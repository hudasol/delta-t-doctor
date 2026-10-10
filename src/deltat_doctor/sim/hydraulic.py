"""Simulator B: a structurally different generator, used to test generalisation (see docs/CROSS_SIMULATOR.md).

Where simulator A injects each fault as an explicit flow with a fixed heat signature, here the faults act on a small
hydraulic and psychrometric model and their meter signatures *emerge*:

* Demand comes from air enthalpy (humidity and outdoor-air fraction), a VAV fan and zone start-up, not from a single
  dry-bulb curve. Hospitals and data centres barely follow the weather.
* Each AHU has an equal-percentage control valve with finite rangeability, a minimum controllable position and an
  oversize factor, fed by a differential-pressure set point. Water flow is whatever the valve passes.
* The coil is a wet coil: duty = effectiveness x capacity x (air enthalpy - saturation enthalpy at the water supply).
* overflow    = a differential-pressure set point above need and extra valve oversize: the valve cannot close below its
                minimum position, so low-load flow is too high.
* passing     = a closed valve leaks a fraction of its capacity; the leak exchanges heat only as much as the (possibly
                stopped) air stream allows.
* constant    = a 3-way valve (bypass returns unheated water and mixes) or a valve stuck at a fixed position.
* fouling     = extra resistance on the air and water sides of the coil (unequal split).
* The ETS plate exchanger has a load-dependent approach, the meter sits on the primary side, supply and return sensors
  carry fixed offsets, and hours are dropped at random. Some faults start part-way through the window.

Everything is deterministic given the random generator. This is a second model written by the same author, so it
reduces, not removes, the circularity risk; it is a necessary first step, not field validation.
"""
from __future__ import annotations

from dataclasses import dataclass, replace

import numpy as np
import pandas as pd

from .. import CAUSES, CP_KJ_KG_K
from .coil import eps_counterflow
from .scenarios import PRESENT_THRESHOLD_C, Sample
from .weather import make_timestamps, synth_outdoor_temp

BUILDING_TYPES_B = ("office", "hotel", "residential", "mall", "hospital", "data_centre", "school")
CS = 2.6            # slope of saturation enthalpy against temperature near coil conditions, kJ/kg per K
H_SUPPLY_AIR = 36.0
H_DESIGN_IN = 62.0
H_RETURN_AIR = 47.0
VALVE_R = 50.0


def h_sat(t):
    """Saturated air enthalpy, kJ/kg dry air."""
    ps = 0.6108 * np.exp(17.27 * t / (t + 237.3))
    w = 0.622 * ps / (101.3 - ps)
    return 1.006 * t + w * (2501.0 + 1.86 * t)


def h_moist(t, dew):
    ps = 0.6108 * np.exp(17.27 * dew / (dew + 237.3))
    w = 0.622 * ps / (101.3 - ps)
    return 1.006 * t + w * (2501.0 + 1.86 * t)


@dataclass
class BuildingB:
    building_type: str
    q_design_kw: np.ndarray
    dt_design: np.ndarray
    valve_oversize: np.ndarray      # healthy valve capacity over design flow
    x_min: np.ndarray               # minimum controllable valve position
    oa_frac: np.ndarray
    t_supply_nom: float
    hx_k: float                     # plate exchanger approach scale, K
    off_s: float                    # supply sensor offset, K
    off_r: float                    # return sensor offset, K
    flow_bias: float
    drop_frac: float
    building_id: int = 0

    @property
    def n_ahu(self) -> int:
        return len(self.q_design_kw)


@dataclass
class FaultsB:
    foul: np.ndarray        # (N,) coil resistance excess
    leak: np.ndarray        # (N,) closed-valve leak as fraction of valve capacity
    cf_mask: np.ndarray
    cf_stuck: np.ndarray
    cf_pos: np.ndarray
    dp_ratio: np.ndarray    # (N,) differential pressure set point over need (1 = right)
    ov_extra: np.ndarray    # (N,) extra valve oversize (1 = none)
    onset: float = 0.0      # fraction of the window before faults appear (0 = from the start)

    @staticmethod
    def healthy(n: int) -> "FaultsB":
        z, b = np.zeros(n), np.zeros(n, dtype=bool)
        return FaultsB(z.copy(), z.copy(), b.copy(), b.copy(), z.copy(), np.ones(n), np.ones(n))

    def without(self, cause: str) -> "FaultsB":
        h = FaultsB.healthy(len(self.foul))
        o = replace(self)
        if cause == "fouling":
            o.foul = h.foul
        elif cause == "passing_valves":
            o.leak = h.leak
        elif cause == "constant_flow":
            o.cf_mask, o.cf_stuck, o.cf_pos = h.cf_mask, h.cf_stuck, h.cf_pos
        elif cause == "overflow":
            o.dp_ratio, o.ov_extra = h.dp_ratio, h.ov_extra
        else:
            raise ValueError(cause)
        return o


def sample_building_b(rng: np.random.Generator, building_id: int = 0) -> BuildingB:
    btype = BUILDING_TYPES_B[rng.integers(len(BUILDING_TYPES_B))]
    n = int(rng.integers(5, 36))
    q_total = float(np.exp(rng.uniform(np.log(300.0), np.log(8000.0))))
    q = q_total * rng.dirichlet(np.full(n, 2.5))
    dt_b = rng.uniform(4.5, 13.0)
    dt = np.clip(dt_b + rng.normal(0, 0.8, n), 4.0, 14.0)
    return BuildingB(
        building_type=btype, q_design_kw=q, dt_design=dt,
        valve_oversize=rng.uniform(1.2, 2.2, n), x_min=rng.uniform(0.05, 0.15, n),
        oa_frac=np.clip(rng.normal(0.18 if btype != "data_centre" else 0.04, 0.06, n), 0.02, 0.4),
        t_supply_nom=float(rng.uniform(4.8, 7.2)), hx_k=float(rng.uniform(0.2, 0.9)),
        off_s=float(np.clip(rng.normal(0, 0.12), -0.25, 0.25)), off_r=float(np.clip(rng.normal(0, 0.12), -0.25, 0.25)),
        flow_bias=float(rng.normal(0, 0.02)), drop_frac=float(rng.uniform(0.0, 0.05)), building_id=building_id,
    )


def sample_faults_b(cfg: BuildingB, rng: np.random.Generator, causes: tuple[str, ...], severity_scale: float = 1.0) -> FaultsB:
    n = cfg.n_ahu
    f = FaultsB.healthy(n)

    def pick(lo, hi):
        k = max(1, int(round(rng.uniform(lo, hi) * n)))
        m = np.zeros(n, dtype=bool)
        m[rng.choice(n, size=min(k, n), replace=False)] = True
        return m

    if "fouling" in causes:
        f.foul = np.where(pick(0.3, 1.0), rng.uniform(0.15, 1.2, n) * severity_scale, 0.0)
    if "passing_valves" in causes:
        f.leak = np.where(pick(0.15, 0.7), rng.uniform(0.015, 0.11, n) * severity_scale, 0.0)
    if "constant_flow" in causes:
        m = pick(0.15, 0.8)
        f.cf_mask = m
        f.cf_stuck = m & (rng.random(n) < rng.uniform(0, 1))
        f.cf_pos = np.where(f.cf_stuck, rng.uniform(0.4, 1.0, n), 0.0)
    if "overflow" in causes:
        m = pick(0.3, 1.0)
        f.dp_ratio = np.where(m, 1.0 + rng.uniform(0.3, 1.6, n) * severity_scale, 1.0)
        f.ov_extra = np.where(m, 1.0 + rng.uniform(0.2, 1.2, n) * severity_scale, 1.0)
    if rng.random() < 0.25:
        f.onset = float(rng.uniform(0.15, 0.7))
    return f


def _occupancy(btype: str, ts: pd.DatetimeIndex, phase: np.ndarray) -> np.ndarray:
    """(T, N) occupancy, with a per-AHU phase offset in hours."""
    hour = ts.hour.values[:, None] + phase[None, :]
    dow = ts.dayofweek.values[:, None]
    wk = dow < 5
    if btype == "office":
        occ = ((hour >= 6) & (hour < 19) & wk) * 0.9
    elif btype == "school":
        term = ((ts.month.values[:, None] != 7) & (ts.month.values[:, None] != 8))
        occ = ((hour >= 7) & (hour < 15) & wk & term) * 0.95
    elif btype == "mall":
        occ = ((hour >= 9) & (hour < 23)) * 0.9
    elif btype == "hotel":
        occ = 0.7 + 0.25 * np.cos(2 * np.pi * (hour - 20) / 24.0) ** 2
    elif btype == "hospital":
        occ = 0.85 + 0.1 * np.cos(2 * np.pi * (hour - 13) / 24.0)
    elif btype == "data_centre":
        occ = np.full(hour.shape, 0.92)
    else:
        occ = 0.55 + 0.4 * np.cos(2 * np.pi * (hour - 21) / 24.0) ** 2
    return np.clip(occ, 0.0, 1.0)


@dataclass
class DriversB:
    ts: pd.DatetimeIndex
    t_out: np.ndarray
    h_ai: np.ndarray      # (T, N)
    fan: np.ndarray       # (T, N) VAV fan fraction
    on: np.ndarray        # (T, N)
    t_ws: np.ndarray      # (T,)
    ramp: np.ndarray      # (T,) fault severity ramp 0..1


def make_drivers_b(cfg: BuildingB, ts: pd.DatetimeIndex, t_out: np.ndarray, faults: FaultsB,
                   rng: np.random.Generator) -> DriversB:
    T, N = len(ts), cfg.n_ahu
    month = ts.month.values
    dew_mean = np.array([11, 12, 14, 16, 20, 23, 25, 26, 24, 20, 15, 12], dtype=float)[month - 1]
    dew = np.minimum(dew_mean + rng.normal(0, 1.5, T) + 0.1 * (t_out - 30), t_out - 1.0)
    h_out = h_moist(t_out, dew)
    phase = rng.integers(-1, 2, N).astype(float)
    occ = _occupancy(cfg.building_type, ts, phase)
    start = np.zeros_like(occ)
    turn_on = np.zeros_like(occ, dtype=bool)
    turn_on[1:] = (occ[1:] > 0.3) & (occ[:-1] <= 0.3)
    for lag, amp in enumerate((0.45, 0.25, 0.1)):
        idx = np.arange(T) - lag
        ok = idx >= 0
        start[ok] += amp * turn_on[idx[ok]]
    oa = cfg.oa_frac[None, :]
    h_ra = H_RETURN_AIR + rng.normal(0, 0.8, (T, 1)) + 1.5 * (cfg.building_type == "data_centre")
    h_ai = (1 - oa) * h_ra + oa * h_out[:, None]
    sT = np.clip((t_out - 15.0) / 31.0, 0.0, 1.1)[:, None]
    zone = occ * (0.30 + 0.30 * sT) + 0.2 * start
    if cfg.building_type in ("hospital", "data_centre"):
        zone = 0.55 + 0.35 * occ + 0.1 * sT
    div = np.ones((T, N))
    e = rng.normal(0, 0.08, (T, N))
    for t in range(1, T):
        div[t] = 0.9 * div[t - 1] + 0.1 + e[t]
    zone = zone * np.clip(div, 0.6, 1.3)
    fan = np.clip(0.3 + 0.7 * zone, 0.3, 1.0)
    always = cfg.building_type in ("hotel", "residential", "hospital", "data_centre")
    on = np.ones((T, N), dtype=bool) if always else (occ > 0.05)
    walk = np.zeros(T)
    for t in range(1, T):
        walk[t] = 0.95 * walk[t - 1] + rng.normal(0, 0.06)
    t_ws = np.clip(cfg.t_supply_nom + walk, 4.5, 8.0)
    n_on = int(faults.onset * T)
    ramp = np.ones(T)
    if n_on > 0:
        ramp[:n_on] = 0.0
        r = min(72, T - n_on)
        ramp[n_on:n_on + r] = np.linspace(0, 1, r)
    return DriversB(ts, t_out, h_ai, fan, on, t_ws, ramp)


def _design(cfg: BuildingB):
    m_d = cfg.q_design_kw / (CP_KJ_KG_K * cfg.dt_design)
    m_air = cfg.q_design_kw / (H_DESIGN_IN - H_SUPPLY_AIR)
    cw = m_d * CP_KJ_KG_K / CS
    cmin = np.minimum(m_air, cw)
    eps_d = np.clip(cfg.q_design_kw / (cmin * (H_DESIGN_IN - float(h_sat(6.0)))), 0.05, 0.97)
    cr = cmin / np.maximum(m_air, cw)
    lo, hi = np.zeros_like(eps_d), np.full_like(eps_d, 60.0)
    for _ in range(50):
        mid = 0.5 * (lo + hi)
        e = eps_counterflow(mid, cr)
        hi = np.where(e > eps_d, mid, hi)
        lo = np.where(e > eps_d, lo, mid)
    ntu = 0.5 * (lo + hi)
    r_tot = 1.0 / (ntu * cmin)
    return m_d, m_air, r_tot * 0.6, r_tot * 0.4


def _duty(m_w, m_air_eff, h_ai, t_ws, foul, des):
    m_d, _, r_air, r_w = des
    m_w = np.asarray(m_w, dtype=float)
    cw = np.maximum(m_w * CP_KJ_KG_K / CS, 1e-9)
    ca = np.maximum(m_air_eff, 1e-9)
    cmin, cmax = np.minimum(ca, cw), np.maximum(ca, cw)
    ratio = np.maximum(m_d / np.maximum(m_w, 1e-9 * m_d), 1e-6)
    r = r_air * (1.0 + 0.7 * foul) + r_w * ratio ** 0.8 * (1.0 + 0.3 * foul)
    eps = eps_counterflow(1.0 / (r * cmin), cmin / cmax)
    q = eps * cmin * np.maximum(h_ai - h_sat(t_ws), 0.0)
    return np.where(m_w <= 0, 0.0, q)


def _solve_m(q_req, m_air_eff, h_ai, t_ws, foul, des, m_cap):
    lo = np.zeros_like(q_req)
    hi = m_cap.copy()
    for _ in range(36):
        mid = 0.5 * (lo + hi)
        low = _duty(mid, m_air_eff, h_ai, t_ws, foul, des) < q_req
        lo = np.where(low, mid, lo)
        hi = np.where(low, hi, mid)
    m = 0.5 * (lo + hi)
    sat = _duty(m_cap, m_air_eff, h_ai, t_ws, foul, des) < q_req
    return np.where(sat, m_cap, np.where(q_req <= 1e-9, 0.0, m))


@dataclass
class PhysicsB:
    flow_kgs: np.ndarray
    heat_kw: np.ndarray
    dt_p: np.ndarray
    t_ws: np.ndarray
    cfg: BuildingB
    ts: pd.DatetimeIndex
    t_out: np.ndarray

    @property
    def dt_period(self) -> float:
        f = self.flow_kgs.sum()
        return float(self.heat_kw.sum() / (CP_KJ_KG_K * f)) if f > 0 else float("nan")


def physics_b(cfg: BuildingB, f: FaultsB, drv: DriversB) -> PhysicsB:
    des = _design(cfg)
    m_d, m_air_d, _, _ = des
    ramp = drv.ramp[:, None]
    foul = f.foul[None, :] * ramp
    leak = 0.0005 + f.leak[None, :] * ramp
    dp = 1.0 + (f.dp_ratio[None, :] - 1.0) * ramp
    ov = cfg.valve_oversize[None, :] * (1.0 + (f.ov_extra[None, :] - 1.0) * ramp)
    t_ws = drv.t_ws[:, None]
    m_air = m_air_d[None, :] * drv.fan * drv.on
    air_idle = m_air_d[None, :] * 0.03
    m_air_eff = np.where(drv.on, m_air, air_idle)

    m_vmax = m_d[None, :] * ov * np.sqrt(dp)
    # High differential pressure and extra oversize push the valve into the bottom of its stroke, where it cannot turn down.
    x_eff = np.clip(cfg.x_min[None, :] + 0.26 * (dp - 1.0) + 0.14 * (ov / cfg.valve_oversize[None, :] - 1.0), 0.0, 0.7)
    phi_min = VALVE_R ** (x_eff - 1.0)
    m_floor = m_vmax * phi_min
    m_leak = m_vmax * leak
    q_leak = _duty(m_leak, m_air_eff, drv.h_ai, t_ws, foul, des)

    q_dem = np.where(drv.on, m_air * np.maximum(drv.h_ai - H_SUPPLY_AIR, 0.0), 0.0)
    q_dem = np.minimum(q_dem, 1.15 * cfg.q_design_kw[None, :])
    q_req = np.maximum(q_dem - q_leak, 0.0)
    m_req = _solve_m(q_req, m_air_eff, drv.h_ai, t_ws, foul, des, m_vmax)
    running = drv.on & (q_req > 1e-6)
    m_ctrl = np.where(running, np.maximum(m_req, m_floor), 0.0)
    m = m_ctrl + m_leak
    q = np.where(running, _duty(m_ctrl, m_air_eff, drv.h_ai, t_ws, foul, des), 0.0) + q_leak

    cf = f.cf_mask[None, :] & (ramp > 0.5)
    if cf.any():
        m_const = np.where(f.cf_stuck[None, :], f.cf_pos[None, :], 1.0) * m_d[None, :]
        q_const = _duty(m_const, m_air_eff, drv.h_ai, t_ws, foul, des)
        q_const = np.minimum(q_const, 1.2 * cfg.q_design_kw[None, :])
        stuck = f.cf_stuck[None, :]
        q_cf = np.where(stuck, q_const, np.where(drv.on, q_dem, q_const))
        m = np.where(cf, m_const, m)
        q = np.where(cf, q_cf, q)

    m_sec = m.sum(axis=1)
    q_tot = q.sum(axis=1)
    with np.errstate(divide="ignore", invalid="ignore"):
        dt_sec = np.where(m_sec > 1e-6, q_tot / (CP_KJ_KG_K * m_sec), 0.0)
    lf_tot = np.clip(q_tot / cfg.q_design_kw.sum(), 0.0, 1.2)
    app = cfg.hx_k * (0.3 + 0.7 * lf_tot)
    dt_p = np.maximum(dt_sec - app, 0.0)
    flow_p = np.where(q_tot > 1e-6, q_tot / (CP_KJ_KG_K * np.maximum(dt_p, 0.3)), 0.0)
    heat = np.where(flow_p > 0, CP_KJ_KG_K * flow_p * dt_p, 0.0)
    return PhysicsB(flow_p, heat, dt_p, drv.t_ws, cfg, drv.ts, drv.t_out)


def measure_b(out: PhysicsB, rng: np.random.Generator, flow_noise: float = 0.02, temp_noise: float = 0.08) -> pd.DataFrame:
    cfg, T = out.cfg, len(out.ts)
    flow = out.flow_kgs * (1.0 + cfg.flow_bias) * (1.0 + rng.normal(0, flow_noise, T))
    design_flow = float((cfg.q_design_kw / (CP_KJ_KG_K * cfg.dt_design)).sum())
    flow = np.where(flow < 0.006 * design_flow, 0.0, flow)
    ts_m = out.t_ws + cfg.off_s + rng.normal(0, temp_noise, T)
    tr_m = out.t_ws + out.dt_p + cfg.off_r + rng.normal(0, temp_noise, T)
    energy = np.where(flow > 0, CP_KJ_KG_K * flow * np.maximum(tr_m - ts_m, 0.0), 0.0)
    df = pd.DataFrame({"timestamp": out.ts, "t_supply_c": ts_m, "t_return_c": tr_m, "flow_m3h": flow * 3.6,
                       "energy_kw": energy, "t_outdoor_c": out.t_out})
    if cfg.drop_frac > 0:
        keep = rng.random(T) >= cfg.drop_frac
        df = df[keep].reset_index(drop=True)
    return df


def make_sample_b(rng: np.random.Generator, building_id: int = 0, *, cfg: BuildingB | None = None,
                  causes: tuple[str, ...] | None = None, month: int | None = None, days: int = 30,
                  severity_scale: float = 1.0, climate_shift: float = 0.0, flow_noise: float = 0.02,
                  temp_noise: float = 0.08) -> Sample:
    from .scenarios import draw_cause_set
    cfg = cfg or sample_building_b(rng, building_id)
    causes = draw_cause_set(rng) if causes is None else causes
    month = int(rng.integers(1, 13)) if month is None else month
    ts = make_timestamps(month, days)
    t_out = synth_outdoor_temp(ts, rng, climate_shift)
    faults = sample_faults_b(cfg, rng, causes, severity_scale)
    drv = make_drivers_b(cfg, ts, t_out, faults, rng)
    out = physics_b(cfg, faults, drv)
    dt_actual = out.dt_period
    dt_healthy = physics_b(cfg, FaultsB.healthy(cfg.n_ahu), drv).dt_period
    gains, present = {}, {}
    for c in CAUSES:
        if c in causes:
            g = physics_b(cfg, faults.without(c), drv).dt_period - dt_actual
        else:
            g = 0.0
        gains[c] = float(max(g, 0.0))
        present[c] = bool(c in causes and gains[c] >= PRESENT_THRESHOLD_C)
    sub = ""
    if "constant_flow" in causes and faults.cf_mask.any():
        st = faults.cf_stuck[faults.cf_mask]
        sub = "stuck_open" if st.all() else ("three_way" if (~st).all() else "mixed")
    frame = measure_b(out, rng, flow_noise, temp_noise)
    return Sample(frame=frame, present=present, gains=gains, gain_all=float(max(dt_healthy - dt_actual, 0.0)),
                  dt_actual=dt_actual, dt_healthy=dt_healthy, causes_injected=tuple(causes), cf_subtype=sub,
                  unmet_kwh=0.0, cfg=cfg, month=month)
