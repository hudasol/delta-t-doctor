"""Synthetic Dubai-like hourly outdoor temperature.

This is a stylised climate (monthly means + diurnal cycle + day-to-day AR(1)
noise) so the simulator has realistic seasonal load swings. It is NOT measured
weather; swap in real data via `ets_frame['t_outdoor_c']` when diagnosing a
real building.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

# approximate climatological monthly mean air temperature, deg C (Jan..Dec)
DUBAI_MONTHLY_MEAN_C = np.array([19, 20, 23, 27, 32, 34, 36, 36, 33, 30, 25, 21], dtype=float)


def make_timestamps(month: int, days: int = 30, year: int = 2025) -> pd.DatetimeIndex:
    start = pd.Timestamp(year=year, month=month, day=1)
    return pd.date_range(start, periods=24 * days, freq="h")


def synth_outdoor_temp(ts: pd.DatetimeIndex, rng: np.random.Generator,
                       climate_shift: float = 0.0) -> np.ndarray:
    n = len(ts)
    month_idx = ts.month.values - 1
    mean = DUBAI_MONTHLY_MEAN_C[month_idx] + climate_shift
    hour = ts.hour.values + ts.minute.values / 60.0
    amp = 5.5 + 0.0 * mean
    diurnal = amp * np.sin(2 * np.pi * (hour - 9.0) / 24.0)  # peak ~15:00
    days = n // 24 + 2
    daily = np.zeros(days)
    for d in range(1, days):
        daily[d] = 0.7 * daily[d - 1] + rng.normal(0, 1.4)
    day_idx = np.arange(n) // 24
    noise = rng.normal(0, 0.4, n)
    return mean + diurnal + daily[day_idx] + noise
