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

# ADR-001: The foundation is a Python package, not a browser engine

Status: accepted (user-ratified 2026-08-20, "Python"). Supersedes gridlab ADR-001
(dual-lane solver port), ADR-002 (per-lane engines + parity) and ADR-004 (free-forever
static baseline).

## Context

gridlab was designed as a static web app whose core loop ran in the browser (TypeScript
Newton-Raphson + HiGHS-WASM) with a Python service as an optional second lane. On
2026-08-20 the user re-scoped the programme: build a fundamental power system and
electricity market *package* first, and build the commercial product on top of it. A
package's home is where its users and its numerical ecosystem live. For power systems
that is Python: scipy sparse, HiGHS via highspy, pandapower and PyPSA as oracles, and a
practitioner audience that reads notebooks.

## Decision

`mambo-power` is a Python ≥ 3.11 package (PyPI `mambo-power`, import `mambo_power`).
There is one engine. The browser-WASM lane, the per-lane parity suite and the
static-site-as-core-loop property are retired; the future commercial layer calls the
package server-side through its job API (ADR-004).

## Consequences

- Serves R1-R13 directly; the "free in both senses" constraint narrows to "open stack,
  no billed service in build/test/docs/release" — zero *run* cost is no longer a
  structural property of the foundation and becomes the commercial layer's concern.
- gridlab's W1 TypeScript work (~2.1k lines) is archived under tag `archive/ts-w1`; its
  knowledge (schema field set, MATPOWER importer semantics, AC-NR + Q-limit formulation,
  fixtures with provenance, SolveRequest/SolveResult shape) carries into M1/M2.
- Rejected: TypeScript extraction of W1 (wrong ecosystem, LP limited to highs-js);
  Rust + WASM + PyO3 (heaviest toolchain, no browser lane left to justify it).
