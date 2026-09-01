---
governing-skill: agent-skills:spec-driven-development
sdlc-step: 4
---

# M3 S6 report — jobs: opf.dc/n1 kinds, INFEASIBLE_LP/UNBOUNDED_LP failure codes

Slice S6 of wave M3 (opf-n1): registers `opf.dc` and `n1` in `jobs.KINDS`, plus two new
structured job-failure codes. AC-8. Commit `5fc26aa` on `wave/03-opf-n1` (pushed).

## What was built

Followed M2's exact four-edit registration mechanism (`src/mambo_power/jobs/registry.py`) for
both new kinds:

- **`opf.dc`**: `options_model=OpfDcOptions`, `result_model=OpfDcResult`, runner `_run_opf_dc`
  wraps `opf.solve_dc_opf`.
- **`n1`**: `options_model=N1Options` (S4's empty options model), `result_model=N1Result`,
  runner `_run_n1` wraps `contingency.n1`.

**The load-bearing design decision — `INFEASIBLE_LP`/`UNBOUNDED_LP` as a runner-side
translation, not a raised-exception mapping.** `opf.solve_dc_opf` itself never raises on a
non-Optimal LP/QP: it reports `OpfDcResult.status` as HiGHS's own model-status string
(`"Optimal"`, `"Infeasible"`, `"Unbounded"`, ...), the same never-raise-on-non-convergence
convention `pf.solve_ac` uses. But AC-8 wants an infeasible/unbounded `opf.dc` job to come back
as a structured job **failure**, not a "successful" `SolveResult` carrying a non-Optimal status
— the spec's own reasoning: a truly infeasible LP has no dispatch at all, unlike a
non-converged AC iterate, which still carries a meaningful partial state. So the translation
happens one layer up, in the `opf.dc` runner itself (`jobs/registry.py:_run_opf_dc`): after
calling `solve_dc_opf`, it checks `result.status` and raises a new job-local exception
(`InfeasibleLpError` for `"Infeasible"`, `UnboundedLpError` for `"Unbounded"`; any other
non-Optimal status falls to `InfeasibleLpError` as the closer reading) when the status isn't
`"Optimal"`. `jobs/run.py`'s runner-exception `except` chain gained two matching clauses
mapping these to `INFEASIBLE_LP`/`UNBOUNDED_LP`, structurally mirroring the M2 R1 fold's
`UnsolvableNetworkError` → `UNSOLVABLE_NETWORK` precedent — even though, unlike that precedent,
the underlying condition here isn't Python-exception-shaped inside `solve_dc_opf` itself; the
job-local exception exists purely to reuse `run()`'s existing except-chain plumbing.

Other edits:
- `jobs/models.py`: `SolveResult.result`'s closed union widened to `AcPowerFlowResult |
  DcPowerFlowResult | OpfDcResult | N1Result`; `FailureCode` widened with `INFEASIBLE_LP`,
  `UNBOUNDED_LP`.
- `jobs/__init__.py`: exports `InfeasibleLpError`/`UnboundedLpError` alongside the existing
  public surface.

## RED → GREEN evidence

`tests/unit/test_jobs.py` (AC-8): KINDS contract updated to expect exactly 4 kinds; new
`opf.dc`/`n1` happy-path tests (typed result + provenance); the purity test
(`test_run_is_pure_equal_results_modulo_timing`) and JSON round-trip test
(`test_result_round_trips_through_json_with_the_kinds_result_type`) parametrized/extended to
cover both new kinds alongside `pf.ac`/`pf.dc`; new
`test_infeasible_opf_dc_is_infeasible_lp_not_internal` — a hand-built `case14` variant with
every generator's `p_max_mw` collapsed to `0.01` (load unreachable) yields
`status="failed"`, `error.code == "INFEASIBLE_LP"`.

RED confirmed with real evidence, not assumed: `git stash push` on just the four
`src/mambo_power/jobs/*.py` implementation files (keeping the updated test file in place), then
`pytest tests/unit/test_jobs.py` — **9 failed, 23 passed**. All 9 failures are exactly the
new/changed assertions: `KINDS` still 2 entries, `opf.dc`/`n1` still `UNKNOWN_KIND`, the
infeasible-LP test getting `UNKNOWN_KIND` instead of `INFEASIBLE_LP`. Popped the stash, re-ran:
**32 passed**.

## A real regression the full suite caught (not `test_jobs.py` itself)

`test_unknown_kind_is_a_failed_result` and `examples/04_jobs_api.py`'s own "unknown kind" demo
both used `kind="opf.dc"` as their unknown-kind example — no longer unknown once this slice
registers it. `test_unknown_kind_is_a_failed_result` was caught immediately (same file, same
`pytest` run); `examples/04_jobs_api.py`'s assertion failure (`assert unknown.error is not
None` — false, since `opf.dc` now solves successfully on `case14`) only surfaced on the full
repo suite via `tests/unit/test_examples_run.py`, which executes every `examples/*.py` script
end to end. Both switched to `kind="market.nodal"` — a real future kind name named in the wave
spec's own provenance comment (`"market.*"`), still genuinely unregistered. `examples/` is not
named in this slice's out-of-scope list (only `docs/` is), and fixing a regression this slice's
own change caused is in scope regardless.

`docs/manual/jobs.md` has the identical stale "`opf.dc` is unknown" prose example (line 200,
plus the line-217 sample output), but no test under `tests/` executes or checks it against live
output — confirmed by search, not assumed. `docs/` is explicitly out of scope for this slice
(named in the dispatch brief); left for S7 (docs) to fix alongside its own manual-page work.

## Verification

- `uv run --no-sync pytest -q tests/unit/test_jobs.py` — 32 passed.
- `uv run --no-sync pytest -q` (full repo suite) — **572 passed**, 228.06s, same 10
  pre-existing pandapower deprecation/divide warnings as prior slices, unrelated to this change.
- `ruff check .` — clean (fixed two `E501` line-too-long findings: a long f-string in
  `_run_opf_dc`, a long list comprehension in the new test helper).
- `ruff format --check .` — clean.
- `mypy` (project config, `files = ["src"]`) — clean, 39 source files, no issues.

## Carry-overs (named, not silently dropped)

- `docs/manual/jobs.md`'s stale "`opf.dc` is unknown" example (line 200/217) — S7's job, per
  this slice's own out-of-scope list.

## Commit

`5fc26aa` on `wave/03-opf-n1`, pushed (fast-forward from S3's `8d2c4e6`). 6 files, 176
insertions / 30 deletions: `examples/04_jobs_api.py`, `src/mambo_power/jobs/__init__.py`,
`src/mambo_power/jobs/models.py`, `src/mambo_power/jobs/registry.py`,
`src/mambo_power/jobs/run.py`, `tests/unit/test_jobs.py`.

No shared-worktree coordination needed this slice — no other agent was active in
`mambo-power-m3` (per the dispatch brief), and `git status --porcelain` showed only my own
edits at every checkpoint.
