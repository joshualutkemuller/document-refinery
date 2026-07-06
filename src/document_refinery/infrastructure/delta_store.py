"""Production gold storage on Delta Lake (delta-rs, no Spark required).

Writes real, versioned Delta tables for ``gold_eligibility_terms`` — the same
bitemporal records the JSONL adapter produces, but in a format Databricks / Spark
/ DuckDB / Polars can query directly. The table URI can be a local path or a
cloud object store (``s3://``, ``az://``, ``gs://``); credentials/region are
passed through ``storage_options`` (typically from environment), never persisted.

``deltalake`` and ``pyarrow`` are an optional extra: ``pip install
document-refinery[delta]``. They are imported lazily so the core stays
dependency-light and the JSONL adapter remains the zero-dependency default.

Bitemporal closure reuses the domain ``InMemoryBitemporalHistory`` so semantics
match the JSONL adapter exactly; each ``upsert`` rewrites the current snapshot as
a new Delta version (time-travel + audit come for free from the ``_delta_log``).
"""

from __future__ import annotations

from datetime import date, datetime
from typing import TYPE_CHECKING, Any

from document_refinery.application.promotion import InMemoryBitemporalHistory
from document_refinery.domain.models import GoldEligibilityTerm, MarginType

if TYPE_CHECKING:
    import pyarrow as pa


def _gold_schema() -> pa.Schema:
    import pyarrow as pa

    return pa.schema(
        [
            ("counterparty", pa.string()),
            ("agreement_id", pa.string()),
            ("schedule_version", pa.string()),
            ("margin_type", pa.string()),
            ("asset_criterion", pa.string()),
            ("eligible", pa.bool_()),
            ("haircut_pct", pa.float64()),
            ("concentration_limit_pct", pa.float64()),
            ("concentration_basis", pa.string()),
            ("currency_scope", pa.list_(pa.string())),
            ("rating_floor", pa.string()),
            ("tenor_cap_days", pa.int64()),
            ("valid_from", pa.date32()),
            ("valid_to", pa.date32()),
            ("knowledge_from", pa.timestamp("us", tz="UTC")),
            ("knowledge_to", pa.timestamp("us", tz="UTC")),
            ("silver_extraction_ids", pa.list_(pa.string())),
            ("doc_id", pa.string()),
        ]
    )


class DeltaGoldStore:
    """Delta Lake adapter for gold eligibility terms."""

    def __init__(
        self,
        table_uri: str,
        *,
        storage_options: dict[str, str] | None = None,
    ) -> None:
        self.table_uri = table_uri
        self.storage_options = storage_options
        self.history = InMemoryBitemporalHistory()
        for record in self._load_existing():
            self.history.upsert(record)

    def upsert(self, records: tuple[GoldEligibilityTerm, ...]) -> str:
        from deltalake import write_deltalake

        for record in records:
            self.history.upsert(record)
        table = self._arrow_table(self.history.records)
        write_deltalake(
            self.table_uri,
            table,
            mode="overwrite",
            schema_mode="overwrite",
            storage_options=self.storage_options,
        )
        return self.table_uri

    def _load_existing(self) -> tuple[GoldEligibilityTerm, ...]:
        from deltalake import DeltaTable
        from deltalake.exceptions import TableNotFoundError

        try:
            table = DeltaTable(self.table_uri, storage_options=self.storage_options)
        except TableNotFoundError:
            return ()
        rows = table.to_pyarrow_table().to_pylist()
        return tuple(_gold_from_row(row) for row in rows)

    def _arrow_table(self, records: tuple[GoldEligibilityTerm, ...]) -> pa.Table:
        import pyarrow as pa

        rows = [_gold_to_row(record) for record in records]
        return pa.Table.from_pylist(rows, schema=_gold_schema())


def _gold_to_row(record: GoldEligibilityTerm) -> dict[str, Any]:
    return {
        "counterparty": record.counterparty,
        "agreement_id": record.agreement_id,
        "schedule_version": record.schedule_version,
        "margin_type": record.margin_type.value,
        "asset_criterion": record.asset_criterion,
        "eligible": record.eligible,
        "haircut_pct": record.haircut_pct,
        "concentration_limit_pct": record.concentration_limit_pct,
        "concentration_basis": record.concentration_basis,
        "currency_scope": list(record.currency_scope),
        "rating_floor": record.rating_floor,
        "tenor_cap_days": record.tenor_cap_days,
        "valid_from": record.valid_from,
        "valid_to": record.valid_to,
        "knowledge_from": record.knowledge_from,
        "knowledge_to": record.knowledge_to,
        "silver_extraction_ids": list(record.silver_extraction_ids),
        "doc_id": record.doc_id,
    }


def _gold_from_row(row: dict[str, Any]) -> GoldEligibilityTerm:
    return GoldEligibilityTerm(
        counterparty=row["counterparty"],
        agreement_id=row["agreement_id"],
        schedule_version=row["schedule_version"],
        margin_type=MarginType(row["margin_type"]),
        asset_criterion=row["asset_criterion"],
        eligible=row["eligible"],
        haircut_pct=row["haircut_pct"],
        concentration_limit_pct=row["concentration_limit_pct"],
        concentration_basis=row["concentration_basis"],
        currency_scope=tuple(row["currency_scope"] or ()),
        rating_floor=row["rating_floor"],
        tenor_cap_days=row["tenor_cap_days"],
        valid_from=_require_date(row["valid_from"]),
        valid_to=_as_date(row["valid_to"]),
        knowledge_from=_require_datetime(row["knowledge_from"]),
        knowledge_to=_as_datetime(row["knowledge_to"]),
        silver_extraction_ids=tuple(row["silver_extraction_ids"] or ()),
        doc_id=row["doc_id"],
    )


def _as_date(value: object) -> date | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    return date.fromisoformat(str(value))


def _as_datetime(value: object) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value
    return datetime.fromisoformat(str(value))


def _require_date(value: object) -> date:
    result = _as_date(value)
    if result is None:
        raise ValueError("valid_from is required in a gold record")
    return result


def _require_datetime(value: object) -> datetime:
    result = _as_datetime(value)
    if result is None:
        raise ValueError("knowledge_from is required in a gold record")
    return result
