"""Building-side physics: many AHU coils -> one ETS meter.

The simulator turns (building config, fault spec, weather) into the time
series a district-cooling utility meter would record: supply temperature,
return temperature, flow and energy. Four physical fault families are modelled:

* fouling         - coil/heat-exchanger resistance rises, more flow per kW
* passing_valves  - water leaks through idle or part-loaded coils
* constant_flow   - 3-way valves or stuck-open actuators hold flow regardless of load
* overflow        - excess differential pressure / oversized valves push extra
                    flow through coils at part load
"""
from __future__ import annotations

from dataclasses import dataclass, field, replace
from typing import Any

import numpy as np
import pandas as pd

from .coil import CP_W, CoilDesign, coil_duty, solve_flow

BUILDING_TYPES = ("office", "hotel", "residential", "mall")


@dataclass
class BuildingConfig:
    building_type: str
    q_design_kw: np.ndarray          # per AHU
    dt_design: np.ndarray            # per AHU coil design delta-T
    dt_cap: np.ndarray               # healthy part-load delta-T ceiling per AHU
    t_supply_nom: float = 6.0
    ets_loss: float = 0.2            # heat-exchanger approach seen at the meter, K
    flow_bias: float = 0.0           # relative meter bias
    building_id: int = 0

    @property
    def n_ahu(self) -> int:
        return len(self.q_design_kw)


@dataclass
class FaultSpec:
    """Per-AHU fault parameters (arrays of length n_ahu; zeros = healthy)."""
    foul: np.ndarray
    leak_frac: np.ndarray             # extra flow as fraction of design flow
    cf_mask: np.ndarray               # bool, constant-flow AHUs
    cf_stuck: np.ndarray              # bool, True = stuck-open, False = 3-way
    cf_pos: np.ndarray                # stuck-open flow fraction of design
    overflow_k: np.ndarray            # extra flow factor at part load

    @staticmethod
    def healthy(n: int) -> "FaultSpec":
        z = np.zeros(n)
        b = np.zeros(n, dtype=bool)
        return FaultSpec(z.copy(), z.copy(), b.copy(), b.copy(), z.copy(), z.copy())

    def without(self, cause: str) -> "FaultSpec":
        n = len(self.foul)
        h = FaultSpec.healthy(n)
        out = replace(self)
        if cause == "fouling":
            out.foul = h.foul
        elif cause == "passing_valves":
            out.leak_frac = h.leak_frac
        elif cause == "constant_flow":
            out.cf_mask, out.cf_stuck, out.cf_pos = h.cf_mask, h.cf_stuck, h.cf_pos
        elif cause == "overflow":
            out.overflow_k = h.overflow_k
        else:
            raise ValueError(cause)
        return out


@dataclass
class Drivers:
    ts: pd.DatetimeIndex
    t_out: np.ndarray                 # (T,)
    lf: np.ndarray                    # (T, N) per-AHU load fraction (0 = AHU off)
    on: np.ndarray                    # (T, N) bool AHU running
    t_ws: np.ndarray                  # (T,) utility supply temperature


def _schedule(btype: str, ts: pd.DatetimeIndex, rng: np.random.Generator) -> np.ndarray:
    hour = ts.hour.values
    dow = ts.dayofweek.values  # Mon=0
    weekday = dow < 5
    if btype == "office":
        on = ((hour >= 6) & (hour < 19) & weekday).astype(float)
        occ = on * np.where((hour >= 8) & (hour < 17), 1.0, 0.7)
        sat = ((hour >= 8) & (hour < 14) & (dow == 5)).astype(float) * 0.35
        occ = np.maximum(occ, sat)
    elif btype == "mall":
        occ = ((hour >= 9) & (hour < 24)).astype(float)
        occ *= np.where(hour >= 17, 1.0, 0.85)
    elif btype == "hotel":
        occ = 0.78 + 0.22 * np.sin(2 * np.pi * (hour - 14) / 24.0) ** 2
    else:  # residential
        occ = 0.62 + 0.38 * np.sin(2 * np.pi * (hour - 16) / 24.0) ** 2
        occ = occ + 0.1 * np.where((hour >= 19) & (hour < 23), 1.0, 0.0)
    return np.clip(occ, 0.0, 1.0)


def make_drivers(cfg: BuildingConfig, ts: pd.DatetimeIndex, t_out: np.ndarray,
                 rng: np.random.Generator) -> Drivers:
    T, N = len(ts), cfg.n_ahu
    occ = _schedule(cfg.building_type, ts, rng)
    base = np.clip(0.2 + 0.8 * (t_out - 15.0) / (46.0 - 15.0), 0.06, 1.05)
    lf_total = occ * base
    # per-AHU diversity (AR(1) multiplicative noise)
    div = np.ones((T, N))
    eps = rng.normal(0, 0.12, (T, N))
    for t in range(1, T):
        div[t] = 0.85 * div[t - 1] + 0.15 * 1.0 + eps[t]
    div = np.clip(div, 0.5, 1.4)
    static = rng.uniform(0.8, 1.15, N)
    lf = np.clip(lf_total[:, None] * div * static[None, :], 0.0, 1.1)
    always_on = cfg.building_type in ("hotel", "residential")
    on = (lf > 0.02) if not always_on else np.ones((T, N), dtype=bool)
    lf = np.where(on, np.maximum(lf, 0.03 if always_on else 0.0), 0.0)
    # utility supply temperature: slow wander around nominal
    walk = np.zeros(T)
    for t in range(1, T):
        walk[t] = 0.97 * walk[t - 1] + rng.normal(0, 0.05)
    t_ws = np.clip(cfg.t_supply_nom + walk, 4.5, 8.0)
    return Drivers(ts, t_out, lf, on, t_ws)


@dataclass
class PhysicsOut:
    flow_kgs: np.ndarray       # (T,)
    heat_kw: np.ndarray        # (T,)
    t_ws: np.ndarray           # (T,)
    unmet_kw: np.ndarray       # (T,)
    t_out: np.ndarray
    ts: pd.DatetimeIndex
    cfg: Any = field(repr=False, default=None)

    @property
    def delta_t_series(self) -> np.ndarray:
        with np.errstate(divide="ignore", invalid="ignore"):
            return np.where(self.flow_kgs > 1e-6, self.heat_kw / (CP_W * self.flow_kgs), np.nan)

    @property
    def delta_t_period(self) -> float:
        """Flow-weighted (= energy / volume) delta-T over the window, deg C."""
        f = self.flow_kgs.sum()
        return float(self.heat_kw.sum() / (CP_W * f)) if f > 0 else float("nan")


def physics(cfg: BuildingConfig, faults: FaultSpec, drv: Drivers) -> PhysicsOut:
    N = cfg.n_ahu
    design = CoilDesign(cfg.q_design_kw, cfg.dt_design)
    t_ai = (24.0 + 0.2 * (drv.t_out - 24.0))[:, None] * np.ones((1, N))
    t_ws = drv.t_ws[:, None]
    q_dem = cfg.q_design_kw[None, :] * drv.lf
    c_air = np.maximum(q_dem / np.maximum(t_ai - design.t_sa, 1.0), 1e-9)
    foul = faults.foul[None, :]

    m_s, q_del = solve_flow(design, q_dem, c_air, t_ai, t_ws, foul)
    # healthy part-load ceiling on coil delta-T (valves cannot throttle perfectly)
    with np.errstate(divide="ignore", invalid="ignore"):
        dt_nat = np.where(m_s > 0, q_del / (CP_W * m_s), 0.0)
    m_cap = np.where(q_del > 0, q_del / (CP_W * cfg.dt_cap[None, :]), 0.0)
    m = np.where(dt_nat > cfg.dt_cap[None, :], m_cap, m_s)
    heat = q_del.copy()                      # kW removed by flow m
    on = drv.on

    # ---- constant-flow coils (3-way or stuck-open) ----
    cf = faults.cf_mask[None, :] & np.ones_like(m, dtype=bool)
    if cf.any():
        m_cf_3way = np.broadcast_to(design.m_d[None, :], m.shape)
        m_cf_stuck = np.broadcast_to((faults.cf_pos * design.m_d)[None, :], m.shape)
        m_cf = np.where(faults.cf_stuck[None, :], m_cf_stuck, m_cf_3way)
        # stuck-open: coil delivers whatever physics gives at that flow (over-cools)
        q_stuck = coil_duty(design, m_cf, c_air, t_ai, t_ws, foul)
        q_stuck = np.where(on, q_stuck, 0.0)
        q_3way = np.where(on, q_del, 0.0)
        q_cf = np.where(faults.cf_stuck[None, :], q_stuck, q_3way)
        # idle coil with water flowing: small parasitic gain
        idle_heat = m_cf * CP_W * 0.4
        q_cf = np.where(on, q_cf, idle_heat)
        m = np.where(cf, m_cf, m)
        heat = np.where(cf, q_cf, heat)

    # ---- passing valves: extra flow with little heat exchange ----
    leak_m = faults.leak_frac[None, :] * design.m_d[None, :]
    leak_m = np.broadcast_to(leak_m, m.shape)
    leak_dt = np.where(on, 3.0, 0.5)
    leak_m = np.where(faults.cf_mask[None, :], 0.0, leak_m)  # already full-flow
    m = m + leak_m
    heat = heat + leak_m * CP_W * leak_dt

    # ---- overflow at part load (excess DP / hunting) ----
    lf_eff = np.clip(drv.lf, 0.0, 1.0)
    extra = faults.overflow_k[None, :] * (1.0 - lf_eff) * np.where(on, m_s, 0.0)
    extra = np.where(faults.cf_mask[None, :], 0.0, extra)
    m = m + extra
    heat = heat + extra * CP_W * 3.0

    flow = m.sum(axis=1)
    heat_tot = heat.sum(axis=1)
    unmet = np.maximum(q_dem - q_del, 0.0).sum(axis=1)
    return PhysicsOut(flow, heat_tot, drv.t_ws, unmet, drv.t_out, drv.ts, cfg)


def measure(out: PhysicsOut, rng: np.random.Generator,
            flow_noise: float = 0.015, temp_noise: float = 0.10) -> pd.DataFrame:
    """Turn physics into what the utility meter logs (with noise and cutoffs)."""
    cfg = out.cfg
    T = len(out.ts)
    flow = out.flow_kgs * (1.0 + cfg.flow_bias)
    flow_meas = flow * (1.0 + rng.normal(0, flow_noise, T))
    design_flow = float((cfg.q_design_kw / (CP_W * cfg.dt_design)).sum())
    flow_meas = np.where(flow_meas < 0.005 * design_flow, 0.0, flow_meas)
    with np.errstate(divide="ignore", invalid="ignore"):
        dt_true = np.where(out.flow_kgs > 1e-6, out.heat_kw / (CP_W * out.flow_kgs), 0.0)
    dt_meter = np.maximum(dt_true - cfg.ets_loss, 0.0)
    ts_meas = out.t_ws + rng.normal(0, temp_noise, T)
    tr_meas = out.t_ws + dt_meter + rng.normal(0, temp_noise, T)
    energy = np.where(flow_meas > 0, CP_W * flow_meas * np.maximum(tr_meas - ts_meas, 0.0), 0.0)
    return pd.DataFrame({
        "timestamp": out.ts,
        "t_supply_c": ts_meas,
        "t_return_c": tr_meas,
        "flow_m3h": flow_meas * 3.6,        # kg/s ~ L/s -> m3/h
        "energy_kw": energy,
        "t_outdoor_c": out.t_out,
    })
