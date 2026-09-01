# M3 research — opf-n1 groundwork

Wave M3 "opf-n1" of the mambo-power epic, Step 1/2 research. Read-only; written 2026-08-23
against repo `C:\Claude Projects\mambo-power` @ `dcdc1c9` (branch `epic/01-foundation`, M2
merged), highspy 1.15.1, pandapower 3.3.0, PyPSA 1.2.4 from `.venv` (`uv` at
`C:\Users\mambo\AppData\Roaming\Python\Python314\Scripts\uv.exe`). No source files touched;
only reads and `uv run --no-sync python <scratchpad>/probe_*.py`.

Headline (the rest is evidence):

- **Assumption 2 holds outright.** `highspy.Highs().getSolution()` returns `row_dual` for both
  an equality (balance) row and a binding inequality (flow-limit) row, and `col_dual` (reduced
  cost) for a variable pinned at its bound — all from one `.run()` call, no special options. No
  fallback-to-PTDF-reconstruction is needed (§1).
- **No fixture has any piecewise-linear generator cost.** All five OPF-fixtures' `gencost` is
  MODEL 2 (polynomial) with real, non-trivial coefficients (linear term always nonzero) — the
  "is convexity a real constraint on the fixtures" question in the brief is moot for parity
  data; PWL support can only be tested with a hand-built network (§2). `PiecewiseCost` validates
  strictly-increasing `p_mw` only, **not** non-decreasing slope (convexity) — confirmed by
  reading `model/network.py:182-197`; this is a real, open design gap, not a silent assumption
  (§2.2).
- **OPF fixture survey: pandapower `rundcopp` converges on all 5** (case14, case_ieee30,
  case57, case118, case300) once the same `BASE_KV<=0 → 1.0` patch M2's oracle already applies
  is used. **PyPSA is not usable as an automated oracle without more work**: its own
  `import_from_pypower_ppc` explicitly does not import `gencost` (warns and silently zeroes
  every `marginal_cost`); after manually bridging MATPOWER's polynomial coefficients into
  `marginal_cost`/`marginal_cost_quadratic`, `n.optimize(solver_name="highs")` returns
  **Infeasible on all five fixtures**, root cause not diagnosed within this session's budget
  (§3). This is the biggest open question for the design interview.
- **No fixture has a branch rating.** `RATE_A == 0` on every branch of all five `.m` files
  (independently confirmed by `awk` over the raw bytes and by the importer's own
  `rating_mva=None` output) — MATPOWER's convention for "no limit". Both R3's PTDF flow-limit
  LP constraints and R4's N-1 limit-violation check have **nothing to bind against** in the
  current fixture set. This is not `unverified`, it is a real, load-bearing gap the design
  interview must resolve (§6).
- **N-1 brute-force DC re-solve is cheap** — case300's full brute force (322 non-bridge
  outages, single-RHS `pf.dc.solve` per outage) measured **0.968 s** total including a full
  `validate_network` per outage (M1's `_brute_force_lodf.py` pattern); no unit/parity tier
  split is needed by timing alone, *provided* the re-solve stays single-RHS DC (a full PTDF
  matrix rebuild per outage, which is what LODF's own brute force does, is ~7-10x more
  expensive per outage and is what pushed M1's case118 LODF brute force over the 10 s rule)
  (§4).
- AC-feasibility check: `pf.solve_ac(net)` already takes a `Network`; the cheapest construction
  is `net.model_copy(deep=True)` + overwrite each in-service generator's `p_mw` from the OPF
  dispatch (keyed by id), no import round-trip needed. `AcPowerFlowResult` already carries
  `converged`/`message`; **no violation-reporting type exists yet** — `BranchResult.loading_pct`
  gives overload directly, but voltage-limit checking needs `Bus.v_min_pu`/`v_max_pu`, which
  live on `model.Network`, not on `results.BusResult` — a violations summary needs both inputs
  (§5).
- `jobs/registry.py` + `jobs/run.py` extension mechanics are exactly as documented: a
  `KindSpec` (options model, result model, runner) + `register()`; the closed `ResultModel`
  union and `FailureCode` literal both need widening by hand at the call site (no plugin
  mechanism). HiGHS distinguishes `Infeasible` and `Unbounded` as separate model statuses
  (confirmed), which maps cleanly onto MATPOWER-style `UNSOLVABLE_NETWORK` precedent (§7).
- `opf/` and `contingency/` packages do not exist yet; `numerics.ptdf`/`numerics.lodf` live at
  `src/mambo_power/numerics/ptdf.py` / `lodf.py` exactly as epic.spec.md's module table says
  (§8).

---

## 1. Assumption 2 — highspy row/column duals

probe: `<scratchpad>/probe_highs_duals.py`, `probe_highs_duals2.py`.

Built a minimal DC-OPF-shaped LP directly on `highspy.Highs()` (no wrapper): two generator
columns with cost and bounds via `addVars`/`changeColsCost`; one **equality** row (nodal
balance, `pg1+pg2 == 50`) and one **inequality** row (a PTDF-style flow-limit,
`0.6·pg1 − 0.4·pg2 ≤ 20`) via `addRows` in CSR form (`h.addRows(nrows, lower, upper, nnz,
starts, indices, values)`).

```
col value: [40.0, 10.0]
col dual:  [0.0, 0.0]
row value: [50.0, 20.0]
row dual:  [16.0, -10.0]        # balance dual = 16 (a per-unit LMP-like price); flow-limit
                                 # dual = -10, and row_value == 20 == the upper bound: binding
```

A second probe forced generator 1 to its upper bound (cap 5 < optimal 40):

```
col value: [5.0, 45.0]
col dual (reduced cost): [-10.0, 0.0]   # generator 1's bound has a nonzero shadow price
row dual: [20.0]
```

**API**: after `Highs.run()`, `Highs.getSolution()` returns `.row_dual` (one per constraint
row, nonzero exactly on binding rows/equalities) and `.col_dual` (reduced cost, nonzero exactly
on variables at a bound) — both read straight off the LP relaxation, no extra option needed.
This is exactly what LMP decomposition (energy = balance-row dual, congestion = Σ flow-row
duals × PTDF) needs. **Assumption 2's fallback (reconstruct via PTDF from binding-set) is not
needed** — the direct dual read is proven to work for every constraint type opf.dc_opf uses:
equality balance, inequality flow limit, and variable (generation) bounds.

## 2. PWL cost as an LP

### 2.1 Standard formulation (not run — a documented fact, cross-checked against source only for
what's checkable; the general epigraph/segment construction is textbook and not itself probed
here — `unverified` in the sense of "not executed against MATPOWER/PyPSA source this session",
but standard enough that citing it is safe)

The standard LP encoding of a convex PWL cost `cost(p)` with breakpoints `(p_0,c_0)...(p_n,c_n)`
is either (a) segment variables `p = p_0 + Σδ_i`, `0 ≤ δ_i ≤ p_i−p_{i-1}`, `cost = c_0 +
Σ(slope_i · δ_i)` (works only if slopes are non-decreasing — a non-convex PWL cost makes the LP
choose the *cheapest* segment first regardless of `p`'s true position, corrupting the answer),
or (b) an epigraph set of linear inequalities `cost ≥ slope_i·(p − p_i) + c_i` for every segment
(also requires convexity: a concave segment's inequality is not tight where it should be and
the LP will never bind it, again giving a silently wrong answer for a non-convex curve). Both
require the PWL cost to be convex; there is no LP encoding of a non-convex PWL cost.

### 2.2 What the fixtures actually contain

probe: `awk` over `mpc.gencost` block, `col 1` (MODEL), across all 5 fixtures (`case14`,
`case_ieee30`, `case57`, `case118`, `case300`):

```
case14: MODEL values present = {2}     (5 rows)
case_ieee30: MODEL values present = {2}   (6 rows)
case57: MODEL values present = {2}     (7 rows)
case118: MODEL values present = {2}    (54 rows)
case300: MODEL values present = {2}    (69 rows)
```

**Every generator in every fixture uses MODEL 2 (polynomial).** There is zero MODEL 1
(piecewise) data anywhere in the fixture set. Each row also has exactly 2 of its 3 polynomial
coefficients nonzero (a real quadratic-or-linear cost, never all-zero/free generation) —
checked with the same awk pass. **Consequence**: M3's PWL-cost LP path (and the
MATPOWER-`rundcopf`-vs-PyPSA-`optimize` PWL parity the brief asked about) cannot be exercised
against any of the 5 OPF-parity fixtures — it needs a hand-built or externally-sourced test
network. This is a real gap for the design interview to name (does M3 add a small synthetic
PWL fixture, e.g. under `fixtures/matpower/derived/`, the way M1 added `case14_island.m` etc.?).

### 2.3 `PiecewiseCost` validation — does not check convexity

read: `src/mambo_power/model/entities.py:74-82` (`PiecewiseCost.points`, docstring "at least
two; p_mw must be strictly increasing") and `src/mambo_power/model/network.py:182-197` (the
only validation: `len(p_values) >= 2` and strictly increasing `p_mw`; no check on the
`cost`/`p` slope sequence).

**Confirmed**: `PiecewiseCost` accepts a **non-convex** breakpoint sequence today (e.g.
decreasing marginal cost) — nothing rejects it. Per §2.1, an LP built from such a curve would
silently produce a wrong dispatch (the segment-selection relaxation is only valid for convex
costs) rather than fail loudly. **This is a real design question, not a silent assumption**:
should `validate_network` gain a `BAD_RANGE`-style convexity check on `PiecewiseCost` (would
change M1's already-shipped, already-audited validation surface), or should `opf.dc_opf`
itself detect non-convex PWL input and raise (e.g. a new, kind-specific error distinct from
`UNSOLVABLE_NETWORK`, since this is malformed *cost* data, not malformed network topology)?

## 3. OPF fixture survey (case14, case_ieee30, case57, case118, case300)

probe: `<scratchpad>/probe_opf_parity2.py` — reuses the exact oracle-construction path M2's own
parity tests already use (`tests.parity._mpc_reader.read_mpc_numpy` → `tests.parity.
test_matpower_vs_pandapower.pandapower_from_raw`, with the same `BASE_KV<=0 → 1.0` patch and
`trafo_model="pi"` M2's `tests/parity/test_dc_vs_pandapower.py:75-84` already uses for
`rundcpp`), then `pp.rundcopp(net, trafo_model="pi")`.

```
case14:      rundcopp OK  cost=7642.5918   conv=True
case_ieee30: rundcopp OK  cost=8343.4017   conv=True
case57:      rundcopp OK  cost=41006.7369  conv=True
case118:     rundcopp OK  cost=125947.8814 conv=True
case300:     rundcopp OK  cost=706292.3242 conv=True
```

(Without the `BASE_KV` patch, `case14` and `case57` fail with `FloatingPointError: invalid
value encountered in divide` inside pandapower's own converter, from dividing by a stored
`BASE_KV = 0` — exactly the M2-documented defect, same fix applies.) **All 5 fixtures the wave
names converge cleanly under pandapower's DC-OPF** (`pp.rundcopp`, confirmed genuinely an OPF —
its docstring: "Runs the pandapower Optimal Power Flow… Flexibilities, constraints and cost
parameters are defined in the pandapower element tables", `run.py:473-478`, honoring
`min_p_mw`/`max_p_mw` and `max_loading_percent` — not just a DC power flow with a cost label).
`case30` is correctly excluded per the brief (M1/M2's own "flat, no real solution" verdict,
`m1-w1-extract.md` / `m2-research.md` — not re-litigated here).

### 3.1 PyPSA: import drops cost data; optimize is infeasible after a manual bridge

probe: `<scratchpad>/probe_pypsa_opf2.py`, `probe_pypsa_opf3.py`, `probe_pypsa_diag.py`.

`pypsa.Network.import_from_pypower_ppc` (the natural MATPOWER-shaped import path) **logs and
enforces**: `"Warning: Note that when importing from PYPOWER, some PYPOWER features not
supported: areas, gencosts, component status"` — confirmed by inspecting its source
(`pypsa/network/io.py`, function body read directly) and by probe: every generator's
`marginal_cost` and `marginal_cost_quadratic` is `0.0` after import, for all 5 fixtures.

Manually bridging MATPOWER's polynomial `gencost` (`c2 → marginal_cost_quadratic`, `c1 →
marginal_cost`, mirroring the independent-oracle-construction discipline `tests/parity/
_mpc_reader.py` already establishes) and calling `n.optimize(solver_name="highs")`:

```
case14:      status=warning cond=infeasible
case_ieee30: status=warning cond=infeasible
case57:      status=warning cond=infeasible
case118:     status=warning cond=infeasible
case300:     status=warning cond=infeasible
```

Diagnostic check on `case14` (`probe_pypsa_diag.py`): generator `p_nom`/`p_min_pu`/`p_max_pu`
after import look sane (`p_nom` = each MATPOWER `PMAX`, `p_min_pu=0`, `p_max_pu=1`, total
capacity 772.4 MW against 259 MW of load — plenty of headroom), so the infeasibility is **not**
an obvious generation-capacity mismatch; root cause not isolated within this session's time
budget (candidates not yet checked: branch `s_nom`/reactance mapping, slack-bus/angle-reference
setup, a MATPOWER phase-shifter or zero-impedance branch PyPSA's DC-OPF formulation rejects
differently than pandapower's). **`unverified`**: whether PyPSA is usable as an OPF oracle at
all without deeper investigation into its ppc-import path.

**Open question for the design interview** (genuinely undecided, not silently resolved here):
should M3's automated OPF parity rely on pandapower `rundcopp` alone (which is proven to
converge cleanly on all 5 fixtures) and treat PyPSA as, at most, a manually-verified spot check
on one small case — or is diagnosing/fixing the PyPSA bridge worth the time before M3 starts?
The wave brief named both oracles; only one is currently working.

### 3.2 No MATPOWER-shipped "stored OPF solution" exists

Unlike the power-flow fixtures, whose `bus` `VM`/`VA` columns carry a stored (if imprecise —
`m2-research.md` §1) solved state, the same `.m` files' `gen` `PG`/`QG` columns are the
**base-case dispatch**, not an optimality-verified OPF result — there is no MATPOWER
`rundcopf`-published reference-column set analogous to the stored `VM`/`VA` M2 used for
`test_ac_vs_matpower_stored.py`. Checked by inspecting the case-file column layout directly
(same MATPOWER version-2 format for PF and OPF cases; no separate results section). **The only
available OPF oracle is a live solve** (pandapower confirmed above; PyPSA unresolved) — there
is no static "stored solution" fallback the way M2 had for power flow.

## 4. N-1 brute-force cost (case300)

probe: `<scratchpad>/probe_n1_timing.py`, `probe_n1_timing2.py`.

Two measurements, both reusing `mambo_power.numerics.bridges` to skip branches whose outage
islands the network (matching `tests/_brute_force_lodf.py`'s own skip rule) and both timed with
`time.perf_counter()`:

**(a) Minimal loop** — mutate `net.branches[k].in_service = False`, rebuild `NetworkArrays`, run
`pf.dc.solve`, restore — no `validate_network` call:

```
case14:      n_branch=20  n_bridge=1  per_outage=0.00088 s  est_full=0.02 s
case_ieee30: n_branch=41  n_bridge=3  per_outage=0.00112 s  est_full=0.04 s
case57:      n_branch=80  n_bridge=1  per_outage=0.00113 s  est_full=0.09 s
case118:     n_branch=186 n_bridge=9  per_outage=0.00159 s  est_full=0.28 s
case300:     n_branch=411 n_bridge=89 per_outage=0.00251 s  est_full=0.81 s
```

**(b) M1's exact `_brute_force_lodf.py` pattern** — `net.model_copy(deep=True)` once, then per
outage: flip `in_service`, **`assert validate_network(outaged) == []`** (a full pydantic
re-validation pass), rebuild `NetworkArrays`, solve, restore:

```
case118: n_outages=177 total=0.323 s  per_iter=0.00182 s
case300: n_outages=322 total=0.968 s  per_iter=0.00301 s
```

**Both are well under M1's ~10 s unit/parity tier-crossing threshold** even for case300's full
brute force (411 branches, 322 non-bridge outages), including a full network re-validation per
outage. This is markedly cheaper than M1's own brute-force LODF test, which crossed 10 s
*inside* the unit tier at case118 alone (measured 3.90 s for 186 branches per
`m1-r1-fold-report.md:113`, ~0.021 s/outage) and had to move to the parity tier. The difference
is the **shape of the linear solve**: N-1 needs one DC re-solve per outage (`pf.dc.solve`,
single right-hand-side vector), while LODF's brute force needs a **full PTDF rebuild** per
outage (`numerics.ptdf`, one sparse LU solve against an `n_bus`-column right-hand side, `n_bus`
being far larger than 1) — ~7-10x more linear-algebra work per outage, which is exactly what
the ratio of the two measured `per_outage` figures shows (0.021 s/outage for PTDF-rebuild vs.
0.0016-0.0030 s/outage for a single DC re-solve).

**Recommendation for the design interview** (not a silent choice — flagging the dependency):
*if* M3's N-1 brute-force agreement test is written against `pf.dc.solve` per outage (as R4
naturally wants — a re-solve, not a PTDF rebuild), it can very likely stay in the **unit tier**
even on `case300`, unlike M1's LODF brute force. This should be confirmed with the actual test
harness (pytest overhead, fixture setup) once written, not assumed from a bare script.

## 5. AC-feasibility check shape

read: `src/mambo_power/pf/__init__.py:72-124` (`solve_ac`), `src/mambo_power/results/
power_flow.py:90-100` (`AcPowerFlowResult`), `src/mambo_power/results/tables.py` (`BranchResult`,
`BusResult`).

`solve_ac(net: Network, *, options: AcOptions | None = None) -> AcPowerFlowResult` takes a
`Network` directly — no separate "from arrays" entry point exists at the public API level, so
the cheapest construction from an `opf.dc_opf` dispatch is: `net.model_copy(deep=True)`, then
for each in-service generator set `.p_mw` to the OPF result's dispatch (matched by generator
`id` — `AcPowerFlowResult`/`DcPowerFlowResult`'s `GenResult` rows are already id-keyed), then
`solve_ac(dispatched_net)`. No import/export round-trip is needed or faster.

`AcPowerFlowResult` already carries exactly what "report convergence" needs: `converged: bool`
and `message: str | None` (from the M2 R1 fold, per the wave brief's expectation). **What it
does *not* carry, and what "and limit violations" needs new work for**:

- `BranchResult.loading_pct` (already `p_from_mw / rating_mva`-derived, `None` when unrated)
  gives thermal overload directly — `loading_pct > 100` — **but see §6: no fixture has a rated
  branch today**, so this check is currently untestable against real data.
- Voltage-limit violation needs `Bus.v_min_pu`/`v_max_pu`, which live only on
  `model.Network.buses` (see `entities.py:41-42`), **not** on `results.BusResult` (which has
  only the solved `vm_pu`, no bounds). A violations summary therefore needs **both** the
  original `Network` (for limits) and the `AcPowerFlowResult` (for state) — there is no
  existing type that already combines them. This is a real design decision: does `contingency`
  or a shared `results` helper own a `Violations`/`FeasibilityReport` type, and does it belong
  to `opf.dc_opf`'s own result (an optional `ac_check` field) or to a separate callable the job
  runner composes?
- Generator P-bound violation is not checked by `solve_ac` at all (it enforces reactive limits
  via Q-limit PV→PQ pinning, but active dispatch is whatever the caller supplied) — worth
  naming since a DC-OPF dispatch should already respect P bounds by LP construction, so this is
  more a documentation point than a missing check, but the design interview should confirm that
  reasoning rather than have it assumed silently.

## 6. Branch ratings — none exist in the fixture set

probe: `<scratchpad>/probe_ratings.py` (via `mambo_power.io.matpower.load`) and an independent
`awk` pass over each raw `.m` file's `mpc.branch` block, column 6 (`RATE_A`):

```
case14:      n_branch=20  rated=0  unrated=20
case_ieee30: n_branch=41  rated=0  unrated=41
case57:      n_branch=80  rated=0  unrated=80
case118:     n_branch=186 rated=0  unrated=186
case300:     n_branch=411 rated=0  unrated=411
```

```
awk column-6 (RATE_A) distinct values, all 5 fixtures: {0}
```

Confirmed two independent ways: the importer's own output (`rating_mva=row[5] if row[5] > 0
else None`, `io/matpower.py:378` — MATPOWER's own "0 means unlimited" convention) and a raw
byte scan of every fixture. **Every branch in every one of the 5 OPF/N-1 fixtures is
unrated.** This is not a corner case — it is the entire fixture set.

**Consequences, stated plainly because this is load-bearing for both R3 and R4**:

- R3's "PTDF limits" constraint in `opf.dc_opf`'s LP has no rating data to constrain against on
  any of the 5 fixtures — the LP would need either synthetic/derived ratings (a new fixture, or
  a documented convention like "rating = k × base-case flow"), or the flow-limit constraint
  needs to be tested against a hand-built network (as M1 did for LODF's six-bus unit case) with
  parity against the *live* fixtures necessarily testing only the unconstrained-dispatch path
  (no rating ever binds).
- R4's N-1 "flag branch outages that would violate a limit" is untestable against real limits
  on any of the 5 fixtures for the same reason — the brute-force agreement test (§4) can still
  prove LODF-screen-vs-full-re-solve *flow* agreement without any rating, but "violate a limit"
  specifically needs one.
- This was **not** surfaced in M1 or M2's research/audit docs as a concern (both waves' own
  scope did not need branch ratings) — it is new information for M3, not a re-litigation of a
  settled point.

**Open question for the design interview**: does M3 add rating data (a derived fixture set with
synthetic `RATE_A`, analogous to `fixtures/matpower/derived/case14_island.m` etc.), pull ratings
from a different published source for these same five IEEE systems, or accept that limit-bound
behavior is validated only against a hand-built unit-tier network while the 5 live fixtures
prove the *unconstrained* LP and LODF-screen-vs-brute-force agreement?

## 7. jobs registry extension — what `opf.dc`/`n1` need

read: `src/mambo_power/jobs/registry.py`, `run.py`, `models.py` (full files).

Mechanically, exactly as M2 built it — no plugin system, four hand-edits per new kind:

1. A `pydantic.BaseModel` options pair (or `None` if the kind takes none) + a result model
   (subclass of whatever combines with `results.ResultModel`, e.g. an `OpfDcResult` with
   dispatch, duals, LMP-shaped fields — `SolveResult.result`'s annotation
   (`jobs/models.py:30`) is a **closed union** (`AcPowerFlowResult | DcPowerFlowResult` today)
   that must be widened by hand to add the new result type(s); there is no discriminated-union
   auto-registration.
2. A runner function `(Network, BaseModel | None) -> BaseModel` matching the `Runner` alias.
3. A `KindSpec(kind="opf.dc", options_model=..., result_model=..., runner=...)` passed to
   `register()` in `registry.py` (raises `ValueError` on a duplicate key — cheap safety net).
4. `FailureCode` (`jobs/models.py:33-41`, currently `UNKNOWN_KIND | BAD_REQUEST | BAD_OPTIONS |
   VALIDATION | NO_SLACK_GENERATOR | UNSOLVABLE_NETWORK | INTERNAL`) is a plain `Literal` — a
   new failure mode needs a new string added here by hand, and `run.py`'s runner-exception
   `except` chain (`run.py:154-161`) needs a matching `except SomeNewError` clause, mirroring
   how `NoSlackGeneratorError`/`UnsolvableNetworkError` are wired today.

**LP infeasible/unbounded as a `FailureCode`**: confirmed via probe
(`<scratchpad>/probe_highs_status.py`) that `highspy` reports these as **distinct** model
statuses — `h.modelStatusToString(h.getModelStatus())` returns the literal strings
`"Infeasible"` and `"Unbounded"` for two minimal LPs constructed to be each. This mirrors the
`UNSOLVABLE_NETWORK` precedent exactly (a valid `Network` that the *solver* it was handed to
cannot solve — user data, not a package bug) and **should get its own code(s)**, distinct from
`INTERNAL`. Open question: one shared code (e.g. `INFEASIBLE_LP` covering both HiGHS statuses,
with the distinction carried in the message) or two (`INFEASIBLE_LP` / `UNBOUNDED_LP`) — the
design interview should decide; both are cheap to add either way.

## 8. Naming / module layout

Confirmed absent: `src/mambo_power/opf/` and `src/mambo_power/contingency/` do not exist
(`ls src/mambo_power/`: `__init__.py, io, jobs, model, numerics, pf, py.typed, results`) —
epic.spec.md's module table (`opf/ dc_opf (single LP builder over highspy, duals returned)`,
`contingency/ n1`, lines ~132-135) names locations M3 creates fresh, not locations that already
exist and need extending.

`numerics.ptdf` lives at `src/mambo_power/numerics/ptdf.py` (`ptdf(arr, slack=None) ->
FloatArray`, dense `n_branch × n_bus`, slack column zeroed, one sparse LU factorisation reused
for all right-hand sides). `numerics.lodf` lives at `src/mambo_power/numerics/lodf.py`
(`lodf(arr, ptdf_matrix=None) -> FloatArray`, dense `n_branch × n_branch`, bridge columns
`NaN`, diagonal `-1`; `bridges(arr) -> list[int]`, an independent Tarjan lowpoint search used
both for its own bridge-column proof and, per §4, to skip un-outageable branches in brute-force
loops). Both are exactly what `opf.dc_opf`'s flow-limit rows and `contingency.n1`'s LODF screen
need, already built and already parity-tested (M1).

`tests/_brute_force_lodf.py` is the exact reusable pattern named in the wave brief — confirmed
its structure (deep-copy-once, flip `in_service`, `validate_network`, rebuild `NetworkArrays`,
restore) and its cost characteristics per §4; M3's N-1 brute-force agreement test should share
this shape (possibly literally reuse the module, generalised from "outage → PTDF diff" to
"outage → DC re-solve → limit check", or add a sibling helper next to it).

---

## Carry-forward list for the M3 design interview

1. **Biggest open question**: PyPSA `optimize` is Infeasible on all 5 fixtures after a manual
   gencost bridge, root cause undiagnosed (§3.1) — decide whether to invest more time
   diagnosing it, drop PyPSA from M3's automated parity and rely on pandapower `rundcopp` alone
   (proven clean on all 5), or scope PyPSA to a single hand-verified case.
2. **Second open question, equally load-bearing**: no branch in any of the 5 fixtures carries a
   rating (§6) — both R3's flow-limit LP rows and R4's "violates a limit" check need rating
   data that does not exist in the current fixture set. Decide: synthetic/derived ratings (new
   fixture files), a different data source, or unit-tier-only limit-bound testing.
3. `PiecewiseCost` does not validate convexity (§2.3) — a non-convex PWL cost would silently
   corrupt the LP dispatch, not fail loudly. No fixture exercises PWL at all (§2.2), so this
   needs either a synthetic fixture or a hand-built unit-tier network either way, which is the
   moment to also decide whether to add the convexity guard.
4. Assumption 2 is proven true with exact API calls (`Highs.getSolution().row_dual`/`col_dual`
   after `.run()`) — no fallback path needed; the design interview can build directly on this
   (§1).
5. N-1 brute force is cheap enough (< 1 s for case300, both with and without per-outage
   `validate_network`) that it likely does not need M1's unit/parity split — but this should be
   re-measured inside the actual pytest harness once written, not assumed from the bare-script
   numbers here (§4).
6. AC-feasibility construction is a simple `model_copy` + per-id `p_mw` overwrite (§5); the
   "violations" reporting type is new work with no existing home — decide where it lives (part
   of `opf.dc_opf`'s result, part of `contingency`, or a new small shared type) and what
   voltage/thermal fields it carries, given §6's rating gap limits what can be exercised now.
7. `FailureCode` needs at least one new entry for LP infeasible/unbounded, mirroring
   `UNSOLVABLE_NETWORK`; HiGHS already distinguishes the two statuses cleanly if the interview
   wants two codes instead of one (§7).
8. `opf/` and `contingency/` are new packages, not extensions of existing ones; `numerics.ptdf`/
   `lodf` are already built, already parity-tested, and directly reusable (§8).
