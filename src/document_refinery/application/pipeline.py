"""End-to-end Phase 0/1 orchestration."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from document_refinery.agents.eligibility import (
    EligibilityAdversarialValidator,
    EligibilityScheduleExtractor,
)
from document_refinery.agents.public_schedules import (
    PublicCollateralScheduleExtractor,
    PublicScheduleValidator,
)
from document_refinery.agents.semantic import SemanticExtractor, SemanticValidator
from document_refinery.application.classification import EligibilityScheduleClassifier
from document_refinery.application.gates import GateADecision, GateAService
from document_refinery.application.promotion import EligibilityPromotion
from document_refinery.domain.models import GoldEligibilityTerm, SilverExtraction
from document_refinery.infrastructure.artifacts import ArtifactStore, BronzeDocument
from document_refinery.infrastructure.model_calls import SemanticCallStore
from document_refinery.infrastructure.records import GoldStore, SilverStore
from document_refinery.infrastructure.tasks import TaskStatus, TaskStore


@dataclass(frozen=True, slots=True)
class PipelineResult:
    document: BronzeDocument
    silver_rows: tuple[SilverExtraction, ...]
    gold_rows: tuple[GoldEligibilityTerm, ...]
    gate_decision: GateADecision | None
    review_json: Path
    review_html: Path


class RefineryPipeline:
    def __init__(
        self,
        workspace: Path,
        *,
        semantic_extractor: SemanticExtractor | None = None,
        semantic_validator: SemanticValidator | None = None,
    ) -> None:
        if (semantic_extractor is None) != (semantic_validator is None):
            raise ValueError(
                "semantic extractor and validator must be configured together"
            )
        self.workspace = workspace
        self.artifacts = ArtifactStore(workspace / "artifacts")
        self.tasks = TaskStore(workspace / "refinery_tasks.sqlite3")
        self.silver = SilverStore(workspace / "silver")
        self.gold = GoldStore(workspace / "gold" / "eligibility_terms.jsonl")
        self.classifier = EligibilityScheduleClassifier()
        self.extractor = EligibilityScheduleExtractor()
        self.validator = EligibilityAdversarialValidator()
        self.public_extractor = PublicCollateralScheduleExtractor()
        self.public_validator = PublicScheduleValidator()
        self.semantic_extractor = semantic_extractor
        self.semantic_validator = semantic_validator
        self.semantic_calls = SemanticCallStore(workspace / "model_calls")
        self.gate = GateAService()
        self.promotion = EligibilityPromotion()

    def run(
        self,
        source_path: Path,
        *,
        source: str,
        approved_by: str | None = None,
        language: str = "und",
    ) -> PipelineResult:
        document = self.artifacts.ingest(source_path, source=source)
        self.tasks.create(document.doc_id)
        document, text_artifact = self.artifacts.extract_text(document)
        classification = self.classifier.classify(
            text_artifact.text,
            hint=document.doc_class_hint,
        )
        semantic_route = (
            classification.doc_class == "unknown" or classification.review_required
        )
        if semantic_route and (
            self.semantic_extractor is None or self.semantic_validator is None
        ):
            raise ValueError(
                f"classification requires owner review (confidence={classification.confidence:.2f})"
            )
        self.tasks.transition(document.doc_id, TaskStatus.CLASSIFIED)

        if semantic_route:
            assert self.semantic_extractor is not None
            assert self.semantic_validator is not None
            semantic_extraction = self.semantic_extractor.extract(
                doc_id=document.doc_id,
                doc_class=EligibilityScheduleClassifier.DOC_CLASS,
                text=text_artifact.text,
                language=language,
            )
            semantic_validation = self.semantic_validator.validate(
                doc_id=document.doc_id,
                text=text_artifact.text,
                extractions=semantic_extraction.rows,
                extractor_session_id=self.semantic_extractor.model.session_id,
                language=language,
            )
            extracted = semantic_extraction.rows
            validated = semantic_validation.rows
            self.semantic_calls.write(
                document.doc_id,
                (semantic_extraction.call, semantic_validation.call),
            )
        elif classification.profile == "normalized":
            extracted = self.extractor.extract(
                doc_id=document.doc_id,
                text=text_artifact.text,
            )
            validated = self.validator.validate(
                text=text_artifact.text,
                extractions=extracted,
            )
        else:
            extracted = self.public_extractor.extract(
                profile=classification.profile,
                doc_id=document.doc_id,
                text=text_artifact.text,
                received_date=document.received_at.date(),
            )
            validated = self.public_validator.validate(
                text=text_artifact.text,
                extractions=extracted,
            )
        self.silver.write(extracted, stage="extracted")
        self.tasks.transition(document.doc_id, TaskStatus.EXTRACTED)

        self.silver.write(validated, stage="validated")
        self.tasks.transition(document.doc_id, TaskStatus.VALIDATED)
        self.tasks.transition(document.doc_id, TaskStatus.GATE_A_PENDING)
        review_json, review_html = self.gate.create_review_packet(
            output_directory=self.workspace / "reviews",
            extractions=validated,
        )
        if approved_by is None:
            return PipelineResult(
                document=document,
                silver_rows=validated,
                gold_rows=(),
                gate_decision=None,
                review_json=review_json,
                review_html=review_html,
            )

        decision = self.gate.decide(
            extractions=validated,
            decided_by=approved_by,
            approved=True,
            note="Approved through the Phase 1 pipeline.",
        )
        self.tasks.transition(document.doc_id, TaskStatus.GATE_A_APPROVED)
        gold_rows = tuple(
            self.promotion.promote(group, knowledge_from=datetime.now(UTC))
            for group in _group_eligibility_rows(validated)
        )
        self.gold.upsert(gold_rows)
        self.tasks.transition(document.doc_id, TaskStatus.GOLD_LANDED)
        return PipelineResult(
            document=document,
            silver_rows=validated,
            gold_rows=gold_rows,
            gate_decision=decision,
            review_json=review_json,
            review_html=review_html,
        )

    def approve(self, doc_id: str, *, approved_by: str) -> tuple[GoldEligibilityTerm, ...]:
        task = self.tasks.get(doc_id)
        if task.status is not TaskStatus.GATE_A_PENDING:
            raise ValueError(f"document is not awaiting Gate A: {task.status}")
        validated = self.silver.read(doc_id, stage="validated")
        self.gate.decide(
            extractions=validated,
            decided_by=approved_by,
            approved=True,
            note="Approved after review of the generated Gate A packet.",
        )
        self.tasks.transition(doc_id, TaskStatus.GATE_A_APPROVED)
        gold_rows = tuple(
            self.promotion.promote(group, knowledge_from=datetime.now(UTC))
            for group in _group_eligibility_rows(validated)
        )
        self.gold.upsert(gold_rows)
        self.tasks.transition(doc_id, TaskStatus.GOLD_LANDED)
        return gold_rows

    def close(self) -> None:
        self.tasks.close()


def _group_eligibility_rows(
    rows: tuple[SilverExtraction, ...],
) -> tuple[tuple[SilverExtraction, ...], ...]:
    groups: dict[int, list[SilverExtraction]] = {}
    for row in rows:
        match = re.match(r"eligibility\[(\d+)]\.", row.field_path)
        if not match:
            continue
        groups.setdefault(int(match.group(1)), []).append(row)
    return tuple(tuple(groups[index]) for index in sorted(groups))
