from __future__ import annotations

import json
from pathlib import Path

import pytest

from document_refinery.cli import main
from document_refinery.quality.accuracy import GoldenCase, load_corpus, score_corpus

_DOC = """Collateral Eligibility Schedule
Eligible Collateral
Counterparty: Atlas Bank
Agreement ID: AGR-001
Schedule Version: 2026-01
Margin Type: VM
Valid From: 2026-01-01
Asset: GOVT_US | Eligible: yes | Haircut: 2% | Concentration Limit: 100% | Currencies: USD, EUR
"""

_EXPECTED = {
    "eligibility[0].counterparty": "Atlas Bank",
    "eligibility[0].agreement_id": "AGR-001",
    "eligibility[0].margin_type": "VM",
    "eligibility[0].valid_from": "2026-01-01",
    "eligibility[0].asset_criterion": "GOVT_US",
    "eligibility[0].eligible": "true",
    "eligibility[0].haircut_pct": "2",
    "eligibility[0].currency_scope": "USD,EUR",
}


def test_perfect_extraction_scores_100() -> None:
    case = GoldenCase(case_id="c1", text=_DOC, expected=_EXPECTED, owner_verified=True)
    report = score_corpus((case,))
    assert report.field_accuracy == 1.0
    assert not report.mismatches
    assert report.locator_coverage == 1.0
    assert report.owner_verified_document_count == 1


def test_wrong_ground_truth_is_flagged_as_mismatch() -> None:
    expected = {**_EXPECTED, "eligibility[0].haircut_pct": "3"}  # human says 3, doc says 2
    case = GoldenCase(case_id="c1", text=_DOC, expected=expected)
    report = score_corpus((case,))
    assert report.field_accuracy < 1.0
    assert any(m.field_path == "eligibility[0].haircut_pct" for m in report.mismatches)
    # Per-field breakdown isolates the weak field.
    assert report.per_field["haircut_pct"] == (0, 1)
    assert report.per_field["counterparty"] == (1, 1)


def test_not_found_expectation_scored() -> None:
    expected = {**_EXPECTED, "eligibility[0].rating_floor": "not_found"}
    case = GoldenCase(case_id="c1", text=_DOC, expected=expected)
    report = score_corpus((case,))
    # not_found expectations count toward total but not toward found-value stats.
    assert report.found_fields == len(_EXPECTED)
    assert report.total_fields == len(_EXPECTED) + 1


def test_release_gate_requires_owner_verification() -> None:
    case = GoldenCase(case_id="c1", text=_DOC, expected=_EXPECTED, owner_verified=False)
    report = score_corpus((case,) * 10)
    assert report.field_accuracy >= 0.95
    assert not report.release_ready()  # not owner-verified


def test_shipped_golden_corpus_is_measurable() -> None:
    corpus = Path(__file__).resolve().parents[1] / "examples" / "golden_corpus"
    cases = load_corpus(corpus)
    assert len(cases) == 10
    report = score_corpus(cases)
    # Realistic, credible accuracy (surfaces real normalization gaps, not 100%).
    assert 0.95 <= report.field_accuracy < 1.0
    assert report.locator_coverage == 1.0
    assert report.owner_verified_document_count == 0
    assert not report.release_ready()
    # The known gaps are the weak fields.
    weak = {name for name, (c, t) in report.per_field.items() if c < t}
    assert weak == {"margin_type", "eligible", "currency_scope", "haircut_pct"}


def test_corpus_check_reports_structural_problems(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    corpus = tmp_path / "corpus"
    corpus.mkdir()
    (corpus / "c1.txt").write_text(_DOC, encoding="utf-8")
    # c2 has ground truth but no .txt; orphan.txt has a file but no ground truth.
    (corpus / "orphan.txt").write_text(_DOC, encoding="utf-8")
    (corpus / "ground_truth.json").write_text(
        json.dumps(
            {
                "c1": {"owner_verified": True, "expected": _EXPECTED},
                "c2": {"owner_verified": True, "expected": _EXPECTED},
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(
        "sys.argv",
        ["document-refinery", "corpus-check", "--corpus", str(corpus), "--json"],
    )
    code = main()

    assert code == 1  # structural problems present
    report = json.loads(capsys.readouterr().out)
    assert report["document_count"] == 2
    assert report["owner_verified_document_count"] == 2
    assert any("c2" in p for p in report["problems"])
    assert any("orphan" in p for p in report["problems"])
    assert "8 more document(s)" in report["release_blockers"]


def test_shipped_rule_schedule_corpus_is_structurally_valid(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    corpus = (
        Path(__file__).resolve().parents[1] / "examples" / "collateral_rule_corpus"
    )
    monkeypatch.setattr(
        "sys.argv",
        ["document-refinery", "corpus-check", "--corpus", str(corpus), "--json"],
    )
    code = main()
    report = json.loads(capsys.readouterr().out)

    assert code == 0  # structurally valid scaffold
    assert report["structurally_valid"] is True
    assert report["document_count"] == 5
    # Ships as an unverified template: the release gate must still block.
    assert report["owner_verified_document_count"] == 0
    assert report["release_blockers"]


def test_corpus_check_passes_on_valid_corpus(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    corpus = tmp_path / "corpus"
    corpus.mkdir()
    (corpus / "c1.txt").write_text(_DOC, encoding="utf-8")
    (corpus / "ground_truth.json").write_text(
        json.dumps({"c1": {"owner_verified": False, "expected": _EXPECTED}}),
        encoding="utf-8",
    )
    monkeypatch.setattr(
        "sys.argv",
        ["document-refinery", "corpus-check", "--corpus", str(corpus), "--json"],
    )
    code = main()

    assert code == 0  # structurally valid even if not yet release-ready
    report = json.loads(capsys.readouterr().out)
    assert report["structurally_valid"] is True
    assert report["problems"] == []
