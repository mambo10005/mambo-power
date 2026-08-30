---
governing-skill: superpowers:writing-plans
sdlc-step: 9
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

| T6 | bugfix | audited | fix `opf/multiperiod.py:485`'s per-period flow-row constant (fold in `p_shift_mw`) | **done** (`8a6fb11`; per-site sabotage: reverting T6 alone reddens only its own new tests) |
| T7 | bugfix | audited | fix `opf/redispatch.py:424`'s constant and `:550`'s `branch_flow_mw` (call `flow_from_ptdf` directly for the latter — full injection vector, same shape as T2/T3) | **done** (`eb771b1`; line 428's zonal-point term re-derived by hand and confirmed it needed no correction, left as is) |
| T8 | build | audited | regression tests for `multiperiod_dc_opf`/`redispatch_dc_opf`/`solve_zonal`/`solve_multiperiod` on the shifter fixture vs `pf.solve_dc`; restore `formats.md`'s caveat narrowly, then remove once T6/T7 land; re-run the named sweep, re-dispatch walk/audit/critic at the new head | **done** (`272d84c` 24 tests incl. the critic's exact two numbers reproduced then closed — 81.4 MW gap, false-Infeasible; `9e0cbb4` changelog names all five sites; `formats.md` needed no restoration — the orchestrator's own exhaustive grep and the agent's independent one agree: only the five now-fixed sites and `flow_from_ptdf`'s own definition remain. F1: `git status` showed 2 files uncommitted after the agent's own regression runs went unreported (unused import, two ruff-format lines) — same F8/F11 pattern a fourth time; orchestrator committed the trivial cleanup (`bd952cc`) and ran the sweep independently rather than waiting) |

**Re-review (`record/shifter-critic.md`, at `bd952cc`): merge-ready as-is; both blockers
closed.** Both original repros re-run and confirmed fixed: the 81.4 MW gap is now 1.8e-15; the
false `Infeasible` now returns `Optimal` matching `dc_opf`. `multiperiod.py`'s period-invariant
`p_shift_mw` hoist re-derived by hand (module docstring confirms static topology across periods —
cannot vary per period); `redispatch.py`'s two-part constant re-derived by hand from the full
identity — both match byte-for-byte, not "looks plausible." One nuance worth keeping: `git log` on
`formats.md` shows exactly one commit ever touched it (`6a7617f`, T5's deletion, predating T6/T7) —
there was a real window on this branch where the docs and code disagreed; nothing merged during it,
and the code caught up to the docs rather than the reverse, so it's closed, but "needed no
restoration" means the claim *became* true, not that it was never false. No new findings; `opf/zonal.py`
confirmed to build no PTDF/branch-flow rows at all (cannot mask or double-count); `flow_from_ptdf`
is not in any per-period loop (`multiperiod.py` never calls it; `redispatch.py` once, post-solve).
The one should-fix from the first review (infeasible-status-only test) stands, non-blocking.

**Re-audit (`record/shifter-audit.md`, at `bd952cc`): task verdict PASS, 8/8, 0 blocking, 1
should-fix (non-blocking, same lineage as the first pass's — harmless, its sibling test covers
it).** Own five-bus two-loop mesh, not the fix's fixtures. T6/T7 sabotaged alone each redden
exactly their own tests (2 and 8), zero overlap, T1–T5 unaffected. `market.solve_zonal`/
`solve_multiperiod` reproduced both of the critic's failure modes independently — confirmed live at
the pre-T6/T7 head `9e00ab5` (up to 107.2 MW gap, false `Infeasible`), confirmed gone at `bd952cc`
(0.0000 MW, `Optimal`). Exhaustive site search via four differently-shaped greps (not the plan's own
pattern); two non-obvious candidates (`market/agents.py`, `contingency/n1.py`) read in full and
cleared by reasoning, not grep-absence. **Self-correction recorded rather than hidden**: mid-audit
caught its own first pass reading the wrong `MarketZonalResult` field (`generators`, the zonal-stage
dispatch, instead of `generators_final`, what `branches[].p_from_mw` is actually sourced from) — a
combo that happened to leave the two stages coincidentally equal would have made the check vacuous;
re-ran with a combo provably forcing them to differ (g1: 100→50, g3: 0→50), held to <1e-6 MW.

## Verification

Regression check: full `tests/unit` 1228 passed (0 failed, 0 skipped — 10 new); full `tests/parity`
292 passed / 4 skipped (2 new PyPSA shifter tests; the 4 skips are pre-existing zonal fixed-load
skips, unchanged). Every pre-existing fixture has `shift_deg == 0` everywhere, so the fix is a
provable no-op on all of them. Gates at `6a7617f`: ruff check, ruff format (204 files), mypy (59
files), mkdocs --strict all clean. Named sweep at `6a7617f`, 2026-08-30 19:33Z: 1525 / 4, all gates clean (superseded — the critic
found two more sites at this head). **Named sweep at `bd952cc`, 2026-08-30 23:18Z — after T6–T8,
the task's figure of record: 1539 passed / 4 skipped in 778.25s** (+14 over `6a7617f`, +26 over the
1513 baseline), ruff check, ruff format (205 files), mypy (59 files), mkdocs --strict all clean. Log:
scratchpad `shifter-gate-bd952cc.log`. Re-dispatching the auditor and critic at this head, since T6–T8
changed the diff both reviewed.

## Steps 6-9

- **Step 6**: critic not-merge-ready (2 blocking, at `9e00ab5`) → extended T6-T8 → merge-ready
  as-is (re-review at `bd952cc`).
- **Step 7**: adr: n/a — a restoration to `pf.solve_dc`'s own already-correct model, no new
  decision beyond what this plan's Design section already states.
- **Step 8**: merge to `epic/01-foundation`, tag/commit below; worktree removed with `--force`
  (never `rm -rf` — M7 F20); `.bionic/tmp/shifter-*` preserved under `record/` before the wipe.
- **Step 9**: this task was M9's queued first item (M8's continuation carry 1) — closing it there
  rather than a separate continuation file; M9 Step 0 opens next on a checkout free of the defect.

## Handoff

**Shipped 2026-08-30.** Task head `bd952cc` (10 commits, T1–T8 plus two orchestrator commits), two
full review passes (critic found 2 more sites the first pass missed; both closed and re-confirmed).
Merges to `epic/01-foundation` next.
