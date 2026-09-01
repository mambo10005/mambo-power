# M5 R1 fold A — code and unit tests

Worktree `C:\Claude Projects\mambo-power-m5`, branch `wave/05-multiperiod`, from `13aff40`.
Two commits, both staged with explicit paths (`git add <file> ...`, never `-A`/`-a`):

| commit | contents |
|---|---|
| `0ed05b2` | F2 fix; the T>1 coverage that hid it and F1/F4 |
| `c4de00c` | `Period` range, storage sizing validation, dual-sign prose, stale docstrings + schema snapshot, row-count guard |

Files touched, all inside the ownership boundary (`src/mambo_power/**`, `tests/unit/**`):
`src/mambo_power/opf/multiperiod.py`, `src/mambo_power/results/multiperiod.py`,
`src/mambo_power/model/{entities,network,scenario}.py`,
`tests/unit/{test_opf_multiperiod,test_market_multiperiod,test_period_scenario,test_model_invariants}.py`,
`tests/unit/snapshots/network.schema.json`. Nothing under `docs/`, `examples/`, `tests/_*.py`
or `tests/parity/` was read-modified or staged.

## Counts

Baseline measured directly, before any edit, on a clean tree at `13aff40`:

```
$ uv run --no-sync python -m pytest tests/unit -q
590 passed in 49.62s
```

At `c4de00c`:

```
$ uv run --no-sync python -m pytest tests/unit -q
604 passed in 183.93s

$ uv run --no-sync python -m pytest -q          # whole suite, sibling's docs work in the tree
815 passed, 10 warnings in 294.63s
```

604 − 590 = **14**, which is exactly this slice's arithmetic (6 + 2 + 1 + 4 + 1, minus the one
test whose rule item 2 deliberately reverses). The 815 figure includes `m5-fold-b`'s
uncommitted work and is **not** a clean baseline for this slice; the `tests/unit` figure is.

```
$ uv run --no-sync ruff check .        -> All checks passed!
$ uv run --no-sync ruff format --check .  -> 154 files already formatted
$ uv run --no-sync mypy                -> Success: no issues found in 46 source files
```

## 1. F2 — a `Period` override on a bid-carrying load was a no-op

Reproduced first, on `case14` with a bid on `load-2` only and an 0.8/1.2 profile on both loads:

```
status Optimal
load-2 base=  21.700 expected 17.360/26.040 SERVED = 21.7000 / 21.7000  bid=YES
load-3 base=  94.200 expected 75.360/113.040 SERVED = 75.3600 / 113.0400  bid=no
```

Cause as reported: the elastic column's upper bound stayed at `arr.load_p_max_pu * base_mva`
while the period's own value was already subtracted from the fixed-load total, so the two
cancelled exactly. Fixed at `src/mambo_power/opf/multiperiod.py` — `demand_p_max` is now
`(n_periods, n_demand)`, taken from `period_load_mw[:, elastic_idx_arr]` when a profile is
given and tiled from the base otherwise (so the `period_load_mw=None` path, and with it AC-4's
exactness, is byte-identical). `demand_p_min` does **not** move: `load_p_min_pu` is not derived
from `p_mw`. The module docstring's "Period-varying data" paragraph is rewritten to say that
one array moves two things, and why.

After the fix, same probe:

```
load-2 base=  21.700 expected 17.360/26.040 SERVED = 17.3600 / 21.8094  bid=YES
```

17.36 at t=0 is the bound; 21.8094 at t=1 is the *bid* clearing interior, because
`tests/_bids.py` anchors that curve's marginal value to the fleet ceiling at the load's base
21.7 MW — above that quantity the curve is worth less than the clearing price. That is the
intended semantics ("the curve is fixed by hour, the quantity anchor is not") behaving
correctly, not a residue of the bug; the guard tests below use a flat bid so the bound is the
only thing that can move the answer.

Guards added:

* `tests/unit/test_opf_multiperiod.py::test_a_period_profile_moves_an_elastic_columns_upper_bound`
  — array level, hand-derived: flat 80 $/MWh bid against a 10 $/MWh generator, profile
  ×0.8/×1.2, so the elastic load must serve 80 then 120 MW and the fixed one 40 then 60.
* `tests/unit/test_market_multiperiod.py::test_a_period_override_moves_a_bid_loads_quantity_too`
  — the same claim through `Scenario`/`Period`/`Load.bid`, plus an explicit assertion that the
  bid load does **not** sit at its base 100 MW in both periods (the bug's signature).

## 2. `Period.load_p_mw` is no longer narrower than the field it overrides

```
$ uv run --no-sync python -c "... case300 ..."
negative loads: 8 ['load-51', 'load-207', 'load-250', 'load-281', 'load-323', 'load-552', 'load-664', 'load-1200']
identity Period -> ValidationError load_p_mw
```

The `>= 0` field validator is dropped from `Period` (`allow_inf_nan=False` kept), and both the
class docstring and the field description now state the range rule and its reason.

`tests/unit/test_period_scenario.py::test_period_rejects_negative_load_p_mw` — the test that
pinned the old rule — is replaced by three:
`test_period_accepts_a_negative_load_p_mw`, `test_period_still_rejects_a_non_finite_load_p_mw`
(the half of the old contract that survives), and
`test_the_case300_identity_profile_is_a_valid_scenario`. That file's own module docstring also
claimed "nothing reads these fields yet" and was corrected.

At the solver level,
`tests/unit/test_market_multiperiod.py::test_a_flat_case300_horizon_clears_and_matches_the_period_less_solve`
proves the flat horizon clears and that each period reproduces the period-less solve — measured
agreement 7.9e-13 max per-generator, objective exactly 2× (`rel=1e-12`).

## 3. D7 — storage sizing validated

Measured on the fold's own two-unit network before the fix:

```
energy_mwh=0.0      validation PASSED  solve Optimal  charge=-0.000 soc=0.000
p_max_mw=0.0        validation PASSED  solve Optimal  charge= 0.000 soc=0.000
energy_mwh=-15.0    validation PASSED  solve Infeasible
p_max_mw=-5.0       validation PASSED  solve Infeasible
```

`p_max_mw` and `energy_mwh` now join `validate_network`'s BAD_RANGE catalog requiring `> 0`,
in the same loop shape and message shape `ramp_up_mw`/`ramp_down_mw` use, with the unit id in
the message. Four parametrised cases added to `tests/unit/test_model_invariants.py`.

## 4. F1 — the PWL / tier-2 path now has T ≥ 2 coverage

Two tests, both against an oracle rather than a readback: with no storage and no ramp limit a
horizon is *uncoupled*, so period `t` must equal a standalone `dc_opf` on the network carrying
that period's own loads — a separate builder reached through a separate call.

* `test_pwl_generator_costs_are_period_specific_at_t2` — `case14_pwl.m` at T=2, factors
  0.9/1.15, against two independent `dc_opf` solves. Asserts total cost, each period's balance
  dual and each period's total dispatch. Per-generator dispatch is deliberately **not**
  asserted: that fixture's own module docstring records a genuine LP tie between gen-2's and
  gen-3's 30 $/MWh segments, so the split is not unique.
* `test_pwl_demand_bids_are_period_specific_at_t2` — the first time `demand_pwl_bids` reaches
  this builder anywhere in the repository. Hand-derived two-regime horizon: bound 30 MW (the
  bound binds, 30 served) then bound 90 MW (the bid binds, 40 served), cross-checked against
  two `dc_opf` solves.

## 5. F4 — heterogeneous units

Two hand-built networks, each derived on paper before it was ever solved; both derivations
matched the solver on the first run.

* `_hetero_storage_network` / `test_two_storage_units_keep_their_own_power_limits` — st_small
  P=10 E=10 η=0.8, st_big P=30 E=30 η=1.0, three periods, load [20, 100, 20]. Charging is worth
  it only while `gcheap`'s 40 MW of headroom lasts, and 40 MW is exactly what the two units take
  together, each at its own rating. `objective = 10*(60+60+20) + 50*3.6 = 1580`.
* `_hetero_ramp_network` / `test_two_ramped_generators_keep_their_own_ramp_limits` — gA up 20 /
  down 30, gB up 5 / down 8, gC unramped, four periods, load [0, 100, 200, 20]. Every period is
  forced: t0 by non-negativity, t1/t2 by the ramp-up ceilings, t3 by the ramp-down floors.
  `objective = 7725 + 15450 + 220 = 23395`.

**Deviation from the brief, deliberate.** Item 5 asked for *one* network carrying both kinds of
heterogeneity. I attempted it and abandoned it: a ramp-down limit tight enough to bind forces a
generation floor in the last period, and the cyclic SoC row forbids the net absorption that
floor requires (storage can only *release* energy once its SoC is spent, and charge/discharge
overlap absorbs nothing net), so every combined design I tried went infeasible rather than
interesting. Two networks, two tests, both sabotages red — the intent is discharged; the cost
is one extra fixture function in test code.

## 6. F3 — the shipped dual signs

Measured, arbitrage horizon (η_d = 0.9, LMP 10 then 50, E = 15 MWh):

```
t=0  soc 15.0  soc_dual -11.11111  energy_bound_dual -33.88889  lmp 10.0
t=1  soc  0.0  soc_dual -45.00000  energy_bound_dual  45.00000  lmp 50.0
```

`soc_dual` is `-η_d·LMP`, the **negative** of what the prose promised. Both sites I own now
state the convention explicitly, in `GenPeriodDispatchResult.ramp_dual`'s style:
`MultiperiodDuals.soc_balance` in `src/mambo_power/opf/multiperiod.py` and the frozen
`StorageDispatchResult.soc_dual` field description in `src/mambo_power/results/multiperiod.py`.

`energy_bound_dual`'s "0 unless the energy capacity binds" is falsified by the t=1 row above —
the unit is **empty**, 15 MWh below its cap, and reports 45.0. Both that field and
`MultiperiodDuals.storage_soc_bound` now read "non-zero at either end of `[0, energy_mwh]`;
0 only where the state of charge is strictly interior".

`tests/unit/test_market_multiperiod.py::test_the_storage_dual_signs_are_the_ones_the_fields_describe`
pins both statements.

**The third site is not fixed and is not mine**: `docs/manual/multiperiod.md:166` still reads
"`soc_dual` is that row's shadow price — the marginal value of one more MWh". `m5-fold-b` owns
that file. Flagged to the lead.

## 7. D2/D3/D4 — stale docstrings, and the schema snapshot

* `Storage`: "Schema-present; no M1 solver reads it" -> names `market.multiperiod` and what it
  builds per unit per period.
* `Period`: the "nothing reads this field yet, wave M5 Design item 1" clause is gone (rewritten
  wholesale as part of item 2); no internal planning language remains in the public docstring.
* `Load`: "`bid` is model-present; only `market.nodal` reads it" -> names both market modules.
  The `Load.bid` **field description** carried the same false claim and is corrected too, and
  `Load.p_mw`'s description now states the meaning F2 turns on: with a bid it is the maximum
  servable quantity, and a `Period` override of it moves that maximum.

Snapshot regenerated with `MAMBO_UPDATE_SNAPSHOTS=1`; diff read before committing:

```
 tests/unit/snapshots/network.schema.json | 8 ++++----
 1 file changed, 4 insertions(+), 4 deletions(-)
```

Four `"description"` strings (Load's class doc, `Load.p_mw`, `Load.bid`, Storage's class doc).
No `properties`, `type`, `required`, `$defs` or ordering change — description text only,
confirmed by reading the full diff, not the stat line.

## 8. The row-order contract is now asserted

`multiperiod_dc_opf` computes the expected total from the docstring's tier table and asserts it
against `h.getNumRow()` before any dual index is read. See the item-8 sabotage pair below for
why this is not decoration.

## Revert-and-watch table

Every sabotage was applied in a **detached scratch worktree**
(`git worktree add --detach .../sab-folda HEAD`), never in the live tree, with pytest run from
the live worktree under `PYTHONPATH=<scratch>/src`. That the scratch copy is the one that loads
was proved, not assumed:

```
$ PYTHONPATH="$SCRATCH/src" uv run --no-sync python -c "import importlib; print(importlib.import_module('mambo_power.opf.multiperiod').__file__)"
C:\...\scratchpad\sab-folda\src\mambo_power\opf\multiperiod.py
```

| # | sabotage | guard tests | pre-existing tests |
|---|---|---|---|
| F2 | `demand_p_max` back to `arr.load_p_max_pu` | **2 failed** | 55 passed |
| F1a | `base = n_dispatch_total + t*per_period_free` -> `n_dispatch_total` | **2 failed** | 55 passed |
| F1b | epigraph rows pinned to `gen_cols[0]`/`cost_col_of[0]` | **1 failed**, 1 passed | 55 passed |
| F1c | hypograph rows pinned to period 0 | **1 failed**, 1 passed | 55 passed |
| F4a | `np.tile(storage_p_max, T)` -> `np.repeat` | **1 failed** | 55 passed |
| F4b | `np.tile(down/up, T-1)` -> `np.repeat` | **1 failed** | 55 passed |
| 2 | `>= 0` validator restored on `Period.load_p_mw` | **3 failed** | — |
| 3 | storage sizing entries removed from BAD_RANGE | **4 failed** | — |
| 6 | `soc_dual=-float(duals.soc_balance[t, s])` | **1 failed** | — |
| 8a | extra row family appended after tier 6 | **33 failed**, 5 passed | — |
| 8b | the same, *with the new assertion also removed* | — | **63 passed** |

"pre-existing tests" is the 55 tests that existed in `test_opf_multiperiod.py` and
`test_market_multiperiod.py` before this fold, with the six new ones deselected: every one of
the six shipped defects is invisible to them, which is why they shipped. F1b fails only the
generator-side test and F1c only the demand-side one, each being the side it breaks.

Row 8b is the whole argument for item 8: the same unaccounted row family that trips the
assertion on 33 tests is caught by **nothing else at all** — remove the assertion too and the
full 63-test multiperiod suite goes green.

Restored afterwards and verified:

```
=== restored
6375cad6372743142601d89ad85abcead6d3c2bf4f18e4f221e690dc7006e6f2 *<scratch>/src/mambo_power/opf/multiperiod.py
6375cad6372743142601d89ad85abcead6d3c2bf4f18e4f221e690dc7006e6f2 *<live>/src/mambo_power/opf/multiperiod.py
  match  src/mambo_power/model/scenario.py
  match  src/mambo_power/model/network.py
  match  src/mambo_power/market/multiperiod.py
  match  src/mambo_power/opf/multiperiod.py
```

The scratch worktree has been removed; `git worktree list` shows only the two real ones.

## Left for someone else

1. **`docs/manual/multiperiod.md:166`** — F3's third site, `m5-fold-b`'s file (§6 above).
2. **A negative override on a bid-carrying load.** With F2 fixed, `Period.load_p_mw = -5` on a
   load that bids produces the column bound `[0, -5]` and HiGHS returns `Infeasible` with no
   message naming the cause. I did **not** add new semantics for this mid-fold: `dc_opf` has
   behaved identically for a negative `Load.p_mw` with a bid since M4, so multiperiod now
   simply matches its sibling. It is a wave-M6 question (is a negative elastic load meaningful
   at all, and if not, should `validate_network` reject the combination?), not a fold one.
3. **A worktree I pruned.** `.../scratchpad/sabotage` was registered at `13aff40` with its
   directory already missing (`git worktree list` reported it `prunable`); I pruned it and used
   `sab-folda`. Harmless if it was a finished agent's leftover — detached, no branch — but
   recorded here in case it is expected back.
