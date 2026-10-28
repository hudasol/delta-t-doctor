"""Generate the main training pool and the stress-test sets (deterministic seeds)."""
import argparse, os, sys, time
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
from deltat_doctor.sim.dataset import generate

STRESS = {
    "fresh":        dict(),
    "noise_x3":     dict(flow_noise=0.045, temp_noise=0.30),
    "res_2h":       dict(post="2h"),
    "climate_p3":   dict(climate_shift=3.0),
    "climate_m3":   dict(climate_shift=-3.0),
    "severity_x05": dict(severity_scale=0.5),
    "severity_x15": dict(severity_scale=1.5),
    "no_outdoor":   dict(post="no_oat"),
    "window_21d":   dict(days=21),
    "energy_only":  dict(post="energy_only"),
}

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="results/data")
    ap.add_argument("--buildings", type=int, default=500)
    ap.add_argument("--per", type=int, default=10)
    ap.add_argument("--stress-buildings", type=int, default=80)
    ap.add_argument("--stress-per", type=int, default=6)
    ap.add_argument("--jobs", type=int, default=2)
    ap.add_argument("--sim", default="A", choices=["A", "B", "CA", "CB", "D"],
                    help="B = structurally different hydraulic simulator; D = dynamic world (docs/research/WORLD_D.md); stress sets are made for A only")
    ap.add_argument("--temporal", action="store_true", help="also store the optional temporal feature block (docs/research/WORLD_D.md)")
    ap.add_argument("--no-stress", action="store_true", help="skip the stress sets")
    ap.add_argument("--seed", type=int, default=11)
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)
    t = time.time()
    ds = generate(a.buildings, a.per, seed=a.seed, n_jobs=a.jobs, sim=a.sim, temporal=a.temporal)
    ds.save(os.path.join(a.out, "main.npz"))
    print(f"main {len(ds.X)} samples in {time.time()-t:.0f}s", flush=True)
    for i, (name, kw) in enumerate(STRESS.items() if a.sim == "A" and not a.no_stress else []):
        t = time.time()
        d = generate(a.stress_buildings, a.stress_per, seed=1000 + i, n_jobs=a.jobs, **kw)
        d.save(os.path.join(a.out, f"stress_{name}.npz"))
        print(f"stress_{name} {len(d.X)} in {time.time()-t:.0f}s", flush=True)
    print("DONE", flush=True)
