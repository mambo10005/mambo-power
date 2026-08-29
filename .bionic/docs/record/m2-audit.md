# M2 audit — Step 5 exit gate (coverage · power · authenticity)

Auditor: m2-auditor (fresh, read-only; implemented nothing in M2). Written 2026-08-20 22:10 PDT
(2026-08-21 UTC). Wave head `502dc1b` in worktree `C:\Claude Projects\mambo-power-m2`
(`git status --porcelain` empty before and after every command below; all pytest runs with
`-p no:cacheprovider`; `mkdocs build` was pointed at a scratchpad `-d`, never at the worktree).
`uv` = `C:\Users\mambo\AppData\Roaming\Python\Python314\Scripts\uv.exe`.

Inputs held: wave spec (W1-W10, AC-1..10, Design 1-8), epic spec §Design, plan (matrix, per-AC
evidence, ledger, A1-A12), record/m2-research.md (+ erratum), m2-s1..s7-report.md,
m2-step5-tests-floor.md, CI via `gh`. Every factual claim here carries its command + output or
is labelled `unverified`.

## Headline

**Wave verdict: REFUTED as "implemented and proven" on two rows, with the substance intact.**
Every solver claim I re-executed reproduces (AC parity 37/37 at machine precision, the unit
batch 51/51, `mkdocs build --strict` exit 0, CI 8/8 on 502dc1b, case300 cold 0.0400 s in the CI
log). The two refutations are proof gaps, not behaviour defects:

1. **AC-8** — the API reference does not list `pf.ac_newton`'s public symbols (`newton`,
   `newton_raphson`, `flat_start`, `specified_injection`, `allocate_generation`,
   `BUS_TYPE_CODE`, `SOLVER`); `docs/api/pf.md` has no `::: mambo_power.pf.ac_newton` block.
   Design item 1 names `pf.ac_newton.newton(arr, opts)` as a public entry point.
2. **AC-5** — the clause "the solve then matches pandapower on the main island" has no test;
   the matrix's claim that "the S4 parity path" covers it is false (the fixture is not in
   `CASES`). My own probe shows the clause is *true* (8.9e-16 pu), so this is an unproven-not-
   broken finding; a durable test is one fold item away.

Plus one **coverage hole** (W7 has no inbound design citation and its sha256/licence clause has
no criterion — evidence exists only in S1's test) and three letter-vs-substance deviations
(AC-4, AC-7, AC-9) that the fold should settle by amending wording or code. The
revert-and-watch demonstration (Q-limit pin logic stubbed → exactly the predicted 28 checks red,
99 green) is **VALIDATED** (§2b). The Step-5 walk artifact never landed during my window, so its
AC-identifier check is **UNVERIFIABLE** (§5a).

---

## 1. Coverage — requirement → design decision → criterion → evidence

### Mechanical seed (inverted citation maps)

Inbound citations to each W from the spec's `provenance:` lines (AC-n) and from the Design
items' parenthetical references:

| Req | Design items citing it | ACs citing it | Inbound = 0? |
|---|---|---|---|
| W1 | 1 (Solver API), 3 (Q-limits) | AC-1, AC-2 | no |
| W2 | 1 | AC-3 | no |
| W3 | 2 | AC-4 | no |
| W4 | 4 | AC-5 | no |
| W5 | 5 | AC-6 | no |
| W6 | 6 | AC-6 | no |
| **W7** | **none** (item 7 cites "AC-1, D4", not W7; its text mentions "case300 qlim-off + DC + timing" only) | AC-7 (timing clause only) | **design: yes** |
| W8 | 8 | AC-8 | no |
| W9 | 8 | AC-9 | no |
| W10 | 8 | AC-10 | no |

Command: `grep -nE "provenance: W|\(W[0-9]" wave-02-power-flow.spec.md` (spec lines 98-143 and
150-183; read in full above).

### Chain walk with judgment

| Req | Design | Criterion | Evidence (file · test · record) | Chain status |
|---|---|---|---|---|
| W1 AC-NR (sparse, splu, 1e-8, 20 iters, flat/warm, pandapower Q-limits) | 1, 3, 7 | AC-1, AC-2, AC-7 | `pf/ac_newton.py`; `tests/parity/test_ac_vs_pandapower.py` (37), `test_ac_vs_matpower_stored.py` (10), `tests/unit/test_pf_ac_newton.py` (21); S4 report | Whole. Warm start is covered by unit tests (`test_warm_start_from_its_own_solution_is_immediate`, `test_solve_ac_auto_init_warm_starts_from_stored_state`) but by no AC — letter gap, substance present. "Slack never limited" is structural (`newton` inspects only `pv`) and asserted at `test_pf_ac_newton.py:285`. |
| W2 DC (B'θ = P, phase-shift injections, Bf flows) | 1 | AC-3 | `pf/dc.py`; `test_dc_vs_pandapower.py` (21), `test_pf_dc.py` (12); S3 report | Whole. |
| W3 effective roles | 2 | AC-4 | `numerics/roles.py`; `test_effective_roles.py` (10), `test_roles_vs_pandapower.py` (3), `test_pf_ac_newton.py::test_effective_roles_are_honoured_on_case14_roles`; S2 | Whole; see AC-4 note in §4 ("matches pandapower" is proven at role level, and a numeric match is impossible by construction on the combined fixture). |
| W4 islands | 4 | AC-5 | `model/islands.py`, `io/report.py`; `test_islands.py` (12); S2 | Design and criterion present; **one criterion clause unproven** (§2 AC-5). |
| W5 results + provenance, never on Network | 5 | AC-6 | `results/*`; `test_results_models.py` (14); S3 | Whole. "Never stored on the Network" has no test; it is structural (`Network` is `extra="forbid"`, `unverified` by me — I did not re-run the schema test). |
| W6 jobs | 6 | AC-6 | `jobs/*`; `test_jobs.py` (24); S5 | Whole. |
| **W7** case300 verbatim + sha256 + provenance/licence; modified case14 | **none** | AC-7 covers only timing; AC-4/5 consume the derived fixtures | `tests/unit/test_fixture_case300.py::test_bytes_are_the_recorded_upstream_blob` (sha256/size), `test_fixtures_derived.py` (9); S1 §1, §5; `fixtures/matpower/PROVENANCE.md` | **Hole**: no design decision and no criterion for the verbatim-bytes / sha256 / licence-caveat clause. Evidence exists (S1's test, re-executed by the floor inside the 484) but the matrix cannot express it. Wave-level finding below. |
| W8 docs substrate | 8 | AC-8 | `docs/`, `mkdocs.yml`, `ci.yml` docs job, `pages.yml`; floor §5; S6/S7 | Design + criterion present; **criterion refuted on the API-reference clause** (§2 AC-8). |
| W9 examples | 8 | AC-9 | `examples/01..07`; `test_examples_run.py` (9); CI `examples` job | Whole; embedding is in the Examples gallery page, not "a manual page" (letter deviation, §4). |
| W10 docstrings | 8 | AC-10 | `tests/unit/test_docstrings.py`; S6 planted-miss proof | Whole. |

Epic-level note: the wave header names R2, R9, R10, R14. R9 ("own solvers; pandapower dev-only")
is cited by no W; it is carried by M1's install-smoke job (floor §7: the wheel's venv holds
numpy/scipy/pydantic/highspy only). Not a wave hole, recorded for the epic audit.

**Uncovered list (wave-level):** W7's verbatim-bytes / sha256 / licence clause — requirement
with zero design citations and no criterion. Recommended fold action: add a design line to
item 7 ("fixtures: verbatim upstream bytes, sha256 pinned by test, licence caveat in
PROVENANCE") and either a criterion or an explicit "covered by test_fixture_case300, no AC"
note in the matrix.

---

## 2. Power — what would the observation have shown had the change been absent?

| AC | Observation | Counterfactual (change absent) | Paired positive case? | Power |
|---|---|---|---|---|
| AC-1 | 37 parity cases ≤ 4e-14 pu vs runpp; stored columns within 2e-3/0.5 with pinned residuals | No solver → `ImportError` (S4 RED recorded). Wrong solver → 1e-6 band fails (the case300 tap-side story shows it did: 0.107 pu at bus 17 before the oracle fix). | Yes — nonzero residuals pinned per fixture (`MEASURED_RESIDUAL`). | Strong |
| AC-2 | pin sets equal pandapower's on ieee30/118/300-on; hand Qmax/Qmin pins; bus-103 negative pair | Pinning absent → ours `{}` vs theirs `{bus-2: max}` etc.; the bus-103 "on" value would equal the "off" value (9.0e-3 breach). | Yes — the negative pair is itself the positive/negative pairing. **Revert-and-watch targets exactly this** (§2a). | Strong |
| AC-3 | DC ≤ 3.3e-12 deg / 3.5e-12 MW vs rundcpp on 6 fixtures | No `pf.dc` → `ModuleNotFoundError` (S3 RED). Wrong phase-shift handling → hand 3-bus phase-shifter test vs dense solve fails. | Yes. | Strong |
| AC-4 | bus-6 effective PQ (declared PV); bus-2 takes 1.055 + warning; noslackgen raises | No demotion → bus-6 held at 1.07 (test asserts `abs(vm−1.07) > 1e-3`); first-wins → 1.045 (test pins both numbers). | Yes — declared-vs-effective asserted on the same bus. | Strong for roles; **"matches pandapower" is role-level only** (§4). |
| AC-5 | repair yields 13 live buses, one `ISLAND_DEACTIVATED` (bus-8, gen-5); `load` silent; direct `Network` raises | No repair → `load_with_warnings` raises `DISCONNECTED_BUS` — S1's original test asserted exactly that and S2 recorded its flip (RED). | Yes. | Strong for repair. **"solve matches pandapower on the main island": no observation exists in the suite** — power zero by absence. Auditor probe (below) supplies one. |
| AC-6 | JSON round-trip; version equality; run×2 equal mod timing; invalid network → `failed`; KINDS contract | Impure `run` → second-run warning swallowed (S5 found and fixed exactly this via `simplefilter("always")`); unwrapped exception → test fails. | Yes (`test_result_type_must_match_the_kind`, failure codes enumerated). | Strong |
| AC-7 | CI log `case300 AC cold 0.0400 s` (502dc1b), `0.0419 s` (e1e7e4f) | Slow solver → `assert cold_s < 1.0` fails with the figure in the message. | Yes — a nonzero measured number, not a zero readback. | Adequate (threshold is loose; the figure is what matters and it is recorded). |
| AC-8 | `--strict` exit 0; 21 pages; mermaid ×2 + classDiagram ×2 | Missing page → nav warning → non-zero under `--strict`. **Zero-readback ("0 warnings") paired** with my positive probes: 210 symbol anchors on api pages, 2 mermaid, 2 classDiagram. | Yes (mine). | Adequate for build/IA/diagrams; **powerless for "every public symbol"** — nothing checks it, and it is false for `pf.ac_newton`. |
| AC-9 | 7 scripts exit 0 in CI; embed asserted per script | Script error → exit ≠ 0; un-embedded script → `test_examples_run` fails (S7). | Yes. | Strong |
| AC-10 | 0 offenders | Planted-miss proof: 4 removed docstrings → 4 named offenders (S6). | Yes. | Strong |

### 2a. Revert-and-watch (durable, whole-change demonstration)

Request written 22:03 at `.bionic/tmp/m2-audit-revert-request.md`. Target: **M2's Q-limit pin
logic** — `src/mambo_power/pf/ac_newton.py::newton` lines 289-290 stubbed to
`over = pv[:0]; under = pv[:0]` (violators never detected; everything else intact).
Predicted RED: 5 unit hand-case tests, all parity tests on `case_ieee30-qlim-on`,
`case118-qlim-on`, `case300-qlim-on` + `test_at_least_one_fixture_pins`,
`test_case118_without_q_limits_breaches_at_bus_103`,
`test_matches_stored_columns_outside_the_exclusions[case118]`. Predicted GREEN: `case14-qlim-on`,
`case57-qlim-on`, `case300-qlim-off` rows, `q_limits=False` tests, timing, jobs, examples, DC.

Capture: `record/m2-revert-watch.md` (landed 22:2x; throwaway worktree `mambo-power-audit2`
removed; m2 worktree never entered — `git -C …m2 status --porcelain` empty, HEAD 502dc1b before
and after).

### 2b. Revert-and-watch validation — **VALIDATED**

1. **Change really absent.** Recorded `git diff` is byte-identical to my §diff: 1 file,
   2 insertions, 2 deletions, lines 289-290 of `ac_newton.py` replaced by `pv[:0]`; base
   `git rev-parse HEAD` = 502dc1b, `git status --porcelain` empty before the stub; restored with
   `git checkout --`, porcelain empty again, unit file re-run green (21 passed).
2. **Checks the matrix leans on.** The red set is exactly AC-2's tier-run
   (`test_pinned_buses_match_runpp` ×3, hand Qmax/Qmin/no-restore cases, bus-103 negative pair)
   plus the qlim-on half of AC-1's parity (`case_ieee30/case118/case300-qlim-on`, all six tests
   each) — 28 failures, all on M2 code.
3. **The red is the failure I predicted.** Every named predicted-RED test failed (5 unit, 19
   parity, 2 stored-column); the assertion payloads are the predicted ones —
   `test_pinned_buses_match_runpp[case118-qlim-on]`: `('case118', {}, {'bus-19': 'min',
   'bus-32': 'min', 'bus-34': 'min', 'bus-92': 'min', 'bus-103': 'max', 'bus-105': 'min'})`;
   `test_case118_without_q_limits_breaches_at_bus_103`: `abs(1.0099999999999996 − 1.001) =
   0.008999999999999675 > 0.002` (predicted 9.0e-3 at bus 103); `test_q_max_pin`: `assert 0 == 1`
   on `q_limit_rounds`. The "likely red, not staked" slack-generation tests went red ×3. No
   predicted-GREEN test went red: the other 16 unit tests, all 18 parity tests on
   `case14-qlim-on` / `case57-qlim-on` / `case300-qlim-off`, the case14/case57 stored rows, the
   two self-consistency tests, timing, jobs (24), examples (9) and DC parity (25) — 99 passed.
4. **Direction-not-predicted items resolved:**
   `test_matches_stored_columns_outside_the_exclusions[case_ieee30]` RED at
   `('case_ieee30', 'bus-2', 0.0020000000000000018)` — without the bus-2 pin the solved Vm sits
   at the band edge (2e-18 over), a genuine but hairline breach;
   `test_exclusions_sit_where_the_data_are_worst[case_ieee30]` RED (excluded bus 3 at 0.86 of the
   band is no longer the worst once bus 2 drifts); `[case118]` GREEN. All three consistent with
   the pin being absent; none unexplained.
5. **Baseline divergence ruled on.** The runner's BEFORE for command 4 was 59, not my expected
   55, because `tests/parity/test_dc_vs_pandapower.py` collects **25** tests (4 tests × 6
   fixtures + `test_oracle_is_invariant_to_the_base_kv_substitution`), verified by me:
   `uv run pytest --co -q tests/parity/test_dc_vs_pandapower.py` → `25 tests collected`;
   `git log -- tests/parity/test_dc_vs_pandapower.py` → a single commit (41e531b), so the file
   has always held 25. The "21 cases" in the plan's AC-3 row and S3's "47 new (14 + 12 + 21)"
   are the record's miscount (§5 item 5); the runner was right. 21 + 37 + 10 + 59 = 127 BEFORE,
   99 + 28 AFTER; arithmetic closes.

Verdict on the demonstration: **VALIDATED** — durable, auditable after integration, covers
the Q-limit change end-to-end (unit, parity-vs-oracle, stored-column negative pair).

---

## 3. Authenticity — evidence produced at its declared tier; ≤ 3 re-executions

Tiers used by the matrix: T1 (AC-4,5,6,7,9,10) and T2 (AC-1,2,3,8). No T3 row (no real-surface
claim), so the T3 checklist does not apply. T2 rows all carry a `fixture-fidelity:` line; the
fixtures are structurally able to reach the guarded failure (verbatim MATPOWER bytes plus
oracles that did fail before alignment — S3's case300 T-model miss and S4's tap-side miss are
recorded REDs of the oracle, which is the fidelity proof one wants). One inaccuracy: AC-8's
fidelity line names `e1e7e4f` as the wave head; the head is `502dc1b` (docs-only delta).

### Re-execution 1 (T2 · AC-1/AC-2)

```
$ uv run pytest -q -p no:cacheprovider tests/parity/test_ac_vs_pandapower.py
37 passed in 39.61s
```
Record: "37 cases" (plan AC-1 tier-run; S4 table). **Match.** Pre/post `git status --porcelain` empty.

### Re-execution 2 (T1 · AC-4/5/6/10)

```
$ uv run pytest -q -p no:cacheprovider tests/unit/test_islands.py tests/unit/test_effective_roles.py \
    tests/unit/test_jobs.py tests/unit/test_docstrings.py tests/parity/test_roles_vs_pandapower.py -v
51 passed in 37.13s
```
Record: 12 + 10 + 24 + 2 + 3 = 51 (plan AC-4/5/6/10 tier-runs; S6 says the docstring file holds
two tests). **Match.**

### Re-execution 3 (T2 · AC-8)

```
$ uv run mkdocs build --strict -d <scratchpad>/audit-site
INFO    -  Documentation built in 25.24 seconds
exit=0
pages: 21            (find -name index.html | wc -l)
mermaid on design/architecture: 2    classDiagram on data-model: 2
```
Record: exit 0, 21 pages (floor §5, plan AC-8). **Match** on build/IA/diagrams.

Symbol-coverage probe (auditor script over the built `api/` pages, `__all__` or `dir()` per package):
```
public names checked: 122   anchors in site: 210   missing (real symbols only):
  mambo_power.pf.ac_newton            (module — no ::: block in docs/api/pf.md)
  mambo_power.pf.ac_newton.newton, .newton_raphson, .flat_start, .specified_injection,
  .allocate_generation, .BUS_TYPE_CODE, .SOLVER
  mambo_power.model.GeneratorCost     (a typing alias; mkdocstrings renders no entry)
$ grep -rl specified_injection <site>/api | wc -l   -> 0   (whole site: 0)
$ grep -rl allocate_generation  <site>/api | wc -l   -> 0   (whole site: 0)
$ grep -rl newton_raphson       <site>/api | wc -l   -> 0   (whole site: 2 — manual + search index)
$ cat docs/api/pf.md  -> "::: mambo_power.pf (show_submodules: false)" + "::: mambo_power.pf.dc" only
```
`AcOptions` / `AcSolution` *are* listed (via the `mambo_power.pf` re-export). The remaining
imported names in the missing list (`np`, `splu`, `Field`, …) are `dir()` noise from a module
without `__all__`, not public symbols.

### CI readback (not a re-execution; independent log read)

```
$ gh run view 32448061526 --repo mambo10005/mambo-power --json conclusion,headSha,jobs
conclusion success · headSha 502dc1b… · 8 jobs all success (incl. "docs (mkdocs --strict)", "examples (run every script)", "install smoke")
$ gh run view --job 96671226077 --log | grep -E "case300 AC cold|passed"
484 passed, 10 warnings in 24.35s
case300 AC cold 0.0400 s, warm 0.0226 s, 5 iterations
$ (run 32447930888 / e1e7e4f, ubuntu 3.12)  case300 AC cold 0.0419 s, warm 0.0222 s, 5 iterations
$ gh run view 32445786960 (e4ed0f6)  success, 7 jobs success
```
Plan figures (0.040 s on 502dc1b; 0.0419 s on e1e7e4f; 8/8; 7/7) **match**.

### Auditor probe for AC-5's unproven clause (not one of the 3 re-executions — there was no evidence command to re-execute)

```
$ PYTHONPATH=<worktree> uv run python <scratchpad>/ac5_probe.py
issues: [('ISLAND_DEACTIVATED', ['bus-8'], ['gen-5'])]
ours converged True iters 4 rounds 0 rows 13
pp converged True
pp bus-8 result (islanded): nan nan
main-island parity: buses=13 max|dvm|=8.88e-16 pu max|dva|=4.44e-14 deg
```
(pandapower `runpp` on the same raw matrices, BASE_KV substitution, `trafo_model="pi"`,
`enforce_q_lims=True`; its own connectivity check drops bus 8.) The clause holds at machine
precision. It is **not** in the suite.

### Per-row authenticity

| AC | Tier | Declared evidence found at that tier? | Note |
|---|---|---|---|
| AC-1 | T2 | yes — fixture-fidelity, oracle alignment rules (A5, A11), RED recorded, CI readback | re-executed |
| AC-2 | T2 | yes — same module + hand cases declared synthetic | revert target |
| AC-3 | T2 | yes — RED recorded; `gh run view 32443812218` → success, headSha 41e531b, 6/6 jobs success | CI readback |
| AC-4 | T1 | yes | re-executed |
| AC-5 | T1 | partially — the pandapower-match clause has no evidence at any tier | auditor probe |
| AC-6 | T1 | yes | re-executed (jobs) |
| AC-7 | T1 | yes — CI log line read directly | — |
| AC-8 | T2 | build/IA/diagrams yes; symbol-coverage clause has no instrument | re-executed |
| AC-9 | T1 | yes — CI `examples` job success on 502dc1b | — |
| AC-10 | T1 | yes — planted-miss proof in S6 | re-executed |

---

## 4. Verdict table

| Row | Verdict | Reason (one line) |
|---|---|---|
| AC-1 | CONFIRMED | 37/37 re-executed at ≤ 4e-14 pu; stored-column bands ratified (A10) with residuals pinned; CI 8/8. |
| AC-2 | CONFIRMED | pin sets asserted against pandapower's internal post-loop types; hand Qmax/Qmin + no-restore; bus-103 pair; revert-and-watch VALIDATED (§2b: stubbing the violator detection turns exactly the predicted 28 checks red, 99 stay green). |
| AC-3 | CONFIRMED | 21 parity + 12 unit cases, RED recorded, CI green on every run since 41e531b (not re-executed by me: cap). |
| AC-4 | CONFIRMED | roles proven both sides; note: "matches pandapower" holds at bus-type level only — a numeric match is impossible on `case14_roles` by construction (bus-2 first-wins vs last-wins), so the AC wording should say "solves as PQ, as pandapower does". |
| AC-5 | REFUTED (as proven) | three of four clauses proven; "solve matches pandapower on the main island" has no test, and the matrix's "covered by S4 parity path" is false. Substance true per auditor probe (8.9e-16 pu). Fold: add the test. |
| AC-6 | CONFIRMED | 24 jobs + 14 results cases; re-executed jobs 24/24; structured-failure codes enumerated. |
| AC-7 | CONFIRMED | CI ubuntu 3.12 log: cold 0.0400 s (502dc1b), 25× under threshold; note: the docs carry a Windows figure (0.029 s) with a pointer to CI, not the CI number the AC literally asks for. |
| AC-8 | REFUTED | `--strict`, IA, diagrams, pages.yml all hold (re-executed); "API reference lists every public symbol of … pf" is false for `pf.ac_newton` (7 public names, no `:::` block). One-line fold fix + a coverage test. |
| AC-9 | CONFIRMED | 7/7 exit 0 in CI and locally; embed asserted per script; note: embedded in the Examples gallery, not "a manual page" as the AC says. |
| AC-10 | CONFIRMED | re-executed 2/2; planted-miss proof recorded. |
| **Wave** | **REFUTED** | Two rows refuted on proof (AC-5 clause untested; AC-8 symbol clause false) and one coverage hole (W7: zero design citations, sha256/licence clause has no criterion). No behaviour defect found; every re-execution matched the record. Fixable in the fold without touching solver code. |

---

## 5. Reporting-contract violations found in the record

1. **Plan, AC-5 tier-run** — "AC solve on the repaired network vs pandapower covered by the S4
   parity path (case14_roles/island not in FIXTURES — A8)": a factual claim with no proving
   command, and false — `tests/parity/test_ac_vs_pandapower.py::CASES` holds six upstream rows
   only; `grep -rn case14_island tests/` hits `test_islands.py` and `test_fixtures_derived.py`,
   neither of which calls a solver (`grep -n "solve_ac\|solve_dc\|runpp" tests/unit/test_islands.py`
   → only a docstring mention of pandapower).
2. **Plan, AC-8 tier-run** — "API ×7 (model, io.matpower, io.native, numerics, pf, results,
   jobs)" and the criterion "covers all public symbols": no command checks symbol coverage;
   S6's anchor list (its §"Rendered-site proof") predates S4, and S7's docs finish did not
   re-check after `pf.ac_newton` landed. The claim is false for `pf.ac_newton` (§3).
3. **Plan, AC-8 fixture-fidelity** — "the built site from the wave head e1e7e4f"; the ratified
   head is 502dc1b (floor: "HEAD moved under the run"). Stale, not false.
4. **S1 report §1** — the 9-bus gate list transcribed from research is correctly labelled
   `unverified`; S7 §5 then correctly left it standing with a "transcription, not re-measured"
   heading. No violation — noted as the model for how the rest should read.
5. **Plan AC-3 tier-run / S3 report** — "tests/parity/test_dc_vs_pandapower.py (21 cases)" and
   "47 new: 14 results-model, 12 pf-dc, 21 parity": the file collects 25
   (`pytest --co -q` → `25 tests collected`; one commit in its history). Harmless in direction
   (more green tests than claimed) but a factual count without its proving command; it is what
   made the revert-and-watch baseline look divergent.
6. **Walk artifact** (`record/m2-walk-docs-site.md`) — see §5a.

### 5a. Walk check — UNVERIFIABLE (not on disk)

Polled from 21:59 to 22:26 (`ls record/m2-walk-docs-site.md`, `ls record/walk-m2/`): the file
never appeared and `walk-m2/` is empty (the dispatch ledger still says `active`). The mandated
AC-identifier check (`grep -E 'AC-[0-9]'`) could not be run. The matrix's AC-8
`fixture-fidelity` and `readback` lines cite this walk as evidence; until it lands, that citation
is to an artifact that does not exist, and AC-8's browser-rendering claim rests on my
`--strict` build + page/diagram/anchor probes alone. If the walk lands later, re-run the grep
and attach the result here; a non-empty grep is a reporting-contract violation (the walker must
not have read the ACs).
