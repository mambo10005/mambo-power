# M1 Step 6 — tests floor re-run on the post-fold head

Date: 2026-08-20 (18:00–18:03 PDT). Machine: Windows 11 Pro 10.0.26200, Git Bash. Recorded by the M1 step-6 post-fold floor subagent.
Worktree: `C:\Claude Projects\mambo-power-m1`, branch `wave/01-substrate`, HEAD `ddbcdc4e9457ac5343c308656817a2bf415ac6ca` (`chore(m1/R1): fold review + critic — …`).
uv: `C:\Users\mambo\AppData\Roaming\Python\Python314\Scripts\uv.exe` (`uv 0.12.5 (210d1f678 2026-08-14 x86_64-pc-windows-msvc)`), not on PATH, invoked by absolute path. Every command below was run from the worktree root. Same floor as `m1-step5-tests-floor.md`, re-run on the fold head.

**Verdict: all green on ddbcdc4.** Every command exited 0. This subagent edited, committed and pushed nothing.

**Prominent caveat — worktree was not clean *after*.** `git status --porcelain` was empty before the run, but at the end it showed `M tests/parity/test_ybus_vs_pandapower.py` (file mtime 18:02:31), and briefly `M src/mambo_power/numerics/lodf.py` (mtime 18:03:32, content back to identical with HEAD a moment later). Neither edit is mine: another agent is editing this shared worktree concurrently. The parity-test diff is a macOS-Accelerate tolerance change to the LODF bridge-column oracle assertion (§7). **Timing places it after every measurement in this record:** all four pytest runs finished before `uv build` started, the sdist (which bundles `tests/`) was written at 18:01 and the wheel at 18:02, both before the 18:02:31 mtime; the wheel does not contain `tests/` at all. So every number below reflects the committed tree at ddbcdc4, not the stray edit. I did not revert it (read-only mandate; it is someone else's in-flight work). The lead should expect a non-empty porcelain on this worktree and decide whose edit it is before the next floor run.

## Summary table

| Suite | Command | Pass | Total | Exit | Wall |
|---|---|---|---|---|---|
| lockfile sync | `uv sync --locked --all-groups` | — | — | 0 | ~8 s (rebuilt editable) |
| lint | `uv run ruff check .` | — | — | 0 | <1 s |
| format | `uv run ruff format --check .` | 36 files | 36 | 0 | <1 s |
| types | `uv run mypy` (strict, `files=["src"]`) | 14 files | 14 | 0 | ~2 s |
| unit | `uv run pytest -m unit -q -p no:cacheprovider` | 202 | 202 (67 deselected) | 0 | 7.6 s (pytest 5.81 s) |
| parity | `uv run pytest -m parity -q -p no:cacheprovider` | 62 | 62 (207 deselected) | 0 | 12.4 s (pytest 10.18 s) |
| property | `uv run pytest -m property -q -p no:cacheprovider` | 5 | 5 (264 deselected) | 0 | 14.0 s (pytest 12.10 s) |
| full | `uv run pytest -q -p no:cacheprovider` | 269 | 269 | 0 | **37.1 s** (pytest 32.56 s) |
| build | `uv build` | 2 artifacts | 2 | 0 | 12.8 s |
| wheel listing | `uv run --no-project python -m zipfile -l dist/*.whl` + py.typed / no-fixtures-tests greps | 2 checks | 2 | 0 | — |
| sdist listing | `tar -tzf dist/*.tar.gz` + 6 required-file greps + machine-local grep | 7 checks | 7 | 0 | — |
| wheel install smoke (AC-8) | `uv venv .smoke --python 3.12` → `uv pip install --python .smoke dist/*.whl` → `uv pip list` → import + case14 | 1 | 1 | 0 | 0.8 + 2.9 + 0.2 + 3.2 s |
| sdist install smoke | `uv venv .smoke2 --python 3.12` → `uv pip install --python .smoke2 dist/*.tar.gz` → import | 1 | 1 | 0 | 0.8 + 4.5 + 0.6 s |

Reconciliation: 202 + 62 + 5 = **269** = full run. Each tier's "deselected" is the other two tiers (67 = 62+5, 207 = 202+5, 264 = 202+62). Warnings: 9 in parity (and the same 9 in the full run), all from pandapower's `converter/pypower/from_ppc.py` — third-party, unchanged from the Step-5 record.

Delta vs Step 5 (HEAD 36bd20a): 175 → 269 tests (+79 unit, +15 parity, +0 property); 32 → 36 formatted files; mypy still 14 source files. Full-run wall 14.8 s → 37.1 s (fixture-parametrized dense/LODF and the new PTDF oracle account for the parity/unit growth). `-p no:cacheprovider` was used throughout at the lead's instruction, so no `.pytest_cache` was written.

Local adaptations of `ci.yml`'s install-smoke job: `.smoke/bin/python` → `.smoke/Scripts/python.exe` (Windows venv layout); `--python 3.12` on the wheel-listing step omitted since `.python-version` is `3.12` and the project interpreter is CPython 3.12.14. Wall times measured by a `date +%s%N` wrapper around each command. The 3.11 / 3.13 / ubuntu / macos legs of the CI matrix are not reproducible here and remain **unverified** by this record.

## 1. Head and status (before)

```
$ git rev-parse --short HEAD
ddbcdc4
$ git branch --show-current
wave/01-substrate
$ git status --porcelain
(no output)            exit 0
```

## 2. Lockfile sync

```
$ uv sync --locked --all-groups
Resolved 81 packages in 5ms
   Building mambo-power @ file:///C:/Claude%20Projects/mambo-power-m1
      Built mambo-power @ file:///C:/Claude%20Projects/mambo-power-m1
Prepared 1 package in 8.10s
Uninstalled 1 package in 60ms
Installed 1 package in 55ms
 ~ mambo-power==0.0.1.dev0 (from file:///C:/Claude%20Projects/mambo-power-m1)
exit 0
```

## 3. Lint, format, types

```
$ uv run ruff check .
All checks passed!
exit 0

$ uv run ruff format --check .
36 files already formatted
exit 0

$ uv run mypy
Success: no issues found in 14 source files
exit 0
```

## 4. Pytest tiers and full run

```
$ uv run pytest -m unit -q -p no:cacheprovider
........................................................................ [ 35%]
........................................................................ [ 71%]
..........................................................               [100%]
202 passed, 67 deselected in 5.81s
exit 0   wall 7.6s

$ uv run pytest -m parity -q -p no:cacheprovider
..............................................................           [100%]
============================== warnings summary ===============================
tests/parity/test_matpower_vs_pandapower.py::test_counts_match_pandapower[case14]
tests/parity/test_matpower_vs_pandapower.py::test_counts_match_pandapower[case57]
  ...\pandapower\converter\pypower\from_ppc.py:212: RuntimeWarning: invalid value encountered in divide
  ...\pandapower\converter\pypower\from_ppc.py:223: RuntimeWarning: divide by zero encountered in divide
  ...\pandapower\converter\pypower\from_ppc.py:223: RuntimeWarning: invalid value encountered in divide
  ...\pandapower\converter\pypower\from_ppc.py:224: RuntimeWarning: invalid value encountered in divide
tests/parity/test_matpower_vs_pandapower.py::test_counts_match_pandapower[case30]
  ...\pandapower\converter\pypower\from_ppc.py:330: FutureWarning: Setting an item of incompatible dtype is deprecated ...
62 passed, 207 deselected, 9 warnings in 10.18s
exit 0   wall 12.4s

$ uv run pytest -m property -q -p no:cacheprovider
.....                                                                    [100%]
5 passed, 264 deselected in 12.10s
exit 0   wall 14.0s

$ uv run pytest -q -p no:cacheprovider
........................................................................ [ 26%]
........................................................................ [ 53%]
........................................................................ [ 80%]
.....................................................                    [100%]
(same 9 pandapower warnings as the parity tier)
269 passed, 9 warnings in 32.56s
exit 0   wall 37.1s
```

## 5. Build and content guards

```
$ uv build
Building source distribution...
Building wheel from source distribution...
Successfully built dist\mambo_power-0.0.1.dev0.tar.gz
Successfully built dist\mambo_power-0.0.1.dev0-py3-none-any.whl
exit 0   wall 12.8s

$ ls -la dist/
-rw-r--r-- 1 mambo 197121     1 Aug 20 18:01 .gitignore
-rw-r--r-- 1 mambo 197121 23710 Aug 20 18:02 mambo_power-0.0.1.dev0-py3-none-any.whl
-rw-r--r-- 1 mambo 197121 61595 Aug 20 18:01 mambo_power-0.0.1.dev0.tar.gz
exit 0
```

Wheel listing (`uv run --no-project python -m zipfile -l dist/*.whl`), 19 entries: `mambo_power/__init__.py`, `mambo_power/py.typed`, `io/{__init__,matpower,native}.py`, `model/{__init__,entities,errors,network}.py`, `numerics/{__init__,arrays,bbus,lodf,ptdf,ybus}.py`, `mambo_power-0.0.1.dev0.dist-info/{METADATA,WHEEL,licenses/LICENSE,RECORD}`.
- `py.typed` present: **OK**
- no `fixtures/` or `tests/` path: **OK**

Sdist listing (`tar -tzf dist/*.tar.gz`), 47 entries under `mambo_power-0.0.1.dev0/`: `fixtures/matpower/{PROVENANCE.md,SOURCES.md,case118.m,case14.m,case30.m,case57.m,case_ieee30.m}`, the 14 `src/mambo_power/**` files incl. `py.typed`, `tests/{_brute_force_lodf.py,_fixtures.py,conftest.py}`, `tests/parity/{_mpc_reader.py,test_matpower_vs_pandapower.py,test_oracles_import.py,test_ybus_vs_pandapower.py}`, `tests/property/test_numerics_properties.py`, 11 `tests/unit/test_*.py` + `tests/unit/snapshots/network.schema.json`, `.gitignore`, `LICENSE`, `README.md`, `pyproject.toml`, `PKG-INFO`.
- required `src/mambo_power/py.typed`, `tests/conftest.py`, `fixtures/matpower/case14.m`, `README.md`, `LICENSE`, `pyproject.toml`: all **OK**
- no `.bionic` / `.github` / `.venv` / `uv.lock` / `.python-version`: **OK**

Note: the sdist was written at 18:01, before the stray 18:02:31 edit to `tests/parity/test_ybus_vs_pandapower.py`, so the bundled tests are the committed ddbcdc4 versions.

## 6. Install smoke (AC-8)

```
$ uv venv .smoke --python 3.12
Using CPython 3.12.14
Creating virtual environment at: .smoke
exit 0   wall 0.8s

$ uv pip install --python .smoke dist/mambo_power-0.0.1.dev0-py3-none-any.whl
Resolved 9 packages in 413ms
Installed 9 packages in 1.89s
 + annotated-types==0.8.0  + highspy==1.15.1  + mambo-power==0.0.1.dev0 (from file:///.../dist/...whl)
 + numpy==2.5.2  + pydantic==2.13.4  + pydantic-core==2.46.4  + scipy==1.18.0
 + typing-extensions==4.16.0  + typing-inspection==0.4.4
exit 0   wall 2.9s

$ uv pip list --python .smoke
(the 9 packages above; no pytest / hypothesis / pandapower / pypsa — dev group absent as required)
exit 0

$ .smoke/Scripts/python.exe -c "import mambo_power; from mambo_power.io import matpower; n = matpower.load('fixtures/matpower/case14.m'); print(mambo_power.__version__, len(n.buses))"
0.0.1.dev0 14
exit 0   wall 3.2s

$ uv venv .smoke2 --python 3.12
Using CPython 3.12.14
Creating virtual environment at: .smoke2
exit 0   wall 0.8s

$ uv pip install --python .smoke2 dist/mambo_power-0.0.1.dev0.tar.gz
Resolved 9 packages in 229ms
   Building mambo-power @ file:///.../dist/mambo_power-0.0.1.dev0.tar.gz
      Built mambo-power @ file:///.../dist/mambo_power-0.0.1.dev0.tar.gz
Installed 9 packages in 1.33s   (same 9 packages)
exit 0   wall 4.5s

$ .smoke2/Scripts/python.exe -c "import mambo_power; print('sdist install ok', mambo_power.__version__)"
sdist install ok 0.0.1.dev0
exit 0   wall 0.6s
```

Cleanup: `rm -rf .smoke .smoke2 dist` (exit 0).

## 7. Status (after) — NOT clean, not from this run

```
$ git status --porcelain
 M tests/parity/test_ybus_vs_pandapower.py
$ git rev-parse --short HEAD
ddbcdc4
```

A re-check ~30 s later showed `M src/mambo_power/numerics/lodf.py` as well; by the following check its diff was empty again (mtime 18:03:32, content identical to HEAD). Diff of the file that stayed modified (mtime 18:02:31):

```
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

This subagent issued no write to any tracked file; the only filesystem writes were `.venv` (via `uv sync`), `dist/`, `.smoke`, `.smoke2` — all either gitignored or removed. The edit above was authored by a concurrent agent in the shared worktree. It is left in place untouched. It does not affect any number in this record (see timing argument at the top), but it does mean the "porcelain empty after" acceptance criterion of this task is **not met**, for reasons outside this run.
