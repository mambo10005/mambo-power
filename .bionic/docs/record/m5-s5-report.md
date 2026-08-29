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

# M5 S5 — market-multiperiod (W5, AC-4, AC-5)

Slice S5 `market-multiperiod`. Role: senior-implementor. Worktree
`C:\Claude Projects\mambo-power-m5`, branch `wave/05-multiperiod`, base `d93c448` (S1 `fbab76d`
+ S2 `7afa9c5` + S3 `d0031cb` + S4 `d93c448` all landed). Commit **`faba273`** —
`feat(m5/S5): market.multiperiod — per-period LMPs, storage settlement, horizon totals`.
Not pushed.

**AC-4 and AC-5 both hold, and the settlement identity closes per period.** Storage turned out to
be a genuine third settlement participant: without its charge payment and discharge revenue the
identity is wrong by exactly its net revenue, which on the AC-5 fixture is −166.67 $/h in one
period and +675 $/h in the other. Both halves are asserted.

A second finding, smaller but worth the orchestrator's attention: **M4's `market.nodal` statement
of the identity omits two terms and is correct only because none of its fixtures carry them**
(§4.4).

Every factual claim below carries the command that produced it and that command's output, or the
explicit label `unverified`.

---

## 1. What changed

| file | status | lines |
|---|---|---|
| `src/mambo_power/market/multiperiod.py` | new | 328 |
| `src/mambo_power/results/multiperiod.py` | new | 184 |
| `tests/unit/test_market_multiperiod.py` | new | 762 |
| `src/mambo_power/market/__init__.py` | modified | +18 / −4 |
| `src/mambo_power/market/nodal.py` | modified | +15 / −3 |
| `src/mambo_power/results/__init__.py` | modified | +10 / −0 |
| `src/mambo_power/opf/__init__.py` | modified | +1 / −1 |

```
$ git show --stat faba273 | tail -9
 src/mambo_power/market/__init__.py     |  22 +-
 src/mambo_power/market/multiperiod.py  | 328 ++++++++++++++
 src/mambo_power/market/nodal.py        |  18 +-
 src/mambo_power/opf/__init__.py        |   2 +-
 src/mambo_power/results/__init__.py    |  10 +
 src/mambo_power/results/multiperiod.py | 184 ++++++++
 tests/unit/test_market_multiperiod.py  | 762 +++++++++++++++++++++++++++++++++
 7 files changed, 1318 insertions(+), 8 deletions(-)
```

Nothing under `jobs/`, `model/` or `numerics/` was touched, as scoped. `opf/multiperiod.py` and
`opf/dc_opf.py` have **zero diff**.

### 1.1 The two edits to tracked files outside `market/multiperiod.py`'s own module, and why

**`market/nodal.py`: `_load_bid_coeffs` → public `load_bid_coeffs`.** A pure rename plus a
docstring paragraph; no behaviour change. `solve_multiperiod` needs the identical demand-bid
extraction, and the alternative was a second copy — the exact Duplication FLAG M4's Step-6 review
raised and M4/R2 resolved by making `gen_cost_coeffs` public. This is the same move applied to
the demand side, and the brief's own escape hatch ("if you must touch it for a shared helper,
prove nodal's own tests unchanged") covers it. The proof is §6's empty `git diff -- tests/`:
`tests/unit/test_market_nodal.py` is byte-identical to `HEAD`, so nodal's behaviour is pinned by
exactly the assertions M4 wrote.

**`opf/__init__.py`: one docstring word.** `gen_cost_coeffs`'s docstring cross-references
`:func:`mambo_power.market.nodal._load_bid_coeffs``, which the rename would leave dangling. The
diff is literally one line:

```
$ git diff HEAD~1 -- src/mambo_power/opf/__init__.py
-    (:func:`mambo_power.market.nodal._load_bid_coeffs`) has no prior-wave analog to share.
+    (:func:`mambo_power.market.nodal.load_bid_coeffs`) has no prior-wave analog to share.
```

`opf/` is outside this slice's scope, so this was kept to the minimum needed to avoid a dangling
reference. **FLAG (fold, cosmetic)**: the sentence's *content* is now dated — "has no prior-wave
analog to share" was true of M4 and is no longer, since `market.multiperiod` shares it. Left
alone rather than expanded, since rewriting `opf/`'s prose is not this slice's mandate.

---

## 2. Design

### 2.1 The result shape, and the one place it is not a straight mirror

`MarketMultiperiodResult{provenance, status, message, n_periods, periods, objective_cost, +5
horizon totals}` over `MarketPeriodResult{period, generators, loads, buses, storage, +5
settlement fields}`. `LoadDispatchResult` and `BusLmpResult` are reused **verbatim** (ADR-006).

Two new row types, and the line between them was drawn deliberately:

* **`GenPeriodDispatchResult(GenDispatchResult)`** adds one field, `ramp_dual` — the dual of the
  ramp row coupling the *previous* period to this one, `0.0` in period 0 and for a generator with
  no ramp row at all. It subclasses rather than replaces, so `id`/`bus`/`p_mw`/`bound_dual` mean
  what they mean in a single-period result. Included even though W5's list does not name it,
  because it is a *per-period* quantity that belongs on the per-period generator row, and without
  it a ramp-constrained period's price is unexplainable from the result alone.
* **`StorageDispatchResult`** is new: `charge_mw`, `discharge_mw`, `soc_mwh`, plus the duals of
  the three storage row families (`soc_dual`, `energy_bound_dual`, `power_limit_dual`).

**Deliberately not included: the cyclic dual.** `MultiperiodDuals.cyclic` is `(n_storage,)` — a
horizon-level quantity, not a per-period one, so exposing it would need a fourth row type at a
level nothing else occupies. W5 does not ask for it and the array layer already reports it.
**FLAG (M6/M7, low)**: a user asking "what does the cyclic end-of-horizon condition cost me?"
currently has to drop to `multiperiod_dc_opf`.

### 2.2 A period-less scenario is the degenerate end of the same path, not a special case

`scenario.periods is None` clears `T = 1` with `period_load_mw=None`. That is not a shortcut —
it is what makes AC-4 exact rather than close, and §3.2 shows the alternative is measurably a
different LP.

### 2.3 What is extracted here, and what is imported

| thing | source | shared or new |
|---|---|---|
| generator costs | `opf.gen_cost_coeffs` | imported verbatim (M4/R2's public helper) |
| load bids | `market.nodal.load_bid_coeffs` | imported verbatim (promoted here, §1.1) |
| per-period fixed load | `Period.load_p_mw` → `(T, n_load)` in `load_ids` order | new, `_period_load_mw` |
| ramp limits | `Generator.ramp_up_mw`/`ramp_down_mw` → `(n_gen,)` | new, `_ramp_limits` |
| per-period LMPs | `opf.dc_opf.lmp_decomposition` on period `t`'s dual slice | imported verbatim (M3's) |

`_period_load_mw` implements `Period`'s own contract — an *override*, so a load the dict omits
keeps its own `Load.p_mw` — and skips an id `NetworkArrays` dropped (out of service, or on a bus
that is), since there is no column for it to reach. `_ramp_limits` maps `None` to `inf`, which
the builder reads as unconstrained and for which it builds no row.

`MarketMultiperiodOptions` is an empty frozen model, taken up on S4's FLAG: the array builder has
no `options` parameter by design, so this is the one place multiperiod options can live.

---

## 3. AC-4 — degeneracy, and a measurement that changed the design

### 3.1 Exact, on a real fixture

`test_ac4_period_less_scenario_reproduces_market_nodal_exactly[case14]`, `[case30]` —
`rated_network(matpower.load(...))`, cleared once through `solve_nodal` and once through
`solve_multiperiod`, compared with `np.testing.assert_array_equal` (**exact**, not `allclose`) on:

* every generator's `p_mw` and `bound_dual`
* every load's `p_mw` (and, in the bid-carrying variant, `bound_dual`)
* every bus's `lmp`, `energy` and `congestion`

plus plain `==` on `total_load_payment`, `total_generator_receipts` and `congestion_rent`, at both
the period and the horizon level.

`test_ac4_exactness_holds_with_elastic_bids_in_play` repeats it on `with_bids(case14)` so the
*elastic demand* columns are in play, not only the fixed-load path.

### 3.2 The finding: the two fixed-load routes are not the same LP

`opf/multiperiod.py` computes the period's bus-aggregate fixed load two ways — `arr.p_load_pu *
base_mva` when `period_load_mw is None` (a `/base` then `*base` round trip, `dc_opf`'s literal
expression) and `bincount(load_bus, period_load_mw[t])` otherwise. Measured directly:

```
$ uv run --no-sync python -c "...np.array_equal(direct, roundtrip)..."
case14      bitwise equal: False  max|d| 1.7763568394002505e-15  ndiff 2
case30      bitwise equal: False  max|d| 4.440892098500626e-16   ndiff 2
case_ieee30 bitwise equal: False  max|d| 4.440892098500626e-16   ndiff 2
case57      bitwise equal: False  max|d| 7.105427357601002e-15   ndiff 6
case118     bitwise equal: False  max|d| 1.4210854715202004e-14  ndiff 7
case300     bitwise equal: False  max|d| 5.684341886080802e-14   ndiff 37
```

So the two routes hand HiGHS different LP data on **every** fixture. The *answers* nonetheless
come back bit-identical on case14 and case30 — `test_ac4_an_explicit_single_period_also_
reproduces_market_nodal_exactly` asserts that with `assert_array_equal` too, and its docstring
records that this is measured rather than guaranteed. `solve_multiperiod` therefore routes a
period-less scenario through `None`, because only that route's exactness is structural. A future
fixture where the answers diverged would land that test on `assert_allclose`, and that would be
information rather than a regression.

### 3.3 The second half — `market.nodal` unchanged

Proved two ways. By content: `git diff --stat -- tests/` is empty (§6), so
`tests/unit/test_market_nodal.py` is byte-identical to `HEAD` and nodal is pinned by exactly M4's
own assertions, all green in the 747. By behaviour:
`test_ac4_market_nodal_ignores_periods_entirely` clears the same network through `solve_nodal`
with `periods=None` and with a 3-period profile and asserts the two `model_dump(exclude=
{"provenance"})` are equal — nodal never silently starts reading period data.

---

## 4. The settlement identity — derived, then proved per period

### 4.1 The derivation, and why it is per-period

Written to `.bionic/tmp/m5-s5-progress.md` at T+25, before any line of `market/multiperiod.py`
existed. Exactly three facts are used:

1. **balance row `t`**: `Σ_g p_g + Σ_s (d_s − c_s) − Σ_{d∈E} p_d = F_t`, with
   `F_t = Σ_n (fixed load_n + g_shunt_n)`. Hence `Σ_n inj_n = 0` exactly, where
   `inj_n = Σ_{g@n} p_g + Σ_{s@n}(d_s − c_s) − Σ_{d@n} p_d − g_shunt_n`.
2. **flow row `(t,k)`**: the row activity is `PTDF[k,:] @ (variable injections)` and
   `const_kt = pf_shift_k − PTDF[k,:] @ (p_load_t + g_shunt)`, so `f_kt = PTDF[k,:] @ inj_t +
   pf_shift_k`.
3. **`LMP_nt = λ_t + Σ_k μ_kt·PTDF[k,n]`** (`lmp_decomposition`, M3's, unchanged).

Then `Σ_n LMP_nt·inj_nt = λ_t·0 + Σ_k μ_kt·(f_kt − pf_shift_k)`, and rearranging gives

> **`load_payment + storage_charge_payment − generator_receipts − storage_discharge_revenue
> = −Σ_k μ_kt·f_kt + Σ_k μ_kt·pf_shift_k − Σ_n LMP_nt·g_shunt_n`**

**No ramp row, no SoC row and no cyclic row appears anywhere in that derivation.** That is the
reason the identity holds *per period* even though the LP is horizon-coupled — the coupling rows
constrain which dispatch is optimal, but they contribute nothing to the price-times-quantity
accounting within a period.

### 4.2 Storage's settlement terms

A storage unit injects and withdraws at a bus, so it is a settlement participant like any other:
it **pays** `LMP·charge_mw` and is **paid** `LMP·discharge_mw`. Leaving it unsettled leaves the
identity wrong by exactly `Σ_s LMP·(d_s − c_s)` — which is the whole of the unit's arbitrage
revenue, and is non-zero in every period the unit moves.

`MarketPeriodResult` therefore carries `total_storage_charge_payment` and
`total_storage_discharge_revenue` as their own fields, and `congestion_rent` is
`(load payment + charge payment) − (generator receipts + discharge revenue)`.

### 4.3 The right side, computed independently of the left

M4's AC-4 test is the model, and the same discipline is used. `_identity_rhs` builds the
right-hand side from:

* a **separate array-level `multiperiod_dc_opf` call** — not `solve_multiperiod`'s solution;
* a **PTDF recomputed** via `numerics.ptdf.ptdf(arr)`, deliberately not `sol.ptdf`;
* bus injections assembled from that solve's dispatch/storage arrays and the period load matrix.

The left side is `solve_multiperiod`'s own payment/receipt subtraction off its result rows. The
two sides share no arithmetic — one is `Σ LMP·q`, the other is `Σ μ·f` — so the assertion is a
proof of the identity rather than a restatement of a subtraction just performed.

Four committed tests assert it: on the arbitrage horizon, on a 3-period congested-storage
horizon, on the shunt network (§4.4), and on case30 with rated branches, quadratic fixture costs,
a non-uniform 4-period profile and a storage unit.

### 4.4 The finding: M4's form of the identity omits two terms

M4 proved `load payment − generator receipts = −Σ_k μ_k·flow_k`. That is the special case where
there is no phase shifter and no bus shunt conductance. Both are real network elements that
withdraw real power and are settled by nobody, so both appear in the general form. Measured
across every fixture this repository ships:

```
$ uv run --no-sync python -c "...max|g_shunt_pu| ... max|pf_shift| ..."
case14      max|g_shunt_pu| 0.0                     max|pf_shift| 0.0
case30      max|g_shunt_pu| 0.0                     max|pf_shift| 0.0
case_ieee30 max|g_shunt_pu| 0.0                     max|pf_shift| 0.0
case57      max|g_shunt_pu| 0.0                     max|pf_shift| 0.0
case118     max|g_shunt_pu| 0.0                     max|pf_shift| 0.0
case300     max|g_shunt_pu| 0.0014000000000000002   max|pf_shift| 0.0
```

So M4's statement was fixture-lucky rather than general. **This is not a defect in M4's tested
behaviour** — its own AC-4 network has neither element, and the assertion it makes is true there.
It is a docstring that reads more general than it is (`market/nodal.py`'s module docstring and
`MarketNodalResult.congestion_rent`'s field description). `results/multiperiod.py` states the
general form, and `MarketPeriodResult.congestion_rent` is documented as the operator's
merchandising surplus, which equals congestion rent *proper* only where nothing is left
unsettled. **FLAG (fold / M6, low)**: nodal's own docstring could be narrowed to match.

The shunt term is **not** decoration here:
`test_the_shunt_term_of_the_identity_is_load_bearing` puts a 5 MW shunt at `b2` behind a 40 MVA
rating over 3 periods, asserts the identity closes with the term, and asserts that dropping it
breaks the identity by exactly `−5·LMP_b2` in every period (`min|gap| > 1.0` asserted, so it is
not a rounding-scale effect).

---

## 5. AC-5 — the analytic arbitrage optimum, three independent confirmations

Research §7.1/§7.3's instance, promoted to the market layer: built through `Generator.cost`,
`Storage` and `Scenario.periods` so `solve_multiperiod` is what is under test, with the two period
prices formed by the builder's own balance rows rather than assumed. Every number below was
written into `.bionic/tmp/m5-s5-progress.md` **before** the module existed, and every one passed
unadjusted on the first solver run.

| quantity | research §7.2/§7.3 closed form | `solve_multiperiod` |
|---|---|---|
| `charge*` | `min(20, 15/0.9) = 50/3 = 16.666667` | ✓ |
| `discharge*` | `0.81 × 50/3 = 13.5` | ✓ |
| `soc` | `[15.0, 0.0]` | ✓ |
| dispatch | `[[110/3, 0], [40, 46.5]]` | ✓ |
| `objective_cost` | `3091.666667` | ✓ |
| LMPs (unrated branch, so uniform) | `[[10, 10], [50, 50]]` | ✓ |
| **cost saving vs no storage** | `profit* = 50/3 × 30.5 = 508.333333` | ✓ |
| **`mu_soc`** | `−11.111111` (research §7.3's scipy LP) | `soc_dual[0] = −100/9` ✓ |

Three routes to `profit*`, and they are genuinely independent of each other:

1. **Cost difference** — `test_ac5_horizon_saving_equals_the_closed_form_profit` clears the same
   scenario with the storage unit removed (`3600.0`) and subtracts.
2. **Settlement** — `test_ac5_settlement_reproduces_the_closed_form_profit_independently` reaches
   the same figure from prices and quantities alone: discharge revenue `675.0` minus charge
   payment `500/3`, per-period figures also asserted.
3. **Duals** — `soc_dual = [−100/9, −45]` and `energy_bound_dual[0] = −(y_soc0 − y_soc1)`, the
   `−11.111111` being exactly what research §7.3's independent `scipy.optimize.linprog` probe
   reported for this instance before any of this existed.

---

## 6. TDD, and the powerless tests caught

### 6.1 RED

Derivations and expected numbers written to the progress log at T+25; the whole test file written
against them next; module created only after.

```
$ uv run --no-sync pytest -q -p no:cacheprovider tests/unit/test_market_multiperiod.py
tests\unit\test_market_multiperiod.py:29: in <module>
    from mambo_power.market.multiperiod import MarketMultiperiodOptions, solve_multiperiod
E   ModuleNotFoundError: No module named 'mambo_power.market.multiperiod'
1 error in 19.05s
```

### 6.2 First GREEN, and the guard that fired

```
$ uv run --no-sync pytest -q -p no:cacheprovider tests/unit/test_market_multiperiod.py
1 failed, 17 passed in 19.76s
```

The single failure was **my own powerless-test guard**, not the module:

```
E       AssertionError: per-period rents not distinct: [0.0, 1.8189894035458565e-12, 0.0, 0.0]
```

case14's rated base case has no binding branch even under a moving profile, so the real-fixture
identity test would have read `0 == 0` four times over and proved nothing. Moved to case30, with
the storage unit placed at the bus whose LMP carries the largest congestion component in a
storage-free probe, and the guard widened to also require that dropping storage's settlement
terms visibly changes the answer. Every AC-4 exactness assertion and every AC-5 number passed
unadjusted on that first run.

### 6.3 The sabotage sweep — 13 of 14 red

Driver in scratchpad: patches `market/multiperiod.py` in place one behaviour at a time, runs the
test meant to catch it, restores, and compares sha256.

| behaviour broken | result |
|---|---|
| period load overrides ignored (every period uses `Load.p_mw`) | 1 failed |
| omitted load falls back to `0.0` instead of its own `Load.p_mw` | 1 failed |
| ramp fields not read off the model (all unconstrained) | 1 failed |
| `ramp_up_mw` and `ramp_down_mw` transposed | 1 failed |
| every period priced with period 0's duals | 1 failed |
| ramp dual read from row `t` instead of row `t−1` | 1 failed |
| storage charge/discharge transposed in the result rows | 1 failed |
| storage charge payment dropped from the settlement | 1 failed |
| storage discharge revenue dropped from the settlement | 1 failed |
| storage settled on the wrong side of the identity | 1 failed |
| non-bid load reported at `Load.p_mw` instead of this period's demand | 1 failed |
| elastic-load dispatch ignored (bid loads reported as fixed) | 1 failed |
| horizon totals not summed over periods (period 0 only) | 1 failed |
| **`periods=None` routed through a materialised profile instead of `None`** | **2 passed** |
| | `restored byte-identical: True` |

**The one survivor is a finding, not a hole.** It is §3.2 restated from the other side: on case14
and case30 the two routes give identical answers, so no test can distinguish them — and the
committed test says so in its docstring rather than pretending otherwise. The `None` route is
kept because its exactness is structural and the other's is not.

### 6.4 The powerless test the sweep caught before it ran

Preparing the transposition sabotage exposed that my ramp fixture had
`ramp_up_mw == ramp_down_mw == 20`, so swapping the two fields was a **literal no-op** — the same
class of defect S4's own sweep caught twice. Added
`test_ramp_up_and_ramp_down_are_not_interchangeable`: `ramp_up = 60` (slack) against
`ramp_down = 20` (binding), profile `[100, 50]`, hand-derived before running —

* `t=1` balance pins total at 50 and `gexp ≥ 0`, so `gcheap[1] ≤ 50`;
* the ramp-*down* row `gcheap[0] − gcheap[1] ≤ 20` caps `gcheap[0]` at 70, so `gexp[0] = 30`;
* dispatch `[[70, 30], [50, 0]]`, cost `10·70 + 50·30 + 10·50 = 2700`;
* duals: `gexp[0]` interior ⇒ `λ_0 = 50`; `gcheap[0]` interior ⇒ `y_ramp = +40` (**positive** —
  the ramp-down side, the mirror of S4's AC-2 `−40`); `gcheap[1]` interior ⇒ `λ_1 = −30`.

Transposed, the answer would be `gcheap = [100, 50]` and cost `1500`. Passed on its first solver
run, and the transposition sabotage then goes red.

---

## 7. Gates

```
$ uv run --no-sync pytest -q -p no:cacheprovider
747 passed, 10 warnings in 858.70s (0:14:18)
```

747 = **725** briefed baseline + **22** new tests, all in the one new file. Reconciles exactly.
Run at the exact tree state committed as `faba273`. An earlier run of the same suite, before the
last two edits, also reported `747 passed ... in 566.83s`. The 858 s wall time is **contention,
not a regression** — the orchestrator's own verification `pytest` and an `examples/` run were live
alongside it (confirmed by `Get-CimInstance Win32_Process`); standalone the baseline suite is
~165 s.

**Zero pre-existing tests modified**, proven by content rather than assertion:

```
$ git diff --stat -- tests/          # before commit
(empty)
```

Nothing under `tests/` differed from `HEAD` by a byte; the only test content in the commit is one
new file. This is also the proof §1.1 owes for the `load_bid_coeffs` promotion —
`tests/unit/test_market_nodal.py` is untouched.

```
$ uv run --no-sync ruff check .
All checks passed!

$ uv run --no-sync ruff format --check .
146 files already formatted

$ uv run --no-sync mypy
Success: no issues found in 46 source files
```

All three repo-wide, and all three re-run **after** the final source edit so no claim post-dates
its evidence.

Docs coverage needed no edit: the new public symbols are re-exported from `mambo_power.market`
and `mambo_power.results`, both of which already carry `:::` directives, so
`test_api_docs_coverage.py` is green inside the 747 without touching `docs/`.

---

## 8. Flags and carry-overs

* **FLAG (fold / M6, low)** — `market/nodal.py`'s module docstring and
  `MarketNodalResult.congestion_rent`'s field description state the settlement identity in a form
  that omits the `pf_shift` and `g_shunt` terms (§4.4). True on M4's fixtures, not true in
  general, and case300 has a non-zero `g_shunt`. `results/multiperiod.py` states the general
  form; nodal's could be narrowed to match. No behaviour change either way.
* **FLAG (fold, cosmetic)** — `opf/__init__.py:78` now says the demand-bid-side mirror "has no
  prior-wave analog to share", which stopped being true when `market.multiperiod` started sharing
  it (§1.1). Left as-is because `opf/` is outside this slice's scope.
* **FLAG (S8, low)** — `market.multiperiod`'s and `results.multiperiod`'s public symbols are
  reachable through `mambo_power.market` / `mambo_power.results`, so the coverage test is green
  without a docs edit. If S8 wants dedicated `::: mambo_power.market.multiperiod` and
  `::: mambo_power.results.multiperiod` blocks for page structure, nothing here prevents it.
  `mkdocs build --strict` was **not** run here (AC-8 is S8's gate) — `unverified`.
* **FLAG (S7, informational)** — `MarketMultiperiodOptions` exists as an empty frozen model,
  taking up S4's FLAG, so a `market.multiperiod` `KindSpec` has a stable options model to
  validate against. `solve_multiperiod(scenario, options=None)` matches `solve_nodal`'s shape, so
  the uniform `Runner` protocol S7 is widening to should take it unchanged.
* **Named gap, not a defect** — the cyclic end-of-horizon dual is not exposed at the market layer
  (§2.1). It is horizon-level rather than per-period and W5 does not ask for it; it remains
  available from `multiperiod_dc_opf`.
* **Measured, not structural** — an explicit single `Period` restating each load's own `p_mw`
  produces bit-identical results to `periods=None` on case14 and case30, but the underlying LP
  data differs by ~1e-15 MW on every fixture (§3.2). A later wave should not assume the
  materialised route is interchangeable.
* **Storage remains costless in the objective**, carried forward from S4: `model.Storage` has no
  cost field, so a unit's only economic footprint is the round-trip loss it imposes on
  generation. It *does* now have a settlement footprint, which is a different thing and is
  documented on `MarketPeriodResult`.
* No defect was found in `opf/multiperiod.py`, `opf/dc_opf.py` or `market/nodal.py`, and nothing
  in the existing suite had to be reinterpreted to stay green.
