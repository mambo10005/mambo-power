# M5 walk — the multiperiod running surface, driven cold

Walker: fresh-eyes verification, wave M5 (`wave/05-multiperiod`, head `13aff40`), worktree
`C:\Claude Projects\mambo-power-m5`. I did not open the wave's spec, plan, research or step
reports; everything below comes from the shipped source, the built site, and running things.

Every claim carries the command that proves it. Where I could not reproduce something, it is
labelled `unverified`.

---

## 1. What I drove

**The built site, twice over.** I read the built HTML directly (`site/manual/multiperiod/index.html`,
`site/api/{market,opf,model,results}/index.html`, `site/design/architecture/index.html`,
`site/examples/index.html`, `site/index.html`, `site/changelog/index.html`) by stripping tags with a
small Python extractor, *and* I drove the site in a real Chrome via the chrome-devtools MCP tools.

I served the site over HTTP rather than opening `file://` URLs:

```
$ cd "C:/Claude Projects/mambo-power-m5/site" && python -m http.server 8777 --bind 127.0.0.1 &
$ curl -s -o /dev/null -w "%{http_code}\n" http://127.0.0.1:8777/design/architecture/
200
```

This matters. On `file://` the console fills with `'file:' URLs are treated as unique security
origins` and a 404 for `search/search_index.js`, and those errors are artifacts of the protocol, not
of the site. Serving over HTTP removes the confound, and none of those errors appear.

**The manual, followed as written.** I extracted the code blocks from the *built page* (not the
markdown) and ran them unmodified.

**The example.** `uv run --no-sync python examples/10_multiperiod_market.py`.

**The API, cold**, building scenarios from `mambo_power` / `mambo_power.model` only and trying to
break them the way a new user would.

**The test suite**, to establish the baseline: `uv run --no-sync pytest -q --no-header -p no:randomly`
-> **`800 passed, 10 warnings in 144.19s`, exit code 0.**

---

## 2. What worked

### 2.1 The manual's worked example reproduces character-for-character

I pulled the "Using it" snippet and the Jobs snippet out of the built HTML and concatenated them
into one file, changing nothing:

```
$ uv run --no-sync python .../manual_snippet.py
Optimal 2 3091.666667
t=0  lmp  10.0  charge 16.666667  discharge  0.000000  soc 15.000  surplus -0.000000
t=1  lmp  50.0  charge  0.000000  discharge 13.500000  soc  0.000  surplus 0.000000
508.333333 $ storage net revenue over the horizon
ok 2
EXIT=0
```

That is byte-identical to the two output blocks on the page, down to the `-0.000000` negative zero.
The closed-form claims in the surrounding prose check out too: `charge* = min(20, 15/0.9) = 16.6667`,
`discharge* = 0.81 x 50/3 = 13.5`, `profit = 50/3 x (40.5 - 10) = 508.3333`.

This is the single most reassuring thing I found. A docs snippet that still runs and still prints
what the page says it prints is rare.

### 2.2 The example runs clean and its numbers back the prose

```
$ uv run --no-sync python examples/10_multiperiod_market.py
EXIT=0
--- stderr ---
(empty)
```

24 periods, `status: Optimal`, horizon cost 172905.31 $. The cyclic condition closes exactly
(`77.700 MWh == soc_initial * energy_mwh = 77.700 MWh`), 7 of 24 hours have a binding branch rating,
and two ramp rows bind with duals of opposite sign (`-0.082157` at h13 up, `+0.082200` at h20 down),
exactly as the manual's sign-convention paragraph says.

The manual states, in prose: *"At hour 4 of that horizon the load pays 6308.385 $/h, the generators
receive 7011.653 $/h, and it is storage's 703.268 $/h charge payment that closes the gap."* The
example prints:

```
  4      6308.385    7011.653      703.268         0.000        0.000
```

All three figures match. "Drop the two storage columns and the same subtraction reads -703.268" is
borne out by the example's own line `(storage left unsettled: 703.268 $/h)`.

The docs gallery (`site/examples/index.html`) embeds the example's *source* via snippets and does not
paste an expected-output block, so there is no pasted output to have drifted. Good design; nothing to
check.

### 2.3 Navigation, links and diagrams

Nav reaches the new page — `Multiperiod market -> manual/multiperiod/` sits between `Nodal market`
and `Results` in the Manual section on every page.

I link-checked every internal `href` and every fragment across all 29 built pages with a script that
resolves directory URLs to `index.html` and checks the fragment against the target's `id=` set:

```
--- 42 bad link instances, 32 distinct, over 29 pages
```

Every one of those 42 is inside `site/404.html`, and none anywhere else:

```
$ python linkcheck-sources.py
['site\\404.html']
```

404.html uses site-root-absolute `/mambo-power/...` paths by design, which cannot resolve on a local
disk. **Outside 404.html: zero dead links, zero dead anchors.**

**No unrendered `:::` blocks anywhere** — `grep -rn ':::' site/manual/ site/api/ site/design/
site/examples/` returns nothing.

**The mermaid diagrams render.** I nearly filed this as a defect and was wrong, so the correction is
worth recording. My first probe reported both `.mermaid` elements as empty with no `<svg>`:

```json
{"n":2,"details":[{"tag":"DIV","hasSvg":false,"len":0},{"tag":"DIV","hasSvg":false,"len":0}],"svgInArticle":0}
```

That reading is meaningless. The theme's own code (in `site/assets/javascripts/bundle.d7400e89.min.js`)
does `let s = r.attachShadow({mode:"closed"}); s.innerHTML = n; e.replaceWith(r)` — the SVG lives in a
**closed** shadow root, which `querySelector` can never see. Measuring layout instead:

```json
[{"w":688,"h":415},{"w":688,"h":286}]
```

and a screenshot confirms both diagrams draw correctly, including the new `opf.multiperiod` node with
its `(ramp, SoC, cyclic rows)` caption. Mermaid itself is healthy: a hand-fed flowchart rendered to a
17,359-byte SVG in the same page context.

### 2.4 The architecture page tells the truth about the imports

The component diagram asserts `opfmp --> numerics`, `opfmp --> opf`, and `market --> {model, numerics,
opf, opfmp, results}`. Checked against the real imports:

```
$ grep -n '^from\|^import' src/mambo_power/opf/multiperiod.py
103:from mambo_power.numerics.arrays import NetworkArrays
104:from mambo_power.numerics.bbus import pf_shift
105:from mambo_power.numerics.ptdf import ptdf as compute_ptdf
106:from mambo_power.opf.dc_opf import (

$ grep -n '^from\|^import' src/mambo_power/market/multiperiod.py
51:from mambo_power.model import Network, Period, Scenario
52:from mambo_power.numerics.arrays import NetworkArrays
53:from mambo_power.opf import gen_cost_coeffs
54:from mambo_power.opf.dc_opf import (
61:from mambo_power.opf.multiperiod import MultiperiodSolution, multiperiod_dc_opf
62:from mambo_power.results import (
72:from mambo_power.market.nodal import load_bid_coeffs  # isort: skip
```

Every edge is real. The page's finer claim — *"it does not call `market.nodal`'s clearing, only its
`load_bid_coeffs` extractor, shared rather than copied"* — is literally true: line 72 imports exactly
that one name and nothing else.

### 2.5 The manual's checkable numbers are all correct

| Manual claim | How I checked | Result |
|---|---|---|
| Row-index table is "a contract of this module's own" | read `opf/multiperiod.py:643-664` | offsets match the table exactly: `flow_base = n_periods`, `soc_base = flow_base + T*n_branch`, then `limit_base`, `cyclic_base`, `ramp_base` in that order |
| g_shunt zero on every fixture "except case300, max 0.0014 pu" | summed `Shunt.g_mw` over all 6 fixtures | only case300 non-zero; `max abs(g_mw) = 0.14 MW / 100 base = 0.0014 pu` |
| PyPSA oracle rates "the 17 Line and the 3 Transformer components of case14" | counted case14 branches | 20 branches = 17 lines + 3 transformers |
| profile is trough 0.7x at hour 4, peak 1.2x twelve hours later | example output vs case14 total load 259.0 MW | h4 = 181.30 (259 x 0.7), h16 = 310.80 (259 x 1.2) |
| storage sized 38.85 MW / 155.4 MWh on case14 | example output | `38.85 MW / 155.40 MWh` |
| `market.solve_nodal` "ignores `Scenario.periods` entirely" | called it on a 2-period scenario | `Optimal`, served the network's own 20.0 MW base load |
| entry point is `solve_multiperiod(scenario, options=None)` | `inspect.signature` | `(scenario: 'Scenario', options: 'MarketMultiperiodOptions \| None' = None) -> 'MarketMultiperiodResult'` |

`MarketMultiperiodOptions` has no fields, which surprised me until I read its docstring — it explains
exactly why, and the reasoning is sound. Not a defect.

### 2.6 Math typesets; six equations, six containers

All 6 `.arithmatex` blocks on the multiperiod page produce an `<mjx-container>`, and the article
contains zero un-typeset `\[` or `\(` delimiters. MathJax loads from
`https://unpkg.com/mathjax@3.2.2/es5/tex-mml-chtml.js`. (What it typesets is not entirely right — see
defect 6.)

### 2.7 Error messages name the offending id

This was the part I most expected to find wanting, and it is the strongest part of the surface.

| What I did wrong | What I got back |
|---|---|
| `Period(load_p_mw={"ld9": 50.0})` against a network with no `ld9` | `ValidationError` ... `periods reference load id(s) not present in network.loads: ['ld9']` |
| `Period(load_p_mw={"ld2": -5.0})` | `load_p_mw values must be >= 0, got {'ld2': -5.0}` |
| `Scenario(periods=[])` | `List should have at least 1 item after validation, not 0` |
| `ramp_up_mw=0.0` | `BAD_RANGE at generators[0].ramp_up_mw: generator "g1": ramp_up_mw must be > 0 when given, got 0.0` |
| `ramp_up_mw=-5.0` | same message, `got -5.0` |
| `soc_initial=1.5` | `BAD_RANGE at storage[0].soc_initial: storage "st2": soc_initial must be in [0, 1], got 1.5` |
| `efficiency_discharge=0.0` | `storage "st2": efficiency_discharge must be in (0, 1], got 0.0` |
| storage on a non-existent bus | `DANGLING_REF at storage[0].bus: storage "st2": bus references missing bus "b9"` |

Every one names the offending id and the offending field path. The efficiency check correctly uses
the half-open `(0, 1]` interval, which is what stops a divide-by-zero in the `discharge/eta_d` term of
the SoC row.

Genuinely infeasible horizons come back as data, not exceptions, exactly as documented:

```
CASE: ramp of 1 MW/h against a 130 MW jump (infeasible horizon)
  NO RAISE -> status='Infeasible' message="multiperiod_dc_opf: HiGHS reported model status 'Infeasible'"

CASE: storage must discharge but cyclic row demands it end full
  NO RAISE -> status='Infeasible' message="multiperiod_dc_opf: HiGHS reported model status 'Infeasible'"
```

---

## 3. What did not work

Nothing in the *runtime* failed. Every defect below is in the documentation layer — but four of them
tell a new user something false about what the code does, and three of those are on the public API
page for the very types this wave introduced.

---

## 4. Defects, ranked by harm to a new user

### D1 — HIGH — The changelog stops at M2, and calls M2 "in progress"

The site's changelog opens with *"All notable changes to mambo-power are recorded here."* It has
exactly three content headings:

```
$ python heading-dump.py site/changelog/index.html
  h1 Changelog
  h2 Unreleased
  h3 Added — wave M2 (power flow), in progress
  h3 Added — wave M1 (substrate), merged
  h3 Changed
```

There is no M3, no M4, no M5:

```
$ grep -n -i 'M3\|M4\|M5\|opf\|market\|multiperiod\|contingency\|n-1\|storage\|ramp' docs/changelog.md
74:  `PolynomialCost` / `PiecewiseCost`), `Load`, `Shunt`, `Storage`, `Zone`, `Geo`. Physical
$ wc -l docs/changelog.md
112 docs/changelog.md
```

The single hit is the M1 entity list. In 112 lines the changelog never mentions optimal power flow,
N-1 screening, the nodal market, multiperiod clearing, ramp limits or storage dispatch.

Meanwhile the home page says M1-M4 "are all merged".

Why this ranks first: the changelog is in the nav on **every page**, it is the conventional place a
new user looks to learn what a project can do, and it currently reports that the newest work is power
flow and still in progress. It is not merely incomplete — it is affirmatively misleading, and it is
the one page whose entire purpose is not to be.

This is not solely M5's doing; M3 and M4 skipped it too. But M5 also shipped without touching it, and
the walk is about the surface as it stands.

### D2 — HIGH — The API page for `Period` says nothing reads its only field

`site/api/model/index.html:3613`, rendered from the class docstring:

> `load_p_mw` is an id-keyed override of each `Load`'s `p_mw` for this period, not a scale factor: a
> load id absent from the dict falls back unchanged to that `Load`'s own `p_mw` (solver-side
> behaviour; **nothing reads this field yet, wave M5 Design item 1**).

`Period.load_p_mw` is the entire input surface of this wave. The API reference for the wave's headline
new type tells the reader the field is inert. A user who consults the API reference before the manual
— a normal order — is told the feature does not exist.

The sentence also leaks internal planning vocabulary ("wave M5 Design item 1") into published docs,
naming a document the reader has no access to.

### D3 — HIGH — The `Storage` docstring says no solver reads it

`src/mambo_power/model/entities.py:174`, rendered on the same public page:

```python
class Storage(_Entity):
    """Energy storage. Schema-present; no M1 solver reads it."""
```

The multiperiod manual devotes a whole section to the opposite: *"`model.Storage` has been in the
schema since M1 and solver-ignored ever since. This is the wave that reads it."* The architecture
page's ownership table gets it right too — "model.Storage (M1, solver-read from M5)". Only the
docstring — the thing a reader sees from `help(Storage)` and from the API page — still says the field
is dead.

### D4 — HIGH — The `Load` docstring says only `market.nodal` reads `bid` — proved false

```python
class Load(_Entity):
    """Fixed demand at a bus. ``bid`` is model-present; only ``market.nodal`` reads it."""
```

`market.solve_multiperiod` reads it. I gave one load a `PolynomialBid` valuing energy at 30 $/MWh
against an 80 $/MWh generator and cleared a 2-period horizon:

```
no bid (fixed load)                                        status=Optimal    served_t0=[50.0] obj=8000.0
elastic bid: value 30 $/MWh (below the 80 $/MWh gen)       status=Optimal    served_t0=[0.0] obj=0.0
```

The bid changed the answer completely — the load was curtailed to zero because its stated value is
below the marginal cost of serving it. The manual is aware of this (it says
`market.nodal.load_bid_coeffs` supplies the bids, shared rather than copied, and that the degeneracy
case holds "with elastic bids in play"). Only the docstring is stale, and it steers users away from a
working feature.

### D5 — MEDIUM — The Errors section names an exception that will not be caught

The multiperiod manual's Errors section says:

> `solve_multiperiod` additionally raises `ValueError` up front for a ramp limit of exactly zero.

and earlier:

> A ramp limit of exactly 0 is rejected with a `ValueError` before any solve.

Two things are wrong.

**The type.** What is raised is `NetworkValidationError`, and that class deliberately does not inherit
from `ValueError`:

```
NetworkValidationError is a ValueError? False
NetworkValidationError MRO: ['NetworkValidationError', 'Exception', 'BaseException', 'object']
```

This is not an accident, and the site says so on the very same API page:

> Subclasses `Exception` rather than `ValueError` **on purpose**: pydantic-core converts any
> `ValueError` raised inside a validator into its own `ValidationError`, which would hide `.issues`
> behind a generic message.

So a reader who writes `except ValueError:` from the manual's instruction gets an uncaught exception,
and the site contradicts itself between two pages.

**The raiser.** The check lives in `src/mambo_power/model/network.py:176-182`, inside network
validation:

```python
for field in ("ramp_up_mw", "ramp_down_mw"):
    ramp: float | None = getattr(gen, field)
    if ramp is not None and not ramp > 0:
        add("BAD_RANGE", f"generators[{index}].{field}",
            f'generator "{gen.id}": {field} must be > 0 when given, got {ramp}')
```

`grep -rn 'ramp' src/mambo_power/market/multiperiod.py src/mambo_power/opf/multiperiod.py` finds no
zero-check at all in either multiperiod module. You can never reach `solve_multiperiod` with a
zero ramp — `Network(...)` refuses to construct first. The manual's "up front ... before any solve"
framing misplaces the guard by a layer, so a reader looking for it in the solver will not find it.

Minor addendum: the guard also rejects *negative* ramps, which the manual does not mention.

### D6 — MEDIUM — Literal backslashes in 4 of the 6 display equations

The ramp constraint — the defining formula of the wave — renders on screen as:

> −ramp\\_down\\_mw_g ≤ p_g[t] − p_g[t−1] ≤ ramp\\_up\\_mw_g.

with the backslashes visible. Confirmed by screenshot and by reading the typeset MathML:

```json
[{"typeset":true,"text":"−ramp\\_down\\_mwg≤pg[t]−pg[t−1]≤ramp\\_up\\_mwg."},
 {"typeset":true,"text":"charge[t]+discharge[t]≤p\\_max\\_mw,"},
 {"typeset":true,"text":"soc[t]−soc[t−1]−ηccharge[t]+discharge[t]ηd=0,"},
 {"typeset":true,"text":"soc[T−1]=soc\\_initial×energy\\_mwh,"}, ...]
```

Cause is `\_` inside `\text{}`, which MathJax v3 emits literally:

```
$ grep -rn '\\text{[^}]*\\_' docs/
docs/manual/multiperiod.md:107:-\text{ramp\_down\_mw}_g \;\le\; p_g[t] - p_g[t-1] \;\le\; \text{ramp\_up\_mw}_g .
docs/manual/multiperiod.md:139:\text{charge}[t] + \text{discharge}[t] \;\le\; \text{p\_max\_mw} ,
docs/manual/multiperiod.md:159:\text{soc}[T-1] = \text{soc\_initial} \times \text{energy\_mwh} ,
docs/manual/multiperiod.md:234:= -\sum_k \mu_k f_k + \sum_k \mu_k \,\text{pf\_shift}_k - \sum_n \text{LMP}_n\, g_{\text{shunt},n}
docs/manual/n1.md:34:\text{estimated}[l] = \bigl|\, \text{base\_flow}[l] + \text{LODF}[l, k] ...
```

The pattern is pre-existing — the N-1 page has one instance, and it renders the same way
(`estimated[l]=|base\_flow[l]+LODF[l,k]⋅base\_flow[k]|`, verified in-browser). This wave added four
more, including the two a reader of this page cannot avoid seeing. The equations are still legible,
which is why this sits below the docstrings, but on the page whose whole job is to explain a new
mathematical formulation, formulas that look broken undermine the argument.

### D7 — MEDIUM — Negative storage sizing passes validation and fails opaquely

Storage validation (`src/mambo_power/model/network.py:229-243`) checks `soc_initial` and both
efficiencies, with the excellent messages quoted in §2.7. It does not check `energy_mwh` or
`p_max_mw`:

```
CASE: Network with Storage(energy_mwh=-1.0)
  NO RAISE -> network built OK
```

Nor does anything downstream diagnose it. A typo'd sign produces:

```
CASE: energy_mwh=-1.0
  RETURNED status='Infeasible' message="multiperiod_dc_opf: HiGHS reported model status 'Infeasible'" n_periods=2 len(periods)=0
CASE: p_max_mw=-5.0
  RETURNED status='Infeasible' message="multiperiod_dc_opf: HiGHS reported model status 'Infeasible'" n_periods=2 len(periods)=0
```

The user gets no unit id, no field name, and an "Infeasible" that reads as a modelling problem rather
than a data-entry problem. Given how good the neighbouring checks are, this gap is conspicuous: three
of five numeric `Storage` fields are range-checked and two are not.

`Generator.p_max_mw` has the same shape of gap — only `p_min_mw > p_max_mw` is checked
(`network.py:164`) — pre-existing, out of this wave's scope, noted for completeness.

### D8 — LOW — A test helper justifies itself with a design that was abandoned

`tests/_storage.py:32` explains its siting rule:

> the bus most likely to sit behind a congested branch during its own peak hour
> (``tests/_periods.py``'s own **two-archetype profile**).

`tests/_periods.py:10` says that design is gone:

> **A single system-wide curve, not two phase-shifted archetypes — and why the first design was
> wrong.** ... any per-load *divergence* from the network's own base-case load ratios ... makes the
> 24-period LP genuinely infeasible

The manual agrees with `_periods.py` ("An earlier design used two phase-shifted archetypes for
locational diversity and had to be abandoned"). So `_storage.py`'s stated rationale now rests on a
profile that does not exist. The siting rule itself is fine; only its justification is stale. Reader
impact is limited to contributors reading the test helpers, which is why it ranks low — but it is
exactly the kind of thing that silently misleads the next person to change the fixture.

### D9 — LOW — The flagship example has the property the manual warns about

The manual argues carefully that equal efficiencies are dangerous:

> deliberately asymmetric efficiencies (0.92 / 0.88, round-trip 0.8096) — an equal pair is exactly the
> shape under which transposing the two efficiencies in the SoC row is a silent no-op.

`tests/_storage.py` honours that (`EFFICIENCY_CHARGE = 0.92`, `EFFICIENCY_DISCHARGE = 0.88`). But
`examples/10_multiperiod_market.py:56-57` uses `efficiency_charge=0.95, efficiency_discharge=0.95`,
and the example prints it:

```
storage st-1 at bus-3: 38.85 MW / 155.40 MWh, round trip 0.9025
```

The manual points readers at this example ("See `10_multiperiod_market.py` for the full 24-hour
version on case14"), so the one storage configuration most readers will actually see and copy is the
symmetric one the manual singles out as the blind spot. No correctness impact — the example is not a
test — but it undercuts the manual's own argument for a reader who notices.

### D10 — LOW — Public API pages cite documents that were never published

```
$ grep -rno 'record/[a-z0-9-]*\.md' site/ --include=*.html
api/opf/index.html:5753: record/m5-research.md
api/opf/index.html:5026: record/m3-research.md
api/pf/index.html:3021:  record/m2-research.md
api/contingency/index.html:1888: record/m3-s1-report.md
... (12 instances total)
```

Rendered, this reads: *"`record/m5-research.md` §2.2 describes the variable vector as T per-period
blocks concatenated..."* — a citation to a file that is not on the site and not in the package. The
same pages carry bare internal step labels: `(S7)` on `MarketMultiperiodOptions`, `W1` and `W3`
elsewhere. Pre-existing pattern from M2/M3; M5 added one more instance. Each is a dead end for a
reader who tries to follow it.

### Nit, unranked

The manual says of an uncongested hour: *"the surplus must be exactly zero — and it is."* The example
prints `largest surplus over the 17 uncongested hours: 1.146e-10 $/h`. At the page's own display
precision this is invisible, and the snippet's `-0.000000` is consistent with it, so this is a wording
looseness rather than a wrong number.

---

## 5. Summary table

| # | Severity | Defect | Where |
|---|---|---|---|
| D1 | HIGH | Changelog stops at M2, labelled "in progress"; no M3/M4/M5 | `docs/changelog.md` |
| D2 | HIGH | `Period` docstring: "nothing reads this field yet" | `model/entities.py`, `site/api/model/index.html:3613` |
| D3 | HIGH | `Storage` docstring: "no M1 solver reads it" | `model/entities.py:174` |
| D4 | HIGH | `Load` docstring: "only `market.nodal` reads" `bid` — false | `model/entities.py` |
| D5 | MEDIUM | Errors section: wrong exception type and wrong raiser | `docs/manual/multiperiod.md` |
| D6 | MEDIUM | Literal `\_` in 4 of 6 display equations | `docs/manual/multiperiod.md:107,139,159,234` |
| D7 | MEDIUM | `Storage.energy_mwh` / `p_max_mw` accept negatives | `model/network.py:229-243` |
| D8 | LOW | Helper cites the abandoned two-archetype profile | `tests/_storage.py:32` |
| D9 | LOW | Example uses the symmetric efficiencies the manual warns about | `examples/10_multiperiod_market.py:56-57` |
| D10 | LOW | API pages cite unpublished `record/*.md` and step labels | `site/api/{opf,pf,contingency,market}` |

---

## 6. The walker's overall read

The engineering is sound and the manual is unusually honest — it discloses the oracle's two limits,
names the case where its own settlement identity is narrower than its field name, and explains why
simultaneous charge and discharge is bounded rather than banned. Its worked example still runs and
still prints what it says it prints, which is the strongest single signal I can give you.

The gap is entirely at the seam between the manual and everything else. The manual knows storage is
read now, that `Period.load_p_mw` drives the horizon, and that multiperiod consumes bids. The
docstrings on those three types — which are what a user meets first through `help()`, an IDE tooltip,
or the API reference — each still describe the world before this wave. And the changelog describes the
world three waves ago. Fix D1-D4 and the surface stops contradicting itself; everything else is
polish.
