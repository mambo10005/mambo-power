# M6 AC-2 derivation — the zonal LP's hand-solvable fixture

Wave M6 "zonal-redispatch" of the `mambo-power` epic, Step 4 (researcher). Read-only against
repo `C:\Claude Projects\mambo-power` @ `4cfd1d7` (branch `epic/01-foundation`); no source files
touched. Every number below was reproduced by running code — none is `unverified`. Two
independent verification paths are used throughout, per M5-§7's style:

1. **The zonal LP** (`opf.zonal` — not yet built; W2) is hand-derived (KKT) and cross-checked
   against a **hand-built `scipy.optimize.linprog`** formulation of the same LP.
2. **The nodal reference** on the identical physical network is computed two ways: by hand
   (exploiting the network's radial/tree topology, where DC-flow is impedance-independent), and
   by calling this repo's own **pre-existing** (M2/M3/M4, already-merged) `opf.dc_opf` /
   `market.solve_nodal` directly on a hand-built `Network`/`Scenario` — not the unbuilt zonal
   builder, and not read-only-violating (only reads/runs existing code, writes nothing).

Scripts: `<scratchpad>/m6_ac2_probe.py` (zonal LP, scipy), `<scratchpad>/m6_ac2_nodal.py` (nodal
reference via `solve_nodal`), `<scratchpad>/m6_ac2_bidload.py` (optional bid-load variant, both
ways). Run as `cd "C:\Claude Projects\mambo-power" && uv run --no-sync python <script>`.

---

## 1. The fixture

A 2-zone/3-bus network, per AC-2's literal wording (not the 2-bus sketch the task brief first
suggested — the committed AC names 3 buses, so zone A is split across two buses joined by an
intra-zone branch that never binds, which is also a useful proof that the zonal LP is right to
carry **no** intra-zone flow row — b2, `record/m6-research.md` §2(b)):

| entity | zone | detail |
|---|---|---|
| bus1 | A | generator `genA`, linear cost `c_A = 10 $/MWh`, `p_max = 200 MW` |
| bus2 | A | fixed load `L_A = 50 MW` |
| bus3 | B | generator `genB`, linear cost `c_B = 50 $/MWh`, `p_max = 200 MW`; fixed load `L_B = 30 MW` |
| branch `br12` | intra-zone A | unrated (never binds; not part of the zonal LP at all) |
| branch `br23` | the A–B corridor | rated `C = 20 MW` (chosen so it binds: zone B wants `L_B = 30 MW` of cheap import, capped at 20) |

Every number is a small integer; `p_max` is set far above anything either generator ever
dispatches (70/80 vs. 200) so it's never the binding bound, isolating the corridor as the only
interesting constraint.

## 2. The zonal LP (b2 formulation), corridor binding — hand KKT

Variables `p_A, p_B >= 0`, one exchange column `f_AB` (zone A's withdrawal / zone B's injection,
the b2 convention — `record/m6-research.md` §2(b): "a corridor's own cut-set rating... a plain
variable bound"), bounded `-C <= f_AB <= C` (only the upper bound binds here since zone B is the
importer). Two per-zone balance rows, reusing `dc_opf._balance_row`'s own sign convention
(injection `+1`, withdrawal `-1`, `src/mambo_power/opf/dc_opf.py:396-418`):

```
zone A:  p_A - f_AB == L_A        (dual λ_A)
zone B:  p_B + f_AB == L_B        (dual λ_B)
```

```
minimize   c_A p_A + c_B p_B
subject to p_A - f_AB = L_A
           p_B + f_AB = L_B
           0 <= p_A <= 200,  0 <= p_B <= 200,  -C <= f_AB <= C
```

**KKT.** Lagrangian `L = c_A p_A + c_B p_B - λ_A(p_A - f_AB - L_A) - λ_B(p_B + f_AB - L_B)
- ν(C - f_AB)` with `ν >= 0` the multiplier of the active upper bound `f_AB <= C` (the lower
bound `f_AB >= -C` and both generator bounds are inactive at this solution — checked below).
Stationarity:

```
∂p_A: c_A - λ_A = 0                →  λ_A = c_A = 10
∂p_B: c_B - λ_B = 0                →  λ_B = c_B = 50
∂f_AB: λ_A - λ_B + ν = 0           →  ν = λ_B - λ_A = 40
```

Primal feasibility with `f_AB` pinned at its cap: `f_AB* = C = 20`, `p_A* = L_A + f_AB* = 70`,
`p_B* = L_B - f_AB* = 10`. Both `70` and `10` are strictly inside `[0, 200]`, confirming the
generator-bound multipliers are 0 and the stationarity equations above are the whole story.
Objective `= c_A p_A* + c_B p_B* = 10·70 + 50·10 = 1200`.

**Closed form** (general form for S3 to transcribe):

```
f_AB* = C
p_A*  = L_A + C
p_B*  = L_B - C
λ_A   = c_A
λ_B   = c_B
ν     = c_B - c_A          (corridor bound's own dual == price difference)
obj*  = c_A(L_A + C) + c_B(L_B - C)
```
valid whenever `0 <= L_A + C <= P_A_max`, `0 <= L_B - C <= P_B_max`, and `c_A < c_B` (so the
corridor wants to carry cheap power toward B — this fixture's `10 < 50` and `0 <= 70,10 <= 200`
all hold).

### Independent scipy cross-check

`m6_ac2_probe.py`, `scipy.optimize.linprog(method="highs")`, variables `[p_A, p_B, f_AB]`:

```
=== Zonal LP, corridor binding (C = 20.0) ===
success: True status: 0
p_A=70.000000  p_B=10.000000  f_AB=20.000000
objective: 1200.0
eqlin.marginals (row duals, zone A / zone B): [10. 50.]
upper/lower bound marginals: [  0.   0. -40.] [0. 0. 0.]
```

Matches the hand solve exactly (dispatch, objective, both zone-price duals, corridor-bound
marginal magnitude 40).

**scipy's dual sign convention, stated and verified.** For `linprog`'s `min c^T x` with
`A_eq x = b_eq`, `res.eqlin.marginals` is `d(objective)/d(b_eq)` at the optimum — i.e. the
*price* directly, the same convention `dc_opf.OpfDuals.balance` already uses (its own docstring:
the balance dual "also exactly equal[s] an unconstrained... generator's own linear cost
coefficient" — no sign flip needed to call it a price). Confirmed numerically: perturbing `L_A`
by `+1` MW and re-solving gives `Δobjective = 10.0`, exactly `eqlin.marginals[0] = 10.0`
(`m6_ac2_probe.py`, "scipy dual sign-convention check" block). Bound marginals follow the mirror
convention for a minimize problem: `res.upper.marginals[k] = d(obj)/d(upper_bound_k) <= 0` when
that bound binds (relaxing an upper bound can only help, i.e. lower cost) — here `-40`, meaning
raising `C` by 1 MW would lower the objective by 40, i.e. `|upper.marginals| = ν` exactly.
`res.lower.marginals[k] = d(obj)/d(lower_bound_k) >= 0` when a lower bound binds — this is the
standard "reduced cost" of a variable pinned at its floor (used below for `p_B` in the
copper-plate case).

## 3. Copper-plate degenerate control (`C → ∞`)

With the cap removed, summing the two balance rows makes `f_AB` cancel entirely
(`(p_A - f_AB) + (p_B + f_AB) = p_A + p_B = L_A + L_B`) — exactly `record/m6-research.md` §2(a)'s
point that an unconstrained exchange variable collapses the per-zone rows into the single
system-wide balance `dc_opf` already builds. The LP is then plain merit-order dispatch of
`L_A + L_B = 80 MW` against `c_A = 10 < c_B = 50`: the cheap generator serves everything it can
(`p_A* = 80 <= 200`), the expensive one is idle (`p_B* = 0`, at its **lower** bound, not
interior). `f_AB* = L_B - p_B* = 30` — the corridor still carries a real flow, just an
unconstrained one.

**Hand KKT.** With no active bound on `f_AB`, its stationarity condition loses the `ν` term
entirely: `λ_A - λ_B = 0 → λ_A = λ_B`. From `p_A*` interior (`80 < 200`): `λ_A = c_A = 10`. Since
`λ_A = λ_B`, **both zone prices equal `10`** — the "one national price wearing per-zone labels"
`record/m6-research.md` §2(a) predicts for the unconstrained case. `p_B*` sits at its lower bound
with reduced cost `c_B - λ_B = 50 - 10 = 40 >= 0` (correctly non-negative: turning it on would
cost 40 more than it's worth). Objective `= 10·80 + 50·0 = 800`.

### Independent scipy cross-check (cap = 1e6, effectively unbounded)

```
=== Zonal LP, copper plate (cap effectively unbounded, C=1e6) ===
success: True status: 0
p_A=80.000000  p_B=0.000000  f_AB=30.000000
objective: 800.0
eqlin.marginals (row duals, zone A / zone B): [10. 10.]
upper/lower bound marginals: [0. 0. 0.] [ 0. 40.  0.]
```

`eqlin.marginals = [10, 10]` — the two zone-price duals are numerically identical, and
`lower.marginals[1] = 40` is `p_B`'s reduced cost, matching the hand value exactly.

### Nodal λ on the same network, no branch rating — must equal both zone prices

`m6_ac2_nodal.py` builds the actual 3-bus `Network` (bus1/bus2/bus3, `br12` unrated always,
`br23` with `rating_mva=None`) and calls this repo's own `market.solve_nodal` — the pre-existing
M2–M4 nodal builder, not the unbuilt zonal one:

```
--- corridor unrated (copper-plate nodal) ---
status: Optimal
  gen genA @ bus1: p=80.000000 MW  bound_dual=0.000000
  gen genB @ bus3: p=0.000000 MW  bound_dual=40.000000
  bus bus1: lmp=10.000000  energy=10.000000  congestion=0.000000
  bus bus2: lmp=10.000000  energy=10.000000  congestion=0.000000
  bus bus3: lmp=10.000000  energy=10.000000  congestion=0.000000
```

Dispatch (`80, 0`), the reduced cost on `genB` (`40`), and every bus's LMP (`10`, uniform — no
congestion anywhere) match the zonal copper-plate numbers exactly. **Why:** with no rating on
either branch, `dc_opf`'s own single system-wide balance row is, algebraically, the same
collapse the zonal per-zone rows underwent above — one balance constraint either way, so the two
formulations are the same LP up to relabelling. `_check_invariants`/PTDF details never enter it:
this is a topology fact (§4 makes it explicit).

## 4. The paired negative — the load-bearing quantity

```
Δλ_B = λ_B(corridor binding) - λ_B(copper plate) = 50 - 10 = 40
```

exactly the corridor bound's own dual `ν = 40` from §2. **This is the quantity a committed test
asserts**: removing the cap (`C → ∞`) must move zone B's price by precisely `c_B - c_A`, no more
and no less, and zone A's price must not move at all (`λ_A = 10` in both cases — zone A's own
marginal unit, the cheap generator, is interior and price-setting in both regimes, since
`p_A* ∈ {70, 80}`, both `< 200`). A sabotage that flips the corridor's bound sign, or that lets
the exchange column enter a balance row with the wrong sign, would either fail to reproduce `40`
here or would fail to collapse to equal prices in §3 — either failure is visible from this one
pair of solves.

## 5. Nodal reference with the corridor's real branch rated `C = 20` (for S5)

Same `m6_ac2_nodal.py`, `br23.rating_mva = 20.0`, run twice with **different** reactances
(`x12=0.1,x23=0.1` and `x12=0.05,x23=0.4`) to make the network's radial-topology-determinism
explicit rather than assumed — a tree has exactly one path between any two buses, so DC-flow on
each branch is fixed by KCL alone (net injection on one side of the cut), independent of branch
impedances:

```
--- corridor rated C=20 (matches zonal-binding case) (x12=0.1, x23=0.1) ---
status: Optimal
  gen genA @ bus1: p=70.000000 MW  bound_dual=0.000000
  gen genB @ bus3: p=10.000000 MW  bound_dual=0.000000
  bus bus1: lmp=10.000000  energy=10.000000  congestion=0.000000
  bus bus2: lmp=10.000000  energy=10.000000  congestion=0.000000
  bus bus3: lmp=50.000000  energy=10.000000  congestion=40.000000

--- corridor rated C=20, DIFFERENT reactances (x12=0.05,x23=0.4) ---
status: Optimal
  gen genA @ bus1: p=70.000000 MW  bound_dual=0.000000
  gen genB @ bus3: p=10.000000 MW  bound_dual=0.000000
  bus bus1: lmp=10.000000  energy=10.000000  congestion=0.000000
  bus bus2: lmp=10.000000  energy=10.000000  congestion=0.000000
  bus bus3: lmp=50.000000  energy=10.000000  congestion=40.000000

=== cross-check ===
r1 vs r2 gen dispatch match: True
r1 vs r2 LMPs match: True
```

Bit-identical dispatch and LMPs between the two reactance choices, confirming the topology
argument. These are the numbers **S5 reuses**: `genA=70 MW`, `genB=10 MW`,
`LMP(bus1)=LMP(bus2)=10`, `LMP(bus3)=50` (energy `10` everywhere + congestion `40` only at
bus3, `lmp_decomposition`'s own split, `src/mambo_power/opf/dc_opf.py:522-532`). They equal the
zonal-LP numbers from §2 exactly, dispatch-for-dispatch and price-for-price — expected here
specifically **because** zone A's only internal branch (`br12`) is unrated and zone B is a single
bus, so this particular fixture has zero "zonal relaxation gap" by construction (AC-2 is testing
the zonal LP's own correctness, not the zonal-vs-nodal welfare gap AC-4/AC-5 own).

## 6. Optional bid-load variant (hand-solvable, included)

Zone B's fixed load replaced by a flat (constant-marginal-value) bid: value `45 $/MWh` for any
quantity up to `Q_max = 30 MW` (a single-segment `PiecewiseBid`, breakpoints `(0,0)` and
`(30, 1350)`); same corridor cap `C = 20`, same generators.

**Reasoning.** Since `c_B = 50 > V_B = 45`, the local expensive generator is never worth running
— every MW it produces costs 50 but the demand it could serve is worth at most 45, a losing
trade — so `p_B* = 0` regardless of the corridor. With `p_B* = 0`, zone B's balance becomes
`f_AB = p_d_B`; cheap corridor power is worth serving up to `min(C, Q_max) = min(20, 30) = 20`,
so `f_AB* = p_d_B* = 20` (still corridor-capped, not bid-capped) and `p_A* = L_A + f_AB* = 70`
(unchanged from §2, since `p_A` only depends on the export volume, not on what's on the other
side of it). Objective `= c_A·70 + c_B·0 - V_B·20 = 700 - 900 = -200` (negative: welfare surplus
now nets in, unlike the fixed-load objective which was pure cost).

`p_d_B*` is interior (`20 < 30`), so its own stationarity sets the price:
`λ_B = V_B = 45` (the bid's flat value, not `c_B`). `p_B* = 0` is at its lower bound with reduced
cost `c_B - λ_B = 50 - 45 = 5 >= 0`. Corridor dual `ν = λ_B - λ_A = 45 - 10 = 35`.

### Independent cross-check, both ways

`m6_ac2_bidload.py` — hand-built scipy LP (variables `[p_A, p_B, f_AB, p_d_B]`):

```
p_A=70.000000 p_B=0.000000 f_AB=20.000000 p_d_B=20.000000
objective: -200.0
eqlin.marginals (zone A, zone B): [10. 45.]
f_AB bound marginals (lower, upper): 0.0 -35.0
p_B lower-bound marginal (reduced cost): 5.0
```

and the same network built as a real `Network`/`Scenario` with a `PiecewiseBid` load, solved by
this repo's own `market.solve_nodal`:

```
status: Optimal
  gen genA: p=70.000000  bound_dual=0.000000
  gen genB: p=0.000000  bound_dual=5.000000
  load loadA: p=50.000000  bound_dual=0.000000
  load loadB_bid: p=20.000000  bound_dual=0.000000
  bus bus1: lmp=10.000000
  bus bus2: lmp=10.000000
  bus bus3: lmp=45.000000
```

All three (hand KKT, scipy, `solve_nodal`) agree exactly: `p_A=70, p_B=0, f_AB=p_d_B=20,
λ_A=10, λ_B=45`, generator-B reduced cost `5`. Not required by AC-2 (the fixed-load case is
mandatory) but demonstrates the same fixture's corridor-binding structure survives an elastic
zone-B demand, and gives S3 a second, harder case for free if wanted.

## 7. Summary table (closed forms, for direct test transcription)

| quantity | fixed-load, corridor binding | fixed-load, copper plate | bid-load, corridor binding |
|---|---|---|---|
| `p_A*` | 70 | 80 | 70 |
| `p_B*` | 10 | 0 | 0 |
| `f_AB*` | 20 (= C) | 30 | 20 (= C) |
| `p_d_B*` (bid case only) | — | — | 20 |
| `λ_A` | 10 | 10 | 10 |
| `λ_B` | 50 | 10 | 45 |
| corridor dual `ν` | 40 | 0 (inactive) | 35 |
| objective | 1200 | 800 | -200 |

Every cell was produced by at least two independent computations (hand KKT + scipy for the
zonal-LP columns; hand-topology + `solve_nodal` for the nodal-reference columns in §5) and they
agree to the printed precision (6 decimals in every script's output; the underlying numbers are
exact rationals so scipy's `highs` backend lands on them bit-for-bit at this scale).
