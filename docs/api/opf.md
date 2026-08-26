# `mambo_power.opf`

DC optimal power flow, single-period and multiperiod. See the [manual
page](../manual/opf.md) for the formulation, duals, piecewise-linear costs and the
pandapower formulation caveat, and the [multiperiod manual
page](../manual/multiperiod.md) for the coupling row families this builder adds.

::: mambo_power.opf
    options:
      show_submodules: false

## LP/QP builder over arrays

::: mambo_power.opf.dc_opf

## Multiperiod LP/QP builder over arrays

The `T`-loop over `dc_opf`'s own row families plus the three coupling families. Its module
docstring carries the column layout and the row-index contract the duals are read back against.

::: mambo_power.opf.multiperiod
