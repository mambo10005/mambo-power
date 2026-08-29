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
walk: required
design-interview: true
model_plan:
  orchestrator: fable-5
  implementor: sonnet
  senior-implementor: opus
  researcher: sonnet
  test-runner: sonnet
  auditor: opus
  critic: opus
---

# Wave M7 — agents: strategic bidding, best-response iteration, markup against a bid cap

Integration branch `epic/01-foundation`, base `6ca9dcc` (M6's merge).
Step 1 record: `record/m7-scope-closure.md` (carries the D1–D3 design ledger).
Research: `record/m7-research.md`.

**How might we** let generators *bid* rather than be dispatched at cost — a `Strategy` deciding
what each unit offers, a market clearing those offers, settlement paying on the clearing price —
and show the machinery is honest by reproducing the competitive outcome when nobody games, and
producing a real markup when one supplier is pivotal?

M7 is the epic's last market wave and the first where the *inputs* to clearing are chosen by
something other than the network's own data. M4–M6 all solved a market whose supply curve was
fixed; M7 makes the supply curve an **output of a decision**, and the wave's content is the loop
that connects the two. The offered cost stays distinguishable from the true cost — that
distinction is what "markup" means, and it is why the offers reach the engine as an overlay and
the network is never mutated.

## Requirements

- **W1 — ADR-008 one level down, plus the generator-side overlap guard.** The diagonal-Hessian
  assembly, now a third verbatim copy across `dc_opf.py` / `multiperiod.py` / `zonal.py`
  (continuation-m6 carry-over 1), is unified into one shared helper **before** any agents column is
  written. Behaviour-preserving: M6's suite green unmodified. `redispatch.py`'s two-column form
  stays a non-caller — the 2×2 coupling is genuinely different, not duplication.
  **And one disclosed behaviour change:** `_extract_and_validate` raises when a *load* index
  appears in both bid maps but has **no mirror guard on the generator side** — a generator index in
  `pwl_costs` whose `cost_coeffs` row is nonzero is silently double-counted. Measured on case14
  (2026-08-28): the LP clears **Optimal** with that generator's dispatch driven from 223.19 MW to
  **0.00 MW** and the objective 2409.70 above the correct form. `gen_cost_coeffs` maintains the
  invariant by construction, which is why five waves never hit it; M7 is the first wave whose
  coefficients are assembled per round from strategy output, so the guard lands before the loop
  does. Silent-plausible beats loud-infeasible — the epic's most-repeated finding.
- **W2 — The `Strategy` seam** (`market/strategy.py`): `Strategy` is a `typing.Protocol` with one
  method, `offer(observation) -> GeneratorCost`. `Observation` is an **own-node view** — the agent's
  own true cost curve and capacity, the round index, and the agent's own **last two rounds** of
  `(offer, bus LMP, cleared MW)`; nothing global, and nothing about any rival. Two rounds, not one:
  measured 2026-08-28, a one-round view lets an agent tell whether it is marginal but **not whether
  its last move helped**, and the three rules computable from it either cycle or settle at a
  markup gain of **$0.02/h**. The strategy still holds no state — the loop supplies the history, so
  a run stays a pure function of `(network, strategies, tolerance)`.
  `StrategyConfig` is a discriminated union (`price_taker` | `markup`) on `kind`, mirroring
  `GeneratorCost` at `model/entities.py:87`, resolved to an instance by a factory. The first two
  rounds' observations have fewer than two prior points and their shape says so explicitly — never
  a silent zero.
- **W3 — The fixed-point loop** (`market/agents.py`): each round builds an offer map
  (generator id → `GeneratorCost`), clears it through the **general** array-level path — never a
  delegation to `solve_nodal` — forms each agent's own-node observation from the clearing, and
  applies the termination test below, up to `max_iterations`. Settlement is
  computed once, on the final round's clearing, at the final round's prices. The overlay is a
  choice of coefficients, not a mutation: `Scenario` and `Network` are untouched.
  **Updates are simultaneous, and the order is fixed and documented either way.** An earlier draft
  specified round-robin on the strength of a sweep showing simultaneous *exact best response*
  cycles in five of six duopoly configurations. That evidence does not apply to the strategies M7
  ships: an exact best response requires evaluating one's own profit at every candidate offer,
  which means clearing the market, which the own-node observation deliberately withholds. Measured
  with the incremental strategies that *are* computable, both orders reach the same point on the
  AC-5 duopoly. Simultaneous is kept because it is the simpler contract and matches scope answer 2
  as written; round-robin remains a documented fallback if S3's re-measurement disagrees.
  **Termination.** A fixed-step climber does not come to rest — it oscillates by ±one step about
  its optimum, which is the *expected* end state, not a failure. So the loop detects a repeated
  offer vector and then classifies it by the **amplitude** of the detected cycle:
  amplitude ≤ `offer_tol` is convergence (`converged`), amplitude above it is a genuine cycle
  (`termination_reason = "cycle"`), and neither is the iteration cap. Measured separation
  (2026-08-28): at a peak the amplitude is **1.0 = two steps of 0.5** on every fixture tried, while
  the non-climbing "raise while at capacity" rule swings the full markup range. This makes
  `offer_tol ≥ 2 × step` a **derived** constraint rather than a calibration — D6's "tune it later"
  is closed. Reporting a genuine cycle as an iteration-cap hit would be a confident wrong
  diagnosis, the failure mode this epic has named in every wave.
- **W4 — Result types** (`results/agents.py`): `MarketAgentsResult` carries the final clearing
  (generators, loads, buses, **branches**, settlement figures) plus `offers`, `iterations`,
  `converged` and `termination_reason`. `status` is the **LP's**; `converged` is the **loop's**;
  the two are never conflated in a field, a docstring or a message. Same wave, same requirement:
  `MarketNodalResult` gains the `OpfBranchFlowResult` rows `MarketZonalResult` already has,
  closing M5's A23 symmetrically (continuation-m6 carry-over 12).
- **W5 — The two economic statements.** (a) Price-takers reproduce the competitive result: the
  offer vector is *exactly* the true cost coefficients, and the clearing agrees with
  `market.solve_nodal` **exactly** — measured bitwise, so no tolerance enters. (b) A pivotal supplier's
  markup walks up to the point where demand's own `Load.bid` refuses to pay more — the cap is the
  bid-side willingness to pay that M4 already ships. **No new model field.**
- **W6 — Jobs.** Kind `market.agents`, `KINDS` exactly 8, JSON round-trip with the `StrategyConfig`
  union crossing as data (never a callable), never raises, all six error codes hold. Caller
  mistakes map to `BAD_OPTIONS` or `VALIDATION`, never `INTERNAL` — M6's walk found four that did.
- **W7 — Fixtures.** Wave-owned, built in the `tests/_rated.py` / `tests/_bids.py` tradition:
  (a) the **smooth pivotal** network — 900 MW at a true $20/MWh against `q = 1000 − 10·price`, no
  competing unit between cost and the peak, closed-form optimum $60.00 / 400 MW / $16,000/h;
  (b) its **non-pivotal control** — the same unit with a 900 MW rival at $22, which stops the climb
  at $21.50; (c) the **≥2-reactive-agent duopoly** — 300 MW / 300 MW at $20 against the same bid
  curve. All three round counts and end states are **re-measured** through committed test machinery
  before AC-4's and AC-5's numbers are frozen; disagreement with the Step-2 measurements is a
  finding, not a tolerance to widen.
- **W8 — Docs** (epic R14 standing requirement): manual page, API pages rendering every new result
  and config field, architecture edges, an example, changelog. Plus the `docs/manual/jobs.md`
  registered-kinds update — **corrected 2026-08-28 after S8 refuted the spec's own claim with
  proof**. It is not a stale line and not a one-line fix: the page is *accurate today* (the
  registry holds exactly the seven kinds it lists, and `test_docs_registry_listing.py` pins the
  current list verbatim, 4 passed), and the eighth kind invalidates **three** sites together — the
  `print(jobs.kinds())` block (~:242), the capability table (~:250, needing a new
  `market.agents`/`MarketAgentsResult` row) and the transcript (:267). It is therefore
  **contingent on W6 registering the kind** and cannot land before it.

## Not Doing

Stateful / learning / RL agents and seeded stochastic strategies (the `Strategy` surface must not
forbid a later stateful implementation, but M7 ships none and asserts nothing about one). New
model fields on `Generator`, `Load` or `Network` — if the design finds one unavoidable that is an
escalation, not a quiet addition. Multi-period or zonal agent bidding. Strategic demand — loads
carry bids and those bids are data, not decisions. Unit commitment, declared unavailability, or
physical withholding: markup is economic, the offer curve moves and the capacity does not. A
second solver. Equilibrium existence or uniqueness proofs — M7 reports whether *its own iteration*
converged and claims nothing more. **Markup on a non-linear cost** — `MarkupStrategy` is scoped to a linear `PolynomialCost` and
raises `NotImplementedError` otherwise. Measured consequence: all **147** generators across the six
committed MATPOWER fixtures carry quadratic costs, so a markup agent can be attached to **none** of
them and works only on W7's synthetic fixtures. No acceptance row is affected; no docs example may
show otherwise. The natural widening (a constant adder to `c1`) is an M8 candidate, declined here
because it redefines the profit the AC-4/AC-5 numbers were measured from.
**Global best response** — the strategies M7 ships hill-climb on
their own observed profit and therefore find a *local* optimum; where a competing unit puts a
discontinuity between an agent's cost and its peak, the climb provably stalls short (A4: $9,497.52
against a derivable $12,250). M7 does not claim otherwise and does not ship a fixture that hides
it.

## Prior art

M4 is the direct ancestor: it made demand elastic and gave the clearing a bid surface, and
`Load.bid` is precisely the cap W5(b) leans on. M6 is the process ancestor: ADR-009 consequence 3
established that an end-to-end row can be structurally blind to a stage, which is exactly the trap
an iterated loop invites — a fixed-point test that passes because the loop ran zero effective
iterations. M5's `Period` precedent binds too: a model field present but solver-ignored is how a
wave ships a lie, and M7 adds no field for that reason. The formulation is textbook and that is a
feature — best-response iteration in a supply-function game is standard (AMES, EMCAS; the Cournot
and supply-function-equilibrium literature). **No external engine models strategic bidding in a
form this repo can compare against — PyPSA clears, it does not bid — so outside the docs row M7
has no T2 oracle, and the matrix does not pretend otherwise.** AC-3's oracle is `solve_nodal`
itself; AC-4's is a hand-derived optimum.

## Acceptance criteria

- **AC-1** — W1, in three clauses.
  (a) The unification is behaviour-preserving: M6's complete suite passes with **zero test edits**
  on a tree differing from `6ca9dcc` only in the unified files.
  (b) A sabotage of the shared helper's diagonal takes at least one test red in *each* of the three
  callers' test modules, naming the residual that moves in each.
  (c) The new generator-side overlap guard fires: a generator index appearing in `pwl_costs` with a
  nonzero `cost_coeffs` row raises, mirroring the load-side message; and the previously-measured
  silent wrong answer is reproduced against the pre-guard build as the guard's power proof —
  dispatch 223.19 MW → 0.00 MW, objective +2409.70, status still `Optimal`. Clause (c) is the one
  deliberate behaviour change in W1 and is disclosed as such.
  provenance: ADR-008's reasoning one level down; continuation-m6 carry-over 1; m7-research §7;
  the A2 resolution probe 2026-08-28

- **AC-2** — the overlay never mutates the network: `Scenario` and `Network` serialize
  byte-identically before and after a `solve_agents` run whose agents all bid above cost, and every
  `Generator.cost` is unchanged. Paired positive control: on that same run the coefficients handed
  to the array builder **differ** from the true ones — so the byte-identity is not the vacuous
  consequence of a run in which nothing happened.
  provenance: scope answer 1 2026-08-28 ("overlay handed to the builder, network never mutated")

- **AC-3** — price-takers reproduce the competitive result, in two clauses.
  (a) **Exact, on the input**: on an all-price-taker configuration the offer coefficients handed to
  the array builder are `array_equal` to the generators' own true cost coefficients.
  (b) **Exact, on the output too**: dispatch and LMPs are `array_equal` to `market.solve_nodal`'s.
  Measured 2026-08-28 — five independent `dc_opf` constructions on identical input agree
  **bitwise**. The research premise that two separate `highspy.Highs()` constructions must diverge
  is false for *identical* input: M5's macOS one-ULP finding was a structurally different LP (T=1
  multiperiod builds extra rows), whereas here both paths hand the builder the same arrays, and CI
  runs both calls in one process on one machine. Should a platform ever disagree, that is a finding
  to record, not a tolerance to introduce quietly.
  No price-taker short-circuit exists: the all-price-taker case is an ordinary run of the general
  path, so both clauses exercise the loop, the overlay and the offer map.
  provenance: D1 2026-08-28 "Exact inputs + bounded outputs" — the *outputs* turned out to be exact
  as well, strengthening the row beyond what D1 asked for; m7-research §5(a), corrected by
  measurement

- **AC-4** — a pivotal supplier's markup stops where demand stops paying. **Fixture**: one
  strategic supplier, 900 MW at a true $20/MWh, facing `Load.bid` giving `q = 1000 − 10·price`,
  with **no competing unit between its cost and the peak** — a *smooth* residual demand, chosen
  deliberately and disclosed (see Not Doing). Closed form: profit `(π − 20)(1000 − 10π)` peaks at
  **π = $60.00, q = 400 MW, profit $16,000/h**. Measured 2026-08-28: the climb reaches offer
  **$60.00**, price **$60.00**, dispatch **400.00 MW**, profit **$15,999.98** — against $0.06 at
  true-cost offers. The quantity that stops it is demand's own bid curve; raising the bid moves the
  peak.
  Paired control: the same strategy and the same unit, now facing a 900 MW rival at $22, stops at
  offer **$21.50** for a gain of **$1,177.50 against the pivotal $15,999.92** — real, nonzero, and
  **13.6× smaller**, and stopped by the *rival*, not by demand. Both numbers are asserted; neither
  is a bound.
  These replace the research's 363.64 MW / $63.64 and 593.20 / 10,101.01, which came from a
  different demand curve and from an exact best response the shipped agent cannot compute. The
  wave asserts numbers it has reproduced through its own clearing.
  provenance: scope answer 3 2026-08-28; the A4 measurement 2026-08-28, superseding
  m7-research §5(b)

- **AC-5** — the loop's own termination, in two halves, on a **≥2-reactive-agent** fixture (the
  only shape in which best-response can fail to settle in one round).
  (i) **Convergence is real**: the run takes strictly more than one non-trivial round and ends with
  the offer vector's oscillation amplitude inside `offer_tol`, reporting `converged=True` with
  `iterations` equal to the measured count. Measured on the symmetric duopoly (300 MW / 300 MW,
  true MC $20/MWh, `Load.bid` giving `q = 1000 − 10·price`), step 0.5: the run reaches offers
  `[60.0, 60.0]` at a clearing price of **$60.00** and a joint profit of **$15,999.98** against
  **$11,999.96** at true-cost offers, with a settled amplitude of **1.0** — exactly two steps — at
  **iteration 84**. Both the round count and the amplitude are asserted; the amplitude is what
  makes `converged` mean something.
  (ii) **Non-convergence is reported, not hidden**, in both of its shapes: with `max_iterations`
  set below the needed count the run stops with `termination_reason` naming the **cap**; and on the
  same fixture driven by the "raise while at capacity" rule — whose oscillation spans the whole
  markup range, far outside `offer_tol` — it stops with `termination_reason` naming the **cycle**,
  not the cap. `converged=False` in both, and neither a truncated nor a cycling result ever
  presents as converged.
  `status` is asserted independently of `converged` in every clause.
  provenance: D2 2026-08-28 "Dedicated row, both halves"; m7-research §4; the A1 and A4
  measurements 2026-08-28; ADR-009 consequence 3 (the visible rows must not be structurally blind
  to a stage)

- **AC-6** — jobs: `market.agents` registered and `KINDS` exactly 8; a request round-trips through
  JSON with the `StrategyConfig` union crossing as data; and each of an unknown strategy kind, a
  strategy naming a nonexistent generator, a non-positive `max_iterations`, and a non-positive
  `offer_tol` maps to `BAD_OPTIONS` or `VALIDATION` — never `INTERNAL`, never a silently accepted
  last-wins duplicate.
  provenance: M6 walk (four caller mistakes on `market.zonal` returned `INTERNAL`, one duplicate
  silently accepted); D7; epic jobs requirement

- **AC-7** — docs: manual page, API pages rendering **every** new result and config field under the
  per-model griffe guard, architecture edges, an example that runs, changelog entry, and the
  `docs/manual/jobs.md:267` stale-transcript fix. `mkdocs build --strict` exit 0; every example
  runs.
  provenance: epic R14; M6 fold-b's griffe extension and the per-model form of its guard (R2)

- **AC-8** — `MarketNodalResult` carries `OpfBranchFlowResult` rows agreeing with `pf.dc` on the
  same solution to a pinned tolerance, under the same field name and row type as
  `MarketZonalResult`. Closes M5's A23 symmetrically and retires the residual that bounded what
  M6's AC-4 could assert.
  provenance: continuation-m6 carry-over 12; M5 A23

## Design

Ratified 2026-08-28 in the Step 2 interview — D1–D3 walked one at a time, D4–D7 defaulted and
surfaced at ratification. Ledger: `record/m7-scope-closure.md`.

### Domain model

**No new model fields.** An **offer** is a `GeneratorCost` — the model's own discriminated union —
so the overlay is a `dict[str, GeneratorCost]` and `dc_opf._extract_and_validate` handles
polynomial and piecewise offers unchanged. The true cost stays where it is, on `Generator.cost`,
and is never overwritten; "markup" is the difference between the two, which only exists because
they are separate objects.

`StrategyConfig = Annotated[PriceTakerConfig | MarkupConfig, Field(discriminator="kind")]`, the
same shape as `GeneratorCost` and `LoadBid`. `Observation` is a frozen model carrying the own-node
view only.

### Component boundaries and interfaces

- `opf.dc_opf` — gains the shared diagonal-Hessian helper beside `_extract_and_validate`;
  `multiperiod` and `zonal` become callers, `redispatch` does not. `_extract_and_validate` gains
  the generator-side mirror of its load-side overlap guard. **No signature change** for the
  overlay: `dc_opf` already takes `cost_coeffs` / `pwl_costs` as arguments, so the offer map is
  simply *which* coefficients get passed. Serves W1, W3.
- `opf.gen_cost_coeffs` — generalised to take the cost source rather than always reading
  `Generator.cost`, so the offer overlay and the true-cost extraction are **one** function under
  two arguments. The existing `(net, arr)` call sites keep their behaviour. Serves W3, AC-3(a).
- `market.strategy` — `Observation`, the `Strategy` Protocol, `PriceTakerStrategy`,
  `MarkupStrategy`, `StrategyConfig`, `build_strategy(config)`. In-process callers may pass any
  structurally-conforming object; the jobs surface accepts only the named configs. Serves W2.
- `market.agents.solve_agents(scenario, options)` — the loop; `MarketAgentsOptions` beside it, as
  `MarketZonalOptions` sits at `market/zonal.py:233`. Serves W3, W5.
- `results.agents.MarketAgentsResult` / `AgentOfferResult`; `results.market.MarketNodalResult`
  gains `branches`. Serves W4, W8's rendering, AC-8.
- `jobs` — one more `KINDS` entry; `Runner` signature unchanged. Serves W6.

### Ownership table

| concept | owner (SSoT) | rendered at | agreement test |
|---|---|---|---|
| diagonal-Hessian assembly | the shared helper in `dc_opf` | `dc_opf`, `multiperiod`, `zonal` | AC-1 overlay-tree suite, zero test edits, per-caller sabotage |
| true cost | `Generator.cost` | AC-4's markup baseline | AC-2 network byte-identity + differing-coefficients control |
| offered cost | the round's offer map | LP objective, `MarketAgentsResult.offers` | AC-3(a) `array_equal` on the all-price-taker case |
| loop termination | `converged` + `termination_reason` | manual, API page | AC-5(ii) capped run |
| LP status | `status` | same | AC-5 asserts it independently of `converged` |
| strategy identity | `StrategyConfig.kind` | `AgentOfferResult.strategy`, jobs JSON | AC-6 round-trip |
| branch flows | `OpfBranchFlowResult` | nodal, zonal and agents results | AC-8 against `pf.dc` |

### Rejected alternatives

**A price-taker short-circuit to `solve_nodal`** (D1): buys bit-exactness by making AC-3 true by
construction — the row that exists to prove the loop honest would bypass the loop, the overlay and
the offer map, and a second code path would exist that no acceptance row exercises end to end.
That is the vacuity class this epic has hit three times (M5 A20, M6 F2, and M6's first replacement
for F2). **Deep-copying the network and rewriting `Generator.cost_coeffs`** (scope 1): loses the
true-vs-offered distinction and allocates a network per iteration. **An `offer` field on
`Generator`** (scope 1): widens the schema and the JSON snapshot for something one market mode
reads. **An `offer_cap` field, or a market-wide ceiling in `MarketAgentsOptions`** (scope 3): a
knob the other three market modes lack, so the union of market options stops being uniform.
**Stateful / seeded agents** (scope 2): determinism then needs a seed discipline every test must
pin — the coupling class that made M5's storage tests fragile. **An ABC base class** (D3a): nominal
coupling for a one-method interface, and the repo has no other ABC to match. **A plain callable**
(D3a): no per-agent identity or parameters in the result, and the config union reappears on the
JSON side anyway, without the type checking. **A full-previous-result or result-plus-network
observation** (D3b): makes `MarketNodalResult`'s shape part of the public strategy contract, and
lets an agent reconstruct the clearing and short-circuit the game the loop exists to play out.
**Converging on the LMP vector** (D6): prices can be stable across a degenerate face while offers
still move, so the loop could report converged with agents still re-bidding — M6's case300
degeneracy in a new place. **Damped updates** (A1, measured): the standard fix for best-response
cycling, and worse here — three of six configurations converge, at 16–21 rounds against
round-robin's 2–3, adding a tuning constant nothing calibrates.
**A one-round own-node observation** (A4, measured): cannot tell an agent whether its last move
helped; the rules it supports either cycle or reach a $0.02/h markup gain.
**A residual-demand-estimating strategy** (A4): would jump straight to a computed best response and
clear the local-optimum stall, but it puts a market model inside the agent — the rival reasoning
D3b excluded — and its correctness would need an acceptance row of its own.
**Weakening AC-4 to "the markup is real and stops"** (A4): robust to fixture shape and to whatever
strategy ships, and close to unfalsifiable — the vacuity class this epic has hit three times.
**Unit-tests-only loop coverage, or widening AC-4 to carry the loop**
(D2): the first leaves the acceptance matrix blind to the stage; the second gives an ambiguous red
and perturbs the only closed-form number in the wave.

### Assumptions

- **A1 — RESOLVED 2026-08-28, before approval, by building the fixture rather than deferring it.**
  The assumption as first written ("the fixture converges") was **false under the loop as first
  specified**. Six duopoly configurations were cleared through this repo's own `dc_opf` with an
  exact grid best response:

  | update rule | result |
  |---|---|
  | simultaneous | **cycles, period 2, in 5 of 6**; converges only under asymmetric capacity |
  | round-robin (one agent per round) | **converges in 6 of 6**, in 2–3 rounds |
  | damped simultaneous (α = 0.5) | converges in 3 of 6, taking 16–21 rounds |

  **What this sweep does and does not establish.** It measured *exact* best response — an agent
  evaluating its own profit at every candidate offer. That requires clearing the market, which the
  own-node observation deliberately withholds, so **it is not the dynamics M7 ships** (see A4). It
  is retained because it characterises the game: best response in a capacity-constrained duopoly is
  cyclic, the fixed point is asymmetric (one agent marks up to $45.00 while the other stays at its
  true cost of $20.00 — the Bertrand-Edgeworth outcome), and it is order-dependent (round-robin
  settles at `[45.0, 20.0]` where the damped rule finds `[20.0, 47.5]`). M7 reports the point *its
  own iteration* reaches and claims no uniqueness, exactly as Not Doing states. The update-order
  question this sweep appeared to settle is reopened and answered by A4 instead.
- **A2 — RESOLVED 2026-08-28, before approval.** An offer expressed as a `GeneratorCost` needs no
  `dc_opf` signature change: `opf.gen_cost_coeffs(net, arr)` **already** performs the whole
  union → `(cost_coeffs, pwl_costs)` mapping, including the all-zero-row convention for a PWL
  generator, and `dc_opf` already takes both as arguments. So M7 does **not** write a parallel
  assembler — it generalises `gen_cost_coeffs` to take the cost source (the offer map) instead of
  reading `Generator.cost`, which is also what makes AC-3(a)'s `array_equal` a comparison of two
  runs of *one* function rather than of two implementations. The probe that resolved this found the
  W1(c) defect: outside `gen_cost_coeffs` the invariant is unguarded.
- **A3 — RESOLVED 2026-08-28, and the assumption was over-cautious.** Five independent `dc_opf`
  constructions on identical input agree **bitwise**. M5's macOS one-ULP finding was a
  structurally different LP, not evidence about this comparison. AC-3(b) asserts `array_equal`, and
  no tolerance is introduced. If a platform ever disagrees, that is recorded as a finding.
- **A4 — RESOLVED 2026-08-28, and the assumption was false.** A *one-round* own-node observation is
  **not** sufficient: it tells an agent whether it is marginal but not whether its last move
  helped, and the three rules computable from it either cycle (period 2 and period 4) or settle at
  a markup gain of **$0.02/h**. Two rounds are sufficient and are what W2 now specifies — the agent
  compares its own profit at t−1 and t−2 and keeps or reverses direction. Measured on the smooth
  pivotal fixture, that climb reaches the closed-form peak exactly ($60.00 / 400 MW / $15,999.98
  against a derived $16,000.00) at every step size tried, in 84 / 44 / 24 rounds for steps of
  0.5 / 1.0 / 2.0.
  **The residual limitation, kept and disclosed:** this is *local* best response. Put a competing
  unit between the agent's cost and its peak and the climb stalls at the local optimum the
  discontinuity creates — measured **$9,497.52 against a derivable $12,250, 22% short**. AC-4's
  fixture is therefore smooth by construction, and the spec says so rather than letting a chosen
  fixture look like a general result.
- **A5 — RESOLVED 2026-08-28.** Checked rather than assumed (M5's A25 was exactly the error of not
  checking): the repository's only JSON schema snapshot is
  `tests/unit/snapshots/network.schema.json`, a **network**-model snapshot. No result model appears
  in any snapshot, so `MarketNodalResult` gaining `branches` cannot require a regeneration. It
  remains additive; that it breaks no existing test is S6's to prove.
- **A6** — `AgentOfferResult.markup` is derivable from `offer`, `true_cost` and the cleared MW. It
  must therefore be asserted **as that identity**, not presented as independent content (M6: "two
  quantities plus an identity are not three fields").
- **A7** — `termination_reason` is a required enumerated field — `converged` | `iteration_cap` |
  `cycle` — not free text and not inferable from the `converged` flag alone; and `iterations` is
  readable from the result, without which AC-5(i) is not assertable at all.
- **A8** — updates are simultaneous, in `NetworkArrays.gen_ids` order where order is observable at
  all. Nothing in the wave asserts that a *different* order reaches the same point, because the A1
  sweep showed it need not. The update rule is part of the documented contract, not an
  implementation detail, and S3 re-measures it against the shipped strategy; a disagreement makes
  round-robin the fallback W3 already names.
- **A9** — `offer_tol ≥ 3 × step` is derived, not tuned. **Corrected at Step 6** (critic finding 2,
  F18): the Step-2 derivation said *two* steps, measured as amplitude 1.0 at step 0.5 on every
  fixture — but every fixture's optimum sat on a grid point. When the optimum is equidistant from
  two grid points (true cost 33.33, step 0.01) the tie rule keeps direction and overshoots one extra
  step, giving a period-6, **three**-step orbit (amplitude 0.03), which `2 × step` reported as
  `cycle` after 3339 rounds. With `3 × step` the critic's 70-case sweep converges 70/70. A
  strategy that adapts its step must state its own settling amplitude, or the convergence test
  loses its meaning. Related limit, measured and *not* fixable by a constant: the profit-tie band
  `_PROFIT_TIE_REL_TOL = 1e-9` is below HiGHS's noise at a marginal agent (2.5e-8 relative at
  step 0.5, scaling linearly with step), while the smallest real one-step profit change scales with
  step² (1.8e-7 at step 0.01) — the two bounds cross, so no tolerance separates them at every
  step. Under `3 × step` a noise-decided tie only chooses which of two equal-profit offers the climb
  rests on; the verdict is `converged` either way.
