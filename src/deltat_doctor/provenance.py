"""Audit trail for a report: what file, which model, which parameters, when. Computed, never typed."""
from __future__ import annotations

import datetime as _dt
import hashlib
import json
import os

from . import __version__

_ASSETS = os.path.join(os.path.dirname(__file__), "assets")


def model_identity(informed: bool = False) -> dict:
    """Identity of the bundled model that produced a result, from its model card."""
    name = "diagnoser_informed.joblib" if informed else "diagnoser.joblib"
    try:
        card = json.load(open(os.path.join(_ASSETS, "model_card.json")))
    except (OSError, ValueError):
        return {"file": name, "note": "model card not found"}
    return {
        "file": name, "package_version": card.get("version"), "sha256": (card.get("sha256", {}).get(name) or "")[:16],
        "trained_on_windows": card.get("trained_on_samples"), "trained_on_buildings": card.get("n_buildings"),
        "training_data": card.get("data"), "git_commit_at_training": card.get("git_commit_at_training"),
        "sklearn_version": card.get("sklearn_version"),
    }


def build(d: dict, *, filename: str | None = None, raw: bytes | None = None, rows: int | None = None,
          kind: str = "diagnosis") -> dict:
    """Provenance block for a Report.to_dict() or PortfolioReport.to_dict()."""
    informed = d.get("mode") == "informed" or any(b.get("mode") == "informed" for b in d.get("buildings", []))
    model = model_identity(informed)
    sha = hashlib.sha256(raw).hexdigest() if raw is not None else None
    terms = d.get("terms", {})
    now = _dt.datetime.now(_dt.timezone.utc)
    basis = json.dumps({"in": sha, "terms": terms, "design": d.get("design_delta_t_c"), "model": model.get("sha256"),
                        "v": __version__, "kind": kind}, sort_keys=True)
    rid = f"DTD-{now:%Y%m%d}-{hashlib.sha256(basis.encode()).hexdigest()[:8].upper()}"
    dq = d.get("data_quality", {})
    inp = dq.get("input", {})
    return {
        "report_id": rid, "generated_utc": now.strftime("%Y-%m-%dT%H:%M:%SZ"), "software_version": __version__, "kind": kind,
        "input": {"filename": (filename or "")[:120] or None, "sha256": sha, "bytes": len(raw) if raw is not None else None,
                  "rows_read": inp.get("rows_raw", rows), "dropped_fraction": inp.get("dropped_fraction")},
        "data_window": {"start": dq.get("start"), "end": dq.get("end"), "days": d.get("n_days")},
        "model": model,
        "parameters": {**terms, "design_delta_t_c": d.get("design_delta_t_c"), "mode": d.get("mode")},
        "quality": {"reliable": dq.get("reliable"), "coverage": dq.get("coverage"),
                    "features_out_of_range": dq.get("features_out_of_range"), "out_of_range_limit": dq.get("out_of_range_limit")},
    }
