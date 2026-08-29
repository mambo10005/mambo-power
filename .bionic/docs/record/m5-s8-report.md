# M5 / S8 — docs

Slice: S8 docs, wave M5 (multiperiod). Discharges **W8 / AC-8**. Triple: build · audited · wave.
Worktree `C:\Claude Projects\mambo-power-m5`, branch `wave/05-multiperiod`.
Base `1fd4c74` (S7). Commit **`13aff40`** (not pushed).

Reporting contract: every factual claim below carries its proving command and that command's
output, or the label `unverified`.

---

## 1. Verdict

**AC-8 holds.** All four clauses proven, each below.

| Clause | Result |
| --- | --- |
| `mkdocs build --strict` exits 0 with the new manual and API pages | **exit 0** |
| the symbol-coverage test passes **without modification** | **2 passed**, file untouched |
| the new example exits 0 in CI | **exit 0**, ~0.5 s |
| …and is snippet-embedded | embedded, asserted by `test_every_example_is_embedded_in_the_docs` |
| full suite reconciles against 795 | **800 passed** = 795 + 4 + 1, itemised in §3 |

**Zero changes to `src/`.** The brief's docstring carve-out was not needed and not used.

```
$ git diff --name-only 1fd4c74..13aff40 -- src
(no output)
```

---

## 2. Gate evidence

### 2.1 `mkdocs build --strict`

Run after the final edit (the corrected settlement-identity LaTeX, §6.5):

```
$ uv run --no-sync mkdocs build --strict 2>&1 | grep -iE "^(WARNING|ERROR|INFO *- *Documentation)"
INFO    -  Documentation built in 24.53 seconds
MKDOCS_EXIT=0
```

Baseline before any of my edits, for comparison — the gate was already green, so this proves I
did not break it rather than that I fixed it:

```
$ uv run --no-sync mkdocs build --strict 2>&1 | tail -3
INFO    -  Cleaning site directory
INFO    -  Building documentation to directory: C:\Claude Projects\mambo-power-m5\site
INFO    -  Documentation built in 34.17 seconds
EXIT=0
```

### 2.2 `test_api_docs_coverage.py`, unmodified

```
$ uv run --no-sync pytest -q tests/unit/test_api_docs_coverage.py
..                                                                       [100%]
2 passed in 1.71s
```

Unmodified, and more broadly **no tracked test file is modified at all**:

```
$ git status --short -- tests
?? tests/unit/test_docs_registry_listing.py
```

```
$ git diff --stat 1fd4c74..13aff40 -- tests
 tests/unit/test_docs_registry_listing.py | 62 ++++++++++++++++++++++++++++++++
 1 file changed, 62 insertions(+)
```

Only an addition. Nothing edited.

### 2.3 The example

```
$ uv run --no-sync python examples/10_multiperiod_market.py
... (full output in §4.2) ...
EXIT=0
```

Embedded, and the embed is asserted rather than eyeballed:

```
$ uv run --no-sync pytest -q tests/unit/test_examples_run.py
............                                                             [100%]
12 passed in 24.97s
```

### 2.4 Full suite

Baseline, taken before I touched anything:

```
$ uv run --no-sync pytest -q
795 passed, 10 warnings in 207.33s (0:03:27)
```

After:

```
$ uv run --no-sync pytest -q
800 passed, 10 warnings in 164.81s (0:02:44)
```

### 2.5 Lint and types

```
$ uv run --no-sync ruff check .
All checks passed!

$ uv run --no-sync ruff format --check .
154 files already formatted

$ uv run --no-sync mypy
Success: no issues found in 46 source files
```

(`uv run --no-sync mypy` with no arguments, which is what `.github/workflows/ci.yml:40` runs.
My first attempt passed explicit paths and hit a module-resolution error that is an artefact of
the invocation, not a type error — `tests\_fixtures.py: note: ... adding __init__.py somewhere`.
The CI form is clean.)

---

## 3. Suite reconciliation: 795 → 800

| Source | Count |
| --- | --- |
| baseline (S7 head) | 795 |
| `tests/unit/test_docs_registry_listing.py` (new file, §5) | +4 |
| `test_examples_run.py::test_example_runs_to_completion[10_multiperiod_market]` — the file is parametrised over `examples/*.py`, so a new script is a new case | +1 |
| **total** | **800** |

Exact, no residue.

---

## 4. What was delivered

### 4.1 `docs/manual/multiperiod.md` (new)

Mirrors `docs/manual/market.md`'s structure and depth — the pattern the brief named. Eleven
sections: intro + entry-point table + runnable-script link; the horizon (`Scenario.periods`,
`Period` as an id-keyed override, `periods=None`, what is and is not period-varying); one
builder not two (the shared row-family core, the two-tier column layout, the row-index contract
as a table); ramp coupling (MW units, `None` vs `0`, the two-sided row, the dual-sign
convention, the legitimate-negative-energy-price note); storage (two columns not one signed
column, the shared power row, SoC balance with efficiency, the cyclic condition, and why the
charge/discharge overlap is bounded rather than banned); per-period LMPs; settlement; degeneracy;
errors; oracle and fixtures; a worked example with real output; jobs.

### 4.2 `examples/10_multiperiod_market.py` (new) + gallery entry

Five parts: build the 24-period scenario over case14; the horizon hour by hour; a binding ramp
row and its dual; per-period settlement with storage as the third participant; the `periods=None`
degeneracy. Follows `09_nodal_market.py`'s shape. Full output:

```
status: Optimal  periods: 24  horizon cost: 172905.31 $

storage st-1 at bus-3: 38.85 MW / 155.40 MWh, round trip 0.9025
  h   load MW    LMP@bus       energy  congestion   charge  discharge     SoC MWh
  0    213.67    35.6883    35.6883      0.0000    0.000      0.000      77.700
  1    200.26    34.7953    34.7953      0.0000    1.246      0.000      78.884
  2    189.97    34.7953    34.7953      0.0000   11.536      0.000      89.844
  3    183.51    34.7953    34.7953      0.0000   18.005      0.000     106.949
  4    181.30    34.7953    34.7953      0.0000   20.212      0.000     126.150
  5    183.51    34.7953    34.7953      0.0000   18.005      0.000     143.255
  6    189.97    34.7953    34.7953      0.0000   11.537      0.000     154.215
  7    200.26    34.7953    34.7953      0.0000    1.247      0.000     155.400
  8    213.67    35.6883    35.6883      0.0000    0.000      0.000     155.400
  9    229.29    36.8349    36.8349      0.0000   -0.000      0.000     155.400
 10    246.05    38.0654    38.0654      0.0000    0.000      0.000     155.400
 11    262.81    39.2958    39.2958      0.0000    0.000      0.000     155.400
 12    278.43    40.0117    40.0117      0.0000    0.000      0.000     155.400
 13    291.84    40.2760    40.2642      0.0118    0.000      2.719     152.538
 14    302.13    40.2761    40.2642      0.0119    0.000      9.005     143.060
 15    308.59    40.2761    40.2641      0.0120    0.000     15.538     126.704
 16    310.80    40.2761    40.2635      0.0125    0.000     19.299     106.389
 17    308.59    40.2761    40.2641      0.0120    0.000     15.536      90.035
 18    302.13    40.2761    40.2642      0.0119    0.000      9.002      80.559
 19    291.84    40.2761    40.2643      0.0118    0.000      2.716      77.700
 20    278.43    40.0117    40.0117      0.0000    0.000      0.000      77.700
 21    262.81    39.2958    39.2958      0.0000    0.000      0.000      77.700
 22    246.05    38.0654    38.0654      0.0000    0.000      0.000      77.700
 23    229.29    36.8349    36.8349      0.0000    0.000      0.000      77.700
cyclic end-of-horizon SoC: 77.700 MWh == soc_initial * energy_mwh = 77.700 MWh
hours with a binding branch rating: 7 of 24 -- [13, 14, 15, 16, 17, 18, 19]

binding ramp rows: 2
  h13 gen-3:    4.694 ->    9.694 MW  (delta  +5.000, limit +-5.000)  ramp-up dual -0.082157 $/MWh
  h20 gen-3:    9.695 ->    4.695 MW  (delta  -5.000, limit +-5.000)  ramp-down dual 0.082200 $/MWh

settlement (per period, $/h):
  h   load payment    receipts    st charge  st discharge      surplus
  4      6308.385    7011.653      703.268         0.000        0.000
 16     12582.711   11736.773        0.000       777.294       68.643
largest surplus over the 17 uncongested hours: 1.146e-10 $/h  (storage left unsettled: 703.268 $/h)
horizon: surplus 96.472 $  storage net revenue 127.090 $ (its arbitrage profit)
(the identity's other side, -sum_k(mu_k*flow_k), needs the flow duals, which this result
 type does not carry; tests/unit/test_market_multiperiod.py computes it from a second,
 array-level solve and proves the equality period by period)

periods=None -> n_periods 1, status Optimal
dispatch identical to market.solve_nodal: True (5 gens)
LMPs identical to market.solve_nodal:     True (14 buses)
(bit-exact `==`, not a tolerance: at T=1 the multiperiod builder issues the identical
 calls, in the identical column and row order, that `dc_opf` itself does)
```

Every M5 row family is visibly engaged: ramp rows bind (two, with duals of opposite sign — the
sign convention the manual documents, shown rather than asserted), storage genuinely arbitrages
(charging hours 1–7, discharging 13–19), the cyclic row lands the SoC exactly back on 77.700,
congestion binds in 7 of 24 hours and not the rest, and the degeneracy is `==`.

**How the fixture was tuned, and why that is honest rather than convenient.** My first draft used
`tests/_storage.py`'s own realistic Li-ion efficiencies (0.92 / 0.88, round-trip 0.8096) and 15%
ramp limits. Measured result: the battery sat **completely idle** all 24 hours and no ramp row
bound. That is a correct answer — case14's LMP spread under this profile is 33.31–40.59 \$/MWh,
and `40.59 × 0.8096 = 32.86 < 33.31`, so arbitrage does not pay at that round-trip — but it is a
powerless example, which is precisely the docs-specific trap the brief named. Raising the
efficiencies to 0.95 / 0.95 (round-trip 0.9025) and tightening ramps to 5% of `p_max` makes both
families engage. Recorded here so a reader knows the example's parameters were chosen to exercise
the feature, and so the underlying measurement — *a realistic round-trip is marginally
unprofitable on case14's own price spread* — is not lost.

### 4.3 API pages — the A17(c) decision

**Decided: yes, add dedicated `:::` blocks**, for `market.multiperiod` (in `docs/api/market.md`),
`results.multiperiod` (in `docs/api/results.md`) and `opf.multiperiod` (in `docs/api/opf.md`).

S5's observation is correct and I re-verified it: the coverage test is green either way, because
the new symbols are re-exported into `mambo_power.market` and `mambo_power.results`. So this is a
page-structure choice, and the deciding argument is not coverage:

> `::: mambo_power.market` and `::: mambo_power.results` are configured with
> `show_submodules: false`. That directive renders the **package** `__init__.py` docstring plus
> the re-exported members. It does **not** render the submodule's own module docstring.

Those three module docstrings carry the content a reader most needs and which exists nowhere
else on the site:

- `opf/multiperiod.py` — the two-tier column layout and the **row-index contract** the duals are
  read back against (an eight-row table that is the module's stated contract).
- `results/multiperiod.py` — the settlement identity **in its general form**, with the
  `pf_shift` and `g_shunt` correction terms and the note that M4's statement omitted them.
- `market/multiperiod.py` — what is extracted and from where, and why `periods=None` is the
  degenerate end of one code path rather than a special case.

Without the directives that content is written but unpublished. That is the reason; symbol
coverage is not.

This also follows the page's own established shape: `docs/api/opf.md` already has a dedicated
`::: mambo_power.opf.dc_opf` section and `docs/api/market.md` a `::: mambo_power.market.nodal`
one, both alongside their package-level directive, so the duplicate-rendering question was
already settled in practice. Confirmed empirically anyway — `mkdocs build --strict` is exit 0
with all three added, so no duplicate-anchor warning is produced.

### 4.4 Architecture diagram

The brief said to check rather than assume. I rebuilt the edges from a scrape of every
`from mambo_power...` import across all 33 modules under `src/mambo_power/`, then diffed against
the diagram. Corrections:

- `subgraph present["Shipped (M1-M4)"]` → `(M1-M5)`.
- New node `opf.multiperiod` (`multiperiod_dc_opf`, ramp / SoC / cyclic rows) with the real
  edges `market --> opfmp`, `opfmp --> opf`, `opfmp --> numerics`.
- `market` node now names both entry points; `model` node now names `Period`.
- Later-waves node `market: zonal, multiperiod, agents (M5-M7)` → `zonal (M6), agents (M7)`.
- **A false rule corrected.** The page said *"Later market modes (zonal, multiperiod, agents)
  build on `market.nodal` in turn, not on `opf` directly."* That is flatly untrue of what M5
  built: `market/multiperiod.py` imports `opf.gen_cost_coeffs`, four names from `opf.dc_opf` and
  `multiperiod_dc_opf` from `opf.multiperiod`, and takes only `load_bid_coeffs` from
  `market.nodal`. Replaced with the actual layering.
- `jobs` rule extended with the M5 `Scenario` widening and `resolved_scenario`.
- Ownership table: three new rows (ramp/SoC/cyclic row families → `opf.multiperiod`; storage
  physical limits → `model.Storage`, solver-read from M5; horizon shape → `Scenario.periods`).
- **Module map on disk** had drifted well past M5. It was missing `jobs/` **entirely**, plus
  `model/scenario.py`, `model/islands.py`, `model/warnings.py`, `io/report.py`,
  `numerics/roles.py`, `numerics/errors.py`, `pf/ac_newton.py`, `pf/_common.py` — accumulated
  M2/M3/M4 drift, not M5's. Rebuilt from `ls` output and corrected in full.

### 4.5 `docs/manual/jobs.md`

Eight corrections. Detail and RED evidence in §5.

### 4.6 Pages M5 falsified, corrected in passing

All in `docs/`, all within the stated scope.

- `manual/market.md` — (a) *"`Scenario(network=net)` is presently a thin, self-contained wrapper
  (`network: Network`, nothing else yet)"*, false since S2 added `periods`; (b) *"`jobs.run(...)`
  wraps the network in a `Scenario` itself (the runner's own job, not the caller's)"*, false since
  S7 moved the wrap to `SolveRequest.resolved_scenario`; (c) an **additive** note pointing at the
  general form of the identity — see §6.4 for why this is flagged.
- `manual/model.md` — `Storage`'s row and section both said no solver reads it; `Generator`'s
  field table had no `ramp_up_mw` / `ramp_down_mw`; `Load`'s field table had no `bid` (M4 drift);
  there was no `Scenario` / `Period` section at all. All added or corrected.
- `index.md` — status admonition still had M4 "in progress"; roadmap had M4 "in progress" and
  M5–M7 "planned"; the "Where to go next" table had no multiperiod row.

---

## 5. TDD evidence

### 5.1 Example registration — RED before GREEN

The example was written and committed to disk *before* the gallery entry, so the registration
test fails for the real reason:

```
$ uv run --no-sync pytest -q tests/unit/test_examples_run.py
.F..........                                                             [100%]
_________________ test_every_example_is_embedded_in_the_docs __________________
>       assert missing == [], f"not embedded in docs/examples/index.md: {missing}"
E       AssertionError: not embedded in docs/examples/index.md: ['10_multiperiod_market.py']
E       assert ['10_multiperiod_market.py'] == []
1 failed, 11 passed in 21.84s
```

After adding the `--8<--` embed and the gallery row:

```
$ uv run --no-sync pytest -q tests/unit/test_examples_run.py
............                                                             [100%]
12 passed in 24.97s
```

### 5.2 `tests/unit/test_docs_registry_listing.py` — a new guard, RED on the shipped page

`docs/manual/jobs.md`'s registry listing was stale in **three** separate places, and had been
since M4 — it still printed four kinds, missing `market.nodal` as well as `market.multiperiod`.
The brief said M4's own S7 found a stale hand-written snippet there; whatever it found, it was
not these. Since the failure mode is now on record twice, I added a guard rather than only
another hand-fix.

The test pins the three strings against the live registry. RED is demonstrated against the
**committed** page, read out of git so it is genuinely the shipped bytes:

```
$ git show HEAD:docs/manual/jobs.md > docs/manual/jobs.md   # (restored immediately after)
$ uv run --no-sync pytest -q tests/unit/test_docs_registry_listing.py
FAILED tests/unit/test_docs_registry_listing.py::test_the_manual_prints_the_real_sorted_kind_list
FAILED tests/unit/test_docs_registry_listing.py::test_the_manual_capability_table_lists_every_registered_kind
FAILED tests/unit/test_docs_registry_listing.py::test_the_manual_unknown_kind_message_lists_every_registered_kind
3 failed, 1 passed in 3.76s
```

with, for instance:

```
E   AssertionError: docs/manual/jobs.md's UNKNOWN_KIND message is stale; current list:
    market.multiperiod, market.nodal, n1, opf.dc, pf.ac, pf.dc
```

GREEN on the corrected page:

```
$ uv run --no-sync pytest -q tests/unit/test_docs_registry_listing.py
....                                                                     [100%]
4 passed in 2.16s
```

The fourth test (`test_the_registry_is_non_trivial`, `len(KINDS) >= 6`) is the absence-readback
guard the wave's own A10 practice asks for: the other three are vacuous against an empty
registry.

### 5.3 The pasted outputs in `jobs.md` were regenerated, not hand-edited

Every `text` block on that page was re-derived by running the page's own snippets
(scratchpad script, not committed) and pasting the true output. Blocks 1, 2 and 4 came back
byte-identical to what was already on the page; block 3 (the capability listing) and the
`UNKNOWN_KIND` line of block 5 did not, and are the two that were stale.

**Honest limitation, stated as the brief requires.** `docs/manual/jobs.md`'s snippets remain
**hand-written**, not `pymdownx.snippets` embeds. They are prose-length fragments spread across
the page, not runnable files, so the `--8<--` mechanism that keeps `docs/examples/index.md`
honest does not apply without restructuring the whole page into a script — which is beyond a
docs slice and would make the page worse to read. What is now tested is the part that
demonstrably rots: the registry's contents, in all three places the page states them (§5.2).
What is still untested is the rest — the pasted numbers, the option dicts, the JSON payload
length. Those have not drifted across four waves, but nothing stops them.

---

## 6. What the documentation exposed

The brief asked for this explicitly. Five items; the first is substantive.

### 6.1 The settlement identity cannot be checked from a result object

**Finding.** Neither `MarketNodalResult` nor `MarketMultiperiodResult` / `MarketPeriodResult`
carries branch rows. `MarketPeriodResult` has `generators`, `loads`, `buses`, `storage` and five
settlement scalars — no `flow_limit_dual`, no flows. `OpfDcResult` *does* carry
`OpfBranchFlowResult` rows with `flow_limit_dual`, so the single-period OPF result is strictly
richer than the market results built on top of it.

**How I hit it.** My first draft of the example "verified" the identity as

```python
residual = max(abs((p.total_load_payment + p.total_storage_charge_payment)
                   - (p.total_generator_receipts + p.total_storage_discharge_revenue)
                   - p.congestion_rent) for p in result.periods)
```

which printed `identity residual over all 24 periods: 0.000e+00 $/h`. That reads like a proof and
is worth nothing: `congestion_rent` **is defined as** that subtraction in
`market/multiperiod.py`, so the check is `x - x == 0`. A textbook powerless test, in the docs
slice, exactly as the brief warned. I caught it reading my own printed zero, not from the code.

Worth noting that `examples/09_nodal_market.py` prints the same shape of check
(`payment - receipts == congestion_rent`, tolerance `1e-6`), which is likewise true by
construction on `MarketNodalResult`. Not mine to change and not changed.

**What the example does instead.** A check that can actually fail: on an hour with no binding
rating every LMP equals `λ`, so the surplus must be exactly zero — and it is *only because
storage is settled*. Hour 4 reads load payment 6308.385, generator receipts 7011.653, storage
charge payment 703.268, surplus 0.000; drop the two storage columns and the same subtraction
reads −703.268. The example prints both the settled maximum (`1.146e-10`) and the unsettled one
(`703.268`) across all 17 uncongested hours.

**Recommendation.** Consider adding `OpfBranchFlowResult`-shaped rows to `MarketPeriodResult` in
M6. Today a user who wants the right-hand side must drop to `opf.multiperiod_dc_opf`, re-derive
the PTDF and rebuild the injections — which is what `test_market_multiperiod.py::_identity_rhs`
does, in about 45 lines. That is a reasonable thing for a test to do and an unreasonable thing to
ask of a reader of the manual page that states the identity. The manual page says so plainly
rather than implying the check is available.

### 6.2 Three shipped docstrings are now false — and fixing them is not free

| Symbol | Docstring | Status |
| --- | --- | --- |
| `model.Storage` | "Energy storage. Schema-present; no M1 solver reads it." | false since S4/S5 |
| `model.Period` | "…solver-side behaviour; nothing reads this field yet, wave M5 Design item 1" | false since S5 |
| `model.Load` | "``bid`` is model-present; only ``market.nodal`` reads it." | false since S5 (`market.multiperiod` reads it via the shared `load_bid_coeffs`) |

All three render in the API reference. `Storage`'s is the one that most directly contradicts the
new manual page.

**I did not fix them, and the reason is not scope timidity.** pydantic puts a model's class
docstring into its JSON schema, and that schema is snapshot-tested:

```
$ grep -rn "no M1 solver reads it" tests/unit/snapshots/
tests/unit/snapshots/network.schema.json:616:      "description": "Energy storage. Schema-present; no M1 solver reads it.",
```

So the one-line docstring fix regenerates `tests/unit/snapshots/network.schema.json` — i.e. it
changes the package's **published JSON schema surface**, which is a deliberately visible diff
(`docs/manual/model.md`: *"any schema change is a visible diff"*). That is not a docs-slice
change, and it is not a change that should be made silently at the end of a wave.

**Fold candidates A17(d), (e), (f); they must land together with a snapshot regeneration.**

### 6.3 `docs/manual/jobs.md` had been wrong since M4, in three places

Detail in §5.2. The point for the record: this is the second wave running in which the jobs
manual's registry listing shipped stale, and both times it was the docs slice that found it. It
is now guarded.

### 6.4 One edit adjacent to A17(b), flagged for the fold

`docs/manual/market.md` states the settlement identity in its narrow form — the same claim as
A16 / A17(b), but on the manual page rather than in the docstring. The brief scoped **the
docstring** out of my slice.

I left M4's derivation text intact and added a five-line `!!! note` after it saying the form is
stated without the `pf_shift` / `g_shunt` corrections, that it is exact only on a network
carrying neither, that `case300` is the exception, and pointing at the general form on the new
page. Rationale: it stops a reader inheriting the error without rewriting anything the fold will
want to rewrite.

**If you would rather the nodal page and its docstring be corrected in one motion at the fold,
revert that hunk** — it is the only one in `docs/manual/market.md`'s Settlement section.

### 6.5 An error of my own, caught in the built HTML

My first draft of the general identity rendered as

```latex
\underbrace{\sum_d LMP_d p_d + \sum_s LMP_s c_s}_{paid in} -
\underbrace{\sum_g LMP_g p_g - \sum_s LMP_s d_s}_{paid out}
```

The minus in front of the second underbrace distributes, so that reads
`… − Σ LMP_g p_g **+** Σ LMP_s d_s` — the wrong sign on the discharge term, contradicting the
identity three paragraphs above it. Found by reading `site/manual/multiperiod/index.html` rather
than the Markdown source. Corrected with an explicit `\left( … \right)` and re-verified in the
built site:

```
$ grep -A 2 'text{paid in}' site/manual/multiperiod/index.html
\underbrace{\sum_d \text{LMP}_d\, p_d + \sum_s \text{LMP}_s\, c_s}_{\text{paid in}} \;-\;
\underbrace{\left(\sum_g \text{LMP}_g\, p_g + \sum_s \text{LMP}_s\, d_s\right)}_{\text{paid out}}
= -\sum_k \mu_k f_k + \sum_k \mu_k \,\text{pf\_shift}_k - \sum_n \text{LMP}_n\, g_{\text{shunt},n}
```

Recorded because rendering LaTeX is a place where a docs slice can ship a *wrong equation* while
every gate stays green — `mkdocs --strict` does not typecheck mathematics.

---

## 7. Claims I verified rather than inherited

The brief warned against over-claiming, so the two fixture facts the new page asserts were
measured here rather than copied from S5's report:

```
$ uv run --no-sync python -c "..."   # max |g_shunt_pu| per fixture
case14 max g_shunt_pu 0.0
case30 max g_shunt_pu 0.0
case118 max g_shunt_pu 0.0
case300 max g_shunt_pu 0.0014000000000000002
```

```
$ uv run --no-sync python -c "..."   # case14, both correction terms
case14 max |pf_shift| pu 0.0 max |g_shunt| pu 0.0
```

So: the manual's claim that the two correction terms vanish on every shipped fixture except
`case300` is measured, as is the example's claim that case14 carries neither — which is what
makes the example's narrow reading of `congestion_rent` legitimate *there*.

Internal anchors were verified against the built site rather than by inspection:

```
$ cd site && for a in the-horizon-scenarioperiods-and-period ramp-coupling \
      degeneracy-one-period-is-the-nodal-clearing; do grep -c "id=\"$a\"" manual/multiperiod/index.html; done
1
1
1
$ grep -c 'id="10-multiperiod-market"' examples/index.html
1
$ grep -c 'id="the-scenario"' manual/market/index.html
1
```

The manual page's own worked example and its jobs snippet were both executed, and their pasted
output is the real output:

```
Optimal 2 3091.666667
t=0  lmp  10.0  charge 16.666667  discharge  0.000000  soc 15.000  surplus -0.000000
t=1  lmp  50.0  charge  0.000000  discharge 13.500000  soc  0.000  surplus 0.000000
508.333333 $ storage net revenue over the horizon
ok 2
```

which reproduces research §7.2's closed form exactly: `charge* = 50/3 = 16.666667`,
`discharge* = 0.81 × 50/3 = 13.5`, `profit* = 50/3 × 30.5 = 508.333333`.

---

## 8. Smaller findings, no action taken

- The example prints `-0.000` for storage charge at hour 9 — a real signed zero out of HiGHS. Left
  as printed rather than cosmetically clamped; the output is what the solver returned.
- `tests/_storage.py`'s siting paragraph refers to *"`tests/_periods.py`'s own two-archetype
  profile"*, which `_periods.py` itself abandoned (its own docstring records the measurement that
  forced the change to a single curve). A stale cross-reference inside `tests/`, outside a docs
  slice's scope. Cheap fold item.
- `docs/design/decisions.md` (ADR-004) still says long-running kinds *"(N-1 sweeps, multi-period)
  will take a `cancel`/`progress` hook"*. Left alone deliberately: ADRs are dated records of what
  was decided, not living documentation, and rewriting one to match later reality destroys its
  value. The corresponding forward-looking sentence in `manual/jobs.md` — which *is* living
  documentation — was updated instead, to say that `market.multiperiod` ships without such a hook
  because a 24-period case14 horizon solves in well under a second (measured: 0.043–0.11 s).

---

## 9. Files touched

```
$ git show --stat --oneline 13aff40
13aff40 docs(m5/S8): multiperiod manual + API pages, architecture, example 10, jobs.md corrections
 docs/api/market.md                       | 11 +++--
 docs/api/opf.md                          | 13 ++++--
 docs/api/results.md                      |  8 ++++
 docs/design/architecture.md              | 47 ++++++++++++-------
 docs/examples/index.md                   | 16 ++++++-
 docs/index.md                            | 27 +++++++----
 docs/manual/jobs.md                      | 55 ++++++++++++++++-------
 docs/manual/market.md                    | 17 +++++--
 docs/manual/model.md                     | 25 +++++++++--
 docs/manual/multiperiod.md               | (new)
 examples/10_multiperiod_market.py        | (new)
 mkdocs.yml                               |  1 +
 tests/unit/test_docs_registry_listing.py | (new)
 13 files changed, 842 insertions(+), 53 deletions(-)
```

Nothing under `src/`. No pre-existing test modified.

---

## 10. Handoff

- Commit `13aff40` on `wave/05-multiperiod`, **not pushed** (as instructed).
- Progress artifact: `.bionic/tmp/m5-s8-progress.md`.
- Fold candidates raised here: **A17(d)(e)(f)** (§6.2, the three false docstrings — must land with
  a `network.schema.json` snapshot regeneration); the `market.md` note in §6.4 (revert if the fold
  prefers to correct nodal page and docstring together); `tests/_storage.py`'s stale
  cross-reference (§8).
- Design item for M6: branch rows on `MarketPeriodResult` (§6.1).
