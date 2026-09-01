# m1 / R3 — parity: assert nothing about the oracle's bridge columns

Wave M1 "substrate", mambo-power epic (build · audited · wave), Step 6 follow-up fix R3.
Worktree: `/c/Users/mambo/AppData/Local/Temp/claude/C--Claude-Projects-mambo-power/0d397067-49ef-4969-aefa-5709948393ef/scratchpad/bionic-unified`, branch `wave/01-substrate`, base `fcbf571`.
Test-only change; no `src/` edits. Not pushed.

## Failure being fixed

CI run 32435150722 on fcbf571, failing ONLY on macos-latest / py3.12:

```
$ gh run view 32435150722 --repo mambo10005/mambo-power --log-failed | grep -E "FAILED|AssertionError"
macos-latest / py3.12	UNKNOWN STEP	2026-08-21T01:07:36.9486590Z E           AssertionError: case_ieee30: oracle bridge column 15 is finite and bounded
macos-latest / py3.12	UNKNOWN STEP	2026-08-21T01:07:36.9506610Z tests/parity/test_ybus_vs_pandapower.py:144: AssertionError
macos-latest / py3.12	UNKNOWN STEP	2026-08-21T01:07:36.9561890Z E           AssertionError: case118: oracle bridge column 6 is finite and bounded
macos-latest / py3.12	UNKNOWN STEP	2026-08-21T01:07:36.9595350Z tests/parity/test_ybus_vs_pandapower.py:144: AssertionError
macos-latest / py3.12	UNKNOWN STEP	2026-08-21T01:07:36.9631100Z FAILED tests/parity/test_ybus_vs_pandapower.py::test_ptdf_lodf_match_pandapower[case_ieee30] - AssertionError: case_ieee30: oracle bridge column 15 is finite and bounded
macos-latest / py3.12	UNKNOWN STEP	2026-08-21T01:07:36.9644380Z FAILED tests/parity/test_ybus_vs_pandapower.py::test_ptdf_lodf_match_pandapower[case118] - AssertionError: case118: oracle bridge column 6 is finite and bounded
```

Diagnosis (orchestrator): pandapower's `makeLODF` leaves a bridge (singular) column finite and
bounded on macOS Accelerate (nanmax = 1.0, i.e. the raw `H[:, k] = PTDF·(e_f − e_t)` values) but
non-finite on Linux/Windows OpenBLAS. R2's "non-finite OR > 1e6" tolerance still encoded an
assumption about the oracle's representation. The test must make no assertion about how the
oracle represents a bridge column. Our side is deterministic: `lodf()` NaNs bridges by
`|1 − h_kk| < 1e-10`, cross-checked against the graph-theoretic `bridges()` elsewhere — that
assertion stays.

## Diff

```diff
diff --git a/tests/parity/test_ybus_vs_pandapower.py b/tests/parity/test_ybus_vs_pandapower.py
index d88511b..2f5b4c2 100644
--- a/tests/parity/test_ybus_vs_pandapower.py
+++ b/tests/parity/test_ybus_vs_pandapower.py
@@ -134,16 +134,11 @@ def test_ptdf_lodf_match_pandapower(case: dict[str, Any]) -> None:
     keep = [k for k in range(arr.n_branch) if k not in bridge]
     worst = float(np.abs(l_ours[:, keep] - l_pp[:, keep]).max())
     assert worst <= TOL, f"{case['name']}: max |LODF diff| = {worst:.3e}"
+    # pandapower's makeLODF representation of a bridge (singular) column is platform-dependent --
+    # non-finite on Linux/Windows, finite and bounded on macOS Accelerate (CI runs 32434672637,
+    # 32435150722). We assert nothing about it; only that OUR column is NaN.
     for k in bridge:
         assert np.isnan(l_ours[:, k]).all()
-        # pypower's makeLODF scales column k by 1 / (1 - h_kk). For a bridge, h_kk is 1 in exact
-        # arithmetic; whether the BLAS-computed 1 - h_kk is exactly 0.0 (Linux/Windows OpenBLAS
-        # -> inf/NaN column) or ~1e-16 (macOS Accelerate -> huge but finite column) is platform
-        # noise. Accept either: the oracle column is non-finite or blows past 1e6.
-        col = l_pp[:, k]
-        assert (~np.isfinite(col)).any() or float(np.nanmax(np.abs(col))) > 1e6, (
-            f"{case['name']}: oracle bridge column {k} is finite and bounded"
-        )
```

Kept: the non-bridge PTDF comparison (all columns; PTDF has no singular columns) and the
non-bridge LODF comparison, which excludes bridge columns on both sides via the existing
`keep` mask (`l_ours[:, keep]` vs `l_pp[:, keep]`). Kept: `assert np.isnan(l_ours[:, k]).all()`
for every bridge `k`.

## Teeth check

Temporarily deleted `result[:, is_bridge] = np.nan` (line 40) from
`src/mambo_power/numerics/lodf.py`, ran the parity test, then reverted with
`git checkout -- src/mambo_power/numerics/lodf.py`.

RED (src broken):

```
$ uv run pytest -q -p no:cacheprovider tests/parity/test_ybus_vs_pandapower.py -k test_ptdf_lodf_match_pandapower
>           assert np.isnan(l_ours[:, k]).all()        (x5)
FAILED tests/parity/test_ybus_vs_pandapower.py::test_ptdf_lodf_match_pandapower[case14]
FAILED tests/parity/test_ybus_vs_pandapower.py::test_ptdf_lodf_match_pandapower[case30]
FAILED tests/parity/test_ybus_vs_pandapower.py::test_ptdf_lodf_match_pandapower[case_ieee30]
FAILED tests/parity/test_ybus_vs_pandapower.py::test_ptdf_lodf_match_pandapower[case57]
FAILED tests/parity/test_ybus_vs_pandapower.py::test_ptdf_lodf_match_pandapower[case118]
5 failed, 25 deselected in 6.45s
```

All five fixtures fail at the ours-NaN assertion. After revert, `git status --porcelain` showed
only ` M tests/parity/test_ybus_vs_pandapower.py`.

GREEN (src restored): included in the full-suite run below (269 passed).

## Gate outputs

```
$ uv sync --locked --all-groups
Resolved 81 packages in 5ms
Checked 77 packages in 18ms

$ uv run ruff check .
All checks passed!
exit=0

$ uv run ruff format --check .
36 files already formatted
exit=0

$ uv run mypy
Success: no issues found in 14 source files
exit=0

$ uv run pytest -q -p no:cacheprovider
269 passed, 9 warnings in 12.59s
exit=0

$ git status --porcelain      (before commit)
 M tests/parity/test_ybus_vs_pandapower.py
```

## Commit

```
3c4f88d8d6a83b6f1b1bc94eb214efd6c9275b9c
fix(m1/R3): parity — assert nothing about the oracle's bridge columns (platform-dependent); ours must be NaN

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01NA3xnvrFVGDqG3azRk8CBs
```

`git status --porcelain` after commit: empty. Not pushed.

## Residual

The fix is verified locally on Windows only. The macOS branch of the claim ("finite and bounded")
is established by the CI logs above, not reproduced here; the next CI run on this commit is the
confirmation for macos-latest.
