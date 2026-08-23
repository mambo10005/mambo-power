# Examples

Seven runnable scripts live under `examples/` in the repository. Each one is self-contained,
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

## Conventions for examples

- Each script is self-contained, runs from the repository root, and reads only files under
  `fixtures/`. It prints what it computes and writes nothing outside a temporary directory.
- Numbered `NN_name.py`; the module docstring says what the script shows and how to run it.
- A script that exits non-zero fails `tests/unit/test_examples_run.py` and the `examples` CI
  job; a script that is not embedded on this page fails the same test.
- Embedding uses the `{ .python }` fence form on purpose: `ruff format` rewrites Python
  fences in Markdown and would turn the `--8<--` marker into an expression.
