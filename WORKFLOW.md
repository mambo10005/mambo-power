# Repository contract

This file is prepended to every agent prompt in this repository. Keep it short; it is paid for on every call.

## What this is

`mambo-power`: a public, MIT-licensed Python package for power system analysis and electricity market modelling, on PyPI. It owns its network data model (`mambo_power.model`, pydantic v2) and implements its own solvers on numpy, scipy and HiGHS. The public decision log is `docs/design/decisions.md` (ADR-NNN); read the ADRs your task names. `docs/contributing.md` is the long form of this file.

## Architecture rules

- **Runtime dependencies are exactly `numpy`, `scipy`, `highspy`, `pydantic`.** Anything else is stdlib or a dev/docs group dependency.
- **pandapower and PyPSA are test oracles only.** Nothing under `src/` imports them; tests under `tests/parity/` do.
- **Physical units in the model; per-unit only inside `NetworkArrays`** (the single conversion site).
- **Results are typed, id-keyed and never stored on the `Network`.**
- **Every public module, class, function, method and property has a Sphinx/reST docstring.** `tests/unit/test_docstrings.py` fails otherwise.
- **Documentation ships with the change.** A new public symbol gets its docstring, its `docs/api/` page or entry (wired into `mkdocs.yml`) and a manual section. `examples/*.py` are embedded byte-for-byte in `docs/examples/index.md`, so the script and the page are the same bytes.

## Testing

- Tiers: `tests/unit` (marker `unit`), `tests/parity` (`parity`, against pandapower/PyPSA/MATPOWER), `tests/property` (`property`, hypothesis). The marker comes from the directory.
- **The full suite takes 15–20 minutes.** While working, run only the test files you touched: `uv run pytest tests/unit/test_x.py -q`. Codewright's gates run the whole suite after you finish; do not run it yourself more than once.
- **Always `uv run --frozen ...`.** A plain `uv run` may rewrite `uv.lock`, which is outside every task's lease and fails the lease gate. If `uv.lock` shows in `git status` and you did not change a dependency, `git checkout uv.lock`.
- Before done: `uv run --frozen ruff check .`, `uv run --frozen ruff format --check .`, `uv run --frozen mypy`, and the test files for everything you changed. If you touched `docs/` or `mkdocs.yml`: `uv run mkdocs build --strict`. If you touched a notebook: `uv run pytest --nbmake docs/tutorials -q`.
- A feature is not done without a test that would fail if it were removed. Never loosen a parity tolerance or skip a test to get green; say what is wrong instead.

## Style

- Python ≥ 3.11, `mypy --strict` clean, ruff (E, F, I, UP, B), line length 100. No `# type: ignore` without a reason on the same line.
- A comment explains why, never what.
- Commit messages are Conventional Commits (`feat:`, `fix:`, `docs:`, `test:`, `chore:`): python-semantic-release derives the version and changelog from them.

## Out of bounds

- Never edit `.bionic/` — it is the historical planning record.
- Never edit the version in `pyproject.toml`, the generated sections of `docs/changelog.md`, `.github/workflows/publish.yml` or `[tool.semantic_release]`.
- Never change `uv.lock` unless the task changes a dependency, and then regenerate it with `uv lock`.
- Never add a runtime dependency.
