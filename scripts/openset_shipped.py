"""Measure the shipped guard (deltat_doctor.openset) in both directions. Writes results/openset_shipped.json.
Building-level: share of other-world buildings flagged / held-out in-world buildings flagged (median-window rule)."""
import json, os, sys
import numpy as np
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
from sklearn.metrics import roc_auc_score
from sklearn.model_selection import GroupKFold
from deltat_doctor.openset import OpenSetGuard
from deltat_doctor.sim.dataset import Dataset

D = {k: Dataset.load(p) for k, p in (("A", "results/data/main.npz"), ("B", "results/data_b/main.npz"))}
res = {}
for fit, other in (("A", "B"), ("B", "A")):
    d, o = D[fit], D[other]
    g = d.meta["building_id"].to_numpy(); tr, te = next(GroupKFold(5).split(d.X, groups=g))
    gd = OpenSetGuard().fit(d.X[tr])
    s_in, s_out = gd.score(d.X[te]), gd.score(o.X)
    def bshare(X, ids):
        s = gd.score(X); return float(np.mean([np.median(s[ids == b]) > gd.threshold for b in np.unique(ids)]))
    y = np.r_[np.zeros(len(s_in)), np.ones(len(s_out))]
    res[f"fit_{fit}"] = {"auroc_window": float(roc_auc_score(y, np.r_[s_in, s_out])),
        "windows_flagged_in_world": float((s_in > gd.threshold).mean()), "windows_flagged_other": float((s_out > gd.threshold).mean()),
        "buildings_flagged_in_world": bshare(d.X[te], g[te]), "buildings_flagged_other": bshare(o.X, o.meta["building_id"].to_numpy())}
    print(fit, {k: round(v, 3) for k, v in res[f"fit_{fit}"].items()}, flush=True)
json.dump(res, open("results/openset_shipped.json", "w"), indent=2)
