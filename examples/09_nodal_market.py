"""Nodal-market clearing: welfare-maximizing DC-OPF with elastic demand, LMPs, and settlement.

What this shows:

* ``market.solve_nodal(scenario)`` on a hand-built 2-bus network -- the same fixture-free style
  as the wave's own AC-1 hand-KKT test: a cheap slack generator, an expensive generator behind a
  rated branch, one load that bids a 2-segment piecewise-linear demand curve and one that stays
  fixed (unbid). ``MarketNodalResult`` reports every load, bid or fixed -- the unbid load still
  gets a dispatch/LMP row, just no reduced cost.
* The binding branch rating splits the LMP into energy + congestion, the identical decomposition
  ``opf.lmp_decomposition`` gives ``opf.solve_dc_opf`` (reused verbatim -- ADR-006, now exercised
  by its intended second consumer).
* The settlement identity: total load payment minus total generator receipts equals the
  congestion rent, which equals ``-sum(mu_k * flow_k)`` over the binding branches.

Run from the repository root: ``uv run python examples/09_nodal_market.py``.
"""

from __future__ import annotations

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
    buses=[
        Bus(id="b1", base_kv=138.0, type="slack"),
        Bus(id="b2", base_kv=138.0, type="pq"),
    ],
    branches=[
        Branch(id="br12", from_bus="b1", to_bus="b2", r=0.0, x=0.1, b=0.0, rating_mva=20.0),
    ],
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
            cost=PolynomialCost(coefficients=[10.0, 0.0]),  # 10 $/MWh, linear
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
            cost=PolynomialCost(coefficients=[50.0, 0.0]),  # 50 $/MWh, linear
        ),
    ],
    loads=[
        Load(id="d0", bus="b1", p_mw=10.0, q_mvar=0.0),  # fixed -- no bid
        Load(
            id="d1",
            bus="b2",
            p_mw=100.0,
            q_mvar=0.0,
            # 2-segment concave PWL bid: marginal value 45 $/MWh on [0, 50], 20 $/MWh on
            # [50, 100] (the wave's own hand-KKT example, see AC-1 in the wave spec).
            bid=PiecewiseBid(points=[(0.0, 0.0), (50.0, 2250.0), (100.0, 3250.0)]),
        ),
    ],
)

result = market.solve_nodal(Scenario(network=net))
print(f"status: {result.status}")

print("dispatch:")
for g in result.generators:
    print(f"  gen  {g.id:4s} bus {g.bus:3s} {g.p_mw:7.3f} MW  bound dual {g.bound_dual:7.3f}")
for d in result.loads:
    tag = "  (fixed, no bid)" if d.id == "d0" else ""
    print(f"  load {d.id:4s} bus {d.bus:3s} {d.p_mw:7.3f} MW  bound dual {d.bound_dual:7.3f}{tag}")

print("LMPs:")
for b in result.buses:
    print(f"  {b.id}: lmp {b.lmp:7.3f}  energy {b.energy:7.3f}  congestion {b.congestion:7.3f}")

print(
    f"settlement: load payment {result.total_load_payment:.2f}  "
    f"generator receipts {result.total_generator_receipts:.2f}  "
    f"congestion rent {result.congestion_rent:.2f}"
)
identity_holds = (
    abs((result.total_load_payment - result.total_generator_receipts) - result.congestion_rent)
    < 1e-6
)
print(f"settlement identity (payment - receipts == congestion rent) holds: {identity_holds}")
