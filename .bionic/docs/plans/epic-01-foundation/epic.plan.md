---
governing-skill: superpowers:writing-plans
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
rigor-floor: audited
walk: exempt
design-interview: true
model_plan:
  orchestrator: fable-5
  implementor: sonnet
  senior-implementor: opus
  researcher: sonnet
  test-runner: sonnet
  auditor: opus
  critic: opus
---

# Epic 01 plan — mambo-power wave carve

Spec: .bionic/docs/specs/epic-01-foundation/epic.spec.md (governing design lives there, section Design).
Epic scale runs steps 0-3 only; each wave below is its own canonical-sdlc run (wave spec +
plan under this epic's dirs, own worktree) branched from epic/01-foundation.

## SDLC State

integration-branch: main
intent: build
rigor: audited
scale: epic
current: 3

- Step 0: prereqs: ok; configured 2026-08-20 via "confirm"; model_plan=fable-5/sonnet/opus tiers; integration-branch=main; walk=exempt (library, no UI)
- Step 1: scope closed in epic.spec.md sections Requirements + Not Doing + Prior art; brainstorm Q&A 2026-08-20 (runtime=Python, commercial=Web SaaS, foundation=own model + own solvers, layering=A two repos)
- Step 2: design interview run as the sectioned walk 2026-08-20 (architecture "ok", formulations "ok", stack/carve/gridlab "ok"); spec approved 2026-08-20 ("approved"); governing design in epic.spec.md section Design
- Step 3: epic.plan.md approved by user 2026-08-20 ("approved"); design + plan + matrix + ADRs 001-004 ratified together; matrix discharged; AC-4 executed (see Handoff)

## Waves

Ordering rules (from spec AC-2): nodal LMP before every other market mode; agent-based
bidding last among markets. Waves marked [par] can run in parallel with their row-neighbour
once their dependency is met. Every wave carries the audited rigor floor and ships a
tagged, pip-installable state of the package (`uv build` green) even before 0.1.0.

| Wave | Slug | Delivers | Depends on | Flags |
|---|---|---|---|---|
| M1 | substrate | uv project (pyproject, lock, src layout), ruff + mypy strict, pytest tiers (unit/parity/property), GitHub Actions CI matrix (Linux/macOS/Windows) with pandapower+PyPSA dev-deps proven installable (spec assumption 3); `model` pydantic v2 Network + Scenario + JSON schema export + named validation errors; `io.native` round-trip; `io.matpower` importer; MATPOWER fixtures migrated from gridlab W1 with PROVENANCE/SOURCES verbatim; `numerics` Ybus/Bbus/PTDF/LODF with dense re-derivation tests | — | walk exempt (no drivable surface) |
| M2 | power-flow | `pf.ac_newton` (sparse Jacobian, splu, Q-limit PV→PQ, flat/warm start), `pf.dc`; parity vs MATPOWER published solutions + pandapower on IEEE 14/30/57/118; `results` provenance stamp; `jobs` SolveRequest/SolveResult/run() with kinds pf.ac, pf.dc; timing measurement for assumption 1 | M1 | |
| M3 | opf-n1 | `opf.dc_opf` single LP builder on highspy with duals (assumption 2 verified first, fallback recorded); PWL costs; parity vs MATPOWER rundcopf + PyPSA; `contingency.n1` LODF screen + re-solve, brute-force agreement test; jobs kinds opf.dc, n1 | M2 | |
| M4 | nodal-market | Scenario offers/bids model; `market.nodal` day-ahead clearing; LMP = energy + congestion decomposition; congestion rent; settlement identities as tests; jobs kind market.nodal | M3 | first market wave by AC-2 |
| M5 | multiperiod | 24-period LP with ramp coupling and storage SoC dynamics; scenario runner; degenerate-to-nodal and analytic arbitrage tests; jobs kind market.multiperiod | M4 | [par] with M6 |
| M6 | zonal-redispatch | zonal clearing LP, min-cost redispatch LP, nodal-vs-zonal comparison result; feasibility and cost-ordering invariants; jobs kind market.zonal | M4 | [par] with M5 |
| M7 | agents | `Strategy` protocol, bid→clear→settle→learn loop, reference strategies (price-taker, pivotal-supplier markup); competitive-reproduction and cap tests; jobs kind market.agents | M5 | last market wave by AC-2 |
| M8 | interop | pandapower JSON import/export, PyPSA export, PSS/E RAW v33 import, CSV bundle; round-trip tests vs schema fixtures | M1 | [par] any time after M1 |
| M9 | release-0.1 | mkdocs-material site on GitHub Pages, API reference, notebook-tested tutorials, CHANGELOG via python-semantic-release, PyPI trusted publishing, 0.1.0 tag; re-derives walk (docs site is drivable → walk: required) | all | PyPI project name claim is a user action |

Standing requirement from 2026-08-20 (spec R14): every wave from M2 on ships documentation
— manual page(s), class descriptions (mkdocstrings), mermaid diagrams, runnable examples in
CI — for what it adds; M2 also backfills M1 (docs site skeleton, model/io/numerics manuals,
data-model diagram, first examples). M9 becomes release polish, not the first docs.

Epic close: after M9 merges, epic/01-foundation merges to main once, with continuation
notes for anything deferred. The gridlab SaaS epic opens only after that merge.

## Verification Matrix

stack-health: n/a: epic scale ships documents only; no runtime stack exists yet

| AC | tier | status | evidence | auditor |
|---|---|---|---|---|
| AC-1 | T0 | discharged | see AC-1 | |
| AC-2 | T0 | discharged | see AC-2 | |
| AC-3 | T0 | discharged | see AC-3 | |
| AC-4 | T0 | discharged | see AC-4 | |

AC-1:
  criterion: epic.spec.md carries requirements + governing design (docs tier T0)
  provenance: user 2026-08-20 "Can you redesign this idea?"
  tier-run: epic.spec.md written and user-approved 2026-08-20 ("approved"); contains R1-R13 with provenance, Not Doing, Prior art, and a flush-left Design section with domain model, module boundaries, ownership table, verification table, stack, rejected alternatives, assumptions, gridlab disposition; governing-skill hook accepted the write
  readback: .bionic/docs/specs/epic-01-foundation/epic.spec.md
AC-2:
  criterion: epic.plan.md carves dependency-ordered waves, LMP-first, agents-last (docs tier T0)
  provenance: user 2026-08-20 "ok" (design section 3)
  tier-run: Waves table M1-M9 with depends-on column; M4 nodal precedes M5/M6/M7; M7 agents is the final market wave; M8 interop and M5/M6 marked parallel
  readback: .bionic/docs/plans/epic-01-foundation/epic.plan.md section Waves
AC-3:
  criterion: ADRs recorded for Python foundation, own solvers, two-repo layering, stateless job surface (docs tier T0)
  provenance: user 2026-08-20 "Python" / "Own model + own solvers" / "A"
  tier-run: four ADRs written 2026-08-20 under adrs/epic-01-foundation/ (adr-001-python-foundation, adr-002-own-model-own-solvers, adr-003-two-repo-library-first, adr-004-stateless-job-surface)
  readback: .bionic/docs/adrs/epic-01-foundation/
AC-4:
  criterion: gridlab re-pointed — archive tag, README, superseded ADRs, fixtures moved (docs tier T0)
  provenance: user 2026-08-20 "ok" (design section 3, gridlab's fate)
  tier-run: see Handoff section line "AC-4 execution" for the tag SHA, README commit, ADR edits and fixture destination
  readback: gridlab `git tag -l archive/ts-w1`; gridlab README.md; gridlab .bionic/docs/adrs/epic-01-power-market-platform/adr-00{1,2,4}*.md status lines; mambo-power fixtures/matpower/

## Assumptions

Seeded from spec section Not Doing and spec Design assumptions 1-6. Additions:

- A7: Wave carve treats M5/M6 as parallelizable and M8 as free-floating after M1; if a
  shared `model` schema change surfaces mid-wave, serialize and log here.
- A8: epic/01-foundation is the integration branch every wave merges into; main receives
  exactly one merge at epic close.
- A9: Waves are dispatched with worktrees (use_worktree true at wave scale) because
  multiple waves may be in flight; the epic itself needs none.
- A10: The PyPI name `mambo-power` is assumed available; claiming it (and creating the
  GitHub remote) is a user action — M9 carries a stop-and-wake if the name is taken.
- A11: gridlab's W1 worktree `C:\Claude Projects\gridlab-w1` is removed once the archive
  tag exists; the tag preserves the tree, so removal is reversible.

## Handoff

Resume point: epic steps 0-3 COMPLETE and approved 2026-08-20. Epic run closed by design
(epic scale does not run 4-9). Branch epic/01-foundation created off main. GitHub remote
mambo10005/mambo-power exists; main pushed.
Decisions ratified: triple (build/audited/epic), Python runtime, Web SaaS as the future
commercial layer, own model + own solvers, two-repo library-first layering, MIT licence,
wave carve M1-M9.
Tried and rejected: see spec section Rejected alternatives.
Open blockers: none. User actions outstanding: create GitHub remote mambo10005/mambo-power;
claim PyPI name before M9.
AC-4 execution (2026-08-20): gridlab tag archive/ts-w1 → e9f3f3507f4b63dad0a59f7eaad850e1d9a1f738
(wave/01-substrate-powerflow head, clean tree); gridlab README rewritten, commit 365fd72 on
main; gridlab ADR-001/002/004 status lines marked superseded by mambo-power ADR-001,
ADR-003 marked re-evaluate (untracked .bionic, no commit); fixtures copied to
mambo-power fixtures/matpower/ (7 files incl. PROVENANCE.md + SOURCES.md), sha256 of all
five .m files verified SAME against `git show archive/ts-w1:…`, commit ca10b6a; gridlab-w1
worktree deregistered (`git worktree list` shows main only) but its directory
C:\Claude Projects\gridlab-w1 could not be deleted from this session (tool permission
refused twice) — user deletes it; nothing in it is unpreserved.
Resume instruction: on approval, create branch epic/01-foundation off main; open M1
substrate as its own wave-scale canonical-sdlc run (wave spec + plan under this epic's
dirs; branch wave/01-substrate off epic/01-foundation; worktree). First M1 actions:
uv init + CI skeleton proving pandapower/PyPSA install on the matrix (assumption 3);
port Case schema v1 field set to pydantic.
