"""Printable owner report: one self-contained HTML page (Print > Save as PDF gives a PDF)."""
from __future__ import annotations

import datetime as _dt
from html import escape

from . import __version__

CSS = """
:root{--ink:#11303b;--muted:#5c7480;--line:#d5dee3;--blue:#2b7ba3;--red:#b23a2c;--bg:#fff}
*{box-sizing:border-box}body{font:14px/1.5 system-ui,-apple-system,Segoe UI,Roboto,sans-serif;color:var(--ink);
background:var(--bg);margin:0}main{max-width:820px;margin:0 auto;padding:36px 28px}
h1{font-size:26px;line-height:1.2;margin:0 0 6px}h2{font-size:17px;margin:30px 0 8px}
.sub{color:var(--muted);margin:0 0 18px}.gap{color:var(--red)}
.kpis{display:grid;grid-template-columns:repeat(3,1fr);gap:14px;margin:18px 0}
.kpi{border:1px solid var(--line);border-radius:6px;padding:12px 14px}.kpi b{display:block;font-size:22px}
.kpi span{color:var(--muted);font-size:12px}
table{width:100%;border-collapse:collapse;font-size:13px}th,td{padding:6px 8px;border-bottom:1px solid var(--line);text-align:right}
th:first-child,td:first-child{text-align:left}th{color:var(--muted);font-weight:600}
.cause{border-top:1px solid var(--line);padding:12px 0}.cause h3{font-size:15px;margin:0 0 4px;display:flex;justify-content:space-between;gap:12px}
.bar{height:6px;background:#e4ebee;border-radius:3px;margin:6px 0}.bar i{display:block;height:100%;background:var(--blue);border-radius:3px}
ul{margin:6px 0 0;padding-left:20px}.note{background:#f3f7f9;border-left:3px solid var(--blue);padding:8px 12px;margin:10px 0}
.foot{color:var(--muted);font-size:12px;margin-top:30px;border-top:1px solid var(--line);padding-top:10px}
@media print{main{padding:0}.cause{break-inside:avoid}}
"""


def _aed(x: float) -> str:
    return f"AED {x:,.0f}"


def _chart(sig: list, min_dt: float) -> str:
    if not sig:
        return ""
    W, H, L, B, T = 640, 230, 46, 34, 14
    xs = lambda v: L + (W - L - 10) * v
    ymax = max(14.0, max(p["dt_c"] for p in sig) + 1, min_dt + 1)
    ys = lambda v: T + (H - T - B) * (1 - v / ymax)
    parts = [f'<svg viewBox="0 0 {W} {H}" role="img" aria-label="Delta-T against load" width="100%">']
    for g in range(0, int(ymax) + 1, 2):
        parts.append(f'<line x1="{L}" x2="{W-10}" y1="{ys(g):.1f}" y2="{ys(g):.1f}" stroke="#e4ebee"/>'
                     f'<text x="{L-6}" y="{ys(g)+4:.1f}" text-anchor="end" font-size="11" fill="#5c7480">{g}</text>')
    parts.append(f'<line x1="{L}" x2="{W-10}" y1="{ys(min_dt):.1f}" y2="{ys(min_dt):.1f}" stroke="#b23a2c" '
                 f'stroke-dasharray="5 4"/><text x="{W-12}" y="{ys(min_dt)-5:.1f}" text-anchor="end" font-size="11" '
                 f'fill="#b23a2c">contract minimum {min_dt:.1f} C</text>')
    pts = " ".join(f"{xs(p['load_pct']/100):.1f},{ys(p['dt_c']):.1f}" for p in sig)
    parts.append(f'<polyline points="{pts}" fill="none" stroke="#2b7ba3" stroke-width="2"/>')
    wmax = max(p["flow_share"] for p in sig) or 1.0
    for p in sig:
        r = 3 + 7 * (p["flow_share"] / wmax) ** 0.5
        parts.append(f'<circle cx="{xs(p["load_pct"]/100):.1f}" cy="{ys(p["dt_c"]):.1f}" r="{r:.1f}" fill="#2b7ba3" fill-opacity=".35" stroke="#2b7ba3"/>')
    for v in (0, .2, .4, .6, .8, 1.0):
        parts.append(f'<text x="{xs(v):.1f}" y="{H-14}" text-anchor="middle" font-size="11" fill="#5c7480">{int(v*100)}%</text>')
    parts.append(f'<text x="{(L+W)/2:.0f}" y="{H-1}" text-anchor="middle" font-size="11" fill="#5c7480">cooling load, share of peak</text>')
    parts.append(f'<text x="12" y="{T+4}" font-size="11" fill="#5c7480">delta-T (C)</text></svg>')
    return "".join(parts)


def render_report(d: dict, building_name: str = "Building") -> str:
    """d is Report.to_dict()."""
    e = escape
    short = max(d["min_delta_t_c"] - d["delta_t_c"], 0.0)
    head = (f'returns <b>{d["delta_t_c"]:.1f} C</b>, <span class="gap">{short:.1f} C under</span> the '
            f'{d["min_delta_t_c"]:.1f} C minimum.' if d["below_minimum"]
            else f'returns <b>{d["delta_t_c"]:.1f} C</b>, at or above the {d["min_delta_t_c"]:.1f} C minimum.')
    top = d["findings"][0] if d["findings"] else None
    kp = [(_aed(d["annual_surcharge_aed_estimate"]), "estimated surcharge per year"),
          (f'{d["p_any_cause"]:.0%}', "chance a fixable cause is present"),
          (_aed(top["expected_saving_aed_per_year"]) if top else "-", "expected saving from the first fix")]
    out = [f'<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">'
           f'<title>Delta-T report: {e(building_name)}</title><style>{CSS}</style></head><body><main>',
           f'<h1>{e(building_name)} {head}</h1>',
           f'<p class="sub">{d["n_days"]:.0f} days of meter data, {d["n_windows"]} analysis window(s). '
           f'{"Informed diagnosis, design delta-T " + str(d["design_delta_t_c"]) + " C." if d.get("mode") == "informed" else "Blind diagnosis: no design delta-T given."}'
           f' Generated {_dt.date.today().isoformat()} by delta-t-doctor {__version__}.</p>',
           '<div class="kpis">' + "".join(f'<div class="kpi"><b>{e(v)}</b><span>{e(l)}</span></div>' for v, l in kp) + "</div>",
           "<h2>Delta-T against load</h2>", _chart(d.get("signature", []), d["min_delta_t_c"]),
           '<p class="sub">Each dot is a load band; larger dots carry more of the water. A building that falls under the '
           'dashed line is paying the surcharge in that band.</p>',
           "<h2>Where to look first</h2>"]
    for f in d["findings"]:
        out.append(f'<div class="cause"><h3><span>{e(f["label"])}</span><span>{_aed(f["expected_saving_aed_per_year"])} a year</span></h3>'
                   f'<div class="bar"><i style="width:{max(f["probability"]*100, 1):.0f}%"></i></div>'
                   f'<div class="sub">{f["probability"]:.0%} likely. Fixing it would recover about {f["expected_dt_gain_c"]:.1f} C.</div>'
                   f'<b>What to check</b><ul>' + "".join(f"<li>{e(c)}</li>" for c in f["checks"]) + "</ul></div>")
    if d.get("monthly"):
        out.append("<h2>Month by month</h2><table><tr><th>Month</th><th>Delta-T (C)</th><th>Below minimum (C)</th><th>Surcharge (AED)</th></tr>")
        for m in d["monthly"]:
            out.append(f'<tr><td>{e(str(m.get("month")))}</td><td>{m.get("delta_t_c", float("nan")):.2f}</td>'
                       f'<td>{m.get("shortfall_c", 0):.2f}</td><td>{m.get("surcharge_aed", 0):,.0f}</td></tr>')
        out.append("</table>")
    for n in d.get("notes", []):
        out.append(f'<div class="note">{e(n)}</div>')
    t = d["terms"]
    out.append(f'<p class="foot">Contract terms used: minimum delta-T {t["min_delta_t_c"]} C, surcharge '
               f'{t["surcharge_pct_per_degree"]:.0%} per C below it, rate AED {t["rate_aed_per_rt_hr"]} per RT-hr. '
               f'Dirham figures are only as good as these inputs.<br>{e(d["disclaimer"])}</p></main></body></html>')
    return "".join(out)
