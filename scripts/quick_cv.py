import sys, os, json, time
sys.path.insert(0, "src")
from deltat_doctor.sim.dataset import Dataset
from deltat_doctor.evaluate import cross_validate
ds = Dataset.load("results/data/main.npz")
print("n", len(ds.X), "prev", ds.Y.mean(0).round(3), flush=True)
t = time.time()
res = cross_validate(ds, 5)
print("cv time", round(time.time()-t))
for name,(m,_) in res.items():
    print(name, {k: (round(v,3) if isinstance(v,float) else v) for k,v in m.items() if k not in ("per_cause","prevalence","n")})
    print("   per-cause auroc", {c: round(v["auroc"],3) for c,v in m["per_cause"].items()}, "gainMAE", {c: round(v["gain_mae_c"],2) for c,v in m["per_cause"].items()})
