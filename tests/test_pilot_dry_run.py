"""Reduced pilot dry run (scripts/pilot_dry_run.py): fleet files, manifest, evaluate_real, calibrate, scoring with the calibrated model."""
import json
import os
import sys

import pandas as pd

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))
import pilot_dry_run  # noqa: E402


def test_reduced_pilot_dry_run_end_to_end(tmp_path):
    out = tmp_path / "dry"
    res = pilot_dry_run.main(["--buildings", "20", "--months", "1", "--out", str(out), "--boot", "0"])
    files = os.listdir(out)
    exports = [f for f in files if f.endswith(".csv") and not f.startswith("manifest")]
    assert len(exports) == 20 and all(f.startswith("SYNTHETIC_") for f in exports)
    man = pd.read_csv(out / "manifest_SYNTHETIC_all.csv", dtype=str)
    assert list(man.columns) == list(pd.read_csv(os.path.join(os.path.dirname(__file__), "..", "examples", "real_manifest_template.csv")).columns)
    assert man["building_id"].str.startswith("SYN-").all() and (man["complete"] == "yes").all()
    summary = json.load(open(out / "summary_synthetic.json"))
    assert summary["SYNTHETIC"] is True and "Not evidence about real buildings" in summary["note"]
    assert summary["all_bundled"]["n_buildings"] == 20 and summary["second_half_calibrated"]["n_buildings"] == 10
    card = res["calibration_card"]
    assert card["n_labelled_buildings"] == 10 and card["weakly_calibrated"] is True
    text = (out / "SUMMARY_SYNTHETIC.md").read_text(encoding="utf-8")
    assert text.startswith("# Pilot dry run summary (SYNTHETIC)") and "weakly calibrated" in text
    card_file = json.load(open(out / "fleet_model_SYNTHETIC.joblib.card.json"))
    assert card_file["SYNTHETIC"] is True and card_file["n_labelled_buildings"] == 10
    for d in ("eval_all_bundled", "eval_half_bundled", "eval_half_calibrated"):
        files = os.listdir(out / d)
        assert files == ["SYNTHETIC_eval.json"], files            # no file named "real_..." is left behind
        assert json.load(open(out / d / "SYNTHETIC_eval.json"))["SYNTHETIC"] is True
    # the calibrated model was really used: its probabilities differ from the bundled model's on the same buildings
    pb = [b["probs"] for b in json.load(open(out / "eval_half_bundled" / "SYNTHETIC_eval.json"))["buildings"]]
    pc = [b["probs"] for b in json.load(open(out / "eval_half_calibrated" / "SYNTHETIC_eval.json"))["buildings"]]
    assert pb != pc
