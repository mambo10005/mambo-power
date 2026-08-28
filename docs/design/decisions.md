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

## ADR-006 — `opf.dc_opf` splits array-level from `Network`-level, so the market waves reuse the LP builder

**Status:** accepted with wave M3, 2026-08-23.

**Context.** The epic commits `market` to composing `opf`, and a nodal market clearing is
mechanically a DC-OPF with offers and bids substituted for fuel costs — the same LMP
decomposition, the same flow rows. Before any OPF code existed there was a real fork: ship
`opf.dc_opf` as one `Network`-in / result-out function, simplest for the OPF wave alone, or split
it the way `pf` already splits twice (`pf.ac_newton.newton` vs `solve_ac`, `pf.dc.solve` vs its
wrapper) so a market wave could call the builder directly. Whichever shape shipped, every later
market wave would be written against it.

**Decision.** `opf.dc_opf.dc_opf(arr, cost_coeffs, options) -> OpfSolution` is the array-level
entry point: pure numerics over `NetworkArrays` plus caller-supplied cost coefficients, with no
`Network` or `Scenario` dependency. `opf.solve_dc_opf(net, options)` is a thin wrapper that derives
the coefficients from `Generator.cost` and calls it. `lmp_decomposition(duals, ptdf)` is a
standalone function — balance dual for energy, flow-limit duals times PTDF columns for congestion —
callable with hand-built inputs. A market module calls `dc_opf` and `lmp_decomposition` directly
with offer-derived coefficients; it does not build a `Network` to smuggle a `Scenario` through the
wrong door.

**Consequences.** One extra thin wrapper, in exchange for zero new LP-building code in every
market wave since. The array-level / `Network`-level split is now the established pattern for
solver-shaped modules here — but it is *earned by a real second caller*, not applied by default:
`contingency.n1` takes only a `Network` and is right to, because nothing yet needs its pieces
independently. *Rejected:* a single `Network`-shaped `dc_opf`, which would have forced the market
wave to duplicate the builder or fake a `Network`.

## ADR-007 — Elastic demand extends the one `dc_opf` builder rather than composing a second solver

**Status:** accepted with wave M4, 2026-08-24.

**Context.** A price-elastic load is algebraically a generator with a negative-signed concave
cost, so the nodal market could have been built without touching the OPF builder at all: translate
each bid load into a synthetic generator, solve, translate back. The alternative was to grow the
builder demand-side columns, hypograph rows for concave piecewise-linear bids, and the balance and
flow terms that go with them. The choice was not local — multiperiod, zonal and the agent waves all
build on the same seam, and they inherit whichever answer this one gave.

**Decision.** Elastic demand is a first-class part of the single array-level builder. `dc_opf`
gained `demand_bid_coeffs` / `demand_pwl_bids`, demand columns bounded `[0, load_p_max]` with no
sign flip, hypograph rows mirroring the generator-side epigraph construction, and the matching
solution fields. Two things are part of the decision rather than incidental to it:

1. **The builder owns the double-counting contract.** An elastic load's own `p_mw` is subtracted
   from the fixed-load right-hand side *inside* `dc_opf`. A caller cannot get this wrong because a
   caller cannot do it at all.
2. **Convexity guards are symmetric.** `NonConcaveBidError` for a bid whose marginal value is not
   non-increasing, and `NonConvexCostError` for a generator cost with negative `c2` — closing an
   asymmetry the OPF wave had left. Both raise before any solver object exists.

**Consequences.** One balance row, one PTDF flow-row builder, one dual-extraction path, one
`lmp_decomposition` reused verbatim; the market module is thin — extract, call, settle. The
price-taker reduction is exact rather than approximate, so the market wave inherited the OPF wave's
oracle-proved parity instead of needing its own. The cost was that an oracle-verified builder was
modified rather than left alone, paid down by holding 68 existing tests green through the
extension. One lesson generalises to every wave that extends this builder: **a fixture where the
answer is pinned by a bound cannot test the term that moves the answer** — the first parity fixture
here could not detect a double-counting fault until one load's bid was anchored around the
fixture's own clearing price. *Rejected:* the pseudo-generator trick — correct and cheaper to land,
but it hides the market's economics in a translation layer invisible from the LP and leaves each
later wave to reinvent it.

## ADR-008 — One shared row-family core, two callers — and the contract that did not come with it

**Status:** accepted with wave M5, 2026-08-26.

**Context.** Multiperiod clearing was the first wave to add rows that couple *across* periods — a
ramp row tying one period to the last, a state-of-charge row tying the whole horizon into one
energy budget. Either the horizon loop went inside `dc_opf`, or the row families came out into
helpers that a single-period and a multi-period caller both invoke.

**Decision.** Extraction. `_balance_row`, `_flow_limit_rows`, `_epigraph_rows`, `_hypograph_rows`
and their support were pulled out of `dc_opf` as a pure refactor touching one file and no test, and
`multiperiod_dc_opf` calls them unmodified. The evidence that this is one implementation rather
than two that agree is a sabotage, not a reading: sign-flipping the shared flow-limit helper takes
18 tests red across five files, spanning both surfaces.

**But the two *consequences* the previous ADR claimed did not survive the extraction.** The
double-counting contract and the convexity guards were duplicated, not shared: 54 identical lines
out of 68 between the single-period and multiperiod preambles. That is not a stylistic
observation — the safety property that was claimed impossible is exactly the one that failed. A
per-period load override on a bid-carrying load shipped as a complete no-op, because the elastic
column's upper bound stayed at the network's base value while the fixed-load total was corrected.
The bug lived in the duplicated copy, and it was caught by review rather than by the wave's
acceptance criteria, its sabotage sweeps, or its audit. **So the zonal wave unified the preamble
into one shared helper before adding its own row families** — not after, because a third copy pays
the unification cost three times over.

**Consequences.**

1. **The row-order contract is guarded by one assertion, and that assertion is the whole guard.**
   `multiperiod_dc_opf` checks the solver's row count against an expected total before reading any
   dual. Its necessity is measured: appending a spurious row family fails 56 tests with the
   assertion present and passes 63 with it disabled. Any wave adding a row family must update that
   sum, and will be told loudly if it does not.
2. **A sabotage applied to shared fixture data is not a sabotage.** Transposing two storage
   efficiencies in the test fixture relabels both sides of a parity comparison at once, which is
   why it looked undetectable. Transposing the *engine's* state-of-charge row with the oracle held
   fixed takes the committed test red immediately. For every parity test: apply the fault to the
   side under test, and make sure the residual that moves is one the assertion actually reads.
3. **An override must be at least as general as the field it overrides.** A per-period load
   validator rejected negative values while the `Load.p_mw` it overrides has no lower bound, so an
   identity profile failed on a fixture that ships eight negative loads and that the nodal market
   clears without complaint.
4. **A wire-format bound belongs in the model, not in a future HTTP layer.** A 34 kB request
   expands to 20 million matrix nonzeros — a decompression-bomb shape. Added after the model is
   treated as stable, such a bound becomes a breaking change.

*Rejected:* the horizon loop inside `dc_opf` (every single-period caller pays for machinery it
does not use, and the behaviour-preservation proof becomes unstateable); a separate multiperiod
solver (refused by ADR-007, and this wave supplied the evidence — the one place the two surfaces
diverged is the one place code was copied instead of called); unifying the preamble inside this
same wave (refused on sequencing: a substantive refactor landed after the matrix was discharged is
an unproven change under a green gate).

## ADR-009 — Redispatch reproduces nodal by construction; the comparison measures the repair

**Status:** accepted with wave M6, 2026-08-27.

**Context.** The zonal wave was asked for a zonal clearing, a minimum-cost redispatch, and a
nodal-versus-zonal comparison. Redispatch is priced at each unit's own curve in both directions
and elastic demand participates in both LPs — and under those answers the redispatch objective is
a free choice with two readings, which decides what the wave measures.

*True curves.* If the redispatch objective is true generation cost minus true bid value of the
**final** quantities, the redispatch LP has the nodal welfare LP's exact feasible set and an
objective equal to nodal's up to a constant. It returns the nodal optimum from *any* feasible
start, so the welfare difference is identically zero.

*An anchored linear rate.* If each unit is priced at its marginal cost or value *at the zonal
point*, the final point genuinely differs and a welfare gap exists — but that reading carries a
systematic bias. An anchored rate understates a concave bid curve's marginal value below the
anchor, so the LP over-curtails demand all the way down. A worked case gives cost 0 against nodal's
1800 while welfare is 0 against 100: the reported "gap" is partly the bias, and the cost figure
inverts.

**Decision.** The redispatch objective uses the true cost and value curves, and the chain landing
on the nodal optimum is asserted as an exact-agreement row. **The comparison therefore does not
measure how far zonal lands from nodal — that distance is zero by construction. It measures what
the zonal design costs to repair:** redispatch volume, redispatch payment, and the zonal price
vector against the nodal LMPs. That is the European day-ahead-plus-redispatch metric as actually
used, not a synthetic welfare loss. The falsifiable statement about the zonal approximation moves
to the relaxation inequality — `welfare(zonal) >= welfare(nodal)` whenever the corridor caps are at
least as loose as the network's own limits, strictly when a corridor binds.

**Consequences.**

1. **Two independent comparison quantities, not three.** With `A = cost(final) − cost(zonal)` and
   `B = value(zonal) − value(final)`, the result publishes `redispatch_payment = A + B`,
   `generation_cost_gap = −A` and `welfare_gap = 0`. So the first two sum to the
   curtailment-compensation term `B` and nothing else — `−2.6e-11 \$/h` on fixed-load case30,
   `+0.94 \$/h` with bids. Worked at [Zonal market › The three figures are two independent
   quantities plus a check](../manual/zonal.md#the-three-figures-are-two-independent-quantities-plus-a-check).
2. **`redispatch_payment` is a settlement figure and can be negative.** It is non-negative exactly
   when the zonal LP is a relaxation. With caps tighter than the network — the normal transfer-capacity
   regime — or with corridors omitted, it runs inward: `−11.05 \$/h` and `−800 \$/h` on the two
   fixtures where it was measured. See [When `redispatch_payment` goes
   negative](../manual/zonal.md#when-redispatch_payment-goes-negative).
3. **The exact-agreement row is blind to the zonal stage.** Because the redispatch LP reaches nodal
   from any start, breaking the zonal LP leaves every final-point assertion green. Only the zone
   prices, the corridor flows and the oracle parity see that stage — which is why the hand-derived
   zonal optimum and the zonal-stage parity are kept as separate acceptance rows, and must not be
   collapsed.
4. **Degenerate LPs need discriminating checks, not descriptive ones.** Rated case300 is
   primal-degenerate at the nodal optimum — seven branches at rating, five priced — so two optimal
   solves legitimately pick different active sets and their LMPs differ by about `0.32 \$/MWh`
   while the primal agrees to `1e-8`. A "structural property" (priced branches are a subset of
   at-rating branches) was substituted for the price comparison and turned out to be complementary
   slackness: satisfied by *any* optimal solution, carrying no information, and green under the
   sabotage it was meant to catch. **A check that a sabotage cannot move is not a check.**
5. **The shared core now has four callers and one new copy.** ADR-008's unification executed
   cleanly — one extraction-and-validation preamble with four callers, guard strings living only
   there. But diagonal-Hessian assembly is now a third verbatim copy. That is the next seam, on the
   same reasoning as ADR-008, one level down.
6. **A result type a reader must construct from is a design surface.** This wave's documentation
   surface had no inbound design decision, and produced exactly the defect one would have owned:
   `MarketZonalResult`'s field names rendered nowhere on this site, because the API-reference
   configuration never rendered pydantic fields for *any* result model and no earlier wave had a
   result type readers had to assemble inputs for. "Where do this type's fields reach the reader?"
   is a design question.

*Rejected:* the anchored linear rate (a genuine gap, but one carrying a proven over-curtailment
bias, so the cost figure cannot be read as approximation quality); true curves for generators with
demand frozen at the zonal quantity (a redispatch that ignores the bids its own zonal stage
honoured); a blanket price tolerance on the degenerate fixture (it would admit real regressions to
hide a known degeneracy); unifying the Hessian copy inside this wave (sequencing, as above).

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
