"""Cross-simulator generalisation: train on one simulator, test on the other. Predictions: docs/research/CROSS_SIMULATOR.md.

Writes results/cross_simulator.json and results/cross_simulator.md.
"""
import json, os, sys
import numpy as np
import pandas as pd
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
from deltat_doctor import CAUSES
from deltat_doctor.evaluate import MODELS, bootstrap_ci, cross_validate, metrics
from deltat_doctor.models import Diagnoser, LogisticBaseline, Prediction
from deltat_doctor.sim.dataset import Dataset

A = Dataset.load("results/data/main.npz")
B = Dataset.load("results/data_b/main.npz")
gA, gB = A.meta["building_id"].to_numpy(), B.meta["building_id"].to_numpy()

def slim(m):
    return {"n": m["n"], "macro_auroc": m["macro_auroc"], "any_fault_auroc": m["any_fault_auroc"], "macro_f1": m["macro_f1"],
            "per_cause_auroc": {c: m["per_cause"][c]["auroc"] for c in CAUSES},
            "per_cause_brier": {c: m["per_cause"][c]["brier"] for c in CAUSES},
            "prevalence": m["prevalence"], "top1_fix_gain_captured_blind": m.get("top1_fix_gain_captured_blind")}

def ece(ds, pred, bins=10):
    p, y = pred.prob.ravel(), ds.Y.ravel()
    idx = np.minimum((p * bins).astype(int), bins - 1)
    return float(sum(abs(p[idx == b].mean() - y[idx == b].mean()) * (idx == b).sum() for b in range(bins) if (idx == b).any()) / len(p))

def transfer(train, gtrain, test, tag, with_logistic=True):
    m = Diagnoser(seed=0).fit(train.X, train.Y, train.G, groups=gtrain)
    p = m.predict(test.X)
    out = {"model": slim(metrics(test, p)), "ece": ece(test, p)}
    out["ci"] = bootstrap_ci(test, {tag: p}, n_boot=200)["models"][tag]
    ood = m.ood_count(test.X)
    out["ood_fire_rate"] = float((ood > m.ood_threshold).mean())
    healthy = test.Y.sum(1) == 0
    out["healthy_false_alarm_rate"] = float((p.p_any[healthy] >= 0.5).mean())
    out["healthy_n"] = int(healthy.sum())
    if with_logistic:
        lg = LogisticBaseline().fit(train.X, train.Y, train.G)
        out["logistic"] = slim(metrics(test, lg.predict(test.X)))
    return out

res = {"n_A": len(A.X), "n_B": len(B.X), "buildings_A": int(A.meta.building_id.nunique()), "buildings_B": int(B.meta.building_id.nunique())}
res["prevalence_A"] = {c: float(A.Y[:, k].mean()) for k, c in enumerate(CAUSES)}
res["prevalence_B"] = {c: float(B.Y[:, k].mean()) for k, c in enumerate(CAUSES)}
cvA = cross_validate(A, 5, models={"m": MODELS["ours_gbdt"]})["m"][0]
cvB = cross_validate(B, 5, models={"m": MODELS["ours_gbdt"]})["m"][0]
res["within_A"], res["within_B"] = slim(cvA), slim(cvB)
print("within done", flush=True)
res["A_to_B"] = transfer(A, gA, B, "A_to_B")
print("A->B", res["A_to_B"]["model"]["macro_auroc"], flush=True)
res["B_to_A"] = transfer(B, gB, A, "B_to_A")
print("B->A", res["B_to_A"]["model"]["macro_auroc"], flush=True)
# pooled: grouped CV over both, scored per domain
gP = np.concatenate([gA, gB + 100000])
P = Dataset(np.vstack([A.X, B.X]), np.vstack([A.Y, B.Y]), np.vstack([A.G, B.G]),
            pd.concat([A.meta.assign(building_id=gA), B.meta.assign(building_id=gB + 100000)], ignore_index=True))
cvP = cross_validate(P, 5, models={"m": MODELS["ours_gbdt"]})["m"][1]
isA = np.arange(len(P.X)) < len(A.X)
for tag, sel in (("A", isA), ("B", ~isA)):
    sub = P.subset(sel)
    res[f"pooled_on_{tag}"] = slim(metrics(sub, Prediction(cvP.prob[sel], cvP.gain[sel], cvP.p_any[sel])))
json.dump(res, open("results/cross_simulator.json", "w"), indent=2)

def row(name, d):
    m = d["model"] if "model" in d else d
    pc = m["per_cause_auroc"]
    return f"| {name} | {m['macro_auroc']:.3f} | {m['any_fault_auroc']:.3f} | " + " | ".join(f"{pc[c]:.3f}" for c in CAUSES) + " |"
md = ["# Cross-simulator results\n", "Simulator A: 5000 windows. Simulator B: structurally different (see docs/research/CROSS_SIMULATOR.md).\n",
      "| setting | macro AUROC | any-fault AUROC | " + " | ".join(CAUSES) + " |", "|---|---|---|" + "---|" * len(CAUSES),
      row("within A (grouped CV)", res["within_A"]), row("within B (grouped CV)", res["within_B"]),
      row("train A, test B", res["A_to_B"]), row("train B, test A", res["B_to_A"]),
      row("train A+B, test A (grouped CV)", res["pooled_on_A"]), row("train A+B, test B (grouped CV)", res["pooled_on_B"]),
      "", "| transfer | macro AUROC 95% CI | ECE | out-of-range windows | healthy false alarms (p>=0.5) | logistic macro AUROC |", "|---|---|---|---|---|---|"]
for k in ("A_to_B", "B_to_A"):
    d = res[k]; ci = d["ci"]["macro_auroc"]["ci95"]
    md.append(f"| {k.replace('_to_', ' to ')} | {d['model']['macro_auroc']:.3f} [{ci[0]:.3f}, {ci[1]:.3f}] | {d['ece']:.3f} | {d['ood_fire_rate']:.0%} | {d['healthy_false_alarm_rate']:.0%} (n={d['healthy_n']}) | {d['logistic']['macro_auroc']:.3f} |")
md += ["", "Prevalence of each cause (share of windows with the cause present):", "", "| | " + " | ".join(CAUSES) + " |", "|---|" + "---|" * len(CAUSES),
       "| A | " + " | ".join(f"{res['prevalence_A'][c]:.2f}" for c in CAUSES) + " |", "| B | " + " | ".join(f"{res['prevalence_B'][c]:.2f}" for c in CAUSES) + " |"]
open("results/cross_simulator.md", "w").write("\n".join(md) + "\n")
print("\n".join(md))
