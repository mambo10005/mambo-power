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

from mambo_power.io import matpower
from mambo_power.model import Branch, Bus, Generator, Load, Network, Shunt, Storage
from mambo_power.numerics import NetworkArrays
from tests._fixtures import FIXTURES, FIXTURES_DIR

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


def test_no_storage_gives_empty_arrays_not_a_crash(arr: NetworkArrays) -> None:
    """``four_bus`` carries no ``Storage`` entities at all -- the common case (research §8.1:
    every MATPOWER fixture has zero storage), not an edge case. ``from_network`` must not
    raise, and every per-storage array must come back empty with the right dtype.
    """
    assert arr.storage_ids == []
    assert arr.storage_bus.shape == (0,)
    assert arr.storage_bus.dtype.kind == "i"
    for values in (
        arr.storage_p_max_pu,
        arr.storage_energy_pu,
        arr.storage_soc_initial,
        arr.storage_efficiency_charge,
        arr.storage_efficiency_discharge,
    ):
        assert values.shape == (0,)
        assert values.dtype.kind == "f"


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


def test_per_bus_sums_agree_with_per_generator_arrays(arr: NetworkArrays) -> None:
    # bus-2 carries two in-service generators, so this is the multi-generator agreement case.
    pairs = [
        (arr.p_gen_pu, arr.gen_p_pu),
        (arr.q_gen_pu, arr.gen_q_pu),
        (arr.p_min_pu, arr.gen_p_min_pu),
        (arr.p_max_pu, arr.gen_p_max_pu),
        (arr.q_min_pu, arr.gen_q_min_pu),
        (arr.q_max_pu, arr.gen_q_max_pu),
    ]
    for per_bus, per_gen in pairs:
        summed = np.bincount(arr.gen_bus, weights=per_gen, minlength=arr.n_bus)
        np.testing.assert_allclose(summed, per_bus, rtol=0, atol=1e-15)


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


def test_aggregate_load_arrays_unchanged_by_per_load_identity(arr: NetworkArrays) -> None:
    """M4 W3 regression: the per-load identity fields are additive.

    ``p_load_pu``/``q_load_pu`` (the bus aggregate M1-M3 callers read) must be byte-identical
    to what the pre-M4 ``per_bus`` bincount alone produces — not merely "close", exact, since
    no new code path may touch them.
    """
    net = four_bus()
    loads = [ld for ld in net.loads if ld.in_service and ld.bus in arr.bus_index]
    expected_p = (
        np.bincount(
            [arr.bus_index[ld.bus] for ld in loads],
            weights=[ld.p_mw for ld in loads],
            minlength=arr.n_bus,
        )
        / net.base_mva
    )
    expected_q = (
        np.bincount(
            [arr.bus_index[ld.bus] for ld in loads],
            weights=[ld.q_mvar for ld in loads],
            minlength=arr.n_bus,
        )
        / net.base_mva
    )
    np.testing.assert_array_equal(arr.p_load_pu, expected_p)
    np.testing.assert_array_equal(arr.q_load_pu, expected_q)


def multi_load_network() -> Network:
    """Mirrors ``four_bus``'s multi-generator-per-bus case, but for loads: bus-2 carries two
    in-service loads and one out-of-service load; bus-3 carries one. Exercises per-load
    identity, exclusion, and per-bus aggregation with more than one load at a bus — the load
    equivalent of ``four_bus``'s bus-2 (three generators, one excluded).
    """
    return Network(
        base_mva=BASE,
        buses=[
            Bus(id="bus-1", base_kv=132.0, type="slack"),
            Bus(id="bus-2", base_kv=132.0, type="pq"),
            Bus(id="bus-3", base_kv=33.0, type="pq"),
        ],
        branches=[
            Branch(id="branch-1", from_bus="bus-1", to_bus="bus-2", r=0.01, x=0.1, b=0.0),
            Branch(id="branch-2", from_bus="bus-2", to_bus="bus-3", r=0.01, x=0.1, b=0.0),
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
        ],
        loads=[
            Load(id="load-2a", bus="bus-2", p_mw=30.0, q_mvar=5.0),
            Load(id="load-2b", bus="bus-2", p_mw=15.0, q_mvar=2.0),
            Load(id="load-2-off", bus="bus-2", p_mw=999.0, q_mvar=999.0, in_service=False),
            Load(id="load-3", bus="bus-3", p_mw=8.0, q_mvar=1.0),
        ],
    )


@pytest.fixture(scope="module")
def marr() -> NetworkArrays:
    return NetworkArrays.from_network(multi_load_network())


def test_per_load_identity(marr: NetworkArrays) -> None:
    assert marr.load_ids == ["load-2a", "load-2b", "load-3"]
    np.testing.assert_array_equal(marr.load_bus, [1, 1, 2])
    assert marr.load_bus.dtype.kind == "i"


def test_per_load_bounds_are_zero_to_own_demand(marr: NetworkArrays) -> None:
    """W3's derived rule: ``[0, p_mw]`` in pu for every load, regardless of ``Load.bid``.

    A generator's ``gen_p_min_pu``/``gen_p_max_pu`` come straight off two entity fields
    (``p_min_mw``/``p_max_mw``); ``Load`` has no such fields (only ``p_mw``), and the bound
    that matters for a bid-load is ``[0, p_mw]`` (record/m4-research.md §4.2, "up to its own
    fixed historical demand"). Since nothing in that rule turns on whether ``Load.bid`` is
    set, arrays.py builds this bound uniformly for every load — bid-having or not; S3 decides
    whether/how ``dc_opf`` actually uses it for a given load. ``load-2a``/``load-2b``/
    ``load-3`` here stand in for "a load with a bid" and "a load without" precisely because
    the bound formula does not distinguish them.
    """
    np.testing.assert_allclose(marr.load_p_min_pu, [0.0, 0.0, 0.0])
    np.testing.assert_allclose(marr.load_p_max_pu, [30.0 / BASE, 15.0 / BASE, 8.0 / BASE])


def test_per_load_sums_agree_with_aggregate(marr: NetworkArrays) -> None:
    summed = np.bincount(marr.load_bus, weights=marr.load_p_max_pu, minlength=marr.n_bus)
    np.testing.assert_allclose(summed, marr.p_load_pu, rtol=0, atol=1e-15)


def multi_storage_network() -> Network:
    """Mirrors ``multi_load_network``'s shape, but for storage: bus-2 carries two in-service
    storage units and one out-of-service unit; bus-3 carries one. Exercises per-storage
    identity, exclusion, and pu conversion with more than one storage unit at a bus -- the
    storage equivalent of ``multi_load_network``'s bus-2.
    """
    return Network(
        base_mva=BASE,
        buses=[
            Bus(id="bus-1", base_kv=132.0, type="slack"),
            Bus(id="bus-2", base_kv=132.0, type="pq"),
            Bus(id="bus-3", base_kv=33.0, type="pq"),
        ],
        branches=[
            Branch(id="branch-1", from_bus="bus-1", to_bus="bus-2", r=0.01, x=0.1, b=0.0),
            Branch(id="branch-2", from_bus="bus-2", to_bus="bus-3", r=0.01, x=0.1, b=0.0),
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
        ],
        loads=[Load(id="load-1", bus="bus-1", p_mw=100.0, q_mvar=20.0)],
        storage=[
            Storage(
                id="storage-2a",
                bus="bus-2",
                p_max_mw=20.0,
                energy_mwh=40.0,
                soc_initial=0.5,
                efficiency_charge=0.9,
                efficiency_discharge=0.85,
            ),
            Storage(
                id="storage-2b",
                bus="bus-2",
                p_max_mw=10.0,
                energy_mwh=15.0,
                soc_initial=0.25,
                efficiency_charge=0.95,
                efficiency_discharge=0.9,
            ),
            Storage(
                id="storage-2-off",
                bus="bus-2",
                p_max_mw=999.0,
                energy_mwh=999.0,
                soc_initial=1.0,
                efficiency_charge=1.0,
                efficiency_discharge=1.0,
                in_service=False,
            ),
            Storage(
                id="storage-3",
                bus="bus-3",
                p_max_mw=5.0,
                energy_mwh=8.0,
                soc_initial=1.0,
                efficiency_charge=0.8,
                efficiency_discharge=0.8,
            ),
        ],
    )


@pytest.fixture(scope="module")
def sarr() -> NetworkArrays:
    return NetworkArrays.from_network(multi_storage_network())


def test_per_storage_identity(sarr: NetworkArrays) -> None:
    """Every in-service storage unit gets exactly one entry, correctly ordered, out-of-service
    excluded, bus index correct -- the storage mirror of ``test_per_load_identity``.
    """
    assert sarr.storage_ids == ["storage-2a", "storage-2b", "storage-3"]
    np.testing.assert_array_equal(sarr.storage_bus, [1, 1, 2])
    assert sarr.storage_bus.dtype.kind == "i"


def test_per_storage_values(sarr: NetworkArrays) -> None:
    """ADR-005: physical units (MW, MWh) in the model, per unit in numerics -- ``p_max_mw`` and
    ``energy_mwh`` divide by ``base_mva`` like every other physical field ``arrays.py`` already
    converts; ``soc_initial`` (already a fraction of ``energy_mwh``) and both efficiencies
    (already dimensionless ratios) carry through unconverted.
    """
    np.testing.assert_allclose(sarr.storage_p_max_pu, [20.0 / BASE, 10.0 / BASE, 5.0 / BASE])
    np.testing.assert_allclose(sarr.storage_energy_pu, [40.0 / BASE, 15.0 / BASE, 8.0 / BASE])
    np.testing.assert_allclose(sarr.storage_soc_initial, [0.5, 0.25, 1.0])
    np.testing.assert_allclose(sarr.storage_efficiency_charge, [0.9, 0.95, 0.8])
    np.testing.assert_allclose(sarr.storage_efficiency_discharge, [0.85, 0.9, 0.8])


def test_storage_pu_conversion_scales_with_base() -> None:
    net = multi_storage_network()
    net.base_mva = 50.0
    arr = NetworkArrays.from_network(net)
    assert arr.storage_p_max_pu[0] == 20.0 / 50.0
    assert arr.storage_energy_pu[0] == 40.0 / 50.0


@pytest.mark.parametrize("name", FIXTURES)
def test_every_matpower_fixture_has_no_storage(name: str) -> None:
    """research §8.1: every fixture has zero storage -- the common case, not an edge case."""
    net = matpower.load(FIXTURES_DIR / f"{name}.m")
    arr = NetworkArrays.from_network(net)
    assert arr.storage_ids == []
    assert arr.storage_bus.shape == (0,)


@pytest.mark.parametrize("name", FIXTURES)
def test_existing_aggregate_arrays_unchanged_on_every_fixture(name: str) -> None:
    """The pre-existing aggregate arrays must be byte-identical before and after adding
    per-storage identity, on every fixture -- the check that matters most (a silent shift here
    would corrupt every solver in the package), mirrored from
    ``test_aggregate_load_arrays_unchanged_by_per_load_identity`` which proved the same thing
    for M4's own per-load identity addition.
    """
    net = matpower.load(FIXTURES_DIR / f"{name}.m")
    arr = NetworkArrays.from_network(net)

    loads = [ld for ld in net.loads if ld.in_service and ld.bus in arr.bus_index]
    expected_p = (
        np.bincount(
            [arr.bus_index[ld.bus] for ld in loads],
            weights=[ld.p_mw for ld in loads],
            minlength=arr.n_bus,
        )
        / net.base_mva
    )
    expected_q = (
        np.bincount(
            [arr.bus_index[ld.bus] for ld in loads],
            weights=[ld.q_mvar for ld in loads],
            minlength=arr.n_bus,
        )
        / net.base_mva
    )
    np.testing.assert_array_equal(arr.p_load_pu, expected_p)
    np.testing.assert_array_equal(arr.q_load_pu, expected_q)

    gens = [g for g in net.generators if g.in_service and g.bus in arr.bus_index]
    expected_p_max = (
        np.bincount(
            [arr.bus_index[g.bus] for g in gens],
            weights=[g.p_max_mw for g in gens],
            minlength=arr.n_bus,
        )
        / net.base_mva
    )
    np.testing.assert_array_equal(arr.p_max_pu, expected_p_max)
