"""Round 5 (ATRC): open-set abstention, evidence vs healthy, tiers, trend, savings cap."""
import numpy as np

from deltat_doctor.api import _demo
from deltat_doctor.diagnose import diagnose_frame
from deltat_doctor.openset import OpenSetGuard
from deltat_doctor.portfolio import diagnose_portfolio
from deltat_doctor.penalty import ContractTerms


def test_guard_flags_joint_shift_not_seen_by_per_feature_box():
    rng = np.random.default_rng(0)
    A = rng.normal(size=(2000, 6)) @ np.array([[1, .9, 0, 0, 0, 0], [0, .4, 0, 0, 0, 0]] + [[0] * 6] * 4) + rng.normal(size=(2000, 6)) * .2
    g = OpenSetGuard().fit(A)
    ok = A[:200]
    assert (g.score(ok) > g.threshold).mean() < 0.2
    # each coordinate in range, but the correlation between the first two is broken
    bad = A.copy()[:200]
    bad[:, 1] = -bad[:, 1] * 2
    assert np.median(g.score(bad)) > g.threshold


def test_shuffled_meter_data_is_withheld():
    df, _ = _demo("fouled_coils")
    r = np.random.default_rng(0)
    d = df.copy()
    for c in d.columns:
        if c != "timestamp" and d[c].dtype.kind == "f":
            d[c] = r.permutation(d[c].to_numpy())
    rep = diagnose_frame(d)
    assert rep.abstained and rep.findings == [] and rep.data_quality["reliable"] is False
    assert any("withheld" in n for n in rep.notes)


def test_normal_building_is_not_withheld_and_has_evidence_and_tier():
    df, _ = _demo("three_way_valves")
    rep = diagnose_frame(df)
    assert not rep.abstained
    top = rep.findings[0]
    assert top["tier"] in {"likely", "possible", "weak", "unsupported"}
    assert top["evidence"] and top["evidence"]["items"]
    it = top["evidence"]["items"][0]
    assert {"value", "healthy_p5", "healthy_p95", "label_ar", "outside_healthy"} <= set(it)


def test_weak_signature_cause_is_never_likely():
    df, _ = _demo("excess_pressure")
    rep = diagnose_frame(df)
    f = next(f for f in rep.findings if f["cause"] == "overflow")
    assert f["evidence"]["weak_signature"] and f["tier"] != "likely"


def test_savings_never_exceed_surcharge():
    for name in ("fouled_coils", "mixed_problems", "idle_coils_leaking"):
        df, _ = _demo(name)
        rep = diagnose_frame(df)
        sur = rep.annual_surcharge_aed_estimate
        for f in rep.findings:
            assert f["expected_saving_aed_per_year"] <= sur + 1e-6
            assert (f["saving_high_aed_per_year"] or 0) <= sur + 1e-6


def test_series_and_trend_fields():
    df, _ = _demo("fouled_coils")
    rep = diagnose_frame(df)
    assert len(rep.series) == rep.n_windows and set(rep.series[0]["p"]) == {"fouling", "passing_valves", "constant_flow", "overflow"}
    assert "significant" in rep.trend and rep.trend["n_windows"] >= 1


def test_portfolio_total_saving_capped_by_surcharge():
    from deltat_doctor.api import _portfolio_frame
    rep = diagnose_portfolio(_portfolio_frame().copy(), ContractTerms())
    assert rep.total_expected_saving_aed <= rep.total_surcharge_aed + 1e-6
