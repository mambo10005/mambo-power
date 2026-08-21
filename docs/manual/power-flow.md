# Power flow

`mambo_power.pf` holds the power-flow solvers. Public entry points take a `Network` and return
a typed [result](results.md) with provenance; the array-level solvers work on
[`NetworkArrays`](numerics.md) only and return plain positional arrays. The network is never
modified.

| Entry point | Status | Returns |
| --- | --- | --- |
| `pf.solve_dc(net)` | shipped | `DcPowerFlowResult` |
| `pf.dc.solve(arr)` | shipped | `DcSolution` (positional, pu) |
| `pf.solve_ac(net, *, options=AcOptions())` | landing in wave M2 | `AcPowerFlowResult` |
| `pf.ac_newton.newton(arr, opts)` | landing in wave M2 | positional solution |

## DC power flow

The DC model is the lossless linearisation: flat voltage magnitudes, small angle differences,
resistance and line charging ignored. It is exact for what it models and is the workhorse of
PTDF-based contingency analysis and DC optimal power flow.

### Formulation

With \(B'\) the DC susceptance matrix, \(B_f\) the from-side flow matrix, and the
phase-shifter injections \(P_\text{shift} = C_{ft}^\top P_{f,\text{shift}}\),
\(P_{f,\text{shift}} = -b \odot \phi\) (all from [numerics](numerics.md#dc-susceptance-matrices-bbus-bf-p_shift)),
the declared net injection per bus in per unit is

\[
P_\text{bus} = P_\text{gen} - P_\text{load} - G_\text{shunt}
\]

where \(G_\text{shunt}\) is the shunt conductance consumption at 1.0 pu. The angles solve the
linear system with the slack row and column removed and the slack angle fixed at zero:

\[
B'[\text{keep},\text{keep}]\;\theta[\text{keep}] = (P_\text{bus} - P_\text{shift})[\text{keep}],
\qquad \theta_\text{slack} = 0 .
\]

Flows and realised injections follow:

\[
P_f = B_f\,\theta + P_{f,\text{shift}}, \qquad P_t = -P_f, \qquad
P_\text{inj} = B'\,\theta + P_\text{shift} .
\]

\(P_\text{inj}\) equals \(P_\text{bus}\) on every non-slack bus; at the slack it is whatever
closes the balance (lossless, so \(\sum P_\text{inj} = 0\)). These are exactly MATPOWER
`rundcpf`'s steps — which pandapower's `rundcpp` copies — and the parity test asserts equality
with `rundcpp` within 1e-9 on every fixture including case300.

The reduced system is factorised with `scipy.sparse.linalg.splu`, the same backend as the PTDF
builder and the AC solver; the provenance records `solver = "scipy.sparse.linalg.splu"`.

### Slack convention

The slack-bus balance goes **entirely to the first in-service generator at the slack bus**;
every other generator keeps its declared dispatch. This is MATPOWER's rule
(`gen(on(refgen(1)), PG) += ...`) and the number pandapower reports on `res_ext_grid`. Bus-level
generation is therefore engine-independent; the per-generator split is this documented
convention. If the slack bus has no in-service generator the balance is still visible on the
bus injection; naming that situation is the job of [effective roles](#effective-bus-roles).

### Errors

`pf.dc.solve` raises `ValueError` when a branch has `x == 0` (susceptance undefined) or when
the reduced \(B'\) is singular or yields non-finite angles — an islanded bus set that slipped
past validation. Through the [jobs API](jobs.md) these become structured failures.

### The result

`solve_dc` returns a `DcPowerFlowResult` in MW keyed by ids: `vm_pu = 1.0` on every bus
(MATPOWER `rundcpf` sets `VM = 1`), all reactive columns 0, `converged = True` always,
`p_to_mw = -p_from_mw` on every branch, `loading_pct` from the from-side flow over
`rating_mva` or `None` when unrated. See [Results](results.md).

```python
from mambo_power import pf
from mambo_power.io import matpower

net = matpower.load("fixtures/matpower/case14.m")
result = pf.solve_dc(net)
print(result.provenance.kind, result.provenance.solver, result.converged)
print(result.buses[1].va_deg, result.branches[0].p_from_mw, result.generators[0].p_mw)
```

```text
pf.dc scipy.sparse.linalg.splu True
-5.01201116593048 147.83859555890945 218.99999999999983
```

Positional use, when you already have arrays:

```python
from mambo_power.numerics import NetworkArrays
from mambo_power.pf import dc

arr = NetworkArrays.from_network(net)
sol = dc.solve(arr)  # DcSolution: theta_rad, p_from_pu, p_inj_pu, gen_p_pu
print(sol.theta_rad[arr.slack], sol.p_from_pu[0] * arr.base_mva)
```

```text
0.0 147.83859555890945
```

## AC power flow

!!! warning "Landing in wave M2"
    The AC Newton-Raphson solver is being implemented in the same wave as this page. What
    follows is its **design contract** — the semantics the implementation is tested against.
    The API names below are fixed; the [API reference](../api/pf.md) lists them once they
    exist.

### API

```python
from mambo_power import pf

result = pf.solve_ac(net, options=pf.AcOptions(tol=1e-8, max_iter=20, q_limits=True))
```

`AcOptions` fields:

| Option | Default | Meaning |
| --- | --- | --- |
| `tol` | `1e-8` | Convergence tolerance on the ∞-norm of the power mismatch, pu. |
| `max_iter` | `20` | Newton iterations per round. |
| `q_limits` | `True` | Enforce generator reactive limits (see below). |
| `max_q_rounds` | `10` | Maximum outer Q-limit rounds. |
| `init` | `"auto"` | `"auto"` warm-starts from `Bus.vm_pu` / `va_deg` when **every** in-service bus carries both, else flat; `"flat"` forces 1.0∠0 with PV and slack buses at their setpoint. |

### Formulation: polar Newton-Raphson

Unknowns are the angles at every non-slack bus and the magnitudes at every PQ bus. With
\(S = V \odot (Y_\text{bus} V)^*\) the complex injections, the mismatch is

\[
f(\theta, |V|) =
\begin{bmatrix}
\Re\{S\}_{\text{pv} \cup \text{pq}} - P^\text{spec}_{\text{pv} \cup \text{pq}} \\
\Im\{S\}_{\text{pq}} - Q^\text{spec}_{\text{pq}}
\end{bmatrix}
\]

and each iteration solves \(J\,\Delta x = -f\) with the sparse Jacobian

\[
J = \begin{bmatrix} \partial P/\partial\theta & \partial P/\partial|V| \\
\partial Q/\partial\theta & \partial Q/\partial|V| \end{bmatrix}
\]

factorised by `scipy.sparse.linalg.splu`. Convergence is declared when
\(\|f\|_\infty < \text{tol}\); the result records `iterations` and `max_mismatch_mva`
(the final ∞-norm in MVA). Failure to converge within `max_iter` gives `converged = False`
with the last iterate — never an exception.

### Q-limit enforcement (pandapower semantics, decision D2)

After each converged inner solve, every PV bus whose total reactive output lies outside its
summed generator limits is **pinned** to PQ at the breached limit and the solve repeats:

- pins accumulate across rounds and are **never restored** (no PQ→PV switch back);
- the slack bus is never limited;
- the comparison is strict (`q > q_max` or `q < q_min`);
- at most `max_q_rounds` rounds run; the result's `q_limit_rounds` counts them;
- each pinned generator's `GenResult.q_limited` reports `"min"` or `"max"`.

This matches pandapower `runpp(enforce_q_lims=True)` exactly — the parity test requires the
same set of pinned buses on the same side on every fixture where limits bind — and differs
from MATPOWER only in that MATPOWER re-slacks when the slack generator itself hits a limit.

### Effective bus roles

The declared `Bus.type` is the input; the role the solver uses is derived by
`numerics.effective_roles(arr)`, the single derivation site:

| Situation | Effective role |
| --- | --- |
| PV bus with at least one in-service generator | PV, setpoint from the generators |
| PV bus with **no** in-service generator | **PQ** (both oracles agree) |
| Slack bus with no in-service generator | raises `NoSlackGeneratorError` |
| Several in-service generators on one bus | setpoint is the **last** one's `v_set_pu` (MATPOWER's rule); a `SetpointConflictWarning` is emitted when the setpoints differ |

`NetworkArrays.bus_type` keeps the declared roles; solvers consume the effective ones, and
every `BusResult.role_effective` reports the role the bus was actually solved with. DC power
flow does not need setpoints, so its `role_effective` is the declared role.

### Islands (decision D1)

The AC solver assumes the in-service subset is connected — the model guarantees it. Files
with islands are repaired by the importer (buses unreachable from the slack and their
elements are deactivated, with an `ISLAND_DEACTIVATED` warning) before the network is
validated; see [File formats › Islands](formats.md#islands).

### Verification

pandapower `runpp(init="flat", tolerance_mva=1e-8)` is the primary oracle: voltage
magnitudes within 1e-6 pu, angles within 1e-4 degrees, branch flows within 1e-4 MVA on
case14, case_ieee30, case57 and case118 (Q-limits on) and case300 (Q-limits off). MATPOWER's
stored VM/VA columns are a secondary check at file precision with a documented exclusion list
per case. case300 from a flat start must converge in under 1.0 s cold on the CI Ubuntu job;
the measured figure is recorded in the changelog when the solver lands.

## Choosing between DC and AC

| | DC | AC |
| --- | --- | --- |
| Models | active power, angles | active + reactive power, magnitudes + angles |
| Losses | none | yes |
| Solve | one sparse linear solve | Newton iterations, Q-limit rounds |
| Always converges | yes (if connected) | no — check `converged` |
| Use for | screening, PTDF/LODF, DC-OPF, markets | voltage studies, AC feasibility check after DC-OPF |
