"""Emergency ratings (ADR-020): a post-contingency flow is held to ``Branch.rating_emergency_mva``.

The hand case is ``tests/unit/test_opf_scopf.py``'s triangle — ``br13`` rated 60 MVA, the plain
OPF's 90 MW on ``g1``, and the ``br12`` outage putting ``90 − x`` on ``br13`` for ``g3 = x``.
With an emergency rating ``E`` on ``br13`` that outage needs ``90 − x <= E``: at ``E = 90`` the
plain OPF is already secure (cost 900, no row added); at ``E = 75`` the secure dispatch is
``x = 15``, cost ``10·75 + 20·15 = 1050``, between the plain 900 and the normal-rating 1200. The
base case still sees the normal rating: no base-case solve reads the emergency one.
"""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from mambo_power import cases
from mambo_power.contingency import n1
from mambo_power.contingency.n1 import N1Options
from mambo_power.io import csv_bundle, matpower
from mambo_power.model import Branch, Bus, Generator, Load, Network, PolynomialCost
from mambo_power.model.network import validate_network
from mambo_power.numerics import NetworkArrays
from mambo_power.opf import solve_dc_opf, solve_scopf


def _gen(gen_id: str, bus: str, marginal_cost: float) -> Generator:
    return Generator(
        id=gen_id,
        bus=bus,
        p_mw=0.0,
        q_mvar=0.0,
        p_min_mw=0.0,
        p_max_mw=200.0,
        q_min_mvar=0.0,
        q_max_mvar=0.0,
        v_set_pu=1.0,
        cost=PolynomialCost(coefficients=[marginal_cost, 0.0]),
    )


def _triangle(br13_emergency: float | None) -> Network:
    return Network(
        base_mva=100.0,
        buses=[
            Bus(id="b1", base_kv=138.0, type="slack"),
            Bus(id="b2", base_kv=138.0, type="pq"),
            Bus(id="b3", base_kv=138.0, type="pv"),
        ],
        branches=[
            Branch(id="br12", from_bus="b1", to_bus="b2", r=0.0, x=0.1, b=0.0, rating_mva=100.0),
            Branch(
                id="br13",
                from_bus="b1",
                to_bus="b3",
                r=0.0,
                x=0.1,
                b=0.0,
                rating_mva=60.0,
                rating_emergency_mva=br13_emergency,
            ),
            Branch(id="br23", from_bus="b2", to_bus="b3", r=0.0, x=0.1, b=0.0, rating_mva=100.0),
        ],
        generators=[_gen("g1", "b1", 10.0), _gen("g3", "b3", 20.0)],
        loads=[Load(id="ld2", bus="b2", p_mw=90.0, q_mvar=0.0)],
    )


def test_arrays_carry_the_emergency_rating_and_fall_back_to_the_normal_one() -> None:
    arr = NetworkArrays.from_network(_triangle(75.0))
    assert arr.rating_pu.tolist() == [1.0, 0.6, 1.0]
    assert arr.rating_emergency_pu.tolist() == [1.0, 0.75, 1.0]
    plain = NetworkArrays.from_network(_triangle(None))
    assert plain.rating_emergency_pu.tolist() == plain.rating_pu.tolist()


def test_n1_holds_post_contingency_flows_to_the_emergency_rating() -> None:
    normal = n1(_triangle(None), N1Options(generator_outages=False))
    relaxed = n1(_triangle(90.0), N1Options(generator_outages=False))

    br12_out = next(o for o in normal.outages if o.outage_branch_id == "br12")
    flag = next(f for f in br12_out.flagged_branches if f.branch_id == "br13")
    assert flag.confirmed_violating and flag.confirmed_flow_mw == pytest.approx(90.0)
    assert flag.rating_mva == 60.0
    # 90 MW on br13 after the br12 outage is inside the 90 MVA emergency rating
    assert relaxed.outages == []


def test_scopf_secures_against_the_emergency_rating_and_the_base_case_against_the_normal() -> None:
    plain = solve_dc_opf(_triangle(None))
    strict = solve_scopf(_triangle(None))
    relaxed = solve_scopf(_triangle(90.0))
    partial = solve_scopf(_triangle(75.0))

    assert plain.objective_cost == pytest.approx(900.0)
    assert strict.objective_cost == pytest.approx(1200.0)
    assert relaxed.status == "Optimal" and relaxed.secure
    assert relaxed.objective_cost == pytest.approx(900.0)
    assert relaxed.constraints == []
    assert partial.status == "Optimal" and partial.secure
    assert partial.objective_cost == pytest.approx(1050.0)
    assert {g.id: g.p_mw for g in partial.generators} == pytest.approx({"g1": 75.0, "g3": 15.0})
    (row,) = partial.constraints
    assert (row.outage_id, row.branch_id) == ("br12", "br13")
    assert abs(row.post_contingency_flow_mw) == pytest.approx(75.0)
    assert row.rating_mva == 75.0
    # the base case is unchanged by the emergency rating: the same LP, the same cost
    assert solve_dc_opf(_triangle(75.0)).objective_cost == pytest.approx(900.0)


def test_case14_rated_is_cheaper_to_secure_with_emergency_headroom() -> None:
    net = cases.load("derived/case14_rated")
    headroom = net.model_copy(deep=True)
    for br in headroom.branches:
        if br.rating_mva is not None:
            br.rating_emergency_mva = 1.3 * br.rating_mva

    strict = solve_scopf(net)
    relaxed = solve_scopf(headroom)

    assert strict.status == relaxed.status == "Optimal"
    assert strict.secure and relaxed.secure
    assert relaxed.base_objective_cost == pytest.approx(strict.base_objective_cost)
    assert strict.base_objective_cost < relaxed.objective_cost < strict.objective_cost


def test_validation_requires_a_normal_rating_the_emergency_one_is_not_below() -> None:
    net = _triangle(None)
    br13 = net.branches[1]
    br13.rating_emergency_mva = 50.0
    (issue,) = [i for i in validate_network(net) if i.code == "BAD_RANGE"]
    assert "rating_emergency_mva 50.0" in issue.message
    br13.rating_emergency_mva = 60.0
    assert [i for i in validate_network(net) if i.code == "BAD_RANGE"] == []
    br13.rating_mva = None
    (issue,) = [i for i in validate_network(net) if i.code == "BAD_RANGE"]
    assert issue.path == "branches[1].rating_emergency_mva"


def test_matpower_rate_c_becomes_the_emergency_rating_only_where_it_exceeds_rate_a() -> None:
    def case(rate_a: float, rate_c: float) -> str:
        return (
            "function mpc = t\nmpc.version = '2';\nmpc.baseMVA = 100;\n"
            "mpc.bus = [\n1 3 0 0 0 0 1 1 0 110 1 1.1 0.9;\n"
            "2 1 50 10 0 0 1 1 0 110 1 1.1 0.9;\n];\n"
            "mpc.gen = [\n1 60 5 100 -100 1.02 100 1 200 0;\n];\n"
            f"mpc.branch = [\n1 2 0.01 0.1 0.02 {rate_a} 0 {rate_c} 0 0 1;\n];\n"
            "mpc.gencost = [\n2 0 0 2 10 0;\n];\n"
        )

    (br,) = matpower.loads(case(150, 180)).branches
    assert (br.rating_mva, br.rating_emergency_mva) == (150.0, 180.0)
    (br,) = matpower.loads(case(150, 150)).branches
    assert (br.rating_mva, br.rating_emergency_mva) == (150.0, None)
    (br,) = matpower.loads(case(0, 180)).branches
    assert (br.rating_mva, br.rating_emergency_mva) == (None, None)
    # every bundled case reads as before: none states an emergency rating above its normal one
    for name in cases.available():
        if name.endswith(".raw"):
            continue
        assert all(br.rating_emergency_mva is None for br in cases.load(name).branches), name


def test_emergency_rating_round_trips_through_json_and_the_csv_bundle() -> None:
    net = _triangle(75.0)
    assert Network.model_validate_json(net.model_dump_json()) == net
    with tempfile.TemporaryDirectory() as tmp:
        csv_bundle.dump(net, Path(tmp))
        back = csv_bundle.load(Path(tmp))
    assert back.branches == net.branches
