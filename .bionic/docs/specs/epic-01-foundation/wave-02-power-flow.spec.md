---
governing-skill: agent-skills:spec-driven-development
sdlc-step: 2
intent: build
rigor: audited
scale: wave
canonical_sdlc_version: 13
surface_type: library
language: python
has_ui: false
multi_agent: true
deploy_target: pypi
cleanup_on_finish: true
use_worktree: true
rigor-floor: audited
design: specs/epic-01-foundation/epic.spec.md
model_plan:
  orchestrator: fable-5
  implementor: sonnet
  senior-implementor: opus
  researcher: sonnet
  test-runner: sonnet
  auditor: opus
  critic: opus
---

# Wave M2 — power-flow: AC-NR + DC solvers, results with provenance, jobs API, docs substrate

Epic: .bionic/docs/specs/epic-01-foundation/epic.spec.md (R2, R9, R10, R14). Builds on M1
(merged 6c94459). Makes the package solve, settles M1's two semantic carry-overs (effective
bus roles A18, island policy A16), and stands up the documentation substrate that every
later wave extends.

## Requirements

- W1 — AC power flow: polar Newton-Raphson over `NetworkArrays`, sparse Jacobian solved
  with `scipy.sparse.linalg.splu`, tolerance 1e-8 pu on the power-mismatch ∞-norm, max 20
  iterations, flat or warm start, Q-limit enforcement with pandapower semantics (pin PV→PQ
  at the limit, never restore, slack never limited, ≤ 10 outer rounds).
  provenance: epic R2; user 2026-08-21 D2 "pandapower semantics"; record/m2-research.md §3
- W2 — DC power flow: B'θ = P with phase-shift injections, branch flows via Bf.
  provenance: epic R2; epic Design §4
- W3 — Effective bus roles: PV with no in-service generator → PQ; slack with no in-service
  generator → named error; multi-generator setpoint = last in-service generator's VG with a
  warning when setpoints on a bus differ.
  provenance: M1 plan A18 (critic 2); design item 2 ratified 2026-08-21; record/m2-research.md §4
- W4 — Island policy: the model stays strict; importers deactivate in-service islands
  (buses unreachable from the slack over in-service branches, plus attached elements) and
  return `ISLAND_DEACTIVATED` warnings; one shared `model.repair_islands` implementation.
  provenance: user 2026-08-21 D1 "Importer repairs, model stays strict"; M1 plan A16
- W5 — Typed results keyed by stable ids with provenance (engine, version, kind, solver,
  started_at, elapsed_s, options, iterations, max_mismatch_mva, converged); never stored on
  the Network; `.to_arrays()` positional view.
  provenance: epic R10; epic Design §1 (SolveResult provenance)
- W6 — Jobs API: `jobs.SolveRequest` / `jobs.SolveResult` / `jobs.run` / `jobs.KINDS`
  registry with kinds `pf.ac`, `pf.dc`; pure, JSON-serializable; failures are structured
  results, never exceptions across the boundary.
  provenance: epic R10; ADR-004
- W7 — case300 fixture (verbatim MATPOWER bytes, recorded sha256, provenance stating the
  data are public IEEE test data as distributed by MATPOWER, not BSD-licensed) and a
  modified-case14 fixture that exercises W3.
  provenance: epic Design §7 assumption 1 (300-bus timing); record/m2-research.md §5 (licence caveat)
- W8 — Documentation substrate: mkdocs-material site built `--strict` in CI; mkdocstrings
  API reference; manual pages for model, formats, numerics, power flow, jobs; mermaid
  architecture and data-model diagrams; Design section with ADR summaries; Changelog;
  GitHub Pages deploy workflow.
  provenance: epic R14 (user 2026-08-20 "a lot of documents ... class description, diagrams, examples")
- W9 — Runnable examples under `examples/` executed by CI and embedded in the manual pages.
  provenance: epic R14
- W10 — Every public class and function in `src/` carries a docstring; enforced by a test.
  provenance: epic R14 ("class description")

## Not Doing (M2)

OPF, N-1 (M3) · markets, Scenario (M4+) · PSS/E, pandapower-JSON, PyPSA formats (M8) ·
PyPI publish, semantic-release (M9) · fast-decoupled / Gauss-Seidel / continuation power
flow · distributed slack · three-phase · MATPOWER slack-limiting re-slack · PQ→PV restore ·
notebooks as the only example form · enabling GitHub Pages on the repo (user setting).

## Prior art (alternatives lens)

MATPOWER `runpf`/`newtonpf` (formulation), pandapower `runpp`/`rundcpp` (executable oracle),
PowerModels.jl result schema (results shape); docs after pandapower/PyPSA (executed
tutorials) with mkdocstrings class pages and mermaid diagrams.

## Acceptance criteria

AC-1: For case14, case_ieee30, case57, case118 (q_limits on) and case300 (q_limits off),
  `pf.solve_ac` from flat start converges and matches pandapower `runpp` (init="flat",
  tolerance_mva=1e-8, enforce_q_lims matched) within 1e-6 pu (vm) and 1e-4 deg (va) on every
  in-service bus, and branch p/q flows within 1e-4 MVA; MATPOWER stored VM/VA match within
  2e-3 pu / 0.5 deg (W1's ratified bands — amended 2026-08-21 at Step 4 from "file
  precision 5e-4 / 5e-3", which the stored solutions do not meet for pandapower or us: the
  per-fixture measured residual is pinned in the test) on every bus not in the documented
  exclusion list
  (case_ieee30 bus 3; case57 buses 14/46/47; case118 buses 17/30/38/68, each with its measured
  defect in the test); case30 is self-consistency only (stored state is flat).
  provenance: W1; record/m2-research.md §1-2
AC-2: Q-limit enforcement pins exactly the buses pandapower pins (same set, same limit side)
  on every fixture where limits bind, and a hand-built case forces both a Qmax and a Qmin pin
  and shows no restore across rounds; with q_limits off, case118 breaches the stored-VM band at
  bus 103 (the negative pair).
  provenance: W1; record/m2-research.md §3 (case118 bus 103)
AC-3: `pf.solve_dc` angles and branch flows equal pandapower `rundcpp` within 1e-9 on all
  fixtures incl. case300.
  provenance: W2
AC-4: On the modified-case14 fixture: the PV bus with its only generator out solves as PQ, as
  pandapower does (role-level agreement — a numeric match on this fixture is impossible by
  construction because pandapower's converter keeps the first setpoint and we keep the last;
  wording amended 2026-08-21 per audit); a bus with two in-service generators at differing setpoints uses the
  last one and emits a warning naming the bus; a slack with no in-service generator raises
  `NoSlackGeneratorError` from `effective_roles`.
  provenance: W3
AC-5: A case14 variant with one branch out creating an island: `load_with_warnings` returns a
  valid Network with the island's buses/elements deactivated and an `ISLAND_DEACTIVATED`
  warning listing them; the solve then matches pandapower on the main island; `load` on the
  same file succeeds silently; `Network(...)` built directly with the island still raises
  DISCONNECTED_BUS (model stays strict).
  provenance: W4
AC-6: `AcPowerFlowResult`/`DcPowerFlowResult` round-trip through JSON; provenance fields are
  populated (version equals `mambo_power.__version__`, elapsed_s > 0, iterations > 0 for AC);
  `jobs.run(SolveRequest(kind="pf.ac", ...))` twice on the same input yields equal results
  modulo provenance timing; a request with an invalid network yields `status="failed"` with a
  structured error and no exception; `jobs.KINDS` lists exactly `pf.ac`, `pf.dc` and each
  entry's models/runner exist (contract test).
  provenance: W5, W6
AC-7: case300 AC-NR (q_limits off, flat start) converges in < 1.0 s wall on the CI ubuntu
  3.12 job, measured cold (first call) and recorded in the job log and the docs; if the cold
  figure exceeds 1.0 s the row records the number and a warm-run figure, and the threshold
  decision is surfaced (at-risk row).
  provenance: W7; epic Design §7 assumption 1
AC-8: `uv run mkdocs build --strict` exits 0 locally and in CI; the site contains the IA pages
  (Home, Getting started, Manual ×5, Examples, API reference, Design, Changelog); the Design
  page renders a mermaid architecture diagram and a data-model class diagram; the API
  reference lists every public symbol of model, io, numerics, pf, results, jobs; the Pages
  deploy workflow exists and runs `mkdocs build` (publish step conditional on Pages being
  enabled).
  provenance: W8
AC-9: Every script in `examples/` runs to completion in a CI job (exit 0) against the
  installed package; each is embedded in the docs (the Examples gallery, linked from the
  manual pages — wording amended 2026-08-21 per audit) via snippets, so the docs and the
  executed code are the same bytes.
  provenance: W9
AC-11: `fixtures/matpower/case300.m`'s sha256 equals the recorded digest
  69a90280e999ef533d94656e0fbc08311f1347c962dd2753ff2005ff5e3f9ac5 and the PROVENANCE entry
  quotes MATPOWER's LICENSE exclusion of case files and makes no BSD claim — both asserted by
  a test. (Added 2026-08-21 at Step 5: the audit found W7's provenance/licence clause had no
  criterion.)
  provenance: W7; record/m2-research.md §4; record/m2-audit.md coverage finding
AC-10: A test walks `mambo_power` public modules and fails on any public class/function
  without a docstring; passes on the wave head.
  provenance: W10

## Design

Governing design: epic spec §Design; M1's wave spec §Design for model/io/numerics. M2-local
decisions (ratified 2026-08-21):

1. **Solver API (W1, W2).** `pf.solve_ac(net, *, options=AcOptions())` and
   `pf.solve_dc(net)` are the public entry points; `pf.ac_newton.newton(arr, opts)` and
   `pf.dc.solve(arr)` work on `NetworkArrays` only. `AcOptions(tol=1e-8, max_iter=20,
   q_limits=True, max_q_rounds=10, init="auto"|"flat")`; auto = warm from `Bus.vm_pu/va_deg`
   when every in-service bus carries both, else flat (1.0∠0, PV/slack at setpoint).
2. **Effective roles (W3).** `numerics.effective_roles(arr) -> EffectiveRoles` is the single
   derivation site: PV→PQ when no in-service generator; slack without generator →
   `NoSlackGeneratorError`; setpoint = last in-service generator's `v_set_pu` (MATPOWER
   rule), `warnings.warn` when setpoints differ (pandapower rule). `NetworkArrays` keeps the
   *declared* roles; solvers consume the effective ones.
3. **Q-limits (W1, D2).** pandapower semantics exactly (pin at limit, no restore, slack never
   limited, strict comparison, ≤ `max_q_rounds`).
4. **Islands (W4, D1).** `model.repair_islands(net) -> tuple[Network, list[ImportIssue]]`
   (typed issue named `ImportIssue` — renamed 2026-08-21 from the draft's `ImportWarning`,
   which shadowed the Python built-in; `io.ImportReport` carries the list and
   `load_with_report` returns it, while `load_with_warnings` keeps its legacy `list[str]`)
   owns the logic; `io.matpower.load_with_warnings` calls it and every later importer must.
   Warning code `ISLAND_DEACTIVATED` with bus and element ids. The model's DISCONNECTED_BUS
   check is unchanged.
5. **Results (W5).** pydantic models keyed by ids: `BusResult`, `BranchResult`, `GenResult`
   tables + scalars + `ResultProvenance`. Built from arrays by `results.from_arrays`;
   `.to_arrays()` returns the positional view. Results are never attached to `Network`.
6. **Jobs (W6).** `jobs.KINDS: dict[str, KindSpec(options_model, result_model, runner)]`;
   `run()` validates the request, times the runner, wraps any exception into
   `SolveResult(status="failed", error=StructuredError(code, message, issues?))`.
7a. **Fixtures and provenance (W7).** case300 is carried as verbatim MATPOWER bytes with a
   recorded sha256 and a PROVENANCE entry that quotes MATPOWER's LICENSE exclusion of case
   files (no BSD claim); derived case14 variants are synthetic and documented cell by cell.
   Agreement test: AC-11 (sha256 + licence wording). (Design citation added 2026-08-21 per
   audit coverage finding.)
7. **Verification policy (AC-1, D4).** pandapower primary at 1e-6 pu / 1e-4 deg; MATPOWER
   stored columns secondary at file precision with listed exclusions; case30
   self-consistency; case300 qlim-off + DC + timing.
8. **Docs (W8-W10, D7).** `docs/` + `mkdocs.yml`; `docs` dependency group (mkdocs-material,
   mkdocstrings[python], pymdown-extensions); IA = Home · Getting started · Manual (model,
   formats, numerics, power-flow, jobs) · Examples · API reference · Design · Changelog;
   mermaid via superfences; `examples/*.py` embedded via `pymdownx.snippets`; CI jobs
   `docs` (build --strict) and `examples` (run all); `pages.yml` deploys on push to
   epic/main when Pages is enabled.

Ownership additions: effective roles → `numerics.effective_roles` (consumers: pf.ac, pf.dc,
results) — agreement test: AC-4 vs pandapower; island repair → `model.repair_islands`
(consumers: every importer) — agreement test: AC-5; provenance → `results.ResultProvenance`
(consumers: jobs, docs) — agreement test: AC-6 version equality.

Rejected: PQ→PV restore (no oracle); model-tolerated islands; MATPOWER slack re-slack;
results on the Network; Sphinx.

Assumptions: (a) pandapower runpp with enforce_q_lims converges from flat on 14/30/57/118
and — corrected 2026-08-21 — on case300 too once the oracle copy applies MATPOWER's
tap-side swap for the 16 transformers whose hv side is T_BUS (the research's
non-convergence was a from_ppc artefact); case300 is therefore tested both qlim-off and
qlim-on; (b) case300 bytes obtainable verbatim from
MATPOWER's GitHub at sha256 69a90280…9ac5; (c) mkdocstrings renders pydantic fields
acceptably (else a small griffe extension); (d) CI ubuntu solves case300 AC < 1 s cold.
