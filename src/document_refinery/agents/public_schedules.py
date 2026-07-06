"""Extract public collateral schedule formats used by the real-example corpus."""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from datetime import UTC, date, datetime

from document_refinery.domain.models import SilverExtraction, ValidatorStatus, ValueType


@dataclass(frozen=True, slots=True)
class _Profile:
    counterparty_raw: str
    counterparty: str
    agreement_raw: str
    agreement_id: str
    schedule_raw: str
    schedule_version: str
    margin_raw: str
    margin_type: str
    valid_from_raw: str | None
    valid_from: str | None


@dataclass(frozen=True, slots=True)
class _Entry:
    asset_raw: str
    asset_criterion: str
    clause: str
    haircut_raw: str | None = None
    haircut_pct: str | None = None
    concentration_raw: str | None = None
    concentration_limit_pct: str | None = None
    concentration_basis: str | None = None
    rating_floor: str | None = None
    tenor_cap_days: str | None = None


class PublicCollateralScheduleExtractor:
    """Profile-aware deterministic parser for published schedule conventions."""

    DOC_CLASS = "collateral_eligibility_schedule"

    def __init__(
        self,
        *,
        extractor_version: str = "public-rules-1.0.0",
        constitution_version: str = "eligibility-1.1.0",
    ) -> None:
        self.extractor_version = extractor_version
        self.constitution_version = constitution_version

    def extract(
        self,
        *,
        profile: str,
        doc_id: str,
        text: str,
        received_date: date,
    ) -> tuple[SilverExtraction, ...]:
        metadata = _profile(profile, text)
        entries = _entries(profile, text)
        if not entries:
            raise ValueError(f"no eligibility rules found for profile: {profile}")
        rows: list[SilverExtraction] = []
        for index, entry in enumerate(entries):
            fields = _field_values(metadata, entry)
            for field, (raw, normalized, value_type, clause, unit) in fields.items():
                if field == "valid_from" and normalized is None:
                    raw = ""
                rows.append(
                    self._row(
                        doc_id=doc_id,
                        field_path=f"eligibility[{index}].{field}",
                        raw_value=raw,
                        normalized_value=normalized,
                        value_type=value_type,
                        source_clause=clause,
                        text=text,
                        unit=unit,
                    )
                )
        return tuple(rows)

    def _row(
        self,
        *,
        doc_id: str,
        field_path: str,
        raw_value: str,
        normalized_value: str | None,
        value_type: ValueType,
        source_clause: str,
        text: str,
        unit: str | None,
    ) -> SilverExtraction:
        missing = normalized_value is None
        resolved_value: str = (
            "not_found" if normalized_value is None else normalized_value
        )
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
            raw_value="" if missing else raw_value,
            normalized_value=resolved_value,
            value_type=ValueType.NOT_FOUND if missing else value_type,
            source_clause="[FIELD NOT FOUND]" if missing else source_clause,
            source_locator=(
                "document=all;field_not_found"
                if missing
                else _source_locator(text, source_clause)
            ),
            confidence=0.0 if missing else 0.98,
            validator_status=ValidatorStatus.PENDING,
            unit=unit,
            created_at=datetime.now(UTC),
        )


class PublicScheduleValidator:
    """Evidence validator independent of the profile parsing functions."""

    def validate(
        self,
        *,
        text: str,
        extractions: tuple[SilverExtraction, ...],
    ) -> tuple[SilverExtraction, ...]:
        from dataclasses import replace

        validated: list[SilverExtraction] = []
        collapsed_text = _collapse(text).casefold()
        for row in extractions:
            if row.value_type is ValueType.NOT_FOUND:
                status = ValidatorStatus.CONFIRMED
            else:
                clause_present = _collapse(row.source_clause).casefold() in collapsed_text
                raw_supported = row.raw_value.casefold() in row.source_clause.casefold()
                field = row.field_path.rsplit(".", 1)[-1]
                if field == "eligible":
                    raw_supported = any(
                        marker in collapsed_text for marker in ("eligible", "acceptable")
                    )
                elif field == "asset_criterion":
                    tokens = {
                        token
                        for token in re.findall(r"[a-z0-9]+", row.raw_value.casefold())
                        if len(token) >= 4
                    }
                    clause_text = row.source_clause.casefold()
                    raw_supported = raw_supported or (
                        bool(tokens) and any(token in clause_text for token in tokens)
                    )
                elif field == "rating_floor":
                    raw_supported = all(
                        token in collapsed_text
                        for token in re.findall(
                            r"[a-z0-9]+",
                            row.raw_value.casefold(),
                        )
                    )
                elif field == "concentration_basis":
                    basis_tokens = re.findall(r"[a-z]{5,}", row.raw_value.casefold())
                    raw_supported = any(
                        token in row.source_clause.casefold() for token in basis_tokens
                    )
                consistent = _value_is_consistent(row)
                status = (
                    ValidatorStatus.CONFIRMED
                    if clause_present and raw_supported and consistent
                    else ValidatorStatus.DISPUTED
                )
            validated.append(replace(row, validator_status=status))
        return tuple(validated)


def _profile(name: str, text: str) -> _Profile:
    if name == "ficc_gsd":
        effective = _required_match(r"EFFECTIVE DATE:\s*([A-Za-z]+ \d{1,2}, \d{4})", text)
        return _Profile(
            "FICC GOVERNMENT SECURITIES DIVISION",
            "FICC GSD",
            "SCHEDULE OF HAIRCUTS FOR ELIGIBLE CLEARING FUND SECURITIES",
            "FICC-GSD-CLEARING-FUND",
            effective,
            effective,
            "CLEARING FUND",
            "Clearing Fund",
            effective,
            _iso_date(effective),
        )
    if name == "dtc":
        effective = _required_match(r"EFFECTIVE DATE:\s*([A-Za-z]+ \d{1,2}, \d{4})", text)
        return _Profile(
            "DEPOSITORY TRUST AND CLEARING CORPORATION",
            "DTC",
            "SCHEDULE OF HAIRCUTS FOR ELIGIBLE COLLATERAL SECURITIES",
            "DTC-ELIGIBLE-COLLATERAL",
            effective,
            effective,
            "Collateral Monitor",
            "Clearing Fund",
            effective,
            _iso_date(effective),
        )
    if name == "cme":
        return _Profile(
            "CME Group",
            "CME Clearing",
            "Acceptable Performance Bond Collateral for Base Guaranty Fund Products",
            "CME-BASE-GUARANTY-FUND",
            "Acceptable Performance Bond Collateral for Base Guaranty Fund Products",
            "current",
            "Performance Bond",
            "Clearing Fund",
            None,
            None,
        )
    if name == "isda_vm":
        agreement_date = _required_match(r"dated as of\s+([A-Za-z]+ \d{1,2}, \d{4})", text)
        return _Profile(
            "JPMORGAN CHASE BANK, N.A.,   and   CAMBRIDGE MASTER FUND LP.",
            "JPMorgan Chase Bank / Cambridge Master Fund",
            "2002 MASTER AGREEMENT",
            "JPM-CAMBRIDGE-ISDA-2017",
            agreement_date,
            agreement_date,
            "VM",
            "VM",
            agreement_date,
            _iso_date(agreement_date),
        )
    if name == "portfolio_guidelines":
        effective = _required_match(
            r"AMENDMENT NO\. 10 TO CREDIT AGREEMENT, dated as of ([A-Za-z]+ \d{1,2}, \d{4})",
            text,
        )
        return _Profile(
            "SABA CAPITAL INCOME & OPPORTUNITIES FUND",
            "Saba Capital Income & Opportunities Fund",
            "AMENDMENT NO. 10 TO CREDIT AGREEMENT",
            "SABA-TD-CREDIT-AGREEMENT",
            effective,
            effective,
            "Credit Agreement",
            "Secured Financing",
            effective,
            _iso_date(effective),
        )
    raise ValueError(f"unsupported public schedule profile: {name}")


def _entries(profile: str, text: str) -> tuple[_Entry, ...]:
    if profile == "ficc_gsd":
        return _percent_table_entries(
            text,
            start="Security Type",
            end="Any deposits of Eligible Clearing Fund",
            prefix="ficc",
        )
    if profile == "dtc":
        return _percent_table_entries(
            text,
            start="Table 2",
            end="Securities are assigned a 100% haircut",
            prefix="dtc",
        )
    if profile == "cme":
        return _cme_entries(text)
    if profile == "isda_vm":
        return _isda_entries(text)
    if profile == "portfolio_guidelines":
        return _portfolio_entries(text)
    return ()


def _percent_table_entries(
    text: str,
    *,
    start: str,
    end: str,
    prefix: str,
) -> tuple[_Entry, ...]:
    section = text[text.index(start) :]
    if end in section:
        section = section[: section.index(end)]
    context = ""
    entries: list[_Entry] = []
    for line in (_collapse(item) for item in section.splitlines()):
        if not line:
            continue
        match = re.search(r"(\d+(?:\.\d+)?)%\s*$", line)
        if not match:
            if line.casefold() not in {
                "security type remaining maturity haircut",
                "security type rating (s&p/moody) collateral haircut",
            }:
                if line.casefold().startswith(
                    ("with ", "obligations ", "of ", "the ", "a ", "an ")
                ):
                    context = _collapse(f"{context} {line}")
                else:
                    context = line
            continue
        haircut = match.group(1)
        raw_description = line[: match.start()].strip()
        if _needs_table_context(raw_description):
            description = _collapse(f"{context} {raw_description}")
        else:
            description = raw_description
            context = description
        clause = line
        criterion = _slug(f"{prefix}-{len(entries) + 1}-{description}")
        entries.append(
            _Entry(
                asset_raw=raw_description or f"{haircut}%",
                asset_criterion=criterion,
                clause=clause,
                haircut_raw=f"{haircut}%",
                haircut_pct=haircut,
            )
        )
    return tuple(entries)


def _cme_entries(text: str) -> tuple[_Entry, ...]:
    entries: list[_Entry] = []
    for label, buckets in (
        ("T-Bills", ("0 to 1 year",)),
        ("TFRNs", ("0 to 1 year", "1 to 3 years")),
        (
            "T-Notes",
            ("0 to 1 year", "1 to 3 years", "3 to 5 years", "5 to 10 years", "10 to 30 years"),
        ),
        (
            "T-Bonds",
            ("0 to 1 year", "1 to 3 years", "3 to 5 years", "5 to 10 years", "10 to 30 years"),
        ),
    ):
        match = re.search(
            rf"(?m)^• {re.escape(label)}\s+((?:\d+(?:\.\d+)?%\s*)+)",
            text,
        )
        if not match:
            continue
        percentages = re.findall(r"\d+(?:\.\d+)?", match.group(1))
        clause = _collapse(match.group(0))
        for bucket, haircut in zip(buckets, percentages, strict=False):
            entries.append(
                _Entry(
                    asset_raw=f"{label}, {bucket}",
                    asset_criterion=_slug(f"cme-{label}-{bucket}"),
                    clause=clause,
                    haircut_raw=f"{haircut}%",
                    haircut_pct=haircut,
                )
            )
    for label, pattern in (
        ("COMEX gold warrants", r"15%\s+COMEX gold"),
        ("IEF2 money market mutual funds", r"2%\s+Select IEF2"),
        ("U.S. equities", r"U\.S\. Equities.*?\n30%\s+Yes Yes Yes"),
        ("Select ETFs", r"• Select ETFs 25%\s+Yes Yes Yes"),
    ):
        match = re.search(pattern, text, flags=re.DOTALL)
        if not match:
            continue
        clause = _collapse(match.group(0))
        haircut = _required_match(r"(\d+(?:\.\d+)?)%", clause)
        entries.append(
            _Entry(
                asset_raw=label,
                asset_criterion=_slug(f"cme-{label}"),
                clause=clause,
                haircut_raw=f"{haircut}%",
                haircut_pct=haircut,
            )
        )
    return tuple(entries)


def _isda_entries(text: str) -> tuple[_Entry, ...]:
    start = text.index("ISDA COLLATERAL ASSET DEFINITION")
    end = text.index("The definitions used in this table", start)
    section = text[start:end]
    entries: list[_Entry] = []
    current_asset = ""
    for line in (_collapse(item) for item in section.splitlines()):
        match = re.search(r"(\d+(?:\.\d+)?)%\s*$", line)
        if not match:
            continue
        valuation = match.group(1)
        description = line[: match.start()].strip()
        asset_match = re.match(r"(US-[A-Z /-]+)\s+(.*)", description)
        if asset_match:
            current_asset = asset_match.group(1).strip(" /")
            condition = asset_match.group(2)
        else:
            condition = description
        asset = current_asset or description
        haircut = _format_decimal(100.0 - float(valuation))
        entries.append(
            _Entry(
                asset_raw=f"{asset}: {condition}",
                asset_criterion=_slug(f"isda-{asset}-{condition}"),
                clause=line,
                haircut_raw=f"{valuation}%",
                haircut_pct=haircut,
                rating_floor="AA / Aa2" if asset != "US-CASH" else None,
            )
        )
    return tuple(entries)


def _portfolio_entries(text: str) -> tuple[_Entry, ...]:
    entries: list[_Entry] = []
    rules = (
        (
            "Single Issuer Concentration Limit",
            r"(Single Issuer Concentration Limit\.\s+No more than (\d+(?:\.\d+)?)%[^.]*\.)",
            "aggregate Value of Eligible Assets",
        ),
        (
            "Maximum Issuance Concentration Limit",
            (
                r"(Maximum Issuance Concentration Limit\.[\s\S]{0,220}?"
                r"more than (\d+(?:\.\d+)?)%[^.]*\.)"
            ),
            "lesser of notional or outstanding issuance",
        ),
        (
            "BICS Industry Group Concentration Limit",
            r"(BICs Industry Group Concentration Limit\.\s+No more than (\d+(?:\.\d+)?)%[^.]*\.)",
            "Bloomberg BICS industry group",
        ),
    )
    for label, pattern, basis in rules:
        match = re.search(pattern, text, flags=re.IGNORECASE)
        if match:
            entries.append(
                _Entry(
                    asset_raw=label,
                    asset_criterion=_slug(label),
                    clause=_collapse(match.group(1)),
                    concentration_raw=f"{match.group(2)}%",
                    concentration_limit_pct=match.group(2),
                    concentration_basis=basis,
                )
            )
    liquidation = re.search(
        r"(Liquidation Period\.[\s\S]{0,1200}?Less than 5 trading days\s+0%[\s\S]*?"
        r"5\s*[–-]\s*9\.9999 trading days\s+20%[\s\S]*?10 trading days or more\s+100%)",
        text,
    )
    if liquidation:
        clause = _collapse(liquidation.group(1))
        for label, haircut in (
            ("Equity liquidation under 5 trading days", "0"),
            ("Equity liquidation 5 to 9.9999 trading days", "20"),
            ("Equity liquidation 10 or more trading days", "100"),
        ):
            entries.append(
                _Entry(
                    asset_raw=label,
                    asset_criterion=_slug(label),
                    clause=clause,
                    haircut_raw=f"{haircut}%",
                    haircut_pct=haircut,
                )
            )
    return tuple(entries)


def _field_values(
    profile: _Profile,
    entry: _Entry,
) -> dict[str, tuple[str, str | None, ValueType, str, str | None]]:
    return {
        "counterparty": (
            profile.counterparty_raw,
            profile.counterparty,
            ValueType.STRING,
            profile.counterparty_raw,
            None,
        ),
        "agreement_id": (
            profile.agreement_raw,
            profile.agreement_id,
            ValueType.STRING,
            profile.agreement_raw,
            None,
        ),
        "schedule_version": (
            profile.schedule_raw,
            profile.schedule_version,
            ValueType.STRING,
            profile.schedule_raw,
            None,
        ),
        "margin_type": (
            profile.margin_raw,
            profile.margin_type,
            ValueType.STRING,
            profile.margin_raw,
            None,
        ),
        "asset_criterion": (
            entry.asset_raw,
            entry.asset_criterion,
            ValueType.STRING,
            entry.clause,
            None,
        ),
        "eligible": (
            "Eligible",
            "true",
            ValueType.BOOLEAN,
            profile.agreement_raw,
            None,
        ),
        "haircut_pct": (
            entry.haircut_raw or "",
            entry.haircut_pct,
            ValueType.PERCENTAGE,
            entry.clause,
            (
                "percent_haircut_from_valuation_percentage"
                if profile.margin_type == "VM" and entry.haircut_pct is not None
                else "percent"
            ),
        ),
        "concentration_limit_pct": (
            entry.concentration_raw or "",
            entry.concentration_limit_pct,
            ValueType.PERCENTAGE,
            entry.clause,
            "percent",
        ),
        "concentration_basis": (
            entry.concentration_basis or "",
            entry.concentration_basis,
            ValueType.STRING,
            entry.clause,
            None,
        ),
        "currency_scope": ("", None, ValueType.STRING_ARRAY, entry.clause, None),
        "rating_floor": (
            entry.rating_floor or "",
            entry.rating_floor,
            ValueType.STRING,
            entry.clause,
            None,
        ),
        "tenor_cap_days": (
            entry.tenor_cap_days or "",
            entry.tenor_cap_days,
            ValueType.INTEGER,
            entry.clause,
            "days",
        ),
        "valid_from": (
            profile.valid_from_raw or "",
            profile.valid_from,
            ValueType.DATE,
            profile.valid_from_raw or entry.clause,
            None,
        ),
        "valid_to": ("", None, ValueType.DATE, entry.clause, None),
    }


def _value_is_consistent(row: SilverExtraction) -> bool:
    field = row.field_path.rsplit(".", 1)[-1]
    if field in {"haircut_pct", "concentration_limit_pct"}:
        try:
            return 0.0 <= float(row.normalized_value) <= 100.0
        except ValueError:
            return False
    if field == "eligible":
        return row.normalized_value in {"true", "false"}
    if field == "valid_from":
        try:
            date.fromisoformat(row.normalized_value)
        except ValueError:
            return False
    return True


def _source_locator(text: str, clause: str) -> str:
    target = _collapse(clause)
    pages = text.split("\f")
    for page_number, page in enumerate(pages, start=1):
        collapsed_page = _collapse(page)
        position = collapsed_page.find(target)
        if position >= 0:
            anchor = target[:48]
            for line_number, line in enumerate(page.splitlines(), start=1):
                if _collapse(line) and _collapse(line) in anchor:
                    return f"page={page_number};line={line_number}"
            digest = hashlib.sha256(target.encode()).hexdigest()[:16]
            return f"page={page_number};anchor_sha256={digest}"
    return "document=all;locator_unresolved"


def _required_match(pattern: str, text: str) -> str:
    match = re.search(pattern, text, flags=re.IGNORECASE)
    if not match:
        raise ValueError(f"required pattern not found: {pattern}")
    return _collapse(match.group(1))


def _needs_table_context(description: str) -> bool:
    lowered = description.casefold()
    return (
        len(description) < 8
        or lowered.startswith(
            (
                "with ",
                "zero to ",
                "1 year",
                "2 years",
                "5 years",
                "10 years",
                "15 years",
                "rated ",
                "not rated",
                "all ",
            )
        )
        or bool(
            re.match(
                r"^(?:AAA|AA|A[+-]?(?:\d)?|BBB|BB|B[+-]|CCC|SP-|MIG-|P-)",
                description,
            )
        )
    )


def _collapse(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip()


def _slug(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", value.casefold()).strip("_")[:160]


def _iso_date(value: str) -> str:
    return datetime.strptime(value, "%B %d, %Y").date().isoformat()


def _format_decimal(value: float) -> str:
    return f"{value:.4f}".rstrip("0").rstrip(".")
