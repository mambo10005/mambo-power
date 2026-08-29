"""``market.agents``: the fixed-point loop, its result, and the cost-source generalisation of
``opf.gen_cost_coeffs`` (wave M7 W3/W4; AC-2 and AC-5).

Every network here comes from ``tests._agents``' three factories -- nothing in this file
hand-assembles a strategic-bidding network, and nothing here mutates one.

**What the two acceptance rows need from this module.** AC-2 is one test, deliberately: the
byte-identity of ``Scenario``/``Network`` across a run and the positive control that the
coefficients the array builder saw *differed* from the true ones are asserted on **the same run**,
because a byte-identity taken from a run in which nothing happened is vacuous. AC-5 is the loop's
own termination in its three shapes -- settled, capped, cycling -- with ``status`` asserted
independently of ``converged`` in every one of them, since one is the LP's verdict and the other
is the loop's.

**Where the numbers come from.** The AC-5(i) figures (84 iterations, offers ``[60.0, 60.0]``,
$60.00, joint profit $15,999.98 against $11,999.96 at true cost, settled amplitude 1.0) were
re-measured through this module's own machinery -- the shipped ``solve_agents`` driving the
shipped ``MarkupStrategy`` over ``tests._agents.duopoly_network()`` -- and agree with the spec's
Step-2 measurement. :data:`PROFIT_ABS_TOL` and :data:`PRICE_ABS_TOL` follow
``tests/unit/test_agents_fixtures.py``'s own reasoning: HiGHS solves each of these LPs to its
default tolerance rather than bit-exactly, so a price is off by ~2e-4 $/MWh and a
four-figure profit by a few cents. The iteration count, the amplitude and the offer levels carry
**no** tolerance at all -- they are exact arithmetic on the step size, and a tolerance on them
would be admitting the one thing the row exists to pin.
"""

from __future__ import annotations

import json

import numpy as np
import pytest
from pydantic import ValidationError

from mambo_power.market import agents as agents_module
from mambo_power.market.agents import MarketAgentsOptions, solve_agents
from mambo_power.market.strategy import (
    GeneratorCost,
    MarkupStrategy,
    Observation,
    PolynomialCost,
    PriceTakerStrategy,
)
from mambo_power.model import PiecewiseCost, Scenario
from mambo_power.numerics import NetworkArrays
from mambo_power.opf import gen_cost_coeffs
from mambo_power.results.agents import AgentOfferResult, MarketAgentsResult
from tests._agents import (
    STRATEGIC_TRUE_COST,
    duopoly_network,
    non_pivotal_control_network,
    smooth_pivotal_network,
)

PRICE_ABS_TOL = 0.01
PROFIT_ABS_TOL = 0.5

STEP = 0.5
"""The AC-5(i) step size. ``offer_tol`` is then ``2 * STEP`` by A9's derivation, not by choice."""

AC5_ITERATIONS = 84
AC5_OFFER = 60.0
AC5_PRICE = 60.0
AC5_JOINT_PROFIT = 15_999.98
AC5_TRUE_COST_JOINT_PROFIT = 11_999.96
AC5_AMPLITUDE = 1.0
AC5_PERIOD = 4


class _Recorder:
    """Wraps a strategy and keeps every offer it returned, in round order.

    The loop's result carries only the **final** round's offers, which is the right shape for a
    result -- but AC-5(i) asserts the *amplitude of the settled oscillation*, which is a property
    of the last few rounds together. Rather than recompute the climb (which would assert the test's
    own arithmetic instead of the loop's), this records what the real strategies really offered
    inside the real run, and the assertions read the tail of that.
    """

    def __init__(self, inner: object) -> None:
        self.inner = inner
        self.offers: list[GeneratorCost] = []
        self.observations: list[Observation] = []

    def offer(self, observation: Observation) -> GeneratorCost:
        """*inner*'s offer, recorded alongside the observation it was made from."""
        self.observations.append(observation)
        made = self.inner.offer(observation)  # type: ignore[attr-defined]
        self.offers.append(made)
        return made


class RaiseWhileAtCapacity:
    """AC-5(ii)'s cycling rule: raise the offer while the agent cleared at its own capacity,
    and drop straight back to true cost the moment it did not.

    Not a shipped :data:`~mambo_power.market.strategy.StrategyConfig` kind and deliberately so --
    it is the non-climbing rule the A4 probe used to characterise a *genuine* cycle, whose
    oscillation spans the whole markup range instead of settling into two steps about an optimum.
    It reaches the loop through ``solve_agents``' in-process ``strategies`` seam, which is what
    the :class:`~mambo_power.market.strategy.Strategy` Protocol is structural for.
    """

    def __init__(self, step: float) -> None:
        self.step = step

    def offer(self, observation: Observation) -> GeneratorCost:
        """True cost in round 0; then up by ``step`` if last round cleared at capacity, else
        back to true cost."""
        true_cost = observation.true_cost
        assert isinstance(true_cost, PolynomialCost)
        previous = observation.previous_round
        if previous is None:
            return true_cost
        assert isinstance(previous.offer, PolynomialCost)
        at_capacity = previous.cleared_mw >= observation.p_max_mw - 1e-6
        level = (
            previous.offer.coefficients[0] + self.step if at_capacity else true_cost.coefficients[0]
        )
        return true_cost.model_copy(update={"coefficients": [level, true_cost.coefficients[1]]})


def _markup_options(*gen_ids: str, step: float = STEP, **kwargs: object) -> MarketAgentsOptions:
    """A markup config for each of *gen_ids*, with A9's derived ``offer_tol`` of ``2 * step``."""
    return MarketAgentsOptions(
        strategies={gen_id: {"kind": "markup", "step": step} for gen_id in gen_ids},
        offer_tol=2.0 * step,
        **kwargs,  # type: ignore[arg-type]
    )


def _level(cost: GeneratorCost) -> float:
    """The $/MWh marginal level of a linear polynomial cost -- every offer in this module's
    fixtures is one."""
    assert isinstance(cost, PolynomialCost)
    return cost.coefficients[0]


def _lmp_at(result: MarketAgentsResult, bus: str) -> float:
    return next(row.lmp for row in result.buses if row.id == bus)


def _profit(result: MarketAgentsResult, *gen_ids: str, true_cost: float) -> float:
    """Joint profit of *gen_ids* at the reported clearing: ``(bus LMP - true MC) * cleared MW``."""
    return sum(
        (_lmp_at(result, row.bus) - true_cost) * row.p_mw
        for row in result.generators
        if row.id in gen_ids
    )


# --------------------------------------------------------------------------------------------
# opf.gen_cost_coeffs -- the cost source (spec A2; the overlay's one and only assembler)
# --------------------------------------------------------------------------------------------


def test_no_cost_source_is_exactly_the_pre_m7_behaviour() -> None:
    """``costs=None`` and an empty mapping both mean "every generator keeps its own cost"."""
    net = non_pivotal_control_network()
    arr = NetworkArrays.from_network(net)
    baseline, baseline_pwl = gen_cost_coeffs(net, arr)
    for costs in (None, {}):
        coeffs, pwl = gen_cost_coeffs(net, arr, costs=costs)
        assert np.array_equal(coeffs, baseline)
        assert pwl == baseline_pwl


def test_the_cost_source_overlays_only_the_generators_it_names() -> None:
    """An offer replaces its own generator's row and leaves every other row at the true cost.

    This is the property that makes the overlay an overlay: the control fixture's rival is a
    price-taker precisely because it is absent from the map, not because anything copied its
    cost across.
    """
    net = non_pivotal_control_network()
    arr = NetworkArrays.from_network(net)
    true_coeffs, _ = gen_cost_coeffs(net, arr)
    offered, _ = gen_cost_coeffs(
        net, arr, costs={"strategic": PolynomialCost(coefficients=[60.0, 0.0])}
    )
    strategic = arr.gen_ids.index("strategic")
    rival = arr.gen_ids.index("rival")
    assert list(offered[strategic]) == [0.0, 60.0, 0.0]
    assert not np.array_equal(offered[strategic], true_coeffs[strategic])
    assert np.array_equal(offered[rival], true_coeffs[rival])


def test_a_piecewise_offer_gets_the_all_zero_row_convention_a_piecewise_cost_gets() -> None:
    """An offer is mapped by the same union-to-coefficients rules a true cost is (A2).

    The generator's own cost is polynomial here, so the all-zero row plus a ``pwl_costs`` entry
    can only have come from the *offer* -- which is the point: a hand-rolled assembler is exactly
    what breaks this convention, and W1(c)'s new guard exists to catch the result.
    """
    net = smooth_pivotal_network()
    arr = NetworkArrays.from_network(net)
    offer = PiecewiseCost(points=[(0.0, 0.0), (900.0, 54_000.0)])
    coeffs, pwl = gen_cost_coeffs(net, arr, costs={"strategic": offer})
    i = arr.gen_ids.index("strategic")
    assert list(coeffs[i]) == [0.0, 0.0, 0.0]
    assert pwl == {i: [(0.0, 0.0), (900.0, 54_000.0)]}


def test_a_cost_source_naming_an_absent_generator_raises_rather_than_doing_nothing() -> None:
    """A cost source entry that could never reach the clearing is a caller mistake, not a no-op."""
    net = smooth_pivotal_network()
    arr = NetworkArrays.from_network(net)
    with pytest.raises(ValueError, match=r'"ghost", which is not in the network'):
        gen_cost_coeffs(net, arr, costs={"ghost": PolynomialCost(coefficients=[1.0, 0.0])})

    out_of_service = net.model_copy(deep=True)
    out_of_service.generators[0].in_service = False
    off_arr = NetworkArrays.from_network(out_of_service)
    with pytest.raises(ValueError, match=r"in the network but not in its arrays"):
        gen_cost_coeffs(
            out_of_service, off_arr, costs={"strategic": PolynomialCost(coefficients=[1.0, 0.0])}
        )


# --------------------------------------------------------------------------------------------
# AC-2 -- the overlay never mutates the network, and the run was not vacuous
# --------------------------------------------------------------------------------------------


def test_ac2_the_network_is_byte_identical_across_a_run_that_really_marked_up(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """AC-2, both clauses, on one run: ``Scenario``/``Network`` come out byte-identical and every
    ``Generator.cost`` is unchanged -- *and* the coefficients handed to the array builder on that
    same run differ from the true ones.

    The two clauses are one test on purpose. Byte-identity alone is satisfied trivially by a run
    in which every agent offered its own cost, so the positive control has to be taken from the
    run being checked, not from a second one.
    """
    net = smooth_pivotal_network()
    scenario = Scenario(network=net)
    before_scenario = scenario.model_dump_json().encode()
    before_network = net.model_dump_json().encode()
    true_costs_before = {gen.id: gen.cost.model_dump_json() for gen in net.generators}

    handed: list[np.ndarray] = []
    real_dc_opf = agents_module.dc_opf

    def capturing_dc_opf(arr, cost_coeffs, options, **kwargs):  # type: ignore[no-untyped-def]
        handed.append(np.array(cost_coeffs, copy=True))
        return real_dc_opf(arr, cost_coeffs, options, **kwargs)

    monkeypatch.setattr(agents_module, "dc_opf", capturing_dc_opf)
    result = solve_agents(scenario, _markup_options("strategic", max_iterations=400))

    # The run did something: every agent ended above its own cost.
    assert result.status == "Optimal"
    assert [_level(row.offer) for row in result.offers] == [AC5_OFFER]
    assert _level(result.offers[0].true_cost) == STRATEGIC_TRUE_COST

    # Clause 1 -- byte-identical, and no Generator.cost moved.
    assert scenario.model_dump_json().encode() == before_scenario
    assert net.model_dump_json().encode() == before_network
    assert {gen.id: gen.cost.model_dump_json() for gen in net.generators} == true_costs_before

    # Clause 2, the paired positive control -- on this same run, what the builder actually saw
    # was not the true costs.
    arr = NetworkArrays.from_network(net)
    true_coeffs, _ = gen_cost_coeffs(net, arr)
    assert len(handed) == result.iterations + 1
    assert np.array_equal(handed[0], true_coeffs), "round 0 offers true cost, by the climb's rule"
    assert not np.array_equal(handed[-1], true_coeffs)
    strategic = arr.gen_ids.index("strategic")
    assert handed[-1][strategic][1] == AC5_OFFER
    assert true_coeffs[strategic][1] == STRATEGIC_TRUE_COST


def test_the_true_cost_reaches_the_strategies_and_the_result_unchanged() -> None:
    """``Observation.true_cost`` and ``AgentOfferResult.true_cost`` are the generator's own cost
    object, not the offer -- the distinction the whole overlay exists to preserve."""
    net = smooth_pivotal_network()
    recorder = _Recorder(MarkupStrategy(step=STEP))
    result = solve_agents(
        Scenario(network=net),
        MarketAgentsOptions(offer_tol=2 * STEP, max_iterations=400),
        strategies={"strategic": recorder},
    )
    true_cost = net.generators[0].cost
    assert all(observation.true_cost == true_cost for observation in recorder.observations)
    assert result.offers[0].true_cost == true_cost
    assert result.offers[0].offer != true_cost


# --------------------------------------------------------------------------------------------
# The loop's own contract: history, order, one settlement
# --------------------------------------------------------------------------------------------


def test_the_loop_hands_every_strategy_a_contiguous_history() -> None:
    """Round ``r``'s observation carries round ``r-1`` and ``r-2``, and nothing else.

    ``Observation``'s own validator rejects a stale pair (S2's F1), which only bites if a loop
    skips or restarts a round. This asserts the loop's side of that contract directly rather than
    trusting that the validator would have caught it: the records' own ``round_index`` values are
    checked against the slot they were put in.
    """
    net = duopoly_network()
    recorders = {gen_id: _Recorder(MarkupStrategy(step=STEP)) for gen_id in ("agent_a", "agent_b")}
    result = solve_agents(
        Scenario(network=net),
        MarketAgentsOptions(offer_tol=2 * STEP, max_iterations=12),
        strategies=dict(recorders),
    )
    for recorder in recorders.values():
        seen = recorder.observations
        assert [observation.round_index for observation in seen] == list(range(len(seen)))
        assert len(seen) == result.iterations + 1
        assert seen[0].previous_round is None and seen[0].two_rounds_ago is None
        assert seen[1].previous_round is not None and seen[1].two_rounds_ago is None
        for r, observation in enumerate(seen[2:], start=2):
            assert observation.previous_round is not None
            assert observation.two_rounds_ago is not None
            assert observation.previous_round.round_index == r - 1
            assert observation.two_rounds_ago.round_index == r - 2


def test_updates_are_simultaneous_not_round_robin() -> None:
    """Every agent moves in every round (W3/A8): each one's round-``r`` offer is computed from
    round ``r-1``'s clearing, before any of them is cleared.

    Under round-robin one of the two symmetric agents would sit still while the other moved, so
    their offer sequences would differ; under simultaneous updates two agents with identical
    costs, capacities and rules produce identical sequences.
    """
    net = duopoly_network()
    recorders = {gen_id: _Recorder(MarkupStrategy(step=STEP)) for gen_id in ("agent_a", "agent_b")}
    solve_agents(
        Scenario(network=net),
        MarketAgentsOptions(offer_tol=2 * STEP, max_iterations=10),
        strategies=dict(recorders),
    )
    a = [_level(offer) for offer in recorders["agent_a"].offers]
    b = [_level(offer) for offer in recorders["agent_b"].offers]
    assert a == b
    assert len(set(a)) > 1, "a run in which nobody ever moved would pass the equality vacuously"


def test_settlement_is_the_final_round_s_alone() -> None:
    """The reported settlement is one clearing's, not a sum over the search that found it.

    Checked against the result's own rows rather than against a recomputed clearing: payment,
    receipts and rent are each recomputed here from the reported dispatch and LMPs, so a total
    accumulated across rounds (or taken from a different round than the dispatch) fails.
    """
    result = solve_agents(
        Scenario(network=duopoly_network()),
        _markup_options("agent_a", "agent_b", max_iterations=400),
    )
    assert result.status == "Optimal"
    payment = sum(_lmp_at(result, row.bus) * row.p_mw for row in result.loads)
    receipts = sum(_lmp_at(result, row.bus) * row.p_mw for row in result.generators)
    assert result.total_load_payment == pytest.approx(payment, abs=1e-9)
    assert result.total_generator_receipts == pytest.approx(receipts, abs=1e-9)
    assert result.congestion_rent == pytest.approx(payment - receipts, abs=1e-9)


def test_branch_rows_mirror_the_nodal_result_s_shape() -> None:
    """One row per branch, in network order, with the same row type ``MarketNodalResult`` uses."""
    net = duopoly_network()
    result = solve_agents(Scenario(network=net), _markup_options("agent_a", max_iterations=400))
    assert [row.id for row in result.branches] == [branch.id for branch in net.branches]
    assert [row.id for row in result.generators] == [gen.id for gen in net.generators]
    assert [row.id for row in result.loads] == [load.id for load in net.loads]
    assert [row.id for row in result.buses] == [bus.id for bus in net.buses]


def test_a_generator_with_no_strategy_is_not_an_agent() -> None:
    """It clears at its own true cost and gets no ``offers`` row -- the control fixture's rival."""
    result = solve_agents(
        Scenario(network=non_pivotal_control_network()),
        _markup_options("strategic", max_iterations=400),
    )
    assert [row.id for row in result.offers] == ["strategic"]
    assert {row.id for row in result.generators} == {"strategic", "rival"}


# --------------------------------------------------------------------------------------------
# A6 -- markup is an identity, not independent content
# --------------------------------------------------------------------------------------------


def test_markup_is_the_identity_in_offer_true_cost_and_cleared_mw() -> None:
    """``markup == offer(cleared_mw) - true_cost(cleared_mw)``, recomputed from the row's own
    other three fields (spec A6)."""
    result = solve_agents(
        Scenario(network=duopoly_network()),
        _markup_options("agent_a", "agent_b", max_iterations=400),
    )
    for row in result.offers:
        offered = _level(row.offer) * row.cleared_mw
        true = _level(row.true_cost) * row.cleared_mw
        assert row.markup == pytest.approx(offered - true, abs=1e-9)


def test_a_price_taker_s_markup_is_exactly_zero() -> None:
    """Offering one's own cost is a markup of nothing -- and the identity says so without a
    tolerance, since both sides evaluate the same curve."""
    result = solve_agents(
        Scenario(network=duopoly_network()),
        MarketAgentsOptions(strategies={"agent_a": {"kind": "price_taker"}}),
    )
    assert result.offers[0].offer == result.offers[0].true_cost
    assert result.offers[0].markup == 0.0


def test_the_markup_identity_holds_for_a_piecewise_offer_too() -> None:
    """The identity is stated on the *curves*, so it holds for an offer shape no shipped strategy
    produces -- which is what makes it an identity rather than a linear-cost coincidence."""

    class PiecewiseOfferer:
        """Offers a fixed piecewise curve from round 1 on."""

        def offer(self, observation: Observation) -> GeneratorCost:
            """True cost first, then a $40/MWh piecewise curve."""
            if observation.round_index == 0:
                return observation.true_cost
            return PiecewiseCost(points=[(0.0, 0.0), (900.0, 36_000.0)])

    result = solve_agents(
        Scenario(network=smooth_pivotal_network()),
        MarketAgentsOptions(max_iterations=6),
        strategies={"strategic": PiecewiseOfferer()},
    )
    row = result.offers[0]
    assert isinstance(row.offer, PiecewiseCost)
    assert row.markup == pytest.approx((40.0 - STRATEGIC_TRUE_COST) * row.cleared_mw, abs=1e-6)


# --------------------------------------------------------------------------------------------
# AC-5(i) -- convergence is real
# --------------------------------------------------------------------------------------------


def test_ac5i_the_duopoly_climbs_to_the_measured_point_and_reports_it_converged() -> None:
    """AC-5(i): on the 300/300 duopoly with both agents reactive at step 0.5, the loop takes 84
    update rounds and settles at offers ``[60.0, 60.0]``, $60.00, joint profit $15,999.98 against
    $11,999.96 at true cost.

    ``iterations > 1`` is asserted as its own clause: a fixed point reached in one round would
    make the whole loop unnecessary, and a run that took one round could still report every other
    figure here correctly.
    """
    net = duopoly_network()
    result = solve_agents(
        Scenario(network=net), _markup_options("agent_a", "agent_b", max_iterations=400)
    )
    assert result.status == "Optimal"  # the LP's verdict...
    assert result.converged is True  # ...and, separately, the loop's
    assert result.termination_reason == "converged"
    assert result.iterations > 1
    assert result.iterations == AC5_ITERATIONS
    assert [_level(row.offer) for row in result.offers] == [AC5_OFFER, AC5_OFFER]
    assert _lmp_at(result, result.generators[0].bus) == pytest.approx(AC5_PRICE, abs=PRICE_ABS_TOL)
    assert _profit(result, "agent_a", "agent_b", true_cost=STRATEGIC_TRUE_COST) == pytest.approx(
        AC5_JOINT_PROFIT, abs=PROFIT_ABS_TOL
    )


def test_ac5i_the_settled_oscillation_is_two_steps_wide() -> None:
    """AC-5(i)'s amplitude clause: what the loop calls convergence is a cycle of amplitude
    **1.0** -- exactly two steps of 0.5 -- which is inside ``offer_tol`` because A9 derives
    ``offer_tol = 2 * step``, not because a tolerance was widened to fit.

    Measured on the offers the real strategies really made, recorded round by round. The
    periodicity is asserted too: an amplitude read off a tail that is not actually repeating
    would be a number, not a settled oscillation.
    """
    net = duopoly_network()
    recorders = {gen_id: _Recorder(MarkupStrategy(step=STEP)) for gen_id in ("agent_a", "agent_b")}
    result = solve_agents(
        Scenario(network=net),
        MarketAgentsOptions(offer_tol=2 * STEP, max_iterations=400),
        strategies=dict(recorders),
    )
    assert result.converged is True
    for recorder in recorders.values():
        levels = [_level(offer) for offer in recorder.offers]
        tail = levels[-AC5_PERIOD:]
        assert max(tail) - min(tail) == AC5_AMPLITUDE
        assert AC5_AMPLITUDE == 2 * STEP
        assert levels[-1] == levels[-1 - AC5_PERIOD], "the tail must actually be periodic"
    assert AC5_AMPLITUDE <= 2 * STEP  # i.e. inside the derived offer_tol


def test_ac5i_the_true_cost_baseline_the_markup_is_measured_against() -> None:
    """The same duopoly with both agents price-taking: $11,999.96 of joint profit, which is what
    makes AC-5(i)'s $15,999.98 a markup rather than a number."""
    result = solve_agents(
        Scenario(network=duopoly_network()),
        MarketAgentsOptions(
            strategies={
                "agent_a": {"kind": "price_taker"},
                "agent_b": {"kind": "price_taker"},
            }
        ),
    )
    assert result.status == "Optimal"
    assert result.converged is True
    assert [_level(row.offer) for row in result.offers] == [
        STRATEGIC_TRUE_COST,
        STRATEGIC_TRUE_COST,
    ]
    assert _profit(result, "agent_a", "agent_b", true_cost=STRATEGIC_TRUE_COST) == pytest.approx(
        AC5_TRUE_COST_JOINT_PROFIT, abs=PROFIT_ABS_TOL
    )


def test_an_out_of_merit_markup_agent_settles_at_true_cost_not_at_the_cap() -> None:
    """The walk's shape (M7 S9 fix 3): a markup agent whose true cost sits above the price the
    rest of the market clears at is never dispatched. Before the idle rule its profit was
    0 == 0 every round, read as "not worse", so it climbed by a step per round until
    ``max_iterations`` and the run ended ``iteration_cap``. Now it probes up once, sees two
    idle rounds, walks back to its true cost and stays there -- and the loop reports that
    resting point as ``converged``."""
    net = non_pivotal_control_network(strategic_true_cost=30.0, rival_true_cost=22.0)
    recorder = _Recorder(MarkupStrategy(step=STEP))
    result = solve_agents(
        Scenario(network=net),
        MarketAgentsOptions(offer_tol=2 * STEP, max_iterations=40),
        strategies={"strategic": recorder},
    )
    assert result.status == "Optimal"
    assert result.termination_reason == "converged"
    assert result.converged is True
    (row,) = result.offers
    assert row.cleared_mw == 0.0
    assert _level(row.offer) == 30.0  # true cost, exactly
    assert row.markup == 0.0
    assert _lmp_at(result, "b1") == pytest.approx(22.0, abs=PRICE_ABS_TOL)
    levels = [_level(offer) for offer in recorder.offers]
    assert levels[:2] == [30.0, 30.5]  # true cost, then the one upward probe
    assert max(levels) == 30.5  # and never higher
    assert result.iterations < 40


@pytest.mark.parametrize("step", [0.5, 1.0, 2.0, 0.25, 0.3, 0.1, 0.2, 0.7, 0.05])
def test_a_settled_climb_converges_at_every_step_not_only_representable_ones(
    step: float,
) -> None:
    """The convergence verdict must not turn on whether ``2 * step`` is exactly representable.

    A9 derives ``offer_tol = 2 * step``, and a settled climber's amplitude *is* two steps -- so
    the two sides of the loop's comparison are the same number whenever it has genuinely arrived.
    They are not computed the same way: ``offer_tol`` is one multiplication, the amplitude is a
    peak-to-peak of levels each reached by hundreds of accumulated additions. Measured on this
    fixture (re-measured 2026-08-29, in ULPs of ``offer_tol``), the amplitude lands 102 ULPs
    *above* ``2 * step`` at 0.1 and 26 above at 0.7, while at 0.3 it lands 51 below and at 0.5 it
    is bit-exact. Under a plain ``<=`` the first two report a
    real climb as a ``cycle`` and the other two converge by luck.

    Every one of these runs is the same settled two-step oscillation; only the arithmetic differs.
    Steps 0.1, 0.2 and 0.7 are the cases that were wrong and are in the list for that reason;
    0.5, 1.0, 2.0 and 0.25 are binary-exact and cannot see this defect at all, which is why an
    otherwise thorough sabotage sweep run only at the wave own step of 0.5 could not have caught
    it. A defect sweep probes the defects you thought of, at the parameters you happened to use.
    """
    result = solve_agents(
        Scenario(network=duopoly_network()),
        _markup_options("agent_a", "agent_b", step=step, max_iterations=3000),
    )
    assert result.status == "Optimal"
    assert result.termination_reason == "converged"
    assert result.converged is True


def test_the_amplitude_band_admits_ulps_and_nothing_economically_real() -> None:
    """``_settled`` widens the comparison by a ULP-scale band, not by a margin that could hide a
    real cycle: it admits an amplitude a few parts in 1e9 over the tolerance and refuses one a
    part in 1e3 over.

    Without this the previous test would pass for the wrong reason -- a band wide enough to make
    every oscillation "settled" would also make ``converged`` meaningless.
    """
    assert agents_module._settled(1.0, 1.0)
    assert agents_module._settled(1.0 + 64 * 2.0**-52, 1.0), "the measured step-0.1 overshoot"
    assert agents_module._settled(0.2 + 2.9e-15, 0.2)
    assert not agents_module._settled(1.001, 1.0)
    assert not agents_module._settled(20.0, 1.0), "a genuine cycle on this wave's own fixtures"


# --------------------------------------------------------------------------------------------
# AC-5(ii) -- non-convergence is reported, in both of its shapes
# --------------------------------------------------------------------------------------------


def test_ac5ii_a_run_cut_short_reports_the_cap_and_never_claims_convergence() -> None:
    """AC-5(ii), first shape: ``max_iterations`` below the 84 the climb needs stops the run with
    ``termination_reason == "iteration_cap"`` and ``converged`` False -- while ``status`` stays
    ``Optimal``, because every round of it cleared perfectly well."""
    result = solve_agents(
        Scenario(network=duopoly_network()),
        _markup_options("agent_a", "agent_b", max_iterations=AC5_ITERATIONS - 1),
    )
    assert result.status == "Optimal"
    assert result.converged is False
    assert result.termination_reason == "iteration_cap"
    assert result.iterations == AC5_ITERATIONS - 1
    assert _level(result.offers[0].offer) < AC5_OFFER, "it was cut off mid-climb"


def test_ac5ii_a_genuine_cycle_reports_the_cycle_and_never_the_cap() -> None:
    """AC-5(ii), second shape: the "raise while at capacity" rule swings the offer over the whole
    markup range, so the repeated state it reaches has an amplitude far outside ``offer_tol`` and
    is reported as a **cycle** -- not as the cap (the run stops well short of it) and not as
    convergence.

    ``max_iterations`` is left far above the round the cycle is detected in, which is what makes
    the "never the cap" half of the clause mean something.
    """
    net = duopoly_network()
    result = solve_agents(
        Scenario(network=net),
        MarketAgentsOptions(offer_tol=2 * STEP, max_iterations=400),
        strategies={
            "agent_a": RaiseWhileAtCapacity(step=5.0),
            "agent_b": RaiseWhileAtCapacity(step=5.0),
        },
    )
    assert result.status == "Optimal"
    assert result.converged is False
    assert result.termination_reason == "cycle"
    assert result.iterations < 400, "stopped by the cycle, not by the cap"
    assert [row.strategy for row in result.offers] == [
        "RaiseWhileAtCapacity",
        "RaiseWhileAtCapacity",
    ]


def test_a_cycle_wider_than_offer_tol_is_never_reported_as_converged() -> None:
    """The classification is the amplitude's, not the repetition's: the same cycling run reports
    ``converged`` only if ``offer_tol`` is widened past the swing it actually makes.

    This is the sabotage-shaped companion to the test above -- it shows the ``cycle`` verdict is
    produced by comparing an amplitude against the tolerance, and not by anything else about the
    run that happens to correlate with it.
    """
    net = duopoly_network()
    kwargs = {
        "strategies": {
            "agent_a": RaiseWhileAtCapacity(step=5.0),
            "agent_b": RaiseWhileAtCapacity(step=5.0),
        }
    }
    narrow = solve_agents(
        Scenario(network=net), MarketAgentsOptions(offer_tol=1.0, max_iterations=400), **kwargs
    )
    wide = solve_agents(
        Scenario(network=net), MarketAgentsOptions(offer_tol=1e3, max_iterations=400), **kwargs
    )
    assert narrow.termination_reason == "cycle"
    assert wide.termination_reason == "converged"
    assert narrow.iterations == wide.iterations, "the same run, classified two ways"


def test_status_is_the_lp_s_and_termination_reason_is_none_when_it_failed() -> None:
    """A round that does not clear ends the run through ``status``/``message``, never by raising,
    and reports **no** loop outcome -- there was none.

    The infeasibility is built on the duopoly fixture by giving its load a fixed demand no
    generation can serve, so the LP itself fails rather than any agent misbehaving.
    """
    net = duopoly_network().model_copy(deep=True)
    net.loads[0].bid = None
    net.loads[0].p_mw = 5_000.0
    result = solve_agents(
        Scenario(network=net), _markup_options("agent_a", "agent_b", max_iterations=400)
    )
    assert result.status != "Optimal"
    assert result.converged is False
    assert result.termination_reason is None
    assert result.generators == [] and result.offers == []


# --------------------------------------------------------------------------------------------
# Caller mistakes -- caught before any solve (AC-6's engine-side half)
# --------------------------------------------------------------------------------------------


def test_offer_tol_below_two_steps_is_rejected_by_the_options_themselves() -> None:
    """A9's derived constraint is validated, not hoped for: a tolerance narrower than the
    settling oscillation would report every successful climb as a cycle."""
    with pytest.raises(ValidationError, match=r"below 2 \* step"):
        MarketAgentsOptions(strategies={"agent_a": {"kind": "markup", "step": 0.5}}, offer_tol=0.9)
    MarketAgentsOptions(strategies={"agent_a": {"kind": "markup", "step": 0.5}}, offer_tol=1.0)


def test_an_injected_markup_strategy_is_held_to_the_same_derived_constraint() -> None:
    """The object path does not escape A9 just because it skipped the config path."""
    with pytest.raises(ValueError, match=r"below 2 \* step"):
        solve_agents(
            Scenario(network=duopoly_network()),
            MarketAgentsOptions(offer_tol=0.9),
            strategies={"agent_a": MarkupStrategy(step=0.5)},
        )


@pytest.mark.parametrize(
    ("kwargs", "match"),
    [
        ({"max_iterations": 0}, r"greater than 0"),
        ({"max_iterations": -3}, r"greater than 0"),
        ({"offer_tol": 0.0}, r"greater than 0"),
        ({"offer_tol": -1.0}, r"greater than 0"),
    ],
)
def test_non_positive_bounds_are_rejected(kwargs: dict[str, object], match: str) -> None:
    """``max_iterations`` and ``offer_tol`` are both strictly positive (AC-6)."""
    with pytest.raises(ValidationError, match=match):
        MarketAgentsOptions(**kwargs)  # type: ignore[arg-type]


@pytest.mark.parametrize(
    ("gen_id", "match"),
    [("ghost", r"not in the network"), ("agent_a", r"has no cost")],
)
def test_a_strategy_that_cannot_bid_is_rejected_before_any_solve(gen_id: str, match: str) -> None:
    """A strategy naming a generator the network lacks, or one with no true cost to depart
    from."""
    net = duopoly_network().model_copy(deep=True)
    net.generators[0].cost = None
    with pytest.raises(ValueError, match=match):
        solve_agents(
            Scenario(network=net),
            MarketAgentsOptions(strategies={gen_id: {"kind": "price_taker"}}),
        )


def test_a_strategy_on_an_out_of_service_generator_is_rejected() -> None:
    """Its offer would never reach the clearing, so accepting it would be accepting a lie."""
    net = duopoly_network().model_copy(deep=True)
    net.generators[0].in_service = False
    with pytest.raises(ValueError, match=r"not in its arrays"):
        solve_agents(
            Scenario(network=net),
            MarketAgentsOptions(strategies={"agent_a": {"kind": "price_taker"}}),
        )


def test_two_sources_of_agents_at_once_is_rejected() -> None:
    """Configs or objects, never both -- otherwise which one ran is a coin toss the result
    cannot report."""
    with pytest.raises(ValueError, match=r"exactly one source"):
        solve_agents(
            Scenario(network=duopoly_network()),
            MarketAgentsOptions(strategies={"agent_a": {"kind": "price_taker"}}),
            strategies={"agent_b": PriceTakerStrategy()},
        )


def test_a_markup_strategy_on_a_quadratic_cost_is_rejected_before_any_clearing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A ``MarkupStrategy`` on a non-linear true cost is a caller mistake in the agent set, and
    is caught where the other four are: up front, as ``ValueError`` naming the generator, before
    the first clearing (M7 S9 fix 2 -- previously the strategy's own ``NotImplementedError``
    escaped the loop and reached ``jobs.run`` as ``INTERNAL``). ``dc_opf`` is sabotaged to
    prove "before any clearing" rather than assume it; ``MarkupStrategy`` itself still raises
    ``NotImplementedError`` (its own contract, ``test_market_strategy.py``)."""

    def never(*args: object, **kwargs: object) -> object:
        raise AssertionError("dc_opf was reached: the agent set was not rejected up front")

    monkeypatch.setattr(agents_module, "dc_opf", never)
    net = duopoly_network().model_copy(deep=True)
    net.generators[0].cost = PolynomialCost(coefficients=[0.01, 20.0, 0.0])
    with pytest.raises(ValueError, match=r'"agent_a".*only a linear PolynomialCost') as info:
        solve_agents(Scenario(network=net), _markup_options("agent_a", max_iterations=4))
    assert isinstance(info.value.__cause__, NotImplementedError)


def test_a_strategy_returning_something_other_than_a_cost_is_rejected_at_the_call_site(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Walk finding (M7 S9): a strategy that returns ``None`` (a forgotten ``return``) or any
    non-``GeneratorCost`` used to fail *after* the clearing, with a pydantic error naming
    ``RoundRecord`` -- the wrong layer and the wrong name. The loop checks what a strategy
    returned where it called it, before any clearing, and says which generator's strategy."""

    def never(*args: object, **kwargs: object) -> object:
        raise AssertionError("dc_opf was reached: the bad return was not caught at the call site")

    monkeypatch.setattr(agents_module, "dc_opf", never)

    class Forgetful:
        def offer(self, observation: Observation) -> GeneratorCost:
            return None  # type: ignore[return-value]

    with pytest.raises(TypeError, match=r'"agent_a".*returned None'):
        solve_agents(
            Scenario(network=duopoly_network()),
            MarketAgentsOptions(),
            strategies={"agent_a": Forgetful()},
        )


def test_no_agents_at_all_is_a_market_in_which_nobody_bids() -> None:
    """An empty strategy map is meaningful, not a missing argument: the clearing is the ordinary
    true-cost one and the loop settles immediately with no offers to report."""
    result = solve_agents(Scenario(network=duopoly_network()), MarketAgentsOptions())
    assert result.status == "Optimal"
    assert result.converged is True
    assert result.offers == []
    assert result.generators != []


# --------------------------------------------------------------------------------------------
# The result model's own guards (A7: status is the LP's, converged is the loop's)
# --------------------------------------------------------------------------------------------


def _minimal_result(**overrides: object) -> dict[str, object]:
    base: dict[str, object] = {
        "provenance": {
            "engine": "mambo-power",
            "version": "0",
            "kind": "market.agents",
            "solver": "highspy.Highs",
            "started_at": "2026-08-28T00:00:00Z",
            "elapsed_s": 0.0,
            "options": {},
        },
        "status": "Optimal",
        "converged": True,
        "termination_reason": "converged",
    }
    base.update(overrides)
    return base


@pytest.mark.parametrize(
    ("overrides", "match"),
    [
        ({"termination_reason": None}, r"required when status == 'Optimal'"),
        (
            {"status": "Infeasible", "converged": False},
            r"has no loop outcome to report",
        ),
        ({"converged": False}, r"contradicts termination_reason"),
        (
            {"converged": True, "termination_reason": "cycle"},
            r"contradicts termination_reason",
        ),
    ],
)
def test_a_result_cannot_carry_a_self_contradicting_story(
    overrides: dict[str, object], match: str
) -> None:
    """``converged`` and ``termination_reason`` say the same thing, and neither is reported for a
    clearing that never happened."""
    with pytest.raises(ValidationError, match=match):
        MarketAgentsResult(**_minimal_result(**overrides))  # type: ignore[arg-type]


def test_the_result_round_trips_through_json() -> None:
    """Including the ``GeneratorCost`` union on both sides of every offer row."""
    result = solve_agents(
        Scenario(network=duopoly_network()),
        _markup_options("agent_a", "agent_b", max_iterations=400),
    )
    again = MarketAgentsResult.model_validate(json.loads(result.model_dump_json()))
    assert again.model_dump() == result.model_dump()
    assert isinstance(again.offers[0], AgentOfferResult)


# --------------------------------------------------------------------------------------------
# Package export -- the fourth mode is reachable the way the other three are
# --------------------------------------------------------------------------------------------


def test_solve_agents_is_exported_from_the_market_package_like_the_other_modes() -> None:
    """``docs/changelog.md``, ``docs/index.md`` and ``docs/examples/index.md`` all name
    ``market.solve_agents``; the walk found only ``market.agents.solve_agents`` importable while
    ``solve_nodal``/``solve_multiperiod``/``solve_zonal`` were each re-exported from the package
    (M7 S9, fix 1)."""
    from mambo_power import market

    assert market.solve_agents is agents_module.solve_agents
    assert market.MarketAgentsOptions is agents_module.MarketAgentsOptions
    assert "solve_agents" in market.__all__
    assert "MarketAgentsOptions" in market.__all__
