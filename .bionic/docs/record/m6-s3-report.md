# M6 S3 report — zonal clearing LP (`opf.zonal`)

Wave M6 "zonal-redispatch", Step 4, slice S3 (senior-implementor). Worktree
`C:\Claude Projects\mambo-power-m6`, branch `wave/06-zonal-redispatch`. Serves spec requirement
**W2** and acceptance criterion **AC-2**.

Commit: **`4be66b4`** — `feat(m6/S3): zonal clearing LP — per-zone balance rows, one bounded
corridor per tied pair`.

Every command below was run; every number is measured output, none is `unverified`.

---

## 1. What shipped

| file | change |
|---|---|
| `src/mambo_power/opf/zonal.py` | new, 511 lines — `zonal_dc_opf`, `ZonalSolution`, `ZonalDuals`, three private helpers |
| `tests/unit/test_opf_zonal.py` | new, 642 lines — **26 tests** |
| `src/mambo_power/opf/__init__.py` | +4 lines — one import, three `__all__` entries |

Nothing else was touched. The sibling slice S4 had already committed its own `__init__.py` edit
(`fdd8993`), so the file was unmodified when I reached it; `git diff` was inspected before staging
and contains only my four lines. Staging used explicit paths.

### The formulation (design decision D2, alternative b2)

The nodal LP carries one system-wide balance row plus one PTDF flow-limit row per branch. The
zonal LP replaces **both**:

- one `_balance_row` **per zone** — that zone's generators and inbound corridors inject, its bid
  loads and outbound corridors withdraw, and its fixed right-hand side is that zone's own load
  plus shunt;
- one bounded **exchange column per tied zone-pair**, bounds `[-cap, +cap]` as plain variable
  bounds, never a row;
- **no** `_flow_limit_rows` call and **no PTDF matrix built at all** — the intra-zone grid does
  not constrain a zonal clearing, and a solve that consulted the PTDF would be modelling
  something else.

`_epigraph_rows` / `_hypograph_rows` are reused verbatim, and every cost/bid guard comes from the
single shared `dc_opf._extract_and_validate` (ADR-008) — this builder implements none of them,
which a committed test asserts by driving `NonConvexCostError`, `NonConcaveBidError` and the
`cost_coeffs` shape check through `zonal_dc_opf`.

**Column layout**, two tiers as in `multiperiod_dc_opf`: tier 1 `[gen | demand | corridor]`,
tier 2 `[cost_g | val_d]`. The Hessian covers the dispatch columns only and is passed *before*
the corridor columns are appended, which keeps `dc_opf`'s already-proven "Hessian over a column
prefix, then append more columns" ordering unchanged rather than inventing a new one. A corridor
column carries no objective coefficient and no quadratic term, so it has nothing to contribute to
a Hessian.

**Row layout**: balance rows at indices `0 .. n_zone-1` in sorted `zone_ids` order; epigraph then
hypograph rows after, whose indices nothing reads back.

### Corridor sign convention

Keys are unordered zone pairs normalised to sorted order (`z1 < z2`), and **positive flow means
z1 → z2**: the column enters z1's balance row as a withdrawal (`-1`) and z2's as an injection
(`+1`). This is exactly the convention `record/m6-ac2-derivation.md` §2 hand-derives
(`p_A - f_AB == L_A`, `p_B + f_AB == L_B`), so the committed AC-2 numbers transcribe directly with
no translation step. A negative `corridor_flow_mw` entry means the corridor runs z2 → z1, and sits
at `-cap` when it binds that way — which case30 actually exercises (§3).

### Corridor capacity shadow price

`ZonalDuals.corridor_cap` is the shadow price of the corridor's **capacity**: how much the
objective improves per extra MW of cap, in whichever direction it is binding. It is `|reduced
cost|` — non-negative in both directions, `0` when slack.

`_corridor_cap_price`'s docstring *derives* this rather than asserting it: the column carries no
objective coefficient, so its reduced cost is `d = -λᵀA_f`; for a minimisation `d ≤ 0` at the
upper bound and `d ≥ 0` at the lower; raising the capacity by `δ` moves whichever bound is active
outward, giving an objective change of `d·δ` at the upper bound and `-d·δ` at the lower — both
`≤ 0`, both of magnitude `|d|·δ`. So no branch on which bound is active is needed, and no solver
sign convention is trusted.

The `abs` is load-bearing, not cosmetic: the raw HiGHS reduced cost was **measured** at `-40.0`
under *both* key orderings on the derivation fixture, and returning it signed is sabotage S-5,
which goes red on 6 tests. Returning the signed value would also make the field's meaning depend
on zones' alphabetical names, which is an artifact rather than a market fact.

### Two documented modelling boundaries

**Phase shifters do not enter the zonal balance rows.** `dc_opf` omits phase-shift injections from
its single row because they cancel system-wide; per zone they do not, since a phase shifter on a
tie line injects in one zone and withdraws in the other. They are omitted here anyway, and
deliberately: a PST steers flow on a branch model this LP does not have, and whatever inter-zone
transfer it would produce is already, and entirely, what the corridor variable represents —
bounded by capacity rather than by a device setting. Folding `pf_shift` into a zone's fixed RHS
would *force* a transfer the abstraction has no basis for, on top of the free one. At one zone
this reduces to `dc_opf`'s own cancellation, which is what keeps the degenerate case exact.

**`objective_cost` is generation cost only**, exactly `OpfSolution.objective_cost`'s semantics —
not HiGHS's own objective value, which with bid loads present also nets in the negated demand
value. W4's `generation_cost_gap` should read this field knowing that.

### Validation

Every bus must carry a zone (a hole is rejected, never defaulted — the omitted bus's load and
generation would otherwise vanish from every balance row). `zone_of_bus` accepts either a
`{bus id: zone id}` mapping or a positional sequence in `NetworkArrays` bus order; both are
validated to the same standard and a committed test proves they solve identically. Corridor keys
must be pairs of two distinct, *assigned* zones; the same unordered pair must not appear twice
under both orderings; caps must be non-negative and not NaN. `cap == 0` is allowed (an honest
"tie that carries nothing", whose capacity price stays readable) and `cap == inf` is allowed.

A single zone with no corridors is explicitly legitimate, and equals `dc_opf` on an unrated
network (§4).

---

## 2. AC-2, transcribed from the hand-derived oracle

Every number below comes from `.bionic/docs/record/m6-ac2-derivation.md`, which solved the same LP
three independent ways (hand KKT, hand-built `scipy.optimize.linprog`, and this repo's
pre-existing `market.solve_nodal` for the nodal-reference columns). None was read off
`zonal_dc_opf`'s output and pasted back — that is what makes these an oracle rather than a
change-detector.

The fixture is the derivation's §1 network, built from `Network`/`NetworkArrays`: bus1+bus2 in
zone A, bus3 in zone B; `genA` at 10 $/MWh on bus1, `genB` at 50 $/MWh on bus3; loads 50 MW
(zone A, at bus2) and 30 MW (zone B); A–B corridor capped at 20 MW. Zone A is deliberately *two*
buses joined by an intra-zone branch, so "no intra-zone flow rows" is a property the fixture
witnesses rather than one merely asserted.

| quantity | derivation | measured | test |
|---|---|---|---|
| dispatch, binding | (70, 10) | (70, 10) | `test_corridor_binding_reproduces_the_hand_derived_optimum` |
| `f_AB`, binding | 20 (= cap) | 20 | same |
| zone prices, binding | (10, 50) | (10, 50) | same |
| corridor dual, binding | 40 | 40 | same |
| generation cost, binding | 1200 | 1200 | same |
| dispatch, copper plate | (80, 0) | (80, 0) | `test_copper_plate_prices_equal_each_other_and_equal_the_nodal_lambda` |
| zone prices, copper plate | (10, 10) | (10, 10) | same |
| `dc_opf` λ, unrated | 10 | 10 | same (computed live, then also pinned at 10) |
| `genB` reduced cost, copper | 40 | 40 | same |
| **λ_B(binding) − λ_B(copper)** | **40 == corridor dual** | **40** | `test_lifting_the_cap_moves_zone_b_price_by_exactly_the_corridor_dual_and_zone_a_not_at_all` |
| λ_A movement | 0 | 0 | same |
| bid-load dispatch | (70, 0), `p_d = 20` | (70, 0), 20 | `test_bid_load_variant_prices_zone_b_at_the_bid_not_the_local_generator` |
| bid-load prices | (10, 45) | (10, 45) | same |
| bid-load corridor dual | 35 | 35 | same |
| bid-load `genB` reduced cost | 5 | 5 | same |

**The paired negative lives in one test**, as required: it solves both regimes and asserts the
difference *is* the corridor dual, and that zone A's price does not move at all. That pairing is
what makes the corridor column load-bearing in both directions at once — a wrong-signed
coefficient fails to reproduce 40, and a missing bound fails to separate the prices in the first
place. Neither single-regime test catches both.

**The bid-load objective reconciles rather than conflicts.** The derivation quotes `-200`; that is
the *LP's* objective, which nets in the bid's `45 × 20 = 900` of value. `objective_cost` is
generation cost only, so it reads `10 × 70 = 700`, and the test asserts both, closing the loop
with `700 - 45·20 == -200`.

---

## 3. AC-2's real fixture — promoted, rated case30

Driven through the committed helpers (`tests/_zones.py`'s `promote_areas_to_zones` /
`corridors` / `zone_of_bus`, and `tests/_rated.py`'s `rated_network`), never a hand-copy of their
output.

```
zones ['1', '2', '3']  sizes {'1': 11, '2': 10, '3': 9}
corridors {('1','2'): 1.5237037054530278, ('1','3'): 16.576768909781237, ('2','3'): 19.456188360964873}

status Optimal
prices       [3.759145443393  3.880504459345  3.759146979274]
corridor_ids [('1','2'), ('1','3'), ('2','3')]
flows        [ 1.523703705453  15.358813947146  -19.456188360965]
cap duals    [0.121358863582  0.0  0.121355534452]
AT CAP: ('1','2') at 1.5237037054530278 ; ('2','3') at 19.456188360964873
generation cost 565.4275858199703 ; total dispatch 189.2 == total load 189.2
```

**Reporting what binds, as asked: two of the three corridors bind, not one.**

- **(1,2) binds at its 1.52 MVA cap, flowing 1 → 2 (positive)** — exactly what plan A19 predicted.
- **(2,3) also binds, at its 19.46 MVA cap, flowing 3 → 2 (negative)**. This was not predicted, and
  it is the more valuable of the two: it is what exercises the negative-flow half of the
  capacity-price derivation on real data. The test asserts flow *direction*, not just magnitude.
- (1,3) stays slack — 15.36 MW against a 16.58 MVA cap, capacity price exactly `0.0`.

**On "three distinct zone prices or a documented reason two coincide": two coincide, and the
reason is a theorem.** Zones 1 and 3 are joined by the **slack** (1,3) corridor, and an exchange
column strictly inside its bounds forces its two balance-row duals equal (KKT: interior column ⇒
zero reduced cost ⇒ `λ_1 = λ_3`). Zone 2 — importing at cap from *both* sides — is the one that
separates. So the fixture yields two distinct prices, and both binding corridors hold open the
same gap, which is why their duals agree with each other too.

Three committed tests pin this structure: the two-at-cap reading with directions, the
slack-corridor price identity, and "each binding corridor's dual equals the price gap it holds
open" (checked over every corridor, including the slack one at exactly 0). A fourth reconstructs
every zone's balance from the result object and the network arrays independently of the LP's own
rows — residual **1.4e-14 MW** — so a corridor entering the wrong zone's row, or with the wrong
sign, surfaces as a nonzero residual rather than as nothing.

### Plan A19's open question, answered

A19 left "case300 still to be checked by S3". **Spec A4 holds on case300**: its four real zones
(122 / 80 / 63 / 35 buses) carry **26 / 22 / 16 / 5** in-service generators respectively — no
generation-less zone, so no corridor is forced to carry a zone's entire load.

---

## 4. The degenerate case, and the tolerances

A network with one zone and no corridors is allowed and equals `dc_opf` on an **unrated** network.
The two builders hand HiGHS structurally different LPs (`dc_opf` still builds `n_branch`
unconstrained flow-limit rows this one never does), so the agreement is a theorem about their
optima, not about their floating-point paths.

**Answering the brief's "say whether bitwise or tolerance; measure and pin": tolerance.** Measured
on case30, stable across three consecutive runs:

| quantity | measured residual |
|---|---|
| dispatch | `2.842e-14` MW (relative `4.878e-16`) |
| zone price vs `dc_opf.duals.balance` | `0.0` |
| objective cost | `1.137e-13` $ |
| every generator bound dual | `0.0` |
| bitwise dispatch equality | **False** |

Pinned at `rtol=1e-9, atol=1e-8`. The M5 CI lesson is honoured throughout: **nothing in this file
asserts bit-equality, even where the run is bit-exact.** The 3-bus hand-derived numbers all
measure a residual of identically `0.0`, and are still asserted at `rtol=0, atol=1e-9` — ~11
orders of magnitude tighter than any distinction being drawn, so the tolerance costs the
assertions nothing while a last-bit platform difference cannot break CI.

**case30's zonal dual identities carry a real, reproducible slack.** Measured:

```
|price[1] - price[3]|          1.5358813949539751e-06     (slack (1,3) corridor)
|nu(1,2) - (price2 - price1)|  1.5237037054305347e-07
|nu(2,3) - (price2 - price3)|  1.9456188362632076e-06
|nu(1,2) - nu(2,3)|            3.3291298606741293e-06
```

Each is that corridor's own flow times ~1e-7 — HiGHS's default dual-feasibility tolerance showing
through. This wave adds no solver-tuning option to chase it (`OpfDcOptions`' own docstring: an
option is added when a caller actually needs one), so the residual is **pinned rather than
removed**, at `atol=1e-4`: ~50x headroom over the largest measured residual, and ~1200x *below*
the 0.1214 $/MWh separation the tests draw a conclusion from. The assertion keeps its teeth, and
the companion test asserts zone 2's separation exceeds `1000 × atol` so that "coincide" and
"differ" are not the same reading at this tolerance.

---

## 5. A finding that changed a test: removing a corridor is *not* the copper plate

The brief offered the copper-plate control as "cap = ∞ **or** corridors removed". **They are
opposites, and only `cap = inf` is the copper plate.**

Measured on the derivation fixture with the corridor deleted:

```
status Optimal   corridors []
dispatch [50. 30.]      prices [10. 50.]      objective 2000.0
```

With no exchange column the two balance rows stop being coupled at all, so each zone must serve
its own load from its own generation: zone B is forced onto its 50 $/MWh unit for all 30 MW and
prices there. That is the **most separated** the two zones can be, not the least — the opposite
end of the range from the copper plate, and strictly the most expensive of the three regimes
(`2000 > 1200 > 800`).

This matters beyond tidiness. A copper-plate control built on corridor *removal* would still pass
a sign-flipped corridor column, because there would be no corridor column left to sign. The
committed suite therefore uses `cap = inf` for the control and keeps corridor removal as its own
explicitly-named paired negative
(`test_removing_the_corridor_islands_the_zones_it_does_not_make_a_copper_plate`), which also pins
the strict cost ordering across all three regimes.

---

## 6. Sabotage sweep — five sabotages, all red

Detached scratch worktree at `<scratchpad>/sab-s3` (`git worktree add --detach`), removed
afterwards. The scratch copies were proven to be the imported ones before any sabotage ran —
`PYTHONPATH` and every relevant `__file__` printed:

```
PYTHONPATH = .../scratchpad/sab-s3/src;.../scratchpad/sab-s3
mambo_power.opf.zonal        __file__ = ...\sab-s3\src\mambo_power\opf\zonal.py
mambo_power.opf.dc_opf       __file__ = ...\sab-s3\src\mambo_power\opf\dc_opf.py
tests._zones                 __file__ = ...\sab-s3\tests\_zones.py
tests._rated                 __file__ = ...\sab-s3\tests\_rated.py
=== pristine scratch run === 26 passed in 1.31s
```

Pristine sha256 `d7a5d5b6ac4130b9f049296bd5c38f64217f6fbd991b50c91d68a688a7c4ad0a`, restored and
re-verified after **every** sabotage; post-sweep run green (26 passed); the main worktree's
`zonal.py` carries the identical hash.

| # | sabotage | result | named residual |
|---|---|---|---|
| S-1 | corridor column enters z1's balance row with the **wrong sign** (injection, not withdrawal) | **10 failed** | zone A balance readback `p_A - f_AB` reads **10.0**, expected **50.0** — a 40 MW error, exactly 2× the cap |
| S-2 | corridor **bound dropped** (column made free instead of `[-cap, +cap]`) | **8 failed**, including *both* the binding test and the paired negative | price separation reads **0.0**, expected **40.0** |
| S-3 | zone price read off the **wrong row** (rolled by one) | **6 failed** | prices `[50, 10]`, expected `[10, 50]` |
| S-4 | per-zone fixed RHS replaced by the **system-wide total** spread evenly | **9 failed** | dispatch and prices both wrong from the binding case down |
| S-5 | capacity price returns the **raw signed** reduced cost instead of `\|d\|` | **6 failed** | corridor dual reads **-40.0**, expected **+40.0** |

Coverage of the brief's requirement that every new row family and column family gets one: the
per-zone balance **row** family is attacked three ways (S-1 sign, S-3 readback, S-4 right-hand
side); the corridor **column** family two ways (S-2 bounds, S-5 dual reading). **No sabotage
stayed green**, so nothing here is a powerless test.

S-2 is the one the brief called out specifically, and it behaves as demanded: dropping the bound
kills `test_corridor_binding_reproduces_the_hand_derived_optimum` *and*
`test_lifting_the_cap_moves_zone_b_price_by_exactly_the_corridor_dual_and_zone_a_not_at_all`.

---

## 7. Reporting contract — commands and output

```
$ uv run --no-sync pytest --collect-only -q            # baseline, at 97b56ef
830 tests collected in 3.64s

$ uv run --no-sync pytest tests/unit/test_opf_zonal.py -q
26 passed in 1.12s

$ uv run --no-sync pytest --collect-only -q tests/unit/test_opf_zonal.py
26 tests collected in 1.63s
$ uv run --no-sync pytest --collect-only -q tests/unit/test_opf_redispatch.py   # sibling S4
18 tests collected in 1.02s

$ uv run --no-sync ruff check src tests
All checks passed!

$ uv run --no-sync ruff format --check src tests
117 files already formatted

$ uv run --no-sync mypy                                # CI's own invocation; files = ["src"]
Success: no issues found in 48 source files

$ uv run --no-sync pytest -q
874 passed, 10 warnings in 154.67s (0:02:34)
```

**Count reconciliation:** 830 (S1 baseline `97b56ef`) + 18 (S4's `test_opf_redispatch.py`,
committed as `fdd8993` / `55f716d` while this slice was in flight) + 26 (this slice) = **874**.

One note on `mypy`: the repo configures `files = ["src"]` and CI runs a bare `uv run mypy`, which
is clean. An exploratory `mypy src tests` reports a pre-existing namespace-package complaint about
`tests/_fixtures.py` that predates this slice and is an artifact of that non-canonical invocation;
a targeted `mypy src/mambo_power/opf/zonal.py tests/unit/test_opf_zonal.py` reports
`Success: no issues found in 2 source files`.

---

## 8. Carry-overs and notes for downstream slices

1. **For S4/S5 (`market.solve_zonal`, W4):** `objective_cost` is **generation cost only**, matching
   `OpfSolution`. `redispatch_payment` / `generation_cost_gap` should be composed knowing that the
   bid-side value is not in this figure.
2. **For S6 (AC-6, the PyPSA oracle):** the corridor sign convention is "sorted key, positive =
   z1 → z2", and case30 binds **two** corridors, one of them **negatively**. A `Link`-based oracle
   must be given a matching orientation, and the zone-assignment / cap-sign sabotage AC-6 calls for
   should be checked against the negatively-binding (2,3) corridor as well as the positive (1,2)
   one — the reverse direction is where an orientation bug hides.
3. **Plan A19 closed on the case300 half:** spec A4 holds there (26/22/16/5 generators across the
   four zones).
4. **No new carry-over debt.** Nothing in this slice was deferred; the phase-shifter omission and
   the `objective_cost` scope are documented decisions in the module docstring, not gaps.
