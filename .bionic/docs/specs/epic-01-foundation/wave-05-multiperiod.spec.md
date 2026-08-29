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
  orchestrator: opus-5
  implementor: sonnet
  senior-implementor: opus
  researcher: sonnet
  test-runner: sonnet
  auditor: opus
  critic: opus
---

# Wave M5 — multiperiod: 24-period clearing with ramp coupling and storage SoC

M1-M4 each solved a *single instant*. Every solve was independent, and correctness was
checkable one snapshot at a time. M5 introduces **temporal coupling**: a ramp row ties period
`t` to `t-1`, an SoC row ties the whole horizon into one energy budget, and a cyclic row closes
it. The wave's goal is to clear 24 coupled periods **without disturbing the single-period answer
that four waves of oracle parity already pin down** — which is why the degeneracy criterion
(AC-4) carries as much weight here as any new capability.

Research: `record/m5-research.md` (8 sections, every claim carrying its proving command and
output). Scope closure: `record/m5-scope-closure.md`. Design interview: 2026-08-25, frame
ratified, D1/D2/D3 ratified individually, composed design ratified ("Ratified — write the
spec"); the `## Design` section below was written after that ratification, not before it.

## Requirements

- **W1 — Shared row-family core.** `opf/dc_opf.py`'s per-period row construction (nodal balance
  row, PTDF flow rows, generator epigraph / demand hypograph cost blocks) is extracted into
  internal helpers that `dc_opf()` itself calls. `dc_opf()`'s public signature and behaviour are
  unchanged; this is a pure refactor, provable as such.
  provenance: design interview D1 2026-08-25, user "Extract shared core; both call it"

- **W2 — Multiperiod array-level builder.** `opf/multiperiod.py` owns the `T`-loop over that
  shared core plus three new row families: generator ramp coupling (`t-1 -> t`, both directions),
  storage SoC balance with charge/discharge efficiency, and the cyclic end-of-horizon condition
  `SoC_T == soc_initial`.
  provenance: epic spec R7; record/m5-research.md §2.2

- **W3 — Domain model.** `Period` (`load_p_mw: dict[str, float]`, an id-keyed per-load override);
  `Scenario.periods: list[Period] | None`; `Generator.ramp_up_mw` / `ramp_down_mw`
  (`float | None`, MW, `None` = unconstrained). `model.Storage` — schema-present and
  solver-ignored since M1 — becomes solver-read for the first time.
  provenance: design interview D2 2026-08-25, user "Per-load override, no bid fields";
  record/m5-research.md §4.4, §5.3

- **W4 — Arrays.** `NetworkArrays` gains per-storage identity (`storage_ids`, `storage_bus`,
  power/energy/efficiency/initial-SoC arrays), mirroring the per-load identity M4 added in its
  own W3.
  provenance: epic spec R7; ADR-006 array-level seam

- **W5 — Market clearing and settlement.** `market/multiperiod.py:solve_multiperiod(scenario,
  options) -> MarketMultiperiodResult`: per-period dispatch and LMP rows, per-storage
  charge/discharge/SoC rows, per-period settlement, horizon totals. Reuses
  `opf.lmp_decomposition` (M3) and `opf.gen_cost_coeffs` (M4/R2) verbatim. This entry point
  **is** the wave's "scenario runner"; there is no separate batch facility.
  provenance: epic spec R7 + module table row `market.multiperiod`; user 2026-08-25 scope
  answer 3 "Just the multiperiod solve entry point"

- **W6 — Jobs surface.** `SolveRequest` accepts either `network` or `scenario` (exactly one,
  normalized by a validator); every `Runner` becomes `(Scenario, options) -> result`; the five
  existing kinds read `.network` off the scenario. New kind `market.multiperiod`. Every
  already-valid `SolveRequest` JSON stays valid.
  provenance: design interview D3 2026-08-25, user "Widen Runner to Scenario, uniformly";
  `jobs/registry.py` shipped docstring — "Revisit only if a future wave gives Scenario fields a
  bare Network cannot supply"

- **W7 — Fixtures.** `tests/_periods.py` (24-period per-load profile) and `tests/_storage.py`
  (storage sizing), both **derived at test time** from already-committed fixture data, committing
  no new fixture files — the discipline `tests/_bids.py` and `tests/_rated.py` established twice.
  `tests/_rated.py` is reused unchanged to rate a branch, which also discharges M4's carry-over
  A7.
  provenance: record/m5-research.md §8; record/continuation-m4.md carry-over 1

- **W8 — Documentation.** Manual page, `docs/api/` page, architecture-diagram update, one new
  runnable example in CI, snippet-embedded.
  provenance: epic spec R14 standing requirement 2026-08-20

## Not Doing (M5)

Carried verbatim from `record/m5-scope-closure.md`, which recorded the three scoping answers.

- **Per-period offers/bids.** `Period` is shaped so M7 can widen it additively, but M5 implements
  load-profile variation only. (Scope answer 1.)
- **Configurable end-of-horizon SoC.** Cyclic only — no free or fixed-target option, no third
  code path. (Scope answer 2.)
- **A batch scenario runner** over several Scenarios. (Scope answer 3.)
- **Unit commitment.** No binaries, no startup/shutdown costs, no minimum up/down times. Ramp
  limits without commitment is the standard economic-dispatch relaxation and is what R7 asks for.
- **MILP complementarity for storage.** Would change the solver class from LP/QP for a hazard
  research §3.2 proves narrow. A shared power-limit row plus a committed invariant test instead.
- **AC multiperiod.** DC only, as with every market wave.
- **Reserve / ancillary co-optimization.** Not in R7, not in the epic module table.
- **Storage degradation, cycle limits, state-dependent efficiency.** `model.Storage` carries
  constant efficiencies and M5 uses exactly those.
- **A second solver.** ADR-007 binds: multiperiod adds row families to the one array-level
  builder. W1's extraction is what makes that literally true rather than merely intended.
- **Repairing PyPSA integration as a goal.** Research §1 already established PyPSA works
  (assumption A4 was stale, corrected 2026-08-25); no further PyPSA work is an M5 deliverable.

## Prior art (alternatives lens)

- **Within this repo.** M4 is the direct predecessor — it added demand columns and hypograph rows
  to `dc_opf` and proved the result three ways (hand-KKT, settlement identity, oracle parity).
  M3 supplied `lmp_decomposition`, reused verbatim by M4 and reused per period here. M1 put
  `Storage` in the schema and left it solver-ignored; M5 makes it real.
- **The formulation is textbook, and that is the point.** Multi-period economic dispatch with
  ramp limits and storage SoC balance is standard (Wood, Wollenberg & Sheblé; MATPOWER's MOST is
  the multi-period extension of exactly our DC-OPF). The wave's risk is not "is the formulation
  right" but "did we wire it into an existing builder without moving the single-period answer" —
  hence AC-4's weight.
- **Oracles considered.** PyPSA multi-period `optimize` with `StorageUnit` and
  `ramp_limit_up`/`ramp_limit_down` — **chosen**, verified working end-to-end (research §1.2-1.3).
  pandapower — ruled out, no multi-period OPF exists, so M4's `rundcopp`/`sgen` route does not
  extend. MATPOWER MOST — a published reference but Matlab/Octave, unavailable in CI, so usable
  only as hand-transcribed numbers. Hand-derived analytic optima — used regardless, as AC-5.
- **The simultaneous charge/discharge relaxation** is the known hazard in every LP storage
  formulation, well-documented rather than novel. Research §3.2 proved it is not merely an
  optimality curiosity: it constructed a case where forbidding overlap makes the LP *infeasible*,
  which is why M5 bounds it rather than banning it.

## Acceptance criteria

- **AC-1** — the extraction of W1's shared core is behaviour-preserving: the full suite passes
  with **zero test edits**, and `dc_opf`'s existing oracle parity (MATPOWER, pandapower, PyPSA)
  is unchanged.
  provenance: design interview D1 2026-08-25; the interview's own named consequence that the
  extraction must be proven before any multiperiod row exists

- **AC-2** — the multiperiod builder reproduces a hand-derived optimum exactly on a small case
  where a **generator ramp limit binds**, with the binding period identified and its dual
  recovered.
  provenance: epic spec R7; record/m5-research.md §2.2

- **AC-3** — storage SoC dynamics with charge/discharge efficiency: the SoC balance identity
  holds every period, the cyclic condition `SoC_T == soc_initial` is met exactly, and a committed
  invariant test shows `min(charge, discharge) ≈ 0` on every fixture M5 ships.
  provenance: epic spec R7; user 2026-08-25 scope answer 2 "Cyclic"; record/m5-research.md §3.3

- **AC-4** — degeneracy: a `T=1` multiperiod solve reproduces `market.nodal`'s dispatch, duals and
  LMPs **exactly** (not approximately) on a real fixture, and `Scenario.periods=None` leaves
  `market.nodal` byte-identical to its M4 behaviour.
  provenance: epic spec module table row `market.multiperiod` — "1 period ≡ nodal";
  record/m5-research.md §6.2

- **AC-5** — the analytic 2-bus/2-period storage-arbitrage optimum is reproduced to the pinned
  tolerance, matching the closed-form derivation.
  provenance: epic spec module table row `market.multiperiod` — "analytic 2-bus/2-period
  arbitrage"; record/m5-research.md §7.2-7.3

- **AC-6** — `market.multiperiod` matches a PyPSA multi-period oracle (ramp limits and lossy
  storage both active) within a tolerance measured and pinned at implementation, on at least one
  real fixture **with a rated branch**, so congestion binds in some periods and not others.
  provenance: epic spec R9 (oracle discipline); record/m5-research.md §1.3, §8.2

- **AC-7** — `jobs.run`/`run_json` for `market.multiperiod` is pure, JSON round-trips, and never
  raises; every pre-existing `SolveRequest(kind=..., network=...)` still works unchanged across
  all five prior kinds; `jobs.KINDS` lists exactly 6 kinds.
  provenance: design interview D3 2026-08-25; epic spec ADR-004 stateless job surface

- **AC-8** — `mkdocs build --strict` exits 0 with the new manual and API pages; the
  symbol-coverage test passes without modification; the new example exits 0 in CI and is
  snippet-embedded.
  provenance: epic spec R14 standing requirement 2026-08-20

## Design

Composed in the 2026-08-25 design interview and ratified before this file was written. Three
strategic decisions (D1-D3) were each posed with their tension and decided individually; three
tactical defaults (T1-T3) were taken by the orchestrator and surfaced explicitly at ratification.

### 1. Domain model

| Entity | Change | Invariants |
|---|---|---|
| `Period` | **new** — `load_p_mw: dict[str, float]` | every key resolves to a `Load` id in the network, caught by the same nested-validator path `Scenario` already relies on; values ≥ 0 |
| `Scenario` | `periods: list[Period] \| None = None` | `None` ⇒ single-period, `market.nodal` semantics unchanged; if present, non-empty |
| `Generator` | **new** `ramp_up_mw`, `ramp_down_mw`: `float \| None = None` | `None` ⇒ unconstrained between periods; if present, **strictly > 0** — `0` would mean "frozen", the MATPOWER unpopulated-column trap (research §4.2) |
| `Storage` | schema unchanged; **becomes solver-read** | existing field invariants; efficiencies in (0, 1] |
| `MarketMultiperiodResult` | **new** | per-period dispatch/LMP rows, per-storage charge/discharge/SoC rows, per-period settlement, horizon totals; the settlement identity holds **per period** |

### 2. Component boundaries and interfaces

- `opf/dc_opf.py` — owns the extracted shared row-family core (balance row, PTDF flow rows,
  epigraph/hypograph cost blocks). `dc_opf()` keeps its **exact public signature** as the T=1
  caller of that core.
- `opf/multiperiod.py` *(new)* — array-level `T`-loop over the shared core, plus ramp rows, SoC
  rows and the cyclic row. Same array-level altitude as `dc_opf`, per ADR-006's seam.
- `market/multiperiod.py` *(new)* — `solve_multiperiod(scenario, options)`; model-side extraction
  and settlement. Mirrors `market/nodal.py`'s structure exactly.
- `numerics/arrays.py` — per-storage identity arrays, mirroring M4's per-load identity.
- `results/` — `MarketMultiperiodResult` and its row types.
- `jobs/` — widened `SolveRequest`, uniform `Runner`, new `market.multiperiod` kind.

### 3. Ownership table

| Concept | Owner (SSoT) | Rendering surfaces | Agreement test |
|---|---|---|---|
| balance + flow row construction | `opf/dc_opf.py` shared core | `dc_opf` (T=1), `multiperiod_dc_opf` (T-loop) | **AC-4** degenerate-to-nodal |
| LMP decomposition | `opf.lmp_decomposition` (M3) | `market.nodal`, `market.multiperiod` | per-period LMP equals nodal's at T=1 (**AC-4**) |
| generator cost extraction | `opf.gen_cost_coeffs` (M4/R2) | `market/nodal.py`, `market/multiperiod.py` | existing parity suite, unchanged |
| settlement identity | `market/*` | `MarketNodalResult`, `MarketMultiperiodResult` | identity asserted per period (**AC-3**, **AC-6**) |
| ramp / SoC row families | `opf/multiperiod.py` | sole caller `market/multiperiod.py` | **AC-2** (ramp), **AC-5** (arbitrage) |
| storage physical limits | `model.Storage` | LP bounds, result rows, docs | **AC-3** invariant test |

### 4. Rejected alternatives

- **`dc_opf()` grows a period axis** (D1). The most literal reading of ADR-007, and rejected:
  every existing parameter would become period-indexed, rewriting the single-period path four
  waves of parity depend on. M4's extension was *additive* (append column blocks, prior callers
  untouched); a period axis is *multiplicative*. Same word, materially different change.
- **A new builder reproducing `dc_opf`'s idioms** (D1). Lowest risk to proven code, rejected
  because it reproduces balance/flow/epigraph construction wholesale — the duplication M4's own
  Step-6 review raised a FLAG over at roughly one tenth the size.
- **Scalar system-wide load scaling** (D2). Cheapest shape, rejected because every load moves in
  lockstep: the spatial pattern is identical in all 24 periods, so congestion binds in all or
  none and storage arbitrage loses locational content. A fixture structurally unable to reach the
  case it must test — the exact defect M4's critic caught in AC-6.
- **Full `Period` with bid/offer fields now** (D2). Rejected: ships model fields M5's own solver
  never reads, against an M7 whose `Strategy` protocol is still unspecified, so the shape would
  be guessed now and re-cut later.
- **Periods carried in the options model** (D3). Zero change to existing code, rejected because
  periods are scenario *data*, not solve *options*: one scenario would be split across
  `request.network` and `request.options.periods` while `model.Scenario` sat bypassed.
- **Per-kind `Runner` shapes** (D3). Rejected: leaves the protocol with two shapes for M6 and M7
  to each pick a side on.
- **MILP complementarity for storage** (T2). Rejected: changes the solver class from LP/QP for a
  hazard research §3.2 bounds tightly.

### 5. Assumptions

- **A1** — PyPSA is a working multi-period oracle. **Verified, not assumed**: `uv run --no-sync
  pytest -q tests/parity/test_opf_vs_pypsa.py` → 20 passed on five fixtures, 2026-08-25, plus an
  end-to-end multi-period probe with ramp and lossy storage (research §1.2). This **supersedes
  the stale A4** carried in M4's plan and continuation, both corrected 2026-08-25.
- **A2** — simultaneous charge and discharge does not bind on M5's own fixtures. To be **proven
  by a committed invariant test** (AC-3), never assumed. Research §3.2 constructed a case where
  forbidding overlap makes the LP infeasible, so the formulation bounds it (shared
  `charge + discharge ≤ p_max_mw` row) rather than banning it.
- **A3** — no MATPOWER fixture populates ramp data (every ramp column is all-zero on every
  generator of all five fixtures), so `None` is the honest default and ramp limits are derived at
  test time. A `0` default would mean "cannot move at all".
- **A4** — no fixture carries storage; storage is derived at test time (W7).
- **A5** — cyclic end-of-horizon SoC (user scope answer 2). Not configurable this wave.
- **A6** — the shared-core extraction is behaviour-preserving, and the wave's **first slice must
  demonstrate it** (AC-1) before any multiperiod row exists. Two entangled changes would make a
  parity regression unattributable.
- **A7** — carried from M4: worktree junction removal on this machine needs git-bash `rm` before
  `git worktree remove`; PowerShell/cmd `rmdir` is sandbox-blocked on that path.
- **A8** — carried from M4: the evidence gate requires a `## Tasks` heading on an audited
  multi-agent wave plan. M5's plan uses it from the start.

### 6. Tactical defaults (surfaced at ratification, not silent)

- **T1** — `Generator.ramp_up_mw` / `ramp_down_mw`, MW units, `None`-default, mirroring
  `Branch.rating_mva`'s established `float | None` pattern. MW rather than PyPSA's
  per-unit-of-`p_nom` convention, for consistency with every other physical field on `Generator`.
- **T2** — storage as two nonnegative columns (charge, discharge) plus a shared
  `charge + discharge ≤ p_max_mw` row per unit per period, plus the AC-3 invariant test. No MILP.
- **T3** — `tests/_periods.py` and `tests/_storage.py` derive at test time; `tests/_rated.py` is
  reused unchanged to rate a branch for AC-6, discharging M4's carry-over A7. The concrete
  derivation rules (load-curve shape, storage sizing) are pinned at implementation the way M4
  pinned its VOLL figure, not invented here.
