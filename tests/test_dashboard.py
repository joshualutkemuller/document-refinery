from __future__ import annotations

from collections.abc import Callable

from document_refinery.domain.models import SilverExtraction, ValidatorStatus, ValueType
from document_refinery.quality.dashboard import render_dashboard
from document_refinery.quality.reporting import QualityReporter


def test_dashboard_renders_self_contained_html(
    extraction: Callable[..., SilverExtraction],
) -> None:
    rows = (
        extraction(extraction_id="a", field_path="eligibility[0].asset_criterion"),
        extraction(
            extraction_id="b",
            field_path="eligibility[0].haircut_pct",
            value_type=ValueType.NOT_FOUND,
            normalized_value="not_found",
            raw_value="not_found",
        ),
    )
    report = QualityReporter().build(rows)
    html = render_dashboard(report)

    # Self-contained: no external assets or scripts.
    assert "<script" not in html
    assert "http://" not in html and "https://" not in html
    # Theme-aware.
    assert "prefers-color-scheme: dark" in html
    # KPI tiles and the per-document table are present.
    assert "Fields extracted" in html
    assert "Per-document coverage" in html
    assert "doc-1" in html
    # Status legend labels accompany the colours (never colour-alone).
    assert "confirmed" in html and "disputed" in html


def test_dashboard_flags_disputes(
    extraction: Callable[..., SilverExtraction],
) -> None:
    rows = (extraction(validator_status=ValidatorStatus.DISPUTED),)
    report = QualityReporter().build(rows)
    html = render_dashboard(report)
    assert "pill-alert" in html  # dispute highlighted in the per-doc table
    assert "tile-alert" in html  # open-disputes KPI flagged


def test_dashboard_escapes_untrusted_text(
    extraction: Callable[..., SilverExtraction],
) -> None:
    rows = (extraction(doc_id="doc-<script>evil</script>"),)
    report = QualityReporter().build(rows)
    html = render_dashboard(report)
    assert "<script>evil" not in html
    assert "&lt;script&gt;evil" in html


def test_reporter_per_document_breakdown(
    extraction: Callable[..., SilverExtraction],
) -> None:
    rows = (
        extraction(extraction_id="a", doc_id="d1"),
        extraction(extraction_id="b", doc_id="d2"),
    )
    payload = QualityReporter().build(rows).dashboard_payload
    per_doc = payload["per_document"]
    assert isinstance(per_doc, list)
    assert {d["doc_id"] for d in per_doc} == {"d1", "d2"}
