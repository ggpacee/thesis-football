"""
align_and_select.py  --  cluster every season, align the clusters across seasons, build transitions
==================================================================================================
    %run make_analysis_panel.py       (once, first)
    %run align_and_select.py          (roughly 5-10 minutes)

For each rate variant (raw / shrunk) and each K in K_LIST it
  1. clusters EACH SEASON independently with FCMd-MD-NC (fixed Akhanli-Hennig weights, noise cluster);
  2. aligns the K substantive clusters across adjacent seasons with the Hungarian algorithm
     (scipy.optimize.linear_sum_assignment). ALIGN_METHOD = "profile" (default) matches the archetypes by their
     PROFILES: the membership-weighted mean of the z-scored clustering variables over all players of the archetype
     (Manhattan distance between profiles). "medoid" matches them by the weighted squared distance between the single
     medoid players; it was used first but swapped labels between seasons in some runs (e.g. m = 1.5), because a
     medoid is one player. Noise is never aligned;
  3. builds membership-transition vectors  delta_u = u(t+1) - u(t)  for every player observed in
     two consecutive seasons (columns delta_u_1..K for the archetypes, delta_u_noise separately);
  4. prints one comparison table so K can be chosen with everything on the table.

Everything for every (rates, K) is saved, so choosing K afterwards needs no recomputation:
  clustering/aligned_memberships_{rates}_K{K}.csv   clustering/transitions_{rates}_K{K}.csv
  clustering/medoids_{rates}_K{K}.csv               clustering/alignment_{rates}_K{K}.csv
  clustering/select_K_summary.csv

READING THE SUMMARY TABLE (per rates, K; averages over seasons unless stated)
  xb           Xie-Beni, lower is better, but it rises with K almost mechanically.
  noise        share of players whose largest membership is the noise cluster (want ~3-12%).
  crisp        share with largest substantive membership >= 0.7.
  stab         agreement (adjusted Rand) between random starts of the same season.
  min_size     smallest substantive cluster as a share of players (tiny = fragile archetype).
  align_d      mean distance between medoids matched across adjacent seasons (lower = the same
               archetype really is present in both seasons).
  ambiguous    matched pairs whose second-best alternative is within 10% of the chosen match.
  persist      among players in two consecutive seasons, share keeping the same archetype.
  mean_norm    average size of the transition vector.
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.optimize import linear_sum_assignment
from scipy.spatial.distance import cdist

sys.path.insert(0, str(Path.cwd()))
for _m in ("build_panel", "fcmd_mdnc"):
    sys.modules.pop(_m, None)
from build_panel import TYPE1, TYPE2, TYPE2_SHR, TYPE3, find_fbref                  # noqa: E402
from fcmd_mdnc import TypeDistances, fit_best, weights_by_variable_count             # noqa: E402

RATES = ("shrunk", "raw")
K_LIST = (3, 4, 5, 6)
M, RHO, N_STARTS, SEED = 1.3, 1.0, 10, 0
AMBIG = 1.10
ALIGN_METHOD = "profile"     # "profile": match archetypes by their mean profiles (robust); "medoid": by the distance between medoids
PROFILE = (("shrunk", 4), ("shrunk", 5))          # profiles printed at the end

base = find_fbref().parent
ap = pd.read_csv(base / "panel" / "analysis_panel.csv")
ap["season"] = ap["season"].astype(str).str.zfill(4)
seasons = sorted(ap["season"].unique())
out = base / "clustering"
out.mkdir(exist_ok=True)
print(f"analysis panel: {len(ap):,} player-seasons, {ap['uid'].nunique():,} players, seasons {seasons}")
dfs = {s: ap[ap["season"] == s].reset_index(drop=True) for s in seasons}


def entropy(u):
    u = np.clip(u, 1e-12, 1)
    return float(-(u * np.log(u)).sum())


summary, profiles = [], {}
for rates in RATES:
    t2 = TYPE2 if rates == "raw" else TYPE2_SHR
    W = weights_by_variable_count([len(TYPE1), len(t2), len(TYPE3)])
    td = TypeDistances(ap, TYPE1, t2, TYPE3, norm="sd")
    Ds = {s: td.within(dfs[s]) for s in seasons}
    zc = [f"s_{v}" for v in TYPE1 + t2] + TYPE3
    _X = ap[zc].to_numpy(float)
    _mu, _sd = _X.mean(0), _X.std(0)
    Zs = {s: (dfs[s][zc].to_numpy(float) - _mu) / _sd for s in seasons}
    print(f"\n##### rates={rates}  weights={np.round(W, 3)}  scaling constants={np.round(td.const, 2)}")
    for K in K_LIST:
        models = {s: fit_best(Ds[s], K, M, RHO, N_STARTS, SEED, fixed_weights=W) for s in seasons}

        # ---- Hungarian alignment of adjacent seasons --------------------------------------
        perm = {seasons[0]: np.arange(K)}          # perm[s][c] = reference label of season-s cluster c
        arows = []
        for a, b in zip(seasons[:-1], seasons[1:]):
            if ALIGN_METHOD == "profile":
                Pa = (models[a].U_[:, :K].T @ Zs[a]) / models[a].U_[:, :K].sum(0)[:, None]
                Pb = (models[b].U_[:, :K].T @ Zs[b]) / models[b].U_[:, :K].sum(0)[:, None]
                cost = cdist(Pa, Pb, "cityblock")                       # distance between archetype profiles
            else:
                sd = td.cross(dfs[a], models[a].medoids_, dfs[b], models[b].medoids_)
                cost = sum(w ** 2 * x ** 2 for w, x in zip(W, sd))      # weighted squared distance of medoids
            r, c = linear_sum_assignment(cost)
            pb = np.empty(K, int)
            for ri, ci in zip(r, c):
                pb[ci] = perm[a][ri]
            perm[b] = pb
            ratios = [min(np.delete(cost[ri], ci).min(), np.delete(cost[:, ci], ri).min())
                      / max(cost[ri, ci], 1e-12) for ri, ci in zip(r, c)]
            arows.append({"rates": rates, "K": K, "pair": f"{a}->{b}",
                          "mean_d": float((cost[r, c] if ALIGN_METHOD == "profile" else np.sqrt(cost[r, c])).mean()),
                          "max_d": float((cost[r, c] if ALIGN_METHOD == "profile" else np.sqrt(cost[r, c])).max()),
                          "n_ambiguous": int(sum(x < AMBIG for x in ratios)), "min_ratio": float(min(ratios))})
        pd.DataFrame(arows).to_csv(out / f"alignment_{rates}_K{K}.csv", index=False)

        # ---- aligned memberships and medoids ---------------------------------------------------
        mem, med = [], []
        for s in seasons:
            U = models[s].U_
            Ua = np.empty_like(U)
            Ua[:, perm[s]] = U[:, :K]              # raw column c -> reference column perm[s][c]
            Ua[:, K] = U[:, K]
            m = dfs[s][["uid", "pid", "season"]].copy()
            for j in range(K):
                m[f"u_{j + 1}"] = Ua[:, j]
            m["u_noise"] = Ua[:, K]
            m["hard"] = Ua.argmax(axis=1) + 1      # 1..K, K+1 = noise
            mem.append(m)
            for cidx, mi in enumerate(models[s].medoids_):
                med.append({"season": s, "archetype": int(perm[s][cidx]) + 1,
                            **dfs[s].loc[mi, ["player", "team_main", "pos_raw", "minutes"]].to_dict()})
        mem = pd.concat(mem, ignore_index=True)
        mem.to_csv(out / f"aligned_memberships_{rates}_K{K}.csv", index=False)
        pd.DataFrame(med).sort_values(["archetype", "season"]).to_csv(out / f"medoids_{rates}_K{K}.csv", index=False)

        # ---- transitions for consecutive seasons ---------------------------------------------------
        ucols = [f"u_{j + 1}" for j in range(K)] + ["u_noise"]
        nxt = {s: seasons[i + 1] for i, s in enumerate(seasons[:-1])}
        a_ = mem[mem["season"].isin(nxt)].copy()
        a_["season_t1"] = a_["season"].map(nxt)
        b_ = mem[["uid", "season"] + ucols + ["hard"]].rename(
            columns={c: c + "_t1" for c in ucols + ["hard"]}).rename(columns={"season": "season_t1"})
        tr = a_.merge(b_, on=["uid", "season_t1"], how="inner", validate="1:1")
        for j in range(K):
            tr[f"delta_u_{j + 1}"] = tr[f"u_{j + 1}_t1"] - tr[f"u_{j + 1}"]
        tr["delta_u_noise"] = tr["u_noise_t1"] - tr["u_noise"]
        dcols = [f"delta_u_{j + 1}" for j in range(K)]
        tr["transition_norm"] = np.sqrt((tr[dcols] ** 2).sum(axis=1))
        tr["dominant"] = tr[dcols].abs().to_numpy().argmax(axis=1) + 1
        tr["entropy_t"] = [entropy(r) for r in tr[ucols].to_numpy()]
        tr["entropy_t1"] = [entropy(r) for r in tr[[c + "_t1" for c in ucols]].to_numpy()]
        tr["delta_entropy"] = tr["entropy_t1"] - tr["entropy_t"]
        tr = tr.rename(columns={"season": "season_t", "hard": "hard_t", "hard_t1": "hard_t1"})
        tr.to_csv(out / f"transitions_{rates}_K{K}.csv", index=False)

        both = tr[(tr["hard_t"] <= K) & (tr["hard_t1"] <= K)]
        A = pd.DataFrame(arows)
        summary.append({
            "rates": rates, "K": K,
            "xb": np.mean([models[s].xie_beni_ for s in seasons]),
            "noise": np.mean([(models[s].labels_ == K).mean() for s in seasons]),
            "crisp": np.mean([(models[s].U_[:, :K].max(1) >= 0.7).mean() for s in seasons]),
            "stab": np.mean([models[s].stability_ for s in seasons]),
            "min_size": np.mean([np.bincount(models[s].labels_, minlength=K + 1)[:K].min() / len(dfs[s]) for s in seasons]),
            "align_d": A["mean_d"].mean(), "ambiguous": int(A["n_ambiguous"].sum()),
            "persist": float((both["hard_t"] == both["hard_t1"]).mean()) if len(both) else np.nan,
            "mean_norm": float(tr["transition_norm"].mean()), "n_transitions": len(tr)})
        s_ = summary[-1]
        print(f"  K={K}: xb={s_['xb']:.2f} noise={s_['noise']:.1%} crisp={s_['crisp']:.2f} stab={s_['stab']:.2f} "
              f"min_size={s_['min_size']:.1%} align_d={s_['align_d']:.2f} ambiguous={s_['ambiguous']} "
              f"persist={s_['persist']:.2f} transitions={len(tr):,}", flush=True)
        if (rates, K) in PROFILE:
            profiles[(rates, K)] = mem

summ = pd.DataFrame(summary)
summ.to_csv(out / "select_K_summary.csv", index=False)
print("\n================ SUMMARY (averages over seasons) ================")
print(summ.round(3).to_string(index=False))

cols = ["npg_p90", "assists_p90", "shots_p90", "crosses_p90", "interceptions_p90", "tackles_won_p90",
        "fouled_p90", "sot_rate", "g_sh", "pos_DF", "pos_MF", "pos_FW"]
for (rates, K), mem in profiles.items():
    m = mem.merge(ap[["uid", "season"] + cols], on=["uid", "season"], validate="1:1")
    rows = {}
    for j in range(K + 1):
        w = m["u_noise" if j == K else f"u_{j + 1}"]
        rows["noise" if j == K else f"archetype {j + 1}"] = m[cols].mul(w, axis=0).sum() / w.sum()
    rows["all"] = m[cols].mean()
    print(f"\n=== PROFILE rates={rates} K={K}: membership-weighted means over ALL seasons ===")
    print(pd.DataFrame(rows).T.round(2).to_string())
    md = pd.read_csv(out / f"medoids_{rates}_K{K}.csv")
    print("medoid players by archetype (one per season):")
    for k, g in md.groupby("archetype"):
        print(f"  archetype {k}: " + "; ".join(f"{r.season}:{r.player}({r.pos_raw})" for r in g.itertuples()))
