---
governing-skill: agent-skills:incremental-implementation
sdlc-step: 4
intent: build
rigor: audited
scale: wave
canonical_sdlc_version: 13
surface_type: library
language: python
has_ui: false
multi_agent: true
deploy_target: pypi
cleanup_on_finish: true
use_worktree: true
rigor-floor: audited
walk: required
design-interview: true
---

# M5 S4 — multiperiod-builder (W2, AC-2, AC-3)

Slice S4 `multiperiod-builder`. Role: senior-implementor. Worktree
`C:\Claude Projects\mambo-power-m5`, branch `wave/05-multiperiod`, base `d0031cb` (S1 `fbab76d`
+ S2 `7afa9c5` + S3 `d0031cb` all landed). Commit **`d93c448`** —
`feat(m5/S4): multiperiod DC-OPF builder — ramp coupling, storage SoC, cyclic horizon`.
Not pushed.

**AC-2 and AC-3 both hold.** For AC-3 specifically, the paired positive case genuinely produced
a non-zero readback: `min(charge, discharge) = [26.6667, 26.6667]` MW on research §3.2's
overlap-required network, against `< 1e-7` on the four canonical fixtures.

Every factual claim below carries the command that produced it and that command's output, or the
explicit label `unverified`.

---

## 1. What changed

| file | status | lines |
|---|---|---|
| `src/mambo_power/opf/multiperiod.py` | new | 683 |
| `tests/unit/test_opf_multiperiod.py` | new | 742 |
| `src/mambo_power/opf/__init__.py` | modified | +21 / −1 |

```
$ git show --stat d93c448
 src/mambo_power/opf/__init__.py    |  22 +-
 src/mambo_power/opf/multiperiod.py | 683 ++++++++++++++++++++++++++++++++++
 tests/unit/test_opf_multiperiod.py | 742 +++++++++++++++++++++++++++++++++++++
 3 files changed, 1446 insertions(+), 1 deletion(-)
```

`src/mambo_power/opf/dc_opf.py` has **zero diff**. Nothing under `market/`, `jobs/`, `model/` or
`numerics/` was touched, as scoped.

### 1.1 The one edit to a tracked file, and why it was necessary

`opf/__init__.py` re-exports `multiperiod_dc_opf`, `MultiperiodSolution` and `MultiperiodDuals`.
This is not cosmetic: `tests/unit/test_api_docs_coverage.py` walks every public submodule and
fails on any public symbol not reachable from a module that carries a `:::` directive on a
`docs/api/*.md` page. Creating `opf/multiperiod.py` took it red immediately:

```
$ uv run --no-sync pytest -q tests/unit/test_api_docs_coverage.py tests/unit/test_docstrings.py
E   AssertionError: submodule symbols missing from docs/api pages:
E     mambo_power.opf.multiperiod: MultiperiodDuals, MultiperiodSolution, multiperiod_dc_opf
1 failed, 3 passed in 6.33s
```

The re-export closes it (the test's own docstring records that a re-exported member is documented
wherever it is rendered), and it is the import path `market/multiperiod.py` will want anyway —
the same shape as `market/nodal.py` importing `gen_cost_coeffs` from `mambo_power.opf`. **S8 may
still want a `::: mambo_power.opf.multiperiod` directive on `docs/api/opf.md`** for its own page
structure; the coverage test does not require one, and adding docs pages is not this slice's
scope.

---

## 2. Design: what was decided here, and against what

### 2.1 S1's helpers took a T-loop unmodified

All four of S1's extracted helpers are called, none is reimplemented, and **no helper signature
was changed** — the brief's escape hatch was not needed. They were built to take LP column
indices rather than assume a layout, and that is exactly what made a T-loop work on first
contact.

| family | how it is built here |
|---|---|
| nodal balance | `_balance_row(concat(gen_cols[t], discharge_cols[t]), concat(demand_cols[t], charge_cols[t]), total_fixed[t])` |
| PTDF flow limit | `_flow_limit_rows(ptdf, concat(gen_cols[t], discharge_cols[t]), concat(gen_bus, storage_bus), concat(demand_cols[t], charge_cols[t]), concat(elastic_bus, storage_bus), rating_mw, const[t])` |
| PWL epigraph | `_epigraph_rows(segments_by_gen, gen_cols[t], cost_col_of[t])` |
| PWL hypograph | `_hypograph_rows(demand_segments_by_load, demand_col_of[t], demand_val_col_of[t])` |

Storage joins the *same* two calls it belongs in rather than getting a family of its own: it
injects and withdraws at a bus like anything else, so it is an injection column in the balance
row and in every flow row. That is the whole of what "storage must appear in the PTDF flow rows"
required, and §4.4 proves the flow-row half is load-bearing rather than assumed.

The three new families are built through `_add_rows` via one small local helper, `_sparse_rows`,
which takes explicit `(column, coefficient)` pairs. `_dense_csr` was deliberately **not** reused
for them: it exists to preserve `dc_opf`'s dense structural-zero pattern (S1's report §1, "could
move the simplex's vertex choice on a degenerate problem"), and a ramp row touching 2 columns out
of hundreds has no such pattern to preserve.

### 2.2 A finding: research §2.2's column structure does not survive contact with the Hessian

Research §2.2 describes the variable vector as `T` per-period blocks concatenated, each block
being `[gen | demand | charge | discharge | soc]` **plus that period's own PWL free variables**.
That last part cannot be built as written. `dc_opf` documents its own constraint above the
Hessian: the quadratic-cost Hessian is passed **once, over a prefix of the columns, before any
free `cost_g`/`val_d` column exists** ("the same ordering already proven safe against later
addVars calls"). Interleaving each period's free variables inside its own block means the
quadratic-carrying columns are no longer a prefix.

Resolution: two tiers, not one block per period.

* **tier 1**, `T * (n_gen + n_demand + 3*n_storage)` columns, period-major, each period's block
  `[gen | demand | charge | discharge | soc]`. The Hessian covers exactly this tier.
* **tier 2**, `T * (n_pwl + n_demand_pwl)` columns, period-major, each block `[cost_g | val_d]`.

Same LP, and it buys something concrete: at `T = 1` with no storage this is column-for-column,
row-for-row and `addVars`/`changeColsCost`/`passHessian`/`addRows`-call-for-call the model
`dc_opf` itself builds. That is why the degeneracy tests in §5 can assert
`np.testing.assert_array_equal` rather than `assert_allclose`. Research §2.2's *row* structure
survived unchanged; it is only the column interleaving that had to move.

### 2.3 Row-order contract — defined here, not inherited

S1's report flags that `dc_opf` gets balance at row 0 and flows at `1..n_branch` *because it adds
them first*, and that S4 must re-establish the contract for itself. It is re-derived here as a
table in the module docstring, and dual extraction computes its offsets from that table:

| tier | family | row index |
|---|---|---|
| 1 | nodal balance, one per period | `t` |
| 2 | PTDF flow limit, per branch per period | `T + t*n_branch + k` |
| 3 | SoC balance, per unit per period | `T*(1 + n_branch) + t*n_storage + s` |
| 4 | `charge + discharge <= p_max` | after tier 3, `t*n_storage + s` |
| 5 | cyclic `soc[T-1] == soc_initial` | after tier 4, `s` |
| 6 | ramp coupling, per ramped gen per adjacent pair | after tier 5, `(t-1)*n_ramped + j` |
| 7-8 | PWL epigraph / hypograph, per period | last — internal encoding detail |

Tiers 7-8 stay last for the same reason they do in `dc_opf`: they encode the PWL curves and are
never part of `MultiperiodDuals`' shape. Every offset in the code is computed from the counts
above (`flow_base`, `soc_base`, `limit_base`, `cyclic_base`, `ramp_base`), so a family going
empty shifts nothing silently.

### 2.4 The three new families

**Ramp coupling.** One *two-sided* row per ramp-limited generator per adjacent pair,
`-ramp_down[g] <= p_g[t] - p_g[t-1] <= ramp_up[g]`. A generator with neither limit gets **no row
at all**; one with a single limit gets `±highspy.kHighsInf` on the other side — a genuinely
unbounded row, not a large finite bound. A limit of exactly `0` raises `ValueError`: it would
freeze the unit at its first-period dispatch for the whole horizon, which is MATPOWER's
unpopulated-column default rather than anything a caller declares (research §4.2, design T1).
`None`, `inf` and `nan` all mean unconstrained.

There is **no** ramp row from an initial dispatch into period 0. Neither the spec nor research
§2.2 specifies one (research is explicit: `n_gen × (T−1)` rows, `t = 1..T-1`), and inventing an
initial condition out of `Generator.p_mw` would be a modelling decision this slice has no mandate
for. Named here so a later wave adds it deliberately rather than discovering the gap.

**Storage SoC balance.** Two nonnegative power columns plus an explicit SoC column per unit per
period (tactical default T2; research §3.1's argument that a single signed column cannot carry
`+eta_c` against `-1/eta_d` in one linear row). The `t = 0` row anchors to
`soc_initial * energy_mwh`; `t >= 1` rows couple adjacent periods. A shared
`charge + discharge <= p_max_mw` row bounds the overlap (research §3.3 option 1) rather than a
binary banning it — §4.3 shows why banning it would be wrong and §4.4 shows the bounding row is
live.

**Cyclic end-of-horizon.** `soc[T-1] == soc_initial * energy_mwh`, one equality row per unit, not
configurable (scope answer 2).

### 2.5 Signature, and the argument shapes S5 inherits

```python
multiperiod_dc_opf(
    arr, cost_coeffs, n_periods, *,
    period_load_mw=None, ramp_up_mw=None, ramp_down_mw=None,
    pwl_costs=None, demand_bid_coeffs=None, demand_pwl_bids=None,
) -> MultiperiodSolution
```

* **No `options` parameter.** `dc_opf`'s exists and its body is `del options`; an empty options
  model here would be speculative. Flagged to the orchestrator: if S5 wants one for symmetry it
  is a two-line change.
* **Ramp limits are caller-supplied `(n_gen,)` arrays**, mirroring how `cost_coeffs` is
  caller-supplied. `NetworkArrays` carries no ramp fields — S3 was right that no *model* gap
  exists (the fields are on `Generator`, added by S2), but they are not in the arrays, so the
  array-level builder takes them the way it takes costs. S5 extracts them the way
  `gen_cost_coeffs` extracts costs.
* **`period_load_mw` is `(T, n_load)` MW** in `NetworkArrays.load_ids` order — i.e.
  `Period.load_p_mw` resolved to array positions. With `None` the fixed-load and flow-constant
  expressions are *literally* `dc_opf`'s (`arr.p_load_pu * base_mva`, then the same
  elastic-load subtraction), which is what makes the T=1 reduction bit-exact rather than
  ULP-close.
* **Elastic demand and PWL costs/bids are supported per period**, horizon-invariant (per-period
  offers/bids are the wave's own Not-Doing list). So AC-4 can use a bid-carrying fixture.
* Per-period LMPs: feed `duals.balance[t]` and `duals.flow_limit[t]` to M3's `lmp_decomposition`
  with `sol.ptdf`, unchanged.

---

## 3. TDD — RED before GREEN

The full hand derivations were written to `.bionic/tmp/m5-s4-progress.md` at T+25, **before any
line of `opf/multiperiod.py` existed**, and the tests were written against them next.

### 3.1 RED

```
$ uv run --no-sync pytest -q tests/unit/test_opf_multiperiod.py
tests\unit\test_opf_multiperiod.py:33: in <module>
    from mambo_power.opf.multiperiod import multiperiod_dc_opf
E   ModuleNotFoundError: No module named 'mambo_power.opf.multiperiod'
1 error in 13.17s
```

### 3.2 First GREEN run, and the one disagreement

```
$ uv run --no-sync pytest -q tests/unit/test_opf_multiperiod.py
1 failed, 24 passed in 1.73s
```

Every AC-2 and AC-3 number passed on the first run, unadjusted. The single failure was **my
test's expectation, not the builder**: I had asserted `storage_soc_bound[1,0] == 0`; HiGHS
returned `45.0`.

Per the brief I did not adjust the derivation to match the code — I re-derived the storage dual
set from the same KKT relation the ramp derivation uses:

```
charge[0]    interior -> 0 - (lambda_0*(-1) + y_soc0*(-eta_c)) = 0 -> y_soc0 = -10/0.9 = -11.1111
discharge[1] interior -> 0 - (lambda_1*(+1) + y_soc1*(1/eta_d)) = 0 -> y_soc1 = -0.9*50 = -45
soc[1]       interior -> 0 - (y_soc1 + y_cyclic) = 0              -> y_cyclic = +45
soc[0] at E_max       -> reduced cost = -(y_soc0 - y_soc1) = -33.8889
```

`soc[1] = 0` sits on the SoC column's own **lower bound** as well as being pinned by the cyclic
row, so a nonzero reduced cost there is correct and my expectation was simply wrong. The
corrected test asserts the derived duals instead — and `y_soc0 = -11.1111` is **exactly** the
`mu_soc = -11.111111` research §7.3's independent `scipy.optimize.linprog` probe reports for the
same instance, a second confirmation arriving from the dual side.

```
$ uv run --no-sync pytest -q tests/unit/test_opf_multiperiod.py
25 passed in 1.63s
```

(The final count is 33 after §4.6's two added fixtures.)

---

## 4. The evidence

### 4.1 AC-2 — hand-derived ramp optimum, binding period identified, dual recovered

2-bus network, `br12` unrated so no flow row can bind. `gcheap` c1=10, `[0,100]`,
`ramp_up = ramp_down = 20`; `gexp` c1=50, `[0,100]`, unconstrained. Load profile `[50, 100]`.

Derivation (recorded at T+25, before the builder existed): period 0's balance pins total
generation at 50 MW and `gexp >= 0`, so `gcheap[0] <= 50`; the objective drives it to exactly 50;
the ramp-up row then caps `gcheap[1]` at 70 and `gexp[1]` covers the rest.

| quantity | hand-derived | asserted |
|---|---|---|
| dispatch (period-major, `[gcheap, gexp]`) | `[[50, 0], [70, 30]]` | ✓ |
| objective | `10*50 + 10*70 + 50*30 = 2700` | ✓ |
| **binding period** | **t = 1**, ramp-up side | ✓ |
| ramp dual on `(t=1, gcheap)` | `-40.0` | ✓ |
| ramp dual on `gexp` | `0.0` (no row exists) | ✓ |
| balance duals | `[-30.0, 50.0]` | ✓ |
| `gexp` reduced cost at t=0 | `50 - (-30) = 80.0` | ✓ |
| flow duals | all `0.0` | ✓ |

The negative period-0 price is derived, not observed: one more MW of load at `t=0` lets `gcheap`
rise 1 MW there, relaxing the ramp row so it also rises 1 MW at `t=1` and displaces `gexp`. Net
system cost change `+10 - (50-10) = -30`. The HiGHS sign convention was pinned in advance from
`reduced_cost_j = c_j - sum_r y_r a_rj` and cross-checked against the existing `dc_opf` triangle
test (g2 interior at 30, `lambda = 10`, `PTDF[br12,b3] = -1/3` ⇒ `y_br12 = -120`, negative for a
row binding at its upper bound), which is why `-40` rather than `+40` was predicted.

Two further tests cover the family: relaxing the limit removes the constrained optimum entirely
(`[[50,0],[100,0]]`, cost 1500, ramp duals all zero), and reversing the profile makes the
**ramp-down** side of the same two-sided row bind (`[[70,30],[50,0]]`, cost 2700).

### 4.2 AC-3 — SoC balance, cyclic, and the overlap invariant

Five storage-bearing fixtures: `arbitrage`, `asymmetric-efficiency`, `congested`,
`cyclic-binding`, `overlap-required`.

* **SoC identity every period** — `test_soc_balance_identity_holds_every_period`, parametrized
  over all five. The expected trajectory is recomputed from the **entity** efficiencies
  (`s.efficiency_charge`, `s.efficiency_discharge`, `s.soc_initial * s.energy_mwh` read straight
  off `model.Storage`), not from anything the builder returns, so the check does not share a code
  path with the thing under test.
* **Cyclic met exactly** — `test_cyclic_end_of_horizon_soc_is_met_exactly`, all five, `atol=1e-9`.
* **`min(charge, discharge) ≈ 0`** — the four canonical fixtures, `< 1e-7`.

### 4.3 AC-3's paired positive case — the readback is capable of being non-zero

Research §3.2's construction, built as `_overlap_network`: a must-run generator
(`p_min = p_max = 65`) against a 50 MW load leaves a *fixed* 15 MW surplus every period with no
dispatch freedom at all, and the storage unit's 5 MWh cap cannot canonically absorb it.

```
$ uv run --no-sync python -c "...multiperiod_dc_opf(overlap_network) ..."
status Optimal
charge    [41.66666667 41.66666667]
discharge [26.66666667 26.66666667]
soc       [0. 0.]
min(c,d)  [26.66666667 26.66666667]
p_max=60 -> Infeasible
```

Two things are worth stating precisely.

1. **The readback is the same one the canonical fixtures return ~0 on** — literally
   `np.minimum(sol.storage_charge_mw, sol.storage_discharge_mw)`, the same expression, the same
   code path — and it returns 26.67 MW here. That is what discharges AC-3's absence-readback
   requirement.
2. **The numbers match research §3.2's independent `scipy.optimize.linprog` probe to 6 dp**
   (`charge=[41.666667, 41.666667]`, `discharge=[26.666667, 26.666667]`, `soc=[0,0]`), which the
   research recorded before this builder existed. The test asserts the *feasible-set* bound
   (`charge - discharge == 15` exactly, `min > 15`, `min <= 26.6667`) rather than a single vertex,
   because the LP is genuinely degenerate here — every `c0 in [30.5556, 41.6667]` with
   `c0 + c1 = 83.3333` is optimal, and all of them have `min > 0`. The assertion is therefore
   robust to which vertex HiGHS picks, and non-zero on all of them.

### 4.4 The absence readbacks the row families themselves needed

A committed negative control on the same network: with `p_max_mw = 60` the shared
`charge + discharge <= p_max` row caps `c` at 37.5, so `c0 + c1 <= 75 < 83.3333` and the problem
is **Infeasible** — derived before running, asserted by
`test_the_shared_power_limit_row_is_live`. That is the proof the power-limit row is load-bearing
rather than decorative.

Storage in the PTDF flow rows: `_congested_storage_network` rates `br12` at 40 MVA against a
50 MW load at `b2` in period 1, so at least 10 MW must be injected locally. Round-trip loss makes
more strictly worse, so `discharge[1] = 10` exactly, `charge[0] = 10/0.81 = 12.345679`,
`soc = [11.1111, 0]`, `g1 = [22.345679, 40]`, objective `623.45679` — all hand-derived, all
asserted, plus the `t=1` flow dual nonzero and the `t=0` one zero.

### 4.5 The analytic arbitrage optimum — the end-to-end check

Research §7's closed form, re-expressed so the two period prices are formed **by the builder's own
balance rows** rather than assumed: `gcheap` c1=10 capped at 40 MW is interior at `t=0`
(`lambda_0 = 10`) and at its cap at `t=1` where `gexp` is interior (`lambda_1 = 50`). Storage:
`P_max=20`, `E_max=15 MWh`, `soc_initial=0`, `eta_c = eta_d = 0.9`.

| quantity | research §7.2/§7.3 closed form | builder |
|---|---|---|
| `charge*` | `min(20, 15/0.9) = 16.6667` | ✓ |
| `discharge*` | `0.81 * 16.6667 = 13.5` | ✓ |
| `soc` | `[15.0, 0.0]` (E_max binds; cyclic met) | ✓ |
| `mu_soc` | `-11.111111` | `soc_balance[0] = -100/9` ✓ |
| system cost saving vs no storage | `profit* = 16.6667 * 30.5 = 508.3333` | `3600 - 3091.6667` ✓ |

The saving check is the strongest single statement in this slice: it is an end-to-end
reconciliation against a closed form derived and independently probed before the builder existed,
and it exercises the balance rows, the flow rows, both efficiencies, the SoC coupling and the
cyclic row at once.

### 4.6 A sabotage sweep, and the two powerless tests of my own that it caught

An S1-style sweep broke one row family at a time in an in-place copy and ran the matching test
(driver in scratchpad; it restores the file and asserts byte-equality afterwards). The **first**
run:

| row family broken | test | result |
|---|---|---|
| storage absent from PTDF flow rows | `test_storage_relieves_a_binding_flow_limit` | 1 failed |
| storage absent from balance row | `test_analytic_storage_arbitrage_optimum` | 1 failed |
| `eta_charge`/`eta_discharge` **swapped** in the SoC row | `test_analytic_storage_arbitrage_optimum` | **1 passed** |
| SoC `t-1` coupling term dropped | `test_soc_balance_identity_holds_every_period` | 1 failed |
| **cyclic row removed** | `test_cyclic_end_of_horizon_soc_is_met_exactly` | **3 passed** |
| shared power-limit row removed | `test_the_shared_power_limit_row_is_live` | 1 failed |
| ramp rows removed | `test_ramp_limit_binds_...` | 1 failed |

Two survivors, both my tests' fault, and both the *same* absence-readback failure AC-3's
tier-rationale warns about:

1. **Every fixture had `eta_c == eta_d`**, so swapping the two efficiencies is literally a no-op.
   Nothing in the module could tell the charge efficiency from the discharge efficiency.
2. **Every fixture's unconstrained optimum already ended at `soc_initial`** (research §7.1 derives
   its optimum with a *free* ending SoC and gets the same answer), so the cyclic row was satisfied
   for free and asserting it proved nothing.

Two new fixtures, hand-derived and written to the progress log before running:

* **`asymmetric-efficiency`** — `eta_c = 0.95`, `eta_d = 0.80`, otherwise the arbitrage shape.
  Closed form: `charge* = 15/0.95 = 300/19 = 15.789474`, `discharge* = 0.76 * 300/19 = 12.0`
  exactly, `soc = [15, 0]`, objective `3157.894737`, saving `8400/19 = 442.105263`. SoC duals
  `y_soc0 = -10/0.95 = -10.526316` and `y_soc1 = -0.8*50 = -40` put each efficiency in exactly
  one place. Swapping them would give `charge* = 18.75`, `discharge* = 14.25`.
* **`cyclic-binding`** — a half-charged 30 MWh unit (`soc_initial = 0.5`, `p_max = 20`) under the
  same `[10, 50]` price structure. *With* the row: charge to the 30 MWh cap, discharge 13.5, end
  at 15 = `soc_initial`, objective `3091.6667`, cyclic dual **+45.0** (derived two independent
  ways — `d(cost)/d(rhs)` and the `soc[1]`-interior reduced-cost relation — before running).
  *Without* the row the LP additionally drains its initial 15 MWh, hits its 20 MW power cap and
  ends at `30 - 20/0.9 = 7.7778`.

Both fixtures passed on their first solver run, and both were added to the AC-3 invariant sweeps.
Re-run of the sweep:

```
| storage absent from the PTDF flow rows | test_storage_relieves_a_binding_flow_limit | 1 failed |
| storage absent from the balance row | test_analytic_storage_arbitrage_optimum | 1 failed |
| charge/discharge efficiencies swapped in the SoC row | test_charge_and_discharge_efficiencies_... | 1 failed |
| SoC rows not coupled across periods (t-1 term dropped) | test_soc_balance_identity_holds_every_period | 1 failed, 4 passed |
| cyclic row removed | test_cyclic_row_forces_the_unit_back_to_its_starting_energy | 1 failed |
| shared power-limit row removed | test_the_shared_power_limit_row_is_live | 1 failed |
| ramp rows removed | test_ramp_limit_binds_and_reproduces_the_hand_derived_dispatch | 1 failed |
restored: True
```

**7 of 7 go red.**

---

## 5. T=1 reduces to `dc_opf` — exactly

Not this slice's AC (AC-4 is S5's, at market level), but the substrate has to support it and the
two-tier column layout (§2.2) was chosen to make it true, so it is proven here:

* `test_single_period_matches_dc_opf_on_a_hand_built_network`
* `test_single_period_matches_dc_opf_on_a_real_fixture[case14]`, `[case30]` — via
  `gen_cost_coeffs`, so genuine quadratic and PWL fixture costs are in play.

Both use `np.testing.assert_array_equal` — **exact**, not `allclose` — on dispatch, balance dual,
flow duals and generator bound duals, plus `==` on `objective_cost`. Both pass.

---

## 6. Gates

```
$ uv run --no-sync pytest -q -p no:cacheprovider
725 passed, 10 warnings in 271.53s (0:04:31)
```

725 = **692** briefed baseline + **33** new tests, all in the one new file. Reconciles exactly.

**Zero pre-existing tests modified**, proven by content rather than assertion:

```
$ git diff --stat -- tests/          # before commit
(empty)

$ git status --short                 # before commit
 M src/mambo_power/opf/__init__.py
?? src/mambo_power/opf/multiperiod.py
?? tests/unit/test_opf_multiperiod.py
```

Nothing under `tests/` differs from `HEAD` by a byte; the only test content in the commit is a new
file. The one modified tracked file is `opf/__init__.py` (§1.1).

```
$ uv run --no-sync ruff check .
All checks passed!

$ uv run --no-sync ruff format --check .
143 files already formatted

$ uv run --no-sync mypy
Success: no issues found in 44 source files
```

All three are **repo-wide**, which is meaningful this time because the tree was clean and this
slice was the only one running — the isolation problem S1 flagged (its §5) did not recur.

`mypy` was not free: `_sparse_rows`'s bound parameters were first typed `Sequence[float]` and
mypy caught six call sites passing `ndarray`, which is how the coupling families actually build
their bounds. Widened to `Sequence[float] | FloatArray`.

---

## 7. Flags and carry-overs

* **FLAG (S5, low)** — `multiperiod_dc_opf` takes **no `options` parameter**, deliberately
  (§2.5). If `market/multiperiod.py` wants one for symmetry with `dc_opf(arr, coeffs, options)`,
  it is a two-line change and should be made once, not guessed at twice.
* **FLAG (S8, low)** — the three new public symbols are reachable through `mambo_power.opf`, so
  `test_api_docs_coverage.py` is green without a docs edit. If S8 wants a dedicated
  `::: mambo_power.opf.multiperiod` block on `docs/api/opf.md`, nothing here prevents it.
* **Named gap, not a defect** — there is no ramp constraint from an initial dispatch into period
  0 (§2.4). Neither the spec nor research §2.2 asks for one. A later wave should add it
  deliberately.
* **Research correction** — §2.2's per-period column blocks with interleaved PWL free variables
  cannot be built as described against `dc_opf`'s Hessian-ordering constraint (§2.2 above). The
  row structure it describes survived unchanged.
* **Storage is costless in the objective.** `model.Storage` carries no cost field, so a unit's
  only economic footprint is the round-trip loss it imposes on generation. Documented on
  `MultiperiodSolution.objective_cost`. If M6/M7 want storage bids, that is a model change, not a
  builder change.
* **Degeneracy is real in the overlap case** and the test is written for it (§4.3) — a later
  reader should not "tighten" that assertion to a single vertex.
* No behaviour change was found in `dc_opf`, and nothing in the existing suite had to be
  reinterpreted to stay green.
