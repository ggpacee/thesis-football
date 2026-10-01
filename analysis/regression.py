"""
regression.py  --  do membership transitions explain value changes beyond performance?
=======================================================================================
    %run make_analysis_panel.py ; %run align_and_select.py ; then
    %run regression.py                (about 1-3 minutes)

UNIT   one season pair (player, t -> t+1): the player has >= 200 league minutes in BOTH seasons
       and a Transfermarkt value at the end of both (June to June).
OUTCOME  delta_log_mv = log MV(t+1) - log MV(t).
KEY REGRESSORS  delta_u = u(t+1) - u(t): the change in fuzzy membership of each archetype
       (the K+1 memberships sum to 1, so the changes sum to 0: one archetype is the omitted
       reference, the most common one, and coefficients read "a shift of membership from the
       reference to archetype k"). Also tried: the size of the shift and the change in entropy.

TWO BASELINES (Carlo's overlap point, made explicit):
  core   age, age^2, minutes (level, change), position, team points per match (level, change),
         club change, season-pair effects, goals and assists per 90 (level, change)   [Franceschi et al. 2024]
  full   core + level AND change of ALL 12 variables the clustering itself uses.
         delta_u is a nonlinear summary of exactly these variables, so if it still adds
         explanatory power over `full`, it is not just re-encoding the raw statistics.

TESTS   cluster-robust (by player) Wald test for the added block; in-sample adjusted-R2 gain;
        out-of-sample R2 gain in repeated 5-fold cross-validation with folds grouped by player.
LANGUAGE  everything is associational: no causal identification is attempted.

NOT YET DONE (next script): the two-stage bootstrap for the generated-regressor problem. The
p-values here treat the memberships as observed and are therefore too optimistic.
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import statsmodels.api as sm

sys.path.insert(0, str(Path.cwd()))
for _m in ("build_panel", "pairs_lib"):
    sys.modules.pop(_m, None)
from build_panel import find_fbref          # noqa: E402
from pairs_lib import build_pairs, cluster_fit, wald_p, oos_gain      # noqa: E402

MAIN = ("shrunk", 4)
CONFIGS = [("shrunk", 4), ("raw", 4), ("shrunk", 3), ("shrunk", 5), ("raw", 3)]
CV_REPS, CV_FOLDS, SEED = 30, 5, 0

base = find_fbref().parent
ap = pd.read_csv(base / "panel" / "analysis_panel.csv")
ap["season"] = ap["season"].astype(str).str.zfill(4)
out = base / "regression"
out.mkdir(exist_ok=True)


def load_pairs(K, rates):
    mem = pd.read_csv(base / "clustering" / f"aligned_memberships_{rates}_K{K}.csv")
    return build_pairs(ap, mem, K, rates)


def compare(p, base_cols, add_cols, label):
    varies = [c for c in dict.fromkeys(base_cols + add_cols) if p[c].std() > 1e-10]
    base_cols = [c for c in base_cols if c in varies]
    add_cols = [c for c in add_cols if c in varies and c not in base_cols]
    y, g = p["y"].to_numpy(), pd.factorize(p["uid"])[0]
    r0 = cluster_fit(y, p[base_cols], g)
    r1 = cluster_fit(y, p[base_cols + add_cols], g)
    a, b = oos_gain(y, p[base_cols].to_numpy(float), p[base_cols + add_cols].to_numpy(float), g,
                    np.random.default_rng(SEED), CV_REPS, CV_FOLDS)
    return {"model": label, "n": int(r1.nobs), "k_added": len(add_cols),
            "adjR2_base": r0.rsquared_adj, "adjR2_ext": r1.rsquared_adj,
            "d_adjR2": r1.rsquared_adj - r0.rsquared_adj, "wald_p": wald_p(r1, add_cols),
            "oos_R2_base": a.mean(), "oos_R2_ext": b.mean(), "d_oos": (b - a).mean(),
            "share_cv_better": float((b > a).mean())}, r1


rows, main_fit = [], {}
for rates, K in CONFIGS:
    print(f"\n### rates={rates}  K={K}", flush=True)
    p, B, ref = load_pairs(K, rates)
    print(f"    {len(p):,} season pairs, {p['uid'].nunique():,} players; reference archetype = {ref}")
    for bname in ("core", "full"):
        bc = B["core"] + (B["full"] if bname == "full" else [])
        for lab, add in (("+ delta_u", B["du"]), ("+ size of shift", B["norm"]), ("+ delta entropy", B["dH"]),
                         ("+ levels u(t)", B["levels"]), ("+ levels u(t) + delta_u", B["levels"] + B["du"])):
            r, fit = compare(p, bc, add, f"{bname} {lab}")
            rows.append({"rates": rates, "K": K, **r})
            if (rates, K) == MAIN and lab == "+ delta_u":
                main_fit[bname] = fit

res = pd.DataFrame(rows)
res.to_csv(out / "regression_summary.csv", index=False)
pd.set_option("display.width", 220)
print("\n=========== MAIN CONFIGURATION  rates=%s K=%d ===========" % MAIN)
print(res[(res.rates == MAIN[0]) & (res.K == MAIN[1])].drop(columns=["rates", "K", "k_added"]).round(4).to_string(index=False))
print("\n=========== ROBUSTNESS: does delta_u add anything? (wald_p, gain in adj R2, gain in out-of-sample R2) ===========")
r = res[res.model.str.endswith("+ delta_u") & ~res.model.str.contains("levels")]
print(r[["rates", "K", "model", "n", "wald_p", "d_adjR2", "d_oos", "share_cv_better"]].round(4).to_string(index=False))

for bname, fit in main_fit.items():
    names = [n for n in fit.model.exog_names if n.startswith("d_u_")]
    tab = pd.DataFrame({"coef": fit.params[names], "se": fit.bse[names], "p": fit.pvalues[names]})
    tab["% change in value for +0.10 membership"] = 100 * (np.exp(0.10 * tab["coef"]) - 1)
    tab.to_csv(out / f"delta_u_coefficients_{bname}_baseline.csv")
    print(f"\n--- delta_u coefficients, {bname} baseline (cluster-robust by player; NOT bootstrap-corrected) ---")
    print(tab.round(3).to_string())
print(f"\nSaved to {out}")
