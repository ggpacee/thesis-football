# Master thesis: tracking player profile evolution through robust fuzzy clustering (Primeira Liga)

Author: Gonçalo Passinhas. Supervisor: Carlo Cavicchia. Erasmus School of Economics, MSc Data Science & Marketing Analytics.

Question: do changes in a player's fuzzy cluster memberships between consecutive seasons have incremental explanatory power for the
change in his Transfermarkt market value, beyond performance statistics? Eight Primeira Liga seasons (2017/18-2024/25).

## Layout
- `thesis/`      LaTeX source (`main.tex`, `chapters/`, `MyReferencesFile.bib`, `thesis_outputs/` = every table and figure of the thesis,
                 `main_proposal.tex` = the approved proposal).
- `analysis/`    all Python code (flat, because the scripts import each other) and the data/results needed to re-run it:
                 `fbref_all_seasons.csv` (collected FBref statistics), `panel/` (player-season panels), `tm_out/` (Transfermarkt links and
                 values; raw HTML/JSON caches are not included), `clustering/` (memberships, medoids, diagnostics of the MAIN setting
                 rho=1.0, m=1.3), `regression/` (all test results), `logs/` (printouts of the data-construction steps).
- `docs/`        local only (git-ignored): papers, the thesis manual, the supervisor's comments.
- `review/`      where the reviewer writes the review (`REVIEW.md`).

## Run order (from inside `analysis/`; every script reads the files written by the earlier ones)
| step | script | what | runtime |
|---|---|---|---|
| 1 | `test_fbref_collection_v2.py` | collects FBref tables (needs internet; NOT needed to re-run, the result is `fbref_all_seasons.csv`) | - |
| 2 | `collect_tm_v2.py` | Transfermarkt squads, links, value histories (NOT needed to re-run; results in `tm_out/`) | - |
| 3 | `build_panel.py` | one row per player-season, variables, scaling -> `panel/panel_player_season.csv` | seconds |
| 4 | `make_analysis_panel.py` | identity, valuations, outcome -> `panel/analysis_panel.csv` | seconds |
| 5 | `align_and_select.py` | clusters every season, aligns archetypes (profile-based Hungarian), transitions, K diagnostics -> `clustering/` | 6-10 min |
| 6 | `regression.py` | main regressions, baselines, CV -> `regression/regression_summary.csv` | 3 min |
| 7 | `robustness.py` | sample/outcome variations, FE/RE, Hausman | 1 min |
| 8 | `spec_grid.py` | 120 specifications (creates `clustering_sens_*` folders, git-ignored) | 10-15 min |
| 9 | `bootstrap.py` | two-stage bootstrap, 10 configurations x 500 replications | 30-40 min |
| 10 | `extra_results.py`, `sensitivity_and_benchmark.py`, `seed_sensitivity.py`, `alignment_check.py`, `estimated_weights_check.py` | coefficient tables, PCA benchmark, 30-seed analysis, label check, Appendix B | 1-3 min each |
| 11 | `make_tables_figures.py` | tables and figures -> `thesis_outputs/` | 1 min |

Scripts that write results overwrite files in `analysis/`. To re-run anything, work in a copy: `cp -r analysis /tmp/analysis_copy`.
All random numbers use fixed seeds; with the same row order a re-run reproduces the stored memberships exactly.

## Where each thesis table/figure comes from
| thesis | file |
|---|---|
| Table 4.1 sample steps | `analysis/logs/build_panel_output.txt` |
| Table 4.2 sample by season, Table 4.4 descriptives | `thesis/thesis_outputs/tables/sample_by_season.csv`, `summary_statistics.csv` |
| Table 6.1 K diagnostics | `analysis/clustering/select_K_summary.csv` |
| Tables 6.2-6.3 profiles, medoids | `thesis_outputs/tables/archetype_profiles.csv`, `medoids_by_season.csv` |
| Table 6.4 main coefficients | `thesis_outputs/tables/main_regression.csv` (from `analysis/regression/bootstrap_shrunk_K4_{core,full}.csv`) |
| Table 6.5 alternative summaries | `analysis/regression/regression_summary.csv` |
| Table 7.1 K and rates | `analysis/regression/robustness_configurations.csv`, `bootstrap_summary.csv` |
| Table 7.2 sample/outcome variations | `analysis/regression/robustness_variations.csv` |
| Table 7.3 PCA and minimal baseline | `pca_benchmark.csv`, `minimal_baseline.csv` |
| Table 7.4 fuzziness | `spec_grid.csv`, `bootstrap_summary.csv` |
| Table 7.5 / Figure 7.1 grid | `spec_grid.csv`, `spec_heatmap.png` |
| Table 7.6 / Figure 7.2 seeds | `seed_sensitivity.csv`, `seed_sensitivity.png` |
| Appendix B estimated weights | `analysis/regression/estimated_weights_2324.csv` |
| Appendix C coefficients | `thesis_outputs/tables/coef_*.csv` |

## Data note
`fbref_all_seasons.csv` and the Transfermarkt files are derived from public web pages (FBref via `soccerdata`; Transfermarkt web endpoints).
This repository is private and for review only; do not publish it, and check the sites' terms before sharing the data further.
