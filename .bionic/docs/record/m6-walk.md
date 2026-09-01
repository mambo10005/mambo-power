# M6 walk — the running surface, driven cold

Walker: fresh-eyes verification. Worktree `C:\Claude Projects\mambo-power-m6`, branch
`wave/06-zonal-redispatch`. 2026-08-27, ~10:45–11:55 PDT.

**Provenance — which site directory I actually read.** The walk was driven against head
`e58fff6` and against a `site/` **I built myself** at 10:46 (see §0 — `mkdocs` was not
installed in the worktree venv, so I used an ephemeral overlay). Two commits landed on the
branch while I was walking, moving the head to `d0ce957`:

```
$ git log --oneline e58fff6..HEAD
d0ce957 docs(m6/S7b): note the market.agents collision ahead of time
2952047 docs(m6/S8): example 04's unknown-kind demo uses market.agents, matching jobs.md
```

and `site/` was rebuilt by another agent in the meantime, so the directory on disk is no
longer the one I read. After the docs group was installed I rebuilt with the documented
command at `d0ce957` and **re-verified every finding below against that fresh build and
that new head**. All nine hold unchanged. The two new commits are about the `market.agents`
placeholder-kind name and touch none of them; the only built page whose content they change
is `manual/jobs`, additively (a paragraph about which files a future wave must move
together), and the sentence D1 turns on is still there verbatim. Example 11's output at the
new head is byte-identical to the run this record is built on.

**Modality.** Both. I parsed the rendered HTML with my own extractor for every page listed
below, and I additionally drove `manual/zonal` in a **real browser** (chrome-devtools MCP
against a local `python -m http.server` on 127.0.0.1:8099) to settle whether MathJax and
mermaid actually render, which HTML parsing cannot answer.

**Teardown.** The server was stopped and the port verified clear before I finished:

```
$ Get-NetTCPConnection -LocalPort 8099 -State Listen | Stop-Process -Id $_.OwningProcess -Force
killing pid 56448
port 8099 clear
```

The browser page was closed (`close_page` → "the previously selected page was closed").

---

## 0. Building the site

The documented command does not work in this worktree. `mkdocs` is not installed in
`.venv` — the `docs` dependency group is not synced, and I was told not to sync:

```
$ uv run --no-sync mkdocs build --strict
error: Failed to spawn: `mkdocs`
  Caused by: program not found

$ .venv/Scripts/python.exe -m mkdocs --version
No module named mkdocs
```

I built with an ephemeral overlay instead, which leaves the project env untouched:

```
$ uv run --no-sync --with mkdocs-material --with "mkdocstrings[python]" \
      --with pymdown-extensions mkdocs build --strict
INFO    -  Cleaning site directory
INFO    -  Building documentation to directory: C:\Claude Projects\mambo-power-m6\site
INFO    -  Documentation built in 12.72 seconds
```

Zero warnings under `--strict`. `site/` is authoritative for everything below.

**Resolved mid-walk.** The team lead ran `uv sync --all-groups` in the worktree while I was
writing this up; `mkdocs` 1.6.1 is now in that venv and the documented command works:

```
$ uv run --no-sync mkdocs --version
mkdocs, version 1.6.1 from C:\Claude Projects\mambo-power-m6\.venv\Lib\site-packages\mkdocs
$ uv run --no-sync mkdocs build --strict
INFO    -  Documentation built in 24.56 seconds
```

Also clean under `--strict`, and it is the build every finding was re-verified against.

This is a worktree/environment fact, not a wave defect — CI runs `uv sync --locked
--all-groups` first (`.github/workflows/ci.yml:146`), and `docs/contributing.md`'s
"Building the docs locally" section does say `uv sync --all-groups` before
`uv run mkdocs`. But the checklist earlier on that same page lists
`uv run mkdocs build --strict` alongside ruff/mypy/pytest with no sync line, and
`pyproject.toml` has no `default-groups`, so a contributor running that checklist
top-to-bottom on a fresh clone fails on the last line only. Filed as **D8** below.

---

## 1. What I drove

| Surface | How |
|---|---|
| `site/manual/zonal/`, `manual/jobs/`, `manual/market/`, `manual/results/` | parsed HTML; zonal also in a browser |
| `site/api/{market,opf,results}/`, `design/{architecture,decisions}/`, `examples/`, `changelog/`, `index.html` | parsed HTML |
| `examples/11_zonal_redispatch.py` | run |
| The manual's "Using it" snippet | run verbatim |
| The manual's `cap_mw=30.0` variant claim | run |
| Cold API: 2-zone scenario from `from mambo_power import ...` + docs only | 14 error probes |
| `jobs.run` with `kind="market.zonal"` | 8 probes incl. exact JSON round-trip |
| Three comparison figures + settlement identity | hand-computed from the result's own rows, two scenarios |
| Internal links/anchors, all 30 built pages | checked |
| `tests/unit` | run |

---

## 2. What worked

### Example 11 — exit 0, and every quoted number matches

```
$ uv run --no-sync python examples/11_zonal_redispatch.py
EXIT=0     real 0m0.828s
```

Cross-checking the manual's prose against that run, number by number:

| Manual says | Run prints | |
|---|---|---|
| corridor caps 1.524 / 16.577 / 19.456 MW | `1.524` / `16.577` / `19.456` | ✅ |
| zone prices 3.759145 / 3.880504 / 3.759147 | identical | ✅ |
| corridor flows +1.5237 / +15.3588 / −19.4562 | identical | ✅ |
| capacity prices 0.121359 / 0.000000 / 0.121356 | identical | ✅ |
| "17 of case30's 41 branches over rating" | `17 of 41 branches over rating` | ✅ |
| "worst overload 11.85 MW" | `worst  11.8468 MW` | ✅ |
| "none under the redispatched one" | `0 of 41` | ✅ |
| "moves 21.9 MW up and the same down across all six generators" | `+21.933 MW up / -21.933 MW down across 6 of 6` | ✅ |
| `redispatch_payment` 14.637 $/h | `+14.636683` | ✅ |
| `generation_cost_gap` −14.637 $/h | `-14.636683` | ✅ |
| settlement prints `31.694262 31.694262` | identical | ✅ |
| "residual of 1.066e-13 $/h" | `residual: 1.066e-13 $/h` | ✅ |
| "6 branches sit at rating, only 4 are priced" | identical | ✅ |
| "28 of 30 buses agree to 5.2e-06; two differ by 0.917" | identical | ✅ |

The examples gallery embeds source only, with no output block — uniform across all eleven
examples, so there is no printed output there to drift out of date. The gallery's prose
blurb for §11 ("overloading 17 real branches") matches.

### The manual's own snippet, run verbatim

Copied the "Using it" block out of the rendered page and ran it unmodified:

```
Optimal [('A', 10.0), ('B', 50.0)]
[('genA', 70.0), ('genB', 10.0)]
[('genA', 70.0), ('genB', 10.0)]
0.0 0.0
```

Byte-identical to the documented output. The follow-on claim in the same section — that
`cap_mw=30.0` against the same 20 MW branch gives `redispatch_payment = 400.0`,
`generation_cost_gap = -400.0`, `welfare_gap = 0.0`, with the zonal stage pricing both
zones at 10.0 and handing genA all 80 MW — is exact:

```
Optimal [('A', 10.0), ('B', 10.0)]
[('genA', 80.0), ('genB', 0.0)]        <- zonal
[('genA', 70.0), ('genB', 10.0)]       <- final (10 MW moved back)
400.0 -400.0     welfare_gap 0.0
```

### The three figures, hand-computed from the result's own rows

I built my own 2-zone/3-bus scenario with an elastic load and computed each figure from
its published definition, using nothing but the result object:

```
redispatch_payment   reported +400.000000000   hand +400.000000000   diff 0.000e+00
generation_cost_gap  reported -400.000000000   hand -400.000000000   diff 0.000e+00
welfare_gap          reported +0.000e+00       hand +0.000e+00
welfare(zonal)-welfare(final) = +400.000000000   (manual says == redispatch_payment)  ✅
```

Then a second scenario where demand actually moves (corridor oversold into a zone whose
only local generator is expensive, so redispatch must curtail):

```
zonal  gens [('genA', 90.0), ('genB', 0.0)]  loads [('loadA', 50.0), ('loadB', 40.0)]
final  gens [('genA', 55.0), ('genB', 0.0)]  loads [('loadA', 50.0), ('loadB',  5.0)]
hand redispatch_payment = (550.0-900.0)+(1200.0-150.0) = +700.000000 ; reported +700.000000
welfare_gap +0.000e+00   generation_cost_gap +350.000000
```

Note that here `redispatch_payment` (+700) and `generation_cost_gap` (+350) are genuinely
independent, which is exactly what the manual's parenthetical promises happens "with bids
in play" — on the fixed-load case30 fixture they are exact negatives. Verified.

The netting identities hold exactly on both sides of the market:

```
netting gen  genA: p0 +90.000000 + up 0.000000 - down 35.000000 = 55.000000 (final 55.000000)  product 0.0e+00
netting load loadB: d0 40.000000 + restore 0.000000 - curtail 35.000000 = 5.000000 (final 5.000000)  product 0.0e+00
```

### The settlement identity closes from the result object alone

Using only `result.buses`, `result.loads_final`, `result.generators_final` and
`result.branches` — nothing from `numerics/` or `opf/`, no second solve, as the manual
claims:

```
mine:    settlement 800.000000 vs 800.000000   residual 0.00e+00
case30:  load payment 762.6075 - generator receipts 730.9132 = 31.694262 $/h
         -sum_k(mu_k * flow_k) over 4 binding branches = 31.694262 $/h
         residual: 1.066e-13 $/h
```

### Corridor sign convention — manual, docstring and code agree three ways

The manual: keys normalised to sorted order (z1 < z2), positive means z1 → z2, the column
enters z1's balance row as a withdrawal and z2's as an injection. The `opf.zonal` module
docstring says the same with the coefficients spelled out (−1 / +1). The code:

```python
# src/mambo_power/opf/zonal.py:449-451
for c, (z1, z2) in enumerate(corridor_ids):
    outbound[zone_pos[z1]].append(int(corridor_cols[c]))  # positive f leaves z1 ...
    inbound[zone_pos[z2]].append(int(corridor_cols[c]))   # ... and arrives in z2
```

And the observable consequence the manual predicts — corridor (2,3) binding at −19.456 MW
with a *positive* capacity price 0.121356 — is what the example prints.

### Errors: every message names the offending thing

14 probes. The manual's errors table is accurate on every row I drove. Verbatim:

```
corridor names a zone that does not exist
  ValueError: corridor key ('A', 'Z') names zone 'Z', which no bus is assigned to (zones present: ['A', 'B'])
corridor names the same zone twice
  ValueError: corridor key ('A', 'A') names the same zone twice -- a corridor joins two *distinct* zones
             (an intra-zone tie is not modelled: a zone is a copper plate)
same pair twice, both orders
  ValueError: zone pair ('A', 'B') appears twice in corridors (once as ('B', 'A')) -- a corridor is keyed
             by an *unordered* pair, so give it exactly once
buses carry no zone
  ValueError: 3 of 3 in-service buses carry no zone (first: "bus1") -- a zonal clearing needs every bus
             assigned to exactly one zone. Set Bus.zone (every MATPOWER import populates it from the ZONE column).
negative cap_mw
  pydantic ValidationError: cap_mw / Input should be greater than or equal to 0
Bus.zone naming a Zone not in Network.zones
  NetworkValidationError: DANGLING_REF at buses[2].zone: bus "bus3": zone references missing zone "Q"
  isinstance ValueError: False        <- the manual warns about exactly this; correct
load bigger than every generator combined
  NO RAISE. status='Infeasible'
  message="zonal clearing stage: zonal_dc_opf: HiGHS reported model status 'Infeasible'"
  every row list empty, every figure 0.0     <- matches the manual's stated shape exactly
```

These are unusually good error messages. Every one names the key, the offending value and
the set of legal values.

### Links, math, diagrams, tests

- **Internal links**: 30 built pages, **zero** dead links and **zero** missing anchors.
  (My checker reported 39 problems; all 39 are on `404.html` and are the absolute
  `/mambo-power/` GitHub Pages prefix, correct in production.)
- **Browser** on `manual/zonal`: 64 rendered `mjx-container` elements, **zero** raw TeX
  occurrences in visible text, zero visible backslashes; the mermaid flowchart draws
  (screenshot confirms boxes, edges and edge labels). Sole console error is a 404 on
  `api.github.com/repos/mambo10005/mambo-power/releases/latest` — the theme's release
  widget, repo has no releases. `mermaid@11.17.2` and MathJax both load 200.
- **Jobs**: exactly 7 kinds; `SolveRequest` JSON round-trip identical; `market.zonal`
  returns a `MarketZonalResult` through `jobs.run`; the manual's "seven as of M6" is right.
- **Architecture page and home roadmap** are current for M6; the on-disk module map in
  `design/architecture` matches `ls src/mambo_power/{opf,market,results}` exactly.
- `uv run --no-sync python -m pytest tests/unit -q` → **719 passed in 30.28s**, exit 0.

---

## 3. Defects, ranked by what would hurt a new user

### D1 — HIGH. Caller mistakes on `market.zonal` are reported as library bugs

Four distinct *user data* errors come back through the jobs surface as `INTERNAL`:

```
$ uv run --no-sync python scratchpad/jobs2.py
valid corridor                             -> ok
negative cap (field constraint)            -> failed BAD_OPTIONS  options for kind "market.zonal" are invalid...
unknown option key                         -> failed BAD_OPTIONS  ...Extra input
cap_mw = inf                               -> failed BAD_OPTIONS  ...
corridor names a missing zone              -> failed INTERNAL     ValueError: corridor key ('A', 'Z') names zone 'Z'...
corridor names same zone twice             -> failed INTERNAL     ValueError: corridor key ('A', 'A') names the same zone twice...
same pair twice, both orders               -> failed INTERNAL     ValueError: zone pair ('A', 'B') appears twice in corridors...
buses carry no zone                        -> failed INTERNAL     ValueError: 3 of 3 in-service buses carry no zone...
```

The jobs manual's own error table defines `INTERNAL` as:

> Anything else the runner raised (singular matrix, **a bug**): "ExceptionType: message".

and defines `BAD_OPTIONS` as "options did not validate against the kind's options model".
So four ordinary caller mistakes are reported to a service as *"the library has a bug."*

Worse, the jobs manual's zonal paragraph states the opposite outcome explicitly:

> `jobs.run` validates it the same way as every other kind's options — **a corridor naming
> a zone the network has no bus assigned to is caught before any solve is attempted** — and
> its three-stage chain ... reports whichever stage first failed to reach Optimal through
> the same `INFEASIBLE_LP` / `UNBOUNDED_LP` translation the other market kinds use.

That sentence is the one I tested first, and it is the one that does not hold in the way a
reader will take it. A service author reading it will map `INTERNAL` to a 5xx and a pager,
and every customer who fat-fingers a zone name will page them.

The underlying cause is legitimate and hard: `CorridorLimit` cannot validate a zone name
because the options model has no access to the network. So this is a classification gap,
not a validation gap — the errors themselves are excellent (see above). The fix is either a
code change (catch these as `BAD_OPTIONS`/a dedicated code in the runner) or a doc change
(say plainly that cross-model corridor errors arrive as `INTERNAL`). Right now the docs
promise the first and the code does the second.

**Why it ranks first:** it is the only finding that would cause a downstream system to
behave wrongly rather than merely leave a reader uninformed.

### D2 — MEDIUM-HIGH. `MarketZonalResult`'s field names are published nowhere

The zonal manual's centrepiece section is *"Settlement, from the result object alone"*,
and its whole argument is field access: `b.lmp`, `ld.p_mw`, `g.bus`, `br.flow_limit_dual`,
`br.p_from_mw`. A reader who wants the rest of the object goes to `api/results`. There are
no fields there. Not for `MarketZonalResult`, and not for any result type on the site:

```
$ grep -o 'id="mambo_power\.results\.[A-Za-z]*\.[a-z_]*"' site/api/results/index.html | sort -u
id="mambo_power.results.PowerFlowResultBase.to_arrays"
```

One entry, and it is a method. Compare the same query against `api/opf`, where the
`opf.zonal` types are plain dataclasses:

```
id="mambo_power.opf.zonal.ZonalDuals.corridor_cap"
id="mambo_power.opf.zonal.ZonalSolution.corridor_flow_mw"
id="mambo_power.opf.zonal.ZonalSolution.corridor_ids"
... (13 entries, each with its description)
```

So dataclasses under `opf/` render their attributes and pydantic `BaseModel`s under
`results/` do not. The carefully written `Field(description=...)` text in
`src/mambo_power/results/zonal.py` — which is genuinely good, including the properly
hedged `redispatch_payment` description — reaches the site only inside
`show_source: true` code blocks, where it is syntax-highlighted Python, not documentation.

Concretely, `delta_restore_mw` and `delta_curtail_mw` occur **zero times** in the entire
built site:

```
$ grep -rl 'delta_restore_mw' site --include=*.html
(nothing)
$ grep -rl 'delta_curtail_mw' site --include=*.html
(nothing)
```

Three things compound this into a real trap rather than a gap:

1. The zonal manual's *"Reported deltas are netted"* section names `MarketZonalResult` and
   then states the identity purely in generator vocabulary: "`delta_up = max(u, 0)`,
   `delta_down = max(-u, 0)` — so that `final == p0 + delta_up - delta_down`". On loads
   those attributes do not exist. Following the manual, I wrote
   `l.delta_up_mw` for a load row and got
   `AttributeError: 'LoadRedispatchResult' object has no attribute 'delta_up_mw'`.
   The changelog's M6 entry repeats the same generator-only phrasing.

2. `Manual › Results` — the page in the nav directly *after* `Zonal market`, and the
   obvious place to look — has one section per result type and stops at
   `MarketNodalResult`. There is no `MarketMultiperiodResult` section (M5) and no
   `MarketZonalResult` section (M6):

   ```
   $ grep -o 'Market[A-Za-z]*Result' site/manual/results/index.html | sort | uniq -c
         4 MarketNodalResult
   ```

   The words "zonal" and "multiperiod" appear **zero** times in that page's body. The three
   `zonal` hits in its raw HTML are all navigation chrome — and one of them is the tell:

   ```
   $ grep -o '.\{0,70\}[Zz]onal.\{0,50\}' site/manual/results/index.html
           <link rel="prev" href="../zonal/">
         <a href="../zonal/" class="md-nav__link">
     Zonal market
   ```

   `rel="prev"` — the Results page is literally the next page after *Zonal market* in the
   reading order, and it is the previous two waves' result types that are missing from it.

3. So both plausible destinations — the API reference and the Results manual — are empty
   on this object, and the only complete description of it lives in the source.

The site-wide half of this is pre-existing (M5 already missed the Results manual). What is
new in M6 is that this is the first wave whose manual builds a headline section entirely
on reading fields off a result object, which is what turns a latent gap into a wall.

### D3 — MEDIUM. `CorridorLimit` rejects an infinite cap; the array level accepts it

The manual's *"Deleting a corridor is not the copper plate"* section tells the reader that
the copper plate is obtained by "**lifting the cap** — leaving the column in place,
unbounded". The array-level validator's own docstring is more explicit still:

```python
# src/mambo_power/opf/zonal.py:273
raise ValueError(f"corridor {key!r} has a NaN cap -- give a number, 0, or inf")
```

But the documented, options-level path refuses `inf`:

```
CASE: cap_mw = inf
  -> RAISED pydantic_core._pydantic_core.ValidationError
     cap_mw / Input should be a finite number [type=finite_number, input_value=inf]
```

while the array level accepts it and produces the genuine copper plate:

```
$ ... zonal_dc_opf(arr, cc, zof, {('A','B'): float('inf')}, ...)
ARRAY LEVEL cap=inf -> Optimal ['A', 'B'] [10. 10.] [30.]
```

So the two layers disagree about whether `inf` is a legal cap, and through
`market.solve_zonal` the only copper plate available is a large finite approximation — the
example uses `1.0e6` and labels the line `cap lifted (1e6 MW)`. Neither the manual's prose
nor its errors table (which documents the negative-cap rejection in detail) mentions that
the cap must be finite. A reader who reads "unbounded" and writes the obvious thing gets a
validation error with no pointer to the workaround.

Either constraint is defensible on its own; the defect is that they differ and the docs
describe the permissive one while shipping the strict one.

### D4 — MEDIUM. `redispatch_payment` goes negative in precisely the regime the page showcases

Both the manual and the field docstring hedge the sign correctly:

> …which is why it is non-negative **wherever the zonal LP is a relaxation of the nodal
> one** — it is the welfare the zonal clearing promised and the network could not deliver.

Neither then says *when it is not a relaxation*. And the manual's own
*"Deleting a corridor is not the copper plate"* section walks the reader directly into that
case: removing corridors makes the zonal problem strictly *more* constrained. On the
manual's own 3-bus fixture:

```
CASE: corridors omitted entirely (default options)
  status = Optimal
  figures = -800.0 0.0 800.0        <- redispatch_payment = -800.0
CASE: cap_mw exactly 0
  figures = -800.0 0.0 800.0
```

The arithmetic is right (zonal islands at 50·10 + 30·50 = 2000; final is 70·10 + 10·50 =
1200; 1200 − 2000 = −800), and the hedge technically covers it. But the page devotes an
entire subsection plus a runnable demonstration to the no-corridor regime while discussing
only the *prices* there, never the figures — so a reader who tries the documented
variation sees the operator being *paid* 800 $/h to make the schedule deliverable, with
nothing on the page acknowledging that this can happen.

Meanwhile the runnable example prints an unqualified label, two sections after
demonstrating the no-corridor case itself:

```
  redispatch_payment    +14.636683 $/h   settlement figure, >= 0
```

The page spends a whole warning admonition teaching that `generation_cost_gap` is not
sign-constrained. The same treatment is owed to the conditional on `redispatch_payment`'s
sign, or the example's `>= 0` should carry the condition.

### D5 — MEDIUM. Rendered API prose cites documents that are not on the site

Stripping source-view blocks first, so these are citations a reader meets in ordinary
rendered prose:

```
api/opf     :: record/m6-research.md x2, record/m6-ac2-derivation.md x1, record/m3-research.md x5,
               record/m5-research.md x1, .bionic/tmp/m3-s2-progress.md x1,
               spec "## Design" x4, spec A3 x1, design decision D2 x1,
               research §1..§7 x16, (W4), (W6) x4, wave M5 W2 x2, wave M6 W1/W2/W3
api/market  :: record/m3-research.md x4, design decision D1/D2/D3 x4, spec "## Design",
               spec "## Rejected", research §1 x4, research §2 x4, (S6) x2, (S7) x2, wave M6 W4
api/results :: design decision D1, (W1) x2, (W3) x4, wave M2 W5, wave M5 W5, wave M6 W4
api/pf, api/contingency, api/numerics, api/jobs, manual/power-flow :: same pattern, M2–M3 vintage
```

Sample, from `site/api/opf/index.html`:

> That is design decision D2, alternative b2 (spec `## Design`; `record/m6-research.md`
> §2(b)) …
> This is precisely the convention `record/m6-ac2-derivation.md` §2 hand-derives …
> … collapsing them into the single system-wide row `dc_opf` already builds
> (`record/m6-research.md` §2(a)).

None of `record/*.md`, the spec, or the `D`/`W`/`S` identifiers is published. Nothing
404s — these are plain text, not links — but a reader is repeatedly told that the real
justification is somewhere they cannot go.

Two things worth separating:

- **This is a house pattern, not an M6 invention.** Every API page does it, back to M2. The
  single worst instance is `.bionic/tmp/m3-s2-progress.md` on `api/opf` — a machine-local
  scratch path in a published docstring — and that is M3's, not M6's. M6's contribution is
  three more `record/m6-*.md` citations and the `W1`–`W4` slice tags.
- **`ADR-006`, `ADR-007` and `ADR-008` are cited but do not exist.** 20 citations across
  the site; `Design › Decisions` documents ADR-001 through ADR-005 only:

  ```
  $ grep -rhoE 'ADR-[0-9]+' site --include=*.html | sort | uniq -c
        4 ADR-001   4 ADR-002   3 ADR-003   10 ADR-004   5 ADR-005
        6 ADR-006   5 ADR-007    9 ADR-008
  ```

  `ADR-008` in particular is load-bearing in M6's own prose ("`_extract_and_validate`
  (ADR-008)'s whole point"), cited nine times, and undocumented. This one is a dead
  cross-reference to a page the site *does* have — the cheapest of the five to fix and the
  most likely to be noticed by an outside reader.

### D6 — LOW. A "later wave" placeholder that is now real

`api/market`, `MarketNodalOptions`:

> No fields yet: mirrors `OpfDcOptions`'s own precedent … — present now, not omitted, so a
> **future** jobs `KindSpec` (S6) has a stable options model to validate requests against.

`market.nodal` has been a registered kind since M4, and `market.multiperiod` since M5:

```
KINDS: 7 ['market.multiperiod', 'market.nodal', 'market.zonal', 'n1', 'opf.dc', 'pf.ac', 'pf.dc']
```

`MarketMultiperiodOptions` next to it has the same shape of sentence with `(S7)`. Neither
kind is future any more.

### D7 — LOW. "Two prices" is a rounding statement, asserted flatly

`manual/zonal`, in *Zone prices*:

> case30 has three zones and **produces two prices**, because zones 1 and 3 are joined by a
> slack corridor whose interior exchange column forces their two balance duals equal.

The run gives three distinct floats — `3.759145`, `3.880504`, `3.759147` — so
`len({z.price for z in result.zones})` is 3, not 2. The manual reconciles this two sections
later ("their prices are equal **to solver precision**") and the example prints all six
decimals, so the reader does get the truth eventually. But the flat claim comes first and a
reader who tests it with a `set()` finds it false.

### D8 — LOW. `contributing.md`'s quality-gate checklist omits the docs sync

The worktree half of this was resolved mid-walk (§0). The durable half is not: the
quality-gate checklist in `docs/contributing.md` lists

```bash
uv run pytest                   # all tiers
uv run mkdocs build --strict    # the docs, zero warnings
```

with no preceding `uv sync --all-groups`, while `pyproject.toml` declares no
`default-groups` — so `uv run` provisions the `dev` group only and that last line fails
with "Failed to spawn: mkdocs" on a fresh clone. The "Building the docs locally" section
further down the same page *does* include the sync, so it is a one-line inconsistency
within a single file. Pre-existing, not M6.

### D9 — LOW / cosmetic. Negative zeros reach the result surface

```
zonal gens  : [('genA', 80.0), ('genB', -0.0)]
branch rows : [('br12', 70.0, -0.0), ('br23', 20.0, -40.0)]
```

`-0.0` in `result.generators` for an idle generator and in `flow_limit_dual` for an
unbinding branch. Harmless arithmetically (`-0.0 == 0.0`), but it prints, it serialises to
`-0.0` in JSON, and it makes a clean-looking table look like it has a sign error in it.

---

## 4. Things I specifically looked for and did not find

Recording the negatives, since a clean walk is only worth anything if the misses are named.

- **Broken `:::` blocks** — none. Every `::: mambo_power.<module>` directive rendered; the
  mkdocstrings headings, signatures and cross-reference links are all present.
- **Math with literal backslashes** — none. 64 MathJax containers rendered; zero `\(`,
  `\[`, `\sum`, `\Delta`, `\lambda` occurrences in the browser's visible text, and zero
  lines of visible text containing a backslash at all.
- **Dead cross-references** — zero broken internal links and zero missing anchors across
  all 30 built pages. (The ADR-006/007/008 problem in D5 is prose text, not a link.)
- **Code blocks that lost content** — none in the manual. The `results/` field-list absence
  in D2 is an mkdocstrings/pydantic rendering behaviour, not a truncated block.
- **A page still counting six job kinds** — none. Every count I found says seven, and
  `len(jobs.KINDS)` is 7.
- **A docstring contradicting the manual** — none found on the substantive claims. I
  checked the sign convention (agrees three ways), the capacity price's non-negativity, the
  netting representative, the three figures' definitions, and the `redispatch_payment` sign
  hedge (the field description in `results/zonal.py` is if anything *more* carefully hedged
  than the manual). The one asymmetry is D2's `delta_up`/`delta_restore` vocabulary split,
  which is an omission rather than a contradiction.
- **Stale future-tense claims about zonal itself** — none. `grep` for "later wave" /
  "will add" / "not yet" near zonal/corridor/redispatch returns nothing. The home page
  status block, the roadmap table, the architecture diagram and the changelog are all
  current for M6. The only stale placeholder found is D6, about M4/M5.
- **`MarketZonalResult` carrying corridor rows** — the manual says it does not, and it does
  not. Its 15 fields are exactly what the page enumerates. The array-level route it points
  to for corridor flows and duals works as described.

---

## 5. Summary

| # | Severity | Defect |
|---|---|---|
| D1 | **High** | Four caller-data mistakes on `market.zonal` return `INTERNAL` (documented as "a bug"), not `BAD_OPTIONS`; the jobs manual claims the opposite |
| D2 | Med-High | `MarketZonalResult` field names published nowhere: `api/results` renders no pydantic fields site-wide; `Manual › Results` stops at M4; manual's netting identity uses generator-only field names |
| D3 | Medium | `CorridorLimit` rejects `cap_mw=inf`; array level accepts it; manual describes the copper plate as "unbounded" |
| D4 | Medium | `redispatch_payment` is negative in the no-corridor regime the same page showcases; example labels it ">= 0" unqualified |
| D5 | Medium | Rendered API prose cites `record/*.md`, spec sections and slice tags that are not on the site; `ADR-006/007/008` cited 20× and undocumented |
| D6 | Low | `MarketNodalOptions` still says it exists for "a future jobs KindSpec" — registered since M4 |
| D7 | Low | "case30 … produces two prices" — three distinct floats; reconciled only two sections later |
| D8 | Low | `contributing.md`'s quality-gate checklist runs `uv run mkdocs` with no preceding `uv sync --all-groups` and no `default-groups` declared (worktree half resolved mid-walk) |
| D9 | Low | `-0.0` reaches `result.generators` and `flow_limit_dual` |

The engine itself came through this walk without a single numerical discrepancy. Every
figure, identity, dual, sign and error message I could check against the documentation
matched, including two hand-computed scenarios of my own construction and 719 unit tests.
The defects are concentrated in the seam between the library and the people who will use
it: how a failure is classified for a service (D1), and where a reader finds out what is on
the object the manual tells them to read (D2).
