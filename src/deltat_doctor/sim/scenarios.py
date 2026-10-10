"""Random building / fault scenario sampling and counterfactual ground truth."""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from .. import CAUSES
from .building import (BUILDING_TYPES, BuildingConfig, FaultSpec, PhysicsOut,
                       make_drivers, measure, physics)
from .weather import make_timestamps, synth_outdoor_temp

DESIGN_DT_RANGE_C = (5.0, 12.2)   # buildings are designed for anywhere in this range (v0.2; v0.1 used 9.0-12.2)
PRESENT_THRESHOLD_C = 0.20   # a cause counts as "present" if fixing it recovers >= this


def sample_building(rng: np.random.Generator, building_id: int = 0) -> BuildingConfig:
    btype = BUILDING_TYPES[rng.integers(len(BUILDING_TYPES))]
    n = int(rng.integers(6, 31))
    q_total = float(np.exp(rng.uniform(np.log(400.0), np.log(6000.0))))  # kW, ~115-1700 RT
    share = rng.dirichlet(np.full(n, 4.0))
    q_d = q_total * share
    dt_d_b = rng.uniform(*DESIGN_DT_RANGE_C)
    dt_d = np.clip(dt_d_b + rng.normal(0, 0.5, n), DESIGN_DT_RANGE_C[0] - 0.5, 13.5)
    # Healthy part-load ceiling on coil delta-T. It may sit BELOW design: real healthy buildings often run under their
    # design delta-T (valve authority, hysteresis, flow floors). It was always above design before v1.1.
    dt_cap = np.clip(dt_d + rng.uniform(-1.8, 1.5) + rng.normal(0, 0.3, n), 3.5, 14.5)
    return BuildingConfig(
        building_type=btype, q_design_kw=q_d, dt_design=dt_d, dt_cap=dt_cap,
        t_supply_nom=float(rng.uniform(5.0, 7.0)),
        ets_loss=float(rng.uniform(0.0, 0.5)),
        flow_bias=float(rng.normal(0, 0.015)),
        building_id=building_id,
    )


def sample_faults(cfg: BuildingConfig, rng: np.random.Generator,
                  causes: tuple[str, ...], severity_scale: float = 1.0) -> FaultSpec:
    n = cfg.n_ahu
    f = FaultSpec.healthy(n)

    def pick(frac_lo, frac_hi):
        frac = rng.uniform(frac_lo, frac_hi)
        k = max(1, int(round(frac * n)))
        mask = np.zeros(n, dtype=bool)
        mask[rng.choice(n, size=min(k, n), replace=False)] = True
        return mask

    if "fouling" in causes:
        m = pick(0.3, 1.0)
        f.foul = np.where(m, rng.uniform(0.15, 1.2, n) * severity_scale, 0.0)
    if "passing_valves" in causes:
        m = pick(0.15, 0.7)
        f.leak_frac = np.where(m, rng.uniform(0.04, 0.30, n) * severity_scale, 0.0)
    if "constant_flow" in causes:
        m = pick(0.15, 0.8)
        f.cf_mask = m
        p_stuck = rng.uniform(0.0, 1.0)
        f.cf_stuck = m & (rng.random(n) < p_stuck)
        f.cf_pos = np.where(f.cf_stuck, rng.uniform(0.4, 1.0, n), 0.0)
    if "overflow" in causes:
        m = pick(0.3, 1.0)
        f.overflow_k = np.where(m, rng.uniform(0.2, 1.5, n) * severity_scale, 0.0)
    return f


def meter_delta_t(out: PhysicsOut) -> float:
    return out.delta_t_period - out.cfg.ets_loss


@dataclass
class Sample:
    frame: pd.DataFrame            # measured ETS data (what a real meter gives)
    present: dict                  # cause -> bool (gain >= threshold)
    gains: dict                    # cause -> delta-T gain (deg C) if that cause fixed
    gain_all: float                # gain if every fault fixed
    dt_actual: float
    dt_healthy: float
    causes_injected: tuple
    cf_subtype: str                # 'three_way' | 'stuck_open' | 'mixed' | ''
    unmet_kwh: float
    cfg: BuildingConfig
    month: int


def draw_cause_set(rng: np.random.Generator) -> tuple[str, ...]:
    r = rng.random()
    k = 0 if r < 0.30 else (1 if r < 0.70 else (2 if r < 0.92 else 3))
    if k == 0:
        return ()
    return tuple(str(c) for c in rng.choice(CAUSES, size=k, replace=False))


def make_sample(rng: np.random.Generator, building_id: int = 0, *,
                cfg: BuildingConfig | None = None, causes: tuple[str, ...] | None = None,
                month: int | None = None, days: int = 30,
                severity_scale: float = 1.0, climate_shift: float = 0.0,
                flow_noise: float = 0.015, temp_noise: float = 0.10) -> Sample:
    cfg = cfg or sample_building(rng, building_id)
    causes = draw_cause_set(rng) if causes is None else causes
    month = int(rng.integers(1, 13)) if month is None else month
    ts = make_timestamps(month, days)
    t_out = synth_outdoor_temp(ts, rng, climate_shift)
    drv = make_drivers(cfg, ts, t_out, rng)
    faults = sample_faults(cfg, rng, causes, severity_scale)

    out = physics(cfg, faults, drv)
    dt_actual = meter_delta_t(out)
    healthy_out = physics(cfg, FaultSpec.healthy(cfg.n_ahu), drv)
    dt_healthy = meter_delta_t(healthy_out)

    gains, present = {}, {}
    for c in CAUSES:
        injected = c in causes
        if injected:
            g = meter_delta_t(physics(cfg, faults.without(c), drv)) - dt_actual
        else:
            g = 0.0
        gains[c] = float(max(g, 0.0))
        present[c] = bool(injected and gains[c] >= PRESENT_THRESHOLD_C)

    sub = ""
    if "constant_flow" in causes and faults.cf_mask.any():
        st = faults.cf_stuck[faults.cf_mask]
        sub = "stuck_open" if st.all() else ("three_way" if (~st).all() else "mixed")

    frame = measure(out, rng, flow_noise=flow_noise, temp_noise=temp_noise)
    return Sample(frame=frame, present=present, gains=gains,
                  gain_all=float(max(dt_healthy - dt_actual, 0.0)),
                  dt_actual=dt_actual, dt_healthy=dt_healthy,
                  causes_injected=tuple(causes), cf_subtype=sub,
                  unmet_kwh=float(out.unmet_kw.sum()), cfg=cfg, month=month)
