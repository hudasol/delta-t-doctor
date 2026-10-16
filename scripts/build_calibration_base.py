"""Bundle the base model's training rows for fleet calibration: src/deltat_doctor/assets/calibration_base.npz.

usage: python scripts/build_calibration_base.py

Takes the same pools train.py uses (results/data/main.npz and results/data_b/main.npz), with the same building id offsets, and stores
the 42 shape features, the four presence labels and the building groups. Its sha256 is added to the model card, and calibrate.py refuses
the file if it does not match. Run scripts/check_regenerated.py first: the A pool must be the one the shipped model was trained on.
The default model and its recorded hashes are not touched.
"""
import hashlib, json, os, sys
import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))
from deltat_doctor.sim.dataset import Dataset

paths = ["results/data/main.npz", "results/data_b/main.npz"]
parts = [Dataset.load(p) for p in paths]
X = np.vstack([d.X for d in parts])
Y = np.vstack([d.Y for d in parts]).astype(np.uint8)
g = np.concatenate([d.meta["building_id"].to_numpy() + 100000 * i for i, d in enumerate(parts)]).astype(np.int64)
assets = "src/deltat_doctor/assets"
out = os.path.join(assets, "calibration_base.npz")
np.savez_compressed(out, X=X, Y=Y, groups=g)
card_path = os.path.join(assets, "model_card.json")
card = json.load(open(card_path))
card["sha256"]["calibration_base.npz"] = hashlib.sha256(open(out, "rb").read()).hexdigest()
card["calibration_base"] = {"rows": int(len(X)), "buildings": int(len(np.unique(g))), "from": paths,
                            "note": ("training rows of the shipped blind model, used only by 'deltat-doctor calibrate'; the A rows were regenerated "
                                    "and match the model's stored training percentiles to 4e-15 (scripts/check_regenerated.py)")}
json.dump(card, open(card_path, "w"), indent=2)
print("wrote", out, len(X), "rows", card["sha256"]["calibration_base.npz"])
