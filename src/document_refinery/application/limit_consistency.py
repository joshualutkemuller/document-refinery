"""Deterministic consistency rules for collateral portfolio limits (§5.3).

The adversarial-validator counterpart to the ``gold_collateral_limits`` promotion
guardrails, run on ``limit[i].*`` silver rows *before* Gate A so silently-wrong
limits surface as violations rather than landing. Class-specific consistency
checks (handoff §5.3): percent caps in range with a basis, absolute caps with a
currency, and a value-scoped cap never looser than the blanket cap for the same
dimension (e.g. a "Technology sector 10%" cap under a blanket "sector 5%" cap is
contradictory).

Pure and deterministic: it reports violations; it does not mutate silver, write
gold, or call a model.
"""

from __future__ import annotations

import re
from collections.abc import Iterable
from dataclasses import dataclass

from document_refinery.domain.models import SilverExtraction, ValueType

_LIMIT_INDEX = re.compile(r"^limit\[(\d+)\]\.(.+)$")


@dataclass(frozen=True, slots=True)
class LimitConsistencyViolation:
    code: str
    message: str
    limit_index: int | None = None
    dimension: str | None = None


class LimitConsistencyError(ValueError):
    """Raised by :meth:`LimitConsistencyValidator.assert_consistent`."""


class LimitConsistencyValidator:
    """Class-specific consistency rules for ``limit[i]`` groups."""

    def check(
        self, extractions: Iterable[SilverExtraction]
    ) -> tuple[LimitConsistencyViolation, ...]:
        groups = _group_limits(tuple(extractions))
        violations: list[LimitConsistencyViolation] = []
        # (dimension -> smallest blanket percent cap) for the scoped-vs-blanket rule.
        blanket_percent: dict[str, float] = {}
        scoped_percent: list[tuple[int, str, str | None, float]] = []

        for index in sorted(groups):
            fields = groups[index]
            dimension = _value(fields, "dimension")
            unit = (_value(fields, "limit_unit") or "").strip().casefold()
            value = _number(fields, "limit_value")
            scope = _value(fields, "scope_value")

            if unit and unit not in {"percent", "absolute"}:
                violations.append(
                    LimitConsistencyViolation(
                        "invalid_unit", f"limit_unit '{unit}' is not percent or absolute",
                        index, dimension,
                    )
                )
            if unit == "percent":
                if _value(fields, "basis") is None:
                    violations.append(
                        LimitConsistencyViolation(
                            "missing_basis",
                            "percent limit needs a basis (market vs post-haircut value)",
                            index, dimension,
                        )
                    )
                if value is not None and not 0.0 <= value <= 100.0:
                    violations.append(
                        LimitConsistencyViolation(
                            "percent_out_of_range", f"percent limit {value} not in [0, 100]",
                            index, dimension,
                        )
                    )
                if dimension and value is not None:
                    if scope is None:
                        blanket_percent[dimension] = min(
                            value, blanket_percent.get(dimension, value)
                        )
                    else:
                        scoped_percent.append((index, dimension, scope, value))
            elif unit == "absolute":
                if not (_value(fields, "limit_currency") or _currency(fields)):
                    violations.append(
                        LimitConsistencyViolation(
                            "missing_currency", "absolute limit needs a currency",
                            index, dimension,
                        )
                    )
                if value is not None and value < 0.0:
                    violations.append(
                        LimitConsistencyViolation(
                            "negative_absolute", f"absolute limit {value} is negative",
                            index, dimension,
                        )
                    )

        for index, dimension, scope, value in scoped_percent:
            blanket = blanket_percent.get(dimension)
            if blanket is not None and value > blanket:
                violations.append(
                    LimitConsistencyViolation(
                        "scoped_exceeds_blanket",
                        f"{dimension} '{scope}' cap {value}% exceeds the blanket "
                        f"{dimension} cap {blanket}%",
                        index, dimension,
                    )
                )
        return tuple(violations)

    def assert_consistent(self, extractions: Iterable[SilverExtraction]) -> None:
        violations = self.check(extractions)
        if violations:
            raise LimitConsistencyError(
                "; ".join(f"[{v.code}] {v.message}" for v in violations)
            )


def _group_limits(
    rows: tuple[SilverExtraction, ...],
) -> dict[int, dict[str, SilverExtraction]]:
    groups: dict[int, dict[str, SilverExtraction]] = {}
    for row in rows:
        if row.value_type is ValueType.NOT_FOUND:
            continue
        match = _LIMIT_INDEX.match(row.field_path)
        if match is None:
            continue
        groups.setdefault(int(match.group(1)), {})[match.group(2)] = row
    return groups


def _value(fields: dict[str, SilverExtraction], name: str) -> str | None:
    row = fields.get(name)
    return row.effective_value if row else None


def _currency(fields: dict[str, SilverExtraction]) -> str | None:
    row = fields.get("limit_value")
    return row.currency if row and row.currency else None


def _number(fields: dict[str, SilverExtraction], name: str) -> float | None:
    value = _value(fields, name)
    if value is None:
        return None
    try:
        return float(value)
    except ValueError:
        return None
