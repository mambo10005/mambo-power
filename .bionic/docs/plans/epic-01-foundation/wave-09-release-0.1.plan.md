---
governing-skill: superpowers:writing-plans
sdlc-step: 4
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
current: 4

- Step 0: prereqs: ok; configured 2026-08-30 via "confirm"; base 9012c43 (1539/4, CI green on
  all 8 matrix jobs)
- Step 1: record/m9-scope.md (D1 narrative notebooks, D2 structural reorg; Not Doing; prior art)
- Step 2: specs/epic-01-foundation/wave-09-release-0.1.spec.md (W1–W8, AC-1..AC-6 with
  provenance, `## Design` ratified 2026-08-31 after S1–S4 walked one per turn, T1–T5 surfaced
  at ratification)
- Step 3: plans/epic-01-foundation/wave-09-release-0.1.plan.md approved by the user 2026-08-31 ("Approved — go"); design + plan + matrix locked together at that one checkpoint; governing design: the spec's `## Design` + epic.spec.md
- Step 4: worktree C:/Claude Projects/mambo-power-m9 on wave/09-release-0.1 from d18aaea, slices
  in their own worktrees per A12. **Baseline on the clean main checkout at d18aaea, before any
  agent entered a worktree: 1539 passed / 4 skipped in 1949.56s** (scratchpad
  m9-baseline-d18aaea.log, 2026-08-31 03:13Z).

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
| m9-s1-tutorials | senior-implementor | S1: four narrative tutorial notebooks + intro page (W1). Own worktree `mambo-power-m9-s1` on `wave/09-release-0.1-s1` | record/m9-s1-report.md + 5 commits | **done** (`8af9df5` index, `7d2b2cf`/`2bb8cd7`/`eb84e5c`/`bceb367` the four notebooks; merged `f5847ec`). Went beyond the brief: fully executed all four via `jupyter nbconvert --to notebook --execute --inplace` (jupyter/nbconvert/ipykernel installed transiently, never added to pyproject.toml/uv.lock — S2's job), all exit 0, baked-in outputs match standalone-script runs bit for bit; full execution verification NOT deferred to S2 as the brief allowed. `git diff --stat -- . ':!docs/tutorials'` empty — nothing touched outside its own directory |
| m9-s4-getting-started | implementor | S4: PyPI-install-text-vs-tag drift guard (W5, AC-3). Own worktree `mambo-power-m9-s4` | record/m9-s4-report.md + 1 commit | **done** (`33412e7`, merged `fc8bc85`). S4 finished the work and reported holding, uncommitted, on its own full-suite background run before committing — the F8/F11/F17 pattern this session has hit repeatedly. Orchestrator verified independently (20/20 guard tests, the guard passing against the real getting-started.md) and committed directly rather than waiting on the agent's own background run |
| m9-s5-semantic-release | senior-implementor | S5: python-semantic-release config, changelog restructure preserving all nine wave sections verbatim (W6, AC-4). Own worktree `mambo-power-m9-s5` | record/m9-s5-report.md + 1 commit | **done** (`34710aa`, merged `70407e4`). Config in `pyproject.toml` (not `.releaserc`); discovered the tool defaults its branch match to `main\|master` and had to widen it to `epic/01-foundation` (a real repo-shape gap the spec didn't anticipate); `allow_zero_version=true` + `major_on_zero=true` re-enabled so the first tag stays 0.1.0 (v10 defaults to forcing 1.0.0); the built-in update-mode insertion (an `<!-- version list -->` flag) does W6's coexistence requirement with no custom template, verified twice (throwaway repo + the real file — 2 hunks, 9/-5, none of the twelve wave subsections touched). AC-4's four fixture types all correct via the tool's own `--print`. Adversarial safety check: a fake merge commit with a `feat`-shaped subject line still correctly excluded (`ignore_merge_commits`). **Two findings routed to S7**: Windows-local runs need `PYTHONUTF8=1` (changelog's non-ASCII prose crashes the tool otherwise; GHA's UTF-8 locale likely spares CI); `semantic-release changelog` run twice without an intervening tag duplicates the Unreleased block — the release step must run via `semantic-release version`, never standalone twice |
| m9-s6-publish | senior-implementor | S6: publish.yml — tag-triggered, OIDC-only, pypi environment (W7, AC-5). Own worktree `mambo-power-m9-s6` | record/m9-s6-report.md + 1 commit | **done** (`a922ce6`, merged `bfddb0a`). Orchestrator-verified: trigger is exactly `push: tags: [v*]`, no `branches:`/`pull_request:`/`workflow_dispatch:`; `id-token: write` scoped only to the publish job; no `password`/`api-token` input on `gh-action-pypi-publish@v1.14.2`; a version-consistency check gates the build. Caught and fixed its own mistake before committing (a fabricated action SHA pin, corrected to a verified real tag). Dropped the optional `workflow_dispatch` escape hatch entirely rather than gate it — the safer reading of AC-5, kept as built |

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

Step 4 open: worktree `C:/Claude Projects/mambo-power-m9` on `wave/09-release-0.1` from `d18aaea`;
baseline dispatched on the clean main checkout. S1/S4/S5/S6 each in their own worktree
(`mambo-power-m9-s1/s4/s5/s6`) per A12, dispatched in parallel. S2 (needs S1's notebooks) and S3
(needs S2's nav entry) dispatch once S1/S2 land respectively; S7 closes once S1–S6 are merged.
