import numpy as np
import pandas as pd
import pytest
from deltat_doctor.io import DataError, canonicalise


def _frame(hours=24 * 20, **cols):
    ts = pd.date_range("2025-07-01", periods=hours, freq="h")
    d = {"timestamp": ts}
    d.update(cols)
    return pd.DataFrame(d)


def test_temps_path_and_units():
    n = 24 * 20
    df = _frame(n, flow_m3h=np.full(n, 36.0), t_supply_c=np.full(n, 6.0), t_return_c=np.full(n, 14.0))
    h = canonicalise(df)
    assert abs(h["flow_kgs"].mean() - 10.0) < 1e-9          # 36 m3/h = 10 kg/s
    assert abs(h["dt_c"].mean() - 8.0) < 1e-9


def test_energy_path_matches_temperature_path():
    n = 24 * 20
    flow = np.full(n, 36.0)
    kw = 4.186 * 10.0 * 8.0
    a = canonicalise(_frame(n, flow_m3h=flow, energy_kw=np.full(n, kw)))
    assert abs(a["dt_c"].mean() - 8.0) < 1e-6


def test_aliases_and_gpm():
    n = 24 * 20
    df = _frame(n, GPM=np.full(n, 100.0), Supply_Temp_C=np.full(n, 6.0), Return_Temp_C=np.full(n, 15.0))
    df = df.rename(columns={"GPM": "flow_gpm", "Supply_Temp_C": "t_supply_c", "Return_Temp_C": "t_return_c"})
    h = canonicalise(df)
    assert abs(h["flow_kgs"].mean() - 100 * 0.0630902) < 1e-9


def test_resamples_15_minute_data_to_hourly():
    ts = pd.date_range("2025-07-01", periods=4 * 24 * 20, freq="15min")
    n = len(ts)
    df = pd.DataFrame({"timestamp": ts, "flow_m3h": np.full(n, 36.0),
                       "t_supply_c": 6.0, "t_return_c": 14.0})
    h = canonicalise(df)
    assert len(h) == 24 * 20


@pytest.mark.parametrize("drop,msg", [("timestamp", "timestamp"), ("flow_m3h", "flow")])
def test_missing_required_columns(drop, msg):
    n = 24 * 20
    df = _frame(n, flow_m3h=np.full(n, 36.0), t_supply_c=6.0, t_return_c=14.0).drop(columns=[drop])
    with pytest.raises(DataError, match=msg):
        canonicalise(df)


def test_needs_temperatures_or_energy():
    n = 24 * 20
    with pytest.raises(DataError):
        canonicalise(_frame(n, flow_m3h=np.full(n, 36.0)))


def test_too_short():
    n = 24 * 5
    with pytest.raises(DataError, match="at least"):
        canonicalise(_frame(n, flow_m3h=np.full(n, 36.0), t_supply_c=6.0, t_return_c=14.0))
