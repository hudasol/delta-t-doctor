"""Rewrite the results table in README.md from results/metrics.json so the README never drifts from the evidence."""
import json, re, sys
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
s = open("README.md").read()
n_s, n_b = cv["ours_gbdt"]["n"], len(set(range(0)))  # n_b filled from model card below
card = json.load(open("src/deltat_doctor/assets/model_card.json"))
head = f"All simulated, {card['trained_on_samples']} samples across {card['n_buildings']} buildings, 5-fold CV grouped by building. Intervals resample whole buildings."
s = re.sub(r"<!--results:start-->.*<!--results:end-->", f"<!--results:start-->\n{head}\n\n{block}\n<!--results:end-->", s, flags=re.S)
open("README.md", "w").write(s)
print(block)
