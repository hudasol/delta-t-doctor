"""Fleet calibration (calibrate.py): refusal paths, weak marking, integrity, and improvement on a pretend fleet.

The pretend fleet is simulator B; the base model is trained on a small simulator A set only, so B is a world it has not seen.
"""
import hashlib
import json
import os

import numpy as np
import pandas as pd
import pytest

from deltat_doctor import CAUSES
from deltat_doctor import calibrate as cal
from deltat_doctor import diagnose as dg
from deltat_doctor.io import DataError
from deltat_doctor.models import Diagnoser
from deltat_doctor.sim.dataset import generate
from deltat_doctor.sim.hydraulic import make_sample_b, sample_building_b
from deltat_doctor.sim.scenarios import draw_cause_set


@pytest.fixture(scope="module")
def base():
    """A-only base model and its training rows (small; not for accuracy claims)."""
    ds = generate(60, 6, seed=17, n_jobs=1)
    g = ds.meta["building_id"].to_numpy()
    return Diagnoser(seed=0).fit(ds.X, ds.Y, ds.G, groups=g), (ds.X, ds.Y, g)


def _fleet(tmp_path, n, seed=3, months=(5, 6), complete=True):
    """n simulator-B buildings, each a two month meter export, labelled from the simulator's own counterfactual ground truth."""
    rng = np.random.default_rng(seed)
    rows = []
    for b in range(n):
        cfg = sample_building_b(rng, b)
        causes = draw_cause_set(rng)
        frames, present = [], set()
        for m in months:
            s = make_sample_b(rng, b, cfg=cfg, causes=causes, month=m)
            frames.append(s.frame)
            present |= {c for c in CAUSES if s.present[c]}
        name = f"b{b:03d}.csv"
        pd.concat(frames, ignore_index=True).to_csv(tmp_path / name, index=False)
        rows.append({"building_id": f"B{b:03d}", "file": name, "causes": ";".join(sorted(present)) or "none",
                     "complete": "yes" if complete else "no", "design_dt": "", "min_dt": "8.9"})
    path = tmp_path / "manifest.csv"
    pd.DataFrame(rows).to_csv(path, index=False)
    return str(path)


def test_refuses_below_ten_buildings(tmp_path, base):
    m, data = base
    man = _fleet(tmp_path, 9)
    with pytest.raises(cal.CalibrationError, match="at least 10"):
        cal.calibrate(man, str(tmp_path / "out.joblib"), base_model=m, base_data=data)
    assert not os.path.exists(tmp_path / "out.joblib")


def test_incomplete_inspections_do_not_count(tmp_path, base):
    m, data = base
    man = _fleet(tmp_path, 12, complete=False)
    with pytest.raises(cal.CalibrationError, match="has 0"):
        cal.calibrate(man, str(tmp_path / "out.joblib"), base_model=m, base_data=data)


def test_cli_refusal_message(tmp_path, base, capsys):
    from deltat_doctor.cli import main
    man = _fleet(tmp_path, 3)
    with pytest.raises(SystemExit) as e:
        main(["calibrate", man, "--out", str(tmp_path / "out.joblib")])
    assert "calibration refused" in str(e.value) and "at least 10" in str(e.value)


def test_never_writes_into_package_assets(tmp_path, base):
    m, data = base
    man = _fleet(tmp_path, 10)
    with pytest.raises(cal.CalibrationError, match="assets"):
        cal.calibrate(man, os.path.join(os.path.dirname(dg.DEFAULT_MODEL), "x.joblib"), base_model=m, base_data=data)


@pytest.fixture(scope="module")
def weak(tmp_path_factory, base):
    m, data = base
    d = tmp_path_factory.mktemp("weak")
    man = _fleet(d, 12, seed=8)
    out = str(d / "fleet.joblib")
    card = cal.calibrate(man, out, base_model=m, base_data=data)
    return d, out, card


def test_weak_calibration_is_marked_everywhere(weak):
    d, out, card = weak
    assert card["weakly_calibrated"] is True and "Weakly calibrated" in card["warning"]
    assert card["n_labelled_buildings"] == 12 and card["n_holdout_buildings"] >= 3
    assert card["n_fit_buildings"] + card["n_holdout_buildings"] == 12
    assert {"base", "calibrated"} <= set(card["holdout"]) and card["base_model"]["sha256"] is None
    assert card["manifest"]["sha256"] == hashlib.sha256(open(d / "manifest.csv", "rb").read()).hexdigest()
    on_disk = json.load(open(out + ".card.json"))
    assert on_disk["sha256"] == hashlib.sha256(open(out, "rb").read()).hexdigest()
    model = dg._load_verified(out)
    rep = dg.diagnose_csv(str(d / "b000.csv"), model=model).to_dict()
    assert rep["calibration"]["weakly_calibrated"] is True
    assert any(n.startswith("WEAKLY CALIBRATED") for n in rep["notes"])
    assert any("معايرة ضعيفة" in n for n in rep["notes_ar"])
    from deltat_doctor import provenance
    prov = provenance.build(rep, filename="b000.csv", raw=b"x")
    assert prov["model"]["file"] == "fleet calibrated model" and prov["model"]["weakly_calibrated"] is True
    assert prov["model"]["sha256"] == on_disk["sha256"][:16]


def test_tampered_calibrated_model_is_refused(weak, tmp_path):
    _, out, _ = weak
    bad = tmp_path / "fleet.joblib"
    blob = bytearray(open(out, "rb").read())
    blob[len(blob) // 2] ^= 0xFF
    bad.write_bytes(bytes(blob))
    (tmp_path / "fleet.joblib.card.json").write_text(open(out + ".card.json").read())
    with pytest.raises(RuntimeError, match="does not match"):
        dg._load_verified(str(bad))


def test_calibrated_model_is_blind_only(weak):
    d, out, _ = weak
    with pytest.raises(DataError, match="blind only"):
        dg.diagnose_csv(str(d / "b000.csv"), model=dg._load_verified(out), design_delta_t_c=9.0)


def test_default_model_is_untouched_and_still_default(weak):
    card = json.load(open(os.path.join(os.path.dirname(dg.DEFAULT_MODEL), "model_card.json")))
    assert hashlib.sha256(open(dg.DEFAULT_MODEL, "rb").read()).hexdigest() == card["sha256"]["diagnoser.joblib"]
    assert dg.load_default_model() is not None and not getattr(dg.load_default_model(), "calibration", None)


def test_calibration_improves_held_out_agreement_on_unseen_world(tmp_path, base):
    """30 pretend-fleet buildings from simulator B; the A-only base has never seen B. Holdout = 9 buildings never used for fitting."""
    m, data = base
    man = _fleet(tmp_path, 30, seed=21)
    card = cal.calibrate(man, str(tmp_path / "fleet.joblib"), base_model=m, base_data=data)
    hb, hc = card["holdout"]["base"], card["holdout"]["calibrated"]
    assert card["weakly_calibrated"] is False
    assert hc["macro_auroc"] > hb["macro_auroc"]
