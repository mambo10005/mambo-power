# M1 Step 6 — R1 review + critic fold report

Agent: m1-r1-fold. Date: 2026-08-20. Worktree `C:\Claude Projects\mambo-power-m1`, branch
`wave/01-substrate`, base `36bd20a` → **commit `ddbcdc4`** (not pushed). `uv` =
`C:\Users\mambo\AppData\Roaming\Python\Python314\Scripts\uv.exe`; `uv sync --locked --all-groups`
→ `Resolved 81 packages … Checked 77 packages` (uv.lock untouched, no new dependencies).
Every claim below carries its command/output or a file:line, or is labelled `unverified`.

Scope: `m1-review-6axis.md` Correctness 1-5, Architecture 1, Duplication 2-4, Readability 1-5;
`m1-critic.md` issues 1, 5, 6. Critic 2, 3, 4, 7, 8 and review Architecture 2 (F2, spec edit)
were **not** touched, per the brief.

Method: for every behavioural change the failing test was written first and run
(`uv run --no-sync pytest -q tests/unit/test_model_invariants.py tests/unit/test_numerics_guards.py
tests/unit/test_matpower_parser.py -p no:cacheprovider` → `15 failed, 70 passed, 5 warnings in 5.27s`),
then the fix was applied and the same selection re-run. Items that only *add* proof (E, F, G
agreement tests) have no RED by nature — they passed on first run, which is the point: the
properties held, the suite just did not say so.

---

## Baseline (before any edit, HEAD 36bd20a)

```
uv run --no-sync pytest -q tests/unit   → 123 passed in 8.43s
uv run --no-sync pytest -q              → 175 passed, 9 warnings in 68.67s (0:01:08)
```

(pytest's own wall figures; the machine is shared with other agents during this step, so the
absolute numbers are environmental — the review saw 61-65 s for the same 175 tests, the floor
saw 14.8 s.)

---

## Fold items

### A. Architecture 1 / Duplication 2 — delete `Network.bus_index()`

- RED (deletion, no behaviour): `grep -rn "bus_index()" src tests` before → only
  `tests/unit/test_model_examples.py:58`; after deleting the method and that test → no hits
  (`grep … ; exit 1`).
- Changed: `src/mambo_power/model/network.py` — method removed (was `:52-54`);
  `tests/unit/test_model_examples.py` — `test_bus_index_is_positional` removed, module docstring
  updated. `numerics.NetworkArrays.bus_index` (`arrays.py:43`) is now the single positional-index
  site.
- GREEN: unit tier `202 passed` (below).

### B. Correctness 2-3 — validator BAD_RANGE for self-loop, `tap_ratio <= 0`, `r == x == 0`; `ybus` guard

- RED (`tests/unit/test_model_invariants.py:87: Failed: DID NOT RAISE NetworkValidationError`) for
  `test_bad_range[kwargs8-branches[1].to_bus]`, `[kwargs9-branches[0].tap_ratio]` (0.0),
  `[kwargs10-branches[0].tap_ratio]` (-1.0), `[kwargs11-branches[0].x]` (r=x=0);
  `tests/unit/test_numerics_guards.py:53: Failed: DID NOT RAISE ValueError` for
  `test_ybus_rejects_zero_series_impedance`.
- Changed: `src/mambo_power/model/network.py:138-161` (new branch loop: self-loop → path
  `branches[i].to_bus`, `tap_ratio` not `> 0`, `r == 0 and x == 0` → path `branches[i].x`);
  `src/mambo_power/numerics/ybus.py:30-35` (`ValueError` naming the branch ids, mirror of
  `bbus.branch_susceptance`). Self-loop fillers replaced with a real `b1–b2` branch plus a third
  bus in `test_duplicate_id` and `test_all_issues_are_reported_in_one_error`
  (`tests/unit/test_model_invariants.py:131-135, 272-278`).
- Tests: `tests/unit/test_model_invariants.py:212-235` (4 BAD_RANGE cases),
  `tests/unit/test_numerics_guards.py:48` (ybus guard, reached by mutating a validated network).
- GREEN: all five pass in the unit run below.

### C. Critic 1 — `allow_inf_nan=False`

- RED: `test_nan_field_is_rejected_at_construction` → `:292 DID NOT RAISE ValidationError`;
  `test_inf_base_mva_is_rejected_at_construction` → `:297 DID NOT RAISE ValidationError`;
  `test_non_standard_json_tokens_are_rejected_not_coerced[…Infinity…]` → `:315 DID NOT RAISE`;
  `[…-Infinity…]` → `:315 DID NOT RAISE`; `[…NaN…]` → raised `NetworkValidationError` (BAD_BASE on
  `nan > 0` being false) instead of pydantic `ValidationError` — i.e. the NaN token *was* parsed
  into the float field and only caught downstream by an unrelated rule.
- Changed: `src/mambo_power/model/entities.py:22` and `src/mambo_power/model/network.py:28`
  (`ConfigDict(…, allow_inf_nan=False)`).
- Tests: `tests/unit/test_model_invariants.py:294-319` — Python-side NaN/inf at construction
  and three hand-written JSON documents with `Infinity` / `NaN` / `-Infinity` tokens via
  `Network.model_validate_json`; pydantic rejects each with `ValidationError` (not coerced to
  `null`, not accepted).
- GREEN: 5/5 pass.

### D. Critic 6 — `rating_mva <= 0`, cost shapes, strictly increasing PWL

- RED (`:87 DID NOT RAISE NetworkValidationError`): `test_bad_range[kwargs12-branches[0].rating_mva]`,
  `[kwargs13-generators[0].cost.coefficients]` (empty), `[kwargs14-generators[0].cost.points]`
  (one point), `[kwargs15-generators[0].cost.points]` (`[(0,0),(10,5),(10,9)]` vertical segment —
  passed the old `<` non-decreasing check).
- Changed: `src/mambo_power/model/network.py:157-161` (`rating_mva` present and not `> 0`),
  `:176-181` (polynomial needs ≥ 1 coefficient), `:184-195` (piecewise needs ≥ 2 points, then
  `later <= earlier` → strictly increasing). Field descriptions updated to state the enforced
  rule (`entities.py:67-68, 75, 78-79`).
- Importer stays silent on fixtures: `RATE_A 0 → None` is already `matpower.py:337` and tested
  at `tests/unit/test_matpower_parser.py:227`; new `tests/unit/test_fixture_agreement.py:41`
  asserts `arr.rating_pu > 0` (i.e. `None → inf`, never 0) on all five fixtures. No existing test
  relied on the looser rule (the round-trip PWL at `test_model_roundtrip.py:81` is strictly
  increasing; the property tier builds no costs).
- GREEN: 4/4 new + fixture assertion ×5 pass.

### E. Correctness 1 (audit F1) — dense Ybus/Bbus/PTDF and brute-force LODF on `[six_bus] + FIXTURES`

- No RED possible (proof gap): the audit's probe already showed the property holds.
- Changed: `tests/unit/test_numerics_dense.py` — `CASES = ["six_bus", *FIXTURES]` (`:33`),
  module-scoped `net` fixture parametrised over it (`:103-112`, asserts the fixture is all
  in-service so dense positions equal array positions), `arr` derived; six-bus-only assertions
  (phase-shift asymmetry, "the shifter really contributes", exact bridge id, parallel pair)
  moved onto a separate `six_arr` fixture (`:121`). `dense_ptdf_column` became `dense_ptdf`
  (`:181`): still one explicit reduced dense `np.linalg.solve`, but one right-hand side per bus
  instead of rebuilding the dense Bbus 118 times — the first cut took 12.3 s + 10.2 s on case118
  for the two PTDF tests alone (`--durations` output, first run), now 0.05 s + 0.08 s.
- LODF brute force: first cut inline in the unit tier put the tier at `207 passed in 39.21s`
  (case118 leg 7.20 s with a pydantic `model_dump`/`model_validate` round trip per outage); after
  switching to deep-copy-once + flip `in_service` + `validate_network(outaged) == []` +
  rebuild arrays, `207 passed in 12.28s` (case118 3.90 s, case57 0.59 s, case30/ieee30 ~0.27 s,
  case14 0.12 s). That is over the ~10 s rule in the brief, so **only the fixture-parametrised
  brute force moved to the parity tier**: the loop lives once in `tests/_brute_force_lodf.py`
  (shared helper, nothing shared with `numerics` beyond calling `ptdf` on the outaged network);
  the unit tier keeps it on the 6-bus case (`test_numerics_dense.py:307`), the parity tier runs
  it on the five fixtures (`tests/parity/test_ybus_vs_pandapower.py:142`, via the existing
  `case` fixture which now also carries `net`, `:72`).
- Timing, unit tier: before `123 passed in 8.43s` → after `202 passed in 6.14s` (slowest test
  0.08 s). Full suite: before `175 passed in 68.67s` → after `269 passed, 9 warnings in 48.46s`
  (slowest own-code item: `test_lodf_matches_brute_force_outage[case118]` 2.45 s; the top
  entries remain pandapower/pypsa import and hypothesis). Absolute figures are environmental;
  the *direction* is what is verified: the unit tier did not get slower.
- GREEN: every dense test runs 6× (`six_bus`, case14, case30, case_ieee30, case57, case118):
  `uv run --no-sync pytest -q tests/unit/test_numerics_dense.py -p no:cacheprovider` is inside
  the `202 passed`.

### F. Critic 5 — independent PTDF/LODF oracle on the five fixtures

- Changed: `tests/parity/test_ybus_vs_pandapower.py:118-139` `test_ptdf_lodf_match_pandapower`
  — `pandapower.pypower.makePTDF.makePTDF(baseMVA, bus, branch)` (slack = REF bus) and
  `makeLODF.makeLODF(branch, PTDF)` on the same internally-indexed ppc the Ybus/Bbus oracle
  uses (built from `_mpc_reader.read_mpc_numpy`, never from our importer), compared at
  `TOL = 1e-9` after the bus permutation; bridge columns asserted NaN on our side and non-finite
  on pypower's. Module docstring extended to name the two new oracle calls.
- GREEN: 5/5 in the parity run (`62 passed` for the tier within the full-suite run; the
  standalone parity run before the LODF move was `57 passed, 9 warnings in 23.30s`).

### G. Duplication 3-4 + Correctness 4 — agreement and guard tests

- `np.bincount(arr.gen_bus, weights=arr.gen_*_pu, minlength=n_bus) == arr.*_pu` for all six
  per-bus/per-generator pairs: on the hand-built multi-generator 4-bus case
  (`tests/unit/test_numerics_arrays.py:200`) and on the five fixtures
  (`tests/unit/test_fixture_agreement.py:26`). Survey (`uv run python -` over the fixtures):
  no fixture has a multi-generator bus (`multi-gen buses {}` on all five — the critic's p3
  survey was right, the review's "case30 bus 2" remark is not), so the 4-bus case is the
  load-bearing one and the fixture leg guards the single-generator path.
- Bus-type round trip `arr.bus_type == raw BUS_TYPE[perm]`:
  `tests/parity/test_ybus_vs_pandapower.py:109` (a test function on the `case` fixture rather
  than an assertion inside it, so a failure is one red test and not five errors).
- Four previously untested guards, `tests/unit/test_numerics_guards.py`: `arrays.py` no
  in-service slack (`:41`), `bbus.py` `x == 0` (`:57`), `ptdf.py` slack out of range both sides
  (`:65`), `lodf.py` shape mismatch (`:73`) — each reached by mutating a validated network or
  passing a bad argument, `pytest.raises(ValueError, match=…)` on the message text.
- GREEN: all inside the `269 passed`.

### H. Readability 1-5 — helper module, single FIXTURES, dead field, BOM, typing, leftovers

- **Import hack → module** (R1): `tests/parity/_mpc_reader.py` holds `read_mpc_numpy` (docstring
  states it is intentionally independent of the importer — review Duplication 5). Both parity
  modules import it; the `importlib.util.spec_from_file_location` block is gone.
- **Mechanism check** (as the brief asked): probe showed `from tests._probe import X` already
  resolved under pytest 9.1.1's importlib mode — but only because pytest injects a synthetic
  `tests` module with `__path__` into `sys.modules` (probe printed `TESTS_PATH: ['…\tests'] None`
  while the repo root was *not* on `sys.path`). That is an internal of the current pytest, so
  I made it explicit with the documented `pythonpath = ["."]` ini option (`pyproject.toml:64-66`,
  commented). `tests` is then a PEP 420 namespace package; checked that no installed package
  ships a top-level `tests`/`test` that would shadow it (`ls .venv/Lib/site-packages/tests` → no
  such file). The `tests/parity/conftest.py` fallback was not needed.
- **Single FIXTURES** (R2): `tests/_fixtures.py` (`FIXTURES`, `FIXTURES_DIR`); the three copies
  in `test_native_roundtrip_fixtures.py`, `test_matpower_vs_pandapower.py`,
  `test_ybus_vs_pandapower.py` removed; `test_numerics_dense.py` and
  `test_fixture_agreement.py` use it too.
- **Dead `_Matrix.line`** (R3): removed (`matpower.py:129-131`, constructor call `:170`).
- **BOM** (Correctness 5): RED `tests/unit/test_matpower_parser.py::test_utf8_bom_does_not_hide_the_first_assignment`
  → `MatpowerImportError: MISSING_BASE_MVA: mpc.baseMVA = ...; not found` (raised at
  `matpower.py:262`). Fix: `read_text(encoding="utf-8-sig", …)` (`matpower.py:109`) and
  `_scan(text.lstrip("\ufeff"))` for the `loads` path (`:116`). Test at `:306` covers both the
  file and the text entry point with a minimal case whose first line is `mpc.baseMVA`.
- **`add: Any`** (R4): `_AddIssue = Callable[[ValidationCode, str, str], None]`
  (`network.py:62`, used at `:232`); mypy strict still clean.
- **Leftovers** (R5): `tests/property/.gitkeep` and `tests/unit/test_version.py` deleted
  (`git rm`); the latter is subsumed by
  `test_packaging_metadata.py::test_dunder_version_matches_distribution_metadata` (`:35`).

---

## Schema snapshot

Observed: after C alone (plus A) the unit tier was green *except* the snapshot — the failure
was entirely due to D's description edits. Regenerated once with
`MAMBO_UPDATE_SNAPSHOTS=1 uv run --no-sync pytest -q tests/unit/test_json_schema_snapshot.py`
(`3 passed`); `git diff -U0 tests/unit/snapshots/network.schema.json | grep '^[-+][^-+]'`:

```
-      "description": "MATPOWER gencost MODEL 1: piecewise-linear (p_mw, cost) breakpoints, non-decreasing in p.",
+      "description": "MATPOWER gencost MODEL 1: piecewise-linear (p_mw, cost) breakpoints, increasing in p.",
-          "description": "(p_mw, cost) breakpoints; p_mw must be non-decreasing.",
+          "description": "(p_mw, cost) breakpoints, at least two; p_mw must be strictly increasing.",
-          "description": "Polynomial coefficients, highest order first, cost per hour at p_mw.",
+          "description": "Polynomial coefficients (at least one), highest order first, cost per hour.",
```

`1 file changed, 3 insertions(+), 3 deletions(-)` — three description strings, nothing
structural. `allow_inf_nan=False` and the deleted `bus_index()` do not appear in the schema, as
the critic predicted. The regeneration is called out in the commit body. Leaving the old text
would have had the schema document a rule the validator no longer enforces.

---

## GREEN gate (HEAD ddbcdc4, worktree root)

| Command | Exit | Output |
|---|---|---|
| `uv run --no-sync ruff check .` | 0 | `All checks passed!` |
| `uv run --no-sync ruff format --check .` | 0 | `36 files already formatted` |
| `uv run --no-sync mypy` | 0 | `Success: no issues found in 14 source files` |
| `uv run --no-sync pytest -q tests/unit -p no:cacheprovider` | 0 | `202 passed in 6.14s` |
| `uv run --no-sync pytest -q --durations=8` | 0 | `269 passed, 9 warnings in 48.46s` |

Test count: 175 → **269** (+94: 16 BAD_RANGE/non-finite cases, 5 guards, 1 BOM, 1 four-bus
agreement, 10 fixture-agreement, +60 from parametrising 12 dense tests over 6 cases net of the
six-bus-only split, +15 parity (bus-type, PTDF/LODF oracle, LODF brute force × 5), −1
`test_bus_index_is_positional`, −1 `test_version`).

Full-suite `--durations=8` (own code in bold, rest is oracle import / hypothesis):

```
13.12s setup    tests/parity/test_matpower_vs_pandapower.py::test_counts_match_pandapower[case14]
 5.17s call     tests/property/test_numerics_properties.py::test_ybus_symmetric_without_phase_shift
 3.72s call     tests/parity/test_oracles_import.py::test_pypsa_imports
 2.45s call     tests/parity/test_ybus_vs_pandapower.py::test_lodf_matches_brute_force_outage[case118]
 1.78s call     tests/property/test_numerics_properties.py::test_reduced_bbus_is_nonsingular
 1.66s call     tests/property/test_numerics_properties.py::test_ptdf_slack_column_is_zero
 1.26s call     tests/property/test_numerics_properties.py::test_bridges_and_nan_lodf_columns_agree_with_removal
 1.04s call     tests/property/test_numerics_properties.py::test_bbus_row_sums_are_zero
```

---

## Commit

`git commit -F …` → exit 0, no hook output. `git status --porcelain` empty afterwards.

```
ddbcdc4 chore(m1/R1): fold review + critic — drop model.bus_index, non-finite + range guards, fixture-parametrized dense/LODF, PTDF oracle, agreement tests, parity helper module
```

Body records the description-only snapshot regeneration and the `pythonpath` decision; trailers
`Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>` and
`Claude-Session: https://claude.ai/code/session_01NA3xnvrFVGDqG3azRk8CBs` verbatim.

`git show --stat HEAD`:

```
 pyproject.toml                               |   3 +
 src/mambo_power/io/matpower.py               |   8 +-
 src/mambo_power/model/entities.py            |   8 +-
 src/mambo_power/model/network.py             |  56 ++++++++++--
 src/mambo_power/numerics/ybus.py             |   6 ++
 tests/_brute_force_lodf.py                   |  44 ++++++++++
 tests/_fixtures.py                           |  12 +++
 tests/parity/_mpc_reader.py                  |  37 ++++++++
 tests/parity/test_matpower_vs_pandapower.py  |  29 +------
 tests/parity/test_ybus_vs_pandapower.py      |  91 +++++++++++++-------
 tests/property/.gitkeep                      |   0
 tests/unit/snapshots/network.schema.json     |   6 +-
 tests/unit/test_fixture_agreement.py         |  43 ++++++++++
 tests/unit/test_matpower_parser.py           |  10 +++
 tests/unit/test_model_examples.py            |   6 +-
 tests/unit/test_model_invariants.py          |  95 ++++++++++++++++++++-
 tests/unit/test_native_roundtrip_fixtures.py |   4 +-
 tests/unit/test_numerics_arrays.py           |  15 ++++
 tests/unit/test_numerics_dense.py            | 123 ++++++++++++++-------------
 tests/unit/test_numerics_guards.py           |  76 +++++++++++++++++
 tests/unit/test_version.py                   |   6 --
 21 files changed, 525 insertions(+), 153 deletions(-)
```

Not pushed. Main checkout and other repos untouched.

---

## Not done / deviations from the brief

- **Nothing from the A-H list was skipped.** Two judgment calls worth the orchestrator's eye:
  1. The LODF brute force moved to parity *for the fixtures only*, per the brief's ~10 s rule
     (measured 12.28 s with it in the unit tier). The loop lives once in
     `tests/_brute_force_lodf.py` rather than being duplicated in both tiers.
  2. `pythonpath = ["."]` in `pyproject.toml` — a one-line, documented pytest option — instead of
     relying on pytest 9's synthetic `tests` module (works today, unspecified). Alternative was the
     brief's `conftest.py`-fixture fallback, which cannot supply a module-level `params=FIXTURES`.
- Out of scope and untouched, as instructed: critic 2 (effective bus types / `v_set` rule), 3
  (island policy, A15), 4 (silently dropped MATPOWER columns), 7 (`NetworkArrays` arrays are
  writable), 8 (record items: epic branch push, A15-A17 ledger entries, mypy scope); review
  Architecture 2 / F2 (spec wording `load(path) / loads(text)`), Correctness 6-9 (lenient
  `float(token)`, duplicate `mpc.<name>` last-wins, `...` continuation, absolute `BRIDGE_TOL`),
  Performance 1-3, Security note 1.
- The fixture-parametrised `NetworkArrays` survey that informed G (no multi-generator bus in any
  fixture) was run ad hoc and is not a test; the four-bus unit case carries that proof.
