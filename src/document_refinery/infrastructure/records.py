"""Persistent JSONL silver and gold adapters for a local vertical slice."""

from __future__ import annotations

import json
from dataclasses import asdict
from datetime import date, datetime
from enum import Enum
from pathlib import Path
from typing import cast

from document_refinery.application.promotion import (
    InMemoryBitemporalHistory,
    InMemoryLimitHistory,
)
from document_refinery.domain.models import (
    GoldCollateralLimit,
    GoldEligibilityTerm,
    LimitUnit,
    MarginType,
    SilverExtraction,
    ValidatorStatus,
    ValueType,
)


class SilverStore:
    def __init__(self, root: Path) -> None:
        self.root = root
        self.root.mkdir(parents=True, exist_ok=True)

    def write(self, rows: tuple[SilverExtraction, ...], *, stage: str) -> Path:
        if not rows:
            raise ValueError("cannot persist empty silver extraction")
        path = self.root / f"{rows[0].doc_id}.{stage}.jsonl"
        content = "\n".join(json.dumps(_json_safe(asdict(row)), sort_keys=True) for row in rows)
        path.write_text(content + "\n", encoding="utf-8")
        return path

    def read(self, doc_id: str, *, stage: str) -> tuple[SilverExtraction, ...]:
        path = self.root / f"{doc_id}.{stage}.jsonl"
        if not path.exists():
            raise FileNotFoundError(path)
        return tuple(
            _silver_from_json(json.loads(line))
            for line in path.read_text(encoding="utf-8").splitlines()
            if line.strip()
        )


class GoldStore:
    def __init__(self, path: Path) -> None:
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.history = InMemoryBitemporalHistory()
        if self.path.exists():
            for line in self.path.read_text(encoding="utf-8").splitlines():
                if line.strip():
                    self.history.upsert(_gold_from_json(json.loads(line)))

    def upsert(self, records: tuple[GoldEligibilityTerm, ...]) -> Path:
        for record in records:
            self.history.upsert(record)
        content = "\n".join(
            json.dumps(_json_safe(asdict(record)), sort_keys=True)
            for record in self.history.records
        )
        self.path.write_text(content + "\n", encoding="utf-8")
        return self.path


class GoldLimitStore:
    """JSONL gold store for collateral portfolio limits (parallel to GoldStore)."""

    def __init__(self, path: Path) -> None:
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.history = InMemoryLimitHistory()
        if self.path.exists():
            for line in self.path.read_text(encoding="utf-8").splitlines():
                if line.strip():
                    self.history.upsert(_limit_from_json(json.loads(line)))

    def upsert(self, records: tuple[GoldCollateralLimit, ...]) -> Path:
        for record in records:
            self.history.upsert(record)
        content = "\n".join(
            json.dumps(_json_safe(asdict(record)), sort_keys=True)
            for record in self.history.records
        )
        self.path.write_text(content + "\n", encoding="utf-8")
        return self.path


def _limit_from_json(payload: dict[str, object]) -> GoldCollateralLimit:
    payload["limit_unit"] = LimitUnit(str(payload["limit_unit"]))
    payload["silver_extraction_ids"] = tuple(
        cast(list[str], payload["silver_extraction_ids"])
    )
    for date_field in ("valid_from", "valid_to"):
        if payload.get(date_field):
            payload[date_field] = date.fromisoformat(str(payload[date_field]))
    if payload.get("knowledge_from"):
        payload["knowledge_from"] = datetime.fromisoformat(str(payload["knowledge_from"]))
    if payload.get("knowledge_to"):
        payload["knowledge_to"] = datetime.fromisoformat(str(payload["knowledge_to"]))
    return GoldCollateralLimit(**payload)  # type: ignore[arg-type]


def _json_safe(value: object) -> object:
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, list | tuple):
        return [_json_safe(item) for item in value]
    if isinstance(value, datetime | date):
        return value.isoformat()
    if isinstance(value, Enum):
        return value.value
    return value


def _gold_from_json(payload: dict[str, object]) -> GoldEligibilityTerm:
    payload["margin_type"] = MarginType(str(payload["margin_type"]))
    payload["currency_scope"] = tuple(cast(list[str], payload["currency_scope"]))
    payload["silver_extraction_ids"] = tuple(
        cast(list[str], payload["silver_extraction_ids"])
    )
    payload["valid_from"] = date.fromisoformat(str(payload["valid_from"]))
    if payload.get("valid_to"):
        payload["valid_to"] = date.fromisoformat(str(payload["valid_to"]))
    if payload.get("knowledge_from"):
        payload["knowledge_from"] = datetime.fromisoformat(str(payload["knowledge_from"]))
    if payload.get("knowledge_to"):
        payload["knowledge_to"] = datetime.fromisoformat(str(payload["knowledge_to"]))
    return GoldEligibilityTerm(**payload)  # type: ignore[arg-type]


def _silver_from_json(payload: dict[str, object]) -> SilverExtraction:
    payload["value_type"] = ValueType(str(payload["value_type"]))
    payload["validator_status"] = ValidatorStatus(str(payload["validator_status"]))
    if payload.get("created_at"):
        payload["created_at"] = datetime.fromisoformat(str(payload["created_at"]))
    return SilverExtraction(**payload)  # type: ignore[arg-type]
