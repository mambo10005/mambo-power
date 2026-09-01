# M9 AC-4: semantic-release dry-run reproduction (durable transcript)

**Result: all four observed outputs match expectations exactly. No discrepancies.**

## Method

This reproduces AC-4 (semantic-release dry-run version classification) for wave M9
in a disposable clone, isolated from the real wave worktree and main repo. The
clone was made from `wave/09-release-0.1` (checked out from
`C:/Claude Projects/mambo-power-m9`), then switched to a branch named
`epic/01-foundation` — the release branch the tool is configured to expect — and
tagged `v0.1.0` to simulate the bootstrap tag that wave M9 Step 9 will eventually
cut in the real history (this repo has no real tags yet). `uv sync --group
release` was run once to install `python-semantic-release` and its dependencies.
Each of the four fixtures below was then run from the **same starting state**
(`git reset --hard v0.1.0` immediately before each fixture commit) rather than
cumulatively — this is deliberate: it tests each commit-message classification
rule (feat / fix / breaking change / chore) independently against the same base,
so one fixture's result cannot leak into another's. Every command and its raw
terminal output below is copied verbatim, not retyped or paraphrased. The
disposable clone was deleted after this transcript was captured.

## Transcript

```
=== FIXTURE 1: feat (minor) ===
$ git reset --hard v0.1.0
HEAD is now at a221482 style(m9-s7): ruff-clean the four tutorial notebooks (source-only, outputs unchanged)

$ git commit --allow-empty -m "feat(ac4-fixture): add a new capability"
[epic/01-foundation 1db20d4] feat(ac4-fixture): add a new capability

$ uv run --group release semantic-release --noop version --print
🛡 You are running in no-operation mode, because the '--noop' flag was supplied
[19:09:11] WARNING  Token value is missing!                       config.py:866
0.2.0

Expected: 0.2.0 — OBSERVED: 0.2.0 (match)

=== FIXTURE 2: fix (patch) ===
$ git reset --hard v0.1.0
HEAD is now at a221482 style(m9-s7): ruff-clean the four tutorial notebooks (source-only, outputs unchanged)

$ git commit --allow-empty -m "fix(ac4-fixture): correct a defect"
[epic/01-foundation afc5742] fix(ac4-fixture): correct a defect

$ uv run --group release semantic-release --noop version --print
🛡 You are running in no-operation mode, because the '--noop' flag was supplied
[19:09:46] WARNING  Token value is missing!                       config.py:866
0.1.1

Expected: 0.1.1 — OBSERVED: 0.1.1 (match)

=== FIXTURE 3: breaking change (major) ===
$ git reset --hard v0.1.0
HEAD is now at a221482 style(m9-s7): ruff-clean the four tutorial notebooks (source-only, outputs unchanged)

$ git commit --allow-empty -m "feat(ac4-fixture): change the public API" -m "BREAKING CHANGE: renames the primary entry point"
[epic/01-foundation 7d62acf] feat(ac4-fixture): change the public API

$ uv run --group release semantic-release --noop version --print
🛡 You are running in no-operation mode, because the '--noop' flag was supplied
[19:10:09] WARNING  Token value is missing!                       config.py:866
1.0.0

Expected: 1.0.0 — OBSERVED: 1.0.0 (match)

=== FIXTURE 4: chore (no release) ===
$ git reset --hard v0.1.0
HEAD is now at a221482 style(m9-s7): ruff-clean the four tutorial notebooks (source-only, outputs unchanged)

$ git commit --allow-empty -m "chore(ac4-fixture): housekeeping only"
[epic/01-foundation f22bf29] chore(ac4-fixture): housekeeping only

$ uv run --group release semantic-release --noop version --print
🛡 You are running in no-operation mode, because the '--noop' flag was supplied
[19:10:37] WARNING  Token value is missing!                       config.py:866
0.1.0
No release will be made, 0.1.0 has already been released!

Expected: "no release will be made" — OBSERVED: "No release will be made, 0.1.0 has already been released!" (match)
```
