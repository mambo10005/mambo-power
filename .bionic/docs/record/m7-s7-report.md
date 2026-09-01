# M7 S7 report — jobs kind `market.agents`

Role: implementor. Wave M7 (agents), slice S7 (the jobs half of W6/AC-6). Worktree
`C:\Claude Projects\mambo-power-m7`, branch `wave/07-agents`. Started from the tip of that
branch as found (`74a0532`, S4's fixed-point loop landed, plus uncommitted work from S2/S3/S5/S6
in the shared tree); landed against `67d189e` (S4's F6 float-noise fix, which also committed the
`results/__init__.py` re-export I had been carrying, see below).

**Status: complete.** The `jobs/models.py` blocker (below) was resolved by team-lead's grant;
everything gated on it is now proven green.

## Scope and ownership

Owned per brief: `src/mambo_power/jobs/registry.py`, `src/mambo_power/results/__init__.py`,
`tests/unit/test_jobs.py` (and any other `tests/unit/test_jobs*.py`, none other exist). Grant
during this slice added `src/mambo_power/jobs/models.py` (see "The blocker" below; recorded by
team-lead as finding **F7**: ownership was assigned by module, but "one union member per
registered kind" is a cross-cutting invariant living in a different module from the
registration, and M5, M6 and M7 have each hit it). Docs (`docs/**`) explicitly out of scope —
S8's, briefed for phase 2, blocked on this slice's registration landing.

## The blocker, and the corrected mechanism

Registering `market.agents` in `registry.py` alone is not sufficient: `jobs/models.py`'s
`SolveResult.result: ResultModel | None` is a closed pydantic union that did not include
`MarketAgentsResult`. Flagged to team-lead before writing any test that would have gotten this
wrong; granted access to the file (sent four times across crossed messages — team-lead's
standing answer was "go", no further confirmation needed).

**My first message to team-lead was wrong about the failure mode, and I self-corrected it by
running the code rather than by re-reasoning.** I initially said the gap would make
`SolveResult(...)`'s construction raise an uncaught `ValidationError`, reasoning from Python
Union-validation semantics in the abstract. Actually running it showed otherwise: `run.py:198`
carries its own `isinstance(raw, ResultModel)` guard, three lines before that construction, which
catches the mismatch first and returns a graceful `status="failed"`, `code="INTERNAL"` failure —
`run()`'s "never raises" contract was never actually at risk. I sent a correction to team-lead
within the same exchange, before they had to catch it themselves (they had independently found
and were about to send me the identical correction — our messages crossed). Team-lead noted this
is the second self-correction this wave caught by re-running rather than re-reading (the other
being S4's, on a different question) and asked it be recorded here: **re-running beats
re-reasoning when the two disagree, and this exchange is a second data point for it this wave
alone.**

The corrected, verified consequence: `jobs.run()` does not crash — but *every* `market.agents`
call, correct usage included, came back `INTERNAL` instead of `ok`. That is the same defect class
M6's walk found on `market.zonal` (a caller doing everything right receiving an internal-error
code) and silent-plausible rather than loud, which is worse for exactly the reason this epic has
named in every wave.

## What changed

### `src/mambo_power/jobs/models.py`

- Added `MarketAgentsResult` to the `mambo_power.results` import and to the `ResultModel` closed
  union (`SolveResult.result`'s annotation), in exactly the shape M6's S7b added
  `MarketZonalResult` at `4432163` — the same mechanical widening every prior kind's wave has
  made to this file. Module docstring's kind-history list updated to name M7/`MarketAgentsResult`
  too.

### `src/mambo_power/jobs/registry.py`

- Imported `MarketAgentsOptions`, `solve_agents` from `mambo_power.market.agents` and
  `MarketAgentsResult` from `mambo_power.results`.
- New `_run_market_agents(scenario, options) -> BaseModel`: calls `solve_agents(scenario,
  options=options)`, translates a non-`"Optimal"` status through the same shared
  `_translate_non_optimal_status` helper every other market runner uses (now five callers, not
  four — `InfeasibleLpError`/`UnboundedLpError`/`_translate_non_optimal_status` docstrings
  updated to say so), and translates the plain `ValueError` `solve_agents` raises for a caller
  mistake in the agent set (unknown generator, generator not in the arrays, generator with no
  cost, or an injected `MarkupStrategy` too coarse for `offer_tol`) into a
  `NetworkValidationError` (`DANGLING_REF`, path `options.strategies`) — the same translation
  `_run_market_zonal` applies to `UnzonedBusError`, and for the same reason: without it this
  specific caller mistake falls into `jobs.run()`'s catch-all and reports `INTERNAL`, exactly the
  defect class M6's walk found four instances of on `market.zonal`.
- An unknown `StrategyConfig.kind` and a non-positive `max_iterations`/`offer_tol` never reach
  the runner at all — both fail `MarketAgentsOptions` validation itself (a discriminated union
  with no matching tag, and `Field(gt=0)`, respectively), so `jobs.run()`'s own step-2 options
  validation already reports them as `BAD_OPTIONS` before any runner is called. No new code was
  needed for these two of the four AC-6 mistakes; verified directly (see AC-6 proof below).
- `register(KindSpec(kind="market.agents", options_model=MarketAgentsOptions,
  result_model=MarketAgentsResult, runner=_run_market_agents))` — the 8th registration. `KINDS`
  now has exactly 8 entries (`len(KINDS) == 8`, verified); `kinds()` returns them sorted.
- Bug found and fixed during my own manual verification, before any test caught it:
  `NetworkValidationError(ValidationIssue(...))` — passing a bare `ValidationIssue` instance
  rather than a list — silently iterates over the model's own `__iter__` (pydantic `BaseModel`
  yields `(field_name, value)` tuples), producing three bogus "issues" instead of one real one.
  Fixed to `NetworkValidationError([ValidationIssue(...)])`, matching `_run_market_zonal`'s own
  (correct, list-comprehension) usage.

### `src/mambo_power/results/__init__.py`

No change by me — S4's commit `67d189e` landed the `MarketAgentsResult`/`AgentOfferResult`/
`TerminationReason` re-export I had been carrying uncommitted (per the brief: "S4 raised this as
a carry and it is now yours"). I verified its correctness and completeness (every public name in
`results/agents.py` present, `__all__` alphabetically sorted) before it landed; nothing left to
do here — the file is clean in `git status` and not part of my commit.

### `tests/unit/test_jobs.py` (112 tests)

New imports: `MarketAgentsOptions`, `MarketAgentsResult`, `ConfigDict`, `datetime`/`UTC`,
`duopoly_network`, `smooth_pivotal_network` (the latter two from `tests/_agents.py`, S3's W7
fixtures).

Pre-existing lines touched, all the necessary count/name bumps every prior wave's slice has made
to this same file (each explained at its own site in the diff):
- `KNOWN_KINDS`: added `"market.agents"`.
- `ALL_SEVEN_KINDS` -> `ALL_EIGHT_KINDS` (renamed, widened), its one usage
  (`test_run_is_pure_across_all_seven_kinds` -> `test_run_is_pure_across_all_eight_kinds`) and
  comment.
- Two pre-existing exact-count assertions bumped 7 -> 8:
  `test_kinds_registers_market_multiperiod_as_the_sixth_kind`,
  `test_kinds_registers_market_zonal_as_the_seventh_kind`.

New tests, grouped under a `# wave M7 S7 / AC-6` banner (mirroring the M6 banner already in this
file):

- **KINDS contract**: `test_kinds_registers_market_agents_as_the_eighth_kind`,
  `test_kinds_is_sorted_with_market_agents_in_place`.
- **Happy path**: `test_run_market_agents_on_smooth_pivotal_is_ok_with_typed_result_and_provenance`
  (price-taker strategy; asserts `status="ok"`, a **typed** `isinstance(out.result,
  MarketAgentsResult)`, `converged`/`termination_reason`/`markup==0`/provenance checks) and
  `test_run_market_agents_with_no_options_is_ok_no_agents_case14` (the no-options degenerate
  case every other kind's smoke test uses — `strategies={}` default, offers empty).
- **Purity**: folded into the widened `test_run_is_pure_across_all_eight_kinds` parametrize,
  plus a dedicated `test_run_is_pure_for_market_agents_with_a_markup_strategy` on the duopoly
  fixture.
- **JSON round trip, StrategyConfig union crosses as data**:
  `test_request_with_market_agents_strategy_config_round_trips_through_json`,
  `test_result_round_trips_through_json_for_market_agents`,
  `test_market_agents_strategy_config_round_trips_through_run_json_as_data_not_a_callable` — the
  AC-6 "crosses as data, never a callable" clause, driven through `run_json` (a JSON *string*,
  not a dict, per the brief's explicit warning) and asserting the serialized `StrategyConfig`
  carries only `{"kind", "step"}` — no importable path, no callable.
- **The four AC-6 caller mistakes**:
  `test_market_agents_unknown_strategy_kind_is_bad_options`,
  `test_market_agents_strategy_naming_a_nonexistent_generator_is_a_validation_failure`,
  `test_market_agents_non_positive_bounds_are_bad_options` (parametrized x4: max_iterations
  zero/negative, offer_tol zero/negative), and the direct AC-6 statement
  `test_ac6_four_caller_mistakes_never_report_internal` (parametrized over all four, asserting
  `code in ("BAD_OPTIONS", "VALIDATION")`).
- **Shared status-translation function**: `test_market_agents_shares_the_status_translation_
  function` — stubs `solve_agents` itself (rather than a genuinely infeasible LP, unreachable on
  `tests/_agents.py`'s elastic-only fixtures) to return a canned non-Optimal result, spies on
  `_translate_non_optimal_status`, confirms `market.agents`'s runner calls the same shared
  function object every other market kind's runner does.
- **The `run.py:198` union guard, kept live** (team-lead's explicit ask, since the widening this
  slice made could otherwise let that guard rot into decoration):
  `test_run_py_198_union_guard_still_fires_for_a_result_model_never_added_to_the_union`. A
  throwaway `_UnregisteredResultModel` is registered as a temporary kind's own `result_model`
  *and* returned by its runner, so the earlier `type(raw) is not spec.result_model` check
  passes (they match) and only the union-membership check can catch it — distinct from the
  pre-existing `test_runner_returning_the_wrong_type_is_internal`, which exercises the *earlier*
  check (a real, registered-elsewhere model returned for the wrong kind). This is precisely the
  shape of mistake a slice forgetting to widen `ResultModel` produces — see the sharp sabotage
  below, which reproduces it for real.
- **Backward compatibility**: `PRIOR_SEVEN_KINDS` + `test_prior_seven_kinds_still_accept_their_
  existing_network_form_unchanged` — the seven pre-existing kinds' `network=` form is unchanged
  by this slice's widening.

## AC-6 outcome — all clauses proven

| clause | evidence |
|---|---|
| `market.agents` registered, `KINDS` exactly 8 | `test_kinds_registers_market_agents_as_the_eighth_kind`, direct `len(KINDS) == 8` |
| request+result round-trip through JSON (incl. `run_json`, text not dict), `StrategyConfig` crosses as data | `test_request_with_market_agents_strategy_config_round_trips_through_json`, `test_result_round_trips_through_json_for_market_agents`, `test_market_agents_strategy_config_round_trips_through_run_json_as_data_not_a_callable` — all green |
| unknown strategy kind -> BAD_OPTIONS, never INTERNAL | `test_market_agents_unknown_strategy_kind_is_bad_options` |
| strategy naming a nonexistent generator -> VALIDATION, never INTERNAL | `test_market_agents_strategy_naming_a_nonexistent_generator_is_a_validation_failure`; sabotage-proven, see below |
| non-positive `max_iterations` -> BAD_OPTIONS | `test_market_agents_non_positive_bounds_are_bad_options[max-iterations-*]` |
| non-positive `offer_tol` -> BAD_OPTIONS | `test_market_agents_non_positive_bounds_are_bad_options[offer-tol-*]` |
| success path returns `ok` with a typed `MarketAgentsResult`, not `INTERNAL` | `test_run_market_agents_on_smooth_pivotal_is_ok_with_typed_result_and_provenance`; sharp sabotage below |
| runner never raises | verified directly (see corrected mechanism above) |
| `run.py:198` union guard still catches a genuinely unregistered model, post-widening | `test_run_py_198_union_guard_still_fires_for_a_result_model_never_added_to_the_union` |

```
$ pytest tests/unit/test_jobs.py -q
........................................................................ [ 64%]
........................................                                 [100%]
112 passed in 39.46s
```

## Sabotage sweeps

Both done on scratch-directory overlays, never the shared worktree (per constraints): copied
`src/`, `tests/`, `fixtures/` to a temp directory under the scratchpad, ran via
`PYTHONPATH=<scratch>/src <venv>/Scripts/python.exe -m pytest`, confirmed via a direct `__file__`
print that imports resolved to the scratch copy, not `C:\Claude Projects\mambo-power-m7`. Both
reverted by deleting the scratch copy; the shared worktree was never modified by either.

### 1. The `ValueError` -> `VALIDATION` translation (registry.py)

Baseline (unsabotaged scratch copy):
```
$ PYTHONPATH=<scratch>/src python -m pytest tests/unit/test_jobs.py -q -k "nonexistent_generator or unknown_strategy_kind"
..
2 passed, 109 deselected in 9.28s
```

Sabotage: removed the `except ValueError as exc: raise NetworkValidationError(...)` block from
`_run_market_agents`, leaving `solve_agents`'s `ValueError` to fall into `jobs.run()`'s
catch-all.
```
$ PYTHONPATH=<scratch>/src python -m pytest tests/unit/test_jobs.py -q -k "nonexistent_generator or unknown_strategy_kind or ac6_four"
.F.F..
FAILED test_market_agents_strategy_naming_a_nonexistent_generator_is_a_validation_failure
  - AssertionError: assert 'INTERNAL' == 'VALIDATION'
FAILED test_ac6_four_caller_mistakes_never_report_internal[nonexistent-generator]
  - AssertionError: assert 'INTERNAL' in ('BAD_OPTIONS', 'VALIDATION')
2 failed, 4 passed, 105 deselected in 17.14s
```
The residual that moves is exactly the one this guard exists for: `code` goes from `VALIDATION`
to `INTERNAL`, reproducing the precise M6 defect class, on precisely the row that exercises this
guard. The other three rows of the same parametrized test (`unknown-strategy-kind`, both
non-positive-bound cases) stay green under the identical sabotage, since those are caught earlier
at `MarketAgentsOptions` validation — untouched by this change — confirming the test
discriminates the actual mechanism rather than passing coincidentally.

### 2. The `ResultModel` union widening (models.py) — the sharp sabotage team-lead asked for

Baseline (unsabotaged scratch copy, `jobs/models.py` with the widened union):
```
$ PYTHONPATH=<scratch>/src python -m pytest tests/unit/test_jobs.py -q -k "market_agents_on_smooth_pivotal or market_agents_with_no_options"
..
2 passed, 109 deselected in 7.64s
```

Sabotage: reverted `jobs/models.py`'s `ResultModel` union widening *alone* (removed
`MarketAgentsResult` from the import and the union, nothing else touched — a tree that is
otherwise entirely correct).
```
$ PYTHONPATH=<scratch>/src python -c "... run(SolveRequest(kind='market.agents', ... a correct, valid price-taker request ...)) ..."
status: failed
error: code='INTERNAL' message='result model MarketAgentsResult of kind "market.agents" is not
in SolveResult.result' issues=None details=None

$ PYTHONPATH=<scratch>/src python -m pytest tests/unit/test_jobs.py -q
FAILED test_run_is_pure_across_all_eight_kinds[market.agents]
FAILED test_run_market_agents_on_smooth_pivotal_is_ok_with_typed_result_and_provenance
FAILED test_run_market_agents_with_no_options_is_ok_no_agents_case14
FAILED test_run_is_pure_for_market_agents_with_a_markup_strategy
FAILED test_result_round_trips_through_json_for_market_agents
FAILED test_market_agents_strategy_config_round_trips_through_run_json_as_data_not_a_callable
6 failed, 105 passed in 14.93s
```
The residual is exactly the quantity AC-6 names: a **correct, valid** `market.agents` request —
right strategy kind, existing generator, positive bounds — degrades from `status="ok"` to
`code="INTERNAL"` on an otherwise-correct tree. This is the defect class team-lead identified as
sharper than neutering the registration (which would reden everything for the obvious reason and
prove less): it isolates the union-widening specifically, on a tree where the registration,
runner, and caller-mistake translations are all still correct. The other 105 tests — every
caller-mistake mapping, the KINDS-contract tests, and the request-side JSON round trip (which
does not need a runner) — stay green under this exact sabotage, confirming those clauses do not
secretly depend on the union.

## Manual proofs of the four AC-6 mappings (pasted output, clean tree)

```
$ python -c "MarketAgentsOptions(strategies={'strategic': {'kind': 'bogus'}})"
ValidationError (discriminator: no matching tag)
$ python -c "MarketAgentsOptions(max_iterations=0)"
ValidationError (greater_than)
$ python -c "MarketAgentsOptions(offer_tol=0.0)"
ValidationError (greater_than)

$ python -c "run(SolveRequest(kind='market.agents', network=smooth_pivotal_network(), options={'strategies': {'ghost': {'kind': 'price_taker'}}}))"
failed code='VALIDATION' message='Network validation failed with 1 issue:
  - DANGLING_REF at options.strategies: a strategy names generator "ghost", which is not in the network'
issues=[ValidationIssue(code='DANGLING_REF', path='options.strategies', message='a strategy names generator "ghost", which is not in the network')]

$ python -c "run(SolveRequest(kind='market.agents', network=..., options={'strategies': {'strategic': {'kind': 'bogus'}}}))"
failed code='BAD_OPTIONS' message="... Input tag 'bogus' found using 'kind' does not match any of the expected tags: 'price_taker', 'markup' ..."
$ python -c "run(SolveRequest(kind='market.agents', network=..., options={'max_iterations': 0}))"
failed code='BAD_OPTIONS' message="... Input should be greater than 0 ..."
$ python -c "run(SolveRequest(kind='market.agents', network=..., options={'offer_tol': -1.0}))"
failed code='BAD_OPTIONS' message="... Input should be greater than 0 ..."
```

## Deliberately left red, not mine

- `tests/unit/test_docs_registry_listing.py` — 3 of 4 tests red as briefed and expected:
  `test_the_manual_prints_the_real_sorted_kind_list`,
  `test_the_manual_capability_table_lists_every_registered_kind`,
  `test_the_manual_unknown_kind_message_lists_every_registered_kind`. Verified directly:
  ```
  $ pytest tests/unit/test_docs_registry_listing.py -q
  3 failed, 1 passed in 18.75s
  ```
  `docs/**` is S8's, briefed for a phase-2 pass blocked on this slice's registration landing.
  Not touched.
- `tests/unit/test_api_docs_coverage.py` — briefed as "may also be red"; **verified it is
  actually green** (contrary to that expectation):
  ```
  $ pytest tests/unit/test_api_docs_coverage.py -q
  2 passed in 5.94s
  ```
  This check walks `:::` directive coverage at the *module/symbol* level (is every public
  class/function defined in a submodule reachable from some documented page), not the registry's
  kind count or `results/__init__.py`'s re-export list. `mambo_power.results.agents` and
  `mambo_power.market.agents` already carry their own directives from an earlier docs phase
  (S2/S3/S4's work), so nothing this slice does moves this particular check. Reporting the
  actual result rather than the predicted one.

## Collateral observation, not mine — corrected

Full `tests/unit` run before the blocker resolved (888 tests, timestamp ~23:1x, on a tree
team-lead had separately confirmed clean of the unrelated `opf/__init__.py` sabotage at 23:20):
11 failed. 3x docs (above), 6x mine (all resolved once `jobs/models.py` landed — now green, see
AC-6 table). The remaining 2 were `test_market_agents.py::test_a_settled_climb_converges_at_
every_step_not_only_representable_ones[0.1]`/`[0.7]` — not mine (I did not touch
`market/agents.py`, `market/strategy.py`, or `test_market_agents.py`). **I originally diagnosed
this as a defect in S4's `_settled()` ULP-tolerance guard; that diagnosis was wrong, and
team-lead's correction (23:22, `pytest ...test_a_settled_climb... → 9 passed` on the same tree)
is the accurate account: I had read S4's files mid-edit, between the parametrised test being
saved and the `_settled` fix that makes it pass being saved.** Reading an uncommitted file in a
shared worktree is reading a moving target — a red there is a timestamp, not evidence about the
owner's code, and I should have reported the observation without a diagnosis attached.
Flagging-rather-than-fixing was still the right call (`market/agents.py` is not mine); the error
was in the conclusion I drew from an unattributable red, not in declining to fix it. S4's
`67d189e`, "the convergence test itself was decided by float noise (F6)", was the commit that
made this observation moot; my own full-suite re-run after it landed (see "Verification run at
head" below) confirms both rows pass on the committed tree.

## Verification run at head (final, post-blocker-resolution)

```
$ ruff check src/mambo_power/jobs/registry.py src/mambo_power/jobs/models.py tests/unit/test_jobs.py
All checks passed!
$ ruff format --check src/mambo_power/jobs/registry.py src/mambo_power/jobs/models.py tests/unit/test_jobs.py
3 files already formatted
$ pytest tests/unit/test_jobs.py -q
112 passed in 39.46s
```

`mypy` on my three files: 8 pre-existing errors, none introduced by this slice (verified by
diffing against the same command run before this slice's tests existed) — 6 in pre-existing
`test_jobs.py` code (runner-signature and `Network | None` narrowing issues, lines
150/387/489/610/652/1097) and 2 `[misc]` "dict comprehension value type" notes on my
`_price_taker_options`/`_markup_options` helpers' `strategies={gen_id: {"kind": ...} for ...}`
literals — the same class of mypy noise `tests/unit/test_market_agents.py`'s own `_markup_
options` helper already carries unannotated (16 pre-existing errors in that file, same
`StrategyConfig`-dict-literal class); matched that file's existing convention rather than
introducing a new one. The `comparison-overlap` error the blocked state produced on `type(again.
result) is MarketAgentsResult` is gone now that `ResultModel` includes `MarketAgentsResult`.

Full `pytest tests/unit` re-run after `jobs/models.py` landed, on the current head (`67d189e`):
```
$ pytest tests/unit -q
...
FAILED tests/unit/test_docs_registry_listing.py::test_the_manual_prints_the_real_sorted_kind_list
FAILED tests/unit/test_docs_registry_listing.py::test_the_manual_capability_table_lists_every_registered_kind
FAILED tests/unit/test_docs_registry_listing.py::test_the_manual_unknown_kind_message_lists_every_registered_kind
3 failed, 887 passed in 335.05s
```
Exactly the 3 expected docs reds (S8's) remain. Every `test_jobs.py` test is green (all 6
previously-blocked tests now pass), and both `test_market_agents.py` reds from the earlier,
pre-`jobs/models.py` full-suite run are also gone — confirming S4's `67d189e` addressed that
finding for real, on a suite I actually re-ran rather than assumed.

## Public symbols new to this slice (for S8)

- `mambo_power.jobs.registry.KINDS["market.agents"]` — `KindSpec(options_model=
  MarketAgentsOptions, result_model=MarketAgentsResult, runner=_run_market_agents)`.
- `mambo_power.jobs.models.ResultModel` now includes `MarketAgentsResult`.
- No new public names of my own beyond the registration — `MarketAgentsResult`,
  `AgentOfferResult`, `TerminationReason`, `MarketAgentsOptions` etc. are S2/S3/S4's, already
  documented (or pending S8 phase 2 for the `jobs.md` registered-kinds sites).

## Not done / left for others

- `docs/manual/jobs.md`'s three registered-kind sites — S8 phase 2, unblocked as of this
  slice's commit landing.

## Commit

Explicit paths only: `src/mambo_power/jobs/registry.py`, `src/mambo_power/jobs/models.py`,
`tests/unit/test_jobs.py`.
