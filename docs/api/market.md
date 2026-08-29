# `mambo_power.market`

Market clearing at three granularities: one period nodally, a whole horizon, and one period
zonally with the redispatch that makes it deliverable. See the [nodal manual
page](../manual/market.md) for the elastic-demand formulation, LMP/settlement decomposition, the
price-taker reduction and the oracle convention, the [multiperiod manual
page](../manual/multiperiod.md) for ramp coupling, storage state of charge, the cyclic horizon
and the per-period settlement, and the [zonal manual page](../manual/zonal.md) for the
three-solve chain, corridors, and the three separated gap figures.

::: mambo_power.market
    options:
      show_submodules: false

## Welfare LP over a `Scenario`

::: mambo_power.market.nodal

## Multiperiod clearing over a horizon

::: mambo_power.market.multiperiod

## Zonal clearing and redispatch

The three-solve chain: a zonal clearing, a minimum-cost redispatch onto the real network, and
`market.solve_nodal` as the reference. Its module docstring states where each of the three
reported figures comes from and why the third one is not sign-constrained.

::: mambo_power.market.zonal

## The strategy seam

One generator's bidding rule, and nothing else: an own-node `Observation` in, the `GeneratorCost`
it offers next out. `Observation` carries the agent's own true cost curve and active limits, the
round it is bidding into, and its own **last two rounds** of `(offer, bus LMP, cleared MW)` — it
names no rival, no other bus, and no part of the clearing as a whole, so a strategy cannot
reconstruct the market it is bidding into. Two rounds rather than one because a single round tells
an agent whether it is marginal but not whether its last move *helped*. A round that has not
happened is `None`, never a zero-valued `RoundRecord`, and a record from the wrong round is
rejected rather than accepted as adjacent.

`Strategy` is a `typing.Protocol`, so an in-process caller may hand the seam any object with a
matching `offer` method without inheriting from anything. What crosses JSON is never a callable:
`StrategyConfig` is a discriminated union on `kind` — the same shape as `GeneratorCost` and
`LoadBid` — and `build_strategy` is the one place a config becomes an instance.

`MarkupStrategy` is scoped to a **linear** `PolynomialCost` and raises `NotImplementedError` on
any other cost shape: a piecewise or higher-degree curve has no single scalar the climb has
established a meaning for. Every generator in every MATPOWER fixture this package ships carries a
quadratic cost (147 of 147, measured), so a markup agent applies only to a network built for one;
`PriceTakerStrategy` carries no such restriction and returns the true cost verbatim whatever its
shape.

::: mambo_power.market.strategy
