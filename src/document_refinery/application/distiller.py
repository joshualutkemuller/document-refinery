"""Distiller learning loop: turn owner corrections into reusable knowledge.

The durable correction log (handoff §5.7, Locked-Decision-adjacent instruction 5)
records every owner confirm/correct/dispute. On its own that log is an audit
trail; the distiller is what stops corrections from *evaporating*. It replays the
log into two owner-reviewable outputs:

1. **Constitution-rule proposals** — when the same field is corrected the same way
   more than once, propose a normalization rule for the document class
   ("map 'IG' -> 'Investment Grade' for eligibility.rating_floor"). Ambiguous
   corrections (one original value corrected to several different targets) and
   disputes become *review-flag* proposals instead of silent rules.
2. **Golden-case proposals** — every owner-decided value (a correction's target,
   or a confirmed extractor value) becomes a candidate golden ground-truth entry,
   keyed by document and field path, ready to seed the regression corpus.

The distiller only *proposes*. It never mutates a constitution, a golden set, or
silver/gold — the owner batch-approves (§5.7). Disputes with no agreed value are
surfaced as unresolved rather than turned into truth.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime

from document_refinery.application.corrections import CorrectionAction, CorrectionRecord

DEFAULT_MIN_RULE_OCCURRENCES = 2


def schema_of(field_path: str) -> str:
    """Document-class proxy: the schema prefix of a field path.

    ``eligibility[0].haircut_pct`` -> ``eligibility``. Falls back to the whole
    path when there is no ``[`` or ``.`` separator.
    """
    for index, char in enumerate(field_path):
        if char in "[.":
            return field_path[:index]
    return field_path


def field_suffix_of(field_path: str) -> str:
    """Record-independent field name: ``eligibility[0].haircut_pct`` -> ``haircut_pct``."""
    return field_path.rsplit(".", 1)[-1]


@dataclass(frozen=True, slots=True)
class ConstitutionRuleProposal:
    schema: str
    field_suffix: str
    kind: str  # "normalization" | "review_flag"
    original_value: str | None
    corrected_value: str | None
    occurrences: int
    reviewers: tuple[str, ...]
    example_doc_ids: tuple[str, ...]
    rationale: str
    notes: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, object]:
        return {
            "schema": self.schema,
            "field_suffix": self.field_suffix,
            "kind": self.kind,
            "original_value": self.original_value,
            "corrected_value": self.corrected_value,
            "occurrences": self.occurrences,
            "reviewers": list(self.reviewers),
            "example_doc_ids": list(self.example_doc_ids),
            "rationale": self.rationale,
            "notes": list(self.notes),
        }


@dataclass(frozen=True, slots=True)
class GoldenCaseProposal:
    doc_id: str
    schema: str
    field_path: str
    field_suffix: str
    expected_value: str
    source: str  # "correction" | "confirmed"
    reviewer: str
    decided_at: datetime
    note: str | None = None

    def to_dict(self) -> dict[str, object]:
        return {
            "doc_id": self.doc_id,
            "schema": self.schema,
            "field_path": self.field_path,
            "field_suffix": self.field_suffix,
            "expected_value": self.expected_value,
            "source": self.source,
            "reviewer": self.reviewer,
            "decided_at": self.decided_at.isoformat(),
            "note": self.note,
        }


@dataclass(frozen=True, slots=True)
class UnresolvedDispute:
    doc_id: str
    field_path: str
    reviewer: str
    decided_at: datetime
    note: str | None = None

    def to_dict(self) -> dict[str, object]:
        return {
            "doc_id": self.doc_id,
            "field_path": self.field_path,
            "reviewer": self.reviewer,
            "decided_at": self.decided_at.isoformat(),
            "note": self.note,
        }


@dataclass(frozen=True, slots=True)
class DistillerReport:
    constitution_rules: tuple[ConstitutionRuleProposal, ...]
    golden_cases: tuple[GoldenCaseProposal, ...]
    unresolved_disputes: tuple[UnresolvedDispute, ...]
    correction_count: int

    def to_dict(self) -> dict[str, object]:
        return {
            "correction_count": self.correction_count,
            "constitution_rules": [rule.to_dict() for rule in self.constitution_rules],
            "golden_cases": [case.to_dict() for case in self.golden_cases],
            "unresolved_disputes": [d.to_dict() for d in self.unresolved_disputes],
        }

    def ground_truth_fragment(self) -> dict[str, dict[str, object]]:
        """Golden cases shaped like the accuracy harness ground_truth.json.

        ``{doc_id: {"owner_verified": false, "expected": {field_path: value}}}``.
        The owner reviews and merges this into a corpus's ground truth; it is left
        ``owner_verified: false`` because a distilled proposal is not yet a signed
        golden case.
        """
        expected: dict[str, dict[str, object]] = {}
        for case in self.golden_cases:
            block = expected.setdefault(case.doc_id, {"owner_verified": False, "expected": {}})
            fields = block["expected"]
            assert isinstance(fields, dict)
            fields[case.field_path] = case.expected_value
        return expected

    def to_markdown(self) -> str:
        lines = [
            "# Distiller proposals",
            "",
            f"Replayed {self.correction_count} owner action(s) from the correction log.",
            "",
            f"- Constitution-rule proposals: {len(self.constitution_rules)}",
            f"- Golden-case proposals: {len(self.golden_cases)}",
            f"- Unresolved disputes: {len(self.unresolved_disputes)}",
            "",
            "## Constitution-rule proposals",
        ]
        if not self.constitution_rules:
            lines.append("_None — no repeated corrections or disputes yet._")
        for rule in self.constitution_rules:
            if rule.kind == "normalization":
                lines.append(
                    f"- **[{rule.schema}.{rule.field_suffix}]** normalize "
                    f"`{rule.original_value}` -> `{rule.corrected_value}` "
                    f"({rule.occurrences}×; {rule.rationale})"
                )
            else:
                lines.append(
                    f"- **[{rule.schema}.{rule.field_suffix}]** review-flag "
                    f"({rule.occurrences}×; {rule.rationale})"
                )
                for note in rule.notes:
                    lines.append(f"    - note: {note}")
        lines += ["", "## Unresolved disputes"]
        if not self.unresolved_disputes:
            lines.append("_None._")
        for dispute in self.unresolved_disputes:
            note = f" — {dispute.note}" if dispute.note else ""
            lines.append(f"- {dispute.doc_id} `{dispute.field_path}` (by {dispute.reviewer}){note}")
        return "\n".join(lines) + "\n"


class Distiller:
    """Replays owner corrections into constitution and golden-set proposals."""

    def __init__(self, *, min_rule_occurrences: int = DEFAULT_MIN_RULE_OCCURRENCES) -> None:
        if min_rule_occurrences < 1:
            raise ValueError("min_rule_occurrences must be positive")
        self.min_rule_occurrences = min_rule_occurrences

    def distill(self, records: tuple[CorrectionRecord, ...]) -> DistillerReport:
        golden_cases: list[GoldenCaseProposal] = []
        unresolved: list[UnresolvedDispute] = []
        # (schema, field_suffix, original) -> {corrected_value: [records]}
        correction_groups: dict[tuple[str, str, str], dict[str, list[CorrectionRecord]]] = (
            defaultdict(lambda: defaultdict(list))
        )
        dispute_groups: dict[tuple[str, str], list[CorrectionRecord]] = defaultdict(list)

        for record in records:
            schema = schema_of(record.field_path)
            suffix = field_suffix_of(record.field_path)
            if record.action is CorrectionAction.CORRECT and record.corrected_value is not None:
                golden_cases.append(
                    GoldenCaseProposal(
                        doc_id=record.doc_id,
                        schema=schema,
                        field_path=record.field_path,
                        field_suffix=suffix,
                        expected_value=record.corrected_value,
                        source="correction",
                        reviewer=record.reviewer,
                        decided_at=record.decided_at,
                        note=record.note,
                    )
                )
                correction_groups[(schema, suffix, record.previous_value)][
                    record.corrected_value
                ].append(record)
            elif record.action is CorrectionAction.CONFIRM:
                golden_cases.append(
                    GoldenCaseProposal(
                        doc_id=record.doc_id,
                        schema=schema,
                        field_path=record.field_path,
                        field_suffix=suffix,
                        expected_value=record.previous_value,
                        source="confirmed",
                        reviewer=record.reviewer,
                        decided_at=record.decided_at,
                        note=record.note,
                    )
                )
            elif record.action is CorrectionAction.DISPUTE:
                unresolved.append(
                    UnresolvedDispute(
                        doc_id=record.doc_id,
                        field_path=record.field_path,
                        reviewer=record.reviewer,
                        decided_at=record.decided_at,
                        note=record.note,
                    )
                )
                dispute_groups[(schema, suffix)].append(record)

        rules = self._constitution_rules(correction_groups, dispute_groups)
        return DistillerReport(
            constitution_rules=rules,
            golden_cases=tuple(golden_cases),
            unresolved_disputes=tuple(unresolved),
            correction_count=len(records),
        )

    def _constitution_rules(
        self,
        correction_groups: dict[tuple[str, str, str], dict[str, list[CorrectionRecord]]],
        dispute_groups: dict[tuple[str, str], list[CorrectionRecord]],
    ) -> tuple[ConstitutionRuleProposal, ...]:
        rules: list[ConstitutionRuleProposal] = []
        for (schema, suffix, original), by_target in sorted(correction_groups.items()):
            total = sum(len(recs) for recs in by_target.values())
            if len(by_target) > 1:
                # One original value corrected to several targets: the owner must
                # decide the canonical mapping — never guess silently.
                rules.append(
                    ConstitutionRuleProposal(
                        schema=schema,
                        field_suffix=suffix,
                        kind="review_flag",
                        original_value=original,
                        corrected_value=None,
                        occurrences=total,
                        reviewers=_reviewers(recs for recs in by_target.values()),
                        example_doc_ids=_doc_ids(recs for recs in by_target.values()),
                        rationale=(
                            f"'{original}' was corrected to "
                            f"{len(by_target)} different values ("
                            + ", ".join(sorted(by_target)) + "); needs a canonical rule"
                        ),
                    )
                )
                continue
            target, recs = next(iter(by_target.items()))
            if total < self.min_rule_occurrences:
                continue  # one-off: captured as a golden case, not yet a rule
            rules.append(
                ConstitutionRuleProposal(
                    schema=schema,
                    field_suffix=suffix,
                    kind="normalization",
                    original_value=original,
                    corrected_value=target,
                    occurrences=total,
                    reviewers=_reviewers([recs]),
                    example_doc_ids=_doc_ids([recs]),
                    rationale=f"corrected the same way {total} times",
                )
            )
        for (schema, suffix), recs in sorted(dispute_groups.items()):
            notes = tuple(sorted({rec.note for rec in recs if rec.note}))
            rules.append(
                ConstitutionRuleProposal(
                    schema=schema,
                    field_suffix=suffix,
                    kind="review_flag",
                    original_value=None,
                    corrected_value=None,
                    occurrences=len(recs),
                    reviewers=_reviewers([recs]),
                    example_doc_ids=_doc_ids([recs]),
                    rationale=f"disputed {len(recs)} time(s); constitution guidance may be missing",
                    notes=notes,
                )
            )
        return tuple(rules)


def _reviewers(groups: Iterable[list[CorrectionRecord]]) -> tuple[str, ...]:
    seen: set[str] = set()
    for recs in groups:
        for rec in recs:
            seen.add(rec.reviewer)
    return tuple(sorted(seen))


def _doc_ids(groups: Iterable[list[CorrectionRecord]]) -> tuple[str, ...]:
    ordered: list[str] = []
    for recs in groups:
        for rec in recs:
            if rec.doc_id not in ordered:
                ordered.append(rec.doc_id)
    return tuple(ordered)
