"""Risk coverage metric used in docs/SELECTIVE_PREDICTION.md must not depend on file order when scores tie."""
import importlib.util
import os

import numpy as np

_spec = importlib.util.spec_from_file_location("sp", os.path.join(os.path.dirname(__file__), "..", "scripts", "selective_prediction.py"))
sp = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(sp)


def test_aurc_is_order_independent_under_ties():
    rng = np.random.default_rng(0)
    score = rng.integers(0, 3, 300).astype(float)     # heavy ties, like isotonic probabilities
    wrong = rng.random(300) < 0.3
    a = sp.aurc(score, wrong)
    perm = rng.permutation(300)
    b = sp.aurc(score[perm], wrong[perm])
    assert np.allclose(a[0], b[0]) and np.allclose(a[1], b[1])
    assert np.isclose(sp.aurc(np.zeros(10), np.array([1, 0, 1, 0, 0, 0, 1, 0, 0, 0]))[0], 0.3)


def test_aurc_rewards_a_signal_that_ranks_errors_last():
    wrong = np.array([0] * 70 + [1] * 30)
    good, bad = np.arange(100.0), -np.arange(100.0)
    assert sp.aurc(good, wrong)[0] < wrong.mean() < sp.aurc(bad, wrong)[0]
