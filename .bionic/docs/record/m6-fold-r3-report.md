# M6 fold R3 — the re-audit's two follow-ups

**Role:** senior-implementor, R3 fold. Wave M6 (`zonal-redispatch`).
**Worked in:** worktree `C:\Claude Projects\mambo-power-m6`, branch `wave/06-zonal-redispatch`.
**From:** `dadfe31` (992 passed / 4 skipped). **To:** `9d49727`, one commit, one file.
**Scope:** `.bionic/docs/record/m6-reaudit.md` §5(a) and §5(b). Nothing else.
**Every claim below carries its command and its output**, or is labelled *(source-read)*.

---

## Verdicts

| item | done | one line |
|---|---|---|
| **§5(a)** the load-bearing floor | **fixed, not as proposed** | The re-audit's form is not implementable (`MarketNodalResult` carries no branch duals) and the fragility is on *two* sites, not one. Clause 4 now asserts a **fraction of the disagreement** — invariant along the face — and the vacuity guard is replaced by a *stronger* flat-LMP assertion in the regime where it used to fire. |
| **§5(b)** AC-5(b)'s evaluator | **done as specified** | `_bid_value_from_the_network`, no `market.*` import, bit-identical at baseline, 238x margin under the defect the old form could not see. |

**Gate sweep at the final head, one chain, clean tree.**

```
$ git rev-parse HEAD && git status --porcelain
9d49727d9bec6c540a8df9bb5336f720f33b085a
$ uv run --no-sync python -m pytest -q
992 passed, 4 skipped, 10 warnings in 211.53s (0:03:31)
$ uv run --no-sync ruff check .
All checks passed!
$ uv run --no-sync ruff format --check .
167 files already formatted
$ uv run --no-sync mypy
Success: no issues found in 50 source files
$ uv run --no-sync mkdocs build --strict
INFO    -  Documentation built in 39.33 seconds
```

**Delta against the `dadfe31` baseline: zero.** 992/4 on both sides. No test was added or removed;
one dead helper was deleted.

---

## 1 — §5(a): why I did not take the proposed form

### 1.1 The proposal is not implementable as written

> "assert it on the structural fact instead — that `at_rating` strictly contains `priced` (already
> asserted) and that **the two solves' priced sets differ**"

The second half cannot be written. `priced` is read from `result.branches[].flow_limit_dual`, and
`MarketNodalResult` has no `branches` field at all — its rows are `generators`, `loads`, `buses`
and four settlement scalars *(source-read: `src/mambo_power/results/market.py:39-74`)*. The
reference solve's flow duals never leave `solve_nodal`. The test can only recover them by
inverting the least-squares fit, and that puts a magnitude threshold back in the middle of the
"structural" guard:

```
$ uv run --no-sync python .../face.py
fit of D over at_rating (= mu_chain - mu_nodal restricted to at_rating):
   branch-48     coeff=-0.318821   mu_chain=-0.318821   => mu_nodal=+0.000000
   branch-83     coeff=-0.000096   mu_chain=-1.924870   => mu_nodal=-1.924774
   branch-147    coeff=+0.000484   mu_chain=+1.700438   => mu_nodal=+1.699954
   branch-289    coeff=+0.000617   mu_chain=+0.887152   => mu_nodal=+0.886535
   branch-308    coeff=-0.000215   mu_chain=+0.029609   => mu_nodal=+0.029825
   branch-310    coeff=+0.000000   mu_chain=+0.000000   => mu_nodal=-0.000000
   branch-360    coeff=-0.318931   mu_chain=+0.000000   => mu_nodal=+0.318931
```

`mu_nodal[branch-83]` comes out at `-1.924774` where `mu_chain` is `-1.924870` — a 9.6e-5
difference that is solver noise, not pricing. Any "the priced sets differ" test has to decide
whether 9.6e-5 counts, which is the magnitude threshold the brief asked to remove.

### 1.2 The fragility is on two sites, and clause 4's crosses first

`CASE300_FACE_IS_LOAD_BEARING_ATOL` was asserted **twice** — at `:656` (the sup-norm vacuity guard
the re-audit measured) and at `:676` (clause 4's residual floor) *(source-read, `dadfe31`)*. Both
are absolute floors on quantities that scale together along the face, and clause 4's crosses at
s≈0.664, *before* the guard's s≈0.686. Fixing only the guard would have left the test red on a
correct build.

### 1.3 What the face actually is, reproduced

```
$ PYTHONPATH=".../src;..." uv run --no-sync python .../dump300.py
LOADED zonal: C:\Claude Projects\mambo-power-m6\src\mambo_power\market\zonal.py
LOADED test : C:\Claude Projects/mambo-power-m6\tests\unit\test_market_zonal.py
sup|cong diff| = 0.31878395341163446
sup|energy diff| = 5.400336e-06
sup|cong_chain| = 1.3449300335709538
sup|cong_ref|   = 1.3447784628058994
n at_rating = 7 n priced = 5
median|LMP_ref| = 39.96387548338848

residual off at_rating = 4.025e-16
residual off priced    = 0.297652
RATIO resid_priced/sup = 0.933711
```

Every figure matches the re-audit and the critic. The whole disagreement is one multiplier of
magnitude ~0.319 relocating between `branch-48` and `branch-360`, which §1.1's table shows
directly.

**The optimal dual set is convex**, so every point of the segment between the two solves' duals is
itself an optimal dual — an equally *correct* reference solve. Along that segment the numerator
(`residual off priced`) and the denominator (`sup|D|`) are both homogeneous of degree one in the
same factor, so **their ratio is invariant**. Measured across the whole segment:

```
  s      sup|D|     ratio
  0.000  0.318784   0.9337
  0.500  0.159392   0.9337
  0.700  0.095635   0.9337
  0.950  0.015939   0.9337
  0.990  0.003188   0.9337
```

That is a quantity a guard may key on. `sup|D|` is not: it is HiGHS's choice of vertex.

### 1.4 The fix

Three changes, all in `tests/unit/test_market_zonal.py`:

1. **`CASE300_FACE_CARRIES_FRACTION = 0.5`** replaces the floor in clause 4. The clause now reads
   "at least half of *the disagreement* survives the refit over the priced branches", measured
   0.9337 — 1.87x headroom on an invariant instead of 3x headroom on a vertex choice.
2. **The vacuity guard is deleted.** When the two solves agree to `CASE30_LMP_ATOL`, the test
   asserts the **flat** LMP tolerance A20 said case300 could not have, at
   `CASE30_LMP_ATOL + CASE300_ENERGY_ATOL`, and returns. That is strictly stronger than clauses
   2-4, and it is the only regime in which they have nothing to locate — so no branch of the test
   is assertion-free, and the branch that used to fail now proves *more*.
3. **`CASE300_CONGESTION_IS_PRESENT_ATOL = 0.1`** is new, and is the price of (2). See §1.6.

`assert len(at_rating) > len(priced)` at `:647` is **untouched**. That is the structural statement
that the degenerate face *exists*; it is a property of case300's LP rather than of any vertex pick,
and it is what still reddens when the face is genuinely absent.

### 1.5 RED first, then green — the real test function, correct reference solves

The harness replaces the reference solve's congestion component with the convex combination
`(1-s)*cong_ref + s*cong_chain` and calls
`test_ac4_case300_prices_agree_except_across_the_degenerate_face` with the result. Both endpoints
are optimal duals of the same QP and the optimal dual set is convex, so **every `s` is a correct
build**. `at_rating` and `priced` are read off the chain, which is untouched.

**OLD** — the committed file at `dadfe31`, in a detached scratch worktree:

```
$ PYTHONPATH="$SC/wt-r3/src;$SC/wt-r3" uv run --no-sync python .../facewalk.py "$SC/wt-r3" ...
LOADED zonal: ...\scratchpad\wt-r3\src\mambo_power\market\zonal.py
LOADED test : ...\scratchpad\wt-r3\tests\unit\test_market_zonal.py
  s=0.000  sup|cong diff|=0.318784    PASS
  s=0.500  sup|cong diff|=0.159392    PASS
  s=0.600  sup|cong diff|=0.127514    PASS
  s=0.700  sup|cong diff|=0.095635    FAIL  <- the two solves' congestion components agree on this build
  s=0.800  sup|cong diff|=0.063757    FAIL  <- the two solves' congestion components agree on this build
  s=0.950  sup|cong diff|=0.015939    FAIL  <- the two solves' congestion components agree on this build
  s=1.000  sup|cong diff|=0.000000    FAIL  <- the two solves' congestion components agree on this build
```

**NEW** — the live worktree at `9d49727`:

```
$ PYTHONPATH="...-m6/src;...-m6" uv run --no-sync python .../facewalk.py "...-m6" ...
LOADED zonal: C:\Claude Projects\mambo-power-m6\src\mambo_power\market\zonal.py
LOADED test : C:\Claude Projects/mambo-power-m6\tests\unit\test_market_zonal.py
  s=0.000  sup|cong diff|=0.318784    PASS
  s=0.500  sup|cong diff|=0.159392    PASS
  s=0.600  sup|cong diff|=0.127514    PASS
  s=0.700  sup|cong diff|=0.095635    PASS
  s=0.800  sup|cong diff|=0.063757    PASS
  s=0.950  sup|cong diff|=0.015939    PASS
  s=0.990  sup|cong diff|=0.003188    PASS
  s=0.999  sup|cong diff|=0.000319    PASS
  s=1.000  sup|cong diff|=0.000000    PASS
```

The two points the brief named, side by side: **s=0.70** OLD `FAIL` / NEW `PASS`; **s=0.95** OLD
`FAIL` / NEW `PASS`.

### 1.6 The other direction — the new guard still reddens when the face is absent

Same harness, four constructed cases, old file and new file, `__file__` printed on both runs:

```
[1] face NOT EXERCISED (both solves on the same vertex) -- a correct build, must PASS
    OLD:  FAIL  <- the two solves' congestion components agree on this build -- clauses 3 and 4 ...
    NEW:  PASS

[2] face ABSENT (every at-rating branch priced) -- must FAIL
    OLD:  FAIL  <- expected strictly more at-rating branches than priced ones -- that inequality *is* ...
    NEW:  FAIL  <- expected strictly more at-rating branches than priced ones -- that inequality *is* ...

[3] disagreement NOT face-shaped (lives on the chain's own priced branches) -- must FAIL
    sup|D|=0.3188  OLD: FAIL <- the priced branches alone reproduce the difference ...
                   NEW: FAIL <- the branches the chain prices reproduce 100.0% of the two solves' ...
    sup|D|=0.0500  OLD: FAIL <- the two solves' congestion components agree on this build  [WRONG REASON]
                   NEW: FAIL <- the branches the chain prices reproduce 100.0% of the two solves' ...

[4] common-mode: congestion erased from BOTH solves -- must FAIL
    OLD:  FAIL  <- the two solves' congestion components agree on this build ...
    NEW:  FAIL  <- the chain reports no congestion component on case300, which prices five branches ...
```

Three things to read out of that table.

**The brief's "force both solves to the same active set" is row [1], and it must now pass.** That
is not the face being absent; it is the face not being *exercised*, by a correct build. Rows [2]
and [4] are the cases where something is genuinely wrong, and both still fail. The distinction
between them is the whole content of the fix.

**Row [4] is why `CASE300_CONGESTION_IS_PRESENT_ATOL` exists.** Every clause reads the two
components' *difference*, so a defect erasing congestion from **both** solves leaves that
difference at zero and satisfies all of them. The deleted floor was the only thing catching it.
The replacement is a per-solve statement — measured 1.3449 (chain) and 1.3448 (nodal), pinned at
0.1, and no vertex on the face can move either by more than the face's own 0.319 diameter, so the
durable headroom is 10x.

**Row [3] at `sup|D|=0.05` is a diagnostic improvement, not just a wash.** The old test reddened
there for the wrong reason — it reported that the two solves *agree* when in fact they disagreed
by 0.05 in a shape that proves a defect. The new message quantifies it: `reproduce 100.0%`.

### 1.7 The full defect list, old form vs new, on the dumped solve

Post-hoc evaluation of both clause sets against the same solve, `priced`/`at_rating` as the test
computes them (the re-audit's §1.5 rows plus the ones the critic drove):

```
  defect                               sup|D|     OLD                          NEW
  baseline                             0.318784   green                        green (ratio=0.9337)
  chain cong x 1.446007                0.600000   RED clause2                  RED clause2
  chain cong x 2                       1.345082   RED clause2                  RED clause2
  chain cong x 10                      12.104522  RED clause2                  RED clause2
  chain cong sign-flipped              2.689708   RED clause2                  RED clause2
  chain cong := 0                      1.344778   RED clause2                  RED present
  BOTH cong := 0 (common mode)         0.000000   RED guardA                   RED present
  congestion + 0.05 uniform            0.368784   RED clause3(5.00e-02)        RED clause3(5.00e-02)
  mu[branch-1] += 0.05 (off-face)      0.318784   RED clause3(4.23e-02)        RED clause3(4.23e-02)
  mu[branch-360] += 0.3                0.248758   RED clause4(0.0177<=0.1)     RED clause4(0.0177<=0.1244)
  cancel the unpriced-face duals       0.244339   RED clause4(0.0000<=0.1)     RED clause4(0.0000<=0.1222)
```

**The new form reddens on every row the old one did.** No measured power was traded away.

### 1.8 The residual I am handing back, not fixing

If a future solve puts the **chain** (not the reference) at an interior point of the face, it
prices both `branch-48` and `branch-360`; the difference then lies inside `span(priced)` and
clause 4 goes red — **in the fraction form and in the old floor form alike**:

```
=== the CHAIN moves onto an interior point of the face (priced grows to 6)
  t=0.00  sup|D|=0.318784  priced=5  OLD=green                     NEW=green (ratio=0.9337)
  t=0.25  sup|D|=0.239088  priced=6  OLD=RED clause4(0.0000<=0.1)  NEW=RED clause4(0.0000<=0.1195)
  t=0.70  sup|D|=0.095635  priced=6  OLD=RED guardA                NEW=RED clause4(0.0000<=0.0478)
  t=0.95  sup|D|=0.015939  priced=6  OLD=RED clause4(0.0000<=0.1)  NEW=RED clause4(0.0000<=0.0080)
```

This is **pre-existing and not a regression** — the old form dies on the same rows. It is not
fixable without the reference solve's duals (§1.1). It is also unlikely: the models carry a
Hessian *(source-read: `src/mambo_power/opf/dc_opf.py:750-752`)* and HiGHS returns active-set
duals, so an interior multiplier vector is not what the solver hands back. Named because §1.4 of
the re-audit modelled the face walk with `priced` held fixed, which is faithful to the *reference*
solve moving and not to the chain moving.

---

## 2 — §5(b): AC-5(b) now stands on its own

### 2.1 The hole, reproduced

Detached scratch worktree at `dadfe31`; one edit, `_demand_value`'s quadratic term x1.10
(`src/mambo_power/market/zonal.py:456`).

```
$ PYTHONPATH="$W/src;$W" uv run --no-sync python -m pytest \
      "$W/.../test_market_zonal.py::test_ac5b_the_third_figure_is_the_curtailment_compensation" -q
456:        total += 1.10 * v2 * q**2 + v1 * q + v0
.                                                                        [100%]
1 passed in 1.28s
```

It passes because both sides move together: `redispatch_payment` drops from `14.513371574803273`
to `14.275376829254924` and the production right-hand side from `0.9410544288693927` to
`0.7030596833210438`, leaving the residual at `6.054056e-05` — unchanged to the last bit.

### 2.2 The fix, and that it is a drop-in

`_bid_value_from_the_network(net, load_rows)` reads `net.loads[].bid.coefficients` and the
result's own load rows, importing neither `load_bid_coeffs` nor `_demand_value` — nothing from
`mambo_power.market`. Measured against production on the live tree, before the swap:

```
  independent value(zonal) = 302419.80168303644
  production  value(zonal) = 302419.80168303644   diff = 0.000e+00
  independent value(final) = 302418.86062860757
  production  value(final) = 302418.86062860757   diff = 0.000e+00
```

Bit-for-bit. And after the swap, on the committed head:

```
$ uv run --no-sync python .../resid.py
LOADED zonal: C:\Claude Projects\mambo-power-m6\src\mambo_power\market\zonal.py
LOADED test : C:\Claude Projects/mambo-power-m6\tests\unit\test_market_zonal.py
  case30             RHS_independent=0.9410544288693927  LHS=0.9411149694290089  residual=6.054055961612903e-05
  case30_fixed_load  RHS_independent=0.0  LHS=-2.6489033189136535e-11  residual=-2.6489033189136535e-11
  COMPENSATION_ATOL = 0.001
```

**The residual is unchanged at 6.054056e-05. No tolerance moved.**

### 2.3 Power, same sabotage, same tree

```
### NEW test file + x1.10 sabotage
E       assert 0.70312022388066 == 0.9410544288693927 +- 0.001
E         Obtained: 0.70312022388066
E         Expected: 0.9410544288693927 +- 0.001
1 failed

### NEW test file + x0.5 sabotage
E         Obtained: 2.1310886971125456
E         Expected: 0.9410544288693927 +- 0.001
1 failed
```

x1.10 gives `|LHS-RHS| = 2.379342e-01`, **237.9x** `COMPENSATION_ATOL`.
x0.5 gives `1.190034e+00`, **1190x**.
The independent right-hand side holds at `0.9410544288693927` under both — bit-identical to its
unsabotaged value, which is the independence proof.

### 2.4 Scope: it raises rather than handling piecewise

Every bid in every fixture that reaches this helper is a quadratic `PolynomialBid` — measured
across all three (`case30`: `load-2`…`load-8`, 5 bids, `{'polynomial': 5}`; `case30_fixed_load`:
0 bids; `case300`: `load-1`…`load-6`, 5 bids, `{'polynomial': 5}`) — and this is structural, not
incidental: both derivation rules in `tests/_bids.py` end in
`return PolynomialBid(coefficients=[v2, v1, 0.0])` *(source-read: `:119`, `:185`)*, so `with_bids`
cannot emit a piecewise bid on any case.

So the helper raises `NotImplementedError` naming the load and the kind. The reason is coverage,
not effort: a piecewise branch would be executed by zero fixtures, would ship as untested dead
code, and could not be sabotage-proved. It would also be easy to get subtly wrong — production's
`_pwl_curve_value` takes the **minimum over each segment's affine extension**, the hypograph
encoding, which is not the polyline outside the breakpoint range *(source-read:
`src/mambo_power/market/zonal.py:385-411`)*. A second, independently re-derived copy of that is
exactly the "second, subtly different definition" this helper family exists to avoid. Repo
precedent: `tests/_bids.py::fleet_max_marginal_cost` raises rather than silently ignoring a
piecewise generator cost.

### 2.5 One deviation from the brief

`_served_bid_value` had **no callers left** after the swap. I deleted it rather than leave dead
code, and retargeted the new helper's docstring contrast to `_welfare`, which makes the same point
("reuse the chain's own extractors on purpose, so the test measures the relationship and not the
gap between two definitions of welfare") and is still live. The sibling
`test_the_curve_evaluators_agree_with_the_figures_the_builders_report` is untouched, as asked.

---

## 3 — Hygiene

One detached scratch worktree (`wt-r3` at `dadfe31`), every sabotage applied there, restored and
removed:

```
$ git checkout -- .
--- git status --porcelain ---
--- git diff HEAD --stat ---
456:        total += v2 * q**2 + v1 * q + v0
$ git worktree remove .../wt-r3 && git worktree list
C:/Claude Projects/mambo-power     4cfd1d7 [epic/01-foundation]
C:/Claude Projects/mambo-power-m6  9d49727 [wave/06-zonal-redispatch]
```

Verified by `git status` / `git diff`, not by hash: a fresh `git worktree add` checkout picks up
CRLF, so a sha256 against the live tree differs spuriously.

One commit, explicit path, `tests/unit/test_market_zonal.py` only: `9d49727`, 134 insertions,
57 deletions.
