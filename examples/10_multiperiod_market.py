"""Multiperiod clearing: a 24-hour horizon with ramp coupling, storage SoC and per-period LMPs.

What this shows:

* ``market.solve_multiperiod(scenario)`` on a 24-period ``Scenario`` built over case14: one
  ``Period`` per hour carrying a per-load ``load_p_mw`` override, a storage unit, and ramp
  limits on every generator. The whole horizon is **one** coupled LP -- the periods are not
  solved one at a time, which is the entire point: a ramp row ties hour ``t`` to ``t-1`` and the
  state-of-charge rows tie all 24 hours into a single energy budget.
* Storage arbitrage the clearing finds by itself: charge through the overnight trough, discharge
  into the afternoon peak, with the charge/discharge efficiencies applied in the SoC row and the
  cyclic end-of-horizon condition returning the unit to exactly its starting energy.
* Per-period LMPs, split into energy and congestion by the same ``opf.lmp_decomposition`` a
  single-period clearing uses, and the per-period settlement -- where storage is a **third
  participant**: it pays ``LMP * charge_mw`` and is paid ``LMP * discharge_mw``, and the
  identity does not close if a dispatched unit is left out.
* A ramp row binding, and its dual: negative when the ramp-*up* side binds, positive when the
  ramp-*down* side does.
* The degenerate case: a ``Scenario`` with ``periods=None`` clears one period and reproduces
  ``market.solve_nodal`` exactly -- the same dispatch and the same LMPs, not merely close.

Run from the repository root: ``uv run python examples/10_multiperiod_market.py``.
"""

from __future__ import annotations

import math

from mambo_power import market, pf
from mambo_power.io import matpower
from mambo_power.model import Period, Scenario, Storage

# --- 1. Build the 24-period scenario ----------------------------------------------------------
# case14 ships no branch ratings, no storage and no ramp data (every MATPOWER RATE_A and ramp
# column reads 0, the format's "unpopulated" convention), so all three are derived here from the
# fixture's own committed numbers -- the same test-time-transformation discipline the test suite
# uses, and the same 20%-headroom rating rule as `08_opf_and_n1.py`.
net = matpower.load("fixtures/matpower/case14.m")
base_flow_mw = {b.id: abs(b.p_from_mw) for b in pf.solve_dc(net).branches}
for br in net.branches:
    if br.id in base_flow_mw:
        br.rating_mva = max(1.2 * base_flow_mw[br.id], 1.0)

total_load_mw = sum(ld.p_mw for ld in net.loads)
load_by_bus: dict[str, float] = {}
for ld in net.loads:
    load_by_bus[ld.bus] = load_by_bus.get(ld.bus, 0.0) + ld.p_mw
busiest_bus = max(load_by_bus, key=lambda bus: load_by_bus[bus])
net.storage = [
    Storage(
        id="st-1",
        bus=busiest_bus,
        p_max_mw=0.15 * total_load_mw,  # 4-hour unit at 15% of system load
        energy_mwh=0.15 * total_load_mw * 4.0,
        soc_initial=0.5,  # half-charged: free to move either way from hour 0
        # Deliberately *unequal*: the two efficiencies enter the SoC row with different
        # coefficients (+eta_c against -1/eta_d), so with an equal pair transposing them is a
        # silent no-op and the asymmetry this example exists to show is invisible.  The pair
        # also has to leave arbitrage worth doing: this day's LMPs swing 33.31 -> 40.88 $/MWh,
        # so a round trip below 33.31/40.88 = 0.815 leaves the unit idle for all 24 hours --
        # which is why this is 0.9021 and not `tests/_storage.py`'s more pessimistic 0.8096.
        efficiency_charge=0.97,
        efficiency_discharge=0.93,
    )
]
for g in net.generators:
    # `None` means unconstrained; a limit must be strictly > 0 (0 would freeze the unit).
    g.ramp_up_mw = g.ramp_down_mw = 0.05 * g.p_max_mw

# A raised-cosine day: every load scaled by the same multiplier, 0.7x at 04:00 up to 1.2x at
# 16:00.  `Period.load_p_mw` is an id-keyed *override*, not a scale factor -- a load left out of
# the dict keeps its own `Load.p_mw` in that period.
PEAK, TROUGH, TROUGH_HOUR = 1.2, 0.7, 4


def multiplier(hour: int) -> float:
    swing = (1.0 - math.cos(2.0 * math.pi * (hour - TROUGH_HOUR) / 24.0)) / 2.0
    return TROUGH + (PEAK - TROUGH) * swing


periods = [
    Period(load_p_mw={ld.id: ld.p_mw * multiplier(h) for ld in net.loads}) for h in range(24)
]
result = market.solve_multiperiod(Scenario(network=net, periods=periods))
print(f"status: {result.status}  periods: {result.n_periods}", end="  ")
print(f"horizon cost: {result.objective_cost:.2f} $")

# --- 2. The horizon, hour by hour -------------------------------------------------------------
unit = net.storage[0]
print(
    f"\nstorage {unit.id} at {unit.bus}: {unit.p_max_mw:.2f} MW / {unit.energy_mwh:.2f} MWh",
    end=", ",
)
print(f"round trip {unit.efficiency_charge * unit.efficiency_discharge:.4f}")
print("  h   load MW    LMP@bus       energy  congestion   charge  discharge     SoC MWh")
for t, period in enumerate(result.periods):
    price = next(b for b in period.buses if b.id == unit.bus)
    store = period.storage[0]
    print(
        f" {t:2d}  {sum(ld.p_mw for ld in period.loads):8.2f}  {price.lmp:9.4f}"
        f"  {price.energy:9.4f}"
        f"  {price.congestion:10.4f}  {store.charge_mw:7.3f}  {store.discharge_mw:9.3f}"
        f"  {store.soc_mwh:10.3f}"
    )
print(f"cyclic end-of-horizon SoC: {result.periods[-1].storage[0].soc_mwh:.3f} MWh", end=" == ")
print(f"soc_initial * energy_mwh = {unit.soc_initial * unit.energy_mwh:.3f} MWh")
congested = [
    t for t, p in enumerate(result.periods) if any(abs(b.congestion) > 1e-9 for b in p.buses)
]
print(f"hours with a binding branch rating: {len(congested)} of 24 -- {congested}")

# --- 3. A binding ramp row and its dual -------------------------------------------------------
binding_ramps = [
    (t, g.id, g.ramp_dual)
    for t, period in enumerate(result.periods)
    for g in period.generators
    if abs(g.ramp_dual) > 1e-9
]
print(f"\nbinding ramp rows: {len(binding_ramps)}")
for t, gen_id, dual in binding_ramps:
    side = "ramp-up" if dual < 0 else "ramp-down"
    previous = next(g for g in result.periods[t - 1].generators if g.id == gen_id)
    now = next(g for g in result.periods[t].generators if g.id == gen_id)
    limit = next(g for g in net.generators if g.id == gen_id)
    print(
        f"  h{t:02d} {gen_id}: {previous.p_mw:8.3f} -> {now.p_mw:8.3f} MW"
        f"  (delta {now.p_mw - previous.p_mw:+7.3f}, limit +-{limit.ramp_up_mw:.3f})"
        f"  {side} dual {dual:.6f} $/MWh"
    )

# --- 4. Settlement, per period, with storage as the third participant -------------------------
# `congestion_rent` is the operator's merchandising surplus: (load payment + storage charge
# payment) - (generator receipts + storage discharge revenue).  It equals congestion rent
# proper, -sum_k(mu_k * flow_k), only where the network has no phase-shifting transformer and
# no bus shunt conductance -- case14 has neither, so it does here.
print("\nsettlement (per period, $/h):")
print("  h   load payment    receipts    st charge  st discharge      surplus")
for t in (TROUGH_HOUR, 16):
    p = result.periods[t]
    print(
        f" {t:2d}  {p.total_load_payment:12.3f}  {p.total_generator_receipts:10.3f}"
        f"  {p.total_storage_charge_payment:11.3f}  {p.total_storage_discharge_revenue:12.3f}"
        f"  {p.congestion_rent:11.3f}"
    )
# An hour with no binding rating has one price everywhere, so the surplus must be *exactly* zero
# -- and it is, only because storage is settled.  Leaving the two storage columns out of the sum
# (M4's nodal form of the identity, which had no storage to settle) reads a large number instead:
# the arbitrage profit the unit is making at the market operator's expense on paper.
uncongested = [p for t, p in enumerate(result.periods) if t not in congested]
worst = max(abs(p.congestion_rent) for p in uncongested)
unsettled = max(abs(p.total_load_payment - p.total_generator_receipts) for p in uncongested)
print(f"largest surplus over the {len(uncongested)} uncongested hours: {worst:.3e} $/h", end="  ")
print(f"(storage left unsettled: {unsettled:.3f} $/h)")
storage_profit = result.total_storage_discharge_revenue - result.total_storage_charge_payment
print(f"horizon: surplus {result.congestion_rent:.3f} $", end="  ")
print(f"storage net revenue {storage_profit:.3f} $ (its arbitrage profit)")
print("(the identity's other side, -sum_k(mu_k*flow_k), needs the flow duals, which this result")
print(" type does not carry; tests/unit/test_market_multiperiod.py computes it from a second,")
print(" array-level solve and proves the equality period by period)")

# --- 5. Degeneracy: one period is the nodal clearing, exactly ----------------------------------
plain = matpower.load("fixtures/matpower/case14.m")
nodal = market.solve_nodal(Scenario(network=plain))
single = market.solve_multiperiod(Scenario(network=plain))  # periods=None -> a one-period horizon
print(f"\nperiods=None -> n_periods {single.n_periods}, status {single.status}")
one = single.periods[0]
same_dispatch = [a.p_mw == b.p_mw for a, b in zip(nodal.generators, one.generators, strict=True)]
same_lmp = [a.lmp == b.lmp for a, b in zip(nodal.buses, one.buses, strict=True)]
print(f"dispatch identical to market.solve_nodal: {all(same_dispatch)} ({len(same_dispatch)} gens)")
print(f"LMPs identical to market.solve_nodal:     {all(same_lmp)} ({len(same_lmp)} buses)")
print("(bit-exact `==`, not a tolerance: at T=1 the multiperiod builder issues the identical")
print(" calls, in the identical column and row order, that `dc_opf` itself does)")
