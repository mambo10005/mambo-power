"""Generator-outage contingencies in :mod:`mambo_power.contingency` (ADR-015).

``_two_generator_triangle`` is ``test_contingency_n1.py``'s 3-bus equal-reactance mesh (slack
``g1`` at ``b1``, a 90 MW load at ``b2``) plus a 60 MW generator ``g3`` at ``b3``. With ``g3``
in service the two injections superpose: the load alone puts 60 MW on the direct branch
``br12`` and 30 MW on each indirect leg; ``g3``'s 60 MW flowing back to the slack at ``b1``
puts 40 MW on ``br13`` and 20 MW on the ``b3 -> b2 -> b1`` path, *against* the load's flow on
``br12``. Base case, in each branch's from->to sign: ``br12 = +40``, ``br13 = -10``,
``br23 = -50`` MW. Losing ``g3`` leaves the plain single-source triangle — ``br12 = 60``,
``br13 = 30``, ``br23 = -30`` — so a 50 MVA rating on ``br12`` holds in the base case (40) and
breaks on the outage (60), while a 55 MVA rating on ``br23`` holds in both (50, then 30).
DC power flow is linear, so the PTDF estimate and the re-solve are the same system evaluated two
ways and the numbers can be asserted exactly, as the branch tests do.

The brute-force half re-solves every non-slack generator outage of the five rated OPF fixtures
with no screen at all and demands the confirmed-violating set match — the generator analogue of
``test_contingency_n1_brute_force.py``'s agreement guarantee.
"""

from __future__ import annotations

import pytest

from mambo_power.contingency import N1Options, n1
from mambo_power.contingency.n1 import confirm_n1_generators, screen_n1
from mambo_power.io.matpower import load
from mambo_power.jobs import SolveRequest, run
from mambo_power.model import Branch, Bus, Generator, Load, Network
from mambo_power.numerics import NetworkArrays
from mambo_power.results import N1GeneratorOutageResult, N1Result
from tests._brute_force_n1 import brute_force_n1_generators
from tests._fixtures import FIXTURES_DIR
from tests._rated import rated_network

OPF_FIXTURES = ["case14", "case_ieee30", "case57", "case118", "case300"]


def _gen(gen_id: str, bus: str, p_mw: float) -> Generator:
    return Generator(
        id=gen_id,
        bus=bus,
        p_mw=p_mw,
        q_mvar=0.0,
        p_min_mw=0.0,
        p_max_mw=200.0,
        q_min_mvar=0.0,
        q_max_mvar=0.0,
        v_set_pu=1.0,
    )


def _two_generator_triangle(
    *, br12_rating: float | None = 50.0, br23_rating: float | None = 55.0
) -> Network:
    return Network(
        base_mva=100.0,
        buses=[
            Bus(id="b1", base_kv=138.0, type="slack"),
            Bus(id="b2", base_kv=138.0, type="pq"),
            Bus(id="b3", base_kv=138.0, type="pv"),
        ],
        branches=[
            Branch(
                id="br12", from_bus="b1", to_bus="b2", r=0.0, x=0.1, b=0.0, rating_mva=br12_rating
            ),
            Branch(id="br13", from_bus="b1", to_bus="b3", r=0.0, x=0.1, b=0.0),
            Branch(
                id="br23", from_bus="b2", to_bus="b3", r=0.0, x=0.1, b=0.0, rating_mva=br23_rating
            ),
        ],
        generators=[_gen("g1", "b1", 30.0), _gen("g3", "b3", 60.0)],
        loads=[Load(id="ld2", bus="b2", p_mw=90.0, q_mvar=0.0)],
    )


# --- screen_n1 (array-level PTDF fast screen) ------------------------------------------------


def test_screen_flags_the_remote_generator_and_skips_the_slack_one() -> None:
    net = _two_generator_triangle()
    arr = NetworkArrays.from_network(net)

    screen = screen_n1(arr, N1Options())

    g1, g3 = arr.gen_ids.index("g1"), arr.gen_ids.index("g3")
    br12, br23 = arr.branch_index["br12"], arr.branch_index["br23"]
    assert screen.gen_slack_positions == [g1]
    assert set(screen.gen_flagged_positions) == {g3}
    assert screen.gen_flagged_positions[g3] == [br12]
    assert screen.gen_lost_p_mw == {g3: pytest.approx(60.0)}
    assert screen.gen_estimated_flow_mw[g3][br12] == pytest.approx(60.0)
    assert screen.gen_estimated_flow_mw[g3][br23] == pytest.approx(30.0)
    # The branch half is untouched by the generator sweep.
    without = screen_n1(arr, N1Options(generator_outages=False))
    assert screen.flagged_positions == without.flagged_positions
    assert screen.bridge_positions == without.bridge_positions


def test_screen_flags_no_generator_when_the_direct_branch_is_unrated() -> None:
    net = _two_generator_triangle(br12_rating=None)
    arr = NetworkArrays.from_network(net)

    screen = screen_n1(arr, N1Options())

    assert screen.gen_flagged_positions == {}
    assert screen.gen_estimated_flow_mw == {}
    assert len(screen.gen_lost_p_mw) == 1


def test_screen_skips_generators_entirely_when_the_option_is_off() -> None:
    net = _two_generator_triangle()
    arr = NetworkArrays.from_network(net)

    screen = screen_n1(arr, N1Options(generator_outages=False))

    assert screen.gen_flagged_positions == {}
    assert screen.gen_estimated_flow_mw == {}
    assert screen.gen_slack_positions == []
    assert screen.gen_lost_p_mw == {}


# --- confirm_n1_generators (confirming DC re-solve) ------------------------------------------


def test_confirm_reports_estimate_and_re_solve_side_by_side() -> None:
    net = _two_generator_triangle()
    arr = NetworkArrays.from_network(net)
    screen = screen_n1(arr, N1Options())

    outages = confirm_n1_generators(net, arr, screen)

    assert len(outages) == 1
    (outage,) = outages
    assert isinstance(outage, N1GeneratorOutageResult)
    assert outage.outage_generator_id == "g3"
    assert outage.lost_p_mw == pytest.approx(60.0)
    assert outage.confirmed_violating is True
    (flag,) = outage.flagged_branches
    assert flag.branch_id == "br12"
    assert flag.rating_mva == pytest.approx(50.0)
    assert flag.estimated_flow_mw == pytest.approx(60.0)
    assert flag.confirmed_flow_mw == pytest.approx(60.0)
    assert flag.confirmed_violating is True
    # The confirming re-solve ran on a copy: the network still has g3 in service.
    assert all(gen.in_service for gen in net.generators)


# --- contingency.n1 (network-level) ----------------------------------------------------------


def test_n1_carries_generator_outages_and_slack_generator_ids() -> None:
    result = n1(_two_generator_triangle())

    assert isinstance(result, N1Result)
    assert result.slack_generator_ids == ["g1"]
    assert [o.outage_generator_id for o in result.generator_outages] == ["g3"]
    assert result.generator_outages[0].confirmed_violating is True
    assert result.provenance.options == {"generator_outages": True}


def test_n1_with_generator_outages_off_leaves_both_generator_fields_empty() -> None:
    result = n1(_two_generator_triangle(), N1Options(generator_outages=False))

    assert result.generator_outages == []
    assert result.slack_generator_ids == []
    assert result.provenance.options == {"generator_outages": False}


def test_n1_result_round_trips_through_json_and_accepts_the_pre_adr_015_shape() -> None:
    result = n1(_two_generator_triangle())

    again = N1Result.model_validate_json(result.model_dump_json())
    assert again == result

    legacy = result.model_dump(mode="json")
    del legacy["generator_outages"]
    del legacy["slack_generator_ids"]
    old = N1Result.model_validate(legacy)
    assert old.generator_outages == []
    assert old.slack_generator_ids == []


def test_jobs_n1_kind_accepts_the_generator_outages_option() -> None:
    net = _two_generator_triangle()

    on = run(SolveRequest(kind="n1", network=net))
    off = run(SolveRequest(kind="n1", network=net, options={"generator_outages": False}))

    assert on.status == "ok" and isinstance(on.result, N1Result)
    assert [o.outage_generator_id for o in on.result.generator_outages] == ["g3"]
    assert off.status == "ok" and isinstance(off.result, N1Result)
    assert off.result.generator_outages == []


# --- the agreement guarantee, generator edition ----------------------------------------------


@pytest.mark.parametrize("name", OPF_FIXTURES)
def test_screen_then_confirm_agrees_with_brute_force_for_generators(name: str) -> None:
    net = rated_network(load(FIXTURES_DIR / f"{name}.m"))
    arr = NetworkArrays.from_network(net)

    result = n1(net)
    screened = {o.outage_generator_id for o in result.generator_outages if o.confirmed_violating}
    brute = brute_force_n1_generators(net, arr)

    assert screened == brute
    # Every generator is accounted for exactly once: screened, or skipped as a slack generator.
    slack_bus = net.buses[arr.slack].id
    assert result.slack_generator_ids == [
        gen.id for gen in net.generators if gen.in_service and gen.bus == slack_bus
    ]
    assert set(result.slack_generator_ids).isdisjoint(
        {o.outage_generator_id for o in result.generator_outages}
    )
