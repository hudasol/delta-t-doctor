"""Feature-group ablation and a single-feature baseline (grouped CV by building). Writes results/ablation.json."""
import json, os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
from deltat_doctor.evaluate import MODELS, cross_validate
from deltat_doctor.features import FEATURE_NAMES
from deltat_doctor.sim.dataset import Dataset

ds = Dataset.load("results/data/main.npz")
names = FEATURE_NAMES
groups = {
    "dt_shape": [i for i, n in enumerate(names) if n.startswith("dt_") or n in ("zero_flow_frac",)],
    "flow_shape": [i for i, n in enumerate(names) if n.startswith("flow_")],
    "load_dist": [i for i, n in enumerate(names) if n.startswith(("frac_bin", "duty", "load_"))],
}
res = {}
def run(tag, cols):
    sub = Dataset(ds.X[:, cols], ds.Y, ds.G, ds.meta)
    cv = cross_validate(sub, 5, models={"m": MODELS["ours_gbdt"]})
    m = cv["m"][0]
    res[tag] = {"n_features": len(cols), "macro_auroc": m["macro_auroc"], "any_fault_auroc": m["any_fault_auroc"],
                "macro_f1": m["macro_f1"], "per_cause_auroc": {c: v["auroc"] for c, v in m["per_cause"].items()}}
    print(tag, res[tag]["macro_auroc"], flush=True)
run("all", list(range(len(names))))
for g, cols in groups.items():
    run(f"only_{g}", cols)
    run(f"without_{g}", [i for i in range(len(names)) if i not in cols])
run("dt_period_only", [names.index("dt_period")])
json.dump(res, open("results/ablation.json", "w"), indent=2)
