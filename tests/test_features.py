import numpy as np
import pytest
from deltat_doctor.features import FEATURE_NAMES, extract, to_vector
from deltat_doctor.io import canonicalise
from deltat_doctor.sim.scenarios import make_sample, sample_building


def _frame(causes, seed=1):
    rng = np.random.default_rng(seed)
    cfg = sample_building(rng, 0)
    cfg.building_type = "office"
    s = make_sample(np.random.default_rng(seed + 100), 0, cfg=cfg, causes=causes, month=7)
    return canonicalise(s.frame)


def test_vector_shape_finite_named():
    v = to_vector(extract(_frame(())))
    assert v.shape == (len(FEATURE_NAMES),)
    assert np.isfinite(v).all()
    assert len(set(FEATURE_NAMES)) == len(FEATURE_NAMES)


def test_passing_valves_raise_low_load_flow_share():
    ix = FEATURE_NAMES.index("flow_lowload_share")
    healthy = to_vector(extract(_frame(())))[ix]
    leaky = to_vector(extract(_frame(("passing_valves",))))[ix]
    assert leaky > healthy


def test_constant_flow_decouples_flow_from_load():
    ix = FEATURE_NAMES.index("flow_load_corr")
    healthy = to_vector(extract(_frame(())))[ix]
    cf = to_vector(extract(_frame(("constant_flow",))))[ix]
    assert cf < healthy + 0.02


def test_scale_invariance_of_shape_features():
    """Doubling flow and heat together (a bigger building) must not change shape features."""
    h = _frame(("fouling",))
    h2 = h.copy()
    h2["flow_kgs"] *= 2.0
    h2["heat_kw"] *= 2.0
    a, b = extract(h), extract(h2)
    for k in FEATURE_NAMES:
        assert a[k] == pytest.approx(b[k], rel=1e-9, abs=1e-9), k
