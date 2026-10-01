"""
collect_tm_v2.py  --  Transfermarkt collection, rebuilt
=======================================================
WHY: the old search-based matching linked 22 of 1,475 players (1.5%).
The tmkt search returns names with the CURRENT club glued on ("Pedro Neto
Chelsea FC"), so fuzzy name matching almost always failed.

NEW APPROACH (matching happens inside a season, so candidate pools are small):
  A. For each season, read the Primeira Liga page      -> club ids
  B. For each club-season, read the squad page          -> player ids, names, birth year
  C. Match FBref players to that season's TM pool        -> name + birth year
  D. Fetch each matched player's value history (ceapi)   -> cached, resumable
  E. Build end-of-season valuations (wide + long)

RUN (in a VS Code notebook cell, script next to the notebook):
    %run collect_tm_v2.py --test     # 1 season, 2 clubs, 3 players: checks parsing
    %run collect_tm_v2.py            # full run, resumable (re-run if it stops)

NOTE: the HTML parsing below is written from how Transfermarkt pages are laid
out, but has NOT been tested against the live site. That is what --test is for.
Every page is cached in tm_out/html/, so if parsing fails we can fix the parser
without downloading anything again.

Needs: pandas numpy requests beautifulsoup4 lxml rapidfuzz unidecode
"""

import json
import random
import re
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path

import numpy as np
import pandas as pd
import requests
from bs4 import BeautifulSoup
from rapidfuzz import fuzz
from unidecode import unidecode

TEST_MODE = "--test" in sys.argv

# FBref season code -> Transfermarkt saison_id (start year)
SEASONS = {"1718": 2017, "1819": 2018, "1920": 2019, "2021": 2020,
           "2122": 2021, "2223": 2022, "2324": 2023, "2425": 2024}
END_YEAR = {k: v + 1 for k, v in SEASONS.items()}

MIN_MINUTES = 200
SLEEP_HTML = 3.0        # seconds between page downloads (+ random 0-1)
SLEEP_API = 1.5         # seconds between value-history calls (+ random 0-0.5)
WINDOW_DAYS = 120       # accept a valuation within +/-120 days of 1 June

LEAGUE_URL = ("https://www.transfermarkt.com/primeira-liga/startseite/"
              "wettbewerb/PO1/plus/?saison_id={year}")
SQUAD_URL = ("https://www.transfermarkt.com/{slug}/kader/verein/{cid}/"
             "saison_id/{year}/plus/1")
CEAPI = "https://www.transfermarkt.com/ceapi/marketValueDevelopment/graph/{tm_id}"

HEADERS = {
    "User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                   "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.5",
    "Referer": "https://www.transfermarkt.com/",
}


def log(*a):
    print(*a, flush=True)


# ---------------------------------------------------------------- paths -----
def find_fbref():
    here = Path.cwd()
    for base in (here, here.parent, here / "test_outputs", here.parent / "test_outputs"):
        p = base / "fbref_all_seasons.csv"
        if p.exists():
            return p
    raise FileNotFoundError("fbref_all_seasons.csv not found near " + str(here))


def norm(s):
    """lowercase, strip accents/punctuation, collapse spaces"""
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9 ]", " ", unidecode(str(s)).lower())).strip()


# ------------------------------------------------------------- download -----
def get_html(session, url, cache_file):
    """Download a page once; later calls read the cached copy."""
    if cache_file.exists():
        return cache_file.read_text(encoding="utf-8")
    for attempt in range(4):
        try:
            r = session.get(url, timeout=30)
        except requests.RequestException as e:
            log(f"   network error ({e}); retry {attempt + 1}")
            time.sleep(5 * (attempt + 1))
            continue
        if r.status_code == 200 and len(r.text) > 5000:
            cache_file.write_text(r.text, encoding="utf-8")
            time.sleep(SLEEP_HTML + random.random())
            return r.text
        log(f"   HTTP {r.status_code} (len {len(r.text)}) for {url}; attempt {attempt + 1}")
        time.sleep(15 * (attempt + 1))
    return None


# -------------------------------------------------------------- parsing -----
def parse_league_clubs(html):
    """League season page -> [{club_id, slug, name}]"""
    soup = BeautifulSoup(html, "lxml")
    clubs = {}
    for a in soup.select("table.items a[href*='/startseite/verein/']"):
        m = re.search(r"/([^/]+)/startseite/verein/(\d+)", a.get("href", ""))
        if not m:
            continue
        slug, cid = m.group(1), m.group(2)
        name = a.get_text(strip=True) or a.get("title", "")
        if cid not in clubs or (name and not clubs[cid]["name"]):
            clubs[cid] = {"club_id": cid, "slug": slug, "name": name}
    return list(clubs.values())


def parse_squad(html):
    """Squad page -> [{tm_id, tm_name, birth_year}]"""
    soup = BeautifulSoup(html, "lxml")
    out = {}
    for row in soup.select("table.items > tbody > tr"):
        link = row.select_one("td.hauptlink a[href*='/profil/spieler/']")
        if link is None:
            continue
        m = re.search(r"/profil/spieler/(\d+)", link.get("href", ""))
        if not m:
            continue
        cells = " | ".join(td.get_text(" ", strip=True)
                           for td in row.find_all("td", recursive=False))
        by = re.search(r"\b((?:19|20)\d{2})\s*\(\s*\d{1,2}\s*\)", cells)
        out[m.group(1)] = {"tm_id": m.group(1),
                           "tm_name": link.get_text(strip=True),
                           "birth_year": int(by.group(1)) if by else np.nan}
    return list(out.values())


# ---------------------------------------------------------- A + B: scrape ---
def scrape_squads(session, tm_out, seasons):
    html_dir = tm_out / "html"
    html_dir.mkdir(parents=True, exist_ok=True)
    rows = []
    for fb_season in seasons:
        year = SEASONS[fb_season]
        log(f"\n[{fb_season}] league page")
        html = get_html(session, LEAGUE_URL.format(year=year), html_dir / f"league_{year}.html")
        if html is None:
            log("   !! could not download league page"); continue
        clubs = parse_league_clubs(html)
        log(f"   clubs found: {len(clubs)}")
        if TEST_MODE:
            clubs = clubs[:2]
        for c in clubs:
            url = SQUAD_URL.format(slug=c["slug"], cid=c["club_id"], year=year)
            html = get_html(session, url, html_dir / f"squad_{year}_{c['club_id']}.html")
            if html is None:
                log(f"   !! squad failed: {c['name']}"); continue
            pl = parse_squad(html)
            log(f"   {c['name'][:28]:<28} players parsed: {len(pl)}")
            for p in pl:
                rows.append({"season": fb_season, "club": c["name"], **p})
    df = pd.DataFrame(rows)
    df.to_csv(tm_out / "tm_squads.csv", index=False)
    return df


# --------------------------------------------------------- C: matching ------
def match_players(fb, tm):
    """
    Match FBref player-seasons to the TM pool of the SAME season.
    Birth year gates the candidates; the name score threshold depends on it:
      same birth year -> score >= 70 | +/-1 year -> >= 85 | unknown -> >= 92
    Then one TM id per (player, born) is chosen by majority across seasons.
    """
    tm = tm.copy()
    tm["n"] = tm["tm_name"].map(norm)
    pools = {s: g.reset_index(drop=True) for s, g in tm.groupby("season")}
    found = []
    for r in fb.itertuples():
        pool = pools.get(r.season)
        if pool is None or pool.empty:
            continue
        a = norm(r.player)
        born = r.born
        if pd.notna(born):
            cand = pool[(pool["birth_year"] - born).abs() <= 1]
            cand = pd.concat([cand, pool[pool["birth_year"].isna()]])
        else:
            cand = pool
        best, best_sc = None, 0
        for c in cand.itertuples():
            sc = max(fuzz.token_sort_ratio(a, c.n), fuzz.token_set_ratio(a, c.n) - 5)
            if sc > best_sc:
                best, best_sc = c, sc
        if best is None:
            continue
        if pd.isna(born) or pd.isna(best.birth_year):
            need = 92
        elif int(best.birth_year) == int(born):
            need = 70
        else:
            need = 85
        if best_sc >= need:
            found.append({"player": r.player, "born": born, "season": r.season,
                          "tm_id": best.tm_id, "tm_name": best.tm_name, "score": best_sc})
    m = pd.DataFrame(found)
    if m.empty:
        return m
    # one id per player: the id most often matched across seasons
    cw = (m.groupby(["player", "born", "tm_id"], dropna=False)
            .agg(n=("season", "nunique"), score=("score", "max"), tm_name=("tm_name", "first"))
            .reset_index()
            .sort_values(["player", "born", "n", "score"], ascending=[True, True, False, False])
            .drop_duplicates(["player", "born"]))
    return cw


# --------------------------------------------------------- D: value history -
def fetch_history(session, tm_id, mv_dir):
    """list of entries, [] if none, None if the call failed (retry next run)"""
    cache = mv_dir / f"{tm_id}.json"
    if cache.exists():
        try:
            return json.loads(cache.read_text(encoding="utf-8")).get("list", [])
        except Exception:
            cache.unlink()
    headers = {"Accept": "application/json, text/plain, */*",
               "X-Requested-With": "XMLHttpRequest",
               "Referer": f"https://www.transfermarkt.com/-/marktwertverlauf/spieler/{tm_id}"}
    for attempt in range(4):
        try:
            r = session.get(CEAPI.format(tm_id=tm_id), headers=headers, timeout=30)
            if r.status_code == 200:
                data = r.json()
                if isinstance(data, dict) and "list" in data:
                    cache.write_text(json.dumps(data), encoding="utf-8")
                    time.sleep(SLEEP_API + random.random() * 0.5)
                    return data["list"]
            log(f"   [{tm_id}] HTTP {r.status_code}; attempt {attempt + 1}")
        except (requests.RequestException, ValueError) as e:
            log(f"   [{tm_id}] {type(e).__name__}; attempt {attempt + 1}")
        time.sleep(10 * (attempt + 1))
    return None


# -------------------------------------------------- E: end-of-season values --
def near_season_end(history, end_year):
    target = datetime(end_year, 6, 1)
    best, best_d = None, timedelta(days=9999)
    for e in history:
        try:
            d = datetime.strptime(e["datum_mw"], "%d/%m/%Y")
        except Exception:
            continue
        gap = abs(d - target)
        if gap <= timedelta(days=WINDOW_DAYS) and gap < best_d:
            best, best_d = e, gap
    return best


def build_valuations(cw, histories):
    wide = []
    for r in cw.itertuples():
        h = histories.get(r.tm_id) or []
        rec = {"player": r.player, "born": r.born, "tm_id": r.tm_id}
        for s in SEASONS:
            e = near_season_end(h, END_YEAR[s])
            rec[f"mv_{s}"] = e["y"] if e else np.nan
            rec[f"mv_date_{s}"] = e["datum_mw"] if e else None
            rec[f"mv_club_{s}"] = e["verein"] if e else None
        wide.append(rec)
    wide = pd.DataFrame(wide)
    long = []
    for r in wide.itertuples(index=False):
        d = r._asdict()
        for s in SEASONS:
            v = d[f"mv_{s}"]
            if pd.notna(v) and v > 0:
                long.append({"player": d["player"], "born": d["born"], "tm_id": d["tm_id"],
                             "season": s, "market_value": v, "log_mv": np.log(v),
                             "mv_date": d[f"mv_date_{s}"], "mv_club": d[f"mv_club_{s}"]})
    long = pd.DataFrame(long)
    if long.empty:
        return wide, long
    order = {s: i for i, s in enumerate(SEASONS)}
    long["idx"] = long["season"].map(order)
    long = long.sort_values(["tm_id", "idx"])
    g = long.groupby("tm_id")
    long["delta_log_mv"] = (g["log_mv"].shift(-1) - long["log_mv"]).where(
        g["idx"].shift(-1) == long["idx"] + 1)
    return wide, long.drop(columns="idx")


# ----------------------------------------------------------------- main -----
def main():
    fb_path = find_fbref()
    tm_out = fb_path.parent / ("tm_out_test" if TEST_MODE else "tm_out")
    mv_dir = tm_out / "mv_raw"
    mv_dir.mkdir(parents=True, exist_ok=True)
    log(f"FBref file: {fb_path}\nOutput dir: {tm_out}\nTEST_MODE: {TEST_MODE}")

    fb = pd.read_csv(fb_path)
    fb = fb[~fb["pos"].astype(str).str.upper().str.contains("GK", na=False)]
    fb = fb[pd.to_numeric(fb["playing_time_min"], errors="coerce") >= MIN_MINUTES]
    fb = fb[["player", "born", "season", "team"]].copy()
    fb["season"] = fb["season"].astype(str).str.zfill(4)
    seasons = ["2324"] if TEST_MODE else list(SEASONS)
    fb = fb[fb["season"].isin(seasons)]
    log(f"FBref outfield player-seasons (>= {MIN_MINUTES} min): {len(fb):,}")

    session = requests.Session()
    session.headers.update(HEADERS)
    session.get("https://www.transfermarkt.com/", timeout=30)
    time.sleep(3)

    tm = scrape_squads(session, tm_out, seasons)
    if tm.empty:
        log("\n!! No TM squad players parsed. Send me tm_out/html/league_*.html "
            "(first lines) and I will fix the parser."); return
    log(f"\nTM pool: {len(tm):,} player-season rows, {tm['tm_id'].nunique():,} distinct players")

    cw = match_players(fb, tm)
    keys = fb.drop_duplicates(["player", "born"])
    n_players = len(keys)
    log(f"Matched players: {len(cw):,} of {n_players:,} ({len(cw) / max(n_players, 1):.1%})")
    if TEST_MODE:
        log(cw.head(15).to_string())
    cw.to_csv(tm_out / "player_crosswalk.csv", index=False)
    matched_keys = set(zip(cw["player"], cw["born"].fillna(-1)))
    um = keys[[(p, b if pd.notna(b) else -1) not in matched_keys
               for p, b in zip(keys["player"], keys["born"])]]
    um.to_csv(tm_out / "unmatched.csv", index=False)
    row_hit = np.mean([(p, b if pd.notna(b) else -1) in matched_keys
                       for p, b in zip(fb["player"], fb["born"])])
    log(f"Player-season match rate (what the thesis reports): {row_hit:.1%}")

    ids = cw["tm_id"].tolist()[:3] if TEST_MODE else cw["tm_id"].tolist()
    log(f"\nFetching value histories for {len(ids):,} players "
        f"(~{len(ids) * (SLEEP_API + 0.5) / 60:.0f} min; resumable)")
    histories, failed = {}, 0
    for i, tid in enumerate(ids, 1):
        h = fetch_history(session, tid, mv_dir)
        if h is None:
            failed += 1
        else:
            histories[tid] = h
        if i % 25 == 0 or i == len(ids):
            log(f"   {i}/{len(ids)} done, failed so far: {failed}")

    wide, long = build_valuations(cw[cw["tm_id"].isin(ids)], histories)
    wide.to_csv(tm_out / "mv_wide.csv", index=False)
    long.to_csv(tm_out / "mv_long.csv", index=False)
    pairs = int(long["delta_log_mv"].notna().sum()) if len(long) else 0
    log(f"\nmv_wide: {wide.shape}  mv_long: {len(long):,} rows, {pairs:,} consecutive-season deltas")
    if len(wide):
        for s in SEASONS:
            log(f"   {s}: {int(wide[f'mv_{s}'].notna().sum()):,} players with a valuation")
    json.dump({"players": n_players, "matched": len(cw), "row_match_rate": float(row_hit),
               "history_failed": failed, "long_rows": len(long), "deltas": pairs},
              open(tm_out / "summary.json", "w"), indent=2)
    log("\nDONE ->", tm_out)


if __name__ == "__main__":
    main()
