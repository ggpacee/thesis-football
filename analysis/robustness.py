"""
robustness.py  --  does the answer survive different choices?  (plus fixed/random effects and a Hausman test)
=============================================================================================================
    pip install linearmodels        (once; only needed for the fixed/random-effects part)
    %run robustness.py               (about 1 minute)

PART A  Sample and outcome variations for one clustering configuration (default: the main one).
        Each row re-tests "do the delta_u add anything?" with a cluster-robust (by player) Wald test under
        the core and the full baseline. All are associational checks; none is a causal design.
          winsorised outcome     value changes clipped at the 1st and 99th percentile
          stayers only           drop pairs where the player changed club inside the league
                                 (a transfer moves value for reasons unrelated to playing style)
          non-zero changes only  drop the 14% of pairs with exactly zero change (Transfermarkt values move in steps)
          minutes >= 500 in both seasons
          exclude COVID seasons  drop pairs starting in 2019-20 and 2020-21
          age <= 30
          no noise-dominated     drop players whose noise membership exceeds 0.5 in either season
PART B  Fixed effects (within-player) versus random effects, Hausman test.
          The outcome is already a change, so FE removes each player's own typical drift in value. Hausman
          tests whether FE and RE coefficients differ; a rejection favours FE. The proposal promised this test.
NOTE    p-values here are NOT corrected for the estimated memberships (see bootstrap.py for that) nor for the
        number of variations tried. Read the pattern across rows, not single p-values.
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import statsmodels.api as sm
from scipy.stats import chi2

sys.path.insert(0, str(Path.cwd()))
for _m in ("build_panel", "pairs_lib"):
    sys.modules.pop(_m, None)
from build_panel import find_fbref                                              # noqa: E402
from pairs_lib import build_pairs, cluster_fit, wald_p                          # noqa: E402

CONFIGS = [("shrunk", 4)]          # add ("shrunk", 3), ("shrunk", 5), ("raw", 4) to repeat everything for them

base = find_fbref().parent
ap = pd.read_csv(base / "panel" / "analysis_panel.csv")
ap["season"] = ap["season"].astype(str).str.zfill(4)
out = base / "regression"
out.mkdir(exist_ok=True)


def test_block(p, B, bname, y=None):
    """Cluster-robust Wald p-value for the delta_u block, and adjusted-R2 gain, on sample p."""
    bc = B["core"] + (B["full"] if bname == "full" else [])
    cols = [c for c in dict.fromkeys(bc + B["du"]) if p[c].std() > 1e-10]
    bc = [c for c in bc if c in cols]
    du = [c for c in B["du"] if c in cols]
    yy = (p["y"] if y is None else y).to_numpy(float)
    g = pd.factorize(p["uid"])[0]
    r0, r1 = cluster_fit(yy, p[bc], g), cluster_fit(yy, p[bc + du], g)
    return {"n": len(p), "players": p["uid"].nunique(), "wald_p": wald_p(r1, du),
            "d_adjR2": r1.rsquared_adj - r0.rsquared_adj}


def variants(p, mem_noise_cut=0.5):
    y = p["y"]
    yield "all pairs (main)", p, None
    yield "winsorised outcome (1%/99%)", p, y.clip(y.quantile(0.01), y.quantile(0.99))
    yield "stayers only (no club change)", p[p["club_change"] == 0], None
    yield "non-zero value changes only", p[p["y"] != 0], None
    yield "minutes >= 500 in both seasons", p[(np.exp(p["log_min"]) >= 500) & (np.exp(p["log_min"] + p["dlog_min"]) >= 500)], None
    yield "exclude COVID seasons (pairs from 1920, 2021)", p[~p["season"].isin(["1920", "2021"])], None
    yield "age <= 30", p[p["age"] <= 30], None
    yield "no noise-dominated players", p[(p["u_noise"] <= mem_noise_cut) & (p["u_noise_t1"] <= mem_noise_cut)], None


rows = []
for rates, K in CONFIGS:
    print(f"\n################ rates={rates}  K={K} ################")
    mem = pd.read_csv(base / "clustering" / f"aligned_memberships_{rates}_K{K}.csv")
    p, B, ref = build_pairs(ap, mem, K, rates)
    print(f"{len(p):,} pairs, {p['uid'].nunique():,} players, reference archetype {ref}")
    print("\nPART A: does delta_u add anything?  (Wald p, adjusted-R2 gain)")
    print(f"{'variation':<48}{'n':>6}{'players':>9} | {'core p':>8}{'core dR2':>10} | {'full p':>8}{'full dR2':>10}")
    for label, ps, ys in variants(p):
        if len(ps) < 200:
            print(f"{label:<48}  too few pairs ({len(ps)})")
            continue
        yv = None if ys is None else ys.loc[ps.index]
        rc, rf = test_block(ps, B, "core", yv), test_block(ps, B, "full", yv)
        print(f"{label:<48}{rc['n']:>6}{rc['players']:>9} | {rc['wald_p']:>8.3f}{rc['d_adjR2']:>10.4f} | "
              f"{rf['wald_p']:>8.3f}{rf['d_adjR2']:>10.4f}")
        rows.append({"rates": rates, "K": K, "variation": label, "n": rc["n"], "players": rc["players"],
                     "core_p": rc["wald_p"], "core_dR2": rc["d_adjR2"], "full_p": rf["wald_p"], "full_dR2": rf["d_adjR2"]})

    # ---------------------------------------------------------------- PART B
    try:
        from linearmodels.panel import PanelOLS, RandomEffects
    except ImportError:
        print("\nPART B skipped: run  pip install linearmodels  and rerun.")
        continue
    print("\nPART B: fixed vs random effects, Hausman test")
    d = p.assign(t=p["season"].astype(int)).set_index(["uid", "t"])      # linearmodels needs a numeric time index
    multi = d.groupby(level=0)["y"].transform("size") >= 2
    print(f"players with >= 2 season pairs (identify the fixed-effects model): "
          f"{d[multi].index.get_level_values(0).nunique():,} ({int(multi.sum()):,} pairs)")
    for bname in ("core", "full"):
        bc = B["core"] + (B["full"] if bname == "full" else [])
        cols = list(dict.fromkeys(bc + B["du"]))
        Xall = d[cols]
        within = Xall.groupby(level=0).transform(lambda s: s - s.mean()).std()
        # age rises by exactly one per season for the same player, so with player AND season effects it is
        # not identified (and age^2 nearly so); both are left out of this comparison
        cols = [c for c in cols if within[c] > 1e-8 and c not in ("age", "age_sq")]
        X, y = d[cols], d["y"]
        fe0 = PanelOLS(y, X, entity_effects=True, drop_absorbed=True).fit(cov_type="unadjusted")
        cols = [c for c in cols if c in fe0.params.index]              # what fixed effects can identify
        X = d[cols]
        fe = PanelOLS(y, X, entity_effects=True).fit(cov_type="unadjusted")
        re = RandomEffects(y, sm.add_constant(X)).fit(cov_type="unadjusted")
        fe_c = PanelOLS(y, X, entity_effects=True).fit(cov_type="clustered", cluster_entity=True)
        du = [c for c in B["du"] if c in cols]
        b_fe, b_re = fe.params[cols], re.params[cols]
        diff = (b_fe - b_re).to_numpy()
        Vd = (fe.cov.loc[cols, cols] - re.cov.loc[cols, cols]).to_numpy()
        H = float(diff @ np.linalg.pinv(Vd) @ diff)
        dfh = int(np.linalg.matrix_rank(Vd))
        pH = float(1 - chi2.cdf(max(H, 0), dfh))
        W = float(fe_c.params[du].to_numpy() @ np.linalg.pinv(fe_c.cov.loc[du, du].to_numpy()) @ fe_c.params[du].to_numpy())
        pFE = float(1 - chi2.cdf(W, len(du)))
        WR = float(re.params[du].to_numpy() @ np.linalg.pinv(re.cov.loc[du, du].to_numpy()) @ re.params[du].to_numpy())
        pRE = float(1 - chi2.cdf(WR, len(du)))
        print(f"  {bname} baseline: Hausman chi2({dfh}) = {H:.2f}, p = {pH:.3f} "
              f"({'favours FE' if pH < 0.05 else 'no evidence against RE'})")
        print(f"     delta_u block:  FE (cluster-robust) p = {pFE:.3f}   RE p = {pRE:.3f}   "
              f"| theta (random-effects variance share) = {float(re.theta.mean().iloc[0]):.2f}")
        tab = pd.DataFrame({"FE": fe_c.params[du], "FE_se": fe_c.std_errors[du], "RE": re.params[du], "RE_se": re.std_errors[du]})
        print(tab.round(3).to_string())
        rows.append({"rates": rates, "K": K, "variation": f"FE/RE Hausman ({bname})", "n": len(d), "players": d.index.get_level_values(0).nunique(),
                     "core_p" if bname == "core" else "full_p": pFE, "hausman_p": pH})

pd.DataFrame(rows).to_csv(out / "robustness_checks.csv", index=False)
print(f"\nSaved {out / 'robustness_checks.csv'}")
