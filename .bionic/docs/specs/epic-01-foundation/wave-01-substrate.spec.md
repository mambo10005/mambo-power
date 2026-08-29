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

# Wave M1 — substrate: installable package, data model, MATPOWER import, network matrices

Epic: .bionic/docs/specs/epic-01-foundation/epic.spec.md (R1, R9, R11-partial, R12).
Turns the empty repo into a CI-proven, pip-installable package carrying the `Network`
model, the native and MATPOWER importers, and the admittance/sensitivity matrices every
later solver consumes. No solver ships in M1.

## Requirements

- W1 — uv-managed project (`src/` layout, hatchling), ruff + mypy strict, pytest tiers
  `unit` / `parity` / `property`, GitHub Actions CI on Ubuntu/macOS/Windows (3.12) plus
  Ubuntu 3.11 and 3.13; pandapower and PyPSA installed as dev-only oracles.
  provenance: epic spec R12, R9; user 2026-08-20 "ok" (M1 scope, tactical defaults)
- W2 — `mambo_power.model.Network`: pydantic v2 model with entities bus, branch,
  generator (with optional cost curve), load, shunt, storage, zone; physical units in the
  model (MW, MVAr, kV, MWh), impedances pu on system base; named validation errors.
  provenance: epic spec R1; record/m1-w1-extract.md §1 (W1 Case schema v1 field set)
- W3 — JSON schema emitted from the model and snapshot-tested; native JSON round-trip is
  identity.
  provenance: epic spec R1 "the native file format IS the model"
- W4 — `mambo_power.io.matpower.load(path) -> Network` and `loads(text) -> Network` for
  MATPOWER .m case files including `mpc.gencost`, proven on the five migrated fixtures
  against pandapower's `from_ppc` converter pipeline fed by an independent reader.
  (Amended 2026-08-20 at Step 6 from `load(path_or_text)`: the path/text split follows the
  `json` precedent — sniffing is a footgun; see plan A15. Oracle wording amended per A10.)
  provenance: epic spec R11 (MATPOWER import); record/m1-w1-extract.md §2 (column map)
- W5 — `mambo_power.numerics`: `NetworkArrays` view (index maps, pu conversion) and
  Ybus, Bbus, PTDF, LODF over scipy.sparse, proven against dense re-derivation and
  pandapower's Ybus.
  provenance: epic spec Design §2 (numerics module), §4 (pf.dc via PTDF)
- W6 — `uv build` produces a wheel that installs into a clean venv where
  `import mambo_power` and a fixture load succeed.
  provenance: epic spec R13 (installable before 0.1), epic plan "every wave ships a pip-installable state"

## Not Doing (M1)

Power-flow / OPF solvers (M2/M3) · `Scenario`, bids, offers (M4) · pandapower JSON, PyPSA,
PSS/E RAW, CSV formats (M8) · `jobs` API (M2) · docs site, PyPI publish, semantic-release
(M9) · performance work · Python < 3.11 · transformer magnetising branches, three-winding
transformers, DC lines, asymmetric/three-phase data.

## Prior art (alternatives lens)

pandapower element tables (units in MW/MVAr/kV, `in_service` booleans) and MATPOWER
column semantics (fixtures) shape the model; PyPSA's component naming where it agrees.
JSON-schema-from-model is the differentiator (PyPSA has none; pandapower's is hand-kept).

## Acceptance criteria

AC-1: `uv sync`, `uv run ruff check .`, `uv run mypy`, `uv run pytest` all exit 0 locally
  and in every CI matrix job (5 jobs).
  provenance: W1; user 2026-08-20 "ok" (tactical defaults)
AC-2: A planted failing unit test turns CI red (run observed), then is reverted and CI is
  green again — the instrument is proven to catch.
  provenance: canonical-sdlc build intent rule ("prove it CATCHES planted failures"); epic plan M1
AC-3: `import pandapower, pypsa` succeeds inside the test session on all three OSes.
  provenance: epic spec Design §7 assumption 3; W1
AC-4: Each invariant — exactly one slack (NO_SLACK / MULTIPLE_SLACK), connectivity over
  in-service branches (DISCONNECTED_BUS), unique ids per collection (DUPLICATE_ID),
  references resolve (DANGLING_REF), positive bases (BAD_BASE), ordered limits and SoC in
  [0,1] (BAD_RANGE) — raises its named error on a minimal counter-example and is silent
  on every fixture; the exported JSON schema matches the committed snapshot.
  provenance: W2, W3; record/m1-w1-extract.md §1.4 (W1 error codes) + "Surprises" (socInitial unvalidated)
AC-5: For every fixture, `Network.model_validate_json(net.model_dump_json()) == net`.
  provenance: W3
AC-6: For each of the five fixtures, bus/branch/generator/load/shunt counts, per-element
  values (r, x, b, tap, shift, rating, p/q limits, setpoints, gencost coefficients) and
  bus types equal pandapower `from_mpc` on the same file within 1e-9 after unit alignment;
  MATPOWER bus type 4 maps to an out-of-service bus, not an error.
  provenance: W4; record/m1-w1-extract.md §2 (gencost never read in W1 — M1 closes that gap)
AC-7: For every fixture, sparse Ybus equals a dense re-derivation (1e-12) and pandapower's
  Ybus (1e-9); Bbus equals the imaginary DC approximation; PTDF rows satisfy
  PTDF · (unit injection at slack) = 0 and sum-of-flows-around-cut identities; LODF
  equals the brute-force single-outage PTDF difference for every branch whose removal
  keeps the network connected, and is marked undefined for bridges.
  provenance: W5; epic spec Design §4 (dense re-derivation oracle)
AC-8: `uv build` wheel installs in a fresh venv (no dev deps) and
  `python -c "import mambo_power; from mambo_power.io import matpower; matpower.load('fixtures/matpower/case14.m')"` exits 0.
  provenance: W6

## Design

Governing design: epic spec §Design (module boundaries, ownership table, verification
table, stack). M1-local decisions below; each cites the requirement it serves.

1. **Units convention (W2, W5).** The model stores physical units — MW, MVAr, kV, MWh,
   degrees — with branch r/x/b in pu on `base_mva`, exactly as MATPOWER and pandapower do
   and as W1 did. Per-unit conversion happens once, in `numerics.NetworkArrays`, never in
   the model. Rationale: files stay human-readable and interop stays lossless.
2. **Field naming (W2).** snake_case with unit suffix: `p_mw`, `q_mvar`, `base_kv`,
   `v_set_pu`, `tap_ratio`, `shift_deg`, `rating_mva`, `energy_mwh`, `soc_initial`;
   `in_service: bool` replaces W1's `status: 0|1`; `Bus.type: Literal["slack","pv","pq"]`.
   Buses carry optional `vm_pu` / `va_deg` (initial or last-solved state, imported from
   VM/VA) and optional `v_min_pu` / `v_max_pu`, `area`, `zone`, `geo`.
3. **Generator cost in the model now (W4).** `Generator.cost: PolynomialCost | PiecewiseCost
   | None`, parsed from `mpc.gencost` (MODEL 2 polynomial, MODEL 1 PWL), with startup and
   shutdown costs. Model-present, solver-ignored until M3 — avoids a schema bump one wave
   later. W1 never read gencost; this closes that gap.
4. **Isolated buses (W4).** MATPOWER type 4 → `in_service=False` bus; connectivity is
   checked over in-service buses and branches from the slack. W1 hard-errored; pandapower
   tolerates. Tolerating keeps real-world RAW/MATPOWER files loadable.
5. **Named errors (W2).** One `ValidationIssue(code, path, message)` type; `Network`
   validation raises `NetworkValidationError` carrying a list of issues with codes
   NO_SLACK, MULTIPLE_SLACK, DISCONNECTED_BUS, DUPLICATE_ID, DANGLING_REF, BAD_BASE,
   BAD_RANGE. Importer errors carry MISSING_BASE_MVA, MISSING_SECTION, UNTERMINATED_MATRIX,
   BAD_NUMBER, BAD_ROW (ported from W1).
6. **IDs (W2, W4).** Stable strings. Importer derives `bus-<n>` from BUS_I,
   `gen-<k>`, `branch-<k>`, `load-<bus>`, `shunt-<bus>` (W1 convention); loads and shunts
   are emitted only for non-zero rows.
7. **Ownership (W5).** `numerics` is the only module that holds positional indices;
   `NetworkArrays` is the single pu-conversion site — the agreement test is AC-7's
   Ybus-vs-pandapower comparison, which fails if conversion drifts.

Rejected: pu-in-model (lossy interop, unreadable files); `status: int` (pydantic bool is
the idiomatic JSON boolean); erroring on bus type 4 (rejects loadable real files);
deferring gencost to M3 (schema bump).

Assumptions: (a) pandapower `from_mpc` is a faithful oracle for the column map — where
it and MATPOWER's manual disagree, the manual wins and the divergence is logged;
(b) pandapower exposes a Ybus via `pandapower.pypower.makeYbus` on its internal ppc —
if that path breaks, AC-7's oracle falls back to dense re-derivation only and says so;
(c) hypothesis-generated radial/meshed networks are enough to exercise connectivity and
LODF-bridge logic beyond the five fixtures.
