# M1 / S1 report — project scaffold + CI skeleton

Date: 2026-08-20. Worktree: `C:\Claude Projects\mambo-power-m1`, branch `wave/01-substrate`,
base `ca10b6a`. Windows 11, Git Bash. `uv` invoked by absolute path
(`/c/Users/mambo/AppData/Roaming/Python/Python314/Scripts/uv.exe`, uv 0.12.5); shown as `uv` below.
Every claim is followed by the command that proved it and its trimmed output; anything not run
is labelled `unverified`.

## Result

- Commit: **`2922d8e3cbb939b03d8e26ad060a79a58a53e32c`** on `wave/01-substrate` (not pushed, per brief).
- All four local checks exit 0 on Windows / CPython 3.12.14; lock reproducible (`--locked` exit 0).
- pandapower 3.3.0 and pypsa 1.2.4 install as wheels on Windows 3.12 and import inside the
  test session (AC-3 local leg).
- Deviations from the brief: 5 small additive ones, listed at the end; none change scope.

## RED (before scaffold)

```
$ uv run --no-sync pytest
warning: `--no-sync` has no effect when used outside of a project
error: Failed to spawn: `pytest`
  Caused by: program not found
exit=2

$ ls .github src tests pyproject.toml uv.lock
ls: cannot access '.github': No such file or directory
ls: cannot access 'src': No such file or directory
ls: cannot access 'tests': No such file or directory
ls: cannot access 'pyproject.toml': No such file or directory
ls: cannot access 'uv.lock': No such file or directory
exit=2
```

Pre-state: `git status --short --branch` → `## wave/01-substrate` with no entries; `git log --oneline -1`
→ `ca10b6a chore(epic-01): migrate MATPOWER fixtures ...`. No git hooks
(`ls C:\Claude Projects\mambo-power\.git\hooks | grep -v sample` → empty; `core.hooksPath` unset).

## GREEN

### Lock and sync

```
$ uv lock
Using CPython 3.12.14
Resolved 81 packages in 1.92s
exit=0
  (uv.lock: 555,579 bytes, 81 [[package]] entries)

$ uv sync --all-groups
 ... + pandapower==3.3.0 ... + pypsa==1.2.4 ... + xarray==2026.7.0
exit=0

$ uv pip list | grep -iE '^(pandapower|pypsa|numpy|scipy|highspy|pydantic|pytest|hypothesis|ruff|mypy|mambo-power) '
highspy 1.15.1 · hypothesis 6.165.10 · mambo-power 0.0.1.dev0 (editable, C:\Claude Projects\mambo-power-m1)
mypy 2.3.1 · numpy 2.5.2 · pandapower 3.3.0 · pydantic 2.13.4 · pypsa 1.2.4 · pytest 9.1.1
ruff 0.16.4 · scipy 1.18.0
```

### The four checks

```
$ uv run ruff check .
All checks passed!
exit=0

$ uv run ruff format --check .
7 files already formatted
exit=0

$ uv run mypy
Success: no issues found in 1 source file
exit=0

$ uv run pytest
platform win32 -- Python 3.12.14, pytest-9.1.1, pluggy-1.6.0
rootdir: C:\Claude Projects\mambo-power-m1
configfile: pyproject.toml
testpaths: tests
plugins: hypothesis-6.165.10, typeguard-4.6.0
collected 3 items
tests\parity\test_oracles_import.py ..                                   [ 66%]
tests\unit\test_version.py .                                             [100%]
============================= 3 passed in 16.84s ==============================
exit=0
```

### Lock reproducibility

```
$ uv sync --locked --all-groups
Resolved 81 packages in 1ms
Checked 77 packages in 5ms
exit=0

$ uv lock --check
Resolved 81 packages in 1ms
exit=0
```

### Tier markers auto-applied by directory (tests/conftest.py)

```
$ uv run pytest -m unit --collect-only -q
tests/unit/test_version.py::test_version_is_nonempty_string
1/3 tests collected (2 deselected)            exit=0

$ uv run pytest -m parity --collect-only -q
tests/parity/test_oracles_import.py::test_pandapower_imports
tests/parity/test_oracles_import.py::test_pypsa_imports
2/3 tests collected (1 deselected)            exit=0

$ uv run pytest -m property --collect-only -q
no tests collected (3 deselected)             exit=5   (expected: tests/property is empty in S1)
```

### Version / oracle values

```
$ uv run python -c "import mambo_power, pandapower, pypsa; print(...)"
mambo_power 0.0.1.dev0
pandapower 3.3.0
pypsa 1.2.4
exit=0
```

### CI workflow parses; matrix is the 5 briefed jobs

```
$ uv run python -c "import yaml,json; d=yaml.safe_load(open('.github/workflows/ci.yml')); ..."
[{"os": "ubuntu-latest", "python": "3.12"}, {"os": "macos-latest", "python": "3.12"},
 {"os": "windows-latest", "python": "3.12"}, {"os": "ubuntu-latest", "python": "3.11"},
 {"os": "ubuntu-latest", "python": "3.13"}]
permissions {'contents': 'read'}
exit=0
```

### Lock covers every matrix leg (wheel-tag scan of uv.lock)

```
$ head -3 uv.lock
version = 1
revision = 3
requires-python = ">=3.11"

$ (awk/grep over wheel URLs per package, collapsed to interpreter-platform tags)
numpy         cp311/cp312/cp313 × macosx/manylinux/win_amd64
scipy         cp311/cp312/cp313 × macosx/manylinux/win_amd64
highspy       cp311/cp312/cp313 × macosx/manylinux/win_amd64
pydantic-core cp311/cp312/cp313 × macosx/manylinux/win_amd64
pandapower    py3-none-any
pypsa         py3-none-any
```

This is lock-level evidence only. Actual install + test on ubuntu/macos and on 3.11/3.13 is
`unverified` locally — it is CI's job and the brief forbids pushing; S2 observes the first run.

### Line endings

`core.autocrlf=true` printed "LF will be replaced by CRLF" warnings at `git add`. The committed
blobs are LF:

```
$ for f in pyproject.toml .github/workflows/ci.yml tests/conftest.py; do git cat-file -p HEAD:$f | tr -cd '\r' | wc -c; done
0  0  0
```

## Commit

```
$ git status --short        (after git add -A, before commit)
A  .github/workflows/ci.yml
A  .python-version
A  pyproject.toml
A  src/mambo_power/__init__.py
A  src/mambo_power/py.typed
A  tests/conftest.py
A  tests/parity/test_oracles_import.py
A  tests/property/.gitkeep
A  tests/unit/test_version.py
A  uv.lock

$ git status --short --ignored | grep '^!!'
!! .bionic/  !! .mypy_cache/  !! .pytest_cache/  !! .ruff_cache/  !! .venv/  (+ __pycache__ dirs)
   → nothing local leaked into the commit; no .gitignore additions were needed.

$ git show --stat HEAD
commit 2922d8e3cbb939b03d8e26ad060a79a58a53e32c
Author: Manho Joung <manhojoung@gmail.com>
Date:   Thu Aug 20 15:19:18 2026 -0700

    feat(m1/S1): project scaffold + CI skeleton — uv/hatchling, ruff+mypy strict, pytest tiers, 5-job matrix

    Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>
    Claude-Session: https://claude.ai/code/session_01NA3xnvrFVGDqG3azRk8CBs

 .github/workflows/ci.yml            |   41 +
 .python-version                     |    1 +
 pyproject.toml                      |   57 +
 src/mambo_power/__init__.py         |   10 +
 src/mambo_power/py.typed            |    0
 tests/conftest.py                   |   24 +
 tests/parity/test_oracles_import.py |   15 +
 tests/property/.gitkeep             |    0
 tests/unit/test_version.py          |    6 +
 uv.lock                             | 2533 +++++++++++++++++++++++++++++++++++
 10 files changed, 2687 insertions(+)
```

## What was delivered (per brief item)

1. `pyproject.toml` — name/version/description/license/requires-python as briefed; hatchling with
   `packages = ["src/mambo_power"]`; runtime deps numpy, scipy, highspy, pydantic>=2; dev group
   pytest, hypothesis, pandapower, pypsa, ruff, mypy; ruff line-length 100, select E/F/I/UP/B,
   target py311; mypy `strict = true`, `files = ["src"]`, `ignore_missing_imports` override for
   pandapower/pypsa/highspy/scipy; pytest testpaths/markers/addopts (see deviation 1).
2. `.python-version` = `3.12`; `uv.lock` committed.
3. `src/mambo_power/__init__.py` — `__version__` from `importlib.metadata.version("mambo-power")`,
   fallback `"0.0.0"`; `src/mambo_power/py.typed`.
4. `tests/conftest.py` applies `unit`/`parity`/`property` by first path component under `tests/`;
   `tests/unit/test_version.py`; `tests/parity/test_oracles_import.py` (AC-3); no `__init__.py`
   anywhere under `tests/`.
5. `.github/workflows/ci.yml` — `permissions: contents: read`, push + pull_request, `fail-fast: false`,
   5-job include matrix, steps exactly as briefed (checkout@v4, setup-uv@v5 enable-cache,
   `uv python install`, `uv sync --locked --all-groups`, ruff check, ruff format --check, mypy, pytest).
6. `.gitignore` — unchanged; every generated directory was already covered (proved above).

## Deviations from the brief (all additive)

1. **pytest `addopts`** is `"-ra --strict-markers --import-mode=importlib"`, not just `"-ra"`.
   Reason: the briefed `__init__.py`-free layout makes same-basename test files across tiers
   collide under the default `prepend` import mode; `importlib` mode removes that trap.
   `--strict-markers` makes a misspelled tier marker an error instead of a silent no-op.
2. **CI job-level `env: UV_PYTHON: ${{ matrix.python }}`.** Reason: `.python-version` pins 3.12,
   and without the override `uv sync`/`uv run` on the ubuntu-3.11 and ubuntu-3.13 legs would
   resolve to 3.12 and silently not test those interpreters. Step list is otherwise verbatim.
3. **`tests/property/.gitkeep`.** Git does not track empty directories and S1 ships no property
   test; the placeholder keeps the tier directory present for S3/S5.
4. **`[tool.ruff] extend-exclude = [".bionic"]`.** The worktree contains a `.bionic` symlink into
   the main checkout's SDLC record; excluded explicitly so ruff never walks it even if gitignore
   handling changes. `readme`/`license-files` metadata also added (standard, harmless).
5. **Oracle import test lives in `tests/parity/`** (the brief) rather than `tests/unit/` (the
   plan's Slices table row S1). Followed the brief: the oracle tier is where oracle imports belong.

## Not done / unverified

- No push, no CI run observed (brief: do not push). AC-1's "every CI matrix job" half and AC-3's
  ubuntu/macos legs are therefore `unverified` — lock-level wheel coverage above is the only
  local evidence. S2 will observe the first run.
- `astral-sh/setup-uv@v5` used as briefed; whether a newer major exists was not checked (`unverified`).
