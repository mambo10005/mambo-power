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

**Unit commitment (ADR-017).** With ``MarketMultiperiodOptions.unit_commitment`` the builder is
handed a :class:`~mambo_power.opf.multiperiod.Commitment` block gathered here the way ramps are:
start-up and shut-down costs from each generator's :class:`~mambo_power.model.GeneratorCost`
(``startup``/``shutdown``, defaults 0), the status before the horizon from the unit's declared
``p_mw`` — a unit dispatched above zero in the network's own state is on, one at zero is off —
and a polynomial cost's constant term ``c0`` as the unit's **no-load** cost, paid only while on
(the LP charges it in every period unconditionally, which is the right reading when nothing can
be switched off). HiGHS solves MILPs, not MIQPs, so a quadratic cost is **linearised** here into
``quadratic_segments`` equal-width convex chords between 0 and ``p_max`` and passed as a
piecewise-linear cost; the reported ``objective_cost`` is the chord cost, a slight over-estimate
of the quadratic one. The clearing becomes a MIP; the prices and settlement below are those of
the LP left once the commitment is fixed at the optimum (the builder's own two-pass rule), and
the result carries each unit's schedule in ``MarketMultiperiodResult.commitment``. Minimum up
and down times (ADR-019) come off ``Generator.min_up_periods`` / ``min_down_periods``, and the
obligation a unit brings into the horizon off ``initial_state_periods``: a unit that states no
history is taken to have been in its state long enough that none carries in. Hot and warm
start-up tiers (ADR-026) come off ``startup_hot_cost`` / ``startup_hot_periods`` and
``startup_warm_cost`` / ``startup_warm_periods``, the cold cost staying ``cost.startup``.

**Spinning reserve (ADR-023).** A ``Period.reserve_mw`` is handed to the builder as that
period's requirement (a period that states none requires 0 once any period does), each unit's
``Generator.reserve_max_mw`` as its cap; the result carries each unit's ``reserve_mw``, each
period's ``reserve_price`` (the requirement row's dual) and ``total_reserve_payment``, which is
settled outside the energy identity below.

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
from pydantic import BaseModel, ConfigDict, Field

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
from mambo_power.opf.multiperiod import (
    Commitment,
    IntArray,
    MultiperiodSolution,
    multiperiod_dc_opf,
)
from mambo_power.results import (
    BusLmpResult,
    GenCommitmentResult,
    GenPeriodDispatchResult,
    LoadDispatchResult,
    MarketMultiperiodResult,
    MarketPeriodResult,
    ResultProvenance,
    StorageDispatchResult,
)

from mambo_power.market.nodal import load_bid_coeffs  # isort: skip

_NO_HISTORY = 10**9
"""``initial_state_periods`` for a unit that states none: longer than any minimum, so no
obligation carries into the horizon."""

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

    unit_commitment: bool = Field(
        default=False,
        description="Clear with per-unit on/off decisions (ADR-017): start-up and shut-down "
        "costs, no-load costs only while on, minimum output only while on; prices from the LP "
        "with the commitment fixed.",
    )
    quadratic_segments: int = Field(
        default=8,
        ge=1,
        description="With unit_commitment, the number of equal-width chords a quadratic "
        "generator cost is linearised into between 0 and p_max (HiGHS has no MIQP).",
    )


def _commitment(
    net: Network,
    arr: NetworkArrays,
    cost_coeffs: FloatArray,
    pwl_costs: dict[int, list[tuple[float, float]]],
    segments: int,
) -> tuple[Commitment, FloatArray, dict[int, list[tuple[float, float]]]]:
    """The :class:`~mambo_power.opf.multiperiod.Commitment` block of ``net`` (module docstring,
    "Unit commitment") plus the cost arguments rewritten for it: ``c0`` moved into the block as
    the no-load cost, and every quadratic cost linearised into ``segments`` chords of
    ``c2·p² + c1·p`` between 0 and ``p_max`` and moved into the piecewise map. Returns
    ``(commitment, cost_coeffs, pwl_costs)``; the inputs are not modified.
    """
    gens_by_id = {g.id: g for g in net.generators}
    n_gen = len(arr.gen_ids)
    startup = np.zeros(n_gen)
    shutdown = np.zeros(n_gen)
    initial_on = np.zeros(n_gen, dtype=np.bool_)
    coeffs = np.array(cost_coeffs, dtype=np.float64, copy=True)
    pwl = {i: list(points) for i, points in pwl_costs.items()}
    no_load = coeffs[:, 2].copy()
    coeffs[:, 2] = 0.0
    p_max = arr.gen_p_max_pu * arr.base_mva
    for i, gen_id in enumerate(arr.gen_ids):
        gen = gens_by_id[gen_id]
        if gen.cost is not None:
            startup[i] = gen.cost.startup
            shutdown[i] = gen.cost.shutdown
        initial_on[i] = gen.p_mw > 0.0
        c2, c1 = float(coeffs[i, 0]), float(coeffs[i, 1])
        if c2 != 0.0:
            grid = np.linspace(0.0, max(float(p_max[i]), 0.0), segments + 1)
            pwl[i] = [(float(p), float(c2 * p * p + c1 * p)) for p in grid]
            coeffs[i, :2] = 0.0
    gens = [gens_by_id[gen_id] for gen_id in arr.gen_ids]
    initial_periods = [g.initial_state_periods for g in gens]
    commitment = Commitment(
        startup_cost=startup,
        shutdown_cost=shutdown,
        initial_on=initial_on,
        no_load_cost=no_load,
        startup_tiers=[
            [
                (periods, cost)
                for cost, periods in (
                    (g.startup_hot_cost, g.startup_hot_periods),
                    (g.startup_warm_cost, g.startup_warm_periods),
                )
                if cost is not None and periods is not None
            ]
            for g in gens
        ],
        min_up_periods=np.array([g.min_up_periods or 1 for g in gens], dtype=np.int64),
        min_down_periods=np.array([g.min_down_periods or 1 for g in gens], dtype=np.int64),
        # a unit that states no history carries no obligation in: "long enough" is the horizon
        initial_state_periods=np.array(
            [k if k is not None else _NO_HISTORY for k in initial_periods], dtype=np.int64
        ),
    )
    return commitment, coeffs, pwl


def _period_count(values: IntArray | None, i: int) -> int:
    return 1 if values is None else int(values[i])


def _commitment_rows(
    arr: NetworkArrays, solution: MultiperiodSolution, commitment: Commitment
) -> list[GenCommitmentResult]:
    """One :class:`~mambo_power.results.GenCommitmentResult` per generator."""
    rows = []
    for i, gen_id in enumerate(arr.gen_ids):
        on = solution.committed[:, i]
        started = solution.started[:, i]
        stopped = solution.stopped[:, i]
        rows.append(
            GenCommitmentResult(
                id=gen_id,
                committable=bool(
                    arr.gen_p_min_pu[i] > 0.0
                    or commitment.no_load_cost[i] > 0.0
                    or commitment.startup_cost[i] > 0.0
                    or commitment.shutdown_cost[i] > 0.0
                ),
                initial_on=bool(commitment.initial_on[i]),
                min_up_periods=_period_count(commitment.min_up_periods, i),
                min_down_periods=_period_count(commitment.min_down_periods, i),
                on=[bool(x) for x in on],
                started=[bool(x) for x in started],
                stopped=[bool(x) for x in stopped],
                startup_cost=float(np.sum(solution.startup_cost_paid[:, i])),
                startup_costs=[float(x) for x in solution.startup_cost_paid[:, i]],
                shutdown_cost=float(commitment.shutdown_cost[i] * np.sum(stopped)),
                no_load_cost=float(commitment.no_load_cost[i] * np.sum(on)),
            )
        )
    return rows


def _reserve(
    net: Network, arr: NetworkArrays, periods: list[Period] | None
) -> tuple[FloatArray | None, FloatArray | None]:
    """``(reserve_mw, reserve_max_mw)`` for the builder (ADR-023): the per-period requirement
    (a period that states none requires 0) and each unit's cap in ``arr`` order (``None`` →
    uncapped). ``(None, None)`` when no period states a requirement, so the LP is untouched."""
    if periods is None or all(p.reserve_mw is None for p in periods):
        return None, None
    gens_by_id = {g.id: g for g in net.generators}
    requirement = np.array([0.0 if p.reserve_mw is None else p.reserve_mw for p in periods])
    caps = np.array(
        [
            np.inf if gens_by_id[g].reserve_max_mw is None else gens_by_id[g].reserve_max_mw
            for g in arr.gen_ids
        ],
        dtype=np.float64,
    )
    return requirement, caps


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
    reserve_requirement: float = 0.0,
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
            committed=bool(solution.committed[t, i]) if solution.committed.size else True,
            reserve_mw=float(solution.reserve_mw[t, i]) if solution.reserve_mw.size else 0.0,
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
    reserve_price = float(duals.reserve[t]) if duals.reserve.size else 0.0
    reserve_held = float(sum(row.reserve_mw for row in generators))

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
        reserve_requirement_mw=reserve_requirement,
        reserve_price=reserve_price,
        total_reserve_payment=reserve_price * reserve_held,
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
    commitment = None
    if opts.unit_commitment:
        commitment, cost_coeffs, pwl_costs = _commitment(
            net, arr, cost_coeffs, pwl_costs, opts.quadratic_segments
        )

    reserve_mw, reserve_max_mw = _reserve(net, arr, periods)

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
        commitment=commitment,
        reserve_mw=reserve_mw,
        reserve_max_mw=reserve_max_mw,
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
        _period_rows(
            net,
            arr,
            solution,
            t,
            fixed_load_mw=fixed_load_mw,
            elastic_pos=elastic_pos,
            reserve_requirement=0.0 if reserve_mw is None else float(reserve_mw[t]),
        )
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
        total_reserve_payment=horizon("total_reserve_payment"),
        commitment=_commitment_rows(arr, solution, commitment) if commitment is not None else [],
        commitment_cost=solution.commitment_cost,
        no_load_cost=solution.no_load_cost,
    )
