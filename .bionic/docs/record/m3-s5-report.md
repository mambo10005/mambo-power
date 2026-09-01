# M3 S5 — ac-check (FeasibilityReport), completed by the orchestrator

Slice S5 was dispatched as agent `m3-s5-ac-check` (standard, implementor). It finished the
actual implementation — code green, tested, lint/type-clean — but went idle without sending a
completion message, committing, or writing this report. Per the non-response procedure (writing
agents are never resumed — examine the output directly, take over, stand it down), I verified
its work independently and landed it as-is, no changes made to the code it left behind.

## What was found (uncommitted working-tree state)

`git status --porcelain` in the worktree showed exactly the files S5's brief described, nothing
else attributable to it: `src/mambo_power/opf/__init__.py`, `src/mambo_power/opf/dc_opf.py`,
`src/mambo_power/results/__init__.py`, `src/mambo_power/results/feasibility.py` modified,
`tests/unit/test_opf_solve_dc_opf.py` extended, `tests/unit/test_feasibility.py` new. Its own
progress file (`.bionic/tmp/m3-s5-progress.md`) was stale — last entry said "designing test
networks... about to write RED tests" — well behind the actual diff, which had tests written and
passing. The progress note was simply not kept current; the work itself was complete.

## What it built

`results/feasibility.py:feasibility_report(ac: AcPowerFlowResult, net: Network) ->
FeasibilityReport` — thermal violations from `BranchResult.loading_pct > 100%` (an unrated
branch, `loading_pct is None`, never contributes one — "unmeasurable" is not "violating"),
voltage violations from `Bus.v_min_pu`/`v_max_pu` against the solved `vm_pu` (a bus with neither
bound set never contributes one). `converged`/`message` pass through from `ac` unchanged, never
recomputed.

`opf/__init__.py:solve_dc_opf` wires it in behind a new `OpfDcOptions.ac_check: bool = False`
field: when true and the LP/QP solves to `"Optimal"`, a `net.model_copy(deep=True)` gets its
in-service generators' `p_mw` overwritten from the dispatch (id-keyed), `pf.solve_ac` re-solves
that copy, and `OpfDcResult.ac_check` is populated from both — report, no re-dispatch attempted
on failure, matching the wave spec's W6.

## Verification (done independently by the orchestrator, not by the agent)

```
$ uv run --no-sync pytest -q -p no:cacheprovider tests/unit/test_feasibility.py tests/unit/test_opf_solve_dc_opf.py
13 passed in 16.79s
$ uv run --no-sync ruff check .
All checks passed!
$ uv run --no-sync ruff format --check .
118 files already formatted
$ uv run --no-sync mypy
Success: no issues found in 39 source files
```

Full-repo suite was not clean-run at commit time — S3 (`m3-s3-pwl`) was concurrently mid-TDD in
the same shared worktree, with a genuinely, expectedly RED test file
(`tests/unit/test_opf_dc_pwl.py`, importing `NonConvexCostError` before S3 has added it) and an
in-progress edit to `dc_opf.py` (visible as a `.tmp` file mid-write). That RED is S3's own slice,
not a defect in S5's work — confirmed by diffing `dc_opf.py`'s and `opf/__init__.py`'s actual
staged content, which contains only `OpfDcOptions.ac_check` and the `ac_check` wiring, nothing
PWL-related. S5's own two test files run clean in isolation (above) and were the only files it
touched.

## AC-7 evidence

- Hand-built network with a rated branch under a dispatch producing a thermal overload:
  `FeasibilityReport.thermal_violations` catches it (branch id, correct `loading_pct`).
- Hand-built network with a voltage bound violated post-dispatch: caught in `voltage_violations`.
- A clean case (within limits): both lists empty.
- `FeasibilityReport.converged` asserted equal to `solve_ac`'s own convergence flag on the same
  dispatched network (passed through, not independently recomputed).

Exact hand-built test networks are in `tests/unit/test_feasibility.py` and the `ac_check=True`
additions to `tests/unit/test_opf_solve_dc_opf.py` — not reproduced here; read them directly.

## Commit

`9d317ee` on `wave/03-opf-n1` (on top of S2's `d6d3ef5`), pushed. Staged only the 6 files listed
above, by exact path — confirmed nothing of S3's in-progress, untracked work
(`test_opf_dc_case14_pwl.py`, `test_opf_dc_pwl.py`, `test_opf_pwl_guard.py`, the `dc_opf.py.tmp`
scratch file) was swept in.

## Not done by this report

The agent's own accounting of *why* it went idle mid-slice is unknown and not investigated
further — the evidence-first check found complete, correct, tested work, so there was nothing to
diagnose beyond "the report never got written." No attempt was made to resume the same agent
(writing agents are never resumed); it is left idle rather than force-stopped, per this session's
open `stop-guard.sh` Windows-path bug (see memory `dispatch-preflight-windows-path-bug.md`) —
stopping it would need fighting a known false "FOREIGN" refusal for no operational benefit, since
it has nothing further to report and its work is already safely landed.
