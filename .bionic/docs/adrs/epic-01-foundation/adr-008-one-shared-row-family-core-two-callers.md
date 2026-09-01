---
governing-skill: agent-skills:documentation-and-adrs
sdlc-step: 7
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
model_plan: see wave-05-multiperiod.plan.md
---

# ADR-008: one shared row-family core, two callers — and the contract that did not come with it

Status: accepted (wave M5, 2026-08-26; ratified in the Step 2 design interview as Decision D1,
"extract shared core; both call it").

## Context

ADR-006 split `opf.dc_opf` into an array-level LP builder and a `Network`-level wrapper so a market
wave could reuse the builder. ADR-007 then bound every later market mode to extend **that one
builder** with further column and row families rather than composing a second solver, and named M5,
M6 and M7 as inheriting the decision.

M5 is the first wave to test that binding under real strain, because it is the first to add rows
that couple *across* periods — a ramp row tying `t` to `t-1`, and a state-of-charge row tying the
whole horizon into one energy budget. The Step 2 design interview put the fork plainly: put the
T-loop inside `dc_opf` itself, or extract the row families into helpers that both a single-period
and a multi-period caller invoke. **D1 chose extraction.** S1 pulled `_balance_row`,
`_flow_limit_rows`, `_epigraph_rows`, `_hypograph_rows`, `_add_rows`, `_dense_csr` and `_RowBlock`
out of `dc_opf` as a pure refactor touching exactly one file and no test, and S4's
`multiperiod_dc_opf` calls them unmodified.

## Decision

**The row families are shared, and that half of ADR-007 holds in substance, not merely in form.**
The evidence is a sabotage rather than a reading: sign-flipping the shared `_flow_limit_rows` inside
`dc_opf.py` takes **18 tests red across five files** — `test_opf_dc` (2), `test_opf_dc_demand` (1),
`test_market_nodal` (1), `test_opf_multiperiod` (5), `test_market_multiperiod` (9). One helper, both
surfaces. Independently, breaking `_balance_row`'s withdrawal coefficients takes both the nodal and
the multiperiod market red together. These are not two implementations that happen to agree; they
are one implementation with two callers.

**But ADR-007's two stated *consequences* did not survive the extraction, and this ADR records that
they are now duplicated rather than shared.** ADR-007 claimed that the double-counting contract
lives inside `dc_opf` so that "a caller cannot get this wrong, because a caller cannot do it at
all", and that the convexity guards are symmetric and enforced in one place. Measured at the wave
head, `dc_opf.py:560-627` against `multiperiod.py:322-390` is **54 identical lines out of 68/69, a
difflib ratio of 0.788** — the cost-coefficient shape check, the load-index range check, the
`v2`/`v1`/`v0` bid fill, and both `NonConvexCostError` / `NonConcaveBidError` guards with
hand-edited message text. The Hessian block and the fixed-load/`const` arithmetic are duplicated
alongside it, and `MultiperiodDuals` carries its own hand-maintained row-offset sum, so "one
dual-extraction path" is no longer literally true either.

**This is not a stylistic observation. The safety property ADR-007 asserted is precisely the one
that failed.** M5 shipped with a `Period.load_p_mw` override on a bid-carrying load being a complete
no-op: the per-period value was subtracted from the fixed-load total correctly, but the elastic
column's upper bound stayed at the network's base `Load.p_mw`, so the override cancelled itself
exactly. That bug lived in the **duplicated copy** of the double-counting contract — the copy
ADR-007's reasoning said could not exist. It was caught by the six-axis review, not by the eight
acceptance criteria, four slice-level sabotage sweeps, or the audit.

**Therefore: M6 unifies the extraction-and-validation preamble into one shared helper before adding
zonal redispatch's row families.** Not after. ADR-007 already names M6 as inheriting this seam, and
M6 would otherwise make the duplication a third copy — at which point the marginal cost of
unification is paid three times over and the odds of a third divergent bug rise accordingly.

## Consequences

1. **The row-order contract is now guarded by an assertion, and that assertion is the whole guard.**
   `multiperiod_dc_opf` asserts `h.getNumRow() == expected_rows` before reading any dual. This was
   added because the row order is declared in a docstring table, implemented in one place, and
   re-derived as a hand-maintained running sum ~150 lines away, with nothing tying the three
   together. Its necessity is measured, not assumed: appending a spurious row family after tier 6
   fails 56 tests with the assertion present and **63 pass with it disabled**. Any wave adding a row
   family must update the expected-row sum, and will be told loudly if it does not.

2. **A sabotage applied to shared fixture data is not a sabotage.** M5 spent three rounds of review
   accepting that the AC-6 parity fixture "cannot tell the two storage efficiencies apart", because
   the probe transposed the constants in `tests/_storage.py` — which the PyPSA oracle bridge reads
   too, via `efficiency_store=unit.efficiency_charge`. That relabels both sides of a parity
   comparison at once. Transposing the **engine's** SoC row with the oracle held fixed takes the
   committed file red at 5.088e-2 MWh against a 1e-2 tolerance. For every future parity test: the
   sabotage must be applied to the side under test, and the residual that moves must be one the
   assertion actually reads. Here only the SoC trajectory diverged, because `eta_c * eta_d` is
   symmetric and every other quantity agreed by construction.

3. **`Period`'s shape is the wave's weakest element and M6 should expect to revisit it.** Two
   independent defects landed on it: the bid-load no-op above, and a validator that rejected
   negative per-period loads while the `Load.p_mw` it overrides has no lower bound — so the identity
   profile raised `ValidationError` on case300, which ships 8 negative loads and which
   `market.solve_nodal` clears without complaint. Both are fixed. The design lesson generalises
   beyond this field: **an override must be at least as general as the field it overrides**, and
   D2's justification that a per-load override is "strictly more general" than scalar scaling was
   false on one of six fixtures until it was made true.

4. **`Scenario.periods` needs a `max_length` in the model, not a bound in a future HTTP layer.**
   Nothing is network-facing today, but `SolveRequest` is a pydantic model whose purpose is to be a
   wire format, and a 33,997-byte request expands to 20,088,000 matrix nonzeros — a ~7,000x
   amplification with a decompression-bomb shape. Added after the model is treated as stable, the
   bound becomes a breaking change.

## Alternatives considered

**Put the T-loop inside `dc_opf` itself.** Rejected at the design interview: it makes every
single-period caller pay for horizon machinery it does not use, and it would have made S1's
behaviour-preservation proof — M4's complete unmodified 654-test suite passing against a tree
differing in exactly one file — impossible to state, let alone run.

**Compose a separate multiperiod solver.** Refused by ADR-007 outright, and this wave supplies the
evidence for why that refusal was right: the two surfaces are provably one implementation, and the
single place they diverged is the single place where code was copied instead of called.

**Unify the preamble now, inside M5.** Rejected on sequencing, not on merit. The wave had already
passed its audit and both folds when the duplication was measured; refactoring shared validation
across two solvers is a substantive change that deserves its own slice, its own behaviour-preservation
proof of the kind S1 produced, and a wave whose acceptance criteria cover it. Doing it in a fold,
after the verification matrix had been discharged, would put an unproven change under a green matrix
— which is the exact failure mode this process exists to prevent.
