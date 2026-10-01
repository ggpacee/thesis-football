"""
seed_sensitivity.py -- how much does the answer depend on the random draw of the clustering?
=============================================================================================
    %run seed_sensitivity.py            (about 5-10 minutes on a multi-core machine; prints progress)

WHY. The clustering starts from random medoids, and the partitions of different starts agree only moderately (adjusted
Rand index about 0.5). The best of ten starts is kept per season, but the objective is flat, so a different seed (or a
different ordering of the rows) can give a different set of memberships. The first run of the pipeline and the rerun gave
very different test results for the SAME configuration (shrunk rates, K=4, m=1.3, rho=1.0), which is exactly this problem.
This script measures it: it repeats stage 1 (clustering of all seasons + alignment by profiles) with 30 different seeds,
builds the membership changes each time, and repeats the key test.

OUTPUT regression/seed_sensitivity.csv, thesis_outputs/figures/seed_sensitivity.png, thesis_outputs/tables/seed_sensitivity.csv
The p-values are conventional cluster-robust Wald tests (the memberships treated as observed); the bootstrap is not repeated.
Seed 0 should reproduce clustering/aligned_memberships_shrunk_K4.csv; the script checks this and says so.
"""
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from joblib import Parallel, cpu_count, delayed
from scipy.optimize import linear_sum_assignment
from scipy.spatial.distance import cdist

sys.path.insert(0, str(Path.cwd()))
for _m in ("build_panel", "fcmd_mdnc", "pairs_lib"):
    sys.modules.pop(_m, None)
from build_panel import TYPE1, TYPE2, TYPE2_SHR, TYPE3, find_fbref                  # noqa: E402
from fcmd_mdnc import TypeDistances, fit_best, weights_by_variable_count             # noqa: E402
from pairs_lib import build_pairs, cluster_fit, wald_p, oos_gain                     # noqa: E402

CONFIGS = [("shrunk", 4, 1.0, m) for m in (1.2, 1.3, 1.4, 1.5, 2.0)]
N_SEEDS = 30
N_STARTS = 10
CV_REPS = 10
N_JOBS = -2

base = find_fbref().parent
ap = pd.read_csv(base / "panel" / "analysis_panel.csv")
ap["season"] = ap["season"].astype(str).str.zfill(4)
seasons = sorted(ap["season"].unique())
dfs = {s: ap[ap["season"] == s].reset_index(drop=True) for s in seasons}
reg_dir, fig_dir, tab_dir = base / "regression", base / "thesis_outputs" / "figures", base / "thesis_outputs" / "tables"
for d in (reg_dir, fig_dir, tab_dir):
    d.mkdir(parents=True, exist_ok=True)


def cluster_align(rates, K, m, rho, seed):
    """Stage 1, exactly as align_and_select.py with ALIGN_METHOD = 'profile'. Returns the aligned memberships."""
    t2 = TYPE2 if rates == "raw" else TYPE2_SHR
    W = weights_by_variable_count([len(TYPE1), len(t2), len(TYPE3)])
    td = TypeDistances(ap, TYPE1, t2, TYPE3, norm="sd")
    zc = [f"s_{v}" for v in TYPE1 + t2] + TYPE3
    X = ap[zc].to_numpy(float)
    mu, sd = X.mean(0), X.std(0)
    models = {s: fit_best(td.within(dfs[s]), K, m, rho, N_STARTS, seed, fixed_weights=W) for s in seasons}
    Zs = {s: (dfs[s][zc].to_numpy(float) - mu) / sd for s in seasons}
    prof = {s: (models[s].U_[:, :K].T @ Zs[s]) / models[s].U_[:, :K].sum(0)[:, None] for s in seasons}
    perm = {seasons[0]: np.arange(K)}
    for a, b in zip(seasons[:-1], seasons[1:]):
        r, c = linear_sum_assignment(cdist(prof[a], prof[b], "cityblock"))
        pb = np.empty(K, int)
        for ri, ci in zip(r, c):
            pb[ci] = perm[a][ri]
        perm[b] = pb
    out = []
    for s in seasons:
        U = models[s].U_
        Ua = np.empty_like(U)
        Ua[:, perm[s]] = U[:, :K]
        Ua[:, K] = U[:, K]
        d = dfs[s][["uid", "pid", "season"]].copy()
        for j in range(K):
            d[f"u_{j + 1}"] = Ua[:, j]
        d["u_noise"] = Ua[:, K]
        d["hard"] = Ua.argmax(axis=1) + 1
        out.append(d)
    return pd.concat(out, ignore_index=True)


def evaluate(cfg, k):
    rates, K, rho, m = cfg
    seed = 100 * k
    mem = cluster_align(rates, K, m, rho, seed)
    p, B, ref = build_pairs(ap, mem, K, rates, verbose=False)
    y, g = p["y"].to_numpy(float), pd.factorize(p["uid"])[0]
    rec = {"rates": rates, "K": K, "rho": rho, "m": m, "seed": k, "persist": float(((mem.hard <= K)).mean()), "noise_share": float((mem.hard == K + 1).mean())}
    for bname in ("core", "full"):
        bc = B["core"] + (B["full"] if bname == "full" else [])
        cols = [c for c in dict.fromkeys(bc + B["du"]) if p[c].std() > 1e-10]
        bc, du = [c for c in bc if c in cols], [c for c in B["du"] if c in cols]
        r0, r1 = cluster_fit(y, p[bc], g), cluster_fit(y, p[bc + du], g)
        a, b = oos_gain(y, p[bc].to_numpy(float), p[bc + du].to_numpy(float), g, np.random.default_rng(0), CV_REPS, 5)
        rec.update({f"{bname}_p": wald_p(r1, du), f"{bname}_dR2": r1.rsquared_adj - r0.rsquared_adj, f"{bname}_dOOS": float((b - a).mean())})
    return rec


# ---- sanity check: seed 0 must reproduce the saved main-configuration memberships ----------------
saved = base / "clustering" / "aligned_memberships_shrunk_K4.csv"
if saved.exists():
    new = cluster_align("shrunk", 4, 1.3, 1.0, 0)
    old = pd.read_csv(saved)
    old["season"] = old["season"].astype(str).str.zfill(4)
    mm = new.merge(old, on=["pid", "season"], suffixes=("_n", "_o"), validate="1:1")
    diff = max(float((mm[f"u_{j}_n"] - mm[f"u_{j}_o"]).abs().max()) for j in (1, 2, 3, 4))
    print(f"check: seed 0 vs the saved main-configuration memberships: max abs difference = {diff:.2e} "
          f"({'reproduced' if diff < 1e-8 else 'NOT identical -- the saved file came from a different row order or settings'})", flush=True)

jobs = [(cfg, k) for cfg in CONFIGS for k in range(N_SEEDS)]
print(f"running {len(jobs)} clusterings on {max(1, cpu_count() + 1 + N_JOBS)} workers ...", flush=True)
rows = Parallel(n_jobs=N_JOBS, verbose=5)(delayed(evaluate)(cfg, k) for cfg, k in jobs)
R = pd.DataFrame(rows)
R.to_csv(reg_dir / "seed_sensitivity.csv", index=False)

summ = []
for (m_), g in R.groupby("m"):
    summ.append({"m": m_, "seeds": len(g),
                 "core_p_median": g.core_p.median(), "core_p_q25": g.core_p.quantile(.25), "core_p_q75": g.core_p.quantile(.75),
                 "core_p_min": g.core_p.min(), "core_p_max": g.core_p.max(), "core_share_sig": (g.core_p < .05).mean(),
                 "full_p_median": g.full_p.median(), "full_p_q25": g.full_p.quantile(.25), "full_p_q75": g.full_p.quantile(.75),
                 "full_p_min": g.full_p.min(), "full_p_max": g.full_p.max(), "full_share_sig": (g.full_p < .05).mean(),
                 "core_dR2_median_pp": 100 * g.core_dR2.median(), "full_dR2_median_pp": 100 * g.full_dR2.median(),
                 "core_dOOS_median_pp": 100 * g.core_dOOS.median(), "full_dOOS_median_pp": 100 * g.full_dOOS.median(),
                 "core_share_oos_pos": (g.core_dOOS > 0).mean(), "full_share_oos_pos": (g.full_dOOS > 0).mean()})
S = pd.DataFrame(summ)
S.to_csv(tab_dir / "seed_sensitivity.csv", index=False)
pd.set_option("display.width", 250, "display.max_columns", 30)
print("\n=========== SUMMARY OVER", N_SEEDS, "SEEDS (shrunk rates, K=4, rho=1.0) ===========")
print(S.round(3).T.to_string(header=[f"m={x}" for x in S.m]))

fig, axs = plt.subplots(1, 2, figsize=(9, 3.6), sharey=True)
for ax, bname in zip(axs, ("core", "full")):
    data = [R[R.m == m_][f"{bname}_p"].to_numpy() for m_ in sorted(R.m.unique())]
    ax.boxplot(data, tick_labels=[str(x) for x in sorted(R.m.unique())], showfliers=True)
    for i, d in enumerate(data):
        ax.scatter(np.random.default_rng(1).normal(i + 1, 0.05, len(d)), d, s=10, alpha=0.5, color="#0072B2")
    ax.axhline(0.05, color="black", ls="--", lw=0.8)
    ax.set_yscale("log"); ax.set_xlabel("Fuzziness exponent m"); ax.set_title(f"{bname.capitalize()} baseline", fontsize=9)
axs[0].set_ylabel("Wald p-value (log scale)")
fig.savefig(fig_dir / "seed_sensitivity.png", dpi=300, bbox_inches="tight")
plt.close(fig)
print(f"\nSaved {reg_dir / 'seed_sensitivity.csv'} and the figure/table in thesis_outputs/")
