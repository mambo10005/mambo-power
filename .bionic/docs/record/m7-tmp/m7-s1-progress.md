# M7 S1 — Hessian unification + generator-side overlap guard — progress

Worktree `/c/Users/mambo/AppData/Local/Temp/claude/C--Claude-Projects-mambo-power/0d397067-49ef-4969-aefa-5709948393ef/scratchpad/bionic-unified`, branch `wave/07-agents`, base `6ca9dcc`.
S1 head: **a22922d**.
NOTE: other slices (S2/S3/S6) hold uncommitted work in this same worktree
(`market/strategy.py`, `market/nodal.py`, `results/market.py`, `tests/_agents.py`, ...).
S1 touched only its own four paths and committed only those.

## Done
- [x] `_pass_diagonal_hessian` in `dc_opf.py` beside `_extract_and_validate`;
      `multiperiod` + `zonal` are callers; `redispatch` proved a non-caller by readback
- [x] Generator-side overlap guard in `_extract_and_validate`
- [x] AC-1(a): overlay tree, `diff -rq` names exactly the three source files,
      unmodified M6 suite **992 passed / 4 skipped**, overlay proved to be what loads
      inside the run's own process
- [x] AC-1(b): one-line sabotage inside the helper, red in all three callers' modules,
      residuals named
- [x] AC-1(c): pre-guard silent wrong answer reproduced (223.192107 -> -0.000000 MW,
      objective +2409.699637, status Optimal); `tests/unit/test_opf_overlap_guard.py` 7 passed
- [x] Committed a22922d (explicit paths)

## In flight
- [ ] Named gate sweep at a22922d (running)
- [ ] Final report `.bionic/docs/record/m7-s1-report.md`
