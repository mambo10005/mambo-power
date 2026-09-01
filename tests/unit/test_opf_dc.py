"""AC-2, AC-3: ``opf.dc_opf.dc_opf``'s dual-API wiring and ``lmp_decomposition`` standalone use.

The hand-built network (module-level fixture below) is a 3-bus/3-generator triangle with equal
branch reactances, chosen so a slack-bus generator's PTDF column is exactly zero by construction
(``numerics.ptdf`` zeroes the slack column) — an *unconstrained* slack-bus generator's KKT
stationarity condition then reduces to ``cost'(p) == balance_dual`` exactly, with no congestion
term to solve for. This gives AC-2 a numeric oracle for the balance dual that is independently
derivable by hand, without solving a coupled dual system:

* ``g0`` (bus1, slack): cheapest (c1=1), tiny capacity (p_max=5) — always dispatched to its
  cap regardless of the flow constraint, so it is the "generator pinned at its bound".
* ``g1`` (bus1, slack): mid-cost (c1=10), wide bounds ([0, 200]) — never pinned, so its own
  cost coefficient *is* the balance dual (its PTDF column is exactly zero: bus1 is the slack).
* ``g2`` (bus3): expensive (c1=50), wide bounds — dispatched only as much as ``br12``'s rating
  forces, so it stays interior on its own bounds (reduced cost 0, not asserted, but checked).

Only the load (90 MW at bus2, no generator there) drives ``br12``'s flow before congestion
management: with every non-slack generator at 0, ``ptdf(arr)`` gives ``flow_br12 = 60`` MW
(measured directly below); a rating of 50 MW forces exactly 30 MW onto ``g2`` to relieve it
(``flow_br12 = 60 - (1/3)*pg2 <= 50``), leaving ``g1`` to absorb the rest (`90 - 5 - 30 = 55`,
still interior).
"""

from __future__ import annotations

import dataclasses

import numpy as np
import pytest

from mambo_power.model import Branch, Bus, Generator, Load, Network
from mambo_power.numerics.arrays import NetworkArrays
from mambo_power.numerics.ptdf import ptdf
from mambo_power.opf.dc_opf import OpfDcOptions, OpfDuals, dc_opf, lmp_decomposition


def _triangle_network() -> Network:
    """3-bus/3-generator triangle, equal branch reactances (module docstring)."""
    return Network(
        base_mva=100.0,
        buses=[
            Bus(id="b1", base_kv=138.0, type="slack"),
            Bus(id="b2", base_kv=138.0, type="pq"),
            Bus(id="b3", base_kv=138.0, type="pq"),
        ],
        branches=[
            Branch(id="br12", from_bus="b1", to_bus="b2", r=0.0, x=0.1, b=0.0, rating_mva=50.0),
            Branch(id="br23", from_bus="b2", to_bus="b3", r=0.0, x=0.1, b=0.0),
            Branch(id="br13", from_bus="b1", to_bus="b3", r=0.0, x=0.1, b=0.0),
        ],
        generators=[
            Generator(
                id="g0",
                bus="b1",
                p_mw=0,
                q_mvar=0,
                p_min_mw=0,
                p_max_mw=5,
                q_min_mvar=0,
                q_max_mvar=0,
                v_set_pu=1.0,
            ),
            Generator(
                id="g1",
                bus="b1",
                p_mw=0,
                q_mvar=0,
                p_min_mw=0,
                p_max_mw=200,
                q_min_mvar=0,
                q_max_mvar=0,
                v_set_pu=1.0,
            ),
            Generator(
                id="g2",
                bus="b3",
                p_mw=0,
                q_mvar=0,
                p_min_mw=0,
                p_max_mw=100,
                q_min_mvar=0,
                q_max_mvar=0,
                v_set_pu=1.0,
            ),
        ],
        loads=[Load(id="ld2", bus="b2", p_mw=90.0, q_mvar=0.0)],
    )


@pytest.fixture
def triangle_arrays() -> NetworkArrays:
    return NetworkArrays.from_network(_triangle_network())


def _cost_coeffs(c1: list[float]) -> np.ndarray:
    """``[c2, c1, c0]`` rows, linear-only (module docstring: every generator here is linear)."""
    return np.array([[0.0, c, 0.0] for c in c1])


# --- AC-2: hand-built binding flow limit + pinned generator ------------------------------------


def test_ptdf_confirms_the_hand_derived_flow_before_congestion(
    triangle_arrays: NetworkArrays,
) -> None:
    """Sanity check on the module docstring's own derivation, not on ``dc_opf`` itself."""
    p = ptdf(triangle_arrays)
    br12 = triangle_arrays.branch_index["br12"]
    b2 = triangle_arrays.bus_index["b2"]
    b1 = triangle_arrays.bus_index["b1"]
    assert p[br12, b1] == 0.0  # slack column is always exactly zero
    flow_with_only_load = -p[br12, b2] * 90.0  # g2 = 0
    assert flow_with_only_load == pytest.approx(60.0)


def test_dc_opf_duals_on_the_hand_built_binding_case(triangle_arrays: NetworkArrays) -> None:
    arr = triangle_arrays
    coeffs = _cost_coeffs([1.0, 10.0, 50.0])  # g0, g1, g2 order (NetworkArrays.gen_ids order)
    assert arr.gen_ids == ["g0", "g1", "g2"]

    solution = dc_opf(arr, coeffs, OpfDcOptions())

    assert solution.status == "Optimal"
    assert solution.duals is not None
    np.testing.assert_allclose(solution.dispatch_mw, [5.0, 55.0, 30.0], atol=1e-7)

    # balance dual == g1's own linear cost coefficient (module docstring derivation)
    assert solution.duals.balance == pytest.approx(10.0, abs=1e-7)

    # flow-limit dual: nonzero exactly on br12 (the only rated, binding branch)
    br12 = arr.branch_index["br12"]
    for k, dual in enumerate(solution.duals.flow_limit):
        if k == br12:
            assert dual != 0.0
        else:
            assert dual == 0.0

    # generator bound reduced cost: nonzero exactly on g0 (pinned at p_max), zero on g1/g2
    g0, g1, g2 = (arr.gen_ids.index(i) for i in ("g0", "g1", "g2"))
    assert solution.duals.gen_bound[g0] != 0.0
    assert solution.duals.gen_bound[g1] == 0.0
    assert solution.duals.gen_bound[g2] == 0.0

    # objective cost matches the linear costs at the found dispatch (no constant terms here)
    expected_cost = 1.0 * 5.0 + 10.0 * 55.0 + 50.0 * 30.0
    assert solution.objective_cost == pytest.approx(expected_cost, rel=1e-9)


def test_dc_opf_status_infeasible_on_contradictory_bounds(triangle_arrays: NetworkArrays) -> None:
    """A generator whose own [p_min, p_max] cannot possibly meet the fixed load is Infeasible."""
    arr = triangle_arrays
    # collapse every generator's capacity far below the 90 MW load
    tiny = dataclasses.replace(arr, gen_p_max_pu=np.full_like(arr.gen_p_max_pu, 0.01))
    coeffs = _cost_coeffs([1.0, 10.0, 50.0])
    solution = dc_opf(tiny, coeffs, OpfDcOptions())
    assert solution.status == "Infeasible"
    assert solution.duals is None
    assert solution.message is not None


# --- AC-3: cost_coeffs is caller-supplied, independent of Network; lmp_decomposition standalone -


def test_dc_opf_takes_cost_coeffs_independent_of_network(triangle_arrays: NetworkArrays) -> None:
    """Two different synthetic cost arrays over the *same* NetworkArrays give two different,
    each internally-LP-optimal dispatches — proving dc_opf reads costs from its own argument,
    not from anywhere the Network might otherwise expose them (there is no cost on this
    NetworkArrays at all; it never had one)."""
    arr = triangle_arrays
    # g2 cheaper than g1 (5 < 10): the LP should want as much g2 as its own cap allows, not just
    # the 30 MW the flow constraint forces (see the "expensive" case) — cost genuinely drives it.
    cheap_g2 = _cost_coeffs([1.0, 10.0, 5.0])
    expensive_g2 = _cost_coeffs([1.0, 10.0, 50.0])  # the AC-2 case: g2 dispatched only as forced

    sol_cheap = dc_opf(arr, cheap_g2, OpfDcOptions())
    sol_expensive = dc_opf(arr, expensive_g2, OpfDcOptions())

    assert sol_cheap.status == sol_expensive.status == "Optimal"
    assert not np.allclose(sol_cheap.dispatch_mw, sol_expensive.dispatch_mw)

    # each is internally optimal for its own objective: cheaper g2 costs the LP to use it more
    g2 = arr.gen_ids.index("g2")
    assert sol_cheap.dispatch_mw[g2] > sol_expensive.dispatch_mw[g2]

    # both still satisfy the balance and bounds regardless of which cost array was used
    for sol in (sol_cheap, sol_expensive):
        assert np.sum(sol.dispatch_mw) == pytest.approx(90.0, abs=1e-6)
        assert np.all(sol.dispatch_mw >= arr.gen_p_min_pu * arr.base_mva - 1e-9)
        assert np.all(sol.dispatch_mw <= arr.gen_p_max_pu * arr.base_mva + 1e-9)


def test_lmp_decomposition_is_standalone_and_independent_of_solve_dc_opf() -> None:
    """Callable with hand-built duals/ptdf, never having called dc_opf/solve_dc_opf at all."""
    duals = OpfDuals(
        balance=20.0,
        flow_limit=np.array([5.0, -3.0]),
        gen_bound=np.array([0.0, 0.0]),
    )
    # 2 branches x 3 buses, hand-picked PTDF-shaped values
    ptdf_matrix = np.array(
        [
            [0.0, -0.6, 0.4],
            [0.0, 0.2, -0.2],
        ]
    )
    breakdown = lmp_decomposition(duals, ptdf_matrix)

    expected_congestion = duals.flow_limit @ ptdf_matrix
    expected_energy = np.full(3, 20.0)
    np.testing.assert_allclose(breakdown.energy, expected_energy)
    np.testing.assert_allclose(breakdown.congestion, expected_congestion)
    np.testing.assert_allclose(breakdown.lmp, expected_energy + expected_congestion)


def test_dc_opf_accepts_a_precomputed_ptdf_and_solves_identically(
    triangle_arrays: NetworkArrays,
) -> None:
    """``dc_opf(..., ptdf=...)`` (M7 S11, critic finding 3) is a cache, not a different model: the
    dispatch, duals and returned PTDF are ``array_equal`` -- bitwise, not ``allclose`` -- to the
    default path that computes the matrix itself. The default keeps every existing caller
    byte-identical; a matrix of the wrong shape is refused up front rather than silently used
    as some other network's."""
    arr = triangle_arrays
    coeffs = _cost_coeffs([1.0, 10.0, 50.0])
    computed = dc_opf(arr, coeffs, OpfDcOptions())
    cached = dc_opf(arr, coeffs, OpfDcOptions(), ptdf=ptdf(arr))
    assert computed.status == cached.status == "Optimal"
    assert computed.duals is not None and cached.duals is not None
    assert np.array_equal(computed.dispatch_mw, cached.dispatch_mw)
    assert np.array_equal(computed.ptdf, cached.ptdf)
    assert np.array_equal(computed.duals.flow_limit, cached.duals.flow_limit)
    assert np.array_equal(computed.duals.gen_bound, cached.duals.gen_bound)
    assert computed.duals.balance == cached.duals.balance
    assert computed.objective_cost == cached.objective_cost
    with pytest.raises(ValueError, match=r"ptdf must have shape \(3, 3\)"):
        dc_opf(arr, coeffs, OpfDcOptions(), ptdf=np.zeros((2, 3)))
