"""AC-4: every named validation code is raised on a minimal counter-example.

Each test builds the smallest network that violates exactly one invariant and asserts the
expected ``ValidationCode`` appears in ``NetworkValidationError.issues``.
"""

import math
from typing import Any

import pytest
from pydantic import ValidationError

from mambo_power.model import (
    Branch,
    Bus,
    Generator,
    Load,
    Network,
    NetworkValidationError,
    PiecewiseCost,
    PolynomialCost,
    Storage,
    ValidationCode,
)


def codes(err: NetworkValidationError) -> set[str]:
    return {issue.code for issue in err.issues}


def slack(bus_id: str = "b1", **overrides: Any) -> Bus:
    data: dict[str, Any] = {"id": bus_id, "base_kv": 110.0, "type": "slack"}
    data.update(overrides)
    return Bus(**data)


def pq(bus_id: str, **overrides: Any) -> Bus:
    data: dict[str, Any] = {"id": bus_id, "base_kv": 110.0, "type": "pq"}
    data.update(overrides)
    return Bus(**data)


def line(branch_id: str, from_bus: str, to_bus: str, **overrides: Any) -> Branch:
    data: dict[str, Any] = {
        "id": branch_id,
        "from_bus": from_bus,
        "to_bus": to_bus,
        "r": 0.01,
        "x": 0.1,
        "b": 0.0,
    }
    data.update(overrides)
    return Branch(**data)


def gen(gen_id: str, bus: str, **overrides: Any) -> Generator:
    data: dict[str, Any] = {
        "id": gen_id,
        "bus": bus,
        "p_mw": 10.0,
        "q_mvar": 0.0,
        "p_min_mw": 0.0,
        "p_max_mw": 100.0,
        "q_min_mvar": -50.0,
        "q_max_mvar": 50.0,
        "v_set_pu": 1.0,
    }
    data.update(overrides)
    return Generator(**data)


def storage(storage_id: str, bus: str, **overrides: Any) -> Storage:
    data: dict[str, Any] = {
        "id": storage_id,
        "bus": bus,
        "p_max_mw": 10.0,
        "energy_mwh": 40.0,
        "soc_initial": 0.5,
        "efficiency_charge": 0.95,
        "efficiency_discharge": 0.95,
    }
    data.update(overrides)
    return Storage(**data)


def expect(code: ValidationCode, **network_kwargs: Any) -> NetworkValidationError:
    with pytest.raises(NetworkValidationError) as excinfo:
        Network(base_mva=100.0, **network_kwargs)
    assert code in codes(excinfo.value), excinfo.value
    return excinfo.value


def test_no_slack() -> None:
    expect("NO_SLACK", buses=[pq("b1")])


def test_no_slack_counts_only_in_service_slack_buses() -> None:
    expect("NO_SLACK", buses=[slack("b1", in_service=False)])


def test_multiple_slack() -> None:
    expect("MULTIPLE_SLACK", buses=[slack("b1"), slack("b2")], branches=[line("l1", "b1", "b2")])


def test_disconnected_bus() -> None:
    err = expect("DISCONNECTED_BUS", buses=[slack("b1"), pq("b2")])
    assert any(i.code == "DISCONNECTED_BUS" and i.path == "buses[1]" for i in err.issues)


def test_disconnected_bus_over_out_of_service_branch() -> None:
    expect(
        "DISCONNECTED_BUS",
        buses=[slack("b1"), pq("b2")],
        branches=[line("l1", "b1", "b2", in_service=False)],
    )


def test_disconnected_bus_over_branch_to_out_of_service_bus() -> None:
    # b3 is only reachable through b2, which is out of service: the branch b2-b3 carries nothing.
    expect(
        "DISCONNECTED_BUS",
        buses=[slack("b1"), pq("b2", in_service=False), pq("b3")],
        branches=[line("l1", "b1", "b2"), line("l2", "b2", "b3")],
    )


def test_out_of_service_bus_is_not_disconnected() -> None:
    # Wave design 4: MATPOWER type-4 buses become in_service=False and are tolerated.
    net = Network(base_mva=100.0, buses=[slack("b1"), pq("b2", in_service=False)])
    assert len(net.buses) == 2


def test_duplicate_id() -> None:
    err = expect(
        "DUPLICATE_ID",
        buses=[slack("b1"), pq("b1"), pq("b2")],
        branches=[line("l1", "b1", "b2")],
    )
    assert any(i.code == "DUPLICATE_ID" and i.path == "buses[1].id" for i in err.issues)


def test_duplicate_id_is_per_collection_not_global() -> None:
    # Same id on a bus and a load is fine: uniqueness is per collection (W1 extract 1.4).
    net = Network(
        base_mva=100.0,
        buses=[slack("x")],
        loads=[Load(id="x", bus="x", p_mw=1.0, q_mvar=0.0)],
    )
    assert net.loads[0].id == net.buses[0].id


@pytest.mark.parametrize(
    ("kwargs", "path"),
    [
        ({"branches": [line("l1", "b1", "ghost")]}, "branches[0].to_bus"),
        ({"branches": [line("l1", "ghost", "b1")]}, "branches[0].from_bus"),
        ({"generators": [gen("g1", "ghost")]}, "generators[0].bus"),
        ({"loads": [Load(id="d1", bus="ghost", p_mw=1.0, q_mvar=0.0)]}, "loads[0].bus"),
        ({"shunts": [{"id": "s1", "bus": "ghost", "g_mw": 0.0, "b_mvar": 1.0}]}, "shunts[0].bus"),
        ({"storage": [storage("e1", "ghost")]}, "storage[0].bus"),
        ({"buses": [slack("b1", zone="ghost")]}, "buses[0].zone"),
    ],
)
def test_dangling_ref(kwargs: dict[str, Any], path: str) -> None:
    kwargs.setdefault("buses", [slack("b1")])
    err = expect("DANGLING_REF", **kwargs)
    assert any(i.code == "DANGLING_REF" and i.path == path for i in err.issues), err


def test_bad_base_mva() -> None:
    with pytest.raises(NetworkValidationError) as excinfo:
        Network(base_mva=0.0, buses=[slack("b1")])
    assert any(i.code == "BAD_BASE" and i.path == "base_mva" for i in excinfo.value.issues)


def test_bad_base_kv() -> None:
    err = expect("BAD_BASE", buses=[slack("b1", base_kv=-1.0)])
    assert any(i.code == "BAD_BASE" and i.path == "buses[0].base_kv" for i in err.issues)


@pytest.mark.parametrize(
    ("kwargs", "path"),
    [
        ({"generators": [gen("g1", "b1", p_min_mw=50.0, p_max_mw=10.0)]}, "generators[0].p_min_mw"),
        (
            {"generators": [gen("g1", "b1", q_min_mvar=10.0, q_max_mvar=-10.0)]},
            "generators[0].q_min_mvar",
        ),
        ({"buses": [slack("b1", v_min_pu=1.1, v_max_pu=0.9)]}, "buses[0].v_min_pu"),
        ({"storage": [storage("e1", "b1", soc_initial=1.5)]}, "storage[0].soc_initial"),
        ({"storage": [storage("e1", "b1", soc_initial=-0.1)]}, "storage[0].soc_initial"),
        (
            {"storage": [storage("e1", "b1", efficiency_charge=0.0)]},
            "storage[0].efficiency_charge",
        ),
        (
            {"storage": [storage("e1", "b1", efficiency_discharge=1.2)]},
            "storage[0].efficiency_discharge",
        ),
        (
            {
                "generators": [
                    gen(
                        "g1",
                        "b1",
                        cost=PiecewiseCost(points=[(0.0, 0.0), (50.0, 100.0), (20.0, 200.0)]),
                    )
                ]
            },
            "generators[0].cost.points",
        ),
        # Correctness 2: a branch may not connect a bus to itself.
        (
            {
                "buses": [slack("b1"), pq("b2")],
                "branches": [line("l1", "b1", "b2"), line("l2", "b2", "b2")],
            },
            "branches[1].to_bus",
        ),
        # Correctness 3: tap_ratio <= 0 and r == x == 0 would reach the builders as NaN.
        (
            {"buses": [slack("b1"), pq("b2")], "branches": [line("l1", "b1", "b2", tap_ratio=0.0)]},
            "branches[0].tap_ratio",
        ),
        (
            {
                "buses": [slack("b1"), pq("b2")],
                "branches": [line("l1", "b1", "b2", tap_ratio=-1.0)],
            },
            "branches[0].tap_ratio",
        ),
        (
            {"buses": [slack("b1"), pq("b2")], "branches": [line("l1", "b1", "b2", r=0.0, x=0.0)]},
            "branches[0].x",
        ),
        # Critic 6: rating_mva 0 in a native file means zero capacity, not "no rating".
        (
            {
                "buses": [slack("b1"), pq("b2")],
                "branches": [line("l1", "b1", "b2", rating_mva=0.0)],
            },
            "branches[0].rating_mva",
        ),
        (
            {"generators": [gen("g1", "b1", cost=PolynomialCost(coefficients=[]))]},
            "generators[0].cost.coefficients",
        ),
        (
            {"generators": [gen("g1", "b1", cost=PiecewiseCost(points=[(0.0, 0.0)]))]},
            "generators[0].cost.points",
        ),
        (
            # equal consecutive p: a vertical segment; MATPOWER requires strictly increasing x
            {
                "generators": [
                    gen(
                        "g1",
                        "b1",
                        cost=PiecewiseCost(points=[(0.0, 0.0), (10.0, 5.0), (10.0, 9.0)]),
                    )
                ]
            },
            "generators[0].cost.points",
        ),
    ],
)
def test_bad_range(kwargs: dict[str, Any], path: str) -> None:
    kwargs.setdefault("buses", [slack("b1")])
    err = expect("BAD_RANGE", **kwargs)
    assert any(i.code == "BAD_RANGE" and i.path == path for i in err.issues), err


def test_all_issues_are_reported_in_one_error() -> None:
    err = expect(
        "DUPLICATE_ID",
        buses=[slack("b1"), pq("b1"), pq("b2")],
        branches=[line("l1", "b1", "b2")],
        generators=[gen("g1", "b1", p_min_mw=50.0, p_max_mw=10.0)],
    )
    assert {"DUPLICATE_ID", "BAD_RANGE"} <= codes(err)
    text = str(err)
    assert "DUPLICATE_ID" in text and "BAD_RANGE" in text


def test_model_validate_json_raises_the_same_error() -> None:
    with pytest.raises(NetworkValidationError) as excinfo:
        Network.model_validate_json('{"base_mva": 100, "buses": []}')
    assert "NO_SLACK" in codes(excinfo.value)


# --- non-finite floats (critic issue 1) -----------------------------------------------------------


def test_nan_field_is_rejected_at_construction() -> None:
    with pytest.raises(ValidationError):
        Branch(id="l1", from_bus="b1", to_bus="b2", r=0.01, x=math.nan, b=0.0)


def test_inf_base_mva_is_rejected_at_construction() -> None:
    with pytest.raises(ValidationError):
        Network(base_mva=math.inf, buses=[slack("b1")])


@pytest.mark.parametrize(
    "document",
    [
        '{"base_mva": Infinity, "buses": [{"id": "b1", "base_kv": 110.0, "type": "slack"}]}',
        '{"base_mva": 100.0, "buses": [{"id": "b1", "base_kv": NaN, "type": "slack"}]}',
        (
            '{"base_mva": 100.0, "buses": [{"id": "b1", "base_kv": 110.0, "type": "slack"}],'
            ' "loads": [{"id": "d", "bus": "b1", "p_mw": -Infinity, "q_mvar": 0.0}]}'
        ),
    ],
)
def test_non_standard_json_tokens_are_rejected_not_coerced(document: str) -> None:
    # pydantic's JSON parser accepts NaN/Infinity tokens; allow_inf_nan=False must refuse them
    # rather than letting a non-finite value (or a null) into a float field.
    with pytest.raises(ValidationError):
        Network.model_validate_json(document)


# --- PiecewiseCost.points bound (review Security FLAG) --------------------------------------------
# Every breakpoint adds one epigraph row to opf.dc_opf's LP; jobs.run's opf.dc kind takes the
# network inline, so an unbounded points list is caller-reachable unbounded work.


def test_piecewise_cost_over_the_bound_is_rejected_at_construction() -> None:
    with pytest.raises(ValidationError):
        PiecewiseCost(points=[(float(i), float(i)) for i in range(201)])


def test_piecewise_cost_at_the_bound_is_accepted() -> None:
    cost = PiecewiseCost(points=[(float(i), float(i)) for i in range(200)])
    assert len(cost.points) == 200
