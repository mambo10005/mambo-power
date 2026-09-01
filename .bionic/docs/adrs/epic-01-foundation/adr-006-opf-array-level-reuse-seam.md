---
governing-skill: agent-skills:documentation-and-adrs
sdlc-step: 7
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
model_plan: see wave-03-opf-n1.plan.md
---

# ADR-006: `opf.dc_opf` splits array-level from Network-level so M4 reuses the LP builder directly

Status: accepted (wave M3, 2026-08-23; ratified in the Step 2 design interview, "that seam
matches, go ahead").

## Context

The epic's own module table already commits `market` to composing `opf` (epic.spec.md §Design:
"`market` composes `opf`, ..."). M4 (`nodal-market`) is described identically to DC-OPF with a
different cost source: "`market.nodal` day-ahead clearing... LMP = energy + congestion
decomposition" is, mechanically, `opf.dc_opf` with `Scenario` offers/bids substituted for
generator fuel costs — the LMP decomposition M3 needs for its own result is exactly the
decomposition M4 needs for settlement. M3's Step 2 design interview surfaced a real fork before
any code existed: build `opf.dc_opf` as a single `Network`-in/`OpfDcResult`-out function (simplest
for M3 alone), or split it the way `pf` already splits twice (`ac_newton.newton(arr, ...)` vs
`solve_ac(net, ...)`; `pf.dc.solve(arr, ...)` vs its wrapper) so M4 can call the LP builder
directly with offer-derived costs. This is a "cannot be changed later without a rewrite of the
consumer" decision in the same sense ADR-005 (units) was for M1: M4 will be written against
whichever shape M3 ships.

## Decision

`opf/dc_opf.py:dc_opf(arr: NetworkArrays, cost_coeffs, options: OpfDcOptions) -> OpfSolution` is
the array-level entry point — pure numerics over `NetworkArrays` plus a caller-supplied
cost-coefficient input, no `Network`/`Scenario` dependency, mirroring `pf.ac_newton.newton`/
`pf.dc.solve` exactly. `opf/__init__.py:solve_dc_opf(net: Network, options) -> OpfDcResult` is a
thin wrapper that derives `cost_coeffs` from `net.generators[i].cost` and calls `dc_opf`.
`opf/dc_opf.py:lmp_decomposition(duals, ptdf) -> LmpBreakdown` is a standalone function computing
per-bus LMP = balance dual (energy) + Σ(flow-limit duals × PTDF column) (congestion); `solve_dc_opf`
calls it for `OpfDcResult.lmp`, and it is independently callable with hand-built inputs (proven by
wave M3's AC-3).

When M4 builds `market.nodal`, it is expected to call `opf.dc_opf.dc_opf` and `lmp_decomposition`
directly with offer/bid-derived `cost_coeffs`, not `opf.solve_dc_opf` and not a `Network`
constructed to smuggle a `Scenario` through the wrong door.

## Consequences

- Costs M3 one extra thin wrapper (`solve_dc_opf`) it would not otherwise need, in exchange for
  M4 needing zero new LP-building code.
- The array-level/Network-level split this ADR extends to `opf` is now the established pattern
  for every solver-shaped module in this repo (`pf.ac_newton`, `pf.dc`, `opf.dc_opf`) — a future
  `contingency`-style module that only ever takes a `Network` (as `contingency.n1` does today,
  correctly, since nothing yet needs its array-level pieces independently) is not obligated to
  split preemptively; the split is earned by a real second caller, not applied by default.
- Rejected: a single `Network`-in/`OpfDcResult`-out `opf.dc_opf`, requiring M4 to either
  duplicate the LP builder or construct a fake `Network` from a `Scenario` just to reuse it.
