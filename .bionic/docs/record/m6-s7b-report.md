# M6 S7b report — jobs kind `market.zonal`

Role: implementor. Wave M6 (zonal-redispatch), Step 4, slice S7b (the jobs half of W6/AC-7).
Worktree `C:\Claude Projects\mambo-power-m6`, branch `wave/06-zonal-redispatch`. Started from
head `f1782e8` (S5's `market.solve_zonal`/`MarketZonalResult`/`MarketZonalOptions` landed, 951
passed / 4 skipped). Landed as commit `4432163`.

## Scope and ownership

Owned: `src/mambo_power/jobs/**`, `tests/unit/test_jobs.py`, `docs/manual/jobs.md`. A sibling
(`m6-s8-docs`) owns `docs/**` except `docs/manual/jobs.md`, plus `examples/**`, live in the same
worktree concurrently. Explicit-path commits only — verified below.

## What changed

### `src/mambo_power/jobs/registry.py`

- Imported `MarketZonalOptions`, `solve_zonal` from `mambo_power.market.zonal` and
  `MarketZonalResult` from `mambo_power.results`.
- New `_run_market_zonal(scenario, options) -> BaseModel`: calls `solve_zonal(scenario,
  options=options)`, then translates a non-`"Optimal"` status through the same
  `_translate_non_optimal_status` helper `opf.dc`, `market.nodal` and `market.multiperiod`
  already share (now four callers, not three — docstrings on `InfeasibleLpError`,
  `UnboundedLpError` and `_translate_non_optimal_status` updated to say so).
- `register(KindSpec(kind="market.zonal", options_model=MarketZonalOptions,
  result_model=MarketZonalResult, runner=_run_market_zonal))` — the 7th and last registration.
  `KINDS` now has exactly 7 entries; `kinds()` returns them sorted.

### `src/mambo_power/jobs/models.py`

- Added `MarketZonalResult` to the `mambo_power.results` import and to the `ResultModel` closed
  union (`SolveResult.result`'s annotation) — the same mechanical widening every prior kind's
  wave has made to this file.

### `tests/unit/test_jobs.py` (57 → 79 tests)

New fixture/helper: `case30_zoned` (module-scoped, `rated_network(promote_areas_to_zones(...))`
on case30) and `_case30_zonal_options(net)` (builds `MarketZonalOptions` from
`tests/_zones.py`'s `corridors(net)` — the "corridors from `tests/_zones.py`" clause of AC-7).

Added tests, grouped under a new `# wave M6 S7b / AC-7` banner (mirroring the M5 banner
convention already in this file):

- **KINDS contract**: `test_kinds_registers_market_zonal_as_the_seventh_kind`,
  `test_kinds_is_sorted_with_market_zonal_in_place`.
- **Happy path**: `test_run_market_zonal_on_case30_is_ok_with_typed_result_and_provenance`
  (real corridors, 3 zone rows, branch rows present — the M5 A23 carry-over, provenance ==
  result.provenance, options land in provenance) and
  `test_run_market_zonal_with_no_options_is_ok_single_zone_case14` (the T=1/no-corridor
  degenerate case every other kind's smoke test uses).
- **Purity**: folded into the widened `test_run_is_pure_across_all_seven_kinds` parametrize,
  plus a dedicated `test_run_is_pure_for_market_zonal_with_real_corridors` on the
  non-degenerate case30 fixture.
- **JSON round trip, options preserved**:
  `test_request_with_market_zonal_options_round_trips_through_json` (AC-7's explicit
  "including the options" clause — asserts `corridors` survives, length 3),
  `test_result_round_trips_through_json_for_market_zonal`,
  `test_market_zonal_with_corridors_round_trips_through_run_json` (the same clause through
  `run_json`'s text-in/text-out path, options.corridors present in the provenance payload too).
- **Never raises, adversarial inputs**:
  - `test_market_zonal_with_empty_corridors_islands_the_zones_and_is_not_an_error` — S3's A22(i)
    finding, exercised through the job surface: `options={}` → `corridors=[]` clears
    `status="ok"`, `Optimal`, 3 distinct zone prices (every zone on promoted case30 carries
    generation, measured directly: 2/2/2 in-service generators per zone).
  - `test_market_zonal_corridor_naming_an_unknown_zone_is_a_failed_result_not_a_crash` — a
    corridor naming a zone no bus is assigned to is `solve_zonal`'s own documented `ValueError`
    (from `opf.zonal._normalise_corridors`); `run`'s generic exception boundary turns it into
    `INTERNAL`, not a crash.
  - `test_market_zonal_through_resolved_scenario_invalid_network_is_a_failed_validation_result`
    — the mutated-invalid-network path (M5 A22) through `market.zonal`: `VALIDATION`, not a
    raised exception.
  - `test_infeasible_market_zonal_is_infeasible_lp_not_internal` — the standard
    `_infeasible_net(case14)` fixture routed through `market.zonal`: `INFEASIBLE_LP`, message
    names the zonal clearing stage.
  - `test_market_zonal_shares_the_status_translation_function` — spies on
    `jobs_registry._translate_non_optimal_status`, confirms `market.zonal`'s runner calls the
    identical function object the other three market/LP kinds already share.
- **Backward compatibility**: `test_prior_six_kinds_still_accept_their_existing_network_form_
  unchanged` (parametrized over all six pre-existing kinds) and
  `test_prior_kinds_still_accept_their_existing_scenario_form_unchanged`.

Two pre-existing lines were forced to change (both explained inline at their site, the same
treatment wave M5 gave this file when it widened from 5 kinds to 6):

- `KNOWN_KINDS` widened to include `"market.zonal"`; `ALL_SIX_KINDS` renamed to
  `ALL_SEVEN_KINDS` and widened (its one usage, `test_run_is_pure_across_all_six_kinds`, renamed
  to `test_run_is_pure_across_all_seven_kinds`); `test_kinds_registers_market_multiperiod_as_
  the_sixth_kind`'s `assert len(KINDS) == 6` bumped to `7` (a 7th kind is now registered too).
- `test_unknown_kind_is_a_failed_result` used `kind="market.zonal"` as its canonical
  still-unregistered example through M5 (a comment there explained it was moved off
  `"market.nodal"` when M4 registered *that* kind). Now that `market.zonal` registers, that
  example needed to move again — to `"market.agents"`, the placeholder
  `docs/manual/jobs.md`'s own `SolveRequest.kind` row already names as "a later wave".

### `docs/manual/jobs.md`

`tests/unit/test_docs_registry_listing.py` pins three exact strings against the live registry.
**RED before** (captured pre-edit):

```
FAILED tests/unit/test_docs_registry_listing.py::test_the_manual_prints_the_real_sorted_kind_list
FAILED tests/unit/test_docs_registry_listing.py::test_the_manual_capability_table_lists_every_registered_kind
FAILED tests/unit/test_docs_registry_listing.py::test_the_manual_unknown_kind_message_lists_every_registered_kind
3 failed, 1 passed in 0.84s
```

**GREEN after**:

```
....
4 passed in 0.67s
```

Edits made to the page (updating the page, never the test, per the assignment's own framing):

- `kinds()` print block and the capability-table block both now include the `market.zonal
  MarketZonalOptions MarketZonalResult` line, verified against the live registry's actual
  printed output.
- The `UNKNOWN_KIND` failure demo's registered-kinds list updated to the 7-kind sorted list.
- `SolveRequest.kind` field row: `market.zonal` moved from "later waves" to "M6"; `market.agents`
  kept as "a later wave".
- `SolveResult.result` field row: added `MarketZonalResult` to the listed result models.
- `INFEASIBLE_LP` / `UNBOUNDED_LP` rows: "an `opf.dc`, `market.nodal` or `market.multiperiod`"
  → "...or `market.zonal`"; "the same three kinds" → "the same four kinds".
- `KINDS` section: "six as of M5" → "seven as of M6".
- **Collision with the pre-existing "Failures are data" demo**: it used
  `kind="market.zonal", network=net)  # not registered yet` as its `UNKNOWN_KIND` example — now
  false. Moved to `kind="market.agents"`, with the printed `UNKNOWN_KIND` message text updated
  to the new 7-kind registered list and verified by actually running the snippet.
- New short paragraph documenting `MarketZonalOptions.corridors` — that it is market design
  data (not solver tuning), that the empty-list default is not "no limit" but "every zone must
  supply itself", that a corridor naming an unknown zone is validated before any solve, and that
  the chain's `INFEASIBLE_LP`/`UNBOUNDED_LP` translation follows the other market kinds'
  convention — placed alongside the existing `market.multiperiod` usage note.
- "Relationship to the module-level functions" section: added `market.solve_zonal` to the list
  of notebook-friendly entry points `jobs.run` calls.

## Verification

- `ruff check` / `ruff format --check` / `mypy` clean on all four touched files, and clean
  repo-wide except one file the sibling slice is mid-edit on
  (`docs/manual/zonal.md`, untracked, not touched here).
- `tests/unit/test_jobs.py` alone: 79 passed. `tests/unit/test_jobs.py` +
  `tests/unit/test_docs_registry_listing.py`: 83 passed.
- Full suite: **972 passed, 4 skipped, 2 failed**. Both failures are outside this slice's
  ownership and were confirmed (not merely assumed) to be caused by concurrent/pre-existing
  state on the sibling's side, not by this commit:
  - `test_example_runs_to_completion[04_jobs_api]` — `examples/04_jobs_api.py` (owned by
    `m6-s8-docs`) has its own `UNKNOWN_KIND` demo using `kind="market.zonal"  # not registered
    yet`, the identical collision fixed in this slice's own two files. Confirmed by tracing the
    assertion failure (`assert unknown.error is not None`) to that exact line; reported to
    `m6-s8-docs` via SendMessage with the precise fix (swap to `"market.agents"`, matching the
    fix applied here).
  - `test_every_example_is_embedded_in_the_docs` — `examples/11_zonal_redispatch.py` exists
    (untracked, sibling WIP) but isn't yet embedded in `docs/examples/index.md`; unrelated to
    this slice, also flagged to `m6-s8-docs` in the same message for visibility.
  - `tests/parity/test_market_zonal_vs_pypsa.py`'s 4 skips are pre-existing (unrelated
    parameter skips, present in the S5 baseline too).

## Sabotage sweep (in-place on this worktree, reverted before committing)

1. **Neutered the registration** (removed the `register(KindSpec(kind="market.zonal", ...))`
   call, imports/runner left intact): 18 tests went red — all 12 of this slice's
   `market.zonal`-specific tests in `test_jobs.py` that depend on the kind actually being
   registered, plus `test_kinds_registers_market_zonal_as_the_seventh_kind` and
   `test_kinds_is_sorted_with_market_zonal_in_place`, plus the 2 of 3
   `test_docs_registry_listing.py` pins that name `market.zonal` by string (the capability-table
   pin is naturally silent here since it only checks *registered* kinds are documented, not the
   reverse). Reverted by rewriting the file from the known-good content (see note below);
   re-verified 83/83 on `test_jobs.py` + `test_docs_registry_listing.py`.
2. **Pointed the runner at `solve_nodal` instead of `solve_zonal`**: 9 tests went red, including
   `test_run_market_zonal_on_case30_is_ok_with_typed_result_and_provenance` (the typed-result
   test named in the dispatch's own sabotage prediction) — because `solve_nodal`'s return type
   (`MarketNodalResult`) doesn't match the registered `KindSpec.result_model`
   (`MarketZonalResult`), so `run()`'s own `type(raw) is not spec.result_model` check turns
   every call into `INTERNAL`. Reverted with a single targeted `Edit`; full suite re-confirmed
   972/4/2 (same two pre-existing, out-of-scope failures) after revert.

**Process note**: sabotage 1's revert used `git checkout -- src/mambo_power/jobs/registry.py`,
which — since the file was still uncommitted at that point — discarded *all* of this slice's
edits to that file, not just the sabotage line. Caught immediately (grep for `market.zonal`
came back empty), and the file was rewritten in full from the content still visible in this
session's own transcript (the tool's own pre-edit diff notice had captured it). Re-verified
byte-identical via `git diff --stat` (73 insertions/deletions, matching the pre-sabotage diff
exactly) and a full lint/type/test pass. Sabotage 2's revert used a single `Edit` call instead,
specifically to avoid repeating this.

## Commit

`4432163` on `wave/06-zonal-redispatch`, exactly `src/mambo_power/jobs/models.py`,
`src/mambo_power/jobs/registry.py`, `tests/unit/test_jobs.py`, `docs/manual/jobs.md`.

## Open item for the orchestrator

`examples/04_jobs_api.py` needs a one-line fix (`kind="market.zonal"` → `kind="market.agents"`
at line 51, plus its printed message text) before the wave's full suite is green. That file is
owned by `m6-s8-docs`; already messaged directly with the exact fix. Not fixed here to respect
the ownership boundary (explicit-path commits only).
