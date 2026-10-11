"""Overflow identifiability. Predictions: docs/OVERFLOW.md. Writes results/overflow_analysis.json."""
import json, os, sys
import numpy as np
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
from sklearn.ensemble import HistGradientBoostingClassifier as HGB
from sklearn.metrics import roc_auc_score
from sklearn.model_selection import GroupKFold
from deltat_doctor import CAUSES
from deltat_doctor.sim.dataset import Dataset

D = {"A": Dataset.load("results/data/main.npz"), "B": Dataset.load("results/data_b/main.npz")}
OV = CAUSES.index("overflow")
rng = np.random.default_rng(0)


def dp_channel(d):
    """Simulated measured DP channel: normalised excess loop DP. Overflow windows read high (1.3 to 2.6), others about 1.0; 10% noise.
    Generated from the label by construction (ceiling test only)."""
    ov = d.Y[:, OV] > 0
    base = np.where(ov, rng.uniform(1.3, 2.6, len(ov)), 1.0 + rng.normal(0, 0.05, len(ov)))
    return (base * (1 + rng.normal(0, 0.10, len(ov))))[:, None]


def fit_pred(Xtr, ytr, Xte):
    m = HGB(max_iter=300, learning_rate=0.06, random_state=0).fit(Xtr, ytr)
    return m.predict_proba(Xte)[:, 1]


def auc(y, s):
    return float(roc_auc_score(y, s)) if 0 < y.sum() < len(y) else float("nan")


res = {}
for w, d in D.items():
    g = d.meta["building_id"].to_numpy()
    tr, te = next(GroupKFold(5).split(d.X, groups=g))
    Y = d.Y; n = Y.sum(1)
    s = fit_pred(d.X[tr], Y[tr, OV], d.X[te])
    r = {"overflow_vs_all": auc(Y[te, OV], s)}
    per = {}
    for j, c in enumerate(CAUSES):  # AUROC of each cause (to rank)
        per[c] = auc(Y[te, j], fit_pred(d.X[tr], Y[tr, j], d.X[te]))
    r["per_cause"] = per
    single = (n[te] <= 1)
    r["overflow_single_fault"] = auc(Y[te, OV][single], s[single])
    ov_te = Y[te, OV] > 0
    multi = (n[te] >= 2) | (~ov_te)  # overflow co-occurring (n>=2) versus clean healthy/other-only? use: positives multi vs negatives all
    pos_multi = ov_te & (n[te] >= 2); pos_single = ov_te & (n[te] == 1); neg = ~ov_te
    r["overflow_cooccurring_vs_negatives"] = auc(np.r_[np.ones(pos_multi.sum()), np.zeros(neg.sum())], np.r_[s[pos_multi], s[neg]])
    r["overflow_alone_vs_negatives"] = auc(np.r_[np.ones(pos_single.sum()), np.zeros(neg.sum())], np.r_[s[pos_single], s[neg]])
    r["n_pos_single"], r["n_pos_multi"] = int(pos_single.sum()), int(pos_multi.sum())
    pairs = {}
    for j, c in enumerate(CAUSES):
        if j == OV: continue
        m_ = (Y[te].sum(1) == 1) & ((Y[te, OV] > 0) | (Y[te, j] > 0))
        pairs[c] = auc(Y[te, OV][m_], s[m_])
    r["pairs_single_fault"] = pairs
    res[w] = r
    print(w, json.dumps(r, indent=1), flush=True)

# DP ceiling
for a, b in (("A", "B"), ("B", "A")):
    da, db = D[a], D[b]
    ga = da.meta["building_id"].to_numpy(); tr, te = next(GroupKFold(5).split(da.X, groups=ga))
    Xa = np.hstack([da.X, dp_channel(da)]); Xb = np.hstack([db.X, dp_channel(db)])
    s_in = fit_pred(Xa[tr], da.Y[tr, OV], Xa[te])
    s_x = fit_pred(Xa, da.Y[:, OV], Xb)
    res.setdefault("dp_ceiling", {})[f"{a}_in_world"] = auc(da.Y[te, OV], s_in)
    res["dp_ceiling"][f"{a}_to_{b}"] = auc(db.Y[:, OV], s_x)
    print("DP", a, res["dp_ceiling"], flush=True)
json.dump(res, open("results/overflow_analysis.json", "w"), indent=2)
