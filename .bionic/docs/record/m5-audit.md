# M5 audit — Step 5 exit gate

Auditor, wave M5 (`multiperiod`), head `13aff40` on `wave/05-multiperiod`, worktree
`C:\Claude Projects\mambo-power-m5`. Dispatched 2026-08-26.

Every claim below carries the command that proves it and its output, or the explicit label
`unverified`. The live worktree was never written to: `git status --porcelain` is empty and
`git rev-parse HEAD` is `13aff400b18379a9e4c7507cac48e2bb73801dc4` at the close of the audit.
All sabotage was done in isolated `git archive` extractions under the scratchpad, with the
loaded module's `__file__` printed on every run and full restoration verified by `diff -rq`
against a fresh archive.

## Verdicts

| AC | verdict | one-line reason |
|---|---|---|
| AC-1 | **CONFIRMED** | M4's complete unmodified 654-test suite passes against (M4 tree + M5 `dc_opf.py` only); `dc_opf`'s full float output is byte-identical across `e88752c` / swap / `13aff40` |
| AC-2 | **CONFIRMED** | hand optimum and all four duals re-derived from scratch by the auditor; dropping the ramp rows → 5 red, transposing up/down → 2 red |
| AC-3 | **CONFIRMED** | pairing is genuine — same helper, same readback expression, positive case >15 MW, `Infeasible` negative control; efficiency transposition → 2 red, cyclic-row deletion → 4 red. One coverage shortfall recorded below |
| AC-4 | **CONFIRMED** | `periods=None` route bit-exact on all 6 fixtures × 2 shapes; `market.nodal`'s full result byte-identical to `e88752c` across 15 solves |
| AC-5 | **CONFIRMED** | closed form re-derived independently; every value confirmed (`c*`=50/3, `d*`=13.5, `soc[0]`=15, profit 508.333, duals 10/50) |
| AC-6 | **CONFIRMED** | tolerances never moved (single commit); every residual re-measured by zeroing all five constants — all five documented figures reproduce, margins 24×–2300× |
| AC-7 | **CONFIRMED** | `KINDS` == 6; never raises across 7 adversarial JSON inputs, both mutation paths and infeasibility; all five prior kinds still take the M4 form |
| AC-8 | **CONFIRMED** | `mkdocs build --strict` exit 0 (34.05 s); coverage test untouched across the **whole** wave, not just `HEAD~1`; example 10 exit 0, snippet-embedded, CI globs `examples/*.py` |

Stack health, re-run by the auditor at the head:

```
$ uv run --no-sync pytest -q
800 passed, 10 warnings in 130.29s (0:02:10)          [exit 0]

$ uv run --no-sync ruff check .          -> All checks passed!
$ uv run --no-sync ruff format --check . -> 154 files already formatted
$ uv run --no-sync mypy                  -> Success: no issues found in 46 source files
$ uv run --no-sync mkdocs build --strict -> Documentation built in 34.05 seconds  [exit 0]
```

---

## AC-1 — the shared-core extraction is behaviour-preserving

**CONFIRMED.** The plan's own evidence for the "zero test edits" half was that S1's commit
contains no test file. That is a weaker claim than the criterion: it proves S1 did not edit a
test *at the time of S1*, not that the extraction preserves behaviour. I proved the stronger
thing two independent ways.

### Scope: `dc_opf.py` was touched exactly once in the whole wave

```
$ git show --name-only --format="" fbab76d
src/mambo_power/opf/dc_opf.py

$ git log --oneline e88752c..13aff40 -- src/mambo_power/opf/dc_opf.py
fbab76d refactor(m5/S1): extract dc_opf's row families into internal helpers
```

So the entire `dc_opf` change in M5 *is* the extraction — nothing later in the wave amended it.

### Proof 1 — M4's own 654 tests, unmodified, against M5's `dc_opf.py`

I built an isolation tree my own way: `git archive e88752c` extracted whole, then M5's
`dc_opf.py` blob written over the one file.

```
$ git archive e88752c | tar -x -C $SCR/ac1
$ git show 13aff40:src/mambo_power/opf/dc_opf.py > $SCR/ac1/src/mambo_power/opf/dc_opf.py
$ diff -rq $SCR/ac1_ref $SCR/ac1        # ac1_ref = pristine e88752c archive
Files .../ac1_ref/src/mambo_power/opf/dc_opf.py and .../ac1/src/mambo_power/opf/dc_opf.py differ
```

Exactly one file differs. Module resolution proven rather than assumed:

```
$ cd $SCR/ac1 && PYTHONPATH=$SCR/ac1/src python -c "import importlib; \
    print(importlib.import_module('mambo_power.opf.dc_opf').__file__)"
C:\...\scratchpad\ac1\src\mambo_power\opf\dc_opf.py
```

Then M4's complete, untouched test suite:

```
$ cd $SCR/ac1 && PYTHONPATH=$SCR/ac1/src python -m pytest -q -p no:cacheprovider
654 passed, 10 warnings in 129.17s (0:02:09)          [exit 0]
```

654 is exactly M4's close baseline. Every test M4 shipped — including all 196 parity tests
against MATPOWER, pandapower and PyPSA — passes against M5's extracted `dc_opf.py` with zero
edits of any kind.

### Proof 2 — bit-identity, not tolerance

A passing tolerance-based parity suite is compatible with a behaviour change. So I dumped
IEEE-754 hex of everything `dc_opf` returns — `objective_cost`, `dispatch_mw`,
`demand_dispatch_mw`, `ptdf`, `duals.balance`, `duals.flow_limit`, `duals.gen_bound` — over
6 fixtures × 3 LP shapes (plain / rated / rated + elastic polynomial bid) = 18 solves, and ran
the identical probe under three trees.

```
probe_m4     PROBE-SHA256 850bb84f4d9bd498410f5242348d6c1b5d678b7f0e30e8e730d44e6051945800
probe_swap   PROBE-SHA256 850bb84f4d9bd498410f5242348d6c1b5d678b7f0e30e8e730d44e6051945800
probe_m5     PROBE-SHA256 850bb84f4d9bd498410f5242348d6c1b5d678b7f0e30e8e730d44e6051945800
```

(`probe_m4` = pristine `e88752c`; `probe_swap` = `e88752c` + M5's `dc_opf.py`; `probe_m5` =
live worktree at `13aff40`.) Identical bits, duals included. There is no floating-point drift
to argue about.

### Reading the diff

Two things the extraction could have silently changed, both checked:

- **Row order.** M4 iterated `for gen_idx in pwl_gen_idxs`; M5 iterates
  `for gen_idx in sorted(segments_by_gen)`. `git show e88752c:...dc_opf.py` line 364 reads
  `pwl_gen_idxs = sorted(pwl_costs_)`, so the two orders are the same. Same for the demand side
  (line 386).
- **Structural zeros.** `_dense_csr` emits an entry in every column of `cols` including zeros,
  which is the pattern M4's single `h.addRows` call produced. Preserved deliberately, and the
  bit-identity above is the proof it worked.

### Readback — is the shared core actually shared?

The plan's own readback missed on its first aim. Mine aimed at a family that is always live.
Sign-flipping `injections` inside `_flow_limit_rows` **in `dc_opf.py`**, in the isolated
`git archive 13aff40` tree:

```
$ pytest -q -rf tests/unit/test_opf_multiperiod.py tests/unit/test_market_multiperiod.py \
      tests/unit/test_opf_dc.py tests/unit/test_opf_dc_demand.py tests/unit/test_market_nodal.py
      9 FAILED tests/unit/test_market_multiperiod.py
      1 FAILED tests/unit/test_market_nodal.py
      2 FAILED tests/unit/test_opf_dc.py
      1 FAILED tests/unit/test_opf_dc_demand.py
      5 FAILED tests/unit/test_opf_multiperiod.py
```

One helper broken, five test files red spanning both the single-period and the multiperiod
surface. That is the direct evidence D1's shared core is one implementation and not two copies
that happen to agree.

---

## AC-2 — hand-derived ramp optimum, binding period identified, dual recovered

**CONFIRMED.**

```
$ uv run --no-sync pytest -q tests/unit/test_opf_multiperiod.py \
      tests/unit/test_market_multiperiod.py -k ramp
9 passed, 46 deselected in 5.59s
```

### I re-derived the optimum before reading the assertions

Fixture (`tests/unit/test_opf_multiperiod.py:134`): `gcheap` c1=10 on [0,100] with ramp ±20,
`gexp` c1=50 on [0,100] unconstrained, both at slack bus b1; load at b2 = 50 MW then 100 MW;
`br12` unrated.

- t=0 balance pins generation at 50; objective prefers `gcheap` ⇒ `gcheap[0]=50`, `gexp[0]=0`.
- Ramp-up `gcheap[1] − gcheap[0] ≤ 20` ⇒ `gcheap[1] ≤ 70`; t=1 balance ⇒ `gexp[1]=30`.
- Objective `= 10·50 + 10·70 + 50·30 = 500 + 700 + 1500 = 2700`.

Duals, from `reduced_cost_j = c_j − Σ_r y_r·a_rj`:

- `gexp[1]` interior ⇒ `50 − λ₁ = 0` ⇒ **λ₁ = 50**.
- `gcheap[1]` interior ⇒ `10 − (λ₁ + y_ramp) = 0` ⇒ **y_ramp = −40**.
- `gcheap[0]` interior; the ramp row carries `−1` on `gcheap[0]` ⇒ `10 − λ₀ + y_ramp = 0` ⇒
  **λ₀ = −30**.
- `gexp[0]` at its lower bound ⇒ reduced cost `= 50 − λ₀ =` **80**.

Economic cross-check on the negative price: one more MW of load at t=0 costs `+10` directly,
then relaxes the ramp row so `gcheap` displaces `gexp` at t=1 for `+10 − 50 = −40`; net `−30`.
All four numbers match the committed assertions (`ramp[0, gcheap] ≈ −40`,
`balance ≈ [−30, 50]`, `gen_bound ≈ [[0, 80], [0, 0]]`), and `duals.ramp.shape == (1, 2)`
identifies the single t=0→t=1 row, i.e. binding at t=1.

The ramp-down mirror re-derives the same way: load `[100, 50]`, `gcheap[1] ≤ 50` by balance,
`gcheap[0] − gcheap[1] ≤ 20` ⇒ `gcheap[0] ≤ 70`, cost `= 700 + 1500 + 500 = 2700`.

### Readback

In the isolated tree (control on the broad set: `104 passed in 36.39s`):

```
--- S-E ramp rows dropped        (if n_ramped and n_periods > 1:  ->  if False:)
5 failed, 99 passed in 42.76s
--- S-D ramp up/down transposed  (down<-ramp_up, up<-ramp_down)
2 failed, 102 passed in 38.35s
```

Both directions of the two-sided row are load-bearing, and up/down are not interchangeable.

---

## AC-3 — SoC balance, cyclic condition, and the overlap invariant

**CONFIRMED**, with a coverage shortfall recorded below that does not change the verdict.

```
$ uv run --no-sync pytest -q tests/unit/test_opf_multiperiod.py \
      -k "soc or cyclic or overlap or efficienc or simultaneous or power_limit"
19 passed, 14 deselected in 13.95s
```

### The absence-readback pairing is genuine

This is the shape the brief flagged as classically powerless, so I checked whether the positive
case is the *same question* on the *same code path*, not a different network answering
something else.

- Both sides call the identical builder entry point: `_solve_overlap()` and `_storage_case(case)`
  each call `multiperiod_dc_opf(NetworkArrays.from_network(...), _linear_costs(...), 2,
  period_load_mw=...)`.
- The readback expression is character-identical in both tests:
  `np.minimum(sol.storage_charge_mw, sol.storage_discharge_mw)`
  (`tests/unit/test_opf_multiperiod.py:379` and `:619`).
- The positive case is genuinely positive and *bounded on both sides*, not merely non-zero:
  `assert overlap.min() > 15.0` and `assert overlap.max() <= 26.6666667 + 1e-7`, matching the
  derivation in `_overlap_network`'s docstring (`c ∈ [30.5556, 41.6667]`, `min = c − 15`).
- There is also a negative control on the row that bounds it:
  `test_the_shared_power_limit_row_is_live` shrinks `p_max` to 60 and asserts `Infeasible`.

The positive case uses a *different network*, which is correct — the point of a paired positive
case is that the same readback on the same code path reads non-zero when the physics demands it.
It is not a different question.

### Readbacks

```
--- S-A efficiency transposition (eta_charge <-> eta_discharge in the SoC row)
2 failed, 61 passed in 6.33s
--- S-B cyclic row deleted
4 failed, 59 passed in 9.41s
--- S-C shared power-limit row deleted
32 failed, 31 passed in 5.94s
```

S-A reproduces A20/A10's finding directly: the transposition is caught by exactly the two tests
built for it, confirming that S4's own catch of its powerless test is what gives this row any
detection power at all. S-B confirms S4's cyclic-binding fixture repaired a genuinely
tautological assertion.

### Coverage shortfall (does not change the verdict)

The criterion says the invariant holds *"on every fixture M5 ships"*. The committed invariant
covers only the four hand-built 2-period archetypes:

```
$ grep -rn "np.minimum\|simultaneous\|overlap" tests/ --include=*.py \
      | grep -v "^tests/unit/test_opf_multiperiod.py"
tests/parity/test_market_multiperiod_vs_pypsa.py:22: ...simultaneously makes PyPSA's...  (prose)
tests/_periods.py:26: ...simultaneously feasible.                                        (prose)
```

Nothing asserts it on the AC-6 `case14 × 24` fixture, in `test_market_multiperiod.py`, or in
example 10. I measured it myself:

```
AC-6 fixture (case14 x 24, rated, ramp+lossy storage):
  status: Optimal
  max min(charge,discharge) = 0.0
  case14 x24 (unrated, storage only): max overlap = 0.000e+00
  case30 x24 (unrated, storage only): max overlap = 0.000e+00
  case57 x24 (unrated, storage only): max overlap = 0.000e+00
  case118 x24 (unrated, storage only): max overlap = 0.000e+00
```

So A2 holds in substance and the criterion is met; part of that support is my measurement rather
than a committed test. **Two lines in `tests/parity/test_market_multiperiod_vs_pypsa.py` would
close it**, and the AC-6 case is exactly where the wave would most want the pin, since it is the
only 24-period fixture with congestion, ramp and lossy storage all live at once.

---

## AC-4 — T=1 degeneracy, and `market.nodal` unchanged

**CONFIRMED.** Both halves proved harder than the wave proved them.

```
$ uv run --no-sync pytest -q tests/unit/test_opf_multiperiod.py \
      tests/unit/test_market_multiperiod.py -k "ac4 or single_period_matches"
9 passed, 46 deselected in 9.62s
```

### First half, widened from 2 fixtures to all 6 × 2 shapes

The committed tests cover `case14` and `case30`. I ran `solve_multiperiod(Scenario(network=net))`
against `solve_nodal` on every fixture, comparing dispatch, generator bound duals, LMP, energy
and congestion components, load MW, and all three settlement totals with `np.array_equal` / `==`:

```
  case14/plain  [periods=None]: BIT-EXACT      case57/plain  [periods=None]: BIT-EXACT
  case14/rated  [periods=None]: BIT-EXACT      case57/rated  [periods=None]: BIT-EXACT
  case30/plain  [periods=None]: BIT-EXACT      case118/plain [periods=None]: BIT-EXACT
  case30/rated  [periods=None]: BIT-EXACT      case118/rated [periods=None]: BIT-EXACT
  case_ieee30/plain [periods=None]: BIT-EXACT  case300/plain [periods=None]: BIT-EXACT
  case_ieee30/rated [periods=None]: BIT-EXACT  case300/rated [periods=None]: BIT-EXACT
```

The structural route — the one `solve_multiperiod` actually takes for a period-less scenario —
is bit-exact on **every** fixture in the repository, `case300` included.

### Second half — the criterion says "byte-identical to its **M4** behaviour"

No committed test makes this comparison. `test_ac4_market_nodal_ignores_periods_entirely`
compares `solve_nodal(with periods)` against `solve_nodal(without periods)` *inside M5*; it never
touches M4. And `src/mambo_power/market/nodal.py` **did** change this wave (S5, `faba273`), so
the claim needed testing rather than assuming.

The change is a rename plus a docstring paragraph:

```
$ git diff e88752c..13aff40 -- src/mambo_power/market/nodal.py
-def _load_bid_coeffs(net: Network, arr: NetworkArrays) -> ...
+def load_bid_coeffs(net: Network, arr: NetworkArrays) -> ...
-    demand_bid_coeffs, demand_pwl_bids = _load_bid_coeffs(net, arr)
+    demand_bid_coeffs, demand_pwl_bids = load_bid_coeffs(net, arr)
    (+ __all__ entry, + docstring paragraph)
```

Proved behaviourally: `solve_nodal(...).model_dump(exclude={"provenance"}, mode="json")` over
15 (fixture × shape) solves including elastic bids, run under pristine `e88752c` and under
`13aff40`:

```
=== under pristine M4 tree (e88752c) ===
NODAL-SHA256 60ec1f7af7f7795fcd4c05e2be1a777dbf6a11f544d3ddd4e947cd9dcb83ae16
=== under M5 head ===
NODAL-SHA256 60ec1f7af7f7795fcd4c05e2be1a777dbf6a11f544d3ddd4e947cd9dcb83ae16
$ cmp nodal_m4.json nodal_m5.json
BYTE-IDENTICAL
```

### Readback

```
--- S-G multiperiod balance RHS + 1e-9 MW  (total_fixed[t] -> total_fixed[t] + 1e-9)
8 failed, 96 passed in 37.77s
```

A one-nano-megawatt perturbation goes red. That is what `assert_array_equal` buys over
`allclose`, confirmed independently of the plan's own run.

### Finding: the divergent fixture the wave predicted, located

`test_ac4_an_explicit_single_period_also_reproduces_market_nodal_exactly`'s docstring says the
explicit-Period route is exact *as measured, not as structurally guaranteed*, and that "a fixture
where the two answers diverged would land this test on `assert_allclose`, and that would be
information rather than a regression."

That fixture exists, inside the repo's own set. On `rated_network(case57)` and
`rated_network(case118)` the explicit route is **not** bit-exact:

```
  case57/rated  [explicit T=1] gbound:   NOT bit-equal, maxabs=2.842e-14
  case57/rated  [explicit T=1] lmp:      NOT bit-equal, maxabs=1.705e-13
  case57/rated  [explicit T=1] energy:   NOT bit-equal, maxabs=1.421e-14
  case57/rated  [explicit T=1] congest:  NOT bit-equal, maxabs=1.137e-13
  case57/rated  [explicit T=1] gen_recv: 61452.12701426307 != 61452.12701426306
  case57/rated  [explicit T=1] rent:     10223.83585361173 != 10223.835853611738
  case118/rated [explicit T=1] dispatch: NOT bit-equal, maxabs=7.283e-12
  case118/rated [explicit T=1] lmp:      NOT bit-equal, maxabs=2.082e-12
  case118/rated [explicit T=1] load_pay: 167603.27983591688 != 167603.27983591714
```

Deterministic, not solver noise — reproduced three times per fixture with identical values, and
`periods=None` stays bit-equal on the same runs:

```
case57  run1/2/3: explicit-vs-nodal bit-equal=False maxabs=1.705e-13 | None-vs-nodal bit-equal=True
case118 run1/2/3: explicit-vs-nodal bit-equal=False maxabs=2.082e-12 | None-vs-nodal bit-equal=True
```

The trigger is congestion: the plain (unrated) case57 and case118 are bit-exact; only once
flow-limit rows bind does the ~1e-15 MW difference in fixed-load aggregation move the vertex and
dual selection. The mechanism is exactly the one the test docstring names.

**This does not refute AC-4**, whose criterion reads "on a real fixture" — satisfied several
times over. It has two consequences worth folding:

1. `docs/manual/multiperiod.md:262` states, flatly and in the same sentence as "asserted with
   `==` and not with a tolerance": *"So does an explicit single-period scenario, and so does one
   with elastic bids in play."* That sentence is false on those two networks. The test docstring
   is candid; the shipped manual is not.
2. The test is parametrized over `["case14", "case30"]` only. Adding `case57`/`case118` would
   land it on `assert_allclose` — which the wave itself said would be information rather than a
   regression.

---

## AC-5 — the analytic 2-bus/2-period arbitrage optimum

**CONFIRMED.**

```
$ uv run --no-sync pytest -q tests/unit/test_opf_multiperiod.py \
      tests/unit/test_market_multiperiod.py -k "ac5 or analytic or arbitrage"
9 passed, 46 deselected in 5.53s
```

### Re-derived independently from the fixture, not read off the assertions

`gcheap` c1=10 on [0,40], `gexp` c1=50 on [0,200], both at b1; load at b2 `[20, 100]`; storage
`p_max=20`, `energy=15`, `soc_initial=0`, `η_c = η_d = 0.9`; `br12` unrated.

- `soc[0] = 0.9c`, capped by `E_max = 15` ⇒ `c ≤ 16.6667`; the power cap `c ≤ 20` is slack, so
  the **energy** cap binds.
- Cyclic `soc[1] = 0` ⇒ `d = 0.9·soc[0] = 0.81c`.
- Cost `= 10(20 + c) + [10·40 + 50(60 − 0.81c)] = 3600 − 30.5c`, minimised at the largest
  feasible `c`.
- ⇒ `c* = 50/3 = 16.6667`, `d* = 0.81·16.6667 = 13.5`, `soc[0] = 15.0`,
  objective `= 3600 − 508.3333 = 3091.6667`.
- `gcheap[0] = 20 + 16.6667 = 36.6667` — interior below its 40 cap ⇒ **λ₀ = 10**;
  `gcheap[1] = 40` at cap, `gexp[1] = 100 − 13.5 − 40 = 46.5` interior ⇒ **λ₁ = 50**.
- Saving `= c*·(c_H·η_cη_d − c_L) = 16.6667 × (40.5 − 10) = 508.3333`.

Every one of these matches the committed assertions. The prices are *formed by the builder*
rather than assumed, which is what makes this a genuine reduction of research §7.1's price-taker
setup rather than a hard-coded answer.

### Why this row is not fitted to the implementation

The closed form is in `record/m5-research.md` §7.2 (derivation) and §7.3 ("Numeric instance,
independently verified"), written at Step 1, and cross-checked there against an independent
scipy LP. The oracle predates the solver, which is the usual way an analytic row goes powerless
and does not apply here. The end-to-end check is independent of the closed form's own algebra:
`test_storage_saving_equals_the_closed_form_arbitrage_profit` solves the *same network with no
storage at all* (`3600.0`) and differences the two objectives.

---

## AC-6 — PyPSA multi-period oracle parity

**CONFIRMED.**

```
$ uv run --no-sync pytest -q tests/parity/test_market_multiperiod_vs_pypsa.py
9 passed in 38.31s
```

### Did any tolerance move after first being written?

```
$ git log --oneline -- tests/parity/test_market_multiperiod_vs_pypsa.py
ad0ad7e feat(m5/S6): fixtures-oracle — 24-period profile, storage sizing, PyPSA multiperiod parity
```

One commit. No tolerance has ever been widened in committed history. That alone cannot rule out
pre-commit tuning, so I measured the residuals directly.

### The residuals, re-measured by the auditor

I zeroed all five tolerance constants **in memory** via a pytest plugin (`pytest_collection_finish`
setting them to `0.0`; no file touched) and read the failure messages:

```
ZEROTOL: ...test_market_multiperiod_vs_pypsa.py TIGHT_COST_REL_TOL  was 1e-09 -> 0.0
ZEROTOL: ...                                    DISPATCH_ABS_TOL_MW was 0.01  -> 0.0
ZEROTOL: ...                                    STORAGE_ABS_TOL_MW  was 0.01  -> 0.0
ZEROTOL: ...                                    SOC_ABS_TOL_MWH     was 0.01  -> 0.0
ZEROTOL: ...                                    LMP_ABS_TOL         was 0.001 -> 0.0

E  AssertionError: (173117.3398497686, 173117.3398498439, 4.3491662624249813e-13)
E  AssertionError: ((18, 2), 0.00030082881895054925)
E  AssertionError: (18, 0.000109984242649519, 1.0326393212978224, 1.032529337055173)
E  AssertionError: (16, 0.00012498209407851846, 78.87345377420202, 78.87332879210794)
E  AssertionError: ((11, 13), 4.244263550390315e-05)
5 failed, 4 passed in 48.97s
```

| quantity | measured residual | pinned tolerance | margin |
|---|---|---|---|
| objective (relative) | 4.3492e-13 | 1e-9 | ~2300× |
| generator dispatch | 3.0083e-4 MW | 1e-2 MW | ~33× |
| storage net power | 1.0998e-4 MW | 1e-2 MW | ~91× |
| state of charge | 1.2498e-4 MWh | 1e-2 MWh | ~80× |
| LMP | 4.2443e-5 $/MWh | 1e-3 $/MWh | ~24× |

Every documented figure reproduces to the digits quoted in the plan. The tolerances are round
decades well clear of the residuals — measured then margined, not fitted. Note also which four
tests **passed** with tolerances zeroed: the four preconditions (both engines converge, congestion
binds and un-binds, ramp and storage both engaged), which are the fixture-fidelity assertions and
carry no tolerance.

### The fixture-fidelity precondition is itself committed and passes

`test_congestion_binds_in_some_periods_and_not_others` asserts a binding period *and* a slack
period exist, pins the specific branch/flow/rating at the first binding period with
`pytest.approx(rating, abs=1e-2)`, and asserts every branch that ever binds is one of the 17
PyPSA rates as a `Line` — closing A19's routing-around at the level of an assertion rather than
a comment. `test_ramp_and_storage_are_both_genuinely_engaged` asserts a non-zero ramp dual and
non-zero storage power. All four pass with every tolerance at zero.

### A20 attacked directly — and it holds

The plan discloses that transposing the two efficiencies is a near no-op on this fixture. I
attacked that as a hypothesis. In the isolated tree, `tests/_storage.py` lines 89–90 transposed
(`efficiency_charge=EFFICIENCY_DISCHARGE`, `efficiency_discharge=EFFICIENCY_CHARGE`) against the
**unmodified** oracle:

```
9 passed in 15.07s
```

A20 is **confirmed, not refuted**: the AC-6 fixture genuinely cannot tell 0.92 from 0.88. The
disclosure is accurate. The property is nonetheless proven by the wave, one tier down — my S-A
sabotage shows `test_charge_and_discharge_efficiencies_enter_the_soc_row_the_right_way_round`
and the `asymmetric-efficiency` SoC case going red (2 failed). AC-6's criterion does not require
efficiency orientation, so this does not bear on the verdict.

---

## AC-7 — the jobs surface

**CONFIRMED.**

```
$ uv run --no-sync pytest -q tests/unit/test_jobs.py
57 passed in 6.70s → re-run: 57 passed in 12.25s
```

### `KINDS` is exactly 6, and all five prior kinds still take the M4 form

```
KINDS: ['market.multiperiod', 'market.nodal', 'n1', 'opf.dc', 'pf.ac', 'pf.dc'] len = 6
  market.nodal           status=ok
  n1                     status=ok
  opf.dc                 status=ok
  pf.ac                  status=ok
  pf.dc                  status=ok
```

Each of those five was invoked as `jobs.run(jobs.SolveRequest(kind=k, network=net))` — the
verbatim M4 call shape — on `case14`.

### "Never raises", attacked adversarially

Seven malformed inputs through `run_json`, all returning a status rather than an exception:

```
  run_json('{"kind": "no.such.kind", "network": null}')                 -> status='failed'
  run_json('{"kind": "market.multiperiod"}')                            -> status='failed'
  run_json('not json at all')                                           -> status='failed'
  run_json('{"kind": "market.multiperiod", "network": {"buses": []}}')  -> status='failed'
  run_json('{}')                                                        -> status='failed'
  run_json('[]')                                                        -> status='failed'
  run_json('{"kind":"market.multiperiod","network":null,"scenario":null}') -> status='failed'
```

Both mutation paths, including A22's new scenario surface (network mutated invalid *after* the
request exists, which is the pre-existing contract):

```
  A network-mutated-after-construction -> failed | code='VALIDATION' DANGLING_REF at branches[0].to_bus
  B scenario-mutated                   -> failed | code='VALIDATION' DANGLING_REF at branches[0].to_bus
  C market.multiperiod -> failed   C market.nodal -> failed   C n1     -> failed
  C opf.dc             -> failed   C pf.ac        -> failed   C pf.dc  -> failed
  D all-generators-tiny (infeasible LP) -> failed
```

A22 is confirmed behaviourally: `Scenario` re-validation on wrap is caught at the resolution
step and returned as a graceful `VALIDATION` failure on all six kinds, not raised.

JSON round-trip with type preserved, on a real 3-period scenario:

```
  3-period run_json status: ok | result keys: ['provenance','status','message','n_periods','periods']
```

### A21 adjudicated on content, across the whole wave

The plan adjudicated S7's single test edit using S7's own commit. I checked the whole wave range,
which is the stronger check:

```
$ git diff -U0 e88752c..13aff40 -- tests/unit/test_jobs.py | grep "^-" | grep -v "^---"
-from mambo_power.market import MarketNodalOptions
-from mambo_power.model import Network
-KNOWN_KINDS = {"pf.ac", "pf.dc", "opf.dc", "n1", "market.nodal"}
-    def wrong(net: Network, options: BaseModel | None) -> BaseModel:
-        return solve_dc(net)
```

Exactly five deleted lines, exactly as A21 states: two imports, the `KNOWN_KINDS` constant that
AC-7's own criterion *requires* to change, and the two-line body of a local `Runner`-protocol
stub. Test functions removed from M4 to M5:

```
M4 count: 32  M5 count: 48
removed from M4 -> M5:      (empty)
```

Zero. Nothing exercising the public `SolveRequest(network=...)` surface was touched. A21's
adjudication stands.

### Readbacks

```
--- control (jobs)                              57 passed in 3.30s
--- S-H exactly-one-of validator neutered        3 failed, 54 passed
--- S-I periods dropped on resolution            4 failed, 53 passed
```

---

## AC-8 — documentation

**CONFIRMED.**

```
$ uv run --no-sync mkdocs build --strict
INFO - Documentation built in 34.05 seconds          [exit 0]
```

### Symbol coverage passes unmodified — across the whole wave

The plan checked `HEAD~1..HEAD`. I checked the full range, which is what "without modification"
means:

```
$ git diff --stat e88752c..13aff40 -- tests/unit/test_api_docs_coverage.py
(empty)
$ git log --oneline e88752c..13aff40 -- tests/unit/test_api_docs_coverage.py
(empty)
$ uv run --no-sync pytest -q tests/unit/test_api_docs_coverage.py
2 passed in 5.97s
```

Not one commit in the wave touched that file.

### The new example runs and is snippet-embedded, and CI runs it

```
$ uv run --no-sync python examples/10_multiperiod_market.py
exit=0
  periods=None -> n_periods 1, status Optimal
  dispatch identical to market.solve_nodal: True (5 gens)
  LMPs identical to market.solve_nodal:     True (14 buses)

$ uv run --no-sync pytest -q tests/unit/test_examples_run.py
12 passed in 17.16s

$ grep -n "10_multiperiod_market" docs/examples/index.md
26:  | [`10_multiperiod_market.py`](#10-multiperiod-market) | ... |
125: --8<-- "examples/10_multiperiod_market.py"

$ grep -rn "examples" .github/workflows/ci.yml
49:  examples:
68:          for f in examples/*.py; do
```

The CI job globs `examples/*.py`, so example 10 is picked up without a config edit.

### The new pages exist in the built site with rendered content

```
$ ls site/manual/multiperiod/index.html && wc -c site/manual/multiperiod/index.html
82168 site/manual/multiperiod/index.html

symbol                     market-api  opf-api  results-api   (occurrence counts in built HTML)
solve_multiperiod              25          2         4
MarketMultiperiodResult        12          0        15
multiperiod_dc_opf              3         26         0
```

S8's dedicated `:::` blocks did what they were added for.

### Do the walk's defects change this row?

**No.** AC-8's three clauses are build success, the coverage test being unmodified, and the
example running and being embedded. None is a claim about the *truth* of rendered prose. D6
(MathJax literal backslashes) and D1–D4 (staleness) are all invisible to `--strict` by
construction, which the plan's own readback note already concedes and which is the standing
argument for the walk existing. D7 concerns validation and touches no AC-8 clause.

---

## Findings no acceptance criterion covers

Four. None changes a verdict; all four are fold candidates.

### F1 — the manual states something that is false (see AC-4)

`docs/manual/multiperiod.md:262`. Detail and evidence under AC-4 above. One sentence to soften,
and optionally two fixture names to add to
`test_ac4_an_explicit_single_period_also_reproduces_market_nodal_exactly`'s parametrize list —
which would move it to `assert_allclose`, exactly as the test itself anticipated.

### F2 — A25/A28's schema coupling is wrong about D2

A25 and A28 both state that D2/D3/D4 "must land **together** with a JSON-schema snapshot
regeneration", because pydantic embeds class docstrings into the committed snapshot. That is true
for two of the three and false for the third.

```
$ python -c "import json; d=json.load(open('tests/unit/snapshots/network.schema.json')); print(list(d['\$defs']))"
['Branch','Bus','Generator','Geo','Load','PiecewiseBid','PiecewiseCost',
 'PolynomialBid','PolynomialCost','Shunt','Storage','Zone']
Period present: False
```

The snapshot is of `Network`. `Period` hangs off `Scenario`, which has no snapshot test at all
(`tests/unit/test_json_schema_snapshot.py` is the only pin, and it pins `Network`). The coupling
is real for the other two:

```
tests/unit/snapshots/network.schema.json:616:
  "description": "Energy storage. Schema-present; no M1 solver reads it.",
Load description in snapshot:
  Fixed demand at a bus. ``bid`` is model-present; only ``market.nodal`` reads it.
```

**Consequence: D2 is a one-line docstring fix with no snapshot regeneration and no published
schema surface involved.** The "must land together" argument — which is the stated reason S8
deferred all three — does not apply to it. The fold is cheaper than recorded.

### F3 — A27 understates D7, and the correction makes the defect worse

A27 records that `Storage.energy_mwh` and `Storage.p_max_mw` are absent from `BAD_RANGE` and
"surface only as a bare `Infeasible` from the LP". That is true for negative values. It is **not**
true for zero, which is the case A27 explicitly lists as a gap:

```
baseline (good)          validate_ok=True  solve=Optimal  soc=[33.3154,33.3154,20.0] charge=[14.0162,0,0] discharge=[0,0,12.6496]
energy_mwh = 0.0         validate_ok=True  solve=Optimal  soc=[0.0,0.0,0.0]  charge=[0,0,0]  discharge=[0,0,0]
energy_mwh = -40.0       validate_ok=True  solve=Infeasible
p_max_mw   = 0.0         validate_ok=True  solve=Optimal  soc=[20.0,20.0,20.0] charge=[0,0,0] discharge=[0,0,0]
p_max_mw   = -20.0       validate_ok=True  solve=Infeasible
```

A zero-sized unit passes validation **and clears `Optimal`**, with the storage silently
contributing nothing. A user who mis-specifies `energy_mwh=0` or `p_max_mw=0` gets a
plausible-looking result with an inert unit rather than a loud failure — silent, not loud, which
is the worse of the two failure modes A27 considered.

This does not make any shipped test powerless, because M5's own fixtures all size storage
properly. It does strengthen the case for folding D7, and it means the fold should say
"negative *and* zero are both wrong, and zero is the dangerous one".

### F4 — `Period.load_p_mw` is strictly *less* general than the `Load.p_mw` it overrides

`Period.load_p_mw`'s validator (`src/mambo_power/model/scenario.py:27-33`) rejects any value
`< 0`. `Load.p_mw` (`src/mambo_power/model/entities.py:151`) carries no lower bound, and
`case300` ships eight negative loads:

```
case300 loads with p_mw < 0: 8 [('load-51',-5.0), ('load-207',-21.0), ('load-250',-23.0), ('load-281',-33.1)]
network itself validates: Network loads: 201
identity Period REJECTED: ValidationError  load_p_mw
market.nodal on case300: Optimal
```

So `market.multiperiod` cannot express even the **identity** profile on a fixture that
`market.nodal` clears `Optimal`. The same asymmetry stops `tests/_periods.py:96` from deriving a
profile for case300 at all.

This matters beyond the fixture. D2's ratified rationale was that a per-load override is
*strictly more general* than scalar load scaling; on one of the repository's six fixtures it is
less general than the field it overrides. The fix is a design decision, not a docs edit —
either relax `Period`'s bound to match `Load`'s, or add the matching bound to `Load` and accept
that case300 needs a loader change. Recorded for M6, not for this fold.

---

## What I could not establish

Nothing material was left unverified. Two boundaries worth naming:

- **A19's root cause** (PyPSA infeasible when `Line` and `Transformer` are rated together)
  remains `unverified`, as the wave itself labels it. I did not attempt to diagnose it; the
  routing-around is asserted in a committed test that I ran with every tolerance at zero, so
  the AC-6 comparison is never asked to agree on a constraint the oracle does not enforce.
- **Pre-commit tolerance tuning** on AC-6 cannot be ruled out by git history, since the parity
  file has a single commit. I substituted a direct measurement of every residual instead, which
  is the stronger evidence and is recorded under AC-6.

## Method and hygiene

- Isolation: `git archive <sha> | tar -x` into the scratchpad, never `git worktree`, never a
  write to the live worktree — A13's own rule, and S1's technique.
- Every sabotage run printed the loaded module's `__file__` before pytest, proving the sabotaged
  copy was the one imported.
- Restoration verified structurally rather than by hash alone (`git archive` and `git show`
  differ by line-ending conversion on this machine, which produces a false "DIRTY" if you compare
  their hashes):

```
$ diff -rq $SCR/sab_ref/src $SCR/sab/src
Only in .../sab/src/mambo_power: __pycache__          (and the same for each subpackage)
```

  No source file differs.

- Live worktree at the close of the audit:

```
$ git status --porcelain
(empty)
$ git rev-parse HEAD
13aff400b18379a9e4c7507cac48e2bb73801dc4
```
