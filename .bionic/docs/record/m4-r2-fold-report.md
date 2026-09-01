# M4 / Step 6 — R2 fold report

Folds the Step-6 findings from `m4-review-6axis.md` (stance 1, six-axis) and `m4-critic.md`
(stance 2, adversarial critic) into `wave/04-nodal-market`. Base `f5e20d9` (the R1 fold).
Worktree `C:\Claude Projects\mambo-power-m4`.

**Authorship note (non-response procedure).** The `m4-r2-fold` senior-implementor was dispatched
in the previous session and completed items A, B and C, leaving them **uncommitted** in the
worktree; it went idle before item D and did not survive the session boundary. Per the
non-response procedure, a writing agent is never resumed: the orchestrator examined its output
directly (`.bionic/tmp/m4-r2-progress.md` plus `git diff`), independently re-verified A/B/C
against the full suite before building on them, took over item D, and stood the agent down. The
ledger row is updated to reflect the split. Nothing the agent wrote was changed — A/B/C are its
work, verified, not rewritten.

## Items

### A — share the generator-cost extraction (review Duplication FLAG, P1)

`market/nodal.py`'s `_gen_cost_coeffs` was a byte-for-byte duplicate of `opf/__init__.py`'s
module-private `_cost_coeffs`, disclosed in its own docstring but not architecturally justified.
Folded by renaming `_cost_coeffs` to the exported `gen_cost_coeffs` (added to `opf.__all__`, with
a docstring paragraph saying why it is public), importing it in `market/nodal.py`, and deleting
the copy along with the now-dead `FloatArray`/`PwlCosts` aliases and the `numpy`/`numpy.typing`
imports only that dead function used.

Pure refactor — zero test edits. 228 tests across `test_market_nodal`, `test_opf_dc*`,
`test_opf_solve_dc_opf` and `tests/parity` pass unchanged.

### B — 3+-segment concave PWL demand-bid test (review Correctness flag, T1)

Every committed PWL demand-bid test used exactly 2 segments, so `_concave_pwl_segments` — a
literal sign-mirror of the generator-side `_convex_pwl_segments`, which *is* 3-segment-tested —
was never exercised past 2 anywhere in the suite. Added
`test_demand_pwl_bid_with_three_segments_lands_at_an_interior_optimum` to
`tests/unit/test_opf_dc_demand.py`, built from the review's own probe (1-bus, g0 at $15/MWh,
slopes 30/20/10 over `[0,10],[10,20],[20,30]`, expected interior optimum `d=20`, balance dual
15.0).

RED proven before GREEN: truncating `_concave_pwl_segments`'s input to the first 3 points (drops
the 2nd segment) failed the test (60.0 vs the expected 20.0 — demand ran past the dropped bound);
reverted, confirmed zero net diff to `dc_opf.py`, 11 passed.

### C — document the partial-capacity two-`Load` pattern (review flag, D1)

`Load.bid` covers a load's entire `p_mw` with no per-load partial split; the two-`Load`-entities
workaround was nowhere documented, flagged on both the correctness and readability axes. Added a
`Field(description=...)` on `Load.bid` (`model/entities.py`) and a matching two-sentence note in
`docs/manual/market.md`'s "Using it" section. `tests/unit/snapshots/network.schema.json`
regenerated (`MAMBO_UPDATE_SNAPSHOTS=1`) — the diff is exactly the new description string,
nothing structural. `mkdocs build --strict` exit 0.

### D — AC-6 real power on all four sub-checks (critic Issue 1)

**The finding.** `m4-audit.md` §2/§3 established that three of AC-6's four parity sub-checks are
decorative on case14: because `tests/_bids.py`'s fleet-ceiling anchor rule floors every derived
bid above the achievable clearing price, every bid load is pinned at its own `p_mw`, so a
dispatch-quantity check cannot distinguish a correct solve from a double-counted one — the bound
pins the answer either way. Both the audit and the R1 fold accepted this as structural to the
anchor-rule strategy. The critic proved it is not, and that a one-load fix closes it.

**The fold.** `tests/_bids.py` gains a second, narrowly-scoped derivation path beside the
existing one, which is unchanged and still the default for every other load:

- `baseline_clearing_price(net)` — the highest bus LMP from a plain **fixed-load**
  `opf.solve_dc_opf` on `net` (`solve_dc_opf` ignores `Load.bid` entirely, so this is
  well-defined whether or not `net` already carries bids). Measured on case14: **39.0162 $/MWh**,
  uniform system-wide (case14 rates no branch, so no congestion is structurally possible).
- `interior_bid_for_load(net, load_id)` — marginal value descending linearly from
  `INTERIOR_TOP_MULTIPLE * baseline` (2x) at `p=0` to `INTERIOR_FLOOR_MULTIPLE * baseline` (0.5x)
  at `p = load.p_mw`. The floor is strictly below the baseline price and the top strictly above
  it, so the load's own optimality condition (marginal value == its bus LMP) is met **strictly
  inside** its domain, and that quantity moves whenever the balance RHS moves. Anchored to data
  the fixture already carries, the same discipline `fleet_max_marginal_cost` established — no
  invented magic numbers.
- `with_bids(..., interior_load_ids=[...])` applies it to a named subset, rejecting an id outside
  the bid set rather than silently ignoring it (a typo there would quietly restore the
  all-price-taking fixture the caller was avoiding).
- Shared `_load_or_raise` factored out of `bid_for_load`, since both rules reject the same two
  unusable inputs.

`tests/parity/test_market_nodal_vs_pandapower.py` now builds case14 with `INTERIOR_LOAD_ID =
"load-9"` (29.5 MW) interior-anchored and the other ten fleet-anchored. Measured result:

```
load-9: p = 20.017601430 MW  (cap 29.5)  bound_dual = 0     <== interior
the other ten: each at its own committed p_mw exactly, bound_dual = -51.68
system LMP: 38.31996 $/MWh (uniform)
```

**Power, measured not asserted.** Revert-and-watch, performed directly by the orchestrator:
stubbed out `dc_opf.py`'s own double-counting subtraction (`if n_demand:` -> `if False:`, the
elastic loads' own contribution no longer removed from the fixed aggregate) and re-ran the same
oracle comparison.

| sub-check | measured residual, correct code | with the subtraction stubbed | pinned tolerance |
|---|---|---|---|
| dispatch (worst over 11 loads) | 1.006e-5 MW | **1.569 MW** (`load-9`) | 1e-3 MW |
| LMP (worst over 11 buses) | 1.797e-5 $/MWh | **3.114 $/MWh** (`load-4`) | 1e-3 $/MWh |

The dispatch sub-check goes from *undetecting* (7.14e-10 MW residual, unchanged by the bug on the
all-price-taking fixture — the audit's own finding) to **~1,570x over tolerance**. That is the
gap closed: all four sub-checks now have genuine power against the double-counting bug, on the
real pandapower-cross-validated fixture rather than only on AC-4's hand-built network.
`src/mambo_power/opf/dc_opf.py` was restored by `git checkout` immediately after the measurement
and re-confirmed byte-identical (`git diff --stat` empty, `grep REVERT-AND-WATCH` -> 0).

**Tolerance re-pin.** `DISPATCH_ABS_TOL_MW` moves `1e-6 -> 1e-3`. This is not a loosening to make
a test pass: the old figure was calibrated against a fixture where every dispatch was
*bound-pinned* (residual 7.14e-10, essentially exact by construction), and the new one is
calibrated against a genuinely solved interior quantity (residual 1.006e-5, HiGHS-vs-pandapower
solver tolerance). ~100x margin over the measurement, matching `LMP_ABS_TOL`'s own discipline.
Both figures and their derivation are written into the test module's docstring.

New/changed tests: `test_the_interior_anchored_load_clears_strictly_inside_its_own_bound` (three
independent ways: strictly inside both ends with a >5%-of-cap margin, a zero bound dual, and
agreement with the independent sgen oracle on that same interior quantity);
`test_every_bid_load_is_fully_price_taking_on_this_fixture` renamed to
`..._every_fleet_anchored_bid_load_...` and now asserts it excluded exactly the one interior load;
six new unit tests in `tests/unit/test_bids.py` proving the new rule's own guarantees (brackets
the baseline, genuinely concave, rejects an unknown load, subset-only application, stray-id
rejection) and `baseline_clearing_price` pinned against a direct fixed-load solve.

## Carried, not folded

Critic Notes 2-5 are all confirmations, not findings — the R1 fold's disclosed scope widening,
S5's delayed-message case, the elastic-demand cost formula, and `Load.bid`'s placement were each
independently re-verified sound and need no change. The critic's own three failed falsification
attempts likewise close clean.

`m4-critic.md`'s §3 observation that case14 rates no branch — so no fixture in this wave proves
the settlement identity under *simultaneous* congestion and elastic demand against an independent
oracle — remains as disclosed. It is a carry-over of M3's fixture set (`m3-research.md` §6), not
something M4 introduced, and AC-4's hand-built network covers the interaction against `dc_opf`'s
own arithmetic. Logged in the plan's `## Assumptions` as an M5 candidate, not closed here.

## Verification

All run on the folded tree, worktree `C:\Claude Projects\mambo-power-m4`:

```
uv run --no-sync pytest -q -p no:cacheprovider   -> 654 passed  (0:01:03)
uv run --no-sync ruff check tests/ src/          -> All checks passed!
uv run --no-sync ruff format --check             -> 56 files already formatted
uv run --no-sync mypy                            -> Success: no issues found in 43 source files
uv run --no-sync mkdocs build --strict           -> exit 0, built in 15.92s
examples/*.py (9 scripts)                        -> 9/9 exit 0
uv build                                         -> wheel + sdist built
```

**Test-count reconciliation.** 646 (R1 fold, `m4-step5-tests-floor.md`) + 1 (item B, 3-segment
demand bid) + 1 (item D, interior-clearing parity test) + 6 (item D, `tests/_bids.py` unit tests)
= **654**. Item A added none by design (pure refactor); item C added none (the schema snapshot
test already existed and was regenerated, not added).

## Scope discipline

Items A and C touch no test-covered behaviour; item B is test-only; item D changes only
`tests/`. No `src/` behaviour changed anywhere in this fold — `market/nodal.py`,
`opf/__init__.py` and `model/entities.py` are edited for the shared helper, its export, and a
field description respectively, all behaviour-preserving. The `auditor-wave: CONFIRMED` verdict
and every row's `auditor` column stand unchanged; this fold strengthens AC-6's evidence and does
not re-open its verdict.
