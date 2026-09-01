# M7 S3 report — agents fixtures (`tests/_agents.py`)

Wave M7 "agents", Step 4, slice S3 (implementor). Worktree `C:\Claude Projects\mambo-power-m7`,
branch `wave/07-agents`, base `6ca9dcc`. Serves spec requirement **W7**, and the fixture numbers
quoted in **AC-4** and **AC-5**.

Commit: **`7083460`** — see §6.

Every command below was run; every number is measured output. Nothing in this report is labelled
`unverified`.

---

## 1. What shipped

| file | change |
|---|---|
| `tests/_agents.py` | new, 194 lines — three network factories (`smooth_pivotal_network`, `non_pivotal_control_network`, `duopoly_network`) + shared `clear_with_offers` helper |
| `tests/unit/test_agents_fixtures.py` | new, 332 lines — **15 tests**: measured-table checks, an independent closed-form check, a 5-point sabotage sweep, an AC-2-shaped no-mutation check, and a factory-default guard |

Nothing else was touched. `market/agents.py` (the fixed-point loop itself) does not exist yet —
that is S4 — so every clearing here goes through `opf.dc_opf` directly, the same path
`market.nodal.solve_nodal` uses (`gen_cost_coeffs` + `load_bid_coeffs` + `dc_opf`), on hand-set
offers. No iteration count, `converged` flag or `termination_reason` is measured anywhere in
this slice.

## 2. Measurement provenance — clean tree, not a moving target

`opf/dc_opf.py` (the builder every fixture clears through) was under concurrent edit by S1 for
the whole of this slice (`git diff --stat src/mambo_power/opf/dc_opf.py` showed 87
insertions/18 deletions throughout). Rather than trust that S1's in-flight edit is
behaviour-preserving by assumption, every number in §3 and §4 was cross-checked against a
**clean `git archive 6ca9dcc`** extracted to a scratch directory, imported via `sys.path`
override (not `git checkout`/`stash`/`restore` — those would touch the shared worktree the other
three slices are using):

```
$ uv run --no-sync python .bionic/tmp/m7-s3-baseline-check.py
using mambo_power from: C:\Users\mambo\AppData\Local\Temp\m7-baseline-check\src\mambo_power\__init__.py
=== smooth pivotal (BASELINE 6ca9dcc) ===
true cost: Optimal 20.00007999984 799.9984000031999 0.06399974400092068
offer 60 : Optimal 60.00003999992 399.99920000159995 15999.983999999997
=== control (BASELINE) ===
offer 21.5: Optimal 21.500078499843 784.9984300031399 1177.5592672582197
=== duopoly (BASELINE) ===
true cost: Optimal 39.99993999999999 [300. 300.]
both 60  : Optimal 60.00001999997 [199.99970001 199.99969999] 15999.984000011997
```

**Bit-identical** to the same probe run against the working tree (S1's in-flight edit included)
— confirming AC-1(a)'s own behaviour-preservation claim at this fixture's scale, and confirming
none of this report's numbers are an artifact of a half-finished edit. The scratch directory was
deleted after the check; nothing in the shared worktree was touched.

## 3. Measured table — spec's own numbers vs. this slice's measurement

All six spec-table rows, reproduced through the actual model classes and `opf.dc_opf` (not the
Step-2 research probes' ad hoc `Market` class):

| fixture | offer | spec price | measured price | spec dispatch | measured dispatch | spec profit | measured profit |
|---|---|---|---|---|---|---|---|
| smooth pivotal | true cost ($20) | $20.00 | 20.00008 | 800.00 MW | 799.9984 MW | $0.06 | 0.06400 |
| smooth pivotal | strategic $60 | $60.00 | 60.00004 | 400.00 MW | 399.9992 MW | $15,999.98 | 15999.98400 |
| control | true cost | $20.00 | 20.00008 | -- | -- | $0.06 | 0.06400 |
| control | strategic $21.50 | -- | 21.50008 | -- | 784.9984 MW | gain $1,177.50 | gain 1177.4953* |
| duopoly | true cost | $40.00 | 39.99994 | [300, 300] | [300.00, 300.00] | $11,999.96 | 11999.96400 |
| duopoly | both $60 | $60.00 | 60.00002 | -- | [200.00, 200.00] | $15,999.98 | 15999.98400 |

\* control gain computed as (offer-21.50 profit) − (true-cost profit), both measured in the same
run, matching the spec's own framing ("$1,177.50 ... against the pivotal $15,999.92"); pivotal
gain measured at 15999.984 − 0.064 = 15999.920, matching exactly.

**No disagreement with the spec table.** Every measured figure sits within HiGHS's own solve
residual (~2e-4 $/MWh on price, ~2e-3 MW on free dispatch) of the spec's two-decimal-place
number — the pattern the spec's own AC-3(b)/A3 findings already document for this solver on
identical-input LPs. This is the agreement AC-4 asks to be pinned, not a discrepancy.

Proving command (identical numbers to the working-tree run, confirmed against baseline in §2):

```
$ uv run --no-sync pytest tests/unit/test_agents_fixtures.py -q
...............                                                          [100%]
15 passed in 14.10s
```

## 4. Closed-form check (AC-4's own requirement, independent of any solve)

`test_smooth_pivotal_closed_form_peak_matches_the_spec_derivation` computes
`profit(price) = (price - 20)(1000 - 10*price)` in pure Python (no `dc_opf` call), and asserts:
- `profit(60.0) == 16000.0` exactly (`abs=1e-9`)
- `profit(59.0) < profit(60.0)` and `profit(61.0) < profit(60.0)` — a genuine peak, not a plateau

The solver's measured $15,999.98 (§3) against this exact $16,000.00 is the two-figure agreement
the spec calls out explicitly.

## 5. Sabotage sweep — every defining parameter is load-bearing

Standing rule: perturb each fixture's defining parameter and name the residual that moves. All
five probes below were run through `clear_with_offers` on the sabotaged network (same helper
the pinned tests use), with expected values derived by hand first, then checked against the
solve:

| # | fixture | parameter sabotaged | test that would go red | residual that moves | measured |
|---|---|---|---|---|---|
| 1 | smooth pivotal | capacity 900→300 MW | `test_smooth_pivotal_offer_60_reaches_the_closed_form_peak` (price/dispatch/profit trio) | price $60→$70, dispatch 400→300, profit $15,999.98→$15,000.00 (demand's own curve pushes price up to clear at the now-binding cap) | price 69.99997, dispatch 300.0, profit 14999.99100 |
| 2 | smooth pivotal | true cost $20→$25 | `test_smooth_pivotal_closed_form_peak_matches_the_spec_derivation` ($16,000 figure) and `test_smooth_pivotal_true_cost_offer_reproduces_the_competitive_result` ($20.00/800 MW) | closed-form peak moves to $62.50/375 MW/$14,062.50; true-cost clearing moves to $25.00/750 MW | true-cost: price 25.00007, dispatch 749.9985; peak: price 62.50004, dispatch 374.99925, profit 14062.48594 |
| 3 | control | rival true cost $22→$20.50 (now below the strategic $21.50 stop offer) | `test_control_offer_21_50_gain_is_real_and_far_smaller_than_the_pivotal_gain` (dispatch ~785 MW, gain $1,177.50) | strategic dispatch/profit collapse to exactly 0 — the rival now serves the whole clearing quantity below the strategic offer | dispatch strategic 0.0, profit 0.0, price 20.50008 |
| 4 | duopoly | agent_a capacity 300→100 MW | implicit even split behind `test_duopoly_both_offer_60_matches_the_measured_settling_point` | per-agent split 200/200 → 100/300; joint profit **unchanged** (total quantity and price unchanged since agent_b's cap covers the shortfall) — proving `DUOPOLY_P_MAX_MW` constrains something rather than being decorative | dispatch [100.0, 299.9993], price 60.00003, joint profit 15999.98400 |
| 5 | shared demand curve | `PolynomialBid` intercept $100→$80 (`q=800-10*price` instead of `1000-10*price`) | `test_smooth_pivotal_true_cost_offer_reproduces_the_competitive_result` (800 MW dispatch) and the closed-form peak | true-cost dispatch 800→600 MW; peak moves to $50.00/300 MW/$9,000.00 | true-cost: dispatch 599.99880; peak: price 50.00003, dispatch 299.99940, profit 8999.99100 |

Every sabotage row's measured figure matches its hand-derived expectation to within the same
HiGHS residual documented in §3 — the perturbation reliably moves the numbers the pinned tests
check, so those numbers are not vacuous. All five are asserted directly in
`tests/unit/test_agents_fixtures.py`'s `test_sabotage_*` functions (not merely narrated here).

Proving command: same `pytest tests/unit/test_agents_fixtures.py -q` run in §3 (the sabotage
tests are five of the fifteen).

## 6. Gates and commit

```
$ uv run --no-sync pytest tests/unit/test_agents_fixtures.py -q
15 passed in 14.10s

$ uv run --no-sync ruff check tests/_agents.py tests/unit/test_agents_fixtures.py
All checks passed!

$ uv run --no-sync ruff format --check tests/_agents.py tests/unit/test_agents_fixtures.py
2 files already formatted

$ uv run --no-sync mypy
Success: no issues found in 51 source files
```

`mypy`'s repo gate is `[tool.mypy] files = ["src"]` (confirmed by reading `pyproject.toml:59-61`
directly, and matching M6/S2's own precedent, `.bionic/docs/record/m6-s2-report.md:116`) — it
does not scope `tests/`, so it has nothing to say about either owned file specifically; the
repo-wide invocation above is clean regardless.

```
$ uv run --no-sync pytest -q
...
FAILED tests/unit/test_api_docs_coverage.py::test_every_public_symbol_is_reachable_from_an_api_page
FAILED tests/unit/test_docstrings.py::test_every_public_symbol_has_a_docstring
2 failed, 1005 passed, 4 skipped, 10 warnings in 740.96s (0:12:20)
```

**Both failures are foreign, not mine.** `test_docstrings.py`'s own captured output names the
missing symbols directly: `mambo_power.market.strategy.MarkupStrategy.offer` and
`mambo_power.market.strategy.PriceTakerStrategy.offer` — S2's in-flight, uncommitted
`market/strategy.py`, a path this slice never touches. `test_api_docs_coverage.py` fails for the
same reason (an undocumented public symbol has no API page to be reachable from). Neither test
lives under `tests/_agents.py` or `tests/unit/test_agents_fixtures.py`'s import graph. Per the
team lead's standing instruction, these are reported, not investigated or fixed. The 1005 passed
includes all 15 of this slice's own tests.

Repo-wide `ruff check .` also currently shows unrelated findings in `market/strategy.py`,
`test_market_strategy.py` (S2) and `test_market_nodal.py` (S6) — none in either file this slice
owns; scoped `ruff check tests/_agents.py tests/unit/test_agents_fixtures.py` above is clean.

**Commit:**

```
$ git add tests/_agents.py tests/unit/test_agents_fixtures.py
$ git commit -m "test(m7/s3): agents fixtures — smooth pivotal, non-pivotal control, two-agent duopoly"
```

SHA: **`7083460`** (see §6 header — filled in after the commit below; explicit paths only, no
`git add -A`/`.`, no `checkout`/`stash`/`restore`/`clean` anywhere in this slice).

## 7. What was not proved

- No iteration count, `converged` value or `termination_reason` — the loop (`market.agents`,
  S4) does not exist in this worktree yet; W7's own text places round-count/end-state
  re-measurement at "before AC-4's and AC-5's numbers are frozen," which is this slice's
  economics check, not the loop's own dynamics (that is S4/S5's row).
- Platform-dependence of the bitwise/near-bitwise agreement in §2 — only run on this machine, as
  AC-3(b)/A3 already flag as a standing, not newly introduced, limitation.
