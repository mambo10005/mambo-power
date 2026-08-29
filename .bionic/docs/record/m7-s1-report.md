# M7 · S1 — one diagonal-Hessian assembly, three callers; plus the generator-side overlap guard

Slice **S1** of wave M7 (`agents`). Requirement **W1**, acceptance criterion **AC-1** (three
clauses).

- Worktree `C:\Claude Projects\mambo-power-m7`, branch `wave/07-agents`, base `6ca9dcc`.
- **Commit: `a22922d`** — `refactor(m7/S1): one diagonal-Hessian assembly, three callers — plus
  the generator-side overlap guard`.
- Files changed, and no others: `src/mambo_power/opf/dc_opf.py`,
  `src/mambo_power/opf/multiperiod.py`, `src/mambo_power/opf/zonal.py`,
  `tests/unit/test_opf_overlap_guard.py` (new).
- `src/mambo_power/opf/redispatch.py` **untouched**, by design.

Every claim below carries the command that proves it and that command's output. Anything not
proved is labelled `unverified` in the closing section.

---

## 1. What changed

### 1.1 The shared helper

The diagonal-Hessian assembly was a third verbatim copy:

| file | lines at `6ca9dcc` | status |
|---|---|---|
| `dc_opf.py` | 739–759 | copy → now the shared helper |
| `multiperiod.py` | 428–446 | copy → now a caller |
| `zonal.py` | 386–402 | copy → now a caller |
| `redispatch.py` | 352–371 | **not** a copy — the 2×2 `Δ⁺`/`Δ⁻` form, untouched, non-caller |

(Inventory recorded for later citation: M6's equivalent count is why W1 exists.)

All three re-encoded the same four facts: HiGHS's `0.5·xᵀQx` convention (so a generator's entry
is `2·c2[g]` and an elastic load's the sign-mirrored `−2·v2[d]`), the `[gen | demand]` order of
the dispatch prefix, the triangular CSR form a purely diagonal Hessian takes, and the rule that
a Hessian with no nonzero entry is not passed at all — which is what keeps a pure LP a pure LP.

They become one function, `_pass_diagonal_hessian`, in `dc_opf.py` beside `_extract_and_validate`.
*Layout* stays with the caller, the same division of labour `_ExtractedProblem` already draws:

```
dc_opf, zonal_dc_opf   _pass_diagonal_hessian(h, c2, v2, n_gen, n_demand)
                       -> one block, n_gen + n_demand wide

multiperiod_dc_opf     _pass_diagonal_hessian(h, c2, v2, n_gen, n_demand,
                           n_blocks=n_periods, block_stride=per_period_dispatch)
                       -> n_periods blocks; the 3·n_storage storage columns in each
                          carry no quadratic term and stay zero
```

`git show --numstat a22922d` — this commit's own contents, nothing else's (S2, S3 and S6 landed
`7083460`, `832a546`, `df3c849`, `aade93b` on the same branch while S1 was running; the commit was
staged with explicit paths, so none of their files are in it):

```
87	18	src/mambo_power/opf/dc_opf.py
12	18	src/mambo_power/opf/multiperiod.py
4	16	src/mambo_power/opf/zonal.py
184	0	tests/unit/test_opf_overlap_guard.py
```

`multiperiod` sheds 18 lines for 12 (an import, a call, and a two-line rationale comment); `zonal`
sheds 16 for 4. `dc_opf`'s +87 is the helper and its docstring, the new guard, and the guard's
line in the `_extract_and_validate` docstring; its −18 is its own former copy. No guard, no
convention and no CSR construction is written twice any more.

### 1.2 `redispatch.py` is a non-caller, and that is proved, not asserted

Its `Δ⁺`/`Δ⁻` pair carries `2·c2·[[1, −1], [−1, 1]]` — a 2×2 block with off-diagonal entries
(`redispatch._hessian_pairs`, `redispatch.py:227`). Not a copy of this helper, a different
Hessian. Readback (run inside the AC-1(a) overlay tree, so it is the post-change code speaking):

```
mambo_power.opf.dc_opf       imports helper: True   (defines it)
mambo_power.opf.multiperiod  imports helper: True
mambo_power.opf.zonal        imports helper: True
mambo_power.opf.redispatch   imports helper: False
```

`git status` at `a22922d` shows `redispatch.py` unmodified; it is not in the commit's file list.

### 1.3 The generator-side overlap guard — the one deliberate behaviour change

`_extract_and_validate` raised when a *load* index appeared in both `demand_bid_coeffs` and
`demand_pwl_bids`. It had no mirror on the generator side. Added, immediately before the
load-side check it mirrors:

```python
double_charged = [i for i in pwl_gen_idxs if 0 <= i < n_gen and bool(np.any(coeffs[i] != 0.0))]
if double_charged:
    raise ValueError(
        f"generator index(es) {double_charged} appear in both cost_coeffs (nonzero row) and "
        "pwl_costs — a generator's cost must be either polynomial or piecewise-linear, not "
        "both; a PWL generator's cost_coeffs row must be all-zero"
    )
```

Two deliberate details:

- The guard **skips out-of-range generator indices** (`0 <= i < n_gen`). `pwl_costs` has never
  had a generator-index range check, and adding one is outside W1; skipping keeps the guard from
  turning a previously-unvalidated out-of-range index into a new `IndexError`.
- It fires **after** `_convex_pwl_segments` has run, so a PWL curve that is both non-convex and
  doubly charged still raises `NonConvexCostError` first — the existing precedence is unchanged.

`_extract_and_validate`'s docstring now names the new `ValueError` in its raises list.

---

## 2. AC-1(a) — behaviour preservation

**Method.** Two `git archive 6ca9dcc` trees; the three changed source files overlaid onto one of
them; `diff -rq` between them; the **unmodified** M6 suite run from the overlay with `PYTHONPATH`
pointed at its `src`.

### 2.1 Exactly three files differ

```
$ git archive 6ca9dcc | tar -x -C $SP/pristine
$ git archive 6ca9dcc | tar -x -C $SP/overlay
$ for f in src/mambo_power/opf/{dc_opf,multiperiod,zonal}.py; do cp $f $SP/overlay/$f; done
$ diff -rq $SP/pristine $SP/overlay
Files .../pristine/src/mambo_power/opf/dc_opf.py and .../overlay/src/mambo_power/opf/dc_opf.py differ
Files .../pristine/src/mambo_power/opf/multiperiod.py and .../overlay/src/mambo_power/opf/multiperiod.py differ
Files .../pristine/src/mambo_power/opf/zonal.py and .../overlay/src/mambo_power/opf/zonal.py differ
```

Three files, all under `src/mambo_power/opf/`. **Zero test edits** — `diff -rq` names no file
under `tests/`, `fixtures/`, `examples/` or `docs/`.

### 2.2 The overlay is what the run loads

An out-of-tree `pytest_report_header` plugin (`$SP/probe/overlay_probe.py`, deliberately outside
the overlay so it is not one of the differing files) prints, inside the test run's own process:

```
$ cd $SP/overlay && PYTHONPATH="$SP/overlay/src;$SP/probe" python -m pytest tests/unit/test_opf_dc.py -p overlay_probe -p no:cacheprovider
============================= test session starts =============================
platform win32 -- Python 3.12.14, pytest-9.1.1, pluggy-1.6.0
OVERLAY-PROBE mambo_power.opf.dc_opf -> ...\scratchpad\overlay\src\mambo_power\opf\dc_opf.py
OVERLAY-PROBE mambo_power.opf.multiperiod -> ...\scratchpad\overlay\src\mambo_power\opf\multiperiod.py
OVERLAY-PROBE mambo_power.opf.zonal -> ...\scratchpad\overlay\src\mambo_power\opf\zonal.py
OVERLAY-PROBE mambo_power.opf.redispatch -> ...\scratchpad\overlay\src\mambo_power\opf\redispatch.py
OVERLAY-PROBE dc_opf has _pass_diagonal_hessian: True
rootdir: ...\scratchpad\overlay
```

This matters because the venv carries an **editable** install of `mambo_power` pointing at the
real worktree; the readback is what rules that out rather than assuming `PYTHONPATH` wins.

### 2.3 The bytes proved are the bytes committed

```
$ sha256sum <worktree file> <overlay file>
dc_opf       0fd8d14f0588bb5e78283464df5a1eb7b8ebb955e9eb2b0838681b3d1ca7acaf   same=YES
multiperiod  78175ee2042aa2651684851f8f1f8eef597ece8c0b869ebe06baf46665aedea6   same=YES
zonal        e246b0e10cb786133941171334813a52d2079c5ca565a1aa8004f96e607189ad   same=YES
```

### 2.4 The suite

```
$ cd $SP/overlay && PYTHONPATH="$SP/overlay/src;$SP/probe" python -m pytest -q -p overlay_probe -p no:cacheprovider
992 passed, 4 skipped, 10 warnings in 661.05s (0:11:01)
```

**992 passed / 4 skipped** — the M6 close's own numbers, on a tree whose tests are byte-identical
to `6ca9dcc`. AC-1(a) discharged.

---

## 3. AC-1(b) — the helper is live, not cosmetic

**Rule honoured.** The sabotage edits the **engine** only — one line inside `_pass_diagonal_hessian`
in a *copy* of the overlay tree. No test file, no fixture, no `tests/_*.py` helper is touched
(M5 A32: an edit to shared fixture data moves both sides of a comparison and makes a live check
look dead).

**Baseline**, seven modules, unsabotaged overlay:

```
$ python -m pytest tests/unit/test_opf_dc.py tests/unit/test_opf_dc_demand.py \
    tests/unit/test_opf_dc_pwl.py tests/unit/test_opf_dc_case14_pwl.py \
    tests/unit/test_opf_solve_dc_opf.py tests/unit/test_opf_multiperiod.py \
    tests/unit/test_opf_zonal.py -q
100 passed in 10.54s
```

### 3.1 The sabotage that discharges the clause

One line, inside the shared helper:

```python
-        hess_diag[base : base + n_gen] = 2.0 * c2
+        hess_diag[base : base + n_gen] = 2.0 * c2 * (1.0 + 0.25 * n_blocks)
```

```
5 failed, 95 passed in 13.14s
FAILED tests/unit/test_opf_dc_case14_pwl.py::test_objective_cost_matches_hand_built_economic_dispatch_oracle
FAILED tests/unit/test_opf_dc_case14_pwl.py::test_quadratic_generators_dispatch_matches_the_uniquely_pinned_oracle_value
FAILED tests/unit/test_opf_dc_case14_pwl.py::test_pwl_generators_fully_use_their_strictly_cheaper_segments_and_split_the_tied_residual
FAILED tests/unit/test_opf_multiperiod.py::test_pwl_generator_costs_are_period_specific_at_t2
FAILED tests/unit/test_opf_zonal.py::test_case30_zones_joined_by_a_slack_corridor_price_identically
```

**The residual that moves, per caller** — measured, not inferred (baselines taken by driving the
tests' own fixture factories on the unsabotaged overlay tree):

| caller | module | residual | baseline | sabotaged |
|---|---|---|---|---|
| `dc_opf` | `test_opf_dc_case14_pwl.py` | `case14_pwl` total objective cost, $ | `6239.000085788995` | `6262.115817507788` (rel. err. `3.705e-3` against a `1e-4` tolerance) |
| `dc_opf` | same | gen-1's uniquely λ-pinned dispatch, MW | `116.24463977234849` | `93.02217442848982` (oracle `116.2 ± 0.1`) |
| `dc_opf` | same | the tied 30 $/MWh residual split between gen-2 seg3 and gen-3 seg2, MW | `22.75536022765152` (gen-3's `52.75536022765152` less its `30.0` floor; gen-2 sits exactly on its `90.0` floor) | `45.97782557151018` (oracle `22.8 ± 0.1`) |
| `multiperiod` | `test_opf_multiperiod.py` | T=2 horizon objective vs two independent `dc_opf` solves, $ | horizon `12866.91389148627` **=** references `12866.91389148627` | horizon `12965.510033520717` **≠** references `12912.72403104955` |
| `zonal` | `test_opf_zonal.py` | case30 zone-2 minus zone-1 price separation, $/MWh | `0.12135901595232834` | `0.024714161965116332` — under the `0.1` floor (`1000 × CASE30_DUAL_ATOL`) the test asserts it above |

At least one test red in **each** of the three callers' test modules, off **one** line inside the
shared helper. AC-1(b) discharged.

### 3.2 A finding: `test_opf_multiperiod.py` is blind to a *symmetric* defect in the helper

The first sabotage tried was the plainer `2.0 * c2 → 2.5 * c2`:

```
4 failed, 96 passed in 13.90s
FAILED tests/unit/test_opf_dc_case14_pwl.py  (3, the same three residuals as above)
FAILED tests/unit/test_opf_zonal.py::test_case30_zones_joined_by_a_slack_corridor_price_identically
```

`test_opf_multiperiod.py` stayed **green**, and the reason is structural, not accidental. Every
quadratic-cost test in that module compares `multiperiod_dc_opf` against `dc_opf` —
`test_single_period_matches_dc_opf_on_a_real_fixture[case14|case30]` at T=1,
`test_pwl_generator_costs_are_period_specific_at_t2` against two `dc_opf` solves at T=2 — and
both sides now call the same helper, so a defect that depends only on `(c2, v2, n_gen, n_demand)`
moves oracle and subject together and cancels exactly. The module's one elastic-demand test
(`demand_bid_coeffs={elastic: (0.0, 80.0, 0.0)}`, `test_opf_multiperiod.py:777`) has `v2 = 0`, so
no demand-side sabotage can reach it either; that value is the only `demand_bid_coeffs` in the
module (enumerated: `grep -n demand_bid_coeffs tests/unit/test_opf_multiperiod.py` returns exactly
that one line).

That is why the discharging sabotage carries an `n_blocks` dependence: it is asymmetric between
the T=2 subject and its T=1 oracles, so the cancellation does not occur.

**This blindness is created by the unification, not revealed by it** — before this commit
`multiperiod` had its own copy, so a defect in *that* copy would not have moved the `dc_opf`
oracle. It is a real consequence of the change and is disclosed here rather than left for the
audit. It is the exact shape of ADR-009 consequence 3 ("an end-to-end row can be structurally
blind to a stage"). Two things bound it: the whole-suite AC-1(a) run still exercises the helper
through every non-multiperiod absolute oracle, and the AC-1(b) sabotage above does redden the
module. Whether `test_opf_multiperiod.py` should gain an absolute quadratic oracle of its own is
a coverage question outside W1's scope; I did not add one, and flag it for the audit.

### 3.3 A third sabotage that did not produce a usable red — reported, not hidden

`for block in range(n_blocks)` → `range(1)` (drop every period after the first from the diagonal)
was tried as the multiperiod-specific probe. It does not produce a clean failure: the run of
`tests/unit/test_opf_multiperiod.py` alone did **not terminate within ~15 minutes** against a
~5 s baseline, and was killed. The rank-deficient Hessian it leaves apparently sends HiGHS into a
pathologically long solve rather than a wrong answer. Recorded because it was run; it discharges
nothing, and the clause rests on §3.1.

---

## 4. AC-1(c) — the new guard, and its power proof

### 4.1 The measured silent wrong answer, reproduced on the pre-guard build

`uv run --no-sync python .bionic/tmp/m7-a2-overlap-guard-probe.py`, run at `6ca9dcc` before the
guard existed. My own numbers:

```
case14: 5 gens, pwl entries from the model: []
gen 0 true coeffs [c2,c1,c0] = [ 0.04302926 20.          0.        ]

baseline           status=Optimal  objective=7642.591777
correct form       status=Optimal  objective=7708.066811
broken form        status=Optimal  objective=10117.766447

>>> NOT CAUGHT. objective differs from the correct form by 2409.699637
>>> gen 0 dispatch: correct=223.192107 broken=-0.000000

load-side overlap  RAISED ValueError: load index(es) [0] appear in both demand_bid_coeffs and demand_pwl_bids ...
```

| | status | objective ($) | gen-0 dispatch (MW) |
|---|---|---|---|
| correct form (poly row zeroed, curve via `pwl_costs`) | `Optimal` | 7708.066811 | 223.192107 |
| doubly charged (poly row **kept** *and* `pwl_costs`) | `Optimal` | 10117.766447 | −0.000000 |
| **difference** | — | **+2409.699637** | **223.19 → 0.00** |

Matches the spec's measured figures (223.19 → 0.00 MW, +2409.70, status still `Optimal`) exactly.
The failure is silent and plausible: nothing raises, nothing warns, and the LP reports `Optimal`.
`gen_cost_coeffs` maintains the all-zero-row convention by construction, which is why five waves
never hit it; M7 is the first wave that assembles coefficients per round from strategy output.

### 4.2 The committed test

`tests/unit/test_opf_overlap_guard.py`:

```
$ uv run --no-sync pytest tests/unit/test_opf_overlap_guard.py -q
....... [100%]
7 passed in 20.92s
```

| test | what it holds |
|---|---|
| `test_dc_opf_raises_on_a_nonzero_cost_row_beside_a_pwl_entry` | the *exact* input §4.1 solved silently now raises `ValueError`, naming index `[0]`, `pwl_costs`, and the all-zero-row rule |
| `test_the_correct_form_of_the_same_offer_still_solves` | the guard rejects the **overlap**, not the PWL offer: zeroing the row clears `Optimal` and dispatches the generator the broken form pushed to zero (`> 1.0 MW`). Without this, a guard that rejected *every* `pwl_costs` entry would pass the row above |
| `test_a_zero_cost_row_beside_a_pwl_entry_passes_the_guard` | the convention's own shape is accepted — the guard's negative control |
| `test_gen_cost_coeffs_output_never_trips_the_guard` | the producer that maintains the invariant still passes, on `case14_pwl.m`, the repo's fixture that actually carries PWL generators |
| `test_multiperiod_inherits_the_same_guard` | same raise from `multiperiod_dc_opf` |
| `test_zonal_inherits_the_same_guard` | same raise from `zonal_dc_opf` |
| `test_the_load_side_mirror_still_fires` | the message the new guard was shaped after, asserted beside it |

The PWL curve is a 5-point sample of generator 0's **own** quadratic cost, computed from the
repo's own `gen_cost_coeffs` output and the generator's own `p_min`/`p_max` off `NetworkArrays` —
a fixture factory, not a hand-assembled reconstruction. The correct and broken forms therefore
differ only in whether the polynomial row was zeroed.

AC-1(c) discharged, and it is the **one deliberate behaviour change** in W1.

---

## 5. Gates

Run as one chain at `a22922d`, from the worktree root:

```
uv run --no-sync pytest -q --tb=no
uv run --no-sync ruff check
uv run --no-sync ruff format --check .
uv run --no-sync mypy
```

| gate | result | exit |
|---|---|---|
| `pytest` | `1 failed, 1045 passed, 4 skipped, 10 warnings in 203.72s` | 1 |
| `ruff check` | `All checks passed!` | 0 |
| `ruff format --check .` | `172 files already formatted` | 0 |
| `mypy` | `Success: no issues found in 51 source files` | 0 |

`mkdocs build --strict` deliberately not run — a docs slice owns that gate, per the brief.

**The one failure is not S1's.** `a22922d` sits on top of S2's, S3's and S6's commits
(`7083460`, `832a546`, `df3c849`, `aade93b`), so this head is the branch, not the slice.
The failure names its cause outright:

```
$ uv run --no-sync pytest tests/unit/test_api_docs_coverage.py::test_every_public_symbol_is_reachable_from_an_api_page -q --tb=short
E   AssertionError: submodule symbols missing from docs/api pages:
E     mambo_power.market.strategy: MarkupConfig, MarkupStrategy, Observation, PriceTakerConfig,
E     PriceTakerStrategy, RoundRecord, Strategy, build_strategy
```

Every named symbol is S2's `market/strategy.py`, awaiting S8's API page (AC-7). S1 adds one
symbol, `_pass_diagonal_hessian`, which is private and so outside this test's scope. The
independent evidence is §2.4: on a tree carrying **S1's changes and nobody else's**, this same
test — and `test_docstrings.py` beside it — passed, in a run of 992 passed / 4 skipped / **0
failed**.

---

## 6. What I could not prove, and what I am flagging

- **`unverified`** — that `test_opf_multiperiod.py` *should* gain an absolute quadratic oracle of
  its own. §3.2 establishes the blindness by enumeration of that module's quadratic tests and its
  single `demand_bid_coeffs` line; whether to close it is a coverage decision outside W1, and I
  did not make it.
- The single pytest failure in §5 is **verified** as S2's, by the failure's own message (it names
  eight `mambo_power.market.strategy` symbols and nothing else) and by §2.4's run, which carries
  S1's changes and none of the other slices' and passes that test. What I have *not* verified is
  when S8 will close it — that is AC-7's, not mine.
- **Disclosed behaviour change**, as required: the generator-side overlap guard (§1.3, §4). It is
  AC-1(c) itself, not a side effect. Two sub-decisions inside it are also disclosed: the guard
  skips out-of-range generator indices, and it fires after PWL convexity validation so the
  existing `NonConvexCostError` precedence is unchanged.
- **No other behaviour change.** The helper reproduces each caller's previous construction
  exactly, including the two guard conditions (`dim == 0` → return; no nonzero → do not call
  `passHessian` at all). Evidence: §2.4's 992/4.
- `mkdocs build --strict` was **not run** — a docs slice owns that gate, per the brief.
- **Ownership honoured.** S1 edited only `src/mambo_power/opf/{dc_opf,multiperiod,zonal}.py` and
  one new `tests/unit/test_opf_*.py`. `redispatch.py` was not touched. Nothing outside the owned
  list was edited, and nothing outside it was staged (`git show --numstat a22922d`, §1.1).
