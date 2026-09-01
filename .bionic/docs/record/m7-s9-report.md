# M7 S9 — three walk findings, fixed at the layer they live

Worktree `/c/Users/mambo/AppData/Local/Temp/claude/C--Claude-Projects-mambo-power/0d397067-49ef-4969-aefa-5709948393ef/scratchpad/bionic-unified`, branch `wave/07-agents`, base `9b30e01`.
Final head `3686f2e` (three fix commits plus one style reflow). Each fix: red test, change,
green, sabotage (change reverted with the test kept), restore.

Final gates at head: `uv run ruff check .` clean, `uv run ruff format --check .` 178 files
formatted, `uv run mypy` no issues in 53 files, `uv run --project "/c/Claude Projects/mambo-power" python examples/12_agent_market.py`
exit 0. `tests/unit/test_market_agents_economics.py`: 21 passed before S9, after fix 2, and after
fix 3 — pivotal, control and duopoly figures untouched. Full suite not run (orchestrator's sweep).

## Fix 1 — `market.solve_agents` did not exist — `1de01e0`

Files: `src/mambo_power/market/__init__.py` (import, `__all__`, docstring "Four entry points"),
`docs/manual/jobs.md` (one line: `market.agents.solve_agents` → `market.solve_agents`),
`tests/unit/test_market_agents.py` (`test_solve_agents_is_exported_from_the_market_package_like_the_other_modes`).
`docs/api/market.md` already carried `::: mambo_power.market.agents`; `test_api_docs_coverage.py` green.

Red:
```
>       assert market.solve_agents is agents_module.solve_agents
E       AttributeError: module 'mambo_power.market' has no attribute 'solve_agents'
1 failed, 48 deselected
```
Green: `3 passed, 48 deselected` (export test + both api-docs-coverage tests).
Sabotage (stash `__init__.py`): `AttributeError: module 'mambo_power.market' has no attribute
'solve_agents'` — `1 failed`; restored.

## Fix 2 — markup on a non-linear cost leaked as `INTERNAL` — `d718053`

Mechanism followed: `jobs/registry.py:_run_market_agents` catches `ValueError` from
`solve_agents` and raises `NetworkValidationError([DANGLING_REF @ options.strategies])`, which
`jobs/run.py` maps to `VALIDATION`. So the fix raises `ValueError` up front.

Files: `src/mambo_power/market/agents.py` — new `_initial_offers(agents)` called right after
`_resolve_agents`, before `load_bid_coeffs`/any `dc_opf`: asks each strategy for its round-0
offer, re-raises `NotImplementedError` as `ValueError('the markup strategy on generator "gen-1"
cannot bid on that generator's true cost: ...')` with the original chained as `__cause__`. The
offers it returns ARE round 0's (the loop computes later rounds at the bottom of its body), so a
strategy still sees exactly one observation per round — a first draft that probed and discarded
broke `test_the_loop_hands_every_strategy_a_contiguous_history` (observations == iterations+1),
which is why the loop was restructured rather than the test. `_resolve_agents` and `solve_agents`
docstrings; `src/mambo_power/jobs/registry.py` runner docstring; `docs/manual/agents.md` (warning
box ~80, mistakes table ~288 row now `ValueError ... before the first clearing`, ~298 unchanged and
now true); `docs/manual/jobs.md` (new table row). `MarkupStrategy` itself untouched.
Tests: `tests/unit/test_jobs.py::test_market_agents_markup_on_a_quadratic_cost_is_a_validation_failure`
(case14 `gen-1`, quadratic asserted as premise); `tests/unit/test_market_agents.py::
test_a_markup_strategy_on_a_quadratic_cost_is_rejected_before_any_clearing` (replaces the old
`..._still_raises_through_the_loop`, which expected the leak; `dc_opf` monkeypatched to raise
AssertionError; asserts `__cause__` is the `NotImplementedError`).

Red:
```
E       AssertionError: assert 'INTERNAL' == 'VALIDATION'
E           NotImplementedError: MarkupStrategy supports only a linear PolynomialCost (coefficients=[c1, c0]) as observation.true_cost; got kind='polynomial', coefficients=[0.01, 20.0, 0.0]
2 failed, 160 deselected
```
Green: `2 passed`; full `test_jobs.py` + `test_market_agents.py`: `162 passed`.
Sabotage (stash `agents.py`, final shape): same two lines (`'INTERNAL' == 'VALIDATION'`, bare
`NotImplementedError`) — `2 failed`; restored.

## Fix 3 — an idle markup agent climbs forever — `a02dd2b`

Files: `src/mambo_power/market/strategy.py` — in `MarkupStrategy.offer`, after the real-decrease
rule (untouched): `if previous.cleared_mw <= 0.0 and two_ago.cleared_mw <= 0.0: direction = -1.0`;
class docstring gains the rule as a bullet. `docs/manual/agents.md` rule paragraph (~73).
Tests, `tests/unit/test_market_strategy.py`: (a) `test_markup_walks_back_after_two_idle_rounds`
(30.5 → 30.0); (b) `..._floored_at_true_cost` (30.0 stays exactly 30.0); plus
`test_markup_one_idle_round_is_not_yet_a_reason_to_walk_back` (one idle round is the decrease
rule's case, passes before and after). (c) existing positive-profit tie behaviour is
`test_markup_does_not_reverse_on_a_profit_tie_within_relative_tolerance` — unchanged, green.
End to end, `tests/unit/test_market_agents.py::test_an_out_of_merit_markup_agent_settles_at_true_cost_not_at_the_cap`:
`non_pivotal_control_network(strategic_true_cost=30.0, rival_true_cost=22.0)`, markup step 0.5,
cap 40 → `converged`, offer exactly 30.0, markup 0.0, cleared 0.0, offers `[30.0, 30.5, ...]`
with max 30.5, LMP ≈ 22.

Red:
```
E       assert 31.0 == 30.0 ± 3.0e-05        (a)
E       assert 30.5 == 30.0                  (b)
E       AssertionError: assert 'iteration_cap' == 'converged'   (e2e)
3 failed, 1 passed
```
Green: `test_market_strategy.py` + `test_market_agents.py`: `83 passed`.
Sabotage (stash `strategy.py`): `3 failed, 1 passed` on the same three quantities; restored.
Economics file after: `21 passed in 13.12s`.

Note for the lead: the idle test is `cleared_mw <= 0.0` exactly, as specified. HiGHS returned an
exact 0.0 for the out-of-merit unit in the e2e case (the test asserts `== 0.0`); if some fixture
ever returns a 1e-14 dispatch for an undispatched unit the rule would not fire there. Not changed.

## Style — `3686f2e`
`jobs/registry.py` docstring line reflowed under 100 columns (E501 found by the final ruff run,
introduced by fix 2's docstring edit).

## Fourth commit — walk prose and the strategy-return check — `c0cfd12`

Head is now `c0cfd12` (on top of `3686f2e`). Tree clean.

Item 5 (code): `src/mambo_power/market/agents.py` — new `_checked_offer(agent, observation)`,
used by `_initial_offers` (round 0) and at the loop bottom (later rounds); raises
`TypeError('the <label> strategy on generator "agent_a" returned None for round 0; a
Strategy.offer must return a GeneratorCost (PolynomialCost or PiecewiseCost)')` before that
round's clearing. `solve_agents` docstring updated. Test:
`tests/unit/test_market_agents.py::test_a_strategy_returning_something_other_than_a_cost_is_rejected_at_the_call_site`
(`dc_opf` monkeypatched to AssertionError; a `Forgetful.offer` returning `None`).

Red: `AssertionError: dc_opf was reached: the bad return was not caught at the call site` —
1 failed (confirms the walk: the bad return sailed into the clearing).
Green: `test_market_agents.py` + `test_market_strategy.py` + `test_jobs.py`: 197 passed.
Sabotage (stash `agents.py`): same `dc_opf was reached` line — 1 failed; restored.

Item 2: "(spec A9)" removed from the two `offer_tol < 2 * step` messages and the validator
docstring (`agents.py`); the manual's quoted message block updated to match. Tests match on
`below 2 \* step` (test_market_agents.py:687, :694) — unchanged, green.
Item 1: `docs/manual/agents.md` — Observation/RoundRecord field names (step 1 of "One round");
default `offer_tol` 1e-9 (termination section); final-round-only result + recording wrapper
(after the settlement paragraph); `converged` needs two update rounds, `max_iterations=1` is
always `iteration_cap` (after the message block); pydantic `ValidationError` note under the error
table; LP-noise sentence (29.999974999999992) under the price-taker exactness claim.
Item 3: `docs/changelog.md` "returns the cost curve it offers (any `GeneratorCost`)".
Item 4: `examples/12_agent_market.py` two prints → "after N update rounds"; run output shows
"after 84 update rounds" / "after 7 update rounds"; exit 0.

Gates at `c0cfd12`: ruff check clean, ruff format --check 178 formatted, mypy clean (53 files),
economics file + api-docs coverage 23 passed, example 12 exit 0. Full suite not run.
