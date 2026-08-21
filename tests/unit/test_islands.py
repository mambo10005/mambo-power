"""W4 / AC-5: island repair — the importer deactivates islands, the model stays strict.

``model.repair_islands`` (design item 4) is the one implementation every importer calls:
BFS from the in-service slack bus(es) over in-service branches whose endpoints are in
service; every in-service bus not reached is deactivated together with its attached
generators, loads, shunts, storage and branches, and each island is reported as one
``ISLAND_DEACTIVATED`` :class:`ImportWarning`. This mirrors pandapower's
``check_connectivity`` (unreached buses get ``BUS_TYPE = NONE``, their elements are dropped
from the solve) and MATPOWER's ``ext2int`` handling of isolated buses — except that here the
result is an explicit, validated :class:`Network` and a warning, never a NaN row.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from mambo_power.io import matpower
from mambo_power.model import (
    Branch,
    Bus,
    BusType,
    Generator,
    ImportWarning,
    Load,
    Network,
    NetworkValidationError,
    repair_islands,
    repair_islands_entities,
)
from tests._fixtures import FIXTURES_DIR

ISLAND = FIXTURES_DIR / "derived" / "case14_island.m"
CASE14 = FIXTURES_DIR / "case14.m"


def _service(net: Network) -> dict[str, bool]:
    out: dict[str, bool] = {}
    for coll in (net.buses, net.branches, net.generators, net.loads, net.shunts, net.storage):
        for item in coll:
            out[item.id] = item.in_service
    return out


# --- case14_island through the importer ---------------------------------------------------------


def test_load_with_warnings_repairs_the_island_and_warns_once() -> None:
    net, warnings = matpower.load_with_warnings(ISLAND)
    service = _service(net)
    assert service["bus-8"] is False
    assert service["gen-5"] is False  # the island's generator (bus 8 carries no load/shunt)
    assert service["branch-14"] is False  # 7-8, the edit that made the island
    # everything else is untouched: 13 live buses, 19 live branches, 4 live gens
    assert sum(b.in_service for b in net.buses) == 13
    assert sum(br.in_service for br in net.branches) == 19
    assert sum(g.in_service for g in net.generators) == 4
    assert all(ld.in_service for ld in net.loads)
    # case14 carries BASE_KV = 0 on every bus, so 14 BASE_KV_REPLACED warnings precede it
    island = [w for w in warnings if w.startswith("ISLAND_DEACTIVATED:")]
    assert len(island) == 1 and island[0] == warnings[-1]
    assert "bus-8" in island[0] and "gen-5" in island[0]
    assert all(w.startswith("BASE_KV_REPLACED:") for w in warnings[:-1])


def test_load_with_report_carries_typed_island_warning() -> None:
    net, report = matpower.load_with_report(ISLAND)
    assert net == matpower.load(ISLAND)
    assert report.codes == {"BASE_KV_REPLACED", "ISLAND_DEACTIVATED"}
    (w,) = [w for w in report.warnings if w.code == "ISLAND_DEACTIVATED"]
    assert isinstance(w, ImportWarning)
    assert w.bus_ids == ["bus-8"]
    assert w.element_ids == ["gen-5"]
    assert report.as_strings() == matpower.load_with_warnings(ISLAND)[1]
    assert str(w).startswith("ISLAND_DEACTIVATED: ")


def test_load_succeeds_silently() -> None:
    net = matpower.load(ISLAND)
    assert isinstance(net, Network)
    assert next(b for b in net.buses if b.id == "bus-8").in_service is False


def test_direct_network_with_the_island_still_raises_disconnected_bus() -> None:
    repaired = matpower.load(ISLAND)
    raw = repaired.model_dump()
    for bus in raw["buses"]:
        if bus["id"] == "bus-8":
            bus["in_service"] = True
    for gen in raw["generators"]:
        if gen["id"] == "gen-5":
            gen["in_service"] = True
    with pytest.raises(NetworkValidationError) as excinfo:
        Network.model_validate(raw)
    assert excinfo.value.codes == {"DISCONNECTED_BUS"}
    assert any("bus-8" in str(issue) for issue in excinfo.value.issues)


def test_repaired_network_round_trips_through_repair_unchanged() -> None:
    net = matpower.load(ISLAND)
    again, warnings = repair_islands(net)
    assert again == net and warnings == []


# --- repair_islands on a connected network: no-op -------------------------------------------------


def test_repair_islands_on_connected_case14_is_a_noop() -> None:
    net = matpower.load(CASE14)
    repaired, warnings = repair_islands(net)
    assert warnings == []
    assert repaired == net
    assert repaired is not net  # a new Network, never the input


def test_repair_islands_does_not_mutate_its_input() -> None:
    net = matpower.load(ISLAND)
    for bus in net.buses:
        if bus.id == "bus-8":
            bus.in_service = True
    for gen in net.generators:
        if gen.id == "gen-5":
            gen.in_service = True
    repaired, warnings = repair_islands(net)
    assert next(b for b in net.buses if b.id == "bus-8").in_service is True
    assert next(b for b in repaired.buses if b.id == "bus-8").in_service is False
    assert [w.code for w in warnings] == ["ISLAND_DEACTIVATED"]


# --- hand cases on the entity lists ---------------------------------------------------------------


def _bus(i: int, kind: BusType = "pq", in_service: bool = True) -> Bus:
    return Bus(id=f"b{i}", base_kv=110.0, type=kind, in_service=in_service)


def _branch(k: int, f: int, t: int, in_service: bool = True) -> Branch:
    return Branch(
        id=f"l{k}", from_bus=f"b{f}", to_bus=f"b{t}", r=0.01, x=0.1, b=0.0, in_service=in_service
    )


def _gen(k: int, bus: int, in_service: bool = True) -> Generator:
    return Generator(
        id=f"g{k}",
        bus=f"b{bus}",
        p_mw=10,
        q_mvar=0,
        p_min_mw=0,
        p_max_mw=100,
        q_min_mvar=-50,
        q_max_mvar=50,
        v_set_pu=1.0,
        in_service=in_service,
    )


def _load(k: int, bus: int) -> Load:
    return Load(id=f"d{k}", bus=f"b{bus}", p_mw=5, q_mvar=1)


def test_entities_repair_deactivates_each_island_with_its_elements_and_live_branches() -> None:
    # slack b1 -- b2 ; island A = {b3, b4} (live branch inside, open branch to b2); island B = {b5}
    buses = [_bus(1, "slack"), _bus(2), _bus(3, "pv"), _bus(4), _bus(5)]
    branches = [
        _branch(1, 1, 2),
        _branch(2, 2, 3, in_service=False),
        _branch(3, 3, 4),
        _branch(4, 4, 5, in_service=False),
    ]
    gens = [_gen(1, 1), _gen(2, 3), _gen(3, 4, in_service=False)]
    loads = [_load(1, 2), _load(2, 4), _load(3, 5)]
    out = repair_islands_entities(buses, branches, gens, loads, [], [])
    new_buses, new_branches, new_gens, new_loads, new_shunts, new_storage, warnings = out
    assert [b.in_service for b in new_buses] == [True, True, False, False, False]
    assert [br.in_service for br in new_branches] == [True, False, False, False]
    assert [g.in_service for g in new_gens] == [True, False, False]
    assert [ld.in_service for ld in new_loads] == [True, False, False]
    assert new_shunts == [] and new_storage == []
    # one warning per island, in bus order; already-out elements are not listed as deactivated
    assert [(w.code, w.bus_ids, w.element_ids) for w in warnings] == [
        ("ISLAND_DEACTIVATED", ["b3", "b4"], ["l3", "g2", "d2"]),
        ("ISLAND_DEACTIVATED", ["b5"], ["d3"]),
    ]
    # inputs untouched
    assert all(b.in_service for b in buses) and gens[1].in_service
    # and the repaired entities validate as a Network while the raw ones do not
    Network(
        base_mva=100, buses=new_buses, branches=new_branches, generators=new_gens, loads=new_loads
    )
    with pytest.raises(NetworkValidationError) as excinfo:
        Network(base_mva=100, buses=buses, branches=branches, generators=gens, loads=loads)
    assert excinfo.value.codes == {"DISCONNECTED_BUS"}


def test_entities_repair_ignores_buses_already_out_of_service() -> None:
    buses = [_bus(1, "slack"), _bus(2), _bus(3, in_service=False)]
    branches = [_branch(1, 1, 2), _branch(2, 2, 3)]
    *_, warnings = repair_islands_entities(buses, branches, [_gen(1, 1)], [], [], [])
    assert warnings == []


def test_entities_repair_without_any_slack_changes_nothing() -> None:
    # No slack: nothing is reachable by definition; that is NO_SLACK's job, not a repair.
    buses = [_bus(1, "pv"), _bus(2)]
    out = repair_islands_entities(buses, [_branch(1, 1, 2)], [_gen(1, 1)], [], [], [])
    assert [b.in_service for b in out[0]] == [True, True] and out[-1] == []


def test_two_islands_each_with_a_slack_are_both_kept_but_the_model_rejects_multi_slack() -> None:
    # Per-island slacks are out of scope for M2 (spec Not Doing: distributed slack; model
    # invariant MULTIPLE_SLACK). The repair keeps both — neither is an island from *a* slack —
    # and the Network constructor then rejects the pair, as it did before S2.
    buses = [_bus(1, "slack"), _bus(2), _bus(3, "slack"), _bus(4)]
    branches = [_branch(1, 1, 2), _branch(2, 3, 4)]
    gens = [_gen(1, 1), _gen(2, 3)]
    *_, warnings = repair_islands_entities(buses, branches, gens, [], [], [])
    assert warnings == []
    with pytest.raises(NetworkValidationError) as excinfo:
        Network(base_mva=100, buses=buses, branches=branches, generators=gens)
    # MULTIPLE_SLACK, plus DISCONNECTED_BUS: the model's own BFS starts from the first slack only
    assert excinfo.value.codes == {"MULTIPLE_SLACK", "DISCONNECTED_BUS"}


def test_import_warning_is_typed_and_prints_with_its_code() -> None:
    w = ImportWarning(code="ISLAND_DEACTIVATED", message="m", bus_ids=["b1"], element_ids=[])
    assert str(w) == "ISLAND_DEACTIVATED: m"
    with pytest.raises(ValidationError):  # closed code set
        ImportWarning(code="SOMETHING_ELSE", message="m")  # type: ignore[arg-type]
