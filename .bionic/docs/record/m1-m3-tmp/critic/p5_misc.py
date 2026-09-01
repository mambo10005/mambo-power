"""P5: smaller edges: v_set with multiple gens, gen-less PV/slack buses, empty cost shapes, rating 0,
base_mva inf, frozen arrays, empty network, MATPOWER v1 format."""
from mambo_power.io import matpower
from mambo_power.model import (
    Branch, Bus, Generator, Network, NetworkValidationError, PiecewiseCost, PolynomialCost,
)
from mambo_power.numerics import NetworkArrays, bbus


def g(i, bus, v, on=True):
    return Generator(id=f"g{i}", bus=bus, p_mw=0, q_mvar=0, p_min_mw=0, p_max_mw=1,
                     q_min_mvar=0, q_max_mvar=1, v_set_pu=v, in_service=on)


buses = [Bus(id="a", base_kv=110, type="slack"), Bus(id="b", base_kv=110, type="pv")]
br = [Branch(id="l", from_bus="a", to_bus="b", r=0.01, x=0.1, b=0.0)]

net = Network(base_mva=100, buses=buses, branches=br,
              generators=[g(1, "a", 1.0), g(2, "b", 1.05, on=False), g(3, "b", 1.02), g(4, "b", 1.07)])
arr = NetworkArrays.from_network(net)
print("a) v_set at pv bus, gens (OOS 1.05 | 1.02 | 1.07):", arr.v_set[1],
      "-- MATPOWER runpf: last in-service wins (1.07); pandapower from_ppc: first row (1.05)")

net = Network(base_mva=100, buses=buses, branches=br, generators=[g(1, "a", 1.0), g(2, "b", 1.05, on=False)])
arr = NetworkArrays.from_network(net)
print("b) pv bus with every gen out: bus_type =", arr.bus_type[1], "v_set =", arr.v_set[1],
      "-- MATPOWER bustypes() demotes to PQ")

net = Network(base_mva=100, buses=buses, branches=br, generators=[g(3, "b", 1.02)])
arr = NetworkArrays.from_network(net)
print("c) slack bus with no generator accepted: gen_bus =", arr.gen_bus, "slack =", arr.slack)

print("d) PolynomialCost([]) accepted:", PolynomialCost(coefficients=[]).coefficients,
      "| PiecewiseCost([]) accepted:", PiecewiseCost(points=[]).points)
pw = Network(base_mva=100, buses=buses, branches=br,
             generators=[g(1, "a", 1.0).model_copy(update={"cost": PiecewiseCost(points=[(0, 0), (10, 5), (10, 9)])})])
print("e) PWL with equal p (vertical segment) accepted:", pw.generators[0].cost.points)

net = Network(base_mva=100, buses=buses,
              branches=[Branch(id="l", from_bus="a", to_bus="b", r=0.01, x=0.1, b=0.0, rating_mva=0.0)],
              generators=[g(1, "a", 1.0)])
print("f) rating_mva=0.0 accepted -> rating_pu =", NetworkArrays.from_network(net).rating_pu,
      "(importer maps RATE_A 0 -> None = unlimited; native 0.0 means zero capacity)")

Network(base_mva=float("inf"), buses=buses, branches=br, generators=[g(1, "a", 1.0)])
print("g) base_mva=inf accepted (BAD_BASE only checks > 0)")

arr = NetworkArrays.from_network(Network(base_mva=100, buses=buses, branches=br, generators=[g(1, "a", 1.0)]))
arr.x[0] = 0.0
try:
    bbus(arr)
    print("h) frozen NetworkArrays: arr.x[0] mutated in place; bbus built")
except ValueError as e:
    print("h) frozen NetworkArrays: arr.x[0] mutated in place to 0 ->", str(e)[:60])

try:
    Network(base_mva=100)
    print("i) empty network accepted")
except NetworkValidationError as e:
    print("i) empty network ->", e.codes)

try:
    matpower.loads("function [baseMVA, bus, gen, branch] = case_v1\nbaseMVA = 100;\nbus = [\n"
                   "1 3 0 0 0 0 1 1 0 110 1 1.1 0.9;\n];\n")
except matpower.MatpowerImportError as e:
    print("j) MATPOWER v1-format file ->", e)
