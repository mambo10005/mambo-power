---
governing-skill: superpowers:writing-plans
sdlc-step: 3
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

Spec: `specs/epic-01-foundation/wave-09-release-0.1.spec.md` (carries `## Design`).
Scope + design ledger: `record/m9-scope.md`.

## SDLC State

integration-branch: epic/01-foundation
intent: build
rigor: audited
scale: wave
current: 3

- Step 0: prereqs: ok; configured 2026-08-30 via "confirm"; base 9012c43 (1539/4, CI green on
  all 8 matrix jobs)
- Step 1: record/m9-scope.md (D1 narrative notebooks, D2 structural reorg; Not Doing; prior art)
- Step 2: specs/epic-01-foundation/wave-09-release-0.1.spec.md (W1–W8, AC-1..AC-6 with
  provenance, `## Design` ratified 2026-08-31 after S1–S4 walked one per turn, T1–T5 surfaced
  at ratification)
- Step 3: plans/epic-01-foundation/wave-09-release-0.1.plan.md approved by the user 2026-08-31 ("Approved — go"); design + plan + matrix locked together at that one checkpoint; governing design: the spec's `## Design` + epic.spec.md

## Slices

| slice | scope | ACs | complexity | role | depends on |
|---|---|---|---|---|---|
| S1 tutorials | W1: four notebooks (content); `docs/tutorials/index.md` | AC-1 (content half) | complex | senior-implementor | — |
| S2 notebook CI+render | W2 (`nbmake` wired into CI), W3 (`mkdocs-jupyter`, nav entries) | AC-1 (mechanical half) | standard | implementor | S1 (needs real notebooks to wire against) |
| S3 nav+home | W4 (index.md roadmap/status, "where do I go" table) | AC-2 | standard | implementor | S2 (Tutorials nav entry must exist first) |
| S4 getting-started sequencing | W5, the AC-3 drift-guard script | AC-3 | standard | implementor | — |
| S5 semantic-release | W6 (config, changelog restructure into `## Released` + coexistence) | AC-4 | complex | senior-implementor | — |
| S6 publish workflow | W7 (`publish.yml`, OIDC, `pypi` environment) | AC-5 | complex | senior-implementor | — |
| S7 wave docs | W8 (changelog M9 entry, final nav/strict-build check) | AC-6 | standard | implementor | S1–S6 |

S1–S6 own disjoint files and parallelize except the two noted dependencies (S2 needs S1's
notebooks to exist to wire CI against; S3 needs S2's nav entry). S7 is the closing slice.

## Verification Matrix

stack-health: PENDING — taken at Step 5 (baseline 1539 passed / 4 skipped at 9012c43, CI green
on all 8 matrix jobs, verified live)

| AC | tier | status | evidence | auditor |
|---|---|---|---|---|
| AC-1 | T2 | pending | see AC-1 | |
| AC-2 | T1 | pending | see AC-2 | |
| AC-3 | T1 | pending | see AC-3 | |
| AC-4 | T2 | pending | see AC-4 | |
| AC-5 | T2 | pending | see AC-5 | |
| AC-6 | T0 | pending | see AC-6 | |

Tier rationale: AC-1 is T2 — `nbmake` executes real notebooks against the real package in CI
(the fixture-fidelity declaration is "the bundled MATPOWER cases, same as every example"); AC-4 is
T2 — `python-semantic-release`'s own dry-run over hand-authored fixture commits is the real engine
running over declared-fidelity input; AC-5 is T2 — the workflow's trigger condition and OIDC wiring
are inspected against the real GitHub Actions/PyPI trusted-publisher contract, with the actual
pypi.org configuration live-checked (or a named stop-and-wake) rather than assumed; AC-2/AC-3 are
T1 substrate (nav content, a drift-guard script); AC-6 is docs. No T3: nothing here is a live
user-driven surface beyond what the walk covers first.

AC-1:
  criterion: four tutorial notebooks execute cleanly under nbmake (fresh kernel, no exception, exit 0) and render on the built site with outputs visible
  provenance: epic M9 row; user 2026-08-31 "Four, difficulty-tiered"
  fixture-fidelity: the same bundled MATPOWER cases every example script already uses
  tier-run: (pending)
  readback: (pending)
AC-2:
  criterion: Tutorials nav entry between Getting started and Manual; Manual's 12 entries byte-identical in content/order; roadmap reads merged M1-M9; "where do I go" table lists Tutorials
  provenance: user 2026-08-31 "Structural reorg" + "Stay flat"
  tier-run: (pending)
  readback: (pending)
AC-3:
  criterion: getting-started.md says "not on PyPI yet" through Step 8's merge; PyPI install text added only in the same action as the v0.1.0 tag push; a script asserts the tag exists whenever that text is present
  provenance: user 2026-08-31 sequencing requirement (W5)
  tier-run: (pending)
  readback: (pending)
AC-4:
  criterion: semantic-release computes the correct next version from hand-authored conventional-commit fixtures (feat/fix/breaking/chore) via dry-run starting from v0.1.0; its section inserts above the nine wave sections without altering their text
  provenance: epic M9 row; user 2026-08-31 "Coexist"
  fixture-fidelity: hand-authored commit-message fixtures covering every bump type semantic-release must classify, run through its own real dry-run engine
  tier-run: (pending)
  readback: (pending)
AC-5:
  criterion: publish.yml triggers only on a v* tag push, not on every commit; OIDC only, no token/secret anywhere; pypi environment values match the user's actual pypi.org configuration (live-checked or named stop-and-wake)
  provenance: epic M9 row; epic A10; the user's own PyPI configuration
  fixture-fidelity: the real GitHub Actions workflow file and (where checkable) the real pypi.org trusted-publisher state
  tier-run: (pending)
  readback: (pending)
AC-6:
  criterion: M9 changelog entry; mkdocs --strict exit 0, zero unlinked-page/dangling-anchor lines; every new page reachable from the nav
  provenance: epic R14
  tier-run: (pending)
  readback: (pending)

## Tasks

| id | role | unit | deliverable | status |
|---|---|---|---|---|

## Assumptions

Design assumptions A1–A4 live in the spec. Process assumptions, binding from Step 4:

- **A11** — baseline on the clean main checkout before any agent enters the worktree; wave
  worktree `C:/Claude Projects/mambo-power-m9` on `wave/09-release-0.1` from `9012c43`, removed at
  Step 8 with `git worktree remove --force` (never `rm -rf`).
- **A12** — S1–S6 each work in their own worktree on a slice branch, per M8's A17 pattern (four
  agents sharing one git index caused M7's A14–A17 incidents); the orchestrator merges each on
  verification and removes the slice worktree.
- **A13** — every slice commit's `--stat` is checked against the brief's file list before its
  report is believed; agents are stopped on hand-back; briefs say never amend. Given this session's
  own pattern (F8, F11, and the case30 task's clean run), commit early and often is now a standing
  instruction in every brief, and the orchestrator re-verifies independently rather than trusting a
  self-report when a bookkeeping phase goes missing.
- **A14** — the walk is dispatched first at Step 5, driving the actual built docs site (the epic's
  own words: "docs site is drivable → walk: required"), forbidden the spec/plan/reports.
- **A15** — `.bionic/docs/` is committed with each checkpoint commit; `.bionic/tmp/` stays
  ephemeral, wiped at Step 8 after evidence moves to `record/`.
- **A16 (at risk)** — AC-5's live pypi.org check depends on the user having completed the
  trusted-publisher configuration (spec A1); if not yet done when Step 5 reaches it, that row is
  `blocked` with a named stop-and-wake, not silently waived.

## Handoff

Awaiting the Step-3 approval checkpoint. On "go": commit Steps 0–3, create `wave/09-release-0.1` +
worktree, baseline on the clean checkout, dispatch S1 (tutorials) and S4/S5/S6 in parallel (no
dependency on S1); S2 follows S1, S3 follows S2; S7 closes.
