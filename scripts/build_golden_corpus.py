#!/usr/bin/env python3
"""Generate the realistic collateral-schedule golden corpus + ground truth.

Writes 10 varied schedules (CSA VM/IM, tri-party repo, securities lending,
multi-currency, EM, cash) to ``examples/golden_corpus/`` with an independently
authored ``ground_truth.json``. A few documents carry realistic real-world
variations (``Variation Margin`` vs ``VM``, ``1.50%`` vs ``1.5``, currency names
vs ISO codes, ``Y`` vs ``yes``) whose ground truth stays human-correct, so the
accuracy harness surfaces genuine extractor normalization gaps instead of grading
the extractor against itself.

These are realistic **synthetic** fixtures modeled on real collateral schedules —
not real published documents (which the sandbox cannot fetch) and not
owner-verified. Run this to regenerate; run `document-refinery accuracy` to score.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))

from document_refinery.agents.eligibility import EligibilityScheduleExtractor  # noqa: E402

OUT = REPO / "examples" / "golden_corpus"

# Each asset: (criterion, eligible, haircut, conc_limit, basis, currencies, rating, tenor_days)
# rating/tenor None -> omitted from the document (ground truth "not_found").
Schedules: list[dict[str, object]] = [
    {
        "case_id": "01-csa-vm-us-megabank",
        "title": "ISDA CSA (VM) — Sterling Bridge Bank, N.A. (USD)",
        "cp": "Sterling Bridge Bank, N.A.",
        "agr": "CSA-2019-US-0442",
        "ver": "2026-01",
        "margin": "VM",
        "valid_from": "2026-01-01",
        "assets": [
            ("US Treasury Securities", True, 0.5, 100, "market value", ["USD"], None, 10950),
            ("US Agency Debentures", True, 1.0, 50, "market value", ["USD"], "AA-", 10950),
            ("US Agency MBS", True, 2.0, 40, "market value", ["USD"], "AA-", 10950),
            ("USD Investment-Grade Corporates", True, 5.0, 20, "market value", ["USD"], "A-", 3650),
            ("US Large-Cap Equities", True, 15.0, 10, "market value", ["USD"], None, None),
        ],
    },
    {
        "case_id": "02-csa-vm-eur",
        "title": "ISDA CSA (VM) — Meridian Global Markets SA (EUR)",
        "cp": "Meridian Global Markets SA",
        "agr": "CSA-2018-EU-1177",
        "ver": "2026-02",
        "margin": "VM",
        "valid_from": "2026-02-01",
        "assets": [
            ("German Federal Bonds (Bunds)", True, 0.5, 100, "market value", ["EUR"], None, 10950),
            ("French OATs", True, 1.0, 60, "market value", ["EUR"], "AA-", 10950),
            ("EUR Covered Bonds (Pfandbriefe)", True, 3.0, 25, "market value", ["EUR"], "AAA", 3650),
            ("EUR Investment-Grade Corporates", True, 6.0, 15, "market value", ["EUR"], "A-", 3650),
        ],
    },
    {
        "case_id": "03-csa-im-simm",
        "title": "ISDA CSA (IM, SIMM) — Halcyon Asset Management LLP",
        "cp": "Halcyon Asset Management LLP",
        "agr": "IM-CSD-2021-0098",
        "ver": "2026-01",
        "margin": "IM",
        "valid_from": "2026-01-15",
        "assets": [
            ("US Treasury Securities", True, 1.0, 100, "market value", ["USD"], None, 10950),
            ("German Federal Bonds (Bunds)", True, 1.0, 100, "market value", ["EUR"], None, 10950),
            ("Gold Bullion (LBMA)", True, 12.0, 10, "market value", ["USD"], None, None),
        ],
    },
    {
        "case_id": "04-triparty-repo-gmra",
        "title": "Tri-party Repo Eligibility (GMRA) — Pacific Rim Clearing Ltd",
        "cp": "Pacific Rim Clearing Ltd",
        "agr": "GMRA-TP-2020-3310",
        "ver": "2026-03",
        "margin": "Repo",
        "valid_from": "2026-03-01",
        "assets": [
            ("G7 Government Bonds", True, 2.0, 100, "market value", ["USD", "EUR", "GBP", "JPY"], "AA-", 10950),
            ("Supranational & Agency", True, 3.0, 40, "market value", ["USD", "EUR"], "AA-", 5475),
            ("Covered Bonds", True, 4.5, 20, "market value", ["EUR"], "AAA", 3650),
        ],
    },
    {
        "case_id": "05-gmsla-securities-lending",
        "title": "Securities Lending Collateral (GMSLA) — Northwind Securities Inc",
        "cp": "Northwind Securities Inc",
        "agr": "GMSLA-2019-0521",
        "ver": "2026-01",
        "margin": "Secured Financing",
        "valid_from": "2026-01-01",
        "assets": [
            ("Main-Index Equities (DM)", True, 8.0, 15, "market value", ["USD", "EUR", "GBP"], None, None),
            ("Exchange-Traded Funds", True, 10.0, 10, "market value", ["USD"], None, None),
            ("Convertible Bonds", False, 0.0, 0, "market value", ["USD"], None, None),
        ],
    },
    {
        "case_id": "06-gilt-gbp",
        "title": "Collateral Schedule (VM) — Thames Capital Partners (GBP)",
        "cp": "Thames Capital Partners LLP",
        "agr": "CSA-2020-UK-0777",
        "ver": "2026-02",
        "margin": "VM",
        "valid_from": "2026-02-15",
        "assets": [
            ("UK Gilts", True, 1.0, 100, "market value", ["GBP"], None, 10950),
            ("Index-Linked Gilts", True, 2.5, 50, "market value", ["GBP"], None, 10950),
            ("GBP Investment-Grade Corporates", True, 6.0, 15, "market value", ["GBP"], "A-", 3650),
        ],
    },
    {
        "case_id": "07-jpy-jgb",
        "title": "Collateral Schedule (VM) — Sakura Trust Bank (JPY)",
        "cp": "Sakura Trust Bank, Ltd.",
        "agr": "CSA-2017-JP-0203",
        "ver": "2026-01",
        "margin": "VM",
        "valid_from": "2026-01-01",
        # Variation: margin rendered "Variation Margin" (ground truth "VM").
        "margin_render": "Variation Margin",
        "assets": [
            ("Japanese Government Bonds (JGB)", True, 1.5, 100, "market value", ["JPY"], None, 10950),
        ],
    },
    {
        "case_id": "08-em-sovereign",
        "title": "Collateral Schedule (VM) — Andes Frontier Bank (EM USD)",
        "cp": "Andes Frontier Bank",
        "agr": "CSA-2022-EM-0459",
        "ver": "2026-02",
        "margin": "VM",
        "valid_from": "2026-02-01",
        "assets": [
            # Variation: eligible rendered "Y" (ground truth "true").
            ("EM Sovereign USD Bonds", True, 8.0, 40, "market value", ["USD"], "BBB-", 3650,
             {"eligible_render": "Y"}),
            ("EM Quasi-Sovereign USD Bonds", True, 10.0, 20, "market value", ["USD"], "BB+", 1825),
        ],
    },
    {
        "case_id": "09-cash-mmf",
        "title": "Collateral Schedule (VM) — Coastal Reserve Trust (Cash & Bills)",
        "cp": "Coastal Reserve Trust",
        "agr": "CSA-2021-US-0812",
        "ver": "2026-01",
        "margin": "VM",
        "valid_from": "2026-01-01",
        "assets": [
            # Variation: currencies rendered as names (ground truth ISO codes).
            ("Cash", True, 0.0, 100, "notional", ["USD", "EUR"], None, None,
             {"currencies_render": "US Dollar, Euro"}),
            ("US Treasury Bills (<= 1y)", True, 0.5, 100, "market value", ["USD"], None, 365),
        ],
    },
    {
        "case_id": "10-multiccy-triparty",
        "title": "Tri-party Collateral Basket (Repo) — Global Nexus Custody",
        "cp": "Global Nexus Custody",
        "agr": "TP-BASKET-2023-0031",
        "ver": "2026-03",
        "margin": "Repo",
        "valid_from": "2026-03-01",
        "assets": [
            # Variation: haircut rendered "1.50%" (ground truth "1.5").
            ("OECD Government Bonds", True, 1.5, 100, "market value", ["USD", "EUR", "GBP", "JPY", "CHF"],
             "AA-", 10950, {"haircut_render": "1.50%"}),
            ("Supranational Bonds", True, 2.5, 40, "market value", ["USD", "EUR"], "AAA", 5475),
            ("Senior Financial Corporates", True, 7.0, 15, "market value", ["USD", "EUR"], "A-", 3650),
        ],
    },
]


def _num(value: float) -> str:
    return f"{value:g}"


def _ccy(codes: list[str]) -> str:
    return ",".join(c.upper() for c in codes)


def render_and_ground_truth(schedule: dict[str, object]) -> tuple[str, dict[str, str]]:
    lines = ["Collateral Eligibility Schedule", "Eligible Collateral"]
    lines.append(f"Counterparty: {schedule['cp']}")
    lines.append(f"Agreement ID: {schedule['agr']}")
    lines.append(f"Schedule Version: {schedule['ver']}")
    lines.append(f"Margin Type: {schedule.get('margin_render', schedule['margin'])}")
    lines.append(f"Valid From: {schedule['valid_from']}")

    expected: dict[str, str] = {}
    assets = schedule["assets"]
    assert isinstance(assets, list)
    for index, asset in enumerate(assets):
        crit, eligible, haircut, conc, basis, ccy, rating, tenor = asset[:8]
        overrides = asset[8] if len(asset) > 8 else {}

        segments = [f"Asset: {crit}"]
        segments.append(f"Eligible: {overrides.get('eligible_render', 'yes' if eligible else 'no')}")
        segments.append(f"Haircut: {overrides.get('haircut_render', _num(haircut) + '%')}")
        segments.append(f"Concentration Limit: {_num(conc)}%")
        segments.append(f"Concentration Basis: {basis}")
        segments.append(f"Currencies: {overrides.get('currencies_render', ', '.join(ccy))}")
        if rating is not None:
            segments.append(f"Rating Floor: {rating}")
        if tenor is not None:
            segments.append(f"Tenor Cap Days: {tenor}")
        lines.append(" | ".join(segments))

        prefix = f"eligibility[{index}]"
        expected[f"{prefix}.counterparty"] = str(schedule["cp"])
        expected[f"{prefix}.agreement_id"] = str(schedule["agr"])
        expected[f"{prefix}.schedule_version"] = str(schedule["ver"])
        expected[f"{prefix}.margin_type"] = str(schedule["margin"])  # human-correct
        expected[f"{prefix}.valid_from"] = str(schedule["valid_from"])
        expected[f"{prefix}.asset_criterion"] = str(crit)
        expected[f"{prefix}.eligible"] = "true" if eligible else "false"
        expected[f"{prefix}.haircut_pct"] = _num(haircut)
        expected[f"{prefix}.concentration_limit_pct"] = _num(conc)
        expected[f"{prefix}.concentration_basis"] = str(basis)
        expected[f"{prefix}.currency_scope"] = _ccy(ccy)
        expected[f"{prefix}.rating_floor"] = str(rating) if rating is not None else "not_found"
        expected[f"{prefix}.tenor_cap_days"] = str(tenor) if tenor is not None else "not_found"
    return "\n".join(lines) + "\n", expected


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    extractor = EligibilityScheduleExtractor()
    ground_truth: dict[str, object] = {}
    intended_misses = 0
    for schedule in Schedules:
        case_id = str(schedule["case_id"])
        text, expected = render_and_ground_truth(schedule)
        (OUT / f"{case_id}.txt").write_text(text, encoding="utf-8")
        ground_truth[case_id] = {
            "title": schedule["title"],
            "owner_verified": False,
            "expected": expected,
        }
        # Self-check: diff extractor output against the human ground truth.
        actual = {r.field_path: r.normalized_value for r in extractor.extract(doc_id=case_id, text=text)}
        for field_path, want in expected.items():
            got = actual.get(field_path, "<missing>")
            if got != want:
                intended_misses += 1
                print(f"  gap {case_id} {field_path}: extractor={got!r} truth={want!r}")

    (OUT / "ground_truth.json").write_text(
        json.dumps(ground_truth, indent=2) + "\n", encoding="utf-8"
    )
    print(f"Wrote {len(Schedules)} schedules to {OUT}")
    print(f"Extractor vs ground-truth gaps surfaced: {intended_misses}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
