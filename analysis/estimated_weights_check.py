"""
estimated_weights_check.py -- reproduces Appendix B (the estimated attribute weights of D'Urso et al. fail on these data)
=====================================================================================================================
    %run estimated_weights_check.py          (about 1 minute)

For ONE season (2023/24, the development season) it fits the model with the weights ESTIMATED as in the original paper
(fixed_weights=None, no weight floor), m = 1.3, rho = 0.5 and Dave's noise distance, for
    distances scaled by their MAXIMUM (as in the paper) or by their MEAN,   raw or shrunk success rates,   K = 3, 4, 5.
It prints the estimated weights (performance, success rates, position), the noise share and whether the solution is
degenerate (one type with weight > 0.8, or Xie-Beni ~ 0, or more than half of the players in the noise cluster).
Saves regression/estimated_weights_2324.csv. The thesis table (Appendix B) is built from this file.
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path.cwd()))
for _m in ("build_panel", "fcmd_mdnc"):
    sys.modules.pop(_m, None)
from build_panel import TYPE1, TYPE2, TYPE2_SHR, TYPE3, find_fbref                  # noqa: E402
from fcmd_mdnc import TypeDistances, fit_best                                        # noqa: E402

SEASON, M, RHO, N_STARTS, SEED = "2324", 1.3, 0.5, 10, 0
base = find_fbref().parent
panel = pd.read_csv(base / "panel" / "panel_player_season.csv")
panel["season"] = panel["season"].astype(str).str.zfill(4)
df = panel[panel["season"] == SEASON].reset_index(drop=True)
print(f"season {SEASON}: n = {len(df)} players")

rows = []
for norm in ("max", "mean"):
    for rates, t2 in (("raw", TYPE2), ("shrunk", TYPE2_SHR)):
        D = TypeDistances(panel, TYPE1, t2, TYPE3, norm=norm).within(df)
        for K in (3, 4, 5):
            mod = fit_best(D, K, M, RHO, N_STARTS, SEED, fixed_weights=None, noise_rule="dave")
            noise = float((mod.labels_ == K).mean())
            w = mod.weights_
            degenerate = bool(w.max() > 0.8 or mod.xie_beni_ < 1e-6 or noise > 0.5)
            rows.append({"scaling": norm, "rates": rates, "K": K, "w_performance": w[0], "w_rates": w[1], "w_position": w[2],
                         "noise_share": noise, "xie_beni": mod.xie_beni_, "degenerate": degenerate})
R = pd.DataFrame(rows)
out = base / "regression"
out.mkdir(exist_ok=True)
R.to_csv(out / "estimated_weights_2324.csv", index=False)
pd.set_option("display.width", 200)
print(R.round(3).to_string(index=False))
print(f"\nSaved {out / 'estimated_weights_2324.csv'}")
