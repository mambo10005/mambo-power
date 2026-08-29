# M7 S8 — docs — phase 1 report

Slice: S8 (docs), wave M7 `agents`, requirement **W8**, acceptance **AC-7** (partial — phase 1).
Worktree `C:\Claude Projects\mambo-power-m7`, branch `wave/07-agents`.
Base at dispatch `a22922d`. **Commit: `9ae56ed`** — `docs(m7/s8): the strategy seam reaches the
API reference and the architecture edges`. Two files, both S8-owned:
`docs/api/market.md`, `docs/design/architecture.md`. Nothing under `src/` or `tests/` touched.

## Headline

`tests/unit/test_api_docs_coverage.py` — **green** at `9ae56ed`. The red that has stood since S2
landed `market/strategy.py` at `df3c849` is closed; no other slice needs to reason about it again.

`mkdocs build --strict` — **exit 0** at `9ae56ed`.

One briefed item is **deferred to phase 2 with proof that it cannot land now**: the
`docs/manual/jobs.md:267` transcript fix. See F1.

## How everything below was measured

This worktree is shared with three live slices and, at the time of writing, holds S4's
**uncommitted** `src/mambo_power/market/agents.py`, `src/mambo_power/results/agents.py`,
`tests/unit/test_market_agents.py` and a modified `src/mambo_power/opf/__init__.py`. Per plan
assumptions A14/A15, every number quoted here was taken against an isolated
`git archive 9ae56ed` tree extracted into the session scratchpad, driven by `sys.path`, with the
resolved module path printed **inside the run's own process** so the archive is proved to have won
over the venv's editable install. Nothing outside the scratchpad was written; no
`checkout`/`stash`/`restore`/`clean` was run in either tree.

```
RESOLVED mambo_power: ...\scratchpad\iso2\src\mambo_power\__init__.py
RESOLVED mambo_power.results: ...\scratchpad\iso2\src\mambo_power\results\__init__.py
```

The archive's `src/mambo_power/market/` holds `__init__.py multiperiod.py nodal.py strategy.py
zonal.py` and its `results/` holds no `agents.py` — i.e. the isolation is real and readable, not
asserted.

## Deliverable 1 — the API page for `mambo_power.market.strategy`

`docs/api/market.md` gains `## The strategy seam`, in the page's existing
one-section-per-submodule form (`## Welfare LP over a Scenario`, `## Multiperiod clearing over a
horizon`, `## Zonal clearing and redispatch`), with prose then a bare
`::: mambo_power.market.strategy` directive. A separate nav page was **not** created: every API
page in this site is one top-level package with a section per submodule, and `nav:` lists exactly
one page per package.

Proving command (archive of `9ae56ed`):

```
pytest -q tests/unit/test_api_docs_coverage.py tests/unit/test_docstrings.py \
          tests/unit/test_docs_registry_listing.py
8 passed in 5.23s
```

### Rendering evidence — anchors, not just class names

Two `mkdocs build --strict` runs, same config, differing only in this page:

| built site | `mambo_power.market.strategy.*` anchors on `api/market` | all `mambo_power.market.*` anchors on that page |
|---|---|---|
| before (worktree at `a22922d`) | **0** | 37 |
| after (`9ae56ed`) | **23** | 61 |

The 23:

```
build_strategy
MarkupConfig, MarkupConfig.step
MarkupStrategy, MarkupStrategy.offer
Observation, Observation.p_max_mw, Observation.p_min_mw, Observation.previous_round,
  Observation.round_index, Observation.true_cost, Observation.two_rounds_ago
PriceTakerConfig
PriceTakerStrategy, PriceTakerStrategy.offer
RoundRecord, RoundRecord.cleared_mw, RoundRecord.lmp, RoundRecord.offer, RoundRecord.round_index
Strategy, Strategy.offer
StrategyConfig
```

All nine named symbols (the briefed eight plus `build_strategy`), including `StrategyConfig`,
which is an `Annotated` module attribute rather than a class and which
`test_api_docs_coverage` therefore does **not** police — it renders because it carries a module
docstring, not because the test made it.

Ten of those anchors are pydantic **fields**, and their `Field(description=...)` prose is on the
page, which is the thing M6's griffe extension exists to publish. Extracted from the built HTML:

```
two_rounds_ago : RoundRecord | None
  Round round_index - 2's own outcome; None when round_index <= 1, i.e. there is at most one
  prior round.

step : float
  Fixed offer step, $/MWh per round. Bounds the loop's own convergence tolerance from below
  (A9): offer_tol must be >= 2 * step.
```

**One absence, checked rather than shrugged at.** `PriceTakerConfig.kind` and `MarkupConfig.kind`
render no anchor. That is the site's existing convention, not a gap this page introduced: a
discriminator field carries a `Literal` default and no `description=`, the extension attaches
nothing, and `show_if_no_docstring: false` drops it. Verified against the shipped precedent —
`mambo_power.model.PolynomialCost.kind` is absent from `api/model` in the same build where
`PolynomialCost.coefficients` is present. The per-model griffe guard does not fire on them either,
correctly: `_undocumented` only counts fields that *have* a `description=` to publish, so a
`kind`-only model is not a silently-empty model. The `--strict` build's exit 0 is that guard
passing, on every model in the package.

## Deliverable 2 — architecture edges

`docs/design/architecture.md`, four changes:

1. **The seam gets its own node**, `marketstrategy`, in the component diagram — not a line added
   to the `market` node's label. The load-bearing fact is an import direction the collapsed form
   would hide: `market.strategy` reaches `model` and **nothing else** — no `numerics`, no `opf`,
   no `results` — where `market` reaches seven modules. That is the same reason `opf.multiperiod`,
   `opf.zonal` and `opf.redispatch` are separate nodes rather than lines in the `opf` label. Its
   one edge is `marketstrategy --> model`; the not-yet-committed loop points at it dotted
   (`marketlater -.-> marketstrategy`).
2. **A prose bullet** under "Rules the diagram encodes", between the `market.zonal` bullet and the
   `jobs` one: the seam's narrow import direction as the own-node observation contract *made
   mechanical rather than merely documented*; Protocol over ABC and why; `StrategyConfig` as the
   thing that crosses the `jobs` boundary, never a callable; and the offer as an overlay, with
   `Generator.cost` never rewritten — "which is the only reason 'markup' is a quantity this
   package can compute at all."
3. **Two ownership-table rows**, each with an agreement test that exists today and was read before
   it was cited:
   - *Offered cost, as distinct from true cost* — `market.strategy` (M7) — agreement:
     `PriceTakerStrategy` returns `Observation.true_cost` verbatim, coefficients compared with
     `==` (`test_price_taker_returns_true_cost_exactly`, `..._with_history_present`), and a
     piecewise true cost asserted `is`-or-`==` identical
     (`test_price_taker_returns_a_piecewise_true_cost_exactly`).
   - *An agent's own-node history* — `market.strategy.Observation` (M7) — agreement: a skipped
     round and a stale one both raise
     (`test_observation_rejects_a_missing_previous_round`, `..._a_stale_previous_round`,
     `..._a_stale_two_rounds_ago`).
4. **The module map on disk** gains `strategy.py (Observation, Strategy, PriceTakerStrategy,
   MarkupStrategy, StrategyConfig, build_strategy)` under `market/`.

Two consequential wordings, flagged because they are judgement calls and phase 2 revisits both:

- The shipped subgraph is relabelled `Shipped (M1-M6)` -> `Shipped (M1-M7)`. It now contains an
  M7 module, so the old label was false on this branch.
- The "later waves" node is narrowed from `market: agents (M7)` to
  `market.agents / solve_agents (the fixed-point loop, M7)` — the half of M7 that genuinely is not
  committed. Phase 2 moves it into the shipped box.

Rendered-output check (built site, `design/architecture/index.html`): "seam, not a solver",
"Offered cost, as distinct", "own-node history" and "strategy.py (Observation" all present; four
occurrences of `market.strategy` on the page. No test in `tests/` reads this file
(`grep -rln architecture tests/ --include=*.py` -> nothing), so the `--strict` build is its only
gate and it passed.

## Deliverable 3 — `MarketNodalResult.branches` renders (checked, not assumed)

S6 added the field at `832a546`. It is a new *field* on an existing model, so
`test_api_docs_coverage` cannot see it and the griffe extension is what has to carry it. Verified
on the built site rather than reasoned about: `api/results` carries
`id="mambo_power.results.MarketNodalResult.branches"` with its full field prose —

```
branches : list[OpfBranchFlowResult]
  Per-branch flow and flow-limit shadow price at the solved dispatch -- the same field name and
  row type as MarketZonalResult.branches (module docstring, AC-8). Makes the settlement
  identity's flow-dual side, -sum_k(mu_k * f_k), computable from this object alone.
```

`MarketNodalResult` renders six field anchors in total (`branches`, `congestion_rent`, `message`,
`status`, `total_generator_receipts`, `total_load_payment`). **No page edit was required**; the
`::: mambo_power.results` block reaches it through `results/__init__.py`'s re-export, which is the
mechanism `test_api_docs_coverage`'s own docstring describes. Item closed with evidence, zero diff.

## F1 — the `jobs.md:267` fix cannot land in phase 1, and here is the proof

The brief lists it as phase-1 scope, "a stale transcript, a known one-line fix". **It is not stale
yet, and writing the fix now turns a currently-green test red.**

`tests/unit/test_docs_registry_listing.py::test_the_manual_unknown_kind_message_lists_every_registered_kind`
asserts that `"registered kinds: " + ", ".join(sorted(jobs.KINDS))` appears **verbatim** in
`docs/manual/jobs.md`. At `9ae56ed` the registry holds seven kinds and the page's line 267 lists
exactly those seven:

```
$ python -c "from mambo_power import jobs; print(sorted(jobs.KINDS))"
['market.multiperiod', 'market.nodal', 'market.zonal', 'n1', 'opf.dc', 'pf.ac', 'pf.dc']

docs/manual/jobs.md:267
failed UNKNOWN_KIND | unknown kind "pf.telepathy"; registered kinds: market.multiperiod,
market.nodal, market.zonal, n1, opf.dc, pf.ac, pf.dc

$ pytest -q tests/unit/test_docs_registry_listing.py
4 passed in 5.38s
```

Replacing that line with an eight-kind list before `market.agents` registers removes the string
the test looks for. The line goes stale **at the moment of registration**, which is the jobs
slice, and that is where the fix belongs — `m7-research.md:450` says the same thing ("a one-line
update the day `market.agents` registers").

It is also **not one line**. The same module pins three sites on that page, all of which the
eighth kind invalidates together:

| test | site | what goes stale |
|---|---|---|
| `test_the_manual_prints_the_real_sorted_kind_list` | the `print(jobs.kinds())` output block | the 7-tuple |
| `test_the_manual_capability_table_lists_every_registered_kind` | the capability table | one missing row: `market.agents <OptionsModel> MarketAgentsResult` |
| `test_the_manual_unknown_kind_message_lists_every_registered_kind` | line 267 | the sorted list in the `UNKNOWN_KIND` message |

Phase 2 does all three in one edit. `pf.telepathy` remains safe as the fictional unknown kind —
it collides with nothing `market.agents` introduces (research §9, re-confirmed here).

## Intel for phase 2, arriving live

Running `test_api_docs_coverage` in the *shared worktree* (not the archive) reads S4's
uncommitted files and prints tomorrow's list already:

```
mambo_power.market.agents: MarketAgentsOptions, solve_agents
mambo_power.results.agents: AgentOfferResult, MarketAgentsResult
```

So phase 2's API-page work is: a `market.agents` section on `docs/api/market.md` and a
`## Agent market results` section on `docs/api/results.md` — four public symbols, plus whatever
fields `MarketAgentsResult` and `AgentOfferResult` carry, each of which needs its
`Field(description=...)` to actually appear (the per-model guard fails the build if a model with
descriptions renders none, but it cannot fail on a model that reaches no page at all — that is
`test_api_docs_coverage`'s job, and only for classes and functions).

Phase-2 items not started, per the brief: the agents manual page, the worked example, the
changelog entry, the `market.agents` API page, and F1's three-site jobs fix.

## Anything not proven

Nothing claimed above is unverified. Two statements are scoped rather than proven and are labelled
as such in place: the `Shipped (M1-M7)` relabel is true of this branch's head and becomes true of
`epic/01-foundation` when the wave merges; and the phase-2 symbol list is read off another slice's
uncommitted working tree, so it is current-as-of-now intel, not a committed fact.

## Standing-rule compliance

- Committed with explicit paths (`git add docs/api/market.md docs/design/architecture.md`); the
  post-commit `git status` shows the other slices' files still untracked/modified and untouched.
- No `git checkout`, `stash`, `restore` or `clean` in either tree.
- `C:\Claude Projects\mambo-power` (the user's main checkout) was never read from or written to.
- No file under `src/`, `tests/`, `.bionic/docs/specs/**` or `.bionic/docs/plans/**` was edited.
