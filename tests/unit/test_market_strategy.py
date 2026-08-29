"""Unit tests for :mod:`mambo_power.market.strategy` — the own-node ``Observation``/``Strategy``
seam (wave M7 W2, spec AC-3/AC-4/AC-5's shared building block; design D3, assumptions A4/A8/A9).

No market loop exists here (that is S4's ``market.agents``, not yet built) — every test drives
:class:`~mambo_power.market.strategy.Strategy` implementations directly against hand-built
:class:`~mambo_power.market.strategy.Observation` values, through this file's own fixture
factory (:func:`_linear_cost` / :func:`_record` / :func:`_observation`) rather than reconstructing
one ad hoc per test.

**What each behaviour is checked against.**

* :class:`~mambo_power.market.strategy.PriceTakerStrategy` must return the *exact* true-cost
  coefficients (``==``, not ``pytest.approx``) — AC-3(a)'s ``array_equal`` claim starts here — and
  must do so for a :class:`~mambo_power.model.PiecewiseCost` true cost just as much as a
  polynomial one: AC-3(a) does not know it is the only path a piecewise offer reaches the array
  builder through this wave, but that is exactly what makes it load-bearing.
* :class:`~mambo_power.market.strategy.MarkupStrategy`'s two-point climb is checked against the
  rule as measured (A4, ``.bionic/tmp/m7-a4-two-point-climb.py``): direction continues on improved
  profit, reverses on a *real* worsened profit, defaults to ``+1`` with no prior movement, and the
  result never drops below true cost. A tie within relative tolerance -- an agent at capacity
  seeing two rounds of solver-noise-only LMP difference -- must **not** reverse (found downstream
  on the AC-5 duopoly, where a strict ``<`` turned a settled climb into the true-cost outcome
  reported as convergence); a paired test at the same zero-movement baseline confirms a real
  decrease still reverses. It is deliberately scoped to a linear
  :class:`~mambo_power.model.PolynomialCost` and raises loudly, rather than approximating
  something, on anything else.
* :class:`~mambo_power.market.strategy.Observation`'s round-0/round-1 shapes are constructed
  directly and asserted to carry ``None`` — never a fabricated zero-valued
  :class:`~mambo_power.market.strategy.RoundRecord`. Two distinct bad histories are asserted
  rejected, not silently accepted: a **missing** entry (``two_rounds_ago`` set without
  ``previous_round``) and a **stale** one (a record present in the right slot but tagged with the
  wrong round -- not actually adjacent).
* :data:`~mambo_power.market.strategy.StrategyConfig` round-trips through
  ``model_dump_json``/``model_validate_json`` (via a minimal wrapper model, since the union itself
  is not a ``BaseModel``) and :func:`~mambo_power.market.strategy.build_strategy` resolves it to
  the right class.
* Purity: the same :class:`~mambo_power.market.strategy.Observation` handed to the same strategy
  twice returns equal offers, and a strategy's own attributes (e.g. ``MarkupStrategy.step``) are
  unchanged after the call.
"""

from __future__ import annotations

import pytest
from pydantic import BaseModel, ValidationError

from mambo_power.market.strategy import (
    MarkupConfig,
    MarkupStrategy,
    Observation,
    PriceTakerConfig,
    PriceTakerStrategy,
    RoundRecord,
    StrategyConfig,
    build_strategy,
)
from mambo_power.model import GeneratorCost, PiecewiseCost, PolynomialCost

# ---- fixture factory --------------------------------------------------------------------------


def _linear_cost(marginal: float, *, intercept: float = 0.0) -> PolynomialCost:
    """A degree-1 ``PolynomialCost``: ``cost(p) = marginal * p + intercept``."""
    return PolynomialCost(coefficients=[marginal, intercept])


def _record(round_index: int, offer_level: float, lmp: float, cleared_mw: float) -> RoundRecord:
    return RoundRecord(
        round_index=round_index, offer=_linear_cost(offer_level), lmp=lmp, cleared_mw=cleared_mw
    )


def _observation(
    round_index: int,
    true_cost_level: float = 20.0,
    *,
    p_min_mw: float = 0.0,
    p_max_mw: float = 300.0,
    true_cost: GeneratorCost | None = None,
    previous_round: RoundRecord | None = None,
    two_rounds_ago: RoundRecord | None = None,
) -> Observation:
    return Observation(
        round_index=round_index,
        true_cost=true_cost if true_cost is not None else _linear_cost(true_cost_level),
        p_min_mw=p_min_mw,
        p_max_mw=p_max_mw,
        previous_round=previous_round,
        two_rounds_ago=two_rounds_ago,
    )


class _ConfigWrapper(BaseModel):
    """The union itself is not a ``BaseModel`` (it is an ``Annotated`` alias), so a JSON
    round-trip needs one field of this shape somewhere — exactly how ``Generator.cost`` carries
    ``GeneratorCost``."""

    config: StrategyConfig


# ---- PriceTakerStrategy -------------------------------------------------------------------------


def test_price_taker_returns_true_cost_exactly() -> None:
    obs = _observation(0, true_cost=_linear_cost(20.0, intercept=5.0))
    offer = PriceTakerStrategy().offer(obs)
    assert isinstance(offer, PolynomialCost)
    assert offer.coefficients == [20.0, 5.0]  # exact, not approx


def test_price_taker_returns_true_cost_exactly_with_history_present() -> None:
    """A price-taker ignores its own history entirely -- present or not, the answer is the same."""
    true_cost = _linear_cost(20.0)
    obs = _observation(
        2,
        true_cost=true_cost,
        previous_round=_record(1, 24.0, 26.0, 150.0),
        two_rounds_ago=_record(0, 22.0, 24.0, 140.0),
    )
    offer = PriceTakerStrategy().offer(obs)
    assert isinstance(offer, PolynomialCost)
    assert offer.coefficients == true_cost.coefficients


def test_price_taker_returns_a_piecewise_true_cost_exactly() -> None:
    """AC-3(a) does not carve out an exception for a piecewise true cost, and this is the only
    path a PWL offer reaches the array builder in this wave -- the overlap guard (W1(c)) exists
    to protect exactly this path."""
    piecewise = PiecewiseCost(points=[(0.0, 0.0), (100.0, 2000.0), (300.0, 6500.0)])
    obs = _observation(0, true_cost=piecewise)
    offer = PriceTakerStrategy().offer(obs)
    assert isinstance(offer, PiecewiseCost)
    assert offer.points == piecewise.points
    assert offer is piecewise or offer == piecewise  # verbatim, not a reconstruction


def test_price_taker_handles_non_linear_polynomial_costs() -> None:
    """Unlike MarkupStrategy, a price-taker never reads inside the cost, so it is not scoped to
    linear costs at all."""
    quadratic = PolynomialCost(coefficients=[0.01, 20.0, 5.0])
    obs = _observation(0, true_cost=quadratic)
    offer = PriceTakerStrategy().offer(obs)
    assert isinstance(offer, PolynomialCost)
    assert offer.coefficients == [0.01, 20.0, 5.0]


# ---- MarkupStrategy: the base cases (round 0 and round 1) --------------------------------------


def test_markup_round_zero_offers_true_cost() -> None:
    """No offer[t-1] exists yet -- nothing to climb from -- so round 0 is identical to a
    price-taker's."""
    obs = _observation(0, true_cost_level=20.0)
    offer = MarkupStrategy(step=0.5).offer(obs)
    assert isinstance(offer, PolynomialCost)
    assert offer.coefficients == [20.0, 0.0]


def test_markup_round_one_probes_upward_by_one_step() -> None:
    """No offer[t-2] exists, so direction defaults to +1 and there is no profit to compare --
    round 1 is a pure upward probe from round 0's offer."""
    obs = _observation(
        1,
        true_cost_level=20.0,
        previous_round=_record(0, offer_level=20.0, lmp=25.0, cleared_mw=100.0),
    )
    offer = MarkupStrategy(step=0.5).offer(obs)
    assert isinstance(offer, PolynomialCost)
    assert offer.coefficients[0] == pytest.approx(20.5)


# ---- MarkupStrategy: the two-point rule ---------------------------------------------------------


def test_markup_continues_direction_when_last_move_raised_profit() -> None:
    """offer moved 20.0 -> 20.5 (up). profit went 500 -> 660 (better). Keep climbing up."""
    obs = _observation(
        2,
        true_cost_level=20.0,
        two_rounds_ago=_record(0, offer_level=20.0, lmp=25.0, cleared_mw=100.0),  # profit 500
        previous_round=_record(1, offer_level=20.5, lmp=26.0, cleared_mw=110.0),  # profit 660
    )
    offer = MarkupStrategy(step=0.5).offer(obs)
    assert isinstance(offer, PolynomialCost)
    assert offer.coefficients[0] == pytest.approx(21.0)


def test_markup_reverses_direction_when_last_move_lowered_profit() -> None:
    """offer moved 20.5 -> 21.0 (up). profit went 660 -> 360 (worse). Reverse: step back down."""
    obs = _observation(
        2,
        true_cost_level=20.0,
        two_rounds_ago=_record(0, offer_level=20.5, lmp=26.0, cleared_mw=110.0),  # profit 660
        previous_round=_record(1, offer_level=21.0, lmp=24.0, cleared_mw=90.0),  # profit 360
    )
    offer = MarkupStrategy(step=0.5).offer(obs)
    assert isinstance(offer, PolynomialCost)
    assert offer.coefficients[0] == pytest.approx(20.5)


def test_markup_direction_defaults_positive_on_zero_movement() -> None:
    """offer[t-1] == offer[t-2] (no movement to read a sign from) and profit did not worsen --
    direction stays the documented default, +1."""
    obs = _observation(
        2,
        true_cost_level=20.0,
        two_rounds_ago=_record(0, offer_level=20.0, lmp=22.0, cleared_mw=50.0),  # profit 100
        previous_round=_record(1, offer_level=20.0, lmp=23.0, cleared_mw=60.0),  # profit 180
    )
    offer = MarkupStrategy(step=0.5).offer(obs)
    assert isinstance(offer, PolynomialCost)
    assert offer.coefficients[0] == pytest.approx(20.5)


def test_markup_offer_never_goes_below_true_cost() -> None:
    """Direction says "keep going down" (last downward move helped), and the unfloored result
    would land below true cost -- it is clamped there instead."""
    obs = _observation(
        2,
        true_cost_level=20.0,
        two_rounds_ago=_record(0, offer_level=20.5, lmp=21.0, cleared_mw=50.0),  # profit 50
        previous_round=_record(1, offer_level=20.0, lmp=25.0, cleared_mw=80.0),  # profit 400
    )
    offer = MarkupStrategy(step=0.5).offer(obs)
    assert isinstance(offer, PolynomialCost)
    assert offer.coefficients[0] == pytest.approx(20.0)  # would be 19.5 unfloored


def test_markup_does_not_reverse_on_a_profit_tie_within_relative_tolerance() -> None:
    """The defect this guards against: an agent sitting at capacity while price is set elsewhere
    sees consecutive rounds whose LMP differs only by solver-noise ULPs -- here a ~1e-12 $/MWh
    difference, scaled by 300 MW to a ~3e-10 profit difference against a ~$6,000 profit level
    (relative ~5e-14, deep inside the 1e-9 relative band). offer[t-1] == offer[t-2] (both 45.0,
    at capacity, no movement), so direction defaults to +1; the tie must not flip it."""
    obs = _observation(
        2,
        true_cost_level=20.0,
        two_rounds_ago=_record(0, offer_level=45.0, lmp=40.0, cleared_mw=300.0),  # profit 6000.0
        previous_round=_record(
            1, offer_level=45.0, lmp=40.0 - 1e-12, cleared_mw=300.0
        ),  # profit ~6000.0 - 3e-10, a tie, not a real decrease
    )
    offer = MarkupStrategy(step=0.5).offer(obs)
    assert isinstance(offer, PolynomialCost)
    assert offer.coefficients[0] == pytest.approx(45.5)  # continues up, not reversed to 44.5


def test_markup_reverses_on_a_real_profit_decrease_at_the_same_zero_movement_baseline() -> None:
    """Companion to the tie test above, same zero-movement baseline (offer[t-1] == offer[t-2] ==
    45.0) but a real $3.00 profit drop (0.05% relative, far outside the 1e-9 tie band) -- this
    must still reverse."""
    obs = _observation(
        2,
        true_cost_level=20.0,
        two_rounds_ago=_record(0, offer_level=45.0, lmp=40.00, cleared_mw=300.0),  # profit 6000.0
        previous_round=_record(1, offer_level=45.0, lmp=39.99, cleared_mw=300.0),  # profit 5997.0
    )
    offer = MarkupStrategy(step=0.5).offer(obs)
    assert isinstance(offer, PolynomialCost)
    assert offer.coefficients[0] == pytest.approx(44.5)  # reversed down, not 45.5


# ---- MarkupStrategy: scope guards -----------------------------------------------------------


def test_markup_strategy_rejects_non_positive_step() -> None:
    with pytest.raises(ValueError, match="step must be positive"):
        MarkupStrategy(step=0.0)
    with pytest.raises(ValueError, match="step must be positive"):
        MarkupStrategy(step=-1.0)


def test_markup_strategy_rejects_non_linear_true_cost() -> None:
    quadratic = PolynomialCost(coefficients=[0.01, 20.0, 0.0])
    obs = _observation(0, true_cost=quadratic)
    with pytest.raises(NotImplementedError, match="linear PolynomialCost"):
        MarkupStrategy(step=0.5).offer(obs)


def test_markup_strategy_rejects_piecewise_true_cost() -> None:
    """A markup agent whose true cost is piecewise has no scalar to climb on -- it must fail
    loudly, not silently emit something approximate."""
    piecewise = PiecewiseCost(points=[(0.0, 0.0), (100.0, 2000.0)])
    obs = _observation(0, true_cost=piecewise)
    with pytest.raises(NotImplementedError, match="linear PolynomialCost"):
        MarkupStrategy(step=0.5).offer(obs)


# ---- purity: same observation in, same offer out, no attribute drift ---------------------------


def test_price_taker_is_a_pure_function_of_its_observation() -> None:
    strategy = PriceTakerStrategy()
    obs = _observation(0, true_cost_level=20.0)
    before = vars(strategy).copy()
    first = strategy.offer(obs)
    second = strategy.offer(obs)
    assert first == second
    assert vars(strategy) == before  # no attribute of the strategy moved


def test_markup_is_a_pure_function_of_its_observation() -> None:
    strategy = MarkupStrategy(step=0.5)
    obs = _observation(
        2,
        true_cost_level=20.0,
        two_rounds_ago=_record(0, offer_level=20.0, lmp=25.0, cleared_mw=100.0),
        previous_round=_record(1, offer_level=20.5, lmp=26.0, cleared_mw=110.0),
    )
    before = vars(strategy).copy()
    first = strategy.offer(obs)
    second = strategy.offer(obs)
    assert first == second
    assert vars(strategy) == before  # no attribute of the strategy moved, step included


# ---- Observation: the round-0/round-1 shapes, and the rejected bad histories -------------------


def test_observation_round_zero_has_no_history_at_all() -> None:
    obs = _observation(0)
    assert obs.previous_round is None
    assert obs.two_rounds_ago is None


def test_observation_round_one_has_exactly_one_prior_round() -> None:
    obs = _observation(1, previous_round=_record(0, 20.0, 25.0, 100.0))
    assert obs.previous_round is not None
    assert obs.two_rounds_ago is None


def test_observation_round_two_has_both_prior_rounds() -> None:
    obs = _observation(
        2,
        previous_round=_record(1, 20.5, 26.0, 110.0),
        two_rounds_ago=_record(0, 20.0, 25.0, 100.0),
    )
    assert obs.previous_round is not None
    assert obs.two_rounds_ago is not None


def test_observation_rejects_a_missing_previous_round() -> None:
    """two_rounds_ago set without previous_round is not a valid history -- there is no round it
    could have followed."""
    with pytest.raises(ValidationError, match="two_rounds_ago"):
        Observation(
            round_index=2,
            true_cost=_linear_cost(20.0),
            p_min_mw=0.0,
            p_max_mw=300.0,
            previous_round=None,
            two_rounds_ago=_record(0, 20.0, 25.0, 100.0),
        )


def test_observation_rejects_a_stale_previous_round() -> None:
    """previous_round must be round_index - 1's own record, not merely present -- a record from
    some other round is not "the immediately preceding round" just because it fills that slot."""
    with pytest.raises(ValidationError, match="stale"):
        Observation(
            round_index=3,
            true_cost=_linear_cost(20.0),
            p_min_mw=0.0,
            p_max_mw=300.0,
            previous_round=_record(1, 20.5, 26.0, 110.0),  # round 1, not round 2
            two_rounds_ago=None,
        )


def test_observation_rejects_a_stale_two_rounds_ago() -> None:
    """The literal case this check exists for: round 5's own outcome correctly fills
    previous_round for round 6, but two_rounds_ago is round 2's -- three rounds stale, not one."""
    with pytest.raises(ValidationError, match="stale"):
        Observation(
            round_index=6,
            true_cost=_linear_cost(20.0),
            p_min_mw=0.0,
            p_max_mw=300.0,
            previous_round=_record(5, 24.0, 30.0, 200.0),  # correctly round_index - 1
            two_rounds_ago=_record(2, 22.0, 28.0, 180.0),  # should be round 4, is round 2
        )


def test_observation_rejects_unknown_fields() -> None:
    with pytest.raises(ValidationError, match="[Ee]xtra"):
        Observation.model_validate(
            {
                "round_index": 0,
                "true_cost": _linear_cost(20.0).model_dump(),
                "p_min_mw": 0.0,
                "p_max_mw": 300.0,
                "rival_offer": 99.0,
            }
        )


def test_round_record_rejects_unknown_fields() -> None:
    with pytest.raises(ValidationError, match="[Ee]xtra"):
        RoundRecord.model_validate(
            {
                "round_index": 0,
                "offer": _linear_cost(20.0).model_dump(),
                "lmp": 25.0,
                "cleared_mw": 100.0,
                "rival_offer": 99.0,
            }
        )


# ---- StrategyConfig: discriminated union, JSON round-trip, build_strategy ----------------------


def test_strategy_config_round_trips_price_taker() -> None:
    original = _ConfigWrapper(config=PriceTakerConfig())
    again = _ConfigWrapper.model_validate_json(original.model_dump_json())
    assert isinstance(again.config, PriceTakerConfig)
    assert again.config.kind == "price_taker"
    assert isinstance(build_strategy(again.config), PriceTakerStrategy)


def test_strategy_config_round_trips_markup() -> None:
    original = _ConfigWrapper(config=MarkupConfig(step=0.5))
    again = _ConfigWrapper.model_validate_json(original.model_dump_json())
    assert isinstance(again.config, MarkupConfig)
    assert again.config.kind == "markup"
    assert again.config.step == 0.5
    resolved = build_strategy(again.config)
    assert isinstance(resolved, MarkupStrategy)
    assert resolved.step == 0.5


def test_strategy_config_rejects_unknown_kind() -> None:
    with pytest.raises(ValidationError):
        _ConfigWrapper.model_validate({"config": {"kind": "bogus"}})


def test_markup_config_rejects_non_positive_step() -> None:
    with pytest.raises(ValidationError):
        MarkupConfig(step=0.0)
    with pytest.raises(ValidationError):
        MarkupConfig(step=-1.0)


def test_build_strategy_price_taker_ignores_extra_state() -> None:
    strategy = build_strategy(PriceTakerConfig())
    assert isinstance(strategy, PriceTakerStrategy)
