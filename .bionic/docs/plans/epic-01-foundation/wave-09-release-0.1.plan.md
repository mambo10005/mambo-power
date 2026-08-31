---
governing-skill: superpowers:writing-plans
sdlc-step: 1
intent: build
rigor: audited
scale: wave
canonical_sdlc_version: 13
surface_type: library + docs site
language: python
has_ui: false
multi_agent: true
deploy_target: pypi
cleanup_on_finish: true
use_worktree: true
rigor-floor: audited
walk: required
design-interview: true
model_plan:
  orchestrator: fable-5
  implementor: sonnet
  senior-implementor: opus
  researcher: sonnet
  auditor: opus
  critic: opus
---

# Wave M9 — release-0.1 — plan

Scope: `record/m9-scope.md`. Spec pending Step 2.

## SDLC State

integration-branch: epic/01-foundation
intent: build
rigor: audited
scale: wave
current: 1

- Step 0: prereqs: ok; configured 2026-08-30 via "confirm"; model_plan=fable-5/sonnet/opus;
  integration-branch=epic/01-foundation; base 9012c43 (1539 passed / 4 skipped; CI green on all
  8 matrix jobs including both ubuntu Python versions — verified live, not just locally, after
  the case30 degeneracy task)
- Step 1: record/m9-scope.md — D1 (new narrative notebooks) and D2 (structural nav reorg) ruled
  by the user 2026-08-31; Not Doing; prior art; five questions carried to Step 2

## Handoff

Resume at Step 2's design interview: frame (notebook-driven tutorials as a first-class docs layer,
alongside the reorg), walk S1 (tutorial count/topics), S2 (CI execution tool + rendering), S3
(nav shape), S4 (changelog coexistence with semantic-release), ratify, write the spec in one Write.
Three external actions remain the user's regardless of design outcome: pushing (done, `9012c43`
CI-verified), PyPI trusted-publisher configuration (guide already given), and cutting the `v0.1.0`
tag at Step 9.
