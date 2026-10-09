"""End-to-end diagnosis of a real meter export."""
from __future__ import annotations

import os
from dataclasses import dataclass, field, asdict

import numpy as np
import pandas as pd

from . import CAUSES, CAUSE_LABELS
from .features import extract, to_vector
from .io import DataError, canonicalise
from .models import Diagnoser
from .penalty import ContractTerms, KW_PER_RT, monthly_table, saving_from_gain, window_penalty

WINDOW_DAYS = 30
MIN_WINDOW_DAYS = 14

DEFAULT_MODEL = os.path.join(os.path.dirname(__file__), "assets", "diagnoser.joblib")

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

DOMAIN_MIN_DT_C = 4.0

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
    disclaimer: str = DISCLAIMER

    def to_dict(self) -> dict:
        d = asdict(self)
        return d


_cached: dict = {}


def load_default_model(path: str | None = None) -> Diagnoser:
    path = path or DEFAULT_MODEL
    if path not in _cached:
        if not os.path.exists(path):
            raise FileNotFoundError(
                f"No trained model at {path}. Run `python scripts/train.py` first.")
        _cached[path] = Diagnoser.load(path)
    return _cached[path]


def _windows(h: pd.DataFrame):
    ts = pd.DatetimeIndex(h["timestamp"])
    start = ts.min().normalize()
    end = ts.max()
    total_days = (end - start).total_seconds() / 86400.0
    n = max(int(total_days // WINDOW_DAYS), 1)
    edges = [start + pd.Timedelta(days=WINDOW_DAYS * i) for i in range(n)] + [end + pd.Timedelta(hours=1)]
    wins = []
    for i in range(n):
        lo, hi = edges[i], edges[i + 1]
        if i == n - 1:
            hi = end + pd.Timedelta(hours=1)  # last window absorbs the remainder
        w = h[(h["timestamp"] >= lo) & (h["timestamp"] < hi)]
        if len(w) >= MIN_WINDOW_DAYS * 24 * 0.6:
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
        dt = float(heat[sel].sum() / (4.186 * flow[sel].sum()))
        rows.append({"load_pct": float(100 * (lo + min(hi, 1.1)) / 2), "dt_c": dt,
                     "hours": int(sel.sum()), "flow_share": float(flow[sel].sum() / tot)})
    return rows


def diagnose_frame(df: pd.DataFrame, terms: ContractTerms | None = None,
                   model: Diagnoser | None = None) -> Report:
    terms = terms or ContractTerms()
    model = model or load_default_model()
    h = canonicalise(df)
    wins = _windows(h)
    if not wins:
        raise DataError("Not enough contiguous data to form a 14-day analysis window.")

    X = np.vstack([to_vector(extract(w)) for w in wins])
    pred = model.predict(X)

    # per-window energy, delta-T
    rt_hr = np.array([w["heat_kw"].sum() / KW_PER_RT for w in wins])
    dts = np.array([w["heat_kw"].sum() / (4.186 * max(w["flow_kgs"].sum(), 1e-9)) for w in wins])
    days = np.array([len(w) / 24.0 for w in wins])
    scale = 365.0 / days.sum()

    findings = []
    for k, c in enumerate(CAUSES):
        p = float(np.average(pred.prob[:, k], weights=days))
        gain = float(np.average(pred.gain[:, k], weights=days))
        sav = sum(saving_from_gain(dts[i], pred.gain[i, k], rt_hr[i], terms) for i in range(len(wins))) * scale
        findings.append(CauseFinding(c, CAUSE_LABELS[c], p, gain, float(sav), CHECKS[c]))
    findings.sort(key=lambda f: (f.expected_saving_aed_per_year, f.probability), reverse=True)

    mt = monthly_table(h, terms)
    annual_sur = float(sum(window_penalty(dts[i], rt_hr[i], terms)["surcharge_aed"] for i in range(len(wins))) * scale)
    dt_all = float(h["heat_kw"].sum() / (4.186 * max(h["flow_kgs"].sum(), 1e-9)))

    notes = []
    has_oat = bool(h["t_outdoor_c"].notna().mean() > 0.5)
    if not has_oat:
        notes.append("No outdoor temperature supplied; diagnosis is less certain (add t_outdoor_c).")
    top2 = {f.cause for f in findings[:2] if f.probability > 0.4}
    if {"passing_valves", "constant_flow"} <= top2:
        notes.append(AMBIGUITY_NOTE)
    if len(wins) == 1 and days.sum() < 25:
        notes.append("Under 25 days of data; use 30+ days (ideally a full year) for a firmer diagnosis.")
    if dt_all >= terms.min_delta_t_c:
        notes.append("Delta-T is at or above the contract minimum over this period; no surcharge exposure "
                     "expected, but listed causes may still cost energy.")

    if dt_all < DOMAIN_MIN_DT_C:
        notes.append(
            f"Average delta-T ({dt_all:.1f} C) is below what the model saw in training (building design "
            f"delta-T of 9-13 C). If this plant was designed for a low delta-T, the cause probabilities "
            f"will be overconfident: a design deficit looks like fouling. Treat the ranking as unreliable.")
    signature = _signature(h)
    quality = {
        "hours": int(len(h)), "has_outdoor_temp": has_oat,
        "zero_flow_fraction": float((h["flow_kgs"] <= 1e-6).mean()),
        "windows": len(wins),
    }
    return Report(
        n_days=float(days.sum()), n_windows=len(wins), delta_t_c=dt_all,
        min_delta_t_c=terms.min_delta_t_c, below_minimum=bool(dt_all < terms.min_delta_t_c),
        annual_surcharge_aed_estimate=annual_sur, p_any_cause=float(np.average(pred.p_any, weights=days)),
        findings=[asdict(f) for f in findings], monthly=mt.to_dict(orient="records"),
        notes=notes, terms=terms.to_dict(), data_quality=quality, signature=signature,
    )


def diagnose_csv(path: str, terms: ContractTerms | None = None, model: Diagnoser | None = None) -> Report:
    return diagnose_frame(pd.read_csv(path), terms, model)
