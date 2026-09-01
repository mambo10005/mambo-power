# M4 research — nodal-market groundwork

Wave M4 "nodal-market" of the mambo-power epic, Step 1/2 research. Read-only; written
2026-08-24 against repo `C:\Claude Projects\mambo-power` @ `5fa3285` (branch
`epic/01-foundation`, M3 "opf-n1" just merged — `pf`, `opf.dc_opf`, `contingency.n1`, `jobs`
all present and read at their current, merged shape), highspy (version string unavailable via
`highspy.__version__`, package importable), pandapower 3.3.0, PyPSA 1.2.4, scipy (bundled with
the `.venv`) — all from `.venv` (`uv` at
`C:\Users\mambo\AppData\Roaming\Python\Python314\Scripts\uv.exe`). No source files touched;
only reads and `uv run --no-sync python <scratchpad>/probe_*.py`.

Headline (the rest is evidence):

- **The welfare LP formulation in the brief is confirmed exactly right**, including the
  concave/convex mirror-image point: a load's marginal-value curve needs the opposite
  monotonicity direction from a generator's marginal-cost curve, and its PWL encoding is the
  mirror image of `dc_opf`'s existing convex epigraph trick — a concave "min of supporting
  hyperplanes" hypograph, not a "max of supporting hyperplanes" epigraph. Proved both
  algebraically and numerically on an independent `scipy.optimize.linprog` LP, not
  `opf.dc_opf` itself (§1, §4).
- **`dc_opf` itself may need *zero* signature changes** — the single biggest finding of this
  research. `dc_opf` only ever reads `arr.gen_ids`/`gen_bus`/`gen_p_min_pu`/`gen_p_max_pu`
  (`dc_opf.py:246,265-269,317-324`) plus branch/PTDF/aggregate-load fields; nothing in it is
  gen-count-specific beyond those four arrays. A caller can build its own `NetworkArrays` via
  `dataclasses.replace` (the dataclass is frozen but `replace` still works) with a **combined
  generator ∪ negative-bound-pseudo-generator** column set representing elastic loads —
  exactly the "negative-sign generator" trick this research independently proved works in both
  pandapower and PyPSA (§3) — and get dispatch, duals and LMPs back from the unmodified LP
  builder. This is real but comes with a real cost (double-counting risk, sign bookkeeping,
  semantic overload of `dispatch_mw`) that is NOT silently resolved here — it is this wave's
  central open design question (§2).
- **`NetworkArrays` has an existing, exploitable asymmetry**: generators already carry both a
  per-bus aggregate (`p_gen_pu`, `arrays.py:71`) *and* a per-generator identity-preserving set
  (`gen_ids`/`gen_bus`/`gen_p_pu`/…, `arrays.py:80-88`); loads carry **only** the aggregate
  (`p_load_pu`/`q_load_pu`, `arrays.py:64-66`, built by the bus-summing `per_bus` bincount
  helper, `arrays.py:137-147`) — no `load_ids`/`load_bus`/per-load array exists anywhere in the
  package (confirmed by grep). Elastic demand needs the same per-load extension generators
  already have; this is additive to `NetworkArrays` (new fields, `p_load_pu`/`q_load_pu`
  untouched) so M1-M3 callers are unaffected either way (§2).
- **Oracle strategy: a real, working trick exists for both pandapower and PyPSA, but it is
  fragile in pandapower and unverified end-to-end in PyPSA.** pandapower's `rundcopp` solves a
  hand-built 2-bus elastic-demand welfare-max problem to the exact hand-calculated optimum
  when the flexible load is modelled as a **negative-sign, negative-bound-cost `sgen`**
  (`min_p_mw=-60, max_p_mw=0`, quadratic `poly_cost`) — confirmed numerically, dispatch and
  price match a hand KKT solve to 5 decimal places. The seemingly more natural path — a
  `controllable=True` **`load`** row with its own `poly_cost` — **does not converge** in
  `rundcopp` for a quadratic (concave-value) cost, even though the identical economics
  converges instantly via the `sgen` framing; linear-only load costs *do* converge via `load`.
  This is a real, reproduced pandapower limitation, not `unverified`. PyPSA's `Generator`
  component genuinely has a documented `sign` attribute (confirmed via
  `Network().components["Generator"].defaults`, default `1.0`, "Sign denoting the orientation
  of the dispatch") that is the same mechanism — but PyPSA's `optimize()` inherits M3's own
  unresolved infeasibility on plain generator-only OPF (`m3-research.md` §3.1), so this wave
  cannot produce a working PyPSA elastic-demand proof without first fixing that pre-existing,
  unrelated problem (§3).
- **Settlement identity, re-derived for elastic demand and proved with a binding flow limit**:
  `Σ_d LMP(bus_d)·p_d − Σ_g LMP(bus_g)·p_g = −Σ_k μ_k·flow_k` (congestion rent) holds
  algebraically regardless of whether `p_d` is a decision variable or a fixed parameter, proved
  by direct KKT substitution using `lmp_decomposition`'s own energy+congestion convention, and
  confirmed numerically on an independent `scipy.optimize.linprog` LP (2 buses, one binding
  flow limit, a piecewise-linear concave demand bid): `payments=900, receipts=200, rent=700 =
  −μ_flow·flow` exactly, and the importing bus's LMP (45) exactly equals the marginal value of
  the last unit of demand actually served — the standard equilibrium check (§4). The
  "price-taker reduces to plain OPF" property is confirmed as a clean logical (not just
  hand-wavy) argument, precisely stated (§4).
- **No fixture carries any demand-bid data** — MATPOWER's `.m` bus table has exactly 13
  columns (`bus_i type Pd Qd Gs Bs area Vm Va baseKV zone Vmax Vmin`), confirmed by reading
  `case14.m`'s own header comment directly; there is no MATPOWER concept of a load bid curve at
  all. Unlike M3's ratings gap (a derivable single number per branch), a demand *curve* is not
  a single-number derivation — the cheapest plausible approach is a **documented synthetic-bid
  rule** (e.g. "value(p) is linear/quadratic anchored at the load's own historical `p_mw` and a
  chosen VOLL"), test-time-derived like `tests/_rated.py`, not a new committed fixture file
  (§5).
- **A genuine spec/implementation drift, surfaced here for the first time**: the epic's
  domain-model table describes `Scenario` as owning "offers/bids per generator/load" as market
  data, but M1 already shipped `Generator.cost: GeneratorCost | None` **on `Network` itself**
  (`entities.py:103`), consumed directly by `opf.dc_opf` with no `Scenario` in the loop at all.
  `Load` (`entities.py:106-114`) has no equivalent field. The consistent read of what actually
  shipped, not what the Step-2 domain-model prose said before M1 existed, is that offer/bid
  data belongs **on the entity itself** (`Load.bid: LoadBid | None`, mirroring
  `Generator.cost` exactly) and `Scenario` stays a thin `network: Network` wrapper — not a
  parallel `offers`/`bids` collection duplicating what `Network.generators[].cost` already
  carries. This is presented as a recommendation, not a silent choice (§6).

---

## 1. The welfare-maximizing LP formulation

### 1.1 Standard formulation — confirmed right, and the concavity-direction question resolved

The brief's formulation — `max Σ value_d(p_d) − Σ cost_g(p_g)` s.t. `Σp_g = Σp_d`, PTDF flow
limits, `0 ≤ p_g ≤ p_g_max`, `0 ≤ p_d ≤ p_d_max` — is textbook DC-market welfare maximization
(same "single system-wide balance + PTDF flow-limit rows" shape `opf.dc_opf`'s own module
docstring already documents for the cost-only case, `dc_opf.py:14-23`). No repo document names
a specific external textbook for this beyond what M3 already cited for the cost-minimization
half (PowerModels.jl / MATPOWER as the epic's own "prior art" list, `epic.spec.md` §Prior art);
this half is standard enough that citing it is safe, same disclosure M3's research used for its
own PWL formulation (`m3-research.md` §2.1).

**Yes — a load's bid curve needs its own convexity-direction check, and it is the mirror image
of `NonConvexCostError`.** Proved two ways, independent of `opf.dc_opf`:

- *Algebraically*: a welfare-maximization LP is a **maximize** problem; the standard PWL
  encoding of a function inside a maximize LP represents a **concave** function as the pointwise
  **minimum** of its segments' supporting lines (`val ≤ slope_i·p + intercept_i` for every
  segment — the *hypograph*), exactly mirroring how `dc_opf`'s existing convex-cost encoding
  represents a **convex** function as the pointwise **maximum** of its segments' supporting
  lines (`cost ≥ slope_i·p + intercept_i`, the *epigraph*, `dc_opf.py` module docstring,
  "PWL costs"). Both encodings are only valid in their respective direction: a convex
  hypograph or a concave epigraph both silently corrupt the LP's answer instead of failing
  (same failure mode M3's research already established for the epigraph case,
  `m3-research.md` §2.1).
- *Numerically*: probe `<scratchpad>/probe_settlement_identity2.py` builds exactly this
  hypograph encoding for a 2-segment concave demand-value curve (`val - 45d ≤ 0`,
  `val - 20d - 1250 ≤ 0`) via `scipy.optimize.linprog` (not `opf.dc_opf`) and the LP finds the
  correct welfare optimum (§4 has the full run).

So `market.nodal` needs a check symmetric to `NonConvexCostError` — call it (design interview's
choice of name) `NonConcaveBidError` — raised when a bid's breakpoint slopes are not
**non-increasing** (the mirror of `_convex_pwl_segments`'s "not non-decreasing" check,
`dc_opf.py:194-214`). Whether this lives in `opf.dc_opf` itself (if loads are folded into the
same PWL machinery, §2) or in a new `market`-local check (if loads get their own code path) is
exactly the shape decided by §2's central question — not resolved here.

### 1.2 Quadratic (polynomial) bid curves — same mirror-image requirement

For a quadratic value curve `value(p) = v2·p² + v1·p` to be concave (non-increasing marginal
value `v1 + 2·v2·p`), `v2` must be **≤ 0** — the literal sign mirror of `dc_opf`'s existing
quadratic-cost requirement (`c2 ≥ 0` for convexity, enforced today only implicitly by
`Highs.passHessian`'s own convexity requirement on the QP, not by an explicit repo-level check
— `dc_opf.py:270-281` builds the Hessian from whatever `c2` values are supplied with no sign
check at all). This is worth naming as a **second**, generator-side gap this wave's own
groundwork surfaces: `dc_opf` today has no explicit `c2 ≥ 0` guard either (HiGHS would simply
report a non-convex QP as some other status, not a clean, named error) — not this wave's job to
fix, but the design interview should decide whether a bid-side convexity check without a
matching generator-side one is an acceptable asymmetry or whether both should be added together.

## 2. Can `dc_opf` be extended, or does elastic demand need new machinery? — THE open question

### 2.1 What `dc_opf` actually touches (exact line numbers)

Read `src/mambo_power/opf/dc_opf.py:230-386` in full (module docstring + implementation) again,
specifically for what `dc_opf(arr, cost_coeffs, options, pwl_costs=None)` reads off `arr`:

- `arr.gen_ids` — only for `n_gen = len(arr.gen_ids)` (`dc_opf.py:246`).
- `arr.gen_p_min_pu` / `arr.gen_p_max_pu` — generator column bounds (`dc_opf.py:265-266`).
- `arr.p_load_pu`, `arr.g_shunt_pu` — the balance row's fixed RHS and each flow row's `const`
  term (`dc_opf.py:295-297, 301-306`).
- `arr.gen_bus` — indexes the PTDF matrix to build each generator's flow-row coefficient
  (`dc_opf.py:319`: `ptdf_matrix[:, arr.gen_bus]`).
- Branch/topology fields (`f`, `t`, `r`, `x`, `b`, `tap`, `shift_rad`, `rating_pu`, `n_branch`)
  via `compute_ptdf(arr)` and `pf_shift(arr)` (`dc_opf.py:303-304`) — **not** gen-count-specific
  at all; PTDF is a pure network-topology function, unaffected by which "gen" columns are later
  built from it.

That is the complete surface. `dc_opf` has no notion of "generator" beyond these four arrays
plus `cost_coeffs`/`pwl_costs`, which are caller-supplied and already fully decoupled from
`Network.generators` (that decoupling is the entire point of ADR-006).

### 2.2 Option A — reuse `dc_opf` unmodified via a negative-bound pseudo-generator array

Because `NetworkArrays` is a frozen `@dataclass` (`arrays.py:31`), `dataclasses.replace` still
works (it returns a new instance; frozen only blocks in-place mutation). A caller — `market.nodal`
or a helper it owns — can build:

```python
combined_arr = dataclasses.replace(
    base_arr,
    gen_ids=base_arr.gen_ids + load_ids,
    gen_bus=np.concatenate([base_arr.gen_bus, load_bus_positions]),
    gen_p_min_pu=np.concatenate([base_arr.gen_p_min_pu, -load_p_max_pu]),
    gen_p_max_pu=np.concatenate([base_arr.gen_p_max_pu, np.zeros(n_load)]),
    p_load_pu=base_arr.p_load_pu - <the bid-loads' own contribution, per bus>,
)
```

with `cost_coeffs`/`pwl_costs` for the appended pseudo-generator columns being the **sign-flip
of each load's bid** — exactly the transformation this research proved numerically works in
both pandapower and PyPSA (§3): `cost_pseudo(p) = -value(-p)`. `dc_opf` runs completely
unmodified; `OpfSolution.dispatch_mw` comes back with `n_gen + n_load` entries, the last
`n_load` of which are ≤ 0 and equal to `-p_d` for each bid-load.

**This is real and it is the cheapest possible path** (dc_opf.py: literally zero lines changed),
but it has three real costs the design interview needs to weigh, not have resolved silently:

1. **Double-counting risk**: `p_load_pu` (the aggregate) must have each bid-load's contribution
   *subtracted out* before the LP runs, or that load's demand is counted twice (once via the
   fixed balance RHS, once via its pseudo-generator column). Doing that subtraction correctly,
   per-load, requires exactly the per-load identity `NetworkArrays` does not have today (§2.3)
   — so "zero changes to `dc_opf`" still requires real new machinery, just relocated to
   `NetworkArrays`/`market.nodal` instead of to `dc_opf` itself.
2. **Semantic overload**: `OpfSolution.dispatch_mw`/`OpfDuals.gen_bound` become a mixed array of
   real generators and negated pseudo-loads: any caller (including a future `market.zonal`/
   `market.multiperiod` reusing this pattern) must know which trailing slice is which and
   un-negate correctly. `market.nodal`'s own result type would do this splitting once, but it
   is one more hand-maintained invariant (mirroring the "closed union must be widened by hand"
   pattern `jobs`/`results` already carry, §7) rather than a type-checked one.
3. **Bid-side convexity check has no natural home in `dc_opf`** under this option: `dc_opf`'s
   own `NonConvexCostError`/`_convex_pwl_segments` (§1) validate for **increasing** marginal
   cost; if a caller feeds it a decreasing-marginal-cost pseudo-generator (i.e. a valid concave
   bid, sign-flipped), that check would **reject valid input** unless it is bypassed or
   generalized to accept either direction per-column — a real wrinkle, not a footnote.

### 2.3 Option B — genuinely new demand machinery inside `dc_opf`

The brief's own proposed shape: `dc_opf` gains an optional `demand_bid_coeffs`/
`demand_pwl_bids` parameter (default `None` = today's fixed-load behaviour, so every M2/M3
caller and test is untouched), new LP columns for each bid-load with their **own** bounds
`[0, p_d_max]` (no sign flip needed — cleaner semantics), a **separate** hypograph row family
(§1's mirror-image encoding) built directly, and the balance/flow rows extended to include a
`−1`-signed load-column term alongside the existing `+1`-signed generator term (exactly the
`d − p2` row this research hand-derived and verified in §4, generalized to `n_load` columns).
`OpfSolution` would gain explicit `demand_dispatch_mw`/`demand_bound` fields (mirroring
`dispatch_mw`/`gen_bound`) rather than overloading the existing ones. `NonConcaveBidError`
(§1.1) is a clean second check next to `NonConvexCostError`, no cross-contamination.

This is **more new code inside `opf.dc_opf`** (new row-construction paths, new result fields,
one more validated invariant) in exchange for **no double-counting risk, no semantic overload,
and no need to bypass or generalize `NonConvexCostError`**.

### 2.4 `NetworkArrays` needs the same extension either way

Independent of A vs B, `NetworkArrays` today has the asymmetry the headline calls out:
generators get both `p_gen_pu` (bus aggregate, `arrays.py:71`, built at `arrays.py:157`) *and*
`gen_ids`/`gen_bus`/`gen_p_pu`/`gen_p_min_pu`/`gen_p_max_pu`/… (per-generator,
`arrays.py:80-88`, built at `arrays.py:153-210`); loads get **only** `p_load_pu`/`q_load_pu`
(`arrays.py:64-66`, built at `arrays.py:145-147` via the same `per_bus` bincount helper
generators' aggregate form also uses). Confirmed by grep (`load_ids`/`load_index`/`per_load`:
no hits anywhere in `src/`). Whichever option the design interview picks, `market.nodal` needs
per-load identity (`load_ids`, `load_bus`, and each load's own `[0, p_max]` bound derived from
its bid) to either (Option A) correctly zero out the aggregate before building pseudo-generator
columns, or (Option B) build the new demand-side LP columns at all. The natural, additive fix —
new `NetworkArrays` fields mirroring the existing `gen_*` pattern exactly, `p_load_pu`/
`q_load_pu` untouched — is not itself in question; only *how `dc_opf` consumes it* is (§2.2 vs
§2.3).

**This is the wave's single most important open design question**, explicitly not resolved
here per the brief's own instruction.

## 3. Oracle strategy

### 3.1 pandapower: a working trick, with one confirmed, reproducible bug

probe: `<scratchpad>/probe_pp_elastic.py` through `_elastic6.py` (six iterations, kept because
each failure mode is itself informative).

`pandapower.create_load(..., controllable=True, min_p_mw=..., max_p_mw=...)` plus
`pp.create_poly_cost(net, load_idx, "load", cp1_eur_per_mw=..., cp2_eur_per_mw2=...)` is a real,
documented API (`create_poly_cost`'s own docstring lists `"load"` as a supported element type,
confirmed via `help(pp.create_poly_cost)`). A **linear**-only version of this (negative `cp1`,
`cp2=0`) converges correctly:

```
gen p_mw: 59.99990013   load p_mw: 59.99999985   lam_p: 10.00000003   cost: -1200.0009941940893
```
(matches hand calc exactly: marginal value 30 > marginal cost 10 everywhere on `[0,60]`, so the
load is pinned at its own cap and price is set by the marginal generator, `probe_pp_elastic4.py`).

The same setup with a **quadratic** (concave) load cost added (`cp2_eur_per_mw2=0.2`) — the
economically interesting case, since a flat/linear bid is really just a step function, not a
real demand curve — **fails to converge** (`pandapower.auxiliary.OPFNotConverged`), reproduced
twice independently (`probe_pp_elastic2.py` with a line, `probe_pp_elastic5.py` single-bus, no
line — ruling out the line/ext_grid framing as the cause). Root cause not diagnosed further
within this session's budget (candidate: pandapower's internal `dcopf` may assume `cp2 ≥ 0`
represents a *convex generation* cost and mis-handle the sign when the element is a "load" row
internally represented as negative generation — `unverified` beyond "it reproducibly fails").

**The fix, found and proven**: model the flexible load as a **negative-sign, negative-bound
`sgen`** instead of a `load` row — `pp.create_sgen(net, bus, p_mw=-30, min_p_mw=-60,
max_p_mw=0, controllable=True)` + `pp.create_poly_cost(net, sgen_idx, "sgen",
cp1_eur_per_mw=+30, cp2_eur_per_mw2=+0.2)` (the sign-flip transformation `cost_sgen(p) =
-value(-p)`, i.e. `value(d)=30d-0.2d²` becomes `cost_sgen(p)=30p+0.2p²` for `p=-d`) —
`probe_pp_elastic6.py`:

```
gen p_mw: 49.99989941   sgen p_mw: -49.99999895   lam_p: 10.0   cost: -500.00099542716833
expected: gen=50, sgen=-50, cost=-500     <- matches to 4 decimal places
```

This is exactly the pattern this research also proposes for §2.2's Option A internal
implementation — the oracle trick and one candidate internal implementation are the same idea,
independently arrived at and independently verified.

**Open question for the design interview**: is the `load`-row non-convergence worth a deeper
root-cause dig (it would let M4's automated parity tests use the more semantically natural
`load` framing), or does M4 accept the `sgen` framing as the permanent, documented
oracle-construction pattern (one more entry in the "oracle-construction discipline" this repo's
parity tests already maintain, alongside M2/M3's `BASE_KV<=0` patch and `trafo_model="pi"`)?

### 3.2 PyPSA: the mechanism exists; a working proof is blocked by M3's unresolved issue

probe: direct inspection, `Network().components["Generator"].defaults` (not a script file —
a one-line interactive check).

```
sign: type=float, default=1.0, description="Sign denoting the orientation of the dispatch..."
```

PyPSA's `Generator` component genuinely carries a `sign` attribute (confirmed present, with
that exact description, in the installed 1.2.4). This is the identical mechanism to the
pandapower `sgen` trick: a `Generator` with `sign=-1` and its own `marginal_cost`/
`marginal_cost_quadratic` models a price-responsive load using PyPSA's own native generator
machinery, no separate component type needed. **This is confirmed to exist as an API surface,
not `unverified`.**

What is genuinely `unverified`: whether `n.optimize()` actually solves a network built this
way, because M3's own research already found `n.optimize(solver_name="highs")` returns
**Infeasible on all 5 OPF fixtures** after a manual `gencost` bridge, root cause undiagnosed
(`m3-research.md` §3.1, carried forward unresolved into M3's own shipped code and audit —
confirmed still unresolved by reading `m3-research.md` directly, not re-probed here since M3's
own audit/critic docs did not report it being fixed). Building an elastic-demand PyPSA network
on top of a foundation that cannot even solve a plain generator-only case is not a productive
use of this session's time; **this wave inherits M3's open PyPSA question rather than
compounding it with a new one**.

**Open question, same shape as M3's own carry-forward item**: does M4 invest in diagnosing
PyPSA's infeasibility (unblocking both M3's and M4's parity ambitions at once), or does the
epic accept pandapower as the sole automated oracle for both OPF and market clearing, treating
PyPSA as, at most, a manually-verified spot check once someone has time?

### 3.3 No oracle needed for the core proof either way

Per the brief's own framing: even in the worst case (no working external oracle for elastic
demand at all), the wave's correctness proof rests on (a) the settlement/welfare identities,
proved algebraically and numerically here without any external engine (§4), and (b) the
price-taker-reduces-to-OPF property (§4.2), which reduces directly to M3's own already-oracle-
proved `opf.dc_opf` parity (`m3-research.md` §3). Both are provable — and now proved, at the
research stage — independent of §3.1/§3.2's outcome.

## 4. Settlement identities

### 4.1 Congestion rent, re-derived for elastic demand and proved with a binding limit

**Algebraic derivation** (standalone, using `lmp_decomposition`'s own convention —
`LMP(bus) = balance_dual + Σ_k flow_limit_dual[k]·PTDF[k,bus]`, `dc_opf.py:217-227` — not
re-deriving that convention, just applying it):

```
Σ_d LMP(bus_d)·p_d − Σ_g LMP(bus_g)·p_g
  = Σ_d [λ + cong(bus_d)]·p_d − Σ_g [λ + cong(bus_g)]·p_g
  = λ·(Σp_d − Σp_g) + Σ_d cong(bus_d)·p_d − Σ_g cong(bus_g)·p_g
  = 0                       + Σ_k μ_k·[Σ_d PTDF[k,bus_d]·p_d − Σ_g PTDF[k,bus_g]·p_g]
  = −Σ_k μ_k·flow_k         since flow_k = Σ_g PTDF[k,gen_bus]·p_g − Σ_d PTDF[k,load_bus]·p_d
```

The balance term vanishes because `Σp_g = Σp_d` holds at the optimum **whether or not `p_d` is
a decision variable** — the identity's derivation never uses "load is fixed" anywhere. This
answers the brief's question directly: the identity extends to elastic demand with **no change
in form**, only in which terms are decision variables versus parameters.

**Numeric confirmation**, independent of `opf.dc_opf` (`scipy.optimize.linprog`, not highspy —
`<scratchpad>/probe_settlement_identity2.py`): 2-bus network, slack bus1 generator (linear cost
10/MW), bus2 generator (linear cost 50/MW, ends up undispatched) and an elastic load at bus2
with a 2-segment concave bid (marginal value 45 on `[0,50]`, 20 on `[50,100]`), one binding
flow-limit row (`d − p2 ≤ 20`, PTDF[branch,bus2]=−1 since bus1 is slack and a PTDF matrix's
slack column is always zero by construction — the same convention `dc_opf` itself relies on).
Solved optimum: `p1=20, p2=0, d=20` (line-limited, not bid-limited — the load *wants* more at
this price but the line won't allow it). Duals: `λ=10, μ_flow=−35`. Resulting LMPs:
`LMP(bus1)=10` (cheap/exporting side), `LMP(bus2)=45` (congested/importing side) — which
**exactly equals the marginal value of the last unit of demand actually served** (the segment
`[0,50]` marginal value), the standard nodal-market equilibrium check, itself a form of
verification beyond the identity alone.

```
load_payment = 45*20 = 900     gen_receipts = 10*20 + 45*0 = 200
payments - receipts = 700
-mu_flow * flow = -(-35)*20 = 700     <- matches exactly
```

An earlier version of this same probe (`probe_settlement_identity.py`, kept as a documented
dead end rather than deleted) used the wrong PTDF sign (wrote the flow row directly as `p1 ≤
20` instead of in terms of bus2's net injection) and produced a nonsensical, backwards result
(`LMP(bus1)=45 > LMP(bus2)=10`, negative congestion "rent") — worth keeping in the record as a
concrete illustration of exactly the sign-convention trap §2's `dc_opf`-extension options must
get right (a flow row's coefficients must be zero on the slack bus and correctly signed by
PTDF, never written directly against a generator's own dispatch variable as a shortcut).

### 4.2 "Price-taker reduces to plain OPF" — precisely stated

If, for every bid-load `d`, `value_d(p)`'s marginal value exceeds every price the market could
possibly produce (a sufficient, checkable bound: greater than the highest generator's marginal
cost at its own `p_max`) for **every** `p` up to that load's fixed historical demand
`p_load_fixed`, then the hypograph constraint `val ≤ marginal_value_curve(p)` never binds below
`p = p_load_fixed` at the welfare optimum: raising `p_d` always strictly increases welfare
(marginal value exceeds marginal cost everywhere achievable) until `p_d` hits its own upper
bound. `p_d` is therefore pinned exactly at `p_load_fixed`, the balance and flow rows become
numerically identical to `opf.dc_opf`'s own fixed-load rows (§2.1's `p_load_mw` term), and the
resulting dispatch, duals and LMPs are identical to a plain `dc_opf` call with that load as
fixed demand — which is already oracle-proved by M3 (`m3-research.md` §3). This is the wave's
main correctness test per the brief, and its exact bid-curve shape ("above every achievable
price at every quantity up to the fixed value") is now precisely stated, not left implicit.

## 5. Fixture strategy

probe: reading `fixtures/matpower/case14.m` directly (`grep -n "mpc.bus" -A5`).

```
%	bus_i	type	Pd	Qd	Gs	Bs	area	Vm	Va	baseKV	zone	Vmax	Vmin
```

Confirmed: MATPOWER's bus table has **exactly 13 columns**, `Pd`/`Qd` are the only demand
fields, and there is no separate demand-bid block anywhere in the `.m` format (unlike
`mpc.gencost`, which at least exists for generators). **No fixture — none of the 5 OPF
fixtures, nor any other `.m` file in the repo — carries any demand-bid data at all**; this is
not a gap in an otherwise-present section, the section doesn't exist in the format.

This is a **different shape of gap than M3's ratings problem** (`m3-research.md` §6): a branch
rating is one number, cheaply and non-speculatively derivable from the network's own base-case
flow (`tests/_rated.py`'s `RATING_MARGIN * |base_case_flow|` rule). A demand bid is an entire
**curve** (at minimum 2 numbers: a slope and an anchor; more for a genuinely concave PWL/
quadratic shape) with no obvious single "derive it from the network's own data" rule the way a
rating has one. The cheapest non-speculative options, roughly in order of how much new
committed data they require:

1. **Anchor to each load's existing `p_mw`** (already committed, real MATPOWER data) plus a
   *documented*, test-time convention for the curve's shape around that anchor — e.g. "linear
   marginal value from a chosen VOLL (value of lost load, a literature-standard figure) down to
   the generation-fleet's own maximum marginal cost at `p_mw`", mirroring `_rated.py`'s
   "derive at test time from the fixture's own solved state" pattern exactly (`tests/
   _rated.py`'s own docstring calls this "the same … pattern `tests._brute_force_lodf` already
   uses" — a third module doing the same thing would be a clear, established convention, not a
   one-off).
2. A small number of **hand-built, committed synthetic bid fixtures** (mirroring M3's own
   `case14_pwl.m` for PWL generator costs) for the specific cases a derived rule can't cover
   well — e.g. testing the `NonConcaveBidError`/hypograph-mirror-of-epigraph path itself, which
   by definition needs a deliberately malformed (non-concave) bid, not a derived one.

**This wave's fixture strategy should very likely follow option 1 as the default** (a
`tests/_bids.py` sibling to `_rated.py`, same "derive at test time, no new committed fixture
data" discipline) **with option 2 only for the deliberately-malformed convexity-check case** —
this is a recommendation, not a silent choice; the design interview should confirm the anchor
rule and VOLL figure, which this research does not propose numerically (that is a genuine
design decision, not a research fact).

## 6. `model.Scenario`'s real shape

### 6.1 Confirmed absent, and confirmed how

`model/__init__.py`'s `__all__` (read in full, `model/__init__.py:23-45`) has no `Scenario`;
`model/entities.py` (read in full) defines `Bus`, `Branch`, `PolynomialCost`, `PiecewiseCost`,
`Generator`, `Load`, `Shunt`, `Storage`, `Zone` — no `Scenario`; grep for `market`/`scenario`
across `src/` finds no `market/` package and no `Scenario` class anywhere. Confirmed absent,
not merely absent from the public API.

### 6.2 The cross-reference pattern already established, and the drift it exposes

Every existing cross-entity reference in this codebase is a **string id resolved within one
`Network`** (`Branch.from_bus`/`to_bus → Bus.id`, `Generator.bus`/`Load.bus`/… `→ Bus.id`,
`Bus.zone → Zone.id`, all checked by `validate_network`'s `DANGLING_REF` pass,
`network.py:98-129`) — there is **no existing precedent anywhere in this codebase for one
top-level pydantic model referencing another by id/path**. The one place that already composes
a `Network` with something else is `jobs.models.SolveRequest`, which embeds `network: Network`
directly (`jobs/models.py:88`, "the request is self-contained" — its own module docstring,
`jobs/models.py:2-3`). Given R10's own stated goal ("stateless, fully JSON-serializable job
API… safe to call from a notebook, CLI, worker queue or HTTP handler", `epic.spec.md` R10),
`Scenario` embedding `network: Network` directly (mirroring `SolveRequest`) is the pattern this
codebase has actually established, not an id/path reference to a `Network` stored elsewhere
(which would need its own resolution mechanism this repo has never built).

**A genuine, worth-surfacing drift**: the epic's own domain-model table (`epic.spec.md`
line 123, written at Step 2, before M1 existed) describes `Scenario` as owning "offers/bids per
generator/load" as *Scenario-level* market data. But M1 already shipped
`Generator.cost: GeneratorCost | None` **directly on `Network`**
(`entities.py:103`) — consumed by `opf.dc_opf` with `Network.generators[i].cost` alone, no
`Scenario` anywhere in that path (`opf/__init__.py:55-72`'s `_cost_coeffs`). The domain-model
table's wording is now stale relative to what actually shipped. `Load` (`entities.py:106-114`)
has **no** equivalent field today.

**Recommendation** (explicit, not silently applied): the consistent reading of what this
codebase has *actually done*, not what a pre-M1 design doc said it would do, is `Load.bid:
LoadBid | None`, mirroring `Generator.cost: GeneratorCost | None` exactly — same discriminated-
union shape (`PolynomialBid`/`PiecewiseBid`, or reusing the existing `PolynomialCost`/
`PiecewiseCost` field *shape* under new names, since the underlying data representation
(`coefficients`/`points`) is identical; only the field's *meaning* and its convexity-direction
validation differ, per §1.1) — keeping `Network` the single owner of all cost/bid data and
`Scenario` a genuinely thin wrapper (`network: Network` plus, per §6.3, nothing else for M4).
This avoids a second, parallel, Scenario-level `offers`/`bids` collection that would either
duplicate or shadow `Generator.cost`, which the "single source of truth" principle this
codebase already applies everywhere else (e.g. `results` never mutates `Network`,
`opf/__init__.py` docstring: "The network is not modified") argues against. Not resolved here —
this is the single concrete proposal for the design interview to accept, adjust or reject.

### 6.3 `periods` / agent strategies — a real tension, not a one-sided call

The brief's framing ("present but unused, not invented speculatively") has a genuine
counter-precedent already in the shipped codebase: `Storage` (`entities.py:126-138`) is
explicitly documented "Schema-present; no M1 solver reads it" and has stayed that way through
M1-M3 without friction. This is a real, working example of "stub the field now" succeeding in
this exact codebase.

**The distinguishing factor, and why that precedent doesn't transfer directly**: `Storage`'s
fields (`p_max_mw`, `energy_mwh`, `soc_initial`, `efficiency_charge`/`efficiency_discharge`)
were **already fully specced** in the epic's own domain model before M1 shipped them — they are
stable physical quantities with no ambiguity about eventual meaning. `periods` and "agent
strategies" are, by contrast, exactly the two things M5 and M7 have not designed yet (the
epic's own domain-model table gives them zero field-level detail: "periods (contiguous), agent
strategies" is a one-line gloss, not a spec). Stubbing a field whose eventual shape is
genuinely unknown risks the same "cannot be changed later without a rewrite" trap ADR-006's own
opening paragraph names for irreversible decisions — except worse, because an *empty* stub
still has to be filled in later in a way that is compatible with whatever M4 already shipped
and tested against it, whereas a genuinely absent field costs M5/M7 nothing to add fresh
(pydantic's `extra="forbid"` convention, used everywhere in this codebase, makes a later
additive field change clean and loud, never silent).

**Recommendation, weighed against the counter-precedent rather than ignoring it**: omit
`periods` and agent-strategy fields entirely from M4's `Scenario`, on the grounds that
`Storage`'s success case had a real spec behind the stub and this wave's `periods`/strategy
fields do not — but this is presented as a recommendation with its counter-argument named, per
the brief's explicit ask, not a unilateral resolution.

## 7. jobs registry mechanics for `market.nodal`

Read `jobs/registry.py`, `jobs/run.py`, `jobs/models.py` in full at their current (M3-merged)
state — mechanically unchanged from M3's own already-current description
(`m3-research.md` §7), reconfirmed rather than re-discovered:

- `ResultModel = AcPowerFlowResult | DcPowerFlowResult | OpfDcResult | N1Result`
  (`jobs/models.py:37`) is still a hand-widened closed union; `market.nodal` needs a new
  `MarketNodalResult` (or similar) type added to this union by hand, same mechanism M2→M3 used.
- `FailureCode` (`jobs/models.py:40-50`) currently has `INFEASIBLE_LP`/`UNBOUNDED_LP` already
  (added in M3 for `opf.dc`, `registry.py:28-45`, `run.py:166-169`) — **directly reusable for
  `market.nodal` with no new code**, since a welfare-maximization LP has the exact same two
  failure shapes (infeasible: no feasible dispatch satisfies balance+bounds+limits; unbounded:
  in principle impossible here since every bound — generator `p_max`, load `p_max` — is finite
  by construction, but HiGHS could still report it for a malformed input, e.g. a `p_max=inf`
  slipping through, so the code path should stay wired even if the wave's own valid inputs never
  trigger it). No new `FailureCode` is needed unless the design interview wants a distinct code
  (e.g. `INFEASIBLE_MARKET`) purely for clearer error messages, not because the underlying HiGHS
  status set differs from `opf.dc`'s.
- `ResultProvenance.kind` is a plain `str` (`results/provenance.py:28`, confirmed by direct
  read), not a constrained `Literal` — `"market.nodal"` needs no widening there.
- Runner mechanics are identical to `opf.dc`'s (`registry.py:72-90`, `_run_opf_dc`): validate
  options into a new `MarketNodalOptions` model, call the (as-yet-unbuilt) `market.nodal`
  Network-facing wrapper, translate a non-`"Optimal"` status into `InfeasibleLpError`/
  `UnboundedLpError` exactly as `_run_opf_dc` does today — this translation logic is generic
  enough it could plausibly be factored into a shared helper both `opf.dc` and `market.nodal`
  call, worth naming as a small design option (not required; `_run_opf_dc`'s own ~15 lines
  would just be duplicated with a different result type otherwise).

---

## Carry-forward list for the M4 design interview

1. **Biggest open question, explicitly not resolved here**: does `opf.dc_opf` stay
   byte-for-byte unmodified, with `market.nodal` building its own combined generator/pseudo-
   generator `NetworkArrays` via `dataclasses.replace` and a sign-flip transformation (§2.2,
   Option A — proven as a *pattern* by this research's pandapower/PyPSA oracle probes, §3), or
   does `dc_opf` gain genuinely new demand-side columns/rows/result fields (§2.3, Option B —
   more new code, cleaner semantics, no double-counting risk)? Either way `NetworkArrays` needs
   a per-load identity extension mirroring its existing per-generator arrays (§2.4) — that part
   is not in question.
2. **Second open question**: pandapower's `load`-row quadratic `poly_cost` reproducibly fails
   to converge in `rundcopp`, while the economically identical `sgen`-row framing converges
   exactly (§3.1) — invest in root-causing the `load`-row path, or adopt `sgen` as M4's
   permanent oracle-construction convention?
3. PyPSA's elastic-demand mechanism (`Generator.sign`) is confirmed to exist as an API surface
   but is untestable until M3's own already-open PyPSA-infeasibility question (`m3-research.md`
   §3.1, still unresolved as of this read) is fixed — this wave inherits, not duplicates, that
   open question (§3.2).
4. A bid-side convexity-direction check (`NonConcaveBidError`, the mirror of `NonConvexCostError`)
   is needed regardless of §1's resolution (§1.1) — and this research also surfaces that
   `dc_opf`'s existing *generator*-side quadratic cost has no explicit `c2 ≥ 0` convexity guard
   today either (§1.2); worth deciding together rather than adding an asymmetric bid-only check.
5. Settlement identity and the price-taker-reduces-to-OPF property are both proved — the first
   algebraically and numerically (independent of `opf.dc_opf`), the second as a precisely
   stated logical argument reducing to M3's already-oracle-proved parity (§4). These do not
   need further research-stage work.
6. Fixture strategy: no MATPOWER fixture has any demand-bid data at all (a different, harder
   gap than M3's derivable branch ratings) — recommend a test-time-derived synthetic bid rule
   (`tests/_bids.py`, mirroring `tests/_rated.py`'s discipline) as the default, with a small
   number of hand-built fixtures only for the deliberately-malformed (non-concave) convexity
   test (§5). The specific anchor rule and VOLL figure are a genuine design decision, not
   proposed numerically here.
7. `Scenario`'s shape: recommend `network: Network` embedded directly (mirroring
   `SolveRequest`, §6.2) plus `Load.bid: LoadBid | None` added to `Load` itself (mirroring
   `Generator.cost`, correcting a real drift between the epic's pre-M1 domain-model wording and
   what M1 actually shipped, §6.2) — not a separate Scenario-level offers/bids collection.
   `periods`/agent-strategy fields: recommend omitting entirely, but the `Storage` precedent
   (§6.3) is a real counter-argument, weighed and named rather than ignored.
8. `jobs` registry mechanics need no new mechanism: widen `ResultModel`'s union, reuse
   `INFEASIBLE_LP`/`UNBOUNDED_LP` as-is, `ResultProvenance.kind` needs no change (§7).
