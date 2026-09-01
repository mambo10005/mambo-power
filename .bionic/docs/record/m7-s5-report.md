# M7 S5 — AC-3 and AC-4, the wave's two economic statements

Slice: senior-implementor, wave M7 `agents`, branch `wave/07-agents`, worktree
`C:\Claude Projects\mambo-power-m7`.
Commit: **`8bc24e5`** — `test(m7/s5): AC-3 and AC-4 -- price-takers reproduce solve_nodal
bitwise, a pivotal markup stops at demand's own bid`, one file, 544 insertions.
File owned and touched: `tests/unit/test_market_agents_economics.py` (new). **No source file
was edited, and no source change proved necessary.**
New public symbols: **none** (a test module; nothing is exported).

Every claim below carries the command that proves it and that command's pasted output, or the
label `unverified`.

## Where the numbers were taken

Never on the shared worktree. A `git archive` overlay of the committed head `74a0532` was built
in the session scratchpad and driven by `PYTHONPATH`, with `__file__` printed to prove which
tree ran:

```
$ cd "C:/Claude Projects/mambo-power-m7" && git rev-parse HEAD
74a0532776d494fb2dc2f031491a24ff62d96e88

$ cd "$SCR/ov" && PYTHONPATH="$SCR/ov/src" .../python.exe -c "import mambo_power, ..."
mambo_power: ...\scratchpad\ov\src\mambo_power\__init__.py
agents: ...\scratchpad\ov\src\mambo_power\market\agents.py
tests._agents: ...\scratchpad\ov\tests\_agents.py
```

The sabotage sweep ran on a **second, separate** archive copy (`sab`) with a pristine reference
beside it, restored and byte-compared after every defect.

**This provenance is load-bearing for every figure below, not a process note.** For part of this
slice the shared worktree was carrying an uncommitted defect that silently disabled the offer
overlay (next section). Under it a markup run clears at true cost every round while still
reporting `Optimal` and `converged` — so a slice measuring in place during that window would
have obtained plausible, wrong numbers and reported them in good faith. **Every AC-3 and AC-4
number in this report was taken on the archive overlay of `74a0532`, which the shared tree's
state cannot reach**, and each was re-confirmed by the committed tests at the branch head after
the tree was restored (`21 passed`, twice — at `8bc24e5` and again at `67d189e`). That is the
reason these figures stand despite the window, and it is the part of the evidence an audit
should check first.

## Finding reported to the lead during the slice (not mine, not fixed by me)

**Confirmed by the lead independently at 23:03 and 23:05, and attributed to S4.** The lead
recorded the cause as its own (**A17**): S4 was dispatched before the no-sweeping-in-the-shared-
tree rule existed, its brief told it to run a sweep and did not say where, and the rule was
embedded in later briefs (including mine) without being relayed to the slices already running.
The lead also declined to revert it, on the same reasoning I did — reverting would destroy a
sweep possibly still in flight.

At 22:59–23:02 PDT 2026-08-28 the **shared worktree** carried an uncommitted one-line sabotage
of `src/mambo_power/opf/__init__.py` that deleted the cost-source application, making the offer
overlay a silent no-op for every slice measuring there:

```
$ git diff -- src/mambo_power/opf/__init__.py
@@ -126,7 +126,7 @@ def gen_cost_coeffs(
     for i, gen_id in enumerate(arr.gen_ids):
-        cost = costs.get(gen_id, gens_by_id[gen_id].cost) if costs else gens_by_id[gen_id].cost
+        cost = gens_by_id[gen_id].cost
```

Under it a markup run clears at true cost every round while still reporting `Optimal` /
`converged` — silent-plausible. Messaged to the lead immediately; when I re-checked a few
minutes later the owner had restored the line (`grep -n "cost = costs.get"
src/mambo_power/opf/__init__.py` → present at line 129, and `git status --short` no longer
listed the file). I did not touch it.

## AC-3 — price-takers reproduce the competitive result: **PASS, both clauses, bitwise**

Asserted on three cost shapes, because `PriceTakerStrategy` is scoped to none of them: **linear**
(`tests._agents.smooth_pivotal_network()`, and the only one of the three carrying an elastic
load, so the bid side is exercised too), **quadratic** (`case14` — the shape all 147 committed
MATPOWER generators carry), **piecewise** (`case14_pwl`, MODEL-1 PWL on gen-2/gen-3 mixed with
quadratic on the rest — the only path by which a PWL offer reaches the array builder this wave,
and the invariant S1's generator-side overlap guard protects).

Measurement probe (`scratchpad/probe_ac3.py`, run on the overlay). Identical output on all five
networks tried; the two MATPOWER ones quoted in full:

```
--- case14 (quadratic) ---
  n_gen 5 kinds ['polynomial']
  poly degrees [3]
  status Optimal converged True reason converged iterations 2
  clearings captured: 3
  every handed cost_coeffs array_equal true: True
  pwl handed == true pwl on every round: True | n_pwl_gens 0
  gen ids order equal: True
  bus ids order equal: True
  dispatch array_equal: True max abs diff 0.0
  lmp array_equal: True max abs diff 0.0
  load dispatch array_equal: True
  settlement equal: True True
  offers == true costs: True
  markups: [0.0]
--- case14_pwl (piecewise + quadratic) ---
  n_gen 5 kinds ['piecewise', 'polynomial']
  poly degrees [3]
  status Optimal converged True reason converged iterations 2
  clearings captured: 3
  every handed cost_coeffs array_equal true: True
  pwl handed == true pwl on every round: True | n_pwl_gens 2
  gen ids order equal: True
  bus ids order equal: True
  dispatch array_equal: True max abs diff 0.0
  lmp array_equal: True max abs diff 0.0
  load dispatch array_equal: True
  settlement equal: True True
  offers == true costs: True
  markups: [0.0]
```

- **(a), on the input.** `array_equal` on **every round's** `cost_coeffs` (not only the last —
  a strategy that drifted after round 0 would still leave a correct final offer on a fixture
  whose clearing does not move), and on the `pwl_costs` map beside it.
- **(b), on the output.** Dispatch, LMPs **and** elastic-load dispatch `array_equal` to
  `market.solve_nodal`'s — `max abs diff 0.0`, no tolerance introduced. Settlement totals agree
  exactly too (measured; asserted only via the rows the criterion names). **No platform
  disagreement was seen on this Windows/HiGHS build**; nothing is known here about other
  platforms, and the module's docstring says a disagreement would be a finding to record, not a
  tolerance to add.
- **No short-circuit, confirmed rather than assumed.** `iterations == 2`, `clearings captured:
  3` — the all-price-taker case is an ordinary run of the general path, three real `dc_opf`
  constructions. The committed test proves it in the form that would catch a short-circuit added
  later: `market.nodal.solve_nodal` is monkeypatched to raise and the run still clears.
- **The PWL row is real**: `n_pwl_gens 2` on `case14_pwl`, the two PWL generators' own
  coefficient rows all-zero and the quadratic half still carrying a nonzero `c2` — the
  convention W1(c)'s guard now raises on.

## AC-4 — a pivotal supplier's markup stops where demand stops paying: **PASS**

`scratchpad/probe_ac4.py` and `probe_ac4b.py`, on the overlay. Every figure reproduced the
Step-2 measurement; **nothing disagreed, so no number was adjusted and no tolerance widened.**

```
=== pivotal, smooth_pivotal_network, step 0.5 ===
markup   : status=Optimal conv=True reason=converged iters=84 offer=60.0 price=60.00003999992 mw=399.99920000159995 profit=15999.983999999997
truecost : status=Optimal conv=True reason=converged iters=2 offer=20.0 price=20.00007999984 mw=799.9984000031999 profit=0.06399974400092068
  gain = 15999.920000255996

=== closed form (pi-20)(1000-10 pi) ===
  grid argmax: (60.0, 16000.0)  q = 400.0
```

Spec's $60.00 / 400.00 MW / $15,999.98 against the hand-derived **$16,000.00**, at **84** update
rounds, against **$0.06** at true-cost offers — gain **$15,999.92**, exactly the figure AC-4's
control is compared against.

**The cap is `Load.bid`, not a clamp — the peak moves when the bid does.** Demand's intercept
`v1` moved on the factory's own network (bid only; `Load.p_mw` untouched at 1000, above every
peak quantity reached), against the closed form `pi* = (v1 + 20)/2`:

`probe_ac4.py`, verbatim (the closed form is recomputed inside the probe, not read off the run):

```
=== the cap is Load.bid: raise the bid curve, does the peak move? ===
  v1=100.0 : status=Optimal conv=True reason=converged iters=84 offer=60.0 price=60.00003999992 mw=399.99920000159995 profit=15999.983999999997
        closed form peak pi=60.0, profit=16000.0, q=400.0
  v1=140.0 : status=Optimal conv=True reason=converged iters=124 offer=80.0 price=80.00005999988 mw=599.9988000023999 profit=35999.96399999999
        closed form peak pi=80.0, profit=36000.0, q=600.0
  v1=80.0  : status=Optimal conv=True reason=converged iters=64 offer=50.0 price=50.00002999994 mw=299.99940000119994 profit=8999.990999999998
        closed form peak pi=50.0, profit=9000.0, q=300.0
```

`probe_ac4b.py`, verbatim, for the two further curves the committed test pins:

```
pivotal, bid moved (no rival):
  v1=100.0 : offer=60.0 price=60.000040 mw=399.9992 iters=84 profit=15999.9840 rows=[('strategic', 399.9992)]
  v1=90.0  : offer=55.0 price=55.000035 mw=349.9993 iters=74 profit=12249.9877 rows=[('strategic', 349.9993)]
  v1=120.0 : offer=70.0 price=70.000050 mw=499.9990 iters=104 profit=24999.9750 rows=[('strategic', 499.999)]
```

Five bid curves, five different closed-form peaks, the climb at each one. The committed test
pins three of them (`v1 = 90 / 100 / 120` → `$55 / $60 / $70`).

**Control — stopped by the rival, not by demand.** Both numbers asserted; neither is a bound:

```
=== control, non_pivotal_control_network ===
markup   : status=Optimal conv=True reason=converged iters=7 offer=21.5 price=21.500078499843 mw=784.9984300031399 profit=1177.5592672582197
truecost : status=Optimal conv=True reason=converged iters=2 offer=20.0 price=20.000079999839997 mw=799.9984000031999 profit=0.0639997439980785
  gain = 1177.4952675142217
  ratio pivotal_gain/control_gain = 13.588097074931767
  control rows: [('strategic', 784.9984300031399), ('rival', 0.0)]
```

**$1,177.50** against the pivotal **$15,999.92** — real, nonzero, **13.59×** smaller (spec's
13.6×).

**And the mechanism differs, not merely the magnitude** — shown from both sides:

`probe_ac4.py`, verbatim:

```
=== the control's cap is the rival: move the rival's cost ===
  rival=22.0 : status=Optimal conv=True reason=converged iters=7 offer=21.5 price=21.500078499843 mw=784.9984300031399 profit=1177.5592672582197
  rival=30.0 : status=Optimal conv=True reason=converged iters=23 offer=29.5 price=29.500070499859007 mw=704.9985900028199 profit=6697.536307327984
  rival=26.0 : status=Optimal conv=True reason=converged iters=15 offer=25.5 price=25.50007449985101 mw=744.99851000298 profit=4097.547307294388
```

`probe_ac4b.py`, verbatim -- the same bid move, on the control and on the pivotal fixture:

```
control, bid moved (rival fixed at $22):
  v1=100.0 : offer=21.5 price=21.500078 mw=784.9984 iters=7 profit=1177.5593 rows=[('strategic', 784.9984), ('rival', 0.0)]
  v1=90.0  : offer=21.5 price=21.500068 mw=684.9986 iters=7 profit=1027.5449 rows=[('strategic', 684.9986), ('rival', 0.0)]

pivotal, bid moved (no rival):
  v1=100.0 : offer=60.0 price=60.000040 mw=399.9992 iters=84 profit=15999.9840 rows=[('strategic', 399.9992)]
  v1=90.0  : offer=55.0 price=55.000035 mw=349.9993 iters=74 profit=12249.9877 rows=[('strategic', 349.9993)]
```

The control's stop tracks the **rival's** cost, one step below it in every case (the round that
offers the rival's own cost ties, the tie breaks against the strategic unit, its profit falls,
the climb reverses). The **bid** move that walks the pivotal climb from $60.00 to $55.00 leaves
the control at $21.50 — and it is not vacuous, because that same bid move does reach this
market: cleared quantity 785 → 685 MW. The pivotal stop is nowhere near a capacity limit either:
400 MW of an available 900, down from 800 MW at true cost.

## Sabotage sweep — each clause red under a defect in **the quantity it names**

Six defects, one at a time, on the separate archive copy; the overlay was byte-compared against
pristine after each (`overlay restored to pristine: True`). Driver: `scratchpad/sabotage.py`.

```
=== baseline (no sabotage) ===
    21 passed in 37.26s

=== S1b: price-taker offers true cost + $1.00 on the CONSTANT term ===
3 failed, 18 passed in 22.60s
    test_ac3a_..._are_exactly_the_true_costs[linear]
    test_ac3a_..._are_exactly_the_true_costs[quadratic]
    test_ac3a_..._are_exactly_the_true_costs[piecewise]

=== S2-dispatch-rounded ===
    3 failed, 18 passed in 27.80s
    FAILED  test_ac3b_dispatch_and_lmps_are_bitwise_market_solve_nodals[linear]
    FAILED  test_ac3b_dispatch_and_lmps_are_bitwise_market_solve_nodals[piecewise]
    FAILED  test_ac3b_dispatch_and_lmps_are_bitwise_market_solve_nodals[quadratic]

=== S3-markup-clamped-at-60 ===
    2 failed, 19 passed in 26.13s
    FAILED  test_ac4_the_cap_is_demands_own_bid_and_the_peak_moves_with_it[120.0]
    FAILED  test_ac4_the_pivotal_climb_reaches_the_measured_stopping_point

=== S4-markup-never-reverses ===
    12 failed, 9 passed in 96.53s   (every AC-4 test; no AC-3 test)

=== S5-non-agent-cost-dropped ===
    5 failed, 16 passed in 32.14s
    FAILED  test_ac4_control_stops_at_21_50_for_a_real_but_far_smaller_gain
    FAILED  test_ac4_moving_demands_bid_does_not_move_the_controls_stop
    FAILED  test_ac4_the_control_is_stopped_by_the_rival_and_the_stop_follows_it[22.0]
    FAILED  test_ac4_the_control_is_stopped_by_the_rival_and_the_stop_follows_it[26.0]
    FAILED  test_ac4_the_control_is_stopped_by_the_rival_and_the_stop_follows_it[30.0]

=== S1-pricetaker-one-ulp ===
    7 failed, 14 passed in 25.63s   (all three AC-3(a), all three AC-3(b), and the AC-4 baseline)
```

What each one establishes, and the residual that moved:

| defect | reddens | why it is the right quantity |
|---|---|---|
| **S1b** — the offer's **constant** term shifted by $1.00 (`PriceTakerStrategy`) | AC-3(a) ×3 **only** | An input the LP's argmin cannot see: the coefficients handed to the builder differ while dispatch and LMPs are untouched. This is the clause "a price-taker is a price-taker" in isolation. |
| **S2** — the reported generator dispatch rounded to 6 dp (`agents._clearing_rows`) | AC-3(b) ×3 **only** | An output-only defect, four orders inside every tolerance the wave uses elsewhere (`DISPATCH_ABS_TOL = 0.01`) — nothing but a bitwise comparison catches it. It leaves AC-3(a) and every AC-4 row green. |
| **S3** — `MarkupStrategy` clamped at a hardcoded $60.00 | AC-4 moved-bid `[120.0]`, and the headline's round count | **The cap-vs-clamp discrimination.** `[90.0]` and `[100.0]` stay green — a clamp at $60 is indistinguishable from a bid-side cap on the fixture's own case. Residuals: `offer 70.0 -> 60.0` at `v1 = 120`, and `iterations 84 -> 82` (the clamp arrives two rounds early). |
| **S4** — `MarkupStrategy` never reverses direction | every AC-4 test; **no** AC-3 test | The climb with no way to stop at an optimum. Broad by construction, which is why it is not the proof for any single clause — it is the proof that the *stopping* is a behaviour and not an artefact of where the run was cut off. |
| **S5** — a generator absent from the cost source loses its own cost (`gen_cost_coeffs`) | exactly the **five control** tests; **no** pivotal test | The rival stops being a $22 competitor. Nothing on `smooth_pivotal_network()` moves, because its single generator is itself an agent — so this separates "stopped by the rival" from "stopped by demand" at the source. |
| **S1** — the offer perturbed by **one ULP** in its leading coefficient | AC-3(a) ×3, AC-3(b) ×3, and the AC-4 true-cost baseline | Recorded because it is a fact worth having, not because it isolates a clause: **one ULP in an offer coefficient does move this LP's answer**, on all three cost shapes. That is precisely why AC-3(b)'s bitwise claim is meaningful rather than lucky — it holds because both paths hand the builder *identical* arrays, not because the solve is insensitive. |

## Gates at my head (`8bc24e5`)

```
$ uv run --no-sync ruff check .
All checks passed!
$ uv run --no-sync ruff format --check .
176 files already formatted
$ uv run --no-sync mypy
Success: no issues found in 53 source files
```

```
$ uv run --no-sync pytest tests/unit/test_market_agents_economics.py -q
21 passed in 16.72s
```

Full suite, run at `8bc24e5` **while other slices held uncommitted work in the shared tree** —
`11 failed, 1132 passed, 4 skipped in 534.88s`. Attributed by path, then re-measured:

| red | owner | status when re-run minutes later |
|---|---|---|
| `tests/unit/test_docs_registry_listing.py` (3) | **S7/S8** | still red — and correctly so: `jobs.kinds()` now returns eight kinds including `market.agents`, so the manual's three coupled sites are stale exactly as plan F5 predicted. Not touched by me. |
| `tests/unit/test_jobs.py` (6, all `market.agents`) | **S7** | **green** on re-run — transient, from that slice's in-flight edits |
| `tests/unit/test_market_agents.py` (2, `..._at_every_step...[0.1]`, `[0.7]`) | **S4** | **green** on re-run (`9 passed`) — transient, same cause |

```
$ uv run --no-sync pytest tests/unit/test_jobs.py tests/unit/test_docs_registry_listing.py \
    tests/unit/test_market_agents.py tests/unit/test_market_agents_economics.py \
    tests/unit/test_agents_fixtures.py tests/unit/test_market_strategy.py -q --tb=line
FAILED tests/unit/test_docs_registry_listing.py::test_the_manual_prints_the_real_sorted_kind_list
FAILED tests/unit/test_docs_registry_listing.py::test_the_manual_capability_table_lists_every_registered_kind
FAILED tests/unit/test_docs_registry_listing.py::test_the_manual_unknown_kind_message_lists_every_registered_kind
3 failed, 226 passed in 50.15s
```

**No red in `tests/unit/test_market_agents_economics.py` at any point.**

## Unproved / limits of what is claimed

- **AC-3(b)'s bitwise agreement is a statement about this machine and this build only** —
  Windows 11, the worktree's pinned `highspy`, both calls in one process. No cross-platform claim
  is made or asserted.
- The **`S1` one-ULP result** above says the LP is not insensitive to a coefficient ULP, so
  AC-3(b) rests on the two paths handing the builder *identical* arrays. If a future change ever
  makes them merely equivalent rather than identical, (b) will fail — by design.
- The **$1,177.50 / 13.6× control figures** are computed as *gains over each fixture's own
  true-cost baseline* (`15,999.98 − 0.06 = 15,999.92`), which is how the spec's two pivotal
  numbers reconcile. That reading is measured, not assumed, and is stated in the tests.
- **Nothing here asserts anything about AC-5** (S4's) or about the loop's non-convergence shapes;
  a red in this file is unambiguously AC-3 or AC-4.
- The **shared-worktree sabotage** reported above was observed by me, reported, and seen
  restored. That it was **S4's** is the lead's finding, independently verified at 23:03 and
  23:05, not mine — I established only that it was live and what it did. I did not verify
  whether any other slice's numbers were taken during the window it was live; the lead has
  warned S7 and separated its structural results from its value-dependent ones.
