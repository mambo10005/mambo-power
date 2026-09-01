---
governing-skill: agent-skills:spec-driven-development
sdlc-step: 2
intent: build
rigor: audited
scale: wave
canonical_sdlc_version: 13
surface_type: library + docs site
language: python
has_ui: false
multi_agent: true
deploy_target: pypi
cleanup_on_finish: true
use_worktree: true
rigor-floor: audited
design: specs/epic-01-foundation/epic.spec.md
walk: required
design-interview: true
model_plan:
  orchestrator: fable-5
  implementor: sonnet
  senior-implementor: opus
  researcher: sonnet
  auditor: opus
  critic: opus
---

# Wave M9 — release-0.1: tutorials, nav reorg, semantic-release, PyPI trusted publishing

Epic row (`epic.plan.md`): "mkdocs-material site on GitHub Pages, API reference, notebook-tested
tutorials, CHANGELOG via python-semantic-release, PyPI trusted publishing, 0.1.0 tag; re-derives
walk (docs site is drivable → walk: required)." The site, API reference and changelog structure
already exist (M2 onward, spec R14); this wave adds what doesn't: notebook tutorials, automated
version/changelog generation, and the actual publish pipeline. Scope and the four Step-2 rulings:
`record/m9-scope.md`.

## Requirements

- **W1 — four narrative tutorial notebooks.** `docs/tutorials/{01-first-power-flow,
  02-dc-opf-and-n1, 03-nodal-market, 04-where-next}.ipynb`, difficulty-tiered, each self-contained,
  prose-heavy (not terse like `examples/`), ~15–20 min read, referencing the previous. Content:
  (1) load a MATPOWER case, run `pf.solve_dc`/`solve_ac`, read branch/bus results; (2)
  `opf.solve_dc_opf` for dispatch and LMPs, `contingency.n1` screening; (3) `market.solve_nodal`
  with elastic demand and settlement; (4) a guided tour choosing between agents (`market.agents`)
  and interop (`io.*`) as the reader's next stop, with a short example of each. A short intro
  `docs/tutorials/index.md` states the arc and the difficulty tier of each.
- **W2 — notebooks execute in CI.** `nbmake` as a pytest plugin; every notebook runs fresh and
  fails on any raised exception or nonzero exit — no output-diffing (D nothing in Step 1 asked for
  byte-stable notebook outputs, and this repo's own history argues against building a check that
  would fight solver float noise). Wired into the existing test matrix as its own job or folded
  into an existing one — implementor's call, stated in the report.
- **W3 — notebooks render on the site.** `mkdocs-jupyter` as a docs-group dependency; nav entries
  under a new top-level `Tutorials` section, between `Getting started` and `Manual`. `Manual`
  itself is untouched in content and stays flat (S3) — only `Tutorials` is new nav structure.
- **W4 — home page and roadmap.** `docs/index.md`'s status prose and roadmap table read `merged`
  for every wave M1–M9 once this wave itself is included (a self-referential last row — state what
  the wave head will read once *this* wave merges, not what it reads mid-wave). The "where do I go"
  table gains a `Tutorials` row before the `Manual` rows.
- **W5 — getting started, sequenced correctly.** `docs/getting-started.md`'s "not on PyPI yet"
  install instructions are the correct state for every commit up to and including Step 8's merge;
  the PyPI install instructions (`pip install mambo-power`) are added in the SAME action as Step
  9's tag cut, never merged before the package actually exists on PyPI (A-something below — the
  live docs site deploys on every push, so a docs claim ahead of the real PyPI state would be
  false for however long the gap lasts).
- **W6 — CHANGELOG via `python-semantic-release`.** Configured (`pyproject.toml` `[tool.
  semantic_release]` or `.releaserc`, implementor's call on the conventional format) to compute the
  next version from conventional-commit messages on `epic/01-foundation` (feat→minor, fix→patch,
  `BREAKING CHANGE:`→major) starting from a manually-cut `v0.1.0` (T2) — never computed from the
  full pre-semantic-release history. Its auto-generated section is inserted **above** the nine
  existing hand-written wave sections in `docs/changelog.md`, which move under a `## Released`
  (or equivalent) heading as history; the auto-section never overwrites or reformats the
  hand-written prose (S4).
- **W7 — PyPI trusted publishing.** `.github/workflows/publish.yml`: triggers only on a pushed
  `v*`-shaped tag (T3, never on every commit); builds the wheel and sdist (`uv build` or
  `python -m build`); publishes via `pypa/gh-action-pypi-publish` with OIDC (no token, no secret
  anywhere in the repo or its settings); runs in a `pypi` GitHub environment (T1) with the values
  already given to the user (owner `mambo10005`, repo `mambo-power`, workflow `publish.yml`,
  environment `pypi`) — implementor confirms these match what the user configured on pypi.org
  before Step 5 claims this criterion live-verified, per the standing stop-and-wake if they don't.
  A required-reviewer rule on the `pypi` environment is the manual-approval gate (T1) — configure
  it in the workflow's `environment:` block; whether GitHub enforces the reviewer list itself is a
  repo-settings action outside this SDLC's reach, named as a Step-9 checklist item for the user.
- **W8 — the wave's own docs.** This wave documents itself the way M2–M8 documented themselves:
  changelog entry, and (novel for this wave) the whole package's release is what `docs/index.md`'s
  status prose finally reads in full.

## Not doing

Rewriting Manual's technical content; a second docs theme; computing the semantic version from
full pre-M9 history; retroactively rewriting any prior wave's continuation/ADR for the reorg; any
solver code change; a docs-site redesign beyond the reorg named in W3/W4; automating the actual
`v0.1.0` tag push (Step 9, the user's or an explicit final act, never silent).

## Prior art

`docs/examples/index.md`'s "the docs and the tested artifact are the same bytes" discipline
(`pymdownx.snippets`, `test_examples_run.py`) — the precedent W2 extends to notebooks via a
different mechanism (`nbmake`, not snippet-embedding, since a notebook's rendered outputs are part
of what's shown). Every prior wave's `manual/*.md` section shape. ADR-009/011/012 as the precedent
for when a packaging/CI decision in this wave earns its own ADR (W6's coexistence rule is a
candidate).

## Acceptance criteria

- **AC-1** — the four tutorial notebooks exist, execute cleanly under `nbmake` in CI (fresh kernel,
  no raised exception, exit 0), and render on the built docs site with their outputs visible
  (`mkdocs build --strict` exit 0, the rendered HTML contains each notebook's final cell output).
  provenance: epic M9 row "notebook-tested tutorials"; user 2026-08-31 "Four, difficulty-tiered"
- **AC-2** — `Tutorials` appears in the nav between `Getting started` and `Manual`; `Manual`'s own
  12 entries are byte-identical in content and order to pre-wave (S3: no split, no rewrite);
  `docs/index.md`'s roadmap table reads `merged` for M1–M9 and the "where do I go" table lists
  `Tutorials`.
  provenance: user 2026-08-31 "Structural reorg" + "Stay flat"
- **AC-3** — `docs/getting-started.md` at the wave's Step-8 merge head still says "not on PyPI
  yet"; the PyPI install instructions are added and merged in the same commit/action as the
  `v0.1.0` tag push, never before — checked by a script asserting the tag exists (or is being cut
  in the same action) whenever the getting-started page's PyPI text is present, so this can't drift
  silently in a later wave either.
  provenance: user 2026-08-31 sequencing requirement (W5)
- **AC-4** — `python-semantic-release` computes the correct next version from a small set of
  hand-authored conventional-commit fixtures (feat/fix/breaking-change/chore combinations) run
  through its own dry-run mode, starting from `v0.1.0`; its changelog output is inserted above the
  nine existing wave sections without altering their text (a diff of the pre-wave sections against
  post-tool-run is empty except for their new position in the file).
  provenance: epic M9 row "CHANGELOG via python-semantic-release"; user 2026-08-31 "Coexist"
- **AC-5** — `publish.yml` triggers only on a `v*` tag push (a workflow-dispatch or push-to-branch
  event does NOT trigger the publish job — tested by inspecting the workflow's `on:` block and, if
  feasible, a dry run against a non-matching ref); builds and would publish via OIDC with no
  token/secret referenced anywhere in the workflow file or repo settings; the `pypi` environment
  and its values match exactly what the user configured on pypi.org (live-checked at Step 5, or a
  named stop-and-wake if they don't yet exist).
  provenance: epic M9 row "PyPI trusted publishing"; epic A10; user's own PyPI configuration
- **AC-6** — the wave's own docs: a changelog entry for M9, `mkdocs build --strict` exit 0 with
  zero unlinked-page or dangling-anchor lines, every new page reachable from the nav.
  provenance: epic R14

## Design

### Domain model

No changes to `Network` or any solver-facing entity — this wave is docs, packaging and CI/CD. The
two new artifacts with structure worth naming: a **tutorial notebook** (prose cells + executed
code cells, CI-gated by `nbmake`, rendered by `mkdocs-jupyter` — distinct from an `examples/*.py`
script, which is terse, embedded by snippet, and has no prose); a **release** (a `v*` tag → a
built wheel+sdist → a PyPI publish via OIDC, with no artifact of that chain ever containing a
credential).

### Component boundaries and interfaces

| module/area | owns | crosses in | crosses out |
|---|---|---|---|
| `docs/tutorials/` | the four notebooks + intro page | nothing (pure docs, imports the public package) | rendered HTML via `mkdocs-jupyter`; CI pass/fail via `nbmake` |
| `mkdocs.yml` nav | the reorg (W3/W4) | — | the site's structure |
| `docs/changelog.md` | hand-written wave history (unchanged) + a new auto-generated section (W6) | commit messages, via semantic-release | the published CHANGELOG |
| `.github/workflows/publish.yml` | the release pipeline (W7) | a pushed `v*` tag | a PyPI package, via OIDC, no secret |
| `docs/getting-started.md` | the install instructions, sequenced (W5) | the fact of whether `v0.1.0` has been tagged | what a new user is told to run |

### Ownership table

| concept | owning module (SSoT) | rendering surfaces | agreement test |
|---|---|---|---|
| "is this released yet" | the existence of a `v0.1.0`+ git tag | `getting-started.md`'s install block, `docs/index.md`'s status prose, `changelog.md`'s `[Unreleased]` vs released split | AC-3's script: PyPI install text present ⇒ tag exists |
| the wave's own completion state | `epic.plan.md`'s roadmap row for M9 | `docs/index.md`'s roadmap table, `changelog.md`'s M9 section | a docs test comparing the two, if one doesn't already exist — implementor checks |
| what conventional-commit type bumps what | `python-semantic-release`'s own config | its dry-run output, the generated changelog section | AC-4's fixture commits |

### Rejected alternatives

Converting `examples/*.py` into the tutorials directly (S1: doesn't serve a different reader);
`nbval`'s output-diffing (S2: real upkeep this repo's own float-noise history argues against, for
a benefit — silent drift detection — nothing else in this repo provides either); splitting Manual
into sub-groups (S3: ceremony without fixing a real confusion); semantic-release replacing the
hand-written wave sections entirely (S4: loses prose richness for no stated benefit); computing the
version from full pre-M9 history (would not land on 0.1.0; not how semantic-release is bootstrapped
onto an existing repo); publishing on every commit rather than a tag (removes the deliberate human
act the epic's own A10 assumption requires).

### Assumptions

- **A1** — the user has already been given the exact `publish.yml`/`pypi` environment values this
  spec commits to (owner `mambo10005`, repo `mambo-power`, workflow `publish.yml`, environment
  `pypi`) and will configure pypi.org's pending-trusted-publisher form to match before Step 5's
  live check, or Step 5 raises a stop-and-wake naming exactly what's missing.
- **A2** — `nbmake` and `mkdocs-jupyter` install cleanly as dev/docs-group deps on the existing CI
  matrix (to be verified at Step 4, mirroring M1's own CI-skeleton proof for pandapower/PyPSA).
- **A3** — `python-semantic-release`'s conventional-commit parsing tolerates this repo's actual
  commit history shape (`feat(scope):`, `fix(scope):`, plus non-standard types like `merge(...)`,
  `chore(...)` that appear frequently) without misinterpreting a non-conventional type as a bump —
  verified by AC-4's dry-run rather than assumed.
- **A4** — a notebook executed by `nbmake` in CI has access to whatever fixtures/data the tutorials
  reference (bundled MATPOWER cases) without network access or external services — same
  environment guarantee the examples already have.
