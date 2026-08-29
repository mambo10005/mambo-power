# M5 (`multiperiod`) — six-axis code review

Scope: `e88752c..13aff40` on `wave/05-multiperiod`, 8 commits (S1..S8), 41 files, +5566/−221.
Worktree reviewed: `C:\Claude Projects\mambo-power-m5`.

Baselines, before anything was touched:

```
uv run --no-sync pytest tests/unit -q            -> 590 passed in 48.82s
uv run --no-sync pytest tests/parity/test_market_multiperiod_vs_pypsa.py -q
                                                 -> 9 passed in 32.93s
```

Every sabotage below was applied in a detached scratch worktree
(`git worktree add --detach <scratch>/m5sab 13aff40`) and run from the main worktree with
`PYTHONPATH=<scratch>/m5sab/src` (override confirmed: `import mambo_power.opf.multiperiod`
resolves to the scratch path). **No tracked file in either worktree was modified.**

Findings already recorded by the separate walk (changelog stopping at M2; false `Storage`/
`Period`/`Load` docstrings; `ValueError` vs `NetworkValidationError` in the manual; MathJax
backslashes; `Storage.energy_mwh`/`p_max_mw` accepting negative and zero) are not repeated here
except where this review adds new information about their consequences.

---

## Verdict

**Nothing blocks the merge.** I found no wrong number in the shipped LP: the two-tier index
arithmetic, the dual sign conventions, the efficiency placement in the SoC row and the cyclic row
all check out under direct probing, and the coupling families are backed by hand-derived-dual
tests that are genuinely powerful. What the wave is missing is not correctness — it is *coverage
of the paths that happen to be uninhabited by its own fixtures*. Four items should be folded
before merge; three should be carried.

| # | Axis | Severity | Disposition |
|---|---|---|---|
| F1 | Test quality | High | Fold before merge |
| F2 | Test quality / correctness | High | Fold before merge |
| F3 | Correctness (docs) | Medium | Fold before merge |
| F4 | Test quality | Medium | Fold before merge |
| C1 | Architecture | Medium | Carry to M6 |
| C2 | Security | Low (today) | Carry |
| C3 | Test quality | Low | Carry |

---

## Fold before merge

### F1 — The PWL / tier-2 code path has zero effective coverage at `T > 1`

This is the most delicate arithmetic in `opf/multiperiod.py` and nothing tests it.

The module's own docstring ("Column layout — two tiers, not one block per period") explains that
the free `cost_g`/`val_d` variables had to be **hoisted out** of the per-period blocks that
`record/m5-research.md` §2.2 describes, because `dc_opf`'s Hessian must be passed over a prefix of
the columns before any free column exists. That hoist is the one place the implementation
deliberately departs from the research plan, and it is the one place with no test.

No M5 test ever passes a non-empty `pwl_costs` or `demand_pwl_bids` at `T > 1`:

- `tests/unit/test_opf_multiperiod.py:699` passes `pwl` but with `n_periods=1`, where
  `t * per_period_free == 0` makes the stride invisible.
- `demand_pwl_bids` is never passed to the multiperiod builder at all —
  `grep -rln demand_pwl_bids tests/` returns only `test_market_nodal.py` and
  `test_opf_dc_demand.py`.
- `tests/_bids.py:119,185` only ever produce `PolynomialBid`, so even
  `test_ac4_exactness_holds_with_elastic_bids_in_play` cannot reach `_hypograph_rows` in this
  module.

Three sabotages, each a genuine bug at `T > 1`, leave the suite fully green:

| Sabotage | Location | Result |
|---|---|---|
| `base = n_dispatch_total + t * per_period_free` → `base = n_dispatch_total` | `multiperiod.py:403` | **590 unit passed** |
| epigraph rows pinned to `gen_cols[0]` / `cost_col_of[0]` | `multiperiod.py:578` | **599 passed** (unit + parity) |
| hypograph rows pinned to `demand_col_of[0]` / `demand_val_col_of[0]` | `multiperiod.py:581` | **599 passed** (unit + parity) |

That the third is behaviour-changing is not a guess. The same epigraph edit, on
`fixtures/matpower/derived/case14_pwl.m` at `T = 2` with an 0.8x/1.2x load profile:

```
clean     : status Optimal  objective     12514.1881053129
            period-1 dispatch [116.3075 124.4925  70.  0.  0.]
sabotaged : status Optimal  objective -19993647.1222030520
            period-1 dispatch [ 70.8    140.     100.  0.  0.]
```

An objective off by six orders of magnitude, and 599 green tests.

**Fix.** One test at `T ≥ 2` on `case14_pwl.m` (the fixture already exists), and one with a
`PiecewiseBid` load at `T ≥ 2`. Both are cheap; the first would have caught all three sabotages.

### F2 — Elastic demand × per-period load is unguarded, and silently ignores the period override

**The coverage half.** In `multiperiod.py:507`, replacing

```python
elastic_own_mw = period_load_mw[t][elastic_idx_arr]
```

with `np.zeros(n_demand)` — that is, double-counting every bid load's demand in the fixed RHS,
the exact fault ADR-007 Consequence 1 exists to prevent — leaves **590 unit tests passing**. The
cause is that no test combines bids with `T > 1`: `tests/unit/test_market_multiperiod.py:387-388`
builds `with_bids(...)` and then clears `Scenario(network=net)`, i.e. `T = 1` with
`period_load_mw=None`, which takes the *other* branch of that `if`.

**The behavioural half, which the same code produces.** The subtraction is correct — it removes
exactly the period's own value for that load. But the elastic column's bounds come from the
*network*, not the period (`multiperiod.py:428-429`):

```python
demand_p_min = arr.load_p_min_pu[elastic_idx_arr] * arr.base_mva
demand_p_max = arr.load_p_max_pu[elastic_idx_arr] * arr.base_mva
```

`arr.load_p_max_pu` is built from `Load.p_mw`. So the period value is subtracted from the RHS and
then never reappears anywhere: **a `Period.load_p_mw` entry naming a bid-carrying load has no
effect on the solve at all.** Measured on rated case14 with a bid on `load-2` only and a
0.8x/1.2x two-period profile:

```
bid load: load-2   network p_mw: 21.7
t=0  bid-load served=21.7000   other(load-3) served= 75.3600
t=1  bid-load served=21.7000   other(load-3) served=113.0400
```

`load-3` (no bid) scales correctly; `load-2` is pinned. With `with_bids` applied to *every* load,
a 24-hour profile collapses to 24 identical periods — confirmed: both periods returned
`served 259.0000` and identical LMPs.

This is arguably in scope of "bids are horizon-invariant" (`docs/manual/multiperiod.md:40`, "Costs,
bids, **bounds**, ratings ... are horizon-invariant"), and I am not calling the behaviour wrong.
I am calling it **silent**: `Period.load_p_mw`'s own docstring (`model/scenario.py`) describes it
as an id-keyed override of each `Load`'s `p_mw`, unqualified, and a user combining a load profile
with demand bids gets a plausible-looking answer that ignores half their input.

**Fix.** One sentence in `Period`'s docstring and in the manual naming the exclusion, plus a test
that pins the behaviour either way (which also closes the sabotage above).

### F3 — `soc_dual`'s shipped sign is the opposite of what three docstrings say

The numerics are right; the prose is not.

Measured on a two-period arbitrage network (η_c = η_d = 0.9, LMPs [10, 50]):

```
balance (LMP energy) [10. 50.]
soc_balance dual     [-11.11111111 -45.        ]
check -eta_d*LMP[t]: [-9.0, -45.0]
```

`y_soc[1] = −45 = −η_d · λ_1` exactly, which is what the KKT stationarity of the discharge column
requires under HiGHS's `reduced_cost_j = c_j − Σ_r y_r·a_rj`. The dual is the **negative** of the
marginal value of stored energy. `test_storage_soc_duals_match_the_hand_derived_kkt_conditions`
(`test_opf_multiperiod.py:623`) hand-derives those negatives correctly and asserts them, so the
builder is right and the test is strong.

Three shipped surfaces describe it as a positive quantity:

- `src/mambo_power/opf/multiperiod.py:165-166` — *"the marginal value of one more MWh in that unit
  at the end of that period"*
- `src/mambo_power/results/multiperiod.py:79-82` — same wording, on a **frozen public pydantic
  field description** (`StorageDispatchResult.soc_dual`)
- `docs/manual/multiperiod.md:152-153` — same wording again

The contrast is internal to this wave: `GenPeriodDispatchResult.ramp_dual`
(`results/multiperiod.py:52-57`) states its HiGHS sign convention explicitly and correctly
("negative when the ramp-up side binds, positive when the ramp-down side does"). The storage field
should say the same kind of thing.

**Same fold, same file.** `StorageDispatchResult.energy_bound_dual`
(`results/multiperiod.py:83-86`) says *"0 unless the energy capacity binds"*. Falsified by the same
probe: at `t = 1` the unit sits at `soc = 0.0` — empty, not capped — and `energy_bound_dual` is
`+45.0`. It is the reduced cost of the `[0, energy_mwh]` bound and is non-zero at **either** end.
`MultiperiodDuals.storage_soc_bound`'s own wording is closer to right; the results-layer one is
wrong as written.

### F4 — Every storage/ramp fixture is degenerate, so per-unit strides are unfalsifiable

Every M5 network carries exactly **one** storage unit and exactly **one** ramped generator:

- `Storage(` appears 5x in `test_opf_multiperiod.py` and 3x in `test_market_multiperiod.py`, one
  per `storage=[...]` block (counted per block programmatically).
- `tests/_storage.py:161` derives a single unit.
- The parity fixture ramps only `gen-1` (`test_market_multiperiod_vs_pypsa.py:97-100`).

With `n_storage == 1` and `n_ramped == 1`, period-major and unit-major orderings are
indistinguishable. Two transposition sabotages leave **all 599 tests green**:

| Sabotage | Location |
|---|---|
| `limit_upper = np.tile(storage_p_max, n_periods)` → `np.repeat(...)` | `multiperiod.py:559` |
| `np.tile(down/up, n_periods - 1)` → `np.repeat(...)` | `multiperiod.py:576` |

Both are real bugs. On a hand-built 3-period network with two heterogeneous storage units
(10 MW/40 MWh and 60 MW/240 MWh) and two heterogeneous ramp limits (5 MW/h and 60 MW/h):

```
clean     : objective 2300.000000
            dispatch [[68.78  0.  0.] [73.78  6.22  0.] [68.78  0.  0.]]
            charge   [[10.  38.78] [0. 0.] [1.08 27.70]]
sabotaged : objective 4375.623269
            dispatch [[40.  0.  0.] [45.  5.  30.] [97.56  0.  0.]]
            charge   [[10.  10.  ] [0. 0.] [1.08 56.48]]
```

The current code is correct — I verified the tile/loop-order pairing by hand and the clean run
respects each unit's own `p_max`. But nothing would notice if it stopped being correct, and M6
(zonal) is the wave most likely to touch this.

**Fix.** One fixture with two heterogeneous storage units and two heterogeneous ramp limits,
carried through the existing invariant sweep.

---

## Carry to the next wave

### C1 — ADR-007: honoured in substance for the row families, forked for everything else

**The row-family half is real, not cosmetic.** `opf/multiperiod.py:112-125` imports
`_balance_row`, `_flow_limit_rows`, `_epigraph_rows`, `_hypograph_rows`, `_add_rows`, `_RowBlock`,
`_dense_csr`'s two segment helpers and the two error classes, and reimplements none of them. The
helpers really are parameterised on LP column indices rather than on `dc_opf`'s own layout, which
is what lets `multiperiod.py:521-538` hand them a period's columns *plus* storage columns and get
the same rows back. And the extraction's behaviour-preservation has the strongest evidence
available: `git diff --stat e88752c..13aff40` touches **no** `tests/unit/test_opf_dc*.py` file, so
the pre-existing DC-OPF/PWL/elastic-demand suite held green completely unchanged through S1.

**But ADR-007's other two consequences are now a second copy.** The ADR's own words:

> **`dc_opf` owns the double-counting contract itself.** … A caller cannot get this wrong, because
> a caller cannot do it at all.

That contract is now implemented a second time in `multiperiod.py:496-513` — and F2 proves that
second copy has no test. The same goes for Consequence 2's symmetric convexity guards.

Quantified, not asserted. The cost/bid extraction and validation block:

```
dc_opf.py:566-627  (62 lines)
multiperiod.py:318-382  (65 lines)
identical lines: 48   difflib ratio: 0.756
```

The diff between them is `del v0`, one dropped local, and hand-edited error-message text. Add:

- the Hessian block — `dc_opf.py:653-667` vs `multiperiod.py:452-468`
- the fixed-load / flow-constant arithmetic — `dc_opf.py:704-717` vs `multiperiod.py:496-513`

"One dual-extraction path" is also no longer literally true: `MultiperiodDuals` carries its own
hand-maintained row-offset running sum (`multiperiod.py:648-652`).

**Judgment.** This is not a violation — a `T`-loop genuinely cannot be a parameter of `dc_opf`
without making that function worse, and the wave was right to add a sibling. But the ADR's
guarantee was that the *invariants* live in one place, and half of them now live in two. M6 adds
zonal clearing plus a redispatch LP on this same seam; if it copies the preamble again, the
double-counting contract exists in three places and the ADR is dead in substance while alive in
form. Recommendation: extract the extraction+validation preamble into one shared helper **before**
M6 starts, not after.

### C2 — No upper bound on `n_periods`, with large amplification

`multiperiod.py:302` rejects `n_periods < 1` and nothing else. `Scenario.periods` has
`min_length=1` and no maximum. Measured on rated case118 through the real `SolveRequest`:

```
T=1     request 76,117 B (network-only baseline 76,103 B)
T=2000  request 110,100 B  ->  periods block ~33,997 B
        LP cols ~108,000   flow rows ~372,000   flow-row nonzeros ~20,088,000
```

~34 KB of `{"load_p_mw":{}}` produces ~240 MB of constraint matrix before HiGHS starts, and the
measured `T`-scaling (below) puts the solve in the hours. There is no network-facing service yet,
so this is not urgent — but it wants a cap on `Scenario.periods` (or a `jobs`-level guard) before
the job surface is ever exposed over HTTP.

**The rest of this axis is clean, and I checked it rather than assuming it.**

- `io/matpower.py` is **untouched** by the wave — absent from `git diff --stat e88752c..13aff40`.
  The file-parsing surface is unchanged.
- `Period.load_p_mw` validates every value `>= 0` and sets `allow_inf_nan=False`
  (`model/scenario.py`).
- `Scenario`'s `_check_period_load_refs` catches dangling load ids at construction; a load id that
  `NetworkArrays` legitimately dropped is skipped rather than crashing
  (`market/multiperiod.py:110-112`).
- `validate_network` gained `ramp_up_mw`/`ramp_down_mw` `> 0` checks (`model/network.py:176-183`),
  and `_checked_ramp` (`multiperiod.py:242`) rejects a zero limit with a good message.
- Degenerate storage inputs degrade rather than crash. Probed: `efficiency_discharge=0` is
  rejected at `Network` construction (`NetworkValidationError`); `energy_mwh=-15` and
  `p_max_mw=-20` both return `status="Infeasible"` with no exception. **One new fact for the
  already-slated `Storage` validation fold**: through `jobs.run` those become `INFEASIBLE_LP`, not
  `VALIDATION` — a bad-input error reported as a solver outcome.

Minor, not worth a fold on its own: `_checked_ramp` normalises `nan` to `inf` but lets `-inf`
through as "unconstrained" (`np.isfinite(-inf)` is `False`), where a negative *finite* limit is
correctly rejected.

### C3 — `c0` is zero in every fixture, so the per-period constant term is unfalsifiable

`objective_cost` sums `c2·p² + c1·p + c0` over the full `(T, n_gen)` dispatch array
(`multiperiod.py:673`), so each generator's constant term accrues in **every period, whether or
not it is dispatched at all**. The docstring says so deliberately. But nothing can check it:

```
case118.m       models={2.0}  maxabs(c0) = 0
case14.m        models={2.0}  maxabs(c0) = 0
case30.m        models={2.0}  maxabs(c0) = 0
case300.m       models={2.0}  maxabs(c0) = 0
case57.m        models={2.0}  maxabs(c0) = 0
case_ieee30.m   models={2.0}  maxabs(c0) = 0
(+ all four derived fixtures)
```

And the PyPSA oracle adds `c0_sum` exactly once
(`test_market_multiperiod_vs_pypsa.py:130,195`), so a `(T−1)·Σc0` discrepancy would be invisible
to `test_objective_cost_matches_pypsa` even if a fixture had one. Documented, defensible,
unverified. A unit-commitment wave will have to revisit the convention anyway.

---

## No issue — and what I looked at

### Correctness of the LP

I re-derived the index arithmetic rather than reading the docstring table and trusting it.

- **Column layout.** Tier-1 offsets (`_cols` at `multiperiod.py:381-397`) match the `addVars` call
  order at `multiperiod.py:435-449` exactly: gen, demand, charge, discharge, soc. Tier-2 offsets
  (`400-413`) match `470-482`. The `if n_gen:` / `if n_demand:` / `if n_storage:` guards are
  consistent with `per_period_dispatch = n_gen + n_demand + 3*n_storage`.
- **Row offsets.** `flow_base = T`, `soc_base = T + T·n_branch`, `limit_base`, `cyclic_base`,
  `ramp_base` (`multiperiod.py:648-652`) match the actual `_add_rows` order, including the
  `n_storage == 0` and `n_branch == 0` collapses (`_add_rows` is a no-op on an empty block).
- **Efficiency placement.** `soc[t] − soc[t−1] − η_c·charge[t] + discharge[t]/η_d == 0` is the
  standard grid-side convention (η_c multiplies grid-side charge power; grid-side discharge is
  drawn from storage at `1/η_d`). Directly confirmed rather than argued: the measured
  `y_soc = −η_d·λ` relation in F3 is exactly what that placement implies.
- **Cyclic row.** A single equality on `soc[T−1]`, not over-determined against the tier-3 row at
  `t = T−1` (charge/discharge remain free). At `T = 1` with storage it correctly forces
  `η_c·charge = discharge/η_d`, which is loss-making and therefore inactive.
- **Ramp row.** `+1` on `p[t]`, `−1` on `p[t−1]`, bounds `[−ramp_down, +ramp_up]`, one-sided limits
  getting genuine `±kHighsInf`. The dual sign the docstring claims ("negative when ramp-up binds")
  is correct under `y = ∂obj/∂rhs`, and the `test_ramp_dual...` hand derivation (−40) confirms it.
- **Storage in the flow rows.** `multiperiod.py:534-538` gives discharge the `+PTDF` injection sign
  and charge the `−PTDF` withdrawal sign at the same bus, matching the balance row at `521-529`.
  `test_storage_relieves_a_binding_flow_limit` exercises this against a rating only a local
  discharge can respect.

### Performance — no accidental O(T²)

I separated assembly from solve by wrapping `highspy.Highs.run` with a timer. Rated case118
(54 gens, 186 branches, 99 loads):

| T | total | `highs.run` | build + dual read |
|---:|---:|---:|---:|
| 12 | 1.677 s | 1.643 s | **0.035 s** |
| 24 | 6.152 s | 6.081 s | **0.070 s** |
| 48 | 27.697 s | 27.600 s | **0.097 s** |
| 96 | 142.272 s | 142.137 s | **0.135 s** |

Python-side assembly is O(T) and about 0.1% of runtime. All superlinearity (~T^2.1) is inside
HiGHS's own solve. PTDF and `pf_shift` are correctly hoisted out of the `T`-loop and computed
exactly once (`multiperiod.py:486-487`); the only repeated work is the per-period re-gather of
`ptdf[:, injection_bus]` inside `_flow_limit_rows`, which the numbers above say is not worth
hoisting.

The dense structural-zero pattern `_dense_csr` preserves is inherent here rather than wasteful —
a PTDF row is genuinely dense in the bus dimension — so the row count, not the density choice, is
what scales. Practical envelope worth handing to M6: case118 at T=24 is ~4.5 s, at T=96 ~2.5 min.

### Maintainability of the row-family boundary — partially guarded

The structural hazard is real: the row order is *declared* in a docstring table, *implemented* at
`multiperiod.py:517-582`, and *re-derived* as a hand-maintained running sum ~70 lines later, with
nothing tying the two together. A future author adding a family in the middle shifts every
downstream dual.

I tested whether that actually bites. Inserting one spurious always-slack row family between
tier 2 and tier 3 without updating the offsets: **8 tests failed**. So the contract is guarded
where storage exists — the `.reshape(n_periods, n_storage)` / `.reshape(n_periods, n_branch)`
calls raise on a length mismatch, which is a genuine (if accidental) structural check.

It is *not* guarded for a family appended after tier 6, which shifts only the PWL rows — exactly
the region F1 shows is untested. Cheap hardening that would close both: assert
`h.getNumRow()` equals the expected total before reading duals. Two of the six dual reads
(`balance`, `cyclic`) are plain slices with no reshape and would silently return the wrong rows.

Answering the question as asked — *is the row-family boundary one a future author can extend
without reading all 683 lines?* Mostly yes for the row families themselves (each is a
self-contained `_RowBlock` producer, and `_sparse_rows` is the right escape hatch for the sparse
coupling families). No for the dual offsets, which require reading both ends of the function.

### Fixture derivation rules — honest, not self-fulfilling

Asked to judge whether the new helpers' derivation rules are arbitrary:

- `tests/_periods.py` abandons an earlier two-archetype design and says why, with a measured
  feasibility boundary (uniform scaling feasible to 1.2x/0.7x; a 2-hour phase shift infeasible at
  1.0x peak). The single-curve choice is forced by `tests/_rated.py`'s own 20% margin, not chosen
  for convenience, and the module is explicit about what it gives up.
- `tests/_storage.py`'s asymmetric efficiencies (0.92/0.88) exist *specifically* so an η
  transposition can fail — it says so, and it is true: swapping `eta_charge`/`eta_discharge` in the
  SoC row failed 2 tests (control).
- The parity fixture's asymmetric ramp (10.0 up / 14.5 down) is sized against the fixture's own
  measured 14.3 MW/h natural swing so exactly one side binds — again a measurement, not a pick.

One stale cross-reference: `tests/_storage.py:129` cites *"`tests/_periods.py`'s own two-archetype
profile"*, the design `_periods.py`'s own docstring explains it abandoned. Cosmetic; fold with F3
if convenient.

### The strongest tests in the wave

Worth naming, because the F1–F4 gaps should not read as a verdict on the suite as a whole:

- `test_ramp_dual_is_recovered_on_the_identified_binding_period` and
  `test_cyclic_row_forces_the_unit_back_to_its_starting_energy` both assert **hand-derived duals**
  (−40 and +45) on purpose-built fixtures where the row demonstrably changes the answer, with the
  derivation written above the test. Sabotaging either row family fails them.
- `test_overlap_is_used_when_feasibility_requires_it` is the correct pairing for the
  `min(charge, discharge) ≈ 0` invariant: it shows the identical readback returning >15 MW on the
  same code path, so the near-zero reading is a measurement rather than an absence.
- `_identity_rhs` (`test_market_multiperiod.py:239`) computes the settlement identity's right-hand
  side from a **second, independent** array-level solve with a freshly recomputed PTDF, so the
  per-period identity assertions are a proof rather than a restatement. This is the discipline the
  rest of the suite should copy — and the four fold items above are precisely where it was not
  applied.

### Jobs D3 (`SolveRequest` widening)

Clean, and the right call. `Scenario` now genuinely carries something a bare `Network` cannot
supply (`periods`), which is exactly the trigger the M4 registry docstring named for revisiting
the decision.

- `resolved_scenario` (`jobs/models.py:133-152`) is the single wrap point; the `Runner` signature
  change to `(Scenario, options) -> result` is uniform across all six kinds, and the four
  network-only runners read `.network` off the scenario rather than special-casing.
- `run.py:151-160` correctly catches the `NetworkValidationError` the wrap can now raise (from
  re-running `Network`'s after-validator on a mutated network) and keeps it a graceful
  `VALIDATION` failure rather than letting it cross `run()`'s boundary. The comment explaining why
  is accurate.
- No consumer reads `request.network` directly any more: `grep -rn "request.network" src/` returns
  only comments and the guarded branch inside `resolved_scenario`.
- Sharing `gen_cost_coeffs` and promoting `_load_bid_coeffs` → `load_bid_coeffs` is exactly the
  reuse the M4 review's Duplication FLAG asked for, applied to the demand side.

One residual, low: `run()` re-validates `scenario.network` but never re-checks `Scenario`'s own
cross-field invariant (`_check_period_load_refs`), so `periods` mutated in place after
construction is not re-validated. Harmless today — `_period_load_mw` skips unresolvable ids
(`market/multiperiod.py:110-112`) — but it is an asymmetry with the network path.

---

## Appendix: sabotage sweep, full results

| # | Sabotage | Suite | Result |
|---|---|---|---|
| S1 | tier-2 PWL column stride removed (`base = n_dispatch_total`) | unit | 590 passed — **powerless** |
| S2 | elastic double-count subtraction disabled in the period branch | unit | 590 passed — **powerless** |
| S3 | per-period Hessian demand block zeroed | unit | 1 failed, 589 passed — caught |
| S4 | `eta_charge` / `eta_discharge` swapped in the SoC row | multiperiod | 2 failed, 53 passed — caught |
| S5 | ramp row bounds `np.tile` → `np.repeat` | unit + parity | 599 passed — **powerless** |
| S6 | storage power-limit bounds `np.tile` → `np.repeat` | unit + parity | 599 passed — **powerless** |
| S7 | hypograph rows pinned to period 0 | unit + parity | 599 passed — **powerless** |
| S8 | epigraph rows pinned to period 0 | unit + parity | 599 passed — **powerless** |
| S9 | spurious row family inserted mid-stack, offsets stale | unit + parity | 8 failed, 591 passed — caught |

S3, S4 and S9 are the controls: they confirm the sweep can detect a fault, so the six green rows
are a property of the fixtures rather than of the method.
