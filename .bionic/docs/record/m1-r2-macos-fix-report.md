# m1/R2 — macOS-only parity failure: pandapower LODF bridge-column oracle

**Wave:** M1 "substrate" · mambo-power epic (build · audited · wave) · Step 6 follow-up fix R2
**Worktree:** `C:\Claude Projects\mambo-power-m1`, branch `wave/01-substrate`, base `ddbcdc4`
**Commit:** `fcbf5710bfd630f8258ef340e3d7a3090d1b10cf` (not pushed)
**Scope:** test-only, one file, +8/−1. No `src/` change.

## 1. The failure (CI run 32434672637 on ddbcdc4)

Only `macos-latest / py3.12` failed; ubuntu and windows legs were green.

```
$ gh run view 32434672637 --repo mambo10005/mambo-power --log-failed | grep -E "FAILED|assert"
macos-latest / py3.12   ...         assert worst <= TOL, f"{case['name']}: max |PTDF diff| = {worst:.3e}"
macos-latest / py3.12   ...         assert worst <= TOL, f"{case['name']}: max |LODF diff| = {worst:.3e}"
macos-latest / py3.12   ...             assert np.isnan(l_ours[:, k]).all()
macos-latest / py3.12   ... >           assert not np.isfinite(l_pp[:, k]).all()
macos-latest / py3.12   ... E           AssertionError: assert not np.True_
macos-latest / py3.12   ...         assert worst <= TOL, f"{case['name']}: max |PTDF diff| = {worst:.3e}"
macos-latest / py3.12   ...         assert worst <= TOL, f"{case['name']}: max |LODF diff| = {worst:.3e}"
macos-latest / py3.12   ...             assert np.isnan(l_ours[:, k]).all()
macos-latest / py3.12   ... >           assert not np.isfinite(l_pp[:, k]).all()
macos-latest / py3.12   ... E           AssertionError: assert not np.True_
macos-latest / py3.12   ... FAILED tests/parity/test_ybus_vs_pandapower.py::test_ptdf_lodf_match_pandapower[case_ieee30] - AssertionError: assert not np.True_
macos-latest / py3.12   ... FAILED tests/parity/test_ybus_vs_pandapower.py::test_ptdf_lodf_match_pandapower[case118] - AssertionError: assert not np.True_
```

Note the PTDF comparison, the non-bridge LODF comparison and our own `np.isnan(l_ours[:, k]).all()`
all passed on macOS; only the assertion about the *oracle's* bridge column failed.

## 2. Diagnosis, as verified

`pandapower.pypower.makeLODF` builds column k as `(H[:, f_k] − H[:, t_k]) / (1 − h_kk)`. For a bridge
branch, h_kk is exactly 1 in real arithmetic, so the denominator is 0 and the column is undefined.
What the *floating-point* `1 − h_kk` comes out as depends on the BLAS that computed `H`:

| platform | `1 − h_kk` | oracle bridge column |
|---|---|---|
| Windows (this machine, OpenBLAS) / Linux | exactly `0.0` | every entry inf or NaN |
| macOS (Accelerate) | ~1e-16 | huge but **finite** |

Probe on this machine over all five fixtures (every bridge `bridges()` reports), confirming the
first row empirically:

```
case14       k= 13 1-h_kk=0.000e+00 nonfinite=20/20   nanmax|col|=inf
case30       k= 12 1-h_kk=0.000e+00 nonfinite=41/41   nanmax|col|=inf
case30       k= 15 1-h_kk=0.000e+00 nonfinite=41/41   nanmax|col|=inf
case30       k= 33 1-h_kk=0.000e+00 nonfinite=41/41   nanmax|col|=inf
case_ieee30  k= 12 1-h_kk=0.000e+00 nonfinite=41/41   nanmax|col|=inf
case_ieee30  k= 15 1-h_kk=0.000e+00 nonfinite=41/41   nanmax|col|=inf
case_ieee30  k= 33 1-h_kk=0.000e+00 nonfinite=41/41   nanmax|col|=inf
case57       k= 44 1-h_kk=0.000e+00 nonfinite=80/80   nanmax|col|=inf
case118      k=6,8,112,132,133,175,176,182,183 (9 bridges) 1-h_kk=0.000e+00 nonfinite=186/186 nanmax|col|=inf
```

The old assertion `assert not np.isfinite(l_pp[:, k]).all()` therefore encoded a platform
accident of the oracle, not a property we care about. The property we care about — *the oracle
also treats this column as degenerate* — is satisfied by either outcome. Our own LODF
(`src/mambo_power/numerics/lodf.py`) marks bridge columns NaN from a `|1 − h_kk| < BRIDGE_TOL`
test, and `bridges()` is a graph-theoretic Tarjan search; both are deterministic, so the
`np.isnan(l_ours[:, k]).all()` assertion is correct and unchanged. (That macOS failed on
case_ieee30/case118 but not case30/case14/case57 is consistent with the rounding being
case-dependent, as one expects from accumulated BLAS rounding.)

## 3. The diff

```diff
--- a/tests/parity/test_ybus_vs_pandapower.py
+++ b/tests/parity/test_ybus_vs_pandapower.py
@@ -136,7 +136,14 @@ def test_ptdf_lodf_match_pandapower(case: dict[str, Any]) -> None:
     assert worst <= TOL, f"{case['name']}: max |LODF diff| = {worst:.3e}"
     for k in bridge:
         assert np.isnan(l_ours[:, k]).all()
-        assert not np.isfinite(l_pp[:, k]).all()
+        # pypower's makeLODF scales column k by 1 / (1 - h_kk). For a bridge, h_kk is 1 in exact
+        # arithmetic; whether the BLAS-computed 1 - h_kk is exactly 0.0 (Linux/Windows OpenBLAS
+        # -> inf/NaN column) or ~1e-16 (macOS Accelerate -> huge but finite column) is platform
+        # noise. Accept either: the oracle column is non-finite or blows past 1e6.
+        col = l_pp[:, k]
+        assert (~np.isfinite(col)).any() or float(np.nanmax(np.abs(col))) > 1e6, (
+            f"{case['name']}: oracle bridge column {k} is finite and bounded"
+        )
```

Checked as asked: the non-bridge comparison on lines 134–136 (`keep = [k ... if k not in bridge]`,
`l_ours[:, keep] - l_pp[:, keep]`) already excludes bridge columns on **both** sides; no change
needed there. `np.nanmax` on an all-NaN column would warn and return NaN, but the `or`
short-circuits on `(~np.isfinite(col)).any()` first, so that path is never reached.

## 4. Teeth check (local only, reverted, not committed)

`lodf()` does not call `bridges()` — it marks bridges by numeric tolerance — so flipping
`bridges()` alone exercises the `keep` comparison rather than the ours-NaN line. Two flips were
run to cover both lines the test relies on:

**A. `bridges()` → `return []`** (as instructed). `keep` now includes the bridge columns, whose
ours side is NaN → RED on the LODF comparison, all five fixtures:
```
>       assert worst <= TOL, f"{case['name']}: max |LODF diff| = {worst:.3e}"
E       AssertionError: case14: max |LODF diff| = nan
E       assert nan <= 1e-09
  (identical for case30, case_ieee30, case57, case118)
5 failed in 6.80s
```

**B. `lodf()` with `result[:, is_bridge] = np.nan` removed.** RED on the ours-NaN assertion, all
five fixtures:
```
>           assert np.isnan(l_ours[:, k]).all()
E           AssertionError: assert np.False_
  (identical for all five)
```

**Reverted** (`git status` showed only the test file modified), then GREEN:
```
$ uv run pytest -q -p no:cacheprovider tests/parity/test_ybus_vs_pandapower.py::test_ptdf_lodf_match_pandapower
5 passed in 6.91s
```

## 5. GREEN gate (worktree, after `uv sync --locked --all-groups`)

```
=== uv run ruff check . ===
All checks passed!
exit=0
=== uv run ruff format --check . ===
36 files already formatted
exit=0
=== uv run mypy ===
Success: no issues found in 14 source files
exit=0
=== uv run pytest -q -p no:cacheprovider ===
269 passed, 9 warnings in 12.79s
exit=0
```

## 6. Commit

```
fcbf5710bfd630f8258ef340e3d7a3090d1b10cf
fix(m1/R2): parity — make the pandapower LODF bridge-column check platform-robust (macOS BLAS yields finite 1/(1-h_kk))
 tests/parity/test_ybus_vs_pandapower.py | 9 ++++++++-
```
Trailers `Co-Authored-By` / `Claude-Session` present. No hook fired. Not pushed.

## 7. Residual

The macOS leg has not been re-run; the fix is verified on Windows plus reasoning about the
macOS value. The only way the new assertion can still fail on macOS is if Accelerate's
`1 − h_kk` were large enough that `|col| ≤ 1e6`, i.e. `1 − h_kk ≳ 1e-6` — ten orders of magnitude
above rounding noise and far beyond our own `BRIDGE_TOL`, which would be a real oracle
discrepancy worth failing on. The next CI run on the branch is the confirmation.
