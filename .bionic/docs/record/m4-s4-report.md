# M4 S4 — market-nodal: `solve_nodal`, `MarketNodalResult`, settlement

Slice S4 (senior-implementor, complex). TDD throughout: RED (`tests/unit/test_market_nodal.py`
written first, confirmed failing on `ModuleNotFoundError: No module named 'mambo_power.market'`),
then implementation, then GREEN (3/3 on first implementation attempt — one incorrect assertion
in a same-slice non-AC test was fixed before commit, not a source bug; see "One test fix" below).

## What was built

**`src/mambo_power/market/nodal.py`** (new package `market/`, per the epic's own module table):

1. **`solve_nodal(scenario: Scenario, options: MarketNodalOptions | None = None) ->
   MarketNodalResult`** — the `Scenario`-facing welfare-maximizing DC-OPF entry point, mirroring
   `opf.solve_dc_opf`'s own shape (provenance stamp, PTDF reuse, id-keyed result rows). Extracts
   generator costs from `scenario.network.generators[i].cost` (`_gen_cost_coeffs`, structurally
   identical to `opf._cost_coeffs` — mirrored locally rather than imported, since that name is
   module-private) and load bids from `scenario.network.loads[i].bid` (`_load_bid_coeffs`, the
   demand-side twin). Builds `NetworkArrays` from `scenario.network` **unmodified** (S3's
   contract: `dc_opf` itself does the fixed-load-vs-elastic-column double-counting subtraction).
   Calls the extended `dc_opf` with both `cost_coeffs`/`pwl_costs` and
   `demand_bid_coeffs`/`demand_pwl_bids` — a load with `bid=None` contributes to neither demand
   mapping, so it stays purely on the fixed-RHS side, exactly as `dc_opf` already handles it.
   Calls `lmp_decomposition` (M3's, imported and used verbatim — no reimplementation).
2. **`MarketNodalResult`** (`src/mambo_power/results/market.py`, new): `generators` (reuses
   `results.opf.GenDispatchResult` verbatim), `loads` (new `LoadDispatchResult`), `buses`
   (reuses `results.opf.BusLmpResult` verbatim), plus settlement — `total_load_payment`,
   `total_generator_receipts`, `congestion_rent`. `provenance`/`status`/`message` mirror
   `OpfDcResult`'s own never-raise-on-infeasible convention.
3. **`MarketNodalOptions`** — deliberately empty (mirrors `OpfDcOptions`'s own stated precedent:
   a tunable field is added the first time a caller actually needs one, not invented
   speculatively), present now so a future `jobs` `KindSpec` (S6) has a stable model to validate
   requests against.

## Design decision: every load gets a dispatch row, not just bid loads

`MarketNodalResult.loads` includes **every** load in the network, bid or not — a non-bid load's
row reports its own fixed `Load.p_mw` with `bound_dual=0.0` (it never became an LP column). This
was not spelled out explicitly in the dispatch but follows directly from `m4-research.md` §4.1's
own derivation: the settlement identity `Σ_d LMP(bus_d)·p_d − Σ_g LMP(bus_g)·p_g = −Σ_k
μ_k·flow_k` is proved to hold "whether or not `p_d` is a decision variable" — its derivation sums
over *every* load, not just the elastic ones. Restricting `MarketNodalResult.loads` (and
therefore `total_load_payment`) to only bid loads would silently break the identity on any
network with a mix of fixed and elastic loads, which is the realistic case this wave's own
`test_mixed_elastic_and_inelastic_load_no_double_counting` fixture (S3) already established as a
first-class scenario. `total_load_payment`/`total_generator_receipts` therefore sum over the full
`loads`/`generators` lists, computed directly from each row's `p_mw` and its bus's LMP — a
genuinely independent quantity, not asserted equal to the flow-based identity by construction
(see AC-4 evidence below for how the test proves the two sides agree).

## Settlement fields: computed independently, proved equal by the test (not by construction)

Per the dispatch's own instruction, `congestion_rent` is `total_load_payment −
total_generator_receipts` — computed from dispatch and LMPs directly (the identity's *left*
side), not from `−Σ_k μ_k·flow_k` (the *right* side). The AC-4 test computes the right side
independently, via a **separate, direct `dc_opf()` call** (not through `solve_nodal`) that reads
`OpfSolution.ptdf`/`OpfDuals.flow_limit` and reconstructs branch flow from net injection, then
asserts the two sides match to `1e-4`. This is a real proof, not a restatement: the two numbers
come from two different code paths (`solve_nodal`'s payment/receipt subtraction vs. a
PTDF-times-injection flow computation), and both independently reproduce `m4-research.md`
§4.1's hand-KKT value, 700.0.

## RED/GREEN evidence

RED (before implementation):
```
$ uv run --no-sync pytest -q tests/unit/test_market_nodal.py
ModuleNotFoundError: No module named 'mambo_power.market'
```

GREEN (after implementation):
```
$ uv run --no-sync pytest -q tests/unit/test_market_nodal.py
...                                                                      [100%]
3 passed in 4.20s
```

## One test fix (not a source bug)

The first GREEN pass failed one assertion in a non-AC helper test
(`test_ac4_dispatch_and_lmp_rows_are_id_keyed_and_cover_every_generator_and_load`): I had written
`assert d1.bound_dual != 0.0`, wrongly assuming `d1` (dispatched at 20 MW on a `[0, 100]` bid
bound, limited by the branch's flow rating rather than its own bid cap) would be pinned at a
bound. It isn't — 20 MW is an interior point of `[0, 100]`, so the reduced cost is correctly
`0.0`; the binding constraint here is the branch's flow limit, which shows up in bus `b2`'s LMP
congestion component instead (already asserted correctly elsewhere in the AC-4 test). Fixed the
assertion (and its comment) to match; no `market/nodal.py`/`results/market.py` code was touched
to make this pass — confirmed by re-running with the corrected assertion, GREEN, no other
changes.

## AC-4 evidence

`test_ac4_settlement_identity_holds_on_a_binding_flow_limit_network` reuses the exact two-bus
network `m4-research.md` §4.1 / S3's own AC-1 test hand-derive (slack `b1`/`g1` linear cost 10,
`b2`/`g2` linear cost 50, one 20 MW-rated branch, load `d1` at `b2` with a 2-segment concave PWL
bid) — but built through `Generator.cost`/`Load.bid`/`Scenario`, so `solve_nodal`'s own
extraction (`_gen_cost_coeffs`/`_load_bid_coeffs`) is what's under test, not `dc_opf` directly.
Result, to `1e-4`–`1e-6`:

```
dispatch: g1=20.0, g2=0.0, d1=20.0
LMP(b1)=10.0   LMP(b2)=45.0
solve_nodal's own: total_load_payment=900.0, total_generator_receipts=200.0,
                    congestion_rent=700.0
independent right-side check (direct dc_opf() call, separate PTDF/duals path):
                    -Σ μ_k·flow_k = 700.0   <- matches congestion_rent exactly
```

`test_ac4_dispatch_and_lmp_rows_are_id_keyed_and_cover_every_generator_and_load` confirms every
generator/load/bus in the network gets exactly one row (`{g1, g2}`, `{d1}`, `{b1, b2}`), id-keyed.

## AC-5 evidence

`test_ac5_price_taker_reduction_matches_plain_opf_dc_opf` gives `d1` a constant marginal-value
bid (`PolynomialBid(coefficients=[1000.0, 0.0])`, i.e. `v1=1000`, `v2=0`) — 1000 exceeds both
generators' marginal costs (10, 50) at every quantity up to `d1`'s own fixed historical demand
(100 MW), the precise condition `m4-research.md` §4.2 states. Result: `d1` is pinned exactly at
100 MW (`bound_dual != 0.0`, confirming it's genuinely at its bound, not coincidentally equal),
and every one of `solve_nodal`'s outputs — generator dispatch, generator bound duals, bus LMPs,
bus congestion components — matches `opf.solve_dc_opf` called on the identical network with `d1`
fixed (`bid=None`) to `1e-6`. This reduces exactly to M3's own already-oracle-proved `opf.dc_opf`
parity, per the spec's own framing of AC-5 as the wave's main correctness test.

## Full suite / lint / type evidence

```
$ uv run --no-sync pytest -q
630 passed, 10 warnings in 168.56s
```
(630 = 627 before this slice + 3 new — reconciles exactly.)

```
$ uv run --no-sync ruff check .
All checks passed!
$ uv run --no-sync ruff format --check .
134 files already formatted
$ uv run --no-sync mypy
Success: no issues found in 43 source files
```

(`ruff format .` needed one pass on `market/nodal.py`'s `solve_nodal` signature line, applied
before the commit — no logic changed.)

## Commit

`ec4ba22` on `wave/04-nodal-market` (on top of S1+S2+S3's `972d7f9`), pushed. Staged exactly the
five files this slice touched: `src/mambo_power/market/__init__.py`,
`src/mambo_power/market/nodal.py`, `src/mambo_power/results/market.py`,
`src/mambo_power/results/__init__.py` (export addition), `tests/unit/test_market_nodal.py`.

Plan updated (`.bionic/docs/plans/epic-01-foundation/wave-04-nodal-market.plan.md`): AC-4/AC-5
evidence blocks filled, both status cells flipped `pending` → `done`, dispatch ledger row for
`m4-s4-market-nodal` flipped `active` → `done` with the real commit sha.

## Not done by this slice (explicitly out of scope, per the dispatch)

`opf/dc_opf.py`'s LP internals (S3's, untouched — this slice is a pure consumer), `tests/_bids.py`
or any fixture-bid-derivation work (S5's job), `jobs/` (S6's job), `docs/` (S7's job). `AC-6`
(pandapower `sgen`-framed oracle parity) is explicitly S5's, not attempted here.
