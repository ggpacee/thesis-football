# Review task: the thesis (LaTeX) AND its code

There are TWO equally important review targets: **(1) the thesis text** in `thesis/` (`main.tex` + `chapters/*.tex`, and the compiled `thesis/main.pdf`
if present) and **(2) the code** in `analysis/`. Review both, and check that they agree with each other.

You have two hats. (1) **Expert in cluster analysis**: fuzzy and medoid-based clustering, mixed-type dissimilarities, noise clustering, validity
indices, label alignment across time, and inference with estimated (generated) regressors. (2) **Examiner** of a master's thesis in Data Science &
Marketing Analytics (Erasmus School of Economics) who understands panel econometrics and football analytics. Review as the supervisor
(Carlo Cavicchia, a clustering expert) and the second assessor would, and tell the author what to fix before submission. The deadline is
**tonight**: be specific and prioritised, and finish the critical parts first.

## What the thesis does
Does the change in a player's fuzzy cluster memberships between consecutive seasons have incremental explanatory power for the change in log
Transfermarkt value, beyond performance metrics and basic controls? FBref + Transfermarkt data, 8 Primeira Liga seasons (3,192 player-seasons,
1,499 players; 1,361 season pairs of 697 players in the valuation stage). Each season is clustered separately with the robust fuzzy C-medoids model for
mixed data with a noise cluster (FCMd-MD-NC; D'Urso, De Giovanni & Vitale 2022). Archetypes are aligned across seasons (Hungarian algorithm on
membership-weighted PROFILES). Stage 2: OLS of the change in log value on controls + membership changes (reference archetype omitted),
cluster-robust SEs by player; "core" and "full" baselines; in-sample adjusted-R2 gain and grouped cross-validated out-of-sample R2 gain; fixed vs
random effects + Hausman; a two-stage bootstrap (resample players, re-cluster all seasons, re-anchor to the original solution, re-estimate) for
the generated-regressor problem (Pagan 1984). Objective: explanatory/associational, no causal claim.

## Results as currently written (check them!)
Main configuration (shrunk rates, K=4, m=1.3, rho=1.0; ONE run of a stochastic clustering): membership changes jointly significant against the
full baseline (bootstrap Wald p = 0.015), borderline against the core baseline (p = 0.079); adjusted-R2 gains +0.34/+0.56 pp; out-of-sample gains
+0.08/+0.33 pp; association concentrated in the shift defenders -> wide attackers (coefficient -0.22 core, -0.31 full); present with player
fixed effects; not present for size-of-shift or entropy; PCA scores show nothing. BUT: absent at m=1.2 and K=5; across 30 random draws of the clustering
the full-baseline test is significant in 60-73% of draws (m=1.3-1.5) and the core-baseline test in 27-37%, with p-values ranging over orders of
magnitude, and the median out-of-sample gain over the core baseline is slightly negative; no result survives a Holm correction (20 bootstrap
comparisons). Framing: "weak, specification-dependent evidence of a small association; no robust incremental explanatory power". An EARLIER run of
the same configuration (before two pipeline corrections) gave conventional p = 0.70/0.36.

## Deliberate deviations from D'Urso et al. (scrutinise each)
1. Fixed attribute-type weights proportional to sqrt(number of variables) (after Akhanli & Hennig 2023), because estimating them collapsed in every
   variant tried (Appendix B; reproducible with `analysis/estimated_weights_check.py`).
2. Noise distance = rho * mean(d^2) over all unit-medoid pairs (Dave 1991), not the u^m-weighted average printed in the paper.
3. Success rates shrunk towards the pooled rate (kappa = 10 shots); raw rates as a robustness variant.
4. Same K in every season; scaling constants fixed on the pooled panel.
5. m fixed at 1.3 (the paper's value) although the proposal said m would be chosen by Xie-Beni (within the main configuration XB is lowest at m=1.4).
6. Alignment by profiles instead of medoid distances (the first, medoid-based version gave inconsistent labels in 70% of 120 runs).
7. Rows of same-name players at one club (FBref table join error) and merged player-seasons above 3,100 minutes are excluded.

## Repository
See `README.md` (layout, run order, mapping of every thesis table/figure to its source file). Thesis: `thesis/main.tex` + `thesis/chapters/*.tex`
(+ `thesis/main.pdf` if present). Code: `analysis/*.py`. Results: `analysis/regression/*.csv`, `analysis/clustering/*.csv`, `thesis/thesis_outputs/`.

## PHASE 1 -- THE THESIS (do this first; read all of it before judging)
1.1 **Read** `thesis/main.tex` and every chapter in order (01 to 09 and the appendices); look at the compiled `thesis/main.pdf` for layout, figures,
    table fit, overfull boxes and page count (main text should be about 40-50 pages incl. tables/figures; references and appendices excluded).
1.2 **Examine as an examiner**: does the argument hold from research question -> theory -> data -> methods -> results -> discussion -> conclusion? Do the
    conclusions follow from the evidence (over-claiming / under-claiming)? Is the specification search and the moving result reported honestly and with enough
    caution? Is anything promised but not delivered, or delivered but not motivated? Is the writing clear, non-repetitive, and consistent in terminology
    (archetype names, "core"/"full" baselines, K/m/rho)? Abbreviations written out at first use (the manual requires it)? `\cite` vs `\citeA` (apacite)?
    Cross-references, captions, table notes, units, signs?
1.3 **Number and claim audit.** For every number in Chapters 1, 4-9 and the appendices, check it against its source file (mapping in README.md). Write
    `review/number_audit.csv` (location, claim, value in text, source file, value in source, OK/WRONG/UNVERIFIABLE). Check prose vs tables vs captions vs notes.
    Check statements attributed to other papers against `docs/` (2019 transfer volume in USD; Muller et al. on crowd limitations; Franceschi et al. on the
    Portuguese Liga and multicollinearity; D'Urso et al. numbers; Akhanli & Hennig numbers; Pacifico's data description).
1.4 **Supervisor's comments.** Go through `docs/proposal_with_carlo_comments.pdf` (objective: prediction vs interpretation; causal wording; alignment
    specification - distance, algorithm, ties; generated regressors; overlap with performance controls; why transitions should carry information beyond raw
    statistics; economic meaning of coefficients and of fuzzy memberships; Hausman and unobserved heterogeneity; match rates; Transfermarkt measurement error;
    sample size N, T; PCA/dynamic-clustering positioning; transition definitions). For each: addressed / partly / not, with the location.

## PHASE 2 -- THE CODE
2.1 **Code vs text.** Read the code as a referee: does it do what Chapter 5 says it does? Quote file and line numbers. Targets, in priority order:
- `analysis/fcmd_mdnc.py`: membership update (stable softmax), medoid update, noise distance, Xie-Beni adaptation, k-medoids++ initialisation, fixed weights,
  handling of duplicated rows (bootstrap copies), convergence, `fit_best` and the stability measure.
- `analysis/align_and_select.py`: profile-based Hungarian alignment, propagation of labels (`perm`), the mapping `Ua[:, perm[s]] = U[:, :K]`, ambiguity and
  persistence definitions, how transitions are merged (uid, season_next).
- `analysis/pairs_lib.py`: season pairs, controls, reference archetype, deltas, season dummies, `oos_gain` (is the grouped CV leak-free?).
- `analysis/bootstrap.py`: resampling by player, copy ids, re-clustering, anchoring to the original profiles, estimation, Wald statistic with bootstrap covariance, bias.
- `analysis/build_panel.py`, `make_analysis_panel.py`, `collect_tm_v2.py`: merges and keys, filters, identity resolution, matching thresholds, valuation window.
- `regression.py`, `robustness.py`, `spec_grid.py`, `seed_sensitivity.py`, `alignment_check.py`, `make_tables_figures.py`: logic errors, off-by-one in season pairs,
  silent drops, hard-coded values, name/label mix-ups.
Look for real bugs (wrong keys, leakage, wrong denominators, mislabelled archetypes, stale files read by mistake) and for mismatches between code and text.
2.2 **Reproducibility spot-checks (cheap).** In a scratch copy, re-run `build_panel.py` and `make_analysis_panel.py` and diff against `analysis/panel/*.csv` and
`analysis/logs/*`; run `alignment_check.py`; if time allows run `regression.py` and compare `regression/regression_summary.csv`. Report differences.

## PHASE 3 -- METHODOLOGY AND ECONOMETRICS
The sqrt(n_s) weights argument; the Dave noise distance; the profile-based alignment and the label check (independent enough?); choice of K and the Xie-Beni
adaptation; the reference archetype; the core/full baselines and the "incremental explanatory power" logic given that memberships are deterministic functions of the
same statistics; cluster-robust Wald tests; grouped CV; FE/RE and Hausman with age dropped; the two-stage bootstrap (validity, bias towards zero, SE ratios); the seed
analysis; multiple-comparison handling; selection (players who leave). Is "weak, specification-dependent evidence" the right reading? State what you would conclude.

## PHASE 4 -- DEFENCE
The 15 hardest questions a supervisor or second assessor would ask in the online defence, each with the weak point it targets and a two-sentence outline of a good answer.

## BUDGET
If you run short of budget or context, finish in this order and SAVE `review/REVIEW.md` after each step: 1.1-1.3, 1.4, 2.1 (priority files first), 3, 2.2, 4.

## Output: `review/REVIEW.md` with exactly these sections
1. Verdict (<= 150 words): would this pass, at what level, and the 3 things most likely to hurt the grade.
2. Critical issues (could invalidate a result or be considered an error): location -> problem -> evidence (file, line, number) -> fix -> fixable tonight?
3. Thesis review (Phase 1.2): argument, honesty/caution, writing, structure and format fixes; the 15 worst passages with concrete rewrites or fixes.
4. Number and claim audit (summary; details in `review/number_audit.csv`).
5. Code audit findings (by file, with line numbers; severity: critical / major / minor) and reproducibility results.
6. Methodology and econometrics audit.
7. Supervisor's comments: addressed / partly / not.
8. Defence questions with answer outlines.
9. Prioritised to-do list for the next 6 hours (must do vs nice to have, with time estimates).
Also append "Commands run" and anything you could not verify.

## Style
Direct and concrete; quote the exact sentence or number criticised; no generic praise; if something is fine, say so in one line.
