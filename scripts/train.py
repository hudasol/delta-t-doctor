"""Train the final Diagnoser (blind and informed) on the pooled simulated data and save it into the package.

usage: python scripts/train.py [data1.npz,data2.npz] [out.joblib]
Default data: simulator A main set plus simulator B main set, when both exist.
"""
import hashlib, json, os, subprocess, sys, time
import numpy as np
import pandas as pd
import sklearn
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
from deltat_doctor import CAUSES, __version__
from deltat_doctor.features import augment
from deltat_doctor.models import Diagnoser
from deltat_doctor.sim.dataset import Dataset

default = "results/data/main.npz" + ("," + "results/data_b/main.npz" if os.path.exists("results/data_b/main.npz") else "")
paths = (sys.argv[1] if len(sys.argv) > 1 else default).split(",")
out = sys.argv[2] if len(sys.argv) > 2 else "src/deltat_doctor/assets/diagnoser.joblib"


def sha(p):
    return hashlib.sha256(open(p, "rb").read()).hexdigest()


parts = [Dataset.load(p) for p in paths]
X = np.vstack([d.X for d in parts])
Y = np.vstack([d.Y for d in parts])
G = np.vstack([d.G for d in parts])
meta = pd.concat([d.meta.assign(building_id=d.meta["building_id"] + 100000 * i, source=os.path.basename(os.path.dirname(p)))
                  for i, (d, p) in enumerate(zip(parts, paths))], ignore_index=True)
bid = meta["building_id"].to_numpy()
dd = meta["design_dt"].to_numpy()
t = time.time()
m = Diagnoser(seed=0).fit(X, Y, G, groups=bid).fit_quantile_margin(X, G, bid)
os.makedirs(os.path.dirname(out), exist_ok=True)
m.save(out)
Xi = augment(X, dd)
mi = Diagnoser(seed=0).fit(Xi, Y, G, groups=bid).fit_quantile_margin(Xi, G, bid)
informed_path = os.path.join(os.path.dirname(out), "diagnoser_informed.joblib")
mi.save(informed_path)
try:
    git = subprocess.run(["git", "rev-parse", "--short", "HEAD"], capture_output=True, text=True).stdout.strip()
except Exception:
    git = ""
card = {
    "version": __version__, "causes": list(CAUSES), "trained_on_samples": int(len(X)), "n_buildings": int(len(np.unique(bid))),
    "prevalence": {c: float(Y[:, k].mean()) for k, c in enumerate(CAUSES)},
    "design_dt_training_range_c": [float(np.percentile(dd, 0.5).round(1)), float(np.percentile(dd, 99.5).round(1))],
    "gain_interval_margin_c": {c: {k: round(v, 3) for k, v in d.items()} for c, d in m.q_margin.items()},
    "modes": ["blind", "informed"],
    "data": "simulated (deltat_doctor.sim, simulators A and B); no field data",
    "training_sets": {os.path.dirname(p).split(os.sep)[-1] + "/" + os.path.basename(p): int(len(d.X)) for p, d in zip(paths, parts)},
    "train_seconds": round(time.time() - t, 1), "git_commit_at_training": git, "sklearn_version": sklearn.__version__,
    "training_data_sha256": {p: sha(p) for p in paths},
    "sha256": {os.path.basename(out): sha(out), "diagnoser_informed.joblib": sha(informed_path)},
}
try:   # worst-world AUROC per cause from the cross-simulator test (used to cap tiers; see docs/CROSS_SIMULATOR.md)
    xs = json.load(open("results/cross_simulator.json"))
    card["worst_world_auroc"] = {c: round(min(xs["A_to_B"]["model"]["per_cause_auroc"][c], xs["B_to_A"]["model"]["per_cause_auroc"][c]), 3)
                                 for c in CAUSES}
except (OSError, KeyError):
    pass
json.dump(card, open(os.path.join(os.path.dirname(out), "model_card.json"), "w"), indent=2)
print("saved", out, json.dumps(card)[:600])
