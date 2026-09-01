# M2 Step 5 — tests floor (wave head)

**Wave:** M2 "power-flow" · branch `wave/02-power-flow` · worktree `C:\Claude Projects\mambo-power-m2`
**Run:** 2026-08-20 21:43–21:55 PDT, Windows 11 Pro, Python 3.12.14 (`.python-version` = 3.12), uv 0.12.5
**Mode:** read-only — no edits, commits or pushes by this agent. Every command below ran from the worktree root with
`UV=/c/Users/mambo/AppData/Roaming/Python/Python314/Scripts/uv.exe` (`uv` is not on PATH).

## Verdict

**GREEN on wave head 502dc1b — every command exited 0.** 484/484 tests, lint/format/mypy clean, `mkdocs build --strict`
clean, 7/7 examples, wheel + sdist build/install/guards pass.

## Head: 502dc1b (ratified by the lead; brief originally named e1e7e4f)

- **Pre-check (≈21:43):** HEAD = `e1e7e4f` (the brief's SHA) with `git status --porcelain` = ` M docs/index.md` — a 9-line prose
  hunk in the "Status" admonition, not my change.
- **21:44:23:** that hunk was committed as `502dc1b docs(m2/S7): home page status names the shipped jobs surface …`;
  `git show --stat 502dc1b` = `docs/index.md | 9 ++++++---`, 1 file. The lead then ratified 502dc1b as the wave head.
- **21:44:49 onward:** every command in this record ran (first log mtime 21:44:49), so **the whole floor — including the
  mkdocs build (log 21:51:57) — ran on 502dc1b**. No re-run was needed. Because the only file differing from e1e7e4f is
  `docs/index.md`, the non-docs results are identical for e1e7e4f as well.
- **Post-check (21:54, and again after writing this record):** `git status --porcelain` empty; HEAD `502dc1b`.

## Discovered suite inventory

From `pyproject.toml`:
- `[tool.pytest.ini_options]` — `testpaths=["tests"]`, `addopts="-ra --strict-markers --import-mode=importlib"`, `pythonpath=["."]`;
  markers `unit` (tests/unit), `parity` (tests/parity, pandapower/PyPSA oracles), `property` (tests/property, hypothesis).
- `[tool.ruff]` line-length 100, py311, `extend-exclude=[".bionic"]`; lint select `E F I UP B`.
- `[tool.mypy]` strict, `files=["src"]`; overrides ignore missing imports for pandapower/pypsa/highspy/scipy.
- `[tool.hatch]` wheel `packages=["src/mambo_power"]`; sdist explicit allow-list (src, tests, fixtures, README, LICENSE, pyproject).
- dependency groups: `dev` (pytest, hypothesis, pandapower, pypsa, ruff, mypy), `docs` (mkdocs-material>=9.7, mkdocstrings[python]>=1.0, pymdown-extensions>=10.16).

From `.github/workflows/ci.yml` (4 jobs):
- `test` — matrix ubuntu/macos/windows × 3.12 + ubuntu 3.11, 3.13: `uv sync --locked --all-groups` → `ruff check .` → `ruff format --check .` → `mypy` → `pytest`; plus on ubuntu/3.12 only: `pytest tests/parity/test_ac_timing.py -q -s -p no:cacheprovider` (AC-7 timing figure).
- `examples` — `for f in examples/*.py; do uv run python "$f"; done` (AC-9).
- `install-smoke` — `uv build`; wheel listing guard (py.typed present, no fixtures/ tests/); sdist listing guard (has src/mambo_power/py.typed, tests/conftest.py, fixtures/matpower/case14.m, README.md, LICENSE, pyproject.toml; none of .bionic/.github/.venv/uv.lock/.python-version); wheel → fresh venv `.smoke` → import + `matpower.load('fixtures/matpower/case14.m')`; sdist → fresh venv `.smoke2` → import (AC-8).
- `docs` — `uv run mkdocs build --strict`, upload `site/`.

From `.github/workflows/pages.yml`: `build` = same `mkdocs build --strict` (on push to `epic/01-foundation`/`main`), then `deploy-pages`. No additional check beyond the docs job.

From `mkdocs.yml`: material theme; plugins search, autorefs, mkdocstrings (python, paths [src], sphinx docstrings); hook `docs/hooks/rest_roles.py`; `pymdownx.snippets` with `base_path: [examples, .]` and `check_paths: true` (missing snippet = build failure); nav of 21 pages (Home, Getting started, 6 manual, Examples, 7 API, 3 design, Changelog, Contributing).

Trees: `examples/` = 7 scripts (01_load_and_validate … 07_results_and_export). `tests/` = 22 unit modules, 7 parity modules (+ `_mpc_reader.py`), 1 property module, shared `conftest.py`, `_fixtures.py`, `_brute_force_lodf.py`. `fixtures/matpower/`.

Windows note: the CI job's `.smoke/bin/python` is `.smoke/Scripts/python.exe` here; otherwise the sequence is verbatim.

## Commands, exit codes, trimmed output

### 1. Sync
```
$ uv sync --locked --all-groups            # exit 0, 1 s
Resolved 102 packages in 2ms
Checked 98 packages in 60ms
```

### 2. Lint / format / types
```
$ uv run ruff check .                      # exit 0
All checks passed!
$ uv run ruff format --check .             # exit 0
98 files already formatted
$ uv run mypy                              # exit 0, 1 s
Success: no issues found in 31 source files
```

### 3. Pytest tiers and full run
```
$ uv run pytest -m unit -q -p no:cacheprovider        # exit 0, wall 29 s
329 passed, 155 deselected in 26.78s
$ uv run pytest -m parity -q -p no:cacheprovider      # exit 0, wall 63 s
150 passed, 334 deselected, 10 warnings in 57.74s
$ uv run pytest -m property -q -p no:cacheprovider    # exit 0, wall 6 s
5 passed, 479 deselected in 5.35s
$ uv run pytest -q -p no:cacheprovider                # exit 0, wall 209 s
484 passed, 10 warnings in 193.65s (0:03:13)
```
Tier sum 329 + 150 + 5 = **484 = full total**; deselected counts are the complement (155 = 150+5, 334 = 329+5, 479 = 329+150), so every test carries exactly one of the three markers and none is unmarked or skipped.

The 10 warnings are all inside pandapower's `converter/pypower/from_ppc.py` (RuntimeWarning divide-by-zero/invalid at lines 212/223/224, FutureWarning pandas dtype at line 330) raised from `test_matpower_vs_pandapower.py::test_counts_match_pandapower[case14/case30/case57]` and `test_dc_vs_pandapower.py::test_angles_match_rundcpp[case30]` — oracle-side, not ours.

Wall-time note: the full run (194 s) took about twice the tier sum (90 s). Another agent was running `mkdocs serve`/probes in the same worktree concurrently (scratchpad shows `mkdocs-serve.log`, `probe_sec.py` at 21:53), so the machine was contended; no test timed out or failed.

### 4. AC-7 timing (the ubuntu/3.12 CI step)
```
$ uv run pytest tests/parity/test_ac_timing.py -q -s -p no:cacheprovider    # exit 0, wall 12 s
case300 AC cold 0.1521 s, warm 0.1825 s, 5 iterations
.
1 passed in 6.91s
```
**case300 cold 0.1521 s · warm 0.1825 s · 5 iterations** (threshold < 1.0 s cold). Warm > cold on this contended Windows box; both are well inside the contract.

### 5. Docs
```
$ uv run mkdocs build --strict             # exit 0, wall 50 s
INFO    -  Cleaning site directory
INFO    -  Building documentation to directory: C:\Claude Projects\mambo-power-m2\site
INFO    -  Documentation built in 43.48 seconds
```
`grep -ci 'warning'` = **1**, and that single hit is the Material-for-MkDocs team's advisory banner ("Warning from the Material for MkDocs team … MkDocs 2.0 …") printed by the theme at startup, not a build warning; `--strict` would have exited non-zero on any real warning. Ran on 502dc1b (the post-commit `docs/index.md`).

### 6. Examples (as ci.yml's examples job: `uv run python "$f"` for each)

| script | exit | wall | first 3 output lines |
|---|---|---|---|
| examples/01_load_and_validate.py | 0 | 4 s | `case14: 14 buses, 20 branches, 5 generators, 11 loads, 1 shunts` / `base_mva: 100.0 ¦ slack: ['bus-1']` / `import report: 14 issue(s), codes ['BASE_KV_REPLACED']` |
| examples/02_ac_power_flow.py | 0 | 8 s | `--- case14, q_limits=True` / `converged=True iterations=4 q_limit_rounds=0 max_mismatch=8.77e-13 MVA` / `pinned generators: none` |
| examples/03_dc_power_flow.py | 0 | 16 s | `case300 DC: pf.dc scipy.sparse.linalg.splu converged = True` / `angles: min -19.46 deg, max 56.63 deg (slack at 0)` / `largest DC flows:` |
| examples/04_jobs_api.py | 0 | 22 s | `registered kinds: ['pf.ac', 'pf.dc']` / `pf.ac job_id=a1 status=ok result=AcPowerFlowResult converged=True slack P=232.393 MW` / `pf.dc job_id=d1 status=ok result=DcPowerFlowResult converged=True slack P=219.000 MW` |
| examples/05_roles_and_islands.py | 0 | 11 s | `case14_roles: declared vs effective role where they differ` / `  bus-6: declared pv, effective pq (no in-service generator)` / `demoted PV buses: ['bus-6']` |
| examples/06_network_matrices.py | 0 | 6 s | `case14 arrays: 14 buses, 20 branches, slack position 0` / `  p_load_pu[:4] = [0.    0.217 0.942 0.478]  (MW / base_mva = 100.0)` / `Ybus: (14, 14), format csc, nnz 54, density 27.6%` |
| examples/07_results_and_export.py | 0 | 12 s | `JSON: 7097 bytes; round trip equal: True` / `top-level keys: ['branches', 'buses', 'converged', 'generators', 'iterations', 'max_mismatch_mva', 'provenance', 'q_limit_rounds']` / `provenance keys: ['elapsed_s', 'engine', 'kind', 'options', 'solver', 'started_at', 'version']` |

(`¦` stands in for the literal `|` in example 01's second line.) Wall times include `uv run` start-up under machine contention.

### 7. Build + install smoke (ci.yml install-smoke job)
`dist/`, `.smoke/`, `.smoke2/` did not exist beforehand.
```
$ uv build                                 # exit 0
Successfully built dist\mambo_power-0.0.1.dev0.tar.gz
Successfully built dist\mambo_power-0.0.1.dev0-py3-none-any.whl
  (wheel 59,593 B; sdist 137,246 B)

$ uv run --no-project --python 3.12 python -m zipfile -l dist/*.whl
  36 entries: mambo_power/{__init__,py.typed}, io/ (4), jobs/ (4), model/ (6), numerics/ (8), pf/ (3), results/ (5),
  dist-info/{METADATA,WHEEL,licenses/LICENSE,RECORD}
  py.typed: PRESENT                                             # guard exit 0
  no (fixtures|tests|docs|examples)/ paths                      # guard exit 0  (brief's wider guard; CI checks fixtures|tests)

$ tar -tzf dist/*.tar.gz                   # 84 entries
  has src/mambo_power/py.typed, tests/conftest.py, fixtures/matpower/case14.m, README.md, LICENSE, pyproject.toml   # exit 0
  none of .bionic/.github/.venv/uv.lock/.python-version                                                             # exit 0

$ uv venv .smoke --python 3.12             # exit 0
$ uv pip install --python .smoke dist/*.whl                                  # exit 0
$ uv pip list --python .smoke
  annotated-types 0.8.0, highspy 1.15.1, mambo-power 0.0.1.dev0, numpy 2.5.2, pydantic 2.13.4, pydantic-core 2.46.4,
  scipy 1.18.0, typing-extensions 4.16.0, typing-inspection 0.4.4          (no dev/docs packages — clean venv)
$ .smoke/Scripts/python.exe -c "import mambo_power; from mambo_power.io import matpower; n = matpower.load('fixtures/matpower/case14.m'); print(mambo_power.__version__, len(n.buses))"
0.0.1.dev0 14                              # exit 0

$ uv venv .smoke2 --python 3.12            # exit 0
$ uv pip install --python .smoke2 dist/*.tar.gz                              # exit 0
$ .smoke2/Scripts/python.exe -c "import mambo_power; print('sdist install ok', mambo_power.__version__)"
sdist install ok 0.0.1.dev0                # exit 0

$ rm -rf .smoke .smoke2 dist; git status --porcelain      # (empty)
```

### 8. Stack-health snapshot
```
$ uv run python -c "import sys, numpy, scipy, pydantic, highspy; print(sys.version); print(numpy.__version__, scipy.__version__, pydantic.__version__)"   # exit 0
3.12.14 (main, Aug 14 2026, 15:40:22) [MSC v.1944 64 bit (AMD64)]
2.5.2 1.18.0 2.13.4
```

| package | version | | package | version |
|---|---|---|---|---|
| numpy | 2.5.2 | | pytest | 9.1.1 |
| scipy | 1.18.0 | | hypothesis | 6.165.10 |
| highspy | 1.15.1 | | ruff | 0.16.4 |
| pydantic | 2.13.4 | | mypy | 2.3.1 |
| pandapower | 3.3.0 | | mkdocs-material | 9.7.7 |
| pypsa | 1.2.4 | | mkdocstrings | 1.0.6 |
| | | | mkdocstrings-python | 2.0.7 |
| | | | pymdown-extensions | 11.0.1 |

## Summary table

| suite | cmd | pass | total | exit | wall |
|---|---|---|---|---|---|
| sync | `uv sync --locked --all-groups` | – | – | 0 | 1 s |
| lint | `uv run ruff check .` | – | – | 0 | <1 s |
| format | `uv run ruff format --check .` | 98 files | 98 | 0 | <1 s |
| types | `uv run mypy` | 31 files | 31 | 0 | 1 s |
| unit | `uv run pytest -m unit -q -p no:cacheprovider` | 329 | 329 | 0 | 29 s |
| parity | `uv run pytest -m parity -q -p no:cacheprovider` | 150 | 150 | 0 | 63 s |
| property | `uv run pytest -m property -q -p no:cacheprovider` | 5 | 5 | 0 | 6 s |
| full | `uv run pytest -q -p no:cacheprovider` | 484 | 484 | 0 | 209 s |
| timing | `uv run pytest tests/parity/test_ac_timing.py -q -s -p no:cacheprovider` | 1 | 1 | 0 | 12 s |
| docs | `uv run mkdocs build --strict` | – | 0 real warnings | 0 | 50 s |
| examples | `uv run python examples/*.py` (×7) | 7 | 7 | 0 | 79 s |
| build | `uv build` | wheel + sdist | 2 | 0 | – |
| wheel guards | py.typed present · no fixtures/tests/docs/examples | 2 | 2 | 0 | – |
| sdist guards | 6 required paths · nothing machine-local | 7 | 7 | 0 | – |
| install-smoke wheel | fresh venv → install → import + case14 (14 buses) | 1 | 1 | 0 | – |
| install-smoke sdist | fresh venv → install → import | 1 | 1 | 0 | – |
| stack | python/numpy/scipy/pydantic/highspy import | – | – | 0 | – |

**Timing figures:** case300 AC cold **0.1521 s**, warm **0.1825 s**, 5 iterations.

Raw logs: `C:\Users\mambo\AppData\Local\Temp\claude\C--Claude-Projects-bionic\bcbaf070-8e03-407c-9441-ba9348a5082a\scratchpad\0[1-7]*.log`.
