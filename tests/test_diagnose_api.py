import io

import pytest
from fastapi.testclient import TestClient

from deltat_doctor import CAUSES
from deltat_doctor import diagnose as dg
from deltat_doctor.io import DataError
from deltat_doctor.penalty import ContractTerms


@pytest.fixture()
def client(tiny_model, tiny_informed_path, monkeypatch):
    _, path = tiny_model
    monkeypatch.setattr(dg, "DEFAULT_MODEL", path)
    monkeypatch.setattr(dg, "INFORMED_MODEL", tiny_informed_path)
    dg._cached.clear()
    from deltat_doctor.api import app
    return TestClient(app)


def _year_frame(causes=("fouling",)):
    from deltat_doctor.api import _demo
    name = {(): "healthy", ("fouling",): "fouled_coils"}[tuple(causes)]
    return _demo(name)[0]


def test_diagnose_frame_report_structure(tiny_model):
    m, _ = tiny_model
    rep = dg.diagnose_frame(_year_frame(("fouling",)), ContractTerms(), m)
    d = rep.to_dict()
    assert {f["cause"] for f in d["findings"]} == set(CAUSES)
    sav = [f["expected_saving_aed_per_year"] for f in d["findings"]]
    assert sav == sorted(sav, reverse=True)
    assert all(0 <= f["probability"] <= 1 for f in d["findings"])
    assert d["n_windows"] >= 5 and d["monthly"] and d["signature"]
    assert "simulated" in d["disclaimer"]


def test_report_changes_with_contract_rate(tiny_model):
    m, _ = tiny_model
    df = _year_frame(("fouling",))
    a = dg.diagnose_frame(df, ContractTerms(rate_aed_per_rt_hr=0.2), m).annual_surcharge_aed_estimate
    b = dg.diagnose_frame(df, ContractTerms(rate_aed_per_rt_hr=0.4), m).annual_surcharge_aed_estimate
    assert b == pytest.approx(2 * a, rel=1e-6)


def test_short_data_rejected(tiny_model):
    m, _ = tiny_model
    with pytest.raises(DataError):
        dg.diagnose_frame(_year_frame(()).head(24 * 5), ContractTerms(), m)


def test_api_health_and_demos(client):
    r = client.get("/api/health")
    assert r.status_code == 200 and r.json()["status"] == "ok"
    assert "fouled_coils" in client.get("/api/demos").json()["demos"]


def test_api_demo_reports_truth_and_rejects_unknown(client):
    r = client.get("/api/demo/fouled_coils")
    assert r.status_code == 200
    assert r.json()["truth_for_demo"] == ["fouling"]
    assert client.get("/api/demo/nope").status_code == 404


def test_api_upload_roundtrip(client):
    df = _year_frame(("fouling",))
    buf = io.BytesIO(df.to_csv(index=False).encode())
    r = client.post("/api/diagnose", files={"file": ("x.csv", buf, "text/csv")},
                    data={"min_dt": "8.9", "pct": "0.1", "rate": "0.5"})
    assert r.status_code == 200
    assert r.json()["terms"]["rate_aed_per_rt_hr"] == 0.5


def test_api_validation_errors(client):
    bad = io.BytesIO(b"a,b\n1,2\n")
    r = client.post("/api/diagnose", files={"file": ("x.csv", bad, "text/csv")})
    assert r.status_code == 422 and "timestamp" in r.json()["detail"].lower()
    ok = io.BytesIO(_year_frame(()).to_csv(index=False).encode())
    r = client.post("/api/diagnose", files={"file": ("x.csv", ok, "text/csv")}, data={"min_dt": "99"})
    assert r.status_code == 422
    r = client.post("/api/diagnose", files={"file": ("x.csv", io.BytesIO(b"\x00\xff\x00"), "text/csv")})
    assert r.status_code == 422


def test_index_served(client):
    r = client.get("/")
    assert r.status_code == 200 and "delta-t-doctor" in r.text


def test_demo_csv_route_not_shadowed(client):
    r = client.get("/api/demo/fouled_coils.csv")
    assert r.status_code == 200 and r.text.startswith("timestamp") or "flow" in r.text.splitlines()[0]


@pytest.mark.parametrize("field", ["rate", "pct", "min_dt"])
def test_non_finite_terms_rejected(client, field):
    r = client.get("/api/demo/healthy", params={field: "nan"})
    assert r.status_code == 422
    r = client.get("/api/demo/healthy", params={field: "inf"})
    assert r.status_code == 422


def test_non_finite_design_dt_rejected(client):
    assert client.get("/api/demo/healthy", params={"design_dt": "nan"}).status_code == 422


def test_oversize_upload_rejected(client, monkeypatch):
    from deltat_doctor import api
    monkeypatch.setattr(api, "MAX_BYTES", 1000)
    r = client.post("/api/diagnose", files={"file": ("x.csv", io.BytesIO(b"a,b\n" * 1000), "text/csv")})
    assert r.status_code == 413
