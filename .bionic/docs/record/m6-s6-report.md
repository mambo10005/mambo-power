# M6 S6 — AC-6: PyPSA zonal parity, and the settlement of assumption A1

Wave M6 "zonal-redispatch", Step 4, slice S6. Worktree `C:\Claude Projects\mambo-power-m6`,
branch `wave/06-zonal-redispatch`. Commit `dcc1839`, one file:
`tests/parity/test_market_zonal_vs_pypsa.py` (664 lines, 47 tests).

---

## 1. The verdict on A1

Spec `## Design` A1 read: *"PyPSA expresses b2 as one bus per zone + `Link`s with `p_nom = cap`.
Research §5 probed 'intra-zone limits removed', not `Link`s — AC-6 stays at-risk until S6 proves
the `Link` form."*

**Settled YES, and stronger than the assumption claimed.** The `Link` form is not merely
*expressible*; it is an **exact LP equivalence**. The objective agrees bit-for-bit on both
fixed-load fixtures (relative residual exactly `0.0`), and no other residual exceeds `2.6e-12`
except the corridor capacity price, whose `1.3e-05` is HiGHS's own QP dual precision rather than a
difference between the two models.

### Why research §5's probe could not have settled it either way

The §5 probe kept the full nodal network and set every *intra-zone* line's `s_nom` effectively
unconstrained while the 7 tie lines kept their real ratings. That is a different LP from
`opf.zonal.zonal_dc_opf` in two structural ways, not one tuning knob apart:

1. **KVL survives.** PyPSA's linearised power flow still holds over the whole network, so
   inter-zone transfer splits across the tie lines *by reactance*, and each tie line is capped
   **individually**. The engine's corridor is one free variable capped by the **sum** of its
   cut-set's ratings (`tests/_zones.py`'s `corridors`). No reactance-constrained model can
   reproduce a sum-of-ratings transport bound: the reactance-determined split is a constraint the
   engine simply does not have.
2. **Intra-zone topology survives.** Every intra-zone bus is still a real balance row, so
   intra-zone network structure still shapes the answer. The engine's zone is a copper plate with
   exactly one row.

So the probe answered "can PyPSA express something zonal-ish", which was the right Step-1
question, and left A1 genuinely open — the spec was right to flag it.

### Why `Link` and not `Line` — the argument, before the measurement

The slice brief left the choice open ("or a `Line` with `s_nom = cap` and unit reactance — pick the
form that gives an exact LP equivalence and say why"). `Line` is the wrong form, and provably so:

- A PyPSA `Line` carries a reactance and enters the linearised-power-flow (KVL) constraints. On
  case30's 3-zone partition there are **three** corridors joining **three** zones, which closes a
  loop; the loop equation would pin the flow split by reactance. The engine's LP has no
  counterpart for that equation, so the two feasible sets would differ.
- "Unit reactance" does not escape this. A unit reactance is still *a* reactance: with three equal
  reactances around a loop the split is pinned at a specific ratio, just a different one. The
  problem is the presence of the KVL row, not its coefficients.
- A `Link` is instead a **controllable transport** element. PyPSA constrains it only by
  `p_min_pu * p_nom <= p0 <= p_max_pu * p_nom`, and enters `p0` in `bus0`'s nodal balance with
  `-1` and `p1 = -efficiency * p0` in `bus1`'s.

With `p_nom = cap`, `p_min_pu = -1`, `p_max_pu = +1`, `efficiency = 1`, that is column-for-column
the engine's own corridor variable as `opf/zonal.py` documents it under "Corridor sign convention":
bounds `[-cap, +cap]`, coefficient `-1` in `z1`'s balance row and `+1` in `z2`'s. The two LPs are
**the same LP**, which is why the agreement below is structural and the objective comes back
bit-identical.

---

## 2. The oracle

One PyPSA `Bus` per zone; every generator and load attached to its own zone's bus; per-zone
aggregate fixed load; one bidirectional `Link` per corridor. Built **by hand** from the raw
MATPOWER matrices rather than through `import_from_pypower_ppc`, for a necessary reason and with a
useful side effect.

**Necessary:** the zone-aggregated network has no MATPOWER counterpart — 3 buses (case30) or 4
(case300), and **no branches at all**. There is nothing for the ppc importer to import.

**Useful side effect — a repo-wide finding.** `import_from_pypower_ppc` silently drops the bus
shunt-conductance column `GS` from its power balance. That is the *entire* root cause of
`tests/parity/test_opf_vs_pypsa.py`'s separate, wider case300 tolerance band (that module's own
docstring: 1.3 MW redistributed thinly across 68 of case300's 69 generators). Building the oracle
directly lets the per-zone fixed load be `sum(PD) + sum(GS)` over that zone's own buses — exactly
what the engine's balance row uses — so **case300 lands in the same tight band as case30 here**
rather than needing a band of its own. Any future PyPSA oracle on a shunt-bearing fixture can take
this route instead of widening a tolerance.

**Inherited unchanged from `test_opf_vs_pypsa.py`:** the gencost bridge (columns 4/5 into
`marginal_cost_quadratic`/`marginal_cost`; column 6's `c0` added back to `n.objective`, which
excludes constants — inert on every fixture here since `c0 == 0` throughout, kept so a future
`c0`-bearing fixture is not silently mis-compared).

**Not needed:** the `p_set` fix that module root-caused. Nothing here is imported, so no generator
is ever pinned in the first place.

**Elastic demand** uses PyPSA's negative-generator pattern: a `Generator` with `sign = -1`
withdraws its own `p` from the bus, so `marginal_cost = -v1` and `marginal_cost_quadratic = -v2`
reproduce the engine's demand column exactly (`dc_opf` minimises `sum cost_g - sum value_d`, putting
`-v1` on the column and `-2*v2` on the Hessian diagonal). Bids come from `tests/_bids.py`'s
`interior_bid_for_load`, not `bid_for_load`: the latter's fleet-ceiling anchor is price-taking by
construction, so every bid load would sit pinned at its own upper bound and the demand comparison
could not distinguish a correct solve from a double-counted one (that module's own docstring, M4
critic Issue 1). `test_elastic_loads_clear_strictly_inside` asserts the interior clearing actually
happened rather than trusting the anchor rule — measured on case30: 28.94 of 30.0, 10.67 of 11.2,
16.88 of 17.5.

### A PyPSA limitation worth recording

PyPSA declines to write back the shadow prices of a `Link`'s own `p` bounds, and says so:
*"the shadow-prices of the constraints Generator-fix-p-lower, Generator-fix-p-upper,
Link-fix-p-lower, Link-fix-p-upper were not assigned to the network."* `links_t.mu_upper` and
`mu_lower` come back **empty**. The oracle-side corridor capacity price is therefore taken as
`|price(z1) - price(z2)|` from PyPSA's **own** bus marginal prices. That is the capacity price by
construction rather than by assumption: a costless link's reduced cost is exactly the negated price
difference across it — the same identity `opf/zonal.py`'s `_corridor_cap_price` derives from the
engine's side — so a binding corridor's capacity is worth precisely the spread it sustains. It
remains oracle-side data: PyPSA's duals, not the engine's.

### Independence of partition and caps (AC-6's own wording, and A34)

Both come from `tests/_zones.py` — `zone_of_bus` and `corridors`, over a `tests/_rated.py`-rated,
`promote_areas_to_zones`-promoted network — and are handed to the two sides **separately**. Nothing
this module reads from a `ZonalSolution` feeds the oracle. `tests/_zones.py` needed **no addition**;
the existing four functions were sufficient.

Two structural checks guard the aggregation itself rather than trusting it:

- `test_zone_fixed_load_totals_the_raw_matpower_columns` — every zone's oracle-side fixed load plus
  every elastic load's own upper bound must total the fixture's whole `sum(PD) + sum(GS)`, summed a
  second way from the raw matrices. A partition that dropped or double-counted a bus fails here
  before it could show up as a dispatch difference a tolerance might absorb.
- `test_every_bus_and_corridor_reaches_the_oracle` — the two sides agree on the bus axis and the
  corridor axis, so no corridor is silently missing from one side.

---

## 3. Tolerances: measured first, then pinned

Worst residual over all four fixture/bid combinations (case30 and case300 × fixed-load and bids),
measured against this module's own oracle **before** any tolerance was written:

| quantity | worst measured | pinned | margin |
|---|---|---|---|
| objective (relative) | 1.67e-15 | 1e-9 | ~6e5x |
| generator dispatch | 1.59e-12 MW | 1e-6 MW | ~6e5x |
| elastic demand dispatch | 2.27e-13 MW | 1e-6 MW | ~4e6x |
| zone price | 7.11e-15 $/MWh | 1e-6 $/MWh | ~1e8x |
| corridor flow | 2.64e-12 MW | 1e-6 MW | ~4e5x |
| corridor capacity price | 1.31e-05 $/MWh | 1e-3 $/MWh | ~76x |

Per-combination, for the record:

```
case30   elastic=0  obj_rel=0.000e+00 gen=7.105e-15 dem=0.000e+00 price=0.000e+00 flow=7.105e-15 cap=1.946e-06
case30   elastic=1  obj_rel=1.667e-15 gen=1.066e-14 dem=0.000e+00 price=0.000e+00 flow=1.421e-14 cap=1.946e-06
case300  elastic=0  obj_rel=0.000e+00 gen=9.095e-13 dem=0.000e+00 price=0.000e+00 flow=1.847e-12 cap=1.309e-05
case300  elastic=1  obj_rel=2.031e-16 gen=1.592e-12 dem=2.274e-13 price=7.105e-15 flow=2.643e-12 cap=1.304e-05
```

Every band except the last sits at machine precision because the two LPs are identical. They are
pinned **four orders tighter** than this repository's usual parity bands (`1e-2` MW in
`test_opf_vs_pypsa.py` and `test_market_multiperiod_vs_pypsa.py`) precisely because there is no
modelling gap left to absorb — while still holding five-plus orders of margin against the platform
drift wave M5 met on macOS CI (spec A3). §5 below shows the tight pins are load-bearing rather than
decorative.

The corridor capacity price is the one genuinely looser band, and its looseness is the solver's dual
precision, not a model difference: HiGHS reports a primal-dual objective error around `1e-6` on
these QPs and both sides read duals off it. `1e-3` keeps ~76x over what is measured and stays two
orders below the smallest real signal any sabotage produced (0.12 $/MWh).

### On objective comparison with bids in play

`ZonalSolution.objective_cost` is generation cost only (deliberately, mirroring `OpfSolution`),
while PyPSA's `n.objective` nets the demand value out. `Case.welfare_objective()` subtracts the bid
value at the **engine's own** cleared quantities, putting the two on the same footing without either
side borrowing the other's primal solution. With no bids the subtraction is empty and it is
`objective_cost` unchanged.

---

## 4. The fixture's binding structure, committed

`test_case30_corridor_structure_binds_two_of_three` and
`test_case30_prices_separate_into_exactly_two_levels` commit S3's measured structure as tests, so
the parity above is demonstrably over a case where the corridor bounds *matter* rather than over a
copper plate where the caps are inert.

Measured (S3's numbers, re-measured here):

| corridor | cap (MVA) | flow (MW) | `abs(flow)/cap` | capacity price ($/MWh) |
|---|---|---|---|---|
| `('1','2')` | 1.5237 | +1.5237 | **1.000** | 0.12136 |
| `('1','3')` | 16.5768 | +15.3588 | 0.9265 | 0.0 |
| `('2','3')` | 19.4562 | −19.4562 | **1.000** | 0.12136 |

Signs are part of the structure and are asserted: `('2','3')` is negative under the sorted-key
convention, i.e. flowing `3 -> 2`. Zone prices come back as `3.75914544 / 3.88050446 / 3.75914698`
— **exactly two distinct levels**, for a theorem-shaped reason: summing two balance rows joined by a
non-binding exchange column cancels that column, collapsing them into the single system-wide row
`dc_opf` already builds, so the slack `('1','3')` corridor ties zones 1 and 3 (they agree to
1.5e-6 $/MWh) while the two binding corridors let zone 2 stand apart by exactly their own capacity
shadow price. That last identity is asserted in both directions, with the *oracle's* prices on the
left-hand side, so it is a statement about the market rather than about this builder's dual
bookkeeping.

Thresholds: `BINDING_RATIO = 1 - 1e-9` (nothing lands near it — 1.0 and 1.0 against 0.9265) and
`DISTINCT_PRICE_MIN = 1e-3` (two orders clear on either side — 1.5e-6 below, 0.121 above).

---

## 5. Engine-side sabotage sweep — 3 of 3 red

**Protocol.** Detached scratch worktree at branch head `4d8fc10`, created with
`git worktree add --detach`; the committed test file copied in; run with
`PYTHONPATH=<scratch>/src;<scratch>` under the main worktree's interpreter. `zonal.__file__` printed
on every run and confirmed to resolve to
`...\scratchpad\sabotage\src\mambo_power\opf\zonal.py`, never the main tree's. **The oracle's own
construction and inputs were unchanged throughout** — only `opf/zonal.py` was edited. Restored from
a pristine copy after each run, worktree removed at the end.

**Main-tree integrity.** `sha256(src/mambo_power/opf/zonal.py)` =
`d7a5d5b6ac4130b9f049296bd5c38f64217f6fbd991b50c91d68a688a7c4ad0a`, identical before the sweep and
after; the restored scratch copy hashes to the same value; `git status` in the scratch worktree
clean under `src/` at teardown.

**Control (unsabotaged scratch tree):** every residual green, matching §3's table exactly.

### Sabotage 1 — corridor sign convention flipped

`inbound`/`outbound` swapped in the per-zone balance-row loop.

| fixture | residual that moves | measured | tolerance | ratio |
|---|---|---|---|---|
| case30 fixed | corridor flow | **38.912 MW** | 1e-6 MW | 3.9e7x |
| case30 bids | corridor flow | **38.912 MW** | 1e-6 MW | 3.9e7x |
| case300 fixed | corridor flow | **261.85 MW** | 1e-6 MW | 2.6e8x |

`6 failed, 37 passed, 4 skipped`.

**The interesting part:** *only* the flow residual moves. Objective, dispatch, zone prices and
capacity prices are all untouched — a global sign flip on a symmetrically-bounded corridor is a
relabelling of direction, so the feasible set and the optimum are unchanged and only the *reported*
flows invert. This is precisely why `test_corridor_flows_match_pypsa` compares **signed** values
against `links_t.p0` rather than magnitudes; a magnitude comparison would have let this sabotage
through completely. The point is recorded in that test's own docstring.

### Sabotage 2 — a corridor bound dropped

The first corridor's cap set to `kHighsInf` at the `addVars` call.

| fixture | obj (rel) | gen (MW) | demand (MW) | price ($/MWh) | flow (MW) | cap price ($/MWh) |
|---|---|---|---|---|---|---|
| case30 fixed | **3.92e-04** | **1.826** | 0.0 | **0.0913** | **12.851** | **0.1214** |
| case30 bids | **3.38e-03** | **1.839** | **0.1014** | **0.0920** | **13.029** | **0.1219** |
| case300 fixed | 1.65e-16 | 3.18e-12 | 0.0 | 7.11e-15 | 9.12e-12 | 1.31e-05 |

`14 failed, 29 passed, 4 skipped`.

**case300 stays green**, because no corridor binds there (all three capacity prices are 0 in the
true solve). This is the concrete argument for case30 carrying AC-6: on a fixture where the caps are
slack, a dropped cap is invisible — which is exactly what §4's binding-structure test exists to
prevent anyone assuming away.

### Sabotage 3 — two zones' assignments swapped, engine-side only

Zone labels `"1"` and `"2"` transposed inside `_zone_labels`, so only the engine's own partition
changes; `tests/_zones.py`'s output and therefore the oracle's partition are untouched.

| fixture | obj (rel) | gen (MW) | demand (MW) | price ($/MWh) | flow (MW) | cap price ($/MWh) |
|---|---|---|---|---|---|---|
| case30 fixed | **8.62e-04** | **1.440** | 0.0 | **0.1933** | **33.546** | **0.2170** |
| case30 bids | **7.11e-03** | **1.401** | **0.0773** | **0.1920** | **33.847** | **0.2148** |
| case300 fixed | 1.09e-13 | **7.50e-04** | 0.0 | **1.32e-05** | **208.25** | 1.31e-05 |

`21 failed, 22 passed, 4 skipped`.

**A finding about the tolerances.** On case300 this sabotage moves generator dispatch by only
`7.5e-04` MW and zone price by `1.3e-05` $/MWh. Under this repository's customary parity bands
(`1e-2` MW dispatch, `1e-3` $/MWh price) **both of those comparisons would have stayed green** —
case300's four zones price almost uniformly (~40.026 $/MWh), so relabelling two of them barely moves
the optimum. The 1e-6 pins catch both. The corridor-flow comparison catches it regardless at 208 MW,
so detection was never at risk, but the margin the tight pins buy is real and this is the evidence
for it.

---

## 6. The negative control — and why it is committed as a test

`test_transposing_the_shared_caps_is_not_a_sabotage` makes `continuation-m5.md`'s A34 lesson
(*"a sabotage applied to shared fixture data is not a sabotage"*) demonstrable rather than asserted,
inside the suite, where it cannot quietly rot.

It swaps the `('1','3')` and `('2','3')` caps in the dictionary `tests/_zones.py` returns, **before**
either side is handed it, then does two things in order:

1. **Proves the transposition genuinely moved the market** — otherwise the demonstration is vacuous:

   | quantity | shift | matching tolerance | ratio |
   |---|---|---|---|
   | objective | 0.487 $/h | — | — |
   | worst generator dispatch | 1.440 MW | 1e-6 MW | 1.4e6x |
   | worst corridor flow | 2.879 MW | 1e-6 MW | 2.9e6x |
   | worst zone price | 0.0720 $/MWh | 1e-6 $/MWh | 7.2e4x |

2. **Re-runs five of the parity comparisons on the transposed market and shows them green**, to the
   very same tolerances the true-cap comparison meets.

A one-sided fault of that size fails every one of those tests loudly. Applied to both sides it is
invisible. That is a property of what parity *means*, not a hole in the module — and it is the
reason §5's faults are injected into `opf.zonal` itself while this oracle's construction is held
fixed.

**Which transposition, and why that one.** All three pairwise cap swaps were measured. Swapping
`('1','2')` with `('2','3')` moves the corridor flows by 17.9 MW but leaves the objective unchanged
to 1.5e-10 $ — the slack `('1','3')` corridor absorbs the rerouting and the dispatch is essentially
identical, which makes for a weaker demonstration ("the caps did not matter"). Swapping `('1','3')`
with `('2','3')` moves the objective, the dispatch, the flows **and** the prices all far past every
pinned tolerance, so that is the one committed.

---

## 7. Gates and reconciliation

| gate | result |
|---|---|
| this file | 47 collected, **43 passed, 4 skipped**, 38.6s |
| full suite (worktree) | **951 passed, 4 skipped, 0 failed**, 146.9s |
| `ruff check` (this file) | All checks passed |
| `ruff format --check` (this file) | already formatted |
| `mypy` (src-scoped) | Success, no issues in 50 source files |
| commit | `dcc1839`, explicit path, 1 file, 664 insertions |

The 4 skips are the two elastic-only tests (`test_demand_dispatch_matches_pypsa`,
`test_elastic_loads_clear_strictly_inside`) on the two fixed-load parameters. The former asserts
`demand_dispatch_mw.size == 0` before skipping, so a fixture that quietly lost its bids fails there
rather than passing an empty comparison.

**Baseline reconciliation.** The brief named 874 at `4be66b4`. That was already stale when this
slice began: the worktree collected **878** at the start, and **908** immediately before this
commit, as siblings (`m6-s5-market`'s `market/zonal.py` + `results/zonal.py` +
`tests/unit/test_market_zonal.py`, `m6-s7a-maxlength`'s `Scenario.periods` work, which advanced the
branch head to `4d8fc10`) landed during it. **955** collected after. This file accounts for exactly
the 47-test delta; the rest is sibling work, and the full-suite green above is with all of it in the
tree.

**Ownership.** Only `tests/parity/test_market_zonal_vs_pypsa.py` was created or modified. No sibling
file was touched. `tests/_zones.py` needed no addition — the brief's conditional allowance was not
used.

---

## 8. One scope decision, flagged

AC-6's wording is *"`market.zonal`'s zonal stage matches a PyPSA oracle"*. This module compares
`opf.zonal.zonal_dc_opf` **directly** rather than going through `market.solve_zonal`, for four
reasons, all recorded in the module docstring:

1. the zonal stage *is* that builder — `solve_zonal` chains it with redispatch and a nodal
   reference, neither of which this comparison is about;
2. the corridor flows and capacity prices AC-6 names live on `ZonalSolution`;
3. the array level is where an engine-side sabotage actually lands, so the comparison sits directly
   on the rows and columns §5 corrupts;
4. `market/zonal.py` was a sibling's in-flight, untracked file for most of this slice.

If the wave wants the comparison re-pointed at `solve_zonal` once S5 settles, that is a small,
contained change — the fixture builders, the oracle and every tolerance carry over unchanged.

---

## 9. Carry-overs for the wave

- **The dropped-`GS` route.** Hand-building a PyPSA oracle instead of using
  `import_from_pypower_ppc` removes the 1.3 MW shunt gap that forces `test_opf_vs_pypsa.py`'s wider
  case300 band. If that band is ever revisited, this is the fix, not a wider tolerance.
- **`Link` p-bound duals are unavailable in PyPSA.** Any future corridor/interconnector parity work
  must take the capacity price from the bus price spread, as here.
- **Signed comparisons matter.** Sabotage 1 is invisible to a magnitude comparison. Any future flow
  or transfer parity test should compare signed values.
- **Tight pins bought real detection margin.** Sabotage 3 on case300 sits at 7.5e-04 MW and
  1.3e-05 $/MWh — inside this repo's customary bands. Where an oracle is an exact LP equivalence,
  the tolerance should reflect that rather than defaulting to the house band.
