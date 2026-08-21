# Examples

Runnable scripts live under `examples/` in the repository. Each one is executed in CI against
the installed package on every push, and the manual pages embed them with `pymdownx.snippets`
so the documentation and the executed code are the same bytes. Run any of them from a clone:

```bash
uv run python examples/<name>.py
```

| Script | What it shows | Manual page |
| --- | --- | --- |
| `load_and_inspect.py` | Load a MATPOWER case with `load_with_warnings`, print counts, walk buses and branches, list the repair warnings. | [File formats](../manual/formats.md) |
| `validate_network.py` | Build a deliberately broken `Network`, catch `NetworkValidationError`, print every issue with its code and path; repair it and re-check with `validate_network`. | [Network model](../manual/model.md) |
| `native_roundtrip.py` | Save a network as native JSON with `native.save`, reload it, assert equality; export the JSON schema. | [File formats](../manual/formats.md) |
| `dc_power_flow.py` | `pf.solve_dc` on case14: print bus angles, branch flows, generator dispatch and the provenance stamp; show the slack balance. | [Power flow](../manual/power-flow.md) |
| `network_matrices.py` | `NetworkArrays`, `ybus`, `bbus`, `ptdf`, `lodf`, `bridges` on case14; a 100 MW transfer through the PTDF; the NaN bridge column. | [Numerics](../manual/numerics.md) |
| `results_roundtrip.py` | Serialise a `DcPowerFlowResult` to JSON and back, use `to_arrays()` to find the most loaded branch. | [Results](../manual/results.md) |
| `ac_power_flow.py` | `pf.solve_ac` with and without Q-limit enforcement on case118; compare pinned generators; warm vs flat start. *Added when the AC solver lands.* | [Power flow](../manual/power-flow.md) |
| `jobs_api.py` | Build a `SolveRequest`, call `jobs.run`, inspect `status`, show a failed request carrying a structured error, list `jobs.KINDS`. *Added when the jobs module lands.* | [Jobs API](../manual/jobs.md) |

!!! note
    The scripts are being added in this wave (M2, slice S7). Until they land, every manual
    page carries inline, executed code blocks with their real output — the same content the
    scripts will replace.

## Conventions for examples

- Each script is self-contained, runs from the repository root, and reads only files under
  `fixtures/`.
- Scripts print what they compute; they do not write files outside a temporary directory.
- A script that exits non-zero fails the `examples` CI job.
- Sections of a script are marked with `# --8<-- [start:name]` / `# --8<-- [end:name]` so the
  manual can embed one block at a time.
