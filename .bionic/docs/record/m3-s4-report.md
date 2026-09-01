# M3 S4 report — contingency: LODF screen + DC re-solve confirm + brute-force agreement

Slice S4 of wave M3 (opf-n1). Worktree `C:\Claude Projects\mambo-power-m3`, branch
`wave/03-opf-n1` (base `2b31307`, S1's commit). Delivers W5: the N-1 branch-contingency screen
(`contingency.n1`), the behavioral half of AC-4, and AC-6 in full.

## What was built

- **`src/mambo_power/contingency/n1.py`** (array-level split, mirroring `pf.ac_newton`/`pf.dc`):
  - `N1Options` — empty pydantic model, reserved for future knobs.
  - `N1Screen` (frozen dataclass) — `screen_n1(arr, options) -> N1Screen`: for every non-bridge
    branch outage `k` (`numerics.bridges` skips the rest, same rule `_brute_force_lodf.py`
    uses), estimates every other branch's post-outage flow as `|base_flow_signed +
    lodf[:, k] * base_flow_signed[k]|` and flags `k` if any estimate exceeds that branch's
    `rating_mva`.
  - `confirm_n1(net, arr, screen) -> list[N1OutageResult]`: for each flagged outage, rebuilds
    the network with that branch out of service (deep-copy-once/flip/rebuild/restore, exactly
    `_brute_force_lodf.py`'s pattern) and runs a real `pf.dc.solve`, recording both the
    LODF-estimated and the DC-re-solve-confirmed flow for every flagged branch.
- **`src/mambo_power/contingency/__init__.py`**: the public, network-level `n1(net, options) ->
  N1Result` — builds `NetworkArrays`, calls `screen_n1` then `confirm_n1`, stamps
  `ResultProvenance` (`kind="n1"`, `solver=pf.dc.SOLVER`).
- **`src/mambo_power/results/n1.py`**: `N1BranchFlag`, `N1OutageResult`, `N1Result` — placed in
  `results/`, not siloed in `contingency/`, because the wave spec's own ownership table names
  `results.N1Result` as the type `contingency.n1` produces and `jobs`' `n1` kind (S6) will
  consume, the same reasoning that put `FeasibilityReport` in `results/`. Wired into
  `results/__init__.py`'s exports (a genuinely shared, concurrently-edited file — see
  "Shared-worktree note" below).
- **`tests/_brute_force_n1.py`**: the AC-6 oracle — generalizes `_brute_force_lodf.py`'s
  deep-copy-once/flip/rebuild shape from "outage → PTDF diff" to "outage → DC re-solve → limit
  check," per spec Design item 5. No LODF involved at all; every non-bridge outage gets a real
  re-solve.

### A note on the module-name/function-name overlap

`contingency/n1.py` (submodule, array-level `screen_n1`/`confirm_n1`) and `contingency.n1`
(package-level, the public network-level function) deliberately share a name — the wave spec's
own Design item 5 names both that way. After `contingency/__init__.py` finishes executing,
`mambo_power.contingency.n1` is the function (the `def n1(...)` at the end of the file rebinds
the package attribute that importing the submodule set); code that wants the submodule imports
it directly (`from mambo_power.contingency.n1 import screen_n1`), which this package's own
`__init__.py` does. Verified this resolves as expected — documented inline in `__init__.py` so
a future reader isn't surprised by it.

## Bugs found and fixed during RED → GREEN

1. **LODF formula sign bug.** The LODF re-composition formula (`post[l] = pre[l] + LODF[l, k] *
   pre[k]`) needs the *signed* pre-outage flow; an early draft fed in `np.abs(p_from_pu)`
   before applying the formula, which silently flips the estimate's sign on any branch whose
   declared from/to direction opposes its actual flow direction. Caught immediately by the
   hand-built triangle-network unit test (`test_screen_n1_flags_the_direct_branch_when_either_
   indirect_leg_is_outaged`): only one of two physically-symmetric outages was flagged. Fixed
   by keeping the flow signed through the formula and taking the absolute value only of the
   final estimate.
2. **Per-outage deep copy.** An early `confirm_n1` called `net.model_copy(deep=True)` inside the
   per-outage loop instead of once up front. Measured cost on case300: ~18.6s combined
   screen+confirm for 293 confirmed outages vs. ~4.0s after fixing it to deep-copy once and
   flip/restore `in_service` on that one copy (the `_brute_force_lodf.py` pattern the task
   brief named) — roughly 20x. Both bugs are root-caused in the plan.md AC-4/AC-6 evidence
   blocks, not just patched silently.

## AC-4 (behavioral half)

S1 delivered the fixture half (`tests/_rated.py`, the rating-derivation helper). S4's job:
prove a *real DC re-solve* — not just the LODF estimate — confirms a genuine N-1 violation on
real multi-bus data.

`tests/unit/test_contingency_n1.py::test_ac4_behavioral_case14_has_a_confirmed_n1_violation` —
1 passed. `contingency.n1` on `tests._rated.rated_network(case14)` confirms **18 outages / 86
outage-branch pairs**, every single one DC-re-solve-confirmed (not just screened).

This is close to but not identical to S1's own screen-only sanity-sweep numbers (17 outages /
81 pairs) — root-caused, not just noted: S1's uncommitted `probe_margin.py` fed the *unsigned*
base-case flow into the LODF formula (the same bug named above); reproducing that unsigned
version against case14 by hand gives exactly 17/81, confirming it as the cause. This did not
affect S1's margin choice or its own AC-4 evidence (both only needed "violations exist"), and
`probe_margin.py` was never committed, so nothing there needs fixing. AC-6 (below) is the actual
proof that the corrected, signed formula is right.

## AC-6 (brute-force agreement)

`tests/unit/test_contingency_n1_brute_force.py` — 5 passed (all parametrized over case14,
case_ieee30, case57, case118, case300; the wave's own 5-fixture OPF set, not `tests._fixtures.
FIXTURES`, which also carries `case30`). On every fixture, the confirmed-violating outage set
from `contingency.n1` (screen-then-confirm) equals the confirmed-violating set from
`tests._brute_force_n1.brute_force_n1` (full re-solve, no LODF pre-filter) **exactly**:

| fixture | confirmed-violating outages | screen+confirm | brute force |
|---|---|---|---|
| case14 | 18 | ~0.13s | ~0.11-0.15s |
| case_ieee30 | 34 | ~0.24-0.33s | ~0.26-0.36s |
| case57 | 75 | ~0.66-2.7s | ~0.57-1.6s |
| case118 | 166 | ~2.5-5.9s | ~2.3-2.9s |
| case300 | 293 | ~10-19s | ~4.8-8.3s |

**Agreement held on every one of the five fixtures** — the screen-then-confirm pipeline misses
no confirmed violation the brute force would catch, and confirms nothing the brute force would
not.

### Timing

Ranges above reflect real variance across repeated runs in this session, run concurrently with
another agent's own CPU-heavy work in the same shared machine (not just the same worktree —
both agents run tests on the same physical CPU). Isolated (bare script, no pytest, no sibling
contention), case300 alone: `screen_n1` 0.06s + `confirm_n1` 3.96s (293 re-solves, after the
deep-copy-once fix) + `brute_force_n1` 1.63s ≈ **5.6s total** — comfortably inside M1's ~10s
unit/parity tier-crossing threshold and consistent with research §4's bare-script estimate.
Under contention, the case300 pytest parametrize case (screen+confirm and brute_force both run
inside one test function) sometimes summed past 10s. Kept in the unit tier per the wave spec's
own framing ("likely staying in the unit tier... reconfirm once the real test exists") — the
contention-free number is clearly under threshold and the slowdown is external (a sibling
agent's own tests on the same machine), not a property of this test. Flagging this as
information per the task brief, not treating it as an automatic tier-move.

## RED → GREEN evidence

RED: `tests/unit/test_contingency_n1.py` and `tests/unit/test_contingency_n1_brute_force.py`
written first, against a `mambo_power.contingency` package that did not yet exist —
`ModuleNotFoundError: No module named 'mambo_power.contingency'` on collection of both files.

GREEN (after the two bugs above were found and fixed):
- `uv run --no-sync pytest -q tests/unit/test_contingency_n1.py` — 9 passed.
- `uv run --no-sync pytest -q -s tests/unit/test_contingency_n1_brute_force.py` — 5 passed.

## Verification

- `uv run --no-sync pytest -q -m unit` — 368 passed (includes S2/S3's concurrent `opf` work,
  already landed in the shared worktree at commit time).
- `uv run --no-sync pytest -q` (full suite, all tiers) — **524 passed**, 220.73s, 10
  pre-existing pandapower deprecation/divide warnings unrelated to this change.
- `ruff check` / `ruff format --check` on this slice's files: all clean.
- `mypy` (project config, `files = ["src"]`): no issues in this slice's files. (One pre-existing
  error in `src/mambo_power/opf/dc_opf.py:175`, `Call to untyped function "Highs" in typed
  context` — S2/S3's concurrent, not-yet-committed work, not touched here.)

## Files touched (exactly these, staged individually)

- `src/mambo_power/contingency/__init__.py` (new)
- `src/mambo_power/contingency/n1.py` (new)
- `src/mambo_power/results/n1.py` (new)
- `src/mambo_power/results/__init__.py` (modified — see shared-worktree note below)
- `tests/_brute_force_n1.py` (new)
- `tests/unit/test_contingency_n1.py` (new)
- `tests/unit/test_contingency_n1_brute_force.py` (new)

Also updated (via the `.bionic` junction, not part of the code commit, gitignored):
plan.md's AC-4 (S4 addendum, appended without disturbing S1's own block) and AC-6 evidence
blocks — both include the two root-caused discrepancies above rather than glossing over them.

### Shared-worktree note: `results/__init__.py`

This file turned out to be genuinely shared — S2/S3's concurrent work (`results/feasibility.py`,
`results/opf.py`) also registers its exports there, unlike the "entirely different files"
framing in the dispatch brief. Rather than `git add`-ing the whole file (which would have
pulled S2/S3's still-uncommitted, not-yet-tested additions into this commit), I staged only my
own three-line addition (the `results.n1` import and its three `__all__` entries) as a separate
git blob via `git hash-object`/`git update-index --cacheinfo`, verified with `git diff --cached`
before committing, leaving the merged working-tree file (mine + S2/S3's) untouched on disk for
them to commit their own half from later. Flagged to `m3-s2-opf-core` via message before editing.

## Commit

`feat(m3/S4): contingency — LODF screen + DC re-solve confirm + brute-force agreement` —
`3c84504`, pushed to `wave/03-opf-n1` (fast-forward from S1's `2b31307`; origin had not moved,
so no rebase was actually needed despite checking).

## Carry-forward notes for S6 (jobs)

- `contingency.n1(net, options: N1Options | None = None) -> N1Result` is the entry point S6's
  `n1` `KindSpec` should call; `N1Options` is currently empty (JSON round-trips to `{}`), so the
  jobs options model for this kind can start minimal.
- `N1Result` lives in `results/`, importable as `mambo_power.results.N1Result` — no need to
  import `contingency` just for the type.
- Not touched, per the task's explicit scope: `opf/`, `tests/_rated.py`,
  `fixtures/matpower/derived/case14_pwl.m`, `jobs/`, `docs/`. Generator-outage contingencies
  remain out of scope (branch outages only), not added.
