"""Pilot dry run, end to end, on SYNTHETIC buildings: proves the path from inspected buildings to a calibrated, scored model works before a
partner exists. Nothing produced here is evidence about real buildings.

usage: python scripts/pilot_dry_run.py [--buildings 24] [--months 2] [--world B|D] [--seed 5] [--out results/pilot_dry_run]

Steps:
1. Simulate a small fleet (simulator B by default, which the shipped model has seen; `--world D` uses a physics it has not seen but is slow)
   and write one meter export per building plus a manifest in the format of examples/real_manifest_template.csv. Labels are the simulator's
   counterfactual ground truth, standing in for blind inspections; every building is "complete". File names, building ids and the summary
   all carry the word SYNTHETIC.
2. Run scripts/evaluate_real.py on the whole manifest with the bundled model.
3. Split the buildings in two halves (seeded). Run `deltat-doctor calibrate` on the first half.
4. Run scripts/evaluate_real.py on the second half twice, with the bundled model and with the calibrated one.
5. Write SUMMARY_SYNTHETIC.md (one page) and summary_synthetic.json in the output folder, and print the summary.
"""
import argparse, json, os, subprocess, sys
import numpy as np
import pandas as pd

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
sys.path.insert(0, os.path.join(ROOT, "src"))
from deltat_doctor import CAUSES

FIELDS = ("n_buildings", "abstention_rate", "top1", "top2", "healthy_false_alarm", "confidently_wrong_buildings", "brier", "interpretable")


def build_fleet(out, n, months, world, seed):
    from deltat_doctor.sim.hydraulic import make_sample_b, sample_building_b
    from deltat_doctor.sim.scenarios import draw_cause_set
    from deltat_doctor.sim.world_d import make_sample_d, sample_building_d
    make, sample = {"B": (make_sample_b, sample_building_b), "D": (make_sample_d, sample_building_d)}[world]
    rng = np.random.default_rng(seed)
    rows = []
    for b in range(n):
        cfg = sample(rng, b)
        causes = draw_cause_set(rng)
        start = int(rng.integers(1, 13 - months))
        frames, present = [], set()
        for m in range(start, start + months):
            s = make(rng, b, cfg=cfg, causes=causes, month=m)
            frames.append(s.frame)
            present |= {c for c in CAUSES if s.present[c]}
        name = f"SYNTHETIC_{world}{b:03d}.csv"
        pd.concat(frames, ignore_index=True).to_csv(os.path.join(out, name), index=False)
        rows.append({"building_id": f"SYN-{world}{b:03d}", "file": name, "causes": ";".join(sorted(present)) or "none",
                     "complete": "yes", "design_dt": "", "min_dt": "8.9"})
    return pd.DataFrame(rows)


def run(cmd):
    r = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError(f"{' '.join(cmd[:3])} failed:\n{r.stdout[-1500:]}\n{r.stderr[-1500:]}")
    return r.stdout


def evaluate(manifest, out, model=None, boot=200):
    cmd = [sys.executable, os.path.join(ROOT, "scripts", "evaluate_real.py"), manifest, "--out", out, "--boot", str(boot)]
    if model:
        cmd += ["--model", model]
    run(cmd)
    path = os.path.join(out, "real_eval.json")
    full = json.load(open(path))
    # evaluate_real.py names its output "real_eval.json"; here it is not real, so the file is marked and renamed
    full = {"SYNTHETIC": True, "note": "Produced by scripts/pilot_dry_run.py from simulated buildings; not real data."} | full
    json.dump(full, open(os.path.join(out, "SYNTHETIC_eval.json"), "w"), indent=2, default=float)
    os.remove(path)
    s = full["summary"]
    return {k: s.get(k) for k in FIELDS} | {"per_cause_auroc": s.get("per_cause_auroc")}


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--buildings", type=int, default=24)
    ap.add_argument("--months", type=int, default=2)
    ap.add_argument("--world", choices=["B", "D"], default="B")
    ap.add_argument("--seed", type=int, default=5)
    ap.add_argument("--boot", type=int, default=200)
    ap.add_argument("--out", default=os.path.join("results", "pilot_dry_run"))
    a = ap.parse_args(argv)
    out = os.path.abspath(a.out)
    os.makedirs(out, exist_ok=True)
    man = build_fleet(out, a.buildings, a.months, a.world, a.seed)
    full = os.path.join(out, "manifest_SYNTHETIC_all.csv")
    man.to_csv(full, index=False)
    order = np.random.default_rng(a.seed).permutation(len(man))
    half = len(man) // 2
    cal_m, score_m = os.path.join(out, "manifest_SYNTHETIC_calibrate.csv"), os.path.join(out, "manifest_SYNTHETIC_score.csv")
    man.iloc[order[:half]].to_csv(cal_m, index=False)
    man.iloc[order[half:]].to_csv(score_m, index=False)

    res = {"SYNTHETIC": True, "note": "Simulated buildings with simulator ground truth standing in for inspections. Not evidence about real buildings.",
           "world": a.world, "buildings": a.buildings, "months_per_building": a.months, "seed": a.seed,
           "label_prevalence": {c: float(man["causes"].str.contains(c).mean()) for c in CAUSES}}
    res["all_bundled"] = evaluate(full, os.path.join(out, "eval_all_bundled"), boot=a.boot)
    model = os.path.join(out, "fleet_model_SYNTHETIC.joblib")
    res["calibrate_stdout"] = run([sys.executable, "-m", "deltat_doctor.cli", "calibrate", cal_m, "--out", model, "--seed", str(a.seed)]).strip()
    card = json.load(open(model + ".card.json"))
    card = {"SYNTHETIC": True} | card       # extra keys do not affect loading; the model's sha256 is unchanged
    json.dump(card, open(model + ".card.json", "w"), indent=2, default=float)
    res["calibration_card"] = {k: card[k] for k in ("weakly_calibrated", "n_labelled_buildings", "n_fit_buildings", "n_holdout_buildings", "holdout")}
    res["second_half_bundled"] = evaluate(score_m, os.path.join(out, "eval_half_bundled"), boot=a.boot)
    res["second_half_calibrated"] = evaluate(score_m, os.path.join(out, "eval_half_calibrated"), model=model, boot=a.boot)
    res["calibrated_model_sha256"] = card["sha256"]
    json.dump(res, open(os.path.join(out, "summary_synthetic.json"), "w"), indent=2, default=float)

    f = lambda v: "n/a" if v is None or (isinstance(v, float) and np.isnan(v)) else (f"{v:.2f}" if isinstance(v, float) else str(v))
    lines = ["# Pilot dry run summary (SYNTHETIC)", "",
             f"**Simulated buildings only (simulator {a.world}, seed {a.seed}); the labels are simulator ground truth, not inspections. "
             "Nothing here is evidence about real buildings.** Produced by `scripts/pilot_dry_run.py`.", "",
             f"Fleet: {a.buildings} buildings, {a.months} months each. Calibration half: {half}; scoring half: {len(man) - half}.", "",
             "| Measure | All buildings, bundled model | Scoring half, bundled | Scoring half, calibrated |", "|---|---|---|---|"]
    for k in FIELDS:
        if k == "interpretable":
            continue
        lines.append(f"| {k} | {f(res['all_bundled'][k])} | {f(res['second_half_bundled'][k])} | {f(res['second_half_calibrated'][k])} |")
    lines += ["", "Calibration card: " + ("**weakly calibrated**" if card["weakly_calibrated"] else "calibrated") +
              f" on {card['n_labelled_buildings']} buildings ({card['n_fit_buildings']} fitted, {card['n_holdout_buildings']} held out inside "
              "the calibration half).", "",
              "With fewer than 10 buildings in a half, `evaluate_real.py` marks the figures as not interpretable; that is expected in a small dry run."]
    open(os.path.join(out, "SUMMARY_SYNTHETIC.md"), "w", encoding="utf-8", newline="\n").write("\n".join(lines) + "\n")
    print("\n".join(lines))
    return res


if __name__ == "__main__":
    main()
