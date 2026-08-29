# M4 S3 — opf-extension: elastic-demand LP in `dc_opf`

Slice S3 (senior-implementor, complex, the wave's central piece). TDD throughout: RED
(`tests/unit/test_opf_dc_demand.py` written first, confirmed failing on `ImportError` for
`NonConcaveBidError`), then implementation, then GREEN (10/10 first attempt, no adjustment
needed — including the AC-1 hand-KKT numbers matching exactly).

## What was built

`src/mambo_power/opf/dc_opf.py`:

1. **`dc_opf` gains two optional parameters**: `demand_bid_coeffs: Mapping[int, tuple[float,
   float, float]] | None` (load index → `(v2, v1, v0)`, mirrors `cost_coeffs`' `[c2, c1, c0]`
   row) and `demand_pwl_bids: Mapping[int, Sequence[tuple[float, float]]] | None` (load index
   → bid points, mirrors `pwl_costs`). Both default `None`. Keyed by **load index** rather
   than a dense `(n_load, 3)` array + mask, since only a subset of loads become elastic LP
   columns — a sparse mapping avoids a sentinel-value problem and mirrors the existing
   `pwl_costs` shape exactly. A load index must not appear in both mappings (`ValueError` if
   it does); an out-of-range index also raises `ValueError`.
2. **New LP columns per bid-load**, bounded `[load_p_min_mw, load_p_max_mw]` (from
   `NetworkArrays.load_p_min_pu`/`load_p_max_pu`, S2) — **no sign flip**, per Option B.
   Inserted immediately after the generator dispatch columns (`[n_gen, n_gen+n_demand)`), so
   `dispatch_mw`/`gen_bound` stay a clean `[:n_gen]` slice and the new
   `demand_dispatch_mw`/`demand_bound` are a clean `[n_gen:n_gen+n_demand]` slice — no
   semantic overload of the generator-side fields.
3. **Hypograph rows** (`val_d <= slope_i·p_d + intercept_i` per segment) for PWL bid-loads,
   built by a new `_concave_pwl_segments` — the literal sign-mirror of the existing
   `_convex_pwl_segments`/epigraph construction. One free `val_d` column per PWL bid-load,
   objective coefficient `-1` (minimising `-Σval_d` pulls `val_d` up to its tightest bound).
4. **Balance/flow rows extended** with a `-1`-signed load-column term
   (`Σp_g - Σp_d == fixed_load + shunt`) and a `-PTDF[k, load_bus[d]]`-signed flow term — the
   exact mirror of the generator's `+1`/`+PTDF[k, gen_bus[g]]` terms.
5. **`OpfSolution.demand_dispatch_mw`/`demand_bound`** — new, explicit fields (order:
   `sorted(set(demand_bid_coeffs or {}) | set(demand_pwl_bids or {}))`, i.e. the caller's own
   bid-index set ascending — the caller already has this set, so no extra id list needed).
6. **`NonConcaveBidError`** (new, beside `NonConvexCostError`) — raised pre-solve for (a) a
   PWL bid's breakpoint slopes not non-increasing, (b) a polynomial bid's `v2 > 0`. Both
   checked before any `highspy.Highs()` object is created.
7. **Generator-side `c2 >= 0` guard** — a real, pre-existing gap the research found. Reuses
   `NonConvexCostError` (same failure family — a non-convex cost fed to a convex-only
   encoding) rather than a new class, added in the same commit per the spec's own instruction
   ("closing the asymmetry... to avoid shipping an asymmetric guard").
8. `OpfSolution.objective_cost` semantics **unchanged** ("total generation cost only," not net
   welfare) — recomputed directly from generator dispatch + PWL `cost_g` values instead of
   HiGHS's raw `objective_function_value` (which, with demand columns present, nets in the
   negated demand value). Proved algebraically identical to the pre-M4 formula whenever
   `n_demand == 0`, so zero regression risk — confirmed by every existing objective-cost
   assertion in the untouched test suite still passing unchanged.

## The double-counting contract (the real design decision in this slice's scope)

**Chosen: `dc_opf` performs the fixed-load subtraction itself**, not the caller.

For every load index appearing in `demand_bid_coeffs`/`demand_pwl_bids`, `dc_opf` reads that
load's own historical contribution directly off `arr.load_p_max_pu[idx]` and removes exactly
that amount, at that load's own bus (`arr.load_bus[idx]`), from the fixed balance/flow-row
RHS before adding the load's new LP column. The caller passes `arr` **completely
unmodified** — the same `NetworkArrays` it would use for a plain fixed-load solve — and
supplies bid data only for whichever loads are meant to be elastic.

This works safely and unambiguously because `arr.load_p_max_pu[idx]` and that load's own
contribution to the `p_load_pu` bus aggregate are **provably the same number**: both were
built in `NetworkArrays.from_network` (S2) from the identical `ld.p_mw` source (`arrays.py`'s
`per_bus` and `per_load` helpers both divide by the same `base`), so there is no way for them
to drift apart. Concretely: `p_load_pu[bus] = Σ_{loads at bus} ld.p_mw / base`, and
`load_p_max_pu[idx] = ld.p_mw / base` for that same load — subtracting the latter from the
former, at the right bus, exactly reconstructs "the aggregate excluding this one load," with
no separate bookkeeping needed.

**Why this over "the caller must pre-zero `arr.p_load_pu`"**: that alternative (mirroring how
`_cost_coeffs` in `opf/__init__.py` already zeroes a PWL generator's own `cost_coeffs` row)
would work too, but it's a fragile contract — the caller would need to reconstruct the exact
same per-bus amount to remove, using the same `load_bus`/`p_mw` data `dc_opf` already has
directly, with no way for `dc_opf` itself to verify the caller did it correctly. Since
`dc_opf` already receives the bid-mapping keys (i.e. already knows exactly which loads are
elastic) and already has `arr.load_bus`/`arr.load_p_max_pu` in hand, doing the subtraction
itself removes an entire class of caller error at zero extra cost, and keeps the "caller
passes `arr` as-is" invariant that already holds for every other `dc_opf` argument. The
`test_mixed_elastic_and_inelastic_load_no_double_counting` test proves this decisively: a
network with one fixed load (30 MW, no bid) and one elastic load (50 MW cap, bid value 1000
$/MW — always pinned at its own cap) dispatches the generator to exactly 80 MW, not 130 MW
(the double-counted answer a broken subtraction would produce).

## RED/GREEN evidence

RED (before implementation):
```
$ uv run --no-sync pytest -q tests/unit/test_opf_dc_demand.py
ImportError: cannot import name 'NonConcaveBidError' from 'mambo_power.opf.dc_opf'
```

GREEN (after implementation, first attempt):
```
$ uv run --no-sync pytest -q tests/unit/test_opf_dc_demand.py
..........
10 passed in 1.49s
```

Existing opf/PWL/parity suite (zero regressions):
```
$ uv run --no-sync pytest -q tests/unit/test_opf_dc.py tests/unit/test_opf_dc_pwl.py \
    tests/unit/test_opf_pwl_guard.py tests/unit/test_opf_dc_case14_pwl.py \
    tests/unit/test_opf_solve_dc_opf.py tests/parity/test_opf_vs_pandapower.py \
    tests/parity/test_opf_vs_pypsa.py
....................................................................
68 passed in 27.91s
```

Full repo suite:
```
$ uv run --no-sync pytest -q
627 passed, 10 warnings in 132.46s
```
(627 = 617 before this slice + 10 new — reconciles exactly.)

Lint/type:
```
$ uv run --no-sync ruff check .
All checks passed!
$ uv run --no-sync ruff format --check .
130 files already formatted
$ uv run --no-sync mypy
Success: no issues found in 40 source files
```

## AC-1 evidence

`test_ac1_two_bus_hand_kkt_welfare_optimum` reproduces `m4-research.md` §4.1's exact network
(slack `b1` with `g1` linear cost 10/MW, `b2` with `g2` linear cost 50/MW and a 2-segment
concave demand bid — marginal value 45 on `[0,50]`, 20 on `[50,100]` — one 20 MW-rated branch
`b1↔b2`) directly on `dc_opf` (hand-built `NetworkArrays`, no fixture dependency). Result,
confirmed by direct interactive run and by the test itself, to `1e-6`:

```
dispatch_mw = [20.0, 0.0]   (g1, g2)
demand_dispatch_mw = [20.0]  (d1)
balance dual (λ) = 10.0
flow_limit dual (μ_flow) = -35.0
LMP(b1) = 10.0   LMP(b2) = 45.0   (via lmp_decomposition, M3's, reused verbatim)
```

Every number matches the research doc's hand-KKT solve exactly, including the sign of
`μ_flow` — no sign-convention adjustment was needed against the research's independent
`scipy.optimize.linprog` derivation, first attempt.
`test_ac1_settlement_identity_holds_on_the_two_bus_case` independently cross-checks via the
settlement identity: `payments=900.0, receipts=200.0, payments-receipts=700.0` (matching
`-μ_flow·flow = -(-35)·20 = 700` exactly).

## AC-2 evidence

- `test_nonconcavebiderror_on_increasing_pwl_segment_slope`: PWL bid slopes 20 then 25
  (increasing) → `NonConcaveBidError`.
- `test_nonconcavebiderror_on_positive_v2_polynomial_bid`: quadratic bid `v2=0.5 > 0` →
  `NonConcaveBidError`.
- `test_nonconvexcosterror_on_negative_c2_generator_cost`: generator cost `c2=-0.1 < 0` →
  `NonConvexCostError` (the new generator-side guard).
- `test_positive_c2_generator_cost_is_unaffected_by_the_new_guard`: `c2=0.1` (valid convex)
  solves normally — the new guard doesn't misfire on legitimate input.

All four raise (or don't) before any `highspy.Highs()` object is created, per both errors'
own docstrings.

## Additional tests (beyond the letter of AC-1/AC-2, within scope)

- `test_mixed_elastic_and_inelastic_load_no_double_counting` +
  `test_demand_bound_reduced_cost_nonzero_when_pinned_at_cap` — proves the double-counting
  contract above on a network with one fixed and one elastic load.
- `test_demand_pwl_bid_stops_at_the_breakpoint_where_marginal_value_drops_below_gen_cost` —
  exercises the hypograph row construction specifically (PWL demand bid, not just the
  linear/quadratic path), mirroring `test_opf_dc_pwl.py`'s generator-side PWL test structure.
- `test_dc_opf_with_no_demand_params_is_byte_identical_to_the_pre_s3_call` — explicit
  backward-compatibility check (`demand_dispatch_mw`/`demand_bound` both shape `(0,)`,
  dispatch unaffected), on top of the full existing suite's 68 zero-regression tests.

## Commit

`972d7f9` on `wave/04-nodal-market` (on top of S1+S2's `6578709`), pushed. Staged exactly
`src/mambo_power/opf/dc_opf.py` and `tests/unit/test_opf_dc_demand.py` — the two files this
slice touched, by exact path.

## Not done by this slice (explicitly out of scope, per the dispatch)

`opf/__init__.py`'s `solve_dc_opf`/`_cost_coeffs` (S4's job — the Network/Scenario-facing
wrapper), `market/` (doesn't exist yet, S4), `jobs/` (S6), `docs/` (S7),
`tests/_bids.py`/fixture-derivation (S5) — this slice's tests are entirely hand-built, no
fixture dependency, as instructed.
