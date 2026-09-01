---
governing-skill: agent-skills:spec-driven-development
sdlc-step: 4
---

# M3 S2 report — opf-core

Slice S2 of wave M3 (opf-n1): `opf/dc_opf.py` array-level LP/QP builder + duals +
`lmp_decomposition`, `opf/__init__.py:solve_dc_opf` wrapper. AC-1 (parity half), AC-2, AC-3.
Commit `d6d3ef5` on `wave/03-opf-n1` (pushed).

## What was built

- **`src/mambo_power/opf/dc_opf.py`** — `dc_opf(arr, cost_coeffs, options) -> OpfSolution`, the
  array-level entry point over `highspy.Highs`. One generator column per `NetworkArrays`
  generator (bounded `[p_min_mw, p_max_mw]`), one system-wide nodal-balance equality row, one
  PTDF-based flow-limit row per branch (unrated branches get an `[-inf, inf]` row, never binds).
  Duals read directly from `Highs.getSolution().row_dual`/`col_dual` after `.run()`. Also
  `lmp_decomposition(duals, ptdf) -> LmpBreakdown` (standalone), `OpfDcOptions`, `OpfDuals`,
  `OpfSolution`, `LmpBreakdown`.
- **`src/mambo_power/opf/__init__.py`** — `solve_dc_opf(net, options) -> OpfDcResult`: derives
  `cost_coeffs` from `Generator.cost` (raises `NotImplementedError` for `PiecewiseCost`, S3's
  job), calls `dc_opf`, decomposes LMPs, builds the typed result.
- **`src/mambo_power/results/opf.py`** — `OpfDcResult`, `GenDispatchResult`, `BusLmpResult`,
  `OpfBranchFlowResult` (id-keyed rows + `ResultProvenance`, mirrors the `pf` result pattern).
- **`src/mambo_power/results/feasibility.py`** — `FeasibilityReport`, `ThermalViolation`,
  `VoltageViolation` (spec design item 6). Minimal stub so `OpfDcResult.ac_check` typechecks;
  not populated this slice — wave M3 slice S5 wires the actual AC-feasibility-check logic.
- `src/mambo_power/results/__init__.py` — exports for all of the above.

## The load-bearing design finding: real quadratic costs, QP not pure LP

The dispatch brief framed this as "a single LP", following the research doc's proof of the
HiGHS dual-reading API on a pure-LP example. Direct inspection of all 5 OPF fixtures' raw
`gencost` blocks (not assumed from the research doc, which only confirmed MODEL=2/polynomial,
not the coefficient degree) showed every fixture carries genuine **nonzero quadratic (`c2`)
coefficients** — e.g. case14's cheapest generator: `c2=0.043, c1=20, c0=0`. pandapower's own
`_from_ppc_gencost` maps these straight into `cp2_eur_per_mw2`/`cp1_eur_per_mw`/`cp0_eur`
(confirmed by reading its source directly), the same unscaled `cost(p) = c2·p² + c1·p + c0`
convention MATPOWER's gencost itself uses. A pure-linear-cost LP would not have reproduced
pandapower `rundcopp`'s actual dispatch on this fixture set — not a minor precision gap, a
structurally different (and wrong) answer.

Resolution, verified before relying on it: `highspy.Highs` supports convex QP via
`Highs.passHessian(HighsHessian)` on top of the exact `addVars`/`changeColsCost`/`addRows` CSR
API the research doc proved for LP duals. Built a 2-generator QP by hand (probe, not committed),
diagonal Hessian value `2*c2` (HiGHS's `0.5·xᵀQx` convention), and the dispatch/duals matched an
independent hand-KKT solve exactly (28.333/21.667 MW; `row_dual` = 10.667 = the marginal cost at
the optimum). `dc_opf` therefore stays a pure LP (no `passHessian` call at all) whenever every
generator's `c2` is exactly 0 — the common case, and the literal "single LP" the spec
describes — and transparently extends to a QP only when a nonzero `c2` is present. No
QP-specific dual-reading logic was needed; `Highs.getSolution()` reads identically either way.

## RED → GREEN evidence, per piece

1. **AC-2 (hand-built duals)** — `tests/unit/test_opf_dc.py`. RED: `ModuleNotFoundError: No
   module named 'mambo_power.opf'` (confirmed before writing any implementation). GREEN after
   `dc_opf`: 5/5 passed. Hand-built 3-bus/3-generator triangle network, equal branch reactances,
   designed so a slack-bus generator's PTDF column is exactly zero by construction — gives a
   closed-form oracle for the balance dual (the unconstrained slack generator's own linear cost,
   `10.0`) without needing to solve a coupled dual system. Confirmed: balance dual == 10.0
   exactly; flow-limit dual nonzero exactly on the one rated, binding branch (`br12`), zero on
   the two unrated branches; generator-bound reduced cost nonzero exactly on the one pinned
   generator (`g0`, at `p_max`), zero on the other two (both interior). A first draft of the
   AC-3 test (varying a generator's *constant* cost term between two solves) failed correctly —
   a constant doesn't affect the LP optimum, so the two dispatches were identical; this was a
   test-design bug, not an implementation bug, fixed by varying the *linear* coefficient instead.
2. **AC-3 (cost independence + standalone `lmp_decomposition`)** — same file, 2/2 passed. Two
   different synthetic `cost_coeffs` arrays over the same `NetworkArrays` give two different,
   each internally-LP-optimal dispatches (`g2=85` vs `g2=30` MW depending on whether it's
   cheaper or more expensive than the alternative). `lmp_decomposition` called directly with a
   hand-built `OpfDuals`/PTDF pair, zero calls to `dc_opf`/`solve_dc_opf` anywhere in that test.
3. **`solve_dc_opf` wrapper wiring** — `tests/unit/test_opf_solve_dc_opf.py`. RED: `ImportError:
   cannot import name 'solve_dc_opf'`. GREEN after the wrapper: 4/4 passed — dispatch/LMP/flow
   row construction, provenance (`kind="opf.dc"`, `solver="highspy.Highs"`), the free-generator
   (no cost) convention, and the `PiecewiseCost` → `NotImplementedError` seam.
4. **AC-1 (parity half)** — `tests/parity/test_opf_vs_pandapower.py`. The RED-equivalent step
   here was an exploratory probe script (not committed) comparing `solve_dc_opf` against
   pandapower `rundcopp` before any parity test file existed — this is what surfaced the
   quadratic-cost finding above; by the time the pytest file was written the underlying
   implementation was already correct, so the file went straight GREEN (20/20 passed) and now
   stands as the regression test. See measured residuals below.

## AC-1 parity: measured residuals (pandapower `rundcopp`, all 5 fixtures)

Oracle: the same construction `tests/parity/test_dc_vs_pandapower.py` already uses
(`_mpc_reader`, `BASE_KV<=0 -> 1.0` patch, `pandapower_from_raw` with `trafo_model="pi"`), run
through `pp.rundcopp` instead of `pp.rundcpp`.

| fixture | status | cost rel. diff | worst per-gen dispatch abs. diff (MW) |
|---|---|---|---|
| case14 | Optimal | 4.3e-12 | 3.1e-05 |
| case_ieee30 | Optimal | 1.6e-11 | 3.6e-05 |
| case57 | Optimal | 4.6e-13 | 7.6e-04 |
| case118 | Optimal | 3.5e-13 | 6.5e-04 |
| case300 | Optimal | 5.2e-12 | 1.42e-02 |

Tolerances pinned with margin above measured: `COST_REL_TOL = 1e-7`, `DISPATCH_ABS_TOL_MW =
0.05`. Also asserted (not just cost/dispatch): every branch's flow-limit dual is exactly `0.0`
on all 5 fixtures — confirms the wave's own research finding (no fixture rates a branch, per
`m3-research.md` §6) is still true and that no flow constraint is silently binding anywhere.

**A genuine formulation difference was found and checked, not assumed away.** pandapower's
`rundcopp` marks the slack-bus generator (`ext_grid`) `controllable=False`: it solves a full
nodal, theta-based OPF where the slack generator's dispatch is the network's power-balance
residual (a dependent variable), not a bounded decision variable — though its real cost
coefficients are still charged in the reported total cost. `opf.dc_opf`'s PTDF-based
formulation makes *every* generator, including the one at the slack bus, a normal decision
variable bounded by its own `[p_min, p_max]` in a single system-wide balance row. These two
formulations are only guaranteed to produce the same answer when (a) no branch is rated, so
`dc_opf`'s flow-limit rows never bind (true here, confirmed above), and (b) the slack-bus
generator's own bounds never happen to bind in the oracle's unconstrained dispatch — true on
all 5 fixtures as measured (case14's `ext_grid` dispatches ~221 MW against declared bounds
`[0, 332.4]`, comfortably interior), but not proven true in general. This is named explicitly in
the plan's AC-1 evidence block, not silently rounded into a looser tolerance.

**PyPSA (secondary oracle) was not attempted this slice.** The task named it a bonus, not a
blocker, and the time budget went to root-causing the quadratic-cost/QP finding above, which was
load-bearing for AC-1 to pass at all (the pandapower-half parity would have failed outright
without it). Named as an open carry-over in the plan, per the wave's own carry-over discipline.

## Shared-worktree coordination note

Mid-slice, `git status` showed a live, uncommitted second agent (S4/contingency) also editing
`src/mambo_power/results/__init__.py` — a file I also needed to edit — beyond the single
concurrent agent (S1, disjoint files) named in the dispatch. Flagged this to the team lead
(`main`) via `SendMessage` as soon as found, then continued independent work while it resolved
on its own: S4 committed (`3c84504`) before I needed to commit, so by commit time `git diff`
against the new `HEAD` showed my working copy's `results/__init__.py` hunk contained *only* my
own additions (S4's N1 exports were already in `HEAD`, not in my diff) — verified explicitly
before staging. No file was force-overwritten or restored; the two agents' edits to the shared
file composed cleanly without any manual conflict resolution needed.

## Verification

`ruff check .` / `ruff format --check .` clean repo-wide. `mypy src` (`--strict`) clean (one
`# type: ignore[no-untyped-call]` on `highspy.Highs()`, which ships no type stubs). Full
`pytest -q -m "unit or parity"`: **539 passed** (includes S1's and S4's concurrent work in this
shared worktree, not just S2's own tests).

## Carry-overs (named, not silently dropped)

- PyPSA as AC-1's secondary oracle — not attempted this slice (see above).
- The pandapower-`ext_grid`-vs-`dc_opf`-slack-generator formulation difference — shown
  immaterial on these 5 specific fixtures, not proven equivalent in general; a future fixture
  with a tightly-bound slack generator's own capacity could diverge and would need revisiting.
- `PiecewiseCost` support in `dc_opf` — explicit `NotImplementedError` seam, S3's job (per this
  slice's own scope).

## Commit

`d6d3ef5` on `wave/03-opf-n1`, pushed. 8 files, 984 insertions:
`src/mambo_power/opf/__init__.py`, `src/mambo_power/opf/dc_opf.py`,
`src/mambo_power/results/__init__.py`, `src/mambo_power/results/feasibility.py`,
`src/mambo_power/results/opf.py`, `tests/parity/test_opf_vs_pandapower.py`,
`tests/unit/test_opf_dc.py`, `tests/unit/test_opf_solve_dc_opf.py`.
