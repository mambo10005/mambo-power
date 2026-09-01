# Continuation — after wave M3 opf-n1 (2026-08-24)

## Wave completed

M3 opf-n1 — merged into `epic/01-foundation` at **5fa3285** (wave head 4bd67d9, --no-ff).
Delivered: `opf.dc_opf` (array-level LP/QP builder over HiGHS, PTDF flow-limit rows, duals,
convex PWL cost support, LMP decomposition), `opf.solve_dc_opf` (Network-facing wrapper),
`contingency.n1` (LODF fast-screen + confirming DC re-solve, brute-force-proven on all 5
fixtures), an AC-feasibility check (`FeasibilityReport`), `jobs` kinds `opf.dc`/`n1`, manual +
API docs, one new example. 596 tests; CI 32781551954 success on the exact merged tree. Auditor
first pass REFUTED one row (AC-1's PyPSA half — a proof gap, honestly disclosed, not a
behaviour defect), closed by the R1 fold and re-audited CONFIRMED. Step 6's 6-axis self-review
(2 real FLAGs — Security: `PiecewiseCost.points` unbounded; Performance: PTDF computed twice
per call) and independent critic (root-caused a genuine documentation error — the case300 PyPSA
residual's cause, wrongly guessed in 3 places including this session's own re-audit) both
folded as R3. ADR-006 records the array-level/Network-level reuse seam M4 is expected to build
on directly.

## Integration state

- `epic/01-foundation` local head `5fa3285` — **not pushed** (user decision, same convention
  as M1/M2). CI has therefore not yet run on the merge commit itself, though the merged tree is
  byte-identical to wave head `4bd67d9`, which CI already proved.
- `origin/wave/03-opf-n1` = `4bd67d9` (pushed for CI). Can be deleted on origin after the epic
  branch is pushed, same as M1's/M2's wave branches.
- Main checkout `C:\Claude Projects\mambo-power` is on `epic/01-foundation`. Worktree
  `mambo-power-m3` removed (junction via git-bash `rm`, not PowerShell/cmd `rmdir` — same
  known sandbox block as M2). `.bionic/tmp` wiped.
- `uv` at `C:\Users\mambo\AppData\Roaming\Python\Python314\Scripts\uv.exe` (not on PATH).

## Notable this session (context for whoever picks up M4)

- **A user interruption mid-wave (all 20 background agents stopped) happened between Step 6's
  R3 fold dispatch and completion.** The killed fold agent had done almost nothing (one
  verified-but-uncommitted docstring edit); it was re-dispatched fresh (`m3-r3-fold-2`),
  building on that one edit rather than redoing it, and completed cleanly. No data was lost,
  but it's worth knowing the session survived an interruption mid-fold without incident.
- **Two agents (S3, S5) finished their slices correctly but went idle without ever committing
  or reporting** — the orchestrator verified their work directly (diff + tests + lint/mypy) and
  landed it on their behalf, writing their reports itself. Both are recorded with a "completed
  by the orchestrator" framing in `m3-s3-report.md`/`m3-s5-report.md`. If this pattern recurs in
  M4, the playbook is: check `git status --porcelain` and the agent's own progress file before
  assuming anything is wrong — the work may well be done and just unreported.
- **A pervasive, deliberate 22-file documentation convention was discovered and correctly left
  alone** — `W<n>`/`wave M<n> design item <n>` citations in module docstrings, spanning M1/M2/M3.
  A walk finding flagged one instance as confusing; investigating it before fixing more revealed
  the whole codebase does this consistently. Logged as Assumption A6, not fixed project-wide.
  If M4 wants this changed, it's a real, scoped documentation-consistency task on its own, not
  something to fold piecemeal.
- **A three-document misdiagnosis was caught and corrected**: the case300-vs-PyPSA cost residual
  was guessed ("bus numbering") in the test docstring, the plan, and this session's own re-audit
  before the Step-6 critic actually root-caused it (PyPSA silently drops bus shunt conductance
  from its balance equation; `dc_opf` is provably more correct, not less). Worth remembering
  when M4 inherits case300 as a fixture: the corrected explanation is in
  `tests/parity/test_opf_vs_pypsa.py`'s docstring and should not need re-deriving.

## Two harness hook bugs from M2, status update

- `dispatch-preflight.sh` and `canonical-sdlc-governing-skill.sh` fixes (Windows drive-letter
  path bugs) held up cleanly through all of M3's dispatches — no recurrence.
- `stop-guard.sh`'s Windows-path bug (found in M2, never fixed — only blocks `TaskStop` on
  already-idle agents) also never blocked anything real this wave. Still open; see memory
  `dispatch-preflight-windows-path-bug.md`.

## Next wave: M4 nodal-market

Opens as its own wave-scale canonical-sdlc run: branch `wave/04-nodal-market` off
`epic/01-foundation` (`5fa3285`, once pushed), worktree `C:\Claude Projects\mambo-power-m4`,
junction `.bionic` (remove with git-bash `rm`, not PowerShell/cmd `rmdir`, before `git worktree
remove`). Per epic.plan.md: `Scenario` offers/bids model; `market.nodal` day-ahead clearing;
LMP = energy + congestion decomposition (**reuse `opf.dc_opf.lmp_decomposition` directly, per
ADR-006** — do not rebuild this); congestion rent; settlement identities as tests; jobs kind
`market.nodal`. M4 is explicitly the wave ADR-006's reuse seam was built for — read it first.

## Carry-overs into M4 (from M3's own scope, spec Not Doing + R3 fold Assumptions)

- Generator-outage N-1 (branch outages only this wave, per spec Not Doing) — M4 doesn't need
  this, but a later wave will.
- `model.PiecewiseCost`'s missing convexity validation at the model level (M3 guards it locally
  in `opf.dc_opf` instead) — still open if a future wave wants network-level enforcement.
- The 22-file `W<n>` docstring-citation convention (Assumption A6) — a real but deliberately
  deferred documentation-consistency task, not urgent.
- `PiecewiseCost.points` now has `max_length=200` (R3 fold, closes a real unbounded-work
  vector) — if M4's `Scenario` offers/bids ever compose through the same cost-shape machinery,
  check whether an analogous bound is needed there too.

## Carry-overs from M1/M2, still open

- A17 (M1) silently dropped MATPOWER columns (RAMP_*, ANGMIN/MAX, RATE_B/C, MBASE, PC/QC).
- A6/A9 (M1) schema candidates: machine-readable bounds, optional `name` fields.
- `ideas/pandapower-from-ppc-bug-report.md` — upstream bug, user decides whether to file.
- M2's deferred fold batches (A13/A14, ~18 small doc-wording/code-tidy items) — still open,
  still low priority.

## User actions outstanding

- Push `epic/01-foundation` (and optionally delete `origin/wave/01-substrate`,
  `origin/wave/02-power-flow`, `origin/wave/03-opf-n1`).
- Claim the PyPI name `mambo-power` before M9 (carried from M1, still open).
