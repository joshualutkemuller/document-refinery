"""Quality Reporter outputs at executive, dashboard, and audit altitudes."""

from __future__ import annotations

from dataclasses import dataclass
from statistics import fmean

from document_refinery.domain.models import SilverExtraction, ValidatorStatus, ValueType


@dataclass(frozen=True, slots=True)
class QualityReport:
    executive_briefing: str
    dashboard_payload: dict[str, object]
    audit_appendix: tuple[dict[str, object], ...]


class QualityReporter:
    def build(self, rows: tuple[SilverExtraction, ...]) -> QualityReport:
        if not rows:
            raise ValueError("quality report requires silver rows")
        found = [row for row in rows if row.value_type is not ValueType.NOT_FOUND]
        disputed = [
            row for row in rows if row.validator_status is ValidatorStatus.DISPUTED
        ]
        ambiguous = [row for row in rows if row.ambiguity_flag]
        completeness = len(found) / len(rows)
        mean_confidence = fmean(row.confidence for row in rows)
        doc_count = len({row.doc_id for row in rows})
        briefing = (
            f"Processed {doc_count} document(s) with {completeness:.1%} field completeness, "
            f"{mean_confidence:.1%} mean extraction confidence, {len(disputed)} disputed "
            f"field(s), and {len(ambiguous)} explicitly ambiguous field(s). "
            "Gold promotion remains gated on independent validation and Gate A approval."
        )
        dashboard = {
            "document_count": doc_count,
            "field_count": len(rows),
            "completeness_pct": round(completeness * 100, 2),
            "mean_confidence": round(mean_confidence, 4),
            "dispute_count": len(disputed),
            "ambiguity_count": len(ambiguous),
            "validator_status_counts": {
                status.value: sum(row.validator_status is status for row in rows)
                for status in ValidatorStatus
            },
        }
        audit: tuple[dict[str, object], ...] = tuple(
            {
                "doc_id": row.doc_id,
                "extraction_id": row.extraction_id,
                "field_path": row.field_path,
                "normalized_value": row.normalized_value,
                "source_clause": row.source_clause,
                "source_locator": row.source_locator,
                "validator_status": row.validator_status.value,
            }
            for row in rows
        )
        return QualityReport(briefing, dashboard, audit)
