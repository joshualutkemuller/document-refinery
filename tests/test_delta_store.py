from __future__ import annotations

from datetime import UTC, date, datetime
from pathlib import Path

import pytest

pytest.importorskip("deltalake")
pytest.importorskip("pyarrow")

from deltalake import DeltaTable  # noqa: E402

from document_refinery.application.pipeline import RefineryPipeline  # noqa: E402
from document_refinery.domain.models import GoldEligibilityTerm, MarginType  # noqa: E402
from document_refinery.infrastructure.delta_store import DeltaGoldStore  # noqa: E402
from document_refinery.infrastructure.tasks import TaskStatus  # noqa: E402

TEXT = """Collateral Eligibility Schedule
Eligible Collateral
Counterparty: Atlas Bank
Agreement ID: AGR-001
Schedule Version: 2026-01
Margin Type: VM
Valid From: 2026-01-01
""" + (
    "Asset: GOVT_US | Eligible: yes | Haircut: 2% | Concentration Limit: 100% "
    "| Concentration Basis: market value | Currencies: USD, EUR | Rating Floor: AA- "
    "| Tenor Cap Days: 3650\n"
)


def _gold(**overrides: object) -> GoldEligibilityTerm:
    values: dict[str, object] = {
        "counterparty": "Atlas Bank",
        "agreement_id": "AGR-001",
        "schedule_version": "2026-01",
        "margin_type": MarginType.VM,
        "asset_criterion": "GOVT_US",
        "eligible": True,
        "haircut_pct": 2.0,
        "concentration_limit_pct": 100.0,
        "concentration_basis": "market value",
        "currency_scope": ("USD", "EUR"),
        "rating_floor": "AA-",
        "tenor_cap_days": 3650,
        "valid_from": date(2026, 1, 1),
        "valid_to": None,
        "knowledge_from": datetime(2026, 7, 1, tzinfo=UTC),
        "knowledge_to": None,
        "silver_extraction_ids": ("ext-a", "ext-b"),
        "doc_id": "doc-1",
    }
    values.update(overrides)
    return GoldEligibilityTerm(**values)  # type: ignore[arg-type]


def test_delta_gold_store_round_trips_real_table(tmp_path: Path) -> None:
    uri = str(tmp_path / "gold.delta")
    store = DeltaGoldStore(uri)
    store.upsert((_gold(),))

    table = DeltaTable(uri)
    assert (tmp_path / "gold.delta" / "_delta_log").is_dir()
    rows = table.to_pyarrow_table().to_pylist()
    assert len(rows) == 1
    row = rows[0]
    assert row["counterparty"] == "Atlas Bank"
    assert row["margin_type"] == "VM"
    assert row["currency_scope"] == ["USD", "EUR"]  # array preserved
    assert row["silver_extraction_ids"] == ["ext-a", "ext-b"]  # lineage preserved
    assert row["valid_from"] == date(2026, 1, 1)  # bitemporal date
    assert row["knowledge_to"] is None  # open interval


def test_delta_upsert_creates_new_versions(tmp_path: Path) -> None:
    uri = str(tmp_path / "gold.delta")
    store = DeltaGoldStore(uri)
    store.upsert((_gold(asset_criterion="GOVT_US"),))
    store.upsert((_gold(asset_criterion="GOVT_EU"),))
    # A second write is a new Delta version (time travel / audit via _delta_log).
    assert DeltaTable(uri).version() == 1
    assert len(DeltaTable(uri).to_pyarrow_table().to_pylist()) == 2


def test_delta_reload_closes_prior_knowledge_interval(tmp_path: Path) -> None:
    uri = str(tmp_path / "gold.delta")
    DeltaGoldStore(uri).upsert((_gold(knowledge_from=datetime(2026, 7, 1, tzinfo=UTC)),))

    # A fresh store instance (new process) reloads history from the Delta table,
    # so a later knowledge version supersedes and closes the prior one.
    reopened = DeltaGoldStore(uri)
    reopened.upsert((_gold(knowledge_from=datetime(2026, 7, 5, tzinfo=UTC), haircut_pct=1.5),))

    rows = DeltaTable(uri).to_pyarrow_table().to_pylist()
    assert len(rows) == 2
    closed = [r for r in rows if r["knowledge_to"] is not None]
    open_rows = [r for r in rows if r["knowledge_to"] is None]
    assert len(closed) == 1 and len(open_rows) == 1
    assert closed[0]["haircut_pct"] == 2.0  # the superseded value
    assert open_rows[0]["haircut_pct"] == 1.5  # the current value


def test_pipeline_lands_gold_into_delta(tmp_path: Path) -> None:
    uri = str(tmp_path / "gold.delta")
    source = tmp_path / "schedule.txt"
    source.write_text(TEXT, encoding="utf-8")
    pipeline = RefineryPipeline(tmp_path / "ws", gold_store=DeltaGoldStore(uri))
    try:
        result = pipeline.run(source, source="test", approved_by="Joshua")
        assert result.gold_rows
        assert pipeline.tasks.get(result.document.doc_id).status is TaskStatus.GOLD_LANDED
    finally:
        pipeline.close()
    landed = DeltaTable(uri).to_pyarrow_table().to_pylist()
    assert landed
    assert landed[0]["silver_extraction_ids"]  # lineage present in Delta
