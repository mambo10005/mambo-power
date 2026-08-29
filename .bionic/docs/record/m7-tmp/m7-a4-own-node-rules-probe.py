"""A4 probe: what can a STATELESS OWN-NODE agent actually do, and does it settle?

The A1 sweep used an exact grid best response -- the agent evaluating its own profit at every
candidate offer. Under D3b that is not computable: profit at a candidate offer requires clearing
the market, and the observation carries only the agent's own bus price, its own cleared MW, its
own true cost and capacity, and its own previous offer.

So the shipping MarkupStrategy must adjust incrementally. This measures the rules that ARE
computable from that observation, under both update orders.

Also checked: whether two separate dc_opf constructions on identical input agree bitwise
(AC-3(b) -- does the tolerance need to exist at all?).
"""

import numpy as np

from mambo_power.market.nodal import load_bid_coeffs
from mambo_power.model.entities import Branch, Bus, Generator, Load, PolynomialBid, PolynomialCost
from mambo_power.model.network import Network
from mambo_power.numerics.arrays import NetworkArrays
from mambo_power.opf.dc_opf import OpfDcOptions, dc_opf

V1, V2 = 100.0, -0.05
OPTS = OpfDcOptions()


def build(caps, costs):
    return Network(
        base_mva=100.0,
        buses=[Bus(id="b1", base_kv=138.0, type="slack"), Bus(id="b2", base_kv=138.0, type="pq")],
        branches=[Branch(id="l1", from_bus="b1", to_bus="b2", r=0.0, x=0.05, b=0.0,
                         rating_mva=9999.0)],
        generators=[
            Generator(id=f"g{k}", bus=bus, p_mw=0.0, q_mvar=0.0, p_min_mw=0.0, p_max_mw=cap,
                      q_min_mvar=-999.0, q_max_mvar=999.0, v_set_pu=1.0,
                      cost=PolynomialCost(coefficients=[c, 0.0]))
            for k, bus, cap, c in ((1, "b1", caps[0], costs[0]), (2, "b2", caps[1], costs[1]))
        ],
        loads=[Load(id="d1", bus="b2", p_mw=1000.0, q_mvar=0.0,
                    bid=PolynomialBid(coefficients=[V2, V1, 0.0]))],
    )


CAPS, COSTS = [300.0, 300.0], [20.0, 20.0]
net = build(CAPS, COSTS)
arr = NetworkArrays.from_network(net)
bid, pwl_bid = load_bid_coeffs(net, arr)
caps = np.array(CAPS)
costs = np.array(COSTS)


def clear(offers):
    coeffs = np.zeros((len(arr.gen_ids), 3))
    coeffs[:, 1] = offers
    sol = dc_opf(arr, coeffs, OPTS, demand_bid_coeffs=bid or None, demand_pwl_bids=pwl_bid or None)
    assert sol.status == "Optimal", sol.status
    return sol.dispatch_mw, float(sol.duals.balance)


# ---------------------------------------------------------------- AC-3(b): is a tolerance needed?
print("=== AC-3(b): two separate dc_opf constructions on identical input ===")
runs = [clear(costs.copy()) for _ in range(5)]
d0, l0 = runs[0]
exact = all(np.array_equal(d, d0) and lam == l0 for d, lam in runs)
print(f"5 independent dc_opf constructions, identical input: bitwise identical = {exact}")
print(f"  dispatch={d0.round(6).tolist()}  price={l0!r}")


# --------------------------------------------------- what a stateless own-node agent can compute
def rule_at_capacity(offer, cost, cap, price, mw, step):
    """R1 'raise while fully dispatched': at cap -> raise; below cap -> back off."""
    return max(cost, offer + step) if mw >= cap - 1e-6 else max(cost, offer - step)


def rule_chase_price(offer, cost, cap, price, mw, step):
    """R2 'move toward the price I just saw', never below my own cost."""
    if price > offer + 1e-9:
        return max(cost, min(offer + step, price))
    if price < offer - 1e-9 and mw <= 1e-6:
        return max(cost, offer - step)
    return offer


def rule_undercut_if_idle(offer, cost, cap, price, mw, step):
    """R3: at cap -> raise; dispatched but not at cap -> hold (I am marginal); idle -> back off."""
    if mw >= cap - 1e-6:
        return max(cost, offer + step)
    if mw <= 1e-6:
        return max(cost, offer - step)
    return offer


RULES = {"R1 at-capacity": rule_at_capacity,
         "R2 chase-price": rule_chase_price,
         "R3 hold-if-marginal": rule_undercut_if_idle}


def run(rule, simultaneous, step=0.5, max_rounds=300):
    offers = costs.copy()
    seen = {tuple(np.round(offers, 6)): 0}
    for r in range(1, max_rounds + 1):
        disp, price = clear(offers)
        prev = offers.copy()
        idxs = range(2) if simultaneous else [(r - 1) % 2]
        offers = prev.copy()
        for i in idxs:
            offers[i] = rule(prev[i], costs[i], caps[i], price, disp[i], step)
        if np.allclose(offers, prev, atol=1e-9):
            d, p = clear(offers)
            profits = [round(float((p - costs[i]) * d[i]), 2) for i in (0, 1)]
            return (f"settled r={r:<3d} offers={np.round(offers, 2).tolist()} "
                    f"price={p:6.2f} profit={profits}")
        key = tuple(np.round(offers, 6))
        if key in seen:
            return f"CYCLE period {r - seen[key]} (r{r} repeats r{seen[key]})"
        seen[key] = r
    return f"no settlement in {max_rounds} rounds"


print("\n=== incremental own-node rules, symmetric duopoly 300/300, cost 20/20, step 0.5 ===")
for name, rule in RULES.items():
    print(f"{name:22s} round-robin  : {run(rule, False)}")
    print(f"{'':22s} simultaneous : {run(rule, True)}")
