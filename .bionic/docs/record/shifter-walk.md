# Shifter fix — independent walk

## Head and provenance

Walked commit `6a7617f73a4af3c202fae7330e639c30b1c8ae25`. Obtained by `git archive
6a7617f | tar -x` into an isolated scratch directory (no worktree, no shared venv with
any other running work). Confirmed the isolation before touching anything else:

```
$ uv run --project <scratchdir> python -c "import mambo_power; print(mambo_power.__file__)"
...
C:\Users\mambo\AppData\Local\Temp\claude\...\shifter-walk-6a7617f\src\mambo_power\__init__.py
```

The path resolves inside the scratch copy, not the original working tree or any other
checkout — every result below came from code at this exact commit and nowhere else.

## What I read

Cold, before writing any code: `docs/manual/power-flow.md` (DC formulation, the
`P_shift` / `P_f,shift` identity), `docs/manual/opf.md` (flow-limit row formulation,
`const_k`'s phase-shift term), `docs/manual/numerics.md` (the `bbus`/`p_shift`/`ptdf`
table), `docs/manual/market.md` (nodal clearing, `Scenario`, settlement), and the new
"Fixed" entry at the top of `docs/changelog.md`, which names the defect: `opf.dc_opf`'s
flow-limit row constant, `opf.solve_dc_opf`'s derived branch flows, and
`market.solve_nodal`/`solve_agents`'s derived branch flows all omitted the phase
shifter's own bus-injection term from their PTDF product — right for every existing
fixture (all have `shift_deg == 0`), wrong the moment a network declares a real one, and
capable of reporting a generously-rated shifter loop as falsely `Infeasible`.
`docs/manual/formats.md` mentions `shift_deg` only as an importer column mapping, no
solver-behavior claims to check there. I also opened `docs/manual/agents.md` for
`solve_agents`'s calling convention, since it isn't covered by `market.md` and the task
asked me to exercise it; and dropped into `src/mambo_power/numerics/bbus.py` once, for
the reason noted under Surprises below.

## What I ran

**Network A** — my own 4-bus ring, built from the model manual's field tables, not the
fix's own fixture: `bus-1` (slack) – `bus-2` – `bus-3` – `bus-4` – `bus-1`, asymmetric
reactances (0.10 / 0.15 / 0.10 / 0.20 pu), a phase shifter on `br-34` (`shift_deg=15`,
not on an edge of any ring symmetry — the other three branches are all plain lines with
distinct reactances), a rated branch `br-23` (40 MVA), loads at `bus-3` (40 MW) and
`bus-4` (20 MW), two generators of different cost at `bus-1` and `bus-2`.

`opf.solve_dc_opf(net)`, then a deep copy with each generator's `p_mw` overwritten from
that dispatch, then `pf.solve_dc` on the copy, flows compared branch-by-branch:

```
opf status: Optimal
--- flow comparison: opf.solve_dc_opf vs pf.solve_dc (on dispatched net) ---
br-12: opf=-18.508980  pf=-18.508980  diff=3.55e-15
br-23: opf=-18.508980  pf=-18.508980  diff=0.00e+00
br-34: opf=-58.508980  pf=-58.508980  diff=2.84e-14
br-41: opf=-78.508980  pf=-78.508980  diff=1.42e-14
max abs diff: 2.842170943040401e-14
```

KCL from the OPF result alone (generator dispatch off `opf_result.generators`, load off
the untouched input `Network`, flows off `opf_result.branches`, `p_to_mw` reconstructed
as `-p_from_mw` since `OpfBranchFlowResult` carries only the from-side value):

```
bus-1 (slack): gen-load=60.000000  outflow=60.000000  match=True
bus-2 (non-slack): gen-load=0.000000  outflow=0.000000  match=True
bus-3 (non-slack): gen-load=-40.000000  outflow=-40.000000  match=True
bus-4 (non-slack): gen-load=-20.000000  outflow=-20.000000  match=True
ALL KCL CHECKS PASS: True
```

`market.solve_nodal(Scenario(network=net))` on the same network, flows against the same
`pf.solve_dc` baseline:

```
market status: Optimal
br-12: market=-18.508980  pf=-18.508980  diff=3.55e-15
br-23: market=-18.508980  pf=-18.508980  diff=0.00e+00
br-34: market=-58.508980  pf=-58.508980  diff=2.84e-14
br-41: market=-78.508980  pf=-78.508980  diff=1.42e-14
max abs diff market vs pf: 2.842170943040401e-14
market dispatch == opf dispatch? True
```

**Network B** — a second, independent 5-bus network for the "shifter far from slack"
case: `bus-1` (slack) – `bus-2`, then a loop `bus-2` – `bus-3` – `bus-4` – `bus-5` –
`bus-2`. The shifter sits on `br-34` (`shift_deg=-20`); neither `bus-3` nor `bus-4` is
the slack or adjacent to it (only `bus-2` touches `bus-1` directly), so `bus-3` is two
hops and `bus-4` three. Loads on `bus-3`/`bus-4`/`bus-5`, generators at `bus-1` and
`bus-5`.

```
--- Network B: opf vs pf flows (shifter on br-34, 2-3 hops from slack) ---
br-12: opf=50.000000  pf=50.000000  diff=3.55e-14
br-23: opf=91.094308  pf=91.094308  diff=1.42e-14
br-34: opf=81.094308  pf=81.094308  diff=4.26e-14
br-45: opf=56.094308  pf=56.094308  diff=0.00e+00
br-25: opf=-41.094308  pf=-41.094308  diff=0.00e+00
max abs diff: 4.263256414560601e-14

--- Network B: market.solve_nodal vs pf flows ---
(same five branches, same diffs, status market: Optimal)
```

The fix holds unchanged at two and three hops from the slack, not just adjacent to it.

**`market.solve_agents`** on Network A, `gen-1` a linear-cost markup strategist
(`step=0.5`), `gen-2` a price-taker, `offer_tol=1.5`:

```
status: Optimal
termination_reason: converged converged: True
id='gen-1' bus='bus-1' p_mw=60.0 bound_dual=0.0
id='gen-2' bus='bus-2' p_mw=0.0 bound_dual=0.0
...
--- solve_agents branch flows vs pf.solve_dc (dispatched net) ---
br-12: agents=-18.508980  pf=-18.508980  diff=3.55e-15
br-23: agents=-18.508980  pf=-18.508980  diff=0.00e+00
br-34: agents=-58.508980  pf=-58.508980  diff=2.84e-14
br-41: agents=-78.508980  pf=-78.508980  diff=1.42e-14
max abs diff: 2.842170943040401e-14
```

The fixed-point loop's own reported flows agree with `pf.solve_dc` to floating-point
precision too, same as the direct one-shot solvers.

**Deliberately reconstructing the old bug**, per the task's suggestion of a tight
rating that only binds under the wrong formula. Using Network A's own topology, I
computed what the pre-fix code would have produced — `ptdf(arr) @ injection_mw` with no
phase-shift correction at all — against the fixed code's own `numerics.flow_from_ptdf`
(the exact helper the changelog names as now shared by `opf.solve_dc_opf` and
`market`'s clearing), swept across every generation split the balance and generator
bounds allow (`gen-1` from 0 to 60 MW, `gen-2` making up the rest):

```
naive |flow| on br-23 over g1 in [0,60]: min=29.091 max=40.000
correct |flow| on br-23 over g1 in [0,60]: min=7.600 max=18.509
```

Across the *entire* feasible dispatch range, the pre-fix formula's flow estimate on
`br-23` never drops below 29.09 MW, while the true flow never exceeds 18.51 MW — so any
rating strictly between those two numbers is a case where the old code was
mathematically guaranteed to reject every feasible dispatch, regardless of what HiGHS
tried. I tightened `br-23` to 25 MVA (comfortably inside that gap) and re-ran the fixed
code:

```
status: Optimal
message: None
id='gen-1' bus='bus-1' p_mw=60.0 bound_dual=0.0
id='br-23' from_bus='bus-2' to_bus='bus-3' p_from_mw=-18.508979599845333 flow_limit_dual=-0.0

br-23 flow = -18.509 MW, rating = 25 MVA, within rating: True
```

`Optimal`, not the false `Infeasible` the changelog says the pre-fix code could produce
on exactly this shape of network.

**Immutability and silence**, across all four solve entry points, each on a fresh copy
of Network A, stdout/stderr captured around the call:

```
pf.solve_dc: unchanged=True  stdout=''  stderr=''
opf.solve_dc_opf: unchanged=True  stdout=''  stderr=''
market.solve_nodal: unchanged=True  stdout=''  stderr=''
market.solve_agents: unchanged=True  stdout=''  stderr=''
```

The input `Network` object came back byte-identical (`model_dump_json()` equality)
after every solve, and nothing was written to stdout or stderr by any of them.

## Surprises

**Doc claim:** `docs/manual/numerics.md`'s DC-susceptance table lists `bbus.pf_shift(arr)`
as a callable — attribute access on the `bbus` function, returning the per-branch
phase-shifter flow injection.
**Observed:** `mambo_power.numerics.bbus` is bound to the `bbus(arr) -> Bbus matrix`
function itself (the package `__init__` does `from .bbus import bbus, bf,
flow_from_ptdf, p_shift`, which shadows the submodule name at the package level), so
`bbus.pf_shift(arr)` raises `AttributeError: 'function' object has no attribute
'pf_shift'`. The underlying `pf_shift` function does exist, in
`src/mambo_power/numerics/bbus.py`, but it is not re-exported from
`mambo_power.numerics` under any name — a caller who wants it has no path to it through
the public surface the manual describes. This is a real, reproducible gap between the
documented call and what the package exposes; it did not block me since
`flow_from_ptdf` (which internally calls `pf_shift`) is exported and is the actually
load-bearing function for the fix, but the table entry as written cannot be run.

**Doc claim vs observed, confirmed correct:** the changelog's claimed identity — `flow =
ptdf @ (injection_mw - p_shift·base_mva) + pf_shift·base_mva`, matching `pf.solve_dc`
exactly — held to floating-point precision (differences at or below 4e-14 MW, i.e.
solver rounding, not formula error) in every comparison I ran: `opf.solve_dc_opf` vs
`pf.solve_dc`, `market.solve_nodal` vs `pf.solve_dc`, and `market.solve_agents` vs
`pf.solve_dc`, on two independently-built networks with shifters at different distances
from the slack.

**Doc claim, confirmed by direct reconstruction:** the changelog's assertion that a
generously-rated shifter loop "could come back Infeasible with no flows at all" under
the old formula was reproducible by hand from the numbers alone — the pre-fix formula's
flow estimate on a tightened branch stayed above the true flow's own maximum across
every dispatch the network could reach — and the fixed code does not exhibit it: same
network, same tight rating, `Optimal`.

## Friction

`solve_agents`'s calling convention (the `strategies=` dict keyed by generator id, the
`MarketAgentsOptions` fields, the `offer_tol >= 3*step` rule) lives in
`docs/manual/agents.md`, which wasn't in the initial reading list — `market.md` doesn't
mention `solve_agents` at all. Reading `agents.md`'s "Using it" section directly was
enough; I didn't need source for that part. The one time I did drop into source
(`src/mambo_power/numerics/bbus.py`) was to chase the `bbus.pf_shift` discrepancy above,
since the documented call itself doesn't work.

Minor naming snag on my own part, not the package's: `OpfBranchFlowResult` (what
`opf.solve_dc_opf` and `market.solve_nodal` return per branch) carries only
`p_from_mw`, not `p_to_mw` — unlike the plain power-flow `BranchResult`, which has both.
`results.md`'s `BranchResult` table doesn't flag this difference, so my first KCL-check
draft assumed the field existed and raised `AttributeError`. Reconstructing
`p_to_mw = -p_from_mw` (valid for a lossless DC solve, which the manual does state
elsewhere) fixed it; a one-line note on `opf.md` or `results.md` that the OPF/market
branch-flow row is from-side-only would have saved the round trip.

## Verdict

The fix does what the changelog says: on two independently-built networks — one a
4-bus ring with the shifter answering to none of the ring's own symmetries, one a 5-bus
network where the shifter sits two and three hops from the slack — `opf.solve_dc_opf`,
`market.solve_nodal`, and `market.solve_agents` all report branch flows matching
`pf.solve_dc` to floating-point precision (worst case 4e-14 MW), KCL closes exactly at
every bus from the OPF result alone, and a rating chosen to sit strictly between the
old formula's flow estimate and the true flow's own maximum — a case constructed by
hand specifically to trigger the described false-infeasibility failure — clears
`Optimal` under the fixed code rather than the false `Infeasible` the old formula was
mathematically guaranteed to produce there. The one thing that didn't hold up under
use was a single documented call (`bbus.pf_shift(arr)`) that the public API doesn't
actually expose; it's a documentation gap, not a numerics gap, and nothing in the fix's
own behavior gave me a wrong answer at any point in this walk.
