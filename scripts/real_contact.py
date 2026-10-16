"""Real data contact without labels (docs/REAL_DATA_CONTACT.md). No accuracy is measured or claimed here.

usage: python scripts/real_contact.py            (after python scripts/fetch_real_data.py)

Two paths per building:

* product path: the loader writes the meter export as a file a user would upload (columns named as the source names them) and the
  shipped product (`read_table` + `diagnose_frame`) is run on it unchanged. Outcome: diagnosed, abstained, or refused with a message.
* research path (not the product): the loader builds the canonical hourly frame directly, skipping the chilled water plausibility
  checks, so the 42 shape features, both guards and the model can be looked at on real hydraulics. This answers "if a heating file got
  past the unit checks, would the open set guard still stop it?". It is labelled as research output wherever it is reported.

Writes results/real_data_contact.json.
"""
import json, os, sys, traceback
import numpy as np
import pandas as pd

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
sys.path.insert(0, os.path.join(ROOT, "src"))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from deltat_doctor import CP_KJ_KG_K
from deltat_doctor.diagnose import _windows, diagnose_frame, load_default_model
from deltat_doctor.features import FEATURE_NAMES, extract, to_vector
from deltat_doctor.io import DataError, read_table
from real_loaders import dk_canonical, dk_export, nis_export

EXT = os.path.join(ROOT, "external")


def product_path(export: pd.DataFrame) -> dict:
    raw = export.to_csv(index=False).encode()
    try:
        rep = diagnose_frame(read_table(raw, "export.csv")).to_dict()
    except DataError as e:
        return {"outcome": "refused", "message": str(e)}
    except Exception as e:      # anything else is a product bug and is reported as such
        return {"outcome": "crash", "error": f"{type(e).__name__}: {e}", "trace": traceback.format_exc()[-800:]}
    return {"outcome": "abstained" if rep["abstained"] else "diagnosed", "delta_t_c": rep["delta_t_c"],
            "notes": rep["notes"], "reliable": rep["data_quality"]["reliable"], "guard": rep["guard"],
            "top_cause": rep["findings"][0]["cause"] if rep["findings"] else None}


def research_path(h: pd.DataFrame, model) -> dict:
    wins = _windows(h)
    if not wins:
        return {"windows": 0}
    X = np.vstack([to_vector(extract(w)) for w in wins])
    gs = model.guard.score(X)
    box = model.ood_count(X)
    p = model.predict(X)
    return {"windows": len(wins), "guard_window_flag_share": float((gs > model.guard.threshold).mean()),
            "guard_building_flag": bool(np.median(gs) > model.guard.threshold),
            "box_window_flag_share": float((box > model.ood_threshold).mean()),
            "box_median_features_out": float(np.median(box)),
            "abstain_building": bool(np.median(gs) > model.guard.threshold or np.average(box, weights=[len(w) for w in wins]) > model.ood_threshold),
            "p_any_median": float(np.median(p.p_any)),
            "flow_load_corr_median": float(np.median(X[:, FEATURE_NAMES.index("flow_load_corr")]))}


def flow_weighted_dt(h):
    return float(h["heat_kw"].sum() / (CP_KJ_KG_K * max(h["flow_kgs"].sum(), 1e-9)))


def main():
    model = load_default_model()
    man = json.load(open(os.path.join(EXT, "fetch_manifest.json")))
    out = {"note": "No cause labels exist for these data; nothing here is an accuracy figure.", "fetched": man["fetched_utc"], "datasets": {}}
    # Denmark: 40 smart heat meters
    rows = []
    for f in sorted(x["file"] for x in man["files"] if x["dataset"] == "dk_smart_heat_6563114" and x["file"].endswith(".csv")
                    and "contextual" not in x["file"]):
        raw = pd.read_csv(os.path.join(ROOT, f))
        r = {"file": os.path.basename(f), "rows": len(raw)}
        r["product"] = product_path(dk_export(raw))
        try:
            h, q = dk_canonical(raw)
            r["loader_quality"] = q
            r["flow_weighted_dt_c"] = flow_weighted_dt(h)
            r["research"] = research_path(h, model)
        except Exception as e:
            r["loader_error"] = f"{type(e).__name__}: {e}"
        rows.append(r)
        print("dk", r["file"], r["product"]["outcome"], r.get("flow_weighted_dt_c"), r.get("research", {}).get("abstain_building"), flush=True)
    out["datasets"]["dk_smart_heat_6563114"] = summarise(rows)
    # Nis: five substations, no flow column
    rows = []
    for f in sorted(x["file"] for x in man["files"] if x["dataset"] == "nis_xai4heat_2mwc6x6kwb"):
        raw = pd.read_csv(os.path.join(ROOT, f))
        r = {"file": os.path.basename(f), "rows": len(raw), "product": product_path(nis_export(raw)),
             "primary_dt_median_c": float((raw["t_sup_prim"] - raw["t_ret_prim"]).median())}
        rows.append(r)
        print("nis", r["file"], r["product"]["outcome"], flush=True)
    out["datasets"]["nis_xai4heat_2mwc6x6kwb"] = summarise(rows)
    os.makedirs(os.path.join(ROOT, "results"), exist_ok=True)
    json.dump(out, open(os.path.join(ROOT, "results", "real_data_contact.json"), "w"), indent=2, default=float)
    print(json.dumps({k: {kk: vv for kk, vv in v.items() if kk != "buildings"} for k, v in out["datasets"].items()}, indent=2, default=float))


def summarise(rows):
    oc = pd.Series([r["product"]["outcome"] for r in rows]).value_counts().to_dict()
    msgs = pd.Series([r["product"].get("message", r["product"].get("error", "")).split(".")[0] for r in rows]).value_counts().to_dict()
    s = {"n_buildings": len(rows), "product_outcomes": oc, "product_messages": msgs, "buildings": rows}
    res = [r["research"] for r in rows if r.get("research", {}).get("windows")]
    if res:
        dts = np.array([r["flow_weighted_dt_c"] for r in rows if "research" in r and r["research"].get("windows")])
        s["research"] = {
            "n_with_windows": len(res),
            "abstain_building_share": float(np.mean([r["abstain_building"] for r in res])),
            "guard_building_flag_share": float(np.mean([r["guard_building_flag"] for r in res])),
            "guard_window_flag_share_mean": float(np.mean([r["guard_window_flag_share"] for r in res])),
            "box_window_flag_share_mean": float(np.mean([r["box_window_flag_share"] for r in res])),
            "flow_weighted_dt_c_percentiles_5_25_50_75_95": [float(v) for v in np.percentile(dts, [5, 25, 50, 75, 95])],
            "p_any_median_of_buildings": float(np.median([r["p_any_median"] for r in res])),
            "flow_load_corr_median_of_buildings": float(np.median([r["flow_load_corr_median"] for r in res])),
        }
    return s


if __name__ == "__main__":
    main()
