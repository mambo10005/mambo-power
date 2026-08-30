---
governing-skill: superpowers:writing-plans
sdlc-step: 1
intent: bugfix
rigor: audited
scale: task
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
  auditor: opus
  critic: opus
---

# Task — the DC-OPF phase-shifter flow defect (M7 F1, M8 A19)

## SDLC State

integration-branch: epic/01-foundation
intent: bugfix
rigor: audited
scale: task
current: T1

- T0: prereqs: ok; configured 2026-08-30 via "confirm"; model_plan=fable-5/sonnet/opus;
  integration-branch=epic/01-foundation; base e02feea (1513 passed / 4 skipped)

## Scope (Step 1, compressed for bugfix)

**The bug, diagnosed and located precisely before Step 0.** `pf.solve_dc` (`pf/dc.py`) solves the
correct DC model — `B'θ = P − p_shift`, `flow = Bf·θ + pf_shift`, equivalently
`flow = PTDF @ (P − p_shift) + pf_shift` — and three other sites compute the same flow from a
PTDF matrix without the `− p_shift` term:

1. `opf/dc_opf.py:927–933` — the LP's own flow-limit row constant:
   `const = pf_shift_mw − ptdf_matrix @ fixed_bus_mw` (missing `− ptdf_matrix @ p_shift_mw`).
2. `opf/__init__.py:206–210` — `solve_dc_opf`'s derived branch-flow result, same formula.
3. `market/_clearing.py:100–115` — the nodal/agents branch-flow result, same formula.

`numerics.bbus.p_shift(arr)` already exists (per-bus phase-shifter injection, pu) and is unused at
all three sites. Measured on the clean checkout (`e02feea`) with a 3-bus loop, one ±5° shifter,
generously rated: `pf.solve_dc` and PyPSA `lpf()` agree to 1e-9 (95.755 / 37.578 MW); `solve_dc_opf`
disagrees (153.933 / −20.600 MW) and violates KCL at the load bus by ~87 MW; at 0° the two agree
exactly. No bundled fixture has a phase shifter, so five waves never hit it (M7's continuation, M8's
walk on a generously-rated loop found it `Infeasible`).

**Not doing:** no change to the flow *formulation* itself (rating rows, LMP decomposition,
`lmp_decomposition`'s own math are untouched — they consume `duals`, not the derived flow); no
change to `numerics.bbus` (the correct primitives already exist); no new market mode.

**Fix:** subtract `p_shift(arr) * arr.base_mva` inside the PTDF product at all three sites — one
shared correction, applied identically, since it is the same formula in three places (a candidate
for a shared helper, left to the implementor's judgment — the design ledger below records the
choice).

## Design (Step 2, compressed — the model is `pf.solve_dc`'s, already correct and in the repo)

**Domain model:** no new entity. The correction is `flow_k = PTDF[k,:] @ (injection − p_shift) +
pf_shift_k`, matching `pf.solve_dc`'s own `p_from`/`p_inj` construction exactly — this is a
restoration, not a new design decision.

**Fixture:** no bundled MATPOWER case has a shifter (M8 research). A new hand-built network with a
phase shifter, generous ratings, is required for AC-1/AC-2/AC-3; place it in `tests/_shifter.py`
or beside the existing per-module fixture helpers — implementor's call, recorded in its report.

**Ownership:** the three sites are read-only consumers of `numerics.bbus.p_shift`; whether the fix
is three inline edits or one shared helper (`numerics.bbus` gaining a `flow_from_ptdf(ptdf,
injection, arr)` function all three call) is the one open design question — lean shared helper,
since a formula proven wrong once in three places is exactly ADR-008's "unify before it drifts a
fourth time" pattern, but this is a bugfix task and a new public primitive is a design decision, so
ask before adding one.

## Tasks

| id | intent | rigor | description | status |
|---|---|---|---|---|
| T1 | bugfix | audited | fix `dc_opf.py`'s flow-limit row constant | pending |
| T2 | bugfix | audited | fix `opf/__init__.py`'s derived flow (or extract a shared helper T1/T2/T3 call) | pending |
| T3 | bugfix | audited | fix `market/_clearing.py`'s derived flow | pending |
| T4 | bugfix | audited | shifter fixture; tests: dc_opf rows, solve_dc_opf flows, nodal/agents flows — each vs `pf.solve_dc` and PyPSA `lpf()` | pending |
| T5 | build | audited | M8's four `formats.md` limitations sections + `opf.md`'s shifter note, corrected now that the defect is fixed | pending |

## Handoff

Awaiting Step-1 confirmation (compressed with Step 2 above, per bugfix convention) before Step 4
dispatch.
