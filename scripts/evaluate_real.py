"""Score delta-t-doctor against site-inspection labels on real buildings.

usage: python scripts/evaluate_real.py manifest.csv [--out results/real_eval] [--boot 2000] [--model fleet_model.joblib]

manifest.csv columns (one row per building; see examples/real_manifest_template.csv):
  building_id   any string
  file          path to the meter export (relative to the manifest)
  causes        semicolon-separated inspected causes: fouling;passing_valves;constant_flow;overflow;other;none
  complete      yes if the inspection ruled out every cause not listed (needed for false-alarm and confidently-wrong counts)
  design_dt     optional design delta-T in C (switches to the informed model)
  min_dt        optional contract minimum delta-T (default 8.9)

Reports (with building-level bootstrap intervals): abstention rate, top-1 / top-2 agreement on single-cause buildings, per-cause
AUROC, Brier score and reliability bins, healthy false-alarm rate, confidently-wrong count (p > 0.8 on a ruled-out cause), and
the pilot success criteria from docs/PILOT.md. Nothing here is a claim about accuracy until it is run on real labelled data; with
fewer than 10 buildings the script says the result is not interpretable.
"""
import argparse, json, os, sys
import numpy as np
import pandas as pd

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
from deltat_doctor import CAUSES
from deltat_doctor.diagnose import diagnose_frame
from deltat_doctor.io import read_table
from deltat_doctor.penalty import ContractTerms

CONF = 0.8


def run_building(row, base, model=None):
    path = os.path.join(base, row["file"])
    with open(path, "rb") as fh:
        table = read_table(fh.read(), path)
    dd = row.get("design_dt")
    dd = float(dd) if pd.notna(dd) and str(dd).strip() else None
    md = row.get("min_dt")
    terms = ContractTerms(float(md) if pd.notna(md) and str(md).strip() else 8.9, 10.0, 1.0)
    rep = diagnose_frame(table, terms, model=model, design_delta_t_c=dd).to_dict()
    probs = {c: 0.0 for c in CAUSES}
    for f in rep["findings"]:
        probs[f["cause"]] = float(f["probability"])
    ranked = [f["cause"] for f in rep["findings"]]
    return {"abstained": bool(rep["abstained"]), "probs": probs, "ranked": ranked, "p_any": float(rep["p_any_cause"]),
            "guard": rep.get("guard", {})}


def auc(y, s):
    y, s = np.asarray(y), np.asarray(s, float)
    if y.sum() == 0 or y.sum() == len(y):
        return float("nan")
    from sklearn.metrics import roc_auc_score
    return float(roc_auc_score(y, s))


def summarise(rows):
    """rows: list of dicts with labels/probs/abstained. Returns metric dict."""
    n = len(rows)
    ans = [r for r in rows if not r["abstained"]]
    out = {"n_buildings": n, "abstention_rate": 1 - len(ans) / n if n else float("nan")}
    single = [r for r in ans if len(r["labels"] & set(CAUSES)) == 1 and not (r["labels"] - set(CAUSES) - {"other"})]
    out["n_single_cause_answered"] = len(single)
    if single:
        out["top1"] = float(np.mean([bool(r["ranked"]) and r["ranked"][0] in r["labels"] for r in single]))
        out["top2"] = float(np.mean([bool(set(r["ranked"][:2]) & r["labels"]) for r in single]))
    comp = [r for r in ans if r["complete"]]
    out["n_complete_answered"] = len(comp)
    hl = [r for r in comp if r["labels"] <= {"none"}]
    out["healthy_false_alarm"] = float(np.mean([r["p_any"] >= 0.5 for r in hl])) if hl else float("nan")
    out["confidently_wrong_buildings"] = int(sum(any(r["probs"][c] > CONF and c not in r["labels"] for c in CAUSES) for r in comp))
    out["per_cause_auroc"] = {c: auc([c in r["labels"] for r in comp], [r["probs"][c] for r in comp]) for c in CAUSES}
    pairs = [(float(r["probs"][c]), float(c in r["labels"])) for r in comp for c in CAUSES]
    if pairs:
        p, y = np.array(pairs).T
        out["brier"] = float(np.mean((p - y) ** 2))
        bins = np.digitize(p, [0.2, 0.4, 0.6, 0.8])
        out["reliability"] = [{"bin": int(b), "n": int((bins == b).sum()), "mean_p": float(p[bins == b].mean()), "observed": float(y[bins == b].mean())}
                              for b in range(5) if (bins == b).any()]
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("manifest")
    ap.add_argument("--out", default="results/real_eval")
    ap.add_argument("--boot", type=int, default=2000)
    ap.add_argument("--model", default=None, help="a fleet calibrated model; verified against its .card.json when the card exists, otherwise loaded with a warning")
    a = ap.parse_args()
    model = None
    if a.model:
        from deltat_doctor.diagnose import load_default_model
        model = load_default_model(a.model)
    man = pd.read_csv(a.manifest, dtype=str).fillna("")
    base = os.path.dirname(os.path.abspath(a.manifest))
    rows = []
    for _, m in man.iterrows():
        r = run_building(m, base, model)
        r["id"] = m["building_id"]
        r["labels"] = {x.strip() for x in m["causes"].split(";") if x.strip()}
        r["complete"] = m.get("complete", "").strip().lower() in ("yes", "y", "true", "1")
        rows.append(r)
        print(r["id"], "abstained" if r["abstained"] else "ranked " + ",".join(r["ranked"][:2]), flush=True)
    res = summarise(rows)
    rng = np.random.default_rng(0)
    boots = []
    for _ in range(a.boot if len(rows) >= 10 else 0):
        idx = rng.integers(0, len(rows), len(rows))
        boots.append(summarise([rows[i] for i in idx]))
    ci = {}
    for k in ("abstention_rate", "top1", "top2", "healthy_false_alarm", "brier"):
        v = [b[k] for b in boots if k in b and np.isfinite(b[k])]
        if v:
            ci[k] = [float(np.percentile(v, 2.5)), float(np.percentile(v, 97.5))]
    res["ci95_building_bootstrap"] = ci
    res["interpretable"] = len(rows) >= 10
    res["pilot_criteria"] = {
        "top2_at_least_0.70": bool(res.get("top2", 0) >= 0.70),
        "confidently_wrong_at_most_1_in_10": bool(res["confidently_wrong_buildings"] <= max(1, len(rows) // 10)),
    }
    if not res["interpretable"]:
        res["pilot_criteria"] = None
        res["warning"] = "Fewer than 10 buildings: no intervals computed and these numbers must not be quoted as accuracy."
    os.makedirs(a.out, exist_ok=True)
    json.dump({"summary": res, "buildings": [{k: (sorted(v) if isinstance(v, set) else v) for k, v in r.items()} for r in rows]},
              open(os.path.join(a.out, "real_eval.json"), "w"), indent=2, default=float)
    print(json.dumps(res, indent=2, default=float))


if __name__ == "__main__":
    main()
