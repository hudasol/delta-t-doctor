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

import io as _io
import re

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


# ---------------------------------------------------------------- reading real exports

def read_table(raw: bytes, filename: str = "upload.csv") -> pd.DataFrame:
    """Read an uploaded export: CSV with any common delimiter or encoding, or an .xlsx sheet."""
    name = (filename or "").lower()
    try:
        if name.endswith((".xlsx", ".xlsm", ".xls")):
            return pd.read_excel(_io.BytesIO(raw))
        for enc in ("utf-8-sig", "utf-16", "latin-1"):
            try:
                text = raw.decode(enc)
                break
            except (UnicodeDecodeError, UnicodeError):
                continue
        df = pd.read_csv(_io.StringIO(text), sep=None, engine="python")
        if df.shape[1] < 2:
            df = pd.read_csv(_io.StringIO(text), sep=";")
        return df
    except ImportError:
        raise DataError("Reading Excel files needs the optional 'openpyxl' package; export the sheet as CSV instead.")
    except Exception:
        raise DataError("Could not read the file as a table. Use a CSV or an Excel sheet with a header row.")


def _split_name(col: str) -> tuple[str, str]:
    """'Supply Temp [degC]' -> ('supply_temp', 'degc'); the unit is whatever sits in brackets."""
    unit = "".join(re.findall(r"[\[(]([^\])]*)[\])]", str(col))).lower()
    base = re.sub(r"[\[(][^\])]*[\])]", " ", str(col)).lower()
    base = re.sub(r"[^a-z0-9]+", "_", base).strip("_")
    return base, re.sub(r"[^a-z0-9/%\u00b0\u00b3]", "", unit)


def harmonise(df: pd.DataFrame) -> pd.DataFrame:
    """Map messy real-world headers and units onto the canonical column names.

    Recognises names like 'CHW Supply Temp (degC)', 'CHWR', 'Flow [m3/h]', 'Cooling Load (kW)', 'Power (RT)',
    'OA Temp (F)'; converts Fahrenheit, MW, RT/TR and l/s or gpm. Columns that already use a canonical name win.
    Cumulative kWh/MWh registers are differenced into kW. Anything not recognised is left untouched.
    """
    out = df.copy()
    have = {c.lower().strip() for c in out.columns}
    canon = {a for al in _ALIASES.values() for a in al}
    used = {c for c in out.columns if c.lower().strip() in canon}

    def claim(key, series):
        if key not in have:
            out[key] = series
            have.add(key)

    for col in list(df.columns):
        if col in used:
            continue
        base, unit = _split_name(col)
        txt = base + "_" + unit
        is_f = bool(re.search(r"(^|[^a-z])(f|degf|\u00b0f|fahrenheit)($|[^a-z])", unit)) and "c" not in unit
        num = lambda: pd.to_numeric(df[col], errors="coerce")
        if re.fullmatch(r"(date_?time|timestamp|time_?stamp|time|date|reading_?(time|date)|ts)", base):
            claim("timestamp", df[col])
        elif "flow" in base and not re.search(r"temp|setpoint|sp$", base):
            if "gpm" in txt:
                claim("flow_gpm", num())
            elif re.search(r"l/s|lps|l_s|ls$", unit) or re.search(r"(^|_)(lps|l_s)($|_)", base):
                claim("flow_ls", num())
            else:
                claim("flow_m3h", num())
        elif re.search(r"(supply|chws|(^|_)sup($|_)|(^|_)st($|_))", base) and re.search(r"temp|t_|chws|degc|\u00b0|^t", base + unit):
            claim("t_supply_c", (num() - 32) * 5 / 9 if is_f else num())
        elif re.search(r"(return|chwr|(^|_)ret($|_)|(^|_)rt($|_))", base) and re.search(r"temp|t_|chwr|degc|\u00b0|^t", base + unit):
            claim("t_return_c", (num() - 32) * 5 / 9 if is_f else num())
        elif re.search(r"(outdoor|outside|ambient|oat|oa_?temp|dry_?bulb)", base):
            claim("t_outdoor_c", (num() - 32) * 5 / 9 if is_f else num())
        elif re.search(r"(power|load|cooling|duty|energy|demand|btu)", base):
            v = num()
            if re.search(r"(mwh|kwh|rth|trh|tonh|ton_?h)", txt):          # energy: cumulative or per interval
                kind = "mwh" if "mwh" in txt else ("kwh" if "kwh" in txt else "rth")
                mult = {"mwh": 1000.0, "kwh": 1.0, "rth": 3.517}[kind]
                claim("energy_kw", _energy_to_kw(v * mult, df, col))
            elif re.search(r"(mw)($|_)", unit) or unit == "mw":
                claim("energy_kw", v * 1000.0)
            elif re.search(r"\b(rt|tr|tons?)\b", unit) or re.search(r"(^|_)(rt|tr|tons?)($|_)", base):
                claim("energy_kw", v * 3.517)
            elif re.search(r"kw", unit) or "kw" in base:
                claim("energy_kw", v)
    return out


def _energy_to_kw(kwh: pd.Series, df: pd.DataFrame, col: str) -> pd.Series:
    """kWh readings -> kW. Monotonic registers are differenced; interval energies are divided by the step."""
    ts_col = _find(df, "timestamp")
    if ts_col is None:
        base = next((c for c in df.columns if re.fullmatch(r"(date_?time|timestamp|time|date)", _split_name(c)[0])), None)
        ts_col = base
    if ts_col is None:
        return kwh
    ts = pd.to_datetime(df[ts_col], errors="coerce")
    step_h = ts.diff().dt.total_seconds().div(3600.0)
    d = kwh.diff()
    if (d.dropna() >= -1e-9).mean() > 0.98 and kwh.dropna().iloc[-1] > kwh.dropna().iloc[0]:
        kw = d / step_h
        kw[(d < 0) | (step_h <= 0)] = np.nan
        return kw
    return kwh / step_h.median() if step_h.median() > 0 else kwh


def _parse_time(series: pd.Series) -> pd.Series:
    ts = pd.to_datetime(series, errors="coerce")
    if ts.isna().mean() > 0.2 or ts.isna().all():
        alt = pd.to_datetime(series, errors="coerce", dayfirst=True)
        if alt.isna().mean() < ts.isna().mean():
            ts = alt
    return ts


def canonicalise(df: pd.DataFrame, min_hours: int = MIN_HOURS) -> pd.DataFrame:
    """Return an hourly frame with flow_kgs, heat_kw, dt_c, t_outdoor_c."""
    df = harmonise(df)
    c_ts = _find(df, "timestamp")
    if c_ts is None:
        raise DataError("No timestamp column found (expected e.g. 'timestamp'). Columns seen: "
                        + ", ".join(map(str, df.columns[:12])))
    ts = _parse_time(df[c_ts])
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
        raise DataError("No flow column found (flow_m3h, flow_ls or flow_gpm). Columns seen: "
                        + ", ".join(map(str, df.columns[:12])))
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
        raise DataError("Need supply and return temperatures, or a cooling power/energy column. Columns seen: "
                        + ", ".join(map(str, df.columns[:12])))
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
