"""v0.2 follow-up on the LBNL benchmark (predictions P4 and P5 in docs/EXTERNAL_CHECK.md, section 5).

Needs external/lbnl/ChillerPlant.csv (extracted by scripts/lbnl_check.py).
Runs the fault-free year in blind mode, then in informed mode for a sweep of design delta-T values.
"""
import json, os, sys
import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
from lbnl_check import to_frame
from deltat_doctor import CAUSES
from deltat_doctor.diagnose import _windows, load_default_model
from deltat_doctor.features import augment, extract, to_vector
from deltat_doctor.io import canonicalise

SWEEP = [3.0, 4.1, 5.0, 6.0, 7.0, 9.0, 10.0, 12.0]
FILES = {"fault_free": "ChillerPlant.csv", "chiller_bias_+2C": "ChillerPlant_chiller_bias_2.csv",
         "cond_3way_stuck_75%": "ChillerPlant_bypass_stuck_075.csv"}

blind, informed = load_default_model(), load_default_model(informed=True)
out = {}
for tag, name in FILES.items():
    h = canonicalise(to_frame(os.path.join("external", "lbnl", name)))
    wins = [w for w in _windows(h) if int(pd.DatetimeIndex(w["timestamp"]).month[len(w) // 2]) in (6, 7, 8, 9)]
    X = np.vstack([to_vector(extract(w)) for w in wins])
    rec = {"windows": len(wins)}
    pb = blind.predict(X)
    rec["blind"] = {"p_any": float(pb.p_any.mean()), **{c: float(pb.prob[:, k].mean()) for k, c in enumerate(CAUSES)}}
    rec["informed"] = {}
    for d in SWEEP:
        pi = informed.predict(augment(X, d))
        rec["informed"][str(d)] = {"p_any": float(pi.p_any.mean()), **{c: float(pi.prob[:, k].mean()) for k, c in enumerate(CAUSES)}}
    out[tag] = rec
    print(tag, "blind p_any", round(rec["blind"]["p_any"], 2),
          "| informed:", {d: round(v["p_any"], 2) for d, v in rec["informed"].items()}, flush=True)
json.dump(out, open("results/lbnl_v02.json", "w"), indent=2)
print("wrote results/lbnl_v02.json")
