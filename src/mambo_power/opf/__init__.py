"""Optimal power flow (epic Design §2 ``opf/``): DC-OPF with duals (W1, W2).

:func:`solve_dc_opf` is the thin ``Network``-facing wrapper around the array-level
:func:`mambo_power.opf.dc_opf.dc_opf` (mirrors :func:`mambo_power.pf.solve_dc` /
:func:`mambo_power.pf.dc.solve`): derives ``cost_coeffs``/``pwl_costs`` from each generator's
:class:`~mambo_power.model.PolynomialCost` or :class:`~mambo_power.model.PiecewiseCost` (raising
:class:`~mambo_power.opf.dc_opf.NonConvexCostError` up front for a non-convex piecewise cost,
spec design item 4, and :class:`~mambo_power.opf.dc_opf.MissingCostError` for a generator with
no cost — both re-exported here), calls ``dc_opf``,
decomposes the duals into LMPs (:func:`mambo_power.opf.dc_opf.lmp_decomposition`) and builds a
typed :class:`~mambo_power.results.OpfDcResult`.

:func:`~mambo_power.opf.multiperiod.multiperiod_dc_opf` (wave M5 W2) and its two result types are
re-exported here alongside them: it is the ``T``-coupled-period sibling of ``dc_opf``, built from
the same row-family core (ADR-007), and ``market.multiperiod`` imports it from this package the
way ``market.nodal`` imports :func:`gen_cost_coeffs`. There is no ``solve_multiperiod`` wrapper in
``opf`` — the ``Scenario``-facing entry point lives in ``market/`` because a horizon needs
``Scenario.periods``, which a bare ``Network`` cannot supply.

:func:`solve_ac_opf` (ADR-018) is the AC sibling of :func:`solve_dc_opf`: the same wrapper
shape around :func:`mambo_power.opf.ac_opf.ac_opf`, the trust-region sequential-LP AC optimal
power flow, with reactive dispatch, voltages, apparent-power limits and AC LMPs.

:func:`solve_scopf` (ADR-016) is the security-constrained sibling of :func:`solve_dc_opf`: the
same wrapper shape around :func:`mambo_power.opf.scopf.scopf_dc`, which generates
post-contingency flow rows from :mod:`mambo_power.contingency`'s N-1 screen until the dispatch
survives every single branch or generator outage, then confirms that dispatch with the real
:func:`mambo_power.contingency.n1`.
"""

from __future__ import annotations

import time
from collections.abc import Mapping
from datetime import UTC, datetime

import numpy as np
import numpy.typing as npt

import mambo_power
from mambo_power.contingency import N1Options, n1, n2
from mambo_power.model import GeneratorCost, Network
from mambo_power.numerics.arrays import NetworkArrays
from mambo_power.numerics.bbus import flow_from_ptdf
from mambo_power.opf.ac_opf import SOLVER as AC_OPF_SOLVER
from mambo_power.opf.ac_opf import AcOpfSolution, OpfAcOptions, ac_opf
from mambo_power.opf.dc_opf import (
    MissingCostError,
    NonConvexCostError,
    OpfDcOptions,
    dc_opf,
    lmp_decomposition,
)
from mambo_power.opf.multiperiod import (
    MultiperiodDuals,
    MultiperiodSolution,
    multiperiod_dc_opf,
)
from mambo_power.opf.redispatch import RedispatchSolution, redispatch_dc_opf
from mambo_power.opf.scopf import ScopfOptions, ScopfSolution, scopf_dc
from mambo_power.opf.zonal import ZonalDuals, ZonalSolution, zonal_dc_opf
from mambo_power.pf import dc as pfdc
from mambo_power.pf import solve_ac
from mambo_power.results import (
    AcBranchFlowResult,
    AcBusResult,
    AcGenDispatchResult,
    AcLoadDispatchResult,
    BusLmpResult,
    CorrectiveActionResult,
    GenCorrectionResult,
    GenDispatchResult,
    OpfAcResult,
    OpfBranchFlowResult,
    OpfDcResult,
    ResultProvenance,
    ScopfDcResult,
    SecurityConstraintResult,
    feasibility_report,
)

__all__ = [
    "AcOpfSolution",
    "MissingCostError",
    "MultiperiodDuals",
    "MultiperiodSolution",
    "NonConvexCostError",
    "OpfAcOptions",
    "OpfDcOptions",
    "RedispatchSolution",
    "ScopfOptions",
    "ScopfSolution",
    "ZonalDuals",
    "ZonalSolution",
    "ac_opf",
    "gen_cost_coeffs",
    "multiperiod_dc_opf",
    "redispatch_dc_opf",
    "scopf_dc",
    "solve_ac_opf",
    "solve_dc_opf",
    "solve_scopf",
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

    Returns ``(coeffs, pwl_costs)``: ``coeffs`` is ``(n_gen, 3)``; a generator with a
    :class:`~mambo_power.model.PiecewiseCost` gets an all-zero row because its cost is captured
    entirely by the epigraph rows :func:`~mambo_power.opf.dc_opf.dc_opf` builds from
    ``pwl_costs`` instead (spec design item 4). A generator with **no** cost (``cost is None``
    after the *costs* overlay below) raises :class:`~mambo_power.opf.dc_opf.MissingCostError`
    (re-exported here as :data:`MissingCostError`) naming every such generator, before any
    solve: it used to get an all-zero row too — "free" — which let a network with no economic
    data at all (every RAW import) clear an OPF at zero cost with all load on one unit (M8 walk,
    surprise 3). ``pwl_costs`` maps generator index to that generator's raw
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
    missing = [
        gen_id
        for gen_id in arr.gen_ids
        if (costs.get(gen_id, gens_by_id[gen_id].cost) if costs else gens_by_id[gen_id].cost)
        is None
    ]
    if missing:
        raise MissingCostError(missing)
    for i, gen_id in enumerate(arr.gen_ids):
        cost = costs.get(gen_id, gens_by_id[gen_id].cost) if costs else gens_by_id[gen_id].cost
        assert cost is not None  # the MissingCostError check above
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
    generator whose :class:`~mambo_power.model.PiecewiseCost` is not convex, and
    :class:`MissingCostError` for one with no cost at all (see :func:`gen_cost_coeffs`). The
    network is not modified. ``OpfDcResult.ac_check`` stays ``None``
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

    # branch flows at the found dispatch: flow_from_ptdf(ptdf, injection, arr) — the same
    # PTDF-minus-shift identity dc_opf's own flow-limit rows are built from by hand (module
    # docstring there) and pf.solve_dc solves for directly (numerics.bbus.flow_from_ptdf).
    gen_by_bus = np.bincount(arr.gen_bus, weights=solution.dispatch_mw, minlength=arr.n_bus)
    p_load_mw = arr.p_load_pu * arr.base_mva
    g_shunt_mw = arr.g_shunt_pu * arr.base_mva
    injection_mw = gen_by_bus - p_load_mw - g_shunt_mw
    flows_mw = flow_from_ptdf(ptdf_matrix, injection_mw, arr)

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


def _dispatched_copy(net: Network, arr: NetworkArrays, dispatch_mw: FloatArray) -> Network:
    """A deep copy of *net* with each in-service generator's ``p_mw`` set from *dispatch_mw*."""
    dispatched = net.model_copy(deep=True)
    p_mw_by_id = dict(zip(arr.gen_ids, dispatch_mw.tolist(), strict=True))
    for gen in dispatched.generators:
        if gen.id in p_mw_by_id:
            gen.p_mw = p_mw_by_id[gen.id]
    return dispatched


def solve_scopf(net: Network, options: ScopfOptions | None = None) -> ScopfDcResult:
    """Security-constrained DC-OPF of ``net`` (ADR-016): the cheapest dispatch no single branch
    or generator outage can overload, with LMPs, base-case flows, the post-contingency rows
    that had to be added, and the confirming :func:`mambo_power.contingency.n1` of the result.

    The same never-raise convention as :func:`solve_dc_opf`: an infeasible LP — no preventive
    dispatch survives every contingency at these ratings — is reported through
    ``ScopfDcResult.status``/``message``; so is :data:`mambo_power.opf.scopf.ITERATION_LIMIT`.
    Raises :class:`NonConvexCostError` and :class:`MissingCostError` up front like
    :func:`solve_dc_opf`. The network is not modified: the confirming N-1 run and the optional
    ``ac_check`` both work on a deep copy carrying the secure dispatch.
    """
    opts = options if options is not None else ScopfOptions()
    started_at = datetime.now(UTC)
    clock = time.perf_counter()
    arr = NetworkArrays.from_network(net)
    cost_coeffs, pwl_costs = gen_cost_coeffs(net, arr)
    ramp_up, ramp_down = _corrective_ramps(net, arr)
    secured = scopf_dc(
        arr,
        cost_coeffs,
        opts,
        pwl_costs=pwl_costs or None,
        ramp_up_mw=ramp_up,
        ramp_down_mw=ramp_down,
    )
    solution = secured.solution

    def provenance() -> ResultProvenance:
        return ResultProvenance(
            engine="mambo-power",
            version=mambo_power.__version__,
            kind="opf.scopf",
            solver="highspy.Highs",
            started_at=started_at,
            elapsed_s=time.perf_counter() - clock,
            options=opts.model_dump(),
        )

    if secured.status != "Optimal" or solution.duals is None:
        return ScopfDcResult(
            provenance=provenance(),
            status=secured.status,
            message=secured.message,
            iterations=secured.iterations,
            base_objective_cost=secured.base_objective_cost,
        )

    ptdf_matrix = solution.ptdf
    lmp = lmp_decomposition(solution.duals, ptdf_matrix, secured.security, secured.corrective)
    gen_by_bus = np.bincount(arr.gen_bus, weights=solution.dispatch_mw, minlength=arr.n_bus)
    injection_mw = gen_by_bus - (arr.p_load_pu + arr.g_shunt_pu) * arr.base_mva
    flows_mw = flow_from_ptdf(ptdf_matrix, injection_mw, arr)

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
    constraints = [
        SecurityConstraintResult(
            outage_kind=c.kind,
            outage_id=(arr.gen_ids if c.kind == "generator" else arr.branch_ids)[c.outage],
            outage_ids=(
                [arr.branch_ids[c.outage], arr.branch_ids[c.outage2]] if c.kind == "pair" else []
            ),
            branch_id=arr.branch_ids[c.monitored],
            rating_mva=float(secured.security.rating_mw[r]),
            post_contingency_flow_mw=float(secured.post_contingency_flow_mw[r]),
            dual=float(solution.duals.security[r]),
        )
        for r, c in enumerate(secured.contingencies)
    ]

    dispatched = _dispatched_copy(net, arr, solution.dispatch_mw)
    confirmation = n1(dispatched, N1Options(generator_outages=opts.generator_outages))
    secure = not any(o.confirmed_violating for o in confirmation.outages) and not any(
        o.confirmed_violating for o in confirmation.generator_outages
    )
    pair_confirmation = n2(dispatched) if opts.branch_pairs else None
    if pair_confirmation is not None:
        secure = secure and not any(o.confirmed_violating for o in pair_confirmation.outages)
    corrections = _corrections(net, arr, secured)
    ac_check = feasibility_report(solve_ac(dispatched), dispatched) if opts.ac_check else None
    return ScopfDcResult(
        provenance=provenance(),
        status=secured.status,
        message=None,
        iterations=secured.iterations,
        secure=secure,
        base_objective_cost=secured.base_objective_cost,
        objective_cost=solution.objective_cost,
        security_cost=solution.objective_cost - secured.base_objective_cost,
        balance_dual=solution.duals.balance,
        generators=generators,
        buses=buses,
        branches=branches,
        constraints=constraints,
        n1=confirmation,
        n2=pair_confirmation,
        ac_check=ac_check,
        corrections=corrections,
        corrected_secure=all(c.confirmed_max_loading <= 1.0 + 1e-9 for c in corrections),
    )


def _corrective_ramps(net: Network, arr: NetworkArrays) -> tuple[FloatArray, FloatArray]:
    """``Generator.ramp_up_mw`` / ``ramp_down_mw`` in ``arr`` order, ``inf`` where ``None``: the
    corrective ramps of ADR-021, the same gather ``market.multiperiod`` makes for its ramp rows."""
    gens_by_id = {g.id: g for g in net.generators}

    def column(attribute: str) -> FloatArray:
        values = [getattr(gens_by_id[gen_id], attribute) for gen_id in arr.gen_ids]
        return np.array([np.inf if v is None else v for v in values], dtype=np.float64)

    return column("ramp_up_mw"), column("ramp_down_mw")


def _corrections(
    net: Network, arr: NetworkArrays, secured: ScopfSolution
) -> list[CorrectiveActionResult]:
    """One :class:`~mambo_power.results.CorrectiveActionResult` per corrected outage (ADR-021),
    each confirmed by a real DC re-solve of the network with the outage applied and the
    corrected dispatch written in: the loading reported is that solve's, not the LP's."""
    solution = secured.solution
    if secured.corrective is None or solution.duals is None:
        return []
    rows_by_outage: dict[tuple[str, int], list[SecurityConstraintResult]] = {}
    for r, c in enumerate(secured.corrected_contingencies):
        rows_by_outage.setdefault((c.kind, c.outage), []).append(
            SecurityConstraintResult(
                outage_kind=c.kind,
                outage_id=(arr.branch_ids if c.kind == "branch" else arr.gen_ids)[c.outage],
                branch_id=arr.branch_ids[c.monitored],
                rating_mva=float(secured.corrective.rating_mw[r]),
                post_contingency_flow_mw=float(secured.corrected_flow_mw[r]),
                dual=float(solution.duals.corrective_flow[r]),
            )
        )
    out: list[CorrectiveActionResult] = []
    for b, (kind, outage) in enumerate(secured.corrected_outages):
        corrected = solution.corrective_dispatch_mw[b]
        outage_id = (arr.branch_ids if kind == "branch" else arr.gen_ids)[outage]
        outaged = _dispatched_copy(net, arr, corrected)
        if kind == "branch":
            next(br for br in outaged.branches if br.id == outage_id).in_service = False
        else:
            next(g for g in outaged.generators if g.id == outage_id).in_service = False
        arr_k = NetworkArrays.from_network(outaged)
        flows = np.abs(pfdc.solve(arr_k).p_from_pu)
        loading = flows / arr_k.rating_pu  # inf rating -> 0
        out.append(
            CorrectiveActionResult(
                outage_kind="branch" if kind == "branch" else "generator",
                outage_id=outage_id,
                redispatch=[
                    GenCorrectionResult(
                        id=gen_id,
                        p_mw=float(corrected[i]),
                        delta_mw=float(corrected[i] - solution.dispatch_mw[i]),
                    )
                    for i, gen_id in enumerate(arr.gen_ids)
                ],
                constraints=rows_by_outage.get((kind, outage), []),
                confirmed_max_loading=float(np.max(loading)) if loading.size else 0.0,
            )
        )
    return out


def voltage_limits(
    net: Network, arr: NetworkArrays, *, default_min: float, default_max: float
) -> tuple[FloatArray, FloatArray]:
    """Per-bus ``(v_min_pu, v_max_pu)`` in ``arr`` bus order, each bus's own limit where it
    carries one and the given default where it does not — the cost gather's voltage twin."""
    buses_by_id = {b.id: b for b in net.buses}
    v_min = np.array(
        [
            default_min if buses_by_id[b].v_min_pu is None else buses_by_id[b].v_min_pu
            for b in arr.bus_ids
        ],
        dtype=np.float64,
    )
    v_max = np.array(
        [
            default_max if buses_by_id[b].v_max_pu is None else buses_by_id[b].v_max_pu
            for b in arr.bus_ids
        ],
        dtype=np.float64,
    )
    return v_min, v_max


def solve_ac_opf(net: Network, options: OpfAcOptions | None = None) -> OpfAcResult:
    """AC optimal power flow of ``net`` (ADR-018): active and reactive dispatch, voltages, AC
    LMPs, apparent-power flows at both ends of every branch.

    The same never-raise convention as :func:`solve_dc_opf`: a run that does not converge is
    reported through ``OpfAcResult.status``/``message``. Raises :class:`NonConvexCostError` and
    :class:`MissingCostError` up front like :func:`solve_dc_opf`, and
    :class:`~mambo_power.opf.dc_opf.NonConcaveBidError` for a non-concave bid when
    ``options.elastic_demand`` is on (ADR-030: every ``Load.bid`` is then honoured, the welfare
    ``objective_cost − demand_value`` minimised). A bus with no ``v_min_pu`` / ``v_max_pu``
    takes ``options.v_default_min_pu`` / ``v_default_max_pu``. The network is not modified.
    """
    opts = options if options is not None else OpfAcOptions()
    started_at = datetime.now(UTC)
    clock = time.perf_counter()
    arr = NetworkArrays.from_network(net)
    cost_coeffs, pwl_costs = gen_cost_coeffs(net, arr)
    v_min, v_max = voltage_limits(
        net, arr, default_min=opts.v_default_min_pu, default_max=opts.v_default_max_pu
    )
    bid_coeffs: dict[int, tuple[float, float, float]] = {}
    pwl_bids: dict[int, list[tuple[float, float]]] = {}
    if opts.elastic_demand:
        from mambo_power.market.nodal import load_bid_coeffs  # market imports opf: lazily

        bid_coeffs, pwl_bids = load_bid_coeffs(net, arr)
    elastic_idxs = sorted(set(bid_coeffs) | set(pwl_bids))
    solution = ac_opf(
        arr,
        cost_coeffs,
        opts,
        v_min_pu=v_min,
        v_max_pu=v_max,
        pwl_costs=pwl_costs or None,
        demand_bid_coeffs=bid_coeffs or None,
        demand_pwl_bids=pwl_bids or None,
    )
    provenance = ResultProvenance(
        engine="mambo-power",
        version=mambo_power.__version__,
        kind="opf.ac",
        solver=AC_OPF_SOLVER,
        started_at=started_at,
        elapsed_s=time.perf_counter() - clock,
        options=opts.model_dump(),
    )
    if solution.status != "Optimal" or solution.duals is None:
        return OpfAcResult(
            provenance=provenance,
            status=solution.status,
            message=solution.message,
            iterations=solution.iterations,
            objective_cost=solution.objective_cost,
            max_mismatch_pu=solution.max_mismatch_pu,
        )
    base = arr.base_mva
    duals = solution.duals
    generators = [
        AcGenDispatchResult(
            id=gen_id,
            bus=arr.bus_ids[int(arr.gen_bus[i])],
            p_mw=float(solution.gen_p_mw[i]),
            q_mvar=float(solution.gen_q_mvar[i]),
            p_bound_dual=float(duals.gen_p_bound[i]),
            q_bound_dual=float(duals.gen_q_bound[i]),
        )
        for i, gen_id in enumerate(arr.gen_ids)
    ]
    served = arr.load_p_max_pu * base
    served[elastic_idxs] = solution.demand_dispatch_mw
    bound_dual = np.zeros(len(arr.load_ids))
    bound_dual[elastic_idxs] = duals.demand_bound
    with np.errstate(divide="ignore", invalid="ignore"):
        pf_ratio = np.where(arr.load_p_max_pu > 0.0, arr.load_q_pu / arr.load_p_max_pu, 0.0)
    loads = [
        AcLoadDispatchResult(
            id=load_id,
            bus=arr.bus_ids[int(arr.load_bus[i])],
            p_mw=float(served[i]),
            q_mvar=float(served[i] * pf_ratio[i]) if served[i] != 0.0 else 0.0,
            elastic=i in elastic_idxs,
            bound_dual=float(bound_dual[i]),
        )
        for i, load_id in enumerate(arr.load_ids)
    ]
    buses = [
        AcBusResult(
            id=bus_id,
            vm_pu=float(np.abs(solution.v[i])),
            va_deg=float(np.degrees(np.angle(solution.v[i]))),
            lmp_p=float(duals.lmp_p[i]),
            lmp_q=float(duals.lmp_q[i]),
            v_bound_dual=float(duals.v_bound[i]),
        )
        for i, bus_id in enumerate(arr.bus_ids)
    ]
    s_from = solution.s_from_pu * base
    s_to = solution.s_to_pu * base
    rating = arr.rating_pu * base
    branches = []
    for k, br_id in enumerate(arr.branch_ids):
        s_f, s_t = float(np.abs(s_from[k])), float(np.abs(s_to[k]))
        branches.append(
            AcBranchFlowResult(
                id=br_id,
                from_bus=arr.bus_ids[int(arr.f[k])],
                to_bus=arr.bus_ids[int(arr.t[k])],
                p_from_mw=float(s_from[k].real),
                q_from_mvar=float(s_from[k].imag),
                p_to_mw=float(s_to[k].real),
                q_to_mvar=float(s_to[k].imag),
                s_from_mva=s_f,
                s_to_mva=s_t,
                loading_percent=(
                    100.0 * max(s_f, s_t) / float(rating[k]) if np.isfinite(rating[k]) else None
                ),
                flow_from_dual=float(duals.flow_from[k]),
                flow_to_dual=float(duals.flow_to[k]),
                angle_deg=float(
                    np.degrees(
                        np.angle(solution.v[int(arr.f[k])]) - np.angle(solution.v[int(arr.t[k])])
                    )
                ),
                angle_dual=float(duals.angle[k]) if duals.angle.size else 0.0,
            )
        )
    losses_mw = float(np.sum(solution.gen_p_mw) - np.sum(served))
    return OpfAcResult(
        provenance=provenance,
        status=solution.status,
        message=None,
        iterations=solution.iterations,
        objective_cost=solution.objective_cost,
        demand_value=solution.demand_value,
        losses_mw=losses_mw,
        max_mismatch_pu=solution.max_mismatch_pu,
        generators=generators,
        loads=loads,
        buses=buses,
        branches=branches,
    )
