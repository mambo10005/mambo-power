import sys
BASELINE_SRC = r"C:\Users\mambo\AppData\Local\Temp\m7-baseline-check\src"
sys.path.insert(0, BASELINE_SRC)

import mambo_power  # noqa
assert mambo_power.__file__.startswith(BASELINE_SRC.replace("\\", "/")) or "m7-baseline-check" in mambo_power.__file__, mambo_power.__file__
print("using mambo_power from:", mambo_power.__file__)

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

print("=== smooth pivotal (BASELINE 6ca9dcc) ===")
net = _network([("strategic", 900.0, 20.0)])
arr, sol = clear(net, {})
i = list(arr.gen_ids).index("strategic")
print("true cost:", sol.status, sol.duals.balance, sol.dispatch_mw[i], (sol.duals.balance-20.0)*sol.dispatch_mw[i])
arr, sol = clear(net, {"strategic": 60.0})
i = list(arr.gen_ids).index("strategic")
print("offer 60 :", sol.status, sol.duals.balance, sol.dispatch_mw[i], (sol.duals.balance-20.0)*sol.dispatch_mw[i])

print("=== control (BASELINE) ===")
net2 = _network([("strategic", 900.0, 20.0), ("rival", 900.0, 22.0)])
arr, sol = clear(net2, {"strategic": 21.5})
i = list(arr.gen_ids).index("strategic")
print("offer 21.5:", sol.status, sol.duals.balance, sol.dispatch_mw[i], (sol.duals.balance-20.0)*sol.dispatch_mw[i])

print("=== duopoly (BASELINE) ===")
net3 = _network([("a", 300.0, 20.0), ("b", 300.0, 20.0)])
arr, sol = clear(net3, {})
price = sol.duals.balance
print("true cost:", sol.status, price, sol.dispatch_mw)
arr, sol = clear(net3, {"a": 60.0, "b": 60.0})
price = sol.duals.balance
pa=(price-20)*sol.dispatch_mw[0]; pb=(price-20)*sol.dispatch_mw[1]
print("both 60  :", sol.status, price, sol.dispatch_mw, pa+pb)
