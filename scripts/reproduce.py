"""Regenerate key results from fixed seeds and compare them with what is committed in results/ and the model card.

usage (any platform, from the repository root):
    python scripts/reproduce.py            quick checks (a few minutes)
    python scripts/reproduce.py --full     also regenerates the simulator A pool (500 x 10 windows) and world D (150 x 10); slow

Checks:
  artefacts     sha256 of every bundled model and data file against assets/model_card.json
  zero_shot_D   shipped model on the committed world D set, compared with results/world_d.json (zero_shot)
  openset       shipped open set guard rates on world D and the fresh in world sets, compared with results/world_d.json (guard)
  pool_A        --full: simulator A pool regenerated (seed 11) and compared numerically with the shipped model's stored training
                percentiles and label prevalence (the file sha256 is also reported; it differs across platforms in the last float bits)
  world_D       --full: world D regenerated (seed 21) and compared array by array with results/data_d/main.npz

Writes results/reproduce_report.json and exits with code 1 if any check differs.

Known gap: the committed simulator B pool (results/data_b) cannot be regenerated from this repository, because the seed used to make it
was not recorded (seed 11 gives a different pool). It is committed, and its sha256 is in the model card.
"""
import argparse, hashlib, json, os, sys, tempfile, time
import numpy as np

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
sys.path.insert(0, os.path.join(ROOT, "src"))
from deltat_doctor.sim.dataset import Dataset, generate

ASSETS = os.path.join(ROOT, "src", "deltat_doctor", "assets")
TOL = 1e-9


def sha(path):
    return hashlib.sha256(open(path, "rb").read()).hexdigest()


def same_arrays(a, b):
    return all(np.array_equal(getattr(a, k), getattr(b, k)) for k in ("X", "Y", "G"))


def check_artefacts():
    card = json.load(open(os.path.join(ASSETS, "model_card.json")))
    bad = [n for n, h in card["sha256"].items() if not os.path.exists(os.path.join(ASSETS, n)) or sha(os.path.join(ASSETS, n)) != h]
    return {"ok": not bad, "checked": sorted(card["sha256"]), "mismatch": bad}


def check_pool_a(jobs):
    card = json.load(open(os.path.join(ASSETS, "model_card.json")))
    new = generate(500, 10, seed=11, n_jobs=jobs, sim="A")
    with tempfile.TemporaryDirectory() as d:
        p = os.path.join(d, "main.npz")
        np.savez_compressed(p, X=new.X, Y=new.Y, G=new.G)
        got = sha(p)
    from deltat_doctor.diagnose import load_default_model
    m = load_default_model()
    X = np.vstack([new.X, Dataset.load(os.path.join(ROOT, "results", "data_b", "main.npz")).X])
    d = max(float(np.abs(np.percentile(X, 1, 0) - m.feat_lo).max()), float(np.abs(np.percentile(X, 99, 0) - m.feat_hi).max()))
    return {"ok": len(X) == m.trained_on and d < 1e-9, "max_abs_diff_training_percentiles": d, "file_sha256": got,
            "model_card_file_sha256": card["training_data_sha256"]["results/data/main.npz"]}


def check_world_d(jobs):
    new = generate(150, 10, seed=21, n_jobs=jobs, sim="D", temporal=True)
    old = Dataset.load(os.path.join(ROOT, "results", "data_d", "main.npz"))
    return {"ok": same_arrays(new, old) and np.array_equal(new.T, old.T)}


def check_zero_shot_d():
    from deltat_doctor.diagnose import load_default_model
    from deltat_doctor.evaluate import metrics
    D = Dataset.load(os.path.join(ROOT, "results", "data_d", "main.npz"))
    want = json.load(open(os.path.join(ROOT, "results", "world_d.json")))["zero_shot"]
    r = metrics(D, load_default_model().predict(D.X))
    got = {"macro_auroc": r["macro_auroc"], "any_fault_auroc": r["any_fault_auroc"]}
    diff = max(abs(got[k] - want[k]) for k in got)
    return {"ok": diff <= TOL, "got": got, "committed": {k: want[k] for k in got}, "max_abs_diff": diff}


def check_openset():
    from deltat_doctor.diagnose import load_default_model
    m = load_default_model()
    want = json.load(open(os.path.join(ROOT, "results", "world_d.json")))["guard"]
    out, ok = {}, True
    for name, path in (("D", "results/data_d/main.npz"), ("fresh_A", "results/data_fresh_a/main.npz"), ("fresh_B", "results/data_fresh_b/main.npz")):
        p = os.path.join(ROOT, path)
        if not os.path.exists(p):
            out[name] = "set not present (run scripts/world_d_eval.py guard to create it)"
            continue
        X = Dataset.load(p).X
        got = float((m.guard.score(X) > m.guard.threshold).mean())
        out[name] = {"windows_open_set": got, "committed": want[name]["windows_open_set"]}
        ok &= abs(got - want[name]["windows_open_set"]) <= TOL
    return {"ok": bool(ok), **out}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--full", action="store_true")
    ap.add_argument("--jobs", type=int, default=max(1, (os.cpu_count() or 2) - 1))
    a = ap.parse_args()
    os.chdir(ROOT)
    checks = [("artefacts", check_artefacts), ("zero_shot_D", check_zero_shot_d),
              ("openset", check_openset)]
    if a.full:
        checks += [("pool_A", lambda: check_pool_a(a.jobs)), ("world_D", lambda: check_world_d(a.jobs))]
    report = {}
    for name, fn in checks:
        t = time.time()
        try:
            report[name] = fn()
        except FileNotFoundError as e:
            report[name] = {"ok": False, "error": f"missing file: {e.filename}"}
        report[name]["seconds"] = round(time.time() - t, 1)
        print(f"{name:12s} {'OK' if report[name]['ok'] else 'DIFFERS'}  ({report[name]['seconds']} s)", flush=True)
    json.dump(report, open(os.path.join(ROOT, "results", "reproduce_report.json"), "w"), indent=2, default=float)
    sys.exit(0 if all(r["ok"] for r in report.values()) else 1)


if __name__ == "__main__":
    main()
