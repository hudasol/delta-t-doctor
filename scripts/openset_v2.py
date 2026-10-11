"""Open-set guard v2: threshold-free comparison of detectors, in both directions. Writes results/openset_v2.json.
For each fit world, scores held-out in-world buildings (negatives) and the other physics (positives).
Metrics: AUROC of 'other world' vs 'in-world', and the share of other-world windows flagged at a threshold set so that 5% of
training windows are flagged (the shipped rule)."""
import json, os, sys
import numpy as np
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
from sklearn.covariance import LedoitWolf
from sklearn.ensemble import IsolationForest
from sklearn.metrics import roc_auc_score
from sklearn.model_selection import GroupKFold
from sklearn.neighbors import NearestNeighbors
from sklearn.svm import OneClassSVM
from sklearn.decomposition import PCA
from deltat_doctor.sim.dataset import Dataset

D = {k: Dataset.load(p) for k, p in (("A", "results/data/main.npz"), ("B", "results/data_b/main.npz"))}

class Box:
    def fit(self, X): self.lo, self.hi = np.percentile(X, 1, 0), np.percentile(X, 99, 0); return self
    def score(self, X): return ((X < self.lo) | (X > self.hi)).sum(1).astype(float)

class Base:
    def fit(self, X):
        self.mu = np.median(X, 0); self.sc = np.subtract(*np.percentile(X, [75, 25], 0)) + 1e-6; self.Z = self.z(X); self._fit(self.Z); return self
    def z(self, X): return np.clip((X - self.mu) / self.sc, -8, 8)
    def score(self, X): return self._score(self.z(X))

class Maha(Base):
    def _fit(self, Z): self.lw = LedoitWolf().fit(Z)
    def _score(self, Z): return self.lw.mahalanobis(Z)

class PCAMaha(Base):
    def _fit(self, Z):
        self.p = PCA(n_components=0.95, whiten=True, svd_solver="full").fit(Z)
    def _score(self, Z): return (self.p.transform(Z) ** 2).sum(1)

class KNN(Base):
    def _fit(self, Z): self.nn = NearestNeighbors(n_neighbors=11).fit(Z)
    def _score(self, Z):
        d, _ = self.nn.kneighbors(Z, n_neighbors=10); return d.mean(1)

class Iso(Base):
    def _fit(self, Z): self.m = IsolationForest(n_estimators=300, random_state=0).fit(Z)
    def _score(self, Z): return -self.m.score_samples(Z)

class OCSVM(Base):
    def _fit(self, Z): self.m = OneClassSVM(nu=0.05, gamma="scale").fit(Z[:3000])
    def _score(self, Z): return -self.m.decision_function(Z)

class Ens:
    """Average of the training-ranks of Mahalanobis and kNN (rank among training scores)."""
    def fit(self, X):
        self.a, self.b = Maha().fit(X), KNN().fit(X)
        self.ta, self.tb = np.sort(self.a.score(X)), np.sort(self.b.score(X)); return self
    def score(self, X):
        ra = np.searchsorted(self.ta, self.a.score(X)) / len(self.ta); rb = np.searchsorted(self.tb, self.b.score(X)) / len(self.tb)
        return (ra + rb) / 2

DET = {"box_count": Box, "mahalanobis": Maha, "pca_mahalanobis": PCAMaha, "knn": KNN, "isolation_forest": Iso, "one_class_svm": OCSVM, "maha+knn": Ens}
res = {}
for fit, other in (("A", "B"), ("B", "A")):
    d, o = D[fit], D[other]
    g = d.meta["building_id"].to_numpy(); tr, te = next(GroupKFold(5).split(d.X, groups=g))
    res[f"fit_{fit}"] = {}
    for name, cls in DET.items():
        m = cls().fit(d.X[tr])
        s_tr, s_in, s_out = m.score(d.X[tr]), m.score(d.X[te]), m.score(o.X)
        thr = np.percentile(s_tr, 95)
        y = np.r_[np.zeros(len(s_in)), np.ones(len(s_out))]
        res[f"fit_{fit}"][name] = {"auroc_other_vs_in": float(roc_auc_score(y, np.r_[s_in, s_out])),
                                  "flag_in_world": float((s_in > thr).mean()), "flag_other_world": float((s_out > thr).mean())}
        print(fit, name, {k: round(v, 3) for k, v in res[f"fit_{fit}"][name].items()}, flush=True)
json.dump(res, open("results/openset_v2.json", "w"), indent=2)
