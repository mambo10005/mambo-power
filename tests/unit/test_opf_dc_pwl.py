"""AC-5 (array level): ``dc_opf``'s convex segment/epigraph LP encoding for PWL generator costs
(spec design item 4, research §2.1), and the ``NonConvexCostError`` pre-solve guard.

Hand-built 1-bus, 2-generator, branch-less network (no PTDF/flow-limit interaction to worry
about — isolates the PWL row-building itself, mirroring ``test_opf_dc.py``'s "prove the wiring,
not the whole pipeline" discipline): ``g0`` is a flat linear generator (``$22/MWh``, cheap
enough to relieve the PWL generator's own costlier upper segments but not its cheap first
segment), ``g1`` is convex PWL with breakpoints ``(0,0), (30,600), (60,1500), (100,3000)``
(segment slopes 20, 30, 37.5 $/MWh, strictly increasing). At a 40 MW load, the merit order is:
``g1``'s first segment (20 $/MWh) is cheaper than ``g0`` (22 $/MWh) — take all 30 MW of it; the
remaining 10 MW is cheaper from ``g0`` (22 $/MWh) than from ``g1``'s second segment (30 $/MWh),
so ``g0`` supplies it and ``g1`` stops exactly at its first breakpoint. Expected optimum
(hand-derived, not from ``dc_opf``): ``g0 = 10 MW``, ``g1 = 30 MW``, cost ``22*10 + 600 = 820``
(``g1``'s cost at ``p=30`` is exactly the second breakpoint's own tabulated value — no partial
interpolation needed to state the expected number).
"""

from __future__ import annotations

import numpy as np
import pytest

from mambo_power.model import Bus, Generator, Load, Network, PiecewiseCost, PolynomialCost
from mambo_power.numerics.arrays import NetworkArrays
from mambo_power.opf.dc_opf import NonConvexCostError, OpfDcOptions, dc_opf

G1_POINTS = [(0.0, 0.0), (30.0, 600.0), (60.0, 1500.0), (100.0, 3000.0)]


def _one_bus_network(g1_points: list[tuple[float, float]]) -> Network:
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
                cost=PolynomialCost(coefficients=[22.0, 0.0]),
            ),
            Generator(
                id="g1",
                bus="b1",
                p_mw=0,
                q_mvar=0,
                p_min_mw=0,
                p_max_mw=100,
                q_min_mvar=0,
                q_max_mvar=0,
                v_set_pu=1.0,
                cost=PiecewiseCost(points=g1_points),
            ),
        ],
        loads=[Load(id="ld1", bus="b1", p_mw=40.0, q_mvar=0.0)],
    )


@pytest.fixture
def arr() -> NetworkArrays:
    return NetworkArrays.from_network(_one_bus_network(G1_POINTS))


def _cost_coeffs_linear_g0_only() -> np.ndarray:
    # [c2, c1, c0] rows, NetworkArrays gen order (g0, g1); g1's row is all-zero — its cost is
    # captured entirely by the PWL epigraph rows, not this array (module docstring, dc_opf.py).
    return np.array([[0.0, 22.0, 0.0], [0.0, 0.0, 0.0]])


def test_dc_opf_pwl_generator_stops_at_the_breakpoint_where_the_alternative_is_cheaper(
    arr: NetworkArrays,
) -> None:
    coeffs = _cost_coeffs_linear_g0_only()
    solution = dc_opf(arr, coeffs, OpfDcOptions(), pwl_costs={1: G1_POINTS})

    assert solution.status == "Optimal"
    assert solution.duals is not None
    g0, g1 = arr.gen_ids.index("g0"), arr.gen_ids.index("g1")
    np.testing.assert_allclose(
        [solution.dispatch_mw[g0], solution.dispatch_mw[g1]], [10.0, 30.0], atol=1e-6
    )
    assert solution.objective_cost == pytest.approx(820.0, abs=1e-4)

    # neither generator is pinned at a bound (both interior) — reduced costs are 0
    assert solution.duals.gen_bound[g0] == pytest.approx(0.0, abs=1e-6)
    assert solution.duals.gen_bound[g1] == pytest.approx(0.0, abs=1e-6)


def test_dc_opf_pwl_generator_can_be_forced_into_a_later_segment(arr: NetworkArrays) -> None:
    """Same network, load raised to 90 MW: g0 caps out cheap capacity is irrelevant here (its
    bound is 100, never binds), but g1 must now supply enough that it crosses into its second
    segment. Merit order: g1 seg1 (20) < g0 (22) < g1 seg2 (30) < g1 seg3 (37.5) — so g1 takes
    its full 30 MW seg1, then g0 (22) is next-cheapest and takes as much as it wants (unbounded
    at 100), so *all* remaining 60 MW should still come from g0, not g1's seg2 (30 > 22). Expected
    optimum: g0 = 60, g1 = 30 (same as the 40 MW case's g1 dispatch, since g1's second segment is
    never cheaper than g0)."""
    coeffs = _cost_coeffs_linear_g0_only()
    net = _one_bus_network(G1_POINTS)
    net = net.model_copy(deep=True)
    net.loads[0] = net.loads[0].model_copy(update={"p_mw": 90.0})
    heavier_arr = NetworkArrays.from_network(net)

    solution = dc_opf(heavier_arr, coeffs, OpfDcOptions(), pwl_costs={1: G1_POINTS})
    assert solution.status == "Optimal"
    g0, g1 = heavier_arr.gen_ids.index("g0"), heavier_arr.gen_ids.index("g1")
    np.testing.assert_allclose(
        [solution.dispatch_mw[g0], solution.dispatch_mw[g1]], [60.0, 30.0], atol=1e-6
    )
    assert solution.objective_cost == pytest.approx(22.0 * 60.0 + 600.0, abs=1e-4)


def test_dc_opf_with_no_pwl_costs_is_unaffected_by_the_new_parameter(arr: NetworkArrays) -> None:
    """``pwl_costs=None`` (the default) must reproduce the exact pre-S3 polynomial-only LP —
    proves the extension is additive, not a rewrite of the existing path."""
    coeffs = np.array([[0.0, 22.0, 0.0], [0.0, 15.0, 0.0]])  # both linear this time
    solution = dc_opf(arr, coeffs, OpfDcOptions())
    assert solution.status == "Optimal"
    # g1 (cheaper, 15 < 22) should take the whole 40 MW load
    g1 = arr.gen_ids.index("g1")
    assert solution.dispatch_mw[g1] == pytest.approx(40.0, abs=1e-6)


def test_dc_opf_raises_nonconvexcosterror_for_decreasing_slope_before_any_solve(
    arr: NetworkArrays,
) -> None:
    """Slopes 20 then 10 (decreasing) is non-convex — rejected up front, not silently solved into
    a wrong dispatch (module docstring, research §2.1)."""
    non_convex_points = [(0.0, 0.0), (30.0, 600.0), (60.0, 900.0)]  # slopes 20, 10
    coeffs = _cost_coeffs_linear_g0_only()
    with pytest.raises(NonConvexCostError, match="non-convex"):
        dc_opf(arr, coeffs, OpfDcOptions(), pwl_costs={1: non_convex_points})


def test_dc_opf_accepts_equal_consecutive_slopes_as_convex(arr: NetworkArrays) -> None:
    """Non-decreasing (weak convexity) is the documented bar, not strictly increasing —
    equal consecutive slopes must not raise."""
    equal_slope_points = [(0.0, 0.0), (30.0, 600.0), (60.0, 1200.0)]  # slopes 20, 20
    coeffs = _cost_coeffs_linear_g0_only()
    solution = dc_opf(arr, coeffs, OpfDcOptions(), pwl_costs={1: equal_slope_points})
    assert solution.status == "Optimal"
