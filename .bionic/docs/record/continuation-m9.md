# Continuation — M9 release-0.1 closed; epic 01-foundation's last wave

Wave M9 (`release-0.1`), triple build · audited · wave, integration branch `epic/01-foundation`
(base `d18aaea`, baseline 1539/4).

- **Merge SHA:** `f993cda` (`--no-ff`, local; wave head `ce381d9`, zero conflicts —
  `git merge-tree` dry run confirmed clean before the real merge)
- **Suite:** 1266 passed (1262 unit + the Step-6 fix batch's own 4 new tests), `tests/parity`
  292 passed / 4 skipped — verified independently three times (wave worktree, post-merge on
  `epic/01-foundation`, and again live in CI)
- **Pushed and CI-verified for real** — `epic/01-foundation` pushed (`9012c43..eda3a9d`),
  GitHub Actions run `33475672236`: **all 10 jobs green**, including the wave's own two new
  jobs (`tutorials (nbmake)`, `pypi sequencing guard`). Docs (GitHub Pages) run `33475672282`:
  both jobs green, site live. Fetched `https://mambo10005.github.io/mambo-power/tutorials/`
  directly (T3, cold client) and confirmed all four tutorial titles render.
- **Independent verdicts:** walk (`m9-walk.md`, dispatched first, no spec/plan/AC access,
  zero `AC-[0-9]` occurrences) — clean, a few non-blocking surprises. Auditor: round 1
  **REFUTED** at wave level (proof gaps, not implementation — F-A1 through F-A9, 9 findings),
  round 2 **CONFIRMED** after 6 fixed (`m9-audit.md`, both rounds). 6-axis reviewer: FLAG on
  5 axes / PASS on performance, 16 findings R1–R16 (`m9-review.md`). Independent critic: 7
  findings C1–C7, three "would not merge without" (`m9-critic.md`). All findings proportionate
  to Step 6 fixed in one batch (`dc677f8`, 14 files), independently re-verified twice.
- **AC-5 waived, not refuted:** the live pypi.org trusted-publisher check is out of the
  orchestrator's reach (no PyPI account access) — static half (workflow YAML) confirmed by
  three independent readers; live half waived by the user, deferred to the real tag push.
- **ADR-013** — tutorial fixtures ship in the sdist, not the wheel; a permanent constraint, not
  a pre-release one (Step-6 critic finding C3).
- **Epic status: this was the last wave on the roadmap.** `epic/01-foundation` now needs its
  own one-time closing act (merge to `main`) — see "What's left" below. No M10 exists.

## What M9 shipped

Four narrative tutorial notebooks (`docs/tutorials/`), difficulty-tiered (beginner power flow →
intermediate DC-OPF+N-1 → intermediate nodal market → guided fork into agents/interop),
execution-tested fresh in CI via `nbmake` (no output-diffing — this repo's own float-noise
history argued against it), rendered on the docs site via `mkdocs-jupyter` (`execute: false`,
stored outputs only — CI proves the code runs, not that the displayed numbers are fresh, a
distinction the Step-6 critic found overclaimed and fixed). Docs nav/home reorg: `Tutorials`
section above `Manual`, roadmap table all-`merged`, "where do I go" table gains a row.
`scripts/check_pypi_sequencing.py` — bidirectional (Step-6 critic C5: the first cut only
checked "unqualified install text ⇒ tag exists," not the reverse) — guards
`getting-started.md`'s PyPI claim against the real tag state, wired into CI as its own lean
job. `python-semantic-release` configured (`allow_zero_version`/`major_on_zero` so the first
tag stays `0.1.0`; `branches.main.match = "epic/01-foundation"` until the epic merges),
changelog restructured to coexist (nine hand-written wave sections preserved verbatim, new
`## Pre-release history` heading — critic F-A7/C2 both caught and fixed a self-contradiction in
the surrounding prose, twice, because the first fix addressed the heading but not the sentence
that actually caused it). `publish.yml` — tag-only trigger, OIDC-only (no stored credential),
`pypi` GitHub environment as a manual-approval gate, every action SHA-pinned (critic R13 — the
one workflow in the repo holding `id-token: write`, pins resolved and verified via `gh api`,
never hand-typed). `docs/contributing.md`'s new "Cutting a release" section — the release chain
(semantic-release config → `pyproject.toml` version → `publish.yml`'s consistency gate) had
three individually-correct pieces and no procedure joining them in the shipped repo until this
section existed (reviewer finding R11, the single most important finding of the wave).

## What's left (not part of this wave, explicitly deferred)

1. **Cut `v0.1.0`.** From a clean `epic/01-foundation` checkout: `PYTHONUTF8=1 uv run --group
   release semantic-release version` (bumps `pyproject.toml`, writes the changelog section,
   commits, tags — atomically, so `publish.yml`'s version-consistency gate cannot fail), then
   `git push --follow-tags`. Full procedure: `docs/contributing.md#cutting-a-release`.
2. **Approve the `pypi` GitHub environment's manual-approval gate** when `publish.yml`'s
   `publish` job pauses for it (repo Settings → Environments → `pypi`).
3. **Confirm the PyPI trusted-publisher configuration** is actually complete on pypi.org
   (owner `mambo10005`, repo `mambo-power`, workflow `publish.yml`, environment `pypi`) — this
   is what AC-5's waiver deferred; the real tag push is what finally answers it, live.
4. **Merge `epic/01-foundation` into `main`, once** — the epic's own final, one-time closing
   act (per `epic.plan.md`), separate from and after the PyPI release. Not performed as part of
   this wave; a human decision on timing, same class as the push/tag/PyPI actions above.

## Carry-overs (not blocking, recorded so they aren't lost)

1. **F-A6 / R-review Row-2** — the design's ownership table prescribed an agreement test for
   "the wave's own completion state" across its rendering surfaces; never implemented. The
   6-axis reviewer found the wave already solved half of it *by design* (`docs/changelog.md`
   now refuses to restate merge status, deferring to `index.md`'s roadmap table) and recommends
   recording this as resolved-by-design-change, residual pair (`epic.plan.md`'s row vs.
   `index.md`'s table) explicitly declined rather than left as "never checked." **Two slices
   (S3, S4) left no report artifact at all** — the sixth F8/F11/F17-shaped vanished-bookkeeping
   incident this session; every verdict resting on their work was independently re-verified by
   the orchestrator and/or the auditor rather than trusted from a report that doesn't exist.
2. **F-A9 / R3-adjacent** — the PyPI-sequencing guard's pre-release qualifier pattern (`not
   (yet )?on pypi` / bare `not yet` / `wave m9`) is broad enough that an unrelated "not yet"
   sentence near an install block could disable the tag check for that block, and `wave m9`
   will stay true of this repo's prose forever. R3's prerelease-tag fix (this wave) closed the
   sharper, active half of this class; the qualifier-breadth half is real but low-stakes, left
   for a future wave unless it actually bites.
3. **R4/R5** — the guard's `_blocks()` splitter isn't fence-aware (a blank line inside a code
   fence splits context incorrectly); low probability against today's page, matters for
   durability across future waves that might touch `getting-started.md`.
4. **R8/R9/R10/R14/R15** — assorted CI/script nits (a no-op `needs: []`, a dead `argv` param, a
   heavier-than-needed version-check invocation, a third narrower "what's a release tag"
   definition, the `tutorials` CI job installing dependency groups no notebook needs). None
   change behavior; batched here rather than fixed piecemeal.
5. **C1's own caveat** — `README.md` (PyPI's project-description page, effectively immutable
   once published) was rewritten to match reality this wave, but nothing guards it against
   going stale again the way `getting-started.md`/`index.md`/`changelog.md` now do. If a future
   wave changes wave-status language, check `README.md` by hand.
6. **A1** (epic) — a live PyPI trusted-publisher check was never independently completed by
   this SDLC run (see "What's left" #3 above); this is the standing, expected gap, not a new
   one.

## The M9 lessons worth carrying

1. **A hook's "this passed before, why does it fail now" is worth tracing to ground before
   working around it.** The evidence gate's field detector is line-anchored
   (`^[[:space:]]*key[[:space:]]*:`); prose-style evidence ("cmd: X; pass: Y; total: Z") only
   satisfies it by accident, depending on which fields happen to land at a physical line start.
   It passed for several commits, then blocked a routine `--amend` the moment the accident
   didn't recur. The fix (one field per physical line) is cheap once found; finding it took
   reading the hook's actual regex rather than guessing at the plan's prose.
2. **A genuinely blocking gate (the Waiver Protocol's "user-only" moves) is not something to
   route around, even under schedule pressure.** AC-5's live pypi.org check and Step 9's real
   PyPI publish both stayed correctly un-closeable by the orchestrator through to the end of
   the wave — asked directly, twice, rather than self-authorized either time.
3. **Independent review at every gate this wave found real, load-bearing defects that three
   prior passes (implementation, orchestrator spot-checks, the walk) all missed** — a shipped
   self-contradiction in `docs/changelog.md` (twice — the heading fix and the preamble fix were
   two separate findings, F-A7 then C2/R1, because the first fix addressed the symptom, not the
   mechanism), a packaging gap that breaks the wave's own headline tutorials for the exact
   reader the wave's other headline deliverable (PyPI publishing) creates (C3/ADR-013), and a
   release procedure that existed in three individually-correct pieces with no code path
   joining them (R11) — found by a fresh reviewer tracing user input to callsite, not by anyone
   who had already decided the wave was done.
4. **Reusing an auditor for a fixes-only re-check (rather than a full fresh dispatch) worked
   well and stayed genuinely independent** — round 2 re-executed every claim itself (a different
   dangling-link fixture for the revert-and-watch, its own fresh greps and diffs) rather than
   trusting the round-1-to-round-2 diff's own description of what changed.
5. **A live push + real CI run is not optional evidence for a release wave**, even when every
   local check has passed — this repo's own case30 degeneracy (found only when CI resumed after
   weeks idle, closed before M9 opened) is the standing proof that a local sweep on one machine
   cannot see everything a real, multi-platform CI matrix can.

## Process notes for the epic's closing act (main merge) and any future epic

- Baseline on a clean checkout before any agent enters a worktree; one agent per worktree;
  `.bionic/docs/` committed with every checkpoint; `.bionic/tmp/` wiped of wave-scoped ephemera
  at Step 8, session-infrastructure state files left alone.
- Walk first, from the real running surface, forbidden the spec/plan/AC list, artifact
  machine-checked for zero `AC-[0-9]` occurrences.
- When an auditor or critic finds something fixable, fix it and re-dispatch for an independent
  re-check rather than trusting the fix's own description — this wave's round-2 audit and the
  two post-fix verification dispatches all caught their assigned scope by re-executing, not by
  reading a diff.
- Remove worktrees with `git worktree remove --force`; if it hangs, `git worktree prune -v` →
  PowerShell junction-check (`Get-ChildItem -Attributes ReparsePoint -Recurse`) → Bash `rm -rf`
  only once zero junctions are confirmed.
- A hook that blocks unexpectedly is worth reading, not routing around — this wave found and
  fixed one real bug in `canonical-sdlc-governing-skill.sh` (Windows backslash-path
  normalization, missing from a rewritten version of the hook) this way.
