"""Optimal power flow (epic Design §2 ``opf/``): DC-OPF with duals (W1, W2).

:func:`solve_dc_opf` is the thin ``Network``-facing wrapper around the array-level
:func:`mambo_power.opf.dc_opf.dc_opf` (mirrors :func:`mambo_power.pf.solve_dc` /
:func:`mambo_power.pf.dc.solve`): derives ``cost_coeffs`` from each generator's
:class:`~mambo_power.model.PolynomialCost`, calls ``dc_opf``, decomposes the duals into LMPs
(:func:`mambo_power.opf.dc_opf.lmp_decomposition`) and builds a typed
:class:`~mambo_power.results.OpfDcResult`.
"""

from __future__ import annotations

import time
from datetime import UTC, datetime

import numpy as np
import numpy.typing as npt

import mambo_power
from mambo_power.model import Network
from mambo_power.numerics.arrays import NetworkArrays
from mambo_power.numerics.bbus import pf_shift
from mambo_power.numerics.ptdf import ptdf as compute_ptdf
from mambo_power.opf.dc_opf import OpfDcOptions, dc_opf, lmp_decomposition
from mambo_power.pf import solve_ac
from mambo_power.results import (
    BusLmpResult,
    GenDispatchResult,
    OpfBranchFlowResult,
    OpfDcResult,
    ResultProvenance,
    feasibility_report,
)

__all__ = ["OpfDcOptions", "solve_dc_opf"]

FloatArray = npt.NDArray[np.float64]


def _cost_coeffs(net: Network, arr: NetworkArrays) -> FloatArray:
    """Per-generator ``[c2, c1, c0]``, ``NetworkArrays`` generator order, from ``Generator.cost``.

    A generator with no cost (``cost is None``) is free — an all-zero row, dispatched purely by
    the network constraints, never preferred or avoided on cost. A
    :class:`~mambo_power.model.PiecewiseCost` generator raises ``NotImplementedError``: wave M3
    slice S3 adds the convex segment/epigraph LP encoding (spec design item 4) — this slice does
    not silently misread a piecewise cost as polynomial.
    """
    gens_by_id = {g.id: g for g in net.generators}
    coeffs = np.zeros((len(arr.gen_ids), 3))
    for i, gen_id in enumerate(arr.gen_ids):
        cost = gens_by_id[gen_id].cost
        if cost is None:
            continue
        if cost.kind == "piecewise":
            raise NotImplementedError(
                f'generator "{gen_id}" has a piecewise-linear cost; opf.solve_dc_opf does not '
                "support PiecewiseCost yet (wave M3 slice S3 adds the convex segment/epigraph "
                "LP encoding — see wave-03-opf-n1.spec.md design item 4)"
            )
        values = list(cost.coefficients)
        if len(values) > 3:
            raise NotImplementedError(
                f'generator "{gen_id}" has a degree-{len(values) - 1} polynomial cost; '
                "opf.solve_dc_opf supports polynomial costs up to quadratic only"
            )
        coeffs[i, 3 - len(values) :] = values  # right-align: [c1, c0] -> [0, c1, c0], etc.
    return coeffs


def solve_dc_opf(net: Network, options: OpfDcOptions | None = None) -> OpfDcResult:
    """DC-OPF of ``net`` (module docstring): dispatch, LMPs, branch flows, shadow prices.

    Never raises for an infeasible or unbounded LP/QP — reported through
    ``OpfDcResult.status``/``message``, mirroring :func:`mambo_power.pf.solve_ac`'s
    never-raise-on-non-convergence convention. Raises ``NotImplementedError`` up front for a
    generator with a :class:`~mambo_power.model.PiecewiseCost` (see :func:`_cost_coeffs`). The
    network is not modified. ``OpfDcResult.ac_check`` stays ``None`` unless ``options.ac_check``
    is true and the LP/QP solved to ``"Optimal"``; when it fires (W6), a fresh deep copy of
    ``net`` has each in-service generator's ``p_mw`` overwritten from the dispatch (id-keyed),
    :func:`mambo_power.pf.solve_ac` re-solves that copy, and
    :func:`mambo_power.results.feasibility_report` builds the report from that solved state plus
    the copy's own declared bounds.
    """
    opts = options if options is not None else OpfDcOptions()
    started_at = datetime.now(UTC)
    clock = time.perf_counter()
    arr = NetworkArrays.from_network(net)
    cost_coeffs = _cost_coeffs(net, arr)
    solution = dc_opf(arr, cost_coeffs, opts)
    elapsed_s = time.perf_counter() - clock
    provenance = ResultProvenance(
        engine="mambo-power",
        version=mambo_power.__version__,
        kind="opf.dc",
        solver="highspy.Highs",
        started_at=started_at,
        elapsed_s=elapsed_s,
        options=opts.model_dump(),
    )
    if solution.status != "Optimal" or solution.duals is None:
        return OpfDcResult(provenance=provenance, status=solution.status, message=solution.message)

    ptdf_matrix = compute_ptdf(arr)
    lmp = lmp_decomposition(solution.duals, ptdf_matrix)

    # branch flows at the found dispatch: flow = PTDF @ (net injection) + phase-shift injection,
    # the same construction dc_opf's own flow-limit rows are built from (module docstring there).
    gen_by_bus = np.bincount(arr.gen_bus, weights=solution.dispatch_mw, minlength=arr.n_bus)
    p_load_mw = arr.p_load_pu * arr.base_mva
    g_shunt_mw = arr.g_shunt_pu * arr.base_mva
    injection_mw = gen_by_bus - p_load_mw - g_shunt_mw
    flows_mw = ptdf_matrix @ injection_mw + pf_shift(arr) * arr.base_mva

    generators = [
        GenDispatchResult(
            id=gen_id,
            bus=arr.bus_ids[int(arr.gen_bus[i])],
            p_mw=float(solution.dispatch_mw[i]),
            bound_dual=float(solution.duals.gen_bound[i]),
        )
        for i, gen_id in enumerate(arr.gen_ids)
    ]
    buses = [
        BusLmpResult(
            id=bus_id,
            lmp=float(lmp.lmp[i]),
            energy=float(lmp.energy[i]),
            congestion=float(lmp.congestion[i]),
        )
        for i, bus_id in enumerate(arr.bus_ids)
    ]
    branches = [
        OpfBranchFlowResult(
            id=br_id,
            from_bus=arr.bus_ids[int(arr.f[k])],
            to_bus=arr.bus_ids[int(arr.t[k])],
            p_from_mw=float(flows_mw[k]),
            flow_limit_dual=float(solution.duals.flow_limit[k]),
        )
        for k, br_id in enumerate(arr.branch_ids)
    ]
    ac_check = None
    if opts.ac_check:
        dispatched = net.model_copy(deep=True)
        p_mw_by_id = {row.id: row.p_mw for row in generators}
        for gen in dispatched.generators:
            if gen.id in p_mw_by_id:
                gen.p_mw = p_mw_by_id[gen.id]
        ac_check = feasibility_report(solve_ac(dispatched), dispatched)
    return OpfDcResult(
        provenance=provenance,
        status=solution.status,
        message=None,
        objective_cost=solution.objective_cost,
        balance_dual=solution.duals.balance,
        generators=generators,
        buses=buses,
        branches=branches,
        ac_check=ac_check,
    )
