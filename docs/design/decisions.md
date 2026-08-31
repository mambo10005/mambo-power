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

## ADR-010 — Offers are an overlay the loop supplies; the agent sees only its own node, two rounds deep

**Status:** accepted with wave M7, 2026-08-29.

**Context.** The agents wave was asked for generators that *offer* rather than reveal their cost, a
market that clears the offers, and a loop that runs until the offers settle. Three design questions
decided what the wave measures and what it can promise.

*Where the offer lives.* A deep-copied network with `Generator.cost` rewritten loses the
true-versus-offered distinction the settlement needs and allocates a network per round; an `offer`
field on `Generator` widens the schema and the JSON snapshot for one market mode. The offer is
instead a mapping the loop hands to `gen_cost_coeffs`, which already accepted a per-generator cost
override — so the clearing is the ordinary nodal DC-OPF on offered coefficients and the network is
never touched (proved by `is`-identity of every `Generator.cost` after a run in which every agent
marked up).

*What the agent sees.* An exact best response needs the agent to clear the market at candidate
offers, which means handing it the network and every rival's offer — a rival-omniscient agent whose
strategy is a second copy of the solver. The observation is instead **own-node only**: the agent's
true cost, bounds, and its own last rounds (price at its bus, cleared MW, the offer it made). At
Step 2 this was one round of history; measured, every one-round rule either cycled or settled at a
$0.02/h markup gain, because an agent that sees only `(offer, price, MW)` can tell whether it is
marginal but not whether its last move *helped*. Two rounds of own history make a two-point hill
climb computable, and that is what ships.

*What "settled" means.* Simultaneous updates with exact best response cycle period-2 in five of six
configurations; an incremental climber dithers around its optimum forever. Termination is therefore
not "no offer moved" but a repeated state followed by an amplitude measurement, reported as one of
three words — `converged`, `iteration_cap`, `cycle` — rather than a flag a reader could take as
settled when the loop merely stopped.

**Decision.** `market.solve_agents` clears offered coefficients through the unchanged nodal builder
each round; a `Strategy` is a pure function of an own-node `Observation` carrying the agent's own
last two rounds; updates are simultaneous; convergence is decided on the amplitude of the last
repeated orbit against `offer_tol`, with `offer_tol ≥ 3 × step` derived for the shipped fixed-step
climber and enforced at construction. Strategies cross `jobs` as a discriminated config union,
never as callables.

**Consequences.**

1. **Price-takers reproduce `solve_nodal` bitwise, and that is the overlay's proof, not a
   tolerance's.** Both paths hand the builder identical arrays, so `array_equal` holds on dispatch,
   LMPs, loads and branch flows on all three cost shapes — and a one-ULP perturbation of an offer
   *does* move the LP, so the agreement is exactness, not insensitivity. A tolerance would have
   hidden a real defect the wave found (rounding reported dispatch to six decimals reddens exactly
   those rows and nothing else). Bitwise is a claim about this build and this pinned solver, in one
   process; a platform disagreement is a finding to record, not a tolerance to introduce.
2. **Every comparison on solver output that is exact in arithmetic gets a stated tie rule — the wave
   found the same defect class three times, on both sides of one boundary.** A strict `<` on profit
   reversed the climb on one ULP and reported a false `converged`; `amplitude <= offer_tol` at
   `offer_tol == 2 × step` reported genuine convergence as `cycle` at non-binary-exact steps; an
   exact `cleared_mw <= 0.0` idle test would miss solver dust. Each now carries a named tolerance
   constant with its reason. The one place no constant works — the profit-tie band, where noise
   scales with the step and the real change with its square, so the bounds cross — is documented as
   such: under the `3 × step` floor a noise-decided tie only picks which of two equal-profit offers
   the climb rests on, and the verdict is the same either way.
3. **The derived floor was wrong by a step, because every Step-2 fixture's optimum sat on a grid
   point.** A half-grid optimum (true cost 33.33, step 0.01) settles in a three-step orbit, which
   `2 × step` called `cycle` after 3339 rounds. The constant is derived from the climber's worst
   orbit, not its typical one, and the validator recommends exactly that value — so the
   recommendation must be the safe one.
4. **A caller mistake reaches `jobs` as `VALIDATION`, and the up-front check has to ask the
   strategy.** The loop cannot know which cost shapes a strategy accepts without knowing its
   internals; it asks for round 0's offer before any clearing and re-raises a refusal as
   `AgentSetError`, the one class the runner catches. The bare `except ValueError` it replaced also
   swallowed `NonConvexCostError` — an engine fault labelled as a strategies mistake. And the
   "silent last-wins duplicate" clause turned out to be a property of `json.loads`, applying to
   every kind, so its fix lives in `run_json`, not in the agents runner.
5. **The clearing rows are one construction with two callers.** The per-round clearing needed the
   branch flows and settlement that `solve_nodal` assembles; the first landing copied that block
   verbatim, and the critic made it `market/_clearing.py`. The PTDF it needs is computed once per
   run and passed to `dc_opf`, which is 70 % of a 200-round case14 run; every other caller is
   byte-identical with the keyword unused.
6. **The walk found what the criteria could not.** Three shipped defects — a documented entry point
   that did not exist, the first mistake every bundled fixture invites leaking as `INTERNAL`, and an
   undispatched agent climbing to the cap — were outside every acceptance row and every one of
   1146 tests, and were found in the first ten minutes of using the feature from its manual. The
   walk is dispatched first, from the docs, forbidden the spec.

*Rejected:* a price-taker short-circuit to `solve_nodal` (makes the exactness row true by
construction and leaves the loop unexercised); round-robin updates (fixes the exact-best-response
cycle, which the own-node observation cannot compute anyway); a market-wide offer cap (a knob the
other three market modes lack); resizing the profit-tie band (no value separates noise from real
change at every step — measured, and the reasoning independently accepted by the critic).

## ADR-011 — Every format pivots through `Network`; what a format cannot carry is a report entry, never a guess

**Status:** accepted with wave M8, 2026-08-30.

**Context.** The interop wave was asked for pandapower JSON in both directions, PyPSA export, PSS/E
RAW v33 import and a CSV bundle. Three of the four are lossy against the model, in different ways:
PyPSA holds no piecewise cost, bid or zone; RAW holds no cost at all; pandapower caps costs at
degree 2 and drops a piecewise offset. And two conventions in the ecosystem invite silent damage —
pandapower's own `from_ppc` reads our BASE_KV=0 fixtures as `vn_kv = 0` and its `to_ppc` raises,
and every external solver treats a generator setpoint as a dispatch pin rather than an input.

**Decision.**

1. **`Network` is the schema of record and the only pivot.** Each format is `import → Network →
   export`; nothing converts format-to-format; no importer or exporter changes what the solvers
   compute. The oracle for each direction is the external engine running the *converted* network
   against mambo running the *original*: pandapower `rundcpp`/`runpp` against `pf.solve_dc`/`solve_ac`,
   PyPSA `optimize` against `opf.solve_dc_opf`.
2. **Best effort plus a report, never an approximation.** A field the target cannot hold is dropped
   and named — element id and field — in an `ImportReport`/`ExportReport`; a piecewise or degree > 2
   cost is *dropped*, not fitted, so the parity rows never compare two different problems. An empty
   report means lossless. Nothing in `io` prints or logs.
3. **One model widening: `Branch.kind`.** Explicit `line | transformer`, defaulted from tap and
   shift at construction, so a neutral-tap transformer — pandapower's case14 has two — survives
   the round-trip. An explicit `line` with a non-nominal tap is *promoted*, not rejected; exporters
   route on `is_transformer` (`kind` or a non-nominal tap), so a `kind` that goes stale after
   mutation cannot drop a tap.
4. **A generator with no cost is a refusal, not a zero.** `gen_cost_coeffs` raises
   `MissingCostError` naming the generators unless the caller supplies the costs; `jobs` maps it to
   `VALIDATION`. A RAW import therefore flows and refuses to dispatch, as its documentation says.
5. **Fixtures with declared provenance stand in for the oracle RAW lacks.** `case14_v33.raw` is
   transcribed field by field from `case14.m`, and a synthetic file exercises CZ/CW/CM codes, a
   neutral-tap transformer, parallel circuits and a ZIP load with hand-derived expected values.

**Consequences.**

1. **The limitations list is a registry, not prose.** `io.limitations.LIMITATIONS` references each
   module's `CODES` tuple; a test demands every code be documented in `formats.md`; the registry
   lives beside the formats, not inside `report.py`, because a leaf module importing its callers
   works only by partially-initialised-module luck.
2. **"Lossless" is measured per table, not assumed.** Strict `pp.toolbox.nets_equal` holds on our
   export re-imported for `poly_cost`/`pwl_cost` only — the other tables differ on `name`, dtype
   and default-column set, never on a value, all of which survive at 1e-12. The holding set is
   pinned so drift shows; A6 as first written was false.
3. **Cross-oracle tolerances are the oracle's, and they are recorded, not tuned.** PyPSA's HiGHS
   QP stops 1.87e-3 MW early on one case118 unit — the identical residual M3 measured, mambo's point
   cheaper under the exact polynomial — so that row's tolerance is 2e-3 MW on case118 only.
4. **What the fixtures could not see, the reviews did.** Every bundled transformer has `b = 0`, so
   a PyPSA admittance factor inverted for `b` survived the parity rows until the critic built a
   2-bus case; no fixture has a shifter, so `opf.dc_opf`'s phase-shifter flow rows are wrong
   (F1) and stay wrong until a dedicated bugfix task after this wave — every importer's limitations
   say so.
5. **The walk is the first review, not the last.** From the docs alone it found the cost-less RAW
   network dispatching at zero, the unreported `s_nom` sentinel, a mis-located RAW error, and the
   BOM and blank-line refusals — none reachable from the criteria.

*Rejected:* inference-only `kind` (a neutral-tap transformer imports as a line); rejection of
line-with-tap (a mutated network fails its own round-trip); cost approximation on export; refusing
lossy conversions by default; the IEEE-14 RAW found in the wild (licence undetected); converting
through pandapower's `from_ppc`; reading `res_bus` as an input (the spec's Not-doing — an early
landing did, and was removed).

## ADR-012 — Degenerate duals are quotiented by proven PTDF redundancy, never widened by tolerance

**Status:** accepted 2026-08-31, discovered on M9's first CI run since M7.

**Context.** `epic/01-foundation` had not run CI since M7's close (`cdb4fef`); pushing it for M9
(74 commits later) surfaced two failures — `test_market_zonal.py`'s AC-4 LMP comparison and
`test_opf_redispatch.py`'s D1 theorem — on `ubuntu-latest` at both Python versions, while macOS,
Windows and ubuntu 3.13 stayed green. A throwaway probe at `cdb4fef` itself reproduced the *same
two tests* failing, but on Windows with ubuntu green — proving the defect predates M8 and the
shifter-fix task entirely, and that which platform trips it is not fixed. ADR-009 had already
named this class for case300 ("two optimal solves legitimately pick different active sets and
their LMPs differ... while the primal agrees to 1e-8") and rejected a blanket tolerance as the
fix ("would admit real regressions to hide a known degeneracy"). The test author's own commit
(`f1782e8`, M6/S5) shows they believed case30, unlike case300, was *not* degenerate, and pinned
`CASE30_LMP_ATOL`/`DUAL_TOL` at `1e-3` against one measured run of `8.9e-6` agreement — 100×
headroom that turned out to be sized for ordinary float noise, never tested against a real vertex
swap of `~1.02`, three orders larger.

**Diagnosis.** Bus-9 carries zero net injection — no generator, load or shunt — sitting on a
radial path between two rated branches. Restricted to every column any decision variable
touches, their PTDF rows are identical to `1.2e-17`; the six-row active-constraint matrix at the
optimum has rank 4, not 6 — a genuine 2-dimensional null space, not measurement noise. HiGHS has
real, KKT-legitimate freedom in how it splits the shadow price on that shared bottleneck; the
primal (dispatch, welfare, objective) stayed rigid at `~1e-5` across every re-solve and 24
microscopic cost perturbations. A full scan found **19** such structurally-redundant branch pairs
in case30's topology — this is not a one-off coincidence, it is what a radial subtree looks like
under PTDF. The second failure (an LMP tie between two buses) traced to the identical mechanism
once corrected for an array-index/bus-id-sort mismatch in the diagnosis's own first pass — the
buses tied are connected by a plain radial PTDF identity across all 41 rows, the same shape as the
dual swap, not a second unrelated defect.

**Decision.** Neither of the two previously-tried resolutions is available: a tolerance widen
was already rejected by ADR-009 for exactly this reason, and a `priced ⊆ at_rating`
(complementary-slackness) check was tried and removed from this same module (audit F2) because
every optimal solution satisfies it trivially — vacuous by construction, a check no sabotage can
move. Instead: **compute the redundant-row equivalence classes directly from the PTDF matrix**
(rows proportional to each other, restricted to decision-variable columns — a rank/proportionality
test, not a hand-picked exception list) and assert equality **quotiented by those classes** — exact
and point-wise for every row outside a redundant group, a *weighted group-sum* (the group's shared
KKT invariant) for rows inside one. A row that is the zero vector on decision columns carries no
invariant at all — dual-feasible at any value, nothing to assert. The utility (`tests/_degeneracy.py`)
is shared by both test files, not duplicated.

**Consequences.**

1. **The check stays discriminating, proven by sabotage against the exact CI-reported failure
   shapes** — the row-swap and the bus-tie-shift that broke CI are both reproduced and correctly
   rejected by the new checks (and correctly *accepted* as legitimate by the old point-wise ones,
   which is precisely the false failure); an unrelated row, a redundant group's own aggregate
   value, and the structural tie itself moving are each independently rejected too. A check a
   sabotage cannot move is not a check (ADR-009's own principle) — this one is proven to move.
2. **The first draft pooled every redundant group into one combined residual fit and was caught
   being too permissive by its own sabotage sweep** — an unrelated defect on one group's bus
   inflated every other group's residual, masking real defects elsewhere. Fixed by fitting each
   group separately, against only its own affected buses. Worth naming: the fix for a
   too-strict check is not "loosen it" and the fix for a too-loose check is not "the first
   generalization that occurs to you" — both directions get their own sabotage proof.
3. **case14 carries one dormant redundant group too** — measured exactly zero on every solve, so
   quotienting is provably lossless there. The class is general to radial topology, not specific
   to case30; any future fixture with a zero-injection pass-through node will need the same
   treatment, and now has the tool to get it for free.
4. **CI had not run in weeks; a genuine, three-wave-old defect was sitting undetected.** M8 and
   the shifter-fix both landed with clean local sweeps and never touched this code path — the
   defect predates all of it. The lesson is not about either of those waves; it is that a local
   sweep on one machine cannot see a degeneracy whose tie-break is platform-specific, and this
   repo's CI matrix existing does no good unless CI actually runs before a release wave opens.

*Rejected:* widening `CASE30_LMP_ATOL`/`DUAL_TOL` (ADR-009's own precedent, would hide a real
regression class); a `priced ⊆ at_rating` check (already tried in this module, vacuous); a
hand-picked exception list for the specific rows/buses observed failing (works for this fixture,
teaches nothing to the next one, and case14's dormant group would have shipped unguarded); dropping
case30 for a non-degenerate replacement fixture (loses coverage of exactly the topology class real
networks contain).

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
