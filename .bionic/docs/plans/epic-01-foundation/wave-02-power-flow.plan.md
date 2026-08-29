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
  orchestrator: fable-5
  implementor: sonnet
  senior-implementor: opus
  researcher: sonnet
  test-runner: sonnet
  auditor: opus
  critic: opus
---

# Wave M2 plan — power-flow

Spec: .bionic/docs/specs/epic-01-foundation/wave-02-power-flow.spec.md (design pointer →
epic spec §Design, plus M2-local design). Branch: wave/02-power-flow off epic/01-foundation
(6c94459). Worktree: C:\Claude Projects\mambo-power-m2 with `.bionic` junctioned to the main
checkout (remove the junction with `cmd /c rmdir` before `git worktree remove`).

## SDLC State

integration-branch: epic/01-foundation
intent: build
rigor: audited
scale: wave
current: 9

- Step 0: prereqs: ok; configured 2026-08-21 via "confirm"; model_plan=fable-5/sonnet/opus tiers; integration-branch=epic/01-foundation; walk=required (docs site is drivable)
- Step 1: scope closed 2026-08-21 ("ok") in wave-02-power-flow.spec.md sections Requirements + Not Doing + Prior art; research record/m2-research.md
- Step 2: design interview 2026-08-21 — frame ratified ("ok"), D1 islands "Importer repairs, model stays strict", D2 Q-limits "pandapower semantics", composed design "ratified"; spec Design section written after ratification
- Step 3: wave-02-power-flow.plan.md approved by user 2026-08-21 ("approved"); design + plan + matrix locked; GitHub Pages enabled by the user (source: GitHub Actions) and gridlab-w1 leftover deleted
- Step 4: slices S1-S7 landed RED→GREEN as commits 011698c, 41e531b, 5d41103, cf3f9fb, e4ed0f6, 0ba1c8d, e1e7e4f — reports record/m2-s{1..7}-report.md; every commit 6/6 or 7/7 green on CI; assumptions A1-A11 logged; worktree: C:\Claude Projects\mambo-power-m2; base-sha: 6c94459; branch: wave/02-power-flow
- Step 5: walk-artifact: record/m2-walk-docs-site.md (docs-site walk in a real browser by an agent that has not read the ACs); cmd: `uv run pytest -q -p no:cacheprovider` on wave head 502dc1b (plus ruff check, ruff format --check, mypy, `mkdocs build --strict`, 7 examples, timing -s, uv build + wheel/sdist smoke); pass: 484; total: 484; output: record/m2-step5-tests-floor.md (unit 329/329, parity 150/150, property 5/5, full 484/484; docs strict 0 real warnings; examples 7/7 exit 0; build 2 artifacts; wheel + sdist smoke ok; case300 cold 0.152 s locally, 0.040 s on CI ubuntu); CI run 32448061526 on 502dc1b 8/8 success; auditor: m2-auditor (record/m2-audit.md) first-pass verdict REFUTED (2 rows + 1 coverage hole), closed by the R1 fold (commit b771197, record/m2-r1-fold-report.md) and re-audited CONFIRMED by m2-r2-reaudit (record/m2-r2-reaudit.md, 2026-08-23) — 492/492 tests, all 11 AC rows CONFIRMED, auditor-wave: CONFIRMED
- Step 6: stance 1 six-axis self-review record/m2-review-6axis.md (Correctness/Readability/Architecture/Performance/Duplication PASS with flags, Security FLAG — the FLAG's two should-fix items folded into R1 as F/G above); stance 2 independent critic record/m2-critic.md (2 should-fix-this-wave issues, both folded into R1 as D/E above); both re-verified closed by m2-r2-reaudit
- Step 7: adr: n/a — no new momentous or cross-wave decision this wave; D1 (island repair-and-warn) and D2 (pandapower Q-limit semantics) were ratified at Step 2 and already live in this spec's Design section; the R1 fold's choices (shared `absorb_slack_p` helper, `UNSOLVABLE_NETWORK` FailureCode, `AcPowerFlowResult.message`, iteration bounds + divergence guard) are implementation-detail fixes within the surface ADR-004 (stateless job contract) and ADR-005 (pu convention, M1) already govern, captured in record/m2-r1-fold-report.md; nothing here shapes M3+ the way ADR-005 shaped M2
- Step 8: merge: dcdc1c9 (wave/02-power-flow b771197 → epic/01-foundation, --no-ff, local; merge tree verified byte-identical to CI-proven wave head via `git diff b771197 HEAD --stat` = empty, so the 492/492 + CI 32663188881 8/8 evidence carries over without re-running the suite; pushing the epic branch is the user's call, same as M1's A20); worktree-removed: C:\Claude Projects\mambo-power-m2 (junction to .bionic removed via `rm` first — `cmd`/PowerShell `rmdir` were blocked by this session's sandbox guard, git-bash `rm` on the reparse point worked cleanly); cleanup: done; tmp-wiped: .bionic/tmp emptied 2026-08-23 (including this session's own preflight/roster state files, per the skill's literal `wipe .bionic/tmp/*` — harmless, hooks self-heal a missing attestation); tasks-completed: all dispatch-ledger rows done, stale, or superseded (m2-walk and m2-auditor rows were corrected from a stale "active" — they'd finished but were never marked — before this check), none active
- Step 9: deploy: none this wave — PyPI publish is M9 (deploy_target: pypi applies at M9, same as M1); verified-at: CI run 32663188881 on b771197 (8/8, the exact tree merged, confirmed byte-identical) + re-audit record/m2-r2-reaudit.md; monitor: GitHub Actions on every push to epic/01-foundation and wave/* (ci.yml) — epic branch not yet pushed this wave, so CI has not yet run ON the merge commit itself; continuation: record/continuation-m2.md

## Slices

| Slice | Delivers | ACs | complexity | role |
|---|---|---|---|---|
| S1 fixtures | case300.m verbatim from MATPOWER GitHub (sha256 69a90280e999ef533d94656e0fbc08311f1347c962dd2753ff2005ff5e3f9ac5, 66034 bytes) + PROVENANCE/SOURCES entries with the licence caveat; `case14_roles.m` (one unit off on a PV bus; one bus with two in-service gens at differing VG) and `case14_island.m` (one bridge branch out) derived from case14 with documented edits; importer round-trip + pandapower parity on the new files | AC-7 (fixture), AC-4/5 (fixtures) | standard | implementor |
| S2 roles-islands | `numerics.effective_roles` + `NoSlackGeneratorError`; `model.repair_islands` + `ISLAND_DEACTIVATED` warnings wired into `io.matpower.load_with_warnings`; tests vs pandapower on the S1 fixtures | AC-4, AC-5 | complex | senior-implementor |
| S3 dc-results | `pf.dc`, `results/` models + `from_arrays` + `.to_arrays()` + `ResultProvenance`; DC parity vs rundcpp on all fixtures | AC-3, AC-6 (results part) | standard | implementor |
| S4 ac-newton | `pf.ac_newton` (polar NR, sparse Jacobian, splu, flat/warm, Q-limit pandapower semantics), `pf.solve_ac`; parity vs runpp + stored columns with exclusions; Q-limit pin-set agreement; case118 bus-103 negative pair; case300 timing measurement | AC-1, AC-2, AC-7 | complex | senior-implementor |
| S5 jobs | `jobs/` request/result/KINDS/run for pf.ac + pf.dc; purity, JSON round-trip, structured failure, registry contract test | AC-6 | standard | implementor |
| S6 docs-site | `docs/`, `mkdocs.yml`, docs dep group, mkdocstrings, IA pages, manual pages for model/formats/numerics/power-flow/jobs (M1 backfill + M2), mermaid architecture + data-model diagrams, Design page with ADR summaries, Changelog; docstring-coverage test; CI `docs` job; `pages.yml` | AC-8, AC-10 | complex | senior-implementor |
| S7 examples | `examples/` (01 load+validate, 02 ac power flow, 03 dc power flow, 04 jobs api, 05 islands+roles warnings, 06 matrices) + CI `examples` job + snippet embedding in manual pages | AC-9 | standard | implementor |

Order: S1 → S2 → S3 → S4 → S5; S6 can start after S3 (documents results) and finishes after
S5; S7 after S5. S1/S3 may run in parallel (disjoint files). Every slice RED → GREEN.

## Verification Matrix

stack-health: before (M1 close, record/m1-step5-tests-floor.md): 269 tests, Python 3.12.14, numpy 2.5.2, scipy 1.18.0, pydantic 2.13.4, highspy 1.15.1, pandapower 3.3.0, pypsa 1.2.4; after (Step 5, record/m2-step5-tests-floor.md §stack): same runtime stack, plus docs group mkdocs-material 9.7.7 / mkdocstrings 1.0.6 / mkdocstrings-python 2.0.7 / pymdown-extensions 11.0.1; 484 tests, full run 209 s on a contended box (tier sum 90 s), 10 third-party pandapower warnings, none from src

| AC | tier | status | evidence | auditor |
|---|---|---|---|---|
| AC-1 | T2 | discharged | see AC-1 | CONFIRMED |
| AC-2 | T2 | discharged | see AC-2 | CONFIRMED (revert-and-watch VALIDATED: Q-limit stub → exactly the 28 predicted checks red, 99 predicted-green green) |
| AC-3 | T2 | discharged | see AC-3 | CONFIRMED |
| AC-4 | T1 | discharged | see AC-4 | CONFIRMED (wording: role-level match — spec amended) |
| AC-5 | T1 | discharged | see AC-5 | CONFIRMED (record/m2-r2-reaudit.md §1 — re-executed, re-measured 8.88e-16 pu / 4.44e-14 deg, matches original probe) |
| AC-6 | T1 | discharged | see AC-6 | CONFIRMED |
| AC-7 | T1 | discharged | see AC-7 | CONFIRMED (docs to carry the CI figure — fold) |
| AC-8 | T2 | discharged | see AC-8 | CONFIRMED (record/m2-r2-reaudit.md §2 — planted-miss-verified regression guard reproduces the exact original 5-name gap; site render confirmed) |
| AC-9 | T1 | discharged | see AC-9 | CONFIRMED (wording: gallery, not manual page — spec amended) |
| AC-10 | T1 | discharged | see AC-10 | CONFIRMED |
| AC-11 | T1 | discharged | see AC-11 | CONFIRMED (record/m2-r2-reaudit.md §3 — new test asserts the licence-exclusion sentence text and no-BSD-claim property, distinct from the pre-existing sha256 test) |

auditor-wave: CONFIRMED (record/m2-r2-reaudit.md, 2026-08-23) — re-audit of the R1 fold (commit b771197) against the original REFUTED verdict (record/m2-audit.md §4, 2026-08-21). All three proof gaps closed with real, re-executed, independently-verified evidence: AC-5's island test is a genuine independent comparison (repair path vs. pandapower's own connectivity check, re-measured to match the original probe exactly); AC-8's coverage test was planted-miss-verified to reproduce the original 5-name gap when reverted, and the built site now renders all four names; AC-11's new test asserts the licence-wording property the coverage hole actually required. Critic issues 1-2 (diagram edges, fabricated provenance text) both spot-checked closed. No collateral damage: full suite 492/492, ruff/mypy/mkdocs clean, AC-1/AC-2/AC-3 parity tiers unchanged at original tolerances despite sharing solver-loop code with the self-review's divergence-guard/iteration-bound fixes.

AC-11:
  criterion: fixtures/matpower/case300.m sha256 equals the recorded digest 69a90280e999ef533d94656e0fbc08311f1347c962dd2753ff2005ff5e3f9ac5 and PROVENANCE.md's case300 entry carries the MATPOWER LICENSE exclusion sentence and makes no BSD claim (T1)
  provenance: wave spec W7; record/m2-research.md §4 (licence caveat); audit coverage finding
  tier-run: tests/unit/test_fixture_case300.py::test_bytes_are_the_recorded_upstream_blob asserts the committed bytes' sha256 (S1, commit 011698c); R1 fold adds test_provenance_case300_entry_carries_the_licence_exclusion_and_no_bsd_claim — reads the case300 ### entry in PROVENANCE.md, asserts "not covered by MATPOWER's BSD licence" is present and no affirmative BSD-claim phrase ("is BSD"/"under the BSD"/"BSD-licensed"/"BSD licensed") appears; passed on first run (the wording already held, R1 fold report §C — a proof gap, not a defect). R1 also stripped 8 sentences referencing a nonexistent packages/engine-pf monorepo, Node/TypeScript suite, "browser harness in S8" and "W1-R5" numbering, inherited verbatim from the abandoned gridlab-w1 project (commit ca10b6a) — critic issue 2 — from PROVENANCE.md and SOURCES.md, without touching the sha256/licence content this AC checks.
  readback: uv run --no-sync pytest tests/unit/test_fixture_case300.py -> 4 passed (R1 fold commit — record/m2-r1-fold-report.md)

AC-1:
  criterion: AC-NR parity vs pandapower runpp (1e-6 pu / 1e-4 deg) on 14/ieee30/57/118 (qlim on) + 300 (qlim off AND on); MATPOWER stored columns within 2e-3 pu / 0.5 deg with listed exclusions and pinned residuals (amended from file precision, A10); case30 self-consistency (T2)
  provenance: wave spec W1; record/m2-research.md §1-2
  fixture-fidelity: verbatim MATPOWER bytes (PROVENANCE.md; case300 sha256 69a90280…9ac5 verified pre-copy, post-copy and from the committed blob — record/m2-s1-report.md)
  tier-run: tests/parity/test_ac_vs_pandapower.py (37 cases) — oracle built from the independent numpy reader → from_ppc with BASE_KV substitution, trafo_model="pi", slack-angle alignment and the MATPOWER tap-side swap for hv=T_BUS transformers (A5, A11); max |Δvm| ≤ 4e-14 pu, |Δva| ≤ 4e-12 deg, flows/injections ≤ 1e-10 MVA on every fixture (one 4e-8 from pandapower's res_bus rounding); iterations/rounds: case14 4/0, case_ieee30 6/1, case57 4/0, case118 7/1, case300 qlim-off 5/0, case300 qlim-on matches pandapower's 2 iterations / 10 pins; tests/parity/test_ac_vs_matpower_stored.py (10 cases) — stored columns within 2e-3 pu / 0.5 deg after exclusions, residuals pinned (case14 1.33e-3 at bus 4, case_ieee30 6.1e-4, case57 8.7e-4, case118 9.9e-4); case30 + case300 self-consistency (warm start → 0 iterations, identical state); RED: ImportError AcOptions before src existed; commit e4ed0f6 (record/m2-s4-report.md)
  readback: CI run 32445786960 on e4ed0f6 — 7/7 jobs success (parity tier on ubuntu 3.11/3.12/3.13, macOS, Windows); wave head 502dc1b run 32448061526 — 8/8 success
AC-2:
  criterion: Q-limit pin set equals pandapower's; hand case pins both sides, no restore; case118 bus 103 negative pair with qlim off (T2)
  provenance: wave spec W1; record/m2-research.md §3
  fixture-fidelity: verbatim MATPOWER bytes + a hand-built case declared synthetic
  tier-run: pinned sets identical to pandapower's internal post-loop bus types on every fixture where limits bind (case_ieee30 bus 2 max; case118 {19,32,34,92,105 min; 103 max}; case300 qlim-on 10 pins); tests/unit/test_pf_ac_newton.py hand cases force a Qmax pin and a Qmin pin, assert q_limited sign, role flip, Vm off setpoint, and no restore across rounds; q_limits=False leaves PV; negative pair: case118 qlim-off breaches 2e-3 pu at bus 103 (9.0e-3) and is within with qlim on (2.9e-4); commit e4ed0f6 (record/m2-s4-report.md)
  readback: CI run 32445786960 on e4ed0f6 success 7/7
AC-3:
  criterion: DC angles/flows equal rundcpp within 1e-9 on all fixtures incl. case300 (T2)
  provenance: wave spec W2
  fixture-fidelity: verbatim MATPOWER bytes
  tier-run: tests/parity/test_dc_vs_pandapower.py (25 cases — corrected from "21" per audit §5; S3's "47 new" was a miscount) on case14, case30, case_ieee30, case57, case118, case300 — max diffs ≤ 3.3e-12 deg angles, ≤ 3.5e-12 MW flows, ≤ 5.2e-12 MW bus injections, slack gen equals ext_grid p everywhere; oracle with trafo_model="pi" and BASE_KV substitution (A5); hand 3-bus with a phase shifter vs dense solve at 1e-12 (tests/unit/test_pf_dc.py, 12 cases); RED: ImportError before src; commit 41e531b (record/m2-s3-report.md)
  readback: CI run 32443812218 on 41e531b success 6/6; re-run green in every later wave-branch run
AC-4:
  criterion: effective roles on case14_roles — PV-without-gen → PQ matches pandapower; multi-gen uses last VG + warning; slack without gen → NoSlackGeneratorError (T1)
  provenance: wave spec W3; M1 plan A18
  tier-run: tests/unit/test_effective_roles.py (10 cases) — bus 6 (gen out) effective PQ vs declared PV; bus 2 takes the LAST gen's 1.055 and SetpointConflictWarning names bus-2 with 1.045/1.055; case14_noslackgen → NoSlackGeneratorError("bus-1"); plain case14 effective == declared, no warnings; tests/parity/test_roles_vs_pandapower.py (3 cases) — pandapower BUS_TYPE==1 for bus 6 and vm not at VG; pandapower's converter keeps FIRST (1.045) vs our LAST (1.055), both asserted explicitly; derived fixture re-derived from case14 raw matrices by the independent reader (record/m2-s1-report.md); RED: collection ImportError ×3; commit 5d41103 (record/m2-s2-report.md)
  readback: CI run 32444376997 on 5d41103 success 6/6
AC-5:
  criterion: case14_island — load_with_warnings repairs with ISLAND_DEACTIVATED, solve matches pandapower on the main island; load succeeds; direct Network still raises DISCONNECTED_BUS (T1)
  provenance: wave spec W4; user 2026-08-21 D1
  tier-run: tests/unit/test_islands.py (12 cases) — load_with_warnings/load_with_report on case14_island return a valid Network with bus-8 and gen-5 deactivated (bus 8 carries no load/shunt, A8) and exactly one ISLAND_DEACTIVATED issue listing them; load succeeds silently; direct Network from the raw entities raises DISCONNECTED_BUS; repair on connected case14 is a no-op; hand multi-island/load/branch cases; two-slack case still MULTIPLE_SLACK; S1's island test flipped from DISCONNECTED_BUS to repaired behaviour (RED recorded); commit 5d41103 (record/m2-s2-report.md); the "solve matches pandapower on the main island" clause had NO test at Step 5 (the earlier "covered by S4 parity path" claim was false — case14_island is not in the parity CASES; audit §5 item 1) — R1 fold closes this: tests/parity/test_ac_vs_pandapower_island.py::test_repaired_island_solve_matches_runpp_on_the_main_island loads case14_island through load_with_warnings, solves AC, and independently builds a pandapower net from the same raw matrices (BASE_KV substitution, trafo_model="pi", enforce_q_lims=True — the test_ac_vs_pandapower.py oracle convention) and runs runpp, whose own connectivity check drops bus 8 (NaN result row, in_service stays True) independently of our repair; asserts the 13 main-island buses agree at TOL_VM=1e-14 pu / TOL_VA_DEG=1e-13 deg — measured 8.9e-16 pu / 4.4e-14 deg, matching the auditor's probe (m2-audit.md §3) exactly; passed on first run (a proof gap, not a defect — the auditor had already shown the property true by hand)
  readback: CI run 32444376997 on 5d41103 success 6/6; uv run --no-sync pytest tests/parity/test_ac_vs_pandapower_island.py -> 1 passed (R1 fold — record/m2-r1-fold-report.md)
AC-6:
  criterion: results JSON round-trip + provenance populated; jobs.run pure, structured failure, KINDS contract (T1)
  provenance: wave spec W5, W6; ADR-004
  tier-run: tests/unit/test_results_models.py (14 cases: construction, JSON round-trip, to_arrays ordering, inf/nan rejected, provenance version == mambo_power.__version__) commit 41e531b; tests/unit/test_jobs.py (24 cases: KINDS == {pf.ac, pf.dc} with importable models and callable runners; run twice equal modulo started_at/elapsed_s; run_json round-trip; UNKNOWN_KIND / BAD_OPTIONS / VALIDATION (dangling ref through run_json) / NO_SLACK_GENERATOR failures with no exception; SetpointConflict warning string attached; max_iter=1 → status ok, converged False) commit 0ba1c8d (record/m2-s5-report.md); RED recorded in both
  readback: CI run 32446619776 on 0ba1c8d success 7/7 (jobs); CI run 32443812218 on 41e531b success 6/6 (results)
AC-7:
  criterion: case300 AC-NR cold < 1.0 s on CI ubuntu 3.12, recorded; else number + warm figure recorded and surfaced (T1)
  provenance: wave spec W7; epic Design §7 assumption 1
  tier-run: tests/parity/test_ac_timing.py — first solve_ac in a fresh subprocess, qlim off, flat start, asserts < 1.0 s; local (Windows 11, 3.12): cold 0.0312 s, warm 0.0194 s, 5 iterations (record/m2-s4-report.md); CI ubuntu 3.12 job of run 32447930888 on e1e7e4f prints "case300 AC cold 0.0419 s, warm 0.0222 s, 5 iterations" — 24× under the 1.0 s threshold on the contracted surface; epic Design §7 assumption 1 confirmed
  readback: https://github.com/mambo10005/mambo-power/actions/runs/32447930888
AC-8:
  criterion: mkdocs build --strict green locally + CI; IA pages present; mermaid diagrams render; API reference covers all public symbols; pages.yml exists (T2)
  provenance: wave spec W8; epic R14
  fixture-fidelity: the built site from the wave head 502dc1b (e1e7e4f + docs/index.md) is the artifact; the Step-5 walk (record/m2-walk-docs-site.md) drives it in a real browser via browser-verify
  tier-run: docs/ with mkdocs.yml (material, mkdocstrings-python sphinx style + autoref hook, pymdownx superfences/mermaid/snippets/arithmatex): Home, Getting started, Manual ×6 (model, formats, numerics, power-flow incl. finished AC section + NR/Q-limit mermaid loop, results, jobs), Examples gallery, API ×7 (model, io.matpower, io.native, numerics, pf, results, jobs), Design ×3 (architecture diagram, data-model classDiagram, decisions = ADR-001..005 + D1/D2), Changelog, Contributing — 21 pages; `uv run mkdocs build --strict` exit 0 with 0 warnings locally (S6, S5, S7 reports) and in CI job "docs (mkdocs --strict)" on cf3f9fb, e4ed0f6, 0ba1c8d; 35/35 docs code blocks executed with matching output (S7); `.github/workflows/pages.yml` deploys on push to epic/01-foundation + main (Pages enabled by the user, source GitHub Actions); commits cf3f9fb, 0ba1c8d, e1e7e4f — R1 fold closes the "covers all public symbols" gap the auditor found (pf.ac_newton had no ::: block; newton/newton_raphson/flat_start/specified_injection/allocate_generation had 0 site anchors, m2-audit.md §3): added "## AC solver over arrays" + `::: mambo_power.pf.ac_newton` to docs/api/pf.md, and a durable tests/unit/test_api_docs_coverage.py — walks every docs/api/*.md page's ::: directives and every src/mambo_power subpackage's submodules (pkgutil), flags a submodule whose defined public classes/functions are reachable from no documented module (directly or by re-export, e.g. model.islands'/numerics.roles'/io.report's symbols already render via their package's own __all__ re-export — verified empirically before writing the test, so it doesn't demand new blocks for those); RED before the fix named exactly pf.ac_newton's 5 missing symbols, GREEN after. R1 also fixed critic issue 1: docs/design/architecture.md's mermaid diagram drew a nonexistent ac-->results edge and omitted the real pf-->model and jobs-->numerics edges (grep-verified against the actual import lines both before and after).
  readback: CI run 32448061526 on wave head 502dc1b — 8/8 success incl. docs job (and 32447930888 on e1e7e4f); walk artifact record/m2-walk-docs-site.md; uv run --no-sync mkdocs build --strict -> exit 0 (R1 fold), grep of the built site for newton_raphson/allocate_generation/flat_start/specified_injection -> 1 occurrence each (was 0)
AC-9:
  criterion: every examples/*.py exits 0 in CI; each embedded in a manual page by snippet (T1)
  provenance: wave spec W9; epic R14
  tier-run: examples/01_load_and_validate … 07_results_and_export (7 scripts, 0.26–1.32 s each); tests/unit/test_examples_run.py (9 cases) runs each in a subprocess and asserts exit 0; CI job `examples` runs them via `uv run python`; gallery docs/examples/index.md embeds each via `--8<--` snippets in `{ .python }` fences (ruff rewrites the marker inside ```python — A12); commit e1e7e4f (record/m2-s7-report.md)
  readback: CI run 32447930888 on e1e7e4f — job "examples (run every script)" success
AC-10:
  criterion: docstring-coverage test over public symbols passes on the wave head (T1)
  provenance: wave spec W10; epic R14
  tier-run: tests/unit/test_docstrings.py walks mambo_power packages with pkgutil and fails on any public module/class/function/property without a docstring; 0 offenders on cf3f9fb and on every later head (S6 planted-miss proof: removing docstrings in memory from a module, function, class and property each fails the test); commit cf3f9fb (record/m2-s6-report.md)
  readback: CI run 32444984780 on cf3f9fb success 7/7; green on every later run

## Dispatch ledger

| id | role | unit | deliverable | status |
|---|---|---|---|---|
| m2-research | researcher | Step 1/2: stored-solution precision, pandapower/MATPOWER conventions, case300 provenance + licence, docs tooling | record/m2-research.md | done (verified on disk 2026-08-21, 291 lines) |
| m2-s1-fixtures | implementor | S1 fixtures: case300 verbatim + provenance/licence caveat; derived case14 roles/island/no-slack-gen — progress .bionic/tmp/m2-s1-progress.md, cadence 5m, ~35 min | record/m2-s1-report.md + commit on wave/02-power-flow | done (commit 011698c; 308 tests; case300 sha verified pre/post/committed; derived fixtures re-derived by independent reader; pushed) |
| m2-s2-roles-islands | senior-implementor | S2 roles-islands: numerics.effective_roles + NoSlackGeneratorError + SetpointConflictWarning; model.repair_islands + ISLAND_DEACTIVATED wired into importer; tests vs pandapower — progress .bionic/tmp/m2-s2-progress.md, cadence 5m, ~45 min | record/m2-s2-report.md + commit on wave/02-power-flow | done (commit 5d41103; 380 tests; legacy `load_with_warnings` kept as list[str] + new typed `load_with_report` → ImportReport; NoSlackGeneratorError, SetpointConflictWarning(UserWarning); pushed) |
| m2-s4-ac-newton | senior-implementor | S4 ac-newton: AcOptions, sparse polar NR, pandapower Q-limits, effective roles, solve_ac, parity vs runpp + stored columns, case300 timing — progress .bionic/tmp/m2-s4-progress.md, cadence 5m, ~75 min | record/m2-s4-report.md + commit on wave/02-power-flow | done (commit e4ed0f6; ~445 tests; AC parity vs runpp on all 6 fixtures incl. case300 qlim-on after correcting a pandapower from_ppc tap-side defect in the oracle copy; pinned sets identical; case300 cold 0.031 s / 5 iterations; pushed) |
| m2-s5-jobs | implementor | S5 jobs: SolveRequest/SolveResult/StructuredError, KINDS registry, run/run_json, warnings capture; jobs manual + API page — progress .bionic/tmp/m2-s5-progress.md, cadence 5m, ~35 min | record/m2-s5-report.md + commit on wave/02-power-flow | done (commit 0ba1c8d; 475 tests; KINDS pf.ac/pf.dc; structured failure codes UNKNOWN_KIND/BAD_OPTIONS/VALIDATION/NO_SLACK_GENERATOR/INTERNAL; jobs manual + API page; pushed) |
| m2-s7-examples | implementor | S7 examples + docs finish: 7 runnable scripts, CI examples job + subprocess test, snippet gallery, AC manual finished, timing echoed, ImportWarning→ImportIssue, case300 PROVENANCE corrected — progress .bionic/tmp/m2-s7-progress.md, cadence 5m, ~50 min | record/m2-s7-report.md + commit on wave/02-power-flow | done (commit e1e7e4f; 484 tests; 7 examples CI-executed + snippet gallery using `{ .python }` fences (ruff rewrites `--8<--` inside ```python); AC manual finished; timing echoed via -s step; ImportIssue rename; PROVENANCE corrected; pushed) |
| m2-walk | researcher | Step 5 walk: build + serve the docs site, drive it in a real browser (browser-verify), narrate what is seen — agent has NOT read the ACs | record/m2-walk-docs-site.md | done (artifact verified on disk — 7 screenshots 01-home through 07-search-island-deactivated; cited throughout m2-audit.md and the AC-8 evidence block; ledger row was never updated at the time, corrected here) |
| m2-floor | test-runner | Step 5 tests floor on e1e7e4f: discovered suites (ruff, format, mypy, pytest tiers + full, mkdocs --strict, examples, build + wheel/sdist smoke), stack-health | record/m2-step5-tests-floor.md | done (all green on 502dc1b: 484/484 tiers reconcile; docs strict; examples 7/7; build + smoke; deviation "HEAD moved under the run" recorded) |
| m2-auditor | auditor | Step 5 exit gate: coverage / power / authenticity over spec + design + matrix + record; ≤3 re-executions; revert-and-watch via request file .bionic/tmp/m2-audit-revert-request.md → test-runner | record/m2-audit.md | done (first-pass wave verdict REFUTED — 2 rows + 1 coverage hole, revert-and-watch VALIDATED; superseded by m2-r2-reaudit's CONFIRMED after the R1 fold; ledger row was never updated at the time, corrected here) |
| m2-revert-watch | test-runner | Auditor's revert-and-watch: stub Q-limit violator detection in pf/ac_newton.py in throwaway worktree mambo-power-audit2 @502dc1b; 4 commands before/after; predicted reds = pin tests + qlim-on parity rows + case118 bus-103 pair | record/m2-revert-watch.md | done (BEFORE 127 passed; AFTER 28 failed / 99 passed — 5 pin tests, 19 qlim-on parity rows, 4 stored-column checks red; qlim-off/DC/jobs/examples green; worktree removed, verified) |
| m2-review-6axis | code-reviewer | Step 6 stance 1: six-axis review of 6c94459..502dc1b (correctness, readability, architecture + closure, security, performance, duplication vs ownership tables) | record/m2-review-6axis.md | done (artifact verified 28 KB; Correctness/Readability/Architecture/Performance/Duplication PASS with flags, Security FLAG) |
| m2-critic | critic | Step 6 stance 2: adversarial critic over spec + plan + diff + review + audit; ~50 min | record/m2-critic.md | stale — dispatched 2026-08-21, session ended before it produced record/m2-critic.md or any progress note (only two throwaway probe scripts survive in .bionic/tmp/critic-m2/); no report exists on disk, so treated as never delivered and re-dispatched below rather than resumed (writing agents are never resumed per the non-response procedure) |
| m2-critic-r2 | critic | Step 6 stance 2 re-dispatch: same mandate, worktree C:\Claude Projects\mambo-power-m2 @502dc1b, read-only; progress .bionic/tmp/critic-m2/progress.md, cadence ~5-10m, ~20-40 min | record/m2-critic.md | done (2 should-fix-this-wave: mermaid diagram misdraws pf.ac_newton's import edges; PROVENANCE.md/SOURCES.md carry 8 fabricated gridlab-w1 sentences predating M2; reconfirmed AC-5/AC-8 still open; 3 falsification attempts failed — Q-limit pins non-circular, gen-on-OOS-bus cleanly excluded, no array aliasing) |
| m2-r1-fold | senior-implementor | Step 5/6 fold: AC-5 island-vs-pandapower test, AC-8 api page + coverage test, AC-11 provenance-wording test, critic's 2 doc-accuracy fixes, self-review's S4.1/S4.2/C1/C2/D1 — progress .bionic/tmp/m2-r1-progress.md, cadence ~10m, ~90 min | record/m2-r1-fold-report.md + commit on wave/02-power-flow | done (commit b771197, pushed, CI run 32663188881 8/8; all 10 items A-J via TDD; 484->492 tests; AC-5/AC-8/AC-11 rows discharged pending re-audit; deferred items logged as Assumptions A13/A14; one process note — gh credential had to be switched from MJoung_sempra to mambo10005 mid-run to push, see fold report) |
| m2-r2-reaudit | auditor | Step 5 re-audit, scoped: AC-5/AC-8/AC-11 rows only + wave-level re-verdict, against fold commit b771197 — ~30-45 min | record/m2-r2-reaudit.md | done (all three rows CONFIRMED with re-execution + a planted-miss verification on AC-8; critic issues 1-2 spot-checked closed; wave verdict CONFIRMED; no collateral damage on AC-1/2/3 parity) |
| m2-s3-dc-results | implementor | S3 dc-results: results package + provenance, pf.dc + solve_dc, parity vs rundcpp — progress .bionic/tmp/m2-s3-progress.md, cadence 5m, ~45 min | record/m2-s3-report.md + commit on wave/02-power-flow | done (commit 41e531b; 355 tests, 47 new; DC parity vs rundcpp on all 6 upstream fixtures with oracle set to trafo_model=pi; report verified on disk) |
| m2-s6-docs | senior-implementor | S6 docs-site: docs dep group, mkdocs.yml, IA pages (home, getting started, manuals ×6, examples index, API ×6, design ×3, changelog, contributing), docstring test, docs + pages workflows, README — progress .bionic/tmp/m2-s6-progress.md, cadence 5m, ~70 min | record/m2-s6-report.md + commit on wave/02-power-flow | done (commit cf3f9fb; 20 pages, mkdocs build --strict 0 warnings, docstring test green with planted-miss proof, docs + pages workflows, README; S4's in-flight files excluded from its gate; pushed) |

## Assumptions

Seeded from spec Not Doing and spec Design assumptions (a)-(d). Additions:

- A1: The Step-5 walk opens the locally built docs site (`mkdocs serve` or the `site/`
  build) in a browser via the browser-verify skill and narrates navigation, API pages,
  diagrams and examples — without reading the ACs.
- A2: GitHub Pages enabled by the user 2026-08-21 (source: GitHub Actions). `pages.yml`
  builds on every push and deploys only on pushes to epic/01-foundation and main.
- A3: W1's PQ→PV restore and MATPOWER's slack re-slack are recorded as rejected in the spec;
  `AcOptions` does not expose them.
- A5 (S3): pandapower oracle conventions for AC/DC parity — (i) from_ppc nets built from
  case14/case57 have BASE_KV = 0 on every bus and crash runpp/rundcpp (FloatingPointError
  in _wye_delta); the oracle copy applies the importer's BASE_KV ≤ 0 → 1.0 kV substitution
  (DC proven invariant to it); (ii) run with `trafo_model="pi"` — the default "t" model
  alters the series x of transformers with BR_B ≠ 0 (four in case300) by a T→π
  conversion; (iii) case118 stores slack VA = 30°, so angles are compared after
  subtracting the slack angle; (iv) 16 case300 transformers have hv_bus = T_BUS — flows
  compared via p_lv_mw. All recorded in record/m2-s3-report.md.
- A6 (S3): slack generator takes the whole balance (MATPOWER first-in-service-slack-gen
  rule); parity compares bus-level injections. DC results report vm_pu = 1.0 and the
  declared role until S2's effective roles land (S4 switches both solvers to effective).
- A7 (S2): typed import warnings live in `model.ImportWarning(code, message, bus_ids,
  element_ids)` — a name that shadows Python's built-in `ImportWarning`. Step-6 fold
  renames it `ImportIssue` (and amends the spec's W4 wording); `io.report.ImportReport`
  and `load_with_report` stay. Legacy `load_with_warnings` strings now carry a
  `CODE: message` prefix (codes ISLAND_DEACTIVATED, BASE_KV_REPLACED,
  GENCOST_REACTIVE_IGNORED).
- A8 (S2): case14_island's islanded bus 8 carries no load/shunt, so the warning lists
  `bus-8` and `gen-5`; loads/branches/multi-island coverage comes from a hand case. Two
  slacks in two islands → model still rejects (MULTIPLE_SLACK); per-island slacks are out
  of scope (spec Not Doing, distributed slack).
- A9 (S6): docs conventions — docstring style is reST/sphinx (`docstring_style: sphinx`
  in mkdocs.yml + `docs/hooks/rest_roles.py` turning :class:`X` roles into autorefs);
  ruff formats fenced Python inside Markdown, so every docs page and README must stay
  `ruff format` clean; every code block on a page is executed by the author before commit
  (S6 ran 23/23); AC and jobs pages are written as design contracts until S4/S5 land.
- A10 (S4, orchestrator-decided): AC-1's stored-column band amended to 2e-3 pu / 0.5 deg
  (W1's ratified bands); "file precision" (5e-4 / 5e-3) is not met by the stored MATPOWER
  solutions for pandapower or us (case14 bus 4 is 1.33e-3 pu off for both). Measured
  residuals pinned per fixture: case14 1.33e-3, case_ieee30 6.1e-4, case57 8.7e-4,
  case118 9.9e-4 pu. Primary oracle (runpp) is at machine precision (≤ 4e-14 pu).
- A11 (S4, record correction): pandapower `from_ppc` places every transformer tap on the
  winding it picks as hv by base voltage; for 16 case300 transformers that is MATPOWER's
  T_BUS, so the research's oracle modelled a different network. The research's "stored
  columns 0.107 pu away" (§1.2) and "pandapower cannot converge case300 with Q-limits"
  (§4.3) were artefacts; corrected figures: our case300 vs stored VM worst 8.5e-3 pu
  (11/300 buses > 2e-3), and pandapower converges case300 qlim-on in 2 iterations with the
  same 10 pins we find. case300 qlim-on parity row added. The fold corrects
  fixtures/matpower/PROVENANCE.md's case300 wording and the research file gets an erratum
  note; spec assumption (a) already amended.
- A12 (S7): snippet embeds must use the ``` { .python } fence form — ruff format rewrites
  `--8<-- "x"` inside a ```python fence into `--8 < --"x"` and would break every embed
  silently. Documented in the gallery's conventions; applies to all later waves.
- A4: Worktree discipline from M1 applies (junction removal before worktree removal; push
  wave branches via PowerShell `Set-Location` into the worktree — the protect-main hook
  reads the session cwd's branch). User authorization for wave-branch CI pushes carries
  over from M1 (2026-08-20).
- A13 (R1 fold, deferred — self-review recommended fold order item 7, "Docs/text batch"):
  not implemented this fold, carry to a follow-up wave — A1 spec sentence naming
  `repair_islands_entities` (not `repair_islands`) as the importer's actual hook (review
  Architecture finding 1); A2 the pu-boundary docstring wording in `numerics/arrays.py` /
  epic §2 (results.from_arrays is the inverse site, review Architecture finding 2); R6
  reword "Python ≥ 3.14 makes warnings thread-local" to "opt-in from 3.14"
  (`jobs/run.py:25`, `docs/manual/jobs.md:246`); R7 the AC-7 timing figure needs its
  measurement condition stated ("idle machine") next to the number
  (`docs/manual/power-flow.md:333`); C3 `loading_pct` should note it is documented as
  from-side-only, not `max(from, to)` (review Readability finding 3 / Correctness
  finding 3); C4 a sentence noting the per-generator-vs-per-bus Q-limit edge (review
  Correctness finding 4); S4.3 `pages.yml` should scope `pages: write`/`id-token: write`
  to the `deploy` job only, not workflow-level (review Security finding 3); S4.4 pin the
  MathJax CDN version (`mathjax@3.2.2`) rather than the unpinned major (review Security
  finding 4).
- A14 (R1 fold, deferred — self-review recommended fold order item 8, "Code tidy batch"):
  not implemented this fold, carry to a follow-up wave — R1 compute `s_from_pu`/`s_to_pu`
  and the shunt-free injection inside `ac_newton.newton` so `pf/__init__.py` is pure
  mapping (review Readability finding 1); R2 a frozen dataclass for `RepairedEntities`
  instead of a positional 7-tuple (review Readability finding 2); R4 the dead
  `if "case300" not in FIXTURES` branch in `test_dc_vs_pandapower.py` (review Readability
  finding 4, unreachable since S1 added case300 to `FIXTURES`); R5
  `test_effective_roles.py:106`'s hand-parametrised case list should use `FIXTURES`
  (review Readability finding 5); D2 `NetworkArrays.v_set` (first-wins, unused by any
  `src` module after M2) vs `EffectiveRoles.v_set` (last-wins) — drop or rename the stale
  one (review Duplication finding 2); D3 a `ResultProvenance.stamp(...)` classmethod so
  the three hand-written provenance-construction sites can't diverge (review Duplication
  finding 3); D4 the three parity test files' `SUBSTITUTE_KV = 1.0` should import
  `mambo_power.io.matpower.DEFAULT_BASE_KV` instead of repeating the literal (review
  Duplication finding 4); A3 (review Architecture finding 3) type `StructuredError.code:
  FailureCode` or add a test that every code `run` emits is in
  `typing.get_args(FailureCode)`; C5 the single-in-service-generator Q-assignment
  precision loss with very wide limits (review Correctness finding 5); C6 add
  `and vm_pu > 0` to the `initial_voltage` "auto" guard so a stored `vm_pu = 0.0` falls
  back to flat (review Correctness finding 6).

## Handoff

**Wave closed 2026-08-23.** Merged into `epic/01-foundation` at `dcdc1c9` (local only — pushing
is the user's call, see `record/continuation-m2.md`). Worktree removed, `.bionic/tmp` wiped,
`current: 9`. Nothing left to resume in this plan; the next wave-scale run is M3 opf-n1, opening
its own plan per `record/continuation-m2.md`.

<details>
<summary>Prior resume point (2026-08-23, superseded — kept for history)</summary>

Resume point (2026-08-23): mid-Step-5-close/Step-6. Slices S1-S7 landed (commits 011698c..502dc1b,
484 tests). Step-5 auditor verdict is REFUTED (record/m2-audit.md): AC-5 and AC-8 rows `blocked`
pending a fold (island-vs-pandapower solve test; `pf.ac_newton` API-reference page + a symbol-
coverage test), plus a new AC-11 row (`pending`) added for the W7 coverage hole (sha256/licence
criterion). Step-6 stance-1 self-review is done (record/m2-review-6axis.md, 6 axes, Security
FLAGged, an 8-item recommended fold order). Step-6 stance-2 critic never produced a report in the
prior session (see m2-critic ledger row, marked stale) and was re-dispatched this session
(m2-critic-r2, active).

Decisions ratified this session: none yet — this session is verification/fold work, not a new
Step-0-3 decision; the triple (build/audited/wave) and integration-branch (epic/01-foundation)
stand as locked at Step 3.

Tried-and-rejected / discovered surprises (persist): m2-audit found the "AC-5 covered by the S4
parity path" claim in this plan was false (case14_island is not in parity CASES) — a reporting-
contract violation logged in m2-audit.md §5, not a code defect. AC-3's "21 cases" was also a
miscount (25 collected); corrected in the AC-3 evidence block above.

Open blockers: none (critic running is not a blocker, it is the next gate). Outstanding user
actions carried from Step 3, still open: claim PyPI name before M9.

Resume instruction: once m2-critic-r2 lands record/m2-critic.md, fold together — in one commit,
mirroring m1's R1 pattern (record/m1-r1-fold-report.md) — (a) the auditor's three blocked/pending
rows (AC-5 test, AC-8 docs page + coverage test, AC-11 provenance-wording test), (b) the
self-review's items 1-6 (S4.1 RecursionError, S4.2 iteration bounds, C1 message field, C2 DC
error code, D1 slack-P helper, A4 = same as AC-8's fix) at minimum, folding 7-8 too if cheap, and
(c) whatever the critic finds. Then re-dispatch the auditor scoped to just the changed rows,
fold any R2/R3 as m1 needed, run Step 7 (ADRs for any momentous decisions — likely none new),
then Step 8 (merge wave/02-power-flow into epic/01-foundation, remove the m2 worktree, wipe tmp).

*(All of the above happened as described: fold commit b771197, re-audit CONFIRMED
record/m2-r2-reaudit.md, merge dcdc1c9. See the closure note above the `<details>` and
record/continuation-m2.md for the full account.)*

</details>
