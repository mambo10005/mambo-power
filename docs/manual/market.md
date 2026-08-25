# Nodal market

`mambo_power.market` clears a day-ahead nodal energy market: generators and loads both bid,
the market dispatches to maximise welfare (generation cost minimised, demand value maximised)
subject to the same linearised network `opf.dc_opf` solves, and the result decomposes into
per-bus locational marginal prices (LMPs) and settlement. It is built directly on
[`opf.dc_opf`/`lmp_decomposition`](opf.md) — the welfare LP is `dc_opf` with an elastic-demand
extension, and the LMP math is `lmp_decomposition` called verbatim, not reimplemented.

| Entry point | Returns |
| --- | --- |
| `market.solve_nodal(scenario, options=None)` | `MarketNodalResult` |

Runnable script: [`09_nodal_market.py`](../examples/index.md#9-nodal-market).

## The `Scenario`

`solve_nodal` takes a [`Scenario`](model.md), not a bare `Network`: `Scenario(network=net)` is
presently a thin, self-contained wrapper (`network: Network`, nothing else yet) — mirroring
[`jobs.SolveRequest`](jobs.md)'s own self-contained pattern rather than an id/path
cross-reference, since no such resolution mechanism exists anywhere else in this codebase.
Bid data lives on the entities themselves, not on the scenario: a generator's offer is
`Generator.cost` (unchanged since M3) and a load's bid is the new `Load.bid`, a
`PolynomialBid | PiecewiseBid` discriminated union that mirrors `GeneratorCost` field-for-field
with one difference — direction. A load with `bid is None` stays fixed demand, exactly as
every M1–M3 network already behaves.

## Elastic demand inside the DC-OPF

`opf.dc_opf` gained two optional parameters this wave, `demand_bid_coeffs` and
`demand_pwl_bids`, both defaulting to `None` — every M2/M3 caller is unaffected. A load index
appearing in either becomes a new elastic-demand LP column, bounded
`[load_p_min_mw, load_p_max_mw]` (no sign flip: the column is the load's own served demand,
not a negative-bound pseudo-generator). The system-wide balance row and every PTDF-based
flow-limit row gain a matching `-1`-signed load term, the mirror image of the `+1`-signed
generator term already there. The LP/QP being solved is

\[
\min \sum_g \text{cost}(p_g) \;-\; \sum_d \text{value}(p_d)
\quad\text{s.t.}\quad
\sum_g p_g - \sum_d p_d = \text{fixed load} + \text{shunt},
\]

plus the same per-branch PTDF flow-limit rows `opf.md` describes, now carrying both generator
and elastic-load terms. A polynomial bid contributes a `(v2, v1, v0)` value row exactly as a
polynomial cost does; a piecewise-linear bid is encoded by a **hypograph** — the concave mirror
of the [convex epigraph encoding](opf.md#piecewise-linear-costs) already used for PWL generator
costs: one free `val_d` variable per PWL bid-load with objective coefficient `-1`, plus one
row per segment, `val_d <= slope_i·p_d + intercept_i`. Minimising `-Σval_d` pulls each `val_d`
up to the tightest bound, i.e. exactly `value(p_d)` at the optimum — because the hypograph's
segment slopes are non-increasing (concave), the lower envelope of these rows equals the true
piecewise value function exactly on `[p_min, p_max]`.

`OpfSolution.demand_dispatch_mw`/`demand_bound` are new, explicit fields — never overloading
the generator-side `dispatch_mw`/`gen_bound`. Order is `sorted(set(demand_bid_coeffs or {}) |
set(demand_pwl_bids or {}))`, the caller's own bid-index set ascending.

### Double-counting: `dc_opf`'s own contract

A load that becomes an elastic LP column must not *also* count as fixed demand in the balance
and flow-limit rows. `dc_opf` resolves this itself, not its caller: for every bid-load index it
removes that load's own historical contribution — read directly off
`NetworkArrays.load_p_max_pu[idx]`, at that load's own bus — from the fixed RHS before adding
the new LP column. This is safe because `load_p_max_pu[idx]` and that load's contribution to
the aggregate `p_load_pu` are provably the same number: both are built from the identical
`Load.p_mw` in `NetworkArrays.from_network`. The caller (`market.solve_nodal`) passes `arr`
completely unmodified — the same array it would build for a plain fixed-load solve — and
supplies bid coefficients only for whichever loads should be elastic.

### Convexity guards, both directions

`dc_opf` raises `market.NonConcaveBidError` before any HiGHS object is created if a bid's
marginal value is not non-increasing — a non-concave PWL breakpoint sequence, or a polynomial
bid with `v2 > 0`. This is the demand-side mirror of `NonConvexCostError`; both are re-exported
from `market` for convenience. Building the extension surfaced a pre-existing gap on the
generator side too: a quadratic `GeneratorCost` with `c2 < 0` (non-convex) was never checked
before this wave. Closed in the same commit, as `NonConvexCostError`, rather than shipping an
asymmetric guard — the fix is a byproduct of building the bid-side check, not evidence M3
shipped incomplete.

## `solve_nodal`

`solve_nodal(scenario, options=None) -> MarketNodalResult` pulls generator costs
(`Generator.cost`) and load bids (`Load.bid`) from `scenario.network`, calls the extended
`dc_opf`, and builds the result. Like `opf.solve_dc_opf`, it never raises for an infeasible or
unbounded LP/QP — reported through `MarketNodalResult.status`/`message` — and never modifies
the network. It does raise `NonConvexCostError`/`NonConcaveBidError` up front, before any solve
is attempted, for a non-convex cost or non-concave bid.

`MarketNodalResult.loads` carries one `LoadDispatchResult` for **every** load in the network,
bid or not — not only the elastic ones. A bid load's `p_mw` is its solved elastic dispatch and
`bound_dual` its bid-bound reduced cost; a load with no bid keeps its own fixed `Load.p_mw` and
`bound_dual == 0.0` (it was never an LP column, so it has no reduced cost). This mirrors the
settlement identity's own derivation (below), which sums `LMP · p_d` over every load, not just
the elastic ones — including every fixed load in the settlement was the natural reading of that
identity, not an arbitrary inclusion.

## LMPs, reused verbatim

`solve_nodal` calls `opf.dc_opf.lmp_decomposition(duals, ptdf)` — the identical function
`opf.solve_dc_opf` already calls, unmodified — to split every bus's price into

\[
\text{lmp}_b = \underbrace{\lambda_\text{balance}}_{\text{energy}} +
\underbrace{\sum_k \mu_k \cdot \text{PTDF}[k, b]}_{\text{congestion}} .
\]

See [DC-OPF › Duals and locational marginal prices](opf.md#duals-and-locational-marginal-prices)
for the full derivation; nothing about it changes with elastic demand in the picture, since the
duals `lmp_decomposition` consumes already account for the demand-side LP columns and rows.

## Settlement

`MarketNodalResult` reports three settlement fields, each computed directly rather than
asserted equal to the others by construction:

* `total_load_payment` — `Σ_d LMP(bus_d) · p_d` over every load.
* `total_generator_receipts` — `Σ_g LMP(bus_g) · p_g` over every generator.
* `congestion_rent` — `total_load_payment - total_generator_receipts`.

At the optimum these satisfy the settlement identity

\[
\sum_d \text{LMP}(bus_d) \cdot p_d \;-\; \sum_g \text{LMP}(bus_g) \cdot p_g \;=\;
-\sum_k \mu_k \cdot \text{flow}_k ,
\]

i.e. `congestion_rent` equals the negated sum of every binding flow-limit dual times its flow —
proved exactly on a hand-KKT-verified 2-bus case
(`tests/unit/test_opf_dc_demand.py::test_ac1_settlement_identity_holds_on_the_two_bus_case`) and
independently on real multi-bus fixtures with derived bids
(`tests/unit/test_market_nodal.py`). `congestion_rent` is 0 whenever no branch binds — the
common case on this package's bundled fixtures, none of which carries a real `RATE_A` (see
[DC-OPF › Formulation](opf.md#formulation)).

## The price-taker reduction

When every load's bid value exceeds every achievable price at every quantity up to its own
fixed historical demand, `solve_nodal`'s dispatch, duals, and LMPs are identical to plain
`opf.solve_dc_opf` called with that same demand as fixed load — bidding never changes the
outcome for a load that would always clear anyway. This is not a coincidence needing a special
case: it falls directly out of the welfare LP's own KKT conditions (a bid-load column pinned at
its own upper bound behaves exactly like a fixed-RHS load, since neither can absorb the
column's own upper-bound reduced cost). `tests/unit/test_market_nodal.py`'s AC-5 test proves it
directly with a hand-picked constant bid, and `tests/_bids.py`'s derived bids (below) confirm it
a second way, independently, against pandapower's own oracle.

## Oracle & fixtures: the `sgen` framing

No bundled MATPOWER fixture carries any load-bid data — the `.m` bus table has no such concept.
`tests/_bids.py` derives a bid curve **at test time** from a fixture's own already-committed
`Load.p_mw` and `Generator.cost` data, mirroring `tests/_rated.py`'s established discipline for
branch ratings: no new fixture data is committed, only a documented transformation of data the
fixture already owns. Each load's marginal value descends linearly from a value-of-lost-load
figure (`VOLL_PER_MWH = 10,000` \$/MWh, a round, literature-standard figure clearly above any
bundled fixture's own generation-fleet ceiling) at `p=0` down to that fixture's own
generation-fleet max marginal cost at `p = load.p_mw` — a genuinely concave, non-trivial
quadratic curve, not a degenerate flat step.

The pandapower oracle for this derived-bid data is built via the **`sgen` framing**: each bid
load is dropped as a `load` row and rebuilt as a sign-flipped, negative-bound `sgen`
(`min_p_mw = -p_mw, max_p_mw = 0`) with a poly-cost whose coefficients are the bid's own value
coefficients sign-flipped (`cost_sgen(p) = -value(-p)`) — proved exact against a hand KKT solve
before any test was written. This is the permanent, documented oracle-construction convention
for elastic demand in this codebase, alongside the existing `BASE_KV`/`trafo_model="pi"`
conventions — not the more natural-looking `load`-row framing (a genuine quadratic cost
attached directly to a `load` row), which reproducibly fails to converge in pandapower's
`rundcopp` for reasons not worth this wave's time to root-cause; `tests/parity/
test_market_nodal_vs_pandapower.py`'s own module docstring documents the bug precisely so a
future reader — or a pandapower upgrade — doesn't have to rediscover it. Measured tolerances on
case14 with every load bid: dispatch within `1e-6` MW, LMP within `1e-3` \$/MWh.

## Errors

`market.NonConvexCostError`/`market.NonConcaveBidError` (both `ValueError` subclasses,
re-exported from `opf.dc_opf`) are raised before any solve for a non-convex generator cost or
non-concave load bid. `solve_nodal` itself never raises for an infeasible or unbounded LP/QP —
reported through `MarketNodalResult.status`/`message`, mirroring `opf.solve_dc_opf`'s
never-raise convention. Through the [jobs API](jobs.md), a non-`"Optimal"` `market.nodal` job
comes back as a structured failure — `INFEASIBLE_LP` or `UNBOUNDED_LP`, via the same
non-Optimal-status translation `opf.dc`'s runner uses — not a "successful" result carrying a
meaningless dispatch.

## Using it

```python
from mambo_power import market
from mambo_power.model import (
    Branch,
    Bus,
    Generator,
    Load,
    Network,
    PiecewiseBid,
    PolynomialCost,
    Scenario,
)

net = Network(
    base_mva=100.0,
    buses=[Bus(id="b1", base_kv=138.0, type="slack"), Bus(id="b2", base_kv=138.0, type="pq")],
    branches=[Branch(id="br12", from_bus="b1", to_bus="b2", r=0.0, x=0.1, b=0.0, rating_mva=20.0)],
    generators=[
        Generator(
            id="g1",
            bus="b1",
            p_mw=0,
            q_mvar=0,
            p_min_mw=0,
            p_max_mw=100,
            q_min_mvar=0,
            q_max_mvar=0,
            v_set_pu=1.0,
            cost=PolynomialCost(coefficients=[10.0, 0.0]),
        ),
        Generator(
            id="g2",
            bus="b2",
            p_mw=0,
            q_mvar=0,
            p_min_mw=0,
            p_max_mw=100,
            q_min_mvar=0,
            q_max_mvar=0,
            v_set_pu=1.0,
            cost=PolynomialCost(coefficients=[50.0, 0.0]),
        ),
    ],
    loads=[
        Load(id="d0", bus="b1", p_mw=10.0, q_mvar=0.0),
        Load(
            id="d1",
            bus="b2",
            p_mw=100.0,
            q_mvar=0.0,
            bid=PiecewiseBid(points=[(0.0, 0.0), (50.0, 2250.0), (100.0, 3250.0)]),
        ),
    ],
)
result = market.solve_nodal(Scenario(network=net))
print(result.status)
print(result.loads[1].p_mw, result.buses[1].lmp, result.congestion_rent)
```

```text
Optimal
20.0 45.0 700.0
```

See [`09_nodal_market.py`](../examples/index.md#9-nodal-market) for the full printout: dispatch,
bound duals, per-bus LMP split into energy/congestion, and the settlement identity check.

## Jobs API

`market.nodal` is a registered [jobs](jobs.md) kind: `jobs.run(jobs.SolveRequest(kind=
"market.nodal", network=net))` wraps the network in a `Scenario` itself (the runner's own job,
not the caller's) and returns a `MarketNodalResult`. See [Jobs API › Failures are
data](jobs.md#failures-are-data) for the structured-failure shape.
