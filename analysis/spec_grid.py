"""
spec_grid.py -- the whole specification space: does the answer depend on the tuning choices?
=============================================================================================
    %run spec_grid.py                (about 10 minutes; progress is printed)

The sensitivity run showed that the main result (no incremental explanatory power at m = 1.3, rho = 1.0, K = 4,
shrunk rates) changes when the fuzziness exponent m is raised. This script maps that completely instead of
reporting a few hand-picked settings:

    rates  in {shrunk, raw}     K in {3, 4, 5, 6}     rho in {0.75, 1.0, 1.5}     m in {1.2, 1.3, 1.4, 1.5, 2.0}

For every combination it re-runs the clustering and the cross-season alignment, builds the membership changes and
tests them against the core and the full baseline: cluster-robust (by player) Wald p-value, gain in adjusted R2, and
gain in out-of-sample R2 (grouped cross-validation, 10 repetitions).
m = 1.2-1.5 is the range D'Urso et al. (2022) recommend for medoid-based methods, and they compared 1.3, 1.5 and 2.0.
All p-values are NAIVE (the memberships are treated as observed); bootstrap.py gives the corrected ones for chosen cells.
Each (rho, m) gets its own folder  clustering_sens_rho*_m*/ ; the main folder is reused for rho = 1.0, m = 1.3.
Outputs: regression/spec_grid.csv, thesis_outputs/figures/spec_heatmap.png, thesis_outputs/tables/spec_grid_by_m.csv/.tex
"""
import contextlib
import io
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

sys.path.insert(0, str(Path.cwd()))
for _m in ("build_panel", "pairs_lib", "fcmd_mdnc"):
    sys.modules.pop(_m, None)
from build_panel import find_fbref                                                    # noqa: E402
from pairs_lib import build_pairs, cluster_fit, wald_p, oos_gain                      # noqa: E402

RATES_LIST = ("shrunk", "raw")
K_LIST = (3, 4, 5, 6)
RHO_LIST = (0.75, 1.0, 1.5)
M_LIST = (1.2, 1.3, 1.4, 1.5, 2.0)
MAIN = (1.0, 1.3)
CV_REPS = 10

base = find_fbref().parent
ap = pd.read_csv(base / "panel" / "analysis_panel.csv")
ap["season"] = ap["season"].astype(str).str.zfill(4)
reg_dir, fig_dir, tab_dir = base / "regression", base / "thesis_outputs" / "figures", base / "thesis_outputs" / "tables"
for d in (reg_dir, fig_dir, tab_dir):
    d.mkdir(parents=True, exist_ok=True)
src0 = (base / "align_and_select.py") if (base / "align_and_select.py").exists() else Path("align_and_select.py")
src0 = src0.read_text(encoding="utf-8")


def folder_for(rho, m):
    return base / "clustering" if (rho, m) == MAIN else base / f"clustering_sens_rho{rho}_m{m}"


def ensure_clustering(rho, m):
    folder = folder_for(rho, m)
    need = [folder / f"aligned_memberships_{r}_K{k}.csv" for r in RATES_LIST for k in K_LIST]
    if all(f.exists() for f in need) and (folder / "select_K_summary.csv").exists():
        return folder
    s = src0
    for old, new in (("M, RHO, N_STARTS, SEED = 1.3, 1.0, 10, 0", f"M, RHO, N_STARTS, SEED = {m}, {rho}, 10, 0"),
                     ('RATES = ("shrunk", "raw")', f"RATES = {tuple(RATES_LIST)!r}"),
                     ("K_LIST = (3, 4, 5, 6)", f"K_LIST = {tuple(K_LIST)!r}"),
                     ('PROFILE = (("shrunk", 4), ("shrunk", 5))', "PROFILE = ()"),
                     ('out = base / "clustering"', f'out = base / "clustering_sens_rho{rho}_m{m}"')):
        assert old in s, f"align_and_select.py changed: cannot find  {old}"
        s = s.replace(old, new)
    with contextlib.redirect_stdout(io.StringIO()):
        exec(compile(s, "align_and_select_grid", "exec"), {"__name__": "__main__"})
    return folder


def evaluate(p, B, bname):
    bc = B["core"] + (B["full"] if bname == "full" else [])
    cols = [c for c in dict.fromkeys(bc + B["du"]) if p[c].std() > 1e-10]
    bc, du = [c for c in bc if c in cols], [c for c in B["du"] if c in cols]
    y, g = p["y"].to_numpy(float), pd.factorize(p["uid"])[0]
    r0, r1 = cluster_fit(y, p[bc], g), cluster_fit(y, p[bc + du], g)
    a, b = oos_gain(y, p[bc].to_numpy(float), p[bc + du].to_numpy(float), g, np.random.default_rng(0), CV_REPS, 5)
    return wald_p(r1, du), r1.rsquared_adj - r0.rsquared_adj, float((b - a).mean())


rows = []
combos = [(rho, m) for rho in RHO_LIST for m in M_LIST]
for i, (rho, m) in enumerate(combos, 1):
    folder = ensure_clustering(rho, m)
    summ = pd.read_csv(folder / "select_K_summary.csv")
    for rates in RATES_LIST:
        for K in K_LIST:
            mem = pd.read_csv(folder / f"aligned_memberships_{rates}_K{K}.csv")
            p, B, ref = build_pairs(ap, mem, K, rates, verbose=False)
            sm = summ[(summ["rates"] == rates) & (summ["K"] == K)].iloc[0]
            rec = {"rates": rates, "K": K, "rho": rho, "m": m, "pairs": len(p), "xie_beni": sm["xb"],
                   "noise_share": sm["noise"], "crisp": sm["crisp"], "persist": sm["persist"]}
            for bname in ("core", "full"):
                pv, dr, do = evaluate(p, B, bname)
                rec.update({f"{bname}_p": pv, f"{bname}_dR2": dr, f"{bname}_dOOS": do})
            rows.append(rec)
    print(f"  [{i}/{len(combos)}] rho={rho}, m={m} done", flush=True)

G = pd.DataFrame(rows)
G.to_csv(reg_dir / "spec_grid.csv", index=False)

# ---------------------------------------------------------------------------------- summaries
print("\nShare of the specifications with naive Wald p < 0.05, and median gains, by fuzziness m "
      "(all rates, K and rho pooled; 24 specifications per m):")
by_m = G.groupby("m").agg(core_share_sig=("core_p", lambda s: (s < 0.05).mean()), full_share_sig=("full_p", lambda s: (s < 0.05).mean()),
                          core_median_dR2=("core_dR2", "median"), full_median_dR2=("full_dR2", "median"),
                          core_median_dOOS=("core_dOOS", "median"), full_median_dOOS=("full_dOOS", "median"),
                          median_noise=("noise_share", "median"), median_crisp=("crisp", "median"),
                          median_xie_beni=("xie_beni", "median")).reset_index()
print(by_m.round(3).to_string(index=False))
by_m.to_csv(tab_dir / "spec_grid_by_m.csv", index=False)
(tab_dir / "spec_grid_by_m.tex").write_text(by_m.to_latex(index=False, float_format="%.3f", escape=True), encoding="utf-8")

print("\nBy K (pooled over rates, rho, m):")
print(G.groupby("K").agg(core_share_sig=("core_p", lambda s: (s < 0.05).mean()), full_share_sig=("full_p", lambda s: (s < 0.05).mean()),
                         full_median_dOOS=("full_dOOS", "median")).round(3).to_string())
print("\nBy rho (pooled):")
print(G.groupby("rho").agg(core_share_sig=("core_p", lambda s: (s < 0.05).mean()), full_share_sig=("full_p", lambda s: (s < 0.05).mean()),
                           full_median_dOOS=("full_dOOS", "median")).round(3).to_string())
print("\nThe pre-specified cell (shrunk, K=4, rho=1.0, m=1.3) and its neighbours in m:")
print(G[(G.rates == "shrunk") & (G.K == 4) & (G.rho == 1.0)][["m", "core_p", "core_dR2", "core_dOOS", "full_p", "full_dR2", "full_dOOS"]].round(4).to_string(index=False))

# ---------------------------------------------------------------------------------- figure
fig, axs = plt.subplots(2, 2, figsize=(9, 7.2), sharey="row")
for r, rho in enumerate((1.0,)):
    pass
for col, bname in enumerate(("core", "full")):
    for row, rho in enumerate((1.0, 1.5)):
        sub = G[G["rho"] == rho]
        lab = [(rt, k) for rt in RATES_LIST for k in K_LIST]
        mat = np.array([[sub[(sub.rates == rt) & (sub.K == k) & (sub.m == m)][f"{bname}_p"].iloc[0] for m in M_LIST] for rt, k in lab])
        ax = axs[row, col]
        im = ax.imshow(mat, cmap="RdYlBu", vmin=0, vmax=0.2, aspect="auto")
        for i in range(mat.shape[0]):
            for j in range(mat.shape[1]):
                ax.text(j, i, f"{mat[i, j]:.3f}", ha="center", va="center", fontsize=7, fontweight="bold" if mat[i, j] < 0.05 else "normal")
        ax.set_xticks(range(len(M_LIST))); ax.set_xticklabels([str(m) for m in M_LIST])
        ax.set_yticks(range(len(lab))); ax.set_yticklabels([f"{rt}, K={k}" for rt, k in lab], fontsize=8)
        ax.set_title(f"{bname.capitalize()} baseline, rho = {rho}", fontsize=9)
        if row == 1:
            ax.set_xlabel("Fuzziness exponent m")
fig.subplots_adjust(hspace=0.3, wspace=0.08, right=0.88)
cax = fig.add_axes([0.9, 0.25, 0.02, 0.5])
fig.colorbar(im, cax=cax, label="Naive Wald p-value (colour capped at 0.2; bold = below 0.05)")
fig.savefig(fig_dir / "spec_heatmap.png", dpi=300, bbox_inches="tight")
plt.close(fig)
print(f"\nSaved {reg_dir / 'spec_grid.csv'} and {fig_dir / 'spec_heatmap.png'}")
