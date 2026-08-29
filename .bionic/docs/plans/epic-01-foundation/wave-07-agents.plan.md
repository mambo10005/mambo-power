---
governing-skill: superpowers:writing-plans
sdlc-step: 9
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
rigor-floor: audited
walk: required
design-interview: true
cleaned: 2026-08-29
model_plan:
  orchestrator: fable-5
  implementor: sonnet
  senior-implementor: opus
  researcher: sonnet
  test-runner: sonnet
  auditor: opus
  critic: opus
---

# Wave M7 — agents — plan

Spec: `specs/epic-01-foundation/wave-07-agents.spec.md` (carries `## Design`).
Scope + design ledger: `record/m7-scope-closure.md`. Research: `record/m7-research.md`.

## SDLC State

integration-branch: epic/01-foundation
intent: build
rigor: audited
scale: wave
current: 9 — shipped; merge `473b718`

- Step 0: prereqs: ok; configured 2026-08-28 via "confirm"; model_plan=fable-5/sonnet/opus;
  integration-branch=epic/01-foundation; base 6ca9dcc
- Step 1: record/m7-scope-closure.md (three scope answers, Not Doing, prior art, process notes)
- Step 2: specs/epic-01-foundation/wave-07-agents.spec.md (W1–W8, AC-1..AC-8 with provenance,
  `## Design` ratified 2026-08-28 after D1–D3 walked one at a time, D4–D7 surfaced at ratification)
- Step 3: plans/epic-01-foundation/wave-07-agents.plan.md — awaiting the approval checkpoint.
  **A1 and A2 were resolved by measurement before the checkpoint** rather than carried in as
  at-risk assumptions (record/m7-scope-closure.md, "A1 and A2 resolved"): A2 confirmed the overlay
  needs no `dc_opf` signature change *and* uncovered a missing generator-side overlap guard (now
  W1(c)/AC-1(c)). **A1, A3 and A4 were then also resolved by measurement** — A4 was false (a
  one-round own-node observation cannot support a walk; two rounds can), A3 was over-cautious
  (AC-3(b) is exact, not tolerance-bounded), and A1 turned out to have measured *exact* best
  response, which the shipped agent cannot compute. AC-4's and AC-5's numbers are now the wave's
  own, reproduced through its own clearing. Reproduction scripts in `.bionic/tmp/m7-a*.py`
- Step 4: worktree: `C:\Claude Projects\mambo-power-m7`; base-sha `6ca9dcc`; branch `wave/07-agents`
  — pre-existing from Step 0, **verified rather than assumed** at dispatch: tree clean at
  `6ca9dcc`, `.bionic` junction live (the M7 spec is readable through it), venv synced, and all
  four gate tools proven (`mkdocs` 1.6.1, `ruff` 0.16.4, `mypy` 2.3.1, `mambo_power` + `highspy`
  importable) — A11 satisfied *before* any dispatch. Approved by the user 2026-08-28 ("go").
  S1, S2, S3, S6 dispatched concurrently on disjoint path ownership.
  **Orchestrator error, caught and corrected the same hour (A14 below):** the base-suite baseline
  was started in the worktree and the four slices were dispatched into it *while it ran*, so it
  measured a moving tree and returned `1 failed, 991 passed`
  (`test_examples_run.py::[11_zonal_redispatch]`) — a number about nothing. Re-measured on the
  clean main checkout, also at `6ca9dcc`. All four slices were messaged with shared-worktree
  discipline: never `checkout`/`stash`/`restore`/`clean`; commit own paths early; a red outside
  your ownership is reported, not fixed; take your own numbers against a clean `opf/` or a
  `git archive 6ca9dcc` scratch tree
- Step 5: walk-artifact: record/m7-walk.md (0 `AC-[0-9]` hits, at ec8876e); cmd: `uv run pytest -q -p no:cacheprovider` at 0a4ce41; pass: 1175; total: 1175 (+4 skipped); output: scratchpad gate-0a4ce41.log; auditor: record/m7-audit.md — 8 DISCHARGED / 0 PARTIAL / 0 REFUTED (final pass at 12aa3ce, byte-identical source to 0a4ce41)
- Step 6: critic: record/m7-critic.md — 19 findings across three passes, final verdict merge-ready as-is at 9739be8; every should-fix fixed at the layer it lives (S9–S11 + orchestrator commits), each red → green → sabotage
- Step 7: adr: docs/design/decisions.md#ADR-010 (commit 0a4ce41); continuation: record/continuation-m7.md
- Step 8: merge: 473b718 (--no-ff, epic/01-foundation, tree identical to 0a4ce41); worktree-removed: /c/Users/mambo/AppData/Local/Temp/claude/C--Claude-Projects-mambo-power/0d397067-49ef-4969-aefa-5709948393ef/scratchpad/bionic-unified (2026-08-29); cleanup: done; tmp-wiped: m7-* moved to record/m7-tmp/ (17 files — the spec and reports cite them as evidence), rest wiped; tasks-completed: all
- Step 9: deploy: n/a (deploy_target: none — library, unpushed by convention); verified-at: 2026-08-29T19:46Z sweep at 0a4ce41; monitor: n/a

## Slices

Worktree `C:\Claude Projects\mambo-power-m7`, branch `wave/07-agents`, base `6ca9dcc`, `.bionic`
junction in place. **Ordering constraint (spec W1, ADR-008 one level down): S1 lands and is proven
before S4 writes any agents column.** S2, S3 and S6 are independent of S1 and run concurrently
with it — ownership is disjoint by path, verified per commit as in M6.

| slice | scope | rows | complexity | role |
|---|---|---|---|---|
| S1 hessian-unification | W1: the shared diagonal-Hessian helper in `dc_opf.py`; `multiperiod.py` and `zonal.py` become callers; `redispatch.py` stays a non-caller; overlay-tree proof. **Plus W1(c)**: the generator-side mirror of the load-side overlap guard in `_extract_and_validate`, with the measured pre-guard silent wrong answer as its power proof | AC-1 | complex | senior-implementor |
| S2 strategy-seam | W2: `market/strategy.py` — `Observation` (own-node), the `Strategy` Protocol, `PriceTakerStrategy`, `MarkupStrategy`, `StrategyConfig` union + factory; round-0 shape explicit | feeds AC-3/4/5 | standard | implementor |
| S3 fixtures | W7: the **smooth** pivotal (900 MW @ $20 vs `q = 1000 − 10·price`), its non-pivotal control (900 MW rival @ $22), and the 300/300 duopoly — **re-measured through committed machinery; a disagreement with Step 2's numbers is a finding** | feeds AC-4, AC-5 | standard | implementor |
| S4 agents-loop | W3/W4: `market/agents.py` (overlay, simultaneous updates, **amplitude-classified** termination — converged vs cycle vs cap), `results/agents.py` (`MarketAgentsResult`, `AgentOfferResult`); generalise `gen_cost_coeffs` to take the cost source | AC-2, AC-5 | complex | senior-implementor |
| S5 economics | W5: AC-3's two clauses and AC-4's two fixtures, each with its own power proof | AC-3, AC-4 | complex | senior-implementor |
| S6 nodal-branches | W4 half: `MarketNodalResult.branches` + `pf.dc` agreement; JSON schema snapshot **checked, not assumed** | AC-8 | standard | implementor |
| S7 jobs | W6: `market.agents` kind, `KINDS` 8, the four caller-mistake mappings | AC-6 | standard | implementor |
| S8 docs | W8: manual, API pages, architecture, example + snippet, changelog, `jobs.md:267` fix | AC-7 | complex | senior-implementor |

Dependencies: S1 → S4; S2 → S4; S3 → S5; S4 → S5, S7; S6 independent; S8 last.

Every slice brief carries the standing rules, now six waves deep:

- **Sabotage sweep** over each new row family, naming the residual that *moves*; sabotage the
  engine, never shared fixture data (M5 A32 — an edit to `tests/_storage.py` moved both sides of
  the comparison and made a live check look dead).
- **A replacement or new check's power proof must show it red under a defect in the specific
  quantity the criterion names** (M6 A37/A39 — the epic's most expensive lesson; a sabotage that
  moves the whole solution lets every clause fire for the wrong reason).
- **Drive the test's own fixture factory**, never a hand-assembled reconstruction (M5, three times).
- **Never write "only" about a coverage set that has not been enumerated** (M6, ADR-009
  consequence 3 was false and contradicted its own consequence 1).
- **Report gate before bookkeeping**; progress artifact at 10m cadence; explicit-path commits only.
- **A finding split across two agents needs a named owner and a check** (M5's macOS CI failure).

## Verification Matrix

stack-health: before (M6 close, `6ca9dcc`): **992 passed / 4 skipped** — **independently
re-confirmed by this wave 2026-08-28** on the clean main checkout at that SHA (770.46s), not
carried forward from M6's own report. The first attempt returned `1 failed, 991 passed` because it
ran in the worktree while four slices edited it; see A14. `ruff check` clean,
`ruff format --check` 167 files, `mypy` clean on 50 source files, `mkdocs build --strict` exit 0,
11/11 examples. After: filled at the final wave head by **one named gate sweep** — `pytest`,
`ruff check`, `ruff format --check .`, `mypy`, `mkdocs build --strict` — taken as a single command
list at one head, never assembled ad hoc per check (M6 A38: a dropped format check let a red CI
gate through while the brief claimed all gates green).

**Pre-docs measurement, 2026-08-29, all seven source slices landed** (`8df221d`, before S8 phase 2):
**1142 passed, 3 failed, 4 skipped in 310.32s** — **+150 tests** over the 992 baseline. Taken on a
`git archive` overlay of `8df221d` with module resolution proved in-process, precisely so S8's
concurrent docs edits could not reach it (A14/A15/A16 applied to the orchestrator's own
measurement, having broken the same rule on this wave's first baseline). The three reds are
**exactly** the three `test_docs_registry_listing.py` rows of the tracked jobs.md split finding —
`jobs.kinds()` returns eight, the manual still lists seven — owned by S8 phase 2 and predicted by
the spec after S8 refuted the orchestrator's "one-line fix" claim. **Nothing else is red anywhere
in the wave.** This is not the wave's gate figure: the single named sweep at the final head, after
S8 lands and including `mkdocs build --strict`, is the number of record (A18, M6 A38).

**Named sweep at `47b52da`, 2026-08-29 18:36Z — the first fully green sweep of the wave, after S8, S9,
S10 and the F16 repair:** `pytest` **1159 passed, 4 skipped in 272.21s** (+167 over the 992
baseline; the 4 skips are M6's pre-existing fixed-load parametrisations), `ruff check` clean,
`ruff format --check` 178 files clean, `mypy` clean (53 source files), `mkdocs build --strict`
exit 0. Log: scratchpad `gate-47b52da.log`. Earlier sweeps this wave, each at its own named head:
`ec8876e` 1146/4 with one format failure (F13); `9b30e01` stopped when the walk's fixes were
dispatched; `852dd38` 1157/4 with 2 failed (F16). This figure stands unless the critic (Step 6)
moves the head, in which case the sweep is retaken there.

**Named sweep at `12aa3ce`, 2026-08-29 19:27Z — after S11 (the critic's should-fixes and nits)
and the two run.py nit fixes:** `pytest` **1172 passed, 4 skipped in 417.81s** (+180 over the 992
baseline), `ruff check` clean, `ruff format --check` 179 files clean, `mypy` clean (54 source
files — `market/_clearing.py` is new), `mkdocs build --strict` exit 0. Log: scratchpad
`gate-12aa3ce.log`. This is the wave's figure of record unless the critic's re-review or the
auditor's final pass moves the head.

**Sweeps at `9739be8` (19:40Z, after the critic's finding 11 — an iterative, flag-gated
duplicate-key walk) and at the final head `0a4ce41` (19:46Z, after ADR-010 — docs only): both
1175 passed, 4 skipped** (216.53s and 179.69s), ruff, format (179 files), mypy (54 files), mkdocs
strict all clean. **`0a4ce41` is the figure of record: 1175 / 4, +183 over the 992 baseline.**
Merged `--no-ff` as `473b718` on `epic/01-foundation`, tree byte-identical to the wave head.
Continuation: `record/continuation-m7.md`.

walk-artifact: `record/m7-walk.md` — dispatched **first** at Step 5, before any row below is
discharged; the walker is forbidden the spec, plan and slice reports, is dispatched against a
**named head** that is ledgered and messaged on any commit landing during the walk (M6 A30), and
the artifact is machine-checked for zero `AC-[0-9]` occurrences.

auditor-wave: pending. The auditor's brief says out loud that any orchestrator ruling of the form
"structural", "not a waiver" or "cannot be tested" is its first target — three waves running, an
independent reader has overturned exactly such a ruling (M4's fixture claim, M5 A20, M6 A20), and
in M6 the critic then overturned the *fix* for the overturned ruling.

| AC | tier | status | planned discharge |
|---|---|---|---|
| AC-1 | T1 | planned | (a) `git archive 6ca9dcc` overlay differing in exactly the unified files, `diff -rq` against a pristine archive, `__file__` proven into the overlay, M6's suite unmodified; (b) a per-caller sabotage of the shared diagonal, red in each of the three callers' test modules with the moving residual named; (c) the new generator-side overlap guard raises, and the pre-guard build reproduces the measured silent wrong answer (223.19 → 0.00 MW, objective +2409.70, status `Optimal`) |
| AC-2 | T1 | planned | serialize `Scenario` + `Network` before and after a markup run, compare bytes; assert every `Generator.cost` unchanged; **and** capture the coefficients the builder received and assert they differ from the true ones on that same run |
| AC-3 | T1 | planned | (a) `array_equal` on the offer coefficients for an all-price-taker config; (b) `array_equal` on dispatch and LMPs vs `solve_nodal` — measured bitwise-identical over five independent `dc_opf` constructions, so **no tolerance is introduced**. No short-circuit exists, so both clauses run the general path |
| AC-4 | T1 | planned | smooth pivotal fixture (900 MW @ $20, `q = 1000 − 10·price`): assert the climb reaches offer/price **$60.00**, **400.00 MW**, profit **$15,999.98** against the closed-form $16,000.00, and that `Load.bid` is the binding quantity (raise the bid, the peak moves); control (900 MW rival @ $22): assert offer **$21.50**, gain **$1,177.50** against the pivotal $15,999.92 — both numbers, neither a bound |
| AC-5 | T1 | planned | (i) `iterations > 1`, settled oscillation **amplitude 1.0** (two steps of 0.5) inside `offer_tol`, `converged is True`, `iterations == 84` on the 300/300 duopoly reaching offers `[60.0, 60.0]` at **$60.00**, joint profit **$15,999.98** vs **$11,999.96** at true cost; (ii) two shapes of non-convergence — `max_iterations` below that count → `termination_reason == "iteration_cap"`, and the "raise while at capacity" rule, whose amplitude spans the whole markup range → `termination_reason == "cycle"`, never the cap. `status` asserted independently of `converged` throughout |
| AC-6 | T1 | planned | `len(KINDS) == 8`; a `market.agents` request round-tripped through `run_json` (a JSON **string**, not a dict — M6's own slip); four caller mistakes each asserted to `BAD_OPTIONS`/`VALIDATION` with the message naming the offending input |
| AC-7 | T2 | planned | `mkdocs build --strict` exit 0; the **per-model** griffe field guard covering every new result and config model (M6 R2 — the total-failure guard let 129 fields vanish at exit 0); every example run; `jobs.md:267` diff shown |
| AC-8 | T1 | planned | `MarketNodalResult.branches` compared against `pf.dc` on the same solution at a pinned tolerance; the nodal and zonal rows asserted to be the same row type under the same field name; JSON schema snapshot regenerated **only if** `$defs` actually changes — checked, per A5 |

## Tasks

One row per dispatched unit, written at dispatch (status `active`) and completed at
execution-confirmation. This harness has no task-list tool (checked at Step 0), so this ledger is
the visible progress surface.

| id | role | unit | deliverable | status |
|---|---|---|---|---|
| m7-s1-hessian | senior-implementor | S1: shared diagonal-Hessian helper in `dc_opf.py` with `multiperiod`/`zonal` as callers, `redispatch` a non-caller; **plus W1(c)** the generator-side overlap guard. AC-1's three clauses: overlay-tree suite unmodified, per-caller sabotage, guard power proof (223.19 → 0.00 MW, objective +2409.70). Owns `opf/{dc_opf,multiperiod,zonal}.py` + `tests/unit/test_opf_*.py` | record/m7-s1-report.md + commits | **done** (`a22922d`; AC-1 discharged, the auditor's AC-1(b) partial closed by S10's multiperiod hand oracle — F15) |
| m7-s2-strategy | implementor | S2: `market/strategy.py` — `Observation` (own-node, **two** rounds of history), `Strategy` Protocol, `PriceTakerStrategy`, `MarkupStrategy` (two-point hill climb), `StrategyConfig` union + factory. Owns `market/strategy.py` + `tests/unit/test_market_strategy.py` | record/m7-s2-report.md + commits | **done** (commit `df3c849`, two files, +624; orchestrator-verified: exactly the two owned files). 24/24 own tests; 6/6 sabotage sweep with `strategy.py` diffed byte-identical after each revert. The PWL requirement I set was **met but unreported** — verified here: `PriceTakerStrategy` passes quadratic *and* piecewise costs through with **content** asserted (`coefficients`/`points`), not just type, and `MarkupStrategy` raises `NotImplementedError` on both. Fixed its half of the split finding (`test_docstrings` green); correctly left `test_api_docs_coverage` red for S8. **Amended at `aade93b`** (+129/-41, same two files) after orchestrator review found a real gap — see F1 below. **Fixed F4 at `20ba1e7`** (relative tie tolerance behind `_PROFIT_TIE_REL_TOL = 1e-9`, docstring and contract aligned). **30/30 tests, 8/8 sabotage across three commits.** Its guard pair is the right shape and worth citing as a pattern: both tests share the *same* zero-movement baseline and differ only in the disputed quantity — a ~5e-14 relative tie versus a real $3.00 drop — so reverting to the strict `<` reddens the tie test and leaves the companion green. That is a sabotage moving only what the criterion names, which is what M6 spent three attempts learning. Adopted the archive-overlay sweep rule (A16) and cited S4's cross-module witness in its own report. Carries C3 |
| m7-s3-fixtures | implementor | S3: `tests/_agents.py` — smooth pivotal, non-pivotal control, 300/300 duopoly; economics verified by **hand-set offers** (the loop does not exist yet), re-measured against Step 2's table. Owns `tests/_agents.py` + `tests/unit/test_agents_fixtures.py` | record/m7-s3-report.md + commits | **done** (commit `7083460`, two files, +526; orchestrator-verified: `git show --stat` shows exactly `tests/_agents.py` + `tests/unit/test_agents_fixtures.py`). All six spec-table rows reproduce through the real model classes; cross-checked against a clean `git archive 6ca9dcc` via `sys.path` override and **bit-identical** to the working-tree numbers, so the agreement is not a moving-target artifact (A14 honoured). AC-4's closed-form peak pinned independently of any solve ($60/400 MW/$16,000 vs the solver's $15,999.98). 5-point sabotage sweep, each with a hand-derived expected value. 15/15 own tests pass. `mypy` clean — but note its scope is `files = ["src"]` (verified, pyproject.toml:61), so it does **not** cover `tests/`; this slice's mypy result proves nothing about this slice's own code |
| m7-s4-loop | senior-implementor | S4: `market/agents.py` — `solve_agents`, simultaneous updates, amplitude-classified termination (`converged | iteration_cap | cycle`), `_settled` tie rule; `results/agents.py`. Owns `market/agents.py`, `results/agents.py`, `tests/unit/test_market_agents.py` | record/m7-s4-report.md + commits | **done** (`74a0532`; F6 fix `67d189e`). F6: `offer_tol == 2*step` at non-binary-exact steps (0.1, 0.2) reported genuine convergence as `cycle` while 0.5/0.25 converged — the validator recommended the exact value that failed. Fixed with `_settled` (`_AMPLITUDE_TIE_REL_TOL = 1e-9`), the same shape as S2's F4 fix on the other side of the same boundary. A18: its head-gate figure was stale (byte-identical across two reports either side of its own fix); the wave's gate is taken by the orchestrator, below |
| m7-s5-economics | implementor | S5: AC-3 price-takers reproduce `solve_nodal` bitwise (`array_equal`, F10), AC-4 pivotal markup stops at demand's bid vs closed form with the non-pivotal control, AC-5 duopoly. Owns `tests/unit/test_market_agents_economics.py` | record/m7-s5-report.md + commit | **done** (`8bc24e5`, 544 lines). Measured that a one-ULP offer perturbation moves the LP, so bitwise agreement is a claim about identical arrays, not insensitivity (F10) |
| m7-s7-jobs | implementor | S7: `market.agents` kind, `KINDS == 8`, `ResultModel` union widened, AC-6's four caller-mistake→`VALIDATION` mappings. Owns `jobs/{registry,models}.py`, `tests/unit/test_jobs.py` | record/m7-s7-report.md + commit | **done** (`8df221d`, +396 tests lines). F7: my ownership map omitted `jobs/models.py`; S7 stopped and asked, and corrected its own mechanism claim by running it (`run.py:198` guards → graceful `INTERNAL`, not an uncaught `ValidationError`). F9: reported a false finding against S4's `_settled` (mid-edit artifact; orchestrator re-ran, 9 passed). Left `test_docs_registry_listing` red for S8 as briefed |
| m7-s8-docs | senior-implementor | S8: phase 1 `docs/api/market.md` + `architecture.md` (`9ae56ed`); phase 2 `jobs.md` three sites, `market.agents`/`results.agents` API sections, `manual/agents.md`, `examples/12_agent_market.py`, changelog, nav, examples index, roadmap | commit | **done** (`ec8876e`). The agent did not survive the PAUSE (F11): it left four files edited and two created, uncommitted, with `mkdocs build --strict` already exit 0 and the docs tests 6 passed — but no nav entry, no examples-index row/section (the manual linked a `#12-strategic-bidding` anchor that did not exist), no changelog, roadmap stale. Orchestrator finished those four directly and re-ran the strict build (exit 0, no unlinked-page or dangling-anchor INFO lines) before committing. Example 12 runs: exit 0, 84 iterations, `converged` |
| m7-s9-walkfix | implementor | S9: the walk's three defects (F14) + prose + strategy-return check. Owns `market/{__init__,agents,strategy}.py`, `docs/manual/agents.md`, tests | record/m7-s9-report.md + 5 commits | **done** (`1de01e0` export; `d718053` `_initial_offers` — round-0 offers collected up front, `NotImplementedError` → `ValueError` naming the generator, so no duplicate strategy call; `a02dd2b` idle rule; `3686f2e` style; `c0cfd12` prose + `_checked_offer` `TypeError` at the call site). Economics file 21 passed before and after; each fix red → green → sabotage. Its caveat that the idle test was an exact `<= 0.0` was correct and went to S10 (the message crossed its hand-back — it was stopped rather than allowed to resume on a queued brief while S10 held the worktree) |
| m7-s10-auditfix | implementor | S10: the audit's three should-fixes (F15) + the idle tolerance + two notes. Owns `market/agents.py`, `market/strategy.py`, `jobs/{registry,run}.py`, `tests/unit/test_opf_multiperiod.py`, tests, docs | record/m7-s10-report.md + 4 commits | **done** (`e635eb0` `AgentSetError(ValueError)` at all six up-front sites, registry catches only it — the auditor's `c2 = −0.01` case now classifies identically under `market.nodal` and `market.agents`; `cacbf4f` multiperiod hand-oracle QP case, reddens under both Hessian sabotages at the predicted values, band 1e-3 MW because HiGHS's QP stops at 124.99985 vs exact 125 — a measured fact about the tree's QP precision, recorded; `bfd25d4` `run_json` `object_pairs_hook`, duplicate key at any depth → `BAD_REQUEST` naming key and path, every kind; `01f8c7b` `_IDLE_MW_ABS_TOL = 1e-9`, ULP figures re-measured, three `match=` added). Missed one one-line follow-up (a `(spec A9)` in a field description) — orchestrator committed it as `852dd38` |
| m7-s11-criticfix | implementor | S11: the critic's should-fixes 2–6 and nits 7–10 (F18) + the auditor's docstring note. Owns `market/{agents,strategy,nodal,_clearing}.py`, `opf/dc_opf.py`, `jobs/registry.py`, `results/agents.py`, tests, docs | record/m7-s11-report.md + 6 commits | **done** (`8d0858f` floor `3·step`, one constant `MarkupStrategy.min_offer_tol`, one message at both sites; the critic's cycle reproduced first, 70/70 converge after; `0245991` `dc_opf(ptdf=)` computed once per run, 200-round case14 0.41 s → 0.19 s, cache on/off `array_equal` on all three fixtures; `36ad1f9` `market/_clearing.py` shared by nodal and agents, 14 golden results equal, sabotage moves 10/14 on both; `a566088` NaN/inf step rejected; `1f9d41e` structured error for an out-of-range PWL index; `71f1cf3` nits 7–9 + registry docstring). **Stopped on fix 1(b) with the numbers, as briefed**: tie-noise 2.5e-8 relative at step 0.5 and 2.7e-7 at step 2.0 (∝ step) versus the smallest real one-step change 1.5e-6 at step 0.5 and 1.8e-7 at step 0.01 (∝ step²) — 10× noise exceeds 1/10 of real change, no gap, `_PROFIT_TIE_REL_TOL` left at 1e-9 and A9 rewritten in the spec to say why. Every commit's `--stat` verified to carry its source (F16 rule). Its two run.py nits from the critic crossed its hand-back (F17 pattern) — it was stopped and the orchestrator committed them as `12aa3ce` (`_Node.duplicated` attribute instead of a literal marker key; `_DuplicateKeyError` private; a first draft of the collision test made a *real* duplicate and was rightly rejected by the code before the test was corrected) |
| m7-s6-branches | implementor | S6: `MarketNodalResult` gains `OpfBranchFlowResult` rows, same field name and row type as `MarketZonalResult`, agreeing with `pf.dc`; closes M5 A23 symmetrically. Owns `results/market.py`, `market/nodal.py`, `tests/unit/test_market_nodal.py` | record/m7-s6-report.md + commits | **done** (commit `832a546`, three files, +172/-7). Orchestrator-verified independently, not accepted on report: `git show --stat` confirms exactly the three owned files; every deletion is docstring prose or a rewritten import, so the additive claim holds; and the type-identity clause was re-run here — both models' `model_fields["branches"].annotation` really are `list[OpfBranchFlowResult]`. Sabotage (demand-term sign flip) reddens three tests **on `p_from_mw`**, the quantity AC-8 names — not a whole-solution move. A5 re-confirmed. **Addendum**: S6 later re-measured on a clean tree and got bit-identical numbers (7.993605777301127e-14 MW), so AC-8 provably does not depend on S1's in-flight `opf/` edits — a real strengthening. Its *method* is A15 below. Carries C1, C2 |

## Findings the review layers caught (the chain doing independent work)

**F1 — the `Observation` contiguity validator accepted a *stale* history pair.** S2's first commit
checked only that a history entry was **present**, not that it was **adjacent**. So an observation
for round 5 could carry `previous_round` from round 4 and `two_rounds_ago` from round **2**, and the
hill climb would compare non-consecutive profits and reverse direction on a comparison that means
nothing — a confident wrong answer, the failure mode this epic has named in every wave. Latent
rather than live: it needs a loop that skips or restarts a round to trigger, which S4 has not been
written yet to avoid.

Caught by orchestrator review of the slice report, **not** by the slice's own 24 tests or its
6-point sabotage sweep — both of which were otherwise thorough. `RoundRecord` now carries its own
`round_index` and the validator requires `previous_round.round_index == round_index - 1` and
`two_rounds_ago.round_index == round_index - 2`. Orchestrator re-verified the fix directly rather
than on report: stale-two-ago (5←4,2), stale-previous (5←2,1), reversed order (5←3,4) and the
missing-previous-with-present-two-ago inconsistency are all rejected with messages naming the
actual and expected round; the contiguous case builds.

The pattern to carry: **a slice's own sabotage sweep tests the behaviours the slice thought of.**
Six waves in, every layer of this chain has found something the layer below did not — and the layer
below was not careless.

**F2 — the unification made `test_opf_multiperiod.py` blind to symmetric Hessian defects, and the
slice reported this against its own interest.** Every quadratic-cost test in that module compares
`multiperiod_dc_opf` against `dc_opf`. Before W1 those were two implementations and the comparison
had power; after W1 both sides call one helper, so any defect depending only on
`(c2, v2, n_gen, n_demand)` cancels on both sides. S1 raised it unprompted and correctly declined to
make the coverage call, which is outside W1. **And it predicted this one rather than explaining it
after the fact**: when the symmetric sabotage left the module green, S1 diagnosed the cancellation
structurally, predicted that only an `n_blocks`-dependent defect could break it, and named
`test_pwl_generator_costs_are_period_specific_at_t2` — the module's one T≥2 quadratic test — as the
single test that would redden. It was exactly the one that did. S1 also stated plainly, unasked,
which of its other residuals were merely observed-then-explained. That distinction is the
difference between a power proof and a story, and it was volunteered.

**Orchestrator-verified independently** (archive overlay of `a22922d`, symmetric sabotage
`2.0*c2 -> 2.5*c2`, all 136 `opf` tests): `test_opf_multiperiod.py` **green**, confirming the
blindness. AC-1(b) still discharges — its sabotage carries an `n_blocks` dependence, which is
asymmetric and does redden the module.

**F3 — and the complete enumeration says something S1's did not.** S1 wrote that the symmetric
sabotage "reddened only dc_opf's and zonal's modules". Measured across every `opf` test: **11 red**
— `test_opf_dc_case14_pwl.py` (3), `test_opf_zonal.py` (1), and **`test_opf_redispatch.py` (7)**.
The redispatch reds were missing from S1's account — it sabotage-swept seven `test_opf_*` modules
(100 tests) where the complete `opf` set is ten (136). This is the wave's own standing rule ("never
write *only* about a set you have not enumerated", M6 ADR-009 consequence 3) recurring. To be fair
to the slice: the *finding* was right and predicted; it was the survey of everything **else** that
was partial. But the completion changes the conclusion rather than merely extending it, which is
exactly why the rule exists.

`redispatch` is the **non-caller**. It kept its own 2x2 construction, so sabotaging the shared
helper moves `dc_opf`'s answer and not redispatch's, and the D1-theorem tests that compare them
break. **The module left out of the unification is now the strongest independent check on the
unified code** — 7 of the 11 reds. The decision to exclude `redispatch` was taken on the grounds
that its 2x2 coupling is genuinely different; it turns out to also be what preserves an independent
oracle.

The principle, which ADR-008's programme does not currently capture and ADR-010 should:
**unifying two implementations that were being compared against each other silently deletes the
comparison's power.** Behaviour preservation and *coverage* preservation are different properties,
and W1 only ever asked for the first. Every future unification should ask which comparison it is
about to collapse, and whether anything absolute remains.

**Fold item (owner assigned at Step 6):** give `test_opf_multiperiod.py` an absolute quadratic
oracle of its own — a hand-derived T=2 quadratic optimum — so its quadratic coverage does not rest
entirely on a comparison the wave has just made trivial. Not urgent for the wave: the suite as a
whole still catches the symmetric defect 11 times over. It becomes urgent the moment anyone
proposes unifying `redispatch` too.

**F4 — `MarkupStrategy` reversed direction on one ULP of solver noise, and reported the
competitive outcome as a strategic equilibrium.** `offer` used a strict
`if profit_prev < profit_2ago:` with no tie tolerance. On the AC-5 duopoly both 300 MW agents sit
at capacity while demand sets the price, so consecutive rounds are economically identical — the
price is exactly $40 both times. The observed balance dual differs by **one ULP**; times 300 MW
that is ~1.6e-12 of profit, and the strict comparison flips direction on it. The climb turns around
at round 2, the loop then correctly detects a period-4 repeat, and `solve_agents` reports
**converged at iteration 4, offers `[20.5, 20.5]`, joint profit $11,999.96** — the true-cost
outcome dressed as a settled equilibrium. Silent-plausible again, and the loop was blameless: it
faithfully reported a strategy that turned around for no economic reason.

**Fixed by S2 at `20ba1e7`** — relative form behind a named constant, docstring updated to state
the tie rule, guard test at `test_market_strategy.py:229`. **Two independent witnesses**, which is
what makes the guard credible: S2's unit test proves the rule; S4's
`test_market_agents.py::test_ac5i_...` goes red under the same sabotage from a different module and
a different fixture path, proving the rule matters to the *market*. They fail for different
reasons.

**Cause: the orchestrator's brief.** The Step-2 probe
(`.bionic/tmp/m7-a4-two-point-climb.py:79`) used `profit_prev[i] < profit_prev2[i] - 1e-9`. The S2
brief restated the rule in prose — "if `profit[t-1] < profit[t-2]` the direction reverses" — and
dropped the epsilon. S2 implemented what it was given. **When a measured probe is handed to a slice
as prose, the tolerances in it are part of the specification, not incidental detail.**

Found by S4, three slices downstream of where it was introduced, on a fixture S2's module could not
construct: a tie needs a market. Fixed by S2 under relay (ownership held). The remedy is the
**relative** form — `math.isclose(..., rel_tol=1e-9, abs_tol=1e-9)` — not the probe's absolute
epsilon: profit is ~$6,000 here and would be millions on a large network, and an absolute
tie-breaker at one scale is a no-op at another. Measured by S4 against all three fixtures: either
form restores AC-5(i) exactly (iterations 84, `[60.0, 60.0]`, $60.00, $15,999.98) and neither moves
AC-4's numbers, so the change lands only on the case that needs it.

**C4 — `_clearing_rows` in `market/agents.py` duplicates `solve_nodal`'s loads/branches/settlement
assembly.** Raised by S4 as a carry rather than reopened, correctly — it is unavoidable inside that
slice's file list. Third duplication finding of the wave, after C1 (branch-flow derivation) and
F2/F3 (the Hessian). Line count and whether it is verbatim requested from S4, because C1 showed an
accurate carry is worth more than a large one: what looked like a third copy proved to be one
shared line with genuinely different surrounding constructions, which changed the remedy.

**F5 — the spec told a slice to make a fix that would have broken a passing test, and the slice
refuted it with proof instead of doing it.** W8 said "the one-line stale-transcript fix at
`docs/manual/jobs.md:267`". S8 showed it is neither stale nor one line, and declined to touch the
file. **Orchestrator-verified**: `jobs.KINDS` holds exactly seven kinds and the transcript lists
exactly those seven in sorted order — the page is *correct today* — and
`test_docs_registry_listing.py` (4 passed) pins the current list verbatim, so writing an eight-kind
list before `market.agents` registers turns it **red**. It is also three coupled sites, not one
line: the `print(jobs.kinds())` block, the capability table, and the transcript, all invalidated
together by the eighth kind.

**Cause, and it is the second instance of one pattern.** `m7-research.md:450` had it right — "a
one-line update the day `market.agents` registers" — and the spec transcribed it while **dropping
the condition**, turning a contingent observation into a standalone instruction. That is exactly
F4's shape: the Step-2 probe's `- 1e-9` tie tolerance was load-bearing and the S2 brief restated
the rule without it. Twice this wave the orchestrator has flattened a *conditioned* finding into an
unconditional one when moving it from research into a brief or spec.

**The rule this yields:** when a research note carries a condition — "the day X happens", "within
tolerance t", "provided Y" — the condition travels with it or the claim does not travel at all.
Both failures were caught downstream by slices reading the underlying evidence rather than the
instruction, which is the verification chain working, but neither should have needed catching.

Sequencing consequence: **S8 phase 2 depends on S4 *and* S7**, not S4 alone.

**F6 — the loop reports a genuine convergence as a `cycle` whenever `offer_tol == 2 * step` and the
step is not binary-exact — which is the value the validator itself recommends.** Orchestrator-
measured on the duopoly, markup on both agents, `offer_tol` set to the validator's own stated
minimum:

| step | offer_tol = 2*step | reported | iterations | offers reached |
|---|---|---|---|---|
| 0.5 | 1.0 | converged | 84 | `[60.0, 60.0]` |
| 0.25 | 0.5 | converged | 164 | `[60.0, 60.0]` |
| **0.1** | **0.2** | **cycle** | 404 | `[60.0, 60.0]` |
| **0.2** | **0.4** | **cycle** | 204 | `[60.0, 60.0]` |
| 0.1 | 0.2*(1+1e-7) | converged | 404 | `[60.0, 60.0]` |

All four runs reach `[60.0, 60.0]` — the correct answer. 0.5 and 0.25 pass only because they are
binary-exact, so peak-to-peak comes out at exactly `2 * step` and `amplitude <= offer_tol`
(`agents.py:528`) holds by equality; 0.1 and 0.2 accumulate representation error and land a few ULP
above. **The validator's own message tells the caller to "raise `offer_tol` to at least `2 * step`",
so following the guidance is what triggers the failure.**

**This is F4 mirrored, and the wave has now found the same class on both sides of one comparison.**
F4: a strict `<` reversed direction on a noise-sized *difference*, producing a false *convergence*.
F6: a `<=` refuses convergence on a noise-sized *excess*, producing a false *cycle*. Both are
correct in exact arithmetic and decided by float noise. The remedy is the same shape as S2's:
relative slack on the comparison, not a strict validator making callers pad around it — at step 0.1
the honest amplitude *is* `2 * step`, so `2 * step` is the right tolerance.

**Why the eight-defect sweep missed it:** every defect was probed at the wave's own step of 0.5,
where the arithmetic is exact. A parametrised test over a non-binary-exact step is what catches it,
and is what S4 has been asked to add. **Coverage that varies only the defect, never the
configuration, cannot see a defect that lives in the configuration.**

**F7 — the plan's file-ownership map was incomplete: registering a kind also widens a closed union
in a file no slice owned.** `jobs/models.py`'s `ResultModel` is a closed pydantic union, one member
per registered kind. S7 found this **before writing code** and stopped rather than reaching outside
its list — the behaviour the ownership discipline exists to produce. Granted to S7: it is the right
owner, nobody else is in the file, and M6's S7b widened the same union for `market.zonal` at
`4432163`.

**The slice's diagnosis was right about severity and wrong about mechanism, which the orchestrator
corrected before it wrote a test.** S7 reported that `run()` would raise an uncaught
`ValidationError`, because the `SolveResult(...)` construction sits outside the try/except. It does
— but `run.py:198` guards it with `if not isinstance(raw, ResultModel)`, and `ResultModel` is a
PEP 604 union that `isinstance` accepts. So nothing raises and the never-raise contract holds; the
actual consequence is that **every successful `market.agents` request returns `INTERNAL`**.

That is the *same* defect M6's walk found on `market.zonal` — a caller doing everything right
receiving an internal-error code — and it is strictly worse than a crash for the epic's recurring
reason: a crash is loud, this is silent-plausible. It also yields the sharper sabotage for AC-6:
revert the union widening and show the success path degrade to `INTERNAL`, a defect in exactly the
quantity the criterion names, from a tree otherwise correct.

**The general lesson for the plan's ownership map:** ownership was assigned by *module*, but this
change is defined by a *cross-cutting invariant* — "one union member per registered kind" — that
lives in a different module from the registration. Every wave that registers a kind has hit it
(M5, M6, now M7). A file map derived from where the new code goes will keep missing the files the
new code's invariants live in.

**F8 — the wave's own rules only bind the agents that were told them, and the second A16 breach
proved it at cost.** At 23:03 the shared worktree carried an uncommitted one-line sabotage of
`gen_cost_coeffs` — the cost-source lookup replaced by `gens_by_id[gen_id].cost`, making the offer
overlay a **silent no-op**. A markup run clears at true cost every round and still reports
`Optimal` and `converged`: the silent-plausible class, sitting on the exact mechanism M7 exists to
build. S7 was concurrently running `market.agents` tests whose runner clears through that function.

**Found by S5**, which takes every number on a `git archive` overlay of `74a0532` and therefore had
a clean vantage point — it saw the poisoned tree instead of quietly measuring against it, and
flagged without touching, correctly refusing to revert a file it did not own and a sweep that was
mid-run.

This is the third distinct manifestation of one root cause (A14 baseline, A15 main-checkout
overlay, A16/A17 in-place sweeps): **concurrency and measurement cannot share a working directory,
and every sub-case of that has had to be learned separately.** The generalisation for the next wave
is not another rule but a default: **give each slice its own tree, or require every measurement to
run against an archive overlay, from the first brief.** Six slices sharing one worktree produced
four incidents; none lost work, but each was caught by an agent noticing rather than by the design
preventing.

**F9 — the shared worktree stopped merely poisoning numbers and started manufacturing findings.**
S7's full-suite run reported two reds in `test_market_agents.py` at steps `[0.1]` and `[0.7]` and
concluded "S4's guard doesn't fully cover its own documented worst case" — written into
`m7-s7-report.md`, a record the auditor reads. **Orchestrator-verified at 23:22 on the same tree:
9 passed, `[0.1]` and `[0.7]` among them.** S7 had run while S4 had the parametrised test saved and
the `_settled` fix not yet written; both files were still uncommitted. The test's own docstring
names those two steps as "the cases that were wrong" — describing the defect it was written to
catch — which is what made a transient red read as a live worst case.

S7 did the right things: it flagged rather than fixed, attributed by path, and declined to touch a
file it did not own. Only the *diagnosis* was wrong, and routing it unchecked would have sent S4
chasing a non-defect in code that was already correct.

**This is the fifth incident from one shared worktree and the first to cost a false claim rather
than a measurement.** Reading another slice's uncommitted files is reading a moving target, so the
rule for the rest of the wave: **a red in a committed file is evidence; a red in an uncommitted one
is a timestamp.** Check `git status` before attributing, report the observation with that fact
attached, and stop short of a diagnosis.

It also sharpens F8's conclusion. The remedy is not another rule for agents to follow — five have
now been needed and each was learned from an incident. **The next wave gives each slice its own
worktree.** Six slices in one tree produced: a meaningless baseline (A14), an overlay into the
user's main checkout (A15), two in-place sabotage sweeps poisoning concurrent measurement
(A16/A17), and now a false finding about another slice's correctness. Every one was caught by an
agent noticing; none by the design preventing.

## Carries out of the slices (measured, not asserted)

**C1 — the branch-flow derivation is now a third application site, and this wave added it.**
`flows_mw = ptdf_matrix @ injection_mw + pf_shift(arr) * arr.base_mva` is **verbatim identical** at
`opf/__init__.py:152` (`solve_dc_opf`) and `market/nodal.py:214` (`solve_nodal`, added by S6 at
`832a546`); `redispatch.py:422-428` builds the same quantity in constant-folded form. ADR-008's
lesson is *unify before adding*, and M7 opened with W1 doing exactly that for the diagonal Hessian
— then S6 added a copy of a different formula. Recorded rather than reopened, for a reason that is
itself measured: **the shared part is one line; the injection constructions genuinely differ.**
`solve_nodal` subtracts elastic demand and each elastic load's own historical MW (`dc_opf`'s
double-counting contract); `solve_dc_opf` does not, and correctly so — it never passes demand bids
to `dc_opf`, so it has no elastic demand to subtract. This is **not** a latent bug in
`solve_dc_opf`, and the wave must not claim one. It is a real duplication whose unifiable core is
thin, which is precisely the judgement ADR-008 asks a wave to make explicitly rather than by
default. Candidate for M8, with the count stated: three sites, one shared line, three different
injection constructions.

**C2 — AC-8's tolerance is loose by four orders, and that is defended, not overlooked.** The pin is
`abs=1e-9` MW, reused verbatim from `test_opf_redispatch.py`'s pin for the identical
solution-vs-`pf.dc` claim; the measured residual is 0.0 MW on the two-bus fixture and 7.99e-14 MW
sup-norm on rated case14. Tightening to ~1e-11 would still leave headroom, but M5's macOS one-ULP
CI failure is the standing argument against pinning a cross-platform float identity near its
observed value, and the sabotage shows the reachable defect class moves this quantity by
O(100 MW) — so the looseness hides nothing reachable. Recorded because M6's most expensive lesson
was that nobody checked what a tolerance actually admitted for two rounds.

**C3 — `MarkupStrategy` cannot be attached to any generator in any committed fixture, and the wave
must say so.** S2 scoped it to a linear `PolynomialCost`, raising `NotImplementedError` otherwise.
Measured consequence (orchestrator, 2026-08-28, direct probe of all six MATPOWER fixtures):
**147 generators, every one quadratic, zero linear.**

| fixture | gens | linear | quadratic |
|---|---|---|---|
| case14 / case30 / case_ieee30 / case57 / case118 / case300 | 5 / 6 / 6 / 7 / 54 / 69 | 0 in every case | all |

No acceptance criterion is affected — AC-4 and AC-5 run on W7's synthetic fixtures, which are
linear by construction. But the wave's headline capability works only on networks the wave itself
builds, and that is the kind of limitation an audit finds if the spec does not state it first.
**Binding on S8:** no docs example may apply a markup strategy to a MATPOWER case; it would raise.

The obvious widening — offer `(c2, c1 + markup, c0)`, a constant adder to marginal cost, which is
the standard reading and would work on all 147 — is **deliberately not taken in M7**. It changes
what "profit" means in the hill climb (total revenue minus a quadratic total cost, not
`(price − c1) × MW`), which is the exact quantity AC-4's and AC-5's measured numbers were derived
from. Widening it now would put those numbers back in question late in the wave for no acceptance
gain. M8 candidate, with the reason recorded rather than the option forgotten.

**A18 — an agent that idles instead of messaging must be reconciled against the disk, and its last
reported gate number is the one most likely to be stale.** S4 idled twice without a completion
message (the known `stop-guard` behaviour, M6 carry-over). Both times the work was further along
than the signal suggested — the second time it had picked up the resume instruction, re-taken the
whole sweep on an overlay and grown the report by 2.3KB, all without saying so. Reading the disk
found that; waiting for a message would not have.

The specific trap: a slice's **head-gate figure ages the moment anything else lands.** S4's
`1 failed, 1085 passed, 4 skipped in 455.03s` is byte-identical across two reports written either
side of its own F6 fix *and* S5's 544-line commit — it is the `74a0532` run, carried forward
unchanged. Nothing about it is dishonest; it is simply a number about a tree that no longer exists.
**A slice-level gate result is evidence about that slice at that commit, never about the wave.**
The orchestrator's single named sweep at the final head is the only figure that speaks for the
wave, which is exactly why M6's A38 required it.

**F10 — the bitwise choice for AC-3(b) is now justified by measurement, not by preference, and S5
established the distinction that makes it meaningful.** Two results from its sweep, which nobody
asked for and which change how the criterion should be read:

**A tolerance would have hidden a real defect.** Rounding reported dispatch to 6 decimal places
reddens exactly the three AC-3(b) cases and nothing else — and **no tolerance-based row anywhere in
this wave would catch it**. The Step-2 decision to assert `array_equal` rather than `assert_allclose`
was taken because bitwise agreement was *available*; it turns out also to be the only form that
detects this class.

**But the reason it holds is not that the solve is insensitive.** S5 measured that a **one-ULP**
perturbation of an offer coefficient *does* move this LP's answer, on all three cost shapes. So
AC-3(b) passes because both paths hand the builder **identical arrays**, not because small input
changes wash out. That is the honest reading, and it is a much stronger statement than "the numbers
matched": it says the overlay is exact, on a solve that would have shown any inexactness.

**Limits stated plainly by the slice, and kept:** the bitwise agreement is a claim about this
Windows build, this pinned `highspy`, both calls in one process. **No cross-platform claim is
made** — which is the correct posture given M5's macOS one-ULP CI failure, and the spec already
says a platform disagreement would be a finding to record rather than a tolerance to introduce.

**F11 — the S8 agent was lost across the PAUSE/compaction, and its half-finished state was
uncommitted.** `ListAgents` on resume showed no subagents at all; the worktree had S8's phase-2
edits sitting in the working tree. Nothing was lost — the edits were intact and already strict-green —
but the four things S8 had not yet done (nav, examples index, changelog, roadmap) had to be
identified by inspection rather than from a report. Rule for the next wave: an agent that will
outlive a checkpoint commits at every self-contained sub-deliverable, not at the end; a strict-green
docs tree is a commit point.

**F12 — my own changelog draft misdescribed W1(c).** I wrote the guard up as rejecting "a cost
overlay whose generator ids overlap with the network's". It is nothing of the kind: it rejects a
generator appearing in `pwl_costs` **with a nonzero `cost_coeffs` row** — a double charge, the mirror
of the load-side guard. Caught by reading `test_opf_overlap_guard.py`'s docstring before the strict
build, not by any tool. Third instance of the F4/F5 class (a claim restated from memory drifting from
its source); same rule — the condition travels with the claim.

**F13 — the first named sweep at `ec8876e` (2026-08-29 16:56Z) was green on four of five gates
and red on one:** pytest **1146 passed, 4 skipped in 539.92s** (+154 over the 992 baseline, nothing
red anywhere), `ruff check` clean, `mypy` clean (53 source files), `mkdocs build --strict` exit 0 —
and `ruff format --check` flagged one file: two aligned trailing comments in a Python fence in
`docs/manual/agents.md`. Fixed by `ruff format` and committed as `9b30e01` (docs-only, +2/−2, no
source byte changed). Because the rule is *one* sweep at the *final* head (A18, M6 A38), the full
sweep was re-run at `9b30e01` rather than re-checking only the failed gate; the walk and audit
dispatched against `ec8876e` remain valid for the source, which is byte-identical between the two
heads, and that is stated in both artifacts' provenance by reference here.

**F14 — the walk (Step 5, `record/m7-walk.md`, at `ec8876e`, machine-checked: 0 hits of
`AC-[0-9]`) found three defects the eight criteria and 1146 tests did not, all verified in source
by the orchestrator before dispatch:** (1) `market.solve_agents` does not exist — the changelog,
examples index and home page all name it, and the other three modes are exported that way;
(2) a `MarkupStrategy` on a quadratic cost — i.e. on **every** bundled fixture — leaves `jobs` as
`INTERNAL`, because `strategy.py` raises `NotImplementedError`, `agents.py:507` documents it as
propagating unchanged, and `run.py`'s bare `except` maps it to `INTERNAL`, while the manual
promises "never `INTERNAL`" nineteen lines after documenting the exception; (3) an agent never
dispatched has profit 0 == 0 every round, the tie rule keeps direction, and it climbs to $130
against a true $30 and reports `iteration_cap` on the simplest possible market. None is a criterion
failure: AC-6 lists four caller mistakes and this is a fifth; the climb rule was measured at Step 2
only on agents that clear. Three more surprises and seven friction items are prose. All go to a
fix slice S9 (four commits) at the layer each lives — the export, an up-front strategy/cost check at
the loop boundary (not a wider `jobs` catch), an idle rule at the strategy (direction −1 when two
consecutive rounds cleared zero; the real-decrease tie rule untouched), and a return-type check at
the strategy call site. The walk earned its place as the first thing dispatched: the auditor, working
from the criteria, could not have found (2) or (3) because no criterion names them.

**F15 — the independent audit (`record/m7-audit.md`, at `ec8876e`, run entirely from
`git archive` copies with in-process provenance proven, full suite 1146 passed / 4 skipped from the
archive): 6 DISCHARGED / 2 PARTIAL / 0 REFUTED.** Discharged with independent recomputation, not by
re-running the slice's tests: AC-2 (`Generator.cost` `is`-identical after both agents went 20 → 60),
AC-3 (`tobytes()` bitwise on all three cost shapes), AC-4 (four hand-set fixtures land on
`(v1 + c)/2`; the control stops at `rival − step` at two step sizes), AC-5 (own recorder and period
search; caps at 83 → `iteration_cap`, 84 → `converged`; `offer_tol == 2*step` at 0.1 and 0.7 →
`converged`), AC-7, AC-8 (independent dense B′θ solve agrees to 9e-14 MW on 20 branches).
Partial: **AC-1(b)** — sabotaging the shared Hessian diagonal reddens `dc_opf` and `zonal` tests but
**zero** tests in multiperiod's own modules (its unit file uses only linear costs; its one quadratic
case compares against `dc_opf` itself), so the "per-caller sabotage" S1 reported held for two callers
of three. **AC-6** — the four named mistakes classify correctly, but `registry.py:248` wraps the
*whole* `solve_agents` call in `except ValueError` and relabels it `VALIDATION`/`DANGLING_REF` at
`options.strategies`; `NonConvexCostError` and `NonConcaveBidError` are `ValueError` subclasses, so a
non-convex true cost on case14 says `INTERNAL` under `market.nodal` and `VALIDATION at
options.strategies` under `market.agents`. And the spec's "never a silently accepted last-wins
duplicate" does not hold at the `run_json` surface: a duplicated generator key in the JSON is
last-wins with `status=ok` — a JSON-parser property that applies to every kind. Notes: `_settled`'s
docstring ULP figures are stale against this head; three `pytest.raises` without `match` in
`test_market_strategy.py:433–440`; pre-M7, halving the demand Hessian entry reddens only zonal tests.
**The audit's F2 is coupled to S9's fix 2**, which deliberately routes its up-front rejection through
that same `except ValueError` — the right fix is one dedicated exception class raised by
`_resolve_agents` and `_initial_offers` and caught by name, which closes both. All go to S10 after S9
hands the worktree back.

**F16 — S10's fix C (`bfd25d4`) committed its tests and its docs row but not the source.** The
gate at `852dd38` (2026-08-29 18:19Z: **2 failed, 1157 passed, 4 skipped**; ruff, format, mypy,
mkdocs all clean) reddened exactly the two new duplicate-key tests; they failed alone as well, and
`git show --stat bfd25d4` lists `docs/manual/jobs.md` and `tests/unit/test_jobs.py` only. S10 had
reported green *and* a sabotage — so at the moment it measured, the source change existed in its
working tree, and it was lost afterwards, most plausibly to fix B's `git checkout -- src/` restore.
The orchestrator implemented the pre-parse the tests specify (`47b52da`: `object_pairs_hook`,
`BAD_REQUEST` naming key and dotted path, malformed/too-deep JSON still left to pydantic), with the
sabotage re-proved by stash (116 passed with, 2 failed without). Rule, joining A16: **a report's
green is a claim about a working tree, and the commit is a different object** — the orchestrator's
check on every slice is `git show --stat` against the files the brief named, and the named sweep is
the only figure that speaks for a head. The re-audit and critic were both dispatched at `852dd38`
before this was found and were redirected to `47b52da` for the one file that differs.

**F17 — an idle agent resumed on a queued message and rewrote history on the shared branch.**
S10 reported done; I then sent it a one-line follow-up, and while it sat idle I committed that same
line myself as `852dd38` and started the sweep. S10 woke on the queued message, found my commit,
and `commit --amend`ed it into `6d00ac3` (identical content) — an amend of a commit it did not
author, on a branch a sweep was about to be named against. Outcome was benign: the branch stayed
linear, my `47b52da` landed on `6d00ac3`, and the sweep started after both. The re-audit and
independent measurement stayed valid because `852dd38` and `6d00ac3` are byte-identical trees.
Two rules: (1) **a queued message to an agent that has handed back is a dispatch** — either stop the
agent when it reports (as S9 was) or do not touch its worktree until it has acknowledged; (2) briefs
say *never amend or rebase a commit you did not author* explicitly. S10 was stopped on discovery.
Related: the auditor's re-audit at `852dd38` independently found F16 (the un-committed source) and
called it blocking — the audit layer catching a gate failure the implementor's report did not.

**F18 — the critic (Step 6, `record/m7-critic.md`, at `852dd38` with `run.py` redirected to
`47b52da`): not merge-ready — one blocking (F16, already fixed at `47b52da`), five should-fix, four
nits; held up: history/observation indexing, cycle-window arithmetic, `_offer_key` exactness,
`_pass_diagonal_hessian` stride, `AgentSetError` coverage, `run_json` on 20k-deep nesting.** The
should-fix that matters is the **third instance of the F4/F6 class**: a profit peak equidistant
from two grid points (true cost 33.33, step 0.01, `offer_tol` 0.02) produces a period-6, three-step
orbit — amplitude 3·step — reported as `cycle` after 3339 iterations, so the derived bound
`offer_tol ≥ 2·step` (spec A9, Step 2) is wrong by one step; and beneath it the 1e-9 relative
profit-tie band is *below* HiGHS's QP noise at a marginal agent (2.5e-8 relative), so at c = 20.5 /
step 0.5 the reverse decision is decided by noise and converges by luck. Also: PTDF and incidence
rebuilt every round inside `dc_opf` — 70 % of a 200-round case14 run; `_clearing_rows` a verbatim
copy of nodal's block; `MarkupStrategy(step=nan)` a silent price-taker; the double-charge guard's
range clause turning an out-of-range `pwl_costs` index into a raw `IndexError`. All to S11, with the
tie tolerance to be set from *measured* noise with both bounds stated, and an instruction to stop
and report if the bounds leave no gap. A9 in the spec is rewritten once S11's measurement lands.

**F19 — the critic's re-review at `12aa3ce` (verdict: merge after one finding) found a regression
in my own `12aa3ce` rewrite of `run.py`:** the duplicate-key path walk was recursive and ran outside
the `try` guarding `json.loads`, so at JSON depth 1000–1100 it raised `RecursionError`, which the
catch-all reports as `INTERNAL` where `47b52da` had said `BAD_REQUEST` (990 and 5000 were fine on
both — the latter because `json.loads` overflows first, inside the guard). Its side note was also
right: the walk ran on every clean request, 3.1 → 7.8 ms on case300. Fixed at `9739be8`: an explicit
stack, run only when the hook saw a duplicate; regression test at depths 990/1100/5000, and with the
change stashed two of the three said `INTERNAL`. Everything else the critic re-verified against its
own reproductions: 70/70 converge at `3·step`, the tie band at 1e-9 **accepted** with its own
derivation (real adjacent-point change `10·s·(2d+s)`, noise step-independent, a mis-decided
near-tie widens the orbit by at most one step, which `3·step` covers; it could not construct a
misclassified verdict at steps 0.005/0.002/0.001 on- or half-grid), the `ptdf=` cache 5.20 s →
0.47 s with `solve_nodal`/`solve_dc_opf` byte-identical across venvs on five networks. The auditor's
final pass at `12aa3ce` is 8/0/0 with AC-3's arrays md5-identical to `ec8876e`. Lesson: the same
reviewer that found my F16 repair's nits found the regression in my fix of those nits — the review
layers were the check on the orchestrator's own commits, three times this wave.

**F20 — at Step 8 close, `rm -rf` of the M7 worktree emptied the main checkout's `.bionic/`
tree — every spec, plan, ADR, record and probe of seven waves.** `git worktree remove` had hung
past its timeout (the worktree's `.venv`), leaving the entry prunable; I finished the delete with
`rm -rf "…/mambo-power-m7"` in the background. The worktree's `.bionic` was evidently a junction to
the main checkout's, and MSYS `rm -rf` traversed it. Nothing under `.bionic/` is in git (its
`.gitignore` is `*`), so git could not help. **Recovered from the Claude Code transcripts**: every
`Write`/`Edit`/`MultiEdit` and every shell command that wrote under a mambo-power `.bionic` path,
across all session and subagent transcripts of every project directory (M1/M2 ran from a sibling
cwd), replayed in one timestamp-ordered timeline into a staging root with paths remapped —
1,050 events, 370 shell commands executed under Git Bash with a UTF-8 environment, 106 skipped for
also running git/pytest/curl, 77 failed (probes needing the source tree, not doc writes). Four
wrong turns on the way, each a lesson about the replay itself: two-stage (tools then shell) instead
of one timeline; `bash` resolving to WSL's, not Git's; the subprocess decoding heredocs as cp1252;
and a skip filter matching the word `git` inside heredoc prose. 261 files restored; the last closure
edits (skipped for their `curl`) re-applied by hand. **Losses**: a handful of `Edit`s whose anchors
no longer matched in M3/M4-era files, and any shell write that also ran a dangerous command
(`_skipped.log` in the scratchpad names them) — none in M7's artifacts. Rules: never `rm -rf` a
directory that may contain a junction — use `git worktree remove --force` or `cmd /c rmdir` (which
does not follow junctions); and treat `.bionic/` as un-backed-up — it should be committed or
mirrored, which is the user's call and is raised in the continuation.

## Split findings (named owner for each half + an orchestrator check)

M5's most expensive process lesson: a finding spanning two slices needs an owner for **each half**
and a check at the final head. M5 lost a CI run to a finding whose halves went to two agents with
the split itself owned by nobody.

| finding | half | owner | status |
|---|---|---|---|
| A new public symbol reddens `test_api_docs_coverage::test_every_public_symbol_is_reachable_from_an_api_page` and `test_docstrings::test_every_public_symbol_has_a_docstring` | the docstrings on the new symbols | the slice that added them (S2: `MarkupStrategy.offer`, `PriceTakerStrategy.offer`) | assigned to S2 |
| Registering `market.agents` (KINDS 8) invalidates three coupled sites in `docs/manual/jobs.md` — the `print(jobs.kinds())` block, the capability table, the transcript — turning `test_docs_registry_listing.py` red | the registration | **S7** (leaves it red, states why) | **done** (`8df221d`) |
| same | the three `jobs.md` sites | **S8 phase 2** | **done** (`ec8876e`; `test_docs_registry_listing` 4 passed) |
| same | `docs/api/*.md` must reach them — S2 contributes `MarkupConfig, MarkupStrategy, Observation, PriceTakerConfig, PriceTakerStrategy, RoundRecord, Strategy, build_strategy`; S4 and S6 add more | **S8** | **done** — `test_api_docs_coverage` green at `ec8876e`; `DEFAULT_MAX_ITERATIONS` and `TerminationReason` are invisible to that test by construction and were verified in the rendered site instead — `site/api/market/index.html` names `DEFAULT_MAX_ITERATIONS` 8 times and `site/api/results/index.html` names `TerminationReason` 20 times, both via the `:::` directives |

Consequence for the rest of the wave: `test_api_docs_coverage` is **expected red** from S2's first
commit until S8 lands. It is not a regression, and no slice but S8 may touch it. Every slice adding
a public symbol reports it so S8's list stays complete — the reporting step is the check that makes
this a tracked split rather than an assumed one.

## Assumptions

Carried from the spec's `### Assumptions` (A1–A7) and binding on the slices:

- **A1 — RESOLVED before approval**, by building the fixture instead of deferring it. The sweep
  measured *exact* best response: it cycles (period 2) in 5 of 6 duopoly configurations, round-robin
  converges in 6 of 6, damping in 3 of 6 at 16–21 rounds. **That is not the dynamics M7 ships** —
  see A4 — so it stands as a characterisation of the game, not as the update-rule decision. It is
  why the wave claims no uniqueness: the fixed point is asymmetric and order-dependent.
- **A2 — RESOLVED before approval.** `opf.gen_cost_coeffs` already does the whole
  `GeneratorCost` → `(cost_coeffs, pwl_costs)` mapping; S4 generalises it to take the cost source
  rather than writing a parallel assembler. The probe also found the W1(c) defect — see AC-1(c).
- **A3 — RESOLVED before approval.** Five independent `dc_opf` constructions on identical input are
  **bitwise identical**, so AC-3(b) asserts `array_equal` and no tolerance enters the wave. M5's
  macOS one-ULP finding was a structurally different LP.
- **A4 — RESOLVED before approval, and the assumption was false.** A one-round own-node observation
  cannot tell an agent whether its last move helped; the rules it supports cycle or reach a
  **$0.02/h** markup gain. W2 now specifies **two** rounds of own history, which reaches the
  closed-form peak exactly. Residual limitation, disclosed in Not Doing: the climb is *local* and
  stalls at **$9,497.52 against a derivable $12,250** when a competing unit puts a step between
  cost and peak — so AC-4's fixture is smooth by construction and the spec says so.
  `offer_tol >= 2 × step` is derived from the measured settling amplitude, closing D6.
- **A5 — RESOLVED before approval.** Checked: the only JSON schema snapshot is
  `tests/unit/snapshots/network.schema.json`, a network-model snapshot; no result model is in any
  snapshot, so `MarketNodalResult.branches` needs no regeneration. Additive; S6 proves no test
  breaks.
- **A6** — `AgentOfferResult.markup` is asserted as an identity against `offer`, `true_cost` and
  cleared MW, not presented as independent content (M6).
- **A7** — `termination_reason` is required and enumerated; `iterations` is readable from the
  result, without which AC-5(i) is not assertable.

- **A8** — updates are simultaneous; round-robin is the documented fallback if S3's re-measurement
  against the shipped strategy disagrees. The update rule is contract, not implementation detail.
- **A9** — `offer_tol >= 2 × step` is derived from the measured settling amplitude (1.0 at step
  0.5), not tuned. A strategy with an adaptive step must state its own settling amplitude.
  **Superseded at Step 6 (F18): the floor is `3 × step`** — a half-grid optimum settles three steps
  wide; see the spec's A9 for the correction and the measured reason no profit-tie tolerance can be
  sized.

Process assumptions, binding from Step 4:

- **A14** — **a measurement is only about the tree it ran against.** M6's A30 said this about the
  walk ("a walk gate reports against a head"); it generalises to every gate, and the orchestrator
  broke it in this wave's first hour by baselining a worktree it was about to dispatch four
  concurrent editors into. Rule: any number that will be quoted — baseline, acceptance, gate — is
  taken against a tree that is either committed and quiet, or an isolated `git archive` overlay.
  Concurrency and measurement do not share a working directory.
- **A15** — **the main checkout is not scratch space, and "it was clean when I looked" is not a
  safety property in a concurrent wave.** S6 measured against a clean tree by copying its three
  files into `C:\Claude Projects\mambo-power`, testing there, and reverting with
  `git checkout --` on those paths. Outcome was clean — verified: that checkout is at `6ca9dcc`
  with no diff and no untracked strays, and the numbers were bit-identical, which strengthened
  AC-8. But that directory is the user's primary working directory and is where the orchestrator
  runs baselines; had the overlay coincided with the stack-health run, the wave's "before" number
  would have been silently wrong. Checked after the fact: the file S6 touched holds **3** tests at
  base and **7** with its commit, and the baseline collected exactly **992**, so the overlay was
  absent — luck confirmed retrospectively, not a safeguard. And `git checkout --` is the one
  command every slice was told never to run; scoping it to a tree that looked quiet is an argument
  that fails the instant another writer appears.
  **The pattern that buys the same assurance at no risk**, used successfully by S3: extract
  `git archive <base>` into a temp directory, overlay your files there, drive it by `sys.path` /
  `PYTHONPATH` with the loaded module's `__file__` printed. Nothing outside that directory is
  written, so nothing can be lost and nothing needs reverting. Relayed to S1 pre-emptively; **S1
  confirmed it had used the session scratchpad throughout** (`git archive 6ca9dcc` trees driven by
  `PYTHONPATH`, no `checkout`/`stash`/`restore`/`clean` in either tree), so the practice was S6's
  alone and no other slice adopted it. S1's readback is also the sharper form of the pattern: an
  out-of-tree `pytest_report_header` plugin printing module resolution **inside the run's own
  process**, which is what rules out the venv's editable install winning over `PYTHONPATH` — an
  assumption the simpler form leaves untested.
- **A16** — **a sabotage sweep is a deliberate temporary corruption of shared state, and must run
  against a `git archive` overlay, never a shared worktree.** The wave asked all six slices for a
  sweep and never said this. S2 swept `strategy.py` in place while S4 was measuring AC-5 against
  it; S4 took a run with the real fix present, then ninety seconds later saw
  `really_decreased = profit_prev < profit_2ago  # sabotage` in `git diff`. It correctly refused to
  quote a number in either direction rather than reporting an unreliable one. Nothing was lost —
  because the measuring agent noticed, not because the design prevented it.
  The rule is A14/A15's third face: concurrency and measurement do not share a working directory,
  and a sweep is *both* at once. Two slices worked this out unprompted (S3, S1) and swept against
  archive trees driven by `PYTHONPATH`; two did not (S2, S6). **A future wave's slice brief must
  state it at dispatch**, alongside the sweep instruction itself — the instruction and its
  precondition belong in the same sentence.
- **A17 — a rule recorded mid-wave must be *pushed to every live agent*, not merely embedded in the
  next brief.** A16 was violated **twice**, and on both occasions by an agent that had never been
  told it: S2 and S4 were both dispatched before A16 existed, and both were instructed to run a
  sabotage sweep with no statement of where. The rule was correct and the relay was not. The second
  violation put a live no-op sabotage of `gen_cost_coeffs`' cost-source lookup into the shared tree
  while S7 was measuring `market.agents` through it — an overlay that silently does nothing while
  the run still reports `Optimal` and `converged`. Caught by S5, which was measuring on an archive
  overlay and so could see the tree rather than absorb it.
  **Neither violation was the agent's fault.** When the orchestrator learns something mid-wave, the
  obligation is a broadcast to everyone already running, then the brief change for whoever comes
  next — in that order, because the running agents are the ones exposed now.
- **A11** — worktree setup is `uv sync --all-extras --all-groups`, then prove
  `uv run --no-sync mkdocs --version` **before** dispatching any docs or walk agent (M6 A27).
- **A12** — teardown sweeps both listeners on agent ports **and** any process whose command line
  names the worktree (M6 carry-over 13 — two orphaned `pytest` processes blocked removal).
- **A13** — `stop-guard.sh`'s Windows-path bug is still open; finished agents idle rather than
  exit. Reconcile against the artifact on disk, never the completion message (M7's own research
  agent delivered a stale completion message beside a fully updated file).

## ADR

**ADR-010** planned, written at Step 7. Two decisions, both already measured.

**D1** — AC-3's reproduction is stated as *exact inputs plus bounded outputs*, with no price-taker
short-circuit. Consequences: the all-price-taker case is an ordinary run of the general path, so
the loop and overlay are exercised by the row that proves them; the offer vector is a first-class
result member because an acceptance criterion reads it; and bit-identity was rejected as a goal
because reaching it would have made the criterion true by construction — the fourth instance in
this epic of a check that a sabotage cannot move.

**What an own-node agent can actually do** — and therefore what the loop must measure. A stateless
own-node strategy is a *local* hill climber, not a best responder: computing a best response means
clearing the market, which the observation withholds. Consequences: the observation carries two
rounds of the agent's own history, because one cannot tell it whether its last move helped; a
fixed-step climber never comes to rest, so termination is classified by the **amplitude** of the
oscillation it settles into, making `offer_tol >= 2 × step` derived rather than tuned; AC-4's
fixture is smooth by construction and the spec says so, because the climb provably stalls at a
local optimum when a competing unit puts a step between cost and peak; and the round-robin update
rule an earlier draft adopted was reverted, because the cycling it answered belongs to exact best
response, which M7 does not ship.

Expected further consequences from the audit and review, as in M6.

## Handoff

**Shipped 2026-08-29.** Wave head `0a4ce41` (33 commits), merged `--no-ff` as `473b718` on
`epic/01-foundation`, unpushed (the user's call, as M1–M6). Final sweep 1175 / 4, all gates clean.
Audit 8/0/0 (`record/m7-audit.md`); critic merge-ready as-is (`record/m7-critic.md`); walk
(`record/m7-walk.md`) three defects fixed. ADR-010 in `docs/design/decisions.md`. Carries and
lessons for M8 in `record/continuation-m7.md`. Nineteen findings (F1–F19), eight process
assumptions (A11–A18), four carries (C1–C4) above; spec A9 corrected in place.
