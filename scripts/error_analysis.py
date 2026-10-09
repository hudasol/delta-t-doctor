"""Where does the model fail, and why? Out-of-fold error analysis on the simulated pool.

Writes results/error_analysis.json and results/error_analysis.md. Slices: design delta-T band, building type,
number of air handlers, number of injected causes, true gain size, season. Also calibration error (ECE) and how much
of the apparent error is label-threshold ambiguity (true gain within 0.1 C of the 0.20 C "present" cutoff).
"""
import json, os, sys
import numpy as np
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
from deltat_doctor import CAUSES
from deltat_doctor.evaluate import MODELS, cross_validate
from deltat_doctor.sim.dataset import Dataset
from sklearn.metrics import roc_auc_score

ds = Dataset.load("results/data/main.npz")
cv = cross_validate(ds, 5, models={"ours": MODELS["ours_gbdt"]})
pred = cv["ours"][1]
Y, G, P, meta = ds.Y.astype(int), ds.G, pred.prob, ds.meta
out = {}

def ece(y, p, bins=10):
    idx = np.minimum((p * bins).astype(int), bins - 1); e = 0.0
    for b in range(bins):
        s = idx == b
        if s.any(): e += s.mean() * abs(p[s].mean() - y[s].mean())
    return float(e)

def auc(y, p):
    return float(roc_auc_score(y, p)) if 0 < y.sum() < len(y) else float("nan")

out["ece"] = {c: ece(Y[:, k], P[:, k]) for k, c in enumerate(CAUSES)}

def slice_report(name, labels):
    res = {}
    for v in sorted(set(labels)):
        m = labels == v
        if m.sum() < 80: continue
        res[str(v)] = {"n": int(m.sum()),
                       "macro_auroc": float(np.nanmean([auc(Y[m, k], P[m, k]) for k in range(4)])),
                       "per_cause_auroc": {c: auc(Y[m, k], P[m, k]) for k, c in enumerate(CAUSES)},
                       "error_rate_at_0.5": float(((P[m] >= .5).astype(int) != Y[m]).mean())}
    out[name] = res

slice_report("by_design_band", np.digitize(meta.design_dt, [7, 9, 11]).astype(int))
slice_report("by_building_type", meta.building_type.to_numpy())
slice_report("by_n_ahu", np.digitize(meta.n_ahu, [10, 16, 22]).astype(int))
slice_report("by_n_causes", Y.sum(1))
slice_report("by_season", np.digitize(meta.month, [3, 6, 9, 12]).astype(int) % 4)

# error vs size of the true gain (per cause, present only)
bins = [0.2, 0.4, 0.8, 1.6, 99]
out["recall_by_true_gain"] = {}
for k, c in enumerate(CAUSES):
    r = {}
    for lo, hi in zip(bins[:-1], bins[1:]):
        m = (Y[:, k] == 1) & (G[:, k] >= lo) & (G[:, k] < hi)
        if m.sum() >= 20: r[f"{lo}-{hi if hi < 99 else 'inf'}"] = {"n": int(m.sum()), "recall_at_0.5": float((P[m, k] >= .5).mean())}
    out["recall_by_true_gain"][c] = r

# label-threshold ambiguity: injected cause whose gain is within 0.1 of the cutoff
out["borderline_labels"] = {}
for k, c in enumerate(CAUSES):
    inj = np.array([c in str(i).split("+") for i in meta.injected])
    border = inj & (np.abs(G[:, k] - 0.2) < 0.1)
    err = ((P[:, k] >= .5).astype(int) != Y[:, k])
    out["borderline_labels"][c] = {"borderline_share_of_errors": float((err & border).sum() / max(err.sum(), 1)),
                                    "n_errors": int(err.sum()), "n_borderline": int(border.sum())}

# confusion between the two flow-at-low-load faults
both = (Y[:, 1] + Y[:, 2]) == 1
pv, cf = Y[:, 1] == 1, Y[:, 2] == 1
out["valve_confusion"] = {
    "passing_true_called_constant": float(((P[:, 2] >= .5) & pv & ~cf).sum() / max((pv & ~cf).sum(), 1)),
    "constant_true_called_passing": float(((P[:, 1] >= .5) & cf & ~pv).sum() / max((cf & ~pv).sum(), 1)),
}
# false alarms on healthy buildings
h = Y.sum(1) == 0
out["healthy"] = {"n": int(h.sum()), "mean_p_any": float(pred.p_any[h].mean()),
                  "false_alarm_rate_at_0.5": float((pred.p_any[h] >= .5).mean())}
# multi-cause degradation: exact match by number of causes
out["exact_match_by_n_causes"] = {int(n): float((((P[Y.sum(1) == n] >= .5).astype(int) == Y[Y.sum(1) == n]).all(1)).mean())
                                  for n in range(4) if (Y.sum(1) == n).sum() > 20}
json.dump(out, open("results/error_analysis.json", "w"), indent=2)
print(json.dumps({k: out[k] for k in ("ece", "healthy", "valve_confusion", "borderline_labels", "exact_match_by_n_causes")}, indent=1))
for k in ("by_design_band", "by_building_type", "by_n_ahu", "by_n_causes", "by_season"):
    print(k, {a: (b["n"], round(b["macro_auroc"], 3)) for a, b in out[k].items()})
print("recall by gain", json.dumps(out["recall_by_true_gain"]))
