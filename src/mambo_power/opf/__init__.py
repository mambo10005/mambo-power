"""Optimal power flow (epic Design §2 ``opf/``): DC-OPF with duals (W1, W2).

:func:`solve_dc_opf` is the thin ``Network``-facing wrapper around the array-level
:func:`mambo_power.opf.dc_opf.dc_opf` (mirrors :func:`mambo_power.pf.solve_dc` /
:func:`mambo_power.pf.dc.solve`): derives ``cost_coeffs``/``pwl_costs`` from each generator's
:class:`~mambo_power.model.PolynomialCost` or :class:`~mambo_power.model.PiecewiseCost` (raising
:class:`~mambo_power.opf.dc_opf.NonConvexCostError` up front for a non-convex piecewise cost,
spec design item 4 — re-exported here as :data:`NonConvexCostError`), calls ``dc_opf``,
decomposes the duals into LMPs (:func:`mambo_power.opf.dc_opf.lmp_decomposition`) and builds a
typed :class:`~mambo_power.results.OpfDcResult`.

:func:`~mambo_power.opf.multiperiod.multiperiod_dc_opf` (wave M5 W2) and its two result types are
re-exported here alongside them: it is the ``T``-coupled-period sibling of ``dc_opf``, built from
the same row-family core (ADR-007), and ``market.multiperiod`` imports it from this package the
way ``market.nodal`` imports :func:`gen_cost_coeffs`. There is no ``solve_multiperiod`` wrapper in
``opf`` — the ``Scenario``-facing entry point lives in ``market/`` because a horizon needs
``Scenario.periods``, which a bare ``Network`` cannot supply.
"""

from __future__ import annotations

import time
from collections.abc import Mapping
from datetime import UTC, datetime

import numpy as np
import numpy.typing as npt

import mambo_power
from mambo_power.model import GeneratorCost, Network
from mambo_power.numerics.arrays import NetworkArrays
from mambo_power.numerics.bbus import pf_shift
from mambo_power.opf.dc_opf import NonConvexCostError, OpfDcOptions, dc_opf, lmp_decomposition
from mambo_power.opf.multiperiod import (
    MultiperiodDuals,
    MultiperiodSolution,
    multiperiod_dc_opf,
)
from mambo_power.opf.redispatch import RedispatchSolution, redispatch_dc_opf
from mambo_power.opf.zonal import ZonalDuals, ZonalSolution, zonal_dc_opf
from mambo_power.pf import solve_ac
from mambo_power.results import (
    BusLmpResult,
    GenDispatchResult,
    OpfBranchFlowResult,
    OpfDcResult,
    ResultProvenance,
    feasibility_report,
)

__all__ = [
    "MultiperiodDuals",
    "MultiperiodSolution",
    "NonConvexCostError",
    "OpfDcOptions",
    "RedispatchSolution",
    "ZonalDuals",
    "ZonalSolution",
    "gen_cost_coeffs",
    "multiperiod_dc_opf",
    "redispatch_dc_opf",
    "solve_dc_opf",
    "zonal_dc_opf",
]

FloatArray = npt.NDArray[np.float64]
PwlCosts = dict[int, list[tuple[float, float]]]


def gen_cost_coeffs(
    net: Network,
    arr: NetworkArrays,
    *,
    costs: Mapping[str, GeneratorCost] | None = None,
) -> tuple[FloatArray, PwlCosts]:
    """Per-generator ``[c2, c1, c0]`` (``NetworkArrays`` generator order) plus any PWL costs,
    from ``Generator.cost`` or from an explicit *costs* source.

    Returns ``(coeffs, pwl_costs)``: ``coeffs`` is ``(n_gen, 3)``; a generator with no cost
    (``cost is None``) or a :class:`~mambo_power.model.PiecewiseCost` gets an all-zero row — free
    in the first case, and in the second because its cost is captured entirely by the epigraph
    rows :func:`~mambo_power.opf.dc_opf.dc_opf` builds from ``pwl_costs`` instead (spec design
    item 4). ``pwl_costs`` maps generator index to that generator's raw
    ``PiecewiseCost.points``; :func:`dc_opf` raises ``NonConvexCostError`` (re-exported as
    :data:`NonConvexCostError` on this module) if any entry's breakpoint slopes are not
    non-decreasing, before any solve is attempted.

    **The cost source** (M7 W3, spec A2). ``costs`` maps a generator id to the
    :class:`~mambo_power.model.GeneratorCost` to use *in place of* that generator's own
    ``Generator.cost``; a generator absent from the mapping keeps its own cost, and ``costs=None``
    — every pre-M7 call site — is exactly "every generator keeps its own". This is what makes a
    strategic **offer** overlay and the true-cost extraction one function under two arguments
    rather than two implementations of one mapping:
    :func:`mambo_power.market.agents.solve_agents` passes each round's offer map here instead of
    assembling ``(cost_coeffs, pwl_costs)`` itself, so the all-zero-row convention above — and
    :func:`~mambo_power.opf.dc_opf.dc_opf`'s generator-side overlap guard, which exists precisely
    because a hand-rolled assembler can break that convention — hold identically for an offer and
    for a true cost. The network is never touched: an offer is a *choice of coefficients*, not a
    mutation of ``Generator.cost`` (AC-2).

    Raises ``ValueError`` if ``costs`` names a generator id that is not in ``net``, or one that is
    in ``net`` but absent from ``arr`` (out of service, or on a bus that is). In both cases the
    entry would otherwise be silently ignored, and a cost source that quietly does nothing is
    exactly the plausible-wrong-answer class this repo keeps finding.

    Exported (not module-private) because :func:`mambo_power.market.nodal.solve_nodal` needs the
    identical generator-cost extraction and imports this rather than carrying its own copy
    (M4 review Duplication FLAG) — the demand-bid-side mirror
    (:func:`mambo_power.market.nodal.load_bid_coeffs`) has no prior-wave analog to share.
    """
    gens_by_id = {g.id: g for g in net.generators}
    if costs:
        in_arrays = set(arr.gen_ids)
        for gen_id in costs:
            if gen_id not in gens_by_id:
                raise ValueError(
                    f'costs names generator "{gen_id}", which is not in the network -- its entry '
                    f"would be silently ignored"
                )
            if gen_id not in in_arrays:
                raise ValueError(
                    f'costs names generator "{gen_id}", which is in the network but not in its '
                    f"arrays (out of service, or on a bus that is) -- its entry would be silently "
                    f"ignored"
                )
    coeffs = np.zeros((len(arr.gen_ids), 3))
    pwl_costs: PwlCosts = {}
    for i, gen_id in enumerate(arr.gen_ids):
        cost = costs.get(gen_id, gens_by_id[gen_id].cost) if costs else gens_by_id[gen_id].cost
        if cost is None:
            continue
        if cost.kind == "piecewise":
            pwl_costs[i] = list(cost.points)
            continue
        values = list(cost.coefficients)
        if len(values) > 3:
            raise NotImplementedError(
                f'generator "{gen_id}" has a degree-{len(values) - 1} polynomial cost; '
                "opf.solve_dc_opf supports polynomial costs up to quadratic only"
            )
        coeffs[i, 3 - len(values) :] = values  # right-align: [c1, c0] -> [0, c1, c0], etc.
    return coeffs, pwl_costs


def solve_dc_opf(net: Network, options: OpfDcOptions | None = None) -> OpfDcResult:
    """DC-OPF of ``net`` (module docstring): dispatch, LMPs, branch flows, shadow prices.

    Never raises for an infeasible or unbounded LP/QP — reported through
    ``OpfDcResult.status``/``message``, mirroring :func:`mambo_power.pf.solve_ac`'s
    never-raise-on-non-convergence convention. Raises :class:`NonConvexCostError` up front for a
    generator whose :class:`~mambo_power.model.PiecewiseCost` is not convex (see
    :func:`_cost_coeffs`). The network is not modified. ``OpfDcResult.ac_check`` stays ``None``
    unless ``options.ac_check`` is true and the LP/QP solved to ``"Optimal"``; when it fires
    (W6), a fresh deep copy of
    ``net`` has each in-service generator's ``p_mw`` overwritten from the dispatch (id-keyed),
    :func:`mambo_power.pf.solve_ac` re-solves that copy, and
    :func:`mambo_power.results.feasibility_report` builds the report from that solved state plus
    the copy's own declared bounds.
    """
    opts = options if options is not None else OpfDcOptions()
    started_at = datetime.now(UTC)
    clock = time.perf_counter()
    arr = NetworkArrays.from_network(net)
    cost_coeffs, pwl_costs = gen_cost_coeffs(net, arr)
    solution = dc_opf(arr, cost_coeffs, opts, pwl_costs=pwl_costs or None)
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

    # solve_dc_opf reuses the PTDF matrix dc_opf already built (OpfSolution.ptdf docstring)
    # instead of recomputing it — review Performance FLAG, ~62% of a warm solve_dc_opf call.
    ptdf_matrix = solution.ptdf
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
