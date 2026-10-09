"""Fault-signature classifier + counterfactual delta-T gain regressors."""
from __future__ import annotations

import warnings
from dataclasses import dataclass

import joblib
import numpy as np
from sklearn.calibration import CalibratedClassifierCV
from sklearn.ensemble import HistGradientBoostingClassifier, HistGradientBoostingRegressor
from sklearn.linear_model import LogisticRegression
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


@dataclass
class Prediction:
    prob: np.ndarray      # (n, 4) probability each cause is materially present
    gain: np.ndarray      # (n, 4) expected delta-T recovery if that cause is fixed, deg C
    p_any: np.ndarray     # (n,) probability any cause present


class Diagnoser:
    """Four calibrated one-vs-rest classifiers, an any-fault detector and four gain regressors."""

    def __init__(self, seed: int = 0):
        self.seed = seed
        self.clf = {}
        self.reg = {}
        self.any_clf = None
        self.feature_names = list(FEATURE_NAMES)
        self.trained_on = 0

    def fit(self, X: np.ndarray, Y: np.ndarray, G: np.ndarray) -> "Diagnoser":
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            for k, c in enumerate(CAUSES):
                y = Y[:, k].astype(int)
                if y.sum() >= 10 and (1 - y).sum() >= 10:
                    self.clf[c] = CalibratedClassifierCV(_gbc(self.seed), method="isotonic", cv=3).fit(X, y)
                else:
                    self.clf[c] = None
                self.reg[c] = _gbr(self.seed).fit(X, G[:, k])
            y_any = (Y.sum(axis=1) > 0).astype(int)
            self.any_clf = CalibratedClassifierCV(_gbc(self.seed), method="isotonic", cv=3).fit(X, y_any)
        self.trained_on = len(X)
        # Out-of-distribution guard: remember the 1st-99th percentile range of every shape feature, and how
        # many features fall outside it on a typical (95th percentile) training window.
        n = len(FEATURE_NAMES)
        self.feat_lo = np.percentile(X[:, :n], 1, axis=0)
        self.feat_hi = np.percentile(X[:, :n], 99, axis=0)
        self.ood_threshold = int(np.percentile(self.ood_count(X[:, :n]), 95))
        return self

    def ood_count(self, X: np.ndarray) -> np.ndarray:
        """Per row: how many of the shape features lie outside the range seen in training."""
        X = np.atleast_2d(X)[:, : len(self.feat_lo)]
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
        return Prediction(prob, gain, p_any)

    def save(self, path: str) -> None:
        joblib.dump(self, path, compress=3)

    @staticmethod
    def load(path: str) -> "Diagnoser":
        return joblib.load(path)


class LogisticBaseline:
    """Simple linear baseline using the same features."""

    def __init__(self, seed: int = 0):
        self.seed = seed
        self.clf = {}
        self.reg = {}

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
