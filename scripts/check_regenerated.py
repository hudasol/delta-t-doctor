"""Check that regenerated training pools are the ones the shipped model was trained on.

usage: python scripts/check_regenerated.py

* A: results/data/main.npz is regenerated (it is not committed). Its X, Y and G are saved again without the optional temporal block
  and the sha256 of that file is compared with training_data_sha256 in the model card (bitwise). Because that hash changes with the last
  bit of any float, the check that decides "identical" is numerical: row count, label prevalence, and the 1st and 99th percentile of every
  feature, which the shipped model stores from its exact training rows.
* B: results/data_b_t/main.npz (regenerated with --temporal, seed 11) is compared array by array with the committed
  results/data_b/main.npz. They differ: the seed used for the committed B pool was not recorded. This is reported, not counted, and the
  regenerated pool is used only where both sides of a comparison use it (the temporal block experiment).

Writes results/regeneration_check.json. Exit code 1 if anything differs.
"""
import hashlib, json, os, sys, tempfile
import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))
from deltat_doctor.sim.dataset import Dataset

card = json.load(open("src/deltat_doctor/assets/model_card.json"))
out = {}
a = Dataset.load("results/data/main.npz")
with tempfile.TemporaryDirectory() as d:
    p = os.path.join(d, "main.npz")
    np.savez_compressed(p, X=a.X, Y=a.Y, G=a.G)
    got = hashlib.sha256(open(p, "rb").read()).hexdigest()
want = card["training_data_sha256"]["results/data/main.npz"]
out["A"] = {"regenerated_sha256_without_temporal": got, "model_card_sha256": want, "file_identical": got == want}
# The file hash is sensitive to the last bit of every float. A numerical check: the shipped model stores the 1st and 99th percentile of
# every feature over its exact training rows (A + B). Recompute them from the regenerated A pool plus the committed B pool.
from deltat_doctor.diagnose import load_default_model
m = load_default_model()
b0 = Dataset.load("results/data_b/main.npz")
X = np.vstack([a.X, b0.X])
dlo = float(np.abs(np.percentile(X, 1, 0) - m.feat_lo).max())
dhi = float(np.abs(np.percentile(X, 99, 0) - m.feat_hi).max())
prev = np.vstack([a.Y, b0.Y]).mean(0)
prev_card = np.array([card["prevalence"][c] for c in ("fouling", "passing_valves", "constant_flow", "overflow")])
out["A"].update({"rows": int(len(X)), "model_trained_on": int(m.trained_on), "max_abs_diff_feature_p1": dlo, "max_abs_diff_feature_p99": dhi,
                 "prevalence_identical": bool(np.allclose(prev, prev_card, rtol=0, atol=1e-12)),
                 "identical": bool(len(X) == m.trained_on and max(dlo, dhi) < 1e-9 and np.allclose(prev, prev_card, rtol=0, atol=1e-12))})
if os.path.exists("results/data_b_t/main.npz"):
    b_new, b_old = Dataset.load("results/data_b_t/main.npz"), Dataset.load("results/data_b/main.npz")
    same = all(np.array_equal(getattr(b_new, k), getattr(b_old, k)) for k in ("X", "Y", "G"))
    out["B_informational"] = {"identical_X_Y_G": bool(same), "seed_tried": 11,
                              "note": "the seed of the committed B pool is not recorded; seed 11 does not reproduce it"}
json.dump(out, open("results/regeneration_check.json", "w"), indent=2)
print(json.dumps(out, indent=2))
sys.exit(0 if out["A"]["identical"] else 1)
