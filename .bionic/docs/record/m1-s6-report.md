# M1 S6 report — install smoke: wheel/sdist build config, py.typed shipped, install-smoke CI job, packaging metadata test

Agent: m1-s6 · 2026-08-20 · worktree `C:\Claude Projects\mambo-power-m1`, branch `wave/01-substrate`
Base: fc68535 (S5 numerics) → **commit 36bd20aefae9bd5da20ed63fac49ff53815bf0ae** (not pushed).
Every claim below carries its command and trimmed output, or is labelled `unverified`.

**Read this first.** AC-8's wheel path was already green at fc68535 — `py.typed` shipped, no
`fixtures/` or `tests/` in the wheel, and the import + case14 load exited 0 from a clean venv.
The real RED was the **sdist**: hatch's VCS default followed the worktree's machine-local
`.bionic -> C:\Claude Projects\mambo-power\.bionic` symlink and shipped the entire planning tree
(specs, plans, ADRs, every slice report, progress files), plus `.github/`, `uv.lock`,
`.python-version`, `.gitattributes` — 283 KB. An explicit `[tool.hatch.build.targets.sdist]
include` list fixes it (58 KB) and the new CI job guards both artifacts. No `src/` change, no
dependency change. The CI job has **not run on GitHub** (nothing pushed) — its steps were replayed
locally on Windows (§4) with `.smoke/Scripts/python.exe` in place of `.smoke/bin/python`.

## 1. Delivered

| Path | Contents |
|---|---|
| `pyproject.toml` (+13) | `[tool.hatch.build.targets.sdist] include = ["/src/mambo_power", "/tests", "/fixtures", "/README.md", "/LICENSE", "/pyproject.toml"]`; wheel config unchanged (`packages = ["src/mambo_power"]`) |
| `tests/unit/test_packaging_metadata.py` (+40, 3 tests) | `importlib.metadata.version("mambo-power")` matches the canonical PEP 440 regex (inlined — `packaging` is not a declared dependency); `mambo_power.__version__` equals it; `py.typed` is a file inside the installed package |
| `.github/workflows/ci.yml` (+58) | job `install-smoke` (ubuntu-latest, py3.12, `needs: []`): `uv build` → wheel listing must contain `py.typed` and no `fixtures/`/`tests/` path → sdist listing must contain `src/mambo_power/py.typed`, `tests/conftest.py`, `fixtures/matpower/case14.m`, README, LICENSE, pyproject and nothing under `.bionic`, `.github`, `.venv`, `uv.lock`, `.python-version` → `uv venv .smoke` + `uv pip install` wheel (no project, no dev group) + AC-8 command → `uv venv .smoke2` + sdist install + import |

## 2. RED — state at fc68535

`uv build` → exit 0 (`Successfully built dist\mambo_power-0.0.1.dev0.tar.gz` / `...-py3-none-any.whl`).

Wheel (`uv run python -m zipfile -l dist/mambo_power-*.whl`, 19 entries): `mambo_power/__init__.py`,
`mambo_power/py.typed` (size 0), `io/{__init__,matpower,native}.py`,
`model/{__init__,entities,errors,network}.py`, `numerics/{__init__,arrays,bbus,lodf,ptdf,ybus}.py`,
`dist-info/{METADATA,WHEEL,licenses/LICENSE,RECORD}`. **Already correct** — no fixtures, no tests,
`py.typed` present.

Sdist (`tar -tzf dist/mambo_power-*.tar.gz`, 283 755 bytes, 73 entries) — **RED**, trimmed:

```
mambo_power-0.0.1.dev0/.gitattributes
mambo_power-0.0.1.dev0/.python-version
mambo_power-0.0.1.dev0/uv.lock
mambo_power-0.0.1.dev0/.bionic/.gitignore
mambo_power-0.0.1.dev0/.bionic/docs/adrs/epic-01-foundation/adr-001-python-foundation.md
... (4 ADRs, 2 plans, 2 specs, 7 record files, 6 tmp progress files — 23 entries under .bionic/)
mambo_power-0.0.1.dev0/.github/workflows/ci.yml
mambo_power-0.0.1.dev0/fixtures/matpower/case14.m   (+ 6 more fixture files)
mambo_power-0.0.1.dev0/src/mambo_power/...           (15 files)
mambo_power-0.0.1.dev0/tests/...                     (17 files)
mambo_power-0.0.1.dev0/.gitignore, LICENSE, README.md, pyproject.toml, PKG-INFO
```

Cause: `ls -la` → `.bionic -> /c/Claude Projects/mambo-power/.bionic` (symlink; `git ls-files
.bionic` → 0 tracked files; `git check-ignore -v` → `.bionic/.gitignore:1:*`). Hatch's default
sdist walk follows the link and does not honour the nested `.gitignore` on the far side.

Fresh-venv wheel install at fc68535 (scratch venv, `uv venv --python 3.12`, `uv pip install
--python <venv> dist/mambo_power-*.whl`) → exit 0, 9 packages (annotated-types, highspy 1.15.1,
mambo-power 0.0.1.dev0, numpy 2.5.2, pydantic 2.13.4, pydantic-core, scipy 1.18.0,
typing-extensions, typing-inspection — no pytest/pandapower/pypsa). AC-8 command from the worktree
root → prints `0.0.1.dev0 14`, **exit 0**. Sdist install into a second scratch venv + `import
mambo_power` → exit 0. So: wheel path GREEN before S6; sdist content RED; no CI job; no metadata test.

## 3. GREEN — build after the change

`uv build` → exit 0. `ls -la dist/` → wheel 23 313 B (unchanged), sdist **57 597 B** (was 283 755).

Wheel listing: identical to §2 (19 entries). Checks: `grep -Eq '(^|/)py\.typed[[:space:]]'` →
`py.typed present`; `grep -E '(^|/)(fixtures|tests)/'` → no match → `no fixtures/ or tests/ in wheel`.

Sdist listing (45 entries): `fixtures/matpower/{PROVENANCE.md,SOURCES.md,case118.m,case14.m,case30.m,case57.m,case_ieee30.m}`,
`src/mambo_power/**` (15 incl. `py.typed`), `tests/**` (18 incl. the new test and `snapshots/network.schema.json`),
`.gitignore`, `LICENSE`, `README.md`, `pyproject.toml`, `PKG-INFO`. Checks: all six required paths
`has ...`; machine-local grep → no match → `no machine-local files in sdist`. (`.gitignore` and
`PKG-INFO` are hatch's always-included files; the CI guard deliberately does not forbid them.)

## 4. Local replay of the `install-smoke` job (Windows, worktree root, PATH += uv dir)

| CI step | Local command | Exit | Output (trimmed) |
|---|---|---|---|
| `uv build` | same | 0 | two `Successfully built` lines |
| wheel check | `uv run --no-project --python 3.12 python -m zipfile -l dist/*.whl` + greps | 0 | `py.typed present`, `no fixtures/ or tests/ in wheel` |
| sdist check | `tar -tzf dist/*.tar.gz` + greps | 0 | six `has ...` lines, `no machine-local files in sdist` |
| wheel venv | `uv venv .smoke --python 3.12`; `uv pip install --python .smoke dist/*.whl`; `uv pip list --python .smoke` | 0 | 9 packages, `Using Python 3.12.14 environment at: .smoke` |
| AC-8 | `.smoke/Scripts/python.exe -c "import mambo_power; from mambo_power.io import matpower; n = matpower.load('fixtures/matpower/case14.m'); print(mambo_power.__version__, len(n.buses))"` | **0** | `0.0.1.dev0 14` |
| sdist venv | `uv venv .smoke2 --python 3.12`; `uv pip install --python .smoke2 dist/*.tar.gz`; `.smoke2/Scripts/python.exe -c "import mambo_power; print('sdist install ok', mambo_power.__version__)"` | 0 | `sdist install ok 0.0.1.dev0` |

YAML sanity: `yaml.safe_load(ci.yml)` → `jobs: ['test', 'install-smoke']`, 9 steps in `install-smoke`.
`unverified`: the job on GitHub Actions itself (branch not pushed; `needs: []` and the
`uv run --no-project` invocation are exercised only locally).

## 5. GREEN gate

| Command | Exit | Output |
|---|---|---|
| `uv run ruff check .` | 0 | `All checks passed!` |
| `uv run ruff format --check .` | 0 | `32 files already formatted` |
| `uv run mypy` | 0 | `Success: no issues found in 14 source files` |
| `uv run pytest tests/unit/test_packaging_metadata.py -v` | 0 | 3 passed (`test_distribution_version_is_pep440`, `test_dunder_version_matches_distribution_metadata`, `test_py_typed_marker_ships_inside_the_package`) |
| `uv run pytest` | 0 | `175 passed, 9 warnings in 10.11s` (warnings: pre-existing pandas FutureWarning from pandapower's `from_ppc`) |

## 6. Cleanup and commit

`rm -rf dist .smoke .smoke2` + scratch venvs. `git status --porcelain` before commit: exactly
` M .github/workflows/ci.yml`, ` M pyproject.toml`, `?? tests/unit/test_packaging_metadata.py`;
after commit: empty. No hook fired.

```
commit 36bd20aefae9bd5da20ed63fac49ff53815bf0ae
    feat(m1/S6): install smoke — wheel/sdist build config, py.typed shipped, install-smoke CI job, packaging metadata test

    Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>
    Claude-Session: https://claude.ai/code/session_01NA3xnvrFVGDqG3azRk8CBs

 .github/workflows/ci.yml              | 58 +++++++++++++++++++++++++++++++++++
 pyproject.toml                        | 13 ++++++++
 tests/unit/test_packaging_metadata.py | 40 ++++++++++++++++++++++++
 3 files changed, 111 insertions(+)
```

## 7. Judgment calls

1. **Sdist allow-list instead of an exclude list.** The leak came from a symlink to a path outside
   the repo; excluding `.bionic` would fix today's symptom only. The include list is the contract
   the plan row names (src, tests, fixtures, README, LICENSE, pyproject) and is guarded in CI.
2. **PEP 440 regex inlined** rather than importing `packaging.version`. `packaging` is only a
   transitive dependency of pytest; importing it would create an undeclared dependency the brief
   forbids adding.
3. **Third assertion added to the metadata test** (`py.typed` reachable via `importlib.resources`).
   Not in the brief, but it is the only place the normal suite can catch the marker going missing
   before the wheel job does; zero cost.
4. **Sdist content guard added to CI** beyond the brief's wheel-only guard — it is the regression
   test for the RED actually found.
5. **`needs: []` kept as written in the brief.** It is a no-op (jobs without `needs` already run in
   parallel) but documents the intent; drop it if actionlint ever objects.
6. **Fixtures are read relative to the repo root in CI**, not from the wheel, exactly as the AC
   states; the wheel stays package-only.
