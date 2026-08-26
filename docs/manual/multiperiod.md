# Multiperiod market

`market.solve_multiperiod` clears a whole horizon — up to and beyond a 24-hour day — as **one**
coupled LP/QP. Every wave before this one solved a single instant: each solve was independent and
correctness was checkable one snapshot at a time. Multiperiod clearing introduces *temporal
coupling*: a ramp row ties period `t` to `t-1`, a state-of-charge row ties the whole horizon into
one energy budget, and a cyclic row closes it. The periods cannot be solved one at a time and
then stacked; the coupling rows are what make the answer different from 24 independent clearings.

| Entry point | Returns |
| --- | --- |
| `market.solve_multiperiod(scenario, options=None)` | `MarketMultiperiodResult` |

Runnable script: [`10_multiperiod_market.py`](../examples/index.md#10-multiperiod-market).

It is built on the same [`opf.dc_opf`](opf.md) row families the [nodal
clearing](market.md) uses, through the array-level builder `opf.multiperiod_dc_opf` — not on a
second solver. `opf.lmp_decomposition` (M3) and `opf.gen_cost_coeffs` are called verbatim, per
period; `market.nodal.load_bid_coeffs` supplies the load bids, shared rather than copied.

## The horizon: `Scenario.periods` and `Period`

`Scenario` gained one field:

```text
Scenario(network: Network, periods: list[Period] | None = None)
Period(load_p_mw: dict[str, float])
```

`Period.load_p_mw` is an id-keyed **override** of each `Load.p_mw` for that period, not a scale
factor: a load id absent from the dict keeps its own `Load.p_mw` in that period, so a scenario
that varies two loads out of eleven names two. Every key must resolve to a real `Load` id in the
scenario's network — checked by `Scenario`'s own validator rather than by `Period`, since a bare
`Period` has no network to check against — and every value must be `>= 0`.

`periods=None` means single-period. That is not a special case in the solver; it is the
degenerate end of the same code path, and it reproduces `market.solve_nodal` bit-for-bit (see
[Degeneracy](#degeneracy-one-period-is-the-nodal-clearing), below).

**Only the fixed load varies by period.** Costs, bids, bounds, ratings and the network's topology
are horizon-invariant. Per-period offers and bids are deliberately out of scope this wave —
`Period` is shaped so a later wave can widen it additively rather than re-cut it. The PTDF matrix
is computed **once** and reused for every period, which assumes a static topology over the
horizon: no intra-horizon switching, no mid-day outage.

## One builder, not two

`opf/multiperiod.py` does not reimplement the nodal-balance row, the PTDF flow-limit rows or the
piecewise-linear epigraph and hypograph rows. It calls `dc_opf`'s own four internal helpers for
them, once per period, against that period's own column indices — the extraction that made this
literally true was landed and proved behaviour-preserving before any multiperiod row existed.
What is new is the three coupling families a single-period solve cannot have: ramp, SoC, and the
cyclic end-of-horizon row.

### Column layout — two tiers

The variable vector is *not* `T` self-contained per-period blocks. `dc_opf` passes its quadratic
cost Hessian once, over a **prefix** of the columns, before any free `cost_g` / `val_d` PWL
variable exists, so the free variables are hoisted into a second tier:

* **tier 1**, `T * (n_gen + n_demand + 3*n_storage)` columns, period-major, each period's block
  being `[gen | demand | charge | discharge | soc]`. The Hessian covers exactly this tier.
* **tier 2**, `T * (n_pwl + n_demand_pwl)` columns, period-major, each period's block being
  `[cost_g | val_d]`.

At `T == 1` with no storage this is column-for-column, row-for-row and call-for-call the model
`dc_opf` itself builds — which is what makes the degenerate case *exact* rather than merely
close.

### Row families and their order

Row indices are read back for duals, so the order is a contract of this module's own — it is
re-derived for `T` periods rather than inherited from `dc_opf`:

| Tier | Family | Row index |
| --- | --- | --- |
| 1 | nodal balance, one per period | `t` |
| 2 | PTDF flow limit, per branch per period | `T + t*n_branch + k` |
| 3 | SoC balance, per unit per period | `T*(1 + n_branch) + t*n_storage + s` |
| 4 | `charge + discharge <= p_max` | after tier 3, `t*n_storage + s` |
| 5 | cyclic `soc[T-1] == soc_initial` | after tier 4, `s` |
| 6 | ramp coupling, per ramped generator per adjacent pair | after tier 5, `(t-1)*n_ramped + j` |
| 7-8 | PWL epigraph / hypograph rows | last — an encoding detail, never part of the dual shape |

## Ramp coupling

`Generator` gained two optional fields:

```text
Generator(..., ramp_up_mw: float | None = None, ramp_down_mw: float | None = None)
```

Both are in MW per period, mirroring `Branch.rating_mva`'s established `float | None` pattern
rather than PyPSA's per-unit-of-`p_nom` convention — every other physical field on `Generator` is
already physical. `None` means **unconstrained**, and a generator with neither limit set gets no
ramp row at all, not a row with a large finite bound. A generator with only one of the two set
gets a genuinely unbounded side.

A ramp limit of exactly `0` is **rejected** with a `ValueError` before any solve. Zero would mean
"frozen for the whole horizon", which is never what a caller means; it is MATPOWER's unpopulated
ramp-column value, and no bundled fixture populates a ramp column at all. `None` is the honest
default for that data, not `0`.

One two-sided row is built per ramp-limited generator per adjacent period pair `t = 1..T-1`:

\[
-\text{ramp\_down\_mw}_g \;\le\; p_g[t] - p_g[t-1] \;\le\; \text{ramp\_up\_mw}_g .
\]

`GenPeriodDispatchResult.ramp_dual` reports that row's shadow price under HiGHS's own row-dual
sign convention — **negative** when the ramp-up side binds, **positive** when the ramp-down side
does, the same convention `flow_limit` duals already carry. Period 0 has no row reaching into it
and reports `0.0` rather than borrowing another period's, and so does any generator with no ramp
row at all.

!!! note "A negative energy price is legitimate here"
    `MultiperiodDuals.balance` may be negative in a ramp-constrained period, and correctly so:
    an extra MW of load in a period a ramp row binds out of can let a cheap unit start climbing
    earlier and displace an expensive one later. The builder's own hand-derived acceptance case
    constructs exactly that.

## Storage

`model.Storage` has been in the schema since M1 and solver-ignored ever since. This is the wave
that reads it. A network with no `Storage` builds no storage column and no SoC row, so the
formulation costs a storage-free caller nothing.

### Two columns, not one signed column

Each unit gets **two nonnegative** power columns per period, `charge` and `discharge`, each
bounded `[0, p_max_mw]`, plus an explicit `soc` column bounded `[0, energy_mwh]`. Not one signed
column: the charge and discharge efficiencies enter the SoC row with *different* coefficients
(`+eta_c` against `-1/eta_d`), an asymmetry a single signed column cannot express in one linear
row.

The two columns share one row per unit per period:

\[
\text{charge}[t] + \text{discharge}[t] \;\le\; \text{p\_max\_mw} ,
\]

so the unit's combined converter throughput is capped whichever way it is running.

### SoC balance, with efficiency

\[
\text{soc}[t] - \text{soc}[t-1] - \eta_c\,\text{charge}[t] +
\frac{\text{discharge}[t]}{\eta_d} = 0 ,
\]

one equality row per unit per period, anchored at `t = 0` to the unit's own initial energy
`soc_initial * energy_mwh`. `StorageDispatchResult.soc_mwh` is the state of charge at the **end**
of the period, and `soc_dual` is that row's shadow price — the marginal value of one more MWh
stored in that unit at the end of that period.

### Cyclic end of horizon

\[
\text{soc}[T-1] = \text{soc\_initial} \times \text{energy\_mwh} ,
\]

one equality row per unit, met exactly rather than to a tolerance. **This is not
configurable.** A free end state or a fixed target would be a third code path this wave
deliberately does not ship; a later wave that needs one adds it as an option, not as a second
solver. `MultiperiodDuals.cyclic` reports what the condition itself costs, separably from the SoC
dynamics above it.

### Simultaneous charge and discharge is bounded, not banned

Because charge and discharge are separate nonnegative columns, an LP solution in which both are
non-zero at once is *representable*. That is deliberate. Banning the overlap needs a binary,
which would change the solver class from LP/QP to MILP — and it is not merely an optimality
curiosity to be tidied away: there are networks on which forbidding the overlap makes the LP
**infeasible**, and the wave's own research constructed one. So the formulation caps the sum with
the shared power-limit row and leaves the overlap representable.

Whether it actually happens on real data is then a measurement, not an assumption:
`min(charge, discharge) ≈ 0` on every fixture this package ships is a committed invariant test,
paired with the constructed network where the same readback is genuinely non-zero — so the
near-zero reading is a measurement rather than an absence.

Storage is **costless in the objective**: `model.Storage` carries no cost field, so a unit's only
economic footprint is the round-trip loss it imposes on generation. Its profit is a settlement
outcome, not an objective term.

## Per-period LMPs

`opf.lmp_decomposition` is called once per period, unmodified, with that period's own balance and
flow-limit dual slice against the single PTDF matrix the builder already returned:

\[
\text{lmp}_b[t] = \underbrace{\lambda_\text{balance}[t]}_{\text{energy}} +
\underbrace{\sum_k \mu_k[t] \cdot \text{PTDF}[k, b]}_{\text{congestion}} .
\]

See [DC-OPF › Duals and locational marginal prices](opf.md#duals-and-locational-marginal-prices)
for the derivation. Nothing about it changes with a horizon in the picture; the duals it consumes
already account for the coupling rows.

Every figure on `MarketPeriodResult` is **that period's own**, never a horizon average. The `$/h`
quantities are that period's rate, and the horizon totals on `MarketMultiperiodResult` are their
plain sum — an energy-weighted total only because every period is one hour long. There is no
period-duration field this wave.

## Settlement

`MarketPeriodResult` reports five settlement figures, each computed directly from that period's
own prices and quantities:

* `total_load_payment` — `Σ_d LMP(bus_d) · p_d` over every load, bid or not.
* `total_generator_receipts` — `Σ_g LMP(bus_g) · p_g` over every generator.
* `total_storage_charge_payment` — `Σ_s LMP(bus_s) · charge_mw`, what storage pays for what it
  stores.
* `total_storage_discharge_revenue` — `Σ_s LMP(bus_s) · discharge_mw`, what the market pays
  storage for what it returns.
* `congestion_rent` — `(load payment + storage charge payment) - (generator receipts + storage
  discharge revenue)`.

### Storage is a third settlement participant

A storage unit both withdraws and injects at a bus, so it settles on both sides. The identity
does **not** close if a dispatched unit is left unsettled — it is then wrong by exactly the
unit's net revenue, which is the whole of its arbitrage profit. The 24-hour example makes this
visible directly: on an hour with no binding rating every LMP is equal, so the surplus must be
exactly zero — and it is. At hour 4 of that horizon the load pays 6308.385 \$/h, the generators
receive 7011.653 \$/h, and it is storage's 703.268 \$/h charge payment that closes the gap. Drop
the two storage columns and the same subtraction reads −703.268 instead of 0.

### The identity, in its general form

\[
\underbrace{\sum_d \text{LMP}_d\, p_d + \sum_s \text{LMP}_s\, c_s}_{\text{paid in}} \;-\;
\underbrace{\left(\sum_g \text{LMP}_g\, p_g + \sum_s \text{LMP}_s\, d_s\right)}_{\text{paid out}}
= -\sum_k \mu_k f_k + \sum_k \mu_k \,\text{pf\_shift}_k - \sum_n \text{LMP}_n\, g_{\text{shunt},n}
\]

holds **per period**, at the optimum. The two trailing terms are corrections for phase-shifting
transformers and for bus shunt conductance — both fixed, unsettled withdrawals from the network
itself rather than from a market participant. They are exactly zero on every MATPOWER fixture
this package ships except `case300`, whose `g_shunt` is non-zero (max 0.0014 pu, measured).

!!! warning "`congestion_rent` is the merchandising surplus"
    The field is the market operator's merchandising surplus, computed directly from prices and
    quantities. It equals congestion rent **proper** — exactly `-Σ_k(μ_k · f_k)` — only on a
    network with no bus shunt conductance and no phase-shifting transformer. Where either
    exists, the surplus also carries that unsettled withdrawal. The value is right either way; it
    is the *name* that is narrower than the number. [The nodal page](market.md#settlement)
    states the identity in the narrower form, which was correct for the fixtures M4 itself
    carried.

The identity is proved per period in `tests/unit/test_market_multiperiod.py` with the right-hand
side computed by a **separate** code path — a second, array-level solve and a recomputed PTDF —
so the assertion is a proof rather than a restatement of arithmetic already performed. Note that
`MarketMultiperiodResult` carries no branch rows, so its flow duals `μ_k` are not reachable from
the result object itself; a caller who wants to check the right-hand side has to go to
`opf.multiperiod_dc_opf` for them.

## Degeneracy: one period is the nodal clearing

A `Scenario` with `periods=None` clears `T = 1` from the network's own loads and reproduces
`market.solve_nodal` **exactly** — the same dispatch, the same duals, the same LMPs, asserted
with `==` and not with a tolerance. So does an explicit single-period scenario, and so does one
with elastic bids in play.

This is not a special case in the code. `solve_multiperiod` passes `period_load_mw=None` rather
than materialising a copy of the network's own loads, which makes the builder evaluate `dc_opf`'s
literal fixed-load and flow-constant expressions; combined with the column layout above, at `T=1`
the two builders issue identical calls in identical order, so the floating-point arithmetic is
the same arithmetic. This is the wave's own agreement test for the shared row-family core: it is
what fails if the extraction and the `T`-loop ever disagree.

`market.solve_nodal` ignores `Scenario.periods` entirely — it is a single-period entry point and
stays one.

## Errors

`market.NonConvexCostError` / `market.NonConcaveBidError` are raised before any solve, exactly as
for the nodal clearing. `solve_multiperiod` additionally raises `ValueError` up front for a ramp
limit of exactly zero. It never raises for an infeasible or unbounded LP/QP — that is reported
through `MarketMultiperiodResult.status` / `message`, mirroring `solve_nodal`'s and
`opf.solve_dc_opf`'s never-raise convention. The scenario is not modified.

An infeasible horizon is a real possibility that a single-period clearing does not have: a
profile whose per-bus injection pattern departs from the one a network's ratings were derived
against can be infeasible *over the horizon* even where every individual period would solve, and
the coupling rows are what make it so.

## Oracle & fixtures

No MATPOWER fixture carries multi-period data, storage, ramp limits or real branch ratings — the
format has no section for the first two and uses `0` as "unpopulated" for the others. All four
are derived **at test time** from data the fixtures already own, committing no new fixture files,
the same discipline `tests/_bids.py` and `tests/_rated.py` established for the nodal wave:

* `tests/_periods.py` — a 24-hour raised-cosine profile, `TROUGH_MULTIPLE = 0.7` at hour 4 up to
  `PEAK_MULTIPLE = 1.2` twelve hours later, applied as a **single system-wide curve**. An earlier
  design used two phase-shifted archetypes for locational diversity and had to be abandoned:
  measured on case14, any per-load divergence from the network's own base-case load ratios — even
  a 2-hour phase shift at unchanged amplitude — makes the 24-period LP genuinely infeasible,
  because several of the derived ratings sit at exactly their 20% headroom with no redispatch
  slack. A single curve keeps every branch's flow proportional to one multiplier, which is what
  keeps the whole horizon simultaneously feasible.
* `tests/_storage.py` — one unit sized at 15% of the network's own total base-case load with a
  4-hour duration (38.85 MW / 155.4 MWh on case14), `soc_initial = 0.5` so the cyclic condition
  forbids neither direction in period 0, and **deliberately asymmetric** efficiencies
  (`0.92` / `0.88`, round-trip `0.8096`) — an equal pair is exactly the shape under which
  transposing the two efficiencies in the SoC row is a silent no-op.
* `tests/_rated.py` — reused unchanged, at 20% headroom over the base-case flow, so congestion
  binds in some hours and not others.

The oracle is **PyPSA** multi-period `optimize` with `StorageUnit` and
`ramp_limit_up`/`ramp_limit_down`, on a 24-period rated case14 with the lossy unit and an
asymmetric generator ramp limit (10 MW/h up, 14.5 MW/h down) both genuinely engaged. Measured
worst-case residuals, with the pinned tolerances in brackets: objective `4.35e-13` relative
(`1e-9`), per-generator per-period dispatch `3.01e-4` MW (`1e-2`), net storage power `1.10e-4` MW
(`1e-2`), state of charge `1.25e-4` MWh (`1e-2`), per-bus per-period LMP `4.24e-5` \$/MWh
(`1e-3`).

!!! warning "Two disclosed limits of that oracle"
    **PyPSA's transformer ratings.** Rating both the 17 `Line` and the 3 `Transformer` components
    of case14 simultaneously makes PyPSA's constrained QP genuinely infeasible — reproduced from
    the bare single-period base case up through 3x uniform slack on every rating, so it is not a
    numerical near-miss. Root cause is `unverified` beyond "reproducibly fails". The parity test
    routes around it by rating only the 17 lines in the oracle while this package's engine rates
    all 20, and *asserts* that every branch which actually binds in our own dispatch across the
    horizon is one of those 17 — safe for that fixture's claim, not a general fix.

    **The parity fixture cannot tell the two efficiencies apart.** Storage's usage there is small
    (~0.5–1 MW) and nearly symmetric between charge and discharge, so transposing the two
    efficiency values is a near no-op (`3.14e-4` MW residual against `3.01e-4` baseline noise). A
    *magnitude* sabotage on the same field is caught clearly (2.16 MW, ~200x tolerance), so
    storage is not decorative in the oracle comparison — but efficiency *orientation* is proved
    elsewhere, on a hand-built asymmetric fixture at the builder level, not at the oracle tier.

## Using it

A 2-bus, 2-period arbitrage whose optimum is available in closed form. `gcheap` (10 \$/MWh,
40 MW) and `gexp` (50 \$/MWh) sit at the slack bus; a 20 MW load at `b2` becomes 100 MW in the
second period; a lossy 20 MW / 15 MWh unit sits beside it. Since
`c_H · η_c · η_d = 50 × 0.81 = 40.5 > 10 = c_L`, arbitrage pays, and the energy cap — not the
converter rating — is what binds:

```python
from mambo_power import market
from mambo_power.model import (
    Branch,
    Bus,
    Generator,
    Load,
    Network,
    Period,
    PolynomialCost,
    Scenario,
    Storage,
)


def gen(gid: str, p_max_mw: float, price: float) -> Generator:
    return Generator(
        id=gid,
        bus="b1",
        p_mw=0,
        q_mvar=0,
        p_min_mw=0,
        p_max_mw=p_max_mw,
        q_min_mvar=0,
        q_max_mvar=0,
        v_set_pu=1.0,
        cost=PolynomialCost(coefficients=[price, 0.0]),
    )


net = Network(
    base_mva=100.0,
    buses=[Bus(id="b1", base_kv=138.0, type="slack"), Bus(id="b2", base_kv=138.0, type="pq")],
    branches=[Branch(id="br12", from_bus="b1", to_bus="b2", r=0.0, x=0.1, b=0.0)],
    generators=[gen("gcheap", 40.0, 10.0), gen("gexp", 200.0, 50.0)],
    loads=[Load(id="ld2", bus="b2", p_mw=20.0, q_mvar=0.0)],
    storage=[
        Storage(
            id="st2",
            bus="b2",
            p_max_mw=20.0,
            energy_mwh=15.0,
            soc_initial=0.0,
            efficiency_charge=0.9,
            efficiency_discharge=0.9,
        )
    ],
)
scenario = Scenario(
    network=net,
    periods=[Period(load_p_mw={"ld2": 20.0}), Period(load_p_mw={"ld2": 100.0})],
)
result = market.solve_multiperiod(scenario)
print(result.status, result.n_periods, round(result.objective_cost, 6))
for p in result.periods:
    st = p.storage[0]
    print(
        f"t={p.period}  lmp {p.buses[1].lmp:5.1f}  charge {st.charge_mw:9.6f}"
        f"  discharge {st.discharge_mw:9.6f}  soc {st.soc_mwh:6.3f}"
        f"  surplus {p.congestion_rent:.6f}"
    )
print(
    round(result.total_storage_discharge_revenue - result.total_storage_charge_payment, 6),
    "$ storage net revenue over the horizon",
)
```

```text
Optimal 2 3091.666667
t=0  lmp  10.0  charge 16.666667  discharge  0.000000  soc 15.000  surplus -0.000000
t=1  lmp  50.0  charge  0.000000  discharge 13.500000  soc  0.000  surplus 0.000000
508.333333 $ storage net revenue over the horizon
```

Every figure is the closed form: `charge* = min(20, 15/0.9) = 50/3 = 16.6667` MW (the energy cap
binds, not the 20 MW rating), `discharge* = 0.81 × 50/3 = 13.5` MW, and the horizon profit
`50/3 × (40.5 − 10) = 508.3333` \$. The two prices are formed by the builder's own balance rows,
not assumed: `gcheap` is interior at `t=0` so `LMP = 10`, and at `t=1` it is at its cap with
`gexp` interior so `LMP = 50`. The branch is unrated, so both periods' surpluses are zero — and
they are zero **only** because storage is settled on both sides.

See [`10_multiperiod_market.py`](../examples/index.md#10-multiperiod-market) for the full 24-hour
version on case14: the storage schedule hour by hour, the cyclic SoC, two binding ramp rows with
duals of opposite sign, the per-period settlement, and the `periods=None` degeneracy.

## Jobs API

`market.multiperiod` is a registered [jobs](jobs.md) kind, and it is the reason `SolveRequest`
now accepts either a `network` **or** a `scenario`: a horizon needs `Scenario.periods`, which a
bare `Network` cannot supply.

```python
from mambo_power import jobs

outcome = jobs.run(jobs.SolveRequest(kind="market.multiperiod", scenario=scenario))
print(outcome.status, outcome.result.n_periods)
```

```text
ok 2
```

A `SolveRequest` carrying a `network` still works for this kind too — it is wrapped as a
single-period `Scenario`, and the clearing degenerates to the nodal one. A non-`"Optimal"` status
comes back as a structured failure (`INFEASIBLE_LP` or `UNBOUNDED_LP`) through the same
non-Optimal-status translation `opf.dc` and `market.nodal` use, not as a "successful" result
carrying a meaningless dispatch. See [Jobs API › Failures are
data](jobs.md#failures-are-data).
