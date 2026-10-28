"""Baseline suite. Protocol and predictions: docs/research/BASELINES.md. Writes results/baselines.json.

Inside simulators A, B and D: building grouped 5 fold CV, identical folds for every model.
Zero shot: A to B, B to A, A+B to D.
"""
import json
import os
import sys
import time

import numpy as np
import pandas as pd
from sklearn.model_selection import GroupKFold

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
from deltat_doctor.baselines import BASELINES, FittedStumps  # noqa: E402
from deltat_doctor.evaluate import bootstrap_ci, summary_row  # noqa: E402
from deltat_doctor.models import Diagnoser, Prediction  # noqa: E402
from deltat_doctor.sim.dataset import Dataset  # noqa: E402

WORLDS = {"A": "results/data/main.npz", "B": "results/data_b/main.npz", "D": "results/data_d/main.npz"}
OUT = "results/baselines.json"
REF = "shipped"


def make(name):
    return (lambda: Diagnoser(seed=0)) if name == REF else (lambda: BASELINES[name]())


def fit_predict(name, train, groups, X_test):
    m = make(name)()
    if name == REF:
        m.fit(train.X, train.Y, train.G, groups=groups)
    else:
        m.fit(train.X, train.Y, train.G)
    return m, m.predict(X_test)


def empty_pred(ds):
    return Prediction(np.zeros_like(ds.Y, dtype=float), np.zeros_like(ds.G, dtype=float), np.zeros(len(ds.Y)))


def evaluate(ds, preds, label):
    ci = bootstrap_ci(ds, preds, n_boot=200, ref=REF)
    rows = {}
    for name, p in preds.items():
        r = summary_row(ds, p)
        r["macro_auroc_ci95"] = ci["models"][name]["macro_auroc"]["ci95"]
        if name != REF:
            r["lead_of_shipped_macro_auroc"] = ci["paired_vs_" + REF][name]["macro_auroc"]["diff_mean"]
            r["lead_ci95"] = ci["paired_vs_" + REF][name]["macro_auroc"]["diff_ci95"]
        rows[name] = r
    print(label, {n: round(r["macro_auroc"], 3) for n, r in rows.items()}, flush=True)
    return rows


def main():
    data = {w: Dataset.load(p) for w, p in WORLDS.items()}
    names = list(BASELINES) + [REF]
    res = {"models": names, "in_world": {}, "zero_shot": {}}
    t0 = time.time()
    for w, ds in data.items():
        groups = ds.meta["building_id"].to_numpy()
        preds = {n: empty_pred(ds) for n in names}
        for tr, te in GroupKFold(5).split(ds.X, groups=groups):
            sub = Dataset(ds.X[tr], ds.Y[tr], ds.G[tr], ds.meta.iloc[tr].reset_index(drop=True))
            for n in names:
                _, p = fit_predict(n, sub, groups[tr], ds.X[te])
                preds[n].prob[te], preds[n].gain[te], preds[n].p_any[te] = p.prob, p.gain, p.p_any
        res["in_world"][w] = evaluate(ds, preds, f"in world {w}")
        res["in_world"][w]["_n_windows"] = int(len(ds.X))
        print(f"  {time.time() - t0:.0f}s", flush=True)
        json.dump(res, open(OUT, "w"), indent=2)

    def pooled(keys):
        parts = [data[k] for k in keys]
        meta = pd.concat([d.meta.assign(building_id=d.meta["building_id"] + 100000 * i) for i, d in enumerate(parts)], ignore_index=True)
        return Dataset(np.vstack([d.X for d in parts]), np.vstack([d.Y for d in parts]), np.vstack([d.G for d in parts]), meta)

    for label, train_keys, test_key in (("A_to_B", ["A"], "B"), ("B_to_A", ["B"], "A"), ("AB_to_D", ["A", "B"], "D")):
        train, test = pooled(train_keys), data[test_key]
        gtr = train.meta["building_id"].to_numpy()
        preds = {n: fit_predict(n, train, gtr, test.X)[1] for n in names}
        res["zero_shot"][label] = evaluate(test, preds, label)
        print(f"  {time.time() - t0:.0f}s", flush=True)
        json.dump(res, open(OUT, "w"), indent=2)

    # the fitted stump rules, written out for the docs
    full = pooled(["A"])
    res["stump_rules_fit_on_A"] = FittedStumps().fit(full.X, full.Y, full.G).describe()
    json.dump(res, open(OUT, "w"), indent=2)


if __name__ == "__main__":
    main()
