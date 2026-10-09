import numpy as np
from deltat_doctor import CAUSES
from deltat_doctor.sim.building import FaultSpec, make_drivers, measure, physics
from deltat_doctor.sim.scenarios import make_sample, sample_building, sample_faults, meter_delta_t
from deltat_doctor.sim.weather import make_timestamps, synth_outdoor_temp


def _setup(seed=0, month=7, btype=None):
    rng = np.random.default_rng(seed)
    cfg = sample_building(rng, 0)
    if btype:
        cfg.building_type = btype
    ts = make_timestamps(month)
    drv = make_drivers(cfg, ts, synth_outdoor_temp(ts, rng), rng)
    return cfg, drv, rng


def test_healthy_building_meets_load_and_has_reasonable_delta_t():
    cfg, drv, _ = _setup()
    out = physics(cfg, FaultSpec.healthy(cfg.n_ahu), drv)
    assert out.unmet_kw.sum() < 1e-3 * out.heat_kw.sum()
    assert 8.5 < out.delta_t_period < 15.0


def test_every_fault_family_lowers_delta_t():
    for c in CAUSES:
        for seed in range(3):
            cfg, drv, rng = _setup(seed, 7)
            healthy = meter_delta_t(physics(cfg, FaultSpec.healthy(cfg.n_ahu), drv))
            f = sample_faults(cfg, rng, (c,))
            faulty = meter_delta_t(physics(cfg, f, drv))
            assert faulty < healthy - 0.02, (c, seed, healthy, faulty)


def test_gains_nonnegative_and_zero_for_absent_causes():
    rng = np.random.default_rng(3)
    for _ in range(6):
        s = make_sample(rng, 0)
        for c in CAUSES:
            assert s.gains[c] >= 0
            if c not in s.causes_injected:
                assert s.gains[c] == 0
        # fixing one cause cannot recover more than fixing everything (up to interaction slack)
        assert max(s.gains.values()) <= s.gain_all + 0.5


def test_deterministic_given_seed():
    a = make_sample(np.random.default_rng(11), 0)
    b = make_sample(np.random.default_rng(11), 0)
    assert np.allclose(a.frame["flow_m3h"], b.frame["flow_m3h"])
    assert a.causes_injected == b.causes_injected


def test_flow_conservation_energy_balance_at_meter():
    cfg, drv, rng = _setup(2)
    out = physics(cfg, FaultSpec.healthy(cfg.n_ahu), drv)
    df = measure(out, rng, flow_noise=0.0, temp_noise=0.0)
    # energy_kw ~ cp * flow(kg/s) * (Tr - Ts)
    flow_kgs = df["flow_m3h"] / 3.6
    e = 4.186 * flow_kgs * (df["t_return_c"] - df["t_supply_c"])
    assert np.allclose(e, df["energy_kw"], rtol=1e-6, atol=1e-6)


def test_passing_valves_dominate_when_load_is_low():
    """Offices switch AHUs off at night: leaks should show up as flow with ~zero heat."""
    cfg, drv, rng = _setup(4, 7, "office")
    f = FaultSpec.healthy(cfg.n_ahu)
    f.leak_frac = np.full(cfg.n_ahu, 0.15)
    out = physics(cfg, f, drv)
    night = (drv.ts.hour.values >= 22) | (drv.ts.hour.values <= 4)
    assert out.flow_kgs[night].mean() > 0.05 * out.flow_kgs.max()
    assert np.nanmean(out.delta_t_series[night]) < 2.0
