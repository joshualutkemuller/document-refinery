from __future__ import annotations

from datetime import UTC, date, datetime

from document_refinery.domain.models import (
    GoldCollateralLimit,
    GoldEligibilityTerm,
    LimitUnit,
    MarginType,
)
from document_refinery.platinum.constraint_set import build_constraint_sets

_K1 = datetime(2026, 1, 1, tzinfo=UTC)
_K2 = datetime(2026, 6, 1, tzinfo=UTC)


def _term(
    counterparty: str,
    agreement_id: str,
    asset: str,
    *,
    knowledge_to: datetime | None = None,
) -> GoldEligibilityTerm:
    return GoldEligibilityTerm(
        counterparty=counterparty,
        agreement_id=agreement_id,
        schedule_version="2026-01",
        margin_type=MarginType.VM,
        asset_criterion=asset,
        eligible=True,
        haircut_pct=2.0,
        concentration_limit_pct=None,
        concentration_basis=None,
        currency_scope=("USD",),
        rating_floor=None,
        tenor_cap_days=None,
        valid_from=date(2026, 1, 1),
        valid_to=None,
        knowledge_from=_K1,
        knowledge_to=knowledge_to,
        silver_extraction_ids=("e1",),
        doc_id="doc-1",
    )


def _limit(
    *,
    counterparty: str | None,
    agreement_id: str | None,
    dimension: str,
    value: float,
    knowledge_to: datetime | None = None,
) -> GoldCollateralLimit:
    return GoldCollateralLimit(
        dimension=dimension,
        scope_value=None,
        limit_value=value,
        limit_unit=LimitUnit.PERCENT,
        limit_currency=None,
        basis="market_value",
        aggregation="posted_collateral",
        counterparty=counterparty,
        agreement_id=agreement_id,
        schedule_version="2026-01",
        clearing_house=None,
        valid_from=date(2026, 1, 1),
        valid_to=None,
        knowledge_from=_K1,
        knowledge_to=knowledge_to,
        silver_extraction_ids=("l1",),
        doc_id="doc-1",
    )


def test_join_groups_eligibility_and_limits_by_agreement() -> None:
    eligibility = (
        _term("Atlas Bank", "AGR-1", "GOVT_US"),
        _term("Atlas Bank", "AGR-1", "AGENCY"),
        _term("Beacon Bank", "AGR-2", "GOVT_US"),
    )
    limits = (
        _limit(counterparty="Atlas Bank", agreement_id="AGR-1", dimension="sector", value=10),
    )
    sets = build_constraint_sets(eligibility, limits)
    assert [(s.counterparty, s.agreement_id) for s in sets] == [
        ("Atlas Bank", "AGR-1"),
        ("Beacon Bank", "AGR-2"),
    ]
    atlas = sets[0]
    assert len(atlas.eligible_assets) == 2
    assert len(atlas.limits) == 1
    assert sets[1].limits == ()  # Beacon has no matching limit


def test_schedule_wide_limit_attaches_to_every_set() -> None:
    eligibility = (
        _term("Atlas Bank", "AGR-1", "GOVT_US"),
        _term("Beacon Bank", "AGR-2", "GOVT_US"),
    )
    limits = (
        _limit(counterparty=None, agreement_id=None, dimension="country", value=20),
    )
    sets = build_constraint_sets(eligibility, limits)
    assert all(len(s.limits) == 1 for s in sets)


def test_active_only_filters_superseded_knowledge_versions() -> None:
    eligibility = (
        _term("Atlas Bank", "AGR-1", "GOVT_US", knowledge_to=_K2),  # superseded
        _term("Atlas Bank", "AGR-1", "AGENCY"),  # active
    )
    active = build_constraint_sets(eligibility, ())
    assert len(active[0].eligible_assets) == 1
    everything = build_constraint_sets(eligibility, (), active_only=False)
    assert len(everything[0].eligible_assets) == 2


def test_limits_only_corpus_yields_unscoped_set() -> None:
    limits = (
        _limit(counterparty=None, agreement_id=None, dimension="asset_type", value=30),
    )
    sets = build_constraint_sets((), limits)
    assert len(sets) == 1
    assert sets[0].counterparty is None
    assert sets[0].eligible_assets == ()
    assert len(sets[0].limits) == 1
