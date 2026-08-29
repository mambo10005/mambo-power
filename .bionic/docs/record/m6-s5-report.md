# M6 S5 — `market.zonal` chain and `MarketZonalResult`

Wave M6 "zonal-redispatch", Step 4, slice S5 (senior-implementor). Worktree
`C:\Claude Projects\mambo-power-m6`, branch `wave/06-zonal-redispatch`, base `4be66b4`,
commit **`f1782e8`**. Serves W4/W5 and acceptance criteria **AC-4** and **AC-5**.

Every number below was produced by running code in this worktree. Nothing is `unverified`.

---

## 1. What landed

Five files, exactly the ownership the brief assigned:

| file | lines | what |
|---|---|---|
| `src/mambo_power/market/zonal.py` | +528 | `solve_zonal`, `MarketZonalOptions`, `CorridorLimit`, `zone_partition`, the two curve evaluators |
| `src/mambo_power/results/zonal.py` | +224 | `MarketZonalResult`, `ZonePriceResult`, `GenRedispatchResult`, `LoadRedispatchResult` |
| `tests/unit/test_market_zonal.py` | +945 | 30 tests |
| `src/mambo_power/market/__init__.py` | +17/−3 | export line + a docstring fold naming the third entry point |
| `src/mambo_power/results/__init__.py` | +10 | export line |

### The chain

`solve_zonal(scenario, options=None)` runs, in order: (1) read the zone partition off
`Bus.zone`; (2) `zonal_dc_opf` on that partition and the options' corridor caps; (3)
`redispatch_dc_opf` from the zonal point with the true curves (D1); (4) `solve_nodal` on the same
scenario as the reference; (5) compose. A non-`Optimal` stage returns `status` plus a `message`
naming the stage — never raises. Malformed input (a bus with no zone, a non-convex cost, a
non-concave bid) still raises up front.

### The result

`MarketZonalResult` carries the D4 field set exactly: `zones` (one price per zone), the **zonal**
dispatch layer (`generators`/`loads`), the redispatch deltas (`redispatch_generators`/
`redispatch_loads`), the **final** layer (`generators_final`/`loads_final`), `branches`
(`OpfBranchFlowResult` verbatim — the first market result type to carry branch rows), `buses`
(final LMPs), and the three separated figures. Frozen, `extra="forbid"`, `allow_inf_nan=False`,
exact JSON round trip asserted.

No field was added beyond D4's list. Corridor flows and capacity prices are *not* on the result:
D4 does not name them and inventing a field is not this slice's call. Noted here because a reader
of `zones` can see that two zones price apart but not, from the result alone, which corridor holds
the gap open — a real limitation, and a candidate for S8's docs or a later wave.

---

## 2. Verification

Command: `uv run --no-sync python -m pytest -q -p no:randomly` from the worktree.

```
951 passed, 4 skipped, 10 warnings in 69.92s (0:01:09)
```

`tests/unit/test_market_zonal.py` collects **30**. Baseline at `4be66b4` was 874; siblings
(`m6-s6-parity`, `m6-s7a-maxlength`) landed the remaining +47 passed / +4 skipped concurrently.

```
uv run --no-sync ruff check src tests      -> All checks passed!
uv run --no-sync ruff format --check src tests -> 121 files already formatted
uv run --no-sync mypy                      -> Success: no issues found in 50 source files
```

### AC-4 — the redispatched point is the nodal optimum

Both multi-zone fixtures, with `tests/_bids.py` elastic bids in play. Each fixture is assembled
only from the committed factories: `rated_network(promote_areas_to_zones(load(...)))`, then
`with_bids(net, five_ids, interior_load_ids=first_two)` — the same construction S4 uses, and for
the same reason: without the interior derivation every bid load sits pinned at its own bound and
`redispatch_payment`'s curtailment term is multiplied by zero on every fixture in the file.
Corridor caps come from `tests/_zones.py`'s `corridors()`, never a hand copy.

| measurement | case30 | case300 | pinned |
|---|---|---|---|
| generator dispatch vs `solve_nodal` | 2.83e-5 MW (rel 4.6e-7) | 9.45e-3 MW (rel 4.8e-6) | 1e-3 / 5e-2 MW |
| served demand vs `solve_nodal` | 1.46e-5 MW | 8.28e-5 MW | same |
| bus LMPs vs `solve_nodal` | 8.92e-6 $/MWh (scale 6.78) | 0.319 $/MWh (scale 40.9) | 1e-3 on case30 only |
| `welfare_gap`, relative | 1.37e-14 | 8.28e-13 | 1e-9 |

The case300 LMP row is **A20's degeneracy, not a disagreement**, and it is asserted as the
structural property the orchestrator ruled on rather than hidden behind a loosened tolerance:
`test_ac4_case300_flow_duals_are_degenerate_at_the_nodal_optimum` asserts that every branch the
chain prices is genuinely at its rating, and that the at-rating set is *strictly larger* than the
priced set — which is what degeneracy means. The primal quantities and the welfare stay at their
pinned tolerances.

Everything is asserted as a tolerance, never bitwise (spec A3, M5's macOS CI finding).

**Paired negative.** S4 owns AC-4's — the anchored-rate objective substituted in a scratch tree,
which S4 measured at 6 red with the dispatch moving 106.9 MW on case14. My own cross-file
addition is S-5 below (the redispatch objective's sign flipped on the demand class alone), which
moves `welfare_gap` and turns 8 of my tests red.

### AC-5 — relaxation, three figures, and A23

**(a)** `welfare(zonal) >= welfare(nodal)` on both fixtures, compared against a nodal welfare
recomputed from an independent `solve_nodal` result through the same evaluators, so the two
numbers differ only in the dispatch they are evaluated at. On rated case30 it holds **strictly**:
a 14.51 $/h gap behind 43.02 MW of generator redispatch and 0.31 MW of load movement — the strict
case S3's two binding corridors ((1,2) at 1.524 and (2,3) at 19.456 MVA) create.

**(b)** The three figures on case30: `redispatch_payment` **+14.51**, `welfare_gap` **−4.13e-9**,
`generation_cost_gap` **−13.57**. Three separate fields, three visibly different values, and the
diagnostic is *negative* — research §4(b)'s cost-ordering inversion showing up live on real
fixture data. They are asserted apart by their own scale (payment strictly positive, cost gap
strictly negative, welfare gap negligible against both), not by a shared epsilon.

**(c) A23 closed.** `_settlement_from_result_alone(result)` computes both sides of the settlement
identity reading only `result.buses`, `result.loads_final`, `result.generators_final` and
`result.branches`. No second solve; nothing imported from `numerics` or `opf` in it. Measured
closure **8.53e-14 $/h** on case30 against a congestion rent of 31.85, and **exactly 800 $/h**
both ways on the hand fixture.

The identity is asserted on case30 and the hand fixture, **not** case300 — whose `g_shunt` is the
one non-zero one this repository ships, so the merchandising surplus there also carries that
unsettled withdrawal (measured: lhs −25.01 against rhs 26.71). `results/multiperiod.py` already
states the general form with its `pf_shift`/`g_shunt` corrections; the test docstring says so
rather than leaving the omission unexplained.

### The hand fixture — both legs derived, then pinned

The AC-2 derivation network (`record/m6-ac2-derivation.md` §1), run through the whole chain.

*Leg 1 — corridor cap 20 == the tie's 20 MVA rating.* Zone prices **(10, 50)** (§2's λ), zonal
dispatch **(70, 10)**, final LMPs **(10, 10, 50)** and final dispatch **(70, 10)** (§5),
`redispatch_payment` **0** with zero redispatch volume. That the two points coincide is §5's own
observation about this fixture — zone A's only internal branch is unrated and zone B is a single
bus, so it has zero zonal relaxation gap by construction — which makes the zero payment a derived
consequence rather than a number read back.

*Leg 2 — corridor declared at 30 while the tie is still rated 20* (the honest picture of a zonal
market whose transfer capacity overstates the grid). Derived by hand in the test docstring from
§3 (copper-plate branch: `p_A=80, p_B=0, f=30`, both prices 10, cost 800) and §5 (nodal:
`p_A=70, p_B=10`, LMPs (10,10,50), cost 1200):

| figure | hand | measured |
|---|---|---|
| `redispatch_payment` | `1200 − 800 = 400` | 400.000000000 |
| `generation_cost_gap` | `800 − 1200 = −400` | −400.000000000 |
| `welfare_gap` | 0 | 0.0 |
| settlement identity | `2000 − 1200 = 800`, and `−(−40 · 20) = 800` | 800 / 800 |

Every residual identically 0.0, asserted at `1e-9` (derivation §7: exact rationals at this scale;
asserted as a tolerance anyway per A3).

The §6 piecewise-bid variant also runs end to end (zone B prices at the **bid**, 45, not at
`c_B = 50`), which is what exercises the piecewise branch of the curve evaluators.

### A21 — every feasibility readback asserts balance too

`pf.dc` pins the slack bus at angle 0 and absorbs whatever mismatch the declared injections
carry, so a rating-respecting flow vector does not imply a balanced dispatch. Both halves are
asserted:

| | case30 | case300 | pinned |
|---|---|---|---|
| max overload through `pf.dc` | 2.0e-14 MW | 5.52e-10 MW | 1e-6 MW |
| energy-balance residual | 0.0 MW | −2.52e-10 MW | 1e-6 MW |

Separately, `result.branches[k].p_from_mw` is checked against `pf.dc`'s own flow at the same
dispatch — a different code path (B-bus rather than the PTDF the LP used) — to 2.31e-14 MW.

---

## 3. Sabotage sweep

Detached scratch tree at `<scratchpad>/sab` (a copy of `src`, `tests`, `fixtures`,
`pyproject.toml`). `PYTHONPATH` and the loaded module's `__file__` were printed before the sweep
and both point into the scratch copy:

```
loaded __file__ = ...\scratchpad\sab\src\mambo_power\market\zonal.py
PYTHONPATH      = ...\scratchpad\sab\src
```

Both touched files restored byte-identical, sha256 verified:

```
sha256(market/zonal.py)     before 301f4afd0cc125cf5621a825c889fa63c4fed3c9372fd83e6babaa548dc9d069
                            after  301f4afd0cc125cf5621a825c889fa63c4fed3c9372fd83e6babaa548dc9d069
sha256(opf/redispatch.py)   before 2d77553861372d7f6d0784b74b4f895746a96a93bb5871a061eca2f860bdb92c
                            after  2d77553861372d7f6d0784b74b4f895746a96a93bb5871a061eca2f860bdb92c
```

The repository itself was never modified — the sweep ran entirely in the scratch copy.

| # | sabotage | red | residual that moves |
|---|---|---|---|
| S-1 | branch rows dropped from the result | 5 | both A23 identity tests, the branch-flow readback, the row-coverage test, and the case300 degeneracy property |
| S-2 | `welfare_gap` computed from the zonal point instead of the final one | 5 | both `welfare_gap` tests, both three-figures tests, and the hand fixture's `welfare_gap == 0` |
| S-3 | `generation_cost_gap` conflated with `redispatch_payment` | 3 | both three-figures tests and the hand fixture's `−400` |
| S-4 | stage 4 skipped, the zonal point reused as the nodal reference | 5 | both `welfare_gap` tests, both three-figures tests, the hand fixture |
| S-5 | *(mine, cross-file)* redispatch objective's sign flipped on the demand class only | 8 | both AC-4 dispatch tests, the case30 LMP test, both `welfare_gap` tests, both three-figures tests, the hand fixture |

**No sabotage stayed green.**

### S-4's residual is AC-4's, not AC-5(a)'s — a finding

The brief predicted S-4 would turn AC-5(a) red. It does not, and cannot: AC-5(a) relates welfare
at the **zonal** point to welfare at the **nodal** one, and in my test both are computed without
consulting the chain's stage-4 result — the zonal side from the result's own rows, the nodal side
from an independent `solve_nodal` in the test. Skipping stage 4 inside `solve_zonal` moves
neither.

I tried routing AC-5(a) through the chain's own reference (`zonal_welfare >= final_welfare +
result.welfare_gap`). Under exactly this sabotage that degenerates to a tautology —
`welfare_gap` becomes `welfare(zonal) − welfare(final)`, so the assertion reduces to
`wz >= wz`. A line that is vacuous precisely under the sabotage it was added for is worse than no
line, so I removed it and left AC-5(a) stating the inequality literally.

The sabotage *is* caught, by AC-4's `welfare_gap` clause and by AC-5(b) — 5 tests, on both
fixtures and the hand fixture. The criterion that catches it is a different one from the brief's
prediction, which the auditor should see stated rather than discover.

---

## 4. Two design calls that deviate from the brief

### (a) `MarketZonalOptions.corridors` is a `list[CorridorLimit]`, not `dict[tuple[str,str], float]`

The brief named the mapping as the expected shape. It cannot be the *stored* shape, measured:

```python
class M(BaseModel):
    corridors: dict[tuple[str, str], float]
M(corridors={('1','2'): 5.0}).model_dump_json()   # -> {"corridors":{"1,2":5.0}}
M.model_validate_json(...)                         # -> ValidationError:
#   corridors.1,2.[key]  Input should be a valid array [type=tuple_type, input_value='1,2']
```

It serialises one way and refuses to validate back. The epic's `jobs` criterion (AC-7) is exact
JSON round-trip on every kind, and S7 will validate `market.zonal` requests against this options
model — so a shape that round-trips one-way would land as an S7 failure with its cause two slices
upstream. `CorridorLimit(zone1, zone2, cap_mw)` is a row model in the style `results/` uses
everywhere, and `MarketZonalOptions.corridor_map()` hands `zonal_dc_opf` the
`{(z1, z2): cap_mw}` mapping it actually takes. Both halves are asserted in
`test_the_options_round_trip_through_json_which_a_tuple_keyed_mapping_would_not`.

**For S7:** the request form is `{"corridors": [{"zone1": "1", "zone2": "2", "cap_mw": 1.52}, ...]}`.

### (b) `generation_cost_gap` is `cost(zonal) − cost(nodal)`

Research §6 defines it as `cost(final) − cost(nodal)`. That definition is a casualty of D1, in the
same way §6's `redispatch_payment` definition is (which A17 already records and the spec's A5
already replaced): under true curves the final point **is** the nodal optimum, so
`cost(final) − cost(nodal)` is identically zero — the same theorem that zeroes `welfare_gap`. It
would ship as a second copy of the exactness row, and AC-5(b)'s "three distinct fields" would be
two fields and a duplicate.

§4(b)'s argument has two halves. The half that needs the anchored-rate objective is the *worked
example* (the LP that curtails to zero). The half that needs **no** assumption about the
redispatch objective at all is the opening claim: *"A feasible point of `S_nodal` can have lower
generation cost than nodal's own optimum while having worse welfare... This half of the argument
needs no assumption about the redispatch objective."* That applies directly to the **zonal**
point, which is welfare-better by the relaxation argument and generation-cost-unordered. So
`cost(zonal) − cost(nodal)` is the quantity that survives D1 with §4(b)'s not-sign-constrained
warning intact and load-bearing.

Measured: **−13.57 $/h** on case30 and **−400** by hand on the fixture — negative in both cases,
which is the warning made concrete rather than merely documented.

A17 rules that the spec governs where it and the research differ, and the spec names the field
without redefining it. I made the call rather than blocking; the full reasoning is in
`market/zonal.py`'s module docstring under *"A note on the third figure's definition"*, and the
field's own description carries the unsigned warning. **If the orchestrator prefers the research's
literal definition, it is a one-line change** — and AC-5(b) would then need re-scoping, since two
of the three figures would be zero to solver noise.

### A third, smaller call

`redispatch_payment` is implemented as
`[cost(final) − cost(zonal)] + [value(d_zonal) − value(d_final)]` — spec A5's wording exactly
(extra generation cost plus curtailment compensation at bid value, with a *restored* load paying
back at the same bid value). It rearranges algebraically to `welfare(zonal) − welfare(final)`,
which is why it is non-negative wherever the zonal LP is a relaxation: it is exactly the welfare
the zonal clearing promised and the network could not deliver. That rearrangement is asserted
against welfare computed from the result's own two dispatch layers (residual 5.57e-12 $/h on
case30), so the field's sign is a consequence of AC-5(a) rather than a separate hope.

---

## 5. Implementation notes worth carrying forward

**Welfare is evaluated one way, at all three points.** The three points need cost and value, and
only some are reported by the solve that produced them — `ZonalSolution` has a generation cost but
no demand value, `MarketNodalResult` has neither. Mixing reported and derived figures would make
the differences not-quite-like-for-like, so the module evaluates the true curves itself
(`_generation_cost` / `_demand_value`) at all three. That is an independent path from the LPs'
epigraph/hypograph encoding, and the two are asserted to agree: **residual identically 0.0** for
zonal cost, final cost and final demand value on case30. The piecewise branch is checked
separately against `redispatch_dc_opf`'s own hypograph column on the §6 fixture, since every
committed fixture carries quadratic curves only.

`_pwl_curve_value` reproduces the encoding (max over the segments' affine extensions for a convex
cost, min for a concave bid) rather than interpolating, so it stays exact where the LP is —
including outside the breakpoint range, where interpolation and the LP disagree.

**The nodal reference's rows are gathered by id, not position.** `MarketNodalResult` and
`NetworkArrays` order generators the same way today. A comparison the whole result rests on should
not be silently load-bearing on that, so both `_nodal_quantities` (in `src`) and `_quantities` (in
the tests) key by id.

**`zone_partition` is public**, for the reason `gen_cost_coeffs` and `load_bid_coeffs` are: it is
the model-to-solver extraction step for one more kind of network data, and a caller driving
`zonal_dc_opf` directly needs exactly that mapping.

---

## 6. Open items for downstream slices

- **S7 (`jobs`)**: the `market.zonal` request form is the list-of-rows shape in §4(a). `KINDS`
  goes to 7; `MarketZonalOptions` round-trips and is ready to validate against.
- **S8 (docs)**: five new public symbols are re-exported into `market`/`results`, so
  `test_api_docs_coverage.py` passes as-is; the manual page will want the three-figures
  distinction (§4b) and the `Bus.zone`-is-read-not-derived rule. S3's finding A22 (phase shifters
  deliberately omitted from the per-zone balance rows) is still a design note S8 must document.
- **Audit**: the S-4/AC-5(a) insensitivity in §3 is the one place a criterion behaves differently
  from the brief's prediction.
- **Not shipped, deliberately**: corridor flows and capacity prices are absent from
  `MarketZonalResult` because D4 does not name them (§1).
