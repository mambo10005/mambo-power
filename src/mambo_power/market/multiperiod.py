"""``market.multiperiod`` clearing: the ``Scenario``-facing wrapper over the multiperiod builder.

:func:`solve_multiperiod` is the exact multiperiod sibling of
:func:`mambo_power.market.nodal.solve_nodal` and sits at the same altitude: it is the
**model-side extraction and settlement layer** over
:func:`mambo_power.opf.multiperiod.multiperiod_dc_opf`, precisely as ``market.nodal`` sits over
:func:`mambo_power.opf.dc_opf.dc_opf`. Nothing numeric happens here; what happens here is turning
``Scenario`` data into the array-level builder's arguments, and turning its solution back into
id-keyed rows with a settlement attached.

**What is extracted, and from where.**

* Generator costs -- :func:`mambo_power.opf.gen_cost_coeffs`, shared verbatim with
  ``market.nodal`` (M4's Step-6 review raised a Duplication FLAG over exactly this, and M4/R2
  made the helper public so both market modules could call the one copy).
* Load bids -- :func:`mambo_power.market.nodal.load_bid_coeffs`, likewise shared rather than
  copied. Bids are horizon-invariant: per-period offers and bids are the wave's own Not-Doing
  list.
* Per-period fixed load -- each :class:`~mambo_power.model.Period`'s ``load_p_mw`` resolved into
  ``NetworkArrays.load_ids`` positions, with a load the period's dict omits falling back to its
  own ``Load.p_mw`` (``Period`` is an override, not a complete specification).
* Ramp limits -- ``Generator.ramp_up_mw``/``ramp_down_mw`` gathered into ``(n_gen,)`` arrays the
  same way ``gen_cost_coeffs`` gathers costs. ``NetworkArrays`` carries no ramp fields; the ramp
  data lives on the entity, so this is where it becomes an array.
* Per-period LMPs -- :func:`mambo_power.opf.dc_opf.lmp_decomposition` (M3's, unmodified), fed
  period ``t``'s own balance and flow-limit duals against the single PTDF matrix the builder
  already returned.

**A period-less scenario is a one-period horizon.** ``Scenario.periods is None`` means
single-period (the model's own documented meaning), so ``solve_multiperiod`` clears ``T = 1``
with ``period_load_mw=None`` -- which makes the builder's fixed-load and flow-constant
expressions *literally* ``dc_opf``'s, so the result is bit-for-bit ``market.nodal``'s (wave
AC-4). It is not an error and not a special case; it is the degenerate end of the same code path.

**Settlement.** Payments, receipts and congestion rent are computed per period, directly from
that period's LMPs and dispatch. Storage is settled as the third participant it physically is --
it pays for what it stores and is paid for what it returns -- and
:mod:`mambo_power.results.multiperiod` states the identity that makes that necessary rather than
decorative, together with the general form's ``pf_shift``/``g_shunt`` correction terms.
"""

from __future__ import annotations

import time
from datetime import UTC, datetime

import numpy as np
from pydantic import BaseModel, ConfigDict

import mambo_power
from mambo_power.model import Network, Period, Scenario
from mambo_power.numerics.arrays import NetworkArrays
from mambo_power.opf import gen_cost_coeffs
from mambo_power.opf.dc_opf import (
    FloatArray,
    NonConcaveBidError,
    NonConvexCostError,
    OpfDuals,
    lmp_decomposition,
)
from mambo_power.opf.multiperiod import MultiperiodSolution, multiperiod_dc_opf
from mambo_power.results import (
    BusLmpResult,
    GenPeriodDispatchResult,
    LoadDispatchResult,
    MarketMultiperiodResult,
    MarketPeriodResult,
    ResultProvenance,
    StorageDispatchResult,
)

from mambo_power.market.nodal import load_bid_coeffs  # isort: skip

__all__ = [
    "MarketMultiperiodOptions",
    "NonConcaveBidError",
    "NonConvexCostError",
    "solve_multiperiod",
]


class MarketMultiperiodOptions(BaseModel):
    """Options of a ``market.multiperiod`` clearing.

    No fields yet, for the same reason :class:`~mambo_power.market.nodal.MarketNodalOptions` has
    none: a solver-tuning field is added the first time a caller actually needs one. It exists
    now, rather than being omitted, because the options model is what the registered
    ``market.multiperiod`` ``jobs`` kind validates a request against -- and because the
    array-level builder
    deliberately takes no ``options`` parameter at all, so this is the one place multiperiod
    options can live.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)


def _period_load_mw(net: Network, arr: NetworkArrays, periods: list[Period]) -> FloatArray:
    """``(T, n_load)`` MW in ``NetworkArrays.load_ids`` order, resolving each period's overrides.

    A load absent from a period's ``load_p_mw`` keeps its own ``Load.p_mw`` in that period
    (:class:`~mambo_power.model.Period`'s own contract). A period may legitimately name a load
    :class:`~mambo_power.numerics.NetworkArrays` dropped -- one that is out of service, or on a
    bus that is -- and such an entry is skipped, since there is no column for it to reach.
    """
    loads_by_id = {ld.id: ld for ld in net.loads}
    position = {load_id: i for i, load_id in enumerate(arr.load_ids)}
    base = np.array([loads_by_id[load_id].p_mw for load_id in arr.load_ids], dtype=np.float64)
    out = np.tile(base, (len(periods), 1))
    for t, period in enumerate(periods):
        for load_id, p_mw in period.load_p_mw.items():
            i = position.get(load_id)
            if i is not None:
                out[t, i] = p_mw
    return out


def _ramp_limits(net: Network, arr: NetworkArrays) -> tuple[FloatArray, FloatArray]:
    """Per-generator ``(ramp_up_mw, ramp_down_mw)`` in ``NetworkArrays`` generator order, the
    demand-free mirror of :func:`~mambo_power.opf.gen_cost_coeffs`'s cost gather.

    ``None`` -- the field's default, and the honest one, since no MATPOWER fixture populates a
    ramp column -- becomes ``inf``, which the builder reads as *unconstrained* and for which it
    builds no ramp row at all.
    """
    gens_by_id = {g.id: g for g in net.generators}

    def column(attribute: str) -> FloatArray:
        values = [getattr(gens_by_id[gen_id], attribute) for gen_id in arr.gen_ids]
        return np.array([np.inf if v is None else v for v in values], dtype=np.float64)

    return column("ramp_up_mw"), column("ramp_down_mw")


def _period_rows(
    net: Network,
    arr: NetworkArrays,
    solution: MultiperiodSolution,
    t: int,
    *,
    fixed_load_mw: FloatArray | None,
    elastic_pos: dict[int, int],
) -> MarketPeriodResult:
    """Assemble period ``t``'s rows and settlement from the horizon solution."""
    duals = solution.duals
    assert duals is not None  # caller has already checked status == "Optimal"

    # M3's decomposition, unmodified, against this period's own dual slice and the single PTDF
    # matrix the builder already returned (OpfSolution.ptdf's reuse contract).
    lmp = lmp_decomposition(
        OpfDuals(
            balance=float(duals.balance[t]),
            flow_limit=duals.flow_limit[t],
            gen_bound=duals.gen_bound[t],
        ),
        solution.ptdf,
    )
    lmp_by_bus_id = {bus_id: float(lmp.lmp[i]) for i, bus_id in enumerate(arr.bus_ids)}

    generators = [
        GenPeriodDispatchResult(
            id=gen_id,
            bus=arr.bus_ids[int(arr.gen_bus[i])],
            p_mw=float(solution.dispatch_mw[t, i]),
            bound_dual=float(duals.gen_bound[t, i]),
            # duals.ramp is (T-1, n_gen): row t-1 is the row coupling t-1 to t, so period 0 has
            # no row reaching into it and reports 0.0 rather than borrowing another period's.
            ramp_dual=float(duals.ramp[t - 1, i]) if t > 0 else 0.0,
        )
        for i, gen_id in enumerate(arr.gen_ids)
    ]

    # Every load gets a row whether or not it bids (LoadDispatchResult's own docstring): the
    # settlement identity sums LMP*p_d over *every* load, and its derivation never assumes p_d
    # is a decision variable. A bid load's dispatch comes from the elastic columns; a non-bid
    # load sits at this period's own fixed demand, with no reduced cost because it is not a
    # column at all.
    loads_by_id = {ld.id: ld for ld in net.loads}
    loads = []
    for i, load_id in enumerate(arr.load_ids):
        bus_id = arr.bus_ids[int(arr.load_bus[i])]
        j = elastic_pos.get(i)
        if j is not None:
            p_mw = float(solution.demand_dispatch_mw[t, j])
            bound_dual = float(duals.demand_bound[t, j])
        elif fixed_load_mw is not None:
            p_mw = float(fixed_load_mw[t, i])
            bound_dual = 0.0
        else:
            p_mw = float(loads_by_id[load_id].p_mw)
            bound_dual = 0.0
        loads.append(LoadDispatchResult(id=load_id, bus=bus_id, p_mw=p_mw, bound_dual=bound_dual))

    storage = [
        StorageDispatchResult(
            id=storage_id,
            bus=arr.bus_ids[int(arr.storage_bus[s])],
            charge_mw=float(solution.storage_charge_mw[t, s]),
            discharge_mw=float(solution.storage_discharge_mw[t, s]),
            soc_mwh=float(solution.storage_soc_mwh[t, s]),
            soc_dual=float(duals.soc_balance[t, s]),
            energy_bound_dual=float(duals.storage_soc_bound[t, s]),
            power_limit_dual=float(duals.storage_power_limit[t, s]),
        )
        for s, storage_id in enumerate(arr.storage_ids)
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

    # Settlement: each quantity computed directly from this period's prices and quantities, as
    # its own independently meaningful figure -- none of them is asserted equal to the identity's
    # flow-dual side by construction (results/multiperiod.py's module docstring; proved per
    # period, independently, in tests/unit/test_market_multiperiod.py).
    total_load_payment = float(sum(lmp_by_bus_id[row.bus] * row.p_mw for row in loads))
    total_generator_receipts = float(sum(lmp_by_bus_id[row.bus] * row.p_mw for row in generators))
    charge_payment = float(sum(lmp_by_bus_id[row.bus] * row.charge_mw for row in storage))
    discharge_revenue = float(sum(lmp_by_bus_id[row.bus] * row.discharge_mw for row in storage))
    congestion_rent = (total_load_payment + charge_payment) - (
        total_generator_receipts + discharge_revenue
    )

    return MarketPeriodResult(
        period=t,
        generators=generators,
        loads=loads,
        buses=buses,
        storage=storage,
        total_load_payment=total_load_payment,
        total_generator_receipts=total_generator_receipts,
        total_storage_charge_payment=charge_payment,
        total_storage_discharge_revenue=discharge_revenue,
        congestion_rent=congestion_rent,
    )


def solve_multiperiod(
    scenario: Scenario, options: MarketMultiperiodOptions | None = None
) -> MarketMultiperiodResult:
    """Clear ``scenario`` over its whole horizon as one coupled LP/QP (module docstring):
    per-period dispatch, per-bus LMPs, per-storage charge/discharge/SoC, per-period settlement,
    and horizon totals.

    ``scenario.periods is None`` clears a single period from the network's own loads, reproducing
    :func:`mambo_power.market.nodal.solve_nodal` exactly (wave AC-4).

    Never raises for an infeasible or unbounded LP/QP -- reported through
    ``MarketMultiperiodResult.status``/``message``, mirroring ``solve_nodal``'s never-raise
    convention. Raises :class:`~mambo_power.opf.dc_opf.NonConvexCostError` up front for a
    non-convex generator cost, :class:`~mambo_power.opf.dc_opf.NonConcaveBidError` for a
    non-concave load bid, and :class:`ValueError` for a ramp limit of exactly zero (which would
    freeze a unit for the whole horizon) -- all before any solve is attempted. The scenario is
    not modified.
    """
    opts = options if options is not None else MarketMultiperiodOptions()
    started_at = datetime.now(UTC)
    clock = time.perf_counter()
    net = scenario.network
    arr = NetworkArrays.from_network(net)
    cost_coeffs, pwl_costs = gen_cost_coeffs(net, arr)
    demand_bid_coeffs, demand_pwl_bids = load_bid_coeffs(net, arr)
    ramp_up_mw, ramp_down_mw = _ramp_limits(net, arr)

    periods = scenario.periods
    n_periods = 1 if periods is None else len(periods)
    # None (rather than a materialised copy of the network's own loads) is deliberate: it is what
    # makes the builder evaluate dc_opf's literal fixed-load expression, hence AC-4's exactness.
    fixed_load_mw = None if periods is None else _period_load_mw(net, arr, periods)

    solution = multiperiod_dc_opf(
        arr,
        cost_coeffs,
        n_periods,
        period_load_mw=fixed_load_mw,
        ramp_up_mw=ramp_up_mw,
        ramp_down_mw=ramp_down_mw,
        pwl_costs=pwl_costs or None,
        demand_bid_coeffs=demand_bid_coeffs or None,
        demand_pwl_bids=demand_pwl_bids or None,
    )
    elapsed_s = time.perf_counter() - clock
    provenance = ResultProvenance(
        engine="mambo-power",
        version=mambo_power.__version__,
        kind="market.multiperiod",
        solver="highspy.Highs",
        started_at=started_at,
        elapsed_s=elapsed_s,
        options=opts.model_dump(),
    )
    if solution.status != "Optimal" or solution.duals is None:
        return MarketMultiperiodResult(
            provenance=provenance,
            status=solution.status,
            message=solution.message,
            n_periods=n_periods,
        )

    # The elastic-load column order is the builder's own: sorted(bid indices), exactly as
    # market.nodal reads OpfSolution.demand_dispatch_mw.
    elastic_idxs = sorted(set(demand_bid_coeffs) | set(demand_pwl_bids))
    elastic_pos = {idx: j for j, idx in enumerate(elastic_idxs)}
    period_results = [
        _period_rows(net, arr, solution, t, fixed_load_mw=fixed_load_mw, elastic_pos=elastic_pos)
        for t in range(n_periods)
    ]

    def horizon(field: str) -> float:
        return float(sum(getattr(p, field) for p in period_results))

    return MarketMultiperiodResult(
        provenance=provenance,
        status=solution.status,
        message=None,
        n_periods=n_periods,
        periods=period_results,
        objective_cost=solution.objective_cost,
        total_load_payment=horizon("total_load_payment"),
        total_generator_receipts=horizon("total_generator_receipts"),
        total_storage_charge_payment=horizon("total_storage_charge_payment"),
        total_storage_discharge_revenue=horizon("total_storage_discharge_revenue"),
        congestion_rent=horizon("congestion_rent"),
    )
