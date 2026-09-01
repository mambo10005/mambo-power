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
model_plan: see wave-04-nodal-market.plan.md
---

# ADR-007: elastic demand extends the one `dc_opf` LP builder rather than composing a second solver

Status: accepted (wave M4, 2026-08-24; ratified in the Step 2 design interview as Decision 1,
"the latter with cleaner lp code").

## Context

ADR-006 split `opf.dc_opf` into an array-level LP builder (`dc_opf`) and a `Network`-level
wrapper (`solve_dc_opf`) precisely so M4's market clearing could reuse the builder directly.
M4 then had to decide *how* demand-side bids enter that builder, and research
(`record/m4-research.md` §1) established that there were two genuinely workable answers.

**The pseudo-generator trick.** A price-elastic load is algebraically a generator with a
negative-signed, concave cost. `dc_opf` could have been left completely untouched: `market.nodal`
would translate each bid load into a synthetic generator row, solve, and translate the results
back. Nothing in `opf` would change, and the wave would ship without touching M3's
oracle-verified code at all.

**The direct extension.** `dc_opf` grows optional demand-side columns, hypograph rows for
concave PWL bids, and the balance/flow-row terms that go with them — one LP builder that knows
about both sides of the market.

The choice is not local to M4. Every remaining market wave builds an LP on this same seam:
M5 (multiperiod) adds ramp coupling and storage SoC dynamics across 24 periods, M6 (zonal)
adds zonal clearing plus a redispatch LP, M7 (agents) runs bid→clear→settle→learn over the
clearing LP repeatedly. Whichever answer M4 picks is the shape all three inherit.

## Decision

**Elastic demand is a first-class part of the single array-level LP builder.** `dc_opf` gains
`demand_bid_coeffs`/`demand_pwl_bids` parameters, its own demand columns bounded
`[0, load_p_max_pu]` per load (no sign flip), hypograph rows mirroring the generator-side
epigraph construction, and `OpfSolution.demand_dispatch_mw`/`demand_bound`. `market.nodal`
extracts bids from the model and calls it; it does not translate, wrap, or re-solve.

Two consequences of that choice are part of the decision, not incidental:

1. **`dc_opf` owns the double-counting contract itself.** An elastic load's own historical `p_mw`
   is subtracted from the fixed-RHS aggregate *inside* `dc_opf`, read off `arr.load_p_max_pu`,
   rather than the caller being trusted to pre-subtract. A caller cannot get this wrong, because
   a caller cannot do it at all.
2. **Convexity guards live on both sides symmetrically.** `NonConcaveBidError` for a demand bid
   whose marginal value is not non-increasing, and — closing a pre-existing asymmetry M3 left —
   `NonConvexCostError` for a `c2 < 0` generator cost. Both raise before any HiGHS object exists.

## Consequences

**What this buys.** One LP builder, one place where the balance row is assembled, one place
where PTDF-based flow rows are built, one dual-extraction path, and therefore one
`lmp_decomposition` that M4 reuses verbatim. `market.nodal` is thin: extract, call, settle. The
price-taker reduction (AC-5) is exact rather than approximate — with every bid above the
achievable price, the welfare LP *is* the fixed-load LP, so M4 inherits M3's already
oracle-proved DC-OPF parity instead of needing its own from scratch.

**What it costs.** M3's oracle-verified builder was modified rather than left alone, which is
the real risk the pseudo-generator option avoided. The wave paid that down explicitly: 68
existing opf/PWL/parity tests were held green unchanged through the extension, and the
double-counting contract was given a dedicated hand-KKT test (AC-1) plus oracle parity (AC-6).
The Step-6 critic found the AC-6 fixture initially could not detect a double-counting fault in
its dispatch quantities; the R2 fold closed that by anchoring one load's bid around the
fixture's own clearing price (`record/m4-r2-fold-report.md` item D). The lesson generalizes to
every later wave that extends this builder: **a fixture where the answer is pinned by a bound
cannot test the term that moves the answer.**

**What later waves inherit.** M5, M6 and M7 extend this same builder rather than composing new
ones — ramp/SoC coupling, zonal aggregation and redispatch are further column/row families on
`dc_opf`, not separate solvers. The seam is the same one ADR-006 opened; this ADR fixes that it
is the *only* seam. Reversing it after M5 would mean unwinding a builder that three waves call.

**Rejected: the pseudo-generator trick.** Correct and cheaper to land, but it puts the market's
economics in a translation layer nobody can see from the LP, duplicates bound and convexity
handling on the demand side, and leaves each later wave to re-invent its own translation. The
design interview's own words for the alternative chosen — "cleaner lp code" — is exactly the
axis it lost on.

**Lesser M4 decisions are not here.** The `Scenario` shape (`network` only, no periods/strategy
fields — Decision 2, deferred to M5 which actually needs them), the `sgen` oracle-construction
convention for elastic-demand parity, `SolveRequest` staying `Network`-shaped, and the
all-or-nothing-per-`Load` bid contract all live in the wave spec's `## Design`, the plan's
`## Assumptions`, and the docstrings that own them.
