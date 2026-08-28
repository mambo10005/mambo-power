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
