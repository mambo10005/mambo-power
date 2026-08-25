"""``market.nodal`` clearing (spec design item 5; wave M4 W4): the ``Scenario``-facing welfare-
maximizing DC-OPF wrapper. :func:`solve_nodal` mirrors :func:`mambo_power.opf.solve_dc_opf`
(same provenance/PTDF-reuse/id-keyed-result shape) but pulls both generator costs
(``Generator.cost``) and load bids (``Load.bid``) from ``scenario.network``, calls the extended
:func:`mambo_power.opf.dc_opf.dc_opf` with both, and decomposes the result into per-bus LMPs
(:func:`mambo_power.opf.dc_opf.lmp_decomposition`, M3's, reused verbatim per ADR-006) plus
settlement (payments, receipts, congestion rent -- the identity proved in ``record/
m4-research.md`` §4.1).
"""

from __future__ import annotations

import time
from datetime import UTC, datetime

import numpy as np
import numpy.typing as npt
from pydantic import BaseModel, ConfigDict

import mambo_power
from mambo_power.model import Network, Scenario
from mambo_power.numerics.arrays import NetworkArrays
from mambo_power.opf.dc_opf import (
    NonConcaveBidError,
    NonConvexCostError,
    OpfDcOptions,
    dc_opf,
    lmp_decomposition,
)
from mambo_power.results import (
    BusLmpResult,
    GenDispatchResult,
    LoadDispatchResult,
    MarketNodalResult,
    ResultProvenance,
)

__all__ = ["MarketNodalOptions", "NonConcaveBidError", "NonConvexCostError", "solve_nodal"]

FloatArray = npt.NDArray[np.float64]
PwlCosts = dict[int, list[tuple[float, float]]]
PolyBidCoeffs = dict[int, tuple[float, float, float]]
PwlBids = dict[int, list[tuple[float, float]]]


class MarketNodalOptions(BaseModel):
    """Options of a ``market.nodal`` clearing (wave M4 W4).

    No fields yet: mirrors :class:`~mambo_power.opf.dc_opf.OpfDcOptions`'s own precedent (a
    solver-tuning field is added the first time a caller actually needs one, not invented
    speculatively) -- present now, not omitted, so a future ``jobs`` ``KindSpec`` (S6) has a
    stable options model to validate requests against.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)


def _gen_cost_coeffs(net: Network, arr: NetworkArrays) -> tuple[FloatArray, PwlCosts]:
    """Per-generator ``[c2, c1, c0]`` plus any PWL costs, from ``Generator.cost``.

    The same extraction :func:`mambo_power.opf._cost_coeffs` performs, mirrored here rather than
    imported (that name is module-private) since ``market.nodal`` needs the identical pattern
    for the demand side too (:func:`_load_bid_coeffs`, below).
    """
    gens_by_id = {g.id: g for g in net.generators}
    coeffs = np.zeros((len(arr.gen_ids), 3))
    pwl_costs: PwlCosts = {}
    for i, gen_id in enumerate(arr.gen_ids):
        cost = gens_by_id[gen_id].cost
        if cost is None:
            continue
        if cost.kind == "piecewise":
            pwl_costs[i] = list(cost.points)
            continue
        values = list(cost.coefficients)
        if len(values) > 3:
            raise NotImplementedError(
                f'generator "{gen_id}" has a degree-{len(values) - 1} polynomial cost; '
                "market.nodal supports polynomial costs up to quadratic only"
            )
        coeffs[i, 3 - len(values) :] = values
    return coeffs, pwl_costs


def _load_bid_coeffs(net: Network, arr: NetworkArrays) -> tuple[PolyBidCoeffs, PwlBids]:
    """Per-load ``(v2, v1, v0)`` plus any PWL bids, from ``Load.bid`` -- the demand-side mirror
    of :func:`_gen_cost_coeffs`. A load with no bid (``bid is None``) contributes to neither
    mapping, so :func:`~mambo_power.opf.dc_opf.dc_opf` leaves it purely on the fixed-RHS side
    (its module docstring, "Elastic demand").
    """
    loads_by_id = {ld.id: ld for ld in net.loads}
    demand_bid_coeffs: PolyBidCoeffs = {}
    demand_pwl_bids: PwlBids = {}
    for i, load_id in enumerate(arr.load_ids):
        bid = loads_by_id[load_id].bid
        if bid is None:
            continue
        if bid.kind == "piecewise":
            demand_pwl_bids[i] = list(bid.points)
            continue
        values = list(bid.coefficients)
        if len(values) > 3:
            raise NotImplementedError(
                f'load "{load_id}" has a degree-{len(values) - 1} polynomial bid; '
                "market.nodal supports polynomial bids up to quadratic only"
            )
        row = [0.0, 0.0, 0.0]
        row[3 - len(values) :] = values
        demand_bid_coeffs[i] = (row[0], row[1], row[2])
    return demand_bid_coeffs, demand_pwl_bids


def solve_nodal(scenario: Scenario, options: MarketNodalOptions | None = None) -> MarketNodalResult:
    """Welfare-maximizing DC-OPF of ``scenario.network`` (module docstring): dispatch
    (generators and every load, bid or fixed), per-bus LMPs, and settlement.

    Never raises for an infeasible or unbounded LP/QP -- reported through
    ``MarketNodalResult.status``/``message``, mirroring :func:`mambo_power.opf.solve_dc_opf`'s
    never-raise convention. Raises :class:`~mambo_power.opf.dc_opf.NonConvexCostError` up front
    for a non-convex generator cost and :class:`~mambo_power.opf.dc_opf.NonConcaveBidError` for
    a non-concave load bid (both before any solve is attempted). The network is not modified.
    """
    opts = options if options is not None else MarketNodalOptions()
    started_at = datetime.now(UTC)
    clock = time.perf_counter()
    net = scenario.network
    arr = NetworkArrays.from_network(net)
    cost_coeffs, pwl_costs = _gen_cost_coeffs(net, arr)
    demand_bid_coeffs, demand_pwl_bids = _load_bid_coeffs(net, arr)
    solution = dc_opf(
        arr,
        cost_coeffs,
        OpfDcOptions(),
        pwl_costs=pwl_costs or None,
        demand_bid_coeffs=demand_bid_coeffs or None,
        demand_pwl_bids=demand_pwl_bids or None,
    )
    elapsed_s = time.perf_counter() - clock
    provenance = ResultProvenance(
        engine="mambo-power",
        version=mambo_power.__version__,
        kind="market.nodal",
        solver="highspy.Highs",
        started_at=started_at,
        elapsed_s=elapsed_s,
        options=opts.model_dump(),
    )
    if solution.status != "Optimal" or solution.duals is None:
        return MarketNodalResult(
            provenance=provenance, status=solution.status, message=solution.message
        )

    # solve_nodal reuses the PTDF matrix dc_opf already built (OpfSolution.ptdf docstring),
    # mirroring solve_dc_opf's own reuse (review Performance FLAG, carried forward from M3).
    ptdf_matrix = solution.ptdf
    lmp = lmp_decomposition(solution.duals, ptdf_matrix)
    lmp_by_bus_id = {bus_id: float(lmp.lmp[i]) for i, bus_id in enumerate(arr.bus_ids)}

    generators = [
        GenDispatchResult(
            id=gen_id,
            bus=arr.bus_ids[int(arr.gen_bus[i])],
            p_mw=float(solution.dispatch_mw[i]),
            bound_dual=float(solution.duals.gen_bound[i]),
        )
        for i, gen_id in enumerate(arr.gen_ids)
    ]

    # Every load gets a row (results/market.py's LoadDispatchResult docstring): a bid load's
    # dispatch/bound comes from OpfSolution.demand_dispatch_mw/demand_bound, in the same
    # load-index order dc_opf itself uses (sorted(demand_bid_coeffs.keys() |
    # demand_pwl_bids.keys())); a non-bid load stays at its own fixed Load.p_mw with
    # bound_dual 0.0 (it is not an LP column).
    elastic_idxs = sorted(set(demand_bid_coeffs) | set(demand_pwl_bids))
    elastic_pos = {idx: j for j, idx in enumerate(elastic_idxs)}
    loads_by_id = {ld.id: ld for ld in net.loads}
    loads = []
    for i, load_id in enumerate(arr.load_ids):
        bus_id = arr.bus_ids[int(arr.load_bus[i])]
        j = elastic_pos.get(i)
        if j is not None:
            p_mw = float(solution.demand_dispatch_mw[j])
            bound_dual = float(solution.demand_bound[j])
        else:
            p_mw = float(loads_by_id[load_id].p_mw)
            bound_dual = 0.0
        loads.append(LoadDispatchResult(id=load_id, bus=bus_id, p_mw=p_mw, bound_dual=bound_dual))

    buses = [
        BusLmpResult(
            id=bus_id,
            lmp=float(lmp.lmp[i]),
            energy=float(lmp.energy[i]),
            congestion=float(lmp.congestion[i]),
        )
        for i, bus_id in enumerate(arr.bus_ids)
    ]

    # Settlement (module docstring; record/m4-research.md §4.1): total_load_payment and
    # total_generator_receipts are each computed directly from dispatch and LMPs, as their own
    # independently meaningful quantities -- not asserted equal to the identity's other
    # (flow-based) side by construction. tests/unit/test_market_nodal.py's AC-4 test proves the
    # equality holds, independently.
    total_load_payment = sum(lmp_by_bus_id[row.bus] * row.p_mw for row in loads)
    total_generator_receipts = sum(lmp_by_bus_id[row.bus] * row.p_mw for row in generators)
    congestion_rent = total_load_payment - total_generator_receipts

    return MarketNodalResult(
        provenance=provenance,
        status=solution.status,
        message=None,
        generators=generators,
        loads=loads,
        buses=buses,
        total_load_payment=total_load_payment,
        total_generator_receipts=total_generator_receipts,
        congestion_rent=congestion_rent,
    )
