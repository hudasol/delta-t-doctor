"""Reference models used to judge the shipped diagnoser.

Every model takes the same 42 shape features and exposes ``fit(X, Y, G)`` and ``predict(X)``, returning a
:class:`~deltat_doctor.models.Prediction`. Hyperparameters are fixed here and are never tuned on a test fold
(see docs/research/BASELINES.md). The older ``PriorBaseline``, ``ExpertRules`` and ``LogisticBaseline`` stay in
``models.py`` and are re-exported by :data:`BASELINES`.
"""
from __future__ import annotations

import warnings

import numpy as np
from sklearn.ensemble import (HistGradientBoostingClassifier, HistGradientBoostingRegressor, RandomForestClassifier,
                              RandomForestRegressor)
from sklearn.linear_model import LogisticRegression, Ridge
from sklearn.metrics import roc_auc_score
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.tree import DecisionTreeClassifier, DecisionTreeRegressor

from . import CAUSES
from .features import FEATURE_NAMES
from .models import ExpertRules, LogisticBaseline, Prediction, PriorBaseline

_DT = FEATURE_NAMES.index("dt_period")


class _PerCause:
    """One classifier and one gain regressor per cause, plus an any-fault classifier."""

    columns: list[int] | None = None   # feature subset; None means all

    def __init__(self, seed: int = 0):
        self.seed = seed

    def _clf(self):
        raise NotImplementedError

    def _reg(self):
        raise NotImplementedError

    def _x(self, X):
        X = np.atleast_2d(np.asarray(X, float))
        return X if self.columns is None else X[:, self.columns]

    def fit(self, X, Y, G):
        X = self._x(X)
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            self.clf = [self._clf().fit(X, Y[:, k].astype(int)) for k in range(len(CAUSES))]
            self.reg = [self._reg().fit(X, G[:, k]) for k in range(len(CAUSES))]
            self.any = self._clf().fit(X, (Y.sum(1) > 0).astype(int))
        return self

    def predict(self, X):
        X = self._x(X)
        prob = np.column_stack([m.predict_proba(X)[:, 1] for m in self.clf])
        gain = np.column_stack([np.clip(m.predict(X), 0, None) for m in self.reg])
        return Prediction(prob, gain, self.any.predict_proba(X)[:, 1])


class DeltaTOnly(_PerCause):
    """The number a billing dashboard already has: flow weighted delta T and nothing else."""

    columns = [_DT]

    def _clf(self):
        return make_pipeline(StandardScaler(), LogisticRegression(C=0.5, max_iter=1000))

    def _reg(self):
        return make_pipeline(StandardScaler(), Ridge(alpha=5.0))


class ShallowTree(_PerCause):
    """Depth 3 decision tree per cause: rules a person can read."""

    def _clf(self):
        return DecisionTreeClassifier(max_depth=3, min_samples_leaf=20, random_state=self.seed)

    def _reg(self):
        return DecisionTreeRegressor(max_depth=3, min_samples_leaf=20, random_state=self.seed)


class Forest(_PerCause):
    def _clf(self):
        return RandomForestClassifier(n_estimators=300, min_samples_leaf=3, max_features="sqrt", n_jobs=2, random_state=self.seed)

    def _reg(self):
        return RandomForestRegressor(n_estimators=200, min_samples_leaf=5, max_features=0.33, n_jobs=2, random_state=self.seed)


class PlainBoosting(_PerCause):
    """The shipped model's learner without calibration, quantile heads or ensembling over folds."""

    def _clf(self):
        return HistGradientBoostingClassifier(max_iter=200, learning_rate=0.06, max_leaf_nodes=15, min_samples_leaf=20,
                                              l2_regularization=1.0, random_state=self.seed)

    def _reg(self):
        return HistGradientBoostingRegressor(max_iter=200, learning_rate=0.06, max_leaf_nodes=15, min_samples_leaf=20,
                                             l2_regularization=1.0, random_state=self.seed)


class FittedStumps:
    """A fitted version of "rules of thumb": for each cause, the one feature and threshold with the best training AUROC.

    The probability on each side of the threshold is the training rate on that side, so the output is a calibrated step.
    """

    N_THRESHOLDS = 200

    def __init__(self, seed: int = 0):
        self.seed = seed

    @staticmethod
    def _best_split(X, y):
        best = (0.5, 0, 0.0, 1)  # auroc, feature, threshold, sign
        if y.sum() == 0 or y.sum() == len(y):
            return best
        for j in range(X.shape[1]):
            auc = roc_auc_score(y, X[:, j])
            sign = 1 if auc >= 0.5 else -1
            score = max(auc, 1 - auc)
            if score > best[0]:
                qs = np.unique(np.percentile(X[:, j], np.linspace(1, 99, FittedStumps.N_THRESHOLDS)))
                # threshold with the best balanced accuracy on the training rows
                bal = [((sign * (X[:, j] - t) > 0) & (y == 1)).sum() / y.sum() + ((sign * (X[:, j] - t) <= 0) & (y == 0)).sum() / (len(y) - y.sum())
                       for t in qs]
                best = (score, j, float(qs[int(np.argmax(bal))]), sign)
        return best

    def _fit_one(self, X, y, g):
        _, j, t, s = self._best_split(X, y)
        above = s * (X[:, j] - t) > 0
        smooth = lambda a, n: (a.sum() + 0.5) / (n + 1.0)
        p_hi = smooth(y[above], above.sum()) if above.any() else float(y.mean())
        p_lo = smooth(y[~above], (~above).sum()) if (~above).any() else float(y.mean())
        g_hi = float(g[above].mean()) if above.any() else 0.0
        g_lo = float(g[~above].mean()) if (~above).any() else 0.0
        return dict(j=j, t=t, s=s, p=(p_lo, p_hi), g=(g_lo, g_hi))

    def fit(self, X, Y, G):
        X = np.asarray(X, float)
        self.rules = [self._fit_one(X, Y[:, k].astype(int), G[:, k]) for k in range(len(CAUSES))]
        self.any_rule = self._fit_one(X, (Y.sum(1) > 0).astype(int), G.sum(1))
        return self

    @staticmethod
    def _apply(rule, X, key):
        hi = (rule["s"] * (X[:, rule["j"]] - rule["t"]) > 0).astype(int)
        return np.where(hi == 1, rule[key][1], rule[key][0])

    def predict(self, X):
        X = np.atleast_2d(np.asarray(X, float))
        prob = np.column_stack([self._apply(r, X, "p") for r in self.rules])
        gain = np.column_stack([self._apply(r, X, "g") for r in self.rules])
        return Prediction(prob, gain, self._apply(self.any_rule, X, "p"))

    def describe(self) -> list[str]:
        """Human readable form of the fitted rules, for the docs."""
        return [f"{c}: {FEATURE_NAMES[r['j']]} {'>' if r['s'] > 0 else '<'} {r['t']:.3g}" for c, r in zip(CAUSES, self.rules)]


BASELINES = {
    "prior": PriorBaseline,
    "rules_v1": ExpertRules,
    "delta_t_only": DeltaTOnly,
    "stumps": FittedStumps,
    "tree3": ShallowTree,
    "logistic": LogisticBaseline,
    "rf": Forest,
    "hgb": PlainBoosting,
}
