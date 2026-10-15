"""Elastic demand in the AC-OPF (ADR-030): a ``Load.bid`` is served where its marginal value
meets the AC LMP, with ``OpfAcOptions(elastic_demand=True)``.

* **The SLSQP oracle of ``test_opf_ac.py`` with one more variable.** On the two-bus hand case the
  load's demand ``P_d`` joins the decision vector at its own power factor and its bid's value
  leaves the objective; SLSQP knows nothing about power systems, so agreeing with it on welfare,
  dispatch and the served demand is independent evidence. A quadratic bid clears in the
  interior (marginal value = LMP), a piecewise-linear one at a breakpoint (the LMP between the
  two slopes, no bound dual), and a bid above every price at its full ``p_mw`` with the bound
  dual equal to the gap.
* **The fixed-load solve is untouched**: with ``elastic_demand`` off, or with no bid, every
  published objective and every row is what it was.
* **case14 with bids**: served demand, LMP-equals-marginal-value where interior, the bound dual
  where pinned, the ``loads`` rows and the welfare identity ``objective_cost − demand_value``
  equal to the SLP's own objective, through ``solve_ac_opf`` and the ``opf.ac`` job.
"""

from __future__ import annotations

import numpy as np
import pytest
from scipy import optimize

from mambo_power import cases
from mambo_power.jobs import SolveRequest, run
from mambo_power.model import Network, PiecewiseBid, PolynomialBid
from mambo_power.opf import OpfAcOptions, solve_ac_opf
from mambo_power.opf.dc_opf import NonConcaveBidError
from mambo_power.results import OpfAcResult
from tests.unit.test_opf_ac import LOAD_P, LOAD_Q, B, R, X, _two_bus

ELASTIC = OpfAcOptions(elastic_demand=True)
PF_RATIO = LOAD_Q / LOAD_P


def _bid_two_bus(bid: PolynomialBid | PiecewiseBid) -> Network:
    net = _two_bus()
    net.loads[0].bid = bid
    return net


def _oracle(value_coeffs: tuple[float, float]) -> optimize.OptimizeResult:
    """SLSQP on the two-bus AC-OPF with the load's demand free in ``[0, LOAD_P]`` at its power
    factor and ``value(P_d) = v2·P_d² + v1·P_d`` taken off the objective."""
    v2, v1 = value_coeffs
    y_s = 1.0 / (R + 1j * X)
    y_sh = 1j * B / 2.0
    y = np.array([[y_s + y_sh, -y_s], [-y_s, y_s + y_sh]])
    cost = np.array([10.0, 30.0])

    def unpack(x: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray, float]:
        va2, vm1, vm2, pg1, pg2, qg1, qg2, pd = x
        v = np.array([vm1, vm2 * np.exp(1j * va2)])
        return v, np.array([pg1, pg2]), np.array([qg1, qg2]), float(pd)

    def balance(x: np.ndarray) -> np.ndarray:
        v, pg, qg, pd = unpack(x)
        load = np.array([0.0, pd * (1.0 + 1j * PF_RATIO)]) / 100.0
        s = v * np.conj(y @ v) + load - (pg + 1j * qg) / 100.0
        return np.concatenate([s.real, s.imag])

    def objective(x: np.ndarray) -> float:
        _, pg, _, pd = unpack(x)
        return float(np.dot(cost, pg) - (v2 * pd * pd + v1 * pd))

    x0 = np.array([0.0, 1.0, 1.0, LOAD_P, 0.0, LOAD_Q, 0.0, LOAD_P])
    result = optimize.minimize(
        objective,
        x0,
        method="SLSQP",
        bounds=[
            (-np.pi, np.pi),
            (0.95, 1.05),
            (0.95, 1.05),
            (0, 300),
            (0, 50),
            (-100, 100),
            (-50, 50),
            (0, LOAD_P),
        ],
        constraints=[{"type": "eq", "fun": balance}],
        options={"ftol": 1e-12, "maxiter": 500},
    )
    assert result.success, result.message
    return result


# --- the hand case against SLSQP ----------------------------------------------------------------


def test_quadratic_bid_clears_where_marginal_value_meets_the_lmp() -> None:
    v2, v1 = -0.1, 20.0  # marginal value 20 − 0.2·P_d, meets the ~10.2 $/MWh LMP near 49 MW
    result = solve_ac_opf(_bid_two_bus(PolynomialBid(coefficients=[v2, v1, 0.0])), ELASTIC)
    oracle = _oracle((v2, v1))

    assert result.status == "Optimal", result.message
    welfare_cost = result.objective_cost - result.demand_value
    assert welfare_cost == pytest.approx(oracle.fun, rel=1e-6)
    (load,) = result.loads
    assert load.elastic and load.id == "ld" and load.bus == "b2"
    assert load.p_mw == pytest.approx(oracle.x[7], abs=1e-2)
    assert load.q_mvar == pytest.approx(load.p_mw * PF_RATIO)
    assert 0.0 < load.p_mw < LOAD_P and load.bound_dual == 0.0
    lmp = {b.id: b.lmp_p for b in result.buses}
    assert lmp["b2"] == pytest.approx(v1 + 2.0 * v2 * load.p_mw, abs=1e-3)  # marginal value
    assert lmp["b2"] > 10.0  # losses priced in above the cheap unit's cost
    dispatch = {g.id: g.p_mw for g in result.generators}
    assert dispatch["cheap"] == pytest.approx(oracle.x[3], abs=1e-2)
    assert dispatch["dear"] == pytest.approx(0.0, abs=1e-6)
    assert result.demand_value == pytest.approx(v2 * load.p_mw**2 + v1 * load.p_mw)
    assert result.losses_mw == pytest.approx(dispatch["cheap"] - load.p_mw, abs=1e-6)


def test_a_bid_above_every_price_is_served_in_full_with_the_gap_as_bound_dual() -> None:
    v1 = 40.0  # above the 30 $/MWh dear unit: the load takes all of its p_mw
    result = solve_ac_opf(_bid_two_bus(PolynomialBid(coefficients=[v1, 0.0])), ELASTIC)
    fixed = solve_ac_opf(_two_bus())
    oracle = _oracle((0.0, v1))

    assert result.status == "Optimal", result.message
    (load,) = result.loads
    assert load.p_mw == pytest.approx(LOAD_P)
    assert oracle.x[7] == pytest.approx(LOAD_P, abs=1e-6)
    assert result.objective_cost == pytest.approx(fixed.objective_cost, rel=1e-6)
    assert result.demand_value == pytest.approx(v1 * LOAD_P)
    lmp = {b.id: b.lmp_p for b in result.buses}
    # pinned at p_mw: the reduced cost is what one more MW would be worth, bid minus price
    assert load.bound_dual == pytest.approx(lmp["b2"] - v1, abs=1e-3)
    assert load.bound_dual < 0.0


def test_piecewise_bid_clears_at_its_breakpoint_with_the_lmp_between_the_slopes() -> None:
    # 30 $/MWh for the first 40 MW, 10 $/MWh beyond: the ~10.15 $/MWh LMP sits between
    bid = PiecewiseBid(points=[(0.0, 0.0), (40.0, 1200.0), (100.0, 1800.0)])
    result = solve_ac_opf(_bid_two_bus(bid), ELASTIC)

    assert result.status == "Optimal", result.message
    (load,) = result.loads
    assert load.p_mw == pytest.approx(40.0, abs=1e-6)
    assert load.bound_dual == 0.0  # a breakpoint is not a bound
    assert result.demand_value == pytest.approx(1200.0, abs=1e-6)
    lmp = {b.id: b.lmp_p for b in result.buses}
    assert 10.0 < lmp["b2"] < 30.0


def test_a_non_concave_bid_is_rejected_up_front() -> None:
    with pytest.raises(NonConcaveBidError):
        solve_ac_opf(_bid_two_bus(PolynomialBid(coefficients=[0.1, 20.0, 0.0])), ELASTIC)


# --- the fixed-load solve is untouched ------------------------------------------------------------


def test_without_the_option_or_a_bid_every_load_is_fixed() -> None:
    plain = solve_ac_opf(_two_bus())
    with_bid_off = solve_ac_opf(_bid_two_bus(PolynomialBid(coefficients=[-0.1, 20.0, 0.0])))
    assert with_bid_off.objective_cost == pytest.approx(plain.objective_cost, rel=1e-9)
    assert with_bid_off.demand_value == 0.0
    (load,) = with_bid_off.loads
    assert not load.elastic and load.p_mw == LOAD_P and load.q_mvar == LOAD_Q

    on_without_bids = solve_ac_opf(_two_bus(), ELASTIC)
    assert on_without_bids.objective_cost == pytest.approx(plain.objective_cost, rel=1e-9)
    assert on_without_bids.loads == with_bid_off.loads

    for name in ("case14", "case30"):
        fixed = solve_ac_opf(cases.load(name))
        elastic = solve_ac_opf(cases.load(name), ELASTIC)  # no bundled load carries a bid
        assert elastic.objective_cost == pytest.approx(fixed.objective_cost, rel=1e-9)
        assert elastic.generators == fixed.generators
        assert all(not ld.elastic for ld in elastic.loads)
        assert sum(ld.p_mw for ld in elastic.loads) == pytest.approx(
            sum(ld.p_mw for ld in cases.load(name).loads)
        )


# --- case14 ---------------------------------------------------------------------------------------


def _case14_with_bids(value: float, count: int = 3) -> Network:
    net = cases.load("case14")
    for load in net.loads[:count]:
        load.bid = PolynomialBid(coefficients=[value, 0.0])
    return net


def test_case14_bids_clear_against_the_lmps() -> None:
    net = _case14_with_bids(38.0)
    result = solve_ac_opf(net, ELASTIC)
    fixed = solve_ac_opf(cases.load("case14"))

    assert result.status == "Optimal", result.message
    lmp = {b.id: b.lmp_p for b in result.buses}
    elastic = [ld for ld in result.loads if ld.elastic]
    assert [ld.id for ld in elastic] == [ld.id for ld in net.loads[:3]]
    full = {ld.id: ld.p_mw for ld in net.loads}
    for load in elastic:
        assert 0.0 <= load.p_mw <= full[load.id] + 1e-9
        if load.p_mw < full[load.id] - 1e-6:  # interior: the bus price is the bid
            assert lmp[load.bus] == pytest.approx(38.0, abs=0.05)
            assert load.bound_dual == 0.0
        else:  # pinned at its p_mw: the price is below the bid by the bound dual
            assert lmp[load.bus] < 38.0
            assert load.bound_dual == pytest.approx(lmp[load.bus] - 38.0, abs=0.05)
    assert any(ld.p_mw < full[ld.id] - 1e-6 for ld in elastic)  # some demand was shed
    assert any(ld.p_mw == pytest.approx(full[ld.id]) for ld in elastic)  # some was not
    assert result.objective_cost < fixed.objective_cost
    assert result.demand_value == pytest.approx(38.0 * sum(ld.p_mw for ld in elastic))
    for load in result.loads:
        if not load.elastic:
            assert load.p_mw == pytest.approx(full[load.id]) and load.bound_dual == 0.0
    assert result.losses_mw == pytest.approx(
        sum(g.p_mw for g in result.generators) - sum(ld.p_mw for ld in result.loads), abs=1e-6
    )


def test_result_round_trips_and_the_job_carries_the_option() -> None:
    net = _case14_with_bids(38.0, count=2)
    result = solve_ac_opf(net, ELASTIC)
    assert OpfAcResult.model_validate_json(result.model_dump_json()) == result

    reply = run(SolveRequest(kind="opf.ac", network=net, options={"elastic_demand": True}))
    assert reply.status == "ok" and isinstance(reply.result, OpfAcResult)
    assert reply.result.provenance.options["elastic_demand"] is True
    assert [ld.p_mw for ld in reply.result.loads] == pytest.approx(
        [ld.p_mw for ld in result.loads], abs=1e-6
    )
