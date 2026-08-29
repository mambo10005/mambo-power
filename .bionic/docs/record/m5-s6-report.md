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

# M5 S6 — fixtures-oracle (W7, AC-6)

Slice S6 `fixtures-oracle`. Role: implementor. Worktree `C:\Claude Projects\mambo-power-m5`,
branch `wave/05-multiperiod`, base `faba273` (S1-S5 all landed). Commit **`ad0ad7e`** —
`feat(m5/S6): fixtures-oracle — 24-period profile, storage sizing, PyPSA multiperiod parity`.
Not pushed.

**AC-6 holds.** All 9 committed parity tests pass against a genuine PyPSA multi-period oracle
(case14, 24 periods, rated branches, ramp limits and lossy storage both active). Every factual
claim below carries the command that produced it and that command's output, or the label
`unverified`.

Two real findings surfaced along the way and are reported rather than hidden: a PyPSA
oracle-construction gotcha (transformers + lines rated together makes PyPSA's own QP infeasible
on this fixture) and a fixture-design course correction (a two-archetype load profile makes the
24-period LP infeasible on case14's tightly-margined mesh). A third, smaller finding — a storage
efficiency *transposition* does not move the parity residual past noise on this fixture — is
disclosed as a named gap, not concealed.

---

## 1. What changed

| file | status | lines |
|---|---|---|
| `tests/_periods.py` | new | 97 |
| `tests/_storage.py` | new | 103 |
| `tests/parity/test_market_multiperiod_vs_pypsa.py` | new | 378 |
| `tests/unit/test_periods_helper.py` | new | 103 |
| `tests/unit/test_storage_helper.py` | new | 96 |

```
$ git show --stat ad0ad7e
 tests/_periods.py                                   |  97 +++
 tests/_storage.py                                    | 103 +++
 tests/parity/test_market_multiperiod_vs_pypsa.py     | 378 +++
 tests/unit/test_periods_helper.py                    | 103 +++
 tests/unit/test_storage_helper.py                    |  96 +++
 5 files changed, 777 insertions(+)
```

`tests/_rated.py` and `tests/_bids.py` are untouched (reused exactly as briefed):

```
$ git diff --stat -- tests/_rated.py tests/_bids.py
(empty)
```

Nothing under `src/`, `tests/unit/test_jobs.py`, or `src/mambo_power/jobs/*` was touched by this
slice — those diffs in the shared worktree belong to S7, running concurrently, and were left
unstaged:

```
$ git status --short
 M src/mambo_power/jobs/models.py      <- S7, not committed here
 M src/mambo_power/jobs/registry.py    <- S7, not committed here
 M src/mambo_power/jobs/run.py         <- S7, not committed here
 M tests/unit/test_jobs.py             <- S7, not committed here
```

---

## 2. `tests/_periods.py` — one course correction, disclosed

### 2.1 The first design, and why it broke

The first version alternated two phase-shifted diurnal curves across `Network.loads` (odd/even
split), aiming for the locational diversity spec Design item 4 names as the reason "scalar
system-wide load scaling" was rejected for `Period`'s own shape. Measured directly on case14
(`tests/_rated.py`'s derived ratings, no storage, no ramp — the plainest possible probe):

```
$ ... two-curve profile, peak=1.0 (i.e. no amplitude change at all), 2-hour phase shift ...
multiperiod_dc_opf: HiGHS reported model status 'Infeasible'
```

Root cause, isolated by bisection: `RATING_MARGIN` (1.2) is applied uniformly to *every*
branch's own base-case flow, and case14's meshed core has branches sitting at exactly that 20%
headroom in the base case itself (e.g. `branch-19`, rated 1.809 MVA against a 1.507 MVA base
flow). Any per-load *divergence* from the ratio the ratings were derived from — even with the
system-wide total unchanged — pushes at least one such branch past its own rating, and
redispatch alone cannot bring it back under while also respecting every other branch's own tight
margin. This is a genuine, reproduced fact about this fixture's topology, not a bug in the
helper.

### 2.2 The fix, and why it is not the same failure as the rejected alternative

A single system-wide raised-cosine curve, `peak=1.2x` / `trough=0.7x` of each load's own
committed `p_mw`, feasible up to (and pinned with margin below) the infeasibility boundary found
by bisection. This keeps every branch's flow *proportional* to the one multiplier, which is what
keeps the whole 24-period horizon simultaneously feasible.

This is not the failure spec Design item 4 warns against ("congestion binds in all or none").
Measured directly (§4 below, and the committed
`test_congestion_binds_in_some_periods_and_not_others`): 10 of 24 hours congest, 14 do not — a
real split, not all-or-nothing. What a single curve gives up is locational diversity in the
*load pattern*; `tests/_storage.py`'s siting rule supplies the remaining locational content this
wave's AC-6 fixture needs.

### 2.3 Unit tests

```
$ uv run --no-sync pytest -q -p no:cacheprovider tests/unit/test_periods_helper.py
9 passed
```

Proves: 24 periods by default, every period names every load, the swing is real (not a flat
line — every load's own max/min across the horizon equals `p_mw * PEAK_MULTIPLE` /
`p_mw * TROUGH_MULTIPLE` exactly), the curve genuinely peaks/troughs where documented, no
mutation of the input network, determinism, rejects a loadless network and a non-positive period
count, and `n_periods` wraps the 24-hour cycle correctly (`periods[0] == periods[24]`).

---

## 3. `tests/_storage.py`

Single unit, sized as `p_max_mw = 0.15 * sum(Load.p_mw)`, `energy_mwh = p_max_mw * 4.0` (a
4-hour duration, the standard grid-scale Li-ion benchmark). `soc_initial = 0.5` (half-charged, so
the cyclic condition can move in either direction from hour 0). Efficiencies **deliberately
asymmetric**, `efficiency_charge=0.92` / `efficiency_discharge=0.88` — S4's own sabotage sweep
(plan Assumption A10) found that an *equal*-efficiency fixture makes an `eta_c`/`eta_d` swap a
silent no-op; distinct values here are what let a transposition sabotage on this term have any
chance of showing.

Default siting: the bus with the largest aggregate load (deterministic, no per-fixture
hand-picking). On case14: `bus-3` (94.2 MW, `load-3`), confirmed in
`test_default_siting_is_the_bus_with_the_largest_aggregate_load`.

```
$ uv run --no-sync pytest -q -p no:cacheprovider tests/unit/test_storage_helper.py
9 passed
```

Proves: sizing anchored to the network's own committed total load, efficiencies genuinely
distinct, `soc_initial` a genuine fraction, default siting is the documented rule, an explicit
`bus_id` override is honoured, an unknown `bus_id` and a loadless network both raise, no mutation
of the input, determinism.

---

## 4. AC-6 — the PyPSA multi-period oracle

### 4.1 Fixture: case14, rated, storage, ramp

`tests/parity/test_market_multiperiod_vs_pypsa.py`'s own fixture: `rated_network(case14)` (W7,
unchanged) + `storage_for_network(net, bus_id="bus-14")` (an explicit override of the general
default — measured, scratchpad, to be the case14 bus with the largest LMP peak-to-trough spread
under this profile, `unverified` beyond the scratchpad probe since the spread number itself was
not committed) + `gen-1.ramp_up_mw=10.0` / `ramp_down_mw=14.5` (deliberately asymmetric, sized
below/above gen-1's own natural ~14.3 MW/h unconstrained swing so the up side binds and the down
side stays slack — the one-sided-binding shape S4's and S5's own sabotage sweeps found necessary
to catch a ramp transposition).

### 4.2 The AC-6 fixture-fidelity precondition — proven, not assumed

```
$ uv run --no-sync pytest -q -p no:cacheprovider tests/parity/test_market_multiperiod_vs_pypsa.py::test_congestion_binds_in_some_periods_and_not_others -v
PASSED
```

Binding hours (>= 99.9% of rating on at least one branch): `13, 14, 15, 16, 17, 18, 19, 20, 21,
22` (10 of 24). Slack hours (every branch < 95% of its own rating): `0-12, 23` (14 of 24).
Example evidence at the peak hour (t=18):

| branch | flow (MW) | rating (MVA) |
|---|---|---|
| branch-11 | 8.074 | 8.074 |
| branch-14 | -1.000 | 1.000 |
| branch-16 | 6.926 | 6.926 |
| branch-18 | -3.874 | 3.874 |

Every branch that binds across the whole horizon is checked to be one of the 17 `Line`s PyPSA's
own oracle rates (§4.4) — `binding_ids.isdisjoint(transformer_ids)` asserted at every binding
hour, so the comparison is never asked to agree on a constraint the oracle does not itself
enforce.

```
$ uv run --no-sync pytest -q -p no:cacheprovider tests/parity/test_market_multiperiod_vs_pypsa.py::test_ramp_and_storage_are_both_genuinely_engaged -v
PASSED
```

gen-1's ramp row binds (nonzero dual) on 7 consecutive period transitions; storage charges at
two hours and discharges at another, both nonzero, cyclic-consistent (SoC returns to
`soc_initial` at the horizon's end).

### 4.3 Measured residuals and pinned tolerances

```
$ uv run --no-sync pytest -q -p no:cacheprovider tests/parity/test_market_multiperiod_vs_pypsa.py -v
9 passed in 86.47s
```

| quantity | measured worst-case | pinned tolerance | margin |
|---|---|---|---|
| objective cost (relative) | 4.35e-13 | 1e-9 | ~2,300x |
| generator dispatch | 3.01e-4 MW | 1e-2 MW | ~33x |
| storage net power (discharge - charge) | 1.10e-4 MW | 1e-2 MW | ~91x |
| state of charge | 1.25e-4 MWh | 1e-2 MWh | ~80x |
| LMP | 4.24e-5 $/MWh | 1e-3 $/MWh | ~24x |

All five figures were measured by a scratchpad probe against the exact committed fixture before
the tolerances were pinned in the committed test file (the same "measure and record, don't
assume a round number" discipline `tests/parity/test_opf_vs_pypsa.py` and
`tests/parity/test_market_nodal_vs_pandapower.py` both use).

### 4.4 The PyPSA oracle-construction finding

case14 has three tap-ratio transformers (raw branch rows 8, 9, 10 — `bus4-bus7`, `bus4-bus9`,
`bus5-bus6`; PyPSA's `import_from_pypower_ppc` splits them into `Transformer` components `T0`,
`T1`, `T2`, distinct from the 17 `Line`s). Setting `tests/_rated.py`'s own derived rating as
`s_nom` on **both** the lines and the transformers simultaneously makes PyPSA's constrained QP
genuinely infeasible on this fixture:

```
$ ... single-snapshot base case, no ramp, no storage, multiplier 1.0 (the exact dispatch the
    ratings were derived from), lines AND transformers both rated at their exact tests/_rated.py
    value ...
Model status: Infeasible

$ ... same, uniform slack swept 1.1x, 1.3x, 1.5x, 2.0x, 3.0x on every rating ...
slack=1.1: warning infeasible
slack=1.3: ok optimal
slack=1.5: ok optimal
slack=2.0: ok optimal
slack=3.0: ok optimal

$ ... lines constrained ALONE (transformers at overwrite_zero_s_nom) ...
lines only -> ok optimal
$ ... transformers constrained ALONE (lines at overwrite_zero_s_nom) ...
xfmr only -> ok optimal
$ ... both together, exact tests/_rated.py values, no slack ...
both -> warning infeasible
```

So it is not a numerical near-miss (a small slack does not fix it; the base-case dispatch itself
— known feasible for every individual rating with 17-20% headroom — is rejected as infeasible by
PyPSA's own constructed QP), and it is not a bug in either component type alone (each is
independently fine). Root cause **not fully diagnosed** — a plausible but `unverified` candidate
is that PyPSA's linear power flow references a transformer's `s_nom` against a per-unit base
that differs from the one this repository's own PTDF-based flow uses, so a rating this repo
derives as "safe" is not, from PyPSA's own perspective, quite what it is fed. This module routes
around it by rating **only the 17 lines** in PyPSA's oracle; `mambo_power`'s own engine keeps
rating all 20 branches exactly as `tests/_rated.py` derives them, unchanged. This is safe for
*this* fixture's own claim (§4.2's disjointness check), not a general fix, and is documented as
such in the module docstring.

### 4.5 Sabotage sweep — against the TRUE oracle held fixed

Per the brief's own instruction, each sabotage perturbs **only** the network fed to
`mambo_power`'s own engine; the PyPSA oracle is built once from the correct, unperturbed network
and held fixed, so a divergence is a genuine sensitivity, not two wrong answers agreeing.

```
$ ... scratchpad sabotage sweep, worst_gen_residual / worst_storage_residual vs the true oracle ...
BASELINE:                                       worst_gen=0.000301 MW  worst_storage=0.000110 MW  obj_diff=0.0000
SABOTAGE ramp 25/25 (loosened):                 worst_gen=9.202001 MW  worst_storage=0.782662 MW  obj_diff=29.1111
SABOTAGE ramp None (removed):                   worst_gen=9.202001 MW  worst_storage=0.782662 MW  obj_diff=29.1111
SABOTAGE eff swapped (0.88 charge/0.92 disch.): worst_gen=0.000314 MW  worst_storage=0.000124 MW  obj_diff=0.0000
SABOTAGE eff both 0.70 (wrong magnitude):       worst_gen=2.159022 MW  worst_storage=1.032529 MW  obj_diff=0.9976
SABOTAGE branch-14 rating 1.0 -> 20.0:          worst_gen=6.837734 MW  worst_storage=2.222602 MW  obj_diff=8.7390
SABOTAGE branch-18 rating 3.874 -> 20.0:        worst_gen=2.101072 MW  worst_storage=0.049199 MW  obj_diff=1.1598
```

Against the pinned tolerances (dispatch 1e-2 MW, storage 1e-2 MW): **ramp** goes red by ~900x,
**storage-efficiency-magnitude** by ~200x, **branch-14 rating** by ~680x, **branch-18 rating** by
~210x. All three of the brief's named terms (ramp, storage efficiency, branch rating) are proven
load-bearing.

**The one survivor, disclosed rather than hidden.** Swapping the two *true* efficiency values
(0.88 charge / 0.92 discharge, instead of the committed 0.92/0.88) does **not** move the residual
past baseline noise (3.14e-4 MW vs the baseline's own 3.01e-4 MW). Storage's usage on this
fixture is small (~0.5-1 MW against a 38.85 MW rating) and its charge/discharge magnitudes are
close enough that swapping which of the two efficiencies applies to which direction is a
near-no-op at this scale — a genuine, measured property of this fixture, not a defect in the
sabotage method. A **magnitude** sabotage on the same field (§ above) is clearly caught. This
mirrors S5's own disclosed finding that the `periods=None` route is the one sabotage survivor on
its fixture ("a finding, not a hole") — reported per the REPORTING CONTRACT rather than tuned
away.

---

## 5. TDD, RED before GREEN

The committed parity test's *first* run — against the first (two-archetype) version of
`tests/_periods.py` — failed all 9 tests:

```
$ uv run --no-sync pytest -q -p no:cacheprovider tests/parity/test_market_multiperiod_vs_pypsa.py -v
FAILED test_solve_multiperiod_converges_optimal
  AssertionError: multiperiod_dc_opf: HiGHS reported model status 'Infeasible'
FAILED test_congestion_binds_in_some_periods_and_not_others
FAILED test_ramp_and_storage_are_both_genuinely_engaged
  AssertionError: gen-1's ramp row never binds -- the fixture cannot test the ramp term
FAILED test_pypsa_itself_converges_optimal
  AssertionError: ('warning', 'infeasible')
... (9 failed)
```

Root-caused to §2.1's finding (not a test-writing mistake — the module-scoped fixture's own
`solve_multiperiod` call was genuinely infeasible). `tests/_periods.py` rewritten per §2.2, all 9
green on the next run (§4.3).

---

## 6. Gates

```
$ uv run --no-sync pytest -q -p no:cacheprovider tests/unit/test_periods_helper.py tests/unit/test_storage_helper.py tests/parity/test_market_multiperiod_vs_pypsa.py
27 passed

$ uv run --no-sync pytest -q -p no:cacheprovider
795 passed, 10 warnings in 222.53s (0:03:42)
```

795 = 747 briefed baseline + 27 this slice's own (9+9+9) + 21 from S7's concurrent, uncommitted
in-flight jobs work in the same shared worktree — **this total includes S7's edits and is
reported as such, not as clean evidence of this slice alone.** The clean, scope-isolated evidence
is the 27/27 own-file run above and the full-repo lint/format runs below, both of which are
unaffected by whether S7's edits are present.

```
$ git diff --stat -- tests/
(only this slice's own new files appear as additions; every pre-existing test file, including
tests/unit/test_market_multiperiod.py, tests/unit/test_market_nodal.py, tests/_rated.py and
tests/_bids.py, is byte-identical to HEAD -- confirmed above, §1)

$ uv run --no-sync ruff check .
All checks passed!

$ uv run --no-sync ruff format --check .
151 files already formatted

$ uv run --no-sync mypy
Success: no issues found in 46 source files
```

`mypy` is scoped to `files = ["src"]` in `pyproject.toml` — this slice touches only `tests/`, so
the check is structurally unaffected by anything done here; recorded for completeness, not as a
claim about this slice's own files.

**Zero pre-existing tests modified.** No `src/` file touched. `tests/_rated.py` reused
byte-for-byte unchanged, as briefed.

---

## 7. Flags and carry-overs

* **FLAG (informational)** — the PyPSA transformer/line rating interaction (§4.4) is a real,
  reproduced gotcha that a later wave's own PyPSA oracle work (any wave adding a transformer-rich
  fixture to a rated-branch parity test) should expect to hit again. Root cause not diagnosed
  here; worth a dedicated research pass if a future wave needs transformers rated in a PyPSA
  oracle rather than routed around.
* **Named gap, not a defect** — a storage efficiency *transposition* (as opposed to a magnitude
  change) is not caught by this fixture's own sabotage sensitivity (§4.5). If a future wave wants
  this specific sensitivity, the fixture would need a storage unit whose charge and discharge
  magnitudes are more decisively asymmetric than this one's ~0.5-1 MW usage allows without
  materially changing case14's already-tight congestion balance — not attempted here, given the
  three required terms (ramp, storage-magnitude, rating) are all already proven load-bearing.
* **Measured, not structural** — `STORAGE_BUS = "bus-14"` in the AC-6 fixture (an override of
  `tests/_storage.py`'s own general default) was picked from a scratchpad LMP-spread measurement,
  `unverified` beyond that scratchpad probe since the specific spread figures were not committed
  anywhere. The *engagement* itself (storage genuinely charges/discharges) is proven by the
  committed `test_ramp_and_storage_are_both_genuinely_engaged`, independent of why bus-14 was
  chosen.
* No defect was found in `market/multiperiod.py`, `opf/multiperiod.py`, or any other `src/`
  module. `tests/_rated.py` needed no change to be reusable exactly as briefed.
