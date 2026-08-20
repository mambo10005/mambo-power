"""A well-formed 3-bus network validates silently and the index helper is positional."""

import pytest
from pydantic import ValidationError

from mambo_power.model import Branch, Bus, Generator, Load, Network


def three_bus() -> Network:
    return Network(
        base_mva=100.0,
        buses=[
            Bus(id="bus-1", base_kv=110.0, type="slack"),
            Bus(id="bus-2", base_kv=110.0, type="pv"),
            Bus(id="bus-3", base_kv=110.0, type="pq"),
        ],
        branches=[
            Branch(id="branch-1", from_bus="bus-1", to_bus="bus-2", r=0.01, x=0.1, b=0.0),
            Branch(id="branch-2", from_bus="bus-2", to_bus="bus-3", r=0.01, x=0.1, b=0.0),
            Branch(id="branch-3", from_bus="bus-1", to_bus="bus-3", r=0.01, x=0.1, b=0.0),
        ],
        generators=[
            Generator(
                id="gen-1",
                bus="bus-1",
                p_mw=0.0,
                q_mvar=0.0,
                p_min_mw=0.0,
                p_max_mw=300.0,
                q_min_mvar=-100.0,
                q_max_mvar=100.0,
                v_set_pu=1.0,
            ),
            Generator(
                id="gen-2",
                bus="bus-2",
                p_mw=50.0,
                q_mvar=0.0,
                p_min_mw=0.0,
                p_max_mw=100.0,
                q_min_mvar=-50.0,
                q_max_mvar=50.0,
                v_set_pu=1.0,
            ),
        ],
        loads=[Load(id="load-bus-3", bus="bus-3", p_mw=90.0, q_mvar=30.0)],
    )


def test_three_bus_validates_silently() -> None:
    net = three_bus()
    assert net.schema_version == 1
    assert [b.id for b in net.buses] == ["bus-1", "bus-2", "bus-3"]
    assert net.shunts == [] and net.storage == [] and net.zones == []


def test_bus_index_is_positional() -> None:
    assert three_bus().bus_index() == {"bus-1": 0, "bus-2": 1, "bus-3": 2}


def test_defaults_are_applied() -> None:
    net = three_bus()
    assert all(b.in_service for b in net.buses)
    assert all(br.tap_ratio is None and br.shift_deg is None for br in net.branches)
    assert all(g.cost is None for g in net.generators)


def test_extra_fields_are_rejected() -> None:
    with pytest.raises(ValidationError):
        Bus(id="b", base_kv=1.0, type="pq", colour="red")  # type: ignore[call-arg]
