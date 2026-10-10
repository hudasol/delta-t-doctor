"""Open-set guard benchmark: fit on one simulator, test on the other and on stress sets. Writes results/openset.json.

The shipped guard is fit on A+B, so this is a leave-one-world-out *estimate* of how it behaves on a world it never saw.
Held-out in-world false flag rate uses building-grouped folds.
"""
import json, os, sys
import numpy as np
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
from sklearn.model_selection import GroupKFold
from deltat_doctor.openset import OpenSetGuard
from deltat_doctor.sim.dataset import Dataset
import glob

A = Dataset.load("results/data/main.npz"); B = Dataset.load("results/data_b/main.npz")
n = A.X.shape[1]

def box_flag(Xtr, Xte):
    lo, hi = np.percentile(Xtr, 1, 0), np.percentile(Xtr, 99, 0)
    lim = np.percentile(((Xtr < lo) | (Xtr > hi)).sum(1), 95)
    return (((Xte < lo) | (Xte > hi)).sum(1) > lim).mean()

res = {}
for name, tr, other in (("fit_A", A, B), ("fit_B", B, A)):
    g = tr.meta["building_id"].to_numpy()
    a, b = next(GroupKFold(5).split(tr.X, groups=g))
    guard = OpenSetGuard().fit(tr.X[a])
    res[name] = {"in_world_heldout_flag_rate": float((guard.score(tr.X[b]) > guard.threshold).mean()),
                 "other_world_flag_rate": float((guard.score(other.X) > guard.threshold).mean()),
                 "box_in_world": float(box_flag(tr.X[a], tr.X[b])), "box_other_world": float(box_flag(tr.X[a], other.X)),
                 "n_train": int(len(a)), "n_other": int(len(other.X))}
g = A.meta["building_id"].to_numpy(); a, b = next(GroupKFold(5).split(A.X, groups=g))
guard = OpenSetGuard().fit(A.X[a]); stress = {}
for f in sorted(glob.glob("results/data/stress_*.npz")):
    d = Dataset.load(f); stress[os.path.basename(f)[7:-4]] = float((guard.score(d.X) > guard.threshold).mean())
res["fit_A_stress_flag_rate"] = stress
os.makedirs("results", exist_ok=True)
json.dump(res, open("results/openset.json", "w"), indent=2)
print(json.dumps(res, indent=1))
