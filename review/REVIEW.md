# Review: "Tracking Player Profile Evolution Through Robust Fuzzy Clustering" (thesis text + code)

Reviewer's position: supervisor / second-assessor reading of `thesis/` (main.tex, chapters, compiled `main.pdf`) and `analysis/`.
Everything marked "verified" was checked against the files in this repository, and re-runs were made in a scratch copy
(`review/scratch/`). "Opinion" marks judgement. `docs/` is not in this checkout, so the papers, the thesis manual and the
supervisor's annotated proposal could not be read (see "Could not verify" at the end).

---

## 1. Verdict

A careful, unusually honest thesis with a clean pipeline: 73 of 98 audited claims match their sources, and the panel and main
regressions re-run bit-for-bit. It passes; I expect **about 7–7.5**, and 8 is possible if the issues below are fixed or
openly acknowledged. The three things most likely to hurt the grade:

1. **Stale sensitivity results (C1).** 88/120 grid cells and 5/10 bootstrap configurations are not reproduced by the submitted
   code. Corrected, m = 1.2 is significant (bootstrap p = 0.050 / 0.013) and m = 2.0 is not (0.32 / 0.13), the reverse of
   what the thesis says.
2. **Position-label changes are omitted from both baselines (C2).** With them added, the main result is gone: bootstrap
   p = 0.35 (core) and 0.12 (full).
3. **Visible errors (C3, C4):** no abstract; the counts of Table 4.1 run off the page; the age coefficient is misread.

---

## 2. Critical issues

Format: location → problem → evidence → fix → fixable tonight?

### C1. The sensitivity analyses at m ≠ 1.3 (and at ρ ≠ 1.0) come from stale clustering folders and are not reproducible
- **Location.** Ch. 7 Tables 7.3B, 7.4 and 7.5, Fig. 7.1, Sections 7.5–7.6, Appendix C Table C.3. The statement "absent for
  near-crisp memberships (m = 1.2)" also appears in Ch. 1 §1.2, §7.9, §8.1–8.2 and Ch. 9.
- **Problem.** `spec_grid.py::ensure_clustering` (l. 58–62) and `sensitivity_and_benchmark.py` (l. 65) re-use any existing
  `clustering_sens_rho*_m*/` folder without checking that it was made with the current panel and code. `bootstrap.py`
  (`folder_for`, l. 99–100), `extra_results.py` (l. 157) and `alignment_check.py` read the same folders. The thesis says
  (§7.6, italic) that *"all results in Chapters 6 and 7, including the specification grid and the bootstrap, were recomputed"*.
  For most cells that is not what the stored files contain.
- **Evidence (verified by re-running in `review/scratch/analysis_copy`).**
  - Re-clustering with the current code and panel, seed 0, through exactly the path of `spec_grid.py` reproduces the main cell
    to 1e-12. It does not reproduce the other cells (shrunk, K = 4, ρ = 1.0; conventional Wald p, core / full):

    | m | stored in `spec_grid.csv` | re-run (current code) |
    |---|---|---|
    | 1.2 | 0.292 / 0.102 (ΔR̄² +0.09 / +0.18; ΔR²oos −0.22 / −0.07) | **0.035 / 0.005** (+0.29 / +0.47; +0.02 / +0.23) |
    | 1.4 | 0.00450 / 0.00041 | 0.00445 / 0.00041 (close, not identical) |
    | 1.5 | 0.0010 / 0.0001 (wide coef −0.31 / −0.41) | 0.0001 / 0.00004 (wide coef −0.29 / −0.37) |
    | 2.0 | 0.048 / 0.011 | 0.181 / 0.048 (and the reference archetype changes to no. 4) |

  - The author's own `regression/seed_sensitivity.csv` (seed 0 = the same draw) agrees with the re-run, not with the grid:
    m = 1.2 seed 0 gives 0.0350 / 0.0048.
  - Full grid re-run: only 32 of 120 cells are identical, those of (ρ = 1.0, m = 1.3) and (ρ = 1.5, m = 1.4, 1.5, 2.0). The
    other 11 (ρ, m) folders were stale. Pooled summaries hardly move (core significant 34 → 30 of 120; full 74 → 76; medians
    of the gains unchanged to ±0.02 pp). Cells and sub-groups do move: K = 5 full 30 % → 40 %; ρ = 0.75 core 28 % → 18 %;
    shrunk full 53 % → 62 %.
  - **Two-stage bootstrap re-run with the regenerated folders (500 replications, same code), core / full:**

    | m | Table 7.4 | corrected |
    |---|---|---|
    | 1.2 | 0.445 / 0.277 | **0.050 / 0.013** |
    | 1.5 | 0.029 / 0.008 | 0.008 / 0.004 |
    | 2.0 | 0.088 / 0.019 | **0.318 / 0.126** |

    m = 1.3 is unchanged (0.079 / 0.015). m = 1.4 was not re-bootstrapped; its conventional p barely moves.
  - Medoid position agreement (§7.6) with fresh folders: 0.94 / 0.88 / 0.84 / 0.69 / 0.56 for m = 1.2 … 2.0. The thesis has
    0.88 / 0.88 / 0.84 / 0.75 / 0.59.
- **Consequence.** The qualitative bottom line, weak and specification-dependent evidence, survives. The specific story
  "absent with near-crisp memberships (m = 1.2), present from m = 1.3 on" does not, and neither does the §8.2 conjecture
  built on it (crisp memberships discard graded information). With reproducible runs, the full-baseline test is significant
  from m = 1.2 to 1.5 and absent at m = 2.0. The seed analysis (`seed_sensitivity.py`, which always re-clusters) is
  unaffected and should carry the m-story: there, m = 1.2 and m = 2.0 are both weaker than 1.3–1.5.
- **Fix.**
  1. Delete `clustering_sens_*`.
  2. Re-run `spec_grid.py` (10–15 min), `sensitivity_and_benchmark.py`, `alignment_check.py`, `extra_results.py`, then
     `bootstrap.py` for the 5 affected configurations (~3 min each on 4 cores here), then `make_tables_figures.py`.
  3. Update Tables 7.3B, 7.4, 7.5, Fig. 7.1, Table C.3, §7.5–7.6 and every "absent at m = 1.2" sentence.
  4. Add a guard to `ensure_clustering`: store the panel hash and settings in the folder, and re-run when they differ.
  5. Base the m-narrative on Table 7.6 (30 draws per m), not on single cells.
- **Fixable tonight?** Yes: ≈1 h compute and ≈1 h rewriting. If not done, at minimum add a footnote that the grid cells
  were produced with an earlier panel version and that the seed analysis is the reliable evidence.

### C2. The baselines omit the change in the position labels, which the memberships contain
- **Location.** §3.5 ("The memberships are constructed from twelve performance statistics …", "Against the full baseline,
  the transitions can contribute only through the nonlinear way in which they combine these statistics"), §5.4.1, §6.4,
  §7.3, §8.2; `pairs_lib.py` l. 15–17 and l. 31, 66–68.
- **Problem.** The clustering uses three position indicators with weight 0.275, i.e. 3/15 of d² (Table 4.3, §5.1). The core
  baseline contains only the *levels* `pos_DF` and `pos_FW` at t. Neither baseline contains `pos_MF` or the *change* in any
  position label between t and t+1. A change of FBref label (e.g. DF → DF,MF) mechanically moves memberships. So Δu
  contains observable, linear information that is not in the "full" baseline, and the central identification argument of §3.5
  is false as written.
- **Evidence (verified; `review/scratch/position_check.py`, `nonlinear_check.py`; stored memberships, cluster-robust).**
  - 24.8 % of the 1,361 pairs change position label.
  - Position-label changes alone, added to core: p = 0.023, ΔR̄² **+0.42 pp**, which is more than Δu's +0.34 pp, and
    ΔR²oos +0.20 pp.
  - Δu added to core + position changes: **p = 0.169**, ΔR̄² +0.12 pp, ΔR²oos **−0.12 pp** (better in 13 % of CV
    repetitions).
  - Δu added to full + position changes: **p = 0.038**, ΔR̄² +0.28 pp, ΔR²oos +0.04 pp. Wide-attacker coefficient −0.20
    (SE 0.097).
  - **Two-stage bootstrap with the position controls in the baseline** (main configuration, 500 replications,
    `review/scratch/analysis_copy3/bootstrap_pos.py`):
    - joint Wald **p = 0.352 (core)** and **p = 0.120 (full)**;
    - wide-attacker coefficient −0.113 (bootstrap p = 0.26) against core and −0.202 (p = 0.068) against full.
    - **Neither the joint test nor any coefficient remains significant at 5 %.**
  - By contrast, adding the squares of all 24 statistic terms to the full baseline does not absorb Δu (p = 0.002). The
    "extra" information in Δu is largely the position label, not nonlinearity in the statistics.
  - The defender → wide-attacker coefficient is identified by about 40 pairs with Δu_wide > 0.1 and Δu_def < −0.1. Only 7 are
    crisp DEF → WIDE moves. They are mostly full-backs gaining the MF label (DF → DF,MF: 13; DF → DF: 8). Their raw mean
    Δln V is +0.19, against +0.07 overall, so the negative coefficient is purely conditional on the controls.
- **Fix.**
  - Add `pos_MF` and the changes of the three indicators to the core block (`pairs_lib.py` l. 31, 34, 66). The patch is reproduced under "Commands run".
  - Re-run `regression.py`, `robustness.py`, `bootstrap.py` for the main configuration (the bootstrap with position controls
    is reported in §5; ≈3–10 min), `seed_sensitivity.py`, and ideally `spec_grid.py`.
  - Rewrite §3.5 and the conclusion. Alternatively, keep the current baselines but add a "core/full + position changes" row to
    Tables 6.5 and 7.2 and say plainly that the association largely disappears against core.
- **Fixable tonight?** Yes for the regressions and the main-configuration bootstrap (≈1 h including text). Re-running the
  grid and seeds with the new baseline takes another ≈30 min compute.

### C3. Format defects visible on the first read
- **No abstract.** `main.tex` goes from the title page straight to the table of contents. An MSc thesis at ESE is, to my
  knowledge, expected to have an abstract (and usually keywords). Check the manual in `docs/`, which I could not read.
  Fix: 150–200 words. 20 min.
- **Table 4.1 is cut off in `main.pdf` (p. 16).** The first column is an `l` column with long text, so the column
  "Rows or player-seasons" (all the counts) is printed outside the page and is invisible. Verified by rendering the page.
  Fix: `\begin{tabular}{p{11.5cm}r}` or `tabularx`. 5 min.
- Fixable tonight? Yes.

### C4. Wrong statements of results (each small, but each is an "error" an examiner can tick)
| Location | Text | Correct | Source |
|---|---|---|---|
| §6.4.1 | "Value growth falls with age (a coefficient of −0.16 per year, with a small positive curvature)" | −0.162 is the slope at age 0; with age² = +0.0019 the slope is **−0.067 per year at 25** (−0.082 at 21, −0.051 at 29); turning point 42.5 | `coef_core_m1.3.csv`; recomputed |
| §6.4.1 | "The coefficients (Appendix C, Table C.1) have the expected signs" (describing the *baseline*) | Table C.1 is the *extended* model (with Δu) | `extra_results.py` l. 184–198 |
| §7.1 | bootstrap means differ "by up to 0.17 … in the direction of zero" | max \|bias\| = **0.25** (m = 2.0, full), 0.20 (raw K = 3, full); up to 1.5 bootstrap SEs; 46 of 78 coefficients toward zero | `bootstrap_summary.csv` col. `max_abs_bias` |
| §7.2 | "significant at 5 % in seven of the eight variations … core in five of eight" | the first row is the main sample, not a variation: **6 of 7** (full) and **4 of 7** (core) | `robustness_checks.csv` |
| §4.4, §8.5 | "96.2 % of the player-seasons" linked | 96.2 % is at the collection step (1,507 raw club-row keys); in the analysis sample **95.4 %** have a Transfermarkt id | `tm_out/summary.json`; `analysis_panel.csv` |
| §5.1.2 | positions took "76 to 91 %" | 76.2, 87.1, 90.5 % → "76 to 90 %" | `estimated_weights_2324.csv` |
| Ch. 9 | values "for 94 % of them" | 94.5 % (Ch. 4) | `sample_by_season.csv` |
| Table 4.2 note | season pairs "form the estimation sample" | total is 1,364; the estimation sample is 1,361 | `sample_by_season.csv` |

Fixable tonight: yes, 20 min.

### C5. Fixed effects and the Hausman test are misinterpreted and computed with non-robust covariances
- **Location.** §5.4.3, §6.4.3; `robustness.py` l. 98–135.
- **Problem.**
  1. The outcome is already a first difference (Δln V). Time-invariant talent or reputation *levels* are differenced out
     before any fixed effect is added. Player FE in this model absorb player-specific *growth rates*, i.e. trends. The code
     docstring says this correctly (l. 19); the thesis text does not ("talent, reputation or injury history may be
     correlated with both memberships and values").
  2. The Hausman statistic uses `cov_type="unadjusted"` for both FE and RE (l. 111–115), while the data are clustered and
     heteroskedastic. It compares all coefficients including season dummies, and `max(H, 0)` hides a possibly
     non-positive-definite difference. p = 0.000 is therefore not informative.
  3. Age is dropped from RE as well as FE. The RE model without age is misspecified, which by itself drives a rejection.
  4. Only age, not age², is collinear with player and season effects (age² = b² + 2bt + t² varies within player).
- **Fix.** Rewrite §5.4.3 and §6.4.3: FE = player-specific value trends, estimated from the 346 players with at least two
  pairs (1,010 pairs). Replace the Hausman test by a cluster-robust Mundlak (correlated-RE) test, or drop the claim "the
  Hausman test rejects … as expected". Keep the FE result: p = 0.018 / 0.001.
- **Fixable tonight?** Text: yes (20 min). Robust Mundlak test: 30–45 min.

---

## 3. Thesis review (Phase 1.2)

### 3.1 Argument
- The chain RQ → theory → data → method → results → discussion holds. Ch. 3 is a genuinely good chapter: it states the
  null, the reading of coefficients (0.10 shift), and why transitions might *not* add anything. Ch. 7 is an exemplary
  sensitivity chapter for an MSc.
- **The weak link is §3.5**, the claim that the full baseline leaves only "nonlinear aggregation" for Δu to contribute. It is
  false because of positions (C2), and the PCA benchmark (linear, against core only) cannot test it. After C2, the honest
  answer to the main RQ is: *no robust incremental explanatory power; at most a small conditional association, much of which
  reflects changes in FBref position labels*.
- **Theory ↔ results.** The three mechanisms of §3.2 (forward-looking, role-specific, nonlinear aggregation) are never tested
  against each other. The discussion (§8.2) offers three new, untested explanations for the defender → wide-attacker sign.
  That is fine if labelled as conjecture, but the role-specific mechanism could be examined directly: interact Δu with age,
  or check whether the effect is driven by full-backs gaining the MF label (C2).

### 3.2 Honesty and caution (over- and under-claiming)
- Strong points: the earlier run (p = 0.70 / 0.36) is reported (§7.7); the 30-draw seed analysis; the Holm correction; and
  "the run reported in Chapter 6 is a favourable draw". Keep all of this.
- Over-claiming remains in places:
  - §7.9 "robust to the definition of the sample and the outcome, to player fixed effects, and to the inclusion or exclusion
    of performance controls". All of these are conventional p-values, and the COVID and stayers variations fail.
  - §6.4.2 "it is the direction of the movement, and not its size or the starting point, that is associated with the change
    in value". This compares a 4-df block with 1-df summaries in a single draw.
  - §7.3 "The membership changes are therefore not proxies for goals and assists". True, but the more relevant proxy is
    position change (C2).
  - §8.1 "In the main configuration the answer is a qualified yes".
- "Fixed before the valuation stage was estimated" (§1.2, §5 intro, §6.1). True for (K, m, ρ). But the alignment method and the
  data were changed *after* valuation results had been seen; the `spec_grid.py` docstring (l. 6–7) still records the earlier
  null result. Say so in Ch. 1, not only in §7.7 and §8.5. Also, Table 6.1 is computed with the *later* profile alignment, so
  it is not literally the table on which K was chosen.
- §7.6 "This is a correction of the method made because of the label check and not because of any outcome." This cannot be
  shown, because the check was run after the null result. Rephrase: "The correction was triggered by the label check; it
  was made after earlier valuation results had been seen, which is why those results are reported."
- Under-claiming: none of substance. The descriptive contribution (RQ1) is undersold. The archetypes, persistence matrix and
  medoids are clean and reproducible and could be the thesis's main positive finding.

### 3.3 Writing, terminology, format
- Prose is clear, formal and economical. The main weakness is **repetition**: the headline numbers (0.015 / 0.079, +0.34 /
  +0.56, 0.08 / 0.33, 60 % / 37 %) appear almost verbatim in §1.2, §6.5, §7.9, §8.1 and Ch. 9. The RQ block is quoted twice
  verbatim (§1.1 and §2.5). Cut §2.5 to a cross-reference and shorten §6.5 and §7.9.
- Terminology is mostly consistent: core/full, K/m/ρ, archetype names. Exceptions:
  - "C" in §5 intro ("selecting C and m") should be K.
  - The noise cluster is "atypical attackers" in the tables and "high-volume attackers" in the text. Pick one.
  - "effects" is used for associations (§6.4.1 "The effects of assists …", §8.5 "effects may be understated"). Use
    "associations" or "coefficients", in line with the stated non-causal objective.
- Abbreviations are written out at first use (FCM, FCMd-MD-NC, XB, IQR in the note). Fine. `\cite` vs `\citeA` usage is
  correct throughout (42 uses checked).
- Format (verified in `main.pdf`, 58 pp.; main text pp. 4–49 = 46 pages, within the 40–50 target):
  - no abstract (C3);
  - Table 4.1 cut off (C3);
  - Table C.2 prints raw variable names ("Level of sot p90", "Level of g sh shr"); fix the label map in
    `extra_results.py::label`;
  - Appendix C describes the m = 1.5 numbering, but no m = 1.5 table is included, and the full-baseline m = 1.4 table is
    missing;
  - Fig. 7.1 shows 80 of the 120 specifications (ρ = 0.75 is not plotted), while the caption says "across the specification
    grid";
  - Table 4.2's "Players" column equals "Player-seasons" in every season row (redundant);
  - Table 7.3's column headers are misaligned.
- Unsupported factual claim: "a league that supplies many players to the larger leagues" (§1.1, §2.1). Add a source, e.g.
  Franceschi et al. on Benfica/Porto, which is already cited in §2.1.

### 3.4 The 15 worst passages, with fixes

1. **§3.5.** "The memberships are constructed from twelve performance statistics … Against the full baseline, the transitions
   can contribute only through the nonlinear way in which they combine these statistics, which is exactly the claim in
   Section 3.2."
   → "The memberships are built from twelve statistics and three position labels. The full baseline contains the levels and
   changes of all fifteen, so against it the transitions can contribute only through the nonlinear, league-relative way in
   which the clustering combines them." (Requires the C2 fix.)
2. **§6.4.1.** "Value growth falls with age (a coefficient of −0.16 per year, with a small positive curvature)"
   → "Value growth declines with age: at the mean age of 25, one more year is associated with value growth about
   6.7 log points lower, and the decline flattens with age."
3. **§7.5.** "With near-crisp memberships (m = 1.2) there is no association after the bootstrap (p = 0.45 and 0.28)."
   → Replace with the re-run numbers (C1). Then: "Single runs differ by orders of magnitude between draws (Section 7.7), so
   the dependence on m is read from Table 7.6: the full-baseline test is significant in 40 % of draws at m = 1.2, 60–73 % at
   1.3–1.5, and 43 % at 2.0."
4. **§1.2 / §7.9 / §8.1 / Ch. 9.** "It is absent for near-crisp memberships and for five archetypes."
   → "It is weaker for near-crisp and for near-uniform memberships (in the distribution over random draws) and for five
   archetypes."
5. **§7.1.** "by up to 0.17 for individual coefficients … The bootstrap corrects the standard errors but not this
   attenuation, so the point estimates should be read as conservative."
   → "by up to 0.25 (1.5 bootstrap standard errors) … A bootstrap distribution this far from the estimate means that normal
   intervals centred on the estimate and percentile intervals can disagree. For the wide-attacker coefficient against the
   core baseline, an approximate percentile interval includes zero. The bias may reflect attenuation, or imperfect anchoring
   of labels in the replications, which the data cannot separate."
6. **§7.2.** "Against the full baseline, the block … is significant at 5 % in seven of the eight variations, and against the
   core baseline in five of eight"
   → "… in six of the seven variations (full) and four of seven (core); all with conventional standard errors."
7. **§7.3.** "The membership changes are therefore not proxies for goals and assists."
   → "They are therefore not proxies for goals and assists. They are, however, partly proxies for changes in the FBref
   position labels (Table X): with those changes controlled, the bootstrap p-values are 0.35 (core) and 0.12 (full)."
8. **§6.4.2.** "it is the direction of the movement, and not its size or the starting point, that is associated with the
   change in value."
   → "In this run, the direction of the movement is associated with the change in value, while its size and the starting
   memberships are not."
9. **§5.1.4 vs §6.1.** "The Xie–Beni index alone is not decisive, because it increases almost mechanically with K" vs.
   "the Xie–Beni index, which is lowest at K = 4 …". The two sentences contradict each other in spirit; the data are
   non-monotone (shrunk 0.82, 0.72, 1.35, 1.24).
   → "The index is not monotone in K here and is used together with the other diagnostics."
10. **§5.4.3.** "Player-specific unobserved characteristics such as talent, reputation or injury history may be correlated with
    both memberships and values. The model is therefore also estimated with player fixed effects"
    → "Because the outcome is already a change, time-invariant player characteristics are differenced out. Player fixed
    effects in this model absorb player-specific *trends* in value, for example those of young players on a steep path."
    (C5)
11. **§6.1.** "It reflects that player profiles form a continuum with no sharp natural boundaries"
    → "It shows that the objective has several local optima with quite different partitions. This is consistent with a
    continuum of profiles, but it also means that the best of ten starts is itself unstable (Section 7.7)."
12. **§7.6.** "This is a correction of the method made because of the label check and not because of any outcome."
    → See §3.2 above.
13. **§8.2.** "… supports the view that what the memberships capture is not a linear change in the underlying statistics, but
    the relative position of a player with respect to the archetypes."
    → After C2: "A linear summary of the statistics carries no association; the clustering adds the position labels and the
    league-relative position of a player. Controlling for the change in position labels removes most of the association."
14. **§8.5.** "… with 96 % of the player-seasons linked, a few wrong links removed by hand, and two players of the sample with
    the same name merged by FBref."
    → "… 95 % of the player-seasons of the sample linked; three wrong links removed by hand; eleven Transfermarkt profiles
    shared by two FBref names split; one merged player-season (two different players named Vitinha) and 22 rows of
    same-name team-mates removed."
15. **§4.4.** "Of the 1,507 outfield players, 1,446 (96.0 %) could be linked, which corresponds to 96.2 % of the
    player-seasons"
    → "At the collection step, 1,446 of 1,507 FBref outfield names (96.0 %) were linked. In the final sample, after the
    checks below, 95.4 % of the 3,192 player-seasons have a Transfermarkt identifier and 94.5 % a value."

Also fix, briefly:
- Appendix C text vs tables (m = 1.5);
- §7.7 "this is consistent with, but does not show, that they act partly as a regulariser". Drop it: it is speculation.

---

## 4. Number and claim audit (details: `review/number_audit.csv`, 98 rows)

- **Verified OK: 73 rows** (several rows cover whole tables: Tables 6.1, 6.2, 6.3, 6.4, 6.5, 7.1, 7.2, 7.6 and B.1 match
  their source files cell by cell).
  - All sample counts of Table 4.1: 4,463 → 4,441 → 4,364 → 4,363 → 4,009 → 3,201 → 3,192.
  - The 22,152-minute same-name case (João Mendes, b. 2000, Vitória SC 2024/25).
  - 18 clubs per season.
  - Linking thresholds 70/85/92; 32 weak links; 15/12/11/1 shared Transfermarkt ids.
  - Outcome moments; transition shares; medoid position claims; player-trajectory descriptions.
  - PCA share of variance (70.6 %, "about 71 %").
  - Holm thresholds.
  - Seed statistics: the main run ranks 8th (core) and 6th (full) of 30 draws at m = 1.3, so "favourable draw" is fair.
- **Wrong: 3 rows** (age interpretation; bootstrap bias "up to 0.17"; "twelve statistics" in §3.5). **Minor or partly
  wrong: 7 rows** (96.2 %, 91 %, 94 %, 7-of-8, Table 4.2 and 4.4 notes, unclear §8.5 sentence). See C4.
- **OK against the file but the file is stale (C1):** every number for m ≠ 1.3 or ρ ≠ 1.0 in Ch. 7, Ch. 8 and App. C, and
  the XB medians quoted in the Ch. 5 intro.
- **Unverifiable: 13 rows.**
  - Every statement about other papers (docs/ absent): Franceschi et al. (18,080; USD 7.35 bn; 29 studies / 111
    specifications; 32/45 and 41/45), Müller et al. (4,217 players; 6–12-month updates), Poli et al. (8,389; 84.8 %),
    D'Urso et al. (397/544; 49 noise; m = 1.3; 12 %), Akhanli & Hennig (3,003 / 1,501; 13 experts), Pacifico (27 players;
    35 variables), Bezdek (10–25 iterations), Behravan (93,000; 4,900).
  - Please re-check the 2019 transfer figure in particular. The text says "18,080 players moved", but such reports count
    *transfers*, not players. I could not check the number itself.
  - Results of earlier pipeline versions are not stored anywhere: the medoid alignment consistent in 36 of 120 runs; the
    one-, two- and three-pair inconsistencies at m = 1.5, 2.0, 1.2; "99 % noise" with the paper's noise rule; the earlier
    run with p = 0.70 / 0.36. Keep the output of those runs (or the commit) so that the claims are documented.

---

## 5. Code audit findings (with re-run results)

Severity: **C** critical, **M** major, **m** minor.

**`fcmd_mdnc.py`** (the model; matches Ch. 5 equations; verified)
- Membership update (l. 138–145): stable softmax on −log(d²)/(m−1), noise column −log δ²/(m−1). Equivalent to the
  equation in §5.1.3. OK.
- Medoid update (l. 183–186): argmin_h Σᵢ uᵢcᵐ d²(h,i), distinct medoids enforced. OK.
- Fixed weights √nₛ / Σ√nᵣ (l. 119–122) = (0.501, 0.224, 0.275). OK.
- Dave noise distance δ² = ρ·mean(d²) over the n×K unit–medoid pairs (l. 180–181). OK, matches §5.1.3.
  - (m) δ² is refreshed from the medoids *before* their update, so in the final E-step it lags by one iteration if
    `max_iter` is hit.
  - (m) Convergence is tested on medoids only (l. 187), not on the objective or the weights. Harmless with fixed weights.
- XB (l. 200–202): Σ u^m d² / (n · min inter-medoid d²), K substantive clusters, squared distances. OK, matches §5.1.4.
  Returns `inf` when two medoids coincide (duplicated rows in the bootstrap). OK.
- k-medoids++ (l. 147–156): probability ∝ d² to the nearest chosen medoid. OK. (m) It can loop forever if all remaining
  probability mass is on copies of chosen medoids. Practically impossible.
- `fit_best` (l. 207–219): lowest objective of `n_starts` (seeds seed … seed+9). The "stability" is the mean ARI between the
  best and the *other local optima*, not resampling stability. The text should say "agreement between random starts"; §6.1
  does. OK.
- (m) Module docstring says "rho in [0.05, 0.5]" and l. 17 shows the paper's u^m-weighted δ², while the default rule is Dave.
  The docstring is stale.

**`align_and_select.py`** (verified correct)
- Profile alignment (l. 90–93): u-weighted means of pooled z-scores of the 12 scaled statistics + 3 positions, L1 cost,
  Hungarian. OK.
- Propagation (l. 97–101): `pb[ci] = perm[a][ri]` correctly gives season-b cluster ci the reference label of the matched
  season-a cluster.
- `Ua[:, perm[s]] = U[:, :K]` (l. 115) moves raw column c to reference column perm[s][c]. Correct.
- Ambiguity ratio (l. 102–103) matches §5.2. Persistence (l. 150–160) uses argmax including noise and drops pairs with
  noise in either season; §6.3 says so, §5.2 should too.
- Transitions merge on (uid, season_t1), inner, `validate="1:1"` (l. 133–137). Correct; consecutive seasons only.
- (m) Docstring l. 30 still says `align_d` is a medoid distance.

**`pairs_lib.py`**
- (**C**, = C2) Position changes are missing from both baselines (l. 31, 66–68). The docstring (l. 15–17) claims the full
  baseline "really contains everything the memberships are built from".
- Pairs merge memberships by `pid` at t and `pid_1` at t+1 (l. 37–40). This correctly handles the one player with two
  spellings. Season-pair dummies are for the start season. Reference = largest mean membership at t. OK.
- `oos_gain` (l. 85–106): folds by player, OLS refit in each training fold, SST around the training mean. **Leak-free with
  respect to the outcome.** The memberships are estimated on all players, but unsupervised (no y), so this is not leakage.
  Base and extended models use the same folds (same rng seed). OK.
- (m) `wald_p` uses `use_f=True`, i.e. an F version of the cluster-robust Wald test. Fine; say "F-form" once in §5.4.2.

**`bootstrap.py`** (mechanics verified; validity discussed in §6)
- Player resampling with copy ids `uid#c` (l. 124–132) and `pid = uid` for copies: correct. All seasons travel together.
- Re-clustering with the original scaling constants and weights; a new seed per replication (l. 136); per-season Hungarian
  anchoring to the *original* profiles (l. 137–152). Correct.
- Wald with the bootstrap covariance θ̂′V⁻¹θ̂ ~ χ²(4) (l. 230–235). Individual p from θ̂ / SE_boot (l. 236). Normal
  intervals (l. 238).
- (**C**, = C1) For m ≠ 1.3 or ρ ≠ 1.0 the "original" memberships and anchor profiles come from the stale folders (l. 99–100,
  172), while the replications use the current panel.
- **Re-run with regenerated folders (500 replications, `review/scratch/analysis_copy/bootstrap_fix.py`):**
  - m = 1.2: core **p = 0.050**, full **p = 0.013** (thesis 0.445 / 0.277);
  - m = 2.0: core **p = 0.318**, full **p = 0.126** (thesis 0.088 / 0.019). The reference archetype is no. 4 in the
    reproduced run.
  - m = 1.5: core p = 0.008, full p = 0.004 (thesis 0.029 / 0.008). The wide-attacker coefficient is −0.285 / −0.371
    (bootstrap p = 0.006 / 0.002).
  - Even with consistent folders, bootstrap bias at m = 1.5 reaches 0.13–0.15 (≈1.2 SE), so the large bias is a property of
    the bootstrap, not only of the stale anchor.
- **Main configuration with position-change controls (C2; `analysis_copy3`):** bootstrap Wald p = **0.352 (core)** and
  **0.120 (full)**; SE ratios 1.07–1.18.
- (m) Docstring l. 13 ("medoid distances") and l. 24 ("percentile intervals") are stale: the code uses profiles and normal
  intervals.

**`build_panel.py` / `make_analysis_panel.py` / `collect_tm_v2.py`**
- **Re-run: both panel scripts reproduce `panel_player_season.csv`, `analysis_panel.csv` and `scale_table.csv` exactly**
  (3,192 × 63 and × 75, max diff 0). The logs are identical except for UTF-8 mojibake in the stored logs (Windows
  console).
- Keys are correct:
  - same-name exclusion on (season, team, player);
  - multi-club merge on (player, born, season) with counts summed and rates recomputed;
  - per-90 from exact minutes;
  - shrinkage κ = 10 towards the pooled rate;
  - AAD scaling, pooled;
  - crosswalk keyed on (player, born), id by majority across seasons;
  - value nearest 1 June ±120 days (windows do not overlap);
  - `has_next` = consecutive season index;
  - club change based on the club with the most minutes.
- (m) The goalkeeper filter differs: `collect_tm_v2.py` l. 310 drops any row containing "GK"; `build_panel.py` l. 121 drops
  only pure "GK". This has no effect here.
- (m) The 22.1 % club-change share in the log is on 1,433 pairs; on the 1,361 estimation pairs it is 22.3 %.
- (m) The duplicate `(tm_id, season)` valuation rows (115) are exact duplicates, from 15 shared ids. Harmless.

**`regression.py`** — re-run reproduces `regression_summary.csv` to 1.5e-12. (m) The docstring l. 26–27 ("NOT YET DONE …
bootstrap") is stale.

**`robustness.py`** — (M, = C5) non-robust Hausman (l. 111–123); FE interpretation. The variations (l. 60–69) are implemented
as described (winsorising at the 1st/99th percentiles of the full sample; COVID = pairs starting 2019/20 and 2020/21).

**`spec_grid.py`**
- (**C**, = C1) `ensure_clustering` caches by file existence (l. 61).
- (m) The docstring l. 6–7 states the *earlier* main result ("no incremental explanatory power at m = 1.3"). Update it; an
  examiner reading the code will ask.
- (m) The heatmap plots only ρ ∈ {1.0, 1.5} (l. 133).
- (m) Outputs go to `analysis/thesis_outputs/`, while the thesis reads `thesis/thesis_outputs/`. The copy step is
  undocumented in the README.

**`seed_sensitivity.py`**
- Correct; always re-clusters; the seed-0 self-check at m = 1.3 passes.
- (m) Column `persist` (l. 91) is actually the share of non-noise rows: `persist + noise_share = 1` in every row. Rename it
  or compute persistence. It is not used in the thesis.
- (m) The self-check only covers m = 1.3. Extending it to every m would have caught C1.

**`alignment_check.py`**
- With profile alignment, "aligned_ok" is true by construction (the check uses the same criterion). The only independent part
  is `medoid_pos_agree`. The thesis says this (§7.6). OK.
- (m) The docstring still describes medoid alignment.
- Re-run on regenerated folders: 120/120 consistent; medoid agreement as in C1.

**`make_tables_figures.py`**
- (M) l. 154: `robustness_configurations` merges `bootstrap_summary` on (rates, K, baseline) only, ignoring ρ and m. Each
  shrunk-K4 row is duplicated 6× with the bootstrap p of *other* m/ρ settings attached (see
  `thesis_outputs/tables/robustness_configurations.csv`). The thesis Table 7.1 is typed by hand and is correct, but the
  README maps Table 7.1 to this file. Fix: filter `bs` to ρ = 1.0, m = 1.3 before merging.
- (m) `sample_by_season` counts 1,364 pairs (pre-`ppm` drop).
- (m) Player selection for Fig. 6.4 matches names by substring ("Paulinho", "Otávio" are common names). The chosen ones
  (Braga/Sporting Paulinho, Porto Otávio) are right, but this is fragile; select by uid.

**`extra_results.py`** — stale folders (C1) for m = 1.4/1.5 coefficient tables and Table 7.3B. (m) The `label()` map lacks
the full-baseline variables, giving the raw names in Table C.2.

**`estimated_weights_check.py`**
- (M, methodological) It tests weight estimation only with max/mean scaling and ρ = 0.5, never with the SD scaling and
  ρ = 1.0 of the final model.
- Re-run with `norm="sd"` (`review/scratch/weights_sd_check.py`; seasons 2023/24 and 2019/20; raw/shrunk; ρ ∈ {0.5, 1.0};
  K = 3–5; 24 fits): positions take **69–100 % of the weight in 23 of 24 fits**, with ~0 % noise; the other fit puts 88 % on
  the rates. This *strengthens* deviation 1. Add the table to Appendix B (10 min).

**Reproducibility summary.**
- Reproduced exactly: `build_panel.py`, `make_analysis_panel.py`, `regression.py`, the main clustering (seed 0) and the
  m = 1.3 cells.
- Not reproduced: 88/120 grid cells, 5/10 bootstrap configurations, Tables 7.3B / 7.4 / 7.5 / C.3 (C1).
- Not run: `bootstrap.py` for all 10 configurations (only the 3 affected cells plus the C2 variant were re-run),
  `collect_tm_v2.py` and the FBref collection (network; not needed).

---

## 6. Methodology and econometrics audit

**Fixed √nₛ weights (deviation 1).**
- Well motivated, and now better documented: the SD-scaled re-run above shows the collapse onto positions also under the
  thesis's own scaling.
- Two points for the text:
  1. Akhanli & Hennig aggregate dissimilarities *linearly* with weights ∝ nₛ (I believe; paper not available). The thesis
     squares them, so √nₛ makes each group's share of d² ∝ nₛ. That is a reasonable translation, but say it is an
     adaptation.
  2. Fixing the weights fixes what an "archetype" is. Positions take 3/15 of d² despite having only five distinct
     combinations, so they partition the space strongly, and C2 shows position labels carry the valuation association.
     One sensitivity run with the position weight halved would show whether the result is a position-label artefact.

**Dave noise distance (deviation 2).** Standard (δ² = ρ × mean squared distance) and correctly implemented. The calibration
ρ = 1.0 → 5 % noise is a choice, not an estimate. Fine as long as it is called that. The "99 % noise" justification is
undocumented (no stored run); keep it in an appendix footnote with the setting.

**Alignment (deviation 6).**
- Profile-based Hungarian matching is the right choice: it uses the whole archetype and is invariant to medoid noise.
- After the switch, the "label check" is the same criterion, so it is no longer an independent check. The medoid
  position-label agreement is independent but coarse (3 labels).
- A stronger independent check: for players present in both seasons, the share keeping their argmax under the chosen
  permutation versus the best alternative permutation (a margin), or the ARI of hard labels for these players.
- The proposal promised sensitivity to alternative assignments for ambiguous matches. This is not delivered; with 2
  ambiguous matches at K = 4 it is cheap.

**K, m and XB.**
- The K choice is defensible but partly mechanical: persistence and the *count* of ambiguous matches favour small K by
  construction (21 vs 28 vs 35 matches). Raw rates with K = 3 dominate shrunk K = 4 on XB, persistence and ambiguity;
  shrunk K = 4 is preferred on a-priori grounds, which should be said explicitly.
- Not choosing m by XB is correct: XB with uᵐ in the numerator falls mechanically with m. The text should not then lean on
  "XB lowest at m = 1.4" as a quasi-endorsement.
- With reproducible folders, the main-configuration XB values are 0.72 / 0.72 / 0.66 / 0.79 / 0.66 (m = 1.2 … 2.0).

**Reference archetype.** Defenders (largest mean membership): fine. Coefficients are contrasts against defenders, so
"wide attackers" means "wide attackers relative to defenders". Report the joint test (done) and avoid reading single
coefficients causally (done).

**"Incremental explanatory power" logic.**
- Memberships are deterministic functions of (x_t, x_{t+1}, positions, and the other players of the season). The full
  baseline must contain everything observable that enters the memberships (C2).
- The PCA benchmark is linear and is tested against *core*, so it cannot separate "nonlinear" from "linear but omitted".
  My check with squared terms shows nonlinearity in the statistics is not the channel; positions are.
- The genuinely new information in Δu is the league-relative position of a player (distance to this season's medoids).
  That is a nice theoretical point and could be tested: e.g. Δ of the distance to the nearest medoid, or a hard-clustering
  (k-medoids) variant.

**Cluster-robust Wald tests and grouped CV.** Correctly implemented (697 clusters; F-form). The CV is leak-free. The OOS gains
are tiny (+0.08 pp against core) and negative in the typical draw. The thesis says so. With position controls the core OOS
gain is −0.12 pp.

**FE/RE and Hausman.** See C5. Also, FE estimates come from 346 players / 1,010 pairs. With T ≤ 7 per player, FE in a
differenced model is a demanding specification, and its significance (p = 0.018 / 0.001, conventional) deserves a bootstrap
too, or at least a caveat.

**Two-stage bootstrap.**
- Design: resample players, re-cluster, anchor to the original, re-estimate. This is the right idea for Pagan's problem,
  and the implementation is correct.
- Validity concerns:
  1. The estimator is non-smooth (argmin over medoids, assignment), so bootstrap consistency is not guaranteed.
  2. Duplicated players create zero distances: copies can become co-medoids, and the medoid search is biased towards
     duplicated points.
  3. The bootstrap distribution is shifted by up to 1.5 SE from θ̂ (main configuration: wide-attacker core +0.066 = 0.75 SE).
     The Wald test centred at θ̂ with V_boot is then only an approximation.
- Under normality of the draws (draws not in the repo), an approximate percentile 95 % interval for the core wide-attacker
  coefficient is [−0.32, +0.02], i.e. **not significant**; for the full baseline [−0.42, −0.02].
- Report percentile and bias-corrected intervals next to the normal ones. Report the share of replications with an
  ambiguous anchoring (cost ratio < 1.1), which would show whether the "bias" is label mixing rather than attenuation.
- The bias-towards-zero → "conservative" reading is consistent with the bootstrap bias logic, but it is only one of two
  explanations; say so.

**Seed analysis.**
- The single best methodological decision in the thesis. Given ARI ≈ 0.5 between starts and p-values spanning three orders
  of magnitude, the seed distribution should be the *primary* evidence, not a robustness check.
- Two cheap improvements:
  1. Report the seed distribution of the *coefficients*: does the wide-attacker sign hold in all 30 draws?
  2. A consensus estimate: align all 30 draws to seed 0 by profiles and average the memberships. It is less noisy and
     removes the "one favourable draw" problem.

**Multiple comparisons.** Holm over 20 bootstrap comparisons is honest. The family is arbitrary, but nothing survives
either way.

**Selection.**
- Only players with ≥ 200 minutes in two consecutive seasons who stay in the league enter.
- Sellers to bigger leagues (the high-value-growth players the RQ is about) and players who lose their place
  (value-decline players) are both excluded. This truncates the outcome at both ends and probably attenuates any
  association.
- Show a comparison of stayers vs leavers at t (age, minutes, value, archetype). That would take 30 min.

**What I would conclude.**
- The clustering stage delivers a credible, stable, interpretable description: four archetypes plus noise; strong
  persistence of defenders; mobility among attacking roles. That is a real contribution.
- The valuation stage finds no robust incremental explanatory power. In one favourable draw there is a small conditional
  association, concentrated in full-backs drifting into wide/midfield profiles. Once changes in FBref position labels
  (observable without any clustering) are controlled, the association is not significant: bootstrap p = 0.35 (core) and
  0.12 (full).
- "Weak, specification-dependent evidence" is the right genre of conclusion. After C1 and C2 it should be stated more
  firmly as "no robust evidence; the descriptive archetypes are the main finding".

---

## 7. Supervisor's comments (`docs/proposal_with_carlo_comments.pdf` was not available)

The assessment below is against the topic list in `REVIEW_TASK.md` §1.4, not against the actual annotations.

| Topic | Status | Where / what is missing |
|---|---|---|
| Objective: prediction vs interpretation | **Addressed** | §1.1, §2.5: explanatory/associational; OOS R² only as a diagnostic (§5.4.2) |
| Causal wording | **Mostly** | §1.1, §2.5, §3.4 are explicit; remove "effects" (§6.4.1, §8.5) |
| Alignment: distance, algorithm, ties | **Partly** | §5.2 specifies profile L1 + Hungarian + 10 % ambiguity rule; ties and ambiguous matches are counted but no alternative-assignment sensitivity (promised in the proposal) |
| Generated regressors | **Partly** | §5.5, §7.1: two-stage bootstrap done well; bias, interval type and seed variability of the original estimate not handled (§6 above) |
| Overlap with performance controls | **Partly** | core/full/minimal baselines (§3.5, §7.3) are good; position labels missing (C2) |
| Why transitions carry information beyond raw statistics | **Partly** | theory in §3.2; empirically the PCA benchmark cannot test nonlinearity; the evidence points to positions (C2) |
| Economic meaning of coefficients and memberships | **Addressed / partly** | §3.1, §3.4 (0.10 shift, % change); the DEF → wide result has no tested interpretation (§8.2 conjectures) |
| Hausman and unobserved heterogeneity | **Partly** | done, but misinterpreted for a differenced outcome and non-robust (C5) |
| Match rates | **Addressed** | §4.4 (denominator issue C4) |
| Transfermarkt measurement error | **Addressed** | §3.3, §4.6, §8.5; correctly notes noise in y does not bias β (the proposal had said it attenuates; fixed) |
| Sample size N, T | **Partly** | N and T reported; the proposal promised "a formal power analysis", which is not delivered. A minimum-detectable-effect calculation for the 4-df block would take 30 min |
| PCA / dynamic-clustering positioning | **Addressed** | §2.4 and §7.3 |
| Transition definitions | **Addressed** | §5.3 (vector, norm, entropy, levels) |

---

## 8. Defence questions (the 15 hardest), with answer outlines

1. **"Your position labels enter the clustering. Why are their changes not in the full baseline, and what happens if you add
   them?"** (C2)
   *Answer:* It was an oversight. With position changes controlled, the bootstrap p-values are 0.35 (core) and 0.12 (full),
   so the association largely runs through observable label changes, and the conclusion is "no robust incremental
   explanatory power".
2. **"Re-running your code gives different grid results from your tables. Which are right?"** (C1)
   *Answer:* The grid cells came from cached folders built on an earlier panel. The corrected runs are in the final version,
   and the conclusions rest on the 30-draw distribution, which always re-clusters and was unaffected.
3. **"Your main result is one draw that ranks 6th–8th of 30. Why should we believe any single-run number?"**
   *Answer:* We shouldn't. The seed distribution is the evidence: full baseline significant in 60–73 % of draws, core
   27–37 %, and a negative median OOS gain against core.
4. **"The proposal said m would be chosen by Xie–Beni; XB picks 1.4, where your results are stronger. Isn't m = 1.3 a
   convenient choice — or an inconvenient one you kept to look honest?"**
   *Answer:* m = 1.3 was fixed a priori from the literature, because XB falls mechanically in m. Both settings are reported,
   and the seed distributions at 1.3 and 1.4 overlap heavily.
5. **"The main result changed from p = 0.70 to p = 0.03 after you fixed the alignment and the data. How do we know the
   fixes were not outcome-driven?"**
   *Answer:* Each fix is justified independently: labels inconsistent in 70 % of medoid-aligned runs; a 22,152-minute
   artefact. The earlier result is reported, and the seed analysis shows such swings arise from the random draw alone.
6. **"Your bootstrap means are up to 1.5 SEs away from the estimates. Is the bootstrap valid for a medoid estimator with
   duplicated observations?"**
   *Answer:* Consistency is not guaranteed for non-smooth estimators, and the shift is either attenuation or label mixing.
   I therefore report percentile intervals as well, and they are less favourable.
7. **"Why fix the attribute weights when estimating them is the main feature of D'Urso et al.?"**
   *Answer:* Estimated weights collapse onto the lowest-dimensional, most compact group in every scaling I tried (max, mean,
   and the SD scaling used in the thesis), with ~0 noise and XB ≈ 0. Fixed weights ∝ nₛ follow Akhanli & Hennig, adapted
   to the squared aggregation.
8. **"Why the Davé noise distance rather than the paper's formula? Isn't ρ just tuned to get 5 %?"**
   *Answer:* The paper's u^m-weighted version produced degenerate solutions (up to 99 % noise). ρ is a calibration
   constant, varied over 0.75–1.5 in the grid, with weaker results when less noise is assigned.
9. **"Your outcome is already a difference. What do player fixed effects do here, and what does the Hausman test tell
   us?"** (C5)
   *Answer:* They absorb player-specific value trends, not talent levels. The non-robust Hausman test is not informative,
   so I report a cluster-robust Mundlak test instead.
10. **"What does a −0.22 coefficient on 'defender → wide attacker' mean economically, given that only 7 players make a crisp
    move?"**
    *Answer:* It is a conditional contrast driven by about 40 graded shifts, mostly full-backs gaining a midfield label. Their
    raw value growth is above average, so the negative sign is conditional on minutes and output and is not a robust
    economic effect.
11. **"Memberships are deterministic functions of the same statistics. Where could incremental information come from at
    all?"**
    *Answer:* From the position labels (now controlled), from nonlinearity (squared terms do not absorb it), and from the
    *league-relative* position of a player via season-specific medoids. Only the last is genuinely new, and it was not
    isolated.
12. **"Your sample excludes players who leave the league — exactly the ones whose value moves most. How does that affect
    the RQ?"**
    *Answer:* The estimates are conditional on staying, with the outcome truncated at both ends, which likely attenuates
    associations. A stayer/leaver comparison at t shows how different the leavers are.
13. **"Start stability ARI ≈ 0.5 — doesn't that mean the clustering is not identified, so the archetypes are not
    'found' but chosen?"**
    *Answer:* The archetype *types* are stable (medoid positions, profiles, 30 draws), but individual memberships near
    boundaries are not. That is why transitions are noisy and why I treat the seed distribution as primary.
14. **"Why a profile-based alignment, and what independent evidence do you have that labels are right?"**
    *Answer:* Profiles average the whole archetype and are invariant to medoid noise. Independent evidence is the medoid
    position labels (0.88 agreement at m = 1.3) and the persistence matrix (no DEF ↔ striker flows). A margin to the
    second-best permutation is reported.
15. **"Is 0.3 pp of adjusted R² (and negative OOS) of any practical value for a club?"**
    *Answer:* No. The practical value is descriptive (profiles, trajectories, medoids), and the valuation result is a
    well-documented null with a clear explanation of why.

---

## 9. Prioritised to-do list (next 6 hours)

**Must do (≈4.5 h)**
1. (20 min) Add an abstract. Fix Table 4.1 (`p{11.5cm}r`). Fix the C4 numbers (age slope at 25; bias "up to 0.25"; 6 of 7 /
   4 of 7; 95.4 %; 90 %; 94.5 %; Table 4.2 note).
2. (≈1.5 h: 15 min compute + text) **C2: this changes the answer to the RQ, so do it first.**
   - Apply the `pairs_lib.py` patch (reproduced under "Commands run").
   - Re-run `regression.py`, `robustness.py` and `bootstrap.py` (main configuration). Expected: bootstrap p ≈ 0.35 / 0.12.
   - Do not silently swap the pre-specified baseline. Report the position-controlled baselines as an explicit, motivated
     check (a new row in Tables 6.5 and 7.2 plus one paragraph in §6.4), and say why it was added.
   - Then rewrite §3.5, §6.4.2, §7.3, §8.2, the summaries (§6.5, §7.9, §8.1) and Ch. 1 / Ch. 9 to: "no robust incremental
     explanatory power; the small association in the main run largely reflects changes in position labels".
3. (≈1 h compute, mostly unattended, + 45 min text) **C1.**
   - Delete `clustering_sens_*`. Re-run `spec_grid.py`, `sensitivity_and_benchmark.py`, `alignment_check.py`,
     `extra_results.py`, then `bootstrap.py` for the 5 non-main configurations, then `make_tables_figures.py`.
   - Update Tables 7.3B, 7.4, 7.5, C.3, Fig. 7.1 and §7.5–7.6.
   - Replace every "absent at m = 1.2" sentence (§1.2, §7.9, §8.1, §8.2, Ch. 9) with the seed-based statement.
   - If time is short, at least add the footnote described under C1.
4. (20 min) **C5.** Rewrite §5.4.3 and §6.4.3 (FE = player trends). Drop or qualify the Hausman claim.
5. (15 min) Code hygiene, because examiners read the code:
   - fix `make_tables_figures.py` l. 154 (merge on ρ and m);
   - fix the stale docstrings: `spec_grid.py` l. 6–7, `bootstrap.py` l. 13 and 24, `regression.py` l. 26,
     `fcmd_mdnc.py` l. 16–17, `align_and_select.py` l. 30, `pairs_lib.py` l. 15–17;
   - fix the `persist` column in `seed_sensitivity.py`;
   - add the folder guard in `ensure_clustering`.

**Nice to have (≈1.5 h)**
6. (10 min) Add the SD-scaled estimated-weights table to Appendix B (`review/scratch/weights_sd_check.csv`).
7. (20 min) Report percentile / bias-corrected bootstrap intervals for Table 6.4 from `bootstrap_draws_*.csv` (already saved
   locally).
8. (20 min) Clean up the appendix: Table C.2 labels, m = 1.5 tables or remove the sentence, full-baseline m = 1.4. Plot all
   three ρ in Fig. 7.1 or fix the caption. De-duplicate §2.5 and shorten the repeated headline numbers.
9. (30 min) Stayer/leaver comparison table; a minimum-detectable-effect paragraph (promised power analysis).
10. (15 min) Seed distribution of the wide-attacker coefficient (sign stability over 30 draws).

---

## Commands run

All re-runs were made in copies under `review/scratch/` (git-ignored); nothing in `thesis/` or `analysis/` was modified.

- Reading:
  - `cat`/`sed` of README.md, REVIEW_TASK.md, CLAUDE.md, all `thesis/chapters/*.tex`, `main.tex`, `main_proposal.tex`,
    `MyReferencesFile.bib`, all `analysis/*.py`, all CSVs in `analysis/{logs,regression,clustering,tm_out}` and
    `thesis/thesis_outputs/tables`.
  - `pdfinfo`/`pdftotext -layout thesis/main.pdf`; `pdftoppm` on pp. 16–18, 26–27, 29, 31, 35, 37, 39–41 (layout check).
- Environment: `pip install numpy "pandas<3" scipy scikit-learn statsmodels linearmodels joblib matplotlib rapidfuzz
  unidecode` (Python 3.11, pandas 2.3.3, numpy 2.4).
- Re-runs:
  - `cp -r analysis review/scratch/analysis_copy2`; `python3 build_panel.py`; `python3 make_analysis_panel.py`; diff of
    logs and panels (identical); `python3 regression.py` (identical to 1.5e-12).
  - `cp -r analysis review/scratch/analysis_copy`; `rerun_cells.py` (stage 1 for shrunk K = 4 ρ = 1.0, m ∈ {1.2, 1.3, 1.4,
    1.5, 2.0}); `python3 spec_grid.py` (full 120-cell re-run, fresh folders); `python3 alignment_check.py`;
    `bootstrap_fix.py` (= `bootstrap.py` with CONFIGS = m 1.2, 2.0, 1.5; B = 500).
  - `review/scratch/position_check.py`, `nonlinear_check.py` (stored memberships; position-change and squared-term
    baselines); `weights_sd_check.py` (estimated weights with SD scaling).
  - `cp -r analysis review/scratch/analysis_copy3` with `pairs_lib.py` patched (position controls); `python3 regression.py`;
    `bootstrap_pos.py` (main configuration, B = 500).
- Ad-hoc pandas checks of transitions, medoids, trajectories, PCA shares, age slope, FE subsample, bootstrap bias, and the
  seed rank of the main run.

### Patch used for the C2 check (`analysis/pairs_lib.py`)

```diff
--- analysis/pairs_lib.py	2026-10-01 18:57:51.959139718 +0000
+++ analysis/pairs_lib.py	2026-10-01 19:17:58.947075176 +0000
@@ -28,10 +28,10 @@
     uc = [f"u_{j + 1}" for j in range(K)] + ["u_noise"]
     mem = mem.copy()
     mem["season"] = mem["season"].astype(str).str.zfill(4)
-    keep = ["uid", "pid", "season", "age", "minutes", "team_ppm", "team_main", "pos_DF", "pos_FW"] + [f"s_{v}" for v in PERF]
+    keep = ["uid", "pid", "season", "age", "minutes", "team_ppm", "team_main", "pos_DF", "pos_FW", "pos_MF"] + [f"s_{v}" for v in PERF]
     t = ap[ap["has_next"] & ap["delta_log_mv"].notna()][keep + ["season_next", "delta_log_mv", "club_change_next"]].copy()
     t["season_next"] = t["season_next"].astype(float).astype(int).astype(str).str.zfill(4)   # CSV turned it into a float
-    n1 = ap[["uid", "pid", "season", "minutes", "team_ppm"] + [f"s_{v}" for v in PERF]]
+    n1 = ap[["uid", "pid", "season", "minutes", "team_ppm", "pos_DF", "pos_MF", "pos_FW"] + [f"s_{v}" for v in PERF]]
     n1 = n1.rename(columns={c: c + "_1" for c in n1.columns if c != "uid"}).rename(columns={"season_1": "season_next"})
     p = t.merge(n1, on=["uid", "season_next"], validate="1:1")
     U0 = mem[["pid", "season"] + uc]
@@ -44,6 +44,8 @@
     p["dlog_min"] = np.log(p["minutes_1"]) - p["log_min"]
     p["ppm"], p["dppm"] = p["team_ppm"], p["team_ppm_1"] - p["team_ppm"]
     p["club_change"] = p["club_change_next"]
+    for _q in ("DF", "MF", "FW"):
+        p[f"D_pos_{_q}"] = p[f"pos_{_q}_1"] - p[f"pos_{_q}"]
     for v in PERF:
         p[f"L_{v}"], p[f"D_{v}"] = p[f"s_{v}"], p[f"s_{v}_1"] - p[f"s_{v}"]
     for c in uc:
@@ -63,7 +65,7 @@
     p = pd.concat([p, season_d], axis=1)
     core_perf = [f"{a}_{v}" for v in CORE_PERF for a in ("L", "D")]
     blocks = {
-        "core": ["age", "age_sq", "log_min", "dlog_min", "pos_DF", "pos_FW", "ppm", "dppm", "club_change"]
+        "core": ["age", "age_sq", "log_min", "dlog_min", "pos_DF", "pos_FW", "pos_MF", "D_pos_DF", "D_pos_MF", "D_pos_FW", "ppm", "dppm", "club_change"]
                 + core_perf + list(season_d.columns),
         "full": [c for c in (f"{a}_{v}" for v in PERF for a in ("L", "D")) if c not in core_perf],
         "du": dcols, "norm": ["norm"], "dH": ["dH"], "levels": lcols}
```

The check scripts (`position_check.py`, `nonlinear_check.py`, `weights_sd_check.py`, `rerun_cells.py`) are in
`review/scratch/`, which is git-ignored: they exist only in this session's container. Each is under 40 lines and is
described above, so it can be recreated if needed.

## Could not verify

- `docs/` is absent: every statement about other papers (Ch. 1–2 numbers; D'Urso et al.'s printed noise formula and
  m-range; Akhanli & Hennig's aggregation), the thesis manual (abstract requirement, page limits) and the supervisor's
  annotated proposal (Section 7 is assessed against the topic list only).
- Results of earlier pipeline versions are not stored: medoid-aligned label check (36/120, by K, by m), "99 % noise" with
  the paper's rule, the earlier main run (p = 0.70 / 0.36).
- Bootstrap draws (`bootstrap_draws_*.csv`, git-ignored): percentile intervals are approximated under normality.
- I could not compile LaTeX (no TeX installation), so overfull-box warnings were checked only visually in `main.pdf`.
- `bootstrap.py` was re-run only for m = 1.2, 1.5 and 2.0 (corrected folders) and for the main configuration with position
  controls. Two other configurations also rest on stale folders: ρ = 1.0 with m = 1.4 (nearly identical conventional
  results) and ρ = 1.5 with m = 1.3. Their bootstrap p-values were not re-checked. The main configuration and the K = 3/5
  and raw-rate rows at m = 1.3 use `clustering/`, which is current, and were not re-run.
