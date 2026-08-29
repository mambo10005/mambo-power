# M7 S7 progress

## Status: blocked on a scope question, working on unblocked parts in parallel

Started: registering `market.agents` (W6/AC-6), worktree `mambo-power-m7`, branch `wave/07-agents`.

## Blocker reported to team-lead (awaiting reply)

`jobs/models.py`'s `ResultModel` union needs `MarketAgentsResult` added, or `jobs.run()`'s final
`SolveResult(...)` construction raises `ValidationError` on every successful `market.agents` run
(confirmed empirically: a BaseModel instance outside a pydantic Union of BaseModels is rejected,
not accepted). `jobs/models.py` is not on my file list. Reported via SendMessage; continuing with
everything else meanwhile.

## Done so far
- Read wave-07 spec (W6, AC-6), existing `market/agents.py`, `market/strategy.py`,
  `results/agents.py` (all pre-existing from S2/S3/S4), `jobs/registry.py`, `jobs/models.py`,
  `jobs/run.py`.
- Confirmed `results/__init__.py` already exports `MarketAgentsResult`, `AgentOfferResult`,
  `TerminationReason` (uncommitted in the shared tree already — task 2 already done by someone
  upstream; verifying and will commit as mine since it's on my file list).
- Confirmed the four AC-6 caller mistakes' expected failure paths:
  - unknown strategy kind -> pydantic discriminator error at `MarketAgentsOptions` validation ->
    BAD_OPTIONS (no runner code needed).
  - non-positive `max_iterations` / `offer_tol` -> `Field(gt=0)` -> BAD_OPTIONS (no runner code
    needed).
  - strategy naming a nonexistent generator -> `solve_agents` raises plain `ValueError` from
    `_resolve_agents`, which `jobs.run()`'s catch-all currently turns into INTERNAL (the M6 bug
    class) -> needs my runner to catch `ValueError` and re-raise `NetworkValidationError` (mirrors
    M6 zonal's `UnzonedBusError` -> `NetworkValidationError` translation), which `run()` already
    maps to VALIDATION.

## Next
- Write `_run_market_agents` in `jobs/registry.py`, register the kind (KINDS -> 8).
- Write `test_jobs.py` coverage for AC-6 (round trip, four caller mistakes, KINDS==8).
- Sabotage sweep over the new runner's ValueError translation.
- Confirm `test_docs_registry_listing.py` and `test_api_docs_coverage.py` go red as expected;
  leave both, state why.

## Update: registry.py + test_jobs.py written, sabotage-proven, still blocked on jobs/models.py

- `_run_market_agents` written in `jobs/registry.py`: translates `solve_agents`'s caller-mistake
  `ValueError` into `NetworkValidationError` (DANGLING_REF), mirroring `_run_market_zonal`'s
  `UnzonedBusError` treatment; shares `_translate_non_optimal_status`. Kind registered, `KINDS`
  now 8 (verified directly: `len(KINDS) == 8`, sorted list correct).
- Found and fixed my own bug during manual verification: `NetworkValidationError(ValidationIssue(...))`
  (a bare instance) silently iterates over the model's own `__iter__` (field, value) pairs instead
  of the list of issues intended -- fixed to `NetworkValidationError([ValidationIssue(...)])`.
- All four AC-6 caller mistakes confirmed end-to-end through `run()`, manually and via
  `tests/unit/test_jobs.py`'s new `test_ac6_four_caller_mistakes_never_report_internal` (green,
  30 passed among the new/updated tests -- the only reds are the "ok"-path tests blocked on
  jobs/models.py, see below).
- **Sabotage sweep, done on a scratch-directory overlay (not the shared worktree)**: copied
  `src`+`tests` to a temp dir, ran via `PYTHONPATH=<scratch>/src` against the real venv's
  python.exe (confirmed via `__file__` print that imports resolved to the scratch copy, not
  `/c/Users/mambo/AppData/Local/Temp/claude/C--Claude-Projects-mambo-power/0d397067-49ef-4969-aefa-5709948393ef/scratchpad/bionic-unified`). Removed the `except ValueError -> NetworkValidationError`
  translation in the scratch copy's `_run_market_agents`: the two tests that assert VALIDATION for
  a strategy naming a nonexistent generator (`test_market_agents_strategy_naming_a_nonexistent_
  generator_is_a_validation_failure`, and that case's row of
  `test_ac6_four_caller_mistakes_never_report_internal`) go red with `code='INTERNAL'` --
  reproducing the exact M6 defect class. The other two rows of the same parametrized test
  (unknown-strategy-kind, non-positive bounds) stay green under the same sabotage, because those
  are caught earlier at `MarketAgentsOptions` validation, untouched by this change -- confirming
  the test suite discriminates the actual mechanism, not a coincidental pass. Sabotage reverted
  (scratch dir deleted); shared worktree was never touched.
- Confirmed (manually, then reproduced in the overlay) that `run_json`/`run` do NOT crash on the
  models.py gap -- `run()`'s own `isinstance(raw, ResultModel)` guard catches it first and reports
  a graceful `INTERNAL` failure. Reported this correction to team-lead already.

## Still blocked

`jobs/models.py`'s `ResultModel` union needs `MarketAgentsResult` added for any successful
`market.agents` run to report `status="ok"` instead of `INTERNAL`. 6 tests red for exactly this
reason (all "ok"-path tests: happy path x2, purity x2, JSON round trip x2). Every caller-mistake /
registration / request-JSON-round-trip test is green already. Awaiting team-lead's go-ahead to
touch `jobs/models.py` (not on my file list) since no other slice appears to own it.

## Update: full pytest tests/unit run (888 tests): 877 passed, 11 failed

- 3x docs (S8's, expected).
- 6x mine, blocked on jobs/models.py.
- 2x test_market_agents.py (S4's file, pre-existing, not caused by this slice, reported to
  team-lead to route -- termination_reason "cycle" vs "converged" at step 0.1/0.7, the exact
  cases MarketAgentsOptions's own docstring/test flags as ULP-tolerance edge cases).
- results/__init__.py's __all__ verified alphabetically sorted and complete.
- Report written to .bionic/docs/record/m7-s7-report.md, updated with full-suite results.
- Still holding: no commit yet, waiting on team-lead's answer re: jobs/models.py before finishing.
