"""Feature extraction from an hourly ETS frame (flow, heat, delta-T, outdoor temp).

Features describe the *shape* of the building's behaviour (delta-T versus load,
flow at low load, flow-versus-load slope, time-of-day structure) rather than
absolute size, so they transfer across buildings of different capacity.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from . import CP_KJ_KG_K

LF_EDGES = np.array([0.0, 0.10, 0.20, 0.30, 0.45, 0.60, 0.75, 0.90, 10.0])
N_BINS = len(LF_EDGES) - 1


def _wavg_dt(heat: np.ndarray, flow: np.ndarray) -> float:
    f = flow.sum()
    return float(heat.sum() / (CP_KJ_KG_K * f)) if f > 1e-9 else np.nan


def feature_names() -> list[str]:
    names = ["dt_period", "dt_p10", "dt_p90", "dt_std_loaded", "zero_flow_frac",
             "flow_lowload_share", "dt_lowload", "flow_intercept_ratio", "flow_load_corr",
             "flow_cv_loaded", "dt_night_minus_day", "dt_weekend_minus_week",
             "dt_hi_minus_mid", "dt_vs_oat_slope", "duty_factor", "flow_p10_over_p95",
             "flow_p50_over_p95", "load_p10_over_p98"]
    names += [f"dt_bin{i}" for i in range(N_BINS)]
    names += [f"flow_bin{i}" for i in range(N_BINS)]
    names += [f"frac_bin{i}" for i in range(N_BINS)]
    return names


FEATURE_NAMES = feature_names()


def extract(h: pd.DataFrame) -> dict:
    """h: canonical hourly frame from io.canonicalise()."""
    flow = h["flow_kgs"].to_numpy(float)
    heat = h["heat_kw"].to_numpy(float)
    dt = h["dt_c"].to_numpy(float)
    oat = h["t_outdoor_c"].to_numpy(float)
    ts = pd.DatetimeIndex(h["timestamp"])

    q98 = np.nanpercentile(heat, 98) if np.nanmax(heat) > 0 else 1.0
    q98 = max(q98, 1e-6)
    lf = np.clip(heat / q98, 0, 10)
    f95 = max(np.nanpercentile(flow, 95), 1e-9)
    running = flow > 1e-6

    feats: dict[str, float] = {}
    feats["dt_period"] = _wavg_dt(heat, flow)
    dt_run = dt[running & np.isfinite(dt)]
    feats["dt_p10"] = float(np.percentile(dt_run, 10)) if len(dt_run) else 0.0
    feats["dt_p90"] = float(np.percentile(dt_run, 90)) if len(dt_run) else 0.0
    loaded = running & (lf > 0.3) & np.isfinite(dt)
    feats["dt_std_loaded"] = float(np.std(dt[loaded])) if loaded.sum() > 5 else 0.0
    feats["zero_flow_frac"] = float(1.0 - running.mean())

    low = lf < 0.10
    tot_flow = flow.sum()
    feats["flow_lowload_share"] = float(flow[low].sum() / tot_flow) if tot_flow > 0 else 0.0
    feats["dt_lowload"] = _wavg_dt(heat[low], flow[low]) if flow[low].sum() > 1e-9 else 0.0

    # flow vs load: robust linear fit on running hours
    if running.sum() > 20:
        x, y = lf[running], flow[running] / f95
        feats["flow_load_corr"] = float(np.corrcoef(x, y)[0, 1]) if np.std(x) > 1e-9 and np.std(y) > 1e-9 else 0.0
        # binned medians -> intercept at zero load
        order = np.argsort(x)
        k = max(len(x) // 6, 5)
        lo_idx = order[:k]
        feats["flow_intercept_ratio"] = float(np.median(y[lo_idx]))
        feats["flow_cv_loaded"] = float(np.std(flow[loaded]) / max(np.mean(flow[loaded]), 1e-9)) if loaded.sum() > 5 else 0.0
    else:
        feats["flow_load_corr"] = 0.0
        feats["flow_intercept_ratio"] = 0.0
        feats["flow_cv_loaded"] = 0.0

    hour = ts.hour.values
    night = running & (hour >= 1) & (hour <= 5)
    day = running & (hour >= 12) & (hour <= 16)
    feats["dt_night_minus_day"] = (
        _wavg_dt(heat[night], flow[night]) - _wavg_dt(heat[day], flow[day])
        if night.sum() > 5 and day.sum() > 5 else 0.0)
    wk = ts.dayofweek.values >= 5
    feats["dt_weekend_minus_week"] = (
        _wavg_dt(heat[running & wk], flow[running & wk]) - _wavg_dt(heat[running & ~wk], flow[running & ~wk])
        if (running & wk).sum() > 5 and (running & ~wk).sum() > 5 else 0.0)

    # per-bin stats
    dts, flows, fracs = [], [], []
    for b in range(N_BINS):
        sel = running & (lf >= LF_EDGES[b]) & (lf < LF_EDGES[b + 1])
        fracs.append(sel.mean())
        if sel.sum() >= 3:
            dts.append(_wavg_dt(heat[sel], flow[sel]))
            flows.append(float(np.median(flow[sel]) / f95))
        else:
            dts.append(np.nan)
            flows.append(np.nan)
    dts_arr = np.array(dts, dtype=float)
    fill = np.nanmean(dts_arr) if np.isfinite(dts_arr).any() else 0.0
    dts_f = np.where(np.isfinite(dts_arr), dts_arr, fill)
    flows_arr = np.array(flows, dtype=float)
    flows_f = np.where(np.isfinite(flows_arr), flows_arr, np.nanmean(flows_arr) if np.isfinite(flows_arr).any() else 0.0)
    for b in range(N_BINS):
        feats[f"dt_bin{b}"] = float(dts_f[b])
        feats[f"flow_bin{b}"] = float(flows_f[b])
        feats[f"frac_bin{b}"] = float(fracs[b])

    hi = np.nanmean(dts_f[N_BINS - 2:N_BINS]) if N_BINS >= 2 else 0.0
    mid = np.nanmean(dts_f[3:5])
    feats["dt_hi_minus_mid"] = float(hi - mid)

    ok = running & np.isfinite(oat) & np.isfinite(dt) & (lf > 0.1)
    if ok.sum() > 30 and np.nanstd(oat[ok]) > 0.5:
        feats["dt_vs_oat_slope"] = float(np.polyfit(oat[ok], dt[ok], 1)[0])
    else:
        feats["dt_vs_oat_slope"] = 0.0

    feats["duty_factor"] = float(np.nanmean(lf))
    feats["flow_p10_over_p95"] = float(np.nanpercentile(flow, 10) / f95)
    feats["flow_p50_over_p95"] = float(np.nanpercentile(flow, 50) / f95)
    feats["load_p10_over_p98"] = float(np.nanpercentile(heat, 10) / q98)
    return feats


def to_vector(feats: dict) -> np.ndarray:
    v = np.array([feats[k] for k in FEATURE_NAMES], dtype=float)
    return np.nan_to_num(v, nan=0.0, posinf=0.0, neginf=0.0)


INFORMED_EXTRA = ["design_dt_c", "dt_gap_to_design"]


def augment(X: np.ndarray, design_dt) -> np.ndarray:
    """Add the two 'informed' columns: the design delta-T and the shortfall against it.

    X is (n, len(FEATURE_NAMES)); design_dt is a scalar or (n,) array in deg C.
    """
    X = np.atleast_2d(np.asarray(X, float))
    d = np.broadcast_to(np.asarray(design_dt, float), (len(X),))
    return np.column_stack([X, d, X[:, FEATURE_NAMES.index("dt_period")] - d])
