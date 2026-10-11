"""Printable owner report: one self-contained HTML page (Print > Save as PDF gives a PDF). English or Arabic (RTL)."""
from __future__ import annotations

import base64
import functools
import os
from html import escape

from . import __version__

FONT_DIR = os.path.join(os.path.dirname(__file__), "web", "fonts")
DEFAULT_RATE = 0.40

S = {
    "en": {
        "dir": "ltr", "title": "Delta-T report", "demo": "SIMULATED DEMO. This is not a real building.",
        "not_validated": "Trained on simulated buildings. Not yet checked against UAE field data. Use as a ranked inspection list, not a quote.",
        "unreliable_h": "Ranking not reliable.", "unreliable_b": "This building behaves unlike the data the model was trained on, or the data has quality problems (see notes). Do not act on the ranking without an engineer's review.",
        "returns": "returns", "under": "under", "the_min": "the", "min_word": "minimum", "meets": "at or above the",
        "status_below": "Below contract by", "status_ok": "Meets the contract minimum",
        "k_sur": "estimated surcharge per year", "k_sur_basis": "extrapolated from", "days": "days",
        "k_first": "first action", "k_save": "expected saving from the first fix", "k_range": "plausible range", "k_negl": "could be negligible",
        "k_conf": "simulated-model probability band", "withheld": "The cause ranking is withheld because this result is flagged not reliable (see the notes). The delta-T and surcharge figures above are measured from your data.", "h_series": "Delta-T over time", "s_start": "Window start", "s_dt": "Delta-T (°C)", "s_hi": "Delta-T at 60-100% load (°C)", "trend_sig": "High-load delta-T is {direction} by about {slope} °C per month (Kendall p={p}). Seasonal swings can mimic a trend.", "High": "High", "Medium": "Medium", "Low": "Low", "NA": "Not reliable",
        "k_chance": "chance a fixable cause is present",
        "basis": "Basis", "basis_blind": "blind diagnosis (no design delta-T given)", "basis_informed": "informed diagnosis, design delta-T",
        "coverage": "data coverage", "window": "analysis windows",
        "h_chart": "Delta-T against load", "chart_note": "Each dot is a load band; larger dots carry more of the water. Where the line is under the dashed contract minimum the building pays the surcharge in that band.",
        "x_label": "cooling load, share of peak", "y_label": "delta-T (°C)", "minimum": "contract minimum",
        "t_band": "Load band", "t_dt": "Delta-T (°C)", "t_share": "Share of water",
        "h_first": "Where to look first", "likely": "likely", "recover": "Fixing it would recover about", "range": "range",
        "check": "What to check", "h_ruled": "Ruled out or negligible", "ruled_note": "Each is under 5% likely and worth under AED 1,000 a year.",
        "h_month": "Month by month", "m_month": "Month", "m_dt": "Delta-T (°C)", "m_short": "Below minimum (°C)", "m_sur": "Surcharge (AED)",
        "h_notes": "Notes", "h_terms": "Contract terms used",
        "terms": "minimum delta-T {min} °C, surcharge {pct} per °C below it, rate AED {rate} per RT-hr{ill}",
        "illustrative": " (illustrative default; enter your contract rate for real dirham figures)",
        "aed": "AED", "a_year": "a year", "h_prov": "Provenance", "prov_note": "Everything needed to reproduce or challenge this report.",
        "p_id": "Report ID", "p_time": "Generated (UTC)", "p_file": "Input file", "p_sha": "SHA-256 of input", "p_window": "Data window",
        "p_rows": "Rows read", "p_dropped": "Rows dropped", "p_model": "Model", "p_trained": "Trained on", "p_params": "Parameters",
        "p_quality": "Reliability", "p_sw": "Software", "p_none": "not recorded", "p_ood": "measurements outside training range",
        "p_rel_yes": "within the model's range", "p_rel_no": "NOT RELIABLE", "windows": "windows", "buildings": "buildings",
        "page": "Page", "font": "system-ui,-apple-system,'Segoe UI',Roboto,sans-serif", "ill_label": "illustrative rate",
    },
    "ar": {
        "dir": "rtl", "title": "تقرير فرق درجة الحرارة", "demo": "نسخة تجريبية محاكاة. هذا ليس مبنى حقيقياً.",
        "not_validated": "جرى تدريب النموذج على مبانٍ محاكاة، ولم يُتحقق منه بعد ببيانات ميدانية من الإمارات. استخدمه قائمةً مرتّبة للفحص لا عرض سعر.",
        "unreliable_h": "الترتيب غير موثوق.", "unreliable_b": "يختلف سلوك هذا المبنى عن البيانات التي تدرّب عليها النموذج، أو أن في البيانات مشكلات جودة (راجع الملاحظات). لا تعتمد على الترتيب دون مراجعة مهندس.",
        "returns": "يعيد", "under": "دون", "the_min": "الحد الأدنى", "min_word": "", "meets": "عند الحد الأدنى أو أعلى منه",
        "status_below": "أقل من العقد بمقدار", "status_ok": "يستوفي الحد الأدنى للعقد",
        "k_sur": "الغرامة السنوية المقدّرة", "k_sur_basis": "مُستقرأة من", "days": "يوماً",
        "k_first": "أول إجراء", "k_save": "الوفر المتوقع من الإصلاح الأول", "k_range": "النطاق المحتمل", "k_negl": "قد يكون ضئيلاً",
        "k_conf": "نطاق احتمال النموذج المحاكى", "withheld": "حُجب ترتيب الأسباب لأن هذه النتيجة موسومة بأنها غير موثوقة (راجع الملاحظات). أرقام فرق درجة الحرارة والغرامة أعلاه مقيسة من بياناتك.", "h_series": "فرق درجة الحرارة عبر الزمن", "s_start": "بداية النافذة", "s_dt": "فرق درجة الحرارة (°م)", "s_hi": "فرق درجة الحرارة عند حمل 60-100% (°م)", "trend_sig": "فرق درجة الحرارة عند الأحمال العالية {direction} بنحو {slope} °م في الشهر (كندال p={p}). التقلبات الموسمية قد تحاكي اتجاهاً.", "High": "عالية", "Medium": "متوسطة", "Low": "منخفضة", "NA": "غير موثوق",
        "k_chance": "احتمال وجود سبب قابل للإصلاح",
        "basis": "الأساس", "basis_blind": "تشخيص دون فرق درجة الحرارة التصميمي", "basis_informed": "تشخيص مُستنير بفرق درجة الحرارة التصميمي",
        "coverage": "تغطية البيانات", "window": "نوافذ التحليل",
        "h_chart": "فرق درجة الحرارة مقابل الحمل", "chart_note": "كل نقطة تمثّل نطاق حِمل؛ والنقاط الأكبر تحمل قدراً أكبر من الماء. حيث يهبط الخط دون الحد الأدنى المتقطع للعقد يدفع المبنى الغرامة في ذلك النطاق.",
        "x_label": "حمل التبريد، نسبة من الذروة", "y_label": "فرق درجة الحرارة (°م)", "minimum": "الحد الأدنى للعقد",
        "t_band": "نطاق الحمل", "t_dt": "فرق درجة الحرارة (°م)", "t_share": "حصة الماء",
        "h_first": "من أين تبدأ الفحص", "likely": "احتمال", "recover": "إصلاحه يسترد نحو", "range": "النطاق",
        "check": "ما الذي يجب فحصه", "h_ruled": "مستبعد أو ضئيل", "ruled_note": "احتمال كل منها أقل من 5% وقيمته أقل من 1,000 درهم سنوياً.",
        "h_month": "شهراً بشهر", "m_month": "الشهر", "m_dt": "فرق درجة الحرارة (°م)", "m_short": "دون الحد الأدنى (°م)", "m_sur": "الغرامة (درهم)",
        "h_notes": "ملاحظات", "h_terms": "شروط العقد المستخدمة",
        "terms": "الحد الأدنى لفرق درجة الحرارة {min} °م، والغرامة {pct} لكل درجة دونه، والسعر {rate} درهم لكل ساعة طن تبريد{ill}",
        "illustrative": " (قيمة افتراضية توضيحية؛ أدخل سعر عقدك للحصول على أرقام فعلية بالدرهم)",
        "aed": "درهم", "a_year": "سنوياً", "h_prov": "مصدر التقرير وتتبّعه", "prov_note": "كل ما يلزم لإعادة إنتاج هذا التقرير أو الطعن فيه.",
        "p_id": "رقم التقرير", "p_time": "وقت الإنشاء (UTC)", "p_file": "ملف الإدخال", "p_sha": "بصمة SHA-256 للملف", "p_window": "نافذة البيانات",
        "p_rows": "الصفوف المقروءة", "p_dropped": "الصفوف المستبعدة", "p_model": "النموذج", "p_trained": "بيانات التدريب", "p_params": "المعاملات",
        "p_quality": "الموثوقية", "p_sw": "البرنامج", "p_none": "غير مسجّل", "p_ood": "مؤشرات خارج نطاق التدريب",
        "p_rel_yes": "ضمن نطاق النموذج", "p_rel_no": "غير موثوق", "windows": "نوافذ", "buildings": "مبانٍ",
        "page": "صفحة", "font": "'IBM Plex Sans Arabic',system-ui,'Segoe UI',Tahoma,sans-serif", "ill_label": "سعر توضيحي",
    },
}

CSS = """
:root{--ink:#0f2b36;--muted:#455d69;--line:#cdd9de;--blue:#1d6f9a;--red:#a8321f;--amber:#8a4b0f;--bg:#fff;--tint:#eef4f7}
*{box-sizing:border-box}
body{font:14px/1.55 var(--font);color:var(--ink);background:var(--bg);margin:0;font-variant-numeric:tabular-nums}
main{max-width:860px;margin:0 auto;padding:30px 28px 48px;position:relative}
h1{font-size:25px;line-height:1.25;margin:6px 0 6px}h2{font-size:17px;margin:28px 0 8px}h3{font-size:15px;margin:0}
.sub{color:var(--muted);margin:0 0 14px}.gap{color:var(--red)}
.top{display:flex;justify-content:space-between;gap:12px;flex-wrap:wrap;font-size:12px;color:var(--muted);border-bottom:1px solid var(--line);padding-bottom:8px}
.demo{background:repeating-linear-gradient(135deg,#fff3cd,#fff3cd 12px,#ffe9a8 12px,#ffe9a8 24px);border:2px solid #b38600;color:#5c4400;font-weight:700;text-align:center;padding:8px;margin:12px 0;border-radius:4px}
.trust{background:var(--tint);border-inline-start:4px solid var(--blue);padding:8px 12px;margin:12px 0;font-size:13px}
.warn{background:#fdecea;border:2px solid var(--red);color:#6d1d11;padding:10px 14px;margin:12px 0;border-radius:4px}.warn b{display:block;font-size:16px}
.chip{display:inline-block;font-weight:700;font-size:13px;padding:3px 10px;border-radius:999px;border:1.5px solid currentColor}
.chip.bad{color:var(--red)}.chip.good{color:#1c6b3a}
.kpis{display:grid;grid-template-columns:repeat(3,1fr);gap:12px;margin:14px 0}
.kpi{border:1px solid var(--line);border-radius:6px;padding:11px 13px}.kpi b{display:block;font-size:21px;line-height:1.25}
.kpi span{color:var(--muted);font-size:12px;display:block}.kpi small{display:block;color:var(--muted);font-size:12px;margin-top:2px}
.basis{font-size:13px;color:var(--muted);margin:4px 0 10px}
.chartbox{overflow-x:auto}.chartbox svg{min-width:520px}
table{width:100%;border-collapse:collapse;font-size:13px}th,td{padding:6px 8px;border-bottom:1px solid var(--line);text-align:end;white-space:nowrap}
th:first-child,td:first-child{text-align:start}th{color:var(--muted);font-weight:600}
.cause{border-top:1px solid var(--line);padding:12px 0}.cause h3{display:flex;justify-content:space-between;gap:12px;flex-wrap:wrap}
.bar{height:7px;background:#dde7eb;border-radius:4px;margin:7px 0;position:relative}.bar i{display:block;height:100%;background:var(--blue);border-radius:4px}
.whisk{position:relative;height:10px;margin:2px 0 6px;background:linear-gradient(#cfdbe1,#cfdbe1) center/100% 2px no-repeat}
.whisk u{position:absolute;top:1px;height:8px;background:rgba(29,111,154,.28);border:1.5px solid var(--blue);border-radius:2px;text-decoration:none}
.whisk s{position:absolute;top:0;width:3px;height:10px;background:var(--ink);text-decoration:none}
ul{margin:6px 0 0;padding-inline-start:20px}.note{background:var(--tint);border-inline-start:3px solid var(--blue);padding:8px 12px;margin:10px 0}
details summary{cursor:pointer;color:var(--blue);font-weight:600}
dl.prov{display:grid;grid-template-columns:max-content 1fr;gap:4px 16px;font-size:12.5px;margin:6px 0}
dl.prov dt{color:var(--muted)}dl.prov dd{margin:0;word-break:break-all}
.foot{color:var(--muted);font-size:12px;margin-top:26px;border-top:1px solid var(--line);padding-top:10px}
.mono{font-family:ui-monospace,Menlo,Consolas,monospace;font-size:12px}
@page{size:A4;margin:14mm 12mm;@bottom-center{content:counter(page);font-size:10px;color:#455d69}}
@media (max-width:600px){main{padding:18px 14px 36px}.kpis{grid-template-columns:1fr}h1{font-size:21px}dl.prov{grid-template-columns:1fr}}
@media print{main{padding:0;max-width:none}.cause,.kpi,.warn,.note{break-inside:avoid}.chartbox{overflow:visible}}
"""


@functools.lru_cache(maxsize=1)
def _arabic_font_css() -> str:
    out = []
    for w in (400, 600, 700):
        path = os.path.join(FONT_DIR, f"ibm-plex-sans-arabic-arabic-{w}-normal.woff2")
        try:
            b64 = base64.b64encode(open(path, "rb").read()).decode()
        except OSError:
            continue
        out.append(f"@font-face{{font-family:'IBM Plex Sans Arabic';font-weight:{w};src:url(data:font/woff2;base64,{b64}) format('woff2')}}")
    return "".join(out)


TIER = {"en": {"likely": "Likely", "possible": "Possible", "weak": "Weak evidence", "unsupported": "Unconfirmed by the data",
               "weak_sig": "Meter data barely shows this cause, so it is never rated more than possible.",
               "ev": "Measured against healthy buildings", "ev_row": "{v} measured; healthy buildings {lo} to {hi}",
               "outside": "outside the healthy range"},
        "ar": {"likely": "مرجّح", "possible": "محتمل", "weak": "دليل ضعيف", "unsupported": "غير مؤكد بالبيانات",
               "weak_sig": "بيانات العدّاد لا تُظهر هذا السبب بوضوح، لذا لا يُصنَّف أعلى من محتمل.",
               "ev": "القياس مقابل المباني السليمة", "ev_row": "المقيس {v}؛ المباني السليمة من {lo} إلى {hi}",
               "outside": "خارج النطاق السليم"}}


def _evidence_html(f: dict, ar: bool) -> str:
    ev, tt = f.get("evidence"), TIER["ar" if ar else "en"]
    if not ev:
        return ""
    rows = []
    for it in ev["items"]:
        lbl = it["label_ar"] if ar else it["label"]
        txt = tt["ev_row"].format(v=f'{it["value"]:.2f}', lo=f'{it["healthy_p5"]:.2f}', hi=f'{it["healthy_p95"]:.2f}')
        flag = f' <b>({tt["outside"]})</b>' if it["outside_healthy"] else ""
        rows.append(f"<li>{escape(lbl)}: {escape(txt)}{flag}</li>")
    weak = f'<p class="sub">{escape(tt["weak_sig"])}</p>' if ev.get("weak_signature") else ""
    return f'<b>{escape(tt["ev"])}</b><ul>' + "".join(rows) + "</ul>" + weak


def confidence(d: dict) -> str:
    """High / Medium / Low / NA for the top finding. Not reliable data gives NA."""
    if not d.get("data_quality", {}).get("reliable", True) or not d.get("findings"):
        return "NA"
    f = d["findings"][0]
    p, lo = f["probability"], f.get("saving_low_aed_per_year")
    if p >= 0.8 and (lo is None or lo > 0):
        return "High"
    return "Medium" if p >= 0.5 else "Low"


def _money(x: float, ar: bool) -> str:
    return f"{x:,.0f} درهم" if ar else f"AED {x:,.0f}"


def _chart(sig: list, min_dt: float, t: dict) -> str:
    if not sig:
        return ""
    W, H, L, B, T = 640, 270, 50, 46, 26
    xs = lambda v: L + (W - L - 12) * v
    ymax = max(14.0, max(p["dt_c"] for p in sig) + 1, min_dt + 1)
    ys = lambda v: T + (H - T - B) * (1 - v / ymax)
    parts = [f'<svg viewBox="0 0 {W} {H}" role="img" aria-label="{escape(t["h_chart"])}" width="100%" direction="ltr" style="direction:ltr">']
    for g in range(0, int(ymax) + 1, 2):
        parts.append(f'<line x1="{L}" x2="{W-12}" y1="{ys(g):.1f}" y2="{ys(g):.1f}" stroke="#dde7eb"/>'
                     f'<text x="{L-7}" y="{ys(g)+4:.1f}" text-anchor="end" font-size="13" fill="#455d69">{g}</text>')
    parts.append(f'<line x1="{L}" x2="{W-12}" y1="{ys(min_dt):.1f}" y2="{ys(min_dt):.1f}" stroke="#a8321f" stroke-width="2" stroke-dasharray="6 4"/>'
                 f'<text x="{W-14}" y="{ys(min_dt)-6:.1f}" text-anchor="end" font-size="13" font-weight="600" fill="#a8321f">{escape(t["minimum"])} {min_dt:.1f} °C</text>')
    pts = " ".join(f"{xs(p['load_pct']/100):.1f},{ys(p['dt_c']):.1f}" for p in sig)
    parts.append(f'<polyline points="{pts}" fill="none" stroke="#1d6f9a" stroke-width="2.5"/>')
    wmax = max(p["flow_share"] for p in sig) or 1.0
    for p in sig:
        r = 3.5 + 8 * (p["flow_share"] / wmax) ** 0.5
        parts.append(f'<circle cx="{xs(p["load_pct"]/100):.1f}" cy="{ys(p["dt_c"]):.1f}" r="{r:.1f}" fill="#1d6f9a" fill-opacity=".3" stroke="#1d6f9a"/>')
    for v in (0, .2, .4, .6, .8, 1.0):
        parts.append(f'<text x="{xs(v):.1f}" y="{H-24}" text-anchor="middle" font-size="13" fill="#455d69">{int(v*100)}%</text>')
    parts.append(f'<text x="{(L+W)/2:.0f}" y="{H-5}" text-anchor="middle" font-size="13" fill="#455d69">{escape(t["x_label"])}</text>')
    parts.append(f'<text x="{L}" y="12" font-size="13" font-weight="600" fill="#0f2b36">{escape(t["y_label"])}</text></svg>')
    return "".join(parts)


def _whisker(f: dict, scale_max: float) -> str:
    lo, hi, mid = f.get("saving_low_aed_per_year"), f.get("saving_high_aed_per_year"), f["expected_saving_aed_per_year"]
    if lo is None or hi is None or scale_max <= 0:
        return ""
    pct = lambda v: 100 * min(max(v / scale_max, 0.0), 1.0)
    return (f'<div class="whisk" aria-hidden="true"><u style="left:{pct(lo):.1f}%;width:{max(pct(hi)-pct(lo), 0.8):.1f}%"></u>'
            f'<s style="left:{pct(mid):.1f}%"></s></div>')


def render_report(d: dict, building_name: str = "Building", lang: str = "en") -> str:
    """d is Report.to_dict(), optionally with 'provenance' and 'is_demo'."""
    lang = "ar" if lang == "ar" else "en"
    t, ar = S[lang], lang == "ar"
    e = escape
    prov = d.get("provenance", {}) or {}
    dq = d.get("data_quality", {})
    reliable = bool(dq.get("reliable", True))
    short = max(d["min_delta_t_c"] - d["delta_t_c"], 0.0)
    findings = d["findings"]
    top = findings[0] if findings else None
    rid = prov.get("report_id", "")
    name = e(building_name)

    if ar:
        head = (f'{name}: يعيد <b>{d["delta_t_c"]:.1f} °م</b>، '
                + (f'<span class="gap">{short:.1f} °م دون</span> الحد الأدنى {d["min_delta_t_c"]:.1f} °م.' if d["below_minimum"]
                   else f'وهو عند الحد الأدنى {d["min_delta_t_c"]:.1f} °م أو أعلى منه.'))
    else:
        head = (f'{name} returns <b>{d["delta_t_c"]:.1f} °C</b>, '
                + (f'<span class="gap">{short:.1f} °C under</span> the {d["min_delta_t_c"]:.1f} °C minimum.' if d["below_minimum"]
                   else f'at or above the {d["min_delta_t_c"]:.1f} °C minimum.'))
    chip = (f'<span class="chip bad">{t["status_below"]} {short:.1f} °{"م" if ar else "C"}</span>' if d["below_minimum"]
            else f'<span class="chip good">{t["status_ok"]}</span>')

    conf = confidence(d)
    kpis = [(_money(d["annual_surcharge_aed_estimate"], ar), t["k_sur"], f'{t["k_sur_basis"]} {d["n_days"]:.0f} {t["days"]}')]
    if top and reliable:
        lo, hi = top.get("saving_low_aed_per_year"), top.get("saving_high_aed_per_year")
        rng = ""
        if lo is not None and hi is not None:
            rng = (f'{t["k_range"]}: {_money(lo, ar)} – {_money(hi, ar)}' if lo > 0.005 * max(hi, 1) else f'{t["k_negl"]}; {t["k_range"]}: 0 – {_money(hi, ar)}')
        kpis.append((_money(top["expected_saving_aed_per_year"], ar), t["k_save"], rng))
        label = top["label_ar"] if ar and top.get("label_ar") else top["label"]
        kpis.append((e(label.split(" (")[0]), t["k_first"], f'{t["k_conf"]}: {t[conf]}'))
    else:
        kpis.append(("–", t["k_save"], t["NA"]))
        kpis.append(("–", t["k_first"], t["NA"]))

    basis = (f'{t["basis_informed"]} {d["design_delta_t_c"]} °{"م" if ar else "C"}' if d.get("mode") == "informed" else t["basis_blind"])
    basis += f' · {t["coverage"]} {dq.get("coverage", 1):.0%} · {d["n_windows"]} {t["window"]}'

    notes = d.get("notes_ar") if ar and d.get("notes_ar") else d.get("notes", [])
    out = [f'<!doctype html><html lang="{lang}" dir="{t["dir"]}"><head><meta charset="utf-8">'
           f'<meta name="viewport" content="width=device-width,initial-scale=1"><title>{e(t["title"])}: {name}</title>'
           f'<style>{_arabic_font_css() if ar else ""}:root{{--font:{t["font"]}}}{CSS}</style></head><body><main>',
           f'<div class="top"><span>delta-t-doctor {__version__}</span><span>{e(t["p_id"])}: <span class="mono">{e(rid) or "–"}</span></span></div>']
    if d.get("is_demo"):
        out.append(f'<div class="demo" role="note">{e(t["demo"])}</div>')
    out.append(f'<h1>{head}</h1><p>{chip}</p>')
    if not reliable:
        out.append(f'<div class="warn" role="alert"><b>{e(t["unreliable_h"])}</b>{e(t["unreliable_b"])}</div>')
    out.append('<div class="kpis">' + "".join(
        f'<div class="kpi"><b>{v}</b><span>{e(l)}</span>' + (f'<small>{e(sm)}</small>' if sm else "") + "</div>" for v, l, sm in kpis) + "</div>")
    out.append(f'<p class="basis">{e(t["basis"])}: {e(basis)}</p><div class="trust">{e(t["not_validated"])}</div>')

    sig = d.get("signature", [])
    out.append(f'<h2>{e(t["h_chart"])}</h2><div class="chartbox">{_chart(sig, d["min_delta_t_c"], t)}</div><p class="sub">{e(t["chart_note"])}</p>')
    if sig:
        out.append(f'<details><summary>{e(t["h_chart"])} – {e(t["t_band"])}</summary><table><tr><th>{e(t["t_band"])}</th><th>{e(t["t_dt"])}</th><th>{e(t["t_share"])}</th></tr>'
                   + "".join(f'<tr><td>{p["load_pct"]:.0f}%</td><td>{p["dt_c"]:.1f}</td><td>{100*p["flow_share"]:.0f}%</td></tr>' for p in sig) + "</table></details>")

    main_f = [f for f in findings if f["probability"] >= 0.05 or f["expected_saving_aed_per_year"] >= 1000]
    minor = [f for f in findings if f not in main_f]
    scale = max([f.get("saving_high_aed_per_year") or f["expected_saving_aed_per_year"] for f in findings] + [1.0])
    out.append(f'<h2>{e(t["h_first"])}</h2>')
    if not reliable or not findings:
        main_f, minor = [], []
        out.append(f'<p class="sub">{e(t["withheld"])}</p>')
    for f in main_f:
        label = f["label_ar"] if ar and f.get("label_ar") else f["label"]
        checks = f["checks_ar"] if ar and f.get("checks_ar") else f["checks"]
        rng = ""
        if f.get("saving_low_aed_per_year") is not None:
            rng = f' · {t["range"]} {_money(f["saving_low_aed_per_year"], ar)} – {_money(f["saving_high_aed_per_year"], ar)}'
        prob = f'{f["probability"]:.0%} {t["likely"]}' if not ar else f'{t["likely"]} {f["probability"]:.0%}'
        out.append(f'<div class="cause"><h3><span>{e(label)}</span><span>{_money(f["expected_saving_aed_per_year"], ar)} {e(t["a_year"])}</span></h3>'
                   f'<div class="bar"><i style="width:{max(f["probability"]*100, 1):.0f}%"></i></div>{_whisker(f, scale)}'
                   f'<div class="sub">{e(prob)}. {e(t["recover"])} {f["expected_dt_gain_c"]:.1f} °{"م" if ar else "C"}{e(rng)}</div>'
                   f'<p class="sub"><b>{e(TIER["ar" if ar else "en"].get(f.get("tier", ""), ""))}</b></p>' + _evidence_html(f, ar) +
                   f'<b>{e(t["check"])}</b><ul>' + "".join(f"<li>{e(c)}</li>" for c in checks) + "</ul></div>")
    if minor:
        names = "؛ ".join((f["label_ar"] if ar and f.get("label_ar") else f["label"]).split(" (")[0] for f in minor) if ar else "; ".join(f["label"].split(" (")[0] for f in minor)
        out.append(f'<h2>{e(t["h_ruled"])}</h2><p class="sub">{e(names)}. {e(t["ruled_note"])}</p>')

    ser = d.get("series") or []
    if len(ser) >= 2:
        out.append(f'<h2>{e(t["h_series"])}</h2><table><tr><th>{e(t["s_start"])}</th><th>{e(t["s_dt"])}</th><th>{e(t["s_hi"])}</th></tr>')
        for w in ser:
            hi = w.get("dt_high_load_c")
            out.append(f'<tr><td>{e(w["start"][:10])}</td><td>{w["dt_c"]:.2f}</td><td>{"-" if hi is None else f"{hi:.2f}"}</td></tr>')
        out.append("</table>")
        tr = d.get("trend") or {}
        if tr.get("significant"):
            dirn = ("ينخفض" if tr["direction"] == "falling" else "يرتفع") if ar else tr["direction"]
            msg = t["trend_sig"].format(direction=dirn, slope="%.2f" % abs(tr["slope_c_per_month"]), p="%.2f" % tr["p_value"])
            out.append(f'<p class="sub">{e(msg)}</p>')

    if d.get("monthly"):
        out.append(f'<h2>{e(t["h_month"])}</h2><table><tr><th>{e(t["m_month"])}</th><th>{e(t["m_dt"])}</th><th>{e(t["m_short"])}</th><th>{e(t["m_sur"])}</th></tr>')
        for m in d["monthly"]:
            out.append(f'<tr><td>{e(str(m.get("month")))}</td><td>{m.get("delta_t_c", float("nan")):.2f}</td>'
                       f'<td>{m.get("shortfall_c", 0):.2f}</td><td>{m.get("surcharge_aed", 0):,.0f}</td></tr>')
        out.append("</table>")
    if notes:
        out.append(f'<h2>{e(t["h_notes"])}</h2>' + "".join(f'<div class="note">{e(n)}</div>' for n in notes))

    tm = d["terms"]
    rate = tm["rate_aed_per_rt_hr"]
    ill = t["illustrative"] if abs(rate - DEFAULT_RATE) < 1e-9 else ""
    out.append(f'<h2>{e(t["h_terms"])}</h2><p class="sub">'
               + e(t["terms"].format(min=tm["min_delta_t_c"], pct=f'{tm["surcharge_pct_per_degree"]:.0%}', rate=rate, ill=ill)) + "</p>")

    # provenance
    inp, win, mod, par = prov.get("input", {}), prov.get("data_window", {}), prov.get("model", {}), prov.get("parameters", {})
    na = t["p_none"]
    rows = [
        (t["p_id"], rid or na), (t["p_time"], prov.get("generated_utc", na)),
        (t["p_file"], inp.get("filename") or na), (t["p_sha"], inp.get("sha256") or na),
        (t["p_window"], f'{(win.get("start") or "")[:10]} → {(win.get("end") or "")[:10]}' if win.get("start") else na),
        (t["p_rows"], f'{inp.get("rows_read")}' if inp.get("rows_read") is not None else na),
        (t["p_dropped"], f'{(inp.get("dropped_fraction") or 0):.1%}'),
        (t["p_model"], f'{mod.get("file", na)} · sha256 {mod.get("sha256", na)}… · {mod.get("training_data", na)}'),
        (t["p_trained"], f'{mod.get("trained_on_windows", na)} {t["windows"]} / {mod.get("trained_on_buildings", na)} {t["buildings"]}, git {mod.get("git_commit_at_training") or na}, scikit-learn {mod.get("sklearn_version") or na}'),
        (t["p_params"], ", ".join(f"{k}={v}" for k, v in par.items())),
        (t["p_quality"], (t["p_rel_yes"] if reliable else t["p_rel_no"]) + f' ({dq.get("features_out_of_range", "–")} / {dq.get("out_of_range_limit", "–")} {t["p_ood"]})'),
        (t["p_sw"], f'delta-t-doctor {prov.get("software_version", __version__)}'),
    ]
    out.append(f'<h2>{e(t["h_prov"])}</h2><p class="sub">{e(t["prov_note"])}</p><dl class="prov">'
               + "".join(f'<dt>{e(str(k))}</dt><dd class="mono" dir="ltr" style="text-align:start">{e(str(v))}</dd>' for k, v in rows) + "</dl>")
    disc = d.get("disclaimer_ar") if ar and d.get("disclaimer_ar") else d.get("disclaimer", "")
    out.append(f'<p class="foot">{e(disc)}</p></main></body></html>')
    return "".join(out)
