"""Self-contained HTML quality dashboard rendered from a QualityReport.

No external assets or scripts: inline CSS, theme-aware (light/dark), so the file
opens anywhere and can be served by the Dash stack or attached to a briefing.
Status colours follow the reserved good/warning/serious/critical roles and always
ship with a text label — never colour alone.
"""

from __future__ import annotations

import html
from typing import Any

from document_refinery.quality.reporting import QualityReport

# Reserved status palette (dataviz status roles); confirmed=good, corrected=blue
# (a settled state, not an alert), disputed=critical, pending=warning.
_STATUS_STYLE = {
    "confirmed": ("#0ca30c", "confirmed"),
    "corrected": ("#2a78d6", "corrected"),
    "disputed": ("#d03b3b", "disputed"),
    "pending": ("#fab219", "pending"),
}


def render_dashboard(report: QualityReport, *, title: str = "Document Refinery") -> str:
    d = report.dashboard_payload
    disputes = _int(d["dispute_count"])
    tiles = [
        _tile("Documents", str(_int(d["document_count"]))),
        _tile("Fields extracted", str(_int(d["field_count"]))),
        _tile("Field completeness", f"{_num(d['completeness_pct']):.1f}%"),
        _tile("Mean confidence", f"{_num(d['mean_confidence']) * 100:.0f}%"),
        _tile("Open disputes", str(disputes), alert=disputes > 0),
        _tile("Ambiguous fields", str(_int(d["ambiguity_count"]))),
    ]
    raw_counts = d.get("validator_status_counts", {})
    status_counts: dict[str, Any] = raw_counts if isinstance(raw_counts, dict) else {}
    raw_docs = d.get("per_document", [])
    per_doc: list[dict[str, Any]] = raw_docs if isinstance(raw_docs, list) else []
    return _PAGE.format(
        title=html.escape(title),
        briefing=html.escape(report.executive_briefing),
        tiles="\n".join(tiles),
        status_bar=_status_bar(status_counts),
        status_legend=_status_legend(status_counts),
        rows=_doc_rows(per_doc),
    )


def _tile(label: str, value: str, *, alert: bool = False) -> str:
    cls = " tile-alert" if alert else ""
    return (
        f'<div class="tile{cls}"><div class="tile-value">{html.escape(value)}</div>'
        f'<div class="tile-label">{html.escape(label)}</div></div>'
    )


def _status_bar(counts: dict[str, Any]) -> str:
    total = sum(int(v) for v in counts.values()) or 1
    segments = []
    for status, (color, _label) in _STATUS_STYLE.items():
        n = int(counts.get(status, 0))
        if n == 0:
            continue
        pct = n / total * 100
        segments.append(
            f'<div class="seg" style="width:{pct:.3f}%;background:{color}" '
            f'title="{html.escape(status)}: {n}"></div>'
        )
    return "".join(segments)


def _status_legend(counts: dict[str, Any]) -> str:
    items = []
    for status, (color, label) in _STATUS_STYLE.items():
        n = int(counts.get(status, 0))
        items.append(
            f'<span class="legend-item"><span class="swatch" style="background:{color}"></span>'
            f"{html.escape(label)} <b>{n}</b></span>"
        )
    return "".join(items)


def _doc_rows(per_doc: list[dict[str, Any]]) -> str:
    rows = []
    for doc in per_doc:
        comp = _num(doc.get("completeness_pct", 0))
        conf = _num(doc.get("mean_confidence", 0)) * 100
        disputes = int(doc.get("dispute_count", 0))
        dispute_cell = (
            f'<span class="pill pill-alert">{disputes}</span>'
            if disputes
            else '<span class="pill">0</span>'
        )
        rows.append(
            "<tr>"
            f'<td class="mono">{html.escape(str(doc.get("doc_id", "")))}</td>'
            f'<td class="num">{int(doc.get("field_count", 0))}</td>'
            f"<td>{_meter(comp)}</td>"
            f"<td>{_meter(conf)}</td>"
            f'<td class="num">{dispute_cell}</td>'
            "</tr>"
        )
    return "\n".join(rows)


def _meter(pct: float) -> str:
    pct = max(0.0, min(100.0, pct))
    return (
        f'<div class="meter"><div class="meter-fill" style="width:{pct:.1f}%"></div>'
        f'<span class="meter-text">{pct:.0f}%</span></div>'
    )


def _int(value: object) -> int:
    if isinstance(value, int | float) and not isinstance(value, bool):
        return int(value)
    return 0


def _num(value: object) -> float:
    if isinstance(value, int | float) and not isinstance(value, bool):
        return float(value)
    return 0.0


_PAGE = """<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title} — quality dashboard</title>
<style>
:root {{
  --surface: #fcfcfb; --plane: #f9f9f7; --ink: #0b0b0b; --ink2: #52514e;
  --muted: #898781; --hair: #e1e0d9; --ring: rgba(11,11,11,0.10);
}}
@media (prefers-color-scheme: dark) {{
  :root {{
    --surface: #1a1a19; --plane: #0d0d0d; --ink: #fff; --ink2: #c3c2b7;
    --muted: #898781; --hair: #2c2c2a; --ring: rgba(255,255,255,0.10);
  }}
}}
* {{ box-sizing: border-box; }}
body {{ margin:0; background:var(--plane); color:var(--ink);
  font:15px/1.5 system-ui,-apple-system,"Segoe UI",sans-serif; }}
.wrap {{ max-width: 960px; margin: 0 auto; padding: 2rem 1.25rem 3rem; }}
h1 {{ font-size: 1.4rem; margin: 0 0 .25rem; }}
.sub {{ color: var(--ink2); margin: 0 0 1.5rem; }}
.briefing {{ background:var(--surface); border:1px solid var(--ring);
  border-radius:12px; padding:1rem 1.15rem; color:var(--ink2); margin-bottom:1.5rem; }}
.tiles {{ display:grid; gap:.75rem; margin-bottom:1.75rem;
  grid-template-columns:repeat(auto-fit,minmax(150px,1fr)); }}
.tile {{ background:var(--surface); border:1px solid var(--ring);
  border-radius:12px; padding:1rem 1.1rem; }}
.tile-value {{ font-size:1.9rem; font-weight:650; letter-spacing:-0.02em; }}
.tile-label {{ color:var(--muted); font-size:.82rem; margin-top:.15rem; }}
.tile-alert .tile-value {{ color:#d03b3b; }}
.card {{ background:var(--surface); border:1px solid var(--ring);
  border-radius:12px; padding:1.25rem; margin-bottom:1.5rem; }}
.card h2 {{ font-size:.95rem; margin:0 0 .9rem; }}
.bar {{ display:flex; height:14px; border-radius:7px; overflow:hidden;
  background:var(--hair); gap:2px; }}
.seg {{ height:100%; }}
.legend {{ display:flex; flex-wrap:wrap; gap:1rem; margin-top:.8rem;
  color:var(--ink2); font-size:.85rem; }}
.legend-item {{ display:inline-flex; align-items:center; gap:.4rem; }}
.swatch {{ width:11px; height:11px; border-radius:3px; display:inline-block; }}
table {{ width:100%; border-collapse:collapse; font-size:.88rem; }}
th,td {{ text-align:left; padding:.55rem .5rem;
  border-bottom:1px solid var(--hair); vertical-align:middle; }}
th {{ color:var(--muted); font-weight:600; font-size:.78rem;
  text-transform:uppercase; letter-spacing:.04em; }}
td.num, th.num {{ text-align:right; font-variant-numeric:tabular-nums; }}
.mono {{ font-family:ui-monospace,"SF Mono",Menlo,monospace;
  font-size:.82rem; color:var(--ink2); }}
.meter {{ position:relative; background:var(--hair); border-radius:6px;
  height:20px; min-width:120px; }}
.meter-fill {{ position:absolute; inset:0 auto 0 0; background:#2a78d6; border-radius:6px; }}
.meter-text {{ position:relative; z-index:1; font-size:.75rem; padding:0 .5rem;
  line-height:20px; color:var(--ink); font-variant-numeric:tabular-nums; }}
.pill {{ display:inline-block; min-width:1.6rem; text-align:center;
  padding:.1rem .4rem; border-radius:20px; background:var(--hair);
  font-variant-numeric:tabular-nums; }}
.pill-alert {{ background:#d03b3b; color:#fff; }}
.foot {{ color:var(--muted); font-size:.8rem; margin-top:1.5rem; }}
.scroll {{ overflow-x:auto; }}
</style></head>
<body><div class="wrap">
<h1>{title} — quality dashboard</h1>
<p class="sub">Coverage, confidence, and validation across processed documents.</p>
<div class="briefing">{briefing}</div>
<div class="tiles">{tiles}</div>
<div class="card"><h2>Validation status</h2>
<div class="bar">{status_bar}</div>
<div class="legend">{status_legend}</div></div>
<div class="card"><h2>Per-document coverage</h2><div class="scroll">
<table><thead><tr><th>Document</th><th class="num">Fields</th><th>Completeness</th>
<th>Mean confidence</th><th class="num">Disputes</th></tr></thead>
<tbody>{rows}</tbody></table></div></div>
<p class="foot">Engineering/coverage metrics — not an owner-verified accuracy score.
Gold promotion remains gated on independent validation and Gate A approval.</p>
</div></body></html>
"""
