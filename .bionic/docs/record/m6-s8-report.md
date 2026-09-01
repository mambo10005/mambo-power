# M6 / S8 — docs

Slice: S8 docs, wave M6 (zonal-redispatch). Discharges **W8 / AC-8**. Triple: build · audited · wave.
Worktree `C:\Claude Projects\mambo-power-m6`, branch `wave/06-zonal-redispatch`.
Base `f1782e8` (S5); S7b landed `4432163` concurrently. Commit **`e58fff6`** (not pushed).

Reporting contract: every factual claim below carries its proving command and that command's
output, or the label `unverified`.

---

## 1. Verdict

**AC-8 holds.** All four clauses proven, each below. Plus one live CI breakage found and fixed
(§5), and three findings I could not act on under the zero-`src`-changes rule (§7).

| Clause | Result |
| --- | --- |
| `mkdocs build --strict` exits 0 with the new manual + API pages | **exit 0**, zero warnings |
| the symbol-coverage test passes **unmodified** | **2 passed**, file untouched |
| the new example exits 0 in CI | **exit 0** |
| …and is snippet-embedded | embedded, asserted by `test_examples_run.py` |
| the changelog carries an M6 entry | added (Added + 2 Changed bullets) |
| full suite | **974 passed, 4 skipped** |

**Zero changes to `src/`.**

```
$ git diff --name-only f1782e8..e58fff6 -- src
(no output)
$ git status --short -- tests src
(no output)
```

---

## 2. Gate evidence

### 2.1 `mkdocs build --strict`

```
$ uv run --no-sync --with "mkdocs==1.6.1" --with "mkdocs-material==9.7.7" \
    --with "mkdocstrings[python]==1.0.6" --with "pymdown-extensions==11.0.1" \
    python -m mkdocs build --strict
INFO    -  Documentation built in 10.25 seconds
MKDOCS_EXIT=0
```

**Deviation, flagged.** The `m6` worktree's `.venv` has no `docs` dependency group, so the
brief's `uv run --no-sync mkdocs` fails with `program not found`. CI's own recipe is
`uv sync --locked --all-groups && uv run mkdocs build --strict`
(`.github/workflows/ci.yml:146-147`), and the brief forbids `uv sync`. I used `uv run --with`,
which builds an ephemeral overlay on top of the project environment and mutates neither, with
every version **pinned to what `uv.lock` already resolves** (`mkdocs 1.6.1`,
`mkdocs-material 9.7.7`, `mkdocstrings 1.0.6`, `pymdown-extensions 11.0.1`, read out of
`uv.lock:1348,1401,1432,2231`). So the build is the same build CI runs, at the same versions,
without touching the locked environment. Whoever runs the fold should be aware the worktree
cannot run this gate the brief's way.

### 2.2 `test_api_docs_coverage.py`, unmodified

```
$ uv run --no-sync pytest -q --no-header -p no:randomly tests/unit/test_api_docs_coverage.py
2 passed
```

Unmodified — no tracked file under `tests/` or `src/` is touched at all (§1).

Note the coverage test would have passed *without* the new `:::` blocks, because
`results.zonal`'s symbols are re-exported into `mambo_power.results` and `opf.zonal`'s /
`opf.redispatch`'s into `mambo_power.opf`. The blocks were added anyway, per the brief and per
M5's finding that `show_submodules: false` renders only the package docstring — proven to render
real symbols in §4.3, not merely to satisfy the test.

### 2.3 The example

```
$ uv run --no-sync python examples/11_zonal_redispatch.py
... (full output in §3.2) ...
EXIT=0

$ uv run --no-sync ruff check examples/11_zonal_redispatch.py
All checks passed!
```

### 2.4 Full suite, lint, types

```
$ uv run --no-sync pytest -q --no-header
974 passed, 4 skipped, 10 warnings in 70.56s

$ uv run --no-sync ruff check .
All checks passed!
$ uv run --no-sync ruff format --check .
166 files already formatted
$ uv run --no-sync mypy
Success: no issues found in 48 source files
```

**Suite reconciliation.** Baseline 951 at `f1782e8`. My own delta is **+1**: `test_examples_run.py`
is parametrised over `examples/*.py`, so a new script is a new case (12 example cases before, 13
after — visible in the first §2.2-style run, which reported `1 failed, 14 passed` over the two
files = 2 coverage + 13 examples). The remaining +22 is S7b's, landed concurrently at `4432163`.

`ruff format --check .` covers ` ```python ` fences inside Markdown (which is why the examples
gallery deliberately uses the `{ .python }` fence form). My manual page's snippet needed
reformatting; it was reformatted and then **re-extracted from the page and re-run** to confirm
the output block still matches (§3.1).

---

## 3. What was delivered, and how each number in it was obtained

### 3.1 `docs/manual/zonal.md` (new, 573 lines)

Mirrors `market.md`/`multiperiod.md` in structure and depth. Sections: the three-solve chain with
a mermaid diagram; what the comparison measures (D1's theorem stated as a theorem, and the
anchored-rate rejection with its mechanism); zones and corridors (why the capacity is an option
and not a model field, why `CorridorLimit` is a row model); the zonal LP (per-zone balance row,
capacity as a variable bound, two-tier column layout); the corridor sign convention; zone prices
and the "distinct prices are a property of which corridors bind, not of how many zones you drew"
consequence; the capacity price as `|reduced cost|` with the HiGHS sign argument spelled out;
**A22(i)** as its own section (deleting a corridor islands the zones — and a control built by
deletion would also pass a sign-flipped corridor column); **A22's** phase-shifter note; the
redispatch LP (deltas both sides, netted reporting, the PWL linking column, the 2x2 Hessian
block); the three figures as a table with A24's exact definitions; the settlement identity from
the result object; the AC-2 worked example; the case30 fixture; **A20 and A21 as two documented
limits**; errors; a runnable "Using it" snippet; jobs.

Every quoted number is re-run, not pasted:

| Claim on the page | How verified |
| --- | --- |
| the three-regime table (`10/50`, `10/10`, `10/50`) | copied from `examples/11`'s own stdout |
| case30 corridor caps / flows / capacity prices / zone prices | copied from `examples/11`'s own stdout — the array-level readout was **added to the example** so the manual would not be quoting a block no committed script prints |
| `31.694262 31.694262`, residual `1.066e-13` | `examples/11` stdout |
| 17 of 41 branches over rating, worst 11.85 MW, 21.9 MW moved, payment 14.637 | `examples/11` stdout |
| 28 of 30 buses to `5.2e-06`, two at `0.917`, 6 at rating / 4 priced | `examples/11` stdout |
| "elastic bids make every LMP agree to `1e-5`" | measured directly: `with_bids(promote_areas_to_zones(rated_network(case30)))` gives worst LMP diff **9.836563e-06** |
| the "Using it" output block | the block was **extracted from the page by regex and executed**; stdout is byte-identical, before and after `ruff format` touched it |
| the overstated-corridor figures (`400.0` / `-400.0` / `0.0`) | run against the page's own fixture with `cap_mw=30.0` |

The AC-2 numbers agree with `record/m6-ac2-derivation.md` §7's table exactly
(`p_A=70, p_B=10, f=20, λ_A=10, λ_B=50, ν=40`; copper plate `80/0`, both prices `10`).

**Errors section: types verified by running, not read.** M5's D5 was a manual naming `ValueError`
where `NetworkValidationError` was raised. Every row of my errors table was produced by executing
the failure:

```
NonConvexCostError MRO: ['NonConvexCostError', 'ValueError', 'Exception', 'BaseException', 'object']
NonConcaveBidError MRO: ['NonConcaveBidError', 'ValueError', 'Exception', 'BaseException', 'object']
bus with no zone:                 builtins.ValueError                              isValueError=True
Bus.zone -> missing Zone entity:  mambo_power.model.errors.NetworkValidationError  isValueError=False
corridor names unknown zone:      builtins.ValueError                              isValueError=True
corridor names same zone twice:   builtins.ValueError                              isValueError=True
corridor pair given twice:        builtins.ValueError                              isValueError=True
negative cap:                     pydantic_core...ValidationError                  isValueError=True
non-convex generator cost:        mambo_power.opf.dc_opf.NonConvexCostError        isValueError=True
non-concave load bid:             mambo_power.opf.dc_opf.NonConcaveBidError        isValueError=True
no corridor, zone B has no generation:
    -> NO RAISE: status='Infeasible' message="zonal clearing stage: zonal_dc_opf: HiGHS reported model status 'Infeasible'"
```

Two of those are non-obvious and are stated explicitly on the page: `NetworkValidationError` is
**not** a `ValueError` (so `except ValueError:` will not catch a dangling zone reference), and
`CorridorLimit(zone1="A", zone2="A")` is *not* rejected at construction despite the field
description saying the ends must differ — it raises at solve time.

### 3.2 `examples/11_zonal_redispatch.py` (new) + gallery entry

Five parts. Full output:

```
=== 1. Two zones, three buses, one corridor ===
genA @ zone A: 10 $/MWh   genB @ zone B: 50 $/MWh   load: 50 MW in A, 30 MW in B
  corridor capped at 20 MW   price A  10.00  price B  50.00   genA  70.00 MW  genB  10.00 MW
  cap lifted (1e6 MW)        price A  10.00  price B  10.00   genA  80.00 MW  genB   0.00 MW
  no corridor at all         price A  10.00  price B  50.00   genA  50.00 MW  genB  30.00 MW

=== 2. case30, three zones ===
status: Optimal   buses per zone: {'1': 11, '2': 10, '3': 9}
  corridor 1-2: cap   1.524 MW  (1 crossing branches)
  corridor 1-3: cap  16.577 MW  (3 crossing branches)
  corridor 2-3: cap  19.456 MW  (3 crossing branches)
  zone 1: price 3.759145 $/MWh
  zone 2: price 3.880504 $/MWh
  zone 3: price 3.759147 $/MWh
  price spread across the three zones: 0.121359 $/MWh
  corridor ('1', '2'): flow  +1.5237 MW   capacity price 0.121359 $/MWh
  corridor ('1', '3'): flow +15.3588 MW   capacity price 0.000000 $/MWh
  corridor ('2', '3'): flow -19.4562 MW   capacity price 0.121356 $/MWh

=== 3. Deliverability ===
  zonal schedule: 17 of 41 branches over rating  (worst  11.8468 MW)   slack absorbs +0.000e+00 MW
  redispatched:    0 of 41 branches over rating  (worst   0.0000 MW)   slack absorbs -7.105e-15 MW
  redispatch volume: +21.933 MW up / -21.933 MW down across 6 of 6 generators

=== 4. What the zonal design cost ===
  redispatch_payment    +14.636683 $/h   settlement figure, >= 0
  welfare_gap           -2.649e-11 $/h   exactness row, 0 by construction
  generation_cost_gap   -14.636683 $/h   diagnostic, ANY sign
  redispatched point vs market.solve_nodal: dispatch within 3.30e-05 MW
  LMPs: 28 of 30 buses agree within 5.2e-06 $/MWh; the rest differ by up to 0.917 $/MWh
  because the final point is primal-degenerate: 6 branches sit at their rating, only 4 carry a nonzero dual

=== 5. Settlement identity, computed from MarketZonalResult alone ===
  load payment 762.6075 - generator receipts 730.9132  = 31.694262 $/h
  -sum_k(mu_k * flow_k) over 4 binding branches = 31.694262 $/h
  residual: 1.066e-13 $/h
EXIT=0
```

The case30 figures reproduce S5's own orchestrator run exactly (`redispatch_payment=+14.637`,
`generation_cost_gap=-14.637`, 41 branch rows) and the corridor readout reproduces **A22(ii)**
exactly (two of three corridors at cap, `(1,2)` at `+1.52` and `(2,3)` at `-19.46`, zones 1 and 3
equal, zone 2 separated by `0.1214` = both binding corridors' capacity prices).

The example does **not** import from `tests/` — it derives ratings, the zone promotion and the
corridor caps inline from case30's own committed columns, using the same rule `tests/_rated.py`
uses (`max(1.2 * |base flow|, 1.0)`), which is why its numbers coincide with the test fixture's.

Two deliberate choices worth recording:

- **Part 3 asserts the energy balance alongside the ratings, and prints it** — A21's blind spot,
  made visible rather than assumed away. The slack absorbs `+0.000e+00` under the zonal schedule
  and `-7.105e-15` under the redispatched one, so neither readback is the false-green A21 warns
  about, and a reader writing their own check is told to do both.
- **Part 4 evidences the LMP degeneracy instead of hiding it** — see §6.

### 3.3 API pages

Dedicated `:::` blocks for `mambo_power.market.zonal`, `mambo_power.results.zonal`,
`mambo_power.opf.zonal` and `mambo_power.opf.redispatch`, each under a prose heading explaining
what the module owns. Page intros rewritten (market: "three granularities"; opf: "single-period,
multiperiod, zonal, and redispatch").

### 3.4 `docs/design/architecture.md` — from a real scrape

Extended from an **AST walk of every module under `src/`**, not by hand:

```
mambo_power.opf.zonal       -> numerics.arrays, opf.dc_opf
mambo_power.opf.redispatch  -> numerics.arrays, numerics.bbus, numerics.ptdf, opf.dc_opf
mambo_power.market.zonal    -> mambo_power, market.nodal, model, numerics.arrays, opf,
                               opf.dc_opf, opf.redispatch, opf.zonal, results
mambo_power.results.zonal   -> results.market, results.opf, results.provenance
mambo_power.opf             -> ... opf.multiperiod, opf.redispatch, opf.zonal ...
mambo_power.jobs.registry   -> ... market.multiperiod, market.nodal, market.zonal ...
```

Every edge drawn in the diagram is one of those. Diagram gains `opf.zonal` and `opf.redispatch`
nodes with their six real edges; `zonal` removed from the "Later waves" box; the label is now
"Shipped (M1-M6)". Three new rules paragraphs: the two new callers of the shared core and how
they use it in opposite directions (zonal calls `_balance_row` per zone and `_flow_limit_rows`
never; redispatch uses both, with no new row-family helper — the PWL linking equality is an
instance of `_balance_row`); **the D5 helper** `_extract_and_validate` as the single owner of
extraction and both convexity guards; and `market.zonal`'s composition of three solves. Ownership
table gains four rows (D5 helper, zone price, corridor capacity, `final == nodal`). Module map on
disk updated for all four new files.

### 3.5 `docs/changelog.md`

New `### Added — wave M6 (zonal market and redispatch)` section, in M5's shape: `solve_zonal` and
what makes its comparison meaningful; `Zone`/`Bus.zone` becoming solver-read; `CorridorLimit`/
`MarketZonalOptions` and why the capacity is not a model field; both array-level builders;
`results.zonal` and the three separated figures; the seventh jobs kind; the PyPSA `Link` oracle
with **A23's** mechanism and its measured residuals; `tests/_zones.py`. Two `### Changed`
bullets: the D5 unification, and `Scenario.periods` `max_length = 200` (S7a).

### 3.6 Pages M6 falsified

- **`docs/index.md`** — the status admonition said M5 was "in progress on its own wave branch";
  M5 merged at `f447249`. Now M1–M5 merged, M6 in progress. Roadmap table split `M6–M7` into
  `M6` (in progress) and `M7` (planned). New "Where to go next" row.
- **`docs/manual/model.md`** — `## Zone` gains a paragraph saying it is solver-read from M6 and
  pointing at the new page; the `Bus.zone` field row gains the same pointer.
- **`docs/manual/market.md`** — the `Scenario` section now names the third entry point; the
  settlement section discloses that `MarketNodalResult` carries no per-branch rows and points at
  the result type that closed that gap.
- **`mkdocs.yml`** — nav entry (root file, not under `docs/`; no other slice owns it).

---

## 4. Walk-proofing: the render, not just the build

M5's lesson was that `--strict` certifies the build and says nothing about the render. All of
the following are against the **built site**, and the browser checks are against it **served over
HTTP** (`127.0.0.1:8791`), not `file://` — M5's walk showed `file://` injects console errors that
are artifacts of the protocol.

### 4.1 Equations — M5's D6, checked the way D6 was found

```
$ playwright-cli -s=m6-docs-render2 run-code <mathcheck.js> --raw
{"n":32,"untypeset":0,"containingBackslash":[],"rawOpenDelims":0,
 "mermaidBoxes":[{"w":688,"h":238}], ...}
```

**32 of 32 expressions typeset; zero contain a literal backslash; zero raw `\[`/`\(` delimiters
survive in the article text.** The page was written to avoid the D6 cause structurally — it
contains no `\_` at all (`docs/manual/zonal.md` count of `\_`: **0**) because no display equation
uses an underscored identifier inside `\text{}`.

D6 itself is **fixed repo-wide**, which I confirmed rather than assumed:

```
$ python -c "<regex \\text\{[^}]*\\_ over docs/**/*.md>"
=== literal \_ inside \text{} in docs/*.md ===
  (none)
```

`multiperiod.md:131,163,194,271` and `n1.md:34` now carry bare underscores inside `\text{}`, which
MathJax renders correctly.

### 4.2 Mermaid

`mermaidBoxes: [{"w":688,"h":238}]` — measured layout, not a `querySelector` for `<svg>`. M5's walk
recorded that the theme puts the SVG in a **closed** shadow root where `querySelector` can never
see it, so a zero-node reading is meaningless; measuring the element's box is the check that
works. A screenshot of the rendered page is at `.bionic/tmp/m6-s8-zonal.png`.

### 4.3 The `:::` blocks render symbols, not literal text

```
--- api/opf
{"literalColons":0,
 "zonalSymbols":["mambo_power.opf.zonal_dc_opf","mambo_power.opf.zonal",
   "mambo_power.opf.zonal.ZoneKey","mambo_power.opf.zonal.ZonalDuals",
   "mambo_power.opf.zonal.ZonalDuals.zone_price","mambo_power.opf.zonal.ZonalDuals.corridor_cap", ...],
 "redispatchSymbols":["mambo_power.opf.redispatch_dc_opf","mambo_power.opf.redispatch",
   "mambo_power.opf.redispatch.BOUND_TOL_MW","mambo_power.opf.redispatch.RedispatchSolution", ...]}
--- api/market   {"literalColons":0, "newHeadings":["MarketZonalOptions","solve_zonal","Zonal clearing and redispatch","mambo_power.market.zonal", ...]}
--- api/results  {"literalColons":0, "newHeadings":["GenRedispatchResult","LoadRedispatchResult","MarketZonalResult","Zonal market results","mambo_power.results.zonal", ...]}
```

Real anchors per attribute, on all four blocks. Site-wide count of literal `:::` in rendered text:
**0**.

### 4.4 Links, anchors, nav

```
pages: 30  bad links/anchors: 0
```

Every internal `href` on all 30 built pages resolved to a real file, and every fragment to a real
`id=` on the target page. (Site-root-absolute `/mambo-power/...` hrefs, which only exist in
`404.html`, are excluded — they cannot resolve on local disk by design, the same call M5's walk
made.)

Nav reaches the page from pages that are not it: `manual/market/` links `../zonal/` **and**
`../zonal/#settlement-from-the-result-object-alone`; `manual/multiperiod/` links `../zonal/`;
`index.html` and `changelog/` carry it. Screenshot confirms "Zonal market" sits between
"Multiperiod market" and "Results" in the Manual section.

### 4.5 The 3-line rendered-output check, with a positive **and** negative control

```
  PRESENT worked-example numbers:      True
  PRESENT unsigned warning:            True
  PRESENT settlement output 31.694262: True
  PRESENT errors table NetworkValidationError: True
  NEGATIVE CONTROL (should be False):  False
```

and for the gallery embed:

```
  gallery embeds example 11 source (def overloads):        True
  gallery embeds example 11 docstring line:                True
  gallery embeds example 10 too (control that embedding works): True
  gallery NEGATIVE CONTROL (a string only in ex-10 output): False
  gallery NEGATIVE CONTROL ("12_" absent):                 False
```

The negative controls matter: the first extractor I wrote inserted spaces where tags were
stripped, which turned `def overloads(` into `def overloads (` and reported the embed **absent**.
Without a positive control on a page I knew embedded correctly, I would have filed a false defect.

### 4.6 No internal vocabulary on my pages

```
site/manual/zonal/index.html:         record-leaks=none  step-labels=none
site/design/architecture/index.html:  record-leaks=none  step-labels=none
site/changelog/index.html:            record-leaks=none  step-labels=none
site/index.html:                      record-leaks=none  step-labels=none
site/manual/model/index.html:         record-leaks=none  step-labels=none
site/examples/index.html:             record-leaks=none  step-labels=['AC-1','AC-6']   <- pre-existing, in examples 08/09's own source
site/manual/market/index.html:        record-leaks=none  step-labels=['AC-5']          <- pre-existing, M4
```

Both residues are M3/M4's, in files I did not write; see §7.3.

### 4.7 Console

One console error on the zonal page — and on `manual/n1/`, a page this wave never touched:

```
[ERROR] Failed to load resource: 404 @ https://api.github.com/repos/mambo10005/mambo-power/releases/latest
```

The Material theme's repo-stats fetch against a project with no releases. Pre-existing and not
mine; will resolve itself at M9's first release.

### 4.8 Teardown — the M5 trap

M5's teardown was blocked by an HTTP server left running. Mine is down, verified:

```
$ playwright-cli close-all
(PS) killing PID 4532
(PS) port 8791 free
```

---

## 5. A live CI breakage, found and fixed

`tests/unit/test_examples_run.py` was **already red** when I first ran it, before I had touched
anything it covers:

```
FAILED tests/unit/test_examples_run.py::test_example_runs_to_completion[04_jobs_api]
  assert unknown.error is not None   (examples/04_jobs_api.py:52)
```

Cause: `examples/04_jobs_api.py:51` used

```python
unknown = jobs.run(jobs.SolveRequest(kind="market.zonal", network=net))  # not registered yet
```

as its *unknown kind* demonstration. S7b registered `market.zonal` (`4432163`), so the request
succeeded and the assertion failed. `examples/**` is mine, so I fixed it — with a deliberately
fictional kind rather than another real-but-unbuilt one, and a comment saying why:

```python
# A deliberately fictional kind, not a real-but-unbuilt one: `market.zonal` stood here until
# it was registered, at which point this example stopped demonstrating an unknown kind.
unknown = jobs.run(jobs.SolveRequest(kind="pf.telepathy", network=net))
```

```
$ uv run --no-sync python examples/04_jobs_api.py | grep "unknown kind"
unknown kind -> failed UNKNOWN_KIND | unknown kind "pf.telepathy"; registered kinds: market.multiperiod, market.nodal, market.zonal, n1, opf.dc, pf.ac, pf.dc
```

**The same trap is now set again**, in a file I do not own: `docs/manual/jobs.md:226` (S7b's)
uses `kind="market.agents"` as *its* unknown-kind demo, and M7 is the wave that registers
`market.agents`. Flagged to the orchestrator; not edited.

---

## 6. Two design notes the docs now carry, both measured

### 6.1 A20's degeneracy is live on **case30**, not only case300

A20 recorded primal degeneracy at the nodal optimum on rated case300. It reproduces on rated
case30 **when the loads are fixed** (no elastic bids):

```
branches at rating: 6  ['branch-1','branch-11','branch-12','branch-14','branch-20','branch-26']
branches with nonzero dual (redispatch chain): 4  ['branch-1','branch-14','branch-20','branch-26']
branches with nonzero dual (solve_dc_opf):     4  ['branch-1','branch-11','branch-20','branch-26']
  bus-9:  zonal-chain 2.981820 vs nodal 3.899041  |d|=9.172e-01
  bus-11: zonal-chain 2.981820 vs nodal 3.899041  |d|=9.172e-01
  bus-6:  3.675202 vs 3.675207   |d|=5.185e-06
worst dispatch diff: 3.2993e-05 MW
```

The two solves select different active sets (`branch-14` vs `branch-11`), so two of thirty buses
price differently while the **primal** theorem holds to `3.3e-05` MW. S5's AC-4 measured
`8.92e-6` on case30 because its fixture carries bids; I verified that directly — with
`tests/_bids.with_bids` applied to the same promoted, rated case30, the worst LMP difference
drops to **9.836563e-06** while the degeneracy count is unchanged (still 6 at rating, 4 priced).
So bids do not remove the degeneracy; they make both solves land on the **same** dual solution.

The manual documents this as a limit with that measurement, and says explicitly that a blanket
price tolerance wide enough to hide it would admit real regressions — A20's own ruling, stated
for a reader rather than for an auditor.

### 6.2 `MarketZonalResult` carries no corridor rows

`ZonalDuals.corridor_cap` and `ZonalSolution.corridor_flow_mw` exist only at the array level;
the market-level result reports zone prices, both dispatch layers, the deltas, branch rows, bus
LMPs and the three figures. So a corridor's own flow and capacity price are **not** readable from
`solve_zonal`'s output. This is not a defect — the price separation between zones carries the same
information at the market level — but it is a surprise worth stating, so the manual states it in
an admonition and the example demonstrates the array-level call that gets them.

---

## 7. Findings I could not act on (zero `src/` changes)

### 7.1 `opf/zonal.py` cites unpublished planning documents — M5 walk D10, recurring

```
$ grep -rn "record/m6" src/mambo_power/
src/mambo_power/opf/zonal.py:16: ... (spec ``## Design``; ``record/m6-research.md`` §2(b)):
src/mambo_power/opf/zonal.py:43: convention ``record/m6-ac2-derivation.md`` §2 hand-derives ...
src/mambo_power/opf/zonal.py:61: ... already builds (``record/m6-research.md`` §2(a)).
```

These render on the **public** `api/opf` page as citations to files that are not on the site and
not in the package. M5's walk filed exactly this as D10 (LOW) against M2/M3/M5; M6 adds three more
instances. The same page also carries **52** bare wave-step labels (`W1`–`W6`, `AC-1`–`AC-5`) and
`ADR-006/007/008` from M6 docstrings; `api/market` carries 20 and `api/results` 13. Every one is a
dead end for a reader who tries to follow it.

Not fixed: the brief forbids `src/` changes. Each is a one-line docstring edit that changes no
behaviour, and they are all in modules this wave wrote, so a fold is the natural place.

### 7.2 `Zone`'s docstring does **not** lie

The brief asked me to check whether `Zone`'s docstring went false the way `Storage`'s did in M5.
It did not:

```python
class Zone(_Entity):
    """Named grouping of buses (MATPOWER loss zone, market zone, ...)."""
```

It never claimed no solver read it, so becoming solver-read did not falsify it. (M5's D2/D3/D4
docstrings — `Period`, `Storage`, `Load` — are all fixed in `src` already; I re-grepped for the
offending phrases and found none.) The one thing it *could* now say and doesn't is that it is
read, and I put that on `docs/manual/model.md` instead, which is mine. `Generator.cost`'s
`"model-present and solver-ignored until M3"` (`entities.py:125`) is still accurate.

### 7.3 Two pre-existing step labels on public pages

`examples/08_opf_and_n1.py:91` and `examples/09_nodal_market.py:6,76` cite `AC-6` / `AC-1` "in the
wave spec"; `docs/manual/market.md:157` cites "`test_market_nodal.py`'s AC-5 test". All render.
These are M3/M4 residue of the same D10 class. I own both those examples and that page and could
have rewritten them, but they are outside this slice's subject and rewriting a sibling wave's
prose mid-wave is the kind of drive-by that makes a diff hard to review. Left for the fold, noted
here so the decision is deliberate rather than an oversight.

---

## 8. Deviations from the brief

1. **`mkdocs` invocation** (§2.1). The worktree venv has no `docs` group; `uv sync` is forbidden.
   Used `uv run --with` at `uv.lock`'s own pinned versions. Same build, same versions, locked
   environment untouched.
2. **`mkdocs.yml` edited.** It is at the repo root, not under `docs/**`. Without the nav entry the
   new page is unreachable and `--strict` fails on an orphaned file. No sibling owns it.
3. **`examples/04_jobs_api.py` edited** beyond "add example 11" — it was red (§5), it is under
   `examples/**` which the brief assigns me, and leaving CI red was not an option.
4. **The manual's case30 block is quoted from the example**, which meant adding an array-level
   corridor readout to `examples/11` so that no fenced output block on the page comes from a
   script nobody can run. This grew the example past the brief's implied minimum; it is the only
   way to honour "every number the manual quotes from it must be re-run".

---

## 9. Files

| Path | Change |
| --- | --- |
| `docs/manual/zonal.md` | new, 573 lines |
| `examples/11_zonal_redispatch.py` | new, 272 lines |
| `docs/api/opf.md` | +2 `:::` blocks, intro rewritten |
| `docs/api/market.md` | +1 `:::` block, intro rewritten |
| `docs/api/results.md` | +1 `:::` block |
| `docs/design/architecture.md` | diagram, 3 rules paragraphs, 4 ownership rows, module map |
| `docs/changelog.md` | M6 Added section + 2 Changed bullets |
| `docs/examples/index.md` | gallery row + section + `--8<--` embed |
| `docs/index.md` | status, roadmap, "where to go next" |
| `docs/manual/model.md` | `Zone` solver-read; `Bus.zone` pointer |
| `docs/manual/market.md` | third entry point; branch-rows disclosure |
| `mkdocs.yml` | nav entry |
| `examples/04_jobs_api.py` | unknown-kind demo fixed (§5) |

Commit `e58fff6`, 13 files, +1037/-32. Not pushed.
