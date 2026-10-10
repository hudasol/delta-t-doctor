"""End-to-end diagnosis of a real meter export."""
from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field, asdict

import numpy as np
import pandas as pd

from . import CAUSES, CAUSE_LABELS, CP_KJ_KG_K
from .features import FEATURE_NAMES, augment, extract, to_vector
from .io import DataError, canonicalise
from .models import Diagnoser
from .penalty import saving_interval, ContractTerms, KW_PER_RT, monthly_table, saving_from_gain, window_penalty

WINDOW_DAYS = 30
MIN_WINDOW_DAYS = 14

DEFAULT_MODEL = os.path.join(os.path.dirname(__file__), "assets", "diagnoser.joblib")
INFORMED_MODEL = os.path.join(os.path.dirname(__file__), "assets", "diagnoser_informed.joblib")

CHECKS = {
    "fouling": [
        "Trend coil delta-T against load per AHU (BMS) - fouled coils lose delta-T most at high load.",
        "Inspect and clean coil fins; flush or clean strainers, filters and the ETS plate heat exchanger.",
        "Check water-side fouling on the building loop (dosing, water quality, plate-exchanger pressure drop).",
    ],
    "passing_valves": [
        "Compare each AHU control-valve command with coil delta-T when the AHU is off or the command is near 0%.",
        "Test two-way valves for leak-by and check actuators/linkages; look for cold return pipes on idle coils.",
        "Verify control-valve interlock so valves close when the fan or zone is off.",
    ],
    "constant_flow": [
        "Identify any 3-way valves still in service and convert to 2-way (ideally pressure-independent) valves.",
        "Look for actuators stuck open or in manual/override; check for fixed-position valves.",
        "Confirm the building pumps are variable-speed and following demand.",
    ],
    "overflow": [
        "Review secondary differential-pressure setpoint and pump curve; reduce excess pressure.",
        "Check valve sizing and authority; look for hunting valves and unbalanced branches.",
        "Consider pressure-independent control valves with a delta-T limiting function.",
    ],
}

DOMAIN_MIN_DT_C = 3.0   # revisited after v0.2 training; see docs/EXTERNAL_CHECK.md

AMBIGUITY_NOTE = (
    "From meter data alone, constant-flow coils and leaking/passing valves can look alike "
    "(both keep water moving when load is low). Treat these two as a pair to inspect together."
)

DISCLAIMER = (
    "Statistical diagnosis from ETS meter data. It ranks likely causes to inspect first; it does not "
    "replace a site survey. Trained and tested on simulated buildings only; it has not been "
    "validated on UAE field data."
)


@dataclass
class CauseFinding:
    cause: str
    label: str
    probability: float
    expected_dt_gain_c: float
    expected_saving_aed_per_year: float
    checks: list
    saving_low_aed_per_year: float | None = None     # 10th percentile
    saving_high_aed_per_year: float | None = None    # 90th percentile
    dt_gain_low_c: float | None = None
    dt_gain_high_c: float | None = None


@dataclass
class Report:
    n_days: float
    n_windows: int
    delta_t_c: float
    min_delta_t_c: float
    below_minimum: bool
    annual_surcharge_aed_estimate: float
    p_any_cause: float
    findings: list
    monthly: list
    notes: list
    terms: dict
    data_quality: dict
    signature: list = field(default_factory=list)
    mode: str = "blind"                      # "informed" when a design delta-T was supplied
    design_delta_t_c: float | None = None
    disclaimer: str = DISCLAIMER

    def to_dict(self) -> dict:
        d = asdict(self)
        return d


log = logging.getLogger(__name__)
_cached: dict = {}
_ASSETS = os.path.join(os.path.dirname(__file__), "assets")


def _load_verified(path: str) -> Diagnoser:
    """Load a model. A bundled file must match the sha256 in the model card (fail closed) and the sklearn minor
    version it was trained with. The bytes that are hashed are the bytes that are unpickled.

    This is integrity, not authenticity: whoever can rewrite both the model and its card can still swap the model.
    Verify release artefacts out of band (see docs/SECURITY.md) and never point DTD at a model you did not build.
    """
    import hashlib
    import io as _io
    import json
    import warnings
    with open(path, "rb") as fh:
        blob = fh.read()
    if os.path.dirname(os.path.abspath(path)) == os.path.abspath(_ASSETS):
        card_path = os.path.join(_ASSETS, "model_card.json")
        try:
            card = json.load(open(card_path))
            want = card["sha256"][os.path.basename(path)]
        except (OSError, KeyError, ValueError):
            raise RuntimeError("No recorded sha256 for the bundled model; refusing to load it. Rebuild with scripts/train.py.") from None
        if hashlib.sha256(blob).hexdigest() != want:
            raise RuntimeError(f"{os.path.basename(path)} does not match its recorded sha256; refusing to load it.")
        import sklearn
        trained = str(card.get("sklearn_version", ""))
        if trained.split(".")[:2] != sklearn.__version__.split(".")[:2] and not os.environ.get("DTD_ALLOW_SKLEARN_MISMATCH"):
            raise RuntimeError(f"The model was trained with scikit-learn {trained} but {sklearn.__version__} is installed. "
                               f"Install the pinned version (requirements-lock.txt) or retrain.")
    else:
        log.warning("loading a model from outside the package assets: %s (not verified)", path)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        import joblib
        return joblib.load(_io.BytesIO(blob))


def load_default_model(path: str | None = None, informed: bool = False) -> Diagnoser:
    path = path or (INFORMED_MODEL if informed else DEFAULT_MODEL)
    if path not in _cached:
        if not os.path.exists(path):
            raise FileNotFoundError(
                f"No trained model at {path}. Run `python scripts/train.py` first.")
        _cached[path] = _load_verified(path)
    return _cached[path]


MIN_COVERAGE = 0.80          # share of hours in a window that must have data
MAX_WINDOW_DAYS = 45
DESIGN_DT_RANGE = (4.0, 14.0)   # training covers about 4.5-13.5 C; outside this the informed model would extrapolate


def _windows(h: pd.DataFrame):
    """Split into near-equal windows of 20-45 days (30 where possible), keeping only well-covered ones.

    The model was trained on dense 30-day windows, so a window is kept only if at least 80% of its hours have data.
    """
    ts = pd.DatetimeIndex(h["timestamp"])
    start = ts.min().normalize()
    end = ts.max() + pd.Timedelta(hours=1)
    total_days = (end - start).total_seconds() / 86400.0
    n = max(int(round(total_days / WINDOW_DAYS)), 1)
    while n > 1 and total_days / n < 20:
        n -= 1
    while total_days / n > MAX_WINDOW_DAYS:
        n += 1
    step = (end - start) / n
    wins = []
    for i in range(n):
        lo, hi = start + step * i, start + step * (i + 1)
        w = h[(h["timestamp"] >= lo) & (h["timestamp"] < hi)]
        span_h = (hi - lo).total_seconds() / 3600.0
        if len(w) >= MIN_WINDOW_DAYS * 24 and len(w) / span_h >= MIN_COVERAGE:
            wins.append(w.reset_index(drop=True))
    return wins


def _signature(h: pd.DataFrame) -> list:
    """Flow-weighted delta-T by load band, for plotting: [{load_pct, dt_c, hours, flow_share}]."""
    heat = h["heat_kw"].to_numpy(float)
    flow = h["flow_kgs"].to_numpy(float)
    q98 = max(np.nanpercentile(heat, 98), 1e-6)
    lf = np.clip(heat / q98, 0, 1.2)
    edges = np.array([0, 0.1, 0.2, 0.3, 0.45, 0.6, 0.75, 0.9, 1.3])
    tot = max(flow.sum(), 1e-9)
    rows = []
    for lo, hi in zip(edges[:-1], edges[1:]):
        sel = (flow > 1e-6) & (lf >= lo) & (lf < hi)
        if sel.sum() < 3:
            continue
        dt = float(heat[sel].sum() / (CP_KJ_KG_K * flow[sel].sum()))
        rows.append({"load_pct": float(100 * (lo + min(hi, 1.1)) / 2), "dt_c": dt,
                     "hours": int(sel.sum()), "flow_share": float(flow[sel].sum() / tot)})
    return rows


def diagnose_frame(df: pd.DataFrame, terms: ContractTerms | None = None,
                   model: Diagnoser | None = None,
                   design_delta_t_c: float | None = None) -> Report:
    """Diagnose a meter export.

    If ``design_delta_t_c`` (the delta-T the building's loop was designed for) is given, the *informed*
    model is used: it separates "this building was never designed to return warm water" from "something is
    wrong". Without it the blind model assumes a design delta-T anywhere in 5-12 C and is less certain.
    """
    terms = terms or ContractTerms()
    informed = design_delta_t_c is not None
    if informed and not (DESIGN_DT_RANGE[0] <= design_delta_t_c <= DESIGN_DT_RANGE[1]):
        raise DataError(f"Design delta-T must be between {DESIGN_DT_RANGE[0]:.0f} and {DESIGN_DT_RANGE[1]:.0f} C "
                        f"(the range the model was trained on).")
    model = model or load_default_model(informed=informed)
    h = canonicalise(df)
    q_in = dict(h.attrs.get("quality", {}))
    in_notes = list(h.attrs.get("notes", []))
    wins = _windows(h)
    if not wins:
        raise DataError("Not enough contiguous data to form a 14-day analysis window.")

    X = np.vstack([to_vector(extract(w)) for w in wins])
    if informed:
        X = augment(X, design_delta_t_c)
    pred = model.predict(X)
    ood = getattr(model, "ood_count", None)
    n_ood = float(np.average(ood(X), weights=[len(w) for w in wins])) if ood else 0.0
    ood_limit = getattr(model, "ood_threshold", None)

    # per-window energy, delta-T
    rt_hr = np.array([w["heat_kw"].sum() / KW_PER_RT for w in wins])
    dts = np.array([w["heat_kw"].sum() / (CP_KJ_KG_K * max(w["flow_kgs"].sum(), 1e-9)) for w in wins])
    days = np.array([len(w) / 24.0 for w in wins])
    scale = 365.0 / days.sum()

    findings = []
    for k, c in enumerate(CAUSES):
        p = float(np.average(pred.prob[:, k], weights=days))
        gain = float(np.average(pred.gain[:, k], weights=days))
        if pred.gain_q is not None:
            parts = [saving_interval(dts[i], pred.gain_q[i, k], rt_hr[i], terms) for i in range(len(wins))]
            sav = sum(x[0] for x in parts) * scale
            lo, hi = sum(x[1] for x in parts) * scale, sum(x[2] for x in parts) * scale   # windows move together: a wide, safe interval
            g_lo = float(np.average(pred.gain_q[:, k, 0], weights=days))
            g_hi = float(np.average(pred.gain_q[:, k, -1], weights=days))
            findings.append(CauseFinding(c, CAUSE_LABELS[c], p, gain, float(sav), CHECKS[c], float(lo), float(hi), g_lo, g_hi))
        else:
            sav = sum(saving_from_gain(dts[i], pred.gain[i, k], rt_hr[i], terms) for i in range(len(wins))) * scale
            findings.append(CauseFinding(c, CAUSE_LABELS[c], p, gain, float(sav), CHECKS[c]))
    findings.sort(key=lambda f: (f.expected_saving_aed_per_year, f.probability), reverse=True)

    mt = monthly_table(h, terms)
    annual_sur = float(sum(window_penalty(dts[i], rt_hr[i], terms)["surcharge_aed"] for i in range(len(wins))) * scale)
    dt_all = float(h["heat_kw"].sum() / (CP_KJ_KG_K * max(h["flow_kgs"].sum(), 1e-9)))

    notes = list(in_notes)
    has_oat = bool(h["t_outdoor_c"].notna().mean() > 0.5)
    if not has_oat:
        notes.append("No outdoor temperature supplied; diagnosis is less certain (add t_outdoor_c).")
    if len(findings) > 1 and findings[0].saving_low_aed_per_year is not None:
        a, b = findings[0], findings[1]
        if b.saving_high_aed_per_year > a.saving_low_aed_per_year and b.expected_saving_aed_per_year > 0.5 * a.expected_saving_aed_per_year:
            notes.append(f"The order of the top two fixes is uncertain: the ranges for '{a.label.split(' (')[0]}' and "
                         f"'{b.label.split(' (')[0]}' overlap. Check both.")
    top2 = {f.cause for f in findings[:2] if f.probability > 0.4}
    if {"passing_valves", "constant_flow"} <= top2:
        notes.append(AMBIGUITY_NOTE)
    if len(wins) == 1 and days.sum() < 25:
        notes.append("Under 25 days of data; use 30+ days (ideally a full year) for a firmer diagnosis.")
    if dt_all >= terms.min_delta_t_c:
        notes.append("Delta-T is at or above the contract minimum over this period; no surcharge exposure "
                     "expected, but listed causes may still cost energy.")

    out_of_range = ood_limit is not None and n_ood > ood_limit
    if out_of_range:
        notes.append(
            f"This building's behaviour is unlike anything the model was trained on ({n_ood:.0f} of "
            f"{len(FEATURE_NAMES)} shape measurements are outside the training range; a normal building "
            f"shows {ood_limit} or fewer). The ranking below is NOT reliable. Typical reasons: variable "
            f"flow that does not follow load, a plant-side loop rather than a building ETS, or a different system type.")
    if dt_all < DOMAIN_MIN_DT_C and not informed:
        notes.append(
            f"Average delta-T ({dt_all:.1f} C) is below the range the model was trained on. If this building "
            f"was designed for a low delta-T, the ranking will be overconfident: a design shortfall looks like "
            f"fouling. Enter the design delta-T to get an informed diagnosis.")
    elif not informed:
        notes.append("No design delta-T supplied. If you know it, enter it: the diagnosis separates a design "
                     "shortfall from a fault and is more reliable.")
    span_h = max((h["timestamp"].iloc[-1] - h["timestamp"].iloc[0]).total_seconds() / 3600.0, 1.0)
    coverage = float(min(len(h) / (span_h + 1.0), 1.0))
    if coverage < 0.85:
        notes.append(f"Only {coverage:.0%} of the hours between the first and last reading have data. "
                     f"Gaps weaken the diagnosis; check the export for missing periods.")
    if days.sum() < 330:
        notes.append(f"The yearly figures are scaled up from {days.sum():.0f} days of data. Cooling demand is seasonal, "
                     f"so a summer-only file overstates and a winter-only file understates the year.")
    if float(np.nanstd(h["flow_kgs"])) < 1e-6:
        notes.append("Flow never changes in this file. Check that the flow column is the real meter reading.")
    signature = _signature(h)
    quality = {
        "coverage": coverage,
        "hours": int(len(h)), "has_outdoor_temp": has_oat,
        "zero_flow_fraction": float((h["flow_kgs"] <= 1e-6).mean()),
        "windows": len(wins), "features_out_of_range": n_ood, "out_of_range_limit": ood_limit,
        "reliable": bool(not out_of_range and q_in.get("dropped_fraction", 0) < 0.05
                         and q_in.get("negative_dt_fraction", 0) < 0.02 and coverage >= MIN_COVERAGE
                         and q_in.get("outlier_fraction", 0) < 0.02 and q_in.get("bad_timestamp_fraction", 0) < 0.02
                         and q_in.get("longest_flatline_readings", 0) < 48),
        "input": q_in, "annualised_from_days": float(days.sum()),
    }
    return Report(
        n_days=float(days.sum()), n_windows=len(wins), delta_t_c=dt_all,
        min_delta_t_c=terms.min_delta_t_c, below_minimum=bool(dt_all < terms.min_delta_t_c),
        annual_surcharge_aed_estimate=annual_sur, p_any_cause=float(np.average(pred.p_any, weights=days)),
        findings=[asdict(f) for f in findings], monthly=mt.to_dict(orient="records"),
        notes=notes, terms=terms.to_dict(), data_quality=quality, signature=signature,
        mode="informed" if informed else "blind", design_delta_t_c=design_delta_t_c,
    )


def diagnose_csv(path: str, terms: ContractTerms | None = None, model: Diagnoser | None = None,
                 design_delta_t_c: float | None = None) -> Report:
    from .io import read_table
    with open(path, "rb") as fh:
        return diagnose_frame(read_table(fh.read(), path), terms, model, design_delta_t_c)
