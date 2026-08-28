"""Zone-promotion and corridor-derivation test helper (M6 W7, AC-2/AC-6 fixture half).

Mirrors ``tests/_rated.py``'s "documented, test-time transformation of an already-owned
fixture" pattern (wave-06 spec `## Domain model`), applied to a different MATPOWER column than
that helper touches: case30's ``AREA`` column (research §1: 3 groups, 11/10/9 buses) is a
free-form ``Bus.area`` label the importer never wires into a real :class:`~mambo_power.model.
Zone` entity (``io/matpower.py``'s bus loop builds ``net.zones``/``Bus.zone`` from the ``ZONE``
column only, always present, always a single group ``"1"`` on case30) -- so a market-layer test
needs a promotion step before it can exercise the zonal LP's actual zone-pair machinery on
case30's hand-inspectable, 30-bus/3-zone partition. No new fixture data is committed; both
functions below operate purely on fields the importer already writes.

**No-op-safe on an already-zoned network (case300).** :func:`promote_areas_to_zones` treats
"more than one real zone already present" (``len(net.zones) > 1``) as proof the network already
carries a genuine, importer-populated, validated multi-zone partition on ``Bus.zone``/
``net.zones`` (research §1: case300's ZONE column gives 4 real zones, 122/80/63/35) and returns
an unchanged deep copy -- re-deriving from ``Bus.area`` would be actively wrong there (case300's
own AREA column is a single group of 300, research §1's own table), silently collapsing a real
4-zone partition down to 1. The threshold is ``> 1``, not ``!= 1``: a single already-real zone
(``net.zones == [Zone(id=...)]``, true of every MATPOWER-imported fixture except case300) is
exactly the state every import starts in and is the state promotion is *for*.

**Corridors: an unrated crossing branch is a hard error, not a silent skip.** :func:`corridors`
takes a ``tests/_rated.py`` ``rated_network(...)`` output as input and raises if any crossing
branch has no ``rating_mva`` -- silently treating an unrated crossing branch as "no cap" would
make the derived transfer bound wrong in a way no downstream test could distinguish from
"correctly unbounded". Out-of-service branches are excluded from every cut-set: ``rated_network``
itself only derives ratings for the in-service, connected branches ``NetworkArrays`` keeps (its
own module docstring), so an out-of-service crossing branch could carry no rating at all through
no fault of the fixture -- and an out-of-service branch cannot carry power regardless of its
label, so excluding it is correct on its own terms too, not merely a workaround for the rating
gap.
"""

from __future__ import annotations

from mambo_power.model import Network, Zone


def promote_areas_to_zones(net: Network) -> Network:
    """A copy of ``net`` with case30-style free-form ``Bus.area`` labels turned into real
    :class:`~mambo_power.model.Zone` entities and each bus's ``.zone`` set to its own area's
    zone id.

    A no-op (module docstring) when ``net`` already carries more than one real zone -- returns
    an unchanged deep copy rather than re-deriving from ``Bus.area``. Does not mutate ``net``;
    returns a fresh :class:`Network` via ``model_copy(deep=True)``, mirroring ``tests/_rated.py``
    and ``tests/_storage.py``.

    Raises ``ValueError`` if any bus has no ``area`` label to promote (nothing to build a zone
    id from).
    """
    out = net.model_copy(deep=True)
    if len(out.zones) > 1:
        return out
    areas: list[str] = []
    for bus in out.buses:
        if bus.area is None:
            raise ValueError(f'bus "{bus.id}" has no area label -- cannot promote to a zone')
        areas.append(bus.area)
    out.zones = [Zone(id=zone_id) for zone_id in sorted(set(areas))]
    for bus, area in zip(out.buses, areas, strict=True):
        bus.zone = area
    return out


def zone_of_bus(net: Network) -> dict[str, str]:
    """``{bus id: zone id}`` for every bus in ``net`` that carries a zone (``Bus.zone is not
    None``); a bus with no zone assigned is simply absent from the mapping."""
    return {bus.id: bus.zone for bus in net.buses if bus.zone is not None}


def buses_by_zone(net: Network) -> dict[str, list[str]]:
    """``{zone id: [bus ids]}`` for every zone in ``net.zones``, in ``net.buses`` order. A zone
    with no buses assigned to it still gets an (empty) entry."""
    by_zone: dict[str, list[str]] = {zone.id: [] for zone in net.zones}
    for bus in net.buses:
        if bus.zone is not None:
            by_zone[bus.zone].append(bus.id)
    return by_zone


def corridors(net: Network) -> dict[tuple[str, str], float]:
    """``{(zone1, zone2): cap_mw}`` for every unordered zone pair with at least one crossing
    branch (a branch whose ``from_bus`` and ``to_bus`` sit in different zones), ``cap_mw`` being
    the sum of ``Branch.rating_mva`` over that pair's cut-set. Keys are sorted pairs
    (``zone1 < zone2``), so the same corridor is never reported under both orderings.

    ``net`` must already carry both a real zone assignment (:func:`promote_areas_to_zones`, or
    an already-real-zoned network like case300) and real branch ratings (``tests/_rated.py``'s
    ``rated_network``, unmodified) -- raises ``ValueError`` if any in-service crossing branch has
    no ``rating_mva`` (module docstring). Out-of-service branches are excluded from every
    cut-set. A bus with no zone assigned is treated as not crossing anything (module docstring's
    ``zone_of_bus`` convention).
    """
    zone_of = zone_of_bus(net)
    caps: dict[tuple[str, str], float] = {}
    for br in net.branches:
        if not br.in_service:
            continue
        z_from = zone_of.get(br.from_bus)
        z_to = zone_of.get(br.to_bus)
        if z_from is None or z_to is None or z_from == z_to:
            continue
        if br.rating_mva is None:
            raise ValueError(
                f'branch "{br.id}" crosses zones "{z_from}"/"{z_to}" but has no rating_mva -- '
                "run tests/_rated.py's rated_network first"
            )
        key = (z_from, z_to) if z_from < z_to else (z_to, z_from)
        caps[key] = caps.get(key, 0.0) + br.rating_mva
    return caps
