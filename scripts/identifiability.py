"""How separable are the causes in the feature space? Nearest-neighbour test on windows with exactly one cause present.

For each such window, find its nearest neighbour (standardised features) among single-cause windows of OTHER buildings and
record whether that neighbour has a different cause. A high cross-cause rate means meter data alone cannot tell the two causes apart.
Also reports how often the shipped model's guard fires on the stress sets. Writes results/identifiability.json.
"""
import json, os, sys
import numpy as np
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
from sklearn.neighbors import NearestNeighbors
from deltat_doctor import CAUSES
from deltat_doctor.diagnose import load_default_model
from deltat_doctor.sim.dataset import Dataset

def single(ds):
    sel = ds.Y.sum(1) == 1
    return ds.X[sel], ds.Y[sel].argmax(1), ds.meta["building_id"].to_numpy()[sel]

def nn_confusion(Xa, ya, ga, Xb=None, yb=None, gb=None):
    mu, sd = Xa.mean(0), Xa.std(0) + 1e-9
    A = (Xa - mu) / sd
    B = A if Xb is None else (Xb - mu) / sd
    yq, gq = (ya, ga) if Xb is None else (yb, gb)
    nn = NearestNeighbors(n_neighbors=12).fit(A)
    _, idx = nn.kneighbors(B)
    M = np.zeros((4, 4)); n = np.zeros(4)
    for i in range(len(B)):
        for j in idx[i]:
            if Xb is None and ga[j] == gq[i]:
                continue
            M[yq[i], ya[j]] += 1
            break
    n = M.sum(1)
    return (M / np.maximum(n[:, None], 1)).round(3).tolist(), n.astype(int).tolist()

A = Dataset.load("results/data/main.npz"); B = Dataset.load("results/data_b/main.npz")
XA, yA, gA = single(A); XB, yB, gB = single(B)
res = {"causes": list(CAUSES)}
res["within_A"], res["n_A"] = nn_confusion(XA, yA, gA)
res["within_B"], res["n_B"] = nn_confusion(XB, yB, gB)
res["B_query_A_reference"], _ = nn_confusion(XA, yA, gA, XB, yB, gB)
m = load_default_model()
res["guard_fire_rate"] = {}
for name in ("fresh", "noise_x3", "climate_p3", "climate_m3", "severity_x15", "no_outdoor"):
    d = Dataset.load(f"results/data/stress_{name}.npz")
    res["guard_fire_rate"][name] = float((m.ood_count(d.X) > m.ood_threshold).mean())
res["guard_threshold"] = int(m.ood_threshold)
json.dump(res, open("results/identifiability.json", "w"), indent=2)
for k in ("within_A", "within_B", "B_query_A_reference"):
    print(k); [print(" ", c, r) for c, r in zip(CAUSES, res[k])]
print(res["guard_fire_rate"], res["guard_threshold"])
