"""Domain-randomised worlds C-A and C-B: simulator A or B physics with a much wider randomisation envelope.

These test whether training on a broader envelope helps transfer to the *other* physics. They contain no physics the base
simulator lacks, apart from sensor offsets, dropped hours and a wider ETS loss on the A side. See docs/TRANSFER_V2.md.
"""
from __future__ import annotations

from dataclasses import replace

import numpy as np

from .hydraulic import make_sample_b, sample_building_b
from .scenarios import Sample, make_sample, sample_building


def wide_building_a(rng: np.random.Generator, building_id: int):
    cfg = sample_building(rng, building_id)
    n = cfg.n_ahu
    return replace(cfg, t_supply_nom=float(rng.uniform(4.5, 8.0)), ets_loss=float(rng.uniform(0.0, 1.0)),
                   flow_bias=float(rng.normal(0, 0.04)), dt_cap=np.clip(cfg.dt_cap + rng.normal(0, 0.7, n), 3.0, 15.0))


def wide_building_b(rng: np.random.Generator, building_id: int):
    cfg = sample_building_b(rng, building_id)
    n = cfg.n_ahu
    return replace(cfg, valve_oversize=cfg.valve_oversize * rng.uniform(0.8, 1.6), x_min=rng.uniform(0.02, 0.30, n),
                   hx_k=float(rng.uniform(0.1, 1.5)), t_supply_nom=float(rng.uniform(4.5, 8.0)),
                   off_s=float(np.clip(rng.normal(0, 0.2), -0.4, 0.4)), off_r=float(np.clip(rng.normal(0, 0.2), -0.4, 0.4)),
                   flow_bias=float(rng.normal(0, 0.04)), drop_frac=float(rng.uniform(0.0, 0.12)))


def wide_kwargs(rng: np.random.Generator) -> dict:
    return {"flow_noise": float(rng.uniform(0.005, 0.05)), "temp_noise": float(rng.uniform(0.05, 0.35)),
            "severity_scale": float(rng.uniform(0.5, 1.8)), "climate_shift": float(rng.uniform(-4, 4)),
            "days": int(rng.integers(21, 46))}


def make_sample_world(base: str, rng: np.random.Generator, building_id: int, cfg) -> Sample:
    kw = wide_kwargs(rng)
    if base == "A":
        s = make_sample(rng, building_id, cfg=cfg, **kw)
        f = s.frame.copy()
        f["t_supply_c"] = f["t_supply_c"] + rng.normal(0, 0.2) + 0.0
        f["t_return_c"] = f["t_return_c"] + rng.normal(0, 0.2)
        drop = rng.uniform(0.0, 0.12)
        if drop > 0:
            f = f[rng.random(len(f)) >= drop].reset_index(drop=True)
        s.frame = f
        return s
    return make_sample_b(rng, building_id, cfg=cfg, **kw)
