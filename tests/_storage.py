"""Storage-derivation test helper (M5 W7, AC-6 fixture half).

No fixture in this repo carries any :class:`~mambo_power.model.Storage` data at all
(``n_storage=0`` on all 5 OPF fixtures, record/m5-research.md §8.1) -- the same "the format
doesn't have the section" gap ``tests/_bids.py`` and ``tests/_rated.py`` each solved once already.
This module derives a single, synthetic storage unit **at test time**, sized and sited from a
fixture's own already-committed ``Load.p_mw`` data, committing no new fixture file.

**Sizing rule (pinned here, the same "genuine design choice, documented, not invented" pattern
``tests/_bids.py``'s ``VOLL_PER_MWH`` and ``tests/_rated.py``'s ``RATING_MARGIN`` both use).**
:data:`POWER_FRACTION_OF_TOTAL_LOAD` = 0.15 of the network's own total base-case load (summed
over every :class:`~mambo_power.model.Load`, in-service or not -- the same "network's own
committed figure" anchor ``tests/_bids.py`` uses) sets the unit's ``p_max_mw``;
:data:`DURATION_HOURS` = 4.0 (a 4-hour duration is the standard grid-scale Li-ion benchmark this
sizing follows, not an invented number) sets ``energy_mwh = p_max_mw * DURATION_HOURS``. On
case14 (total load 259.0 MW) this is a 38.85 MW / 155.4 MWh unit -- large enough, relative to the
single biggest load on the fixture, to move a rated branch's flow and to be worth arbitraging
across a 24-hour swing, without being sized so large it dominates the network's own generation
capacity.

**Efficiencies are deliberately asymmetric.** :data:`EFFICIENCY_CHARGE` = 0.92,
:data:`EFFICIENCY_DISCHARGE` = 0.88 (round-trip 0.8096, a realistic Li-ion figure) -- *not* equal.
S4's own sabotage sweep (record/wave-05-multiperiod.plan.md Assumption A10) found that swapping
``eta_charge``/``eta_discharge`` in the SoC row was a silent no-op on every one of its fixtures,
because every one of them had ``eta_c == eta_d``; using distinct values here is what lets a
transposition sabotage on this fixture actually fail. **Measured, not hoped for**: transposing
the two coefficients in the engine's own SoC row moves
``tests/parity/test_market_multiperiod_vs_pypsa.py``'s state-of-charge comparison by 5.088e-2 MWh
against its 1e-2 tolerance, and that module's own
``test_the_fixture_can_tell_which_efficiency_is_which`` keeps the margin asserted.

Two things about that proof belong here, because both have already misled a reader of this
module. First, **the transposition is invisible to every comparison except the SoC one**:
``eta_c * eta_d`` is symmetric, so a transposed engine converts grid-in to grid-out at the same
ratio and -- no SoC bound binding on that fixture -- chooses the same charge/discharge schedule.
A sabotage sweep reporting only dispatch and net-power residuals will see nothing and conclude,
wrongly, that the fixture is powerless here. Second, **transposing the two constants in this
module is not a sabotage at all**: :func:`storage_for_network`'s unit is handed to *both* engines
-- ``mambo_power``'s own ``Storage`` and the oracle's ``efficiency_store``/``efficiency_dispatch``
-- so swapping them relabels both sides of the comparison at once. That is a no-op by
construction, as it would be for any parity fixture however strong, and it says nothing about
this one. The sabotage that means something goes on the engine, not on this file.

**Siting.** :func:`storage_for_network` places the unit, by default, at the bus carrying the
largest aggregate load in ``net`` (summed over every load at that bus) -- a deterministic,
fixture-derived choice needing no per-fixture hand-picking, and the choice that carries this
fixture's *entire* locational content. ``tests/_periods.py`` applies one **system-wide** curve to
every load (its own module docstring records why the two-phase-shifted-archetype design it started
from was abandoned: measured on case14, any per-load divergence from the network's own base-case
load ratios makes the 24-period LP genuinely infeasible against ``tests/_rated.py``'s derived
ratings), so every load peaks in the same hour and the profile itself has no locational diversity
to contribute. Siting the unit at the largest-load bus is what supplies it: that bus is the one
most likely to sit behind a branch that congests at the system peak, so the unit sees a genuine
LMP spread to arbitrage even though every load moves in lockstep.

**``soc_initial`` = 0.5** (half-charged) is chosen so the cyclic end-of-horizon condition
(``soc[T-1] == soc_initial``) neither starts empty (which would forbid net discharge in period 0)
nor full (which would forbid net charge in period 0) -- the unit can genuinely arbitrage in either
direction from hour 0 without immediately hitting a bound of its own starting condition.
"""

from __future__ import annotations

from mambo_power.model import Network, Storage

POWER_FRACTION_OF_TOTAL_LOAD = 0.15
"""``p_max_mw = POWER_FRACTION_OF_TOTAL_LOAD * sum(Load.p_mw)`` (module docstring)."""
DURATION_HOURS = 4.0
"""``energy_mwh = p_max_mw * DURATION_HOURS`` -- the standard grid-scale Li-ion benchmark."""
SOC_INITIAL = 0.5
"""Fraction of ``energy_mwh`` at the start (and, by the cyclic row, the end) of the horizon."""
EFFICIENCY_CHARGE = 0.92
EFFICIENCY_DISCHARGE = 0.88
"""Deliberately asymmetric (module docstring) -- round-trip 0.8096."""


def _bus_with_largest_aggregate_load(net: Network) -> str:
    totals: dict[str, float] = {}
    for ld in net.loads:
        totals[ld.bus] = totals.get(ld.bus, 0.0) + ld.p_mw
    if not totals:
        raise ValueError("net has no loads -- nothing to site a derived storage unit against")
    return max(totals, key=lambda bus: totals[bus])


def storage_for_network(
    net: Network, bus_id: str | None = None, *, storage_id: str = "storage-derived-1"
) -> Storage:
    """A single :class:`~mambo_power.model.Storage` unit sized off ``net``'s own total committed
    load (module docstring). ``bus_id`` defaults to the bus with the largest aggregate load in
    ``net``; an explicit ``bus_id`` must resolve to a real bus.

    Raises ``ValueError`` if ``net`` has no loads (nothing to size against) or if an explicit
    ``bus_id`` does not resolve to a bus in ``net``.
    """
    total_load_mw = sum(ld.p_mw for ld in net.loads)
    if total_load_mw <= 0.0:
        raise ValueError("net's total load is <= 0 -- nothing to size a derived storage unit off")
    if bus_id is None:
        bus_id = _bus_with_largest_aggregate_load(net)
    elif bus_id not in {b.id for b in net.buses}:
        raise ValueError(f'bus_id="{bus_id}" is not a bus in net')

    p_max_mw = POWER_FRACTION_OF_TOTAL_LOAD * total_load_mw
    return Storage(
        id=storage_id,
        bus=bus_id,
        p_max_mw=p_max_mw,
        energy_mwh=p_max_mw * DURATION_HOURS,
        soc_initial=SOC_INITIAL,
        efficiency_charge=EFFICIENCY_CHARGE,
        efficiency_discharge=EFFICIENCY_DISCHARGE,
    )


def with_storage(net: Network, bus_id: str | None = None) -> Network:
    """A copy of ``net`` with :func:`storage_for_network`'s derived unit appended to
    ``net.storage``. Mirrors ``tests/_rated.py``'s ``rated_network`` / ``tests/_bids.py``'s
    ``with_bids`` -- does not mutate ``net``, returns a fresh
    :class:`~mambo_power.model.Network` via ``model_copy(deep=True)``.
    """
    unit = storage_for_network(net, bus_id)
    out = net.model_copy(deep=True)
    out.storage.append(unit)
    return out
