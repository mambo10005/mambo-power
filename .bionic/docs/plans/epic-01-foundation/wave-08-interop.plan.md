---
governing-skill: superpowers:writing-plans
sdlc-step: 3
intent: build
rigor: audited
scale: wave
canonical_sdlc_version: 13
surface_type: library
language: python
has_ui: false
multi_agent: true
deploy_target: none
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
  test-runner: sonnet
  auditor: opus
  critic: opus
---

# Wave M8 — interop — plan

Spec: `specs/epic-01-foundation/wave-08-interop.spec.md` (carries `## Design`).
Scope + design ledger: `record/m8-scope.md`. Research: `record/m8-research.md`.

## SDLC State

integration-branch: epic/01-foundation
intent: build
rigor: audited
scale: wave
current: 3

- Step 0: prereqs: ok; configured 2026-08-30 via "confirm"; model_plan=fable-5/sonnet/opus;
  integration-branch=epic/01-foundation; base cdb4fef (1175 passed / 4 skipped locally; CI green on
  Linux/macOS/Windows at that head)
- Step 1: record/m8-scope.md (rulings D1–D4, Not Doing, prior art, four questions carried to Step 2)
- Step 2: specs/epic-01-foundation/wave-08-interop.spec.md (W1–W8, AC-1..AC-8 with provenance,
  `## Design` ratified 2026-08-30 after the frame and S1–S3 walked one per turn, T1–T6 surfaced at
  ratification; research `record/m8-research.md` supplied every field map)
- Step 3: plans/epic-01-foundation/wave-08-interop.plan.md approved by the user 2026-08-30 ("Approved — go"); design + plan + matrix locked together at that one checkpoint; governing design: the spec's `## Design` + epic.spec.md
- Step 4: (pending)
- Step 5: (pending)
- Step 6: (pending)
- Step 7: (pending)
- Step 8: (pending)
- Step 9: (pending)

## Slices

| slice | scope | ACs | complexity | role | depends on |
|---|---|---|---|---|---|
| S1 `kind` + reports | W6 `Branch.kind` defaulted at construction, schema snapshot; W7 `ExportReport` in `io/report.py`; the docs test that ties each module's limitation list to its report codes (stub, filled by S2–S5) | AC-6, AC-7 | complex | senior-implementor | — |
| S2 pandapower JSON | W1 import + W2 export, lazy pandapower import, `ext_grid` rule, unit conversions, parity vs `rundcpp`/`runpp`, `nets_equal` (A6) | AC-1, AC-2 | complex | senior-implementor | S1 |
| S3 PyPSA export | W3, parity vs `opf.solve_dc_opf` on case14/30/118, drop-and-report for inexpressible costs, no `p_set` on generators | AC-3 | standard | implementor | S1 |
| S4 RAW v33 | W4 parser; **fixtures first**: `fixtures/case14_v33.raw` hand-authored from `case14.m` with PROVENANCE, plus `fixtures/synthetic_quirks_v33.raw` with hand-derived expected values | AC-4 | complex | senior-implementor | S1 |
| S5 CSV bundle | W5 dump/load, manifest, side tables, bit-exact round-trip on every fixture, three malformed-bundle errors | AC-5 | standard | implementor | S1 |
| S6 docs | W8: `formats.md` sections, API pages, `examples/13_interop.py`, changelog, architecture edge; `test_api_docs_coverage` green | AC-8 | standard | implementor | S2–S5 |

S2–S5 run in parallel after S1 lands (they share only `io/report.py` and `model/entities.py`,
which S1 owns and finishes first). Each slice owns its module, its test file(s) and its fixtures;
nothing else. Per-file ownership is in the dispatch briefs; the orchestrator verifies every
commit's `--stat` against it (M7 F16).

## Verification Matrix

stack-health: PENDING — taken at Step 5 (baseline 1175 passed / 4 skipped at cdb4fef, CI green on 3 OS)

| AC | tier | status | evidence | auditor |
|---|---|---|---|---|
| AC-1 | T2 | pending | see AC-1 | |
| AC-2 | T2 | pending | see AC-2 | |
| AC-3 | T2 | pending | see AC-3 | |
| AC-4 | T1 | pending | see AC-4 | |
| AC-5 | T1 | pending | see AC-5 | |
| AC-6 | T1 | pending | see AC-6 | |
| AC-7 | T1 | pending | see AC-7 | |
| AC-8 | T0 | pending | see AC-8 | |

Tier rationale: AC-1..AC-3 are T2 because the real engine (pandapower, PyPSA) runs over the
converted network — the fixture-fidelity declaration is the MATPOWER case each was derived from;
AC-4..AC-7 are pure substrate with no runtime surface (hand-derived oracles, bit-exact round-trips,
schema snapshot); AC-8 is docs. No T3: nothing is a live surface. The walk (required) drives the
four modules from `formats.md` as a user would, before any row discharges.

AC-1:
  criterion: pandapower JSON import agrees with the MATPOWER-derived Network on case14/30 to 1e-9 on every listed field; multi-ext_grid → one slack + warning; dropped columns reported
  provenance: epic R11; user 2026-08-30 "Best effort + report"; m8-research.md §1
  fixture-fidelity: pandapower's own `pp.networks.case14()`/`case30()` (real pandapower objects) against `fixtures/case14.m`/`case30.m` (MATPOWER, PROVENANCE files)
  tier-run: (pending)
  readback: (pending)
AC-2:
  criterion: exported JSON loads in pandapower; rundcpp/runpp agree with pf.solve_dc/solve_ac to 1e-6 on case14/30/57; nets_equal on carried tables; dropped costs reported
  provenance: epic R11; user 2026-08-30 "Drop + report"; m8-research.md §1
  fixture-fidelity: the six bundled MATPOWER cases, exported by this wave and solved by pandapower 3.3.0
  tier-run: (pending)
  readback: (pending)
AC-3:
  criterion: PyPSA optimize on to_network(net) agrees with opf.solve_dc_opf on case14/30/118 (1e-8 rel objective, 1e-4 MW dispatch); piecewise units at marginal_cost 0 and reported; no generator p_set
  provenance: epic R11; user 2026-08-30 "Drop + report"; m8-research.md §2; M3 spec AC-3
  fixture-fidelity: bundled MATPOWER cases with degree ≤ 2 costs, solved by PyPSA 1.2.4 / linopy 0.9.1 / HiGHS
  tier-run: (pending)
  readback: (pending)
AC-4:
  criterion: case14_v33.raw imports equal to case14.m's Network (kind included) to 1e-9, costs absent and reported; quirks fixture matches hand-derived values; 3-winding records ignored with one report entry each
  provenance: epic R11; user 2026-08-30 "Hand-author from case14.m"; m8-research.md §3
  tier-run: (pending)
  readback: (pending)
AC-5:
  criterion: load(dump(net)) == net and array_equal on every NetworkArrays matrix for all fixtures; three malformed bundles fail with named errors; manifest names the schema version
  provenance: epic R11; user 2026-08-30 "Machine round-trip"; m8-research.md §4
  tier-run: (pending)
  readback: (pending)
AC-6:
  criterion: Branch.kind defaults line/transformer from tap/shift; snapshot changes by one property; every pre-M8 test unmodified and green; pandapower's neutral-tap transformer round-trips as transformer
  provenance: user 2026-08-30 "Explicit kind, defaulted"; m8-research.md G4
  tier-run: (pending)
  readback: (pending)
AC-7:
  criterion: each module's lossy conversion yields a report naming element and field; lossless yields an empty report; raise_on_error as ImportReport; no logging/printing
  provenance: user 2026-08-30 "Best effort + report"; M1 io.report
  tier-run: (pending)
  readback: (pending)
AC-8:
  criterion: formats.md sections, API pages under the griffe guard, examples/13_interop.py exit 0 and embedded, changelog, mkdocs --strict exit 0
  provenance: epic R14; M6/M7 docs rows
  tier-run: (pending)
  readback: (pending)

## Tasks

| id | role | unit | deliverable | status |
|---|---|---|---|---|
| m8-research | researcher | Field maps for the four formats against `Network`; model gaps G1–G11; fixture candidates; versions | record/m8-research.md | **done** (orchestrator-verified: artifact exists, 11 gaps, three fidelity limits; measured pandapower/PyPSA unit conventions and the `from_ppc` failure that rules out pandapower's converter) |

## Assumptions

Design assumptions A1–A8 live in the spec. Process assumptions, binding from Step 4:

- **A11** — baseline is taken on the clean main checkout before any agent enters the worktree
  (M7 A14); the wave worktree is `C:/Claude Projects/mambo-power-m8` on `wave/08-interop` from
  `cdb4fef`, removed at Step 8 with `git worktree remove --force` (M7 F20 — never `rm -rf`).
- **A12** — one agent in the worktree at a time per file set; S2–S5 own disjoint files; measurement
  from `git archive` overlays with `__file__` proven (M7 A16).
- **A13** — every slice commit's `--stat` is checked against the brief's file list before its
  report is believed (M7 F16); agents are stopped on hand-back (M7 F17); briefs say never amend.
- **A14** — the walk is dispatched first at Step 5, from `formats.md` and the example only,
  forbidden the spec/plan/reports, artifact machine-checked for zero `AC-[0-9]`.
- **A15** — `.bionic/docs/` is committed with each checkpoint commit (it is tracked since
  `7f396be`); `.bionic/tmp/` stays ignored and is wiped at Step 8 after evidence moves to `record/`.
- **A16 (at risk, from spec A6)** — `nets_equal` on our export re-imported: S2 measures it first
  and reports the exact table set on which it holds; if it fails on a carried table, that is a
  finding, not a tolerance.

## Handoff

Awaiting the Step-3 approval checkpoint. On "go": commit the Step 0–3 artifacts on
`epic/01-foundation`; create `wave/08-interop` + worktree; take the baseline on the clean main
checkout; dispatch S1; on S1's commit, dispatch S2–S5 in parallel; S6 on all four.
