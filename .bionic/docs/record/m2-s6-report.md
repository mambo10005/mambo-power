# M2 / S6 — docs-site: report

Agent: m2-s6 · worktree `C:\Claude Projects\mambo-power-m2` · branch `wave/02-power-flow` ·
started on HEAD 41e531b · commit **cf3f9fb** (29 files, +3286 / −8). Not pushed.

## IA as built (20 pages, all real content)

| Nav | Page | File |
| --- | --- | --- |
| Home | what mambo-power is, three principles, mermaid system-context diagram, "where next" table, roadmap | `docs/index.md` |
| Getting started | install from source (uv / pip), load MATPOWER, warnings, validate (all-issues), `validate_network`, DC solve, read results, JSON round-trip, `to_arrays`, hand-built 2-bus network — every block executed, outputs shown are real | `docs/getting-started.md` |
| Manual › Network model | conventions; `Network`, `Bus`, `Geo`, `Branch`, `Generator`, `PolynomialCost`, `PiecewiseCost`, `Load`, `Shunt`, `Storage`, `Zone` field tables (type, unit, default, invariant); all-issues contract; 7 validation codes × triggers; `validate_network`; JSON schema export; mutability caveats | `docs/manual/model.md` |
| Manual › File formats | native JSON (4 functions, minimal document, rules); MATPOWER importer: sections, derived ids, bus/gen/branch/gencost column maps incl. dropped columns, warning codes (`BASE_KV_REPLACED`, `GENCOST_REACTIVE_IGNORED`, `ISLAND_DEACTIVATED`), islands (D1), 5 error codes, limitations, fixtures | `docs/manual/formats.md` |
| Manual › Numerics | `NetworkArrays` (filtering rules, every attribute group, single pu site); Ybus / Bbus / Bf / p_shift formulas (MathJax); PTDF; LODF + bridges + NaN columns; worked code | `docs/manual/numerics.md` |
| Manual › Power flow | DC formulation B'θ = P − P_shift, flows, slack convention, errors, result; AC section as design contract (API, polar NR + Jacobian, Q-limit D2 semantics, effective roles table, islands, verification policy); DC vs AC table | `docs/manual/power-flow.md` |
| Manual › Results | shape; `ResultProvenance`, `BusResult`, `BranchResult`, `GenResult` tables; DC/AC models; JSON round-trip (executed); `to_arrays()` table + code; `dc_result_from_arrays` | `docs/manual/results.md` |
| Manual › Jobs API | design contract: guarantees, `SolveRequest`, `SolveResult`, `StructuredError` codes, `KINDS`, `run` algorithm, intended use (text blocks only — no fake runnable code) | `docs/manual/jobs.md` |
| Examples | table of 8 scripts with one-line descriptions + page links; conventions for S7 | `docs/examples/index.md` |
| API reference ×6 | `::: mambo_power.model` (+ entities/errors/network), `io.matpower`, `io.native`, `numerics` (+ arrays/ybus/bbus/ptdf/lodf), `pf` (+ dc), `results` (+ tables/provenance/power_flow/from_arrays) | `docs/api/*.md` |
| Design › Architecture | mermaid component diagram with allowed import directions (shipped / landing / later), rules, ownership table (epic §3 + M2 additions), sequence diagram of one solve, module map | `docs/design/architecture.md` |
| Design › Data model | mermaid classDiagram of Network + 10 entities with multiplicities; units convention table; classDiagram of result models | `docs/design/data-model.md` |
| Design › Decisions | ADR-001…005 restated (context/decision/consequences) + M2 D1, D2, effective roles, verification policy | `docs/design/decisions.md` |
| Changelog | Keep-a-Changelog, Unreleased: M2 items (shipped + landing), M1 items, Changed | `docs/changelog.md` |
| Contributing | uv workflow, gates, test tiers/markers, oracle policy table, docstring rule + style, building docs, branches/commits | `docs/contributing.md` |

Supporting files: `mkdocs.yml` (material, navigation.tabs/sections, content.code.copy, search +
autorefs + mkdocstrings python handler `paths: [src]`, superfences mermaid fence, snippets
`base_path: [examples, .]` with `check_paths`, admonition, toc permalink, tables, arithmatex
generic + MathJax), `docs/javascripts/mathjax.js`, `docs/hooks/rest_roles.py` (see judgment
calls), `.github/workflows/ci.yml` (+ `docs` job: ubuntu/3.12, `uv sync --locked --all-groups`,
`mkdocs build --strict`, upload `site/`), `.github/workflows/pages.yml` (push to
`epic/01-foundation` + `main` + dispatch; build → `configure-pages` → `upload-pages-artifact` →
`deploy-pages`; `permissions: pages: write, id-token: write, contents: read`; `concurrency:
pages`; environment `github-pages`), `README.md` (what/status/install/quick start/manual
links/dev/licence), `pyproject.toml` docs group, `uv.lock`.

## Dependencies

`[dependency-groups] docs = ["mkdocs-material>=9.7", "mkdocstrings[python]>=1.0",
"pymdown-extensions>=10.16"]`. Resolved: mkdocs 1.6.1, mkdocs-material 9.7.7, mkdocstrings
1.0.6, mkdocstrings-python 2.0.7, pymdown-extensions 11.0.1 (matches research §5).
`uv lock` + `uv sync --locked --all-groups` exit 0.

## mkdocs build --strict

```
INFO    -  Cleaning site directory
INFO    -  Building documentation to directory: C:\Claude Projects\mambo-power-m2\site
INFO    -  Documentation built in 3.94 seconds
exit=0          grep -ci 'warning  -' → 0
```

(The only stderr noise is Material's MkDocs-2.0 advisory banner, not a build warning.)

Rendered-site proof: 20 `index.html` pages under `site/`; home page nav carries hrefs for
every IA page (`getting-started/`, `manual/{model,formats,numerics,power-flow,results,jobs}/`,
`examples/`, `api/{model,io-matpower,io-native,numerics,pf,results}/`,
`design/{architecture,data-model,decisions}/`, `changelog/`, `contributing/`). API pages contain
anchors for e.g. `mambo_power.model.Network`, `mambo_power.model.entities.Bus`,
`mambo_power.io.matpower.load_with_warnings`, `mambo_power.numerics.arrays.NetworkArrays`,
`mambo_power.numerics.lodf.bridges`, `mambo_power.pf.solve_dc`, `mambo_power.pf.dc.DcSolution`,
`mambo_power.results.power_flow.PowerFlowResultBase.to_arrays`, and S2's
`mambo_power.numerics.effective_roles`, `mambo_power.model.repair_islands` (their modules were
in the tree at build time). Mermaid blocks: home 1, architecture 2, data-model 2.
Arithmatex spans on numerics page: 20.

## Docstring test (AC-10)

`tests/unit/test_docstrings.py` — pkgutil walk; checks module, public class, public function,
and public methods/properties/classmethods/staticmethods defined in the class body, restricted
to objects whose `__module__` is inside `mambo_power`; second test asserts the walk reaches
every shipped package (so the check cannot go vacuous).

- **Baseline run on the wave head: GREEN, 0 offenders** — every public symbol already carried
  a docstring, including S2's new modules. No source docstrings needed adding.
- **Planted-miss proof (in-memory, no source change):** removing docstrings from
  `mambo_power.pf.dc` (module), `mambo_power.pf.solve_dc` (function),
  `mambo_power.results.tables.BusResult` (class) and
  `NetworkValidationError.codes` (property) → walker lists exactly
  `['mambo_power.pf.dc', 'mambo_power.pf.solve_dc', 'mambo_power.results.tables.BusResult']`
  and `['mambo_power.model.errors.NetworkValidationError.codes']`. The instrument catches all
  four kinds.

## Gate outputs (final, on the committed tree)

| Gate | Result |
| --- | --- |
| `uv run mkdocs build --strict` | exit 0, 0 warnings |
| `uv run ruff check . --exclude tests/unit/test_pf_ac_newton.py --exclude src/mambo_power/pf/ac_newton.py` | All checks passed, exit 0 |
| `uv run ruff format --check .` (same excludes) | 79 files already formatted, exit 0 |
| `uv run mypy` | Success: no issues found in 27 source files |
| `uv run pytest -q -p no:cacheprovider --ignore=tests/unit/test_pf_ac_newton.py` | **382 passed**, 10 warnings (pandapower RuntimeWarnings), 32.9 s |
| Doc code blocks (ad-hoc runner executing every ```` ```python ```` block in getting-started, model, formats, numerics, power-flow, results, index) | 23 OK, 0 FAIL, 1 SKIP (the AC-API contract block) |
| README quick start | executed, outputs match comments |

**Exclusions, stated:** `src/mambo_power/pf/ac_newton.py`, `tests/unit/test_pf_ac_newton.py`
and `tests/parity/test_ac_vs_pandapower.py` are S4's *uncommitted* files that appeared in the
worktree mid-slice. On their own they fail `ruff check` (E501 ×5), `ruff format --check`
(2 files) and pytest collection (`ImportError: cannot import name 'AcOptions' from
mambo_power.pf`). They are not in my commit and were excluded from the gates above; S4 owns
them. S2's files were present and committed (by S2) before my commit; their tests are included
in the 382.

## Commit

```
cf3f9fb docs(m2/S6): documentation substrate — mkdocs-material site, API reference, manuals for model/formats/numerics/power-flow/results, architecture + data-model diagrams, design decisions, docstring test, docs + pages workflows
```

`git show --stat HEAD`:

```
 .github/workflows/ci.yml      |  22 +++
 .github/workflows/pages.yml   |  49 +++++
 README.md                     | 108 ++++++++++-
 docs/api/io-matpower.md       |   6 +
 docs/api/io-native.md         |   6 +
 docs/api/model.md             |  27 +++
 docs/api/numerics.md          |  28 +++
 docs/api/pf.md                |  12 ++
 docs/api/results.md           |  24 +++
 docs/changelog.md             |  75 ++++++++
 docs/contributing.md          | 120 ++++++++++++
 docs/design/architecture.md   | 121 ++++++++++++
 docs/design/data-model.md     | 222 ++++++++++++++++++++++
 docs/design/decisions.md      | 168 ++++++++++++++++
 docs/examples/index.md        |  34 ++++
 docs/getting-started.md       | 227 ++++++++++++++++++++++
 docs/hooks/rest_roles.py      |  27 +++
 docs/index.md                 | 102 ++++++++++
 docs/javascripts/mathjax.js   |  19 ++
 docs/manual/formats.md        | 233 +++++++++++++++++++++++
 docs/manual/jobs.md           | 121 ++++++++++++
 docs/manual/model.md          | 291 ++++++++++++++++++++++++++++
 docs/manual/numerics.md       | 226 ++++++++++++++++++++++
 docs/manual/power-flow.md     | 213 +++++++++++++++++++++
 docs/manual/results.md        | 153 +++++++++++++++
 mkdocs.yml                    | 119 ++++++++++++
 pyproject.toml                |   5 +
 tests/unit/test_docstrings.py | 105 ++++++++++
 uv.lock                       | 431 ++++++++++++++++++++++++++++++++++++++++++
 29 files changed, 3286 insertions(+), 8 deletions(-)
```

## Judgment calls

1. **Docstring style = `sphinx`, not google/numpy.** The code's docstrings are reST
   (`:class:`…``, `:func:`…``, double-backtick literals), so `docstring_style: sphinx` is what
   matches. Python-Markdown leaves `:class:` as literal text before a `<code>` — so I added a
   27-line mkdocs hook (`docs/hooks/rest_roles.py`, `on_page_content`) that rewrites
   `:role:<code>target</code>` into `<autoref identifier=… optional>`; mkdocs-autorefs then
   resolves them to the API anchors (verified: `href="../model/#mambo_power.model.Network"` in
   the matpower API page; 0 unresolved `<autoref>` left). `optional` keeps unknown targets
   from breaking `--strict`. The only remaining literal `:class:` strings are inside the
   `show_source` raw listings, which is correct. Alternative rejected: rewriting every
   docstring to mkdocstrings `[x][y]` syntax — touches S2's files and every module for a
   cosmetic gain.
2. **`show_if_no_docstring: false`.** Pydantic `Field(description=…)` attributes have no
   attribute docstring, so they do not appear as separate entries on the API pages; the
   manual pages carry the full field tables instead (and the class signatures show every
   field). Flipping the option later is a one-line change.
3. **Warnings documented as S2 implements them** (`CODE: message` strings with
   `BASE_KV_REPLACED` / `GENCOST_REACTIVE_IGNORED` / `ISLAND_DEACTIVATED`; `load_with_report`
   not yet documented in the manual — the API page picks it up automatically from
   `io.matpower`'s `__all__`). If S2's final shape differs, formats.md §Warnings and the
   getting-started warning output need a one-line touch.
4. **AC and jobs pages are contracts, not code.** The AC API block is fenced as python for
   display but excluded from my executor; jobs.md uses `text` fences only, so nothing on the
   site claims to run that cannot. S7 swaps in snippets once S4/S5 land.
5. **ruff now formats fenced Python inside Markdown** (this ruff version does so by default);
   I ran `ruff format` over the docs and README so the repo-wide `ruff format --check .`
   stays green — a constraint S7 should know when writing snippet-bearing pages.
6. **`pages.yml` publishes unconditionally** on the two branches (Pages is already enabled
   with source = GitHub Actions, per the brief); `configure-pages` is included so the first
   run on a fresh repo does not fail.
7. Could not render: nothing. No page was dropped or stubbed.

## Open for the fold

- S4's uncommitted files fail ruff and collection on their own (above).
- `edit_uri` in `mkdocs.yml` points at `edit/epic/01-foundation/docs/`; switch to `main` at
  0.1.0.
- `examples/` does not exist yet; `pymdownx.snippets` `check_paths: true` will fail the strict
  build on a bad snippet path once S7 adds embeds — intended.
