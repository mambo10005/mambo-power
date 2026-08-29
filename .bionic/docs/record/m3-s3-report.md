# M3 S3 — pwl (completed by the orchestrator)

Slice S3 was dispatched as agent `m3-s3-pwl` (standard, implementor). Like S5 before it, it
finished the actual implementation — code green, tested, lint/type-clean, and per its own
progress notes had reached "wait for/coordinate with S5's commit before committing" — but went
idle without sending a completion message, committing, or writing this report. Per the
non-response procedure, I verified its work independently and landed it as-is, no changes made
to the code it left behind.

## What was found (uncommitted working-tree state)

`git status --porcelain` showed exactly what S3's own progress file (`.bionic/tmp/
m3-s3-progress.md`) described having finished: `src/mambo_power/opf/__init__.py`,
`src/mambo_power/opf/dc_opf.py`, `tests/unit/test_opf_solve_dc_opf.py` modified;
`tests/unit/test_opf_dc_pwl.py`, `tests/unit/test_opf_pwl_guard.py`,
`tests/unit/test_opf_dc_case14_pwl.py` new. Local HEAD in the shared worktree was already at
S5's commit (`9d317ee`) — since S3 and S5 shared one physical working directory, S3 never
needed a separate `git pull` to see S5's landed work; it was already composed into the same
files S3 was mid-editing, as its own progress note observed ("edits are disjoint ... composed
cleanly with no manual merge needed").

## What it built

`opf/dc_opf.py`: `NonConvexCostError` and `_convex_pwl_segments` (epigraph slope/intercept row
construction, raised before any `highspy.Highs()` object is built when a `PiecewiseCost`'s
breakpoint slopes are not non-decreasing — fail fast, never a silently-wrong LP answer). `dc_opf()`
gained an optional `pwl_costs` parameter: new free `cost_g` columns plus one epigraph inequality
row per cost segment, appended after the existing balance/flow-limit row structure — the
existing `dispatch_mw`/`gen_bound` slicing narrowed to `[:n_gen]` and `flow_limit` to
`[1:n_rows]` so the new rows don't leak into code that assumed the old row layout.

`opf/__init__.py`: `_cost_coeffs` now returns `(coeffs, pwl_costs)` instead of raising
`NotImplementedError` for a `PiecewiseCost` generator (replacing the seam S2 explicitly left for
this slice); `solve_dc_opf` passes `pwl_costs` through; `NonConvexCostError` re-exported from
`opf`.

## Oracle finding (AC-5, resolves spec Assumption b)

Pandapower's `create_pwl_cost` + `rundcopp` genuinely honours piecewise-linear costs — S3
verified this on a hand-built 2-bus network against the exact hand-computed optimum before
trusting it. But pandapower's own `make_objective._init_gencost` refuses to mix quadratic and
piecewise-linear costs **anywhere in the same network** (a network-wide check, not
per-generator) — confirmed directly against `case14_pwl.m` itself, which (correctly, per S1's
design) keeps case14's real nonzero quadratic coefficients on generators 1/4/5 alongside the new
PWL generators 2/3. So pandapower cannot serve as this fixture's oracle, and S3 fell back to the
spec's own documented alternative (Assumption b): an independent lambda-iteration
economic-dispatch solver sharing no code with `dc_opf`/HiGHS, exploiting that `case14` (and
`case14_pwl`, a gencost-only edit) has zero rated branches — so DC-OPF collapses to classic
equal-marginal-cost economic dispatch, solvable independently by iterating on the system
marginal price.

**A genuine LP degeneracy was found and handled honestly, not smoothed over**: two of the
hand-picked PWL breakpoints (S1's derived fixture) tie in marginal cost — gen-2's third segment
slope equals gen-3's second segment slope, both below generators 4/5's flat marginal cost — so
the LP has multiple optima for how gen-2/gen-3 split roughly 22.8 MW between them. S3's test
asserts that split as an interval, not a false-precise exact number, while the three strictly
convex generators and the total system cost (`6239.0` exactly) are uniquely pinned and asserted
exactly. This is the right way to test a degenerate LP — asserting a specific split would have
been either wrong or lucky, both bad.

## Verification (done independently by the orchestrator)

```
$ uv run --no-sync pytest -q -p no:cacheprovider tests/unit/test_opf_dc_pwl.py \
    tests/unit/test_opf_pwl_guard.py tests/unit/test_opf_dc_case14_pwl.py \
    tests/unit/test_opf_solve_dc_opf.py tests/unit/test_feasibility.py
26 passed in 21.58s
$ uv run --no-sync ruff check .
All checks passed!
$ uv run --no-sync ruff format --check .
121 files already formatted
$ uv run --no-sync mypy
Success: no issues found in 39 source files
```

Full-repo suite launched in background at commit time; result to be confirmed and appended to
the Step 5 tests floor rather than re-verified here (S5's equivalent full-suite run, taken
under the same shared-worktree conditions, showed 554/556 with the only 2 failures being S3's
own then-in-progress RED tests — now resolved by this commit).

## AC-5 evidence

- `case14_pwl.m` (S1's derived fixture) solved end-to-end via `opf.solve_dc_opf`; dispatch
  matches the independent lambda-iteration oracle exactly on the three uniquely-determined
  generators and on total cost; the two degenerate generators' split is asserted within the
  provably-optimal interval.
- A hand-built non-convex `PiecewiseCost` (decreasing-slope segment) raises `NonConvexCostError`
  before any solve is attempted.

Exact test networks and assertions are in `tests/unit/test_opf_dc_pwl.py`,
`tests/unit/test_opf_pwl_guard.py`, and `tests/unit/test_opf_dc_case14_pwl.py` — read them
directly rather than reproduced here.

## Commit

`8d2c4e6` on `wave/03-opf-n1` (on top of S5's `9d317ee`), pushed. Staged only the 6 files listed
above, by exact path.

## Not done by this report

Same note as S5's: why the agent went idle mid-handoff (immediately after finishing, per its own
progress note — "Next: full suite + ruff + mypy, then wait for/coordinate with S5's commit
before committing", which is exactly the state found) is not investigated further; the work
itself was complete and correct. Not force-stopped, per this session's open `stop-guard.sh`
Windows-path bug (see memory `dispatch-preflight-windows-path-bug.md`).
