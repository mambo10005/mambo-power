# M3 S7 report — docs: opf/n1 manual + API pages, architecture diagram, example

Slice S7 of wave M3 (opf-n1), the last slice: `docs/manual/opf.md`, `docs/manual/n1.md`,
`docs/api/opf.md`, `docs/api/contingency.md`, `mkdocs.yml` nav, `docs/design/architecture.md`'s
import-graph diagram, `examples/08_opf_and_n1.py`, and a stale `docs/manual/jobs.md` fix left by
S6. AC-9. Commit `f37815a` on `wave/03-opf-n1` (pushed).

## What was built

- **`docs/manual/opf.md`** — DC-OPF formulation (nodal-balance row, PTDF flow-limit rows,
  LP-vs-QP cost handling), the convex segment/epigraph PWL encoding and its convexity
  requirement, duals and `lmp_decomposition`, the `ac_check` AC-feasibility option, and a
  dedicated section on the PTDF-vs-theta slack-generator formulation caveat S2 found (when
  `opf.dc_opf` and pandapower `rundcopp` are and aren't guaranteed to agree).
- **`docs/manual/n1.md`** — the screen-then-confirm pipeline (LODF estimate, then a confirming
  DC re-solve), the deliberate `contingency.n1` module/function name collision, rating data
  (no bundled fixture ships one), the brute-force agreement guarantee with the measured
  per-fixture counts, and branch-outages-only scope with generator outages named as a
  carry-over, not silently dropped.
- **`docs/api/opf.md`, `docs/api/contingency.md`** — mkdocstrings pages following
  `docs/api/pf.md`'s exact pattern: a package-level `::: mambo_power.opf` /
  `::: mambo_power.contingency` block (`show_submodules: false`) plus a submodule block
  (`opf.dc_opf`, `contingency.n1`) — necessary, not decorative (see below).
- **`mkdocs.yml`** — nav entries for the two new manual pages (between Power flow and Results)
  and the two new API pages (between pf and results).
- **`docs/design/architecture.md`** — the mermaid import-graph diagram, corrected against the
  actual `from mambo_power...`/`import mambo_power` lines in `opf/__init__.py`,
  `opf/dc_opf.py`, `contingency/__init__.py`, `contingency/n1.py`, and (because it also changed)
  `jobs/registry.py`. Moved `opf`/`contingency` from the placeholder "Later waves" group into
  "Shipped", replaced the two guessed dotted edges (`opf -.-> numerics`, `n1 -.-> pf`) with the
  real, complete, solid set (`opf`/`contingency` each import `model`, `numerics`, `pf`, and
  `results`), and added `jobs --> opf` / `jobs --> contingency` — edges the diagram never had at
  all, since S6 (jobs) landed after the diagram was last touched. Also fixed one stale
  ownership-table line (see below) and added the two new package directories to "Module map on
  disk", which had drifted the same way.
- **`examples/08_opf_and_n1.py`** — `solve_dc_opf` dispatch/duals/LMP on case14 with
  `ac_check=True`, a tightened branch rating that forces the OPF's own dispatch off it (nonzero
  flow-limit dual, LMP splitting into energy + congestion), and `contingency.n1` on a
  ratings-derived copy of the same network, showing one outage's LODF-screened estimate next to
  its DC-re-solve-confirmed flow. Registered in `docs/examples/index.md`'s table and snippet
  embed; `tests/unit/test_examples_run.py` picked it up with no edit needed (directory glob).
- **`docs/manual/jobs.md`** — fixed the stale `kind="opf.dc"` "unknown kind" demonstration
  (line 200/217, left by S6) to `kind="market.nodal"`, matching S6's own fix to
  `examples/04_jobs_api.py`; verified the exact replacement output text by running the block
  live rather than hand-computing it.

## A finding: `test_api_docs_coverage.py`'s `PACKAGES` is not generic

The dispatch brief framed this test as walking packages "generically," so that the new API
pages alone should make it pass "without modification." Reading the test file directly showed
that is only half true: `pkgutil.iter_modules` genuinely walks *within* a package generically,
but *which* top-level packages get walked at all is `PACKAGES = ("model", "io", "numerics",
"pf", "results", "jobs")` — a hand-maintained literal tuple that had never been touched to add
`opf`/`contingency`.

Checked before touching anything: running the test unmodified passed (2/2) with `opf` and
`contingency` never walked — the coverage claim in this AC would have been true only vacuously,
not because the new API pages were actually verified sufficient. Added `"opf"`, `"contingency"`
to `PACKAGES` — a one-line, mechanical extension, the same step every prior wave's own new
top-level package required when it shipped (this is presumably how `pf` and `results` got onto
the tuple in the first place; nothing else about the test's logic changes). Re-ran: still 2/2,
now genuinely exercising the new packages.

That widening is also what made the submodule `:::` blocks in the two new API pages necessary
rather than decorative: `OpfDuals`, `OpfSolution`, `LmpBreakdown` (defined in `opf/dc_opf.py`)
and `N1Screen`, `screen_n1`, `confirm_n1` (defined in `contingency/n1.py`) are none of them
re-exported into their package's `__init__.py` — without a direct `::: mambo_power.opf.dc_opf` /
`::: mambo_power.contingency.n1` block, they would show up as coverage gaps the moment
`PACKAGES` included the new packages (verified: removing those two blocks and re-running the
test reproduces exactly that failure, then restoring them clears it). This mirrors the M2 R1
fold's `pf.ac_newton` fix precisely — same failure mode, same fix shape.

## Other things found and fixed, not silently left

- **Two broken doc anchors**, both introduced by this slice's own new pages, caught by
  `mkdocs build --strict`'s INFO-level anchor check (not fatal to `--strict` itself, but real):
  `docs/manual/opf.md` linked `numerics.md#power-transfer-distribution-factor-ptdf` (singular
  "factor"; the real heading is "Power transfer distribution factor**s**"), and
  `docs/manual/n1.md` linked a `#verification` section that doesn't exist on that page (meant
  "the agreement guarantee," the section that actually documents the sign-bug-catching test).
  Both fixed; rebuilt clean with zero anchor notices.
- **`docs/design/architecture.md`'s ownership table** named "MATPOWER `rundcopf`, PyPSA
  `optimize`" as DC-OPF's agreement test — but the wave's own spec (Prior art, Not Doing) is
  explicit that MATPOWER `rundcopf` was never executed (a structure reference only); the real
  primary oracle is pandapower `rundcopp`, PyPSA `optimize` secondary. Fixed to name the actual
  oracles used, and added the `contingency.n1` ownership row the table never had at all.
- **A second stale sample in `docs/manual/jobs.md`**, adjacent to the one named in scope: the
  "capability list" code block a few sections up printed `['pf.ac', 'pf.dc']` and a two-row
  table — both stale for the identical reason as the named example (S6 registered `opf.dc`/
  `n1`). Verified the real current output (`['n1', 'opf.dc', 'pf.ac', 'pf.dc']`, four rows) and
  updated the block to match, since leaving it wrong in the same page felt worse than the small
  extra diff.

## Verification (AC-9)

```
$ uv run --no-sync mkdocs build --strict
INFO    -  Documentation built in 48.95 seconds        # exit 0, zero anchor/link warnings

$ uv run --no-sync pytest -q tests/unit/test_api_docs_coverage.py
2 passed in 2.89s

$ uv run --no-sync pytest -q tests/unit/test_examples_run.py -v
tests\unit\test_examples_run.py ..........              # 10 passed, incl. 08_opf_and_n1

$ uv run --no-sync python examples/08_opf_and_n1.py
status: Optimal  cost: 7642.59 $/h  balance dual (energy price): 39.0162 $/MWh
...                                                      # exit 0, real output, no traceback

$ uv run --no-sync pytest -q
573 passed, 10 warnings in 124.97s               # 572 baseline + this slice's 1 new example test

$ uv run --no-sync ruff check .
All checks passed!
$ uv run --no-sync ruff format --check .
126 files already formatted
$ uv run --no-sync mypy
Success: no issues found in 39 source files
```

The 10 pandapower deprecation/divide warnings are the same pre-existing, unrelated ones every
prior slice's own verification reported.

## Files touched (exactly these, staged individually)

- `docs/api/contingency.md` (new)
- `docs/api/opf.md` (new)
- `docs/design/architecture.md` (modified — diagram, ownership table, module map)
- `docs/examples/index.md` (modified — table row, snippet section, "Seven" -> "Eight")
- `docs/manual/jobs.md` (modified — the two stale samples above)
- `docs/manual/n1.md` (new)
- `docs/manual/opf.md` (new)
- `examples/08_opf_and_n1.py` (new)
- `mkdocs.yml` (modified — nav)
- `tests/unit/test_api_docs_coverage.py` (modified — `PACKAGES` widened by two entries)

Also updated (via the `.bionic` junction, not part of the code commit, gitignored): plan.md's
AC-9 evidence block and the S7 dispatch-ledger row.

## Commit

`docs(m3/S7): opf/n1 manual + API pages, architecture diagram, example` — `f37815a`, pushed to
`wave/03-opf-n1` (fast-forward from S6's `5fc26aa`). 10 files, 476 insertions / 17 deletions.

No shared-worktree coordination needed — solo in `mambo-power-m3`, per the dispatch brief;
`git status --porcelain` showed only my own edits at every checkpoint.

## Carry-overs (named, not silently dropped — same list this wave has carried since Step 3)

- Generator-outage N-1 and `model.PiecewiseCost`'s missing convexity validation — both already
  named in the wave spec's own Assumptions/Not Doing and in `contingency`/`opf`'s docstrings and
  now in their manual pages too; nothing new to add here.
- PyPSA as AC-1's secondary oracle was never attempted across the wave (named by S2); this
  slice's own docs (`docs/manual/opf.md`) describe only the pandapower-parity finding actually
  measured, not a PyPSA claim that was never run.

## Wave status

This was the last slice of wave M3 (opf-n1). All of S1-S7 are landed on `wave/03-opf-n1` at
`f37815a`. Per the dispatch brief, the wave now moves to Step 5 (Verify) — not merged, worktree
not removed, `epic/01-foundation` not touched, all per instruction.
