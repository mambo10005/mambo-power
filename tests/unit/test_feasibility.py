"""``results.feasibility_report``: builds a ``FeasibilityReport`` from a solved AC state plus the
network it bounds (spec design item 6, W6). Exercised directly against real ``pf.solve_ac``
output, not a hand-built ``AcPowerFlowResult`` — the builder's own logic (violation detection,
converged/message passthrough) is what's under test, not ``solve_ac`` itself.
"""

from __future__ import annotations

from mambo_power.model import Branch, Bus, Generator, Load, Network, PolynomialCost
from mambo_power.pf import solve_ac
from mambo_power.results import FeasibilityReport, feasibility_report


def _net(
    *,
    x: float,
    r: float,
    p_mw: float,
    q_mvar: float,
    rating_mva: float | None,
    v_min_pu: float,
    v_max_pu: float,
) -> Network:
    return Network(
        base_mva=100.0,
        buses=[
            Bus(id="b1", base_kv=138.0, type="slack", v_min_pu=v_min_pu, v_max_pu=v_max_pu),
            Bus(id="b2", base_kv=138.0, type="pq", v_min_pu=v_min_pu, v_max_pu=v_max_pu),
        ],
        branches=[
            Branch(id="br1", from_bus="b1", to_bus="b2", r=r, x=x, b=0.0, rating_mva=rating_mva)
        ],
        generators=[
            Generator(
                id="g0",
                bus="b1",
                p_mw=p_mw,
                q_mvar=q_mvar,
                p_min_mw=0,
                p_max_mw=200,
                q_min_mvar=-200,
                q_max_mvar=200,
                v_set_pu=1.0,
                cost=PolynomialCost(coefficients=[10.0, 0.0]),
            ),
        ],
        loads=[Load(id="ld1", bus="b2", p_mw=p_mw, q_mvar=q_mvar)],
    )


def test_feasibility_report_catches_a_thermal_violation() -> None:
    # reactive-heavy load pushes apparent flow well past the branch's real-power-sized rating
    net = _net(x=0.05, r=0.01, p_mw=30.0, q_mvar=40.0, rating_mva=32.0, v_min_pu=0.9, v_max_pu=1.1)
    ac = solve_ac(net)
    assert ac.converged

    report = feasibility_report(ac, net)

    assert isinstance(report, FeasibilityReport)
    assert report.converged is True
    assert report.voltage_violations == []
    assert len(report.thermal_violations) == 1
    violation = report.thermal_violations[0]
    assert violation.branch_id == "br1"
    assert violation.limit_pct == 100.0
    assert violation.loading_pct > 100.0
    measured = next(b.loading_pct for b in ac.branches if b.id == "br1")
    assert violation.loading_pct == measured


def test_feasibility_report_catches_a_voltage_violation() -> None:
    # high reactance + sizeable load sags b2's voltage below v_min_pu; branch left unrated so
    # the thermal path stays isolated (an unrated branch never contributes a thermal violation)
    net = _net(x=0.3, r=0.03, p_mw=25.0, q_mvar=25.0, rating_mva=None, v_min_pu=0.95, v_max_pu=1.1)
    ac = solve_ac(net)
    assert ac.converged

    report = feasibility_report(ac, net)

    assert report.thermal_violations == []
    assert len(report.voltage_violations) == 1
    violation = report.voltage_violations[0]
    assert violation.bus_id == "b2"
    assert violation.limit_pu == 0.95
    assert violation.vm_pu < 0.95
    measured = next(b.vm_pu for b in ac.buses if b.id == "b2")
    assert violation.vm_pu == measured


def test_feasibility_report_clean_case_has_no_violations() -> None:
    net = _net(x=0.1, r=0.01, p_mw=10.0, q_mvar=5.0, rating_mva=50.0, v_min_pu=0.9, v_max_pu=1.1)
    ac = solve_ac(net)
    assert ac.converged

    report = feasibility_report(ac, net)

    assert report.converged is True
    assert report.thermal_violations == []
    assert report.voltage_violations == []


def test_feasibility_report_converged_and_message_pass_through_unchanged() -> None:
    # a network with contradictory generator bounds that Newton cannot converge on: an over-
    # loaded slack pinned far below what the load demands, driving the mismatch away from
    # tolerance within the iteration budget
    net = _net(x=0.6, r=0.05, p_mw=60.0, q_mvar=60.0, rating_mva=None, v_min_pu=0.5, v_max_pu=1.5)
    ac = solve_ac(net)
    assert ac.converged is False
    assert ac.message is not None

    report = feasibility_report(ac, net)

    assert report.converged is False
    assert report.message == ac.message
