# M9 S5 report — python-semantic-release config (W6, AC-4)

Worktree: `C:\Claude Projects\mambo-power-m9-s5`, branch `wave/09-release-0.1-s5`, base `d18aaea`.
Commit landed: `34710aa` (`feat(m9/s5): python-semantic-release config (W6/AC-4) — coexisting
changelog`). `git diff --cached --stat` before commit: `docs/changelog.md | 14 +-`,
`pyproject.toml | 53 ++`, `uv.lock | 262 ++` — only the three files touched; nothing under
`src/mambo_power`.

## 1–2. Dependency + config location

`python-semantic-release>=10.6.2` (verified: `uv add --group release python-semantic-release`
resolved 10.6.2) lives in a new `[dependency-groups].release` group, not `dev`. Rationale: it
only runs in the tag-push release job (W7), never in local dev/test/lint — the same
purpose-scoped split this repo already uses for `dev` vs `docs`.

Config location: `pyproject.toml`'s `[tool.semantic_release]` (not a separate `.releaserc`) —
it's the tool's more common modern convention and keeps all packaging/release config in one
file this repo already treats as the config root (`[tool.ruff]`, `[tool.mypy]`,
`[tool.pytest.ini_options]` are all there too).

### Config landed (`pyproject.toml`, verbatim)

```toml
[tool.semantic_release]
version_toml = ["pyproject.toml:project.version"]
tag_format = "v{version}"
commit_parser = "conventional"
allow_zero_version = true
major_on_zero = true

[tool.semantic_release.branches.main]
match = "epic/01-foundation"
prerelease = false

[tool.semantic_release.commit_parser_options]
minor_tags = ["feat"]
patch_tags = ["fix", "perf"]
other_allowed_tags = ["build", "chore", "ci", "docs", "style", "refactor", "test", "merge", "fixtures"]
allowed_tags = [
  "feat", "fix", "perf",
  "build", "chore", "ci", "docs", "style", "refactor", "test", "merge", "fixtures",
]
parse_squash_commits = true
ignore_merge_commits = true

[tool.semantic_release.changelog]
mode = "update"
insertion_flag = "<!-- version list -->"

[tool.semantic_release.changelog.default_templates]
changelog_file = "docs/changelog.md"
output_format = "md"
```

Key decisions, with reasoning:

- **`commit_parser = "conventional"`** — the tool's current, non-deprecated parser (checked via
  its own docs: `angular` still exists but `conventional` is the modern one it documents first).
- **`allow_zero_version = true`, `major_on_zero = true`** — v10's own default flipped
  `allow_zero_version` to `false` (would force straight to 1.0.0 on the very first release).
  This repo's plan is a deliberate `v0.1.0` first tag (T2), so it must be re-enabled explicitly.
  `major_on_zero = true` keeps semver's stricter reading (a breaking change still means a major
  bump even pre-1.0) — this is also exactly what AC-4's fixture expects (see below).
- **`branches.main.match = "epic/01-foundation"`** — the tool's own default release-branch
  pattern is `(main|master)`; this repo releases from `epic/01-foundation`. Discovered this the
  hard way: the first `--print` against the real repo failed with `branch
  'wave/09-release-0.1-s5' isn't in any release groups` until this was set.
- **`other_allowed_tags`/`allowed_tags` include `merge` and `fixtures`** — this repo's own two
  non-standard conventional-commit types (see the A3 tally below). Added so they're recognized
  and render correctly (as non-bumping) in the generated changelog, rather than silently dropped
  as unparseable.
- **`changelog.mode = "update"` + `insertion_flag = "<!-- version list -->"`** — see part 3.

## 3. Changelog insertion mode — the tool's built-in mechanism is sufficient

Researched via context7 (`/websites/python-semantic-release_readthedocs_io_en`): the tool ships
a built-in **update mode** (`ChangelogMode.UPDATE`, the actual default since v10) that reads the
existing changelog file, splits it at a configurable `insertion_flag` (default
`<!-- version list -->` for markdown), and recombines it as
`[content before flag] + flag + [newly generated version sections] + [content that was already
after the flag]`. **No custom template or split-file workaround was needed** — this directly
satisfies "insert section, preserve the rest."

Verified empirically in a throwaway fixture repo (`scratchpad/m9-s5-fixture`, deleted after use):
seeded a `CHANGELOG.md` with an intro paragraph, the flag, and a fake "Existing hand-written
content that must survive untouched" section below it; tagged `v0.1.0`; added `feat`/`fix`/
breaking-change/`chore`/`docs` commits; ran `semantic-release changelog`. Result: the intro
paragraph and the flag were preserved verbatim above; new `## Unreleased` and `## v1.0.0 (...)`
sections were inserted directly below the flag; the pre-existing "must survive untouched" text
came back **byte-for-byte identical**, just pushed further down. Re-running with no new commits
duplicated the `## Unreleased` block — an important operational gotcha, noted below, not fixed
here since it's a CI-wiring (W7) concern.

## `docs/changelog.md` restructure

Original structure: `# Changelog` + a 4-line intro paragraph, then `## [Unreleased]` with its
own 3-line paragraph ("One section per wave, newest first...Nothing on this page has been
released..."), then twelve `###` subsections in one continuous block: two standalone `Fixed`
entries (case30 degeneracy, DC-OPF phase-shifter defect — not wave-titled), nine sections titled
`wave M#` (M8 Added, M8 Changed, M7–M1 Added), and one trailing rollup `### Changed` (no wave
title, individual bullets tagged inline `M6.`/`M5.`/etc.) — then a trailing reference-link line
`[Unreleased]: https://github.com/mambo10005/mambo-power/commits/epic/01-foundation`.

New structure: the top intro paragraph is unchanged. `## [Unreleased]` and its paragraph are
replaced by `<!-- version list -->` (the tool's insertion flag) followed by a new `## Released`
heading with a reworded intro paragraph (same cross-reference to `index.md`'s roadmap table,
reworded to describe history rather than "nothing released yet," since that framing will
shortly become inaccurate). All twelve `###` subsections follow, completely unchanged. The
trailing link's label changes from `[Unreleased]` to `[Released]` (same URL), since the
"[Unreleased]" heading it matched no longer exists — an orphaned, dangling reference link would
be worse than renaming it to match the new heading text it's now paired with.

**Diff proof**: `git diff docs/changelog.md` (full, from the real commit) shows exactly **2
hunks**, confined to the top intro block and the bottom link line — **9 insertions, 5
deletions** total, in a 546-line file. Nothing in the middle — all twelve subsections, all ~530
lines of hand-written prose — appears in the diff at all, which is git's own byte-level
confirmation that content is untouched (not just the nine wave-titled sections AC-4 names, but
every subsection under the old `## [Unreleased]`, since none of them were named as
distinguishable from the nine in a way that would justify treating them differently).

Also confirmed by feeding the exact real (post-restructure) `docs/changelog.md` into a second
throwaway fixture repo (`scratchpad/m9-s5-fixture-realstructure`, deleted after use), tagging
`v0.1.0`, adding one `feat:` commit, and running the real `semantic-release changelog` command
against it: it inserted `## Unreleased` / `## v0.1.0 (date)` sections directly below the flag;
`git diff --stat` on that fixture's copy showed **12 insertions, 0 deletions** — a pure prepend,
confirming the real file's exact heading shape works with the tool as configured.

## 4. AC-4 fixture proof

All in a throwaway git repo under the scratchpad (`m9-s5-fixture`, tagged `v0.1.0`, deleted
after use — never touched this repo's real tags/history). Same `commit_parser_options` as the
real config. Each fixture tagged and re-based off the previous result to isolate one bump type
per commit:

| fixture commit | expected | `semantic-release version --print` computed |
|---|---|---|
| `feat(widget): add widget support` | minor | **0.2.0** (from 0.1.0) |
| `fix(widget): correct off-by-one in widget count` | patch | **0.2.1** (from 0.2.0) |
| `feat(widget): redesign widget API` + `BREAKING CHANGE:` body | major | **1.0.0** (from 0.2.1) |
| `chore: bump internal lint config`, then `docs: fix typo in README` | no bump | **1.0.0**, "No release will be made, 1.0.0 has already been released!" (both) |

All four match expectation exactly, with real command output (not inferred).

## 5. A3 — safety against this repo's actual commit shape

Tallied every commit-type prefix across `epic/01-foundation`'s full 219-commit history
(`git log --oneline epic/01-foundation | awk -F'[(:]' '{print $1}' | sort | uniq -c`):

```
64 docs   48 feat   47 fix   20 test   15 merge
12 chore   5 style   5 refactor   2 perf   1 fixtures
```

Two non-standard types found: `merge` (15 commits) and `fixtures` (1 commit) — both added to
`other_allowed_tags`/`allowed_tags` above.

Three empirical checks (throwaway repo `m9-s5-fixture-default`, deleted after use):

1. **Unrecognized/non-bump types never cause a false bump or a crash.** A single-parent commit
   `merge(m8): wave/08-interop into epic/01-foundation` (an unrecognized type under the
   *default*, un-augmented parser options) computed `no_release`, version stayed at `0.1.0` —
   confirming the tool's allow-list design makes this safe by construction, not by luck.
2. **This repo's real `merge(...)`-labeled commits are genuine two-parent git merges**
   (verified: `git cat-file -p 511c6a0 | grep -c "^parent"` → `2`) — the default
   `ignore_merge_commits = true` excludes them from parsing *entirely*, before the allow-list is
   even consulted. Proved with a deliberately adversarial case: created a real two-parent merge
   commit whose subject was `feat(sneaky): this subject looks like a feature but IS a real git
   merge commit` — `--print` still returned `no_release` / unchanged version, confirming the
   merge-commit exclusion, not just the tag allow-list, is what keeps these safe.
3. **Read-only dry-run against the real 219-commit history.** Ran `semantic-release version
   --print` from the real worktree, `--config` pointed at a **scratch copy** of `pyproject.toml`
   with the `branches.main.match` regex temporarily widened to also accept
   `wave/09-release-0.1-s5` (the worktree's actual checked-out branch) — the committed
   `pyproject.toml` itself was never modified for this test, and `--print` makes no commits, no
   tags, no file writes regardless. Result: `Found 219 commits since the last release! ... type
   of the next release release is: minor` → **0.1.0**. This is driven entirely by the 48 real
   `feat:` commits (the highest bump type present); no `BREAKING CHANGE:` marker exists anywhere
   in the full history (confirmed by the absence of a major bump); no `merge`/`chore`/`style`/
   `fixtures` commit contributed to the bump. **This is why T2's manual-tag-first bootstrap
   matters**: this full-history computation landed on the same number (0.1.0) the wave plans to
   tag by hand, but only by coincidence (first-ever release under `allow_zero_version=true`
   defaults to a minor bump) — a different real commit mix could easily have landed elsewhere,
   and the provenance (a deliberate, PR-reviewed human act vs. an accidental full-history
   replay) is exactly what the spec's "never computed from the full pre-semantic-release
   history" rules out.

## Real findings worth flagging (outside S5's ownership, not fixed here)

- **Windows encoding crash.** `semantic-release changelog` / `version` fails on this Windows
  worktree with `'charmap' codec can't decode byte 0x81 in position ...` reading
  `docs/changelog.md` — the file's non-ASCII prose (em dashes, `›`, etc.) is read through the
  Windows default codepage instead of UTF-8 when `PYTHONUTF8`/`PYTHONIOENCODING` aren't set.
  Fix: set `PYTHONUTF8=1` (or `PYTHONIOENCODING=utf-8`) in the environment before invoking
  `semantic-release`. Confirmed the fix works, and confirmed the coexistence mechanism against
  the real restructured file, in the same run (`m9-s5-fixture-realstructure` test above).
  GitHub Actions runners default to a UTF-8 locale, so this most likely won't reproduce in the
  actual `publish.yml` job (W7, not owned by S5) — but it's a real trap for any Windows
  contributor running `semantic-release` locally, worth a one-line note in whatever
  CONTRIBUTING/W7 documentation gets written.
- **`changelog` is not idempotent against an unreleased/untagged state.** Running
  `semantic-release changelog` twice in a row with no new tag in between duplicates the
  `## Unreleased` block (each run re-splits at the flag and regenerates everything above it from
  current git state; the previous run's already-materialized `## Unreleased` section counts as
  "content after the flag" and is preserved rather than replaced). Not a config bug — this is
  why the tool is meant to be invoked as part of `semantic-release version` (which also tags,
  moving the boundary) rather than repeatedly on its own. Relevant to whoever wires the `version`
  step into a CI job (W7) — flagging so it isn't rediscovered the hard way.

## Gates

```
uv run ruff check .            -> All checks passed!
uv run ruff format --check .   -> 206 files already formatted
uv run mypy                    -> Success: no issues found in 59 source files
```

No file under `src/mambo_power` was touched. No Python fixture/test script was added to the
committed tree — all AC-4/A3 proof work happened in throwaway git repos under the session
scratchpad, deleted after use; there was nothing new for the gates to lint beyond the
`pyproject.toml` edit itself, which the gates above already cover.

## Duration

Well under the 90-minute estimate.
