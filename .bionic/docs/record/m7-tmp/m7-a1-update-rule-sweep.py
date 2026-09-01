"""A1, part 2: how robust is the simultaneous-update cycle, and does damping fix it?

Variants swept: symmetric vs asymmetric capacity/cost, grid resolution, and three update rules
(simultaneous, alternating, damped simultaneous). Clearings are memoised per game — the grid
search re-visits the same offer pairs across rounds and rules.
"""

import sys

import numpy as np

from mambo_power.market.nodal import load_bid_coeffs
from mambo_power.model.entities import Branch, Bus, Generator, Load, PolynomialBid, PolynomialCost
from mambo_power.model.network import Network
from mambo_power.numerics.arrays import NetworkArrays
from mambo_power.opf.dc_opf import OpfDcOptions, dc_opf

V1, V2 = 100.0, -0.05  # marginal value = 100 - 0.1 * p
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


class Game:
    def __init__(self, caps, costs, step, hi=100.0):
        self.costs = np.array(costs, dtype=float)
        net = build(caps, costs)
        self.arr = NetworkArrays.from_network(net)
        self.bid, self.pwl_bid = load_bid_coeffs(net, self.arr)
        self.grid = np.round(np.arange(min(costs), hi + 1e-9, step), 4)
        self._memo: dict[tuple[float, float], tuple[np.ndarray, float]] = {}

    def clear(self, offers):
        key = (round(float(offers[0]), 6), round(float(offers[1]), 6))
        hit = self._memo.get(key)
        if hit is None:
            coeffs = np.zeros((len(self.arr.gen_ids), 3))
            coeffs[:, 1] = offers
            sol = dc_opf(self.arr, coeffs, OPTS, demand_bid_coeffs=self.bid or None,
                         demand_pwl_bids=self.pwl_bid or None)
            assert sol.status == "Optimal", sol.status
            hit = (sol.dispatch_mw, float(sol.duals.balance))
            self._memo[key] = hit
        return hit

    def profit(self, offers, i):
        disp, lmp = self.clear(offers)
        return float((lmp - self.costs[i]) * disp[i])

    def best_response(self, offers, i):
        trial, best_m, best_p = offers.copy(), offers[i], -np.inf
        for m in self.grid:
            trial[i] = m
            p = self.profit(trial, i)
            if p > best_p + 1e-9:
                best_p, best_m = p, m
        return float(best_m)


def run(game, rule, alpha=0.5, max_rounds=24):
    offers = game.costs.copy()
    seen = {tuple(np.round(offers, 6)): 0}
    for r in range(1, max_rounds + 1):
        prev = offers.copy()
        if rule == "simultaneous":
            offers = np.array([game.best_response(prev, 0), game.best_response(prev, 1)])
        elif rule == "alternating":
            offers = prev.copy()
            offers[(r - 1) % 2] = game.best_response(offers, (r - 1) % 2)
        else:
            br = np.array([game.best_response(prev, 0), game.best_response(prev, 1)])
            offers = prev + alpha * (br - prev)
        if np.allclose(offers, prev, atol=1e-6):
            _, lmp = game.clear(offers)
            return f"converged r={r:<2d} offers={np.round(offers, 2).tolist()} p={lmp:.2f}"
        key = tuple(np.round(offers, 6))
        if key in seen:
            return f"CYCLE period {r - seen[key]} (r{r} repeats r{seen[key]})"
        seen[key] = r
    return f"no settlement in {max_rounds} rounds"


CASES = [
    ("symmetric  300/300  cost 20/20  step 0.5", [300.0, 300.0], [20.0, 20.0], 0.5, 100.0),
    ("symmetric  300/300  cost 20/20  step 0.1", [300.0, 300.0], [20.0, 20.0], 0.1, 60.0),
    ("asym cap   300/250  cost 20/20  step 0.5", [300.0, 250.0], [20.0, 20.0], 0.5, 100.0),
    ("asym cost  300/300  cost 20/25  step 0.5", [300.0, 300.0], [20.0, 25.0], 0.5, 100.0),
    ("asym both  320/240  cost 18/26  step 0.5", [320.0, 240.0], [18.0, 26.0], 0.5, 100.0),
    ("slack cap  500/500  cost 20/20  step 0.5", [500.0, 500.0], [20.0, 20.0], 0.5, 100.0),
]

for label, caps, costs, step, hi in CASES:
    g = Game(caps, costs, step, hi)
    sim, alt, damp = run(g, "simultaneous"), run(g, "alternating"), run(g, "damped")
    print(f"{label}\n    simultaneous : {sim}\n    alternating  : {alt}\n    damped(0.5)  : {damp}")
    sys.stdout.flush()
