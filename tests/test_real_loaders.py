"""Loaders for the real data contact (scripts/real_loaders.py) and the parser behaviour they exposed. Synthetic fixtures only."""
import os
import sys

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))
from real_loaders import dk_canonical, dk_export, nis_export  # noqa: E402

from deltat_doctor.io import DataError, canonicalise, read_table  # noqa: E402


def _dk_registers(hours=24 * 20, t_in=70.0, t_back=35.0, seed=0):
    """Cumulative registers in the Danish smart meter format, from a known hourly volume and temperatures."""
    rng = np.random.default_rng(seed)
    vol = rng.uniform(0.05, 0.2, hours)
    ts = pd.date_range("2019-01-01", periods=hours + 1, freq="h", tz="UTC")
    cum = lambda x: np.concatenate([[100.0], 100.0 + np.cumsum(x)])
    return pd.DataFrame({"customer_id": 1, "meter_id": 1, "time_rounded": ts.strftime("%Y-%m-%dT%H:%M:%SZ"),
                         "energy_heat_kwh": cum(vol * 1.163 * (t_in - t_back)), "volume_flow_m3": cum(vol),
                         "inlet_flow_energy_m3xC": cum(vol * t_in), "back_flow_energy_m3xC": cum(vol * t_back)})


def test_dk_registers_are_differenced_into_flow_and_temperatures():
    h, q = dk_canonical(_dk_registers())
    assert len(h) == 24 * 20 and q["negative_register_steps"] == 0
    assert np.allclose(h["dt_c"], 35.0) and abs(q["heat_vs_energy_register"] - 4.186 / 3.6 / 1.163) < 1e-3
    e = dk_export(_dk_registers())
    assert np.allclose(e["t_supply_c"], 70.0) and np.allclose(e["t_return_c"], 35.0)


def test_heating_export_is_refused_with_a_plain_message():
    raw = dk_export(_dk_registers()).to_csv(index=False).encode()
    with pytest.raises(DataError, match="not a plausible chilled-water temperature"):
        canonicalise(read_table(raw, "dk.csv"))


def test_nis_export_without_flow_is_refused():
    raw = pd.DataFrame({"datetime": pd.date_range("2020-01-01", periods=400, freq="h").astype(str), "t_sup_prim": 60.0,
                        "t_ret_prim": 40.0, "t_amb": 5.0, "delta_e": 100.0})
    with pytest.raises(DataError, match="No flow column"):
        canonicalise(read_table(nis_export(raw).to_csv(index=False).encode(), "nis.csv"))


def test_utc_timestamps_raise_a_note():
    from deltat_doctor.sim.scenarios import make_sample
    f = make_sample(np.random.default_rng(1), 0, causes=(), month=6).frame
    f["timestamp"] = pd.to_datetime(f["timestamp"]).dt.strftime("%Y-%m-%dT%H:%M:%SZ")
    h = canonicalise(read_table(f.to_csv(index=False).encode(), "z.csv"))
    assert any("UTC" in n for n in h.attrs["notes"])
    f["timestamp"] = pd.to_datetime(f["timestamp"]).dt.strftime("%Y-%m-%d %H:%M")
    assert not any("UTC" in n for n in canonicalise(read_table(f.to_csv(index=False).encode(), "z.csv")).attrs["notes"])
