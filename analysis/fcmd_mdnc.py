"""
fcmd_mdnc.py  --  Robust Fuzzy C-Medoids Clustering of Mixed Data with a Noise Cluster
==========================================================================================
Implements Algorithm 1 and equations (2)-(7) of
  D'Urso, De Giovanni & Vitale (2022), "A robust method for clustering football
  players with mixed attributes", Annals of Operations Research 325, 9-36.
Noise-cluster idea: Dave (1991).  Medoid heuristic: Fu & Albus (1977), Krishnapuram et al. (2001).

NOTATION.  The paper's C counts the noise cluster (C-1 good clusters + 1 noise).
Here K = number of SUBSTANTIVE clusters (= C-1); the membership matrix U has K+1
columns and the LAST column is the noise cluster.

THE MODEL IN FOUR LINES  (S attribute types, each with a distance sd in [0,1])
  d2_ic  = sum_s (w_s * sd_ic,s)^2                         (2)  units i to medoid c
  U      : u_ic ~ (1/d2_ic)^(1/(m-1)), noise ~ (1/delta2)^(1/(m-1)), rows sum to 1   (4),(6)
  w_s    = (1/A_s) / sum_s'(1/A_s'),  A_s = sum_i sum_c u_ic^m sd2_ic,s              (5)
  delta2 = rho / (n*K) * sum_i sum_c u_ic^m d2_ic,  rho in [0.05, 0.5]  (noise distance)
  medoid_c = argmin_i' sum_i'' u_i''c^m d2(i', i'')                       (Algorithm 1, l.11)

CHOICES THE PAPER LEAVES OPEN (documented, and flagged where they matter):
  * delta2 is refreshed every iteration (as in Dave's noise clustering).
  * Xie-Beni is computed with SQUARED distances and the K substantive clusters
    (the paper's eq. (7) is ambiguous about squares and about the noise cluster).
  * Type distances are divided by FIXED constants computed once on the pooled panel
    (not per season), so medoids from different seasons stay comparable.
    norm="max"  : constant = largest pairwise distance -> sd in [0,1], as the paper says.
    norm="mean" : constant = mean pairwise distance    -> every type has average sd = 1.
    WHY BOTH: on the real data norm="max" put weight 0.95 on the two success-rate
    variables (a few extreme rates stretch the maximum, so typical sd looks tiny) and
    ~0 on performance and positions. norm="mean" makes the types comparable by typical
    spread, so the weights (which reward compact, well-separated types) mean what the
    paper's Remark 3 intends. Report both.
  * Several random starts; the run with the lowest objective is kept.
  * FIXED attribute-type weights (fixed_weights=...). On the Primeira Liga data the paper's
    estimated weights (eq. 5) degenerate whichever way the distances are scaled: they reward
    the type with the tightest within-cluster spread, which is always a LOW-DIMENSIONAL type
    (two success rates, or three coarse position dummies), never the ten performance
    variables. Akhanli & Hennig (2023, Sect. 2.5) instead standardise each group's
    dissimilarities by their standard deviation and choose the group weights
    proportionally to the number of variables in the group. norm="sd" and
    weights_by_variable_count() reproduce that. Because FCMd-MD-NC squares the weights
    (d2 = sum_s (w_s sd_s)^2), w_s is set proportional to sqrt(n_s) so that each group's
    contribution to d2 is proportional to its number of variables.
  * OPTIONAL weight floor (w_floor, default 0 = exactly the paper). Testing showed that
    eq. (5) can collapse onto one attribute type (weight -> 1) when that type is nearly
    discrete, e.g. coarse positions: clusters then just copy that type, the noise
    cluster absorbs the rest, the objective goes to 0 and Xie-Beni becomes meaningless.
    If that happens on the real data, w_floor > 0 enforces w_s >= w_floor
    (w = floor + (1 - S*floor) * w_paper). It is a DEVIATION from the paper: report it.
"""
import numpy as np
import pandas as pd
from scipy.spatial.distance import pdist


# ------------------------------------------------------------ type distances --
def l1_matrix(A, B=None, chunk=256):
    """Manhattan distance between all rows of A and all rows of B."""
    B = A if B is None else B
    out = np.empty((A.shape[0], B.shape[0]))
    for j in range(0, A.shape[0], chunk):
        out[j:j + chunk] = np.abs(A[j:j + chunk, None, :] - B[None, :, :]).sum(-1)
    return out


def jaccard_matrix(A, B=None):
    """Jaccard distance between 0/1 row vectors (a player can hold several positions).
    Two empty sets count as identical (distance 0)."""
    A = A.astype(float)
    B = A if B is None else B.astype(float)
    inter = A @ B.T
    union = A.sum(1)[:, None] + B.sum(1)[None, :] - inter
    with np.errstate(invalid="ignore", divide="ignore"):
        sim = np.where(union > 0, inter / union, 1.0)
    return 1.0 - sim


class TypeDistances:
    """Type 1 and 2: Manhattan on the scaled variables. Type 3: Jaccard on positions.
    Each is divided by a constant fixed once on the POOLED panel, so sd is in [0,1]
    and means the same thing in every season."""

    def __init__(self, panel, type1, type2, type3, prefix="s_", norm="max"):
        self.cols = [[prefix + c for c in type1], [prefix + c for c in type2], list(type3)]
        self.norm = norm
        X1 = panel[self.cols[0]].to_numpy(float)
        X2 = panel[self.cols[1]].to_numpy(float)
        d1, d2 = pdist(X1, "cityblock"), pdist(X2, "cityblock")
        if norm == "max":
            self.const = [d1.max(), d2.max(), 1.0]
        elif norm == "mean":
            J = jaccard_matrix(panel[self.cols[2]].to_numpy(float))
            self.const = [d1.mean(), d2.mean(), J[np.triu_indices_from(J, 1)].mean()]
        elif norm == "sd":                      # Akhanli & Hennig (2023), eq. (1): s_k = SD of the dissimilarities
            J = jaccard_matrix(panel[self.cols[2]].to_numpy(float))
            self.const = [d1.std(), d2.std(), J[np.triu_indices_from(J, 1)].std()]
        else:
            raise ValueError("norm must be 'max', 'mean' or 'sd'")

    def _block(self, df):
        return [df[c].to_numpy(float) for c in self.cols]

    def within(self, df):
        """List of three (n,n) matrices sd_s for one season's rows."""
        X = self._block(df)
        return [l1_matrix(X[0]) / self.const[0],
                l1_matrix(X[1]) / self.const[1],
                jaccard_matrix(X[2]) / self.const[2]]

    def cross(self, dfA, iA, dfB, iB):
        """List of three (len(iA), len(iB)) matrices between rows iA of dfA and rows iB of dfB."""
        XA = [x[iA] for x in self._block(dfA)]
        XB = [x[iB] for x in self._block(dfB)]
        return [l1_matrix(XA[0], XB[0]) / self.const[0],
                l1_matrix(XA[1], XB[1]) / self.const[1],
                jaccard_matrix(XA[2], XB[2]) / self.const[2]]


def weights_by_variable_count(counts):
    """Fixed weights w_s proportional to sqrt(n_s), summing to 1 (see module docstring)."""
    w = np.sqrt(np.asarray(counts, float))
    return w / w.sum()


# ------------------------------------------------------------------- model ----
class FCMdMDNC:
    def __init__(self, n_clusters, m=1.3, rho=0.2, max_iter=200, random_state=0, w_floor=0.0,
                 noise_rule="dave", fixed_weights=None):
        self.K, self.m, self.rho, self.w_floor = n_clusters, m, rho, w_floor
        self.noise_rule = noise_rule
        self.fixed_weights = None if fixed_weights is None else np.asarray(fixed_weights, float) / np.sum(fixed_weights)
        self.max_iter, self.random_state = max_iter, random_state

    @staticmethod
    def _combine(D2, w):
        return sum(wt ** 2 * d2 for wt, d2 in zip(w, D2))       # eq. (2), all pairs

    def _memberships(self, d2, delta2):
        e = 1.0 / (self.m - 1.0)
        logit = -e * np.log(np.maximum(d2, 1e-12))
        noise = np.full((d2.shape[0], 1), -e * np.log(max(delta2, 1e-12)))
        L = np.hstack([logit, noise])
        L -= L.max(axis=1, keepdims=True)                        # stable softmax
        P = np.exp(L)
        return P / P.sum(axis=1, keepdims=True)                  # eq. (4) and (6)

    def _init_medoids(self, Dc, rng):
        n = Dc.shape[0]
        med = [int(rng.integers(n))]
        while len(med) < self.K:                                 # k-medoids++ seeding
            dmin = Dc[:, med].min(axis=1)
            p = dmin / dmin.sum() if dmin.sum() > 0 else None
            nxt = int(rng.choice(n, p=p))
            if nxt not in med:
                med.append(nxt)
        return med

    def fit(self, D_list):
        """D_list: S matrices (n,n) of type distances already in [0,1]."""
        D2 = [np.asarray(d, float) ** 2 for d in D_list]
        n, S, K, m = D2[0].shape[0], len(D2), self.K, self.m
        rng = np.random.default_rng(self.random_state)
        w = np.full(S, 1.0 / S) if self.fixed_weights is None else self.fixed_weights.copy()
        med = self._init_medoids(self._combine(D2, w), rng)
        d2 = self._combine(D2, w)[:, med]
        delta2 = self.rho * d2.mean()
        converged = False
        for it in range(1, self.max_iter + 1):
            U = self._memberships(d2, delta2)
            um = U[:, :K] ** m
            A = np.array([(um * d[:, med]).sum() for d in D2]) + 1e-12
            if self.fixed_weights is None:
                w = (1.0 / A) / (1.0 / A).sum()                  # eq. (5)
            if self.fixed_weights is None and self.w_floor > 0:
                w = self.w_floor + (1.0 - S * self.w_floor) * w   # optional floor
            Dw2 = self._combine(D2, w)
            d2 = Dw2[:, med]
            if self.noise_rule == "paper":                       # as printed in D'Urso et al.
                delta2 = self.rho * (um * d2).sum() / (n * K)
            else:                                                # Dave (1991): unweighted mean
                delta2 = self.rho * d2.mean()
            new = []
            for c in range(K):                                   # medoid update
                cost = Dw2 @ um[:, c]
                cost[new] = np.inf                               # keep medoids distinct
                new.append(int(np.argmin(cost)))
            if new == med:
                converged = True
                break
            med = new
            d2 = Dw2[:, med]
        # final E-step with the final medoids / weights
        Dw2 = self._combine(D2, w)
        d2 = Dw2[:, med]
        U = self._memberships(d2, delta2)
        um = U[:, :K] ** m
        self.U_, self.medoids_, self.weights_ = U, med, w
        self.delta2_, self.n_iter_, self.converged_ = delta2, it, converged
        self.objective_ = float((um * d2).sum() + (U[:, K] ** m).sum() * delta2)   # eq. (3)
        inter = Dw2[np.ix_(med, med)] + np.diag(np.full(K, np.inf))
        imin = inter.min() if K > 1 else 0.0          # two identical medoids (duplicated rows) -> undefined
        self.xie_beni_ = float((um * d2).sum() / (n * imin)) if imin > 0 else np.inf
        self.labels_ = U.argmax(axis=1)                          # K = noise
        return self


def fit_best(D_list, n_clusters, m=1.3, rho=0.2, n_starts=10, seed=0, w_floor=0.0,
             noise_rule="dave", fixed_weights=None):
    """Best of n_starts random starts (lowest objective). Also sets best.stability_ = mean
    adjusted Rand index between the best run's hard partition and the other starts'."""
    from sklearn.metrics import adjusted_rand_score
    runs = [FCMdMDNC(n_clusters, m, rho, random_state=seed + i, w_floor=w_floor,
                     noise_rule=noise_rule, fixed_weights=fixed_weights).fit(D_list)
            for i in range(n_starts)]
    best = min(runs, key=lambda r: r.objective_)
    others = [r for r in runs if r is not best]
    best.stability_ = (float(np.mean([adjusted_rand_score(best.labels_, r.labels_) for r in others]))
                       if others else np.nan)
    return best


def select_parameters(D_list, K_grid=(2, 3, 4, 5, 6), m_grid=(1.2, 1.3, 1.4, 1.5),
                      rho=0.2, n_starts=10, seed=0, w_floor=0.0, noise_rule="dave", fixed_weights=None):
    """Grid over (K, m). Returns (table, {(K,m): fitted model}). Lower Xie-Beni is better."""
    rows, models = [], {}
    for K in K_grid:
        for m in m_grid:
            mod = fit_best(D_list, K, m, rho, n_starts, seed, w_floor, noise_rule, fixed_weights)
            U = mod.U_
            noise = float((mod.labels_ == K).mean())
            rows.append({"K": K, "m": m, "xie_beni": mod.xie_beni_, "objective": mod.objective_,
                         "noise_share": noise,
                         # degenerate = one type dominates, or objective ~0, or mostly noise
                         "degenerate": bool(mod.weights_.max() > 0.8 or mod.xie_beni_ < 1e-6 or noise > 0.5),
                         "share_max_mem_ge_0.7": float((U[:, :K].max(1) >= 0.7).mean()),
                         "stab_ari": mod.stability_, "iters": mod.n_iter_, "converged": mod.converged_,
                         **{f"w{s + 1}": w for s, w in enumerate(mod.weights_)}})
            models[(K, m)] = mod
    return pd.DataFrame(rows), models
