"""Repeat the whole pipeline (new buildings, new faults, new training) under several generator seeds.

The bootstrap intervals in results/metrics.md reflect test-set noise only. This shows the spread you get from regenerating
the data and retraining. Writes results/seed_replication.json.
"""
import json, os, sys
import numpy as np
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
from deltat_doctor.evaluate import MODELS, cross_validate
from deltat_doctor.sim.dataset import generate

rows = []
for seed in (101, 202, 303, 404):
    ds = generate(250, 8, seed=seed, n_jobs=2)
    m = cross_validate(ds, 5, models={"m": MODELS["ours_gbdt"]})["m"][0]
    rows.append({"seed": seed, "n": m["n"], "macro_auroc": m["macro_auroc"], "any_fault_auroc": m["any_fault_auroc"],
                 "macro_f1": m["macro_f1"], "per_cause_auroc": {c: v["auroc"] for c, v in m["per_cause"].items()}})
    print(rows[-1], flush=True)
agg = {k: {"mean": float(np.mean([r[k] for r in rows])), "sd": float(np.std([r[k] for r in rows], ddof=1))}
       for k in ("macro_auroc", "any_fault_auroc", "macro_f1")}
json.dump({"runs": rows, "aggregate": agg}, open("results/seed_replication.json", "w"), indent=2)
print(agg)
