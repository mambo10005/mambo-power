"""``market.strategy``: the seam between an agent's own history and the offer it makes next
(wave M7 W2, design D3).

**Own-node, not world-model.** :class:`Observation` carries exactly what one generator can see
about itself — its own true cost curve and capacity, the round it is bidding into, and its own
**last two rounds** of ``(offer, bus LMP, cleared MW)`` — and nothing about any rival, any other
bus, or the network. That is deliberate (D3(b)): a strategy that could reconstruct the clearing or
infer the merit order could short-circuit the game the fixed-point loop in ``market.agents``
(W3) exists to play out. Two rounds, not one, because a one-round view can tell an agent whether
it is marginal but not whether its **last move helped** — measured 2026-08-28 (spec A4), the rules
computable from one round either cycle or settle at a markup gain of $0.02/h. The first two
rounds necessarily have fewer than two prior points; :class:`Observation` says so explicitly
through :attr:`Observation.previous_round` / :attr:`Observation.two_rounds_ago` being ``None``,
never through a fabricated zero-valued :class:`RoundRecord`.

**Stateless by construction.** :class:`Strategy` is a :class:`typing.Protocol` with one method,
``offer(observation) -> GeneratorCost``, and every strategy here is a pure function of that single
argument: it reads no attribute of itself that isn't a fixed parameter set at construction (e.g.
:class:`MarkupStrategy`'s ``step``), and it writes nothing back. The loop supplies the history by
constructing a fresh :class:`Observation` each round; a strategy that cached anything between
calls would make a run something other than a pure function of ``(network, strategies,
tolerance)``, which is exactly the property scope answer 2 asks for.

**Structural, not nominal.** A :class:`typing.Protocol` was chosen over an ABC (D3(a)) because the
repo has no other ABC to match and the interface is one method: mypy checks conformance
structurally, and an in-process caller may pass any object with a matching ``offer`` method
without inheriting from anything. What crosses the jobs surface, though, is never a callable —
:data:`StrategyConfig` is a discriminated union on ``kind`` (mirroring
:data:`~mambo_power.model.entities.GeneratorCost` at ``model/entities.py:87``), and
:func:`build_strategy` resolves a config to an instance. A config round-trips through JSON; a
:class:`Strategy` instance does not need to.

**What ships, and what does not.** :class:`PriceTakerStrategy` offers true cost, unchanged, every
round — the AC-3 reproduction depends on this being exact, not approximate.
:class:`MarkupStrategy` is a fixed-step two-point hill climb on the agent's own profit (A4): keep
the last direction if it raised profit, reverse it if not, and never offer below true cost. It is
scoped to a **linear** :class:`~mambo_power.model.entities.PolynomialCost` (``coefficients =
[c1, c0]``) because that is the only cost shape this wave's fixtures and A4's own measurement use;
a piecewise or higher-degree cost has no established single scalar to climb on, so
:class:`MarkupStrategy` raises rather than inventing one. Both strategies are provably *local*
best-responders (Not Doing): neither evaluates a candidate offer against a market clearing, so
neither can be a global best response. Stateful, learning or seeded strategies are out of scope
(Not Doing) — the :class:`Strategy` Protocol does not forbid one, but this module ships none.
"""

from __future__ import annotations

from typing import Annotated, Literal, Protocol

from pydantic import BaseModel, ConfigDict, Field, model_validator

from mambo_power.model import GeneratorCost, PolynomialCost

__all__ = [
    "MarkupConfig",
    "MarkupStrategy",
    "Observation",
    "PriceTakerConfig",
    "PriceTakerStrategy",
    "RoundRecord",
    "Strategy",
    "StrategyConfig",
    "build_strategy",
]


class RoundRecord(BaseModel):
    """One past round's own-node outcome: what the agent offered, and what it got for it.

    ``offer`` is the whole :class:`~mambo_power.model.entities.GeneratorCost` the agent bid that
    round (not just a scalar), because that is what the loop actually held; a strategy that needs
    a scalar reading of it derives one, as :class:`MarkupStrategy` does.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    offer: GeneratorCost = Field(description="The generator's own offer that round.")
    lmp: float = Field(description="The LMP at the generator's own bus that round, $/MWh.")
    cleared_mw: float = Field(description="The generator's own cleared dispatch that round, MW.")


class Observation(BaseModel):
    """An agent's own-node view of the market, as of the round it is about to bid into.

    Own-node only (D3(b)): the generator's own true cost and capacity, the round index, and its
    own last two rounds' outcomes. Nothing here names another generator, another bus, or the
    clearing as a whole.

    ``previous_round`` and ``two_rounds_ago`` are ``None`` exactly when that round has not
    happened: both are ``None`` for the very first round's observation (there is no round to
    report), and only ``previous_round`` is set for the second round's (there is one prior round,
    not two). ``None`` is a documented "this round does not exist yet" marker — never a silent
    zero-valued :class:`RoundRecord` standing in for missing history. A gap (``two_rounds_ago``
    set while ``previous_round`` is not) is not a valid history and is rejected below.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    round_index: int = Field(ge=0, description="The round for which this offer is being decided.")
    true_cost: GeneratorCost = Field(
        description="The generator's own true cost curve (Generator.cost, never the offer)."
    )
    p_min_mw: float = Field(description="The generator's own lower active limit, MW.")
    p_max_mw: float = Field(description="The generator's own upper active limit, MW.")
    previous_round: RoundRecord | None = Field(
        default=None,
        description="Round round_index - 1's own outcome; None when round_index == 0, i.e. "
        "there is no prior round at all.",
    )
    two_rounds_ago: RoundRecord | None = Field(
        default=None,
        description="Round round_index - 2's own outcome; None when round_index <= 1, i.e. "
        "there is at most one prior round.",
    )

    @model_validator(mode="after")
    def _history_has_no_gap(self) -> Observation:
        if self.two_rounds_ago is not None and self.previous_round is None:
            raise ValueError(
                "Observation.two_rounds_ago is set but Observation.previous_round is not -- "
                "an own-node history cannot skip the immediately preceding round"
            )
        return self


class Strategy(Protocol):
    """One generator's bidding rule: its own observation in, its next offer out.

    Structural (D3(a)): any object with a matching ``offer`` method satisfies this Protocol, no
    inheritance required. Every implementation here holds no state that changes between calls —
    see the module docstring.
    """

    def offer(self, observation: Observation) -> GeneratorCost:
        """The generator's offer for ``observation.round_index``, a pure function of
        *observation*."""
        ...


class PriceTakerStrategy:
    """Offers the generator's own true cost, unchanged, every round.

    Ignores ``observation.round_index`` and both history fields entirely -- there is nothing a
    price-taker's own past has to tell it. AC-3 depends on this being the true cost *exactly*
    (the same coefficients, not a numerically close approximation), which is what returning
    ``observation.true_cost`` verbatim guarantees.
    """

    def offer(self, observation: Observation) -> GeneratorCost:
        """*observation.true_cost*, verbatim."""
        return observation.true_cost


def _marginal_offer(cost: GeneratorCost, *, what: str) -> float:
    """The scalar $/MWh level :class:`MarkupStrategy` climbs on.

    Scoped to a linear :class:`PolynomialCost` (``coefficients = [c1, c0]``): its p^1 coefficient
    is the marginal cost, and that is the only shape this wave's fixtures (and the A4 measurement
    that validated the climb rule) use. Anything else -- a piecewise cost, or a polynomial with
    any other degree -- has no scalar reading this strategy has established, so it raises rather
    than picking one silently.
    """
    if not isinstance(cost, PolynomialCost) or len(cost.coefficients) != 2:
        shape = (
            f"kind={cost.kind!r}, coefficients={cost.coefficients!r}"
            if isinstance(cost, PolynomialCost)
            else f"kind={cost.kind!r}"
        )
        raise NotImplementedError(
            f"MarkupStrategy supports only a linear PolynomialCost (coefficients=[c1, c0]) as "
            f"{what}; got {shape}"
        )
    return cost.coefficients[0]


def _with_marginal_offer(true_cost: GeneratorCost, level: float) -> GeneratorCost:
    """A copy of *true_cost* (itself already validated linear by the caller) with its p^1
    coefficient replaced by *level*; the intercept and startup/shutdown terms carry over from the
    true cost unchanged, so only the marginal price component is ever marked up.
    """
    assert isinstance(true_cost, PolynomialCost)
    return true_cost.model_copy(update={"coefficients": [level, true_cost.coefficients[1]]})


class MarkupStrategy:
    """A fixed-step two-point hill climb on the agent's own profit (A4, measured 2026-08-28).

    **The rule.** Let ``offer[t-1]`` / ``offer[t-2]`` be the marginal-cost levels of the last two
    rounds' offers and ``profit[t-1]`` / ``profit[t-2]`` be ``(own bus LMP - own true marginal
    cost) * own cleared MW`` at those rounds:

    * *direction* is ``sign(offer[t-1] - offer[t-2])``, defaulting to ``+1`` when there is no
      prior movement to read (``offer[t-1] == offer[t-2]``, or ``t-2`` does not exist yet);
    * *direction* reverses if the last move made things worse: ``profit[t-1] < profit[t-2]``;
    * the new offer is ``offer[t-1] + direction * step``, **floored at the agent's own true
      marginal cost** -- a markup never goes negative relative to cost.

    **The two base cases.** Round 0 (``observation.previous_round is None``) has no ``offer[t-1]``
    for the rule to start from, so it offers true cost, exactly as :class:`PriceTakerStrategy`
    would -- there is nothing yet to have an opinion about. Round 1
    (``observation.two_rounds_ago is None``) has ``offer[t-1]`` but no ``offer[t-2]``: direction
    defaults to ``+1`` and there is no profit comparison to make, so it is a pure upward probe.

    **Why this is a local best response, not a global one (Not Doing).** The rule only ever
    compares the two most recent profits it has actually observed; it never evaluates a candidate
    offer against a market clearing. Where a competing unit creates a discontinuity between this
    agent's cost and its true profit peak, the climb provably stalls at the local optimum on its
    side of that discontinuity (A4 measured: $9,497.52 against a derivable $12,250). This module
    does not claim otherwise.

    ``step`` also fixes the loop's convergence tolerance from the other side (A9): a fixed-step
    climber oscillates by exactly two steps about its optimum once it arrives, so
    ``market.agents``' ``offer_tol`` must be ``>= 2 * step`` for that oscillation to read as
    converged rather than as a cycle.
    """

    def __init__(self, step: float) -> None:
        if step <= 0:
            raise ValueError(f"MarkupStrategy.step must be positive, got {step}")
        self.step = step

    def offer(self, observation: Observation) -> GeneratorCost:
        """The two-point climb described above, applied to *observation*'s own history."""
        true_level = _marginal_offer(observation.true_cost, what="observation.true_cost")
        previous = observation.previous_round
        if previous is None:
            return observation.true_cost

        offer_prev = _marginal_offer(previous.offer, what="observation.previous_round.offer")
        two_ago = observation.two_rounds_ago
        if two_ago is None:
            direction = 1.0
        else:
            offer_2ago = _marginal_offer(two_ago.offer, what="observation.two_rounds_ago.offer")
            direction = 1.0 if offer_prev >= offer_2ago else -1.0
            profit_prev = (previous.lmp - true_level) * previous.cleared_mw
            profit_2ago = (two_ago.lmp - true_level) * two_ago.cleared_mw
            if profit_prev < profit_2ago:
                direction = -direction

        new_level = max(true_level, offer_prev + direction * self.step)
        return _with_marginal_offer(observation.true_cost, new_level)


class PriceTakerConfig(BaseModel):
    """Config for :class:`PriceTakerStrategy`. No parameters: it always offers true cost."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    kind: Literal["price_taker"] = "price_taker"


class MarkupConfig(BaseModel):
    """Config for :class:`MarkupStrategy`."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    kind: Literal["markup"] = "markup"
    step: float = Field(
        gt=0,
        description="Fixed offer step, $/MWh per round. Bounds the loop's own convergence "
        "tolerance from below (A9): offer_tol must be >= 2 * step.",
    )


StrategyConfig = Annotated[PriceTakerConfig | MarkupConfig, Field(discriminator="kind")]
"""What crosses JSON: a discriminated union on ``kind``, mirroring
:data:`~mambo_power.model.entities.GeneratorCost` at ``model/entities.py:87``. Never a callable --
:func:`build_strategy` is the one place a config becomes a :class:`Strategy` instance."""


def build_strategy(config: StrategyConfig) -> Strategy:
    """Resolve a :data:`StrategyConfig` to the :class:`Strategy` instance it names."""
    if config.kind == "price_taker":
        return PriceTakerStrategy()
    return MarkupStrategy(step=config.step)
