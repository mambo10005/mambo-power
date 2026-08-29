# M6 (`zonal-redispatch`) — six-axis code review

Scope: `4cfd1d7..d0ce957`, 11 commits, 34 files, +6734/−223 (`git diff --stat 4cfd1d7..d0ce957`).
Worktree `C:\Claude Projects\mambo-power-m6`, branch `wave/06-zonal-redispatch`.
Method: full read of `opf/zonal.py`, `opf/redispatch.py`, `opf/dc_opf.py`'s extraction preamble
and row-family core, `market/zonal.py`, `results/zonal.py`, `jobs/*`; assertion-level inventory of
all six M6 test files; a 12-sabotage sweep and six behavioural probes in a detached scratch
worktree at `d0ce957` (`git worktree add --detach`, `PYTHONPATH=<scratch>/src`, imports verified
to resolve to the scratch copy). The live worktree was not modified.

Baseline for every sabotage figure below:

```
PYTHONPATH=<scratch>/src uv run --no-sync pytest tests/unit/test_opf_zonal.py \
  tests/unit/test_opf_redispatch.py tests/unit/test_market_zonal.py \
  tests/unit/test_zones_helper.py tests/parity/test_market_zonal_vs_pypsa.py
-> 131 passed, 4 skipped in 18.57s
```

**Verdict: no blocking finding.** The LP formulations are correct — I checked every sign,
right-hand side and slice by hand and could not find an error that produces a wrong market answer
on a well-formed input. Three items should be folded before merge; all three are on the
user-facing input surface or in a docstring that would mislead the next person, not in the maths.

---

## Severity-ranked findings

### FOLD BEFORE MERGE

#### F1 — Duplicate corridors given in the *same* order are silently collapsed, and the manual documents the opposite

`src/mambo_power/market/zonal.py:181`:

```python
return {(entry.zone1, entry.zone2): entry.cap_mw for entry in self.corridors}
```

A dict comprehension over a list: the last entry for a repeated key wins, with no error.
`opf/zonal.py:280-284`'s "appears twice in corridors" guard is therefore **unreachable** for
same-order duplicates — it only ever sees one entry per key.

Measured on case30 (`docs`-shaped inputs, no sabotage):

```
duplicate same-order corridor_map(): {('1', '2'): 999.0}   len(corridors)= 2
reversed-order solve -> ValueError zone pair ('1', '2') appears twice in corridors ...
```

`docs/manual/zonal.md:469` promises the opposite:

> | The same zone pair given twice, **in either order** | `ValueError` — a corridor is keyed by an unordered pair, so give it once |

"in either order" is false. `[(A,B,10), (B,A,999)]` raises; `[(A,B,10), (A,B,999)]` clears the
market at 999 MW and says nothing. This is the JSON job surface, so the input arrives from a
caller who gets no signal that half their corridor list was discarded. No test covers it — every
corridor-validation test in the wave is at the `zonal_dc_opf` array layer
(`tests/unit/test_opf_zonal.py:589-608`), where a `Mapping` makes same-order duplicates
impossible to express.

Fix: a `model_validator` on `MarketZonalOptions.corridors` that normalises each pair and rejects a
repeat. The same validator closes the second half of this: `CorridorLimit.zone2`'s description
(`market/zonal.py:139`) says *"must differ from `zone1`"* and nothing enforces it —
`MarketZonalOptions(corridors=[CorridorLimit(zone1="1", zone2="1", cap_mw=1.0)])` constructs
happily and fails at solve time.

#### F2 — No `max_length` on `MarketZonalOptions.corridors`

`market/zonal.py:170-175` declares `corridors: list[CorridorLimit] = Field(default_factory=list, ...)`
with no length bound. This wave's own S7a added `max_length=200` to `Scenario.periods`
(`model/scenario.py`) — the M5 carry-over, for exactly this reason — and then shipped a new
user-supplied unbounded list on the new job kind.

Measured: `20000 corridors accepted by the options model: 20000 -> corridor_map size 1`.

The LP does not blow up (the map collapses them, per F1), so this is a request/response-size
issue rather than a solver one — but `_provenance()` echoes `opts.model_dump()` into every result,
so a 20 000-entry request produces a 20 000-entry response body. Bound it; a network with `n`
zones has at most `n(n−1)/2` legitimate corridors.

#### F3 — `_dispatch_rows`'s docstring claims sharing that does not exist

`market/zonal.py`, `_dispatch_rows`:

> ":func:`~mambo_power.market.nodal.solve_nodal`'s own row construction, **shared** here because
> both dispatch layers of this result need it"

It is not shared. `market/nodal.py:142-149` builds `GenDispatchResult` inline, `market/nodal.py:159-170`
builds `LoadDispatchResult` inline, `market/multiperiod.py:176-190` builds the load rows inline a
second time, and `market/zonal.py` is the third copy. (`_load_rows`'s own docstring is honest —
it says "`solve_nodal`'s rule **verbatim**", which correctly describes a copy.) Either extract the
two row builders to `results/` or `market/_rows.py`, or change the word. A reader who believes
"shared" will fix a bug in one place and ship two.

---

### CARRY

#### C1 — No `getNumRow()` tripwire in either new builder (M5 added one and was right to)

`opf/multiperiod.py:635` carries:

```python
assert h.getNumRow() == expected_rows, (
    f"multiperiod_dc_opf built {h.getNumRow()} rows, but the row-order contract in this "
```

Neither `opf/zonal.py` nor `opf/redispatch.py` got the equivalent, and **no test in
`test_opf_zonal.py` or `test_opf_redispatch.py` asserts a row or column count at all**. Both
modules document a row layout and then read it back by slicing:

- `zonal.py`: `sol.row_dual[:n_zone]`, `sol.col_dual[n_dispatch:n_tier1]`, `sol.col_value[n_gen:n_dispatch]`
- `redispatch.py`: `sol.row_dual[0]`, `sol.row_dual[1:n_rows]`, `col_value[gen_up_cols]`

and both append conditionally-present row families (epigraph, hypograph, PWL linking) *after* the
rows they slice. The guard is one line each and would have caught the exact class of defect M5
shipped. `zonal.py`: `1 + n_zone` is wrong — it is `n_zone + Σ segments + Σ demand segments`;
`redispatch.py`: `1 + n_branch + n_pwl + n_demand_pwl + Σ segments + Σ demand segments`.

#### C2 — The diagonal-Hessian assembly is now a third verbatim copy

```
$ grep -rn "HighsHessian()" src/mambo_power/
src/mambo_power/opf/dc_opf.py:750
src/mambo_power/opf/multiperiod.py:437
src/mambo_power/opf/redispatch.py:361
src/mambo_power/opf/zonal.py:387
```

`diff` of `dc_opf.py:744-759` against `zonal.py:381-396` is a single cosmetic line-merge
(`starts = np.cumsum(...)` then `.tolist()`, versus the two chained on one line). `multiperiod.py:429-445`
is the same block with a per-period fill loop. `redispatch.py`'s `_hessian_pairs` is *not*
duplication — it assembles 2×2 coupled blocks and is correctly its own function.

ADR-008 was written about precisely this pattern one level up. S3 added a fresh copy of the
sibling idiom rather than extracting `_diagonal_hessian(diag) -> HighsHessian | None` alongside
`_balance_row` / `_epigraph_rows`. Three copies is where M5's extraction preamble was when
ADR-008 was written.

**The ADR-008 decision itself is executed correctly** and worth stating plainly: the
extraction/validation preamble is genuinely one copy now. `grep -rn "cost_coeffs must have
shape\|NonConvexCostError(\|NonConcaveBidError(\|appear in both demand" src/mambo_power/` returns
`dc_opf.py` only, at four sites; `_extract_and_validate(` has exactly four call sites
(`dc_opf.py:707`, `multiperiod.py:323`, `redispatch.py:283`, `zonal.py:342`); and W1's commit
deleted 65 lines from `multiperiod.py` against 17 added (`git diff --numstat 4cfd1d7..97b56ef`).

#### C3 — The shunt term in the per-zone RHS is exercised by one fixture family, and the unit test that appears to cover it is vacuous

Sabotage S1 — `zonal.py`, `fixed_bus_mw = p_load_mw + arr.g_shunt_pu * arr.base_mva` → `= p_load_mw`:

```
9 failed, 122 passed, 4 skipped
FAILED tests/parity/test_market_zonal_vs_pypsa.py::test_objective_matches_pypsa[case300-fixed]
... (all 9 are case300 parity)
```

**Every unit test stays green.** `test_case30_every_zone_balances_at_the_solution`
(`test_opf_zonal.py:526`) writes `arr.g_shunt_pu` into its expected right-hand side and looks like
the covering test — but case30 has no conductive shunt. Measured across every fixture this wave
uses:

| fixture | `sum(g_shunt_pu)` | `sum(c0)` | out-of-service gens/branches |
|---|---|---|---|
| case14 | 0.000000 | 0.0 | 0 / 0 |
| case30 | 0.000000 | 0.0 | 0 / 0 |
| case300 | 0.013000 | 0.0 | 0 / 0 |
| case14_pwl | 0.000000 | 0.0 | 0 / 0 |

So the shunt half of that assertion is arithmetic on a zero vector. Cheapest fix: run the
zone-balance test on case300 as well, or put a `g_shunt` on one bus of the hand fixture — the
latter also gives the corridor's own RHS a nonzero shunt to carry.

#### C4 — AC-4 is structurally blind to any zonal-stage defect

This answers the brief's question directly. D1's theorem is that the redispatched point is the
nodal optimum *from any feasible starting point*. `test_ac4_the_redispatched_point_is_the_nodal_optimum`
and `test_ac4_final_lmps_equal_the_nodal_lmps_on_case30` therefore pass no matter how wrong the
zonal clearing that produced the starting point was.

Demonstrated by S1 above: the zonal per-zone RHS was broken on case300 (the shunt dropped from
every zone) and every AC-4 and AC-5 assertion in `test_market_zonal.py` stayed green — only the
parity module noticed.

This is inherent to D1, not a defect, but it means AC-4 measures the redispatch stage while
carrying the chain's name. The chain's zonal half is guarded entirely by the hand-derived fixtures
and the PyPSA parity module. One sentence in `test_market_zonal.py`'s module docstring saying so
would stop the next reader from treating AC-4 as chain coverage.

#### C5 — A shared `_extract_and_validate` defect in the constant term is invisible to the entire wave

Sabotage S13b — `dc_opf.py:404`, `c0 = coeffs[:, 2]` → `c0 = np.zeros(n_gen)`:

```
131 passed, 4 skipped
```

Nothing. Cause: `sum(c0) == 0` on every fixture (table in C3). This is M5's known `c0` carry-over
and outside the wave's declared scope, but **M6 widened the exposure**: `ZonalSolution.objective_cost`,
`RedispatchSolution.objective_cost` and `RedispatchSolution.demand_value` all sum the constant
term, and none is exercised.

Worth noting because of what it does to the one test built to catch this:
`market/zonal.py`'s three figures go through `_generation_cost`/`_demand_value`, which read the
**raw** `cost_coeffs` array and never touch the extractor. Under a `c0` defect the two paths
disagree silently — and `test_the_curve_evaluators_agree_with_the_figures_the_builders_report`
(`test_market_zonal.py:783`), whose entire job is to catch a divergence between those two
constructions at `rel=1e-12`, is vacuous on every committed fixture. It is the most important
non-parity test in the file and it currently compares two zeros.

#### C6 — Two paths have exactly one assertion holding them up

Both found by sabotage; both survive today, but a single test deletion or fixture change opens
them.

**The demand half of `redispatch_payment`.** S7 — `market/zonal.py`,
`(value_zonal - value_final)` → `(value_final - value_zonal)`:

```
1 failed, 130 passed, 4 skipped
FAILED tests/unit/test_market_zonal.py::test_ac5a_redispatch_payment_is_the_welfare_the_zonal_clearing_could_not_deliver
```

The hand-derived AC-5 fixture (`test_an_overstated_corridor_sells_a_schedule_the_network_cannot_carry`,
which pins `redispatch_payment == 400.0` to 1e-9) moves no elastic demand, so it is blind to the
sign of the demand half. The one test that catches it is an algebraic rearrangement using the same
helpers as production — it catches the flip only because the grouping differs.

**The redispatch PWL linking row.** S11 — swap the delta pair in `q + Δ− − Δ+ == p0`:

```
1 failed, 130 passed, 4 skipped
FAILED tests/unit/test_opf_redispatch.py::test_d1_theorem_holds_on_the_piecewise_linear_route
```

That single test (`test_opf_redispatch.py:498`) is also the one D1 test that *drops* the `welfare`
leg (`_welfare_of` refuses PWL), so it is entirely differential against `dc_opf`. No real fixture
carries a PWL generator through `market.zonal` at all.

#### C7 — `redispatch_payment` goes negative in an ordinary regime and nothing covers it

Measured, case30 with every branch rating × 20 and every corridor cap 0:

```
loose ratings, caps 0            payment=-11.05343  welfare_gap=-1.12e-10  cost_gap= 11.05343
loose ratings, derived caps      payment= -0.22162  welfare_gap=-1.69e-10  cost_gap=  0.22162
```

The zonal LP is a relaxation only when its corridor caps are looser than what the network can
carry. A real NTC is normally set *below* thermal capability, so the restriction regime is the
common one in practice, and the "settlement figure — what the operator pays" then pays inward.

The field docstring (`results/zonal.py`) and `docs/manual/zonal.md:300` both hedge this correctly
("non-negative wherever the zonal LP is a relaxation of the nodal one") — the docs are honest.
What is missing is on the test side: `test_ac5a_the_zonal_clearing_is_a_relaxation_so_its_welfare_is_never_lower`
states the hedge's conclusion as its name and asserts the inequality unconditionally, and every
committed corridor set is `1.2 × Σ rating` (`tests/_zones.py:corridors` over `tests/_rated.py`),
i.e. always the relaxation side. One case on the other side would keep the next reader from
treating the inequality as a theorem.

#### C8 — Nothing in M6 touches `in_service`

Zero out-of-service buses, branches, generators or loads in any fixture this wave uses (table in
C3); `grep in_service tests/unit/test_opf_zonal.py tests/unit/test_opf_redispatch.py` is empty.
`tests/_zones.py:corridors` carries an explicit `if not br.in_service: continue` — that branch is
dead in every test. An out-of-service crossing branch wrongly summed into a corridor cap would not
be noticed by anything.

#### C9 — A user's bad corridor is classified as an engine bug

`solve_zonal` raises `ValueError` for an unknown zone id or a self-pair; `_run_market_zonal`
(`jobs/registry.py`) does not translate it, so `jobs/run.py:183`'s catch-all makes it `INTERNAL`.
`tests/unit/test_jobs.py:939` pins that behaviour:

```python
error = _assert_failed(out, "INTERNAL")
assert "no-such-zone" in error.message
```

`corridors` is user-supplied options data on a stateless JSON surface, and `BAD_OPTIONS` is the
code the caller needs in order to know it is their request and not the engine. Related to F1 — the
same validator would move both to pydantic and get `BAD_OPTIONS` for free.

#### C10 — Performance: two array builds and two PTDF builds per chain, ≈7% of wall

Measured on case300 (300 buses, 411 branches, 69 generators, 4 zones, 3 corridors):

```
case300 zones=4 corridors=3 status=Optimal wall=0.172s ptdf_builds=2
  from_network 0.0007s   one ptdf build 0.0106s
  duplicated work: 1 extra from_network + 1 extra ptdf = 0.0112s of 0.172s (7%)
```

The zonal stage correctly builds no PTDF at all. The two builds are `redispatch_dc_opf`'s and
`solve_nodal`'s own; the two `NetworkArrays.from_network` calls are `solve_zonal`'s and
`solve_nodal`'s, and `gen_cost_coeffs`/`load_bid_coeffs` are extracted twice for the same reason.
`RedispatchSolution.ptdf` is already returned "for reuse" but `solve_nodal` takes a `Scenario` and
cannot accept it — that seam, not this wave, is the thing that would have to change. At 7% it is
not worth restructuring the nodal entry point; recorded so the next person does not rediscover it.

Nothing is `O(n_zone²)`. `_normalise_corridors` and the inbound/outbound construction are
`O(n_corridor)`. The only zone-scaled loop is `np.flatnonzero(gen_zone == z)` once per zone,
`O(n_zone · n_gen)` where `O(n_gen)` would do — irrelevant at 3–4 zones, worth a `np.argsort`
grouping only if zone counts ever reach the hundreds.

#### C11 — `generators` means something different in `MarketZonalResult` than in `MarketNodalResult`

In `MarketNodalResult` it is the dispatch the network delivers. In `MarketZonalResult` it is the
**sold** schedule, which by construction the network cannot deliver; the delivered one is
`generators_final`. Both docstrings say this clearly and at length. The field *name* does not, and
`SolveResult.result` is a closed union of the three market result types — so a consumer writing
one loop over `result.generators` reads the physically-delivered dispatch from two members of the
union and an undeliverable schedule from the third.

Judged against the brief's D4 question: M6 did **not** create a third result convention. Every
reused row model (`GenDispatchResult`, `LoadDispatchResult`, `BusLmpResult`, `OpfBranchFlowResult`)
is reused verbatim, the `_Row` config matches, and the two-layer shape is justified by what the
result exists to report. This one field name is the single place the shape is a trap.

#### C12 — Two layers, two rules on infinite caps

`opf/zonal.py:272` explicitly permits an infinite cap ("give a number, 0, or inf") and
`zonal_dc_opf` maps it to `kHighsInf`. `CorridorLimit` sets `allow_inf_nan=False`
(`market/zonal.py:145`) and refuses it. No test sits at that boundary. Harmless today — the
`Scenario` path simply cannot express a copper-plate corridor — but say which layer is
authoritative before someone reconciles them the wrong way.

#### C13 — The netting test cannot fail

`test_reported_deltas_are_netted_and_reconstruct_the_final_point` (`test_opf_redispatch.py:424`):

```python
assert np.array_equal(solution.dispatch_mw, p0 + solution.delta_up_mw - solution.delta_down_mw)
assert np.all(solution.delta_up_mw * solution.delta_down_mw == 0.0)
```

Production computes `delta_up = np.maximum(gen_net, 0.0)`, `delta_down = np.maximum(-gen_net, 0.0)`,
`dispatch_mw = p0 + gen_net` from a single `gen_net`. `max(g,0) − max(−g,0) ≡ g` and
`max(g,0)·max(−g,0) ≡ 0` hold bit-exactly for every float, for any solver output whatsoever. Three
of the four assertions test NumPy; only the trailing shape check carries information. The
*property* is real and correctly implemented — it just has no test. If you want one, assert
something about the **raw** HiGHS columns (e.g. that they do not both come back large and
cancelling, which is what a degenerate formulation would produce); the reported pair cannot tell
you.

---

## What the sweep confirmed is solid

The formulations, checked by hand:

- **Corridor sign convention is mirrored correctly in both rows it touches.** `zonal.py`,
  `outbound[zone_pos[z1]]` / `inbound[zone_pos[z2]]` feed `_balance_row`'s withdrawal and
  injection sides respectively, giving `p_A − f == L_A` and `p_B + f == L_B` — exactly the
  AC-2 derivation. Sabotage S12 (corridor entering both rows as an injection): **41 failed**.
- **`_corridor_cap_price`'s `abs()` is right in both directions** and the docstring derives it
  rather than asserting it. Sabotage S2 (raw reduced cost): **11 failed**, across the hand oracle,
  the case30 negative-flow corridor and the parity duals.
- **The quadratic expansion's linear piece is present and correctly signed on both sides.**
  `gen_rate = c1 + 2.0 * c2 * p0` on `Δ+`, `−gen_rate` on `Δ−`; `demand_rate = v1 + 2.0 * v2 * d0`
  with the mirror sign. S4 (generator cross term dropped): **11 failed**. S5 (demand cross term
  dropped): **11 failed**. The Hessian's 2×2 block is `2a·[[1,−1],[−1,1]]` with only the lower
  triangle stored and row indices ascending within each column — correct for
  `HessianFormat.kTriangular`. S20 (off-diagonal sign flipped): **2 failed**, and it is worth
  noting *why* only two: `a(Δ⁺+Δ⁻)²` and `a(Δ⁺−Δ⁻)²` agree wherever the optimum nets, so this
  sabotage is nearly benign — it is caught only by the D1 test that starts from both `p_min` and
  `p_max`, which is a point in that test's favour.
- **Balance RHS and flow `const_k` fold the zonal point across correctly.**
  `balance_rhs = total_fixed − Σp0 + Σd0` and `const += PTDF @ (p0_by_bus − d0_by_bus)` are both
  the exact substitution of `p = p0 + Δ⁺ − Δ⁻` into `dc_opf`'s own rows, with `Δ⁺`/`Δd⁻` entering
  as injections and `Δ⁻`/`Δd⁺` as withdrawals at the same buses.
- **Bound arithmetic at a bound.** `np.maximum(p_max − p0, 0.0)` gives exactly `[p_min, p_max]`
  for the final point and floors a `BOUND_TOL_MW`-scale overshoot at zero. S18 (floor removed):
  caught, by one test — the deliberately-designed one.
- **PWL linking row.** `q + Δ⁻ − Δ⁺ == p0` via `_balance_row`, `q` bounded by the participant's
  own box, `_epigraph_rows`/`_hypograph_rows` called verbatim over `q`. S11: caught (see C6).
- **The three market figures compute what their docstrings say.** `redispatch_payment =
  (cost_final − cost_zonal) + (value_zonal − value_final)`, which is exactly
  `welfare(zonal) − welfare(final)`; `welfare_gap = welfare(nodal) − welfare(final)`;
  `generation_cost_gap = cost_zonal − cost_nodal`. All three match `results/zonal.py` word for
  word. S8 (cost-gap sign flipped): **3 failed**.

The pinned tolerances are load-bearing, not blankets. The brief asked me to check S6's claim
directly. Sabotage S10 scales the corridor caps inside `zonal_dc_opf` by `(1 + 1e-5)` — caps of
1.5–19.5 MW on case30, so a perturbation of order 1e-4 MW:

```
16 failed, 115 passed, 4 skipped
```

including `test_generator_dispatch_matches_pypsa` at `GEN_DISPATCH_ABS_TOL_MW = 1e-6` and
`test_zone_prices_match_pypsa` at `ZONE_PRICE_ABS_TOL = 1e-6`. The 1e-6 pins catch sub-milli-MW
movement, as claimed. The two bands with the least headroom are `CASE300_QUANTITY_ATOL` (5e-2 MW
against a measured 9.45e-3 residual — ~5×) and `CORRIDOR_PRICE_ABS_TOL` (1e-3 against a smallest
real signal of 0.121 $/MWh — ~76×); both are still well clear, and both are documented with the
measurement that set them.

Two other things deserve saying:

`tests/parity/test_market_zonal_vs_pypsa.py:615`,
`test_transposing_the_shared_caps_is_not_a_sabotage`, is an unusually honest test. It swaps two
corridor caps *before either side sees them*, proves the swap moves the market by 100× the pinned
tolerances, then re-runs all five parity assertions and shows them green — committing a measured
demonstration of the module's own blind spot rather than leaving it implicit. The blind spot is
real and there are two more of the same shape that have no such demonstration: the elastic bid
curves reach both sides from `tests/_bids.py`'s `interior_bid_for_load`, which derives them by
*running a mambo `solve_dc_opf`*, and the zone partition reaches both sides from
`tests/_zones.py`. Generator bounds and cost coefficients do come from the raw MATPOWER matrices
via `tests/parity/_mpc_reader.py` and are genuinely independent.

And the "two-price theorem" test does assert the reason, not a count.
`test_case30_prices_separate_into_exactly_two_levels` (parity:588) names which zones tie (1 and 3),
which stands apart (2), and pins the separation to the binding corridors' own capacity shadow
prices in both directions at 1e-3 $/MWh. Two notes: the "exactly two" of the title is completed by
its sibling `test_case30_corridor_structure_binds_two_of_three` rather than within itself, and the
docstring's claim that this is asserted "through the oracle's prices, not the engine's" is true of
the first two assertions only — the `cap_price` legs read the engine's duals. The corridor-deletion
islanding test in `tests/unit/test_jobs.py:920` *is* a bare count
(`assert len(set(prices.values())) == 3`, on exact float equality); the substantive islanding
assertion lives in `test_market_zonal.py:934`, which pins `[10.0, 50.0]`.

---

## Recommended order of work

1. F1 (validator on `corridors`: duplicate pairs, self-pair) — also fixes C9 and the manual line.
2. F2 (`max_length`), F3 (docstring or extraction) — minutes each.
3. C1 (two `getNumRow` asserts) — the cheapest real defence in the list.
4. C3 + C7 (one shunt on the hand fixture, one tight-cap case) — closes the two coverage holes
   that a plausible future change would walk into.
5. C2, C5, C6, C11 — record as wave carry-overs; C5 stays blocked on the `c0` fixture that M5
   already deferred.
