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
- `jobs`: the stateless, JSON-serialisable job surface (ADR-004) — `SolveRequest(kind,
  network, options, job_id)`, `SolveResult(kind, job_id, status, result, error, provenance,
  warnings)`, `StructuredError(code, message, issues, details)`, the `KINDS` registry
  (`KindSpec`, `register`, `kinds`) with `pf.ac` and `pf.dc`, and `run` / `run_json`. Every
  failure is a `status="failed"` result with a stable code (`UNKNOWN_KIND`, `BAD_OPTIONS`,
  `VALIDATION` with every issue, `NO_SLACK_GENERATOR`, `BAD_REQUEST`, `INTERNAL`); a
  non-converged power flow is `status="ok"` with `converged=False`; warnings emitted by the
  solve are attached as strings. Manual page with executed examples and API reference page.
- `pf.solve_ac(net, *, options=AcOptions()) -> AcPowerFlowResult`: sparse polar
  Newton-Raphson AC power flow (MATPOWER `newtonpf` formulation, `scipy.sparse.linalg.splu`),
  tolerance 1e-8 pu on the mismatch ∞-norm, flat or warm start (`init="auto"|"flat"`),
  reactive-limit enforcement with pandapower semantics (pin PV→PQ at the limit, never
  restore, slack never limited, ≤ `max_q_rounds` rounds); non-convergence is
  `converged=False`, never an exception. `pf.ac_newton.newton` is the positional solver;
  `results.ac_result_from_arrays` builds the typed result. Parity with pandapower `runpp` at
  machine precision on case14, case_ieee30, case57, case118 (Q-limits on) and case300
  (Q-limits off and on), identical pinned sets; MATPOWER stored columns within 2e-3 pu /
  0.5 deg outside the documented exclusions; case300 cold solve measured and echoed in CI.
- Effective bus roles (`numerics.effective_roles`, `EffectiveRoles`): a PV bus without an
  in-service generator solves as PQ, a slack without one raises `NoSlackGeneratorError`, the
  last in-service generator's setpoint wins with a `SetpointConflictWarning` when setpoints
  differ. Both solvers and `BusResult.role_effective` use the effective roles.
- Island repair in importers (`model.repair_islands`, `model.repair_islands_entities`):
  buses unreachable from the slack and their elements are deactivated before validation,
  reported as typed `ImportIssue(code="ISLAND_DEACTIVATED", bus_ids, element_ids)`; the
  model itself still rejects islands (`DISCONNECTED_BUS`). `io.matpower.load_with_report` /
  `loads_with_report` return an `ImportReport` of typed issues; the `load_with_warnings`
  strings are the same entries rendered `CODE: message`.
- `examples/`: seven runnable scripts (load and validate, AC power flow, DC power flow, jobs
  API, roles and islands, network matrices, results and export), each run by
  `tests/unit/test_examples_run.py` and by the `examples` CI job, and embedded byte-for-byte
  in the documentation's Examples gallery.
- Documentation: the power-flow manual covers the AC solver as shipped (options, formulation,
  Q-limit loop diagram, warm start, parity and timing tables); the model and formats manuals
  document `ImportIssue`, `ImportReport` and `repair_islands`; getting started runs an AC
  power flow.

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
  `GENCOST_REACTIVE_IGNORED`, `ISLAND_DEACTIVATED`) — M2, with island repair.
- The typed import-issue record is `model.ImportIssue` (`ImportIssueCode`); it was briefly
  named `ImportWarning` on the wave branch, which shadowed the Python built-in. Behaviour is
  unchanged.
- `fixtures/matpower/PROVENANCE.md`, case300: the reference-solution wording now carries the
  measured residual against the AC solver (8.5e-3 pu worst, 11 of 300 buses beyond 2e-3) and
  withdraws the earlier "0.107 pu" and "pandapower cannot converge with Q-limits" figures,
  which came from a tap-side defect in the research's oracle copy, not from the data.

[Unreleased]: https://github.com/mambo10005/mambo-power/commits/epic/01-foundation
