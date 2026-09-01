# M9 walk — docs site, tutorials, changelog, publish workflow

## Where I looked, and how

Worktree: `C:/Claude Projects/mambo-power-m9`, branch `wave/09-release-0.1`, head `a221482`
("style(m9-s7): ruff-clean the four tutorial notebooks"). I did not read anything under
`.bionic/docs/specs/` or `.bionic/docs/plans/`. Everything below is what I actually ran or read,
in the worktree, this session.

## 1. Building the docs site

```text
$ uv run mkdocs build --strict
...
INFO    -  Cleaning site directory
INFO    -  Building documentation to directory: C:\Claude Projects\mambo-power-m9\site
INFO    -  pydantic_fields: pydantic_fields: documented 249 field(s) in mambo_power
INFO    -  Cache hit: C:\Claude Projects\mambo-power-m9\docs\tutorials\01-first-power-flow.ipynb
INFO    -  Cache hit: C:\Claude Projects\mambo-power-m9\docs\tutorials\02-dc-opf-and-n1.ipynb
INFO    -  Cache hit: C:\Claude Projects\mambo-power-m9\docs\tutorials\03-nodal-market.ipynb
INFO    -  Cache hit: C:\Claude Projects\mambo-power-m9\docs\tutorials\04-where-next.ipynb
INFO    -  Documentation built in 85.56 seconds
```

Exit clean, no errors in `--strict` mode. The one thing printed before the build starts is a
boxed notice from the Material for MkDocs team about breaking changes coming in MkDocs 2.0 (not
this project's own warning — it's the theme package nagging about its own future). The four
tutorial notebooks are "cache hit" rather than freshly rendered — `mkdocs-jupyter` is configured
with `execute: false`, so the build embeds whatever outputs are already stored in the `.ipynb`
files rather than re-running the solver code. That's a real thing to notice as a reader of the
built site: what you see on the tutorial pages is exactly what's committed in the notebook files,
not something mkdocs computed at build time.

I then read the generated HTML directly (stripped of markup, since no browser tool connected in
this session — chrome-devtools MCP timed out) at `site/index.html`,
`site/tutorials/index.html`, and each `site/tutorials/0{1,2,3,4}-*/index.html`, and separately
read the corresponding `docs/*.md` / `docs/tutorials/*.ipynb` sources to sanity-check what the
build did with them.

## 2. The home page (`docs/index.md` / `site/index.html`)

Opens with a two-sentence description of what the package is (fundamental power-system analysis
and market modelling, its own model and solvers on numpy/scipy/HiGHS), then a runnable four-line
DC power-flow snippet, then a "Status" admonition that narrates the whole roadmap wave by wave —
M1 through M9, each with one or two sentences on what it added and a link into the manual. It
ends on M9 in the present tense: "closed the epic — narrative tutorials, an automated changelog
and the PyPI trusted-publishing pipeline. Nothing is on PyPI yet — install from source." That
last clause is doing real work: a reader who skims only the bold wave labels could come away
thinking the package is pip-installable, and this sentence heads that off explicitly, twice
(once in prose, once as a link to Getting started).

Below that: three numbered principles ("own model, own solvers"; "free in both senses"; "a
foundation for a service, not a notebook toolbox"), a mermaid system-context diagram (inputs →
package internals → consumers), a "where to go next" table with one row per manual page — a
`Tutorials` row sits between "Follow a guided walkthrough" and the manual rows, pointing at
`tutorials/index.md` — and a roadmap table listing all nine waves as `merged`, M9's scope given
as "Tutorials, semantic-release changelog, PyPI 0.1.0 trusted publishing."

The status prose and the roadmap table agree with each other and with what I actually found on
disk (four tutorial notebooks, a changelog with a semantic-release marker, a publish workflow) —
nothing in this page overclaims relative to what I could independently verify by opening those
files myself.

## 3. Tutorials nav and the four notebook pages

The nav (from `mkdocs.yml`) puts `Tutorials` as its own top-level section between `Getting
started` and `Manual`, with five entries: the tutorials index page plus the four notebooks,
numbered "1. Your first power flow" through "4. Where next." `docs/tutorials/index.md` frames
them as "prose-heavy... rather than the terse one-concept-per-script style of the examples," with
a difficulty-tiered table (Beginner, Intermediate, Intermediate, Guided fork) and an explicit "the
arc" section laying out the four progressively-harder questions each one answers: what's
happening now, what should happen, what happens when participants bid, where do you go from
here. It also states, as a claim a reader can go verify: "Every code cell in every notebook
actually runs — they're executed fresh in CI on every push (nbmake), so the numbers you see
rendered here are the real ones, not hand-typed illustrations." I independently checked this
claim in §4 below rather than taking it on faith.

**Tutorial 1 — Your first power flow.** Loads IEEE case14 via `matpower.load`, prints
`14 buses, 20 branches, 5 generators, 11 loads`, shows one bus and one branch's repr, then walks
DC vs. AC power flow side by side: `pf.solve_dc` converges, prints per-bus angle/power for the
first three buses; `pf.solve_ac` converges in 4 iterations, prints voltage magnitude/angle/
reactive power for the same three buses; a follow-up cell sums branch losses and prints
`AC active losses: 13.393 MW` next to "DC model has no losses by construction." The prose
between cells explains *why* DC and AC differ (flat 1.0 pu assumption, ignored resistance) before
showing the numbers, so the numbers read as illustrating a point already made rather than an
unexplained printout. Ends with a "Try it yourself" note pointing at five more bundled MATPOWER
cases, explicitly left unexecuted ("so this tutorial's own output stays fixture-independent and
reproducible"), and a "Next" link into tutorial 2.

**Tutorial 2 — DC-OPF and N-1 screening.** Picks up the same case14, runs `opf.solve_dc_opf`
(`status: Optimal cost: 7642.59 $/h`, dispatch table showing three of five generators pinned at
zero), then locational marginal prices — and is upfront that case14's bundled ratings are all
zero ("MATPOWER's 'unlimited' convention"), so every bus's LMP comes out identical
(`39.016` everywhere) with zero congestion component; it says the manual page shows a congested
example instead of pretending this one is. To make N-1 screening non-trivial it derives a
synthetic rating per branch at 20% headroom over that branch's own base-case flow, states plainly
that this is "a documented transformation of data the fixture already owns, not new data, and the
same one this package's own example script and test suite use," then runs `contingency.n1` and
prints `18 outages flagged, out of 19 screenable branches (1 bridge branch skipped: its outage
would island the network)`. It walks the first flagged outage in detail (`branch-1` tripping
pushes `branch-2` on the same corridor from 219.00 MW estimated to 219.00 MW confirmed, past its
85.39 MVA synthetic rating) and states that the LODF-based screen and the confirming DC re-solve
agree to five decimal places, which is not a coincidence but a proven guarantee.

**Tutorial 3 — A nodal market.** Builds a small two-bus network by hand (a $10/MWh and a
$50/MWh linear generator, one fixed load, one load with a two-segment piecewise bid, one branch
rated tightly at 20 MVA so it can actually bind) and explains `Scenario` as the wrapper
`market.solve_nodal` needs, distinguishing a generator's `cost` from a load's `bid` as mirror-
image curves (cost of producing more vs. value of consuming more). This is a smaller, hand-built
example rather than case14 — deliberately, so the branch limit actually binds and there's an LMP
split worth narrating (case14 as shipped has none, as tutorial 2 already told the reader).

**Tutorial 4 — Where next.** Explicitly framed as a fork, not a continuation: strategic bidding
(`market.agents.solve_agents`) on one side, interchange formats (`io.*`) on the other, "pick
whichever matches what you're actually trying to do, or read both; they're independent." The
bidding half again builds a network by hand (a 900 MW generator, $20/MWh true cost, `MarkupStrategy`
hill-climbing its own offer against a downward-sloping demand curve) because `MarkupStrategy`
needs a linear cost curve and none of the bundled MATPOWER fixtures have one — stated directly
rather than left for the reader to wonder about.

Across all four: every markdown explanation appears *before* the code cell it explains, every
printed number is followed by a sentence interpreting it, and the four notebooks reference each
other by name and link at the boundaries ("tutorial 2 picks up exactly here," "Tutorial 1 —
Your first power flow" at the top of Tutorial 2). Nothing in the rendered HTML looked stale,
truncated, or mismatched between the markdown narration and the printed output next to it.

## 4. Actually executing a tutorial notebook fresh

```text
$ uv run jupyter nbconvert --to notebook --execute --stdout docs/tutorials/01-first-power-flow.ipynb \
    > .../scratchpad/exec_out.json 2> .../scratchpad/exec_err.log
$ echo EXIT=$?
EXIT=0
```

stderr contained only benign platform noise — a `RuntimeWarning` about the Windows Proactor event
loop and pyzmq's async support, and an `IPKernelApp` warning that the local kernel is running
unencrypted over TCP (expected for a local dev-machine kernel, not a real security concern here).
No exception, no failed cell, no non-zero exit.

I then diffed the freshly-executed notebook's cell outputs against the committed
`docs/tutorials/01-first-power-flow.ipynb` outputs programmatically. Five of six code cells
matched byte-for-byte. The sixth (the `pf.solve_ac` cell) differed only in how stdout was
chunked across streaming-output records — the committed notebook has one `stream` output with
`AC converged: True  iterations: 4\n...`; my fresh run split the same text into two `stream`
records at `AC converged:` / ` True  iterations: 4\n...` — a buffering/flush artifact of how
ipykernel batches stdout, not a content difference. Concatenated, the text is identical, and every
number in it (`iterations: 4`, `vm=1.0450`, `va=-4.983`, `q=30.86`, etc.) matches the committed
notebook and the built HTML page exactly. So: the tutorial's claim that "every code cell actually
runs" and that the displayed numbers are the real ones held up under a fresh, independent
re-execution — the DC-OPF/N-1 numbers I quote above in §3 for tutorial 2 (`cost: 7642.59 $/h`,
`39.016 $/MWh`, `18 outages flagged... 1 bridge branch skipped`) are what's rendered in the built
site and match what's stored in the notebook file, though I only re-executed tutorial 1 myself
this session, not 2–4.

## 5. `docs/getting-started.md`

Reads as a five-minute, top-to-bottom script: install with `uv sync` (or plain `pip install -e .`
without uv), a "What gets installed" note that the wheel carries only the package and its
`py.typed` marker — the MATPOWER fixtures and test suite are sdist/repo-only, so the page's own
later examples explicitly assume you're inside a clone. Then: load case14, print entity counts,
print one bus and branch repr, then a validation section that deliberately constructs an invalid
network (`Bus(base_kv=0)`, a dangling branch reference, no slack) and prints all four resulting
issues at once — `BAD_BASE`, `DANGLING_REF`, `NO_SLACK`, `DISCONNECTED_BUS` — with the stated
point that validation reports every problem in one pass rather than one at a time. Then DC power
flow, reading results, round-tripping through JSON, then AC power flow, then building a two-bus
network from scratch with no file at all. It closes with a "Next steps" list into the manual.

The install section is explicit and unambiguous about current PyPI status: "mambo-power is not
on PyPI yet (that is wave M9, version 0.1.0). Until then, install from source with uv" — matching
what the home page's Status admonition says, and matching what I could see for myself: there is
no live PyPI listing to check against from here, but the page never tells the reader to `pip
install mambo-power` as things stand.

## 6. `.github/workflows/publish.yml`

Plain-language read of the YAML, as a colleague seeing it for the first time:

- **Trigger.** `on: push: tags: ["v*"]` — nothing else. No branch-push trigger, no
  `pull_request`, no `workflow_dispatch` manual button. So the only way this workflow starts
  running at all is a human (or another automation) pushing a tag whose name starts with `v` —
  ordinary commits and PRs never touch it. A comment right above the trigger says this is
  deliberate: a manual-dispatch escape hatch was considered and left out on purpose, so the only
  way to fire this is the literal act of pushing a release tag.
- **Job 1, `build`.** Runs on `ubuntu-latest`, sets up `uv` and Python 3.12, then — before
  building anything — extracts the version number from the pushed tag name (stripping the leading
  `v`) and compares it against the `version` field in `pyproject.toml`; if they don't match it
  fails the job with an explicit error rather than silently building whatever `pyproject.toml`
  happens to say. Only after that check passes does it run `uv build` and upload the resulting
  `dist/` (wheel + sdist) as a workflow artifact, kept for 7 days.
- **Job 2, `publish`.** Depends on `build` finishing successfully, downloads that same `dist/`
  artifact, and runs `pypa/gh-action-pypi-publish` pinned to a specific release tag of that
  action. It declares `permissions: id-token: write` and nothing else, with a comment explaining
  that's the entire trust mechanism: no PyPI token or password appears anywhere in the file or (as
  far as this file shows) in repo secrets — the job exchanges a short-lived GitHub OIDC token for
  a scoped PyPI credential at publish time. The job also declares
  `environment: {name: pypi, url: https://pypi.org/p/mambo-power}` — a GitHub "environment," which
  is where a required-reviewer rule configured in repo settings (not in this file) would act as a
  manual approval gate between the build finishing and the actual publish happening. The file
  itself doesn't and can't prove that protection rule exists in the actual repo settings — a
  comment says as much — it only shows the workflow is *structured* to be gated by one if it's
  configured.

I did not and could not run this — it needs a real `v*` tag push and live PyPI trusted-publishing
credentials, neither of which apply to a worktree walk.

## 7. `docs/changelog.md`, top portion

Opens with a short, standard preamble (Keep a Changelog format, semantic versioning, "nothing has
been released yet; the first release will be 0.1.0 on PyPI") and a `<!-- version list -->` marker
comment, then a `## Released` heading whose own text tells the reader what that heading means and
will keep meaning: everything below it, right now, is nine hand-written per-wave sections (M1
through M9) written before any automated tool existed; going forward, an automated changelog tool
will insert new sections *above* that marker as real releases happen, so this file explains its
own structure to a reader rather than assuming they already know the convention.

The M9 section itself is the longest, itemizing: the four tutorial notebooks and what each
covers; a new CI job that runs them fresh via `nbmake` on every push (kept off the main OS/Python
test matrix, with a stated reason — solver-heavy, and running the same four notebooks five times
would burn CI minutes for no extra coverage); `mkdocs-jupyter` rendering them into the nav
(explicitly noting the site build does *not* re-execute them, `nbmake` in CI already did — which
is exactly what I confirmed in §1 and §4 above); the home-page and roadmap updates; a PyPI-
sequencing guard script that fails CI if the "not on PyPI yet" text and a real `v0.1.0`+ tag are
ever inconsistent with each other; the `python-semantic-release` configuration and two fairly
specific operational footnotes for whoever actually runs a release (a Windows `PYTHONUTF8=1`
environment-variable requirement, and a warning that the `changelog` subcommand is not idempotent
on its own — always go through `version`, which tags and moves the insertion point together); and
the publish workflow itself, described in essentially the same terms I read directly from the
YAML in §6.

Below the M9 section is a shorter dated entry, "Fixed — case30 redispatch/zonal dual degeneracy
in CI," describing a test flakiness root-caused to a genuinely degenerate LP (a zero-injection
radial node making two branches' sensitivity rows exactly redundant, so the solver has legitimate
freedom in which one it assigns the shadow price to, and that choice is platform-sensitive) and
fixed by changing the test's comparison method rather than loosening a tolerance — with a pointer
to a design-decision record for anyone who wants the full reasoning.

## Surprises / things nobody asked about

- **Tutorial 2's N-1 screen flags nearly every branch.** `18 outages flagged, out of 19
  screenable branches` reads, at a glance, like almost the whole network is unsafe — worth a
  second look even though the tutorial's own explanation (a synthetic rating set at only 20%
  headroom above each branch's *own* base-case flow, not a real engineering margin) fully accounts
  for it: with that little slack, almost any redistribution from a single outage pushes some
  branch over its synthetic limit. The tutorial does explain this, but a reader skimming just the
  printed number before reading the explanation could reasonably read it as "the network is
  broken."
- **mkdocs 2.0 deprecation notice.** The `mkdocs build` run prints an unrelated boxed warning from
  the Material for MkDocs maintainers about MkDocs 2.0 removing the plugin system entirely, with
  no migration path — this project uses two plugins (`mkdocs-jupyter`, `mkdocstrings`) that this
  notice says would stop working outright on that future version. Not this wave's problem, but
  it's the kind of thing that will eventually force a real decision.
- **The publish workflow's `pypi` GitHub environment is aspirational from the file's own point of
  view.** The YAML explicitly documents that it doesn't need to exist yet in repo settings for the
  file to be valid — meaning a reader of just this file cannot tell whether the manual-approval
  gate it describes is actually wired up in the live repository, only that the workflow is written
  so that it *would* be gated if that environment protection rule is configured.
- **Stream-output chunking is nondeterministic across notebook executions.** My fresh execution of
  tutorial 1 split one cell's stdout into two `stream` JSON records where the committed notebook
  has one; the text is identical either way. Harmless, but worth knowing if anyone ever diffs
  notebook outputs byte-for-byte as a CI check — a naive diff would flag this as a change when
  nothing observable actually changed.
- **A source comment in the publish workflow cites a specific pinned release date/version for the
  third-party publish action** ("checked at implementation time via the action's GitHub releases
  page") — a small, honest provenance note that a reader could use to judge how stale the pin
  might be by the time this actually runs.
- Several source comments in the workflow YAML and the changelog's "Fixed" section reference
  short internal tags in the shape of a letter, a hyphen, and a digit (e.g. next to the trigger
  condition, and next to the version-consistency check) — clearly pointers into this wave's own
  planning documents. I did not resolve what they point to, since I was deliberately kept away
  from the spec and plan for this walk; a reader without that context would see the same bare tags
  I did.
