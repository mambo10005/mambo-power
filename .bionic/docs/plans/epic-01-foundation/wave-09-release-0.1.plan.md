---
governing-skill: superpowers:writing-plans
sdlc-step: 5
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
current: 5

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
- Step 5: cmd: `uv run pytest tests/unit -q` (wave head `a221482`); pass: 1262; total: 1262;
  output: "1262 passed in 129.02s"; `tests/parity` 292 passed / 4 skipped (captured mid-slice by
  S7). walk-artifact: record/m9-walk.md (dispatched independent of the spec/plan/ACs, clean —
  zero AC-[0-9] occurrences, verified by grep). AC-1..AC-4 and AC-6 discharged with tier-run/
  readback evidence (see matrix below); AC-5 blocked on A16's live pypi.org check, named
  stop-and-wake, not waived. Auditor dispatched next.

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

stack-health: OK — `tests/unit` 1262 passed (2026-08-31, wave head `a221482`, 129.02s), `tests/parity`
292 passed / 4 skipped (confirmed by S7 mid-slice, orchestrator-trusted since S7's own gate output
was captured before its bookkeeping vanished). Full CI matrix not re-run for the wave itself (case30
task's own CI push at `fde354e` already confirmed all 8 jobs green on the fix this wave's base
includes); a fresh CI push happens naturally at Step 9 when `epic/01-foundation` is pushed.

| AC | tier | status | evidence | auditor |
|---|---|---|---|---|
| AC-1 | T2 | discharged | see AC-1 | |
| AC-2 | T1 | discharged | see AC-2 | |
| AC-3 | T1 | discharged | see AC-3 | |
| AC-4 | T2 | discharged | see AC-4 | |
| AC-5 | T2 | blocked | see AC-5 | |
| AC-6 | T0 | discharged | see AC-6 | |

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
  tier-run: `uv run pytest --nbmake docs/tutorials/*.ipynb -q` → 4 passed, 16.76s (2026-08-31, wave
    head `a221482`)
  readback: `mkdocs build --strict` output HTML for tutorial 1 contains 25 rendered Jupyter
    output-area elements (`jp-OutputArea`) — outputs visible, not stripped
AC-2:
  criterion: Tutorials nav entry between Getting started and Manual; Manual's 12 entries byte-identical in content/order; roadmap reads merged M1-M9; "where do I go" table lists Tutorials
  provenance: user 2026-08-31 "Structural reorg" + "Stay flat"
  tier-run: `mkdocs.yml` nav literal — Tutorials (index + 4 notebooks) sits directly above Manual;
    S2's diff confirmed Manual's 12 entries byte-identical (unchanged this check)
  readback: `grep -in "in progress\|planned" docs/index.md` → zero matches (all-merged confirmed);
    `grep -i tutorial docs/index.md` → Tutorials row present in both the roadmap table and the
    "where do I go" table
AC-3:
  criterion: getting-started.md says "not on PyPI yet" through Step 8's merge; PyPI install text added only in the same action as the v0.1.0 tag push; a script asserts the tag exists whenever that text is present
  provenance: user 2026-08-31 sequencing requirement (W5)
  tier-run: `uv run pytest tests/unit/test_pypi_sequencing_guard.py -q` → 20 passed, 0.57s
  readback: `python scripts/check_pypi_sequencing.py` against the real `docs/getting-started.md` →
    "OK: no unqualified PyPI install text found (pre-release state)", exit 0; file itself reads
    "mambo-power is not on PyPI yet (that is wave M9, version 0.1.0)"
AC-4:
  criterion: semantic-release computes the correct next version from hand-authored conventional-commit fixtures (feat/fix/breaking/chore) via dry-run starting from v0.1.0; its section inserts above the nine wave sections without altering their text
  provenance: epic M9 row; user 2026-08-31 "Coexist"
  fixture-fidelity: hand-authored commit-message fixtures covering every bump type semantic-release must classify, run through its own real dry-run engine
  tier-run: throwaway clone of the wave head, tagged `v0.1.0`, checked out as `epic/01-foundation`
    (the tool's configured release branch) — one fixture commit at a time on top, each
    `semantic-release --noop version --print`: `feat` → 0.2.0 (correct minor bump per
    allow_zero_version), `fix` → 0.1.1 (correct patch bump), `feat`+`BREAKING CHANGE:` → 1.0.0
    (correct major_on_zero override), `chore` → "No release will be made, 0.1.0 has already been
    released!" (correctly non-bumping). All four match spec exactly.
  readback: S5's own report (`70407e4`) — the built-in update-mode insertion verified twice (a
    throwaway repo, then the real changelog.md: 2 hunks, 9 insertions/5 deletions in 546 lines,
    none of the twelve `###` wave subsections touched)
AC-5:
  criterion: publish.yml triggers only on a v* tag push, not on every commit; OIDC only, no token/secret anywhere; pypi environment values match the user's actual pypi.org configuration (live-checked or named stop-and-wake)
  provenance: epic M9 row; epic A10; the user's own PyPI configuration
  fixture-fidelity: the real GitHub Actions workflow file and (where checkable) the real pypi.org trusted-publisher state
  tier-run: read `.github/workflows/publish.yml` directly (2026-08-31) — trigger is exactly
    `on: push: tags: ["v*"]`, no `branches:`/`pull_request:`/`workflow_dispatch:` keys anywhere in
    the file; `permissions: id-token: write` appears only under the `publish` job, not top-level or
    on `build`; no `password:`/`api-token:` input on `pypa/gh-action-pypi-publish@v1.14.2`;
    `environment: {name: pypi, url: https://pypi.org/p/mambo-power}` present. Static half: pass.
  readback: live half (A16) — orchestrator has no PyPI account access to confirm the trusted
    publisher is actually configured on pypi.org for owner/repo/workflow=publish.yml/env=pypi, and
    this is account/billing-adjacent territory ("ask first" per CLAUDE.md). **Named stop-and-wake,
    not silently waived**, per A16 — asked the user directly rather than assumed complete.
AC-6:
  criterion: M9 changelog entry; mkdocs --strict exit 0, zero unlinked-page/dangling-anchor lines; every new page reachable from the nav
  provenance: epic R14
  tier-run: `uv run mkdocs build --strict` → exit 0 (2026-08-31, wave head `a221482`), no
    ERROR/WARNING lines beyond the vendored Material-team 2.0 upgrade notice (unrelated to this
    site); M9 changelog section present (commit `640a378`, 52 lines) covering tutorials, nav
    reorg, PyPI-sequencing guard, semantic-release config, publish.yml
  readback: every new page (4 tutorial notebooks + index) appears in `mkdocs.yml` nav, confirmed
    above under AC-2's tier-run

## Tasks

| id | role | unit | deliverable | status |
|---|---|---|---|---|
| m9-s1-tutorials | senior-implementor | S1: four narrative tutorial notebooks + intro page (W1). Own worktree `mambo-power-m9-s1` on `wave/09-release-0.1-s1` | record/m9-s1-report.md + 5 commits | **done** (`8af9df5` index, `7d2b2cf`/`2bb8cd7`/`eb84e5c`/`bceb367` the four notebooks; merged `f5847ec`). Went beyond the brief: fully executed all four via `jupyter nbconvert --to notebook --execute --inplace` (jupyter/nbconvert/ipykernel installed transiently, never added to pyproject.toml/uv.lock — S2's job), all exit 0, baked-in outputs match standalone-script runs bit for bit; full execution verification NOT deferred to S2 as the brief allowed. `git diff --stat -- . ':!docs/tutorials'` empty — nothing touched outside its own directory |
| m9-s4-getting-started | implementor | S4: PyPI-install-text-vs-tag drift guard (W5, AC-3). Own worktree `mambo-power-m9-s4` | record/m9-s4-report.md + 1 commit | **done** (`33412e7`, merged `fc8bc85`). S4 finished the work and reported holding, uncommitted, on its own full-suite background run before committing — the F8/F11/F17 pattern this session has hit repeatedly. Orchestrator verified independently (20/20 guard tests, the guard passing against the real getting-started.md) and committed directly rather than waiting on the agent's own background run |
| m9-s5-semantic-release | senior-implementor | S5: python-semantic-release config, changelog restructure preserving all nine wave sections verbatim (W6, AC-4). Own worktree `mambo-power-m9-s5` | record/m9-s5-report.md + 1 commit | **done** (`34710aa`, merged `70407e4`). Config in `pyproject.toml` (not `.releaserc`); discovered the tool defaults its branch match to `main\|master` and had to widen it to `epic/01-foundation` (a real repo-shape gap the spec didn't anticipate); `allow_zero_version=true` + `major_on_zero=true` re-enabled so the first tag stays 0.1.0 (v10 defaults to forcing 1.0.0); the built-in update-mode insertion (an `<!-- version list -->` flag) does W6's coexistence requirement with no custom template, verified twice (throwaway repo + the real file — 2 hunks, 9/-5, none of the twelve wave subsections touched). AC-4's four fixture types all correct via the tool's own `--print`. Adversarial safety check: a fake merge commit with a `feat`-shaped subject line still correctly excluded (`ignore_merge_commits`). **Two findings routed to S7**: Windows-local runs need `PYTHONUTF8=1` (changelog's non-ASCII prose crashes the tool otherwise; GHA's UTF-8 locale likely spares CI); `semantic-release changelog` run twice without an intervening tag duplicates the Unreleased block — the release step must run via `semantic-release version`, never standalone twice |
| m9-s6-publish | senior-implementor | S6: publish.yml — tag-triggered, OIDC-only, pypi environment (W7, AC-5). Own worktree `mambo-power-m9-s6` | record/m9-s6-report.md + 1 commit | **done** (`a922ce6`, merged `bfddb0a`). Orchestrator-verified: trigger is exactly `push: tags: [v*]`, no `branches:`/`pull_request:`/`workflow_dispatch:`; `id-token: write` scoped only to the publish job; no `password`/`api-token` input on `gh-action-pypi-publish@v1.14.2`; a version-consistency check gates the build. Caught and fixed its own mistake before committing (a fabricated action SHA pin, corrected to a verified real tag). Dropped the optional `workflow_dispatch` escape hatch entirely rather than gate it — the safer reading of AC-5, kept as built |
| m9-s3-nav-home | implementor | S3: index.md status/roadmap/where-do-I-go reorg (W4, AC-2). Own worktree `mambo-power-m9-s3` on `wave/09-release-0.1-s3` | record/m9-s3-report.md + 1 commit | **done** (`9f0e47c`, merged `9a4d6f7`). Its own bookkeeping/report never landed (no progress log, backgrounded strict-build never reported back) — the F8/F11/F17 pattern a fifth time. Orchestrator verified independently (guard script still passes, zero stale status language, strict build clean) and committed directly |

**F1 (M9) — S2 and S5 both touched `pyproject.toml`'s dependency groups and `uv.lock`, and the
lockfile conflicted on merge** (expected, per A12's own worktree-isolation reasoning — two slices
touching the same generated file will conflict at merge time regardless of how isolated their
work was). `pyproject.toml` auto-merged cleanly (git's textual merge handles TOML table entries
fine when they're additive and non-overlapping); `uv.lock` did not (a generated, dependency-solved
file — text-merging it is never correct even when it succeeds). Resolved by taking one side's
lockfile as a valid TOML starting point (`git show HEAD:uv.lock`, since `checkout --ours` failed
after an earlier `git rm --cached` broke the index reference) and running `uv lock` fresh against
the merged `pyproject.toml` — regenerates rather than merges. `uv sync --locked --all-groups` and
the strict build both re-verified clean after. Rule for the rest of this wave and any future one:
a merge touching `uv.lock` always ends in `uv lock` + a sync/build re-check, never a manual
conflict-marker resolution on the lockfile itself.
| m9-walk | general-purpose | Step-5 walk: drives the built docs site, executes a tutorial notebook fresh, reads getting-started.md/publish.yml/changelog.md, narrates only — no AC/spec/plan access | record/m9-walk.md | **done**. Clean: strict build 85.56s no project warnings; fresh nbconvert re-execution of tutorial 1 exits 0, matches committed notebook (one cell differs only in stdout stream-chunking, not content); home page's status/roadmap agree with what's actually on disk; getting-started.md unambiguous on pre-release state; publish.yml read plain-language, matches S6's own claims; changelog top-portion coherent. Surprises (all non-blocking): tutorial 2's N-1 screen flags 18/19 branches (fully explained by its own 20%-headroom synthetic rating, but a skimming reader could misread it); mkdocs 2.0's future plugin-system removal will eventually force a decision (not this wave's problem); the `pypi` environment's approval gate is unverifiable from the YAML alone (matches A16's own framing) |
| m9-auditor | auditor (opus) | Step-5 independent audit: coverage/power/authenticity walk over the discharged matrix rows, re-execution of one evidence command per tier used | record/m9-audit.md | active |
| m9-s7-wave-docs | implementor | S7: M9 changelog entry, final nav/strict-build check (W8, AC-6). Works in the wave worktree — only agent there, all six other slices merged | record/m9-s7-report.md + commits | **done** (`640a378` changelog entry, `a221482` ruff-clean the four notebooks — found ruff DOES lint `.ipynb`, which S1/S2 both wrongly assumed it didn't). Own bookkeeping/report never landed a sixth time (F8/F11/F17/S3/S4 pattern) — orchestrator verified independently: `tests/unit` 1262 passed (1242 baseline + S4's 20 new guard tests, consistent), `tests/parity` 292/4 already confirmed by S7 mid-slice, `mkdocs build --strict` exit 0, ruff+format+mypy already confirmed clean by S7 mid-slice. Head `a221482` is on `wave/09-release-0.1` directly (S7 worked in the wave worktree itself — no merge step) |

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
