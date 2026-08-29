import numpy as np
from mambo_power.model import Branch, Bus, Generator, Load, Network, PolynomialBid, PolynomialCost
from mambo_power.numerics import NetworkArrays
from mambo_power.opf import gen_cost_coeffs
from mambo_power.opf.dc_opf import OpfDcOptions, dc_opf
from mambo_power.market.nodal import load_bid_coeffs

DEMAND_BID = PolynomialBid(coefficients=[-0.05, 100.0, 0.0])
LOAD_P_MAX_MW = 1000.0

def _network(gens):
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
    load = Load(id="d1", bus=f"b{n+1}", p_mw=LOAD_P_MAX_MW, q_mvar=0.0, bid=DEMAND_BID)
    return Network(base_mva=100.0, buses=buses, branches=branches, generators=gs, loads=[load])

def clear(net, offers):
    arr = NetworkArrays.from_network(net)
    coeffs, pwl = gen_cost_coeffs(net, arr)
    idx = {gid: i for i, gid in enumerate(arr.gen_ids)}
    for gid, offer in offers.items():
        coeffs[idx[gid]] = [0.0, offer, 0.0]
    bid, pwlb = load_bid_coeffs(net, arr)
    sol = dc_opf(arr, coeffs, OpfDcOptions(), pwl_costs=pwl or None, demand_bid_coeffs=bid or None, demand_pwl_bids=pwlb or None)
    return arr, sol

def profit(arr, sol, gid, true_cost):
    i = list(arr.gen_ids).index(gid)
    price = sol.duals.balance
    return (price - true_cost) * sol.dispatch_mw[i], price, sol.dispatch_mw[i]

print("=== smooth pivotal ===")
net = _network([("strategic", 900.0, 20.0)])
arr, sol = clear(net, {})
p, price, d = profit(arr, sol, "strategic", 20.0)
print("true cost:", "price", price, "dispatch", d, "profit", p, "status", sol.status)
arr, sol = clear(net, {"strategic": 60.0})
p, price, d = profit(arr, sol, "strategic", 20.0)
print("offer 60 :", "price", price, "dispatch", d, "profit", p, "status", sol.status)

print("=== control ===")
net2 = _network([("strategic", 900.0, 20.0), ("rival", 900.0, 22.0)])
arr, sol = clear(net2, {})
p, price, d = profit(arr, sol, "strategic", 20.0)
print("true cost:", "price", price, "dispatch", d, "profit", p, "status", sol.status)
arr, sol = clear(net2, {"strategic": 21.5})
p, price, d = profit(arr, sol, "strategic", 20.0)
print("offer 21.5:", "price", price, "dispatch", d, "profit", p, "status", sol.status)

print("=== duopoly ===")
net3 = _network([("a", 300.0, 20.0), ("b", 300.0, 20.0)])
arr, sol = clear(net3, {})
price = sol.duals.balance
pa = (price-20.0)*sol.dispatch_mw[list(arr.gen_ids).index("a")]
pb = (price-20.0)*sol.dispatch_mw[list(arr.gen_ids).index("b")]
print("true cost:", "price", price, "dispatch", sol.dispatch_mw, "joint profit", pa+pb, "status", sol.status)
arr, sol = clear(net3, {"a": 60.0, "b": 60.0})
price = sol.duals.balance
pa = (price-20.0)*sol.dispatch_mw[list(arr.gen_ids).index("a")]
pb = (price-20.0)*sol.dispatch_mw[list(arr.gen_ids).index("b")]
print("both 60  :", "price", price, "dispatch", sol.dispatch_mw, "joint profit", pa+pb, "status", sol.status)
