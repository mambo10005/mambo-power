# M7 S4 — the fixed-point loop — progress

Commits: `74a0532` (the loop) and `67d189e` (F6, the amplitude ULP fix + `results/__init__.py`
export + seam docs). Report: `.bionic/docs/record/m7-s4-report.md`.

## Now running (both OFF-TREE, `git archive` overlays of `67d189e`)

1. **Overlay sabotage sweep**, 10 defects — replaces the two in-place sweeps at the
   orchestrator's request. Module resolution proved in-process by an out-of-tree
   `pytest_report_header`; preflight confirmed `PYTHONPATH` beats the venv's editable install.
2. **Overlay head gates** — `pytest`, `ruff check`, `ruff format --check`, `mypy`. Taken on the
   overlay rather than the worktree, which also removes S7's in-flight `jobs/registry.py` and
   `test_jobs.py` from the measurement rather than making me caveat them.

Loaded-module proof from the gate run:
`C:\...\m7s4-gate-1hjrg05z\overlay\src\mambo_power\__init__.py`.

## Incident, closed

My sweep's cost-source defect was live in the shared worktree for one ~85s test window and the
orchestrator caught it there. `opf/__init__.py` restored and verified byte-identical to HEAD
(`git diff --exit-code` 0; sha256 matches the HEAD blob). S7 released to re-take. **Rule adopted:
a sabotage sweep is a deliberate temporary corruption of shared state and runs on an overlay,
never the shared tree.**

## F6, fixed and committed

Amplitude vs `2*step` was decided by float noise: **+64 ULPs at step 0.1 (404 rounds), +19 at 0.7
(61 rounds), −42 at 0.3, exact at 0.5.** Steps 0.1, 0.2 and 0.7 reported a settled climb that
reached `[60.0, 60.0]` as a `cycle`. `_settled()` + `_AMPLITUDE_TIE_REL_TOL = 1e-9`, mirroring
S2's profit-tie fix. Test parametrized over nine steps. Power proof: plain `<=` reddens exactly
the non-representable ones.

The generalisation, which the orchestrator wants in the wave's lessons rather than only mine:
**a sabotage sweep tests the defects you thought of, at the parameters you happened to use.**
Eight defects at a binary-exact step could not have found this however many more were added.

## Remaining

Fill the report's sweep and gate tables from the overlay runs, note where the in-place and overlay
numbers agree, hand back.
