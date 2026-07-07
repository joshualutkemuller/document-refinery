"""Deterministic silver-to-gold promotion and bitemporal history behavior."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import replace
from datetime import date, datetime

from document_refinery.domain.models import (
    GoldCollateralLimit,
    GoldEligibilityTerm,
    GoldMarginRequirement,
    MarginType,
    SilverExtraction,
    ValidatorStatus,
    ValueType,
)


class PromotionError(ValueError):
    """Raised when silver rows cannot safely produce a gold record."""


class EligibilityPromotion:
    """Aggregate one eligibility criterion's validated silver fields."""

    REQUIRED_FIELDS = {
        "counterparty",
        "agreement_id",
        "schedule_version",
        "margin_type",
        "asset_criterion",
        "eligible",
        "valid_from",
    }

    def promote(
        self,
        extractions: Iterable[SilverExtraction],
        *,
        knowledge_from: datetime,
    ) -> GoldEligibilityTerm:
        rows = tuple(extractions)
        if not rows:
            raise PromotionError("at least one silver extraction is required")
        if any(
            row.validator_status
            not in {ValidatorStatus.CONFIRMED, ValidatorStatus.CORRECTED}
            or row.ambiguity_flag
            for row in rows
        ):
            raise PromotionError("all silver rows must be confirmed and unambiguous")
        doc_ids = {row.doc_id for row in rows}
        if len(doc_ids) != 1:
            raise PromotionError("a gold record cannot combine multiple documents")

        fields = self._index(
            tuple(row for row in rows if row.value_type is not ValueType.NOT_FOUND)
        )
        missing = self.REQUIRED_FIELDS - fields.keys()
        if missing:
            raise PromotionError(f"missing required fields: {', '.join(sorted(missing))}")

        return GoldEligibilityTerm(
            counterparty=fields["counterparty"].effective_value,
            agreement_id=fields["agreement_id"].effective_value,
            schedule_version=fields["schedule_version"].effective_value,
            margin_type=MarginType(fields["margin_type"].effective_value),
            asset_criterion=fields["asset_criterion"].effective_value,
            eligible=self._boolean(fields["eligible"].effective_value),
            haircut_pct=self._optional_float(fields, "haircut_pct"),
            concentration_limit_pct=self._optional_float(fields, "concentration_limit_pct"),
            concentration_basis=self._optional(fields, "concentration_basis"),
            currency_scope=self._csv(fields, "currency_scope"),
            rating_floor=self._optional(fields, "rating_floor"),
            tenor_cap_days=self._optional_int(fields, "tenor_cap_days"),
            valid_from=date.fromisoformat(fields["valid_from"].effective_value),
            valid_to=self._optional_date(fields, "valid_to"),
            knowledge_from=knowledge_from,
            knowledge_to=None,
            silver_extraction_ids=tuple(sorted(row.extraction_id for row in rows)),
            doc_id=rows[0].doc_id,
        )

    @staticmethod
    def _index(rows: tuple[SilverExtraction, ...]) -> Mapping[str, SilverExtraction]:
        indexed: dict[str, SilverExtraction] = {}
        for row in rows:
            field = row.field_path.rsplit(".", 1)[-1]
            if field in indexed:
                raise PromotionError(f"duplicate silver field: {field}")
            indexed[field] = row
        return indexed

    @staticmethod
    def _boolean(value: str) -> bool:
        normalized = value.casefold()
        if normalized not in {"true", "false"}:
            raise PromotionError(f"invalid boolean: {value}")
        return normalized == "true"

    @staticmethod
    def _optional(fields: Mapping[str, SilverExtraction], name: str) -> str | None:
        row = fields.get(name)
        return row.effective_value if row else None

    @classmethod
    def _optional_float(
        cls, fields: Mapping[str, SilverExtraction], name: str
    ) -> float | None:
        value = cls._optional(fields, name)
        return float(value) if value is not None else None

    @classmethod
    def _optional_int(cls, fields: Mapping[str, SilverExtraction], name: str) -> int | None:
        value = cls._optional(fields, name)
        return int(value) if value is not None else None

    @classmethod
    def _optional_date(cls, fields: Mapping[str, SilverExtraction], name: str) -> date | None:
        value = cls._optional(fields, name)
        return date.fromisoformat(value) if value is not None else None

    @classmethod
    def _csv(cls, fields: Mapping[str, SilverExtraction], name: str) -> tuple[str, ...]:
        value = cls._optional(fields, name)
        return tuple(part.strip() for part in value.split(",") if part.strip()) if value else ()


class InMemoryBitemporalHistory:
    """Reference implementation for knowledge-time version closure."""

    def __init__(self) -> None:
        self._records: list[GoldEligibilityTerm] = []

    @property
    def records(self) -> tuple[GoldEligibilityTerm, ...]:
        return tuple(self._records)

    def upsert(self, record: GoldEligibilityTerm) -> None:
        key = (
            record.counterparty,
            record.agreement_id,
            record.margin_type,
            record.asset_criterion,
            record.valid_from,
        )
        for index, current in enumerate(self._records):
            current_key = (
                current.counterparty,
                current.agreement_id,
                current.margin_type,
                current.asset_criterion,
                current.valid_from,
            )
            if current_key == key and current.knowledge_to is None:
                if record.knowledge_from <= current.knowledge_from:
                    raise PromotionError(
                        "new knowledge version must be later than the active version"
                    )
                self._records[index] = replace(current, knowledge_to=record.knowledge_from)
        self._records.append(record)


class InMemoryLimitHistory:
    """Knowledge-time version closure for gold collateral limits."""

    def __init__(self) -> None:
        self._records: list[GoldCollateralLimit] = []

    @property
    def records(self) -> tuple[GoldCollateralLimit, ...]:
        return tuple(self._records)

    @staticmethod
    def _key(record: GoldCollateralLimit) -> tuple[object, ...]:
        return (
            record.counterparty,
            record.agreement_id,
            record.schedule_version,
            record.dimension,
            record.scope_value,
            record.valid_from,
        )

    def upsert(self, record: GoldCollateralLimit) -> None:
        for index, current in enumerate(self._records):
            if self._key(current) == self._key(record) and current.knowledge_to is None:
                if record.knowledge_from <= current.knowledge_from:
                    raise PromotionError(
                        "new knowledge version must be later than the active version"
                    )
                self._records[index] = replace(current, knowledge_to=record.knowledge_from)
        self._records.append(record)


class InMemoryMarginHistory:
    """Knowledge-time version closure for gold margin requirements."""

    def __init__(self) -> None:
        self._records: list[GoldMarginRequirement] = []

    @property
    def records(self) -> tuple[GoldMarginRequirement, ...]:
        return tuple(self._records)

    @staticmethod
    def _key(record: GoldMarginRequirement) -> tuple[object, ...]:
        return (
            record.counterparty,
            record.agreement_id,
            record.netting_set_id,
            record.margin_type,
            record.valuation_date,
        )

    def upsert(self, record: GoldMarginRequirement) -> None:
        for index, current in enumerate(self._records):
            if self._key(current) == self._key(record) and current.knowledge_to is None:
                if record.knowledge_from <= current.knowledge_from:
                    raise PromotionError(
                        "new knowledge version must be later than the active version"
                    )
                self._records[index] = replace(current, knowledge_to=record.knowledge_from)
        self._records.append(record)
