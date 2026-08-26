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
transposition sabotage on this fixture actually fail.

**Siting.** :func:`storage_for_network` places the unit, by default, at the bus carrying the
largest aggregate load in ``net`` (summed over every load at that bus) -- a deterministic,
fixture-derived choice needing no per-fixture hand-picking, and one that puts the unit somewhere
its charge/discharge schedule has real locational content: the bus most likely to sit behind a
congested branch during its own peak hour (``tests/_periods.py``'s own two-archetype profile).

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
