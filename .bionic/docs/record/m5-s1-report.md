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

# M5 S1 — core-extraction (W1, AC-1)

Slice: S1 `core-extraction`. Role: senior-implementor. Branch `wave/05-multiperiod`,
base `e88752c`. Commit: **`fbab76d`** — `refactor(m5/S1): extract dc_opf's row families into
internal helpers`. Not pushed.

**Both halves of AC-1 hold.** Behaviour is preserved (654 → 654, zero test edits, oracle parity
unchanged) and the extraction is real rather than cosmetic (every helper is on `dc_opf`'s live
code path; breaking any one of them takes the suite red).

Every factual claim below carries the command that produced it and that command's output.

---

## 1. What changed

One file: `src/mambo_power/opf/dc_opf.py`, `+231 / −80`.

```
$ git show --stat fbab76d
 src/mambo_power/opf/dc_opf.py | 311 +++++++++++++++++++++++++++++++-----------
 1 file changed, 231 insertions(+), 80 deletions(-)
```

`dc_opf()`'s per-period row construction is now four internal helpers that `dc_opf()` itself
calls:

| Helper | Row family |
|---|---|
| `_balance_row(injection_cols, withdrawal_cols, fixed_mw)` | the system-wide nodal-balance equality row |
| `_flow_limit_rows(ptdf, injection_cols, injection_bus, withdrawal_cols, withdrawal_bus, rating_mw, const_mw)` | one PTDF-based flow-limit row per branch |
| `_epigraph_rows(segments_by_gen, gen_cols, cost_col_of)` | convex-PWL generator cost rows |
| `_hypograph_rows(segments_by_load, demand_col_of, val_col_of)` | concave-PWL demand-bid rows |

Each *returns* a `_RowBlock` — the CSR triple `Highs.addRows` takes — and none of them touches a
`highspy.Highs` object. `_add_rows(h, block)` is the only place a row family meets the solver,
and `_dense_csr` is the shared CSR construction for the two dense families. `dc_opf()` remains
the only thing in the module that owns a solver object.

### Shape decisions, and why

- **Helpers take the LP column indices their coefficients attach to** (`injection_cols`,
  `gen_cols`, `cost_col_of`, …) rather than assuming `dc_opf`'s own `[gen | demand | cost_g |
  val_d]` layout, and none holds or mutates state across calls. That is the minimum needed for
  ADR-007's "one place the balance row is assembled" to be *literally* true for a caller that
  builds the same family once per period, and it is the whole of what was added for such a
  caller — no period, ramp, storage or `T` parameter appears anywhere in this slice.
- **The balance/flow helpers are named by algebra, not by entity** (`injection_cols` /
  `withdrawal_cols` rather than `gen_cols` / `demand_cols`). The row genuinely does not care what
  a column represents, only which side of the balance it sits on; `dc_opf` passes its generator
  columns as injections and its elastic-load columns as withdrawals.
- **`_epigraph_rows` and `_hypograph_rows` stay two mirror functions** rather than one function
  with an orientation flag. The in-repo precedent is deliberate and adjacent:
  `_convex_pwl_segments` / `_concave_pwl_segments` are already a mirror pair for exactly this
  reason, so each side reads as its own derivation.
- **The dense coefficient pattern is preserved exactly, structural zeros included.** The pre-M5
  code handed HiGHS a dense `(1 + n_branch) × n_dispatch` block with explicit zeros; `_dense_csr`
  reproduces that byte-for-byte rather than dropping structural zeros. Dropping them would be a
  mathematically identical LP but could move the simplex's vertex choice on a degenerate problem
  — which would move duals, which is precisely what four waves of oracle parity pin down.
- **Column creation was left in `dc_opf`.** The brief scopes S1 to row-family construction; the
  free `cost_g` / `val_d` column block is entangled with the Hessian-ordering constraint
  documented above it, and moving it is neither asked for nor needed to make a `T`-loop possible.

### Explicitly not done

No period/ramp/storage/multiperiod concept was added; `opf/multiperiod.py` was not created;
nothing under `model/`, `numerics/`, `market/`, `jobs/` was touched; no `__init__.py` was touched
(so the collision M3's S2/S4 and M4's S1/S2 both hit did not recur). No test was added, modified,
renamed or deleted — see §3.

---

## 2. AC-1 half 1 — behaviour preserved

### 2.1 The isolation problem, and how it was solved

**A finding worth recording:** S2 and S3 are running in the *same* worktree
(`C:\Claude Projects\mambo-power-m5`), not in separate ones. Partway through this slice the tree
held S3's commit `d0031cb` plus S2's uncommitted `model/` changes and its new
`tests/unit/test_period_scenario.py`. A "654 passed, zero test edits" claim cannot be made
against that tree: the count drifts as sibling slices land, and repo-wide `ruff check` was red on
S2's in-flight file.

The proof was therefore moved to an isolated tree extracted from the base commit:

```
$ git archive e88752c | tar -x -C <scratch>/s1proof
$ cd <scratch>/s1proof && PYTHONPATH=<scratch>/s1proof/src \
    <m5>/.venv/Scripts/python.exe -c "import mambo_power; print(mambo_power.__file__)"
C:\...\scratchpad\s1proof\src\mambo_power\__init__.py
```

The venv's editable install is a plain `.pth` path entry, so a `PYTHONPATH` prefix wins; the
readback above confirms imports resolve into the isolated tree, not the shared worktree.

### 2.2 Zero test edits — proven by content, not by assertion

Every tracked file in the isolated tree was compared against its `e88752c` blob (line-ending
normalised):

```
files differing from e88752c in the isolated tree: ['src/mambo_power/opf/dc_opf.py']
```

Exactly one file differs, and it is not a test. This is a stronger statement than "I did not edit
a test": nothing under `tests/` differs from the base commit by even a byte.

### 2.3 Baseline and post-change suite, same isolated tree

```
$ pytest -q -p no:cacheprovider          # e88752c, unmodified
654 passed, 10 warnings in 395.03s (0:06:35)

$ pytest -q -p no:cacheprovider          # e88752c + this dc_opf.py, nothing else
654 passed, 10 warnings in 436.63s (0:07:16)
```

654 → 654, reconciling exactly against the briefed baseline. An earlier independent run in the
shared worktree, started before any sibling slice had landed, also reported
`654 passed, 10 warnings in 324.22s` — three independent readings of the same number.

### 2.4 Oracle parity, called out explicitly

```
$ pytest -q -p no:cacheprovider tests/parity        # extraction applied
196 passed, 10 warnings in 64.16s (0:01:04)

$ pytest -q -p no:cacheprovider \
    tests/parity/test_opf_vs_pandapower.py tests/parity/test_opf_vs_pypsa.py \
    tests/parity/test_market_nodal_vs_pandapower.py \
    tests/parity/test_ac_vs_matpower_stored.py tests/parity/test_matpower_vs_pandapower.py
91 passed, 9 warnings in 33.55s
```

MATPOWER (`test_ac_vs_matpower_stored.py`, `test_matpower_vs_pandapower.py`), pandapower
(`test_opf_vs_pandapower.py`, `test_market_nodal_vs_pandapower.py`, `test_dc_vs_pandapower.py`, …)
and PyPSA (`test_opf_vs_pypsa.py`) all pass unmodified. These are the same tests, against the same
fixtures, with the same tolerances as at `e88752c` — §2.2 proves not one of them was touched.

### 2.5 Lint and types

```
$ uv run --no-sync ruff check src/mambo_power/opf/dc_opf.py
All checks passed!
$ uv run --no-sync ruff format --check src/mambo_power/opf/dc_opf.py
1 file already formatted
$ uv run --no-sync mypy
Success: no issues found in 43 source files
```

`mypy` is repo-wide and clean. `ruff` is reported **scoped to `dc_opf.py`** deliberately:
repo-wide `ruff check` was red at the time on `tests/unit/test_period_scenario.py`, S2's
uncommitted file — not this slice's, and not this slice's to fix. Fixing the annotations to get
here was real work, not a formality: the first pass typed the flow helper's bus arguments as
int32 and mypy caught that `NetworkArrays`'s bus arrays are int64, which is why the module now
carries a `ColArray` (int32, HiGHS's own index width) alias distinct from
`numerics.arrays.IntArray` (int64, every bus index array).

---

## 3. AC-1 half 2 — the extraction is real, not cosmetic

Three distinct failure modes had to be ruled out: helpers nobody calls, helpers that *duplicate*
rather than replace the inline assembly, and helpers that are dead code beside a surviving copy.

### 3.1 The inline assembly is gone

`dc_opf()`'s body between `compute_ptdf()` and `h.run()` is now, in full:

```python
    n_rows = 1 + arr.n_branch
    gen_cols = np.arange(n_gen, dtype=np.int32)
    demand_cols = np.arange(n_gen, n_dispatch, dtype=np.int32)

    _add_rows(h, _balance_row(gen_cols, demand_cols, total_fixed))
    _add_rows(h, _flow_limit_rows(ptdf_matrix, gen_cols, arr.gen_bus, demand_cols,
                                  arr.load_bus[elastic_idx_arr], rating_mw, const))
    _add_rows(h, _epigraph_rows(segments_by_gen, gen_cols, cost_col_of))
    _add_rows(h, _hypograph_rows(demand_segments_by_load, demand_col_of, demand_val_col_of))
```

(comments elided; the code is verbatim). No `np.vstack`, no dense-block assembly, no per-segment
CSR loop remains in `dc_opf`.

### 3.2 Exactly one implementation of each family

```
$ grep -n "addRows" src/mambo_power/opf/dc_opf.py
11:  ...docstring...
54:  ...docstring...
335: ...docstring...
368:    h.addRows(
```

One executable `h.addRows` call in the entire module — inside `_add_rows`. The other three hits
are prose. Each helper is defined once and called once from `dc_opf`:

```
$ grep -n "_balance_row(\|_flow_limit_rows(\|_epigraph_rows(\|_hypograph_rows(\|_add_rows(\|_dense_csr("
396,421,455,488  (defs)   379 (def _dense_csr)  359 (def _add_rows)
411,442          (_dense_csr call sites, inside the two dense helpers)
727,728,730,743,744  (dc_opf's own calls)
```

```
$ grep -rn "_balance_row\|_flow_limit_rows\|_epigraph_rows\|_hypograph_rows\|_RowBlock\|_add_rows\|_dense_csr" src/ tests/ examples/ docs/ | grep -v "opf/dc_opf.py"
Binary file src/mambo_power/opf/__pycache__/dc_opf.cpython-312.pyc matches
```

Nothing outside `dc_opf.py` references them (the only hit is a stale bytecode cache), so there is
no second copy anywhere in the repo.

### 3.3 Breaking each helper takes the suite red

A reading proves the helpers *look* wired in. This proves it. Each helper was broken in turn in
the isolated tree — a perturbed constant, a scaled coefficient, an early return — and a fast
opf/market/parity subset was run with `-x`:

| Helper broken | How | Subset result |
|---|---|---|
| `_balance_row` | RHS `fixed_mw` → `fixed_mw + 1.0` | `1 failed, 1 passed in 1.09s` |
| `_flow_limit_rows` | rating halved in both bounds | `1 failed, 1 passed in 1.28s` |
| `_epigraph_rows` | segment slope × 1.05 | `1 failed, 5 passed in 1.27s` |
| `_hypograph_rows` | segment slope × 1.05 | `1 failed, 10 passed in 1.42s` |
| `_dense_csr` | all coefficients × 1.01 | `1 failed, 1 passed in 1.21s` |
| `_add_rows` | return before `h.addRows` | `1 failed, 1 passed in 1.31s` |

6 of 6 go red. (`-x` stops at the first failure, which is why the pass counts are small — the run
is aborted, not survived.) The driver then restored the file and asserted byte-equality:

```
reverted; file restored byte-identical to the extraction under test
```

and the same subset was re-run against the restored file:

```
$ pytest -q -p no:cacheprovider --no-header <subset>
62 passed in 9.27s

$ diff -q <scratch>/s1proof/.../dc_opf.py <m5>/src/mambo_power/opf/dc_opf.py
identical
```

The file the suite was proved against in §2.3 and the file committed as `fbab76d` are the same
bytes.

Driver: `<scratch>/sabotage.py` (scratchpad, not committed — it mutates a throwaway tree and
restores it; nothing in the repo depends on it).

---

## 4. What S4 inherits

- Four helpers that build the same balance / flow / epigraph / hypograph rows against **any**
  column layout, and a `_RowBlock` + `_add_rows` pair that lets a caller decide how many blocks
  it needs and in what order its rows are numbered.
- The row-index contract `dc_opf` relies on and S4 must re-establish for itself: the balance row
  is row 0 and flow-limit rows are `1..n_branch` *because* they are added first;
  epigraph/hypograph rows are appended after them as an internal encoding detail and are never
  part of `OpfSolution`/`OpfDuals`' shape.
- Nothing decided on S4's behalf. There is no `T`, no period offset, no storage column and no
  ramp row in this slice, and the helpers were not given parameters in anticipation of them.

## 5. Carry-overs and flags

- **FLAG (process, not code) — the three parallel slices share one worktree.** The plan's
  "S1, S2 and S3 run in parallel (disjoint files)" held for *files*, but they are disjoint inside
  a single checkout, so no slice can run the full suite and reconcile it against the wave
  baseline once a sibling has landed. S1 worked around it with an isolated `git archive` tree
  (§2.1); S4/S5 will hit the same wall harder, since their ACs are behavioural rather than
  refactor-shaped. Worth the orchestrator deciding whether later parallel slices get separate
  worktrees.
- **Not a defect, but worth naming:** repo-wide `ruff check` is currently red on
  `tests/unit/test_period_scenario.py` (S2's file, unsorted imports + one 101-char line) as of
  this slice's completion. It is S2's to fix, and it is why §2.5's ruff evidence is file-scoped.
- No behaviour change was found. The refactor did not surface any latent bug in `dc_opf`, and
  nothing in the existing suite had to be reinterpreted to stay green.
