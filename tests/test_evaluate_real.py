import json, os, subprocess, sys

ROOT = os.path.join(os.path.dirname(__file__), "..")


def test_evaluator_runs_and_refuses_small_n(tmp_path):
    from deltat_doctor.cli import main
    for name, causes, seed in (("f1", "fouling", 1), ("h1", "", 9)):
        main(["simulate", "--causes", causes, "--seed", str(seed), "--out", str(tmp_path / f"{name}.csv")])
    (tmp_path / "m.csv").write_text("building_id,file,causes,complete,design_dt,min_dt\n"
                                    "a,f1.csv,fouling,yes,,8.9\nb,h1.csv,none,yes,,8.9\n")
    r = subprocess.run([sys.executable, os.path.join(ROOT, "scripts", "evaluate_real.py"), str(tmp_path / "m.csv"), "--out", str(tmp_path / "o")],
                       capture_output=True, text=True, cwd=ROOT)
    assert r.returncode == 0, r.stderr
    s = json.load(open(tmp_path / "o" / "real_eval.json"))["summary"]
    assert s["n_buildings"] == 2 and s["interpretable"] is False and s["pilot_criteria"] is None and "warning" in s
