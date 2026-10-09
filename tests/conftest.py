import os, sys
import numpy as np
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))


@pytest.fixture(scope="session")
def tiny_model(tmp_path_factory):
    """A small model trained on a small simulated set (fast; not for accuracy claims)."""
    from deltat_doctor.models import Diagnoser
    from deltat_doctor.sim.dataset import generate
    from deltat_doctor.features import augment
    ds = generate(24, 6, seed=5, n_jobs=1)
    m = Diagnoser(seed=0).fit(ds.X, ds.Y, ds.G)
    d = tmp_path_factory.mktemp("m")
    path = d / "tiny.joblib"
    m.save(str(path))
    mi = Diagnoser(seed=0).fit(augment(ds.X, ds.meta["design_dt"].to_numpy()), ds.Y, ds.G)
    mi.save(str(d / "tiny_informed.joblib"))
    return m, str(path)


@pytest.fixture(scope="session")
def tiny_informed_path(tiny_model):
    return os.path.join(os.path.dirname(tiny_model[1]), "tiny_informed.joblib")
