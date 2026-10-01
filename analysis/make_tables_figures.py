"""
make_tables_figures.py -- every table and figure for the results chapter, ready for Overleaf
============================================================================================
    %run make_tables_figures.py            (about 1 minute)

Writes to  thesis_outputs/figures/*.png (300 dpi)  and  thesis_outputs/tables/*.tex (+ .csv copies).
In Overleaf: upload both folders, add  \\usepackage{booktabs}  and  \\usepackage{graphicx}  to the preamble, and use
      \\begin{table}[ht]\\centering\\input{tables/NAME.tex}\\caption{...}\\label{...}\\end{table}
      \\begin{figure}[ht]\\centering\\includegraphics[width=\\textwidth]{figures/NAME.png}\\caption{...}\\end{figure}
The captions, the interpretation and the archetype names below are yours to write and judge: the code only
produces numbers. The script skips (and says so) anything whose input file is missing.

ARCHETYPE NAMES are derived automatically from the profiles (the numbering of the archetypes differs between runs,
because it is inherited from the first season): defenders = the archetype with the highest defender share, strikers =
highest non-penalty goals among the rest, wide attackers = most crosses among the rest, central midfielders = the remaining
one. They are my labels for what the profiles show, not something the model outputs; check them against the profile table.
"""
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

sys.path.insert(0, str(Path.cwd()))
sys.modules.pop("build_panel", None)
from build_panel import find_fbref                                     # noqa: E402

MAIN = ("shrunk", 4)
ARCH_NAMES = {}          # filled below from the profiles
NOISE_NAME = "Atypical attackers (noise)"
FEATURED = ["Pedro Neto", "Luis Díaz", "Gonçalo Inácio", "Viktor Gyökeres", "João Palhinha", "Vitinha",
            "Otávio", "Rafa Silva", "Paulinho", "Matheus Nunes", "Florentino Luís", "Trincão"]
N_TRAJ = 6
PAL = ["#0072B2", "#D55E00", "#009E73", "#E69F00", "#CC79A7", "#56B4E9", "#999999"]   # colour-blind safe

base = find_fbref().parent
out = base / "thesis_outputs"
(out / "figures").mkdir(parents=True, exist_ok=True)
(out / "tables").mkdir(parents=True, exist_ok=True)
plt.rcParams.update({"font.size": 9, "axes.spines.top": False, "axes.spines.right": False, "figure.dpi": 100})
rates, K = MAIN
def read(path):
    p = base / path
    if not p.exists():
        print(f"  skipped (missing): {path}")
        return None
    return pd.read_csv(p)


def save_table(df, name, **kw):
    df.to_csv(out / "tables" / f"{name}.csv", index=False)
    kw.setdefault("float_format", "%.3f")
    (out / "tables" / f"{name}.tex").write_text(df.to_latex(index=False, escape=True, **kw), encoding="utf-8")
    print(f"  table  {name}")


def save_fig(fig, name):
    fig.savefig(out / "figures" / f"{name}.png", dpi=300, bbox_inches="tight")
    plt.close(fig)
    print(f"  figure {name}")


def season_label(s):
    s = str(s).zfill(4)
    return f"20{s[:2]}/{s[2:]}"


ap = read("panel/analysis_panel.csv")
ap["season"] = ap["season"].astype(str).str.zfill(4)
mem = read(f"clustering/aligned_memberships_{rates}_K{K}.csv")
mem["season"] = mem["season"].astype(str).str.zfill(4)
seasons = sorted(ap["season"].unique())
ucols = [f"u_{j}" for j in range(1, K + 1)] + ["u_noise"]
m = mem.merge(ap, on=["pid", "season"], suffixes=("", "_ap"), validate="1:1")


def derive_names(m, K):
    """Name the K archetypes from their membership-weighted profiles (only defined for K = 4)."""
    if K != 4:
        return {j: f"Archetype {j}" for j in range(1, K + 1)}
    w = {j: m[f"u_{j}"] for j in range(1, K + 1)}
    prof = {j: {c: float((m[c] * w[j]).sum() / w[j].sum()) for c in ("pos_DF", "npg_p90", "crosses_p90")} for j in w}
    left, names = set(w), {}
    d = max(left, key=lambda j: prof[j]["pos_DF"]); names[d] = "Defenders"; left.discard(d)
    s_ = max(left, key=lambda j: prof[j]["npg_p90"]); names[s_] = "Strikers"; left.discard(s_)
    wd = max(left, key=lambda j: prof[j]["crosses_p90"]); names[wd] = "Wide attackers"; left.discard(wd)
    names[left.pop()] = "Central midfielders"
    return names


ARCH_NAMES = derive_names(m, K)
names = [ARCH_NAMES.get(j, f"Archetype {j}") for j in range(1, K + 1)] + [NOISE_NAME]
print("archetype names derived from the profiles:", {j: ARCH_NAMES[j] for j in sorted(ARCH_NAMES)})

# ------------------------------------------------------------------------------------------- tables
print("TABLES")
t = ap.groupby("season").agg(player_seasons=("uid", "size"), players=("uid", "nunique"),
                             with_value=("log_mv", lambda s: s.notna().mean()))
pr = ap[ap["has_next"] & ap["delta_log_mv"].notna()].groupby("season").size().rename("pairs_with_value_change")
t = t.join(pr).fillna(0).reset_index()
t["season"] = t["season"].map(season_label)
t.loc[len(t)] = ["Total", len(ap), ap["uid"].nunique(), ap["log_mv"].notna().mean(), int(t["pairs_with_value_change"].sum())]
t["pairs_with_value_change"] = t["pairs_with_value_change"].astype(int)
save_table(t.rename(columns={"season": "Season", "player_seasons": "Player-seasons", "players": "Players",
                             "with_value": "Share with value", "pairs_with_value_change": "Season pairs used"}),
           "sample_by_season", float_format="%.2f")

cols = {"npg_p90": "Non-pen. goals/90", "assists_p90": "Assists/90", "shots_p90": "Shots/90", "crosses_p90": "Crosses/90",
        "interceptions_p90": "Interceptions/90", "tackles_won_p90": "Tackles won/90", "sot_rate": "Shots on target rate",
        "g_sh": "Goals per shot", "pos_DF": "Share DF", "pos_MF": "Share MF", "pos_FW": "Share FW"}
rows = []
for j, nm in enumerate(names):
    w = m["u_noise" if j == K else f"u_{j + 1}"]
    r = {"Profile": nm, "Share of player-seasons": float((m["hard"] == j + 1).mean())}
    r.update({lab: float((m[c] * w).sum() / w.sum()) for c, lab in cols.items()})
    rows.append(r)
rows.append({"Profile": "All players", "Share of player-seasons": 1.0, **{lab: float(m[c].mean()) for c, lab in cols.items()}})
save_table(pd.DataFrame(rows), "archetype_profiles", float_format="%.2f")

md = read(f"clustering/medoids_{rates}_K{K}.csv")
if md is not None:
    md["season"] = md["season"].astype(str).str.zfill(4).map(season_label)
    md["Profile"] = md["archetype"].map(lambda k: ARCH_NAMES.get(k, f"Archetype {k}"))
    mt = md.pivot(index="season", columns="Profile", values="player").reset_index().rename(columns={"season": "Season"})
    save_table(mt[["Season"] + [ARCH_NAMES[j] for j in range(1, K + 1) if ARCH_NAMES.get(j) in mt.columns]], "medoids_by_season")

sk = read("clustering/select_K_summary.csv")
if sk is not None:
    save_table(sk.rename(columns={"rates": "Rates", "xb": "Xie-Beni", "noise": "Noise share", "crisp": "Crisp share",
                                  "stab": "Start stability", "min_size": "Smallest archetype", "align_d": "Alignment distance",
                                  "ambiguous": "Ambiguous matches", "persist": "Persistence", "mean_norm": "Mean shift",
                                  "n_transitions": "Transitions"}), "cluster_selection", float_format="%.2f")

bc, bf = read(f"regression/bootstrap_{rates}_K{K}_core.csv"), read(f"regression/bootstrap_{rates}_K{K}_full.csv")
if bc is not None and bf is not None:
    def lab(ix):
        if ix == "d_u_noise":
            return "Change in noise membership"
        return f"Change in {ARCH_NAMES.get(int(ix.split('_')[-1]), ix).lower()} membership"
    rows = []
    for ix in bc.iloc[:, 0]:
        a, b = bc[bc.iloc[:, 0] == ix].iloc[0], bf[bf.iloc[:, 0] == ix].iloc[0]
        rows.append({"Regressor (vs. reference archetype)": lab(ix), "Core coef.": a["coef"], "Core boot. SE": a["boot_se"],
                     "Core p": a["p_boot"], "Full coef.": b["coef"], "Full boot. SE": b["boot_se"], "Full p": b["p_boot"]})
    save_table(pd.DataFrame(rows), "main_regression")

bs, rs = read("regression/bootstrap_summary.csv"), read("regression/regression_summary.csv")
if bs is not None and rs is not None:
    a = rs[rs["model"].isin(["core + delta_u", "full + delta_u"])].copy()
    a["baseline"] = a["model"].str.split().str[0]
    a = a.merge(bs[["rates", "K", "baseline", "wald_p_boot", "mean_se_ratio"]], on=["rates", "K", "baseline"], how="left")
    a = a[["rates", "K", "baseline", "adjR2_base", "d_adjR2", "d_oos", "wald_p", "wald_p_boot", "mean_se_ratio"]]
    save_table(a.rename(columns={"rates": "Rates", "baseline": "Baseline", "adjR2_base": "Adj. R2 baseline", "d_adjR2": "Gain adj. R2",
                                 "d_oos": "Gain out-of-sample R2", "wald_p": "Wald p (naive)", "wald_p_boot": "Wald p (bootstrap)",
                                 "mean_se_ratio": "SE ratio"}), "robustness_configurations", float_format="%.3f")

rv = read("regression/robustness_checks.csv")
if rv is not None:
    v = rv[rv["variation"].notna() & ~rv["variation"].str.startswith("FE/RE")]
    v = v[(v["rates"] == rates) & (v["K"] == K)][["variation", "n", "players", "core_p", "core_dR2", "full_p", "full_dR2"]]
    save_table(v.rename(columns={"variation": "Variation", "n": "Pairs", "players": "Players", "core_p": "Core p",
                                 "core_dR2": "Core gain adj. R2", "full_p": "Full p", "full_dR2": "Full gain adj. R2"}), "robustness_variations")
    fe = rv[rv["variation"].fillna("").str.startswith("FE/RE")]
    if len(fe):
        save_table(fe.dropna(axis=1, how="all"), "fixed_random_effects")

# descriptive statistics: the model variables (unscaled) and the regression variables
from build_panel import TYPE1, TYPE2_SHR                                              # noqa: E402
lab = {"npg_p90": "Non-penalty goals per 90", "assists_p90": "Assists per 90", "shots_p90": "Shots per 90",
       "sot_p90": "Shots on target per 90", "crosses_p90": "Crosses per 90", "interceptions_p90": "Interceptions per 90",
       "tackles_won_p90": "Tackles won per 90", "fouls_p90": "Fouls committed per 90", "fouled_p90": "Fouls drawn per 90",
       "offsides_p90": "Offsides per 90", "sot_rate_shr": "Shots on target rate (shrunk)", "g_sh_shr": "Goals per shot (shrunk)",
       "age": "Age (years)", "minutes": "Minutes played", "team_ppm": "Team points per match (on pitch)"}
rows = []
for c, nm in lab.items():
    x = ap[c].dropna()
    rows.append({"Variable": nm, "Mean": x.mean(), "SD": x.std(), "Min": x.min(), "Median": x.median(), "Max": x.max(), "N": len(x)})
dv = ap.loc[ap["has_next"] & ap["delta_log_mv"].notna(), "delta_log_mv"]
rows.append({"Variable": "Change in log market value (t to t+1)", "Mean": dv.mean(), "SD": dv.std(), "Min": dv.min(),
             "Median": dv.median(), "Max": dv.max(), "N": len(dv)})
if tr_ready := (base / f"clustering/transitions_{rates}_K{K}.csv").exists():
    tn = pd.read_csv(base / f"clustering/transitions_{rates}_K{K}.csv")["transition_norm"]
    rows.append({"Variable": "Size of the membership shift", "Mean": tn.mean(), "SD": tn.std(), "Min": tn.min(),
                 "Median": tn.median(), "Max": tn.max(), "N": len(tn)})
save_table(pd.DataFrame(rows), "summary_statistics", float_format="%.2f")

bsum = read("regression/bootstrap_summary.csv")
if bsum is not None:
    for c, v in (("rho", 1.0), ("m", 1.3)):
        if c not in bsum.columns:
            bsum[c] = v
    t = bsum[["rates", "K", "rho", "m", "baseline", "wald_p_boot", "mean_se_ratio"]].sort_values(["rho", "m", "rates", "K", "baseline"])
    save_table(t.rename(columns={"rates": "Rates", "rho": "Noise multiplier", "m": "Fuzziness", "baseline": "Baseline",
                                 "wald_p_boot": "Bootstrap Wald p", "mean_se_ratio": "SE ratio"}), "bootstrap_summary", float_format="%.3f")

# ------------------------------------------------------------------------------------------ figures
print("FIGURES")
prev = m.groupby("season")[ucols].mean()
fig, ax = plt.subplots(figsize=(6.5, 3.4))
bottom = np.zeros(len(prev))
for j, c in enumerate(ucols):
    ax.bar([season_label(s) for s in prev.index], prev[c], bottom=bottom, color=PAL[j], label=names[j], width=0.75)
    bottom += prev[c].to_numpy()
ax.set_ylabel("Average membership"); ax.set_ylim(0, 1); ax.tick_params(axis="x", rotation=45)
ax.legend(frameon=False, bbox_to_anchor=(1.01, 1), loc="upper left", fontsize=8)
save_fig(fig, "archetype_prevalence")

tr = read(f"clustering/transitions_{rates}_K{K}.csv")
if tr is not None:
    ct = pd.crosstab(tr["hard_t"], tr["hard_t1"]).reindex(index=range(1, K + 2), columns=range(1, K + 2), fill_value=0)
    share = ct.div(ct.sum(axis=1).replace(0, np.nan), axis=0)
    fig, ax = plt.subplots(figsize=(5.4, 4.4))
    im = ax.imshow(share.to_numpy(), cmap="Blues", vmin=0, vmax=1)
    for i in range(K + 1):
        for j in range(K + 1):
            ax.text(j, i, f"{share.iloc[i, j]:.2f}\n(n={ct.iloc[i, j]})", ha="center", va="center", fontsize=7,
                    color="white" if share.iloc[i, j] > 0.55 else "black")
    ax.set_xticks(range(K + 1)); ax.set_xticklabels(names, rotation=35, ha="right", fontsize=8)
    ax.set_yticks(range(K + 1)); ax.set_yticklabels(names, fontsize=8)
    ax.set_xlabel("Main archetype in season t+1"); ax.set_ylabel("Main archetype in season t")
    fig.colorbar(im, ax=ax, fraction=0.046, label="Row share")
    save_fig(fig, "transition_matrix")

    fig, axs = plt.subplots(1, 2, figsize=(7, 2.9))
    dv = ap.loc[ap["has_next"] & ap["delta_log_mv"].notna(), "delta_log_mv"]
    axs[0].hist(dv, bins=40, color=PAL[0]); axs[0].set_xlabel("Change in log market value (t to t+1)"); axs[0].set_ylabel("Season pairs")
    axs[1].hist(tr["transition_norm"], bins=40, color=PAL[1]); axs[1].set_xlabel("Size of the membership shift"); 
    save_fig(fig, "distributions")

pl = m.sort_values(["uid", "season"])
counts = pl.groupby("uid")["season"].nunique()
avail = pl[pl["uid"].isin(counts[counts >= 3].index)]
chosen = []
for nm in FEATURED:
    hit = avail[avail["player"].str.contains(nm.split()[-1], case=False, regex=False) & avail["player"].str.contains(nm.split()[0], case=False, regex=False)]
    if len(hit):
        chosen.append(hit["uid"].iloc[0])
    if len(chosen) >= N_TRAJ:
        break
if len(chosen) < N_TRAJ:                                            # fill with the players who moved most
    mv = avail.groupby("uid")[ucols[:K]].apply(lambda g: g.diff().abs().sum().sum()).sort_values(ascending=False)
    chosen += [u for u in mv.index if u not in chosen][:N_TRAJ - len(chosen)]
fig, axs = plt.subplots(2, 3, figsize=(9, 5.6), sharey=True)
fig.subplots_adjust(hspace=0.6, wspace=0.08)
for ax, uid in zip(axs.ravel(), chosen):
    g = pl[pl["uid"] == uid].set_index("season")[ucols]
    xpos = [seasons.index(s_) for s_ in g.index]                 # a missing season stays an empty slot
    bottom = np.zeros(len(g))
    for j, c in enumerate(ucols):
        ax.bar(xpos, g[c], bottom=bottom, color=PAL[j], width=0.8)
        bottom += g[c].to_numpy()
    ax.set_title(pl.loc[pl["uid"] == uid, "player"].iloc[0], fontsize=9)
    ax.set_xticks(range(len(seasons))); ax.set_xticklabels([season_label(s_)[2:] for s_ in seasons], rotation=60, fontsize=7)
    ax.set_xlim(-0.6, len(seasons) - 0.4); ax.set_ylim(0, 1)
for ax in axs.ravel()[len(chosen):]:
    ax.axis("off")
axs[0, 0].set_ylabel("Membership"); axs[1, 0].set_ylabel("Membership")
fig.legend(names, loc="lower center", ncol=5, frameon=False, fontsize=8, bbox_to_anchor=(0.5, -0.02))
save_fig(fig, "player_trajectories")

if bc is not None and bf is not None:
    fig, axs = plt.subplots(1, 2, figsize=(10, 3.4), gridspec_kw={"width_ratios": [1.2, 1], "wspace": 0.75})
    ix = list(bc.iloc[:, 0])
    y = np.arange(len(ix))
    for off, (tab, colr, lbl) in zip((-0.12, 0.12), ((bc, PAL[0], "Core baseline"), (bf, PAL[1], "Full baseline"))):
        axs[0].errorbar(tab["coef"], y + off, xerr=[tab["coef"] - tab["ci_low"], tab["ci_high"] - tab["coef"]], fmt="o", color=colr,
                        capsize=3, label=lbl, markersize=4)
    axs[0].axvline(0, color="black", lw=0.8); axs[0].set_yticks(y)
    axs[0].set_yticklabels([("noise" if i == "d_u_noise" else ARCH_NAMES.get(int(i.split("_")[-1]), i)) for i in ix])
    axs[0].set_xlabel("Effect on change in log value of a membership shift of 1\n(vs. the reference archetype; 95% bootstrap interval)")
    axs[0].legend(frameon=False, fontsize=8)
    if bs is not None:
        b2 = bs.copy()
        for c_, v_ in (("rho", 1.0), ("m", 1.3)):
            if c_ not in b2.columns:
                b2[c_] = v_
        b2 = b2[(b2["rho"] == 1.0) & (b2["m"] == 1.3)]
        b2["label"] = b2["rates"] + ", K=" + b2["K"].astype(str)
        for k, (bl, colr) in enumerate((("core", PAL[0]), ("full", PAL[1]))):
            s = b2[b2["baseline"] == bl].reset_index(drop=True)
            axs[1].scatter(s["wald_p_boot"], np.arange(len(s)) + (k - 0.5) * 0.25, color=colr, s=22)
        axs[1].set_yticks(np.arange(len(s))); axs[1].set_yticklabels(s["label"], fontsize=8)
        axs[1].axvline(0.05, color="black", ls="--", lw=0.8); axs[1].set_xlim(0, 1)
        axs[1].set_xlabel("Bootstrap Wald p-value, delta_u block")
    save_fig(fig, "coefficients_and_robustness")

print(f"\nDone. Files are in {out}")
