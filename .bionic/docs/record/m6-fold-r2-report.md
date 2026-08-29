# M6 fold R2 — closing the Step-6 critic's findings

**Role:** senior-implementor, R2 fold of wave M6 (`zonal-redispatch`).
**Worktree:** `C:\Claude Projects\mambo-power-m6`, branch `wave/06-zonal-redispatch`.
**Baseline:** `232de50` — 992 passed / 4 skipped.
**Head:** `dadfe31` — **992 passed / 4 skipped**, `ruff check .` / `ruff format --check .` / `mypy`
/ `mkdocs build --strict` all exit 0, tree clean.
**Scratch:** one detached worktree (`sab-k`) at `232de50`, used for all four sabotages, restored
after each (`git checkout -- .`, `git status --porcelain` empty), every touched file verified
sha256-identical to its `232de50` blob (table in §6), worktree removed. `git worktree list` now
shows only the two real ones.
**Everything below is `command + output`.** Nothing is marked `unverified`.

Test count is unchanged because every change is a *guard* — a strengthened assertion or a
docstring. No test was added or removed.

---

## Commits

| commit | item | what |
|---|---|---|
| `7c7b2da` | **1 (HIGH)** — critic (k) | `CASE300_CONGESTION_ATOL = 0.5` + sup-norm assertion; clauses renumbered 1–4 |
| `b1f00da` | **4 (LOW)** — critic (q) | AC-5(a) recomputes its own cut-set premise from `net` |
| `2f7cbe6` | **3 (LOW)** — critic (l) | docstring: the residual is `cost_final − cost_nodal`; what the test cannot catch |
| `fadf350` | **2 (MED)** — critic A33(i) | `docs/hooks/pydantic_fields.py` guard is per model, not per package |
| `dadfe31` | *not in the brief* | `ruff format` on `docs/manual/zonal.md` — a **pre-existing CI break** at `232de50` (§5.2) |

Item 5 (fold-a report `(e)` staleness) is a prose append to
`.bionic/docs/record/m6-fold-a-report.md`. No commit: `.bionic` is an untracked symlinked store
(`git ls-files .bionic` is empty), shared by both worktrees.

---

## 1 — item (k): the case300 price check now bounds what it compares · `7c7b2da`

### 1.1 The change

`tests/unit/test_market_zonal.py`. The critic's §1.5 repair, applied as given: a
`CASE300_CONGESTION_ATOL = 0.5` constant carrying the measurement and the 1.6x-headroom reasoning,
and

```python
    # 2. and it is no wider than the face is.
    assert np.max(np.abs(difference)) <= CASE300_CONGESTION_ATOL, (
        "the congestion components differ by more than the measured degenerate face is wide -- "
        "that is a price defect, not the known degeneracy"
    )
```

placed **after** the `> CASE300_FACE_IS_LOAD_BEARING_ATOL` vacuity guard and **before** the two
least-squares clauses, so the pair brackets the difference in `[0.1, 0.5]`. The docstring's clause
list went from three to four and every cross-reference in the file's assertion messages was
renumbered with it.

### 1.2 Power proof, part 1 — the critic's five variants, reproduced at head

The brief's requirement is that the proof sabotage the **congestion attribution specifically**, not
the whole solution. Probe: solve case300 once through the test module's own `_cleared`, then
re-evaluate every clause with the chain's congestion vector transformed post hoc (energy,
`at_rating` and `priced` untouched — nothing else in the test reads anything else).

```
$ uv run --no-sync python .../probe_k.py "C:/Claude Projects/mambo-power-m6"
LOADED zonal: C:\Claude Projects\mambo-power-m6\src\mambo_power\market\zonal.py
LOADED test : C:\Claude Projects\mambo-power-m6\tests\unit\test_market_zonal.py
variant      clause1  sup|diff|    clause2  clause3  NEW<=0.5  old verdict  new verdict  sup|LMP-LMPref|
--------------------------------------------------------------------------------------------------------
baseline    5.40e-06     0.3188  4.025e-16   0.2977      True         PASS         PASS           0.3188
sign flip   5.40e-06     2.6897  2.665e-15   0.2977     False         PASS         FAIL           2.6897
x2          5.40e-06     1.3451  9.992e-16   0.2977     False         PASS         FAIL           1.3451
x10         5.40e-06    12.1045  8.882e-15   0.2977     False         PASS         FAIL          12.1045
zeroed      5.40e-06     1.3448  8.882e-16   0.2977     False         PASS         FAIL           1.3448

median |LMP_nodal| = 39.96387548338848
```

Every number reproduces the critic's §1.3 table, including the point that made it a refutation:
**clause 3's residual is numerically identical (0.2977) in every row**, and the old clause set
passes all five. The new clause is `False` on all four defects and `True` on baseline. Run twice —
before the edit and again at `dadfe31` — identical both times.

### 1.3 Power proof, part 2 — the reachable defect, both directions

Scratch worktree `sab-k` at `232de50`. One edit at `market/zonal.py`'s `lmp_decomposition` call —
a sign error in the redispatch stage's flow-limit dual convention, the class `opf/redispatch.py`'s
own tripwire comment names:

```python
    import dataclasses as _dc  # SABOTAGE-K
    lmp = lmp_decomposition(
        _dc.replace(final.duals, flow_limit=-final.duals.flow_limit), final.ptdf
    )
```

Confirmed the sabotaged module is the one under test before running anything:

```
$ PYTHONPATH="$SC/src;$SC" uv run --no-sync python -c "..."
LOADED zonal : C:\Users\...\scratchpad\sab-k\src\mambo_power\market\zonal.py
SABOTAGE present: True
```

**Old test (the file as committed at `232de50`), under SABOTAGE-K:**

```
$ PYTHONPATH="$SC/src;$SC" uv run --no-sync python -m pytest \
    "$SC/tests/unit/test_market_zonal.py::test_ac4_case300_prices_agree_except_across_the_degenerate_face" -q
.                                                                        [100%]
1 passed in 2.47s
```

**New test, same sabotaged `src`:**

```
E       AssertionError: the congestion components differ by more than the measured degenerate face
        is wide -- that is a price defect, not the known degeneracy
E       assert np.float64(2.689708496376853) <= 0.5
1 failed in 3.26s
```

2.6897 is exactly the critic's measured `sup|LMP_chain - LMP_nodal|` under this defect, on a system
whose median `|LMP_nodal|` is 39.96 $/MWh. **Audit F2 is closed.**

---

## 2 — A33(i): the griffe guard is per model · `fadf350`

### 2.1 The change

The guard was a package-wide `attached == 0` in `PydanticFieldDescriptions.on_package`. It is now
that *plus* a per-model check. The key design point, and the reason a naive per-model counter would
not have worked: **the check runs in `on_package`, not inside `_document`.** The critic's sabotage
returns early from `_document`, so any guard `_document` computes is bypassed. A new
`_undocumented(cls)` recomputes, from the real class, which of `cls`'s own fields carry a
`description=`, have a griffe `Attribute` member to publish it on, and no explicit attribute
docstring of their own to defer to. A model with such fields and nothing attached is collected and
warned about by name; under `--strict` a warning fails the build.

The predicate is deliberately not "has `model_fields` and attached zero" alone: a model whose
fields all legitimately carry explicit attribute docstrings, or carry no description, attaches zero
correctly and must not warn. The baseline build below confirms no such false positive exists across
the package.

### 2.2 Power proof — the critic's exact partial sabotage

`if cls.module.path.startswith("mambo_power.results"): return 0` at the top of `_document`, in
scratch worktree `sab-k`, `mkdocs build --strict` via the m6 venv's interpreter.

**Old guard, partial sabotage** (reproduces the critic's measurement exactly):

```
INFO    -  pydantic_fields: pydantic_fields: documented 88 field(s) in mambo_power
EXIT=0
```

**New guard, same sabotage:**

```
INFO    -  pydantic_fields: pydantic_fields: documented 88 field(s) in mambo_power
WARNING -  pydantic_fields: 26 pydantic model(s) have fields carrying a description= and had none
           of them attached, so their field lists will render empty:
           mambo_power.results.feasibility.FeasibilityReport, ...,
           mambo_power.results.zonal.MarketZonalResult, mambo_power.results.zonal.ZonePriceResult
Aborted with 1 warnings in strict mode!
EXIT=1
```

All 26 are named, `MarketZonalResult` among them — the model walk D2 / ADR-009 consequence 6 is
actually about.

**New guard, baseline** — no false positive anywhere in the package:

```
$ uv run --no-sync mkdocs build --strict
INFO    -  pydantic_fields: pydantic_fields: documented 217 field(s) in mambo_power
EXIT=0
```

`mypy --strict docs/hooks/pydantic_fields.py`: `Success: no issues found in 1 source file`.

### 2.3 What this does *not* close

The critic's A31 F1 note stands. AC-8's four clauses still cannot detect an unrendered field list;
what changed is that the extension now detects its own partial failure. The criterion-side hole is
where the audit left it.

---

## 3 — item (l): the docstring says what the residual is · `2f7cbe6`

Re-measured independently rather than taken from the critic (`_generation_cost` evaluated on the
network's own curves at both the chain's final point and `solve_nodal`'s):

```
--- bid ---
  LHS (payment+gap)        = 0.9411149694290089
  RHS (test's compensation)= 0.9410544288693927
  LHS - RHS                = 6.054055961612903e-05
  cost_final - cost_nodal  = 6.054055961612903e-05
  |(LHS-RHS)-(cf-cn)|      = 0.000e+00
--- fixed_load ---
  LHS - RHS                = -2.6489033189136535e-11
  cost_final - cost_nodal  = -2.6489033189136535e-11
  |(LHS-RHS)-(cf-cn)|      = 0.000e+00
```

Exactly zero on both fixtures. The docstring now states that the right-hand side is **not**
independent of the left (`_served_bid_value` calls the same `_demand_value` production uses), that
the identity therefore reduces exactly to `cost_final - cost_nodal`, and the two consequences the
brief asked for:

* `_demand_value`, `_generation_cost` and `load_bid_coeffs` appear on both sides and cancel, so a
  wrong bid-curve evaluation is invisible to this test;
* a failure here may be a defect in the **redispatch LP** rather than the settlement block the test
  is named after — if D1's cost clause degrades past `COMPENSATION_ATOL` this test goes red with no
  settlement code involved, and `test_ac4_the_redispatched_point_is_the_nodal_optimum` should be
  read first.

`COMPENSATION_ATOL`'s own docstring carried the same wrong mechanism ("float cancellation — the two
bid values are ~3.0e5 $/h") and is corrected with it. **The assertion is unchanged**; only prose.

---

## 4 — item (q): AC-5(a) states its own premise · `b1f00da`

### 4.1 The change

`CORRIDOR_PREMISE_ATOL = 1e-9` and ~14 lines at the top of
`test_ac5a_zonal_welfare_is_never_lower_where_the_corridors_are_looser_than_the_network`, summing
each corridor's cut-set ratings **from `net.branches` and `Bus.zone` directly** — not from
`corridors()` — and asserting each cap is at least that sum. The docstring now says the premise is
checked, and that it holds with equality.

### 4.2 The premise, measured

```
 case30: 3 corridors
   ('1', '2'): cap=    1.523704  cut-set sum=    1.523704 over 1 branches  diff=0.0  cap>=sum: True
   ('1', '3'): cap=   16.576769  cut-set sum=   16.576769 over 3 branches  diff=0.0  cap>=sum: True
   ('2', '3'): cap=   19.456188  cut-set sum=   19.456188 over 3 branches  diff=0.0  cap>=sum: True
 case300: 3 corridors
   ('1', '2'): cap=  212.533723  cut-set sum=  212.533723 over 3 branches  diff=0.0  cap>=sum: True
   ('1', '3'): cap=  208.415101  cut-set sum=  208.415101 over 7 branches  diff=0.0  cap>=sum: True
   ('1', '9'): cap=   93.768000  cut-set sum=   93.768000 over 1 branches  diff=0.0  cap>=sum: True
```

The critic's §4 table, reproduced, with the difference measured as **exactly 0.0** on all six. The
premise sits on its boundary; that is precisely why it needed asserting.

### 4.3 Power proof — `min` instead of `sum` in `tests/_zones.py`

**Old test:**

```
1 failed, 1 passed, 41 deselected in 1.58s
>       assert zonal_welfare >= _nodal_welfare(net, nodal) - slack
E       AssertionError: assert 1838084.3860384494 >= (1838084.7114406605 - 0.0018380843860384495)
FAILED ...::test_ac5a_zonal_welfare_is_never_lower_...[case300]
```

case300 red on the bare welfare inequality, naming nothing and pointing at the theorem. **case30
green with its premise equally broken** — the confusing-and-incomplete failure the critic predicted.

**New test, same sabotage:**

```
2 failed, 41 deselected in 1.66s
E  AssertionError: corridor ('1', '3') is capped at 3.29099502095169 MW, below its own cut-set's
   16.576768909781237 MVA of rating -- the zonal LP is a *restriction* here, not a relaxation,
   and AC-5(a)'s inequality is not expected to hold. See the paired reversal test below.
E  AssertionError: corridor ('1', '2') is capped at 1.0 MW, below its own cut-set's
   212.53372307617445 MVA of rating -- ...
```

Both fixtures now fail, both by name, and case30 — which the old test let through — is caught.

---

## 5 — item 5, and one thing the brief did not know about

### 5.1 Item 5: the fold-a report's `(e)` section

A `## Correction (R2 fold, 2026-08-27)` section appended to
`.bionic/docs/record/m6-fold-a-report.md`. History is not rewritten. It names the four sentences in
`### (e)` that no longer describe the tree, points at the existing `## (e2)` addendum as the current
contract, notes that `(e)`'s *market* proof still stands (it is about the cap being unbounded, not
about how "unbounded" is spelled), and carries the re-measurement:

```
$ grep -rn ser_json_inf_nan src/ --include="*.py"
(no matches)

  cap_mw=   inf -> rejected, finite_number
  cap_mw=  -inf -> rejected, finite_number
  cap_mw=   nan -> rejected, finite_number
  cap_mw=  None -> accepted; json={"zone1":"A","zone2":"B","cap_mw":null}
  cap_mw=   0.0 -> accepted; json={"zone1":"A","zone2":"B","cap_mw":0.0}
  cap_mw=   5.0 -> accepted; json={"zone1":"A","zone2":"B","cap_mw":5.0}
```

### 5.2 `232de50` was red in CI, and the brief said it was green · `dadfe31`

Not an R2 finding and not mine. `.github/workflows/ci.yml` runs `uv run ruff format --check .` over
the **whole tree**, markdown code blocks included. At `232de50`, in a clean detached worktree:

```
$ uv run --no-sync ruff format --check "$SC"
unformatted: File would be reformatted
   --> docs\manual\zonal.md:229:58
    - market.CorridorLimit(zone1="A", zone2="B", cap_mw=None)   # copper plate
    + market.CorridorLimit(zone1="A", zone2="B", cap_mw=None)  # copper plate
1 file would be reformatted, 166 files already formatted
```

Three comment alignments, from fold-b's docs commit. Verified red at `232de50` **before** touching
the live tree. Fixed by running `ruff format` on that one file; whitespace only, no prose or
semantics changed. **Flagging it because the brief's "all gates green at `232de50`" is not accurate
for that gate, and this would have blocked the merge.**

---

## 6 — Scratch-worktree hygiene

One detached worktree, `sab-k` at `232de50`, reused for all four sabotages, restored between each.
`PYTHONPATH="$SC/src;$SC"` throughout, loaded `__file__` printed and checked before the first run.
After the last restore, every file that was ever edited in it, CR-normalised, against its `232de50`
blob:

| file | scratch sha256 | `232de50` blob sha256 |
|---|---|---|
| `src/mambo_power/market/zonal.py` | `7a1c0cb51ded…e01e194a6ea0` | `7a1c0cb51ded…e01e194a6ea0` |
| `tests/unit/test_market_zonal.py` | `04c6b2658064…7289faf97e3464` | `04c6b2658064…7289faf97e3464` |
| `tests/_zones.py` | `d8ad227ab8a5…0126771535ed` | `d8ad227ab8a5…0126771535ed` |
| `docs/hooks/pydantic_fields.py` | `4413955cca2c…7814b67d34dd8` | `4413955cca2c…7814b67d34dd8` |

`git status --porcelain` empty in the scratch tree; `git worktree remove --force` run; the path no
longer exists; `git worktree list` shows only `mambo-power` and `mambo-power-m6`.

**One stray worktree, recorded rather than hidden.** After the final commit, `git worktree list`
also showed a `sab-k2` at `dadfe31`, detached, inside this session's scratchpad. I did not create
it and cannot account for it; the brief says there is no sibling agent on this tree. It was
clean (`git status --porcelain` empty) and at the current head, so it held nothing and changed
nothing. Removed with `git worktree remove --force` plus `git worktree prune`; the listing is now
the two real worktrees only. The live tree's
`site/` build output was removed.

---

## 7 — Revert-and-watch

Every change in this fold is a guard. **Reverting any of them is invisible to the suite by
construction** — that is what a guard is, and claiming otherwise would repeat the mistake the critic
caught in fold-a. So the watch for each row is not "a test goes red"; it is the specific sabotage
that must go red, and the number that must be re-measured if the fixture ever moves.

| commit | reverting it silently loses | the watch: this must go red |
|---|---|---|
| `7c7b2da` | any bound at all on case300's congestion **magnitude**; the test returns to passing with the component sign-flipped, doubled, x10 or zeroed | negate `final.duals.flow_limit` at `market/zonal.py`'s `lmp_decomposition` call → `2.6897 <= 0.5` |
| `b1f00da` | AC-5(a)'s premise; a tighter cap in `corridors()` sends the *inequality* red instead, blaming the theorem | `corridors()` takes `min` of a cut-set's ratings instead of `sum` → both parametrisations red, naming the corridor |
| `2f7cbe6` | nothing testable — prose only. The risk is a reader debugging `market/zonal.py`'s settlement block for a defect in the redispatch LP | n/a. Re-measure `(LHS - RHS) - (cost_final - cost_nodal)` if either fixture changes; it must stay 0.0 |
| `fadf350` | detection of *partial* extension failure; the site can lose every result model's field list with `--strict` green | `if cls.module.path.startswith("mambo_power.results"): return 0` in `_document` → `mkdocs build --strict` EXIT=1 |
| `dadfe31` | CI's `ruff format --check .` leg goes red again | `uv run ruff format --check .` |

**Two tolerances to re-measure if either fixture is ever regenerated**, because both are pinned
close to a measurement rather than to a theorem: `CASE300_CONGESTION_ATOL = 0.5` against a measured
face width of 0.3188 (1.6x headroom — the narrowest margin introduced in this fold), and
`CORRIDOR_PREMISE_ATOL = 1e-9` against a measured difference of exactly 0.0 on all six corridors.
If case300's degenerate face ever widens past 0.5, the correct response is to re-measure and say so
in the constant's docstring — not to loosen it silently.

---

## 8 — Gates at `dadfe31`

```
$ uv run --no-sync python -m pytest -q
992 passed, 4 skipped, 10 warnings in 212.17s (0:03:32)

$ uv run --no-sync ruff check .
All checks passed!

$ uv run --no-sync ruff format --check .
167 files already formatted

$ uv run --no-sync mypy
Success: no issues found in 50 source files

$ uv run --no-sync mkdocs build --strict
INFO    -  pydantic_fields: pydantic_fields: documented 217 field(s) in mambo_power
MKDOCS EXIT=0

$ git status --porcelain
(empty)
```

992 passed / 4 skipped — identical to the `232de50` baseline, as expected: no test was added or
removed, only assertions strengthened and prose corrected.

---

## 9 — Still open, not assigned to me

The critic's **recommendation 3 — ADR-009 consequence 3's "only" list** — was not in this brief and
I did not touch the ADR. The critic's enumeration stands: perturbing the zonal LP's own merit order
takes 40 tests red, and five of those are outside the ADR's list, two of them acceptance-criterion
rows (AC-5(a)'s relaxation inequality and AC-5(b)'s compensation identity). The ADR contradicts
itself between consequences 1 and 3. The conclusion survives; the supporting sentence does not, and
it is the kind of sentence a later wave cites to prune "redundant" coverage.

The critic's carry to M7 is worth repeating, because item 1 is a second instance of it: **a
replacement test's power proof must show it red under a defect in the specific quantity the
criterion names, not merely red under some sabotage.** Fold-a's sabotage moved the whole solution,
so every clause could have fired for the wrong reason — and clause 1 did, which is exactly why the
vacuity of the other two went unnoticed until the critic sabotaged the narrowest thing the test
claimed to see.
