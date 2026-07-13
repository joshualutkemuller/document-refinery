from __future__ import annotations

from datetime import UTC, date, datetime
from pathlib import Path

import pytest

pytest.importorskip("deltalake")
pytest.importorskip("pyarrow")

from deltalake import DeltaTable  # noqa: E402

from document_refinery.domain.models import GoldCollateralLimit, LimitUnit  # noqa: E402
from document_refinery.infrastructure.delta_store import DeltaLimitStore  # noqa: E402

_K1 = datetime(2026, 1, 1, tzinfo=UTC)
_K2 = datetime(2026, 6, 1, tzinfo=UTC)


def _limit(
    *,
    limit_value: float,
    limit_unit: LimitUnit,
    limit_currency: str | None,
    knowledge_from: datetime,
) -> GoldCollateralLimit:
    return GoldCollateralLimit(
        dimension="sector",
        scope_value="Technology",
        limit_value=limit_value,
        limit_unit=limit_unit,
        limit_currency=limit_currency,
        basis="post_haircut_value",
        aggregation="posted_collateral",
        counterparty="Atlas Bank",
        agreement_id="AGR-1",
        schedule_version="2026-01",
        clearing_house=None,
        valid_from=date(2026, 1, 1),
        valid_to=None,
        knowledge_from=knowledge_from,
        knowledge_to=None,
        silver_extraction_ids=("l1",),
        doc_id="doc-1",
    )


def test_delta_limit_store_writes_and_reloads(tmp_path: Path) -> None:
    uri = str(tmp_path / "gold_limits.delta")
    store = DeltaLimitStore(uri)
    store.upsert(
        (_limit(limit_value=10.0, limit_unit=LimitUnit.PERCENT,
                limit_currency=None, knowledge_from=_K1),)
    )

    rows = DeltaTable(uri).to_pyarrow_table().to_pylist()
    assert len(rows) == 1
    assert rows[0]["dimension"] == "sector"
    assert rows[0]["limit_value"] == 10.0
    assert rows[0]["limit_unit"] == "percent"

    # A reopened store recovers prior bitemporal state from the Delta table.
    reopened = DeltaLimitStore(uri)
    assert len(reopened.history.records) == 1


def test_delta_limit_store_closes_prior_knowledge_version(tmp_path: Path) -> None:
    uri = str(tmp_path / "gold_limits.delta")
    store = DeltaLimitStore(uri)
    store.upsert(
        (_limit(limit_value=10.0, limit_unit=LimitUnit.PERCENT,
                limit_currency=None, knowledge_from=_K1),)
    )
    store.upsert(
        (_limit(limit_value=8.0, limit_unit=LimitUnit.PERCENT,
                limit_currency=None, knowledge_from=_K2),)
    )
    records = DeltaLimitStore(uri).history.records
    # Same identity: the old version is knowledge-closed, the new one is open.
    assert len(records) == 2
    open_versions = [r for r in records if r.knowledge_to is None]
    assert len(open_versions) == 1
    assert open_versions[0].limit_value == 8.0


def test_delta_limit_store_roundtrips_absolute_currency(tmp_path: Path) -> None:
    uri = str(tmp_path / "gold_limits.delta")
    store = DeltaLimitStore(uri)
    store.upsert(
        (_limit(limit_value=50000000.0, limit_unit=LimitUnit.ABSOLUTE,
                limit_currency="USD", knowledge_from=_K1),)
    )
    (record,) = DeltaLimitStore(uri).history.records
    assert record.limit_unit is LimitUnit.ABSOLUTE
    assert record.limit_currency == "USD"
    assert record.limit_value == 50000000.0
