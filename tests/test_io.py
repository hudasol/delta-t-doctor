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


def _msg_frame(n=24 * 20):
    return pd.date_range("2025-07-01", periods=n, freq="h"), n


def test_messy_headers_fahrenheit_lps_and_dayfirst_dates():
    ts, n = _msg_frame()
    df = pd.DataFrame({"Date Time": ts.strftime("%d/%m/%Y %H:%M"), "CHW Supply Temp (°F)": np.full(n, 42.8),
                       "CHW Return Temp (°F)": np.full(n, 57.2), "Flow Rate [L/s]": np.full(n, 10.0)})
    h = canonicalise(df)
    assert abs(h["dt_c"].mean() - 8.0) < 1e-6 and abs(h["flow_kgs"].mean() - 10.0) < 1e-9
    assert h["timestamp"].iloc[0] == pd.Timestamp("2025-07-01 00:00")


def test_cumulative_kwh_register_is_differenced():
    ts, n = _msg_frame()
    kw = 4.186 * 10.0 * 8.0
    df = pd.DataFrame({"Timestamp": ts, "Flow (m3/h)": np.full(n, 36.0),
                       "Cooling Energy (kWh)": np.cumsum(np.full(n, kw))})
    assert abs(canonicalise(df)["dt_c"].mean() - 8.0) < 0.05


def test_power_in_rt_and_mw():
    ts, n = _msg_frame()
    kw = 4.186 * 10.0 * 8.0
    a = canonicalise(pd.DataFrame({"time": ts, "flow m3/h": np.full(n, 36.0), "Cooling Load (RT)": np.full(n, kw / 3.517)}))
    b = canonicalise(pd.DataFrame({"time": ts, "flow m3/h": np.full(n, 36.0), "Cooling Load (MW)": np.full(n, kw / 1000)}))
    assert abs(a["dt_c"].mean() - 8.0) < 1e-6 and abs(b["dt_c"].mean() - 8.0) < 1e-6


def test_read_table_sniffs_delimiter_and_rejects_garbage():
    from deltat_doctor.io import read_table
    ts, n = _msg_frame(30)
    raw = "timestamp;flow_m3h;t_supply_c;t_return_c\n" + "\n".join(f"{t};36;6;14" for t in ts)
    assert read_table(raw.encode(), "a.csv").shape == (30, 4)
    with pytest.raises(DataError):
        read_table(b"\x00\x01\x02 not a table", "a.xlsx")


def test_error_lists_columns_seen():
    ts, n = _msg_frame()
    with pytest.raises(DataError, match="Columns seen"):
        canonicalise(pd.DataFrame({"timestamp": ts, "mystery": 1.0}))


def test_swapped_sensors_rejected():
    n = 24 * 20
    with pytest.raises(DataError):
        canonicalise(_frame(n, flow_m3h=np.full(n, 36.0), t_supply_c=np.full(n, 14.0), t_return_c=np.full(n, 6.0)))


def test_nan_rows_dropped_and_reported():
    n = 24 * 20
    ret = np.full(n, 14.0)
    ret[::10] = np.nan
    h = canonicalise(_frame(n, flow_m3h=np.full(n, 36.0), t_supply_c=np.full(n, 6.0), t_return_c=ret))
    assert not h["dt_c"].isna().any()
    assert h.attrs["quality"]["dropped_fraction"] > 0


def test_latin1_and_dayfirst_dates():
    from deltat_doctor.io import read_table
    n = 24 * 20
    ts = pd.date_range("2025-07-01", periods=n, freq="h")
    df = pd.DataFrame({"timestamp": ts.strftime("%d/%m/%Y %H:%M"), "flow_m3h": 36.0,
                       "t_supply_c": 6.0, "t_return_c": 14.0})
    raw = df.to_csv(index=False).replace("flow_m3h", "flow_m3h").encode("latin-1")
    h = canonicalise(read_table(raw, "x.csv"))
    assert h["timestamp"].min().month == 7 and h["timestamp"].min().day == 1


def test_implausible_temperature_rejected():
    n = 24 * 20
    with pytest.raises(DataError):
        canonicalise(_frame(n, flow_m3h=np.full(n, 36.0), t_supply_c=np.full(n, 600.0), t_return_c=np.full(n, 614.0)))
