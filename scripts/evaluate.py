"""Run every evaluation protocol and write results/metrics.json, results/metrics.md and figures.

Protocols
  A. 5-fold grouped CV on building id (no building in both train and test), 4 models
  B. Stress sets: final model on fresh buildings under distribution shifts
  C. Leave-one-building-type-out
  D. Held-out seasons (train without Jun-Aug, test on Jun-Aug; train without Dec-Feb, test on Dec-Feb)
"""
import json, os, sys, time
import numpy as np
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from deltat_doctor import CAUSES, CAUSE_LABELS
from deltat_doctor.diagnose import load_default_model
from deltat_doctor.evaluate import (MODELS, confusion_single_cause, cross_validate, leave_one_group_out,
                                    metrics, subtype_recall)
from deltat_doctor.features import augment
from deltat_doctor.models import Prediction
from deltat_doctor.sim.dataset import Dataset

D = "results/data"
OUT = "results"
FIG = os.path.join(OUT, "figures")
os.makedirs(FIG, exist_ok=True)

INK, BLUE, AMBER, RED, GREY = "#11303b", "#2b7ba3", "#d9822b", "#b23a2c", "#8fa3ad"
plt.rcParams.update({"font.size": 10, "axes.edgecolor": GREY, "axes.labelcolor": INK,
                     "xtick.color": INK, "ytick.color": INK, "text.color": INK,
                     "axes.spines.top": False, "axes.spines.right": False})

short = lambda m: {k: v for k, v in m.items() if k not in ("prevalence",)}
res = {}
t0 = time.time()
ds = Dataset.load(f"{D}/main.npz")

# ---- A: grouped CV
cv = cross_validate(ds, 5)
res["cv_grouped_by_building"] = {name: m for name, (m, _) in cv.items()}
ours_pred = cv["ours_gbdt"][1]
res["cv_confusion_single_cause"] = confusion_single_cause(ds, ours_pred)
res["cv_constant_flow_subtypes"] = subtype_recall(ds, ours_pred)
dsi = Dataset(augment(ds.X, ds.meta["design_dt"].to_numpy()), ds.Y, ds.G, ds.meta)
cvi = cross_validate(dsi, 5, models={"ours_informed": MODELS["ours_gbdt"]})
res["cv_grouped_by_building"]["ours_informed"] = cvi["ours_informed"][0]
# E. by design delta-T band: does telling the model the design value cut false alarms on healthy buildings?
bands = [(5, 7), (7, 9), (9, 11), (11, 13)]
res["by_design_band"] = {}
dd = ds.meta["design_dt"].to_numpy(); healthy = ds.Y.sum(1) == 0
for lo, hi in bands:
    sel = (dd >= lo) & (dd < hi)
    row_ = {"n": int(sel.sum()), "n_healthy": int((sel & healthy).sum())}
    for tag, pr in (("blind", ours_pred), ("informed", cvi["ours_informed"][1])):
        sub = Prediction(pr.prob[sel], pr.gain[sel], pr.p_any[sel])
        m_ = metrics(ds.subset(sel), sub)
        row_[tag] = {"macro_auroc": m_["macro_auroc"], "any_fault_auroc": m_["any_fault_auroc"],
                     "mean_p_any_on_healthy": float(pr.p_any[sel & healthy].mean()),
                     "false_alarm_rate_at_0.5": float((pr.p_any[sel & healthy] >= 0.5).mean())}
    res["by_design_band"][f"{lo}-{hi}"] = row_
print("A done", round(time.time() - t0), flush=True)

# reliability (pooled over causes, out-of-fold)
p = ours_pred.prob.ravel(); y = ds.Y.ravel()
bins = np.linspace(0, 1, 11); idx = np.digitize(p, bins) - 1
xs, ys, ns = [], [], []
for b in range(10):
    s = idx == b
    if s.sum() >= 20:
        xs.append(p[s].mean()); ys.append(y[s].mean()); ns.append(int(s.sum()))
res["reliability"] = {"pred": xs, "obs": ys, "n": ns}
fig, ax = plt.subplots(figsize=(4.6, 4.2))
ax.plot([0, 1], [0, 1], color=GREY, ls="--", lw=1)
ax.plot(xs, ys, color=BLUE, marker="o", lw=2)
ax.set_xlabel("Predicted probability"); ax.set_ylabel("Observed frequency")
ax.set_title("Calibration, held-out buildings", loc="left", fontweight="bold")
fig.tight_layout(); fig.savefig(f"{FIG}/reliability.png", dpi=160); plt.close(fig)

# confusion heatmap
conf = res["cv_confusion_single_cause"]
rows = list(conf.keys())
M = np.array([[conf[r][c] for c in CAUSES] for r in rows])
fig, ax = plt.subplots(figsize=(6.2, 3.6))
im = ax.imshow(M, cmap="Blues", vmin=0, vmax=1)
ax.set_xticks(range(len(CAUSES))); ax.set_xticklabels([c.replace("_", "\n") for c in CAUSES])
ax.set_yticks(range(len(rows))); ax.set_yticklabels([f"{r} (n={conf[r]['n']})" for r in rows])
for i in range(M.shape[0]):
    for j in range(M.shape[1]):
        ax.text(j, i, f"{M[i,j]:.2f}", ha="center", va="center", color="white" if M[i, j] > .55 else INK, fontsize=9)
ax.set_xlabel("Predicted cause (mean probability)"); ax.set_ylabel("True cause injected")
ax.set_title("What the tool says when exactly one cause is present", loc="left", fontweight="bold")
for s in ax.spines.values(): s.set_visible(False)
fig.tight_layout(); fig.savefig(f"{FIG}/confusion.png", dpi=160); plt.close(fig)

# ---- B: stress sets with the final model
final = load_default_model()
STRESS = ["fresh", "noise_x3", "res_2h", "climate_p3", "climate_m3", "severity_x05",
          "severity_x15", "no_outdoor", "window_21d", "energy_only"]
res["stress"] = {}
for name in STRESS:
    sd = Dataset.load(f"{D}/stress_{name}.npz")
    res["stress"][name] = metrics(sd, final.predict(sd.X))
final_i = load_default_model(informed=True)
res["stress_informed"] = {}
for name in STRESS:
    sd = Dataset.load(f"{D}/stress_{name}.npz")
    res["stress_informed"][name] = metrics(sd, final_i.predict(augment(sd.X, sd.meta["design_dt"].to_numpy())))
print("B done", round(time.time() - t0), flush=True)
fig, ax = plt.subplots(figsize=(7.4, 3.8))
labels = STRESS
a = [res["stress"][k]["macro_auroc"] for k in labels]
b = [res["stress"][k].get("top1_saving_captured", np.nan) for k in labels]
x = np.arange(len(labels)); w = 0.38
ax.bar(x - w/2, a, w, color=BLUE, label="Macro AUROC (cause detection)")
ax.bar(x + w/2, b, w, color=AMBER, label="Saving captured by fix #1")
ax.set_xticks(x); ax.set_xticklabels([l.replace("_", "\n") for l in labels], fontsize=8)
ax.set_ylim(0.5, 1.02); ax.legend(frameon=False, loc="lower left", fontsize=8)
ax.set_title("Robustness to distribution shift (fresh buildings)", loc="left", fontweight="bold")
fig.tight_layout(); fig.savefig(f"{FIG}/stress.png", dpi=160); plt.close(fig)

# ---- C: leave-one-type-out
res["leave_one_type_out"] = leave_one_group_out(ds, "building_type")
print("C done", round(time.time() - t0), flush=True)

# ---- D: held-out seasons
summer = [6, 7, 8]; winter = [12, 1, 2]
res["held_out_season"] = {}
for tag, months in (("summer_JJA", summer), ("winter_DJF", winter)):
    te = ds.meta["month"].isin(months).to_numpy()
    from deltat_doctor.models import Diagnoser
    m = Diagnoser(seed=0).fit(ds.X[~te], ds.Y[~te], ds.G[~te])
    res["held_out_season"][tag] = metrics(ds.subset(te), m.predict(ds.X[te]))
print("D done", round(time.time() - t0), flush=True)

json.dump(res, open(f"{OUT}/metrics.json", "w"), indent=2)

# ---- markdown summary
def row(name, m):
    pc = m["per_cause"]
    return (f"| {name} | {m['n']} | {m['macro_auroc']:.3f} | {m['any_fault_auroc']:.3f} | {m['macro_f1']:.3f} | "
            f"{m['exact_match']:.3f} | {m.get('top1_fix_gain_captured_blind', float('nan')):.3f} | "
            f"{m.get('top1_saving_captured', float('nan')):.3f} |")
H = ("| setting | n | macro AUROC | any-fault AUROC | macro F1 | exact match | fix #1 gain captured | fix #1 saving captured |\n"
     "|---|---|---|---|---|---|---|---|")
md = ["# Evaluation results (simulated buildings)\n",
      "All numbers come from the physics simulator in `deltat_doctor.sim`. They measure how well the tool "
      "recovers *simulated* faults. They are not field accuracy.\n",
      "## A. Held-out buildings (5-fold grouped CV)\n", H]
for name, m in res["cv_grouped_by_building"].items(): md.append(row(name, m))
md += ["\nPer-cause detail for the tool (held-out buildings):\n",
       "| cause | prevalence | AUROC | F1@0.5 | Brier | delta-T gain MAE (C) |", "|---|---|---|---|---|---|"]
mo = res["cv_grouped_by_building"]["ours_gbdt"]
for c in CAUSES:
    pc = mo["per_cause"][c]
    md.append(f"| {c} | {mo['prevalence'][c]:.2f} | {pc['auroc']:.3f} | {pc['f1_at_0.5']:.3f} | {pc['brier']:.3f} | {pc['gain_mae_c']:.2f} |")
md += ["\n## B. Distribution shift (model trained on the main set; fresh buildings)\n", H]
for k, m in res["stress"].items(): md.append(row(k, m))
md += ["\n## B2. Same stress sets, informed model (design delta-T supplied)\n", H]
for k, m in res["stress_informed"].items(): md.append(row(k, m))
md += ["\n## E. Healthy buildings by design delta-T band (held-out buildings)\n",
       "False alarm = any-cause probability of 0.5 or more on a building with no fault.\n",
       "| design delta-T (C) | n | healthy | blind: mean p(any) | blind: false alarms | informed: mean p(any) | informed: false alarms | blind any-fault AUROC | informed any-fault AUROC |",
       "|---|---|---|---|---|---|---|---|---|"]
for k, v in res["by_design_band"].items():
    b, i = v["blind"], v["informed"]
    md.append(f"| {k} | {v['n']} | {v['n_healthy']} | {b['mean_p_any_on_healthy']:.2f} | {b['false_alarm_rate_at_0.5']:.0%} | "
              f"{i['mean_p_any_on_healthy']:.2f} | {i['false_alarm_rate_at_0.5']:.0%} | {b['any_fault_auroc']:.3f} | {i['any_fault_auroc']:.3f} |")
md += ["\n## C. Leave one building type out\n", H]
for k, m in res["leave_one_type_out"].items(): md.append(row(f"held out: {k}", m))
md += ["\n## D. Held-out seasons\n", H]
for k, m in res["held_out_season"].items(): md.append(row(k, m))
md += ["\n## Constant-flow subtypes (recall at 0.5, held-out buildings)\n", "| subtype | n | mean prob | recall |", "|---|---|---|---|"]
for k, v in res["cv_constant_flow_subtypes"].items():
    md.append(f"| {k} | {v['n']} | {v['mean_prob']:.2f} | {v['recall_at_0.5']:.2f} |")
open(f"{OUT}/metrics.md", "w").write("\n".join(md) + "\n")
print("ALL DONE", round(time.time() - t0), flush=True)
