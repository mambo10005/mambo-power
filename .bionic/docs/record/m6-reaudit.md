# M6 targeted re-audit — AC-4's case300 price clause and AC-5(b)

**Role:** independent auditor, targeted re-audit. Wave M6 (`zonal-redispatch`).
**Read at:** worktree `C:\Claude Projects\mambo-power-m6`, branch `wave/06-zonal-redispatch`,
head `dadfe31` (`git rev-parse HEAD` = `dadfe31e22dbc1ecd1fcf84a1bfa4ffd866297ad`).
**Live worktree read-only throughout** — `git status --porcelain` empty before and after.
One detached scratch worktree (`sab-ra` at `dadfe31`), all sabotages applied there, restored
(`git checkout -- .`, `git status --porcelain` empty, `git diff HEAD --stat` empty, no
`SABOTAGE-*` marker left in `src`), removed; `git worktree list` now shows only the two real ones.
**Nothing committed. No fix applied** — the two repairs I recommend are given as descriptions, not
edits.
**Every claim below carries its command and output**, or is labelled *(source-read)*.
Scope: finding F2 (AC-4's case300 LMP clause) and finding F4 (AC-5(b)) only. Nothing else.

---

## Verdicts

| row | verdict | one line |
|---|---|---|
| **AC-4** | **CONFIRMED** | Clauses 1+2 now compose to a pinned LMP tolerance of **0.501 $/MWh** on case300 — which is what the criterion's wording asks for — and 0.5 is defensible because 0.3188 is the degenerate face's *diameter*, not a sample from it. Four reachable congestion defects the old form passed now go red, including one at 0.60 $/MWh. |
| **AC-5** | **CONFIRMED** | The identity is falsifiable — three of my four settlement-combination sabotages turn it red, by my own hand. The one hole the critic named (a wrong bid-curve evaluation) is **not** untested: `test_the_curve_evaluators_agree_with_the_figures_the_builders_report` catches it, and I drove it red. |

**Recommendations.** AC-4: **discharge.** AC-5: **discharge.**
Two follow-ups, neither a blocker, both stated with their cost in §5.

---

## 1 — AC-4: does the bound catch the *class*, or only the one instance?

### 1.1 Baseline, reproduced

Probe: solve case300 through the test module's own `_cleared`, dump every vector the test reads.

```
$ uv run --no-sync python .../solve_dump.py "C:/Claude Projects/mambo-power-m6" dump1.npz
LOADED zonal: C:\Claude Projects/mambo-power-m6\src\mambo_power\market\zonal.py
LOADED test : C:/Claude Projects/mambo-power-m6\tests\unit\test_market_zonal.py
sup|cong diff| = 0.31878395341163446
sup|energy diff| = 5.40034e-06
n at_rating = 7 n priced(chain) = 5
at_rating: ['branch-147','branch-289','branch-308','branch-310','branch-360','branch-48','branch-83']
priced_chain: ['branch-147','branch-289','branch-308','branch-48','branch-83']
median|LMP_ref| = 39.9639
```

Matches the critic's §1.1 and fold-r2's §1.2 to every digit.

### 1.2 Reachable defects, old test vs new test, same sabotaged `src`

Scratch `sab-ra` at `dadfe31`. One edit site in `market/zonal.py` — the vector handed to
`lmp_decomposition`, i.e. the redispatch stage's flow-limit dual convention, the class
`opf/redispatch.py`'s own tripwire comment names. The **old** test is `232de50`'s committed file
(`git show 232de50:tests/unit/test_market_zonal.py`, confirmed to contain no
`CASE300_CONGESTION_ATOL`); the **new** test is `dadfe31`'s. Both run against the same sabotaged
`src`:

```
$ PYTHONPATH="$SC/src;$SC" uv run --no-sync python -c "..."
LOADED zonal: ...\scratchpad\sab-ra\src\mambo_power\market\zonal.py
SABOTAGE present: True
```

| reachable defect | sup&#124;cong diff&#124; | **OLD** | **NEW** |
|---|---|---|---|
| *(none — baseline)* | 0.3188 | 1 passed | 1 passed |
| `mu × 1.446007` — dual scale error | **0.600** | 1 passed | **1 failed** |
| `mu[branch-83] := 0` — most-binding branch left unpriced | 1.268 | 1 passed | **1 failed** |
| `mu[branch-48] ↔ mu[branch-83]` — dual transposition | 2.342 | 1 passed | **1 failed** |
| sign flip (the critic's) | 2.690 | 1 passed | **1 failed** |
| `mu[branch-48] := 0` | 0.122 | 1 passed | 1 passed |

Failure text, the small one — this is the case the brief asked for, a defect **just above** the
bound rather than 5× it:

```
E   AssertionError: the congestion components differ by more than the measured degenerate face
    is wide -- that is a price defect, not the known degeneracy
E   assert np.float64(0.5999997802479344) <= 0.5
```

The three larger ones fail at `1.2679411141512547`, `2.341894045821611` and `2.689708496376853`
against the same bound. **The bound catches a class, not an instance:** scaling, single-branch
erasure, transposition and sign inversion are four structurally different defects and the same
clause is what stops each. The sign flip reproduces fold-r2's number exactly, so their proof
stands as well — but it is now the weakest of four, not the only one.

### 1.3 Is 0.5 defensible? Yes, and for a better reason than "1.6× the measurement"

**Determinism.** Four fresh processes, same command:

```
sup|cong diff| = 0.31878395341163446    (x4, bit-identical)
n at_rating = 7 n priced(chain) = 5     (x4)
priced_chain: ['branch-147','branch-289','branch-308','branch-48','branch-83']  (x4)
```

That is determinism, not robustness — so I measured the face itself.

**The face, characterised.** Fitting the chain-minus-nodal congestion difference over the seven
at-rating branches recovers the two solves' flow-limit duals:

```
                mu_chain      mu_nodal (= mu_chain - fit)
  branch-48    -0.31882086    +0.00000000
  branch-83    -1.92486965    -1.92477380
  branch-147   +1.70043777    +1.69995396
  branch-289   +0.88715227    +0.88653507
  branch-308   +0.02960937    +0.02982465
  branch-310   +0.00000000    -0.00000000
  branch-360   +0.00000000    +0.31893079
```

**The entire disagreement is one multiplier of magnitude ≈0.319 relocating from `branch-48` to
`branch-360`.** Every other dual agrees to ~6e-4. The optimal dual face is therefore the segment
between those two endpoints — outside it one of the two multipliers changes sign and the point is
dual-infeasible — and the two solves sit at its two ends. Walking the segment:

```
  t=0.00 (chain)              sup|diff|=0.3188
  t=0.25                      sup|diff|=0.2391
  t=0.50                      sup|diff|=0.1594
  t=1.00 (chain adopts nodal) sup|diff|=0.0000
```

So **0.3188 is the face's diameter, not a draw from it.** A different HiGHS build, platform or
vertex pick can only land *inside* the segment and produce a *smaller* difference. 0.5 is not
1.6× a lucky sample; it is 1.57× a quantity nothing legitimate can exceed while the primal
optimum is unchanged. If the primal optimum itself moved, `at_rating` would change and the
`len(at_rating) > len(priced)` assertion and clause 4 would say so.

**This is the argument the fold report should have made, and did not.** Its "1.6x headroom on the
measurement" framing is what invited the brief's suspicion; the measurement is a maximum.

### 1.4 The exposure is on the *lower* guard, not the upper — a new finding

`CASE300_FACE_IS_LOAD_BEARING_ATOL = 0.1` is a **floor** on the same scalar, and from the segment
walk above it is crossed at t≈0.70:

```
  t=0.60  sup|diff|=0.1275   vac(>0.1)=True
  t=0.70  sup|diff|=0.0956   vac(>0.1)=False   <- test goes RED
  t=1.00  sup|diff|=0.0000   vac(>0.1)=False
```

If a future solver version lands the two solves anywhere in the closer 30% of the same face — a
perfectly correct outcome, since every point on it is optimal — **this test fails on a correct
build.** Headroom is 3.19x, but on a quantity that is HiGHS's vertex choice rather than anything
the code does. This is the same hazard class as spec A3 / M5's macOS CI finding, pointed the other
way. It is not a correctness gap and the failure message is actionable ("clauses 3 and 4 are then
vacuous and AC-4's price clause should simply be asserted flat on case300"), so I do not hold the
row for it. Named because the audit and the critic both looked only at the ceiling.

### 1.5 Are clauses 1–4 jointly non-vacuous? Yes — each is moved by a defect no other one sees

Post-hoc re-evaluation of all four clauses against the dumped solve (energy, `at_rating` and
`priced` held as the test computes them):

| defect | c1 energy | c2 ≤0.5 | c3 ≤1e-6 | c4 >0.1 |
|---|---|---|---|---|
| `energy + 0.002` (congestion untouched) | **FAIL** | pass | pass | pass |
| `mu × 1.446` | pass | **FAIL** | pass | pass |
| `congestion + 0.05` uniform | pass | pass | **FAIL** (5.0e-2) | pass |
| `mu[branch-1] += 0.05` (a dual on a *non*-at-rating branch) | pass | pass | **FAIL** (4.2e-2) | pass |
| `mu[branch-360] += 0.3` | pass | pass | pass | **FAIL** |
| cancel the unpriced-face duals | pass | pass | pass | **FAIL** |

Every clause has at least one defect that only it catches. In particular the critic's observation
that clause 3's 4e-16 is an algebraic identity is correct *for in-span defects* — but a dual
landing on a branch that is **not** at rating is out of span, and clause 3 is the only clause that
sees it (sup&#124;diff&#124; stays 0.3188, so clause 2 is blind to it). Clauses 2 and 3 are
complementary, not redundant. Clause 4 is not frozen at 0.2977 as the critic's five variants
suggested — it moves to 0.9694 and 2.9049 under duals placed on the unpriced face, and **fails**
on the two rows above.

### 1.6 What the bracket still does not catch — stated exactly

`[0.1, 0.5]` is a bracket, so anything landing inside it is invisible. Measured through the real
code path, with a defect confined to case300 (`len(mu) > 300` guard, so case30 is untouched — the
LMP path only, three of the five congested branches' duals zeroed):

```
$ SAB_RA="sdrop:47,288,307" PYTHONPATH="$SC/src;$SC" uv run --no-sync python -m pytest \
      "$SC/tests/unit/test_market_zonal.py" -q -p no:randomly
43 passed in 3.84s
  sup|LMP_sabotaged - LMP_true| = 0.261665 $/MWh  (0.65% of median 39.96)

$ ... python -m pytest "$SC/tests/unit" -q -p no:randomly
780 passed in 77.18s
```

**780 passed.** Three of case300's five congested branches can lose their congestion contribution
to the published LMPs and nothing in the unit suite notices. The single-branch version
(`sdrop:47`, `branch-48` alone) is 0.244 $/MWh and equally green.

That is the honest residual. It is also **bounded**, which is the whole difference the fold made:
by clauses 1+2 the test now guarantees

```
sup|LMP_chain - LMP_nodal| <= CASE300_ENERGY_ATOL + CASE300_CONGESTION_ATOL = 0.501 $/MWh
```

— 1.25% of the 39.96 $/MWh median price level, measured actual 0.3187893537. Before the fold the
same quantity was unbounded: the critic demonstrated 12.10 $/MWh green, and by linearity any
multiple. AC-4's wording is "LMPs agree with `market.solve_nodal` **to a pinned tolerance** on
case30 and case300" *(source-read: spec `wave-06-zonal-redispatch.spec.md:113`)*. A pinned
tolerance on case300's LMPs now exists and is 0.501. **The criterion's letter is met, and so is
its substance.** F2 is closed.

---

## 2 — AC-5(b): is "letter-only" resolved?

### 2.1 The identity is falsifiable — my own sabotages, not fold-a's

Four settlement-combination defects at `market/zonal.py:655-657`, scratch tree, run against
`test_ac5b_the_third_figure_is_the_curtailment_compensation`:

| defect | AC-5(b) |
|---|---|
| *(none)* | 1 passed |
| `generation_cost_gap = cost_nodal - cost_zonal` (sign) | **1 failed** |
| `redispatch_payment = cost_final - cost_zonal` (compensation term dropped) | **1 failed** |
| `redispatch_payment = (cost_final - cost_zonal) - (value_zonal - value_final)` | **1 failed** |
| `generation_cost_gap = cost_zonal - cost_final` | 1 passed |

```
E  assert 6.054055961612903e-05 == 0.9410544288693927 ± 0.001      # compensation term dropped
E  assert -0.9409938883097766 == 0.9410544288693927 ± 0.001        # value term sign-flipped
```

The dropped-compensation failure is the one that matters: the test fails *at the compensation
figure itself*, which is exactly the content AC-5(b) claims. The fourth row is green because under
D1 `cost_final − cost_nodal` = 6.05e-5, below `COMPENSATION_ATOL = 1e-3` — so the test cannot
distinguish `− cost_nodal` from `− cost_final`. That is benign and already disclosed: it is the
same 6.05e-5 the docstring now correctly names as D1's generation-cost residual, and D1 is proven
separately by `test_ac4_the_redispatched_point_is_the_nodal_optimum`.

### 2.2 The critic's hole is real *in this test* — and covered by a named sibling

Sabotage the settlement-side value evaluator only: `_demand_value`'s quadratic term scaled by *k*.
This does not touch the LP, so the dispatch is unchanged and only the published figures move.

```
SAB_L=1.0    payment=14.513372   LHS=0.94111497  RHS(prod)=0.94105443  |LHS-RHS|=6.054e-05   AC-5(b): 1 passed
SAB_L=1.10   payment=14.275377   LHS=0.70312022  RHS(prod)=0.70305968  |LHS-RHS|=6.054e-05   AC-5(b): 1 passed
SAB_L=0.5    payment=15.703345   LHS=2.13108870  RHS(prod)=2.13102816  |LHS-RHS|=6.054e-05   AC-5(b): 1 passed
```

`redispatch_payment` — a published field — moves from 14.513372 to 14.275377 and to 15.703345, and
the residual does not budge from 6.054e-05. The critic is exactly right about this test.

**But it is not untested.** Full unit suite under the same sabotage:

```
$ SAB_L="1.10" PYTHONPATH="$SC/src;$SC" uv run --no-sync python -m pytest "$SC/tests/unit" -q
FAILED test_the_curve_evaluators_agree_with_the_figures_the_builders_report
FAILED test_ac5a_tight_corridors_reverse_the_inequality_and_the_payment_pays_inward
4 failed, 776 passed in 52.96s
```

`test_the_curve_evaluators_agree_with_the_figures_the_builders_report`
(`tests/unit/test_market_zonal.py:1107`) pins `_demand_value(bid_coeffs, pwl_bids,
final.demand_dispatch_mw, elastic)` against `final.demand_value` at `rel=1e-12` — the LP builder's
own figure, built from the epigraph/hypograph columns HiGHS returns, a different construction
*(source-read + driven red above)*. So the wave does hold the bid-curve evaluation to an
independent check; it is one test away from AC-5(b), not absent.

The residual blind spot is narrower than "a wrong bid-curve evaluation": it is a defect in
`load_bid_coeffs`, the one input shared by both sides of *that* test too. But `load_bid_coeffs`
feeds the LP objective, so any defect in it moves the dispatch and is caught by the
derivation-anchored and parity tests. There is no reachable settlement-only path left uncovered.

### 2.3 The brief's question, answered directly

> Does a test that provably cannot detect an error in the quantities it names discharge an
> acceptance criterion about those quantities?

No — but that is not this test. AC-5's wording is "`redispatch_payment`, `welfare_gap` and
`generation_cost_gap` are **three distinct fields**" *(source-read: spec `:120-124`)*. The
quantities AC-5(b) names are the three *fields*, and the test detects errors in them: three of my
four combination sabotages turn it red, and the fixed-load pair proves the third field's content
is `value_zonal − value_final` and not a sign flip. The bid-curve *arithmetic* is a different
quantity, it is not what AC-5(b) claims, and it is pinned two hundred lines below in the same file.
**AC-5(b) discharges on its own wording. No narrowing and no waiver is needed.**

### 2.4 "Cannot be tested" vs "was not tested" — the brief's third question

A cheap independent evaluation exists. Every bid in the real fixtures is a quadratic
`PolynomialBid` *(measured: `load-2` … `load-8`, `kind=polynomial`, coefficients
`[-0.2340, 13.5408, 0.0]` … `[-166.5458, 10000.0, 0.0]`; 5 of 20 loads carry a bid; no piecewise
bid anywhere in `case30`)*, so the evaluator is twelve lines reading `net.loads[].bid.coefficients`
and the result's own load rows, importing nothing from `mambo_power.market`:

```python
def bid_value_independent(net, load_rows):
    q = {r.id: r.p_mw for r in load_rows}
    total = 0.0
    for ld in net.loads:
        if ld.bid is None:
            continue
        assert ld.bid.kind == "polynomial"
        c = list(ld.bid.coefficients)          # highest power first
        x = q[ld.id]
        total += sum(a * x ** (len(c) - 1 - k) for k, a in enumerate(c))
    return total
```

Measured against production, live worktree, read-only:

```
  independent value(zonal) = 302419.80168303644
  production  value(zonal) = 302419.80168303644   diff = 0.000e+00
  independent value(final) = 302418.86062860757
  production  value(final) = 302418.86062860757   diff = 0.000e+00
  (payment+gap) - independent compensation = 6.054056e-05
```

Bit-for-bit, and the identity closes at the same 6.05e-5 — so it is a **drop-in replacement** for
`_served_bid_value` in AC-5(b), no tolerance change. Its power, under the same `_demand_value`
sabotage that the committed test cannot see:

```
SAB_L=1.10   RHS INDEPENDENT = 0.94105443   |LHS-RHS| = 2.379e-01  -> FAIL   (ATOL 1e-3)
SAB_L=0.5    RHS INDEPENDENT = 0.94105443   |LHS-RHS| = 1.190e+00  -> FAIL
```

238x the tolerance. **Cost: about twelve lines and one docstring paragraph; no new fixture, no new
solve, no runtime.** This wave has twice been wrong about "cannot be tested"; here the honest
statement is *was not tested in this test, and is tested in the next one*. Substituting the
evaluator would make AC-5(b) self-contained rather than leaning on a sibling. That is an
improvement, not a prerequisite — which is why the verdict is CONFIRMED and this sits in §5.

---

## 3 — The three strongest attacks I made on the R2 fix, and why they failed

1. **"0.5 only catches 2.69, so there is a gap between 0.5 and the smallest tested defect."**
   Refuted by construction: `mu × 1.446007` is a reachable defect at **0.600 $/MWh** that the old
   test passed and the new one fails. There is no untested band above the bound.
2. **"0.3188 is one sample; another platform could see a wider face and 0.5 would be illusory."**
   Refuted by measuring the face: the whole disagreement is a single 0.319 multiplier relocating
   between two branches, the two solves sit at the segment's two ends, and every interior point is
   *closer*. 0.3188 is the diameter. The attack succeeded in the other direction, though — see §1.4.
3. **"Clause 2 is redundant with clause 3, or clause 3 with the primal theorem, so a clause remains
   that nothing can move."** Refuted: a spurious dual on a *non*-at-rating branch leaves
   sup&#124;diff&#124; at 0.3188 (clause 2 blind) and moves clause 3's residual to 4.2e-2; a dual on
   the unpriced face at +0.3 leaves clauses 2 and 3 clean and fails clause 4. All four clauses carry
   a defect only they see.

A fourth attack **succeeded**, and is the honest cost of the fix: §1.6's 780-passing case300-local
defect at 0.26 $/MWh. It is inside the bracket by design.

---

## 4 — What I did not do

- No macOS or Linux run — determinism was measured on this machine only (4 processes). The
  cross-platform claim in §1.3 is an argument from the face's geometry, not a measurement on
  another platform.
- No LP-based enumeration of the dual-optimal face. §1.3's "the segment *is* the face" rests on the
  two solves' measured duals and the sign-feasibility argument, not on a solved dual-feasibility LP.
  A second free direction (e.g. mass on `branch-310`, which both solves price at exactly 0) would
  widen the face; both independent solves putting exactly 0 there is evidence, not proof.
- AC-4's primal half, AC-5(a), AC-5(c), and findings F1/F3/F5 — out of scope, untouched.

---

## 5 — Follow-ups (neither blocks discharge)

**(a) `CASE300_FACE_IS_LOAD_BEARING_ATOL`'s downward fragility (§1.4).** The floor fails on a
correct build if a future solver lands the two solves in the closer 30% of the same face. The
cheapest durable fix is to stop asserting the floor on the *sup-norm* and assert it on the
structural fact instead — that `at_rating` strictly contains `priced` (already asserted) and that
the two solves' priced sets differ — leaving the sup-norm with only its ceiling. Cost: two lines,
one of them a deletion. Alternatively lower the floor to ~0.03 and say in the docstring that it
guards a vertex choice, not a code property.

**(b) AC-5(b)'s independent evaluator (§2.4).** Replace `_served_bid_value` with
`bid_value_independent` in `test_ac5b_the_third_figure_is_the_curtailment_compensation`. Twelve
lines, bit-for-bit agreement at baseline, 238x margin under a `_demand_value` defect. Makes the row
self-proving instead of leaning on `test_the_curve_evaluators_agree_with_the_figures_the_builders_report`.

**Neither is a waiver question.** Both rows discharge on the evidence above; these are hardening.
