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
walk: exempt
design-interview: true
model_plan:
  orchestrator: fable-5
  senior-implementor: opus
  auditor: opus
  critic: opus
---

# Task — case30 redispatch/zonal LMP-dual degeneracy in CI

## SDLC State

integration-branch: epic/01-foundation
intent: bugfix
rigor: audited
scale: task
current: T2

- T0: prereqs: ok; configured 2026-08-31; base 059e533 (1539 passed / 4 skipped locally on
  Windows). Discovered on the first CI run since M7's cdb4fef (74 commits, M8 + shifter-fix).

## Scope (Step 1, compressed for bugfix — diagnosis precedes any fix decision)

**What happened.** Pushing `epic/01-foundation` (`059e533`) surfaced two CI failures on
`ubuntu-latest` py3.11 and py3.12 only (macOS, Windows, ubuntu py3.13 all green):
- `tests/unit/test_market_zonal.py::test_ac4_final_lmps_equal_the_nodal_lmps_on_case30` — LMPs at
  bus indices [2] and [29] read 2.920348 where the reference reads 3.938303 (both indices carry the
  *same* value on each side — i.e. both solutions tie those two buses' LMPs to each other, but at
  two different tied values).
- `tests/unit/test_opf_redispatch.py::test_d1_theorem_...[case30]` — `duals.flow_limit` at row
  indices [10]/[13] swap: one reads 0.0 where the other reads −1.0179460410655443, and vice versa.
  `dispatch_mw`, `demand_dispatch_mw`, `objective_cost`, `welfare`, `duals.balance` all pass — only
  the flow-limit dual and the LMPs derived from it disagree.

**Ruled out, with evidence:**
- **Not caused by this session's work.** A throwaway branch pushed at `cdb4fef` (M7's close,
  before M8 or the shifter-fix task ever touched `opf/redispatch.py`) reproduces the *same two
  tests* failing — but on `windows-latest` instead, with ubuntu green. Same tolerance
  (`CASE30_LMP_ATOL = 1e-3`, `DUAL_TOL = 1e-3`), same ~1.02 magnitude. The platform that fails
  flips between runs; the defect does not.
- **Not a dependency drift.** `highspy` is hash-pinned to `1.15.1` in `uv.lock` and untouched since
  M2.
- **Not a floating-point reordering from the shifter-fix.** `opf/redispatch.py`'s T7 change adds
  `p_shift_mw` (an exact-zero array on every fixture without a phase shifter, case30 included)
  into a sum before a PTDF matmul; IEEE-754 guarantees `x + 0.0 == x` bit-for-bit, so this cannot
  perturb the LP's coefficients on case30. (Confirmed by the `cdb4fef` reproduction predating the
  change entirely, independent of this argument.)

**Working hypothesis, from the module's own docstring** (`test_market_zonal.py:30-43`): this is the
same *primal-degenerate, dual-non-unique* class ADR-009 already documented for case300 ("seven
branches at rating, five priced... two optimal solves legitimately pick different active sets and
their LMPs differ... while the primal agrees to 1e-8"), now showing up on case30's *redispatch*
stage specifically (not the plain nodal solve — `nodal.duals` isn't what's compared against itself,
`solution.duals` vs `nodal.duals` are two *different* LPs' duals compared to each other). **Not yet
proven** — diagnose before deciding the fix shape.

**Prior art already in the file, both directions rejected on evidence:**
- A tolerance widen: rejected by ADR-009 itself ("would admit real regressions to hide a known
  degeneracy").
- A `priced ⊆ at_rating` check: tried in this exact module, removed (audit F2) because it is
  complementary slackness computed from one solve's own rows — every optimal solve passes it
  trivially, vacuous by construction.
- `_at_rating_branch_indices` (`test_market_zonal.py:580`) already exists as a helper — read what
  it's used for now before building anything new.

**Not doing:** touching `pf.dc`, `dc_opf`'s formulation, or anything the shifter-fix or M8 touched
unless the diagnosis proves one of them is implicated (ruled out above, but the implementor should
re-verify rather than trust this scope note alone). No blanket tolerance change anywhere else.

## Tasks

| id | intent | rigor | description | status |
|---|---|---|---|---|
| T1 | bugfix | audited | **Diagnose only — no fix yet.** Confirm or refute primal degeneracy on case30's redispatch optimum: are two or more flow-limit rows simultaneously at (or within solver tolerance of) their rating at the point in question? Does perturbing the LP's tie-breaking (e.g. a microscopic cost perturbation on one generator, or forcing HiGHS's simplex vs IPM) reproduce BOTH observed dual vectors on the same machine, proving both are legitimate optima? Confirm the primal (`dispatch_mw`, `welfare`, `objective_cost`) truly agrees to a tight tolerance across whichever dual vertex is chosen. Report with hard numbers before any fix is written. | pending |
| T2 | bugfix/refactor | audited | Once T1 reports, design and implement the actual discriminating check (shape TBD by T1's findings — not a tolerance widen, not `priced ⊆ at_rating`) for both failing tests, or a documented reason case30 should be replaced by a non-degenerate fixture for these two assertions. Regression: full suite; specifically re-verify the tests still catch a real dual bug (sabotage: perturb a rating and confirm redness). | pending |
| T3 | build | audited | Push a probe branch, confirm CI green on all matrix cells; merge to `epic/01-foundation`; document the finding in `docs/design/decisions.md` if it rises to ADR significance (extending ADR-009's own case300 finding to case30 — likely yes, momentous enough: this ships in M9's release CI). | pending |


## T1 diagnosis (2026-08-31, `case30-t1-diagnosis.md`)

**Verdict: genuine LP/QP dual degeneracy, proven algebraically, not a correctness bug — for the
redispatch D1 test.** Windows never flipped the tie in 25 fresh-process reruns. Bus-9
(`arr.bus_ids[8]`) carries zero net injection — no generator, load or shunt — sitting between
`branch-11` (row 10, bus-6→bus-9) and `branch-14` (row 13, bus-9→bus-10); both branches sit exactly
at rating (overloads 1.8e-15/2.7e-15 MW). PTDF rows 10 and 13, restricted to every column any
decision variable touches, are identical to 1.2e-17 (they differ only on bus-9's own column, by
exactly 1.0 — the PTDF self-column identity, which nothing multiplies). The active-set matrix
`{0,10,11,13,19,25}` restricted to those columns has rank 4, not 6 — a real 2-D null space
concentrated in rows {10,11,13}. Four independent solves (nodal + three redispatch starts) and 24
microscopic cost perturbations (±1e-9/±1e-7 on each generator) all landed on the same vertex
(row 13 only) on Windows — the primal is essentially rigid, exactly ADR-009's case300 signature,
but the tie-break's *other* vertex was never visited on this machine. **A full scan found 19
branch pairs total in case30 with exactly-redundant PTDF rows** — this fixture is riddled with
zero-injection radial topology, not a one-off.

For the LMP-tie test (bus-2/bus-29): the {10,11,13} redundancy is ruled out (its null-space
directions dot to ~0 against bus-2's and bus-29's PTDF columns — reallocating that dual mass cannot
move either bus's LMP). A second candidate family exists (rows 36/37/38, the bus-25→…→30 radial
tail terminating at bus-30, adjacent to bus-29) but wasn't confirmed active on Windows. **Same
class, not conclusively pinned to the exact mechanism** — the one experiment left undone needs
either the CI run's own dual vector or a Linux solve.

**The test author's own commit** (`f1782e8`, M6/S5) shows they knew case300 was degenerate and
believed case30 was not — the 1e-3 tolerance was sized against one measured run (8.92e-6 agreement,
100x headroom) for ordinary float noise, never against a real vertex swap (~1.02, three orders
bigger). **Blind luck, not deliberate headroom.**

**Design implication for T2**: the fix shape T1's own tooling makes obvious — a general
PTDF-column-redundancy detector (already built and validated against all 19 pairs) that both tests'
dual/LMP comparisons should *quotient by*: assert equality up to the known degenerate equivalence
classes (aggregate dual mass conserved within a redundant group; individual attribution within the
group not asserted), not simple point-wise equality. This generalizes ADR-009's own resolution
rather than special-casing case30, and stays sabotage-resistant — a real bug moving mass *out* of a
redundant group, or getting the aggregate wrong, still fails.


## T2 fix (2026-08-31, `ab2a89f`, `case30-t2-report.md`)

**`tests/_degeneracy.py`** (new, shared by both test files): `ptdf_redundant_groups` clusters
branch-flow rows that are *proportional* — not just equal — restricted to decision-variable
columns, generalizing T1's exact-tie finding (row 11 turns out to be in the same rank-1 cluster as
T1's {10,13}, at weight 0.5714 — implied by T1's "2D null space concentrated in {10,11,13}" but not
spelled out as weighted). A group's KKT invariant is the **weighted** sum (reduces to a plain sum
at weight 1, an exact tie); rows that are the zero vector on decision columns get no invariant at
all — dual-feasible at any value, nothing to assert. D1's `flow_limit` and the LMP test both now
compare point-wise outside redundant groups, weighted-group-sum inside them; the LMP test adds an
independent structural-tie check (PTDF identical across *every* row, not just decision ones) for the
bus-9/bus-11 radial pendant pair.

**T1's own open gap closed, algebraically, no Linux needed.** T1 ruled out {10,11,13} for the
LMP-tie failure by dotting its null space against `arr.bus_ids[2]`/`[29]` — **array-index** order.
The failing assertion sorts by `sorted(final)` — **bus-id lexical** order — so position 2 is bus-11,
position 29 is bus-9, not the buses T1 checked. Confirmed directly: PTDF is identical for bus-9 and
bus-11 across all 41 rows (a plain radial identity), tied at two different shared values 8.9e-6
apart on Windows's own "good" vertex — the *same* mechanism as the D1 swap, not a second one.

**A bug in its own first draft, caught before shipping.** Pooling every redundant group into one
combined least-squares fit let an unrelated defect on one group's bus inflate every other group's
residual, masking real defects — found by the sabotage sweep, fixed by fitting each group
separately against only its own buses.

**Sabotage, 6/6, against the exact CI-reported failure shapes**: D1's row-10↔13 swap and the LMP
test's bus-9/bus-11 shift (2.920348→3.938303, the CI run's own numbers) both reproduce the original
bug and are correctly rejected by the new checks (accepted as legitimate by the old point-wise
ones, which is the CI failure); an unrelated row/bus, a redundant group's own aggregate, and the
structural tie itself (bus-11 moving without bus-9) are all correctly rejected too.

**case14 carries one dormant redundant group** (every row measured exactly zero on all three
solves) — quotienting is provably lossless there; noted in the test's own docstring.

**Regression**: `tests/unit` 1242 passed, `tests/parity` 292 passed / 4 skipped; both target tests
individually green; case300's shared helper imported, not duplicated, unchanged in behavior; 25/25
Windows repro (confirms stability, not discriminating power — the sabotage proofs are that).
Orchestrator-verified independently: 45/45 in `test_market_zonal.py` + the two originally-failing
tests. Named sweep dispatched at `ab2a89f`.

## Handoff

T1 dispatched first, alone, with an explicit stop-before-fixing instruction. The orchestrator
decides T2's shape from T1's actual numbers, not from this plan's hypothesis.
