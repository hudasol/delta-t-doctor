import pandas as pd
import pytest
from fastapi.testclient import TestClient

from deltat_doctor import diagnose as dg
from deltat_doctor.io import DataError
from deltat_doctor.penalty import ContractTerms
from deltat_doctor.portfolio import diagnose_portfolio, to_csv
from deltat_doctor.report import render_report


@pytest.fixture()
def models(tiny_model, tiny_informed_path, monkeypatch):
    monkeypatch.setattr(dg, "DEFAULT_MODEL", tiny_model[1])
    monkeypatch.setattr(dg, "INFORMED_MODEL", tiny_informed_path)
    dg._cached.clear()


def _demo(name="fouled_coils"):
    from deltat_doctor.api import _demo as d
    return d(name)


def test_informed_mode_sets_report_fields(models):
    df, design = _demo()
    blind = dg.diagnose_frame(df, ContractTerms())
    inf = dg.diagnose_frame(df, ContractTerms(), design_delta_t_c=design)
    assert blind.mode == "blind" and blind.design_delta_t_c is None
    assert inf.mode == "informed" and inf.design_delta_t_c == design


def test_design_delta_t_out_of_range_rejected(models):
    df, _ = _demo()
    with pytest.raises(DataError):
        dg.diagnose_frame(df, ContractTerms(), design_delta_t_c=1.0)


def test_portfolio_ranks_and_skips(models):
    df1, d1 = _demo("fouled_coils"); df2, d2 = _demo("healthy")
    a = df1.assign(building_id="A", design_delta_t_c=d1)
    b = df2.assign(building_id="B", design_delta_t_c=d2)
    tiny = df1.head(30).assign(building_id="C", design_delta_t_c=d1)
    rep = diagnose_portfolio(pd.concat([a, b, tiny], ignore_index=True), ContractTerms())
    assert rep.n_buildings == 3 and rep.n_diagnosed == 2 and rep.n_skipped == 1
    ok = [r for r in rep.buildings if r["status"] == "ok"]
    sav = [r["top_cause_saving_aed"] for r in ok]
    assert sav == sorted(sav, reverse=True)
    assert rep.buildings[-1]["building_id"] == "C" and rep.buildings[-1]["status"] == "skipped"
    assert all(r["mode"] == "informed" for r in ok)
    assert "building_id" in to_csv(rep)


def test_portfolio_needs_building_column(models):
    df, _ = _demo()
    with pytest.raises(DataError):
        diagnose_portfolio(df, ContractTerms())


def test_report_is_self_contained_and_escaped(models):
    df, _ = _demo()
    html = render_report(dg.diagnose_frame(df, ContractTerms()).to_dict(), "<script>x</script>")
    assert html.startswith("<!doctype html>") and "<script>x</script>" not in html
    assert "&lt;script&gt;" in html and "<svg" in html and "http://" not in html.replace("http://www.w3.org", "")


def test_api_portfolio_report_and_design(models):
    from deltat_doctor.api import app, _demo as dm
    c = TestClient(app)
    df, design = dm("fouled_coils")
    r = c.get("/api/demo/fouled_coils", params={"design_dt": design})
    assert r.status_code == 200 and r.json()["mode"] == "informed"
    assert c.get("/api/demo/fouled_coils", params={"design_dt": 99}).status_code == 422
    assert "<svg" in c.get("/api/demo/fouled_coils/report").text
    csv = df.assign(building_id="A").to_csv(index=False)
    r = c.post("/api/portfolio", files={"file": ("p.csv", csv, "text/csv")})
    assert r.status_code == 200 and r.json()["n_diagnosed"] == 1
    r = c.post("/api/portfolio", files={"file": ("p.csv", df.to_csv(index=False), "text/csv")})
    assert r.status_code == 422


def test_ood_guard_flags_flow_that_ignores_load(models):
    df, _ = _demo("healthy")
    ok = dg.diagnose_frame(df, ContractTerms())
    assert ok.data_quality["reliable"] is True
    weird = df.copy()
    weird["flow_m3h"] = float(df["flow_m3h"].mean())
    weird["energy_kw"] = weird["flow_m3h"] * 1.163 * (df["t_return_c"] - df["t_supply_c"])
    bad = dg.diagnose_frame(weird, ContractTerms())
    assert bad.data_quality["features_out_of_range"] > ok.data_quality["features_out_of_range"]


def test_security_headers_and_bundled_fonts(models):
    from deltat_doctor.api import app
    c = TestClient(app)
    r = c.get("/")
    assert r.headers["x-content-type-options"] == "nosniff" and "frame-ancestors 'none'" in r.headers["content-security-policy"]
    assert "googleapis" not in r.text and "http://" not in r.text.replace("http://www.w3.org", "")
    assert c.get("/fonts/ibm-plex-sans-latin-600-normal.woff2").status_code == 200
