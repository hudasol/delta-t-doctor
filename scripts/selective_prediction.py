"""Selective prediction: which label free signal tells when the cause ranking is wrong? Protocol and predictions: docs/research/SELECTIVE_PREDICTION.md.

usage: python scripts/selective_prediction.py           writes results/selective_prediction.json

Seeds: model seed 0; ensemble members 0 to 4; CV folds from GroupKFold (deterministic); bootstrap seed 0. n_jobs is not used (single process).
"""
import json, os, sys, time, warnings
import numpy as np
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score
from sklearn.model_selection import GroupKFold

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))
from deltat_doctor import CAUSES
from deltat_doctor.diagnose import load_default_model
from deltat_doctor.features import FEATURE_NAMES
from deltat_doctor.models import Diagnoser
from deltat_doctor.openset import OpenSetGuard
from deltat_doctor.sim.dataset import Dataset

warnings.simplefilter("ignore")
NF = len(FEATURE_NAMES)
SIGNALS = ["S1_guard", "S2_entropy", "S3_margin", "S4_disagreement"]
t0 = time.time()


def log(*a):
    print(f"[{time.time() - t0:6.0f}s]", *a, flush=True)


class Clf:
    """The product's calibrated classifiers (four causes and any fault), seed 0."""

    def fit(self, X, Y, g):
        d = Diagnoser(seed=0)
        self.c = [d._calibrated(X, Y[:, k].astype(int), g) for k in range(len(CAUSES))]
        self.a = d._calibrated(X, (Y.sum(1) > 0).astype(int), g)
        return self

    def predict(self, X):
        return np.column_stack([c.predict_proba(X)[:, 1] for c in self.c]), self.a.predict_proba(X)[:, 1]


def ensemble_disagreement(X, Y, g, Xt, members=5):
    ids = np.unique(g)
    probs = []
    for m in range(members):
        pick = np.random.default_rng(m).choice(ids, len(ids), replace=True)
        rows = np.concatenate([np.flatnonzero(g == b) for b in pick])
        p = np.zeros((len(Xt), len(CAUSES)))
        for k in range(len(CAUSES)):
            y = Y[rows, k].astype(int)
            if 0 < y.sum() < len(y):
                p[:, k] = HistGradientBoostingClassifier(max_iter=120, learning_rate=0.08, max_leaf_nodes=15, min_samples_leaf=15,
                                                         random_state=m).fit(X[rows], y).predict_proba(Xt)[:, 1]
            else:
                p[:, k] = y.mean()
        probs.append(p)
    return np.std(np.stack(probs), axis=0).mean(axis=1)


def bin_entropy(p):
    p = np.clip(p, 1e-6, 1 - 1e-6)
    return -(p * np.log(p) + (1 - p) * np.log(1 - p))


def decision_wrong(prob, p_any, Y):
    present = Y.sum(1) > 0
    top = prob.argmax(1)
    says_healthy = p_any < 0.5
    return np.where(says_healthy, present, Y[np.arange(len(Y)), top] == 0).astype(int)


def signals(prob, p_any, guard_score, disagreement):
    ent = bin_entropy(prob).sum(1) + bin_entropy(p_any)
    margin = -np.minimum(np.abs(p_any - 0.5), np.abs(prob.max(1) - 0.5))
    return {"S1_guard": guard_score, "S2_entropy": ent, "S3_margin": margin, "S4_disagreement": disagreement}


def setting(Xtr, Ytr, gtr, Xte, Yte, gte, model=None, guard=None):
    if model is None:
        model = Clf().fit(Xtr, Ytr, gtr)
        prob, p_any = model.predict(Xte)
    else:
        p = model.predict(Xte)
        prob, p_any = p.prob, p.p_any
    guard = guard or OpenSetGuard().fit(Xtr[:, :NF])
    s = signals(prob, p_any, guard.score(Xte[:, :NF]), ensemble_disagreement(Xtr, Ytr, gtr, Xte))
    return {"sig": s, "wrong": decision_wrong(prob, p_any, Yte), "brier": ((prob - Yte) ** 2).mean(1), "groups": gte}


def aurc(score, loss):
    """Risk coverage, tie aware: windows with equal scores are kept in random order, so within a tied block the expected loss is used.
    (The first v1.2.1 run broke ties by file order; isotonic probabilities and the capped guard score have many exact ties.)"""
    score = np.asarray(score, float)
    loss = np.asarray(loss, float)
    order = np.argsort(score, kind="stable")
    s_sorted, l_sorted = score[order], loss[order]
    n = len(l_sorted)
    _, start, counts = np.unique(s_sorted, return_index=True, return_counts=True)
    block_mean = np.repeat(np.add.reduceat(l_sorted, start) / counts, counts)
    cum = np.concatenate([[0.0], np.cumsum(block_mean)])
    covs = np.arange(10, 101) / 100
    keep = [max(1, int(round(c * n))) for c in covs]
    risks = np.array([cum[m] / m for m in keep])
    return float(risks.mean()), float(cum[n // 2] / (n // 2)), [float(r) for r in risks[::10]]


def auc(score, wrong):
    return float(roc_auc_score(wrong, score)) if 0 < wrong.sum() < len(wrong) else float("nan")


def measures(r, names):
    out = {"n_windows": int(len(r["wrong"])), "base_error_rate": float(r["wrong"].mean()), "mean_brier": float(r["brier"].mean()),
           "share_of_tied_values": {nme: float(1 - len(np.unique(r["sig"][nme])) / len(r["sig"][nme])) for nme in names}}
    oracle = aurc(r["wrong"] + 1e-9 * np.arange(len(r["wrong"])), r["wrong"])[0]
    out["oracle_aurc"] = oracle
    for nme in names:
        a, r50, curve = aurc(r["sig"][nme], r["wrong"])
        out[nme] = {"auroc_wrong": auc(r["sig"][nme], r["wrong"]), "aurc": a, "risk_at_50pct_coverage": r50, "risk_curve_10_to_100": curve,
                    "auroc_brier_above_median": auc(r["sig"][nme], (r["brier"] > np.median(r["brier"])).astype(int)),
                    "brier_aurc": aurc(r["sig"][nme], r["brier"])[0], "brier_at_50pct_coverage": aurc(r["sig"][nme], r["brier"])[1]}
    return out


def main():
    A, B, D = (Dataset.load(p) for p in ("results/data/main.npz", "results/data_b/main.npz", "results/data_d/main.npz"))
    gA, gB, gD = (d.meta["building_id"].to_numpy() for d in (A, B, D))
    runs = {}
    for name, d, g in (("in_world_A", A, gA), ("in_world_B", B, gB)):
        parts = []
        for tr, te in GroupKFold(3).split(d.X, d.Y, g):
            parts.append(setting(d.X[tr], d.Y[tr], g[tr], d.X[te], d.Y[te], g[te]))
            log(name, "fold done")
        runs[name] = {"sig": {s: np.concatenate([p["sig"][s] for p in parts]) for s in SIGNALS},
                      "wrong": np.concatenate([p["wrong"] for p in parts]), "brier": np.concatenate([p["brier"] for p in parts]),
                      "groups": np.concatenate([p["groups"] for p in parts])}
    runs["A_to_B"] = setting(A.X, A.Y, gA, B.X, B.Y, gB); log("A_to_B done")
    runs["B_to_A"] = setting(B.X, B.Y, gB, A.X, A.Y, gA); log("B_to_A done")
    m = load_default_model()
    XAB, YAB, gAB = np.vstack([A.X, B.X]), np.vstack([A.Y, B.Y]), np.concatenate([gA, gB + 100000])
    runs["world_D"] = setting(XAB, YAB, gAB, D.X, D.Y, gD, model=m, guard=m.guard); log("world_D done")

    # S5: logistic regression on S1 to S4 (raw values, standardised on the A and B rows). For settings 1 to 4 it is fitted on the other three
    # settings (so it is never scored on rows it was fitted on); for world D it is fitted on all four. D is never used for fitting.
    labelled = ["in_world_A", "in_world_B", "A_to_B", "B_to_A"]
    F = {k: np.column_stack([runs[k]["sig"][s] for s in SIGNALS]) for k in runs}
    allF = np.vstack([F[k] for k in labelled])
    mu, sd = allF.mean(0), allF.std(0) + 1e-12
    # S5b (sensitivity, not preregistered): leave the target world out entirely. in_world_A and B_to_A score the same A windows, and
    # in_world_B and A_to_B the same B windows, so leave one setting out still fits S5 on the same windows (under a different model).
    target = {"in_world_A": "A", "B_to_A": "A", "in_world_B": "B", "A_to_B": "B"}
    for k in labelled:
        train = [x for x in labelled if target[x] != target[k]]
        lr = LogisticRegression(C=1.0, max_iter=1000).fit((np.vstack([F[x] for x in train]) - mu) / sd,
                                                          np.concatenate([runs[x]["wrong"] for x in train]))
        runs[k]["sig"]["S5b_leave_target_world_out"] = lr.decision_function((F[k] - mu) / sd)
    for k in runs:
        train = [x for x in labelled if x != k]
        lr = LogisticRegression(C=1.0, max_iter=1000).fit((np.vstack([F[x] for x in train]) - mu) / sd,
                                                          np.concatenate([runs[x]["wrong"] for x in train]))
        runs[k]["sig"]["S5_combination"] = lr.decision_function((F[k] - mu) / sd)
        if k == "world_D":
            coef = {s: float(c) for s, c in zip(SIGNALS, lr.coef_[0])}
            thr = float(np.percentile(lr.decision_function((allF - mu) / sd), 95))
    names = SIGNALS + ["S5_combination"]
    np.savez_compressed("results/selective_prediction_windows.npz",
                        **{f"{k}__{sg}": v for k, r in runs.items() for sg, v in r["sig"].items()},
                        **{f"{k}__wrong": r["wrong"] for k, r in runs.items()}, **{f"{k}__brier": r["brier"] for k, r in runs.items()},
                        **{f"{k}__groups": r["groups"] for k, r in runs.items()})
    res = {"definition": "wrong = says no material cause while one is present, or the top ranked cause is not present (window level)",
           "S5_coefficients_fitted_on_A_and_B": coef, "S5_threshold_95th_percentile_A_and_B": thr,
           "settings": {k: measures(r, names + (["S5b_leave_target_world_out"] if k != "world_D" else [])) for k, r in runs.items()},
           "world_D_windows_at_maximum_guard_score": int((runs["world_D"]["sig"]["S1_guard"] >= runs["world_D"]["sig"]["S1_guard"].max()).sum())}

    # building bootstrap (500 resamples, seed 0): on D for S1, S3 and S5; in world A and B for S1 and S3
    q = lambda v: [float(np.nanpercentile(v, 2.5)), float(np.nanpercentile(v, 97.5))]

    def boot(r, keys):
        ids = np.unique(r["groups"])
        rows = {b: np.flatnonzero(r["groups"] == b) for b in ids}
        rng = np.random.default_rng(0)
        bs = {f"{m}_{k}": [] for k in keys for m in ("auroc", "aurc")}
        for _ in range(500):
            idx = np.concatenate([rows[b] for b in rng.choice(ids, len(ids))])
            w = r["wrong"][idx]
            for k in keys:
                bs[f"auroc_{k}"].append(auc(r["sig"][k][idx], w))
                bs[f"aurc_{k}"].append(aurc(r["sig"][k][idx], w)[0])
        return {k: np.array(v) for k, v in bs.items()}

    bs = boot(runs["world_D"], ["S1_guard", "S3_margin", "S5_combination"])
    res["world_D_bootstrap"] = {"auroc_S1": q(bs["auroc_S1_guard"]), "auroc_S3": q(bs["auroc_S3_margin"]), "auroc_S5": q(bs["auroc_S5_combination"]),
                                "auroc_S5_minus_S1": q(bs["auroc_S5_combination"] - bs["auroc_S1_guard"]),
                                "auroc_S3_minus_S1": q(bs["auroc_S3_margin"] - bs["auroc_S1_guard"]),
                                "aurc_S1": q(bs["aurc_S1_guard"]), "aurc_S3": q(bs["aurc_S3_margin"]), "aurc_S5": q(bs["aurc_S5_combination"]),
                                "aurc_S5_minus_S1": q(bs["aurc_S5_combination"] - bs["aurc_S1_guard"])}
    for k in ("in_world_A", "in_world_B"):
        b2 = boot(runs[k], ["S1_guard", "S3_margin"])
        res[f"{k}_bootstrap"] = {"auroc_S1": q(b2["auroc_S1_guard"]), "auroc_S3": q(b2["auroc_S3_margin"])}
    sD, sA, sB = (res["settings"][k] for k in ("world_D", "in_world_A", "in_world_B"))
    rule = {"a_D_auroc_S5_above_S1_interval_above_0": bool(res["world_D_bootstrap"]["auroc_S5_minus_S1"][0] > 0),
            "b_D_aurc_S5_below_S1": bool(sD["S5_combination"]["aurc"] < sD["S1_guard"]["aurc"]),
            "c_in_world_A_and_B_aurc_not_worse_by_0.005": bool(all(s["S5_combination"]["aurc"] <= s["S1_guard"]["aurc"] + 0.005 for s in (sA, sB)))}
    rule["ship"] = all(rule.values())
    res["shipping_rule"] = rule
    json.dump(res, open("results/selective_prediction.json", "w"), indent=2, default=float)
    for k, v in res["settings"].items():
        log(k, "base", round(v["base_error_rate"], 3), {s: (round(v[s]["auroc_wrong"], 3), round(v[s]["aurc"], 3)) for s in names})
    log("rule", rule)


if __name__ == "__main__":
    main()
