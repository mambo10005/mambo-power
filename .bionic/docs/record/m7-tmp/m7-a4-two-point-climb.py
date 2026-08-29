"""A4, part 2: does a two-point own-node observation make the walk reachable?

Part 1 showed the one-point own-node rules either cycle or settle at a ~zero-markup point: a
stateless agent that sees only (offer_prev, price_prev, mw_prev) can tell whether it is marginal,
but not whether its last move HELPED -- that needs its profit at t-1 AND t-2.

Minimal fix under test: the observation carries the agent's own last TWO rounds. Still own-node,
still no rival information, and the strategy stays a pure function of its observation -- the loop
supplies the history, the agent holds none.

Two fixtures: the symmetric duopoly from A1, and an AC-4-shaped single pivotal supplier facing a
competitive fringe, whose profit peak is derivable in closed form.
"""

import numpy as np

from mambo_power.market.nodal import load_bid_coeffs
from mambo_power.model.entities import Branch, Bus, Generator, Load, PolynomialBid, PolynomialCost
from mambo_power.model.network import Network
from mambo_power.numerics.arrays import NetworkArrays
from mambo_power.opf.dc_opf import OpfDcOptions, dc_opf

V1, V2 = 100.0, -0.05  # marginal value = 100 - 0.1 * p  =>  q(price) = 1000 - 10 * price
OPTS = OpfDcOptions()


def build(caps, costs):
    n = len(caps)
    return Network(
        base_mva=100.0,
        buses=[Bus(id="b1", base_kv=138.0, type="slack")]
        + [Bus(id=f"b{i}", base_kv=138.0, type="pq") for i in range(2, n + 2)],
        branches=[Branch(id=f"l{i}", from_bus="b1", to_bus=f"b{i}", r=0.0, x=0.05, b=0.0,
                         rating_mva=9999.0) for i in range(2, n + 2)],
        generators=[
            Generator(id=f"g{i}", bus="b1" if i == 0 else f"b{i + 1}", p_mw=0.0, q_mvar=0.0,
                      p_min_mw=0.0, p_max_mw=caps[i], q_min_mvar=-999.0, q_max_mvar=999.0,
                      v_set_pu=1.0, cost=PolynomialCost(coefficients=[costs[i], 0.0]))
            for i in range(n)
        ],
        loads=[Load(id="d1", bus=f"b{n + 1}", p_mw=1000.0, q_mvar=0.0,
                    bid=PolynomialBid(coefficients=[V2, V1, 0.0]))],
    )


class Market:
    def __init__(self, caps, costs, reactive):
        self.caps, self.costs = np.array(caps, float), np.array(costs, float)
        self.reactive = reactive
        net = build(caps, costs)
        self.arr = NetworkArrays.from_network(net)
        self.bid, self.pwl = load_bid_coeffs(net, self.arr)

    def clear(self, offers):
        coeffs = np.zeros((len(self.arr.gen_ids), 3))
        coeffs[:, 1] = offers
        sol = dc_opf(self.arr, coeffs, OPTS, demand_bid_coeffs=self.bid or None,
                     demand_pwl_bids=self.pwl or None)
        assert sol.status == "Optimal", sol.status
        return sol.dispatch_mw, float(sol.duals.balance)


def hill_climb(mkt, step=0.5, max_rounds=400, simultaneous=True):
    """Two-point own-node hill climb: keep the last direction if it raised MY profit, else flip."""
    n = len(mkt.caps)
    offers = mkt.costs.copy()
    disp, price = mkt.clear(offers)
    profit_prev2 = np.array([(price - mkt.costs[i]) * disp[i] for i in range(n)])
    offers_prev2 = offers.copy()
    offers = offers.copy()
    for i in mkt.reactive:
        offers[i] += step  # round 1: probe upward
    disp, price = mkt.clear(offers)
    profit_prev = np.array([(price - mkt.costs[i]) * disp[i] for i in range(n)])

    seen = {}
    for r in range(2, max_rounds + 1):
        nxt = offers.copy()
        idxs = mkt.reactive if simultaneous else [mkt.reactive[(r - 2) % len(mkt.reactive)]]
        for i in idxs:
            direction = np.sign(offers[i] - offers_prev2[i]) or 1.0
            if profit_prev[i] < profit_prev2[i] - 1e-9:
                direction = -direction
            nxt[i] = max(mkt.costs[i], offers[i] + direction * step)
        if np.allclose(nxt, offers, atol=1e-9):
            d, p = mkt.clear(nxt)
            return r, nxt, p, d, "settled"
        key = tuple(np.round(np.concatenate([offers, nxt]), 6))
        if key in seen:
            d, p = mkt.clear(nxt)
            return r, nxt, p, d, f"oscillating (period {r - seen[key]}) around the peak"
        seen[key] = r
        offers_prev2, profit_prev2 = offers, profit_prev
        offers = nxt
        d, price = mkt.clear(offers)
        profit_prev = np.array([(price - mkt.costs[i]) * d[i] for i in range(n)])
    return max_rounds, offers, price, disp, "no settlement"


def show(label, mkt, **kw):
    r, offers, price, disp, why = hill_climb(mkt, **kw)
    prof = [round(float((price - mkt.costs[i]) * disp[i]), 2) for i in mkt.reactive]
    print(f"{label}\n    r={r:<4d} {why}\n    offers={np.round(offers, 2).tolist()}  "
          f"price={price:.2f}  dispatch={np.round(disp, 2).tolist()}  reactive profit={prof}")


# ---- Fixture 1: the A1 symmetric duopoly, both agents reactive ------------------------------
duo = Market([300.0, 300.0], [20.0, 20.0], reactive=[0, 1])
d, p = duo.clear(duo.costs)
print("=== duopoly 300/300, cost 20/20 ===")
print(f"    true-cost offers: price={p:.2f} dispatch={np.round(d, 2).tolist()} "
      f"profit={[round(float((p - 20) * d[i]), 2) for i in (0, 1)]}")
show("  two-point hill climb, simultaneous", duo, simultaneous=True)
show("  two-point hill climb, round-robin ", duo, simultaneous=False)

# ---- Fixture 2: AC-4 shape -- one pivotal supplier + a competitive fringe -------------------
# q(price) = 1000 - 10*price.  Fringe: 100 MW at $35.  Strategic: 900 MW at $20.
# Above $35 the fringe is in, so the strategic unit's residual demand is 900 - 10*price;
# profit (price-20)(900-10*price) peaks at price = $55, q = 350 MW, profit = $12,250/h.
piv = Market([900.0, 100.0], [20.0, 35.0], reactive=[0])
d, p = piv.clear(piv.costs)
print("\n=== pivotal 900@20 + fringe 100@35 ===")
print(f"    true-cost offers: price={p:.2f} dispatch={np.round(d, 2).tolist()} "
      f"strategic profit={(p - 20) * d[0]:.2f}")
print("    closed-form peak: price=55.00  q=350.00  profit=12250.00")
show("  two-point hill climb", piv)

# ---- Fixture 3: smooth pivotal -- one strategic supplier, NO fringe step --------------------
# Residual demand is the whole curve: profit (price-20)(1000-10*price) peaks at price=$60,
# q=400 MW, profit=$16,000/h. No discontinuity between the true cost and the peak.
smooth = Market([900.0, 1.0], [20.0, 999.0], reactive=[0])
d, p = smooth.clear(smooth.costs)
print("\n=== smooth pivotal 900@20 (no fringe step) ===")
print(f"    true-cost offers: price={p:.2f} dispatch={d[0]:.2f} profit={(p - 20) * d[0]:.2f}")
print("    closed-form peak: price=60.00  q=400.00  profit=16000.00")
for st in (0.5, 1.0, 2.0):
    show(f"  two-point hill climb, step={st}", smooth, step=st)
