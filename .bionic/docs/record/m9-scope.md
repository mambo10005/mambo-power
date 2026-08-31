# M9 release-0.1 — Step 1 scope (idea-refine)

Wave M9 `release-0.1`, triple build · audited · wave, integration branch `epic/01-foundation`
(base `9012c43`, 1539 passed / 4 skipped, CI green on all 8 matrix jobs including the two ubuntu
Python versions that just caught a real degeneracy). Step 0 confirmed 2026-08-30. Last wave on the
epic roadmap — after this merges, `epic/01-foundation` merges to `main` once, and the epic closes.

## The refined idea

The epic row (`epic.plan.md`): "mkdocs-material site on GitHub Pages, API reference,
notebook-tested tutorials, CHANGELOG via python-semantic-release, PyPI trusted publishing, 0.1.0
tag; re-derives walk (docs site is drivable → walk: required)." Three of the five already exist
(the Pages site, mkdocstrings API reference, a Keep-a-Changelog-formatted `changelog.md` — all
shipped incrementally since M2 per spec R14). What's genuinely new: **notebook-tested tutorials**,
**automated CHANGELOG generation from conventional commits**, and **the actual PyPI publish
pipeline**. The epic's own framing note: "M9 becomes release polish, not the first docs" — this
wave finishes and ships what exists, it doesn't start from zero.

## Rulings from the Step-1 interview (user, 2026-08-31)

- **D1 — tutorials: new narrative notebooks**, not a thin wrapper on the existing 13
  `examples/*.py` scripts. Distinct from the examples' terse, one-concept-per-script
  demonstrations (which stay as-is, CI-run, embedded in `docs/examples/`): prose-heavy walkthroughs
  with a story arc, aimed at a first-time reader rather than a reference. *Rejected:* converting
  examples directly (least new work, but doesn't serve a different reader than the examples
  already do); skipping notebooks entirely (doesn't match the epic's stated deliverable, R13).
- **D2 — docs: structural reorg**, not a light pass. The nav (72 entries, 9 waves' worth of pages
  in roughly build order) gets a first-time-reader's path, not just broken-link fixes. *Rejected:*
  light pass only (cheaper, but leaves a real first-time visitor without a story, which is exactly
  what "release polish" should fix once, deliberately, rather than never).

## Not doing

- Rewriting the manual pages' own technical content — the reorg is structural (nav, entry points,
  a tutorials layer, cross-links), not a rewrite of what M2–M8 already documented correctly.
- A second docs theme, a docs redesign, or moving off mkdocs-material.
- Computing the semantic version from the full commit history. **Default, stated not asked**: the
  first release is tagged `v0.1.0` manually (a human act, Step 9, per the epic's own framing —
  "PyPI project name claim is a user action" extends naturally to "the first tag is too"); `python-
  semantic-release` takes over computing bumps from that point forward, per conventional commits.
  This is the standard bootstrap pattern for adding semantic-release to an existing repo whose
  history predates it — not an open question, a well-established default.
- A GitHub `pypi` environment manual-approval gate: **default yes**, offered and not objected to
  earlier in this session — built into the trusted-publishing workflow as belt-and-suspenders,
  costs nothing day to day.
- Any change to `opf`/`market`/`numerics` solver code — this wave is docs, packaging and CI/CD.
- Retroactively rewriting any of the eight waves' own continuation records or ADRs for the reorg;
  the reorg changes navigation and entry points, not the historical record.

## Prior art (the alternatives lens)

- `docs/examples/index.md`'s embedding convention (`pymdownx.snippets`, `{ .python }` fences,
  `tests/unit/test_examples_run.py` running every script in CI) is the precedent for "the docs and
  the tested artifact are the same bytes" — the notebook tutorials should carry the same discipline
  via CI execution (nbmake or nbval — Step 2 picks), not prose that can silently drift from what
  actually runs.
- Every prior wave's `formats.md`/`manual/*.md` sections (`io.matpower`'s shape: sections read,
  column maps, warnings, errors, limitations, example) are the reference style the tutorials should
  point readers toward, not duplicate.
- `docs/changelog.md`'s existing Keep-a-Changelog structure (one section per wave, newest first) is
  what `python-semantic-release` needs to either consume or replace — Step 2 decides which, since
  semantic-release conventionally *generates* the changelog from commit messages going forward,
  which could either supersede or coexist with the wave-narrative sections already there (each of
  which is far richer prose than a commit-message-generated entry would produce).
- ADR-009/ADR-011/ADR-012's own precedent — every design decision this epic has made, recorded the
  same way — is what any new packaging/CI decision in this wave should follow if it's momentous
  enough (the semantic-release changelog-coexistence question likely qualifies).

## Open for Step 2 (the design interview)

1. Tutorial count and topics — a story arc across how many notebooks, covering which of the eight
   shipped capabilities (substrate/power-flow/OPF/market modes/agents/interop)?
2. Notebook CI execution tool (`nbmake` vs `nbval` vs a bespoke execute-and-diff) and where they
   render on the docs site (mkdocs-jupyter plugin vs a converted-to-markdown snippet, matching the
   examples' `pymdownx.snippets` convention).
3. The nav reorg's actual shape — where do tutorials sit relative to Manual/Examples/API reference;
   does "Manual" split into sub-groups; does Home's own roadmap table change once every wave reads
   "merged."
4. Changelog: does `python-semantic-release` generate a NEW auto-section going forward while the
   nine existing wave sections stay as hand-written history, or does something else happen at the
   0.1.0 boundary?
5. The PyPI trusted-publisher form values (`publish.yml`, `pypi` environment, owner/repo) were
   already given to the user outside this SDLC run — confirm no drift before Step 5's live check.
