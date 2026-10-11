"""Generate labelled training / evaluation data from the simulator."""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd
from joblib import Parallel, delayed

from .. import CAUSES
from ..features import extract, to_vector
from ..io import canonicalise
from .hydraulic import make_sample_b, sample_building_b
from .scenarios import Sample, make_sample, sample_building
from .worlds import make_sample_world, wide_building_a, wide_building_b


@dataclass
class Dataset:
    X: np.ndarray                 # (n, n_features)
    Y: np.ndarray                 # (n, 4) presence labels
    G: np.ndarray                 # (n, 4) delta-T gains (deg C)
    meta: pd.DataFrame            # building_id, month, type, dt_actual, gain_all, ...

    def save(self, path: str) -> None:
        np.savez_compressed(path, X=self.X, Y=self.Y, G=self.G)
        self.meta.to_csv(path.replace(".npz", "_meta.csv"), index=False)

    @staticmethod
    def load(path: str) -> "Dataset":
        z = np.load(path)
        meta = pd.read_csv(path.replace(".npz", "_meta.csv"))
        return Dataset(z["X"], z["Y"], z["G"], meta)

    def subset(self, mask: np.ndarray) -> "Dataset":
        return Dataset(self.X[mask], self.Y[mask], self.G[mask], self.meta[mask].reset_index(drop=True))


def _post(frame: pd.DataFrame, post: str) -> pd.DataFrame:
    """Degrade a measured frame to mimic imperfect real exports."""
    if post == "none":
        return frame
    f = frame.copy()
    if post == "2h":
        g = f.set_index("timestamp").resample("2h").mean().dropna().reset_index()
        return g
    if post == "no_oat":
        f["t_outdoor_c"] = np.nan
        return f
    if post == "energy_only":
        f = f.drop(columns=["t_supply_c", "t_return_c"])
        return f
    raise ValueError(post)


def sample_to_row(s: Sample, post: str = "none"):
    min_hours = 14 * 24 if post != "2h" else 14 * 12
    h = canonicalise(_post(s.frame, post), min_hours=min_hours)
    x = to_vector(extract(h))
    y = np.array([s.present[c] for c in CAUSES], dtype=float)
    g = np.array([s.gains[c] for c in CAUSES], dtype=float)
    meta = {
        "building_id": s.cfg.building_id, "month": s.month,
        "building_type": s.cfg.building_type, "n_ahu": s.cfg.n_ahu,
        "dt_actual": s.dt_actual, "dt_healthy": s.dt_healthy, "gain_all": s.gain_all,
        "injected": "+".join(s.causes_injected) or "none", "cf_subtype": s.cf_subtype,
        "unmet_kwh": s.unmet_kwh,
        "design_dt": float(np.average(s.cfg.dt_design, weights=s.cfg.q_design_kw)),
    }
    return x, y, g, meta


def _one(seed: int, building_id: int, kwargs: dict, new_building_per_sample: bool):
    rng = np.random.default_rng(seed)
    kwargs = dict(kwargs)
    post = kwargs.pop("post", "none")
    sim = kwargs.pop("sim", "A")
    if sim in ("CA", "CB"):
        s = make_sample_world(sim[1], rng, building_id, kwargs.pop("cfg"))
        return sample_to_row(s, post)
    maker = make_sample_b if sim == "B" else make_sample
    s = maker(rng, building_id, **kwargs)
    return sample_to_row(s, post)


def generate(n_buildings: int, samples_per_building: int, seed: int = 0,
             n_jobs: int = 2, sim: str = "A", **kwargs) -> Dataset:
    """n_buildings distinct buildings, each observed in several (month, fault) draws.

    Grouping by building lets evaluation hold out whole buildings.
    """
    master = np.random.default_rng(seed)
    jobs = []
    for b in range(n_buildings):
        bseed = int(master.integers(0, 2**31 - 1))
        brng = np.random.default_rng(bseed)
        cfg = {"B": sample_building_b, "CA": wide_building_a, "CB": wide_building_b}.get(sim, sample_building)(brng, b)
        for k in range(samples_per_building):
            sseed = int(master.integers(0, 2**31 - 1))
            kw = dict(kwargs)
            kw["cfg"] = cfg
            kw["sim"] = sim
            jobs.append((sseed, b, kw))
    rows = Parallel(n_jobs=n_jobs)(delayed(_one)(s, b, kw, False) for s, b, kw in jobs)
    X = np.vstack([r[0] for r in rows])
    Y = np.vstack([r[1] for r in rows])
    G = np.vstack([r[2] for r in rows])
    meta = pd.DataFrame([r[3] for r in rows])
    return Dataset(X, Y, G, meta)
