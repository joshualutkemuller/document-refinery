"""Local, offline semantic model for running the unknown-layout path without a
provider API key or network access.

This is a **heuristic test/demo double**, not a production extractor. It reads the
document text handed to it and emits schema-valid extraction/validation responses
so the full semantic route can be exercised locally: semantic routing, strict
schema conversion to silver, a separate-session validator, and Gate A. It targets
the common "pipe-delimited schedule" layout (``Asset Class: ... | Haircut: ...``)
plus ``Key: Value`` headers, which is what the synthetic corpus fixture uses and
what many real triparty schedules resemble.

Production extraction uses ``OpenAISemanticModel`` under the zero-data-retention
policy; this provider is for local pipeline verification only and makes no
accuracy claim. It never creates system IDs, validation status, or gold — trusted
application code does that from these responses, exactly as with a real model.
"""

from __future__ import annotations

import hashlib
import json
import re
from datetime import UTC, datetime

from document_refinery.agents.semantic import SemanticRequest, SemanticResponse
from document_refinery.domain.models import ValueType

_ASSET_KEY = "asset class"
_HAIRCUT_KEYS = ("valuation haircut", "haircut")
_CONCENTRATION_KEYS = ("concentration cap", "concentration limit")
_RATING_KEYS = ("rating floor",)
_CURRENCY_KEYS = ("currencies", "currency")
_MATURITY_KEYS = ("residual maturity cap", "tenor cap", "maturity cap")
_COUNTERPARTY_KEYS = ("collateral giver", "counterparty", "collateral provider")
_AGREEMENT_KEYS = ("profile reference", "agreement id", "reference")
_VALID_FROM_KEYS = ("effective", "valid from", "effective date")
_NUMBER_RE = re.compile(r"-?\d+(?:\.\d+)?")


class LocalHeuristicSemanticModel:
    """Offline SemanticModel implementation (see module docstring)."""

    def __init__(self, *, model: str = "local-heuristic-v1", session_id: str) -> None:
        self._model = model
        self._session_id = session_id

    @property
    def session_id(self) -> str:
        return self._session_id

    @property
    def provider(self) -> str:
        return "local"

    @property
    def model(self) -> str:
        return self._model

    def generate(self, request: SemanticRequest) -> SemanticResponse:
        payload = json.loads(request.user_payload)
        text = str(payload.get("document_text_untrusted", ""))
        properties = request.response_schema.get("properties", {})
        if isinstance(properties, dict) and "judgments" in properties:
            content = self._validate(text, payload.get("candidate_rows", []))
        else:
            content = self._extract(text)
        body = json.dumps(content, ensure_ascii=False)
        return SemanticResponse(
            content=body,
            provider=self.provider,
            model=self._model,
            response_id=f"local-{hashlib.sha256(body.encode()).hexdigest()[:12]}",
            created_at=datetime.now(UTC),
            latency_ms=0,
            usage={"input_tokens": len(text) // 4, "output_tokens": len(body) // 4},
        )

    # -- extraction -------------------------------------------------------

    def _extract(self, text: str) -> dict[str, object]:
        rows = _extraction_rows(text)
        if not rows:
            raise ValueError(
                "local heuristic found no recognizable schedule structure; "
                "use --semantic-provider openai for arbitrary documents"
            )
        return {"extractions": rows}

    # -- validation -------------------------------------------------------

    def _validate(self, text: str, candidate_rows: list[dict[str, object]]) -> dict[str, object]:
        # Re-derive clauses from the same text so found values get verbatim
        # evidence; missing values are confirmed as not found.
        clause_by_path = {row["field_path"]: row["source_clause"] for row in _extraction_rows(text)}
        judgments: list[dict[str, object]] = []
        for candidate in candidate_rows:
            path = str(candidate.get("field_path", ""))
            normalized = str(candidate.get("normalized_value", ""))
            if normalized == "not_found":
                evidence, locator = "[FIELD NOT FOUND]", "not_found"
            else:
                evidence = str(clause_by_path.get(path) or _first_line(text))
                locator = "revalidated"
            judgments.append(
                {
                    "extraction_id": str(candidate.get("extraction_id", "")),
                    "status": "confirmed",
                    "evidence_clause": evidence,
                    "evidence_locator": locator,
                }
            )
        return {"judgments": judgments}


def _extraction_rows(text: str) -> list[dict[str, object]]:
    if _is_valuation_margin_text(text):
        return _valuation_margin_rows(text)
    lines = text.splitlines()
    header = _header_fields(lines)
    rows: list[dict[str, object]] = []
    asset_index = 0
    for lineno, line in enumerate(lines, start=1):
        kv = _pipe_fields(line)
        if _ASSET_KEY not in kv:
            continue
        rows.extend(_asset_rows(asset_index, line, lineno, kv, header))
        asset_index += 1
    return rows


def _is_valuation_margin_text(text: str) -> bool:
    lowered = text.casefold()
    return (
        "collateral valuation" in lowered
        and "securities valuation and margins table" in lowered
    )


def _valuation_margin_rows(text: str) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    line_pairs = [
        (line.strip(), _collapse_whitespace(line))
        for line in text.splitlines()
        if line.strip()
    ]
    last_updated = _line_containing(line_pairs, "Last Updated:")
    if last_updated:
        normalized_date = _date_from_mdy(last_updated)
        rows.append(
            _row(
                "document.last_updated",
                last_updated.split(":", 1)[-1].strip(),
                normalized_date or last_updated.split(":", 1)[-1].strip(),
                ValueType.DATE if normalized_date else ValueType.STRING,
                last_updated,
                "document=header",
            )
        )
    publisher_clause = _line_containing(line_pairs, "Federal Reserve Bank")
    if publisher_clause:
        rows.append(
            _row(
                "document.publisher",
                "Federal Reserve Bank",
                "Federal Reserve",
                ValueType.STRING,
                publisher_clause,
                "document=header",
            )
        )
    context_clause = _line_containing(line_pairs, "discount window programs")
    if context_clause:
        rows.append(
            _row(
                "document.program_context",
                "discount window programs",
                "Discount Window lending and Payment System Risk",
                ValueType.STRING,
                context_clause,
                "document=header",
            )
        )

    duration_buckets = (("0-1", "0", "1"), (">1-3", "1", "3"), (">3-5", "3", "5"),
                        (">5-10", "5", "10"), (">10", "10", ""))
    row_index = 0
    for original_line, collapsed_line in line_pairs:
        values = re.findall(r"\b\d{2,3}\b", collapsed_line)
        if len(values) < 5:
            continue
        label = re.sub(r"(?:\s+\d{2,3}){5}\s*$", "", collapsed_line)
        label = label.strip()
        if not label or label.casefold().startswith(("duration buckets", "securities margins")):
            continue
        for bucket_index, (bucket, min_years, max_years) in enumerate(duration_buckets):
            collateral_value = values[-5:][bucket_index]
            prefix = f"valuation_margin[{row_index}]"
            implied_haircut = str(100 - int(collateral_value))
            rows.extend(
                (
                    _row(
                        f"{prefix}.asset_category",
                        label,
                        label,
                        ValueType.STRING,
                        original_line,
                        f"line={row_index + 1}",
                    ),
                    _row(
                        f"{prefix}.duration_bucket",
                        bucket,
                        bucket,
                        ValueType.STRING,
                        original_line,
                        f"line={row_index + 1}",
                    ),
                    _row(
                        f"{prefix}.duration_min_years",
                        min_years,
                        min_years,
                        ValueType.INTEGER,
                        original_line,
                        f"line={row_index + 1}",
                    ),
                    _row(
                        f"{prefix}.collateral_value_pct",
                        collateral_value,
                        collateral_value,
                        ValueType.PERCENTAGE,
                        original_line,
                        f"line={row_index + 1}",
                        unit="percent_of_market_value",
                    ),
                    _row(
                        f"{prefix}.implied_haircut_pct",
                        implied_haircut,
                        implied_haircut,
                        ValueType.PERCENTAGE,
                        original_line,
                        f"line={row_index + 1}",
                        unit="percent",
                    ),
                )
            )
            if max_years:
                rows.append(
                    _row(
                        f"{prefix}.duration_max_years",
                        max_years,
                        max_years,
                        ValueType.INTEGER,
                        original_line,
                        f"line={row_index + 1}",
                    )
                )
            row_index += 1
        if row_index >= 20:
            break
    if not rows:
        raise ValueError("local heuristic found no recognizable valuation margin table")
    return rows


def _asset_rows(
    index: int,
    line: str,
    lineno: int,
    kv: dict[str, str],
    header: dict[str, tuple[str, str]],
) -> list[dict[str, object]]:
    prefix = f"eligibility[{index}]"
    locator = f"line={lineno}"
    rows: list[dict[str, object]] = []

    name = kv[_ASSET_KEY]
    rows.append(
        _row(f"{prefix}.asset_criterion", name, _slug(name), ValueType.STRING, line, locator)
    )
    rows.append(_row(f"{prefix}.eligible", "eligible", "true", ValueType.BOOLEAN, line, locator))

    haircut = _first_number(_lookup(kv, _HAIRCUT_KEYS))
    if haircut is not None:
        rows.append(_row(f"{prefix}.haircut_pct", _lookup(kv, _HAIRCUT_KEYS) or haircut,
                         haircut, ValueType.PERCENTAGE, line, locator, unit="percent"))
    concentration = _first_number(_lookup(kv, _CONCENTRATION_KEYS))
    if concentration is not None:
        rows.append(_row(f"{prefix}.concentration_limit_pct", _lookup(kv, _CONCENTRATION_KEYS),
                         concentration, ValueType.PERCENTAGE, line, locator, unit="percent"))
    rating = _lookup(kv, _RATING_KEYS)
    if rating and rating.casefold() not in {"n/a", "na", "none"}:
        rows.append(_row(f"{prefix}.rating_floor", rating, rating, ValueType.STRING, line, locator))
    currencies = _lookup(kv, _CURRENCY_KEYS)
    if currencies:
        rows.append(_row(f"{prefix}.currency_scope", currencies, currencies,
                         ValueType.STRING_ARRAY, line, locator))
    maturity_years = _first_number(_lookup(kv, _MATURITY_KEYS))
    if maturity_years is not None:
        rows.append(_row(f"{prefix}.tenor_cap_days", _lookup(kv, _MATURITY_KEYS) or "",
                         str(int(float(maturity_years) * 365)), ValueType.INTEGER, line, locator))

    # Shared header-derived economics, per group; absent ones are explicit not_found.
    rows.append(_header_row(f"{prefix}.counterparty", header, _COUNTERPARTY_KEYS, ValueType.STRING))
    rows.append(_header_row(f"{prefix}.agreement_id", header, _AGREEMENT_KEYS, ValueType.STRING))
    rows.append(_header_row(f"{prefix}.valid_from", header, _VALID_FROM_KEYS, ValueType.DATE))
    rows.append(_not_found_row(f"{prefix}.margin_type"))
    rows.append(_not_found_row(f"{prefix}.schedule_version"))
    return rows


def _header_row(
    field_path: str,
    header: dict[str, tuple[str, str]],
    keys: tuple[str, ...],
    value_type: ValueType,
) -> dict[str, object]:
    for key in keys:
        if key in header:
            value, clause = header[key]
            normalized = value if value_type is not ValueType.DATE else _iso_date(value)
            if normalized:
                return _row(field_path, value, normalized, value_type, clause, "header")
    return _not_found_row(field_path)


def _row(
    field_path: str,
    raw: str,
    normalized: str,
    value_type: ValueType,
    clause: str,
    locator: str,
    *,
    unit: str | None = None,
    confidence: float = 0.7,
) -> dict[str, object]:
    row: dict[str, object] = {
        "field_path": field_path,
        "raw_value": raw,
        "normalized_value": normalized,
        "value_type": value_type.value,
        "source_clause": clause,
        "source_locator": locator,
        "confidence": confidence,
        "ambiguity_flag": False,
    }
    if unit is not None:
        row["unit"] = unit
    return row


def _not_found_row(field_path: str) -> dict[str, object]:
    return {
        "field_path": field_path,
        "raw_value": "",
        "normalized_value": "not_found",
        "value_type": ValueType.NOT_FOUND.value,
        "source_clause": "[not stated in document]",
        "source_locator": "not_found",
        "confidence": 0.5,
        "ambiguity_flag": False,
    }


def _header_fields(lines: list[str]) -> dict[str, tuple[str, str]]:
    fields: dict[str, tuple[str, str]] = {}
    for line in lines:
        if "|" in line or ":" not in line:
            continue
        key, value = line.split(":", 1)
        key_norm = key.strip().casefold()
        value = value.strip()
        if key_norm and value and key_norm not in fields:
            fields[key_norm] = (value, line)
    return fields


def _pipe_fields(line: str) -> dict[str, str]:
    fields: dict[str, str] = {}
    for part in line.split("|"):
        if ":" not in part:
            continue
        key, value = part.split(":", 1)
        fields[key.strip().casefold()] = value.strip()
    return fields


def _lookup(kv: dict[str, str], keys: tuple[str, ...]) -> str:
    for key in keys:
        if key in kv:
            return kv[key]
    return ""


def _first_number(value: str) -> str | None:
    match = _NUMBER_RE.search(value)
    return match.group(0) if match else None


def _slug(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", value.strip().casefold()).strip("_") or "unspecified"


def _iso_date(value: str) -> str:
    match = re.search(r"\d{4}-\d{2}-\d{2}", value)
    return match.group(0) if match else ""


def _date_from_mdy(value: str) -> str:
    match = re.search(r"(\d{1,2})\.(\d{1,2})\.(\d{4})", value)
    if not match:
        return ""
    month, day, year = match.groups()
    return f"{year}-{int(month):02d}-{int(day):02d}"


def _line_containing(lines: list[tuple[str, str]], needle: str) -> str:
    normalized_needle = needle.casefold()
    for original, collapsed in lines:
        if normalized_needle in collapsed.casefold():
            return original
    return ""


def _collapse_whitespace(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip()


def _first_line(text: str) -> str:
    for line in text.splitlines():
        if line.strip():
            return line
    return text[:80]
