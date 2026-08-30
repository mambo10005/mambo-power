"""P3: generator/load flagged in_service=True but attached to a bus that is itself
in_service=False. Does the model/solver handle this consistently (ignore it) or does
it silently mis-account power (double count, index error, or count toward totals)?"""
from mambo_power.model import Branch, Bus, Generator, Load, Network
from mambo_power.pf import solve_ac, solve_dc
from mambo_power.numerics.arrays import NetworkArrays

buses = [
    Bus(id="s", base_kv=230, type="slack"),
    Bus(id="a", base_kv=230, type="pq"),
    Bus(id="dead", base_kv=230, type="pq", in_service=False),
]
branches = [Branch(id="s-a", from_bus="s", to_bus="a", r=0.01, x=0.1, b=0)]
gens = [
    Generator(id="gs", bus="s", p_mw=0, q_mvar=0, p_min_mw=0, p_max_mw=1e6,
              q_min_mvar=-100, q_max_mvar=100, v_set_pu=1.0),
    Generator(id="gdead", bus="dead", p_mw=999, q_mvar=0, p_min_mw=0, p_max_mw=1e6,
              q_min_mvar=-100, q_max_mvar=100, v_set_pu=1.0, in_service=True),
]
loads = [Load(id="la", bus="a", p_mw=20, q_mvar=5)]

net = Network(base_mva=100, buses=buses, branches=branches, generators=gens, loads=loads)
print("Network constructed OK")

arr = NetworkArrays.from_network(net)
print("arr.bus_ids:", arr.bus_ids)
print("arr.gen_bus (positions):", arr.gen_bus if hasattr(arr, "gen_bus") else "n/a")
print("arr.p_gen_pu:", arr.p_gen_pu)

r_ac = solve_ac(net)
print("AC converged:", r_ac.converged, "gens reported:", [(g.id, g.p_mw) for g in r_ac.generators])
print("AC total gen P:", sum(g.p_mw for g in r_ac.generators), "vs total load:", 20)

r_dc = solve_dc(net)
print("DC gens reported:", [(g.id, g.p_mw) for g in r_dc.generators])
