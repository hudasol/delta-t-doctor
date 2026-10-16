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
import logging
import re
import warnings

import numpy as np
import pandas as pd

from .i18n import note
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
MAX_MEDIAN_STEP_H = 2.0          # coarser data cannot show time-of-day behaviour
log = logging.getLogger(__name__)


class DataError(ValueError):
    pass


def _find(df: pd.DataFrame, key: str):
    low = {c.lower().strip(): c for c in df.columns}
    for a in _ALIASES[key]:
        if a in low:
            return low[a]
    return None


# ---------------------------------------------------------------- reading real exports

def _decode(raw: bytes) -> str:
    """Decode an upload. UTF-16 only when a byte-order mark says so; otherwise UTF-8, then Windows-1252."""
    if raw[:2] in (b"\xff\xfe", b"\xfe\xff"):
        return raw.decode("utf-16")
    for enc in ("utf-8-sig", "cp1252"):
        try:
            return raw.decode(enc)
        except UnicodeDecodeError:
            continue
    return raw.decode("latin-1")


def _sniff_sep(text: str) -> str:
    head = text[:4096]
    best, best_n = ",", 0
    for sep in (",", ";", "\t", "|"):
        n = head.count(sep)
        if n > best_n:
            best, best_n = sep, n
    return best


def _check_zip(raw: bytes) -> None:
    """Refuse spreadsheets that expand absurdly (zip bombs) before openpyxl touches them."""
    import zipfile
    if raw[:2] != b"PK":
        raise DataError("That file is not an .xlsx workbook. Save it as .xlsx or export a CSV.")
    try:
        with zipfile.ZipFile(_io.BytesIO(raw)) as z:
            total = sum(i.file_size for i in z.infolist())
            if total > MAX_UNZIPPED_BYTES or len(z.infolist()) > 200:
                raise DataError("The workbook is too large when unpacked. Export the period you need as a CSV.")
    except zipfile.BadZipFile:
        raise DataError("The .xlsx file is damaged or not a workbook.") from None


def read_table(raw: bytes, filename: str = "upload.csv") -> pd.DataFrame:
    """Read an uploaded export: CSV with any common delimiter or encoding, or an .xlsx sheet. Size-bounded."""
    name = (filename or "").lower()
    try:
        if name.endswith(".xls"):
            raise DataError("Old .xls files are not supported. Save the sheet as .xlsx or CSV.")
        if name.endswith((".xlsx", ".xlsm")):
            _check_zip(raw)
            df = pd.read_excel(_io.BytesIO(raw), nrows=MAX_ROWS + 1)
        else:
            text = _decode(raw)
            df = pd.read_csv(_io.StringIO(text), sep=_sniff_sep(text), nrows=MAX_ROWS + 1)
    except DataError:
        raise
    except ImportError:
        raise DataError("Reading Excel files needs the optional 'openpyxl' package; export the sheet as CSV instead.") from None
    except Exception as e:
        log.info("read_table failed (%s): %s", type(e).__name__, filename)
        raise DataError("Could not read the file as a table. Use a CSV or an Excel sheet with a header row.") from None
    if len(df) > MAX_ROWS or df.shape[1] > MAX_COLS:
        raise DataError(f"The file has more than {MAX_ROWS:,} rows or {MAX_COLS} columns. Export a smaller period.")
    return df


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


def _monotone_share(ts: pd.Series) -> float:
    d = ts.diff().dropna()
    return float((d >= pd.Timedelta(0)).mean()) if len(d) else 1.0


def _parse_time(series: pd.Series, notes: list | None = None) -> pd.Series:
    """Parse timestamps, resolving day-first versus month-first by which reading is consistent.

    Both readings are tried. If exactly one parses every row it wins. If both do and they differ (dd/mm against
    mm/dd with all days <= 12), the one whose rows run forward in time wins; a tie goes to day-first, the UAE convention.
    """
    notes = notes if notes is not None else []
    if pd.api.types.is_datetime64_any_dtype(series):
        return pd.to_datetime(series, errors="coerce")
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        a = pd.to_datetime(series, errors="coerce")
        b = pd.to_datetime(series, errors="coerce", dayfirst=True)
    na, nb = int(a.isna().sum()), int(b.isna().sum())
    if na != nb:
        return a if na < nb else b
    if (a.fillna(pd.Timestamp(0)) == b.fillna(pd.Timestamp(0))).all():
        return a
    ma, mb = _monotone_share(a), _monotone_share(b)
    if abs(ma - mb) > 1e-9:
        pick = a if ma > mb else b
    else:
        pick = b
        notes.append(note("date_ambiguous"))
    return pick


MAX_UNZIPPED_BYTES = 150 * 1024 * 1024
SENTINELS = (-999.0, -9999.0, -99999.0, 9999.0, 99999.0, 65535.0, -32768.0, 32767.0, 999.0, 99.99)
MAX_DT_C = 30.0              # a chilled-water delta-T above this is a sensor fault, not physics
SPIKE_FACTOR = 6.0           # flow above this multiple of its 90th percentile (while running) is a spike
FLATLINE_HOURS = 48          # identical flow and delta-T for this long while water moves means a stuck reading
MAX_ROWS = 2_000_000
MAX_COLS = 200


def _num(df: pd.DataFrame, col, counts: dict) -> pd.Series:
    """to_numeric that counts what it had to throw away: text in a numeric column, infinities, sentinel codes."""
    raw = df[col]
    v = pd.to_numeric(raw, errors="coerce")
    counts["coerced"] += int((v.isna() & raw.notna() & (raw.astype(str).str.strip() != "")).sum())
    v = v.replace([np.inf, -np.inf], np.nan)
    sent = v.isin(SENTINELS)
    counts["sentinel"] += int(sent.sum())
    return v.mask(sent)


def _longest_run(same: np.ndarray) -> int:
    best = cur = 0
    for x in same:
        cur = cur + 1 if x else 0
        best = max(best, cur)
    return best


def canonicalise(df: pd.DataFrame, min_hours: int = MIN_HOURS) -> pd.DataFrame:
    """Return an hourly frame with flow_kgs, heat_kw, dt_c, t_outdoor_c.

    Rows with a missing flow or delta-T are dropped, never zero-filled. Supply and return that look swapped, impossible
    temperatures and data coarser than 2-hourly are rejected. Counts of everything repaired or dropped are stored in
    ``frame.attrs["quality"]`` and plain-language messages in ``frame.attrs["notes"]``.
    """
    notes: list[str] = []
    df = harmonise(df)
    c_ts = _find(df, "timestamp")
    if c_ts is None:
        raise DataError("No timestamp column found (expected e.g. 'timestamp'). Columns seen: "
                        + ", ".join(map(str, df.columns[:12])))
    ts = _parse_time(df[c_ts], notes)
    if ts.isna().all():
        raise DataError("Could not parse the timestamp column.")
    tz = getattr(getattr(ts, "dt", None), "tz", None)
    if tz is not None and ts.notna().any() and ts.dropna().iloc[0].utcoffset() == pd.Timedelta(0):
        # Hour of day features (night against day, weekend against week) assume local wall time. A UTC export shifts them by the local
        # offset (4 hours in the UAE) without any error, so say so (found on the Danish meter data, docs/REAL_DATA_CONTACT.md).
        notes.append(note("utc_time"))
    out = pd.DataFrame({"timestamp": ts})
    n_raw = len(out)
    bad_ts = float(ts.isna().mean())
    counts = {"coerced": 0, "sentinel": 0}

    c_f = _find(df, "flow_m3h")
    c_fl = _find(df, "flow_ls")
    c_fg = _find(df, "flow_gpm")
    if c_f is not None:
        flow_kgs = _num(df, c_f, counts) / 3.6
    elif c_fl is not None:
        flow_kgs = _num(df, c_fl, counts)
    elif c_fg is not None:
        flow_kgs = _num(df, c_fg, counts) * 0.0630902
    else:
        raise DataError("No flow column found (flow_m3h, flow_ls or flow_gpm). Columns seen: "
                        + ", ".join(map(str, df.columns[:12])))
    flow_kgs = flow_kgs.replace([np.inf, -np.inf], np.nan)
    neg_flow = float((flow_kgs < -1e-9).mean())
    if neg_flow > 0.5:
        raise DataError("Most flow readings are negative. Check the flow column (reverse-flow sign or wrong column).")
    flow_kgs = flow_kgs.where(flow_kgs >= -1e-9, np.nan) if neg_flow > 0.05 else flow_kgs
    moving = flow_kgs[flow_kgs > 1e-6]
    n_spike = 0
    if len(moving) >= 24:
        cap = SPIKE_FACTOR * float(np.percentile(moving, 90))
        spike = flow_kgs > cap
        n_spike = int(spike.sum())
        flow_kgs = flow_kgs.mask(spike)
    out["flow_kgs"] = flow_kgs.clip(lower=0)

    c_s, c_r = _find(df, "t_supply_c"), _find(df, "t_return_c")
    c_e, c_rt = _find(df, "energy_kw"), _find(df, "energy_rt")
    if c_s is not None and c_r is not None:
        ts_, tr_ = _num(df, c_s, counts), _num(df, c_r, counts)
        for name, v, lo, hi in (("supply", ts_, -2.0, 25.0), ("return", tr_, 2.0, 40.0)):
            med = float(v.median()) if v.notna().any() else float("nan")
            if np.isfinite(med) and not (lo <= med <= hi):
                raise DataError(f"The {name} temperature column has a median of {med:.1f}, which is not a plausible "
                                f"chilled-water temperature in degrees Celsius. If it is in Fahrenheit, put (F) in the "
                                f"column header.")
        # Readings outside any physical chilled-water range are sensor faults (e.g. 99.9 as 'no reading'): remove them.
        bad_t = (ts_ < -5) | (ts_ > 35) | (tr_ < -5) | (tr_ > 50)
        n_range = int(bad_t.sum())
        dt_raw = (tr_ - ts_).mask(bad_t)
    elif c_e is not None or c_rt is not None:
        kw = (_num(df, c_e, counts) if c_e is not None else _num(df, c_rt, counts) * 3.517)
        n_range = 0
        with np.errstate(divide="ignore", invalid="ignore"):
            dt_raw = kw / (CP_W * out["flow_kgs"].replace(0, np.nan))
    else:
        raise DataError("Need supply and return temperatures, or a cooling power/energy column. Columns seen: "
                        + ", ".join(map(str, df.columns[:12])))
    dt_raw = dt_raw.replace([np.inf, -np.inf], np.nan)
    too_hot = dt_raw > MAX_DT_C
    n_range += int(too_hot.sum())
    dt_raw = dt_raw.mask(too_hot)
    med_dt = float(dt_raw[out["flow_kgs"] > 1e-6].median()) if (out["flow_kgs"] > 1e-6).any() else float("nan")
    if np.isfinite(med_dt) and med_dt < -0.75:   # sensor offsets alone can push a very low delta-T slightly negative
        raise DataError("The return temperature is colder than the supply for most rows, so supply and return look "
                        "swapped. Check the column mapping.")
    if np.isfinite(med_dt) and med_dt > 25:
        raise DataError(f"The typical delta-T is {med_dt:.0f} C, which is not plausible for chilled water. "
                        f"Check the units of the temperature or energy columns.")
    running = out["flow_kgs"] > 1e-6
    neg_dt = float((dt_raw[running] < -0.5).mean()) if running.any() else 0.0
    out["dt_c"] = dt_raw.clip(lower=0)

    c_o = _find(df, "t_outdoor_c")
    oat = _num(df, c_o, counts) if c_o else pd.Series(np.nan, index=df.index)
    out["t_outdoor_c"] = oat.where((oat > -30) & (oat < 60))
    # Stuck sensor: the exact same flow value repeated for two days while water is moving.
    run_len = 0
    if running.any():
        same = (flow_kgs.diff() == 0) & running
        run_len = _longest_run(same.to_numpy())

    out = out.dropna(subset=["timestamp"]).sort_values("timestamp")
    # A row is usable if flow is known and, when water is moving, delta-T is known. Others are dropped, not zero-filled.
    usable = out["flow_kgs"].notna() & ((out["flow_kgs"] <= 1e-6) | out["dt_c"].notna())
    out = out[usable]
    dropped = float(1.0 - len(out) / max(n_raw, 1))
    out["heat_kw"] = CP_W * out["flow_kgs"] * out["dt_c"].fillna(0.0)

    step_h = float(out["timestamp"].diff().dt.total_seconds().median() / 3600.0) if len(out) > 2 else float("nan")
    if np.isfinite(step_h) and step_h > MAX_MEDIAN_STEP_H:
        raise DataError(f"The readings are {step_h:.1f} hours apart. The tool needs hourly or 2-hourly data to see how "
                        f"the building behaves through the day.")
    dup = int(out["timestamp"].duplicated().sum())
    if dup:
        notes.append(note("duplicates", n=dup))
    out = _to_hourly(out)
    if len(out) < min_hours:
        raise DataError(
            f"Need at least {min_hours // 24} days of data ({min_hours} hourly rows); got {len(out)}.")
    if dropped > 0.005:
        notes.append(note("dropped", p=f"{dropped:.1%}"))
    outlier = float((n_spike + n_range) / max(n_raw, 1))
    if outlier > 0.001:
        notes.append(note("outlier", p=f"{outlier:.1%}"))
    if bad_ts > 0.005:
        notes.append(note("bad_ts", p=f"{bad_ts:.1%}"))
    if counts["coerced"] or counts["sentinel"]:
        notes.append(note("coerced", c=counts["coerced"], s=counts["sentinel"]))
    if run_len >= FLATLINE_HOURS:
        notes.append(note("flatline", n=run_len))
    if neg_dt > 0.005:
        notes.append(note("neg_dt", p=f"{neg_dt:.1%}"))
    out = out.reset_index(drop=True)
    out.attrs["quality"] = {"rows_raw": int(n_raw), "dropped_fraction": dropped, "negative_dt_fraction": neg_dt,
                            "negative_flow_fraction": neg_flow, "median_step_h": step_h, "duplicate_timestamps": dup,
                            "outlier_fraction": outlier, "bad_timestamp_fraction": bad_ts,
                            "coerced_cells": int(counts["coerced"]), "sentinel_cells": int(counts["sentinel"]),
                            "longest_flatline_readings": int(run_len)}
    out.attrs["notes"] = notes
    return out


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
