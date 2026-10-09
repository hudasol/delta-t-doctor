"""Delta-T surcharge calculator.

Default rule is taken from a published district-cooling operator FAQ: the
building must return a delta-T of at least 8.9 deg C, and the operator may add
10% to the consumption charge for each degree Celsius the building differential
is below that minimum. Operators and contracts differ, so every term here is a
parameter. `rate_aed_per_rt_hr` has no universal default: the value used in the
demo is illustrative only and MUST be replaced with the contract rate.
"""
from __future__ import annotations

from dataclasses import dataclass, asdict

import numpy as np
import pandas as pd

from . import CP_KJ_KG_K

KW_PER_RT = 3.517


@dataclass
class ContractTerms:
    min_delta_t_c: float = 8.9
    surcharge_pct_per_degree: float = 0.10
    rate_aed_per_rt_hr: float = 0.40     # ILLUSTRATIVE - replace with your contract rate

    def to_dict(self) -> dict:
        return asdict(self)


def window_penalty(dt_c: float, rt_hr: float, terms: ContractTerms) -> dict:
    """Surcharge for one billing window given its flow-weighted delta-T and energy."""
    charge = rt_hr * terms.rate_aed_per_rt_hr
    shortfall = max(0.0, terms.min_delta_t_c - dt_c)
    pct = terms.surcharge_pct_per_degree * shortfall
    return {
        "delta_t_c": dt_c, "shortfall_c": shortfall, "surcharge_pct": 100 * pct,
        "consumption_charge_aed": charge, "surcharge_aed": charge * pct,
    }


def saving_from_gain(dt_c: float, gain_c: float, rt_hr: float, terms: ContractTerms) -> float:
    """AED saved in one window if delta-T improves by `gain_c`."""
    before = window_penalty(dt_c, rt_hr, terms)["surcharge_aed"]
    after = window_penalty(dt_c + max(gain_c, 0.0), rt_hr, terms)["surcharge_aed"]
    return max(before - after, 0.0)


def monthly_table(h: pd.DataFrame, terms: ContractTerms) -> pd.DataFrame:
    """Calendar-month penalty table from a canonical hourly frame."""
    d = h.copy()
    d["month"] = pd.DatetimeIndex(d["timestamp"]).to_period("M")
    rows = []
    for m, g in d.groupby("month"):
        f = g["flow_kgs"].sum()
        heat = g["heat_kw"].sum()  # kW * 1 h = kWh (hourly rows)
        dt = heat / (CP_KJ_KG_K * f) if f > 0 else np.nan
        rt_hr = heat / KW_PER_RT
        p = window_penalty(float(dt) if np.isfinite(dt) else terms.min_delta_t_c, rt_hr, terms)
        p.update({"month": str(m), "rt_hr": rt_hr, "hours": len(g)})
        rows.append(p)
    return pd.DataFrame(rows)
