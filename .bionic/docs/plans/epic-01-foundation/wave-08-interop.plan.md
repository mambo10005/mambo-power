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
deploy_target: none
cleanup_on_finish: true
use_worktree: true
rigor-floor: audited
walk: required
design-interview: true
cleaned: 2026-08-30
model_plan:
  orchestrator: fable-5
  implementor: sonnet
  senior-implementor: opus
  researcher: sonnet
  test-runner: sonnet
  auditor: opus
  critic: opus
---

# Wave M8 — interop — plan

Spec: `specs/epic-01-foundation/wave-08-interop.spec.md` (carries `## Design`).
Scope + design ledger: `record/m8-scope.md`. Research: `record/m8-research.md`.

## SDLC State

integration-branch: epic/01-foundation
intent: build
rigor: audited
scale: wave
current: 9 — shipped; merge `511c6a0`

- Step 0: prereqs: ok; configured 2026-08-30 via "confirm"; model_plan=fable-5/sonnet/opus;
  integration-branch=epic/01-foundation; base cdb4fef (1175 passed / 4 skipped locally; CI green on
  Linux/macOS/Windows at that head)
- Step 1: record/m8-scope.md (rulings D1–D4, Not Doing, prior art, four questions carried to Step 2)
- Step 2: specs/epic-01-foundation/wave-08-interop.spec.md (W1–W8, AC-1..AC-8 with provenance,
  `## Design` ratified 2026-08-30 after the frame and S1–S3 walked one per turn, T1–T6 surfaced at
  ratification; research `record/m8-research.md` supplied every field map)
- Step 3: plans/epic-01-foundation/wave-08-interop.plan.md approved by the user 2026-08-30 ("Approved — go"); design + plan + matrix locked together at that one checkpoint; governing design: the spec's `## Design` + epic.spec.md
- Step 4: worktree: C:/Claude Projects/mambo-power-m8; base-sha: 15e71fa; branch: wave/08-interop; slices S1–S6 per `## Slices`; **baseline on the clean main checkout at 15e71fa, before any agent entered the worktree: 1175 passed / 4 skipped in 452.70s** (scratchpad `m8-baseline-15e71fa.log`, 2026-08-30 02:34Z); `.bionic/docs` is edited only by the orchestrator in the main checkout and committed on epic/01-foundation — the wave branch never touches it
- Step 5: walk-artifact: record/m8-walk.md (0 `AC-[0-9]` hits, at 7ec0b0b, dispatched first); cmd: `uv run pytest -q -p no:cacheprovider` at 3f2a9a0; pass: 1430; total: 1430 (+4 skipped; ruff check + format clean at the same head; mypy/mkdocs cut by the F8 restart — retaken at the post-S7/S8 head); output: scratchpad `m8-gate-3f2a9a0.log`; auditor: record/m8-audit.md — 8 DISCHARGED / 0 PARTIAL / 0 REFUTED, wave COVERED (at 7ec0b0b); rows discharge in the matrix below at the final head
- Step 6: critic: record/m8-critic.md — two full passes, `not merge-ready (3 blocking)` → `merge after should-fixes` → confirmed clean at the final sweep; every finding fixed at the layer it lives, red → green → sabotage (S8, S9)
- Step 7: adr: docs/design/decisions.md#ADR-011 (commit 33abd13/`33abd13`); continuation: record/continuation-m8.md
- Step 8: merge: 511c6a0 (--no-ff, epic/01-foundation, tree identical to 33abd13 modulo orchestrator-only .bionic commits); worktree-removed: C:/Claude Projects/mambo-power-m8 (2026-08-30, --force); cleanup: done; tmp-wiped: 97 m8-* files + 3 leftover M1-M3 critic dirs moved to record/, tmp/ empty; tasks-completed: all
- Step 9: deploy: n/a (deploy_target: none — library, unpushed by convention); verified-at: 2026-08-30T17:38Z sweep at 33abd13; monitor: n/a

## Slices

| slice | scope | ACs | complexity | role | depends on |
|---|---|---|---|---|---|
| S1 `kind` + reports | W6 `Branch.kind` defaulted at construction, schema snapshot; W7 `ExportReport` in `io/report.py`; the docs test that ties each module's limitation list to its report codes (stub, filled by S2–S5) | AC-6, AC-7 | complex | senior-implementor | — |
| S2 pandapower JSON | W1 import + W2 export, lazy pandapower import, `ext_grid` rule, unit conversions, parity vs `rundcpp`/`runpp`, `nets_equal` (A6) | AC-1, AC-2 | complex | senior-implementor | S1 |
| S3 PyPSA export | W3, parity vs `opf.solve_dc_opf` on case14/30/118, drop-and-report for inexpressible costs, no `p_set` on generators | AC-3 | standard | implementor | S1 |
| S4 RAW v33 | W4 parser; **fixtures first**: `fixtures/case14_v33.raw` hand-authored from `case14.m` with PROVENANCE, plus `fixtures/synthetic_quirks_v33.raw` with hand-derived expected values | AC-4 | complex | senior-implementor | S1 |
| S5 CSV bundle | W5 dump/load, manifest, side tables, bit-exact round-trip on every fixture, three malformed-bundle errors | AC-5 | standard | implementor | S1 |
| S6 docs | W8: `formats.md` sections, API pages, `examples/13_interop.py`, changelog, architecture edge; `test_api_docs_coverage` green | AC-8 | standard | implementor | S2–S5 |

S2–S5 run in parallel after S1 lands (they share only `io/report.py` and `model/entities.py`,
which S1 owns and finishes first). Each slice owns its module, its test file(s) and its fixtures;
nothing else. Per-file ownership is in the dispatch briefs; the orchestrator verifies every
commit's `--stat` against it (M7 F16).

## Verification Matrix

auditor-wave: CONFIRMED — COVERED at 7ec0b0b and e2d6da8 (every W has a criterion, every criterion an inbound citation, ownership-table citations resolve)
stack-health: before 1175 passed / 4 skipped at 15e71fa (clean main checkout, 452.70s) → after **1513 passed / 4 skipped at 33abd13** (205.38s; ruff check, ruff format 201 files, mypy 59 files, mkdocs --strict all clean) — +338 over the M7 baseline. This is the wave's figure of record: log scratchpad `m8-gate-33abd13.log`, 2026-08-30 17:38Z. Intermediate sweeps, each recorded above at its own head: `7ec0b0b` (1 failed — F4), `3f2a9a0`, `e2d6da8` (1494/4).

| AC | tier | status | evidence | auditor |
|---|---|---|---|---|
| AC-1 | T2 | discharged | see AC-1 | CONFIRMED (7ec0b0b, e2d6da8) |
| AC-2 | T2 | discharged | see AC-2 | CONFIRMED (7ec0b0b, e2d6da8) |
| AC-3 | T2 | discharged | see AC-3 | CONFIRMED (7ec0b0b, e2d6da8) |
| AC-4 | T1 | discharged | see AC-4 | CONFIRMED (7ec0b0b, e2d6da8) |
| AC-5 | T1 | discharged | see AC-5 | CONFIRMED (7ec0b0b, e2d6da8) |
| AC-6 | T1 | discharged | see AC-6 | CONFIRMED (7ec0b0b, e2d6da8) |
| AC-7 | T1 | discharged | see AC-7 | CONFIRMED (7ec0b0b, e2d6da8) |
| AC-8 | T0 | discharged | see AC-8 | CONFIRMED (7ec0b0b, e2d6da8) |

Tier rationale: AC-1..AC-3 are T2 because the real engine (pandapower, PyPSA) runs over the
converted network — the fixture-fidelity declaration is the MATPOWER case each was derived from;
AC-4..AC-7 are pure substrate with no runtime surface (hand-derived oracles, bit-exact round-trips,
schema snapshot); AC-8 is docs. No T3: nothing is a live surface. The walk (required) drives the
four modules from `formats.md` as a user would, before any row discharges.

AC-1:
  tier-run: `uv run pytest -q tests/unit/test_io_pandapower_json.py tests/parity/test_pandapower_json_vs_pandapower.py` at e2d6da8 — 44 passed (S2) + B2's ten tap_changer_type cases (S8); in the named sweep
  readback: import of pp.networks.case14()/case30() equals io.matpower.load on every listed field at ≤1.1e-16 with the five pandapower deviations asserted PRESENT (vn_kv, the two nominal-tap trafos, cp2 4e-8, rating sentinel, zones); multi-ext_grid → one slack + EXTRA_EXT_GRID_DEMOTED; dropped columns each in the report; tap_changer_type None/Ratio/Symmetrical/Ideal match net._ppc TAP/SHIFT to 1e-9 (S8 B2). Sabotages: shunt sign, tap ignored, report entry dropped — each reddened the named test
  criterion: pandapower JSON import agrees with the MATPOWER-derived Network on case14/30 to 1e-9 on every listed field; multi-ext_grid → one slack + warning; dropped columns reported
  provenance: epic R11; user 2026-08-30 "Best effort + report"; m8-research.md §1
  fixture-fidelity: pandapower's own `pp.networks.case14()`/`case30()` (real pandapower objects) against `fixtures/case14.m`/`case30.m` (MATPOWER, PROVENANCE files)
AC-2:
  tier-run: same parity file — rundcpp vs pf.solve_dc and runpp vs pf.solve_ac on case14/30/57; bulk-export nets_equal test (S8 S4); in the named sweep
  readback: angles worst 8.9e-15 / 1.8e-15 / 1.3e-13 deg, flows ≤1e-6, vm worst 6.7e-16 / 8.9e-16 / 2.4e-15 pu; every fixture's export loads in pp.from_json; strict nets_equal holds on {poly_cost, pwl_cost} and is PINNED (F2); every carried value survives at 1e-12; export report names dropped setpoints; case300 export 3062 → 112 ms with nets_equal to the per-row form. Sabotage: export tap dropped → case57 angles red at 0.215
  criterion: exported JSON loads in pandapower; rundcpp/runpp agree with pf.solve_dc/solve_ac to 1e-6 on case14/30/57; nets_equal on carried tables; dropped costs reported
  provenance: epic R11; user 2026-08-30 "Drop + report"; m8-research.md §1
  fixture-fidelity: the six bundled MATPOWER cases, exported by this wave and solved by pandapower 3.3.0
AC-3:
  tier-run: `tests/unit/test_io_pypsa.py tests/parity/test_pypsa_export_vs_pypsa.py` — 33 passed (S3) + b≠0 pf parity (S8 B1); in the named sweep
  readback: PyPSA optimize vs opf.solve_dc_opf objective ≤1.3e-12 relative on case14/30/118; dispatch ≤1e-4 MW on case14/30 and 1.87e-3 MW on case118 (the oracle's QP residual, F3, amended to 2e-3); piecewise units at marginal_cost 0 each named; no generator p_set (asserted); transformer b as admittance: n.pf() vm matches pf.solve_ac to 1e-6 for b=0.3/−0.05; unrated s_nom sentinel reported per branch (walk). Sabotages: p_set set → parity infeasible; x unscaled → rated-loop test red; b factor reverted → 2 red
  criterion: PyPSA optimize on to_network(net) agrees with opf.solve_dc_opf on case14/30/118 (1e-8 rel objective, 1e-4 MW dispatch); piecewise units at marginal_cost 0 and reported; no generator p_set
  provenance: epic R11; user 2026-08-30 "Drop + report"; m8-research.md §2; M3 spec AC-3
  fixture-fidelity: bundled MATPOWER cases with degree ≤ 2 costs, solved by PyPSA 1.2.4 / linopy 0.9.1 / HiGHS
AC-4:
  tier-run: `tests/unit/test_io_psse_raw.py` — 26 passed (S4 + neutral-tap follow-up) + UNTERMINATED_SECTION fix tests (S7); in the named sweep
  readback: case14_v33.raw equals case14.m's Network on every bus/branch(kind)/generator/load field to 1e-9, costs None with RAW_NO_COSTS; quirks fixture matches hand-derived CZ=2/CW=3/CM=2/ZIP/end-shunt values (auditor re-derived by hand); neutral-tap transformer imports as transformer with tap None; 3-winding → one entry per record; area records reported. Sabotages: CZ=2 skipped → r red; kind dropped → 3 red on the quirks fixture
  criterion: case14_v33.raw imports equal to case14.m's Network (kind included) to 1e-9, costs absent and reported; quirks fixture matches hand-derived values; 3-winding records ignored with one report entry each
  provenance: epic R11; user 2026-08-30 "Hand-author from case14.m"; m8-research.md §3
AC-5:
  tier-run: `tests/unit/test_io_csv_bundle.py` — 56 passed (S5) + BOM/blank-line/atomic tests (S7, S8); in the named sweep
  readback: load(dump(net)) == net and array_equal on every NetworkArrays field for 14 networks incl. 0.1+0.2, 5e-324, 1e300, −0.0, ids "01"/"1"/"" (auditor reproduced); unknown column / missing table / duplicated id / schema 99 each a named error; manifest carries the native schema version; mid-write failure leaves the old bundle byte-identical. Sabotages: .12g floats → 4 red; int-coerced ids → 20 red
  criterion: load(dump(net)) == net and array_equal on every NetworkArrays matrix for all fixtures; three malformed bundles fail with named errors; manifest names the schema version
  provenance: epic R11; user 2026-08-30 "Machine round-trip"; m8-research.md §4
AC-6:
  tier-run: `tests/unit/test_branch_kind.py tests/unit/test_json_schema_snapshot.py` — 15 + promotion/mutation tests (S8 B3); in the named sweep
  readback: default line/transformer from tap/shift both ways; explicit transformer at nominal tap preserved through native; explicit line with a tap PROMOTED (amended, F7); mutated line round-trips through native equal to a fresh build; snapshot changed by exactly the kind property (+ its description text at 738dcf8); every pre-M8 unit test unmodified and green (920 collected pre-M8). Revert-and-watch: default forced to line → 4 red (auditor)
  criterion: Branch.kind defaults line/transformer from tap/shift; snapshot changes by one property; every pre-M8 test unmodified and green; pandapower's neutral-tap transformer round-trips as transformer
  provenance: user 2026-08-30 "Explicit kind, defaulted"; m8-research.md G4
AC-7:
  tier-run: `tests/unit/test_export_report.py tests/unit/test_io_limitations.py tests/unit/test_io_limitations_import_order` (S1, S6, S8 S9) + each module's report tests; in the named sweep
  readback: lossless paths yield an empty report on all four modules (auditor: stdout/stderr/root logger empty on each); every lossy path names element id and field; LIMITATIONS == union of the four CODES by construction, every code documented in formats.md; registry in io/limitations.py, report.py a leaf, eight import orders with pandapower/pypsa blocked. Sabotage: a code removed from formats.md → exactly one test red
  criterion: each module's lossy conversion yields a report naming element and field; lossless yields an empty report; raise_on_error as ImportReport; no logging/printing
  provenance: user 2026-08-30 "Best effort + report"; M1 io.report
AC-8:
  tier-run: `uv run --group docs mkdocs build --strict` exit 0 at e2d6da8 (24.83s, no unlinked/anchor lines); `tests/unit/test_examples_run.py` 15 passed with example 13 at its measured budget (F4); api-docs coverage and docstrings green
  readback: formats.md has a section per format in the matpower shape naming every code; API pages for the four modules, io.report and io.limitations; examples/13_interop.py exit 0 and embedded as example 13; changelog M8 entry; architecture and roadmap updated
  criterion: formats.md sections, API pages under the griffe guard, examples/13_interop.py exit 0 and embedded, changelog, mkdocs --strict exit 0
  provenance: epic R14; M6/M7 docs rows

## Tasks

| id | role | unit | deliverable | status |
|---|---|---|---|---|
| m8-research | researcher | Field maps for the four formats against `Network`; model gaps G1–G11; fixture candidates; versions | record/m8-research.md | **done** (orchestrator-verified: artifact exists, 11 gaps, three fidelity limits; measured pandapower/PyPSA unit conventions and the `from_ppc` failure that rules out pandapower's converter) |
| m8-s1-kind-reports | senior-implementor | S1: `Branch.kind` defaulted at construction (W6), `ExportReport` mirroring `ImportReport` + `LIMITATIONS` registry with the docs-coverage test (W7). Owns `model/entities.py`, `io/report.py`, `tests/unit/test_branch_kind.py`, `tests/unit/test_io_limitations.py`, the schema snapshot | record/m8-s1-report.md + 3 commits | **done** (`79a71ea` kind, `25e9bed` ExportReport + LIMITATIONS, `a51250f` API page; orchestrator-verified: every `--stat` carries its source; 31/31 own tests here; snapshot +1 property exactly. Two things it found: `ImportReport` never had `errors`/`raise_on_error` — my brief assumed them — so it added a shared `_Report` base, backward compatible (950 pre-M8 tests unchanged); and its own commit-2 message claimed a green that a `| tail` had masked (F16 class) — caught and fixed in commit 3 and stated plainly. `ConversionIssue = ImportIssue`; codes stay a closed set in `model/warnings.py`, so S2–S5 extend `ImportIssueCode`. Docs group: `uv run --group docs mkdocs`) |
| m8-s2-pandapower | senior-implementor | S2: `io.pandapower_json` import + export (W1, W2), lazy pandapower import, `ext_grid` rule, unit conversions, parity vs `rundcpp`/`runpp`, `nets_equal` measured first (A16). Own worktree `mambo-power-m8-s2` on `wave/08-interop-s2`. Owns `io/pandapower_json.py`, `tests/unit/test_io_pandapower_json.py`, `tests/parity/test_pandapower_json_vs_pandapower.py`, its LIMITATIONS entry + codes | record/m8-s2-report.md + 3 commits | **done** (`bd05df7` io + 7 codes, `bb539c3` parity + A16 measurement, `cf9652e` np.float64 in messages — a sabotage side-finding; merged as `990235c`). Orchestrator-verified in its worktree: 44 passed across its two files. Import matches the `.m` fixtures at 1e-16 with pandapower's five deviations **listed and asserted present**, not tolerated; `rundcpp`/`runpp` on the export match `solve_dc`/`solve_ac` at 1e-13/1e-15. Its first real red was the exporter's `c_nf_per_km` inversion (b·Zb for b/Zb) — DC parity was blind to it, AC parity caught it (2.4e-3 pu / case30 non-convergence), fixed before commit 1. A16 → **F2** |
| m8-s3-pypsa | implementor | S3: `io.pypsa` export (W3), parity vs `opf.solve_dc_opf` on case14/30/118, drop-and-report, no generator `p_set`. Worktree `mambo-power-m8-s3`. Owns `io/pypsa.py`, `tests/unit/test_io_pypsa.py`, `tests/parity/test_pypsa_export_vs_pypsa.py`, its LIMITATIONS entry + codes | record/m8-s3-report.md + 2 commits | **done** (`9714c1f` exporter + 7 `PYPSA_*` codes, `0a88cbd` API page; merged as `4ebb2bc`). Orchestrator-verified: 33 passed across its two files. Three sabotages; the transformer-x one did not redden case14 parity (no fixture rates a branch, so merit-order dispatch is impedance-independent) and it **added a rated tap-transformer loop test that does** — the M6/M7 lesson applied unprompted. Found **F1** (the shifter bug) on the way. case118 dispatch residual → **F3** |
| m8-s4-raw | senior-implementor | S4: `io.psse_raw` v33 import (W4); fixtures first — `fixtures/case14_v33.raw` hand-authored from `case14.m` with PROVENANCE, `fixtures/synthetic_quirks_v33.raw` with hand-derived values. Worktree `mambo-power-m8-s4`. Owns `io/psse_raw.py`, the two fixtures + PROVENANCE, `tests/unit/test_io_psse_raw.py`, its LIMITATIONS entry + codes | record/m8-s4-report.md + 3 commits | **done** (`8327358` fixtures + `PROVENANCE-raw.md` with the hand arithmetic first, `f30a8a7` parser, `064e2c2` neutral-tap transformer added on orchestrator follow-up; merged as `efdc1dd` after a union resolution of the `ImportIssueCode` conflict with S5 — both appended codes, expected). Orchestrator-verified in its worktree: 26/26 own tests, every `--stat` carries its source. Its honest finding: the first `kind` sabotage did not redden the case14 test because the default infers `transformer` from off-nominal taps — case14 has no neutral-tap transformer, so A7 was not exercised by a fixture; the follow-up added `branch-2-4-1` (WINDV 1.0/1.0, ANG 0) to the quirks file and that sabotage now reddens three tests. Nine `RAW_*`/repair codes in `CODES` for S6. `RawImportError` for malformed files; `REV != 33` refused |
| m8-s5-csv | implementor | S5: `io.csv_bundle` dump/load (W5), manifest, side tables, bit-exact round-trip on every fixture, three malformed-bundle errors. Worktree `mambo-power-m8-s5`. Owns `io/csv_bundle.py`, `tests/unit/test_io_csv_bundle.py`, its LIMITATIONS entry + codes | record/m8-s5-report.md + 1 commit | **done** (`f9bf026`, merged into `wave/08-interop`; orchestrator-verified in its worktree: 66 passed across its file + api-docs-coverage + limitations; `--stat` = module +639, warnings.py +18 (eight `CSV_*` codes), tests +394, plus an API page and one nav line — outside the stated ownership but required by `test_api_docs_coverage`, S1's precedent). Bit-exact `==` and `array_equal` on 14 networks; sabotage 1 (`.12g` floats) reddened 4, sabotage 2 (int-coerced ids) reddened 20 through `Zone.id "1"`. One documented limit: an optional string field holding `""` refuses to dump rather than read back as `None`. The bundle carries the native schema version, no separate one. `io/__init__` re-export deferred to S6 (single owner of shared files) |
| m8-s6-docs | implementor | S6: `formats.md` sections for all four formats, `LIMITATIONS` registration of the four `CODES` tuples (A18 second half), `io/__init__` re-exports, `io-pandapower-json` API page, `model.md` `Branch.kind` prose, `examples/13_interop.py` + index, changelog, architecture, roadmap; F1/A19 shifter limitation under every importer; F2/F3 notes. Works in the wave worktree on `4ebb2bc` | record/m8-s6-report.md + 5 commits | **done** (`4f536cb` registrations + re-exports + last API page, `45828c3` formats.md +458, `7baacf3` model.md, `953ad21` example 13 + index, `b01e432` changelog/architecture/roadmap). `LIMITATIONS` references the four `CODES` tuples, so the registered set equals their union by construction (A18 closed); registry placed at the bottom of `report.py` to break the import cycle, verified for every entry order and with pandapower/pypsa blocked. mkdocs strict exit 0; 95 passed across the five docs tests; 13/13 examples. Its note that `architecture.md` still listed `market.agents` under "Later waves" (an M7 leftover) was fixed by the orchestrator as `7ec0b0b` |
| m8-walk | walker | Step 5 walk at `7ec0b0b` from `formats.md`/`model.md`/API pages/example 13 only; forbidden `.bionic/` and `tests/`; artifact machine-checked for zero `AC-[0-9]` | record/m8-walk.md | **done** (8 surprises / 8 friction; verdict: solid interchange layer whose manual is a few sentences behind its behaviour on the edges a user meets when something is not case14) → F5 |
| m8-audit | auditor | Step 5 audit at `7ec0b0b` from archives: per-criterion discharge with own sabotage/recomputation, coverage verdict, revert-and-watch, hygiene; forbidden the slice reports | record/m8-audit.md | **done** (8/0/0, COVERED; 0 blocking, 2 should-fix → F4 and the matrix discharge, 5 notes) → F6 |
| m8-critic | critic | Step 6 five-axis review of `15e71fa..7ec0b0b` from an archive; unit-conversion and untrusted-input hunts named in the brief | record/m8-critic.md | **done** (not merge-ready: 3 blocking / 7 should-fix / 6 nits) → F7; fixes to S8 |
| m8-s7-walkfix | senior-implementor | S7: the walk's findings (F5) — `gen_cost_coeffs` guard for `cost=None`, PyPSA unrated-`s_nom` report code, `tap_pos` 0 not NaN, RAW `UNTERMINATED_SECTION` location, CSV blank lines + BOM, docs corrections. Own worktree `mambo-power-m8-s7` on `wave/08-interop-s7` off `3f2a9a0` | record/m8-s7-report.md + 7 commits | **done** (`dcbeb5e` `MissingCostError` — the previous agent's diff was mid-sabotage (`pass  # SABOTAGE` where the raise belongs), caught by reading it; nothing in 1144 unit + 113 parity tests relied on cost-less pricing at zero; `jobs` → `VALIDATION`; `c46c063` `PYPSA_UNRATED_S_NOM_DEFAULTED` — case14's 20 unrated branches now report, so the doc example's report grew from 2 codes to 3, honestly; `591f458` fix 3 **deviation accepted**: pandapower's own case14 stores a neutral tap as `tap_side None`/NaN, which is what mambo writes, and the A16 round-trip test proved `from_ppc`'s encoding would break it — docs corrected instead; `d3ca8d4` `UNTERMINATED_SECTION` names the right section and line via the terminator comments; `044b8a9` utf-8-sig read + blank-line skip narrowed so `,,,,` is still a row; `172eb68` docs; `b56e9aa` the audit's two hygiene items). Merged into `wave/08-interop`; orchestrator-verified: 333 passed across seven affected files, every commit carries source |
| m8-s8-criticfix | senior-implementor | S8: the critic's B1–B3 (PyPSA transformer `b` factor, `tap_changer_type`, `Branch.kind` promotion on mutation), S4 bulk export, S6 `gen.slack`, S7 atomic CSV dump, S9 registry to `io/limitations.py`, S10 no `res_bus`, four nits with new codes. Works in the wave worktree on `a78db18` (only agent there) | record/m8-s8-report.md + 11 commits | **done** (`36e8398` B1 admittance factor with a `b≠0` parity test; `9e2c9b3` B2 all four `tap_changer_type`s against `net._ppc`, `TAP_CHANGER_TYPE_UNSUPPORTED`; `df51ee8`+`738dcf8` B3 promotion + `Branch.is_transformer`, exporters route on it, mutation round-trip test; `1f442d6` S10 `res_bus` neither read nor written; `841fb46` S4 bulk creators — case300 export 3062 → 112 ms, `nets_equal` to the per-row form, column *order* differs (pandapower's creators) and is documented; `c6f9894` S6 `GEN_SLACK_PROMOTED`; `c5070ac` S7 atomic dump via staging dir + `os.replace`; `53b084a` S9 registry to `io/limitations.py`, `report.py` imports no format, eight import orders with pandapower/pypsa blocked as a test; `e2d6da8` nits incl. `PYPSA_COST_NONCONVEX`). Orchestrator-verified: 237 passed across six affected files, every commit carries source. One process slip it reported itself (a `cp` restore briefly reverted a file mid-work; re-applied before commit). Two accepted deviations: S4 is `nets_equal`-identical not byte-identical; example 13's report lines changed honestly (more codes, more issues) |
| m8-reaudit | auditor | Re-audit at `e2d6da8` from archives: AC-1..AC-8 re-discharged, every walk/critic fix verified against its finding, revert-and-watch, coverage verdict | record/m8-audit.md (appended) | **done** (8/0/0, COVERED; 2 should-fix — spec AC-6 letter, dead assertion) → F10 |
| m8-recritic | critic | Re-review at `e2d6da8`: all 16 first-pass reproductions re-run, the fixes attacked for the regression class | record/m8-critic.md (appended) | **done** (merge after 17–22; no blockers) → F9; fixes to S9 |
| m8-s9-recriticfix | senior-implementor | S9: re-review should-fixes 17–22 (+ nits 23–24 if cheap) in the wave worktree on `e2d6da8` | record/m8-s9-report.md + 7 commits | **done** (`a676800`–`5baa223`; F11: its bookkeeping phase never ran — no report, no completion message, consistent with F8's restart pattern — the deliverable phase was clean and complete: worktree clear, seven commits with a full progress log. Orchestrator re-verified independently rather than trusting the log: 1218 unit passed, ruff/format/mypy clean, and wrote the report itself from the commits + progress lines, marked as such). Closes should-fixes 17–22 and nit 24: `tap_neutral`/`tap_pos` NaN → no tap, reported; legacy `tap_phase_shifter` files import the tap pandapower 3.3 still applies; `tap2_*` composed; CSV dump swaps at the directory level; the dead `or True` assertion dropped; dumps write the promoted `kind`; changelog `Changed` bullet for `MissingCostError` |

## Findings the review layers caught

**F1 — pre-existing: `opf.dc_opf` mis-models phase shifters in its flow rows (found by S3,
verified by the orchestrator on the clean main checkout, 2026-08-30).** The flow-row constant is
`pf_shift_mw − PTDF @ fixed_bus_mw` (`dc_opf.py:906`): the shifter's equivalent bus injection is
never redistributed through the PTDF, where the DC model (MATPOWER `makeBdc`/`dcpf`) is
`flow = PTDF @ (P_inj − p_shift_bus) + pf_shift`. On a 3-bus loop (x = 0.1 everywhere, 100 MW at b1
to a 100 MW load at b2, `t12` a ±5° shifter, dispatch identical): `pf.solve_dc` gives `t12` =
95.755 / 37.578 MW (S3 matched PyPSA `lpf()` to 1e-9); `solve_dc_opf` reports 153.933 / −20.600 and
its `l23`/`l13` do not move with the shift at all — KCL at b2 reads 187.3 and 12.7 MW against a
100 MW load. At 0° the two agree exactly. Consequence: rating rows on shifter networks bind at the
wrong flow (S3's 70 MVA fixture is declared `Infeasible` at −5°), and the derived-flow sites that
share the formula (`opf/__init__.py:152`, `market/_clearing.py`) inherit it. No bundled MATPOWER
case carries a shifter, so M3's parity never saw it. **Outside M8's locked shape** (a solver
formulation, not an interchange item): recorded here and raised to the user as a scope decision.
**Ruling (user, 2026-08-30): a dedicated `bugfix · audited · task` on `epic/01-foundation`
immediately after the M8 merge** — one formula change at `dc_opf.py:906` plus the two derived-flow
sites, a shifter fixture, parity vs `pf.solve_dc` and PyPSA `lpf()`; M8's shape stays locked. Carried
as **A19** and into `continuation-m8.md` as the first item. S3 continues; its AC-3
parity is shift-free by PyPSA's own limitation (1.2.4 `optimize()` ignores `phase_shift`), and it
tests the shift's sign against `n.lpf()` instead.

**F2 — spec A6 was false as literally stated (S2, A16).** Strict `pp.toolbox.nets_equal` on our
export re-imported holds only on `poly_cost`/`pwl_cost`; `bus`, `ext_grid`, `gen`, `sgen`, `load`,
`shunt`, `line`, `trafo` fail on `name` (`None` vs our ids), dtype (`bus.name` int vs str,
`bus.zone` 1.0 vs `"1"`), default-column sets (`create_*` vs `from_ppc`), and 5e-13 float noise on
`vk_percent` — **never on a carried value**, all of which survive at 1e-12. No tolerance was added:
the holding set is pinned in the test so any drift is visible, and AC-2 and A6 are amended to say
what was measured.

**F3 — AC-3's 1e-4 MW dispatch tolerance does not hold on case118 (S3): 1.87e-3 MW on `gen-5`.**
Diagnosed as the oracle, not the mapping: both dispatches balance 4242.0 MW, every case118 cost is
strictly convex, the exact polynomial puts mambo's point 1.6e-7 $/h *below* PyPSA's, HiGHS reports a
1.1e-6 primal-dual objective error, and tightening its tolerances or switching algorithm leaves the
residual to the last digit (1e-10 returns `internal_solver_error`). M3's `test_opf_vs_pypsa.py`
measured the identical figure on its ppc-built oracle. AC-3 amended: 2e-3 MW on case118 only,
documented in the test file.

**F4 — the first named sweep at `7ec0b0b` (06:26Z): 1429 passed / 4 skipped / 1 failed — example
13 at the example runner's 60 s hang guard.** Reproduced alone (65.9 s) and timed print by print:
49 s in-process — pandapower's cold import plus first `from_json` 24 s, `pp.networks.case14()`
7 s, PyPSA export + `optimize` 13 s — plus interpreter start-up in the subprocess. S6's 15/15 was a
warm-cache run. Not a defect in the example: it is the cost of running two external engines, which
is the example's whole point. Fixed at the layer it lives — the runner's budget is now per script
(`BUDGETS_S = {"13_interop": 240.0}`, still a hang guard) and the examples page says why 13 takes a
minute (`3f2a9a0`; 15/15 with the new budget, 90.75 s for the file). ruff, format, mypy, mkdocs were
all clean at `7ec0b0b`. Sweep retaken at `3f2a9a0`. The walk, audit and critic dispatched at
`7ec0b0b` remain valid: the delta is one test file and a docs paragraph.

**F5 — the walk (`record/m8-walk.md`, at `7ec0b0b`, 0 hits of `AC-[0-9]`, 8 surprises / 8
friction) found three doc sentences that say the opposite of what happens, two of them behaviour:**
(1) a cost-less RAW import runs `opf.solve_dc_opf` to `Optimal` at objective 0.0 with all 259 MW on
the slack, and `market.solve_nodal` likewise — spec A3 assumed "the existing validation" refuses a
generator with `cost=None`; **no such validation exists**, `gen_cost_coeffs` prices it at zero
silently (the silent-default class again); (2) a phase-shifted network makes `solve_dc_opf`
*Infeasible* (empty rows) on a generously rated loop, not merely "wrong" as four `formats.md`
sections say (F1 is still the same defect; the sentence understated it); (3) an unrated branch into
PyPSA becomes `s_nom = 1e5` with no report entry, against the page's own D1 rule (pandapower's
analogous trafo default *is* reported). Smaller: nominal-tap trafo exports `tap_pos = NaN` not 0;
`UNTERMINATED_SECTION` names the wrong section/line when the bus terminator is missing; the CSV
loader counts trailing blank lines as rows and refuses a UTF-8 BOM as `﻿id`; pandapower import
sets slack `vm_pu`/`va_deg` from `ext_grid` undocumented. Held: every conversion left the input
`Network` unchanged and mambo printed/logged nothing (fresh-process check). All to S7 in its own
worktree off `3f2a9a0`; (1) is fixed at the layer it lives — a guard in `gen_cost_coeffs`, which is
the design's own claim (A3) made true, not a formulation change.

**F6 — the independent audit (`record/m8-audit.md`, at `7ec0b0b`, from archives, nothing run in a
checkout): 8 DISCHARGED / 0 PARTIAL / 0 REFUTED; wave coverage verdict COVERED** (every W has a
criterion, every criterion an inbound citation, the ownership table's citations resolve, A1–A8
re-observed, the F2/F3 amendments reproduced independently — `nets_equal` = {poly_cost, pwl_cost}
with ULP-only value noise; case118 residual 1.867e-3 MW with mambo 1.6e-7 $/h cheaper). Nine
sabotages (one per criterion, a `Branch.kind` revert-and-watch, RAW kind-from-record) each
reddened exactly the named test. Should-fix 1 = F4 (already fixed at `3f2a9a0`, with the measured
per-script budget it asked for). Should-fix 2: **the plan's matrix rows were still "(pending)" at
the audit** — the evidence existed but the gate artefact did not carry it; discharged by the
orchestrator below once the `3f2a9a0` sweep is in. Notes to S7: the carried-values parity test
`continue`s on a missing column (a dropped column could never fail it); a bare `pytest.raises`.
Notes kept as notes: the pinned `nets_equal` set cannot see value drift (the carried-values test is
what does — the docstring oversells); PyPSA's own logger chatters during `to_network` (mambo emits
nothing); `test_io_limitations` is one-directional (the auditor verified CODES == registry == emitted
for all four modules).

**F7 — the critic (`record/m8-critic.md`, at `7ec0b0b`, from an archive; repros in
`scratchpad/m8-critic-exp/`): NOT merge-ready — 3 blocking, 7 should-fix, 6 nits.** Blocking, each
demonstrated: (1) `io/pypsa.py:185` scales a transformer's `b` by `s_nom/base_mva` instead of its
inverse — PyPSA `pf()` gives vm 0.9798 vs mambo 1.0053 on a 2-bus case, exact once fixed; hidden
because every fixture transformer has `b = 0`; (2) `io/pandapower_json.py:511–521` applies `tap_pos`
regardless of `tap_changer_type` — pandapower 3.3 ignores the tap when it is `None` (the
`create_transformer_from_parameters` default), so mambo imports 1.05 where pandapower's ppc has 1.0,
AC vm differs by 0.048 pu, no report entry; symmetrical/ideal changers also mis-mapped; (3)
`model/entities.py:80–94` — `Branch.kind` is computed once in a before-validator, so after
`br.tap_ratio = 1.05` on a line the exporters silently drop the tap and `Branch.model_validate(
br.model_dump())` raises: native dumps→loads of a mutated network fails, **a pre-M8 regression** and a
direct consequence of my S1 brief's "reject line-with-tap" choice — the fix is to promote, and to
route exporters on `kind` OR a non-nominal tap. Should-fix: quadratic pandapower export (24–33 s on
case300; bulk creators); example 13's budget (= F4, fixed); `gen.slack=True` → `NO_SLACK` error
instead of a repair; non-atomic `csv_bundle.dump` (a mid-write error leaves a loadable Frankenstein
bundle); BOM (= walk, with S7); `report.py` importing the four format modules at its bottom (an
inverted dependency that works by partially-initialised-module luck — move the registry to
`io/__init__` or `io/limitations.py`); the importer reads/writes pandapower `res_bus` against the
spec's own Not-doing — an undeclared deviation to record or drop. Six nits in the artifact (two error
surfaces, `RawImportError` vs `ReportError`; RAW areas silently discarded; a few tracebacks that
should be reports; readability fat). Held under attack: every pandapower per-unit map to 1e-6
against `net._ppc`/`runpp`; RAW CZ/CW/CM combos not in the fixtures; three real pandapower networks
(`mv_oberrhein`, `example_multivoltage`, `cigre_mv`) import cleanly; no `eval`/`pickle`, no
input-derived paths. All to **S8** on S7's merged head (the two overlap on `pypsa.py`,
`pandapower_json.py`, `csv_bundle.py`, `formats.md`).

**F8 — a Claude Code restart killed the sweep at `3f2a9a0` after `ruff format` and the first S7
agent mid-fix-1** (six files modified, nothing committed, no progress line). Partial sweep figure of
record-in-waiting: pytest **1430 passed / 4 skipped in 546.50s**, ruff check and format clean; mypy
and mkdocs not reached. S7 relaunched with its own uncommitted diff as the starting point and an
instruction to commit early. Rule added to briefs: commit at every self-contained sub-deliverable.

**F9 — the critic's re-review at `e2d6da8` (`record/m8-critic.md`): merge after should-fixes 17–22;
no blocker survives.** First-round status: 11 FIXED with output, B3 FIXED DIFFERENTLY and accepted
(promotion + `is_transformer`), atomic dump PARTLY fixed, three nits standing; the nominal-tap NaN
encoding and `nets_equal`-not-byte-identical bulk export accepted as rulings. Its suite run on an
archive: 1494 / 4 / 0; example 13 now 8.5 s; case300 export 24.3 s → 333 ms on its machine. New:
(17) `tap_neutral` NaN — pandapower's own default — with a `Ratio` changer: mambo applies tap 1.05,
pandapower none (vm 0.945 vs 0.993), unreported; (18) pandapower ≤2.x files carry
`tap_phase_shifter` and no `tap_changer_type`, and pandapower 3.3 still applies the tap through
its deprecation branch while mambo imports nominal and the message claims otherwise; (19) a
`tap2_*` second changer silently ignored; (20) the CSV dump's per-file `os.replace` loop can fail
mid-way on Windows (read-only file, Excel holding one open) and leave a *loadable* mixed bundle plus
an orphan temp dir; (21) `test_bulk_export_is_byte_identical…` ends in `assert … or True` — a check
that cannot fail under a name that claims it can, the F16 class in a test; (22) `MissingCostError`
is a behaviour change outside `io` missing from the changelog, and the spec's assumptions lack this
round's rulings. Held under attack: every other tap formula against `_calc_tap_from_dataframe`,
`kind` leaks via every construction path, `b` with the `s_nom` sentinel, `MissingCostError`'s
callers, import order with pandapower/pypsa/pandas blocked, `GEN_SLACK_PROMOTED` edge cases. All
to **S9** in the wave worktree; the spec's assumptions are the orchestrator's.

**F10 — the re-audit at `e2d6da8` (`record/m8-audit.md`, appended): 8 DISCHARGED / 0 PARTIAL /
0 REFUTED, wave COVERED; 0 blocking, 2 should-fix, 5 notes; archive suite 1494 / 4 / 0.** Every walk
and critic fix verified on the auditor's own inputs (PyPSA trafo `b`: `pf()` vs `solve_ac` to 2e-16;
all four `tap_changer_type`s against `net._ppc`; 26 import orders with pandapower/pypsa/pandas
blocked; 14 sabotages each reddening exactly the guarding tests). Should-fix 1 is the spec's own
letter: AC-6's "every pre-M8 test unmodified" stopped being literally true when the walk's
`MissingCostError` fix inverted the pre-M8 "cost-less generator is free" test — amended in the spec
(AC-6 + A9) by the orchestrator; changelog bullet with S9 (#22). Should-fix 2 = the critic's #21
(the dead `or True` assertion), with S9. Notes: the dump is atomic up to the per-file move-in (= the
critic's #20, with S9); `UNTERMINATED_SECTION` location relies on the `END OF` comments; a mutated
network is not `==` its round-trip (kind promoted — by design); the plan's "nets_equal to the per-row
form" is true against the test's reference, not against the pre-S8 file (column order, `res_bus`).

**F11 — S9's bookkeeping phase never ran (no report, no completion notification), the second
instance of F8's restart pattern this wave.** Its deliverable phase was intact: a clean worktree,
seven commits, a complete progress log at `.bionic/tmp/m8-s9-progress.md`. The orchestrator did not
trust the log — re-ran `tests/unit`, ruff, format and mypy independently against the final commit
before writing the report itself. Two-restart pattern across M7 (F17) and M8 (F8, F11) says the
brief's "commit at every self-contained fix, progress lines per commit" instruction is necessary
but the report-gate discipline needs a cheaper fallback: **the orchestrator writing the report from
verified re-execution, never from an agent's self-report alone, is now the standing recovery — not
an exception**.

## Assumptions

Design assumptions A1–A8 live in the spec. Process assumptions, binding from Step 4:

- **A11** — baseline is taken on the clean main checkout before any agent enters the worktree
  (M7 A14); the wave worktree is `C:/Claude Projects/mambo-power-m8` on `wave/08-interop` from
  `cdb4fef`, removed at Step 8 with `git worktree remove --force` (M7 F20 — never `rm -rf`).
- **A12** — one agent in the worktree at a time per file set; S2–S5 own disjoint files; measurement
  from `git archive` overlays with `__file__` proven (M7 A16).
- **A13** — every slice commit's `--stat` is checked against the brief's file list before its
  report is believed (M7 F16); agents are stopped on hand-back (M7 F17); briefs say never amend.
- **A14** — the walk is dispatched first at Step 5, from `formats.md` and the example only,
  forbidden the spec/plan/reports, artifact machine-checked for zero `AC-[0-9]`.
- **A15** — `.bionic/docs/` is committed with each checkpoint commit (it is tracked since
  `7f396be`); `.bionic/tmp/` stays ignored and is wiped at Step 8 after evidence moves to `record/`.
- **A16 (at risk, from spec A6)** — `nets_equal` on our export re-imported: S2 measures it first
  and reports the exact table set on which it holds; if it fails on a carried table, that is a
  finding, not a tolerance.
- **A17** — S2–S5 each work in their own worktree on a slice branch off `a51250f`
  (`wave/08-interop-s2..s5`), not in the wave worktree: four agents sharing one git index was the
  shape behind M7's A14–A17 incidents. The orchestrator merges each slice branch into
  `wave/08-interop` on verification (disjoint files → clean merges) and removes the slice worktree
  with `git worktree remove --force`.
- **A18 (split finding, both halves owned)** — the `test_io_limitations` docs-coverage test reads
  `docs/manual/formats.md` and `LIMITATIONS` in `io/report.py`; four slices editing one file in four
  worktrees would conflict, so **S2–S5 expose `CODES` at module level and list them in their
  reports** (their half), and **S6 registers all four in `LIMITATIONS` and documents every code in
  `formats.md`** (its half); the orchestrator checks at the final head that the union of the four
  `CODES` equals the registered set. Until S6 lands, the test is green only because unregistered
  modules are not covered — that is the tracked gap, not a passing check.
- **A19 (carry, ruled)** — the `opf.dc_opf` phase-shifter flow defect (F1) is fixed as a standalone
  bugfix task immediately after M8 merges, not inside M8; until then any imported network with a
  non-zero `shift_deg` has wrong `opf`/`market` branch flows, and `formats.md` says so under each
  importer's limitations (S6).

## Handoff

**Shipped 2026-08-30.** Wave head `33abd13` (~40 commits across S1–S9), merged `--no-ff` as
`511c6a0` on `epic/01-foundation`, unpushed (the user's call, as M1–M7). Final sweep 1513 / 4, all
gates clean. Audit 8/0/0 COVERED at two heads; critic clean after two full passes; walk's 8
surprises fixed. ADR-011 in `docs/design/decisions.md`. Carries and lessons for M9 in
`record/continuation-m8.md`. Eleven findings (F1–F11), nineteen assumptions (A1–A9 design, A11–A19
process), spec AC-2/AC-3/AC-6/S1 corrected in place, one carried defect (F1/A19, the phase-shifter
flow bug — a standalone bugfix task, first in line for M9).
