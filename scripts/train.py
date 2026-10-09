"""Train the final Diagnoser on the full simulated pool and save it into the package."""
import hashlib, json, os, subprocess, sys, time
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
from deltat_doctor import CAUSES, __version__
from deltat_doctor.models import Diagnoser
from deltat_doctor.sim.dataset import Dataset

data = sys.argv[1] if len(sys.argv) > 1 else "results/data/main.npz"
out = sys.argv[2] if len(sys.argv) > 2 else "src/deltat_doctor/assets/diagnoser.joblib"
from deltat_doctor.features import augment
ds = Dataset.load(data)
t = time.time()
m = Diagnoser(seed=0).fit(ds.X, ds.Y, ds.G, groups=ds.meta["building_id"].to_numpy())
os.makedirs(os.path.dirname(out), exist_ok=True)
m.save(out)
mi = Diagnoser(seed=0).fit(augment(ds.X, ds.meta["design_dt"].to_numpy()), ds.Y, ds.G, groups=ds.meta["building_id"].to_numpy())
mi.save(os.path.join(os.path.dirname(out), "diagnoser_informed.joblib"))
card = {
    "version": __version__, "causes": list(CAUSES), "trained_on_samples": int(len(ds.X)),
    "n_buildings": int(ds.meta["building_id"].nunique()),
    "prevalence": {c: float(ds.Y[:, k].mean()) for k, c in enumerate(CAUSES)},
    "design_dt_training_range_c": [5.0, 12.2], "modes": ["blind", "informed"],
    "data": "simulated (deltat_doctor.sim); no field data",
    "train_seconds": round(time.time() - t, 1),
}
def _sha(p):
    return hashlib.sha256(open(p, "rb").read()).hexdigest()
adir = os.path.dirname(out)
try:
    sha_git = subprocess.run(["git", "rev-parse", "--short", "HEAD"], capture_output=True, text=True).stdout.strip()
except Exception:
    sha_git = ""
import sklearn
card.update({"git_commit_at_training": sha_git, "sklearn_version": sklearn.__version__,
             "training_data_sha256": _sha(data),
             "sha256": {os.path.basename(out): _sha(out), "diagnoser_informed.joblib": _sha(os.path.join(adir, "diagnoser_informed.joblib"))}})
json.dump(card, open(os.path.join(os.path.dirname(out), "model_card.json"), "w"), indent=2)
print("saved", out, card)
