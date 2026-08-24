# DC-OPF

`mambo_power.opf` holds the DC optimal power flow (DC-OPF) solver: the cost-minimising
generator dispatch subject to the same linearised network `pf.solve_dc` solves, plus generator
bounds and per-branch flow limits, over [HiGHS](https://highs.dev). The public entry point takes
a `Network` and returns a typed [result](results.md) with shadow prices; the array-level solver
works on [`NetworkArrays`](numerics.md) and a caller-supplied cost array. The network is never
modified.

| Entry point | Returns |
| --- | --- |
| `opf.solve_dc_opf(net, options=None)` | `OpfDcResult` |
| `opf.dc_opf.dc_opf(arr, cost_coeffs, options, pwl_costs=None)` | `OpfSolution` (positional, MW) |
| `opf.dc_opf.lmp_decomposition(duals, ptdf)` | `LmpBreakdown` (positional) |

Runnable script: [`08_opf_and_n1.py`](../examples/index.md#8-opf-and-n-1).

## Formulation

One decision variable per generator, bounded by its declared `[p_min_mw, p_max_mw]`. Two row
families, both built directly against `highspy.Highs`:

* **One system-wide nodal-balance equality row**: `Σ p_g == Σ p_load + Σ g_shunt`. A DC/lossless
  network has no other sink, and phase-shifter injections net to zero system-wide by
  construction, so they never enter this row. Its dual is the *energy* component of every bus's
  LMP.
* **One PTDF-based flow-limit row per branch**: `-rating <= Σ_g PTDF[k, gen_bus[g]]·p_g +
  const_k <= rating`, where `const_k` folds in the branch's fixed (load/shunt/phase-shift)
  contribution to its flow — the same [PTDF](numerics.md#power-transfer-distribution-factors-ptdf)
  the numerics module already builds and parity-tests on its own. An unrated branch (`rating ==
  inf`) gets an unconstrained row that never binds; its dual is always 0 — true of every bundled
  MATPOWER fixture (none carries a real `RATE_A`; [`08_opf_and_n1.py`](../examples/index.md#8-opf-and-n-1)
  synthesises one to show a binding row at all).

### Cost: LP when linear, QP when quadratic

`cost_coeffs` is a caller-supplied `(n_gen, 3)` array, columns `[c2, c1, c0]` (the same order as
`PolynomialCost.coefficients`, zero-padded). Every one of the five bundled OPF fixtures carries
genuine nonzero quadratic (`c2`) coefficients, and pandapower's own `rundcopp` honours them — so
matching real fixture data requires the quadratic term, not just the linear one. `dc_opf` stays a
pure LP (no Hessian at all) whenever every generator's `c2` is exactly 0, and transparently
extends to a convex QP via `Highs.passHessian` (diagonal Hessian value `2·c2[g]`, HiGHS's
`0.5·xᵀQx` convention) only when a nonzero `c2` is present. Duals are read identically either
way — `Highs.getSolution().row_dual` / `col_dual` need no QP-specific handling.

Startup/shutdown costs (`PolynomialCost.startup`/`shutdown`) are not modelled: this is a
single-period economic dispatch over already-committed generators, matching pandapower's
`rundcopp`.

### Piecewise-linear costs

A generator with a convex `PiecewiseCost` is passed through `dc_opf`'s `pwl_costs` argument
instead of `cost_coeffs` (that generator's `cost_coeffs` row is all-zero — its cost is captured
entirely by the rows described here). The standard convex **segment/epigraph LP encoding**: for
each PWL generator with breakpoints \((p_0,c_0),\dots,(p_n,c_n)\), one new free variable
\(\text{cost}_g\) is added with objective coefficient 1, plus one inequality row per segment,

\[
\text{cost}_g \ge \text{slope}_i \cdot p_g + \text{intercept}_i, \qquad
\text{slope}_i = \frac{c_{i+1}-c_i}{p_{i+1}-p_i}, \qquad
\text{intercept}_i = c_i - \text{slope}_i \cdot p_i .
\]

Because minimising the LP pulls \(\text{cost}_g\) down to the tightest bound, and the segment
slopes are non-decreasing (convex), the upper envelope of these lines equals the true piecewise
cost exactly on \([p_0, p_n]\) — the standard epigraph trick. It composes unchanged with the QP
path above: a network may mix quadratic and PWL generators in the same solve. **Only valid when
the breakpoints span the generator's own `[p_min, p_max]`** — outside that range the epigraph
rows extrapolate along the boundary segments' slopes.

A non-convex breakpoint sequence (a decreasing segment slope) raises `opf.NonConvexCostError`
before any HiGHS object is created — fail fast, not a wrong-but-optimal-looking LP answer; an LP
built from a non-convex PWL curve silently produces the wrong dispatch, since the encoding above
is only valid for convex costs. This is deliberately an `opf`-local check:
`model.PiecewiseCost` itself validates only strictly-increasing `p_mw`, not convexity.

`opf.solve_dc_opf` supports polynomial costs up to quadratic only; a degree-3-or-higher
`PolynomialCost` raises `NotImplementedError` at cost extraction, before any solve is attempted.

**Oracle limitation, found verifying this against pandapower.** pandapower's `rundcopp` genuinely
supports PWL costs, but its own `make_objective._init_gencost` refuses to mix quadratic and
piecewise-linear costs anywhere in one network — a network-wide check, not per-generator. The
wave's own PWL fixture (`fixtures/matpower/derived/case14_pwl.m`, two of case14's five generators
converted to convex PWL, the rest keeping their real quadratic coefficients) therefore cannot be
oracled by pandapower at all; verification fell back to an independent lambda-iteration
economic-dispatch solver, since case14 carries no rated branch and DC-OPF with none collapses to
classic equal-marginal-cost dispatch. That derivation also produced a genuine LP degeneracy: two
of the fixture's breakpoints tie in marginal cost, so the LP has multiple optima for how the two
affected generators split their combined output — asserted as an interval in
`tests/unit/test_opf_dc_case14_pwl.py`, not a false-precise split, while the other three
generators and the total system cost are uniquely pinned.

## Duals and locational marginal prices

`dc_opf` returns `OpfDuals`: `balance` (the single system-wide row's shadow price, $/MWh —
also exactly an *unconstrained* slack-bus generator's own linear cost coefficient, since a slack
bus's PTDF column is always zero), `flow_limit` (per branch, 0 off the binding set), and
`gen_bound` (per generator, 0 unless pinned at `p_min` or `p_max`).

`lmp_decomposition(duals, ptdf) -> LmpBreakdown` — standalone and independent of `dc_opf` /
`solve_dc_opf`, callable with any hand-built `OpfDuals`/PTDF pair — splits every bus's price into

\[
\text{lmp}_b = \underbrace{\lambda_\text{balance}}_{\text{energy, uniform system-wide}} +
\underbrace{\sum_k \mu_k \cdot \text{PTDF}[k, b]}_{\text{congestion, bus's exposure to every binding row}} .
\]

`solve_dc_opf` calls it to populate `OpfDcResult.lmp`; a later wave's `market.nodal` calls the
identical function with its own duals. On every bundled fixture as shipped, `congestion` is 0 at
every bus (no branch is rated) — LMP is pure energy until a rating actually binds.

## The AC-feasibility check

DC-OPF optimises against no voltage constraint at all: a cost-minimising DC dispatch is not
automatically AC-feasible. `OpfDcOptions.ac_check=True` re-runs `pf.solve_ac` on the dispatched
network — a deep copy with each in-service generator's `p_mw` overwritten from the DC-OPF
dispatch (id-keyed) — and attaches a [`FeasibilityReport`](results.md) as
`OpfDcResult.ac_check`: `converged`, thermal violations (`loading_pct > 100%`), voltage
violations (outside `Bus.v_min_pu`/`v_max_pu`). No re-dispatch is attempted on a violation — this
reports, it does not fix; `08_opf_and_n1.py` shows a real case, case14's own DC-OPF-optimal
dispatch, landing on 3 buses outside their declared 1.06 pu upper bound once AC-solved.

## Formulation note: PTDF-based dispatch vs pandapower's theta-based `rundcopp`

`opf.dc_opf` and pandapower's `rundcopp` solve genuinely different formulations that happen to
agree on every bundled fixture, not the same formulation. pandapower's `rundcopp` marks the
slack-bus generator (`ext_grid`) `controllable=False`: it solves a full nodal, theta-based OPF
where the slack generator's dispatch is the network's power-balance residual — a *dependent*
variable, not a decision variable in the optimisation, though its real cost coefficients are
still charged in the reported total cost. `opf.dc_opf`'s PTDF-based formulation makes *every*
generator, including the one at the slack bus, a normal decision variable bounded by its own
`[p_min, p_max]` in the single system-wide balance row.

The two formulations are only **guaranteed** to produce the same dispatch and cost when:

1. no branch is rated, so `dc_opf`'s flow-limit rows never bind (confirmed true of all five
   bundled fixtures — none carries a real `RATE_A`); and
2. the slack-bus generator's own bounds never happen to bind in pandapower's unconstrained
   dispatch of it (measured true on all five fixtures — e.g. case14's `ext_grid` dispatches
   ~221 MW against declared bounds `[0, 332.4]`, comfortably interior — but not proven true in
   general).

Both conditions were checked directly, not assumed: the parity suite
(`tests/parity/test_opf_vs_pandapower.py`) asserts every branch's flow-limit dual is exactly 0 on
all five fixtures, confirming (1), alongside the measured dispatch/cost residuals themselves,
which confirm (2) empirically. A future fixture with a tightly-bound slack generator, or a real
`RATE_A`, could diverge from `rundcopp` and would need revisiting on its own terms — this is
named as a real formulation difference, not rounded into a looser tolerance that would also mask
an unrelated regression on the other fixtures.

## Errors

`opf.NonConvexCostError` (a `ValueError` subclass) is raised before any solve for a non-convex
`PiecewiseCost`. `NotImplementedError` is raised for a polynomial cost above degree 2. Neither
of these is reachable through the [jobs API](jobs.md) yet as a structured failure — an
`opf.dc` job that hits one surfaces as `INTERNAL`. `solve_dc_opf` itself never raises for an
infeasible or unbounded LP/QP: it is reported through `OpfDcResult.status` /
`message` (HiGHS's own model-status string), mirroring `pf.solve_ac`'s
never-raise-on-non-convergence convention. Through the [jobs API](jobs.md), a non-`"Optimal"`
`opf.dc` job comes back as a structured failure — `INFEASIBLE_LP` or `UNBOUNDED_LP` — not a
"successful" result carrying a meaningless dispatch.

## Using it

```python
from mambo_power import opf
from mambo_power.io import matpower

net = matpower.load("fixtures/matpower/case14.m")
result = opf.solve_dc_opf(net)
print(result.provenance.kind, result.provenance.solver, result.status)
print(result.objective_cost, result.balance_dual)
print(result.generators[0])
print(result.buses[0])
```

```text
opf.dc highspy.Highs Optimal
7642.591776958785 39.0161721283176
id='gen-1' bus='bus-1' p_mw=220.96766334983212 bound_dual=0.0
id='bus-1' lmp=39.0161721283176 energy=39.0161721283176 congestion=0.0
```

See [`08_opf_and_n1.py`](../examples/index.md#8-opf-and-n-1) for the AC-feasibility check, a
tightened rating that actually binds (nonzero flow-limit dual, congestion split across buses),
and the follow-on N-1 screen on the same network.
