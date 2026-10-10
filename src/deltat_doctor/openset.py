"""Open-set guard: is this building's behaviour like anything the model was trained on?

The per-feature box in models.py cannot see *joint* shift (each feature in range, the combination never seen). This guard
scores a window by its Mahalanobis distance (robustly scaled, shrunk covariance) from the training windows. The threshold is
the 95th percentile of the training scores. Measured on simulators (fit on A, test on B): see results/openset.json.
"""
from __future__ import annotations

import numpy as np
from sklearn.covariance import LedoitWolf


class OpenSetGuard:
    def __init__(self, quantile: float = 95.0):
        self.quantile = quantile

    def _z(self, X):
        return np.clip((np.atleast_2d(X) - self.mu) / self.scale, -8, 8)

    def fit(self, X: np.ndarray) -> "OpenSetGuard":
        X = np.asarray(X, float)
        self.mu = np.median(X, axis=0)
        self.scale = np.subtract(*np.percentile(X, [75, 25], axis=0)) + 1e-6
        self.lw = LedoitWolf().fit(self._z(X))
        self.threshold = float(np.percentile(self.score(X), self.quantile))
        return self

    def score(self, X: np.ndarray) -> np.ndarray:
        return self.lw.mahalanobis(self._z(X))

    def flag(self, X: np.ndarray) -> bool:
        """True when the median window score of this building exceeds the threshold."""
        return bool(np.median(self.score(X)) > self.threshold)
