# M3 Step 6 — R3 fold report (review + critic)

Agent: m3-r3-fold (this session). Date: 2026-08-24. Worktree `C:\Claude Projects\mambo-power-m3`,
branch `wave/03-opf-n1`, base `8fc8581` → **commit `4bd67d9`** (pushed). `uv` =
`C:\Users\mambo\AppData\Roaming\Python\Python314\Scripts\uv.exe`; `uv sync --locked --all-groups`
→ `Resolved 102 packages … Checked 98 packages` (uv.lock untouched, no new dependencies). Every
claim below carries its command/output or a `file:line`, or is labelled `unverified`.

Scope: exactly the 5 items (A-E) named in the dispatch — `m3-critic.md` Issues 1-3 and
`m3-review-6axis.md`'s Security and Performance FLAGs. Nothing else from either document was in
scope, and nothing else was touched.

**Prior interrupted agent's head start.** A prior `m3-r3-fold` agent was dispatched for this same
task and got interrupted almost immediately, leaving one file modified:
`tests/parity/test_opf_vs_pypsa.py`'s module docstring, replacing the "bus-numbering
index-alignment" guess with the real `GS`-shunt root cause (item A's test-docstring half). Before
building on it, I re-checked its numbers directly against `m3-critic.md`'s own evidence block
(the reproduction section, §"Diagnosis, fully closed"): 17 buses, 1.3 MW total `GS`, case300 the
only one of 5 fixtures with nonzero `GS`, `mambo_power` total dispatch 23527.15 MW vs PyPSA's
23525.85 MW, gap exactly 1.3 MW spread over 68/69 generators. All matched the critic's reported
numbers exactly — kept as-is, no re-derivation needed. This left two of item A's three target
locations (the plan's AC-1 evidence block, `m3-r2-reaudit.md`) and all of items B-E untouched,
which is what this fold completed.

Method: for B and C (behavioural changes), RED then GREEN — the failing test/reproduction run
before the fix, then the fix, then the same test/reproduction re-run. For A, D, E (documentation/
description corrections), facts were verified against the critic's own evidence before writing,
no RED/GREEN cycle applicable.

---

## Baseline (before any edit beyond the prior agent's uncommitted item-A test docstring)

```
git status --porcelain   -> M tests/parity/test_opf_vs_pypsa.py   (prior agent's item-A work)
uv sync --locked --all-groups   -> Resolved 102 packages … Checked 98 packages
```

---

## Fold items

### A. Critic Issue 1 — case300 PyPSA residual's root cause, corrected in all 3 locations

- **`tests/parity/test_opf_vs_pypsa.py`'s module docstring**: already done by the prior
  interrupted agent, verified (not re-derived) against `m3-critic.md`'s reproduction numbers as
  described above, then committed as-is.
- **`.bionic/docs/plans/epic-01-foundation/wave-03-opf-n1.plan.md`'s AC-1 evidence block**
  (`tier-run:` paragraph, previously ending "...plausibly case300's non-contiguous bus numbering
  causing a minor index-alignment difference in one of the two independent importers"): replaced
  with the real, closed diagnosis (case300 the only fixture with nonzero bus `GS`, 17 buses,
  1.3 MW; `dc_opf`'s balance row includes it, PyPSA's importer silently drops it, gap spread
  across 68/69 generators), with an explicit note that this supersedes the earlier untested
  guess.
- **`.bionic/docs/record/m3-r2-reaudit.md`** (a prior agent's landed record, same guess repeated
  in its own AC-1 verdict paragraph): left the original paragraph in place (not rewritten to
  pretend it was always right) and appended a `> **Correction (R3 fold...)**` blockquote
  immediately after it, quoting the original wrong sentence, then giving the same real diagnosis.
- Not git-tracked: `.bionic` is entirely gitignored (`.bionic/.gitignore` is a bare `*`,
  `git status --porcelain --ignored=matching -- .bionic` confirms both files show `!!`), so these
  two edits are local record/plan scaffolding, same as M1/M3-R1's own fold reports.

### B. Review Security FLAG — bound `PiecewiseCost.points`

- **RED**: added `test_piecewise_cost_over_the_bound_is_rejected_at_construction` /
  `test_piecewise_cost_at_the_bound_is_accepted` to `tests/unit/test_model_invariants.py` before
  any fix. Ran `uv run --no-sync pytest -q tests/unit/test_model_invariants.py -k
  "piecewise_cost_over_the_bound or piecewise_cost_at_the_bound"` → `1 failed, 1 passed`:
  `test_piecewise_cost_over_the_bound_is_rejected_at_construction` → `Failed: DID NOT RAISE
  ValidationError` (a 201-point list constructed with no error).
- Changed: `src/mambo_power/model/entities.py` — `PiecewiseCost.points` gained
  `max_length=200` on the pydantic `Field`; description updated to state the bound and its
  reason ("each adds one epigraph row to opf.dc_opf's LP"). 200 chosen per the review's own
  guidance ("tens to low hundreds is a reasonable scale, not thousands"; the review's own probe
  measured 20,000 points at 0.169s — still not runaway, but unboundedness is the actual gap, not
  current cost).
- **GREEN**: `uv run --no-sync pytest -q tests/unit/test_model_invariants.py` → `43 passed`.
- Schema snapshot regenerated (`MAMBO_UPDATE_SNAPSHOTS=1 uv run --no-sync pytest -q
  tests/unit/test_json_schema_snapshot.py` → `3 passed`); diff is exactly the new description
  string plus `"maxItems": 200` — nothing structural:
  ```
  -          "description": "(p_mw, cost) breakpoints, at least two; p_mw must be strictly increasing.",
  +          "description": "(p_mw, cost) breakpoints, at least two and at most 200 (each adds one epigraph row to opf.dc_opf's LP); p_mw must be strictly increasing.",
  +          "maxItems": 200,
  ```

### C. Review Performance FLAG — stop computing PTDF twice per `solve_dc_opf` call

- Fix shape: `dc_opf` (`opf/dc_opf.py`) already builds `ptdf_matrix = compute_ptdf(arr)` to
  construct its flow-limit rows (line 296, unchanged); `OpfSolution` gained a new `ptdf: FloatArray`
  field, populated on both the early non-Optimal return and the final Optimal return (it is
  computed before `Highs.run()`, so it is available either way). `solve_dc_opf`
  (`opf/__init__.py`) now reads `solution.ptdf` instead of calling `compute_ptdf(arr)` itself; the
  now-unused `from mambo_power.numerics.ptdf import ptdf as compute_ptdf` import was removed.
- **Call-count spy test** (`tests/unit/test_opf_solve_dc_opf.py::
  test_solve_dc_opf_computes_ptdf_exactly_once`): patches `compute_ptdf` on both
  `mambo_power.opf.dc_opf` (the remaining call site) and, only if it still exists,
  `mambo_power.opf` (the package-level name the old, buggy `opf/__init__.py` used) — the module
  object for `dc_opf` is fetched via `importlib.import_module`, not attribute access, because
  `mambo_power.opf`'s own `from .dc_opf import ..., dc_opf, ...` shadows the `dc_opf` submodule
  attribute with the `dc_opf` function of the same name (confirmed directly: a first version of
  this test that used `import mambo_power.opf.dc_opf as dc_opf_module` raised
  `AttributeError: 'function' object has no attribute 'compute_ptdf'`).
- **RED, confirmed against the actual pre-fix code**: temporarily reverted `opf/__init__.py` to
  its original `compute_ptdf(arr)` call (re-adding the import), re-ran the spy test →
  `AssertionError: ptdf(arr) computed 2 times in one solve_dc_opf call` — proving the test
  genuinely detects the double-computation, not just the internal `dc_opf()` call count (an
  earlier draft of the spy, patching only `dc_opf`'s own module, passed even against the buggy
  code because it was blind to the second, independently-imported call site in `opf/__init__.py`
  — caught and corrected before relying on it).
- **GREEN**: restored the real fix, re-ran → `1 passed`; full file
  `uv run --no-sync pytest -q tests/unit/test_opf_solve_dc_opf.py` → `10 passed`.
- **Timing, re-measured directly in this environment** (case300, warm, controlled A/B on the
  identical script, before/after the same revert/restore used for the RED/GREEN check above):

  | | solve_dc_opf warm avg (case300, 15 reps) |
  |---|---|
  | before (double PTDF, reverted) | 0.0337 s |
  | after (fix restored) | 0.0262 s |

  Isolated `ptdf(arr)` cost alone (`numerics.ptdf.ptdf`, same fixture, 15 warm reps):
  `0.0088 s` — consistent with the ~0.0075s measured saving above (removing one full PTDF
  computation). Absolute numbers are lower than the review's own (`0.1163s`/`0.0362s`
  respectively) — an environment/machine-load difference, not a discrepancy in the fix's effect;
  the *direction and mechanism* (one fewer `ptdf(arr)` call per `solve_dc_opf`, saving
  approximately one call's worth of time) is what was verified, matching the review's own
  diagnosis exactly.

### D. Critic Issue 2 — docstring-shorthand sibling gap

- Changed: `src/mambo_power/contingency/n1.py:1` — `"""N-1 branch-contingency screening: LODF
  fast screen -> confirming DC re-solve (wave M3 W5)."""` → `"""N-1 branch-contingency screening:
  LODF fast screen -> confirming DC re-solve."""`, matching `contingency/__init__.py:1`'s
  already-fixed (R1 fold) wording style exactly. The broader 22-file convention (plan Assumption
  A6) was **not** touched, per the brief and per A6's own reasoning (fixing 3 more files in
  isolation would make the codebase *less* consistent, not more) — this is the one file the
  critic named as a narrow, direct inconsistency within the R1 fold's own prior edit, not a
  re-litigation of A6.

### E. Critic Issue 3 — stale `Field` description

- Changed: `src/mambo_power/results/opf.py:77-80` — `OpfDcResult.ac_check`'s description
  `"AC-feasibility check of the dispatch; always None until wave M3 slice S5."` → `"AC-feasibility
  check of the dispatch; None unless options.ac_check is true and the LP/QP solved to Optimal."`
  Confirmed (per the critic, not re-verified independently since the claim is purely negative and
  cheap to trust: `OpfDcResult` is rendered class-docstring-only on the built docs site,
  `show_submodules: false`, no per-field description shown) this does not reach the docs site —
  source-only accuracy fix, no `mkdocs build` diff expected or found.

---

## GREEN gate (HEAD `4bd67d9`, worktree root)

| Command | Exit | Output |
|---|---|---|
| `uv run --no-sync ruff check .` | 0 | `All checks passed!` |
| `uv run --no-sync ruff format --check .` | 0 | `127 files already formatted` |
| `uv run --no-sync mypy` | 0 | `Success: no issues found in 39 source files` |
| `uv run --no-sync pytest -q -p no:cacheprovider` | 0 | `596 passed, 10 warnings in 133.30s` |
| `uv run --no-sync mkdocs build --strict` | 0 | `Documentation built in 18.86 seconds` |

(The 10 warnings are the same pre-existing pandapower/pandas `FutureWarning`/`RuntimeWarning`s
from the oracle import path that every prior fold report in this wave has already noted —
unrelated to this fold.)

Test count: 593 → **596** (+3: 2 `PiecewiseCost.points` bound tests, 1 PTDF call-count spy test).

---

## Commit

```
4bd67d9 chore(m3/R3): fold review + critic — case300 root-cause correction, PWL point bound, PTDF caching, docstring/field cleanup
```

Trailers `Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>` and
`Claude-Session: https://claude.ai/code/session_01Cst4pCPagtiPmT7KSuV2sm` verbatim.

```
$ git show --stat HEAD
 src/mambo_power/contingency/n1.py        |  2 +-
 src/mambo_power/model/entities.py        |  4 +++-
 src/mambo_power/opf/__init__.py          |  5 +++--
 src/mambo_power/opf/dc_opf.py            |  9 +++++++++
 src/mambo_power/results/opf.py           |  3 ++-
 tests/parity/test_opf_vs_pypsa.py        | 25 +++++++++++++++++------
 tests/unit/snapshots/network.schema.json |  3 ++-
 tests/unit/test_model_invariants.py      | 15 ++++++++++++++
 tests/unit/test_opf_solve_dc_opf.py      | 34 ++++++++++++++++++++++++++++++++
 9 files changed, 88 insertions(+), 12 deletions(-)
```

Pushed: `git push origin wave/03-opf-n1` → `8fc8581..4bd67d9  wave/03-opf-n1 -> wave/03-opf-n1`.
CI run `32781551954` (dispatched by the push, `headSha
4bd67d9dedec0baafddbbe75b244957908867dcf`) finished **success** (`gh run list --branch
wave/03-opf-n1 --limit 1 --json databaseId,status,conclusion,headSha` → `completed`, `success`) —
confirmed before this report was closed out.

---

## Not done / deviations from the brief

- **All 5 items (A-E) closed**, none skipped.
- Item A's plan/reaudit corrections and item B/C/D/E's production fixes were all in scope exactly
  as dispatched; nothing beyond the named 5 items was touched (in particular, `contingency/n1.py`
  and the other two files sharing its shorthand convention were left alone except for the one
  line item D named; `results/n1.py`/`test_contingency_n1.py`'s identical shorthand, named as a
  carry-over in the R1 fold report, remains untouched here too — outside this fold's scope).
- One judgment call worth the orchestrator's eye: the PTDF call-count spy test's first draft
  (patching only `mambo_power.opf.dc_opf`'s own `compute_ptdf` name) passed even against the
  unfixed, double-computing code, because it was blind to `opf/__init__.py`'s separate,
  independently-imported call site — a false-negative test that would not have caught the bug it
  was meant to guard against. Caught before trusting it, by deliberately reverting the fix and
  re-running the draft test (it should have gone RED and did not); fixed by patching both known
  call-site names, verified this version genuinely goes RED against the reverted code and GREEN
  against the real fix. Recorded here as a caution for anyone patching an aliased
  `from X import Y as Z` import in a similar test elsewhere in this codebase — patch-where-used,
  and verify by actually breaking the fix once, not just by reading the patch target's name.
