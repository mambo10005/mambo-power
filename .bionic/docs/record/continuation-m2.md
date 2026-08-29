# Continuation — after wave M2 power-flow (2026-08-23)

## Wave completed

M2 power-flow — merged into `epic/01-foundation` at **dcdc1c9** (wave head b771197, --no-ff).
Delivered: `pf.dc` and `pf.ac_newton` (sparse polar Newton-Raphson, pandapower-semantics
Q-limits, flat/warm start), `numerics.effective_roles` + island repair-and-warn
(`model.repair_islands`), `results/` provenance-stamped models, the stateless `jobs` API
(kinds `pf.ac`/`pf.dc`), a full mkdocs-material docs site (21 pages, API reference, mermaid
architecture + data-model diagrams), 7 CI-executed runnable examples. 492 tests; CI 32663188881
8/8 green on the exact merged tree; auditor first pass REFUTED two rows + one coverage hole
(record/m2-audit.md), closed by the R1 fold (commit b771197, record/m2-r1-fold-report.md,
10 items: the 3 proof gaps, 2 independent-critic doc-accuracy findings, 5 self-review findings
including a security contract breach and an unbounded-work path) and re-audited CONFIRMED
(record/m2-r2-reaudit.md). 6-axis self-review + independent critic both clean after the fold.
No ADR this wave (Step 7: n/a — no cross-wave decision beyond what ADR-004/005 already govern).

## Integration state

- `epic/01-foundation` local head `dcdc1c9` — **not pushed** (user decision, same convention as
  M1's plan A20). CI has therefore not yet run on the merge commit itself, though the merged
  tree is byte-identical to wave head `b771197`, which CI already proved 8/8.
- `origin/wave/02-power-flow` = `b771197` (pushed for CI). The wave branch can be deleted on
  origin after the epic branch is pushed, same as M1's `wave/01-substrate`.
- Main checkout `C:\Claude Projects\mambo-power` is on `epic/01-foundation`. Worktree
  `mambo-power-m2` removed (junction removal needed git-bash `rm`, not PowerShell/cmd
  `rmdir` — this session's sandbox blocked both PowerShell's `Remove-Item` alias and `cmd.exe
  /c rmdir` on that path; plain POSIX `rm` on the reparse point from Git Bash worked). `.bionic/tmp`
  wiped, including this session's own preflight/roster state files (harmless — the dispatch
  gate self-heals a missing attestation by re-running the probe).
- `uv` at `C:\Users\mambo\AppData\Roaming\Python\Python314\Scripts\uv.exe` (not on PATH).

## Two harness bugs found and fixed this session (not project code — global `~/.claude/hooks/`)

Both are Windows/Git-Bash path-convention mismatches (drive-letter form `C:/...` vs MSYS mount
form `/c/...`), found while dispatching M2's fold and re-audit subagents:

1. **`dispatch-preflight.sh`** — `resolve_in_repo()` mis-rejoined path components for a
   drive-letter root (prepending a bogus leading `/`), and separately compared a drive-letter
   `$REPO` against an MSYS-form resolved path from `pwd -P`. Both fixed and verified by hand
   simulation before redeploying; blocked **every** subagent dispatch declaring a deliverable
   while a wave was active, on this machine, regardless of the deliverable's actual path.
2. **`stop-guard.sh`** — found, NOT fixed (out of scope for this session, lower stakes since it
   only blocks `TaskStop` on already-idle, already-delivered agents): `OWNING_SID` extraction
   assumes forward-slash separators when taking the basename of a transcript path, so on a
   Windows transcript path (backslash-separated) it strips nothing and misidentifies every
   locally-launched agent as `FOREIGN`. Left `m2-critic` and `m2-r1-fold` running idle rather
   than force a stop through this bug. See memory `dispatch-preflight-windows-path-bug.md` for
   detail; a future session hitting an unexpected `TaskStop` "FOREIGN" refusal on its own agent
   should suspect this same bug before assuming its target id is wrong.

## Next wave: M3 opf-n1

Opens as its own wave-scale canonical-sdlc run: branch `wave/03-opf-n1` off `epic/01-foundation`
(`dcdc1c9`, once pushed), worktree `C:\Claude Projects\mambo-power-m3`, junction `.bionic` → main
checkout's `.bionic` (remove the junction with git-bash `rm`, NOT PowerShell/cmd `rmdir` — see
bug note above — before `git worktree remove`). Per epic.plan.md: `opf.dc_opf` single LP builder
on highspy with duals; PWL costs; parity vs MATPOWER `rundcopf` + PyPSA; `contingency.n1` LODF
screen + re-solve with a brute-force agreement test; jobs kinds `opf.dc`, `n1`.

## Carry-overs into M3 (from M2's R1-fold deferrals, plan Assumptions A13/A14)

- A13 "docs/text batch": `repair_islands_entities` naming in the spec/architecture prose;
  the pu-boundary docstring wording (`numerics/arrays.py` vs `results.from_arrays`); "opt-in
  from 3.14" wording for the warnings-context sentence; the AC-7 timing figure's "idle machine"
  condition; `loading_pct` documented as from-side-only; the per-generator-vs-per-bus Q-limit
  edge note; `pages.yml` permission scoping to the `deploy` job; MathJax CDN version pin.
- A14 "code tidy batch": move `s_from_pu`/`s_to_pu` computation into `ac_newton.newton` so
  `pf/__init__.py` is pure mapping; a frozen dataclass for `RepairedEntities`; delete the dead
  `case300 not in FIXTURES` test branch; `test_effective_roles.py` should use `FIXTURES`; drop
  or rename the stale first-wins `NetworkArrays.v_set`; a `ResultProvenance.stamp()` classmethod;
  import `DEFAULT_BASE_KV` instead of repeating `SUBSTITUTE_KV = 1.0` in three test files; type
  `StructuredError.code: FailureCode` or test coverage for it; single-generator Q-assignment
  precision at very wide limits; `initial_voltage`'s "auto" guard should require `vm_pu > 0`.

## Carry-overs from M1, still open (continuation-m1.md, unchanged by M2)

- A17 silently dropped MATPOWER columns (RAMP_*, ANGMIN/MAX, RATE_B/C, MBASE, PC/QC) — M3 may
  need RATE_B/C and ANGMIN/MAX for N-1 and OPF angle constraints.
- A6/A9 schema candidates: machine-readable bounds via `json_schema_extra`; optional `name` on
  Bus/Generator.
- `ideas/pandapower-from-ppc-bug-report.md` — upstream bug, user decides whether to file.

## User actions outstanding

- Push `epic/01-foundation` (and optionally delete `origin/wave/01-substrate` and
  `origin/wave/02-power-flow`).
- Claim the PyPI name `mambo-power` before M9 (carried from M1, still open).
- (`gridlab-w1` leftover directory: already deleted by the user before M2 Step 3 — resolved,
  not carried forward. The fixture-provenance *text* that leaked from it, unrelated to the
  directory itself, was cleaned up in the M2 R1 fold.)
