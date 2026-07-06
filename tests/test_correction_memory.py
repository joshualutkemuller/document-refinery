from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path

from document_refinery.application.correction_memory import CorrectionMemory
from document_refinery.application.corrections import CorrectionAction, CorrectionRecord
from document_refinery.application.pipeline import RefineryPipeline
from document_refinery.application.review_session import build_review_requests, render_review
from document_refinery.domain.models import SilverExtraction
from document_refinery.infrastructure.memory_store import CorrectionMemoryStore

TEXT_A = """Collateral Eligibility Schedule
Eligible Collateral
Counterparty: Atlas Bank
Agreement ID: AGR-001
Schedule Version: 2026-01
Margin Type: VM
Valid From: 2026-01-01
""" + (
    "Asset: GOVT_US | Eligible: yes | Haircut: 2% | Concentration Limit: 100% "
    "| Concentration Basis: market value | Currencies: USD, EUR | Rating Floor: AA- "
    "| Tenor Cap Days: 3650\n"
)
TEXT_B = TEXT_A.replace("AGR-001", "AGR-002")
_CLASS = "collateral_eligibility_schedule"
_CP = "eligibility[0].counterparty"


def _record(**overrides: object) -> CorrectionRecord:
    values: dict[str, object] = {
        "doc_id": "doc-1",
        "extraction_id": "ext-1",
        "field_path": "eligibility[0].counterparty",
        "action": CorrectionAction.CORRECT,
        "reviewer": "Joshua",
        "decided_at": datetime(2026, 7, 6, tzinfo=UTC),
        "previous_status": None,
        "previous_value": "Atlas Bank",
        "corrected_value": "Atlas Bank NA",
        "note": "legal entity name",
    }
    values.update(overrides)
    return CorrectionRecord(**values)  # type: ignore[arg-type]


def test_memory_learns_a_fix_and_suggests_it(
    extraction: Callable[..., SilverExtraction],
) -> None:
    row = extraction(extraction_id="ext-1", field_path="eligibility[0].counterparty")
    memory = CorrectionMemory()
    memory.learn((row,), (_record(),))
    hit = memory.suggest(_CLASS, "eligibility[9].counterparty", "Atlas Bank")
    assert hit is not None and hit.is_fix
    assert hit.corrected_value == "Atlas Bank NA"
    assert hit.occurrences == 1


def test_memory_occurrences_increment(
    extraction: Callable[..., SilverExtraction],
) -> None:
    row = extraction(extraction_id="ext-1", field_path="eligibility[0].counterparty")
    memory = CorrectionMemory()
    memory.learn((row,), (_record(),))
    memory.learn((row,), (_record(reviewer="Alex"),))
    hit = memory.suggest(_CLASS, _CP, "Atlas Bank")
    assert hit is not None and hit.occurrences == 2
    assert hit.last_reviewer == "Alex"


def test_dispute_is_remembered_as_warning(
    extraction: Callable[..., SilverExtraction],
) -> None:
    row = extraction(extraction_id="ext-1", field_path="eligibility[0].haircut_pct")
    memory = CorrectionMemory()
    memory.learn(
        (row,),
        (
            _record(
                action=CorrectionAction.DISPUTE,
                field_path="eligibility[0].haircut_pct",
                corrected_value=None,
                previous_value="2.0",
            ),
        ),
    )
    hit = memory.suggest("collateral_eligibility_schedule", "eligibility[0].haircut_pct", "2.0")
    assert hit is not None and not hit.is_fix  # warning only, no automatic value


def test_memory_persists_across_store_instances(
    tmp_path: Path,
    extraction: Callable[..., SilverExtraction],
) -> None:
    row = extraction(extraction_id="ext-1", field_path="eligibility[0].counterparty")
    store = CorrectionMemoryStore(tmp_path / "mem.jsonl")
    memory = store.load()
    memory.learn((row,), (_record(),))
    store.save(memory)

    reloaded = CorrectionMemoryStore(tmp_path / "mem.jsonl").load()
    hit = reloaded.suggest(_CLASS, _CP, "Atlas Bank")
    assert hit is not None and hit.corrected_value == "Atlas Bank NA"


def test_render_review_shows_memory_hint(
    extraction: Callable[..., SilverExtraction],
) -> None:
    row = extraction(
        extraction_id="ext-1",
        field_path="eligibility[0].counterparty",
        raw_value="Atlas Bank",
        normalized_value="Atlas Bank",
    )
    memory = CorrectionMemory()
    memory.learn((row,), (_record(),))
    suggestions = memory.suggestions_for((row,))
    rendered = render_review((row,), suggestions=suggestions)
    assert "memory: previously corrected to 'Atlas Bank NA'" in rendered


def test_interactive_correct_prefills_remembered_value(
    extraction: Callable[..., SilverExtraction],
) -> None:
    row = extraction(
        extraction_id="ext-1",
        field_path="eligibility[0].counterparty",
        raw_value="Atlas Bank",
        normalized_value="Atlas Bank",
    )
    memory = CorrectionMemory()
    memory.learn((row,), (_record(),))
    suggestions = memory.suggestions_for((row,))
    # Choose correct, then submit a blank value -> the remembered fix is used.
    answers = iter(["o", "", ""])
    requests = build_review_requests(
        (row,),
        prompt=lambda _m: next(answers),
        echo=lambda _m: None,
        suggestions=suggestions,
    )
    assert requests[0].action is CorrectionAction.CORRECT
    assert requests[0].corrected_value == "Atlas Bank NA"


def test_pipeline_learns_across_documents(tmp_path: Path) -> None:
    ws = tmp_path / "ws"
    (tmp_path / "a.txt").write_text(TEXT_A, encoding="utf-8")
    (tmp_path / "b.txt").write_text(TEXT_B, encoding="utf-8")
    pipeline = RefineryPipeline(ws)
    try:
        result_a = pipeline.run(tmp_path / "a.txt", source="t")
        cp = next(r for r in result_a.silver_rows if r.field_path == "eligibility[0].counterparty")
        from document_refinery.application.corrections import CorrectionRequest

        pipeline.apply_corrections(
            result_a.document.doc_id,
            requests=(
                CorrectionRequest(
                    cp.extraction_id,
                    CorrectionAction.CORRECT,
                    corrected_value="Atlas Bank NA",
                ),
            ),
            reviewer="Joshua",
        )
        # A different document with the same mistake gets the learned suggestion.
        result_b = pipeline.run(tmp_path / "b.txt", source="t")
        suggestions = pipeline.memory_suggestions(result_b.silver_rows)
        cp_b = next(
            r for r in result_b.silver_rows if r.field_path == _CP
        )
        assert cp_b.extraction_id in suggestions
        assert suggestions[cp_b.extraction_id].corrected_value == "Atlas Bank NA"
    finally:
        pipeline.close()
