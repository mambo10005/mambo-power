# M4 / Step 6 — six-axis review (stance 1)

Wave M4 nodal-market, worktree `C:\Claude Projects\mambo-power-m4`, diff `5fa3285..f5e20d9`
(the whole wave, base to R1-fold commit; 32 files, +2536/−113). Reviewed 2026-08-24 against the
wave spec (Requirements W1-W7, AC-1..8, Design 1-8), epic §Design (ownership) and the plan's
Verification Matrix/Assumptions. Every claim below carries its proving command/output or a
`file:line`; anything else is marked `unverified`. This review does not re-run the
coverage/power/authenticity analysis `m4-audit.md` already did — it is scoped to the six axes
below, several of which go beyond what that audit (or the plan's own AC evidence) checked.

Evidence run in the worktree (read-only):

```
git rev-parse --short HEAD          -> f5e20d9 (wave/04-nodal-market)
git status --porcelain              -> 4 untracked files: probe_ac6.py, probe_ac6b.py,
                                        probe_ac6c.py, probe_ac6d.py (mtimes 19:11-19:13,
                                        7-9 min after HEAD's own commit timestamp 19:04 —
                                        pre-existing when this review began, not created by
                                        this review; not this review's to clean up under a
                                        read-only mandate, but disclosed rather than silently
                                        stepped around. This review's own probes were written
                                        to the session scratchpad directory, outside the
                                        worktree, and confirmed not to appear in this status.)
```

All probes below were run via `uv run --no-sync python <scratchpad-script>` against the
installed package; `git status --porcelain` carried exactly the same 4 pre-existing untracked
files before and after every probe in this review, confirming no edit by this review.

---

## 1. Correctness — **PASS** (2 flags, both closed by a direct probe or a code-symmetry check)

**The hypograph encoding genuinely generalizes past 2 segments — confirmed by direct probe, not
inspection alone.** `_concave_pwl_segments` (`opf/dc_opf.py:291-312`) is a literal sign-mirror of
`_convex_pwl_segments` (`opf/dc_opf.py:268-288`): same generic `pairwise(points)` loop, no
special-casing of segment count. But **every PWL demand-bid test in the repo uses exactly 3
points (2 segments)** — confirmed exhaustively: `grep -rn "PiecewiseBid\|demand_pwl_bids"
tests/ src/` shows `D1_BID_POINTS` (`test_opf_dc_demand.py:72`, reused by `test_market_nodal.py`),
the non-concave-guard points (`test_opf_dc_demand.py:151`) and the marginal-value-drop test
(`test_opf_dc_demand.py:253`) are all 3-point curves; `tests/_bids.py` (S5's fixture-oracle
derivation, the wave's only *real*-fixture bid source) only ever emits `PolynomialBid`
(`tests/_bids.py:110`), never `PiecewiseBid` — so AC-6's pandapower-parity fixture exercises zero
PWL demand bids of any segment count. By contrast the *generator*-side epigraph mirror is
genuinely 3-segment-tested (`test_opf_dc_pwl.py:8`, breakpoints `(0,0),(30,600),(60,1500),
(100,3000)`). This is a real, confirmed test-coverage gap on the demand side specifically — not a
paper distinction, since the two encodings are structurally identical and only one of them is
exercised past 2 segments anywhere in the suite.

Closed by a direct probe (read-only, worktree untouched — `git status --porcelain` unchanged
before/after): built a 1-bus network, generator marginal cost $15/MWh, and a genuine 3-segment
concave demand bid (slopes 30, 20, 10 over `[0,10],[10,20],[20,30]`, points `(0,0),(10,300),
(20,500),(30,600)`), called `dc_opf` directly.

```
status: Optimal
demand_dispatch_mw: [20.]
dispatch_mw: [20.]
balance dual: 15.0
demand_bound: [0.]
```

Hand-predicted: welfare-maximizing dispatch takes segment 1 (slope 30 > 15, take all 10 MW), takes
segment 2 (slope 20 > 15, take all 10 MW, total 20), stops at segment 3 (slope 10 < 15) — `d = 20`
exactly, at an interior point of its own bid domain (`demand_bound == 0`, not pinned at either
end), balance dual pinned to the marginal generator's own cost (15.0). The probe matches exactly.
**Verdict: the hypograph encoding is correct for 3+ segments, confirmed empirically here, not
merely by code-symmetry reading — but this is now the review's own evidence, not the wave's; no
committed test in the suite proves this.** Worth a follow-up unit test (3+ segment concave PWL
demand bid, mirroring `test_opf_dc_pwl.py`'s own generator-side 3-segment case) — low severity
(the code is unambiguous and now independently confirmed), but a real gap between "correct" and
"proven," exactly the class of finding M3's own review found in `FeasibilityReport`'s untested
edges.

**The double-counting subtraction's "all-or-nothing per `Load`" contract is correct as
implemented, and the mixed-load test genuinely covers the *only* way this codebase can express a
load bidding less than its full historical demand — but that constraint is nowhere stated as a
constraint.** `Load.bid: LoadBid | None` (`model/entities.py:148`) is one field on one load; the
double-counting subtraction reads `arr.load_p_max_pu[idx]` (`opf/dc_opf.py:496`, `NetworkArrays`
built from `ld.p_mw` directly, `numerics/arrays.py:232`) — a bid-load's *entire* historical demand
is what gets removed from the fixed aggregate and re-added as the LP's elastic bound `[0, p_mw]`.
There is no way to give a single `Load` a bid covering only part of its capacity with the
remainder genuinely fixed — the schema has no `p_min_bid_mw`/split concept. The only way to model
"60 MW must-serve + 40 MW elastic at the same bus" is two separate `Load` entities (one `bid=None`
at 60 MW, one bid-carrying at 40 MW) — and this exact pattern **is** tested, correctly:
`test_mixed_elastic_and_inelastic_load_no_double_counting` (`test_opf_dc_demand.py:210-227`)
builds `ld_fixed` (30 MW, no bid) and `ld_elastic` (50 MW, full bid) at the same bus and proves
`g0` dispatches `80.0` (`30 + 50`, once, not `130`) — this *is* the "partial capacity, rest fixed"
case, correctly generalized, just expressed as two `Load` rows rather than one `Load` with a
split. Verified this pattern is nowhere explicitly documented as the intended workaround: `grep
-n "partial\|split\|entire\|whole" docs/manual/market.md src/mambo_power/model/entities.py
src/mambo_power/opf/dc_opf.py` finds no hit naming this convention. **Low-severity documentation
gap, not a correctness bug**: the code is right (re-confirmed by the existing test plus this
review's own reading of the double-counting contract, `opf/dc_opf.py:115-127`), but a reader
wanting "80% of this load is must-serve, 20% is price-responsive" would have to discover the
two-`Load` pattern by inference, not from any stated guidance.

**Settlement math recomputed by hand on AC-1/AC-4's own fixture, confirmed to match the
implementation, not just the test's assertion.** Two-bus network: `g1`@`b1` linear cost
$10/MWh, `g2`@`b2` linear cost $50/MWh, 20 MW-rated branch `b1`-`b2`, `d1`@`b2` with the 2-segment
PWL bid (value 45/MWh on `[0,50]`, 20/MWh on `[50,100]`). Optimum: `g1=20, g2=0, d1=20`,
`LMP(b1)=10, LMP(b2)=45`. By hand: `total_load_payment = LMP(b2)*d1 = 45*20 = 900`;
`total_generator_receipts = LMP(b1)*g1 + LMP(b2)*g2 = 10*20 + 45*0 = 200`; `congestion_rent =
900 - 200 = 700`. Cross-check via the flow side of the identity: the branch is at its 20 MW cap
(`g1`'s full 20 MW crosses it), `mu_flow = -35`, so `-mu_flow*flow = -(-35)*20 = 700` — matches.
This is exactly `results/market.py`'s documented formula (`total_load_payment`/
`total_generator_receipts`/`congestion_rent` fields, `:59-74`) and exactly what
`market/nodal.py:205-207` computes (`sum(lmp_by_bus_id[row.bus] * row.p_mw for row in loads)` etc.)
— **confirmed implemented as documented, not just as tested** (this hand recompute is
independent of `test_ac4_settlement_identity_holds_on_a_binding_flow_limit_network`,
`test_market_nodal.py:82-124`, which already does its own independent cross-check via a second
`dc_opf` call; this review's arithmetic is a third, fully independent path landing on the same
numbers).

No other correctness flag: `dc_opf`'s `NonConcaveBidError` guard (`opf/dc_opf.py:412-420`) and
the generator-side `c2 >= 0` guard (`:404-411`) are literal sign-mirrors, both raised before any
`Highs` object exists, matching the module docstring's own claim.

## 2. Readability — **PASS** (1 low flag)

Module sizes: `opf/dc_opf.py` 640 lines (up from M3's 376 — the elastic-demand extension roughly
doubled it, but the growth is almost entirely in the module docstring, which — like M3's own
docstring — derives its formulas rather than asserting them, and in genuinely new LP-building
code, not padding); `market/nodal.py` 219, `market/__init__.py` 9, `model/scenario.py` 25,
`results/market.py` 74, `numerics/arrays.py` 233, `jobs/registry.py` 172. Nothing crosses the
concerning-size line M1-M3's own reviews have implicitly used (~400+ lines of *logic*, not
docstring).

**`OpfSolution.demand_dispatch_mw`/`demand_bound` vs. `MarketNodalResult.loads`' framing is easy
to follow for a reader who knows M3's `opf` code, without needing the research doc** — verified by
reading both docstrings cold. `OpfSolution.demand_dispatch_mw` (`opf/dc_opf.py:218-225`) states
its own ordering rule self-containedly (`sorted(set(demand_bid_coeffs or {}) |
set(demand_pwl_bids or {}))`) and explicitly contrasts itself with `dispatch_mw` ("never
overloads... which stays generator-only"). `LoadDispatchResult` (`results/market.py:17-26`)
re-explains the *same* array-index-to-id mapping in Network-facing terms ("for a bid load, its
solved elastic dispatch... for a load with no bid, its own fixed historical `Load.p_mw`") and
states *why* every load (not just bid ones) gets a row — the settlement identity's own derivation.
A reader does not need to hold `dc_opf`'s array-index bookkeeping and `MarketNodalResult`'s
id-keyed rows in their head simultaneously; `market/nodal.py:170-188`'s inline comment bridges the
two directly at the one place they meet (`elastic_pos = {idx: j for j, idx in
enumerate(elastic_idxs)}`). This is the same "derive, don't assert" discipline M3's review praised
in `ac_newton.py`/`opf/dc_opf.py`'s original docstring, now extended cleanly to the demand side.

**Low flag: the all-or-nothing-per-`Load` modeling convention (§1 above) is a readability gap as
much as a documentation one** — a reader of `docs/manual/market.md`'s "Using it" section (`:220-
236`, the one `Load` with a bid the manual shows) has no cue that partial-capacity bidding requires
two `Load` rows rather than one. Low severity: the code's own behavior is unambiguous and correct
once discovered, and the double-counting docstring (`opf/dc_opf.py:115-127`) is honest about
exactly what it subtracts — but a manual reader trying to model a realistic "must-serve floor +
price-responsive remainder" load would not find this pattern without reading `dc_opf`'s own
implementation docstring.

No other readability flag: `NonConcaveBidError`/`NonConvexCostError` living in one module beside
each other (`opf/dc_opf.py:243-265`), the sign-mirrored construction spelled out in both
docstrings, is a genuinely good practice — the same "flag the surprising construct where a reader
would be surprised by it" discipline M3's review praised in `contingency/__init__.py`.

## 3. Architecture — **PASS**

**Import graph matches the diagram exactly.** `grep -n "^from mambo_power\|^import mambo_power"
src/mambo_power/market/*.py` → `market → mambo_power (top), model, numerics.arrays, opf.dc_opf,
results`. `docs/design/architecture.md:47-50` states exactly `market --> model`, `market -->
numerics`, `market --> opf`, `market --> results` — no missing or extra edge.
`docs/design/architecture.md:54` states `jobs --> market`; `jobs/registry.py:28` (`from
mambo_power.market.nodal import MarketNodalOptions, solve_nodal`) confirms it. No reverse edge
(`market → jobs`, `market → contingency`) exists in either direction — confirmed by the same grep
finding nothing in `market/` importing either.

**Closure check — every new public primitive traced to a real call path with genuine Step-5
evidence, not merely a grep hit:**

| Primitive | Production callsite | Test (direct) | Example |
|---|---|---|---|
| `dc_opf`'s `demand_bid_coeffs`/`demand_pwl_bids` params | `market.nodal.solve_nodal` (`market/nodal.py:131-138`) | `test_opf_dc_demand.py` (AC-1/AC-2, calls `dc_opf` directly with both param shapes) | `examples/09_nodal_market.py` (via `solve_nodal`) |
| `NonConcaveBidError` | raised inside `dc_opf` (`opf/dc_opf.py:416`), re-exported `market/__init__.py:7` | `test_opf_dc_demand.py:156-163` (`pytest.raises`, both PWL and polynomial triggers) | not exercised (by design — a valid example network) |
| `market.solve_nodal` | `jobs.registry._run_market_nodal` (`jobs/registry.py:133`) | `test_market_nodal.py` (AC-4/AC-5, direct call) | `examples/09_nodal_market.py:82` (`market.solve_nodal(Scenario(network=net))`) |
| `MarketNodalResult` | returned by `solve_nodal`, carried through `jobs.run`/`run_json` (`jobs/registry.py:169`) | `test_market_nodal.py`, `test_jobs.py` (JSON round-trip, `type(result) is MarketNodalResult`) | printed by example 09 |
| shared `_translate_non_optimal_status` | called by both `_run_opf_dc` (`jobs/registry.py:116`) and `_run_market_nodal` (`jobs/registry.py:135`) | `test_opf_dc_and_market_nodal_share_the_same_status_translation_function` (`test_jobs.py:427-445`) | n/a |

The shared-helper test is a genuine, re-read proof, not taken on the audit's word: it monkeypatches
`jobs_registry._translate_non_optimal_status` with a spy wrapping the *original* function object,
runs both kinds through an infeasible network, and asserts `calls == ["opf.dc", "market.nodal"]`
(`test_jobs.py:434-445`) — this can only pass if both runners call the identical function object,
not two copies. Confirmed by direct read, independent of `m4-audit.md`'s own citation of the same
test.

No architecture flag.

## 4. Security — **PASS**

**`PiecewiseBid.points` inherits the `max_length=200` bound M3's own R3 fold put on
`PiecewiseCost.points` — confirmed directly, not assumed from symmetry.**
`model/entities.py:113-118`: `points: list[tuple[float, float]] = Field(max_length=200, ...)`,
identical bound and near-identical description to `PiecewiseCost.points` (`:78-82`, also
`max_length=200`). This closes exactly the gap M3's own review flagged for the generator side
(`m3-review-6axis.md` §4, "`PiecewiseCost.points` has no upper bound") — the demand side was built
*with* the bound from the start, not requiring its own fold. `MarketNodalOptions`
(`market/nodal.py:47-56`) has zero fields (`extra="forbid", frozen=True`, no `Field` declarations
at all) — no caller-tunable numeric knob exists on this kind's options at all, mirroring
`OpfDcOptions`'s/`N1Options`'s own precedent M3's review already cleared.

**No bound on the *number* of loads (or generators) in a `Network`/`Scenario` — checked directly,
confirmed to be a pre-existing, systemic characteristic, not an M4-introduced gap.**
`Network.loads: list[Load] = Field(default_factory=list)` (`model/network.py:35`) carries no
`max_length`, and neither does `generators` (`:34`) — this predates M4 by two waves and applies
identically to every entity list in the schema (`buses`, `branches`, `shunts`), not specifically
to bid-carrying loads. `Scenario` (`model/scenario.py:25`) embeds `network: Network` directly with
no additional constraint layered on top. This is the same *class* of unbounded-caller-input
question M3's review raised for `PiecewiseCost.points`, but M3's own review scoped its finding to
per-entity breakpoint counts specifically (the thing that maps 1:1 to LP rows), not overall entity
counts — an unbounded number of loads is bounded in practice by the same linear LP-column-count
growth `PiecewiseCost`/`PiecewiseBid` already accept as proportionate (M3's own probe: 20,000
breakpoints, 0.169s, "roughly linear, not runaway"). Not a new M4 finding; noted as checked, not
silently assumed symmetric with the points-count question.

**No sensitive data reaches an error/status message.** `NonConcaveBidError`'s messages
(`opf/dc_opf.py:416-420`, `:304-309`) interpolate only an internal load index and the bid's own
numeric `v2`/slope value — the same class of non-sensitive diagnostic M3's review cleared for
`NonConvexCostError`. `_translate_non_optimal_status` (`jobs/registry.py:64-79`) passes through
only `kind` (a fixed string), `status` (HiGHS's own small status vocabulary) and `message` (already
cleared, above) — no dispatch value, bus/load id, or bid coefficient is ever interpolated into a
failure string reaching `jobs.run`'s boundary.

No security flag.

## 5. Performance — **PASS** (M3's own R3-fixed double-PTDF bug not repeated)

**`market.solve_nodal` builds `NetworkArrays` exactly once and never calls `compute_ptdf`
directly — confirmed by grep, not inference.** `grep -n "NetworkArrays.from_network\|compute_ptdf"
src/mambo_power/market/nodal.py` → one hit, `NetworkArrays.from_network(net)` at
`market/nodal.py:128`; zero hits for `compute_ptdf`/`ptdf(`. `solve_nodal` reuses
`solution.ptdf` — the PTDF matrix `dc_opf` already built internally to construct its own
flow-limit rows (`opf/dc_opf.py:507`, one call, inside `dc_opf` itself) and returns via
`OpfSolution.ptdf` (`opf/dc_opf.py:202-208`, whose own docstring names exactly the mechanism and
cites the M3 review finding it closes) — `market/nodal.py:156` (`ptdf_matrix = solution.ptdf`)
reads it off the solution rather than recomputing. This is the identical fix pattern
`opf.solve_dc_opf` itself uses (`opf/__init__.py:109-111`, same comment lineage) — confirmed both
callers of `dc_opf` (the pre-existing `solve_dc_opf` and this wave's new `solve_nodal`) inherited
the fix, neither reintroducing the ~62%-of-runtime bug M3's own review found and R3 fixed.

No `screen_n1`-style Python-level per-item loop exists in `market/nodal.py`: the generator/load/bus
row-building comprehensions (`:160-198`) are each a single O(n) pass over an already-materialized
array, no nested scalar-indexing loop of the kind M3's review flagged in `contingency/n1.py`.

`m4-step5-tests-floor.md`'s case14 `market.solve_nodal` cold timing (0.0208s) is consistent with
this: far under M3's `opf.solve_dc_opf` case300 cold baseline (0.3943s), and case14 is the smaller
network — no anomaly the code doesn't already explain.

No performance flag.

## 6. Duplication — **FLAG** (1 real, disclosed-but-unjustified duplication; ownership table
otherwise holds)

Ownership table, checked against the actual code, not assumed from the spec:

| Concept | Single site (spec claim) | Consumer(s) | Agreement test |
|---|---|---|---|
| Elastic-demand LP structure | `opf.dc_opf.dc_opf` (`opf/dc_opf.py:328`) | `market.nodal.solve_nodal` (`market/nodal.py:131`) | AC-1 (`test_opf_dc_demand.py`) |
| LMP/settlement math | `opf.dc_opf.lmp_decomposition` (`opf/dc_opf.py:315`) | `OpfDcResult.lmp` (M3), `MarketNodalResult`'s settlement fields (`market/nodal.py:157`) | AC-4 (`test_market_nodal.py`) |
| Demand bid data | `Load.bid` on `Network` (`model/entities.py:148`) | `market.nodal` via `Scenario.network` (`market/nodal.py:96`) | AC-3 |

The first two hold exactly as claimed — `grep -rn "def dc_opf\b\|def lmp_decomposition\b"
src/` → one definition each, both in `opf/dc_opf.py`; `market/nodal.py` calls, never
reimplements, either.

**But `market/nodal.py:_gen_cost_coeffs` (`:59-83`) is a byte-for-byte duplicate of
`opf/__init__.py:_cost_coeffs` (`:42-72`) — confirmed by direct diff, not estimated.** `diff` of
the two function bodies shows the only differences are the docstring text and one interpolated
string (`"opf.solve_dc_opf supports..."` vs. `"market.nodal supports..."` in the
`NotImplementedError` message) — every line of actual logic (the `gens_by_id` lookup, the
all-zero-row-for-no-cost/PWL convention, the `coeffs[i, 3 - len(values):] = values` right-align)
is identical. `market/nodal.py:62-64`'s own docstring discloses this rather than hiding it ("The
same extraction `mambo_power.opf._cost_coeffs` performs, mirrored here rather than imported (that
name is module-private)") — but "module-private" is a naming convention this codebase's own author
controls, not an architectural constraint; the function could have been exported (dropped
underscore, or re-exported from a shared location such as `opf/dc_opf.py`, which both `opf/
__init__.py` and `market/nodal.py` already import from) with zero cost. This is exactly the
"single source of truth" discipline the wave spec's own Design item 2 invokes for `Load.bid`
("matching the... discipline already applied everywhere else in this codebase") — not actually
applied here, on the generator-cost-extraction side specifically. Not the "source type differs"
exception the review brief anticipated: `_gen_cost_coeffs` and `_cost_coeffs` both extract from
`Network`/`Generator.cost` — the identical source type, not a different one; the genuinely
different-source-type function is `_load_bid_coeffs` (`market/nodal.py:86-111`, extracting from
`Load.bid` instead), which has no M2/M3 analog to duplicate and is not this finding. Low-to-moderate
severity — the duplication is small (25 lines), disclosed, and behaviorally inert (both copies are
correct and tested independently) — but it is real, avoidable, and the kind of thing that
compounds if a fourth wave needs generator-cost extraction again. Fix shape: export `_cost_coeffs`
(rename without the leading underscore, or move it to `opf/dc_opf.py` alongside `dc_opf`/
`lmp_decomposition`, which both `opf/__init__.py` and `market/nodal.py` already import from) and
have `market/nodal.py` import it instead of re-defining it.

No other duplication found: `_load_bid_coeffs` is genuinely new logic (demand-side, no prior-wave
analog); the shared status-translation helper (§3) is genuinely shared, not duplicated, confirmed
by the spy test; `PiecewiseBid`/`PiecewiseCost`'s `max_length=200` bound is stated once per class
(not a shared constant, but each class's own field constraint — consistent with `PolynomialCost`/
`PolynomialBid` also each declaring their own `coefficients` field independently, the established
convex/concave-mirror-pair pattern, not unjustified restatement).

---

## Verdicts

| Axis | Verdict |
|---|---|
| 1. Correctness | PASS (2 flags: the 3+-segment demand-side hypograph encoding is correct but untested by the shipped suite — closed here by a direct, independent probe, not by the wave's own evidence; the all-or-nothing-per-`Load` bid contract is correctly implemented and covered by the mixed-load test, but the two-`Load`-entities workaround for partial-capacity bidding is nowhere documented) |
| 2. Readability | PASS (1 low flag: the same undocumented two-`Load` convention, read from the manual-reader's side) |
| 3. Architecture | PASS (import graph matches the diagram exactly; every new public primitive traced to a real production callsite plus direct-test evidence, including the shared status-translation helper's spy-test proof, independently re-read) |
| 4. Security | PASS (`PiecewiseBid.points` inherits M3's `max_length=200` fix from the start, closing the exact gap M3's own review found on the cost side; no unbounded-work vector introduced; no sensitive data in any error path) |
| 5. Performance | PASS (`market.solve_nodal` builds `NetworkArrays` once, never calls `compute_ptdf` directly, reuses `dc_opf`'s own returned PTDF matrix — M3's own R3-fixed double-computation bug is not repeated in this wave's new call chain) |
| 6. Duplication | **FLAG** (`market.nodal._gen_cost_coeffs` is a confirmed byte-for-byte duplicate of `opf._cost_coeffs`, disclosed in its own docstring but not architecturally justified — cheap to fold by exporting the one function both modules already import alongside) |

No axis FAILs. The one FLAG is real, small, and non-gating: it does not threaten any AC, is not a
contract breach, and both copies are independently correct and tested. The two correctness/
readability flags are closed or nearly closed by this review's own direct evidence (the 3-segment
probe) rather than left open; the remaining gap in each is "add a test" / "add a doc sentence," not
"fix a bug."

## Recommended fold order

1. **P1 — export `_cost_coeffs` (or move it into `opf/dc_opf.py`) and have `market/nodal.py`
   import it instead of maintaining `_gen_cost_coeffs` as a second copy** (`opf/__init__.py:42-72`,
   `market/nodal.py:59-83`). Smallest fix in this review (drop one function, one import line);
   closes the one real duplication finding and the spec's own "single source of truth" claim
   becomes true on the generator-cost side too, not just the demand-bid side.
2. **T1 — add a 3+-segment concave PWL demand-bid test**, mirroring `test_opf_dc_pwl.py`'s own
   generator-side 3-segment case (`test_opf_dc_pwl.py:8`) — this review's own probe (§1) is a
   ready-made template (1-bus network, 3-segment bid, hand-predicted interior optimum). Closes the
   gap between "correct" (now confirmed, by this review) and "proven" (by the shipped suite).
3. **D1 — document the two-`Load`-entities pattern for partial-capacity elastic demand**, either
   in `docs/manual/market.md`'s "Using it" section or as an explicit note beside `Load.bid`'s field
   description (`model/entities.py:148`) — one or two sentences, no code change. Closes both the
   correctness-adjacent and readability flags in §1/§2 at once.

Items 1-3 are all small, scoped, behavior-preserving changes (1 and 3 touch no test-covered
behavior at all; 2 is test-only). Nothing here blocks the wave's own acceptance criteria or its
CONFIRMED audit verdict — this review found no wrong number and no contract breach; it found one
real, cheap-to-fold duplication and two real, cheap-to-close gaps between "correct" and "proven or
documented" that the wave's existing evidence did not surface because none of its tests or docs
were built to look for them.
