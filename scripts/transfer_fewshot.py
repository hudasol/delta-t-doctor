"""Few-shot adaptation curve. Predictions: docs/research/TRANSFER_V2.md. Writes results/transfer_fewshot.json."""
import json, os, sys, time
import numpy as np
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
from deltat_doctor import CAUSES
from deltat_doctor.evaluate import metrics
from deltat_doctor.models import Diagnoser
from deltat_doctor.sim.dataset import Dataset

D = {"A": Dataset.load("results/data/main.npz"), "B": Dataset.load("results/data_b/main.npz")}
REP = 5
out = {}
t0 = time.time()
for src, tgt, ks, n_test in (("A", "B", [0, 5, 10, 20, 40, 70], 70), ("B", "A", [0, 5, 10, 20, 50, 100, 200], 150)):
    S, T = D[src], D[tgt]
    ids = np.unique(T.meta["building_id"]); rng = np.random.default_rng(0); rng.shuffle(ids)
    test_ids, pool = ids[:n_test], ids[n_test:]
    te = T.meta["building_id"].isin(test_ids).to_numpy()
    Tt = T.subset(te)
    res = {}
    for k in ks:
        runs = []
        for rep in range(1 if k == 0 else 3):
            pick = np.random.default_rng(100 + rep).permutation(pool)[:k]
            tr = T.meta["building_id"].isin(pick).to_numpy()
            X = [S.X]; Y = [S.Y]; G = [S.G]; g = [S.meta["building_id"].to_numpy()]
            for r in range(REP if k else 0):
                X.append(T.X[tr]); Y.append(T.Y[tr]); G.append(T.G[tr]); g.append(T.meta["building_id"].to_numpy()[tr] + 1000000)
            m = Diagnoser(seed=0).fit(np.vstack(X), np.vstack(Y), np.vstack(G), groups=np.concatenate(g))
            p = m.predict(Tt.X); r = metrics(Tt, p)
            h = Tt.Y.sum(1) == 0
            runs.append({"macro": r["macro_auroc"], "any": r["any_fault_auroc"], "healthy_fa": float((p.p_any[h] >= 0.5).mean()),
                         **{c: r["per_cause"][c]["auroc"] for c in CAUSES}})
        res[k] = {kk: float(np.mean([x[kk] for x in runs])) for kk in runs[0]} | {"sd_macro": float(np.std([x["macro"] for x in runs]))}
        print(src, "->", tgt, "k", k, {a: round(b, 3) for a, b in res[k].items()}, f"{time.time()-t0:.0f}s", flush=True)
        out[f"{src}_to_{tgt}"] = res
        json.dump(out, open("results/transfer_fewshot.json", "w"), indent=2)
