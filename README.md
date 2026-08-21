# mambo-power

A fundamental Python package for power system analysis and electricity market modelling.
It owns its network data model and implements its own solvers on numpy, scipy and HiGHS;
pandapower and PyPSA serve only as test oracles.

Documentation: **https://mambo10005.github.io/mambo-power/**

## What it is

- A JSON-native network model (pydantic v2): `Network` with buses, branches, generators
  (with cost curves), loads, shunts, storage and zones; physical units, stable string ids,
  all-issues validation with named error codes, JSON schema generated from the model.
- Importers that speak only the model: MATPOWER `.m` cases and the native JSON format today;
  pandapower JSON, PyPSA, PSS/E RAW and CSV bundles later.
- Network matrices over scipy.sparse: `NetworkArrays` (the single per-unit conversion site),
  Ybus, Bbus, PTDF, LODF with bridge detection.
- Solvers: DC power flow now; AC Newton-Raphson with Q-limit enforcement in the current wave;
  DC optimal power flow, N-1 contingency analysis and market clearing (nodal LMP, zonal with
  redispatch, multi-period with storage, agent-based bidding) in later waves.
- Typed, id-keyed results stamped with provenance (engine version, solver, timings), never
  stored on the network; a stateless, JSON-serialisable `jobs.run(SolveRequest)` surface
  designed to sit behind a service.

Free in both senses: an open-source stack end to end with no paid solvers or licences, and
built, tested, documented and published entirely on free infrastructure (GitHub Actions,
GitHub Pages, PyPI trusted publishing).

## Status

| Wave | Scope | State |
| --- | --- | --- |
| M1 | Installable package, `Network` model, MATPOWER import, Ybus/Bbus/PTDF/LODF, CI on Linux/macOS/Windows | merged |
| M2 | DC + AC power flow, typed results, `jobs` API, documentation site, runnable examples | in progress |
| M3+ | DC-OPF, N-1, markets, interchange formats, PyPI 0.1.0 | planned |

Not yet on PyPI. Runtime dependencies are exactly `numpy`, `scipy`, `highspy`, `pydantic`;
Python 3.11 or newer.

## Install from source

```bash
git clone https://github.com/mambo10005/mambo-power.git
cd mambo-power
uv sync                    # runtime deps only; add --all-groups for dev + docs tooling
```

Without [uv](https://docs.astral.sh/uv/): `pip install -e .` in any Python >= 3.11 environment.

## Quick start

```python
from mambo_power import pf
from mambo_power.io import matpower

net = matpower.load("fixtures/matpower/case14.m")  # validated Network, physical units
result = pf.solve_dc(net)  # typed result keyed by ids, MW
print(result.generators[0].p_mw)  # 219.0 -- slack generator balance
print(result.branches[0].p_from_mw)  # 147.84 -- flow bus-1 -> bus-2
print(result.provenance.version, result.provenance.solver)
text = result.model_dump_json()  # exact JSON round-trip
again = type(result).model_validate_json(text)
assert again == result
```

Then: [Getting started](https://mambo10005.github.io/mambo-power/getting-started/) walks
through loading, validating, solving and reading results with real output.

## Manual

- [Network model](https://mambo10005.github.io/mambo-power/manual/model/) — every entity,
  field, unit, and validation code
- [File formats](https://mambo10005.github.io/mambo-power/manual/formats/) — native JSON and
  the MATPOWER importer (column map, derived ids, warnings, limitations)
- [Numerics](https://mambo10005.github.io/mambo-power/manual/numerics/) — `NetworkArrays`,
  Ybus, Bbus, PTDF, LODF and bridges
- [Power flow](https://mambo10005.github.io/mambo-power/manual/power-flow/) — the DC
  formulation and the AC solver's contract
- [Results](https://mambo10005.github.io/mambo-power/manual/results/) — result tables,
  provenance, JSON round-trip, `to_arrays()`
- [Jobs API](https://mambo10005.github.io/mambo-power/manual/jobs/) — the stateless
  `SolveRequest` / `SolveResult` surface
- [API reference](https://mambo10005.github.io/mambo-power/api/model/),
  [Design](https://mambo10005.github.io/mambo-power/design/architecture/),
  [Changelog](https://mambo10005.github.io/mambo-power/changelog/),
  [Contributing](https://mambo10005.github.io/mambo-power/contributing/)

## Development

```bash
uv sync --all-groups
uv run ruff check . && uv run ruff format --check . && uv run mypy
uv run pytest                      # tiers: -m unit | parity | property
uv run mkdocs serve                # docs at http://127.0.0.1:8000
```

Tests are tiered (`tests/unit`, `tests/parity` against pandapower/PyPSA/MATPOWER,
`tests/property` with hypothesis). Every public symbol must carry a docstring; a unit test
enforces it. The docs build with `mkdocs build --strict` in CI and deploy to GitHub Pages on
pushes to `epic/01-foundation` and `main`.

## Licence

MIT — see [LICENSE](LICENSE). Bundled MATPOWER cases under `fixtures/matpower/` are public
IEEE test data as distributed by MATPOWER; see `fixtures/matpower/PROVENANCE.md`.
