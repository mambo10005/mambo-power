# M6 S4 — `opf.redispatch`: the min-cost redispatch LP (W3, AC-3, D1's theorem)

Branch `wave/06-zonal-redispatch`, worktree `C:\Claude Projects\mambo-power-m6`.
Base `97b56ef` (S1's unification + S2's `tests/_zones.py`). Head **`55f716d`**, two commits:

| commit | subject |
|---|---|
| `fdd8993` | `feat(m6/S4): min-cost redispatch LP — true-curve objective (D1), deltas both sides` |
| `55f716d` | `test(m6/S4): AC-3 asserts energy balance too — the sabotage sweep found the gap` |

Files owned and touched, nothing else:

- `src/mambo_power/opf/redispatch.py` (new)
- `tests/unit/test_opf_redispatch.py` (new, 18 tests)
- `src/mambo_power/opf/__init__.py` (one import line, two `__all__` entries)

---

## 1. What was built

`redispatch_dc_opf(arr, cost_coeffs, p0_mw, d0_mw=None, *, pwl_costs=None,
demand_bid_coeffs=None, demand_pwl_bids=None) -> RedispatchSolution`.

`d0_mw` is positional-with-default rather than keyword-only, matching the brief's own
`(arr, cost_coeffs, p0_mw, d0_mw, *, ...)`; it defaults to `None` so a generator-only caller
writes `redispatch_dc_opf(arr, coeffs, p0)`.

The third caller of `dc_opf`'s row-family core. `_extract_and_validate`, `_balance_row`,
`_flow_limit_rows`, `_epigraph_rows`, `_hypograph_rows` and `_add_rows` are imported and used
**unmodified**. `dc_opf.py` and `multiperiod.py` are untouched.

### Columns

| tier | family | count | bounds |
|---|---|---|---|
| 1 | `Δp+_g` | `n_gen` | `[0, max(p_max − p0, 0)]` |
| 1 | `Δp-_g` | `n_gen` | `[0, max(p0 − p_min, 0)]` |
| 1 | `Δd+_d` | `n_demand` | `[0, max(d_max − d0, 0)]` |
| 1 | `Δd-_d` | `n_demand` | `[0, max(d0 − d_min, 0)]` |
| 2 | `q_g`, `cost_g` | `n_pwl` each | `[p_min, p_max]`, free |
| 2 | `q_d`, `val_d` | `n_demand_pwl` each | `[d_min, d_max]`, free |

The Hessian covers exactly tier 1 and is passed before any tier-2 column exists — `dc_opf`'s own
documented ordering constraint, which `multiperiod.py` also obeys.

### Objective — D1, the true curves

Plan A17 is honoured: **research §3(a)'s anchored linear rate is not implemented.** The objective
is the true welfare function evaluated at the *final* quantity.

For a quadratic participant, `cost_g(p0 + u) = c2·(p0+u)² + c1·(p0+u) + c0` with `u = Δp+ − Δp-`
expands to a constant, a linear term `(c1 + 2·c2·p0)·u` and a quadratic term `c2·u²`. The linear
part is a column cost (`+mc` on `Δp+`, `−mc` on `Δp-`); the quadratic part is a **2×2 Hessian
block coupling the pair**, `2·c2·[[1, −1], [−1, 1]]` — the one structural difference from
`dc_opf`'s purely diagonal Hessian. The demand side mirrors it with `−v2`/`−mv`. The dropped
constants are added back into `objective_cost`/`demand_value`, which are recomputed from the
final quantities.

That block is positive **semi**-definite and singular. It was probed before the module was
written (a two-column `min (x−y)² − 3(x−y)`): HiGHS solves it to `Optimal` and picks the clean
split. No solver option is set anywhere in the module.

### The one genuine design call: PWL without a new row family

`_epigraph_rows`/`_hypograph_rows` need the cost row to see **one** column carrying the quantity.
Under the delta encoding the final quantity spans two. Rather than write a new row family, a PWL
participant gets one extra bounded column `q` tied to its delta pair by the linking equality

```
q + Δ- − Δ+ == p0
```

which is an ordinary `_balance_row(injection=[q, Δ-], withdrawal=[Δ+], fixed=p0)`. Its own
docstring already licenses this: *"Both arguments are LP column indices, not generator/load
indices: the row is pure algebra and does not care what a column represents."* Both PWL helpers
are then called verbatim, with `q` where `dc_opf` passes its dispatch column. Only PWL
participants pay for the extra column; a quadratic one has no `q` at all.

**So: no new row-family helper was needed, and none was added.**

### The zonal point folded into the fixed RHS

`dc_opf`'s double-counting contract kept, extended by one step:

- balance: `Σ Δp+ − Σ Δp- + Σ Δd- − Σ Δd+ == total_fixed − Σ p0 + Σ d0`
- flow: `const_k` gains `+ Σ_g PTDF[k, gen_bus[g]]·p0_g − Σ_d PTDF[k, load_bus[d]]·d0_d`

`_flow_limit_rows` itself is unchanged: `Δp+`/`Δd-` go in as injections at the generator/load
bus, `Δp-`/`Δd+` as withdrawals at the same buses.

### `RedispatchSolution` (frozen)

`status`, final `dispatch_mw` / `demand_dispatch_mw`, `delta_up_mw` / `delta_down_mw`,
`demand_delta_up_mw` / `demand_delta_down_mw`, `branch_flow_mw`, `ptdf`, `objective_cost`,
`demand_value`, `duals: OpfDuals | None`, `demand_bound`, `message`, and a `welfare` property.

`duals.balance` and `duals.flow_limit` are exactly the pair `lmp_decomposition` takes.
`duals.gen_bound` is the reduced cost of each generator's `Δp+` column, which by
`∂L/∂Δp+ = ∂L/∂p` is that generator's own `[p_min, p_max]` reduced cost at the final point —
asserted against `dc_opf`'s, not merely claimed. `branch_flow_mw` is present so AC-5's settlement
identity is computable from the result object alone (M5 carry-over A23) and matches an
independent `pf.dc` readback to 1e-9 MW.

---

## 2. Two deliberate deviations from the brief's letter

**(a) The curtail bound is `[0, d0 − d_min]`, not `[0, d0]`.** They are identical today —
`NetworkArrays.from_network` sets `load_p_min_pu = np.zeros(n_load)` unconditionally
(`arrays.py:254`) — but it is `d_min` and not `0` that D1's theorem actually needs: the final
quantity must range over exactly the box nodal ranges over, no larger. Written against `d_min`
so a later `Load.p_min_mw` cannot silently break the theorem.

**(b) The reported Δ arrays are netted, not the raw HiGHS columns.** Under D1 the objective sees
the pair only through `u = Δ+ − Δ-`, so `(Δ+ + α, Δ- + α)` is exactly as optimal and the split is
a solver choice, not a modelling one. `RedispatchSolution` reports the canonical representative —
`delta_up = max(u, 0)`, `delta_down = max(−u, 0)` — so that `final == p0 + up − down` and
`up · down == 0` hold **exactly** on every platform, whatever vertex HiGHS returns. This is the
M5 CI lesson applied before it can bite: an un-netted split would be a legitimate
platform-dependent difference in a reported field.

---

## 3. Acceptance

### AC-3 — feasible in `pf.dc`, with a live paired negative

`test_ac3_redispatch_restores_pf_dc_feasibility_from_an_infeasible_zonal_point`, parametrised
over the two multi-zone fixtures. `opf.zonal` is S3's slice and is not imported; the starting
point is built research §5's way — `dc_opf` on the rated network with every *intra-zone* rating
removed, so the clearing sees only the inter-zone cut-sets. On rated case30 that leaves **7 of 41**
branches rated, exactly research §5's own count (asserted). When S3 lands, the same test body takes
its output unchanged: the redispatch LP does not care which solve produced `(p0, d0)`.

| fixture | zones | start: branches over rating | start: worst overload | final: worst overload | pinned |
|---|---|---|---|---|---|
| case30 (promoted) | 3 | 5 | **10.09 MW** | 6.4e-15 MW | `FLOW_TOL_MW = 1e-6` |
| case300 (real) | 4 | 6 | **21.61 MW** | 8.0e-12 MW | same |

Both readbacks go through `pf.dc.solve` on a network *carrying the dispatch*, a path independent
of the LP rows that produced the point. AC-3 also asserts the energy balance closes (see §5).

Redispatch volume on case30 is genuinely nonzero on both sides: 14.42 MW up / 15.11 MW down on
generators, 0.0008 MW up / 0.693 MW down on demand.

### D1's theorem — the same final point as `dc_opf`, from any start

`test_d1_theorem_redispatch_reaches_the_nodal_optimum_from_any_start`, on case14 and rated
case30, from two unrelated bound-feasible starts each: the **floor** of the box (every generator
at `p_min`, no demand served) and its **ceiling** (every generator at `p_max`, all demand served).
Neither is network-feasible and neither is near the optimum. Plus
`test_d1_theorem_holds_from_the_nodal_optimum_itself` (the degenerate start) and, inside the AC-3
test, the zonal-ish point.

Asserted: `dispatch_mw`, `demand_dispatch_mw`, `objective_cost`, `welfare`, `duals.balance`,
`duals.flow_limit`, the derived LMPs, `duals.gen_bound`, `demand_bound`. Tolerance, never
bitwise (spec A3).

| quantity | pinned | worst measured |
|---|---|---|
| dispatch / demand | `DISPATCH_TOL_MW = 1e-3` | 1.1e-4 MW (case14, ceiling) |
| welfare, generation cost | `WELFARE_REL_TOL = 1e-6` | 9.5e-8 (case30) |
| balance dual, flow duals, LMPs | `DUAL_TOL = 1e-3` $/MWh | 2.4e-5 (case14) |

**Why the quantity tolerance is looser, measured rather than assumed.** At the optimum the
welfare surface is flat *along the direction that trades one interior generator against another*:
two interior generators have equal marginal cost there, so moving `δ` MW between them costs
`O(c2·δ²)`. Probed directly on case14: the two points differ by 1.07e-4 MW in dispatch while
their true welfare differs by **3.96e-10 out of 782.65** — and the redispatch point is the
marginally *better* of the two, i.e. this is float noise in a flat valley, not a model
difference. Tightening HiGHS's primal and dual feasibility tolerances to 1e-10 changed the
dispatch difference by exactly nothing, which rules out a convergence-tolerance explanation. The
welfare assertion is the sharp one; both are asserted.

`welfare` is checked against a value computed **outside** the solver from the raw coefficient
arrays, so the theorem's value side is not checked against a number `redispatch` itself produced.

### PWL route

`test_d1_theorem_holds_on_the_piecewise_linear_route` runs the theorem on `case14_pwl` (piecewise
generator costs) with two of its bid loads converted to piecewise bids sampled off their own
derived quadratic curves — both PWL families present in one solve, exercising `q`, its linking
row, and both epigraph/hypograph helpers. Note: `with_bids(..., interior_load_ids=all)` is used
there because `tests/_bids.bid_for_load`'s fleet-ceiling anchor reads `c1 + 2·c2·p_max` off a
polynomial cost and raises `NotImplementedError` on this fixture, while
`interior_bid_for_load` anchors on `solve_dc_opf`'s own baseline price and handles PWL costs fine.

### Other tests

`ValueError` naming the generator / naming the load for an out-of-bounds start; a start a hair
outside its bound accepted (`BOUND_TOL_MW = 1e-6`, because a zonal solve routinely returns a unit
a few ulp past `p_max` — rejecting that would fail on exactly the points redispatch exists to
fix); mis-shaped `p0_mw`/`d0_mw` rejected; the shared `_extract_and_validate` guards
(`NonConvexCostError`, `NonConcaveBidError`, `cost_coeffs` shape) reaching this surface unchanged;
never-raise on an infeasible model (status + zero-filled arrays + `ptdf` still returned);
netting invariants; `branch_flow_mw` vs an independent `pf.dc` readback; final point inside
`[p_min, p_max]`/`[d_min, d_max]`; the no-elastic-demand path.

---

## 4. Finding for S5 — rated case300's duals are degenerate, and AC-4 cannot pin them

`test_case300_flow_duals_are_degenerate_at_the_nodal_optimum` pins this as a measured limit, not
a defect:

- **7** branches sit exactly at their rating at the nodal optimum (indices 47, 82, 146, 288, 307,
  309, 359), but only **5** carry a nonzero flow dual.
- `dc_opf` prices `{82, 146, 288, 307, 359}`; `redispatch_dc_opf` prices `{47, 82, 146, 288, 307}`.
  Both subsets are inside the at-rating set; neither is wrong.
- Resulting LMPs differ by **0.319 $/MWh** on a ~40 $/MWh system (0.8%).
- The **primal** theorem still holds there: generation cost agrees to 7.4e-9 relative.

The active set is not unique, so the dual is not a function of the optimum on that fixture.
**AC-4 asks for LMPs to agree with `solve_nodal` to a pinned tolerance on case300; at any
tolerance tighter than ~1 $/MWh that is unattainable, and the reason lives in the nodal LP, not
in either builder.** Recorded here and as a committed test so the S5 slice does not spend its
budget hunting a bug that isn't there. The decision — loosen AC-4's price half on case300, or
restrict it to case30 with the degeneracy recorded — is the orchestrator's.

---

## 5. Sabotage sweep

Detached scratch worktree `…/scratchpad/sab-s4-redispatch` at `55f716d`, never the working tree.
Provenance printed on every run:

```
PYTHONPATH = …/scratchpad/sab-s4-redispatch/src
redispatch.__file__ = …\scratchpad\sab-s4-redispatch\src\mambo_power\opf\redispatch.py
```

Baseline green in that tree (18 passed). sha256 before **and** after restore, identical:

```
da7dd4d35219d6e58d3529fcfcfd4523babb43e57f7a6d05ceee73ee6556541a  src/mambo_power/opf/redispatch.py
15103f67b1f8cc4f9cebfa3e82bd8e526225e00ccd5713d06fb0fb9a29bc0c60  tests/unit/test_opf_redispatch.py
```

`git status --short` clean after each restore; the worktree was removed at the end.

| # | mutation | result | residual that moves |
|---|---|---|---|
| 1 | flow-limit rows built but never added | **8 red** | AC-3's `final_overload[worst]`: 6.4e-15 MW → **11.91 MW** over rating (case30) |
| 2 | Hessian dropped — the objective becomes research §3(a)'s **anchored linear rate** (AC-4's named paired negative) | **6 red** | theorem's `dispatch_mw`: **106.92 MW** off nodal (case14), **19.06 MW** (case30) |
| 3 | `Δp+` moved to the withdrawal side of the **balance row only** (flow rows left correct) | **7 red** | AC-3's `_balance_residual_mw`: 0 → **2.96 MW** (case30); case300 goes `Infeasible` |

**Sabotage 2 leaves AC-3 green, and that is correct.** An anchored-rate objective still reaches a
*feasible* point — feasibility is a property of the constraints, which the mutation does not
touch. This is research §4(a)'s own argument, and it is the reason AC-4 is not redundant with
AC-3: only the theorem test distinguishes the rejected objective from the adopted one.

### Sabotage 3 found a real hole in AC-3, which is why there are two commits

On its first run (against `fdd8993`) sabotage 3 left **AC-3's case30 readback green**. Cause:
`pf.dc.solve` pins the slack bus at angle 0 and lets it absorb whatever mismatch the declared
injections carry, so an *unbalanced* dispatch still produces a finite flow vector — which on
case30 happened to respect every rating. The flow readback and the energy balance are two
different claims and only one was being made.

`55f716d` adds `_balance_residual_mw` and asserts it in AC-3: the redispatched point must respect
every rating **and** close `Σp − Σd − (fixed load + shunts) == 0` to `FLOW_TOL_MW`. Sabotage 3
then goes red on case30 with a 2.96 MW residual.

**This generalises beyond my slice:** any later test that verifies a dispatch through `pf.dc`
alone has the same blind spot, because the slack bus will always hide an imbalance.

---

## 6. Verification

All commands run from `C:\Claude Projects\mambo-power-m6` with `uv run --no-sync`.

```
$ uv run --no-sync ruff check src/mambo_power/opf/redispatch.py tests/unit/test_opf_redispatch.py src/mambo_power/opf/__init__.py
All checks passed!

$ uv run --no-sync ruff format --check <same three files>
3 files already formatted

$ uv run --no-sync mypy src/mambo_power/opf/redispatch.py src/mambo_power/opf/__init__.py
Success: no issues found in 2 source files

$ uv run --no-sync python -m pytest tests/unit/test_opf_redispatch.py -q
18 passed

$ uv run --no-sync python -m pytest tests/ -q
874 passed, 10 warnings in 167.36s (0:02:47)
```

**Baseline reconcile.** 830 at `97b56ef` + **18** mine = 848, confirmed by `--collect-only`
immediately after my commit. The final full run reports 874 because the sibling slice
`m6-s3-zonal` has 26 further tests present-and-green in the shared worktree, uncommitted at the
time of writing. `pytest tests/unit/test_opf_redispatch.py --collect-only` reports exactly 18.

One transient failure worth recording, not mine and now gone:
`test_api_docs_coverage.py::test_every_public_symbol_is_reachable_from_an_api_page` failed for a
window with `mambo_power.opf.zonal: ZonalDuals, ZonalSolution, zonal_dc_opf` — the sibling's
module existing before its export line. My own symbols never appeared in that gap list, because
`RedispatchSolution`/`redispatch_dc_opf` are re-exported from `mambo_power.opf`, which carries a
`:::` directive. It resolved when the sibling added their export line.

---

## 7. Not done — out of this slice

- Docs: manual page, API page entries and a runnable example for the new symbols (W8 / AC-8).
  The symbol-coverage test passes today only because the `opf` package page covers the
  re-exports; a dedicated `::: mambo_power.opf.redispatch` block is the docs slice's call.
- `market.solve_zonal`'s consumption of `RedispatchSolution` (W4/W5, S5) — including the
  `redispatch_payment` / `welfare_gap` / `generation_cost_gap` split, for which
  `objective_cost` and `demand_value` are exposed separately (`welfare` is their difference).
- AC-4's own end-to-end assertion against `market.solve_nodal`; §4 above is the constraint it
  must be written against.
