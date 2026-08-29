# Examples

Twelve runnable scripts live under `examples/` in the repository. Each one is self-contained,
reads only files under `fixtures/`, prints a short deterministic summary and exits 0 in about a
second. They are executed on every push — by `tests/unit/test_examples_run.py` inside the test
matrix and by the dedicated `examples` CI job — and this page embeds them with
`pymdownx.snippets`, so the code you read here and the code CI ran are the same bytes.

Run any of them from a clone, from the repository root:

```bash
uv run python examples/02_ac_power_flow.py
```

| Script | Shows | Manual page |
| --- | --- | --- |
| [`01_load_and_validate.py`](#1-load-and-validate) | `load_with_report`, a hand-built network, all-issues validation | [Network model](../manual/model.md), [File formats](../manual/formats.md) |
| [`02_ac_power_flow.py`](#2-ac-power-flow) | `solve_ac` with and without Q-limits, voltages, loading table, warm start | [Power flow](../manual/power-flow.md) |
| [`03_dc_power_flow.py`](#3-dc-power-flow) | `solve_dc` on case300, DC vs AC flows | [Power flow](../manual/power-flow.md) |
| [`04_jobs_api.py`](#4-jobs-api) | `SolveRequest` / `run` / `run_json`, structured failures, captured warnings | [Jobs API](../manual/jobs.md) |
| [`05_roles_and_islands.py`](#5-roles-and-islands) | effective bus roles, `NoSlackGeneratorError`, island repair vs strict model | [Power flow](../manual/power-flow.md#effective-bus-roles), [File formats](../manual/formats.md#islands) |
| [`06_network_matrices.py`](#6-network-matrices) | `NetworkArrays`, Ybus sparsity, PTDF, LODF with the bridge `NaN` column, a 3-bus case in full | [Numerics](../manual/numerics.md) |
| [`07_results_and_export.py`](#7-results-and-export) | JSON round trip, `to_arrays()`, CSV export | [Results](../manual/results.md) |
| [`08_opf_and_n1.py`](#8-opf-and-n-1) | `solve_dc_opf` dispatch/duals/LMP, `ac_check`, congestion, `contingency.n1` screen-then-confirm | [DC-OPF](../manual/opf.md), [N-1 screening](../manual/n1.md) |
| [`09_nodal_market.py`](#9-nodal-market) | `market.solve_nodal` on a `Scenario`: elastic-demand dispatch, LMPs split by congestion, settlement | [Nodal market](../manual/market.md) |
| [`10_multiperiod_market.py`](#10-multiperiod-market) | `market.solve_multiperiod` over a 24-period `Scenario`: ramp coupling, storage SoC with efficiency, the cyclic horizon, per-period LMPs and settlement | [Multiperiod market](../manual/multiperiod.md) |
| [`11_zonal_redispatch.py`](#11-zonal-redispatch) | `market.solve_zonal`: zonal clearing, min-cost redispatch, the nodal reference, corridor duals, the three gap figures and the settlement identity | [Zonal market](../manual/zonal.md) |
| [`12_agent_market.py`](#12-strategic-bidding) | `market.solve_agents`: generators offering through a `Strategy`, price-takers reproducing `solve_nodal` bit-exactly, a pivotal markup stopping at demand's own bid, the duopoly, `termination_reason`, `StrategyConfig` crossing `jobs` as JSON | [Agent-based bidding](../manual/agents.md) |

## 1. Load and validate

Load case14 with `load_with_report` and read the typed `ImportIssue` entries; build a 3-bus
network by hand; make the model reject a broken document with every issue listed at once.

``` { .python }
--8<-- "examples/01_load_and_validate.py"
```

## 2. AC power flow

Newton-Raphson on case14 and case118 with Q-limits on and off: iterations, rounds, mismatch,
the pinned generators, the first bus voltages, a branch-loading table and a warm start that
needs zero iterations.

``` { .python }
--8<-- "examples/02_ac_power_flow.py"
```

## 3. DC power flow

`solve_dc` on case300: angle range, the largest flows, the slack balance, and how the lossless
linear flows compare with the AC solution on the same case.

``` { .python }
--8<-- "examples/03_dc_power_flow.py"
```

## 4. Jobs API

`pf.ac` and `pf.dc` through `jobs.run`, the JSON-in / JSON-out path, three failures that come
back as structured results instead of exceptions, and a solver warning captured on the result.

``` { .python }
--8<-- "examples/04_jobs_api.py"
```

## 5. Roles and islands

The derived case14 fixtures: a PV bus solved as PQ, a setpoint conflict resolved by the
last generator, a slack without a generator, and an island the importer repairs but the model
rejects.

``` { .python }
--8<-- "examples/05_roles_and_islands.py"
```

## 6. Network matrices

`NetworkArrays`, the sparse Ybus, a 100 MW transfer through the PTDF, the LODF's `NaN`
column on case14's only bridge, and a 3-bus network whose matrices fit on the screen.

``` { .python }
--8<-- "examples/06_network_matrices.py"
```

## 7. Results and export

A result's exact JSON round trip, the positional `to_arrays()` view, and a CSV export of the
bus and branch tables with the standard library.

``` { .python }
--8<-- "examples/07_results_and_export.py"
```

## 8. OPF and N-1

Cost-minimising DC-OPF dispatch and duals on case14, the `ac_check` AC-feasibility re-solve
finding real voltage violations on an otherwise-clean dispatch, a tightened branch rating
splitting the LMP into energy and congestion, and `contingency.n1`'s LODF screen next to its
confirming DC re-solve on a flagged outage.

``` { .python }
--8<-- "examples/08_opf_and_n1.py"
```

## 9. Nodal market

`market.solve_nodal` on a hand-built 2-bus network wrapped in a `Scenario`: a bid load whose
elastic response is capped by a binding branch rating, a fixed load with no bid, the LMP split
into energy and congestion, and the settlement identity between load payment, generator
receipts, and congestion rent.

``` { .python }
--8<-- "examples/09_nodal_market.py"
```

## 10. Multiperiod market

`market.solve_multiperiod` on a 24-hour horizon over case14 with derived ratings, one storage
unit and ramp limits on every generator: the whole day cleared as one coupled LP, the unit
charging through the overnight trough and discharging into the afternoon peak, the cyclic
end-of-horizon SoC, two binding ramp rows with duals of opposite sign, the per-period settlement
with storage as a third participant, and the `periods=None` degeneracy reproducing
`market.solve_nodal` bit-exactly.

``` { .python }
--8<-- "examples/10_multiperiod_market.py"
```

## 11. Zonal redispatch

`market.solve_zonal` on a hand-solvable 2-zone/3-bus market and then on case30 with its three
MATPOWER areas promoted to zones: the corridor at its cap and the price split it creates, the
copper plate the lifted cap produces and the islanding that *deleting* the corridor produces
instead, a corridor binding in the negative direction with a positive capacity price, the zonal
schedule overloading 17 real branches where the redispatched one overloads none, the three
separated gap figures with the unsigned one negative, and both sides of the settlement identity
computed from the result object alone.

``` { .python }
--8<-- "examples/11_zonal_redispatch.py"
```

## 12. Strategic bidding

`market.solve_agents` on hand-built linear-cost networks (every bundled MATPOWER generator is
quadratic, and a markup agent needs a linear offer to mark up): the overlay proved by a
byte-identical network after every agent marked up, price-takers reproducing
`market.solve_nodal` with `array_equal` on dispatch and LMPs and no tolerance anywhere, a pivotal
supplier's markup climbing to the point where demand's own bid stops paying, checked against the
closed-form optimum, the paired control where a rival rather than demand ends the climb, the
two-agent duopoly reporting `converged`, the same run under an iteration cap reporting
`iteration_cap` instead, and the `StrategyConfig` union crossing `jobs` as JSON data.

``` { .python }
--8<-- "examples/12_agent_market.py"
```

## Conventions for examples

- Each script is self-contained, runs from the repository root, and reads only files under
  `fixtures/`. It prints what it computes and writes nothing outside a temporary directory.
- Numbered `NN_name.py`; the module docstring says what the script shows and how to run it.
- A script that exits non-zero fails `tests/unit/test_examples_run.py` and the `examples` CI
  job; a script that is not embedded on this page fails the same test.
- Embedding uses the `{ .python }` fence form on purpose: `ruff format` rewrites Python
  fences in Markdown and would turn the `--8<--` marker into an expression.
