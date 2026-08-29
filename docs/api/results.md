# `mambo_power.results`

Typed, id-keyed solver results with provenance. See the [manual page](../manual/results.md)
for field semantics, the JSON round-trip and the positional view.

::: mambo_power.results
    options:
      show_submodules: false

## Row models

::: mambo_power.results.tables

## Provenance

::: mambo_power.results.provenance

## Power-flow results

::: mambo_power.results.power_flow

## Builders

::: mambo_power.results.from_arrays

## Multiperiod market results

Per-period dispatch, LMPs and settlement, per-storage charge/discharge/SoC, and horizon totals.
Its module docstring states the settlement identity in its general form, including the
phase-shift and shunt correction terms.

::: mambo_power.results.multiperiod

## Zonal market results

Zone prices, both dispatch layers, the redispatch deltas on both sides, per-branch flows with
their shadow prices, and the three separated gap figures. Its module docstring explains why the
result carries two dispatch layers rather than one and what each of the three figures is for.

::: mambo_power.results.zonal


## Agent market results

The final round's clearing — mirroring `MarketNodalResult` field for field and row type for row
type, because they are the same clearing quantities computed the same way — plus one `offers` row
per agent and the three fields that describe how the loop ended.

`status` and `converged` are never the same thing and never fold into each other: `status` is
HiGHS's verdict on the final round's clearing, `converged` is whether the best-response iteration
settled, and a run can be `Optimal` every round without converging. `termination_reason` is
required and enumerated rather than inferred from the flag, because reporting a genuine cycle as
an iteration-cap hit would be a confident wrong diagnosis. `AgentOfferResult.markup` is not
independent content: it is exactly `offer(cleared_mw) - true_cost(cleared_mw)`, and the wave's
tests assert it as that identity.

::: mambo_power.results.agents
