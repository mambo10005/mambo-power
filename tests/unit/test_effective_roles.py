"""W3 / AC-4: ``numerics.effective_roles`` — the single derivation site for power-flow roles.

Rules under test (wave M2 design item 2; record/m2-research.md §2-3):

* a declared PV bus with no in-service generator is solved as PQ (MATPOWER ``bustypes``:
  ``pq = find(BUS_TYPE == PQ | ~bus_gen_status)``; pandapower: only in-service gens write
  ``BUS_TYPE = PV``) while :class:`NetworkArrays` keeps the declared role;
* a slack bus with no in-service generator raises :class:`NoSlackGeneratorError` naming it
  (MATPOWER would silently re-slack the first PV bus; that is rejected in the spec);
* the setpoint of a bus with several in-service generators is the LAST one's ``v_set_pu`` in
  generator order (MATPOWER ``runpf.m:296`` repeated-index assignment) and differing
  setpoints emit :class:`SetpointConflictWarning` naming the bus (pandapower raises a
  ``UserWarning`` for the same situation).
"""

from __future__ import annotations

import warnings

import numpy as np
import pytest

from mambo_power.io import matpower
from mambo_power.numerics import (
    EffectiveRoles,
    NetworkArrays,
    NoSlackGeneratorError,
    SetpointConflictWarning,
    effective_roles,
)
from tests._fixtures import FIXTURES_DIR

DERIVED_DIR = FIXTURES_DIR / "derived"
PQ, PV, SLACK = 1, 2, 3


def _arrays(name: str) -> NetworkArrays:
    path = (DERIVED_DIR if name.startswith("case14_") else FIXTURES_DIR) / f"{name}.m"
    return NetworkArrays.from_network(matpower.load(path))


# --- case14_roles: gen-less PV bus and a two-generator bus --------------------------------------


def test_pv_bus_without_in_service_generator_is_effectively_pq() -> None:
    arr = _arrays("case14_roles")
    bus6 = arr.bus_index["bus-6"]
    assert arr.bus_type[bus6] == PV  # declared role is untouched
    with pytest.warns(SetpointConflictWarning):  # bus-2, asserted below
        roles = effective_roles(arr)
    assert isinstance(roles, EffectiveRoles)
    assert roles.bus_type[bus6] == PQ
    assert roles.demoted_pv.tolist() == [bus6]
    # every other bus keeps its declared role
    others = [i for i in range(arr.n_bus) if i != bus6]
    np.testing.assert_array_equal(roles.bus_type[others], arr.bus_type[others])
    assert roles.bus_type.dtype.kind == "i"


def test_two_generator_bus_takes_the_last_setpoint_and_warns() -> None:
    arr = _arrays("case14_roles")
    bus2 = arr.bus_index["bus-2"]
    assert arr.v_set[bus2] == 1.045  # M1's arrays keep the first in-service gen's VG
    with pytest.warns(SetpointConflictWarning, match=r"bus-2") as record:
        roles = effective_roles(arr)
    assert roles.v_set[bus2] == 1.055  # MATPOWER: last in-service generator row wins
    assert roles.setpoint_conflicts == [("bus-2", ["gen-2", "gen-6"], [1.045, 1.055])]
    messages = [str(w.message) for w in record if w.category is SetpointConflictWarning]
    assert len(messages) == 1
    assert "bus-2" in messages[0] and "1.045" in messages[0] and "1.055" in messages[0]
    assert "gen-2" in messages[0] and "gen-6" in messages[0]


def test_setpoints_of_single_generator_buses_are_unchanged() -> None:
    arr = _arrays("case14_roles")
    with pytest.warns(SetpointConflictWarning):
        roles = effective_roles(arr)
    for bus_id in ("bus-1", "bus-3", "bus-8"):
        i = arr.bus_index[bus_id]
        assert roles.v_set[i] == arr.v_set[i]
    assert roles.v_set[arr.bus_index["bus-6"]] == 1.0  # no generator left: nothing to pin


def test_effective_roles_is_frozen() -> None:
    arr = _arrays("case14")
    roles = effective_roles(arr)
    with pytest.raises(AttributeError):
        roles.v_set = roles.v_set  # type: ignore[misc]


# --- case14_noslackgen: slack without a generator ------------------------------------------------


def test_slack_without_in_service_generator_raises_named_error() -> None:
    arr = _arrays("case14_noslackgen")
    with pytest.raises(NoSlackGeneratorError, match=r"bus-1") as excinfo:
        effective_roles(arr)
    assert excinfo.value.bus_id == "bus-1"
    assert excinfo.value.position == arr.slack
    assert not isinstance(excinfo.value, ValueError)  # a named error, not a generic one


# --- upstream fixtures: identity -----------------------------------------------------------------


@pytest.mark.parametrize("name", ["case14", "case_ieee30", "case118", "case300"])
def test_effective_equals_declared_on_upstream_fixtures(name: str) -> None:
    arr = _arrays(name)
    with warnings.catch_warnings():
        warnings.simplefilter("error")  # any warning fails the test
        roles = effective_roles(arr)
    np.testing.assert_array_equal(roles.bus_type, arr.bus_type)
    assert roles.demoted_pv.size == 0
    assert roles.setpoint_conflicts == []
    # every generator bus carries its (single or agreeing) VG, every other bus 1.0
    gen_buses = set(arr.gen_bus.tolist())
    for i in range(arr.n_bus):
        if i in gen_buses:
            last = max(g for g in range(len(arr.gen_ids)) if arr.gen_bus[g] == i)
            assert roles.v_set[i] == arr.gen_v_set[last]
        else:
            assert roles.v_set[i] == 1.0


def test_arrays_are_not_modified() -> None:
    arr = _arrays("case14_roles")
    before_type, before_vset = arr.bus_type.copy(), arr.v_set.copy()
    with pytest.warns(SetpointConflictWarning):
        effective_roles(arr)
    np.testing.assert_array_equal(arr.bus_type, before_type)
    np.testing.assert_array_equal(arr.v_set, before_vset)
