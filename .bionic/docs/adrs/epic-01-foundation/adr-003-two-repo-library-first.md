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

# ADR-003: Two repositories, library first

Status: accepted (user-ratified 2026-08-20, option "A").

## Context

The open foundation and the commercial web product have different licences, different
publics and different lifecycles. Hosting both in one repository (option B) is simpler
today and forces a history/licence split on the day the commercial layer goes private.
Porting inside gridlab while keeping its dual-lane design (option C) preserves the most
existing paper but keeps a browser solver lane with nothing to serve.

## Decision

- `mambo10005/mambo-power` — public, MIT, the foundation. This epic.
- `mambo10005/gridlab` — the future commercial UI/SaaS, paused until mambo-power 0.1.0
  is on PyPI. Its W1 branch is tagged `archive/ts-w1`; README rewritten; gridlab ADRs
  001/002/004 marked superseded; ADR-003 (local-first persistence) re-evaluated when the
  SaaS epic opens; MATPOWER fixtures moved to mambo-power.
- The commercial layer depends on mambo-power as a published package, never as a path
  dependency. Anything it needs from the foundation is proposed through this repo's SDLC.

## Consequences

- Clean licence boundary; gridlab can go private without surgery.
- Two CI pipelines and two release cadences; the foundation's semver is the contract
  between them.
- The free-tier SaaS hosting question (FastAPI host, Postgres, static frontend) is
  deferred to the gridlab SaaS epic; anything billable there is a stop-and-ask.
