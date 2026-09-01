# mambo-power

A fundamental Python package for power system analysis and electricity market modelling.
It owns its network data model and implements its own solvers on numpy, scipy and HiGHS;
pandapower and PyPSA serve only as test oracles.

Documentation: **https://mambo10005.github.io/mambo-power/**

## What it is

- A JSON-native network model (pydantic v2): `Network` with buses, branches, generators
  (with cost curves), loads, shunts, storage and zones; physical units, stable string ids,
  all-issues validation with named error codes, JSON schema generated from the model.
- Importers that speak only the model: MATPOWER `.m` cases and the native JSON format, plus
  pandapower JSON, PyPSA, PSS/E RAW and CSV bundles.
- Network matrices over scipy.sparse: `NetworkArrays` (the single per-unit conversion site),
  Ybus, Bbus, PTDF, LODF with bridge detection.
- Solvers: DC power flow and AC Newton-Raphson with Q-limit enforcement; DC optimal power flow
  with duals on HiGHS; N-1 contingency screening; market clearing (nodal LMP, multiperiod with
  storage, zonal with redispatch, agent-based bidding).
- Typed, id-keyed results stamped with provenance (engine version, solver, timings), never
  stored on the network; a stateless, JSON-serialisable `jobs.run(SolveRequest)` surface
  designed to sit behind a service.
- Narrative tutorial notebooks (execution-tested in CI), an automated changelog, and PyPI
  trusted publishing.

Free in both senses: an open-source stack end to end with no paid solvers or licences, and
built, tested, documented and published entirely on free infrastructure (GitHub Actions,
GitHub Pages, PyPI trusted publishing).

## Status

| Wave | Scope | State |
| --- | --- | --- |
| M1 | Installable package, `Network` model, MATPOWER import, Ybus/Bbus/PTDF/LODF, CI matrix | merged |
| M2 | DC + AC Newton-Raphson power flow, typed results, `jobs` API, docs site, examples | merged |
| M3 | DC optimal power flow with duals on HiGHS, N-1 branch-contingency screening | merged |
| M4 | Nodal market: elastic-demand DC-OPF, LMP clearing, settlement | merged |
| M5 | Multiperiod market: 24-period horizon, ramp coupling, storage SoC, per-period settlement | merged |
| M6 | Zonal market: zonal clearing, min-cost redispatch, nodal-vs-zonal comparison | merged |
| M7 | Agent-based bidding: strategies, offered-vs-true cost overlay, fixed-point loop | merged |
| M8 | Interchange: pandapower JSON, PyPSA, PSS/E RAW, CSV bundle | merged |
| M9 | Tutorials, semantic-release changelog, PyPI 0.1.0 trusted publishing | merged |

Not yet on PyPI — this changes in the same action as the `v0.1.0` tag; see
[Getting started](https://mambo10005.github.io/mambo-power/getting-started/) for the current
install instructions, which is the live source of truth if this file is ever stale (this table
is not covered by any automated freshness check — see the wave M9 continuation record if you're
reading this after a release and it still says otherwise). Runtime dependencies are exactly
`numpy`, `scipy`, `highspy`, `pydantic`; Python 3.11 or newer.

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

## Tutorials and manual

[Tutorials](https://mambo10005.github.io/mambo-power/tutorials/) are prose-heavy, narrative
walkthroughs (a first power flow, DC-OPF + N-1, a nodal market, where to go next) — start there
if you're new. The manual is the reference:

- [Network model](https://mambo10005.github.io/mambo-power/manual/model/) — every entity,
  field, unit, and validation code
- [File formats](https://mambo10005.github.io/mambo-power/manual/formats/) — native JSON,
  MATPOWER, pandapower JSON, PyPSA, PSS/E RAW, CSV bundles
- [Numerics](https://mambo10005.github.io/mambo-power/manual/numerics/) — `NetworkArrays`,
  Ybus, Bbus, PTDF, LODF and bridges
- [Power flow](https://mambo10005.github.io/mambo-power/manual/power-flow/) — the DC
  formulation and the AC solver's contract
- [DC-OPF](https://mambo10005.github.io/mambo-power/manual/opf/) and
  [N-1 screening](https://mambo10005.github.io/mambo-power/manual/n1/)
- Market clearing: [nodal](https://mambo10005.github.io/mambo-power/manual/market/),
  [multiperiod](https://mambo10005.github.io/mambo-power/manual/multiperiod/),
  [zonal](https://mambo10005.github.io/mambo-power/manual/zonal/)
- [Agent-based bidding](https://mambo10005.github.io/mambo-power/manual/agents/) — strategies,
  offered-vs-true cost, the fixed-point loop
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
