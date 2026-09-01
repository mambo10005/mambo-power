# M1 Step 5 audit — coverage · power · authenticity

Auditor: m1-auditor (fresh, independent; implemented nothing). Date: 2026-08-20.
Subject: wave M1 "substrate", worktree `C:\Claude Projects\mambo-power-m1`, branch `wave/01-substrate`,
HEAD `36bd20aefae9bd5da20ed63fac49ff53815bf0ae` (`git rev-parse HEAD`, `git status --porcelain` empty
before and after every command below). Read-only: nothing edited, committed, reverted, stubbed or pushed
by the auditor in any repo. `uv` = `C:\Users\mambo\AppData\Roaming\Python\Python314\Scripts\uv.exe`,
run from the worktree root. Every factual claim carries its command and output, or is labelled `unverified`.

Inputs held: wave spec (W1-W6, AC-1..AC-8, M1-local Design 1-7), epic spec §Design (by pointer),
wave plan (Verification Matrix, per-AC blocks, dispatch ledger, A1-A14), record files
m1-s1..s6, m1-s2-ci-proof, m1-step5-tests-floor, m1-w1-extract, m1-env-attestation, and the code.

---

## (1) Coverage — requirement → design decision → criterion → evidence

### Mechanical seed: inverted citation maps

Criteria `provenance:` → requirements: AC-1→W1 · AC-2→(none; canonical-sdlc rule + epic plan) ·
AC-3→W1 · AC-4→W2,W3 · AC-5→W3 · AC-6→W4 · AC-7→W5 · AC-8→W6.
M1-local Design items → requirements: D1→W2,W5 · D2→W2 · D3→W4 · D4→W4 · D5→W2 · D6→W2,W4 · D7→W5.

Requirements with **zero inbound citations from criteria:** none.
Requirements with **zero inbound citations from the M1-local design:** W1, W3, W6. For all three the
wave spec's `design:` pointer to the epic spec applies (W1/W6 → epic §5 "Free stack & release pipeline":
uv env/lock/build, ruff, mypy strict, pytest tiers, GHA Linux/macOS/Windows; W3 → epic §3 ownership row
"Network schema … JSON schema snapshot test; round-trip"). Design is therefore **by pointer, not waived**,
and the chain is walked requirement → governing design → criterion → evidence.

**Uncovered list (mechanical): empty.**

### Coverage map

| Req | Design decision(s) serving it | Criteria | Evidence (record) | Substance check |
|---|---|---|---|---|
| W1 uv project, ruff+mypy strict, pytest tiers, 5-job CI, dev-only oracles | epic §5 (pointer); hatchling = tactical default ratified by user "ok" | AC-1, AC-2, AC-3 | m1-s1-report §GREEN, m1-s2-ci-proof §1-2, m1-step5-tests-floor, CI 32428177629 | Tiering proven by `conftest.py` directory→marker and the floor's 123+47+5=175 reconciliation; 5-leg matrix confirmed in `ci.yml`; "dev-only" half proven by the AC-8 clean-venv `uv pip list` (9 packages, no pandapower/pypsa). Covered in substance. |
| W2 pydantic Network with 7 entity kinds, physical units, named errors | D1 units, D2 naming, D5 named errors, D6 ids | AC-4, AC-5 | m1-s3-report, `tests/unit/test_model_invariants.py` (28), snapshot | All seven entity kinds present in `entities.py` incl. optional `Generator.cost`; 7 codes in `errors.py`; schema_version stamp (epic R1) present. Covered. |
| W3 JSON schema emitted + snapshot-tested; round-trip identity | epic §3 ownership row (pointer) | AC-4 (schema half), AC-5 | m1-s3-report §2 (tamper → FAIL), `test_native_roundtrip_fixtures.py` (16) + `test_model_roundtrip.py` (hand-built all-entity: Geo, Polynomial, Piecewise, Storage, Zone — `grep -n` below) | Covered. |
| W4 `matpower.load(path_or_text)` incl. gencost, parity vs pandapower `from_mpc` on 5 fixtures | D3 gencost-now, D4 type-4 tolerance, D6 ids | AC-6 | m1-s4-report, `tests/parity/test_matpower_vs_pandapower.py` (30) | Covered in substance with two **letter deviations**, both declared in the record: (F2) API is `load(path)` + `loads(text)`, not one `load(path_or_text)` — `load("mpc.baseMVA = …")` would hit `Path(...).read_text` and fail; (F5) oracle is pandapower's `from_ppc` pipeline fed by an independent numpy reader, because `from_mpc`'s `.m` reader (`matpowercaseframes`) is not in the locked env (A10, s4 §5.1). |
| W5 `NetworkArrays` + Ybus/Bbus/PTDF/LODF over scipy.sparse, proven vs dense + pandapower | D1 (pu conversion only in `NetworkArrays`), D7 ownership | AC-7 | m1-s5-report, `test_numerics_dense.py` (15), `test_ybus_vs_pandapower.py` (15), `test_numerics_properties.py` (5) | Covered in substance; see finding F1 under AC-7 (the "for every fixture" clause is guarded on the synthetic case only). PTDF/LODF are returned dense (documented in `ptdf.py`/`lodf.py`); Ybus/Bbus/Bf/Yf/Yt are sparse CSC and the PTDF solve is a sparse LU — "over scipy.sparse" is met where density is not inherent. |
| W6 `uv build` wheel installs clean; import + fixture load | epic §5 "uv (env, lock, build)" (pointer) | AC-8 | m1-s6-report, CI job `install smoke (wheel + sdist)` in 32428177629, floor §7 | Covered. |

Hand-built round-trip coverage, proving command:
```
$ grep -n "Storage\|Zone\|Geo\|PiecewiseCost\|PolynomialCost\|def test_" tests/unit/test_model_roundtrip.py
37:                geo=Geo(lat=37.5, lon=127.0),
68:                cost=PolynomialCost(coefficients=[0.01, 20.0, 100.0], startup=500.0),
80:                cost=PiecewiseCost(
100:            Storage(
110:        zones=[Zone(id="z1", name="Zone 1"), Zone(id="z2")],
125:def test_dumps_loads_is_identity() -> None:
130:def test_model_validate_json_of_model_dump_json_is_identity() -> None:
```

### Findings (judgment half)

- **F1 (AC-7 / W5, letter of the criterion vs what the suite guards).** AC-7 reads "For every fixture,
  sparse Ybus equals a dense re-derivation (1e-12) … LODF equals the brute-force single-outage PTDF
  difference …". The matrix row restates it as "on all fixtures". The suite runs the dense double-loop
  Ybus and the brute-force LODF **only on the hand-built 6-bus case** (`test_numerics_dense.py`); on the
  five fixtures it runs the pandapower `makeYbus`/`makeBdc` oracle and a removal-BFS bridge oracle
  (`test_ybus_vs_pandapower.py`), and hypothesis checks bridge/NaN agreement, not LODF values. The auditor
  ran the missing check (probe, §2 AC-7 below): it **holds** on all five fixtures (dense Ybus worst
  5.68e-14, brute-force LODF worst 8.10e-15 over 351 non-bridge outages). So the requirement is
  implemented, but the record's claim "proven on all fixtures" for those two oracles was **not proven by
  the wave** — it is proven here. Step-6 item: parametrize the dense-Ybus and brute-force-LODF tests over
  the fixtures (cheap: the probe script is ~40 lines and runs in seconds).
- **F2 (W4, API shape).** Spec signature `load(path_or_text)`; delivered `load(path)` / `loads(text)`
  (s4 §1). Declared in the slice report, not in the assumptions ledger. AC-8's command uses `load(path)`,
  which works. Cosmetic; log as an assumption or amend the spec line.
- **F4 (AC-2, sequence).** "planted → red → reverted → green again": the green is the wave-branch run
  32423795251 observed *before* the plant, on a different branch; the plant lived on a throwaway branch
  that was deleted, not reverted (A8). The substance the criterion exists for — the same workflow file
  goes red on a failing test and is green without it — is fully shown. Declared; no action.
- **F5 (AC-6, oracle identity).** See W4 row. Layer A (raw columns vs an independent `numpy.loadtxt`
  read) is the exhaustive check and is if anything stronger than `from_mpc` would have been; layer B
  runs pandapower's own conversion code unchanged except for the from_ppc.py:303 sentinel workaround
  applied to the oracle's copy only. Declared (A10, s4 §5.1, §5.4); no action beyond the upstream-report
  decision already parked under ideas/.
- No requirement is answered by criteria but by no design decision once the pointer is honoured.

**Wave-level coverage verdict: no hole.** Three requirements are designed by pointer only (W1, W3, W6);
two letter deviations (F2, F5) and one proof gap closed by the auditor (F1).

---

## (2) Power — per row: what would the observation have shown had the change been absent?

| AC | Evidence observed | Counterfactual (change absent) | Paired positive/negative? | Powerful? |
|---|---|---|---|---|
| AC-1 | 5/5 (later 6/6) jobs success, every step success; local gates exit 0 | A failing gate makes its step `failure` and the job `failure` — shown by run 32424408894 (pytest step) and 32423921545 (ruff step) | Yes: AC-2's red runs are the negative pair | Yes |
| AC-2 | run 32424408894 `failure`, pytest step failure on 5/5 with `FAILED tests/unit/test_planted_failure.py::test_planted_failure` | Without the plant the same workflow is `success` (32423795251) | Yes, by construction | Yes — this row *is* the instrument's power proof |
| AC-3 | `tests/parity/test_oracles_import.py ..` in all 5 jobs | Missing wheel → `uv sync --locked` fails or `import pandapower` raises → step red | Positive assertion (`__version__` non-empty string), not a zero/empty readback | Yes |
| AC-4 | 28 invariant cases: each builds a minimal violator and asserts the code ∈ `err.issues` with the expected `path`; `test_out_of_service_bus_is_not_disconnected` + 5 fixtures load silently; snapshot tamper `base_kv`→`base_kv_RENAMED` → FAIL → regen → PASS (s3 §2) | A missing check → `Network(...)` constructs → `pytest.raises` fails; a drifted schema → parsed-JSON inequality | Yes: violator raises / fixtures silent; tamper red / regen green | Yes |
| AC-5 | `loads(dumps(net)) == net` and the AC-5 expression verbatim on 5 fixtures (16 cases) + hand-built all-entity network | Any lossy field (float repr, tuple/list, dropped None-default) → pydantic `==` over all fields is False | Equality against the full object is a semantic readback, not a zero/empty one; no separate negative case, none needed | Yes |
| AC-6 | Layer A: every mapped column of bus/gen/branch/gencost vs independent numpy read, max abs diff 0.0; layer B worst 2.8e-14; counts, bus types, reconciliation; skips counted, never silent | A swapped/missing column, wrong sign, wrong id scheme, or wrong None-vs-0 convention → `rep.worst > 1e-9` or an `assert` in `compare_raw` | Negative pair = s4 §2 mutation table (x += 2e-9, cost c1 += 1e-8, type flip, in_service flip all caught) — from a scratch script, **`unverified` by re-execution**; the comparison's structure (element-wise, 1e-9) makes the claim evident | Yes |
| AC-7 | dense double loop 1e-12 (6-bus with tap 0.97 + 5° shift + parallel pair + bridge); PTDF vs direct `Bθ=P` solve, slack column zero, flow conservation; LODF vs actual branch-removal rebuild 1e-8; bridges vs removal-BFS on 5 fixtures and hypothesis nets; pandapower makeYbus/makeBdc on 5 fixtures ≤ 2.93e-14 | Wrong tap/shift/charging convention → dense and pandapower rows fail (revert-and-watch below demonstrates the tap term); wrong LODF denominator → brute-force mismatch; parent-vertex bridge bug → property oracle (s5 §2 mutation table, scratch, `unverified` by re-execution) | Yes, plus the revert-and-watch below | Yes; F1 narrows what the *suite* proves, not what holds |
| AC-8 | CI job success: `uv build`; wheel listing grep `py.typed` present and no `fixtures/|tests/`; sdist 6 required + 5 forbidden greps; clean venv install (9 pkgs, no dev group); `0.0.1.dev0 14` exit 0; sdist install + import | Missing `py.typed` → grep exit 1; leaked `.bionic`/`uv.lock` → forbidden grep matches → exit 1 (this RED was actually observed at fc68535, s6 §2: 283 KB sdist with 23 `.bionic` entries); broken import → non-zero exit | Yes: both polarity greps and an observed RED | Yes |

No row rests on a zero/empty/not-present readback without a paired positive case. The two "not present"
assertions that exist (no `fixtures/`/`tests/` in the wheel; no machine-local files in the sdist) are each
paired with a presence assertion in the same step (`py.typed`; six required sdist paths).

### Auditor's AC-7 probe (closes F1's factual question)

Script: `<scratchpad>/ac7_fixture_probe.py` — explicit dense double-loop Ybus (MATPOWER branch model)
and brute-force LODF by rebuilding the network with branch k out of service, for every non-bridge k,
unit transfer across k, on each fixture. Run from the worktree root:

```
$ uv run --no-sync python ac7_fixture_probe.py
case14       dense-Ybus max|diff|=3.97e-15 (<=1e-12: True)  LODF brute-force over 19 non-bridge branches, 1 bridges NaN: max|diff|=5.11e-15 (<=1e-8: True)
case30       dense-Ybus max|diff|=1.46e-14 (<=1e-12: True)  LODF brute-force over 38 non-bridge branches, 3 bridges NaN: max|diff|=3.89e-15 (<=1e-8: True)
case_ieee30  dense-Ybus max|diff|=7.11e-15 (<=1e-12: True)  LODF brute-force over 38 non-bridge branches, 3 bridges NaN: max|diff|=6.14e-15 (<=1e-8: True)
case57       dense-Ybus max|diff|=1.42e-14 (<=1e-12: True)  LODF brute-force over 79 non-bridge branches, 1 bridges NaN: max|diff|=8.10e-15 (<=1e-8: True)
case118      dense-Ybus max|diff|=5.68e-14 (<=1e-12: True)  LODF brute-force over 177 non-bridge branches, 9 bridges NaN: max|diff|=5.44e-15 (<=1e-8: True)
PROBE OK
exit=0
status-after: []
```

Bridge counts 1/3/3/1/9 agree with s5 §5.2. Fixture structural survey (awk over `mpc.bus`/`mpc.branch`),
confirming s4 §6.14 and the parity tests' preconditions:

```
case118: type4 0 | shift!=0 0  status0 0  offnominal-tap 9
case14:  type4 0 | shift!=0 0  status0 0  offnominal-tap 3
case30:  type4 0 | shift!=0 0  status0 0  offnominal-tap 0
case57:  type4 0 | shift!=0 0  status0 0  offnominal-tap 15
case_ieee30: type4 0 | shift!=0 0  status0 0  offnominal-tap 4
```

So the type-4 → out-of-service path (AC-6 last clause) and the phase-shift conjugation (A12) are reachable
only through the unit tests (`test_bus_type_4_is_out_of_service_pq`; the 6-bus 5° shifter) — declared
in the record and confirmed here.

### Revert-and-watch demonstration

Request written 2026-08-20 16:31 to `.bionic/tmp/audit-revert-request.md`. Change chosen: stub the
from-side tap out of `branch_admittances` in `src/mambo_power/numerics/ybus.py`
(`a = tap · e^{jθ}` → `a = e^{jθ}`, one line). Prediction recorded *before* the run: exactly 6 failures —
`test_numerics_dense.py::test_ybus_matches_dense_double_loop`, `::test_yf_yt_match_dense_and_assemble_ybus`,
`test_ybus_vs_pandapower.py::test_ybus_yf_yt_match_pandapower[case14|case_ieee30|case57|case118]` — and
explicitly that `[case30]` (zero off-nominal taps), all Bbus/PTDF/LODF/bridge tests and the property
`test_ybus_symmetric_without_phase_shift` stay green; 169 passed.

Capture: `record/m1-revert-watch.md` (test-runner m1-revert-watch; relaunched after the first runner died
on a server error — it inherited the stubbed throwaway worktree, re-synced, stashed the stub for a fresh
baseline, then ran the protocol). Validation against the three tests of the mandate:

1. **The change really absent.** The capture's `git diff` is exactly the §2 hunk on
   `36bd20aefae9bd5da20ed63fac49ff53815bf0ae` (`index 5facb40..8d4d450`, `1 file changed, 1 insertion(+),
   1 deletion(-)`). Independently confirmed by the auditor *before* the capture existed, read-only, in the
   throwaway worktree: `git -C "C:\Claude Projects\mambo-power-audit" diff` showed the identical hunk and
   blob hashes, `git rev-parse HEAD` → 36bd20a. Baseline with the stub stashed: `175 passed, 9 warnings in 88.98s`.
2. **The check is one the matrix leans on.** Both failing test functions are named verbatim in the
   matrix's AC-7 `tier-run:` line (`tests/unit/test_numerics_dense.py` dense double-loop Ybus;
   `tests/parity/test_ybus_vs_pandapower.py` makeYbus oracle with the per-fixture diffs quoted).
3. **The red is the failure predicted.** Full run with the stub: `6 failed, 169 passed, 9 warnings in 22.19s`,
   the `short test summary info` being exactly the six predicted ids and no other. The `-v` listing of the
   three numerics files shows every predicted-green item green: `[case30]` PASSED (zero off-nominal taps),
   all five `test_bbus_bf_pshift_match_pandapower[*]` PASSED, `test_ybus_is_not_symmetric_with_phase_shift`
   PASSED, `test_ybus_symmetric_without_phase_shift` PASSED, all PTDF/LODF/bridges PASSED. Signatures:
   parity `AssertionError: case14: max |Ybus diff| = 6.001e-01` / `assert 0.6001… <= 1e-09`; dense
   `Not equal to tolerance rtol=0, atol=1e-12 … Mismatched elements: 3 / 36` at cells [2,2], [2,3], [3,2] —
   precisely the three Ybus entries the tap-0.97 branch `xf-34` (bus-3 ↔ bus-4) touches.
   Restore: `git checkout -- src/mambo_power/numerics/ybus.py` → `git status --porcelain` empty →
   `29 passed in 36.19s` on the two files. Throwaway worktree removed; `git worktree list` shows only
   `mambo-power` and `mambo-power-m1`; the wave worktree was never entered (auditor re-checked:
   `git -C mambo-power-m1 status --porcelain` empty, HEAD 36bd20a).

Ruling on the magnitude note: case57 and case118 diffs (3.19, 3.89) exceed the "order 1e-2..1e0" phrase I
wrote for case14. That phrase was an order-of-magnitude expectation for the *form* of the failure, not a
bound, and it is not the falsifiable part of the prediction — the test-id set, the fixture-by-tap-count
pattern, and the dense cell positions are. The larger values are expected: the diff scales with
`|y|·|1 − 1/tap²|`, and case57/case118 carry transformers with small `x` and taps further from 1 than
case14's; all four are 9–10 orders above the 1e-9 tolerance. **Does not matter.**

**Revert-and-watch: VALIDATED.** Durable, auditable after integration, and it covers the Ybus convention
across the dense and pandapower rows at once — the falsified mutant is one the scratch-script mutation
table of s5 §2 can no longer reproduce.

---

## (3) Authenticity — was each row's evidence produced at its declared tier?

Tiers used: T1 (AC-1,2,3,4,5,8) and T2 (AC-6,7). No T3 row is declared, so no real-surface/freshness/cold-client
check applies; walk is `exempt` (library) and no walk artifact was demanded.

**T2 fixture-fidelity declarations.** Both T2 rows declare "verbatim upstream MATPOWER bytes, sha256-verified
against gridlab archive/ts-w1". Re-verified by the auditor:

```
$ sha256sum fixtures/matpower/*.m                       (worktree)
bc2e6f22…4b5f7  case118.m   2ffc4e1b…cf3c1  case14.m   3d903031…8137  case30.m
2218325a…7d28b  case57.m    b3bcc616…3953e  case_ieee30.m
$ git -C "C:\Claude Projects\gridlab" show archive/ts-w1:packages/io/test/fixtures/matpower/<f>.m | sha256sum
case14 2ffc4e1b…cf3c1  case30 3d903031…8137  case_ieee30 b3bcc616…3953e  case57 2218325a…7d28b  case118 bc2e6f22…4b5f7
```
All five identical. Structural ability to reach the failure the AC guards: the parity suites assert element-wise
numeric agreement at 1e-9 against an independent reader (AC-6) and against pandapower's own builders (AC-7);
any convention error exceeds that by many orders (s5 §2: 1.2–2.0 for the Ybus mutants; revert-and-watch above).
The fixtures *cannot* reach type-4, phase-shift, out-of-service or parallel-branch paths (survey above) — the
record says so and routes those to unit/property tests. Hypothesis networks are declared synthetic.

**Re-executed evidence commands (3, one per tier used plus one more T1):**

| # | Tier | Command (auditor) | Record claim | Auditor output | Match |
|---|---|---|---|---|---|
| 1 | T1 | `gh run view <id> --repo mambo10005/mambo-power --json conclusion,headSha,jobs` for 32428177629, 32424408894, 32423795251, 32426337968, 32427821165 | 36bd20a 6/6 success; c594112 failure with pytest step failing on 5/5; 2922d8e, c9b5a90, fc68535 5/5 success | `{"conclusion":"success","headSha":"36bd20a…","jobs":[install smoke success, windows/ubuntu 3.12/3.13/3.11, macos all success]}`; `{"conclusion":"failure","headSha":"c594112…", every job "Run uv run pytest=failure"}`; the other three `success` on all 5 jobs with no non-success step | Yes, all five |
| 2 | T2 | `uv run pytest -m parity -q -p no:cacheprovider` | floor: `47 passed, 128 deselected, 9 warnings in 16.97s` | `47 passed, 128 deselected, 9 warnings in 131.43s`, exit 0 (wall time inflated: run concurrently with the unit tier and the probe) | Yes (counts, warnings) |
| 3 | T1 | `uv run pytest -m unit -q -p no:cacheprovider` | floor: `123 passed, 52 deselected in 4.82s` | `123 passed, 52 deselected in 9.52s`, exit 0 | Yes |

`git status --porcelain` printed nothing before and after each (pytest caches, `.hypothesis/` are gitignored —
`cat .gitignore` lists `.pytest_cache/`, `.hypothesis/`, `dist/`).

Per-row authenticity:

| AC | Declared tier | Cited surface | Auditor check | Verdict |
|---|---|---|---|---|
| AC-1 | T1 | CI runs + local floor | re-exec #1, #2, #3 | authentic |
| AC-2 | T1 | CI run 32424408894 (+32423921545) | re-exec #1: failure at pytest on 5/5 | authentic |
| AC-3 | T1 | pytest step of 32423795251 | re-exec #1 (job success implies step success); parity tier re-run includes `test_oracles_import` | authentic |
| AC-4 | T1 | `test_model_invariants.py`, snapshot test, s3 §2 tamper | re-exec #3 (123 unit incl. 28+3); tamper RED not re-run (`unverified` beyond the record's own output) | authentic |
| AC-5 | T1 | roundtrip tests | re-exec #3 | authentic |
| AC-6 | T2 | parity module, fixtures | re-exec #2; sha256; survey | authentic (oracle identity deviation declared) |
| AC-7 | T2 | dense/parity/property | re-exec #2 (+ unit #3 for dense); probe; revert-and-watch | authentic |
| AC-8 | T1 | CI install-smoke job + floor §7 | re-exec #1 (job success); local replay not re-run (would create `dist/`, `.smoke`) — `unverified` by the auditor, relied on floor §7's full command/output log | authentic |

---

## (4) Verdicts

| Row | Verdict | Reason (one line) |
|---|---|---|
| AC-1 | CONFIRMED | Gates exit 0 locally (floor) and in 6/6 jobs on 36bd20a; CI re-queried; negative pair exists (AC-2). |
| AC-2 | CONFIRMED | Planted `assert 1 == 2` red at the pytest step on 5/5 (re-queried); same workflow green without it; sequence deviation A8 declared. |
| AC-3 | CONFIRMED | Oracle imports green in all 5 legs; clean-venv install shows oracles are dev-only. |
| AC-4 | CONFIRMED | Each of 7 codes raised on a minimal violator with path asserted; fixtures silent; snapshot drift proven to fail. |
| AC-5 | CONFIRMED | Full-object equality after JSON round-trip on 5 fixtures and an all-entity hand-built network. |
| AC-6 | CONFIRMED | Element-wise parity at 1e-9 (layer A diff 0.0, layer B ≤ 2.8e-14) against an independent reader + pandapower's converter; fixtures verified verbatim; oracle is `from_ppc` pipeline not literal `from_mpc` (declared). |
| AC-7 | CONFIRMED (finding F1) | Dense/pandapower/brute-force/property oracles all green and re-run; the "for every fixture" clause for dense Ybus and LODF is guarded only on the 6-bus case by the suite — the auditor's probe shows it holds (worst 5.7e-14 / 8.1e-15). Revert-and-watch VALIDATED: tap stub → exactly the 6 predicted tests red, 169 green, case30 green as predicted. |
| AC-8 | CONFIRMED | Wheel installs into a clean venv with no dev deps; `0.0.1.dev0 14` exit 0 in CI and locally; both-polarity content guards; sdist RED observed and fixed. |
| **Wave M1** | **CONFIRMED** | Coverage: no uncovered requirement; W1/W3/W6 designed by pointer to the epic design (not waived, not missing). Power: every row has a stated counterfactual that differs from the observation; revert-and-watch validated (6/6 predicted red, 0 unpredicted, predicted-green all green). Authenticity: 3 re-executions match; fixtures byte-verified. Carry F1 (add fixture-parametrized dense/LODF tests) and F2 (`load` signature) to Step 6. |

---

## (5) Reporting-contract observations in the record

1. **Matrix AC-7 criterion** ("… equal dense re-derivation and pandapower Ybus **on all fixtures**") and the
   spec's "For every fixture …" are claims whose proving commands cover the dense and LODF oracles on the
   synthetic case only (F1). Not labelled `unverified`. Closed by the auditor's probe; the wording should be
   corrected or the tests extended.
2. **Plan AC-6/AC-7 `fixture-fidelity:` "sha256-verified against gridlab archive/ts-w1"** — the verification
   is asserted in epic.plan.md (AC-4 execution line, "verified SAME") but no command output with the digests
   appears anywhere in the M1 record (`grep -rn -i sha256 record/` → no hits). Discharged above by the auditor.
3. **Mutation tables in s4 §2 and s5 §2** come from scratch scripts that no longer exist; outputs are shown
   but are not re-executable. They are labelled "scratch", not `unverified`; treat as supporting colour, not
   proof. The revert-and-watch here is the durable replacement for one of them.
4. **Plan Slices table row S1** lists `tests/unit/test_oracles_import.py`; the file is
   `tests/parity/test_oracles_import.py` (s1 report deviation 5 says so; the table was not updated). Stale
   path in the plan, no effect on evidence.
5. Everything else sampled carries command + output or an explicit `unverified` label (S1 CI legs before
   push, S5 3.13 leg, S6 job on GitHub before push, floor's non-local legs — each later discharged by CI
   run 32428177629 or left honestly open as A14).
