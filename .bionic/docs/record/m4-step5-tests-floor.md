# M4 Step 5 — tests floor (wave head)

**Wave:** M4 "nodal-market" · branch `wave/04-nodal-market` · worktree `C:\Claude Projects\mambo-power-m4`
**Run:** 2026-08-24, Windows 11 Pro, Python 3.12.14 (`.python-version` = 3.12), uv 0.12.5
**Mode:** read-only — no edits, commits or pushes by this agent. Every command below ran from the worktree root with
`UV=C:\Users\mambo\AppData\Roaming\Python\Python314\Scripts\uv.exe` (`uv` is not on PATH).

## Verdict

**GREEN on wave head aa53140 — every command exited 0.** 646/646 tests, lint/format/mypy clean, `mkdocs build
--strict` clean, 9/9 examples, wheel + sdist build/install/guards pass.

## Head: aa53140

- **Pre-check:** `git status --porcelain` empty, `git branch --show-current` = `wave/04-nodal-market`,
  `git rev-parse --short HEAD` = `aa53140` — matches the brief exactly, no re-ratification needed.
- **Post-check (after cleaning `dist/`/`.smoke*`/`site/`):** `git status --porcelain` empty; HEAD unchanged at
  `aa53140`. No edits or commits made by this agent at any point.

## Discovered suite inventory

From `pyproject.toml` (unchanged shape from M3):
- `[tool.pytest.ini_options]` — `testpaths=["tests"]`, `addopts="-ra --strict-markers --import-mode=importlib"`,
  `pythonpath=["."]`; markers `unit` (tests/unit), `parity` (tests/parity, pandapower/PyPSA oracles), `property`
  (tests/property, hypothesis). No new markers.
- `[tool.ruff]` line-length 100, py311, `extend-exclude=[".bionic"]`; lint select `E F I UP B`. Unchanged.
- `[tool.mypy]` strict, `files=["src"]`; overrides ignore missing imports for pandapower/pypsa/highspy/scipy.
  Unchanged.
- `[tool.hatch]` wheel `packages=["src/mambo_power"]`; sdist explicit allow-list (src, tests, fixtures, README,
  LICENSE, pyproject) — identical to M3.
- dependency groups: `dev` (pytest, hypothesis, pandapower, pypsa, ruff, mypy), `docs` (mkdocs-material>=9.7,
  mkdocstrings[python]>=1.0, pymdown-extensions>=10.16). No new dependency groups added this wave.

No `Makefile` exists (confirmed absent, same as M2/M3).

From `.github/workflows/ci.yml` (4 jobs, unchanged structure from M3):
- `test` — matrix ubuntu/macos/windows × 3.12 + ubuntu 3.11, 3.13: `uv sync --locked --all-groups` → `ruff check .` →
  `ruff format --check .` → `mypy` → `pytest`; plus on ubuntu/3.12 only:
  `pytest tests/parity/test_ac_timing.py -q -s -p no:cacheprovider` (AC-7 timing figure — still AC power flow only;
  no OPF/N-1/market timing AC exists in this CI file, matching M3's observation — none was added this wave either).
- `examples` — `for f in examples/*.py; do uv run python "$f"; done`.
- `install-smoke` — `uv build`; wheel listing guard (py.typed present, no fixtures/ tests/); sdist listing guard (has
  src/mambo_power/py.typed, tests/conftest.py, fixtures/matpower/case14.m, README.md, LICENSE, pyproject.toml; none
  of .bionic/.github/.venv/uv.lock/.python-version); wheel → fresh venv `.smoke` → import +
  `matpower.load('fixtures/matpower/case14.m')`; sdist → fresh venv `.smoke2` → import.
- `docs` — `uv run mkdocs build --strict`, upload `site/`.

From `.github/workflows/pages.yml`: unchanged from M3 — same `mkdocs build --strict` (on push to
`epic/01-foundation`/`main`), then `deploy-pages`.

From `mkdocs.yml`: material theme; plugins search, autorefs, mkdocstrings (python, paths [src], sphinx docstrings);
hook `docs/hooks/rest_roles.py`; `pymdownx.snippets` with `base_path: [examples, .]` and `check_paths: true` (missing
snippet = build failure). Nav grew from M3: Manual gained **Nodal market** (`manual/market.md`), and API reference
gained `mambo_power.market` (`api/market.md`) — 2 new nav entries vs. M3's 25-page nav.

Trees: `examples/` = **9** scripts (01_load_and_validate … 09_nodal_market — M3 had 8; S7 added `09_nodal_market.py`,
confirmed). `tests/` = 36 unit modules (incl. `test_bids.py`, `test_load_bid_scenario.py`, `test_market_nodal.py`,
`test_opf_dc_demand.py` — the wave's new modules, growth of 4 vs. M3's 32), 12 parity modules (incl.
`test_market_nodal_vs_pandapower.py`, new this wave; + `_mpc_reader.py`, growth of 1 vs. M3's 11), 1 property module
(unchanged), shared `conftest.py`, `_fixtures.py`, `_brute_force_lodf.py`, `_brute_force_n1.py`, `_rated.py`, plus
`_bids.py` (new this wave — test-time bid derivation helper, S5 fixtures-oracle, spec Assumption a). `fixtures/
matpower/` unchanged (no new fixture data committed — bids are derived at test time from existing fixtures, per
`tests/_bids.py`'s own module docstring). New source modules: `src/mambo_power/market/` (`__init__.py`, `nodal.py`)
and `src/mambo_power/results/market.py`; `src/mambo_power/model/scenario.py` present (Scenario/LoadBid domain
additions, S1).

Windows note: the CI job's `.smoke/bin/python` is `.smoke/Scripts/python.exe` here; otherwise the sequence is
verbatim.

## Commands, exit codes, trimmed output

### 1. Sync
```
$ uv sync --locked --all-groups            # exit 0
Resolved 102 packages in 103ms
Checked 98 packages in 131ms
```

### 2. Lint / format / types
```
$ uv run --no-sync ruff check .            # exit 0
All checks passed!
$ uv run --no-sync ruff format --check .   # exit 0
140 files already formatted
$ uv run --no-sync mypy                    # exit 0 (bare, no positional arg — per this wave's documented mypy-.
                                            #   double-count quirk)
Success: no issues found in 43 source files
```
(M3 was 126 files / 39 source files — the growth to 140/43 reflects the wave's new `market` module, `Scenario`/
`LoadBid` domain types, bid-derivation tests, and fixtures.)

### 3. Pytest tiers and full run
```
$ uv run --no-sync pytest -m unit -q -p no:cacheprovider        # exit 0, wall 121.04s
446 passed, 200 deselected in 121.04s (0:02:01)
$ uv run --no-sync pytest -m parity -q -p no:cacheprovider      # exit 0, wall 283.35s
195 passed, 451 deselected, 10 warnings in 283.35s (0:04:43)
$ uv run --no-sync pytest -m property -q -p no:cacheprovider    # exit 0, wall 41.97s
5 passed, 641 deselected in 41.97s
$ uv run --no-sync pytest -q -p no:cacheprovider                # exit 0, wall 105.14s
646 passed, 10 warnings in 105.14s (0:01:45)
```
Tier sum 446 + 195 + 5 = **646 = full total**; deselected counts are the complement (200 = 195+5, 451 = 446+5,
641 = 446+195), so every test carries exactly one of the three markers and none is unmarked or skipped.

**Timing anomaly, noted honestly:** unlike M3 (whose tier-sum wall time roughly matched its full-run wall time), this
run's tier sum is 446.36 s but the single full run took only 105.14 s — a ~4x gap. The most likely explanation:
session-scoped fixtures (pandapower/PyPSA oracle setup) and heavy compiled-package imports (scipy, pandapower) get
built/imported once per pytest process; running the three tiers as three separate invocations pays that cost three
times, while the single full-suite invocation pays it once. An initial foreground attempt at the full run (before the
one recorded above) ran past a 400 s timeout and was killed, consistent with cold-cache/first-invocation costs on
this Windows box (plausibly Defender scanning freshly-touched DLLs) that later runs, including the tiers-then-full
sequence recorded here, did not repeat. This is informational only — it affects wall-time interpretation, not the
pass/total counts, which are internally consistent (tier sum = full total, complements check out).

The same 10 warnings as M3, all inside pandapower's `converter/pypower/from_ppc.py` (RuntimeWarning
divide-by-zero/invalid at lines 212/223/224, FutureWarning pandas dtype at line 330), raised from
`test_matpower_vs_pandapower.py::test_counts_match_pandapower[case14/case57]` and
`test_dc_vs_pandapower.py::test_angles_match_rundcpp[case30]` /
`test_matpower_vs_pandapower.py::test_counts_match_pandapower[case30]` — oracle-side, not ours, unchanged from M3.

### 4. AC-7 timing (the ubuntu/3.12 CI step)
Not re-run as a separate step this time (already exercised inside the full-suite and parity-tier runs above, which
both include `tests/parity/test_ac_timing.py` and passed with the suite). No OPF/N-1/market equivalent timing AC
exists in this wave's CI either — confirmed by inspection of `ci.yml` (§ discovered suite inventory above).

### 5. Docs
```
$ uv run --no-sync mkdocs build --strict   # exit 0, wall 17.88s
INFO    -  Cleaning site directory
INFO    -  Building documentation to directory: C:\Claude Projects\mambo-power-m4\site
INFO    -  Documentation built in 17.88 seconds
```
`grep -ci 'warning'` on the captured log = **1**, and that single hit is the Material-for-MkDocs team's advisory
banner ("Warning from the Material for MkDocs team … MkDocs 2.0 …") printed by the theme at startup, not a build
warning — identical to M3's pattern. `--strict` would have exited non-zero on any real warning; it did not.

### 6. Examples (as ci.yml's examples job: `uv run python "$f"` for each)

| script | exit | wall | first 3 output lines |
|---|---|---|---|
| examples/01_load_and_validate.py | 0 | 0s | `case14: 14 buses, 20 branches, 5 generators, 11 loads, 1 shunts` / `base_mva: 100.0 \| slack: ['bus-1']` / `import report: 14 issue(s), codes ['BASE_KV_REPLACED']` |
| examples/02_ac_power_flow.py | 0 | 2s | `--- case14, q_limits=True` / `converged=True iterations=4 q_limit_rounds=0 max_mismatch=8.77e-13 MVA` / `pinned generators: none` |
| examples/03_dc_power_flow.py | 0 | 2s | `case300 DC: pf.dc scipy.sparse.linalg.splu converged = True` / `angles: min -19.46 deg, max 56.63 deg (slack at 0)` / `largest DC flows:` |
| examples/04_jobs_api.py | 0 | 1s | `registered kinds: ['market.nodal', 'n1', 'opf.dc', 'pf.ac', 'pf.dc']` / `pf.ac job_id=a1 status=ok result=AcPowerFlowResult converged=True slack P=232.393 MW` / `pf.dc job_id=d1 status=ok result=DcPowerFlowResult converged=True slack P=219.000 MW` |
| examples/05_roles_and_islands.py | 0 | 2s | `case14_roles: declared vs effective role where they differ` / `  bus-6: declared pv, effective pq (no in-service generator)` / `demoted PV buses: ['bus-6']` |
| examples/06_network_matrices.py | 0 | 2s | `case14 arrays: 14 buses, 20 branches, slack position 0` / `  p_load_pu[:4] = [0.    0.217 0.942 0.478]  (MW / base_mva = 100.0)` / `Ybus: (14, 14), format csc, nnz 54, density 27.6%` |
| examples/07_results_and_export.py | 0 | 2s | `JSON: 7113 bytes; round trip equal: True` / `top-level keys: [...'message'...]` / `provenance keys: ['elapsed_s', 'engine', 'kind', 'options', 'solver', 'started_at', 'version']` |
| examples/08_opf_and_n1.py | 0 | 1s | `status: Optimal  cost: 7642.59 $/h  balance dual (energy price): 39.0162 $/MWh` / `dispatch:` / `  gen-1    bus-1     220.968 MW  bound dual  0.0000` |
| examples/09_nodal_market.py | 0 | 1s | `status: Optimal` / `dispatch:` / `  gen  g1   bus b1   30.000 MW  bound dual   0.000` |

`registered kinds` in example 04 grew from M3's `['n1', 'opf.dc', 'pf.ac', 'pf.dc']` to `['market.nodal', 'n1',
'opf.dc', 'pf.ac', 'pf.dc']` — the jobs registry now carries this wave's new `market.nodal` kind (S6). Example 09 is
new this wave, on a hand-built 2-bus network (not a MATPOWER fixture) — it shows the elastic-demand PWL bid clearing,
the LMP energy/congestion decomposition reused verbatim from `opf.lmp_decomposition` (ADR-006), and the settlement
identity (`load payment − generator receipts == congestion rent`, confirmed `True`). All 9/9 exit 0.

### 7. Build + install smoke (ci.yml install-smoke job)
`dist/`, `.smoke/`, `.smoke2/` did not exist beforehand.
```
$ uv build                                 # exit 0
Successfully built dist\mambo_power-0.0.1.dev0.tar.gz
Successfully built dist\mambo_power-0.0.1.dev0-py3-none-any.whl
  (wheel 95,742 B; sdist 209,504 B)

$ uv run --no-project --python 3.12 python -m zipfile -l dist/*.whl
  49 entries: mambo_power/{__init__,py.typed}, contingency/ (2), io/ (4), jobs/ (4), market/ (2, new this wave),
  model/ (7), numerics/ (8), opf/ (2), pf/ (4), results/ (9, incl. new market.py), dist-info/{METADATA,WHEEL,
  licenses/LICENSE,RECORD}
  py.typed: PRESENT                                             # guard exit 0
  no (fixtures|tests)/ paths                                    # guard exit 0

$ tar -tzf dist/*.tar.gz                   # 119 entries
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

$ rm -rf .smoke .smoke2 dist site; git status --porcelain      # (empty)
```
Note: `scipy` resolved to `1.18.1` inside the clean smoke venvs vs. `1.18.0` in the dev `.venv` — same drift pattern
as M3, both satisfy the package's unpinned `scipy` dependency; `uv.lock` unaffected (`git status --porcelain` stayed
empty).

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
| pypsa | 1.2.4 (unchanged from M3 — oracle-diagnostic dependency only) | | mkdocstrings | 1.0.6 |
| | | | mkdocstrings-python | 2.0.7 |
| | | | pymdown-extensions | 11.0.1 |

Every package version is **identical to M3's snapshot** — no version drift at all this wave (only `scipy`'s micro
version differs between the locked dev venv and freshly resolved smoke venvs, as in M3, see note in §7).

### 9. Timing: `market.solve_nodal` on case14 (cold, fresh process, bids derived via `tests._bids.with_bids`)

No explicit timing AC exists for the nodal market in this wave (matching M3's own OPF/N-1 baseline note) — this
measurement is **useful-but-not-a-gating-number**, recorded for future waves to have a baseline. Ran via
`uv run --no-sync python <script>` (a fresh interpreter per invocation — the same "cold, first call" property
`test_ac_timing.py` gets from `subprocess.run`), attaching bids to every case14 load with `tests._bids.with_bids`
(the same test-time derivation `tests/unit/test_market_nodal.py` and `tests/parity/test_market_nodal_vs_pandapower.py`
use — no new fixture data):
```
market_nodal_cold=0.0208s status=Optimal
```
**case14 `market.solve_nodal` cold: 0.0208 s** (status Optimal). Far under M3's case300 `opf.solve_dc_opf` cold
baseline (0.3943 s) — expected, since case14 is a much smaller network than case300 and `market.solve_nodal` reuses
`opf`'s LP machinery (ADR-006) rather than adding new solver overhead. Uncontended Windows box, cold-interpreter
first call, so this includes import/JIT/first-factorization costs.

## Summary table

| suite | cmd | pass | total | exit | wall |
|---|---|---|---|---|---|
| sync | `uv sync --locked --all-groups` | – | – | 0 | <1 s |
| lint | `uv run --no-sync ruff check .` | – | – | 0 | <1 s |
| format | `uv run --no-sync ruff format --check .` | 140 files | 140 | 0 | <1 s |
| types | `uv run --no-sync mypy` | 43 files | 43 | 0 | <1 s |
| unit | `uv run --no-sync pytest -m unit -q -p no:cacheprovider` | 446 | 446 | 0 | 121.0 s |
| parity | `uv run --no-sync pytest -m parity -q -p no:cacheprovider` | 195 | 195 | 0 | 283.4 s |
| property | `uv run --no-sync pytest -m property -q -p no:cacheprovider` | 5 | 5 | 0 | 42.0 s |
| full | `uv run --no-sync pytest -q -p no:cacheprovider` | 646 | 646 | 0 | 105.1 s |
| docs | `uv run --no-sync mkdocs build --strict` | – | 0 real warnings | 0 | 17.9 s |
| examples | `uv run --no-sync python examples/*.py` (×9) | 9 | 9 | 0 | ~13 s |
| build | `uv build` | wheel + sdist | 2 | 0 | – |
| wheel guards | py.typed present · no fixtures/tests | 2 | 2 | 0 | – |
| sdist guards | 6 required paths · nothing machine-local | 7 | 7 | 0 | – |
| install-smoke wheel | fresh venv → install → import + case14 (14 buses) | 1 | 1 | 0 | – |
| install-smoke sdist | fresh venv → install → import | 1 | 1 | 0 | – |
| stack | python/numpy/scipy/pydantic/highspy import | – | – | 0 | – |

**Timing figures (informational, non-gating):**
- M3 baseline (unchanged this wave, not re-run separately): case300 AC cold **0.0396 s**, warm **0.0400 s** (AC-7,
  CI-contracted); case300 `opf.solve_dc_opf` cold **0.3943 s**; case300 `contingency.n1` cold **0.7559 s**.
- M4 baseline for future waves (not a gate): case14 `market.solve_nodal` cold **0.0208 s**.

## Stack-health: before/after test count

| | tests | source |
|---|---|---|
| before (M3 close, wave/03-opf-n1 merged into epic/01-foundation) | **596** | `5fa3285`'s own merge commit message: "…DC-OPF (LP/QP) … AC-feasibility check, jobs API, docs site, examples (**596 tests**, CI 32781551954 success on wave head 4bd67d9)" — the count as of the merge, which is *higher* than the 573 recorded in `.bionic/docs/record/m3-step5-tests-floor.md` because M3's own R3 fold (`4bd67d9`, chore(m3/R3): fold review + critic) landed **after** that step-5 floor doc was written and added tests before the merge into `epic/01-foundation` (which M4 branched from). The merge commit message is authoritative for "what M4 actually started from," so it is used here rather than the step-5 snapshot. |
| after (M4 head aa53140) | **646** | this run, §3 above |
| delta | **+50** | new `market` module (`market.nodal`), `Scenario`/`LoadBid` domain additions (S1), elastic-demand LP columns/rows in `opf` (S3), `market.nodal` jobs kind (S6), bid-derivation test helper + parity vs. pandapower `sgen` (S5) — concretely: 4 new unit modules (`test_bids.py`, `test_load_bid_scenario.py`, `test_market_nodal.py`, `test_opf_dc_demand.py`) and 1 new parity module (`test_market_nodal_vs_pandapower.py`), plus additional cases inside existing modules |

Python 3.12.14 throughout; no interpreter change from M3.

Raw logs: `C:\Users\mambo\AppData\Local\Temp\claude\C--Claude-Projects-mambo-power\a52e3226-9462-49b6-aa26-2d629b247419\scratchpad\{01-17}*.log`.
