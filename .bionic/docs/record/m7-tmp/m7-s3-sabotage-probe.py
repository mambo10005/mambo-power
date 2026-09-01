import numpy as np
from mambo_power.model import Branch, Bus, Generator, Load, Network, PolynomialBid, PolynomialCost
from mambo_power.numerics import NetworkArrays
from mambo_power.opf import gen_cost_coeffs
from mambo_power.opf.dc_opf import OpfDcOptions, dc_opf
from mambo_power.market.nodal import load_bid_coeffs

def make_bid(v1=100.0, v2=-0.05):
    return PolynomialBid(coefficients=[v2, v1, 0.0])

def _network(gens, bid=None):
    bid = bid or make_bid()
    n = len(gens)
    buses = [Bus(id="b1", base_kv=138.0, type="slack")]
    buses += [Bus(id=f"b{i}", base_kv=138.0, type="pq") for i in range(2, n + 2)]
    branches = [Branch(id=f"l{i}", from_bus="b1", to_bus=f"b{i}", r=0.0, x=0.05, b=0.0) for i in range(2, n + 2)]
    gs = []
    for k, (gid, p_max, cost) in enumerate(gens):
        bus = "b1" if k == 0 else f"b{k+1}"
        gs.append(Generator(id=gid, bus=bus, p_mw=0.0, q_mvar=0.0, p_min_mw=0.0, p_max_mw=p_max,
                             q_min_mvar=-9999.0, q_max_mvar=9999.0, v_set_pu=1.0,
                             cost=PolynomialCost(coefficients=[cost, 0.0])))
    load = Load(id="d1", bus=f"b{n+1}", p_mw=1000.0, q_mvar=0.0, bid=bid)
    return Network(base_mva=100.0, buses=buses, branches=branches, generators=gs, loads=[load])

def clear(net, offers):
    arr = NetworkArrays.from_network(net)
    coeffs, pwl = gen_cost_coeffs(net, arr)
    idx = {gid: i for i, gid in enumerate(arr.gen_ids)}
    for gid, offer in offers.items():
        coeffs[idx[gid]] = [0.0, offer, 0.0]
    bidc, pwlb = load_bid_coeffs(net, arr)
    sol = dc_opf(arr, coeffs, OpfDcOptions(), pwl_costs=pwl or None, demand_bid_coeffs=bidc or None, demand_pwl_bids=pwlb or None)
    return arr, sol

print("== 1. smooth pivotal, cap sabotage (900 -> 300), offer 60 ==")
net = _network([("strategic", 300.0, 20.0)])
arr, sol = clear(net, {"strategic": 60.0})
i = list(arr.gen_ids).index("strategic")
print("dispatch", sol.dispatch_mw[i], "price", sol.duals.balance, "profit", (sol.duals.balance-20.0)*sol.dispatch_mw[i])

print("== 2. smooth pivotal, cost sabotage (20 -> 25) ==")
net = _network([("strategic", 900.0, 25.0)])
arr, sol = clear(net, {})
i = list(arr.gen_ids).index("strategic")
print("true-cost clearing: price", sol.duals.balance, "dispatch", sol.dispatch_mw[i])
arr, sol = clear(net, {"strategic": 62.5})
i = list(arr.gen_ids).index("strategic")
print("offer 62.5: price", sol.duals.balance, "dispatch", sol.dispatch_mw[i], "profit", (sol.duals.balance-25.0)*sol.dispatch_mw[i])

print("== 3. control, rival-cost sabotage (22 -> 20.5), strategic offer 21.5 ==")
net = _network([("strategic", 900.0, 20.0), ("rival", 900.0, 20.5)])
arr, sol = clear(net, {"strategic": 21.5})
i = list(arr.gen_ids).index("strategic")
j = list(arr.gen_ids).index("rival")
print("dispatch strategic", sol.dispatch_mw[i], "rival", sol.dispatch_mw[j], "price", sol.duals.balance,
      "strategic profit", (sol.duals.balance-20.0)*sol.dispatch_mw[i])

print("== 4. duopoly, cap sabotage (a: 300 -> 100), both offer 60 ==")
net = _network([("a", 100.0, 20.0), ("b", 300.0, 20.0)])
arr, sol = clear(net, {"a": 60.0, "b": 60.0})
ia = list(arr.gen_ids).index("a")
ib = list(arr.gen_ids).index("b")
print("dispatch a", sol.dispatch_mw[ia], "b", sol.dispatch_mw[ib], "price", sol.duals.balance,
      "joint profit", (sol.duals.balance-20.0)*(sol.dispatch_mw[ia]+sol.dispatch_mw[ib]))

print("== 5. bid-curve sabotage (v1: 100 -> 80), smooth pivotal true-cost clearing ==")
net = _network([("strategic", 900.0, 20.0)], bid=make_bid(v1=80.0, v2=-0.05))
arr, sol = clear(net, {})
i = list(arr.gen_ids).index("strategic")
print("true-cost clearing: price", sol.duals.balance, "dispatch", sol.dispatch_mw[i])
# new closed form peak: profit (pi-20)(800-10pi) -> derivative 800-10pi -10pi +200=1000-20pi=0 -> pi=50, q=300, profit=9000
arr, sol = clear(net, {"strategic": 50.0})
i = list(arr.gen_ids).index("strategic")
print("offer 50: price", sol.duals.balance, "dispatch", sol.dispatch_mw[i], "profit", (sol.duals.balance-20.0)*sol.dispatch_mw[i])
