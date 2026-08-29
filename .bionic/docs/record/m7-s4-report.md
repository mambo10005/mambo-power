# M7 S4 — the fixed-point loop — slice report

Commit: `74a0532` — `feat(m7/s4): the fixed-point loop — offer overlay, simultaneous updates,
amplitude-classified termination`.
Branch `wave/07-agents`, worktree `C:\Claude Projects\mambo-power-m7`.
Base at dispatch: `a22922d`. Head at the acceptance run: `74a0532`, which sits on top of S2's
`20ba1e7` and S8's `9ae56ed`.

Every claim below carries the command that proves it and that command's output, or the literal
label **unverified**.

---

## The finding: AC-5(i) was unreachable, and the defect was in a sibling slice

Reported to the orchestrator the moment it was diagnosed, before any further work.

`MarkupStrategy.offer` reversed the climb's direction on a strict `profit_prev < profit_2ago`
with no tie tolerance. The Step-2 reference probe (`.bionic/tmp/m7-a4-two-point-climb.py:79`)
used `if profit_prev[i] < profit_prev2[i] - 1e-9`; S2's port dropped the `- 1e-9`.

On the AC-5 duopoly both 300 MW agents sit **at capacity** while demand sets the price, so
consecutive rounds are economically identical — the price is exactly $40.00 (marginal value
`100 - 0.1 * 600`) in both. What the agent observes is the LP's balance dual, which differs by
**one ULP** between the two rounds. Traced through the shipped loop:

```
  r=2 prev(off=20.5, lmp=39.99993999999998, mw=300.0, profit=5999.9819999999945)
      2ago=(20.0,   '39.99993999999999',   '300.0', '5999.981999999996')     -> 20.0
```

1.6e-12 of solver noise, amplified from 1 ULP by ×300 MW, flipped the direction at round 2. The
loop then correctly detected a genuine period-4 state repeat at iteration 4 with amplitude 0.5,
inside `offer_tol`, and reported **`converged=True` at offers `[20.5, 20.5]`, joint profit
$11,999.96** — the true-cost outcome presented as a settled strategic equilibrium. The loop was
behaving as specified; it was faithfully reporting a strategy that turned around for no economic
reason.

Three candidate rules were measured against all three fixtures, with **nothing edited** — the
candidates were injected through `solve_agents`' in-process `strategies=` seam:

```
shipped: pp < tp              | duopoly        | it=4    converged  offers=[20.5, 20.5] price=39.9999 profit=11999.96
shipped: pp < tp              | smooth pivotal | it=84   converged  offers=[60.0]       price=60.0000 profit=15999.98
shipped: pp < tp              | control        | it=7    converged  offers=[21.5]       price=21.5001 profit=1177.56

probe:   pp < tp - 1e-9       | duopoly        | it=84   converged  offers=[60.0, 60.0] price=60.0000 profit=15999.98
probe:   pp < tp - 1e-9       | smooth pivotal | it=84   converged  offers=[60.0]       price=60.0000 profit=15999.98
probe:   pp < tp - 1e-9       | control        | it=7    converged  offers=[21.5]       price=21.5001 profit=1177.56

relative: pp < tp and not isclose(pp, tp, rel_tol=1e-9, abs_tol=1e-9)
                              | duopoly        | it=84   converged  offers=[60.0, 60.0] price=60.0000 profit=15999.98
                              | smooth pivotal | it=84   converged  offers=[60.0]       price=60.0000 profit=15999.98
                              | control        | it=7    converged  offers=[21.5]       price=21.5001 profit=1177.56
```

Either tolerance restores AC-5(i) exactly and **neither moves AC-4's two numbers**, so the change
lands on exactly the case that needs it. The relative form was recommended over the probe's
absolute `1e-9` because profit here is ~$6,000 but is millions on a large network, and an absolute
epsilon that is a tie-breaker at one scale is a no-op at another. **S2 implemented the relative
form** at `20ba1e7`; this slice did not edit `market/strategy.py`.

The pattern worth carrying: the defect needed a *market* to surface, and S2's module has none. Its
24 tests and 6-point sabotage sweep were thorough about everything the strategy can be asked in
isolation. This is the wave's third instance of a layer finding what the layer below could not
have.

### A process failure, caught, that cost nothing this time

Between the run in which my suite passed and the `git diff` ninety seconds later, `strategy.py`
flipped to a sabotaged state — S2 was running its sweep **in the shared working directory I was
measuring in**. No number was misreported (I stopped and held), but no number taken in that window
would have been trustworthy in either direction. This is A14/A15 recurring: concurrency and
measurement do not share a working directory. Every number in this report was taken after `git
status --short` showed `src/mambo_power/market/strategy.py` clean and `git log` showed S2's fix
committed at `20ba1e7`.

---

## AC-2 — the overlay never mutates the network, and the run was not vacuous

Both clauses are asserted **on the same run**, in one test, deliberately: a byte-identity taken
from a run in which nothing happened is vacuous, so the positive control has to come from the run
being checked.

```
$ uv run --no-sync pytest tests/unit/test_market_agents.py::test_ac2_the_network_is_byte_identical_across_a_run_that_really_marked_up -q
1 passed in 1.79s
```

What it asserts, in order: the run really marked up (`[_level(row.offer) for row in result.offers]
== [60.0]` against a true cost of `20.0`); `scenario.model_dump_json().encode()` and
`net.model_dump_json().encode()` are unchanged **byte for byte**; every `Generator.cost` is
unchanged as JSON; and then, on that same run, the coefficient arrays handed to the array builder
— captured by monkeypatching `mambo_power.market.agents.dc_opf` — are `len(handed) ==
result.iterations + 1`, with `handed[0]` `array_equal` to the true coefficients (round 0 offers
true cost, by the climb's own rule) and `handed[-1]` **not** `array_equal` to them,
`handed[-1][strategic][1] == 60.0` against `true_coeffs[strategic][1] == 20.0`.

Power proof: sabotage **S1** below makes `gen_cost_coeffs` ignore its cost source, which is the
defect in the specific quantity AC-2 names — what the array builder is handed — and this test goes
red.

---

## AC-5 — the loop's own termination

Exact figures, `uv run --no-sync python <scratch>/ac_numbers.py` at head `74a0532`:

```
AC-5(i)   status=Optimal converged=True reason=converged iterations=84
          offers=[60.0, 60.0]  price=60.00001999997
          joint profit=15999.984000011997  dispatch=[199.99970000729422, 199.9996999936057]
          markups=[7999.988000291768, 7999.987999744229]
AC-5(i)b  true-cost joint profit=11999.963999999993 price=39.99993999999999 iterations=2 converged=True
AC-5(ii)cap status=Optimal converged=False reason=iteration_cap iterations=83 offer=59.5
AC-5(ii)cycle status=Optimal converged=False reason=cycle iterations=12 offer=25.0
```

**Every Step-2 number reproduces.** 84 iterations, `[60.0, 60.0]`, $60.00, joint profit
$15,999.98 against $11,999.96 at true cost, settled amplitude 1.0. No number was adjusted and no
tolerance was widened.

### (i) Convergence is real

```
$ uv run --no-sync pytest tests/unit/test_market_agents.py -q -k "ac5i"
3 passed in 4.28s
```

- `iterations > 1` is asserted as its own clause before `iterations == 84`: a fixed point reached
  in one round would make the loop unnecessary, and a one-round run could still report every other
  figure correctly.
- The **amplitude** clause is measured on the offers the real strategies really made, recorded
  round by round through a `_Recorder` wrapper inside the real run — not recomputed, which would
  assert the test's own arithmetic instead of the loop's. `max(tail) - min(tail) == 1.0` exactly,
  with **no tolerance**, over the last `AC5_PERIOD = 4` rounds, and `levels[-1] == levels[-5]` so
  the tail is asserted to be genuinely periodic rather than merely narrow. `1.0 == 2 * STEP` is
  asserted as the derivation A9 states, not as a coincidence.
- `status` is asserted independently of `converged` in every clause: `result.status == "Optimal"`
  and `result.converged is True` are separate assertions with separate meanings, and the same
  pairing appears in all three AC-5(ii) tests, where `status` stays `Optimal` while `converged` is
  `False`.
- Price and profit carry `PRICE_ABS_TOL = 0.01` / `PROFIT_ABS_TOL = 0.5`, following
  `tests/unit/test_agents_fixtures.py`'s own stated reasoning (HiGHS solves to its default
  tolerance, not bit-exactly). The iteration count, the amplitude and the offer levels carry **no
  tolerance at all** — they are exact arithmetic on the step size, and a tolerance on them would
  be admitting the one thing the row exists to pin.

### (ii) Non-convergence is reported, not hidden, in both shapes

```
$ uv run --no-sync pytest tests/unit/test_market_agents.py -q -k "ac5ii or cycle_wider"
3 passed in 12.44s
```

- **Cap**: `max_iterations=83`, one below the 84 the climb needs, gives
  `termination_reason == "iteration_cap"`, `converged is False`, `iterations == 83`, and
  `_level(result.offers[0].offer) < 60.0` — it was genuinely cut off mid-climb (at $59.50), not
  finished early.
- **Cycle**: the "raise while at capacity" rule (`RaiseWhileAtCapacity`, step 5.0) gives
  `termination_reason == "cycle"` at **iteration 12** with `max_iterations` left at **400** — so
  "never the cap" is a real distinction here and not an artifact of a tight bound.
- A third test proves the verdict is produced **by the amplitude comparison and by nothing else
  that correlates with it**: the identical cycling run classified under `offer_tol=1.0` reports
  `cycle` and under `offer_tol=1e3` reports `converged`, with `narrow.iterations ==
  wide.iterations` asserting it is the same run seen two ways.
- The failed-clearing path reports `status != "Optimal"`, `converged is False` and
  `termination_reason is None`, never raising — a clearing that never happened has no loop outcome,
  and inventing a fourth enum value would fold the LP's verdict into the loop's.

---

## Sabotage sweep — eight defects, each naming the residual that moves

Only S4's own files were defected; no shared fixture data was touched. Each file was checksummed,
backed up, defected, tested, restored, and **checksummed again** — `all files restored, checksums
verified`. No `git checkout`, `stash`, `restore` or `clean` was run anywhere, at any point in this
slice.

Baseline: `38 passed in 17.62s`.

| # | defect | residual that moves | result |
|---|---|---|---|
| S1 | `gen_cost_coeffs` ignores the cost source | coefficients handed to the array builder: offer $60.00/MWh → true $20.00/MWh | 8 failed |
| S2 | cycle classified by repetition, not amplitude | `termination_reason` on the at-capacity run: `cycle` → `converged` | 2 failed |
| S3 | amplitude read over one round, not the whole cycle | measured amplitude of the at-capacity cycle: ~20 $/MWh → 0.0 | 2 failed |
| S4 | `iterations` off by one | `iterations` on the AC-5 duopoly: 84 → 85 | 4 failed |
| S5 | history skips a round (stale pair) | `two_rounds_ago.round_index` vs `round_index - 2` — S2's F1 guard fires | 15 failed |
| S6 | settlement taken at round 0's prices | `total_load_payment`: final-round $60.00 → round-0 $40.00 | 1 failed |
| S7 | markup drops the cleared MW | `AgentOfferResult.markup`, $/h: `(60-20)*200 = 8000` → `40` | 2 failed |
| S8 | `converged` asserted, not derived from the reason | `converged` on the capped and cycling runs: False → True | 5 failed |

Two are worth calling out.

**S5 shows S2's F1 guard is live in the loop, not merely present.** Making the loop hand round
`r-3` where round `r-2` belongs does not produce a subtly wrong climb — it produces a
`ValidationError` from `Observation`'s own contiguity validator, across 15 tests. That is the
guard doing exactly the job F1 created it for, in the loop F1 predicted would trigger it.

**S8's reds are the result model's own validator firing.** Setting `converged=True` unconditionally
makes a capped run carry `converged=True` beside `termination_reason="iteration_cap"`, which
`MarketAgentsResult`'s validator refuses to construct at all. The three enumerated words and the
flag cannot drift apart silently.

---

## Head gates

Run at `74a0532`.

```
$ uv run --no-sync pytest -q
1 failed, 1085 passed, 4 skipped, 10 warnings in 455.03s (0:07:35)
FAILED tests/unit/test_api_docs_coverage.py::test_every_public_symbol_is_reachable_from_an_api_page

$ uv run --no-sync ruff check .
All checks passed!

$ uv run --no-sync ruff format --check .
175 files already formatted

$ uv run --no-sync mypy
Success: no issues found in 53 source files
```

**Attribution of the one red.** `tests/unit/test_api_docs_coverage.py` is the wave's expected red
until S8 lands, per the plan's split-findings table. It is red **because of this slice**, and its
message lists exactly this slice's contribution and nothing else:

```
E       AssertionError: submodule symbols missing from docs/api pages:
E         mambo_power.market.agents: MarketAgentsOptions, solve_agents
E         mambo_power.results.agents: AgentOfferResult, MarketAgentsResult
```

Nothing here is attributed to foreign work, and no other test in the suite is red.

---

## New public symbols, for S8's API pages

| module | symbols |
|---|---|
| `mambo_power.market.agents` | `MarketAgentsOptions`, `solve_agents`, `DEFAULT_MAX_ITERATIONS` |
| `mambo_power.results.agents` | `MarketAgentsResult`, `AgentOfferResult`, `TerminationReason` |

`test_api_docs_coverage` names only the four classes/functions; `DEFAULT_MAX_ITERATIONS` (a module
constant) and `TerminationReason` (a `Literal` alias) are **not** currently detected by it, so they
would be silently missing from the API pages if this list did not carry them. Both have docstrings
and both are part of the documented contract — `TerminationReason` is A7's enumeration and
`DEFAULT_MAX_ITERATIONS` carries the measured rationale for the default.

Binding on S8 from spec C3, repeated here because it applies directly to the symbols above: **no
docs example may attach a markup strategy to a MATPOWER case.** All 147 generators in the six
committed fixtures are quadratic and `MarkupStrategy` raises `NotImplementedError` on any of them;
`tests/unit/test_market_agents.py::test_a_markup_strategy_on_a_quadratic_cost_still_raises_through_the_loop`
pins that this propagates through the loop rather than being swallowed into a status string.

---

## Design decisions taken, and what would reverse each

**`iterations` is the final round's index**, i.e. the number of best-response updates after round
0, so the loop clears `iterations + 1` times. Round 0 is the initial offer and responds to nothing,
so it is not an iteration. This is the convention under which the Step-2 probe's `r=84` is the
number reported, and it is stated in the field's own description. Under the other natural reading
(rounds cleared) the same run reports 85; nothing else changes. Flagged because it is a
definitional choice, not a measurement.

**Cycle detection keys on the pair `(offers[r-1], offers[r])`**, recorded after clearing round `r`,
from `r >= 1`. That pair is the loop state that determines round `r+1`: every strategy is a pure
function of its own last two rounds, and each round's LMPs and dispatch are a deterministic
function of that round's offers. A repeat therefore means the sequence is periodic from there —
what remains is classifying how wide the oscillation is, not whether it will end. Keying on a
single repeated offer vector, which is how W3 words it, would not carry that guarantee. The one
assumption this rests on: a strategy that reads `observation.round_index` directly could break the
periodicity. Neither shipped strategy does, and the module docstring says so.

**Offer comparison is exact JSON, with no rounding.** A tolerance here would be an uncalibrated
constant whose failure mode is the bad one — two genuinely different offer vectors declared
identical, so a still-moving run reports as settled. The cost of exactness is benign and the
opposite: a strategy whose offers drift by accumulated float error never repeats exactly and ends
at the iteration cap, which is reported as such.

**Amplitude is read from the coefficient rows the array builder was handed**, not from a
strategy-specific scalar — those rows are what the market actually saw, and every offer shape
`gen_cost_coeffs` maps has one. The exception is handled rather than ignored: a **piecewise** offer
gets an all-zero coefficient row by that mapping's own convention, so a piecewise offer that
*changes* across the cycle would read as zero amplitude and be reported as convergence. Such a
window returns infinity instead — an amplitude that cannot be read is not evidence of having
settled.

**`termination_reason` is `None` exactly when `status != "Optimal"`**, validator-enforced in both
directions. Adding a fourth enum value for a failed clearing would fold the LP's verdict into the
loop's, which is precisely what W4 forbids.

**`offer_tol` defaults to `1e-9`**, which admits only an offer vector that has genuinely come to
rest — what an all-price-taker run does. It is not a tuning constant, and any stepped strategy is
*forced* to state its derived tolerance because the validator refuses `offer_tol < 2 * step`. That
check runs on both paths: `MarketAgentsOptions`' own model validator for configs (so `jobs.run`
sees it as a bad request), and an `isinstance(strategy, MarkupStrategy)` check in
`_resolve_agents` for injected objects.

**`solve_agents(scenario, options, *, strategies=None)`** — the keyword-only in-process seam. It
exists because AC-5(ii)'s "raise while at capacity" rule is not a shipped config kind and could not
otherwise reach the loop, and it is what makes the `Strategy` Protocol non-decorative. Exactly one
source of agents is permitted; giving both raises. `provenance.options` still echoes `options`
verbatim, so `AgentOfferResult.strategy` — the config `kind`, or the injected object's class name —
is the record of what actually ran.

**A generator with no strategy is not an agent**: it clears at its own true cost and gets no
`offers` row. The alternative (requiring an explicit entry per generator) would make `solve_agents`
unusable on case118 without listing 54 generators.

---

## Carries and residuals

**R1 — `results/__init__.py` is outside this slice's file list, so the three new result symbols are
reachable only as `mambo_power.results.agents.*`,** unlike every other result type in the
repository, all of which are re-exported from `mambo_power.results`. Nothing is broken —
`test_docstrings` walks modules with `pkgutil` and sees them — but the public API is asymmetric
until someone who owns that file adds the export. S7 needs `MarketAgentsResult` for the job kind
anyway. **Reported to the orchestrator, not acted on.**

**R2 — `_clearing_rows` in `market/agents.py` duplicates ~55 lines of `solve_nodal`'s loads /
branches / settlement assembly.** This is the C1 pattern recurring in the same wave: the shared
part is real, and the duplication was unavoidable inside this slice's file list, since factoring it
out means editing `market/nodal.py`. Recorded rather than reopened, with the count stated: one
helper, ~55 lines, two call sites, and — unlike C1's branch-flow case — the two injection
constructions here are *identical*, not merely similar, because both clear a nodal market with
elastic demand. That makes this a stronger unification candidate than C1 and it should be named as
such in M8's carry list.

**R3 — the loop's amplitude is computed but not reported.** `converged` is derived from it, so a
user cannot audit the convergence verdict from the result alone; they would have to re-run with a
recorder, as this slice's own AC-5(i) amplitude test does. Adding an `amplitude` field would close
that, but it is not in W4's field list and this slice did not widen the result unilaterally. M8
candidate, or a spec amendment if the orchestrator wants it in M7.

**R4 — this slice asserts nothing about AC-3 or AC-4.** AC-3(b)'s bitwise agreement with
`solve_nodal` and AC-4's pivotal/control numbers are S5's, and `test_market_agents.py` deliberately
measures neither, so a red there will be unambiguous. The one adjacent figure this slice did
measure and can hand over: the smooth-pivotal fixture reaches offer `[60.0]` at iteration **84**
and the non-pivotal control stops at `[21.5]` at iteration **7**, both through the shipped loop
(`<scratch>/fixprobe.py`, "relative" row).

## Nothing was left unproven

Every acceptance clause assigned to this slice has a passing test and a sabotage that reddens it in
the specific quantity the clause names. There is no claim in this report carrying the label
`unverified`.
