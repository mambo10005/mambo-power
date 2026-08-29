# Strategic bidding

`market.agents.solve_agents` is the fourth market mode and the first whose *input* is an output of
a decision. `solve_nodal`, `solve_multiperiod` and `solve_zonal` all clear a market whose supply
curve is read off the network: a generator's `cost` is what the LP minimises against, and a
generator is dispatched at cost whether or not it would have chosen to offer at cost. Here each
generator has a **strategy**, the strategy chooses what to offer, and the market clears the
offers.

That makes one distinction the whole mode rests on. The **true cost** stays on `Generator.cost`
and is never written to. The **offer** is a separate `GeneratorCost` that reaches the clearing as
coefficients. "Markup" is the difference between them, and it is a quantity this package can
compute only because they are two objects rather than one field overwritten in place.

```python
from mambo_power.market.agents import MarketAgentsOptions, solve_agents

result = solve_agents(
    scenario,
    MarketAgentsOptions(
        strategies={"strategic": {"kind": "markup", "step": 0.5}},
        offer_tol=1.5,
    ),
)
```

## One round

Each round, every agent is handed its own [`Observation`](../api/market.md#the-strategy-seam) and
returns a `GeneratorCost`:

1. **Observe.** The agent sees its own true cost curve and active limits, the round index, and
   its own **last two rounds** of `(offer, bus LMP, cleared MW)`. Nothing else — no rival's offer,
   no other bus's price, no view of the clearing as a whole. Concretely, `Observation` has the
   fields `round_index, true_cost, p_min_mw, p_max_mw, previous_round, two_rounds_ago`, and each
   of the last two is a `RoundRecord(round_index, offer, lmp, cleared_mw)` or `None`.
2. **Offer.** The strategy returns a cost curve — any `GeneratorCost`; the loop checks that it
   got one where it called the strategy, before the clearing. It holds no state between calls;
   the loop supplies the history, so a run is a pure function of `(network, strategies,
   tolerance)`.
3. **Clear.** The offers become an overlay: `gen_cost_coeffs(net, arr, costs=offers)` maps the
   offered union to coefficients through the *same* function a true cost goes through, and
   `dc_opf` clears them alongside the loads' own bids.
4. **Repeat**, until the termination test below fires or `max_iterations` rounds have passed.

Updates are **simultaneous**, in `NetworkArrays` generator order: every agent's round-*r* offer is
computed from round *r−1*'s clearing, before any of them is cleared. That is part of the
documented contract, not an implementation detail — a different order need not reach the same
point, and this mode claims nothing about the one it does not run.

Settlement is computed **once**, on the final round's clearing, at the final round's prices. The
intermediate rounds are the agents' search, not a sequence of markets anybody was paid for — and
**only the final round is on the result**: `offers` is each agent's last offer, not its path. To
see per-round offers, wrap a strategy in a recording object and pass it through the in-process
`strategies=` seam (any object with an `offer` method), as the test suite's own recorder does.

!!! note "The clearing is the general path, not a call to `solve_nodal`"
    Every round runs `gen_cost_coeffs` + `load_bid_coeffs` + `dc_opf` directly. A short-circuit
    to `solve_nodal` for the all-price-taker case would have made the exactness claim below true
    by construction while bypassing the loop, the overlay and the offer map it exists to test.

## Why two rounds of history, and not one

A one-round view tells an agent whether it is marginal. It does not tell it whether its **last
move helped**, and every rule computable from one round either cycles or crawls: measured, the
best of them reaches a markup gain of $0.02/h. With two rounds an agent can compare its own profit
at *t−1* and *t−2*, keep its direction if the last move raised profit and reverse it if not.

The first two rounds necessarily have less history than that, and `Observation` says so
explicitly: `previous_round` and `two_rounds_ago` are `None` when that round has not happened,
never a zero-valued `RoundRecord` standing in for it. A record from the wrong round is rejected
rather than accepted as adjacent — an own-node history cannot skip a round or carry a stale one.

## The strategies that ship

`PriceTakerStrategy` offers the generator's own true cost, verbatim, every round. It ignores both
history fields entirely; there is nothing a price-taker's past has to tell it.

`MarkupStrategy` is a fixed-step two-point hill climb on the agent's own observed profit. Round 0
offers true cost (there is nothing yet to have an opinion about); round 1 probes upward by one
step; from round 2 on, direction is kept if the last move raised profit and reversed if it did
not, and the new offer is floored at the agent's own true marginal cost so a markup never goes
negative. One more rule keeps an agent honest when nobody wants it: if it cleared nothing in
both of the last two rounds, its profit is `0 == 0` (a tie, not a decrease) and the climb would
otherwise continue by a step a round until the iteration cap — so direction is `-1` instead, and
the agent walks back down to its true cost and rests there, which the loop reports as `converged`.

!!! warning "`MarkupStrategy` requires a linear cost, and no bundled fixture has one"
    It is scoped to a linear `PolynomialCost` (`coefficients = [c1, c0]`) and raises
    `NotImplementedError` on anything else: a piecewise or higher-degree curve has no single
    scalar the climb has established a meaning for. `solve_agents` asks every strategy for its
    round-0 offer **before the first clearing** and turns that refusal into an `AgentSetError` naming
    the generator (through `jobs`, a `VALIDATION` failure — never `INTERNAL`), so the mistake is
    reported as a mistake in the agent set, not as a fault mid-run. All **147** generators across
    the six bundled MATPOWER cases carry quadratic costs, so a markup agent can be attached to
    none of them and works only on a network built for it — as
    [`examples/12_agent_market.py`](../examples/index.md#12-strategic-bidding) does. A
    price-taker has no such restriction and offers whatever shape its true cost is, MATPOWER
    cases included.

Both are *local* best responders. Neither evaluates a candidate offer against a market clearing —
that would require clearing the market, which the own-node observation deliberately withholds — so
where a competing unit puts a discontinuity between an agent's cost and its profit peak, the climb
stalls at the local optimum on its own side of it. Measured: $9,497.52 against a derivable
$12,250. This mode reports what its own iteration reaches and claims nothing more.

## Termination: three words, not a flag

A fixed-step climber **never comes to rest**. Once it arrives it dithers by one step either
side of its optimum — or, when the optimum sits halfway between two of its grid points, by one
step on one side and two on the other — which is what arrival looks like, not a failure. So the loop watches
for a repeated offer vector and then classifies the repetition by its **amplitude**:

| Amplitude of the repetition found | `termination_reason` | `converged` |
| --- | --- | --- |
| within `offer_tol` | `converged` | `True` |
| wider than `offer_tol` | `cycle` | `False` |
| no repetition inside `max_iterations` rounds | `iteration_cap` | `False` |

Reporting a genuine cycle as an iteration-cap hit would be a confident wrong diagnosis, which is
why the reason is a required enumerated field rather than something a caller infers from the flag.

This makes `offer_tol >= 3 * step` **derived** rather than tuned: the settled oscillation spans
two steps about an on-grid optimum and three about a half-grid one (the two straddling offers tie
in profit, the tie keeps the climb's direction, and it overshoots one extra step before the real
decrease turns it), and a strictly concave profit cannot tie three grid points in a row, so three
steps is the widest a settled orbit gets. A tolerance narrower than that would report a
successful climb as a cycle — found at true cost 33.33 with a step of 0.01, where the earlier
`2 * step` floor reported a settled run as `cycle` after 3,339 rounds. The constant lives in one
place, `MarkupStrategy.min_offer_tol`. The default `offer_tol` is `1e-9` — it admits only an offer vector that has genuinely
come to rest, which is what an all-price-taker run does — so any markup agent needs it set
explicitly. `MarketAgentsOptions` rejects a violating configuration up front rather than
mis-diagnosing the run later:

```text
offer_tol=0.5 is below 3 * step for the markup strategy on generator "g1" (step=0.5, so
3 * step=1.5). A fixed-step climber settles into an oscillation of two steps about its optimum
-- three when the optimum sits halfway between two of its grid points -- so a narrower tolerance
would report that arrival as a cycle. Raise offer_tol to at least 1.5, or lower the step.
```

A repetition needs two rounds to be seen in, so `converged` requires at least **two update
rounds**: `max_iterations=1` always ends `iteration_cap`, even for a market of price-takers whose
offers never move. `iterations` counts update rounds after round 0, so `iterations` is at least 2
on any converged run, and a converged all-price-taker market -- in which nothing moved -- still
reports `iterations 2` (three clearings): a fixed point is confirmed after two identical updates,
not detected before the first.

!!! warning "`status` is the LP's; `converged` is the loop's"
    `status` is HiGHS's model status for the final round's clearing. `converged` is whether the
    best-response iteration settled. A run can be `Optimal` in every round and still not
    converge, and that combination is reported as exactly what it is. Neither field is derived
    from the other, and nothing here uses one word for both.

## Two economic statements

### Price-takers reproduce the competitive result, exactly

On an all-price-taker configuration the offer coefficients handed to the array builder are
`array_equal` to the generators' own true cost coefficients — and so is the outcome. On case14:

```text
dispatch array_equal: True | LMP array_equal: True
status Optimal | converged True | termination_reason converged | iterations 2
every offer is the true cost object: True | markups: [0.0]
```

Both comparisons are `array_equal`, not `allclose`: no tolerance enters this claim. And there is
no short-circuit making it easy — this is an ordinary run of the loop, the overlay and the offer
map, which is what makes it evidence that they are honest. The claim is between the **two paths**
— `solve_agents` with price-takers and `solve_nodal` — not against a hand-computed price: the
LMPs carry the LP's own noise (a demand-set $30 comes back as `29.999974999999992`), and both
paths carry the same noise, bit for bit.

### A pivotal supplier's markup stops where demand stops paying

One 900 MW unit at a true $20/MWh, no rival, facing `q = 1000 − 10·price`. Profit
`(π − 20)(1000 − 10π)` peaks in closed form at **π = $60.00**, **q = 400 MW**, **$16,000/h** — a
figure the market has no knowledge of. The agent finds it by climbing on its own observed profit:

```text
closed form:  offer $60.00/MWh, cleared 400.00 MW, profit $16,000.00/h
the climb:    offer $60.00/MWh, cleared 400.00 MW, markup $15,999.97/h
at true cost: price $20.00/MWh, cleared 800.00 MW, markup $0.00/h
clearing price $60.00/MWh in 84 rounds
```

What stops the climb is **demand's own `Load.bid`** — the willingness to pay the nodal market
mode has carried since M4. There is no bid cap field, no market-wide ceiling and no new model
field anywhere in this mode; raising the bid moves the peak.

The paired control is the same agent with a 900 MW rival at $22/MWh:

```text
offer $21.50/MWh, cleared 785.00 MW, markup $1,177.50/h in 7 rounds
against the pivotal $15,999.97/h -- 13.6x smaller
```

Real, nonzero, and 13.6× smaller — market power **reduced, not eliminated** — and stopped by the
rival's cost rather than by demand.

## Two agents

The duopoly is the only shape here in which best response can fail to settle in one round: two
300 MW units, both at a true $20/MWh, against the same demand curve.

```text
offers [60.0, 60.0] | price $60.00/MWh | joint markup $15,999.98/h
at true cost: price $40.00/MWh, cleared [300.0, 300.0]
status Optimal | converged True | termination_reason converged | iterations 84
under max_iterations=10: status Optimal | converged False | termination_reason iteration_cap | iterations 10
```

The second line is the point: the same run under a cap it cannot meet still clears optimally every
round, and says so — `status` `Optimal`, `converged` `False`, `iteration_cap`. A truncated run
never presents as a settled one.

This mode reports the point *its own iteration* reaches and claims no equilibrium existence or
uniqueness. The fixed point of this game is asymmetric and order-dependent: an exact-best-response
sweep of the same duopoly settles at `[45.0, 20.0]` under one update rule and `[20.0, 47.5]` under
another. That sweep is not the dynamics shipped here — an exact best response requires clearing
the market — but it is why no claim of uniqueness is made.

## The overlay never mutates the network

`Scenario` and `Network` come out of a run byte-identical, and every `Generator.cost` is
unchanged:

```text
network byte-identical after the run: True
Generator.cost still the true curve: [20.0, 0.0]
```

Byte-identity on its own would also hold for a run in which nothing happened, so it is only half
the statement. The other half is the $15,999.97/h markup above: the coefficients the array builder
saw genuinely differed from the true ones, on the very run whose network came back unchanged.

## Results

`MarketAgentsResult` carries the final round's clearing — `generators`, `loads`, `buses`,
`branches` and the three settlement figures, mirroring `MarketNodalResult` field for field and row
type for row type — plus:

| Field | What it is |
| --- | --- |
| `offers` | One `AgentOfferResult` per agent, in `NetworkArrays` generator order |
| `iterations` | Update rounds run after round 0; the market was cleared `iterations + 1` times |
| `converged` | Whether the **loop** settled — never a statement about the LP |
| `termination_reason` | `converged` \| `iteration_cap` \| `cycle`; `None` exactly when `status != "Optimal"` |

A generator no strategy names is **not** an agent: it clears at its own true cost, exactly as
`market.nodal` would clear it, and appears under `generators` only.

Each `AgentOfferResult` carries `offer` and `true_cost` whole, as `GeneratorCost` objects, beside
the `cleared_mw` they were settled at and the `markup` between them. `markup` is not independent
content — it is exactly `offer(cleared_mw) - true_cost(cleared_mw)`, and the test suite asserts it
as that identity rather than as a third number.

`strategy` on each row records which rule produced the offer: the `StrategyConfig.kind` when
`solve_agents` built the strategy from options, or the class name of an object passed through the
in-process seam below.

## Using it

The full worked example is [`examples/12_agent_market.py`](../examples/index.md#12-strategic-bidding).
In brief:

```python
from mambo_power.market.agents import MarketAgentsOptions, solve_agents
from mambo_power.model import Scenario

result = solve_agents(
    Scenario(network=net),
    MarketAgentsOptions(
        strategies={"g1": {"kind": "markup", "step": 0.5}, "g2": {"kind": "price_taker"}},
        offer_tol=1.5,  # >= 3 * step, and validated as such
        max_iterations=200,  # a bound, not a target
    ),
)
```

An **empty** `strategies` mapping is meaningful rather than missing: it is a market in which
nobody bids strategically, and it clears exactly as `market.nodal` would.

### The in-process seam

`Strategy` is a `typing.Protocol`, so `solve_agents` also takes a `strategies=` keyword accepting
any object with a conforming `offer` method:

```python
class AlwaysDouble:
    def offer(self, observation):
        c1, c0 = observation.true_cost.coefficients
        return observation.true_cost.model_copy(update={"coefficients": [2 * c1, c0]})


result = solve_agents(scenario, strategies={"g1": AlwaysDouble()})
```

This exists for a rule the `StrategyConfig` union cannot express — one with parameters the union
does not carry, or one belonging to the caller rather than to this library. Giving both
`options.strategies` and `strategies=` raises, so an agent set always has exactly one source and
the result can say which rule ran. Only the config union crosses JSON, so `jobs` cannot reach this
seam: nothing a service sends decides which code runs.

## Errors

`solve_agents` never raises for an infeasible or unbounded clearing — that is reported through
`status` and `message`, the same convention `solve_nodal` follows. It does raise up front,
before any solve, for a mistake in the agent set:

| The mistake | Raised |
| --- | --- |
| Both `options.strategies` and `strategies=` given | `AgentSetError` (a `ValueError` subclass; every row below is the same type) |
| A strategy naming a generator the network does not have | `AgentSetError` |
| A strategy naming a generator the arrays do not carry (out of service, or on a bus that is) | `AgentSetError` |
| A strategy naming a generator with no `Generator.cost` to depart from | `AgentSetError` |
| An injected `MarkupStrategy` whose step is too coarse for `offer_tol` | `AgentSetError` |
| A strategy that cannot bid on its generator's true cost (a `MarkupStrategy` on a quadratic or piecewise cost) | `AgentSetError`, naming the generator, before the first clearing; the strategy's own `NotImplementedError` is chained as the cause |
| A strategy whose `offer` returned something other than a `GeneratorCost` (`None`, say) | `TypeError`, naming the generator and what came back, at the call site before that round's clearing |
| An offer a strategy produced that the clearing cannot accept | `NonConvexCostError` / `NonConcaveBidError` |

The first six are raised up front, before any solve. The `offer_tol` rule is also enforced by
`MarketAgentsOptions` itself, so through the config path that one arrives as pydantic's
`ValidationError` (a `ValueError` subclass) at construction, not from `solve_agents`. The
convexity guards are applied to the **offer**, every round, exactly as they would be to a true
cost: a strategy does not get a laxer contract than the network does.

## Jobs API

Registered as `market.agents`, the eighth kind. `MarketAgentsOptions.strategies` crosses as
data — a discriminated union on `kind`, never a callable — and every way of getting the agent set
wrong maps to `BAD_OPTIONS` or `VALIDATION`, never `INTERNAL`. See the
[jobs manual page](jobs.md#relationship-to-the-module-level-functions) for the full mapping.

```python
from mambo_power import jobs

reply = jobs.run(
    jobs.SolveRequest(
        kind="market.agents",
        network=net,
        options={"strategies": {"g1": {"kind": "markup", "step": 0.5}}, "offer_tol": 1.5},
    )
)
print(reply.status, reply.result.converged, reply.result.termination_reason)
```

```text
ok True converged
```

A non-converged run is a **successful job** with an honest result, not a failure: `status="ok"`
means the clearing solved, and `converged` is a separate question the caller reads for itself.
