"""
build_panel.py  --  one row per player-season, variables built to the
D'Urso, De Giovanni & Vitale (2022) design.   No Transfermarkt needed.

RUN (notebook cell, script next to fbref_all_seasons.csv or one folder away):
    %run build_panel.py

WHAT IT DOES
  1. Merges the several FBref rows a player gets when he changes club mid-season
     (counts are summed, per-90 figures and rates are RECOMPUTED, not averaged).
  2. Applies the thesis filters AFTER merging: outfield players, >= 200 minutes.
  3. Builds the three attribute types the clustering model needs:
       type 1  performance per 90 (10 count variables)
       type 2  success rates (2 variables)
       type 3  positions (DF / MF / FW indicators, players can hold several)
  4. Scales type 1 and 2 by the average absolute deviation from the median, as in
     Akhanli & Hennig (2023) / D'Urso et al. (2022).

DECISIONS YOU SHOULD KNOW ABOUT (all change results, all are documented here):
  * Rows that share season, club AND name with another row (same-name players at one club) are excluded, because the
    FBref tables cannot be matched for them (see main()).
  * A rate with no attempts (zero shots) is set to 0; a MISSING shot count stays missing
    and the row is listed and dropped (it was silently turned into 0 in the first version).
  * A rate with no attempts (no shots) is set to 0. D'Urso's own medoid for
    low-activity players has Goals/Shots = 0.0, which suggests the same. A
    'no_shots' flag is kept so we can test median-imputation as a robustness check.
  * The scale (average absolute deviation) is computed ONCE on the pooled panel, so
    every season is measured in the same units and medoids from different seasons
    can be compared when we align clusters. Set SCALE_PER_SEASON = True for the
    alternative. (My earlier "standardise within each season" rule was wrong for
    this purpose: there is no prediction task, so there is nothing to leak.)
  * goals-per-shot is non-penalty goals / shots, because FBref's shot count
    excludes penalty kicks. goals-per-shot-on-target is dropped: it equals
    goals-per-shot divided by shot accuracy, so it would double-count.
"""
import re
from pathlib import Path

import numpy as np
import pandas as pd
from unidecode import unidecode

MIN_MINUTES = 200
SCALE_PER_SEASON = False

# raw FBref column -> short name (all confirmed present in the collected file)
SUM_COLS = {
    "playing_time_mp": "mp", "playing_time_starts": "starts",
    "playing_time_min": "minutes", "playing_time_90s": "nineties",
    "performance_gls": "goals", "performance_ast": "assists",
    "performance_g_pk": "npg", "standard_sh": "shots", "standard_sot": "sot",
    "performance_crdy": "yellow", "performance_crdr": "red",
    "performance_fls": "fouls", "performance_fld": "fouled",
    "performance_off": "offsides", "performance_crs": "crosses",
    "performance_int": "interceptions", "performance_tklw": "tackles_won",
}
TYPE1 = ["npg_p90", "assists_p90", "shots_p90", "sot_p90", "crosses_p90",
         "interceptions_p90", "tackles_won_p90", "fouls_p90", "fouled_p90", "offsides_p90"]
TYPE2 = ["sot_rate", "g_sh"]
TYPE2_SHR = ["sot_rate_shr", "g_sh_shr"]   # shrunk versions, see add_shrunk()
SHRINK_K = 10                               # prior strength, in shots
TYPE3 = ["pos_DF", "pos_MF", "pos_FW"]


def find_fbref():
    here = Path.cwd()
    for base in (here, here.parent, here / "test_outputs", here.parent / "test_outputs"):
        if (base / "fbref_all_seasons.csv").exists():
            return base / "fbref_all_seasons.csv"
    raise FileNotFoundError("fbref_all_seasons.csv not found near " + str(here))


def norm(s):
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9 ]", " ", unidecode(str(s)).lower())).strip()


def merge_multi_club(df):
    """One row per (player, born, season). Counts are summed; the club where he
    played most minutes is kept as team_main."""
    df = df.copy()
    df["season"] = df["season"].astype(str).str.zfill(4)
    df["born_key"] = pd.to_numeric(df["born"], errors="coerce").fillna(-1)
    for raw in SUM_COLS:
        df[raw] = pd.to_numeric(df[raw], errors="coerce")
    df = df.rename(columns=SUM_COLS)
    df["age"] = pd.to_numeric(df["age"], errors="coerce")
    df["_w"] = df["minutes"].fillna(0)
    ppm = pd.to_numeric(df["team_success_ppm"], errors="coerce")
    df["_w_ppm"] = df["_w"].where(ppm.notna(), 0)
    df["_ppm_w"] = ppm.fillna(0) * df["_w_ppm"]

    keys = ["player", "born_key", "season"]
    g = df.groupby(keys, sort=False)
    out = g[list(SUM_COLS.values())].sum(min_count=1)
    top = df.loc[g["_w"].idxmax()].set_index(keys)
    out["team_main"] = top["team"]
    out["nation"] = top["nation"]
    out["age"] = top["age"]
    out["n_clubs"] = g["team"].nunique()
    out["pos_raw"] = g["pos"].agg(lambda s: ",".join(sorted({t.strip() for x in s.dropna()
                                                          for t in str(x).split(",") if t.strip()})))
    out["team_ppm"] = g["_ppm_w"].sum() / g["_w_ppm"].sum().replace(0, np.nan)
    out = out.reset_index().rename(columns={"born_key": "born"})
    out["born"] = out["born"].replace(-1, np.nan)
    return out


def build_variables(p):
    n90 = (p["minutes"] / 90).replace(0, np.nan)   # exact; FBref rounds its own 90s column
    for c, name in [("npg", "npg_p90"), ("assists", "assists_p90"), ("shots", "shots_p90"),
                    ("sot", "sot_p90"), ("crosses", "crosses_p90"),
                    ("interceptions", "interceptions_p90"), ("tackles_won", "tackles_won_p90"),
                    ("fouls", "fouls_p90"), ("fouled", "fouled_p90"), ("offsides", "offsides_p90")]:
        p[name] = p[c] / n90
    sh = p["shots"]
    p["no_shots"] = (sh == 0)                       # NaN shots is NOT the same as zero shots
    p["sot_rate"] = np.where(sh > 0, p["sot"] / sh, np.where(sh.isna(), np.nan, 0.0))
    p["g_sh"] = np.where(sh > 0, p["npg"] / sh, np.where(sh.isna(), np.nan, 0.0))
    for tag in ("DF", "MF", "FW", "GK"):
        p[f"pos_{tag}"] = p["pos_raw"].str.contains(tag, na=False).astype(int)
    p["gk_only"] = p["pos_raw"].str.strip().eq("GK")
    p["pid"] = p["player"].map(norm) + "_" + p["born"].fillna(0).astype(int).astype(str)
    p["age_sq"] = p["age"] ** 2
    p["log_minutes"] = np.log(p["minutes"].clip(lower=1))
    return p


def add_shrunk(p):
    """Empirical-Bayes shrinkage of the two rates toward the pooled league rate:
         rate_shr = (successes + K * pooled_rate) / (shots + K)
    A player with 1 shot and 1 goal no longer gets a 100% finishing rate, and a player
    with no shots gets the league rate (no information) instead of 0. Alternative to the
    paper's raw percentages; used as a robustness variant. (Efron & Morris, 1975, for the
    idea -- verify the reference before citing.)"""
    tot = p["shots"].sum()
    p_g, p_s = p["npg"].sum() / tot, p["sot"].sum() / tot
    p["g_sh_shr"] = (p["npg"] + SHRINK_K * p_g) / (p["shots"] + SHRINK_K)
    p["sot_rate_shr"] = (p["sot"] + SHRINK_K * p_s) / (p["shots"] + SHRINK_K)
    return p


def add_scaled(p):
    """s_<var> = var / average absolute deviation from the median."""
    rows = []
    groups = p.groupby("season") if SCALE_PER_SEASON else [("ALL", p)]
    for _, g in groups:
        for v in TYPE1 + TYPE2 + TYPE2_SHR:
            med = g[v].median()
            aad = (g[v] - med).abs().mean()
            aad = aad if aad and aad > 0 else g[v].std() or 1.0
            idx = g.index
            p.loc[idx, f"s_{v}"] = p.loc[idx, v] / aad
            rows.append({"group": _, "variable": v, "median": med, "aad": aad})
    return p, pd.DataFrame(rows)


def main():
    src = find_fbref()
    out_dir = src.parent / "panel"
    out_dir.mkdir(exist_ok=True)
    raw = pd.read_csv(src)
    print(f"Loaded {src.name}: {len(raw):,} rows, {raw['player'].nunique():,} names")

    # Two players with the same name at the same club in the same season cannot be told apart when the four FBref tables
    # are joined on (season, club, name): the join pairs each of them with each row of the other tables, so their counts
    # and minutes are duplicated and mixed (a 'player' with 22,152 minutes appeared this way). Such rows cannot be repaired
    # from the merged file and are excluded; they are listed so that the number is known.
    clash = raw.duplicated(["season", "team", "player"], keep=False)
    if clash.any():
        groups = raw[clash].groupby(["season", "team", "player"]).size().reset_index(name="rows")
        print(f"Raw rows sharing season, club and name with another row: {int(clash.sum())} rows in {len(groups)} groups -> EXCLUDED:")
        print(groups.to_string(index=False))
        raw = raw[~clash].copy()

    p = merge_multi_club(raw)
    print(f"After merging multi-club rows: {len(p):,} player-seasons "
          f"({int((p['n_clubs'] > 1).sum())} had >1 club)")
    # A single player cannot exceed 34 x 90 = 3,060 league minutes. More than that means that two DIFFERENT players with the
    # same name and birth year (at the same or at different clubs) were merged into one row. They cannot be separated here.
    impossible = p["minutes"] > 3100
    if impossible.any():
        print(f"Excluded {int(impossible.sum())} merged player-seasons with more than 3,100 minutes (different players, same name and birth year):")
        print(p.loc[impossible, ["player", "born", "season", "team_main", "n_clubs", "minutes"]].to_string(index=False))
        p = p[~impossible].copy()
    p = build_variables(p)

    n0 = len(p)
    p = p[~p["gk_only"]]
    print(f"Removed goalkeepers: {n0 - len(p):,}")
    n1 = len(p)
    p = p[p["minutes"] >= MIN_MINUTES].copy()
    print(f"Removed < {MIN_MINUTES} minutes: {n1 - len(p):,}")

    need = TYPE1 + TYPE2
    bad = p[p[need].isna().any(axis=1)]
    if len(bad):
        print(f"\nRows with a MISSING model variable (dropped, {len(bad)} = "
              f"{len(bad) / len(p):.2%} of the panel):")
        show = ["player", "season", "team_main", "minutes", "pos_raw"] + [c for c in need if bad[c].isna().any()]
        print(bad[show].to_string(index=False))
        p = p.drop(bad.index)
    dup = p.duplicated(["pid", "season"], keep=False)
    print(f"pid+season duplicates (same name and birth year): {int(dup.sum())}")
    p = add_shrunk(p)
    p, scale = add_scaled(p)

    p.to_csv(out_dir / "panel_player_season.csv", index=False)
    scale.to_csv(out_dir / "scale_table.csv", index=False)

    print(f"\nFINAL: {len(p):,} player-seasons, {p['pid'].nunique():,} distinct players")
    print(p.groupby("season").size().to_string())
    multi = p.groupby("pid")["season"].nunique()
    print(f"\nPlayers seen in >=2 seasons: {int((multi >= 2).sum()):,}; "
          f"consecutive-season pairs possible: see clustering step")
    print("\nPosition sets (top 8):"); print(p["pos_raw"].value_counts().head(8).to_string())
    print(f"\nRows with no shots (rates set to 0): {int(p['no_shots'].sum()):,}")
    print("\nMissing values in model variables:")
    print(p[TYPE1 + TYPE2 + TYPE2_SHR + ["age", "team_ppm"]].isna().sum().to_string())
    print("\nScale table (average absolute deviation):"); print(scale.to_string(index=False))
    print(f"\nLargest minutes in the final panel: {int(p['minutes'].max()):,} (a 34-match season has at most 3,060)")
    print(f"\nSaved to {out_dir}")


if __name__ == "__main__":
    main()
