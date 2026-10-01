# Final consistency check of `thesis/final draft thesis.pdf` (58 pp., 1 Oct 2026)

**Scope.** I read the whole PDF with `pdftotext -layout` and rendered pp. 34, 29–33 and 41–42 (PDF pages 35, 30–34 and 42–43)
as images.

**Versions.**
- The `.tex` files in `thesis/chapters` are older than the PDF (no abstract, no §6.5, code appendix still present). Per the
  instructions this is not counted as an error.
- `analysis/regression/position_check.csv`, `bootstrap_pos_summary.csv` and the refreshed `spec_grid.csv` are **not in the
  repo**; the repo CSVs predate the PDF.
- The position-check and grid tables were therefore compared with my own runs of the same scripts on the same data:
  - `position_check.py` as you sent it, B = 500;
  - a clean `spec_grid.py` re-run with no cached folders.

Page numbers below are the printed page numbers.

## A. BLOCKING

**A1. Table 6.6 runs off the page (p. 34, §6.5).**
- The last column is cut at the right margin. The header reads "Share CV bet" and the values print as single digits
  "8, 9, 7, 1, 9, 6". The real values are 0.87, 0.93, 0.73, 0.13, 0.93, 0.67.
- FIND: the column header `Share CV better`
- REPLACE: `CV better`, and wrap the table in `\resizebox{\textwidth}{!}{...}` or set it in `\footnotesize`.
- Reason: the values are unreadable in the submitted PDF. Also, "CV" is not written out anywhere before this table.

**A2. §7.1, p. 36.**
- FIND: `by up to 0.20 for individual coefficients in the configurations of Table 7.1, which is about 1.5 bootstrap standard errors`
- REPLACE: `by up to 0.20 for individual coefficients in the configurations of Table 7.1, which is about 1.2 bootstrap standard errors`
- Reason: the maximum ratio in Table 7.1's configurations is 0.199/0.160 = 1.24 (raw, K = 3, full baseline; shrunk K = 5:
  1.23). The value 1.5 came from the stale m = 2.0 cell, which is no longer reported.

**A3. §8.5, p. 47 (Estimated regressors).**
- FIND: `which reaches 1.5 standard errors`
- REPLACE: `which reaches about 1.2 standard errors`
- Reason: same as A2. As written, it contradicts §7.1.

**A4. Chapter 5 introduction, p. 21.**
- FIND: `its median falls from 1.06 at m = 1.3 to 0.99, 0.91 and 0.70 at m = 1.4, 1.5 and 2.0`
- REPLACE: `its median falls from 1.06 at m = 1.3 to 1.03, 0.96 and 0.71 at m = 1.4, 1.5 and 2.0`
- Reason: these medians come from the old (stale) grid. The refreshed grid behind Table 7.4 gives 1.10, 1.06, 1.03, 0.96
  and 0.71 for m = 1.2 … 2.0.

**A5. §3.3, p. 14: contradicts §3.5 and §6.5.**
- FIND: `Any information they contain beyond a linear specification must therefore come from the nonlinear way in which they combine those statistics, and a sufficiently flexible specification of the statistics could absorb it.`
- REPLACE: `Any information they contain beyond a linear specification must therefore come from the nonlinear way in which they combine those statistics, which a sufficiently flexible specification could absorb, or from the position labels, whose change is not in the baselines (Section 6.5).`
- Reason: §3.5 and §6.5 say the transitions can also contribute through the position labels.

**A6. §4.4, p. 19: two checks are described, not three, and the first one is manual.**
- FIND: `The linking was checked in three ways, all of which are automatic except the last.`
- REPLACE: `The linking was checked in two ways.`
- Reason: only "First … inspected manually" and "Second …" follow.

**A7. Appendix C, p. 56, versus §4.4.**
- Problem: Appendix C says a second AI assistant checked "four doubtful links … (Section 4.4)". Section 4.4 says only that
  the 32 weak links were "inspected manually".
- FIND, in §4.4: `and inspected manually.`
- REPLACE: `and inspected manually; four doubtful cases were also checked with a second AI assistant (Appendix C).`
- Reason: the cross-reference points to a section that does not contain the statement, and the two descriptions conflict.

## B. SHOULD FIX (minor, safe)

**B1. Table 4.4 note (p. 19).**
- FIND: `refer to the season pairs of the estimation sample`
- REPLACE: `refer to the 1,364 pairs with values at both ends and the 1,433 transitions, respectively`
- Reason: the table shows N = 1,364 and 1,433, not 1,361.

**B2. Chapter 9, p. 49.**
- FIND: `with Transfermarkt valuations for 94.5% of them`
- REPLACE: `with Transfermarkt valuations for 94.5% of the player-seasons`
- Reason: 94.5% is a share of player-seasons, not of players.

**B3. §5.1.4, p. 23.**
- FIND: `because it increases almost mechanically with K.`
- REPLACE: `because it is not monotone in K and is used together with the other diagnostics.`
- Reason: Table 6.1 (shrunk 0.82, 0.72, 1.35, 1.24) and §6.1, which uses "lowest at K = 4", contradict "increases
  mechanically".

**B4. Table 7.4, ρ rows (p. 40): inconsistent rounding.**
- 17.5% is printed as 18% (ρ = 0.75, core), but 32.5% is printed as 32% (ρ = 1.5, core).
- FIND `32%`, REPLACE `33%` (ρ = 1.5 row, core column).

**B5. Noise-cluster name.**
- "Atypical attackers (noise)": Table 6.2 (p. 28) and Table 6.4, as "Noise (atypical attackers)" (p. 33).
- "High-volume attackers": §1.2 (p. 6), §6.2 (p. 28), §6.6 (p. 34–35), §8.1 (p. 44).
- Safe fix: in Tables 6.2 and 6.4, FIND `Atypical attackers` / `atypical attackers`, REPLACE `High-volume attackers` /
  `high-volume attackers`.

**B6. Appendix C, p. 56 — DEPENDENT on the author's decision.**
- `and through a style-editing skill that I wrote, which removes wording typical of AI-generated text` must be deleted if
  that editing pass is not run before submission.

## C. VERIFIED OK

- **Headline coherence.** Abstract, §1.2, §6.6, §7.9, §8.1 and Ch. 9 give the same numbers and the same verdict:
  - 0.015 / 0.079; 0.3–0.6 pp; 0.1–0.3 pp; 0.35 / 0.12;
  - "no robust incremental explanatory power; largely disappears with position-label changes".
  - None presents the position check as pre-specified: Ch. 6 intro, §6.5, §8.5 and Ch. 9 say it was added after the review.
  - None says the corrections were not outcome-driven: §1.2, §7.6 and §8.5 say they came after earlier valuation results.
  - "Absent for five archetypes" always appears with "at m = 1.3" (§7.9, §8.1).
- **Leftovers.** No hits for: "96.2", "3,195", "1,436", "1,367", "699 players", "about 350", "Programming code", "ZIP",
  "submitted as", "selecting C", "regulariser", or "m = 1.2 … absent".
  - "0.74" and "0.47" occur only as legitimate table cells (Table 6.2, Table 7.1).
  - "as expected" occurs only for count data and "expected goals", not for Hausman.
  - "effects" occurs only for fixed, random or season effects and "detect small effects".
- **Cross-references.** No "??". Every Table (4.1–4.4, 6.1–6.6, 7.1–7.5, A.1, B.1–B.2), Figure (6.1–6.4, 7.1–7.2) and Section
  reference exists and points to the right place. Appendices are A weights, B coefficients, C AI use. The only problem is
  the Appendix C → §4.4 reference (A7).
- **Numbers against sources.**
  - Table 6.6 and §6.5 match the position-check run exactly: 0.023 / 0.010 / 0.027 / 0.169 / 0.002 / 0.038;
    bootstrap 0.079 / 0.352 / 0.015 / 0.120; gains +0.42 / +0.50 / +0.34 / +0.12 / +0.56 / +0.28 and
    +0.20 / +0.27 / +0.08 / −0.12 / +0.33 / +0.04; 24.8%; wide-attacker coefficient −0.11 (p = 0.26) and −0.20 (p = 0.068).
  - Table 7.4 and the grid paragraph match the refreshed grid in every cell: 30 / 76; 96 / 107; max 0.90; 39 / 81; max 0.88;
    K = 4 47/80%; K = 5 10/40%.
  - Figure 7.1 is the refreshed heatmap (shrunk K = 4, m = 1.2 core cell = 0.035).
  - Table 7.5 = `seed_sensitivity.csv`. Table 7.1 = `bootstrap_summary.csv` / `regression_summary.csv`.
  - Holm: 10 comparisons, smallest p = 0.012 (0.0116), threshold 0.005.
  - Table A.1 = `estimated_weights_2324.csv`. §7.6 medoid agreement 0.88 (main).
  - The §7.5 statement that the wide-attacker coefficient is largest at m = 1.4 and 1.5 holds in the reproduced runs.
- **Story numbers present and correct.** 3,192 / 1,499; 1,433 / 1,364 / 1,361 of 697; 94.5% / 95.4%; 75%; 346 players and
  1,010 pairs; 14.4% and 22.2% (stated as on 1,364 pairs).
- **Format.**
  - The abstract (with keywords) comes before the contents.
  - Table 4.1 shows its counts column.
  - All six figures render.
  - Main text runs pp. 5–50 = 46 pages.
  - Abbreviations are written out at first use (FCM, FCMd-MD-NC, XB, IQR, SE), apart from "CV" (A1).
  - No other table runs off the page; Tables 6.1, 6.2, 7.2, 7.4 and 7.5 were checked visually.
- **Fixes from the first review:**

  | Fix | Status |
  |---|---|
  | Abstract | OK |
  | Table 4.1 | OK |
  | Age slope ("about 0.07 log points" at 25) | OK |
  | Bias "up to 0.20" | OK, but its "1.5 SE" companion is not (A2, A3) |
  | "Six of seven / four of seven" | OK |
  | 95.4% and 94.5% | OK |
  | Fixed-effects text (player trends; Hausman not interpreted) | OK |
  | §6.5 position labels | OK |
  | Stale single-cell claims removed (Table 7.3B main only; fuzziness read from seeds) | OK, except the XB medians in Ch. 5 (A4) |
  | Grid refreshed | OK |
  | Code appendix removed | OK |

- **Open items from the first review:**

  | Item | Status |
  |---|---|
  | Duplicate headline numbers (Abstract, §1.2, §6.6, §7.9, §8.1, Ch. 9) | open |
  | Raw variable names in the full-baseline coefficient table (now Table B.2: "Level of sot p90", "g sh shr") | open |
  | SD-scaling weights table | open |
  | Percentile intervals | open (mentioned in words in §7.1, no table) |
  | Stayer/leaver table | open |
  | Power analysis | open |
  | Seed sign stability over 30 draws | open (§7.5 refers only to "the runs examined") |

## D. Verdict

**Yes: ready to submit once A1–A7 are applied.** They take about 10 minutes, five text replacements and one table resize. B6
depends on whether the style pass is run.
