# Design decisions

The project's architecture decision records (ADRs) and wave-level design decisions live in
the maintainers' SDLC record, which is not part of the repository. This page restates each
one — context, decision, consequences — so the reasoning travels with the code.

## ADR-001 — The foundation is a Python package, not a browser engine

**Status:** accepted 2026-08-20. Supersedes the gridlab repository's ADR-001 (dual-lane
solver port), ADR-002 (per-lane engines + parity) and ADR-004 (static baseline).

**Context.** The predecessor project, *gridlab*, was a static web app whose core loop ran in
the browser (TypeScript Newton-Raphson + HiGHS-WASM) with a Python service as an optional
second lane. The programme was re-scoped: build a fundamental power system and electricity
market *package* first, then build the commercial product on top of it. A package lives where
its users and numerical ecosystem live — for power systems that is Python: scipy sparse,
HiGHS via highspy, pandapower and PyPSA as oracles, a practitioner audience that reads
notebooks.

**Decision.** `mambo-power` is a Python ≥ 3.11 package (PyPI `mambo-power`, import
`mambo_power`). There is one engine. The browser-WASM lane, the per-lane parity suite and
the static-site-as-core-loop property are retired; the future commercial layer calls the
package server-side through its job API (ADR-004).

**Consequences.** "Free in both senses" narrows to "open stack, no billed service in
build/test/docs/release" — zero *run* cost becomes the commercial layer's concern. gridlab's
TypeScript work is archived under tag `archive/ts-w1`; its knowledge (schema field set,
MATPOWER importer semantics, AC-NR and Q-limit formulation, fixtures with provenance, the
SolveRequest/SolveResult shape) carried into M1 and M2. Rejected: a TypeScript extraction
(wrong ecosystem, LP limited to highs-js); Rust + WASM + PyO3 (heaviest toolchain, no
browser lane left to justify it).

## ADR-002 — Own data model and own solvers; pandapower and PyPSA are test oracles only

**Status:** accepted 2026-08-20.

**Context.** pandapower (BSD) and PyPSA (MIT) already implement power flow and LP-based OPF
and are licence-compatible with a commercial layer. Wrapping them is the fastest path to a
working package — but the goal is a *fundamental* package whose formulations the commercial
product sells and whose release cadence the project controls.

**Decision.** `mambo_power.model` defines its own `Network` (and later `Scenario`), pydantic
v2 and JSON-native. `pf`, `opf`, `contingency` and `market` implement their own formulations
on numpy, scipy.sparse and highspy. Runtime dependencies are exactly numpy, scipy, highspy,
pydantic. pandapower and PyPSA are development dependencies used by the parity test tier and
never imported by package code.

**Consequences.** Every solver carries a published oracle or an analytic invariant; the
parity tier is the contract that keeps "own solvers" honest. More work up front — each wave
writes a formulation rather than a call — and every formulation bug is ours to find, hence the
property tier (hypothesis) and the audited rigor floor on every wave. Interop with both
libraries remains a requirement, as file formats (wave M8), not as engines. Rejected: own
model with delegated solvers; a thin layer over PyPSA (a plugin, not a foundation).

## ADR-003 — Two repositories, library first

**Status:** accepted 2026-08-20.

**Context.** The open foundation and the commercial web product have different licences,
publics and lifecycles. One repository is simpler today and forces a history/licence split
on the day the commercial layer goes private. Porting inside gridlab while keeping its
dual-lane design would preserve the most existing work but keep a browser solver lane with
nothing to serve.

**Decision.** `mambo10005/mambo-power` is public, MIT, the foundation. `mambo10005/gridlab`
is the future commercial UI/SaaS, paused until mambo-power 0.1.0 is on PyPI. The commercial
layer depends on mambo-power as a *published package*, never as a path dependency; anything it
needs from the foundation is proposed through this repository's development process.

**Consequences.** A clean licence boundary — gridlab can go private without surgery. Two CI
pipelines and two release cadences; the foundation's semantic version is the contract between
them. Free-tier hosting questions for the SaaS (API host, Postgres, static frontend) are
deferred to that repository's own epic.

## ADR-004 — One stateless, JSON-serialisable job surface is the contract the SaaS consumes

**Status:** accepted 2026-08-20.

**Context.** The commercial layer will call the foundation server-side: behind an HTTP
handler, from a worker queue, possibly across processes. A notebook-first API — mutable
network objects with results stored on them, global solver state — does not survive that
boundary.

**Decision.** `mambo_power.jobs` exposes `run(SolveRequest) -> SolveResult` for every
analysis kind (`pf.ac`, `pf.dc`, then `opf.dc`, `n1`, `market.nodal`, `market.zonal`,
`market.multiperiod`, `market.agents`). Requests and results are pydantic models, fully
JSON-serialisable; `run` is a pure function of its input; results stamp engine version,
solver, timings and convergence diagnostics. The kinds registry is the SaaS's capability
list. Module-level functions in `pf`, `opf`, `market` remain for notebook use and are what
`jobs` calls.

**Consequences.** The same call works in a notebook, a CLI, a worker and a FastAPI handler —
the SaaS adds transport and persistence, never semantics. Long-running kinds (agents,
multi-period) will take a `cancel`/`progress` hook in the request rather than holding state.
The shape is the port of gridlab's SolveRequest/SolveResult contract, carried over by design.

## ADR-005 — Physical units in the model; per-unit only inside `numerics`; validation reports every issue

**Status:** accepted with wave M1, 2026-08-20.

**Context.** Every later wave reads the same `Network`. Two choices cannot be changed later
without a schema bump and a rewrite of every consumer: what units the model stores, and how
validation failures are reported.

**Decision.** (1) *Units:* `Network` stores physical quantities — MW, MVAr, kV, MWh, degrees —
with branch r/x/b in per-unit on `base_mva`, exactly as MATPOWER and pandapower files do.
Per-unit conversion happens in exactly one place, `numerics.NetworkArrays.from_network`,
which is also the only site holding positional indices. The agreement test is pandapower
`makeYbus` parity on the IEEE fixtures. (2) *Validation:* construction and
`model_validate_json` run every cross-entity invariant in one pass and raise
`NetworkValidationError` carrying the full list of `ValidationIssue(code, path, message)`.
The error subclasses `Exception`, not `ValueError`, because pydantic wraps a `ValueError`
raised inside a validator and would drop the issue list. Range and base bounds live in that
validator rather than in `Field` constraints so one pass reports everything; the JSON schema
therefore carries bounds as description text. Non-finite floats are rejected at the model
boundary. (3) *Re-check:* models are mutable and mutation never re-validates;
`validate_network(net) -> list[ValidationIssue]` is the public re-check.

**Consequences.** Files stay human-readable and lossless against MATPOWER, pandapower and
PSS/E. A service can return every problem in one response. Callers must
`except NetworkValidationError`, not `except ValueError`. Machine-readable bounds in the JSON
schema remain an additive option. Rejected: pu-in-model (lossy interop, unreadable files);
`Field(gt=0)` constraints (first-error-only reporting); a `ValueError` subclass (issue list
lost).

## Wave M2 semantic decisions

Two behaviours M1 deferred were settled for M2 (ratified 2026-08-21).

### D1 — Islands: the importer repairs, the model stays strict

A bus that cannot reach the slack over in-service branches is an *island*. The model keeps
rejecting it (`DISCONNECTED_BUS`), because a silently tolerated island would give every
solver an undefined reference angle. Importers instead **deactivate** islands — the
unreachable buses plus every generator, load, shunt and storage attached to them — and report
each repair as an `ISLAND_DEACTIVATED` warning listing the ids. One shared implementation,
`model.repair_islands(net) -> (Network, warnings)`, owns the logic and every importer calls
it; `io.matpower.load_with_warnings` is the first. `Network(...)` built directly with an
island still raises. *Rejected:* model-tolerated islands (pandapower NaN-fills results for
them; we would rather name the repair).

### D2 — Q-limit enforcement follows pandapower semantics exactly

During AC Newton-Raphson with `q_limits=True`, after each converged inner solve every PV bus
whose reactive output breaches a generator limit is **pinned** to PQ at that limit
(`q_limited = "min" | "max"`). Pins accumulate across rounds and are **never restored**
(no PQ→PV switch back); the slack bus is never limited; comparison is strict; at most
`max_q_rounds` (default 10) outer rounds run. *Rejected:* PQ→PV restore (gridlab's TypeScript
engine did it, neither oracle does — parity runs would compare different fixed points);
MATPOWER's re-slacking when the slack generator hits a limit.

### Effective bus roles (M1 carry-over A18)

The declared `Bus.type` is not always the role a solver can use. `numerics.effective_roles`
is the single derivation site: a PV bus with no in-service generator is solved as PQ; a
slack bus with no in-service generator raises `NoSlackGeneratorError`; when several
in-service generators sit on one bus the voltage setpoint is the **last** one's `v_set_pu`
(MATPOWER's rule) and a warning is emitted when the setpoints differ (pandapower errors
here; we warn). `NetworkArrays` keeps the declared roles; solvers consume the effective ones
and results report `role_effective`.

### Verification policy

pandapower is the primary oracle (1e-6 pu on voltage magnitude, 1e-4 degrees on angle,
1e-4 MVA on branch flows); MATPOWER's stored solution columns are secondary at file precision
(5e-4 pu / 5e-3 degrees) with a documented exclusion list per case; `case30` is
self-consistency only (its stored state is flat); `case300` runs with Q-limits off plus DC
and a cold-start timing budget of 1.0 s.
