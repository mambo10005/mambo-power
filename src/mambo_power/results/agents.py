"""``market.agents`` result: the final round's clearing, plus what each agent offered to get it
and how the loop that produced it ended (wave M7 W4).

**Two different things called "did it work", and they are never the same field.** ``status`` is
the **LP's** -- HiGHS's own model status for the final round's clearing, exactly as
:class:`~mambo_power.results.MarketNodalResult` reports it. :attr:`MarketAgentsResult.converged`
is the **loop's** -- whether the best-response iteration settled. A run can be ``Optimal`` every
round and still not converge (the agents keep re-bidding), and that combination is the one the
wave most needs to report honestly rather than round off to "it worked". Neither field is derived
from the other, and no docstring or message here uses one word for both.

**Why the loop's end needs three words, not a flag** (spec A7). :attr:`converged` alone cannot
distinguish the two shapes of non-convergence, and reporting a genuine cycle as an iteration-cap
hit would be a confident wrong diagnosis. :attr:`termination_reason` is therefore required and
enumerated -- ``converged`` | ``iteration_cap`` | ``cycle`` -- with :attr:`iterations` readable
beside it.

**The clearing fields mirror** :class:`~mambo_power.results.MarketNodalResult` field for field and
row type for row type (generators, loads, buses, ``branches``, and the three settlement figures),
because they are the same clearing quantities computed the same way -- one clearing, the final
round's, settled at the final round's prices. This result is a sibling of that one, not a
subclass: a ``market.agents`` result is not a ``market.nodal`` result, and nothing should be able
to pass one off as the other.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from mambo_power.model import GeneratorCost
from mambo_power.results.market import LoadDispatchResult
from mambo_power.results.opf import BusLmpResult, GenDispatchResult, OpfBranchFlowResult
from mambo_power.results.provenance import ResultProvenance

TerminationReason = Literal["converged", "iteration_cap", "cycle"]
"""How :func:`mambo_power.market.agents.solve_agents`' loop ended (spec A7). ``converged``: the
offer vector repeated and the repetition's amplitude is within ``offer_tol``. ``cycle``: it
repeated with an amplitude wider than that -- a genuine cycle, which is *not* the iteration cap.
``iteration_cap``: ``max_iterations`` update rounds passed without any repetition at all."""


class AgentOfferResult(BaseModel):
    """One agent's final-round offer, beside the true cost it was allowed to depart from.

    Both curves are carried whole, as :class:`~mambo_power.model.GeneratorCost` objects, because
    the whole point of the overlay is that they are two separate objects: ``true_cost`` is the
    generator's own ``Generator.cost``, untouched by the run (AC-2), and ``offer`` is what the
    strategy handed the clearing. "Markup" is the difference, which only means anything because
    neither one overwrote the other.
    """

    model_config = ConfigDict(extra="forbid", frozen=True, allow_inf_nan=False)

    id: str = Field(description="Generator id from the network.")
    strategy: str = Field(
        description="Which bidding rule produced this offer: the StrategyConfig.kind "
        '("price_taker", "markup") when solve_agents built the strategy from '
        "MarketAgentsOptions.strategies, or the class name of the object an in-process caller "
        "passed to solve_agents' own strategies argument."
    )
    offer: GeneratorCost = Field(
        description="The cost curve this agent offered in the final round -- what the clearing "
        "actually minimised against, never written back to the network."
    )
    true_cost: GeneratorCost = Field(
        description="The generator's own Generator.cost, unchanged by the run."
    )
    cleared_mw: float = Field(
        description="This agent's dispatch in the final round's clearing, MW; the same figure "
        "its GenDispatchResult row carries, repeated here because the markup identity below is "
        "stated in terms of it."
    )
    markup: float = Field(
        description="offer(cleared_mw) - true_cost(cleared_mw), $/h: what the agent's departure "
        "from its own cost is worth at the quantity it actually cleared. Not independent "
        "content -- it is exactly that identity in the other three fields (spec A6), and "
        "tests/unit/test_market_agents.py asserts it as one."
    )


class MarketAgentsResult(BaseModel):
    """Result of :func:`mambo_power.market.agents.solve_agents`.

    When ``status != "Optimal"`` the clearing fields are left at their empty/zero defaults and
    ``message`` carries the diagnostic, mirroring
    :class:`~mambo_power.results.MarketNodalResult`'s own convention; :attr:`iterations` still
    reports the round the clearing failed in, since that is a fact about the loop rather than
    about the clearing.
    """

    model_config = ConfigDict(extra="forbid", frozen=True, allow_inf_nan=False)

    provenance: ResultProvenance
    status: str = Field(
        description='HiGHS model status of the final round\'s clearing: "Optimal", "Infeasible", '
        '"Unbounded", or another HiGHS status string passed through verbatim. This is the LP\'s '
        "verdict and says nothing about whether the loop converged -- see converged."
    )
    message: str | None = Field(default=None, description="Diagnostic when status != Optimal.")
    generators: list[GenDispatchResult] = Field(default_factory=list)
    loads: list[LoadDispatchResult] = Field(default_factory=list)
    buses: list[BusLmpResult] = Field(default_factory=list)
    branches: list[OpfBranchFlowResult] = Field(
        default_factory=list,
        description="Per-branch flow and flow-limit shadow price at the final round's dispatch -- "
        "the same field name and row type as MarketNodalResult.branches and "
        "MarketZonalResult.branches.",
    )
    offers: list[AgentOfferResult] = Field(
        default_factory=list,
        description="One row per agent -- a generator that MarketAgentsOptions.strategies (or "
        "solve_agents' strategies argument) named -- in NetworkArrays generator order. A "
        "generator with no strategy is not an agent: it clears at its own true cost and appears "
        "under generators only.",
    )
    iterations: int = Field(
        default=0,
        ge=0,
        description="The final round's index: the number of best-response update rounds the loop "
        "ran after round 0. Round 0 is the initial offer and responds to nothing, so it is not "
        "an iteration; the loop therefore cleared the market iterations + 1 times. A fixed "
        "point is confirmed only after two identical updates (the loop's state is the pair of "
        "consecutive offer vectors), so iterations is at least 2 on any converged run -- an "
        "all-price-taker market, in which nothing moves, still reports 2.",
    )
    converged: bool = Field(
        default=False,
        description="Whether the *loop* settled -- the offer vector repeated with an amplitude "
        "within offer_tol. Never a statement about the LP: see status. True exactly when "
        'termination_reason == "converged".',
    )
    termination_reason: TerminationReason | None = Field(
        default=None,
        description="How the loop ended (spec A7): converged | iteration_cap | cycle. None "
        "exactly when status != Optimal -- a clearing that failed produced no loop outcome to "
        "report, and inventing a fourth value here would fold the LP's verdict into the loop's, "
        "which is what this result exists to keep apart.",
    )
    total_load_payment: float = Field(
        default=0.0,
        description="Sum over every load of LMP(bus_d)*p_d in the final round's clearing, $/h; "
        "0.0 when not Optimal.",
    )
    total_generator_receipts: float = Field(
        default=0.0,
        description="Sum over every generator of LMP(bus_g)*p_g in the final round's clearing, "
        "$/h -- paid at the final round's prices, on the final round's offers; 0.0 when not "
        "Optimal.",
    )
    congestion_rent: float = Field(
        default=0.0,
        description="total_load_payment - total_generator_receipts, $/h; 0.0 when not Optimal.",
    )

    @model_validator(mode="after")
    def _loop_outcome_matches_the_clearing_it_came_from(self) -> MarketAgentsResult:
        """``termination_reason`` is present exactly when there is a clearing to have terminated
        on, and ``converged`` says the same thing as the reason.

        Both halves are checked here rather than left to the producer because both are ways this
        result could carry a self-contradicting story: a converged flag beside a ``cycle`` reason,
        or a loop outcome reported for a market that never cleared.
        """
        if self.status == "Optimal" and self.termination_reason is None:
            raise ValueError(
                "termination_reason is required when status == 'Optimal' -- an optimal run "
                "ended the loop somehow, and how is not inferable from converged alone"
            )
        if self.status != "Optimal" and self.termination_reason is not None:
            raise ValueError(
                f"termination_reason is {self.termination_reason!r} but status is "
                f"{self.status!r} -- a clearing that did not solve has no loop outcome to report"
            )
        if self.converged != (self.termination_reason == "converged"):
            raise ValueError(
                f"converged={self.converged} contradicts termination_reason="
                f"{self.termination_reason!r} -- converged is true exactly when the reason is "
                "'converged'"
            )
        return self
