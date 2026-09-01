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
walk: exempt
design-interview: true
cleaned: 2026-08-20
model_plan:
  orchestrator: fable-5
  implementor: sonnet
  senior-implementor: opus
  researcher: sonnet
  test-runner: sonnet
  auditor: opus
  critic: opus
---

# Wave M1 plan — substrate

Spec: .bionic/docs/specs/epic-01-foundation/wave-01-substrate.spec.md (design pointer →
epic spec §Design, plus M1-local design section).
Branch: wave/01-substrate off epic/01-foundation. Worktree: C:\Claude Projects\mambo-power-m1.

## SDLC State

integration-branch: epic/01-foundation
intent: build
rigor: audited
scale: wave
current: 9

- Step 0: prereqs: ok; configured 2026-08-20 via "confirm"; model_plan=fable-5/sonnet/opus tiers; integration-branch=epic/01-foundation; walk=exempt (library, no UI); uv installed by agent m1-env-uv (record/m1-env-attestation.md)
- Step 1: scope closed 2026-08-20 ("ok") in wave-01-substrate.spec.md sections Requirements + Not Doing + Prior art; Scenario deferred to M4 (A1)
- Step 2: design via pointer to epic spec §Design plus M1-local Design section (units, naming, gencost-now, isolated buses, named errors, ids, ownership); W1 facts ported from record/m1-w1-extract.md
- Step 3: wave-01-substrate.plan.md approved by user 2026-08-20 ("continue when the extract lands", read as approval after the checkpoint was presented); design + plan + matrix locked
- Step 4: slices S1-S6 landed RED→GREEN as commits 2922d8e, (S2 on throwaway branch), 8c82e9d, c9b5a90, fc68535, 36bd20a — reports record/m1-s{1,2,3,4,5,6}-*.md; assumptions A1-A12 logged; worktree: C:\Claude Projects\mambo-power-m1; base-sha: ca10b6a; branch: wave/01-substrate
- Step 5: walk: exempt (Step 0 derivation, library surface); cmd: `uv run pytest -q` on wave head 36bd20a (plus `uv run ruff check .`, `uv run ruff format --check .`, `uv run mypy`, `uv build`, wheel + sdist install smoke); pass: 175; total: 175; output: record/m1-step5-tests-floor.md (unit 123/123, parity 47/47, property 5/5, full 175/175 in 14.8 s; build 2 artifacts; wheel smoke `0.0.1.dev0 14`; sdist smoke ok; all exit 0); CI run 32428177629 on 36bd20a 6/6 jobs success; auditor: record/m1-audit.md — all 8 rows CONFIRMED, wave CONFIRMED, revert-and-watch VALIDATED (tap stub → exactly the 6 predicted tests red, 169 green; capture record/m1-revert-watch.md), 3 re-executions match, F1/F2 carried to Step 6
- Step 6: 6-axis review record/m1-review-6axis.md (Correctness FLAG, Readability FLAG-low, Architecture FLAG, Security PASS, Performance PASS, Duplication FLAG; no FAIL); independent critic record/m1-critic.md (READY AFTER FIXES: issue 1 non-finite floats should-fix; 2/3/4 carry to M2/M3; 5/6/7/8 notes); fold commit ddbcdc4 (record/m1-r1-fold-report.md, nothing skipped) closing review A1/C1-4/D3-4/R1-5 + critic 1/5/6; follow-ups fcbf571 (R2) and 3c4f88d (R3) relaxed the new PTDF/LODF oracle's platform-dependent bridge-column assertion (A22); post-fold floor record/m1-step6-tests-floor-post-fold.md all green (269/269, build + smoke); R3 gate 269 passed; CI run 32435477865 on wave head 3c4f88d 6/6 success incl. macOS; carries logged A16-A22
- Step 7: adr: adrs/epic-01-foundation/adr-005-physical-units-model-pu-in-numerics.md (units convention + all-issues validation contract — momentous, shapes every later wave); lesser decisions (A5-A22) live in this plan's Assumptions; spec W4 amended (A15); ideas/pandapower-from-ppc-bug-report.md filed for the user
- Step 8: merge: 6c94459 (wave/01-substrate 3c4f88d → epic/01-foundation, --no-ff, local; pushing the epic branch is the user's call, A20); worktree-removed: C:\Claude Projects\mambo-power-m1 (junction to .bionic removed first via rmdir, record verified intact); cleanup: done; tmp-wiped: .bionic/tmp emptied 2026-08-20; tasks-completed: all dispatch-ledger rows done or superseded, none active
- Step 9: deploy: none this wave — PyPI publish is M9 (deploy_target pypi applies at M9); verified-at: CI run 32435477865 on 3c4f88d (6/6, the exact tree merged) + post-fold local floor record/m1-step6-tests-floor-post-fold.md; monitor: GitHub Actions on every push to epic/01-foundation and wave/* (workflow ci.yml); continuation: record/continuation-m1.md

## Slices

| Slice | Delivers | ACs | complexity | role |
|---|---|---|---|---|
| S1 scaffold | pyproject (hatchling, src layout, deps numpy/scipy/highspy/pydantic; dev pandapower/pypsa/pytest/hypothesis/ruff/mypy), uv.lock, ruff+mypy strict config, pytest tiers via markers + dirs, `.github/workflows/ci.yml` (5 jobs: ubuntu/macos/windows × 3.12, ubuntu × 3.11/3.13), `tests/parity/test_oracles_import.py`; RED = CI absent / import test fails before deps | AC-1, AC-3 | complex (Windows CI + oracle wheels) | senior-implementor |
| S2 planted failure | one commit adding a deliberately failing unit test, observe the CI run red, revert commit, observe green | AC-2 | standard | test-runner |
| S3 model | `mambo_power/model/`: entities, `Network`, `NetworkValidationError` + codes, JSON schema export + `tests/unit/snapshots/network.schema.json`; minimal counter-example per code; native round-trip | AC-4, AC-5 | standard | implementor |
| S4 matpower | `mambo_power/io/matpower.py` parser (bus/gen/branch/gencost, type-4 → out of service, derived ids) + `io/native.py`; `tests/parity/test_matpower_vs_pandapower.py` over 5 fixtures | AC-6 | complex (parser + oracle alignment) | senior-implementor |
| S5 numerics | `NetworkArrays`, `ybus`, `bbus`, `ptdf`, `lodf` over scipy.sparse; dense re-derivation tests; pandapower Ybus oracle; hypothesis networks for connectivity + bridge detection | AC-7 | complex | senior-implementor |
| S6 install smoke | CI job: `uv build`, fresh venv install of the wheel without dev deps, import + fixture load; fixtures packaged in sdist via MANIFEST/hatch include | AC-8 | standard | implementor |

Order: S1 → S2 (needs CI) → S3 → S4 (needs S3) → S5 (needs S4 for fixture loading) → S6.
S3 can start once S1's pyproject exists; S2 runs in parallel with S3. Every slice RED → GREEN;
tests live beside the slice; commits per slice with `feat(m1/S<n>)` / `test(m1/S<n>)`.

## Verification Matrix

stack-health: before (S1, record/m1-s1-report.md): Python 3.12.14, 3 tests; after (Step 5, record/m1-step5-tests-floor.md): Python 3.12.14 MSC, numpy 2.5.2, scipy 1.18.0, pydantic 2.13.4, highspy 1.15.1, pandapower 3.3.0, pypsa 1.2.4, pytest 9.1.1, hypothesis 6.165.10, ruff 0.16.4, mypy 2.3.1, uv 0.12.5; 175 tests, full run 14.8 s; 9 warnings all from pandapower from_ppc via 3 parity tests, none from src

| AC | tier | status | evidence | auditor |
|---|---|---|---|---|
| AC-1 | T1 | discharged | see AC-1 | CONFIRMED |
| AC-2 | T1 | discharged | see AC-2 | CONFIRMED |
| AC-3 | T1 | discharged | see AC-3 | CONFIRMED |
| AC-4 | T1 | discharged | see AC-4 | CONFIRMED |
| AC-5 | T1 | discharged | see AC-5 | CONFIRMED |
| AC-6 | T2 | discharged | see AC-6 | CONFIRMED |
| AC-7 | T2 | discharged | see AC-7 | CONFIRMED (F1 carried to Step 6) |
| AC-8 | T1 | discharged | see AC-8 | CONFIRMED |

auditor-wave: CONFIRMED — no uncovered requirement; W1/W3/W6 designed by pointer to the epic design; every row has a differing counterfactual; 3 re-executions match; fixtures byte-verified; findings F1 (fixture-parametrized dense Ybus/LODF tests) and F2 (`load` signature) carried to Step 6 (record/m1-audit.md §4)

AC-1:
  criterion: uv sync / ruff / mypy / pytest exit 0 locally and in all 5 CI jobs (T1)
  provenance: wave spec W1; user 2026-08-20 "ok" (tactical defaults)
  tier-run: local (record/m1-s1-report.md): ruff check / ruff format --check / mypy / pytest all exit 0, `uv sync --locked` exit 0; CI run 32423795251 on 2922d8e — 5/5 jobs success, every step success (record/m1-s2-ci-proof.md §1); every later wave-branch commit also green — 8c82e9d run 32424852645, c9b5a90 run 32426337968, fc68535 run 32427821165, wave head 36bd20a run 32428177629 (6/6 incl. install-smoke); local floor on the wave head in record/m1-step5-tests-floor.md
  readback: https://github.com/mambo10005/mambo-power/actions/runs/32428177629
AC-2:
  criterion: planted failing test turns CI red, revert turns it green (T1)
  provenance: canonical-sdlc build intent rule; epic plan M1
  tier-run: planted `assert 1 == 2` on throwaway branch m1/s2-planted-failure (commit c594112): run 32424408894 conclusion failure, pytest step failure on all 5 jobs with `FAILED tests/unit/test_planted_failure.py::test_planted_failure`; an earlier plant (faef8a3, run 32423921545) went red at ruff E501 — incidental proof the lint gate halts the job; the green counterpart is the wave-branch run 32423795251 without the plant; branch deleted, worktree removed (record/m1-s2-ci-proof.md §2-3)
  readback: https://github.com/mambo10005/mambo-power/actions/runs/32424408894
AC-3:
  criterion: pandapower + pypsa import in the test session on ubuntu/macos/windows (T1)
  provenance: epic spec Design §7 assumption 3; wave spec W1
  tier-run: tests/parity/test_oracles_import.py (pandapower 3.3.0, pypsa 1.2.4) passed in the pytest step of all 5 jobs of run 32423795251 — ubuntu 3.11/3.12/3.13, macos 3.12, windows 3.12 (record/m1-s2-ci-proof.md §1 per-job step table)
  readback: https://github.com/mambo10005/mambo-power/actions/runs/32423795251
AC-4:
  criterion: every named validation code raised on its counter-example, silent on fixtures; JSON schema snapshot matches (T1)
  provenance: wave spec W2, W3; record/m1-w1-extract.md §1.4
  tier-run: tests/unit/test_model_invariants.py — 28 cases, one minimal counter-example per code (NO_SLACK, MULTIPLE_SLACK, DISCONNECTED_BUS, DUPLICATE_ID, DANGLING_REF, BAD_BASE, BAD_RANGE) plus a two-problems-one-error case; tests/unit/test_json_schema_snapshot.py vs tests/unit/snapshots/network.schema.json, drift proven by tampering a property name → FAIL → regenerate (record/m1-s3-report.md); silence on fixtures via tests/unit/test_native_roundtrip_fixtures.py (S4) which validates all 5 fixtures; RED: ModuleNotFoundError ×4 before src existed; commit 8c82e9d
  readback: record/m1-s3-report.md §GREEN (pytest 43 passed); CI run 32424852645 on 8c82e9d success 5/5
AC-5:
  criterion: native JSON round-trip is identity on all fixtures (T1)
  provenance: wave spec W3
  tier-run: tests/unit/test_native_roundtrip_fixtures.py — 16 cases over the 5 fixtures, `loads(dumps(net)) == net`; hand-built all-entity round-trip in tests/unit/test_model_roundtrip.py; commit c9b5a90 (record/m1-s4-report.md)
  readback: CI run 32426337968 on c9b5a90 success 5/5
AC-6:
  criterion: importer equals pandapower from_mpc on 5 fixtures within 1e-9; type 4 → out of service (T2)
  provenance: wave spec W4; record/m1-w1-extract.md §2
  fixture-fidelity: fixtures/matpower/*.m are verbatim upstream MATPOWER bytes (PROVENANCE.md, sha256-verified against gridlab archive/ts-w1)
  tier-run: tests/parity/test_matpower_vs_pandapower.py — 30 cases; oracle = independent numpy.loadtxt read of regex-extracted mpc blocks feeding pandapower's own _adjust_ppc_indices / _change_ppc_TAP_value / from_ppc (from_mpc minus its matpowercaseframes reader, which is not in the locked env); layer A raw columns max abs diff 0.0 on every group, layer B pandapower tables after unit alignment worst 2.8e-14; pandapower from_ppc.py:303 bug worked around in the oracle copy only (A10); mutations of 2e-9 on x, 1e-8 on a cost coefficient, bus-type flip, in_service flip all fail the comparison; type-4 → in_service=False covered in tests/unit/test_matpower_parser.py (no fixture carries type 4); commit c9b5a90 (record/m1-s4-report.md §5)
  readback: CI run 32426337968 on c9b5a90 success 5/5 (parity tier ran on ubuntu 3.11/3.12/3.13, macos, windows)
AC-7:
  criterion: Ybus/Bbus/PTDF/LODF equal dense re-derivation and pandapower Ybus on all fixtures; LODF bridges marked undefined (T2)
  provenance: wave spec W5; epic spec Design §4
  fixture-fidelity: same verbatim MATPOWER fixtures plus hypothesis-generated networks (synthetic, declared)
  tier-run: tests/unit/test_numerics_dense.py — 15 cases, independent dense double-loop Ybus/Bbus on a 6-bus tapped+shifted case (1e-12), PTDF vs direct Bθ=P solve (1e-10), LODF vs actual branch-removal rebuild (1e-8), bridges() agrees with NaN columns; tests/parity/test_ybus_vs_pandapower.py — pandapower.pypower.makeYbus oracle (spec assumption (b) holds), max |diff| case14 0, case30 8.9e-16, case_ieee30 7.1e-15, case57 1.4e-14, case118 2.9e-14; Bbus/Bf/Pbusinj vs makeBdc; bridges per fixture 1/3/3/1/9; tests/property/test_numerics_properties.py — 5 hypothesis properties; mutation checks (tap², b/2, DC tap, LODF sign, parallel-edge bridge) all caught; phase-shift conj covered by the dense case only (A12); commit fc68535 (record/m1-s5-report.md)
  readback: record/m1-s5-report.md §GREEN (pytest 172 passed, 11.2 s); CI run 32427821165 on fc68535 success 5/5 (ubuntu 3.11 leg green with the mypy pin removed, A11)
AC-8:
  criterion: built wheel installs in a fresh venv without dev deps; import + case14 load exit 0 (T1)
  provenance: wave spec W6
  tier-run: CI job "install smoke (wheel + sdist)" in run 32428177629 on 36bd20a — `uv build`, fresh venv without the project/dev group, `uv pip install dist/*.whl`, AC-8 import + case14 load command exit 0, wheel listing asserts py.typed present and no fixtures/ or tests/ paths, sdist installed into a second fresh venv and imported; RED (record/m1-s6-report.md): default sdist leaked the .bionic junction tree, uv.lock and dotfiles → explicit sdist include list; tests/unit/test_packaging_metadata.py; local re-run of the same sequence in record/m1-step5-tests-floor.md; commit 36bd20a
  readback: https://github.com/mambo10005/mambo-power/actions/runs/32428177629

## Dispatch ledger

| id | role | unit | deliverable | status |
|---|---|---|---|---|
| m1-env-uv | implementor | Step 0 pre-flight: install uv, Python 3.12 | record/m1-env-attestation.md | done (verified on disk 2026-08-20; uv 0.12.5 at C:\Users\mambo\AppData\Roaming\Python\Python314\Scripts\uv.exe, NOT on PATH; CPython 3.12.14 uv-managed) |
| m1-s1-scaffold | senior-implementor | S1 scaffold (pyproject, lock, ruff/mypy, pytest tiers, CI 5-job matrix) — progress .bionic/tmp/s1-progress.md, cadence 5m, ~25 min | record/m1-s1-report.md + commit on wave/01-substrate | done (commit 2922d8e, report verified on disk 2026-08-20; pushed to origin by orchestrator, user-authorized) |
| m1-s2-planted | test-runner | S2 CI proof: observe green run for 2922d8e; plant failing test on throwaway branch m1/s2-planted-failure (worktree mambo-power-s2), observe red, delete branch — progress .bionic/tmp/s2-progress.md, cadence 5m, ~20 min | record/m1-s2-ci-proof.md | done (report verified; green run 32423795251 5/5, red run 32424408894 pytest-fail 5/5; branch + worktree removed, verified by orchestrator) |
| m1-s3-model | implementor | S3 model: pydantic entities, Network invariants + named errors, JSON schema snapshot, io.native — progress .bionic/tmp/s3-progress.md, cadence 5m, ~40 min | record/m1-s3-report.md + commit on wave/01-substrate | done (commit 8c82e9d, 43 tests green, report verified on disk) |
| m1-s4-matpower | senior-implementor | S4 MATPOWER importer incl. gencost, parity vs pandapower on 5 fixtures, fixture round-trip — progress .bionic/tmp/s4-progress.md, cadence 5m, ~45 min | record/m1-s4-report.md + commit on wave/01-substrate | done (commit c9b5a90, 127 tests green, report verified; oracle = independent numpy read + pandapower from_ppc pipeline; pandapower from_ppc.py:303 bug worked around in oracle copy only) |
| m1-s5-numerics | senior-implementor | S5 numerics: NetworkArrays pu view, Ybus/Bbus/PTDF/LODF, dense + pandapower + hypothesis oracles — progress .bionic/tmp/s5-progress.md, cadence 5m, ~50 min | record/m1-s5-report.md + commit on wave/01-substrate | done (commit fc68535, 172 tests green on 3.12 and a 3.11 scratch venv; Ybus oracle = pandapower makeYbus, max diff ≤ 2.9e-14; report verified; pushed) |
| m1-s6-install | implementor | S6 install smoke: wheel/sdist build config, py.typed, install-smoke CI job, packaging test — progress .bionic/tmp/s6-progress.md, cadence 5m, ~25 min | record/m1-s6-report.md + commit on wave/01-substrate | done (commit 36bd20a, 175 tests green, report verified on disk; CI 32428177629 6/6 incl. install-smoke) |
| m1-auditor | auditor | Step 5 exit gate: coverage / power / authenticity over spec + design + matrix + record; ≤3 re-executions; revert-and-watch via request file .bionic/tmp/audit-revert-request.md → test-runner | record/m1-audit.md | done (all 8 rows CONFIRMED, wave CONFIRMED; revert-and-watch VALIDATED on resume; F1/F2 carried to Step 6) |
| m1-revert-watch | test-runner | Auditor's revert-and-watch: stub off-nominal tap out of ybus.branch_admittances in throwaway worktree mambo-power-audit @36bd20a; predicted 6 fails / 169 pass; restore; remove worktree | record/m1-revert-watch.md | FAILED — API 529 mid-run; stub left applied in mambo-power-audit, no artifact; relaunched fresh as m1-revert-watch-2 |
| m1-revert-watch-2 | test-runner | same protocol, inherits the applied stub; baseline via stash | record/m1-revert-watch.md | done (artifact verified; baseline 175 passed; with stub 6 failed / 169 passed — exact match to the auditor's prediction by name; restored; worktree removed, `worktree list` shows m1 only) |
| m1-review-6axis | code-reviewer | Step 6 stance 1: six-axis review | record/m1-review-6axis.md | FAILED — API 529, no artifact; relaunched fresh as m1-review-6axis-2 |
| m1-review-6axis-2 | code-reviewer | Step 6 stance 1: six-axis review (correctness, readability, architecture incl. closure check, security, performance, duplication vs ownership table + agreement tests) with PASS/FLAG/FAIL per axis; assesses auditor findings F1/F2 | record/m1-review-6axis.md | done (artifact verified 27 KB; Security PASS, Performance PASS, Correctness/Readability/Architecture/Duplication FLAG, no FAIL; fold list in its closing table) |
| m1-critic | critic | Step 6 stance 2: adversarial critic over spec + plan + diff + review notes + audit; ~40 min | record/m1-critic.md | done (artifact verified 18 KB; READY AFTER FIXES; 8 issues: 1 should-fix, 3 carry, 4 notes) |
| m1-fold | senior-implementor | Step 6 fold commit R1: review A1/C1-4/D3-4/R1-5 + critic 1/5/6 — progress .bionic/tmp/r1-progress.md, cadence 5m, ~50 min | record/m1-r1-fold-report.md + commit on wave/01-substrate | done (commit ddbcdc4; nothing from A-H skipped; 269 tests; unit tier 6.1 s, full 48 s; snapshot changed in 3 description strings only; pushed) |
| m1-floor-2 | test-runner | Step-6 floor re-run on ddbcdc4: ruff/format/mypy/pytest per tier + full, build + wheel/sdist smoke | record/m1-step6-tests-floor-post-fold.md | done (all green on ddbcdc4: unit 202, parity 62, property 5, full 269/269 in 37 s; build + wheel/sdist smoke exit 0; the worktree edits it observed afterwards were m1-r2-macos-fix's in-flight work) |
| m1-r2-macos-fix | implementor | R2: relax platform-dependent pandapower LODF bridge-column assertion (CI 32434672637 macOS failure, A22); test-only | record/m1-r2-macos-fix-report.md + commit on wave/01-substrate | done (commit fcbf571, test-only; gate 269 passed; pushed) — CI 32435150722 still red on macOS: oracle bridge column is finite AND bounded there; superseded by R3 |
| m1-r3-oracle-bridge | implementor | R3: delete the oracle bridge-column assertion entirely; ours-NaN stays; teeth check via lodf.py | record/m1-r3-oracle-bridge-report.md + commit on wave/01-substrate | done (commit 3c4f88d, test-only; teeth RED via lodf.py then GREEN; gate 269 passed; pushed; CI awaited) |
| m1-step5-floor | test-runner | Step 5 tests floor on wave head 36bd20a: discovered-suite inventory, ruff/format/mypy/pytest per tier + full, uv build + install-smoke sequence, stack-health snapshot — ~15 min | record/m1-step5-tests-floor.md | done (all green 175/175, artifact verified on disk 15.6 KB) |
| m1-w1-extract | researcher | Step 1/2: W1 schema/importer/parity facts from archive/ts-w1 | record/m1-w1-extract.md | done (verified on disk 2026-08-20, 27 KB, sections 1-4 + Surprises) |

## Assumptions

Seeded from spec Not Doing and spec Design assumptions (a)-(c). Additions:

- A1: `Scenario` moves from the epic plan's M1 line to M4 (first consumer) — one-line
  correction, logged 2026-08-20 at Step 0.
- A2: Python 3.12 is the project's pinned interpreter (`.python-version`); 3.11 and 3.13
  run on Ubuntu only. pandapower/PyPSA wheels for 3.14 are not assumed.
- A3: The GitHub Actions free tier suffices (public repo: unlimited minutes); macOS jobs
  are the slow leg and may be limited to push-to-epic/main if the queue hurts.
- A5 (S3, 2026-08-20): `NetworkValidationError` subclasses `Exception`, not `ValueError` —
  pydantic 2.13.4 wraps any ValueError raised in a model_validator into
  `pydantic_core.ValidationError` and drops `.issues`; `except ValueError` will not catch it.
  Accepted; document in M9 API docs.
- A6 (S3, 2026-08-20): BAD_BASE / BAD_RANGE are checked in the Network after-validator so
  one pass reports every issue; consequence: a standalone `Bus(base_kv=-1)` constructs, and
  the JSON schema carries bounds as description text only. Machine-readable bounds
  (`json_schema_extra` on four fields + snapshot regen) are a Step-6 review candidate, not
  an M1 blocker.
- A7 (S3): `validate_network(net) -> list[ValidationIssue]` is public — models are
  mutable and mutation never re-validates; this is the re-check entry point.
- A8 (S2): the planted failure ran on a throwaway branch off the wave head rather than on
  the wave branch itself, so the wave history carries no plant/revert noise; the same
  workflow file ran, so the instrument proven is the same instrument.
- A9 (S4): `mpc.bus_name` is parsed past and dropped — `Bus` has no `name` field. Adding
  optional `name` to Bus/Generator is a schema change; Step-6 review candidate alongside A6.
- A10 (S4): pandapower 3.3.0 `converter/pypower/from_ppc.py:303` writes the no-rating
  sentinel into the trafo array instead of the impedance array; genuine `from_mpc` crashes
  on case_ieee30 and case118. Worked around in the oracle copy only. Upstream issue not
  filed — logged under ideas/ for the user to decide (external-facing).
- A11 (S5, orchestrator-accepted): `[tool.mypy] python_version = "3.11"` removed from
  pyproject — numpy ≥ 2.5 stubs use PEP 695 `type` statements that mypy cannot parse
  under a 3.11 target; mypy now follows each CI job's interpreter (the lock resolves
  numpy 2.4.6 on 3.11, whose stubs parse). Proven locally on 3.12 and a 3.11 scratch venv.
  Latent S1 defect exposed by the first numpy import from src.
- A12 (S5): no fixture carries SHIFT ≠ 0, so the phase-shift conjugation in Ybus is
  covered only by the dense 6-bus unit case (mutation-checked), not by parity.
- A13 (floor): hatchling packs the repo-root `.gitignore` into the sdist despite the
  explicit include list — harmless, not in the forbidden list; Step-6 review note.
- A14 (floor): the Ubuntu 3.11/3.13 and macOS legs are verified only by CI
  (run 32428177629), not locally — declared, not hidden.
- A15 (audit F2 / review Architecture): the importer ships `load(path)` + `loads(text)`
  instead of the spec's `load(path_or_text)`; spec W4 amended at Step 6 to the delivered
  contract (json precedent), no code change.
- A16 (critic 3, carry to M2 — design question): an in-service island (e.g. one branch
  status flipped in an otherwise valid MATPOWER file) raises DISCONNECTED_BUS at load;
  pandapower tolerates islands (NaN results on isolated buses). M1 keeps the hard error
  (a Network with an island has no solvable power flow without a slack per island); M2
  decides between auto-deactivating islands with a warning in `load_with_warnings` and
  a per-island slack policy. Spec Design 4's rationale ("keeps real files loadable") is
  narrower than stated until then.
- A17 (critic 4, carry to M2/M3): the importer silently drops gen MBASE, PC/QC capability
  curves, RAMP_*, APF, branch RATE_B/RATE_C, ANGMIN/ANGMAX; `Generator` has no ramp or
  emergency-rating fields. Fixtures carry only default values there, so no test can see
  it. M3 (OPF) adds ramp + angle limits to the model when it first needs them; the
  importer should then warn on non-default dropped columns.
- A18 (critic 2, carry to M2): `NetworkArrays.bus_type` / `v_set` are the *declared* roles;
  MATPOWER/pandapower solve with *effective* roles (PV bus with all gens out → PQ; slack
  with no in-service gen → error). M2's AC-NR owns that derivation — in `numerics` or
  `pf`, decided there with a test that can tell the difference.
- A19 (critic 7, note): `NetworkArrays` is `frozen=True` on the dataclass but holds
  mutable numpy arrays; callers can mutate in place. Acceptable for a derived view; M2
  documents it.
- A20 (critic 8a): pushing `epic/01-foundation` after the Step-8 merge is a user decision
  (only the wave branch was authorized for CI pushes).
- A21 (fold G): no IEEE fixture has a multi-generator bus, so the per-bus-sum vs
  per-generator agreement test is load-bearing only on the 4-bus unit network; fixtures
  cover the single-generator path. M2/M3 should add a multi-gen fixture (e.g. case9 with a
  split unit) when per-generator dispatch first matters.
- A22 (R2/R3): pandapower's makeLODF representation of a bridge (singular) column is
  platform-dependent — non-finite on Linux/Windows, but on macOS Accelerate finite AND
  bounded (the column equals the raw H[:,k], max 1.0; CI 32435150722 on fcbf571 showed
  it after R2's "huge finite" relaxation also failed). CI 32434672637 on ddbcdc4 first
  exposed it, only on macOS, in the new PTDF/LODF oracle test for case_ieee30/case118.
  R3 asserts nothing about the oracle's bridge columns. Our `lodf()` marks bridges by the tolerance `|1 − h_kk| < 1e-10`,
  which absorbs the platform noise, and the graph-theoretic `bridges()` is cross-checked
  against those NaN columns by the dense/property/fixture agreement tests (green on macOS
  at fc68535 and ddbcdc4); the oracle assertion was over-specified and is relaxed (R2). Lesson for M2+: oracle
  comparisons exclude singular/bridge columns explicitly rather than asserting how the
  oracle represents them.
- A4: `uv` is at `C:\Users\mambo\AppData\Roaming\Python\Python314\Scripts\uv.exe`
  (record/m1-env-attestation.md) and is NOT on PATH in a fresh shell; slices are briefed
  with the absolute path (or `python -m uv`). CI uses `astral-sh/setup-uv`, so PATH is a
  local-only concern; adding the Scripts dir to PATH is the user's call.

## Handoff

Resume point: WAVE M1 COMPLETE 2026-08-20 — Steps 0-9 done. Merged into
epic/01-foundation at 6c94459 (local; user pushes). Worktree removed, tmp wiped, cleaned.
Next: wave M2 power-flow per record/continuation-m1.md. User authorization on record:
wave branches may be pushed to origin for CI (2026-08-20); the epic branch push is the
user's (A20).
Decisions ratified this session: triple, scope, M1-local design (units, naming, gencost
now, type-4 tolerance, named errors, ids).
Open blockers: none. Outstanding user action: delete leftover C:\Claude Projects\gridlab-w1.
Resume instruction: on approval, `git worktree add C:\Claude Projects\mambo-power-m1 -b
wave/01-substrate epic/01-foundation`; dispatch S1 (senior-implementor) with the uv path
from the attestation; S3 may dispatch as soon as S1's pyproject is committed.
