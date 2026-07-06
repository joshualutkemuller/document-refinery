"""Phase 1 eligibility extractor and independent adversarial validator."""

from __future__ import annotations

import hashlib
import re
from dataclasses import replace
from datetime import UTC, datetime

from document_refinery.domain.models import (
    SilverExtraction,
    ValidatorStatus,
    ValueType,
)

_HEADER_TYPES = {
    "counterparty": ValueType.STRING,
    "agreement_id": ValueType.STRING,
    "schedule_version": ValueType.STRING,
    "margin_type": ValueType.STRING,
    "valid_from": ValueType.DATE,
    "valid_to": ValueType.DATE,
}

_ITEM_TYPES = {
    "asset_criterion": ValueType.STRING,
    "eligible": ValueType.BOOLEAN,
    "haircut_pct": ValueType.PERCENTAGE,
    "concentration_limit_pct": ValueType.PERCENTAGE,
    "concentration_basis": ValueType.STRING,
    "currency_scope": ValueType.STRING_ARRAY,
    "rating_floor": ValueType.STRING,
    "tenor_cap_days": ValueType.INTEGER,
}

_HEADER_LABELS = {
    "counterparty": "Counterparty",
    "agreement_id": "Agreement ID",
    "schedule_version": "Schedule Version",
    "margin_type": "Margin Type",
    "valid_from": "Valid From",
    "valid_to": "Valid To",
}

_ITEM_LABELS = {
    "asset_criterion": "Asset",
    "eligible": "Eligible",
    "haircut_pct": "Haircut",
    "concentration_limit_pct": "Concentration Limit",
    "concentration_basis": "Concentration Basis",
    "currency_scope": "Currencies",
    "rating_floor": "Rating Floor",
    "tenor_cap_days": "Tenor Cap Days",
}


class EligibilityScheduleExtractor:
    """Deterministic reference extractor that emits silver rows only."""

    DOC_CLASS = "collateral_eligibility_schedule"

    def __init__(
        self,
        *,
        extractor_version: str = "rules-1.0.0",
        constitution_version: str = "eligibility-1.0.0",
    ) -> None:
        self.extractor_version = extractor_version
        self.constitution_version = constitution_version

    def extract(self, *, doc_id: str, text: str) -> tuple[SilverExtraction, ...]:
        located_lines = [
            (line_number, line.strip())
            for line_number, line in enumerate(text.splitlines(), start=1)
            if line.strip()
        ]
        headers = self._extract_headers(located_lines)
        item_lines = [
            (line_number, line)
            for line_number, line in located_lines
            if line.casefold().startswith("asset:")
        ]
        if not item_lines:
            raise ValueError("no eligibility rows found")

        output: list[SilverExtraction] = []
        for item_index, (line_number, line) in enumerate(item_lines):
            item = _split_labeled_line(line)
            for field, value_type in _HEADER_TYPES.items():
                output.append(
                    self._row(
                        doc_id=doc_id,
                        field_path=f"eligibility[{item_index}].{field}",
                        raw_value=headers.get(field, ("", "[FIELD NOT FOUND]", 1))[0],
                        source_clause=headers.get(field, ("", "[FIELD NOT FOUND]", 1))[1],
                        line_number=headers.get(field, ("", "[FIELD NOT FOUND]", 1))[2],
                        value_type=value_type,
                    )
                )
            for field, value_type in _ITEM_TYPES.items():
                raw_value = item.get(field, "")
                output.append(
                    self._row(
                        doc_id=doc_id,
                        field_path=f"eligibility[{item_index}].{field}",
                        raw_value=raw_value,
                        source_clause=line if raw_value else "[FIELD NOT FOUND]",
                        line_number=line_number,
                        value_type=value_type,
                    )
                )
        return tuple(output)

    def _extract_headers(
        self, located_lines: list[tuple[int, str]]
    ) -> dict[str, tuple[str, str, int]]:
        headers: dict[str, tuple[str, str, int]] = {}
        labels = {label.casefold(): field for field, label in _HEADER_LABELS.items()}
        for line_number, line in located_lines:
            if ":" not in line:
                continue
            label, value = line.split(":", 1)
            field = labels.get(label.strip().casefold())
            if field:
                headers[field] = (value.strip(), line, line_number)
        return headers

    def _row(
        self,
        *,
        doc_id: str,
        field_path: str,
        raw_value: str,
        source_clause: str,
        line_number: int,
        value_type: ValueType,
    ) -> SilverExtraction:
        missing = not raw_value.strip()
        normalized = "not_found" if missing else _normalize(field_path, raw_value)
        resolved_type = ValueType.NOT_FOUND if missing else value_type
        extraction_id = hashlib.sha256(
            f"{doc_id}|{field_path}|{self.extractor_version}".encode()
        ).hexdigest()[:32]
        return SilverExtraction(
            extraction_id=extraction_id,
            doc_id=doc_id,
            doc_class=self.DOC_CLASS,
            extractor_version=self.extractor_version,
            constitution_version=self.constitution_version,
            field_path=field_path,
            raw_value=raw_value,
            normalized_value=normalized,
            value_type=resolved_type,
            source_clause=source_clause,
            source_locator=f"page=1;line={line_number}",
            confidence=0.0 if missing else 0.99,
            ambiguity_flag=False,
            validator_status=ValidatorStatus.PENDING,
            unit="percent" if value_type is ValueType.PERCENTAGE and not missing else None,
            created_at=datetime.now(UTC),
        )


class EligibilityAdversarialValidator:
    """Independently parses source text and compares each silver value."""

    def validate(
        self,
        *,
        text: str,
        extractions: tuple[SilverExtraction, ...],
    ) -> tuple[SilverExtraction, ...]:
        independently_derived = _independent_derivation(text)
        validated: list[SilverExtraction] = []
        for row in extractions:
            index_match = re.search(r"eligibility\[(\d+)]\.(.+)$", row.field_path)
            if not index_match:
                validated.append(replace(row, validator_status=ValidatorStatus.DISPUTED))
                continue
            key = (int(index_match.group(1)), index_match.group(2))
            expected = independently_derived.get(key, "not_found")
            consistent = _passes_consistency_rule(key[1], row.effective_value)
            status = (
                ValidatorStatus.CONFIRMED
                if expected == row.normalized_value and consistent and not row.ambiguity_flag
                else ValidatorStatus.DISPUTED
            )
            validated.append(replace(row, validator_status=status))
        return tuple(validated)


def _split_labeled_line(line: str) -> dict[str, str]:
    labels = {label.casefold(): field for field, label in _ITEM_LABELS.items()}
    values: dict[str, str] = {}
    for section in line.split("|"):
        if ":" not in section:
            continue
        label, value = section.split(":", 1)
        field = labels.get(label.strip().casefold())
        if field:
            values[field] = value.strip()
    return values


def _normalize(field_path: str, raw_value: str) -> str:
    field = field_path.rsplit(".", 1)[-1]
    value = raw_value.strip()
    if field == "eligible":
        lowered = value.casefold()
        if lowered in {"yes", "true", "eligible"}:
            return "true"
        if lowered in {"no", "false", "ineligible"}:
            return "false"
    if field in {"haircut_pct", "concentration_limit_pct"}:
        return value.removesuffix("%").strip()
    if field == "currency_scope":
        return ",".join(part.strip().upper() for part in value.split(",") if part.strip())
    if field == "margin_type":
        aliases = {"vm": "VM", "im": "IM", "repo": "Repo"}
        return aliases.get(value.casefold(), value)
    return value


def _independent_derivation(text: str) -> dict[tuple[int, str], str]:
    """Validator parser intentionally does not call extractor parsing helpers."""
    header_patterns = {
        field: re.compile(rf"(?im)^{re.escape(label)}\s*:\s*(.+?)\s*$")
        for field, label in _HEADER_LABELS.items()
    }
    headers = {
        field: (match.group(1).strip() if (match := pattern.search(text)) else "not_found")
        for field, pattern in header_patterns.items()
    }
    item_pattern = re.compile(r"(?im)^Asset\s*:\s*(.+?)\s*$")
    output: dict[tuple[int, str], str] = {}
    for index, match in enumerate(item_pattern.finditer(text)):
        whole_line = match.group(0)
        segments: dict[str, str] = {}
        for segment in whole_line.split("|"):
            pieces = segment.split(":", 1)
            if len(pieces) == 2:
                segments[pieces[0].strip().casefold()] = pieces[1].strip()
        for field, label in _ITEM_LABELS.items():
            raw = segments.get(label.casefold())
            output[(index, field)] = (
                _normalize(f"eligibility[{index}].{field}", raw) if raw else "not_found"
            )
        for field, value in headers.items():
            output[(index, field)] = (
                _normalize(f"eligibility[{index}].{field}", value)
                if value != "not_found"
                else value
            )
    return output


def _passes_consistency_rule(field: str, value: str) -> bool:
    if value == "not_found":
        return True
    if field in {"haircut_pct", "concentration_limit_pct"}:
        try:
            return 0.0 <= float(value) <= 100.0
        except ValueError:
            return False
    if field == "tenor_cap_days":
        try:
            return int(value) >= 0
        except ValueError:
            return False
    return True
