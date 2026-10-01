"""
crosswalk_audit.py -- list the weakest FBref <-> Transfermarkt matches so wrong ones can be rejected
====================================================================================================
    %run crosswalk_audit.py

The matcher accepts a name score of 70 when the birth year agrees, so a few different players with
similar names (Paulinho / Carlinhos) can be linked. Wrong links give a player someone else's
valuations. This prints every match whose name score is below 92, with both sides' details, so you
(you know Portuguese football) can spot the wrong ones.

To reject a match, add its line to  tm_out/crosswalk_reject.csv  with columns  player,born  and
re-run make_analysis_panel.py. Rejected players simply lose their valuation (they are not guessed).
"""
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path.cwd()))
sys.modules.pop("build_panel", None)
from build_panel import find_fbref          # noqa: E402

base = find_fbref().parent
panel = pd.read_csv(base / "panel" / "panel_player_season.csv")
cw = pd.read_csv(base / "tm_out" / "player_crosswalk.csv")
sq = pd.read_csv(base / "tm_out" / "tm_squads.csv")
for d in (panel, sq):
    d["season"] = d["season"].astype(str).str.zfill(4)

fb = (panel.groupby(["player", "born"], dropna=False)
      .apply(lambda g: pd.Series({"fbref_clubs": ", ".join(sorted(set(g["team_main"]))),
                                  "seasons": ",".join(sorted(g["season"].str[2:]))}), include_groups=False)
      .reset_index())
tm = (sq.groupby("tm_id").agg(tm_name=("tm_name", "first"), tm_born=("birth_year", "first"),
                              tm_clubs=("club", lambda x: ", ".join(sorted(set(x))))).reset_index())
m = cw.merge(fb, on=["player", "born"], how="left").merge(tm[["tm_id", "tm_born", "tm_clubs"]], on="tm_id", how="left")
weak = m[m["score"] < 92].sort_values("score")
print(f"{len(cw):,} matches; {len(weak):,} with a name score below 92 ({len(weak) / len(cw):.1%})\n")
pd.set_option("display.width", 250, "display.max_colwidth", 42)
print(weak[["score", "player", "born", "fbref_clubs", "seasons", "tm_name", "tm_born", "tm_clubs"]]
      .head(80).to_string(index=False))
weak.to_csv(base / "tm_out" / "crosswalk_weak_matches.csv", index=False)
print(f"\nAll weak matches saved to {base / 'tm_out' / 'crosswalk_weak_matches.csv'}")
