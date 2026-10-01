"""
pairs_lib.py -- shared code for regression.py and bootstrap.py (season-pair table, tests).
Keeping it in one place guarantees the bootstrap builds EXACTLY the same variables as the main regression.
"""
import numpy as np
import pandas as pd
import statsmodels.api as sm

from build_panel import TYPE1, TYPE2, TYPE2_SHR

CORE_PERF = ("npg_p90", "assists_p90")


def perf_vars(rates):
    """The 12 statistics the clustering itself uses. The rate version matches the clustering variant
    (raw memberships are controlled with raw rates, shrunk with shrunk), so the 'full' baseline really
    contains everything the memberships are built from."""
    return TYPE1 + (TYPE2 if rates == "raw" else TYPE2_SHR)


def build_pairs(ap, mem, K, rates, ref=None, verbose=True):
    """One row per season pair (t -> t+1) with outcome, controls and membership changes.
    ap  : analysis panel (uid, pid, season, has_next, season_next, delta_log_mv, club_change_next, ...)
    mem : aligned memberships (pid, season, u_1..u_K, u_noise)
    ref : omitted reference archetype (default: the one with the largest mean membership)
    Returns (pairs, blocks, ref)."""
    PERF = perf_vars(rates)
    uc = [f"u_{j + 1}" for j in range(K)] + ["u_noise"]
    mem = mem.copy()
    mem["season"] = mem["season"].astype(str).str.zfill(4)
    keep = ["uid", "pid", "season", "age", "minutes", "team_ppm", "team_main", "pos_DF", "pos_FW"] + [f"s_{v}" for v in PERF]
    t = ap[ap["has_next"] & ap["delta_log_mv"].notna()][keep + ["season_next", "delta_log_mv", "club_change_next"]].copy()
    t["season_next"] = t["season_next"].astype(float).astype(int).astype(str).str.zfill(4)   # CSV turned it into a float
    n1 = ap[["uid", "pid", "season", "minutes", "team_ppm"] + [f"s_{v}" for v in PERF]]
    n1 = n1.rename(columns={c: c + "_1" for c in n1.columns if c != "uid"}).rename(columns={"season_1": "season_next"})
    p = t.merge(n1, on=["uid", "season_next"], validate="1:1")
    U0 = mem[["pid", "season"] + uc]
    U1 = mem[["pid", "season"] + uc].rename(columns={c: c + "_t1" for c in uc}).rename(
        columns={"pid": "pid_1", "season": "season_next"})
    p = p.merge(U0, on=["pid", "season"], validate="m:1").merge(U1, on=["pid_1", "season_next"], validate="m:1")
    p["y"] = p["delta_log_mv"]
    p["age_sq"] = p["age"] ** 2
    p["log_min"] = np.log(p["minutes"])
    p["dlog_min"] = np.log(p["minutes_1"]) - p["log_min"]
    p["ppm"], p["dppm"] = p["team_ppm"], p["team_ppm_1"] - p["team_ppm"]
    p["club_change"] = p["club_change_next"]
    for v in PERF:
        p[f"L_{v}"], p[f"D_{v}"] = p[f"s_{v}"], p[f"s_{v}_1"] - p[f"s_{v}"]
    for c in uc:
        p[f"d_{c}"] = p[c + "_t1"] - p[c]
    if ref is None:
        ref = max(range(1, K + 1), key=lambda j: p[f"u_{j}"].mean())
    dcols = [f"d_u_{j}" for j in range(1, K + 1) if j != ref] + ["d_u_noise"]
    lcols = [f"u_{j}" for j in range(1, K + 1) if j != ref] + ["u_noise"]
    p["norm"] = np.sqrt(sum(p[f"d_u_{j}"] ** 2 for j in range(1, K + 1)))
    ent = lambda M: -(np.clip(M, 1e-12, 1) * np.log(np.clip(M, 1e-12, 1))).sum(axis=1)
    p["dH"] = ent(p[[c + "_t1" for c in uc]].to_numpy()) - ent(p[uc].to_numpy())
    before = len(p)
    p = p.dropna(subset=["y", "ppm", "dppm"] + dcols).reset_index(drop=True)
    if verbose and len(p) < before:
        print(f"    (dropped {before - len(p)} pairs with a missing control)")
    season_d = pd.get_dummies(p["season"], prefix="s", drop_first=True).astype(float)
    p = pd.concat([p, season_d], axis=1)
    core_perf = [f"{a}_{v}" for v in CORE_PERF for a in ("L", "D")]
    blocks = {
        "core": ["age", "age_sq", "log_min", "dlog_min", "pos_DF", "pos_FW", "ppm", "dppm", "club_change"]
                + core_perf + list(season_d.columns),
        "full": [c for c in (f"{a}_{v}" for v in PERF for a in ("L", "D")) if c not in core_perf],
        "du": dcols, "norm": ["norm"], "dH": ["dH"], "levels": lcols}
    return p, blocks, ref


def cluster_fit(y, X, groups):
    return sm.OLS(y, sm.add_constant(X, has_constant="add")).fit(cov_type="cluster", cov_kwds={"groups": groups})


def wald_p(res, cols):
    names = res.model.exog_names
    R = np.zeros((len(cols), len(names)))
    for i, c in enumerate(cols):
        R[i, names.index(c)] = 1
    return float(res.wald_test(R, use_f=True, scalar=True).pvalue)


def oos_gain(y, Xa, Xb, groups, rng, reps=30, folds=5):
    """Out-of-sample R2 of models a and b, repeated grouped K-fold (folds never split a player)."""
    ug = np.unique(groups)
    ra, rb = [], []
    for _ in range(reps):
        fold_of = dict(zip(ug, rng.integers(0, folds, len(ug))))
        f = np.array([fold_of[g] for g in groups])
        sse = {"a": 0.0, "b": 0.0}
        sst = 0.0
        for k in range(folds):
            tr, te = f != k, f == k
            if te.sum() == 0:
                continue
            for lab, X in (("a", Xa), ("b", Xb)):
                A = np.column_stack([np.ones(tr.sum()), X[tr]])
                beta = np.linalg.lstsq(A, y[tr], rcond=None)[0]
                pred = np.column_stack([np.ones(te.sum()), X[te]]) @ beta
                sse[lab] += ((y[te] - pred) ** 2).sum()
            sst += ((y[te] - y[tr].mean()) ** 2).sum()
        ra.append(1 - sse["a"] / sst)
        rb.append(1 - sse["b"] / sst)
    return np.array(ra), np.array(rb)
