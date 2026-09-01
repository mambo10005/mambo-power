# Continuation — M8 interop closed

Wave M8 (`interop`), triple build · audited · wave, integration branch `epic/01-foundation`
(base `15e71fa`).

- **Merge SHA:** `511c6a0` (`--no-ff`, local; wave head `33abd13`, tree byte-identical modulo the
  `.bionic` docs the orchestrator commits only on `epic/01-foundation`, ~40 commits across 9 slices)
- **Suite:** 1513 passed / 4 skipped (1175 at M7 close → 1513, **+338**)
- **Gates at the wave head, one named sweep — the full list CI runs:** 1513/4 in 205.38s; `ruff
  check` all passed; `ruff format --check` 201 files; `mypy` clean on 59 source files; `mkdocs
  build --strict` exit 0. Log: session scratchpad `m8-gate-33abd13.log`. Earlier sweeps this wave,
  each at its own named head and recorded in the plan: `15e71fa` (baseline, 1175/4), `7ec0b0b`
  (1 failed — F4), `3f2a9a0`, `e2d6da8` (1494/4).
- **Independent verdicts, two full passes:** audit 8 DISCHARGED / 0 PARTIAL / 0 REFUTED at both
  `7ec0b0b` and `e2d6da8`, wave verdict COVERED both times (`m8-audit.md`); critic **not merge-ready
  (3 blocking)** → **merge after should-fixes (0 blocking, 6 should-fix)** across two passes
  (`m8-critic.md`) — every blocker fixed with a parity proof, not asserted; walk (`m8-walk.md`, at
  `7ec0b0b`, dispatched first and from the docs only) — 8 surprises, all fixed and re-verified.
- **Next wave:** M9 `release` (PyPI 0.1.0, trusted publishing, semantic-release) — depends on
  everything and is the last wave on the roadmap.
- **Not pushed:** `epic/01-foundation` is local past `cdb4fef` (M7's push), per the standing
  convention that pushing the epic branch is the user's call. `wave/08-interop` is unpushed too, so
  no CI run exists for this head; every gate figure above is local.

## What M8 shipped

Four interchange formats, all pivoting through `Network`, none changing what the solvers compute.
`io.pandapower_json` (import + export, measured unit conventions, `ext_grid` → slack, `nets_equal`
holds only on `poly_cost`/`pwl_cost` — pinned, not assumed; bulk creators, `nets_equal`-identical
not byte-identical to the per-row form); `io.pypsa` (export only, transformer admittance fixed after
the critic found it inverted, unrated `s_nom` reported, no `p_set` pin, drop-and-report for
piecewise/degree>2/bids/zones); `io.psse_raw` (v33 import, hand-authored `case14_v33.raw` +
`synthetic_quirks_v33.raw` with full provenance, CZ/CW/CM conversion, no cost section — refuses
to dispatch); `io.csv_bundle` (manifest + per-table CSV, atomic directory-level swap, bit-exact
round-trip on 14 networks). `Branch.kind` (`line | transformer`, defaulted, **promotes** rather than
rejects on mutation — corrected mid-wave after the critic found the reject form broke a mutated
network's own round-trip). `io.report.ExportReport` mirroring `ImportReport`; `io/limitations.py`
as the registry, keeping `io/report.py` a leaf. `MissingCostError`: a generator with no cost now
refuses (`VALIDATION` through `jobs`) instead of silently pricing at zero — found by the walk on a
RAW import, fixed across `opf`/`market`/`jobs`. `examples/13_interop.py`. ADR-011.

## Carry-overs into M9

1. **CLOSED 2026-08-30** — the `opf.dc_opf` phase-shifter flow defect (F1, A19) was fixed as a
   standalone bugfix task (`task/shifter-flow-fix`, merged `e9d454a` on `epic/01-foundation`) before
   M9 opened. Its own review found the first pass incomplete: `opf/multiperiod.py` and
   `opf/redispatch.py` carried independent copies of the identical bug, live end-to-end through
   `market.solve_zonal`/`solve_multiperiod` (measured 81.4–107.2 MW flow errors, the exact
   false-`Infeasible` failure mode) — extended and closed across two full audit/critic passes. All
   `formats.md` caveats removed for real. See `record/task-shifter-flow-fix.plan.md` for the full
   record; nothing carries forward from this item.
2. **`res_bus` was read and written by an early landing of the pandapower importer/exporter**,
   against the spec's own Not-doing; removed at Step 6 (critic S10). Watch for the same class —
   reading a results table as an input — in any future format.
3. **PyPSA case118 dispatch tolerance is the oracle's, not the mapping's** (F3): HiGHS's QP stops
   1.87e-3 MW early on one unit, identical to what M3 measured on its own ppc-built oracle. If M9's
   CI runs on a different platform, this is one of two places (with M7's AC-8 pin) a float
   disagreement would first show.
4. **`test_bulk_export_is_byte_identical...` had a dead `assert ... or True`** (critic #21, fixed) —
   the third instance this repo has caught of a check that cannot fail wearing a name that claims
   it can (M6 review, M7 F19-adjacent). Worth a grep sweep (`assert .* or True`, `assert True`) at
   M9 if there's slack.
5. **Nits not closed** (critic #25–26, not blocking): three transformer edge configurations
   pandapower itself cannot solve (a `TypeError` on both sides, not a mambo defect); a
   pre-existing orphan `.name.tmp-<pid>` staging directory get `rmtree`'d rather than left.
6. **M7's carries are still open** (see `continuation-m7.md`): the profit-tie band cannot be sized
   (standing limit, not an M8/M9 item); `MarkupStrategy` cannot attach to any bundled fixture (all
   quadratic); the branch-flow derivation's third site (`redispatch.py`, constant-folded); pre-M7
   demand-Hessian test blindness in `dc_opf`'s own tests; `MarketZonalResult`'s missing corridor
   rows; `c0` zero on every fixture.

## The M8 lessons worth carrying

1. **Fixture blindness hides real defects until a review builds the case that exercises them.**
   Every bundled transformer has `b = 0`, so the PyPSA admittance-factor inversion (critic B1)
   survived every parity row until a 2-bus hand case with `b != 0` found it. No fixture has a phase
   shifter (F1), so that defect is three waves old. When a field is structurally absent from every
   committed case, the review layer that builds its own fixture is the only thing that can see it.
2. **A design decision made under one Step-2 assumption can break under Step-6 attack, and the fix
   is a promotion, not a compromise.** S1 rejected `kind="line"` with a tap; the critic found that
   a mutated network then fails its own native round-trip — a pre-M8 regression. The fix (promote,
   don't reject) is strictly more permissive and closes the gap without reopening the design.
3. **The bookkeeping phase is the fragile half of a dispatch, twice this wave (F8, F11).** Both
   times the deliverable phase was clean — commits, tests, a progress log — and the report/notify
   step simply didn't run, apparently across a session restart. The standing recovery is now: the
   orchestrator re-verifies independently and writes the report itself from the commits and
   progress log, never trusting an agent's self-report as the only evidence. This is cheaper than
   it sounds because the evidence (commits, test runs) is durable; only the narration was lost.
4. **Two full audit/critic passes, not one, because the fixes touched what the first pass measured.**
   The re-audit reproduced F2/F3's amended numbers independently rather than re-reading them; the
   re-critic re-ran all 16 first-pass reproductions before looking for anything new. Diminishing
   the second pass to "spot-check the diff" would have missed the tap-changer edge cases (17–19)
   entirely — they are properties of the fixed code, not of what changed.
5. **A vacuous assertion is a defect class, not a one-off** (critic #21). `assert x == y or True`
   passes at every commit regardless of `x` and `y`; grep for the pattern is cheap and the repo has
   now hit it three times across two waves.
6. **A silent default that turns out to matter economically gets caught by a walk that runs the
   feature, not by criteria that describe it.** `gen_cost_coeffs` pricing a cost-less generator at
   zero was never named by any acceptance criterion; the walk found it because it ran `opf` on a
   RAW import, the way a user would.

## Process notes for M9

- Baseline on a clean checkout before any agent enters the worktree; one agent per worktree at a
  time; measurement from `git archive` overlays with `__file__` proven; verify every slice's commit
  `--stat` against the brief; stop agents on hand-back; briefs say never amend/rebase/reset.
- Walk first, from the docs, at a named head, artifact machine-checked for zero `AC-[0-9]`; audit
  and critic from archives, forbidden the slice reports; when a critic verdict is not merge-ready,
  fix and **re-dispatch both** the auditor and the critic at the new head rather than assuming the
  fix closes the finding — this wave's re-audit found two should-fixes the fix slices' own reports
  did not surface.
- Remove worktrees with `git worktree remove --force`, never `rm -rf` — a worktree's `.bionic` can
  be a junction (M7 F20). `.bionic/docs/` is committed with every checkpoint (tracked since M7's
  `7f396be`); `.bionic/tmp/` stays ephemeral, its M8-cycle contents preserved under `record/` before
  the wipe.
- When an agent's bookkeeping phase goes missing (no report, no notification, worktree otherwise
  clean), do not re-dispatch to redo the work — re-verify the existing commits independently and
  write the report from that verification (F8, F11).
