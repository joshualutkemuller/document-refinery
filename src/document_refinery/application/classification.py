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
    profile: str = "normalized"


class EligibilityScheduleClassifier:
    DOC_CLASS = "collateral_eligibility_schedule"
    VALUATION_DOC_CLASS = "collateral_valuation_margin_table"

    def classify(self, text: str, *, hint: str | None = None) -> Classification:
        valuation_profile = _valuation_profile(text)
        if valuation_profile:
            return Classification(
                doc_class=self.VALUATION_DOC_CLASS,
                confidence=0.85,
                counterparty=None,
                agreement_id=None,
                review_required=True,
                profile=valuation_profile,
            )
        public_profile = _public_profile(text)
        if public_profile:
            return Classification(
                doc_class=self.DOC_CLASS,
                confidence=0.99,
                counterparty=None,
                agreement_id=None,
                review_required=False,
                profile=public_profile,
            )
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
            profile="normalized",
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


def _public_profile(text: str) -> str | None:
    lowered = text.casefold()
    signatures = (
        (
            "ficc_gsd",
            (
                "ficc government securities division",
                "schedule of haircuts for eligible clearing fund securities",
            ),
        ),
        (
            "dtc",
            (
                "depository trust and clearing corporation",
                "schedule of haircuts for eligible collateral securities",
            ),
        ),
        (
            "cme",
            (
                "cme group",
                "acceptable performance bond collateral",
                "haircut schedule",
            ),
        ),
        (
            "isda_vm",
            (
                "isda collateral asset definition",
                "eligible collateral (vm)",
                "valuation percentage",
            ),
        ),
        (
            "portfolio_guidelines",
            (
                "investment guidelines & portfolio requirements",
                "single issuer concentration limit",
                "eligible assets",
            ),
        ),
    )
    for profile, required in signatures:
        if all(value in lowered for value in required):
            return profile
    return None


def _valuation_profile(text: str) -> str | None:
    lowered = text.casefold()
    if all(
        phrase in lowered
        for phrase in (
            "collateral valuation",
            "securities valuation and margins table",
            "loan valuation and margins tables",
        )
    ):
        return "fed_collateral_valuation"
    return None
