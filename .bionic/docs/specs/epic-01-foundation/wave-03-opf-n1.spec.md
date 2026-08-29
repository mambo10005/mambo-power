---
governing-skill: agent-skills:spec-driven-development
sdlc-step: 2
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
design: specs/epic-01-foundation/epic.spec.md
walk: required
design-interview: true
model_plan:
  orchestrator: sonnet
  implementor: sonnet
  senior-implementor: opus
  researcher: sonnet
  test-runner: sonnet
  auditor: opus
  critic: opus
---

# Wave M3 — opf-n1: DC-OPF with duals, N-1 contingency screening

Epic: .bionic/docs/specs/epic-01-foundation/epic.spec.md (R3, R4, R10, R14). Builds on M2
(merged dcdc1c9). Gives the package optimal (not just feasible) DC dispatch with shadow
prices, and N-1 branch-contingency screening — the two pieces every market wave (M4+) composes
on top of, per the epic's own module table ("`market` composes `opf`").

## Requirements

- W1 — DC-OPF as a single LP over HiGHS: array-level `opf.dc_opf.dc_opf(arr, cost_coeffs,
  options) -> OpfSolution` returning dispatch, objective cost, and duals (balance-row dual,
  per-branch flow-limit-row duals, per-generator bound reduced costs); flow-limit rows built
  from `numerics.ptdf`; supports both polynomial and convex piecewise-linear generator costs.
  provenance: epic R3
- W2 — Reuse seam for M4: `opf.dc_opf` splits array-level (`dc_opf`, on `NetworkArrays`) from
  Network-level (`opf.solve_dc_opf`, the public wrapper), mirroring `pf.ac_newton.newton` vs
  `pf.solve_ac`; `lmp_decomposition(duals, ptdf) -> LmpBreakdown` is a standalone function
  consumed identically by this wave's own `OpfDcResult` and by M4's market clearing later.
  provenance: user 2026-08-23 design interview Q1 ("built with M4's market-clearing reuse in
  mind from the start"); epic Design (module table: "market composes opf")
- W3 — Branch-rating data for testing: no MATPOWER fixture in the repo carries a real
  `RATE_A` (confirmed zero across all five OPF fixtures — record/m3-research.md §6), so a
  documented, programmatic rating-derivation rule (DC-solve the base case once per fixture,
  set each branch's synthetic rating at a documented margin above its base-case `|flow|`),
  applied at test time rather than committed as new fixture data, gives W1's flow-limit rows
  and W5's violation check something real to bind against across the full fixture set.
  provenance: user 2026-08-23 design interview S1; record/m3-research.md §6
- W4 — Piecewise-linear costs: the standard convex segment/epigraph LP encoding (record/
  m3-research.md §2.1); a convexity guard at `opf.dc_opf`'s cost-extraction step (a new
  `opf`-local error, not a retroactive change to `model.PiecewiseCost`'s validation, since no
  wave-M1-shipped surface needs to change for this); one new synthetic derived MATPOWER
  fixture carrying convex PWL costs, since no real fixture has any MODEL-1 cost data.
  provenance: epic R3 ("PWL costs"); record/m3-research.md §2.2-2.3
- W5 — N-1 contingency, branch outages only this wave: `contingency.n1` LODF fast-screen
  (reusing `numerics.lodf`/`numerics.bridges`, both M1-built) flags branch outages whose
  estimated post-outage flow would violate a rating, then a full DC re-solve
  (`pf.dc.solve`, one right-hand side per outage) of each flagged outage confirms; a
  brute-force all-outage sweep proves the screen misses nothing the confirming re-solve
  would catch. Generator-outage contingencies are an explicit carry-over, not silently
  dropped.
  provenance: epic R4; user 2026-08-23 design interview ("N-1 outage types" — branch only)
- W6 — AC-feasibility check: after a DC-OPF dispatch, `pf.solve_ac` re-runs on that dispatch
  (each in-service generator's `p_mw` overwritten from the OPF result, id-keyed) and reports
  convergence plus thermal/voltage violations via a `results.FeasibilityReport`; no
  re-dispatch is attempted on failure — report, don't fix.
  provenance: user 2026-08-23 design interview ("AC feasibility check", in-wave); epic Not
  Doing ("AC feasibility is checked by power flow after DC-OPF")
- W7 — Jobs API: `opf.dc` and `n1` kinds added to `jobs.KINDS`, via the exact four-edit
  mechanism M2 established (options/result model pair, runner, `KindSpec`, `FailureCode`
  widening); two new structured failure codes, `INFEASIBLE_LP` and `UNBOUNDED_LP`, since
  HiGHS distinguishes these as separate model statuses (record/m3-research.md §7) and an
  unsolvable LP is user-data, not `INTERNAL`, matching the M2 R1 fold's `UNSOLVABLE_NETWORK`
  precedent.
  provenance: epic R10; record/m3-research.md §7
- W8 — OPF parity oracles: pandapower `rundcopp` (primary, converges cleanly on all five
  fixtures — record/m3-research.md §3) and PyPSA `optimize` (secondary; requires clearing
  the imported base-case `p_set` pin before solving, root-caused and fixed —
  m3-pypsa-diag-result.md) on the full M1/M2 fixture set: case14, case_ieee30, case57,
  case118, case300.
  provenance: epic R3; user 2026-08-23 design interview ("fixture scope"); record/
  m3-research.md §3, .bionic/tmp/m3-pypsa-diag-result.md
- W9 — Documentation: manual pages for DC-OPF and N-1 added to the existing mkdocs site; API
  reference entries for `opf`/`contingency` (covered automatically by the M2 R1 fold's
  symbol-coverage test, which walks packages generically); one new runnable example under
  `examples/`, CI-executed and snippet-embedded, following M2's established pattern.
  provenance: epic R14

## Not Doing (M3)

Generator-outage N-1 (carry-over) · N-2+ contingencies · SCOPF / preventive or corrective
redispatch on an AC or N-1 violation (report only, this wave) · AC-OPF as an optimization
(only a post-dispatch AC feasibility *check*) · market clearing, Scenario offers/bids (M4) ·
sourcing branch ratings from an external published dataset · retroactive convexity validation
on `model.PiecewiseCost` (carry-over, logged) · running actual MATPOWER (`rundcopf` via
Octave/MATLAB) — not a repo dependency, matches M1/M2's precedent of using pandapower/PyPSA
as the real oracles · PyPSA as the primary/sole oracle (secondary, pandapower is primary).

## Prior art (alternatives lens)

MATPOWER `rundcopf`'s LP/QP formulation (structure reference, not executed); pandapower
`rundcopp` (primary executable oracle); PyPSA `optimize` (secondary executable oracle, after
fixing its base-case `p_set` pin); the standard convex PWL-as-LP epigraph/segment
construction (textbook OPF formulation); HiGHS's own dual/reduced-cost API
(`Highs.getSolution().row_dual`/`col_dual`, proven directly — record/m3-research.md §1);
LODF-based contingency screening (the same numerics M1 already built and parity-tested for
its own sake).

## Acceptance criteria

AC-1: `opf.solve_dc_opf` converges to Optimal on case14, case_ieee30, case57, case118, and
  case300, and its dispatch + objective cost matches pandapower `rundcopp` within a tolerance
  pinned during implementation (parity-tier precision, mirroring M2's AC-1 discipline of
  measuring and recording the actual residual rather than assuming a round number); PyPSA
  `optimize` (with `p_set` cleared before solving) matches within the same band on 4/5
  fixtures and within a separately documented, wider band on case300 (the ~0.007% relative
  residual found in diagnosis, named not chased).
  provenance: W1, W8; record/m3-research.md §3, .bionic/tmp/m3-pypsa-diag-result.md
AC-2: On a hand-built network with a known binding flow limit and a generator pinned at its
  bound, `dc_opf`'s returned duals reproduce the balance-row dual as the marginal price, a
  nonzero flow-limit-row dual exactly on the binding row, and a nonzero bound reduced cost
  exactly on the pinned generator — proving `opf.dc_opf`'s own wiring of the dual API is
  correct (the API itself is already proven generically in record/m3-research.md §1; this AC
  proves the wave's use of it).
  provenance: W1; record/m3-research.md §1
AC-3: `opf.dc_opf.dc_opf(arr, cost_coeffs, options)` accepts a caller-supplied
  cost-coefficient array independent of `Network.generators[i].cost` — proven by solving the
  same `NetworkArrays` with two different synthetic cost arrays and getting two different,
  each internally-consistent (LP-optimal for its own objective) dispatches; `lmp_decomposition`
  is importable and callable independent of `solve_dc_opf`'s own result construction.
  provenance: W2
AC-4: The rating-derivation helper, given a fixture's solved base-case DC flow, produces
  ratings such that the base-case dispatch itself never violates them (by the documented
  margin), and at least one branch outage in at least one fixture causes a violation under
  the derived ratings — so W5's violation-check path is exercised on real multi-bus data, not
  only a hand-built network.
  provenance: W3, W5
AC-5: On the new synthetic PWL-cost derived fixture, `opf.dc_opf` matches an oracle (pandapower
  `rundcopp` if it accepts piecewise costs — to be confirmed at implementation; else a
  hand-built dense-LP comparison, recorded either way) within tolerance; a non-convex PWL cost
  is rejected by the new convexity-guard error before any solve is attempted (unit-tier hand
  case).
  provenance: W4
AC-6: On every fixture (using W3's derived ratings), the set of branch outages confirmed as
  violating a rating by LODF-screen-then-DC-reslve equals the set confirmed by a brute-force
  all-branch-outage sweep — the agreement test R4 names.
  provenance: W5
AC-7: On a hand-built case with a known thermal or voltage violation under a given OPF
  dispatch, `FeasibilityReport` reports it (branch/bus id, measured value, limit); on a clean
  case, reports none; `FeasibilityReport.converged` matches `solve_ac`'s own convergence flag
  on the same dispatch.
  provenance: W6
AC-8: `jobs.run`/`jobs.run_json` with kind `opf.dc` and `n1` round-trip through JSON, are pure
  (two runs on the same input equal modulo timing), and never raise across the boundary; an
  infeasible LP (a hand-built case with contradictory generator bounds) yields
  `INFEASIBLE_LP`, not `INTERNAL`; `jobs.KINDS` lists exactly `pf.ac`, `pf.dc`, `opf.dc`, `n1`
  with importable models and a callable runner for each (contract test, mirroring M2's AC-6).
  provenance: W7
AC-9: `uv run mkdocs build --strict` exits 0 with the new OPF/N-1 manual pages and `opf`/
  `contingency` API reference entries present; the M2 R1 fold's symbol-coverage test passes
  for both new packages without modification; the new example script exits 0 in the CI
  `examples` job and is embedded in a manual page by snippet.
  provenance: W9

## Design

Governing design: epic spec §Design; M2's wave spec §Design for the `pf`/`results`/`jobs`
patterns this wave extends rather than reinvents. M3-local decisions (ratified 2026-08-23):

1. **LP builder split (W1, W2).** `opf/dc_opf.py:dc_opf(arr: NetworkArrays, cost_coeffs:
   FloatArray, options: OpfDcOptions) -> OpfSolution` is the array-level entry point — pure
   numerics, no `Network`/`Scenario` dependency, mirroring `pf.ac_newton.newton`/`pf.dc.solve`.
   `opf/__init__.py:solve_dc_opf(net: Network, options: OpfDcOptions | None = None) ->
   OpfDcResult` is the thin Network-facing wrapper: derives `cost_coeffs` from
   `net.generators[i].cost` (raising `NonConvexCostError` if a `PiecewiseCost` fails a
   convexity check done here, not in `model`), calls `dc_opf`, and — when `options.ac_check`
   is true — runs `pf.solve_ac` on the dispatched network for `OpfDcResult.ac_check`.
2. **LMP decomposition (W2).** `opf/dc_opf.py:lmp_decomposition(duals: OpfDuals, ptdf:
   FloatArray) -> LmpBreakdown` is a standalone function: per-bus LMP = balance dual (energy)
   + Σ(flow-limit-row duals × that bus's PTDF column) (congestion). `solve_dc_opf` calls it to
   populate `OpfDcResult.lmp`; M4's `market.nodal` calls the identical function later.
3. **Rating derivation for testing (W3).** A shared test helper (mirroring the
   `tests/_brute_force_lodf.py` precedent — a documented, test-time transformation of an
   already-owned fixture, not new committed data): DC-solve the unmodified fixture once, set
   each branch's `rating_mva` at a fixed margin above its base-case `|p_from_mw|` (exact
   margin pinned during implementation, not in this spec). Applies to all five OPF fixtures
   uniformly.
4. **PWL costs (W4).** Convex segment/epigraph LP rows built from `PiecewiseCost.points`
   inside `dc_opf`'s cost-coefficient extraction; `opf.NonConvexCostError` (new, `opf`-local)
   raised when the point sequence's slopes are not non-decreasing. One new derived fixture
   (case14-based, 1-2 generators converted to MODEL-1 convex PWL costs, documented cell by
   cell like M1's derived fixtures) exercises it against an oracle.
5. **N-1 (W5).** `contingency/n1.py:screen_n1(arr, options) -> N1Screen` (LODF-based fast
   screen against W3's derived ratings) → confirming DC re-solve per flagged outage
   (`pf.dc.solve`) → `N1Result`. Public `contingency.n1(net, options) -> N1Result`. Branch
   outages only; the brute-force agreement test reuses `_brute_force_lodf.py`'s
   deep-copy-once/flip/rebuild shape, generalized from "outage → PTDF diff" to "outage → DC
   re-solve → limit check" (record/m3-research.md §4 measured this at < 1 s for case300,
   likely staying in the unit tier — reconfirmed once the real test exists).
6. **AC-feasibility check (W6).** `results.FeasibilityReport` (new, shared — not siloed in
   `opf` — since a later wave's AC-checked N-1 state would want the identical shape): carries
   `converged: bool`, `message: str | None`, `thermal_violations: list[...]` (branch id,
   loading_pct, limit), `voltage_violations: list[...]` (bus id, vm_pu, limit). Built from a
   `model_copy(deep=True)` of the dispatched `Network` (for bounds) plus the `AcPowerFlowResult`
   (for state) — both are needed, neither alone carries both bounds and solved state.
7. **Jobs (W7).** `opf.dc`/`n1` `KindSpec`s follow M2's registry mechanism exactly.
   `FailureCode` gains `INFEASIBLE_LP`/`UNBOUNDED_LP`, distinguished from HiGHS's own
   `Infeasible`/`Unbounded` model-status strings; `jobs/run.py`'s runner-exception chain gains
   matching `except` clauses for the new `opf`/`contingency` error types.
8. **Verification policy (W8, AC-1).** pandapower `rundcopp` primary oracle on all 5 fixtures;
   PyPSA `optimize` secondary, `p_set` cleared before solving (m3-pypsa-diag-result.md); the
   case300 PyPSA residual (~0.007%) is named and excluded, not silently rounded into a looser
   band that would also mask a real regression on the other four fixtures.
9. **Docs (W9).** New manual pages for DC-OPF and N-1 under the existing `docs/manual/`; new
   `docs/api/opf.md` and `docs/api/contingency.md` following the mkdocstrings pattern the M2
   R1 fold's coverage test already enforces generically; one new `examples/08_opf_and_n1.py`
   (or similar), CI-executed and snippet-embedded.

Ownership additions: DC-OPF dispatch/duals → `opf.dc_opf` (consumers: `opf.solve_dc_opf`,
`jobs` kind `opf.dc`) — agreement test: AC-1 (pandapower/PyPSA parity); LMP decomposition →
`opf.dc_opf.lmp_decomposition` (consumers: `OpfDcResult.lmp` now, `market.nodal` in M4) —
agreement test: AC-2/AC-3 now, an M4 settlement-identity test later; N-1 screen-vs-confirm →
`contingency.n1` (consumers: `results.N1Result`, `jobs` kind `n1`) — agreement test: AC-6;
AC-feasibility → `results.FeasibilityReport` (consumers: `OpfDcResult.ac_check`) — agreement
test: AC-7.

Rejected: Network-level-only `opf.dc_opf` with no array-level split (forces M4 to duplicate
the LP builder or fake a `Network` from a `Scenario`); sourcing branch ratings from a
different published dataset (second external source, licence/provenance risk, no guarantee it
matches these exact `.m` files); five new committed "rated" fixture files (sprawl; a
documented programmatic rule covers the whole set at once); retroactive convexity validation
on `model.PiecewiseCost` (out of this wave's scope, touches M1's already-audited surface —
carried over instead); dropping PyPSA without the bounded diagnostic (the diagnostic
succeeded cheaply, so PyPSA is a genuine second oracle now, matching M1/M2's dual-oracle
discipline).

Assumptions: (a) the rating-derivation margin (how far above base-case flow) is pinned during
implementation, not fixed in this spec, and must be tight enough that at least one N-1 outage
actually violates it on at least one fixture (AC-4) — a margin so generous that nothing ever
binds would make AC-4 and the "violates a limit" half of AC-6 powerless; (b) pandapower
`rundcopp`'s support for piecewise-linear costs is unconfirmed as of this spec (research
checked polynomial costs only, since no real fixture has PWL data) — AC-5's oracle choice is
conditional on that check, resolved at implementation, not assumed here; (c) generator-outage
N-1 and the `PiecewiseCost` convexity gap in `model` are carry-overs for a later wave, not
silent drops — log them in this wave's own Assumptions/carry-over list at Step 4/5 the way
M2's R1 fold logged A13/A14.
