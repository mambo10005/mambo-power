# Continuation — epic 01-foundation closed

Nine waves (M1 substrate → M9 release-0.1), all merged into `epic/01-foundation`; this record
covers the epic's own one-time closing act: the `v0.1.0` release and the merge to `main`.

## v0.1.0, cut after M9 closed

- `semantic-release version` (2026-09-01, on a clean `epic/01-foundation` checkout) bumped
  `pyproject.toml`, wrote the changelog section, committed, and pushed the `v0.1.0` tag
  atomically (commit `9820727`). The tag push fired `publish.yml`; **build and publish both ran
  straight through, unattended** — the `pypi` GitHub environment had no required reviewer
  configured, so the manual-approval gate the wave designed for never paused anything.
- **`mambo-power 0.1.0` is live on PyPI**, confirmed independently via
  `https://pypi.org/pypi/mambo-power/json` (not just the workflow log) — this is also the live
  answer to A1, the epic-level carry-over from `continuation-m9.md`: the trusted-publisher
  configuration on pypi.org was correct; OIDC auth succeeded on the first real attempt.
- The release exposed two real gaps the wave's local checks never could, because neither is
  observable without a real tag: `uv.lock` was stale against the version bump (`uv sync
  --locked` failing in every CI job that installs deps), and `docs/getting-started.md`'s PyPI
  install text was correctly still pre-release-framed pre-tag but needed to flip the moment the
  tag existed — the pypi-sequencing guard (Step-6 critic C5's bidirectional check) caught this
  exactly as designed. Both fixed same-day (`270bc15`).
- A third gap, one layer deeper: `tests/unit/test_pypi_sequencing_guard.py`'s
  `test_guard_passes_against_real_getting_started` runs the real guard against the real repo
  state, but the main CI test-matrix job's `actions/checkout@v4` is shallow by default (no
  tags) — the dedicated `pypi-sequencing` job already carried `fetch-depth: 0` for this exact
  reason, the main `test` job didn't. Untestable until a real tag existed; fixed same-day
  (`46c9440`).
- **Open, not closed by this record:** the `pypi` environment's required-reviewer gate. Adding
  one via `gh api repos/mambo10005/mambo-power/environments/pypi` was blocked by this session's
  own permission classifier (a repo-settings mutation) — not attempted around. Add it by hand
  (repo Settings → Environments → `pypi` → Required reviewers) if you want future releases
  (`0.1.1`, etc.) to pause for approval instead of publishing on tag push the way `0.1.0` did.

## The merge to `main`

Per `epic.plan.md`: "after M9 merges, `epic/01-foundation` merges to `main` once, with
continuation notes for anything deferred." One prerequisite change travels in the same commit
as the merge, per `docs/contributing.md#cutting-a-release`'s own standing warning (R12):
`[tool.semantic_release.branches.main]`'s `match` moves from `epic/01-foundation` to `main` —
semantic-release silently refuses to compute a version on a branch it isn't configured to
release from, so every release after `v0.1.0` needs this to have already moved. `docs/
contributing.md`'s own note on this was rewritten from forward-looking to past-tense in the
same commit, so it doesn't go stale the way the changelog preamble once did (F-A7/C2).

See `continuation-m9.md` for the wave's own full record (what shipped, independent verdicts,
lessons). Carry-overs from that record not superseded above (F-A9/R3-adjacent's qualifier
breadth, R4/R5's fence-awareness, R8/R9/R10/R14/R15's CI/script nits, README's own
staleness-guard gap) are still open and still low-stakes; nothing here escalates them.

## Epic lessons worth carrying into the next epic

1. **A real tag is not optional evidence for a release wave's own CI design**, even when every
   local check and every dry-run passed — three separate CI-only failures (`uv.lock`,
   `getting-started.md`, the shallow-checkout blind spot) surfaced only once `v0.1.0` actually
   existed, each caught within minutes because a green-CI bar was still being held after the
   wave's own SDLC run had formally closed.
2. **A workflow YAML naming an environment as a gate is not the same as the gate existing.**
   `publish.yml` referenced `environment: pypi` throughout wave M9's design and review; nothing
   in the SDLC run checked whether that environment's *protection rule* (the required reviewer)
   was actually configured in GitHub's settings, as opposed to referenced in code. The workflow
   file was correct; the repo setting it depended on was never created.
3. **A "match this branch" config value tied to a stated one-time future event is worth grepping
   for by name before that event, not after** — `epic/01-foundation` appeared in three separate
   config files (`pyproject.toml`, `pages.yml`, `mkdocs.yml`); only the first was load-bearing
   for the epic close (semantic-release would silently no-op otherwise) and is fixed here. The
   other two (`pages.yml`'s Pages trigger, `mkdocs.yml`'s edit-source link) still name
   `epic/01-foundation` — harmless (Pages already also triggers on `main`; the edit link just
   points at a branch that will stop moving) but worth a look if a future change touches either
   file.
