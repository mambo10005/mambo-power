"""Network matrices: NetworkArrays, Ybus, PTDF and LODF on case14, then a 3-bus case in full.

What this shows:

* ``NetworkArrays.from_network`` — the positional, per-unit, in-service view that every
  matrix builder consumes (the only place positions live).
* ``ybus`` is sparse (CSC): on case14 about 25 % of the entries are non-zero, on case300
  about 1 %.
* ``ptdf`` (dense ``n_branch × n_bus``, zero slack column) and a 100 MW transfer through it.
* ``lodf`` with ``bridges``: the single bridge of case14 (branch 7-8) has a ``NaN`` column,
  because outaging a bridge islands a bus and no redistribution exists.
* A 3-bus hand example small enough to print every matrix in full.

Run from the repository root: ``uv run python examples/06_network_matrices.py``.
"""

from __future__ import annotations

import numpy as np

from mambo_power.io import matpower
from mambo_power.model import Branch, Bus, Generator, Load, Network
from mambo_power.numerics import NetworkArrays, bbus, bridges, lodf, ptdf, ybus

np.set_printoptions(precision=4, suppress=True, linewidth=100)

# --- 1. case14 -----------------------------------------------------------------------------
net = matpower.load("fixtures/matpower/case14.m")
arr = NetworkArrays.from_network(net)
print(f"case14 arrays: {arr.n_bus} buses, {arr.n_branch} branches, slack position {arr.slack}")
print(f"  p_load_pu[:4] = {arr.p_load_pu[:4]}  (MW / base_mva = {arr.base_mva})")

y = ybus(arr)
density = y.nnz / (arr.n_bus * arr.n_bus)
print(f"Ybus: {y.shape}, format {y.format}, nnz {y.nnz}, density {density:.1%}")
print(f"  diagonal of bus-1: {y[0, 0]:.4f}")

h = ptdf(arr)
print(f"PTDF: shape {h.shape}, slack column all zero: {np.allclose(h[:, arr.slack], 0.0)}")
src, dst = arr.bus_index["bus-5"], arr.bus_index["bus-14"]
flows = 100.0 * (h[:, src] - h[:, dst])  # 100 MW from bus-5 to bus-14
top = np.argsort(-np.abs(flows))[:4]
print("  100 MW bus-5 -> bus-14, largest branch flows (MW):")
for k in top:
    ends = f"{arr.bus_ids[arr.f[k]]:7s}->{arr.bus_ids[arr.t[k]]:7s}"
    print(f"    {arr.branch_ids[k]:10s} {ends} {flows[k]:8.2f}")

bridge_positions = bridges(arr)
lodf_matrix = lodf(arr, h)
print("bridges:", [(k, arr.branch_ids[k]) for k in bridge_positions], end=" ")
print([f"{arr.bus_ids[arr.f[k]]}-{arr.bus_ids[arr.t[k]]}" for k in bridge_positions])
nan_columns = [k for k in range(arr.n_branch) if np.isnan(lodf_matrix[:, k]).all()]
print(f"LODF: shape {lodf_matrix.shape}; NaN columns {nan_columns} == bridges {bridge_positions}")
print("  (outaging a bridge disconnects a bus: there is no valid redistribution to report)")
k = arr.branch_index["branch-1"]
biggest = np.argsort(-np.nan_to_num(np.abs(lodf_matrix[:, k])))[:3]
print(f"  outage of {arr.branch_ids[k]}: largest LODF entries", end=" ")
print([(arr.branch_ids[j], round(float(lodf_matrix[j, k]), 4)) for j in biggest if j != k])

# --- 2. A 3-bus network, every matrix in full ----------------------------------------------
mini = Network(
    base_mva=100,
    buses=[
        Bus(id="b1", base_kv=110, type="slack"),
        Bus(id="b2", base_kv=110, type="pv"),
        Bus(id="b3", base_kv=110, type="pq"),
    ],
    branches=[
        Branch(id="l12", from_bus="b1", to_bus="b2", r=0.01, x=0.10, b=0.02),
        Branch(id="l13", from_bus="b1", to_bus="b3", r=0.02, x=0.20, b=0.02),
        Branch(id="l23", from_bus="b2", to_bus="b3", r=0.01, x=0.10, b=0.02),
    ],
    generators=[
        Generator(
            id="g1",
            bus="b1",
            p_mw=0,
            q_mvar=0,
            p_min_mw=0,
            p_max_mw=300,
            q_min_mvar=-100,
            q_max_mvar=100,
            v_set_pu=1.02,
        ),
        Generator(
            id="g2",
            bus="b2",
            p_mw=60,
            q_mvar=0,
            p_min_mw=0,
            p_max_mw=100,
            q_min_mvar=-40,
            q_max_mvar=40,
            v_set_pu=1.01,
        ),
    ],
    loads=[Load(id="d3", bus="b3", p_mw=120, q_mvar=40)],
)
small = NetworkArrays.from_network(mini)
print("\n3-bus network, bus order", small.bus_ids, "branch order", small.branch_ids)
print("Ybus (dense):")
print(ybus(small).toarray())
print("B' (DC susceptance):")
print(bbus(small).toarray())
print("PTDF (rows = branches, columns = buses; slack column is 0):")
print(ptdf(small))
print("LODF (no bridges in a triangle, so no NaN column; diagonal -1):")
print(lodf(small))
