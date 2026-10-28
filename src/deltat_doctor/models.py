"""Fault-signature classifier + counterfactual delta-T gain regressors."""
from __future__ import annotations

import warnings
from dataclasses import dataclass
from typing import Any

import joblib
import numpy as np
from sklearn.calibration import CalibratedClassifierCV
from sklearn.ensemble import HistGradientBoostingClassifier, HistGradientBoostingRegressor
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import GroupKFold
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

from . import CAUSES
from .features import FEATURE_NAMES


def _gbc(seed):
    return HistGradientBoostingClassifier(max_iter=250, learning_rate=0.06, max_leaf_nodes=15,
                                          min_samples_leaf=15, l2_regularization=1.0,
                                          random_state=seed)


def _gbr(seed):
    return HistGradientBoostingRegressor(max_iter=300, learning_rate=0.06, max_leaf_nodes=15,
                                         min_samples_leaf=15, l2_regularization=1.0,
                                         random_state=seed)


QUANTILES = (0.1, 0.5, 0.9)
ACTIVE_Q90_C = 0.2   # intervals whose upper end reaches the 'present' threshold are 'active' and get their own margin


def _gbq(seed, q):
    return HistGradientBoostingRegressor(loss="quantile", quantile=q, max_iter=200, learning_rate=0.06, max_leaf_nodes=15,
                                         min_samples_leaf=20, l2_regularization=1.0, random_state=seed)


@dataclass
class Prediction:
    prob: np.ndarray      # (n, 4) probability each cause is materially present
    gain: np.ndarray      # (n, 4) expected delta-T recovery if that cause is fixed, deg C
    p_any: np.ndarray     # (n,) probability any cause present
    gain_q: np.ndarray | None = None   # (n, 4, 3) 10th, 50th, 90th percentile of the recoverable delta-T (includes the chance it is 0)


class Diagnoser:
    """Four calibrated one-vs-rest classifiers, an any-fault detector and four gain regressors."""

    calibration: dict | None = None   # set by fleet calibration (calibrate.py)

    def __init__(self, seed: int = 0):
        self.seed = seed
        self.clf: dict[str, Any] = {}
        self.reg: dict[str, Any] = {}
        self.any_clf: Any = None
        self.regq: dict[str, Any] = {}
        self.q_margin = {c: {"active": 0.0, "inactive": 0.0} for c in CAUSES}
        self.feature_names = list(FEATURE_NAMES)
        self.trained_on = 0

    def _calibrated(self, X, y, groups):
        """Isotonic-calibrated booster. With groups, the inner calibration folds never split a building."""
        cv = 3
        if groups is not None:
            folds = list(GroupKFold(3).split(X, y, groups))
            if all(0 < y[te].sum() < len(te) and 0 < y[tr].sum() < len(tr) for tr, te in folds):
                cv = folds
        return CalibratedClassifierCV(_gbc(self.seed), method="isotonic", cv=cv).fit(X, y)

    def fit(self, X: np.ndarray, Y: np.ndarray, G: np.ndarray, groups: np.ndarray | None = None) -> "Diagnoser":
        """groups: building id per row. Used so that calibration folds are building-grouped (no leakage)."""
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            for k, c in enumerate(CAUSES):
                y = Y[:, k].astype(int)
                if y.sum() >= 10 and (1 - y).sum() >= 10:
                    self.clf[c] = self._calibrated(X, y, groups)
                else:
                    self.clf[c] = None
                self.reg[c] = _gbr(self.seed).fit(X, G[:, k])
                self.regq[c] = [_gbq(self.seed, q).fit(X, G[:, k]) for q in QUANTILES]
            y_any = (Y.sum(axis=1) > 0).astype(int)
            self.any_clf = self._calibrated(X, y_any, groups)
        self.trained_on = len(X)
        # Out-of-distribution guard: remember the 1st-99th percentile range of every shape feature, and how
        # many features fall outside it on a typical (95th percentile) training window.
        self.feat_lo = np.percentile(X, 1, axis=0)
        self.feat_hi = np.percentile(X, 99, axis=0)
        self.ood_threshold = int(np.percentile(self.ood_count(X), 95))
        # Healthy reference: distribution of every shape feature on windows with no material fault (for evidence statements).
        healthy = X[(Y.sum(axis=1) == 0)][:, :len(FEATURE_NAMES)]
        self.healthy_ref = ({n: [float(v) for v in np.percentile(healthy[:, i], [5, 25, 50, 75, 95])] for i, n in enumerate(FEATURE_NAMES)}
                            if len(healthy) >= 50 else {})
        # Evidence spec: per cause, the shape features whose median moves most (in healthy-spread units) when that cause is the only one present.
        self.evidence_spec = {}
        if len(healthy) >= 50:
            Xb = X[:, :len(FEATURE_NAMES)]
            hmed = np.median(healthy, axis=0)
            sc = np.maximum(np.subtract(*np.percentile(healthy, [95, 5], axis=0)) / 3.3, 0.25 * Xb.std(axis=0)) + 1e-9
            for k, c in enumerate(CAUSES):
                only = (Y[:, k] == 1) & (Y.sum(axis=1) == 1)
                if only.sum() < 30:
                    continue
                eff = (np.median(Xb[only], axis=0) - hmed) / sc
                order = [i for i in np.argsort(-np.abs(eff)) if abs(eff[i]) >= 0.5][:4]
                self.evidence_spec[c] = {"strength": float(np.abs(eff).max()),
                                         "features": [(FEATURE_NAMES[i], int(np.sign(eff[i])), float(eff[i])) for i in order]}
        from .openset import OpenSetGuard
        self.guard = OpenSetGuard().fit(X[:, :len(FEATURE_NAMES)])
        return self

    def _quantiles(self, X: np.ndarray, margin: bool = True) -> np.ndarray:
        out = np.zeros((len(X), len(CAUSES), len(QUANTILES)))
        for k, c in enumerate(CAUSES):
            qs = np.column_stack([r.predict(X) for r in self.regq[c]])
            qs = np.sort(np.clip(qs, 0.0, None), axis=1)
            if margin:
                mg = self.q_margin.get(c, {"active": 0.0, "inactive": 0.0})
                act = qs[:, -1] >= ACTIVE_Q90_C
                m = np.where(act, mg["active"], mg["inactive"])
                qs[:, 0] = np.clip(qs[:, 0] - m, 0.0, None)
                qs[:, -1] = qs[:, -1] + m
            out[:, k, :] = qs
        return out

    def fit_quantile_margin(self, X: np.ndarray, G: np.ndarray, groups: np.ndarray, target: float = 0.8, n_splits: int = 5):
        """Conformalised quantile regression: widen the 10-90 interval by the amount that makes out-of-fold
        coverage reach `target`, separately per cause. Out-of-fold means whole buildings are held out."""
        oof = np.zeros((len(X), len(CAUSES), len(QUANTILES)))
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            for tr, te in GroupKFold(n_splits).split(X, G[:, 0], groups):
                for k, c in enumerate(CAUSES):
                    qs = np.column_stack([_gbq(self.seed, q).fit(X[tr], G[tr, k]).predict(X[te]) for q in QUANTILES])
                    oof[te, k, :] = np.sort(np.clip(qs, 0.0, None), axis=1)
        for k, c in enumerate(CAUSES):
            score = np.maximum(oof[:, k, 0] - G[:, k], G[:, k] - oof[:, k, -1])
            act = oof[:, k, -1] >= ACTIVE_Q90_C
            for name, sel in (("active", act), ("inactive", ~act)):
                sc = score[sel]
                if len(sc) < 30:
                    self.q_margin[c][name] = 0.0
                    continue
                level = min(1.0, np.ceil((len(sc) + 1) * target) / len(sc))
                self.q_margin[c][name] = float(max(np.quantile(sc, level), 0.0))
        return self

    def ood_count(self, X: np.ndarray) -> np.ndarray:
        """Per row: how many of the shape features lie outside the range seen in training."""
        X = np.atleast_2d(X)
        return ((X < self.feat_lo) | (X > self.feat_hi)).sum(axis=1)

    def predict(self, X: np.ndarray) -> Prediction:
        X = np.atleast_2d(X)
        prob = np.zeros((len(X), len(CAUSES)))
        gain = np.zeros_like(prob)
        for k, c in enumerate(CAUSES):
            if self.clf[c] is not None:
                prob[:, k] = self.clf[c].predict_proba(X)[:, 1]
            gain[:, k] = np.clip(self.reg[c].predict(X), 0.0, None)
        p_any = self.any_clf.predict_proba(X)[:, 1]
        gq = self._quantiles(X) if self.regq else None
        return Prediction(prob, gain, p_any, gq)

    def save(self, path: str) -> None:
        joblib.dump(self, path, compress=3)

    @staticmethod
    def load(path: str) -> "Diagnoser":
        return joblib.load(path)


class LogisticBaseline:
    """Simple linear baseline using the same features."""

    def __init__(self, seed: int = 0):
        self.seed = seed
        self.clf: dict[str, Any] = {}
        self.reg: dict[str, Any] = {}

    def fit(self, X, Y, G):
        from sklearn.linear_model import Ridge
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            for k, c in enumerate(CAUSES):
                self.clf[c] = make_pipeline(StandardScaler(), LogisticRegression(C=0.5, max_iter=2000)).fit(X, Y[:, k].astype(int))
                self.reg[c] = make_pipeline(StandardScaler(), Ridge(alpha=5.0)).fit(X, G[:, k])
            self.any_clf = make_pipeline(StandardScaler(), LogisticRegression(C=0.5, max_iter=2000)).fit(X, (Y.sum(1) > 0).astype(int))
        return self

    def predict(self, X):
        X = np.atleast_2d(X)
        prob = np.column_stack([self.clf[c].predict_proba(X)[:, 1] for c in CAUSES])
        gain = np.column_stack([np.clip(self.reg[c].predict(X), 0, None) for c in CAUSES])
        return Prediction(prob, gain, self.any_clf.predict_proba(X)[:, 1])


class PriorBaseline:
    """Predicts the training prevalence for every sample (no information)."""

    def fit(self, X, Y, G):
        self.p = Y.mean(0)
        self.g = G.mean(0)
        self.pa = float((Y.sum(1) > 0).mean())
        return self

    def predict(self, X):
        n = len(np.atleast_2d(X))
        return Prediction(np.tile(self.p, (n, 1)), np.tile(self.g, (n, 1)), np.full(n, self.pa))


class ExpertRules:
    """Hand-written heuristics an engineer might apply by eye to the same summary
    features (no training). Scores are crude 0/1 votes; used as a sanity baseline."""

    def fit(self, X, Y, G):
        return self

    def predict(self, X):
        X = np.atleast_2d(X)
        ix = {n: i for i, n in enumerate(FEATURE_NAMES)}
        dt = X[:, ix["dt_period"]]
        low_share = X[:, ix["flow_lowload_share"]]
        corr = X[:, ix["flow_load_corr"]]
        icpt = X[:, ix["flow_intercept_ratio"]]
        hi_mid = X[:, ix["dt_hi_minus_mid"]]
        p = np.zeros((len(X), 4))
        p[:, 0] = (hi_mid < -1.0) & (dt < 9.5)
        p[:, 1] = (low_share > 0.08) & (icpt > 0.15)
        p[:, 2] = (corr < 0.5) | (icpt > 0.5)
        p[:, 3] = (dt < 9.0) & (hi_mid > -0.5) & (icpt < 0.3)
        gain = p * np.clip(9.5 - dt, 0, None)[:, None]
        return Prediction(p.astype(float), gain, (p.sum(1) > 0).astype(float))
