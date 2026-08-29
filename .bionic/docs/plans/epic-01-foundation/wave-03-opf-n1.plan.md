---
governing-skill: superpowers:writing-plans
sdlc-step: 3
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
model_plan:
  orchestrator: sonnet
  implementor: sonnet
  senior-implementor: opus
  researcher: sonnet
  test-runner: sonnet
  auditor: opus
  critic: opus
---

# Wave M3 plan — opf-n1

Spec: .bionic/docs/specs/epic-01-foundation/wave-03-opf-n1.spec.md (design pointer → epic
spec §Design, plus M3-local design). Branch: wave/03-opf-n1 off epic/01-foundation (dcdc1c9).
Worktree: C:\Claude Projects\mambo-power-m3 with `.bionic` junctioned to the main checkout
(remove the junction with git-bash `rm`, NOT PowerShell/cmd `rmdir` — see continuation-m2.md's
hook-bug note — before `git worktree remove`).

## SDLC State

integration-branch: epic/01-foundation
intent: build
rigor: audited
scale: wave
current: 9

- Step 0: prereqs: ok; configured 2026-08-23 via "confirm"; model_plan=sonnet/opus tiers (this
  session's actual model, corrected from M1/M2's stale fable-5); integration-branch=epic/01-foundation;
  walk=required (docs site is drivable, M2 stood it up)
- Step 1: scope closed 2026-08-23 via 3 scoping answers (fixture set = full M1/M2 set; AC
  feasibility check in-wave; N-1 branch outages only) in wave-03-opf-n1.spec.md sections
  Requirements + Not Doing + Prior art; research record/m3-research.md +
  .bionic/tmp/m3-pypsa-diag-result.md
- Step 2: design interview 2026-08-23 — frame ratified ("build with M4's market-clearing
  reuse in mind"), reuse-seam decision (array-level split, "matches"), S1 ratings
  (programmatic derivation, "go with the programmatic derivation"), S2 PyPSA (bounded
  diagnostic, "go with the bounded diagnostic pass" — resolved: RESOLVED, p_set fix),
  composed design ratified ("ok"); spec Design section written after ratification
- Step 3: wave-03-opf-n1.plan.md approved by user 2026-08-23 ("APROVED"); design + plan +
  matrix locked; worktree C:\Claude Projects\mambo-power-m3 created (base dcdc1c9, branch
  wave/03-opf-n1), .bionic junctioned and verified (git-bash `ls -la` shows symlink, spec
  files visible through it)
- Step 4: slices S1-S7 landed RED→GREEN as commits 2b31307, 3c84504, d6d3ef5, 9d317ee,
  8d2c4e6, 5fc26aa, f37815a — reports record/m3-s{1..7}-report.md; two slices (S3, S5)
  finished correctly but went idle without committing/reporting, taken over by the
  orchestrator per the non-response procedure (verified independently before landing, no
  changes made to their code — see those two reports' own "completed by the orchestrator"
  framing); real findings along the way: S2's QP-vs-LP cost handling + PTDF-vs-theta
  formulation caveat, S3's PWL/pandapower oracle limitation + honest LP-degeneracy handling,
  S4's LODF sign-convention bug, S6's stale "unknown kind" example regression, S7's AC
  vacuous-coverage-test fix + case14's real AC-infeasibility finding; worktree:
  C:\Claude Projects\mambo-power-m3; base-sha: dcdc1c9; branch: wave/03-opf-n1
- Step 5: walk-artifact: record/m3-walk-docs-site.md (real findings — MathJax broken on the
  2 new manual pages, stale home-page status/roadmap; neither is AC-9-gating but both are
  real, named for the fold); cmd: `uv run pytest -q -p no:cacheprovider` on wave head
  f37815a (plus ruff check, ruff format --check, mypy, `mkdocs build --strict`, 8 examples,
  uv build + wheel/sdist smoke); pass: 573; total: 573; output: record/
  m3-step5-tests-floor.md; auditor: m3-auditor (record/m3-audit.md) first-pass verdict
  REFUTED (1 row, AC-1's PyPSA half, proof gap honestly disclosed — not a reporting-contract
  violation, not a behaviour defect), closed by the R1 fold (commit 8fc8581, record/
  m3-r1-fold-report.md, 6 items) and re-audited CONFIRMED by m3-r2-reaudit (record/
  m3-r2-reaudit.md, 2026-08-24) — 593 tests, AC-1 row CONFIRMED, auditor-wave: CONFIRMED
- Step 6: stance 1 six-axis self-review record/m3-review-6axis.md (Correctness/Readability/
  Architecture/Duplication PASS, Security FLAG — PiecewiseCost.points unbounded, Performance
  FLAG — PTDF computed twice per solve_dc_opf call — both real, neither audit had surfaced);
  stance 2 independent critic record/m3-critic.md (ready-to-merge verdict; root-caused the
  case300 PyPSA residual independently — a real correction to 3 documents including this
  session's own re-audit, not a defect in the wave's solver code; 2 minor findings); folded
  as R3 (commit 4bd67d9, record/m3-r3-fold-report.md) — 596 tests, all green
- Step 7: adr: adrs/epic-01-foundation/adr-006-opf-array-level-reuse-seam.md — the array-level/
  Network-level split ratified in Step 2's design interview genuinely shapes M4 (market.nodal
  is expected to call opf.dc_opf.dc_opf/lmp_decomposition directly per the epic's own module
  table), the same "cannot change without a rewrite of the consumer" weight ADR-005 (M1) had;
  unlike M2, this wave earned an ADR. Lesser decisions (A1-A6) live in this plan's Assumptions.
- Step 8: merge: 5fa3285 (wave/03-opf-n1 4bd67d9 → epic/01-foundation, --no-ff, local; merge
  tree verified byte-identical to CI-proven wave head via `git diff 4bd67d9 HEAD --stat` =
  empty, so the 596/596 + CI 32781551954 evidence carries over without re-running the suite;
  pushing the epic branch is the user's call, same convention as M1/M2); worktree-removed:
  C:\Claude Projects\mambo-power-m3 (junction removed via git-bash `rm`); cleanup: done;
  tmp-wiped: .bionic/tmp emptied 2026-08-24; two junk files in the main checkout
  (.playwright-cli/, bash.exe.stackdump — leftovers from interrupted background-agent work)
  removed before merging; tasks-completed: all dispatch-ledger rows done or superseded
  (m3-r2-reaudit's row was never updated at the time, corrected before this check), none active
- Step 9: deploy: none this wave — PyPI publish is M9 (deploy_target: pypi applies at M9,
  same as M1/M2); verified-at: CI run 32781551954 on 4bd67d9 (success, the exact tree merged,
  confirmed byte-identical) + re-audit record/m3-r2-reaudit.md + Step 6 fold record/
  m3-r3-fold-report.md; monitor: GitHub Actions on every push to epic/01-foundation and
  wave/* (ci.yml); continuation: record/continuation-m3.md

## Slices

| Slice | Delivers | ACs | complexity | role |
|---|---|---|---|---|
| S1 fixtures | rating-derivation test helper (DC-solve once, margin above base-case flow); new derived MATPOWER fixture with convex PWL generator costs (case14-based) | AC-4 (fixture half), AC-5 (fixture half) | standard | implementor |
| S2 opf-core | `opf/dc_opf.py`: array-level `dc_opf(arr, cost_coeffs, options) -> OpfSolution` (LP over highspy, flow-limit rows from PTDF, duals); `opf/__init__.py:solve_dc_opf(net, options) -> OpfDcResult`; `lmp_decomposition(duals, ptdf) -> LmpBreakdown` | AC-1 (parity half), AC-2, AC-3 | complex | senior-implementor |
| S3 pwl | Convex segment/epigraph PWL cost rows inside `dc_opf`'s cost extraction; `opf.NonConvexCostError` guard; parity against S1's PWL fixture | AC-5 | standard | implementor |
| S4 contingency | `contingency/n1.py`: LODF fast-screen (`numerics.lodf`/`bridges`) → DC re-solve confirm → `N1Result`; brute-force all-outage agreement test (reuses `_brute_force_lodf.py`'s shape) | AC-4 (behavior half), AC-6 | complex | senior-implementor |
| S5 ac-check | `results.FeasibilityReport`; AC-feasibility check wired into `solve_dc_opf` (`options.ac_check`) | AC-7 | standard | implementor |
| S6 jobs | `opf.dc`/`n1` `KindSpec`s in `jobs.registry`; `INFEASIBLE_LP`/`UNBOUNDED_LP` `FailureCode`s + `run.py` except-chain wiring | AC-8 | standard | implementor |
| S7 docs | Manual pages (DC-OPF, N-1), `docs/api/opf.md` + `docs/api/contingency.md`, one new example script + CI + snippet embed | AC-9 | complex | senior-implementor |

Order: S1 and S2 run in parallel (disjoint files, no dependency — S2's core LP/duals work
needs no rating data; ratings only matter for AC-4/AC-6's constrained-path evidence). S4
starts once S1's ratings helper lands (parallel with S2/S3 otherwise — contingency never
calls `opf.dc_opf`). S3 starts once both S1 (PWL fixture) and S2 (LP builder to extend) land.
S5 starts once S2 lands (needs `OpfDcResult` to attach `ac_check` to). S6 starts once S2, S3,
S4, S5 all land (jobs wraps every kind). S7 last. Every slice RED → GREEN.

## Verification Matrix

stack-health: before (M2 close, record/m2-step5-tests-floor.md): 492 tests, same runtime
stack as M2 plus nothing new yet; after (Step 5, record/m3-step5-tests-floor.md): same
runtime stack, versions unbumped (numpy 2.5.2, scipy 1.18.0, pydantic 2.13.4, highspy
1.15.1, pandapower 3.3.0, pypsa 1.2.4 — pypsa now load-bearing as S3's oracle-diagnostic
dep, not just M1/M2's dev-only presence); 573 tests (+81), full suite green, ruff/format/
mypy clean, mkdocs --strict 0 real warnings, 8/8 examples, build+wheel/sdist smoke clean

walk-artifact: record/m3-walk-docs-site.md (docs-site walk in a real browser by an agent
that had not read the ACs) — real findings, not AC-shaped by design: MathJax rendering
silently broken on both new manual pages (the N-1 page's core LODF formula renders as
unreadable raw TeX fragments), and the home page's status callout + roadmap table are
stale (still "M2 in progress", no link to the new OPF/N-1 content). Minor: a public
`contingency` docstring leaks "wave M3 W5" internal shorthand; code-block clipping is a
site-wide pre-existing behavior, not new; mermaid lazy-render and the GitHub-API 404
console error both look intentional/cosmetic. None of these were AC-9's literal criterion
(`mkdocs build --strict` exit 0 + pages present + coverage test — all true), but the
MathJax break and the stale home page are real defects worth folding before close.

auditor-wave: CONFIRMED — record/m3-r2-reaudit.md, 2026-08-23/24 (scoped re-audit, superseding
the original record/m3-audit.md REFUTED verdict). The original audit's sole refutation ground —
AC-1's undischarged PyPSA secondary-oracle half — was closed by the R1 fold
(record/m3-r1-fold-report.md, commit 8fc8581) and independently re-executed and re-measured here:
`tests/parity/test_opf_vs_pypsa.py` re-run fresh (20/20 passed) and its residuals independently
recomputed by a standalone script outside the test's own assertions, matching the fold report's
table exactly on all 5 fixtures. Every other row (AC-2 through AC-9) was already CONFIRMED by the
original audit and is untouched by this fold, with AC-6's revert-and-watch (LODF sign-fix
stubbed → all 5 fixtures' brute-force agreement tests turn red, everything else green) still the
strongest-power evidence in the wave. Coverage: CONFIRMED, no wave-level hole. The fold's other 5
items (AC-4 provenance citation, home page staleness, MathJax root-cause fix, docstring shorthand
cleanup, Assumption A6) were spot-checked and found genuine, not rubber-stamped: MathJax's before/
after diff confirms a real JS string-escaping bug, correctly diagnosed and fixed, browser-verified
post-fix (manual/opf 6/6, manual/n1 1/1 arithmatex blocks processed); `git show --stat 8fc8581`
confirms no scope creep beyond the 5 files claimed; full suite 593/593, ruff/mypy/mkdocs --strict
clean, re-executed fresh.

| AC | tier | status | evidence | auditor |
|---|---|---|---|---|
| AC-1 | T2 | discharged | see AC-1 | CONFIRMED (record/m3-r2-reaudit.md) — both halves now committed and independently re-executed: pandapower 20/20 (original audit), PyPSA 20/20 re-run fresh with residuals independently recomputed and matched exactly to the fold's table on all 5 fixtures; case300's separately wider PyPSA band is a named, bounded exception the spec's own AC-1 text anticipated, not a new refutation ground |
| AC-2 | T1 | discharged | see AC-2 | CONFIRMED (re-executed) |
| AC-3 | T1 | discharged | see AC-3 | CONFIRMED (re-executed) |
| AC-4 | T1 | discharged | see AC-4 | CONFIRMED (re-executed, 18/86 on case14 matches exactly; minor provenance-citation nit cites W3 only, not W5 — substance whole) |
| AC-5 | T2 | discharged | see AC-5 | CONFIRMED (degeneracy handling read directly and confirmed honest) |
| AC-6 | T1 | discharged | see AC-6 | CONFIRMED (re-executed, all 5 fixture counts match exactly; revert-and-watch VALIDATED — record/m3-audit.md §2b) |
| AC-7 | T1 | discharged | see AC-7 | CONFIRMED (test names + commit diff verified directly) |
| AC-8 | T1 | discharged | see AC-8 | CONFIRMED (INFEASIBLE_LP/UNBOUNDED_LP wiring read directly in registry.py/run.py) |
| AC-9 | T2 | discharged | see AC-9 | CONFIRMED (--strict re-executed; walk's MathJax finding re-verified in a real browser, real but pre-existing/site-wide — record/m3-audit.md §3) |

AC-1:
  criterion: opf.solve_dc_opf matches pandapower rundcopp (primary) and PyPSA optimize
    (secondary, p_set cleared) on case14/case_ieee30/case57/case118/case300 within a
    tolerance measured and pinned at implementation
  provenance: wave spec W1, W8; record/m3-research.md §3; .bionic/tmp/m3-pypsa-diag-result.md
  fixture-fidelity: verbatim MATPOWER bytes already committed by M1 (case14/30/57/118/300);
    no new fixture data for this AC
  tier-run: S2 (pandapower half):
    `uv run --no-sync pytest -q -m parity tests/parity/test_opf_vs_pandapower.py` — 20 passed
    (5 fixtures x 4 tests). Measured residuals (not assumed): objective cost within 1.6e-11
    relative (worst: case_ieee30), per-generator dispatch within 0.0142 MW absolute (worst:
    case300, 69 generators) — tolerances pinned with margin above measured
    (COST_REL_TOL=1e-7, DISPATCH_ABS_TOL_MW=0.05). A real formulation difference was found and
    checked, not silently assumed equivalent: pandapower's rundcopp marks the slack-bus
    generator (ext_grid) `controllable=False` (a full nodal theta-based OPF — its dispatch is
    the network's balance residual, not a bounded decision variable), while opf.dc_opf's
    PTDF-based formulation makes every generator, including the slack-bus one, a normal
    bounded decision variable in a single system-wide balance row. The two are only
    guaranteed to coincide when (a) no branch is rated — confirmed true of all 5 fixtures
    (m3-research.md §6); a dedicated test (`test_every_branch_is_unconstrained_so_no_flow_
    limit_dual_binds`) asserts every branch's flow-limit dual is exactly 0 on all 5 fixtures —
    and (b) the slack-bus generator's own bounds never bind in the oracle's
    unconstrained-by-bound dispatch, measured true on all 5 fixtures (not proven true in
    general — a fixture with a tightly-bound slack generator could diverge; none of these 5
    do).

    R1 fold (PyPSA half, closing the audit's one refuted row): `tests/parity/test_opf_vs_pypsa.py`
    (new) — `uv run --no-sync pytest -q -m parity tests/parity/test_opf_vs_pypsa.py` — 20
    passed (5 fixtures x 4 tests). Promotes `.bionic/tmp/m3-pypsa-diag-result.md`'s bounded
    diagnostic to a committed, repeatable test: `import_from_pypower_ppc` then
    `n.generators["p_set"] = float("nan")` before `optimize()` (the root-caused fix — PyPSA
    otherwise pins every generator's dispatch to MATPOWER's unbalanced base-case `PG`, making
    the nodal balance infeasible); `gencost`'s `c2`/`c1` bridged into
    `marginal_cost_quadratic`/`marginal_cost` (PyPSA's import path does not read `gencost` at
    all). RED confirmed directly: with the `p_set` clear temporarily removed,
    `test_pypsa_itself_converges_optimal[case14]` fails with HiGHS `Model status: Infeasible`,
    reproducing the diagnostic's own original symptom; restored, GREEN. Residuals measured
    fresh in the test itself (not hardcoded from the diagnostic's numbers): case14/
    case_ieee30/case57/case118 match within 1.27e-12 relative cost / 1.87e-03 MW dispatch
    (worst: case118 both) — `TIGHT_COST_REL_TOL=1e-9`, `TIGHT_DISPATCH_ABS_TOL_MW=0.01`, pinned
    with margin above measured. case300 does not fit that band: 7.37e-05 relative cost
    (~0.0074%) / 0.082 MW dispatch — a separately wider `WIDE_COST_REL_TOL=2e-4`/
    `WIDE_DISPATCH_ABS_TOL_MW=0.5` covers case300 alone.

    R3 fold (case300 root-cause correction, `m3-critic.md` Issue 1, re-verified fresh here):
    case300's residual is **not** a bus-numbering/index-alignment artifact — that guess was
    published here, in the test's own module docstring, and in `m3-r2-reaudit.md` without ever
    being checked, and turned out to be wrong. The real cause: case300 is the only one of the 5
    OPF fixtures with nonzero MATPOWER bus `GS` (shunt conductance) — 17 buses summing to
    exactly 1.3 MW (re-derived directly from the fixture's raw `bus` matrix). `opf.dc_opf`'s
    balance row correctly includes it (`Σ p_g == Σ p_load + Σ g_shunt`); `solve_dc_opf`'s total
    case300 dispatch (23527.149999999998 MW) matches the fixture's true load-plus-shunt total
    exactly. PyPSA's `import_from_pypower_ppc`/DC-LOPF silently drops bus shunt conductance
    from its own power balance: its total case300 dispatch (23525.850000000006 MW) equals only
    the raw `PD` (load) column, zero `GS` contribution (`n.loads["p_set"].sum() == raw bus PD
    sum`, 23525.85, checked directly). The 1.3 MW gap is redistributed thinly across 68 of 69
    generators by the QP's marginal-cost weighting — the textbook signature of a dropped
    fixed-load term, not a mislabelled index (an index swap would change *who* is credited,
    never the dispatch *totals*, which differ by exactly the GS sum to 13 significant figures).
    `dc_opf` is provably *more* complete than this oracle on this one point, not less; no code
    or tolerance change is needed. Corrected in all three places that repeated the original
    guess: this evidence block, the test's module docstring, and `m3-r2-reaudit.md` (in place,
    noting it supersedes the original text).
  readback: S2 done 2026-08-23 (m3-s2-report.md, commit d6d3ef5) — pandapower half only, PyPSA
    named as an open carry-over at the time (time budget went to root-causing the QP-vs-LP
    cost-formulation finding, load-bearing for AC-1 to pass at all on the pandapower half: the 5
    fixtures' gencost carries real quadratic coefficients, so a pure-linear-cost LP would not
    have matched pandapower's dispatch — see m3-s2-report.md). R1 fold done 2026-08-23
    (m3-r1-fold-report.md): PyPSA half closed — `tests/parity/test_opf_vs_pypsa.py` committed
    and passing (20/20), promoting the Step-1/2 diagnostic to real, repeatable evidence with
    fresh-measured residuals. Both AC-1 halves are now genuinely, fully evidenced.
AC-2:
  criterion: hand-built network with a known binding flow limit and a bound-pinned generator
    — dc_opf's duals reproduce the correct balance/flow-limit/bound-reduced-cost values
  provenance: wave spec W1; record/m3-research.md §1
  tier-run: S2: `uv run --no-sync pytest -q tests/unit/test_opf_dc.py` — 5 passed. Hand-built
    3-bus/3-generator triangle network (equal branch reactances; module docstring in
    tests/unit/test_opf_dc.py derives the expected numbers by hand, cross-checked against
    numerics.ptdf's own trusted, already-parity-tested output — not against dc_opf's own
    answer). Confirmed: balance dual == 10.0 exactly (the unconstrained slack-bus generator's
    own linear cost coefficient — provable in closed form because a slack bus's PTDF column is
    always exactly zero, so no congestion term enters its stationarity condition); flow-limit
    dual nonzero exactly on the one rated, binding branch (br12), zero on the two unrated
    branches; generator bound reduced cost nonzero exactly on the one pinned generator (g0, at
    its p_max), zero on the other two (both interior, as designed).
  readback: S2 done 2026-08-23 (m3-s2-report.md, commit d6d3ef5).
AC-3:
  criterion: dc_opf(arr, cost_coeffs, options) takes a caller-supplied cost array independent
    of Network; lmp_decomposition is standalone and independently callable
  provenance: wave spec W2; user 2026-08-23 design interview Q1
  tier-run: S2: `uv run --no-sync pytest -q tests/unit/test_opf_dc.py::test_dc_opf_takes_cost_
    coeffs_independent_of_network tests/unit/test_opf_dc.py::test_lmp_decomposition_is_
    standalone_and_independent_of_solve_dc_opf` — 2 passed. Same NetworkArrays (no cost
    anywhere on it — it never had one), two different synthetic cost_coeffs arrays (g2 cheaper
    vs more expensive than g1) give two different, each-internally-LP-optimal dispatches
    (g2=85 vs g2=30 MW; both satisfy the balance and bounds regardless of which array was
    used). lmp_decomposition called directly with hand-built OpfDuals/PTDF (2 branches x 3
    buses), zero calls to dc_opf/solve_dc_opf anywhere in that test — energy/congestion/lmp
    all verified against the formula by hand.
  readback: S2 done 2026-08-23 (m3-s2-report.md, commit d6d3ef5).
AC-4:
  criterion: rating-derivation helper never binds on the unmodified base case, and at least
    one outage on at least one fixture violates the derived rating
  provenance: wave spec W3; record/m3-research.md §6
  tier-run: S1 (fixture half only — the helper itself, `tests/_rated.py`; the behavioral N-1
    violation-confirm path is S4's job): `uv run --no-sync pytest -q tests/unit/
    test_rated_helper.py` — 5 passed. `RATING_MARGIN = 1.2` (20% headroom above base-case
    `|p_from_mw|`, floor 1.0 MVA); base-case dispatch never violates its own derived rating on
    case14/case118 (unit test), and a fixture-wide LODF sanity sweep (script, not a committed
    test) confirms hundreds of outage/branch pairs *would* violate the derived ratings on
    every fixture at this margin (case14 81/17, case_ieee30 229/35, case57 636/75, case118
    1173/166, case300 2981/297 — pairs/distinct-outages) — full table in m3-s1-report.md.
  readback: S1 done 2026-08-23 (m3-s1-report.md, commit 2b31307). S4 still owes: the actual
    LODF-screen-then-reslve confirm using this helper's ratings, on real N-1 outages.

  S4 behavioral half: `uv run --no-sync pytest -q tests/unit/
    test_contingency_n1.py::test_ac4_behavioral_case14_has_a_confirmed_n1_violation` — 1
    passed. `contingency.n1` on `tests._rated.rated_network(case14)` confirms 18 outages / 86
    outage-branch pairs with at least one genuinely violating branch by a real DC re-solve (not
    just the LODF estimate) — closing the loop S1 opened. (18/86, not S1's reported 17/81:
    root-caused, not just noted — S1's `probe_margin.py` fed the *unsigned* base-case flow into
    the LODF re-composition formula (`|base_flow| + lodf[l,k]*|base_flow[k]|`); the correct
    formula needs the *signed* flow, taking the absolute value only of the final estimate
    (`contingency.n1.screen_n1`'s own docstring). Reproducing the unsigned version against
    case14 by hand gives exactly 17/81, confirming that as the cause. This did not affect S1's
    margin choice or its AC-4 fixture-half evidence — both only needed "violations exist", not
    an exact count — and `probe_margin.py` was never committed, so nothing there needs fixing.
    AC-6 independently proves the corrected, signed formula is right: its brute-force agreement
    test matches a real DC re-solve exactly on all five fixtures, including case14.)
  readback (S4): done 2026-08-23 (m3-s4-report.md, commit TBD).
AC-5:
  criterion: opf.dc_opf on the new PWL-cost derived fixture matches an oracle (pandapower if
    it supports PWL, else a hand dense-LP comparison — resolved at implementation per spec
    assumption b); a non-convex PWL cost raises NonConvexCostError pre-solve
  provenance: wave spec W4; record/m3-research.md §2
  fixture-fidelity: new derived fixture, case14-based, documented cell by cell (M1-style)
  tier-run: S1 (fixture half only — `fixtures/matpower/derived/case14_pwl.m` well-formed and
    importable; the OPF-solve-vs-oracle half and the NonConvexCostError guard are S3's job):
    `uv run --no-sync pytest -q tests/unit/test_fixtures_pwl.py` — 4 passed. `case14_pwl.m` =
    `case14.m` with `mpc.gencost` rows 2 and 3 (gen-2/bus 2, gen-3/bus 3) converted MODEL 2 ->
    MODEL 1, four breakpoints each, strictly-increasing (convex) segment slopes 20/25/30 and
    20/30/40 $/MWh respectively; rows 1/4/5 unchanged, widened with inert trailing zero
    padding for row rectangularity. Round-trips through `io.matpower.load` into
    `PiecewiseCost` with the documented points; untouched generators keep `PolynomialCost`.
  readback: S1 done 2026-08-23 (m3-s1-report.md, commit 2b31307). S3 (behavioral half) done
    2026-08-23, commit 8d2c4e6 (record/m3-s3-report.md — completed by the orchestrator; agent
    finished correctly, went idle before committing/reporting): 26 tests pass
    (test_opf_dc_pwl.py, test_opf_pwl_guard.py, test_opf_dc_case14_pwl.py). Oracle finding:
    pandapower's rundcopp genuinely supports PWL costs (hand-verified) but refuses to mix
    quadratic and piecewise costs anywhere in the same network, which case14_pwl.m does by
    design (gen-1/4/5 keep real quadratic coefficients) — so pandapower can't oracle this
    fixture; fell back to an independent lambda-iteration economic-dispatch solver per spec
    Assumption b, since zero rated branches on case14 collapses DC-OPF to classic
    equal-marginal-cost dispatch. Found and honestly asserted a genuine LP degeneracy: two
    breakpoints tie in marginal cost, so gen-2/gen-3's ~22.8 MW split has multiple LP optima
    — asserted as an interval; the other 3 generators and total cost (6239.0 exactly) are
    pinned exactly. NonConvexCostError raised pre-solve on a hand-built non-convex case.
AC-6:
  criterion: LODF-screen-then-reslve confirmed-violation set equals the brute-force
    all-branch-outage confirmed-violation set, on every fixture, using AC-4's derived ratings
  provenance: wave spec W5; record/m3-research.md §4
  tier-run: `uv run --no-sync pytest -q -s tests/unit/test_contingency_n1_brute_force.py` — 5
    passed (unit tier). `mambo_power.contingency.n1`'s confirmed-violating outage set equals
    `tests._brute_force_n1.brute_force_n1`'s (every non-bridge outage DC-re-solved directly, no
    LODF pre-filter) exactly, on every one of the five OPF fixtures, using
    `tests._rated.rated_network`'s derived ratings: case14 18, case_ieee30 34, case57 75,
    case118 166, case300 293 confirmed-violating outages. These are close to but not identical
    to S1's own screen-only sanity-sweep outage counts (17, 35, 75, 166, 297) — case57/case118
    coincide exactly, case14 is one higher, case_ieee30/case300 are one and four lower — which
    is expected, not a red flag: S1's numbers are *screen-only* counts from the same buggy
    unsigned-flow LODF formula root-caused under AC-4 above, while these are *DC-re-solve-
    confirmed* counts from the corrected, signed formula; the two need not move in the same
    direction fixture by fixture. AC-6 itself is the actual proof of correctness (screen-then-
    confirm equals a full brute-force re-solve sweep with no LODF involved at all, on every
    fixture), not agreement with the earlier, uncommitted, differently-formulated script. Measured wall time per fixture (`uv run` inside pytest, this machine, with a
    concurrent sibling agent also running CPU-heavy tests in the same shared worktree):
    case14 ~0.13s, case_ieee30 ~0.25-0.33s, case57 ~0.66-1.6s, case118 ~2.5-5.9s,
    case300 ~10-19s combined (screen-then-confirm + brute force, both run inside the one
    parametrized case). Isolated (no sibling contention, bare script, not pytest): case300
    alone is `screen_n1` 0.06s + `confirm_n1` 3.96s + `brute_force_n1` 1.63s ≈ 5.6s total —
    comfortably inside M1's ~10s unit/parity tier-crossing threshold, matching record/
    m3-research.md §4's <1s-per-brute-force estimate once `confirm_n1`'s deep-copy-once pattern
    is used correctly (see report: an early version deep-copied the network per outage instead
    of once, measured ~20x slower — fixed before this evidence was captured). Under this
    session's actual concurrent load the case300 *pytest* case sometimes crosses 10s combined;
    kept in the unit tier per spec Design item 5's own framing ("likely staying in the unit
    tier ... reconfirm once the real test exists") since the contention-free number is well
    clear and the slowdown is external (a sibling agent's own CPU-bound tests), not a property
    of this test — flagged here rather than silently moved to the parity tier, per the task
    brief's instruction to report this as information rather than treat it as an automatic
    blocker.
  readback: S4 done 2026-08-23 (m3-s4-report.md, commit TBD). Agreement held on every one of
    the five fixtures — the screen-then-confirm pipeline misses nothing the brute force would
    catch and confirms nothing it would not.
AC-7:
  criterion: FeasibilityReport catches a known thermal/voltage violation on a hand case,
    reports none on a clean case, and its converged flag matches solve_ac's own
  provenance: wave spec W6
  tier-run: `uv run --no-sync pytest -q tests/unit/test_feasibility.py
    tests/unit/test_opf_solve_dc_opf.py` -> 13 passed. results.feasibility_report(ac, net)
    builds thermal violations from BranchResult.loading_pct > 100% (unrated branch never
    contributes one) and voltage violations from Bus.v_min_pu/v_max_pu vs solved vm_pu (unbounded
    bus never contributes one); wired into solve_dc_opf behind OpfDcOptions.ac_check. Hand cases:
    thermal overload caught, voltage bound violation caught, clean case empty on both lists,
    converged flag passed through unchanged from solve_ac (not recomputed). ruff/mypy clean.
  readback: S5 done 2026-08-23, commit 9d317ee (record/m3-s5-report.md — completed by the
    orchestrator: the implementing agent finished the work correctly but went idle before
    committing or reporting; verified independently before landing, no changes made to its code)
AC-8:
  criterion: jobs.run/run_json for opf.dc and n1 are pure, JSON round-trip, never raise;
    an infeasible LP yields INFEASIBLE_LP not INTERNAL; jobs.KINDS lists exactly 4 kinds
  provenance: wave spec W7
  tier-run: S6: `uv run --no-sync pytest -q tests/unit/test_jobs.py` — 32 passed (unit tier).
    Two new KindSpecs registered exactly per M2's four-edit mechanism (options model, result
    model, runner, KindSpec) — opf.dc (OpfDcOptions/OpfDcResult/_run_opf_dc) and n1
    (N1Options/N1Result/_run_n1). `jobs.KINDS` now lists exactly `{"pf.ac", "pf.dc", "opf.dc",
    "n1"}`; `test_every_kind_has_models_and_a_callable_runner` asserts each spec's options/result
    models and runner directly. Purity (`test_run_is_pure_equal_results_modulo_timing`) and JSON
    round-trip (`test_result_round_trips_through_json_with_the_kinds_result_type`) tests
    parametrized/extended to cover opf.dc and n1 alongside pf.ac/pf.dc. New
    `INFEASIBLE_LP`/`UNBOUNDED_LP` FailureCodes: `solve_dc_opf` itself never raises on a
    non-Optimal status (module docstring); the opf.dc *runner* (`jobs/registry.py:_run_opf_dc`)
    checks `OpfDcResult.status` after calling it and raises a new job-local exception
    (`InfeasibleLpError`/`UnboundedLpError`) on anything but `"Optimal"` — `"Unbounded"` maps to
    `UnboundedLpError`, every other non-Optimal status (in practice just `"Infeasible"`) maps to
    `InfeasibleLpError`; `jobs/run.py`'s runner-exception except-chain gained two matching
    clauses mapping these to the new codes, structurally mirroring the M2 R1 fold's
    `UnsolvableNetworkError` -> `UNSOLVABLE_NETWORK` precedent even though the underlying
    condition here is a returned status string, not a raised exception, inside `solve_dc_opf`
    itself. `test_infeasible_opf_dc_is_infeasible_lp_not_internal`: a hand-built case14 variant
    (every generator's `p_max_mw` collapsed to 0.01, load unreachable) yields `status="failed"`,
    `error.code == "INFEASIBLE_LP"` — proving the deliberate AC-8 distinction from `pf.ac`'s
    non-convergence (still `status="ok"`, `test_non_convergence_is_ok_with_converged_false`,
    unmodified). `SolveResult.result`'s union widened to `AcPowerFlowResult | DcPowerFlowResult
    | OpfDcResult | N1Result` in `jobs/models.py`.
    RED confirmed by `git stash`-ing only the four `src/mambo_power/jobs/*.py` implementation
    files (keeping the updated test file) and re-running: 9 failures — `UNKNOWN_KIND` where
    opf.dc/n1 results or `INFEASIBLE_LP` were expected, exactly the new/changed assertions.
    Popped the stash and re-ran: 32 passed.
    A real regression this change caused was caught by the full suite (not by test_jobs.py
    itself): `test_unknown_kind_is_a_failed_result` and `examples/04_jobs_api.py`'s own
    "unknown kind" demo both used `kind="opf.dc"` as their unknown-kind example, which is no
    longer unknown once registered — both switched to `kind="market.nodal"` (a real future kind
    name per the wave spec's own provenance comment, still unregistered). `examples/` is not
    named in this slice's out-of-scope list (only `docs/` is); `docs/manual/jobs.md` has the
    same now-stale "opf.dc is unknown" prose example but nothing executes/tests it today (no
    test found under `tests/` referencing it), and `docs/` is explicitly out of scope for this
    slice — left for S7 (docs) to fix.
    Full repo suite (`uv run --no-sync pytest -q`) — 572 passed (571 + this slice's own new
    tests), `ruff check .` / `ruff format --check .` clean, `mypy` (project config) clean.
  readback: S6 done 2026-08-23 (m3-s6-report.md, commit 5fc26aa).
AC-9:
  criterion: mkdocs build --strict exits 0 with new OPF/N-1 manual + API pages; symbol-coverage
    test passes for opf/contingency without modification; new example exits 0 in CI and is
    snippet-embedded
  provenance: wave spec W9
  fixture-fidelity: the built site is the artifact, same as M2's AC-9(docs)
  tier-run: S7: `uv run --no-sync mkdocs build --strict` — exit 0, no anchor warnings (two were
    found and fixed: a mistyped numerics.md PTDF anchor, a dangling #verification link — both
    real, not pre-existing). `uv run --no-sync pytest -q tests/unit/test_api_docs_coverage.py`
    — 2 passed. One correction to this AC's own framing, found while implementing it:
    `tests/unit/test_api_docs_coverage.py`'s `PACKAGES` tuple is a hand-maintained literal
    (`("model", "io", "numerics", "pf", "results", "jobs")`), not a generic filesystem walk —
    "walks packages generically" (this AC's provenance framing) describes what it does *within*
    a listed package (`pkgutil.iter_modules`), not *which* packages it lists. Confirmed by
    running the test unmodified first: it passed (2/2) with `opf`/`contingency` entirely
    unwalked — a vacuous pass, not evidence of coverage. Added `"opf"`, `"contingency"` to
    `PACKAGES` (one line, mechanical, the same extension every prior wave's own packages
    required when they shipped) and re-ran: still 2/2, now actually exercising the new
    packages' submodules. `docs/api/opf.md`/`docs/api/contingency.md` each carry a submodule
    `:::` block (`opf.dc_opf`, `contingency.n1`) mirroring the M2 R1 fold's `pf.ac_newton` fix —
    without them, `OpfDuals`/`OpfSolution`/`LmpBreakdown` and `N1Screen`/`screen_n1`/
    `confirm_n1` (none re-exported into their package `__init__.py`) would show as coverage
    gaps once `PACKAGES` was widened; verified by running the coverage test both before and
    after adding those blocks. `uv run --no-sync pytest -q tests/unit/test_examples_run.py` —
    10 passed (the new `08_opf_and_n1.py` picked up generically by the directory glob, no edit
    needed to that test file); `uv run --no-sync python examples/08_opf_and_n1.py` — exit 0
    directly, real output verified (case14's own DC-OPF-optimal dispatch is AC-infeasible on 3
    buses by voltage — an unplanned but accurate illustration of `ac_check`). Full repo suite
    (`uv run --no-sync pytest -q`) — 573 passed (572 + this slice's one new example test);
    `ruff check .` / `ruff format --check .` clean; `mypy` (project config) clean.
  readback: S7 done 2026-08-23 (m3-s7-report.md, commit f37815a). All four AC-9 sub-claims
    (mkdocs strict build, coverage test, example exit-0, snippet embed) independently verified,
    not assumed from a single green run.

## Dispatch ledger

| id | role | unit | deliverable | status |
|---|---|---|---|---|
| m3-research | researcher | Step 1/2: OPF/N-1 groundwork — highspy duals, PWL-as-LP, fixture survey, N-1 brute-force cost, AC-feasibility shape, jobs mechanics, module layout | record/m3-research.md | done (verified on disk; two load-bearing findings: zero rated branches in any fixture, PyPSA needs a p_set-clearing fix) |
| m3-pypsa-diag | researcher | Bounded diagnostic (capped ~20-25 min): why PyPSA optimize is infeasible on all 5 fixtures — progress n/a (short task), deliverable a scratch note not a canonical record | .bionic/tmp/m3-pypsa-diag-result.md | done (RESOLVED: import_from_pypower_ppc pins p_set to MATPOWER's unbalanced base-case PG; clearing it before optimize fixes all 5) |
| m3-s1-fixtures | implementor | S1 fixtures: rating-derivation test helper + PWL-cost derived fixture — progress .bionic/tmp/m3-s1-progress.md, cadence 10m, ~45 min | record/m3-s1-report.md + commit on wave/03-opf-n1 | done (commit 2b31307, pushed; 501 tests (492+9); RATING_MARGIN=1.2, real violations confirmed on all 5 fixtures via LODF sanity sweep; case14_pwl.m derived fixture round-trips; plan AC-4/AC-5 fixture-half evidence filled in by S1 itself) |
| m3-s4-contingency | senior-implementor | S4 contingency: contingency/n1.py LODF screen + DC reslve confirm + N1Result; brute-force all-outage agreement test — progress .bionic/tmp/m3-s4-progress.md, cadence 10m, ~75 min | record/m3-s4-report.md + commit on wave/03-opf-n1 | done (commit 3c84504, pushed; AC-6 brute-force agreement holds on all 5 fixtures; AC-4 behavioral half closed, 18/86 confirmed on case14; 2 real bugs found+fixed — LODF sign convention, per-outage deep-copy perf; staged its own results/__init__.py addition surgically via hash-object/update-index to avoid sweeping S2's uncommitted work; 524 tests) |
| m3-s2-opf-core | senior-implementor | S2 opf-core: opf/dc_opf.py array-level LP builder + duals + lmp_decomposition + solve_dc_opf wrapper (polynomial costs only) — progress .bionic/tmp/m3-s2-progress.md, cadence 10m, ~75 min | record/m3-s2-report.md + commit on wave/03-opf-n1 | done (commit d6d3ef5; 539 tests repo-wide; QP-vs-LP cost finding load-bearing for AC-1 — see report; plan AC-1(parity half)/AC-2/AC-3 evidence filled in by S2 itself; PyPSA half of AC-1 not attempted, named as carry-over) |
| m3-s5-ac-check | implementor | S5 ac-check: results/feasibility.py FeasibilityReport completed + wired into solve_dc_opf's ac_check option — progress .bionic/tmp/m3-s5-progress.md, cadence 10m, ~40-50 min | record/m3-s5-report.md + commit on wave/03-opf-n1 | done (commit 9d317ee, pushed; 13/13 own tests, ruff/mypy clean — non-response procedure: agent finished the work but went idle before committing/reporting; orchestrator verified and landed it as-is) |
| m3-r3-fold | senior-implementor | R3 fold: case300 PyPSA root-cause correction (3 places), PiecewiseCost.points bound, PTDF double-computation fix, docstring/Field cleanup — progress .bionic/tmp/m3-r3-progress.md, cadence 10m, ~45-60 min | record/m3-r3-fold-report.md + commit on wave/03-opf-n1 | interrupted (user stopped all background agents 2026-08-24; left one good, verified, uncommitted edit — item A's test_opf_vs_pypsa.py docstring correction — nothing else started; superseded by m3-r3-fold-2, which builds on that edit rather than redoing it) |
| m3-r3-fold-2 | senior-implementor | R3 fold retry: same scope as m3-r3-fold, resuming from its one uncommitted edit — progress .bionic/tmp/m3-r3-progress.md, cadence 10m, ~45-60 min | record/m3-r3-fold-report.md + commit on wave/03-opf-n1 | done (commit 4bd67d9, pushed, CI 32781551954 success; all 5 items closed; 596 tests; caught and fixed its own false-positive spy test for item C by deliberately reverting the fix and confirming the test failed to go RED, before trusting it) |
| m3-review-6axis | code-reviewer | Step 6 stance 1: six-axis review of dcdc1c9..8fc8581 (correctness, readability, architecture + closure, security, performance, duplication vs ownership table) | record/m3-review-6axis.md | done (Correctness/Readability/Architecture/Duplication PASS; Security FLAG — PiecewiseCost.points has no upper bound, caller-reachable unbounded-work vector via network data; Performance FLAG — PTDF computed twice per solve_dc_opf call, ~62% of warm case300 runtime; both new findings neither audit surfaced; 1 test-gap note on FeasibilityReport edges) |
| m3-critic | critic | Step 6 stance 2: adversarial critic over spec + plan + diff + both audits; ~45-60 min | record/m3-critic.md | done (ready-to-merge verdict; root-caused the case300 PyPSA residual independently — PyPSA silently drops bus shunt conductance (GS) from its balance, dc_opf is provably MORE correct, not less — 3 documents including this session's own re-audit repeated an unverified "bus numbering" guess; also found a docstring-shorthand inconsistency one file away from the fold's own touched package, and a stale source-only Field description; 3 falsification attempts failed clean) |
| m3-r2-reaudit | auditor | Step 5 re-audit, scoped: AC-1 row only + wave-level re-verdict, against fold commit 8fc8581 — ~30-40 min | record/m3-r2-reaudit.md | done (AC-1 row CONFIRMED, PyPSA test independently re-executed and residuals re-measured digit-for-digit; auditor-wave: CONFIRMED; ledger row was never updated at the time, corrected here) |
| m3-r1-fold | senior-implementor | R1 fold: AC-1 PyPSA parity test (closes the audit's one REFUTED row), AC-4/W5 citation nit, home page staleness, MathJax rendering root-cause, docstring shorthand cleanup — progress .bionic/tmp/m3-r1-progress.md, cadence 10m, ~60-90 min | record/m3-r1-fold-report.md + commit on wave/03-opf-n1 | done (commit 8fc8581, pushed, CI 32685413387 success; all 6 items closed; 593 tests; MathJax root cause was a real JS string-escaping bug in mathjax.js, not just the CDN-pin guess — verified live in browser before/after on both new pages plus the audit's numerics.md repro; orchestrator investigated item F's flagged follow-up (3 more files with the same shorthand) and found it's a pervasive 22-file house convention across M1/M2/M3, not a defect — reverted the one extra fix attempted, logged as Assumption A6 instead of chasing it) |
| m3-auditor | auditor | Step 5 exit gate: coverage / power / authenticity over spec + design + matrix + record; ≤3 re-executions; revert-and-watch via a fresh test-runner in a throwaway worktree | record/m3-audit.md | done (auditor-wave: REFUTED — AC-1's PyPSA half undischarged, honestly logged, not a behaviour defect; all other 8 rows CONFIRMED; coverage CONFIRMED, no hole; revert-and-watch on AC-4/AC-6's LODF sign fix VALIDATED; walk's MathJax finding re-verified real but pre-existing/site-wide) |
| m3-floor | test-runner | Step 5 tests floor on f37815a: discovered suites (ruff, format, mypy, pytest tiers + full, mkdocs --strict, examples x8, build + wheel/sdist smoke, case300 opf/n1 timing), stack-health | record/m3-step5-tests-floor.md | done (all green on f37815a: 573/573 tiers reconcile exactly; ruff/format/mypy clean; mkdocs strict 0 real warnings; examples 8/8; build+smoke clean; AC-7-style case300 timing still <1s; bonus case300 opf/n1 timing recorded for M4: 0.39s/0.76s cold) |
| m3-walk | researcher | Step 5 walk: build + serve the docs site, drive it in a real browser (browser-verify), narrate what is seen — agent has NOT read the ACs | record/m3-walk-docs-site.md | done (real findings: MathJax rendering silently broken on both new manual pages, home page status/roadmap stale; minor: leaked "wave M3 W5" shorthand in a public docstring, pre-existing site-wide code-block clipping, likely-intentional mermaid lazy-render, cosmetic GitHub-API 404; 14 screenshots in record/walk-m3/) |
| m3-s7-docs | senior-implementor | S7 docs: manual pages (opf, n1), API pages (opf, contingency), architecture diagram edges, new example — progress .bionic/tmp/m3-s7-progress.md, cadence 10m, ~60-70 min | record/m3-s7-report.md + commit on wave/03-opf-n1 | done (commit f37815a, pushed; 573 tests repo-wide; found test_api_docs_coverage.py's PACKAGES is hand-maintained not generic, widened it + added submodule ::: blocks; found+fixed 2 mkdocs anchor issues, an architecture.md ownership-table inaccuracy, and a second stale jobs.md sample beyond the one named in scope; plan AC-9 evidence filled in by S7 itself — last slice, wave moves to Step 5) |
| m3-s6-jobs | implementor | S6 jobs: opf.dc/n1 KindSpecs, SolveResult union widened, INFEASIBLE_LP/UNBOUNDED_LP FailureCodes — progress .bionic/tmp/m3-s6-progress.md, cadence 10m, ~40-50 min | record/m3-s6-report.md + commit on wave/03-opf-n1 | done (commit 5fc26aa, pushed; 572 tests repo-wide; found+fixed a real regression the full suite caught — examples/04_jobs_api.py's own "unknown kind" demo used kind="opf.dc", now registered — switched both it and one test to kind="market.nodal"; plan AC-8 evidence filled in by S6 itself) |
| m3-s3-pwl | implementor | S3 pwl: convex segment/epigraph PWL cost encoding in opf.dc_opf's cost extraction + NonConvexCostError guard, parity vs case14_pwl.m — progress .bionic/tmp/m3-s3-progress.md, cadence 10m, ~50-60 min | record/m3-s3-report.md + commit on wave/03-opf-n1 | done (commit 8d2c4e6, pushed; 26/26 own tests, ruff/mypy clean — non-response procedure: agent finished the work including clean coordination with S5, but went idle before committing/reporting; orchestrator verified and landed it as-is; found pandapower can't oracle mixed quadratic+PWL networks, fell back to independent lambda-iteration solver; honestly asserted a genuine LP degeneracy as an interval rather than a false-precise split) |

## Assumptions

- A1 (spec assumption a): the rating-derivation margin is pinned during implementation (S1),
  not fixed here — must be tight enough that AC-4/AC-6's violation half is actually exercised
  on real data, not just the unconstrained path.
- A2 (spec assumption b): pandapower `rundcopp`'s PWL-cost support is unconfirmed as of Step 3
  — S3/S1 checks it early; AC-5's oracle choice is conditional, resolved then, not assumed now.
- A3 (spec assumption c, carry-over): generator-outage N-1 and `model.PiecewiseCost`'s missing
  convexity validation are named carry-overs for a later wave — log explicitly at Step 4/5
  fold time the way M2's R1 fold logged A13/A14, not silently dropped.
- A4 (process note, from continuation-m2.md): worktree junction removal on this machine needs
  git-bash `rm`, not PowerShell/cmd `rmdir` (sandbox blocks the latter two on this path).
- A5 (process note): two Windows-path bugs in this session's global `~/.claude/hooks/*.sh`
  were found and fixed (`dispatch-preflight.sh`, `canonical-sdlc-governing-skill.sh`); a third
  (`stop-guard.sh`, TaskStop-only, non-blocking) is known and left open. See memory
  `dispatch-preflight-windows-path-bug.md`. Not expected to recur mid-wave now that the fixes
  are in place, but named here in case a fresh symptom appears.
- A6 (R1 fold follow-up, orchestrator-investigated, NOT fixed — carry-over, not a defect): the
  R1 fold's item F dropped `contingency/__init__.py`'s "wave M3 W5" docstring shorthand per a
  walk finding, and flagged 3 more M3-local instances as out-of-scope follow-up
  (`contingency/n1.py`, `results/n1.py`, `results/feasibility.py`). Investigating those 3 before
  fixing them found the pattern (`W<n>` / `wave M<n> design item <n>` citations in public
  module/class docstrings, rendered on the live API reference site) in **22 files spanning
  M1, M2, and M3** — `io/matpower.py`, `model/entities.py`, `model/errors.py`,
  `model/islands.py`, `numerics/{__init__,arrays,roles}.py`, `pf/{__init__,ac_newton,dc}.py`,
  `results/{__init__,feasibility,from_arrays,n1,opf,power_flow,tables}.py`,
  `jobs/{__init__,models,registry}.py`, `opf/{__init__,dc_opf}.py`. This is a pervasive,
  consistent, clearly deliberate house convention, not an isolated leak — M2's own critic and
  audit never flagged it despite reading plenty of this code. Attempted one more fix
  (`contingency/n1.py`, matching the fixed `__init__.py`'s wording) and reverted it on
  discovering the scale: fixing 3 more files would make the codebase *less* consistent, not
  more, for a stylistic judgment call the walk made in isolation without this context. Left
  `__init__.py`'s already-committed, already-pushed fix as-is (low-risk, arguably the single
  file most likely to be read as a "front door" docstring) rather than revert landed work to
  chase consistency the other direction. If a future wave wants this changed project-wide,
  it is a real, scoped documentation-consistency task (rewrite all 22 files' citations to a
  reader-friendly form, e.g. spelling out "see ADR-004" style rather than "W6") — not
  something to fold piecemeal into whichever wave's walk happens to notice one instance of it.

## Handoff

**Wave closed 2026-08-24.** Merged into `epic/01-foundation` at `5fa3285` (local only —
pushing is the user's call, see `record/continuation-m3.md`). Worktree removed, `.bionic/tmp`
wiped, `current: 9`. Nothing left to resume in this plan; the next wave-scale run is M4
nodal-market, opening its own plan per `record/continuation-m3.md` — read ADR-006 first, it's
the reuse seam M4 is built around.

<details>
<summary>Prior resume point (2026-08-23, superseded — kept for history)</summary>

Resume point (2026-08-23): Step 3 plan written, awaiting user approval.
Decisions ratified this session: triple, scope (3 answers), design interview (frame + 3
decisions + composition), spec + plan written.
Open blockers: none.
Resume instruction: on approval, `git worktree add C:\Claude Projects\mambo-power-m3 -b
wave/03-opf-n1 epic/01-foundation`, junction `.bionic` (mklink /J or equivalent — verify with
`ls -la` from git-bash that it shows as a symlink, matching M2's setup), dispatch S1 and S2 in
parallel.

*(All of the above happened as described, plus a full Step-5/6 audit-fold-critic-fold cycle:
fold commit 8fc8581, re-audit CONFIRMED record/m3-r2-reaudit.md, review+critic fold commit
4bd67d9, merge 5fa3285. See the closure note above the `<details>` and
record/continuation-m3.md for the full account.)*

</details>
