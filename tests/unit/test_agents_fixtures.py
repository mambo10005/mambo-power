"""Unit test for ``tests._agents``: the M7 strategic-bidding fixture builder (wave-07 spec W7;
AC-4's and AC-5's fixture half).

``market.agents.solve_agents`` -- the fixed-point loop itself -- does not exist yet (that is
S4); this module verifies the three fixtures' *economics* by clearing them directly through
``tests._agents.clear_with_offers`` (``opf.dc_opf`` on hand-set offers, the same path
``market.nodal.solve_nodal`` uses). No iteration count, convergence flag or termination reason
is measured anywhere in this file -- those belong to S4/S5's own tests on the actual loop.

Every "measured" figure below was re-measured through this repo's own ``dc_opf`` (not the
Step-2 research probes' ad hoc ``Market`` class) before being pinned; see
``.bionic/docs/record/m7-s3-report.md`` for the full table against the spec's own numbers.

**Solver-residual tolerance.** HiGHS returns each of these LPs solved to its own default
tolerance, not bit-exactly at the analytic optimum: price is typically off by ~2e-4 $/MWh and
free (non-bound) dispatch by ~2e-3 MW, so a profit figure in the thousands is typically off by a
few cents. :data:`PRICE_ABS_TOL`/:data:`DISPATCH_ABS_TOL`/:data:`PROFIT_ABS_TOL` are set well
above that measured residual and well inside the two-decimal-place precision the spec's own
table states its numbers to -- loose enough to survive the residual, tight enough that a real
modelling error (wrong bus, wrong sign, double-counted generator) still fails the assertion.
"""

from __future__ import annotations

import pytest

from mambo_power.model import PolynomialBid
from mambo_power.numerics import NetworkArrays
from tests._agents import (
    DUOPOLY_P_MAX_MW,
    LOAD_P_MAX_MW,
    RIVAL_TRUE_COST,
    STRATEGIC_P_MAX_MW,
    STRATEGIC_TRUE_COST,
    clear_with_offers,
    duopoly_network,
    non_pivotal_control_network,
    smooth_pivotal_network,
)

PRICE_ABS_TOL = 0.01
DISPATCH_ABS_TOL = 0.01
PROFIT_ABS_TOL = 0.5


def _dispatch(net, sol, gen_id: str) -> float:
    """``sol.dispatch_mw`` picked out by ``gen_id`` -- ``dc_opf``'s own generator order,
    recomputed from ``net`` the same way ``clear_with_offers`` built it (``net`` is never
    mutated by a solve, so this is safe to redo)."""
    i = NetworkArrays.from_network(net).gen_ids.index(gen_id)
    return float(sol.dispatch_mw[i])


def _price(sol) -> float:
    return float(sol.duals.balance)


def _profit(net, sol, gen_id: str, true_cost: float) -> float:
    return (_price(sol) - true_cost) * _dispatch(net, sol, gen_id)


# -- smooth pivotal (spec AC-4) -------------------------------------------------------------


def test_smooth_pivotal_has_no_competing_unit() -> None:
    """The smoothness is the point (module docstring in ``tests/_agents.py``, spec AC-4/Not
    Doing): exactly one generator, nothing between the strategic unit's cost and its peak."""
    net = smooth_pivotal_network()
    assert len(net.generators) == 1


def test_smooth_pivotal_true_cost_offer_reproduces_the_competitive_result() -> None:
    """Spec table: true-cost offer -> price $20.00, dispatch 800.00 MW, profit $0.06."""
    net = smooth_pivotal_network()
    sol = clear_with_offers(net, {})
    assert sol.status == "Optimal"
    assert _price(sol) == pytest.approx(20.0, abs=PRICE_ABS_TOL)
    assert _dispatch(net, sol, "strategic") == pytest.approx(800.0, abs=DISPATCH_ABS_TOL)
    assert _profit(net, sol, "strategic", STRATEGIC_TRUE_COST) == pytest.approx(
        0.06, abs=PROFIT_ABS_TOL
    )


def test_smooth_pivotal_offer_60_reaches_the_closed_form_peak() -> None:
    """Spec table: strategic offers $60.00 -> price $60.00, dispatch 400.00 MW, profit
    $15,999.98 -- against the closed-form $16,000.00 pinned independently in
    ``test_smooth_pivotal_closed_form_peak_matches_the_spec_derivation`` below."""
    net = smooth_pivotal_network()
    sol = clear_with_offers(net, {"strategic": 60.0})
    assert sol.status == "Optimal"
    assert _price(sol) == pytest.approx(60.0, abs=PRICE_ABS_TOL)
    assert _dispatch(net, sol, "strategic") == pytest.approx(400.0, abs=DISPATCH_ABS_TOL)
    assert _profit(net, sol, "strategic", STRATEGIC_TRUE_COST) == pytest.approx(
        15_999.98, abs=PROFIT_ABS_TOL
    )


def test_smooth_pivotal_closed_form_peak_matches_the_spec_derivation() -> None:
    """AC-4's own closed form, checked independently of any solve: profit
    ``(price - 20)(1000 - 10*price)`` is maximised where its derivative ``1200 - 20*price`` is
    zero, i.e. ``price=$60``, ``q=1000-10*60=400``, ``profit=(60-20)*400=$16,000``. The
    solver's measured $15,999.98 (immediately above) against this $16,000.00 is the agreement
    AC-4 asks to be pinned, not a discrepancy to explain away.
    """

    def profit(price: float) -> float:
        return (price - STRATEGIC_TRUE_COST) * (LOAD_P_MAX_MW - 10.0 * price)

    peak_price = 60.0
    assert profit(peak_price) == pytest.approx(16_000.0, abs=1e-9)
    assert (peak_price - 20.0) * 400.0 == pytest.approx(16_000.0, abs=1e-9)
    # A genuine peak, not a plateau: moving off it either way strictly loses profit.
    assert profit(peak_price - 1.0) < profit(peak_price)
    assert profit(peak_price + 1.0) < profit(peak_price)


# -- non-pivotal control (spec AC-4's paired control) ----------------------------------------


def test_control_true_cost_offer_matches_the_pivotal_baseline() -> None:
    """Spec table: true-cost offer -> price $20.00, profit $0.06 -- same as the pivotal
    fixture's own true-cost baseline, since the rival is priced above and never binds there."""
    net = non_pivotal_control_network()
    sol = clear_with_offers(net, {})
    assert sol.status == "Optimal"
    assert _price(sol) == pytest.approx(20.0, abs=PRICE_ABS_TOL)
    assert _profit(net, sol, "strategic", STRATEGIC_TRUE_COST) == pytest.approx(
        0.06, abs=PROFIT_ABS_TOL
    )


def test_control_offer_21_50_gain_is_real_and_far_smaller_than_the_pivotal_gain() -> None:
    """Spec table: strategic offers $21.50 -> gain $1,177.50 against the pivotal $15,999.92
    (13.6x smaller) -- stopped by the rival, not by demand. Both gains are computed here from
    the same true-cost baseline each fixture measures above, not hardcoded separately."""
    pivotal_net = smooth_pivotal_network()
    baseline = clear_with_offers(pivotal_net, {})
    peak = clear_with_offers(pivotal_net, {"strategic": 60.0})
    pivotal_gain = _profit(pivotal_net, peak, "strategic", STRATEGIC_TRUE_COST) - _profit(
        pivotal_net, baseline, "strategic", STRATEGIC_TRUE_COST
    )
    assert pivotal_gain == pytest.approx(15_999.92, abs=PROFIT_ABS_TOL)

    control_net = non_pivotal_control_network()
    control_baseline = clear_with_offers(control_net, {})
    control_stop = clear_with_offers(control_net, {"strategic": 21.5})
    control_gain = _profit(control_net, control_stop, "strategic", STRATEGIC_TRUE_COST) - _profit(
        control_net, control_baseline, "strategic", STRATEGIC_TRUE_COST
    )
    assert control_gain == pytest.approx(1_177.50, abs=PROFIT_ABS_TOL)

    assert 0.0 < control_gain < pivotal_gain
    assert pivotal_gain / control_gain == pytest.approx(13.6, abs=0.1)


# -- two-reactive-agent duopoly (spec AC-5) ---------------------------------------------------


def test_duopoly_true_cost_offers_split_evenly() -> None:
    """Spec table: true-cost offers -> price $40.00, dispatch [300, 300], joint profit
    $11,999.96."""
    net = duopoly_network()
    sol = clear_with_offers(net, {})
    assert sol.status == "Optimal"
    assert _price(sol) == pytest.approx(40.0, abs=PRICE_ABS_TOL)
    assert _dispatch(net, sol, "agent_a") == pytest.approx(300.0, abs=DISPATCH_ABS_TOL)
    assert _dispatch(net, sol, "agent_b") == pytest.approx(300.0, abs=DISPATCH_ABS_TOL)
    joint = _profit(net, sol, "agent_a", STRATEGIC_TRUE_COST) + _profit(
        net, sol, "agent_b", STRATEGIC_TRUE_COST
    )
    assert joint == pytest.approx(11_999.96, abs=PROFIT_ABS_TOL)


def test_duopoly_both_offer_60_matches_the_measured_settling_point() -> None:
    """Spec table (AC-5(i)): the loop's own climb settles both agents at offer $60.00 -- price
    $60.00, joint profit $15,999.98 (the loop itself, and the round count/amplitude that gets it
    there, are S4/S5's rows; this only checks that *clearing* at that settled offer reproduces
    the spec's own figure)."""
    net = duopoly_network()
    sol = clear_with_offers(net, {"agent_a": 60.0, "agent_b": 60.0})
    assert sol.status == "Optimal"
    assert _price(sol) == pytest.approx(60.0, abs=PRICE_ABS_TOL)
    joint = _profit(net, sol, "agent_a", STRATEGIC_TRUE_COST) + _profit(
        net, sol, "agent_b", STRATEGIC_TRUE_COST
    )
    assert joint == pytest.approx(15_999.98, abs=PROFIT_ABS_TOL)


# -- sabotage sweep: each fixture's defining parameters really are load-bearing ---------------
#
# Standing rule (six waves deep): perturb each fixture's defining parameter and show the
# residual that moves, proving the pinned numbers above aren't vacuous. Every expected value
# below was itself measured through clear_with_offers on the sabotaged network (not guessed),
# recorded alongside the closed-form arithmetic that predicts it.


def test_sabotage_smooth_pivotal_capacity_forces_price_above_the_unconstrained_peak() -> None:
    """Cut the strategic unit's cap 900 -> 300 MW. With no rival to fill the gap, the market
    can't reach the unconstrained 400 MW peak at $60 -- demand's own curve pushes the price up
    to clear at the 300 MW cap instead: q(price)=1000-10*price=300 => price=$70.00, profit
    (70-20)*300=$15,000.00. This breaks
    test_smooth_pivotal_offer_60_reaches_the_closed_form_peak's price/dispatch/profit trio
    (price $60.00 -> $70.00, dispatch 400 -> 300, profit $15,999.98 -> $15,000.00) were it run
    against this network instead."""
    net = smooth_pivotal_network(p_max_mw=300.0)
    sol = clear_with_offers(net, {"strategic": 60.0})
    assert sol.status == "Optimal"
    assert _price(sol) == pytest.approx(70.0, abs=PRICE_ABS_TOL)
    assert _dispatch(net, sol, "strategic") == pytest.approx(300.0, abs=DISPATCH_ABS_TOL)
    assert _profit(net, sol, "strategic", STRATEGIC_TRUE_COST) == pytest.approx(
        15_000.0, abs=PROFIT_ABS_TOL
    )


def test_sabotage_smooth_pivotal_true_cost_shifts_the_closed_form_peak() -> None:
    """Raise the strategic unit's true cost 20 -> $25/MWh. The closed-form peak moves with it:
    profit ``(price-25)(1000-10*price)`` peaks where ``1250-20*price=0`` => price=$62.50,
    q=375, profit=(62.50-25)*375=$14,062.50 -- not the unperturbed fixture's $60.00/400/$16,000.
    This breaks test_smooth_pivotal_closed_form_peak_matches_the_spec_derivation's own $16,000
    figure and moves the true-cost-offer clearing price (test_smooth_pivotal_true_cost_offer_
    reproduces_the_competitive_result's $20.00) to $25.00, dispatch 800 -> 750."""
    net = smooth_pivotal_network(true_cost=25.0)

    baseline = clear_with_offers(net, {})
    assert _price(baseline) == pytest.approx(25.0, abs=PRICE_ABS_TOL)
    assert _dispatch(net, baseline, "strategic") == pytest.approx(750.0, abs=DISPATCH_ABS_TOL)

    def profit(price: float) -> float:
        return (price - 25.0) * (LOAD_P_MAX_MW - 10.0 * price)

    assert profit(62.5) == pytest.approx(14_062.5, abs=1e-9)

    peak = clear_with_offers(net, {"strategic": 62.5})
    assert _price(peak) == pytest.approx(62.5, abs=PRICE_ABS_TOL)
    assert _dispatch(net, peak, "strategic") == pytest.approx(375.0, abs=DISPATCH_ABS_TOL)
    assert _profit(net, peak, "strategic", 25.0) == pytest.approx(14_062.5, abs=PROFIT_ABS_TOL)


def test_sabotage_control_rival_undercutting_the_offer_zeroes_strategic_profit() -> None:
    """Cut the rival's true cost 22 -> $20.50/MWh, now *below* the strategic unit's $21.50 stop
    price. The rival alone can now serve the whole clearing quantity below that offer, so the
    strategic unit is priced out entirely: dispatch 0.00 MW, profit $0.00 -- not the unperturbed
    control fixture's dispatch ~785 MW / gain $1,177.50
    (test_control_offer_21_50_gain_is_real_and_far_smaller_than_the_pivotal_gain). The residual
    that moves is the strategic unit's own dispatch, all the way to its floor."""
    net = non_pivotal_control_network(rival_true_cost=20.5)
    sol = clear_with_offers(net, {"strategic": 21.5})
    assert sol.status == "Optimal"
    assert _price(sol) == pytest.approx(20.5, abs=PRICE_ABS_TOL)
    assert _dispatch(net, sol, "strategic") == pytest.approx(0.0, abs=DISPATCH_ABS_TOL)
    assert _profit(net, sol, "strategic", STRATEGIC_TRUE_COST) == pytest.approx(
        0.0, abs=PROFIT_ABS_TOL
    )


def test_sabotage_duopoly_capacity_changes_the_split_not_the_joint_total() -> None:
    """Cut agent_a's cap 300 -> 100 MW, both still offering $60. Demand still clears the same
    400 MW total at the same $60.00 price (agent_b's own 300 MW cap covers the shortfall
    exactly), so joint profit is unchanged at ~$15,999.98 -- but the *split*
    test_duopoly_both_offer_60_matches_the_measured_settling_point's implicit 200/200 (from
    test_duopoly_true_cost_offers_split_evenly's dispatch shape) becomes 100/300. The residual
    that moves is the per-agent dispatch, not the joint total -- proving the fixture's
    ``DUOPOLY_P_MAX_MW`` actually constrains something rather than being decorative."""
    net = duopoly_network(gen_a_id="agent_a", gen_b_id="agent_b", p_max_mw=DUOPOLY_P_MAX_MW)
    for gen in net.generators:
        if gen.id == "agent_a":
            gen.p_max_mw = 100.0
    sol = clear_with_offers(net, {"agent_a": 60.0, "agent_b": 60.0})
    assert sol.status == "Optimal"
    assert _price(sol) == pytest.approx(60.0, abs=PRICE_ABS_TOL)
    assert _dispatch(net, sol, "agent_a") == pytest.approx(100.0, abs=DISPATCH_ABS_TOL)
    assert _dispatch(net, sol, "agent_b") == pytest.approx(300.0, abs=DISPATCH_ABS_TOL)
    joint = _profit(net, sol, "agent_a", STRATEGIC_TRUE_COST) + _profit(
        net, sol, "agent_b", STRATEGIC_TRUE_COST
    )
    assert joint == pytest.approx(15_999.98, abs=PROFIT_ABS_TOL)


def test_sabotage_demand_curve_shifts_the_smooth_pivotal_closed_form_peak() -> None:
    """Flatten the shared bid curve's intercept 100 -> 80 (``q(price) = 800 - 10*price`` instead
    of 1000 - 10*price). The closed-form peak moves: profit ``(price-20)(800-10*price)`` peaks
    where ``1000-20*price=0`` => price=$50.00, q=300, profit=(50-20)*300=$9,000.00 -- not the
    shared-curve fixture's $60.00/400/$16,000. This also moves the true-cost-offer dispatch
    (800 -> 600 MW at the same $20.00 price), proving :data:`tests._agents.DEMAND_BID` is what
    the whole module's numbers are anchored to, not an inert default."""
    flatter_bid = PolynomialBid(coefficients=[-0.05, 80.0, 0.0])
    net = smooth_pivotal_network()
    net.loads[0].bid = flatter_bid

    baseline = clear_with_offers(net, {})
    assert _price(baseline) == pytest.approx(20.0, abs=PRICE_ABS_TOL)
    assert _dispatch(net, baseline, "strategic") == pytest.approx(600.0, abs=DISPATCH_ABS_TOL)

    def profit(price: float) -> float:
        return (price - 20.0) * (800.0 - 10.0 * price)

    assert profit(50.0) == pytest.approx(9_000.0, abs=1e-9)

    peak = clear_with_offers(net, {"strategic": 50.0})
    assert _price(peak) == pytest.approx(50.0, abs=PRICE_ABS_TOL)
    assert _dispatch(net, peak, "strategic") == pytest.approx(300.0, abs=DISPATCH_ABS_TOL)
    assert _profit(net, peak, "strategic", STRATEGIC_TRUE_COST) == pytest.approx(
        9_000.0, abs=PROFIT_ABS_TOL
    )


# -- overlay never mutates the network (spec AC-2's own guarantee, checked at this fixture's
#    own scale rather than assumed) ------------------------------------------------------------


def test_clear_with_offers_does_not_mutate_the_network() -> None:
    """``clear_with_offers`` overlays the offer as an argument to ``dc_opf``
    (``tests/_agents.py``'s own docstring); it must not write through to ``Generator.cost`` --
    spec AC-2's guarantee, worth checking directly at this fixture's own scale rather than
    assumed true because a later slice's own AC-2 test says so."""
    net = smooth_pivotal_network()
    before = net.model_dump_json()
    clear_with_offers(net, {"strategic": 60.0})
    assert net.model_dump_json() == before
    assert net.generators[0].cost.coefficients == [STRATEGIC_TRUE_COST, 0.0]


def test_non_pivotal_control_rival_defaults_match_the_module_constants() -> None:
    """Guards the factory defaults themselves against silent drift: the control fixture's rival
    is :data:`RIVAL_TRUE_COST` (\\$22), and both units are :data:`STRATEGIC_P_MAX_MW`\\ /
    :data:`RIVAL_P_MAX_MW` (900 MW each) -- the exact shape spec AC-4's paired control names."""
    net = non_pivotal_control_network()
    rival = next(g for g in net.generators if g.id == "rival")
    strategic = next(g for g in net.generators if g.id == "strategic")
    assert rival.cost.coefficients == [RIVAL_TRUE_COST, 0.0]
    assert rival.p_max_mw == pytest.approx(900.0)
    assert strategic.p_max_mw == pytest.approx(STRATEGIC_P_MAX_MW)
