"""``opf.solve_dc_opf``: the Network-facing wrapper around ``opf.dc_opf`` (spec design item 1).

Cost extraction from ``Generator.cost``, ``OpfDcResult`` construction (id-keyed dispatch/LMP/
flows + provenance), the PiecewiseCost seam, and the free-generator (no cost) convention.
"""

from __future__ import annotations

import pytest

from mambo_power.model import Branch, Bus, Generator, Load, Network, PiecewiseCost, PolynomialCost
from mambo_power.opf import solve_dc_opf
from mambo_power.opf.dc_opf import OpfDcOptions
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


def test_solve_dc_opf_raises_not_implemented_for_piecewise_cost() -> None:
    net = _net(
        PiecewiseCost(points=[(0.0, 0.0), (40.0, 400.0)]),
        PolynomialCost(coefficients=[20.0, 0.0]),
    )
    with pytest.raises(NotImplementedError, match="piecewise"):
        solve_dc_opf(net, OpfDcOptions())


def test_solve_dc_opf_defaults_options_when_none_given() -> None:
    net = _net(PolynomialCost(coefficients=[10.0, 0.0]), PolynomialCost(coefficients=[20.0, 0.0]))
    result = solve_dc_opf(net)
    assert result.status == "Optimal"
