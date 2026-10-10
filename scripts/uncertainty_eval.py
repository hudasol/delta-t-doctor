"""Do the 10-90 intervals for delta-T gain and AED saving cover what they claim to? Out-of-fold, buildings held out.

Writes results/uncertainty.json. Margin calibration (conformalised quantile regression) uses the other folds' scores.
"""
import json, os, sys
import numpy as np
from sklearn.model_selection import GroupKFold
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
from deltat_doctor import CAUSES
from deltat_doctor.evaluate import MODELS, cross_validate
from deltat_doctor.penalty import ContractTerms, saving_from_gain
from deltat_doctor.sim.dataset import Dataset

ds = Dataset.load("results/data/main.npz")
cv = cross_validate(ds, 5, models={"ours": MODELS["ours_gbdt"]})
P = cv["ours"][1]
Q = P.gain_q
groups = ds.meta["building_id"].to_numpy()
terms = ContractTerms()
res = {"nominal": 0.8, "per_cause": {}, "saving": {}}
cal = Q.copy()
for tr, te in GroupKFold(5).split(ds.X, ds.Y, groups):
    for k in range(4):
        act_tr = Q[tr, k, -1] >= 0.2
        act_te = Q[te, k, -1] >= 0.2
        sc = np.maximum(Q[tr, k, 0] - ds.G[tr, k], ds.G[tr, k] - Q[tr, k, -1])
        m = {}
        for name, sel in (("a", act_tr), ("i", ~act_tr)):
            s_ = sc[sel]
            lvl = min(1.0, np.ceil((len(s_) + 1) * 0.8) / len(s_))
            m[name] = max(np.quantile(s_, lvl), 0.0)
        mm = np.where(act_te, m["a"], m["i"])
        cal[te, k, 0] = np.clip(Q[te, k, 0] - mm, 0, None)
        cal[te, k, -1] = Q[te, k, -1] + mm
for k, c in enumerate(CAUSES):
    g = ds.G[:, k]
    raw = float(((g >= Q[:, k, 0]) & (g <= Q[:, k, -1])).mean())
    adj = float(((g >= cal[:, k, 0]) & (g <= cal[:, k, -1])).mean())
    pres = ds.Y[:, k] == 1
    adj_p = float(((g >= cal[:, k, 0]) & (g <= cal[:, k, -1]))[pres].mean())
    act = Q[:, k, -1] >= 0.2
    res["per_cause"][c] = {"coverage_active_calibrated": float(((g >= cal[:, k, 0]) & (g <= cal[:, k, -1]))[act].mean()),
                           "coverage_active_raw": float(((g >= Q[:, k, 0]) & (g <= Q[:, k, -1]))[act].mean()), "n_active": int(act.sum()),
                           "coverage_raw": raw, "coverage_calibrated": adj, "coverage_calibrated_when_present": adj_p,
                           "median_width_c": float(np.median(cal[:, k, -1] - cal[:, k, 0]))}
# saving coverage on the first-fix quantity per window: true saving from the true gain, interval from quantiles
dt = ds.meta["dt_actual"].to_numpy()
for k, c in enumerate(CAUSES):
    true = np.array([saving_from_gain(dt[i], ds.G[i, k], 1.0, terms) for i in range(len(dt))])
    lo = np.array([saving_from_gain(dt[i], cal[i, k, 0], 1.0, terms) for i in range(len(dt))])
    hi = np.array([saving_from_gain(dt[i], cal[i, k, -1], 1.0, terms) for i in range(len(dt))])
    inside = (true >= lo - 1e-12) & (true <= hi + 1e-12)
    res["saving"][c] = {"coverage": float(inside.mean())}
json.dump(res, open("results/uncertainty.json", "w"), indent=2)
print(json.dumps(res, indent=1))
