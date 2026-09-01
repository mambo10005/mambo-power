"""Unit test for ``tests._zones``: the zone-promotion and corridor-derivation test helper (M6
W7, AC-2/AC-6 fixture half).

Mirrors ``tests/unit/test_rated_helper.py``'s and ``tests/unit/test_storage_helper.py``'s own
discipline: proves the helper's guarantees directly (a genuine 3-zone partition promoted from
case30's own AREA column, a documented no-op on an already-zoned network, corridor caps that
equal the hand-summed ratings of their own cut-set, an empty reading on a genuinely single-zone
network paired against that positive) rather than merely exercising it as a side effect of
another test.
"""

from __future__ import annotations

import pytest

from mambo_power.io.matpower import load
from mambo_power.model import Network
from tests._fixtures import FIXTURES_DIR
from tests._rated import rated_network
from tests._zones import buses_by_zone, corridors, promote_areas_to_zones, zone_of_bus


def _case14() -> Network:
    return load(FIXTURES_DIR / "case14.m")


def _case30() -> Network:
    return load(FIXTURES_DIR / "case30.m")


def _case300() -> Network:
    return load(FIXTURES_DIR / "case300.m")


# -- promote_areas_to_zones ---------------------------------------------------------------------


def test_case30_promotes_to_exactly_three_zones_with_the_measured_bus_counts() -> None:
    net = promote_areas_to_zones(_case30())
    assert {z.id for z in net.zones} == {"1", "2", "3"}
    counts: dict[str, int] = {}
    for bus in net.buses:
        assert bus.zone is not None
        counts[bus.zone] = counts.get(bus.zone, 0) + 1
    assert counts == {"1": 11, "2": 10, "3": 9}  # research §1's own measured AREA-column split


def test_case30_every_bus_is_in_exactly_one_zone() -> None:
    net = promote_areas_to_zones(_case30())
    zone_ids = {z.id for z in net.zones}
    for bus in net.buses:
        assert bus.zone is not None
        assert bus.zone in zone_ids


def test_case30_promoted_zone_ids_match_bus_zone_refs_and_the_network_revalidates_clean() -> None:
    net = promote_areas_to_zones(_case30())
    assert {z.id for z in net.zones} == {bus.zone for bus in net.buses}
    # Network's own model_validator(mode="after") re-runs on this fresh construction from the
    # promoted data -- a raise here means the promotion left a dangling Bus.zone ref or similar.
    revalidated = Network(**net.model_dump())
    assert {z.id for z in revalidated.zones} == {"1", "2", "3"}


def test_case30_promotion_does_not_mutate_the_input_network() -> None:
    net = _case30()
    before_zones = [z.id for z in net.zones]
    before_bus_zones = [bus.zone for bus in net.buses]
    promote_areas_to_zones(net)
    assert [z.id for z in net.zones] == before_zones
    assert [bus.zone for bus in net.buses] == before_bus_zones


def test_case300_is_a_no_op_because_it_already_has_real_zones() -> None:
    """case300's AREA column is a single group of 300 (research §1) -- re-deriving from it would
    silently collapse the real, importer-populated 4-zone ZONE-column partition down to 1.
    ``promote_areas_to_zones`` detects "more than one real zone already present" and returns an
    unchanged deep copy instead (module docstring)."""
    net = _case300()
    out = promote_areas_to_zones(net)
    assert out is not net
    assert [z.id for z in out.zones] == [z.id for z in net.zones]
    assert [bus.zone for bus in out.buses] == [bus.zone for bus in net.buses]
    counts: dict[str, int] = {}
    for bus in out.buses:
        assert bus.zone is not None
        counts[bus.zone] = counts.get(bus.zone, 0) + 1
    assert counts == {"1": 122, "2": 80, "3": 63, "9": 35}  # research §1's own measured split


# -- corridors ------------------------------------------------------------------------------


def test_case30_corridors_cover_every_zone_pair_research_saw_tie_lines_for() -> None:
    net = promote_areas_to_zones(rated_network(_case30()))
    caps = corridors(net)
    # research §5's probe: 7 inter-zone tie lines on case30, 3 zones -- all 3 possible pairs
    assert set(caps) == {("1", "2"), ("1", "3"), ("2", "3")}
    for cap in caps.values():
        assert cap > 0.0


def test_case30_corridor_caps_equal_the_hand_summed_cut_set_ratings() -> None:
    """Independent reimplementation of the cut-set sum, not a call through ``corridors`` a
    second time -- the same "hand-derive the expected value" discipline
    ``tests/unit/test_rated_helper.py``'s own margin test uses."""
    net = promote_areas_to_zones(rated_network(_case30()))
    zone_of = {bus.id: bus.zone for bus in net.buses}
    expected: dict[tuple[str, str], float] = {}
    for br in net.branches:
        z_from, z_to = zone_of[br.from_bus], zone_of[br.to_bus]
        if z_from != z_to:
            assert br.rating_mva is not None
            key = tuple(sorted((z_from, z_to)))
            expected[key] = expected.get(key, 0.0) + br.rating_mva
    caps = corridors(net)
    assert caps.keys() == expected.keys()
    for key, value in expected.items():
        assert caps[key] == pytest.approx(value)


def test_case30_corridor_caps_match_directly_measured_values() -> None:
    """Pinned against the concrete numbers this fixture's own derived ratings produce (measured
    directly, scratchpad probe) -- a second, independent check beyond the hand-summed
    reconstruction above, so a sabotage that happens to also corrupt the test's own cut-set
    reconstruction is still caught."""
    net = promote_areas_to_zones(rated_network(_case30()))
    caps = corridors(net)
    assert caps[("1", "3")] == pytest.approx(16.576768909781237)
    assert caps[("1", "2")] == pytest.approx(1.5237037054530278)
    assert caps[("2", "3")] == pytest.approx(19.456188360964873)


def test_corridor_keys_are_sorted_pairs() -> None:
    net = promote_areas_to_zones(rated_network(_case30()))
    for z1, z2 in corridors(net):
        assert z1 < z2


def test_corridors_raises_clearly_on_an_unrated_crossing_branch() -> None:
    """case30 actually ships real ``RATE_A`` values (unlike the fixtures ``tests/_rated.py``'s
    own docstring names), so an unrated crossing branch has to be constructed by hand here."""
    net = promote_areas_to_zones(rated_network(_case30()))
    for br in net.branches:
        if br.id == "branch-12":  # a real inter-zone tie line, zones "1"/"3" (research §5)
            br.rating_mva = None
    with pytest.raises(ValueError, match="branch-12"):
        corridors(net)


def test_case14_single_zone_yields_an_empty_corridor_dict() -> None:
    """The absence-readback pairing: case14 has only 1 AREA group too (research §1), so it is
    already single-zone straight off the importer's own ZONE column -- no promotion needed or
    possible. Paired against the case30 positive above: an empty dict here is a genuine
    single-zone fact, not a bug that would also swallow case30's real corridors."""
    net = rated_network(_case14())
    assert len(net.zones) == 1
    assert corridors(net) == {}


# -- zone_of_bus / buses_by_zone -----------------------------------------------------------------


def test_zone_of_bus_matches_bus_zone_field() -> None:
    net = promote_areas_to_zones(_case30())
    assert zone_of_bus(net) == {bus.id: bus.zone for bus in net.buses}


def test_buses_by_zone_partitions_every_bus_exactly_once_with_the_measured_counts() -> None:
    net = promote_areas_to_zones(_case30())
    by_zone = buses_by_zone(net)
    assert set(by_zone) == {"1", "2", "3"}
    all_buses = [bus_id for buses in by_zone.values() for bus_id in buses]
    assert sorted(all_buses) == sorted(bus.id for bus in net.buses)
    assert {zone_id: len(buses) for zone_id, buses in by_zone.items()} == {
        "1": 11,
        "2": 10,
        "3": 9,
    }


def test_buses_by_zone_agrees_with_zone_of_bus() -> None:
    net = promote_areas_to_zones(_case30())
    by_zone = buses_by_zone(net)
    zmap = zone_of_bus(net)
    for zone_id, bus_ids in by_zone.items():
        for bus_id in bus_ids:
            assert zmap[bus_id] == zone_id
