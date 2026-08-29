# M5 research — multiperiod groundwork

Wave M5 "multiperiod" of the mambo-power epic, Step 1 research. Read-only; written 2026-08-25
against repo `C:\Claude Projects\mambo-power` @ `e88752c` (branch `epic/01-foundation`, M4
"nodal-market" merged — `model.Load.bid`/`Scenario`, `opf.dc_opf`'s demand-side extension,
`market.nodal`, `jobs` kind `market.nodal` all present and read at their current, merged shape),
highspy (version string unavailable via `highspy.__version__`, importable), pandapower 3.3.0,
PyPSA 1.2.4 (`uv run --no-sync python -c "import pypsa; print(pypsa.__version__)"` → `1.2.4`),
scipy (bundled with the `.venv`) — all from `.venv` (`uv` at
`C:\Users\mambo\AppData\Roaming\Python\Python314\Scripts\uv.exe`). No source files touched; only
reads and `uv run --no-sync python <scratchpad>/probe_*.py` / `pytest`.

Headline (the rest is evidence):

- **§1 verdict: YES — PyPSA is a usable AC-6 oracle for M5, and A4 was already closed in M3,
  before either m4-research.md or continuation-m4.md were written.** `tests/parity/
  test_opf_vs_pypsa.py` (committed at `8fc8581`, "chore(m3/R1): fold audit finding — PyPSA
  parity…") root-caused and fixed the infeasibility M3's own frozen research doc reported as
  unresolved: `import_from_pypower_ppc` populates `n.generators.p_set` from MATPOWER's raw,
  unbalanced base-case `Pg`, and PyPSA's optimizer treats a non-null `p_set` as a **fixed**
  dispatch, not a starting guess — clearing it (`n.generators["p_set"] = nan`) before
  `n.optimize()` fixes every one of the 5 OPF fixtures. Re-ran the committed test fresh:
  `uv run --no-sync python -m pytest tests/parity/test_opf_vs_pypsa.py -v` → **20 passed in
  53.03s**, all 5 fixtures at `status="ok"`, `cond="optimal"`. Both `m4-research.md` §3.2 and
  `continuation-m4.md`'s carry-over #2 ("PyPSA infeasibility… still open") are **stale** — a real
  documentation-drift finding this research surfaces and corrects, not a new bug (§1.1).
- **PyPSA genuinely supports multi-period LP with ramp and storage SoC dynamics**, confirmed by
  building and solving a small end-to-end case, not just inspecting the API: `Generator.
  ramp_limit_up`/`ramp_limit_down` (pu of `p_nom` per snapshot step), `StorageUnit.
  efficiency_store`/`efficiency_dispatch`/`state_of_charge_initial`/`cyclic_state_of_charge`, and
  `n.set_snapshots(...)` + `n.optimize(solver_name="highs")` as the one multi-period entry point
  (no separate "multi-period mode" API — snapshots are just a longer index). A 1-bus/3-snapshot
  probe with one ramp-limited generator and one round-trip-lossy `StorageUnit` solved to
  `status="ok"`/`cond="optimal"`, the ramp step bound exactly (`-12.0 MW` step against a declared
  `12.0 MW` limit), and the SoC trajectory exactly consistent with `charge × efficiency_store`
  (§1.2, §1.3).
- **The storage LP-relaxation hazard (simultaneous charge+discharge) is real, not hypothetical,
  and this research reproduces both a case where it never appears and a case where it is
  *required for feasibility*.** The dominance argument (proved algebraically and confirmed on an
  independent `scipy.optimize.linprog` LP) shows overlap strictly *lowers* the resulting SoC
  relative to the equivalent no-overlap dispatch whenever round-trip efficiency `< 1` — so it is
  never chosen when the SoC upper bound has slack. But a second, adversarial probe (a must-run
  generator forcing a fixed net-charge surplus larger than the SoC cap could canonically absorb)
  makes the **no-overlap-allowed** LP genuinely **infeasible**, while allowing overlap makes it
  feasible again — proving overlap is not just an optimality curiosity but can be load-bearing
  for feasibility under a tight SoC cap plus inflexible generation (§3).
- **`Generator` has zero ramp fields today (confirmed by reading `model/entities.py` in full),
  and no MATPOWER fixture in this repo populates MATPOWER's own ramp columns anyway** — `mpc.gen`
  columns 17-20 (`ramp_agc`, `ramp_10`, `ramp_30`, `ramp_q`) are present in the format and are
  **all zero** on every generator of all 5 OPF fixtures (checked directly), and
  `io.matpower.py` reads none of them (grep: zero hits for "ramp"/"RAMP"). pandapower's own
  `net.gen` table carries **no ramp columns at all** on its core static table (checked directly),
  reinforcing the brief's own premise that pandapower's route does not extend to M5. A new,
  optional, MW-unit, `None`-defaulting field (mirroring `Branch.rating_mva`'s "`None` = no
  limit" convention) is the natural backward-compatible shape; not resolved here (§4).
- **`opf.dc_opf`'s row/column families extend cleanly to T periods**, and this research sizes
  and *times* the resulting LP directly (not just estimates it): a standalone highspy probe built
  to the exact structure below solved case14×T=24×1-storage (192 cols, 643 rows) in **8.8 ms**
  and case118×T=24×2-storage (1440 cols, 5778 rows) in **169 ms**, both `Optimal` — HiGHS handles
  this comfortably, with no scaling concern at this size (§2). One genuine open sub-question
  surfaces that ADR-007's text does not fully settle: does `dc_opf()` **itself** grow a period
  axis on every array (a much larger signature change than M4's additive optional params), or
  does a new function reuse its per-period row-family *idioms* (balance row, PTDF flow rows,
  epigraph/hypograph) while owning the T-loop and the two new coupling row families itself? Both
  read as "the one array-level LP builder" under ADR-007's own wording; this is named, not
  resolved (§2.4).
- **The T=1 degenerate-to-nodal reduction is exact, not approximate — proved algebraically and
  confirmed on an independent LP** — mirroring ADR-007's own language for M4's price-taker
  reduction. At T=1 the ramp row family is *structurally absent* (no t-1 to couple to), and an
  idle storage unit (charge=discharge=0) is provably weakly dominant whenever no terminal/cyclic
  SoC target is imposed — confirmed on a probe LP where a present-but-unconstrained storage unit
  is left exactly idle by the optimizer, reproducing the plain fixed-load cost exactly (§6).
- **A hand-derived, closed-form 2-bus/2-period arbitrage optimum is derived and independently
  verified**: `charge* = min(P_max, E_max/η_charge)`, `discharge* = η_charge·η_discharge·charge*`,
  active iff `price_peak·η_charge·η_discharge > price_offpeak`. A concrete numeric instance
  (`c_L=10, c_H=50, η_c=η_d=0.9, P_max=20, E_max=15`) matches an independent
  `scipy.optimize.linprog` solve of the full LP (generators + storage + balance rows) to 6
  decimal places, cost reduction exactly equal to the closed-form profit (§7).
- **No fixture in this repo carries any storage data at all** (`n_storage=0` on all 5 OPF
  fixtures, confirmed by direct read) **and no test-time-derivation helper for storage or a
  multi-period load profile exists yet** (`tests/_bids.py`/`tests/_rated.py` exist; no
  `tests/_storage.py` or period/ramp equivalent) — M5 needs both, following the same
  test-time-derived-from-committed-fixture-data discipline, not new committed fixture files (§8).

---

## 1. The oracle question (AC-6)

### 1.1 Reproducing A4 — it is neither a PyPSA bug nor a modelling mismatch; it is already fixed

`m3-research.md` §3.1 (frozen at M3's Step-1/2 research stage) reports `n.optimize
(solver_name="highs")` returning `Infeasible` on all 5 OPF fixtures after a manual `gencost`
bridge, root cause undiagnosed. `m4-research.md` §3.2 read that frozen doc and concluded the
question was "still unresolved… confirmed still unresolved by reading `m3-research.md` directly,
not re-probed". `continuation-m4.md`'s carry-over #2 repeats the same conclusion. **Both are
wrong about the current repo state.**

`git log --oneline --all -- tests/parity/test_opf_vs_pypsa.py`:

```
4bd67d9 chore(m3/R3): fold review + critic — case300 root-cause correction, PWL point bound, PTDF caching, docstring/field cleanup
8fc8581 chore(m3/R1): fold audit finding — PyPSA parity, citation nit, home page + MathJax + docstring cleanup
```

The file exists, was added in M3's own **R1 fold** (commit `8fc8581`, i.e. *before* `5fa3285`
merged M3 into `epic/01-foundation`, and therefore before `m4-research.md` was written against
`5fa3285`). Its own module docstring names the root cause directly:

> `pypsa.Network.import_from_pypower_ppc` populates `n.generators.p_set` from MATPOWER's raw
> base-case `gen[:, PG]` column, and PyPSA's optimizer treats a non-null `p_set` as a
> **fixed-dispatch** constraint (pins the decision variable exactly to that value) — not an
> initial guess. Since MATPOWER's raw base-case dispatch does not itself balance (e.g. case14:
> `sum(PG) = 272.4` MW vs `sum(load) = 259.0` MW), every generator's degrees of freedom vanish
> and the nodal balance becomes infeasible. The fix… clear the pin (`n.generators["p_set"] =
> float("nan")`) before calling `n.optimize()`.

So: **not a PyPSA bug** (its documented semantics for `p_set` are consistent, just easy to trip
over via the pypower-import path specifically), **not a network-construction error on our side**
in the sense of a wrong topology/parameter, and **not a fundamental modelling mismatch** — a
one-line import-path gotcha with a one-line fix, already found and fixed by M3's own audit fold.

Re-ran the committed test fresh (not trusting the docstring's own claim):

```
uv run --no-sync python -m pytest tests/parity/test_opf_vs_pypsa.py -v
...
tests/parity/test_opf_vs_pypsa.py::test_pypsa_itself_converges_optimal[case14] PASSED
tests/parity/test_opf_vs_pypsa.py::test_pypsa_itself_converges_optimal[case_ieee30] PASSED
tests/parity/test_opf_vs_pypsa.py::test_pypsa_itself_converges_optimal[case57] PASSED
tests/parity/test_opf_vs_pypsa.py::test_pypsa_itself_converges_optimal[case118] PASSED
tests/parity/test_opf_vs_pypsa.py::test_pypsa_itself_converges_optimal[case300] PASSED
... (20 items total: converges/converges-pypsa/cost-matches/dispatch-matches × 5 cases)
============================= 20 passed in 53.03s =============================
```

All 5 fixtures solve to `status="ok"`, `cond="optimal"`, with dispatch/cost matching
`opf.solve_dc_opf` within named tolerances (tight band 1e-9 relative cost / 0.01 MW dispatch on
4 fixtures; a separately-disclosed, root-caused wide band on case300 for an unrelated reason —
PyPSA's DC-LOPF silently drops bus shunt conductance from its own balance, `test_opf_vs_pypsa.py`
docstring, "case300's root cause, closed").

**This is a documentation-drift finding, worth flagging to the orchestrator/user directly**: two
prior research/continuation documents both state PyPSA is not an OPF oracle, and both are
factually wrong about the code as it stands today. The fix landed in M3's own audit fold, whose
commit message literally says "PyPSA parity" — the carry-forward notes in both later documents
were written by reading a stale intermediate artifact (`m3-research.md`, frozen at Step 1/2)
instead of checking whether the wave's own later steps (audit, R1 fold) had since resolved it.

### 1.2 Multi-period LP with storage SoC dynamics, efficiency, and ramp — the exact API

Confirmed by direct inspection (`Network().components[<name>].defaults`) plus an end-to-end
solve, not assumed from documentation:

- **Snapshots, not a separate "multi-period mode".** `n.set_snapshots([...])` sets a longer
  index; every time-varying attribute (`Load.p_set`, etc.) becomes a `pandas.Series`/`DataFrame`
  indexed by snapshot. There is exactly one solve entry point for both single- and multi-period
  problems: `n.optimize(solver_name="highs")` (the modern API; `n.lopf(...)` is the older,
  now-secondary name for the same underlying call in this installed version — `n.optimize` is
  what the already-committed `test_opf_vs_pypsa.py` uses and what this research used throughout).
- **Generator ramp**: `ramp_limit_up`/`ramp_limit_down` — "Maximum active power increase/decrease
  from one snapshot to the next, **per unit of the nominal power**. Ignored if NaN. Does not
  consider snapshot weightings." (field descriptions, read directly). Per-unit of `p_nom`, not an
  absolute MW field — the PyPSA convention differs from this repo's own MW-unit convention
  (`Branch.rating_mva`, `Generator.p_max_mw`, …), a real naming/unit difference worth naming for
  §4, not just for the oracle.
- **Storage SoC dynamics with efficiency**: `StorageUnit` (not `Store`) is the direct match —
  `p_nom` (power rating), `max_hours` (energy = `p_nom × max_hours`, PyPSA's own energy-capacity
  convention, different from this repo's own direct `energy_mwh` field),
  `efficiency_store`/`efficiency_dispatch` (charge/discharge efficiency, matching this repo's
  `Storage.efficiency_charge`/`efficiency_discharge` field-for-field in meaning),
  `state_of_charge_initial`, `cyclic_state_of_charge` (whether the horizon must end where it
  started — a toggle this repo's `Storage` schema has no equivalent field for yet, §3/§5),
  `standing_loss`. `Store` is the alternative (energy-only, needs a paired `Link` for
  charge/discharge efficiency asymmetry) — `StorageUnit` is the closer structural match to this
  repo's existing `Storage` entity and was what this research used.
- **End-to-end proof, not just API inspection** (`probe_pypsa_multiperiod_e2e.py`): 1 bus, 3
  snapshots, one `Generator` (`p_nom=40`, `ramp_limit_up=ramp_limit_down=0.3` → 12 MW/step) and
  one `StorageUnit` (`p_nom=10`, `max_hours=2` → 20 MWh, `efficiency_store=efficiency_dispatch=
  0.9`), load `[10, 30, 10]`:

  ```
  status: ok cond: optimal
  generator p: [19.876543, 22.0, 10.0]        gen ramp step t1->t2: -12.0 (== -ramp_limit_down*p_nom exactly, binding)
  storage p (+discharge/-charge): [-9.876543, 8.0, 0.0]
  storage state_of_charge: [8.888889, ~0, ~0]  (== 9.876543 * efficiency_store(0.9), consistent)
  objective: 518.77
  ```

  Ramp binds at exactly its declared limit; SoC is exactly consistent with `charge ×
  efficiency_store`. This is a real, sanity-checkable multi-period dispatch with both ramp and
  lossy storage active simultaneously, solved by PyPSA's one multi-period entry point.

### 1.3 Can PyPSA serve as an AC-6 oracle for M5? Yes.

Both halves of AC-6 (the LP mechanics work; the fixture-import path from this repo's own
MATPOWER-based network to PyPSA already exists and is proven) are demonstrated with reproducible
evidence, not assumed. The remaining engineering work for an M5 parity test is exactly the same
shape as M4's own oracle-construction discipline: build a PyPSA network from the same
`mambo_power.model.Network` M5's own multiperiod solver consumes (reusing the already-committed
`tests/parity/_mpc_reader.py` / `test_opf_vs_pypsa.py` bridge pattern for cost/branch data),
extend it to `T` snapshots with a synthetic load profile (§8), add `ramp_limit_up`/
`ramp_limit_down` from whatever field M5's design interview picks (§4, converted from MW to
PyPSA's per-unit-of-`p_nom` convention), and add a `StorageUnit` per `Storage` entity (also
needing a synthetic fixture, §8, since none exist today).

### 1.4 A hand-derived analytic optimum is still valuable regardless — not a fallback, a
complement

Per the brief's own framing, the analytic case (§7) was worth deriving independent of §1's
outcome — and having derived it, it is a strictly *stronger* primary correctness check than
PyPSA parity for the specific ramp/SoC-dynamics *mechanics* (PyPSA parity proves "our dispatch
matches a second, independent LP formulation's dispatch"; the closed-form proves "our dispatch
matches the provably-optimal answer", the same relationship M3's hand-KKT case and M4's
settlement-identity derivation already have to their respective oracle parity tests). Since §1's
verdict is yes, this is **not** a tier-downgrade situation — AC-6 can stay a T2/oracle-tier row,
with the closed-form arbitrage case serving the same "AC-1, proven independent of the oracle"
role M3's hand-KKT case and M4's price-taker reduction already played for their waves.

---

## 2. LP formulation — T periods, ramp coupling, storage SoC dynamics on the existing builder

### 2.1 Current single-period shape (recap, exact line references)

`dc_opf(arr, cost_coeffs, options, pwl_costs=None, demand_bid_coeffs=None, demand_pwl_bids=None)`
(`dc_opf.py:230-386` header, body to `:640`) today builds, for one period: `n_gen` generator
columns + `n_demand` elastic-load columns (bounded, no PWL), plus PWL free-var columns; **1**
system-wide balance row + `n_branch` PTDF flow-limit rows, plus PWL epigraph/hypograph rows.

### 2.2 What a T-period extension adds — concrete column/row structure

**Variable vector.** Per period `t ∈ {0, …, T-1}`, the same per-period block `dc_opf` already
builds today: `[gen_1..gen_{n_gen}, demand_1..demand_{n_demand}, storage_charge_1..
storage_charge_{n_storage}, storage_discharge_1..storage_discharge_{n_storage},
storage_soc_1..storage_soc_{n_storage}]` (storage as two nonnegative columns plus an explicit SoC
column — §3 for why not a single signed column), plus any PWL free-var columns for that period's
own PWL generators/bids. The full vector is these `T` blocks concatenated: `x = [x_0, x_1, …,
x_{T-1}]`. Verified directly by building exactly this layout on `highspy` (§2.3).

**Row families** (five; the first two are `dc_opf`'s existing families replicated per period, the
last three are new):

1. **Balance row, per period** (`T` rows total): `Σ gen[t] − Σ demand[t] − Σ charge[t] + Σ
   discharge[t] == fixed_load[t] + shunt[t]` — structurally identical to today's single row,
   referencing only period `t`'s own columns. If `Scenario.periods` gives each period its own
   load figure (§5), only the RHS varies by period; the row's *shape* does not.
2. **Flow-limit rows, per branch per period** (`n_branch × T` rows): the same PTDF-based row as
   today, referencing only period `t`'s own dispatch columns. **The PTDF matrix itself is
   computed once** (`compute_ptdf(arr)`, unchanged) **and reused across all `T` periods** — this
   assumes a static network topology across the horizon (no time-varying outages/switching within
   one multiperiod solve), consistent with R7's own framing and this epic's Not-Doing list (no
   mention of intra-horizon topology change). Worth stating explicitly since it is an assumption,
   not a proven-necessary constraint.
3. **Ramp-coupling rows, per generator per adjacent period pair** (`n_gen × (T−1)` rows, one
   two-sided row per generator per `t = 1..T-1`): `−ramp_down_mw[g] ≤ p_g[t] − p_g[t-1] ≤
   ramp_up_mw[g]`. The **only** row family that references two periods' columns at once (columns
   from block `t` and block `t-1` in the same row) — everything else in families 1-2 is
   block-diagonal per period.
4. **Storage SoC-balance rows, per storage unit per period** (`n_storage × T` rows): a boundary
   row at `t=0` anchoring to `Storage.soc_initial × Storage.energy_mwh` (`soc[0] − η_charge ×
   charge[0] + discharge[0] / η_discharge == soc_initial_mwh`), then `n_storage × (T-1)` coupling
   rows for `t = 1..T-1` (`soc[t] − soc[t-1] − η_charge × charge[t] + discharge[t] / η_discharge
   == 0`) — the storage-side mirror of the ramp row: also couples exactly two adjacent periods'
   columns (or one period plus a constant, at `t=0`).
5. **PWL epigraph/hypograph rows, per period** (unchanged shape from today, replicated for
   whichever periods have a PWL generator/bid active).

This is exactly the concrete answer the brief asked for: ramp rows go **between** adjacent
periods' generator columns; SoC rows go **between** adjacent periods' storage columns (plus one
boundary row); the balance and flow rows are **not** modified in shape, only replicated once per
period with period-specific RHS.

### 2.3 Problem-size estimate and measured HiGHS performance — not estimated, timed directly

A standalone probe (`probe_multiperiod_lp_size.py`) built exactly the five-row-family structure
above directly on `highspy.Highs` (same CSR-row-construction idiom `dc_opf.py` already uses —
`h.addVars`/`h.addRows` with explicit `row_starts`/`col_indices`/`values`, **not** a dense
`T·n_dispatch`-wide matrix — see §2.4's note on why that distinction matters), using this repo's
own `NetworkArrays`/PTDF for case14 and case118, T=24, with synthetic storage units:

```
{'n_gen': 5,  'n_branch': 20,  'T': 24, 'n_storage': 1, 'n_cols': 192,  'n_rows': 643,  'status': 'Optimal', 'elapsed_s': 0.0088}
{'n_gen': 54, 'n_branch': 186, 'T': 24, 'n_storage': 2, 'n_cols': 1440, 'n_rows': 5778, 'status': 'Optimal', 'elapsed_s': 0.1693}
```

Both solve to `Optimal`. **HiGHS handles this comfortably** — case118×T=24 (1440 columns, 5778
rows) solves in 169 ms, the same order of magnitude as a single case300 static OPF solve already
exercised routinely in this repo's own parity suite (case300 alone is 411 branches; this
multi-period case118 problem has roughly 14× as many rows but still solves in well under a
quarter second). No scaling concern surfaces at the wave's own target size (24 periods,
case14/case118-scale networks); HiGHS's general LP capacity (routinely millions of rows in
published benchmarks) is not being stressed here at all — this problem is 2-3 orders of magnitude
smaller than what would start to matter.

### 2.4 A genuine open sub-question for the design interview: does `dc_opf()` itself grow, or
does a new function reuse its row-family idioms?

ADR-007 states plainly that "M5, M6 and M7 extend this same builder rather than composing new
ones — ramp/SoC coupling, zonal aggregation and redispatch are further column/row families on
`dc_opf`, not separate solvers" — and separately, that M4's own extension pattern was: `dc_opf()`
itself gained new **optional, additive** parameters (`demand_bid_coeffs`/`demand_pwl_bids`,
defaulting to `None`, zero-length arrays when absent — every M2/M3 caller unaffected). Read
literally, M5 would do the same: `dc_opf()` gains a `periods: int = 1` parameter (or similar) and
every array (`cost_coeffs`, `arr.gen_p_min_pu`, …) grows a leading/trailing period axis when
`periods > 1`.

That is a **materially larger** signature and array-shape change than M4's — M4 added two new
*optional* parameters with independent, appendable column blocks; a true T-period `dc_opf()`
would need every existing parameter (`cost_coeffs`, `pwl_costs`, `demand_bid_coeffs`, bounds
sourced from `arr`) to become period-indexed, touching the function's entire body, not just
appending new blocks after the old ones. The **practical alternative** — a new function (in
`opf/dc_opf.py` itself, or a new `market/multiperiod.py` module) that owns the `T`-loop and the
two new coupling row families, but calls the *same* `compute_ptdf`/`pf_shift` helpers and
reproduces the *same* balance-row/PTDF-flow-row/epigraph-hypograph construction idioms `dc_opf()`
already uses per period — is arguably still "the one array-level LP builder" at the level ADR-007
actually argues for (one **formulation**, one **place** balance/flow rows are assembled, one
**dual-extraction convention**), without being the literal same 640-line function threaded with a
period dimension on every array.

**Not resolved here** — this is a real fork in how literally to read ADR-007's "single builder"
language, and the design interview should decide it explicitly rather than have an implementor
guess. Whichever is chosen, §2.2's row/column structure is the same either way.

---

## 3. Storage modelling

### 3.1 Two nonnegative columns (charge, discharge), not one signed column

`dc_opf`'s existing elastic-demand precedent (M4, ADR-007) chose **no sign flip** — a bid-load's
dispatch is a nonnegative quantity in its own right, specifically to avoid the "semantic overload"
cost the rejected pseudo-generator alternative would have carried (`m4-research.md` §2.2 item 2).
The same argument applies to storage: charge and discharge have **different efficiency factors**
(`efficiency_charge` vs `efficiency_discharge`) entering the SoC row with different coefficients
(`+η_charge` vs `−1/η_discharge`) — a single signed column `p_storage ∈ [−p_max, p_max]` cannot
express this asymmetric mapping in one linear row without a `max(p,0)`/`min(p,0)` split
internally anyway (which is exactly two nonnegative columns under another name). Two columns is
the direct, no-reformulation-needed encoding; this is what §2's probe and §3.2/§3.3's evidence
both use.

### 3.2 When simultaneous charge+discharge is provably non-binding — the dominance argument

**Claim.** For a fixed target net dispatch `n_t = discharge[t] − charge[t]` at period `t`, among
all `(charge[t], discharge[t]) ≥ 0` achieving that same `n_t`, the **canonical** (no-overlap:
`min(charge[t], discharge[t]) = 0`) choice yields the *highest* possible resulting `soc[t]`
whenever round-trip efficiency `η_charge · η_discharge < 1`.

**Proof.** Let `(c_0, d_0)` be canonical (`min(c_0,d_0)=0`) achieving `n_t = d_0 - c_0`. For any
`m > 0`, `(c_0+m, d_0+m)` achieves the same `n_t` (the `+m`/`+m` cancels in the difference). Its
SoC contribution is `η_c(c_0+m) − (d_0+m)/η_d = [η_c c_0 − d_0/η_d] + m(η_c − 1/η_d)`. Since
`η_c ≤ 1 ≤ 1/η_d`, `(η_c − 1/η_d) ≤ 0` strictly whenever `η_c < 1` or `η_d < 1` — so overlap
(`m>0`) **strictly decreases** the resulting SoC relative to canonical. ∎

**Consequence 1 (non-binding case, confirmed empirically).** Whenever the canonical trajectory
for the LP's chosen net-dispatch schedule never needs to be *lower* than canonical to respect the
SoC's upper bound, overlap is never part of an optimal solution — the LP has no reason to reach
for a strictly SoC-lowering, cost-neutral-or-worse alternative. Confirmed on an independent
`scipy.optimize.linprog` LP (`probe_storage_overlap.py`, Scenario A: 4 periods, alternating cheap/
expensive prices, ample SoC cap): `min(charge, discharge)` is exactly `[0, 0, 0, 0]` at the
optimum. A second, deliberately adversarial attempt with a *tight* SoC cap and steep price swings
(Scenario B, `e_max=3.0` against a much larger natural charge/discharge flow) **still** produced
zero overlap (`min(charge,discharge) ≈ [0,0,0,-0]`, the `-0` being float noise) — the LP simply
chose a smaller canonical charge/discharge that stayed within the cap, since unconstrained
generation capacity gave it that option.

**Consequence 2 (a real case where overlap is not just optimal but *required for feasibility*).**
Scenario B's generation was costly but *uncapped* — the LP always had an escape hatch. Removing
that escape hatch changes the answer entirely: a **must-run generator** (`p_min = p_max`, fixed
output, no dispatch freedom) creates a *fixed* net-charge surplus every period. With a tight SoC
cap (`e_max = 5`, `η_c=η_d=0.8`, forced surplus `15` MW/period), a canonical-only LP
(`discharge` bounded to `[0,0]`) is **provably infeasible**:

```
--- Compare: canonical-only forced (discharge pinned to 0) ---
status: 2  The problem is infeasible. (HiGHS Status 8: model_status is Infeasible)
```

Allowing overlap makes the identical problem feasible — `charge=[41.67, 41.67]`,
`discharge=[26.67, 26.67]` both periods, `soc=[0,0]` throughout (overlap used purely to "spill"
the excess round-trip loss and keep SoC from ever needing headroom it doesn't have):

```
status: 0  Optimal
charge: [41.666667 41.666667]  discharge: [26.666667 26.666667]  soc: [0. 0.]
min(charge,discharge): [26.666667 26.666667]   <- large, deliberate overlap
```

**So the precise answer**: non-binding whenever generation has enough dispatch freedom that the
LP is never forced into a fixed net-dispatch value that a tight SoC cap cannot canonically
absorb; **not** provably non-binding — and in this constructed case, actually *necessary* —
when a storage unit faces both (a) a binding energy-capacity constraint and (b) an inflexible
(must-run/ramp-pinned) net-injection requirement elsewhere in the network that a canonical
charge/discharge split cannot satisfy without breaching the SoC bound.

### 3.3 What the formulation should do about it

Two independent, complementary options (a recommendation, not a resolution — the design
interview's call):

1. **A shared power-limit row**, `charge[t] + discharge[t] ≤ p_max_mw` per storage unit per
   period — bounds the *physical* interface to its own rated throughput (a real device cannot
   simultaneously charge and discharge more than its own converter rating combined), cheap (one
   more row per storage per period), and directly caps how much "spill" §3.2's edge case can ever
   exploit, without eliminating the case where it is genuinely needed for feasibility.
2. **A committed invariant test** on M5's own fixtures (mirroring how this codebase already
   proves things rather than assumes them) asserting `min(charge, discharge) ≈ 0` on whatever
   concrete networks M5 actually ships — cheap, and turns "is this a problem for us in practice"
   from a theoretical question into a checked fact for the wave's own data, the same "prove it
   happens/doesn't happen with evidence" pattern this research applied above.

A hard MILP-style complementarity constraint (binary charge/discharge indicator) was considered
and is **not** recommended: it changes the solver class from LP/QP to MIP, which the wave spec's
own framing ("24-period LP") and ADR-007's LP-builder framing both argue against, for a hazard
that (§3.2) is provably absent under the conditions M5's own realistic fixtures are likely to
satisfy (ample generation flexibility relative to storage's own energy cap).

---

## 4. Generator ramp limits

### 4.1 Confirmed: `Generator` has no ramp field today

`model/entities.py` read in full (§ above, source excerpt already captured in this session):
`Generator` has `id, bus, p_mw, q_mvar, p_min_mw, p_max_mw, q_min_mvar, q_max_mvar, v_set_pu,
in_service, cost` — no ramp field of any kind.

### 4.2 MATPOWER's ramp columns exist in the format but are unpopulated in every fixture here

MATPOWER's `mpc.gen` table header (from `case14.m`'s own comment, verified identical shape
across all 5 fixtures): `bus Pg Qg Qmax Qmin Vg mBase status Pmax Pmin Pc1 Pc2 Qc1min Qc1max
Qc2min Qc2max ramp_agc ramp_10 ramp_30 ramp_q apf` — columns 17-20 are exactly `ramp_agc`,
`ramp_10`, `ramp_30`, `ramp_q` (MATPOWER's AGC/10-minute/30-minute/reactive ramp rates). Checked
directly on all 5 fixtures (`awk` over the raw `.m` gen block): **every value in these four
columns, for every generator, on every fixture, is `0`** — MATPOWER's own "unlimited" convention
for these fields (mirroring `RATE_A=0` meaning unrated, `m3-research.md` §6, the precedent this
finding directly parallels). `io/matpower.py` reads none of them (grep for "ramp"/"RAMP": zero
hits). **This is a different, more severe gap than M3's ratings problem**: a rating of `0` is a
single derivable number from the network's own base-case flow (`tests/_rated.py`); a ramp rate of
`0` copied verbatim would mean "this generator cannot move its output at all between periods" —
plainly wrong for what these fixtures represent, so **no fixture value can be used even as a
literal default**; any M5 ramp value must be synthetic/derived, never read off `mpc.gen` as-is.

### 4.3 pandapower has no ramp support on its own static gen table either

Direct probe (`pp.create_gen(...)`; `[c for c in net.gen.columns if "ramp" in c.lower()]` →
`[]`): pandapower's core `net.gen` table carries no ramp columns at all (ramp is handled, if at
all, through pandapower's separate time-series/controller machinery, not the static OPF table
`rundcopp` reads). This directly confirms the brief's own premise — pandapower's route does not
extend to M5 for ramp any more than it does for multi-period horizons generally.

### 4.4 Field naming and default — a recommendation, not a resolution

Following this codebase's own established convention exactly (`Branch.rating_mva: float | None`,
"`None` = none"; `Branch.tap_ratio`/`shift_deg` likewise): two new optional MW-unit fields on
`Generator`, e.g. `ramp_up_mw: float | None` / `ramp_down_mw: float | None`, defaulting to `None`
meaning "unconstrained between periods" (not `0`, which would mean "cannot move at all" — the
literal opposite of the MATPOWER `0`-value trap named in §4.2). This keeps every existing fixture
and single-period test byte-for-byte valid: `None` on every generator (the honest reading of
every current fixture's unpopulated ramp columns) means the new ramp-coupling row family
(§2.2 item 3) is either omitted entirely or built with `[-inf, inf]` bounds — a no-op either way,
mirroring exactly how an unrated branch's flow row already never binds (`dc_opf.py`'s own
"Unrated branches… get an unconstrained row" convention). MW units (not PyPSA's per-unit-of-
`p_nom` convention, §1.2) keep this consistent with every other physical field on `Generator`.
This is a recommendation reusing an established pattern, not a new decision — presented for the
design interview to confirm or adjust.

---

## 5. `Scenario.periods` shape — options, not a resolution

### 5.1 What a period needs to carry, at minimum, for M5 itself

Per §2's LP structure, the *floor* requirement is: enough information to build a period-specific
balance-row RHS (a load figure per bus per period) — everything else (ramp limits, storage
efficiency/capacity) lives on the static `Generator`/`Storage` entities, not per-period, since
those are physical device properties that do not change hour to hour within one scenario.

### 5.2 What later waves are likely to need — survey, not a commitment

- **M6 (zonal-redispatch)**: per the spec's module table, a zonal clearing LP plus a min-cost
  redispatch LP; "zonal aggregation… further column/row families" per ADR-007. If M6 ever
  composes with M5 (a 24-period zonal clearing), it would need per-period, per-zone data — but M6
  is `[par]` with M5, not dependent on it (epic plan Waves table), so this is speculative, not a
  confirmed need M5 must satisfy now.
- **M7 (agents)**: `Strategy.bid(obs) → offers`, a bid→clear→settle→learn loop, run per spec
  "last market wave", **depends on M5** (epic plan Waves table: `M7 | agents | … | M5`). This is
  the one later wave with a *confirmed* dependency on M5's shape: an agent submitting different
  bids each period needs `Period` to carry **per-period bid/offer data**, not just a load figure
  — `Load.bid`/`Generator.cost` are static per M1/M4's own design (they live on `Network`, one
  value for the whole scenario); M7 will need either a `Period`-level override of those, or a
  different mechanism entirely (a `Strategy` producing a fresh `Network`/bids each period,
  bypassing `Scenario.periods` altogether). Genuinely undesigned at this point — the epic's own
  module table gives `market.agents` a one-line gloss, same as it does periods themselves.
- **jobs registry consequence, already flagged in the shipped code**: `jobs/registry.py`'s own
  docstring for `market.nodal` says `SolveRequest` stays `network`-shaped rather than growing a
  parallel `scenario` field, explicitly "Revisit only if a future wave gives `Scenario` fields a
  bare `Network` cannot supply." **M5's `periods` field is exactly that case** — a bare `Network`
  cannot supply a 24-period load profile. `SolveRequest`/the `market.multiperiod` runner will need
  to either accept a `Scenario` directly (widening the `Runner` signature beyond today's
  `(Network, options) -> result`) or grow a new request shape — a concrete, code-level consequence
  of whichever `periods` shape is picked, not just a model-layer question.

### 5.3 Three concrete options (not chosen here, per the brief's own instruction)

**Option A — minimal, scalar load scaling.** `Period.load_scale: float` (a single system-wide
multiplier applied to every `Load.p_mw` for that period), `Scenario.periods: list[Period]`.
Cheapest, matches R7's literal text ("24-period horizon with ramp limits and storage state of
charge" — no mention of per-period bids), keeps every physical parameter on the static entities.
Cost: every load moves in lockstep (no shape diversity between a commercial and a residential
load's own daily curve), and offers M7 nothing to build on without a further extension.

**Option B — per-load, per-period explicit overrides.** `Period.load_p_mw: dict[str, float]`
(explicit id-keyed override, not a scale factor — independent shape per load), plus **optional**
`Period.bids: dict[str, LoadBid] | None` / `Period.offers: dict[str, GeneratorCost] | None` for
M7's eventual need. More general, directly reusable by M7 without a later rewrite (the field
already exists, just unused by M5's own solver until M7 reads it) — but speculative for M5 itself
(building fields M5 doesn't use risks the exact trap `m4-research.md` §6.3 already named for
`Storage`'s own precedent: a stub whose eventual shape is *not yet* fully specced is a real risk,
not a free option, unlike `Storage`'s successful stub which *was* fully specced before it shipped).

**Option C — layered/minimal-now, explicitly named as growable.** Ship Option A's shape now
(`load_scale` or a `load_p_mw` override, M5's own choice, but *not* the bid/offer fields), with a
short, explicit note (ADR or plan carry-over, mirroring how ADR-007 itself named M5/M6/M7's
eventual needs without designing them) that M7 is expected to **widen** `Period` additively
(pydantic's `extra="forbid"` convention makes an additive field change loud and safe, per the
same reasoning `m4-research.md` §6.3 already used for `Storage`). This treats the M7 dependency as
a known, named future extension rather than either ignoring it (Option A alone) or trying to
design it now without a real spec (Option B in full).

No recommendation is made between these — genuinely a design-interview decision, per the brief.

---

## 6. Degenerate-to-nodal (AC-4 candidate)

### 6.1 Conditions, enumerated

A T=1 multiperiod solve reduces **exactly** to `market.nodal`'s answer when:

1. **T=1 structurally**, not just "ramp doesn't bind": the ramp-coupling row family (§2.2 item 3)
   references `t-1`, which does not exist at `T=1` — the row family is **absent**, not merely
   slack. This is a stronger, structural claim than "assume ramp isn't binding".
2. **Storage is either absent, or present but idle at the optimum** (`charge=discharge=0`) —
   which holds automatically, without needing to force it, whenever **no terminal/cyclic SoC
   target is imposed** on that single period. Proof: with a free ending SoC, any `(c,d)` pair is
   weakly dominated by `(0,0)` — reducing both by `min(c,d)` leaves the balance row's net
   contribution unchanged (§3.2's cancellation argument) and, since nothing in the horizon
   consumes the resulting stored energy, any residual round-trip loss from a nonzero `(c,d)` only
   ever removes value, never adds it. Confirmed on an independent LP
   (`probe_t1_reduction.py`): a present-but-unconstrained storage unit is left exactly idle by the
   optimizer (`charge=0.0, discharge=-0.0, soc1=-0.0`), and the resulting cost (`300.0`) exactly
   equals the plain fixed-load cost with no storage at all.
3. **The single period's own load/bid data must equal what `market.nodal` would build from the
   same `Network`** — i.e. whatever `Scenario.periods[0]` supplies (§5) must reduce to the
   `Network`'s own `Load.p_mw`/`Load.bid`, not an independently-scaled figure. This is a
   data-plumbing condition dependent on §5's still-undecided shape, not a modelling condition.

### 6.2 Exact, not near-exact

Given (1)-(3), the resulting LP is **byte-for-byte** the same LP `market.nodal`/`dc_opf` already
build today — the storage columns are present but pinned at their own zero-cost, zero-value
optimum, contributing nothing to the objective, balance row, or any flow row. This directly
mirrors ADR-007's own language for M4's price-taker reduction ("exact rather than approximate…
the welfare LP *is* the fixed-load LP"), and the reasoning is the identical shape: a structurally
absent row family (ramp) plus a provably-dominated-to-zero variable set (storage) rather than an
approximation or a tolerance-based near-match.

---

## 7. Analytic arbitrage optimum (AC-5 candidate)

### 7.1 Setup

2-bus network: bus 1 carries a price-taking generator (linear marginal cost `c_L` off-peak /
`c_H` on-peak — modelled here as two periods each served by an uncapped, linear-cost generator,
so price is exogenously fixed at that period's own marginal cost regardless of storage's
behaviour, the same "price-taker" condition `m4-research.md` §4.2 already made precise for M4);
bus 2 carries the load and the storage unit. The branch between them is unrated (uncongested) —
this derivation isolates *temporal* arbitrage, not spatial LMP spread, so both buses see the same
system price each period. Storage: power limit `P_max`, energy limit `E_max`, `soc_initial = 0`,
charge efficiency `η_c`, discharge efficiency `η_d`, free ending SoC (2-period horizon, no
terminal target).

### 7.2 Derivation

Storage chooses `charge ∈ [0, P_max]` in period 1 and `discharge ∈ [0, P_max]` in period 2,
subject to `η_c · charge ≤ E_max` (SoC cap after charging) and `discharge ≤ η_d · (η_c · charge)`
(cannot discharge more energy than was stored, net of both efficiency losses). Since generation is
uncapped and price-taking, storage's own objective is exactly its arbitrage profit,
`c_H · discharge − c_L · charge`, and using *all* stored energy is always weakly better (more
discharge revenue, same charge cost) — so at the optimum `discharge* = η_c · η_d · charge*`,
reducing to a single free variable `charge* ∈ [0, min(P_max, E_max/η_c)]` with profit
`charge* · (c_H · η_c · η_d − c_L)` — linear in `charge*`, so the optimum is a corner:

```
charge*     = min(P_max, E_max / η_c)                       if c_H · η_c · η_d > c_L
charge*     = 0                                              otherwise
discharge*  = η_c · η_d · charge*
profit*     = charge* · (c_H · η_c · η_d − c_L)
```

The activation condition `c_H · η_c · η_d > c_L` is the standard "round-trip-efficiency-adjusted
price spread must be positive" arbitrage condition — and is exactly the T=1-reduction condition
of §6 in reverse: when it fails, `charge*=discharge*=0` and storage is optimally idle, the same
"SoC-neutral" state §6.1 condition 2 requires.

### 7.3 Numeric instance, independently verified

`c_L=10, c_H=50, η_c=η_d=0.9, P_max=20, E_max=15` (so the energy cap binds, not the power rating:
`E_max/η_c = 16.67 < P_max = 20`). Closed form: `charge* = 16.667`, `discharge* = 0.81 × 16.667 =
13.5`, `profit* = 16.667 × (50×0.81 − 10) = 16.667 × 30.5 = 508.33`.

Independent verification (`probe_arbitrage_closed_form.py`, `scipy.optimize.linprog`, full LP —
two generators, storage, balance rows, SoC row, not the reduced single-variable form above):

```
gen1=16.666667 gen2=16.500000 charge=16.666667 discharge=13.500000 soc1=15.000000
total cost: 991.666667
closed form: c1*=16.666667 d2*=13.500000 profit*=508.333333
no-storage total cost=1500.000000  with-storage total cost=991.666667
cost reduction = 508.333333 (should equal profit*)
LP total cost matches with-storage closed form: True
duals (lambda1, lambda2, mu_soc): [10.0, 50.0, -11.111111]
```

Matches to 6 decimal places; the LP's own duals confirm `λ1=c_L=10`, `λ2=c_H=50` (price-taking
generators, as designed), and `μ_soc = -11.11` is the (correctly nonzero) shadow price of the
binding energy cap. This case, or a variant tuned per M5's own fixture choices (§8), is directly
promotable to a committed test the same way M3's hand-KKT case became AC-1 and M4's
price-taker-reduction case became AC-5.

---

## 8. Fixture question

### 8.1 No storage data exists in any fixture — confirmed

`n_storage=0` on every one of the 5 OPF fixtures, confirmed directly (`NetworkArrays.from_network
(net)`; `len(net.storage)` for `case14`/`case_ieee30`/`case57`/`case118`/`case300` all `0`). This
is the same shape of gap M4's `_bids.py` and M3's `_rated.py` both solved: no committed data at
all, not merely an unpopulated column (§4.2's ramp gap is the same shape again). No
`tests/_storage.py` or equivalent exists yet (`find tests -iname "*storage*"` → empty).

### 8.2 Does M5 need a rated branch?

Yes, for the same reason M4's own continuation carried this forward (`continuation-m4.md`
carry-over #1, plan Assumption A7): without a rated branch, no fixture can exercise the
interaction between a *binding flow limit* and ramp/storage coupling **simultaneously** — and
M5's own settlement/dispatch behaviour under simultaneous congestion is exactly the kind of
interaction a single-effect-at-a-time fixture cannot prove. `tests/_rated.py`'s `rated_network()`
helper already exists, is already committed, and needs no changes to be reusable by M5 as-is (it
derives a rating from any network's own base-case DC flow, independent of period count — though
note it derives from a *single* base-case solve, so applying it to a multiperiod network means
picking one representative period's flow, or the peak period's, to derive from; a design detail
for whoever writes the fixture helper, not a blocker).

### 8.3 Does M5 need a 24-period load profile, and where would it come from?

Yes — R7 and the plan both specify a 24-period horizon, and §7's arbitrage case only needs 2
periods; a fuller AC-6/parity fixture needs a realistic multi-hour shape for both PyPSA parity
and the LP-sizing evidence in §2.3 to mean anything beyond a synthetic stress test. No such
profile exists in this repo today (no MATPOWER fixture carries anything beyond a single base-case
`Pd`, and MATPOWER's own `.m` format has no multi-period concept at all — the same "the format
doesn't have the section" conclusion `m4-research.md` §5 already reached for demand bids).
Following the established, twice-precedented discipline (`tests/_rated.py`, `tests/_bids.py`,
both explicitly citing "derive at test time from the fixture's own already-committed data, no new
fixture file committed" as *the* pattern, spec Design item 7): a `tests/_periods.py`-shaped helper
deriving a synthetic 24-hour scaling curve (e.g. a documented diurnal shape — a literature-typical
load curve, or even a simple two-level day/night split matching §7's own 2-period arbitrage
derivation scaled up) anchored on each fixture's own already-committed `Load.p_mw`, is the
cheapest non-speculative option and the one this research recommends by direct analogy to the two
prior waves' identical fixture problem — presented as a recommendation, not a decision, since the
exact curve shape is a genuine design choice the same way M4's VOLL figure was.

### 8.4 Storage fixture, similarly

A `tests/_storage.py` helper following the identical pattern — deriving a synthetic
`Storage` entity (bus, power/energy rating, efficiency) anchored on some property of the fixture
network already committed (e.g. sized relative to the network's own peak load or a chosen
generator's capacity, mirroring `_rated.py`'s "derive from the network's own solved state" and
`_bids.py`'s "anchor to the load's own historical figure") — is the same-shape gap as §8.1/8.3 and
should very likely follow the same discipline. Not designed further here — the exact sizing rule
is, again, a genuine design-interview decision (the equivalent of `_bids.py`'s VOLL figure or
`_rated.py`'s `RATING_MARGIN`), not proposed numerically here.

---

## Carry-forward list for the M5 design interview

1. **§1 documentation-drift correction, worth propagating**: `m4-research.md` §3.2 and
   `continuation-m4.md`'s carry-over #2 both state PyPSA is not a working OPF oracle; both are
   stale as of `8fc8581` (M3's own R1 fold). AC-6 can be a T2/oracle-tier row using PyPSA, not a
   T1 hand-derived-only row — no tier downgrade needed.
2. **§2.4, genuinely open**: does `dc_opf()` itself grow a period axis on every existing
   parameter (matching M4's literal "extend the same function" precedent but a much bigger
   signature change), or does a new function own the T-loop while reusing `dc_opf`'s per-period
   row-family construction idioms (arguably still "one builder" under ADR-007's actual reasoning,
   without literally being the same function)? Not resolved here.
3. **§3.3**: add a shared `charge+discharge ≤ p_max_mw` row (cheap, physically meaningful,
   bounds the proven-real overlap edge case) and a committed invariant test on M5's own fixtures
   — recommended together, not required; a hard MILP complementarity constraint is not
   recommended (changes solver class for a provably narrow hazard).
4. **§4.4**: `Generator.ramp_up_mw`/`ramp_down_mw`, optional, MW-unit, defaulting to `None` =
   unconstrained (never `0` — MATPOWER's own unpopulated-column convention would otherwise trap a
   naive default into "cannot ramp at all"). A recommendation reusing `Branch.rating_mva`'s
   existing pattern, not a new decision.
5. **§5.3**: three concrete `Scenario.periods` options (A minimal scalar scaling, B full
   per-load/per-period overrides including bids, C minimal-now-explicitly-growable) — genuinely
   not chosen here per the brief's own instruction. Note the real, already-shipped-code
   consequence: `jobs/registry.py`'s own docstring already names "a future wave gives `Scenario`
   fields a bare `Network` cannot supply" as the trigger for widening `SolveRequest`/`Runner`
   beyond its current `(Network, options)` shape — M5 is that wave.
6. **§6, §7**: both proved with reproducible, independent-LP evidence and are ready to become
   AC-4/AC-5 tests directly, the same way M3's hand-KKT case and M4's price-taker reduction did —
   no further research-stage work needed on either.
7. **§8**: M5 needs both a rated branch (reuse `tests/_rated.py` unchanged) and new
   `tests/_periods.py`/`tests/_storage.py` helpers following the identical "derive at test time,
   commit no new fixture data" discipline `_bids.py`/`_rated.py` already established twice — the
   exact derivation rules (load-curve shape, storage sizing rule) are genuine design-interview
   decisions, not proposed numerically here, the same way M4 left its VOLL figure to that step.
