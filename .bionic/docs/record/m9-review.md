# M9 — Step-6 six-axis self-review (stance 1)

Reviewer: code-reviewer dispatch, `audited` rigor. Stance-1 self-review only — the adversarial
stance-2 critic runs separately and its findings are not folded in here.

Scope: `git diff d18aaea..HEAD` in `C:/Claude Projects/mambo-power-m9`, branch
`wave/09-release-0.1`, head `d5724cb` ("fix(m9): docs/changelog.md contradicted itself").
16 files, +3024/−32 (of which `uv.lock` is +1141).

Context read first: the spec's `## Design` (domain model, component boundaries, ownership
table), the plan (Verification Matrix, task ledger, Handoff), and `record/m9-audit.md` including
its §6 round-2 re-check. The audit's three carried-forward items (F-A6, F-A8, F-A9) are
addressed below on their code-quality merits rather than restated.

Findings are numbered **R1–R16** to keep them distinct from the auditor's `F-A*` and the
critic's `C*`.

---

## 0. State of the tree at review time

**The worktree is dirty.** `git status --short` at review time:

```
 M scripts/check_pypi_sequencing.py
 M tests/unit/test_pypi_sequencing_guard.py
```

The uncommitted diff makes the sequencing guard **bidirectional** — `check()` now also fails
when a `v0.1.0`+ tag is reachable but the page still reads pre-release — and its docstring
attributes this to "Step-6 critic finding C5". So a fix for a parallel critic finding is in
flight in the same tree I am reviewing.

Everything below is a review of the **committed** state at `d5724cb`, which is the diff scope I
was given. Where the in-flight C5 change alters a finding's severity I say so explicitly
(**R3** is the case that matters, and it gets *worse* under the C5 fix, not better).

---

## 1. Correctness — **FLAG**

**What holds.** I could not find a functional defect in any of the new surfaces.

- **Notebooks.** A sub-review cross-checked every `mambo_power` call, keyword argument and
  attribute access in all four notebooks against the real source under `src/`, then re-executed
  all four fresh (`nbconvert --execute` against the repo venv) and diffed regenerated stdout
  against the committed stored outputs. **Every stored output reproduces byte-for-byte** —
  the OPF cost ($7642.59/h), the N-1 counts (18/19), the settlement figures
  ($1,000/$300/$700), the strategic-bidding climb to $60.00/MWh. `PolynomialCost` /
  `PolynomialBid`'s highest-order-first coefficient convention
  (`src/mambo_power/model/entities.py:113-151`) is used correctly in both hand-built networks,
  and the derivative-based "marginal value" comments are arithmetically right. No notebook
  imports `requests`/`urllib`/`socket`/`subprocess`; confirmed imports are
  `mambo_power{,.io,.model,.market.agents}` and `numpy` only, so the offline `nbmake` run in CI
  is safe.
- **`publish.yml`.** Trigger is exactly `on: push: tags: ["v*"]` — no `branches:`, no
  `pull_request:`, no `workflow_dispatch:`. OIDC wiring is right (see §4).
- **`[tool.semantic_release]`.** Table shapes are valid for python-semantic-release ≥10
  (`changelog.mode`/`insertion_flag`, `changelog.default_templates.changelog_file`),
  `allow_zero_version=true` + `major_on_zero=true` produce exactly the bump table the comment
  claims, and `ignore_merge_commits=true` correctly excludes this repo's 15 real `merge(...)`
  two-parent commits before `other_allowed_tags` is consulted.
- **The guard script.** `REPO_ROOT` resolution, the `--merged HEAD` tag query, and the
  `fetch-depth: 0` that makes it meaningful in CI are all correct; the 20 unit tests carry
  genuine failing cases (not just green paths).

**R1 — `docs/changelog.md:54-56` misdescribes the semantic-release insertion direction.**
*(moderate; shipped, reader-facing, operationally misleading)*

> "Its built-in update mode inserts each new release's section **above** the
> `<!-- version list -->` flag now at the top of this page"

S5's own verified fixture says the opposite (`record/m9-s5-report.md:87-89`):

> "the intro paragraph and the flag were preserved verbatim above; new `## Unreleased` and
> `## v1.0.0 (...)` sections were **inserted directly below the flag**"

The observed behaviour is what the file's actual layout depends on (flag at line 8,
`## Pre-release history` at line 10 — new releases land *between* them). A maintainer who
believes the shipped prose and hand-edits or relocates content "above the flag" accordingly
will move the insertion boundary and break the coexistence guarantee W6 exists to provide.
One-word fix: *above* → *below*.

**R2 — `docs/contributing.md:130` instructs contributors to update a heading this wave
deleted.** *(moderate; shipped, reader-facing)*

> "Keep the [changelog](changelog.md) `Unreleased` section current for user-visible changes."

`grep -n '^## ' docs/changelog.md` returns exactly one H2: `## Pre-release history`. S5 replaced
`## [Unreleased]` with `<!-- version list -->` + `## Pre-release history`. `contributing.md` was
edited by this wave (S4 added the `pypi-sequencing` paragraph at :46-51) and this line was left
behind. A contributor following the contributing guide now looks for a section that does not
exist.

This is the **third** instance in this wave of the same defect class the auditor found as F-A7
(`docs/changelog.md` saying "nothing has been released" above a `## Released` heading): a doc
surface left asserting something the mechanism no longer does. F-A7 was fixed at `d5724cb`;
R1 and R2 are the two that were not looked for.

**R3 — `_is_release_tag` accepts prereleases as satisfying "a `v0.1.0`+ tag", and the
in-flight C5 fix turns that from permissive into actively harmful.** *(moderate; confirms and
sharpens the audit's F-A9)*

`scripts/check_pypi_sequencing.py:75` — `re.fullmatch(r"v(\d+)\.(\d+)\.(\d+)(?:[-+].*)?", tag)`
discards the prerelease suffix, so `v0.1.0-rc1` yields `(0,1,0) >= (0,1,0)` → `True`. By semver
a prerelease sorts *below* its release, so this is wrong on its own terms, and the docstring's
"at or above v0.1.0" is not what the code does.
`test_is_release_tag_shapes_accepted` (`tests/unit/test_pypi_sequencing_guard.py:190-192`)
parametrises `"v0.1.0-rc1"` as an accepted shape, so the test **enshrines** the behaviour rather
than pinning the intended one.

Committed behaviour: an rc tag merely *permits* live PyPI install text. **Under the uncommitted
C5 bidirectional change it *requires* it** — with `v0.1.0-rc1` reachable and the page still
reading "not on PyPI yet", `check()` returns
`FAIL: a v0.1.0+ git tag is reachable from HEAD, but docs/getting-started.md ... still reads as
pre-release`. Cutting a release candidate — the normal way to smoke-test a first trusted-publish
run — would turn the `pypi-sequencing` job red until someone writes a PyPI claim that is false.
Fix `_is_release_tag` to reject any tag with a prerelease suffix and flip the test to assert
that, ideally in the same change as C5.

**R4 — `NOT_YET_PATTERN` is broad enough that the durability clause is not met.**
*(moderate; confirms F-A9)*

`scripts/check_pypi_sequencing.py:46-48` treats a block as pre-release framing if it matches
`not (yet )?on pypi` **or** bare `\bnot\s+yet\b` **or** `\bwave\s+m9\b`, and
`has_unqualified_pypi_install_text` (`:67`) counts the **entire preceding block** as context.
Concrete false negative: a paragraph reading "If you have not yet installed uv, see …"
immediately above the install fence silently disables the tag check for that fence. `wave m9`
will also stay true of this repo's prose forever. Narrow it to the `not …on pypi` alternative
(and, if the M9 escape hatch is still wanted, a single explicit sentinel comment rather than a
phrase that can occur by accident).

**R5 — `_blocks()` is not fence-aware.** *(minor)*

`re.split(r"\n\s*\n", content)` splits on any blank line, including one inside a fenced code
block. A fence containing a blank line therefore splits into two "blocks", and the qualifying
sentence that preceded the fence ends up two blocks back, out of the one-block context window.
Low probability against today's page; it matters because durability across future waves is the
guard's whole stated purpose.

**R6 — `03-nodal-market.ipynb` cell 5 gives a self-contradictory explanation.** *(minor)*

> "The elastic load `d1` doesn't buy its full 100 MW; it buys up to where its own bid says the
> price is no longer worth it, and the branch's 20 MVA cap is exactly what's standing between
> the cheap generator and the rest of demand."

In this scenario `d1`'s bid has a flat $45/MWh marginal value across the whole [0, 50] MW
segment it operates in and stays profitable well past 20 MW against $10/MWh generation — the
branch rating is the *sole* binding constraint. The second clause is correct and contradicts the
first. It matters because this is the cell teaching how congestion and demand elasticity show up
differently in an LMP. One-sentence rewrite.

**Verdict: FLAG.** No functional defect and no FAIL. Three shipped doc surfaces state something
the code does not do (R1, R2, R6), and the guard's own durability clause is not met (R3, R4, R5).

---

## 2. Readability — **FLAG**

**What holds, and it is genuinely above average.** Comment density and provenance in
`ci.yml`, `mkdocs.yml`, `publish.yml` and `pyproject.toml` are the best thing in this diff —
every non-obvious choice carries both its rationale and its wave/AC reference. `mkdocs.yml`'s
`execute: false` comment explains why the plugin must *not* re-execute (nbmake already owns
execution) rather than just stating the setting; `ci.yml`'s `tutorials` job comment explains why
it is one leg and not five; `publish.yml`'s OIDC comment explains that the *absence* of a
`password:` input is the mechanism. A future maintainer will not have to reconstruct any of it.
The notebooks' prose is clear and correctly sequenced, tiering is real (02 explicitly builds on
01's dispatch, 03 on 02's LP/QP machinery, 04 forks from the first three), and there is no dead
cell, TODO, or scratch artifact anywhere in the four.

**R7 — `docs/tutorials/index.md` overstates reading time by ~4–5×.** *(moderate; it is the
landing page for the wave's headline deliverable)*

> "these are the fifteen-to-twenty-minute-each story of what the package actually does"

Measured markdown prose per notebook: 727 / 766 / 696 / 888 words → **~3–4.5 minutes** each at
200–250 wpm; ~5–8 minutes generously including code and outputs. The number was inherited from
spec W1's "~15–20 min read" rather than measured. The auditor treated this as an uncovered
requirement clause; the sharper problem is that it is now a **checkable false claim in a shipped
doc**, and the first sentence a reader of the Tutorials section sees. Either correct the index
(five-to-eight minutes) or lengthen the notebooks — but do not ship the spec's aspiration as a
statement of fact. S1 disclosed its own word counts honestly (`m9-s1-report.md:111-126`), so
nothing was hidden; the number just never propagated to the page.

**R8 — `needs: []` on both new CI jobs is a no-op.** *(minor)* `.github/workflows/ci.yml`, jobs
`pypi-sequencing` and `tutorials`. Valid YAML and harmless, but it reads as though a dependency
was intended and got emptied. Drop the key.

**R9 — `main(argv)`'s dead parameter.** *(minor)* `scripts/check_pypi_sequencing.py:115-122`
takes `argv` and immediately `del argv`s it with a comment saying it is "present for a
conventional `main()` signature". Nothing calls it with arguments. Fine, but it is noise in a
70-line stdlib script.

**R10 — `publish.yml`'s version check uses more machinery than it needs.** *(minor)*
`.github/workflows/publish.yml:39-40` shells
`uv run --no-project --python 3.12 python -c 'import tomllib; ...'` where `python3 -c` would do
— `tomllib` is stdlib from 3.11 and ubuntu-latest ships ≥3.12. Every extra moving part in the
release-critical path is one more thing that can fail on the one day it runs.

**Verdict: FLAG** — solely on R7, which is the only readability issue that reaches a reader.
R8–R10 are nits.

---

## 3. Architecture — **FLAG**

### 3a. Closure check: user input → new code → was it reached?

| # | New primitive | User input | Callsite in the repo | Step-5 readback reached it? |
|---|---|---|---|---|
| 1 | `scripts/check_pypi_sequencing.py` | `docs/getting-started.md` text + git tag state | `ci.yml` job `pypi-sequencing`; `tests/unit/test_pypi_sequencing_guard.py` | **Yes** — T1 re-ran both (20 passed; script printed its OK readback) |
| 2 | `nbmake` execution | the four `.ipynb` | `ci.yml` job `tutorials` | **Yes** — T2 re-ran `pytest --nbmake docs/tutorials/*.ipynb` (4 passed) |
| 3 | `mkdocs-jupyter` plugin block | the four `.ipynb` + `include: ["tutorials/*.ipynb"]` | `mkdocs build` | **Yes** — real solver numbers grepped out of the built HTML (`AC active losses: 13.393 MW`) |
| 4 | `mkdocs.yml` `Tutorials:` nav | — | the built site | **Yes** — AC-2 nav readback + exhaustive `docs/**` → nav coverage check |
| 5 | `.github/workflows/publish.yml` | a pushed `v*` tag | GitHub Actions | **Never executed** — correctly named `blocked` under A16/AC-5; static half confirmed. Not a dead callsite, but an unexercised one, and R11 is the consequence |
| 6 | `[tool.semantic_release]` | commit messages | **none** | Dry-run only, in a disposable clone (`record/m9-ac4-dryrun.md`) |

Rows 1–4 close cleanly: real input reaches real code and the readback exercised the actual
callsite, not a stand-in. Row 5 is honestly blocked. **Row 6 does not close**, and that is this
review's central finding.

**R11 — the release chain has three pieces and no callsite joining them. *(most important
finding)*** *(major)*

The three pieces:

1. `[tool.semantic_release]` (`pyproject.toml:92-131`), which owns `project.version` via
   `version_toml` and owns the changelog insertion.
2. `pyproject.toml:7` — `version = "0.0.1.dev0"`.
3. `publish.yml:31-46` — a version-consistency gate that fails the `build` job unless the pushed
   tag's version equals `pyproject.toml`'s.

Nothing in the repository invokes semantic-release. No workflow runs it. `contributing.md:127-129`
mentions that "semantic-release will derive versions and the changelog from them at 0.1.0" but
never says how to run it. There is no `Makefile`, no `justfile`, no `scripts/release.*`. The only
place a human is told the actual procedure is a **bullet inside a changelog entry**
(`docs/changelog.md:58-65`) carrying the two operational traps S5 discovered — the Windows
`PYTHONUTF8=1` requirement and the `semantic-release changelog` non-idempotence. A changelog is
history; nobody consults it as a runbook. S5's report asked explicitly for those notes to land
"in whatever CONTRIBUTING/W7 documentation gets written" (`m9-s5-report.md:198-199`); S7 put them
in the changelog instead, and no slice owned the gap.

The audit's **F-A8** — `pyproject.toml` reads `0.0.1.dev0`, no tags exist, so pushing `v0.1.0`
fails `publish.yml`'s own gate and nothing publishes — is not an isolated oversight. It is the
predictable result of a chain with no owner and no callsite: three pieces each individually
correct and verified, wired to nothing, and inconsistent with each other by construction. It was
found by an auditor reading the tree, not by anything in the repo, and it lives today only in a
`.bionic/` plan file that does not ship.

The spec's component-boundary table has a row for `publish.yml` and a row for `changelog.md`, but
no row for *cutting a release* — so no slice owned it and no criterion covered it.

**Recommendation (this is the single highest-value change available):** add one
`## Cutting a release` section to `docs/contributing.md` — or better, `scripts/release.sh`, which
gets a callsite and a home in the repo — naming, in order: bump `pyproject.toml` to the target
version; run `semantic-release version` from `epic/01-foundation` (`PYTHONUTF8=1` on Windows);
push the tag; approve the `pypi` environment. That single artifact closes F-A8, gives
`[tool.semantic_release]` its missing callsite, moves the Step-9 checklist from a plan file into
the repo, and gives R12 somewhere to be recorded.

**R12 — `branches.main.match = "epic/01-foundation"` is a dated time bomb.** *(minor)*
`pyproject.toml:105-107`. Correct today, and the comment discloses it honestly ("until the epic
itself merges to `main` … this is the only branch that should ever compute a version"). But when
the epic does merge, semantic-release will silently refuse to release from `main` — the branch
it will then be released from. Nothing enforces or reminds. One line in the release runbook R11
asks for.

**Fit against the component-boundary table.** Otherwise good. `docs/tutorials/` genuinely owns
only the notebooks and imports only the public package (`git diff --stat -- . ':!docs/tutorials'`
was empty for S1). `mkdocs.yml` owns the nav change and `Manual`'s 12 entries do not appear in
the diff at all. `publish.yml` crosses out to PyPI and in from a tag, exactly as drawn. No slice
reached outside its row.

**Verdict: FLAG** — five of six new primitives close cleanly; the release chain does not, and
that is where the wave's next gate lands.

---

## 4. Security — **FLAG**

**What holds — and this is the strongest-built surface in the wave.**

- Trigger is exactly `on: push: tags: ["v*"]`. No `branches:`, no `pull_request:`, no
  `workflow_dispatch:`. S6 dropped the optional manual-dispatch escape hatch rather than gate it
  — the safer reading, and the right call.
- Workflow-level `permissions: contents: read`. `id-token: write` appears **only** on the
  `publish` job. The `build` job inherits read-only.
- No `password:` / `api-token:` input on `pypa/gh-action-pypi-publish` — that absence is what
  selects OIDC mode, and the comment says so. No token, secret, or credential anywhere in the
  diff.
- The job-level `permissions:` block on `publish` replaces the workflow default entirely,
  leaving it with `id-token: write` alone — and that is **correct**, not a bug:
  `actions/download-artifact@v4` uses the Actions runtime token for same-run artifacts, not
  `GITHUB_TOKEN`, so no `actions: read` is needed, and the job never checks out code.
- Splitting `build` from `publish` puts the `pypi` environment's approval gate between building
  and publishing — the PyPA-recommended shape, and the one that makes a required-reviewer rule
  meaningful.
- Notebooks: no secret, no absolute local path, no base64 blob, no `kernelspec` block (so no
  leaked interpreter path or username), no network access. Data loads are repo-relative
  (`"../../fixtures/matpower/case14.m"`).

**R13 — every action in the publish workflow is pinned by mutable tag, not commit SHA.**
*(moderate — the one real security finding)*

`.github/workflows/publish.yml`: `actions/checkout@v4`, `astral-sh/setup-uv@v5`,
`actions/upload-artifact@v4`, `actions/download-artifact@v4`,
`pypa/gh-action-pypi-publish@v1.14.2`. Tags are mutable refs. This is house style — `ci.yml`
does the same at seven callsites — and is defensible there, because `ci.yml` holds nothing worth
stealing.

`publish.yml` is different in kind: it is the **only** workflow in the repo holding
`id-token: write` and the authority to publish under this project's PyPI name. A moved or
compromised tag on any of these five actions puts attacker-controlled code inside the job that
mints the PyPI upload credential, and the trusted-publishing model has no second factor behind
it. `astral-sh/setup-uv@v5` is a floating major-version tag — the loosest of the five —
and it runs in the `build` job that produces the artifact `publish` uploads verbatim.

SHA-pin at minimum `pypa/gh-action-pypi-publish` and `astral-sh/setup-uv`, with the version in a
trailing comment. (Context worth preserving: S6 caught itself fabricating a SHA and corrected to
a verified tag — the honest call in the moment. The fix is to look the real SHAs up, not to stay
on tags.)

**R14 — `v*` is broader than the release-tag shape anything else uses.** *(minor)*
The trigger fires on `vfoo` or `v-anything`; the version-consistency step then rejects it with a
clear `::error::`, so the practical exposure is a wasted job rather than a bad publish. Worth
naming because it is a *third* in-repo definition of "a release tag", alongside the guard's
`_is_release_tag` (`v\d+\.\d+\.\d+`, ≥0.1.0, prerelease-permissive — R3) and
`[tool.semantic_release] tag_format = "v{version}"`. See R16.

**Verdict: FLAG.** Nothing leaks or grants anything today; the OIDC design is right. R13 is a
supply-chain hardening gap that matters specifically because of which job it is in.

---

## 5. Performance — **PASS**

This wave is docs and packaging, and the honest answer is that there is almost nothing here to
optimise. Saying so rather than manufacturing a finding:

- **Notebooks are cheap.** `case14` (14 buses, 20 branches) and hand-built 2-bus toys. The
  heaviest single call — `market.agents.solve_agents`'s 84-round best-response loop in notebook
  04 — measures **0.16 s** outside a kernel. Full `nbconvert --execute` wall time is 5.6–9.1 s
  per notebook, dominated by IPython kernel startup, not solver work. No loop, case size, or
  solver call is gratuitous.
- **`execute: false` on `mkdocs-jupyter` is the right call**, and for the right reason: it keeps
  notebook execution in exactly one place (nbmake, in CI) rather than duplicating it into every
  docs build. Docs build stays ~60–85 s, unchanged in character.
- **The `pypi-sequencing` job is deliberately lean** — stdlib-only, no `uv sync`, no project
  install, a few seconds. This is good design and the job comment explains it.
- **One leg, not five, for the tutorials job** — correctly reasoned in the job comment.

**R15 — `ci.yml`'s `tutorials` job over-syncs.** *(minor; the only real perf note)*
`uv run ... uv sync --locked --all-groups` installs **every** dependency group to run four
notebooks. I checked the notebooks' actual imports: `mambo_power{,.io,.model,.market.agents}` and
`numpy`, nothing else. So `--all-groups` pulls in pandapower and PyPSA (the two heaviest
installs in the project, needed by neither) and `python-semantic-release` from the new `release`
group, which no notebook could possibly need. `--group dev` (which carries `nbmake`) or a narrow
`notebooks` group would cut the heaviest install in the wave's new CI surface. Not urgent — it is
one leg and `enable-cache: true` is set — but it is the single place this wave spends CI time it
does not need, and the `release` group only became reachable *because* this wave added it.

**Verdict: PASS.**

---

## 6. Duplication — **FLAG**

Anchored on the spec's ownership table, one row at a time.

### Row 1 — "is this released yet" (SSoT: a `v0.1.0`+ git tag)

The design names **three** rendering surfaces. The tree has **five**, and one agreement test:

| # | Surface | Guarded? |
|---|---|---|
| 1 | `docs/getting-started.md:9` install block | **yes** — `check_pypi_sequencing.py`, CI job `pypi-sequencing` |
| 2 | `docs/index.md:37` "Nothing is on PyPI yet" | no |
| 3 | `docs/changelog.md:5-6` "Nothing has been released yet" | no — and was actively self-contradictory until `d5724cb` (F-A7) |
| 4 | **`pyproject.toml:7` `version = "0.0.1.dev0"`** | no — and this is the one `publish.yml`'s gate actually enforces |
| 5 | **the definition of "a release tag" itself** — `publish.yml`'s `v*`, the guard's `_is_release_tag`, and `tag_format = "v{version}"`: three definitions, mutually inconsistent (R3, R14) | no |

**R16 — one guard covers one of five surfaces, and the two that would actually stop a bad
release are the two with no test at all.** *(major; confirms and extends F-A7 and F-A9)*

Surfaces 4 and 5 are not in the design's table because this wave *created* them and the table
was not revisited. F-A8 is precisely the disagreement between surface 4 and the SSoT; R3 is
precisely the disagreement inside surface 5. Both were found by reading, not by a test, which is
the definition of an unguarded shared truth.

Extending the existing guard is cheap and hermetic — it already parses tags and reads a doc
file. Three additions, in one script, in one CI job that already exists:

1. when a release tag is reachable, assert `pyproject.toml`'s `[project].version` equals it
   (**closes F-A8 permanently**, in the repo, rather than as a checklist line in a plan file);
2. when a release tag is reachable, assert `docs/index.md`'s and `docs/changelog.md`'s
   pre-release sentences are gone (**would have caught F-A7 before it shipped**);
3. share one release-tag predicate between the guard and `publish.yml`'s trigger comment, and
   make it reject prereleases (**closes R3**).

That is the highest-leverage duplication fix available and it is perhaps thirty lines.

### Row 2 — "the wave's own completion state" (SSoT: `epic.plan.md`'s M9 roadmap row)

The design deferred this one: *"a docs test comparing the two, if one doesn't already exist —
implementor checks."* No slice recorded the check and no test exists — the audit's **F-A6**,
carried forward as an open item.

**I recommend closing F-A6 rather than carrying it, because the wave already solved half of it
by design.** `docs/changelog.md:15-17` now explicitly *refuses* to restate merge status and
defers to the roadmap table:

> "Which waves have merged to `epic/01-foundation` and which are still on their own branch is
> tracked in [the home page's roadmap table](index.md), not restated here, so this page cannot
> go stale about it."

That collapses two rendering surfaces into one — a better fix than an agreement test, because it
removes the disagreement rather than detecting it. The residual pair is `epic.plan.md`'s roadmap
row versus `docs/index.md`'s table, and `epic.plan.md` is a `.bionic/` planning artifact that
does not ship; a hermetic test spanning that boundary would couple the shipped package's test
suite to the SDLC's own bookkeeping, which is worse than the drift it prevents. **Record F-A6 as
resolved-by-design-change with the residual pair explicitly declined**, rather than leaving it as
an unresolved "implementor never checked" in the continuation record.

### Row 3 — "what conventional-commit type bumps what" (SSoT: PSR's own config)

**Satisfied.** AC-4's fixtures have a durable transcript (`record/m9-ac4-dryrun.md`). Noted
without a finding: the bump table is *also* restated in prose at `docs/changelog.md:52-53` and
`docs/contributing.md:127-129` — two more unguarded renderings of the same truth. They agree
today and the stakes are low, but it is the same pattern as Row 1, one order of magnitude down.

### Notebook ↔ examples overlap

- `03-nodal-market.ipynb` cell 2 duplicates ~50 lines of `examples/09_nodal_market.py:33-80`
  near byte-for-byte (ids, values, `PiecewiseBid` points, even inline comments) while crediting
  *the manual page* as its source. **Worth fixing** — not for the duplication, which is
  structurally inherent to "self-contained narrative" tutorials, but because the miscredit sends
  a maintainer to the wrong file when the two drift.
- `02-dc-opf-and-n1.ipynb` cell 7 duplicates `examples/08_opf_and_n1.py:70-74` and says so
  honestly. Fine.
- `04-where-next.ipynb` cells 2 and 5 overlap `examples/12_agent_market.py` and
  `examples/13_interop.py` in scenario design and print structure.

All of it executes in CI on both sides, so drift breaks loudly rather than silently. Acceptable;
the miscredit is the only part worth a change.

**Verdict: FLAG.**

---

## 7. Summary

| Axis | Verdict | Driver |
|---|---|---|
| Correctness | **FLAG** | Three shipped doc surfaces state what the code does not do (R1, R2, R6); the guard's durability clause is not met (R3, R4, R5). No functional defect. |
| Readability | **FLAG** | R7 — the Tutorials landing page overstates reading time ~4–5×. Comments and structure otherwise well above average. |
| Architecture | **FLAG** | R11 — five of six new primitives close user-input → code → readback; the release chain has no callsite and no runbook. |
| Security | **FLAG** | R13 — mutable tag pins in the one workflow holding `id-token: write`. OIDC design itself is correct throughout. |
| Performance | **PASS** | Genuinely low-stakes wave. R15 (`--all-groups` over-sync) is the only note. |
| Duplication | **FLAG** | R16 — the released-state SSoT has five rendering surfaces and one guard; the two unguarded ones are exactly F-A8 and R3. |

**Single most important finding: R11** — the release chain (`[tool.semantic_release]` →
`pyproject.toml`'s version → `publish.yml`'s consistency gate) has three individually-verified
pieces, no code path joining them, and no runbook naming the procedure. F-A8 — pushing `v0.1.0`
against the current tree fails the workflow's own gate and publishes nothing — is a symptom of
that gap, not a separate oversight, and it lives today only in a plan file that does not ship.
Step 9 is the next gate and it is the gate this finding lands on. One `## Cutting a release`
section (or `scripts/release.sh`) closes F-A8, gives the semantic-release config its missing
callsite, and gives R12 and R16's checklist items a home in the repo.

**Blocking vs. not.** Nothing here blocks the Step-8 merge: no functional defect, no leak, and
every AC's substance survived the audit's falsification attempts and mine. **R11 and R16(1)
should land before Step 9**, because Step 9 is where they bite. R1, R2 and R7 are three one-line
doc corrections and should land with the wave — all three are reader-visible false statements in
shipped pages, which is the same class as F-A7, already fixed once this wave.

**Note on the dirty tree (§0):** the in-flight C5 bidirectional fix is a genuine improvement to
the guard, but it should not land without R3's prerelease fix in the same change — it converts a
permissive prerelease bug into one that turns CI red and pressures a maintainer into writing a
false PyPI claim.
