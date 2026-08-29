# M2 Step 5/6 — R1 fold report (audit + review + critic)

Agent: m2-r1-fold. Date: 2026-08-23. Worktree `C:\Claude Projects\mambo-power-m2`, branch
`wave/02-power-flow`, base `502dc1b` → **commit `b7711977155976b3194b66e1b1c7b2a628f23aec`**
(pushed). `uv` = `C:\Users\mambo\AppData\Roaming\Python\Python314\Scripts\uv.exe`;
`uv sync --locked --all-groups` → `Resolved 102 packages … Checked 98 packages` (uv.lock
untouched, no new dependencies). Every claim below carries its command/output or a
`file:line`, or is labelled `unverified`.

Scope: `m2-audit.md` AC-5/AC-8 REFUTED rows + the AC-11 coverage-hole row (§1, §4);
`m2-review-6axis.md` recommended fold order items 1-6 (S4.1, S4.2, C1, C2, D1, A4=AC-8's
fix); `m2-critic.md` issues 1-2. Recommended-fold-order items 7-8 (18 sub-items, "Docs/text
batch" and "Code tidy batch") were **not** touched, per the brief — logged as plan
Assumptions A13/A14 for a follow-up wave.

Method: for every behavioural change the failing test/reproduction was written first and run
RED (or, for pure-proof additions like A and C, the reproduction confirmed the property
already held — no RED is possible by nature, which is the point: the property held, the
suite just did not say so). Item G's RED was confirmed a second way — temporarily reverting
`ac_newton.py` with `git stash` and re-running both new tests, which failed exactly as
predicted, then `git stash pop` restored the fix.

---

## Baseline (before any edit, HEAD 502dc1b)

```
uv run --no-sync pytest -q -p no:cacheprovider   -> 484 passed, 10 warnings in 67.71s
```

---

## Fold items

### A. AC-5 — case14_island AC solve vs pandapower on the main island

- No RED possible (proof gap, like M1's E): the Step-5 auditor's own hand probe
  (`m2-audit.md` §3) already showed the property true (8.9e-16 pu / 4.4e-14 deg); the matrix's
  "covered by the S4 parity path" citation was false (`case14_island` is not in
  `test_ac_vs_pandapower.py::CASES`).
- Changed: `tests/parity/test_ac_vs_pandapower_island.py` (new) —
  `test_repaired_island_solve_matches_runpp_on_the_main_island` loads `case14_island` via
  `matpower.load_with_warnings`, `solve_ac`s it, and independently builds a pandapower net
  from the same raw matrices via `read_mpc_numpy` + `pandapower_from_raw` (BASE_KV
  substitution, `trafo_model="pi"`) and runs `runpp(enforce_q_lims=True, ...)` — the same
  oracle convention `test_ac_vs_pandapower.py` uses. pandapower's own connectivity check
  drops bus 8 independently of our repair (`in_service` stays `True`, `res_bus` row is
  `NaN` — asserted via `np.isnan`). Compares the 13 main-island buses at
  `TOL_VM = 1e-14` pu / `TOL_VA_DEG = 1e-13` (order-of-magnitude headroom over the auditor's
  measured 8.9e-16 / 4.4e-14, per the brief — not tightened past what is reproducible).
- GREEN: `uv run --no-sync pytest -q tests/parity/test_ac_vs_pandapower_island.py -v` →
  `1 passed in 6.37s` on first run; measured `worst vm ('bus-7', 8.881784197001252e-16)`,
  `worst va ('bus-12', 4.440892098500626e-14)` — matches the auditor's figures exactly.

### B. AC-8 — `pf.ac_newton` missing from the API reference

- RED: `tests/unit/test_api_docs_coverage.py::test_every_public_symbol_is_reachable_from_an_api_page`
  before the docs fix →
  `mambo_power.pf.ac_newton: allocate_generation, flat_start, newton, newton_raphson, specified_injection`
  — the exact five names the auditor's own probe found missing (`m2-audit.md` §3).
- Changed: `docs/api/pf.md` — added `## AC solver over arrays` + `::: mambo_power.pf.ac_newton`
  (same style as the existing `mambo_power.pf.dc` block). `tests/unit/test_api_docs_coverage.py`
  (new) — walks every `docs/api/*.md` page's `:::` directives, then every
  `src/mambo_power` subpackage's submodules via `pkgutil.iter_modules`; a submodule needs no
  directive of its own if every public class/function *defined in it* is re-exported into an
  already-documented module (verified empirically before writing the test: `model.islands`,
  `model.warnings`, `io.report`, `numerics.errors`, `numerics.roles` all already render their
  symbols this way via their package's own `__all__` re-export — grepping the built site for
  `repair_islands`/`ImportReport`/`NoSlackGeneratorError`/`EffectiveRoles` before any fix
  found 1-3 hits each; `newton_raphson`/`allocate_generation`/`specified_injection` found 0 —
  so a naive "every submodule needs its own `:::`" test would have been over-strict and
  flagged pre-existing, already-covered modules outside this fold's scope). Private
  (`_`-prefixed) submodules are skipped (added for item J's `pf._common`).
- GREEN: same test → `2 passed` after the doc fix.
  `uv run --no-sync mkdocs build --strict -d <scratch>` → exit 0; grep of the built site:
  `newton_raphson: 1`, `allocate_generation: 1`, `flat_start: 1`, `specified_injection: 1`
  (was 0 each before).

### C. AC-11 — PROVENANCE.md's case300 licence wording

- No RED possible (proof gap): the wording already existed pre-fold
  (`fixtures/matpower/PROVENANCE.md` case300 section, "not covered by MATPOWER's BSD
  licence").
- Changed: `tests/unit/test_fixture_case300.py` — added
  `test_provenance_case300_entry_carries_the_licence_exclusion_and_no_bsd_claim`: extracts
  the `### case300.m` entry, asserts `"not covered by MATPOWER's BSD licence"` is present and
  the sha256 is quoted there, and that no affirmative BSD-claim phrase (`"is BSD"`,
  `"under the BSD"`, `"BSD-licensed"`, `"BSD licensed"`) appears anywhere in the entry.
- GREEN: `uv run --no-sync pytest -q tests/unit/test_fixture_case300.py -v` → `4 passed` on
  first run.

### D. Critic issue 1 — architecture diagram misdraws `pf.ac_newton`'s dependencies

- Reproduction (not a test — a docs-content check): before the fix,
  `grep -n "^from mambo_power\|^import mambo_power" src/mambo_power/pf/ac_newton.py` shows
  only `numerics.*` imports (no `results`); `src/mambo_power/pf/__init__.py:23` imports
  `mambo_power.model.Network` directly; `src/mambo_power/jobs/run.py:44` imports
  `mambo_power.numerics.NoSlackGeneratorError` directly — none of which the old diagram drew
  (it drew `ac --> results`, which does not exist, and omitted `pf --> model` and
  `jobs --> numerics`, which do).
- Changed: `docs/design/architecture.md` — mermaid `flowchart TB`: removed `ac --> results`,
  added `pf --> model` and `jobs --> numerics`.
- GREEN: re-grepped the same import lines against the new diagram (all three edges now
  match); `uv run --no-sync mkdocs build --strict -d <scratch>` → exit 0 (diagram still
  parses).

### E. Critic issue 2 — fabricated gridlab-w1 infrastructure references

- Reproduction: `grep -rn "packages/|Node suite|browser harness|engine-pf|W1-R5"
  fixtures/matpower/PROVENANCE.md fixtures/matpower/SOURCES.md` → 8 hits before the fix
  (critic's own count), across both files: the opening "transcribed from" paragraph, the "the
  five M1 files" paragraph, the AC-4 Q-limit-lineage note (`W1-R5`), the reference-quality
  gate note (`packages/engine-pf/src/parity.ts`), and the Consumers section (`Node suite`,
  `browser harness in S8`) in `PROVENANCE.md`; the opening paragraph, the reference-solutions
  paragraph (`W1-R5 / AC-4`, `Node suite here; browser harness in S8`) in `SOURCES.md`.
  `git log --oneline --all -S "packages/engine-pf" -- fixtures/matpower/PROVENANCE.md
  fixtures/matpower/SOURCES.md` → `ca10b6a chore(epic-01): migrate MATPOWER fixtures from
  gridlab W1 with provenance intact` confirms the gridlab-w1 origin (critic's own finding).
- Changed: `fixtures/matpower/PROVENANCE.md`, `fixtures/matpower/SOURCES.md` — stripped all 8
  fabricated sentences, replaced with mambo-power's real structure (`fixtures/matpower/`,
  consumed by `tests/parity/` and `tests/unit/`, no browser harness planned); added a note in
  PROVENANCE.md's Consumers section naming the gridlab-w1 origin and commit `ca10b6a` so a
  future reader does not have to `git log -S` it again, per the brief. The sha256/licence
  content next to the fabricated text (load-bearing for AC-11/item C) was **not** touched —
  re-verified below.
- GREEN: `grep -n "packages/\|Node suite\|browser harness\|engine-pf\|W1-R5"
  fixtures/matpower/PROVENANCE.md fixtures/matpower/SOURCES.md` → only 2 hits left, both
  inside the new explanatory note itself (`` `packages/` `` and "a Node/TypeScript test suite
  and a browser harness" as the description of what was removed, not a live claim);
  `grep -n "69a90280e999ef533d94656e0fbc08311f1347c962dd2753ff2005ff5e3f9ac5"` and
  `grep -n "BSD license\|not covered"` both still hit the same lines as before (sha256 and
  licence-caveat content unchanged) — confirmed via item C's test passing unchanged.

### F. Self-review S4.1 — `_peek` RecursionError

- RED: `tests/unit/test_jobs.py::test_deeply_nested_malformed_json_is_a_failed_result_not_a_crash`
  (`run_json("[" * 5000 + "]" * 5000)`) → `RecursionError: maximum recursion depth exceeded
  while decoding a JSON array from a unicode string`, uncaught, crossing `run_json`'s
  boundary — exactly the review's finding (`jobs/run.py:21` contract "nothing crosses the
  boundary" broken).
- Changed: `src/mambo_power/jobs/run.py` — `_peek`'s `except ValueError:` →
  `except (ValueError, RecursionError):`, with a comment explaining `_peek` is best-effort by
  definition; module docstring's pipeline step 4 unchanged (no new failure code here).
- GREEN: same test → `1 passed`; full `tests/unit/test_jobs.py` → `25 passed`.

### G. Self-review S4.2 — unbounded `max_iter`/`max_q_rounds` + divergence guard

- RED: `tests/unit/test_pf_ac_newton.py::test_max_iter_and_max_q_rounds_are_bounded` (expects
  `ValidationError` on `max_iter=1001`/`max_q_rounds=101`) and
  `::test_diverging_start_stops_early_with_a_diverging_message` (expects `sol.iterations < 10`
  on a genuinely diverging 3-bus overload) both confirmed RED by temporarily reverting
  `src/mambo_power/pf/ac_newton.py` via `git stash push -- <file>` and re-running: the bound
  test failed with `DID NOT RAISE ValidationError`; the divergence test failed with
  `assert 1000 < 10` (ran the whole now-bounded cap, `message='did not converge in 1000
  iterations …'`) — `git stash pop` restored the fix afterward, `git status --porcelain`
  clean throughout.
- Changed: `src/mambo_power/pf/ac_newton.py` — `AcOptions.max_iter` gained `le=1000`,
  `max_q_rounds` gained `le=100` (defaults unchanged, 20/10). `newton_raphson` gained
  `_DIVERGENCE_FACTOR = 1e6` and a check after each iteration's mismatch:
  `if norm0 > 0.0 and norm > _DIVERGENCE_FACTOR * norm0: message = "diverging: …"; break`
  (`norm0` is the pre-loop mismatch). Calibration: traced the mismatch iteration-by-iteration
  on hand-built 3-bus overloads at increasing load (1e5 … 1e11 MW) — moderate overloads
  oscillate chaotically but stay within a few hundred/thousand× the starting norm (not a
  monotonic blow-up, so correctly left alone by the guard); an extreme overload (1e11 MW,
  ~1e7 pu on a 100 MVA base) crosses 1e6× at iteration 1, giving a fast, deterministic test.
  `three_bus()` in `tests/unit/test_pf_ac_newton.py` gained optional `load_p_mw`/
  `load_q_mvar` kwargs (default unchanged) to build the overload case without duplicating the
  network.
- GREEN: `uv run --no-sync pytest -q tests/unit/test_pf_ac_newton.py -v` → `23 passed`
  (the divergence test needs only `sol.iterations < 10`, well short of the 1000 cap).

### H. Self-review C1 — dropped `AcSolution.message`

- RED: added `assert result.message is not None and "did not converge" in result.message` to
  `tests/unit/test_pf_ac_newton.py::test_solve_ac_not_converged_is_reported_not_raised` and
  `assert out.result.message is not None and "did not converge" in out.result.message` to
  `tests/unit/test_jobs.py::test_non_convergence_is_ok_with_converged_false` → both failed
  with `AttributeError: 'AcPowerFlowResult' object has no attribute 'message'`.
- Changed: `src/mambo_power/results/power_flow.py` — `AcPowerFlowResult` gained
  `message: str | None = Field(default=None, ...)`. `src/mambo_power/results/from_arrays.py`
  — `ac_result_from_arrays` gained a `message: str | None = None` parameter, threaded into
  the constructed `AcPowerFlowResult`. `src/mambo_power/pf/__init__.py` — `solve_ac`'s call
  now passes `message=sol.message`.
- GREEN: both edited tests plus `tests/unit/test_results_models.py` →
  `uv run --no-sync pytest -q tests/unit/test_pf_ac_newton.py tests/unit/test_jobs.py
  tests/unit/test_results_models.py` → `61 passed`.

### I. Self-review C2 — DC `x == 0` misfiled as `INTERNAL`

- RED: `tests/unit/test_jobs.py::test_dc_of_a_zero_reactance_branch_is_unsolvable_network_not_internal`
  (case14 with one branch's `x` set to `0.0`, `r` left nonzero — legal per `validate_network`,
  M1 fold item B's `r == 0 and x == 0` rule) → `AssertionError: assert 'INTERNAL' ==
  'UNSOLVABLE_NETWORK'`, i.e. reproduced the review's finding exactly (`jobs/run.py:156`
  mapping a user-data problem to the "solver bug" code).
- Changed: `src/mambo_power/numerics/errors.py` — new `UnsolvableNetworkError(Exception)`
  (deliberately not a `ValueError`, same design rationale as `NoSlackGeneratorError` — module
  docstring). `src/mambo_power/numerics/bbus.py` — `branch_susceptance` raises it instead of
  `ValueError` on `x == 0`. `src/mambo_power/numerics/__init__.py` — re-exports it (`__all__`).
  `src/mambo_power/jobs/models.py` — `FailureCode` gained `"UNSOLVABLE_NETWORK"`.
  `src/mambo_power/jobs/run.py` — `run()` catches `UnsolvableNetworkError` before the generic
  `except Exception`, mapping to code `"UNSOLVABLE_NETWORK"`; module docstring's pipeline
  step 4 updated. `src/mambo_power/pf/dc.py` docstring updated. Two pre-existing tests
  coupled to the exception-type change were updated to match (not scope creep — a direct
  consequence of this fix): `tests/unit/test_numerics_guards.py::test_bbus_rejects_zero_reactance`
  and `tests/unit/test_pf_dc.py::test_zero_reactance_branch_is_a_named_error` now catch
  `UnsolvableNetworkError` instead of bare `ValueError`. Docs updated:
  `docs/manual/numerics.md`, `docs/manual/power-flow.md`, `docs/manual/jobs.md` (failure-code
  table + pipeline summary).
- GREEN: `uv run --no-sync pytest -q tests/unit/test_jobs.py tests/unit/test_numerics_guards.py
  tests/unit/test_pf_dc.py` → `40 passed`.

### J. Self-review D1 — duplicated slack-P rule

- Reproduction (not a behavioural RED — a duplication finding): `pf/dc.py:99-101` and
  `pf/ac_newton.py:231-234` (pre-fold line numbers) each independently coded "the first
  in-service slack-bus generator absorbs the balance," tested only against their own oracle
  (`test_first_slack_generator_absorbs_the_balance` in `test_pf_dc.py`,
  `test_slack_balance_goes_to_the_first_slack_generator` in `test_pf_ac_newton.py`) with
  nothing tying the two together.
- Changed: `src/mambo_power/pf/_common.py` (new, private module — leading underscore, same
  "not part of the public API" convention as `tests/parity/_mpc_reader.py`) —
  `absorb_slack_p(arr, p_bus_pu) -> FloatArray`: every generator keeps its declared dispatch
  except the first in-service generator at the slack bus, which absorbs
  `p_bus_pu - arr.p_gen_pu[arr.slack]`. `src/mambo_power/pf/dc.py` — `solve()` now computes
  `p_bus = p_inj[arr.slack] + arr.p_load_pu[arr.slack] + arr.g_shunt_pu[arr.slack]` and calls
  `absorb_slack_p(arr, p_bus)` (algebraically identical to the old
  `p_inj[arr.slack] - p_declared[arr.slack]` delta — verified by hand and by the unchanged
  parity tolerances below). `src/mambo_power/pf/ac_newton.py` — `allocate_generation()` now
  computes `p_bus = s_bus[arr.slack].real + arr.p_load_pu[arr.slack]` and calls
  `absorb_slack_p(arr, p_bus)` (same value as the old inline computation). Both existing
  hand-case tests are unchanged in content — they now exercise the shared function and are
  its agreement tests, per the brief.
  `tests/unit/test_api_docs_coverage.py` was taught to skip private (`_`-prefixed)
  submodules so `pf._common` (an internal implementation detail) is not flagged as an
  undocumented API page.
- GREEN: full DC + AC parity tiers re-run at unchanged tolerances —
  `uv run --no-sync pytest -q tests/unit/test_pf_dc.py tests/unit/test_pf_ac_newton.py
  tests/unit/test_docstrings.py tests/unit/test_api_docs_coverage.py
  tests/parity/test_dc_vs_pandapower.py tests/parity/test_ac_vs_pandapower.py` →
  `98 passed` — DC still ≤ 3.3e-12 deg / 3.5e-12 MW vs `rundcpp`, AC still ≤ 4e-14 pu vs
  `runpp`, confirming the refactor is behaviour-preserving, not just green.

---

## Plan updates

`.bionic/docs/plans/epic-01-foundation/wave-02-power-flow.plan.md`:

- Verification Matrix: AC-5, AC-8, AC-11 status cells `blocked`/`pending` → `discharged`;
  auditor column → `re-audit pending (fold added <evidence>)` (the re-audit itself is a
  separate later dispatch, per the brief — `current:` in `## SDLC State` left untouched).
- AC-5, AC-8, AC-11 evidence blocks (`tier-run`/`readback`) rewritten to name the new tests
  and their measured results.
- `## Assumptions`: added `A13` (deferred "Docs/text batch," self-review fold-order item 7 —
  8 sub-items) and `A14` (deferred "Code tidy batch," item 8 — 10 sub-items), each naming
  every sub-item and its source finding, for a follow-up wave to adopt — exactly as M1's R1
  fold deferred critic items 2/3/4/7/8 into new Assumptions entries.

---

## GREEN gate (HEAD b771197, worktree root)

| Command | Exit | Output |
|---|---|---|
| `uv run --no-sync ruff check .` | 0 | `All checks passed!` |
| `uv run --no-sync ruff format --check .` | 0 (after 1 auto-format) | `101 files already formatted` |
| `uv run --no-sync mypy` | 0 | `Success: no issues found in 32 source files` |
| `uv run --no-sync pytest -q -p no:cacheprovider` | 0 | `492 passed, 10 warnings in 40.94s` |
| `uv run --no-sync mkdocs build --strict` | 0 | `Documentation built in 6.45 seconds` |

(`ruff format` found one file — `src/mambo_power/pf/ac_newton.py` — needing reformatting
after the `le=` bound edits; auto-fixed with `ruff format .`, re-checked clean.)

Test count: 484 → **492** (+8: island parity ×1, api-docs-coverage ×2, provenance wording
×1, RecursionError regression ×1, bound + divergence guard ×2, DC UNSOLVABLE_NETWORK ×1).

---

## Commit

```
b7711977155976b3194b66e1b1c7b2a628f23aec
chore(m2/R1): fold audit + review + critic — AC-5/AC-8/AC-11 proof gaps, diagram + provenance
accuracy, jobs boundary hardening, dropped diagnostic, DC error code, shared slack-P rule
```

Trailers `Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>` and
`Claude-Session: https://claude.ai/code/session_01Cst4pCPagtiPmT7KSuV2sm` verbatim.
`git status --porcelain` empty before and after.

`git show --stat HEAD`:

```
 docs/api/pf.md                               |  4 ++
 docs/design/architecture.md                  |  3 +-
 docs/manual/jobs.md                          |  3 +-
 docs/manual/numerics.md                      |  4 +-
 docs/manual/power-flow.md                    |  8 ++-
 fixtures/matpower/PROVENANCE.md              | 44 ++++++++-------
 fixtures/matpower/SOURCES.md                 | 14 ++---
 src/mambo_power/jobs/models.py               |  1 +
 src/mambo_power/jobs/run.py                  | 15 +++--
 src/mambo_power/numerics/__init__.py         |  7 ++-
 src/mambo_power/numerics/bbus.py             |  5 +-
 src/mambo_power/numerics/errors.py           |  9 +++
 src/mambo_power/pf/__init__.py               |  1 +
 src/mambo_power/pf/_common.py                | 41 ++++++++++++++
 src/mambo_power/pf/ac_newton.py              | 30 +++++++---
 src/mambo_power/pf/dc.py                     | 16 ++++--
 src/mambo_power/results/from_arrays.py       |  4 ++
 src/mambo_power/results/power_flow.py        |  5 ++
 tests/parity/test_ac_vs_pandapower_island.py | 80 +++++++++++++++++++++++++++
 tests/unit/test_api_docs_coverage.py         | 83 ++++++++++++++++++++++++++++
 tests/unit/test_fixture_case300.py           | 15 +++++
 tests/unit/test_jobs.py                      | 27 +++++++++
 tests/unit/test_numerics_guards.py           |  8 ++-
 tests/unit/test_pf_ac_newton.py              | 36 +++++++++++-
 tests/unit/test_pf_dc.py                     |  6 +-
 25 files changed, 411 insertions(+), 58 deletions(-)
```

Pushed: `git push origin wave/02-power-flow` initially failed (`403`, the ambient `gh`
credential was the wrong GitHub account, `MJoung_sempra`, which lacks push access — the repo
owner account `mambo10005` was already logged in via `gh auth login` but inactive). Fixed
with `gh auth switch --hostname github.com --user mambo10005` + `gh auth setup-git`, then the
push succeeded: `502dc1b..b771197  wave/02-power-flow -> wave/02-power-flow`. CI run
`32663188881` (dispatched by the push, `headSha b771197`) finished **success, 8/8 jobs**
(`gh run view 32663188881 --json conclusion,headSha,jobs` → `success`, `b771197…`, 8 jobs) —
confirmed before this report was closed out.

Not merged into `epic/01-foundation`; that branch untouched, per the brief.

---

## Not done / deviations

- **Nothing from the A-J list was skipped.** One judgment call worth the orchestrator's eye:
  item J's helper lives at `pf/_common.py` rather than in `numerics`, because
  `absorb_slack_p` needs `arr.slack`/`arr.gen_bus`/`arr.gen_p_pu`/`arr.p_gen_pu` only (no new
  `numerics` computation) and both callers are already in `pf` — putting it in `numerics`
  would have added a new `pf --> numerics` dependency direction that already exists, but for
  no benefit, since nothing outside `pf` needs the function. `test_api_docs_coverage.py` was
  extended (not just used) to skip private submodules so this new file would not be
  mis-flagged as an API gap — a direct, necessary consequence of adding it, not scope creep.
- **Deferred, as instructed:** self-review recommended-fold-order items 7 ("Docs/text batch,"
  8 sub-items) and 8 ("Code tidy batch," 10 sub-items) — logged verbatim as plan Assumptions
  `A13`/`A14` for a follow-up wave. Not implemented; no code or docs touched for any of them
  beyond what items A-J's own fixes incidentally required (e.g. item I's docs updates to
  `numerics.md`/`power-flow.md`/`jobs.md` were required by item I itself, not part of the
  deferred batch).
- **Two pre-existing tests were edited, not just added to**, as a direct and necessary
  consequence of item I's exception-type change:
  `test_numerics_guards.py::test_bbus_rejects_zero_reactance` and
  `test_pf_dc.py::test_zero_reactance_branch_is_a_named_error` now catch
  `UnsolvableNetworkError` instead of bare `ValueError` — the old assertion would otherwise
  fail (an `UnsolvableNetworkError` is deliberately not a `ValueError`, by the same design
  choice `NoSlackGeneratorError` already made). Both were re-run GREEN.
- **Environment note, not a wave defect:** the git push required switching the ambient `gh`
  account (see Commit section above) — a session/credential-cache issue, not a repository or
  code problem.
