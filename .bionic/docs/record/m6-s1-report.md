---
governing-skill: agent-skills:incremental-implementation
sdlc-step: 4
intent: build
rigor: audited
scale: wave
canonical_sdlc_version: 13
surface_type: library
language: python
has_ui: false
multi_agent: true
deploy_target: pypi
cleanup_on_finish: true
use_worktree: true
rigor-floor: audited
walk: required
design-interview: true
---

# M6 S1 — ADR-008 preamble unification (W1, AC-1)

Slice: S1. Role: senior-implementor. Worktree `C:\Claude Projects\mambo-power-m6`, branch
`wave/06-zonal-redispatch`, base `4cfd1d7`. Commit: **`97b56ef`** —
`refactor(m6/S1): one _extract_and_validate, two callers — ADR-008's W1`. Not pushed.

**AC-1 holds on all three clauses**, and the unification is live rather than cosmetic: breaking
the shared helper takes both surfaces red together.

Every factual claim below carries the command that produced it and that command's output.
Anything unproven is labelled `unverified`.

---

## 1. What changed

Two files, `+176 / −132`.

```
$ git show --stat 97b56ef
 src/mambo_power/opf/dc_opf.py      | 226 ++++++++++++++++++++++++++-----------
 src/mambo_power/opf/multiperiod.py |  82 +++-----------
 2 files changed, 176 insertions(+), 132 deletions(-)
```

`dc_opf.py` gains two names, placed immediately after `_concave_pwl_segments` (the function the
helper calls) and before `_RowBlock`, so the validation core and the row-family core sit adjacent:

| Name | What it is |
|---|---|
| `_ExtractedProblem` | frozen dataclass: `c2, c1, c0`, `v2, v1, v0`, `pwl_gen_idxs`, `segments_by_gen`, `elastic_load_idxs`, `demand_pwl_idxs`, `demand_segments_by_load`; `n_pwl` / `n_demand` / `n_demand_pwl` as properties |
| `_extract_and_validate(cost_coeffs, pwl_costs, demand_bid_coeffs, demand_pwl_bids, n_gen, n_load)` | the cost-coefficient shape check, the bid polynomial/PWL exclusivity check, the load-index range check, the `v2`/`v1`/`v0` dense fill, and both convexity guards |

The proposed shape from research §7 was adopted unrevised. `multiperiod.py` imports the helper
beside the four row helpers it already imported (`multiperiod.py:112-122`).

### Shape decisions, and why

- **Column layout stays outside the helper.** `dc_opf` places its elastic-demand columns at
  `n_gen + j`; `multiperiod_dc_opf` places one such block per period. The helper returns the
  coefficients and the index sets; each caller keeps where they attach — the same division of
  labour `_RowBlock` already draws for the row families.
- **The Hessian block stays per-caller**, as the spec's `## Design` directs. `dc_opf` builds over
  `n_dispatch = n_gen + n_demand`; `multiperiod_dc_opf` builds over
  `n_dispatch_total = n_periods * per_period_dispatch`, tiled per period. I looked for a clean
  shared form and did not find one worth the widening: what differs is purely the column count and
  the tiling, and the helper already hands both callers the `c2`/`v2` coefficients the assembly
  needs. Forcing a shared form would mean passing each caller's column bookkeeping *into* the
  helper, which is the coupling the extraction exists to avoid.
- **Both callers bind local aliases off the one call** rather than reading `problem.x` inline.
  This is deliberate and it is the smaller change: the names are read heavily in the delicate
  column-index bodies below (`n_demand` 9x in `dc_opf`, 12x in `multiperiod`; `n_pwl` 9x/10x), so
  inlining would have spread the diff far past the preamble and weakened the claim that only the
  preamble moved. What is unified is the *derivation*, not the local names the builder body uses.
- **`demand_col_of` stayed in `dc_opf`.** It is column layout (`{idx: n_gen + j}`), and
  `multiperiod` builds a per-period list of the same mapping. It is one line, derived from
  `elastic_load_idxs`, which the helper does return.

### Two changes worth naming explicitly

**1. Guard message text is now `dc_opf`'s, on both surfaces.** The two copies had hand-edited
message text that had drifted: `NonConvexCostError` said "(module docstring, …)" in `dc_opf` and
"(mambo_power.opf.dc_opf module docstring, …)" in `multiperiod`; `NonConcaveBidError` differed in
both wrapping and the trailing parenthetical. The helper carries `dc_opf`'s wording, which is
correct now that the guard lives in `dc_opf`'s module. Proven safe before changing it — every test
in the repo matches on a substring present in both variants:

```
$ grep -rn "NonConvexCostError\|NonConcaveBidError" tests/
tests/unit/test_opf_dc_demand.py:152:    with pytest.raises(NonConcaveBidError, match="non-concave"):
tests/unit/test_opf_dc_demand.py:161:    with pytest.raises(NonConcaveBidError, match="non-concave"):
tests/unit/test_opf_dc_demand.py:170:    with pytest.raises(NonConvexCostError, match="non-convex"):
tests/unit/test_opf_dc_pwl.py:136:    with pytest.raises(NonConvexCostError, match="non-convex"):
tests/unit/test_opf_pwl_guard.py:44:    with pytest.raises(opf.NonConvexCostError, match="non-convex"):
```

(remaining hits are prose in comments/docstrings and one JSON snapshot). Four `match=` sites, all
on `"non-convex"` / `"non-concave"`.

**2. One deliberate ordering change, outside every test.** In `multiperiod_dc_opf` the guards now
fire *before* `period_load_mw` / ramp validation rather than after. The helper is atomic, and its
first statement — the `cost_coeffs` shape check — had to stay where it was (immediately after the
`n_periods` check), so the guards moved forward with it. Only a call supplying **two**
simultaneously invalid arguments can observe the difference. All four `pytest.raises` sites in
`test_opf_multiperiod.py` supply exactly one bad argument:

```
$ grep -n "pytest.raises" tests/unit/test_opf_multiperiod.py
1033:    with pytest.raises(ValueError, match="n_periods"):
1038:    with pytest.raises(ValueError, match="period_load_mw"):
1048:    with pytest.raises(ValueError, match="ramp_up_mw"):
1054:    with pytest.raises(ValueError, match="strictly positive"):
```

The new order also matches `dc_opf`'s own, and matches `multiperiod_dc_opf`'s docstring promise
that both errors are raised "up front … before any HiGHS object exists".

### Explicitly not done

No zonal, redispatch, corridor or `Zone` concept was added; no row family was written; nothing
under `model/`, `market/`, `results/`, `jobs/`, `numerics/` or `tests/` was touched; no
`__init__.py` was touched. No test was added, modified, renamed or deleted — proven in §2.2.
`tests/_zones.py` and `tests/unit/test_zones_helper.py` are the sibling slice's and were not
touched; the commit used explicit paths, never `git add -A`.

---

## 2. AC-1 clause 1 — zero test edits, full suite green

### 2.1 The isolation problem

The sibling slice `m6-s2-zones` works in the **same** worktree and landed `e8108e4` during this
slice. A full-suite count taken from the live worktree is therefore contaminated — the count
drifts as the sibling's tests land. **The overlay-tree run below is the clean number**, and it is
the only suite count this report claims.

### 2.2 The overlay tree, and proof of exactly what differs

Two trees were extracted from the base commit; only the overlay received this slice's files:

```
$ git archive 4cfd1d7 | tar -x -C <scratch>/pristine
$ git archive 4cfd1d7 | tar -x -C <scratch>/overlay
$ cp src/mambo_power/opf/dc_opf.py src/mambo_power/opf/multiperiod.py <scratch>/overlay/src/mambo_power/opf/
$ diff -rq <scratch>/pristine <scratch>/overlay
Files .../pristine/src/mambo_power/opf/dc_opf.py and .../overlay/src/mambo_power/opf/dc_opf.py differ
Files .../pristine/src/mambo_power/opf/multiperiod.py and .../overlay/src/mambo_power/opf/multiperiod.py differ
```

**Exactly two files differ, both under `src/mambo_power/opf/`.** Nothing under `tests/` differs
from `4cfd1d7` by a byte — a stronger statement than "I did not edit a test".

Import provenance, so the overlay is proven to be what loads rather than the worktree's editable
install:

```
$ cd <scratch>/overlay && PYTHONPATH=<scratch>/overlay/src <m6>/.venv/Scripts/python.exe -c "..."
mambo_power.opf.dc_opf -> ...\scratchpad\overlay\src\mambo_power\opf\dc_opf.py
mambo_power.opf.multiperiod -> ...\scratchpad\overlay\src\mambo_power\opf\multiperiod.py
_extract_and_validate: mambo_power.opf.dc_opf
```

### 2.3 The unmodified suite on that tree

```
$ cd <scratch>/overlay && PYTHONPATH=<scratch>/overlay/src \
    <m6>/.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider
816 passed, 10 warnings in 144.42s (0:02:24)
```

**816 passed**, reconciling exactly against the briefed baseline at `4cfd1d7`. Zero test edits,
zero test failures, zero skips.

### 2.4 Lint and types

```
$ uv run --no-sync ruff check src/mambo_power/opf/dc_opf.py src/mambo_power/opf/multiperiod.py
All checks passed!
$ uv run --no-sync ruff format --check src/mambo_power/opf/dc_opf.py src/mambo_power/opf/multiperiod.py
2 files already formatted
$ uv run --no-sync mypy
Success: no issues found in 46 source files
```

`mypy` is repo-wide and clean. Unlike M5's S1, repo-wide `ruff check` was not red on a sibling's
file at completion time, so the file scoping here is only for brevity.

---

## 3. AC-1 clause 2 — the `getNumRow` tripwire

`multiperiod.py:635` asserts `h.getNumRow() == expected_rows` before any dual is read. On the
overlay tree:

```
$ pytest -q -p no:cacheprovider tests/unit/test_opf_multiperiod.py
38 passed in 1.31s
$ pytest -q -p no:cacheprovider tests/unit/test_market_multiperiod.py
25 passed in 1.61s
$ pytest -q -p no:cacheprovider tests/parity/test_market_multiperiod_vs_pypsa.py
11 passed in 7.57s
```

38 + 25 = 63, plus 11 parity. Every one green.

**Proven live, not vacuous.** A green assertion proves nothing if the assertion never executes, so
`expected_rows += 1` was injected immediately before it in the scratch tree (§4's driver, sabotage
D):

| file | result |
|---|---|
| `tests/unit/test_opf_multiperiod.py` | **33 failed**, 5 passed |
| `tests/unit/test_market_multiperiod.py` | **23 failed**, 2 passed |
| the four `test_opf_dc*.py` files | all green (5 / 5 / 11 / 5 passed) |

33 + 23 = **56 red** — numerically the same 56 ADR-008 consequence 1 measured for a spurious row
family, and confined to the multiperiod surface as it should be. The tripwire runs.

---

## 4. AC-1 clause 3 — no imported private name changed signature

### 4.1 The import block

```
$ diff <(sed -n '112,125p' <pristine>/…/multiperiod.py) <(sed -n '112,122p' <overlay>/…/multiperiod.py)
4,5d3
<     NonConcaveBidError,
<     NonConvexCostError,
8,9d5
<     _concave_pwl_segments,
<     _convex_pwl_segments,
10a7
>     _extract_and_validate,
```

One name **added**; four names **removed** because they became unused there. Removals are not
resignatures, and this is the independent signal the unification is real: `multiperiod` no longer
needs the raw validation machinery, only the shared contract — **four imports replaced by one.**

Checked repo-wide before removing them, that nothing imports those four *from* `opf.multiperiod`:
`market/multiperiod.py:54-60`, `market/nodal.py:24-25` and `market/__init__.py:13` all take
`NonConvexCostError` / `NonConcaveBidError` from `mambo_power.opf.dc_opf` directly, and
`opf/multiperiod.py`'s `__all__` never listed them.

### 4.2 Signatures, before and after

All **12** names `multiperiod.py` imported at `4cfd1d7` were resolved out of each tree and their
`inspect.signature` compared:

```
$ python <scratch>/sigs.py   # run once per tree, output diffed
12 names, pristine == overlay: True (12 lines each)
```

Byte-identical, including the four now-dropped ones. For the record, the six functions:

```
_add_rows(h: 'highspy.Highs', block: '_RowBlock') -> 'None'
_balance_row(injection_cols: 'ColArray', withdrawal_cols: 'ColArray', fixed_mw: 'float') -> '_RowBlock'
_concave_pwl_segments(points: 'Sequence[tuple[float, float]]') -> 'list[tuple[float, float]]'
_convex_pwl_segments(points: 'Sequence[tuple[float, float]]') -> 'list[tuple[float, float]]'
_epigraph_rows(segments_by_gen: 'Mapping[int, Sequence[tuple[float, float]]]', gen_cols: 'ColArray', cost_col_of: 'Mapping[int, int]') -> '_RowBlock'
_flow_limit_rows(ptdf: 'FloatArray', injection_cols: 'ColArray', injection_bus: 'IntArray', withdrawal_cols: 'ColArray', withdrawal_bus: 'IntArray', rating_mw: 'FloatArray', const_mw: 'FloatArray') -> '_RowBlock'
_hypograph_rows(segments_by_load: 'Mapping[int, Sequence[tuple[float, float]]]', demand_col_of: 'Mapping[int, int]', val_col_of: 'Mapping[int, int]') -> '_RowBlock'
_RowBlock(lower: 'FloatArray', upper: 'FloatArray', starts: 'ColArray', indices: 'ColArray', values: 'FloatArray') -> None
```

---

## 5. The unification is live, not cosmetic — one helper, two callers

Per the standing rule, sabotage ran in a detached scratch worktree
(`git worktree add --detach <scratch>/sabotage HEAD`, then this slice's two files overlaid),
never the live worktree. Full test files, no `-x`, so the counts are real rather than
first-failure aborts.

```
=== BASELINE (restored helper, no sabotage) ===
  tests/unit/test_opf_dc.py                     5 passed
  tests/unit/test_opf_dc_case14_pwl.py          5 passed
  tests/unit/test_opf_dc_demand.py             11 passed
  tests/unit/test_opf_dc_pwl.py                 5 passed
  tests/unit/test_opf_multiperiod.py           38 passed
  tests/unit/test_market_multiperiod.py        25 passed
```

| # | sabotage (all inside `_extract_and_validate`) | `test_opf_dc*.py` | `test_*_multiperiod.py` |
|---|---|---|---|
| A | `neg_c2 = np.flatnonzero(c2 < 0)` → `c2 > 0` | case14_pwl **5 errors**, dc_demand **2 failed** | opf_multiperiod **3 failed**, market_multiperiod **8 failed** |
| B | `pos_v2 = np.flatnonzero(v2 > 0)` → `v2 < 0` | dc_demand **1 failed** | market_multiperiod **1 failed** |
| C | shared `c1` extraction × 1.05 | dc **1**, case14_pwl **3**, dc_demand **3**, dc_pwl **2** = **9 failed** | opf_multiperiod **13**, market_multiperiod **8** = **21 failed** |

**All three go red on both surfaces.** A is ADR-008's own named probe — the `NonConvexCostError`
guard's sign — and it takes 18 tests red across four files spanning both callers. C is the
strongest: 30 red across all six files, because `c1` is the one coefficient every fixture carries.
B is thin (2 tests) but real, and it is thin because only two tests exercise a non-concave
polynomial bid at all — a test-quality observation, not a weakness in the extraction.

These are not two implementations that happen to agree. There is one implementation, and both
callers break when it breaks.

### Restore, verified by hash

```
=== RESTORE CHECK ===
  dc_opf.py: IDENTICAL  e9b935e1c057482fb5a82a3cd0f5f768211e7a78b3e0cb903593c0a3a1afefcd
  multiperiod.py: IDENTICAL  65bb9846d9176e476088e96641408f7cf66a3ab1f3ad17fddbba49d8caa876e8
```

The same two hashes hold in the live worktree and in the overlay tree the 816-test suite ran
against — **the bytes proved are the bytes committed**:

```
$ sha256sum src/mambo_power/opf/dc_opf.py src/mambo_power/opf/multiperiod.py    # live worktree
e9b935e1c057482fb5a82a3cd0f5f768211e7a78b3e0cb903593c0a3a1afefcd *src/mambo_power/opf/dc_opf.py
65bb9846d9176e476088e96641408f7cf66a3ab1f3ad17fddbba49d8caa876e8 *src/mambo_power/opf/multiperiod.py
```

The sabotage worktree was removed (`git worktree remove --force`); `git worktree list` shows only
the two real ones. Driver: `<scratch>/sabotage.py`, not committed.

---

## 6. Duplication, re-measured

The measurement script derives both spans from **structural anchors** rather than hard-coded line
numbers (`dc_opf`: between `n_load = len(arr.load_ids)` and `h = highspy.Highs()`; `multiperiod`:
between the `n_periods must be >= 1` raise and the `# --- column layout` banner), and it is run
against the pristine tree first as a control:

```
$ python <scratch>/measure.py <scratch>
[pristine]
  dc_opf span lines 560-627: 68 lines
  multiperiod span lines 322-392: 71 lines
  ratio: 0.7913669064748201
  identical lines (matching blocks sum): 55
[overlay]
  dc_opf span lines 707-719: 13 lines
  multiperiod span lines 319-343: 25 lines
  ratio: 0.631578947368421
  identical lines (matching blocks sum): 12
```

The control reproduces research §7 **to the last digit** — 68/71 lines, `0.7913669064748201`, 55
identical — so this is the same methodology, not a friendlier one.

**Read the identical-line count, not the ratio.** Identical lines fall **55 → 12**, and duplicated
span length falls 68/71 → 13/25. The ratio falls too (0.791 → 0.632), but it is the weaker number
here: the 12 lines that still match are the local alias block —

```python
    c2, c1, c0 = problem.c2, problem.c1, problem.c0
    v1, v2 = problem.v1, problem.v2
    pwl_gen_idxs, segments_by_gen = problem.pwl_gen_idxs, problem.segments_by_gen
    ...
```

— which contains no validation, no guard, and no derivation. Every one of the constructs ADR-008
itemised (the `(n_gen, 3)` shape check, the load-index range check, the `v2/v1/v0` fill, both
convexity guards) now exists exactly once in the repo. **Duplicated logic is zero.**

---

## 7. What W2–W4 inherit

- `_extract_and_validate` / `_ExtractedProblem` in `dc_opf.py`, importable exactly as the four row
  helpers are. `opf.zonal` and `opf.redispatch` should call it rather than re-deriving anything —
  the spec's ownership table already names all four as renderers of this one SSoT, and the
  sabotage sweep is the template for proving each new caller is really wired to it.
- The helper returns coefficients and index sets only. A new caller owns its own column layout,
  its own Hessian assembly, and its own `demand_col_of`. Nothing was parameterised in
  anticipation of zonal or redispatch columns.
- `v0` is carried on the dataclass and used by neither existing caller (`dc_opf` computed it and
  never read it; `multiperiod` computed it and `del`'d it). It is there because it is part of the
  extracted problem and a welfare-accounting caller may want it — but note it is currently
  **unread by any production code path**, so a future slice relying on it should pin it with a
  test of its own.

## 8. Carry-overs and flags

- **FLAG (process) — the shared-worktree contention from M5's S1 recurred exactly as predicted.**
  S1 and S2 run in one checkout; S2's `e8108e4` landed mid-slice. The `git archive` + overlay
  technique handled it again, but it is now two waves in a row that a refactor slice has had to
  build a private tree to state its own acceptance criterion. Worth deciding whether M6's later
  parallel slices get separate worktrees.
- **The ordering change in §1** is the only behaviour difference in this slice and is invisible to
  the suite. If the wave wants it pinned, a test supplying a non-convex `c2` *and* a bad
  `ramp_up_mw` together would do it — I did not add one, because AC-1 forbids test edits and this
  slice's whole claim rests on the suite being untouched.
- **No latent bug surfaced.** The refactor did not turn up any disagreement between the two copies
  beyond the guard message wording noted in §1; nothing in the existing suite had to be
  reinterpreted to stay green.
- `v0`'s unread status (§7) is the one loose thread I would hand to a reviewer.
