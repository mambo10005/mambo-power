"""Unit test for ``tests._storage``: the storage-derivation test helper (M5 W7, AC-6 fixture
half).

Mirrors ``tests/unit/test_rated_helper.py``'s and ``tests/unit/test_bids.py``'s own discipline:
proves the helper's guarantees directly (sizing anchored to the network's own committed load,
asymmetric efficiencies, deterministic siting, no mutation of the input network) rather than
merely exercising it as a side effect of another test.
"""

from __future__ import annotations

import pytest

from mambo_power.io.matpower import load
from mambo_power.model import Storage
from tests._fixtures import FIXTURES_DIR
from tests._storage import (
    DURATION_HOURS,
    EFFICIENCY_CHARGE,
    EFFICIENCY_DISCHARGE,
    POWER_FRACTION_OF_TOTAL_LOAD,
    SOC_INITIAL,
    storage_for_network,
    with_storage,
)


def _case14():  # type: ignore[no-untyped-def]
    return load(FIXTURES_DIR / "case14.m")


def test_storage_for_network_is_sized_off_the_network_s_own_total_load() -> None:
    net = _case14()
    unit = storage_for_network(net)
    assert isinstance(unit, Storage)
    total_load = sum(ld.p_mw for ld in net.loads)
    assert unit.p_max_mw == pytest.approx(POWER_FRACTION_OF_TOTAL_LOAD * total_load)
    assert unit.energy_mwh == pytest.approx(unit.p_max_mw * DURATION_HOURS)


def test_efficiencies_are_asymmetric() -> None:
    """Not equal -- an equal-efficiency fixture is exactly the powerless-sabotage shape S4's own
    sweep caught (module docstring)."""
    assert EFFICIENCY_CHARGE != EFFICIENCY_DISCHARGE
    assert 0.0 < EFFICIENCY_CHARGE <= 1.0
    assert 0.0 < EFFICIENCY_DISCHARGE <= 1.0


def test_soc_initial_is_a_genuine_fraction_not_empty_or_full() -> None:
    assert 0.0 < SOC_INITIAL < 1.0


def test_default_siting_is_the_bus_with_the_largest_aggregate_load() -> None:
    net = _case14()
    unit = storage_for_network(net)
    totals: dict[str, float] = {}
    for ld in net.loads:
        totals[ld.bus] = totals.get(ld.bus, 0.0) + ld.p_mw
    expected_bus = max(totals, key=lambda bus: totals[bus])
    assert unit.bus == expected_bus == "bus-3"  # case14.m's own largest single load, load-3


def test_explicit_bus_id_is_honoured() -> None:
    net = _case14()
    unit = storage_for_network(net, bus_id="bus-9")
    assert unit.bus == "bus-9"


def test_rejects_an_unknown_bus_id() -> None:
    net = _case14()
    with pytest.raises(ValueError, match="bus-999"):
        storage_for_network(net, bus_id="bus-999")


def test_rejects_a_network_with_no_loads() -> None:
    net = _case14()
    net = net.model_copy(deep=True)
    net.loads = []
    with pytest.raises(ValueError, match="load"):
        storage_for_network(net)


def test_with_storage_appends_without_mutating_the_input() -> None:
    net = _case14()
    assert net.storage == []
    out = with_storage(net)
    assert net.storage == [], "input network must be unchanged"
    assert len(out.storage) == 1
    assert out.storage[0].bus == "bus-3"


def test_with_storage_is_deterministic() -> None:
    net = _case14()
    a = with_storage(net)
    b = with_storage(net)
    assert a.storage[0].model_dump() == b.storage[0].model_dump()
