"""The wave's two economic statements, asserted through the shipped loop (M7 W5; AC-3, AC-4).

**What this module is for, and what it is not.** ``tests/unit/test_agents_fixtures.py`` (S3)
pins the same fixtures' economics at *swept* offers, clearing each candidate offer directly
through ``opf.dc_opf``; ``tests/unit/test_market_agents.py`` (S4) pins the loop's own machinery
and its termination. Neither asserts what AC-3 and AC-4 actually claim: that
``market.agents.solve_agents`` **itself** reproduces the competitive result when nobody games,
and **itself** walks a pivotal supplier's markup up to the point where demand stops paying.
Every number below is therefore taken from a ``solve_agents`` call, never from a hand-placed
offer.

**AC-3, in two clauses, and they are different claims.** (a) is about the *input*: on an
all-price-taker configuration the coefficients handed to the array builder are ``array_equal``
to the generators' own true ones -- that is what makes a price-taker a price-taker, and a
perturbation far below the LP's own tolerance breaks it while leaving every output untouched.
(b) is about the *output*: dispatch and LMPs are ``array_equal`` -- **bitwise**, not
``approx`` -- to ``market.solve_nodal``'s. Spec A3 measured five independent ``dc_opf``
constructions on identical input agreeing bitwise, and both paths here hand the builder the same
arrays; the research premise that two ``highspy.Highs()`` constructions must diverge is false for
*identical* input (M5's macOS one-ULP finding was a structurally different LP). **If a platform
ever disagrees, that is a finding to record, not a tolerance to introduce here.**

Both clauses are asserted on three cost shapes, because ``PriceTakerStrategy`` is scoped to none
of them: the wave's own **linear** synthetic fixture (which also exercises the elastic-demand
side), **quadratic** ``case14`` (the shape all 147 generators in every committed MATPOWER
fixture carry), and **piecewise** ``case14_pwl`` -- the only path by which a PWL offer reaches
the builder this wave, and the invariant S1's generator-side overlap guard exists to protect.

**AC-4 is a claim about a mechanism, not a magnitude.** "The markup is real and stops" is close
to unfalsifiable (spec, "Rejected alternatives"), so the stopping point is pinned three ways:
against the closed form ``(pi - 20)(1000 - 10*pi)``; against a **moved bid curve**, which moves
the peak with it -- that is the difference between a cap and a clamp; and against the paired
non-pivotal control, whose climb is stopped by a **rival** instead, which is shown by moving the
rival's cost and watching the stop follow while demand's bid does not move it at all.

**Tolerances.** :data:`PRICE_ABS_TOL` / :data:`DISPATCH_ABS_TOL` / :data:`PROFIT_ABS_TOL` are
``test_agents_fixtures.py``'s own, for its own reason: HiGHS solves these LPs to its default
tolerance, so a price lands ~1e-4 $/MWh off and a five-figure profit a few cents off. The
**offer levels and iteration counts carry no tolerance at all** -- they are exact arithmetic on
the step size -- and neither does anything in AC-3, which is that row's whole point.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping

import numpy as np
import pytest

from mambo_power.io import matpower
from mambo_power.market import agents as agents_module
from mambo_power.market import nodal as nodal_module
from mambo_power.market.agents import MarketAgentsOptions, solve_agents
from mambo_power.market.nodal import solve_nodal
from mambo_power.model import Network, PolynomialBid, PolynomialCost, Scenario
from mambo_power.numerics import NetworkArrays
from mambo_power.opf import gen_cost_coeffs
from mambo_power.results.agents import MarketAgentsResult
from tests._agents import (
    LOAD_P_MAX_MW,
    STRATEGIC_P_MAX_MW,
    STRATEGIC_TRUE_COST,
    non_pivotal_control_network,
    smooth_pivotal_network,
)
from tests._fixtures import FIXTURES_DIR

PRICE_ABS_TOL = 0.01
DISPATCH_ABS_TOL = 0.01
PROFIT_ABS_TOL = 0.5

STEP = 0.5
"""AC-4's step. ``offer_tol`` is then ``2 * STEP`` by A9's derivation, not by choice -- and 0.5
is binary-exact, which keeps this module clear of the representability question
``test_market_agents.py`` owns."""

AC4_PEAK_OFFER = 60.0
AC4_PEAK_MW = 400.0
AC4_PEAK_PROFIT = 15_999.98
AC4_CLOSED_FORM_PROFIT = 16_000.0
AC4_ITERATIONS = 84
AC4_TRUE_COST_PROFIT = 0.06
AC4_PIVOTAL_GAIN = 15_999.92

AC4_CONTROL_OFFER = 21.5
AC4_CONTROL_GAIN = 1_177.50
AC4_GAIN_RATIO = 13.6

DEMAND_SLOPE = 10.0
"""``q(price) = 10*v1 - DEMAND_SLOPE*price`` for the shared bid ``marginal value = v1 - 0.1*p``
(``tests._agents`` module docstring): 0.1 $/MWh per MW is :data:`DEMAND_SLOPE` MW per $/MWh."""

DEMAND_INTERCEPT = 100.0
"""``tests._agents.DEMAND_BID``'s own ``v1`` -- the 100 in ``marginal value = 100 - 0.1*p`` --
restated here so :func:`_rebid` can move it and :func:`_closed_form_peak` can say where the
profit peak goes when it does."""


# --------------------------------------------------------------------------------------------
# Shared helpers
# --------------------------------------------------------------------------------------------


def _price_taker_options(net: Network) -> MarketAgentsOptions:
    """Every generator in *net* an agent, and every one of them a price-taker -- AC-3's own
    configuration. Naming them all matters: a generator left out would not be an agent at all,
    and its offer would prove nothing about the strategy."""
    return MarketAgentsOptions(
        strategies={gen.id: {"kind": "price_taker"} for gen in net.generators}
    )


def _markup_options(*gen_ids: str, **kwargs: object) -> MarketAgentsOptions:
    """A markup config at :data:`STEP` for each of *gen_ids*, with A9's derived ``offer_tol``."""
    return MarketAgentsOptions(
        strategies={gen_id: {"kind": "markup", "step": STEP} for gen_id in gen_ids},
        offer_tol=2.0 * STEP,
        **kwargs,  # type: ignore[arg-type]
    )


def _capture(monkeypatch: pytest.MonkeyPatch) -> list[tuple[np.ndarray, object]]:
    """Record ``(cost_coeffs, pwl_costs)`` as they are handed to the array builder, round by
    round, and return the list they land in.

    AC-3(a) is a claim about what the *builder* saw, not about what the result reports, so it
    has to be read at that call: ``MarketAgentsResult.offers`` renders the same decision one
    layer later, and a defect between the two would be invisible to it. Same seam
    ``test_market_agents.py``'s AC-2 positive control reads.
    """
    handed: list[tuple[np.ndarray, object]] = []
    real_dc_opf = agents_module.dc_opf

    def capturing(arr, cost_coeffs, options, **kwargs):  # type: ignore[no-untyped-def]
        handed.append((np.array(cost_coeffs, copy=True), kwargs.get("pwl_costs")))
        return real_dc_opf(arr, cost_coeffs, options, **kwargs)

    monkeypatch.setattr(agents_module, "dc_opf", capturing)
    return handed


def _rebid(net: Network, v1: float) -> Network:
    """*net* with its shared elastic load's bid intercept moved from :data:`DEMAND_INTERCEPT`
    to *v1*, i.e. demand ``q(price) = 10*v1 - 10*price``.

    Derived by copy from a ``tests._agents`` factory's own network -- nothing in this module
    assembles a strategic-bidding network, and the fixture module's public factories do not
    expose the bid (its private ``_network`` does, for exactly this purpose). Only the bid
    moves: ``Load.p_mw`` stays at :data:`LOAD_P_MAX_MW`, which is above every peak quantity
    reached here, so the elastic column's own upper bound never truncates the curve under test.
    """
    load = net.loads[0]
    moved = load.model_copy(update={"bid": PolynomialBid(coefficients=[-0.05, v1, 0.0])})
    return net.model_copy(update={"loads": [moved]})


def _closed_form_peak(
    v1: float, true_cost: float = STRATEGIC_TRUE_COST
) -> tuple[float, float, float]:
    """``(price, quantity, profit)`` maximising ``(pi - true_cost) * (10*v1 - 10*pi)``.

    A concave quadratic in ``pi``, so its stationary point is the maximum: ``pi* =
    (v1 + true_cost) / 2``. Hand-derived here rather than read off the solver, because AC-4's
    oracle *is* a hand-derived optimum (spec, "Prior art") -- deriving it from the code under
    test would make the comparison circular.
    """
    price = (v1 + true_cost) / 2.0
    quantity = DEMAND_SLOPE * v1 - DEMAND_SLOPE * price
    return price, quantity, (price - true_cost) * quantity


def _bus_of(result: MarketAgentsResult, gen_id: str) -> str:
    return next(row.bus for row in result.generators if row.id == gen_id)


def _price_at(result: MarketAgentsResult, bus: str) -> float:
    return next(row.lmp for row in result.buses if row.id == bus)


def _dispatch_of(result: MarketAgentsResult, gen_id: str) -> float:
    return next(row.p_mw for row in result.generators if row.id == gen_id)


def _offer_level(result: MarketAgentsResult, gen_id: str) -> float:
    """The $/MWh marginal level of *gen_id*'s final offer -- every offer in these fixtures is a
    linear :class:`~mambo_power.model.PolynomialCost`."""
    offer = next(row.offer for row in result.offers if row.id == gen_id)
    assert isinstance(offer, PolynomialCost)
    return offer.coefficients[0]


def _profit_of(result: MarketAgentsResult, gen_id: str) -> float:
    """``(own bus LMP - own true marginal cost) * own cleared MW`` at the reported clearing --
    the same reading ``MarkupStrategy`` climbs on."""
    return (_price_at(result, _bus_of(result, gen_id)) - STRATEGIC_TRUE_COST) * _dispatch_of(
        result, gen_id
    )


def _pivotal_climb(net: Network | None = None) -> MarketAgentsResult:
    """The AC-4 run: one markup agent on the smooth pivotal fixture, with room to finish."""
    return solve_agents(
        Scenario(network=net if net is not None else smooth_pivotal_network()),
        _markup_options("strategic", max_iterations=400),
    )


def _true_cost_run(net: Network) -> MarketAgentsResult:
    """The same fixture with every unit price-taking -- AC-4's own baseline."""
    return solve_agents(Scenario(network=net), _price_taker_options(net))


# --------------------------------------------------------------------------------------------
# AC-3 -- price-takers reproduce the competitive result
# --------------------------------------------------------------------------------------------

CASE14 = FIXTURES_DIR / "case14.m"
CASE14_PWL = FIXTURES_DIR / "derived" / "case14_pwl.m"

COST_SHAPES: dict[str, Callable[[], Network]] = {
    # Linear polynomial costs, and the only one of the three with an elastic load, so AC-3
    # exercises the bid side of the clearing too.
    "linear": smooth_pivotal_network,
    # Quadratic: the shape every one of the 147 generators in the six committed MATPOWER
    # fixtures carries (plan C3). PriceTakerStrategy is not scoped to linear costs -- only
    # MarkupStrategy is -- and this is what proves it.
    "quadratic": lambda: matpower.load(CASE14),
    # Piecewise on gen-2/gen-3, quadratic on the rest: the only path by which a PWL offer
    # reaches the array builder this wave.
    "piecewise": lambda: matpower.load(CASE14_PWL),
}


@pytest.mark.parametrize("shape", list(COST_SHAPES))
def test_ac3a_the_coefficients_handed_to_the_builder_are_exactly_the_true_costs(
    shape: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    """AC-3(a): on an all-price-taker run, **every** round's ``cost_coeffs`` is ``array_equal``
    to ``gen_cost_coeffs(net, arr)``'s own -- the offer map is the true costs, exactly.

    Every round, not only the last: a strategy that drifted after round 0 would still leave a
    final offer equal to true cost on a fixture whose clearing does not move, and this clause
    exists to rule that out. The PWL side is checked in the same breath, since a piecewise cost
    reaches the builder through ``pwl_costs`` and not through the coefficient rows at all.
    """
    net = COST_SHAPES[shape]()
    handed = _capture(monkeypatch)
    result = solve_agents(Scenario(network=net), _price_taker_options(net))
    assert result.status == "Optimal"

    arr = NetworkArrays.from_network(net)
    true_coeffs, true_pwl = gen_cost_coeffs(net, arr)
    assert handed, "the run must have reached the array builder at all"
    assert len(handed) == result.iterations + 1
    for round_index, (coeffs, pwl) in enumerate(handed):
        assert np.array_equal(coeffs, true_coeffs), f"round {round_index}'s coefficients"
        assert (pwl or {}) == (true_pwl or {}), f"round {round_index}'s PWL offers"

    # ...and the same statement as the result renders it, which is the form a caller reads.
    for row in result.offers:
        assert row.offer.model_dump_json() == row.true_cost.model_dump_json()
        assert row.markup == 0.0


@pytest.mark.parametrize("shape", list(COST_SHAPES))
def test_ac3b_dispatch_and_lmps_are_bitwise_market_solve_nodals(shape: str) -> None:
    """AC-3(b): dispatch and LMPs are ``array_equal`` -- **no tolerance** -- to
    ``market.solve_nodal``'s on the same scenario (spec A3, measured bitwise).

    The row ids are asserted equal first: ``array_equal`` over two vectors assembled in
    different orders would compare the wrong pairs, and could then pass or fail for reasons
    that have nothing to do with the clearing.
    """
    net = COST_SHAPES[shape]()
    scenario = Scenario(network=net)
    agents = solve_agents(scenario, _price_taker_options(net))
    nodal = solve_nodal(scenario)
    assert agents.status == "Optimal"
    assert nodal.status == "Optimal"

    assert [row.id for row in agents.generators] == [row.id for row in nodal.generators]
    assert [row.id for row in agents.buses] == [row.id for row in nodal.buses]
    assert [row.id for row in agents.loads] == [row.id for row in nodal.loads]

    assert np.array_equal(
        np.array([row.p_mw for row in agents.generators]),
        np.array([row.p_mw for row in nodal.generators]),
    )
    assert np.array_equal(
        np.array([row.lmp for row in agents.buses]),
        np.array([row.lmp for row in nodal.buses]),
    )
    # Elastic demand is dispatched too, and on the linear fixture it is the whole demand side.
    assert np.array_equal(
        np.array([row.p_mw for row in agents.loads]),
        np.array([row.p_mw for row in nodal.loads]),
    )


def test_ac3_the_all_price_taker_case_is_an_ordinary_run_of_the_general_path() -> None:
    """No price-taker short-circuit exists (spec AC-3): the reproduction is produced *by* the
    loop, the overlay and the offer map, not by a delegation to ``market.solve_nodal``.

    Confirmed rather than assumed, in the way that would catch a short-circuit added later:
    ``solve_nodal`` is replaced by something that raises, and the run still clears. The loop's
    own trace is asserted alongside -- more than one clearing, one offer row per generator --
    because a run that took a single round would satisfy AC-3 while exercising none of the
    machinery the row exists to prove honest.
    """
    net = smooth_pivotal_network()

    def exploding_solve_nodal(*args: object, **kwargs: object) -> None:
        raise AssertionError("solve_agents delegated to market.solve_nodal")

    with pytest.MonkeyPatch.context() as patch:
        patch.setattr(nodal_module, "solve_nodal", exploding_solve_nodal)
        result = solve_agents(Scenario(network=net), _price_taker_options(net))

    assert result.status == "Optimal"
    assert result.converged is True
    assert result.iterations >= 2, "more than one clearing, i.e. the loop really iterated"
    assert [row.id for row in result.offers] == [gen.id for gen in net.generators]


def test_ac3_a_piecewise_true_cost_reaches_the_builder_as_a_piecewise_offer(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The PWL path AC-3 covers is a real one, and it carries S1's guarded invariant.

    ``case14_pwl`` mixes MODEL-1 piecewise costs (gen-2, gen-3) with quadratic ones, so an
    all-price-taker run over it hands the builder a non-empty ``pwl_costs`` map **and** an
    all-zero coefficient row for exactly those generators -- the convention whose violation
    ``_extract_and_validate``'s generator-side overlap guard (W1(c)) now raises on. Asserted
    here because AC-3 is the only acceptance row in the wave under which a PWL offer reaches
    the array builder at all.
    """
    net = matpower.load(CASE14_PWL)
    handed = _capture(monkeypatch)
    result = solve_agents(Scenario(network=net), _price_taker_options(net))
    assert result.status == "Optimal"

    coeffs, pwl = handed[-1]
    assert isinstance(pwl, Mapping)
    pwl_indices = sorted(pwl)
    assert pwl_indices, "case14_pwl must carry piecewise generators, or this proves nothing"
    arr = NetworkArrays.from_network(net)
    assert [arr.gen_ids[i] for i in pwl_indices] == [
        gen.id for gen in net.generators if gen.cost is not None and gen.cost.kind == "piecewise"
    ]
    for i in pwl_indices:
        assert np.array_equal(coeffs[i], np.zeros(3)), "a PWL generator's own row is all-zero"
    others = [i for i in range(len(arr.gen_ids)) if i not in set(pwl_indices)]
    assert others, "the quadratic half of the mix must be present too"
    assert any(coeffs[i][0] != 0.0 for i in others), "and it must still carry a quadratic term"


# --------------------------------------------------------------------------------------------
# AC-4 -- a pivotal supplier's markup stops where demand stops paying
# --------------------------------------------------------------------------------------------


def test_ac4_the_pivotal_climb_reaches_the_measured_stopping_point() -> None:
    """AC-4's headline: on ``smooth_pivotal_network()`` the shipped climb settles at offer
    **$60.00**, price **$60.00**, dispatch **400.00 MW** and profit **$15,999.98**, in **84**
    update rounds -- the Step-2 measurement, reproduced through ``solve_agents`` itself.

    The offer level and the iteration count are exact: both are arithmetic on a step of 0.5,
    and a tolerance on either would admit the one thing this row exists to pin.
    """
    result = _pivotal_climb()
    assert result.status == "Optimal"  # the LP's verdict...
    assert result.converged is True  # ...and, separately, the loop's
    assert result.termination_reason == "converged"
    assert result.iterations == AC4_ITERATIONS
    assert _offer_level(result, "strategic") == AC4_PEAK_OFFER
    assert _price_at(result, _bus_of(result, "strategic")) == pytest.approx(
        AC4_PEAK_OFFER, abs=PRICE_ABS_TOL
    )
    assert _dispatch_of(result, "strategic") == pytest.approx(AC4_PEAK_MW, abs=DISPATCH_ABS_TOL)
    assert _profit_of(result, "strategic") == pytest.approx(AC4_PEAK_PROFIT, abs=PROFIT_ABS_TOL)


def test_ac4_the_stopping_point_is_the_closed_form_optimum() -> None:
    """The solver's $15,999.98 against the hand-derived $16,000.00 -- the agreement AC-4 asks
    to be pinned, with the closed form derived here rather than taken from the run.

    ``profit(pi) = (pi - 20)(1000 - 10*pi)`` is a concave quadratic peaking at ``pi = 60``,
    ``q = 400``, ``$16,000/h``. A genuine peak and not a plateau: a dollar either side of it
    strictly loses money, which is what makes "the climb stopped here" a statement about an
    optimum rather than about where it ran out of road.
    """
    price, quantity, profit = _closed_form_peak(DEMAND_INTERCEPT)
    assert (price, quantity, profit) == (AC4_PEAK_OFFER, AC4_PEAK_MW, AC4_CLOSED_FORM_PROFIT)

    def profit_at(pi: float) -> float:
        return (pi - STRATEGIC_TRUE_COST) * (LOAD_P_MAX_MW - DEMAND_SLOPE * pi)

    assert profit_at(price) == pytest.approx(AC4_CLOSED_FORM_PROFIT, abs=1e-9)
    assert profit_at(price - 1.0) < profit_at(price)
    assert profit_at(price + 1.0) < profit_at(price)

    result = _pivotal_climb()
    assert _profit_of(result, "strategic") == pytest.approx(
        AC4_CLOSED_FORM_PROFIT, abs=PROFIT_ABS_TOL
    )


def test_ac4_the_true_cost_baseline_the_markup_is_measured_against() -> None:
    """$0.06/h at true-cost offers against $15,999.98 marked up: the baseline that makes the
    pivotal figure a *markup* rather than a number, and the $15,999.92 gain AC-4 states."""
    net = smooth_pivotal_network()
    baseline = _true_cost_run(net)
    assert baseline.status == "Optimal"
    assert _offer_level(baseline, "strategic") == STRATEGIC_TRUE_COST
    assert _profit_of(baseline, "strategic") == pytest.approx(
        AC4_TRUE_COST_PROFIT, abs=PROFIT_ABS_TOL
    )
    gain = _profit_of(_pivotal_climb(), "strategic") - _profit_of(baseline, "strategic")
    assert gain == pytest.approx(AC4_PIVOTAL_GAIN, abs=PROFIT_ABS_TOL)


def test_ac4_the_pivotal_unit_stops_far_short_of_its_own_capacity() -> None:
    """What stops the climb is not the unit running out of megawatts: it settles at 400 MW of
    its own 900 MW, having *withheld* nothing -- the offer curve moved and the capacity did not
    (spec "Not Doing"). At true cost the same unit clears 800 MW, so the quantity fell because
    the price rose, which is the whole economic content of a markup."""
    result = _pivotal_climb()
    assert _dispatch_of(result, "strategic") == pytest.approx(AC4_PEAK_MW, abs=DISPATCH_ABS_TOL)
    assert _dispatch_of(result, "strategic") < STRATEGIC_P_MAX_MW - 100.0
    baseline = _true_cost_run(smooth_pivotal_network())
    assert _dispatch_of(baseline, "strategic") > _dispatch_of(result, "strategic")


@pytest.mark.parametrize("v1", [90.0, 100.0, 120.0])
def test_ac4_the_cap_is_demands_own_bid_and_the_peak_moves_with_it(v1: float) -> None:
    """**The cap is ``Load.bid``, not a clamp.** Move demand's own willingness to pay and the
    climb stops somewhere else -- at the new closed-form peak, every time.

    ``marginal value = v1 - 0.1*p`` gives ``q = 10*v1 - 10*price``, whose profit peak sits at
    ``(v1 + 20)/2``: **$55.00 / 350 MW / $12,250** at ``v1 = 90``, the fixture's own **$60.00 /
    400 MW / $16,000** at 100, and **$70.00 / 500 MW / $25,000** at 120. A clamp at any fixed
    level would hold one of these three and fail the other two; nothing but demand's own curve
    puts the climb at all three.
    """
    result = _pivotal_climb(_rebid(smooth_pivotal_network(), v1))
    price, quantity, profit = _closed_form_peak(v1)
    assert result.status == "Optimal"
    assert result.converged is True
    assert _offer_level(result, "strategic") == price
    assert _price_at(result, _bus_of(result, "strategic")) == pytest.approx(
        price, abs=PRICE_ABS_TOL
    )
    assert _dispatch_of(result, "strategic") == pytest.approx(quantity, abs=DISPATCH_ABS_TOL)
    assert _profit_of(result, "strategic") == pytest.approx(profit, abs=PROFIT_ABS_TOL)


def test_ac4_the_three_moved_bids_really_are_three_different_peaks() -> None:
    """The parametrisation above is a cap proof only if its three cases genuinely differ -- one
    assertion that holds at a single peak and is then repeated three times proves nothing."""
    peaks = [_closed_form_peak(v1)[0] for v1 in (90.0, 100.0, 120.0)]
    assert peaks == [55.0, 60.0, 70.0]
    assert len(set(peaks)) == 3


def test_ac4_control_stops_at_21_50_for_a_real_but_far_smaller_gain() -> None:
    """AC-4's paired control: the same unit and the same strategy, now facing a 900 MW rival at
    $22, stops at offer **$21.50** for a gain of **$1,177.50** against the pivotal
    **$15,999.92** -- real, nonzero, and **13.6x** smaller.

    Both gains are asserted; neither is a bound. And the control settles in 7 rounds against
    the pivotal's 84, which is the same fact seen from the loop's side: it has three steps to
    walk, not eighty.
    """
    control = solve_agents(
        Scenario(network=non_pivotal_control_network()),
        _markup_options("strategic", max_iterations=400),
    )
    assert control.status == "Optimal"
    assert control.converged is True
    assert _offer_level(control, "strategic") == AC4_CONTROL_OFFER
    control_gain = _profit_of(control, "strategic") - _profit_of(
        _true_cost_run(non_pivotal_control_network()), "strategic"
    )
    assert control_gain == pytest.approx(AC4_CONTROL_GAIN, abs=PROFIT_ABS_TOL)

    pivotal_gain = _profit_of(_pivotal_climb(), "strategic") - _profit_of(
        _true_cost_run(smooth_pivotal_network()), "strategic"
    )
    assert pivotal_gain == pytest.approx(AC4_PIVOTAL_GAIN, abs=PROFIT_ABS_TOL)
    assert 0.0 < control_gain < pivotal_gain
    assert pivotal_gain / control_gain == pytest.approx(AC4_GAIN_RATIO, abs=0.1)
    assert control.iterations < AC4_ITERATIONS


@pytest.mark.parametrize("rival_cost", [22.0, 26.0, 30.0])
def test_ac4_the_control_is_stopped_by_the_rival_and_the_stop_follows_it(
    rival_cost: float,
) -> None:
    """**The control's cap is the rival, and it is shown the way demand's was**: move the
    rival's true cost and the stop moves with it, to one step below in every case -- $21.50,
    $25.50 and $29.50 for a rival at $22, $26 and $30.

    One step below, not at it: the round that offers the rival's own cost ties with it, the tie
    is broken against the strategic unit, its profit falls and the climb reverses. That is a
    different stopping mechanism from the pivotal fixture's, where nothing but the shape of
    demand's own curve is involved -- and every one of these stops lands nowhere near demand's
    $60.00 peak, which is still exactly where it was.
    """
    net = non_pivotal_control_network(rival_true_cost=rival_cost)
    result = solve_agents(Scenario(network=net), _markup_options("strategic", max_iterations=400))
    assert result.status == "Optimal"
    assert result.converged is True
    assert _offer_level(result, "strategic") == rival_cost - STEP
    assert _offer_level(result, "strategic") < AC4_PEAK_OFFER
    assert _closed_form_peak(DEMAND_INTERCEPT)[0] == AC4_PEAK_OFFER


def test_ac4_moving_demands_bid_does_not_move_the_controls_stop() -> None:
    """The complement, and what makes "stopped by the rival" a mechanism rather than a label:
    the *same* bid move that walks the pivotal climb from $60.00 down to $55.00 leaves the
    control's stop exactly where it was, at $21.50.

    Not vacuous -- the bid change did reach this market: the cleared quantity falls from 785 MW
    to 685 MW, which is the demand curve's own answer at an unchanged $21.50. Demand is simply
    not the binding side here; the rival is.
    """
    at_100 = solve_agents(
        Scenario(network=non_pivotal_control_network()),
        _markup_options("strategic", max_iterations=400),
    )
    at_90 = solve_agents(
        Scenario(network=_rebid(non_pivotal_control_network(), 90.0)),
        _markup_options("strategic", max_iterations=400),
    )
    assert _offer_level(at_100, "strategic") == AC4_CONTROL_OFFER
    assert _offer_level(at_90, "strategic") == AC4_CONTROL_OFFER

    assert _dispatch_of(at_100, "strategic") == pytest.approx(785.0, abs=DISPATCH_ABS_TOL)
    assert _dispatch_of(at_90, "strategic") == pytest.approx(685.0, abs=DISPATCH_ABS_TOL)

    # ...while the same move walks the pivotal climb off its own peak.
    moved_pivotal = _pivotal_climb(_rebid(smooth_pivotal_network(), 90.0))
    assert _offer_level(moved_pivotal, "strategic") == 55.0
    assert _offer_level(_pivotal_climb(), "strategic") == AC4_PEAK_OFFER
