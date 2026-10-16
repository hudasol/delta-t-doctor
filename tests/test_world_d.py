import numpy as np

from deltat_doctor import CAUSES
from deltat_doctor.sim import world_d as W
from deltat_doctor.sim.weather import make_timestamps, synth_outdoor_temp


def test_world_d_sample_is_deterministic_and_labelled():
    a = W.make_sample_d(np.random.default_rng(3), 0, causes=("fouling",), days=14)
    b = W.make_sample_d(np.random.default_rng(3), 0, causes=("fouling",), days=14)
    assert a.frame.equals(b.frame)
    assert set(a.gains) == set(CAUSES) and all(a.gains[c] == 0.0 for c in CAUSES if c != "fouling")
    assert a.gains["fouling"] > 0 and a.dt_healthy > a.dt_actual
    assert {"timestamp", "flow_m3h", "t_supply_c", "t_return_c", "t_outdoor_c"} <= set(a.frame.columns)


def test_world_d_batch_matches_single_runs():
    rng = np.random.default_rng(5)
    cfg = W.sample_building_d(rng, 0)
    ts = make_timestamps(6, 3)
    drv = W.make_drivers_d(cfg, ts, synth_outdoor_temp(ts, rng), rng)
    f = W.sample_faults_d(cfg, rng, ("overflow", "passing_valves"))
    batch = W.physics_d_batch(cfg, [f, W.FaultsD.healthy(cfg.n_ahu)], drv)
    single = W.physics_d(cfg, f, drv)
    assert np.allclose(batch[0].flow_kgs, single.flow_kgs) and np.allclose(batch[0].heat_kw, single.heat_kw)


def test_world_d_through_dataset_interface_with_temporal_block():
    from deltat_doctor.sim.dataset import generate
    from deltat_doctor.temporal import TEMPORAL_NAMES
    d = generate(2, 1, seed=1, n_jobs=1, sim="D", temporal=True)
    assert d.X.shape == (2, 42) and d.T.shape == (2, len(TEMPORAL_NAMES)) and np.isfinite(d.T).all()
    # the temporal flag must not change the shape features or the labels
    d0 = generate(2, 1, seed=1, n_jobs=1, sim="D")
    assert d0.T is None and np.array_equal(d0.X, d.X) and np.array_equal(d0.Y, d.Y)
