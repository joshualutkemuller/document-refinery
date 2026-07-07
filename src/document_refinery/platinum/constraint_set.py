"""Optimizer constraint-set join (platinum preview).

Composes the gold layers a collateral optimizer's solver consumes into one
per-``(counterparty, agreement)`` view: the eligible-asset rules (from
``gold_eligibility_terms``), the portfolio limits (from ``gold_collateral_limits``),
and the margin *demand* (from ``gold_margin_requirements``).

This is a **read-only preview** of a Phase-2/3 platinum feature view (handoff
§4.4): a pure join over gold records, no storage, no gold writes, not wired into
the production flow. It must wait on the N1–N5 gates before it drives anything.
"""

from __future__ import annotations

from dataclasses import dataclass

from document_refinery.domain.models import (
    GoldCollateralLimit,
    GoldEligibilityTerm,
    GoldMarginRequirement,
)

_Key = tuple[str | None, str | None]


@dataclass(frozen=True, slots=True)
class CollateralConstraintSet:
    """Everything a solver needs to allocate collateral for one agreement."""

    counterparty: str | None
    agreement_id: str | None
    eligible_assets: tuple[GoldEligibilityTerm, ...] = ()
    limits: tuple[GoldCollateralLimit, ...] = ()
    margin_requirements: tuple[GoldMarginRequirement, ...] = ()


def _limit_applies(limit: GoldCollateralLimit, key: _Key) -> bool:
    counterparty, agreement_id = key
    # A schedule-wide limit (no counterparty/agreement) applies to every set; a
    # scoped limit applies only where its stated counterparty/agreement matches.
    return (limit.counterparty is None or limit.counterparty == counterparty) and (
        limit.agreement_id is None or limit.agreement_id == agreement_id
    )


def _margin_applies(requirement: GoldMarginRequirement, key: _Key) -> bool:
    counterparty, agreement_id = key
    return requirement.counterparty == counterparty and (
        requirement.agreement_id is None or requirement.agreement_id == agreement_id
    )


def build_constraint_sets(
    eligibility: tuple[GoldEligibilityTerm, ...],
    limits: tuple[GoldCollateralLimit, ...] = (),
    margin_requirements: tuple[GoldMarginRequirement, ...] = (),
    *,
    active_only: bool = True,
) -> tuple[CollateralConstraintSet, ...]:
    """Join gold eligibility, limits, and margin demand into per-agreement sets.

    ``active_only`` keeps only the currently-known bitemporal version of each
    record (``knowledge_to is None``); pass ``False`` to include superseded
    knowledge versions. Sets are keyed by ``(counterparty, agreement_id)``; a
    limit with no counterparty is treated as schedule-wide and attached to every
    set. If only schedule-wide limits exist (no eligibility or margin context), a
    single unscoped ``(None, None)`` set is returned.
    """
    terms: list[GoldEligibilityTerm] = (
        [t for t in eligibility if t.knowledge_to is None] if active_only else list(eligibility)
    )
    limit_rows: list[GoldCollateralLimit] = (
        [limit for limit in limits if limit.knowledge_to is None]
        if active_only
        else list(limits)
    )
    margin_rows: list[GoldMarginRequirement] = (
        [m for m in margin_requirements if m.knowledge_to is None]
        if active_only
        else list(margin_requirements)
    )

    keys: set[_Key] = {(term.counterparty, term.agreement_id) for term in terms}
    keys.update(
        (limit.counterparty, limit.agreement_id)
        for limit in limit_rows
        if limit.counterparty is not None
    )
    keys.update((m.counterparty, m.agreement_id) for m in margin_rows)
    if not keys and limit_rows:
        keys.add((None, None))

    sets: list[CollateralConstraintSet] = []
    for key in sorted(keys, key=lambda k: (k[0] or "", k[1] or "")):
        counterparty, agreement_id = key
        sets.append(
            CollateralConstraintSet(
                counterparty=counterparty,
                agreement_id=agreement_id,
                eligible_assets=tuple(
                    term
                    for term in terms
                    if (term.counterparty, term.agreement_id) == key
                ),
                limits=tuple(
                    limit for limit in limit_rows if _limit_applies(limit, key)
                ),
                margin_requirements=tuple(
                    m for m in margin_rows if _margin_applies(m, key)
                ),
            )
        )
    return tuple(sets)
