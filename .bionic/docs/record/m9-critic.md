# M9 — Step-6 independent adversarial critic

Wave: `wave/09-release-0.1` (worktree `C:/Claude Projects/mambo-power-m9`), head `d5724cb`.
Stance: falsify "this is ready to merge." Not the implementer, not a fork of the orchestrator,
not the 6-axis reviewer.

**The 6-axis self-review (`record/m9-review.md`) did not exist when this pass ran.** Every
finding below was reached without it; overlap is possible and unchecked.

Materials read: spec, plan (matrix + `## Assumptions` + `## Handoff`), `m9-scope.md`,
`m9-walk.md`, `m9-audit.md` (both rounds), `m9-ac4-dryrun.md`, `m9-s1/s2/s5/s6/s7` reports
(S3, S4 have none), full `git diff d18aaea..HEAD`.

**Verdict: not clean. Six findings, three of them release-quality.** Nothing here breaks a
discharged AC — every AC verdict in the matrix survives. What these findings share is that they
live in the gap between the ACs: they are consequences of the release the wave exists to enable,
occurring *after* the last thing anybody verified.

---

## C1 — `README.md` is stale to wave M2 and is the PyPI project description of 0.1.0 (high)

`pyproject.toml:9` is `readme = "README.md"`, and `/README.md` is in the sdist allow-list. So
`README.md` **is** the long-description that `publish.yml` uploads to pypi.org — the page every
visitor to `https://pypi.org/project/mambo-power/` sees.

Its Status table (`README.md:32-35`) reads:

```
| M1 | Installable package, `Network` model, ... | merged |
| M2 | DC + AC power flow, typed results, `jobs` API, documentation site, ... | in progress |
| M3+ | DC-OPF, N-1, markets, interchange formats, PyPI 0.1.0 | planned |
```

`git log --oneline -- README.md` returns two commits, the newest `cf3f9fb` (**wave M2**). The
file has not been touched since. Meanwhile `docs/index.md:127-135` reads `merged` for M1–M9.

So the 0.1.0 release will publish, as its own front page, a claim that DC-OPF, N-1, the four
market modes and the interchange formats are *planned* — the entire content of M3–M8 — and that
M2 is in progress. It also says "Not yet on PyPI" (`README.md:37`) on the PyPI page itself.

Why nobody caught it: `README.md` is not in the wave diff, is named by no AC, and the walk drove
the docs site (`docs/`), not the repo root. W4 scoped the roadmap update to `docs/index.md`
only. The design's ownership table names three rendering surfaces for "is this released yet" —
`getting-started.md`, `docs/index.md`, `changelog.md` — and omits the one that ships to PyPI.

The sting: `docs/changelog.md:16-18` explicitly reasons about this class of staleness —
"Which waves have merged ... is tracked in [the home page's roadmap table](index.md), not
restated here, so this page cannot go stale about it." README restates it and did go stale.

Weight: a PyPI release's metadata is effectively immutable — fixing it means yanking 0.1.0 and
cutting 0.1.1. Cost to fix now: one edit. Cost to fix after Step 9: a version burn.

Reproduce: `git log --oneline -- README.md`; `sed -n '30,38p' README.md`; `grep -n readme pyproject.toml`.

---

## C2 — Step 9 reintroduces F-A7 verbatim; the audit fixed the instance, not the mechanism (high)

F-A7 was "`docs/changelog.md` said 'Nothing has been released yet' four lines above a `## Released`
heading." The fix renamed the heading to `## Pre-release history` and reworded that heading's own
paragraph. **The preamble sentence was left intact**, and it is what the contradiction actually
rested on.

`docs/changelog.md:5-8` today:

```
[Semantic Versioning](https://semver.org/). Nothing has been released yet; the first release
will be 0.1.0 on PyPI (wave M9).

<!-- version list -->
```

`<!-- version list -->` is `insertion_flag` in `[tool.semantic_release.changelog]`. Everything
semantic-release ever generates lands **on the line below that sentence**, forever.

I ran the real Step-9 release in a throwaway clone of the wave head:

```
git clone --no-hardlinks <worktree> critic-clone && cd critic-clone
git checkout -B epic/01-foundation          # 0 tags, the real Step-9 state
PYTHONUTF8=1 uv run --no-project --with 'python-semantic-release>=10.6.2' \
    semantic-release version --no-push --no-vcs-release
```

Resulting file:

```
 will be 0.1.0 on PyPI (wave M9).

 <!-- version list -->

+## v0.1.0 (2026-08-31)
+
+- Initial Release
+
 ## Pre-release history
```

"Nothing has been released yet; the first release **will be** 0.1.0" sitting four lines above
`## v0.1.0`. That is F-A7's exact shape, on the exact same file, restored by the tool the wave
installed — and it is permanent: every future generated section inserts beneath the same
sentence. The auditor's round-2 re-check verified the file is coherent *at rest*, which it is;
the defect only exists in the state the wave is built to reach.

Not logged in `## Assumptions`: nothing anywhere states that the changelog preamble must be
rewritten as part of the release action.

Fix: reword the preamble to be release-state-neutral (the way the `## Pre-release history`
paragraph already was), or add it to the Step-9 checklist beside F-A8.

---

## C3 — the tutorials are unrunnable for the reader that 0.1.0 creates; spec A4 is the silent wrong assumption (high)

Tutorials 1, 2 and 4 open with `matpower.load("../../fixtures/matpower/case14.m")`. The wheel is
package-only:

```toml
[tool.hatch.build.targets.wheel]
packages = ["src/mambo_power"]
```

`find src -name '*.m'` → nothing. `fixtures/` ships in the **sdist** only, and `pip install
mambo-power` gets the wheel. So for the reader created by W7 — the one who runs
`pip install mambo-power` — `fixtures/` does not exist and every tutorial's first executable
line raises `FileNotFoundError`.

Spec **A4** is where this hid: *"a notebook executed by nbmake in CI has access to whatever
fixtures/data the tutorials reference (**bundled MATPOWER cases**) without network access — same
environment guarantee the examples already have."* "Bundled" reads as bundled-with-the-package.
They are bundled with the *repo*, and deliberately excluded from the wheel. A4 is true of CI and
false of the audience the wave exists to serve, and the ambiguity is why nobody looked.

Two compounding factors:

- **Only tutorial 1 states the prerequisite.** Its intro says "This tutorial assumes
  `mambo_power` importable and a clone of the repository on disk (for the bundled MATPOWER
  fixtures)." Tutorials 2 and 4 use the identical path with **no such caveat** (verified: `clone`
  appears nowhere in either notebook's source). W1 requires each notebook be "self-contained,"
  and both are linked as direct entry points from `docs/tutorials/index.md`'s table.
- **Tutorial 1's own pointer breaks at Step 9.** It says "see [Getting started] — one `uv sync`
  and you're set." Today getting-started tells you to clone, so that holds. The moment W5's PyPI
  install text lands (the same action as the tag, per AC-3), getting-started tells the reader to
  `pip install mambo-power`, and tutorial 1's advice becomes precisely wrong for the path it
  points at.
- `include_source: false` in `mkdocs.yml` removes the notebook download link, so a site reader
  has no way to obtain the notebook and see the directory structure the path assumes.

Note `examples/*.py` use `fixtures/matpower/case14.m` — **repo-root**-relative. The tutorials use
a *different* relative base (notebook-dir-relative, which is what nbmake's cwd makes correct).
Two conventions now coexist, neither documented.

This is not a merge blocker — pre-release, every reader has a clone. It is a Step-9 blocker of
the same kind as F-A8, and it is not on any checklist.

Reproduce: `grep -o 'matpower.load([^)]*)' docs/tutorials/*.ipynb`; `sed -n '/hatch.build.targets.wheel/,+2p' pyproject.toml`; `find src -name '*.m'`.

---

## C4 — the site tells readers its numbers come from CI; by design, nothing checks that (medium)

`docs/tutorials/index.md`, shipped, reader-facing:

> "Every code cell in every notebook actually runs — they're executed fresh in CI on every push
> ([nbmake](...)), so **the numbers you see rendered here are the real ones**, not hand-typed
> illustrations."

`mkdocs.yml` asserts the same to maintainers: *"the outputs already stored in the .ipynb files
ARE the CI-verified numbers."*

Neither is established by the toolchain:

- `execute: false` — the site renders the outputs **stored** in the `.ipynb`, produced by S1's
  one-time `nbconvert --execute` pass in August.
- `nbmake` verifies the source *runs without raising*. It does not write outputs back and does
  not compare them to what is stored — that is output-diffing, which **S2 explicitly rejected**
  ("no output-diffing... this repo's own float-noise history argues against it"). The rejection
  is defensible. Asserting the property it would have proven is not.

So S2's ruling and S2's own `mkdocs.yml` comment contradict each other, and the contradiction was
then promoted into reader-facing prose. There is no mechanism that would catch stored outputs
drifting from current source.

Corroboration this is not theoretical: `m9-walk.md` re-executed tutorial 1 fresh and found "one
cell differs only in stdout stream-chunking, not content" — the stored and freshly-executed
outputs already differ. And `a221482` (S7's ruff-clean, after S1's execution pass) rewrote source
cells in all four notebooks while leaving outputs untouched, so stored outputs are now provably
from a *different source revision* than the one shipped.

I hand-verified `a221482` is behaviourally inert — the one manually-split f-string concatenates
to byte-identical text, and the rest is import sorting and call reflow. So the current numbers
are fine. The claim is what's wrong, and it is the claim future maintainers will trust.

Fix: soften both sentences to what is true ("executed fresh in CI on every push, so the code you
see is proven to run"), or add an outputs-match check and keep the claim.

---

## C5 — the AC-3 guard is one-directional; post-release it reports "pre-release state" while a release tag exists (medium)

Demonstrated in the post-release clone from C2 (tag `v0.1.0` present and reachable from `HEAD`):

```
$ git tag --list 'v*' --merged HEAD
v0.1.0
$ python3 scripts/check_pypi_sequencing.py
OK: no unqualified PyPI install text found (pre-release state).
exit=0
$ sed -n '9p' docs/getting-started.md
mambo-power is not on PyPI yet (that is wave M9, version 0.1.0). Until then, install from
```

The package is released; the docs say it is not; the guard prints "(pre-release state)"; CI is
green. `docs/index.md:37` ("Nothing is on PyPI yet") is not checked at all.

AC-3's literal wording is one-directional, so this is not an AC failure. But the design's
ownership table calls this script "**the agreement test**" for the concept "is this released
yet," whose SSoT is the tag — and it enforces only `install-text ⇒ tag`, never `tag ⇒
install-text`. AC-3's stated purpose is "so this can't drift silently in a later wave either";
half the drift space is uncovered, and it is the half that opens the instant Step 9 fires.

This is adjacent to F-A9 but distinct: F-A9 is a false negative *within* the implemented
direction (the `\bnot\s+yet\b` qualifier being too broad). This is a whole missing direction.

Cheap fix: when a `v0.1.0`+ tag is reachable, fail on pre-release framing rather than passing on
its absence — the same function, inverted, ~6 lines.

---

## C6 — two contradictory Step-9 procedures; the riskier one is the documented one (low-medium)

F-A8 (carried forward, correctly) says: *"Bump `pyproject.toml` to `0.1.0` in the same action as
pushing the `v0.1.0` tag."* That is the **manual** path, and it is the only path that can trip
S6's version-consistency gate — a gate S6 added that no AC asked for (the plan says so:
"not required by any AC, but real"). The gate exists to catch exactly the mistake the documented
procedure invites.

The wave also installed a tool that does the whole thing atomically. I ran it (C2's transcript):

```
$ semantic-release version --no-push --no-vcs-release
The next version is: 0.1.0! 🚀
$ git tag -l                    → v0.1.0
$ grep '^version' pyproject.toml → version = "0.1.0"
```

Version bump, changelog insertion, commit, and tag-at-the-bump-commit, in one command —
`publish.yml`'s gate cannot fail on this path, because tag and `pyproject.toml` are written by
the same operation.

Nothing in the spec, plan, Handoff or any report says which path Step 9 takes. They produce
*different repo states* (the tool also writes a changelog section and a release commit). Pick one
and write it down; if it is the tool, F-A8's instruction should be replaced, not just noted.

Related ordering trap the F-A8 note does not spell out: on the manual path the tag must point at
the **bumped** commit. `actions/checkout@v4` on a tag push checks out the tag's tree, so
`git tag v0.1.0 && <bump> && git commit` fails the gate even though both acts happened "in the
same action."

---

## C7 — minor

- `mkdocs-jupyter` is added to the `docs` group with **no version floor**, while all three of its
  siblings are pinned (`mkdocs-material>=9.7`, `mkdocstrings[python]>=1.0`,
  `pymdown-extensions>=10.16`). Breaks that group's own convention. (`nbmake` unpinned in `dev`
  is consistent — `dev` is unpinned throughout.)
- `.gitignore` gains `.cache/` with no explanation in any commit message, report, or AC. Almost
  certainly nbmake/jupyter debris; unremarked scope.
- The `release` group means every `uv sync --locked --all-groups` — five CI jobs including
  `pages.yml`'s Pages deploy — now installs python-semantic-release (30 packages). Harmless, but
  the tool is never invoked by any workflow; it is a local-only dependency paid for on every
  CI leg.

---

## Falsification attempts that failed

Recorded because "no issues" is only meaningful with the attempts attached, and because these
close off avenues the next reviewer would otherwise re-walk.

1. **"`semantic-release` will not bootstrap to 0.1.0."** The strongest structural suspicion I
   had: AC-4 only ever tested *from an existing `v0.1.0` tag*, and the spec's Not-doing forbids
   "computing the semantic version from full pre-M9 history" — yet Step 9's real state is **zero
   tags**, i.e. exactly full-history. 48 `feat` commits on the branch and `major_on_zero = true`
   meant a single `BREAKING CHANGE:` footer anywhere would land 1.0.0. `git log --grep=BREAKING`
   hit `34710aa` — S5's own config commit — three times, and S5's history tally that "proved"
   this was run *before that commit existed*. **Ran it: `0.1.0`.** All three hits are prose, none
   in footer position (`  BREAKING CHANGE still jumps`, mid-line, and `BREAKING CHANGE anywhere`
   with no colon). The config is correct on the one path nobody tested.

2. **"`docs/index.md` carries the same self-contradiction F-A7 found in the changelog."** The
   roadmap row reads `| M9 | Tutorials, semantic-release changelog, PyPI 0.1.0 trusted
   publishing | merged |`, which a skimmer reads as "0.1.0 shipped." Checked the status prose:
   it closes with "Nothing is on PyPI yet — install from source." S3 handled it. The row
   describes the *pipeline* merging, and the prose disambiguates within the same block. Clean.
   (`docs/index.md` still needs C5's other-direction fix at Step 9, but that is C5, not this.)

3. **"`publish.yml` has never been executed and the one-shot release will fail on a defect in
   it."** Attacked four ways. Both workflows YAML-parse (`yaml.safe_load`) and the trigger
   resolves to exactly `{'push': {'tags': ['v*']}}` — no `branches`, no `pull_request`, no
   `workflow_dispatch`. `needs: []` looked wrong until I checked the pre-existing jobs
   (`examples`, `install-smoke`, `docs`) — it is this repo's established convention, not a new
   defect. The remote is genuinely `https://github.com/mambo10005/mambo-power.git`, matching the
   owner/repo the trusted-publisher values were built against. The version-check step's
   `uv run --no-project --python 3.12` is preceded by `uv python install 3.12`. No defect found.
   One residual I could not settle from here, flagged as **uncertain, not a finding**: the
   `publish` job's job-level `permissions:` block replaces the workflow-level `contents: read`,
   leaving `id-token: write` and everything else `none`. `actions/download-artifact@v4` should be
   fine for a same-run artifact (it uses the runtime token, not `GITHUB_TOKEN`), but a
   same-workflow-run download under `actions: none` is not something I could verify offline, and
   the blast radius is a build that succeeds followed by a publish that cannot start. Adding
   `contents: read` alongside `id-token: write` costs nothing and removes the question.

4. **Authenticity spot-checks on evidence I could re-run.** `mkdocs build --strict` at the
   current head `d5724cb` (not `a221482`, where the matrix recorded it): **exit 0**, no
   project-level warnings, only the vendored Material 2.0 notice. Manual's nav entries: **12**,
   matching AC-2's claim. `a221482`'s hand-split f-string: concatenates to text identical to the
   original. No fabrication found.

---

## Disposition

Nothing here refutes a discharged AC, and I found no fabricated evidence. C1 and C3 are the two
I would not merge without: C1 because a stale README becomes immutable the moment W7 fires, and
C3 because the wave's headline deliverable breaks for the audience its other headline deliverable
creates. C2 and C5 are Step-9 checklist items of the same class as F-A8 and belong beside it.
C4 is a claim to fix, not code. C6 is a decision to write down. C7 is housekeeping.

The pattern across C1, C2, C3 and C5 is one thing: **every AC verifies the repository at the
merge head, and every one of these defects begins at the tag.** The wave has no acceptance
criterion that looks at the state after the release it exists to make possible. F-A8 was the
first instance of that blind spot; it is not the only one.
