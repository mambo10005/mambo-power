# M7 S11 — critic should-fixes and nits

Worktree `C:\Claude Projects\mambo-power-m7`, branch `wave/07-agents`, base `47b52da`. Six commits
on top, nothing rewritten. Every fix test-first with a sabotage check; affected files run, not the
full suite. Final gates on the tree at `71f1cf3`: `ruff check .` clean, `ruff format --check .`
clean (179 files), `mypy` clean (54 source files), `examples/12_agent_market.py` exit 0.
`tests/unit/test_market_agents_economics.py`: **21 passed**.

| # | Critic finding | Commit |
| --- | --- | --- |
| 1 | #2(a) settled climb reported `cycle` at a half-grid peak; #10 folded in | `8d0858f` |
| 2 | #3 PTDF rebuilt every round | `0245991` |
| 3 | #4 `_clearing_rows` duplicates `solve_nodal`'s block | `36ad1f9` |
| 4 | #5 `MarkupStrategy(step=nan)` accepted | `a566088` |
| 5 | #6 out-of-range `pwl_costs` index dies as `IndexError` | `1f9d41e` |
| nits | #7, #8, #9, registry docstring (#10 in `8d0858f`) | `71f1cf3` |

**Not done: Fix 1 part (b)**, resizing `_PROFIT_TIE_REL_TOL` — the two bounds the lead set do not
leave a gap (numbers below). The constant is unchanged at `1e-9`.

**One flaw to know about:** the `a566088` commit message's `Claude-Session:` trailer has a typo
(`claude.ac/code/...` for `claude.ai/code/...`). I am not allowed to amend; it stands.

---

## Fix 1 — `offer_tol >= 3 * step` (critic #2a) — `8d0858f`

**Reproduced first** with the critic's `repro7.py` on the worktree: `tc=33.33 step=0.01: cycle
iters=3339`, window amplitude `0.030000000000015348` against `offer_tol = 0.02`. The six-round
window is the period-6, three-step orbit the critic described (66.65 / 66.66 / 66.67 / 66.68).

**Files.** `src/mambo_power/market/strategy.py` (`_SETTLED_ORBIT_STEPS = 3`, new
`MarkupStrategy.min_offer_tol` property, class docstring, `MarkupConfig.step` description);
`src/mambo_power/market/agents.py` (module docstring, `offer_tol` field description, the
validator, new `_offer_tol_shortfall` helper, `_resolve_agents`, `_settled` docstring);
`docs/manual/agents.md`, `docs/api/market.md`, `docs/changelog.md`, `docs/manual/jobs.md`,
`examples/12_agent_market.py` (comment, refusal print, every `offer_tol=1.0` at step 0.5 → 1.5);
tests `test_market_agents.py`, `test_jobs.py`, `test_market_agents_economics.py` (`2 * step` →
`3 * step` in helpers and pinned values; `offer_tol: 1.0` → `1.5` where step is 0.5).

**Nit #10 folded in:** one constant (`MarkupStrategy.min_offer_tol`), one helper
(`_offer_tol_shortfall(offer_tol, gen_id, strategy) -> str | None`), one message text. Both
enforcement points remain — the pydantic validator (so a bad request stays `BAD_OPTIONS` through
`jobs`, no behaviour change) and `_resolve_agents` for the object path (`AgentSetError`) — but
both call the helper. The test asserts the object-path message is a substring of the config-path
`ValidationError`.

**Red:** `test_a_climb_whose_peak_sits_between_two_grid_points_settles_three_steps_wide`
(`cycle`), `test_offer_tol_below_three_steps_is_rejected_by_the_options_themselves` and
`test_an_injected_markup_strategy_is_held_to_the_same_derived_constraint` (no `min_offer_tol`,
`below 2 * step`). **Green:** `test_market_agents.py` + `test_market_strategy.py` 87 passed;
`test_jobs.py` + `test_market_agents_economics.py` 137 passed; example exit 0 with the duopoly
still settling at 84 rounds and the refusal line reading `offer_tol below 3 * step is refused`.
**Sabotage:** `_SETTLED_ORBIT_STEPS = 2` reddens all three (the regression takes `offer_tol` from
`min_offer_tol`, so it reads the shipped constant instead of restating it). Critic's 70-case
sweep (`repro2.py` with `offer_tol=3*step`): 70 of 70 converge.

The validator boundary: `offer_tol = 1.25` (2.5·step at step 0.5) refused, `1.5` admitted.

Note: the spec's A9 text (`offer_tol ≥ 2 × step`, main repo, untouched) is now stale.

### Fix 1 part (b) — `_PROFIT_TIE_REL_TOL` — NOT done, numbers

The lead's rule: set the band ≥ 10× measured noise and ≤ 1/10 the smallest real one-step profit
change a shipped test relies on; stop if no gap.

*Noise, measured three ways on the three fixtures (`noise.py`, `noise3.py`, `noise4.py` in the
session scratchpad):*

- Profit at t−1 vs t−2 with the offer unchanged (the lead's literal definition): **0.0** on every
  fixture and level — HiGHS is deterministic, so this measure is vacuous.
- Solver profit vs closed form: LMP is systematically ~8e-5 $/MWh above the offer
  (e.g. `20.00007999984` for an offer of 20.0), dispatch ~1.6e-3 MW low — absolute profit error up
  to 6.4e-2 $/h, but the *same sign at every level*, so it cancels in a comparison.
- What decides a tie — the difference between two closed-form-tied one-step neighbours straddling
  the peak (`peak ± step/2`): **2.5e-8 relative at step 0.5** (the critic's `c = 20.5` case,
  4.0e-4 $/h on 15,800), 1.0e-7 at step 1.0, **2.7e-7 at step 2.0**. It scales with step
  (LMP error × Δq, Δq = 10·step on these fixtures). At step 0.01 it is 6e-10.

*Smallest real one-step change any shipped test relies on* (a pytest plugin recorded every
`(profit_prev, profit_2ago)` pair `MarkupStrategy` compared across `test_market_agents.py`,
`test_market_agents_economics.py`, `test_market_strategy.py`, `test_jobs.py`: 6,829 pairs, 2,212
distinct nonzero relative differences; the distribution has 15 values ≤ 5e-14 — ULP noise at the
duopoly's capacity plateau — then jumps to **1.5e-6**): 1.5e-6 relative, the duopoly at step 0.5
(0.009 $/h on 6,000). The new 33.33/0.01 regression itself relies on **1.8e-7** (0.002 $/h on
11,112) — a real change scales with step².

*Bounds:* lower ≥ 10 × 2.5e-8 = **2.5e-7** (step-0.5 noise only; 2.7e-6 over the measured grid);
upper ≤ 1.5e-6 / 10 = **1.5e-7** (shipped tests), or 1.8e-8 counting the new 0.01-step test. Lower
exceeds upper — no gap, by 1.7× at the single shipped step and by more across steps. The reason is
structural: tie noise grows linearly with step while a real one-step change grows with step², so
no single relative constant separates them across the step sizes the tests use. Left at `1e-9`;
the critic's suggested `1e-6` would exceed the upper bound. After Fix 1(a) the practical
consequence of a noise-decided tie is only *which* of two equal-profit offers the climb rests on
(the orbit is ≤ 3 steps either way, and classified converged), not the verdict.

## Fix 2 — PTDF once per run (critic #3) — `0245991`

**Files.** `src/mambo_power/opf/dc_opf.py` (keyword-only `ptdf: FloatArray | None = None`,
shape-checked → `ValueError`; `compute_ptdf(arr) if ptdf is None else ptdf`; docstring);
`src/mambo_power/market/agents.py` (`ptdf_matrix = compute_ptdf(arr)` once, passed every round);
tests `test_opf_dc.py`, `test_market_agents.py`.

What `dc_opf` recomputed per call and what is cached: only `compute_ptdf(arr)` (which pulls
`bbus → bf → incidence` and the scipy sparse constructions beneath it). `pf_shift(arr)` is also
called per round but is a cheap elementwise product and was not in the profile; not cached.

**Timing** (`profile200.py`: 200 update rounds on case14, every agent creeping `c1` by
`1e-6·round`, best of 3 wall): **0.41 s before → 0.19 s after**. Profiled: 0.476 s → 0.151 s;
`ptdf()` was 0.338 s (71%) of the before profile and is absent from the after top-12 (HiGHS
`enableCallbacks` at 0.044 s is now the largest item). This machine is ~10× faster than the
critic's copy, so the absolute numbers differ from the critic's 5.2 s; the ratio matches.

**Red:** `dc_opf() got an unexpected keyword argument 'ptdf'`; the loop passed none (3 cases).
**Green:** `test_opf_dc.py` + `test_market_agents.py` 61 passed; other `dc_opf` callers' files
(`test_opf_dc_demand`, `_pwl`, `_solve_dc_opf`, `_redispatch`, `test_market_nodal`,
`test_agents_fixtures`) 66 passed. Test content: `dc_opf(ptdf=ptdf(arr))` vs default —
dispatch, returned PTDF, duals and objective `array_equal`/`==`; wrong shape raises.
`solve_agents` on the three fixtures with the loop's `dc_opf` monkeypatched to strip the keyword
(the pre-S11 path) — final dispatch, LMPs, offers, round count `array_equal`, and the keyword seen
on every round as the same object. **Sabotage:** drop `ptdf=ptdf_matrix` from the loop, all three
cache cases redden.

## Fix 3 — one clearing-rows construction (critic #4) — `36ad1f9`

**Files.** New `src/mambo_power/market/_clearing.py` (`clearing_rows(net, arr, solution, lmp,
elastic_idxs) -> ClearingRows` NamedTuple; the AC-8 derivation and settlement note move to its
docstring); `nodal.py` (block replaced by the call; −60 lines; numpy/`pf_shift`/row-model imports
gone; module docstring points at the helper); `agents.py` (`_clearing_rows` deleted, call
replaced); test `test_market_nodal.py`.

**Before/after equality** (`golden_rows.py`, JSON dumps excluding provenance): `solve_nodal` and
agent-less `solve_agents` on seven networks — case14, the S6 two-bus fixture with the PWL bid and
with a fixed load, rated case14 with bids, and the three M7 fixtures — 14 results, all `==` before
vs after. **Shipped test:** `solve_nodal == solve_agents(nobody bidding)` on generators, loads,
branches, buses and the three settlement figures by `==` on case14, the two-bus PWL fixture and
rated case14 with bids (a characterisation test; it passed pre-refactor too, as a pure extraction
should). **Sabotage:** drop `- demand_by_bus` from the helper's injection — 10 of the 14 golden
results move (every elastic-load network, on *both* solvers) and the three nodal AC-8 tests
redden; restored, golden identical again. `test_market_nodal.py` + `test_market_agents.py` +
`test_market_agents_economics.py`: 86 passed.

## Fix 4 — NaN/inf `step` (critic #5) — `a566088`

`strategy.py` `__init__`: `if not (step > 0) or not math.isfinite(step)`; message
`MarkupStrategy.step must be positive and finite, got nan`. Test (`test_market_strategy.py`,
parametrised nan / inf / −inf) asserts `ValueError` naming `step` and the value. **Red:** nan and
inf did not raise. **Green:** 38 passed. **Sabotage:** revert to `step <= 0` → nan and inf redden.

## Fix 5 — out-of-range `pwl_costs` index (critic #6) — `1f9d41e`

`dc_opf.py` `_extract_and_validate`: range loop before the double-charge test raising
`pwl_costs generator index {idx} out of range for {n_gen} generators (NetworkArrays.gen_ids)`;
the guard's `0 <= i < n_gen` clause removed; docstring lists the new raise. Inherited by all three
builders. Test in `test_opf_overlap_guard.py`: index 99 on case14 (the critic's repro) and −1 via
`_extract_and_validate`. **Red:** `IndexError: index 99 is out of bounds for axis 0 with size 5`.
**Green:** overlap guard, pwl guard, dc_pwl, case14_pwl, multiperiod, zonal + strategy files 124
passed. **Sabotage:** restore the clause and drop the loop → `IndexError` again.

**Through `jobs`:** unreachable — every `pwl_costs` map a runner builds comes from
`gen_cost_coeffs` over the network's own arrays, whose indices are valid by construction. Were it
reachable, `jobs.run`'s catch-all gives a `ValueError` from a runner `INTERNAL` (only
`NetworkValidationError`, the LP errors and `AgentSetError` are mapped). Documented in the test
docstring rather than asserted through `jobs`.

## Nits — `71f1cf3`

- **#7** `_settled`: `abs_tol=0.0`, docstring paragraph added. Test: `_settled(1.9e-9, 1e-9)` is
  False, `_settled(1e-9·(1 + 2⁻⁴⁰), 1e-9)` True. Sabotage: absolute term back → reddens.
- **#8** one sentence in `MarketAgentsResult.iterations`'s description and the manual: a fixed
  point is confirmed after two identical updates, so `iterations ≥ 2` on any converged run; the
  loop is untouched.
- **#9** dead clamp in `_cost_at` removed (piecewise-offer tests still pass).
- **#10** in `8d0858f` (above).
- **registry.py** runner docstring: round-0 `NotImplementedError` arrives as `AgentSetError`; one
  from a later round (nothing shipped does this) reaches `jobs.run`'s catch-all as `INTERNAL`.
- 192 passed across `test_market_agents.py`, `test_jobs.py`, `test_market_agents_economics.py`.

## Scratchpad scripts (session scratchpad, not committed)

`noise.py`, `noise2.py`, `noise3.py`, `noise4.py`, `probe_plugin.py` + `pairs.txt` (the tie
measurements), `find_orbit.py`/`find_orbit2.py` (a cheaper reproduction than 3,339 rounds was
sought and not found: at steps ≥ 0.2 the tie noise is outside the 1e-9 band and always favours
the lower point, so the three-step orbit only appears at step 0.01), `profile200.py`,
`golden_rows.py` + `rows_before/after/sabotage.json`, `repro2_3step.py`.
