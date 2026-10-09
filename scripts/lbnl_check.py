"""External sanity check against the public LBNL FDD chiller-plant benchmark.

Usage: python scripts/lbnl_check.py PATH/TO/LBNL_FDD_Data_Sets_Chiller_Plant.zip [OUT_JSON]
Extracts a handful of the CSVs into ./external/lbnl (gitignored), maps secondary-loop columns
to the tool's canonical frame, and reports the trained model's verdicts per 30-day window.
No retraining and no threshold tuning happens here.
"""
import json, os, sys, zipfile
import numpy as np
import pandas as pd

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
from deltat_doctor import CAUSES
from deltat_doctor.diagnose import load_default_model, _windows
from deltat_doctor.features import extract, to_vector
from deltat_doctor.io import canonicalise

FILES = {
    "fault_free": "ChillerPlant.csv",
    "sec_dp_bias_-20%": "ChillerPlant_secondary_chilled_water_pressure_bias_-020.csv",
    "sec_dp_bias_-10%": "ChillerPlant_secondary_chilled_water_pressure_bias_-010.csv",
    "sec_dp_bias_+10%": "ChillerPlant_secondary_chilled_water_pressure_bias_010.csv",
    "sec_dp_bias_+20%": "ChillerPlant_secondary_chilled_water_pressure_bias_020.csv",
    "tower_fouling_95%": "ChillerPlant_coolingtower_fouling_095.csv",
    "tower_PI_tuning": "ChillerPlant_coolingtower_PI.csv",
    "chiller_bias_+2C": "ChillerPlant_chiller_bias_2.csv",
    "cond_3way_stuck_75%": "ChillerPlant_bypass_stuck_075.csv",
    "cond_3way_leak_75%": "ChillerPlant_bypass_leakage_075.csv",
}
COLS = ["Datetime", "CWL_SEC_RW_TEMP", "CWL_SEC_SW_TEMP", "CWL_SEC_CW_FLOW", "OA_TEMP"]


def to_frame(csv_path: str) -> pd.DataFrame:
    df = pd.read_csv(csv_path, usecols=COLS, parse_dates=["Datetime"])
    f2c = lambda x: (x - 32.0) * 5.0 / 9.0
    return pd.DataFrame({
        "timestamp": df["Datetime"],
        "flow_ls": df["CWL_SEC_CW_FLOW"] * 0.0630902,            # GPM -> kg/s (~L/s)
        # NOTE: LBNL names these from the plant's point of view: CWL_SEC_RW_TEMP is the water
        # ENTERING the secondary loop (cold, = building supply) and CWL_SEC_SW_TEMP the water
        # LEAVING it (warm, = building return). Verified from the data: load = flow*cp*(SW-RW).
        "t_supply_c": f2c(df["CWL_SEC_RW_TEMP"]),
        "t_return_c": f2c(df["CWL_SEC_SW_TEMP"]),
        "t_outdoor_c": f2c(df["OA_TEMP"]),
    })


def main(zip_path, out_json):
    model = load_default_model()
    outdir = os.path.join("external", "lbnl")
    os.makedirs(outdir, exist_ok=True)
    results = {}
    with zipfile.ZipFile(zip_path) as z:
        for tag, name in FILES.items():
            dest = os.path.join(outdir, name)
            if not os.path.exists(dest):
                print("extracting", name, flush=True)
                z.extract(name, outdir)
            f = to_frame(dest)
            h = canonicalise(f)
            wins = _windows(h)
            rows = []
            for w in wins:
                p = model.predict(to_vector(extract(w)))
                month = int(pd.DatetimeIndex(w["timestamp"]).month[len(w) // 2])
                dt = float(w["heat_kw"].sum() / (4.186 * max(w["flow_kgs"].sum(), 1e-9)))
                rows.append({"month": month, "dt_c": dt, "p_any": float(p.p_any[0]),
                             **{c: float(p.prob[0, k]) for k, c in enumerate(CAUSES)},
                             "cooling_kwh": float(w["heat_kw"].sum())})
            cool = [r for r in rows if r["month"] in (6, 7, 8, 9)]
            def mean(rs, k): return float(np.mean([r[k] for r in rs])) if rs else float("nan")
            results[tag] = {
                "file": name, "windows": rows,
                "cooling_season": {k: mean(cool, k) for k in ("dt_c", "p_any", *CAUSES)},
                "full_year": {k: mean(rows, k) for k in ("dt_c", "p_any", *CAUSES)},
            }
            cs = results[tag]["cooling_season"]
            print(f"{tag:22s} cooling-season dT {cs['dt_c']:.2f}  p_any {cs['p_any']:.2f}  " +
                  "  ".join(f"{c[:4]} {cs[c]:.2f}" for c in CAUSES), flush=True)
    json.dump(results, open(out_json, "w"), indent=2)
    print("wrote", out_json)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    main(sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else "results/lbnl_check.json")
