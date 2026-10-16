"""World D evaluation, in the order preregistered in docs/WORLD_D.md. Writes results/world_d.json (updated after every stage).

usage: python scripts/world_d_eval.py [zeroshot|guard|fewshot|temporal|all]

Needs results/data_d/main.npz (generate_data.py --sim D --buildings 150 --per 10 --seed 21 --temporal), results/data/main.npz and
results/data_b/main.npz with the temporal block (regenerated with --temporal; the 42 shape features are checked against the stored hashes
by scripts/check_regenerated.py), and the fresh in world sets, which this script generates and caches if missing.

Classifier only fits: few shot and temporal comparisons fit the product's calibrated classifiers (Diagnoser._calibrated, same settings
and seed) and skip the gain and quantile regressors, which do not enter any AUROC or false alarm figure.
"""
import json, os, sys, time
import numpy as np
from sklearn.model_selection import GroupKFold

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))
from deltat_doctor import CAUSES
from deltat_doctor.diagnose import load_default_model
from deltat_doctor.evaluate import _safe_auc, bootstrap_ci, metrics
from deltat_doctor.models import Diagnoser, Prediction
from deltat_doctor.sim.dataset import Dataset, generate

OUT = os.environ.get("DTD_OUT", "results/world_d.json")   # a separate file lets two stages run at once without overwriting
res = json.load(open(OUT)) if os.path.exists(OUT) else {}
t0 = time.time()


def save():
    json.dump(res, open(OUT, "w"), indent=2, default=float)


def log(*a):
    print(f"[{time.time() - t0:6.0f}s]", *a, flush=True)


def load(p):
    return Dataset.load(p)


def cached(path, **kw):
    if not os.path.exists(path):
        os.makedirs(os.path.dirname(path), exist_ok=True)
        generate(n_jobs=int(os.environ.get("DTD_JOBS", "8")), **kw).save(path)
    return load(path)


def per_cause_ci(ds, p, n_boot=1000, seed=0):
    rng = np.random.default_rng(seed)
    bid = ds.meta["building_id"].to_numpy()
    ids = np.unique(bid)
    rows = {b: np.flatnonzero(bid == b) for b in ids}
    draws = {c: [] for c in CAUSES}
    for _ in range(n_boot):
        idx = np.concatenate([rows[b] for b in rng.choice(ids, len(ids))])
        for k, c in enumerate(CAUSES):
            draws[c].append(_safe_auc(ds.Y[idx, k].astype(int), p.prob[idx, k]))
    return {c: [float(np.nanpercentile(v, 2.5)), float(np.nanpercentile(v, 97.5))] for c, v in draws.items()}


def summary(ds, p, boot=True):
    r = metrics(ds, p)
    h = ds.Y.sum(1) == 0
    out = {"macro_auroc": r["macro_auroc"], "any_fault_auroc": r["any_fault_auroc"],
           "per_cause": {c: r["per_cause"][c]["auroc"] for c in CAUSES}, "prevalence": r["prevalence"],
           "healthy_false_alarm": float((p.p_any[h] >= 0.5).mean()) if h.any() else float("nan"), "n_windows": int(len(ds.Y)),
           "n_healthy_windows": int(h.sum())}
    if boot:
        b = bootstrap_ci(ds, {"m": p}, n_boot=1000, ref="m")["models"]["m"]
        out["macro_auroc_ci95"] = b["macro_auroc"]["ci95"]
        out["any_fault_auroc_ci95"] = b["any_fault_auroc"]["ci95"]
        out["per_cause_ci95"] = per_cause_ci(ds, p)
    return out


class Clf:
    """The product's calibrated classifiers only (no regressors)."""

    def fit(self, X, Y, groups):
        d = Diagnoser(seed=0)
        self.c = {c: d._calibrated(X, Y[:, k].astype(int), groups) for k, c in enumerate(CAUSES)}
        self.a = d._calibrated(X, (Y.sum(1) > 0).astype(int), groups)
        return self

    def predict(self, X):
        prob = np.column_stack([self.c[c].predict_proba(X)[:, 1] for c in CAUSES])
        return Prediction(prob, np.zeros_like(prob), self.a.predict_proba(X)[:, 1])


MODE = sys.argv[1] if len(sys.argv) > 1 else "all"
D = load("results/data_d/main.npz")
res["data"] = {"D": {"windows": int(len(D.X)), "buildings": int(D.meta["building_id"].nunique()),
                     "prevalence": {c: float(D.Y[:, k].mean()) for k, c in enumerate(CAUSES)},
                     "healthy_share": float((D.Y.sum(1) == 0).mean()),
                     "dt_actual_percentiles_5_50_95": [float(v) for v in np.percentile(D.meta["dt_actual"], [5, 50, 95])]}}

if MODE in ("zeroshot", "all"):
    m = load_default_model()
    p = m.predict(D.X)
    res["zero_shot"] = summary(D, p)
    log("zero shot", res["zero_shot"]["macro_auroc"], res["zero_shot"]["per_cause"], res["zero_shot"]["healthy_false_alarm"])
    save()

if MODE in ("guard", "all"):
    m = load_default_model()
    sets = {"D": D, "fresh_A": cached("results/data_fresh_a/main.npz", n_buildings=80, samples_per_building=6, seed=1000, sim="A"),
            "fresh_B": cached("results/data_fresh_b/main.npz", n_buildings=80, samples_per_building=6, seed=2000, sim="B")}
    res["guard"] = {"threshold": m.guard.threshold, "box_limit": m.ood_threshold}
    for name, ds in sets.items():
        gs = m.guard.score(ds.X)
        gw = gs > m.guard.threshold
        bw = m.ood_count(ds.X) > m.ood_threshold
        bid = ds.meta["building_id"].to_numpy()
        gb, bb = [], []
        for b in np.unique(bid):
            sel = bid == b
            gb.append(np.median(gs[sel]) > m.guard.threshold)
            bb.append(m.ood_count(ds.X[sel]).mean() > m.ood_threshold)
        gb, bb = np.array(gb), np.array(bb)
        res["guard"][name] = {"windows_open_set": float(gw.mean()), "windows_box": float(bw.mean()), "windows_either": float((gw | bw).mean()),
                              "buildings_open_set": float(gb.mean()), "buildings_box": float(bb.mean()), "buildings_either": float((gb | bb).mean()),
                              "n_buildings": int(len(gb))}
        log("guard", name, res["guard"][name])
    p = m.predict(D.X)
    gw = m.guard.score(D.X) > m.guard.threshold
    res["guard"]["D_auroc_unflagged_windows"] = metrics(D.subset(~gw), Prediction(p.prob[~gw], p.gain[~gw], p.p_any[~gw]))["macro_auroc"] if (~gw).sum() > 50 else None
    res["guard"]["D_auroc_flagged_windows"] = metrics(D.subset(gw), Prediction(p.prob[gw], p.gain[gw], p.p_any[gw]))["macro_auroc"] if gw.sum() > 50 else None
    log("guard D auroc unflagged / flagged", res["guard"]["D_auroc_unflagged_windows"], res["guard"]["D_auroc_flagged_windows"])
    save()

if MODE in ("fewshot", "all"):
    A, B = load("results/data/main.npz"), load("results/data_b/main.npz")
    src_X = np.vstack([A.X, B.X]); src_Y = np.vstack([A.Y, B.Y])
    src_g = np.concatenate([A.meta["building_id"].to_numpy(), B.meta["building_id"].to_numpy() + 100000])
    ids = np.unique(D.meta["building_id"]); rng = np.random.default_rng(0); rng.shuffle(ids)
    test_ids, pool = ids[:70], ids[70:]
    te = D.meta["building_id"].isin(test_ids).to_numpy()
    Dt = D.subset(te)
    res["few_shot"] = {"n_test_buildings": 70, "repeat": 5, "draws": 3, "curve": {}}
    ks = [int(v) for v in os.environ.get("DTD_KS", "0,5,10,20,40").split(",")]   # DTD_KS narrows the curve (a recorded deviation)
    res["few_shot"]["k_values_planned"] = ks
    for k in ks:
        runs = []
        for rep in range(1 if k == 0 else 3):
            pick = np.random.default_rng(100 + rep).permutation(pool)[:k]
            tr = D.meta["building_id"].isin(pick).to_numpy()
            X = [src_X] + [D.X[tr]] * (5 if k else 0)
            Y = [src_Y] + [D.Y[tr]] * (5 if k else 0)
            g = [src_g] + [D.meta["building_id"].to_numpy()[tr] + 1000000] * (5 if k else 0)
            c = Clf().fit(np.vstack(X), np.vstack(Y), np.concatenate(g))
            runs.append(summary(Dt, c.predict(Dt.X), boot=False))
        r = {"macro_auroc": float(np.mean([x["macro_auroc"] for x in runs])), "sd_macro": float(np.std([x["macro_auroc"] for x in runs])),
             "healthy_false_alarm": float(np.mean([x["healthy_false_alarm"] for x in runs])),
             "per_cause": {cc: float(np.mean([x["per_cause"][cc] for x in runs])) for cc in CAUSES}}
        res["few_shot"]["curve"][str(k)] = r
        log("few shot k", k, r)
        save()

if MODE in ("temporal", "all"):
    # B here is the pool regenerated with the temporal block (seed 11, results/data_b_t): the committed B pool has no temporal block and
    # its seed was not recorded. Both arms of every comparison use the same rows, so the comparison is fair.
    W = {"A": load("results/data/main.npz"), "B": load("results/data_b_t/main.npz"), "D": D}
    for w, d in W.items():
        assert d.T is not None, f"{w} has no temporal block; regenerate with --temporal"
    off = {"A": 0, "B": 100000, "D": 200000}
    res["temporal"] = {"in_world": {}, "leave_one_world_out": {}, "B_pool": "results/data_b_t (seed 11)"}
    in_worlds = os.environ.get("DTD_TEMPORAL_INWORLD", "A,B,D").split(",")   # narrowing is a recorded deviation
    res["temporal"]["in_world_run_for"] = in_worlds
    for test in ("D", "B", "A"):
        train = [w for w in W if w != test]
        Y = np.vstack([W[w].Y for w in train]); g = np.concatenate([W[w].meta["building_id"].to_numpy() + off[w] for w in train])
        r = {"train": train}
        for tag, f in (("base", lambda d: d.X), ("with_temporal", lambda d: np.hstack([d.X, d.T]))):
            c = Clf().fit(np.vstack([f(W[w]) for w in train]), Y, g)
            r[tag] = summary(W[test], c.predict(f(W[test])), boot=False)
        r["delta_per_cause"] = {c: r["with_temporal"]["per_cause"][c] - r["base"]["per_cause"][c] for c in CAUSES}
        res["temporal"]["leave_one_world_out"]["to_" + test] = r
        log("temporal LOWO to", test, r["delta_per_cause"])
        save()
    for w, d in ((w, W[w]) for w in in_worlds if w):
        g = d.meta["building_id"].to_numpy()
        r = {}
        for tag, X in (("base", d.X), ("with_temporal", np.hstack([d.X, d.T]))):
            pred = Prediction(np.zeros_like(d.Y), np.zeros_like(d.G), np.zeros(len(d.Y)))
            for tr, te in GroupKFold(5).split(X, d.Y, g):
                p = Clf().fit(X[tr], d.Y[tr], g[tr]).predict(X[te])
                pred.prob[te], pred.p_any[te] = p.prob, p.p_any
            r[tag] = summary(d, pred, boot=False)
        r["delta_per_cause"] = {c: r["with_temporal"]["per_cause"][c] - r["base"]["per_cause"][c] for c in CAUSES}
        res["temporal"]["in_world"][w] = r
        log("temporal in world", w, r["delta_per_cause"])
        save()
    lo = res["temporal"]["leave_one_world_out"]
    passes_a = any(v["delta_per_cause"]["overflow"] >= 0.02 for v in lo.values())
    passes_b = all(v["delta_per_cause"][c] >= -0.01 for v in lo.values() for c in CAUSES if c != "overflow")
    res["temporal"]["shipping_rule"] = {"a_overflow_gain_0.02_somewhere": bool(passes_a), "b_no_other_cause_drop_over_0.01": bool(passes_b),
                                        "ship": bool(passes_a and passes_b)}
    log("shipping rule", res["temporal"]["shipping_rule"])
    save()
log("done")
