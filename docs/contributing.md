# Contributing

mambo-power is developed in the open at
[github.com/mambo10005/mambo-power](https://github.com/mambo10005/mambo-power) under the MIT
licence. This page covers the mechanics: environment, test tiers, the oracle policy, the
docstring rule and building these docs.

## Environment — uv

The project is managed with [uv](https://docs.astral.sh/uv/). `pyproject.toml` declares the
runtime dependencies (exactly `numpy`, `scipy`, `highspy`, `pydantic`) and two dependency
groups: `dev` (pytest, hypothesis, pandapower, pypsa, ruff, mypy) and `docs`
(mkdocs-material, mkdocstrings[python], pymdown-extensions). `uv.lock` pins everything; CI
installs with `--locked`, so a dependency change must be accompanied by a regenerated lock.

```bash
git clone https://github.com/mambo10005/mambo-power.git
cd mambo-power
uv sync --all-groups            # creates .venv with every group
uv run pytest                   # the whole suite
```

Python ≥ 3.11 is required; CI runs 3.11, 3.12 and 3.13 on Ubuntu and 3.12 on macOS and
Windows. Use `UV_PYTHON=3.11 uv sync` to test another interpreter locally.

## Quality gates

Every push runs, and every change must keep green:

```bash
uv run ruff check .             # lint (E, F, I, UP, B)
uv run ruff format --check .    # formatting
uv run mypy                     # strict, on src/
uv run pytest                   # all tiers
uv run mkdocs build --strict    # the docs, zero warnings
```

The `install-smoke` CI job additionally builds the wheel and sdist and installs each into a
clean virtual environment.

## Test tiers and markers

Tests live under `tests/` in three directories; the matching marker is applied automatically
by `tests/conftest.py`, so `-m` selects a tier without decorating every test.

| Tier | Directory | Marker | Budget | Contents |
| --- | --- | --- | --- | --- |
| unit | `tests/unit/` | `unit` | < 10 s | Hermetic tests of our own code: model invariants, parser, numerics against dense re-derivation, result models, docstrings, packaging metadata, schema snapshot. |
| parity | `tests/parity/` | `parity` | ~1 min | Comparisons against the oracles: pandapower `from_mpc`, `makeYbus`, `rundcpp`, `runpp`; MATPOWER stored solutions. |
| property | `tests/property/` | `property` | varies | hypothesis property-based tests over random radial and meshed networks: conservation, PTDF/LODF identities, bridge agreement. |

```bash
uv run pytest -m unit           # fast loop while developing
uv run pytest -m parity         # needs pandapower / pypsa (dev group)
uv run pytest tests/unit/test_pf_dc.py -q
```

`--strict-markers` is on; a new marker must be declared in `pyproject.toml`.

## Parity oracles policy

pandapower and PyPSA are **development dependencies only**. Package code under `src/` never
imports them; a test does. Every solver carries either a published oracle or an analytic
invariant:

| Module | Oracle / invariant |
| --- | --- |
| `io.matpower` | pandapower `from_mpc` on the same file, after unit alignment (1e-9). |
| `numerics.ybus` | pandapower `makeYbus` (1e-9) and dense re-derivation (1e-12). |
| `numerics.ptdf` / `lodf` | dense re-derivation; brute-force single-outage PTDF difference; graph-theoretic bridges agree with the numeric `NaN` columns. |
| `pf.dc` | pandapower `rundcpp` (1e-9). |
| `pf.ac` | pandapower `runpp` (1e-6 pu, 1e-4 deg, 1e-4 MVA) primary; MATPOWER stored solutions secondary at file precision with a per-case exclusion list. |

Where an oracle and the MATPOWER manual disagree, the manual wins and the divergence is
recorded in the test. Never assert anything about an oracle's *undefined* outputs (for
example pandapower's LODF bridge columns, which are platform-dependent); assert ours.

## Docstring rule

Every public module, class, function, method and property in `mambo_power` carries a
docstring. `tests/unit/test_docstrings.py` walks the package with `pkgutil` and fails listing
every offender, so a missing docstring is a red unit test, not a review comment.

Style: the code uses **Sphinx/reST** docstrings — a one-line summary, an optional body, and
cross-references written as `` :class:`~mambo_power.model.Network` ``,
`` :func:`mambo_power.pf.solve_dc` ``, `` :mod:`mambo_power.numerics` ``. The docs build
renders those roles as links to the API pages (a small mkdocs hook, `docs/hooks/rest_roles.py`,
turns them into autorefs). Use double backticks for literals. Module docstrings state the
module's contract and the conventions it implements, with the formulas where there are any —
that is what the API pages show first.

## Building the docs locally

```bash
uv sync --all-groups
uv run mkdocs serve             # live preview at http://127.0.0.1:8000
uv run mkdocs build --strict    # what CI runs; any warning fails the build
```

The site is configured in `mkdocs.yml`; pages live under `docs/`; the API pages are
`::: mambo_power.<module>` directives rendered by mkdocstrings from the source under `src/`.
Mermaid diagrams are fenced ```` ```mermaid ```` blocks; equations use `\(...\)` and `\[...\]`
(MathJax via `pymdownx.arithmatex`). Example scripts under `examples/` are embedded with
`pymdownx.snippets` (`--8<--` markers) so the documentation and the executed code are the same
bytes.

Pushes to `epic/01-foundation` and `main` deploy the site to
[mambo10005.github.io/mambo-power](https://mambo10005.github.io/mambo-power/) through
`.github/workflows/pages.yml`.

## Commits and branches

- Work happens on wave branches (`wave/NN-name`) merged into the epic branch
  (`epic/01-foundation`), then `main`.
- Commit messages follow Conventional Commits (`feat:`, `fix:`, `docs:`, `test:`,
  `chore:`), because semantic-release will derive versions and the changelog from them at
  0.1.0.
- Keep the [changelog](changelog.md) `Unreleased` section current for user-visible changes.
- Documentation is a per-wave deliverable: a change that adds a public symbol adds its
  docstring, its manual section and, where useful, an example in the same change.
