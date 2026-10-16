"""Why does fouling transfer worst from A to B? Tests H1 to H4 preregistered in docs/TRANSFER_V2.md (addendum). Writes
results/fouling_transfer.json.

Only the fouling classifier is fitted (the product's calibrated booster, Diagnoser._calibrated, seed 0).
"""
import json, os, sys, time
import numpy as np
from sklearn.inspection import partial_dependence, permutation_importance
from sklearn.metrics import roc_auc_score
from sklearn.model_selection import GroupKFold

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))
from deltat_doctor.features import FEATURE_NAMES
from deltat_doctor.models import Diagnoser
from deltat_doctor.sim.dataset import Dataset

t0 = time.time()
K = 0   # fouling column
D = {"A": Dataset.load("results/data/main.npz"), "B": Dataset.load("results/data_b/main.npz")}
F = FEATURE_NAMES
GROUPS = {
    "delta_t_shape": ["dt_period", "dt_p10", "dt_p90", "dt_std_loaded", "dt_lowload", "dt_night_minus_day", "dt_weekend_minus_week",
                      "dt_hi_minus_mid"] + [f"dt_bin{i}" for i in range(8)],
    "flow_shape": ["zero_flow_frac", "flow_lowload_share", "flow_intercept_ratio", "flow_load_corr", "flow_cv_loaded", "flow_p10_over_p95",
                   "flow_p50_over_p95"] + [f"flow_bin{i}" for i in range(8)],
    "load_distribution": ["duty_factor", "load_p10_over_p98"] + [f"frac_bin{i}" for i in range(8)],
    "weather": ["dt_vs_oat_slope"],
}
assert sorted(sum(GROUPS.values(), [])) == sorted(F)


def log(*a):
    print(f"[{time.time() - t0:5.0f}s]", *a, flush=True)


def effects(d):
    """Median shift of each feature in single fault fouling windows against healthy windows, in healthy spread units."""
    h = d.X[d.Y.sum(1) == 0]
    med = np.median(h, 0)
    sc = np.maximum(np.subtract(*np.percentile(h, [95, 5], 0)) / 3.3, 0.25 * d.X.std(0)) + 1e-9
    sel = (d.Y[:, K] == 1) & (d.Y.sum(1) == 1)
    return (np.median(d.X[sel], 0) - med) / sc


def fit(X, y, g):
    return Diagnoser(seed=0)._calibrated(X, y.astype(int), g)


def auc(m, X, y):
    return float(roc_auc_score(y, m.predict_proba(X)[:, 1]))


res = {}
eA, eB = effects(D["A"]), effects(D["B"])
top = list(np.argsort(-np.abs(eA))[:5])
res["H1"] = {"top5_A": [F[i] for i in top], "effect_A": [float(eA[i]) for i in top], "effect_B": [float(eB[i]) for i in top],
             "median_abs_A": float(np.median(np.abs(eA[top]))), "median_abs_B": float(np.median(np.abs(eB[top])))}
res["H1"]["held"] = res["H1"]["median_abs_B"] < 0.5 * res["H1"]["median_abs_A"]
uni = {w: [float(roc_auc_score(D[w].Y[:, K], D[w].X[:, i])) for i in top] for w in D}
opposite = [F[top[j]] for j in range(5) if (uni["A"][j] - 0.5) * (uni["B"][j] - 0.5) < 0]
res["H2"] = {"univariate_auroc_A": uni["A"], "univariate_auroc_B": uni["B"], "opposite_side": opposite, "held": len(opposite) >= 2}
log("H1", res["H1"]["held"], "H2", res["H2"]["held"], opposite)

g = {w: D[w].meta["building_id"].to_numpy() for w in D}
res["H3"] = {}
for src, tgt in (("A", "B"), ("B", "A")):
    r = {}
    for name, cols in [("all", [])] + list(GROUPS.items()):
        keep = [i for i, f in enumerate(F) if f not in cols]
        m = fit(D[src].X[:, keep], D[src].Y[:, K], g[src])
        r[name if name == "all" else "without_" + name] = auc(m, D[tgt].X[:, keep], D[tgt].Y[:, K])
        log("H3", src, "->", tgt, name, round(r[name if name == "all" else "without_" + name], 3))
    r["delta_without_delta_t_shape"] = r["without_delta_t_shape"] - r["all"]
    res["H3"][f"{src}_to_{tgt}"] = r
res["H3"]["held"] = bool(res["H3"]["A_to_B"]["delta_without_delta_t_shape"] >= 0.02 and res["H3"]["B_to_A"]["delta_without_delta_t_shape"] <= -0.02)

oof = np.zeros(len(D["B"].Y))
for tr, te in GroupKFold(5).split(D["B"].X, D["B"].Y, g["B"]):
    oof[te] = fit(D["B"].X[tr], D["B"].Y[tr, K], g["B"][tr]).predict_proba(D["B"].X[te])[:, 1]
inB = float(roc_auc_score(D["B"].Y[:, K], oof))
res["H4"] = {"in_world_B_fouling_auroc_5fold": inB, "A_to_B_k40_fouling_from_transfer_fewshot": 0.66,
             "held": bool(inB <= 0.75 and abs(inB - 0.66) <= 0.10)}
log("H4", inB)

# descriptive: permutation importance of the A trained fouling classifier, on held out A buildings and on B
ids = np.unique(g["A"]); rng = np.random.default_rng(0); rng.shuffle(ids)
te = np.isin(g["A"], ids[:100])
mA = fit(D["A"].X[~te], D["A"].Y[~te, K], g["A"][~te])
pi = {}
for name, X, y in (("heldout_A", D["A"].X[te], D["A"].Y[te, K]), ("B", D["B"].X, D["B"].Y[:, K])):
    p = permutation_importance(mA, X, y, scoring="roc_auc", n_repeats=5, random_state=0)
    order = np.argsort(-p.importances_mean)[:8]
    pi[name] = [{"feature": F[i], "auroc_drop": float(p.importances_mean[i])} for i in order]
res["permutation_importance_A_trained"] = pi
top2 = [F.index(x["feature"]) for x in pi["heldout_A"][:2]]
pdp = {}
for i in top2:
    grid = np.linspace(*np.percentile(np.vstack([D["A"].X, D["B"].X])[:, i], [2, 98]), 12)
    pd_ = partial_dependence(mA, D["A"].X[~te], [i], custom_values={i: grid}, kind="average")
    pdp[F[i]] = {"grid": [float(v) for v in grid], "pd": [float(v) for v in pd_["average"][0]],
                 "A_p5_p95": [float(v) for v in np.percentile(D["A"].X[:, i], [5, 95])],
                 "B_p5_p95": [float(v) for v in np.percentile(D["B"].X[:, i], [5, 95])]}
res["partial_dependence_A_trained"] = pdp
json.dump(res, open("results/fouling_transfer.json", "w"), indent=2, default=float)
log("done", {k: v.get("held") for k, v in res.items() if isinstance(v, dict) and "held" in v})
