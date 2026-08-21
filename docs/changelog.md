# Changelog

All notable changes to mambo-power are recorded here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the project follows
[Semantic Versioning](https://semver.org/). Nothing has been released yet; the first release
will be 0.1.0 on PyPI (wave M9).

## [Unreleased]

### Added — wave M2 (power flow), in progress

- `pf.solve_dc(net) -> DcPowerFlowResult`: DC power flow \(B'\theta = P - P_\text{shift}\)
  with phase-shifter injections, flows via \(B_f\), slack balance to the first in-service
  slack-bus generator (MATPOWER `rundcpf` semantics). `pf.dc.solve(arr) -> DcSolution` is the
  positional solver. Parity with pandapower `rundcpp` within 1e-9 on every fixture including
  case300.
- `results`: typed, id-keyed result models — `BusResult`, `BranchResult`, `GenResult`,
  `ResultProvenance` (engine, version, kind, solver, started_at, elapsed_s, options),
  `DcPowerFlowResult`, `AcPowerFlowResult` — with exact JSON round-trip and a positional
  `to_arrays()` view; `dc_result_from_arrays` builder.
- Fixtures: `case300.m` verbatim from MATPOWER with recorded sha256 and a licence note
  (public IEEE test data as distributed by MATPOWER); derived case14 variants under
  `fixtures/matpower/derived/` exercising effective bus roles, a slack without a generator and
  an island.
- Documentation site (this site): mkdocs-material with mkdocstrings API reference, manual
  pages for the model, file formats, numerics, power flow, results and the jobs API, mermaid
  architecture and data-model diagrams, condensed design decisions, CI job `docs`
  (`mkdocs build --strict`) and a GitHub Pages deploy workflow.
- `tests/unit/test_docstrings.py`: every public module, class, function and method in
  `mambo_power` must carry a docstring.
- Landing in the same wave: AC Newton-Raphson power flow with pandapower Q-limit semantics
  (`pf.solve_ac`, `AcOptions`); effective bus roles (`numerics.effective_roles`,
  `NoSlackGeneratorError`, `SetpointConflictWarning`); island repair in importers
  (`model.repair_islands`, `ISLAND_DEACTIVATED` warning, typed `ImportWarning`); the
  stateless `jobs` API (`SolveRequest`, `SolveResult`, `KINDS`, `run`); runnable
  `examples/` executed in CI.

### Added — wave M1 (substrate), merged

- uv-managed `src/` layout with hatchling; ruff, mypy `--strict`, pytest tiers `unit` /
  `parity` / `property`; GitHub Actions CI on Ubuntu, macOS and Windows (Python 3.12) plus
  Ubuntu 3.11 and 3.13; pandapower and PyPSA installed as development-only oracles.
- `model`: pydantic v2 `Network` with `Bus`, `Branch`, `Generator` (optional
  `PolynomialCost` / `PiecewiseCost`), `Load`, `Shunt`, `Storage`, `Zone`, `Geo`. Physical
  units (MW, MVAr, kV, MWh, degrees), branch impedances in pu on `base_mva`, stable string
  ids, `in_service` booleans, `schema_version = 1`.
- All-issues validation: `NetworkValidationError` carrying every `ValidationIssue(code,
  path, message)` with codes `NO_SLACK`, `MULTIPLE_SLACK`, `DISCONNECTED_BUS`,
  `DUPLICATE_ID`, `DANGLING_REF`, `BAD_BASE`, `BAD_RANGE`; `validate_network` as the public
  re-check; non-finite floats rejected; unknown fields rejected.
- `Network.json_schema()` with a committed snapshot test; native JSON round-trip is identity
  on every fixture (`io.native`: `load`, `loads`, `save`, `dumps`).
- `io.matpower`: `load`, `loads`, `load_with_warnings`, `loads_with_warnings` for MATPOWER
  caseformat v2 files including `gencost` (MODEL 1 and 2, `2 * ngen` rows tolerated);
  `BASE_KV <= 0` repaired to 1.0 with a warning; bus type 4 mapped to an out-of-service bus;
  BOM and CRLF tolerated; `MatpowerImportError` with codes `MISSING_BASE_MVA`,
  `MISSING_SECTION`, `UNTERMINATED_MATRIX`, `BAD_NUMBER`, `BAD_ROW`. Parity with pandapower
  `from_mpc` on case14, case30, case_ieee30, case57, case118.
- `numerics`: `NetworkArrays` (in-service positional view, the single per-unit conversion
  site), `ybus` / `yf_yt` (MATPOWER `makeYbus`), `bbus` / `bf` / `p_shift` (`makeBdc`),
  `ptdf` (sparse LU, zero slack column), `lodf` with `NaN` bridge columns, and
  graph-theoretic `bridges`. Ybus parity with pandapower within 1e-9; PTDF/LODF checked
  against dense re-derivation and brute-force outages; hypothesis property tests over random
  radial and meshed networks.
- Packaging: `uv build` wheel ships only the package and `py.typed`; sdist carries `tests/`
  and `fixtures/`; CI installs both into clean virtual environments and loads case14.
- Fixtures: `case14`, `case30`, `case_ieee30`, `case57`, `case118` with `PROVENANCE.md` and
  `SOURCES.md`.

### Changed

- MATPOWER repair warnings are now `CODE: message` strings (`BASE_KV_REPLACED`,
  `GENCOST_REACTIVE_IGNORED`, `ISLAND_DEACTIVATED`) — M2, landing with island repair.

[Unreleased]: https://github.com/mambo10005/mambo-power/commits/epic/01-foundation
