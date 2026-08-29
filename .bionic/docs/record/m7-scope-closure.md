# M7 / Step 1 — scope closure

Wave M7 (`agents`), triple **build · audited · wave**, integration branch `epic/01-foundation`
(base `6ca9dcc`, M6's merge). Recorded 2026-08-28.

Same arrangement as M5 and M6: the governing-skill hook blocks a wave spec carrying no `## Design`,
so `wave-07-agents.spec.md` is written once, after the Step-2 design interview. Until then this is
the durable record.

## Problem statement

**How might we let generators *bid* rather than be dispatched at cost — a `Strategy` deciding what
each unit offers, a market clearing those offers, settlement paying on the clearing price — and
show that the machinery is honest by reproducing the competitive outcome when nobody games, and
producing a real markup when one supplier is pivotal?**

M7 is the epic's last market wave and the first where the *inputs* to clearing are chosen by
something other than the network's own data. M4-M6 all solved a market whose supply curve was
fixed; M7 makes the supply curve an output of a decision, and the wave's content is the loop that
connects the two — plus the two statements that make it falsifiable: price-takers reproduce nodal,
and a pivotal supplier's markup stops somewhere derivable.

## Scope answers (user, 2026-08-28, three questions)

1. **Offers reach the engine as an overlay; the network is never mutated.** Each iteration produces
   an offer map (generator id → cost coefficients) passed alongside the network, mirroring how
   `market.nodal` already passes derived coefficients into the builder. Rationale accepted:
   `Scenario`/`Network` stay immutable, a run is reproducible from its inputs, comparing against
   `market.solve_nodal` is a like-for-like call, and — decisively — **the offered cost stays
   distinguishable from the true cost**, which is exactly what "markup" means. Rejected: deep-copy
   the network and rewrite `Generator.cost_coeffs` (loses the true-vs-offered distinction, and
   allocates a network per iteration); an `offer` field on `Generator` (widens the schema and the
   JSON snapshot for something one market mode reads, and every prior fixture would carry a field
   it never uses).

2. **"Learn" is stateless best-response iteration to a fixed point.** Every round, each strategy
   re-bids against the previous round's prices; iterate until offers stop moving or an iteration
   cap is reached. No per-agent memory and **no seed** — a run is a pure function of
   `(network, strategies, tolerance)`. Rationale accepted: both named acceptance tests work
   naturally (price-takers converge in one round; a pivotal supplier walks up to its limit), and it
   is what the Cournot / supply-function-equilibrium literature actually models. Rejected: one-shot
   (makes "learn" a no-op and reduces the pivotal test to asserting a hand-computed number rather
   than an emergent one); stateful per-agent memory (the AMES/RL shape — most extensible, but
   determinism then needs an explicit seed discipline and every test must pin it, the coupling class
   that made M5's storage tests fragile).

3. **The cap is the bid-side willingness to pay that already exists** (`Load.bid`, M4). **No new
   model field.** A pivotal supplier raises its offer until demand's own bid curve refuses to pay
   more. Rationale accepted: uses machinery three waves already exercise, and makes AC-4 a real
   economic statement rather than a test that a clamp works. Rejected: an `offer_cap` field on
   `Generator`; a market-wide ceiling in `MarketAgentsOptions` (a knob the other three market modes
   do not have, so the union of market options stops being uniform).

## Not Doing (explicit)

- **Stateful / learning agents, reinforcement learning, seeded stochastic strategies** — scope
  answer 2. The `Strategy` surface should not *forbid* a later stateful implementation, but M7
  ships none and asserts nothing about one.
- **New model fields.** Scope answers 1 and 3 between them mean M7 adds no field to `Generator`,
  `Load` or `Network`. If the design finds one unavoidable, that is a Step-2 escalation, not a
  quiet addition.
- **Multi-period or zonal agent bidding.** M7 clears through the single-period nodal path. Agents ×
  time and agents × zones are compositions a later wave can make once both exist.
- **Strategic demand.** Loads carry bids (M4) and those bids are data, not decisions. Only
  generators have strategies this wave.
- **Unit commitment, capacity withholding by declaring unavailability, or physical withholding.**
  Markup is economic — the offer curve moves, the capacity does not.
- **A second solver.** ADR-007 binds: clearing goes through the one array-level builder. ADR-008
  binds harder — the diagonal-Hessian assembly is now a third verbatim copy and is unified
  **before** any agents column lands. That is M7's first slice, as the preamble was M6's.
- **Equilibrium existence or uniqueness proofs.** M7 reports whether its own iteration converged;
  it does not claim the fixed point is unique or that one exists in general.

## Prior art / alternatives lens

- **Within this repo.** M4 is the direct ancestor: it made demand elastic and gave the clearing a
  bid surface, and `Load.bid` is precisely the cap scope answer 3 leans on. M6 is the direct
  process ancestor: it chained three solves and learned that an end-to-end row can be structurally
  blind to a stage (ADR-009 consequence 3), which is the trap an iterated loop invites — a
  fixed-point test that passes because the loop ran zero effective iterations. M5's `Period`
  precedent matters too: a model field that is present but solver-ignored is how a wave ships a
  lie, and M7 adds no field precisely to avoid it.
- **The formulation is textbook and that is a feature.** Best-response iteration in a supply-function
  game is standard (the AMES and EMCAS agent-based market platforms; the Cournot and
  supply-function-equilibrium literature). The risk is not "is the loop right" but "does the loop
  actually iterate, and is the reproduction test comparing two genuinely independent paths" — which
  is why AC-3 and AC-5 are separate rows.
- **Oracle, in preference order.** (i) `market.solve_nodal` itself is the oracle for AC-3 — an
  all-price-taker run must reproduce it, and under scope answer 1 the two calls hand the builder the
  same coefficients, so exactness is plausible and must be measured rather than assumed (M6's CI
  lesson: bit-equality on solver output is platform-dependent). (ii) Hand-derived optima on a
  smallest-pivotal network for AC-4. (iii) No external engine models strategic bidding in a form
  this repo can compare against — PyPSA clears, it does not bid — so **AC-6/AC-8 aside, M7 has no
  T2 oracle row and the matrix should not pretend otherwise.**

## Open questions carried into Step 2

- **The `Strategy` protocol's surface** — what an observation carries, and which of `Protocol` /
  ABC / plain callable survives JSON round-tripping through the jobs surface (research §2).
- **Termination and cycling** — what convergence test and tolerance, and whether best-response can
  cycle in this game rather than converge (research §4). This is the design's sharpest fork.
- **Whether AC-3's reproduction is bit-identical or tolerance-bounded** (research §5a).
- **`MarketAgentsResult`'s shape**, including closing M6's A40 by giving `MarketNodalResult` the
  branch rows `MarketZonalResult` already has (research §6).
- **The Hessian unification's helper shape and its behaviour-preservation proof** (research §7).

## Process notes carried in, binding from Step 0

- **Worktree setup**: `uv sync --all-extras --all-groups`, then prove `uv run --no-sync mkdocs
  --version` **before** dispatching any docs or walk agent (M6 A27 — the venv lacked the docs group
  and a gate run failed with an unexplained exit 2 beside a green suite).
- **One named gate sweep at the final head** — `pytest`, `ruff check`, `ruff format --check .`,
  `mypy`, `mkdocs build --strict` — never assembled ad hoc per check (M6 A38: a dropped format check
  let a red CI gate through, and the brief claimed "all gates green").
- **A replacement test's power proof must show it red under a defect in the specific quantity the
  criterion names** (M6 A37/A39 — the wave's most expensive lesson; a sabotage that moves the whole
  solution lets every clause fire for the wrong reason).
- **Never write "only" about a coverage set that has not been enumerated** (M6, ADR-009 consequence
  3 was false and contradicted its own consequence 1).
- **Drive the test's own fixture factory**, never a hand-assembled reconstruction (M5, three times).
- **Teardown**: junction via git-bash `rm` first; then sweep both listeners on agent ports **and**
  any process whose command line names the worktree (M6 carry-over 13).
- **A finding split across two agents needs a named owner and a check** (M5 CI finding; held in M6).

## Design ledger (Step 2, accreting — composed into the spec's `## Design` at close)

- **Frame ratified** (user, 2026-08-28, "Frame holds — walk D1 first"). Decision map D1–D7 as
  presented; D1–D3 strategic, D4–D7 tactical-defaulted and surfaced at ratification. Artifact form:
  `## Design` in the wave spec. Views: module map, loop stage boundaries, result-type sketch.
- **Research corrections carried in, both against the orchestrator's own premises:**
  (i) The brief asserted the paired non-pivotal case "makes the markup unprofitable". **False,
  verified numerically**: the markup gain falls from 10,101.01 $/h to 593.20 $/h — reduced ~17x,
  **not eliminated**. AC-4's paired case must assert the real, nonzero, ~17x-smaller number.
  (ii) The brief expected the overlay to make AC-3's reproduction bit-identical. **It does not**:
  `market.agents` calls `dc_opf` directly, so an all-price-taker round is *two* separate
  `highspy.Highs()` constructions and two `.run()` calls on numerically identical input — materially
  weaker than `solve_multiperiod`'s T=1 reduction, which is one evaluation of `dc_opf`'s own
  expressions. Bit-identity is reachable only by a deliberate short-circuit. This is D1.
- **The finding that shapes D2** (research §4): a best-response loop can only cycle when **two or
  more agents react simultaneously**. Both named ACs have exactly **one** reactive agent, so each
  converges after one non-trivial round — meaning neither exercises the tolerance check, the
  iteration cap, or `converged`. Scoped to the named ACs alone, the loop's termination machinery
  ships unexercised by any acceptance test. This is M6's ADR-009 consequence-3 lesson recurring in
  a new form: the visible rows are structurally blind to a stage.

### D1 — AC-3's reproduction claim: **exact inputs, bounded outputs** (user, 2026-08-28)

AC-3 carries **two** clauses, and the wave builds **no** price-taker short-circuit.

(a) **Exact, on the input.** The offer vector an all-price-taker round hands the array builder is
    `array_equal` to the generators' own true cost coefficients. Portable (no solver in the
    comparison), and red under any strategy-side defect — this is the clause that actually proves
    a price-taker strategy is a price-taker.
(b) **Bounded, on the output.** Dispatch and LMPs agree with `market.solve_nodal` under
    `assert_allclose` at a tolerance *measured* at implementation, carrying M5's power proof: a
    perturbation ~1000× the ULP of the compared quantity must still redden the row, so the
    tolerance is demonstrably not a blanket. Precedent and constants to beat:
    `EXPLICIT_PERIOD_RTOL = 1e-9` / `EXPLICIT_PERIOD_ATOL = 1e-8` in
    `tests/unit/test_market_multiperiod.py`.

Rationale accepted: exactness on the outputs is unreachable without a deliberate short-circuit
(the agents path builds a *second* `highspy.Highs()` on numerically identical input, and M5's
macOS one-ULP CI failure proved bit-equality on solver output is not portable). The short-circuit
was rejected because it makes AC-3 true by construction — the row that exists to prove the loop
honest would bypass the loop, the overlay and the offer path, and would leave a second code path
no acceptance row exercises end to end. That is the vacuity class this epic has hit three times
(M5 A20, M6 F2, M6's replacement for F2). Splitting the claim puts exactness where it is genuinely
available and a *proved-discriminating* tolerance where it is not.

**Binding on the design:** `market.agents` never delegates to `solve_nodal`; the all-price-taker
case is an ordinary run of the general path. The offer vector must therefore be *observable* —
clause (a) needs the coefficients the builder received, which makes "the offers of the final round"
a required member of the result or of a documented seam the test can read. This constrains D3
(the `Strategy` surface) and D4 (`MarketAgentsResult`'s shape).

### D2 — the loop gets a dedicated acceptance row, **both halves** (user, 2026-08-28)

A third acceptance criterion, on a fixture carrying **≥2 reactive agents**, asserting:

(i) **Convergence is real** — the loop takes strictly more than one non-trivial round, the offer
    vector is stable inside tolerance at the end, and `converged` is `True`.
(ii) **Non-convergence is reported, not hidden** — with the iteration cap deliberately set below
     the rounds the same fixture needs, the run stops, `converged` is `False`, and
     `termination_reason` names the cap. A truncated result must never present as converged.

Rationale accepted: without it the tolerance test, the cap and `converged` ship unexercised by any
acceptance criterion, because AC-3 has zero reactive agents and AC-4 exactly one — best-response
can only fail to settle in one round when two or more agents react simultaneously. Rejected:
unit-tests-only (leaves the acceptance matrix blind to the stage — ADR-009 consequence 3 verbatim,
and the sentence a later wave cites when pruning coverage); widening AC-4 (one row proving two
things gives an ambiguous red, and it perturbs the hand-derived pivotal optimum, the only
closed-form number in the wave).

**Binding on the design:** `termination_reason` is a required, enumerated field — not free text and
not inferable from `converged` alone. The fixture is wave-owned and must be built and its round
count *measured* before the criterion's threshold is written; if the two agents turn out to cycle
rather than converge, half (i) states the cycle honestly and the wave says so — M7 claims no
equilibrium existence result (Not Doing, scope closure). The `iterations` count must be readable
from the result for (i) to be assertable at all.

### D3 — the `Strategy` seam: **Protocol + config union**, **own-node observation** (user, 2026-08-28)

**(a) Surface.** `Strategy` is a `typing.Protocol` with one method — `offer(observation) -> cost
coefficients`. What crosses the jobs surface is a `StrategyConfig` **discriminated union**
(`price_taker` | `markup` | …) mirroring `GeneratorCost`'s existing discrimination, resolved to an
instance by a factory. In-process callers may pass any structurally-conforming object; the jobs
surface accepts only the named configs. Rationale accepted: mypy checks the contract without
forcing inheritance, and nothing that crosses JSON is ever a callable. Rejected: an ABC (nominal
coupling for a one-method interface, and the repo has no other ABC to match); a plain callable (no
per-agent identity or parameters in the result, and the union reappears on the JSON side anyway,
just without the type checking).

**(b) Observation — own-node view only.** The observation carries: the LMP at the agent's own bus,
the agent's own cleared MW, its own true cost curve and capacity, **its own previous-round offer**,
and the round index. Nothing global. Verified sufficient for both shipping strategies: a markup
agent computes its own profit `(price − cost) × MW` and increments from its last offer, which is
exactly the pivotal walk-up AC-4 measures. Rejected: the full previous-round result (makes
`MarketNodalResult`'s shape part of the public strategy contract, so any later result change is a
breaking strategy-API change, and an agent can infer the merit order and short-circuit the game the
loop exists to play out); result-plus-network (a strategy could solve the LP in closed form, at
which point every iteration criterion is contingent on strategies choosing not to use what they
were handed).

**Binding on the design:** the previous-round offer is carried *in the observation*, not in the
strategy — that is what keeps "stateless best-response" (scope answer 2) true while still allowing
an incrementing agent. Round 0's observation has no prior price; its shape must make that explicit
(a distinct first-round form or an explicitly-optional price with a documented meaning), never a
silent zero. And per D1(a), the offer vector is a first-class output: the final round's offers are
read by an acceptance criterion, so they are a required member of the result, not a debug seam.

### A1 and A2 resolved before the Step-3 approval (orchestrator, 2026-08-28)

Both were written into the spec as at-risk assumptions. Both were checkable, so both were checked.
Reproduction scripts: `.bionic/tmp/m7-a1-update-rule-sweep.py`,
`.bionic/tmp/m7-a2-overlap-guard-probe.py`.

**A2 — resolved, and it found a live defect.** `opf.gen_cost_coeffs(net, arr)` already performs the
whole `GeneratorCost` union to `(cost_coeffs, pwl_costs)` mapping, including the all-zero-row
convention for a PWL generator. So "no `dc_opf` signature change" holds, and the design gets
sharper: M7 **generalises `gen_cost_coeffs` to take the cost source** rather than writing a
parallel assembler, which also makes AC-3(a)'s `array_equal` a comparison of two runs of one
function.

The probe then asked what happens when a caller other than `gen_cost_coeffs` builds the pair.
`_extract_and_validate` raises when a *load* index appears in both bid maps; there is **no mirror
guard on the generator side**. Measured on case14: a generator with a nonzero `cost_coeffs` row
*and* a `pwl_costs` entry clears **Optimal**, with that generator's dispatch driven from
**223.19 MW to 0.00 MW** and the objective **2409.70 above** the correct form. Five waves never hit
it because `gen_cost_coeffs` maintains the invariant by construction; M7 is the first wave whose
coefficients are assembled per round from strategy output. Now W1(c) / AC-1(c), landing in S1
before the loop exists.

**A1 — resolved, and the assumption was false as written.** Six duopoly configurations cleared
through this repo's own `dc_opf`, exact grid best response, three update rules:

| configuration | simultaneous | round-robin | damped (α=0.5) |
|---|---|---|---|
| symmetric 300/300, cost 20/20, step 0.5 | CYCLE period 2 | converged r=2, `[45.0, 20.0]`, $45.00 | no settlement in 24 |
| symmetric 300/300, cost 20/20, step 0.1 | CYCLE period 2 | converged r=2, `[45.0, 20.0]`, $45.00 | no settlement in 24 |
| asym cap 300/250, cost 20/20 | converged r=2 | converged r=2, `[47.5, 20.0]`, $47.50 | converged r=16 |
| asym cost 300/300, cost 20/25 | CYCLE period 2 | converged r=3, `[45.0, 20.0]`, $45.00 | converged r=19, `[20.0, 47.5]` |
| asym both 320/240, cost 18/26 | CYCLE period 2 | converged r=3, `[47.0, 18.0]`, $47.00 | converged r=21, `[18.0, 47.0]` |
| slack cap 500/500, cost 20/20 | CYCLE period 2 | converged r=2, `[35.0, 20.0]`, $35.00 | no settlement in 24 |

Simultaneous best response — the natural reading of scope answer 2 — **cycles in five of six**.
Round-robin converges in **six of six** in 2–3 rounds. Damping, the textbook fix, is worse on both
axes here: three of six, at 16–21 rounds, plus a tuning constant nothing calibrates.

W3 therefore specifies **round-robin updates in `NetworkArrays.gen_ids` order**, and the loop
**detects a repeated offer vector** and reports `termination_reason = "cycle"` — reporting a proved
period-2 cycle as "hit the iteration cap" would be exactly the confident-wrong-diagnosis failure
this epic has named in every wave. Determinism survives: the order is fixed and derived from the
network, so a run stays a pure function of `(network, strategies, tolerance)`.

**Two properties kept rather than designed away.** The fixed point is *asymmetric* — one agent
marks up to $45.00 while the other stays at its true cost of $20.00, the Bertrand-Edgeworth
outcome, which is a real result and not a bug. And it is **order-dependent**: on the
asymmetric-cost configuration round-robin settles at `[45.0, 20.0]` and the damped rule finds
`[20.0, 47.5]`. M7 reports the fixed point its own iteration reaches and claims no uniqueness —
already covered by Not Doing, now with a measurement behind it.

### A3 and A4 resolved, and A1's conclusion corrected (orchestrator, 2026-08-28)

Asked whether anything else needed fixing, the orchestrator kept checking. Three more findings,
two of them against its own previous message. Scripts: `.bionic/tmp/m7-a4-own-node-rules-probe.py`,
`m7-a4-two-point-climb.py`, `m7-a4-control-and-amplitude.py`.

**A1's conclusion was aimed at the wrong dynamics.** The A1 sweep measured *exact* best response —
an agent evaluating its own profit at every candidate offer. That requires clearing the market,
which D3b's own-node observation deliberately withholds. **M7's agents cannot compute it.** The
round-robin update rule adopted on that evidence is reverted; the sweep stands as a
characterisation of the game (cyclic, asymmetric, order-dependent), not as the update-rule
decision.

**A3 was over-cautious; AC-3(b) is exact.** Five independent `dc_opf` constructions on identical
input are **bitwise identical**. The research premise that two separate `highspy.Highs()`
constructions must diverge is false for identical input — M5's macOS one-ULP finding was a
structurally different LP (T=1 multiperiod builds extra rows). AC-3(b) asserts `array_equal`;
no tolerance enters the wave.

**A4 was false.** A one-round own-node observation tells an agent whether it is marginal but not
whether its last move *helped*. Measured on the 300/300 duopoly, the three rules computable from
it: "raise while at capacity" **cycles** (period 4 round-robin, period 2 simultaneous);
"chase the price" settles at `[40.0, 40.0]`, $40.00 — a markup gain of **$0.02/h**; "hold if
marginal" settles at `[40.5, 40.5]`, $40.50. None is a market outcome worth asserting.

**The fix, measured before proposing it:** the observation carries the agent's own **last two**
rounds of `(offer, price, MW)`. Still own-node, still no rival information, and the strategy holds
no state — the loop supplies the history. On a smooth residual demand the resulting climb reaches
the closed-form peak exactly:

| fixture | true-cost offers | climb end state | closed form |
|---|---|---|---|
| smooth pivotal 900 MW @ $20 | price $20.00, profit $0.06 | offer/price **$60.00**, 400.00 MW, profit **$15,999.98** (r=84 at step 0.5; r=44 at 1.0; r=24 at 2.0) | $60.00 / 400 MW / $16,000.00 |
| control: + 900 MW rival @ $22 | price $20.00, profit $0.06 | offer **$21.50**, gain **$1,177.50** — **13.6× smaller**, stopped by the rival, not by demand | — |
| duopoly 300/300 @ $20 | price $40.00, joint profit $11,999.96 | offers `[60.0, 60.0]`, $60.00, joint profit **$15,999.98**, r=84 | — |
| pivotal **with a fringe step** (100 MW @ $35) | — | stalls at **$9,497.52**, 22% short | $55.00 / 350 MW / $12,250.00 |

**Three consequences written into the spec.** (i) The climb is *local*: a competing unit between an
agent's cost and its peak creates a discontinuity the climb will not cross, so AC-4's fixture is
**smooth by construction and the spec says so** — a chosen fixture must not be allowed to look like
a general result. (ii) A fixed-step climber never comes to rest; it oscillates by exactly two steps
about its optimum (**measured amplitude 1.0 at step 0.5 on every fixture**), so termination is
classified by the oscillation's *amplitude* — inside `offer_tol` is convergence, outside it is a
cycle — which makes `offer_tol ≥ 2 × step` **derived**, closing D6's "calibrate at implementation".
(iii) AC-4's numbers are now the wave's own, reproduced through its own clearing, replacing the
research's 363.64 MW / $63.64 and 593.20 / 10,101.01 — which came from a different demand curve and
from an exact best response the shipped agent cannot compute.

**Ruling (user, 2026-08-28): "Smooth fixture, stated plainly."** Rejected: a residual-demand-
estimating strategy (puts a market model inside the agent — the rival reasoning D3b excluded — and
its correctness would need its own acceptance row); weakening AC-4 to "the markup is real and
stops" (robust to everything and close to unfalsifiable, the vacuity class this epic has hit three
times).
