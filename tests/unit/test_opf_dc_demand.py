"""AC-1, AC-2: elastic-demand LP columns/rows in ``dc_opf`` (spec W1, design item 1).

Entirely hand-built networks (no ``tests/_bids.py`` fixture dependency -- that's S5's job).
Mirrors ``test_opf_dc.py``/``test_opf_dc_pwl.py``'s "prove the wiring directly on ``dc_opf``, not
through ``solve_dc_opf``" discipline.
"""

from __future__ import annotations

import numpy as np
import pytest

from mambo_power.model import Branch, Bus, Generator, Load, Network
from mambo_power.numerics.arrays import NetworkArrays
from mambo_power.opf.dc_opf import (
    NonConcaveBidError,
    NonConvexCostError,
    OpfDcOptions,
    dc_opf,
    lmp_decomposition,
)

# --- AC-1: hand-KKT-verified 2-bus elastic-demand welfare optimum (m4-research.md §4.1) --------


def _two_bus_network() -> Network:
    """b1 slack (g1, linear cost 10/MW), b2 (g2, linear cost 50/MW; elastic load d1), one
    rated branch (20 MW) between them -- the exact m4-research.md §4.1 example."""
    return Network(
        base_mva=100.0,
        buses=[
            Bus(id="b1", base_kv=138.0, type="slack"),
            Bus(id="b2", base_kv=138.0, type="pq"),
        ],
        branches=[
            Branch(id="br12", from_bus="b1", to_bus="b2", r=0.0, x=0.1, b=0.0, rating_mva=20.0),
        ],
        generators=[
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
            ),
            Generator(
                id="g2",
                bus="b2",
                p_mw=0,
                q_mvar=0,
                p_min_mw=0,
                p_max_mw=100,
                q_min_mvar=0,
                q_max_mvar=0,
                v_set_pu=1.0,
            ),
        ],
        loads=[Load(id="d1", bus="b2", p_mw=100.0, q_mvar=0.0)],
    )


@pytest.fixture
def two_bus_arrays() -> NetworkArrays:
    return NetworkArrays.from_network(_two_bus_network())


# 2-segment concave bid: marginal value 45 on [0,50], 20 on [50,100] (m4-research.md §4.1).
D1_BID_POINTS = [(0.0, 0.0), (50.0, 2250.0), (100.0, 3250.0)]


def test_ac1_two_bus_hand_kkt_welfare_optimum(two_bus_arrays: NetworkArrays) -> None:
    arr = two_bus_arrays
    assert arr.gen_ids == ["g1", "g2"]
    assert arr.load_ids == ["d1"]
    d1 = arr.load_ids.index("d1")
    coeffs = np.array([[0.0, 10.0, 0.0], [0.0, 50.0, 0.0]])

    solution = dc_opf(arr, coeffs, OpfDcOptions(), demand_pwl_bids={d1: D1_BID_POINTS})

    assert solution.status == "Optimal"
    assert solution.duals is not None
    g1, g2 = arr.gen_ids.index("g1"), arr.gen_ids.index("g2")
    np.testing.assert_allclose(solution.dispatch_mw[[g1, g2]], [20.0, 0.0], atol=1e-6)
    np.testing.assert_allclose(solution.demand_dispatch_mw, [20.0], atol=1e-6)

    assert solution.duals.balance == pytest.approx(10.0, abs=1e-6)

    br12 = arr.branch_index["br12"]
    lmp = lmp_decomposition(solution.duals, solution.ptdf)
    assert lmp.lmp[arr.bus_index["b1"]] == pytest.approx(10.0, abs=1e-6)
    assert lmp.lmp[arr.bus_index["b2"]] == pytest.approx(45.0, abs=1e-6)
    assert solution.duals.flow_limit[br12] != 0.0  # binding, per the hand-KKT solve


def test_ac1_settlement_identity_holds_on_the_two_bus_case(two_bus_arrays: NetworkArrays) -> None:
    """Independent cross-check of AC-1's own numbers via the settlement identity
    (m4-research.md §4.1): payments - receipts == -mu_flow * flow."""
    arr = two_bus_arrays
    d1 = arr.load_ids.index("d1")
    coeffs = np.array([[0.0, 10.0, 0.0], [0.0, 50.0, 0.0]])
    solution = dc_opf(arr, coeffs, OpfDcOptions(), demand_pwl_bids={d1: D1_BID_POINTS})
    assert solution.duals is not None
    lmp = lmp_decomposition(solution.duals, solution.ptdf)

    lmp_bus2 = lmp.lmp[arr.bus_index["b2"]]
    lmp_bus1 = lmp.lmp[arr.bus_index["b1"]]
    d = float(solution.demand_dispatch_mw[0])
    g1, g2 = arr.gen_ids.index("g1"), arr.gen_ids.index("g2")
    payments = lmp_bus2 * d
    receipts = lmp_bus1 * solution.dispatch_mw[g1] + lmp_bus2 * solution.dispatch_mw[g2]
    assert payments == pytest.approx(900.0, abs=1e-4)
    assert receipts == pytest.approx(200.0, abs=1e-4)
    assert (payments - receipts) == pytest.approx(700.0, abs=1e-4)


# --- AC-2: NonConcaveBidError / generator-side c2 >= 0 guard ------------------------------------


def _one_bus_arrays(p_max: float = 100.0) -> NetworkArrays:
    net = Network(
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
                p_max_mw=p_max,
                q_min_mvar=0,
                q_max_mvar=0,
                v_set_pu=1.0,
            ),
        ],
        loads=[Load(id="d0", bus="b1", p_mw=60.0, q_mvar=0.0)],
    )
    return NetworkArrays.from_network(net)


def test_nonconcavebiderror_on_increasing_pwl_segment_slope() -> None:
    """Slopes 20, then 25 (increasing) is non-concave -- rejected up front."""
    arr = _one_bus_arrays()
    d0 = arr.load_ids.index("d0")
    coeffs = np.array([[0.0, 22.0, 0.0]])
    non_concave_points = [(0.0, 0.0), (30.0, 600.0), (60.0, 1350.0)]  # slopes 20, 25
    with pytest.raises(NonConcaveBidError, match="non-concave"):
        dc_opf(arr, coeffs, OpfDcOptions(), demand_pwl_bids={d0: non_concave_points})


def test_nonconcavebiderror_on_positive_v2_polynomial_bid() -> None:
    """A quadratic bid with v2 > 0 has increasing marginal value -- non-concave."""
    arr = _one_bus_arrays()
    d0 = arr.load_ids.index("d0")
    coeffs = np.array([[0.0, 22.0, 0.0]])
    with pytest.raises(NonConcaveBidError, match="non-concave"):
        dc_opf(arr, coeffs, OpfDcOptions(), demand_bid_coeffs={d0: (0.5, 30.0, 0.0)})


def test_nonconvexcosterror_on_negative_c2_generator_cost() -> None:
    """A hand-built c2 < 0 generator cost is rejected before any solve (generator-side convexity
    guard, closing the asymmetry the research found)."""
    arr = _one_bus_arrays()
    coeffs = np.array([[-0.1, 22.0, 0.0]])
    with pytest.raises(NonConvexCostError, match="non-convex"):
        dc_opf(arr, coeffs, OpfDcOptions())


def test_positive_c2_generator_cost_is_unaffected_by_the_new_guard() -> None:
    """The guard must not fire for a valid convex (c2 >= 0) quadratic cost."""
    arr = _one_bus_arrays()
    coeffs = np.array([[0.1, 22.0, 0.0]])
    solution = dc_opf(arr, coeffs, OpfDcOptions())
    assert solution.status == "Optimal"


# --- mixed elastic + inelastic loads: no double-counting ----------------------------------------


def _mixed_load_network() -> Network:
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
                p_max_mw=1000,
                q_min_mvar=0,
                q_max_mvar=0,
                v_set_pu=1.0,
            ),
        ],
        loads=[
            Load(id="ld_fixed", bus="b1", p_mw=30.0, q_mvar=0.0),
            Load(id="ld_elastic", bus="b1", p_mw=50.0, q_mvar=0.0),
        ],
    )


def test_mixed_elastic_and_inelastic_load_no_double_counting() -> None:
    """``ld_fixed`` has no bid (stays in the fixed p_load_pu aggregate); ``ld_elastic`` has a bid
    whose marginal value (1000) vastly exceeds the generator's cost (5), so it is pinned at its
    own [0, 50] cap. If dc_opf double-counted ld_elastic (failed to subtract its own contribution
    from the fixed aggregate before adding its LP column), g0 would be forced to 130 MW instead of
    the correct 80 MW."""
    arr = NetworkArrays.from_network(_mixed_load_network())
    ld_elastic = arr.load_ids.index("ld_elastic")
    assert arr.load_ids == ["ld_fixed", "ld_elastic"]
    coeffs = np.array([[0.0, 5.0, 0.0]])

    solution = dc_opf(
        arr, coeffs, OpfDcOptions(), demand_bid_coeffs={ld_elastic: (0.0, 1000.0, 0.0)}
    )

    assert solution.status == "Optimal"
    assert solution.demand_dispatch_mw[0] == pytest.approx(50.0, abs=1e-6)  # pinned at own cap
    assert solution.dispatch_mw[0] == pytest.approx(80.0, abs=1e-6)  # 30 fixed + 50 elastic, once


def test_demand_bound_reduced_cost_nonzero_when_pinned_at_cap() -> None:
    arr = NetworkArrays.from_network(_mixed_load_network())
    ld_elastic = arr.load_ids.index("ld_elastic")
    coeffs = np.array([[0.0, 5.0, 0.0]])
    solution = dc_opf(
        arr, coeffs, OpfDcOptions(), demand_bid_coeffs={ld_elastic: (0.0, 1000.0, 0.0)}
    )
    assert solution.duals is not None
    assert solution.demand_bound[0] != 0.0  # pinned at its own [0, p_max] upper bound


# --- PWL demand bid: hypograph row construction --------------------------------------------------


def test_demand_pwl_bid_stops_at_the_breakpoint_where_marginal_value_drops_below_gen_cost() -> None:
    """1-bus network, g0 linear ($22/MWh, effectively unbounded), load bid PWL with segment
    slopes 25 then 20 (concave). Welfare-maximizing: increase d while marginal value (25) exceeds
    generation's marginal cost (22) -- take the whole first segment (30 MW); stop there, since the
    second segment's marginal value (20) is below 22. Expected optimum: d = g0 = 30 MW exactly,
    mirroring test_opf_dc_pwl.py's generator-side PWL test structure precisely, demand-side."""
    arr = _one_bus_arrays(p_max=1000.0)
    d0 = arr.load_ids.index("d0")
    coeffs = np.array([[0.0, 22.0, 0.0]])
    bid_points = [(0.0, 0.0), (30.0, 750.0), (60.0, 1350.0)]  # slopes 25, 20

    solution = dc_opf(arr, coeffs, OpfDcOptions(), demand_pwl_bids={d0: bid_points})

    assert solution.status == "Optimal"
    assert solution.duals is not None
    np.testing.assert_allclose(solution.demand_dispatch_mw, [30.0], atol=1e-6)
    np.testing.assert_allclose(solution.dispatch_mw, [30.0], atol=1e-6)


# --- backward compatibility: demand params default to None = today's exact fixed-load behavior --


def test_dc_opf_with_no_demand_params_is_byte_identical_to_the_pre_s3_call(
    two_bus_arrays: NetworkArrays,
) -> None:
    arr = two_bus_arrays
    coeffs = np.array([[0.0, 10.0, 0.0], [0.0, 50.0, 0.0]])
    solution = dc_opf(arr, coeffs, OpfDcOptions())
    assert solution.status == "Optimal"
    assert solution.demand_dispatch_mw.shape == (0,)
    assert solution.demand_bound.shape == (0,)
    # unaffected fixed-load dispatch: b2's 100 MW load served by g1 (cheaper) up to the 20 MW
    # branch rating, remainder from g2 (expensive but local, no line to cross)
    g1, g2 = arr.gen_ids.index("g1"), arr.gen_ids.index("g2")
    assert solution.dispatch_mw[g1] == pytest.approx(20.0, abs=1e-6)
    assert solution.dispatch_mw[g2] == pytest.approx(80.0, abs=1e-6)
