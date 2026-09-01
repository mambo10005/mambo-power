# M1 Step 5 — tests floor on the wave head

Date: 2026-08-20. Machine: Windows 11 Pro 10.0.26200, Git Bash. Recorded by the M1 step-5 tests-floor subagent.
Worktree: `C:\Claude Projects\mambo-power-m1`, branch `wave/01-substrate`, HEAD `36bd20aefae9bd5da20ed63fac49ff53815bf0ae`.
uv: `C:\Users\mambo\AppData\Roaming\Python\Python314\Scripts\uv.exe` (`uv 0.12.5 (210d1f678 2026-08-14 x86_64-pc-windows-msvc)`), not on PATH, invoked by absolute path. Every command below was run from the worktree root.

**Verdict: all green.** Every command exited 0. Nothing in the worktree was edited, committed or pushed; `git status --porcelain` was empty before and after (scratch venvs and `dist/` removed).

## Summary table

| Suite | Command | Pass | Total | Exit |
|---|---|---|---|---|
| lockfile sync | `uv sync --locked --all-groups` | — | — | 0 |
| lint | `uv run ruff check .` | — | — | 0 |
| format | `uv run ruff format --check .` | 32 files | 32 | 0 |
| types | `uv run mypy` (strict, `files=["src"]`) | 14 files | 14 | 0 |
| unit | `uv run pytest -m unit -q` | 123 | 123 (52 deselected) | 0 |
| parity | `uv run pytest -m parity -q` | 47 | 47 (128 deselected) | 0 |
| property | `uv run pytest -m property -q` | 5 | 5 (170 deselected) | 0 |
| full | `uv run pytest -q` | 175 | 175 | 0 |
| build | `uv build` | 2 artifacts | 2 | 0 |
| wheel listing | `uv run --no-project --python 3.12 python -m zipfile -l dist/*.whl` + py.typed / no-fixtures-tests greps | 2 checks | 2 | 0 |
| sdist listing | `tar -tzf dist/*.tar.gz` + 6 required-file greps + machine-local grep | 7 checks | 7 | 0 |
| wheel install smoke (AC-8) | `uv venv .smoke` → `uv pip install dist/*.whl` → import + case14 | 1 | 1 | 0 |
| sdist install smoke | `uv venv .smoke2` → `uv pip install dist/*.tar.gz` → import | 1 | 1 | 0 |

Reconciliation: 123 + 47 + 5 = 175 = full run. Each tier's "deselected" is the other two tiers (52 = 47+5, 128 = 123+5, 170 = 123+47). Full run wall time: **14.8 s** (`WALL_MS=14836`, pytest's own clock `13.21s`). Warnings: 9 in parity, all from pandapower's `converter/pypower/from_ppc.py` (third-party; see §6).

## Discovered-suite inventory

Inspected before running: `pyproject.toml`, `.github/workflows/ci.yml`, `tests/conftest.py`, the `tests/` tree.

**`pyproject.toml`**
- `[build-system]` hatchling. `[project]` `mambo-power 0.0.1.dev0`, `requires-python >=3.11`, deps numpy, scipy, highspy, pydantic>=2. `[dependency-groups] dev` = pytest, hypothesis, pandapower, pypsa, ruff, mypy.
- `[tool.hatch.build.targets.wheel]` `packages = ["src/mambo_power"]`. `[tool.hatch.build.targets.sdist]` explicit include allow-list: `/src/mambo_power`, `/tests`, `/fixtures`, `/README.md`, `/LICENSE`, `/pyproject.toml`.
- `[tool.ruff]` line-length 100, target py311, `extend-exclude = [".bionic"]`; `[tool.ruff.lint] select = ["E","F","I","UP","B"]`.
- `[tool.mypy]` `strict = true`, `files = ["src"]`; overrides `ignore_missing_imports` for `pandapower.*`, `pypsa.*`, `highspy.*`, `scipy.*`.
- `[tool.pytest.ini_options]` `testpaths = ["tests"]`, `addopts = "-ra --strict-markers --import-mode=importlib"`, markers `unit`, `parity`, `property`.

**`tests/conftest.py`** — `pytest_collection_modifyitems` auto-applies the marker matching the first path component under `tests/` (`unit` / `parity` / `property`). No file carries a tier `pytestmark`; only `@pytest.mark.parametrize` appears in test files. So `-m <tier>` selects exactly by directory.

**`tests/` tree** (11 test modules + 1 snapshot):
- `tests/unit/` — `test_json_schema_snapshot.py`, `test_matpower_parser.py`, `test_model_examples.py`, `test_model_invariants.py`, `test_model_roundtrip.py`, `test_native_roundtrip_fixtures.py`, `test_numerics_arrays.py`, `test_numerics_dense.py`, `test_packaging_metadata.py`, `test_version.py`; `snapshots/network.schema.json`.
- `tests/parity/` — `test_matpower_vs_pandapower.py`, `test_oracles_import.py`, `test_ybus_vs_pandapower.py`.
- `tests/property/` — `test_numerics_properties.py` (+ `.gitkeep`).

**`.github/workflows/ci.yml`** — two jobs:
- `test` (matrix: ubuntu/macos/windows py3.12, ubuntu py3.11, ubuntu py3.13; `UV_PYTHON` set per leg): `uv python install` → `uv sync --locked --all-groups` → `uv run ruff check .` → `uv run ruff format --check .` → `uv run mypy` → `uv run pytest`.
- `install-smoke` (ubuntu, py3.12, independent of matrix): `uv build` → `ls -la dist/` → wheel listing via `uv run --no-project --python 3.12 python -m zipfile -l dist/*.whl` with greps (`py.typed` present; no `fixtures/` or `tests/` path) → sdist listing via `tar -tzf dist/*.tar.gz` with greps (required: `src/mambo_power/py.typed`, `tests/conftest.py`, `fixtures/matpower/case14.m`, `README.md`, `LICENSE`, `pyproject.toml`; forbidden: `.bionic`, `.github`, `.venv`, `uv.lock`, `.python-version`) → `uv venv .smoke --python 3.12` + `uv pip install --python .smoke dist/*.whl` + `uv pip list --python .smoke` + `.smoke/bin/python -c "import mambo_power; from mambo_power.io import matpower; n = matpower.load('fixtures/matpower/case14.m'); print(mambo_power.__version__, len(n.buses))"` → `uv venv .smoke2 --python 3.12` + `uv pip install --python .smoke2 dist/*.tar.gz` + `.smoke2/bin/python -c "import mambo_power; print('sdist install ok', mambo_power.__version__)"`.

Applicable set on this machine: everything in the `test` job for the local leg (windows / py3.12 — matches `.python-version`), plus the full `install-smoke` job. Local adaptation: `.smoke/bin/python` → `.smoke/Scripts/python.exe` (Windows venv layout); `UV_PYTHON=3.12` exported for the build/smoke block as ci.yml does. The 3.11 / 3.13 / ubuntu / macos legs are not reproducible here and are **unverified** by this record.

## 1. Head and status

```
$ git rev-parse HEAD
36bd20aefae9bd5da20ed63fac49ff53815bf0ae

$ git status --porcelain
(no output)            exit 0

$ git branch --show-current
wave/01-substrate
```

## 2. Lockfile sync

```
$ uv sync --locked --all-groups          exit 0
Resolved 81 packages in 1ms
Checked 77 packages in 11ms
```

## 3. Lint

```
$ uv run ruff check .                    exit 0
All checks passed!
```

## 4. Format

```
$ uv run ruff format --check .           exit 0
32 files already formatted
```

## 5. Types

```
$ uv run mypy                            exit 0
Success: no issues found in 14 source files
```

## 6. Tests

```
$ uv run pytest -m unit -q               exit 0
........................................................................ [ 58%]
...................................................                      [100%]
123 passed, 52 deselected in 4.82s

$ uv run pytest -m parity -q             exit 0
(9 warnings, see below)
47 passed, 128 deselected, 9 warnings in 16.97s

$ uv run pytest -m property -q           exit 0
.....                                                                    [100%]
5 passed, 170 deselected in 10.07s

$ uv run pytest -q                       exit 0     wall 14836 ms (date +%s%N around the command)
175 passed, 9 warnings in 13.21s
```

(The full run was executed twice: the first pass — `175 passed, 9 warnings in 26.06s`, exit 0 — lost its wall-clock because `bc` is absent in this Git Bash; the second pass, identical result, was timed with shell arithmetic. Nothing changed between the two runs.)

Warnings summary of the full run, trimmed (`sed -n '/warnings summary/,/-- Docs/p' | … | sort | uniq -c`):

```
  4 tests/parity/test_matpower_vs_pandapower.py::test_counts_match_pandapower[case14]
  1 tests/parity/test_matpower_vs_pandapower.py::test_counts_match_pandapower[case30]
  4 tests/parity/test_matpower_vs_pandapower.py::test_counts_match_pandapower[case57]
  1 .venv/Lib/site-packages/pandapower/converter/pypower/from_ppc.py:212: RuntimeWarning: invalid value encountered in divide
  1 .venv/Lib/site-packages/pandapower/converter/pypower/from_ppc.py:223: RuntimeWarning: divide by zero encountered in divide
  1 .venv/Lib/site-packages/pandapower/converter/pypower/from_ppc.py:223: RuntimeWarning: invalid value encountered in divide
  1 .venv/Lib/site-packages/pandapower/converter/pypower/from_ppc.py:224: RuntimeWarning: invalid value encountered in divide
  1 .venv/Lib/site-packages/pandapower/converter/pypower/from_ppc.py:330: FutureWarning: Setting an item of incompatible dtype is deprecated and will raise an error in a future version of pandas. Value '[]' has dtype incompatible with int64, please explicitly cast to a compatible dtype first.
```

All 9 originate inside pandapower 3.3.0's `from_ppc` converter (the oracle side), none from `src/mambo_power`.

## 7. Build and install smoke

`dist/` did not exist before the build (`ls: cannot access 'dist': No such file or directory`).

```
$ export UV_PYTHON=3.12
$ uv build                                                           exit 0
Building source distribution...
Building wheel from source distribution...
Successfully built dist\mambo_power-0.0.1.dev0.tar.gz
Successfully built dist\mambo_power-0.0.1.dev0-py3-none-any.whl

$ ls -la dist/                                                       exit 0
-rw-r--r-- 1 mambo 197121     1 Aug 20 16:22 .gitignore
-rw-r--r-- 1 mambo 197121 23313 Aug 20 16:22 mambo_power-0.0.1.dev0-py3-none-any.whl
-rw-r--r-- 1 mambo 197121 57597 Aug 20 16:22 mambo_power-0.0.1.dev0.tar.gz
```

Wheel contents:

```
$ uv run --no-project --python 3.12 python -m zipfile -l dist/*.whl  exit 0
mambo_power/__init__.py
mambo_power/py.typed
mambo_power/io/__init__.py
mambo_power/io/matpower.py
mambo_power/io/native.py
mambo_power/model/__init__.py
mambo_power/model/entities.py
mambo_power/model/errors.py
mambo_power/model/network.py
mambo_power/numerics/__init__.py
mambo_power/numerics/arrays.py
mambo_power/numerics/bbus.py
mambo_power/numerics/lodf.py
mambo_power/numerics/ptdf.py
mambo_power/numerics/ybus.py
mambo_power-0.0.1.dev0.dist-info/METADATA
mambo_power-0.0.1.dev0.dist-info/WHEEL
mambo_power-0.0.1.dev0.dist-info/licenses/LICENSE
mambo_power-0.0.1.dev0.dist-info/RECORD

grep -Eq '(^|/)py\.typed[[:space:]]'   -> py.typed PRESENT -> ok
grep -E  '(^|/)(fixtures|tests)/'       -> no match -> no fixtures/ or tests/ paths -> ok
```

Sdist contents (ci.yml's greps applied verbatim):

```
$ tar -tzf dist/*.tar.gz                                             exit 0
mambo_power-0.0.1.dev0/fixtures/matpower/{PROVENANCE.md,SOURCES.md,case118.m,case14.m,case30.m,case57.m,case_ieee30.m}
mambo_power-0.0.1.dev0/src/mambo_power/{__init__.py,py.typed}
mambo_power-0.0.1.dev0/src/mambo_power/io/{__init__.py,matpower.py,native.py}
mambo_power-0.0.1.dev0/src/mambo_power/model/{__init__.py,entities.py,errors.py,network.py}
mambo_power-0.0.1.dev0/src/mambo_power/numerics/{__init__.py,arrays.py,bbus.py,lodf.py,ptdf.py,ybus.py}
mambo_power-0.0.1.dev0/tests/conftest.py
mambo_power-0.0.1.dev0/tests/parity/{test_matpower_vs_pandapower.py,test_oracles_import.py,test_ybus_vs_pandapower.py}
mambo_power-0.0.1.dev0/tests/property/{.gitkeep,test_numerics_properties.py}
mambo_power-0.0.1.dev0/tests/unit/{test_json_schema_snapshot.py,test_matpower_parser.py,test_model_examples.py,test_model_invariants.py,test_model_roundtrip.py,test_native_roundtrip_fixtures.py,test_numerics_arrays.py,test_numerics_dense.py,test_packaging_metadata.py,test_version.py}
mambo_power-0.0.1.dev0/tests/unit/snapshots/network.schema.json
mambo_power-0.0.1.dev0/.gitignore
mambo_power-0.0.1.dev0/LICENSE
mambo_power-0.0.1.dev0/README.md
mambo_power-0.0.1.dev0/pyproject.toml
mambo_power-0.0.1.dev0/PKG-INFO

present: src/mambo_power/py.typed
present: tests/conftest.py
present: fixtures/matpower/case14.m
present: README.md
present: LICENSE
present: pyproject.toml
machine-local grep (.bionic|.github|.venv|uv.lock|.python-version) -> no match -> ok
```

Observation (not a failure, not in ci.yml's forbidden list): hatchling also packs the repo-root `.gitignore` into the sdist despite the explicit `include` allow-list. Harmless; noted for the wave's review.

Wheel into a clean venv (AC-8):

```
$ uv venv .smoke --python 3.12                                       exit 0
Using CPython 3.12.14
Creating virtual environment at: .smoke

$ uv pip install --python .smoke dist/*.whl                          exit 0
Installed 9 packages in 672ms
 + annotated-types==0.8.0
 + highspy==1.15.1
 + mambo-power==0.0.1.dev0 (from file:///C:/Claude%20Projects/mambo-power-m1/dist/mambo_power-0.0.1.dev0-py3-none-any.whl)
 + numpy==2.5.2
 + pydantic==2.13.4
 + pydantic-core==2.46.4
 + scipy==1.18.0
 + typing-extensions==4.16.0
 + typing-inspection==0.4.4

$ uv pip list --python .smoke                                        exit 0
(the same 9 packages; no pytest / pandapower / pypsa / hypothesis — dev group absent as required)

$ .smoke/Scripts/python.exe -c "import mambo_power; from mambo_power.io import matpower; n = matpower.load('fixtures/matpower/case14.m'); print(mambo_power.__version__, len(n.buses))"
0.0.1.dev0 14                                                        exit 0
```

Sdist into a second clean venv:

```
$ uv venv .smoke2 --python 3.12                                      exit 0
$ uv pip install --python .smoke2 dist/*.tar.gz                      exit 0
   Building mambo-power @ file:///C:/Claude%20Projects/mambo-power-m1/dist/mambo_power-0.0.1.dev0.tar.gz
      Built mambo-power @ ...
Installed 9 packages in 576ms   (same 9 as above)

$ .smoke2/Scripts/python.exe -c "import mambo_power; print('sdist install ok', mambo_power.__version__)"
sdist install ok 0.0.1.dev0                                          exit 0
```

Cleanup and re-check:

```
$ rm -rf .smoke .smoke2 dist                                         exit 0
$ ls -d .smoke .smoke2 dist
ls: cannot access '.smoke': No such file or directory
ls: cannot access '.smoke2': No such file or directory
ls: cannot access 'dist': No such file or directory

$ git status --porcelain
(no output)            exit 0, 0 lines

$ git rev-parse HEAD
36bd20aefae9bd5da20ed63fac49ff53815bf0ae
```

## 8. Stack-health snapshot

```
$ uv run python -c "import sys, numpy, scipy, pydantic, highspy; print(sys.version); print(numpy.__version__, scipy.__version__, pydantic.__version__)"
3.12.14 (main, Aug 14 2026, 15:40:22) [MSC v.1944 64 bit (AMD64)]
2.5.2 1.18.0 2.13.4                                                  exit 0

$ uv python find
C:\Claude Projects\mambo-power-m1\.venv\Scripts\python.exe           (Python 3.12.14)

$ uv pip list   (trimmed to the requested packages)                  exit 0
highspy           1.15.1
hypothesis        6.165.10
mypy              2.3.1
numpy             2.5.2
pandapower        3.3.0
pydantic          2.13.4
pypsa             1.2.4
pytest            9.1.1
ruff              0.16.4
scipy             1.18.0
```

## Coverage of the floor vs. CI

| ci.yml step | Run here | Result |
|---|---|---|
| `uv sync --locked --all-groups` | yes | exit 0 |
| `uv run ruff check .` | yes | exit 0 |
| `uv run ruff format --check .` | yes | exit 0 |
| `uv run mypy` | yes | exit 0 |
| `uv run pytest` | yes (`-q`, plus per-tier) | 175/175, exit 0 |
| `uv build` + `ls dist/` | yes | exit 0 |
| wheel py.typed / no fixtures-tests | yes, same greps | pass |
| sdist required / machine-local | yes, same greps | pass |
| wheel → `.smoke` → AC-8 command | yes (`Scripts/python.exe`) | `0.0.1.dev0 14`, exit 0 |
| sdist → `.smoke2` → import | yes (`Scripts/python.exe`) | `sdist install ok 0.0.1.dev0`, exit 0 |
| py3.11 / py3.13 / ubuntu / macos legs | no | unverified (not reproducible on this machine) |

Raw logs for steps 2–7 are in the session scratchpad (`02-sync.log` … `07-build.log`), not in the repo.
