"""AC-5: ``opf.solve_dc_opf`` raises ``opf.NonConvexCostError`` for a non-convex ``PiecewiseCost``
generator, before any solve is attempted (spec design item 1 — checked in ``opf``'s own
cost-derivation step, not retroactively in ``model.PiecewiseCost``, per record/m3-research.md
§2.3 and the wave's own Not Doing list). ``PiecewiseCost`` itself accepts non-convex breakpoints
today (only strictly-increasing ``p_mw`` is validated at the model layer) — this guard is the
opf-local defense the research doc flagged as missing.
"""

from __future__ import annotations

import pytest

from mambo_power import opf
from mambo_power.model import Bus, Generator, Load, Network, PiecewiseCost, PolynomialCost


def _network_with_gen_cost(cost: PiecewiseCost | PolynomialCost) -> Network:
    return Network(
        base_mva=100.0,
        buses=[Bus(id="b1", base_kv=138.0, type="slack")],
        branches=[],
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
                cost=cost,
            ),
        ],
        loads=[Load(id="ld1", bus="b1", p_mw=40.0, q_mvar=0.0)],
    )


def test_solve_dc_opf_raises_nonconvexcosterror_for_non_convex_pwl_generator() -> None:
    # slopes 20, then 10: decreasing -> non-convex (module docstring)
    non_convex = PiecewiseCost(points=[(0.0, 0.0), (30.0, 600.0), (60.0, 900.0)])
    net = _network_with_gen_cost(non_convex)
    with pytest.raises(opf.NonConvexCostError, match="non-convex"):
        opf.solve_dc_opf(net)


def test_solve_dc_opf_accepts_convex_pwl_generator_and_solves() -> None:
    convex = PiecewiseCost(points=[(0.0, 0.0), (30.0, 600.0), (60.0, 1500.0), (100.0, 3000.0)])
    net = _network_with_gen_cost(convex)
    result = opf.solve_dc_opf(net)
    assert result.status == "Optimal"


def test_solve_dc_opf_still_solves_a_pure_polynomial_network_unaffected_by_the_guard() -> None:
    """The guard must not fire (or otherwise change behaviour) for a network with no piecewise
    cost at all — proves the new code path is additive."""
    net = _network_with_gen_cost(PolynomialCost(coefficients=[0.05, 22.0, 0.0]))
    result = opf.solve_dc_opf(net)
    assert result.status == "Optimal"
