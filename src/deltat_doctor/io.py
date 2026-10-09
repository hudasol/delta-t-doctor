"""Reading and normalising utility meter exports.

Accepted columns (case-insensitive, common aliases handled):

  timestamp                      required
  flow_m3h  | flow_ls | flow_gpm required (volume flow through the ETS)
  t_supply_c, t_return_c         ...either both temperatures...
  energy_kw | energy_rth | cooling_kw   ...or a thermal power / energy column
  t_outdoor_c                    optional (improves diagnosis)

The result is always the canonical frame used everywhere else: hourly rows with
`flow_kgs`, `heat_kw`, `dt_c`, `t_outdoor_c`.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from .sim.coil import CP_W

_ALIASES = {
    "timestamp": ["timestamp", "time", "datetime", "date", "ts"],
    "flow_m3h": ["flow_m3h", "flow_m3_h", "flow", "volume_flow_m3h"],
    "flow_ls": ["flow_ls", "flow_l_s", "flow_lps"],
    "flow_gpm": ["flow_gpm", "gpm"],
    "t_supply_c": ["t_supply_c", "supply_temp_c", "supply_c", "t_supply", "tsupply"],
    "t_return_c": ["t_return_c", "return_temp_c", "return_c", "t_return", "treturn"],
    "energy_kw": ["energy_kw", "cooling_kw", "power_kw", "load_kw"],
    "energy_rt": ["energy_rt", "cooling_rt", "load_rt", "tons"],
    "t_outdoor_c": ["t_outdoor_c", "oat_c", "outdoor_temp_c", "t_out", "oat"],
}

MIN_HOURS = 14 * 24


class DataError(ValueError):
    pass


def _find(df: pd.DataFrame, key: str):
    low = {c.lower().strip(): c for c in df.columns}
    for a in _ALIASES[key]:
        if a in low:
            return low[a]
    return None


def canonicalise(df: pd.DataFrame, min_hours: int = MIN_HOURS) -> pd.DataFrame:
    """Return an hourly frame with flow_kgs, heat_kw, dt_c, t_outdoor_c."""
    c_ts = _find(df, "timestamp")
    if c_ts is None:
        raise DataError("No timestamp column found (expected e.g. 'timestamp').")
    ts = pd.to_datetime(df[c_ts], errors="coerce")
    if ts.isna().all():
        raise DataError("Could not parse the timestamp column.")
    out = pd.DataFrame({"timestamp": ts})

    c_f = _find(df, "flow_m3h")
    c_fl = _find(df, "flow_ls")
    c_fg = _find(df, "flow_gpm")
    if c_f is not None:
        flow_kgs = pd.to_numeric(df[c_f], errors="coerce") / 3.6
    elif c_fl is not None:
        flow_kgs = pd.to_numeric(df[c_fl], errors="coerce")
    elif c_fg is not None:
        flow_kgs = pd.to_numeric(df[c_fg], errors="coerce") * 0.0630902
    else:
        raise DataError("No flow column found (flow_m3h, flow_ls or flow_gpm).")
    out["flow_kgs"] = flow_kgs.clip(lower=0)

    c_s, c_r = _find(df, "t_supply_c"), _find(df, "t_return_c")
    c_e, c_rt = _find(df, "energy_kw"), _find(df, "energy_rt")
    if c_s is not None and c_r is not None:
        dt = pd.to_numeric(df[c_r], errors="coerce") - pd.to_numeric(df[c_s], errors="coerce")
    elif c_e is not None or c_rt is not None:
        kw = (pd.to_numeric(df[c_e], errors="coerce") if c_e is not None
              else pd.to_numeric(df[c_rt], errors="coerce") * 3.517)
        with np.errstate(divide="ignore", invalid="ignore"):
            dt = kw / (CP_W * out["flow_kgs"].replace(0, np.nan))
    else:
        raise DataError("Need supply+return temperatures, or an energy/power column.")
    out["dt_c"] = dt.clip(lower=0)

    c_o = _find(df, "t_outdoor_c")
    out["t_outdoor_c"] = pd.to_numeric(df[c_o], errors="coerce") if c_o else np.nan

    out = out.dropna(subset=["timestamp"]).sort_values("timestamp")
    out["heat_kw"] = CP_W * out["flow_kgs"] * out["dt_c"].fillna(0.0)
    out = _to_hourly(out)
    if len(out) < min_hours:
        raise DataError(
            f"Need at least {min_hours // 24} days of data ({min_hours} hourly rows); got {len(out)}.")
    return out.reset_index(drop=True)


def _to_hourly(out: pd.DataFrame) -> pd.DataFrame:
    o = out.set_index("timestamp")
    g = o.resample("h")
    flow = g["flow_kgs"].mean()
    heat = g["heat_kw"].mean()
    oat = g["t_outdoor_c"].mean()
    with np.errstate(divide="ignore", invalid="ignore"):
        dt = np.where(flow > 1e-6, heat / (CP_W * flow), np.nan)
    h = pd.DataFrame({"flow_kgs": flow, "heat_kw": heat, "dt_c": dt, "t_outdoor_c": oat})
    h = h.dropna(subset=["flow_kgs"])
    h = h.reset_index()
    return h
