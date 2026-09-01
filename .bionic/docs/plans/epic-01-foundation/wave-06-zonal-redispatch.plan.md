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
  test-runner: sonnet
  auditor: opus
  critic: opus
---

# Wave M6 — zonal-redispatch — plan

Spec: `specs/epic-01-foundation/wave-06-zonal-redispatch.spec.md` (carries `## Design`).
Scope + design ledger: `record/m6-scope-closure.md`. Research: `record/m6-research.md`.

## SDLC State

integration-branch: epic/01-foundation
intent: build
rigor: audited
scale: wave
current: 3

- Step 0: prereqs: ok; configured 2026-08-27 via "confirm"; model_plan=fable-5/sonnet/opus;
  integration-branch=epic/01-foundation; base 4cfd1d7
- Step 1: record/m6-scope-closure.md (three scope answers, Not Doing, prior art)
- Step 2: specs/epic-01-foundation/wave-06-zonal-redispatch.spec.md (W1-W8, AC-1..AC-8 with
  provenance, ## Design ratified 2026-08-27 after D1-D3 walked, D4-D6 surfaced)
- Step 3: this plan, awaiting user approval
- Step 4: (not started)
- Step 5: (not started)
- Step 6: (not started)
- Step 7: (not started)
- Step 8: (not started)
- Step 9: (not started)

## Slices

Worktree `C:\Claude Projects\mambo-power-m6`, branch `wave/06-zonal-redispatch`, base `4cfd1d7`,
`.bionic` junction in place. Ordering constraint (spec W1, ADR-008): **S1 lands and is proven
before S3/S4 write any row family.** S2 is independent of S1 and runs concurrently.

| slice | scope | rows | complexity | role |
|---|---|---|---|---|
| S1 preamble-unification | W1: `_extract_and_validate` in `dc_opf.py`; `multiperiod.py` imports it; overlay-tree proof | AC-1 | complex | senior-implementor |
| S2 zones-fixture | W7 half: `tests/_zones.py` — AREA→Zone promotion, corridor caps from `tests/_rated.py`; helper tests | feeds AC-2/3/5/6 | standard | implementor |
| S3 zonal-lp | W2: `opf/zonal.py` b2 formulation; hand-derived 2-zone/3-bus + copper-plate degenerate | AC-2 | complex | senior-implementor |
| S4 redispatch-lp | W3: `opf/redispatch.py` D1 true-curve objective, Δ both sides; pf.dc feasibility | AC-3 | complex | senior-implementor |
| S5 market-zonal | W4/W5: `market/zonal.py`, `results/zonal.py` incl. branch rows; final==nodal; relaxation; three figures | AC-4, AC-5 | complex | senior-implementor |
| S6 oracle-parity | W7 half: PyPSA one-bus-per-zone + `Link`s, caps handed independently; engine-side sabotage | AC-6 | complex | senior-implementor |
| S7 jobs | W6: `market.zonal` kind, KINDS 7; `Scenario.periods` max_length 200 | AC-7 | standard | implementor |
| S8 docs | W8: manual, API pages, architecture, example + snippet, changelog M6 entry | AC-8 | complex | senior-implementor |

Every slice brief carries M5's standing rules: sabotage sweep over each new row family with the
residual that *moves* named; sabotage the engine, never shared fixture data; drive the test's own
fixture factory; report gate before bookkeeping; progress artifact at 10m cadence; explicit-path
commits only.

## Verification Matrix

stack-health: before (M5 close, 4cfd1d7): 816 tests, ruff/format/mypy clean, mkdocs --strict 0
warnings, 10/10 examples, CI green 8/8; after: (taken at Step 5)

walk-artifact: (Step 5 opens with it; `walk: required`; the mkdocs site + example + public API
are the drivable surface, walked by an agent that has not read the ACs)

auditor-wave: (Step 5 exit gate)

| AC | tier | status | evidence | auditor |
|---|---|---|---|---|
| AC-1 | T1 | pending | see AC-1 | |
| AC-2 | T1 | pending | see AC-2 | |
| AC-3 | T1 | pending | see AC-3 | |
| AC-4 | T1 | pending | see AC-4 | |
| AC-5 | T1 | pending | see AC-5 | |
| AC-6 | T2 | pending | see AC-6 | |
| AC-7 | T1 | pending | see AC-7 | |
| AC-8 | T2 | pending | see AC-8 | |

AC-1:
  criterion: W1's unification is behaviour-preserving — M5's suite passes with zero test edits on
    a tree differing from 4cfd1d7 only in the unified files; the getNumRow tripwire passes; no
    dc_opf-private name imported by multiperiod.py changes signature
  provenance: ADR-008 decision; record/m6-research.md §7
  tier-rationale: T1 — pure substrate; the existing suite green unmodified is the strongest
    available claim (M5 S1 precedent: git archive base + overlay changed files).
  tier-run: (filled at Step 4/5)
  readback: (filled at Step 4/5)

AC-2:
  criterion: zonal LP reproduces a hand-derived 2-zone/3-bus optimum with a binding corridor —
    zone prices differ by the derived amount, corridor at cap; with the cap removed every zone
    price equals nodal λ exactly
  provenance: design interview D2 2026-08-27; record/m6-research.md §2
  tier-rationale: T1 — hand-derived oracle, M3/M4/M5 hand-KKT shape. The copper-plate half is
    the degenerate control that proves the corridor bound is what makes prices differ.
  tier-run: (filled at Step 4/5)
  readback: (filled at Step 4/5)

AC-3:
  criterion: redispatched dispatch feasible in pf.dc under every rating on every multi-zone
    fixture to a pinned tolerance; paired negative — the zonal dispatch itself violates ≥1 rating
    on the strict fixture
  provenance: epic module table invariant; record/m6-research.md §4(c), §5
  tier-rationale: T1 — pure substrate. Absence-readback rule: "no violation" alone proves nothing,
    so the zonal-stage violation is the mandatory paired positive.
  tier-run: (filled at Step 4/5)
  readback: (filled at Step 4/5)

AC-4:
  criterion: redispatched point equals nodal — dispatch, demand, LMPs allclose to solve_nodal on
    case30 (promoted) and case300 (real zones) with bids; welfare_gap ≈ 0; paired negative: an
    anchored-rate objective in a scratch tree breaks agreement
  provenance: design interview D1 2026-08-27; epic module table "cost ≥ nodal"; research §4(a)
  tier-rationale: T1 — the D1 theorem's agreement test; tolerance not bit-equality (M5 CI lesson,
    plan A3). The anchored-rate sabotage is what proves the objective is load-bearing.
  tier-run: (filled at Step 4/5)
  readback: (filled at Step 4/5)

AC-5:
  criterion: welfare(zonal) ≥ welfare(nodal) on every multi-zone fixture, strictly on rated case30
    with nonzero redispatch volume; three figures distinct; settlement flow-dual side computable
    from the result object alone via its branch rows
  provenance: research §4(a) relaxation, §6; continuation-m5.md carry-over 2 (A23)
  tier-rationale: T1 — pure substrate. The strict case is the paired positive; A23's closure is
    checked by computing -Σ μ_k f_k from MarketZonalResult without a second solve.
  tier-run: (filled at Step 4/5)
  readback: (filled at Step 4/5)

AC-6:
  criterion: zonal stage matches a PyPSA one-bus-per-zone + Link oracle within measured, pinned
    tolerances on rated case30; partition and caps handed to PyPSA independently; engine-side
    sabotage goes red against the fixed oracle
  provenance: epic R9; research §5 (YES, probed); continuation-m5.md sabotage lesson
  tier-rationale: T2 — engine-divergent over a declared-fidelity fixture.
  fixture-fidelity: (declared at Step 4/5) — case30 verbatim MATPOWER; AREA→Zone promotion and
    corridor caps derived at test time by tests/_zones.py from tests/_rated.py; no new fixture
    data. The Link form is unproven (spec A1) — the row is at-risk until S6 lands.
  tier-run: (filled at Step 4/5)
  readback: (filled at Step 4/5)

AC-7:
  criterion: jobs.run/run_json for market.zonal pure, round-trips, never raises; six prior kinds
    unchanged; KINDS exactly 7; Scenario.periods rejects 201 entries and accepts 200
  provenance: epic module table SolveRequest kinds; design interview D6 2026-08-27; ADR-004
  tier-rationale: T1 — pure substrate; the backward-compatibility half is the risky half.
  tier-run: (filled at Step 4/5)
  readback: (filled at Step 4/5)

AC-8:
  criterion: mkdocs build --strict exits 0 with the new pages; coverage test unmodified; example
    exits 0 and is snippet-embedded; changelog carries M6
  provenance: epic R14; continuation-m5.md docs lesson
  tier-rationale: T2 — the built site is the artifact; its readback limit (build ≠ render) is why
    the walk precedes discharge.
  fixture-fidelity: the built site itself
  tier-run: (filled at Step 4/5)
  readback: (filled at Step 4/5)

## Tasks

One row per dispatched unit, written at dispatch (status `active`) and completed at
execution-confirmation. This harness has no task-list tool (checked at Step 0), so this ledger is
the visible progress surface.

| id | role | unit | deliverable | status |
|---|---|---|---|---|
| m6-research | researcher | Step 1/2: zone data on fixtures, zonal LP options, redispatch LP, invariants, PyPSA oracle, result shape, ADR-008 measurement, carry-overs — folded in the three scope answers mid-run | record/m6-research.md | done (41 KB, 8 sections, every claim command-backed; §5 verdict YES on PyPSA by a real case30 probe with feasibility re-checked by this repo's own PTDF; §4(b) found and worked the cost-inversion example that made D1 the strategic fork; §7 re-measured the ADR-008 duplication fresh at 0.791/55 lines. Process: it wrote the artifact before sending completion, inverting the report gate, and disclosed it; its completion message summarised a pre-update draft while the file carried the updated §3/§4 — verified by reading the file, not the message) |

## Assumptions

- A1 (spec A1): PyPSA `Link` form of b2 is unproven — research probed "intra-zone limits
  removed". AC-6 is the wave's at-risk row; if the Link form fails, AC-6 becomes an analytic T1
  row and the downgrade goes to the user under the Waiver Protocol.
- A2 (spec A2): case30's three AREA groups yield ≥1 corridor per pair.
- A3 (spec A3): AC-4 agreement is to tolerance, never bitwise (M5 CI macOS finding, `4cfd1d7`).
- A4 (spec A4): no multi-zone fixture has a generation-less zone.
- A5 (spec A5): `redispatch_payment` is a settlement figure; `welfare_gap` is the exactness row.
- A6 (ordering, from spec W1): S1 is proven before S3/S4 write a row family — the same slice-order
  constraint M5's A6 imposed on its extraction, for the same reason (attributability).
- A7 (carry-over, M4/M5): worktree junction — create with PowerShell, remove with git-bash `rm`
  first; **check for listeners on `site/` before deleting the directory** (M5: a walk agent's
  `http.server 8777` blocked removal). Held at Step 1: junction created, scope file visible.
- A8 (carry-over, M5): drive the test's own fixture factory; a hand-assembled reconstruction is
  not evidence.
- A9 (carry-over, M5 A9): idle is neither completion nor failure — check the artifact on disk.
- A10 (carry-over, M5 A10/A34): sabotage sweep per row family, naming the residual that moves;
  **a sabotage applied to shared fixture data is not a sabotage** — apply it to the engine with
  the oracle held fixed.
- A11 (carry-over, M5): `stop-guard.sh` Windows-path bug still open; finished agents idle.
- A12 (carry-over, M5): `dispatch-preflight.sh` needs a plain `Expected artifact:` label first.
- A13 (carry-over, M5): verification on a live shared worktree is read-only; sabotage in a
  detached scratch tree with `PYTHONPATH` and `__file__` printed.
- A14 (carry-over, M5 CI): when one finding is split across two agents, the split needs an owner
  and a check.
- A15 (process): no task-list tool in this harness; `## Tasks` is the progress surface.
- A16 (process, research): the researcher inverted the report gate and its message lagged its
  file; the file is authoritative — read it, do not trust the summary.

## Handoff

Resume point: Step 3, awaiting user approval of this plan (design + plan + matrix ratified
together). Branch `wave/06-zonal-redispatch` at `4cfd1d7`, worktree venv synced, no commits yet.
