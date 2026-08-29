"""The per-generator, per-load and per-branch rows of one cleared market, and its settlement --
shared by :func:`mambo_power.market.nodal.solve_nodal` and
:func:`mambo_power.market.agents.solve_agents` (M7 S11, critic finding 4).

One construction, two callers. ``solve_nodal`` clears once; ``solve_agents`` clears once per round
and reports its last one. Both used to carry a character-for-character copy of this block, and
the spec's ownership table names one owner for branch flows -- the next change to the elastic
double-counting contract or the ``pf_shift`` sign would have drifted one of them. The module is
private to ``market``: the public surface is the two solvers' result models, not the rows helper.

**Branch rows** (M7 W4, AC-8). :class:`~mambo_power.opf.dc_opf.OpfSolution` carries no per-branch
flow -- only the PTDF matrix and the flow-limit duals -- so the flow is derived here as
``flow_k = PTDF[k] . (net injection) + phase-shift injection`` from the dispatch already solved
for. This is not a parallel formula: it is exactly the construction
:func:`mambo_power.opf.dc_opf.dc_opf`'s own flow-limit rows are built from (that module's
docstring), and the one :func:`mambo_power.opf.solve_dc_opf` and
:func:`mambo_power.opf.redispatch.redispatch_dc_opf` already apply at their own solved points --
no second solve, no new model field, and (``tests/unit/test_market_nodal.py``'s AC-8 tests) it
agrees with an independent :func:`mambo_power.pf.dc.solve` readback of the same dispatch. The
fixed load vector excludes each elastic load's own historical MW (``dc_opf``'s double-counting
contract) so it is not counted twice alongside the *dispatched* elastic quantity.

**Settlement.** ``total_load_payment`` and ``total_generator_receipts`` are each computed directly
from dispatch and LMPs, as their own independently meaningful quantities -- never asserted equal
to the congestion-rent identity's other (flow-based) side by construction.
``tests/unit/test_market_nodal.py``'s AC-4 test proves the equality holds, independently.
"""

from __future__ import annotations

from typing import NamedTuple

import numpy as np
import numpy.typing as npt

from mambo_power.model import Network
from mambo_power.numerics.arrays import NetworkArrays
from mambo_power.numerics.bbus import pf_shift
from mambo_power.opf.dc_opf import OpfSolution
from mambo_power.results import GenDispatchResult, LoadDispatchResult, OpfBranchFlowResult

FloatArray = npt.NDArray[np.float64]


class ClearingRows(NamedTuple):
    """One clearing's rows and settlement, as :func:`clearing_rows` returns them."""

    generators: list[GenDispatchResult]
    loads: list[LoadDispatchResult]
    branches: list[OpfBranchFlowResult]
    total_load_payment: float
    total_generator_receipts: float


def clearing_rows(
    net: Network,
    arr: NetworkArrays,
    solution: OpfSolution,
    lmp: FloatArray,
    elastic_idxs: list[int],
) -> ClearingRows:
    """The rows and settlement of one ``Optimal`` clearing (module docstring).

    ``elastic_idxs`` is the sorted list of load indices that were bid columns in the solve --
    ``sorted(set(demand_bid_coeffs) | set(demand_pwl_bids))``, the same load-index order
    ``dc_opf`` itself uses for ``demand_dispatch_mw``/``demand_bound``. Every load gets a row
    (``results/market.py``'s ``LoadDispatchResult`` docstring): a bid load's dispatch and bound
    come from the solution, a non-bid load stays at its own fixed ``Load.p_mw`` with
    ``bound_dual`` 0.0 (it is not an LP column). ``lmp`` is the per-bus LMP vector the caller
    decomposed from the same solution. Callers branch on ``solution.status`` first; this asserts
    the duals are present rather than re-checking.
    """
    assert solution.duals is not None  # callers branch on status first
    generators = [
        GenDispatchResult(
            id=gen_id,
            bus=arr.bus_ids[int(arr.gen_bus[i])],
            p_mw=float(solution.dispatch_mw[i]),
            bound_dual=float(solution.duals.gen_bound[i]),
        )
        for i, gen_id in enumerate(arr.gen_ids)
    ]
    elastic_pos = {idx: j for j, idx in enumerate(elastic_idxs)}
    loads_by_id = {load.id: load for load in net.loads}
    loads = []
    for i, load_id in enumerate(arr.load_ids):
        j = elastic_pos.get(i)
        if j is not None:
            p_mw = float(solution.demand_dispatch_mw[j])
            bound_dual = float(solution.demand_bound[j])
        else:
            p_mw = float(loads_by_id[load_id].p_mw)
            bound_dual = 0.0
        loads.append(
            LoadDispatchResult(
                id=load_id,
                bus=arr.bus_ids[int(arr.load_bus[i])],
                p_mw=p_mw,
                bound_dual=bound_dual,
            )
        )

    elastic_idx_arr = np.asarray(elastic_idxs, dtype=np.int64)
    elastic_bus = arr.load_bus[elastic_idx_arr]
    elastic_own_mw = arr.load_p_max_pu[elastic_idx_arr] * arr.base_mva
    p_load_mw = arr.p_load_pu * arr.base_mva - np.bincount(
        elastic_bus, weights=elastic_own_mw, minlength=arr.n_bus
    )
    g_shunt_mw = arr.g_shunt_pu * arr.base_mva
    gen_by_bus = np.bincount(arr.gen_bus, weights=solution.dispatch_mw, minlength=arr.n_bus)
    demand_by_bus = np.bincount(
        elastic_bus, weights=solution.demand_dispatch_mw, minlength=arr.n_bus
    )
    injection_mw = gen_by_bus - demand_by_bus - p_load_mw - g_shunt_mw
    flows_mw = solution.ptdf @ injection_mw + pf_shift(arr) * arr.base_mva
    branches = [
        OpfBranchFlowResult(
            id=branch_id,
            from_bus=arr.bus_ids[int(arr.f[k])],
            to_bus=arr.bus_ids[int(arr.t[k])],
            p_from_mw=float(flows_mw[k]),
            flow_limit_dual=float(solution.duals.flow_limit[k]),
        )
        for k, branch_id in enumerate(arr.branch_ids)
    ]

    lmp_by_bus_id = {bus_id: float(lmp[i]) for i, bus_id in enumerate(arr.bus_ids)}
    total_load_payment = sum(lmp_by_bus_id[row.bus] * row.p_mw for row in loads)
    total_generator_receipts = sum(lmp_by_bus_id[row.bus] * row.p_mw for row in generators)
    return ClearingRows(generators, loads, branches, total_load_payment, total_generator_receipts)
