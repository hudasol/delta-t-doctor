import os, sys
import numpy as np
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))


@pytest.fixture(scope="session")
def tiny_model(tmp_path_factory):
    """A small model trained on a small simulated set (fast; not for accuracy claims)."""
    from deltat_doctor.models import Diagnoser
    from deltat_doctor.sim.dataset import generate
    ds = generate(24, 6, seed=5, n_jobs=1)
    m = Diagnoser(seed=0).fit(ds.X, ds.Y, ds.G)
    path = tmp_path_factory.mktemp("m") / "tiny.joblib"
    m.save(str(path))
    return m, str(path)
