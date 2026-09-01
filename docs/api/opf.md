# `mambo_power.opf`

DC optimal power flow: single-period, multiperiod, zonal, and redispatch. All four builders
share one row-family core and one cost/bid extractor. See the [manual page](../manual/opf.md)
for the formulation, duals, piecewise-linear costs and the pandapower formulation caveat, the
[multiperiod manual page](../manual/multiperiod.md) for the coupling row families, and the
[zonal manual page](../manual/zonal.md) for the per-zone balance rows, the corridor sign
convention and the redispatch delta columns.

::: mambo_power.opf
    options:
      show_submodules: false

## LP/QP builder over arrays

::: mambo_power.opf.dc_opf

## Multiperiod LP/QP builder over arrays

The `T`-loop over `dc_opf`'s own row families plus the three coupling families. Its module
docstring carries the column layout and the row-index contract the duals are read back against.

::: mambo_power.opf.multiperiod

## Zonal LP/QP builder over arrays

One balance row per zone, one bounded exchange column per tied zone pair, and no branch flow
rows at all. Its module docstring carries the corridor sign convention, the column layout and
the argument for omitting phase shifters from the per-zone rows.

::: mambo_power.opf.zonal

## Redispatch LP/QP builder over arrays

The minimum-cost move from a zonal operating point to a network-feasible one, with delta columns
on both sides of the market. Its module docstring carries the true-curve objective, the linking
column piecewise-linear participants need, and the theorem that makes the result the nodal
optimum.

::: mambo_power.opf.redispatch
