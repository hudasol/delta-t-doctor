"""Transfer v2: do wider randomisation, invariant features or target-batch standardisation close the cross-physics gap?
Predictions: docs/research/TRANSFER_V2.md (written before this ran). Writes results/transfer_v2.json and .md.

T1: train A (+C-A), test B.   T2: train B (+C-B), test A.   Never trains on the test physics.
Dropped features are zeroed (not removed) so the model's column layout is unchanged.
"""
import json, os, sys, time
import numpy as np
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
from sklearn.model_selection import GroupKFold
from deltat_doctor import CAUSES
from deltat_doctor.evaluate import bootstrap_ci, metrics
from deltat_doctor.features import FEATURE_NAMES
from deltat_doctor.models import Diagnoser
from deltat_doctor.sim.dataset import Dataset

D = {k: Dataset.load(p) for k, p in (("A", "results/data/main.npz"), ("B", "results/data_b/main.npz"),
                                       ("CA", "results/data_ca/main.npz"), ("CB", "results/data_cb/main.npz"))}
OFF = {"A": 0, "B": 100000, "CA": 200000, "CB": 300000}

def stack(keys):
    X = np.vstack([D[k].X for k in keys]); Y = np.vstack([D[k].Y for k in keys]); G = np.vstack([D[k].G for k in keys])
    g = np.concatenate([D[k].meta["building_id"].to_numpy() + OFF[k] for k in keys])
    return X, Y, G, g

def world_std(X):
    med = np.median(X, 0); iqr = np.subtract(*np.percentile(X, [75, 25], 0)) + 1e-6
    return (X - med) / iqr

def effects(d):
    h = d.X[d.Y.sum(1) == 0]; med = np.median(h, 0); sc = np.maximum(np.subtract(*np.percentile(h, [95, 5], 0)) / 3.3, 0.25 * d.X.std(0)) + 1e-9
    out = []
    for k in range(4):
        sel = (d.Y[:, k] == 1) & (d.Y.sum(1) == 1)
        out.append((np.median(d.X[sel], 0) - med) / sc)
    return np.array(out)       # (4, F)

def invariant_mask(w1, w2, drop=0.30):
    e1, e2 = effects(D[w1]), effects(D[w2])
    inst = (np.abs(e1 - e2) / (np.abs(e1) + np.abs(e2) + 0.5)).max(0)
    keep = inst <= np.quantile(inst, 1 - drop)
    return keep, inst

def fit_eval(train_keys, test_key, keep=None, batch=False, seed=0):
    X, Y, G, g = stack(train_keys)
    Xt = D[test_key].X.copy()
    if batch:
        X = np.vstack([world_std(D[k].X) for k in train_keys]); Xt = world_std(Xt)
    if keep is not None:
        X = X * keep; Xt = Xt * keep
    m = Diagnoser(seed=seed).fit(X, Y, G, groups=g)
    p = m.predict(Xt)
    t = D[test_key]
    r = metrics(t, p)
    healthy = t.Y.sum(1) == 0
    out = {"macro_auroc": r["macro_auroc"], "any_fault_auroc": r["any_fault_auroc"],
           "per_cause": {c: r["per_cause"][c]["auroc"] for c in CAUSES},
           "healthy_false_alarm": float((p.p_any[healthy] >= 0.5).mean()),
           "ci": bootstrap_ci(t, {"m": p}, n_boot=100, ref="m")["models"]["m"]["macro_auroc"]["ci95"]}
    return out

def in_world(train_keys, test_key, keep=None, batch=False):
    """One building-grouped fold of the test world; the training worlds may add extra data."""
    d = D[test_key]; g = d.meta["building_id"].to_numpy()
    tr, te = next(GroupKFold(5).split(d.X, groups=g))
    X, Y, G, gg = stack([k for k in train_keys if k != test_key]) if len(train_keys) > 1 else (np.empty((0, d.X.shape[1])), np.empty((0, 4)), np.empty((0, 4)), np.empty(0))
    Xa = np.vstack([X, d.X[tr]]); Ya = np.vstack([Y, d.Y[tr]]); Ga = np.vstack([G, d.G[tr]]); ga = np.concatenate([gg, g[tr] + OFF[test_key]])
    Xt = d.X[te]
    if batch:
        Xa = np.vstack([world_std(x) for x in ([D[k].X for k in train_keys if k != test_key] + [d.X[tr]])]); Xt = world_std(d.X[te])
    if keep is not None:
        Xa, Xt = Xa * keep, Xt * keep
    m = Diagnoser(seed=0).fit(Xa, Ya, Ga, groups=ga)
    mask = np.zeros(len(d.X), bool); mask[te] = True
    return float(metrics(d.subset(mask), m.predict(Xt))["macro_auroc"])

MODE = sys.argv[1] if len(sys.argv) > 1 else "all"
res = json.load(open("results/transfer_v2.json")) if os.path.exists("results/transfer_v2.json") and MODE != "all" else {}
t0 = time.time()
if MODE == "all":
    for name, (base, wide, other) in {"T1": ("A", "CA", "B"), "T2": ("B", "CB", "A")}.items():
        keep, inst = invariant_mask(base, wide)
        res[name] = {"dropped_features": [FEATURE_NAMES[i] for i in np.where(~keep)[0]]}
        for tag, kw in {"baseline": dict(keys=[base]), "wide": dict(keys=[base, wide]),
                        "invariant": dict(keys=[base], keep=keep), "batch_std": dict(keys=[base], batch=True),
                        "combined": dict(keys=[base, wide], keep=keep)}.items():
            res[name][tag] = fit_eval(kw["keys"], other, kw.get("keep"), kw.get("batch", False))
            print(name, tag, round(res[name][tag]["macro_auroc"], 3), f"{time.time()-t0:.0f}s", flush=True)
            json.dump(res, open("results/transfer_v2.json", "w"), indent=2)
if MODE in ("all", "inworld"):
    res["in_world"] = {}
    for w, wide in (("A", "CA"), ("B", "CB")):
        keep, _ = invariant_mask(w, wide)
        res["in_world"][w] = {"baseline": in_world([w], w), "wide": in_world([w, wide], w), "invariant": in_world([w], w, keep),
                              "batch_std": in_world([w], w, None, True)}
        print("in-world", w, res["in_world"][w], flush=True)
        json.dump(res, open("results/transfer_v2.json", "w"), indent=2)
if MODE == "seeds":
    res["seeds"] = {}
    for name, (base, wide, other) in {"T1": ("A", "CA", "B"), "T2": ("B", "CB", "A")}.items():
        keep, _ = invariant_mask(base, wide)
        res["seeds"][name] = {}
        for tag, kw in {"baseline": dict(keys=[base]), "invariant": dict(keys=[base], keep=keep), "batch_std": dict(keys=[base], batch=True)}.items():
            vals = [fit_eval(kw["keys"], other, kw.get("keep"), kw.get("batch", False), seed=s)["macro_auroc"] for s in (1, 2, 3)]
            res["seeds"][name][tag] = {"values": vals, "mean": float(np.mean(vals)), "sd": float(np.std(vals))}
            print("seeds", name, tag, res["seeds"][name][tag], flush=True)
            json.dump(res, open("results/transfer_v2.json", "w"), indent=2)
