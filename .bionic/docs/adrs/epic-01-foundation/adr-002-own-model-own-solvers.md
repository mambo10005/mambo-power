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

# ADR-002: Own data model and own solvers; pandapower and PyPSA are test oracles only

Status: accepted (user-ratified 2026-08-20, "Own model + own solvers").

## Context

pandapower (BSD) and PyPSA (MIT) already implement power flow and LP-based OPF and are
licence-compatible with a commercial layer. Wrapping them is the fastest path to a
working package. The user's goal, however, is a *fundamental* package whose formulations
the commercial product sells and whose release cadence the user controls.

## Decision

`mambo_power.model` defines its own Network and Scenario (pydantic v2, JSON-native).
`pf`, `opf`, `contingency` and `market` implement their own formulations on numpy,
scipy.sparse and highspy. Runtime dependencies are exactly numpy, scipy, highspy,
pydantic. pandapower and PyPSA are development dependencies used by the parity tier of
the test suite, never imported by package code.

## Consequences

- Serves R2-R9. Every solver carries a published oracle or an analytic invariant (spec
  Design section 4); the parity tier is the contract that keeps "own solvers" honest.
- More work up front (M2-M7 each write a formulation rather than a call), and every
  formulation bug is ours to find — hence the property tier (hypothesis) and the audited
  rigor floor on every wave.
- Interop with both libraries is still a requirement (R11, wave M8) — as file formats,
  not as engines.
- Rejected: own model + delegated solvers (formulations and cadence owned elsewhere);
  thin layer over PyPSA (a plugin, not a foundation).
