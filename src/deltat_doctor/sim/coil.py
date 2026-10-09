"""Chilled-water cooling coil model (effectiveness-NTU, counterflow).

All quantities SI: kW, kW/K, kg/s, deg C. Arrays broadcast, so one call solves
every (timestep, AHU) pair at once.
"""
from __future__ import annotations

import numpy as np

from .. import CP_KJ_KG_K as CP_W  # kJ/(kg K)


def eps_counterflow(ntu: np.ndarray, cr: np.ndarray) -> np.ndarray:
    """Counterflow effectiveness, valid for 0 <= cr <= 1."""
    ntu = np.asarray(ntu, dtype=float)
    cr = np.clip(np.asarray(cr, dtype=float), 0.0, 1.0)
    one_minus = 1.0 - cr
    expo = np.exp(-ntu * one_minus)
    with np.errstate(divide="ignore", invalid="ignore"):
        eps = (1.0 - expo) / (1.0 - cr * expo)
    near_one = one_minus < 1e-6
    eps = np.where(near_one, ntu / (1.0 + ntu), eps)
    return np.clip(eps, 0.0, 1.0)


class CoilDesign:
    """Design-point description of one or many coils (arrays of length N)."""

    def __init__(self, q_design_kw, dt_design, t_ai_design=27.0, t_sa=13.0,
                 t_ws=6.0, r_air_share=0.6):
        self.q_d = np.asarray(q_design_kw, dtype=float)
        self.dt_d = np.asarray(dt_design, dtype=float)
        self.t_sa = float(t_sa)
        self.t_ws_d = float(t_ws)
        self.m_d = self.q_d / (CP_W * self.dt_d)  # kg/s
        c_w = self.m_d * CP_W
        c_air = self.q_d / (t_ai_design - t_sa)
        c_min = np.minimum(c_air, c_w)
        c_max = np.maximum(c_air, c_w)
        eps_d = self.q_d / (c_min * (t_ai_design - t_ws))
        eps_d = np.clip(eps_d, 0.05, 0.97)
        cr = c_min / c_max
        # invert eps(NTU) numerically (bisection, vectorised)
        lo = np.zeros_like(eps_d)
        hi = np.full_like(eps_d, 60.0)
        for _ in range(60):
            mid = 0.5 * (lo + hi)
            e = eps_counterflow(mid, cr)
            hi = np.where(e > eps_d, mid, hi)
            lo = np.where(e > eps_d, lo, mid)
        ntu_d = 0.5 * (lo + hi)
        ua_d = ntu_d * c_min  # kW/K
        r_total = 1.0 / ua_d
        self.r_air = r_air_share * r_total
        self.r_water = (1.0 - r_air_share) * r_total


def coil_duty(design: CoilDesign, m_w, c_air, t_ai, t_ws, foul):
    """Heat removed by the coil (kW) for water flow m_w (kg/s)."""
    m_w = np.asarray(m_w, dtype=float)
    c_w = np.maximum(m_w * CP_W, 1e-9)
    c_air = np.maximum(np.asarray(c_air, dtype=float), 1e-9)
    c_min = np.minimum(c_air, c_w)
    c_max = np.maximum(c_air, c_w)
    cr = c_min / c_max
    ratio = np.maximum(design.m_d / np.maximum(m_w, 1e-9 * design.m_d), 1e-6)
    r_foul = foul * (design.r_air + design.r_water)
    r = design.r_air + design.r_water * ratio ** 0.8 + r_foul
    ua = 1.0 / r
    ntu = ua / c_min
    eps = eps_counterflow(ntu, cr)
    q = eps * c_min * np.maximum(t_ai - t_ws, 0.0)
    return np.where(m_w <= 0, 0.0, q)


def solve_flow(design: CoilDesign, q_dem, c_air, t_ai, t_ws, foul, cap=1.6):
    """Water flow (kg/s) a ideal controller needs to meet q_dem.

    Returns (m, q_delivered). When even `cap * m_design` cannot meet the demand
    (badly fouled coil) the valve saturates and delivered < demand.
    """
    q_dem = np.asarray(q_dem, dtype=float)
    shape = np.broadcast(q_dem, design.m_d, foul, t_ai).shape
    lo = np.zeros(shape)
    hi = np.broadcast_to(cap * design.m_d, shape).astype(float).copy()
    q_hi = coil_duty(design, hi, c_air, t_ai, t_ws, foul)
    saturated = q_hi < q_dem
    for _ in range(40):
        mid = 0.5 * (lo + hi)
        q = coil_duty(design, mid, c_air, t_ai, t_ws, foul)
        too_low = q < q_dem
        lo = np.where(too_low, mid, lo)
        hi = np.where(too_low, hi, mid)
    m = 0.5 * (lo + hi)
    m = np.where(saturated, cap * design.m_d, m)
    m = np.where(q_dem <= 1e-9, 0.0, m)
    q_del = coil_duty(design, m, c_air, t_ai, t_ws, foul)
    return m, q_del
