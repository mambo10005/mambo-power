"""``NetworkArrays``: the in-service positional view and the single pu-conversion site.

A hand-built 4-bus network exercises every exclusion rule and conversion:

* ``bus-4`` is out of service, so it, its load, its generator and the branch reaching it
  are all absent from the arrays;
* ``branch-4`` has both endpoints in service but ``in_service=False`` — excluded;
* ``bus-2`` carries three generators, the first of which is out of service — sums and the
  voltage setpoint skip it;
* ``bus-3`` has an in-service and an out-of-service load, and a shunt — only the live load
  is summed.
"""

from __future__ import annotations

import dataclasses
import math

import numpy as np
import pytest

from mambo_power.model import Branch, Bus, Generator, Load, Network, Shunt
from mambo_power.numerics import NetworkArrays

BASE = 100.0


def four_bus() -> Network:
    return Network(
        base_mva=BASE,
        buses=[
            Bus(id="bus-1", base_kv=132.0, type="slack"),
            Bus(id="bus-2", base_kv=132.0, type="pv"),
            Bus(id="bus-3", base_kv=33.0, type="pq"),
            Bus(id="bus-4", base_kv=33.0, type="pq", in_service=False),
        ],
        branches=[
            Branch(id="branch-1", from_bus="bus-1", to_bus="bus-2", r=0.01, x=0.1, b=0.02),
            Branch(
                id="branch-2",
                from_bus="bus-2",
                to_bus="bus-3",
                r=0.0,
                x=0.2,
                b=0.0,
                tap_ratio=0.98,
                shift_deg=10.0,
                rating_mva=150.0,
            ),
            Branch(id="branch-3", from_bus="bus-1", to_bus="bus-3", r=0.02, x=0.25, b=0.04),
            Branch(
                id="branch-4",
                from_bus="bus-2",
                to_bus="bus-3",
                r=0.0,
                x=0.2,
                b=0.0,
                in_service=False,
            ),
            Branch(id="branch-5", from_bus="bus-3", to_bus="bus-4", r=0.01, x=0.05, b=0.0),
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
                v_set_pu=1.05,
            ),
            Generator(
                id="gen-2x",
                bus="bus-2",
                p_mw=999.0,
                q_mvar=999.0,
                p_min_mw=0.0,
                p_max_mw=999.0,
                q_min_mvar=-999.0,
                q_max_mvar=999.0,
                v_set_pu=0.9,
                in_service=False,
            ),
            Generator(
                id="gen-2a",
                bus="bus-2",
                p_mw=40.0,
                q_mvar=5.0,
                p_min_mw=10.0,
                p_max_mw=80.0,
                q_min_mvar=-20.0,
                q_max_mvar=30.0,
                v_set_pu=1.02,
            ),
            Generator(
                id="gen-2b",
                bus="bus-2",
                p_mw=25.0,
                q_mvar=3.0,
                p_min_mw=5.0,
                p_max_mw=60.0,
                q_min_mvar=-10.0,
                q_max_mvar=20.0,
                v_set_pu=1.03,
            ),
            Generator(
                id="gen-4",
                bus="bus-4",
                p_mw=10.0,
                q_mvar=0.0,
                p_min_mw=0.0,
                p_max_mw=10.0,
                q_min_mvar=0.0,
                q_max_mvar=0.0,
                v_set_pu=1.0,
            ),
        ],
        loads=[
            Load(id="load-3", bus="bus-3", p_mw=50.0, q_mvar=20.0),
            Load(id="load-3-off", bus="bus-3", p_mw=500.0, q_mvar=200.0, in_service=False),
            Load(id="load-4", bus="bus-4", p_mw=7.0, q_mvar=1.0),
        ],
        shunts=[
            Shunt(id="shunt-3", bus="bus-3", g_mw=5.0, b_mvar=10.0),
            Shunt(id="shunt-4", bus="bus-4", g_mw=1.0, b_mvar=1.0),
        ],
    )


@pytest.fixture(scope="module")
def arr() -> NetworkArrays:
    return NetworkArrays.from_network(four_bus())


def test_index_maps_cover_only_in_service_elements(arr: NetworkArrays) -> None:
    assert arr.bus_ids == ["bus-1", "bus-2", "bus-3"]
    assert arr.bus_index == {"bus-1": 0, "bus-2": 1, "bus-3": 2}
    assert arr.n_bus == 3
    assert arr.branch_ids == ["branch-1", "branch-2", "branch-3"]
    assert arr.branch_index == {"branch-1": 0, "branch-2": 1, "branch-3": 2}
    assert arr.n_branch == 3
    assert arr.gen_ids == ["gen-1", "gen-2a", "gen-2b"]


def test_slack_position_and_bus_types(arr: NetworkArrays) -> None:
    assert arr.slack == 0
    np.testing.assert_array_equal(arr.bus_type, [3, 2, 1])
    assert arr.bus_type.dtype.kind == "i"


def test_branch_endpoints_are_positions(arr: NetworkArrays) -> None:
    np.testing.assert_array_equal(arr.f, [0, 1, 0])
    np.testing.assert_array_equal(arr.t, [1, 2, 2])
    assert arr.f.dtype.kind == "i" and arr.t.dtype.kind == "i"


def test_branch_parameters_with_defaults(arr: NetworkArrays) -> None:
    np.testing.assert_allclose(arr.r, [0.01, 0.0, 0.02])
    np.testing.assert_allclose(arr.x, [0.1, 0.2, 0.25])
    np.testing.assert_allclose(arr.b, [0.02, 0.0, 0.04])
    np.testing.assert_allclose(arr.tap, [1.0, 0.98, 1.0])
    np.testing.assert_allclose(arr.shift_rad, [0.0, math.radians(10.0), 0.0])
    assert arr.rating_pu[0] == math.inf and arr.rating_pu[2] == math.inf
    assert arr.rating_pu[1] == 150.0 / BASE


def test_loads_and_shunts_are_summed_and_converted(arr: NetworkArrays) -> None:
    np.testing.assert_allclose(arr.p_load_pu, [0.0, 0.0, 50.0 / BASE])
    np.testing.assert_allclose(arr.q_load_pu, [0.0, 0.0, 20.0 / BASE])
    np.testing.assert_allclose(arr.g_shunt_pu, [0.0, 0.0, 5.0 / BASE])
    np.testing.assert_allclose(arr.b_shunt_pu, [0.0, 0.0, 10.0 / BASE])


def test_generators_summed_per_bus_skipping_out_of_service(arr: NetworkArrays) -> None:
    np.testing.assert_allclose(arr.p_gen_pu, [0.0, 65.0 / BASE, 0.0])
    np.testing.assert_allclose(arr.q_gen_pu, [0.0, 8.0 / BASE, 0.0])
    np.testing.assert_allclose(arr.p_min_pu, [0.0, 15.0 / BASE, 0.0])
    np.testing.assert_allclose(arr.p_max_pu, [300.0 / BASE, 140.0 / BASE, 0.0])
    np.testing.assert_allclose(arr.q_min_pu, [-100.0 / BASE, -30.0 / BASE, 0.0])
    np.testing.assert_allclose(arr.q_max_pu, [100.0 / BASE, 50.0 / BASE, 0.0])


def test_v_set_is_first_in_service_generator_or_one(arr: NetworkArrays) -> None:
    np.testing.assert_allclose(arr.v_set, [1.05, 1.02, 1.0])


def test_per_generator_arrays(arr: NetworkArrays) -> None:
    np.testing.assert_array_equal(arr.gen_bus, [0, 1, 1])
    np.testing.assert_allclose(arr.gen_p_pu, [0.0, 0.4, 0.25])
    np.testing.assert_allclose(arr.gen_p_min_pu, [0.0, 0.1, 0.05])
    np.testing.assert_allclose(arr.gen_p_max_pu, [3.0, 0.8, 0.6])
    np.testing.assert_allclose(arr.gen_q_pu, [0.0, 0.05, 0.03])
    np.testing.assert_allclose(arr.gen_q_min_pu, [-1.0, -0.2, -0.1])
    np.testing.assert_allclose(arr.gen_q_max_pu, [1.0, 0.3, 0.2])
    np.testing.assert_allclose(arr.gen_v_set, [1.05, 1.02, 1.03])


def test_view_is_frozen(arr: NetworkArrays) -> None:
    with pytest.raises(dataclasses.FrozenInstanceError):
        arr.slack = 1  # type: ignore[misc]


def test_base_mva_is_carried(arr: NetworkArrays) -> None:
    assert arr.base_mva == BASE


def test_pu_conversion_scales_with_base() -> None:
    net = four_bus()
    net.base_mva = 50.0
    arr = NetworkArrays.from_network(net)
    assert arr.p_load_pu[2] == 50.0 / 50.0
    assert arr.rating_pu[1] == 150.0 / 50.0
    assert arr.gen_p_max_pu[0] == 300.0 / 50.0
