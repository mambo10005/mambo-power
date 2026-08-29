"""``market.agents``: the fixed-point loop that lets generators *bid* instead of being dispatched
at cost (wave M7 W3).

**One round.** Every agent's :class:`~mambo_power.market.strategy.Strategy` is handed its own
:class:`~mambo_power.market.strategy.Observation` -- its own true cost and capacity, the round
index, and its own last two rounds of ``(offer, bus LMP, cleared MW)`` -- and returns a
:class:`~mambo_power.model.GeneratorCost`. Those offers become an **overlay**:
:func:`mambo_power.opf.gen_cost_coeffs` is called with ``costs=<the offer map>``, so the offered
curve reaches :func:`~mambo_power.opf.dc_opf.dc_opf` through the *same* union-to-coefficients
mapping a true cost does (spec A2), and ``Generator.cost`` is never written to. That is the whole
of AC-2: ``Scenario`` and ``Network`` come out of a run byte-identical, while the coefficients the
array builder saw differ from the true ones.

**Not a delegation.** The clearing here is the general array-level path --
``gen_cost_coeffs`` + :func:`mambo_power.market.nodal.load_bid_coeffs` + ``dc_opf`` -- and never a
call to :func:`mambo_power.market.nodal.solve_nodal`, deliberately (design, "Rejected
alternatives"): an all-price-taker short-circuit would make AC-3 true by construction while
bypassing the loop, the overlay and the offer map it exists to prove honest.

**Updates are simultaneous** (W3, A8), in ``NetworkArrays.gen_ids`` order where order is
observable at all: every agent's round-``r`` offer is computed from round ``r-1``'s clearing,
before any of them is cleared. An earlier draft specified round-robin on the strength of a sweep
of *exact* best response, which cycles under simultaneous updates in five of six duopoly
configurations -- but an exact best response requires clearing the market, which the own-node
observation deliberately withholds, so that sweep is not about the strategies this wave ships.
Measured with the strategies that are computable, both orders reach the same point on the AC-5
duopoly. The rule is part of the contract, not an implementation detail.

**Termination, and why it is classified by amplitude** (W3, A9). A fixed-step climber never comes
to rest: it oscillates by two steps about its optimum -- three when the optimum sits halfway
between two of its grid points -- which is the expected end state and not a failure. So the loop
watches for a **repeated state** and then measures the **amplitude** of the cycle it found:
amplitude within ``offer_tol`` is convergence, amplitude above it is a genuine
cycle, and neither of those is the iteration cap. Reporting a cycle as a cap hit -- or as
convergence -- would be a confident wrong diagnosis of exactly the kind this epic has named in
every wave, which is why :class:`~mambo_power.results.agents.MarketAgentsResult` spends three
enumerated words on it instead of a flag.

**Settlement is computed once**, on the final round's clearing, at the final round's prices --
never accumulated across rounds. The intermediate rounds are the agents' search, not a sequence of
markets that anybody was paid for.
"""

from __future__ import annotations

import math
import time
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime

import numpy as np
import numpy.typing as npt
from pydantic import BaseModel, ConfigDict, Field, model_validator

import mambo_power
from mambo_power.market._clearing import clearing_rows
from mambo_power.market.nodal import load_bid_coeffs
from mambo_power.market.strategy import (
    MarkupStrategy,
    Observation,
    RoundRecord,
    Strategy,
    StrategyConfig,
    build_strategy,
)
from mambo_power.model import GeneratorCost, Network, PiecewiseCost, PolynomialCost, Scenario
from mambo_power.numerics.arrays import NetworkArrays
from mambo_power.numerics.ptdf import ptdf as compute_ptdf
from mambo_power.opf import gen_cost_coeffs
from mambo_power.opf.dc_opf import (
    LmpBreakdown,
    OpfDcOptions,
    OpfSolution,
    dc_opf,
    lmp_decomposition,
)
from mambo_power.results import BusLmpResult, ResultProvenance
from mambo_power.results.agents import AgentOfferResult, MarketAgentsResult, TerminationReason

__all__ = [
    "AgentSetError",
    "MarketAgentsOptions",
    "solve_agents",
]

FloatArray = npt.NDArray[np.float64]

DEFAULT_MAX_ITERATIONS = 200
"""Default ``max_iterations``. A bound, not a target: the wave's own slowest measured climb is
the AC-5 duopoly at 84 update rounds with a step of $0.50/MWh, and halving the step roughly
doubles the count (84 / 44 / 24 rounds at steps of 0.5 / 1.0 / 2.0, measured 2026-08-28), so 200
covers a step of $0.25/MWh as well. A run that reaches it is *reported* as having reached it
(``termination_reason == "iteration_cap"``), never quietly presented as settled."""


class AgentSetError(ValueError):
    """A caller mistake in the *agent set* -- how ``options.strategies`` (or the in-process
    ``strategies`` argument) relates to the network -- caught before any solve starts.

    A :class:`ValueError` **subclass**, deliberately, for the same two reasons as
    :class:`~mambo_power.market.zonal.UnzonedBusError`. It stays a ``ValueError`` because that is
    what :func:`solve_agents` has always raised for these and what an in-process caller catches.
    It is a distinguishable *type* because ``jobs``' runner cannot otherwise tell it apart from
    any other ``ValueError`` a solve might raise -- and the clearing's own
    :class:`~mambo_power.opf.dc_opf.NonConvexCostError` / ``NonConcaveBidError`` *are*
    ``ValueError`` subclasses. Catching bare ``ValueError`` relabelled an engine rejection of a
    non-convex cost as ``VALIDATION`` at ``options.strategies``, a field the caller need not have
    set, while ``market.nodal`` reported the same network as ``INTERNAL`` (audit finding 2, M7
    S10). Only this type maps to ``VALIDATION``; everything else keeps the verdict every other
    kind gives it.

    Raised by :func:`_resolve_agents` (two agent sources at once, a strategy on a generator the
    network does not have, one its arrays do not carry, one with no cost, a
    :class:`~mambo_power.market.strategy.MarkupStrategy` step too coarse for ``offer_tol``) and by
    :func:`_initial_offers` (a strategy that cannot bid on its generator's true cost).
    """


class MarketAgentsOptions(BaseModel):
    """Options of a ``market.agents`` run: who bids, how long the loop may run, and what counts
    as settled.

    Sits beside :func:`solve_agents` the way
    :class:`~mambo_power.market.zonal.MarketZonalOptions` sits beside its own solver. Like that
    one, its fields are *market-design data* rather than solver tuning -- which strategy each
    generator plays is a choice about the game being simulated, not a knob on HiGHS.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    strategies: dict[str, StrategyConfig] = Field(
        default_factory=dict,
        description="Generator id -> the bidding rule that generator plays. A generator not "
        "named here is not an agent: it offers its own true cost, exactly as market.nodal would "
        "clear it. An empty mapping is therefore meaningful and not a missing argument -- it is "
        "a market in which nobody bids strategically.",
    )
    max_iterations: int = Field(
        default=DEFAULT_MAX_ITERATIONS,
        gt=0,
        description="Most best-response update rounds to run after round 0 (which is the initial "
        "offer and responds to nothing). Reaching it ends the run with "
        'termination_reason == "iteration_cap" and converged False; it is never reported as a '
        "cycle, and a cycle is never reported as it.",
    )
    offer_tol: float = Field(
        default=1e-9,
        gt=0,
        description="Largest offer-vector oscillation amplitude, in cost-coefficient units, that "
        "still counts as converged once the loop detects a repeated state. This is a "
        "*derived* quantity, not a tuning knob: a fixed-step climber settles into an oscillation "
        "of two steps about an on-grid optimum and three about a half-grid one, so a markup "
        "agent of step s needs offer_tol >= 3*s (MarkupStrategy.min_offer_tol) -- which the "
        "validator below enforces rather than hopes for. The default admits only an offer "
        "vector that has genuinely come to rest, which is what an all-price-taker run does.",
    )

    @model_validator(mode="after")
    def _offer_tol_admits_every_stepped_strategy(self) -> MarketAgentsOptions:
        """Reject an ``offer_tol`` below any markup agent's own
        :attr:`~mambo_power.market.strategy.MarkupStrategy.min_offer_tol` (``3 * step``).

        Without this the run would be reported as a **cycle** the moment the climb arrived at its
        optimum and started dithering -- the settled oscillation is what arrival *looks like*, so
        a tolerance narrower than it turns every successful climb into a false non-convergence
        report. A9 calls the constraint derived rather than tuned; deriving it and then not
        checking it would leave the derivation as a comment. The rule and its text live in
        :func:`_offer_tol_shortfall`, shared with the object path in :func:`_resolve_agents`.
        """
        for gen_id, config in self.strategies.items():
            if config.kind != "markup":
                continue
            message = _offer_tol_shortfall(self.offer_tol, gen_id, build_strategy(config))
            if message is not None:
                raise ValueError(message)
        return self


def _offer_tol_shortfall(offer_tol: float, gen_id: str, strategy: Strategy) -> str | None:
    """The one text for A9's derived constraint, or ``None`` when *offer_tol* admits *strategy*.

    Only a :class:`~mambo_power.market.strategy.MarkupStrategy` has a settling orbit to hold
    ``offer_tol`` to; every other strategy passes. Both enforcement points -- the config path's
    pydantic validator and the object path's :func:`_resolve_agents` -- call this, so there is one
    rule, one constant (``MarkupStrategy.min_offer_tol``) and one message.
    """
    if not isinstance(strategy, MarkupStrategy) or offer_tol >= strategy.min_offer_tol:
        return None
    return (
        f"offer_tol={offer_tol} is below 3 * step for the markup strategy on generator "
        f'"{gen_id}" (step={strategy.step}, so 3 * step={strategy.min_offer_tol}). A fixed-step '
        f"climber settles into an oscillation of two steps about its optimum -- three when the "
        f"optimum sits halfway between two of its grid points -- so a narrower tolerance would "
        f"report that arrival as a cycle. Raise offer_tol to at least "
        f"{strategy.min_offer_tol}, or lower the step."
    )


@dataclass(frozen=True)
class _Agent:
    """One resolved agent: where it sits in the arrays, what it truly costs, and how it bids."""

    id: str
    index: int
    bus_index: int
    label: str
    strategy: Strategy
    true_cost: GeneratorCost
    p_min_mw: float
    p_max_mw: float


@dataclass(frozen=True)
class _Round:
    """One cleared round: what was offered, the coefficients that carried it, and what came back."""

    offers: dict[str, GeneratorCost]
    cost_coeffs: FloatArray
    dispatch_mw: FloatArray
    lmp: FloatArray


def _cost_at(cost: GeneratorCost, p_mw: float) -> float:
    """*cost* evaluated at *p_mw*, $/h -- the one reading of a
    :class:`~mambo_power.model.GeneratorCost` this module needs, and the reading
    :attr:`~mambo_power.results.agents.AgentOfferResult.markup`'s identity is stated in.

    Polynomial: Horner over ``coefficients`` (highest order first, as
    :class:`~mambo_power.model.PolynomialCost` documents). Piecewise: linear on the segment
    containing *p_mw*, extrapolated along the first or last segment outside the breakpoint range
    -- an offer curve is not obliged to span the dispatch the clearing found, and refusing to
    evaluate there would leave a markup unreportable for no gain. ``startup``/``shutdown`` are not
    part of an hourly cost and are not read here.
    """
    if cost.kind == "polynomial":
        total = 0.0
        for coefficient in cost.coefficients:
            total = total * p_mw + coefficient
        return total
    points = cost.points
    lower = 0
    for k in range(len(points) - 1):
        if p_mw >= points[k][0]:
            lower = k
    (p0, c0), (p1, c1) = points[lower], points[lower + 1]
    return c0 + (c1 - c0) * (p_mw - p0) / (p1 - p0)


def _resolve_agents(
    net: Network,
    arr: NetworkArrays,
    options: MarketAgentsOptions,
    strategies: Mapping[str, Strategy] | None,
) -> list[_Agent]:
    """The agent list, in ``NetworkArrays`` generator order (A8), from exactly one source.

    Every rejection here is a *caller* mistake caught before any solve, so
    :func:`mambo_power.jobs.run` can classify it as a bad request rather than an engine fault
    (AC-6): two sources of agents at once, a strategy naming a generator the network does not
    have, a strategy on a generator the arrays do not carry (out of service, or on a bus that
    is -- its offer would be silently ignored), a strategy on a generator with no
    ``Generator.cost`` (there is no true cost for it to depart from, and an
    :class:`~mambo_power.market.strategy.Observation` cannot be built without one), an
    injected :class:`~mambo_power.market.strategy.MarkupStrategy` whose step is too coarse for
    ``offer_tol`` (the config path's own validator, applied to the object path). The fifth
    rejection -- a strategy that cannot bid on its generator's true cost at all -- needs the
    strategy's own answer, and lives in :func:`_initial_offers`, which runs next.
    """
    if strategies is not None and options.strategies:
        raise AgentSetError(
            "solve_agents was given both options.strategies and its own strategies argument -- "
            "an agent set has exactly one source, so pass configs (which cross JSON) or Strategy "
            "objects (which do not), never both"
        )
    resolved: dict[str, tuple[str, Strategy]] = (
        {gen_id: (type(obj).__name__, obj) for gen_id, obj in strategies.items()}
        if strategies is not None
        else {
            gen_id: (config.kind, build_strategy(config))
            for gen_id, config in options.strategies.items()
        }
    )
    gens_by_id = {gen.id: gen for gen in net.generators}
    index_of = {gen_id: i for i, gen_id in enumerate(arr.gen_ids)}
    for gen_id, (_, strategy) in resolved.items():
        if gen_id not in gens_by_id:
            raise AgentSetError(
                f'a strategy names generator "{gen_id}", which is not in the network'
            )
        if gen_id not in index_of:
            raise AgentSetError(
                f'a strategy names generator "{gen_id}", which is in the network but not in its '
                f"arrays (out of service, or on a bus that is) -- its offer would never reach "
                f"the clearing"
            )
        if gens_by_id[gen_id].cost is None:
            raise AgentSetError(
                f'a strategy names generator "{gen_id}", which has no cost -- an agent bids '
                f"relative to its own true cost, and there is none to observe"
            )
        message = _offer_tol_shortfall(options.offer_tol, gen_id, strategy)
        if message is not None:
            raise AgentSetError(message)
    agents = []
    for gen_id in arr.gen_ids:
        if gen_id not in resolved:
            continue
        label, strategy = resolved[gen_id]
        gen = gens_by_id[gen_id]
        cost = gen.cost
        assert cost is not None  # checked above
        agents.append(
            _Agent(
                id=gen_id,
                index=index_of[gen_id],
                bus_index=int(arr.gen_bus[index_of[gen_id]]),
                label=label,
                strategy=strategy,
                true_cost=cost,
                p_min_mw=gen.p_min_mw,
                p_max_mw=gen.p_max_mw,
            )
        )
    return agents


def _initial_offers(agents: list[_Agent]) -> dict[str, GeneratorCost]:
    """Round 0's offers -- every agent's answer to an observation with no history -- and the
    fifth up-front rejection: a strategy that **cannot bid on its generator's true cost**.

    Found by *asking the strategy*, not by knowing its internals: a ``NotImplementedError`` from
    the round-0 ``offer`` (a :class:`~mambo_power.market.strategy.MarkupStrategy` on a quadratic
    or piecewise cost, which is every generator in every bundled MATPOWER case) is re-raised as
    :class:`AgentSetError` naming the generator, with the strategy's own exception chained as the
    cause,
    so :func:`mambo_power.jobs.run` reports it as ``VALIDATION`` like the other four
    :func:`_resolve_agents` rejections. The offers returned *are* round 0's -- the loop does not
    ask again -- so a strategy sees exactly one observation per round. Without this the
    strategy's exception escaped the loop mid-run and reached ``jobs`` as ``INTERNAL``: the first
    mistake a user attaching a markup agent to case14 makes, filed as an engine fault (walk
    finding, M7 S9).
    """
    offers: dict[str, GeneratorCost] = {}
    for agent in agents:
        try:
            offers[agent.id] = _checked_offer(agent, _observation(agent, 0, []))
        except NotImplementedError as exc:
            raise AgentSetError(
                f'the {agent.label} strategy on generator "{agent.id}" cannot bid on that '
                f"generator's true cost: {exc}"
            ) from exc
    return offers


def _checked_offer(agent: _Agent, observation: Observation) -> GeneratorCost:
    """*agent*'s strategy's offer for *observation*, checked to be a
    :class:`~mambo_power.model.GeneratorCost` **where it was returned**.

    A strategy that returns ``None`` (a forgotten ``return``) or any other object used to fail
    only after that round's clearing, as a pydantic error on the :class:`RoundRecord` the loop
    builds from history -- the wrong layer, and a name the caller never wrote (walk finding, M7
    S9). ``TypeError`` here names the generator and what came back, before any clearing.
    """
    offer = agent.strategy.offer(observation)
    if not isinstance(offer, PolynomialCost | PiecewiseCost):
        raise TypeError(
            f'the {agent.label} strategy on generator "{agent.id}" returned {offer!r} for round '
            f"{observation.round_index}; a Strategy.offer must return a GeneratorCost "
            f"(PolynomialCost or PiecewiseCost)"
        )
    return offer


def _observation(agent: _Agent, round_index: int, history: list[_Round]) -> Observation:
    """*agent*'s own-node view of round *round_index*, built from *history*'s last two rounds.

    The history handed over is contiguous by construction -- ``history[k]`` *is* round ``k``,
    because this loop never skips or restarts a round -- which is the property
    :class:`~mambo_power.market.strategy.Observation`'s own validator exists to enforce
    independently. If a future change ever wants to skip a round, that is a change to this
    contract to surface, not a validator to work around.
    """

    def record(index: int) -> RoundRecord:
        past = history[index]
        return RoundRecord(
            round_index=index,
            offer=past.offers[agent.id],
            lmp=float(past.lmp[agent.bus_index]),
            cleared_mw=float(past.dispatch_mw[agent.index]),
        )

    return Observation(
        round_index=round_index,
        true_cost=agent.true_cost,
        p_min_mw=agent.p_min_mw,
        p_max_mw=agent.p_max_mw,
        previous_round=record(round_index - 1) if round_index >= 1 else None,
        two_rounds_ago=record(round_index - 2) if round_index >= 2 else None,
    )


def _offer_key(offers: Mapping[str, GeneratorCost], agents: list[_Agent]) -> tuple[str, ...]:
    """A hashable, exact reading of one round's offer vector, in agent order.

    Exact -- the offers' own JSON, not a rounded numeric view. A tolerance here would be a
    calibration constant nothing derives, and its failure mode is the bad one: two genuinely
    different offer vectors declared identical, so a run that is still moving reports as settled.
    The cost of exactness is the opposite and benign: a strategy whose offers drift by accumulated
    float error never repeats a state exactly and ends at the iteration cap, which is reported as
    such.
    """
    return tuple(offers[agent.id].model_dump_json() for agent in agents)


def _amplitude(window: list[_Round], agents: list[_Agent]) -> float:
    """Peak-to-peak spread of the agents' offer coefficients over one full cycle *window*.

    Read from the ``(n_gen, 3)`` coefficient rows that were handed to the array builder, not from
    a strategy-specific scalar: those rows are what the market actually saw, and every offer shape
    ``gen_cost_coeffs`` maps has one. A **piecewise** offer is the exception -- its coefficient row
    is all-zero by that mapping's own convention, so a piecewise offer that *changes* across the
    cycle would read as a zero amplitude and be reported as convergence. Such a window returns
    infinity instead, i.e. it is classified as a cycle: an amplitude that cannot be read is not
    evidence of having settled.
    """
    if not agents:
        return 0.0
    for agent in agents:
        curves = {round_.offers[agent.id].model_dump_json() for round_ in window}
        if len(curves) > 1 and any(
            round_.offers[agent.id].kind == "piecewise" for round_ in window
        ):
            return math.inf
    rows = np.array([[round_.cost_coeffs[agent.index] for agent in agents] for round_ in window])
    return float(np.max(np.ptp(rows, axis=0)))


_AMPLITUDE_TIE_REL_TOL = 1e-9
"""Relative band inside which a settled amplitude that lands a few ULPs *above* ``offer_tol``
still counts as convergence -- see :func:`_settled`. The same constant, in the same role, as
:data:`~mambo_power.market.strategy._PROFIT_TIE_REL_TOL`: both exist because a comparison that is
exact in arithmetic is decided by float noise in practice."""


def _settled(amplitude: float, offer_tol: float) -> bool:
    """Is *amplitude* within *offer_tol*, counting a ULP-scale overshoot as within?

    **Why this is not a plain ``<=``.** A9 derives ``offer_tol = 3 * step`` and a fixed-step
    climber settles into an oscillation of a whole number of steps -- two about an on-grid
    optimum, three about a half-grid one -- so the two sides of this comparison are *the same
    number* whenever the loop has arrived at the widest orbit the tolerance admits, which makes
    the verdict turn on whether that number is computed identically on both sides. It is not.
    ``offer_tol`` is one multiplication, while the amplitude is a peak-to-peak of offer levels
    each reached by hundreds of accumulated additions of ``step``. Measured on the AC-5 duopoly
    against the then-derived ``offer_tol = 2 * step`` (re-measured 2026-08-29, M7 S10, in ULPs
    of ``offer_tol``), the amplitude lands **102 ULPs above** ``2 * step`` at a step of 0.1
    (2.83e-15 over, 404 rounds) and **26 ULPs above** at 0.7 (5.77e-15 over, 61 rounds), while
    at 0.3 it lands 51 ULPs *below* and at 0.5 it is bit-exact. Under a plain ``<=`` the first
    two are reported as a **cycle** -- a real climb, settled at its optimum, declared
    non-convergent -- and the other two converge by luck. The sign of the accumulated error is
    arbitrary, so convergence was being decided by a coin flip. The floor is ``3 * step`` since
    M7 S11 (a half-grid optimum's three-step orbit), and the same equal-number comparison
    recurs there.

    **Why the tolerance goes here and not on ``offer_tol``.** The alternative is to forbid
    ``offer_tol == 3 * step`` and make callers add headroom. That destroys what A9 is for: the
    derived value stops being an admissible one, and the headroom actually needed depends on the
    accumulated float error over a round count the caller cannot know in advance (it tracks the
    number of rounds -- 102 ULPs over 404 of them, 26 over 61). A constant the caller must guess
    and cannot derive is precisely the tuning knob A9 exists to remove.

    The band is enormous on both sides of anything real: at a step of 0.1 it admits 2e-10 against
    an observed error of 2.8e-15, and a genuine cycle on this wave's own fixtures is ~20 $/MWh
    wide -- eleven orders of magnitude out. This is the same defect class, and the same remedy,
    as the profit-tie tolerance in :class:`~mambo_power.market.strategy.MarkupStrategy`.

    The band is **relative only** (``abs_tol=0.0``): an absolute term in cost-coefficient units
    would be a second, hidden tolerance -- and at ``1e-9`` it silently doubled the default
    ``offer_tol`` of ``1e-9``, admitting an amplitude of ``1.9e-9`` as "converged" (critic
    finding 7, M7 S11). An amplitude of exactly zero is the ``<=`` half's business, not the
    band's.
    """
    return amplitude <= offer_tol or math.isclose(
        amplitude, offer_tol, rel_tol=_AMPLITUDE_TIE_REL_TOL, abs_tol=0.0
    )


def solve_agents(
    scenario: Scenario,
    options: MarketAgentsOptions | None = None,
    *,
    strategies: Mapping[str, Strategy] | None = None,
) -> MarketAgentsResult:
    """Run the best-response loop of ``scenario.network`` (module docstring) and return the final
    round's clearing beside how the loop ended.

    **The in-process seam.** ``strategies`` maps a generator id to any structurally-conforming
    :class:`~mambo_power.market.strategy.Strategy` object, and is used *instead of*
    ``options.strategies`` -- giving both raises, so an agent set always has exactly one source
    and the result can say which rule ran. This is deliberate design, not a hole left open for a
    test: it is the surface for a caller whose bidding rule :data:`StrategyConfig` **cannot
    express** -- a rule with parameters the union does not carry, or one belonging to the caller
    rather than to this library -- and it is the reason
    :class:`~mambo_power.market.strategy.Strategy` is a structural
    :class:`typing.Protocol` (design D3(a)) rather than a closed union. Without it the Protocol
    would be decorative, since nothing would ever accept an object that merely conforms to it.
    Only the config union crosses JSON, so only ``options.strategies`` can reach this through
    ``jobs``, and the wave's own jobs coverage (AC-6) is unaffected by anything passed here.
    ``provenance.options`` echoes ``options`` either way, which is why
    :attr:`~mambo_power.results.agents.AgentOfferResult.strategy` -- carrying the config ``kind``
    or, for an injected object, its class name -- and not the provenance, is the record of which
    rule actually produced each offer.

    Never raises for an infeasible or unbounded LP: a round that fails to clear ends the run and
    is reported through ``status``/``message``, mirroring
    :func:`mambo_power.market.nodal.solve_nodal`'s never-raise convention. Does raise
    :class:`AgentSetError` (a ``ValueError``) up front for a caller mistake in the agent set (see
    :func:`_resolve_agents`),
    and :class:`~mambo_power.opf.dc_opf.NonConvexCostError` /
    :class:`~mambo_power.opf.dc_opf.NonConcaveBidError` for a cost or bid the clearing cannot
    accept -- including an *offer* a strategy produced, which is checked on the offer, every
    round, exactly as it would be on a true cost -- and ``TypeError`` at the call site, before
    that round's clearing, for a strategy whose ``offer`` returned something other than a
    :class:`~mambo_power.model.GeneratorCost` (see :func:`_checked_offer`). A strategy that
    cannot bid on its generator's
    true cost at all (:class:`~mambo_power.market.strategy.MarkupStrategy` on a non-linear cost,
    which raises ``NotImplementedError`` from its own ``offer``) is one of the up-front
    ``ValueError`` cases: :func:`_initial_offers` collects round 0's offers before the first
    clearing and re-raises that error with the generator id, so the mistake
    reaches ``jobs`` as ``VALIDATION`` like the other four rather than escaping the loop as
    ``INTERNAL``.

    ``Scenario`` and ``Network`` are not modified -- the offers reach the clearing as coefficients
    (AC-2).
    """
    opts = options if options is not None else MarketAgentsOptions()
    started_at = datetime.now(UTC)
    clock = time.perf_counter()
    net = scenario.network
    arr = NetworkArrays.from_network(net)
    agents = _resolve_agents(net, arr, opts, strategies)
    offers = _initial_offers(agents)
    demand_bid_coeffs, demand_pwl_bids = load_bid_coeffs(net, arr)
    elastic_idxs = sorted(set(demand_bid_coeffs) | set(demand_pwl_bids))
    # The network never changes between rounds -- only the offers do -- so the PTDF (and the
    # B-bus / incidence factorisation beneath it) is built once here and handed to every round's
    # clearing. Rebuilt per round it was 70% of a 200-round case14 run (critic finding 3, M7 S11);
    # passing it changes no number (tests/unit/test_market_agents.py, the cache test).
    ptdf_matrix = compute_ptdf(arr)

    history: list[_Round] = []
    seen: dict[tuple[tuple[str, ...], tuple[str, ...]], int] = {}
    reason: TerminationReason = "iteration_cap"
    solution: OpfSolution | None = None
    breakdown: LmpBreakdown | None = None
    round_index = 0
    while True:
        cost_coeffs, pwl_costs = gen_cost_coeffs(net, arr, costs=offers)
        solution = dc_opf(
            arr,
            cost_coeffs,
            OpfDcOptions(),
            pwl_costs=pwl_costs or None,
            demand_bid_coeffs=demand_bid_coeffs or None,
            demand_pwl_bids=demand_pwl_bids or None,
            ptdf=ptdf_matrix,
        )
        if solution.status != "Optimal" or solution.duals is None:
            return MarketAgentsResult(
                provenance=_provenance(opts, started_at, time.perf_counter() - clock),
                status=solution.status,
                message=solution.message,
                iterations=round_index,
                converged=False,
                termination_reason=None,
            )
        breakdown = lmp_decomposition(solution.duals, solution.ptdf)
        history.append(
            _Round(
                offers=offers,
                cost_coeffs=cost_coeffs,
                dispatch_mw=solution.dispatch_mw,
                lmp=breakdown.lmp,
            )
        )
        # The loop's state going into round r+1 is the pair (round r-1's offers, round r's
        # offers): every strategy is a pure function of its own last two rounds, and each round's
        # LMPs and dispatch are a deterministic function of that round's offers. So a repeat of
        # this pair means every subsequent round replays the ones after its first occurrence --
        # the sequence is periodic from here, and what remains is to classify how wide the
        # oscillation is, not whether it will end.
        if round_index >= 1:
            key = (
                _offer_key(history[round_index - 1].offers, agents),
                _offer_key(history[round_index].offers, agents),
            )
            first_seen = seen.get(key)
            if first_seen is not None:
                period = round_index - first_seen
                amplitude = _amplitude(history[round_index + 1 - period :], agents)
                reason = "converged" if _settled(amplitude, opts.offer_tol) else "cycle"
                break
            seen[key] = round_index
        if round_index >= opts.max_iterations:
            reason = "iteration_cap"
            break
        round_index += 1
        offers = {
            agent.id: _checked_offer(agent, _observation(agent, round_index, history))
            for agent in agents
        }

    assert breakdown is not None  # set on every Optimal round, and the loop broke on one
    # The final round's rows and settlement -- the one construction market.nodal applies to its
    # single clearing (market/_clearing.py), applied to this loop's last one. Settlement is the
    # final round's alone: computed directly from that dispatch and those LMPs, never accumulated
    # over the search that led to it.
    rows = clearing_rows(net, arr, solution, breakdown.lmp, elastic_idxs)
    final = history[-1]
    offer_rows = [
        AgentOfferResult(
            id=agent.id,
            strategy=agent.label,
            offer=final.offers[agent.id],
            true_cost=agent.true_cost,
            cleared_mw=float(final.dispatch_mw[agent.index]),
            markup=_cost_at(final.offers[agent.id], float(final.dispatch_mw[agent.index]))
            - _cost_at(agent.true_cost, float(final.dispatch_mw[agent.index])),
        )
        for agent in agents
    ]
    return MarketAgentsResult(
        provenance=_provenance(opts, started_at, time.perf_counter() - clock),
        status=solution.status,
        message=None,
        generators=rows.generators,
        loads=rows.loads,
        buses=[
            BusLmpResult(
                id=bus_id,
                lmp=float(breakdown.lmp[i]),
                energy=float(breakdown.energy[i]),
                congestion=float(breakdown.congestion[i]),
            )
            for i, bus_id in enumerate(arr.bus_ids)
        ],
        branches=rows.branches,
        offers=offer_rows,
        iterations=round_index,
        converged=reason == "converged",
        termination_reason=reason,
        total_load_payment=rows.total_load_payment,
        total_generator_receipts=rows.total_generator_receipts,
        congestion_rent=rows.total_load_payment - rows.total_generator_receipts,
    )


def _provenance(
    options: MarketAgentsOptions, started_at: datetime, elapsed_s: float
) -> ResultProvenance:
    """This run's provenance stamp; ``options`` is echoed verbatim, as every other market mode
    does."""
    return ResultProvenance(
        engine="mambo-power",
        version=mambo_power.__version__,
        kind="market.agents",
        solver="highspy.Highs",
        started_at=started_at,
        elapsed_s=elapsed_s,
        options=options.model_dump(),
    )
