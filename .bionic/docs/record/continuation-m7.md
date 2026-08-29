# Continuation — M7 agents closed

Wave M7 (`agents`), triple build · audited · wave, integration branch `epic/01-foundation`
(base `6ca9dcc`).

- **Merge SHA:** `473b718` (`--no-ff`, local; wave head `0a4ce41`, tree byte-identical, 33 commits,
  36 files, +6202/−184)
- **Suite:** 1175 passed / 4 skipped (992 at M6 close → 1175, **+183**)
- **Gates at the wave head, one named sweep — the full list CI runs:** 1175/4 in
  179.69s; `ruff check` all passed; `ruff format --check` 179 files; `mypy` clean on 54 source
  files; `mkdocs build --strict` exit 0. The 4 skips are M6's parity module's elastic-only tests on
  fixed-load parameters. Log: session scratchpad `gate-0a4ce41.log`. Earlier sweeps this wave, each
  at its own named head and each recorded in the plan: `ec8876e` (one format failure), `852dd38`
  (2 failed — a commit that shipped tests without its source), `47b52da`, `12aa3ce`, `9739be8`.
- **Independent verdicts at the head or at a byte-identical predecessor:** audit 8 DISCHARGED /
  0 PARTIAL / 0 REFUTED (`m7-audit.md`, final pass at `12aa3ce`, AC-3 arrays md5-identical to its
  first run at `ec8876e`); critic **merge-ready as-is** (`m7-critic.md`, confirmation at `9739be8`);
  walk (`m7-walk.md`, at `ec8876e`, dispatched first and from the docs only) — its three defects
  are fixed and re-verified by the auditor on its own constructions. `0a4ce41` differs from
  `9739be8` by `docs/design/decisions.md` (ADR-010) and one changelog line.
- **Next wave:** M8 `interop` (free since M1). M9 `release` depends on everything.
- **Not pushed:** `epic/01-foundation` is local past `4cfd1d7`, per the M1–M7 convention that
  pushing the epic branch is the user's call. `wave/07-agents` is unpushed too, so no CI run exists
  for this head; every gate figure above is local.

## What M7 shipped

Generators that *offer* rather than reveal their cost, a market that clears the offers, and a loop
that runs until they settle — on the unchanged nodal DC-OPF. `market.strategy` (`Strategy`
protocol; `Observation` = own true cost, bounds, own last **two** rounds; `PriceTakerStrategy`
returning the true cost object itself; `MarkupStrategy`, a two-point fixed-step hill climb floored
at true cost with an idle rule; `StrategyConfig` discriminated union + `build_strategy`);
`market.solve_agents` + `MarketAgentsOptions` (simultaneous updates, offers as a coefficient overlay
through `gen_cost_coeffs`, round-0 offers collected up front so a strategy's refusal is a
`VALIDATION`-class `AgentSetError` before any clearing, a `TypeError` at the call site for a
non-cost return, PTDF computed once per run and passed to `dc_opf(ptdf=)`); `results.MarketAgentsResult`
(final round's nodal result, per-agent `AgentOfferResult`, `termination_reason` ∈ `converged |
iteration_cap | cycle` decided on the amplitude of the last repeated orbit against `offer_tol ≥
3 × step`); `market/_clearing.py` (one clearing-rows construction shared by nodal and agents);
`MarketNodalResult.branches` (M5 A23 closed on the nodal side); `opf/dc_opf.py`'s shared
`_pass_diagonal_hessian` (M6 carry 1 closed — three copies to one) and the generator-side
double-charge guard (a generator in `pwl_costs` with a nonzero coefficient row was charged twice,
silently, `Optimal`; on case14 that moved 223 MW to zero and the objective by +2409.70); the
`market.agents` jobs kind (`KINDS` == 8); `run_json` rejecting a duplicated JSON key at any depth as
`BAD_REQUEST` naming key and path, every kind. Docs: manual page, API pages, example 12, ADR-010.

## Carry-overs into M8

1. **The tie band cannot be sized** (`_PROFIT_TIE_REL_TOL = 1e-9`, spec A9 as corrected): tie-deciding
   noise scales with the step (2.5e-8 relative at 0.5, 2.7e-7 at 2.0) and the real one-step profit
   change with its square (1.8e-7 at 0.01), so the bounds cross. The verdict is safe under the
   `3 × step` floor, but any *adaptive-step* strategy inherits the problem and must state its own
   settling amplitude. Not an M8 item; a standing limit for whoever adds a strategy.
2. **`MarkupStrategy` cannot attach to any committed fixture** (C3): all 147 MATPOWER generators are
   quadratic. The wave's economics run on hand-built linear networks in `tests/_agents.py`. A
   markup rule for a quadratic true cost (mark up the linear term? scale the curve?) is a design
   decision, not a patch — it decides what "markup" reports.
3. **The branch-flow derivation is at three sites** (C1): `opf/__init__.py`, `market/_clearing.py`
   (now the nodal/agents site), `redispatch.py` in constant-folded form. Two of the three are one
   after this wave's refactor; the redispatch form is the remaining seam, on ADR-008's reasoning.
4. **Pre-M7 test blindness to the demand Hessian entry** (audit note 5): halving it reddens only
   zonal tests and the new multiperiod hand oracle; `dc_opf`'s and nodal's own modules do not see
   it. A bid-side hand oracle in `test_opf_dc.py` is cheap.
5. **`MarketZonalResult` carries no corridor rows** (M6 carry 2) — untouched by M7.
6. **`c0` is zero on every fixture** (M5/M6 carry 5) — untouched. M6 carries 4 (per-zone shunt) and
   6 (`in_service` dead in `tests/_zones.py`) — untouched.
7. **AC-8's pin is loose by four orders** (C2, defended): `abs=1e-9` MW against a measured 8e-14
   residual, kept because of M5's macOS one-ULP CI failure. If M9's CI runs on three platforms,
   this is where a platform disagreement would first show.

## The M7 lessons worth carrying

1. **The same defect class, three times, on both sides of one boundary.** A comparison exact in
   arithmetic and decided by float noise: strict `<` on profit (false `converged`), `<=` on
   amplitude at `2 × step` (false `cycle`), exact `== 0` for idle (missed solver dust). Every
   comparison on solver output now carries a named tolerance constant with its reason — and the
   one that cannot be sized says so in the spec rather than pretending.
2. **A derived constant is derived from the worst orbit, not the typical one.** `2 × step` was
   measured on fixtures whose optimum sat on a grid point; the half-grid case needed three. The
   validator *recommends* the floor, so the recommendation must be the safe one.
3. **The walk found what eight criteria and 1146 tests could not** — a documented entry point that
   did not exist, the first mistake every fixture invites leaking as `INTERNAL`, an undispatched
   agent climbing to the cap. Dispatch it first, from the docs, forbidden the spec.
4. **A report's green is a claim about a working tree; the commit is a different object.** S10
   reported green and a sabotage, then committed tests without their source (F16). Check every
   slice's `git show --stat` against the files the brief named; the named sweep is the only figure
   that speaks for a head.
5. **A queued message to an agent that has handed back is a dispatch** (F17): S10 woke on a
   one-line follow-up and amended a commit it did not author. Stop an agent when it reports, or
   don't touch its worktree until it acknowledges; briefs now say *never amend or rebase*.
6. **The review layers were the check on the orchestrator's own commits, three times** — the
   critic found nits in the F16 repair, then a regression in the fix of those nits (F19). The
   orchestrator's commits get the same review as a slice's.
7. **Measure the at-risk assumptions before dispatch, then re-measure the fix.** A1–A5 were all
   resolved by probe at Step 2; the first A1 fix (round-robin) was aimed at dynamics the own-node
   observation cannot compute and was reverted on the second look. "Anymore fix needed?" was the
   right question.
8. **The condition travels with the claim** (F4, F5, F12): three times a rule restated from memory
   dropped its qualifier — a `- 1e-9`, a condition on a docs fix, what the guard actually guards.

## Process notes for M8

- **`.bionic/` has no backup and was lost once (F20).** It is gitignored by design, and at M7's
  close an `rm -rf` on the worktree followed a junction into it. It was rebuilt from the Claude Code
  transcripts (replay script in the session scratchpad: `replay_unified.py`). Decide whether to
  commit `.bionic/docs/` (specs, plans, records are the epic's evidence) or mirror it; until then,
  remove worktrees with `git worktree remove --force`, never `rm -rf`.

- Baseline on a clean checkout before any agent enters the worktree (A14); one agent in the worktree
  at a time; measurement from `git archive` overlays with `__file__` proven (A16); verify each
  slice's commit `--stat` (F16); stop agents on hand-back (F17).
- Walk first, from the docs, at a named head, artifact machine-checked for zero `AC-[0-9]`; audit
  and critic from archives, forbidden the slice reports; every finding fixed at the layer it lives,
  red → green → sabotage, then the sweep retaken at the new head — this wave took six sweeps.
- The plan's ledger has one row per dispatched unit and one entry per finding (F1–F19), assumption
  (A1–A9 design, A11–A18 process) and carry (C1–C4); the spec's A9 records its own correction.
