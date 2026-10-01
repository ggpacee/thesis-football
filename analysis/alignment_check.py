"""
alignment_check.py -- are the archetype labels consistent across seasons in EVERY clustering run?
=================================================================================================
    %run alignment_check.py              (about 1-2 minutes; reads existing outputs only, changes nothing)

WHY. The archetypes of different seasons are matched with the Hungarian algorithm on the distance between MEDOIDS, which
are single players. If two or three archetypes have similar medoids, the matching can swap labels from one season to the
next (the m = 1.5 run does this after 2022/23: the central-midfielder medoids appear under a different number in the last
two seasons). A swapped label turns a whole season pair of memberships into nonsense and makes the "transitions" wrong.

THE CHECK uses a different piece of information than the alignment itself: the PROFILE of each archetype in each season,
i.e. the membership-weighted mean of the (globally z-scored) clustering variables over all players, not one player.
For each pair of adjacent seasons it asks whether label k in season t is still closest to label k in season t+1 under an
optimal one-to-one matching of those profiles. A pair is 'inconsistent' if that optimal matching is not the identity.
It also reports the persistence by pair (share of players keeping their archetype).

OUTPUT regression/alignment_check.csv (one row per clustering run), and a re-summary of the 120-specification grid
restricted to runs whose labels are consistent in every season pair.
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.optimize import linear_sum_assignment
from scipy.spatial.distance import cdist

sys.path.insert(0, str(Path.cwd()))
for _m in ("build_panel",):
    sys.modules.pop(_m, None)
from build_panel import TYPE1, TYPE2, TYPE2_SHR, TYPE3, find_fbref                  # noqa: E402

RATES_LIST, K_LIST = ("shrunk", "raw"), (3, 4, 5, 6)
RHO_LIST, M_LIST = (0.75, 1.0, 1.5), (1.2, 1.3, 1.4, 1.5, 2.0)

base = find_fbref().parent
ap = pd.read_csv(base / "panel" / "analysis_panel.csv")
ap["season"] = ap["season"].astype(str).str.zfill(4)
seasons = sorted(ap["season"].unique())


def folder_for(rho, m):
    return base / "clustering" if (rho, m) == (1.0, 1.3) else base / f"clustering_sens_rho{rho}_m{m}"


rows = []
for rho in RHO_LIST:
    for m in M_LIST:
        folder = folder_for(rho, m)
        for rates in RATES_LIST:
            t2 = TYPE2 if rates == "raw" else TYPE2_SHR
            zc = [f"s_{v}" for v in TYPE1 + t2] + TYPE3
            X = ap[zc].to_numpy(float)
            Z = pd.DataFrame((X - X.mean(0)) / X.std(0), columns=zc)
            Z[["pid", "season", "uid"]] = ap[["pid", "season", "uid"]].to_numpy()
            for K in K_LIST:
                f = folder / f"aligned_memberships_{rates}_K{K}.csv"
                if not f.exists():
                    continue
                mem = pd.read_csv(f)
                mem["season"] = mem["season"].astype(str).str.zfill(4)
                d = mem.drop(columns=[c for c in ("uid",) if c in mem.columns]).merge(Z, on=["pid", "season"], validate="1:1")
                U = {s: g[[f"u_{j + 1}" for j in range(K)]].to_numpy() for s, g in d.groupby("season")}
                V = {s: g[zc].to_numpy() for s, g in d.groupby("season")}
                prot = {s: (U[s].T @ V[s]) / U[s].sum(0)[:, None] for s in seasons}
                incons, margins, pers = [], [], []
                hard = d.set_index(["uid", "season"])["hard"]
                for a, b in zip(seasons[:-1], seasons[1:]):
                    D = cdist(prot[a], prot[b], "cityblock")
                    r, c = linear_sum_assignment(D)
                    incons.append(not np.array_equal(c, np.arange(K)))
                    both = d[d["season"] == a][["uid", "hard"]].merge(d[d["season"] == b][["uid", "hard"]], on="uid", suffixes=("_a", "_b"))
                    both = both[(both.hard_a <= K) & (both.hard_b <= K)]
                    pers.append(float((both.hard_a == both.hard_b).mean()) if len(both) else np.nan)
                # independent of any alignment criterion: do the MEDOIDS of one archetype have the same position labels across seasons?
                mf = folder / f"medoids_{rates}_K{K}.csv"
                mpa = np.nan
                if mf.exists():
                    md = pd.read_csv(mf)
                    mpa = float(np.mean([g["pos_raw"].value_counts().iloc[0] / len(g) for _, g in md.groupby("archetype")]))
                rows.append({"rho": rho, "m": m, "rates": rates, "K": K, "medoid_pos_agree": mpa, "n_inconsistent_pairs": int(sum(incons)),
                             "inconsistent_pairs": ",".join(f"{a[2:]}->{b[2:]}" for a, b, x in zip(seasons[:-1], seasons[1:], incons) if x),
                             "min_pair_persistence": float(np.nanmin(pers)), "mean_pair_persistence": float(np.nanmean(pers))})
        print(f"  rho={rho}, m={m} checked", flush=True)

R = pd.DataFrame(rows)
R["aligned_ok"] = R["n_inconsistent_pairs"] == 0
reg = base / "regression"
reg.mkdir(exist_ok=True)
R.to_csv(reg / "alignment_check.csv", index=False)

print(f"\n{len(R)} clustering runs; {int(R.aligned_ok.sum())} have consistent labels in every season pair ({R.aligned_ok.mean():.0%}).")
print("\nShare of runs with consistent labels, by K and by m:")
print(R.groupby("K")["aligned_ok"].mean().round(2).to_string())
print(R.groupby("m")["aligned_ok"].mean().round(2).to_string())
print("\nKey runs (shrunk, K=4, rho=1.0):")
print(R[(R.rates == "shrunk") & (R.K == 4) & (R.rho == 1.0)][["m", "n_inconsistent_pairs", "inconsistent_pairs", "min_pair_persistence", "mean_pair_persistence", "medoid_pos_agree"]].round(3).to_string(index=False))
print("\nMean share of seasons in which an archetype's medoid has its modal position labels (independent check, 1 = perfectly consistent):")
print(R.groupby("K")["medoid_pos_agree"].mean().round(3).to_string())

G_path = reg / "spec_grid.csv"
if G_path.exists():
    G = pd.read_csv(G_path).merge(R[["rho", "m", "rates", "K", "aligned_ok", "n_inconsistent_pairs"]], on=["rho", "m", "rates", "K"], how="left")
    ok = G[G.aligned_ok == True]
    print(f"\nGrid restricted to the {len(ok)} runs with consistent labels (of {len(G)}):")
    def summ(df):
        return pd.Series({"n": len(df), "core_sig": (df.core_p < .05).mean(), "full_sig": (df.full_p < .05).mean(),
                          "full_dR2_pp": 100 * df.full_dR2.median(), "full_dOOS_pp": 100 * df.full_dOOS.median(),
                          "core_dOOS_pp": 100 * df.core_dOOS.median()})
    print(summ(G).round(3).to_string(), "\n--- consistent runs only:")
    print(summ(ok).round(3).to_string())
    print("\nconsistent runs by m:"); print(ok.groupby("m").apply(summ, include_groups=False).round(3).to_string())
    print("\ninconsistent runs by m:"); print(G[G.aligned_ok == False].groupby("m").size().to_string())
    G.to_csv(reg / "spec_grid_with_alignment.csv", index=False)
print(f"\nSaved {reg / 'alignment_check.csv'}")
