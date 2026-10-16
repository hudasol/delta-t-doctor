"""Fleet calibration check in simulation: the shipped model, calibrated on a pretend fleet from world D (a physics it was not trained on).

usage: python scripts/calibrate_check.py [--buildings 40] [--weak 15]

Builds world D buildings (two consecutive months each, fixed seed 77) as meter export files with a manifest whose labels come from the
simulator's own counterfactual ground truth, then runs `calibrate` with the bundled base model and base rows: once with all buildings and
once with a weak subset. Writes results/calibrate_check.json (the two model cards without the per file hashes). Simulation only; this
says nothing about real fleets.
"""
import argparse, json, os, sys, tempfile
import numpy as np
import pandas as pd

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))
from joblib import Parallel, delayed
from deltat_doctor import CAUSES
from deltat_doctor.calibrate import calibrate
from deltat_doctor.sim.scenarios import draw_cause_set
from deltat_doctor.sim.world_d import make_sample_d, sample_building_d


def one_building(seed, b, months):
    rng = np.random.default_rng(seed)
    cfg = sample_building_d(rng, b)
    causes = draw_cause_set(rng)
    frames, present = [], set()
    for m in months:
        s = make_sample_d(rng, b, cfg=cfg, causes=causes, month=m)
        frames.append(s.frame)
        present |= {c for c in CAUSES if s.present[c]}
    return b, pd.concat(frames, ignore_index=True), sorted(present)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--buildings", type=int, default=40)
    ap.add_argument("--weak", type=int, default=15)
    ap.add_argument("--jobs", type=int, default=int(os.environ.get("DTD_JOBS", "6")))
    a = ap.parse_args()
    master = np.random.default_rng(77)
    seeds = [int(master.integers(0, 2**31 - 1)) for _ in range(a.buildings)]
    months = [(int(m), int(m) + 1) for m in master.integers(1, 12, a.buildings)]
    built = Parallel(n_jobs=a.jobs)(delayed(one_building)(seeds[b], b, months[b]) for b in range(a.buildings))
    out = {"note": "Simulation only: world D buildings as a pretend fleet; the shipped model never saw world D.", "runs": {}}
    with tempfile.TemporaryDirectory() as d:
        rows = []
        for b, frame, present in built:
            frame.to_csv(os.path.join(d, f"d{b:03d}.csv"), index=False)
            rows.append({"building_id": f"D{b:03d}", "file": f"d{b:03d}.csv", "causes": ";".join(present) or "none", "complete": "yes"})
        for tag, n in (("full", a.buildings), ("weak", a.weak)):
            man = os.path.join(d, f"manifest_{tag}.csv")
            pd.DataFrame(rows[:n]).to_csv(man, index=False)
            card = calibrate(man, os.path.join(d, f"{tag}.joblib"))
            card = {k: v for k, v in card.items() if k not in ("fit_buildings", "holdout_buildings")}
            out["runs"][tag] = card
            h = card["holdout"]
            print(tag, n, "macro", h["base"]["macro_auroc"], "->", h["calibrated"]["macro_auroc"],
                  "top2", h["base"]["top2_agreement"], "->", h["calibrated"]["top2_agreement"], flush=True)
    out["label_prevalence"] = {c: float(np.mean([c in p for _, _, p in built])) for c in CAUSES}
    json.dump(out, open("results/calibrate_check.json", "w"), indent=2, default=float)


if __name__ == "__main__":
    main()
