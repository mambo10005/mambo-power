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
  orchestrator: fable-5
  implementor: sonnet
  senior-implementor: opus
  researcher: sonnet
  test-runner: sonnet
  auditor: opus
  critic: opus
---

# Wave M6 — zonal-redispatch: zonal clearing, min-cost redispatch, nodal-vs-zonal comparison

Integration branch `epic/01-foundation`, base `4cfd1d7` (M5's merge + the CI tolerance fix).
Step 1 record: `record/m6-scope-closure.md`. Research: `record/m6-research.md`.

**How might we** clear a market at zonal granularity — one price per zone, the intra-zone grid
ignored — and then measure exactly what that simplification costs, by redispatching to a
network-feasible point at minimum cost and comparing against the nodal optimum M4 computes?

M6 chains **three** solves on the one array-level builder — zonal clearing, redispatch, and the
nodal reference — and its content is their *relationship*. Under design decision D1 that
relationship is a theorem: the redispatched point **equals** the nodal optimum, so the comparison
measures what the zonal design costs the operator (redispatch volume and payment), not how far a
heuristic lands from nodal.

## Requirements

- **W1 — ADR-008 first.** The extraction/validation preamble duplicated between `dc_opf.py` and
  `multiperiod.py` (55 identical lines of 68/71, research §7) is unified into one shared helper
  **before** any new row family is written. Behaviour-preserving: M5's suite green unmodified.
- **W2 — Zonal clearing LP** (`opf.zonal`): per-zone balance rows, inter-zonal exchange as one
  bounded variable per tied zone-pair (D2, b2), no intra-zone flow rows; generator epigraph and
  demand hypograph rows reused. One price per zone as that zone's balance-row dual.
- **W3 — Min-cost redispatch LP** (`opf.redispatch`): from the zonal point `(p0, d0)`, Δ⁺/Δ⁻
  columns per generator and Δd⁺/Δd⁻ per bid load, bounds shifted by the zonal point, **true
  cost/value curves** in the objective (D1), real PTDF flow rows and generator/load bounds.
- **W4 — `market.solve_zonal`** orchestrates zonal → redispatch → `solve_nodal` reference and
  composes a `MarketZonalResult` (D4): zone prices, zonal dispatch, redispatch deltas both sides,
  **per-branch flows and duals** (M5 carry-over A23), and three separated figures —
  `redispatch_payment`, `welfare_gap`, `generation_cost_gap`.
- **W5 — Invariants.** (a) redispatched flows feasible under every branch rating in `pf.dc`;
  (b) the redispatched point equals the nodal optimum (D1's theorem — the epic's `cost ≥ nodal`
  met as `== nodal`); (c) `welfare(zonal) ≥ welfare(nodal)` because the zonal LP is a relaxation,
  strictly when a corridor binds.
- **W6 — Jobs.** Kind `market.zonal`, `KINDS` exactly 7, JSON round-trip, never raises, all six
  prior kinds unchanged. Plus M5 carry-over: `Scenario.periods` gains `max_length = 200` (D6).
- **W7 — Fixtures and oracle.** `tests/_zones.py` promotes case30's AREA column to `Zone`
  entities and derives corridor caps from `tests/_rated.py` ratings (D3); case300's four real
  zones used directly. PyPSA multi-zone parity with the partition and caps handed to the oracle
  independently of the engine.
- **W8 — Docs** (epic R14 standing requirement): manual page, API pages, architecture edges,
  runnable example snippet-embedded, `mkdocs --strict` clean, coverage test unmodified.

## Not Doing

- Asymmetric / administrative redispatch offers (scope answer 1; M7).
- The `c0` per-period test and the combined heterogeneous storage/ramp fixture (scope answer 3;
  M5 test-quality debt in `continuation-m5.md`).
- Multiperiod zonal clearing; storage in the zonal/redispatch LPs (single-period, like M4).
- Flow-based coupling / zonal PTDFs (rejected at D2: needs a GSK convention the model lacks).
- A first-class transfer-capacity entity (rejected at D3: invents committed data).
- An anchored-rate redispatch objective (rejected at D1: proven over-curtailment bias).
- A second solver (ADR-007) or a new row family before W1 lands (ADR-008).
- AC power flow anywhere in this path; new fixture files.

## Prior art

European day-ahead + TSO redispatch (ENTSO-E / CACM); nodal-vs-zonal cost-of-redispatch is a
standard policy metric. In-repo: M4's welfare LP (the zonal LP is that LP with flow rows replaced
by corridor bounds); M5's extracted row helpers and ADR-008's finding that they came without their
contract; M3's `lmp_decomposition` for the nodal side; `Zone` schema-present since M1.

## Acceptance criteria

- **AC-1** — W1's unification is behaviour-preserving: M5's complete suite passes with **zero
  test edits** on a tree differing from `4cfd1d7` only in the unified files; `multiperiod_dc_opf`'s
  `getNumRow` tripwire still passes; no `dc_opf`-private name imported by `multiperiod.py` changes
  signature.
  provenance: ADR-008 decision "M6 unifies the extraction-and-validation preamble before adding
  zonal redispatch's row families"; record/m6-research.md §7

- **AC-2** — the zonal LP reproduces a hand-derived optimum on a 2-zone/3-bus network where the
  corridor binds: the two zone prices differ by the hand-derived amount and the corridor variable
  sits at its cap; and on the same network with the cap removed (copper plate) every zone price
  equals the nodal λ exactly.
  provenance: design interview D2 2026-08-27, user "b2: one variable per tied zone-pair";
  record/m6-research.md §2(a)(b)

- **AC-3** — the redispatched dispatch is feasible in `pf.dc` under every branch rating, on every
  multi-zone fixture, to a pinned tolerance; paired negative: the **zonal** dispatch itself
  violates ≥1 rating on the strict fixture (research §5 measured 7 of 41 case30 branches binding
  the zonal step), so the feasibility readback is not vacuous.
  provenance: epic spec module table "redispatched flows feasible in pf.dc"; record/m6-research.md §4(c)

- **AC-4** — the redispatched point equals the nodal optimum: dispatch, served demand and LMPs
  agree with `market.solve_nodal` to a pinned tolerance on case30 (promoted zones) and case300
  (real zones), with elastic bids in play; `welfare_gap` ≈ 0. Paired negative: an anchored-rate
  objective substituted in a scratch tree breaks the agreement.
  provenance: design interview D1 2026-08-27, user "True cost/value curves"; epic spec module
  table "cost ≥ nodal" (met as equality); record/m6-research.md §4(a)

- **AC-5** — `welfare(zonal) ≥ welfare(nodal)` on every multi-zone fixture, **strictly** on the
  rated case30 fixture where a corridor binds (paired positive), with nonzero redispatch volume
  there; `redispatch_payment`, `welfare_gap` and `generation_cost_gap` are three distinct fields;
  and the settlement identity's flow-dual side is computable **from the result object alone**
  via its `OpfBranchFlowResult` rows (M5 A23 closed).
  provenance: record/m6-research.md §4(a) relaxation argument, §6 result shape; continuation-m5.md
  carry-over 2 (A23)

- **AC-6** — `market.zonal`'s zonal stage matches a PyPSA oracle built as one bus per zone joined
  by `Link`s carrying the corridor caps, within tolerances measured and pinned at implementation,
  on rated case30; partition and caps are handed to PyPSA independently of the engine, and an
  engine-side sabotage (corridor cap sign / zone assignment) goes red against the fixed oracle.
  provenance: epic spec R9 oracle parity; record/m6-research.md §5 (verdict YES, probed);
  continuation-m5.md lesson "a sabotage applied to shared fixture data is not a sabotage"

- **AC-7** — `jobs.run`/`run_json` for `market.zonal` is pure, JSON round-trips and never raises;
  all six prior kinds accept their existing request forms unchanged; `jobs.KINDS` lists exactly 7;
  `Scenario(periods=[...201 entries...])` is rejected and 200 accepted.
  provenance: epic spec module table SolveRequest kinds; design interview D6 2026-08-27
  (max_length = 200); ADR-004

- **AC-8** — `mkdocs build --strict` exits 0 with the new manual + API pages; the symbol-coverage
  test passes unmodified; the new example exits 0 in CI and is snippet-embedded; the changelog
  carries an M6 entry.
  provenance: epic spec R14 standing requirement 2026-08-20; continuation-m5.md lesson on
  hand-maintained docs

## Design

Ratified 2026-08-27 in the Step 2 interview (ledger: `record/m6-scope-closure.md`).

### Domain model

No new model fields. `Zone` (M1, schema-present) becomes solver-read. Test-time derivations,
`tests/_zones.py`: `promote_areas_to_zones(net)` turns case30's free-form AREA labels into `Zone`
entities on a deep copy; `corridors(net)` returns `{(z1, z2): cap_mw}` for every zone-pair with
≥1 crossing branch, `cap = Σ rating_mva` over that cut-set using `tests/_rated.py` unmodified.
Invariants: every bus in exactly one zone; a corridor exists iff a branch crosses it; caps ≥ 0.

### Component boundaries and interfaces

- `opf.dc_opf` — gains `_extract_and_validate(cost_coeffs, pwl_costs, demand_bid_coeffs,
  demand_pwl_bids, n_gen, n_load) -> _ExtractedProblem` (frozen dataclass). Both existing
  callers and both new ones import it beside the four row helpers. Hessian assembly stays
  per-caller (different column counts). Serves W1.
- `opf.zonal.zonal_dc_opf(arr, zone_of_bus, corridors, cost_coeffs, ...)` — per-zone
  `_balance_row` with the corridor columns as injection/withdrawal; corridor bounds are variable
  bounds; `_epigraph_rows`/`_hypograph_rows` reused; **no** `_flow_limit_rows`. Serves W2.
- `opf.redispatch.redispatch_dc_opf(arr, p0, d0, cost_coeffs, ...)` — Δ columns both sides,
  bounds shifted by `(p0, d0)`, true curves via `_extract_and_validate`, `_balance_row` and
  `_flow_limit_rows` reused with the zonal point folded into the fixed RHS. Serves W3.
- `market.zonal.solve_zonal(scenario, options)` — the chain; `results.zonal.MarketZonalResult`.
  Serves W4/W5.
- `jobs` — one more `KINDS` entry; `Runner` signature unchanged. Serves W6.

### Ownership table

| concept | owner (SSoT) | rendered at | agreement test |
|---|---|---|---|
| extraction + convexity guards | `dc_opf._extract_and_validate` | `dc_opf`, `multiperiod`, `zonal`, `redispatch` | AC-1 overlay-tree suite, zero test edits |
| zone price | zonal balance-row dual | `MarketZonalResult.zones`, manual | AC-2 copper-plate degenerate: all equal nodal λ |
| final dispatch == nodal | D1 theorem | `welfare_gap`, redispatch rows | AC-4 `assert_allclose` vs `solve_nodal` |
| corridor caps | `tests/_zones.py` | zonal variable bounds, PyPSA `Link` p_nom | AC-6 caps handed to oracle independently |
| jobs registry | `jobs.KINDS` | `docs/manual/jobs.md` | `test_docs_registry_listing.py` |

### Rejected alternatives

Anchored-rate objective (research §4b proves systematic over-curtailment: cost 0 < nodal 1800
while welfare 0 < 100); freeze demand in redispatch (contradicts scope answer 2); b1 scalar
net-export per zone (cannot distinguish A→B from A→C on either candidate fixture); flow-based
zonal PTDFs (no GSK convention); copper-plate as the model (provably one price); a
transfer-capacity entity; a second solver.

### Assumptions

- A1: PyPSA expresses b2 as one bus per zone + `Link`s with `p_nom = cap`. Research §5 probed
  "intra-zone limits removed", not `Link`s — AC-6 stays at-risk until S6 proves the `Link` form.
- A2: case30's three AREA groups yield ≥1 corridor per zone pair (research §5 saw 7 tie lines).
- A3: under D1, AC-4 agreement is to tolerance, never bitwise (M5's CI macOS finding).
- A4: no multi-zone fixture has a zone with zero generation; if one does, the corridor must carry
  that zone's whole load and AC-2's cap derivation must not make it infeasible.
- A5: the redispatch objective's true-curve form means `redispatch_payment` is
  `cost(final) − cost(zonal)` plus curtailment compensation at bid value — a settlement figure,
  and `welfare_gap` is the exactness row, not a measurement.
