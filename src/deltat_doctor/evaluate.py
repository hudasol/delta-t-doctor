"""Evaluation metrics and protocols (held-out buildings, stress shifts, ablations)."""
from __future__ import annotations

import numpy as np
from sklearn.metrics import average_precision_score, brier_score_loss, f1_score, roc_auc_score
from sklearn.model_selection import GroupKFold

from . import CAUSES
from .models import Diagnoser, ExpertRules, LogisticBaseline, Prediction, PriorBaseline
from .penalty import ContractTerms, saving_from_gain
from .sim.dataset import Dataset


def _safe_auc(y, p):
    return float(roc_auc_score(y, p)) if 0 < y.sum() < len(y) else float("nan")


def metrics(ds: Dataset, pred: Prediction) -> dict:
    Y, G = ds.Y, ds.G
    out: dict = {"n": int(len(Y)), "prevalence": {c: float(Y[:, k].mean()) for k, c in enumerate(CAUSES)}}
    per = {}
    for k, c in enumerate(CAUSES):
        y, p = Y[:, k].astype(int), pred.prob[:, k]
        per[c] = {
            "auroc": _safe_auc(y, p),
            "avg_precision": float(average_precision_score(y, p)) if y.sum() else float("nan"),
            "f1_at_0.5": float(f1_score(y, (p >= 0.5).astype(int), zero_division=0)),
            "brier": float(brier_score_loss(y, p)),
            "gain_mae_c": float(np.abs(pred.gain[:, k] - G[:, k]).mean()),
            "gain_mae_c_when_present": float(np.abs(pred.gain[y == 1, k] - G[y == 1, k]).mean()) if y.sum() else float("nan"),
        }
    out["per_cause"] = per
    y_any = (Y.sum(1) > 0).astype(int)
    out["any_fault_auroc"] = _safe_auc(y_any, pred.p_any)
    out["macro_auroc"] = float(np.nanmean([per[c]["auroc"] for c in CAUSES]))
    out["macro_f1"] = float(np.mean([per[c]["f1_at_0.5"] for c in CAUSES]))
    out["exact_match"] = float(np.mean(((pred.prob >= 0.5).astype(int) == Y.astype(int)).all(1)))

    # decision quality: does following the tool's #1 recommendation recover the most delta-T?
    has = Y.sum(1) > 0
    if has.any():
        Gp = np.where(Y == 1, pred.gain, -1.0)[has]
        Gt = np.where(Y == 1, G, -1.0)[has]
        pick = Gp.argmax(1)
        best = Gt.argmax(1)
        out["top1_fix_accuracy"] = float((pick == best).mean())
        got = Gt[np.arange(len(pick)), pick]
        got = np.where(got < 0, 0.0, got)
        bestv = Gt[np.arange(len(best)), best]
        out["top1_fix_gain_captured"] = float(got.sum() / max(bestv.sum(), 1e-9))
        # same, but ranking ALL four causes by predicted gain (not just those truly present)
        pick_all = pred.gain[has].argmax(1)
        got_all = G[has][np.arange(len(pick_all)), pick_all]
        out["top1_fix_gain_captured_blind"] = float(got_all.sum() / max(bestv.sum(), 1e-9))
        # saving captured under the penalty rule (rt_hr cancels in the ratio)
        terms = ContractTerms()
        dt = ds.meta["dt_actual"].to_numpy()[has]
        s_pick = np.array([saving_from_gain(dt[i], got_all[i], 1.0, terms) for i in range(len(dt))])
        s_best = np.array([saving_from_gain(dt[i], bestv[i], 1.0, terms) for i in range(len(dt))])
        if s_best.sum() > 0:
            out["top1_saving_captured"] = float(s_pick.sum() / s_best.sum())
    return out


MODELS = {
    "ours_gbdt": lambda: Diagnoser(seed=0),
    "logistic": lambda: LogisticBaseline(),
    "expert_rules": lambda: ExpertRules(),
    "prior": lambda: PriorBaseline(),
}


def cross_validate(ds: Dataset, n_splits: int = 5, models: dict | None = None):
    """Group K-fold on building id: no building appears in both train and test."""
    models = models or MODELS
    groups = ds.meta["building_id"].to_numpy()
    gkf = GroupKFold(n_splits=n_splits)
    preds = {name: Prediction(np.zeros_like(ds.Y), np.zeros_like(ds.G), np.zeros(len(ds.Y))) for name in models}
    for tr, te in gkf.split(ds.X, ds.Y, groups):
        for name, mk in models.items():
            m = mk().fit(ds.X[tr], ds.Y[tr], ds.G[tr], **({"groups": groups[tr]} if isinstance(mk(), Diagnoser) else {}))
            p = m.predict(ds.X[te])
            preds[name].prob[te], preds[name].gain[te], preds[name].p_any[te] = p.prob, p.gain, p.p_any
            if p.gain_q is not None:
                if preds[name].gain_q is None:
                    preds[name].gain_q = np.zeros((len(ds.Y),) + p.gain_q.shape[1:])
                preds[name].gain_q[te] = p.gain_q
    return {name: (metrics(ds, p), p) for name, p in preds.items()}


def leave_one_group_out(ds: Dataset, key: str, values=None):
    """Train without one value of meta[key], test on it."""
    values = values if values is not None else sorted(ds.meta[key].unique())
    res = {}
    for v in values:
        te = (ds.meta[key] == v).to_numpy() if not isinstance(v, (list, tuple)) else ds.meta[key].isin(v).to_numpy()
        tr = ~te
        m = Diagnoser(seed=0).fit(ds.X[tr], ds.Y[tr], ds.G[tr], groups=ds.meta["building_id"].to_numpy()[tr])
        res[str(v)] = metrics(ds.subset(te), m.predict(ds.X[te]))
    return res


def confusion_single_cause(ds: Dataset, pred: Prediction) -> dict:
    """Mean predicted probability, by true cause, for single-cause (or healthy) samples."""
    inj = ds.meta["injected"].to_numpy()
    rows = {}
    for name in ["none"] + list(CAUSES):
        sel = inj == name
        if name != "none":
            # only count samples where the injected cause was material
            sel = sel & (ds.Y[:, CAUSES.index(name)] == 1)
        if sel.sum() >= 5:
            rows[name] = {"n": int(sel.sum()), **{c: float(pred.prob[sel, k].mean()) for k, c in enumerate(CAUSES)}}
    return rows


def subtype_recall(ds: Dataset, pred: Prediction) -> dict:
    k = CAUSES.index("constant_flow")
    out = {}
    for sub in ("three_way", "stuck_open", "mixed"):
        sel = (ds.meta["cf_subtype"].fillna("") == sub).to_numpy() & (ds.Y[:, k] == 1)
        if sel.sum() >= 5:
            out[sub] = {"n": int(sel.sum()), "mean_prob": float(pred.prob[sel, k].mean()),
                        "recall_at_0.5": float((pred.prob[sel, k] >= 0.5).mean())}
    return out


def bootstrap_ci(ds: Dataset, preds: dict, n_boot: int = 200, seed: int = 0, ref: str = "ours_gbdt") -> dict:
    """Building-level bootstrap (resample whole buildings with replacement) of macro AUROC and any-fault AUROC.

    Returns the 95% interval for each model and the paired difference ref - other (same resamples), so a gap
    between two models is judged against the same sampling noise.
    """
    rng = np.random.default_rng(seed)
    bid = ds.meta["building_id"].to_numpy()
    ids = np.unique(bid)
    rows_of = {b: np.flatnonzero(bid == b) for b in ids}
    names = list(preds)
    draws = {n: {"macro_auroc": [], "any_fault_auroc": []} for n in names}
    for _ in range(n_boot):
        pick = rng.choice(ids, size=len(ids), replace=True)
        idx = np.concatenate([rows_of[b] for b in pick])
        Y = ds.Y[idx]
        y_any = (Y.sum(1) > 0).astype(int)
        for n in names:
            p = preds[n]
            macro = np.nanmean([_safe_auc(Y[:, k].astype(int), p.prob[idx, k]) for k in range(Y.shape[1])])
            draws[n]["macro_auroc"].append(macro)
            draws[n]["any_fault_auroc"].append(_safe_auc(y_any, p.p_any[idx]))
    q = lambda a: [float(np.percentile(a, 2.5)), float(np.percentile(a, 97.5))]
    out = {"n_boot": n_boot, "resampled": "buildings", "models": {}, "paired_vs_" + ref: {}}
    for n in names:
        out["models"][n] = {k: {"ci95": q(v), "mean": float(np.mean(v))} for k, v in draws[n].items()}
        if n != ref and ref in draws:
            out["paired_vs_" + ref][n] = {
                k: {"diff_ci95": q(np.array(draws[ref][k]) - np.array(draws[n][k])),
                    "diff_mean": float(np.mean(np.array(draws[ref][k]) - np.array(draws[n][k])))}
                for k in draws[n]}
    return out


def expected_calibration_error(ds: Dataset, pred: Prediction, bins: int = 10) -> float:
    """Pooled ECE over all cause probabilities (equal width bins)."""
    p, y = pred.prob.ravel(), ds.Y.ravel()
    idx = np.minimum((p * bins).astype(int), bins - 1)
    err = sum(abs(p[idx == b].mean() - y[idx == b].mean()) * (idx == b).sum() for b in range(bins) if (idx == b).any())
    return float(err / len(p))


def top1_precision(ds: Dataset, pred: Prediction) -> float:
    """Share of faulty windows whose first recommendation (largest probability x predicted gain) is a cause that is really present."""
    has = ds.Y.sum(1) > 0
    if not has.any():
        return float("nan")
    pick = (pred.prob * pred.gain)[has].argmax(1)
    return float(ds.Y[has][np.arange(has.sum()), pick].mean())


def healthy_false_alarm(ds: Dataset, pred: Prediction, threshold: float = 0.5) -> float:
    """Share of windows with no cause present that the model calls faulty (p_any at or above the threshold)."""
    healthy = ds.Y.sum(1) == 0
    return float((pred.p_any[healthy] >= threshold).mean()) if healthy.any() else float("nan")


def summary_row(ds: Dataset, pred: Prediction) -> dict:
    """The compact set of numbers the baseline tables report."""
    m = metrics(ds, pred)
    present = ds.Y == 1
    return {
        "macro_auroc": m["macro_auroc"],
        "any_fault_auroc": m["any_fault_auroc"],
        "brier": float(np.mean([m["per_cause"][c]["brier"] for c in CAUSES])),
        "ece": expected_calibration_error(ds, pred),
        "healthy_false_alarm": healthy_false_alarm(ds, pred),
        "top1_precision": top1_precision(ds, pred),
        "gain_mae_when_present": float(np.abs(pred.gain - ds.G)[present].mean()),
        "top1_fix_gain_captured_blind": m.get("top1_fix_gain_captured_blind", float("nan")),
        "per_cause_auroc": {c: m["per_cause"][c]["auroc"] for c in CAUSES},
    }
