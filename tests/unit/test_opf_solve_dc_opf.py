"""``opf.solve_dc_opf``: the Network-facing wrapper around ``opf.dc_opf`` (spec design item 1).

Cost extraction from ``Generator.cost``, ``OpfDcResult`` construction (id-keyed dispatch/LMP/
flows + provenance), the PiecewiseCost seam, and the free-generator (no cost) convention.
"""

from __future__ import annotations

import pytest

from mambo_power.model import Branch, Bus, Generator, Load, Network, PiecewiseCost, PolynomialCost
from mambo_power.opf import solve_dc_opf
from mambo_power.opf.dc_opf import OpfDcOptions
from mambo_power.pf import solve_ac
from mambo_power.results import OpfDcResult


def _net(cost0: PolynomialCost | None, cost1: PolynomialCost | None) -> Network:
    return Network(
        base_mva=100.0,
        buses=[
            Bus(id="b1", base_kv=138.0, type="slack"),
            Bus(id="b2", base_kv=138.0, type="pq"),
        ],
        branches=[Branch(id="br1", from_bus="b1", to_bus="b2", r=0.0, x=0.1, b=0.0)],
        generators=[
            Generator(
                id="g0",
                bus="b1",
                p_mw=0,
                q_mvar=0,
                p_min_mw=0,
                p_max_mw=100,
                q_min_mvar=0,
                q_max_mvar=0,
                v_set_pu=1.0,
                cost=cost0,
            ),
            Generator(
                id="g1",
                bus="b2",
                p_mw=0,
                q_mvar=0,
                p_min_mw=0,
                p_max_mw=100,
                q_min_mvar=0,
                q_max_mvar=0,
                v_set_pu=1.0,
                cost=cost1,
            ),
        ],
        loads=[Load(id="ld1", bus="b2", p_mw=40.0, q_mvar=0.0)],
    )


def test_solve_dc_opf_wires_dispatch_lmp_flows_and_provenance() -> None:
    net = _net(
        PolynomialCost(coefficients=[10.0, 0.0]),  # c1=10, c0=0
        PolynomialCost(coefficients=[20.0, 0.0]),  # c1=20, c0=0 (more expensive)
    )
    result = solve_dc_opf(net, OpfDcOptions())

    assert isinstance(result, OpfDcResult)
    assert result.status == "Optimal"
    assert result.message is None
    assert result.provenance.kind == "opf.dc"
    assert result.provenance.solver == "highspy.Highs"

    by_id = {g.id: g for g in result.generators}
    assert set(by_id) == {"g0", "g1"}
    # cheaper generator (g0) should absorb all 40 MW of load; g1 stays at 0
    assert by_id["g0"].p_mw == pytest.approx(40.0, abs=1e-6)
    assert by_id["g1"].p_mw == pytest.approx(0.0, abs=1e-6)
    assert result.balance_dual == pytest.approx(10.0, abs=1e-6)
    assert result.objective_cost == pytest.approx(400.0, abs=1e-6)

    bus_ids = {b.id for b in result.buses}
    assert bus_ids == {"b1", "b2"}
    branch_ids = {b.id for b in result.branches}
    assert branch_ids == {"br1"}
    assert result.ac_check is None


def test_solve_dc_opf_treats_a_costless_generator_as_free() -> None:
    net = _net(None, PolynomialCost(coefficients=[20.0, 0.0]))
    result = solve_dc_opf(net, OpfDcOptions())
    assert result.status == "Optimal"
    by_id = {g.id: g for g in result.generators}
    assert by_id["g0"].p_mw == pytest.approx(40.0, abs=1e-6)  # free generator takes it all


def test_solve_dc_opf_solves_a_piecewise_cost_generator() -> None:
    """Wave M3 slice S3 replaced the ``NotImplementedError`` seam S2 left here (this test used
    to assert that seam) with the real convex segment/epigraph LP encoding — see
    ``tests/unit/test_opf_dc_pwl.py``/``test_opf_dc_case14_pwl.py`` for the encoding's own
    correctness proof; this test only confirms ``solve_dc_opf``'s wiring reaches it (g0's PWL
    curve, $10/MWh up to 20 MW then $30/MWh after, is cheaper than g1's flat $20/MWh only for the
    first 20 MW of the 40 MW load, so g0 should take exactly 20 MW and g1 the remaining 20)."""
    net = _net(
        PiecewiseCost(points=[(0.0, 0.0), (20.0, 200.0), (40.0, 800.0)]),  # slopes 10, 30
        PolynomialCost(coefficients=[20.0, 0.0]),
    )
    result = solve_dc_opf(net, OpfDcOptions())
    assert result.status == "Optimal"
    by_id = {g.id: g for g in result.generators}
    assert by_id["g0"].p_mw == pytest.approx(20.0, abs=1e-6)
    assert by_id["g1"].p_mw == pytest.approx(20.0, abs=1e-6)
    assert result.objective_cost == pytest.approx(200.0 + 20.0 * 20.0, abs=1e-4)


def test_solve_dc_opf_defaults_options_when_none_given() -> None:
    net = _net(PolynomialCost(coefficients=[10.0, 0.0]), PolynomialCost(coefficients=[20.0, 0.0]))
    result = solve_dc_opf(net)
    assert result.status == "Optimal"


def test_solve_dc_opf_ac_check_defaults_to_off() -> None:
    net = _net(PolynomialCost(coefficients=[10.0, 0.0]), PolynomialCost(coefficients=[20.0, 0.0]))
    assert solve_dc_opf(net, OpfDcOptions()).ac_check is None
    assert solve_dc_opf(net).ac_check is None


def _ac_check_net(
    *, x: float, r: float, p_mw: float, q_mvar: float, rating_mva: float | None, v_min_pu: float
) -> Network:
    """Single slack generator serving a single PQ load — trivial, deterministic dispatch (the
    only generator must supply exactly the load) so the AC-solved state is fully controlled by
    ``p_mw``/``q_mvar``/``x``/``r``, mirroring ``tests/unit/test_feasibility.py``'s helper.
    """
    return Network(
        base_mva=100.0,
        buses=[
            Bus(id="b1", base_kv=138.0, type="slack", v_min_pu=v_min_pu, v_max_pu=1.1),
            Bus(id="b2", base_kv=138.0, type="pq", v_min_pu=v_min_pu, v_max_pu=1.1),
        ],
        branches=[
            Branch(id="br1", from_bus="b1", to_bus="b2", r=r, x=x, b=0.0, rating_mva=rating_mva)
        ],
        generators=[
            Generator(
                id="g0",
                bus="b1",
                p_mw=0,
                q_mvar=0,
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


def test_solve_dc_opf_ac_check_catches_a_thermal_violation() -> None:
    net = _ac_check_net(x=0.05, r=0.01, p_mw=30.0, q_mvar=40.0, rating_mva=32.0, v_min_pu=0.9)
    result = solve_dc_opf(net, OpfDcOptions(ac_check=True))

    assert result.status == "Optimal"
    assert result.ac_check is not None
    assert result.ac_check.converged is True
    assert result.ac_check.voltage_violations == []
    assert len(result.ac_check.thermal_violations) == 1
    assert result.ac_check.thermal_violations[0].branch_id == "br1"
    assert result.ac_check.thermal_violations[0].loading_pct > 100.0


def test_solve_dc_opf_ac_check_catches_a_voltage_violation() -> None:
    net = _ac_check_net(x=0.3, r=0.03, p_mw=25.0, q_mvar=25.0, rating_mva=None, v_min_pu=0.95)
    result = solve_dc_opf(net, OpfDcOptions(ac_check=True))

    assert result.status == "Optimal"
    assert result.ac_check is not None
    assert result.ac_check.thermal_violations == []
    assert len(result.ac_check.voltage_violations) == 1
    assert result.ac_check.voltage_violations[0].bus_id == "b2"
    assert result.ac_check.voltage_violations[0].vm_pu < 0.95


def test_solve_dc_opf_ac_check_clean_case_has_no_violations() -> None:
    net = _ac_check_net(x=0.1, r=0.01, p_mw=10.0, q_mvar=5.0, rating_mva=50.0, v_min_pu=0.9)
    result = solve_dc_opf(net, OpfDcOptions(ac_check=True))

    assert result.ac_check is not None
    assert result.ac_check.converged is True
    assert result.ac_check.thermal_violations == []
    assert result.ac_check.voltage_violations == []


def test_solve_dc_opf_ac_check_converged_matches_solve_ac_on_the_same_dispatch() -> None:
    net = _ac_check_net(x=0.1, r=0.01, p_mw=10.0, q_mvar=5.0, rating_mva=50.0, v_min_pu=0.9)
    result = solve_dc_opf(net, OpfDcOptions(ac_check=True))
    assert result.ac_check is not None

    dispatched = net.model_copy(deep=True)
    by_id = {g.id: g for g in dispatched.generators}
    for row in result.generators:
        by_id[row.id].p_mw = row.p_mw
    direct = solve_ac(dispatched)

    assert result.ac_check.converged == direct.converged
    assert result.ac_check.message == direct.message
