"""``market.nodal`` clearing: the ``Scenario``-facing welfare-maximizing DC-OPF wrapper.
:func:`solve_nodal` mirrors :func:`mambo_power.opf.solve_dc_opf` (same provenance/PTDF-reuse/
id-keyed-result shape) but pulls both generator costs (``Generator.cost``) and load bids
(``Load.bid``) from ``scenario.network``, calls the extended
:func:`mambo_power.opf.dc_opf.dc_opf` with both, and decomposes the result into per-bus LMPs
(:func:`mambo_power.opf.dc_opf.lmp_decomposition`, M3's, reused verbatim per ADR-006) plus
settlement (payments, receipts, congestion rent): total load payment minus total generator
receipts equals the congestion rent, i.e. ``-sum(mu_k * flow_k)`` over the binding branches
(see the wave spec's AC-4 for the exact identity and its proof).

**Branch rows (M7 W4, AC-8).** ``dc_opf``'s own :class:`~mambo_power.opf.dc_opf.OpfSolution`
carries no per-branch flow -- only the PTDF matrix and the flow-limit duals -- so the flow
``flow_k = PTDF[k] . (net injection) + phase-shift injection`` is derived from the dispatch already
solved for, in :func:`mambo_power.market._clearing.clearing_rows`: one construction, shared with
:func:`mambo_power.market.agents.solve_agents` (M7 S11), and not a parallel formula -- see that
module's docstring for the derivation and the AC-8 readback that checks it.
"""

from __future__ import annotations

import time
from datetime import UTC, datetime

from pydantic import BaseModel, ConfigDict

import mambo_power
from mambo_power.market._clearing import clearing_rows
from mambo_power.model import Network, Scenario
from mambo_power.numerics.arrays import NetworkArrays
from mambo_power.opf import gen_cost_coeffs
from mambo_power.opf.dc_opf import (
    NonConcaveBidError,
    NonConvexCostError,
    OpfDcOptions,
    dc_opf,
    lmp_decomposition,
)
from mambo_power.results import BusLmpResult, MarketNodalResult, ResultProvenance

__all__ = [
    "MarketNodalOptions",
    "NonConcaveBidError",
    "NonConvexCostError",
    "load_bid_coeffs",
    "solve_nodal",
]

PolyBidCoeffs = dict[int, tuple[float, float, float]]
PwlBids = dict[int, list[tuple[float, float]]]


class MarketNodalOptions(BaseModel):
    """Options of a ``market.nodal`` clearing.

    No fields yet: mirrors :class:`~mambo_power.opf.dc_opf.OpfDcOptions`'s own precedent (a
    solver-tuning field is added the first time a caller actually needs one, not invented
    speculatively). It exists rather than being omitted because the ``market.nodal``
    :class:`~mambo_power.jobs.KindSpec` names it as the model every request's ``options`` is
    validated against, and a kind with no options model rejects any key at all.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)


def load_bid_coeffs(net: Network, arr: NetworkArrays) -> tuple[PolyBidCoeffs, PwlBids]:
    """Per-load ``(v2, v1, v0)`` plus any PWL bids, from ``Load.bid`` -- the demand-side mirror
    of :func:`mambo_power.opf.gen_cost_coeffs`. A load with no bid (``bid is None``) contributes
    to neither mapping, so :func:`~mambo_power.opf.dc_opf.dc_opf` leaves it purely on the
    fixed-RHS side (its module docstring, "Elastic demand").

    Public (not module-private) for the same reason
    :func:`~mambo_power.opf.gen_cost_coeffs` is:
    :func:`mambo_power.market.multiperiod.solve_multiperiod` needs the identical bid extraction
    and calls this rather than carrying a second copy (M4 review Duplication FLAG, M4/R2's own
    resolution applied to the demand side).
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
    cost_coeffs, pwl_costs = gen_cost_coeffs(net, arr)
    demand_bid_coeffs, demand_pwl_bids = load_bid_coeffs(net, arr)
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
    # Every load gets a row, and the branch rows and settlement are the one construction shared
    # with market.agents (market/_clearing.py, whose docstring carries the AC-8 derivation and
    # the settlement note this block used to carry). The elastic load indices are handed over in
    # the same load-index order dc_opf itself uses (sorted(demand_bid_coeffs.keys() |
    # demand_pwl_bids.keys())).
    elastic_idxs = sorted(set(demand_bid_coeffs) | set(demand_pwl_bids))
    rows = clearing_rows(net, arr, solution, lmp.lmp, elastic_idxs)
    generators, loads, branches = rows.generators, rows.loads, rows.branches
    total_load_payment, total_generator_receipts = (
        rows.total_load_payment,
        rows.total_generator_receipts,
    )
    congestion_rent = total_load_payment - total_generator_receipts

    buses = [
        BusLmpResult(
            id=bus_id,
            lmp=float(lmp.lmp[i]),
            energy=float(lmp.energy[i]),
            congestion=float(lmp.congestion[i]),
        )
        for i, bus_id in enumerate(arr.bus_ids)
    ]

    return MarketNodalResult(
        provenance=provenance,
        status=solution.status,
        message=None,
        generators=generators,
        loads=loads,
        buses=buses,
        branches=branches,
        total_load_payment=total_load_payment,
        total_generator_receipts=total_generator_receipts,
        congestion_rent=congestion_rent,
    )
