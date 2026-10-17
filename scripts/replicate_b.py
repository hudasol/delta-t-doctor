"""Replicate the simulator B results on B pools generated with recorded seeds. Predictions: docs/REPRODUCIBILITY.md.

usage: python scripts/replicate_b.py [generate|evaluate|all]

generate: for each seed in SEEDS, writes results/data_b_r<seed>/main.npz (150 buildings x 10 windows, n_jobs=1) and generator.json.
evaluate: in world B (5 fold building grouped CV), A to B and B to A macro AUROC and the A to B healthy false alarm rate on every replicate
          (plus the seed 11 pool from results/data_b_t and the committed pool for reference). Writes results/replication_b.json.
Model: the product's calibrated classifiers (Diagnoser._calibrated, seed 0), as in scripts/cross_simulator.py.
"""
import json, os, platform, subprocess, sys, time
import numpy as np

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
sys.path.insert(0, os.path.join(ROOT, "src"))
from sklearn.model_selection import GroupKFold
from deltat_doctor import CAUSES, __version__
from deltat_doctor.evaluate import metrics
from deltat_doctor.models import Diagnoser, Prediction
from deltat_doctor.sim.dataset import Dataset, generate

SEEDS = (2101, 2102, 2103)
t0 = time.time()


def log(*a):
    print(f"[{time.time() - t0:6.0f}s]", *a, flush=True)


def gen(seed):
    out = os.path.join(ROOT, "results", f"data_b_r{seed}")
    if os.path.exists(os.path.join(out, "main.npz")):
        return
    os.makedirs(out, exist_ok=True)
    import numpy, pandas, sklearn
    commit = subprocess.run(["git", "rev-parse", "--short", "HEAD"], capture_output=True, text=True, cwd=ROOT).stdout.strip()
    meta = {"simulator": "B", "buildings": 150, "samples_per_building": 10, "seed": seed, "n_jobs": 1,
            "call": f"deltat_doctor.sim.dataset.generate(150, 10, seed={seed}, n_jobs=1, sim='B')",
            "package_version": __version__, "git_commit": commit, "python": platform.python_version(),
            "numpy": numpy.__version__, "pandas": pandas.__version__, "scikit_learn": sklearn.__version__}
    t = time.time()
    d = generate(150, 10, seed=seed, n_jobs=1, sim="B")
    d.save(os.path.join(out, "main.npz"))
    meta["seconds"] = round(time.time() - t, 1)
    json.dump(meta, open(os.path.join(out, "generator.json"), "w"), indent=2)
    log("generated", seed, meta["seconds"], "s")


class Clf:
    def fit(self, X, Y, g):
        d = Diagnoser(seed=0)
        self.c = [d._calibrated(X, Y[:, k].astype(int), g) for k in range(len(CAUSES))]
        self.a = d._calibrated(X, (Y.sum(1) > 0).astype(int), g)
        return self

    def predict(self, X):
        prob = np.column_stack([c.predict_proba(X)[:, 1] for c in self.c])
        return Prediction(prob, np.zeros_like(prob), self.a.predict_proba(X)[:, 1])


def in_world(d):
    g = d.meta["building_id"].to_numpy()
    pred = Prediction(np.zeros_like(d.Y), np.zeros_like(d.Y), np.zeros(len(d.Y)))
    for tr, te in GroupKFold(5).split(d.X, d.Y, g):
        p = Clf().fit(d.X[tr], d.Y[tr], g[tr]).predict(d.X[te])
        pred.prob[te], pred.p_any[te] = p.prob, p.p_any
    return metrics(d, pred)["macro_auroc"]


def evaluate():
    A = Dataset.load(os.path.join(ROOT, "results", "data", "main.npz"))
    gA = A.meta["building_id"].to_numpy()
    mA = Clf().fit(A.X, A.Y, gA)
    log("A model fitted")
    pools = {"committed": "results/data_b/main.npz", "seed_11": "results/data_b_t/main.npz"}
    pools |= {f"seed_{s}": f"results/data_b_r{s}/main.npz" for s in SEEDS}
    res = {"reference_committed_cross_simulator_json": {"in_world_B": 0.884, "A_to_B": 0.683, "B_to_A": 0.770, "A_to_B_healthy_false_alarm": 0.88},
           "pools": {}}
    for name, path in pools.items():
        B = Dataset.load(os.path.join(ROOT, path))
        gB = B.meta["building_id"].to_numpy()
        pAB = mA.predict(B.X)
        h = B.Y.sum(1) == 0
        mB = Clf().fit(B.X, B.Y, gB)
        r = {"path": path, "prevalence": {c: float(B.Y[:, k].mean()) for k, c in enumerate(CAUSES)},
             "in_world_B": in_world(B), "A_to_B": metrics(B, pAB)["macro_auroc"], "B_to_A": metrics(A, mB.predict(A.X))["macro_auroc"],
             "A_to_B_healthy_false_alarm": float((pAB.p_any[h] >= 0.5).mean())}
        res["pools"][name] = r
        log(name, {k: round(v, 3) for k, v in r.items() if isinstance(v, float)})
        json.dump(res, open(os.path.join(ROOT, "results", "replication_b.json"), "w"), indent=2)
    reps = [res["pools"][k] for k in res["pools"] if k != "committed"]
    res["spread_over_replicates"] = {k: float(max(r[k] for r in reps) - min(r[k] for r in reps))
                                     for k in ("in_world_B", "A_to_B", "B_to_A", "A_to_B_healthy_false_alarm")}
    json.dump(res, open(os.path.join(ROOT, "results", "replication_b.json"), "w"), indent=2)
    log("spread", res["spread_over_replicates"])


if __name__ == "__main__":
    mode = sys.argv[1] if len(sys.argv) > 1 else "all"
    if mode in ("generate", "all"):
        for s in SEEDS:
            gen(s)
    if mode in ("evaluate", "all"):
        evaluate()
