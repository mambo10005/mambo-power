"""Wiring tests for :mod:`mambo_power.contingency` and AC-4's behavioral half (W5).

``_triangle_network`` is a 3-bus/3-branch mesh with equal reactances, so none of its branches
are bridges (removing any one edge still leaves the other two connecting all three buses) and
its DC flow divides exactly 2/3 direct, 1/3 indirect (a 90 MW load at bus2, slack at bus1: the
direct branch ``br12`` carries 60 MW, the indirect legs ``br13``/``br23`` 30 MW each — the
resistor-delta current-divider identity for equal branch impedances). Removing either indirect
leg forces the *entire* 90 MW onto ``br12``, which is exactly what a rating of 70 MVA is chosen
to violate (60 MW base flow does not; 90 MW does) — a hand case whose LODF-estimated and
DC-re-solve-confirmed flows are provably identical (DC power flow is linear, so a single-outage
LODF estimate is not an approximation of the re-solve, it is the same linear system evaluated
two ways), giving deterministic numbers to assert on rather than only "some number changed".

``_radial_network`` is a plain 3-bus chain (both branches are bridges) — nothing in it is ever
screened; it proves the bridge-skip path.

AC-4's behavioral half (the fixture half was S1's job, see ``tests/unit/test_rated_helper.py``)
closes the loop on real multi-bus data: ``tests._rated.rated_network(case14)`` — S1's own
LODF-only sanity sweep already found 17 outages / 81 outage-branch pairs at this margin
(``m3-s1-report.md``) — must have at least one of those pairs come back ``confirmed_violating``
from an *actual* DC re-solve, not just the LODF estimate.
"""

from __future__ import annotations

import pytest

from mambo_power.contingency import N1Options, n1
from mambo_power.contingency.n1 import confirm_n1, screen_n1
from mambo_power.io.matpower import load
from mambo_power.model import Branch, Bus, Generator, Load, Network
from mambo_power.numerics import NetworkArrays, bridges
from mambo_power.results import N1Result
from tests._fixtures import FIXTURES_DIR
from tests._rated import rated_network


def _triangle_network(*, br12_rating: float | None = 70.0) -> Network:
    return Network(
        base_mva=100.0,
        buses=[
            Bus(id="b1", base_kv=138.0, type="slack"),
            Bus(id="b2", base_kv=138.0, type="pq"),
            Bus(id="b3", base_kv=138.0, type="pq"),
        ],
        branches=[
            Branch(
                id="br12", from_bus="b1", to_bus="b2", r=0.0, x=0.1, b=0.0, rating_mva=br12_rating
            ),
            Branch(id="br13", from_bus="b1", to_bus="b3", r=0.0, x=0.1, b=0.0),
            Branch(id="br23", from_bus="b2", to_bus="b3", r=0.0, x=0.1, b=0.0),
        ],
        generators=[
            Generator(
                id="g1",
                bus="b1",
                p_mw=0.0,
                q_mvar=0.0,
                p_min_mw=0.0,
                p_max_mw=200.0,
                q_min_mvar=0.0,
                q_max_mvar=0.0,
                v_set_pu=1.0,
            ),
        ],
        loads=[Load(id="ld2", bus="b2", p_mw=90.0, q_mvar=0.0)],
    )


def _radial_network() -> Network:
    return Network(
        base_mva=100.0,
        buses=[
            Bus(id="b1", base_kv=138.0, type="slack"),
            Bus(id="b2", base_kv=138.0, type="pq"),
            Bus(id="b3", base_kv=138.0, type="pq"),
        ],
        branches=[
            Branch(id="br12", from_bus="b1", to_bus="b2", r=0.0, x=0.1, b=0.0, rating_mva=1.0),
            Branch(id="br23", from_bus="b2", to_bus="b3", r=0.0, x=0.1, b=0.0, rating_mva=1.0),
        ],
        generators=[
            Generator(
                id="g1",
                bus="b1",
                p_mw=0.0,
                q_mvar=0.0,
                p_min_mw=0.0,
                p_max_mw=200.0,
                q_min_mvar=0.0,
                q_max_mvar=0.0,
                v_set_pu=1.0,
            ),
        ],
        loads=[Load(id="ld3", bus="b3", p_mw=10.0, q_mvar=0.0)],
    )


# --- screen_n1 (array-level LODF fast screen) -----------------------------------------------


def test_screen_n1_flags_the_direct_branch_when_either_indirect_leg_is_outaged() -> None:
    net = _triangle_network()
    arr = NetworkArrays.from_network(net)
    assert bridges(arr) == []

    screen = screen_n1(arr, N1Options())

    br12, br13, br23 = arr.branch_index["br12"], arr.branch_index["br13"], arr.branch_index["br23"]
    assert set(screen.flagged_positions) == {br13, br23}
    assert screen.flagged_positions[br13] == [br12]
    assert screen.flagged_positions[br23] == [br12]
    assert screen.estimated_flow_mw[br13][br12] == pytest.approx(90.0)
    assert screen.estimated_flow_mw[br23][br12] == pytest.approx(90.0)
    assert screen.bridge_positions == []


def test_screen_n1_flags_nothing_when_the_direct_branch_is_unrated() -> None:
    net = _triangle_network(br12_rating=None)
    arr = NetworkArrays.from_network(net)

    screen = screen_n1(arr, N1Options())

    assert screen.flagged_positions == {}


def test_screen_n1_skips_bridge_outages() -> None:
    net = _radial_network()
    arr = NetworkArrays.from_network(net)
    assert len(bridges(arr)) == 2

    screen = screen_n1(arr, N1Options())

    assert screen.flagged_positions == {}
    assert sorted(screen.bridge_positions) == sorted(bridges(arr))


# --- confirm_n1 (network-level confirming re-solve) -----------------------------------------


def test_confirm_n1_confirms_the_screened_violation_with_the_exact_resolved_flow() -> None:
    net = _triangle_network()
    arr = NetworkArrays.from_network(net)
    screen = screen_n1(arr, N1Options())

    outages = confirm_n1(net, arr, screen)

    by_outage = {o.outage_branch_id: o for o in outages}
    assert set(by_outage) == {"br13", "br23"}
    for outage in by_outage.values():
        assert outage.confirmed_violating is True
        assert len(outage.flagged_branches) == 1
        flag = outage.flagged_branches[0]
        assert flag.branch_id == "br12"
        assert flag.rating_mva == pytest.approx(70.0)
        assert flag.estimated_flow_mw == pytest.approx(90.0)
        assert flag.confirmed_flow_mw == pytest.approx(90.0)
        assert flag.confirmed_violating is True


# --- n1 (public, network-level entry point) -------------------------------------------------


def test_n1_public_entry_point_returns_an_n1_result() -> None:
    net = _triangle_network()

    result = n1(net)

    assert isinstance(result, N1Result)
    assert result.provenance.kind == "n1"
    assert {o.outage_branch_id for o in result.outages} == {"br13", "br23"}
    assert all(o.confirmed_violating for o in result.outages)
    assert result.bridge_branch_ids == []


def test_n1_accepts_explicit_options() -> None:
    net = _triangle_network()
    result = n1(net, N1Options())
    assert {o.outage_branch_id for o in result.outages} == {"br13", "br23"}


def test_n1_reports_bridge_branch_ids_and_flags_no_bridge_outage() -> None:
    net = _radial_network()

    result = n1(net)

    assert result.outages == []
    assert sorted(result.bridge_branch_ids) == ["br12", "br23"]


def test_n1_does_not_mutate_the_input_network() -> None:
    net = _triangle_network()
    before = [(br.id, br.in_service) for br in net.branches]
    n1(net)
    after = [(br.id, br.in_service) for br in net.branches]
    assert before == after


# --- AC-4 behavioral half: real N-1 violation confirmed on real multi-bus data --------------


def test_ac4_behavioral_case14_has_a_confirmed_n1_violation() -> None:
    net = load(FIXTURES_DIR / "case14.m")
    rated = rated_network(net)

    result = n1(rated)

    confirmed = [o for o in result.outages if o.confirmed_violating]
    assert confirmed, "expected at least one confirmed N-1 violation on rated case14"
    for outage in confirmed:
        assert any(f.confirmed_violating for f in outage.flagged_branches)
