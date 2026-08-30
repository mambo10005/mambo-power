"""M8 finding F1 / A19, critic finding 1: the DC-OPF phase-shifter flow defect's two sibling
copies in ``opf.multiperiod`` and ``opf.redispatch``, fixed (task-shifter-flow-fix.plan.md
T6/T7/T8).

``tests/unit/test_shifter_flow_fix.py`` (T4) proved the fix for ``opf.dc_opf``, ``opf.
solve_dc_opf`` and ``market._clearing`` (T1/T2/T3). The Step-6 critic found two more sites
carrying an *independent* copy of the identical missing ``- p_shift`` term, never touched by
those three fixes and never imported ``numerics.bbus.p_shift`` at all:
``opf.multiperiod.multiperiod_dc_opf``'s per-period flow-limit row constant, and ``opf.
redispatch.redispatch_dc_opf``'s own flow-limit row constant *and* its derived, reported
``branch_flow_mw``. Both reach the public API directly -- ``market.solve_multiperiod`` (the false
``Infeasible`` failure mode) and ``market.solve_zonal``'s ``branches[].p_from_mw`` (measured
81.4 MW off ``pf.solve_dc`` by the critic, at an ``Optimal`` dispatch).

This module proves, independently for each of the two newly-touched sites and the two public
entry points that surface them, that the fixed formula now reproduces ``pf.solve_dc``. Two red
tests near the bottom reproduce the critic's own numbers by name (the 81.4 MW redispatch gap and
the false-Infeasible multiperiod report) so the fix's own regression against the critic's
reproduction is explicit rather than merely subsumed by the tolerance checks above it.

``MarketMultiperiodResult`` carries no branch-flow field at all (unlike ``OpfDcResult``/
``MarketZonalResult`` -- a pre-existing gap the audit's Walk noted as "minor friction, not
fixed" for the sibling ``OpfBranchFlowResult.p_to_mw``, not something this task's scope touches),
so ``market.solve_multiperiod``'s coverage here is its dispatch/status, not a branch-flow field
that does not exist; ``opf.multiperiod_dc_opf``'s own flow-limit rows are proved directly against
``pf.solve_dc`` at the array level instead, where the row math actually lives.
"""

from __future__ import annotations

import numpy as np
import pytest

from mambo_power import pf
from mambo_power.market.multiperiod import solve_multiperiod
from mambo_power.market.nodal import solve_nodal
from mambo_power.market.zonal import solve_zonal
from mambo_power.model import Network, Scenario
from mambo_power.numerics import NetworkArrays
from mambo_power.numerics.bbus import flow_from_ptdf
from mambo_power.opf import gen_cost_coeffs
from mambo_power.opf.multiperiod import multiperiod_dc_opf
from mambo_power.opf.redispatch import redispatch_dc_opf
from tests._shifter import (
    LOAD_P_MW,
    dispatched_network,
    shifter_loop_network,
    zoned_shifter_loop_network,
)

SHIFT_ANGLES_DEG = [-7.0, 12.0]


def _network_with_load(net: Network, load_mw: float) -> Network:
    """Deep copy of ``net`` with the fixture's single load's ``p_mw`` overwritten -- the
    load-side counterpart of ``tests._shifter.dispatched_network``."""
    copy = net.model_copy(deep=True)
    assert len(copy.loads) == 1, "helper assumes tests._shifter's single-load fixture"
    copy.loads[0].p_mw = load_mw
    return copy


def _oracle_flow(net: Network, load_mw: float, dispatch: dict[str, float]) -> dict[str, float]:
    """``pf.solve_dc`` readback of ``dispatch`` on ``net`` with its load overridden to
    ``load_mw``, id-keyed -- the multi-period generalisation of
    ``test_shifter_flow_fix.py``'s ``_oracle_flows``."""
    combined = dispatched_network(_network_with_load(net, load_mw), dispatch)
    oracle = pf.solve_dc(combined)
    assert oracle.converged
    return {b.id: b.p_from_mw for b in oracle.branches}


# ================================================================================================
# T6 -- opf.multiperiod.multiperiod_dc_opf, array level
# ================================================================================================


@pytest.mark.parametrize("shift_deg", SHIFT_ANGLES_DEG)
def test_multiperiod_dc_opf_derived_flows_match_pf_solve_dc_at_every_period(
    shift_deg: float,
) -> None:
    """Two periods with genuinely different loads (60, 140 MW; neither rating binds), so the
    per-period loop's own ``p_shift_mw`` fold (T6) is exercised twice with different fixed-load
    data at each iteration, not just once and reused. At each period ``t`` independently, the
    flow reconstructed from that period's own solved dispatch (``flow_from_ptdf``, the same
    identity the row's own ``const[t]`` is built from) matches an independent ``pf.solve_dc``
    readback of the same dispatch and load.
    """
    period_loads_mw = [60.0, 140.0]
    net = shifter_loop_network(shift_deg)
    arr = NetworkArrays.from_network(net)
    cost_coeffs, pwl_costs = gen_cost_coeffs(net, arr)
    period_load_mw = np.array([[load] for load in period_loads_mw], dtype=np.float64)

    sol = multiperiod_dc_opf(
        arr, cost_coeffs, n_periods=2, period_load_mw=period_load_mw, pwl_costs=pwl_costs or None
    )
    assert sol.status == "Optimal", sol.message

    g_shunt_mw = arr.g_shunt_pu * arr.base_mva
    for t, load_mw in enumerate(period_loads_mw):
        dispatch = {gid: float(sol.dispatch_mw[t, i]) for i, gid in enumerate(arr.gen_ids)}
        gen_by_bus = np.bincount(arr.gen_bus, weights=sol.dispatch_mw[t], minlength=arr.n_bus)
        p_load_mw = np.zeros(arr.n_bus)
        p_load_mw[arr.load_bus[0]] = load_mw
        injection_mw = gen_by_bus - p_load_mw - g_shunt_mw
        computed = flow_from_ptdf(sol.ptdf, injection_mw, arr)

        oracle = _oracle_flow(net, load_mw, dispatch)
        for k, branch_id in enumerate(arr.branch_ids):
            assert computed[k] == pytest.approx(oracle[branch_id], abs=1e-6), (t, branch_id)


def test_multiperiod_dc_opf_flow_limit_row_forces_true_physical_redispatch_every_period() -> None:
    """Generalises ``test_shifter_flow_fix.py``'s
    ``test_dc_opf_flow_limit_row_forces_a_true_physical_redispatch`` (T1) to a two-period
    horizon with a *different* load each period (60, 100 MW) and one shared rating (ratings are
    horizon-invariant, module docstring) chosen -- via an independent ``pf.solve_dc`` readback of
    each period's own achievable extremes -- strictly inside *both* periods' achievable ranges.
    That forces the LP off the cheap-only optimum in both periods simultaneously; each period's
    resulting dispatch is independently read back through ``pf.solve_dc`` at its own load and
    checked against the shared rating. This exercises the row's own ``const[t]`` at ``t=0`` *and*
    ``t=1`` with different data, unlike the derived-flow test above, which only proves the
    solved dispatch's after-the-fact flow is right, not that the row forcing it there was.
    """
    shift_deg = -7.0
    period_loads_mw = [60.0, 100.0]
    net = shifter_loop_network(shift_deg)

    # per-period achievable |t12 flow| range (an independent pf.solve_dc readback at each
    # period's own load, exactly T1's own derivation generalised over periods).
    ranges = []
    for load_mw in period_loads_mw:
        flow_cheap = abs(_oracle_flow(net, load_mw, {"g1": load_mw, "g3": 0.0})["t12"])
        flow_dear = abs(_oracle_flow(net, load_mw, {"g1": 0.0, "g3": load_mw})["t12"])
        ranges.append((min(flow_cheap, flow_dear), max(flow_cheap, flow_dear)))
    intersection_lo = max(lo for lo, _ in ranges)
    intersection_hi = min(hi for _, hi in ranges)
    assert intersection_lo < intersection_hi, (
        f"fixture choice must give overlapping per-period ranges, got {ranges}"
    )
    rating_mva = (intersection_lo + intersection_hi) / 2.0

    rated_net = shifter_loop_network(shift_deg, t12_rating_mva=rating_mva)
    arr = NetworkArrays.from_network(rated_net)
    cost_coeffs, pwl_costs = gen_cost_coeffs(rated_net, arr)
    period_load_mw = np.array([[load] for load in period_loads_mw], dtype=np.float64)

    unrated_sol = multiperiod_dc_opf(
        NetworkArrays.from_network(net),
        cost_coeffs,
        n_periods=2,
        period_load_mw=period_load_mw,
        pwl_costs=pwl_costs or None,
    )
    assert unrated_sol.status == "Optimal", unrated_sol.message

    sol = multiperiod_dc_opf(
        arr, cost_coeffs, n_periods=2, period_load_mw=period_load_mw, pwl_costs=pwl_costs or None
    )
    assert sol.status == "Optimal", sol.message
    # the rating actually re-dispatched, at both periods -- the cheap-only optimum (both
    # periods' flow_cheap sits above the shared rating, by construction of the intersection) is
    # no longer feasible.
    assert not np.allclose(sol.dispatch_mw, unrated_sol.dispatch_mw, atol=1e-6)

    for t, load_mw in enumerate(period_loads_mw):
        dispatch = {gid: float(sol.dispatch_mw[t, i]) for i, gid in enumerate(arr.gen_ids)}
        true_flow = abs(_oracle_flow(rated_net, load_mw, dispatch)["t12"])
        assert true_flow <= rating_mva + 1e-6, t


# ================================================================================================
# T7 -- opf.redispatch.redispatch_dc_opf, array level
# ================================================================================================


@pytest.mark.parametrize("shift_deg", SHIFT_ANGLES_DEG)
@pytest.mark.parametrize("p0", [{"g1": 100.0, "g3": 0.0}, {"g1": 0.0, "g3": 100.0}])
def test_redispatch_dc_opf_branch_flow_matches_pf_solve_dc(
    shift_deg: float, p0: dict[str, float]
) -> None:
    """``redispatch_dc_opf.branch_flow_mw`` (T7's ``flow_from_ptdf`` call) matches an independent
    ``pf.solve_dc`` readback of the same final dispatch, from two unrelated starting points --
    the all-cheap and all-dear extremes -- mirroring ``opf.redispatch``'s own module docstring
    convention of checking the theorem from two starting points."""
    net = shifter_loop_network(shift_deg)
    arr = NetworkArrays.from_network(net)
    cost_coeffs, _ = gen_cost_coeffs(net, arr)
    p0_mw = np.array([p0[gid] for gid in arr.gen_ids], dtype=np.float64)

    sol = redispatch_dc_opf(arr, cost_coeffs, p0_mw)
    assert sol.status == "Optimal", sol.message

    dispatch = {gid: float(sol.dispatch_mw[i]) for i, gid in enumerate(arr.gen_ids)}
    oracle = _oracle_flow(net, LOAD_P_MW, dispatch)
    for k, branch_id in enumerate(arr.branch_ids):
        assert sol.branch_flow_mw[k] == pytest.approx(oracle[branch_id], abs=1e-6), branch_id


def test_redispatch_dc_opf_flow_limit_row_forces_a_true_physical_redispatch() -> None:
    """T1's row-forcing test (``test_shifter_flow_fix.py``), generalised to ``redispatch_dc_opf``:
    starting from the all-cheap zonal point ``p0 = [100, 0]`` (which violates a rating strictly
    inside the achievable range), the redispatch LP must move off ``p0`` and land the *true*
    physical flow (an independent ``pf.solve_dc`` readback) within the rating -- exercising
    T7's own ``const`` fold directly, the way the derived-flow test above does not.
    """
    shift_deg = -7.0
    net = shifter_loop_network(shift_deg)
    flow_cheap = abs(_oracle_flow(net, LOAD_P_MW, {"g1": 100.0, "g3": 0.0})["t12"])
    flow_dear = abs(_oracle_flow(net, LOAD_P_MW, {"g1": 0.0, "g3": 100.0})["t12"])
    rating_mva = (flow_cheap + flow_dear) / 2.0  # strictly between the two extremes

    rated_net = shifter_loop_network(shift_deg, t12_rating_mva=rating_mva)
    arr = NetworkArrays.from_network(rated_net)
    cost_coeffs, _ = gen_cost_coeffs(rated_net, arr)
    p0_mw = np.array([100.0, 0.0])  # the all-cheap point, which violates rating_mva

    sol = redispatch_dc_opf(arr, cost_coeffs, p0_mw)
    assert sol.status == "Optimal", sol.message
    # the rating actually redispatched away from p0
    assert not np.allclose(sol.dispatch_mw, p0_mw, atol=1e-6)

    dispatch = {gid: float(sol.dispatch_mw[i]) for i, gid in enumerate(arr.gen_ids)}
    true_flow = abs(_oracle_flow(rated_net, LOAD_P_MW, dispatch)["t12"])
    assert true_flow <= rating_mva + 1e-6


# ================================================================================================
# T8.1 -- market.solve_zonal / market.solve_multiperiod, the public entry points
# ================================================================================================


@pytest.mark.parametrize("shift_deg", SHIFT_ANGLES_DEG)
def test_solve_zonal_branch_flows_match_pf_solve_dc(shift_deg: float) -> None:
    """``market.solve_zonal``'s public ``branches[].p_from_mw`` -- sourced directly from
    ``redispatch_dc_opf.branch_flow_mw`` (``market/zonal.py``'s own composition, critic finding
    1) -- matches an independent ``pf.solve_dc`` readback of the final dispatch. A single zone
    holding every bus (``tests._shifter.zoned_shifter_loop_network``) needs no corridor, since a
    corridor-less single-zone clearing is a legitimate copper-plate design (``solve_zonal``'s own
    docstring)."""
    net = zoned_shifter_loop_network(shift_deg)
    result = solve_zonal(Scenario(network=net))
    assert result.status == "Optimal", result.message

    dispatch = {row.id: row.p_mw for row in result.generators_final}
    oracle = _oracle_flow(net, LOAD_P_MW, dispatch)
    by_id = {row.id: row.p_from_mw for row in result.branches}
    for branch_id, expected in oracle.items():
        assert by_id[branch_id] == pytest.approx(expected, abs=1e-6), branch_id


@pytest.mark.parametrize("shift_deg", SHIFT_ANGLES_DEG)
def test_solve_multiperiod_matches_solve_nodal_dispatch_on_shifter_network(
    shift_deg: float,
) -> None:
    """A period-less ``Scenario`` reduces ``solve_multiperiod`` to ``T=1`` with
    ``period_load_mw=None``, which is *literally* ``solve_nodal``'s own arithmetic (``opf.
    multiperiod``'s module docstring, "A period-less scenario is a one-period horizon" -- wave
    AC-4). ``test_shifter_flow_fix.py`` already proves ``solve_nodal``'s branch flows match
    ``pf.solve_dc`` on this exact fixture; this test closes the loop for
    ``MultiperiodSolution``'s own flow-limit row (which carries no public branch-flow field --
    ``MarketMultiperiodResult`` has none, module docstring) by proving its dispatch is *exactly*
    ``solve_nodal``'s, not merely close."""
    net = shifter_loop_network(shift_deg)
    scenario = Scenario(network=net)
    multi = solve_multiperiod(scenario)
    nodal = solve_nodal(scenario)
    assert multi.status == "Optimal" == nodal.status

    multi_p_mw = {row.id: row.p_mw for row in multi.periods[0].generators}
    nodal_p_mw = {row.id: row.p_mw for row in nodal.generators}
    assert multi_p_mw == nodal_p_mw


# ================================================================================================
# T8.2 -- the critic's own two numbers, reproduced as their own named tests
# ================================================================================================


def test_redispatch_dc_opf_no_longer_reproduces_the_critics_81_4_mw_gap() -> None:
    """The critic's exact reproduction (shifter-critic.md finding 1): ``redispatch_dc_opf`` at
    dispatch ``[100, 0]`` on ``shift_deg=-7`` was off ``pf.solve_dc`` by 81.4 MW on ``t12``
    pre-fix, where ``flow_from_ptdf`` -- the identical identity, correctly applied -- matched to
    1.8e-15 MW. Post-T7-fix, ``redispatch_dc_opf.branch_flow_mw`` itself must match to the same
    precision, since it now calls ``flow_from_ptdf`` directly."""
    net = shifter_loop_network(-7.0)
    arr = NetworkArrays.from_network(net)
    cost_coeffs, _ = gen_cost_coeffs(net, arr)
    p0_mw = np.array([100.0, 0.0])

    sol = redispatch_dc_opf(arr, cost_coeffs, p0_mw)
    assert sol.status == "Optimal", sol.message
    assert sol.dispatch_mw == pytest.approx([100.0, 0.0], abs=1e-6)

    oracle = _oracle_flow(net, LOAD_P_MW, {"g1": 100.0, "g3": 0.0})
    t12_idx = arr.branch_ids.index("t12")
    gap = abs(sol.branch_flow_mw[t12_idx] - oracle["t12"])
    assert gap < 1.0, f"the critic's 81.4 MW gap should be gone, got {gap} MW"
    assert gap == pytest.approx(0.0, abs=1e-6)


def test_solve_multiperiod_no_longer_reproduces_the_critics_false_infeasible() -> None:
    """The critic's exact reproduction (shifter-critic.md finding 1): a shifter network with
    ``t12`` rated 120 MVA is genuinely ``Optimal`` (``dc_opf`` puts the true flow at 107.39 MW,
    comfortably inside), but pre-fix ``multiperiod_dc_opf``'s row believed every achievable
    dispatch put ``t12`` at 155-189 MW and reported a false ``Infeasible``. Reproduced here
    through the public ``market.solve_multiperiod`` entry point (a period-less ``Scenario``,
    ``T=1``, which the critic notes is the code path with no per-solve branch-flow field to have
    instead shown a wrong number -- the LP's wrong constant surfaces only as status/dispatch)."""
    net = shifter_loop_network(-7.0, t12_rating_mva=120.0)
    result = solve_multiperiod(Scenario(network=net))
    assert result.status == "Optimal", (
        f"the critic's false Infeasible should be gone, got {result.status!r}: {result.message}"
    )
