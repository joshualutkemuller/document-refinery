"""Dependency-free domain models enforcing the handoff's locked decisions."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from enum import StrEnum


class ValueType(StrEnum):
    STRING = "string"
    BOOLEAN = "boolean"
    PERCENTAGE = "percentage"
    INTEGER = "integer"
    DATE = "date"
    STRING_ARRAY = "string_array"
    NOT_FOUND = "not_found"


class ValidatorStatus(StrEnum):
    PENDING = "pending"
    CONFIRMED = "confirmed"
    DISPUTED = "disputed"
    CORRECTED = "corrected"


class MarginType(StrEnum):
    VM = "VM"
    IM = "IM"
    REPO = "Repo"
    CLEARING_FUND = "Clearing Fund"
    SECURED_FINANCING = "Secured Financing"


@dataclass(frozen=True, slots=True)
class SilverExtraction:
    extraction_id: str
    doc_id: str
    doc_class: str
    extractor_version: str
    constitution_version: str
    field_path: str
    raw_value: str
    normalized_value: str
    value_type: ValueType
    source_clause: str
    source_locator: str
    confidence: float
    ambiguity_flag: bool = False
    ambiguity_note: str | None = None
    validator_status: ValidatorStatus = ValidatorStatus.PENDING
    unit: str | None = None
    currency: str | None = None
    corrected_value: str | None = None
    corrected_by: str | None = None
    created_at: datetime | None = None

    def __post_init__(self) -> None:
        required = {
            "extraction_id": self.extraction_id,
            "doc_id": self.doc_id,
            "doc_class": self.doc_class,
            "extractor_version": self.extractor_version,
            "constitution_version": self.constitution_version,
            "field_path": self.field_path,
            "source_clause": self.source_clause,
            "source_locator": self.source_locator,
        }
        missing = [name for name, value in required.items() if not value.strip()]
        if missing:
            raise ValueError(f"blank required fields: {', '.join(sorted(missing))}")
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError("confidence must be between 0 and 1")
        if self.ambiguity_flag and not (self.ambiguity_note or "").strip():
            raise ValueError("ambiguous extraction requires ambiguity_note")
        if self.value_type is ValueType.NOT_FOUND:
            if self.normalized_value != "not_found":
                raise ValueError("missing fields must normalize to 'not_found'")
        elif not self.normalized_value.strip():
            raise ValueError("normalized_value cannot be blank; use not_found")
        corrected = self.validator_status is ValidatorStatus.CORRECTED
        if corrected and not (self.corrected_value and self.corrected_by):
            raise ValueError("corrected rows require corrected_value and corrected_by")
        if not corrected and (self.corrected_value or self.corrected_by):
            raise ValueError("correction data requires corrected validator status")

    @property
    def effective_value(self) -> str:
        return self.corrected_value or self.normalized_value

    @property
    def is_promotable(self) -> bool:
        return (
            self.validator_status in {ValidatorStatus.CONFIRMED, ValidatorStatus.CORRECTED}
            and not self.ambiguity_flag
            and self.value_type is not ValueType.NOT_FOUND
        )


@dataclass(frozen=True, slots=True)
class GoldEligibilityTerm:
    counterparty: str
    agreement_id: str
    schedule_version: str
    margin_type: MarginType
    asset_criterion: str
    eligible: bool
    haircut_pct: float | None
    concentration_limit_pct: float | None
    concentration_basis: str | None
    currency_scope: tuple[str, ...]
    rating_floor: str | None
    tenor_cap_days: int | None
    valid_from: date
    valid_to: date | None
    knowledge_from: datetime
    knowledge_to: datetime | None
    silver_extraction_ids: tuple[str, ...]
    doc_id: str

    def __post_init__(self) -> None:
        if not self.silver_extraction_ids:
            raise ValueError("gold records require silver lineage")
        if self.valid_to is not None and self.valid_from > self.valid_to:
            raise ValueError("valid_from must be on or before valid_to")
        if self.knowledge_to is not None and self.knowledge_from > self.knowledge_to:
            raise ValueError("knowledge_from must be on or before knowledge_to")
        for name, value in (
            ("haircut_pct", self.haircut_pct),
            ("concentration_limit_pct", self.concentration_limit_pct),
        ):
            if value is not None and not 0.0 <= value <= 100.0:
                raise ValueError(f"{name} must be between 0 and 100")


class LimitUnit(StrEnum):
    PERCENT = "percent"
    ABSOLUTE = "absolute"


# Reference set for limit dimensions; kept open (promotion does not hard-reject
# unseen dimensions) so a novel but real limit type is not silently dropped.
KNOWN_LIMIT_DIMENSIONS = frozenset(
    {
        "sector",
        "credit_quality",
        "asset_type",
        "asset_class",
        "issuer",
        "country",
        "currency",
        "concentration",
        "tenor",
    }
)


@dataclass(frozen=True, slots=True)
class GoldCollateralLimit:
    """A canonical, bitemporal portfolio limit from a collateral schedule.

    Captures a limit a per-row percentage cannot: a cap on a dimension (sector,
    credit quality, asset type, issuer, country, currency, ...), optionally scoped
    to one value (e.g. sector = "Technology"), stated as an absolute currency
    amount OR a relative percent, measured on a valuation basis (market value vs
    post-haircut value) at an aggregation level. Every value traces to silver
    lineage (Locked Decision 1); this table is landed only through Gate S.
    """

    dimension: str
    scope_value: str | None
    limit_value: float
    limit_unit: LimitUnit
    limit_currency: str | None
    basis: str | None
    aggregation: str | None
    counterparty: str | None
    agreement_id: str | None
    schedule_version: str | None
    clearing_house: str | None
    valid_from: date | None
    valid_to: date | None
    knowledge_from: datetime
    knowledge_to: datetime | None
    silver_extraction_ids: tuple[str, ...]
    doc_id: str

    def __post_init__(self) -> None:
        if not self.silver_extraction_ids:
            raise ValueError("gold records require silver lineage")
        if not self.dimension.strip():
            raise ValueError("a collateral limit requires a dimension")
        if self.limit_unit is LimitUnit.PERCENT and not 0.0 <= self.limit_value <= 100.0:
            raise ValueError("percent limit_value must be between 0 and 100")
        if self.limit_unit is LimitUnit.ABSOLUTE:
            if self.limit_value < 0.0:
                raise ValueError("absolute limit_value must be non-negative")
            if not (self.limit_currency or "").strip():
                raise ValueError("absolute limits require a limit_currency")
        if (
            self.valid_from is not None
            and self.valid_to is not None
            and self.valid_from > self.valid_to
        ):
            raise ValueError("valid_from must be on or before valid_to")
        if self.knowledge_to is not None and self.knowledge_from > self.knowledge_to:
            raise ValueError("knowledge_from must be on or before knowledge_to")
