"""
sensitivity_and_benchmark.py -- (A) do the tuning constants rho and m drive the result?  (B) a PCA benchmark
=======================================================================================================
    %run sensitivity_and_benchmark.py          (about 5-10 minutes; prints progress)

PART A  Re-runs the whole clustering + alignment for the MAIN configuration (shrunk rates, K=4) with four other
        settings of the noise multiplier rho (0.75, 1.5) and the fuzziness exponent m (1.2, 1.5), builds the
        membership changes, and repeats the key test. Original: rho = 1.0, m = 1.3 (m = 1.3 is D'Urso et al.'s choice).
        Each setting is saved in its own folder  clustering_sens_rho*_m*/  so nothing existing is overwritten.
PART B  Carlo asked why fuzzy clustering rather than a dimensionality-reduction summary (PCA). Benchmark: replace the
        membership changes with changes in the first PCA scores of the same 12 performance variables (pooled over all
        seasons, same number of dimensions as the membership changes) and run the same test.
        Against the FULL baseline this test is empty BY CONSTRUCTION: PCA scores are linear combinations of the
        variables, whose changes the full baseline already contains. So the comparison is against the CORE baseline.
Both parts use cluster-robust (by player) Wald tests that treat the generated regressors as observed (as the main
regression.py does); bootstrap.py is the place for the corrected inference.
"""
import contextlib
import io
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path.cwd()))
for _m in ("build_panel", "pairs_lib", "fcmd_mdnc"):
    sys.modules.pop(_m, None)
from build_panel import find_fbref                                                    # noqa: E402
from pairs_lib import build_pairs, cluster_fit, wald_p, perf_vars                    # noqa: E402

SETTINGS = [(1.0, 1.3), (0.75, 1.3), (1.5, 1.3), (1.0, 1.2), (1.0, 1.5)]            # (rho, m); first = original
RATES, K = "shrunk", 4

base = find_fbref().parent
ap = pd.read_csv(base / "panel" / "analysis_panel.csv")
ap["season"] = ap["season"].astype(str).str.zfill(4)
out = base / "regression"
out.mkdir(exist_ok=True)


def wald_block(p, B, bname, extra=None):
    """Cluster-robust Wald p and adjusted-R2 gain of the delta_u block (or of `extra` columns) over a baseline."""
    bc = B["core"] + (B["full"] if bname == "full" else [])
    add = B["du"] if extra is None else extra
    cols = [c for c in dict.fromkeys(bc + add) if p[c].std() > 1e-10]
    bc, add = [c for c in bc if c in cols], [c for c in add if c in cols and c not in bc]
    y, g = p["y"].to_numpy(float), pd.factorize(p["uid"])[0]
    r0, r1 = cluster_fit(y, p[bc], g), cluster_fit(y, p[bc + add], g)
    return wald_p(r1, add), r1.rsquared_adj - r0.rsquared_adj


# ------------------------------------------------------------------------------------------------ PART A
src0 = (base / "align_and_select.py").read_text(encoding="utf-8") if (base / "align_and_select.py").exists() \
    else Path("align_and_select.py").read_text(encoding="utf-8")
rows = []
print("PART A: sensitivity to rho and m (main configuration: shrunk rates, K=4)")
for rho, m in SETTINGS:
    tag = f"rho{rho}_m{m}"
    folder = base / f"clustering_sens_{tag}"
    if rho == 1.0 and m == 1.3 and (base / "clustering" / f"aligned_memberships_{RATES}_K{K}.csv").exists():
        folder = base / "clustering"
        summ = pd.read_csv(folder / "select_K_summary.csv")
    else:
        if not (folder / f"aligned_memberships_{RATES}_K{K}.csv").exists():
            s = src0
            for old, new in (("M, RHO, N_STARTS, SEED = 1.3, 1.0, 10, 0", f"M, RHO, N_STARTS, SEED = {m}, {rho}, 10, 0"),
                             ('RATES = ("shrunk", "raw")', f'RATES = ("{RATES}",)'),
                             ("K_LIST = (3, 4, 5, 6)", f"K_LIST = ({K},)"),
                             ('PROFILE = (("shrunk", 4), ("shrunk", 5))', "PROFILE = ()"),
                             ('out = base / "clustering"', f'out = base / "clustering_sens_{tag}"')):
                assert old in s, f"align_and_select.py changed: cannot find  {old}"
                s = s.replace(old, new)
            print(f"  running clustering for rho={rho}, m={m} ...", flush=True)
            with contextlib.redirect_stdout(io.StringIO()):
                exec(compile(s, "align_and_select_sens", "exec"), {"__name__": "__main__"})
        summ = pd.read_csv(folder / "select_K_summary.csv")
    sm = summ[(summ["rates"] == RATES) & (summ["K"] == K)].iloc[0]
    mem = pd.read_csv(folder / f"aligned_memberships_{RATES}_K{K}.csv")
    p, B, ref = build_pairs(ap, mem, K, RATES, verbose=False)
    pc, dc = wald_block(p, B, "core"), None
    pf = wald_block(p, B, "full")
    rows.append({"rho": rho, "m": m, "noise_share": sm["noise"], "crisp": sm["crisp"], "stab": sm["stab"],
                 "persist": sm["persist"], "pairs": len(p), "core_p": pc[0], "core_dR2": pc[1],
                 "full_p": pf[0], "full_dR2": pf[1]})
A = pd.DataFrame(rows)
A.to_csv(out / "sensitivity_rho_m.csv", index=False)
print("\n" + A.round(3).to_string(index=False))

# ------------------------------------------------------------------------------------------------ PART B
print("\nPART B: PCA benchmark (changes in principal-component scores instead of membership changes)")
mem0 = pd.read_csv(base / "clustering" / f"aligned_memberships_{RATES}_K{K}.csv")
p, B, ref = build_pairs(ap, mem0, K, RATES, verbose=False)
vars_ = [f"s_{v}" for v in perf_vars(RATES)]
X = ap[vars_].to_numpy(float)
Z = (X - X.mean(0)) / X.std(0)
U_, S_, Vt = np.linalg.svd(Z, full_matrices=False)
share = S_ ** 2 / (S_ ** 2).sum()
k70 = int(np.searchsorted(np.cumsum(share), 0.70) + 1)
print("share of variance of the first 8 components:", np.round(share[:8], 3), f"| components for 70%: {k70}")
scores = pd.DataFrame(Z @ Vt.T[:, :8], columns=[f"pc{j + 1}" for j in range(8)])
scores[["uid", "season"]] = ap[["uid", "season"]].to_numpy()
t0 = scores.rename(columns={f"pc{j + 1}": f"pc{j + 1}_0" for j in range(8)})
t1 = scores.rename(columns={f"pc{j + 1}": f"pc{j + 1}_1" for j in range(8)}).rename(columns={"season": "season_next"})
p["season_next"] = p["season_next"].astype(str)
q = p.merge(t0, on=["uid", "season"], how="left").merge(t1, on=["uid", "season_next"], how="left")
for j in range(1, 9):
    q[f"dpc{j}"] = q[f"pc{j}_1"] - q[f"pc{j}_0"]
rowsB = []
for label, cols in ((f"delta_u ({len(B['du'])} dimensions)", B["du"]),
                    (f"PCA, first {len(B['du'])} components", [f"dpc{j}" for j in range(1, len(B["du"]) + 1)]),
                    (f"PCA, first {k70} components (70% of variance)", [f"dpc{j}" for j in range(1, k70 + 1)]),
                    ("PCA, first 8 components", [f"dpc{j}" for j in range(1, 9)])):
    pc_, dr = wald_block(q.dropna(subset=cols), B, "core", extra=cols)
    rowsB.append({"summary of the change in style": label, "pairs": int(q.dropna(subset=cols).shape[0]), "core_p": pc_, "core_dR2": dr})
Bt = pd.DataFrame(rowsB)
Bt.to_csv(out / "pca_benchmark.csv", index=False)
print(Bt.round(4).to_string(index=False))
print("\n(Against the core baseline only. A PCA summary and the membership changes both condense the same twelve statistics;"
      " the question is whether the clustering-based summary carries any signal the linear summary does not.)")
print(f"\nSaved {out / 'sensitivity_rho_m.csv'} and {out / 'pca_benchmark.csv'}")
