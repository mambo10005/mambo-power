"""Zonal clearing, min-cost redispatch, and what the pair costs against the nodal optimum.

What this shows:

* ``market.solve_zonal(scenario, options)`` -- **three** solves chained, not one: a zonal
  clearing that ignores the intra-zone grid, a minimum-cost redispatch that puts the resulting
  schedule back onto the real network, and ``market.solve_nodal`` as the reference the pair is
  measured against.
* A hand-solvable 2-zone/3-bus market first, where every number can be checked by eye: the
  corridor at its cap, two zone prices separated by exactly the two generators' cost difference,
  and the same market with the cap lifted, where the two prices collapse into one. Also the
  trap: *deleting* the corridor is not the copper plate, it islands the zones.
* case30 with its three MATPOWER areas promoted to real zones and corridor capacities derived
  from the cut-set branch ratings: which corridors bind, what each zone pays, and how far the
  operator has to move the fleet afterwards.
* The point of the whole exercise -- the zonal schedule overloads real branches, the
  redispatched one does not, and the redispatch is what that costs.
* The three separated figures, including the one that is **not** sign-constrained:
  ``generation_cost_gap`` here is *negative*, and reading it as "zonal beat nodal" is exactly
  the mistake it is separated out to prevent.
* Two identities computed from the result object alone: the settlement identity's flow-dual
  side (this is the first market result type carrying per-branch duals), and the redispatched
  point agreeing with ``market.solve_nodal`` -- which is a theorem, not a coincidence.

Run from the repository root: ``uv run python examples/11_zonal_redispatch.py``.
"""

from __future__ import annotations

from mambo_power import market, pf
from mambo_power.io import matpower
from mambo_power.model import (
    Branch,
    Bus,
    Generator,
    Load,
    Network,
    PolynomialCost,
    Scenario,
    Zone,
)
from mambo_power.numerics import NetworkArrays
from mambo_power.opf import gen_cost_coeffs
from mambo_power.opf.zonal import zonal_dc_opf

RATING_MARGIN = 1.2  # 20% headroom over the base-case flow, as in 08_opf_and_n1.py
RATING_FLOOR_MVA = 1.0  # so a near-zero base-case flow does not become a near-zero rating


def gen(gen_id: str, bus: str, price: float, p_max: float) -> Generator:
    """A generator offering a flat ``price`` \\$/MWh up to ``p_max`` MW."""
    return Generator(
        id=gen_id,
        bus=bus,
        p_mw=0.0,
        q_mvar=0.0,
        p_min_mw=0.0,
        p_max_mw=p_max,
        q_min_mvar=0.0,
        q_max_mvar=0.0,
        v_set_pu=1.0,
        cost=PolynomialCost(coefficients=[price, 0.0]),
    )


# --- 1. A hand-solvable 2-zone/3-bus market ---------------------------------------------------
# Zone A holds two buses joined by an unrated branch (so the zonal LP is right to carry no
# intra-zone flow row at all); zone B is one bus.  The A-B corridor is the only thing that can
# stop cheap zone-A power from serving zone B.
small = Network(
    base_mva=100.0,
    zones=[Zone(id="A"), Zone(id="B")],
    buses=[
        Bus(id="bus1", base_kv=138.0, type="slack", zone="A"),
        Bus(id="bus2", base_kv=138.0, type="pq", zone="A"),
        Bus(id="bus3", base_kv=138.0, type="pq", zone="B"),
    ],
    branches=[
        Branch(id="br12", from_bus="bus1", to_bus="bus2", r=0.0, x=0.1, b=0.0),
        Branch(id="br23", from_bus="bus2", to_bus="bus3", r=0.0, x=0.1, b=0.0, rating_mva=20.0),
    ],
    generators=[gen("genA", "bus1", 10.0, 200.0), gen("genB", "bus3", 50.0, 200.0)],
    loads=[
        Load(id="loadA", bus="bus2", p_mw=50.0, q_mvar=0.0),
        Load(id="loadB", bus="bus3", p_mw=30.0, q_mvar=0.0),
    ],
)
small_scenario = Scenario(network=small)

print("=== 1. Two zones, three buses, one corridor ===")
print("genA @ zone A: 10 $/MWh   genB @ zone B: 50 $/MWh   load: 50 MW in A, 30 MW in B")
small_payment: dict[str, float] = {}
for label, caps in (
    ("corridor capped at 20 MW", [market.CorridorLimit(zone1="A", zone2="B", cap_mw=20.0)]),
    # The copper plate: the corridor stays in the LP with no bound, so the two balance rows
    # collapse into one and the market clears as if the zones were one.  `cap_mw=None` *is*
    # unbounded -- a large finite cap would only be unbounded for a network this small.
    ("cap lifted (cap_mw=None)", [market.CorridorLimit(zone1="A", zone2="B", cap_mw=None)]),
    ("no corridor at all", []),
):
    res = market.solve_zonal(small_scenario, market.MarketZonalOptions(corridors=caps))
    prices = {z.id: z.price for z in res.zones}
    schedule = {g.id: g.p_mw for g in res.generators}
    small_payment[label] = res.redispatch_payment
    print(
        f"  {label:<26} price A {prices['A']:6.2f}  price B {prices['B']:6.2f}"
        f"   genA {schedule['genA']:6.2f} MW  genB {schedule['genB']:6.2f} MW"
    )
print("  the 40 $/MWh price split is exactly genB's cost minus genA's -- it is the corridor's")
print("  own capacity shadow price, and it vanishes the moment the corridor stops binding.")
print("  deleting the corridor is NOT the copper plate: with no exchange column the two balance")
print("  rows decouple, each zone self-supplies, and the prices separate as far as they can go.")
print(
    "  redispatch_payment across the three:"
    f"  capped {small_payment['corridor capped at 20 MW']:+8.2f}"
    f"   lifted {small_payment['cap lifted (cap_mw=None)']:+8.2f}"
    f"   deleted {small_payment['no corridor at all']:+8.2f}  $/h"
)
print("  the last one is NEGATIVE: the settlement figure is >= 0 only where the zonal LP is a")
print("  relaxation of the nodal one, i.e. where no corridor cap restricts an exchange more than")
print("  the network itself would.  Island the zones and the operator collects instead.")

# --- 2. case30: three areas promoted to zones, corridors from the cut-set ratings --------------
# case30's ZONE column is a single group, but its AREA column carries three real ones.  Branch
# ratings are derived from the base-case DC flows (case30's RATE_A is not used here, so there is
# one derivation rule and no mixed provenance), and each corridor's capacity is the sum of the
# ratings on the branches that cross it.
net = matpower.load("fixtures/matpower/case30.m")
base_flow_mw = {b.id: abs(b.p_from_mw) for b in pf.solve_dc(net).branches}
for br in net.branches:
    if br.id in base_flow_mw:
        br.rating_mva = max(RATING_MARGIN * base_flow_mw[br.id], RATING_FLOOR_MVA)

zone_of_bus = {bus.id: str(bus.area) for bus in net.buses}
net.zones = [Zone(id=zone_id) for zone_id in sorted(set(zone_of_bus.values()))]
for bus in net.buses:
    bus.zone = zone_of_bus[bus.id]

caps_mw: dict[tuple[str, str], float] = {}
for br in net.branches:
    z1, z2 = zone_of_bus[br.from_bus], zone_of_bus[br.to_bus]
    if z1 == z2 or br.rating_mva is None:
        continue
    key = (min(z1, z2), max(z1, z2))
    caps_mw[key] = caps_mw.get(key, 0.0) + br.rating_mva
corridors = [
    market.CorridorLimit(zone1=z1, zone2=z2, cap_mw=cap)
    for (z1, z2), cap in sorted(caps_mw.items())
]

scenario = Scenario(network=net)
result = market.solve_zonal(scenario, market.MarketZonalOptions(corridors=corridors))
buses_per_zone = {z.id: sum(1 for b in zone_of_bus.values() if b == z.id) for z in net.zones}

print("\n=== 2. case30, three zones ===")
print(f"status: {result.status}   buses per zone: {buses_per_zone}")
for corridor in corridors:
    crossing = sum(
        1
        for br in net.branches
        if {zone_of_bus[br.from_bus], zone_of_bus[br.to_bus]} == {corridor.zone1, corridor.zone2}
    )
    print(
        f"  corridor {corridor.zone1}-{corridor.zone2}: cap {corridor.cap_mw:7.3f} MW"
        f"  ({crossing} crossing branches)"
    )
for zone in result.zones:
    print(f"  zone {zone.id}: price {zone.price:.6f} $/MWh")
spread = max(z.price for z in result.zones) - min(z.price for z in result.zones)
print(f"  price spread across the three zones: {spread:.6f} $/MWh")

# A corridor's own flow and capacity shadow price are array-level quantities: MarketZonalResult
# reports zone prices, not corridor rows.  Call the zonal builder directly for them.
arr = NetworkArrays.from_network(net)
cost_coeffs, pwl_costs = gen_cost_coeffs(net, arr)
zonal = zonal_dc_opf(
    arr,
    cost_coeffs,
    {bus_id: zone_of_bus[bus_id] for bus_id in arr.bus_ids},
    caps_mw,
    pwl_costs=pwl_costs or None,
)
for k, key in enumerate(zonal.corridor_ids):
    flow = zonal.corridor_flow_mw[k]
    price = zonal.duals.corridor_cap[k]
    print(f"  corridor {key}: flow {flow:+8.4f} MW   capacity price {price:.6f} $/MWh")
print("  corridor (2,3) binds NEGATIVE -- zone 3 exports to zone 2, against the sorted key's own")
print("  direction -- and its capacity price is positive all the same: the price is a magnitude.")
print("  zones 1 and 3 are joined by the one slack corridor, so their balance duals are equal;")
print("  zone 2 separates by exactly the two binding corridors' capacity price.")

# --- 3. The zonal schedule is not deliverable; the redispatched one is -------------------------
# Read both dispatches back through pf.dc and compare each branch flow against its own rating.
# The energy balance is checked too, and deliberately: pf.dc pins the slack bus and lets it
# absorb whatever mismatch the declared injections carry, so a rating-respecting flow vector on
# its own is not proof that a dispatch is feasible.


def overloads(dispatch: dict[str, float]) -> tuple[int, float, float]:
    """(branches over rating, worst overload MW, slack absorption MW) for a generator schedule."""
    probe = net.model_copy(deep=True)
    for generator in probe.generators:
        generator.p_mw = dispatch[generator.id]
    solved = pf.solve_dc(probe)
    rating = {br.id: br.rating_mva for br in probe.branches}
    over = [
        abs(b.p_from_mw) - rating[b.id]
        for b in solved.branches
        if rating[b.id] is not None and abs(b.p_from_mw) > rating[b.id] + 1e-6
    ]
    slack_ids = {b.id for b in solved.buses if b.role_effective == "slack"}
    absorbed = sum(g.p_mw - dispatch[g.id] for g in solved.generators if g.bus in slack_ids)
    return len(over), max(over, default=0.0), absorbed


zonal_dispatch = {g.id: g.p_mw for g in result.generators}
final_dispatch = {g.id: g.p_mw for g in result.generators_final}
n_zonal, worst_zonal, slack_zonal = overloads(zonal_dispatch)
n_final, worst_final, slack_final = overloads(final_dispatch)
print("\n=== 3. Deliverability ===")
print(
    f"  zonal schedule: {n_zonal:2d} of {len(net.branches)} branches over rating"
    f"  (worst {worst_zonal:8.4f} MW)   slack absorbs {slack_zonal:+.3e} MW"
)
print(
    f"  redispatched:   {n_final:2d} of {len(net.branches)} branches over rating"
    f"  (worst {worst_final:8.4f} MW)   slack absorbs {slack_final:+.3e} MW"
)
moved_up = sum(g.delta_up_mw for g in result.redispatch_generators)
moved_down = sum(g.delta_down_mw for g in result.redispatch_generators)
touched = sum(1 for g in result.redispatch_generators if g.delta_up_mw + g.delta_down_mw > 1e-9)
print(
    f"  redispatch volume: +{moved_up:.3f} MW up / -{moved_down:.3f} MW down"
    f" across {touched} of {len(net.generators)} generators"
)

# --- 4. The three figures, and the one that is not sign-constrained ----------------------------
print("\n=== 4. What the zonal design cost ===")
print(f"  redispatch_payment  {result.redispatch_payment:+12.6f} $/h   settlement figure")
print(f"  welfare_gap         {result.welfare_gap:+12.3e} $/h   exactness row, 0 by construction")
print(f"  generation_cost_gap {result.generation_cost_gap:+12.6f} $/h   diagnostic, ANY sign")
print("  the third figure is negative here: the zonal clearing burns less fuel than the nodal")
print("  optimum.  It is not therefore cheaper -- it is serving the same demand from a dispatch")
print("  the network cannot carry, and the payment above is what un-carrying it costs.")
print("  the first figure is >= 0 here but not in general -- see part 1's deleted corridor.")
# The three figures are two independent quantities plus a check.  Under the theorem below,
# cost(final) == cost(nodal), so generation_cost_gap is exactly minus the payment's fuel term
# and the two published figures sum to the curtailment-compensation term alone -- zero on this
# fixture, which has no elastic demand, and the third field's entire independent content.
compensation = result.redispatch_payment + result.generation_cost_gap
print(f"  redispatch_payment + generation_cost_gap = {compensation:+.3e} $/h -- the curtailment")
print("  compensation term, and 0 on this fixed-load fixture: with no bids the third figure")
print("  carries nothing the first does not.  Put bids on the same case30 and it is +0.94 $/h.")

nodal = market.solve_nodal(scenario)
nodal_dispatch = {g.id: g.p_mw for g in nodal.generators}
worst_gen = max(abs(final_dispatch[g] - nodal_dispatch[g]) for g in nodal_dispatch)
nodal_lmp = {b.id: b.lmp for b in nodal.buses}
lmp_gaps = sorted((abs(b.lmp - nodal_lmp[b.id]) for b in result.buses), reverse=True)
print(f"  redispatched point vs market.solve_nodal: dispatch within {worst_gen:.2e} MW")
print("  (a theorem, not a tolerance sweep: the redispatch objective is the true welfare")
print("   function over nodal's own feasible set, so its optimum IS the nodal optimum)")

# The *primal* theorem above is exact.  The duals are a different matter on this fixture: more
# branches sit exactly at their rating than carry a price, so the optimum has several valid
# dual solutions and two LPs may legitimately pick different ones.  That is a property of the
# nodal problem, not of either builder -- and it is worth seeing rather than averaging away.
rating_by_id = {br.id: br.rating_mva for br in net.branches}
at_rating = [b.id for b in result.branches if abs(abs(b.p_from_mw) - rating_by_id[b.id]) < 1e-6]
priced = [b.id for b in result.branches if abs(b.flow_limit_dual) > 1e-9]
tight = [gap for gap in lmp_gaps if gap < 1e-4]
print(
    f"  LMPs: {len(tight)} of {len(lmp_gaps)} buses agree within {max(tight):.1e} $/MWh;"
    f" the rest differ by up to {lmp_gaps[0]:.3f} $/MWh"
)
print(
    f"  because the final point is primal-degenerate: {len(at_rating)} branches sit at their"
    f" rating, only {len(priced)} carry a nonzero dual"
)
print("  (put elastic bids on this same fixture and the two solves select the same dual solution")
print("   and every LMP agrees to 1e-5 -- the ambiguity is the nodal LP's, not either builder's)")

# --- 5. Both sides of the settlement identity, from the result object alone --------------------
lmp_by_bus = {b.id: b.lmp for b in result.buses}
load_payment = sum(lmp_by_bus[ld.bus] * ld.p_mw for ld in result.loads_final)
gen_receipts = sum(lmp_by_bus[g.bus] * g.p_mw for g in result.generators_final)
flow_dual_side = -sum(br.flow_limit_dual * br.p_from_mw for br in result.branches)
binding = sum(1 for br in result.branches if abs(br.flow_limit_dual) > 1e-9)
print("\n=== 5. Settlement identity, computed from MarketZonalResult alone ===")
print(f"  load payment {load_payment:.4f} - generator receipts {gen_receipts:.4f}", end="  ")
print(f"= {load_payment - gen_receipts:.6f} $/h")
print(f"  -sum_k(mu_k * flow_k) over {binding} binding branches = {flow_dual_side:.6f} $/h")
print(f"  residual: {abs((load_payment - gen_receipts) - flow_dual_side):.3e} $/h")
print("  no second solve and nothing from numerics/ or opf/ -- MarketZonalResult.branches is")
print("  the first market result surface carrying per-branch flows and their shadow prices.")
