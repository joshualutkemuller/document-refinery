"""Silver-to-gold promotion for collateral portfolio limits (Gate S).

Groups validated ``limit[i].*`` silver rows from a ``collateral_rule_schedule``
document into canonical, bitemporal :class:`GoldCollateralLimit` records — one per
indexed limit group — carrying the shared schedule identity as context and full
silver lineage. Landed only after Gate A sign-off and behind Gate S, like every
gold table. Extractors never write here (Locked Decision 2).
"""

from __future__ import annotations

import re
from collections.abc import Iterable
from datetime import date, datetime

from document_refinery.application.promotion import PromotionError
from document_refinery.domain.models import (
    GoldCollateralLimit,
    LimitUnit,
    SilverExtraction,
    ValidatorStatus,
    ValueType,
)

_LIMIT_INDEX = re.compile(r"^limit\[(\d+)\]\.(.+)$")
_IDENTITY_SUFFIXES = ("counterparty", "agreement_id", "schedule_version", "clearing_house")


class LimitPromotion:
    """Aggregate validated ``limit[i]`` silver rows into gold limit records."""

    def promote(
        self,
        extractions: Iterable[SilverExtraction],
        *,
        knowledge_from: datetime,
    ) -> tuple[GoldCollateralLimit, ...]:
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

        present = tuple(row for row in rows if row.value_type is not ValueType.NOT_FOUND)
        identity = self._identity(present)
        groups = self._group_limits(present)
        if not groups:
            raise PromotionError("no limit[i] rows to promote")

        records: list[GoldCollateralLimit] = []
        for index in sorted(groups):
            records.append(
                self._promote_one(
                    groups[index],
                    identity=identity,
                    knowledge_from=knowledge_from,
                    doc_id=rows[0].doc_id,
                )
            )
        return tuple(records)

    def _promote_one(
        self,
        fields: dict[str, SilverExtraction],
        *,
        identity: dict[str, SilverExtraction],
        knowledge_from: datetime,
        doc_id: str,
    ) -> GoldCollateralLimit:
        if "dimension" not in fields:
            raise PromotionError("each limit requires a dimension")
        if "limit_value" not in fields:
            raise PromotionError("each limit requires a limit_value")
        if "limit_unit" not in fields:
            raise PromotionError("each limit requires a limit_unit (percent or absolute)")
        unit_value = fields["limit_unit"].effective_value.strip().casefold()
        try:
            limit_unit = LimitUnit(unit_value)
        except ValueError as error:
            raise PromotionError(f"invalid limit_unit: {unit_value}") from error

        lineage = {row.extraction_id for row in fields.values()}
        lineage.update(row.extraction_id for row in identity.values())
        return GoldCollateralLimit(
            dimension=fields["dimension"].effective_value,
            scope_value=self._opt(fields, "scope_value"),
            limit_value=float(fields["limit_value"].effective_value),
            limit_unit=limit_unit,
            limit_currency=self._currency(fields),
            basis=self._opt(fields, "basis"),
            aggregation=self._opt(fields, "aggregation"),
            counterparty=self._opt(identity, "counterparty"),
            agreement_id=self._opt(identity, "agreement_id"),
            schedule_version=self._opt(identity, "schedule_version"),
            clearing_house=self._opt(identity, "clearing_house"),
            valid_from=self._opt_date(identity, "valid_from"),
            valid_to=self._opt_date(identity, "valid_to"),
            knowledge_from=knowledge_from,
            knowledge_to=None,
            silver_extraction_ids=tuple(sorted(lineage)),
            doc_id=doc_id,
        )

    @staticmethod
    def _group_limits(
        rows: tuple[SilverExtraction, ...],
    ) -> dict[int, dict[str, SilverExtraction]]:
        groups: dict[int, dict[str, SilverExtraction]] = {}
        for row in rows:
            match = _LIMIT_INDEX.match(row.field_path)
            if match is None:
                continue
            index = int(match.group(1))
            suffix = match.group(2)
            bucket = groups.setdefault(index, {})
            if suffix in bucket:
                raise PromotionError(f"duplicate silver field: limit[{index}].{suffix}")
            bucket[suffix] = row
        return groups

    @staticmethod
    def _identity(rows: tuple[SilverExtraction, ...]) -> dict[str, SilverExtraction]:
        # Schedule-level context shared by every limit: first non-limit row per suffix.
        identity: dict[str, SilverExtraction] = {}
        wanted = set(_IDENTITY_SUFFIXES) | {"valid_from", "valid_to"}
        for row in rows:
            if _LIMIT_INDEX.match(row.field_path):
                continue
            suffix = row.field_path.rsplit(".", 1)[-1] if "." in row.field_path else row.field_path
            if suffix in wanted and suffix not in identity:
                identity[suffix] = row
        return identity

    @staticmethod
    def _currency(fields: dict[str, SilverExtraction]) -> str | None:
        row = fields.get("limit_currency")
        if row is not None:
            return row.effective_value
        # Fall back to the currency column carried on the limit_value row itself.
        value_row = fields.get("limit_value")
        return value_row.currency if value_row and value_row.currency else None

    @staticmethod
    def _opt(fields: dict[str, SilverExtraction], name: str) -> str | None:
        row = fields.get(name)
        return row.effective_value if row else None

    @classmethod
    def _opt_date(cls, fields: dict[str, SilverExtraction], name: str) -> date | None:
        value = cls._opt(fields, name)
        return date.fromisoformat(value) if value else None
