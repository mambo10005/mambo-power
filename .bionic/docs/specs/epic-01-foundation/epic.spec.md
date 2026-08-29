---
governing-skill: agent-skills:spec-driven-development
sdlc-step: 2
intent: build
rigor: audited
scale: epic
canonical_sdlc_version: 13
surface_type: library
language: python
has_ui: false
multi_agent: true
deploy_target: pypi
cleanup_on_finish: true
use_worktree: false
rigor-floor: audited
model_plan:
  orchestrator: fable-5
  implementor: sonnet
  senior-implementor: opus
  researcher: sonnet
  test-runner: sonnet
  auditor: opus
  critic: opus
---

# Epic 01 — mambo-power: fundamental power system & electricity market package

A Python library (PyPI `mambo-power`, import `mambo_power`) that owns its network and
market data model and implements its own solvers — AC/DC power flow, DC optimal power
flow, N-1 contingency analysis, and four market-clearing modes — on numpy, scipy and
HiGHS. It is the foundation a commercial web product (the gridlab repo, evolving into a
SaaS) will later be built on; the foundation itself carries no UI, HTTP, persistence or
auth. Free in both senses: open-source stack with no paid solvers or licences, and
buildable, testable, documented and published entirely on free infrastructure.

## Requirements

- R1 — Network + Scenario data model, JSON-native: pydantic v2 models emit the JSON
  schema; the native file format is the model. Stable string IDs; per-unit consistency;
  exactly one slack bus; connected graph; schema version stamp.
  provenance: user 2026-08-20 "fundamental power system and electricity market model package"
- R2 — AC power flow (Newton-Raphson, sparse, Q-limit enforcement, flat/warm start) and
  DC power flow.
  provenance: gridlab epic R1 (user 2026-08-19), carried forward 2026-08-20 "redesign this idea"
- R3 — DC optimal power flow as a single LP builder over HiGHS returning dispatch and
  duals; piecewise-linear costs.
  provenance: gridlab epic R2, carried forward
- R4 — N-1 contingency analysis: LODF screening then full re-solve of flagged outages;
  optional AC re-solve.
  provenance: gridlab epic R3, carried forward
- R5 — Nodal day-ahead market: clearing via DC-OPF with bids/offers as cost curves; LMP
  decomposed into energy + congestion; congestion rent; settlement.
  provenance: gridlab epic R4, carried forward
- R6 — Zonal market clearing followed by min-cost redispatch; nodal-vs-zonal comparison.
  provenance: gridlab epic R5, carried forward
- R7 — Multi-period market: 24-period horizon with ramp limits and storage state of charge.
  provenance: gridlab epic R6, carried forward
- R8 — Agent-based bidding: a Strategy protocol and a bid → clear → settle → learn loop.
  provenance: gridlab epic R7, carried forward; last market wave (gridlab AC-2 ordering)
- R9 — Own model + own solvers. pandapower and PyPSA are development-only dependencies
  used as parity oracles; the installed package depends on numpy, scipy, highspy, pydantic.
  provenance: user 2026-08-20 "Own model + own solvers"
- R10 — Stateless, fully JSON-serializable job API: `jobs.run(SolveRequest) -> SolveResult`
  for every analysis, safe to call from a notebook, CLI, worker queue or HTTP handler.
  Results stamp engine version, solver, timings and convergence diagnostics.
  provenance: user 2026-08-20 "Web SaaS (gridlab evolves)" — the SaaS calls this surface
- R11 — Interchange formats: MATPOWER .m import, pandapower JSON import/export, PyPSA
  export, PSS/E RAW v33 import, CSV bundle import/export, native JSON round-trip.
  provenance: gridlab epic R13, carried forward
- R12 — Completely free infrastructure and technology: open-source dependencies only;
  GitHub + GitHub Actions + GitHub Pages + PyPI trusted publishing; no billed service in
  build, test, docs or release.
  provenance: user 2026-08-20 "All the implementation should use completely free infrastructure and technology"
- R13 — Published 0.1.0 on PyPI with a docs site (API reference + executable tutorials)
  before any UI/SaaS work resumes.
  provenance: user 2026-08-20 "once it has been implemented, I want to build a commercial package on top of it"
- R14 — Documentation is a per-wave deliverable, not a release-wave one: the repository
  carries a mkdocs-material site (built `--strict` in CI, published to GitHub Pages) with a
  user manual page per module, class descriptions via mkdocstrings (every public class and
  function has a docstring), mermaid architecture and data-model diagrams, and an
  `examples/` directory of runnable scripts/notebooks executed in CI. Every wave from M2
  on ships the docs, diagrams and examples for what it adds; M2 backfills M1.
  provenance: user 2026-08-20 "I want to have a lot of documents in mambo-power github repository including class description, diagrams, examples, etc. For all of the implementation, keep this in mind and do not forget creating detailed manuals, examples, and similar documents."

## Not Doing (this epic)

UI of any kind · HTTP service / FastAPI · persistence, accounts, auth, billing ·
transient/dynamic stability · short-circuit · AC-OPF (AC feasibility is checked by power
flow after DC-OPF) · capacity / ancillary-service markets · real-time telemetry ·
networks beyond what scipy sparse LU handles comfortably (target ≤ 2000 buses, tested
to 300) · GPU or distributed solving · a browser/WASM lane (retired with gridlab ADR-001).

## Prior art (alternatives lens)

pandapower (BSD) and PyPSA (MIT) are the functional references and test oracles;
MATPOWER supplies the canonical fixtures and published solutions; PowerModels.jl the
formulation reference for OPF; AMES / PowerTAC the market-simulation references.
mambo-power differs by owning a single coherent model across physics AND markets with a
serializable job surface designed for a service, rather than a notebook-first toolbox.

## Acceptance criteria (this epic run — steps 0-3 ship documents, not code)

AC-1: epic.spec.md carries this requirement set and a governing design with domain model,
  module boundaries, ownership table, verification table, rejected alternatives, assumptions.
  provenance: user 2026-08-20 "Can you redesign this idea?"
AC-2: epic.plan.md carves dependency-ordered waves M1-M9, each independently shippable,
  LMP-first among markets and agent-based bidding last.
  provenance: user 2026-08-20 "ok" (design section 3)
AC-3: ADRs record: Python-first foundation (supersedes gridlab ADR-001/002/004), own
  model + own solvers, two-repo library-first layering, stateless job surface.
  provenance: user 2026-08-20 "Python" / "Own model + own solvers" / "A"
AC-4: gridlab is re-pointed: `wave/01-substrate-powerflow` tagged `archive/ts-w1`, README
  rewritten as the paused UI/SaaS layer, superseded ADRs marked, fixtures moved.
  provenance: user 2026-08-20 "ok" (design section 3, gridlab's fate)

## Design

### 1. Domain model

| Entity | Contents | Invariants | Owner |
|---|---|---|---|
| Network | buses (id, type, v_base, geo?), branches (lines/transformers: r, x, b, tap, shift, ratings), generators (id, bus, p/q limits, cost curve), loads, storage (power/energy limits, efficiency, SoC bounds), shunts, zones; base_mva; schema_version | connected; exactly one slack; unique IDs; all references resolve; per-unit on base_mva | `model` |
| Scenario | Network ref + market inputs: offers/bids per generator/load, periods (contiguous), agent strategies | references resolve; period grid contiguous; offers monotone non-decreasing | `model` |
| NetworkArrays | numpy/scipy views derived from Network on demand: Ybus, Bbus, PTDF, LODF, index maps | positional ints exist only here | `numerics` |
| SolveRequest / SolveResult | kind ∈ {pf.ac, pf.dc, opf.dc, n1, market.nodal, market.zonal, market.multiperiod, market.agents}; params; result typed per kind with provenance (engine version, solver, timings, diagnostics) | fully JSON-serializable; pure function of inputs | `jobs` + `results` |

### 2. Module boundaries

    mambo_power/
      model/        pydantic v2 Network + Scenario; JSON schema export; validation errors named
      io/           matpower, pandapower_json, pypsa, psse_raw, csv_bundle, native
      numerics/     ybus, bbus, ptdf, lodf, sparse helpers (scipy.sparse)
      pf/           ac_newton, dc
      opf/          dc_opf (single LP builder over highspy, duals returned)
      contingency/  n1
      market/       nodal, zonal, multiperiod, agents (Strategy protocol + loop)
      results/      typed result models, provenance stamp
      jobs/         SolveRequest/SolveResult, run(), registry of kinds

What crosses boundaries: ONLY `model` and `results` types. `market` composes `opf`,
never reimplements it. `io` speaks only `model`. No module holds global state. Every
public function takes and returns pydantic models; numerics are derived views.

### 3. Ownership table

| Concept | Owner (SSoT) | Consumers | Agreement test |
|---|---|---|---|
| Network schema | `model` | io, numerics, jobs, future SaaS | round-trip: every importer/exporter vs schema fixtures; JSON schema snapshot test |
| Power-flow solutions | `pf` | contingency, market (AC check), results | parity: MATPOWER published solutions + pandapower on IEEE 14/30/57/118 |
| DC-OPF formulation | `opf` | market.* | parity: MATPOWER rundcopf + PyPSA optimize on case14/30/118 |
| LMP / rent values | `market.nodal` | zonal comparison, multiperiod, agents | settlement identity: payments − receipts = congestion rent; LMP(slack) = λ |
| Analysis kinds registry | `jobs` | future SaaS capability list | contract test: every kind has a request model, result model, runner |

### 4. Verification table (the contract per solver)

| Module | Formulation | Oracle / invariant |
|---|---|---|
| pf.ac_newton | polar NR, sparse Jacobian, splu; PV→PQ switching; flat/warm start | MATPOWER solutions (1e-4 pu, 1e-2 deg) + pandapower runpp |
| pf.dc | B'θ = P, slack removed; flows via PTDF | dense re-derivation + pandapower rundcpp |
| opf.dc_opf | LP: min Σcost(Pg) s.t. balance, PTDF limits, bounds; PWL costs | MATPOWER rundcopf objective+dispatch; PyPSA optimize |
| contingency.n1 | LODF screen → full DC re-solve; optional AC | brute-force all-branch loop must agree |
| market.nodal | dc_opf with offers as costs; LMP = λ + Σμ·PTDF; rent | settlement identities; price-taker equals OPF |
| market.zonal | zonal LP then min-cost redispatch LP | redispatched flows feasible in pf.dc; cost ≥ nodal |
| market.multiperiod | 24-period LP, ramp, SoC dynamics, efficiency | 1 period ≡ nodal; analytic 2-bus/2-period arbitrage |
| market.agents | Strategy.bid(obs) → offers; bid/clear/settle/learn | price-takers reproduce competitive result; pivotal supplier hits cap |

Test tiers: unit (< 10 s), parity (oracles, ~1 min), property (hypothesis: random
radial/meshed networks satisfy conservation, duality, and the invariants above).

### 5. Free stack & release pipeline

Python ≥ 3.11 · uv (env, lock, build) · runtime deps numpy, scipy, highspy, pydantic ·
dev deps pytest, hypothesis, pandapower, PyPSA, ruff, mypy (strict) · GitHub Actions CI
matrix Linux/macOS/Windows · mkdocs-material on GitHub Pages · PyPI trusted publishing
(OIDC, no tokens) · python-semantic-release (conventional commits → version + changelog)
· MIT licence · public repo `mambo10005/mambo-power`.

### 6. Rejected alternatives

- TypeScript foundation (extract gridlab W1) — rejected by user 2026-08-20: not where the
  domain or its users live; LP limited to highs-js.
- Rust core + WASM + PyO3 — rejected: heaviest toolchain, slowest to first result, no
  browser lane left to justify it.
- Wrap pandapower/PyPSA as the solver layer — rejected by user: the package would not be
  fundamental; formulations and cadence owned elsewhere.
- Monorepo with gridlab — rejected by user (option B): open library and commercial layer
  would share history and licence, forcing a split on the worst possible day.
- Keep gridlab's dual compute lanes — rejected (option C): a browser solver lane with
  nothing to serve.

### 7. Assumptions

1. scipy sparse LU solves a 300-bus AC NR in well under 1 s; 2000-bus in seconds (M2 measures).
2. highspy returns row duals for all constraints needed for LMP decomposition (M3 verifies early; fallback: reconstruct via PTDF from binding-set).
3. pandapower and PyPSA install cleanly on the CI matrix as dev deps (M1 proves in CI skeleton).
4. MATPOWER fixtures and reference solutions from gridlab W1 carry their PROVENANCE/SOURCES verbatim — no re-audit needed.
5. PyPI trusted publishing and GitHub Pages remain free for public repos.
6. The commercial SaaS needs nothing from the foundation beyond R10's job surface plus R1's schema; anything else it needs is a foundation change proposed through this repo's SDLC.

### 8. What happens to gridlab (AC-4)

gridlab stays as the future commercial repo. Branch `wave/01-substrate-powerflow` is tagged
`archive/ts-w1` and frozen; epic-01 docs stay in place with ADR-001 (dual lanes), ADR-002
(per-lane parity) and ADR-004 (static baseline) marked superseded by mambo-power ADR-001;
ADR-003 (local-first) is re-evaluated when the SaaS epic opens. MATPOWER fixtures move
to mambo-power M1. README rewritten: "UI/SaaS layer over mambo-power — paused until
mambo-power 0.1". Later SaaS shape, noted so the foundation serves it and not built now:
FastAPI over `jobs.run` on a free-tier host, Postgres on Supabase/Neon free tier, static
frontend on Cloudflare Pages; anything billable is a stop-and-ask.
