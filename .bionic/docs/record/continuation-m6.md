# Continuation — M6 zonal-redispatch (DRAFT — header numbers filled at Step 9 close)

Wave M6 (`zonal-redispatch`), triple build · audited · wave, integration branch `epic/01-foundation`
(base `4cfd1d7`).

- **Merge SHA:** (filled at close)
- **Suite:** (filled at close; 816 at M5 close → 990 at fold-a's `6edf7f6`, +174, before the last two
  follow-ups)
- **Gates:** ruff, `ruff format --check`, mypy (50 source files), `mkdocs build --strict` — all clean
  at every head the orchestrator measured
- **Next wave:** M7 `agents` (depends on M4; M5 and M6 both done). M8 `interop` available since M1.
- **Pushed:** (the user's call, per the M1–M6 convention)

## What M6 shipped

Zonal market clearing chained with min-cost redispatch and a nodal-vs-zonal comparison, on the one
array-level LP builder. `opf.zonal` (per-zone balance rows, one bounded exchange column per tied
zone-pair, no intra-zone flow rows; zone price = balance dual); `opf.redispatch` (Δ⁺/Δ⁻ columns per
generator and per bid load from a zonal point, **true cost/value curves** in the objective);
`market.solve_zonal` + `MarketZonalResult` — the first market result carrying `OpfBranchFlowResult`
rows, closing M5 carry-over A23; the `market.zonal` jobs kind (`KINDS` == 7); `Scenario.periods`
`max_length = 200` and `MarketZonalOptions.corridors` `MAX_CORRIDORS = 500`; `tests/_zones.py`
(case30's AREA column promoted to `Zone` entities at test time, corridor caps from `tests/_rated.py`);
PyPSA one-bus-per-zone + `Link` parity with the oracle held fixed and a committed negative control.
And first: ADR-008 executed — the extraction/validation preamble is one implementation in `dc_opf.py`
with four callers (55 identical lines → 12, all local-name binding).

**ADR-009** records D1 and what follows from it: the redispatch LP reproduces the nodal optimum by
construction, so the comparison measures the *repair* (redispatch volume and payment, zonal prices vs
LMPs), not a gap; the falsifiable statement about the zonal approximation is the relaxation inequality
`welfare(zonal) ≥ welfare(nodal)`, conditional on the caps.

## Carry-overs into M7

1. **Diagonal-Hessian assembly is a third verbatim copy** (`dc_opf` / `multiperiod` / `zonal`;
   `redispatch`'s two-column form is genuinely different). ADR-008's reasoning one level down; unify
   before adding the agents' columns, with an S1-style overlay-tree proof.
2. **`MarketZonalResult` carries no corridor rows** — corridor flow and capacity price are readable
   only at the array level. The A23 shape again; a `CorridorFlowResult` row is the M7 candidate.
3. **AC-4-style exactness rows are structurally blind to the zonal stage** (review C3/C4): under D1
   the redispatched point is nodal from *any* start, so breaking the zonal LP leaves every final-point
   assertion green. Only zone prices, corridor flows and oracle parity see it. Keep those rows
   separate in any wave that chains solves; do not let an end-to-end row stand in for a stage row.
4. **The per-zone shunt term is never exercised** — case30's `g_shunt` is identically zero and only
   case300 parity catches a dropped shunt. A hand-built shunt-bearing 2-zone fixture is cheap.
5. **`c0` is zero on every fixture** (M5 carry, widened): the extractor-vs-raw agreement test compares
   two zeros. The 12-line `c0` test M5's critic wrote is still uncommitted.
6. **Nothing in M6 touches `in_service`** — `tests/_zones.py`'s out-of-service branch is dead in every
   test. Two single-assertion paths: the demand half of `redispatch_payment` (the hand fixture moves
   no elastic demand) and the redispatch PWL linking row.
7. **Two more A34-shaped shared inputs without a demonstration**: `tests/_bids.py`'s curves are
   derived by running a mambo `solve_dc_opf`, and `tests/_zones.py`'s partition reaches both sides of
   the parity. The caps have their negative control; these two do not.
8. **`market.agents` is M7's kind, and this wave defused the trap it would have sprung**: the
   unknown-kind demos in `jobs.md`, `test_jobs.py` and example 04 now use a fictional `pf.telepathy`.
   Registering `market.agents` will not break them. (It broke example 04 this wave when
   `market.zonal` was registered — A25.)
9. **A Windows cp1252 landmine in the docs pipeline** (A33): mkdocstrings formats attribute
   signatures through an external formatter's stdin encoded cp1252; any non-Latin-1 character in a
   rendered default crashes `--strict`. The griffe extension sidesteps it for `Field(...)` defaults
   only.
10. **API pages site-wide still carry bare step labels from M2–M5 docstrings** (M5 walk D10, M6 walk
    D5); M6's own were stripped in the fold. The older waves' remain.
11. **The `sold` vs `delivered` trap**: `MarketZonalResult.generators` is the zonal (sold) schedule;
    `MarketNodalResult.generators` is delivered dispatch — same field name across a closed union.
    Documented; M7's result types should pick one meaning for the name.

## The M6 lessons worth carrying

**A check that a sabotage cannot move is not a check.** The orchestrator replaced AC-4's LMP clause on
a degenerate fixture with "priced ⊆ at-rating" and recorded the anchored-rate sabotage leaving it
green as *success* ("the property does not depend on the objective"). The audit read the test at
source: complementary slackness, satisfied by any optimal solution, carrying no information. It was a
waiver dressed as a clarification. The fold replaced it with a two-solve comparison on the
non-degenerate face that the same sabotage now takes red.

**Two quantities plus an identity are not three fields.** `generation_cost_gap` was `−redispatch_payment`
to 2.6e-11 on fixed load; the third field's only independent content was the curtailment compensation.
The audit measured it; the fold asserts the identity instead of "they differ".

**The chain's own ruling that a finding is "structural" is the thing to attack.** Third wave running
that the independent auditor or critic overturned an orchestrator ruling (M4's fixture claim, M5's
A20, M6's A20). The pattern is stable enough to name: when the orchestrator writes "not a waiver" or
"cannot be tested", that sentence is the next audit's first target.

**Fold, don't disclose — and the fold is where the decisions surface.** Fold-a refused to make two
calls alone (a non-JSON token on the wire; an error-code policy) and was right to; both were the
orchestrator's, both were made in one message, and both would have been wrong by default.

**Root causes hide behind "that's how it's always rendered".** Result-model fields had never rendered
on the API pages — not since M1 — because griffe reads attribute docstrings and pydantic puts prose in
`Field(description=...)`. Five waves shipped result types nobody could read the fields of; M6 was the
first whose result a reader had to *construct inputs from*, so the gap became load-bearing. The audit's
wave-level finding was exactly this: W8 had no design decision, and "where do this type's fields reach
the reader" is a design question.

**A walk gate reports against a head.** The head moved twice during the walk and nobody told the
walker (A30). It re-verified on its own initiative. Rule: dispatch the walk against a named head, ledger
it, and message the walker on any commit that lands during it.

**Silent-plausible beats loud-infeasible, again.** A duplicate corridor pair *cleared* (last wins);
`energy_mwh = 0` cleared Optimal last wave. The worse failure mode each time is the one that returns a
confident answer.

## Process notes for M7

- **Worktree setup**: `uv sync --all-extras --all-groups`, then prove `uv run --no-sync mkdocs
  --version` before dispatching any docs or walk agent (A27 — the venv lacked the docs group and the
  gate run failed with an unexplained exit 2 beside a green suite).
- **Split findings need an owner and a check** — held this wave (A25: found by S7b, owned by S8,
  checked by the orchestrator before S8 was marked done).
- **The report gate keeps inverting** (research, audit both wrote before messaging). Harmless when the
  artifact is on disk; A9's check-the-disk rule is what makes it harmless.
- **Ownership by path held across two concurrent folds** — 14 commits interleaved on one branch, zero
  collisions, verified per commit. The one cross-ownership item (D1 citations made visible by
  fold-b's rendering fix) was relayed, not fixed across the line.
- **`stop-guard.sh`'s Windows-path bug is still open**; finished agents idle.
