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
uv sync --all-groups            # mkdocs lives in the docs group; uv run alone provisions dev only
uv run ruff check .             # lint (E, F, I, UP, B)
uv run ruff format --check .    # formatting
uv run mypy                     # strict, on src/
uv run pytest                   # all tiers
uv run mkdocs build --strict    # the docs, zero warnings
```

The first line is not optional on a fresh clone. `pyproject.toml` declares no `default-groups`,
so `uv run` provisions `dev` and nothing else, and the last line then fails with
`Failed to spawn: mkdocs` rather than with a docs warning.

The `install-smoke` CI job additionally builds the wheel and sdist and installs each into a
clean virtual environment.

`getting-started.md`'s install instructions may not claim PyPI availability until a matching
`v0.1.0`+ git tag exists — enforced by `scripts/check_pypi_sequencing.py` in the
`pypi-sequencing` CI job. The page is meant to read "not on PyPI yet ... install from source"
until the real `v0.1.0` tag is cut; if a future edit adds an unqualified `pip install
mambo-power` / `uv add mambo-power` line ahead of that tag, this check fails the build rather
than letting the live docs site claim a release that doesn't exist yet.

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
- The changelog's `v0.1.0`-and-later sections are generated automatically by
  `python-semantic-release` from conventional-commit messages at release time — there is no
  `Unreleased` section to keep current by hand (that changed with wave M9; see
  [Cutting a release](#cutting-a-release) below). Before `v0.1.0`, wave-scoped changes are
  still hand-written under [`## Pre-release history`](changelog.md).
- Documentation is a per-wave deliverable: a change that adds a public symbol adds its
  docstring, its manual section and, where useful, an example in the same change.

## Cutting a release

Wave M9 built three separate pieces of a release chain — `[tool.semantic_release]`'s config,
`pyproject.toml`'s `version` field, and `.github/workflows/publish.yml`'s tag-vs-version
consistency gate — without anywhere naming the procedure that connects them (Step-6 reviewer
finding R11). This section is that procedure, and it is the one place a human should look before
cutting any release, including the first (`v0.1.0`).

**Use the tool, not a manual version edit.** `semantic-release version` bumps `pyproject.toml`,
inserts the changelog section, commits, and tags — all in one atomic operation, on the same
commit. A hand-edited `pyproject.toml` followed by a separately-pushed tag is the one order of
operations that can make `publish.yml`'s own version-consistency gate fail the build (the tag's
tree is what `actions/checkout@v4` sees, so the bump commit must exist *before* the tag, not just
"in the same session").

```bash
git checkout epic/01-foundation && git pull
PYTHONUTF8=1 uv run --group release semantic-release version   # Windows needs PYTHONUTF8=1;
                                                                 # GitHub Actions' UTF-8 locale
                                                                 # doesn't need it
git push --follow-tags
```

That single command bumps the version, writes the new changelog section, commits, and tags —
verify the printed version and the diff before it pushes anything if you want to sanity-check
first (it prints "The next version is: X.Y.Z" before acting). `git push --follow-tags` pushes
both the release commit and its tag; the tag push is what fires `publish.yml`.

Then: approve the `pypi` GitHub environment's required-reviewer gate (repo Settings →
Environments → `pypi`) when the `publish` job pauses for it — this is the manual-approval
checkpoint between `build` finishing and the actual PyPI upload.

**Do not run `semantic-release changelog` on its own** as a way to preview the changelog —
it is not idempotent against an untagged state; running it twice with no intervening tag
duplicates the generated section. `version` (above) is the only command that should touch this
repo's changelog.

**Before the epic merges to `main`** (a one-time, later event): `[tool.semantic_release
.branches.main]`'s `match = "epic/01-foundation"` must be updated to match wherever releases
are cut from next — today that's deliberately not `main`, because the epic hasn't merged yet, and
semantic-release will silently refuse to compute a version on a branch it isn't configured to
release from (R12).

**Prerequisite, checked automatically:** `scripts/check_pypi_sequencing.py` (CI job
`pypi-sequencing`) fails if `docs/getting-started.md` claims PyPI availability without a matching
`v0.1.0`+ tag, or — since wave M9's Step-6 remediation — the reverse: a matching tag exists but
the page still reads pre-release. Update `getting-started.md`'s install instructions in the same
change as the release if the guard goes red.
