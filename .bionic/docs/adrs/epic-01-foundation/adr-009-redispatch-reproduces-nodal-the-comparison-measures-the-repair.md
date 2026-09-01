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
model_plan: see wave-06-zonal-redispatch.plan.md
---

# ADR-009: redispatch reproduces nodal by construction — the comparison measures the repair, not a gap

Status: accepted (wave M6, 2026-08-27; ratified in the Step 2 design interview as Decision D1,
"True cost/value curves").

## Context

The epic carve for M6 asked for "zonal clearing LP, min-cost redispatch LP, nodal-vs-zonal
comparison result" with the invariant `cost ≥ nodal`. Two Step-1 scope answers shaped what that
could mean: redispatch is priced at each unit's **own** cost curve in both directions, and elastic
demand participates in **both** LPs. Research then showed that under those answers the redispatch
LP's objective is a free choice with two readings — and that the choice decides what the wave
measures.

**The true-curve reading.** If the redispatch objective is the true generation cost minus the true
bid value of the *final* quantities, the redispatch LP has the nodal welfare LP's exact feasible
set and an objective equal to nodal's up to a constant. It therefore returns the nodal optimum from
*any* feasible starting point. `welfare(zonal + redispatch) − welfare(nodal)` is identically zero;
the epic's `cost ≥ nodal` is met as an equality, always.

**The anchored-rate reading.** If each unit is priced at its marginal cost or value *at the zonal
point* — a single linear rate — the redispatch LP is not nodal's, the final point differs, and a
genuine welfare gap exists. Research §4(b) then proved by a worked example that this reading carries
a systematic bias: the anchored rate understates a concave bid curve's marginal value below the
anchor, so the LP over-curtails demand all the way down (cost 0 vs nodal 1800 while welfare 0 vs
100). The "gap" such a chain reports is partly the bias, and the cost figure inverts.

## Decision

**The redispatch objective uses the true cost and value curves.** The chain provably lands on the
nodal optimum, and this is asserted as an exact-agreement acceptance row (dispatch, served demand,
and welfare to tolerance; LMPs where the nodal LP is not degenerate).

**Consequently the comparison does not measure "how far zonal lands from nodal" — that distance is
zero by construction. It measures what the zonal design costs the operator to repair:** the
redispatch *volume* (Δ⁺/Δ⁻ per generator, restore/curtail per bid load), the redispatch *payment*
(the settlement the repair implies), and the zonal price vector against the nodal LMPs. This is the
European day-ahead-plus-redispatch metric as it is actually used — redispatch cost and volume — not
a synthetic welfare loss.

**The strict paired case moves to the relaxation inequality.** The zonal LP drops every intra-zone
flow row and replaces the corridor's per-branch limits by one bound on the sum, so it is a
relaxation of the nodal LP whenever its caps are at least the network's own limits:
`welfare(zonal) ≥ welfare(nodal)`, strictly when a corridor binds. That inequality, not the gap, is
the wave's falsifiable statement about the zonal approximation — and it is conditional on the caps,
which the fold makes the tests say.

## Consequences

1. **Two independent comparison quantities, not three.** With `A = cost(final) − cost(zonal)` and
   `B = value(zonal) − value(final)`, the result publishes `redispatch_payment = A + B`,
   `generation_cost_gap = −A`, and `welfare_gap = 0`. The audit measured it: on fixed-load case30
   `redispatch_payment + generation_cost_gap = −2.6e-11`; with bids the sum is the curtailment
   compensation `B = +0.94 $/h`. The identity is stated in the field descriptions and asserted by a
   test; "three distinct fields" was an overclaim and is retired.

2. **`redispatch_payment` is a settlement figure and can be negative.** It is non-negative exactly
   when the zonal LP is a relaxation. With caps tighter than the network (the normal NTC regime) or
   with corridors omitted (islanded zones — deleting a corridor is *not* the copper plate), the
   review measured −11.05 $/h and the walk −800 $/h on the manual's own fixture. The docs and the
   relaxation test now name the condition instead of hedging.

3. **The exact-agreement row is blind to the zonal stage.** Because the redispatch LP reaches nodal
   from any start, breaking the zonal LP leaves every final-point assertion green; only the zone
   prices, corridor flows and the oracle parity see the zonal stage. This is a property of D1, not
   a test gap, and it is why the wave keeps AC-2 (hand-derived zonal optimum) and AC-6 (PyPSA
   parity of the zonal stage alone) as separate rows. M7 must not collapse them.

4. **Degenerate LPs need discriminating checks, not descriptive ones.** Rated case300 is
   primal-degenerate at the nodal optimum (7 branches at rating, 5 priced), so two optimal solves
   legitimately pick different active sets and LMPs differ by ~0.32 $/MWh while the primal agrees
   to 1e-8. The wave first substituted a "structural property" (priced ⊆ at-rating) for the LMP
   comparison there, and the audit showed it is complementary slackness — satisfied by any optimal
   solution, carrying no information. The fold replaces it with a comparison on the non-degenerate
   face. The general rule: a check that a sabotage cannot move is not a check.

5. **The shared core now has four callers and one new copy.** ADR-008's decision executed cleanly —
   the extraction/validation preamble is one implementation in `dc_opf.py` with `dc_opf`,
   `multiperiod`, `zonal` and `redispatch` calling it, guard strings living only there (measured:
   55 identical lines → 12, all local-name binding). But diagonal-Hessian assembly is now a third
   verbatim copy (`dc_opf` / `multiperiod` / `zonal`; `redispatch`'s two-column form is genuinely
   different). That is the next seam, and M7 should unify it before adding the agents' columns —
   the same reasoning as ADR-008, one level down.

6. **A result type a reader must construct from is a design surface.** The audit's wave-level
   finding: W8 (docs) had no inbound design decision, and this wave produced exactly the defect one
   would have owned — `MarketZonalResult`'s field names rendered nowhere on the site, because the
   mkdocstrings configuration never rendered pydantic fields for *any* result model and no earlier
   wave had a result type readers had to assemble inputs for. "Where do this type's fields reach the
   reader?" is a design question; M7's design interview asks it.

## Alternatives considered

**Anchored linear rate.** Rejected: a genuine gap, but one that carries a proven over-curtailment
bias, so the cost figure cannot be read as approximation quality and only the welfare figure
could — a comparison result that must be caveated on every read.

**True curves for generators, demand frozen at the zonal quantity.** Rejected: reverses the user's
scope answer for the redispatch stage only, and produces a `market.zonal` whose redispatch ignores
bids that its own zonal stage honoured — the docstring-goes-false shape M5 spent a fold on.

**A blanket LMP tolerance on the degenerate fixture.** Rejected at the time and confirmed by the
audit: ~1 $/MWh would admit real regressions to hide a known degeneracy.

**Unify the Hessian copy inside M6.** Rejected on sequencing, as ADR-008's own preamble unification
was in M5: the wave had passed its audit; an unproven refactor under a discharged matrix is the
failure mode the process exists to prevent.
