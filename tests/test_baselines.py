import numpy as np
import pytest

from deltat_doctor import CAUSES
from deltat_doctor.baselines import BASELINES, FittedStumps
from deltat_doctor.evaluate import expected_calibration_error, healthy_false_alarm, summary_row, top1_precision
from deltat_doctor.models import Prediction
from deltat_doctor.sim.dataset import Dataset


@pytest.fixture(scope="module")
def small():
    rng = np.random.default_rng(0)
    n = 400
    X = rng.normal(size=(n, 42))
    Y = np.column_stack([(X[:, k] + 0.3 * rng.normal(size=n) > 0.5).astype(float) for k in range(4)])
    G = Y * np.abs(rng.normal(1.0, 0.2, size=(n, 4)))
    import pandas as pd
    meta = pd.DataFrame({"building_id": np.arange(n) // 4, "dt_actual": 6.0 + rng.normal(size=n)})
    return Dataset(X, Y, G, meta)


@pytest.mark.parametrize("name", list(BASELINES))
def test_baseline_contract(small, name):
    m = BASELINES[name]().fit(small.X[:300], small.Y[:300], small.G[:300])
    p = m.predict(small.X[300:])
    assert p.prob.shape == (100, 4) and p.gain.shape == (100, 4) and p.p_any.shape == (100,)
    assert np.all((p.prob >= 0) & (p.prob <= 1)) and np.all(p.gain >= 0)


def test_stumps_find_the_planted_feature(small):
    m = FittedStumps().fit(small.X, small.Y, small.G)
    assert [r["j"] for r in m.rules] == [0, 1, 2, 3]
    assert len(m.describe()) == len(CAUSES)


def test_perfect_prediction_metrics(small):
    perfect = Prediction(small.Y.copy(), small.G.copy(), (small.Y.sum(1) > 0).astype(float))
    assert top1_precision(small, perfect) == 1.0
    assert healthy_false_alarm(small, perfect) == 0.0
    assert expected_calibration_error(small, perfect) == 0.0
    assert summary_row(small, perfect)["gain_mae_when_present"] == 0.0


def test_constant_prior_is_uninformative(small):
    prior = BASELINES["prior"]().fit(small.X, small.Y, small.G).predict(small.X)
    assert abs(summary_row(small, prior)["macro_auroc"] - 0.5) < 1e-9
