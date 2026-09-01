# M9 S2 report — notebook CI + render

Worktree `C:\Claude Projects\mambo-power-m9-s2`, branch `wave/09-release-0.1-s2`, base `f5847ec`.

## Commits (all `--stat`-verified, only intended files staged)

1. `7b83757` build(m9-s2): add nbmake (dev) and mkdocs-jupyter (docs) dependency groups
   — `pyproject.toml` (+2), `uv.lock` (+900, regenerated via `uv sync --all-groups`).
2. `1167c94` ci(m9-s2): add tutorials job running nbmake against the four notebooks
   — `.github/workflows/ci.yml` (+22, new `tutorials` job).
3. `517041f` docs(m9-s2): wire mkdocs-jupyter into mkdocs.yml, Tutorials nav section
   — `mkdocs.yml` (+17), `.gitignore` (+1, `.cache/`).

## W2 — nbmake in CI

Invocation: `uv run pytest --nbmake docs/tutorials/*.ipynb -q`.

Local run (clean state, `uv sync --locked --all-groups` confirmed no lockfile drift):
```
....                                                                     [100%]
4 passed in 26.11s
```

Wired as a **new dedicated job** (`tutorials`) in `.github/workflows/ci.yml`, not folded into
the `test` matrix — single `ubuntu-latest` / Python 3.12 leg, same call the `examples` and
`docs` jobs already make. Reasoning stated in the job's own comment: a notebook run is
solver-heavy; re-running the same four notebooks on all five OS/Python legs would be redundant
CI minutes for zero extra coverage the single leg doesn't already give.

`testpaths = ["tests"]` in `pyproject.toml` does not interfere — pytest uses the paths given on
the command line instead of `testpaths` when any are passed explicitly.

## W3 — mkdocs-jupyter render

Plugin config in `mkdocs.yml`:
```yaml
- mkdocs-jupyter:
    include: ["tutorials/*.ipynb"]
    execute: false
    include_source: false
```

- `execute: false` (the plugin's own default) — renders the outputs **already stored** in the
  notebooks (S1 baked them in via nbconvert; CI's `nbmake` job re-verifies them fresh on every
  push). Re-executing at `mkdocs build` time would duplicate that work and slow every docs
  build for no correctness gain — nbmake is the CI-enforced source of truth, not the docs build.
- `include` explicitly scoped to `tutorials/*.ipynb` rather than the plugin's own default glob
  (`["*.py", "*.ipynb", "*.md"]`). Left at the default, that glob would have matched
  `docs/hooks/pydantic_fields.py` and `docs/hooks/rest_roles.py` (mkdocstrings/autorefs hook
  scripts that live under `docs/`) and tried to render them as notebook-style pages — confirmed
  by inspecting `mkdocs_jupyter/plugin.py`'s `should_include` before configuring.

Nav: new `Tutorials` section (index + four notebooks) inserted between `Getting started` and
`Manual` in `mkdocs.yml`'s `nav:` list. `Manual`'s own 12 entries untouched (S3).

Build proof, from a clean state (`rm -rf site .cache`):
```
$ uv run --group docs mkdocs build --strict
EXIT=0
```
Zero warning/error lines beyond the pre-existing "MkDocs 2.0 upcoming changes" notice (unrelated,
present before this slice's changes).

Rendered-output proof: tutorial 4's baked cell output reads
`true cost $20.00/MWh -> climbed offer $60.00/MWh, cleared 400.00 MW, markup $15,999.97/h`
(verified present in the source `.ipynb`'s JSON). Confirmed verbatim in the built HTML:
```
$ grep -n "60.00" site/tutorials/04-where-next/index.html
2922:<pre>true cost $20.00/MWh  -&gt;  climbed offer $60.00/MWh, cleared 400.00 MW, markup $15,999.97/h
```
All four notebooks produced `site/tutorials/{01..04}-*/index.html` plus `site/tutorials/index.html`.

Nav order confirmed by extracting `.md-tabs__link` labels from the built `site/index.html`:
`Home, Getting started, Tutorials, Manual, Examples, API reference, Design, Changelog,
Contributing` — Tutorials sits exactly between Getting started and Manual.

## Regression

```
$ uv run pytest -q tests/unit/test_examples_run.py tests/unit/test_docs_registry_listing.py
...................
19 passed in 45.18s
```
No nav-parsing or mkdocs-config test exists elsewhere in the repo (checked via grep for
`mkdocs.yml|nav:|mkdocs_jupyter|nbmake` under `tests/`) — nothing else in the suite reads
`mkdocs.yml`'s structure, so no additional regression surface was missed.

## Gates

No `.py` file was touched by this slice (only `pyproject.toml`, `uv.lock`, `.github/workflows/ci.yml`,
`mkdocs.yml`, `.gitignore`) — `ruff`/`mypy` gates not applicable, per the task brief.
`uv run --group docs mkdocs build --strict` exit 0 is the main proof (above), confirmed twice
(once mid-session, once from a fully clean `site/`/`.cache/` state after `uv sync --locked`).

## Scope discipline

Did not touch the notebook files themselves — no rendering problem required a metadata fix.
Did not touch `pyproject.toml`'s `dev`/`docs` groups beyond the two additions requested. Did not
touch any other file in `.github/workflows/` or `mkdocs.yml`'s `Manual` nav block.

## Final state

`git status --short` clean (site/ and .cache/ build artifacts gitignored, not tracked). Three
commits, `git log --oneline -4` head `517041f`.
