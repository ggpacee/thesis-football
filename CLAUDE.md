# Instructions for Claude Code in this repository

You are REVIEWING a master's thesis (the LaTeX text in `thesis/`) AND its code (`analysis/`) - both matter equally. Read `README.md` first, then `REVIEW_TASK.md` and carry out that task.

Rules
- Do NOT modify anything in `thesis/` or `analysis/`. Write your output only to `review/REVIEW.md` (and, if useful, `review/number_audit.csv`).
  Put scratch code in `review/scratch/`. If you re-run a script, do it in a copy: `cp -r analysis review/scratch/analysis_copy` and run there.
- Long jobs (do not run unless a check truly needs them): `bootstrap.py` (30-40 min), `spec_grid.py` (10-15 min), `align_and_select.py`
  (6-10 min), `regression.py` (3 min). Short, safe checks: `build_panel.py`, `make_analysis_panel.py`, `alignment_check.py`,
  `seed_sensitivity.py` with fewer seeds, and anything that only reads the stored CSVs.
- Never invent numbers or references. Say "could not verify" when you cannot. Distinguish verified-in-files from opinion.
- Write findings to `review/REVIEW.md` as you go, so nothing is lost if the session ends early.
- `docs/` (git-ignored) may contain the papers, the thesis manual and the supervisor's comments: read them when needed.
