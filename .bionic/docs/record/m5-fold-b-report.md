# M5 R1 fold B — documentation half

Agent `m5-fold-b`. Worktree `C:\Claude Projects\mambo-power-m5`, branch `wave/05-multiperiod`,
started from `13aff40`, finished at `196dada`.

Owned and edited: `docs/**`, `examples/**`, `tests/_storage.py`, `tests/parity/**`. Nothing under
`src/**` or `tests/unit/**` was touched — every commit staged explicit paths and `git status
--porcelain` was checked before each one.

## Commits

| Commit | Contents |
| --- | --- |
| `37aa76e` | D6, D5, audit finding 1, D9, D8, AC-3, the nit's manual site |
| `7a6506c` | D1 changelog, plus three manual claims the wave's own code moved past |
| `f31c599` | the nit's second site, in the example's own comment |
| `196dada` | rewrap three lines past the 100-column margin |

## Verification, at `196dada`

```
$ uv run --no-sync pytest -q
815 passed, 10 warnings in 199.86s (0:03:19)
```

Run on a clean tree (`git status --porcelain` empty). Baseline was 800 at `13aff40`; the +15 is
`m5-fold-a`'s new unit tests plus this half's one new parity test. The run began at `7a6506c`;
`f31c599` and `196dada` are a Python comment and three line wraps, and `tests/unit/
test_examples_run.py` was re-run after both (18 passed, below).

```
$ uv run --no-sync mkdocs build --strict > /dev/null 2>&1; echo $?
0

$ uv run --no-sync pytest tests/unit/test_examples_run.py \
    tests/unit/test_api_docs_coverage.py tests/unit/test_docs_registry_listing.py -q
18 passed in 58.71s
```

`tests/unit/test_api_docs_coverage.py` passes **unmodified** — it was never edited and never
needed to be.

---

## D6 — MathJax renders literal backslashes. Fixed, verified by rendering.

Five sites, all `\_` inside `\text{}`: `docs/manual/multiperiod.md:107` (ramp row), `:139`
(charge+discharge cap), `:159` (cyclic row), `:234` (settlement identity), and the pre-existing
`docs/manual/n1.md:34`.

**The defect, in rendered output.** Built the site, served it on `127.0.0.1:8765`, drove it in
Chrome and read `mjx-container` text:

```
{"n":12,"mathjax":true,"out":[
 {"i":0,"text":"− ramp\\_down\\_mw 𝑔 ≤ 𝑝 𝑔 [ 𝑡 ] − 𝑝 𝑔 [ 𝑡 − 1 ] ≤ ramp\\_up\\_mw 𝑔 ."},
 {"i":2,"text":"charge [ 𝑡 ] + discharge [ 𝑡 ] ≤ p\\_max\\_mw ,"},
 {"i":6,"text":"soc [ 𝑇 − 1 ] = soc\\_initial × energy\\_mwh ,"},
 {"i":10,"text":"... + ∑ 𝑘 𝜇 𝑘 pf\\_shift 𝑘 − ∑ 𝑛 LMP 𝑛 𝑔 shunt , 𝑛"}]}
```

**After the fix, same page, same method:**

```
{"total":12,
 "unique":["− ramp_down_mw 𝑔 ≤ 𝑝 𝑔 [ 𝑡 ] − 𝑝 𝑔 [ 𝑡 − 1 ] ≤ ramp_up_mw 𝑔 .",
           "charge [ 𝑡 ] + discharge [ 𝑡 ] ≤ p_max_mw ,",
           "soc [ 𝑡 ] − soc [ 𝑡 − 1 ] − 𝜂 𝑐 charge [ 𝑡 ] + discharge [ 𝑡 ] 𝜂 𝑑 = 0 ,",
           "soc [ 𝑇 − 1 ] = soc_initial × energy_mwh ,",
           "lmp 𝑏 [ 𝑡 ] = 𝜆 balance [ 𝑡 ] ⏟ energy + ∑ 𝑘 𝜇 𝑘 [ 𝑡 ] ⋅ PTDF [ 𝑘 , 𝑏 ] ⏟ congestion .",
           "∑ 𝑑 LMP 𝑑 𝑝 𝑑 + ∑ 𝑠 LMP 𝑠 𝑐 𝑠 ⏟ paid in − ... + ∑ 𝑘 𝜇 𝑘 pf_shift 𝑘 ..."],
 "literalBackslashRemaining":[]}
```

`docs/manual/n1.md`, same method: `"estimated [ 𝑙 ] = | base_flow [ 𝑙 ] + LODF [ 𝑙 , 𝑘 ] ⋅
base_flow [ 𝑘 ] |"`, `literalBackslashRemaining: []`.

Screenshot of the fixed ramp equation: `<scratchpad>/d6-ramp-equation-fixed.png`.

`grep -rnF '\_' docs/ --include=*.md | wc -l` was 5, is now 0. `mkdocs build --strict` exits 0
both before and after, which is why this was invisible to CI.

## D5 — the Errors section named an exception that will not be caught. Fixed, both sites.

Verified, not assumed:

```
$ uv run --no-sync python -c "..."
MRO: (NetworkValidationError, Exception, BaseException, object)
issubclass ValueError: False
```

```
RAISED at Network construction: NetworkValidationError
Network validation failed with 1 issue:
  - BAD_RANGE at generators[0].ramp_up_mw: generator "g1": ramp_up_mw must be > 0 when given, got 0.0
```

So both the class and the raiser were wrong. `docs/manual/multiperiod.md:99` and `:278` now name
`NetworkValidationError` and `Network`'s own construction, link to
[Validation](../../docs/manual/model.md), state explicitly that `except ValueError:` catches
nothing, and note that the array-level `opf.multiperiod_dc_opf` — which takes ramp limits as bare
arrays with no `Network` behind them — is the function the old `ValueError` claim was true of
(`src/mambo_power/opf/multiperiod.py:323`, `_checked_ramp`).

## Audit finding 1 — the T=1 `==` claim. Softened to what is true, after reproducing it.

Reproduced independently before writing anything, over all five fixtures, plain and
`rated_network`, comparing `market.solve_nodal` against both multiperiod routes:

```
case14  plain | periods=None bitexact=True  || explicit bitexact=True
case14  rated | periods=None bitexact=True  || explicit bitexact=True
case30  plain | periods=None bitexact=True  || explicit bitexact=True
case30  rated | periods=None bitexact=True  || explicit bitexact=True
case57  plain | periods=None bitexact=True  || explicit bitexact=True
case57  rated | periods=None bitexact=True  || explicit bitexact=False lmp=1.705e-13 gen=0.000e+00 pay=0.000e+00
case118 plain | periods=None bitexact=True  || explicit bitexact=True
case118 rated | periods=None bitexact=True  || explicit bitexact=False lmp=2.082e-12 gen=7.283e-12 pay=2.619e-10
case300 plain | periods=None bitexact=True
case300 rated | periods=None bitexact=True
```

`case300`'s *explicit* route was unreachable at the time of the run — `Period`'s `>= 0` validator
rejected the identity profile over its eight negative loads. That validator is the one
`m5-fold-a` dropped; the run above is the direct evidence for why.

The manual now makes two separate claims: `periods=None` is bit-exact on every bundled fixture
including case300, and an explicit single `Period` agrees to floating-point tolerance — bit-exact
on the fixtures the tests assert it over, not in general — with the measured divergences quoted
and the mechanism named (`period_load_mw` array arithmetic instead of `dc_opf`'s literal
expressions).

Widening the test parametrization was left to `m5-fold-a` as instructed.

## AC-3 — `min(charge, discharge) ≈ 0` on the parity fixture. Added.

`tests/parity/test_market_multiperiod_vs_pypsa.py` gains
`test_no_simultaneous_charge_and_discharge` plus `SIMULTANEITY_ABS_TOL_MW = 1e-6`. Measured on
the case14×24 fixture itself:

```
n = 24 max overlap = 0.0 exactly zero: True
charge range -1.1102230246251565e-16 0.7827297793754309
discharge range 0.0 1.0326393212978224
```

Exactly `0.0`, so the constant's docstring says so and says why it pins a measurement rather than
an invariant the builder enforces. `pytest tests/parity/test_market_multiperiod_vs_pypsa.py -q` →
`10 passed in 47.31s`.

## D9 — the flagship example had the property the manual warns about. Fixed, but not with 0.92/0.88.

`examples/10_multiperiod_market.py` used `efficiency_charge = efficiency_discharge = 0.95`.

**`tests/_storage.py`'s 0.92/0.88 is not usable here, measured.** Round trip 0.8096. This
horizon's LMP at the storage bus swings 33.3113 (hour 4) to 40.8846 (hour 15), so arbitrage needs
a round trip above `33.3113 / 40.8846 = 0.8148`. At 0.8096 the unit does nothing at all — the
first attempt printed charge 0.000 and discharge 0.000 for all 24 hours, SoC flat at 77.700,
`storage net revenue -0.000`, and 10 binding ramp rows instead of 2. The whole storage half of the
example dies.

Swept seven pairs. `transpose_dcost` is `|cost(ec,ed) - cost(ed,ec)|` — the thing an equal pair
makes zero, which is the defect:

```
ec=0.95 ed=0.95 rt=0.9025 cost=172905.311 charge_sum=81.789 disch_sum=73.815 transpose_dcost=0.000000
ec=0.92 ed=0.88 rt=0.8096 cost=173096.536 charge_sum= 0.000 disch_sum=-0.000 transpose_dcost=0.000000
ec=0.97 ed=0.93 rt=0.9021 cost=172909.240 charge_sum=80.103 disch_sum=72.261 transpose_dcost=5.296754
ec=0.98 ed=0.92 rt=0.9016 cost=172912.116 charge_sum=79.286 disch_sum=71.484 transpose_dcost=7.842946
ec=0.96 ed=0.94 rt=0.9024 cost=172906.966 charge_sum=80.937 disch_sum=73.038 transpose_dcost=2.668795
ec=0.95 ed=0.90 rt=0.8550 cost=173057.643 charge_sum=59.698 disch_sum=51.042 transpose_dcost=0.000000
ec=0.93 ed=0.92 rt=0.8556 cost=173056.181 charge_sum=61.053 disch_sum=52.237 transpose_dcost=0.000000
```

Chose **0.97 / 0.93** — round trip 0.9021, essentially the 0.9025 the example already had, so the
schedule and the ramp story survive; a 4-point asymmetry; and transposition now moves the horizon
cost by 5.30 \$ where at 0.95/0.95 it moved it by exactly nothing. The example carries a comment
stating the arbitrage threshold and naming why it is not the test suite's more pessimistic pair.

**Re-run, and every figure re-checked:**

```
status: Optimal  periods: 24  horizon cost: 172909.24 $
storage st-1 at bus-3: 38.85 MW / 155.40 MWh, round trip 0.9021
  ... charges hours 1-7 (peak 19.971 MW at h4), discharges hours 13-19 (peak 19.042 MW at h16)
cyclic end-of-horizon SoC: 77.700 MWh == soc_initial * energy_mwh = 77.700 MWh
hours with a binding branch rating: 7 of 24 -- [13, 14, 15, 16, 17, 18, 19]
binding ramp rows: 2
  h13 gen-3: 4.778 ->  9.778 MW (delta +5.000, limit +-5.000) ramp-up   dual -0.084589 $/MWh
  h20 gen-3: 9.780 ->  4.780 MW (delta -5.000, limit +-5.000) ramp-down dual +0.084633 $/MWh
settlement (per period, $/h):
   4   6305.178   6999.710    694.532      0.000        0.000
  16  12585.010  11748.252      0.000    767.032       69.726
largest surplus over the 17 uncongested hours: 2.601e-10 $/h  (storage left unsettled: 694.532 $/h)
```

Still exactly **two** binding ramp rows with opposite-sign duals, so
`docs/examples/index.md:120`'s claim survives unchanged.

Manual figures updated: hour-4 load payment `6308.385 → 6305.178`, generator receipts
`7011.653 → 6999.710`, storage charge payment `703.268 → 694.532`, and the "drop the two storage
columns" figure `−703.268 → −694.532`. Checked: `6305.178 - 6999.710 = -694.532`, and
`6305.178 + 694.532 - 6999.710 = 0`.

## D8 — the `tests/_periods.py` cross-reference. Fixed. The second site does not exist.

`tests/_storage.py:32` cited "`tests/_periods.py`'s own two-archetype profile" as the reason the
largest-load bus is behind a congested branch "during its own peak hour". `tests/_periods.py:10`
records that design as measured infeasible and replaced by a single system-wide curve, under which
every load peaks in the same hour and there is no per-bus peak hour at all.

Rewritten to say what `_periods.py` does, why the two-archetype design was abandoned, and — the
point the old text was reaching for — that because the profile carries no locational diversity,
the siting rule is what supplies all of it.

`grep -rn "two-archetype\|two archetype" tests/ docs/ examples/` returns exactly one hit, the one
fixed. `tests/_storage.py` is 103 lines; there is nothing at the "~129" the review named.
`ruff format --check` and `ruff check` both clean.

## Nit — "exactly zero — and it is". Fixed in both places.

`docs/manual/multiperiod.md:225` and, four lines above the print that contradicts it,
`examples/10_multiperiod_market.py`'s own comment. Both now say what the number is: the largest
surplus over the 17 uncongested hours is 2.601e-10 \$/h — an LP residual, zero to the solver's own
precision, not an imbalance.

## D1 — the changelog. Rewritten; 112 lines → 320.

`docs/changelog.md` had three content headings (`Unreleased`, M2 "in progress", M1 "merged") and
zero occurrences of opf, market, multiperiod, n-1, storage or ramp. Now, rendered:

```
heads: ["Unreleased", "Added — wave M5 (multiperiod market)", "Added — wave M4 (nodal market)",
        "Added — wave M3 (DC optimal power flow, N-1 screening)", "Added — wave M2 (power flow)",
        "Added — wave M1 (substrate)", "Changed"]
mentions: {opf: 53, market: 24, multiperiod: 14, "N-1": 3, storage: 8, ramp: 9}
inProgress: false
```

Every internal link fetched 200 from the rendered page (`../`, `../manual/market/#settlement`,
`../manual/multiperiod/#settlement`); both `#settlement` anchor ids exist in the built HTML;
`highs.dev` and the GitHub commits URL return 200 by curl (they show as CORS failures when fetched
from inside the page).

**Where the content came from.** `git log` over `dcdc1c9..5fa3285` (M3) and `5fa3285..e88752c`
(M4) for what shipped in each wave, the manual pages for the substance, and the running package
for every symbol name. Not from the plans.

Symbol names verified against the live package rather than transcribed:

```
opf:      ['MultiperiodDuals', 'MultiperiodSolution', 'NonConvexCostError', 'OpfDcOptions',
           'gen_cost_coeffs', 'multiperiod_dc_opf', 'solve_dc_opf']
market:   ['MarketMultiperiodOptions', 'MarketNodalOptions', 'NonConcaveBidError',
           'NonConvexCostError', 'load_bid_coeffs', 'solve_multiperiod', 'solve_nodal']
jobs.kinds(): ['market.multiperiod', 'market.nodal', 'n1', 'opf.dc', 'pf.ac', 'pf.dc']
StorageDispatchResult: ['bus','charge_mw','discharge_mw','energy_bound_dual','id',
                        'power_limit_dual','soc_dual','soc_mwh']
MarketPeriodResult:    ['buses','congestion_rent','generators','loads','period','storage',
                        'total_generator_receipts','total_load_payment',
                        'total_storage_charge_payment','total_storage_discharge_revenue']
NetworkArrays load/storage: load_bus, load_ids, load_p_max_pu, load_p_min_pu,
                        storage_bus, storage_efficiency_charge, storage_efficiency_discharge,
                        storage_energy_pu, storage_ids, storage_p_max_pu, storage_soc_initial
```

Wave attribution checked with `git log -S` rather than guessed — e.g. `BusLmpResult`,
`OpfBranchFlowResult` and `ThermalViolation` all first appear in `d6d3ef5 feat(m3/S2)`, so they
are M3 entries; `gen_cost_coeffs` / `load_bid_coeffs` first appear in `ec4ba22 feat(m4/S4)` and go
public in `66ff908 feat(m4/R2)`.

**The PyPSA residuals in the M5 entry were re-measured at current HEAD, not copied** — the
sibling changed `opf/multiperiod.py` mid-fold, so restating the docstring constants would have
been a stale claim:

```
pypsa: ok optimal
objective rel:    4.3491662624249813e-13   (manual says 4.35e-13)
dispatch MW:      0.00030082881895054925   (3.01e-4)
storage net MW:   0.000109984242649519     (1.10e-4)
soc MWh:          0.00012498209407851846   (1.25e-4)
lmp $/MWh:        4.244263550390315e-05    (4.24e-5)
```

All five reproduce.

**One judgment call, flag it if you disagree.** I removed the per-wave `merged` / `in progress`
labels rather than correcting M2's. They are the defect itself: `docs/index.md:109-113` already
carries a roadmap table tracking exactly this, and the second copy is what went stale. Everything
under `## [Unreleased]` is unreleased by definition, and the intro paragraph now points at the
table. Putting labels back is a two-line change if you want them.

The changelog quotes **no** runtime output, so there is nothing on that page to go stale against
a snippet embed.

## D10 — report-only. The list, with wave attribution.

Nothing edited; all of it lives in `src/**`.

### `record/*.md` citations — 12 rendered, from 9 source lines

| Source | Cites | Wave | Renders on |
| --- | --- | --- | --- |
| `src/mambo_power/opf/dc_opf.py:12` | `record/m3-research.md` §1 | M3 | api/opf |
| `src/mambo_power/opf/dc_opf.py:49` | `record/m3-research.md` §1 | M3 | api/opf |
| `src/mambo_power/opf/dc_opf.py:92` | `record/m3-research.md` §2.3 | M3 | api/opf |
| `src/mambo_power/opf/dc_opf.py:270` | `record/m3-research.md` §2.3 | M3 | api/opf ×2, api/market ×3 |
| `src/mambo_power/opf/multiperiod.py:18` | `record/m5-research.md` §2.2 | **M5** | api/opf |
| `src/mambo_power/contingency/n1.py:11` | `record/m3-s1-report.md` | M3 | api/contingency |
| `src/mambo_power/contingency/n1.py:16` | `record/m3-research.md` §4 | M3 | api/contingency |
| `src/mambo_power/pf/dc.py:22` | `record/m2-research.md` §2 | M2 | api/pf |
| `src/mambo_power/numerics/roles.py:22` | `record/m2-research.md` §2 | M2 | *does not render* |

Rendered counts per page: opf 6, market 3, contingency 2, pf 1 = **12**, matching the review. The
inflation over the 8 rendering source lines is mkdocstrings re-rendering `NonConvexCostError`'s
docstring under several paths — `mambo_power.opf.NonConvexCostError`,
`mambo_power.opf.dc_opf.NonConvexCostError`, `mambo_power.market.NonConvexCostError`,
`mambo_power.market.nodal.NonConvexCostError`, `mambo_power.market.multiperiod.NonConvexCostError`.
**None of the market page's three is market-owned text.** Only **one** of the twelve is M5's.

### Bare internal step labels — ~48 rendered, not 3

Counted over the API pages with `<details class="quote">` source blocks stripped, so these are
prose, not code:

| Page | Count | Labels |
| --- | --- | --- |
| api/opf | 23 | W1, W2, W3, W4, W6 |
| api/results | 10 | W1, W3, W5 |
| api/market | 9 | `(S6)`, `(S7)`, R2 |
| api/pf | 8 | W1, W2, W3 |
| api/io-matpower | 4 | W1, W4 |
| api/jobs | 2 | W6 |
| api/numerics | 1 | W3 |
| api/contingency | 1 | `S1's` |

M5-owned: `opf/multiperiod.py` (W1, W2, W4), `market/multiperiod.py:14` (R2) and `:88` (`(S7)`),
`results/multiperiod.py` (W5). Everything else is M2/M3/M4 — `io/matpower.py`, `jobs/`,
`numerics/roles.py`, `pf/`, `opf/dc_opf.py`, `market/nodal.py:55` (`(S6)`) and `:71` (R2),
`contingency/n1.py:11` (`S1's`). Some read fine in context ("wave M5 W4", "ADR-004, W6"); the bare
ones — `(S7)`, `(S6)`, `M4/R2`, `S1's` — do not.

---

## Three things I fixed that were not on the list

All in files this half owns, all found while working the assigned items.

### `soc_dual`'s sign — the manual carried the exact defect `m5-fold-a` fixed in `src`

`docs/manual/multiperiod.md:153` said `soc_dual` is "the marginal value of one more MWh stored in
that unit at the end of that period". `c4de00c` corrected the same sentence in
`results/multiperiod.py`. Measured on the manual's own 2-period example:

```
t=0 lmp= 10.00 charge=16.6667 discharge=0.0000 soc_dual=-11.111111 energy_bound_dual=-33.888889
t=1 lmp= 50.00 charge=0.0000 discharge=13.5000 soc_dual=-45.000000 energy_bound_dual=+45.000000
```

`-11.111 = -10/0.9` charging, `-45.0 = -0.9 × 50` discharging: HiGHS's own row-dual sign, the
negative of the marginal value. The page now says so, gives both closed forms, quotes both
measured numbers off its own worked example, and says to read the worth of an MWh as `-soc_dual`.
`energy_bound_dual`'s "non-zero at either end" reading is documented alongside it.

### `Period.load_p_mw` "values must be `>= 0`" — two manual files, not one

`docs/manual/multiperiod.md:34` **and** `docs/manual/model.md:198`. Both now state `Load.p_mw`'s
own range with the case300 reason. Per your instruction the multiperiod page describes the
**fixed** bid behaviour; I verified it rather than taking the commit message for it, on case14
with `tests/_bids.py`:

```
load-2 base=21.7 t0=17.360 (0.8x=17.360)  t1=21.811 (1.2x=26.040)
load-3 base=94.2 t0=75.360 (0.8x=75.360)  t1=94.684 (1.2x=113.040)
```

The bound moved (t0 tracks the override exactly), and at t1 the bid curve chooses to serve less
than the moved bound — correct elastic behaviour, and the page describes it that way.

Negatives and non-finites re-checked against the landed validator:

```
identity profile on case300 accepted; 8 negative loads: ['load-51','load-207','load-250','load-281']
non-finite rejected: ValidationError
```

### `docs/manual/model.md`'s `BAD_RANGE` catalog was two waves behind

Missing the M5 rule (`ramp_up_mw` / `ramp_down_mw` must be `> 0` when given, shipped at `13aff40`)
and `m5-fold-a`'s new `Storage.p_max_mw` / `energy_mwh` `> 0` rules; the polynomial/piecewise
entries also mentioned only costs, not bids. The `Storage` field table did not mark either sizing
field. Enumerated against `src/mambo_power/model/network.py` and corrected.

---

## Unpinned surfaces

`docs/manual/multiperiod.md`'s hour-4 settlement figures (6305.178 / 6999.710 / 694.532) and the
2-period worked example's output block are hand-pasted from a run. That was already true before
this fold; I re-ran both and re-checked every digit, but nothing pins them. A `pymdownx.snippets`
embed is not available for them — they are prose-embedded fragments of a longer printout, the same
shape `docs/manual/jobs.md` had before `tests/unit/test_docs_registry_listing.py` pinned it. If
this class of staleness is worth closing generally, the jobs-manual test is the pattern.

Nothing else this fold wrote pastes runtime output. The changelog quotes none.

## Not done, deliberately

- Widening the T=1 test parametrization for audit finding 1 — `tests/unit/`, `m5-fold-a`'s.
- Editing any `src/**` docstring for D10 — reported above instead, as instructed.
