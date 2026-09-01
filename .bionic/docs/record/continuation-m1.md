# Continuation — after wave M1 substrate (2026-08-20)

## Wave completed

M1 substrate — merged into `epic/01-foundation` at **6c94459** (wave head 3c4f88d, --no-ff).
Delivered: uv/hatchling project, ruff + mypy strict, pytest tiers (unit/parity/property),
6-job CI (ubuntu 3.11/3.12/3.13, macOS 3.12, Windows 3.12, install-smoke), `mambo_power.model`
(pydantic v2 Network, named all-issues validation, JSON schema snapshot), `io.native`,
`io.matpower` (incl. gencost), `numerics` (NetworkArrays, Ybus/Bbus/PTDF/LODF). 269 tests;
CI 32435477865 6/6 green; auditor CONFIRMED all rows + wave; critic READY AFTER FIXES → fixes
folded (ddbcdc4, fcbf571, 3c4f88d). ADR-005 recorded.

## Integration state

- `epic/01-foundation` local head 6c94459 — **not pushed** (user decision, plan A20).
- `origin/wave/01-substrate` = 3c4f88d (pushed for CI). The wave branch can be deleted on
  origin after the epic branch is pushed.
- Main checkout `C:\Claude Projects\mambo-power` is on `epic/01-foundation`. Worktree
  `mambo-power-m1` removed. `.bionic/tmp` wiped.
- `uv` at `C:\Users\mambo\AppData\Roaming\Python\Python314\Scripts\uv.exe` (not on PATH).

## Next wave: M2 power-flow

Opens as its own wave-scale canonical-sdlc run: branch `wave/02-power-flow` off
`epic/01-foundation` (6c94459), worktree `C:\Claude Projects\mambo-power-m2`, junction
`.bionic` → main checkout's `.bionic` (remove the junction with `rmdir` before
`git worktree remove`). Delivers `pf.ac_newton`, `pf.dc`, `results` provenance stamp, `jobs`
contract with kinds pf.ac / pf.dc; parity vs MATPOWER published VM/VA + pandapower runpp.

## Carry-overs into M2 (from M1 assumptions)

- A16 island policy (critic 3): hard DISCONNECTED_BUS at load vs auto-deactivate + warn —
  decide in M2's design interview.
- A18 effective vs declared bus roles (critic 2): PV with all gens out → PQ; slack with no
  gen → error; multi-gen v_set rule (first in-service vs MATPOWER last). M2 owns, with a
  fixture that can tell the difference (no IEEE fixture has an off gen or multi-gen bus —
  A21; add e.g. a modified case9/case14 fixture).
- A12 phase-shift conjugation covered only by the dense unit case (no fixture has SHIFT≠0).
- A19 NetworkArrays arrays are writable despite frozen dataclass — document.
- W1 NR conventions to port: record/m1-w1-extract.md §4 (tol 1e-8, max 20 iter, 10 Q-limit
  rounds, PV→PQ with ε=1e-9 and restore rule; parity bands VM 2e-3 pu / VA 0.5°).
- A22 lesson: oracle comparisons exclude singular/bridge columns explicitly; never assert
  how an oracle represents them (macOS Accelerate differs).

## Carry-overs into M3+ 

- A17 silently dropped MATPOWER columns (RAMP_*, ANGMIN/MAX, RATE_B/C, MBASE, PC/QC) — M3
  adds ramp + angle limits to the model when OPF needs them; importer then warns.
- A6 / A9 schema candidates: machine-readable bounds via json_schema_extra; optional
  `name` on Bus/Generator (bus_name currently dropped). Additive, snapshot regen.
- ideas/pandapower-from-ppc-bug-report.md — upstream bug, user decides whether to file.

## User actions outstanding

- Push `epic/01-foundation` (and optionally delete `origin/wave/01-substrate`).
- Delete leftover `C:\Claude Projects\gridlab-w1` directory (junk; tag archive/ts-w1 holds the tree).
- Claim the PyPI name `mambo-power` before M9.
