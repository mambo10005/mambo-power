# M4 S5 report — fixtures-oracle: test-time bid derivation, pandapower sgen parity

Wave M4 "nodal-market", Slice S5. Implementor. Worktree `C:\Claude Projects\mambo-power-m4`,
branch `wave/04-nodal-market`, base `ec4ba22` (S1-S4 landed). Commit `5442465`, pushed.

## What was built

1. **`tests/_bids.py`** — a test-time bid-derivation helper mirroring `tests/_rated.py`'s
   discipline exactly: no new committed fixture data, a documented transformation of a
   fixture's own already-committed state.
   - `VOLL_PER_MWH = 10_000.0` ($/MWh) — a round, literature-standard value-of-lost-load figure
     (the same order of magnitude as ERCOT's $9,000/MWh system-wide offer cap, which functions
     as a VOLL proxy in that market's design).
   - `fleet_max_marginal_cost(net)` — the highest, over every in-service generator, of that
     generator's own marginal cost at its own `p_max_mw` (`c1 + 2*c2*p_max_mw`). This is a
     mathematical ceiling on the achievable market-clearing price on that network (a convex
     generator's marginal cost is non-decreasing in its own output, so its marginal cost at its
     actual dispatch never exceeds its marginal cost at its own upper bound).
   - `bid_for_load(net, load_id)` — a `PolynomialBid` whose marginal value descends **linearly**
     from `VOLL_PER_MWH` at `p=0` to `fleet_max_marginal_cost(net)` at `p = load.p_mw` (the
     load's own committed historical demand, never invented). Raises `ValueError` if the VOLL
     doesn't clearly exceed the fleet ceiling (the invariant the concave curve depends on).
   - `with_bids(net, load_ids=None)` — a non-mutating copy of `net` with `bid_for_load`'s
     derivation applied to every id in `load_ids` (default: every load).

2. **`tests/unit/test_bids.py`** (7 tests) — proves `tests/_bids.py`'s own guarantees directly,
   mirroring `tests/unit/test_rated_helper.py`: correct anchor arithmetic (hand-checked against
   case14.m's own gencost/gen blocks), genuine concavity (`v2 < 0`), non-triviality (>1000
   $/MWh marginal-value swing, not a degenerate flat step — the exact failure mode spec
   Assumption (a) warns against), no mutation, default-to-every-load and explicit-subset
   behavior.

3. **`tests/parity/test_market_nodal_vs_pandapower.py`** (4 tests, AC-6) — case14, all 11 loads
   bid via `tests/_bids.py`. Builds the pandapower oracle via the `sgen` framing (sign-flipped,
   negative-bound generator): drops every load row and replaces it with a `pp.create_sgen`
   (`min_p_mw=-p_mw, max_p_mw=0, controllable=True`) plus `pp.create_poly_cost(..., "sgen",
   cp1_eur_per_mw=v1, cp2_eur_per_mw2=-v2)` — the `cost_sgen(p) = -value(-p)` sign-flip
   transformation `m4-research.md` §3.1 proved exact. The module's own docstring documents the
   `load`-row quadratic non-convergence bug (spec Assumption b) this convention routes around,
   so a future reader doesn't have to rediscover it via `git log -S`.

## VOLL figure and curve shape (spec Assumption a)

**VOLL_PER_MWH = 10,000 $/MWh.** Chosen as a round, literature-standard value-of-lost-load
figure clearly above any of this wave's fixtures' own generation-fleet ceiling (case14's is 90
$/MWh, at generator 2's own 140 MW upper bound) — verified, not assumed:
`VOLL_PER_MWH > fleet_max_marginal_cost(net)` is checked by `bid_for_load` itself and asserted
directly in `tests/unit/test_bids.py`.

**Curve shape**: linear marginal value (quadratic value function `value(p) = v1*p + v2*p**2`)
descending from VOLL at `p=0` to the fixture's own fleet ceiling at `p = load.p_mw` — the exact
shape the wave spec's W6/Assumption (a) describes. This is a genuinely non-trivial, strictly
concave curve (`v2 < 0`), not a degenerate flat step: on case14's `load-9` (bus 9, 29.5 MW), the
marginal value swings from 10,000 $/MWh at `p=0` to 90 $/MWh at `p=29.5` — a swing of 9,910
$/MWh, verified directly in `tests/unit/test_bids.py`
(`test_bid_for_load_is_genuinely_concave_and_non_trivial_not_a_degenerate_flat_step`).

A quadratic curve (not a piecewise-linear one) was chosen deliberately for the AC-6 oracle test:
pandapower's `create_poly_cost` API only accepts a **polynomial** cost, not a piecewise-linear
one, so a quadratic bid is what the `sgen` oracle can actually exercise — and it independently
tests the elastic-demand **QP** path (`dc_opf`'s Hessian sign-flip for a nonzero `v2`), a code
path AC-5's own price-taker test (a purely linear, `v2=0` bid) does not touch.

**A proven, documented mathematical consequence of the anchor rule**: because the low end of
every derived curve (`fleet_max_marginal_cost`) is itself an upper bound on the achievable
market-clearing price on that fixture, every bid this module derives is *always* fully
price-taking (dispatched at its own full `p_mw`) — confirmed directly against pandapower's own
engine in the AC-6 test
(`test_every_bid_load_is_fully_price_taking_on_this_fixture`), independent of `opf.dc_opf`'s own
price-taker reduction that AC-5 already proves. This is disclosed plainly, not hidden: it means
this particular anchor rule cannot itself produce a congestion-and-price-elastic-demand
interaction on an unrated fixture (none of this wave's fixtures rate any branch, per
`m3-research.md` §6, so that interaction is untestable via a real fixture regardless of bid
shape) — AC-4's own settlement-identity test already covers that interaction on a hand-built
network.

## Measured oracle-parity tolerance

Measured directly (`<scratchpad>/probe_bid_oracle_all.py`, all 11 case14 loads bid
simultaneously) before any test was written:

| metric | measured worst case | pinned tolerance | margin |
|---|---|---|---|
| dispatch | 7.14e-10 MW | `DISPATCH_ABS_TOL_MW = 1e-6` | ~1,400x |
| LMP | 1.94e-5 $/MWh | `LMP_ABS_TOL = 1e-3` | ~51x |

Both margins follow this repo's established parity discipline (`tests/parity/
test_opf_vs_pandapower.py`'s own docstring: "measured directly ... not assumed").

## RED/GREEN evidence

- **RED**: `tests/unit/test_bids.py` written first, run against a non-existent `tests/_bids.py`
  — `ModuleNotFoundError: No module named 'tests._bids'`, 1 error during collection.
- **GREEN**: `tests/_bids.py` implemented — `pytest -q tests/unit/test_bids.py`: 7 passed.
- The `sgen` sign-flip transformation was probed and numerically pinned in scratchpad
  (`probe_bid_oracle.py`, `probe_bid_oracle_all.py`) *before* `tests/parity/
  test_market_nodal_vs_pandapower.py` was written, so that test file was GREEN on its first run
  (`pytest -q tests/parity/test_market_nodal_vs_pandapower.py`: 4 passed) — no RED-phase
  surprises on the parity half, consistent with this wave's own research-then-implement
  discipline (the transformation itself was already research-proved in `m4-research.md` §3.1;
  this slice's own job was deriving a real bid curve and wiring it through, not re-discovering
  the transformation).
- Full suite: `uv run --no-sync pytest -q` — **645 passed** (630 S4 baseline + S6's concurrently
  landed jobs tests + this slice's 11 new). `ruff check .` and `ruff format --check .` clean on
  the new files. Bare `uv run mypy` (no positional `.`, per the documented quirk — `files =
  ["src"]` in `pyproject.toml`) — clean, 43 source files (tests are outside mypy's `strict`
  scope, as already established by every prior slice in this wave).

## Commit

`5442465` — `feat(m4/S5): fixtures-oracle — test-time bid derivation, pandapower sgen parity`,
pushed to `wave/04-nodal-market`. Staged explicitly (`tests/_bids.py`,
`tests/unit/test_bids.py`, `tests/parity/test_market_nodal_vs_pandapower.py`), never `git add
-A` — S6 (`m4-s6-jobs`) was working concurrently in the same shared worktree on disjoint
`jobs/*.py` files; `git status --porcelain` was checked before every commit and S6's own files
were left untouched. S6's commit (`df565c6`) had already landed and been pushed by the time
this slice pushed; the push was a clean fast-forward (`df565c6..5442465`), no rebase needed.

## Out of scope, confirmed untouched

`opf/dc_opf.py`, `market/nodal.py`, `jobs/*.py`, `docs/*` — not modified by this slice.
