# M7 / S2 report — the `Strategy` seam

Wave M7 (`agents`), slice S2, branch `wave/07-agents`, worktree `C:\Claude Projects\mambo-power-m7`.
Commits: **`df3c849`** (initial) — `feat(m7/s2): the Strategy seam — Observation, PriceTaker,
MarkupStrategy, StrategyConfig`; **`aade93b`** (amendment, review feedback) —
`fix(m7/s2): stale-history guard + explicit PWL coverage on the Strategy seam`;
**`20ba1e7`** (defect fix, found by S4 downstream) —
`fix(m7/s2): MarkupStrategy reverses on a real profit decrease, not solver-noise ties`. See
"Amendment" and "Defect fix" below for what changed and why.

Owned files (only files touched): `src/mambo_power/market/strategy.py` (new),
`tests/unit/test_market_strategy.py` (new, 30 tests after the defect fix).

## What was built

Requirement W2 in full: `Observation` (own-node view, two-round history with explicit-`None`
first/second-round shapes), `Strategy` (a `typing.Protocol`), `PriceTakerStrategy`,
`MarkupStrategy` (the two-point hill climb per A4), `PriceTakerConfig`/`MarkupConfig`/
`StrategyConfig` (discriminated union mirroring `GeneratorCost`), and `build_strategy`.

**Design decisions made in-slice, not in the spec's literal text:**

- `Observation` is one frozen pydantic model with `previous_round: RoundRecord | None` and
  `two_rounds_ago: RoundRecord | None` (rather than a tagged union of "round-0 shape" /
  "round-N shape"), each documented to mean "this round hasn't happened" — never a
  zero-valued `RoundRecord`. A `model_validator` rejects the one invalid combination (
  `two_rounds_ago` set without `previous_round`) as a genuine history gap.
- `MarkupStrategy` is scoped to a **linear** `PolynomialCost` (`coefficients = [c1, c0]`) —
  the only shape A4's own measurement and this wave's fixtures use. A piecewise cost or a
  polynomial of any other degree raises `NotImplementedError` naming the offending shape,
  rather than picking an undefined scalar reading. `PriceTakerStrategy` has no such scoping
  (it never reads inside the cost).
- Round 0 (`previous_round is None`) returns `observation.true_cost` unchanged — there is no
  `offer[t-1]` for the climb rule to start from. Round 1 (`two_rounds_ago is None`) is a pure
  upward probe: direction defaults to `+1`, no profit comparison is made. Both match the
  reference probe `.bionic/tmp/m7-a4-two-point-climb.py`'s `hill_climb`.

## Every claim, with its proving command and output

**Unit tests, both owned files, in isolation:**
```
$ uv run --no-sync pytest tests/unit/test_market_strategy.py -q
........................                                                 [100%]
24 passed in 10.17s
```

**ruff check, both owned files:**
```
$ uv run --no-sync ruff check src/mambo_power/market/strategy.py tests/unit/test_market_strategy.py
All checks passed!
```

**ruff format --check, both owned files:**
```
$ uv run --no-sync ruff format --check src/mambo_power/market/strategy.py tests/unit/test_market_strategy.py
2 files already formatted
```

**mypy --strict, both owned files:**
```
$ uv run --no-sync mypy src/mambo_power/market/strategy.py tests/unit/test_market_strategy.py
Success: no issues found in 2 source files
```

**Full-repo gate sweep at head** (head includes S1's in-flight W1 changes to `dc_opf.py`,
`multiperiod.py`, `zonal.py`, `nodal.py`, `results/market.py` — shared worktree, uncommitted at
the time of this run):
```
$ uv run --no-sync ruff check .          # (1 error, in test_market_nodal.py:186 -- S1's file, not mine)
$ uv run --no-sync ruff format --check . # 171 files already formatted
$ uv run --no-sync mypy .                # Success: no issues found in 2 source files (scoped to changed files)
$ uv run --no-sync pytest -q
2 failed, 1033 passed, 4 skipped, 10 warnings in 584.52s
FAILED tests/unit/test_api_docs_coverage.py::test_every_public_symbol_is_reachable_from_an_api_page
FAILED tests/unit/test_docstrings.py::test_every_public_symbol_has_a_docstring
```

Both failures were caused by this slice's new public module. **The docstring one was fixed** —
`PriceTakerStrategy.offer` and `MarkupStrategy.offer` had no docstring of their own (only the
`Strategy` Protocol's abstract method did); added one line each. Re-run:
```
$ uv run --no-sync pytest tests/unit/test_docstrings.py -q
..                                                                       [100%]
2 passed in 6.67s
```

**The `test_api_docs_coverage` failure was left red, deliberately, and is disclosed here rather
than worked around.** It fires because `market.strategy`'s eight public symbols
(`MarkupConfig`, `MarkupStrategy`, `Observation`, `PriceTakerConfig`, `PriceTakerStrategy`,
`RoundRecord`, `Strategy`, `build_strategy`) are not yet rendered on any `docs/api/` page —
that is W8/AC-7, a separate requirement with its own slice, and fixing it means editing docs
pages that are not in my owned-files list (`.bionic/docs/**` and `docs/**` are out of scope
for S2 per the assignment). Reported rather than fixed:
```
$ uv run --no-sync pytest tests/unit/test_api_docs_coverage.py::test_every_public_symbol_is_reachable_from_an_api_page -q
FAILED — mambo_power.market.strategy: MarkupConfig, MarkupStrategy, Observation, PriceTakerConfig,
PriceTakerStrategy, RoundRecord, Strategy, build_strategy
```
This is expected to close when W8's docs slice adds `market.strategy`'s API page.

The one `ruff check` line-length error (`tests/unit/test_market_nodal.py:186`) belongs to S1's
in-flight file, confirmed by `git status` showing it as `M` under S1's ownership, not mine —
not fixed here, per the "don't touch files you don't own" rule.

## Sabotage sweep — 6/6, each confirmed red then reverted

Verified `src/mambo_power/market/strategy.py` is byte-identical to its pre-sabotage state after
each round (`diff` clean). For each: the edit, the command, the test that went red, and the
residual that moved.

1. **`PriceTakerStrategy.offer` reads history instead of ignoring it** (`return
   observation.previous_round.offer if ... else observation.true_cost`) →
   `test_price_taker_returns_true_cost_exactly_with_history_present` red — residual: returned
   coefficient `24.0` vs expected true cost `20.0`.
2. **`MarkupStrategy`'s floor clamp removed** (`new_level = offer_prev + direction * self.step`,
   no `max(true_level, ...)`) → `test_markup_offer_never_goes_below_true_cost` red — residual:
   `19.5` (below true cost) vs expected floored `20.0`.
3. **`MarkupStrategy`'s profit-based reversal disabled** (profit computed but discarded) →
   `test_markup_reverses_direction_when_last_move_lowered_profit` red — residual: `21.5`
   (kept climbing) vs expected reversed `20.5`.
4. **`Observation`'s history-gap `model_validator` disabled** (body replaced with `return self`)
   → `test_observation_rejects_a_history_gap` red — residual: no `ValidationError` raised where
   one is required.
5. **`build_strategy`'s branches swapped** (`price_taker` resolves to `MarkupStrategy`) →
   `test_strategy_config_round_trips_price_taker` and
   `test_build_strategy_price_taker_ignores_extra_state` both red — residual: resolved instance
   type (`MarkupStrategy` vs expected `PriceTakerStrategy`).
6. **Round-1 default direction sign flipped** (`direction = -1.0` when `two_ago is None`) →
   `test_markup_round_one_probes_upward_by_one_step` red — residual: `20.0` (floored, pushed
   down) vs expected probe-up `20.5`.

Each command was `uv run --no-sync pytest tests/unit/test_market_strategy.py -q`, run once per
sabotage and once after each revert (all reverts confirmed green, final state confirmed
byte-identical to pre-sabotage via `diff`).

## Coverage against the assignment's required list

- PriceTakerStrategy returns coefficients equal to true cost, exactly — `test_price_taker_returns_true_cost_exactly`, `..._with_history_present` (`==`, not `pytest.approx`).
- MarkupStrategy reverses on worsened profit, continues on improved profit — `test_markup_reverses_direction_when_last_move_lowered_profit`, `test_markup_continues_direction_when_last_move_raised_profit`.
- Offer never below true cost — `test_markup_offer_never_goes_below_true_cost`.
- Pure function of observation (same input twice, same output; no attribute drift) — `test_price_taker_is_a_pure_function_of_its_observation`, `test_markup_is_a_pure_function_of_its_observation`.
- StrategyConfig round-trips through `model_dump_json`/`model_validate_json` and resolves to the right class — `test_strategy_config_round_trips_price_taker`, `test_strategy_config_round_trips_markup` (via a minimal test-local wrapper model, since the union itself isn't a `BaseModel`).
- First-round/second-round `Observation` shapes constructible, no silent zero — `test_observation_round_zero_has_no_history_at_all`, `test_observation_round_one_has_exactly_one_prior_round`, `test_observation_round_two_has_both_prior_rounds`, `test_observation_rejects_a_history_gap`, `test_markup_round_zero_offers_true_cost`, `test_markup_round_one_probes_upward_by_one_step`.

Also covered, not explicitly requested but load-bearing: `MarkupStrategy`/`MarkupConfig` reject
non-positive `step`; `MarkupStrategy` raises on a piecewise or non-linear true cost;
`Observation`/`RoundRecord` reject unknown fields (`extra="forbid"`); `StrategyConfig` rejects an
unknown `kind`; `PriceTakerStrategy` handles non-linear and piecewise costs (contrast with
`MarkupStrategy`'s scoping).

## What could not be proven / left for other slices

- **`test_api_docs_coverage` is red for `market.strategy`'s eight public symbols** — W8/AC-7's
  scope, not S2's; see above. This is the one non-green row in the full-suite sweep at this
  slice's head.
- **This slice is not independently usable end-to-end** — nothing calls `market.strategy` yet;
  S4's loop (`market/agents.py`) is the caller and does not exist. AC-3/AC-4/AC-5 are not
  dischargeable from this slice alone, as scoped.
- I did not re-run the full-repo suite after S1's in-flight files finish changing (they were
  mid-edit throughout this slice, in the same worktree). The full-sweep numbers above
  (`1033 passed`, 1 unrelated ruff line-length issue) are a snapshot at the time I ran it, not
  a claim about S1's own final state.

## Amendment (commit `aade93b`) — review feedback from team-lead

Three messages, addressed in full:

1. **"PWL offers: markup vs price-taker."** `PriceTakerStrategy` was already correct at
   `df3c849` (returns `observation.true_cost` verbatim, no special-casing by cost shape) but
   under-asserted — the only piecewise test exercised `PriceTakerStrategy` alongside a
   non-linear-polynomial one, not called out as AC-3(a)'s load-bearing path. Added
   `test_price_taker_returns_a_piecewise_true_cost_exactly`, whose docstring now names it as the
   only path a PWL offer reaches the array builder this wave and the path W1(c)'s overlap guard
   protects. `MarkupStrategy`'s linear-only scoping and loud `NotImplementedError` on a piecewise
   true cost were already in place at `df3c849`; the amendment only sharpens the disclosure
   (module docstring, class docstring, this report) and adds a docstring line to
   `test_markup_strategy_rejects_piecewise_true_cost` stating the "fail loudly, not
   approximate" rationale explicitly.

2. **"Make sure the validator rejects a *gap* (round 5 paired with round 2), not merely a
   missing entry."** This was a real hole in `df3c849`: `RoundRecord` carried no round number of
   its own, so `Observation` could not tell a genuinely-adjacent record from a stale one handed
   into the wrong slot. Fixed by giving `RoundRecord` a `round_index: int` field and rewriting
   the validator (renamed `_history_is_contiguous`) to check, in addition to the existing
   missing-entry case, that `previous_round.round_index == round_index - 1` and
   `two_rounds_ago.round_index == round_index - 2` whenever each is present. New tests
   `test_observation_rejects_a_stale_previous_round` and
   `test_observation_rejects_a_stale_two_rounds_ago` (the literal round-5/round-2 case from the
   feedback). Sabotage-confirmed (see sabotage 7 below).

3. **"Purity test should assert the strategy object is unchanged across calls, not just that the
   return value repeats."** `df3c849`'s purity tests only compared two return values (equal, but
   a caching strategy could still pass that). Rewritten to snapshot `vars(strategy)` before the
   first call and assert it is unchanged after both calls, for both `PriceTakerStrategy` (empty
   `__dict__`) and `MarkupStrategy` (`step`).

4. **"docstring half is yours, API-page half is S8's."** Already handled exactly this way at
   `df3c849` — see "Every claim..." above. No further action; restated here for completeness
   since this message arrived after the report was first written.

Re-verified after the amendment, both owned files:
```
$ uv run --no-sync pytest tests/unit/test_market_strategy.py -q
............................                                             [100%]
28 passed in 2.27s

$ uv run --no-sync ruff check src/mambo_power/market/strategy.py tests/unit/test_market_strategy.py
All checks passed!

$ uv run --no-sync ruff format --check src/mambo_power/market/strategy.py tests/unit/test_market_strategy.py
2 files already formatted

$ uv run --no-sync mypy src/mambo_power/market/strategy.py tests/unit/test_market_strategy.py
Success: no issues found in 2 source files

$ uv run --no-sync pytest tests/unit/test_docstrings.py -q
..                                                                       [100%]
2 passed in 15.23s
```

**Sabotage 7 (new behaviour, the stale-record check):** disabled both adjacency `if` blocks in
`_history_is_contiguous` (kept only the pre-existing missing-entry check) →
`test_observation_rejects_a_stale_previous_round` and `test_observation_rejects_a_stale_two_rounds_ago`
both red — residual: no `ValidationError` raised where the adjacency check should have fired.
Reverted; `diff` against the pre-sabotage file confirmed byte-identical.

I did not re-run the full-repo suite after this amendment (S1/S3/S6 are still actively editing
shared files per the team-lead's worktree-discipline message; a full sweep now would mix their
in-flight state into this slice's signal for no benefit) — the two isolated-file gates above
plus `test_docstrings.py` are what I own and what changed.

## Defect fix (commit `20ba1e7`) — found downstream by S4, root cause was the brief not my care

**The defect.** `MarkupStrategy.offer` reversed direction on a strict `profit_prev < profit_2ago`
with no tie tolerance, against the brief in the team-lead's original message ("if `profit[t-1] <
profit[t-2]` the direction reverses"), which had dropped the `- 1e-9` epsilon the Step-2 reference
probe (`.bionic/tmp/m7-a4-two-point-climb.py:79`) used. I implemented exactly what was specified,
and 24/28 tests at the time were correct against that specification — but the specification itself
was wrong for a case none of those tests could reach without a market.

**Why it mattered (S4's finding, relayed by team-lead).** On the AC-5 duopoly both 300 MW agents
sit at capacity while demand sets price, so consecutive rounds are economically identical but the
LP balance dual differs by one ULP — ~1.6e-12 of profit once scaled by 300 MW. The strict
comparison flipped direction on that noise, the climb turned around at round 2, and the loop
reported `converged=True` at iteration 4 with offers frozen at true cost — the competitive outcome
presented as a settled strategic equilibrium.

**The fix.** Reverse only when `profit_prev < profit_2ago` **and** the two are not
`math.isclose(profit_prev, profit_2ago, rel_tol=1e-9, abs_tol=1e-9)` — relative tolerance, per
team-lead's direction, not the probe's absolute `1e-9`: profit is ~$6,000 on this wave's fixtures
and would be a different order of magnitude on a larger network, so an absolute epsilon that
breaks ties at one scale is a no-op at another. Added `_PROFIT_TIE_REL_TOL = 1e-9` as a named
module constant and documented the rationale in both the module docstring and
`MarkupStrategy`'s own. The documented contract ("reverses if the last move made things worse")
did not change — a ~1e-12 flip was never "worse" under any reasonable reading, so this corrects
the implementation to match the contract already written, not the contract itself.

**New tests, proving the fix and reproducing the defect:**

```
$ uv run --no-sync pytest tests/unit/test_market_strategy.py -q
..............................                                           [100%]
30 passed in 8.50s
```

- `test_markup_does_not_reverse_on_a_profit_tie_within_relative_tolerance` — reproduces the exact
  AC-5 failure shape at unit scale: offer[t-1] == offer[t-2] == 45.0 MW (zero movement, as at
  capacity), lmp differing by 1e-12 between rounds (profit tie at ~5e-14 relative). Asserts the
  climb continues to 45.5, not reversed to 44.5.
- `test_markup_reverses_on_a_real_profit_decrease_at_the_same_zero_movement_baseline` — same
  zero-movement baseline, a real $3.00 profit drop (5e-4 relative, far outside the tie band).
  Asserts it still reverses to 44.5.

**Sabotage 8:** reverted the guard to the pre-fix strict `profit_prev < profit_2ago` (no
`math.isclose`) →
```
$ uv run --no-sync pytest tests/unit/test_market_strategy.py -q -k "markup_does_not_reverse_on_a_profit_tie or markup_reverses_on_a_real_profit_decrease"
F.
FAILED ...test_markup_does_not_reverse_on_a_profit_tie_within_relative_tolerance
1 failed, 1 passed
```
residual: offer flips to `44.5` instead of continuing to `45.5` — this **is** the reported defect,
reproduced exactly at unit scale, with the real-decrease companion staying green throughout
(confirming the sabotage isolates the tie case specifically). Reverted; `diff` confirmed
byte-identical to the pre-sabotage file.

**Process note, corrected by team-lead after this sabotage.** This sabotage (and 1-7 earlier)
ran as an in-place edit-run-revert cycle directly in the shared worktree. That briefly broke a
concurrent measurement: S4 was measuring AC-5 against `MarkupStrategy` in this same directory,
took a run with the real fix present (AC-5(i) green), and 90 seconds later read `git diff`
showing the sabotaged file — it correctly declined to report a number it could not attribute to
either state. Team-lead's ruling (which S1 and S3 had independently already adopted): any further
sweep runs against a `git archive <sha>` overlay in a temp directory, driven via
`PYTHONPATH=<tmp>/src`, printing the loaded module's `__file__` to prove which tree is under
test — nothing in the shared worktree is written, so nothing needs reverting and no concurrent
run can be poisoned. Binding on any future sweep in this slice.

**Independent second witness (S4).** `tests/unit/test_market_agents.py::test_ac5i_the_duopoly_climbs_to_the_measured_point_and_reports_it_converged`
goes red under the identical sabotage (strict `<`, no tie tolerance), from a different module and
a different fixture path — S4's loop-level AC-5 test, not this slice's unit test. The unit test
above proves the rule; S4's proves the rule matters to the market. The two should be read
together.

**Full gate on both owned files after the fix**, all green:
```
$ uv run --no-sync ruff check src/mambo_power/market/strategy.py tests/unit/test_market_strategy.py
All checks passed!
$ uv run --no-sync ruff format --check src/mambo_power/market/strategy.py tests/unit/test_market_strategy.py
2 files already formatted
$ uv run --no-sync mypy src/mambo_power/market/strategy.py tests/unit/test_market_strategy.py
Success: no issues found in 2 source files
$ uv run --no-sync pytest tests/unit/test_docstrings.py -q
..                                                                       [100%]
2 passed in 15.58s
```

## Standing-rules compliance

- Sabotage sweep: 8/8 total (6 at `df3c849`, 1 more at `aade93b` for the new stale-record
  guard, 1 more at `20ba1e7` reproducing the tie-tolerance defect), see above in each commit's
  section. **Methodology correction, all 8 in retrospect:** these ran as in-place edit-run-revert
  in the shared worktree, which is safe for a file only this slice touches but briefly broke a
  concurrent S4 measurement reading `market/strategy.py` mid-sweep (see "Process note" above). Any
  further sweep in this slice runs against a `git archive` overlay in a temp directory via
  `PYTHONPATH`, per team-lead's ruling.
- Fixture factory: `_linear_cost` / `_record` / `_observation` in the test file, driven by
  every test that needed an `Observation`; only the shape/validation tests construct one
  directly (necessarily, since they test construction itself).
- Commits: `git add src/mambo_power/market/strategy.py tests/unit/test_market_strategy.py`,
  explicit paths only, all three times.
