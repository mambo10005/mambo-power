"""Unit commitment on the multiperiod market: when a cheap unit is worth switching on.

What this shows:

* ``market.solve_multiperiod(scenario, MarketMultiperiodOptions(unit_commitment=True))`` — the
  horizon clearing as a mixed-integer problem: per-unit on/off decisions with start-up costs,
  no-load costs paid only while on and minimum outputs that apply only while on (ADR-017).
* The LP cannot switch a unit off and never pays a start-up, so its cost is not a schedule
  anyone could run; the same scenario under commitment either starts the cheap unit and pays
  for it, or leaves it off — and which one depends on the start-up cost.
* ``MarketMultiperiodResult.commitment`` — each unit's schedule and events, and which units
  had anything to decide at all.
* Prices are the restricted LP's (the binaries fixed at the optimum): the LMP is the marginal
  energy cost given the committed fleet, and start-up costs are not recovered through it —
  ``commitment_cost`` is what an uplift would have to cover.
* Minimum up and down times (ADR-019): ``Generator.min_down_periods`` with
  ``initial_state_periods`` holds a unit that has just stopped off into the horizon, so the
  cheapest start is the first one the rules allow, not period 0.
* Spinning reserve (ADR-023): ``Period.reserve_mw`` is capacity the committed fleet must hold
  unused; a requirement the running units cannot cover is what commits another, and the
  requirement row's dual is the reserve price.

Runs from any directory, with no repository clone: ``python 15_unit_commitment.py``.
"""

from __future__ import annotations

from mambo_power.market.multiperiod import MarketMultiperiodOptions, solve_multiperiod
from mambo_power.model import Bus, Generator, Load, Network, Period, PolynomialCost, Scenario


def unit(
    gen_id: str, p_mw: float, p_min: float, p_max: float, marginal: float, startup: float = 0.0
) -> Generator:
    return Generator(
        id=gen_id,
        bus="b1",
        p_mw=p_mw,
        q_mvar=0.0,
        p_min_mw=p_min,
        p_max_mw=p_max,
        q_min_mvar=0.0,
        q_max_mvar=0.0,
        v_set_pu=1.0,
        cost=PolynomialCost(coefficients=[marginal, 0.0], startup=startup),
    )


def scenario(baseload_startup: float, **baseload_fields: int | None) -> Scenario:
    # one bus; a dear peaker that is on, and a cheap baseload unit with a 40 MW minimum that is
    # off before the horizon and costs `baseload_startup` to start
    baseload = unit("baseload", 0.0, 40.0, 200.0, 10.0, startup=baseload_startup)
    net = Network(
        base_mva=100.0,
        buses=[Bus(id="b1", base_kv=138.0, type="slack")],
        generators=[
            unit("peaker", 10.0, 0.0, 100.0, 50.0),
            baseload.model_copy(update=baseload_fields),
        ],
        loads=[Load(id="ld", bus="b1", p_mw=50.0, q_mvar=0.0)],
    )
    return Scenario(network=net, periods=[Period(load_p_mw={"ld": p}) for p in (50.0, 80.0, 50.0)])


# --- 1. The LP: no decision to make, no start-up to pay ------------------------------------
plain = solve_multiperiod(scenario(5000.0))
print(f"LP clearing: {plain.objective_cost:.0f} $ over the horizon; baseload runs every period")
print("(a unit with a 40 MW minimum cannot be switched off in an LP, and starting it is free)")

# --- 2. Commitment: start the cheap unit if, and only if, the start-up pays for itself -------
for startup in (5000.0, 8000.0):
    result = solve_multiperiod(scenario(startup), MarketMultiperiodOptions(unit_commitment=True))
    print(
        f"\nstart-up {startup:.0f} $: {result.status}, horizon cost {result.objective_cost:.0f} $"
    )
    print(f"  energy {result.objective_cost - result.commitment_cost:.0f} $", end="")
    print(f" + events {result.commitment_cost:.0f} $ + no-load {result.no_load_cost:.0f} $")
    for c in result.commitment:
        kind = "committable" if c.committable else "always on "
        on = "".join("1" if x else "0" for x in c.on)
        started = "".join("1" if x else "0" for x in c.started)
        print(
            f"  {c.id:9s} {kind}  on={on}  started={started}  start-up paid {c.startup_cost:.0f} $"
        )
    lmps = [p.buses[0].lmp for p in result.periods]
    print("  LMP by period:", [f"{x:.0f}" for x in lmps], "$/MWh (restricted LP, binaries fixed)")

# --- 3. What the prices do not pay for ---------------------------------------------------------
result = solve_multiperiod(scenario(5000.0), MarketMultiperiodOptions(unit_commitment=True))
baseload = next(c for c in result.commitment if c.id == "baseload")
energy_receipts = sum(
    g.p_mw * p.buses[0].lmp for p in result.periods for g in p.generators if g.id == "baseload"
)
print(f"\nbaseload at the LMP earns {energy_receipts:.0f} $ for {10 * 180:.0f} $ of energy cost,")
print(
    f"and paid {baseload.startup_cost:.0f} $ to start: the gap is the uplift a market would settle"
)

# --- 3. Minimum down time: the unit stopped just before the horizon, and must stay off -------
# a $1000 start-up pays for itself at once, so without the rule baseload starts in period 0;
# with a 3-period minimum down time and 1 period already off, it is held off for two more
free = solve_multiperiod(scenario(1000.0), MarketMultiperiodOptions(unit_commitment=True))
held = solve_multiperiod(
    scenario(1000.0, min_down_periods=3, initial_state_periods=1),
    MarketMultiperiodOptions(unit_commitment=True),
)
for label, result in (("no minimum", free), ("min down 3, off for 1", held)):
    c = next(c for c in result.commitment if c.id == "baseload")
    on = "".join("1" if x else "0" for x in c.on)
    print(f"\n{label:22s} baseload on={on}  horizon cost {result.objective_cost:.0f} $")
print("(the start moves to the first period the rule allows; the peak is met by the peaker)")

# --- 4. Spinning reserve: a requirement the running fleet cannot hold commits a unit --------
# the peaker may hold at most 20 MW of reserve; 60 MW of reserve in every period needs baseload
reserved = scenario(5000.0)
for gen in reserved.network.generators:
    if gen.id == "peaker":
        gen.reserve_max_mw = 20.0
for period in reserved.periods or []:
    period.reserve_mw = 60.0
for label, sc in (("energy only", scenario(8000.0)), ("60 MW reserve", reserved)):
    if label == "60 MW reserve":
        for gen in sc.network.generators:
            if gen.id == "baseload":
                gen.cost = PolynomialCost(coefficients=[10.0, 0.0], startup=8000.0)
    result = solve_multiperiod(sc, MarketMultiperiodOptions(unit_commitment=True))
    c = next(c for c in result.commitment if c.id == "baseload")
    on = "".join("1" if x else "0" for x in c.on)
    prices = [f"{p.reserve_price:.0f}" for p in result.periods]
    print(f"\n{label:14s} baseload on={on}  horizon cost {result.objective_cost:.0f} $", end="")
    print(f"  reserve price by period {prices} $/MW")
print("(at $8000 the start did not pay for itself on energy; the reserve requirement makes it)")
