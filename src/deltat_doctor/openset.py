"""Open-set guard: is this building's behaviour like anything the model was trained on?

The per-feature box in models.py cannot see *joint* shift (each feature in range, the combination never seen). This guard
averages two complementary scores, each turned into its rank among the training scores:

* Mahalanobis distance (robustly scaled, Ledoit-Wolf shrunk covariance): sees global shape and correlation shift;
* mean distance to the 10 nearest training windows: sees local gaps and multi-modal training sets.

The threshold is the 95th percentile of the training scores (leave-self-out for the kNN part). A building is flagged when the
median of its window scores exceeds it. Measured on simulators in both directions: results/openset_v2.json, docs/MODEL_CARD.md.
"""
from __future__ import annotations

import numpy as np
from sklearn.covariance import LedoitWolf
from sklearn.neighbors import NearestNeighbors

K = 10


class OpenSetGuard:
    def __init__(self, quantile: float = 95.0):
        self.quantile = quantile

    def _z(self, X):
        return np.clip((np.atleast_2d(X) - self.mu) / self.scale, -8, 8)

    def _parts(self, Z, self_in_train=False):
        m = self.lw.mahalanobis(Z)
        d, _ = self.nn.kneighbors(Z, n_neighbors=K + 1 if self_in_train else K)
        return m, (d[:, 1:] if self_in_train else d).mean(1)

    def _rank(self, m, k):
        return (np.searchsorted(self.tm, m) / len(self.tm) + np.searchsorted(self.tk, k) / len(self.tk)) / 2

    def fit(self, X: np.ndarray) -> "OpenSetGuard":
        X = np.asarray(X, float)
        self.mu = np.median(X, axis=0)
        self.scale = np.subtract(*np.percentile(X, [75, 25], axis=0)) + 1e-6
        Z = self._z(X)
        self.lw = LedoitWolf().fit(Z)
        self.nn = NearestNeighbors(n_neighbors=K + 1).fit(Z)
        m, k = self._parts(Z, self_in_train=True)
        self.tm, self.tk = np.sort(m), np.sort(k)
        self.threshold = float(np.percentile(self._rank(m, k), self.quantile))
        return self

    def score(self, X: np.ndarray) -> np.ndarray:
        return self._rank(*self._parts(self._z(X)))

    def flag(self, X: np.ndarray) -> bool:
        """True when the median window score of this building exceeds the threshold."""
        return bool(np.median(self.score(X)) > self.threshold)
