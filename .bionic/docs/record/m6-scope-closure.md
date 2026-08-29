# M6 / Step 1 — scope closure

Wave M6 (`zonal-redispatch`), triple **build · audited · wave**, integration branch
`epic/01-foundation` (base `4cfd1d7`, M5's merge plus the CI tolerance fix). Recorded 2026-08-27.

Same arrangement as M5's Step 1: the governing-skill hook blocks a wave spec that carries no
`## Design`, so `wave-06-zonal-redispatch.spec.md` is written once, after the Step 2 design
interview. Until then this is the durable record; when the spec lands, these sections move into it.

## Problem statement

**How might we clear a market at zonal granularity — one price per zone, the intra-zone grid
ignored — and then measure exactly what that simplification costs, by redispatching to a
network-feasible point at minimum cost and comparing against the nodal optimum M4 already
computes?**

M6 differs from M5 in kind. M5 added a dimension (time) to one LP. M6 chains **three** solves —
zonal clearing, min-cost redispatch, and the nodal reference — and its real content is the
*relationship* between them: the feasibility repair and the welfare gap. That is why the two epic
invariants (`redispatched flows feasible in pf.dc`, `cost ≥ nodal`) carry the wave: they are the
statements that the chain is coherent.

## Scope answers (user, 2026-08-27, three questions)

1. **Redispatch cost basis: the generator's own cost curve, both directions.** Up-regulation is
   charged at marginal cost; down-regulation is credited at marginal cost. No new model fields.
   Accepted rationale: this is the only basis under which the ordering invariant is a *theorem*
   rather than a measurement — the redispatched point is a feasible point of the very LP the nodal
   solve optimises. Asymmetric up/down offers are M7's strategic surface, not M6's.

2. **Elastic demand participates in BOTH LPs — zonal clearing and redispatch.** The user chose the
   more general model over the recommended "bids clear zonally; redispatch moves generators only".
   Recorded consequences, stated at the time of the decision and not to be relitigated:
   - Redispatch may curtail (or restore) bid loads, so the comparison result is **three-way**:
     generator deltas, load-curtailment deltas, and the welfare gap.
   - The ordering invariant is on **welfare** (bid value served − generation cost), not on
     generation cost alone. Cost-only ordering may fail under demand-side redispatch — the
     researcher is asked to establish whether it does, with an example — and if so the epic's
     literal "cost ≥ nodal" is restated as "welfare ≤ nodal" with the reason recorded in the spec.
   - The redispatch LP needs demand-side Δ columns valued at the bid, or curtailment is free and
     the LP will always shed load rather than move expensive generation.
   - The upside, and why the choice is coherent: `market.nodal` and `market.multiperiod` both
     honour bids. A `market.zonal` that silently froze them would be the docstring-goes-false
     pattern M5 spent a fold on.

3. **Carry-overs absorbed: `Scenario.periods` `max_length` only.** The 12-line `c0` per-period
   test and the combined heterogeneous storage/ramp fixture stay M5 test-quality debt, recorded in
   `continuation-m5.md`, not M6 scope.

## Not Doing (explicit)

- **Asymmetric redispatch offers** — scope answer 1. M7.
- **The `c0` per-period test and the heterogeneous storage/ramp fixture** — scope answer 3.
- **Multiperiod zonal clearing.** M6 is single-period, like M4. Zonal × time is a later composition
  once both exist; the shared builder makes it mechanical when wanted.
- **Storage in the zonal/redispatch LPs.** Single-period means no SoC row; storage stays
  solver-ignored for M6 exactly as it was for M4.
- **Flow-based market coupling / zonal PTDFs** unless research §2 shows it is the *only* faithful
  formulation. The copper-plate-with-transfer-limits family is the standard zonal model and the
  expected default; the design interview picks among the options research presents.
- **A second solver.** ADR-007 binds: both new LPs extend the one array-level `dc_opf` builder.
  ADR-008 binds harder: the duplicated extraction/validation preamble is unified **before** any
  new row family is written. That is M6's first slice, as S1's extraction was M5's.
- **Redispatch as an iterative / heuristic procedure.** One LP, solved once. No pro-rata, no
  merit-order sweeps.
- **AC power flow anywhere in this path.** DC only, as every market wave.
- **New fixture files.** Zones come from the fixtures' own `Bus.zone` / `Bus.area` columns or from
  a test-time derivation rule in the `tests/_rated.py` style — research §1 decides which.

## Prior art / alternatives lens

- **Within this repo.** M4 is the direct predecessor: the welfare LP with hypograph rows is exactly
  what the zonal LP re-uses with the flow rows removed or replaced. M5 supplies two things: the
  extracted row-family helpers (D1) and the lesson that they came without their contract (ADR-008).
  M3 supplies `lmp_decomposition`, which the comparison result reads for the nodal side. `Zone`
  has been in the schema since M1 and every MATPOWER fixture populates `Bus.zone` and `Bus.area`;
  M6 is the wave that makes zones real, as M5 made storage real.
- **Textbook.** Zonal clearing followed by redispatch is the European day-ahead + TSO-redispatch
  model (ENTSO-E; the ACER/CACM framework). The nodal-vs-zonal cost-of-redispatch comparison is a
  standard policy metric. The formulation risk is low; the wiring risk — three chained solves on a
  shared builder — is the wave's content.
- **Oracle alternatives, in preference order.** (i) PyPSA, expressing zonal clearing either as
  "remove intra-zone line limits" or as one bus per zone joined by `Link`s carrying transfer
  limits — research §5 probes both. (ii) The nodal solve itself is a *partial* oracle for the
  redispatch LP: when zonal already equals nodal (no congestion), redispatch must be identically
  zero — a degeneracy test in the AC-4 mould. (iii) Hand-derived optima on a 2-zone / 3-bus network,
  always available and the honest fallback.
- **The M5 lesson applied at scoping.** A sabotage applied to shared fixture data is not a sabotage.
  Whatever oracle AC-6 uses, the zone partition and transfer limits must be handed to the oracle
  independently of the engine under test, or transposing them proves nothing.

## Open questions carried into Step 2

- **Zone partition source** — `Bus.zone` vs `Bus.area`, and on which fixtures the partition is
  non-trivial (research §1).
- **Inter-zonal transfer limits** — unconstrained (copper plate, degenerate to uniform price) vs
  NTC/ATC-style caps derived from the rated cut-set vs flow-based (research §2). This is the
  design's strategic fork, the analogue of M5's `Scenario.periods` shape.
- **Whether cost-only ordering survives demand-side redispatch** — research §4, and it may reshape
  the invariant's wording.
- **Result-type shape** — including M5 carry-over A23's per-branch rows (research §6).
- **Sizing of `Scenario.periods` `max_length`** (research §8).

## Process notes carried from M5, binding from Step 0

- No task-list tool exists in this harness (checked at Step 0); the plan's `## Tasks` ledger is
  the visible progress surface from Step 3.
- Drive the test's own fixture factory, never a hand-assembled reconstruction (M5 made that error
  three times).
- In a worktree with live writers, a file read is a timestamp, not a fact — `git log` the file.
- When one finding is split across two agents, the split needs an owner and a check (the M5 CI
  finding).
- Worktree teardown: junction via git-bash `rm` first; check for listeners on `site/` before
  deleting the directory.

## Design ledger (Step 2, accreting — composed into the spec's `## Design` at close)

- **Frame ratified** (user, 2026-08-27, "Frame holds — walk D1 first"). Decision map D1–D6 as
  presented; D1–D3 strategic, D4–D6 tactical-defaulted and surfaced at ratification. Artifact form:
  `## Design` in the wave spec. Views: module map, builder call graph, result-type sketch.
- **Finding that shaped D1** (research §3a/§4b, 2026-08-27): with bids in both LPs and a
  *true-curve* redispatch objective, the redispatch LP is the nodal welfare LP and the chain
  reproduces nodal exactly; an *anchored-rate* objective avoids the collapse but carries a proven
  systematic over-curtailment bias (worked example: cost 0 vs nodal 1800, welfare 0 vs 100).
- **D1 decided** (user, 2026-08-27): **true cost/value curves** in the redispatch objective.
  Delta: the redispatch LP is the nodal welfare LP restarted from the zonal point, so
  `x_final == x_nodal` is a theorem and becomes an exact-agreement AC in the AC-4 mould. The
  epic's `cost ≥ nodal` is satisfied as `== nodal`. Comparison content moves to: redispatch volume
  (Δp⁺/Δp⁻ per generator, Δd⁻/Δd⁺ per load), redispatch payment (TSO bill), zonal price vs LMP per
  bus. Paired positive case for the invariant family: `welfare(zonal) ≥ welfare(nodal)` because the
  zonal LP is a relaxation, strictly when a tie limit binds. Rejected: anchored rate (proven
  over-curtailment bias, research §4b); freeze-demand (contradicts scope answer 2).
- **D2 decided** (user, 2026-08-27): **b2 — one exchange variable per tied zone-pair**, bounded
  by that corridor's rated cut-set sum; `_balance_row` per zone with the corridor columns as extra
  injection/withdrawal columns; the bound is a plain variable bound, no new row family. One price
  per zone = that zone's balance-row dual. b1 (scalar per zone) is b2's aggregate and ships only as
  a regression check; (a) copper-plate ships only as the single-price degenerate test. Rejected:
  flow-based (c) — needs a generation-shift-key convention the model lacks.
- **D3 decided** (user, 2026-08-27): **case300's real `Zone` entities (4 zones) + case30's AREA
  column promoted to `Zone` at test time** via a new `tests/_zones.py` in the `tests/_rated.py`
  style; corridor transfer caps = sum of `tests/_rated.py` ratings over each zone-pair's cut-set.
  No new fixture files, no new model fields. Rejected: case300-only (not hand-derivable); a
  first-class transfer-capacity entity (invents committed data no fixture supplies).
- **D4–D6 defaulted and surfaced; design ratified** (user, 2026-08-27, "Ratified — write the
  spec"). D4 `MarketZonalResult`: zone-price row, `GenDispatchResult`/`LoadDispatchResult`
  verbatim, `GenRedispatchResult`/`LoadRedispatchResult` nonnegative pairs, `OpfBranchFlowResult`
  verbatim (first market result with branch rows — closes M5 A23), three separated figures
  (`redispatch_payment`, `welfare_gap` == 0 by D1's theorem, `generation_cost_gap` unsigned
  diagnostic). D5 helper `_extract_and_validate -> _ExtractedProblem` lives in `dc_opf.py`;
  Hessian stays per-caller. D6 `Scenario.periods` `max_length = 200`.
