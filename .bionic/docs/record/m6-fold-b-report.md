# M6 fold B — the documentation half

Worktree `C:\Claude Projects\mambo-power-m6`, branch `wave/06-zonal-redispatch`. Dispatched
against head `d0ce957`; finished at `c065bbe`. Ownership: `docs/**`, `examples/**`, `mkdocs.yml`
only — held, and checkable per commit (`git show --stat`).

Every command below was run with `uv run --no-sync` from the worktree root. `mkdocs 1.6.1`
resolved from the worktree venv on the first try, so A27's setup fix held.

## 0. Commits

| commit | items | files |
|---|---|---|
| `f6a9b7b` | (d) rendering | `docs/hooks/pydantic_fields.py`, `mkdocs.yml` |
| `484aac4` | (d) netting, (f), (l), (i), sold-vs-delivered | `docs/manual/zonal.md`, `docs/changelog.md` |
| `c0aa423` | (d) Results manual | `docs/manual/results.md` |
| `8d85b02` | (b), (j), (f) example | `docs/manual/jobs.md`, `docs/contributing.md`, `examples/04_jobs_api.py`, `examples/11_zonal_redispatch.py` |
| `ec71e18` | (g) | `docs/design/decisions.md` |
| `3dc0fc8` | changelog | `docs/changelog.md` |
| `c065bbe` | hardening | `docs/hooks/pydantic_fields.py` |

No commit touches `src/**` or `tests/**`. The head moved under me twice while I worked
(`8f1e187`, `15ab30b` from fold-a); nothing I report as unfixed is a file fold-a had already
changed — checked with `git log` before writing.

## 1. Item (d) — result-model fields render nowhere

### The gap is not a missing option

The brief pointed at `members` / `show_if_no_docstring` / "pydantic-model handling". The actual
cause is narrower and explains the asymmetry the walk measured exactly. griffe documents an
attribute from a **PEP-257 attribute docstring** — the bare string literal following the
assignment. The dataclasses under `opf/` have them (`opf/zonal.py:164-175`), so their attributes
render. The pydantic models put their prose in `Field(description=...)`, which is an argument to
a function call and not a docstring at all. griffe therefore sees an undocumented attribute,
`show_if_no_docstring: false` drops it, and the description reaches the site only inside the
`show_source: true` block as syntax-highlighted Python.

`show_if_no_docstring: true` would have made the names appear without their prose, and would have
un-hidden every genuinely undocumented member site-wide. `griffe-pydantic` is the purpose-built
answer but is not in the venv (`ls .venv/Lib/site-packages | grep griffe` gives `griffe` and
`griffelib-2.2.0` only), and adding a dependency requires the sync I was told not to run.

### The fix

`docs/hooks/pydantic_fields.py`, a griffe extension registered under the mkdocstrings python
handler's `options.extensions` in `mkdocs.yml`. After a package loads it walks every class,
imports the real module, reads `model_fields[name].description`, and attaches it to the griffe
`Attribute` as its docstring. An explicit attribute docstring always wins, so this can only add.

It also replaces the attribute's rendered **value**. Before, the value shown in the signature was
the entire `Field(...)` call — constraint keywords plus a second copy of the description. Now it
is the field's actual default. That is the better rendering, and on Windows it is load-bearing:
see §5.

### Verified from rendered HTML

Baseline measured by building a copy of `mkdocs.yml` with the `extensions:` block stripped, into a
scratch site directory; the baseline config was deleted afterwards. Distinct field anchors per
page (`id="mambo_power.<mod>.<Class>.<field>"`):

| page | baseline | with the extension |
|---|---|---|
| `api/results` | 2 | **205** |
| `api/model` | 4 | **123** |
| `api/market` | 2 | **6** |
| `api/opf` | 110 | 112 |

`api/opf` moves by two (the pydantic options models under `opf`); the 110 dataclass entries are
untouched, which is the regression control.

The walk's own D2 queries, re-run:

```
$ grep -rl 'delta_restore_mw' site --include=*.html
site/api/results/index.html
site/changelog/index.html
site/manual/results/index.html
site/manual/zonal/index.html
```

— from zero pages site-wide. Same for `delta_curtail_mw`. Negative control: `delta_restore_gw`
is absent (grep count 0). In the browser, on `api/results` with the collapsible source views
removed from the DOM first, so this is documentation and not highlighted Python:

```
documentedFieldHeadings: 222
zonalFieldHeadings: 28
deltaRestoreVisibleOutsideSourceView: true
deltaRestoreDescription: "delta_restore_mw class-attribute instance-attribute ¶
                          delta_restore_mw: float  Served demand restored above the zonal
                          schedule, MW; >= 0. d_final = d_zonal + delta_restore_mw - delta_curtail…"
fieldCallStillShownAsValue: false
```

### Manual > Results

Sections for `MarketMultiperiodResult` and `MarketZonalResult`, in the `MarketNodalResult`
section's shape. The walk's query, before and after:

```
$ grep -o 'Market[A-Za-z]*Result' site/manual/results/index.html | sort | uniq -c
      4 MarketNodalResult                    # walk
      3 MarketMultiperiodResult              # now
      6 MarketNodalResult
      2 MarketPeriodResult
      4 MarketZonalResult
```

In the article body, "zonal" 0 → 14 occurrences and "multiperiod" 0 → 5; `delta_restore_mw`,
`delta_curtail_mw`, `soc_mwh` and `ramp_dual` each present. Both sections appear in the page's
own table of contents (read from the rendered nav in the browser).

### The netting text

The walker's `AttributeError` is reproduced by the docs exactly as reported. Measured field names:

| layer | generator side | load / demand side |
|---|---|---|
| `MarketZonalResult.redispatch_generators` | `delta_up_mw`, `delta_down_mw` | — |
| `MarketZonalResult.redispatch_loads` | — | `delta_restore_mw`, `delta_curtail_mw` |
| `opf.redispatch.RedispatchSolution` | `delta_up_mw`, `delta_down_mw` | `demand_delta_up_mw`, `demand_delta_down_mw` |

The manual stated the identity as `delta_up`/`delta_down` (no `_mw`, and generator-only) while
naming `MarketZonalResult`. It now carries that table, states both forms of the identity, and says
that restoring demand is the `up` direction. The changelog's M6 entry carried the same
generator-only phrasing and is fixed with it.

## 2. Item (f) — when `redispatch_payment` goes negative

Measured myself rather than taken from the records, on the manual's own three-bus fixture:

```
cap 20 MW (binds)    payment    +0.0000   gen_cost_gap    +0.0000
cap lifted 1e6 MW    payment  +400.0000   gen_cost_gap  -400.0000
cap exactly 0        payment  -800.0000   gen_cost_gap  +800.0000
corridors omitted    payment  -800.0000   gen_cost_gap  +800.0000
```

and reproducing the review's C7 case (case30, every branch rating ×20, corridor caps 0):

```
loose ratings, derived caps (1.0x cut-set)  payment=  -0.00000  cost_gap=  +0.00000
loose ratings, caps 0                       payment= -11.05343  cost_gap= +11.05343
loose ratings, corridors omitted (islanded) payment= -11.05343  cost_gap= +11.05343
```

**One correction to the brief's framing.** "Caps tighter than the network, or islanded zones" is
right as a description of the two ways in, but tight caps are not the condition on their own. On
example 11's own case30 — ratings derived at 1.2× the base-case DC flow, a very tight network —
every cap regime stays on the relaxation side:

```
cut-set caps (example 11)    payment   +14.636683
caps x0.5                    payment   +11.363599
caps x0.25                   payment    +8.123034
corridors omitted            payment    +3.804867
```

Islanding the zones there still leaves the zonal problem the looser of the two. The condition is a
*comparison* — the zonal feasible set has to contain the nodal one — and the manual now says that,
with all three numbers, rather than offering a rule of thumb that its own fixture falsifies.

Example 11's `>= 0` label is gone, and the example measures the counterexample instead of
asserting a claim: part 1 already solves the deleted-corridor case, so it now prints the payment
across all three regimes and names the condition.

## 3. Item (l) — the payment / cost-gap identity

Measured on the wave's own committed factories (`tests/_rated`, `tests/_zones`, `tests/_bids`),
driving them rather than reconstructing a fixture:

```
case30  fixed-load  payment=+14.636683  welfare_gap=-2.649e-11  gap=-14.636683  sum=-2.6489033e-11
case30  elastic     payment=+14.513372  welfare_gap=-4.133e-09  gap=-13.572257  sum=+9.4111497e-01
case300 fixed-load  payment=+18.180213  welfare_gap=-2.006e-06  gap=-18.180215  sum=-2.0060688e-06
case300 elastic     payment=+21.877504  welfare_gap=-1.522e-06  gap=-35.820636  sum=-1.3943131e+01
```

The last line is new relative to the audit's two: **`B` is not sign-constrained either.** It is
negative whenever the redispatch lands on more valuable served demand than the zonal clearing
sold, and case300's bid fixture gives −13.943 \$/h. The manual says so.

Coordination with fold-a: I read `src/mambo_power/market/zonal.py` in their working tree before
writing (`git log -p` showed no commit on it yet; the change was uncommitted). Their docstring
uses `A = cost(final) − cost(zonal)`, `B = value(d_zonal) − value(d_final)`, calls the three fields
`A + B` / `0` / `−A`, and quotes "0.94 of a 14.51 \$/h payment". My manual section uses the same
decomposition, the same letters and the same numbers. The one wording difference is the heading —
mine is "two independent quantities plus a check", matching the audit's and ADR-009's phrasing;
theirs is "two quantities and a combination". Same claim.

The old parenthetical on the manual ("with bids in play they are independent numbers") was the
overclaim in miniature and is replaced.

## 4. Items (g), (b), (i), (j) and the sold-vs-delivered trap

**(g) ADRs.** Every ADR number cited anywhere on the site now has exactly one heading on
Design > Decisions:

```
ADR-001 cited 4  heading 1      ADR-006 cited  9  heading 1
ADR-002 cited 4  heading 1      ADR-007 cited  9  heading 1
ADR-003 cited 3  heading 1      ADR-008 cited 14  heading 1
ADR-004 cited 10 heading 1      ADR-009 cited  3  heading 1
ADR-005 cited 5  heading 1
```

Negative control: `adr-010` absent. Each is distilled — context, decision, consequences,
rejected — with no process frontmatter, no citations of documents the site does not publish, and
no internal step or criterion labels.

**I added ADR-009 beyond the three named.** It is this wave's own accepted ADR and stopping at 008
would recreate the identical gap the day the wave merges. It also carries the reasoning behind
three other fold items, so its consequences link out to the zonal manual's new sections. If the
orchestrator wants it held back until after the ADR step, it is one contiguous block in
`ec71e18`.

**(b) `pf.telepathy`.** `docs/manual/jobs.md` and `examples/04_jobs_api.py` switched, with the
general rule stated on the page: an unknown-kind demo must name a kind that can never become real.
Example 04 runs green and its line matches the manual's quoted output verbatim:

```
failed UNKNOWN_KIND | unknown kind "pf.telepathy"; registered kinds: market.multiperiod,
market.nodal, market.zonal, n1, opf.dc, pf.ac, pf.dc
```

The manual's `kind` row still lists `market.agents` as a later wave — that is a roadmap statement,
not a demo, and it stays true. `tests/unit/test_jobs.py` is the third site and is fold-a's.

**(i)** "produces two prices" now reads "two distinct prices *to solver precision*" where it is
first stated, with the three floats and the note that `len(set(...))` is 3 given immediately
rather than two sections later.

**(j)** The quality-gate checklist gains `uv sync --all-groups` and a sentence saying why. Verified
the claim it makes: `grep -n "default-groups" pyproject.toml` finds nothing.

**Sold vs delivered.** A warning admonition on the zonal manual and the lead paragraph of the
Results section: `MarketZonalResult.generators` is the sold schedule, `MarketNodalResult.generators`
the delivered dispatch, the same name across a closed union. Quantified from example 11 — all six
generators move between the layers, 21.9 MW of instructed-up volume.

**Changelog.** It carries no per-wave fold notes; it carries an `Added` section per wave with a
documentation bullet, and one shared `Changed` section whose entries are wave-tagged. I followed
that shape rather than inventing a fold heading: M6's documentation bullet names the new material,
and the field-rendering fix gets a `Changed` entry because it changes the published site for every
wave's models, not only M6's.

## 5. Two findings for the orchestrator

### (a) The rendering fix enlarges fold (a)'s surface

Scanning rendered prose with source views stripped, `api/results` now shows 5 "design decision D#"
citations against the walk's 1. Reading the descriptions off the real classes, exactly two come
from pydantic field descriptions that are newly visible because of my change:

```
results.zonal  MarketZonalResult  generation_cost_gap   design decision D1
results.zonal  MarketZonalResult  generators_final      design decision D1
```

Both are `src/` and therefore fold-a's. The general point is worth carrying to M7: **field
descriptions are now published prose.** Anything written into a `Field(description=...)` reaches
the reader, so the fold (a) discipline about citing unpublished documents applies to them too. The
full current scan, for the re-audit:

```
bare finding label (W#)  20   record/*.md          16
design decision D#       10   spec "## Design"      5
bare slice label (S#)     4   .bionic/tmp           1

api/opf     record/*.md 9, .bionic/tmp 1, spec "## Design" 4, D# 1, (W#) 5
api/market  record/*.md 4, spec "## Design" 1, D# 4, (S#) 4
api/results D# 5, (W#) 6
api/pf      record/*.md 1, (W#) 7
api/contingency record/*.md 2 · api/numerics (W#) 1 · manual/power-flow (W#) 1
```

### (b) A live Windows landmine in the docs build

mkdocstrings formats every attribute signature by piping it to an external formatter as a
subprocess, writing to its **stdin**, which on Windows encodes cp1252. The moment pydantic fields
started rendering, `--strict` died:

```
ERROR - Error reading page 'api/pf.md': 'charmap' codec can't encode character '\u221e'
        in position 65: character maps to <undefined>
  … rendering.py:539 subprocess.run → subprocess.py:1143 self.stdin.write(input)
  … encodings/cp1252.py:19 → UnicodeEncodeError
```

The character is `∞` in `src/mambo_power/pf/ac_newton.py:102` —
`tol: float = Field(default=1e-8, gt=0.0, description="Mismatch ∞-norm tolerance, pu.")` — which
was being rendered as the attribute's *value* because the value was the whole `Field(...)` call.
Replacing the value with the real default removes it, which is why that half of the extension is
not cosmetic. **This is not fixed in general**: any non-Latin-1 character in a rendered default —
a dataclass default, a string constant, an enum member — will do it again, on Windows only, and
the failure names the wrong page. Two durable options if it recurs: set `PYTHONIOENCODING=utf-8`
in the docs CI job, or turn the signature formatter off.

### The fix now fails loudly

The failure mode this whole item exists to prevent is a silent one — field lists vanish and
nothing notices, which is how the gap survived five waves. So the extension warns on a module it
cannot import and warns if it documents zero fields across the package, and under `--strict` a
warning aborts. Positive control, by forcing `_document` to find nothing:

```
WARNING -  pydantic_fields: documented NO fields in mambo_power -- pydantic field
           descriptions will not be published on the API pages
Aborted with 1 warnings in strict mode!
CONTROL_BUILD_EXIT=1
```

Restored, the build is exit 0 with `documented 217 field(s)`.

A stronger guard belongs in `tests/`, which is not mine: a test asserting that `api/results`
renders more than N field anchors would catch the same regression without depending on the build
gate. Recommended for fold-a or M7.

## 6. Gates, at `c065bbe`

| gate | result |
|---|---|
| `uv run --no-sync mkdocs build --strict` | exit 0, no ERROR, no WARNING |
| internal fragment links | 10346 checked across 30 pages, **0 broken** |
| `test_api_docs_coverage.py` | passed, **unmodified** (`git diff HEAD` empty; last touched by `aa53140`, M4) |
| `test_examples_run.py`, `test_docs_registry_listing.py`, `test_docstrings.py` | 21 passed together with the above |
| `examples/04_jobs_api.py` | exit 0 |
| `examples/11_zonal_redispatch.py` | exit 0, output identical to the run quoted here |
| `ruff check` / `ruff format --check` on both examples | clean |

`mkdocs --strict` does **not** validate URL fragments, so the anchor check is a separate script
over the built HTML. It is positive-controlled: injecting one resolvable-looking and one bogus
fragment into a page made it report 2 broken, naming both. (The "resolvable-looking" one,
`#adr-006`, is genuinely broken — the heading's real id is the full slug — which is the checker
being right and my control being sloppy. Nothing on the site links to the short form; the ADR
numbers appear as prose.)

**Browser.** The two new display-math blocks cannot be verified by parsing HTML, so I drove the
page. Served `site/` on `127.0.0.1:8123`:

```
mathJaxLoaded: true
mjxContainersOnPage: 74
mjxContainersInNewIdentitySection: 10
unrenderedLatexLeftInVisibleText: 0
newSectionHeadingFound: true      negativePaymentSectionFound: true
soldVsDeliveredAdmonition: true   tables: 4
```

`manual/results` checked the same way: both new sections present with anchors, both in the page
TOC, all seven outbound fragment links present, 8 tables.

**Teardown.** All three browser pages closed; the server stopped and the port verified clear:

```
killing pid 54860
port 8123 clear
```

## 7. What I did not do

- Nothing in `src/**` or `tests/**`. Fold items (a), (c), (e), (h), (k), (m), (n), (o), (p), (q),
  (r) are fold-a's, and the two field descriptions in §5(a) are the only place my work touches
  theirs.
- The `∞` landmine is sidestepped for the current tree, not fixed at the layer it lives in
  (§5(b)) — that needs a CI env var or a handler option, and I judged a build-config change of
  that reach to be the orchestrator's call rather than a docs fold's.
- No test asserting the field anchors stay rendered, because `tests/**` is not mine (§5).

---

# Appendix — follow-up fold (docs), after fold-a's corridor work

Dispatched after the main fold, on the same ownership. Three items, three commits, all touching
only `docs/**` and `examples/**`. Finished at `34bd131`, on top of fold-a's `cb6dfa9`.

| commit | item |
|---|---|
| `51cb62a` | request-size bounds (`MAX_PERIODS`, `MAX_CORRIDORS`) |
| `7fd6cbe` | corridor mistakes classified, on both the zonal and jobs pages |
| `34bd131` | the copper plate is `null`; the unzoned-bus contract on both surfaces |

## A1. Sequencing — one item was held, deliberately

Two sub-items depended on `fix(m6/e2,c2)`, which was **uncommitted in the shared worktree** when
the follow-up was dispatched. I read that working tree to get the shapes right but did not write
from it, and held the two sub-items until the commit landed. That mattered: between the first read
and the commit, fold-a's change grew from three files to six, and one detail I would have
documented turned out **wrong** — see A4.

The general rule this is an instance of: *a manual written against an uncommitted working tree
describes something that may never ship.* The cost of holding was one idle interval; the cost of
not holding would have been a published page describing an options-level error path that does not
exist.

While held, the patch was **dry-run against a mirror** of the two target files, so all five string
assertions were known to match before the real run.

## A2. Item 1 — the corridor mistakes are caller errors (`7fd6cbe`)

Every code was driven through `jobs.run` on a zoned, rated case30 rather than read off the source:

```
self-pair (A,A)                  status=failed  code=BAD_OPTIONS
duplicate pair, SAME order       status=failed  code=BAD_OPTIONS
duplicate pair, REVERSED order   status=failed  code=BAD_OPTIONS
negative cap                     status=failed  code=BAD_OPTIONS
501 corridors                    status=failed  code=BAD_OPTIONS
unknown zone id                  status=failed  code=VALIDATION
    DANGLING_REF at options.corridors[3].zone2
```

The zonal errors table now carries the `jobs.run` code per row, and gained the `MAX_CORRIDORS` row
it never had. The jobs manual's zonal paragraph claimed only that an *unknown zone* is caught
before any solve; that is now true of all four mistakes, so it says so in a table, and says why the
unknown-zone one is the odd one out — an options model has no network to check against, so it is
raised at resolution time as a network-validation issue instead.

**One behaviour change is called out explicitly**, because a reader on an older build may have
relied on it: a repeated zone pair now raises **in either order**. It previously raised only when
reversed and cleared the market *silently* when repeated in the same order, because `corridor_map()`
is a dict comprehension and the last entry simply won. A request that used to return `status="ok"`
on a capacity the caller never chose now returns `BAD_OPTIONS`.

## A3. Item 3 — the two request-size bounds (`51cb62a`)

`MAX_PERIODS` and `MAX_CORRIDORS` were enforced by the models and stated on no manual page. Both
are now on the Jobs API page under `SolveRequest`, framed as **amplification guards** rather than
solver limits, which is the part a reader needs in order to not mistake them for capability claims.

Measured rather than asserted:

```
MAX_PERIODS = 200          MAX_CORRIDORS = 500
201 periods via run_json  -> failed BAD_REQUEST
501 corridors via jobs.run -> failed BAD_OPTIONS
C(32,2) = 496   C(33,2) = 528     # so 500 is a complete graph on 32 zones
```

The changelog's existing periods entry gains the corridor bound beside it and links to the section.

## A4. Item 2 — the copper plate is `null` (`34bd131`)

**The re-probe earned its keep.** Against `cb6dfa9` the unzoned-bus failure is reported as one
`DANGLING_REF` issue per bus at **`buses[i].zone`** — a *network* path, not the options path I had
drafted from the earlier working tree. The errors table says what the commit does.

Measured at `cb6dfa9`:

```
CorridorLimit   cap_mw=None -> accepted (cap_mw=None)    cap_mw=inf -> finite_number
                cap_mw=0.0  -> accepted                  cap_mw=-1  -> greater_than_equal

solve_zonal     cap 1.524 (binds)  Optimal  prices=[3.759145, 3.880504, 3.759147]
                cap_mw=None        Optimal  prices=[3.789199, 3.789201, 3.7892  ]

run_json        request is plain JSON:            True
                reply has no Infinity token:      True
                json.loads(reply) OK, status =    ok
                echoed corridors[0] = {'zone1': '1', 'zone2': '2', 'cap_mw': None}
                raw text contains '"cap_mw": null': True
```

and the unzoned bus on **all three** surfaces, with three buses cleared to check that every one is
reported rather than only the first:

```
direct zone_partition -> caught by 'except ValueError': UnzonedBusError
   bus_ids = ['bus-4', 'bus-8', 'bus-13']
direct solve_zonal    -> caught by 'except ValueError': UnzonedBusError
jobs.run              -> failed VALIDATION | 3 issues
   DANGLING_REF at buses[3].zone:  bus "bus-4"  …
   DANGLING_REF at buses[7].zone:  bus "bus-8"  …
   DANGLING_REF at buses[12].zone: bus "bus-13" …
```

Both requested sentences are placed *beside* the jobs code rather than instead of it, because the
library contract and the service contract are different readers' concerns:

- the errors table's unzoned-bus row states that `UnzonedBusError` is a `ValueError` **subclass**,
  so a direct caller's existing `except ValueError:` around `zone_partition` or `solve_zonal` keeps
  working unchanged;
- the copper-plate section states the rule for `cap_mw` plainly: the copper plate is `null`, and
  any other cap must be a finite, non-negative number (`inf`, `-inf` and `NaN` all rejected).

A `run_json` example carrying the copper plate sits in the page's Jobs API section, with an
expected-output block beneath it in the page's own convention. Its output was **executed, not
written**: `ok [10.0, 10.0]` and `{'zone1': 'A', 'zone2': 'B', 'cap_mw': None}`. (The first draft
of that example used a zone `C`; the page's own fixture has only `A` and `B`, so it would not have
run. Caught by executing it.)

### Example 11

The copper plate is `cap_mw=None`. The comment keeps the mechanism — the corridor stays in the LP
with no bound, so the two balance rows collapse — and drops the magnitude, naming the trap instead:
`1.0e6` is unbounded only for a network this small, and the same request against a bigger system is
a silently binding limit wearing the word "unbounded".

The re-run diff against the previous output is **exactly one line, the label**:

```
< cap lifted (1e6 MW)        price A  10.00  price B  10.00  genA  80.00 MW  genB   0.00 MW
> cap lifted (cap_mw=None)   price A  10.00  price B  10.00  genA  80.00 MW  genB   0.00 MW
```

Every number identical — which is exactly why the old spelling looked correct and was wrong anyway.
The manual's quoted block is updated to match, and the prose above it now says "only `cap_mw=None`
gives `10 / 10`" instead of "the lifted cap".

## A5. Gates, at `34bd131`

| gate | result |
|---|---|
| `uv run --no-sync mkdocs build --strict` | exit 0, no ERROR, no WARNING |
| internal fragment links | 10361 across 30 pages, **0 broken** |
| `test_examples_run.py`, `test_api_docs_coverage.py`, `test_docs_registry_listing.py` | 19 passed; `test_api_docs_coverage.py` still unmodified |
| lines the manual quotes from example 11 | all 12 match the fresh run verbatim |
| the page's own "Using it" snippet | re-executed at `cb6dfa9` to its quoted output, unchanged |
| the new `run_json` snippet | executed; its output is what the page now prints |
| `ruff check` / `ruff format --check` on example 11 | clean |
| rendered `manual/zonal` body | `cap_mw=None` ×3, `"cap_mw": null` ×3, `UnzonedBusError` ×1, `RFC 8259` ×1, `except ValueError` ×2, `buses[i].zone` ×1, `provenance.options` ×1 |

Ownership held throughout: `git show --stat` on each of the three commits shows `docs/**` and
`examples/**` only.

## A6. Note for M7

The `1e6`-as-copper-plate defect is worth carrying as a shape, not just a fix. It was **correct on
every fixture the repo has** — the manual's three-bus network and case30 both clear identically
under `1e6` and under `None` — so no test and no rendered-output check could have caught it. What
made it wrong was a reader on a network nobody in this repo has. The class of defect is *a magic
number that encodes an assumption about scale*, and the only defence is the one applied here:
spell the intent (`None`) rather than approximate it.

## A7. A correction I had to make to my own commit (`232de50`)

The first version of the copper-plate section explained `cap_mw: null` **by contrast with a bare
`Infinity` token** — that `json.loads` accepts it and a browser's `JSON.parse` rejects it, so a
response carrying one would not be parseable everywhere the request was. That contrast described a
wire format this package does not have. `ser_json_inf_nan` was removed with the revert, and
`CorridorLimit`'s config is now

```python
model_config = ConfigDict(extra="forbid", frozen=True, allow_inf_nan=False)
```

byte-identical to `4432163`, before the fold touched it. Nothing in `market/zonal.py` can emit a
non-standard token.

The paragraph was accurate about what happens and still wrong to print, and the reason generalises:
**explaining a rule by contrast with something that cannot happen teaches the reader a hazard that
does not exist**, and invites them to write defensive code against it. It survived my own review
because every sentence in it was individually true — I had measured "reply has no `Infinity`
token: True" — and the measurement confirmed the behaviour without ever asking whether the
alternative it was defending against was reachable. A rendered-output check cannot catch this
class either; the text renders perfectly.

The section now states the rule and stops: the copper plate is `null`; any other cap must be
finite and non-negative.

Two facts landed with the correction, both measured at `cb6dfa9`:

```
cap_mw required   model_fields["cap_mw"].is_required() -> True   (no default)
                  omitted -> ValidationError (missing)
                  via jobs.run -> BAD_OPTIONS, loc = ['corridors', 0, 'cap_mw']

same reporting    validate_network : DANGLING_REF at buses[3].zone
                                     bus "bus-4": zone references missing zone "no-such-zone"
                  zonal chain      : DANGLING_REF at buses[3].zone
                                     bus "bus-4": carries no zone, and a zonal clearing needs …
                  same code: True    same path: 'buses[3].zone' vs 'buses[3].zone'
```

The required-`cap_mw` row carries the *reason*, which is the part a reader needs: if omission meant
"unbounded", the most permissive market on the network would be the one you get by forgetting a
field. And the page says the two zone faults report identically, naming the only thing that does
differ — when each is caught (`Network` construction versus the zonal chain reading the partition).

Re-verified after the correction: `Infinity`, `JSON.parse` and `RFC 8259` occur **0** times in the
rendered article body; `mkdocs build --strict` exit 0; 10362 fragment links, 0 broken; 19 docs
tests passed; both page snippets re-executed to their quoted output.
