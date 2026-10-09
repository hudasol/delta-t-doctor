"""Corrupted, hostile and malformed inputs: the tool must fail loudly or flag them, never produce a confident wrong number."""
import io

import numpy as np
import pandas as pd
import pytest

from deltat_doctor.io import DataError, canonicalise, read_table
from deltat_doctor.portfolio import safe_cell, to_csv


def _base(hours=24 * 40, seed=0):
    rng = np.random.default_rng(seed)
    ts = pd.date_range("2025-07-01", periods=hours, freq="h")
    load = 0.5 + 0.4 * np.sin(np.arange(hours) / 24 * 2 * np.pi - 2)
    flow = 60 * load + rng.normal(0, 0.5, hours)
    return pd.DataFrame({"timestamp": ts, "flow_m3h": flow, "t_supply_c": 6.0 + rng.normal(0, .05, hours),
                         "t_return_c": 13.5 + rng.normal(0, .1, hours)})


def test_flow_spikes_removed_and_flagged():
    df = _base()
    df.loc[df.sample(frac=0.03, random_state=1).index, "flow_m3h"] = 1e9
    h = canonicalise(df)
    assert h["flow_kgs"].max() < 100
    assert h.attrs["quality"]["outlier_fraction"] > 0.02


def test_sensor_codes_become_missing():
    df = _base()
    df.loc[::25, "t_return_c"] = 99.9
    df.loc[5::31, "flow_m3h"] = -999
    h = canonicalise(df)
    assert h["dt_c"].max() < 15 and not h["flow_kgs"].isna().any()
    q = h.attrs["quality"]
    assert q["sentinel_cells"] > 0 or q["outlier_fraction"] > 0


def test_unparseable_timestamps_counted():
    df = _base()
    df["timestamp"] = df["timestamp"].astype(str)
    df.loc[::12, "timestamp"] = "garbage"
    h = canonicalise(df)
    assert h.attrs["quality"]["bad_timestamp_fraction"] > 0.05
    assert h.attrs["quality"]["dropped_fraction"] > 0.05


def test_frozen_meter_flagged():
    df = _base()
    df.loc[100:400, ["flow_m3h", "t_return_c"]] = [30.0, 13.0]
    h = canonicalise(df)
    assert h.attrs["quality"]["longest_flatline_readings"] >= 48
    assert any("stuck" in n or "frozen" in n for n in h.attrs["notes"])


def test_all_negative_flow_rejected():
    df = _base()
    df["flow_m3h"] = -df["flow_m3h"].abs()
    with pytest.raises(DataError):
        canonicalise(df)


def test_text_cells_in_numeric_column_counted():
    df = _base().astype({"t_return_c": object})
    df.loc[::40, "t_return_c"] = "=cmd|' /C calc'!A0"
    h = canonicalise(df)
    assert h.attrs["quality"]["coerced_cells"] > 0


def test_xls_and_fake_xlsx_rejected():
    with pytest.raises(DataError):
        read_table(b"whatever", "meter.xls")
    with pytest.raises(DataError):
        read_table(b"not a zip at all", "meter.xlsx")


def test_zip_bomb_rejected(monkeypatch):
    import zipfile
    from deltat_doctor import io as dio
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("xl/worksheets/sheet1.xml", b"0" * 5_000_000)
    monkeypatch.setattr(dio, "MAX_UNZIPPED_BYTES", 1_000_000)
    with pytest.raises(DataError):
        read_table(buf.getvalue(), "m.xlsx")


def test_row_cap(monkeypatch):
    from deltat_doctor import io as dio
    monkeypatch.setattr(dio, "MAX_ROWS", 100)
    with pytest.raises(DataError):
        read_table(_base(500).to_csv(index=False).encode(), "m.csv")


def test_semicolon_and_tab_delimiters():
    csv = _base(200)
    for sep in (";", "\t", "|"):
        out = read_table(csv.to_csv(index=False, sep=sep).encode(), "m.csv")
        assert out.shape[1] == 4


def test_csv_formula_injection_neutralised():
    assert safe_cell("=HYPERLINK(\"http://x\")") == "'=HYPERLINK(\"http://x\")"
    assert safe_cell("@SUM(1)").startswith("'")
    assert safe_cell("Tower A") == "Tower A"


def test_portfolio_csv_escapes_building_names(tiny_model, monkeypatch):
    from deltat_doctor import diagnose as dg
    from deltat_doctor.penalty import ContractTerms
    from deltat_doctor.portfolio import diagnose_portfolio
    _, path = tiny_model
    monkeypatch.setattr(dg, "DEFAULT_MODEL", path)
    dg._cached.clear()
    df = _base(24 * 40).assign(building_id="=1+1")
    out = to_csv(diagnose_portfolio(df, ContractTerms()))
    assert "'=1+1" in out and "\n=1+1" not in out


def test_tampered_bundled_model_refused(tmp_path, monkeypatch):
    import shutil
    from deltat_doctor import diagnose as dg
    assets = tmp_path / "assets"
    shutil.copytree(dg._ASSETS, assets)
    (assets / "diagnoser.joblib").write_bytes((assets / "diagnoser.joblib").read_bytes() + b"x")
    monkeypatch.setattr(dg, "_ASSETS", str(assets))
    with pytest.raises(RuntimeError, match="sha256"):
        dg._load_verified(str(assets / "diagnoser.joblib"))


def test_missing_hash_fails_closed(tmp_path, monkeypatch):
    import json
    import shutil
    from deltat_doctor import diagnose as dg
    assets = tmp_path / "assets"
    shutil.copytree(dg._ASSETS, assets)
    card = json.load(open(assets / "model_card.json"))
    card.pop("sha256")
    json.dump(card, open(assets / "model_card.json", "w"))
    monkeypatch.setattr(dg, "_ASSETS", str(assets))
    with pytest.raises(RuntimeError, match="sha256"):
        dg._load_verified(str(assets / "diagnoser.joblib"))
