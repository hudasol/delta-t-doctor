"""World D: a third, dynamic physics, written to test the transfer and guard claims (see docs/research/WORLD_D.md).

Simulators A and B are quasi-steady: every hour is solved on its own. World D is time stepped (5 minute steps, aggregated to the
hourly meter) and closed loop, so its meter signatures come out of control dynamics rather than from a fault formula:

* Each zone has thermal mass (a lumped capacity with a time constant of 1 to 6 hours). Cooling demand is not prescribed; it is
  whatever the coil removes while the controller tries to hold the zone set point.
* Each AHU runs the usual cascade: a slow zone reset sets a discharge air set point, and a digital PI controller with a 5 minute scan
  drives the coil valve on discharge air temperature, through a sensor lag, an actuator with a first order lag and a deadband. 40% of
  valves are linear and 60% equal percentage; valve flow grows with the square root of the differential pressure across it, so a linear
  valve's loop gain at low load rises with excess pressure.
* The coil is a characteristic curve coil (capacity proportional to flow to a power of 0.35 to 0.6 and to the entering temperature
  difference), not an effectiveness NTU or enthalpy model.
* A variable speed pump holds a differential pressure set point; at its minimum speed the pump curve, not the set point, decides the
  pressure, so pressure rises at low flow.
* The ETS is a counterflow plate exchanger whose primary flow is set to hold the secondary supply set point; the meter is on the
  primary side.

Faults act on these components:

* fouling        coil capacity divided by (1 + f)
* passing_valves a closed valve still passes a fraction of its capacity, scaled by the square root of the pressure
* constant_flow  a 3-way valve (branch flow fixed at design, coil flow modulated, bypass mixes into the return) or an actuator stuck
                 at a fixed position
* overflow       a differential pressure set point well above need, sometimes with an oversized valve. The higher valve gain can make
                 the PI loop oscillate (hunt) at low load, and the minimum controllable flow rises.

Nothing here was tuned against the other simulators or the shipped model. Shared with A and B: the synthetic outdoor temperature
(`weather.py`), the counterflow effectiveness formula for the plate exchanger, the 0.20 C "present" threshold and the Sample record.
"""
from __future__ import annotations

from dataclasses import dataclass, replace

import numpy as np
import pandas as pd

from .. import CAUSES, CP_KJ_KG_K
from .coil import eps_counterflow
from .scenarios import PRESENT_THRESHOLD_C, Sample, draw_cause_set
from .weather import make_timestamps, synth_outdoor_temp

BUILDING_TYPES_D = ("office", "hotel", "residential", "mall", "school", "clinic")
STEP_S = 300.0                 # 5 minute integration step
SUB = int(3600 / STEP_S)       # steps per hour
WARMUP_H = 48                  # simulated before the window starts, then discarded
VALVE_R = 30.0                 # equal percentage rangeability
X_SHUT = 0.02                  # positions below this are treated as shut (only seat leakage passes)


@dataclass
class BuildingD:
    building_type: str
    q_design_kw: np.ndarray        # (N,) coil design duty
    dt_design: np.ndarray          # (N,) coil design water delta-T
    coil_a: np.ndarray             # (N,) coil characteristic exponent on flow
    tau_zone_h: np.ndarray         # (N,) zone thermal time constant
    t_set: np.ndarray              # (N,) zone set point, C
    oa_frac: np.ndarray            # (N,) outdoor air fraction
    kp: np.ndarray                 # (N,) discharge air PI gain, valve fraction per K
    ti_s: np.ndarray               # (N,) discharge air PI integral time, s
    k_reset: np.ndarray            # (N,) zone reset of the discharge air set point, K per K of zone error
    sensor_tau_s: np.ndarray       # (N,) discharge air sensor and coil lag, s
    act_tau_s: np.ndarray          # (N,) actuator lag, s
    deadband: np.ndarray           # (N,) actuator deadband, valve fraction
    linear_valve: np.ndarray       # (N,) bool: linear characteristic (else equal percentage)
    oversize: np.ndarray           # (N,) valve capacity over design flow at design pressure
    dp_need_kpa: float             # pressure the index branch needs at design flow
    pump_min_speed: float
    hx_ntu: float                  # plate exchanger NTU at design flow
    t_ps_nom: float                # primary supply temperature
    t_ss_offset: float             # secondary supply set point above primary supply
    off_s: float
    off_r: float
    flow_bias: float
    drop_frac: float
    building_id: int = 0

    @property
    def n_ahu(self) -> int:
        return len(self.q_design_kw)


@dataclass
class FaultsD:
    foul: np.ndarray               # (N,)
    leak: np.ndarray               # (N,) seat leakage as a fraction of valve capacity
    cf_mask: np.ndarray            # (N,) bool
    cf_stuck: np.ndarray           # (N,) bool: True = actuator stuck, False = 3-way valve
    cf_pos: np.ndarray             # (N,) stuck position
    dp_ratio: float = 1.0          # differential pressure set point over need
    ov_extra: np.ndarray | None = None   # (N,) extra valve oversize factor (1 = none)

    @staticmethod
    def healthy(n: int) -> "FaultsD":
        z, b = np.zeros(n), np.zeros(n, dtype=bool)
        return FaultsD(z.copy(), z.copy(), b.copy(), b.copy(), z.copy(), 1.0, np.ones(n))

    def without(self, cause: str) -> "FaultsD":
        h = FaultsD.healthy(len(self.foul))
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


def sample_building_d(rng: np.random.Generator, building_id: int = 0) -> BuildingD:
    btype = BUILDING_TYPES_D[rng.integers(len(BUILDING_TYPES_D))]
    n = int(rng.integers(4, 26))
    q_total = float(np.exp(rng.uniform(np.log(350.0), np.log(7000.0))))
    q = q_total * rng.dirichlet(np.full(n, 3.0))
    dt = np.clip(rng.uniform(5.0, 12.5) + rng.normal(0, 0.6, n), 4.0, 14.0)
    return BuildingD(
        building_type=btype, q_design_kw=q, dt_design=dt, coil_a=rng.uniform(0.35, 0.6, n),
        tau_zone_h=rng.uniform(1.0, 6.0, n), t_set=rng.uniform(22.0, 24.5, n),
        oa_frac=np.clip(rng.normal(0.15, 0.05, n), 0.05, 0.3),
        kp=rng.uniform(0.03, 0.12, n), ti_s=rng.uniform(180.0, 900.0, n), k_reset=rng.uniform(1.0, 3.0, n),
        sensor_tau_s=rng.uniform(60.0, 240.0, n),
        act_tau_s=rng.uniform(60.0, 480.0, n), deadband=rng.uniform(0.005, 0.04, n), linear_valve=rng.random(n) < 0.4,
        oversize=rng.uniform(1.05, 1.6, n), dp_need_kpa=float(rng.uniform(40.0, 90.0)),
        pump_min_speed=float(rng.uniform(0.3, 0.55)), hx_ntu=float(rng.uniform(2.5, 6.0)),
        t_ps_nom=float(rng.uniform(4.5, 6.5)), t_ss_offset=float(rng.uniform(0.8, 2.0)),
        off_s=float(np.clip(rng.normal(0, 0.12), -0.3, 0.3)), off_r=float(np.clip(rng.normal(0, 0.12), -0.3, 0.3)),
        flow_bias=float(rng.normal(0, 0.02)), drop_frac=float(rng.uniform(0.0, 0.04)), building_id=building_id,
    )


def sample_faults_d(cfg: BuildingD, rng: np.random.Generator, causes: tuple[str, ...], severity_scale: float = 1.0) -> FaultsD:
    n = cfg.n_ahu
    f = FaultsD.healthy(n)

    def pick(lo, hi):
        k = max(1, int(round(rng.uniform(lo, hi) * n)))
        m = np.zeros(n, dtype=bool)
        m[rng.choice(n, size=min(k, n), replace=False)] = True
        return m

    if "fouling" in causes:
        f.foul = np.where(pick(0.3, 1.0), rng.uniform(0.2, 1.5, n) * severity_scale, 0.0)
    if "passing_valves" in causes:
        f.leak = np.where(pick(0.15, 0.7), rng.uniform(0.03, 0.2, n) * severity_scale, 0.0)
    if "constant_flow" in causes:
        m = pick(0.15, 0.8)
        f.cf_mask = m
        f.cf_stuck = m & (rng.random(n) < rng.uniform(0, 1))
        f.cf_pos = np.where(f.cf_stuck, rng.uniform(0.4, 1.0, n), 0.0)
    if "overflow" in causes:
        f.dp_ratio = float(1.0 + rng.uniform(0.4, 1.6) * severity_scale)
        f.ov_extra = np.where(pick(0.0, 0.8) & (rng.random() < 0.5), rng.uniform(1.2, 1.8, n), 1.0)
    return f


def _occupancy(btype: str, hours: np.ndarray, dow: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """(occupancy 0..1, plant enabled) for each step. hours are fractional hours of day."""
    wk = dow < 5
    if btype == "office":
        on = (hours >= 6.5) & (hours < 19) & wk
        occ = on * np.where((hours >= 8) & (hours < 17.5), 1.0, 0.5)
    elif btype == "school":
        on = (hours >= 6.5) & (hours < 15.5) & wk
        occ = on * 0.95
    elif btype == "mall":
        on = (hours >= 9) | (hours < 0.5)
        occ = on * np.where(hours >= 16, 1.0, 0.7)
    elif btype == "clinic":
        on = np.ones_like(hours, dtype=bool)
        occ = np.where((hours >= 7) & (hours < 21), 0.9, 0.35)
    elif btype == "hotel":
        on = np.ones_like(hours, dtype=bool)
        occ = 0.5 + 0.35 * np.cos(2 * np.pi * (hours - 21) / 24.0) ** 2
    else:
        on = np.ones_like(hours, dtype=bool)
        occ = 0.4 + 0.5 * np.cos(2 * np.pi * (hours - 21.5) / 24.0) ** 2
    return np.clip(occ, 0, 1), on


@dataclass
class DriversD:
    ts: pd.DatetimeIndex           # hourly timestamps of the window
    t_out_h: np.ndarray            # hourly outdoor temperature (window)
    t_out: np.ndarray              # (S,) per step, warm-up included
    occ: np.ndarray                # (S,)
    on: np.ndarray                 # (S,) bool
    sun: np.ndarray                # (S,) 0..1
    t_ps: np.ndarray               # (S,) primary supply temperature
    z0: np.ndarray                 # (N,) initial zone temperature offset


def make_drivers_d(cfg: BuildingD, ts: pd.DatetimeIndex, t_out_h: np.ndarray, rng: np.random.Generator) -> DriversD:
    n_h = len(ts) + WARMUP_H
    t_full = np.concatenate([np.full(WARMUP_H, t_out_h[:24].mean()), t_out_h])
    t_step = np.interp(np.arange(n_h * SUB) / SUB, np.arange(n_h), t_full)
    start = ts[0] - pd.Timedelta(hours=WARMUP_H)
    stamps = start + pd.to_timedelta(np.arange(n_h * SUB) * STEP_S, unit="s")
    hours = stamps.hour.values + stamps.minute.values / 60.0
    occ, on = _occupancy(cfg.building_type, hours, stamps.dayofweek.values)
    sun = np.clip(np.sin(np.pi * (hours - 6.0) / 13.0), 0.0, 1.0) * rng.uniform(0.7, 1.0)
    walk = np.zeros(n_h)
    for t in range(1, n_h):
        walk[t] = 0.96 * walk[t - 1] + rng.normal(0, 0.05)
    t_ps = np.repeat(np.clip(cfg.t_ps_nom + walk, 4.0, 7.5), SUB)
    return DriversD(ts, t_out_h, t_step, occ, on, sun, t_ps, rng.normal(0, 0.5, cfg.n_ahu))


@dataclass
class PhysicsD:
    flow_kgs: np.ndarray           # hourly primary flow
    heat_kw: np.ndarray            # hourly heat
    t_ps: np.ndarray               # hourly primary supply temperature
    cfg: BuildingD
    ts: pd.DatetimeIndex
    t_out: np.ndarray
    flow_step: np.ndarray | None = None   # secondary flow at every 5 minute step of the window (for inspecting hunting)

    @property
    def dt_period(self) -> float:
        f = self.flow_kgs.sum()
        return float(self.heat_kw.sum() / (CP_KJ_KG_K * f)) if f > 0 else float("nan")


def physics_d(cfg: BuildingD, f: FaultsD, drv: DriversD) -> PhysicsD:
    return physics_d_batch(cfg, [f], drv)[0]


def physics_d_batch(cfg: BuildingD, fs: list, drv: DriversD) -> list:
    """Simulate several fault variants of one building on the same drivers in one time loop (rows of a (K, N) state).

    The variants do not interact; batching only shares the Python loop, which is what makes the counterfactual labels affordable.
    """
    n, K = cfg.n_ahu, len(fs)
    q_d, a = cfg.q_design_kw, cfg.coil_a
    m_d = q_d / (CP_KJ_KG_K * cfg.dt_design)
    t_ws_d = cfg.t_ps_nom + cfg.t_ss_offset
    t_ai_d = 26.0
    stack = lambda name: np.vstack([np.broadcast_to(getattr(f, name), (n,)) for f in fs])
    foul, leak, ov = stack("foul"), stack("leak"), stack("ov_extra")
    cf_mask, cf_stuck, cf_pos = stack("cf_mask").astype(bool), stack("cf_stuck").astype(bool), stack("cf_pos")
    three_way = cf_mask & ~cf_stuck
    cap = 1.0 / (1.0 + foul)                                # fouling divides coil capacity
    m_vs = m_d * cfg.oversize * ov                          # valve capacity at the design pressure
    c_zone = q_d * cfg.tau_zone_h * 3600.0 / 10.0           # kJ/K: full design imbalance moves the zone 10 K per time constant
    dp_need = cfg.dp_need_kpa
    dp_set = dp_need * np.array([f.dp_ratio for f in fs])   # (K,)
    m_tot_d = float(m_d.sum())
    h0 = 1.35 * dp_need                                     # pump shut-off head at full speed, kPa
    k_pipe = 0.35 * dp_need / m_tot_d ** 2                  # pump curve drop with flow
    h_min = h0 * cfg.pump_min_speed ** 2

    S = len(drv.t_out)
    tz = np.tile(cfg.t_set + drv.z0, (K, 1))
    integ = np.zeros((K, n))
    x = np.zeros((K, n))
    dat_m = np.full((K, n), 14.0)                           # measured discharge air temperature
    m_prev_tot = np.full(K, 0.3 * m_tot_d)
    flow_s = np.zeros((S, K))
    heat_s = np.zeros((S, K))
    alpha = 1.0 - np.exp(-STEP_S / cfg.act_tau_s)
    beta = 1.0 - np.exp(-STEP_S / cfg.sensor_tau_s)
    ki = cfg.kp * STEP_S / cfg.ti_s
    w_dt = 1.0 / (t_ai_d - t_ws_d)
    c_air_d = q_d / (t_ai_d - 13.0)                         # air capacity rate at design, kW/K
    zeros = np.zeros((K, n))
    for s in range(S):
        on = drv.on[s]
        t_out = drv.t_out[s]
        t_ws = drv.t_ps[s] + cfg.t_ss_offset
        # pressure at the branches: the set point, or the pump curve at minimum speed when that is higher
        dp = np.maximum(dp_set, h_min - k_pipe * m_prev_tot ** 2)
        g = np.sqrt(dp / dp_need)[:, None]
        # Cascade: a slow zone reset sets the discharge air set point; a digital PI (5 minute scan) drives the valve on discharge air
        # temperature, with anti-windup. Everything is off when the plant schedule is off.
        if on:
            dat_set = np.clip(14.0 - cfg.k_reset * (tz - cfg.t_set), 10.0, 18.0)
            err = dat_m - dat_set
            u = cfg.kp * err + integ
            sat = ((u >= 1.0) & (err > 0)) | ((u <= 0.0) & (err < 0))
            integ = np.where(sat, integ, integ + ki * err)
            u = np.clip(u, 0.0, 1.0)
        else:
            u = zeros
            integ = zeros
        u = np.where(cf_stuck, cf_pos, u)
        move = np.abs(u - x) > cfg.deadband
        x = np.where(cf_stuck, cf_pos, np.where(move, x + alpha * (u - x), x))
        phi = np.where(x > X_SHUT, np.where(cfg.linear_valve, x, VALVE_R ** (x - 1.0)), 0.0)
        m_coil = m_vs * g * (phi + leak)
        # coil: characteristic curve, limited by the air and water capacity; air side nearly idle when the fan is off
        t_ai = (1 - cfg.oa_frac) * tz + cfg.oa_frac * t_out
        c_air = c_air_d * (1.0 if on else 0.04)
        dT_in = np.maximum(t_ai - t_ws, 0.0)
        q = q_d * cap * (1.0 if on else 0.04) * np.power(np.maximum(m_coil / m_d, 0.0), a) * dT_in * w_dt
        q = np.minimum(q, 0.95 * dT_in * np.minimum(CP_KJ_KG_K * m_coil, c_air))
        dat = t_ai - q / c_air
        dat_m = dat_m + beta * (dat - dat_m)
        # 3-way valves: the branch passes design flow at design pressure; the bypass carries the rest at supply temperature
        m_branch = np.where(three_way, np.maximum(m_d * g, m_coil), m_coil)
        # zone energy balance
        gain = q_d * (0.40 * drv.occ[s] * on + 0.45 * (t_out - tz) / 22.0 + 0.20 * drv.sun[s])
        tz = tz + STEP_S * (np.maximum(gain, -0.3 * q_d) - q) / c_zone
        m_prev_tot = m_branch.sum(axis=1)
        flow_s[s] = m_prev_tot
        heat_s[s] = q.sum(axis=1)

    w0 = WARMUP_H * SUB
    t_ps_h = drv.t_ps[w0:].reshape(-1, SUB).mean(1)
    out = []
    for k in range(K):
        fl = flow_s[w0:, k].reshape(-1, SUB).mean(1)
        ht = heat_s[w0:, k].reshape(-1, SUB).mean(1)
        # ETS: counterflow plate exchanger, primary flow set so the secondary leaves at its set point (hourly, quasi-steady)
        t_sr = t_ps_h + cfg.t_ss_offset + np.where(fl > 1e-9, ht / (CP_KJ_KG_K * np.maximum(fl, 1e-9)), 0.0)
        m_p = _primary_flow(ht, fl, t_sr, t_ps_h, cfg.hx_ntu * m_tot_d * CP_KJ_KG_K, 1.4 * m_tot_d)
        out.append(PhysicsD(m_p, np.where(m_p > 0, ht, 0.0), t_ps_h, cfg, drv.ts, drv.t_out_h, flow_s[w0:, k].copy()))
    return out


def _primary_flow(q, m_s, t_sr, t_ps, ua, m_max):
    """Primary flow that transfers q through a counterflow exchanger with conductance ua (bisection, vectorised over hours)."""
    c_s = np.maximum(m_s * CP_KJ_KG_K, 1e-9)
    lo, hi = np.zeros_like(q), np.full_like(q, m_max)

    def duty(m):
        c_p = np.maximum(m * CP_KJ_KG_K, 1e-9)
        cmin, cmax = np.minimum(c_s, c_p), np.maximum(c_s, c_p)
        return eps_counterflow(ua / cmin, cmin / cmax) * cmin * np.maximum(t_sr - t_ps, 0.0)

    for _ in range(40):
        mid = 0.5 * (lo + hi)
        low = duty(mid) < q
        lo, hi = np.where(low, mid, lo), np.where(low, hi, mid)
    return np.where(q > 1e-6, 0.5 * (lo + hi), 0.0)


def measure_d(out: PhysicsD, rng: np.random.Generator, flow_noise: float = 0.015, temp_noise: float = 0.08) -> pd.DataFrame:
    cfg, T = out.cfg, len(out.ts)
    flow = out.flow_kgs * (1.0 + cfg.flow_bias) * (1.0 + rng.normal(0, flow_noise, T))
    design_flow = float((cfg.q_design_kw / (CP_KJ_KG_K * cfg.dt_design)).sum())
    flow = np.where(flow < 0.005 * design_flow, 0.0, flow)
    with np.errstate(divide="ignore", invalid="ignore"):
        dt_p = np.where(out.flow_kgs > 1e-6, out.heat_kw / (CP_KJ_KG_K * out.flow_kgs), 0.0)
    ts_m = out.t_ps + cfg.off_s + rng.normal(0, temp_noise, T)
    tr_m = out.t_ps + dt_p + cfg.off_r + rng.normal(0, temp_noise, T)
    energy = np.where(flow > 0, CP_KJ_KG_K * flow * np.maximum(tr_m - ts_m, 0.0), 0.0)
    df = pd.DataFrame({"timestamp": out.ts, "t_supply_c": ts_m, "t_return_c": tr_m, "flow_m3h": flow * 3.6,
                       "energy_kw": energy, "t_outdoor_c": out.t_out})
    if cfg.drop_frac > 0:
        df = df[rng.random(T) >= cfg.drop_frac].reset_index(drop=True)
    return df


def make_sample_d(rng: np.random.Generator, building_id: int = 0, *, cfg: BuildingD | None = None,
                  causes: tuple[str, ...] | None = None, month: int | None = None, days: int = 30,
                  severity_scale: float = 1.0, climate_shift: float = 0.0, flow_noise: float = 0.015,
                  temp_noise: float = 0.08) -> Sample:
    cfg = cfg or sample_building_d(rng, building_id)
    causes = draw_cause_set(rng) if causes is None else causes
    month = int(rng.integers(1, 13)) if month is None else month
    ts = make_timestamps(month, days)
    t_out = synth_outdoor_temp(ts, rng, climate_shift)
    faults = sample_faults_d(cfg, rng, causes, severity_scale)
    drv = make_drivers_d(cfg, ts, t_out, rng)
    variants = [faults] + ([FaultsD.healthy(cfg.n_ahu)] + [faults.without(c) for c in CAUSES if c in causes] if causes else [])
    runs = physics_d_batch(cfg, variants, drv)
    out = runs[0]
    dt_actual = out.dt_period
    dt_healthy = runs[1].dt_period if causes else dt_actual
    without = dict(zip([c for c in CAUSES if c in causes], runs[2:]))
    gains, present = {}, {}
    for c in CAUSES:
        g = without[c].dt_period - dt_actual if c in causes else 0.0
        gains[c] = float(max(g, 0.0))
        present[c] = bool(c in causes and gains[c] >= PRESENT_THRESHOLD_C)
    sub = ""
    if "constant_flow" in causes and faults.cf_mask.any():
        st = faults.cf_stuck[faults.cf_mask]
        sub = "stuck_open" if st.all() else ("three_way" if (~st).all() else "mixed")
    frame = measure_d(out, rng, flow_noise, temp_noise)
    return Sample(frame=frame, present=present, gains=gains, gain_all=float(max(dt_healthy - dt_actual, 0.0)),
                  dt_actual=dt_actual, dt_healthy=dt_healthy, causes_injected=tuple(causes), cf_subtype=sub,
                  unmet_kwh=0.0, cfg=cfg, month=month)
