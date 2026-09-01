# M3 Step 5 — tests floor (wave head)

**Wave:** M3 "opf-n1" · branch `wave/03-opf-n1` · worktree `C:\Claude Projects\mambo-power-m3`
**Run:** 2026-08-23 18:31–18:53 PDT, Windows 11 Pro, Python 3.12.14 (`.python-version` = 3.12), uv 0.12.5
**Mode:** read-only — no edits, commits or pushes by this agent. Every command below ran from the worktree root with
`UV=/c/Users/mambo/AppData/Roaming/Python/Python314/Scripts/uv.exe` (`uv` is not on PATH).

## Verdict

**GREEN on wave head f37815a — every command exited 0.** 573/573 tests, lint/format/mypy clean, `mkdocs build --strict`
clean, 8/8 examples, wheel + sdist build/install/guards pass.

## Head: f37815a

- **Pre-check (18:31):** `git status --porcelain` empty, `git branch --show-current` = `wave/03-opf-n1`,
  `git rev-parse --short HEAD` = `f37815a` — matches the brief exactly, no re-ratification needed.
- **Post-check (18:53, after cleaning `dist/`/`.smoke*`):** `git status --porcelain` empty; HEAD unchanged at `f37815a`.
  No edits or commits made by this agent at any point.

## Discovered suite inventory

From `pyproject.toml` (unchanged shape from M2, mirrored here):
- `[tool.pytest.ini_options]` — `testpaths=["tests"]`, `addopts="-ra --strict-markers --import-mode=importlib"`,
  `pythonpath=["."]`; markers `unit` (tests/unit), `parity` (tests/parity, pandapower/PyPSA oracles), `property`
  (tests/property, hypothesis).
- `[tool.ruff]` line-length 100, py311, `extend-exclude=[".bionic"]`; lint select `E F I UP B`.
- `[tool.mypy]` strict, `files=["src"]`; overrides ignore missing imports for pandapower/pypsa/highspy/scipy.
- `[tool.hatch]` wheel `packages=["src/mambo_power"]`; sdist explicit allow-list (src, tests, fixtures, README, LICENSE,
  pyproject) — identical to M2.
- dependency groups: `dev` (pytest, hypothesis, pandapower, pypsa, ruff, mypy), `docs` (mkdocs-material>=9.7,
  mkdocstrings[python]>=1.0, pymdown-extensions>=10.16). No new dependency groups added this wave.

No `Makefile` exists (confirmed absent, same as M2).

From `.github/workflows/ci.yml` (4 jobs, unchanged structure from M2):
- `test` — matrix ubuntu/macos/windows × 3.12 + ubuntu 3.11, 3.13: `uv sync --locked --all-groups` → `ruff check .` →
  `ruff format --check .` → `mypy` → `pytest`; plus on ubuntu/3.12 only:
  `pytest tests/parity/test_ac_timing.py -q -s -p no:cacheprovider` (AC-7 timing figure — still AC power flow only;
  the wave brief is correct that there is no OPF/N-1 equivalent timing AC in this CI file).
- `examples` — `for f in examples/*.py; do uv run python "$f"; done`.
- `install-smoke` — `uv build`; wheel listing guard (py.typed present, no fixtures/ tests/); sdist listing guard (has
  src/mambo_power/py.typed, tests/conftest.py, fixtures/matpower/case14.m, README.md, LICENSE, pyproject.toml; none of
  .bionic/.github/.venv/uv.lock/.python-version); wheel → fresh venv `.smoke` → import +
  `matpower.load('fixtures/matpower/case14.m')`; sdist → fresh venv `.smoke2` → import.
- `docs` — `uv run mkdocs build --strict`, upload `site/`.

From `.github/workflows/pages.yml`: `build` = same `mkdocs build --strict` (on push to `epic/01-foundation`/`main`),
then `deploy-pages`. No additional check beyond the docs job. Unchanged from M2.

From `mkdocs.yml`: material theme; plugins search, autorefs, mkdocstrings (python, paths [src], sphinx docstrings);
hook `docs/hooks/rest_roles.py`; `pymdownx.snippets` with `base_path: [examples, .]` and `check_paths: true` (missing
snippet = build failure). Nav grew from M2: Manual now has **DC-OPF** (`manual/opf.md`) and **N-1 screening**
(`manual/n1.md`) pages, and API reference gained `mambo_power.opf` (`api/opf.md`) and `mambo_power.contingency`
(`api/contingency.md`) — 4 new nav entries total vs. M2's 21-page nav.

Trees: `examples/` = **8** scripts (01_load_and_validate … 08_opf_and_n1 — M2 had 7; S7 added `08_opf_and_n1.py`,
confirmed). `tests/` = 32 unit modules (incl. `test_contingency_n1.py`, `test_contingency_n1_brute_force.py`,
`test_opf_dc.py`, `test_opf_dc_case14_pwl.py`, `test_opf_dc_pwl.py`, `test_opf_pwl_guard.py`,
`test_opf_solve_dc_opf.py` — the wave's new modules), 11 parity modules (incl. `test_opf_vs_pandapower.py`, new this
wave; + `_mpc_reader.py`), 1 property module, shared `conftest.py`, `_fixtures.py`, `_brute_force_lodf.py`.
`fixtures/matpower/`. New source modules: `src/mambo_power/opf/` (`__init__.py`, `dc_opf.py`) and
`src/mambo_power/contingency/` (`__init__.py`, `n1.py`), plus `results/opf.py` and `results/n1.py`.

Windows note: the CI job's `.smoke/bin/python` is `.smoke/Scripts/python.exe` here; otherwise the sequence is
verbatim.

## Commands, exit codes, trimmed output

### 1. Sync
```
$ uv sync --locked --all-groups            # exit 0
Resolved 102 packages in 26ms
Checked 98 packages in 108ms
```

### 2. Lint / format / types
```
$ uv run --no-sync ruff check .            # exit 0
All checks passed!
$ uv run --no-sync ruff format --check .   # exit 0
126 files already formatted
$ uv run --no-sync mypy                    # exit 0
Success: no issues found in 39 source files
```
(M2 was 98 files / 31 source files — the growth to 126/39 reflects the wave's new `opf`/`contingency` modules, tests,
and fixtures.)

### 3. Pytest tiers and full run
```
$ uv run --no-sync pytest -m unit -q -p no:cacheprovider        # exit 0, wall 79.50s
397 passed, 176 deselected in 79.50s (0:01:19)
$ uv run --no-sync pytest -m parity -q -p no:cacheprovider      # exit 0, wall 141.48s
171 passed, 402 deselected, 10 warnings in 141.48s (0:02:21)
$ uv run --no-sync pytest -m property -q -p no:cacheprovider    # exit 0, wall 37.68s
5 passed, 568 deselected in 37.68s
$ uv run --no-sync pytest -q -p no:cacheprovider                # exit 0, wall 235.15s
573 passed, 10 warnings in 235.15s (0:03:55)
```
Tier sum 397 + 171 + 5 = **573 = full total**; deselected counts are the complement (176 = 171+5, 402 = 397+5,
568 = 397+171), so every test carries exactly one of the three markers and none is unmarked or skipped.

The same 10 warnings as M2, all inside pandapower's `converter/pypower/from_ppc.py` (RuntimeWarning
divide-by-zero/invalid at lines 212/223/224, FutureWarning pandas dtype at line 330), raised from
`test_matpower_vs_pandapower.py::test_counts_match_pandapower[case14/case57]` and
`test_dc_vs_pandapower.py::test_angles_match_rundcpp[case30]` /
`test_matpower_vs_pandapower.py::test_counts_match_pandapower[case30]` — oracle-side, not ours, unchanged from M2.

Ran sequentially (not concurrently) to keep timings clean; wall-time sum of the three tiers (258.66s) roughly matches
the full run (235.15s) — no unexplained contention this time, unlike M2's 2x-inflated full run.

### 4. AC-7 timing (the ubuntu/3.12 CI step)
```
$ uv run --no-sync pytest tests/parity/test_ac_timing.py -q -s -p no:cacheprovider    # exit 0, wall 4.94s
case300 AC cold 0.0396 s, warm 0.0400 s, 5 iterations
.
1 passed in 4.94s
```
**case300 cold 0.0396 s · warm 0.0400 s · 5 iterations** (threshold < 1.0 s cold) — well inside the contract, and
faster than M2's contended-box figures (0.1521/0.1825 s), consistent with an uncontended run this time.

### 5. Docs
```
$ uv run --no-sync mkdocs build --strict   # exit 0, wall 27.03s
INFO    -  Cleaning site directory
INFO    -  Building documentation to directory: C:\Claude Projects\mambo-power-m3\site
INFO    -  Documentation built in 27.03 seconds
```
`grep -ci 'warning'` on the captured log = **1**, and that single hit is the Material-for-MkDocs team's advisory
banner ("Warning from the Material for MkDocs team … MkDocs 2.0 …") printed by the theme at startup, not a build
warning — identical to M2's pattern. `--strict` would have exited non-zero on any real warning; it did not.

### 6. Examples (as ci.yml's examples job: `uv run python "$f"` for each)

| script | exit | wall | first 3 output lines |
|---|---|---|---|
| examples/01_load_and_validate.py | 0 | 1s | `case14: 14 buses, 20 branches, 5 generators, 11 loads, 1 shunts` / `base_mva: 100.0 \| slack: ['bus-1']` / `import report: 14 issue(s), codes ['BASE_KV_REPLACED']` |
| examples/02_ac_power_flow.py | 0 | 3s | `--- case14, q_limits=True` / `converged=True iterations=4 q_limit_rounds=0 max_mismatch=8.77e-13 MVA` / `pinned generators: none` |
| examples/03_dc_power_flow.py | 0 | 2s | `case300 DC: pf.dc scipy.sparse.linalg.splu converged = True` / `angles: min -19.46 deg, max 56.63 deg (slack at 0)` / `largest DC flows:` |
| examples/04_jobs_api.py | 0 | 3s | `registered kinds: ['n1', 'opf.dc', 'pf.ac', 'pf.dc']` / `pf.ac job_id=a1 status=ok result=AcPowerFlowResult converged=True slack P=232.393 MW` / `pf.dc job_id=d1 status=ok result=DcPowerFlowResult converged=True slack P=219.000 MW` |
| examples/05_roles_and_islands.py | 0 | 3s | `case14_roles: declared vs effective role where they differ` / `  bus-6: declared pv, effective pq (no in-service generator)` / `demoted PV buses: ['bus-6']` |
| examples/06_network_matrices.py | 0 | 4s | `case14 arrays: 14 buses, 20 branches, slack position 0` / `  p_load_pu[:4] = [0.    0.217 0.942 0.478]  (MW / base_mva = 100.0)` / `Ybus: (14, 14), format csc, nnz 54, density 27.6%` |
| examples/07_results_and_export.py | 0 | 3s | `JSON: 7113 bytes; round trip equal: True` / `top-level keys: [...'message'...]` / `provenance keys: ['elapsed_s', 'engine', 'kind', 'options', 'solver', 'started_at', 'version']` |
| examples/08_opf_and_n1.py | 0 | 4s | `status: Optimal  cost: 7642.59 $/h  balance dual (energy price): 39.0162 $/MWh` / `dispatch:` / `  gen-1    bus-1     220.968 MW  bound dual  0.0000` |

`registered kinds` in example 04 grew from M2's `['pf.ac', 'pf.dc']` to `['n1', 'opf.dc', 'pf.ac', 'pf.dc']` — the
jobs registry now carries this wave's two new kinds. Example 07's JSON top-level keys gained `message` vs. M2's set
(7097→7113 bytes). Example 08 is new this wave (confirms AC-9 style coverage of the OPF + N-1 surface). All 8/8 exit
0. Wall times are noticeably faster than M2's (which ran under contention from a concurrent `mkdocs serve`).

### 7. Build + install smoke (ci.yml install-smoke job)
`dist/`, `.smoke/`, `.smoke2/` did not exist beforehand.
```
$ uv build                                 # exit 0
Successfully built dist\mambo_power-0.0.1.dev0.tar.gz
Successfully built dist\mambo_power-0.0.1.dev0-py3-none-any.whl
  (wheel 82,999 B; sdist 179,633 B)

$ uv run --no-project --python 3.12 python -m zipfile -l dist/*.whl
  45 entries: mambo_power/{__init__,py.typed}, contingency/ (2), io/ (4), jobs/ (4), model/ (6), numerics/ (8),
  opf/ (2), pf/ (4), results/ (8), dist-info/{METADATA,WHEEL,licenses/LICENSE,RECORD}
  py.typed: PRESENT                                             # guard exit 0
  no (fixtures|tests)/ paths                                    # guard exit 0

$ tar -tzf dist/*.tar.gz                   # 108 entries
  has src/mambo_power/py.typed, tests/conftest.py, fixtures/matpower/case14.m, README.md, LICENSE, pyproject.toml   # exit 0 (all 6 required paths present)
  none of .bionic/.github/.venv/uv.lock/.python-version                                                             # exit 0

$ uv venv .smoke --python 3.12             # exit 0
$ uv pip install --python .smoke dist/*.whl                                  # exit 0
$ uv pip list --python .smoke
  annotated-types 0.8.0, highspy 1.15.1, mambo-power 0.0.1.dev0, numpy 2.5.2, pydantic 2.13.4, pydantic-core 2.46.4,
  scipy 1.18.1, typing-extensions 4.16.0, typing-inspection 0.4.4          (no dev/docs packages — clean venv)
$ .smoke/Scripts/python.exe -c "import mambo_power; from mambo_power.io import matpower; n = matpower.load('fixtures/matpower/case14.m'); print(mambo_power.__version__, len(n.buses))"
0.0.1.dev0 14                              # exit 0

$ uv venv .smoke2 --python 3.12            # exit 0
$ uv pip install --python .smoke2 dist/*.tar.gz                              # exit 0
$ .smoke2/Scripts/python.exe -c "import mambo_power; print('sdist install ok', mambo_power.__version__)"
sdist install ok 0.0.1.dev0                # exit 0

$ rm -rf .smoke .smoke2 dist; git status --porcelain      # (empty)
```
Note: `scipy` resolved to `1.18.1` inside the clean smoke venvs vs. `1.18.0` in the dev `.venv` — both satisfy the
package's unpinned `scipy` dependency; not a version drift in the locked dev environment (`uv.lock` unaffected,
confirmed by `git status --porcelain` staying empty).

### 8. Stack-health snapshot
```
$ uv run --no-sync python -c "import sys, numpy, scipy, pydantic, highspy; print(sys.version); print(numpy.__version__, scipy.__version__, pydantic.__version__)"   # exit 0
3.12.14 (main, Aug 14 2026, 15:40:22) [MSC v.1944 64 bit (AMD64)]
2.5.2 1.18.0 2.13.4
```
(`highspy` has no `__version__` attribute exposed at import; version below is from `uv pip list`.)

| package | version | | package | version |
|---|---|---|---|---|
| numpy | 2.5.2 | | pytest | 9.1.1 |
| scipy | 1.18.0 (dev venv) / 1.18.1 (smoke venvs) | | hypothesis | 6.165.10 |
| highspy | 1.15.1 | | ruff | 0.16.4 |
| pydantic | 2.13.4 | | mypy | 2.3.1 |
| pandapower | 3.3.0 | | mkdocs-material | 9.7.7 |
| pypsa | 1.2.4 (unchanged from M2 — used as an oracle-diagnostic dependency by S3; no version bump this wave) | | mkdocstrings | 1.0.6 |
| | | | mkdocstrings-python | 2.0.7 |
| | | | pymdown-extensions | 11.0.1 |

All dev-group tool versions are identical to M2's snapshot; only `scipy`'s micro version differs between the locked
dev venv and freshly resolved smoke venvs (see note in §7).

### 9. Timing: `opf.solve_dc_opf` and `contingency.n1` on case300 (cold, fresh subprocess)

No explicit timing AC exists for OPF/N-1 in this wave (unlike M2's AC-7 for AC power flow) — this measurement is
**useful-but-not-a-gating-number**, recorded for M4 (which composes `opf.dc_opf` directly) to have a baseline.
Script ran via `uv run --no-sync python <script>` invoking a fresh `subprocess.run([sys.executable, "-c", ...])`,
mirroring `test_ac_timing.py`'s cold-measurement pattern (first call in a brand-new interpreter):
```
opf_cold=0.3943s opf_status=Optimal
n1_cold=0.7559s n1_contingencies=0
```
**case300 `opf.solve_dc_opf` cold: 0.3943 s** (status Optimal). **case300 `contingency.n1` cold: 0.7559 s**
(0 outages flagged by the LODF screen — the default `N1Options` threshold isn't tripped by any branch outage on this
fixture; not a correctness concern, `contingency.n1` is exercised more thoroughly under non-trivial threshold options
elsewhere in `tests/unit/test_contingency_n1.py` and `tests/parity/test_opf_vs_pandapower.py`). Both figures are on
an uncontended Windows box (no concurrent processes observed this run) and both are cold-interpreter first calls, so
they include import/JIT/first-factorization costs.

## Summary table

| suite | cmd | pass | total | exit | wall |
|---|---|---|---|---|---|
| sync | `uv sync --locked --all-groups` | – | – | 0 | <1 s |
| lint | `uv run --no-sync ruff check .` | – | – | 0 | <1 s |
| format | `uv run --no-sync ruff format --check .` | 126 files | 126 | 0 | <1 s |
| types | `uv run --no-sync mypy` | 39 files | 39 | 0 | <1 s |
| unit | `uv run --no-sync pytest -m unit -q -p no:cacheprovider` | 397 | 397 | 0 | 79.5 s |
| parity | `uv run --no-sync pytest -m parity -q -p no:cacheprovider` | 171 | 171 | 0 | 141.5 s |
| property | `uv run --no-sync pytest -m property -q -p no:cacheprovider` | 5 | 5 | 0 | 37.7 s |
| full | `uv run --no-sync pytest -q -p no:cacheprovider` | 573 | 573 | 0 | 235.2 s |
| AC-7 timing | `uv run --no-sync pytest tests/parity/test_ac_timing.py -q -s -p no:cacheprovider` | 1 | 1 | 0 | 4.9 s |
| docs | `uv run --no-sync mkdocs build --strict` | – | 0 real warnings | 0 | 27.0 s |
| examples | `uv run --no-sync python examples/*.py` (×8) | 8 | 8 | 0 | 23 s |
| build | `uv build` | wheel + sdist | 2 | 0 | – |
| wheel guards | py.typed present · no fixtures/tests | 2 | 2 | 0 | – |
| sdist guards | 6 required paths · nothing machine-local | 7 | 7 | 0 | – |
| install-smoke wheel | fresh venv → install → import + case14 (14 buses) | 1 | 1 | 0 | – |
| install-smoke sdist | fresh venv → install → import | 1 | 1 | 0 | – |
| stack | python/numpy/scipy/pydantic/highspy import | – | – | 0 | – |

**Timing figures (informational, non-gating):**
- AC-7 (CI-contracted): case300 AC cold **0.0396 s**, warm **0.0400 s**, 5 iterations.
- M3 baseline for M4 (not a gate): case300 `opf.solve_dc_opf` cold **0.3943 s**; case300 `contingency.n1` cold
  **0.7559 s**.

## Stack-health: before/after test count

| | tests | source |
|---|---|---|
| before (M2 close) | **492** | `.bionic/docs/record/m2-r1-fold-report.md:268` and `.bionic/docs/record/m2-r2-reaudit.md:191` (`492 passed, 10 warnings`) — the wave-close count after M2's R1 fold added 8 tests on top of the 484 recorded at M2's own step-5 floor (`m2-step5-tests-floor.md`) |
| after (M3 head f37815a) | **573** | this run, §3 above |
| delta | **+81** | new `opf`/`contingency`/`results.opf`/`results.n1` modules, PWL tests, OPF-vs-pandapower parity, N-1 unit + brute-force tests |

Python 3.12.14 throughout; no interpreter change from M2.

Raw logs: `C:\Users\mambo\AppData\Local\Temp\claude\C--Claude-Projects-mambo-power\a52e3226-9462-49b6-aa26-2d629b247419\scratchpad\{01-20}*.log`.
