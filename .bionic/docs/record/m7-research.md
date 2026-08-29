# M7 research — `market.agents`

Researcher pass, Step 1/2 of wave M7 (`build · audited · wave`), epic `01-foundation`. Read-only on
the repo at `epic/01-foundation` head `6ca9dcc`.

Every claim below carries the command/read that proves it, or is labelled `unverified`.

**Scope note (update after the first pass):** three Step-1 answers landed from the user mid-research
and close §1, §3, and half of §5 outright — those sections below are rewritten as worked derivations
against the decided design, not presented options. §2, §6, §7, §8, §9 are unchanged from the first
pass. The decisions: (1) offers reach the engine as an overlay — a per-iteration generator-id → cost
map handed alongside the network; `Network`/`Scenario` stay immutable. (2) "Learn" is stateless
best-response iteration to a fixed point — no per-agent memory, no seed. (3) "The cap" is the
existing bid-side willingness to pay (`Load.bid`) — no new model field.

---

## §1 The overlay mechanism, concretely

**Where a caller-supplied override enters, precisely.** `market/nodal.py:112` reads
`cost_coeffs, pwl_costs = gen_cost_coeffs(net, arr)` and hands the result straight to `dc_opf`
three lines later (`nodal.py:114-121`). Because `Scenario`/`Network` must stay untouched, the
overlay cannot enter through `market.nodal` at all (`solve_nodal`'s own signature has no room for
per-round data, and widening it would touch an oracle-tested wrapper for a caller that isn't
`market.nodal`). **`market.agents` needs its own runner** (a new `market/agents.py`), built by
copying `solve_nodal`'s own construction (`net = scenario.network; arr =
NetworkArrays.from_network(net); cost_coeffs, pwl_costs = gen_cost_coeffs(net, arr)`,
`nodal.py:110-113`) and splicing the current round's offer overlay in between that call and the
`dc_opf` call it feeds (`nodal.py:114-121`).

**What the overlay's type should be.** `dict[str, GeneratorCost]` — id-keyed, reusing
`GeneratorCost = Annotated[PolynomialCost | PiecewiseCost, Field(discriminator="kind")]` verbatim
(`entities.py:87`), the same type `Generator.cost` already carries. This is the ADR-006 reuse
discipline applied one level down: a `Strategy.bid()` output composes directly with the existing
cost model instead of inventing a parallel "Offer" type, and a strategy that wants a PWL offer
(not just a polynomial markup) gets it for free.

**Whether `dc_opf`/`solve_nodal` need a new parameter — confirmed by direct read: no.** `dc_opf`'s
signature (`dc_opf.py:682-688`) already takes `cost_coeffs: FloatArray` and `pwl_costs: Mapping |
None` as bare, disconnected arguments — it has no reference back to `Network`/`Generator` at all,
so it accepts an overlay-built array exactly as readily as `gen_cost_coeffs`'s own output.
`market.agents` calls `dc_opf` **directly**, not through `solve_nodal`, so `market/nodal.py` gains
zero new lines and `market.nodal`'s behaviour is trivially, exactly unchanged.

**The smallest change this actually requires.** `gen_cost_coeffs`'s per-generator row-conversion
logic (`opf/__init__.py:90-103` — the branch that right-aligns polynomial coefficients into
`[c2, c1, c0]` or drops a piecewise curve's points into the PWL map) is currently inline in its
one loop, with no standalone function a second caller could reuse. Converting one `GeneratorCost`
into a `(c2, c1, c0)` row (or a PWL points list) is exactly what an overlay needs to do **per
offered generator**, each round — reusing it, rather than writing a second copy of that
conversion, is the ADR-007/008 lesson applied at agent-granularity (the same lesson that motivated
extracting `_extract_and_validate` in the first place). So: factor that seven-line branch out of
`gen_cost_coeffs`'s loop into a small private helper (`_cost_row(cost: GeneratorCost | None) ->
...`), a pure, behaviour-preserving refactor of `gen_cost_coeffs` itself — `gen_cost_coeffs`'s own
observable output is unchanged, provable the S1 way (unmodified suite green against an overlaid
tree touching exactly `opf/__init__.py`). `market/agents.py` then calls `gen_cost_coeffs(net,
arr)` once per solve for the **true-cost baseline** (needed for settlement and for any strategy's
observation of its own cost), and calls the extracted helper once per **offered** generator each
round to build that round's overlay array — starting from a copy of the baseline array, never the
baseline itself, since the baseline is reused as ground truth every round.

**Net effect:** no signature changes anywhere in `opf/dc_opf.py` or `market/nodal.py`; one small
private-helper extraction inside `opf/__init__.py`; the actual overlay machinery is new code
living entirely in `market/agents.py`. `market.nodal`'s behaviour when no overlay is given is not
merely "preserved" — it is untouched, because no overlay-aware code path exists inside it at all.

---

## §2 The `Strategy` protocol surface

*(unchanged from the first pass.)*

What `bid(observation) -> offers` needs to see, for the two named reference strategies (price-
taker: offer = true marginal cost; pivotal-supplier markup: offer = cost scaled by a markup
factor): both need **own cost** (`Generator.cost`/`cost_coeffs` row) and **own capacity**
(`p_min_mw`/`p_max_mw`, `entities.py:131-134`) at minimum. Under the now-decided best-response
loop (§3/§4), a reactive markup strategy additionally needs **last round's cleared price at its
own bus** to compute its next offer — the loop is stateless, so this is the one piece of feedback
that closes it.

Three concrete shapes (`typing.Protocol`, ABC, plain `Callable`), trade-offs, and the JSON-round-
trip answer common to all three (the *configuration* serialises via a `StrategyConfig` pydantic
discriminated union — `Annotated[PriceTakerConfig | PivotalMarkupConfig, Field(discriminator=
"kind")]`, mirroring `GeneratorCost`'s own shape at `entities.py:87` — a registry maps config to
the actual `bid()`-shaped object at solve time, mirroring `jobs.registry.KINDS`/`register()`,
`registry.py:97-256`) are unchanged from the first pass and stand as written there.

---

## §3 The fixed-point loop's own mechanics

**Decided: no per-agent memory, no seed.** Every round, each strategic agent's `bid()` is a pure
function of `(own cost/capacity, last round's public price/dispatch)` — the loop holds no state
beyond the sequence of rounds itself. This makes `market.agents` fully deterministic given a
deterministic tie-break rule, with **zero** new discipline needed around randomness: this repo has
no existing RNG-seeding convention anywhere market-facing (confirmed: no `market.*`/`opf.*` module
draws a random number), and the decided design keeps it that way.

**The loop, mechanically:**

1. Round 0: every strategy observes only its own cost/capacity (no prior round exists) and offers
   — for the price-taker, true cost; for the markup strategy, some initial guess (a natural choice:
   round 0's markup strategy also offers true cost, since it has no price signal yet — the loop's
   first clearing is effectively a price-taking clearing for everyone, and the markup only begins
   reacting from round 1).
2. Clear the LP (`dc_opf`, §1's overlay) against that round's offer array; read the LMP at each
   agent's own bus.
3. Settle that round (§6): per-agent cleared quantity × LMP.
4. Every strategic agent recomputes its offer as a function of the LMP just observed at its own
   bus (and its own cost/capacity, held fixed across rounds).
5. Check termination (§4). If not terminated, go to 2 with the new offers.

**Why this satisfies the two named ACs without needing anything more.** "Price-takers reproduce
the competitive result" needs no iteration at all — the welfare LP is identical every round
regardless of how many rounds run, since a price-taker's offer never depends on the price it
observes. "Pivotal supplier hits the cap": worked through with real numbers in §5(b) below, and it
turns out the loop **converges in one non-trivial round** for both the pivotal and the paired
cases, for a structural reason given in §4 — not because the fixed-point machinery was skipped,
but because the specific games these two ACs exercise have no cross-agent feedback to iterate on.

---

## §4 Termination and determinism — the real answer

**The standard result for best-response dynamics on this problem class.** Pure best-response
iteration over a game with **two or more simultaneously reactive** players is not guaranteed to
converge in general — the textbook Cournot tâtonnement result is that convergence depends on the
product of the players' reaction-function slopes (converges when that product's magnitude is
below 1, cycles or diverges otherwise), and the supply-function-equilibrium literature (§8)
characterises its equilibria analytically precisely because no best-response process is known to
converge to them in general.

**But the two named ACs do not exercise that regime, and this is worth stating precisely rather
than glossing over.** A best-response iteration only has something to cycle *on* when at least two
agents are simultaneously reacting to each other's last move. In both of §5(b)'s constructions —
the single pivotal generator, and the pivotal generator paired with one **truthful** competitor —
there is exactly **one** strategic (reactive) agent; every other participant (the competing
generator, the elastic load) is not running a `bid()` that reacts to price. A lone reactive agent's
best response depends only on the *residual* demand curve it faces, which is fixed by the other
(non-reactive) participants' fixed behaviour and does not change from round to round — so its
offer in round 1 already equals its offer in round 2, round 3, .... **The loop converges after
exactly one non-trivial round for both of the wave's own acceptance tests**, and the standard
cycling risk is a real property of the *general* `Strategy` protocol (which must support ≥ 2
simultaneously reactive agents) without being something either named AC exercises. This matters
for scoping M7's own test suite: a test that only exercises the two named ACs will never see a
cycling loop, and a *separate*, deliberately-constructed ≥ 2-reactive-agent fixture is needed to
exercise §4's termination machinery at all — worth flagging as a real coverage gap the two named
ACs cannot fill.

**Termination test.** Check convergence on the **offer vector** round-over-round — offers are the
loop's actual state variable (a fixed point is properly defined on the strategy space, "no agent
wants to change its offer given the others'"), and price convergence is a derived, secondary
diagnostic worth reporting alongside it (report both; a price-stable-but-offer-still-moving state
is possible if the clearing map is non-injective on some fixture, and a caller mostly cares about
price/dispatch stability — reporting both, rather than testing only one, is the cheap way to catch
that edge case rather than assume it away).

**Tolerance and cap — mechanism decided, exact numbers need empirical calibration.** A relative
tolerance on each agent's own offered marginal cost (order 1e-6 relative, matching a typical LP
optimality tolerance) is the right *shape*; the exact number should be pinned the way ADR-009's own
sup-norm bound was — "measured against a fixture," not chosen a priori (`unverified` — no M7
fixture exists yet to measure against). A hard iteration cap independent of the tolerance check is
needed regardless, in the same spirit as `MAX_PERIODS`/`MAX_CORRIDORS` bounding array size
(`model/scenario.py:9-16`, `market/zonal.py:139-155`) — here bounding round count so a cycling
≥ 2-agent game always terminates; a starting value in the low hundreds is generous relative to how
fast best-response tâtonnement typically settles when it does settle, but this too wants empirical
tuning during implementation, not a number fixed by research alone.

**What the code reports on non-convergence.** Never raise — this repo's universal convention,
stated identically in every `solve_*`: "Never raises for an infeasible or unbounded LP/QP —
reported through `status`/`message`" (`market/nodal.py:101-106`, `market/multiperiod.py:253-259`,
`market/zonal.py:568-573`). `MarketAgentsResult` needs **two separate, non-conflatable** signals,
not one: (a) `status`, continuing to report the underlying LP solver status for the final round
(`"Optimal"`/`"Infeasible"`/etc., exactly as every other market result), and (b) a distinct
`converged: bool` (or `termination_reason: Literal["converged", "max_iterations"]`) reporting
whether the *loop* itself stabilised — these are orthogonal failure modes (a perfectly-solved LP
every round, in a loop that still hasn't stopped moving, vs. a converged loop whose last round
happened to be infeasible) and collapsing them into one field would repeat the exact mistake
ADR-009/M6 had to walk back once already (keeping welfare/generation-cost/settlement as separate,
non-conflatable fields rather than one overloaded number). `message` carries the loop-level
explanation when `converged=False`, mirroring `MarketZonalResult.message`'s "naming the stage"
convention (`results/zonal.py:159-163`) — here naming the final offer/price delta rather than a
solve stage.

---

## §5 The two acceptance tests, derived

### (a) Price-takers reproduce the competitive result — corrected from the first pass

The first pass argued bit-identity was reachable "if implemented as a literal call-through."
Working through §1's now-decided design shows that claim does not survive contact with the actual
call path, and the honest correction matters enough to state plainly.

`market.agents` calls `dc_opf` **directly** (§1) — it does not, and structurally cannot without a
special-cased short-circuit, call `solve_nodal` itself. So even in the cleanest possible
all-price-taker round (offer array built to be bit-identical to `gen_cost_coeffs`'s own output, fed
through the identical `load_bid_coeffs`/`dc_opf(arr, cost_coeffs, OpfDcOptions(), ...)` call
`solve_nodal` makes), `market.agents`'s LP solve and `market.nodal`'s LP solve are **two separate
`highspy.Highs()` constructions and two separate `.run()` calls** on numerically identical input —
not the *same* call, unlike `solve_multiperiod`'s own T=1 reduction (`multiperiod.py:29-33`),
which reduces to literally one evaluation of `dc_opf`'s own expressions, not two solves of the
same problem. This is a materially weaker situation than that precedent, and per the M6 lesson
(`4cfd1d7`, "AC-4's explicit-Period route asserts tolerance, not bit-equality") — which was about
cross-*platform* solver variation, not within-process repeat solves — even two solves of a
bit-identical LP within the *same* process, same HiGHS build, are not something this session found
a documented guarantee for: `unverified` whether HiGHS's simplex/interior-point path is configured
deterministically here (the only option this repo sets anywhere read this session is
`h.setOptionValue("output_flag", False)` — no thread-count or algorithm pin was found), so two
repeat solves of the identical model are *plausible* to be bit-identical but not provably
guaranteed by anything read this session.

**Honest answer: equal to tolerance, not bit-identical, under the decided overlay design as it
naturally falls out of §1.** The one way to reach a genuine bit-identical claim is a deliberate
design choice this session flags as available but not automatic: detect up front (before any round
runs, from the strategy configs alone — "every strategy is a price-taker" is knowable without
executing the loop) that the whole horizon is price-taking, and **short-circuit to calling
`solve_nodal(scenario)` itself** for that case, exactly mirroring `solve_multiperiod`'s own T=1
trick. That is a single call, not two, and would give the same class of exactness claim
`solve_multiperiod` already carries — but it is a deliberate reduction someone has to build, not a
free consequence of the overlay architecture.

### (b) Pivotal supplier hits the cap — worked, numerically verified

**"Hits the cap," made precise.** At *any* interior LP optimum, the clearing price already equals
the bid curve's own marginal value at the served quantity — that is just the welfare LP's
optimality condition, true for every offer, not specific to a profit-maximising one. So "hits the
cap" cannot mean "reaches some special price"; it means the pivotal generator's *profit-maximising*
markup is itself bounded by the bid curve's declining marginal value — the generator cannot
profitably push price without limit, because past some point further withholding costs it more in
lost sales than it gains in higher price. That stopping point is derivable exactly, and this
session verified the derivation numerically (`uv run --no-sync python`, scipy `brentq`/
`minimize_scalar`/`minimize`, `unverified` only in the sense that this ran independent hand
algebra against scipy, not this repo's own `dc_opf`/HiGHS — the LP being modelled is small and
linear-in-the-relevant-sense enough that this is a faithful stand-in, but a build-time S-slice
should still confirm these numbers against the actual solver).

**Construction, with an elastic bid load present (as required).** One bus, one generator `G1`
(true cost `c2=0.01, c1=20, c0=0` → marginal cost `0.02p + 20`), one elastic load with a concave
quadratic bid `value(p) = 100p - 0.05p²` → marginal value (inverse demand) `P(p) = 100 - 0.1p`. No
other generator: `G1` is trivially, maximally pivotal (residual supply from everyone else is zero,
the degenerate case of the RSI test, §8).

- **Competitive (truthful) point:** solve `0.02p + 20 = 100 - 0.1p` → **p\* = 666.67 MW,
  price = 33.33 $/MWh, G1 profit = 4,444.44 $/h**.
- **G1's profit-maximising markup point** (maximise true profit `price(p)·p − true_cost(p)` over
  `p`, not merely clear at offered=bid): **p = 363.64 MW, price = 63.64 $/MWh, G1 profit =
  14,545.45 $/h — markup gain 10,101.01 $/h.**
- **The distinction team-lead's framing pointed at, made precise and numerically located at two
  different thresholds, not one.** Raw *revenue* `P(p)·p` peaks at the demand curve's own
  unit-elastic point — verified at **p = 500 MW** — a *different*, less restrictive point than the
  profit optimum. Withholding from 666.67 MW down to 500 MW **raises revenue** (the standard
  monopoly-restricts-output result); withholding further, from 500 MW down to the true optimum at
  363.64 MW, **lowers revenue but keeps raising profit**, because the cost saved from producing
  less outweighs the revenue given up; past 363.64 MW, further withholding lowers both. **363.64
  MW — not 500 MW — is "the cap": the point past which pushing the offer higher curtails demand
  without any further gain, revenue or profit.** A rational profit-maximising markup strategy
  should target the 363.64 MW point, not the (less restrictive) revenue-maximising one.

**The paired, non-pivotal control — with a real, verified, non-trivial number, not a near-zero
one, and a correction to the premise as stated.** Add a second generator `G2` (true cost
`c2=0.01, c1=25`, `p_max = 500 MW`) that clears truthfully in this paired scenario, alongside the
same `G1`/demand:

- **Both truthful:** `p1 = 477.27 MW, p2 = 227.27 MW, price = 29.55 $/MWh, G1 profit = 2,277.89
  $/h.`
- **G1's best response** (its own optimal markup against the *residual* demand curve left after
  `G2`'s truthful supply is netted out — derived in closed form, then confirmed by an independent
  coarse grid search and a local Nelder-Mead refinement from the closed-form point, both landing on
  the identical optimum to four decimal places): **p1 = 328.125 MW, price = 32.03 $/MWh, G1 profit
  = 2,871.09 $/h — markup gain 593.20 $/h.**
- **Ratio: the pivotal case's markup gain (10,101.01 $/h) is ~17.0× the paired case's (593.20
  $/h)** — a real, sizeable, unambiguously non-zero difference, satisfying the explicit "not a
  near-zero" requirement.
- **The premise needs one correction: a second competitor does not make the markup
  *unprofitable* — it makes it substantially, measurably *less* profitable.** G1's best response
  in the paired case is still a genuine, nonzero act of withholding (593.20 $/h gained over
  truthful bidding), not a reversion to price-taking. This is the economically correct and
  expected result for a two-generator Cournot-style game — a single competitor essentially never
  fully eliminates market power in this class of model; it takes either many more competitors or
  one whose capacity dwarfs demand to drive a pivotal generator's best response all the way back
  to truthful. If the design interview specifically wants a case where the markup reverts to
  (near-)zero, that is a *different*, additional construction (a much larger `G2` capacity, driving
  `G1`'s residual demand toward perfectly elastic) — buildable on request, but it is not what "add
  one competitor" produces, and asserting otherwise in a committed test would be asserting a false
  number.

Verification commands run this session (`uv run --no-sync python` against throwaway scratch
scripts, scipy `brentq`/`minimize_scalar`/`minimize`): the single-generator case's closed-form
optimum, the two-generator case's closed-form residual-demand optimum, an independent 200×80 grid
search over the two-generator offer space, and a Nelder-Mead local refinement from the closed-form
point — all four agree to at least four significant figures on both scenarios' optimal points and
profits.

---

## §6 Result shape

*(unchanged from the first pass — reproduced here for continuity.)*

Per-iteration history vs. final-only is conditional on the now-decided iterating design: a
`list[MarketAgentsRoundResult]` mirroring `MarketMultiperiodResult.periods:
list[MarketPeriodResult]` (`results/multiperiod.py:164-166`) is this codebase's own precedent for
"a list of repeated clearing rounds." Given §4's finding that the two named ACs converge in one
non-trivial round, the practical history length for the wave's own tests will be short (1-2
entries), but the *shape* still needs to support the general ≥ 2-agent case, which can run many
rounds before hitting the cap.

Per-agent rows would minimally carry `id`, `bus`, an offer summary, `p_mw` (cleared), `bound_dual`,
and a settlement figure — noting `total_generator_receipts = sum(LMP(bus)*p_mw)` is currently
computed inline, separately, in `market/nodal.py:189`, `market/multiperiod.py:222`, and
`market/zonal.py`'s composition; a fourth inline copy in `market/agents.py` repeats a pattern
ADR-008 already flagged once.

**Binding requirement — confirmed by direct read:** `MarketNodalResult` (`results/market.py:39-74`)
has no `branches` field; `MarketZonalResult` (`results/zonal.py:142-243,196-201`) does. Cost to
close: one list comprehension mirroring `market/zonal.py:684-693`, reusing `OpfBranchFlowResult`
verbatim.

**Compose vs. mirror:** `MarketPeriodResult` (`results/multiperiod.py:97-105`) is this codebase's
own precedent, and it mirrors (duplicates the field set as top-level fields) rather than composing
(nesting a `MarketNodalResult`). No precedent anywhere in this codebase for "compose."

**Naming trap, sharper for M7 than for M6:** `continuation-m6.md`'s own words — "M7's result types
should pick one meaning for the name" — for the bare field `generators`. Under the now-decided
iterating design, a per-round result plausibly has both an "offered/scheduled" layer and a
"settled" layer; reusing `generators` for both would be an **intra-type** ambiguity, sharper than
M6's cross-type one.

**Conventions confirmed universal on every result/row model read this session:**
`ConfigDict(extra="forbid", frozen=True, allow_inf_nan=False)` — `results/market.py:28,48`;
`results/zonal.py:71,152`; `results/multiperiod.py:72,107,152`; `results/opf.py:17,61`.

---

## §7 The Hessian third copy (M6 carry-over #1, wave AC-1)

*(unchanged from the first pass.)*

**Control** (ADR-008/009's own numbers): preamble unification measured 54/68-69 lines identical
(ratio 0.788) before, 55 identical lines → 12 after, across four callers.

**My own measurement**, same method (`difflib.SequenceMatcher`), run directly this session on the
three actual diagonal-Hessian-assembly blocks:

| Pair | Lines (A / B) | `ratio()` | Matched lines |
|---|---|---|---|
| `dc_opf.py:744-759` vs `zonal.py:388-402` | 16 / 15 | **0.903** | 14 |
| `dc_opf.py:744-759` vs `multiperiod.py:429-446` | 16 / 18 | **0.588** | 10 |
| `multiperiod.py:429-446` vs `zonal.py:388-402` | 18 / 15 | 0.485 | 8 |

`dc_opf` vs `zonal`: one purely stylistic one-line diff, otherwise byte-identical. `dc_opf` vs
`multiperiod`: the whole gap is the T-loop `multiperiod` must add plus a rename
(`n_dispatch`→`n_dispatch_total`); the algorithm (zero a diagonal, `flatnonzero`, build a
`HighsHessian` in `kTriangular` format, `passHessian`) is identical in shape and statement order in
all three. Confirms ADR-009 consequence 5 with measurement rather than assertion; confirms (read
directly, `redispatch.py:227-238,321-371`) that `redispatch`'s 2×2-block-coupling Hessian is
structurally different and should stay a non-caller.

**Proposed helper:** an 8-10-line "diagonal vector in, `passHessian` out" function beside
`_epigraph_rows`/`_hypograph_rows`/`_add_rows` in `dc_opf.py`, taking a pre-built `hess_diag`
array; each caller keeps its own few lines of `hess_diag` assembly (2 lines for `dc_opf`/`zonal`,
a 3-line loop for `multiperiod`) since those genuinely differ.

**Behaviour-preservation proof M7's S1 must produce**, mirroring the two precedents already in
this repo's history: (1) `git archive` the base, overlay only the three touched files, run the
full base suite unmodified and show it green; (2) a sabotage proof (sign-flip/zero the shared
helper's Hessian value, show tests redden across all three callers' test files, mirroring ADR-008's
"18 tests red across five files"); (3) confirmed `getNumRow()` tripwires exist at
`multiperiod.py:635`/`zonal.py:487` for row counts, but `unverified` whether an analogous
dimension/nnz tripwire exists for the Hessian specifically — none was found; S1 should add one if
none exists.

---

## §8 Prior art

*(unchanged from the first pass.)*

AMES (Tesfatsion, Iowa State) — open-source agent-based wholesale power market testbed;
reinforcement-learning bidding agents on an ISO-style LMP day-ahead design. PowerTAC — the epic's
own cited reference (`epic.spec.md:97`). EMCAS — named in this task's prompt but not in the epic's
own citation; flagged, not reconciled, `unverified`. Pivotal supplier, precisely, from the
market-power-screening literature: RSI < 1 (residual supply insufficient without that supplier).
Markup, precisely, from the SFE literature (Klemperer-Meyer; Green-Newbery): a steeper/higher
supply-function submission exploiting inelastic residual demand — the exact mechanism §5(b)'s
worked example reproduces in miniature and now verifies numerically.

Sources: [AMES Test Bed](http://www2.econ.iastate.edu/tesfatsi/aelect.htm) ·
[AMES Market Package](https://faculty.sites.iastate.edu/tesfatsi/archive/tesfatsi/AMESMarketHome.htm) ·
[CAISO Residual Demand](https://www.caiso.com/Documents/ResidualDemand.pdf) ·
[CAISO Residual Supply Index](https://www.caiso.com/Documents/PredictingMarketPowerUsingResidualSupplyIndex_AnjaliSheffrin_FERCMarketMonitoringWorkshop_December3-4_2002.pdf) ·
[Pivotal Suppliers and Market Power in Experimental SFE Competition](https://www1feb-uva.nl/creed/pdffiles/SFE.pdf)

---

## §9 Carry-overs from M6 that land on M7

*(unchanged from the first pass.)*

**In scope:** #1 (Hessian, §7), #3 (methodological — don't let a loop-level exactness row stand in
for a per-round one, now sharper given §4's finding that the two named ACs never actually exercise
the loop's iterating machinery), #6 (confirmed architectural, not a gap: `grep -rn "in_service"
src/mambo_power/market/ src/mambo_power/opf/` returns zero hits; filtering happens upstream in
`NetworkArrays.from_network`, `numerics/arrays.py:123,139,173,183,187,207`), #11 (naming, §6),
#12 (`branches`, §6). **Confirmed still defused, #8:** `pf.telepathy` is still the fictional
unknown-kind demo at all three sites (`docs/manual/jobs.md:242,250,267`,
`tests/unit/test_jobs.py:329,335,337,339`, `examples/04_jobs_api.py:53,55`, grepped directly this
session) — registering `market.agents` collides with none of them, but **will** make
`docs/manual/jobs.md:267`'s committed `UNKNOWN_KIND` transcript stale (it hardcodes the current
7-kind sorted list; `market.agents` becomes an 8th) — a one-line doc fix, previously unflagged in
`continuation-m6.md`, worth handing to whoever does the registration. **Out of scope:** #2, #4, #9,
#10 (zonal-specific or docs-debt, unrelated to `market.agents`), #5, #7 (opportunistic only), #13
(orchestration process note, not a design carry-over — though the name collision between "agents"
the wave's subject and "agents" the multi-agent dev process makes it worth the orchestrator
repeating anyway).

---

## Summary for the Step-2 design interview

The three decisions closed one strategic fork each and one methodological finding fell out of
working them through:

- **§1 is now a build task, not a decision.** Overlay via a new `market/agents.py` calling
  `dc_opf` directly; one small private-helper extraction inside `opf/__init__.py`
  (`gen_cost_coeffs`'s row-conversion logic); zero changes to `market/nodal.py` or `dc_opf`'s
  signature.
- **§5(a) needed a correction, not just a derivation.** The decided overlay design cannot reach
  bit-identity for free — it requires two separate HiGHS solves, not one, unlike
  `solve_multiperiod`'s T=1 precedent. Bit-identity is reachable only via a deliberate
  short-circuit to `solve_nodal` itself for the all-price-taker case; absent that, the honest claim
  is tolerance, matching M6's own `4cfd1d7` lesson.
- **§5(b) is now two fully worked, numerically-verified fixtures with real numbers**, ready to
  hand to a build slice: pivotal case (10,101.01 $/h markup gain), paired non-pivotal case (593.20
  $/h) — a verified 17.0× difference, and an explicit correction that the paired case demonstrates
  *reduced*, not *eliminated*, market power (the premise "makes the markup unprofitable" does not
  hold as stated; the honest, verified finding — real, nonzero, ~17× smaller — is what should be
  asserted in a test instead).
- **§4 turned up a real coverage gap worth flagging to the design interview directly:** neither
  named AC exercises more than one reactive agent, so neither exercises the fixed-point loop's
  actual termination machinery (multi-agent cycling, the tolerance check, the iteration cap). If
  M7's test suite is scoped only to the two named ACs, `status`/`converged`/the cap will ship
  unexercised by any acceptance test — a deliberate, separate ≥ 2-reactive-agent fixture is needed
  to cover them at all.

One binding requirement carried in from M6 (§6/§9): close `MarketNodalResult`'s missing `branches`
field, symmetric with `MarketZonalResult`. One binding naming constraint: don't repeat the
`sold`-vs-`delivered` ambiguity, now with the added risk of it landing inside one result type. One
confirmed mechanical fact for whoever does the registration: `docs/manual/jobs.md:267` needs a
one-line update the day `market.agents` registers.
