---
governing-skill: superpowers:writing-plans
sdlc-step: 5
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
current: T4

- T0: prereqs: ok; configured 2026-08-30 via "confirm"; model_plan=fable-5/sonnet/opus;
  integration-branch=epic/01-foundation; base e02feea. **Baseline on the clean main checkout at
  `1a2b31c`, before any agent entered the worktree: 1513 passed / 4 skipped in 250.48s**
  (scratchpad `shifter-baseline-1a2b31c.log`, 2026-08-30 19:02Z)

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
| T1 | bugfix | audited | fix `dc_opf.py`'s flow-limit row constant | **done** (`d085b0b`; hand-derived `const = pf_shift_mw − ptdf_matrix @ (fixed_bus_mw + p_shift_mw)`, since the LP-constant form doesn't fit the shared helper's signature; proven the same identity as `flow_from_ptdf` by a dedicated test) |
| T2 | bugfix | audited | fix `opf/__init__.py`'s derived flow (or extract a shared helper T1/T2/T3 call) | **done** (`b01062f` + `126749a`: `numerics.bbus.flow_from_ptdf` extracted per the design lean, T2 calls it directly) |
| T3 | bugfix | audited | fix `market/_clearing.py`'s derived flow | **done** (`126749a`, calls `flow_from_ptdf` directly) |
| T4 | bugfix | audited | shifter fixture; tests: dc_opf rows, solve_dc_opf flows, nodal/agents flows — each vs `pf.solve_dc` and PyPSA `lpf()` | **done** (`8bb2ece`; `tests/_shifter.py`, asymmetric −7°/+12° angles so a sign error can't hide; red 9/10 on the pre-fix checkout matching the diagnosis's magnitudes; per-site sabotage proved independence — orchestrator re-ran the two new test files: 12 passed) |
| T5 | build | audited | M8's four `formats.md` limitations sections + `opf.md`'s shifter note, corrected now that the defect is fixed | **done** (`6a7617f`; caveats removed, not softened — they were untrue; `opf.md`/`market.md` had no caveat to change; a "Fixed" changelog section ahead of the M8 wave entry, which stays as an accurate ship-time record) |

**Walk (`record/shifter-walk.md`, at `6a7617f`, 0 hits of `AC-[0-9]`): the fix holds.** Two
independent networks built from the docs' own model description (not the fix's own fixture) — a
4-bus ring with the shifter off any symmetry, and a 5-bus network with the shifter two/three hops
from the slack. `opf.solve_dc_opf`, `market.solve_nodal` and `market.solve_agents` all match
`pf.solve_dc` to floating-point precision (worst 4e-14 MW); KCL closes exactly at every bus;
network objects unmodified, no output on any of the four solve paths. Reconstructed the old bug by
hand — swept every feasible dispatch on the ring and showed the pre-fix formula's flow estimate on
one branch never drops below 29.09 MW while the true flow never exceeds 18.51 MW; a 25 MVA rating in
that gap returns `Optimal` under the fix, where the pre-fix code would have reported the false
`Infeasible` the changelog now warns about. One real, pre-existing finding, out of the task's scope
and fixed directly by the orchestrator (`9e00ab5`, docs only): `numerics.md`'s table names
`bbus.pf_shift`/`bbus.branch_susceptance`/`bbus.incidence` with a `bbus.`-prefix convention meaning
"lives in that module" that reads like a call path — `numerics.bbus` is itself the `bbus(arr)`
function (the package shadows the submodule name), so the literal call raises `AttributeError`; one
clarifying sentence added, no export widened. Minor friction, not fixed: `OpfBranchFlowResult`
carries only `p_from_mw`, no `p_to_mw`, undocumented as a difference from `BranchResult` — noted for
a future docs pass, not blocking.

**Audit (`record/shifter-audit.md`, at `6a7617f`): task verdict PASS, 8/8, 0 blocking.**
Re-derived the identity by hand from `pf/dc.py` and `numerics/ptdf.py`, not from the plan's
statement of it. Own fixtures throughout (never `tests/_shifter.py`): AC-1/AC-2/T3 each sabotaged
alone and each reddens exactly its own site's tests, none of the others; AC-3 built its own PyPSA
network via `io.pypsa.to_network`, `lpf()` agrees with `pf.solve_dc` to <1e-7 independently proving
PyPSA itself right, not just mambo; AC-4 confirmed by `git show` that the exact stale caveat is gone
from all four importer sections and nothing else stale remains (other shift mentions in
market/multiperiod/zonal docs are a different, legitimate topic). Revert-and-watch on
`flow_from_ptdf` reddens exactly T2+T3, T1 (which derived its own formula) stays green — the
claimed independence, confirmed. `p_shift(arr)` is the exact zero vector on `case14.m`. One
should-fix, non-blocking: `test_dc_opf_flow_limit_row_reports_infeasible_below_the_achievable_floor`
only checks `status == "Infeasible"`, not *why* — sabotaging T1 alone left it `Infeasible` for the
wrong reason, so AC-1 is discharged only because its sibling forced-redispatch test does catch T1;
this one test alone would not catch a future T1 regression. Carried forward, not blocking Step 6.

**Critic (`record/shifter-critic.md`, at `9e00ab5`): NOT merge-ready — 2 blocking.** (1)
`opf/multiperiod.py:485` and `opf/redispatch.py:424,428,550` carry their own independent copies of
the identical bug — never touched by T1–T5, neither module even imports `flow_from_ptdf`. Live
end-to-end: `market.solve_zonal`'s public `branches[].p_from_mw` comes straight from
`redispatch.py`'s buggy `branch_flow_mw` (measured 81.4 MW off `pf.solve_dc` at an `Optimal`
dispatch, where the already-fixed `flow_from_ptdf` matches to 1.8e-15 at the same point);
`market.solve_multiperiod` reproduces the exact false-`Infeasible` failure mode this task was
chartered to fix. (2) T5's `formats.md` deletions are now a false claim — the deleted caveat warned
generically about "opf / market results," which is still true for these two modules, so the shipped
docs assert phase shifters are safe everywhere they aren't. **Confirmed exhaustively by the
orchestrator**: `grep -rn "ptdf_matrix @\|ptdf @" src/` shows exactly these two files and nothing
else outside the five already-fixed sites — `opf/zonal.py` builds no branch-flow rows at all (per
ADR-009, copper-plate per zone), so nothing there to fix. Everything else the critic attacked held:
T1's LP constant re-derived independently from the row-construction code itself; two-shifter
superposition, a shifter at the slack bus, extreme angles (180°/720°/−540°), and
transformer-with-shift interaction all correct at the three sites already fixed; the performance
premise in the critic's brief didn't hold (`flow_from_ptdf` fires once per `solve_agents` call,
after the loop, not per round) — it said so rather than reporting a manufactured number. Extended
as T6–T8 below; Steps 4–6 re-run at the new head.

| T6 | bugfix | audited | fix `opf/multiperiod.py:485`'s per-period flow-row constant (fold in `p_shift_mw`) | pending |
| T7 | bugfix | audited | fix `opf/redispatch.py:424`'s constant and `:550`'s `branch_flow_mw` (call `flow_from_ptdf` directly for the latter — full injection vector, same shape as T2/T3) | pending |
| T8 | build | audited | regression tests for `multiperiod_dc_opf`/`redispatch_dc_opf`/`solve_zonal`/`solve_multiperiod` on the shifter fixture vs `pf.solve_dc`; restore `formats.md`'s caveat narrowly, then remove once T6/T7 land; re-run the named sweep, re-dispatch walk/audit/critic at the new head |

## Verification

Regression check: full `tests/unit` 1228 passed (0 failed, 0 skipped — 10 new); full `tests/parity`
292 passed / 4 skipped (2 new PyPSA shifter tests; the 4 skips are pre-existing zonal fixed-load
skips, unchanged). Every pre-existing fixture has `shift_deg == 0` everywhere, so the fix is a
provable no-op on all of them. Gates at `6a7617f`: ruff check, ruff format (204 files), mypy (59
files), mkdocs --strict all clean. **Named sweep at `6a7617f`, 2026-08-30 19:33Z — the task's figure of record: 1525 passed / 4
skipped in 1043.32s** (+12 over the 1513 baseline), ruff check, ruff format (204 files), mypy (59
files), mkdocs --strict all clean. Log: scratchpad `shifter-gate-6a7617f.log`. Independent walk and
audit dispatched at the same head — see below once they return.

## Handoff

Steps 4 (T1–T5) done, orchestrator-verified (commits carry source, own tests pass). Independent
walk, audit and named sweep dispatched at `6a7617f`. Awaiting their return before Step 6 (critic,
required by the audited floor even at task scale), Step 7 (ADR — likely `n/a`, a restoration has no
new decision to record beyond what the plan's Design section already states), Step 8 (merge to
`epic/01-foundation`, remove the worktree with `--force`), Step 9 (continuation note, folded into
the standing M8→M9 continuation since this was M9's queued first item).
