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

# Wave M4 — nodal-market: elastic-demand DC-OPF, LMP clearing, settlement

Epic: .bionic/docs/specs/epic-01-foundation/epic.spec.md (R5, R10, R14). Builds on M3
(merged 5fa3285). Gives the package day-ahead nodal market clearing — generators and loads
both bid, the market maximizes welfare, and the result decomposes into LMPs and settlement —
built directly on M3's `opf.dc_opf`/`lmp_decomposition` per ADR-006, the wave that reuse seam
was designed for.

## Requirements

- W1 — Elastic-demand DC-OPF: `opf.dc_opf` gains optional demand-side bid parameters
  (defaulting to `None` = today's fixed-load behavior, so every M2/M3 caller and test is
  untouched), new demand-side LP columns bounded `[0, p_d_max]`, a hypograph row family (the
  concave mirror of the existing convex epigraph encoding), and balance/flow rows extended
  with a `−1`-signed load term; `OpfSolution` gains explicit `demand_dispatch_mw`/
  `demand_bound` fields (no overloading `dispatch_mw`); a new `NonConcaveBidError` guard
  (mirror of `NonConvexCostError`) raised pre-solve on a bid whose marginal value is not
  non-increasing; the existing generator-side quadratic cost gains an explicit convexity
  guard too (`c2 ≥ 0`), closing a gap that predates this wave but surfaced during its
  research.
  provenance: epic R5; record/m4-research.md §1, §2
- W2 — Domain model: `Load.bid: LoadBid | None` (new field, mirrors `Generator.cost:
  GeneratorCost | None` exactly — same discriminated-union shape, opposite
  convexity-direction validation); `Scenario` (new, thin: `network: Network` embedded
  directly, mirroring `SolveRequest`'s self-contained pattern — no id/path reference, no
  precedent for one anywhere in this codebase); no `periods`/agent-strategy fields this wave
  (their eventual shape is genuinely undesigned, unlike `Storage`'s successful M1 stub).
  provenance: epic R5 (Scenario); user 2026-08-24 design interview ("agree" — omit
  periods/strategies); record/m4-research.md §6
- W3 — `NetworkArrays` per-load identity: `load_ids`/`load_bus`/`load_p_min_pu`/
  `load_p_max_pu`, additive, mirroring the existing per-generator arrays exactly;
  `p_load_pu`/`q_load_pu` (the bus aggregate) untouched.
  provenance: record/m4-research.md §2.4
- W4 — `market.nodal` clearing: `solve_nodal(scenario: Scenario, options) ->
  MarketNodalResult` — pulls generator costs and load bids from `scenario.network`, calls
  the extended `dc_opf`, builds a result with id-keyed dispatch (generators and loads),
  per-bus LMP (via `lmp_decomposition`, reused verbatim — ADR-006), and settlement (payments,
  receipts, congestion rent).
  provenance: epic R5; epic Design (market.nodal design line: "dc_opf with offers as costs;
  LMP = λ + Σμ·PTDF; rent"); ADR-006
- W5 — Jobs API: `market.nodal` kind added to `jobs.KINDS`, reusing `INFEASIBLE_LP`/
  `UNBOUNDED_LP` as-is (same failure shape as `opf.dc`, no new code needed); the
  non-Optimal-status-to-structured-failure translation `opf.dc`'s runner already does is
  factored into a small shared helper both kinds call, rather than duplicated.
  provenance: epic R10; record/m4-research.md §7
- W6 — Oracle & fixtures: pandapower's `sgen` (sign-flipped, negative-bound generator)
  framing adopted as the permanent oracle-construction convention for elastic demand
  (proven exact against a hand KKT solve); a new `tests/_bids.py` derives each load's bid
  curve at test time (mirroring `tests/_rated.py`'s established discipline), anchored to
  the load's own already-committed `p_mw`, linear marginal value from a VOLL down to the
  fixture's own generation-fleet max marginal cost — the exact VOLL figure and curve-shape
  parameters pinned at implementation, not fixed here; a small hand-built case (not a new
  `.m` fixture) covers the deliberately-non-concave guard test. PyPSA inherited as M3's
  still-open carry-over (blocked by M3's own unresolved infeasibility issue) — not attempted.
  provenance: user 2026-08-24 design interview (tactical defaults); record/m4-research.md
  §3, §5
- W7 — Documentation: a manual page for nodal-market clearing added to the existing mkdocs
  site; API reference entries for `market` (covered automatically by the existing
  symbol-coverage test); one new runnable example under `examples/`, CI-executed and
  snippet-embedded.
  provenance: epic R14

## Not Doing (M4)

Zonal clearing, min-cost redispatch (M6) · multi-period / ramp / storage state-of-charge
market participation (M5) — `Storage` stays schema-present, unread by market clearing ·
agent-based bidding, Strategy protocol (M7) · AC-OPF as an optimization (still only a
post-dispatch feasibility check, per M3) · price caps, market-power mitigation, capacity or
ancillary-service markets (epic Not Doing) · root-causing pandapower's `load`-row quadratic
non-convergence bug (the `sgen` framing is economically identical and proven exact) · fixing
M3's still-open PyPSA infeasibility (inherited, not compounded) · generator ramp limits ·
real-time telemetry.

## Prior art (alternatives lens)

Standard nodal-market welfare-maximization LP (textbook, same "single system-wide balance +
PTDF flow-limit rows" family as M3's own DC-OPF prior art — PowerModels.jl / MATPOWER, per
the epic's own prior-art list); pandapower's `sgen`-framed elastic-demand OPF (the oracle
trick found and proven exact this wave); M3's `opf.dc_opf`/`lmp_decomposition` (direct reuse,
not reimplementation, per ADR-006).

## Acceptance criteria

AC-1: On a hand-built 2-bus network with a known welfare optimum (one binding flow limit, a
  2-segment concave demand bid) matching record/m4-research.md §4.1's KKT-verified example
  (`p1=20, p2=0, d=20`, `λ=10`, `μ_flow=−35`, `LMP(bus1)=10`, `LMP(bus2)=45`), the extended
  `dc_opf` reproduces dispatch, duals, and LMPs exactly.
  provenance: W1; record/m4-research.md §4.1
AC-2: A hand-built non-concave bid raises `NonConcaveBidError` before any solve is attempted;
  a hand-built non-convex (`c2 < 0`) generator cost is rejected by the new generator-side
  convexity guard, closing the asymmetry the research found.
  provenance: W1; record/m4-research.md §1.2
AC-3: `Load.bid`/`Scenario`/the new `NetworkArrays` per-load identity round-trip through JSON
  and construction; a `Scenario` embeds a `Network` directly (self-contained, matching
  `SolveRequest`'s pattern) and a dangling reference inside it is caught the same way
  `Network`'s own validation catches one.
  provenance: W2, W3
AC-4: On real multi-bus fixtures using `tests/_bids.py`'s derived bid curves, `market.nodal`'s
  settlement identity holds exactly: `Σ_d LMP(bus_d)·p_d − Σ_g LMP(bus_g)·p_g = −Σ_k
  μ_k·flow_k` (congestion rent), matching record/m4-research.md §4.1's algebraic derivation.
  provenance: W4; record/m4-research.md §4.1
AC-5: On a fixture where every load's bid value exceeds every achievable price at every
  quantity up to its own fixed historical demand (the precise condition record/
  m4-research.md §4.2 states), `market.nodal`'s dispatch, duals, and LMPs are identical to
  plain `opf.dc_opf` called with that same demand as fixed load — the price-taker reduction,
  already oracle-proved via M3's own parity.
  provenance: W4; record/m4-research.md §4.2
AC-6: `market.nodal`'s dispatch and price match pandapower's `sgen`-framed elastic-demand
  `rundcopp` (the adopted oracle convention) within a tolerance measured and pinned at
  implementation, on at least one real multi-bus fixture with derived bids.
  provenance: W6; record/m4-research.md §3.1
AC-7: `jobs.run`/`jobs.run_json` with kind `market.nodal` round-trips through JSON, is pure,
  never raises across the boundary; an infeasible welfare LP (a hand-built case with
  contradictory bounds) yields `INFEASIBLE_LP`, not `INTERNAL`; `jobs.KINDS` lists exactly
  `pf.ac`, `pf.dc`, `opf.dc`, `n1`, `market.nodal` with importable models and a callable
  runner for each.
  provenance: W5
AC-8: `uv run mkdocs build --strict` exits 0 with the new nodal-market manual page and
  `market` API reference entry present; the symbol-coverage test passes for `market` without
  modification; the new example exits 0 in the CI `examples` job and is snippet-embedded.
  provenance: W7

## Design

Governing design: epic spec §Design; M3's wave spec §Design and ADR-006 for the reuse seam
this wave builds directly on. M4-local decisions (ratified 2026-08-24):

1. **Elastic demand inside `dc_opf` (W1).** `opf/dc_opf.py:dc_opf` gains optional
   `demand_bid_coeffs`/`demand_pwl_bids` parameters (default `None`, preserving every M2/M3
   caller's exact current behavior). New LP columns per bid-load, bounded `[0, p_d_max]`
   (no sign flip — Option B from the design interview, chosen over the cheaper-but-riskier
   pseudo-generator reuse for its cleaner semantics and absence of double-counting risk).
   Hypograph rows (`val ≤ slope_i·p + intercept_i` per segment) mirror the existing convex
   epigraph construction exactly, sign-flipped. Balance/flow rows extended with a
   `−1`-signed load term. `OpfSolution.demand_dispatch_mw`/`demand_bound` are new, explicit
   fields — never overloading the generator-side ones. `NonConcaveBidError` lives beside
   `NonConvexCostError` in the same module; the generator-side `c2 ≥ 0` check added at the
   same time, in the same commit, to avoid shipping an asymmetric guard.
2. **`Load.bid` on the entity, not a Scenario-level collection (W2).** Corrects a real drift
   the research found between the epic's pre-M1 domain-model wording (`Scenario` "owning"
   offers/bids) and what M1 actually shipped (`Generator.cost` directly on `Network`, no
   `Scenario` in the loop). `Load.bid: LoadBid | None` mirrors `Generator.cost` field-for-field;
   `Network` stays the single owner of all cost/bid data, matching the "single source of
   truth" discipline already applied everywhere else in this codebase.
3. **`Scenario` (W2).** `network: Network` embedded directly, mirroring `SolveRequest`'s
   self-contained pattern (no id/path cross-reference mechanism exists anywhere in this
   codebase, and R10's stateless-job goal argues against inventing one now). No
   `periods`/agent-strategy fields — genuinely undesigned by M5/M7 as of this wave, unlike
   `Storage`'s successful M1 stub, which had a full spec before it shipped.
4. **`NetworkArrays` per-load identity (W3).** `load_ids`/`load_bus`/`load_p_min_pu`/
   `load_p_max_pu` mirror the existing `gen_*` arrays' construction exactly (additive;
   `p_load_pu`/`q_load_pu` untouched, so M1-M3 callers see no change).
5. **`market/nodal.py` (W4).** `solve_nodal(scenario, options) -> MarketNodalResult` is the
   Network-facing (well, Scenario-facing) entry point — extracts costs/bids, calls the
   extended `dc_opf`, calls `lmp_decomposition` verbatim (ADR-006's reuse, now exercised by
   its intended consumer), builds settlement fields from the proven identity.
6. **Jobs (W5).** `market.nodal` `KindSpec` follows the established mechanism; `run.py`'s
   "non-Optimal status → structured failure" translation (today duplicated nowhere yet
   because only `opf.dc` uses it, but about to be duplicated a second time) is factored into
   one shared helper both `opf.dc` and `market.nodal` call.
7. **Oracle & fixtures (W6).** pandapower's `sgen`-framed elastic demand is the permanent,
   documented oracle-construction convention (alongside the existing `BASE_KV`/
   `trafo_model="pi"` conventions) — not the more "natural"-looking `load`-row framing,
   which reproducibly fails to converge in `rundcopp` for a quadratic bid for reasons not
   worth this wave's time to root-cause. `tests/_bids.py` derives bid curves at test time,
   mirroring `tests/_rated.py`'s discipline exactly — no new committed fixture data except
   one small hand-built case for the non-concave guard test.
8. **Docs (W7).** A new manual page (`docs/manual/market.md`) for nodal-market clearing under
   the existing `docs/manual/`; `docs/api/market.md` following the mkdocstrings pattern the M2
   R1 fold's coverage test already enforces generically; the design/architecture diagram
   updated to show `market.nodal`; one new `examples/09_nodal_market.py`, CI-executed and
   snippet-embedded.

Ownership additions: elastic-demand LP structure → `opf.dc_opf` (consumers: `market.nodal`
now, any future wave needing demand-side clearing later) — agreement test: AC-1 (hand KKT
case); LMP/settlement math → `opf.dc_opf.lmp_decomposition`, reused not reimplemented
(consumers: `OpfDcResult.lmp` since M3, `MarketNodalResult`'s settlement fields now) —
agreement test: AC-4 (settlement identity); demand bid data → `Load.bid` on `Network`
(consumers: `market.nodal` via `Scenario.network`) — agreement test: AC-3.

Rejected: the pseudo-generator reuse trick (Option A) — real double-counting risk, semantic
overload of `dispatch_mw`, no natural home for a bid-side convexity check without bypassing
or generalizing `NonConvexCostError`; a `Scenario`-level `offers`/`bids` collection separate
from `Load.bid`/`Generator.cost` — would duplicate or shadow the single source of truth an
entity-level field already gives; an id/path cross-reference from `Scenario` to a
separately-stored `Network` — no precedent, no resolution mechanism exists; stubbing
`periods`/agent-strategy fields now — genuinely undesigned, unlike `Storage`'s successful
stub; root-causing pandapower's `load`-row bug — no functional payoff, `sgen` already proven
exact; attempting to fix M3's PyPSA infeasibility inside M4 — a different wave's carry-over,
not this wave's to compound.

Assumptions: (a) the VOLL figure and bid-curve anchor rule are pinned during implementation
(the fixture-strategy slice), not fixed in this spec — must produce a genuinely concave,
non-trivial bid curve that exercises the hypograph path meaningfully, not a degenerate
linear step; (b) pandapower's `load`-row quadratic-cost non-convergence (record/
m4-research.md §3.1) is a real, reproduced bug worth naming precisely in the implementing
test's own documentation, even though this wave routes around it via `sgen`, so a future
pandapower upgrade or a curious reader isn't left to rediscover it; (c) the generator-side
`c2 ≥ 0` convexity guard (item 1 above) is a pre-existing gap this wave closes as a
byproduct, not a new requirement of its own — log it as such rather than implying M3 was
incomplete without it.
