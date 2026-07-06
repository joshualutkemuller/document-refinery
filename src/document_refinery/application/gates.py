"""Owner Gate A approval and review packet generation."""

from __future__ import annotations

import html
import json
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path

from document_refinery.domain.models import SilverExtraction, ValidatorStatus


@dataclass(frozen=True, slots=True)
class GateADecision:
    doc_id: str
    approved: bool
    decided_by: str
    decided_at: datetime
    note: str | None = None


class GateAService:
    def create_review_packet(
        self,
        *,
        output_directory: Path,
        extractions: tuple[SilverExtraction, ...],
    ) -> tuple[Path, Path]:
        if not extractions:
            raise ValueError("review packet requires silver extractions")
        output_directory.mkdir(parents=True, exist_ok=True)
        doc_id = extractions[0].doc_id
        payload = [_silver_payload(row) for row in extractions]
        json_path = output_directory / f"{doc_id}.review.json"
        html_path = output_directory / f"{doc_id}.review.html"
        json_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
        rows = "\n".join(_review_row_html(row) for row in extractions)
        html_path.write_text(
            _review_html(doc_id=doc_id, rows=rows),
            encoding="utf-8",
        )
        return json_path, html_path

    def decide(
        self,
        *,
        extractions: tuple[SilverExtraction, ...],
        decided_by: str,
        approved: bool,
        note: str | None = None,
    ) -> GateADecision:
        if not decided_by.strip():
            raise ValueError("Gate A requires an identified reviewer")
        statuses = {row.validator_status for row in extractions}
        if approved and not statuses <= {
            ValidatorStatus.CONFIRMED,
            ValidatorStatus.CORRECTED,
        }:
            raise ValueError("Gate A cannot approve pending or disputed extractions")
        return GateADecision(
            doc_id=extractions[0].doc_id,
            approved=approved,
            decided_by=decided_by,
            decided_at=datetime.now(UTC),
            note=note,
        )


def _silver_payload(row: SilverExtraction) -> dict[str, object]:
    payload = asdict(row)
    payload["value_type"] = row.value_type.value
    payload["validator_status"] = row.validator_status.value
    payload["created_at"] = row.created_at.isoformat() if row.created_at else None
    return payload


def _review_row_html(row: SilverExtraction) -> str:
    status = html.escape(row.validator_status.value)
    status_class = f' class="{status}"' if row.validator_status is ValidatorStatus.DISPUTED else ""
    return (
        "<tr>"
        f"<td>{html.escape(row.field_path)}</td>"
        f"<td>{html.escape(row.effective_value)}</td>"
        f"<td{status_class}>{status}</td>"
        f"<td>{html.escape(row.source_locator)}</td>"
        f"<td>{html.escape(row.source_clause)}</td>"
        "</tr>"
    )


def _review_html(*, doc_id: str, rows: str) -> str:
    # Read-only artifact for comfortable reading of clauses. All review actions
    # (confirm/correct/dispute) happen through the `review` CLI, not this page.
    safe_doc = html.escape(doc_id)
    style = (
        "body{font:14px system-ui;margin:2rem;color:#172033}"
        "table{border-collapse:collapse;width:100%}"
        "th,td{border:1px solid #ccd3df;padding:.5rem;text-align:left;vertical-align:top}"
        "th{background:#edf2f7} .disputed{color:#a01818;font-weight:600}"
    )
    return (
        "<!doctype html>\n"
        '<html lang="en"><head><meta charset="utf-8">\n'
        f"<title>Gate A review — {safe_doc}</title>\n"
        f"<style>{style}</style></head><body>\n"
        f"<h1>Gate A review — {safe_doc}</h1>\n"
        "<p>Read-only view. Confirm, correct, or dispute each value with the "
        "<code>document-refinery review</code> CLI; disputes block approval "
        "until resolved.</p>\n"
        "<table><thead><tr><th>Field</th><th>Value</th><th>Validator</th>"
        "<th>Locator</th><th>Clause</th></tr></thead>"
        f"<tbody>{rows}</tbody></table>\n"
        "</body></html>\n"
    )

