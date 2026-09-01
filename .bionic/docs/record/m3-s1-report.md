# M3 S1 report — fixtures: rating-derivation helper + PWL-cost derived fixture

Slice S1 of wave M3 (opf-n1). Worktree `C:\Claude Projects\mambo-power-m3`, branch
`wave/03-opf-n1` (base `dcdc1c9`). Delivers the fixture half of AC-4 and AC-5 — the helper and
fixture other slices (S3, S4) build their behavioral proofs on top of.

## Task A — rating-derivation test helper

`tests/_rated.py`, mirroring `tests/_brute_force_lodf.py`'s "documented, test-time
transformation of an already-owned fixture" pattern. `rated_network(net: Network) -> Network`:
DC-solves the unmodified base case once (`pf.dc.solve` on `NetworkArrays.from_network(net)`),
then returns a `model_copy(deep=True)` with each in-service/connected branch's `rating_mva` set
to `max(RATING_MARGIN * |p_from_mw|, RATING_FLOOR_MVA)`. Does not mutate the input.

### Margin chosen: 1.2 (20% headroom), floor 1.0 MVA

No MATPOWER-shipped OPF fixture carries a real `RATE_A` (record/m3-research.md §6 — confirmed
`RATE_A == 0` on every branch of all five fixtures). I swept five candidate margins
(1.5, 1.2, 1.1, 1.05, 1.02) with a vectorized LODF sanity check — for every fixture and every
non-bridge branch outage `k`, whether `|base_flow[l] + lodf[l, k] * base_flow[k]| >
rating[l]` for any other branch `l` (script: `<scratchpad>/probe_margin.py`, not committed;
reuses `numerics.lodf`/`numerics.bridges`, no full re-solve):

| margin | case14 (pairs/outages) | case_ieee30 | case57 | case118 | case300 |
|---|---|---|---|---|---|
| 1.5 | 45 / 15 | 141 / 31 | 346 / 67 | 619 / 140 | 1739 / 272 |
| **1.2** | **81 / 17** | **229 / 35** | **636 / 75** | **1173 / 166** | **2981 / 297** |
| 1.1 | 102 / 18 | 297 / 36 | 916 / 77 | 1615 / 169 | 4267 / 314 |
| 1.05 | 128 / 19 | 358 / 37 | 1267 / 77 | 2183 / 171 | 5823 / 318 |
| 1.02 | 148 / 19 | 437 / 37 | 1674 / 78 | 3094 / 174 | 8456 / 318 |

(`pairs` = outage/branch combinations that would violate; `outages` = distinct outages causing
at least one violation.) Even at the loosest margin tried (1.5, 50% headroom) every fixture
already shows real violations — the fixture set's flow distribution is spread enough that
"nothing ever binds" was never a risk here. I picked **1.2** (not something looser) for two
reasons: (1) it is the number the task brief itself suggested as a reasonable default, and (2)
it leaves real headroom against DC-vs-AC / re-solve modelling slack in S4's later confirming
DC re-solve, while still producing triple-digit violation counts on case118/case300 and
double-digit counts even on the smallest fixture (case14) — comfortably enough signal for
AC-4's "at least one outage on at least one fixture violates" and AC-6's brute-force agreement
test to actually exercise the violating path, not just the unconstrained one.

Floor: 1.0 MVA, so the handful of near-zero-flow branches (case14 has 1 branch under 1 MVA
base flow, case118 has 5, case300 has 8 — checked directly, not derived from the sweep) don't
get a degenerate near-zero rating that would make every other outage trivially "violate" it.

### RED -> GREEN

RED: `tests/unit/test_rated_helper.py` written first, importing `tests._rated` (did not yet
exist) — collection failed with `ModuleNotFoundError: No module named 'tests._rated'`.

GREEN: `tests/_rated.py` implemented; `uv run --no-sync pytest -q tests/unit/
test_rated_helper.py` — **5 passed**. The test proves the helper's own guarantee (unmodified
base-case dispatch never violates its own derived ratings) on case14 and case118, the exact
margin/floor formula, and that the input `Network` is not mutated.

## Task B — PWL-cost derived fixture

`fixtures/matpower/derived/case14_pwl.m`: `case14.m` with only `mpc.gencost` touched (bus,
gen, branch matrices byte-identical). No real fixture has any MODEL-1 cost data
(record/m3-research.md §2.2), so this is a fresh synthetic derivation, not a fit to any
published curve.

- gen-2 (bus 2, `Pmax` 140): MODEL 2 -> 1, breakpoints `(0,0), (40,800), (90,2050), (140,3550)`
  — segment slopes 20, 25, 30 $/MWh, strictly increasing (convex).
- gen-3 (bus 3, `Pmax` 100): MODEL 2 -> 1, breakpoints `(0,0), (30,600), (70,1800), (100,3000)`
  — segment slopes 20, 30, 40 $/MWh, strictly increasing (convex).
- gen-1 (slack)/gen-4/gen-5: untouched MODEL 2 rows, widened with inert trailing zero padding
  so `mpc.gencost` stays rectangular (the importer's `_matrix()` requires uniform row width;
  MODEL 2 import only reads each row's first `NCOST` coefficients).

`fixtures/matpower/derived/PROVENANCE.md` updated with a matching entry (append, same format
as the `case14_roles`/`case14_island`/`case14_noslackgen` entries).

### RED -> GREEN

RED: `tests/unit/test_fixtures_pwl.py` written first, against a `case14_pwl.m` that did not
yet exist — `FileNotFoundError` on 3 of 4 tests (the pure-Python convexity check on the
documented breakpoints, which needs no file, passed immediately).

GREEN: `case14_pwl.m` + `PROVENANCE.md` entry written; `uv run --no-sync pytest -q
tests/unit/test_fixtures_pwl.py` — **4 passed**: the independent-reader raw-matrix diff
(`tests.parity._mpc_reader`) proves the file is exactly `case14.m` plus the documented
`gencost` edit; the header names the base file and AC-5; `io.matpower.load` round-trips gen-2
and gen-3 into `PiecewiseCost` with the exact documented points (untouched generators keep
`PolynomialCost`); the documented breakpoints are independently re-checked for strictly
non-decreasing slope. No OPF solve is attempted against this fixture — S3's job, out of scope
here per the plan.

## Verification

- `uv run --no-sync pytest -q -p no:cacheprovider` (full suite): **501 passed** (492 baseline +
  9 new: 5 in `test_rated_helper.py`, 4 in `test_fixtures_pwl.py`), 208s, 10 pre-existing
  pandapower deprecation/divide warnings unrelated to this change.
- `ruff check .`: all checks passed.
- `ruff format --check .`: 104 files already formatted (no diff).
- `mypy` (project config, `files = ["src"]` per `pyproject.toml` — `tests/` is intentionally
  out of strict-mypy scope): no issues found in 32 source files. My changes touch no file under
  `src/`.

## Files touched (exactly these, staged individually)

- `tests/_rated.py` (new)
- `tests/unit/test_rated_helper.py` (new)
- `fixtures/matpower/derived/case14_pwl.m` (new)
- `tests/unit/test_fixtures_pwl.py` (new)
- `fixtures/matpower/derived/PROVENANCE.md` (appended)

Also updated (via `.bionic` junction, not part of the code commit): plan.md's AC-4/AC-5
evidence blocks (fixture half filled; S3/S4 named as owing the behavioral half).

## Commit

`feat(m3/S1): fixtures — rating-derivation helper + PWL-cost derived fixture` — `2b31307`,
pushed to `wave/03-opf-n1`.

## Carry-forward notes for S3/S4

- S4 (`contingency.n1`) should reuse `tests._rated.rated_network` directly rather than
  re-deriving ratings; the margin/floor rationale above is the citation for its own AC-4/AC-6
  evidence, not something to re-litigate.
- S3 (PWL cost LP path) consumes `fixtures/matpower/derived/case14_pwl.m` as-is; no changes
  needed to the fixture itself for a convex-cost round-trip. A *non-convex* variant, if S3's
  `NonConvexCostError` guard test wants a file rather than a hand-built in-memory case, is not
  provided here — out of this slice's scope (the task named a hand-built unit-tier case as the
  expected shape for that test, not a new fixture file).
