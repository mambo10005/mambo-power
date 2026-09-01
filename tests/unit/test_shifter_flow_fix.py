"""M7 F1 / M8 A19: the DC-OPF phase-shifter flow defect, fixed
(task-shifter-flow-fix.plan.md T4).

``pf.solve_dc`` (``pf/dc.py``) always computed the correct DC model --
``flow = PTDF @ (injection - p_shift) + pf_shift`` -- but ``opf.dc_opf``'s own flow-limit row
constant, ``opf.solve_dc_opf``'s derived ``branches[].p_from_mw`` and ``market.solve_nodal``'s
derived branch flows all omitted the ``- p_shift`` term, so they silently disagreed with
``pf.solve_dc`` (and violated KCL) whenever a branch had ``shift_deg != 0``. This module proves,
independently for each of the three sites, that the fixed formula
(``numerics.bbus.flow_from_ptdf``, or the hand-derived equivalent in ``dc_opf``'s own row) now
reproduces ``pf.solve_dc``'s flow on ``tests._shifter.shifter_loop_network`` -- generously rated
by default so these tests isolate the shift-formula bug from the rating logic entirely -- at two
asymmetric shift angles, ``-7`` and ``+12`` degrees (deliberately not a symmetric ``+-5``, so a
sign error that happens to cancel at a symmetric pair could not hide).

PyPSA ``lpf()``'s independent agreement with ``pf.solve_dc`` on this same fixture (a second,
external oracle, re-proving the exporter is still correct on a shifted network) lives in
``tests/parity/test_shifter_pf_vs_pypsa.py`` -- this file sticks to hermetic, in-repo checks
(``tests/unit`` convention).
"""

from __future__ import annotations

import pytest

from mambo_power import pf
from mambo_power.market.nodal import solve_nodal
from mambo_power.model import Scenario
from mambo_power.opf import solve_dc_opf
from tests._shifter import LOAD_P_MW, dispatched_network, shifter_loop_network

SHIFT_ANGLES_DEG = [-7.0, 12.0]


def _oracle_flows(net: object, dispatch: dict[str, float]) -> dict[str, float]:
    """``pf.solve_dc`` readback of ``dispatch`` on ``net``, id-keyed."""
    oracle = pf.solve_dc(dispatched_network(net, dispatch))  # type: ignore[arg-type]
    assert oracle.converged
    return {b.id: b.p_from_mw for b in oracle.branches}


# --- opf.solve_dc_opf: derived branches[].p_from_mw vs pf.solve_dc -------------------------------


@pytest.mark.parametrize("shift_deg", SHIFT_ANGLES_DEG)
def test_solve_dc_opf_branch_flows_match_pf_solve_dc(shift_deg: float) -> None:
    net = shifter_loop_network(shift_deg)
    result = solve_dc_opf(net)
    assert result.status == "Optimal", result.message
    dispatch = {g.id: g.p_mw for g in result.generators}
    oracle = _oracle_flows(net, dispatch)
    for branch in result.branches:
        assert branch.p_from_mw == pytest.approx(oracle[branch.id], abs=1e-9), branch.id


# --- market.solve_nodal: derived branch flows vs pf.solve_dc -------------------------------------


@pytest.mark.parametrize("shift_deg", SHIFT_ANGLES_DEG)
def test_solve_nodal_branch_flows_match_pf_solve_dc(shift_deg: float) -> None:
    net = shifter_loop_network(shift_deg)
    result = solve_nodal(Scenario(network=net))
    assert result.status == "Optimal", result.message
    dispatch = {g.id: g.p_mw for g in result.generators}
    oracle = _oracle_flows(net, dispatch)
    for branch in result.branches:
        assert branch.p_from_mw == pytest.approx(oracle[branch.id], abs=1e-9), branch.id


# --- opf.dc_opf's own flow-limit row: the LP's dispatch respects the TRUE physical limit ---------
#
# t12's flow as a function of dispatch is linear in g1 (g3 = 100 - g1 by the balance constraint,
# both bounded [0, 100] here), so its achievable range over a full dispatch sweep is exactly the
# segment between "g1 alone" and "g3 alone" (verified: neither shift angle below crosses zero in
# between). At -7 deg that segment is [74.06, 107.39] MW -- a rating strictly inside it must
# force the LP off the cheap-only optimum and into a real, feasible re-dispatch. At +12 deg the
# segment is [3.15, 36.48] MW with the *cheap* choice already at the achievable floor -- so no
# rating can force a redispatch there without going infeasible; the complementary check is that a
# rating strictly below that floor is correctly reported ``Infeasible`` rather than silently
# accepting a dispatch whose true physical flow exceeds it (exactly what a wrong ``const_k``
# risks: HiGHS is only as good as the row it is handed).


def test_dc_opf_flow_limit_row_forces_a_true_physical_redispatch() -> None:
    """A tight rating on the shifter branch, set strictly inside the achievable flow range (an
    independent ``pf.solve_dc`` readback of the two dispatch extremes), must force ``dc_opf``'s
    LP off the cheap-only optimum and keep the *true* physical flow within it. This exercises the
    row's own ``const_k`` directly (T1) -- unlike the two tests above, which check the *derived*
    flow computed after the fact from a solved dispatch (T2/T3, a different code path) -- since a
    wrong ``const_k`` would let the LP dispatch a physically-infeasible flow through the rated
    branch without ever showing up in the LP's own reported status.
    """
    shift_deg = -7.0
    net = shifter_loop_network(shift_deg)
    flow_cheap = _oracle_flows(net, {"g1": 100.0, "g3": 0.0})["t12"]
    flow_dear = _oracle_flows(net, {"g1": 0.0, "g3": 100.0})["t12"]
    rating_mva = (abs(flow_cheap) + abs(flow_dear)) / 2.0  # strictly between the two extremes

    unrated_result = solve_dc_opf(net)
    assert unrated_result.status == "Optimal", unrated_result.message
    unrated_dispatch = {g.id: g.p_mw for g in unrated_result.generators}

    rated_net = shifter_loop_network(shift_deg, t12_rating_mva=rating_mva)
    result = solve_dc_opf(rated_net)
    assert result.status == "Optimal", result.message
    dispatch = {g.id: g.p_mw for g in result.generators}
    # the rating actually re-dispatched -- the cheap-only optimum is no longer feasible
    assert dispatch != pytest.approx(unrated_dispatch, abs=1e-6)

    true_flow = _oracle_flows(rated_net, dispatch)["t12"]
    assert abs(true_flow) <= rating_mva + 1e-6


def test_dc_opf_flow_limit_row_reports_infeasible_below_the_achievable_floor() -> None:
    """At +12 deg the cheapest dispatch already sits at the achievable floor of |t12 flow|
    (3.15 MW): no dispatch can do better. A rating strictly below that floor is therefore
    genuinely infeasible, and the row must say so -- not silently accept a dispatch whose true
    physical flow (an independent ``pf.solve_dc`` readback) exceeds the rating it was given.
    """
    shift_deg = 12.0
    net = shifter_loop_network(shift_deg)
    floor_mva = abs(_oracle_flows(net, {"g1": 100.0, "g3": 0.0})["t12"])

    rated_net = shifter_loop_network(shift_deg, t12_rating_mva=floor_mva * 0.5)
    result = solve_dc_opf(rated_net)
    assert result.status == "Infeasible", (result.status, result.message)


# --- The KCL identity itself: at the shifted bus, inflow - outflow == load -----------------------


@pytest.mark.parametrize("shift_deg", SHIFT_ANGLES_DEG)
@pytest.mark.parametrize("solver", ["dc_opf", "nodal"])
def test_kcl_holds_at_the_shifted_bus(shift_deg: float, solver: str) -> None:
    """At b2 (the shifter's "to" end and the load bus): inflow via t12 minus outflow via l23
    must equal the 100 MW load -- violated by ~87 MW pre-fix (M8 finding F1 / A19) on a
    generously-rated shifter exactly like this fixture's default."""
    net = shifter_loop_network(shift_deg)
    if solver == "dc_opf":
        result = solve_dc_opf(net)
    else:
        result = solve_nodal(Scenario(network=net))
    assert result.status == "Optimal", result.message
    flows = {b.id: b.p_from_mw for b in result.branches}
    inflow_via_t12 = flows["t12"]  # b1 -> b2, positive = flowing into b2
    outflow_via_l23 = flows["l23"]  # b2 -> b3, positive = flowing out of b2
    assert inflow_via_t12 - outflow_via_l23 == pytest.approx(LOAD_P_MW, abs=1e-9)
