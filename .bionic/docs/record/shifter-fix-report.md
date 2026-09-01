# Task report -- the DC-OPF phase-shifter flow defect (M7 F1, M8 A19)

Worktree: `C:\Claude Projects\mambo-power-shifter`, branch `task/shifter-flow-fix`, based on
`1a2b31c` (docs Steps 0-2, confirmed). Five commits, in order:

| commit | subject | files changed |
|---|---|---|
| `b01062f` | feat(numerics): flow_from_ptdf shared helper (T1 groundwork) | `numerics/__init__.py` +3/-1, `numerics/bbus.py` +26 |
| `126749a` | fix(opf,market): wire flow_from_ptdf into the two full-injection sites (T2, T3) | `market/_clearing.py` +9/-4, `numerics/bbus.py` +6/-3, `opf/__init__.py` +9/-4 |
| `d085b0b` | fix(opf): fold p_shift into dc_opf's flow-limit row constant (T1) | `opf/dc_opf.py` +11/-4 |
| `8bb2ece` | test(shifter): fixture + red/green/sabotage-verified tests for the shift fix (T4) | `tests/_shifter.py` +96, `tests/parity/test_shifter_pf_vs_pypsa.py` +54, `tests/unit/test_shifter_flow_fix.py` +147 |
| `6a7617f` | docs(shifter): remove the now-fixed phase-shifter caveat; changelog entry (T5) | `docs/changelog.md` +20/-1, `docs/manual/formats.md` -18 |

No amend/rebase/reset used at any point; every commit adds on top of the last.

## The fix (T1, T2, T3)

Correct identity, matching `pf.solve_dc` exactly: `flow = PTDF @ (injection - p_shift) +
pf_shift`. Extracted as `numerics.bbus.flow_from_ptdf(ptdf, injection_mw, arr)`, exported from
`numerics/__init__.py` beside `p_shift`/`bf`/`bbus`.

- **T2** (`opf/__init__.py:206-210`, `solve_dc_opf`'s derived `branches[].p_from_mw`) and **T3**
  (`market/_clearing.py:100-115`, `market.solve_nodal`/`solve_agents`' derived branch flows)
  both build a full net-injection-per-bus vector already, so both now call
  `flow_from_ptdf(ptdf, injection_mw, arr)` directly -- their old `pf_shift` import was replaced
  with `flow_from_ptdf`.
- **T1** (`opf/dc_opf.py:927-933`, `dc_opf`'s own flow-limit row `const_k`) folds fixed
  contributions into a constant added to a linear combination of *decision variables*, not a
  product with one full injection vector, so it could not call the helper directly. Derived by
  hand from the same identity instead: `const = pf_shift_mw - ptdf_matrix @ (fixed_bus_mw +
  p_shift_mw)` (previously missing the `+ p_shift_mw` term). A test
  (`test_dc_opf_flow_limit_row_forces_a_true_physical_redispatch`,
  `test_dc_opf_flow_limit_row_reports_infeasible_below_the_achievable_floor`) constructs a
  network with only fixed injections plus a tight rating and confirms `dc_opf`'s LP keeps the
  dispatch within the *true* physical limit (an independent `pf.solve_dc` readback) -- this
  proves T1's hand-derived `const_k` is the same identity as `flow_from_ptdf`, per the plan's
  explicit ask.

## Fixture (T4)

No bundled MATPOWER case has a phase shifter, so `tests/_shifter.py` builds one:
`shifter_loop_network(shift_deg, *, t12_rating_mva=None)` -- a 3-bus loop (cheap gen `g1`@`b1`
slack, dear gen `g3`@`b3`, a 100 MW fixed load@`b2`, phase shifter `t12`: `b1`->`b2`), every
branch unrated by default so no flow-limit row binds and the fix's own tests isolate the
shift-formula bug from the rating logic entirely; `t12_rating_mva` overrides the shifter's
rating for the one test that deliberately binds it. Chose a standalone fixture file over
reusing `tests/parity/test_pypsa_export_vs_pypsa.py`'s existing `_shifter_mesh` (a 70 MVA-rated
loop with its own dispatch/cost shape) since that fixture is not generously rated by default and
belongs to a different test's own narrative; `dispatched_network(net, dispatch)` gives an
independent `pf.solve_dc` readback of any OPF/market dispatch (deep-copies `net`, overwrites
each generator's `p_mw` id-keyed).

Two asymmetric shift angles throughout, `-7` and `+12` degrees (deliberately not a symmetric
`+-5`, so a sign error that happens to cancel at a symmetric pair could not hide).

## Tests (T4) -- 12 new tests total

- `tests/unit/test_shifter_flow_fix.py` (10 tests): `solve_dc_opf`'s and `solve_nodal`'s derived
  branch flows vs `pf.solve_dc` (T2, T3, both angles); `dc_opf`'s own flow-limit row forces a
  true physical redispatch under a tight rating at -7 deg, and reports `Infeasible` below the
  achievable floor at +12 deg (T1 -- see below for why these two angles split that way); the KCL
  identity at the shifted bus (`b2`) for both solvers, both angles.
- `tests/parity/test_shifter_pf_vs_pypsa.py` (2 tests): PyPSA `lpf()` as a second, external
  oracle on the same fixture, agreeing with `pf.solve_dc` at both angles -- re-proves
  `io.pypsa`'s exporter is still correct on a shifted network, independent of any OPF/market
  solve.

### Red -> green

`git checkout 1a2b31c -- src/` (pre-fix source, test files untouched since they are new/untracked)
then `pytest -q tests/unit/test_shifter_flow_fix.py`:

```
9 failed, 1 passed in 1.13s
```

Failure magnitudes matched the diagnosed bug class -- e.g. the KCL identity read `222.17` and
`-109.44` against an expected `100.0` (off by 122/209 MW on this fixture's own numbers, the same
class of violation as the plan's ~87 MW measurement on its own fixture). Only
`test_dc_opf_flow_limit_row_reports_infeasible_below_the_achievable_floor` passed pre-fix too --
noted honestly: that particular case reports `Infeasible` under both the correct and the buggy
formula, so it is a correctness assertion, not a bug-sensitive regression test; its sibling
(`..._forces_a_true_physical_redispatch`) is the bug-sensitive one for that same angle's
direction, and it did redden.

`git checkout HEAD -- src/` (restore the fix) then re-run:

```
10 passed in 0.99s
```

### Sabotage, one site at a time (each restored via `git checkout HEAD -- <file>` before the next)

| site sabotaged | tests reddened | tests staying green |
|---|---|---|
| T1 (`dc_opf.py` const, restored the missing-`p_shift` bug) | `test_dc_opf_flow_limit_row_forces_a_true_physical_redispatch` only (a false `Infeasible` from the wrong row constant) | all other 9 |
| T2 (`opf/__init__.py` derived flow) | the 2 `solve_dc_opf`-flow tests + the `dc_opf`-solver KCL variant (2) = 4 | all other 6, including T1's and T3's own tests |
| T3 (`market/_clearing.py` derived flow) | the 2 `solve_nodal`-flow tests + the `nodal`-solver KCL variant (2) = 4 | all other 6, including T1's and T2's own tests |

Confirms the three tests are independent per site, not one shared fixture accidentally testing
all three via a common path. `src/` is back to the fully-fixed, committed state after the last
restore (`git status --short` showed only the (already-committed-by-this-point) new test files).

## Regression check

Full `tests/unit`: **1228 passed**, 0 failed, 0 skipped, run twice (once right after T4, once in
the final combined gate pass after T5) with an identical result both times. 10 of those are the
new shifter unit tests; nothing else moved. Full `tests/parity`: **292 passed, 4 skipped**, also
run twice with an identical result; 2 of those are the new PyPSA shifter parity tests, and the 4
skips are the pre-existing `test_market_zonal_vs_pypsa.py` fixed-load skips, unchanged. Nothing
else moved, as expected: every pre-existing fixture has `shift_deg == 0` everywhere, so
`p_shift(arr) == 0` identically and the fix is a byte-for-byte no-op on them.

## Docs (T5)

- `docs/manual/formats.md`: removed the "gets wrong or infeasible `opf`/`market` results until
  the phase-shifter fix lands" bullet from all **four** importer limitations sections
  (pandapower JSON, PyPSA, PSS/E RAW, CSV bundle) -- untrue now, so removed rather than
  softened, per the task brief. `opf.md` and `market.md` were checked (grepped for "shift",
  "phase", "F1", "A19") and carried no such caveat -- nothing to change there; `market.md`'s
  "narrow form" note about the settlement identity's phase-shift/shunt corrections is a
  different, still-valid statement about the LMP settlement identity's exact algebraic form, not
  about wrong flows, so it was left untouched.
- `docs/changelog.md`: new `### Fixed -- the DC-OPF phase-shifter flow defect (M7 F1, M8 A19)`
  section at the top of `[Unreleased]`, ahead of the M8 wave section (M9 hasn't opened; this is
  a standalone task after M8 shipped, not part of a wave, so it gets its own section rather than
  folding into M8's). M8's own historical "Known limitation carried out of the wave" bullet was
  left as an accurate record of M8's ship-time state (not rewritten -- it was true then), with a
  one-line forward-pointer appended: `**Fixed** -- see "Fixed", above.`
- `uv run --group docs mkdocs build --strict` -> exit 0 (twice: once mid-task, once in the final
  gate pass). `tests/unit/test_io_limitations.py` + `test_docs_registry_listing.py` (92 tests,
  cross-check the manual against `io.limitations.LIMITATIONS`) -> all pass.

## Final gates (all re-run together after T5, on top of the full commit stack)

```
$ uv run ruff check .
All checks passed!

$ uv run ruff format --check .
204 files already formatted

$ uv run mypy
Success: no issues found in 59 source files

$ uv run pytest -q tests/unit
1228 passed in 163.89s (0:02:43)

$ uv run pytest -q tests/parity
292 passed, 4 skipped, 10 warnings in 123.95s (0:02:03)

$ uv run --group docs mkdocs build --strict
INFO    -  Documentation built in 30.47 seconds
(exit 0)
```

## Status

All five tasks (T1-T5) complete, committed, verified. Nothing left open. Progress log:
`.bionic/tmp/shifter-fix-progress.md` (not committed, per instructions -- the worktree is
task-scoped and cleanup-on-finish).
