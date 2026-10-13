# `mambo_power.opf`

Optimal power flow: DC single-period, AC single-period, security-constrained, multiperiod,
zonal, and redispatch. The DC builders share one row-family core and one cost/bid extractor; the
AC solver reuses the power flow's Jacobian and the epigraph encoding. See the [manual page](../manual/opf.md)
for the formulation, duals, piecewise-linear costs and the pandapower formulation caveat, the
[multiperiod manual page](../manual/multiperiod.md) for the coupling row families, and the
[zonal manual page](../manual/zonal.md) for the per-zone balance rows, the corridor sign
convention and the redispatch delta columns, and the [security-constrained OPF
page](../manual/scopf.md) for the post-contingency rows and the constraint-generation loop.

::: mambo_power.opf
    options:
      show_submodules: false

## LP/QP builder over arrays

::: mambo_power.opf.dc_opf

## AC-OPF over arrays

Trust-region sequential LP with a power-flow restoration (ADR-018). Its module docstring carries
the formulation, the chord model of a quadratic cost and the convergence test; the
[manual page](../manual/ac-opf.md) has the parity table.

::: mambo_power.opf.ac_opf

## Security-constrained builder over arrays

Constraint generation around `dc_opf`: the N-1 screen of each dispatch supplies the
(outage, branch) pairs whose post-contingency flow rows are added for the next solve. Its module
docstring carries the row algebra for branch and generator outages and the convergence argument.

::: mambo_power.opf.scopf

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
