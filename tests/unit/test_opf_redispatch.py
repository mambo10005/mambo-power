"""``opf.redispatch`` — the min-cost redispatch LP/QP from a zonal operating point (M6 W3).

Two acceptance criteria live here.

**AC-3 (feasibility, with its paired negative).** The redispatched dispatch is feasible in
``pf.dc`` under every branch rating, on every multi-zone fixture, to :data:`FLOW_TOL_MW`. The
paired negative is in the same test and is what stops the readback being vacuous: the operating
point the redispatch *starts* from violates at least one real rating, by
:data:`MIN_START_VIOLATION_MW` or more. That starting point is built the way research §5 built its
own probe — solve ``dc_opf`` on the rated network with every *intra-zone* branch rating removed,
so the clearing sees only the inter-zone cut-sets, exactly the information a zonal market has —
because ``opf.zonal`` is a sibling slice and is not imported here. When it lands, the same test
body accepts its output unchanged: the redispatch LP does not care which solve produced
``(p0, d0)``.

**D1's theorem (AC-4's engine-side half).** Because the objective is the true welfare function
over nodal's exact feasible set, ``redispatch_dc_opf`` must return the *same final point as*
``dc_opf`` from **any** bound-feasible starting point. Asserted on case14 and rated case30 from
two unrelated starting points each (every generator at ``p_min`` with no demand served; every
generator at ``p_max`` with all demand served) plus, in the AC-3 test, the zonal-ish point itself.
Agreement is to tolerance, never bitwise (spec assumption A3, M5's macOS CI finding).

**Why the dispatch tolerance is looser than the welfare tolerance**, measured rather than
guessed. At the optimum the welfare surface is *flat along the direction that trades one interior
generator against another*: two interior generators have equal marginal cost there, so moving
``δ`` MW between them costs ``O(c2·δ²)``. The two solves therefore agree on welfare to ~1e-9
relative (:data:`WELFARE_REL_TOL`) while landing up to ~1e-4 MW apart in dispatch
(:data:`DISPATCH_TOL_MW`) — the dispatch difference is the *problem's* flatness, not a modelling
difference, and the welfare assertion is the sharper of the two. Both are asserted; a real
objective error moves the welfare one immediately (the sabotage sweep confirms it).
"""

from __future__ import annotations

import numpy as np
import numpy.typing as npt
import pytest

from mambo_power.io import matpower
from mambo_power.market.nodal import load_bid_coeffs
from mambo_power.model import Network, PiecewiseBid
from mambo_power.numerics import NetworkArrays
from mambo_power.opf import gen_cost_coeffs
from mambo_power.opf.dc_opf import (
    NonConcaveBidError,
    NonConvexCostError,
    OpfDcOptions,
    OpfSolution,
    dc_opf,
    lmp_decomposition,
)
from mambo_power.opf.redispatch import (
    BOUND_TOL_MW,
    RedispatchSolution,
    redispatch_dc_opf,
)
from mambo_power.pf import dc as pfdc
from tests._bids import with_bids
from tests._degeneracy import (
    assert_flow_limit_duals_agree_up_to_redundancy,
    assert_lmps_agree_up_to_redundancy,
    decision_variable_bus_columns,
    ptdf_redundant_groups,
)
from tests._fixtures import FIXTURES_DIR
from tests._rated import rated_network
from tests._zones import promote_areas_to_zones, zone_of_bus

FloatArray = npt.NDArray[np.float64]

FLOW_TOL_MW = 1e-6
"""AC-3's pinned flow-feasibility tolerance, MW — ``|p_from| <= rating + FLOW_TOL_MW`` on every
branch after redispatch. Research §4(c) proposed this order by analogy with
``SIMULTANEITY_ABS_TOL_MW``; the worst case actually measured here is 8e-12 MW (case300), six
orders inside it, so the constant is headroom rather than a fitted threshold."""

MIN_START_VIOLATION_MW = 1.0
"""AC-3's paired negative, MW: the zonal-ish starting point must overload at least one branch by
at least this much, or the post-redispatch feasibility readback proves nothing. Measured worst
overload is 10.1 MW (case30) and 21.6 MW (case300)."""

DISPATCH_TOL_MW = 1e-3
"""D1's theorem, quantity side, MW — see the module docstring on why this is looser than
:data:`WELFARE_REL_TOL`. Worst measured: 1.1e-4 MW (case14, ``p_max`` start)."""

WELFARE_REL_TOL = 1e-6
"""D1's theorem, value side: relative agreement of ``welfare``/``objective_cost`` against
``dc_opf``'s own. Worst measured: 9.5e-8 (case30)."""

DUAL_TOL = 1e-3
"""D1's theorem, price side, $/MWh — the balance dual, the per-branch flow duals and the derived
LMPs. Worst measured: 2.4e-5 (case14). See ``test_case300_flow_duals_are_degenerate`` for the one
fixture where this tolerance is *not* attainable, and why that is a property of the nodal LP
rather than of this module."""


# --------------------------------------------------------------------------------------------
# fixture assembly


def _elastic_network(case: str) -> Network:
    """A rated, zone-promoted, partly-elastic copy of ``case``.

    Drives the committed factories (``tests/_rated.py``, ``tests/_zones.py``, ``tests/_bids.py``)
    rather than hand-assembling anything: ratings from ``rated_network``, zones from
    ``promote_areas_to_zones`` (a no-op on case300, which carries four real ones), bids from
    ``with_bids``. Two of the five bid loads get the *interior* derivation so demand actually
    moves in the redispatch instead of sitting pinned at its own bound.
    """
    net = promote_areas_to_zones(rated_network(matpower.load(FIXTURES_DIR / f"{case}.m")))
    load_ids = [ld.id for ld in net.loads if ld.p_mw > 0][:5]
    return with_bids(net, load_ids, interior_load_ids=load_ids[:2])


def _relax_intra_zone(net: Network) -> Network:
    """A copy of ``net`` with every *intra-zone* branch's rating removed — research §5's own
    construction of a network-blind clearing step. On rated case30 this leaves 7 of 41 branches
    rated (the inter-zone cut-sets), which is exactly the count research §5 measured.
    """
    out = net.model_copy(deep=True)
    zone_of = zone_of_bus(out)
    for branch in out.branches:
        if zone_of.get(branch.from_bus) == zone_of.get(branch.to_bus):
            branch.rating_mva = None
    return out


def _problem(net: Network) -> tuple[NetworkArrays, FloatArray, dict, dict, dict, list[int]]:
    """``(arr, cost_coeffs, pwl_costs, demand_bid_coeffs, demand_pwl_bids, elastic_load_idxs)``
    for ``net``, through the same two extraction helpers ``market.nodal`` itself uses."""
    arr = NetworkArrays.from_network(net)
    cost_coeffs, pwl_costs = gen_cost_coeffs(net, arr)
    bid_coeffs, pwl_bids = load_bid_coeffs(net, arr)
    elastic = sorted(set(bid_coeffs) | set(pwl_bids))
    return arr, cost_coeffs, pwl_costs, bid_coeffs, pwl_bids, elastic


def _nodal(net: Network) -> OpfSolution:
    """``dc_opf`` on ``net`` with its bids — the reference point D1's theorem names."""
    arr, cost_coeffs, pwl_costs, bid_coeffs, pwl_bids, _ = _problem(net)
    return dc_opf(
        arr,
        cost_coeffs,
        OpfDcOptions(),
        pwl_costs=pwl_costs or None,
        demand_bid_coeffs=bid_coeffs or None,
        demand_pwl_bids=pwl_bids or None,
    )


def _redispatch(net: Network, p0: FloatArray, d0: FloatArray | None) -> RedispatchSolution:
    """``redispatch_dc_opf`` on ``net``'s own arrays from ``(p0, d0)``."""
    arr, cost_coeffs, pwl_costs, bid_coeffs, pwl_bids, _ = _problem(net)
    return redispatch_dc_opf(
        arr,
        cost_coeffs,
        p0,
        d0,
        pwl_costs=pwl_costs or None,
        demand_bid_coeffs=bid_coeffs or None,
        demand_pwl_bids=pwl_bids or None,
    )


def _overload_mw(net: Network, p_mw: FloatArray, d_mw: FloatArray) -> FloatArray:
    """Per-branch ``|p_from| − rating`` (MW) of the point ``(p_mw, d_mw)``, read back through
    :func:`mambo_power.pf.dc.solve` on a copy of ``net`` carrying that dispatch — the epic
    verification table's own wording ("redispatched flows feasible in ``pf.dc``"), and a path
    entirely independent of the LP rows that produced the point.
    """
    arr, *_rest, elastic = _problem(net)
    out = net.model_copy(deep=True)
    dispatch_by_id = {gen_id: float(p_mw[i]) for i, gen_id in enumerate(arr.gen_ids)}
    demand_by_id = {arr.load_ids[idx]: float(d_mw[j]) for j, idx in enumerate(elastic)}
    for gen in out.generators:
        if gen.id in dispatch_by_id:
            gen.p_mw = dispatch_by_id[gen.id]
    for load in out.loads:
        if load.id in demand_by_id:
            load.p_mw = demand_by_id[load.id]
    dispatched = NetworkArrays.from_network(out)
    solution = pfdc.solve(dispatched)
    flow_mw = np.abs(solution.p_from_pu) * dispatched.base_mva
    return flow_mw - dispatched.rating_pu * dispatched.base_mva


def _balance_residual_mw(net: Network, p_mw: FloatArray, d_mw: FloatArray) -> float:
    """``Sum p - Sum d - (fixed load + shunts)`` at the point ``(p_mw, d_mw)``, MW.

    :func:`_overload_mw` alone does **not** imply energy balance: ``pf.dc`` puts the slack bus at
    angle 0 and lets it absorb whatever mismatch the declared injections carry, so an unbalanced
    dispatch still produces a finite, possibly rating-respecting flow vector. A sign error
    confined to the balance row is exactly that shape of defect, and the sabotage sweep found it
    passing the flow readback on case30. So AC-3's "feasible" is asserted as both halves: the
    flows respect every rating **and** the point closes the energy balance.
    """
    arr, *_rest, elastic = _problem(net)
    elastic_idx = np.asarray(elastic, dtype=np.int64)
    fixed_load_mw = arr.p_load_pu * arr.base_mva
    if elastic_idx.size:
        fixed_load_mw = fixed_load_mw - np.bincount(
            arr.load_bus[elastic_idx],
            weights=arr.load_p_max_pu[elastic_idx] * arr.base_mva,
            minlength=arr.n_bus,
        )
    shunt_mw = arr.g_shunt_pu * arr.base_mva
    return float(p_mw.sum() - d_mw.sum() - fixed_load_mw.sum() - shunt_mw.sum())


def _bounds(net: Network) -> tuple[FloatArray, FloatArray, FloatArray, FloatArray]:
    """``(p_min, p_max, d_min, d_max)`` in MW, generator order and elastic-load order."""
    arr, *_rest, elastic = _problem(net)
    idx = np.asarray(elastic, dtype=np.int64)
    return (
        arr.gen_p_min_pu * arr.base_mva,
        arr.gen_p_max_pu * arr.base_mva,
        arr.load_p_min_pu[idx] * arr.base_mva,
        arr.load_p_max_pu[idx] * arr.base_mva,
    )


# --------------------------------------------------------------------------------------------
# AC-3 — feasibility in pf.dc, with the paired negative in the same test


@pytest.mark.parametrize("case", ["case30", "case300"])
def test_ac3_redispatch_restores_pf_dc_feasibility_from_an_infeasible_zonal_point(
    case: str,
) -> None:
    """AC-3 on every multi-zone fixture: the *starting* point overloads at least one real rating
    (paired negative, ``MIN_START_VIOLATION_MW``); the *redispatched* point overloads none
    (``FLOW_TOL_MW``). Both readbacks go through ``pf.dc`` on a network carrying the dispatch,
    not through the LP's own rows.
    """
    net = _elastic_network(case)
    relaxed = _relax_intra_zone(net)
    assert len(net.zones) > 1, "fixture must be genuinely multi-zone for AC-3 to mean anything"

    # the network-blind clearing step: same costs/bids, only the inter-zone cut-sets rated.
    arr_relaxed, cost_coeffs, pwl_costs, bid_coeffs, pwl_bids, _ = _problem(relaxed)
    zonal = dc_opf(
        arr_relaxed,
        cost_coeffs,
        OpfDcOptions(),
        pwl_costs=pwl_costs or None,
        demand_bid_coeffs=bid_coeffs or None,
        demand_pwl_bids=pwl_bids or None,
    )
    assert zonal.status == "Optimal"

    start_overload = _overload_mw(net, zonal.dispatch_mw, zonal.demand_dispatch_mw)
    assert start_overload.max() >= MIN_START_VIOLATION_MW, (
        f"{case}: the zonal-ish starting point overloads nothing by more than "
        f"{start_overload.max()!r} MW — AC-3's feasibility readback would be vacuous"
    )

    solution = _redispatch(net, zonal.dispatch_mw, zonal.demand_dispatch_mw)
    assert solution.status == "Optimal"
    final_overload = _overload_mw(net, solution.dispatch_mw, solution.demand_dispatch_mw)
    worst = int(np.argmax(final_overload))
    assert final_overload[worst] <= FLOW_TOL_MW, (
        f"{case}: branch index {worst} is still {final_overload[worst]!r} MW over its rating "
        "after redispatch"
    )
    # ...and the point closes the energy balance, which the flow readback above does not imply
    # (see :func:`_balance_residual_mw`).
    assert _balance_residual_mw(net, solution.dispatch_mw, solution.demand_dispatch_mw) == (
        pytest.approx(0.0, abs=FLOW_TOL_MW)
    )

    # the point genuinely moved: a redispatch that changed nothing would pass the line above
    # trivially, and cannot have, since the starting point was infeasible.
    assert solution.delta_up_mw.sum() + solution.delta_down_mw.sum() > 0.0


def test_ac3_paired_negative_is_the_zonal_point_not_a_weaker_network() -> None:
    """The AC-3 negative above compares against the **same** rated network the positive uses —
    the overload is the starting *point*'s, not an artefact of a different fixture (M5's lesson
    that a sabotage applied to shared fixture data is not a sabotage).

    Stated as its own assertion because the two readbacks in the test above share one ``net``
    variable and nothing else would notice if a future edit split them.
    """
    net = _elastic_network("case30")
    zonal_arr, cost_coeffs, *_rest = _problem(_relax_intra_zone(net))
    rated_arr, *_more = _problem(net)
    assert np.array_equal(zonal_arr.gen_p_max_pu, rated_arr.gen_p_max_pu)
    assert np.array_equal(zonal_arr.p_load_pu, rated_arr.p_load_pu)
    # ...and differ in exactly one way: the intra-zone ratings the clearing step cannot see.
    relaxed_rated = np.isfinite(zonal_arr.rating_pu)
    truly_rated = np.isfinite(rated_arr.rating_pu)
    assert truly_rated.all()
    assert relaxed_rated.sum() == 7, "research §5 measured 7 inter-zone tie lines on case30"


# --------------------------------------------------------------------------------------------
# D1's theorem — the same final point as dc_opf, from any bound-feasible start


def _starting_points(net: Network) -> list[tuple[str, FloatArray, FloatArray]]:
    """Two unrelated bound-feasible starting points: the floor of the box and its ceiling.

    Neither is network-feasible and neither is anywhere near the optimum — which is the point.
    D1's theorem claims path-independence, so the starts that test it hardest are the ones
    furthest from where the answer lies.
    """
    p_min, p_max, d_min, d_max = _bounds(net)
    return [
        ("floor", p_min.copy(), d_min.copy()),
        ("ceiling", p_max.copy(), d_max.copy()),
    ]


@pytest.mark.parametrize("case", ["case14", "case30"])
def test_d1_theorem_redispatch_reaches_the_nodal_optimum_from_any_start(case: str) -> None:
    """D1's theorem: for **any** bound-feasible ``(p0, d0)``, the redispatched point is the nodal
    optimum — quantities to :data:`DISPATCH_TOL_MW`, welfare to :data:`WELFARE_REL_TOL`, prices to
    :data:`DUAL_TOL`. If this fails, the objective is wrong, not the theorem.

    The price clause is quotiented by known PTDF-row redundancy
    (``tests._degeneracy``, ``.bionic/docs/record/case30-t1-diagnosis.md``): rated case30 sits on a
    genuine dual-degenerate face at branch-11/branch-12/branch-14 around bus-9 (a zero-injection
    node, so two of the three branches' flow-limit rows are literally redundant constraints), proven
    by rank deficiency of the restricted active-constraint matrix — not a measurement, algebra. Two
    equally optimal solves may legitimately split that bottleneck's shadow price differently among
    the three rows; only the group's own conserved (weighted) sum is a KKT invariant, so that is
    what is asserted for those rows, point-wise everywhere else. case14 also carries one
    structurally redundant group (branches never simultaneously at rating in this fixture; nodal
    and both starts keep it at exactly zero every time), so quotienting changes nothing there --
    verified by direct measurement, not assumed -- and the assertion is exactly as strong as the
    point-wise form it replaces.
    """
    net = _elastic_network(case)
    arr, *_rest, elastic = _problem(net)
    nodal = _nodal(net)
    assert nodal.status == "Optimal"
    nodal_welfare = _welfare_of(net, nodal.dispatch_mw, nodal.demand_dispatch_mw)
    nodal_lmp = lmp_decomposition(nodal.duals, nodal.ptdf).lmp

    elastic_idx = np.asarray(elastic, dtype=np.int64)
    decision_cols = decision_variable_bus_columns(arr.gen_bus, arr.load_bus[elastic_idx])
    groups, zero_rows = ptdf_redundant_groups(nodal.ptdf, decision_cols)

    for label, p0, d0 in _starting_points(net):
        solution = _redispatch(net, p0, d0)
        assert solution.status == "Optimal", label
        assert solution.dispatch_mw == pytest.approx(nodal.dispatch_mw, abs=DISPATCH_TOL_MW), label
        assert solution.demand_dispatch_mw == pytest.approx(
            nodal.demand_dispatch_mw, abs=DISPATCH_TOL_MW
        ), label
        assert solution.objective_cost == pytest.approx(
            nodal.objective_cost, rel=WELFARE_REL_TOL
        ), label
        assert solution.welfare == pytest.approx(nodal_welfare, rel=WELFARE_REL_TOL), label
        assert solution.duals is not None
        assert solution.duals.balance == pytest.approx(nodal.duals.balance, abs=DUAL_TOL), label
        assert_flow_limit_duals_agree_up_to_redundancy(
            solution.duals.flow_limit,
            nodal.duals.flow_limit,
            groups,
            zero_rows,
            atol=DUAL_TOL,
            label=f"{case}/{label}: ",
        )
        redispatch_lmp = lmp_decomposition(solution.duals, solution.ptdf).lmp
        assert_lmps_agree_up_to_redundancy(
            redispatch_lmp,
            nodal_lmp,
            nodal.ptdf,
            groups,
            zero_rows,
            atol=DUAL_TOL,
            label=f"{case}/{label}: ",
        )
        # the reduced costs come back on the delta columns and mean what the docstring says
        assert solution.duals.gen_bound == pytest.approx(nodal.duals.gen_bound, abs=DUAL_TOL), label
        assert solution.demand_bound == pytest.approx(nodal.demand_bound, abs=DUAL_TOL), label


def _welfare_of(net: Network, p_mw: FloatArray, d_mw: FloatArray) -> float:
    """True welfare (bid value − generation cost) of ``(p_mw, d_mw)``, evaluated **outside** the
    solver from the raw coefficient arrays — so the theorem's value side is not checked against a
    number ``redispatch`` itself computed."""
    _arr, cost_coeffs, pwl_costs, bid_coeffs, pwl_bids, elastic = _problem(net)
    assert not pwl_costs and not pwl_bids, "this helper covers the polynomial fixtures only"
    cost = float(np.sum(cost_coeffs[:, 0] * p_mw**2 + cost_coeffs[:, 1] * p_mw + cost_coeffs[:, 2]))
    coeffs = np.asarray([bid_coeffs[i] for i in elastic], dtype=np.float64)
    value = float(np.sum(coeffs[:, 0] * d_mw**2 + coeffs[:, 1] * d_mw + coeffs[:, 2]))
    return value - cost


def test_d1_theorem_holds_from_the_nodal_optimum_itself() -> None:
    """The degenerate start: redispatching from the nodal optimum moves nothing at all. A
    redispatch LP whose balance RHS or flow ``const`` mis-folds the starting point would still
    reach *some* feasible point from a far-away start, but cannot leave this one alone.

    "Nothing" is :data:`DISPATCH_TOL_MW`, not zero, for the module docstring's reason: the QP
    re-converges into the same flat valley and lands ~3e-5 MW from where ``dc_opf`` stopped. A
    mis-folded RHS moves whole MW, so the tolerance still separates the two cases by two orders."""
    net = _elastic_network("case30")
    nodal = _nodal(net)
    solution = _redispatch(net, nodal.dispatch_mw, nodal.demand_dispatch_mw)
    assert solution.status == "Optimal"
    zero_gen = np.zeros_like(solution.delta_up_mw)
    zero_demand = np.zeros_like(solution.demand_delta_up_mw)
    assert solution.delta_up_mw == pytest.approx(zero_gen, abs=DISPATCH_TOL_MW)
    assert solution.delta_down_mw == pytest.approx(zero_gen, abs=DISPATCH_TOL_MW)
    assert solution.demand_delta_up_mw == pytest.approx(zero_demand, abs=DISPATCH_TOL_MW)
    assert solution.demand_delta_down_mw == pytest.approx(zero_demand, abs=DISPATCH_TOL_MW)


def test_case300_flow_duals_are_degenerate_at_the_nodal_optimum() -> None:
    """A measured, deliberately-recorded *limit* on how far AC-4's price half can be pushed.

    On rated case300 seven branches sit exactly at their rating at the nodal optimum while only
    five carry a nonzero dual — the active set is not unique, so ``dc_opf`` and
    ``redispatch_dc_opf`` legitimately select different ones and their LMPs differ by ~0.32
    $/MWh on a ~40 $/MWh system (0.8%). The *primal* theorem still holds there to
    :data:`WELFARE_REL_TOL`, which is what this test pins: the quantities and the welfare agree,
    the duals are simply not a function of the optimum on this fixture. Recorded here so the
    later ``market.zonal`` slice does not read a degenerate dual as a defect in either builder.
    """
    net = _elastic_network("case300")
    nodal = _nodal(net)
    relaxed_arr, cost_coeffs, pwl_costs, bid_coeffs, pwl_bids, _ = _problem(_relax_intra_zone(net))
    zonal = dc_opf(
        relaxed_arr,
        cost_coeffs,
        OpfDcOptions(),
        pwl_costs=pwl_costs or None,
        demand_bid_coeffs=bid_coeffs or None,
        demand_pwl_bids=pwl_bids or None,
    )
    solution = _redispatch(net, zonal.dispatch_mw, zonal.demand_dispatch_mw)
    assert solution.status == "Optimal"
    assert solution.duals is not None

    # primal: the theorem holds.
    assert solution.objective_cost == pytest.approx(nodal.objective_cost, rel=WELFARE_REL_TOL)

    # dual: the two solves agree on which branches are *at* their rating, and disagree on which
    # subset of those carries the price.
    arr, *_rest = _problem(net)
    rating_mw = arr.rating_pu * arr.base_mva
    at_rating = np.flatnonzero(np.abs(np.abs(solution.branch_flow_mw) - rating_mw) < FLOW_TOL_MW)
    priced_nodal = np.flatnonzero(np.abs(nodal.duals.flow_limit) > 1e-9)
    priced_redispatch = np.flatnonzero(np.abs(solution.duals.flow_limit) > 1e-9)
    assert set(priced_nodal) <= set(at_rating)
    assert set(priced_redispatch) <= set(at_rating)
    assert at_rating.size > priced_nodal.size, (
        "case300 is expected to be primal-degenerate here; if it no longer is, this test's "
        "premise is gone and AC-4's dual half can be tightened on this fixture"
    )
    assert set(priced_nodal) != set(priced_redispatch)


# --------------------------------------------------------------------------------------------
# reported shape and invariants


def test_reported_deltas_are_the_movement_to_an_independently_computed_final_point() -> None:
    """The reported ``(Δ+, Δ−)`` pair is the **canonical netting** of the movement from ``(p0, d0)``
    to the final point — measured against a final point this test computes without the reported
    pair.

    The earlier form of this test asserted ``final == p0 + Δ+ − Δ−`` and ``Δ+ · Δ− == 0`` against
    the solution's own arrays. Production computes ``Δ+ = max(gen_net, 0)``, ``Δ− = max(−gen_net,
    0)`` and ``dispatch = p0 + gen_net`` from a single ``gen_net``, and ``max(g,0) − max(−g,0) ≡ g``
    and ``max(g,0)·max(−g,0) ≡ 0`` hold bit-exactly for every float and any solver output
    whatsoever — so those clauses tested NumPy, not the module (review C13).

    The oracle here is D1's theorem: the final point *is* ``dc_opf``'s optimum on the same network,
    from a separate builder. So ``dc_opf`` supplies the target, the movement ``target − p0`` is
    formed outside the solver, and the reported pair is held to it two ways: the **signed** sum
    reproduces the movement (which the reconstruction clause also did) and the **unsigned** sum
    reproduces its magnitude. The second is the netting claim: a report that padded both columns by
    the same α would still reconstruct the point and still be non-negative, but its unsigned sum
    would exceed the movement by 2α on every participant.

    Non-vacuity is asserted, not hoped for: this fixture must move a real volume and must move it
    in *both* directions, or the unsigned clause reduces to the signed one.
    """
    net = _elastic_network("case30")
    relaxed_arr, cost_coeffs, _pwl, bid_coeffs, _pwlb, _e = _problem(_relax_intra_zone(net))
    zonal = dc_opf(relaxed_arr, cost_coeffs, OpfDcOptions(), demand_bid_coeffs=bid_coeffs or None)
    p0, d0 = zonal.dispatch_mw, zonal.demand_dispatch_mw
    solution = _redispatch(net, p0, d0)

    # The independent target: D1's theorem says the redispatched point is this one.
    target = _nodal(net)
    gen_movement = target.dispatch_mw - p0
    demand_movement = target.demand_dispatch_mw - d0

    assert solution.delta_up_mw - solution.delta_down_mw == pytest.approx(
        gen_movement, abs=DISPATCH_TOL_MW
    )
    assert solution.delta_up_mw + solution.delta_down_mw == pytest.approx(
        np.abs(gen_movement), abs=DISPATCH_TOL_MW
    ), "a non-netted split would reconstruct the point and still overstate the volume"
    assert solution.demand_delta_up_mw - solution.demand_delta_down_mw == pytest.approx(
        demand_movement, abs=DISPATCH_TOL_MW
    )
    assert solution.demand_delta_up_mw + solution.demand_delta_down_mw == pytest.approx(
        np.abs(demand_movement), abs=DISPATCH_TOL_MW
    )

    # The premise: a real volume, moving both ways, or the unsigned clause says nothing extra.
    assert float(np.sum(np.abs(gen_movement))) > 1.0
    assert np.any(gen_movement > DISPATCH_TOL_MW) and np.any(gen_movement < -DISPATCH_TOL_MW), (
        "every generator moving the same way would make the unsigned sum a restatement of the "
        "signed one, and this fixture would stop being a test of netting"
    )

    assert np.all(solution.delta_up_mw >= 0.0) and np.all(solution.delta_down_mw >= 0.0)
    assert np.all(solution.demand_delta_up_mw >= 0.0)
    assert np.all(solution.demand_delta_down_mw >= 0.0)
    # AC-5's carry-over: the flow/dual pair is readable from the result object alone.
    assert solution.branch_flow_mw.shape == solution.duals.flow_limit.shape


def test_branch_flow_mw_matches_an_independent_pf_dc_readback() -> None:
    """``RedispatchSolution.branch_flow_mw`` is the flow ``pf.dc`` computes at the same dispatch —
    so AC-5's settlement identity may be evaluated from the result object without re-solving."""
    net = _elastic_network("case30")
    nodal = _nodal(net)
    solution = _redispatch(net, nodal.dispatch_mw, nodal.demand_dispatch_mw)
    arr, *_rest, elastic = _problem(net)
    out = net.model_copy(deep=True)
    dispatch_by_id = {g: float(solution.dispatch_mw[i]) for i, g in enumerate(arr.gen_ids)}
    demand_by_id = {
        arr.load_ids[idx]: float(solution.demand_dispatch_mw[j]) for j, idx in enumerate(elastic)
    }
    for gen in out.generators:
        if gen.id in dispatch_by_id:
            gen.p_mw = dispatch_by_id[gen.id]
    for load in out.loads:
        if load.id in demand_by_id:
            load.p_mw = demand_by_id[load.id]
    dispatched = NetworkArrays.from_network(out)
    expected = pfdc.solve(dispatched).p_from_pu * dispatched.base_mva
    assert solution.branch_flow_mw == pytest.approx(expected, abs=1e-9)


def test_generator_bounds_are_never_left_by_the_delta_caps() -> None:
    """The delta caps are the shifted generator/load bounds, so the final point cannot leave the
    box nodal itself ranges over — the property D1's theorem rests on, checked directly rather
    than inferred from the theorem holding."""
    net = _elastic_network("case30")
    p_min, p_max, d_min, d_max = _bounds(net)
    for _label, p0, d0 in _starting_points(net):
        solution = _redispatch(net, p0, d0)
        assert np.all(solution.dispatch_mw >= p_min - FLOW_TOL_MW)
        assert np.all(solution.dispatch_mw <= p_max + FLOW_TOL_MW)
        assert np.all(solution.demand_dispatch_mw >= d_min - FLOW_TOL_MW)
        assert np.all(solution.demand_dispatch_mw <= d_max + FLOW_TOL_MW)


# --------------------------------------------------------------------------------------------
# piecewise-linear route — the extra "final quantity" column and its linking row


def _pwl_bid_from(coefficients: tuple[float, float, float], p_max: float) -> PiecewiseBid:
    """A 4-segment concave PWL bid sampling the quadratic ``(v2, v1, v0)`` curve on
    ``[0, p_max]`` — a genuinely concave curve (a concave function's chords are below it, and
    successive chord slopes on an increasing grid are decreasing), not a hand-typed table."""
    v2, v1, v0 = coefficients
    points = [(float(q), float(v2 * q**2 + v1 * q + v0)) for q in np.linspace(0.0, p_max, 5)]
    return PiecewiseBid(points=points)


def test_d1_theorem_holds_on_the_piecewise_linear_route() -> None:
    """The theorem again, on a fixture whose generators carry PWL costs *and* whose bid loads
    carry PWL bids — the route that goes through the extra ``q`` column, its ``_balance_row``
    linking equality and ``_epigraph_rows``/``_hypograph_rows``. A linking row with the wrong sign
    or the wrong RHS puts ``q`` somewhere other than the final quantity, which prices the cost
    curve at the wrong point and breaks the agreement immediately.
    """
    net = matpower.load(FIXTURES_DIR / "derived" / "case14_pwl.m")
    net = rated_network(net)
    arr = NetworkArrays.from_network(net)
    _coeffs, pwl_costs = gen_cost_coeffs(net, arr)
    assert pwl_costs, "case14_pwl must carry piecewise generator costs for this test to mean much"

    # every bid here takes the *interior* derivation: ``bid_for_load``'s fleet-ceiling anchor
    # reads ``c1 + 2·c2·p_max`` off a polynomial cost and rejects this fixture's piecewise ones
    # outright, while ``interior_bid_for_load`` anchors on ``solve_dc_opf``'s own baseline price,
    # which handles a PWL cost fine.
    load_ids = [ld.id for ld in net.loads if ld.p_mw > 0][:3]
    net = with_bids(net, load_ids, interior_load_ids=load_ids)
    # turn the two interior polynomial bids into piecewise ones, sampled off their own curves.
    arr = NetworkArrays.from_network(net)
    bid_coeffs, _pwl_bids = load_bid_coeffs(net, arr)
    by_id = {ld.id: ld for ld in net.loads}
    for load_index, coefficients in list(bid_coeffs.items()):
        load = by_id[arr.load_ids[load_index]]
        if load.id in load_ids[:2]:
            load.bid = _pwl_bid_from(coefficients, load.p_mw)

    arr, cost_coeffs, pwl_costs, bid_coeffs, pwl_bids, _ = _problem(net)
    assert pwl_costs and pwl_bids, "both piecewise families must be present"
    nodal = dc_opf(
        arr,
        cost_coeffs,
        OpfDcOptions(),
        pwl_costs=pwl_costs,
        demand_bid_coeffs=bid_coeffs or None,
        demand_pwl_bids=pwl_bids,
    )
    assert nodal.status == "Optimal"

    p_min, p_max, d_min, d_max = _bounds(net)
    for label, p0, d0 in [("floor", p_min, d_min), ("ceiling", p_max, d_max)]:
        solution = redispatch_dc_opf(
            arr,
            cost_coeffs,
            p0.copy(),
            d0.copy(),
            pwl_costs=pwl_costs,
            demand_bid_coeffs=bid_coeffs or None,
            demand_pwl_bids=pwl_bids,
        )
        assert solution.status == "Optimal", label
        assert solution.objective_cost == pytest.approx(
            nodal.objective_cost, rel=WELFARE_REL_TOL
        ), label
        assert solution.dispatch_mw == pytest.approx(nodal.dispatch_mw, abs=DISPATCH_TOL_MW), label
        assert solution.demand_dispatch_mw == pytest.approx(
            nodal.demand_dispatch_mw, abs=DISPATCH_TOL_MW
        ), label


# --------------------------------------------------------------------------------------------
# validation and the never-raise convention


def test_p0_outside_a_generators_bounds_names_that_generator() -> None:
    net = _elastic_network("case30")
    arr, cost_coeffs, *_rest = _problem(net)
    p_min, p_max, _d_min, _d_max = _bounds(net)
    p0 = p_min.copy()
    p0[2] = p_max[2] + 1.0
    with pytest.raises(ValueError, match=arr.gen_ids[2]):
        redispatch_dc_opf(arr, cost_coeffs, p0, None)


def test_d0_outside_a_loads_bounds_names_that_load() -> None:
    net = _elastic_network("case30")
    arr, cost_coeffs, _pwl, bid_coeffs, _pwlb, elastic = _problem(net)
    _p_min, _p_max, _d_min, d_max = _bounds(net)
    d0 = d_max.copy()
    d0[1] = d_max[1] + 1.0
    with pytest.raises(ValueError, match=arr.load_ids[elastic[1]]):
        redispatch_dc_opf(
            arr,
            cost_coeffs,
            arr.gen_p_min_pu * arr.base_mva,
            d0,
            demand_bid_coeffs=bid_coeffs,
        )


def test_a_starting_point_a_hair_outside_its_bound_is_accepted() -> None:
    """A zonal solve routinely returns a generator a few ulp past its own ``p_max``; rejecting
    that would fail on exactly the points redispatch exists to fix (:data:`BOUND_TOL_MW`)."""
    net = _elastic_network("case30")
    arr, cost_coeffs, *_rest = _problem(net)
    _p_min, p_max, *_ = _bounds(net)
    p0 = p_max + BOUND_TOL_MW / 2.0
    solution = redispatch_dc_opf(arr, cost_coeffs, p0, None)
    assert solution.status == "Optimal"
    assert np.all(solution.delta_up_mw == 0.0), "no headroom above p_max — the cap floors at 0"


def test_mis_shaped_starting_points_are_rejected() -> None:
    net = _elastic_network("case30")
    arr, cost_coeffs, _pwl, bid_coeffs, *_rest = _problem(net)
    with pytest.raises(ValueError, match="p0_mw must have shape"):
        redispatch_dc_opf(arr, cost_coeffs, np.zeros(len(arr.gen_ids) + 1), None)
    with pytest.raises(ValueError, match="d0_mw must have shape"):
        redispatch_dc_opf(
            arr,
            cost_coeffs,
            np.zeros(len(arr.gen_ids)),
            np.zeros(len(bid_coeffs) + 1),
            demand_bid_coeffs=bid_coeffs,
        )


def test_the_shared_extraction_guards_fire_before_any_solve() -> None:
    """``_extract_and_validate`` is this module's only extraction path (ADR-008), so its guards
    reach ``redispatch_dc_opf`` callers unchanged — checked here rather than assumed, since a
    builder that re-derived its own coefficients would silently lose them."""
    net = _elastic_network("case30")
    arr, cost_coeffs, _pwl, bid_coeffs, *_rest = _problem(net)
    p0 = arr.gen_p_min_pu * arr.base_mva

    bad_cost = cost_coeffs.copy()
    bad_cost[0, 0] = -1.0
    with pytest.raises(NonConvexCostError):
        redispatch_dc_opf(arr, bad_cost, p0, None)

    bad_bids = dict(bid_coeffs)
    first = next(iter(bad_bids))
    bad_bids[first] = (1.0, bad_bids[first][1], bad_bids[first][2])
    with pytest.raises(NonConcaveBidError):
        redispatch_dc_opf(
            arr,
            cost_coeffs,
            p0,
            np.zeros(len(bad_bids)),
            demand_bid_coeffs=bad_bids,
        )

    with pytest.raises(ValueError, match="cost_coeffs must have shape"):
        redispatch_dc_opf(arr, cost_coeffs[:, :2], p0, None)


def test_an_infeasible_model_is_reported_through_status_not_raised() -> None:
    """This package's standing never-raise-on-non-convergence convention (``dc_opf``,
    ``multiperiod_dc_opf``, ``solve_ac``): an infeasible redispatch reports a status and
    zero-filled arrays."""
    net = _elastic_network("case30")
    strangled = net.model_copy(deep=True)
    for branch in strangled.branches:
        branch.rating_mva = 1e-4
    arr, cost_coeffs, _pwl, bid_coeffs, *_rest = _problem(strangled)
    solution = redispatch_dc_opf(
        arr,
        cost_coeffs,
        arr.gen_p_min_pu * arr.base_mva,
        np.zeros(len(bid_coeffs)),
        demand_bid_coeffs=bid_coeffs,
    )
    assert solution.status != "Optimal"
    assert solution.duals is None
    assert solution.message is not None and "redispatch_dc_opf" in solution.message
    assert np.all(solution.dispatch_mw == 0.0)
    assert np.all(solution.branch_flow_mw == 0.0)
    assert solution.objective_cost == 0.0 and solution.demand_value == 0.0
    assert solution.ptdf.shape[0] == arr.n_branch  # built before the solve, returned regardless


def test_no_elastic_demand_is_the_plain_generator_only_case() -> None:
    """``d0_mw=None`` with no bids at all — every M2/M3-shaped caller's exact situation."""
    net = rated_network(matpower.load(FIXTURES_DIR / "case14.m"))
    arr = NetworkArrays.from_network(net)
    cost_coeffs, _pwl = gen_cost_coeffs(net, arr)
    nodal = dc_opf(arr, cost_coeffs, OpfDcOptions())
    solution = redispatch_dc_opf(arr, cost_coeffs, arr.gen_p_min_pu * arr.base_mva, None)
    assert solution.status == "Optimal"
    assert solution.dispatch_mw == pytest.approx(nodal.dispatch_mw, abs=DISPATCH_TOL_MW)
    assert solution.objective_cost == pytest.approx(nodal.objective_cost, rel=WELFARE_REL_TOL)
    assert solution.demand_dispatch_mw.shape == (0,)
    assert solution.demand_value == 0.0
    assert solution.welfare == pytest.approx(-nodal.objective_cost, rel=WELFARE_REL_TOL)
