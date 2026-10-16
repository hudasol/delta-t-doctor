"""Optional temporal features from the hourly flow series (an experiment; see docs/WORLD_D.md, section T2.4).

The 42 shape features in features.py describe how flow and delta-T depend on load, but not how flow moves from one hour to the next.
A valve that hunts, or a loop that is pushed by excess pressure, could leave a trace in that hour to hour movement. These features
remove the load driven part of the flow (the median flow in the same load band) and describe what is left:

* tf_resid_acf1      lag 1 autocorrelation of the flow residual (a persistent offset gives values near 1, fast oscillation near or below 0)
* tf_resid_acf2      lag 2 autocorrelation of the flow residual
* tf_resid_rel_std   spread of the residual relative to typical flow
* tf_sign_change     share of consecutive running hours where the residual's first difference changes sign
* tf_lowload_cv      coefficient of variation of hour to hour flow changes at low load (below 30% of peak heat)
* tf_hf_ratio        mean absolute hour to hour flow change over the flow standard deviation

They were written before any world D data existed and are not used by the shipped model.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

TEMPORAL_NAMES = ["tf_resid_acf1", "tf_resid_acf2", "tf_resid_rel_std", "tf_sign_change", "tf_lowload_cv", "tf_hf_ratio"]
_EDGES = np.array([0.0, 0.10, 0.20, 0.30, 0.45, 0.60, 0.75, 0.90, 10.0])


def _acf(r: np.ndarray, lag: int) -> float:
    a, b = r[:-lag], r[lag:]
    ok = np.isfinite(a) & np.isfinite(b)
    if ok.sum() < 20 or np.std(a[ok]) < 1e-12 or np.std(b[ok]) < 1e-12:
        return 0.0
    return float(np.corrcoef(a[ok], b[ok])[0, 1])


def extract_temporal(h: pd.DataFrame) -> dict:
    """h: canonical hourly frame from io.canonicalise(). Missing hours stay missing (they are not interpolated)."""
    h = h.set_index("timestamp").asfreq("h").reset_index()
    flow = h["flow_kgs"].to_numpy(float)
    heat = h["heat_kw"].to_numpy(float)
    q98 = max(float(np.nanpercentile(heat, 98)) if np.isfinite(heat).any() else 1.0, 1e-6)
    lf = np.clip(heat / q98, 0, 10)
    f95 = max(float(np.nanpercentile(flow, 95)) if np.isfinite(flow).any() else 1.0, 1e-9)
    y = flow / f95
    running = np.isfinite(y) & (y > 1e-6) & np.isfinite(lf)
    resid = np.full(len(y), np.nan)
    band = np.digitize(lf, _EDGES) - 1
    for b in range(len(_EDGES) - 1):
        sel = running & (band == b)
        if sel.sum() >= 3:
            resid[sel] = y[sel] - np.median(y[sel])
    out = {n: 0.0 for n in TEMPORAL_NAMES}
    ok = np.isfinite(resid)
    if ok.sum() < 48:
        return out
    out["tf_resid_acf1"] = _acf(resid, 1)
    out["tf_resid_acf2"] = _acf(resid, 2)
    out["tf_resid_rel_std"] = float(np.nanstd(resid) / max(np.nanmean(y[running]), 1e-9))
    d = np.diff(resid)
    s = np.sign(d)
    both = np.isfinite(s[:-1]) & np.isfinite(s[1:]) & (s[:-1] != 0) & (s[1:] != 0)
    out["tf_sign_change"] = float((s[:-1][both] != s[1:][both]).mean()) if both.sum() >= 20 else 0.0
    dy = np.diff(y)
    low = running[1:] & running[:-1] & (lf[1:] < 0.3) & np.isfinite(dy)
    out["tf_lowload_cv"] = float(np.std(dy[low]) / max(np.mean(y[1:][low]), 1e-9)) if low.sum() >= 20 else 0.0
    run2 = running[1:] & running[:-1] & np.isfinite(dy)
    sd = float(np.nanstd(y[running]))
    out["tf_hf_ratio"] = float(np.mean(np.abs(dy[run2])) / sd) if run2.sum() >= 20 and sd > 1e-9 else 0.0
    return out


def temporal_vector(feats: dict) -> np.ndarray:
    return np.nan_to_num(np.array([feats[k] for k in TEMPORAL_NAMES], dtype=float), nan=0.0, posinf=0.0, neginf=0.0)
