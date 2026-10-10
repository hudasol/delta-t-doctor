import numpy as np

from deltat_doctor import CAUSES
from deltat_doctor.penalty import ContractTerms, saving_from_gain, saving_interval
from deltat_doctor.sim.dataset import generate
from deltat_doctor.sim.hydraulic import FaultsB, make_sample_b, sample_building_b


def test_sim_b_runs_and_is_deterministic():
    a = make_sample_b(np.random.default_rng(4), 0, causes=("fouling",), month=7)
    b = make_sample_b(np.random.default_rng(4), 0, causes=("fouling",), month=7)
    assert a.dt_actual == b.dt_actual and a.gains == b.gains
    assert {"t_supply_c", "t_return_c", "flow_m3h", "energy_kw"} <= set(a.frame.columns)
    assert len(a.frame) > 24 * 20


def test_sim_b_absent_cause_has_zero_gain_and_healthy_matches():
    rng = np.random.default_rng(9)
    cfg = sample_building_b(rng, 0)
    s = make_sample_b(rng, 0, cfg=cfg, causes=(), month=7)
    assert all(v == 0.0 for v in s.gains.values()) and abs(s.dt_actual - s.dt_healthy) < 1e-9
    f = FaultsB.healthy(cfg.n_ahu)
    assert np.allclose(f.without("fouling").foul, 0)


def test_sim_b_faults_lower_delta_t_somewhere():
    rng = np.random.default_rng(21)
    worst = {c: 0.0 for c in CAUSES}
    for b in range(8):
        cfg = sample_building_b(rng, b)
        for c in CAUSES:
            s = make_sample_b(rng, b, cfg=cfg, causes=(c,), month=7)
            worst[c] = max(worst[c], s.gains[c])
    assert all(v > 0.2 for v in worst.values()), worst


def test_generate_sim_b_shapes():
    ds = generate(3, 2, seed=1, n_jobs=1, sim="B")
    assert ds.X.shape[0] == 6 and ds.Y.shape == (6, 4) and (ds.G >= 0).all()


def test_saving_interval_ordering_and_zero_gain():
    terms = ContractTerms()
    mean, lo, hi = saving_interval(7.0, (0.2, 0.6, 1.2), 1000.0, terms)
    assert 0 <= lo <= hi and 0 <= mean <= hi * 1.5
    assert abs(hi - saving_from_gain(7.0, 1.2, 1000.0, terms)) < 1e-9
    assert saving_interval(7.0, (0.0, 0.0, 0.0), 1000.0, terms) == (0.0, 0.0, 0.0)


def test_saving_is_zero_above_contract_minimum():
    mean, lo, hi = saving_interval(9.5, (0.5, 1.0, 2.0), 1000.0, ContractTerms())
    assert mean == lo == hi == 0.0


def test_report_findings_carry_intervals(tiny_model):
    from deltat_doctor.api import _demo
    from deltat_doctor.diagnose import diagnose_frame
    rep = diagnose_frame(_demo("fouled_coils")[0], model=tiny_model[0])
    for f in rep.findings:
        assert f["saving_low_aed_per_year"] is not None
        assert f["saving_low_aed_per_year"] <= f["saving_high_aed_per_year"] + 1e-6
        assert f["dt_gain_low_c"] <= f["dt_gain_high_c"] + 1e-9


def test_quantiles_sorted_and_nonnegative(tiny_model):
    from deltat_doctor.sim.dataset import generate as gen
    ds = gen(3, 2, seed=2, n_jobs=1)
    q = tiny_model[0].predict(ds.X).gain_q
    assert q.shape == (6, 4, 3) and (q >= 0).all() and (np.diff(q, axis=2) >= -1e-12).all()


def test_margin_widens_interval(tiny_model):
    m = tiny_model[0]
    from deltat_doctor.sim.dataset import generate as gen
    X = gen(2, 2, seed=3, n_jobs=1).X
    before = m._quantiles(X)
    m.q_margin = {c: {"active": 0.3, "inactive": 0.3} for c in CAUSES}
    after = m._quantiles(X)
    m.q_margin = {c: {"active": 0.0, "inactive": 0.0} for c in CAUSES}
    assert (after[:, :, -1] >= before[:, :, -1]).all() and (after[:, :, 0] <= before[:, :, 0]).all()
