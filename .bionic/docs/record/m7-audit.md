# M7 independent audit — `ec8876e` (`wave/07-agents`)

**Head:** `ec8876e8a381b4bbc15718ce5c5e0ae545d991d2`
**Where it ran:** a `git archive ec8876e` extracted to
`…\scratchpad\audit-ec8876e` (read-only measurements) and a second identical archive at
`…\scratchpad\sabotage-ec8876e` (every sabotage; the file is restored from `git show ec8876e:` after
each one and the restoration diffed against the head — final check: `dc_opf.py` identical).
Nothing was run in `C:\Claude Projects\mambo-power` or `C:\Claude Projects\mambo-power-m7`.
**Module-resolution proof** (printed first, every run):
`mambo_power.__file__ = …\scratchpad\audit-ec8876e\src\mambo_power\__init__.py` (and
`…\sabotage-ec8876e\…` for the sabotage copy, `…\overlay-6ca9dcc\…` for the AC-1(a) overlay).
**Inputs read:** the spec's acceptance criteria, the plan's Verification Matrix section, the archived
source and tests. No slice report was opened.
**Auditor:** independent of every slice; date 2026-08-29.

**Whole suite at this head, from the archive:** `1146 passed, 4 skipped, 10 warnings in 1037.42s`, exit 0.

The plan's matrix names discharge *methods*, not test node ids; the tests named below are the ones
carrying each criterion's `ac<n>_` prefix (or the matrix's described construction) in the archived
test files.

---

## AC-1 — W1, in three clauses

> (a) The unification is behaviour-preserving: M6's complete suite passes with zero test edits on a
> tree differing from `6ca9dcc` only in the unified files. (b) A sabotage of the shared helper's
> diagonal takes at least one test red in *each* of the three callers' test modules, naming the
> residual that moves in each. (c) The new generator-side overlap guard fires: a generator index
> appearing in `pwl_costs` with a nonzero `cost_coeffs` row raises, mirroring the load-side message;
> and the previously-measured silent wrong answer is reproduced against the pre-guard build as the
> guard's power proof — dispatch 223.19 MW → 0.00 MW, objective +2409.70, status still `Optimal`.

### (a) — my own construction, not a test

Two archives of `6ca9dcc`; into one I copied exactly `src/mambo_power/opf/{dc_opf,multiperiod,zonal}.py`
from `ec8876e` (nothing else — `opf/__init__.py`'s `costs=` extension stays at `6ca9dcc`). `diff -rq`
between the two archives lists exactly those three files. M6's own test tree, unmodified:

```
OVERLAY __file__ …\scratchpad\overlay-6ca9dcc\src\mambo_power\__init__.py
992 passed, 4 skipped, 10 warnings in 717.63s (0:11:57)
EXIT 0
```

Same 992/4 as the M6 close. Behaviour-preserving, with the M7 guard and helper in place.

### (b) — sabotage of the shared diagonal (`dc_opf.py:548`, `2.0 * c2` → `1.0 * c2`)

Run against the callers' modules `test_opf_dc.py test_opf_dc_demand.py test_opf_solve_dc_opf.py
test_opf_dc_case14_pwl.py test_opf_multiperiod.py test_market_multiperiod.py test_opf_zonal.py
test_market_zonal.py test_market_nodal.py`:

```
FAILED tests/unit/test_opf_dc_case14_pwl.py::test_objective_cost_matches_hand_built_economic_dispatch_oracle
FAILED tests/unit/test_opf_dc_case14_pwl.py::test_quadratic_generators_dispatch_matches_the_uniquely_pinned_oracle_value
FAILED tests/unit/test_opf_dc_case14_pwl.py::test_pwl_generators_fully_use_their_strictly_cheaper_segments_and_split_the_tied_residual
FAILED tests/unit/test_opf_zonal.py::test_case30_clears_with_two_of_its_three_corridors_at_their_caps
FAILED tests/unit/test_opf_zonal.py::test_case30_zones_joined_by_a_slack_corridor_price_identically
FAILED tests/unit/test_market_zonal.py::test_ac4_the_redispatched_point_is_the_nodal_optimum[case30-0.001]
… (11 test_market_zonal.py rows: nodal-optimum, LMP equality, welfare gap, AC-5a/5b figures)
16 failed, 154 passed in 58.22s
```

- `dc_opf` caller: red on **objective_cost** and **quadratic-generator dispatch** vs the hand-built oracle.
- `zonal` caller: red on **welfare gap / redispatched point / LMPs**.
- `multiperiod` caller: **0 red** in `test_opf_multiperiod.py` and `test_market_multiperiod.py`.

Two follow-up sabotages to characterise the multiperiod blindness (`ac1b-multiperiod.log`,
`ac1b-extra.log`):

| sabotage | multiperiod unit modules | `tests/parity/test_market_multiperiod_vs_pypsa.py` |
|---|---|---|
| gen entry halved (`1.0*c2`) | 0 red | 6 red (objective, dispatch, SOC, LMP vs PyPSA) |
| gen entry zeroed (`0.0*c2`) | 0 red | 8 red |
| demand entry halved (`-1.0*v2`) | 0 red | 0 red |

Why: `test_opf_multiperiod.py:93` — "every generator in this module has a purely linear cost"; its only
quadratic case (lines 693–700) asserts `multiperiod_dc_opf(T=1) == dc_opf` — both sides go through the
same sabotaged helper, so the comparison is blind by construction. Only the PyPSA parity module carries
an external oracle for the multiperiod QP, and nothing anywhere in multiperiod's tests sees the demand
entry.

(For completeness, the demand-halved sabotage against `test_opf_dc_demand.py + test_market_nodal.py +
test_opf_zonal.py + test_market_zonal.py` reddens **only** `test_market_zonal.py` (9): `dc_opf`'s own
demand-side tests do not pin the quadratic bid either. Pre-existing, not M7's, recorded as a note.)

### (c) — named tests, then the power proof with the guard disabled in my copy

```
uv run pytest tests/unit/test_opf_overlap_guard.py -q
7 passed in 8.63s
```

Probe `probe_ac1c.py` (case14, gen 0's own quadratic sampled as a 5-point PWL, `objective_cost` =
polynomial + epigraph term per `dc_opf.py:942`). Guard disabled by editing `dc_opf.py:423`
`if double_charged:` → `if double_charged and False:` in the sabotage copy:

```
--- guard DISABLED ---
correct form: status=Optimal objective=7708.066811 gen0=223.192107 MW
doubly-charged: status=Optimal objective=10117.766447 gen0=-0.000000 MW  delta_obj=+2409.699637
GUARD DID NOT FIRE
markers after restore: 0
--- guard RESTORED ---
doubly-charged: raised ValueError: generator index(es) [0] appear in both cost_coeffs (nonzero row) and pwl_costs — …
```

223.192107 → −0.000000 MW, +2409.699637, status `Optimal`: the spec's three numbers, reproduced to six
decimals. Message mirrors the load-side form (`test_the_load_side_mirror_still_fires` green).

**Verdict: PARTIAL.** (a) and (c) discharged by my own constructions. (b) holds for `dc_opf` and
`zonal`; for `multiperiod` the clause is satisfiable only by counting `tests/parity` as "its test
module", and then only for the generator entry. See Finding 1.

---

## AC-2 — the overlay never mutates the network

> `Scenario` and `Network` serialize byte-identically before and after a `solve_agents` run whose
> agents all bid above cost, and every `Generator.cost` is unchanged. Paired positive control: on that
> same run the coefficients handed to the array builder **differ** from the true ones.

Named test:
```
tests/unit/test_market_agents.py::test_ac2_the_network_is_byte_identical_across_a_run_that_really_marked_up
1 passed in 1.85s
```
Read: both clauses on one run; captures `cost_coeffs` at the `dc_opf` seam; asserts `handed[0]` equals
true cost and `handed[-1]` does not, with the strategic row at 60.0 vs 20.0. Not vacuous.

Independent recomputation (`probe_ac2_ac3.py`) — the brief asked for `is`-identity, which the test does
not check (it compares JSON):
```
AC-2 run: converged [60.0, 60.0]           # duopoly, both agents marked up 20 → 60
scenario.network is same object: True
generator objects identical: True
Generator.cost `is`-identical: True
cost coefficient values: [[20.0, 0.0], [20.0, 0.0]]
```

**Verdict: DISCHARGED.**

---

## AC-3 — price-takers reproduce the competitive result

> (a) Exact, on the input: on an all-price-taker configuration the offer coefficients handed to the
> array builder are `array_equal` to the generators' own true cost coefficients. (b) Exact, on the
> output too: dispatch and LMPs are `array_equal` to `market.solve_nodal`'s. … No price-taker
> short-circuit exists.

Named tests:
```
tests/unit/test_market_agents_economics.py -k ac3
8 passed, 13 deselected in 2.84s
```
Source check: `test_ac3b_dispatch_and_lmps_are_bitwise_market_solve_nodals` uses `np.array_equal` on
dispatch, LMPs and loads (`test_market_agents_economics.py:284-296`) — no `allclose`, no `approx`;
parametrised over linear / quadratic (case14) / piecewise (case14_pwl). `test_ac3_the_all_price_taker_case_is_an_ordinary_run_of_the_general_path`
replaces `solve_nodal` with a raiser and asserts `iterations >= 2`.

Independent recomputation, my own comparison including `tobytes()`:
```
AC-3b linear    kinds=['polynomial'] poly-degrees=[2] iterations=2 dispatch array_equal=True lmp array_equal=True loads array_equal=True max|dp|=0.000e+00 max|dlmp|=0.000e+00 bitwise(tobytes)=True
AC-3b quadratic kinds=['polynomial'] poly-degrees=[3] iterations=2 … bitwise(tobytes)=True
AC-3b piecewise kinds=['piecewise', 'polynomial'] poly-degrees=[3] iterations=2 … bitwise(tobytes)=True
```

**Verdict: DISCHARGED.**

---

## AC-4 — a pivotal supplier's markup stops where demand stops paying

> Closed form: profit `(π − 20)(1000 − 10π)` peaks at π = $60.00, q = 400 MW, $16,000/h. Measured: offer
> $60.00, price $60.00, 400.00 MW, profit $15,999.98 against $0.06 at true cost. Raising the bid moves the
> peak. Paired control: a 900 MW rival at $22 stops the climb at $21.50 for a gain of $1,177.50 against
> the pivotal $15,999.92 — 13.6× smaller, stopped by the rival, not by demand.

Named tests:
```
tests/unit/test_market_agents_economics.py -k ac4
13 passed, 8 deselected in 14.25s
```

Independent recomputation (`probe_ac4_ac5.py`) on **hand-set fixtures the tests never use** (different
true costs, intercepts and steps), against `π* = (v1 + c)/2`, `q* = 10·v1 − 10·π*`:

```
v1=100 c=20 step=0.5 : offer=60.0000 (closed 60.00) lmp=60.0000 mw=399.999 (400.0) profit=15999.98 (16000.00) converged iters=84
v1=100 c=30 step=0.5 : offer=65.0000 (closed 65.00) lmp=65.0000 mw=349.999 (350.0) profit=12249.99 (12250.00) converged iters=74
v1= 80 c=10 step=0.25: offer=45.0000 (closed 45.00) lmp=45.0000 mw=349.999 (350.0) profit=12249.99 (12250.00) converged iters=144
v1=140 c=20 step=1.0 : offer=80.0000 (closed 80.00) lmp=80.0001 mw=599.999 (600.0) profit=35999.96 (36000.00) converged iters=64
```
Non-pivotal control, expected stop = rival − step:
```
step=0.5 : offer=21.5  lmp=21.5001 mw=785.00 converged iters=7
step=0.25: offer=21.75 lmp=21.7501 mw=782.50 converged iters=11
```
The stop follows the step (21.5 / 21.75), i.e. it is the rival's $22 minus one step, not a demand
quantity — the control's mechanism is what the spec says it is.

**Verdict: DISCHARGED.**

---

## AC-5 — the loop's own termination

> (i) the run takes strictly more than one non-trivial round and ends with the offer vector's
> oscillation amplitude inside `offer_tol`, reporting `converged=True` with `iterations` equal to the
> measured count … amplitude 1.0 at iteration 84. (ii) `max_iterations` below the needed count →
> `termination_reason` names the cap; the "raise while at capacity" rule → names the cycle, not the
> cap. `converged=False` in both. `status` asserted independently of `converged` in every clause.

Named tests:
```
tests/unit/test_market_agents.py -k 'ac5 or settled_climb or amplitude_band or cycle_wider or status_is_the_lp'
17 passed, 31 deselected in 29.51s
```

Independent recomputation — amplitude read from offers **recorded by my own wrapper** around the shipped
`MarkupStrategy`, with the cycle's period found by my own repeated-state search (not the loop's):

```
step=0.5: converged iters=84  period=4 amplitude=1.0                 offer_tol=1.0 amp<=tol=True  (amp-tol)=0        offers=[60.0, 60.0]
step=0.1: converged iters=404 period=4 amplitude=0.20000000000000284 offer_tol=0.2 amp<=tol=False (amp-tol)=+2.83e-15 offers=[60.00000000000057, …]
step=0.7: converged iters=61  period=4 amplitude=1.4000000000000057  offer_tol=1.4 amp<=tol=False (amp-tol)=+5.77e-15 offers=[59.9000000000001, …]
step=0.3: converged iters=137 period=4 amplitude=0.5999999999999943  offer_tol=0.6 amp<=tol=True  (amp-tol)=-5.66e-15
```
Cap and the boundary round:
```
max_iterations=10: iteration_cap converged=False iters=10 status=Optimal offers=[25.0, 25.0]
cap=83: iteration_cap iters=83 | cap=84: converged iters=84 | cap=85: converged iters=84
```
Smooth pivotal at `offer_tol == 2*step`: step 0.1 → `converged` (404 rounds, amp 0.2+2.8e-15); step 0.7
→ `converged` (61 rounds, amp 1.4+5.8e-15). Neither is reported as `cycle`, which is what the brief asked
me to check.

Observation: at steps 0.1 and 0.7 the settled amplitude is **strictly outside** `offer_tol` by a few
femto-dollars and is admitted by `_settled`'s `isclose(rel_tol=1e-9)` band (`agents.py:357-393`). The
spec's wording is "inside `offer_tol`"; the code's wording is "inside, counting a ULP-scale overshoot as
inside". The band is disclosed in the docstring, tested directly
(`test_the_amplitude_band_admits_ulps_and_nothing_economically_real`: admits 1+64·2⁻⁵², refuses 1.001),
and eleven orders of magnitude below a real cycle. Finding 4 (note).

**Verdict: DISCHARGED.**

---

## AC-6 — jobs

> `market.agents` registered and `KINDS` exactly 8; a request round-trips through JSON with the
> `StrategyConfig` union crossing as data; and each of an unknown strategy kind, a strategy naming a
> nonexistent generator, a non-positive `max_iterations`, and a non-positive `offer_tol` maps to
> `BAD_OPTIONS` or `VALIDATION` — never `INTERNAL`, never a silently accepted last-wins duplicate.

Named tests:
```
tests/unit/test_jobs.py -k 'market_agents or ac6'
19 passed, 93 deselected in 10.30s
```
`test_market_agents_strategy_config_round_trips_through_run_json_as_data_not_a_callable` goes through
`run_json` on a JSON **string** and asserts the union crosses as `{kind, step}` only.

Independent recomputation (`probe_ac6.py`), through `jobs.run` / `run_json`:
```
len(KINDS) = 8
unknown kind               -> failed BAD_OPTIONS
nonexistent generator      -> failed VALIDATION  (DANGLING_REF at options.strategies)
max_iterations 0 / -3      -> failed BAD_OPTIONS
offer_tol 0 / -1           -> failed BAD_OPTIONS
offer_tol below 2*step     -> failed BAD_OPTIONS
out-of-service generator   -> failed VALIDATION
internal fault (dc_opf raises RuntimeError) -> failed INTERNAL  'RuntimeError: audit-injected engine fault'
internal fault (dc_opf raises ValueError)   -> failed VALIDATION 'DANGLING_REF at options.strategies: audit-injected ValueError from the engine'
duplicate 'strategic' key in JSON -> status=ok  provenance.options.strategies={'strategic': {'kind': 'markup', 'step': 0.5}}  offers.strategy=['markup']
```
The four named mistakes and a `RuntimeError` fault classify correctly. Two things do not:

1. **An engine-side `ValueError` is reported as a caller mistake.** `_run_market_agents`
   (`jobs/registry.py:248-251`) wraps the *whole* `solve_agents` call in `except ValueError` and
   re-raises it as `NetworkValidationError(DANGLING_REF, path="options.strategies")`. Its docstring
   (`registry.py:239-243`) says the clearing's own `NonConvexCostError`/`NonConcaveBidError` "are neither
   one a `ValueError`, so this `except` cannot swallow them" — false: `class NonConvexCostError(ValueError)`
   at `opf/dc_opf.py:261`, `NonConcaveBidError(ValueError)` at `:274`, and pydantic's `ValidationError`
   is a `ValueError` too. Reachable without monkeypatching (`probe_nonconvex.py`: case14 with gen 0's
   `c2 = −0.01`, which `validate_network` accepts):
   ```
   market.nodal   -> failed INTERNAL   'NonConvexCostError: non-convex quadratic generator cost…'
   opf.dc         -> failed INTERNAL   'NonConvexCostError: …'
   market.agents  -> failed VALIDATION issues=[('DANGLING_REF', 'options.strategies')]   (with or without strategies)
   ```
   The same bad network gets three different verdicts, and `market.agents`' one blames a field the
   caller may not have set. This is the mirror image of the M6 defect the row cites, not its fix.
2. **A duplicated generator key in the raw JSON is silently last-wins** and runs to `status=ok`. The
   spec clause says "never a silently accepted last-wins duplicate"; the tests do not exercise a
   duplicate at all. This is a property of JSON parsing at `run.py:240` (`model_validate_json`) and so
   holds for every kind's options, not only `market.agents`; whether the clause meant JSON-level
   duplicates is the lead's reading, but as written it is not discharged.

**Verdict: PARTIAL.** Findings 2 and 3.

---

## AC-7 — docs

> Manual page, API pages rendering every new result and config field under the per-model griffe guard,
> architecture edges, an example that runs, changelog entry, and the `docs/manual/jobs.md:267`
> stale-transcript fix. `mkdocs build --strict` exit 0; every example runs.

Run myself from the archive (`ac7.log`):
```
INFO - pydantic_fields: documented 248 field(s) in mambo_power
INFO - Documentation built in 58.05 seconds
MKDOCS EXIT 0
01_load_and_validate.py … 12_agent_market.py   all 12: exit 0   (run from the archive root)
```
- Per-model guard: `docs/hooks/pydantic_fields.py` — `_undocumented(cls)` is recomputed per class from
  the real `model_fields`, and a non-empty `silent` list emits a warning, which `--strict` turns into
  exit ≠ 0. New models are referenced from `docs/api/market.md`, `docs/api/results.md`,
  `docs/manual/agents.md`, `docs/manual/jobs.md`, `docs/changelog.md` (`### Added — wave M7`).
- `jobs.md` diff vs `6ca9dcc`: the `kind` row now says `"market.agents" in M7`; the transcript at old
  line 267 now lists eight registered kinds; `INFEASIBLE_LP`/`UNBOUNDED_LP` rows widened to five kinds.
- Independent check I did not have: I did not sabotage the griffe guard itself (M6 R2 owns that); I read
  it and confirmed the per-model branch is the one that warns.

**Verdict: DISCHARGED.**

---

## AC-8 — `MarketNodalResult.branches`

> `MarketNodalResult` carries `OpfBranchFlowResult` rows agreeing with `pf.dc` on the same solution to a
> pinned tolerance, under the same field name and row type as `MarketZonalResult`.

Named tests:
```
tests/unit/test_market_nodal.py -k ac8
4 passed in 4.53s
```

Independent recomputation (`probe_ac8.py`) — a **dense `B'θ = P` solve in numpy** (slack pinned, tap
ratios and phase shifts applied, no `pf.dc`, no PTDF) from each result's own reported dispatch and
elastic-load quantities, on rated case14 with three bid loads:
```
nodal : rows=20 type=OpfBranchFlowResult max|reported - independent| = 9.148e-14 MW
agents: rows=20 type=OpfBranchFlowResult max|reported - independent| = 9.148e-14 MW
nodal.branches == agents.branches (price-takers): True
row type / field name: list[OpfBranchFlowResult] == list[OpfBranchFlowResult]  ('branches' on both)
```
`MarketAgentsResult.branches` (the agents loop's own `_clearing_rows`, which AC-8's tests do not cover)
agrees to the same 1e-13.

**Verdict: DISCHARGED.**

---

## Test hygiene (new files)

- `pytest.raises` without `match`: `tests/unit/test_market_strategy.py:433, 438, 440` (unknown config
  kind, non-positive step — `ValidationError` with no message check). `test_jobs.py:288/308/310` are
  pre-existing M3 tests. Note-level.
- Loops that could skip: every `for row in result.offers` / `for recorder in recorders.values()` in the
  new files iterates a container the same test has already bound to a known non-empty set (two named
  agents, or `assert handed`). `test_ac3a` asserts `handed` non-empty before its loop.
- `assert out.result.generators` (`test_jobs.py:1243`) is a non-empty check on a container, used as
  intended.
- `test_ac5i_the_settled_oscillation_is_two_steps_wide:486,488` assert constants against constants
  (`AC5_AMPLITUDE == 2 * STEP`); harmless, the real assertions are on the recorded tail.

---

## Findings

1. **should-fix** — `tests/unit/test_opf_multiperiod.py:93` (and `:693-700`). AC-1(b)'s multiperiod
   clause is not dischargeable against multiperiod's own test modules: every generator there is linear,
   and the one quadratic case compares `multiperiod_dc_opf(T=1)` with `dc_opf`, which shares the
   sabotaged helper. Repro: sabotage `dc_opf.py:548` `2.0 * c2 → 1.0 * c2` (or `0.0 * c2`) in a copy;
   `pytest tests/unit/test_opf_multiperiod.py tests/unit/test_market_multiperiod.py` stays green; only
   `tests/parity/test_market_multiperiod_vs_pypsa.py` reddens (6/8). Sabotage `-2.0 * v2 → -1.0 * v2`:
   nothing in multiperiod reddens, parity included. One hand-oracle quadratic (and one quadratic-bid)
   case in `test_opf_multiperiod.py` closes it.
2. **should-fix** — `src/mambo_power/jobs/registry.py:248-251` (docstring `:239-243`). The
   `market.agents` runner's `except ValueError` catches every `ValueError` raised anywhere under
   `solve_agents`, including `NonConvexCostError`/`NonConcaveBidError` (`opf/dc_opf.py:261, 274` —
   both subclass `ValueError`, contrary to the docstring) and pydantic `ValidationError`, and relabels
   them `VALIDATION / DANGLING_REF at options.strategies`. Repro: `probe_nonconvex.py` — case14 with
   gen 0 `c2 = −0.01` → `market.nodal`/`opf.dc` say `INTERNAL`, `market.agents` says `VALIDATION` at
   `options.strategies`. Fix at the layer it lives: raise a dedicated exception type from
   `_resolve_agents` and catch only that, or catch around `_resolve_agents` alone.
3. **should-fix** (scope is the lead's call) — `src/mambo_power/jobs/run.py:240`. A duplicated key inside
   `options.strategies` in the request JSON is last-wins and runs to `status=ok`
   (`probe_ac6.py`: `{"strategic": price_taker, "strategic": markup}` → provenance shows only `markup`).
   AC-6's text says never a silently accepted last-wins duplicate; no test covers a duplicate. Applies to
   every kind's JSON, not only `market.agents`; a `json.loads(..., object_pairs_hook=…)` pre-check at the
   `run_json` boundary would make it `BAD_REQUEST`.
4. **note** — `src/mambo_power/market/agents.py:357-393`. `converged` admits a settled amplitude a few
   ULPs *above* `offer_tol` (measured +2.8e-15 at step 0.1, +5.8e-15 at 0.7); the spec's AC-5(i) says
   "inside `offer_tol`". Deliberate, documented and tested; the spec text should say so. The docstring's
   "64 ULPs above at 0.1, 19 at 0.7" does not match this head's measurement (2.83e-15 = 102 ULP(0.2) ≈
   12.7·2⁻⁵²; 5.77e-15 = 26 ULP(1.4)); numbers only, the band's adequacy is unaffected.
5. **note** — `tests/unit/test_opf_dc_demand.py`, `tests/unit/test_market_nodal.py`. Halving the demand
   Hessian entry (`dc_opf.py:549`) reddens nothing in `dc_opf`'s or nodal's modules — only
   `test_market_zonal.py` (9). Pre-M7 residual, surfaced by this audit's sabotage; outside AC-1(b)'s
   literal claim.
6. **note** — `tests/unit/test_market_strategy.py:433, 438, 440`: `pytest.raises(ValidationError)` with
   no `match`.

## Overall

**6 DISCHARGED / 2 PARTIAL / 0 REFUTED** — AC-2, AC-3, AC-4, AC-5, AC-7, AC-8 discharged; AC-1 and
AC-6 partial.

The wave's economic content holds up under independent construction: the overlay leaves `Generator.cost`
object-identical, the price-taker run is bitwise `solve_nodal` on all three cost shapes, the pivotal climb
lands on `(v1 + c)/2` for four fixtures the tests never saw, the control's stop tracks the rival minus one
step, the AC-1(c) power proof reproduces to six decimals with the guard disabled, and branch flows agree
with a dense `B'θ` solve to 1e-13 MW on both the nodal and the agents result. The two partials are about
what the tests can *see*, not about the code's numbers: multiperiod's own test module cannot detect a
wrong shared Hessian diagonal because it never exercises one against an external oracle, and the
`market.agents` job runner classifies engine-side `ValueError`s (a non-convex cost included) as the
caller's `options.strategies` mistake — the reverse of the M6 defect AC-6 was written against, and
reachable with a network `validate_network` accepts. Neither blocks the wave; both are one-file fixes
that should land before the merge claims AC-1(b) and AC-6 in full.

---

## Re-audit at 852dd38

**Head:** `852dd38bc1a7cc038725ec6b9110e1aca6b4dae3` (`wave/07-agents`; nine commits after `ec8876e`,
`9b30e01..852dd38`). Fresh `git archive 852dd38` at `…\scratchpad\audit-852dd38` (read-only) and
`…\scratchpad\sabotage-852dd38` (sabotages; `dc_opf.py` restored from `git show 852dd38:` after each,
marker count 0 confirmed). `mambo_power.__file__ = …\scratchpad\audit-852dd38\src\mambo_power\__init__.py`
printed first on every run. Neither checkout was used. No S9/S10 report was opened.

**Source changed since `ec8876e`:** `jobs/registry.py`, `market/__init__.py`, `market/agents.py`,
`market/strategy.py` — four files. **`jobs/run.py` is unchanged** (see item 2).

**Whole suite from the archive:** `2 failed, 1157 passed, 4 skipped, 10 warnings in 491.01s`, exit 1 — the two reds are the duplicate-key tests of item 2.

### 1. AC-1(b) — the hand-oracle multiperiod case

Named test: `tests/unit/test_opf_multiperiod.py::test_quadratic_cost_and_quadratic_bid_at_t2_match_the_hand_oracle`
— `1 passed` at the head (sabotage copy, baseline).

**Derivation, done by hand before reading the test's comment through:** gq cost `0.05p² + 10p` on
[0, 200] → MC = 0.1p + 10; gl `12p` on [0, 50]; elastic load MV = 40 − 0.1d, bound 300 at t=0 and 100 at
t=1; no ramp, storage or rating, so periods decouple.
t=0: price > 12 so gl sits at 50; d = gq + 50; MC = MV → 0.1gq + 10 = 40 − 0.1(gq + 50) → 0.2gq = 25 →
**gq = 125, d = 175, π = 22.5**. t=1: MV(100) = 30 > cost of the 100th MW, bound binds; least-cost split of
100 MW: gl 50, gq 50, **π = MC(50) = 15**. Objective = (781.25 + 1250 + 600) + (125 + 500 + 600) =
**3856.25**. Sabotage predictions: gen entry halved → effective 0.025p² → 0.05gq + 10 = 35 − 0.1gq →
gq = 166.67 (**Δ 41.67**); demand entry halved → MV = 40 − 0.05d → 0.1gq + 10 = 37.5 − 0.05gq →
gq = 183.33 (**Δ 58.33**). All of the test's numbers reproduce.

Sabotages in the sabotage copy (`ac1b-852dd38.log`):
```
--- gen halved   (dc_opf.py: 2.0 * c2 -> 1.0 * c2)      1 failed   Max absolute difference: 41.66641111
--- demand halved (dc_opf.py: -2.0 * v2 -> -1.0 * v2)   1 failed   Max absolute difference: 58.33305556
```
Both reddened on the dispatch, by exactly the hand-predicted amounts. Multiperiod's own module now sees
both entries of the shared diagonal; the finding-1 residual is closed.

**Is the 1e-3 MW band justified?** Measured at the head (`probe_qp.py`):
```
T=2 dispatch [[124.99985000015, 50.0], [50.0, 50.0]]  prices [22.4999975, 15.000005]  obj 3856.246625
residual vs hand: gq0 -1.4999985e-04 MW   p0 -2.5e-06   p1 +5.0e-06   obj -3.375e-03
T=1 gq residual  -1.4999985e-04  |  dc_opf gq residual  -1.4999985e-04      (bit-identical across the three builders)
KKT residual at the solver's point: MC - MV = -3.0e-05 $/MWh
```
The 1.5e-4 MW shortfall is HiGHS's QP stopping point, identical through `dc_opf`, T=1 and T=2, so it is
the solver's and not the builder's. 1e-3 MW is 6.7× the residual and 4.6 orders under either sabotage
(41.7 / 58.3 MW); a 1e-6 band would fail a correct build. Objective band 1e-2 vs 3.4e-3 measured (3×);
price band 1e-5 vs 5e-6 measured at t=1 (2× — the thinnest margin in the test, but a sabotage moves the
price by ≥ 2 $/MWh, five orders away). Justified.

**Verdict for AC-1: DISCHARGED** ((a), (c) as before; (b) now red in all three callers' own modules —
dc_opf 3, zonal 13, multiperiod 1 — under the generator sabotage, and multiperiod also under the demand one).

### 2. AC-6

(i) `probe_nonconvex.py` at the head (case14, gen 0 `c2 = −0.01`):
```
market.nodal   -> failed INTERNAL 'NonConvexCostError: …'
opf.dc         -> failed INTERNAL 'NonConvexCostError: …'
market.agents  -> failed INTERNAL 'NonConvexCostError: …'   (with and without strategies)
```
Same code as `market.nodal`. `probe_ac6.py`'s injected engine `ValueError` now also lands `INTERNAL`
(was `VALIDATION/DANGLING_REF`). Finding 2 closed.

(ii) `registry._run_market_agents` source: the only `except` is `except AgentSetError as exc:`;
`AgentSetError` is a `ValueError` subclass, exported from `mambo_power.market`. The five up-front
rejections through `jobs.run`, each `VALIDATION` with `DANGLING_REF at options.strategies` naming the
generator: ghost generator, out-of-service generator, generator with `cost=None`, `offer_tol < 2·step`
on an injected object (not reachable through JSON; the config path is `BAD_OPTIONS`, as before), and —
new — a markup strategy on quadratic `gen-1` of case14, which raised **with `dc_opf` monkeypatched to
raise `AssertionError`** and so before any clearing (`probe_walk.py` (b)). The four original mistakes
and the unknown kind / non-positive bounds are unchanged (`BAD_OPTIONS`).

(iii)/(iv) **REFUTED at this head.** Commit `bfd25d4` "run_json rejects a duplicated JSON key at any
depth as BAD_REQUEST" changed **only** `docs/manual/jobs.md` and `tests/unit/test_jobs.py`; no source
file carries the `object_pairs_hook` pre-parse it describes (`git grep object_pairs_hook 852dd38 -- src`
is empty; `git log --all -- src/mambo_power/jobs/run.py` ends at M5's `1fd4c74`). Its own two tests fail
at the head:
```
FAILED tests/unit/test_jobs.py::test_run_json_rejects_a_duplicated_strategies_key_as_bad_request
FAILED tests/unit/test_jobs.py::test_run_json_rejects_a_duplicated_top_level_key_as_bad_request_for_any_kind
  AssertionError: assert 'ok' == 'failed'
```
and my own probe still reports `duplicate 'strategic' key in JSON -> status=ok … strategies={'strategic':
markup}`. The spec clause "never a silently accepted last-wins duplicate" does not hold at `run_json`.
The commit message's "Sabotage: skip the pre-parse, both tests redden" describes an implementation that
was never committed. The following commit `6d00ac3` (the worktree's current HEAD) is docs-only, so it
is not there either.

**Verdict for AC-6: PARTIAL** — (i) and (ii) discharged; the duplicate clause refuted at the head, with
the wave's own tests red on it.

### 3. The walk's three defects (`probe_walk.py`, own constructions)

```
market.solve_agents is agents.solve_agents: True | MarketAgentsOptions: True | in __all__: True
(b) markup on quadratic 'gen-1' via jobs, dc_opf sabotaged -> failed VALIDATION  names gen=True
(c) out-of-merit (own market: rivals 900 MW @ $20 and $25, strategic 900 MW @ $35):
    reason=converged iters=4 offer=35.0 cleared=0.0 markup=0.0 lmp=20.0001  levels=[35.0, 35.5, 35.0, 35.0, 35.0]
(c') in-merit control (rival 100 MW @ $20, strategic @ $35): converged offer=62.5 cleared=274.999
     — residual demand 900 − 10π, closed form π* = (90+35)/2 = 62.5, q* = 275: the climb still climbs
(d) TypeError before clearing (dc_opf sabotaged), names gen=True:
    'the Forgetful strategy on generator "agent_b" returned None for round 0; …'
```
All three reproduce on markets the tests do not use. Discharged.

### 4. The idle rule's tolerance, and byte-identity of AC-4/AC-5

`strategy._IDLE_MW_ABS_TOL = 1e-09`. Two idle rounds at `cleared_mw` of 0, 1e-12 and exactly 1e-9 →
next offer 30.0 (walked back); at 1.0000001e-9 and 1e-6 → 31.0 (climbed). Boundary is `<=`, as documented.

`probe_ac4_ac5.py` re-run on **both** archives (`ec8876e`, `852dd38`), module line stripped:
`diff` empty, `md5 fa17eae5…` on both — every AC-4 pivotal/control number, every AC-5 amplitude, period,
iteration count and ULP offset is byte-identical. The idle rule does not touch a unit that is dispatched,
which every AC-4/AC-5 agent is in every round.

Discharged.

### 5. Test hygiene on S9/S10's new tests

- `test_market_strategy.py:433/438/440` now carry `match=` (finding 6 closed). The five new idle-rule tests
  assert exact or `approx` offer levels on hand-built observations; none vacuous.
- `test_market_agents.py`: `test_an_out_of_merit_markup_agent_settles_at_true_cost_not_at_the_cap` unpacks
  `(row,) = result.offers` (fails if empty) and pins the trajectory `[30.0, 30.5]` and `max == 30.5`;
  the two "before any clearing" tests sabotage `dc_opf` to prove the ordering; the export test uses `is`.
  No `raises` without `match`.
- `test_jobs.py`: the two duplicate-key t

---

## Re-audit at 852dd38

**Head:** `852dd38bc1a7cc038725ec6b9110e1aca6b4dae3` (`wave/07-agents`; nine commits after `ec8876e`,
`9b30e01..852dd38`). Fresh `git archive 852dd38` at `…\scratchpad\audit-852dd38` (read-only) and
`…\scratchpad\sabotage-852dd38` (sabotages; `dc_opf.py` restored from `git show 852dd38:` after each,
marker count 0 confirmed). `mambo_power.__file__ = …\scratchpad\audit-852dd38\src\mambo_power\__init__.py`
printed first on every run. Neither checkout was used. No S9/S10 report was opened.

**Source changed since `ec8876e`:** `jobs/registry.py`, `market/__init__.py`, `market/agents.py`,
`market/strategy.py` — four files. **`jobs/run.py` is unchanged** (see item 2).

**Whole suite from the archive:** `2 failed, 1157 passed, 4 skipped, 10 warnings in 491.01s`, exit 1 — the two reds are the duplicate-key tests of item 2.

### 1. AC-1(b) — the hand-oracle multiperiod case

Named test: `tests/unit/test_opf_multiperiod.py::test_quadratic_cost_and_quadratic_bid_at_t2_match_the_hand_oracle`
— `1 passed` at the head (sabotage copy, baseline).

**Derivation, by hand:** gq cost `0.05p² + 10p` on [0, 200] → MC = 0.1p + 10; gl `12p` on [0, 50];
elastic load MV = 40 − 0.1d, bound 300 at t=0 and 100 at t=1; no ramp, storage or rating, so the periods
decouple. t=0: price > 12 so gl sits at 50; d = gq + 50; MC = MV → 0.1gq + 10 = 40 − 0.1(gq + 50) →
0.2gq = 25 → **gq = 125, d = 175, π = 22.5**. t=1: MV(100) = 30 > cost of the 100th MW, so the bound
binds; least-cost split of 100 MW: gl 50, gq 50, **π = MC(50) = 15**. Objective =
(781.25 + 1250 + 600) + (125 + 500 + 600) = **3856.25**. Sabotage predictions: generator entry halved →
effective 0.025p² → 0.05gq + 10 = 35 − 0.1gq → gq = 166.67 (**Δ 41.67 MW**); demand entry halved →
MV = 40 − 0.05d → 0.1gq + 10 = 37.5 − 0.05gq → gq = 183.33 (**Δ 58.33 MW**). Every number in the test
reproduces.

Sabotages in the sabotage copy (`ac1b-852dd38.log`):
```
--- gen halved    (dc_opf.py: 2.0 * c2  -> 1.0 * c2)    1 failed   Max absolute difference: 41.66641111
--- demand halved (dc_opf.py: -2.0 * v2 -> -1.0 * v2)   1 failed   Max absolute difference: 58.33305556
```
Both redden on the dispatch, by exactly the hand-predicted amounts. Multiperiod's own module now sees
both entries of the shared diagonal.

**Is the 1e-3 MW band justified?** Measured at the head (`probe_qp.py`):
```
T=2 dispatch [[124.99985000015, 50.0], [50.0, 50.0]]  prices [22.4999975, 15.000005]  obj 3856.246625
residual vs hand: gq0 -1.4999985e-04 MW   p0 -2.5e-06   p1 +5.0e-06   obj -3.375e-03
T=1 gq residual -1.4999985e-04  |  dc_opf gq residual -1.4999985e-04   (bit-identical across the three builders)
KKT residual at the solver's point: MC - MV = -3.0e-05 $/MWh
```
The 1.5e-4 MW shortfall is HiGHS's QP stopping point, identical through `dc_opf`, T=1 and T=2, so it is
the solver's and not the builder's. 1e-3 MW is 6.7× the residual and 4.6 orders under either sabotage
(41.7 / 58.3 MW); a 1e-6 band would fail a correct build. Objective band 1e-2 vs 3.4e-3 measured (3×);
price band 1e-5 vs 5e-6 measured at t=1 (2× — the thinnest margin in the test; a sabotage moves the price
by ≥ 2 $/MWh, five orders away). Justified.

**Verdict for AC-1: DISCHARGED** — (a), (c) as before; (b) now red in all three callers' own modules
(dc_opf 3, zonal 13, multiperiod 1) under the generator sabotage, and multiperiod also under the demand one.

### 2. AC-6

(i) `probe_nonconvex.py` at the head (case14, gen 0 `c2 = −0.01`, which `validate_network` accepts):
```
market.nodal   -> failed INTERNAL 'NonConvexCostError: …'
opf.dc         -> failed INTERNAL 'NonConvexCostError: …'
market.agents  -> failed INTERNAL 'NonConvexCostError: …'   (with and without strategies)
```
Same code as `market.nodal`. `probe_ac6.py`'s injected engine `ValueError` now lands `INTERNAL` too (was
`VALIDATION/DANGLING_REF`). Finding 2 closed.

(ii) `registry._run_market_agents`'s only `except` is `except AgentSetError as exc:`; `AgentSetError` is
a `ValueError` subclass exported from `mambo_power.market`. Through `jobs.run`, each up-front rejection is
`VALIDATION` with `DANGLING_REF at options.strategies` naming the generator: ghost generator,
out-of-service generator, generator with `cost = None`, and — new — a markup strategy on quadratic
`gen-1` of case14, raised **with `dc_opf` monkeypatched to raise `AssertionError`**, i.e. before any
clearing (`probe_walk.py` (b)). The fifth (`offer_tol < 2·step` on an injected object) is unreachable
through JSON; its config-path twin is `BAD_OPTIONS`, as are the unknown kind and the non-positive bounds.

(iii)/(iv) **REFUTED at this head.** Commit `bfd25d4` ("run_json rejects a duplicated JSON key at any
depth as BAD_REQUEST") changed **only** `docs/manual/jobs.md` and `tests/unit/test_jobs.py`. No source
file carries the `object_pairs_hook` pre-parse its message describes: `git grep object_pairs_hook 852dd38
-- src` is empty and `git log --all -- src/mambo_power/jobs/run.py` ends at M5's `1fd4c74`. Its own two
tests fail at the head:
```
FAILED tests/unit/test_jobs.py::test_run_json_rejects_a_duplicated_strategies_key_as_bad_request
FAILED tests/unit/test_jobs.py::test_run_json_rejects_a_duplicated_top_level_key_as_bad_request_for_any_kind
  AssertionError: assert 'ok' == 'failed'
```
and my own probe still reports `duplicate 'strategic' key in JSON -> status=ok … strategies={'strategic':
markup}`. The commit message's "Sabotage: skip the pre-parse, both tests redden" describes code that was
never committed; the next commit `6d00ac3` (the worktree's current HEAD) is docs-only, so it is not there
either. The spec clause "never a silently accepted last-wins duplicate" does not hold at `run_json`.

**Verdict for AC-6: PARTIAL** — (i) and (ii) discharged; the duplicate clause refuted at the head, with the
wave's own tests red on it.

### 3. The walk's three defects (`probe_walk.py`, own constructions)

```
market.solve_agents is agents.solve_agents: True | MarketAgentsOptions: True | in __all__: True
(b) markup on quadratic 'gen-1' via jobs, dc_opf sabotaged -> failed VALIDATION  names gen=True
(c) out-of-merit (own market: rivals 900 MW @ $20 and $25, strategic 900 MW @ $35):
    reason=converged iters=4 offer=35.0 cleared=0.0 markup=0.0 lmp=20.0001  levels=[35.0, 35.5, 35.0, 35.0, 35.0]
(c') in-merit control (rival 100 MW @ $20, strategic @ $35): converged offer=62.5 cleared=274.999
     residual demand 900 - 10*pi, closed form pi* = (90+35)/2 = 62.5, q* = 275: the climb still climbs
(d) TypeError before clearing (dc_opf sabotaged), names gen=True:
    'the Forgetful strategy on generator "agent_b" returned None for round 0; …'
```
All three reproduce on markets the tests do not use. Discharged.

### 4. The idle rule's tolerance, and byte-identity of AC-4/AC-5

`strategy._IDLE_MW_ABS_TOL = 1e-09`. Two idle rounds at `cleared_mw` of 0, 1e-12 and exactly 1e-9 → next
offer 30.0 (walked back); at 1.0000001e-9 and 1e-6 → 31.0 (climbed). The boundary is `<=`, as documented.

`probe_ac4_ac5.py` re-run on **both** archives (`ec8876e`, `852dd38`), module line stripped: `diff` empty,
md5 `fa17eae5…` on both — every AC-4 pivotal/control number and every AC-5 amplitude, period, iteration
count and ULP offset is byte-identical. The idle rule cannot touch a unit that is dispatched, which every
AC-4/AC-5 agent is in every round.

Discharged.

### 5. Test hygiene on S9/S10's new tests

- `test_market_strategy.py:433/438/440` now carry `match=` (finding 6 closed). The five new idle-rule
  tests assert exact or `approx` offer levels on hand-built observations; none vacuous.
- `test_market_agents.py`: `test_an_out_of_merit_markup_agent_settles_at_true_cost_not_at_the_cap` unpacks
  `(row,) = result.offers` (fails if empty) and pins the trajectory `[30.0, 30.5]` and `max == 30.5`; the
  two "before any clearing" tests sabotage `dc_opf` to prove the ordering; the export test uses `is`. No
  `raises` without `match`.
- `test_jobs.py`: the two duplicate-key tests are well-formed (positive control `run_json(text) == ok`
  included) — and red, per item 2.
- `test_opf_multiperiod.py`: the hand-oracle test reads nothing back from `dc_opf`; its tolerances are
  measured above.

### Findings after re-audit

- Finding 1 (multiperiod blind to the shared diagonal): **closed** — hand-oracle test reddens under both sabotages.
- Finding 2 (runner relabels engine `ValueError`s): **closed** — `AgentSetError` only.
- Finding 3 (duplicate JSON keys silently last-wins): **open, escalated to blocking** — `bfd25d4` committed
  the tests and the manual entry but not the `run_json` pre-parse; the suite at this head has 2 failed.
- Finding 4 (ULP figures in `_settled`'s docstring): **closed** — re-measured to 102/26/51.
- Finding 5 (dc_opf/nodal demand-Hessian blindness): unchanged, note, pre-M7.
- Finding 6 (`raises` without `match`): **closed**.
- **New, note:** the runner docstring and `_initial_offers` say a strategy's `NotImplementedError` "never
  reaches this runner". True for round 0 only; one raised in a later round still escapes as `INTERNAL`.
  No shipped strategy does this; recorded for the docstring's accuracy, not as a defect.

### Overall at 852dd38

**7 DISCHARGED / 1 PARTIAL / 0 REFUTED** — AC-1 now discharged; AC-6 partial on one clause, with the head's
own suite red on it. The two substantive audit findings are fixed and re-proven by my own sabotages and
probes; the walk's three defects and the idle rule reproduce on markets the tests never use; AC-4/AC-5
outputs are byte-identical to `ec8876e`. What remains is one missing source change whose tests and docs
were committed without it.

---

## Re-audit at 47b52da

**Head for this section only:** `47b52da3706f718ca7a9dad84ce9e1c7ee6830d9` — "run_json's duplicate-key
rejection — the source half bfd25d4 committed without". `git diff --stat 852dd38 47b52da -- src` is
exactly one file, `src/mambo_power/jobs/run.py` (+87/−1); every other measurement in the `852dd38`
section stands unchanged for this head. Fresh `git archive 47b52da` at `…\scratchpad\audit-47b52da`
(`mambo_power.__file__ = …\audit-47b52da\src\mambo_power\__init__.py` printed first) and a sabotage
copy at `…\scratchpad\sabotage-47b52da` (`run.py` restored from `git show 47b52da:` afterwards, marker
count 0). Neither checkout used.

**What landed:** `_reject_duplicate_keys` pre-parses the request text with a `json.loads`
`object_pairs_hook` that raises `DuplicateKeyError` on a repeated key in any object; a second pass
locates the dotted path; `run_json` maps it to `BAD_REQUEST` with `kind`/`job_id` still echoed
best-effort. Malformed or too-deep JSON falls through to pydantic exactly as before (the hook's
generic `except` returns). Applies to every kind.

Named tests (both of `bfd25d4`'s, red at `852dd38`):
```
tests/unit/test_jobs.py           116 passed in 11.68s     (whole module; the two duplicate tests included)
```

Independent recomputation (`probe_dup.py`, my own placements of the duplicate — none of them the test's):
```
valid (no duplicate)                          -> ok
dup at options.strategies (agent_a x2)        -> failed BAD_REQUEST  duplicate key "agent_a" at options.strategies
dup top-level kind                            -> failed BAD_REQUEST  duplicate key "kind" at request
dup inside network.buses[1] (id)              -> failed BAD_REQUEST  duplicate key "id" at network.buses[1]
dup inside options (offer_tol x2, same value) -> failed BAD_REQUEST  duplicate key "offer_tol" at options
dup deep in generators[0].cost                -> failed BAD_REQUEST  duplicate key "coefficients" at network.generators[0].cost
malformed JSON                                -> failed BAD_REQUEST  (pydantic json_invalid, unchanged)
not an object                                 -> failed BAD_REQUEST  (pydantic model_type, unchanged)
valid request via run_json == via run (modulo timing): True
```
Every depth tried (top level, `options`, `options.strategies`, inside a list element, inside a nested
model) is rejected with the key and its path; a duplicate that repeats the *same* value is rejected too
(last-wins would have been invisible there). `probe_ac6.py`'s original case — the one that ran to
`status=ok` at `ec8876e` and `852dd38` — now reports `failed BAD_REQUEST`, no provenance options, no
offers. The valid request's output is unchanged modulo timing.

Sabotage (skip the pre-parse call in `run_json`, sabotage copy):
```
markers: 1  (run.py: `_reject_duplicate_keys(text)` replaced by `pass`)
FAILED tests/unit/test_jobs.py::test_run_json_rejects_a_duplicated_strategies_key_as_bad_request
FAILED tests/unit/test_jobs.py::test_run_json_rejects_a_duplicated_top_level_key_as_bad_request_for_any_kind   (assert 'ok' == 'failed')
2 failed, 114 deselected in 16.44s
restored markers: 0
```

**Whole suite from the `47b52da` archive:** `1159 passed, 4 skipped, 10 warnings in 235.61s`, exit 0.

**Verdict for AC-6 at 47b52da: DISCHARGED.** Finding 3 closed.

### Overall at 47b52da

**8 DISCHARGED / 0 PARTIAL / 0 REFUTED.** Heads used per item: AC-1, AC-6(i)/(ii), walk defects, idle
rule, AC-4/AC-5 byte-identity and hygiene at `852dd38` (source identical at `47b52da` except `run.py`);
AC-6(iii)/(iv) and the gate suite at `47b52da`; AC-2/3/4/5/7/8's original discharge at `ec8876e`, with
AC-4/AC-5 re-confirmed byte-identical at `852dd38`. Open notes only: the pre-M7 demand-Hessian blindness
in `dc_opf`'s and nodal's own tests (finding 5), and the runner docstring's "never reaches this runner"
being a round-0 statement.

---

## Final re-audit at 12aa3ce

**Head:** `12aa3ce6b6ad8f087241dcada21eea2da755ab06` (seven commits after `47b52da`: the `3·step` floor,
PTDF built once per run, one `market/_clearing.py` for nodal and agents rows, NaN/inf step guard,
structured out-of-range `pwl_costs` error, critic nits, duplicate-key path finder). Fresh
`git archive 12aa3ce` at `…\scratchpad\audit-12aa3ce`; `mambo_power.__file__ =
…\audit-12aa3ce\src\mambo_power\__init__.py` printed first; no checkout used. Every number below is
from my own probes, re-run on the `ec8876e` archive alongside for comparison.

**Whole suite from the archive:** `1172 passed, 4 skipped, 10 warnings in 393.30s`, exit 0.

### AC-3 — bitwise through `market/_clearing.py` and the cached `ptdf=`

`probe_ac3_md5.py`: all-price-taker `solve_agents` vs `solve_nodal`, dispatch + LMPs + loads + branch
flows concatenated, `array_equal` and `tobytes()` equality, md5 of the raw float64 bytes:
```
             ec8876e                              12aa3ce
linear     bitwise=True  1bfa9723…  (agents == nodal)   bitwise=True  1bfa9723…  (agents == nodal)
quadratic  bitwise=True  98640233…                      bitwise=True  98640233…
piecewise  bitwise=True  984c4b07…                      bitwise=True  984c4b07…
```
`diff` of the two heads' outputs is empty: the shared clearing-rows construction and the PTDF passed
in from the loop change no byte of any of the three shapes' results. **DISCHARGED.**

### AC-4 / AC-5 — at the `offer_tol ≥ 3·step` floor

`probe_ac45_v2.py` (same fixtures as before, `offer_tol = 3·step`; the script runs unchanged on
`ec8876e` since `3·step ≥ 2·step`), `diff` against the `ec8876e` run:
```
AC-4 pivotal (v1,c,step): (100,20,.5) 60.0000/400.0/15999.98 iters=84 | (100,30,.5) 65.0000/350.0/12249.99 | (80,10,.25) 45.0000/350.0 | (140,20,1.0) 80.0000/600.0/35999.96  — all converged, all on (v1+c)/2
AC-4 control: step .5 -> 21.5 (785.00 MW, 7 iters); step .25 -> 21.75 (782.50 MW, 11 iters)
AC-5 duopoly: step .5 -> 84 iters, period 4, amplitude 1.0, offers [60, 60]; .1 -> 404; .7 -> 61; .3 -> 137 — all converged
AC-5(ii): cap 10 -> iteration_cap [25, 25]; cap 83 -> iteration_cap [59.5, 59.5]; cap 84 / 85 -> converged at 84
```
Every stopping point, amplitude, period, iteration count and verdict is **identical** to `ec8876e`; the
only diff lines are the three the floor was meant to change (below). **DISCHARGED**, both rows.

**The critic's half-grid case** (smooth pivotal, true cost 33.33, step 0.01, `offer_tol` 0.03; closed
form π* = (100 + 33.33)/2 = 66.665, exactly between two grid points):
```
12aa3ce: converged  iters=3339  period=6  amplitude=0.030000000000015  offer=66.66  lmp=66.66003  mw=333.399
ec8876e, same case at offer_tol=0.02 (the old 2·step floor): cycle  iters=3339      <- the defect
12aa3ce, offer_tol=0.02:  rejected up front — "offer_tol=0.02 is below 3 * step … so 3 * step=0.03"
```
The orbit is three steps wide (period 6, amplitude 0.03) and the loop reports it `converged`; the
tolerance that used to misreport it is now refused by the validator. `MarketAgentsOptions(step=0.5,
offer_tol=1.0)` is rejected at the head (accepted at `ec8876e`).

**`_settled` abs_tol** (`agents.py:485-487`, `abs_tol=0.0`): `_settled(2e-9, 1e-9)` is `False` at the
head (`True` at `ec8876e` — the default `offer_tol=1e-9` was silently `2e-9`); `_settled(1.9e-9, 1e-9)`
`False`; `_settled(1e-9·(1+5e-10), 1e-9)` still `True` (relative band intact);
`_settled(1.0 + 64·2⁻⁵², 1.0)` still `True`. Default `offer_tol` is `1e-9` and now means it.

### AC-1(c) — the guard after the signature change

`probe_ac1c.py` at the head: correct form `Optimal 7708.066811, gen0 223.192107 MW`; doubly-charged →
`ValueError: generator index(es) [0] appear in both cost_coeffs (nonzero row) and pwl_costs …`. The
raise is unchanged. Out-of-range indices, my own placements on case14 (`n_gen = 5`):
```
idx=5  -> ValueError: pwl_costs generator index 5 out of range for 5 generators (NetworkArrays.gen_ids)
idx=10 -> ValueError: pwl_costs generator index 10 out of range for 5 generators (NetworkArrays.gen_ids)
idx=-1 -> ValueError: pwl_costs generator index -1 out of range for 5 generators (NetworkArrays.gen_ids)
```
A negative index — which Python would otherwise have silently read as "the last generator" — is caught
too. **DISCHARGED.**

### AC-8 — branch flows after the refactor

`probe_ac8.py` (dense `B'θ` solve, rated case14 with three bid loads) at the head:
```
nodal : rows=20  max|reported - independent| = 9.148e-14 MW
agents: rows=20  max|reported - independent| = 9.148e-14 MW
nodal.branches == agents.branches (price-takers): True ; both list[OpfBranchFlowResult] under `branches`
```
Same residual to the last digit as at `ec8876e`. **DISCHARGED.**

### Overall at 12aa3ce

**8 DISCHARGED / 0 PARTIAL / 0 REFUTED.** Nothing survives. The refactors (shared clearing rows, cached
PTDF) are byte-transparent on AC-3 and AC-8; the `3·step` floor and `abs_tol=0.0` change no AC-4/AC-5
outcome while fixing the half-grid misreport and the doubled default tolerance; the overlap guard is
intact and now structured for a bad index. Heads per criterion: AC-1(a)/(b) at `6ca9dcc`-overlay /
`852dd38`, AC-1(c) / AC-3 / AC-4 / AC-5 / AC-8 at `12aa3ce`, AC-6 at `47b52da` (plus the walk/idle
items at `852dd38`), AC-2 / AC-7 at `ec8876e`. Open notes only: the pre-M7 demand-Hessian blindness in
`dc_opf`'s and nodal's own tests (finding 5).
