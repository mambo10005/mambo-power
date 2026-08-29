"""Strategic bidding: generators offer, the market clears the offers, and the loop reports how it
ended.

What this shows:

* ``market.agents.solve_agents(scenario, options)`` -- the first market mode whose *input* is an
  output of a decision. Every other mode reads the supply curve off the network; here each agent
  chooses what to offer, and the offered curve is a different object from the true one.
* The overlay, proved rather than asserted: the network is byte-identical after a run in which
  every agent marked up, and ``Generator.cost`` still holds the true cost.
* Price-takers reproduce the competitive result **exactly** -- ``array_equal`` on both dispatch
  and LMPs against ``market.solve_nodal``, with no tolerance anywhere. This runs the ordinary
  loop; there is no price-taker short-circuit for it to take.
* A pivotal supplier's markup walking up to the point where demand's own bid refuses to pay
  more, against the closed-form optimum of the same problem -- and the paired control where a
  rival, not demand, is what stops the climb.
* The two-agent duopoly, where ``converged`` has to mean something, and the same run under an
  iteration cap, where the result says ``iteration_cap`` rather than pretending to have settled.
* Through ``jobs``: the ``StrategyConfig`` union crossing as JSON data, never a callable.

The synthetic networks are built here rather than imported from ``fixtures/``: a markup agent
needs a **linear** cost, and every one of the 147 generators in the six bundled MATPOWER cases
carries a quadratic one. The price-taker section below does use ``case14``, because a price-taker
offers whatever shape its true cost is.

Run from the repository root: ``uv run python examples/12_agent_market.py``.
"""

from __future__ import annotations

import json

import numpy as np

from mambo_power import jobs, market
from mambo_power.io import matpower
from mambo_power.market.agents import MarketAgentsOptions, solve_agents
from mambo_power.model import (
    Branch,
    Bus,
    Generator,
    Load,
    Network,
    PolynomialBid,
    PolynomialCost,
    Scenario,
)

# The shared demand side of every synthetic market below: marginal value ``100 - 0.1*p``, i.e.
# ``q(price) = 1000 - 10*price``.  A ``PolynomialBid``'s coefficients are the *value* curve, whose
# derivative is the marginal value, so v1 = 100.0 and v2 = -0.05.  ``p_mw`` is the quantity at
# which marginal value reaches zero -- a smaller cap would truncate the curve before the market
# reached its own optimum.
DEMAND_BID = PolynomialBid(coefficients=[-0.05, 100.0, 0.0])
DEMAND_P_MAX_MW = 1000.0


def star(generators: list[tuple[str, float, float]]) -> Network:
    """A star network: ``b1`` (slack) hosts the first generator, every further one gets its own
    bus, and the shared elastic load sits on the last bus.

    Each entry is ``(id, p_max_mw, true_marginal_cost)``.  Every branch is built with no rating,
    so nothing here ever congests -- this example is about bidding, not about flow limits.  Every
    true cost is linear, ``cost(p) = c1 * p``, which is both what ``MarkupStrategy`` requires and
    what makes the profit arithmetic below closed-form.
    """
    n = len(generators)
    buses = [Bus(id="b1", base_kv=138.0, type="slack")]
    buses += [Bus(id=f"b{i}", base_kv=138.0, type="pq") for i in range(2, n + 2)]
    branches = [
        Branch(id=f"l{i}", from_bus="b1", to_bus=f"b{i}", r=0.0, x=0.05, b=0.0)
        for i in range(2, n + 2)
    ]
    gens = [
        Generator(
            id=gen_id,
            bus="b1" if k == 0 else f"b{k + 1}",
            p_mw=0.0,
            q_mvar=0.0,
            p_min_mw=0.0,
            p_max_mw=p_max_mw,
            q_min_mvar=-9999.0,
            q_max_mvar=9999.0,
            v_set_pu=1.0,
            cost=PolynomialCost(coefficients=[true_cost, 0.0]),
        )
        for k, (gen_id, p_max_mw, true_cost) in enumerate(generators)
    ]
    load = Load(id="d1", bus=f"b{n + 1}", p_mw=DEMAND_P_MAX_MW, q_mvar=0.0, bid=DEMAND_BID)
    return Network(base_mva=100.0, buses=buses, branches=branches, generators=gens, loads=[load])


def price(result) -> float:  # noqa: ANN001 - any market result carrying `buses`
    """The clearing price at the load's own bus, which is the last one every `star` builds."""
    return result.buses[-1].lmp


# --- 1. Price-takers reproduce the competitive result, exactly --------------------------------
# Every generator on case14 offers its own true cost, unchanged.  This is an ordinary run of the
# loop -- the offer map is built, the overlay is handed to the array builder, the clearing comes
# back and is compared -- and it agrees with `market.solve_nodal` bitwise, not to a tolerance.
case14 = matpower.load("fixtures/matpower/case14.m")
scenario14 = Scenario(network=case14)

taker_options = MarketAgentsOptions(
    strategies={gen.id: {"kind": "price_taker"} for gen in case14.generators}
)
taker = solve_agents(scenario14, taker_options)
nodal = market.solve_nodal(scenario14)

print("--- 1. price-takers vs market.solve_nodal, on case14 ---")
print(
    "dispatch array_equal:",
    np.array_equal(
        np.array([g.p_mw for g in taker.generators]),
        np.array([g.p_mw for g in nodal.generators]),
    ),
    "| LMP array_equal:",
    np.array_equal(np.array([b.lmp for b in taker.buses]), np.array([b.lmp for b in nodal.buses])),
)
print(
    f"status {taker.status} | converged {taker.converged} | "
    f"termination_reason {taker.termination_reason} | iterations {taker.iterations}"
)
print(
    "every offer is the true cost object:",
    all(offer.offer == offer.true_cost for offer in taker.offers),
    "| markups:",
    sorted({offer.markup for offer in taker.offers}),
)

# --- 2. A pivotal supplier climbs to demand's own limit ----------------------------------------
# One 900 MW unit at a true $20/MWh, no rival, facing q = 1000 - 10*price.  Profit
# (pi - 20)(1000 - 10*pi) peaks at pi = $60.00, q = 400 MW, $16,000/h -- a closed form this
# market has no knowledge of.  The agent finds it by climbing on its own observed profit alone.
pivotal = star([("strategic", 900.0, 20.0)])
before_json = pivotal.model_dump_json()

markup_options = MarketAgentsOptions(
    strategies={"strategic": {"kind": "markup", "step": 0.5}}, offer_tol=1.5
)
climbed = solve_agents(Scenario(network=pivotal), markup_options)
baseline = solve_agents(
    Scenario(network=pivotal),
    MarketAgentsOptions(strategies={"strategic": {"kind": "price_taker"}}),
)

peak = climbed.offers[0]
print()
print("--- 2. a pivotal supplier, against a closed-form optimum ---")
print("closed form:  offer $60.00/MWh, cleared 400.00 MW, profit $16,000.00/h")
print(
    f"the climb:    offer ${peak.offer.coefficients[0]:.2f}/MWh, "
    f"cleared {peak.cleared_mw:.2f} MW, markup ${peak.markup:,.2f}/h"
)
print(
    f"at true cost: price ${price(baseline):.2f}/MWh, "
    f"cleared {baseline.offers[0].cleared_mw:.2f} MW, markup ${baseline.offers[0].markup:,.2f}/h"
)
print(f"clearing price ${price(climbed):.2f}/MWh after {climbed.iterations} update rounds")

# The overlay never touched the network.  Both halves matter: byte-identity alone would also hold
# for a run in which nothing happened, and the markup above is what rules that out.
print("network byte-identical after the run:", pivotal.model_dump_json() == before_json)
print("Generator.cost still the true curve:", pivotal.generators[0].cost.coefficients)

# --- 3. The paired control: a rival, not demand, stops the climb -------------------------------
# The same unit, now with a 900 MW rival at $22/MWh.  The markup is real and nonzero -- market
# power is reduced, not eliminated -- but it is an order of magnitude smaller, and what stops it
# is the rival's cost rather than demand's willingness to pay.
controlled = solve_agents(
    Scenario(network=star([("strategic", 900.0, 20.0), ("rival", 900.0, 22.0)])), markup_options
)
rivalled = controlled.offers[0]
print()
print("--- 3. the same agent with a rival at $22/MWh ---")
print(
    f"offer ${rivalled.offer.coefficients[0]:.2f}/MWh, cleared {rivalled.cleared_mw:.2f} MW, "
    f"markup ${rivalled.markup:,.2f}/h after {controlled.iterations} update rounds"
)
print(f"against the pivotal ${peak.markup:,.2f}/h -- {peak.markup / rivalled.markup:.1f}x smaller")

# --- 4. Two agents, and what `converged` has to mean -------------------------------------------
# Two 300 MW units at $20/MWh: the only shape in this example where best response can fail to
# settle in one round.  A fixed-step climber never comes to rest -- it dithers by two steps about
# its optimum, three when the optimum sits halfway between two grid points -- so the loop
# classifies the repetition it finds by its *amplitude*, which is why `offer_tol` must be at
# least `3 * step` and why the options model enforces that.
duopoly = star([("g1", 300.0, 20.0), ("g2", 300.0, 20.0)])
duopoly_strategies = {
    "g1": {"kind": "markup", "step": 0.5},
    "g2": {"kind": "markup", "step": 0.5},
}
settled = solve_agents(
    Scenario(network=duopoly),
    MarketAgentsOptions(strategies=duopoly_strategies, offer_tol=1.5),
)
competitive = solve_agents(
    Scenario(network=duopoly),
    MarketAgentsOptions(strategies={"g1": {"kind": "price_taker"}, "g2": {"kind": "price_taker"}}),
)
print()
print("--- 4. a two-agent duopoly ---")
print(
    "offers",
    [offer.offer.coefficients[0] for offer in settled.offers],
    f"| price ${price(settled):.2f}/MWh | joint markup "
    f"${sum(offer.markup for offer in settled.offers):,.2f}/h",
)
print(
    f"at true cost: price ${price(competitive):.2f}/MWh, "
    f"cleared {[round(offer.cleared_mw, 2) for offer in competitive.offers]}"
)
print(
    f"status {settled.status} | converged {settled.converged} | "
    f"termination_reason {settled.termination_reason} | iterations {settled.iterations}"
)

# The same run under a cap it cannot meet.  `status` is still the LP's and still Optimal; the loop
# reports that it ran out of rounds, and never presents a truncated run as a settled one.
capped = solve_agents(
    Scenario(network=duopoly),
    MarketAgentsOptions(strategies=duopoly_strategies, offer_tol=1.5, max_iterations=10),
)
print(
    f"under max_iterations=10: status {capped.status} | converged {capped.converged} | "
    f"termination_reason {capped.termination_reason} | iterations {capped.iterations}"
)

# A tolerance narrower than the settling oscillation would turn every arrival into a false cycle
# report, so it is rejected up front rather than mis-diagnosed later.
try:
    MarketAgentsOptions(strategies={"g1": {"kind": "markup", "step": 0.5}}, offer_tol=0.5)
except ValueError as exc:
    print("offer_tol below 3 * step is refused:", str(exc).splitlines()[1].strip()[:78])

# --- 5. Through the jobs API -------------------------------------------------------------------
# The strategy configuration crosses as data.  A `Strategy` object never does: `solve_agents` has
# an in-process `strategies=` seam for a rule the config union cannot express, and `jobs` cannot
# reach it, so nothing a service sends decides which code runs.
request = jobs.SolveRequest(
    kind="market.agents",
    network=duopoly,
    options={"strategies": duopoly_strategies, "offer_tol": 1.5},
)
reply = json.loads(jobs.run_json(request.model_dump_json()))
print()
print("--- 5. through jobs ---")
print("kinds:", jobs.kinds())
print(
    reply["status"],
    reply["provenance"]["kind"],
    "| converged",
    reply["result"]["converged"],
    "| termination_reason",
    reply["result"]["termination_reason"],
    "| iterations",
    reply["result"]["iterations"],
)
print("strategies crossed JSON as data:", reply["provenance"]["options"]["strategies"])

bad = jobs.run(
    jobs.SolveRequest(
        kind="market.agents",
        network=duopoly,
        options={"strategies": {"nope": {"kind": "markup", "step": 0.5}}, "offer_tol": 1.5},
    )
)
print("a strategy naming a generator that does not exist:", bad.status, bad.error.code)
