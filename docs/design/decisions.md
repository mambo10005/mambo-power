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

## ADR-013 — Tutorial fixtures ship in the sdist, not the wheel; narrative tutorials require a clone

**Status:** superseded by ADR-014 (2026-09-13). Originally accepted 2026-08-31, wave M9, Step-6
critic finding C3; the text below is kept as history.

**Context.** M9 built four narrative tutorial notebooks (docs/tutorials/) that load bundled
MATPOWER/PSS-E-RAW fixtures by relative path (`../../fixtures/matpower/case14.m`,
`../../fixtures/case14_v33.raw`), the same fixtures `examples/*.py` and the test suite already
use. `[tool.hatch.build.targets.wheel]` scopes the wheel to `packages = ["src/mambo_power"]`
only — `fixtures/` ships in the sdist, never the wheel. So a reader who does exactly what M9's own
headline deliverable (W7, PyPI trusted publishing) tells them to do — `pip install mambo-power` —
gets a package with no `fixtures/` directory at all, and three of the four tutorials' first
executable cell raises `FileNotFoundError`. The Step-6 independent critic found this by reading
`pyproject.toml`'s wheel scope against the tutorials' own load calls; it was not caught by the
walk, the auditor, or the 6-axis reviewer, none of whom traced a `pip install`-only install path
end to end against what the tutorials actually load.

**Decision.** Ship the tutorials as-is, requiring a repository clone, and say so explicitly in
every tutorial that loads a fixture (tutorial 1 already had the caveat; 2 and 4 were missing it
and now carry it too) rather than change what ships in the wheel. The tutorials are documentation
that teaches the package by exercising real MATPOWER/PSS-E data — the same discipline
`examples/*.py` already established (docs and the tested artifact are the same bytes) — and that
discipline is worth more than making the wheel self-sufficient for a narrative walkthrough nobody
runs from a `pip install`-only environment in practice (a reader following a tutorial is, by
construction, engaging with the project past the point of a bare install).

**Consequences.**

1. **A permanent constraint, not a pre-release one.** Unlike getting-started.md's PyPI-install
   text (AC-3's guard, sequenced to flip only at the `v0.1.0` tag), this caveat does not go away
   once the package ships — `pip install mambo-power` will never carry `fixtures/`, at any
   version, under this decision. Each of the three affected tutorials now states this as a
   standing fact, not a pre-release note.
2. **The gap is not covered by any guard.** AC-3's PyPI-sequencing script checks
   getting-started.md's install claim, not whether the tutorials' own prerequisites are stated
   correctly. A future tutorial that loads a fixture without the caveat would ship silently wrong
   again; this ADR is the record for the next slice that adds one to check against, since no test
   enforces it.
3. **`examples/*.py` carries the identical constraint**, unremarked before now — every bundled
   example already requires a clone for the same reason (`fixtures/matpower/case14.m`,
   repo-root-relative). M9 did not introduce the underlying constraint, only a second convention
   for stating it (notebook-dir-relative paths, vs. the examples' repo-root-relative ones — two
   path conventions now coexist, documented in the tutorial cells but not unified).

*Rejected:* bundling `fixtures/` into the wheel (`[tool.hatch.build.targets.wheel] packages`
widened, or `include`) — grows every install's footprint for data only the tutorials and examples
need, not the library itself, and reverses on a later wave if this repo ever ships a slimmer
"library-only" install tier; rewriting the tutorials to synthesize small in-code networks instead
of loading real MATPOWER cases — loses exactly what D1 (M9's own scope ruling) chose narrative
tutorials for: real IEEE test cases, the ones the power-systems research community actually uses,
not synthetic toy grids; a `pip`-installable "extras" data package — real option, but a bigger
packaging decision than this wave's docs/CI/CD-only scope, deferred rather than decided here.

## ADR-014 — Bundled cases ship in the wheel as package data; tutorials and examples need only pip install

**Status:** accepted 2026-09-13. Supersedes ADR-013.

**Context.** ADR-013 kept `fixtures/` in the sdist only, so every narrative tutorial under
`docs/tutorials/` and every `examples/*.py` script required a repository clone: a reader who ran
`pip install mambo-power` and then the first cell of a tutorial, or `python examples/<name>.py`,
got `FileNotFoundError`. ADR-013 recorded that as a permanent constraint and admitted no guard
enforced even the caveat. With the package live on PyPI, the install path the README and
getting-started page advertise is exactly the one that could not run the project's own teaching
material.

**Decision.** Move the bundled cases into the package and expose them through a public module.

1. **The data moves to `src/mambo_power/cases/data/`.** The six MATPOWER cases, the four derived
   case14 variants and `case14_v33.raw` — about 200 KB of text, the same redistribution the sdist
   already made — ship in the wheel as package data. Their provenance travels with them:
   `PROVENANCE.md`, `SOURCES.md`, `derived/PROVENANCE.md` and `PROVENANCE-raw.md`.
2. **`mambo_power.cases` is the access surface**, stdlib-only (no runtime dependency added):
   `available()` lists the bundled case names, `path()` returns the file on disk and `load()`
   returns a `Network`. Tutorials and examples load through it instead of a relative path, so
   `pip install mambo-power` is enough to run every tutorial and every `examples/*.py`.
3. **Test-only data stays out of the wheel.** `synthetic_quirks_v33.raw` exists to exercise the
   RAW importer's edge cases, teaches a reader nothing, and moves to `tests/fixtures/`.
4. **Exactly one copy of each file exists.** The test suite reads the packaged copy, so the bytes a
   parity test validates are the bytes a user loads; there is no `fixtures/` mirror to drift.
5. **Guards, not caveats.** CI's install-smoke job asserts the built wheel carries
   `cases/data/case14.m` and `PROVENANCE.md`, and solves case14 from a working directory outside
   the checkout, so a wheel that silently drops the data fails before release. A unit test fails on
   any `fixtures/` string under `examples/` or `docs/tutorials/`, so a repo-relative load path
   cannot creep back in.

**Consequences.**

1. **Every install pays the wheel-size cost.** About 200 KB of case text ships to users who only
   want the solvers. Accepted: it is small next to the numpy/scipy/highspy install it rides on, and
   a self-sufficient install is worth more than the bytes.
2. **ADR-013's packaging alternatives are settled.** The hypothetical "library-only" install tier
   ADR-013 cited against bundling is rejected — nothing asks for it, and designing around it cost
   every reader a clone. The separate "extras" data package ADR-013 deferred stays deferred
   indefinitely in favour of the simplest packaging: one wheel, one copy of the data.
3. **ADR-013's constraint and its two path conventions are gone.** The tutorial caveats requiring a
   clone no longer apply, and notebook-dir-relative versus repo-root-relative paths collapse into
   one `mambo_power.cases` call.
4. **Examples run with a temporary working directory.** Because nothing resolves against the
   repository root any more, the example tests execute each script from a scratch directory, which
   is what proves a script needs no checkout.

*Rejected:* keeping ADR-013 and strengthening its caveats — documents the failure instead of
removing it, and the PyPI install stays unable to run the teaching material; a separate
`mambo-power-cases` data distribution or `[cases]` extra — a second package to version, publish
and keep in step for 200 KB of text; downloading cases on first use — adds a network dependency
and a failure mode to a tutorial's first cell, and the files are small enough to ship; keeping a
`fixtures/` copy for the tests alongside the packaged one — two copies drift, and the test suite
would stop validating what users actually load.

## ADR-015 — Generator outages join the N-1 screen; the slack absorbs the loss and is never outaged

**Status:** accepted 2026-10-12.

**Context.** M3 shipped `contingency.n1` for branch outages only and recorded generator-outage
contingencies as a carry-over (wave spec Not Doing; `docs/manual/n1.md` §Scope). The pipeline's
shape — a linear fast screen over the base-case DC dispatch, then a real DC re-solve for every
flagged outage, with a brute-force sweep proving the screen misses nothing — does not depend on
the outaged element being a branch. What it needs for a generator is a rule for where the lost
MW goes, because a generator outage, unlike a branch outage, changes the injection vector.

**Decision.** Generator outages are screened and confirmed by the same pipeline, with the lost
dispatch taken up by the slack bus.

1. **The slack picks up the loss.** This is not a new modelling choice: `pf.dc.solve` already
   closes every DC power flow at the slack bus, and the confirming re-solve of a generator taken
   out of service is just that solve. The screen estimates the same thing linearly — the
   post-outage flow on branch `l` is `|base_flow[l] − PTDF[l, bus(g)] · P_g|`, where `P_g` is the
   generator's base-case *solved* dispatch and the PTDF's slack column is zero, so the slack's
   pickup contributes nothing. DC power flow is linear, so the estimate and the re-solve are the
   same system evaluated two ways; the re-solve is kept as the ground truth and as the value
   reported, exactly as for branches.
2. **Generators at the slack bus are skipped, and named.** The slack bus absorbs every other
   outage's loss; its own generator's outage moves no flow under this rule, and a confirming
   re-solve could have nothing left to absorb the balance. `N1Result.slack_generator_ids` lists
   them, the generator counterpart of `bridge_branch_ids`: a skipped element is reported, never
   silently dropped.
3. **On by default, switchable.** `N1Options.generator_outages` (default `True`) adds
   `N1Result.generator_outages`, one `N1GeneratorOutageResult` per flagged generator with its
   `lost_p_mw` and the same `N1BranchFlag` rows branch outages carry. Both new result fields
   default to empty, so an `N1Result` serialised before this ADR still validates.
4. **The agreement guarantee extends.** `tests/unit/test_contingency_n1_generators.py` re-solves
   every non-slack generator outage of the five rated OPF fixtures with no screen at all and
   requires the confirmed-violating set to match the pipeline's — the generator edition of M3's
   brute-force test.
5. **A rated case ships with it.** No upstream case bundled here has a binding `RATE_A`
   (case30's real ratings never bind), so until now every reader derived ratings by hand before
   N-1 could show anything. `derived/case14_rated.m` — case14 with each branch rated at 20 %
   above its own base-case DC flow, floored at 30 MVA — follows ADR-014's derived-variant
   pattern: the rule and all twenty values are in `derived/PROVENANCE.md`, a script regenerates
   the file, and a test re-derives it from case14. The tutorials and `examples/08_opf_and_n1.py`
   load it; the test suite keeps its own test-time derivation with a 1 MVA floor, which gives
   the agreement tests far more pairs to check.

**Consequences.**

1. **"N-1" now means branches and generators.** A rating violation caused by losing a unit is
   found by the same call as one caused by losing a line. The cost is one PTDF column product per
   generator in the screen and one DC re-solve per flagged generator — case300 (69 generators)
   adds about 56 re-solves to the 293 branch re-solves at the test ratings.
2. **Distributed slack is the open question, not a limitation hidden in the numbers.** Sending
   the whole loss to one slack generator is what the DC solver does today for every analysis;
   a participation-factor or AGC-style pickup would change the base solver, not this module, and
   is recorded here as the next step for anyone who needs it.
3. **Still no N-2 and no redispatch.** `contingency.n1` reports violations, it does not fix them;
   preventive or corrective redispatch stays a carry-over.

*Rejected:* a separate `contingency.n1_generators` entry point — two results for one question,
and the `jobs` kind would have to grow a second kind for the SaaS to call; using the declared
`Generator.p_mw` as the lost dispatch — differs from the solved value only at the slack bus,
which is skipped anyway, but the solved value is what the re-solve removes and so is the honest
estimate; outaging slack-bus generators with the balance moved elsewhere — a different slack
rule for one analysis, breaking the "every DC solve closes at the slack" invariant every other
module relies on.

## ADR-016 — Security-constrained OPF by constraint generation, with the N-1 screen as the oracle

**Status:** accepted 2026-10-12.

**Context.** `contingency.n1` reports post-contingency overloads and `opf.solve_dc_opf` finds the
cheapest dispatch, but nothing connected them: the manual's own scope note called preventive
redispatch on a violation a carry-over. A dispatch that is cheapest and N-1-insecure is not one an
operator can use. ADR-006 split `dc_opf`'s row families from its solver object so a later caller
could add rows to the same LP; ADR-015 made the screen cover generator outages too. Both halves
were in place.

**Decision.** `opf.scopf` is the preventive security-constrained DC-OPF, built on the two existing
pieces rather than as a third solver.

1. **A contingency is a row of the existing shape.** Under the DC model the post-contingency flow
   on a monitored branch is linear in the dispatch — `flow_l + LODF[l,k]·flow_k` for a branch
   outage, `flow_l − PTDF[l,bus(g)]·p_g` for a generator outage with the slack making up the loss —
   so each (outage, branch) pair is one more flow-limit row. `dc_opf` gains an optional
   `security: SecurityRows` block, appended after the base-case rows and priced into
   `OpfDuals.security`; `lmp_decomposition` folds those duals into the congestion term. With
   `security=None` every existing caller's LP is byte-for-byte unchanged.
2. **Rows are generated, not enumerated.** All pairs at once is `n_outages × n_branch` dense rows
   (~170 000 on case300), almost all slack. `scopf_dc` instead solves, screens the dispatch with
   `contingency.n1.screen_n1_dispatch` — the N-1 screen over a caller-supplied dispatch, split out
   of `screen_n1` for this — adds a row for every newly flagged pair, and repeats until nothing new
   is flagged. Linearity makes an added row exact for the next solve, so each round terminates or
   adds a new row from a finite set; `max_iterations` is a guard, and reaching it is reported as
   `IterationLimit`, never as a secure result.
3. **The result carries its own confirmation.** `solve_scopf` writes the dispatch into a copy of
   the network and runs the real `contingency.n1` — every flagged outage DC-re-solved — reporting
   that `N1Result` and its verdict as `secure`. A reader does not have to trust the screen the loop
   used; the proof is in the result.
4. **Infeasible is an answer.** When no dispatch survives every contingency at the given ratings —
   typically a load whose last remaining path is rated below it — the LP is infeasible and the
   result says so, with the plain OPF's cost still reported. Through `jobs` it is the structured
   `INFEASIBLE_LP` failure `opf.dc` already uses.
5. **It is a `jobs` kind.** `opf.scopf`, `ScopfOptions` → `ScopfDcResult`, the ninth kind.

**Consequences.**

1. **Preventive only.** One dispatch holds for every contingency; corrective post-contingency
   redispatch, N-2 and emergency ratings are not modelled. These compose the same way — more rows,
   or a second dispatch block per contingency — and are recorded here as the next step.
2. **The same DC model throughout.** The screen, the rows and the confirmation share one set of
   assumptions, which is what makes "secure" mean something precise: no DC post-contingency
   overload at the normal rating. AC security is a check (`ac_check`), not a constraint.
3. **Ratings drive feasibility.** The test suite's 1 MVA-floor ratings leave every bundled fixture
   but case14 infeasible; the reader-facing `derived/case14_rated` is secured at 13 % extra cost.
   The manual says so, so an infeasible result reads as a finding about the data, not a bug.

*Rejected:* enumerating every (outage, branch) row up front — simplest to reason about, but
hundreds of thousands of dense rows on the larger fixtures for a handful that bind; a separate
SCOPF LP builder — a second copy of the balance, flow, epigraph and hypograph families to keep in
step with `dc_opf`, the duplication ADR-007 and ADR-008 exist to prevent; trusting the loop's own
screen as the proof of security — the brute-force agreement tests say it would be right, but the
real `contingency.n1` on the result costs a few re-solves and leaves nothing to take on faith.

## ADR-017 — Unit commitment is the multiperiod market with binaries, priced by the restricted LP

**Status:** accepted 2026-10-12.

**Context.** `PolynomialCost` and `PiecewiseCost` have carried `startup` and `shutdown` fields
since M1 that nothing read; the DC-OPF manual said so. The multiperiod market (M5) clears a
horizon as one LP, which cannot switch a unit off: a generator with `p_min_mw > 0` runs at its
minimum in every period whether or not that is worth it, a constant cost term is charged in every
period unconditionally, and a start-up never costs anything. For a fleet with real minimums and
event costs that is not a schedule anyone could run. HiGHS solves MILPs, so the decision can be
modelled without a new dependency.

**Decision.** Unit commitment is an option of the multiperiod market, not a new solver or a new
kind.

1. **One builder, one more block.** `multiperiod_dc_opf` gains an optional `Commitment` block —
   start-up, shut-down and no-load costs and the status before the horizon, per unit — and with
   it three binary columns per unit per period (`on`, `started`, `stopped`) in a third column
   tier, and four row families after tier 8: capacity and minimum against `on`, the start/stop
   logic, and one event per period. Without the block the model is byte-for-byte the LP it was.
   The ramp rows split into one-sided pairs relaxed on the period a unit starts or stops, so a
   start to any output and a stop from any output are admissible; no minimum up/down time.
2. **Only units with something to decide get binaries.** A unit with no minimum output, no
   no-load cost and no event cost is the same on at 0 MW as off; it keeps its continuous column
   and is reported always on. This is what keeps the MIP small and the schedules of idle free
   units from flapping at zero cost.
3. **MILP, not MIQP.** HiGHS has no MIQP, so the builder refuses a quadratic cost under
   commitment, and the market wrapper linearises it into `quadratic_segments` convex chords of
   `c2·p² + c1·p` between 0 and `p_max` and passes them as a piecewise-linear cost, with `c0`
   moved into the block as the no-load cost. The epigraph rows carry the unit's `on` column so an
   off unit's cost is exactly zero rather than the first chord's intercept. The reported cost is
   the chord cost, an over-estimate by the chord error, documented as such.
4. **Prices are the restricted LP's.** A MIP has no duals. After the MIP solves, the builder fixes
   every binary at its solution and re-runs the model as an LP, and every dual the market reads —
   LMPs, bound and ramp prices, settlement — is that LP's. This is the standard pricing run of a
   unit-commitment market: the LMP is the marginal cost of energy given the committed fleet, and
   start-up and no-load costs are not recovered through it. The result carries what an uplift
   would need (`commitment_cost`, `no_load_cost`, per-unit event totals) and takes no position on
   how to settle it.
5. **Initial status is the declared dispatch.** A unit with `p_mw > 0` in the network's own state
   is on before the horizon, one at zero is off — the one datum the model already carries that
   means "running now". An explicit initial-status field is not added until a caller needs one.

**Consequences.**

1. **The same result, with a schedule.** `MarketMultiperiodResult` gains `commitment`,
   `commitment_cost` and `no_load_cost` (defaults empty and zero) and each generator row a
   `committed` flag (default true), so a result serialised before this ADR still validates and a
   reader of the LP result reads the committed one. `market.multiperiod` stays the one kind.
2. **Prices move with the linearisation.** Under commitment a quadratic fleet is priced from its
   chords: slightly different LMPs than the QP's, converging with `quadratic_segments`. The LP
   path is untouched.
3. **Not modelled:** minimum up and down times, reserve requirements, start-up cost that depends
   on how long the unit was off, and a configurable end-of-horizon status. Each is more rows or
   columns on the same block and is recorded here as the next step.

*Rejected:* a separate `market.unit_commitment` kind and result — a second copy of the period
rows, settlement and LMP decomposition for one extra block of columns; solving the MIQP with a
different solver — a new runtime dependency, which ADR-002 rules out; pricing from the MIP's LP
relaxation — cheaper, but the relaxation's prices belong to a fleet that is fractionally
committed and are not what any market settles on; charging `c0` unconditionally under commitment
— the LP's reading, which under commitment would pay a unit for being off.

## ADR-018 — AC-OPF by trust-region sequential LP on HiGHS, with a power-flow restoration

**Status:** accepted 2026-10-12.

**Context.** Epic 01 excluded AC-OPF: the DC-OPF's dispatch is checked for AC feasibility after
the fact (`ac_check`) and routinely fails it, and its LMPs carry no loss or voltage term. Every
production AC-OPF is an interior-point NLP (MATPOWER's MIPS, PYPOWER's PIPS, IPOPT), and the
package's runtime stack is numpy, scipy and HiGHS (ADR-002): no NLP solver, and HiGHS's QP
solver — tried first — gives up with "Solve error" on these problems within a few iterations.

**Decision.** `opf.ac_opf` solves the full AC-OPF (polar form, apparent-power limits) as a
sequence of HiGHS LPs inside a trust region, with an AC power flow as the restoration step.

1. **First-order model, exact costs.** Each LP linearises the nodal balance by the Newton
   Jacobian the power flow already factorises and each flow limit by `2P·dP + 2Q·dQ`, and
   confines the step to a trust region on angles, magnitudes and active dispatch. A quadratic
   cost is carried as convex chords through the current dispatch — eight across the `Pg` radius
   plus one to each bound — in `dc_opf`'s epigraph encoding, so the LP's `Pg` step is zero exactly
   when the marginal price sits between the chord slopes at the current point.
2. **Restoration by the package's own power flow.** After each step, `pf.ac_newton.newton` runs at
   the LP's point: generator buses hold the LP's magnitude, the slack its angle, every other
   voltage floats, the slack unit and the generator buses' `Qg` close the balance within their
   limits with the power flow's Q-limit rounds. This removes the second-order residual a
   first-order step leaves, so the `ℓ₁` merit function sees the cost and not the linearisation
   error; without it the ratio test starved the trust region and the loop crawled.
3. **Termination is a KKT test at chord resolution.** A feasible zero step cuts the radii; below
   `step_tol_mw` the point is a KKT point to that accuracy and the LP's row duals are the
   problem's multipliers (the P-balance duals the AC LMPs). An economic tolerance (`cost_tol`)
   and a stall count end a slow final crawl along a curved valley at the same accuracy.
4. **Evidence, not assumption.** All six bundled cases reach MATPOWER's published `runopf`
   objectives (worst 1.5e-5 relative, case30; 2e-6 or better elsewhere), case14's published
   dispatch and bus-1 LMP are reproduced, a hand case is checked against `scipy.optimize`
   with the power-flow equations written out independently, and `tests/parity` checks cost,
   dispatch and voltages against pandapower's `runopp`.
5. **It is a `jobs` kind.** `opf.ac`, `OpfAcOptions` → `OpfAcResult`, the tenth kind.

**Consequences.**

1. **Linear convergence, tens of LPs.** A first-order model converges linearly: 34 LPs on case14,
   50 on case300, each a sparse problem HiGHS solves in milliseconds — seconds in total at
   case300 size, against sub-second for an interior-point code. Accepted for the solver stack it
   keeps.
2. **Local, like every AC-OPF.** A KKT point of a non-convex problem, from the power-flow start.
   Where the AC-OPF has several local optima this finds the one nearest that start, exactly as
   the interior-point codes do from theirs.
3. **The DC-OPF manual gains its comparison.** The DC result is what the AC result approximates;
   the manual pages point at each other and the example runs both.
4. **Not modelled:** angle-difference limits, dispatchable loads and reactive costs, a
   security-constrained AC formulation, re-slacking. Each is rows or columns on the same LP.

*Rejected:* HiGHS's QP solver with the true quadratic objective — reaches the optimum, then
reports "Solve error" on a 6e-5 primal infeasibility it cannot clear; a hand-written primal-dual
interior-point method (MIPS) — the standard, but it needs the second derivatives of the power-flow
equations and a careful implementation, a larger and riskier surface than one that reuses the
Newton Jacobian and the simplex; `scipy.optimize.minimize(method="trust-constr")` — a general NLP
code with no sparsity in its constraint handling at this scale, and its multipliers' conventions
would have to be trusted for the LMPs; pure SLP without restoration — the first version here,
which crawled because the merit penalty on second-order residuals ate every step's gain.

## ADR-019 — Minimum up and down times as event-window rows on the commitment binaries

**Status:** accepted 2026-10-13.

**Context.** ADR-017's unit commitment lets a unit start and stop in adjacent periods: nothing
holds a started unit on or a stopped unit off, which is the first thing a thermal unit's
operator will object to, and the one gap that ADR listed. The model carried no such data.

**Decision.** `Generator` gains `min_up_periods`, `min_down_periods` and
`initial_state_periods`; `Commitment` gains the matching arrays; `multiperiod_dc_opf` builds
two more row families after the four of ADR-017.

1. **Event-window rows, not state chains.** For a committable unit with `min_up > 1`, one row
   per period: the start-ups of the last `min_up` periods ending at `t` sum to at most `u[t]`
   (`Σ v[s] − u[t] ≤ 0`, `s = max(0, t − min_up + 1) .. t`); for `min_down > 1`, the
   shut-downs of the last `min_down` periods sum to at most `1 − u[t]`. These are the standard
   tight formulation on the `(u, v, w)` triple (Rajan–Takriti), one row per period per unit,
   and they use the event columns ADR-017 already has. A minimum of 1 is what the logic row
   says on its own and builds no row.
2. **Pre-horizon obligations are fixed columns.** `initial_state_periods` is how long the unit
   has been in its `initial_on` state, counting the period just before the horizon. A unit on
   for `k < min_up` periods has `u[t]` fixed at 1 for `t < min_up − k` (clipped to the
   horizon); a unit off is held off against `min_down` the same way. `None` means long enough
   that nothing carries in — the wrapper's reading of a generator that states no history.
3. **The data travels.** The three fields round-trip through JSON and the CSV bundle (which
   gains an integer column kind), are exported to PyPSA as `min_up_time` / `min_down_time` and,
   when stated, `up_time_before` / `down_time_before`, and are reported as dropped by the
   pandapower exporter, which has no column for them.

**Consequences.**

1. **Minimal surface.** Three model fields, three `Commitment` fields, two row families, two
   result fields on `GenCommitmentResult`; the restricted-LP pricing, the ramp relaxation and
   everything else in ADR-017 are untouched, and a network that states no minimum times builds
   the same MIP as before, row for row.
2. **Periods are the unit.** `Period` has no duration, so the minimum times are counted in
   periods, like the ramps; a caller with hourly periods and a four-hour minimum writes 4.
3. **Not modelled:** start-up costs that depend on how long the unit has been off (hot/warm/cold
   starts), start-up and shut-down ramp trajectories, must-run and fixed-outage windows. Each is
   more columns or bounds on the same binaries.

*Rejected:* one aggregated row per unit over the whole horizon — weaker LP relaxation, slower
MIP; counting the minimum times in hours with a period duration on `Period` — a model change
with no other consumer yet, and the ramps are already per period.

## ADR-020 — Emergency ratings: a post-contingency flow is held to a second, higher limit

**Status:** accepted 2026-10-13.

**Context.** ADR-016's SCOPF and the N-1 screen held every post-contingency flow to the branch's
one `rating_mva`. Operators rate a line twice: a continuous rating and a short-term one the
line may carry for the minutes after a contingency, until corrective action. MATPOWER (`RATE_C`)
and PSS/E (`RATEC`) both carry it; with only the normal rating the preventive dispatch is more
expensive than it needs to be, and on the bundled fixtures often infeasible outright.

**Decision.** `Branch.rating_emergency_mva`, a second optional rating that only the
contingency code reads.

1. **One array, one fallback.** `NetworkArrays.rating_emergency_pu` is the emergency rating
   where set and `rating_pu` where not, so the N-1 screen, the confirming re-solve and the SCOPF's
   security rows switch to it with one line each and a network that states none is unchanged.
2. **The base case never sees it.** The power flow, DC-OPF and AC-OPF rate the intact network
   at `rating_mva` alone; the SCOPF secures against the emergency rating while holding the base
   case to the normal one — the standard preventive formulation with short-term ratings.
3. **The data travels.** Read from MATPOWER `RATE_C` and PSS/E branch `RATEC` only where they
   exceed the normal rating (every bundled case reads as before), round-tripped through JSON and
   the CSV bundle, and reported as dropped by the pandapower and PyPSA exporters, which carry one
   rating.
4. **Validated.** An emergency rating needs a normal rating and may not be below it
   (`BAD_RANGE`).

**Consequences.**

1. **"Secure" gains a second number.** `N1BranchFlag.rating_mva` and
   `SecurityConstraintResult.rating_mva` report the limit that was applied, which is the
   emergency rating where one exists.
2. **The prerequisite for corrective redispatch.** A corrective SCOPF holds the immediate
   post-contingency flow to the emergency rating and the redispatched one to the normal rating;
   this field is the first of those two limits.
3. **Not modelled:** a third (load-shedding) rating, time-dependent ratings, and PSS/E
   transformer `RATC1`.

*Rejected:* a single configurable factor on the normal rating (`ScopfOptions.emergency_factor`)
— a global knob where the data is per branch and both file formats carry it per branch.

## ADR-021 — Corrective SCOPF: a redispatch column block per contingency in the same LP

**Status:** accepted 2026-10-13.

**Context.** ADR-016's SCOPF is preventive: one dispatch holds every post-contingency flow,
with no action after the outage. Operators do act — within the minutes an emergency rating
(ADR-020) buys — and a preventive dispatch is dearer than it needs to be by exactly the
corrections it refuses to count on. ADR-016 recorded corrective redispatch as the next step
and ADR-020 supplied the first of its two limits.

**Decision.** `ScopfOptions.corrective` adds, for every contingency that needs one, a corrected
dispatch to the same LP.

1. **A block, not a second solver.** `dc_opf` gains an optional `CorrectiveRows` block: per
   corrected contingency a second set of generator columns, bounded like the base dispatch with
   the lost unit fixed at zero, tied to the base dispatch by two-sided ramp rows
   (`Generator.ramp_up_mw` / `ramp_down_mw`, the one-period ramp read as the corrective one),
   closing its own balance with no slack pickup, and holding the monitored branches' corrected
   flows to the *normal* rating. The immediate flow stays a `SecurityRows` row at the emergency
   rating. The corrected dispatch has no cost: the objective is the base dispatch's.
2. **Generated the same way.** The constraint-generation loop screens twice per solve: the base
   dispatch against the emergency ratings (ADR-016, unchanged) and, per outage, the corrected
   dispatch where one exists or the base dispatch where not against the normal ratings. Each
   newly flagged pair is a corrected row; an outage flagged for the first time gets a block.
   Linearity gives the same finite termination argument as ADR-016.
3. **Priced.** A corrected balance row's dual joins the LMP's energy term and a corrected flow
   row's the congestion term (`lmp_decomposition(..., corrective)`); on the hand case a binding
   corrective ramp prices the load bus at the ramping unit's marginal cost.
4. **Confirmed.** Every correction is re-solved for real — the network with the outage applied
   and the corrected dispatch written in, through `pf.dc.solve` — and reported as
   `confirmed_max_loading`; `corrected_secure` is that verdict, next to `n1`'s `secure` for the
   immediate flows.

**Consequences.**

1. **Three answers bracket each other.** Preventive at the normal rating ≥ corrective ≥
   preventive at the emergency rating, and without an emergency rating corrective equals
   preventive. The hand case and case14_rated check the ordering.
2. **The LP grows by `n_gen` columns per corrected outage**, not per contingency: only the
   outages the screen flags against the normal rating get a block. On case14_rated with 30 %
   emergency headroom that is 18 blocks and 3 solves.
3. **The ramp field does double duty.** `ramp_up_mw` / `ramp_down_mw` are the per-period ramps
   of the multiperiod market and the corrective ramps here; a dedicated corrective ramp is a
   field away if a caller needs the two to differ.
4. **An LP, like the commitment.** HiGHS's QP solver reports "Solve error" on the corrective
   problem of case14_rated (it survives the preventive one), so under `corrective` a quadratic
   cost is linearised into `quadratic_segments` chords (default 16, 0.1 % chord error on
   case14) — ADR-017's answer to the same failure. The preventive path keeps the exact QP.
5. **Not modelled:** a cost on the correction, load shedding as a corrective action, N-2.

*Rejected:* corrective rows on the base columns with a relaxed rating (a "soft preventive"
formulation) — it answers a different question and cannot express a lost unit's replacement; a
separate corrective SCOPF builder — ADR-007/008's duplication again; charging the corrected
dispatch its own generation cost — it never runs unless the contingency happens, and the
expected-cost weighting that would make it meaningful needs outage probabilities the model does
not carry.

## ADR-022 — PSS/E RAW export: the writer the importer reads back

**Status:** accepted 2026-10-13.

**Context.** M8 shipped RAW v33 import only; pandapower JSON and the CSV bundle go both ways
and PyPSA is export-only because it is a Python object, not a file. A case prepared here —
rated, re-dispatched, secured — could not be handed to the planning tools that speak RAW.

**Decision.** `io.psse_raw_export`, re-exported from `io.psse_raw` as `dump` / `dumps` /
`*_with_report` like every other writer.

1. **Write the form the importer reads without folding.** `CW = CZ = CM = 1`, constant-power
   loads, no end shunts, no magnetising admittance: every value lands in the one field the
   importer maps straight to the model, so read → write → read is the identity on the bundled
   `case14_v33.raw` (tested, with an empty report) and on every bundled MATPOWER case the AC
   solution is reproduced to 1e-12 pu.
2. **Numbers from ids, or numbered and said so.** The importer's id grammar (`bus-<I>`,
   `load-<I>-<ID>`, `branch-<I>-<J>-<CKT>`) is parsed back; any other id is numbered by
   position and reported `RAW_ID_RENUMBERED` once per table, because a reader of the file
   cannot recover the original ids.
3. **The report rule, unchanged.** Costs, bids, storage, a transformer's line charging, bus
   coordinates and generator ramps and minimum times have no RAW field and are reported under
   the generic codes; defaults the format demands (bus state, voltage limits) are reported
   `FIELD_DEFAULTED`.
4. **Emergency ratings travel.** `RATEC` / `RATC1` are written from `rating_emergency_mva`
   (ADR-020); the importer reads the branch one back.

**Consequences.**

1. **Every file format now round-trips** except PyPSA, which is not a file. The formats page
   says which fields each direction loses.
2. **Transformer charging is the one physical loss.** A RAW transformer record has no `B`; it
   is dropped with a report rather than approximated as end shunts, which would sit outside the
   tap and change the solution anyway. case300 is the bundled case it touches.
3. **Branch order is the format's**, lines then transformers; ids carry the identity.

*Rejected:* writing `CZ = 2` / `CW = 2` records with winding bases — more faithful to how PSS/E
users author files, but every value then goes through the importer's scaling and the round trip
is only approximately the identity; folding transformer charging into fixed shunts — see
consequence 2.

## ADR-023 — Spinning reserve as costless headroom columns, priced by the requirement row

**Status:** accepted 2026-10-13.

**Context.** ADR-017 listed reserve requirements as the next thing the commitment model lacked:
a market that commits units for energy alone leaves the fleet with whatever headroom the energy
optimum happens to have. Operators require a stated amount, and pay for it.

**Decision.** `Period.reserve_mw` and `Generator.reserve_max_mw` on the model;
`multiperiod_dc_opf(..., reserve_mw, reserve_max_mw)` on the builder; two more row families.

1. **Reserve is headroom.** One costless column \(r_g[t]\) per unit per period, bounded by the
   unit's cap, with \(\sum_g r_g[t] \ge R[t]\) (tier 15) and \(p_g[t] + r_g[t] \le p^{\max}_g
   u_g[t]\) (tier 16; \(u = 1\) without commitment). Reserve is what the unit is *not*
   generating, so an uncommitted unit holds none and a requirement the running fleet cannot
   meet is what commits another.
2. **Priced by its own dual.** The requirement row's dual is the reserve price: zero while
   headroom is spare, otherwise the energy cost of freeing a MW. No reserve offer price: the
   package carries none, and a costless column makes the price exactly the opportunity cost.
3. **Settled outside the energy identity.** `total_reserve_payment = price × held` per period,
   an uplift; LMPs, load payments, receipts and congestion rent are the energy market's as
   before, so the settlement identity ADR-007's tests prove is untouched.
4. **Opt-in by data.** No period stating a requirement means no column and no row: the LP is
   byte-for-byte what it was.

**Consequences.**

1. **Three hand-costed answers.** Free reserve with spare headroom, $40/MW when only the cheap
   unit may hold it (a MW of energy moves from $10 to $50), and a requirement that commits a
   unit under ADR-017 — all in `tests/unit/test_market_reserve.py`.
2. **One product, spinning only.** No distinction between regulation, spinning and
   non-spinning reserve, no reserve from storage, no deliverability (zonal reserve) and no
   reserve offer prices; each is a column, a row or a cost on the same block.
3. **The file formats drop it.** `reserve_max_mw` has no column in pandapower, PyPSA or RAW
   and is reported dropped; it travels through JSON and the CSV bundle.

*Rejected:* a reserve fraction of load as an option — a per-period MW on `Period` is what
operators state and what a scenario file can carry; a reserve offer price per unit — nothing
in the model prices capacity, and the opportunity-cost price a costless column yields is the
standard co-optimisation result.

## ADR-024 — N-2 branch pairs by the generalised LODF, with cut sets detected rather than estimated

**Status:** accepted 2026-10-13.

**Context.** ADR-016 and ADR-021 both list N-2 as the next contingency class. The N-1 screen's
machinery — base case, LODF, bridges, confirming re-solves — covers everything but the pair
arithmetic, and the DC model is linear, so the pair estimate is a closed form rather than a
second re-solve.

**Decision.** `contingency.n2`, the pair counterpart of `contingency.n1`.

1. **The generalised LODF, vectorised.** For each branch \(i\), every pair \((i, j > i)\) is
   estimated at once: the 2×2 system for the two shed flows, then every other branch's flow
   from them — \(O(n^3)\) over the whole network, 0.2 s on case300.
2. **A zero determinant is an answer.** \(1 - L_{ij} L_{ji} = 0\) means the pair disconnects
   the network; such pairs are reported as `islanding_pairs` and never estimated, and a pair
   with an N-1 bridge is skipped up front. The brute-force test checks the determinant test
   against the model's own connectivity check on every pair of case14_rated.
3. **Confirmed like N-1.** Every flagged pair is DC re-solved with both branches out, one deep
   copy flipped and restored per pair; `max_confirmed_pairs` caps the re-solves and the result
   says when it did. Emergency ratings (ADR-020) are the post-contingency limit.
4. **A `jobs` kind.** `n2`, `N2Options` → `N2Result`, the eleventh kind.

**Consequences.**

1. **The same guarantee, one order up.** Flagged pairs confirmed to 1e-9 MW, unflagged pairs
   proved non-violating, islanding pairs proved islanding — all by brute force on the rated
   fixture.
2. **It is a screen, not a constraint.** No N-2 security rows in the SCOPF; ADR-016's
   constraint generation would take them unchanged (the pair row is linear in the dispatch),
   recorded here as the next step along with generator pairs and mixed pairs.
3. **The result can be large.** A weakly rated network flags thousands of pairs; the cap and
   `truncated` keep the result bounded and honest.

*Rejected:* N-2 by two successive N-1 LODF applications — wrong by the cross term whenever the
two branches interact; re-solving every pair — \(O(n^2)\) factorisations, minutes on case300
for a screen that costs a fifth of a second.

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
