"""Unit tests for :mod:`mambo_power.market.strategy` — the own-node ``Observation``/``Strategy``
seam (wave M7 W2, spec AC-3/AC-4/AC-5's shared building block; design D3, assumptions A4/A8/A9).

No market loop exists here (that is S4's ``market.agents``, not yet built) — every test drives
:class:`~mambo_power.market.strategy.Strategy` implementations directly against hand-built
:class:`~mambo_power.market.strategy.Observation` values, through this file's own fixture
factory (:func:`_linear_cost` / :func:`_record` / :func:`_observation`) rather than reconstructing
one ad hoc per test.

**What each behaviour is checked against.**

* :class:`~mambo_power.market.strategy.PriceTakerStrategy` must return the *exact* true-cost
  coefficients (``==``, not ``pytest.approx``) — AC-3(a)'s ``array_equal`` claim starts here.
* :class:`~mambo_power.market.strategy.MarkupStrategy`'s two-point climb is checked against the
  rule as measured (A4, ``.bionic/tmp/m7-a4-two-point-climb.py``): direction continues on improved
  profit, reverses on worsened profit, defaults to ``+1`` with no prior movement, and the result
  never drops below true cost.
* :class:`~mambo_power.market.strategy.Observation`'s round-0/round-1 shapes are constructed
  directly and asserted to carry ``None`` — never a fabricated zero-valued
  :class:`~mambo_power.market.strategy.RoundRecord`; the history-gap case is asserted to be
  rejected, not silently accepted.
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


def _record(offer_level: float, lmp: float, cleared_mw: float) -> RoundRecord:
    return RoundRecord(offer=_linear_cost(offer_level), lmp=lmp, cleared_mw=cleared_mw)


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
        previous_round=_record(24.0, 26.0, 150.0),
        two_rounds_ago=_record(22.0, 24.0, 140.0),
    )
    offer = PriceTakerStrategy().offer(obs)
    assert isinstance(offer, PolynomialCost)
    assert offer.coefficients == true_cost.coefficients


def test_price_taker_handles_non_linear_and_piecewise_costs() -> None:
    """Unlike MarkupStrategy, a price-taker never reads inside the cost, so it is not scoped to
    linear costs at all."""
    quadratic = PolynomialCost(coefficients=[0.01, 20.0, 5.0])
    obs = _observation(0, true_cost=quadratic)
    quadratic_offer = PriceTakerStrategy().offer(obs)
    assert isinstance(quadratic_offer, PolynomialCost)
    assert quadratic_offer.coefficients == [0.01, 20.0, 5.0]

    piecewise = PiecewiseCost(points=[(0.0, 0.0), (100.0, 2000.0)])
    obs2 = _observation(0, true_cost=piecewise)
    offer2 = PriceTakerStrategy().offer(obs2)
    assert isinstance(offer2, PiecewiseCost)
    assert offer2.points == [(0.0, 0.0), (100.0, 2000.0)]


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
        previous_round=_record(offer_level=20.0, lmp=25.0, cleared_mw=100.0),
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
        two_rounds_ago=_record(offer_level=20.0, lmp=25.0, cleared_mw=100.0),  # profit 500
        previous_round=_record(offer_level=20.5, lmp=26.0, cleared_mw=110.0),  # profit 660
    )
    offer = MarkupStrategy(step=0.5).offer(obs)
    assert isinstance(offer, PolynomialCost)
    assert offer.coefficients[0] == pytest.approx(21.0)


def test_markup_reverses_direction_when_last_move_lowered_profit() -> None:
    """offer moved 20.5 -> 21.0 (up). profit went 660 -> 360 (worse). Reverse: step back down."""
    obs = _observation(
        2,
        true_cost_level=20.0,
        two_rounds_ago=_record(offer_level=20.5, lmp=26.0, cleared_mw=110.0),  # profit 660
        previous_round=_record(offer_level=21.0, lmp=24.0, cleared_mw=90.0),  # profit 360
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
        two_rounds_ago=_record(offer_level=20.0, lmp=22.0, cleared_mw=50.0),  # profit 100
        previous_round=_record(offer_level=20.0, lmp=23.0, cleared_mw=60.0),  # profit 180
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
        two_rounds_ago=_record(offer_level=20.5, lmp=21.0, cleared_mw=50.0),  # profit 50
        previous_round=_record(offer_level=20.0, lmp=25.0, cleared_mw=80.0),  # profit 400
    )
    offer = MarkupStrategy(step=0.5).offer(obs)
    assert isinstance(offer, PolynomialCost)
    assert offer.coefficients[0] == pytest.approx(20.0)  # would be 19.5 unfloored


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
    piecewise = PiecewiseCost(points=[(0.0, 0.0), (100.0, 2000.0)])
    obs = _observation(0, true_cost=piecewise)
    with pytest.raises(NotImplementedError, match="linear PolynomialCost"):
        MarkupStrategy(step=0.5).offer(obs)


# ---- purity: same observation in, same offer out, no attribute drift ---------------------------


def test_price_taker_is_a_pure_function_of_its_observation() -> None:
    strategy = PriceTakerStrategy()
    obs = _observation(0, true_cost_level=20.0)
    first = strategy.offer(obs)
    second = strategy.offer(obs)
    assert first == second


def test_markup_is_a_pure_function_of_its_observation() -> None:
    strategy = MarkupStrategy(step=0.5)
    obs = _observation(
        2,
        true_cost_level=20.0,
        two_rounds_ago=_record(offer_level=20.0, lmp=25.0, cleared_mw=100.0),
        previous_round=_record(offer_level=20.5, lmp=26.0, cleared_mw=110.0),
    )
    first = strategy.offer(obs)
    step_before = strategy.step
    second = strategy.offer(obs)
    assert first == second
    assert strategy.step == step_before  # no attribute of the strategy moved


# ---- Observation: the round-0/round-1 shapes, and the rejected gap -----------------------------


def test_observation_round_zero_has_no_history_at_all() -> None:
    obs = _observation(0)
    assert obs.previous_round is None
    assert obs.two_rounds_ago is None


def test_observation_round_one_has_exactly_one_prior_round() -> None:
    obs = _observation(1, previous_round=_record(20.0, 25.0, 100.0))
    assert obs.previous_round is not None
    assert obs.two_rounds_ago is None


def test_observation_round_two_has_both_prior_rounds() -> None:
    obs = _observation(
        2,
        previous_round=_record(20.5, 26.0, 110.0),
        two_rounds_ago=_record(20.0, 25.0, 100.0),
    )
    assert obs.previous_round is not None
    assert obs.two_rounds_ago is not None


def test_observation_rejects_a_history_gap() -> None:
    """two_rounds_ago set without previous_round is not a valid history -- there is no round it
    could have followed."""
    with pytest.raises(ValidationError, match="two_rounds_ago"):
        Observation(
            round_index=2,
            true_cost=_linear_cost(20.0),
            p_min_mw=0.0,
            p_max_mw=300.0,
            previous_round=None,
            two_rounds_ago=_record(20.0, 25.0, 100.0),
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
