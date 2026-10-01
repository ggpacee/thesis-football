"""
make_analysis_panel.py  --  attach Transfermarkt valuations to the player-season panel
======================================================================================
    %run make_analysis_panel.py

Inputs : panel/panel_player_season.csv          (build_panel.py)
         tm_out/player_crosswalk.csv, tm_out/mv_long.csv   (collect_tm_v2.py)
Output : panel/analysis_panel.csv

WHAT IT DOES
  1. Links each FBref player-season to a Transfermarkt id (name + birth year key).
  2. Defines ONE player identity, `uid`: the Transfermarkt id when there is one (so a player
     whose name FBref spells differently across seasons is still one player), else name+birth.
  3. Attaches the end-of-season valuation (value nearest 1 June, within +/-120 days).
  4. Builds the outcome for a season pair (t, t+1): delta_log_mv = log MV(t+1) - log MV(t).
     A pair exists only if the player has >= 200 league minutes in BOTH seasons, which is
     what keeps players who left the Primeira Liga out of the valuation analysis.
  5. Flags club changes between t and t+1 (a within-league move changes value for reasons
     unrelated to style).
It prints every check it makes; nothing is dropped silently.
"""
import sys
from pathlib import Path

import re
from itertools import combinations

import numpy as np
import pandas as pd
from rapidfuzz import fuzz
from unidecode import unidecode

sys.path.insert(0, str(Path.cwd()))
for _m in ("build_panel",):
    sys.modules.pop(_m, None)
from build_panel import find_fbref          # noqa: E402


def norm(x):
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9 ]", " ", unidecode(str(x)).lower())).strip()


base = find_fbref().parent
panel = pd.read_csv(base / "panel" / "panel_player_season.csv")
cw = pd.read_csv(base / "tm_out" / "player_crosswalk.csv")
mv = pd.read_csv(base / "tm_out" / "mv_long.csv")
for d in (panel, mv):
    d["season"] = d["season"].astype(str).str.zfill(4)
seasons = sorted(panel["season"].unique())
order = {s: i for i, s in enumerate(seasons)}
print(f"panel {len(panel):,} rows | crosswalk {len(cw):,} | valuations {len(mv):,}")

# 1. crosswalk -> panel ------------------------------------------------------------------
panel["born_k"] = panel["born"].fillna(-1)
cw["born_k"] = cw["born"].fillna(-1)
rej_path = base / "tm_out" / "crosswalk_reject.csv"          # optional: (player, born) pairs you judged wrong
if rej_path.exists():
    rej = pd.read_csv(rej_path)
    bad = set(zip(rej["player"], rej["born"].fillna(-1)))
    hit = [(a, b) in bad for a, b in zip(cw["player"], cw["born_k"])]
    print(f"crosswalk_reject.csv: removing {int(sum(hit))} matches you rejected")
    cw = cw[[not h for h in hit]]
dup_keys = cw.duplicated(["player", "born_k"], keep=False)
print(f"crosswalk rows sharing the same (player, born): {int(dup_keys.sum())}")
cw = cw.sort_values("score", ascending=False).drop_duplicates(["player", "born_k"])
shared = cw[cw.duplicated("tm_id", keep=False)].sort_values("tm_id")
print(f"Transfermarkt ids matched to MORE THAN ONE FBref (player, born) key: "
      f"{shared['tm_id'].nunique()} ids / {len(shared)} keys")
panel = panel.merge(cw[["player", "born_k", "tm_id", "score"]], on=["player", "born_k"], how="left",
                    validate="m:1")

# Two FBref spellings can be ONE person (spelling changes between seasons -> unify) or TWO people
# (a nickname like "Ricardo" or "Eduardo" matched to the same Transfermarkt profile). They cannot be
# one person if both appear in the SAME season, so those are split: the best match (score, then
# minutes) keeps the Transfermarkt id, the others are left unmatched rather than given a wrong value.
same_person, split = [], []
counts = panel[panel["tm_id"].notna()].groupby("tm_id")["pid"].nunique()
for tid in counts[counts > 1].index:
    g = panel[panel["tm_id"] == tid]
    names = list(g.groupby("pid")["player"].first())
    born = g.groupby("pid")["born"].first().dropna()
    # identical names (e.g. two 'Marcao' born in different years) count as similarity 100
    name_sim = min((fuzz.token_set_ratio(norm(a), norm(b)) for a, b in combinations(names, 2)), default=100)
    same_season = g.duplicated("season", keep=False).any()
    # one person only if: never two spellings in one season, names clearly alike, birth years within 1
    one_person = (not same_season) and name_sim >= 90 and (len(born) == 0 or born.max() - born.min() <= 1)
    if one_person:
        same_person.append((tid, sorted(set(g["player"]))))
    else:
        rank = (g.groupby("pid").agg(score=("score", "max"), minutes=("minutes", "sum"))
                 .sort_values(["score", "minutes"], ascending=False))
        panel.loc[(panel["tm_id"] == tid) & (panel["pid"] != rank.index[0]), ["tm_id", "score"]] = np.nan
        split.append((tid, sorted(set(g["player"]))))
print(f"  -> {len(same_person)} ids = one person spelled differently in different seasons (unified)")
print(f"  -> {len(split)} ids = different people (same season, or clearly different names): split; the weaker match loses its id")
for tid, names in split:
    print(f"       split  {tid}: {names}")
for tid, names in same_person[:8]:
    print(f"       unified {tid}: {names}")

# 2. identity ---------------------------------------------------------------------------------
panel["uid"] = np.where(panel["tm_id"].notna(), "tm" + panel["tm_id"].astype("Int64").astype(str), panel["pid"])
print(f"players: {panel['pid'].nunique():,} name+birth keys -> {panel['uid'].nunique():,} unified uids")

# 3. valuations ---------------------------------------------------------------------------------
n_mv = len(mv)
mv = mv.drop_duplicates(["tm_id", "season"]).copy()
if len(mv) < n_mv:
    print(f"dropped {n_mv - len(mv)} duplicate (tm_id, season) valuation rows")
panel["tm_id"] = panel["tm_id"].astype(float)
mv["tm_id"] = mv["tm_id"].astype(float)
panel = panel.merge(mv[["tm_id", "season", "market_value", "log_mv", "mv_date", "mv_club"]],
                    on=["tm_id", "season"], how="left", validate="m:1")

# 4. one row per (uid, season) ------------------------------------------------------------------
dup = panel.duplicated(["uid", "season"], keep=False)
if dup.any():
    print(f"\n{int(dup.sum())} rows share (uid, season): the same player under two FBref spellings in one "
          "season. Keeping the row with most minutes. Examples:")
    print(panel[dup].sort_values(["uid", "season"])[["uid", "player", "season", "team_main", "minutes"]]
          .head(10).to_string(index=False))
    panel = panel.sort_values("minutes", ascending=False).drop_duplicates(["uid", "season"])

# 5. season pairs -----------------------------------------------------------------------------------
panel["sidx"] = panel["season"].map(order)
panel = panel.sort_values(["uid", "sidx"]).reset_index(drop=True)
g = panel.groupby("uid")
nxt_sidx, nxt_lmv, nxt_team = g["sidx"].shift(-1), g["log_mv"].shift(-1), g["team_main"].shift(-1)
panel["has_next"] = nxt_sidx == panel["sidx"] + 1
panel["delta_log_mv"] = np.where(panel["has_next"], nxt_lmv - panel["log_mv"], np.nan)
panel["club_change_next"] = np.where(panel["has_next"], (nxt_team != panel["team_main"]).astype(float), np.nan)
panel["season_next"] = np.where(panel["has_next"], panel["sidx"].add(1).map({v: k for k, v in order.items()}), None)

panel.drop(columns=["born_k"]).to_csv(base / "panel" / "analysis_panel.csv", index=False)

# report -------------------------------------------------------------------------------------------
print(f"\nFINAL: {len(panel):,} player-seasons, {panel['uid'].nunique():,} players")
cov = panel.groupby("season").agg(rows=("uid", "size"), has_tm_id=("tm_id", lambda s: s.notna().mean()),
                                  has_value=("log_mv", lambda s: s.notna().mean()))
print(cov.round(3).to_string())
pairs = panel[panel["has_next"]]
ok = pairs["delta_log_mv"].notna()
print(f"\nconsecutive-season pairs (both seasons >= 200 league minutes): {len(pairs):,}")
print(f"  of which with a valuation in both seasons (the regression sample): {int(ok.sum()):,}")
print(pairs.assign(ok=ok).groupby("season").agg(pairs=("uid", "size"), with_delta=("ok", "sum")).to_string())
d = pairs["delta_log_mv"].dropna()
print(f"\ndelta_log_mv: mean {d.mean():.3f}, sd {d.std():.3f}, p1 {d.quantile(.01):.2f}, "
      f"p99 {d.quantile(.99):.2f}, share exactly 0: {(d == 0).mean():.1%}")
print(f"pairs where the player changed club within the league: {pairs['club_change_next'].mean():.1%}")
print(f"\nSaved {base / 'panel' / 'analysis_panel.csv'}")
