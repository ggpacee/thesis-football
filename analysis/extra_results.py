"""
extra_results.py -- (1) full coefficient tables for the appendix, (2) the baseline WITHOUT performance statistics
==================================================================================================================
    %run extra_results.py            (about 1 minute)

PART 1  Complete coefficient tables (controls and membership changes) of the core and the full model for the main
        configuration and for m = 1.4 and 1.5 (shrunk rates, K = 4, rho = 1.0): cluster-robust standard errors.
        Saved as thesis_outputs/tables/coef_<core|full>_m<m>.csv / .tex.
PART 2  Carlo's request: a robustness check that EXCLUDES the performance statistics from the controls. The "minimal"
        baseline has age, age^2, minutes (level, change), position, team form (level, change), club change and season
        effects only. The membership changes are then tested against it, for every m of the fuzziness grid.
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path.cwd()))
for _m in ("build_panel", "pairs_lib"):
    sys.modules.pop(_m, None)
from build_panel import find_fbref                                                  # noqa: E402
from pairs_lib import build_pairs, cluster_fit, wald_p, oos_gain, CORE_PERF         # noqa: E402

RATES, K, RHO = "shrunk", 4, 1.0
M_TABLES = (1.3, 1.4, 1.5)
M_GRID = (1.2, 1.3, 1.4, 1.5, 2.0)

base = find_fbref().parent
ap = pd.read_csv(base / "panel" / "analysis_panel.csv")
ap["season"] = ap["season"].astype(str).str.zfill(4)
tab_dir = base / "thesis_outputs" / "tables"
tab_dir.mkdir(parents=True, exist_ok=True)


def folder_for(rho, m):
    return base / "clustering" if (rho, m) == (1.0, 1.3) else base / f"clustering_sens_rho{rho}_m{m}"


def label(c, ref, K):
    names = {"age": "Age", "age_sq": "Age squared", "log_min": "Log minutes (level)", "dlog_min": "Change in log minutes",
             "pos_DF": "Defender", "pos_FW": "Forward", "ppm": "Team points per match (level)", "dppm": "Change in team points per match",
             "club_change": "Change of club within the league", "L_npg_p90": "Non-penalty goals per 90 (level)",
             "D_npg_p90": "Non-penalty goals per 90 (change)", "L_assists_p90": "Assists per 90 (level)", "D_assists_p90": "Assists per 90 (change)"}
    if c in names:
        return names[c]
    if c.startswith("s_") and c[2:].isdigit():
        return f"Pair starting {int('20' + c[2:4])}/{c[4:]}"
    if c.startswith("d_u_"):
        k = c.split("_")[-1]
        return "Change in noise membership" if k == "noise" else f"Change in membership of archetype {k}"
    if c.startswith(("L_", "D_")):
        return ("Level of " if c[0] == "L" else "Change in ") + c[2:].replace("_", " ")
    return c


def fit(p, cols):
    return cluster_fit(p["y"].to_numpy(float), p[cols], pd.factorize(p["uid"])[0])


# ------------------------------------------------------------------------------------------------ PART 1
print("PART 1: full coefficient tables")
for m in M_TABLES:
    folder = folder_for(RHO, m)
    f = folder / f"aligned_memberships_{RATES}_K{K}.csv"
    if not f.exists():
        print(f"  skipped m={m}: {f.name} not found in {folder.name}")
        continue
    p, B, ref = build_pairs(ap, pd.read_csv(f), K, RATES, verbose=False)
    for bname in ("core", "full"):
        bc = B["core"] + (B["full"] if bname == "full" else [])
        cols = [c for c in dict.fromkeys(bc + B["du"]) if p[c].std() > 1e-10]
        r = fit(p, cols)
        t = pd.DataFrame({"Variable": [label(c, ref, K) for c in cols], "Coef.": r.params[cols].to_numpy(), "SE": r.bse[cols].to_numpy(),
                          "p": r.pvalues[cols].to_numpy()})
        t.to_csv(tab_dir / f"coef_{bname}_m{m}.csv", index=False)
        (tab_dir / f"coef_{bname}_m{m}.tex").write_text(t.to_latex(index=False, float_format="%.3f", escape=True), encoding="utf-8")
        if bname == "core":
            print(f"\n--- core baseline + delta_u, m = {m} (reference archetype {ref}; N = {int(r.nobs)}; adj R2 = {r.rsquared_adj:.4f}) ---")
            print(t.round(3).to_string(index=False))
    print(f"  tables saved for m={m}")

# ------------------------------------------------------------------------------------------------ PART 2
print("\nPART 2: membership changes against a baseline WITHOUT performance statistics")
rows = []
for m in M_GRID:
    folder = folder_for(RHO, m)
    f = folder / f"aligned_memberships_{RATES}_K{K}.csv"
    if not f.exists():
        print(f"  skipped m={m}")
        continue
    p, B, ref = build_pairs(ap, pd.read_csv(f), K, RATES, verbose=False)
    perf = [f"{a}_{v}" for v in CORE_PERF for a in ("L", "D")]
    minimal = [c for c in B["core"] if c not in perf]
    y, g = p["y"].to_numpy(float), pd.factorize(p["uid"])[0]
    cols = [c for c in dict.fromkeys(minimal + B["du"]) if p[c].std() > 1e-10]
    mn, du = [c for c in minimal if c in cols], [c for c in B["du"] if c in cols]
    r0, r1 = fit(p, mn), fit(p, mn + du)
    a, b = oos_gain(y, p[mn].to_numpy(float), p[mn + du].to_numpy(float), g, np.random.default_rng(0), 30, 5)
    rc = fit(p, B["core"])
    rows.append({"m": m, "adjR2_minimal": r0.rsquared_adj, "adjR2_core": rc.rsquared_adj, "p_delta_u": wald_p(r1, du),
                 "dAdjR2": r1.rsquared_adj - r0.rsquared_adj, "dOOS": float((b - a).mean())})
R = pd.DataFrame(rows)
R.to_csv(base / "regression" / "minimal_baseline.csv", index=False)
R.to_csv(tab_dir / "minimal_baseline.csv", index=False)
print(R.round(4).to_string(index=False))
print("\n(adjR2_minimal = baseline without any performance statistic; adjR2_core = with goals and assists.)")
