# M4 S6 — jobs: `market.nodal` kind, shared status-translation helper

Slice S6 (implementor, standard). TDD throughout: RED (`tests/unit/test_jobs.py` extended in
place, confirmed failing — 8 tests, `AttributeError`/`UNKNOWN_KIND` collisions/missing spec
entries), then implementation, then GREEN (36/36 in the file, 645/645 full suite).

## Request-shape decision (made by this slice, not handed down)

The dispatch flagged a real open question: `market.nodal`'s `solve_nodal(scenario: Scenario,
options)` takes a `Scenario`, not a bare `Network`, unlike every prior kind's runner
(`(Network, options) -> result`). Does `SolveRequest` need to grow a `scenario: Scenario | None`
alternative field?

**Resolved: no.** Reading `model/scenario.py` directly (S1's shipped code, not the pre-S1
research proposal) confirms `Scenario` is, this wave, genuinely just:

```python
class Scenario(BaseModel):
    network: Network = Field(...)
```

— nothing else. Since `Scenario(network=net)` is a trivial, lossless wrap of exactly the
`Network` every other runner already receives, `_run_market_nodal` performs that wrap itself,
inside the runner:

```python
def _run_market_nodal(net: Network, options: BaseModel | None) -> BaseModel:
    assert isinstance(options, MarketNodalOptions)
    result = solve_nodal(Scenario(network=net), options=options)
    ...
```

`SolveRequest` stays untouched — no new field, no widened request-side union. Every `Runner`
keeps the single `(Network, options) -> result` signature `jobs/registry.py`'s `Runner` type
alias already declares. This is presented as a decision, not a discovery of an absent question:
the design interview's own research (§7) left it explicitly open pending S1 landing a real
`Scenario` shape; S1 landed the shape that makes the wrapping trivial, so the "real design
question" the research worried about (would `Scenario` carry fields a bare `Network` can't
supply?) did not materialize this wave. Revisit only if a future wave (`periods`, agent
strategies) gives `Scenario` fields a `Network` alone cannot carry.

## What was built

**`src/mambo_power/jobs/registry.py`**:

1. **`market.nodal` `KindSpec`** registered — `options_model=MarketNodalOptions`,
   `result_model=MarketNodalResult` (both S4's, wired in as-is), `runner=_run_market_nodal`.
2. **`_translate_non_optimal_status(kind: str, status: str, message: str | None) -> NoReturn`**
   — the non-Optimal-status-to-structured-failure translation factored out of `_run_opf_dc`
   (wave spec Design item 6). `"Unbounded"` → `UnboundedLpError`; every other non-`"Optimal"`
   status → `InfeasibleLpError`. Both `_run_opf_dc` and the new `_run_market_nodal` call it —
   genuinely one function, not two copies of the same ~15 lines (proved below, not asserted).
3. `_run_opf_dc` refactored to call the shared helper; its own behavior is unchanged (same two
   exception types, same message format — `f"{kind} LP/QP is ..."`, with `kind` now a parameter
   instead of a hardcoded `"opf.dc"` string).

**`src/mambo_power/jobs/models.py`**: `ResultModel` widened to
`AcPowerFlowResult | DcPowerFlowResult | OpfDcResult | N1Result | MarketNodalResult` (mechanical,
same step every prior kind took); module docstring's provenance note updated.

**`tests/unit/test_jobs.py`** (extended in place, not duplicated):

- `KNOWN_KINDS` gained `"market.nodal"`; `test_kinds_lists_exactly_the_m3_kinds` and
  `test_every_kind_has_models_and_a_callable_runner` extended with `market.nodal`'s spec
  assertions.
- New `test_run_market_nodal_on_case14_is_ok_with_typed_result_and_provenance` — `case14`'s
  loads carry no bid, so this exercises AC-5's price-taker reduction at the jobs boundary
  (status `"ok"`, typed `MarketNodalResult`, `provenance == result.provenance`).
- `test_run_is_pure_equal_results_modulo_timing` parametrized to include `market.nodal`.
- `test_result_round_trips_through_json_with_the_kinds_result_type` extended with
  `("market.nodal", MarketNodalResult)`.
- New `test_infeasible_market_nodal_is_infeasible_lp_not_internal` — the existing
  `_infeasible_net` fixture (contradictory generator bounds) routed through `market.nodal`
  gives `status="failed"`, `error.code == "INFEASIBLE_LP"`, not `INTERNAL`.
- New `test_opf_dc_and_market_nodal_share_the_same_status_translation_function` — a monkeypatch
  spy on `jobs.registry._translate_non_optimal_status` records `["opf.dc", "market.nodal"]`
  across both kinds' infeasible-LP runs: proof the helper is one function object both runners
  exercise, not a coincidentally-identical second copy.
- `test_unknown_kind_is_a_failed_result` fixed: it had used `kind="market.nodal"` as its
  "genuinely unknown kind" example — now a real, registered kind after this slice. Swapped to
  `"market.zonal"` (spec Not Doing: zonal clearing is M6), which is still unregistered.

## A regression this slice's own change caused, found and fixed

`examples/04_jobs_api.py` (existing since M2) had the identical collision:
`jobs.run(jobs.SolveRequest(kind="market.nodal", network=net))` as its "unknown kind" failure
demo. Registering `market.nodal` broke it (`assert unknown.error is not None` failed since the
kind now succeeds) — caught by the full suite's `test_examples_run.py::test_example_runs_to_
completion[04_jobs_api]`, not by anything in `jobs/*.py`'s own test file. Fixed the same way:
swapped to `kind="market.zonal"  # not registered yet`. This is the one file touched outside
`jobs/*.py`/`tests/unit/test_jobs.py` — necessary, mechanical, and directly caused by this
slice's own change (confirmed: the full suite failed without this fix, passed with it).

**Left alone, flagged for S7**: `docs/manual/jobs.md` has a hand-written code block and literal
output text using `kind="market.nodal"` as its own "unknown kind" example (`UNKNOWN_KIND |
unknown kind "market.nodal"; registered kinds: n1, opf.dc, pf.ac, pf.dc`) — now stale in two
ways (market.nodal is real; the registered-kinds list is missing it). Not exercised by any test
(`mkdocs build --strict` doesn't execute code blocks), so it did not block this slice's GREEN,
but it is now factually wrong prose. Squarely S7's territory (the nodal-market manual page is
S7's own deliverable per the plan) — not touched here to avoid stepping on that slice's files.

## RED evidence

```
$ uv run --no-sync pytest -q tests/unit/test_jobs.py
...
8 failed, 28 passed in 1.83s
```
Failures: `test_kinds_lists_exactly_the_m3_kinds`, `test_every_kind_has_models_and_a_callable_
runner`, `test_register_adds_a_kind_and_refuses_duplicates` (all `KNOWN_KINDS` mismatches —
`market.nodal` not yet in `KINDS`), `test_run_market_nodal_on_case14_...` /
`test_run_is_pure_equal_results_modulo_timing[market.nodal]` / `test_result_round_trips_...`
(the kind not registered → `UNKNOWN_KIND` instead of `ok`), `test_infeasible_market_nodal_is_
infeasible_lp_not_internal` (same reason), `test_opf_dc_and_market_nodal_share_the_same_status_
translation_function` (`AttributeError: module 'mambo_power.jobs.registry' has no attribute
'_translate_non_optimal_status'`).

## GREEN evidence

```
$ uv run --no-sync pytest -q tests/unit/test_jobs.py
........................................ [100%]
36 passed in 1.35s
```

Full suite (run twice — once before, once after the `examples/04_jobs_api.py` fix):

```
$ uv run --no-sync pytest -q
645 passed, 10 warnings in 292.15s (0:04:52)
```

(645 includes S5's `tests/_bids.py`-derived and pandapower-parity tests, landed concurrently in
this shared worktree — not audited here, S5 owns that count; confirmed no `jobs/*.py` file
conflicts via `git status --porcelain` before staging.)

```
$ uv run --no-sync ruff check .
All checks passed!
$ uv run --no-sync ruff format --check .
134 files already formatted   # (135 with examples/04_jobs_api.py touched, reformatted clean)
$ uv run --no-sync mypy
Success: no issues found in 43 source files
```

## Commit

`df565c6` on `wave/04-nodal-market` (on top of S4's `ec4ba22`), pushed — remote was still at
`ec4ba22` when checked (S5 had not pushed yet), so no rebase was needed. Staged exactly the four
files this slice touched: `examples/04_jobs_api.py`, `src/mambo_power/jobs/models.py`,
`src/mambo_power/jobs/registry.py`, `tests/unit/test_jobs.py` — confirmed via `git status
--porcelain` that S5's untracked files (`tests/_bids.py`, `tests/parity/test_market_nodal_vs_
pandapower.py`, `tests/unit/test_bids.py`) were present but not staged.

Plan updated (`.bionic/docs/plans/epic-01-foundation/wave-04-nodal-market.plan.md`): AC-7
evidence block filled, status cell flipped `pending` → `done`, dispatch ledger row for
`m4-s6-jobs` flipped `active` → `done` with the real commit sha.

## Not done by this slice (explicitly out of scope, per the dispatch)

`opf/dc_opf.py`, `market/nodal.py`, `results/market.py` (consumed, not modified — no changes
needed to `MarketNodalOptions` after all, since the request-shape question resolved without
touching it). `tests/_bids.py`/pandapower parity (S5's, landed concurrently, untouched by this
slice). `docs/` (S7's job — one known stale-text follow-up flagged above).
