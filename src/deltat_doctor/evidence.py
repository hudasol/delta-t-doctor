"""Evidence a sceptical engineer can check: which measured features support each cause, against healthy buildings.

At training time, for each cause, the shape features whose median moves the most (in units of healthy spread) on windows where
only that cause is present are recorded with their direction (``Diagnoser.evidence_spec``). A report states the measured value
next to the healthy range (5th to 95th percentile). A cause the model likes but whose features do not move is marked
``unsupported``. A cause with a weak signature overall (largest effect under 1.5 healthy spreads) is marked ``weak_signature``
instead and is never called unsupported: meter data barely distinguishes it. This is a physics-consistency flag on simulated
signatures, not proof in either direction.
"""
from __future__ import annotations

import numpy as np

from .features import FEATURE_NAMES, LF_EDGES

WEAK_SIGNATURE = 1.5

_FIXED = {
    "dt_period": ("Delta-T over the period", "فرق درجة الحرارة خلال الفترة", "°C"),
    "dt_p10": ("Delta-T on the worst 10% of hours", "فرق درجة الحرارة في أسوأ 10% من الساعات", "°C"),
    "dt_p90": ("Delta-T on the best 10% of hours", "فرق درجة الحرارة في أفضل 10% من الساعات", "°C"),
    "dt_std_loaded": ("Spread of delta-T while loaded", "تشتّت فرق درجة الحرارة أثناء الحمل", "°C"),
    "zero_flow_frac": ("Share of hours with no flow", "حصة الساعات بلا تدفق", ""),
    "flow_lowload_share": ("Share of water used at under 10% load", "حصة الماء المستهلك عند حمل أقل من 10%", ""),
    "dt_lowload": ("Delta-T at low load", "فرق درجة الحرارة عند الحمل المنخفض", "°C"),
    "flow_intercept_ratio": ("Flow that remains at zero load", "التدفق المتبقي عند حمل صفر", ""),
    "flow_load_corr": ("How closely flow follows load", "مدى تتبع التدفق للحمل", ""),
    "flow_cv_loaded": ("Flow variation while loaded", "تغيّر التدفق أثناء الحمل", ""),
    "dt_night_minus_day": ("Delta-T at night minus day", "فرق درجة الحرارة ليلاً ناقص نهاراً", "°C"),
    "dt_weekend_minus_week": ("Delta-T at weekends minus weekdays", "فرق درجة الحرارة في العطلة ناقص أيام العمل", "°C"),
    "dt_hi_minus_mid": ("Delta-T at high load minus mid load", "فرق درجة الحرارة عند الحمل العالي ناقص المتوسط", "°C"),
    "dt_vs_oat_slope": ("How delta-T changes with outdoor temperature", "تغيّر فرق درجة الحرارة مع الحرارة الخارجية", "°C per °C"),
    "duty_factor": ("Share of hours running", "حصة ساعات التشغيل", ""),
    "flow_p10_over_p95": ("Lowest flows relative to peak flow", "أدنى تدفق نسبةً إلى التدفق الأقصى", ""),
    "flow_p50_over_p95": ("Typical flow relative to peak flow", "التدفق المعتاد نسبةً إلى الأقصى", ""),
    "load_p10_over_p98": ("Lowest loads relative to peak load", "أدنى حمل نسبةً إلى الحمل الأقصى", ""),
}


def _band(i: int) -> str:
    lo, hi = int(round(100 * LF_EDGES[i])), int(round(100 * min(LF_EDGES[i + 1], 1.0)))
    return f"{lo}-{hi}%" if LF_EDGES[i + 1] < 5 else f"over {lo}%"


def describe(name: str):
    """(English label, Arabic label, unit) for a feature name."""
    if name in _FIXED:
        return _FIXED[name]
    kind, i = name.rsplit("bin", 1)[0], int(name.rsplit("bin", 1)[1])
    b = _band(i)
    b_ar = b.replace("over ", "أكثر من ")
    if kind == "dt_":
        return f"Delta-T at {b} load", f"فرق درجة الحرارة عند حمل {b_ar}", "°C"
    if kind == "flow_":
        return f"Flow at {b} load, relative to peak", f"التدفق عند حمل {b_ar} نسبةً إلى الأقصى", ""
    return f"Share of hours at {b} load", f"حصة الساعات عند حمل {b_ar}", ""


def build(X: np.ndarray, weights: np.ndarray, healthy_ref: dict, spec: dict) -> dict:
    """X: window feature matrix (blind columns first). Returns {cause: {supported, weak_signature, items}}."""
    if not healthy_ref or not spec:
        return {}
    x = np.average(np.atleast_2d(X)[:, :len(FEATURE_NAMES)], axis=0, weights=weights)
    ix = {n: i for i, n in enumerate(FEATURE_NAMES)}
    out = {}
    for cause, sp in spec.items():
        items, n_out = [], 0
        for feat, sign, effect in sp["features"]:
            lo, med, hi = healthy_ref[feat][0], healthy_ref[feat][2], healthy_ref[feat][4]
            v = float(x[ix[feat]])
            beyond = (v > hi) if sign > 0 else (v < lo)
            n_out += int(beyond)
            en, ar, unit = describe(feat)
            items.append({"feature": feat, "label": en, "label_ar": ar, "unit": unit, "value": v,
                          "healthy_p5": lo, "healthy_median": med, "healthy_p95": hi,
                          "expected": "higher" if sign > 0 else "lower", "outside_healthy": bool(beyond)})
        out[cause] = {"supported": n_out >= 1, "n_outside": n_out, "weak_signature": sp["strength"] < WEAK_SIGNATURE, "items": items}
    return out
