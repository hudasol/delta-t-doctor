"""Loaders for the real data used in docs/research/REAL_DATA_CONTACT.md. They read data, never execute anything from it.

dk_*  : Danish smart heat meters (Zenodo 6563114). Hourly cumulative registers: energy_heat_kwh, volume_flow_m3,
        inlet_flow_energy_m3xC (volume times inlet temperature) and back_flow_energy_m3xC (volume times return temperature).
        Differencing gives hourly volume, heat and the volume weighted inlet and return temperatures.
nis_* : XAI4HEAT SCADA, Nis (Mendeley 10.17632/2mwc6x6kwb.1). Hourly primary and secondary temperatures, outdoor temperature and an
        energy column; there is no flow column.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

CP = 4.186            # kJ/(kg K); water density taken as 1000 kg/m3 (the register is volume)
MIN_VOL_M3 = 1e-3     # hourly volume below this is treated as no flow (register resolution)


def dk_hourly(raw: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    """Difference the cumulative registers into hourly values. Returns the frame and counts of what was set aside."""
    df = raw.copy()
    df["timestamp"] = pd.to_datetime(df["time_rounded"], utc=True).dt.tz_convert(None)
    df = df.sort_values("timestamp").reset_index(drop=True)
    step_h = df["timestamp"].diff().dt.total_seconds() / 3600.0
    d = {c: df[c].diff() for c in ("energy_heat_kwh", "volume_flow_m3", "inlet_flow_energy_m3xC", "back_flow_energy_m3xC")}
    vol = d["volume_flow_m3"]
    neg = (vol < 0) | (d["energy_heat_kwh"] < 0)
    ok = (step_h == 1.0) & ~neg
    moving = ok & (vol > MIN_VOL_M3)
    with np.errstate(divide="ignore", invalid="ignore"):
        t_in = (d["inlet_flow_energy_m3xC"] / vol).where(moving)
        t_back = (d["back_flow_energy_m3xC"] / vol).where(moving)
    out = pd.DataFrame({"timestamp": df["timestamp"], "flow_m3h": vol.where(ok).clip(lower=0),
                        "t_inlet_c": t_in, "t_back_c": t_back, "energy_kwh": d["energy_heat_kwh"].where(ok)}).iloc[1:]
    q = {"hours": int(len(out)), "negative_register_steps": int(neg.sum()), "non_hourly_steps": int((step_h.iloc[1:] != 1.0).sum()),
         "zero_volume_hours": int(((vol <= MIN_VOL_M3) & ok).iloc[1:].sum())}
    return out.reset_index(drop=True), q


def dk_export(raw: pd.DataFrame) -> pd.DataFrame:
    """What a user would upload: hourly flow and temperatures under the product's column names, supply = inlet, return = back.
    Timestamps keep the source's UTC 'Z' suffix, because that is how such exports arrive."""
    h, _ = dk_hourly(raw)
    return pd.DataFrame({"timestamp": h["timestamp"].dt.strftime("%Y-%m-%dT%H:%M:%SZ"), "flow_m3h": h["flow_m3h"],
                         "t_supply_c": h["t_inlet_c"], "t_return_c": h["t_back_c"]})


def dk_canonical(raw: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    """Research path: the canonical hourly frame (flow_kgs, heat_kw, dt_c, t_outdoor_c) built directly, without the chilled water
    plausibility checks. dt_c is inlet minus return, so it is positive for heating as it is for cooling."""
    h, q = dk_hourly(raw)
    flow = h["flow_m3h"] / 3.6
    dt = (h["t_inlet_c"] - h["t_back_c"])
    bad = (dt < -1) | (dt > 80)
    q["implausible_dt_hours"] = int(bad.sum())
    dt = dt.mask(bad).clip(lower=0)
    usable = flow.notna() & ((flow <= 1e-6) | dt.notna())
    c = pd.DataFrame({"timestamp": h["timestamp"], "flow_kgs": flow, "dt_c": dt, "t_outdoor_c": np.nan})[usable]
    c["heat_kw"] = CP * c["flow_kgs"] * c["dt_c"].fillna(0.0)
    reg = h["energy_kwh"][usable]
    q["heat_vs_energy_register"] = float(c["heat_kw"].sum() / max(reg.sum(), 1e-9))
    return c[["timestamp", "flow_kgs", "heat_kw", "dt_c", "t_outdoor_c"]].reset_index(drop=True), q


def nis_export(raw: pd.DataFrame) -> pd.DataFrame:
    """What a user would upload from the Nis SCADA: primary supply and return, outdoor temperature and the energy column as named
    in the source. There is no flow column to pass on."""
    return pd.DataFrame({"timestamp": raw["datetime"], "t_supply_c": raw["t_sup_prim"], "t_return_c": raw["t_ret_prim"],
                         "t_outdoor_c": raw["t_amb"], "delta_e": raw["delta_e"]})
