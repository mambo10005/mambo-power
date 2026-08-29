# M4 S7 report — docs: nodal-market manual + API pages, architecture diagram, example, jobs.md fix

Wave M4 "nodal-market", Slice S7 (last slice). Senior-implementor, complex. Worktree
`C:\Claude Projects\mambo-power-m4`, branch `wave/04-nodal-market`, base `5442465` (S1-S6
landed). Commit `aa53140`, pushed (`5442465..aa53140`, clean fast-forward).

## What was built

1. **`docs/manual/market.md`** — the nodal-market manual page, following `docs/manual/opf.md`'s
   house style (entry-point table, formulation, duals, errors, "Using it"). Covers: the
   `Scenario` wrapper and why bid data lives on `Load.bid`/`Generator.cost` rather than on the
   scenario; the elastic-demand LP extension inside `opf.dc_opf` (new columns, the hypograph
   encoding as the concave mirror of the existing epigraph one); **the double-counting
   contract** — `dc_opf` itself subtracts an elastic load's own historical contribution off
   `NetworkArrays.load_p_max_pu` before adding its LP column, so the caller (`market.solve_nodal`)
   passes `arr` completely unmodified (S3's real design decision, per its own report); the
   generator-side `c2 ≥ 0` guard closed as a byproduct of the bid-side `NonConcaveBidError`;
   `solve_nodal`'s "every load, bid or fixed, gets a result row" decision (S4); LMPs reused
   verbatim via `lmp_decomposition`; the settlement identity; the price-taker reduction
   property; the `sgen`-framed pandapower oracle convention with the `load`-row quadratic
   non-convergence bug named precisely (S5); the jobs-API integration.
2. **`docs/api/market.md`** — mkdocstrings page mirroring `docs/api/opf.md`'s two-block pattern
   (package-level `show_submodules: false`, then a named `mambo_power.market.nodal` block).
   `"market"` added to `tests/unit/test_api_docs_coverage.py`'s hand-maintained `PACKAGES`
   tuple — confirmed non-vacuous, not just added-and-hoped: `pkgutil.iter_modules` over
   `mambo_power.market` finds `nodal.py`, and both coverage tests pass with `market` genuinely
   walked.
3. **`mkdocs.yml`** — nav entries: "Nodal market" under Manual (after N-1 screening), and
   `mambo_power.market` under API reference (after `mambo_power.contingency`).
4. **`docs/design/architecture.md`** — the mermaid import-graph diagram updated with `market`'s
   real edges, grepped directly (`grep -rn "^from mambo_power\|^import mambo_power"
   src/mambo_power/market/*.py`), not guessed: `market --> model`, `market --> numerics`,
   `market --> opf`, `market --> results`, plus `jobs --> market`. `market` moved out of the
   "Later waves" subgraph into "Shipped"; the later-waves box now holds only zonal/multiperiod/
   agents, dotted into `market` itself (not `opf`) since those later modes build on
   `market.nodal`, not on `opf` directly. Rules prose and the on-disk module map updated to
   match (`market/` directory, `results/market.py`).
5. **`examples/09_nodal_market.py`** — a hand-built 2-bus network (mirroring
   `tests/unit/test_opf_dc_demand.py`'s AC-1 hand-KKT fixture, not a MATPOWER file): a cheap
   slack generator, an expensive generator behind a 20 MVA rated branch, one load with a
   2-segment concave PWL bid and one fixed (unbid) load at the slack bus — added deliberately
   to demonstrate S4's "every load appears in the result" decision without perturbing the
   known congestion numbers (verified: the fixed load sits on the slack side of the binding
   branch, so it doesn't change the branch flow or either dual). Wrapped in `Scenario`, run
   through `market.solve_nodal`, prints dispatch, bound duals, per-bus LMP split into
   energy/congestion, and the settlement identity check. Registered in
   `docs/examples/index.md`'s table and gallery (embedded via the `{ .python }` / `--8<--`
   snippet form, per house convention — never a plain fence, which `ruff format` would rewrite
   into an expression). No separate test-registration was needed:
   `tests/unit/test_examples_run.py`'s `EXAMPLES` list is `sorted(EXAMPLES_DIR.glob("*.py"))`,
   auto-discovered; only the docs-embedding assertion needed the new gallery entry.
6. **`docs/manual/jobs.md`** — fixed S6's flagged stale snippet. The "Failures are data"
   example used `kind="market.nodal"` as its "unknown kind" demo; S6 had already fixed the
   executed test/example (`examples/04_jobs_api.py`) to use `kind="market.zonal"` instead, but
   left this prose-only manual page untouched (explicitly flagged in `m4-s6-report.md` as
   "squarely S7's territory"). Swapped the code block to `market.zonal` and corrected the
   printed `UNKNOWN_KIND` output's registered-kinds list — both verified against a real run
   (`registered kinds: market.nodal, n1, opf.dc, pf.ac, pf.dc`, HiGHS/pydantic-order, not
   guessed).

## Verification (AC-8)

- `uv run --no-sync mkdocs build --strict` — exit 0, "Documentation built in 28.11 seconds"
  (the only warning is Material's own MkDocs-2.0 deprecation notice, unrelated to this wave).
- `uv run --no-sync pytest -q tests/unit/test_api_docs_coverage.py` — 2 passed:
  `test_every_public_symbol_is_reachable_from_an_api_page` and
  `test_walk_covers_every_shipped_package` (the latter is what makes the former non-vacuous —
  it asserts `market` actually has submodules for the walk to see).
- `uv run --no-sync pytest -q tests/unit/test_examples_run.py` — 11 passed, including
  `test_example_runs_to_completion[09_nodal_market]` and
  `test_every_example_is_embedded_in_the_docs`.
- `uv run python examples/09_nodal_market.py` run directly (not just asserted exit 0):
  ```
  status: Optimal
  dispatch:
    gen  g1   bus b1   30.000 MW  bound dual   0.000
    gen  g2   bus b2    0.000 MW  bound dual   5.000
    load d0   bus b1   10.000 MW  bound dual   0.000  (fixed, no bid)
    load d1   bus b2   20.000 MW  bound dual   0.000
  LMPs:
    b1: lmp  10.000  energy  10.000  congestion   0.000
    b2: lmp  45.000  energy  10.000  congestion  35.000
  settlement: load payment 1000.00  generator receipts 300.00  congestion rent 700.00
  settlement identity (payment - receipts == congestion rent) holds: True
  ```
- Full repo suite: `uv run --no-sync pytest -q` — **646 passed** (645 S6 baseline + 1 new
  parametrized `test_example_runs_to_completion` case), 10 warnings (pre-existing pandapower
  `FutureWarning`/`RuntimeWarning` noise, unrelated).
- `uv run --no-sync ruff check .` — all checks passed.
- `uv run --no-sync ruff format --check .` — 140 files formatted clean. `ruff format .` also
  reformatted the plain ```` ```python ```` fence inside `docs/manual/market.md`'s "Using it"
  section (cosmetic re-wrapping only, content and printed output unaffected — re-verified after
  the reformat) — this matches `docs/manual/opf.md`'s own precedent of a plain fence for a
  non-embedded illustrative snippet; only the actual snippet-embedded example
  (`examples/09_nodal_market.py`, referenced via `--8<--`) needed the `{ .python }` guard.
- Bare `uv run mypy` (no positional `.`) — "Success: no issues found in 43 source files"
  (unchanged source-file count: this slice touched no `src/` files).

## Not done by this slice

`src/mambo_power/**` untouched (docs-only slice, per the dispatch). `docs/index.md`'s home-page
status blurb still describes wave M3 as "in progress" — pre-existing staleness relative to this
worktree's actual base (M3 merged at `5fa3285`, confirmed by the wave spec's own header); not
in this slice's assigned scope (the dispatch named `docs/manual/jobs.md`'s specific flagged
snippet, not a general home-page audit), left as a candidate for a future wave's own S7 to pick
up alongside its own status update, the way M2/M3's S7 slices each did for their own wave.

## Commit

`aa53140` — `docs(m4/S7): nodal-market manual + API pages, architecture diagram, example,
jobs.md fix`, pushed to `wave/04-nodal-market` (clean fast-forward `5442465..aa53140`, no
rebase needed — solo in the worktree for this slice, confirmed via `git status --porcelain`
before staging). Staged explicitly: `docs/api/market.md`, `docs/design/architecture.md`,
`docs/examples/index.md`, `docs/manual/jobs.md`, `docs/manual/market.md`,
`examples/09_nodal_market.py`, `mkdocs.yml`, `tests/unit/test_api_docs_coverage.py` — exactly
the eight files this slice touched, no `git add -A`.

This was the wave's last slice. Per the dispatch: no merge, `epic/01-foundation` untouched,
worktree not removed.
