---
governing-skill: agent-skills:documentation-and-adrs
sdlc-step: 3
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
model_plan: see epic.plan.md
---

# ADR-004: One stateless, JSON-serializable job surface is the contract the SaaS consumes

Status: accepted (user-ratified 2026-08-20, "Web SaaS (gridlab evolves)").

## Context

The commercial layer will be a hosted web application calling the foundation server-side:
behind an HTTP handler, from a worker queue, possibly across processes. A notebook-first
API (mutable network objects, results stored on the object) does not survive that
boundary; neither does global solver state.

## Decision

`mambo_power.jobs` exposes `run(SolveRequest) -> SolveResult` for every analysis kind
(`pf.ac`, `pf.dc`, `opf.dc`, `n1`, `market.nodal`, `market.zonal`, `market.multiperiod`,
`market.agents`). Requests and results are pydantic models, fully JSON-serializable; `run`
is a pure function of its input; results stamp engine version, solver, timings and
convergence diagnostics. The kinds registry is the SaaS's capability list. Module-level
functions in `pf`, `opf`, `market` remain for notebook use and are what `jobs` calls.

## Consequences

- Serves R10 (and R1's JSON-native model is what makes it possible).
- The same call works in a notebook, a CLI, a worker, and a FastAPI handler — the SaaS
  adds transport and persistence, never semantics.
- Long-running kinds (agents, multiperiod) take a `cancel`/`progress` hook in the request
  rather than holding state; M5/M7 define it.
- The shape is the port of gridlab W1's SolveRequest/SolveResult contract, carried over
  by design.
