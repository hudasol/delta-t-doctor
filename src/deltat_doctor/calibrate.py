"""Fleet calibration: adapt the cause classifiers to a fleet using a few inspected, labelled buildings (docs/PILOT.md, docs/API.md).

Why: across simulated physics the model transfers poorly (macro AUROC 0.68 to 0.77), and adding about 20 to 40 labelled buildings of the
target physics lifts it to 0.80 to 0.84 in simulation (docs/TRANSFER_V2.md). This module turns that finding into a tool. It is not
evidence that the same happens on real buildings.

What it does, exactly as measured in scripts/transfer_fewshot.py:

* keeps the base model's training rows (bundled as assets/calibration_base.npz, verified by sha256) and adds every analysis window of each
  labelled building, repeated REPEAT times;
* refits the four calibrated cause classifiers and the any fault classifier with the product's settings and building grouped calibration;
* refits the open set guard and the per feature range on base plus fleet windows, so the fleet's own buildings count as seen;
* keeps the base model's delta T gain and saving regressors unchanged: inspections give causes, not recoverable delta T, so savings
  still come from the simulator trained regressors.

Safety rules: fewer than MIN_BUILDINGS usable labelled buildings is refused; fewer than WEAK_BELOW is allowed but marked weakly calibrated in
the model card and in every report; a holdout part of the manifest is never used for fitting and the model card carries the holdout
report; the output can never overwrite the bundled default model, and a calibrated model is used only when asked for with --model.
"""
from __future__ import annotations

import copy
import datetime as _dt
import hashlib
import json
import os
import warnings

import numpy as np
import pandas as pd

from . import CAUSES, __version__
from .features import FEATURE_NAMES, extract, to_vector

MIN_BUILDINGS = 10
WEAK_BELOW = 20
REPEAT = 5
HOLDOUT = 0.3
_ASSETS = os.path.join(os.path.dirname(__file__), "assets")
BASE_DATA = os.path.join(_ASSETS, "calibration_base.npz")
KNOWN = set(CAUSES) | {"other", "none"}


class CalibrationError(ValueError):
    pass


def _sha(path: str) -> str:
    with open(path, "rb") as fh:
        return hashlib.sha256(fh.read()).hexdigest()


def read_manifest(path: str) -> list[dict]:
    """Manifest columns: building_id, file, causes (semicolon list), complete (yes/no), optional design_dt, min_dt."""
    man = pd.read_csv(path, dtype=str).fillna("")
    for col in ("building_id", "file", "causes", "complete"):
        if col not in man.columns:
            raise CalibrationError(f"The manifest has no '{col}' column (see examples/real_manifest_template.csv).")
    base = os.path.dirname(os.path.abspath(path))
    rows = []
    for _, m in man.iterrows():
        labels = {x.strip() for x in m["causes"].split(";") if x.strip()}
        unknown = labels - KNOWN
        if unknown:
            raise CalibrationError(f"Building {m['building_id']}: unknown cause label(s) {sorted(unknown)}; use {sorted(KNOWN)}.")
        rows.append({"building_id": m["building_id"], "file": os.path.join(base, m["file"]), "labels": labels,
                     "complete": m["complete"].strip().lower() in ("yes", "y", "true", "1")})
    return rows


def building_windows(path: str) -> np.ndarray:
    """The 42 shape features of every analysis window of one meter export, cut exactly as diagnose() cuts them."""
    from .diagnose import _windows
    from .io import canonicalise, read_table
    with open(path, "rb") as fh:
        h = canonicalise(read_table(fh.read(), path))
    wins = _windows(h)
    if not wins:
        raise CalibrationError(f"{os.path.basename(path)}: not enough contiguous data for one 14 day window.")
    return np.vstack([to_vector(extract(w)) for w in wins])


def label_vector(labels: set) -> np.ndarray:
    return np.array([float(c in labels) for c in CAUSES])


def load_base_data(path: str = BASE_DATA) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Base training rows (X, Y, building groups), verified against the sha256 recorded in the model card (fail closed)."""
    if not os.path.exists(path):
        raise CalibrationError("The base training rows (assets/calibration_base.npz) are missing; run scripts/build_calibration_base.py.")
    if os.path.abspath(os.path.dirname(path)) == os.path.abspath(_ASSETS):
        try:
            want = json.load(open(os.path.join(_ASSETS, "model_card.json")))["sha256"][os.path.basename(path)]
        except (OSError, KeyError, ValueError):
            raise CalibrationError("No recorded sha256 for the base training rows; refusing to use them.") from None
        if _sha(path) != want:
            raise CalibrationError("The base training rows do not match their recorded sha256; refusing to use them.")
    z = np.load(path, allow_pickle=False)
    return z["X"], z["Y"], z["groups"]


def _fit_classifiers(model, X, Y, groups):
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        for k, c in enumerate(CAUSES):
            y = Y[:, k].astype(int)
            model.clf[c] = model._calibrated(X, y, groups) if y.sum() >= 10 and (1 - y).sum() >= 10 else None
        model.any_clf = model._calibrated(X, (Y.sum(1) > 0).astype(int), groups)


def _abstains(model, X) -> bool:
    return bool(np.median(model.guard.score(X)) > model.guard.threshold or model.ood_count(X).mean() > model.ood_threshold)


def _auc(y, s):
    from sklearn.metrics import roc_auc_score
    y = np.asarray(y)
    return float(roc_auc_score(y, s)) if 0 < y.sum() < len(y) else None


def holdout_report(model, buildings: list[dict]) -> dict:
    """Building level agreement and window level AUROC of one model on held out labelled buildings (probabilities used even when
    the guard would abstain, so base and calibrated models are compared on the same buildings; abstention is reported separately)."""
    rows, Yw, Pw = [], [], []
    for b in buildings:
        p = model.predict(b["X"])
        Yw.append(np.tile(label_vector(b["labels"]), (len(b["X"]), 1)))
        Pw.append(p.prob)
        mean = p.prob.mean(0)
        rows.append({"labels": b["labels"], "ranked": [CAUSES[i] for i in np.argsort(-mean)], "p_any": float(p.p_any.mean()),
                     "abstained": _abstains(model, b["X"])})
    Yw, Pw = np.vstack(Yw), np.vstack(Pw)
    per = {c: _auc(Yw[:, k], Pw[:, k]) for k, c in enumerate(CAUSES)}
    vals = [v for v in per.values() if v is not None]
    single = [r for r in rows if len(r["labels"] & set(CAUSES)) == 1]
    healthy = [r for r in rows if r["labels"] <= {"none"}]
    return {
        "n_buildings": len(rows), "n_windows": int(len(Yw)),
        "abstention_rate": float(np.mean([r["abstained"] for r in rows])),
        "per_cause_auroc": per, "macro_auroc": float(np.mean(vals)) if vals else None,
        "n_single_cause": len(single),
        "top1_agreement": float(np.mean([r["ranked"][0] in r["labels"] for r in single])) if single else None,
        "top2_agreement": float(np.mean([bool(set(r["ranked"][:2]) & r["labels"]) for r in single])) if single else None,
        "n_healthy": len(healthy),
        "healthy_false_alarm": float(np.mean([r["p_any"] >= 0.5 for r in healthy])) if healthy else None,
    }


def calibrate(manifest: str, out: str, base_model=None, base_data: tuple | None = None, repeat: int = REPEAT,
              holdout: float = HOLDOUT, seed: int = 0, base_model_path: str | None = None) -> dict:
    """Fit a fleet calibrated model from a labelled manifest and write it to `out` (plus `out`.card.json). Returns the card."""
    from .diagnose import DEFAULT_MODEL, load_default_model
    from .openset import OpenSetGuard
    if os.path.abspath(os.path.dirname(os.path.abspath(out))) == os.path.abspath(_ASSETS):
        raise CalibrationError("A calibrated model may not be written into the package assets; it must never replace the default model.")
    rows = read_manifest(manifest)
    usable = [r for r in rows if r["complete"]]
    skipped = [r["building_id"] for r in rows if not r["complete"]]
    if len(usable) < MIN_BUILDINGS:
        raise CalibrationError(f"Calibration needs at least {MIN_BUILDINGS} inspected buildings whose inspection ruled out the causes not "
                               f"listed (complete = yes); the manifest has {len(usable)}. Below that the result is not trustworthy, so no "
                               f"model was written.")
    for r in usable:
        r["X"] = building_windows(r["file"])
    order = np.random.default_rng(seed).permutation(len(usable))
    n_hold = max(3, int(round(holdout * len(usable))))
    hold = [usable[i] for i in order[:n_hold]]
    fit = [usable[i] for i in order[n_hold:]]

    if base_model is None:
        base_model_path = base_model_path or DEFAULT_MODEL
        base = load_default_model(base_model_path)
    else:
        base = base_model     # tests and experiments pass a model object; the card then says so instead of naming a file
    Xb, Yb, gb = base_data if base_data is not None else load_base_data()
    Xf = np.vstack([r["X"] for r in fit])
    Yf = np.vstack([np.tile(label_vector(r["labels"]), (len(r["X"]), 1)) for r in fit])
    gf = np.concatenate([np.full(len(r["X"]), 10_000_000 + i) for i, r in enumerate(fit)])
    X = np.vstack([Xb] + [Xf] * repeat)
    Y = np.vstack([Yb] + [Yf] * repeat)
    g = np.concatenate([gb] + [gf] * repeat)

    model = copy.deepcopy(base)
    _fit_classifiers(model, X, Y, g)
    Xg = np.vstack([Xb, Xf])[:, :len(FEATURE_NAMES)]
    model.guard = OpenSetGuard().fit(Xg)
    model.feat_lo, model.feat_hi = np.percentile(Xg, 1, axis=0), np.percentile(Xg, 99, axis=0)
    model.ood_threshold = int(np.percentile(model.ood_count(Xg), 95))

    weak = len(usable) < WEAK_BELOW
    card = {
        "kind": "fleet_calibrated", "weakly_calibrated": weak, "software_version": __version__,
        "created_utc": _dt.datetime.now(_dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "base_model": ({"file": os.path.basename(base_model_path), "sha256": _sha(base_model_path)} if base_model_path
                       else {"file": "model object passed by the caller", "sha256": None}),
        "manifest": {"file": os.path.basename(manifest), "sha256": _sha(manifest)},
        "n_labelled_buildings": len(usable), "n_fit_buildings": len(fit), "n_holdout_buildings": len(hold),
        "n_fit_windows": int(len(Xf)), "skipped_incomplete": skipped,
        "parameters": {"repeat": repeat, "holdout": holdout, "seed": seed, "min_buildings": MIN_BUILDINGS, "weak_below": WEAK_BELOW},
        "fit_buildings": [{"building_id": r["building_id"], "sha256": _sha(r["file"])} for r in fit],
        "holdout_buildings": [{"building_id": r["building_id"], "sha256": _sha(r["file"])} for r in hold],
        "holdout": {"base": holdout_report(base, hold), "calibrated": holdout_report(model, hold)},
        "kept_from_base": ["gain and saving regressors", "evidence statements", "healthy reference"],
        "note": ("Calibrated on inspected buildings; the holdout figures are from buildings not used for fitting. "
                 "Delta T gains and savings still come from the simulator trained base model."),
    }
    if weak:
        card["warning"] = (f"Weakly calibrated: {len(usable)} labelled buildings (at least {WEAK_BELOW} recommended). "
                           "The holdout figures rest on very few buildings.")
    model.calibration = card
    os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)
    model.save(out)
    card_out = dict(card, sha256=_sha(out))
    with open(out + ".card.json", "w", encoding="utf-8") as fh:
        json.dump(card_out, fh, indent=2, default=float)
    return card_out
