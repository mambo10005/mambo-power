# M6 critic — Step 6 adversarial

**Role:** independent critic, wave M6 (`zonal-redispatch`).
**Read at:** `wave/06-zonal-redispatch`, head `cb6dfa9` at start; fold-b landed `7fd6cbe → 232de50`
(docs/examples only — `git diff --stat cb6dfa9 232de50` = `docs/manual/zonal.md`,
`examples/11_zonal_redispatch.py`) while I worked. **Every src/tests measurement below is on the
tree those commits do not touch, so all of it stands at `232de50`.**
**Live worktree: read-only throughout.** Three detached scratch worktrees (`sab-critic`, `sab-k`,
`sab-docs`), all restored (`git checkout -- .`, `git status --porcelain` empty), content verified
byte-identical to the live tree modulo line endings, all three removed
(`git worktree list` now shows only the two real ones).
**Nothing committed.** The brief's read-only instruction is explicit; the one repair I recommend is
given as an exact patch below rather than applied.

---

## Verdict on the primary target

**Three of the five replacements are load-bearing. One — item (k), the highest-severity finding the
audit raised — is not: it is green under a defect that puts case300's LMPs 2.69 $/MWh out on a
40 $/MWh system. Audit F2 is not closed.** Item (l) is falsifiable but its stated mechanism is
wrong and its diagnostic points at the wrong module. (p) and (r) are confirmed strong, by my own
sabotages on the current head.

| item | fold's claim | verdict |
|---|---|---|
| **(k)** case300 two-solve price comparison | "the price comparison case300 did not have" | **REFUTED.** Compares the *energy* level only. Blind to any defect in the congestion component — the component A20 is entirely about. |
| **(l)** AC-5(b) compensation identity | "the right-hand side computed independently" | **Partly refuted.** Not independent; the identity clause reduces exactly to `cost_final − cost_nodal`. Still falsifiable, but not for the stated reason. |
| **(p)** `getNumRow` tripwires | "each is the only guard" | **CONFIRMED on head.** 56F/668P/14E with; **738 passed** without. |
| **(q)** AC-5(a) premise conditioned | "premise load-bearing rather than assumed" | **Sound but incomplete.** The pairing is real; the premise itself is checkable in five lines and is not checked. |
| **(r)** netting test made falsifiable | "capable of failing" | **CONFIRMED by my own sabotage**, at a different site from fold-a's. |

---

## 1 — (k): `test_ac4_case300_prices_agree_except_across_the_degenerate_face` · **REFUTED**

### 1.1 The size of the compared set

`tests/unit/test_market_zonal.py:573`. Probe against the live tree, read-only:

```
LOADED: C:\Claude Projects/mambo-power-m6/src\mambo_power\market\zonal.py
n_branches 411 n_rated 411
|at_rating(chain)| = 7 ['branch-147','branch-289','branch-308','branch-310','branch-360','branch-48','branch-83']
|priced_chain|     = 5 ['branch-147','branch-289','branch-308','branch-48','branch-83']
|priced_nodal|     = 5 ['branch-147','branch-289','branch-308','branch-360','branch-83']
priced_chain <= at_rating(chain): True
priced_nodal <= at_rating(chain): True
union(priced) <= at_rating(chain): True
sup|diff| = 0.31878395341163446
residual off at_rating(chain)   = 4.025e-16   rank=7  n=7
residual off priced_chain       = 2.977e-01   rank=5  n=5
residual off priced_nodal       = 3.111e-01   rank=5  n=5
residual off union priced       = 4.007e-16   rank=6  n=6
```

**The compared set is 7 branches of 411.** The union of the two solves' priced sets is **6**, and
fitting on those 6 alone already reaches 4.007e-16.

### 1.2 Clause 2's 4e-16 is an algebraic identity, not a measurement

`opf/dc_opf.py:678`: `congestion = np.asarray(duals.flow_limit @ ptdf, ...)`. So each solve's
congestion vector is `PTDFᵀ mu` with `mu` supported on that solve's priced branches, and the
difference is `(mu_chain − mu_nodal) @ PTDF`, supported on `union(priced)`. Both priced sets are
inside `at_rating` (measured above; for the chain the test asserts it two lines earlier, which is
the complementary slackness audit F2 condemned; for the reference it follows from D1). **So the
difference lies in the fitted span by construction and the residual is machine zero for any pair of
solves satisfying those containments.** The fold report's "Seven vectors span 7 dimensions of 300;
landing inside to 4e-16 is a statement, not an artefact" is the wrong reading — it is an artefact of
how `congestion` is defined.

Clause 2 is not *decoration*: it goes red when the chain's point moves far enough that `at_rating`
stops containing the reference's priced set (measured under fold-a's own sabotage #1 — clause 2
residual 2.298e-01 there). But its content is then derivative of the primal theorem, which
`test_ac4_the_redispatched_point_is_the_nodal_optimum` already asserts at 5e-2 MW.

### 1.3 The refutation: the test is blind to the congestion component

All three clauses re-evaluated with the chain's congestion vector transformed post hoc (energy,
`at_rating`, `priced` untouched — nothing else in the test reads anything else):

| variant | clause 1 (energy) | sup\|diff\| | clause 2 | clause 3 | **test verdict** | true sup\|LMP−LMP_ref\| |
|---|---|---|---|---|---|---|
| baseline | 5.40e-06 | 0.3188 | 4.025e-16 | 0.2977 | PASS | 0.3188 |
| **sign flip** | 5.40e-06 | 2.6897 | 2.665e-15 | 0.2977 | **PASS** | **2.6897** |
| ×2 | 5.40e-06 | 1.3451 | 9.992e-16 | 0.2977 | **PASS** | 1.3451 |
| ×10 | 5.40e-06 | 12.1045 | 8.882e-15 | 0.2977 | **PASS** | **12.1045** |
| zeroed | 5.40e-06 | 1.3448 | 8.882e-16 | 0.2977 | **PASS** | 1.3448 |

Clause 1 compares only `BusLmpResult.energy` — the balance dual, one number replicated across all
300 buses. Clauses 2 and 3 are least-squares fits, so they are invariant under any rescaling that
keeps the difference in the same span; clause 3's residual is *numerically identical* (0.2977) in
every row above. **The test passes with case300's entire congestion component zeroed out.**

### 1.4 The defect class is reachable through the real code path

Scratch worktree `sab-k` at `232de50`, one edit in `market/zonal.py` at the `lmp_decomposition`
call — a sign error in the redispatch stage's flow-limit dual convention, exactly the class
`opf/redispatch.py`'s own tripwire comment names ("a family inserted before them shifts every
flow-limit dual"):

```python
lmp = lmp_decomposition(
    _dc.replace(final.duals, flow_limit=-final.duals.flow_limit), final.ptdf
)
```

```
$ PYTHONPATH="$SC3/src;$SC3" uv run --no-sync python -m pytest .../tests/unit/test_market_zonal.py -q
4 failed, 39 passed in 20.82s
FAILED ...::test_a_corridor_at_the_true_rating_sells_a_schedule_the_network_can_carry
FAILED ...::test_the_settlement_identity_closes_on_the_hand_fixture_from_the_result_alone
FAILED ...::test_ac4_final_lmps_equal_the_nodal_lmps_on_case30
FAILED ...::test_ac5c_the_settlement_identity_closes_from_the_result_object_alone_on_case30

$ ... -q ".../test_market_zonal.py::test_ac4_case300_prices_agree_except_across_the_degenerate_face"
1 passed in 20.34s

sup|LMP_chain - LMP_nodal| on case300 under SABOTAGE-K = 2.6897138967124903 $/MWh
median |LMP_nodal| = 39.96387548338848
```

**Every red test is a case30 test.** The test written to be AC-4's price clause *on case300* is
green while case300's prices are 6.7% wrong. The wave replaced a check a sabotage could not move
with a check a sabotage still cannot move — differently shaped, same failing.

### 1.5 The repair

One line, and it catches all five variants in §1.3 including the reachable one in §1.4. The wave
rejected a blanket LMP tolerance because "it would admit real regressions to hide a known
degeneracy" (ADR-009, *Rejected*). That reasoning does not survive the measurement: the accepted
option admits regressions of **12 $/MWh**, while a tolerance pinned at 1.6× the *measured*
degeneracy admits 0.5.

```python
CASE300_CONGESTION_ATOL = 0.5
"""Sup-norm bound on the two solves' congestion difference on case300, $/MWh. Measured 0.3188 --
the whole degenerate face is 0.319 wide, so this is 1.6x headroom, not a blanket tolerance. Clauses
2 and 3 locate the difference; without this clause nothing bounds its size, and the test is green
with the chain's congestion component sign-flipped, scaled or zeroed."""

# add after the vacuity guard, before clause 2:
assert np.max(np.abs(difference)) <= CASE300_CONGESTION_ATOL, (
    "the congestion components differ by more than the measured degenerate face is wide -- that "
    "is a price defect, not the known degeneracy"
)
```

This composes with the existing `> CASE300_FACE_IS_LOAD_BEARING_ATOL` guard to bracket the
difference in `[0.1, 0.5]`, which is what "the disagreement is exactly the known degeneracy" means.

---

## 2 — (l): `test_ac5b_the_third_figure_is_the_curtailment_compensation` · **partly refuted**

`tests/unit/test_market_zonal.py:826`. The test's RHS is built by `_served_bid_value`, which calls
`_demand_value` — **imported from `mambo_power.market.zonal`** (`test_market_zonal.py:66`), the same
function production uses, fed the same numbers via the result's own load rows.

Algebra: `payment + gap = (cost_final − cost_zonal) + (value_zonal − value_final) + (cost_zonal −
cost_nodal)`. The value terms cancel bit-for-bit against the RHS, leaving `cost_final − cost_nodal`.
Measured, read-only against the live tree:

```
--- bid ---
  LHS (payment+gap)                       = 0.9411149694290089
  RHS (test's 'independent' compensation) = 0.9410544288693927
  LHS - RHS                               = 6.054055961612903e-05
  cost_final - cost_nodal                 = 6.054055961612903e-05
  |(LHS-RHS) - (cost_final-cost_nodal)|   = 0.000e+00
--- fixed_load ---
  LHS - RHS                               = -2.6489033189136535e-11
  cost_final - cost_nodal                 = -2.6489033189136535e-11
  |(LHS-RHS) - (cost_final-cost_nodal)|   = 0.000e+00
```

**Exactly zero on both fixtures.** Three consequences:

1. **It is not a tautology.** It fails if `redispatch_payment` or `generation_cost_gap` combines the
   wrong terms — fold-a's sabotage #4 is the right shape and I accept it.
2. **It cannot catch an error in the value computation.** `_demand_value`, `_generation_cost` and
   `load_bid_coeffs` appear on both sides and cancel. A wrong bid-curve evaluation is invisible to
   this test.
3. **Its docstring's stated measurement is wrong, and so is its diagnostic.** The docstring explains
   the 6.05e-5 residual as float cancellation between two ~3.0e5 $/h bid values. It is not: it is
   `cost_final − cost_nodal`, D1's generation-cost residual, a physical quantity. So if D1's cost
   clause ever degrades past `COMPENSATION_ATOL = 1e-3`, this test fails saying *"the third figure
   is not the curtailment compensation"* — pointing at `market/zonal.py`'s settlement block when the
   defect is in the redispatch LP. Fix the docstring; the assertion itself can stand.

---

## 3 — (p): the two `getNumRow` tripwires · **CONFIRMED**

Scratch `sab-critic` at `cb6dfa9`. A vacuous `0 == 0` balance row over no columns appended after
the last tier in **both** builders (`opf/zonal.py`, `opf/redispatch.py`):

```
with the asserts:      56 failed, 668 passed, 14 errors in 204.26s
asserts removed:       738 passed in 144.75s
```

**Each assert is the only guard on its layout, confirmed on the current head.** (Fold-a reported
43/28/14 — a different selection; the direction and the assert-removed green are what matter, and
both reproduce.)

**On the brief's "computed from the same loop it guards" concern — they are not.** Both sums are
derived from the loops' *inputs*, not their emitted rows:
`n_epigraph = sum(len(segs) for segs in problem.segments_by_gen.values())` counts segments in the
problem; `_epigraph_rows` iterates the same map to emit rows. A loop that emitted two rows per
segment, skipped an item, or a new family added anywhere all move `getNumRow()` and not
`expected_rows`. `n_linking = len(gen_q_col_of) + len(dem_q_col_of)` is the same shape. Not
decoration.

---

## 4 — (q): AC-5(a)'s premise · sound pairing, unchecked premise

The pairing is real and it is the substance of review C7's point: the reversal test
(`test_ac5a_tight_corridors_reverse_the_inequality_and_the_payment_pays_inward`) drives a genuinely
different regime and measures it.

But **the premise is mechanically checkable and is not checked** — it lives in the test's name and
docstring only. The relaxation argument needs `cap >= sum of rating over the pair's cut-set` (then
any nodal-feasible dispatch's inter-zone transfer is within cap, so the zonal feasible set contains
the nodal one). Computable from `net` and the options alone, and it holds with equality everywhere:

```
 case30: 3 corridors
   ('1','2'): cap=    1.523704  sum(cut-set ratings)=    1.523704 over 1 branches  cap>=sum: True
   ('1','3'): cap=   16.576769  sum(cut-set ratings)=   16.576769 over 3 branches  cap>=sum: True
   ('2','3'): cap=   19.456188  sum(cut-set ratings)=   19.456188 over 3 branches  cap>=sum: True
 case300: 3 corridors
   ('1','2'): cap=  212.533723  sum(cut-set ratings)=  212.533723 over 3 branches  cap>=sum: True
   ('1','3'): cap=  208.415101  sum(cut-set ratings)=  208.415101 over 7 branches  cap>=sum: True
   ('1','9'): cap=   93.768000  sum(cut-set ratings)=   93.768000 over 1 branches  cap>=sum: True
```

Equality everywhere means the premise sits **exactly on its boundary**. If `tests/_zones.py`'s
`corridors()` ever derives a tighter cap (a de-rating factor, `min` instead of `sum`), the premise
silently fails and the positive test goes red blaming the theorem. Five lines computed from `net`
directly — not from `corridors()`, so it stays independent of the helper — converts a confusing
failure into a precise one. **Low severity; not a blocker.**

---

## 5 — (r): the netting test · **CONFIRMED, by my own sabotage**

Scratch `sab-critic`, with the pre-fold test resurrected as `test_OLD_...` in the same file so both
run in one pytest process, one solver build, one fixture.

**My sabotage (demand side — a different site from fold-a's #8, which is on the generator side):**
`opf/redispatch.py:524`, `dem_net = 1.05 * (col_value[dem_up_cols] - col_value[dem_down_cols])`.

```
1 failed, 1 passed, 17 deselected in 7.15s
FAILED ...::test_reported_deltas_are_the_movement_to_an_independently_computed_final_point
  Index | Obtained            | Expected
  (0,)  | -0.7278081342631717 | -0.6931637423606141 ± 0.001
```

**OLD test PASSED, NEW test FAILED.** The replacement is genuinely stronger. Accepted.

**Second sabotage, inconclusive and recorded rather than hidden:** report the raw HiGHS columns
instead of the canonical netting (`delta_up_mw = col_value[gen_up_cols]`, etc., `dispatch_mw`
untouched) — **2 passed**. On this platform HiGHS already returns a netted split, so the netting
step is currently a no-op and *neither* test can see whether it is applied. The module docstring's
own justification for the netting (platform-dependent splits) is untestable here. Worth a line in
the docstring; not a defect.

**One coverage note.** The old test asserted `solution.dispatch_mw == p0 + delta_up - delta_down`
bit-exactly. The new one asserts no relation between `dispatch_mw` and the reported deltas at all —
both are held to the independent target instead. That is a strictly better oracle but a slightly
narrower internal consistency claim. Cheap to keep both.

---

## 6 — Secondary targets

### A35(i)/(ii) — both ratifications hold

```
 direct ctor CorridorLimit(zone1="1", zone2="2"):  ValidationError -- cap_mw Field required
 jobs.run_json missing cap_mw -> failed  BAD_OPTIONS  "corridors.0.cap_mw / Field required [type=missing]"
 jobs.run_json cap_mw=null    -> ok
 jobs.run_json cap_mw=inf     -> failed  BAD_OPTIONS  "Input should be a finite number [type=finite_number]"
```

A required cap is reachable as `BAD_OPTIONS` through `jobs.run_json` and as `ValidationError`
through the direct constructor. **(i) ratified.**

```
 absent zone -> VALIDATION
   DANGLING_REF at options.corridors[0].zone2: corridor names zone 'NOPE', which no bus is assigned to
 unzoned bus -> VALIDATION
   DANGLING_REF at buses[0].zone: bus "bus-1": carries no zone, ...
   DANGLING_REF at buses[3].zone: bus "bus-4": carries no zone, ...
```

The two failures are distinguishable: `path` roots differ (`options.corridors[i].zoneN` vs
`buses[i].zone`), every offender is listed, and the messages differ. A client switching on `code`
alone conflates them; a client switching on `path` — the documented convention — cannot.
**(ii) ratified.** *Also measured:* the unzoned bus now lands as `VALIDATION`, not `INTERNAL`
(`cb6dfa9` closed fold-a's flagged open decision).

**Record staleness, no code impact.** `cap_mw = inf` is now **rejected** and `ser_json_inf_nan` is
gone from `src/` entirely (`grep -rn ser_json_inf_nan src/` returns nothing). `cb6dfa9` reverted
fold-a item (e); the fold-a report's (e) section still describes `inf` as accepted and three models
carrying `ser_json_inf_nan="constants"`. A reader taking that report at face value will be wrong.

### A33(i) — the griffe extension's guard · **the claim is false for partial failure**

`docs/hooks/pydantic_fields.py`'s guard is a **package-wide** `attached == 0` count
(`PydanticFieldDescriptions.on_package`). Any single pydantic model still rendering keeps
`attached > 0` and the build silent.

Scratch `sab-docs`, `mkdocs build --strict` via the m6 venv's interpreter:

```
baseline:            INFO - pydantic_fields: documented 217 field(s) in mambo_power     EXIT=0
partial sabotage:    INFO - pydantic_fields: documented  88 field(s) in mambo_power     EXIT=0
  (sabotage: `if cls.module.path.startswith("mambo_power.results"): return 0` in _document)
```

Rendered loss on `api/results/index.html`: `redispatch_payment` mentions **18 -> 4**,
`generation_cost_gap` **16 -> 4** (the survivors are the source view, not field entries).

**129 fields vanish — every field of every result model, including `MarketZonalResult` — and
`--strict` exits 0.** That is precisely walk D2 / ADR-009 consequence 6, the defect the guard was
written for. The guard catches only total failure and per-module import failure. Fold-b's commit
message ("fails the strict build if it stops working") and their positive control (forcing
`_document` to find *no* fields anywhere) test only the total case.

Repair, one line: track a per-model count and warn when a model that *has* `model_fields` attached
none — or simply pin the total, `if attached < 200: _logger.warning(...)`. The first is better; the
second is one line and would have caught this.

### ADR-009 consequence 3 — **the "only" list is wrong; the ADR should be corrected before merge**

Scratch `sab-critic`, zonal LP's own merit order perturbed and nothing else
(`opf/zonal.py:374`, `h.changeColsCost(n_gen, ..., c1 * 1.30)`): the LP stays feasible, every
corridor bound still applies, the redispatch stage is untouched. Full suite:

```
40 failed, 952 passed, 4 skipped, 10 warnings in 538.29s
```

Complete enumeration of the 40:

| bucket | count | in the ADR's list? |
|---|---|---|
| `tests/parity/test_market_zonal_vs_pypsa.py` (all 23) | 23 | yes — "oracle parity" |
| `tests/unit/test_opf_zonal.py` (all 10) | 10 | yes — "the hand-derived zonal optimum" |
| `test_market_zonal.py::test_the_piecewise_bid_variant_prices_zone_b_at_the_bid...` | 1 | yes — zone prices |
| `test_market_zonal.py::test_a_lifted_cap_clears_one_price_where_the_true_rating_clears_two` | 1 | yes — zone prices |
| `test_market_zonal.py::test_a_corridor_at_the_true_rating_sells_a_schedule_the_network_can_carry` | 1 | **no** — zonal *schedule* feasibility |
| `test_market_zonal.py::test_an_overstated_corridor_sells_a_schedule_the_network_cannot_carry` | 1 | **no** — same |
| `test_market_zonal.py::test_no_corridors_means_each_zone_supplies_itself` | 1 | **no** — same |
| `test_market_zonal.py::test_ac5a_zonal_welfare_is_never_lower_..._[case300]` | 1 | **no** — the **relaxation inequality** |
| `test_market_zonal.py::test_ac5b_the_third_figure_is_the_curtailment_compensation` | 1 | **no** — a **settlement figure** |

**Confirmed:** the first sentence — "breaking the zonal LP leaves every final-point assertion
green". No AC-4 test went red.

**False:** the second — "*Only* the zone prices, the corridor flows and the oracle parity see that
stage." Five more rows see it, and two of them are acceptance-criterion rows: AC-5(a)'s relaxation
inequality and AC-5(b)'s compensation identity. The ADR contradicts itself between consequences 1
and 3: consequence 1 states outright that both settlement figures are computed from the zonal point.

The ADR's *conclusion* survives (keep the hand-derived optimum and the zonal parity as separate
rows). The enumeration supporting it does not, and it is exactly the kind of sentence a later wave
would cite to prune "redundant" coverage. Suggested edit: *"The zone prices, the corridor flows, the
zonal schedule rows, AC-5(a)'s relaxation inequality, AC-5(b)'s compensation identity and the oracle
parity see that stage; the final-point rows do not."*

### A31 F1 — the symptom was closed; the hole is open, and I can now measure it

The audit's own disposition already said this ("the fold already carries it... the finding is that
the chain, not the fold, is what needs the repair"). My A33 measurement makes it concrete:
**AC-8's four clauses still cannot detect an unrendered field list** — the guard fold-b added to
close that gap passes a build in which every result model's fields have vanished. ADR-009
consequence 6 records the lesson retrospectively; nothing in M6's criteria can enforce it. The hole
is where the audit left it.

---

## What I tried to break and could not

1. **(r) via a raw-column sabotage.** Reporting HiGHS's own split instead of the canonical netting
   left both the old and the new test green — but only because HiGHS happens to return a netted
   split on this platform, so it does not weigh against the new test. The discriminating sabotage
   (demand-side scaling, §5) took the new test red and left the old one green.
2. **(p) via the "tripwire computed from its own loop" theory.** I expected the expected-row sums to
   be derived from the emitted rows. They are derived from the loops' *inputs* — a genuinely
   independent hand-maintained contract. The theory was wrong.
3. **A35(ii) via the shared `DANGLING_REF` code.** I expected the two failures to be
   indistinguishable. They are separated by `path` root and by message, and every offending item is
   reported in one pass. The ratification holds.
4. **(l) as a pure tautology.** It is not `0 == 0`; it reduces to a real theorem (`cost_final ==
   cost_nodal`) and fails under a term-combination defect. Only the *independence* claim and the
   docstring's account of the residual are wrong.

---

## Recommended before merge

| # | item | severity | cost |
|---|---|---|---|
| 1 | **(k)**: add `CASE300_CONGESTION_ATOL = 0.5` and the sup-norm bound (§1.5). Audit F2 stays open without it. | **HIGH** | 1 constant + 1 assert |
| 2 | **A33(i)**: make the extension's guard per-model, or pin the total. The current guard cannot catch its own originating defect. | **MED** | 1–3 lines |
| 3 | **ADR-009 consequence 3**: correct the "only" list (§6). | **MED** | 1 sentence |
| 4 | **(l)**: fix the docstring — the residual is `cost_final − cost_nodal`, not float cancellation; say what the test cannot catch. | LOW | prose |
| 5 | **(q)**: assert the cut-set premise from `net` directly. | LOW | 5 lines |
| 6 | **fold-a report item (e)**: mark stale — `cb6dfa9` reverted it. | LOW | prose |

---

## The pattern, named again

The brief predicted it: *"when the orchestrator writes 'not a waiver' or 'cannot be tested here',
that sentence is the next reader's first target."* This wave's instance is one level deeper than
M5's A20 and this wave's own F2. The fold correctly diagnosed that the old case300 clause was
complementary slackness — and then built a replacement whose two *new* clauses are also structurally
satisfied (least-squares fits into a span the difference provably lies in), with the one genuinely
comparative clause aimed at the component that was never in question. The energy level was never the
disputed quantity; the congestion attribution is what A20 is about, and it is still uncompared.

**The generalisation worth carrying to M7:** a replacement test's power proof must show it red under
a defect *in the specific quantity the criterion names*, not merely red under some sabotage. Fold-a's
sabotage #1 moved the whole solution, so every clause could have fired for the wrong reason — and
clause 1 did, which is why the vacuity of clauses 2 and 3 was never exposed. **Sabotage the narrowest
thing the test claims to see, not the widest.**
