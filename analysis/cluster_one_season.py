"""
cluster_one_season.py  --  real-data check of the clustering model (v3: fixed weights)
======================================================================================
WHY v3.  On the Primeira Liga data the paper's ESTIMATED weights (eq. 5) never gave a usable
solution: scaled by the maximum, 95% of the weight went to the two success rates; scaled by the
mean, positions took 75-90% at K = 3-4; K >= 5 collapsed onto the 5 position sets in every variant.
Eq. (5) rewards whichever attribute type is tightest, which is always a low-dimensional one.

WHAT v3 DOES (Akhanli & Hennig 2023, Sect. 2.5):
  * each type's distances are divided by their standard deviation (norm="sd");
  * the type weights are FIXED, proportional to the number of variables in the type
    (sqrt-scaled because FCMd-MD-NC squares them), instead of estimated;
  * everything else is D'Urso's model: fuzzy medoids, noise cluster, Xie-Beni.
The estimated-weights results stay in the thesis as a documented negative result.

Needs build_panel.py (already run), fcmd_mdnc.py, this file in one folder.
    %run cluster_one_season.py        (about 3-5 minutes)

READ THE OUTPUT
  * noise_share   we want roughly 5-15% (the paper had 12%). rho sets it: larger rho -> less noise.
  * stab_ari      how reproducible the partition is across random starts (1 = identical).
  * share_max_mem_ge_0.7   crispness: well above 0.5 but below ~0.95 means fuzzy but readable.
  * xie_beni      only compare within one table (same rates, same rho); it tends to favour small K.
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path.cwd()))
# A notebook kernel keeps imported modules in memory; force fresh copies of the .py files.
for _m in ("build_panel", "fcmd_mdnc"):
    sys.modules.pop(_m, None)
from build_panel import TYPE1, TYPE2, TYPE2_SHR, TYPE3, find_fbref      # noqa: E402
from fcmd_mdnc import TypeDistances, select_parameters, weights_by_variable_count   # noqa: E402

SEASON = "2324"
RHO_LIST = (0.5, 1.0)
K_GRID = (2, 3, 4, 5, 6, 7)
M_GRID = (1.3,)
N_STARTS = 10
SEED = 0
PROFILE_K = (3, 4, 5)
PROFILE_RATES = "shrunk"          # "raw" or "shrunk"
PROFILE_RHO = 1.0

panel_path = find_fbref().parent / "panel" / "panel_player_season.csv"
panel = pd.read_csv(panel_path)
panel["season"] = panel["season"].astype(str).str.zfill(4)
df = panel[panel["season"] == SEASON].reset_index(drop=True)
print(f"Panel: {len(panel):,} player-seasons | season {SEASON}: n = {len(df)}")

variants = {"raw": TYPE2, "shrunk": TYPE2_SHR}
kept = {}
for rates, t2 in variants.items():
    W = weights_by_variable_count([len(TYPE1), len(t2), len(TYPE3)])
    td = TypeDistances(panel, TYPE1, t2, TYPE3, norm="sd")
    D = td.within(df)
    print(f"\n########## rates = {rates} | weights (perf, rates, pos) = {np.round(W, 3)} "
          f"| scaling constants = {np.round(td.const, 2)}")
    for rho in RHO_LIST:
        grid, models = select_parameters(D, K_GRID, M_GRID, rho=rho, n_starts=N_STARTS,
                                         seed=SEED, fixed_weights=W)
        kept[(rates, rho)] = (D, models)
        print(f"\n--- rho = {rho} ---")
        print(grid[["K", "m", "xie_beni", "noise_share", "share_max_mem_ge_0.7", "stab_ari",
                    "converged"]].round(3).to_string(index=False))
        out_dir = panel_path.parent.parent / "clustering"
        out_dir.mkdir(exist_ok=True)
        grid.assign(rates=rates, rho=rho).to_csv(out_dir / f"grid_{SEASON}_{rates}_rho{rho}.csv", index=False)

# ---- profiles for one chosen configuration --------------------------------------------------
D, models = kept[(PROFILE_RATES, PROFILE_RHO)]
cols = ["npg_p90", "assists_p90", "shots_p90", "crosses_p90", "interceptions_p90",
        "tackles_won_p90", "fouled_p90", "sot_rate", "g_sh", "pos_DF", "pos_MF", "pos_FW"]
for K in PROFILE_K:
    mod = models[(K, M_GRID[0])]
    U = mod.U_
    print(f"\n=== PROFILE  rates={PROFILE_RATES}  rho={PROFILE_RHO}  K={K}  m={M_GRID[0]} "
          f"(last row = noise) ===")
    print(df.loc[mod.medoids_, ["player", "team_main", "pos_raw", "minutes"]].to_string())
    rows = {}
    for c in range(K + 1):                                  # membership-weighted means, eq. (8)
        w = U[:, c]
        rows["noise" if c == K else f"cluster {c + 1}"] = df[cols].mul(w, axis=0).sum() / w.sum()
    rows["all players"] = df[cols].mean()
    print(pd.DataFrame(rows).T.round(2).to_string())
    print("hard sizes:", np.bincount(mod.labels_, minlength=K + 1).tolist())
    top = df.assign(noise_mem=U[:, K]).nlargest(5, "noise_mem")[
        ["player", "team_main", "pos_raw", "minutes", "shots_p90", "sot_rate", "g_sh", "noise_mem"]]
    print("highest noise membership:")
    print(top.round(2).to_string(index=False))
