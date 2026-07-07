"""Silver-to-gold promotion for margin requirements (Gate S).

Groups validated ``requirement[i].*`` silver rows from a ``margin_requirement``
document into canonical, bitemporal :class:`GoldMarginRequirement` records — one
per indexed requirement group — carrying document-level context (model, as-of
date, regulatory regime) and full silver lineage. Landed only after Gate A
sign-off and behind Gate S. Extractors never write here (Locked Decision 2).
"""

from __future__ import annotations

import re
from collections.abc import Iterable
from datetime import date, datetime

from document_refinery.application.promotion import PromotionError
from document_refinery.domain.models import (
    GoldMarginRequirement,
    MarginType,
    SilverExtraction,
    ValidatorStatus,
    ValueType,
)

_REQUIREMENT_INDEX = re.compile(r"^requirement\[(\d+)\]\.(.+)$")
_DOC_SUFFIXES = ("model", "as_of_date", "regulatory_regime", "base_currency")
_REQUIRED = ("counterparty", "margin_type", "required_amount")


class MarginRequirementPromotion:
    """Aggregate validated ``requirement[i]`` silver rows into gold records."""

    def promote(
        self,
        extractions: Iterable[SilverExtraction],
        *,
        knowledge_from: datetime,
    ) -> tuple[GoldMarginRequirement, ...]:
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
        if len({row.doc_id for row in rows}) != 1:
            raise PromotionError("a gold record cannot combine multiple documents")

        present = tuple(row for row in rows if row.value_type is not ValueType.NOT_FOUND)
        context = self._context(present)
        groups = self._group(present)
        if not groups:
            raise PromotionError("no requirement[i] rows to promote")

        return tuple(
            self._promote_one(
                groups[index],
                context=context,
                knowledge_from=knowledge_from,
                doc_id=rows[0].doc_id,
            )
            for index in sorted(groups)
        )

    def _promote_one(
        self,
        fields: dict[str, SilverExtraction],
        *,
        context: dict[str, SilverExtraction],
        knowledge_from: datetime,
        doc_id: str,
    ) -> GoldMarginRequirement:
        missing = [name for name in _REQUIRED if name not in fields]
        if missing:
            raise PromotionError(
                f"margin requirement missing required fields: {', '.join(missing)}"
            )
        currency = self._currency(fields)
        if currency is None:
            raise PromotionError("margin requirement missing a currency")
        try:
            margin_type = MarginType(fields["margin_type"].effective_value)
        except ValueError as error:
            raise PromotionError(
                f"invalid margin_type: {fields['margin_type'].effective_value}"
            ) from error

        lineage = {row.extraction_id for row in fields.values()}
        lineage.update(row.extraction_id for row in context.values())
        return GoldMarginRequirement(
            counterparty=fields["counterparty"].effective_value,
            agreement_id=self._opt(fields, "agreement_id"),
            csa_schedule_ref=self._opt(fields, "csa_schedule_ref"),
            netting_set_id=self._opt(fields, "netting_set_id"),
            margin_type=margin_type,
            required_amount=float(fields["required_amount"].effective_value),
            currency=currency,
            risk_class=self._opt(fields, "risk_class"),
            model=self._opt(context, "model"),
            regulatory_regime=self._opt(context, "regulatory_regime"),
            valuation_date=self._opt_date(fields, "valuation_date"),
            valid_from=self._opt_date(fields, "valuation_date")
            or self._opt_date(context, "as_of_date"),
            valid_to=None,
            knowledge_from=knowledge_from,
            knowledge_to=None,
            silver_extraction_ids=tuple(sorted(lineage)),
            doc_id=doc_id,
        )

    @staticmethod
    def _group(
        rows: tuple[SilverExtraction, ...],
    ) -> dict[int, dict[str, SilverExtraction]]:
        groups: dict[int, dict[str, SilverExtraction]] = {}
        for row in rows:
            match = _REQUIREMENT_INDEX.match(row.field_path)
            if match is None:
                continue
            index = int(match.group(1))
            suffix = match.group(2)
            bucket = groups.setdefault(index, {})
            if suffix in bucket:
                raise PromotionError(f"duplicate silver field: requirement[{index}].{suffix}")
            bucket[suffix] = row
        return groups

    @staticmethod
    def _context(rows: tuple[SilverExtraction, ...]) -> dict[str, SilverExtraction]:
        context: dict[str, SilverExtraction] = {}
        for row in rows:
            if _REQUIREMENT_INDEX.match(row.field_path):
                continue
            suffix = row.field_path.rsplit(".", 1)[-1] if "." in row.field_path else row.field_path
            if suffix in _DOC_SUFFIXES and suffix not in context:
                context[suffix] = row
        return context

    @staticmethod
    def _currency(fields: dict[str, SilverExtraction]) -> str | None:
        row = fields.get("currency")
        if row is not None:
            return row.effective_value
        amount = fields.get("required_amount")
        return amount.currency if amount and amount.currency else None

    @staticmethod
    def _opt(fields: dict[str, SilverExtraction], name: str) -> str | None:
        row = fields.get(name)
        return row.effective_value if row else None

    @classmethod
    def _opt_date(cls, fields: dict[str, SilverExtraction], name: str) -> date | None:
        value = cls._opt(fields, name)
        return date.fromisoformat(value) if value else None
