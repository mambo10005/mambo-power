# Walk: strategic bidding (`market.agents.solve_agents`)

## Head and provenance

- Head under walk: `ec8876e` on `wave/07-agents`, exported with `git archive ec8876e | tar -x` into
  `C:\Users\mambo\AppData\Local\Temp\claude\C--Claude-Projects-mambo-power\0d397067-49ef-4969-aefa-5709948393ef\scratchpad\walk-ec8876e`.
  Nothing was run in either checkout.
- Proof the module resolves from the archive (`uv run --project <dir> python -c "import mambo_power; print(mambo_power.__file__)"`):

  ```text
  Built mambo-power @ file:///C:/Users/mambo/AppData/Local/Temp/claude/C--Claude-Projects-mambo-power/0d397067-49ef-4969-aefa-5709948393ef/scratchpad/walk-ec8876e
  Installed 77 packages in 59.84s
  C:\Users\mambo\AppData\Local\Temp\claude\C--Claude-Projects-mambo-power\0d397067-49ef-4969-aefa-5709948393ef\scratchpad\walk-ec8876e\src\mambo_power\__init__.py
  ```

- Date: 2026-08-29.

## What I read

In order, cold: `docs/manual/agents.md`, `examples/12_agent_market.py`, the agent sections of
`docs/api/market.md` and `docs/api/results.md`, the `market.agents` parts of `docs/manual/jobs.md`,
the entry for example 12 in `docs/examples/index.md`, and the M7 block of `docs/changelog.md`.

I opened source once: `src/mambo_power/market/strategy.py`, to find the attribute names on
`Observation` and `RoundRecord`. The manual says an agent sees "the round index" and "its last two
rounds of `(offer, bus LMP, cleared MW)`" but never names a field, and my first custom strategy
died on `obs.round` (it is `round_index`; the record fields are `lmp`, `cleared_mw`, `offer`).

Places the manual left me unsure what to type next:

1. The import path. The changelog, the examples index and the API page all say
   `market.solve_agents`; the manual says `from mambo_power.market.agents import solve_agents`.
   Only the second one exists (see Surprise 1).
2. Field names on `Observation` / `RoundRecord` (above).
3. Whether the result carries per-round offers. It does not; the manual never says so either way,
   and the `Results` table lists only the final `offers`. I had to build a recording wrapper.
4. What `iterations` counts. The table says "update rounds run after round 0; the market was
   cleared `iterations + 1` times", but the prose two sections up says "clearing price $60.00/MWh
   in 84 rounds". Measured: a strategy is called `iterations + 1` times, so "rounds" in the prose
   undercounts by one.
5. The example's `MarketAgentsOptions(strategies=...)` with no `offer_tol` for price-takers: the
   manual never states the default `offer_tol`. (It is `1e-9`, read off `provenance.options`.)

## What I ran

### `examples/12_agent_market.py` (full output)

```text
--- 1. price-takers vs market.solve_nodal, on case14 ---
dispatch array_equal: True | LMP array_equal: True
status Optimal | converged True | termination_reason converged | iterations 2
every offer is the true cost object: True | markups: [0.0]

--- 2. a pivotal supplier, against a closed-form optimum ---
closed form:  offer $60.00/MWh, cleared 400.00 MW, profit $16,000.00/h
the climb:    offer $60.00/MWh, cleared 400.00 MW, markup $15,999.97/h
at true cost: price $20.00/MWh, cleared 800.00 MW, markup $0.00/h
clearing price $60.00/MWh in 84 rounds
network byte-identical after the run: True
Generator.cost still the true curve: [20.0, 0.0]

--- 3. the same agent with a rival at $22/MWh ---
offer $21.50/MWh, cleared 785.00 MW, markup $1,177.50/h in 7 rounds
against the pivotal $15,999.97/h -- 13.6x smaller

--- 4. a two-agent duopoly ---
offers [60.0, 60.0] | price $60.00/MWh | joint markup $15,999.98/h
at true cost: price $40.00/MWh, cleared [300.0, 300.0]
status Optimal | converged True | termination_reason converged | iterations 84
under max_iterations=10: status Optimal | converged False | termination_reason iteration_cap | iterations 10
offer_tol below 2 * step is refused: Value error, offer_tol=0.5 is below 2 * step for the markup strategy on genera

--- 5. through jobs ---
kinds: ['market.agents', 'market.multiperiod', 'market.nodal', 'market.zonal', 'n1', 'opf.dc', 'pf.ac', 'pf.dc']
ok market.agents | converged True | termination_reason converged | iterations 84
strategies crossed JSON as data: {'g1': {'kind': 'markup', 'step': 0.5}, 'g2': {'kind': 'markup', 'step': 0.5}}
a strategy naming a generator that does not exist: failed VALIDATION
```

Every number matches the manual's quoted blocks.

### My own case

A triangle: buses A (slack), B, C; three 250 MW generators with linear costs `cheap` $15 at A,
`mid` $30 at B, `dear` $45 at C; one elastic load at C. Two demand curves were used:

- **D1**: value `80q - 0.1q^2`, i.e. `q = 400 - 5*price` (`p_mw=400`).
- **D2**: value `120q - 0.1q^2`, i.e. `q = 600 - 5*price` (`p_mw=600`).

All price-takers on D1, checked against `solve_nodal` myself:

```text
result type: MarketAgentsResult
agents  dispatch [250.0, 0.0, 0.0] lmps [30.0, 30.0, 30.0]
nodal   dispatch [250.0, 0.0, 0.0] lmps [30.0, 30.0, 30.0]
array_equal dispatch: True lmp: True
status Optimal converged True reason converged iterations 2
offer result fields: ['id', 'strategy', 'offer', 'true_cost', 'cleared_mw', 'markup']
result fields: ['provenance', 'status', 'message', 'generators', 'loads', 'buses', 'branches', 'offers', 'iterations', 'converged', 'termination_reason', 'total_load_payment', 'total_generator_receipts', 'congestion_rent']
net unchanged: True
empty strategies: offers [] reason converged iter 2 equal nodal True
no options: offers [] reason converged
```

Markup on `mid` (step 0.5, `offer_tol` 1.0) on **D1**, where `mid` is not needed at all
(the load takes exactly `cheap`'s 250 MW at $30):

```text
markup on mid: status Optimal converged False reason iteration_cap iterations 200
   {'id': 'cheap', 'strategy': 'price_taker', 'offer': {... 'coefficients': [15.0, 0.0] ...}, 'cleared_mw': 250.0, 'markup': 0.0}
   {'id': 'mid',   'strategy': 'markup',      'offer': {... 'coefficients': [130.0, 0.0] ...}, 'true_cost': {... [30.0, 0.0] ...}, 'cleared_mw': 0.0, 'markup': 0.0}
dispatch [250.0, 0.0, 0.0] lmps [30.0, 30.0, 30.0]
net unchanged: True
per-round offers exposed on result? []
```

The same on **D2**, where `mid` is marginal (nodal: `[250, 200, 0]` at $30):

```text
markup on mid: status Optimal converged True reason converged iterations 33
   mid markup offer c1 44.5 true 30.0 cleared 127.5 markup 1848.746
dispatch [250.0, 127.5, 0.0] lmps [44.5, 44.5, 44.5]
net unchanged: True
```

The result has no per-round offers, so I wrapped `MarkupStrategy` in a recording object and passed
it through the `strategies=` seam (trimmed to the ends and the turn):

```text
via seam: strategy label Recording | converged True converged iterations 33
per-round (round, offer c1, (prev lmp, prev cleared)):
   (0, 30.0, None)
   (1, 30.5, (30.0, 200.0))
   (2, 31.0, (30.5, 197.5))
   ...
   (29, 44.5, (44.0, 130.0))
   (30, 45.0, (44.5, 127.5))
   (31, 44.5, (45.0, 62.5))
   (32, 44.0, (44.5, 127.5))
   (33, 44.5, (44.0, 130.0))
same final offer as config path: True
```

The residual-monopoly optimum for `mid` on D2 is $50 / 100 MW / $2,000/h; the climb stops at
$44.50 because at $45 it ties with `dear` and its cleared MW halves. That is the manual's
"stalls at the local optimum on its own side of it", seen live.

The non-marginal D1 case, recorded with `max_iterations=12`:

```text
clearings seen by strategy: 13 | result.iterations: 12 | reason iteration_cap
   (0, 30.0, None)
   (1, 30.5, (29.999974999999992, 0.0))
   (2, 31.0, (29.999974999999992, 0.0))
   ...
   (12, 36.0, (29.999974999999992, 0.0))
```

### Break attempts (exact type and message; long messages cut where marked with `...`)

```text
market.solve_agents exists? False
[offer_tol < 2*step (options)] ValidationError: 1 validation error for MarketAgentsOptions   Value error, offer_tol=0.5 is below 2 * step for the markup strategy on generator "mid" (step=0.5, so 2 * step=1.0). A fixed-step climber settles into an oscillation of exactly two steps about its optimum (spec A9), so a narrower tolerance would report that arrival as a cycle. Raise offer_tol to at least 1.0, or lower the step. [type=value_error, ...]
[offer_tol < 2*step (seam)] ValueError: offer_tol=0.5 is below 2 * step for the MarkupStrategy on generator "mid" (step=0.5) -- see MarketAgentsOptions.offer_tol; a fixed-step climber settles into a two-step oscillation (spec A9)
[offer_tol == 2*step] NO EXCEPTION -> converged
case14 gen0: gen-1 [0.0430292599, 20.0, 0.0]
[markup on quadratic (case14)] NotImplementedError: MarkupStrategy supports only a linear PolynomialCost (coefficients=[c1, c0]) as observation.true_cost; got kind='polynomial', coefficients=[0.0430292599, 20.0, 0.0]
[unknown generator id] ValueError: a strategy names generator "ghost", which is not in the network
[unknown strategy kind] ValidationError: 1 validation error for MarketAgentsOptions strategies.mid   Input tag 'collude' found using 'kind' does not match any of the expected tags: 'price_taker', 'markup' [type=union_tag_invalid, ...]
[max_iterations=1] NO EXCEPTION -> ('Optimal', False, 'iteration_cap', 1, [30.5, 0.0])
[max_iterations=1, all price-takers] NO EXCEPTION -> ('Optimal', False, 'iteration_cap', 1)
[max_iterations=0] ValidationError: 1 validation error for MarketAgentsOptions max_iterations   Input should be greater than 0 [type=greater_than, input_value=0, input_type=int]
[cap too low (5)] NO EXCEPTION -> ('Optimal', False, 'iteration_cap', 5, [32.5, 0.0])
[both sources] ValueError: solve_agents was given both options.strategies and its own strategies argument -- an agent set has exactly one source, so pass configs (which cross JSON) or Strategy objects (which do not), never both
[negative step] ValidationError: ... strategies.mid.markup.step   Input should be greater than 0
[step=0] ValidationError: ... strategies.mid.markup.step   Input should be greater than 0
[markup missing step] ValidationError: ... strategies.mid.markup.step   Field required
[strategy returning None] ValidationError: 1 validation error for RoundRecord offer   Input should be a valid dictionary or object to extract fields from [type=model_attributes_type, input_value=None, input_type=NoneType]
[strategy returning linear c1=-5 (below cost)] NO EXCEPTION -> status Optimal, converged True, offers=[AgentOfferResult(id='mid', strategy='S', offer=[-5.0, 0.0], true_cost=[30.0, 0.0], cleared_mw=250.0, markup=-8750.0)], lmps 19.99995
[strategy returning quadratic] NO EXCEPTION -> ('Optimal', 'converged', [0.01, 30.0, 0.0], 330.57749812341353)
net unchanged after all attempts: True
```

### `jobs.run_json`, request JSON written by hand from the jobs page

```json
{"kind": "market.agents", "network": <net.model_dump(mode="json")>,
 "options": {"strategies": {"mid": {"kind": "markup", "step": 0.5}, "cheap": {"kind": "price_taker"}},
             "offer_tol": 1.0, "max_iterations": 100}}
```

```text
status ok | kind market.agents | converged True converged iterations 33
offers: [('cheap', 'price_taker', [15.0, 0.0], 250.0, 0.0), ('mid', 'markup', [44.5, 0.0], 127.5, 1848.75)]
provenance.options: {'strategies': {'mid': {'kind': 'markup', 'step': 0.5}, 'cheap': {'kind': 'price_taker'}}, 'max_iterations': 100, 'offer_tol': 1.0}
parsed result type: MarketAgentsResult
```

Malformed and wrong configs through `run_json` (status, code, message head, `details`/`issues`):

```text
[kind misspelt]         failed BAD_OPTIONS | ... Input tag 'mark_up' found using 'kind' does not match any of the expected tags: 'price_taker', 'markup' | details=[{'type': 'union_tag_invalid', 'loc': ['strategies', 'mid'], ...}]
[step as string]        failed BAD_OPTIONS | ... strategies.mid.markup.step  Input should be a valid number | details=[{'type': 'float_parsing', 'loc': ['strategies', 'mid', 'markup', 'step'], ...}]
[strategies as list]    failed BAD_OPTIONS | ... strategies  Input should be a valid dictionary | details=[{'type': 'dict_type', 'loc': ['strategies'], ...}]
[extra key in strategy] failed BAD_OPTIONS | ... strategies.mid.price_taker.step  Extra inputs are not permitted | details=[{'type': 'extra_forbidden', 'loc': ['strategies', 'mid', 'price_taker', 'step'], ...}]
[offer_tol < 2*step]    failed BAD_OPTIONS | ... offer_tol=0.5 is below 2 * step for the markup strategy on generator "mid" ... | details=[{'type': 'value_error', 'loc': [], ...}]
[max_iterations=0]      failed BAD_OPTIONS | ... max_iterations  Input should be greater than 0 | details=[{'type': 'greater_than', 'loc': ['max_iterations'], ...}]
[ghost generator]       failed VALIDATION  | Network validation failed with 1 issue: - DANGLING_REF at options.strategies: a strategy names generator "ghost", which is not in the network | issues=[{'code': 'DANGLING_REF', 'path': 'options.strategies', ...}]
[markup on quadratic via jobs] failed INTERNAL | NotImplementedError: MarkupStrategy supports only a linear PolynomialCost (coefficients=[c1, c0]) as observation.true_cost; got kind='polynomial', coefficients=[0.0430292599, 20.0, 0.0]
net unchanged after jobs: True
```

### Network mutation check

`net.model_dump()` compared before and after every run above (price-takers, empty strategies, no
options, markup on D1 and D2, the seam run, every break attempt, every jobs call): unchanged every
time.

## Surprises

1. **`market.solve_agents` does not exist.** Changelog: "`market.solve_agents(scenario,
   options=None, *, strategies=None) -> MarketAgentsResult`"; examples index: "`market.solve_agents`
   on hand-built linear-cost networks". Observed: `hasattr(market, "solve_agents")` is `False`;
   the function lives only at `mambo_power.market.agents.solve_agents`. The other three market
   modes are reachable as `market.solve_nodal` / `solve_multiperiod` / `solve_zonal`, so the
   missing re-export is a genuine trap for anyone who follows the changelog.

2. **A markup agent on a quadratic cost reaches `jobs` as `INTERNAL`.** Manual, Jobs API section:
   "every way of getting the agent set wrong maps to `BAD_OPTIONS` or `VALIDATION`, never
   `INTERNAL`"; changelog: "Caller mistakes (an unknown generator id, `offer_tol` below `2 * step`,
   **a markup strategy on a non-linear cost**, a bad iteration cap) map to `VALIDATION`, not
   `INTERNAL`." Observed with case14's `gen-1` and `{"kind": "markup", "step": 0.5}` through
   `run_json`: `failed INTERNAL | NotImplementedError: MarkupStrategy supports only a linear
   PolynomialCost ...`. The in-process call raises `NotImplementedError` as the manual's error
   table says it will; the jobs layer just does not translate it. Since every bundled case is
   quadratic, this is the *first* thing a user pointing the jobs kind at a fixture will hit.

3. **A markup agent that is never dispatched climbs forever and hits the cap.** Manual: "from
   round 2 on, direction is kept if the last move raised profit and reversed if it did not"; and
   "once it arrives it dithers by exactly one step either side of its optimum". Observed on D1,
   where `mid` clears 0 MW at every offer: profit is 0.0 in every round, the direction is never
   reversed, and after 200 rounds the run ends `converged False, termination_reason iteration_cap`
   with `mid` offering $130/MWh against a true $30. Reading the manual I expected "did not raise"
   to include "stayed equal" and the agent to settle on a two-step dither near its cost. The
   outcome is harmless to the dispatch (the offer is irrelevant to the clearing), but a user
   sees a non-converged run on the simplest possible market.

4. **`max_iterations=1` cannot converge even with only price-takers.** The price-taker examples
   show `iterations 2`. Observed: all-price-taker, `max_iterations=1` gives `status Optimal,
   converged False, termination_reason iteration_cap, iterations 1`, even though no offer ever
   moved. Consistent with the repetition test needing two update rounds, but the manual's
   "a bound, not a target" comment does not tell you the floor is 2 for anything to be reported
   as converged.

5. **The changelog says the strategy "returns the linear cost it offers"; the seam accepts any
   `GeneratorCost`.** A custom strategy returning `[0.01, 30.0, 0.0]` (quadratic) ran to
   `converged` with `markup 330.58`. The manual's wording ("returns a cost curve") is right; the
   changelog line is narrower than the behaviour.

6. **"Clearing price $60.00/MWh in 84 rounds" vs `iterations` = 84 means 85 clearings.** The
   results table: "the market was cleared `iterations + 1` times". Recording the strategy calls on
   my run with `max_iterations=12` showed 13 calls with `result.iterations == 12`. Both example
   sentences that say "in N rounds" print `iterations`, so they are one short.

## Friction

1. `Observation` and `RoundRecord` field names are not in the manual or the API prose; I had to
   open `strategy.py` after `AttributeError: 'Observation' object has no attribute 'round'`.
   One line listing `round_index`, `true_cost`, `p_min_mw`, `p_max_mw`, `previous_round`,
   `two_rounds_ago` and `RoundRecord(round_index, offer, lmp, cleared_mw)` would have saved it.

2. The rejection message for `offer_tol` below `2 * step` cites "(spec A9)" in both the options
   and the seam path. To a user of the package that reference points nowhere.

3. The default `offer_tol` is never stated in the manual. I learned it (`1e-9`) from
   `provenance.options`. For an all-price-taker run it does not matter; for a custom strategy
   passed through the seam it decides whether a small dither is `converged` or `cycle`.

4. A strategy that returns `None` fails with `ValidationError ... for RoundRecord offer`, i.e. the
   error surfaces after the clearing, naming a type the user never touched, rather than at the
   strategy's return. The cause is findable, but it points away from the mistake.

5. Per-round offers are not on the result. To see the climb I had to wrap the shipped strategy
   in a recorder and pass it through the seam. That worked well (and the wrapper's class name
   showed up as `strategy='Recording'` as documented), but the manual should say plainly that
   only the final round is reported.

6. The manual's error table says the up-front checks raise `ValueError`; through
   `MarketAgentsOptions` they arrive as pydantic `ValidationError`. It is a subclass, so
   `except ValueError` works, but the printed type differs from the table.

7. LMPs on a run where the price is set by demand come back as `29.999974999999992` rather than
   `30.0`, and `19.99995` rather than `20.0`. Expected HiGHS noise, and `array_equal` against
   `solve_nodal` still holds because both paths produce the same noise, but anyone comparing to a
   hand-computed price needs a tolerance the "exactly" language does not prepare them for.

## Verdict

From a user's chair this mode does what its manual promises on the core path: price-takers
reproduce `solve_nodal` bit for bit on my own network and on case14, a markup agent climbs
visibly and stops where a rival or demand stops it, the network I passed in was untouched after
every single run including the ones that raised, and the jobs boundary turns every malformed
strategy config I could think of into a `BAD_OPTIONS` or `VALIDATION` record with a usable
location. What it gets wrong is at the edges of the docs rather than the maths: two documents
name an entry point (`market.solve_agents`) that does not exist, the one mistake every fixture
invites (a markup agent on a quadratic cost) leaks out of `jobs` as `INTERNAL` despite two
documents promising it will not, and an agent that is never dispatched reports `iteration_cap`
at an absurd offer instead of settling. None of those blocked me for more than a few minutes,
but the first two would confuse a new user in their first ten, and the third would make them
distrust `converged` on a market that has nothing to converge.
