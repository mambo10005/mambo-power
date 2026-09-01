# M6 research — zonal-redispatch groundwork

Wave M6 "zonal-redispatch" of the mambo-power epic, Step 1 research. Read-only; written
2026-08-27 against repo `C:\Claude Projects\mambo-power` @ `4cfd1d7` (branch `epic/01-foundation`,
M5 "multiperiod" merged and CI-green — `model.Period`/`Scenario.periods`, `Generator.ramp_up_mw`/
`ramp_down_mw`, `opf.multiperiod_dc_opf`, `market.solve_multiperiod`, jobs kind
`market.multiperiod` all present and read at their current, merged shape), pypsa 1.2.4,
pandapower 3.3.0 (`.venv/Scripts/python.exe -c "import pypsa, pandapower; print(...)"`), from
`.venv`. No source files touched; only reads plus one throwaway probe script run against the
installed package (`.venv/Scripts/python.exe <scratchpad>/zonal_pypsa_probe.py`).

**Scope amendment, 2026-08-27 (after first draft, same research session).** Three Step-1 scope
answers landed from the user, relayed by team-lead, mid-write: (1) redispatch cost basis =
each generator's own cost curve, both directions; (2) elastic demand participates in **both**
LPs — bid loads clear at the zonal price and may be curtailed or restored in redispatch, not
only generators moved; (3) of the three carry-overs in §8, only `Scenario.periods.max_length`
is in scope for M6. §3, §4, §6 and §8 below are written **against these settled answers**, not
as open menus — §2's "present options, don't pick" instruction still stands as originally
written, since it was not touched by the amendment. Where working out the settled decisions'
mechanical consequences required resolving a genuine ambiguity in *how* they compose (marked
explicitly in §3(a)), that resolution is presented as reasoned-through, not as a menu.

Headline (the rest is evidence):

- **§1: two committed fixtures already carry a usable multi-zone partition — no synthetic
  fixture data is needed for a first slice.** `case30`'s MATPOWER `AREA` column splits 30 buses
  into 3 groups (11/10/9); `case300`'s `ZONE` column splits 300 buses into 4 groups
  (122/80/63/35), and `case300`'s zone column is the one the importer already wires into real
  `model.Zone` entities and `Bus.zone` — `case30`'s multi-way column is `Bus.area`, which the
  importer does **not** turn into `Zone` entities. Every other fixture (`case14`, `case_ieee30`,
  `case57`, `case118`) is single-zone *and* single-area — unusable for either row family.
- **§4: with demand-side redispatch in scope, the invariant is `welfare(zonal+redispatch) <=
  welfare(nodal)`, not a cost inequality — and generation-cost-only ordering can actually
  invert.** Proved this can happen with a small, fully hand-checked numeric example: a
  network-congestion scenario where redispatch (curtailing a bid load rather than running an
  expensive generator, priced at the load's own marginal value **anchored at its zonal-cleared
  quantity**) reaches a point with **lower** generation cost (0 vs nodal's 1800) but **worse**
  welfare (0 vs nodal's 100) — because nodal maximises welfare, not minimises generation cost,
  and the anchored redispatch objective systematically over-curtails a load whose true value
  curve is concave. Flagged as the single most consequential open mechanical question for the
  design interview: see §3(a).
- **§5: PyPSA can express both halves — verdict YES, with a probe run on `case30` (its own
  committed `AREA` promoted to zones), not merely argued.** A zonal-ish clearing (intra-zone
  lines unconstrained, the 7 real inter-zone tie lines rated via `tests/_rated.py`, unmodified)
  solved `Optimal`; a redispatch LP built from PyPSA's own pseudo-generator pattern (this
  repository's own `NonConvexCostError`-avoiding trick is not available inside PyPSA, which has
  no native redispatch primitive) also solved `Optimal`, moving 13.36 MW up and 13.36 MW down.
  The resulting dispatch was checked feasible **independently**, with this repo's own PTDF
  (`numerics.ptdf`), against the network's real per-branch ratings: 0 violations across 41
  branches, tightest margin -2.04e-14 MW (i.e. one branch sits exactly on its rating). Full
  script and output below.
- **§7: the ADR-008 preamble duplication is real and already at its third-copy risk — measured
  fresh (`difflib.SequenceMatcher`, not re-asserted from the ADR) at 68 vs 71 lines, ratio
  0.791, 55 identical lines, between `dc_opf.py:560-627` and `multiperiod.py:322-392` —
  essentially unchanged from ADR-008's own M5-wave-head measurement.** M6 is exactly the wave
  ADR-008 named as needing to unify this *before* adding new row families, and this research
  treats that as binding, not optional.
- **The redispatch LP composes cleanly onto the existing row-family core (`_balance_row`/
  `_flow_limit_rows`) with a shifted RHS and shifted bounds, on both the generator and demand
  side — no new helper, no second solver.** See §3(c). This is the one place this research
  converges on a single answer rather than presenting options, because the row-family shape is
  dictated by ADR-007/ADR-008, not a design choice M6 gets to remake.

---

## §1 — Zone data on the committed fixtures

Probed directly (`matpower.load` on each of the six fixtures, then counted distinct
`Bus.zone`/`Bus.area` values and bus counts per value):

| fixture | buses | zones (col 11) | zone sizes | areas (col 7) | area sizes |
|---|---|---|---|---|---|
| `case14` | 14 | 1 | 14 | 1 | 14 |
| `case_ieee30` | 30 | 1 | 30 | 1 | 30 |
| `case30` | 30 | 1 | 30 | **3** | 11 / 10 / 9 |
| `case57` | 57 | 1 | 57 | 1 | 57 |
| `case118` | 118 | 1 | 118 | 1 | 118 |
| `case300` | 300 | **4** | 122 / 80 / 63 / 35 | 1 | 300 |

Command and full output:

```
$ .venv/Scripts/python.exe zone_probe.py
=== case14 (14 buses) ===   zones: 1 -> 1:14   areas: 1 -> 1:14
=== case_ieee30 (30 buses) === zones: 1 -> 1:30   areas: 1 -> 1:30
=== case30 (30 buses) ===   zones: 1 -> 1:30   areas: 3 -> 1:11, 2:10, 3:9
=== case57 (57 buses) ===   zones: 1 -> 1:57   areas: 1 -> 1:57
=== case118 (118 buses) === zones: 1 -> 1:118  areas: 1 -> 1:118
=== case300 (300 buses) === zones: 4 -> 1:122, 2:80, 3:63, 9:35   areas: 1 -> 1:300
```

**Both usable columns exist, on different fixtures, and they are not interchangeable in this
codebase today.** `io/matpower.py:331-332` builds `net.zones` (real `model.Zone` entities) and
sets `Bus.zone` **only from the ZONE column** (raw col 11, 0-indexed `row[10]`):

```python
zone = _label(row[10])
zones.setdefault(zone, Zone(id=zone))
...
Bus(..., zone=zone, area=_label(row[6]))
```

`model/network.py:99-105` then validates every `Bus.zone` resolves to a `net.zones[].id` — so
`Bus.zone`/`net.zones` is a first-class, validated relationship. `Bus.area` (raw col 7,
`row[6]`) is carried as a bare free-form string with **no corresponding entity type and no
cross-reference check** (`entities.py:43`: "Free-form area label"). Consequence: `case300` is
the *only* committed fixture with a real, importer-populated, validated multi-zone partition
today; `case30`'s 3-way split lives on `Bus.area`, a field the market layer would have to read
directly (bypassing `Zone`) or a test helper would have to promote into `Bus.zone`/`net.zones`
first.

**Recommendation for the design interview (not picked here): both are usable, for different
reasons, and neither requires committing new fixture data.**

1. `case300` as-is exercises the real `Zone`-entity path end to end (300 buses, 4 zones,
   3 zone-boundary crossings by construction) but is the largest fixture in the repo — every
   other market-wave oracle test in this codebase (M3 AC-1's PyPSA parity, M4/M5's own AC-6
   fixtures) uses `case14` or `case30` for anything that needs to be hand-inspectable, reserving
   `case300` for a "does it even solve at this size" check (`test_opf_vs_pypsa.py`'s own
   `WIDE_CASES` treatment is exactly this pattern — a wider tolerance for the one large fixture,
   not the fixture everything else is built around).
2. `case30`'s `AREA` column gives a much more inspectable 3-zone, 30-bus partition, but needs a
   `tests/_zones.py`-style test-time promotion (`tests/_rated.py`'s "documented, test-time
   transformation of an already-owned fixture" pattern, applied to `Bus.area` -> `Bus.zone`/
   `net.zones` instead of to `Branch.rating_mva`): copy each bus's own `.area` into `.zone`,
   build one `Zone(id=...)` per distinct area value, return a fresh `Network` via
   `model_copy(deep=True)`. No invented boundary, no new fixture file — the partition is
   `case30`'s own MATPOWER-published data, merely relabelled onto the field the model already
   validates. This is what §5's probe below actually does (informally, inline, not as a
   committed helper) to get a workable zone fixture at a size that is still hand-checkable.
3. **A from-scratch synthetic-partition rule (electrical-distance clustering, a rated cut-set on
   `case14`) is not needed as a fallback**, because two committed fixtures already clear the
   bar the task set ("a fixture where every bus is in one zone cannot exercise zonal clearing").
   If the design interview wants a *third*, smaller (`case14`-scale) fixture for a fully
   hand-derivable KKT-style unit test — mirroring how `test_opf_multiperiod.py`'s AC-2 test
   hand-derives a ramp case — the same `Bus.area`-promotion trick does not apply (`case14` has
   only 1 area too), so that would be the one place a genuinely synthetic rule (e.g. splitting
   the ring at its two weakest-reactance branches) would need inventing. Flagged as a possible
   scope item, not resolved here.

---

## §2 — The zonal clearing LP: formulation options

`NetworkArrays` (`numerics/arrays.py`) carries **no zone information at all** today — no
`bus_zone` array, no zone-id list. Every option below needs a bus->zone index array threaded in
from the caller (`market.zonal`, by analogy with how `market.nodal.load_bid_coeffs` builds a
load-index-keyed mapping straight off `net.loads`/`arr.load_ids` rather than extending
`NetworkArrays` itself) — extending `NetworkArrays` is possible but not obviously required by
any option below, since a `(n_bus,) -> zone_id` array built once in `market/zonal.py` from
`net.buses` (`arr.bus_ids` order) is sufficient for every option's bus-to-zone grouping.

### (a) Per-zone copper plate, unconstrained inter-zonal exchange

Each zone gets its own balance row (`Σ p_g in zone z − Σ p_d in zone z == Σ load_zone_z`), but
with **no** limit on the net flow between zones. Algebraically this is `_balance_row` called
once per zone instead of once system-wide — a direct reuse of the existing helper, zero new row
*shape*, only a different column partition per row.

**This is not distinguishable from "no network" / a single system-wide price.** With inter-zonal
exchange literally unconstrained, the LP's only requirement is that the *sum* of the per-zone
balances equals the system-wide balance dc_opf already builds — the zone boundaries add no
binding constraint anywhere, so the optimal dispatch, total cost and the *shadow price of every
zone's balance row* are all identical to the single system-wide balance row's dual (one number,
the same one, broadcast to every zone) — i.e. one national price wearing per-zone labels. Its
dual is technically "one price per zone" in the sense of one row per zone, but every zone's
price is provably the same number, so it never demonstrates the "zonal ≠ nodal" distinction the
epic's own comparison result exists to show. Useful only as the degenerate check (an equivalent
of M5's AC-4 "1 period ≡ nodal" reduction — here, "1 zone ≡ every-zone-unconstrained ≡ system
copper-plate"), not as the wave's actual formulation.

### (b) Per-zone copper plate with inter-zonal transfer limits (NTC/ATC-style)

Adds a net-export variable per zone, `f_z`, bounded by a transfer capacity derived from that
zone's own **rated cut-set** — the branches whose `from_bus`/`to_bus` sit in different zones
(exactly what §5's probe below identifies and rates via `tests/_rated.py`, unmodified). Two
sub-shapes, not resolved here:

- **b1 — one scalar `f_z` per zone**, balance row `Σ p_g,z − Σ p_d,z − f_z == load_z`, plus
  `Σ_z f_z == 0` (system-wide conservation) and `|f_z| <= cap_z` where `cap_z` = sum of the
  cut-set branches' own ratings touching zone `z`. Cheapest to build (one new column per zone,
  one new row family the shape of `_balance_row` plus a bound), but a single scalar cannot
  distinguish "zone A exports to zone B" from "zone A exports to zone C" when A borders both —
  a real limitation on any fixture with more than 2 zones and more than one tie corridor (both
  `case30` and `case300` qualify).
- **b2 — one `f_{z1,z2}` per ordered zone pair actually tied** (only the pairs that have at
  least one cut-set branch get a variable), each bounded by that corridor's own cut-set rating
  sum. More faithful, more columns/rows (`O(n_zone^2)` worst case, but bounded by the number of
  *actual* tie corridors, which is small on both candidate fixtures — `case30` has exactly one
  corridor per zone pair in the §5 probe's own zone/branch crossing, not checked exhaustively
  here). `f_z` (as in b1) is then `Σ_{z2} f_{z,z2}`, so b1 is b2's degenerate aggregate, not a
  different model — a natural "start with b1, generalize to b2 if a fixture needs it" path.

Either sub-shape's balance row is still `_balance_row`, called with a zone's generator/demand
columns as before, plus the new `f_z`/`f_{z1,z2}` column(s) added as an extra injection or
withdrawal column depending on sign convention — no new row-family helper, just a wider column
set handed to the existing one. The transfer-limit bound itself (`|f_z| <= cap_z`) is a plain
variable bound (`addVars`'s own lower/upper, exactly like a generator's `[p_min, p_max]`), not a
new row at all.

**One price per zone, as a dual:** the shadow price of zone `z`'s own balance row — the direct
zonal analogue of `dc_opf`'s single balance-row dual being the system-wide energy price. This is
real, not degenerate, whenever some `f_z`/`f_{z,z2}` bound actually binds (unlike (a)).

**What's missing from the model today:** no entity carries a zone-to-zone or zone cut-set
transfer capacity. §5's probe computes one ad hoc, in-script, by summing the derived
`Branch.rating_mva` of every branch whose two ends fall in different zones — the same
"test-time-derived, no new fixture data" convention `tests/_rated.py` already establishes for
per-branch ratings, extendable to a per-zone-pair aggregate without inventing a new committed
number.

### (c) Flow-based zonal clearing (zonal PTDFs)

Aggregates the existing bus-level PTDF matrix (`numerics.ptdf`, already computed by `dc_opf`/
`multiperiod_dc_opf`) into a zone-level PTDF via a generation-shift key (GSK) — a weighting that
maps a zone's net position onto individual bus injections, then through the existing bus PTDF to
real per-branch flows. This is the option that actually enforces the *physical* network's flow
limits during zonal clearing (not a synthetic transfer cap), which real flow-based market
coupling does for exactly this reason. It "belongs" in the sense of being the most realistic of
the three, but costs the most: it needs (1) a GSK convention the model has no field for today
(pro-rata by generation capacity, by load share, or flat — all common, none committed here), and
(2) the zone-level flow-limit row is then `PTDF_zonal[k, z] = Σ_bus GSK[bus,z] * PTDF[k, bus]`
per branch `k`, built once outside `_flow_limit_rows` and handed in as if it were a per-column
PTDF — mechanically reusable (the row family doesn't care whether its "injection column" maps to
a bus or a zone-aggregate net position), but the GSK computation itself is new numerics, not a
row-family reuse.

**Recommendation for the interview:** (b1) is the cheapest complete answer that still produces a
genuine second price ("zonal ≠ nodal", satisfying the epic's comparison-result requirement) and
reuses `_balance_row` verbatim; (c) is the more defensible "real zonal market" model but is a
strictly bigger slice. (a) is worth keeping only as a degenerate-case regression test, the way
M5 kept `n_periods=1` as an exactness check rather than a delivered feature.

---

## §3 — The min-cost redispatch LP

**Settled by the user (relayed by team-lead), not re-opened here:** the cost basis is each
generator's own cost curve, both directions (up at marginal cost, down credited at marginal
cost) — no new model fields; elastic demand participates in **both** LPs, curtailable and
restorable in redispatch, not frozen. §3(a) below works out the one genuine mechanical ambiguity
this leaves — *what "marginal cost" means as an LP coefficient* — because the answer determines
whether the redispatch LP is even a different optimization from re-solving nodal outright, which
matters for every downstream section (§4, §6).

### (a) Cost/value basis: the marginal rate must be anchored at the zonal operating point

**Adopted reading, and why it is the only one consistent with the rest of the brief:** each
generator's `Δp+_g` is priced, and `Δp-_g` credited, at that generator's own marginal cost
**evaluated at its zonal-cleared dispatch `p0_g`** — a single linear rate per generator
(`mc_g(p0_g) = c1_g + 2·c2_g·p0_g` for a quadratic `cost_coeffs` row, or the slope of whichever
`_convex_pwl_segments` segment contains `p0_g` for a PWL generator — both derived from data
`dc_opf` already reads, so "no new model fields" holds). The demand side mirrors it exactly
(§3(b)): each bid load's `Δd-_d`/`Δd+_d` is priced/credited at `mv_d(d0_d)`, its own marginal
*value* at its zonal-cleared quantity `d0_d`, read off the same polynomial `(v2,v1,v0)` or
`_concave_pwl_segments` data `load_bid_coeffs` already extracts.

This is a specific reading of "own cost curve" — an **anchored linear rate**, not the curve's
full nonlinear integral re-applied to the delta — and it is not a free stylistic choice; it is
forced by two things simultaneously true elsewhere in this brief:

1. **The redispatch LP's own constraints must reconstruct nodal's exact feasible set** (§4a) —
   same generator/load bounds, same real network. If the redispatch *objective* were also the
   *exact* welfare function nodal uses (the full, non-anchored `cost_g(p)`/`value_d(d)` curves),
   the redispatch LP would be **the nodal welfare LP itself**, with `p0`/`d0` playing no role at
   all — an LP/QP's global optimum does not depend on where a caller "starts" it. Every fixture
   would then redispatch to *exactly* nodal's own point regardless of what the zonal stage
   picked, making `welfare(zonal+redispatch) == welfare(nodal)` an **identity**, never a strict
   inequality, and erasing the "paired positive case" §4 asks for. Zonal clearing would become
   vestigial — computed, then thrown away.
2. **"No new model fields" rules out the other way to keep redispatch path-dependent** — bounding
   `Δp+`/`Δp-`/`Δd+`/`Δd-` to something narrower than the full `[0, p_max−p0]`-style range would
   also preserve path-dependence (a genuine "how far can this be redispatched" limit), and
   `Generator.ramp_up_mw`/`ramp_down_mw` (M5) is an *existing* field that could in principle serve
   that role for generators — but it is optional (many fixtures carry no ramp limit at all), has
   no load-side analogue whatsoever (`Load` carries no comparable field), and the settled scope
   answer is about demand curtailment specifically, not about reusing ramp limits. Anchoring the
   *rate* rather than bounding the *range* is the one mechanism that applies uniformly to both
   generators and loads without inventing anything.

**Consequence, stated plainly because it is a real economic property of this design, not a
defect to paper over:** an anchored linear rate is exact for a **flat** (`c2==0`/`v2==0`) cost or
value curve, but for a genuinely curved one it misprices any redispatch move that travels far
from `p0`/`d0` — understating a convex generator cost's true rise for a large `Δp+`, and
understating a concave load-value curve's true rise (toward `p=0`) for a large `Δd-`. §4(a)
below shows this bias is not a corner case: it can flip which of two economically-legitimate
actions (curtail a load vs. run an expensive generator) looks cheaper to the redispatch LP,
relative to what the *true* curve says.

### (b) Elastic demand redispatch: how bid value enters the objective, mechanically

Reopened (per the settled scope answer), not frozen. Each bid load gets **two** new nonnegative
redispatch columns, mirroring the generator pair exactly: `Δd+_d ∈ [0, d_max_d − d0_d]`
(*restore* — consume more, up to the load's own zonal-stage upper bound) and
`Δd-_d ∈ [0, d0_d − d_min_d]` (*curtail* — consume less). **The load's own marginal value at
`d0_d` must enter the objective, or curtailment is free and the LP always dumps load before it
ever touches an expensive generator** (the team lead's own stated reason, and mechanically
obvious once stated: with no value term, `Δd-_d` has zero objective cost and only ever *helps*
satisfy the balance row more cheaply than any `Δp+_g` with `mc_g > 0` could). Sign convention,
the demand-side mirror of the generator pair: `Δd-_d` (less consumed) sits on the **injection**
side of `_balance_row` (freeing up supply, the same role `Δp+_g` plays) with objective
coefficient `+mv_d(d0_d)` (a real cost — lost value); `Δd+_d` (more consumed) sits on the
**withdrawal** side with objective coefficient `−mv_d(d0_d)` (a credit — value delivered),
exactly the sign roles `dc_opf`'s own existing demand columns already carry
(`dc_opf.py:113-117`'s `−1`-signed balance term, `dc_opf.py:643-645`'s `−v1` objective
convention) — this redispatch pair is not a new sign idiom, it is the existing one applied to a
delta instead of to `p_d` itself.

**On "the same hypograph rows M4's builder already has":** for a *piecewise-linear* bid, the
anchored rate `mv_d(d0_d)` is found the same way a PWL generator's anchored rate is (§3a) — by
locating which segment of `_concave_pwl_segments(bid.points)` contains `d0_d` and reading its
slope — reusing the **segment-derivation** M4/dc_opf already has, not by adding new hypograph
*rows* to the redispatch LP itself (the redispatch objective is linear in `Δd+`/`Δd-`, so it
needs a slope value, not an epigraph/hypograph row family of its own). A genuinely different
reading — literally re-adding `_hypograph_rows` to the redispatch LP over `Δd-`'s own range, with
its own free `val_d` column re-based at `d0_d` — is mechanically possible but was rejected as the
default here for the same path-independence reason as §3(a)'s point 1: over a large enough
`Δd-`, that construction converges toward re-deriving the true value curve exactly, eroding the
same anchoring that keeps redispatch meaningfully different from nodal.

### (c) Mapping onto the existing builder — generator and demand deltas both, symmetrically

The redispatch LP is a `dc_opf` instance with a **shifted objective and shifted bounds on both
sides of the market**, reusing `_balance_row`/`_flow_limit_rows` verbatim, exactly the way
`multiperiod_dc_opf` already reuses them per period (module docstring, `multiperiod.py:9-16`):

- **Columns:** `Δp+_g`/`Δp-_g` per generator (as before) *plus* `Δd+_d`/`Δd-_d` per bid load
  (§3b) — four nonnegative column families total, the direct extension of `multiperiod.py`'s own
  charge/discharge pair pattern to two participants instead of one storage unit.
- **Balance row:** `_balance_row(injection_cols=[Δp+ cols, Δd- cols], withdrawal_cols=[Δp- cols,
  Δd+ cols], fixed_mw=total_fixed_load − Σ_g p0_g + Σ_d d0_d)` — `_balance_row`'s existing
  signature, unmodified, called with four column groups instead of two and a fixed RHS that
  removes **both** the generators' and the bid loads' zonal-cleared quantities before the delta
  columns are added (the double-counting contract, `dc_opf.py:129-141`, applied symmetrically:
  `p0` was already counted as supply, `d0` was already counted as demand, and both must come out
  of the RHS the same way a bid-load's own historical `p_mw` already does in `dc_opf` today).
- **Flow-limit rows:** `_flow_limit_rows` unchanged in shape, with `const_k` extended to fold in
  both `− Σ_g PTDF[k, gen_bus[g]]·p0_g` and `+ Σ_d PTDF[k, load_bus[d]]·d0_d` (mirroring the sign
  each already carries in `dc_opf`'s own flow formula, `dc_opf.py:710-717`'s existing
  "fold every fixed contribution into `const_k`" convention, extended to the zonal-stage
  quantities instead of only the network's raw fixed load).
- **Objective:** linear coefficients `+mc_g(p0_g)` on `Δp+_g`, `−mc_g(p0_g)` on `Δp-_g`,
  `+mv_d(d0_d)` on `Δd-_d`, `−mv_d(d0_d)` on `Δd+_d` (§3a/§3b) — purely linear, **no Hessian call
  at all** in this formulation, since the anchored rate is a constant per generator/load, not a
  function of the delta column itself (a genuine simplification the anchoring buys, on top of
  keeping the LP path-dependent).

No new row-family helper is needed; `_add_rows`, `_dense_csr`, `_balance_row`, `_flow_limit_rows`
are sufficient as-is on both sides of the market. This remains the one place in this research
that converges rather than presents options: ADR-007/ADR-008 already fix the shape ("further
column/row families on `dc_opf`, not separate solvers"), and the redispatch LP's own
structure — a DC-OPF with different bounds, a different RHS constant, and a purely linear
objective — has no genuine alternative formulation that would still qualify as "the one
builder".

---

## §4 — The two invariants: provable or measured? (plus the cost-ordering corollary)

### (a) `welfare(zonal + redispatch) <= welfare(nodal)`, restated in welfare terms

With demand-side redispatch settled in scope (§3), the invariant is on **welfare** — bid value
served minus generation cost — not on generation cost alone, and the proof structure carries
over from the cost-only version cleanly: **provable, and it is the redispatch LP's constraints
that must reconstruct the nodal LP's exact feasible set — not its objective.** Let `S_nodal` be
the nodal welfare LP's feasible set (bus balance, real PTDF flow rows, generator bounds, *and*
bid-load bounds `[0, p_mw]` — every degree of freedom nodal itself has, generation and demand
both) and `W(x) = Σ_d value_d(d) − Σ_g cost_g(p)` the true welfare function. Nodal finds
`max_{x in S_nodal} W(x)`. The redispatch LP's own constraints (§3c) guarantee its solution
`x_final = (p0+Δp+−Δp-, d0+Δd+−Δd-)` is a member of `S_nodal` — same balance row, same real flow
rows, same generator *and* load bounds, not the zonal approximation's relaxed/aggregated ones.
Therefore `W(x_final) <= max_{x in S_nodal} W(x) = W(x_nodal)`. As before, this holds
**regardless of which LP solved for `p0`/`d0`** (§2's options) and **regardless of the
redispatch objective's own anchored rate** (§3a) — both only affect *which* feasible `x_final`
is reached, never whether it is feasible, and feasibility against the *true* welfare function's
exact domain is all the inequality needs.

**What makes it strict, for a paired positive case:** unchanged in kind from the cost-only
version — a fixture where the zonal LP's own approximation loses information the nodal LP would
use (a branch binding at the true nodal optimum that the zonal formulation cannot see). §5's
probe is exactly this shape by construction (7 of 41 case30 branches rated for the zonal step,
all 41 rated for redispatch) and produced a nonzero redispatch (13.36 MW moved both ways) on the
**generation** side alone, before demand-side redispatch is even added — the mechanism that
makes the inequality strict is present and already measured on a real fixture. Once demand
redispatch is added, strictness is if anything *easier* to obtain (more ways for `x_final` to
differ from `x_nodal`), not harder.

### (b) Does generation-cost-only ordering survive as a corollary? **No — it can invert, and it
does on a fully worked example.**

The team lead's suspicion is correct, and the mechanism is structural, not a corner case of the
anchored-rate reading specifically: **nodal maximises welfare, not generation cost minimised.**
A feasible point of `S_nodal` can have *lower* generation cost than nodal's own optimum while
having *worse* welfare overall, whenever it also serves correspondingly less (or less valuable)
demand — nothing in feasibility-plus-optimality-over-welfare constrains generation cost's own
ordering in isolation. This half of the argument needs no assumption about the redispatch
objective at all. What the anchored-rate reading (§3a) adds is a concrete *mechanism* by which a
real redispatch LP actually reaches such a point, not merely "is not excluded from" reaching one.

**Worked example (hand-solved, no network code run — the mechanism is economic, not
topological, so a minimal sketch isolates it cleanly).** One load `L`, concave value curve
`value(d) = 100d − 0.25d²` (marginal value `100 − 0.5d`, so `v1=100, v2=−0.25`), bound
`d ∈ [0,100]`. Two generators: `G1` cheap and flat (`cost=30`/MWh, unlimited), `G2` expensive and
flat (`cost=90`/MWh, unlimited). A single network bottleneck — a branch with `rating_mva = 0` on
`G1`'s only path to `L`'s bus — makes any `p1 > 0` physically infeasible; `G2` is unconstrained.

- **Nodal** (true bottleneck respected, `p1` forced to 0): maximise `value(d) − 90·d`. First-order
  condition `100 − 0.5d = 90` gives `d* = 20`. `cost = 90·20 = 1800`, `value = value(20) = 1900`,
  **`welfare = 100`**.
- **Zonal** (coarse network step, misses the bottleneck): `G1` looks reachable, so the zonal LP
  fills the cheap unit first. Marginal value at `G1`'s own bound (`d=40`, unlimited in this toy)
  is `100−0.5·40=80 < 90` (`G2`'s cost), so it is not worth going past `G1`'s capacity — zonal
  optimum `d0 = 40`, `p1_0 = 40`, `p2_0 = 0`. **This dispatch is infeasible on the real network**
  (uses the blocked path) — exactly the trigger redispatch exists for. (Its own "welfare" number,
  2400, is not a meaningful comparison point — it is priced on a dispatch the real network cannot
  deliver.)
- **Redispatch** (real bottleneck reinstated; anchored rates from the zonal point `p0=(40,0)`,
  `d0=40`): `G1` must come down to 0 (`Δp1- = 40`, forced by the real flow-limit row — feasibility,
  not a choice), credited at `mc_{G1}(p0=40) = 30`/MWh. The balance must then be closed by some
  mix of `Δp2+` (costed at `mc_{G2}(0) = 90`/MWh, flat) and `Δd-` (costed at the **anchored** rate
  `mv_L(d0=40) = 100−0.5·40 = 80`/MWh — a single rate, not the true curve). Per MWh of `d`
  removed, the LP saves `90` (one less MWh from `G2`) at a charged cost of `80` — net objective
  gain `10`/MWh — so the LP **prefers curtailing over generating at every margin down to `d=0`**,
  and does exactly that: `Δd- = 40`, `d_final = 0`, `Δp2+ = 0`. Final dispatch `p1=0, p2=0, d=0`:
  **`cost = 0`**, `value = 0`, **`welfare = 0`**.

| | generation cost | value served | welfare |
|---|---|---|---|
| nodal (true optimum) | **1800** | 1900 | **100** |
| zonal + redispatch (anchored) | **0** | 0 | **0** |

`welfare(zonal+redispatch) = 0 <= welfare(nodal) = 100` — the invariant holds, strictly, exactly
as §4(a) proves it must. **But `cost(zonal+redispatch) = 0 < cost(nodal) = 1800` — the
generation-cost-only ordering is inverted.** The mechanism is precise, not a fluke: nodal's own
optimality condition correctly finds the crossover between `L`'s *true, continuously declining*
marginal value and `G2`'s cost at `d*=20`; the redispatch LP's anchored objective instead compares
`G2`'s cost against a single **stale** rate (`L`'s marginal value back at the zonal-cleared `d0=40`,
which is *lower* than the true marginal value everywhere below `d=40`, since the curve is
concave) — so it keeps finding curtailment "cheaper" all the way down to zero, past the point
where the true curve says it stops being worth it. **This is a systematic bias, not specific to
this fixture:** any concave/declining bid-value curve (or, symmetrically, any convex generator
cost curve on the generation side) will bias an anchored-rate redispatch LP toward
**over-curtailing demand relative to the true-welfare-optimal amount**, because the anchor
understates the true marginal value of the units furthest from the anchor point. It does not
threaten §4(a)'s welfare inequality (which needs only feasibility, not objective accuracy) but it
is real economic behaviour the design interview should see stated plainly, since it means the
`cost` figure in any result type (§6) is informative but must never be read as "how well zonal
redispatch approximates nodal" — only the welfare figure answers that.

### (c) `redispatched flows feasible in pf.dc`

**Checkable exactly as the epic spec's phrasing implies: feed the redispatched injections into
the existing `pf.dc`/PTDF machinery and check every branch against its real rating — no new
numerics needed.** §5's probe does precisely this (independently of the PyPSA LP that produced
the redispatch): `numerics.ptdf.ptdf` + `numerics.bbus.pf_shift`, the same construction
`opf.dc_opf` itself uses to build its flow-limit rows and the same one `opf.solve_dc_opf` uses to
report `OpfBranchFlowResult.p_from_mw` (`opf/__init__.py:157-161`) — not a new code path. The
mambo_power-internal version of this check would use `mambo_power.pf.dc.solve` directly (the
epic verification table's own wording, `pf.dc`) rather than the PTDF pieces the probe used ad
hoc, but they are the same underlying linear model.

**Tolerance:** the probe's independent recomputation matched the LP's own constraint enforcement
to `-2.04e-14` MW margin (i.e. agreement to float64 noise) — well inside any `1e-6`-scale
tolerance this repository uses elsewhere for a flow-feasibility check (e.g.
`SIMULTANEITY_ABS_TOL_MW = 1e-6` in `test_market_multiperiod_vs_pypsa.py`). A `1e-6` MW
tolerance on the redispatched-flow-vs-rating check looks like the right order of magnitude by
analogy, pending an actual measured worst case on whichever fixture M6 ships.

---

## §5 — Oracle viability for the T2 row: PyPSA, probed

**Verdict: YES**, both halves, with a probe actually run (not merely argued) on `case30`, its
own committed `AREA` column promoted in-script to a 3-zone partition (§1's recommendation 2).
Ran via `.venv/Scripts/python.exe <scratchpad>/zonal_pypsa_probe.py` (script preserved in the
scratchpad, not committed — read-only wave). Key output:

```
zone sizes: {'2': 10, '3': 9, '1': 11}
transformer rows (tap != 0): 0
lines: 34 intra-zone (unconstrained), 7 inter-zone (rated)
zonal-ish solve: ok optimal
zonal objective (linear part, no c0): 574.7471644036121
redispatch solve: ok optimal
total up-redispatch MW: 13.360476554335683  total down-redispatch MW: 13.360476554335696
redispatch objective (up/down cost only): 92.0748906470066
sample final dispatch (first 5 gens): {'gen-1': 27.128814903463116, 'gen-2': 63.694926229263
62, 'gen-3': 21.087198710457, 'gen-4': 22.862989575855067, 'gen-5': 21.154359043969645}
independent (mambo_power PTDF) flow check: n_branch = 41 violations = 0
  tightest margin (rating - |flow|), MW: -2.042810365310288e-14
```

**(a) Zonal copper-plate clearing — expressible, via rated-vs-unrated line partitioning, not a
native PyPSA primitive.** PyPSA has no "zone" or "market" concept; the probe builds it by
reusing the standard `import_from_pypower_ppc` bridge (`test_opf_vs_pypsa.py`'s already-proven
`p_set`-clearing fix, applied unchanged) and setting every **intra-zone** line's `s_nom` to an
effectively-unconstrained value while every **inter-zone** (tie) line keeps its real
`tests/_rated.py`-derived rating — §2 option (b)'s per-branch-cut-set idea, expressed through
PyPSA's own rating field rather than through a bespoke NTC constraint. `case30` has zero
transformers at this fixture (`tap != 0` count: 0), so the `test_market_multiperiod_vs_pypsa.py`
transformer caveat (rate lines only, leave transformers unconstrained) does not even arise here
— a simplification specific to `case30`, not general.

**(b) Redispatch LP — expressible, only via PyPSA's own pseudo-generator pattern** (the ADR-007
"pseudo-generator trick" this repository's own engine deliberately rejected for `dc_opf`, but
which is the *only* way to express an asymmetric per-generator up/down cost in PyPSA, which has
no native redispatch/reserve-market component). The probe: freezes each generator at its own
zonal dispatch (`p_min_pu == p_max_pu == p0/p_nom`), adds one `Generator` per unit for "up" (
`sign=+1`, cost = own marginal cost + $5/MWh) and one for "down" (`sign=-1`, cost = own marginal
cost − $5/MWh, i.e. a redispatch *payment* for reducing output, not a credit — deliberately kept
positive-cost so PyPSA's minimiser has no incentive to move power around for free), on the
**fully-rated** network (all 41 lines rated, not just the 7 tie lines). Solved `Optimal`,
13.36 MW moved in each direction — genuinely engaged, not a degenerate zero.

**Feasibility of the result was checked a second, independent way** — not trusting PyPSA's own
LP solve to certify itself — by recomputing the final per-branch flow directly with this
repository's own `numerics.ptdf`/`numerics.bbus.pf_shift` against the real per-branch ratings:
zero violations across 41 branches, and the tightest margin is `-2.04e-14` MW (a branch sitting
exactly at its rating, to float noise) — this is the strongest form of evidence for §4(c)'s
"redispatched flows feasible in pf.dc" invariant, since it is not PyPSA re-checking its own
answer.

**What must be held fixed on the oracle side (the M5 lesson, applied here).** M5's carry-over
("a sabotage applied to shared fixture data is not a sabotage") generalises directly: any
zonal-vs-nodal parity test built on this pattern must **not** let the same rating derivation, the
same zone assignment, or the same $5 up/down adder move on both the mambo_power side and the
PyPSA oracle side simultaneously from a single shared source that a sabotage could corrupt once
and have both sides agree by construction. Concretely: `tests/_rated.py`'s `rated_network` is
already shared fixture data read by both sides (as it is in every existing parity test in this
repo) and that is fine — M5's lesson is not "never share fixture code", it is "know which
*engine-internal* computation the shared data cannot let you distinguish a fault in". Here, the
place to watch is the up/down **cost basis** and the **zone assignment**: if M6's own zonal
market layer derives its transfer-cap/GSK data from the *same* helper the PyPSA oracle bridge
reads (mirroring the `tests/_storage.py`/`efficiency_store=unit.efficiency_charge` trap M5 hit),
a sabotage of that shared derivation would move both sides together and prove nothing — the
fix pattern is the same one M5 used: sabotage the **engine's own** row/column, holding the
oracle's own construction fixed, and confirm the residual the parity test reads is one that
transposition/relabelling cannot leave invariant.

---

## §6 — The nodal-vs-zonal comparison result

With demand-side redispatch settled in scope (§3) and the invariant restated as welfare rather
than cost-only (§4b), the comparison result is genuinely **three-way** — generator deltas, load
curtailment deltas, and an operator/welfare gap — not the two-way (dispatch + generator deltas)
shape a cost-only reading would have suggested. Recommended shape, following directly from the
existing `results/` conventions and the M5 carry-over:

- **Zonal prices** — one row per zone, the dual of that zone's own balance row (§2's "one price
  per zone" as a dual), shaped like `BusLmpResult` but keyed by zone id instead of bus id — a
  new small row type, since no existing type is bus-agnostic in this way.
- **Zonal dispatch** — reuse `GenDispatchResult`/`LoadDispatchResult` verbatim (ADR-006's reuse
  discipline, already the pattern `results/market.py` and `results/multiperiod.py` both follow):
  the zonal LP still dispatches individual generators/loads, it is only the network constraint
  that is coarser, so the row shape carries over exactly.
- **Generator redispatch deltas** — a new row, `id`, `bus`, `delta_up_mw`, `delta_down_mw` (both
  `>= 0`, mirroring `StorageDispatchResult`'s nonnegative-pair convention rather than one signed
  column: §3's anchored up/down rate needs to be readable back out of the result, and a single
  signed net number would erase whether both directions were used, exactly the way
  `min(charge_mw, discharge_mw)` is a real, tested question for storage — AC-3 in M5's own
  multiperiod result).
- **Load curtailment/restoration deltas — the direct demand-side mirror of the generator-delta
  row, not an afterthought.** `id`, `bus`, `delta_restore_mw` (`Δd+`), `delta_curtail_mw` (`Δd-`),
  both `>= 0`, same nonnegative-pair reasoning as the generator row (§3b's `Δd+`/`Δd-` pair is a
  real distinction — a load fully curtailed then partly restored is a different, and readable,
  story from one merely served less than its zonal quantity). This row type does not exist
  anywhere in `results/` today (`LoadDispatchResult` carries a served quantity, not a delta), so
  it is new, alongside the generator-delta row.
- **Operator/welfare gap, three related figures, not one, and the result type must not conflate
  them (§4b's own finding depends on keeping these separate):**
  - `redispatch_payment` — `Σ mc_g(p0_g)·(Δp+_g−Δp-_g) + Σ mv_d(d0_d)·(Δd-_d−Δd+_d)`, the
    redispatch LP's own (anchored-rate) objective value — a *settlement* figure, what the
    mechanism itself charges/credits, not a welfare measure.
  - `welfare_gap` — `welfare(nodal) − welfare(zonal+redispatch)`, computed from the *true*
    `cost_coeffs`/`pwl_costs`/bid data at the final dispatch/quantities, compared against
    `market.nodal`'s own welfare on the identical network — this is what §4(a)'s invariant is
    actually about, and it is `>= 0` by that proof.
  - `generation_cost_gap` — `cost(zonal+redispatch) − cost(nodal)` (both true generation cost,
    not the redispatch payment) — reported as a genuine diagnostic, explicitly documented as
    **not sign-constrained** (§4(b)'s finding: this can be negative), so a reader does not mistake
    it for a second copy of the welfare invariant.

  All three close the gap M5's carry-over #2 (A23) flagged for `MarketNodalResult`/
  `MarketPeriodResult` ("the settlement identity's right-hand side is not computable from a
  result object") — each is directly computable from the result object without a second solve.
- **Per-branch flows and flow duals (M5 carry-over A23, explicitly binding on M6 per that
  carry-over's own text: "would also give zonal redispatch the per-branch surface it needs
  anyway").** Reuse `OpfBranchFlowResult` verbatim (`results/opf.py:39-47`) — it already carries
  `id`, `from_bus`, `to_bus`, `p_from_mw`, `flow_limit_dual`, which is exactly what §4(c)'s
  feasibility check and §2's zonal-vs-nodal flow comparison both need, and it is already a
  `_Row`-shaped, `extra="forbid"`/`frozen=True` model. Neither `MarketNodalResult` nor
  `MarketPeriodResult` carries this today (A23's own finding); a `MarketZonalResult` would be
  the **first** market result type to carry branch rows if it adds them, which is worth noting
  explicitly to whoever designs it: this is new ground for `results/market.py`'s pattern, not
  an established one to copy.

**Composition:** `MarketZonalResult` should mirror `MarketMultiperiodResult`'s top-level shape
(`provenance`, `status`, `message`, then the substantive rows) rather than `MarketNodalResult`'s
flatter one, because — like the multiperiod result — it genuinely has two "layers" (the zonal
clearing's own rows, and the redispatch layer on top), the same reason `MarketMultiperiodResult`
nests `MarketPeriodResult` rather than flattening everything. All new row types should follow
the repo-wide convention already universal in `results/`: `model_config = ConfigDict(extra=
"forbid", frozen=True, allow_inf_nan=False)`.

---

## §7 — ADR-008's preamble unification

**Measured directly on the current tree (`4cfd1d7`), with `difflib.SequenceMatcher`, not
re-asserted from ADR-008's own text:**

```
$ .venv/Scripts/python.exe -c "import difflib; ..."
dc_opf span lines 560-627: 68 lines
multiperiod span lines 322-392: 71 lines
ratio: 0.7913669064748201
identical lines (matching blocks sum): 55
```

`dc_opf.py` lines 560-627 against `multiperiod.py` lines 322-392 — the same two spans ADR-008
itself named ("dc_opf.py:560-627 against multiperiod.py:322-390") — measure at 68/71 lines,
difflib ratio 0.791, 55 identical lines: essentially unchanged from ADR-008's own "68/69 lines, a
difflib ratio of 0.788", "54 identical lines" at the M5 wave head. **The duplication has not
shrunk on its own between M5's close and M6's start** — confirming ADR-008's own framing that M6
would make it a third copy if left alone is still the live situation, not a stale worry. The
duplicated span covers, verbatim per ADR-008's own itemisation and
re-confirmed here by reading both files in full: the `cost_coeffs.shape != (n_gen, 3)` check, the
`elastic_load_idxs` range check (`0 <= idx < n_load`), the `v2/v1/v0` polynomial-bid fill loop,
both convexity guards (`NonConvexCostError` for `c2 < 0`, `NonConcaveBidError` for `v2 > 0`,
including near-identical message text differing only in "module docstring" vs "mambo_power.opf.
dc_opf module docstring" wording), and the diagonal-Hessian-construction block
(`hess_diag`/`nz`/`HighsHessian` triangular-format assembly).

**Proposed helper shape (for the interview to accept or revise):** a single function, something
like `_extract_and_validate(cost_coeffs, pwl_costs, demand_bid_coeffs, demand_pwl_bids, n_gen,
n_load) -> _ExtractedProblem` (a small frozen dataclass carrying `c2, c1, c0, v2, v1,
segments_by_gen, demand_segments_by_load, elastic_load_idxs, ...` — everything both callers
currently derive independently before touching HiGHS at all), living in `dc_opf.py` itself
(where `_balance_row`/`_flow_limit_rows`/`_epigraph_rows`/`_hypograph_rows` already live, so the
row-family core and the validation core sit in one place) and imported by `multiperiod.py`
exactly as those four already are (`multiperiod.py:112-125`'s existing import block is the
precedent — this is one more name added to it, not a new pattern). The Hessian-construction step
is *not* fully shared as-is, because `dc_opf`'s Hessian is built over `n_dispatch = n_gen +
n_demand` columns once, while `multiperiod_dc_opf`'s is built over `n_dispatch_total = n_periods
* per_period_dispatch` columns, tiled per period (`multiperiod.py:477-494`) — so the helper
should return the **coefficients** (`c2`, `v2`, dense over the right index sets) and leave the
actual `hess_diag` array construction (which differs in shape between the two callers) to each
caller, the same division of labour the row-family extraction already uses (the helpers build
row *blocks*, `dc_opf`/`multiperiod_dc_opf` each still own their own column-index bookkeeping
around them).

**What "behaviour-preserving" must mean for M6's own proof, per M5's own precedent (S1's
`git archive` + overlay + unmodified-suite run):** the proof template M5's ADR-008 already names
is *"M4's complete unmodified 654-test suite passing against a tree differing in exactly one
file."* M6's analogue: extract the base commit (`4cfd1d7`) with `git archive`, overlay **only**
`dc_opf.py` and `multiperiod.py` (the two files the unification touches) with the post-unification
versions, and run the **current, unmodified** test suite (816/816 at M5's close) against that
tree unchanged. Two things sharpen this beyond M5's own template, because M6's unification
touches *two* files simultaneously rather than one: (1) the proof must show the *shared* LP each
builder emits is byte-identical to before — the row-order assertion `multiperiod_dc_opf` already
carries (`multiperiod.py:683-687`, `h.getNumRow() == expected_rows`) is a cheap, already-present
tripwire for exactly this, and should be re-run, not merely trusted; (2) because
`multiperiod_dc_opf` imports several `dc_opf`-private names directly (`multiperiod.py:112-125`),
the unification's own diff should be checked for whether it changes any of those imported names'
signatures — a helper rename or resignature is exactly the kind of change the M5-precedent
"unmodified suite" proof would catch structurally (an ImportError or TypeError, not a subtle
numeric drift) but is worth calling out explicitly since ADR-008's whole point is that this
specific seam is where M5's one real defect lived.

---

## §8 — Carry-overs: only `Scenario.periods.max_length` is in scope for M6

**Settled by the user: absorb `max_length` only; the `c0` test and the heterogeneous fixture are
NOT in M6.** The two "why not" cases first, then the sizing recommendation the settled item
still needs.

**Why not the 12-line `c0`-per-period test (M5 C3).** It is real, cheap (12 lines), and every
generator's `c0` in every fixture this repo ships is `0.0` (confirmed directly, again, by this
research's own read of the fixtures) — but it is a **multiperiod** fact about
`opf.multiperiod`'s own per-period constant-term handling, not a zonal-redispatch fact. Nothing
in §2/§3's formulations depends on `c0` being tested; the redispatch LP is purely linear (§3c)
and never touches `c0` at all (a constant term does not move an LP's optimum). Folding it in
because "it's cheap and nearby" is exactly the kind of drive-by scope absorption the user's
explicit exclusion forecloses — it belongs to whichever wave next touches `opf/`'s constant-term
handling on its own terms, not to M6 by proximity.

**Why not the combined heterogeneous storage/ramp fixture, overlap-free (M5 A31).** This is
multiperiod-storage fixture-design work (a clean, hand-derivable network where two heterogeneous
storage units and two heterogeneous ramp limits combine without falling into the
overlap-absorbs-round-trip-loss escape M5's own critic found) — a different problem shape
entirely from M6's own fixture need (§4a: a network where zonal aggregation loses a binding
branch nodal would use). Zonal-redispatch does not need storage or ramp coupling to demonstrate
either invariant; nothing here depends on it. Leaving it out is not deferral-by-neglect, it is
the user's own scope line.

**`Scenario.periods` `max_length` — sizing recommendation.** M5's own measurement (`m5-review.md`
§C2, re-read here): `T=2000` on rated `case118` (186 branches, 54 generators) produced a
110,100-byte request expanding to 20,088,000 constraint-matrix nonzeros (~240 MB) before HiGHS
even starts — nonzeros scale as `T * n_branch * n_gen` for a network with no elastic
demand/storage in the flow rows (`186 * 54 = 10,044` nonzeros/period, `* 2000 = 20,088,000`,
matching M5's own number exactly). `case300` is this repo's largest fixture and its worst case on
this axis (`n_branch=411`, `n_gen=69`, checked directly: `NetworkArrays.from_network` on
`case300.m` gives `n_branch=411`, `n_gen=69`, `n_load=201`, vs `case118`'s `n_branch=186`,
`n_gen=54`, `n_load=99`) — `28,359` nonzeros/period, ~2.8x `case118`'s density.

**Recommend `max_length = 200`.** At `T=200` on `case300`, the same scaling gives `~5,671,800`
nonzeros — ~28% of M5's own `T=2000`/`case118` figure, so roughly **~68 MB** of constraint matrix
by the same linear estimate (`240 MB * 5,671,800/20,088,000`), a wide margin below the point
M5's own docs already called a "decompression-bomb ratio". 200 periods is more than 8x the
epic's own stated real use case (`R7`'s "24-period horizon"), comfortably covers more than a
full week of hourly periods (168) with slack to spare, and is well beyond anything this repo
currently exercises (M5's longest committed fixture, the AC-6 diurnal profile, is 24 periods).
This is a policy choice for the design interview to finalise, not a computed optimum — 200 is
offered as a concrete, derived starting point rather than an unjustified round number.

---

## Appendix — probe script (preserved in scratchpad, not committed)

`C:\Users\mambo\AppData\Local\Temp\claude\C--Claude-Projects-mambo-power\
0d397067-49ef-4969-aefa-5709948393ef\scratchpad\zonal_pypsa_probe.py` — builds `case30` +
`tests/_rated.py`'s `rated_network` (unmodified), promotes `Bus.area` to an in-memory zone
assignment (not committed to any fixture), builds two PyPSA networks (zonal-ish and
fully-rated-for-redispatch) via the same `import_from_pypower_ppc` + `p_set`-clearing bridge
`test_opf_vs_pypsa.py`/`test_market_multiperiod_vs_pypsa.py` already use and prove, solves both,
and independently re-checks the redispatched dispatch's branch flows with this repository's own
`numerics.ptdf`/`numerics.bbus.pf_shift`. Full output reproduced in §5.
