"""Conservative document classifier for the Phase 1 class."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Classification:
    doc_class: str
    confidence: float
    counterparty: str | None
    agreement_id: str | None
    review_required: bool


class EligibilityScheduleClassifier:
    DOC_CLASS = "collateral_eligibility_schedule"

    def classify(self, text: str, *, hint: str | None = None) -> Classification:
        fields = _header_fields(text)
        lowered = text.casefold()
        evidence = sum(
            phrase in lowered
            for phrase in (
                "collateral eligibility schedule",
                "eligible collateral",
                "agreement id:",
                "schedule version:",
            )
        )
        hinted = hint == self.DOC_CLASS
        confidence = min(1.0, 0.2 * evidence + (0.2 if hinted else 0.0))
        return Classification(
            doc_class=self.DOC_CLASS if confidence >= 0.6 else "unknown",
            confidence=confidence,
            counterparty=fields.get("counterparty"),
            agreement_id=fields.get("agreement id"),
            review_required=confidence < 0.8,
        )


def _header_fields(text: str) -> dict[str, str]:
    fields: dict[str, str] = {}
    for line in text.splitlines():
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        normalized = key.strip().casefold()
        if normalized in {
            "counterparty",
            "agreement id",
            "schedule version",
            "margin type",
            "valid from",
        }:
            fields[normalized] = value.strip()
    return fields

