"""
bootstrap.py  --  two-stage bootstrap for the generated-regressor problem (Pagan, 1984)
======================================================================================
    %run bootstrap.py            (it prints a timing estimate first, then works in saved chunks)

WHY. The memberships u are ESTIMATED (stage 1: clustering), then used as regressors (stage 2). Ordinary
standard errors ignore the stage-1 noise, so they are too small. We therefore repeat BOTH stages on
resampled data and read the uncertainty off the spread of the results.

ONE REPLICATION
  1. resample PLAYERS with replacement (all of a player's seasons travel together);
  2. re-cluster every season with the same model, K, m, rho, weights and scaling constants;
  3. align each season's clusters to the ORIGINAL solution (Hungarian algorithm on medoid distances),
     so archetype k means the same thing in every replication and coefficients are comparable;
  4. rebuild the season-pair table (same code as regression.py) and re-estimate the delta_u coefficients
     under both baselines (core, full).

RESUMABLE. Every CHUNK replications are saved to regression/bootstrap_partial_<rates>_K<K>.pkl. If the run
is interrupted (sleep, crash, Ctrl-C) just run the script again: it continues where it stopped. If you raise B
later, only the extra replications are computed. Changing M, RHO, N_STARTS_BOOT or SEED invalidates the file.

OUTPUT (per configuration and baseline)
  * bootstrap SE next to the ordinary cluster-robust SE (ratio > 1: the naive SE was too small);
  * percentile 95% intervals and bootstrap p-values per coefficient;
  * a bootstrap Wald test of the WHOLE delta_u block (bootstrap covariance matrix);
  * how often adjusted R2 improves when delta_u is added.
The original point estimates use the memberships saved by align_and_select.py; medoids come from
clustering/medoids_*.csv, so nothing has to be re-clustered to reproduce the original solution.
"""
import pickle
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd
from joblib import Parallel, cpu_count, delayed
from scipy.optimize import linear_sum_assignment
from scipy.spatial.distance import cdist
from scipy.stats import chi2, norm

sys.path.insert(0, str(Path.cwd()))
for _m in ("build_panel", "fcmd_mdnc", "pairs_lib"):
    sys.modules.pop(_m, None)
from build_panel import TYPE1, TYPE2, TYPE2_SHR, TYPE3, find_fbref                  # noqa: E402
from fcmd_mdnc import TypeDistances, fit_best, weights_by_variable_count             # noqa: E402
from pairs_lib import build_pairs, cluster_fit                                       # noqa: E402

# Each configuration is (rates, K, rho, m). (1.0, 1.3) is the main setting and uses the files in clustering/;
# any other (rho, m) needs the folder clustering_sens_rho*_m*/ that spec_grid.py creates.
CONFIGS = [("shrunk", 4, 1.0, 1.3), ("shrunk", 4, 1.0, 1.4), ("shrunk", 4, 1.0, 1.5), ("shrunk", 4, 1.0, 1.2),
           ("shrunk", 4, 1.0, 2.0), ("shrunk", 4, 1.5, 1.3), ("shrunk", 3, 1.0, 1.3), ("shrunk", 5, 1.0, 1.3),
           ("raw", 4, 1.0, 1.3), ("raw", 3, 1.0, 1.3)]
B = 500                            # replications per configuration (saved replications are reused: only the extra ones are computed)
N_STARTS_BOOT = 10                 # same as the original clustering. With 3 starts a season sometimes landed in a
                                   # different local optimum (agreement with the original 52% in one test season);
                                   # with 10 it was 96-100%. Lower it only if the timing estimate says it is too long.
N_JOBS = -2                        # all cores but one
SEED = 12345
CHUNK = 20                         # replications per saved chunk
TIMING_ONLY = False                # True: time one replication, then stop
ALIGN_METHOD = "profile"            # must match align_and_select.py: archetypes are matched by their mean profiles, not by single medoids

base = find_fbref().parent
ap = pd.read_csv(base / "panel" / "analysis_panel.csv")
ap["season"] = ap["season"].astype(str).str.zfill(4)
ap["uid"] = ap["uid"].astype(str)
seasons = sorted(ap["season"].unique())
out = base / "regression"
out.mkdir(exist_ok=True)
ap_s = {s: ap[ap["season"] == s].reset_index(drop=True) for s in seasons}


def ols_coefs(y, X):
    A = np.column_stack([np.ones(len(y)), X])
    return np.linalg.lstsq(A, y, rcond=None)[0][1:]


def adj_r2(y, X):
    A = np.column_stack([np.ones(len(y)), X])
    beta = np.linalg.lstsq(A, y, rcond=None)[0]
    r2 = 1 - ((y - A @ beta) ** 2).sum() / ((y - y.mean()) ** 2).sum()
    return 1 - (1 - r2) * (len(y) - 1) / (len(y) - A.shape[1])


def estimates(p, blocks):
    """delta_u coefficients and adjusted-R2 gain under each baseline; columns without variation dropped."""
    res = {}
    y = p["y"].to_numpy(float)
    for bname in ("core", "full"):
        base_cols = blocks["core"] + (blocks["full"] if bname == "full" else [])
        base_cols = [c for c in base_cols if p[c].std() > 1e-10]
        du = blocks["du"]
        coef = ols_coefs(y, p[base_cols + du].to_numpy(float))[-len(du):]
        res[bname] = (coef, adj_r2(y, p[base_cols + du].to_numpy(float)) - adj_r2(y, p[base_cols].to_numpy(float)))
    return res


def folder_for(rho, m):
    return base / "clustering" if (rho, m) == (1.0, 1.3) else base / f"clustering_sens_rho{rho}_m{m}"


def original_medoids(rates, K, folder):
    """Row indices (within each season of ap) of the original medoids, in archetype order 1..K."""
    md = pd.read_csv(folder / f"medoids_{rates}_K{K}.csv")
    md["season"] = md["season"].astype(str).str.zfill(4)
    idx = {}
    for s in seasons:
        rows = []
        for k in range(1, K + 1):
            r = md[(md["season"] == s) & (md["archetype"] == k)].iloc[0]
            hit = ap_s[s][(ap_s[s]["player"] == r["player"]) & (ap_s[s]["team_main"] == r["team_main"])
                          & (ap_s[s]["minutes"] == r["minutes"])]
            if len(hit) != 1:
                raise RuntimeError(f"cannot locate medoid {r['player']} ({s}) uniquely: {len(hit)} matches")
            rows.append(int(hit.index[0]))
        idx[s] = rows
    return idx


def one_rep(b, cfg, td, W, ref, orig_idx, orig_prof=None, zinfo=None):
    rates, K, rho, m = cfg
    rng = np.random.default_rng(SEED + b)
    uids = ap["uid"].unique()
    draw = pd.Series(rng.choice(uids, len(uids), replace=True)).value_counts()
    parts = []
    for c in range(int(draw.max())):                           # copy c of every player drawn more than c times
        part = ap[ap["uid"].isin(draw.index[draw.values > c])].copy()
        part["uid"] = part["uid"] + f"#{c}"
        parts.append(part)
    bp = pd.concat(parts, ignore_index=True)
    bp["pid"] = bp["uid"]
    mem = []
    for s in seasons:
        df_s = bp[bp["season"] == s].reset_index(drop=True)
        mod = fit_best(td.within(df_s), K, m, rho, N_STARTS_BOOT, seed=SEED + 1000 * b, fixed_weights=W)
        if ALIGN_METHOD == "profile":
            zc, mu, sdv = zinfo
            Zb = (df_s[zc].to_numpy(float) - mu) / sdv
            Pb = (mod.U_[:, :K].T @ Zb) / mod.U_[:, :K].sum(0)[:, None]
            cost = cdist(orig_prof[s], Pb, "cityblock")                # rows: original archetypes 1..K, cols: bootstrap clusters
        else:
            sd = td.cross(ap_s[s], orig_idx[s], df_s, mod.medoids_)     # rows: original archetypes 1..K
            cost = sum(w ** 2 * x ** 2 for w, x in zip(W, sd))
        r, c = linear_sum_assignment(cost)
        lab = np.empty(K, int)
        for ri, ci in zip(r, c):
            lab[ci] = ri                                            # bootstrap cluster ci = archetype ri+1
        U = mod.U_
        Ua = np.empty_like(U)
        Ua[:, lab] = U[:, :K]
        Ua[:, K] = U[:, K]
        mm = df_s[["pid", "season"]].copy()
        for j in range(K):
            mm[f"u_{j + 1}"] = Ua[:, j]
        mm["u_noise"] = Ua[:, K]
        mem.append(mm)
    p, blocks, _ = build_pairs(bp, pd.concat(mem, ignore_index=True), K, rates, ref=ref, verbose=False)
    return estimates(p, blocks)


all_rows = []
for cfg in CONFIGS:
    rates, K, rho, m = cfg
    folder = folder_for(rho, m)
    tag = "" if (rho, m) == (1.0, 1.3) else f"_rho{rho}_m{m}"
    print(f"\n################ rates={rates}  K={K}  rho={rho}  m={m} ################", flush=True)
    t2 = TYPE2 if rates == "raw" else TYPE2_SHR
    W = weights_by_variable_count([len(TYPE1), len(t2), len(TYPE3)])
    td = TypeDistances(ap, TYPE1, t2, TYPE3, norm="sd")
    orig_idx = original_medoids(rates, K, folder)
    mem0 = pd.read_csv(folder / f"aligned_memberships_{rates}_K{K}.csv")
    zc = [f"s_{v}" for v in TYPE1 + t2] + TYPE3
    _X = ap[zc].to_numpy(float)
    zinfo = (zc, _X.mean(0), _X.std(0))
    mem0s = mem0.copy()
    mem0s["season"] = mem0s["season"].astype(str).str.zfill(4)
    dd = mem0s[["pid", "season"] + [f"u_{j + 1}" for j in range(K)]].merge(ap[["pid", "season"] + zc], on=["pid", "season"], validate="1:1")
    orig_prof = {}
    for s_, g_ in dd.groupby("season"):
        U_ = g_[[f"u_{j + 1}" for j in range(K)]].to_numpy()
        orig_prof[s_] = (U_.T @ ((g_[zc].to_numpy(float) - zinfo[1]) / zinfo[2])) / U_.sum(0)[:, None]
    p0, blocks, ref = build_pairs(ap, mem0, K, rates)
    est0 = estimates(p0, blocks)
    g0 = pd.factorize(p0["uid"])[0]
    print(f"original: {len(p0):,} pairs, reference archetype {ref}")

    workers = max(1, cpu_count() + 1 + N_JOBS) if N_JOBS < 0 else N_JOBS
    meta = {"M": m, "RHO": rho, "N_STARTS_BOOT": N_STARTS_BOOT, "SEED": SEED, "n_pairs": len(p0), "ALIGN": ALIGN_METHOD}
    ckpt = out / f"bootstrap_partial_{rates}_K{K}{tag}.pkl"
    done = {}
    if ckpt.exists():
        saved = pickle.load(open(ckpt, "rb"))
        if saved.get("meta") == meta:
            done = saved["reps"]
            print(f"resuming: {len(done)} replications already saved in {ckpt.name}", flush=True)
        else:
            print(f"!! {ckpt.name} was made with different settings; ignoring it (rename or delete it)", flush=True)
    todo = [b for b in range(B) if b not in done]
    if TIMING_ONLY or not done:
        t0 = time.time()
        b0 = todo[0] if todo else 0
        done[b0] = one_rep(b0, cfg, td, W, ref, orig_idx, orig_prof, zinfo)
        dt = time.time() - t0
        todo = [b for b in todo if b != b0]
        print(f"one replication took {dt:.0f} s; this machine runs {workers} at a time, so the remaining "
              f"{len(todo)} replications need about {dt * len(todo) / workers / 60:.0f} min "
              f"(single core: {dt * len(todo) / 60:.0f} min)", flush=True)
    if TIMING_ONLY:
        continue
    t_start = time.time()
    for i in range(0, len(todo), CHUNK):
        chunk = todo[i:i + CHUNK]
        res = Parallel(n_jobs=N_JOBS)(delayed(one_rep)(b, cfg, td, W, ref, orig_idx, orig_prof, zinfo) for b in chunk)
        done.update(dict(zip(chunk, res)))
        pickle.dump({"meta": meta, "reps": done}, open(ckpt, "wb"))
        el = time.time() - t_start
        left = len(todo) - i - len(chunk)
        print(f"  {len(done)}/{B} replications saved | {el / 60:.1f} min elapsed | "
              f"about {el / (i + len(chunk)) * left / 60:.0f} min left", flush=True)
    reps = [done[b] for b in sorted(done) if b < B]

    for bname in ("core", "full"):
        base_cols = blocks["core"] + (blocks["full"] if bname == "full" else [])
        base_cols = [c for c in base_cols if p0[c].std() > 1e-10]
        du = blocks["du"]
        fit = cluster_fit(p0["y"].to_numpy(float), p0[base_cols + du], g0)
        naive_se = fit.bse[du].to_numpy()
        coef0 = est0[bname][0]
        C = np.array([r[bname][0] for r in reps])                    # B x len(du)
        se_b = C.std(axis=0, ddof=1)
        bias = C.mean(axis=0) - coef0
        V = np.cov(C.T)
        wstat = float(coef0 @ np.linalg.pinv(V) @ coef0)
        pw = float(1 - chi2.cdf(wstat, df=len(du)))
        pz = 2 * (1 - norm.cdf(np.abs(coef0 / se_b)))
        tab = pd.DataFrame({"coef": coef0, "naive_se": naive_se, "boot_se": se_b, "se_ratio": se_b / naive_se,
                            "p_boot": pz, "ci_low": coef0 - 1.96 * se_b, "ci_high": coef0 + 1.96 * se_b,
                            "boot_bias": bias}, index=du)
        print(f"\n--- {bname} baseline: delta_u coefficients (B = {len(reps)}) ---")
        print(tab.round(3).to_string())
        print(f"bootstrap Wald test of the whole delta_u block: chi2({len(du)}) = {wstat:.2f}, p = {pw:.3f}")
        print("(p_boot and the interval use the bootstrap standard error: estimate +/- 1.96 SE. boot_bias = mean of the "
              "bootstrap estimates minus the original; a bootstrap distribution shifted away from the estimate makes "
              "percentile intervals misleading, so they are not used. In-sample R2 gains inside bootstrap samples are "
              "optimistic because of duplicated observations and are deliberately not reported.)")
        tab.to_csv(out / f"bootstrap_{rates}_K{K}{tag}_{bname}.csv")
        pd.DataFrame(C, columns=du).to_csv(out / f"bootstrap_draws_{rates}_K{K}{tag}_{bname}.csv", index=False)
        all_rows.append({"rates": rates, "K": K, "rho": rho, "m": m, "baseline": bname, "wald_p_boot": pw,
                         "mean_se_ratio": float((se_b / naive_se).mean()),
                         "max_abs_bias": float(np.abs(bias).max()), "gain_orig_adjR2": est0[bname][1]})

if all_rows:
    summ_path = out / "bootstrap_summary.csv"
    new = pd.DataFrame(all_rows)
    if summ_path.exists():
        old = pd.read_csv(summ_path)
        for c, v in (("rho", 1.0), ("m", 1.3)):
            if c not in old.columns:
                old[c] = v
        keys = ["rates", "K", "rho", "m", "baseline"]
        old = old.merge(new[keys].assign(_drop=1), on=keys, how="left")
        new = pd.concat([old[old["_drop"].isna()].drop(columns="_drop"), new], ignore_index=True)
    new.to_csv(summ_path, index=False)
    print("\n================ BOOTSTRAP SUMMARY (all configurations run so far) ================")
    print(new.round(3).to_string(index=False))
