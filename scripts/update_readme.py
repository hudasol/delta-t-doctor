"""Rewrite the results table in README.md from results/metrics.json so the README never drifts from the evidence."""
import json, re
m = json.load(open("results/metrics.json"))
cv, bs = m["cv_grouped_by_building"], m.get("bootstrap", {}).get("models", {})
rows = [("**delta-t-doctor (blind)**", "ours_gbdt"), ("delta-t-doctor (informed, design delta-T given)", "ours_informed"),
        ("logistic regression", "logistic"), ("hand-written expert rules", "expert_rules"), ("class prior", "prior")]
def ci(k, key):
    b = bs.get(k, {}).get(key)
    return f" [{b['ci95'][0]:.3f}, {b['ci95'][1]:.3f}]" if b else ""
lines = ["| model | macro AUROC (95% CI) | any-fault AUROC | macro F1 | fix #1 gain captured* |", "|---|---|---|---|---|"]
for label, k in rows:
    x = cv[k]
    lines.append(f"| {label} | {x['macro_auroc']:.3f}{ci(k, 'macro_auroc')} | {x['any_fault_auroc']:.3f} | {x['macro_f1']:.3f} | {x.get('top1_fix_gain_captured_blind', float('nan')):.3f} |")
block = "\n".join(lines)
s = open("README.md", encoding="utf-8").read()
n_s = cv["ours_gbdt"]["n"]
# These rows are simulator A only: models trained and tested on A (5-fold CV grouped by building), not the shipped A + B model.
head = (f"All simulated, simulator A only: {n_s} windows across {n_s // 10} buildings, models trained and tested on A with 5-fold CV grouped "
        f"by building (the shipped model is trained on A and B; on B it scores 0.877 in the same protocol, results/cross_simulator.md). "
        f"Intervals resample whole buildings.")
s = re.sub(r"<!--results:start-->.*<!--results:end-->", f"<!--results:start-->\n{head}\n\n{block}\n<!--results:end-->", s, flags=re.S)
open("README.md", "w", encoding="utf-8", newline=chr(10)).write(s)
print(block)
