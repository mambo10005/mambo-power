"""Island repair: deactivate every in-service bus the slack cannot reach (W4, design item 4).

Policy (user decision D1, 2026-08-21: "importer repairs, model stays strict"): the
:class:`~mambo_power.model.Network` invariant ``DISCONNECTED_BUS`` is unchanged — a network
built directly with an island is rejected. Importers call :func:`repair_islands_entities`
on the raw entity lists *before* constructing the network, so the file loads, the island is
switched off, and the caller receives one ``ISLAND_DEACTIVATED``
:class:`~mambo_power.model.ImportWarning` per island naming the buses and elements.

Algorithm: breadth-first search from every in-service slack bus over in-service branches
whose two endpoints are in service. Every in-service bus not reached is an island bus; it is
deactivated together with every in-service branch, generator, load, shunt and storage unit
attached to it. Islands are reported one warning each (connected components of the
unreached set), in bus order; elements that were already out of service are left alone and
not listed. With no in-service slack at all nothing is reachable and nothing is changed —
that is ``NO_SLACK``'s job.

Oracles: pandapower ``check_connectivity`` (BFS from the reference buses; unreached buses
get ``BUS_TYPE = NONE`` and NaN results), MATPOWER ``ext2int`` (isolated buses removed before
the solve). Per-island slacks are out of scope: a network with two slacks is left intact by
the repair and then rejected by the model's ``MULTIPLE_SLACK`` check (spec Not Doing:
distributed slack).
"""

from __future__ import annotations

from collections import deque
from collections.abc import Sequence
from typing import TypeVar

from mambo_power.model.entities import Branch, Bus, Generator, Load, Shunt, Storage
from mambo_power.model.network import Network
from mambo_power.model.warnings import ImportWarning

_AtBus = TypeVar("_AtBus", Generator, Load, Shunt, Storage)

RepairedEntities = tuple[
    list[Bus],
    list[Branch],
    list[Generator],
    list[Load],
    list[Shunt],
    list[Storage],
    list[ImportWarning],
]
"""What :func:`repair_islands_entities` returns: the six entity lists, then the warnings."""


def repair_islands_entities(
    buses: Sequence[Bus],
    branches: Sequence[Branch],
    generators: Sequence[Generator],
    loads: Sequence[Load],
    shunts: Sequence[Shunt],
    storage: Sequence[Storage],
) -> RepairedEntities:
    """Deactivate island buses and their elements on raw entity lists; inputs are not mutated.

    Returns new lists (copies only where an element changed) and one warning per island.
    Works before validation, so it accepts entity lists that :class:`Network` would reject
    with ``DISCONNECTED_BUS``.
    """
    live = {bus.id for bus in buses if bus.in_service}
    sources = [bus.id for bus in buses if bus.in_service and bus.type == "slack"]
    if not sources:
        return (
            list(buses),
            list(branches),
            list(generators),
            list(loads),
            list(shunts),
            list(storage),
            [],
        )

    adjacency: dict[str, list[str]] = {bus_id: [] for bus_id in live}
    for branch in branches:
        if branch.in_service and branch.from_bus in live and branch.to_bus in live:
            adjacency[branch.from_bus].append(branch.to_bus)
            adjacency[branch.to_bus].append(branch.from_bus)

    reached = _bfs(sources, adjacency)
    island_buses = {bus_id for bus_id in live if bus_id not in reached}
    if not island_buses:
        return (
            list(buses),
            list(branches),
            list(generators),
            list(loads),
            list(shunts),
            list(storage),
            [],
        )

    new_buses = [
        bus.model_copy(update={"in_service": False}) if bus.id in island_buses else bus
        for bus in buses
    ]
    new_branches = [
        br.model_copy(update={"in_service": False})
        if br.in_service and (br.from_bus in island_buses or br.to_bus in island_buses)
        else br
        for br in branches
    ]
    new_generators = _deactivate_at(generators, island_buses)
    new_loads = _deactivate_at(loads, island_buses)
    new_shunts = _deactivate_at(shunts, island_buses)
    new_storage = _deactivate_at(storage, island_buses)

    warnings: list[ImportWarning] = []
    for component in _components(island_buses, adjacency, buses):
        members = set(component)
        element_ids: list[str] = []
        element_ids.extend(
            br.id
            for br in branches
            if br.in_service and (br.from_bus in members or br.to_bus in members)
        )
        for elements in (generators, loads, shunts, storage):
            element_ids.extend(el.id for el in elements if el.in_service and el.bus in members)
        noun = "bus" if len(component) == 1 else "buses"
        message = (
            f"{noun} {', '.join(component)} cannot reach slack bus {', '.join(sources)} over "
            f"in-service branches; deactivated with attached elements "
            f"[{', '.join(element_ids)}]"
        )
        warnings.append(
            ImportWarning(
                code="ISLAND_DEACTIVATED",
                message=message,
                bus_ids=list(component),
                element_ids=element_ids,
            )
        )

    return new_buses, new_branches, new_generators, new_loads, new_shunts, new_storage, warnings


def repair_islands(net: Network) -> tuple[Network, list[ImportWarning]]:
    """Return a new, validated :class:`Network` with every island switched off, plus warnings.

    ``net`` is not modified. On an already-connected network the result is an equal copy and
    the warning list is empty.
    """
    buses, branches, generators, loads, shunts, storage, warnings = repair_islands_entities(
        net.buses, net.branches, net.generators, net.loads, net.shunts, net.storage
    )
    repaired = Network(
        schema_version=net.schema_version,
        base_mva=net.base_mva,
        buses=buses,
        branches=branches,
        generators=generators,
        loads=loads,
        shunts=shunts,
        storage=storage,
        zones=list(net.zones),
    )
    return repaired, warnings


def _bfs(sources: Sequence[str], adjacency: dict[str, list[str]]) -> set[str]:
    reached = set(sources)
    queue = deque(sources)
    while queue:
        current = queue.popleft()
        for neighbour in adjacency[current]:
            if neighbour not in reached:
                reached.add(neighbour)
                queue.append(neighbour)
    return reached


def _components(
    island_buses: set[str], adjacency: dict[str, list[str]], buses: Sequence[Bus]
) -> list[list[str]]:
    """Connected components of the island set, each in bus order, ordered by first bus."""
    order = {bus.id: index for index, bus in enumerate(buses)}
    assigned: set[str] = set()
    components: list[list[str]] = []
    for bus in buses:
        if bus.id not in island_buses or bus.id in assigned:
            continue
        component = _bfs([bus.id], adjacency) & island_buses
        assigned |= component
        components.append(sorted(component, key=order.__getitem__))
    return components


def _deactivate_at(elements: Sequence[_AtBus], island_buses: set[str]) -> list[_AtBus]:
    return [
        el.model_copy(update={"in_service": False})
        if el.in_service and el.bus in island_buses
        else el
        for el in elements
    ]
