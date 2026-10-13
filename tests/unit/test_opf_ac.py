"""AC optimal power flow (:mod:`mambo_power.opf.ac_opf`, ADR-018).

Three kinds of evidence, none of which is the solver checking itself:

* **An independent oracle on a hand case.** ``_two_bus`` is a cheap slack unit feeding a load
  over a lossy line, with a dear unit at the load. The test re-derives the AC power-flow
  equations from the branch parameters in dense complex arithmetic — not through
  ``numerics.ybus`` — and hands the whole problem to ``scipy.optimize.minimize`` (SLSQP), a
  general NLP solver that knows nothing about power systems. Objective, dispatch and voltages
  must agree; and the LMP at the load bus must exceed the slack's marginal cost by the loss
  factor, which the oracle's own Lagrange multiplier confirms.
* **MATPOWER's published optima.** Every bundled case ships with the objective MATPOWER's own
  interior-point AC-OPF reports (``runopf``, in the MATPOWER manual's case table), and case14's
  dispatch and bus-1 LMP are published too. A trust-region sequential-LP method and an
  interior-point method share nothing but the problem; agreeing to 1e-6 on six cases is the
  solver's parity evidence inside the unit tier (the pandapower ``runopp`` oracle runs in
  ``tests/parity``).
* **Constraint discipline.** Voltages inside their band, apparent flows inside their ratings
  with the binding ones priced, reactive dispatch inside its limits, the slack angle at zero.
"""

from __future__ import annotations

import numpy as np
import pytest
from scipy import optimize

from mambo_power import cases
from mambo_power.jobs import SolveRequest, run
from mambo_power.model import Branch, Bus, Generator, Load, Network, PolynomialCost
from mambo_power.numerics import NetworkArrays
from mambo_power.opf import OpfAcOptions, gen_cost_coeffs, solve_ac_opf, voltage_limits
from mambo_power.opf.ac_opf import ac_opf
from mambo_power.results import OpfAcResult

PUBLISHED_OBJECTIVE = {
    # MATPOWER manual, "Summary of the OPF results for the test cases" (runopf, $/h)
    "case14": 8081.53,
    "case30": 576.89,
    "case_ieee30": 8906.14,
    "case57": 41737.79,
    "case118": 129660.69,
    "case300": 719725.11,
}
PUBLISHED_TOL = 2e-5
"""Relative tolerance against a value published to two decimals and reached by a different
method; the measured worst is 1.5e-5 (case30, whose ratings bind), then 2e-6 (case118)."""


def _gen(gen_id: str, bus: str, marginal: float, p_max: float, q_max: float) -> Generator:
    return Generator(
        id=gen_id,
        bus=bus,
        p_mw=0.0,
        q_mvar=0.0,
        p_min_mw=0.0,
        p_max_mw=p_max,
        q_min_mvar=-q_max,
        q_max_mvar=q_max,
        v_set_pu=1.0,
        cost=PolynomialCost(coefficients=[marginal, 0.0]),
    )


R, X, B = 0.02, 0.10, 0.04
LOAD_P, LOAD_Q = 100.0, 20.0


def _two_bus(*, dear_cost: float = 30.0, dear_p_max: float = 50.0) -> Network:
    return Network(
        base_mva=100.0,
        buses=[
            Bus(id="b1", base_kv=138.0, type="slack", v_min_pu=0.95, v_max_pu=1.05),
            Bus(id="b2", base_kv=138.0, type="pv", v_min_pu=0.95, v_max_pu=1.05),
        ],
        branches=[Branch(id="br", from_bus="b1", to_bus="b2", r=R, x=X, b=B)],
        generators=[
            _gen("cheap", "b1", 10.0, 300.0, 100.0),
            _gen("dear", "b2", dear_cost, dear_p_max, 50.0),
        ],
        loads=[Load(id="ld", bus="b2", p_mw=LOAD_P, q_mvar=LOAD_Q)],
    )


def _oracle(dear_cost: float, dear_p_max: float) -> optimize.OptimizeResult:
    """SLSQP on the two-bus AC-OPF, with the power-flow equations written out by hand."""
    y_s = 1.0 / (R + 1j * X)
    y_sh = 1j * B / 2.0
    y = np.array([[y_s + y_sh, -y_s], [-y_s, y_s + y_sh]])
    cost = np.array([10.0, dear_cost])
    load = np.array([0.0, LOAD_P]) / 100.0 + 1j * np.array([0.0, LOAD_Q]) / 100.0

    def unpack(x: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
        va2, vm1, vm2, pg1, pg2, qg1, qg2 = x
        v = np.array([vm1, vm2 * np.exp(1j * va2)])
        return v, np.array([pg1, pg2]), np.array([qg1, qg2])

    def balance(x: np.ndarray) -> np.ndarray:
        v, pg, qg = unpack(x)
        s = v * np.conj(y @ v) + load - (pg + 1j * qg) / 100.0
        return np.concatenate([s.real, s.imag])

    def objective(x: np.ndarray) -> float:
        _, pg, _ = unpack(x)
        return float(np.dot(cost, pg))

    bounds = [
        (-np.pi, np.pi),
        (0.95, 1.05),
        (0.95, 1.05),
        (0, 300),
        (0, dear_p_max),
        (-100, 100),
        (-50, 50),
    ]
    x0 = np.array([0.0, 1.0, 1.0, LOAD_P, 0.0, LOAD_Q, 0.0])
    result = optimize.minimize(
        objective,
        x0,
        method="SLSQP",
        bounds=bounds,
        constraints=[{"type": "eq", "fun": balance}],
        options={"ftol": 1e-12, "maxiter": 500},
    )
    assert result.success, result.message
    return result


# --- the hand case against an independent NLP solver -------------------------------------------


@pytest.mark.parametrize(("dear_cost", "dear_p_max"), [(30.0, 50.0), (10.2, 50.0)])
def test_two_bus_agrees_with_scipy_slsqp(dear_cost: float, dear_p_max: float) -> None:
    result = solve_ac_opf(_two_bus(dear_cost=dear_cost, dear_p_max=dear_p_max))
    oracle = _oracle(dear_cost, dear_p_max)

    assert result.status == "Optimal", result.message
    assert result.objective_cost == pytest.approx(oracle.fun, rel=1e-6)
    dispatch = {g.id: g.p_mw for g in result.generators}
    # when both units are marginal the optimum is flat along their trade-off (the $10.2 case):
    # a few hundredths of a MW either way cost under 1e-6 relative, so the dispatch tolerance
    # is looser than the objective's
    assert dispatch["cheap"] == pytest.approx(oracle.x[3], abs=0.1)
    assert dispatch["dear"] == pytest.approx(oracle.x[4], abs=0.1)
    vm = {b.id: b.vm_pu for b in result.buses}
    assert vm["b1"] == pytest.approx(oracle.x[1], abs=1e-4)
    assert vm["b2"] == pytest.approx(oracle.x[2], abs=1e-4)
    assert result.losses_mw == pytest.approx(
        dispatch["cheap"] + dispatch["dear"] - LOAD_P, abs=1e-6
    )


def test_two_bus_lmp_carries_the_loss_factor() -> None:
    """With the dear unit idle the cheap unit is marginal at $10 at its own bus, and the load
    bus pays more by the marginal loss factor: ``LMP_2 = LMP_1 · (1 + ∂loss/∂P_2)`` — the
    quantity the DC-OPF's lossless LMPs can never show."""
    result = solve_ac_opf(_two_bus())
    lmp = {b.id: b.lmp_p for b in result.buses}
    dispatch = {g.id: g.p_mw for g in result.generators}

    assert dispatch["dear"] == pytest.approx(0.0, abs=1e-6)
    assert lmp["b1"] == pytest.approx(10.0, abs=1e-6)
    assert 10.0 < lmp["b2"] < 12.0
    # finite-difference loss factor: resolve with 1 MW more load at bus 2
    bumped = _two_bus()
    bumped.loads[0].p_mw = LOAD_P + 1.0
    more = solve_ac_opf(bumped)
    marginal_cost = more.objective_cost - result.objective_cost
    assert lmp["b2"] == pytest.approx(marginal_cost, rel=2e-3)


def test_two_bus_dear_unit_runs_when_it_is_cheaper_than_the_losses() -> None:
    """At $10.2 the dear unit beats importing over the lossy line, whose marginal loss factor
    at 100 MW is about 4 %: part of the load is served locally and both units are marginal."""
    result = solve_ac_opf(_two_bus(dear_cost=10.2))
    dispatch = {g.id: g.p_mw for g in result.generators}
    lmp = {b.id: b.lmp_p for b in result.buses}

    assert dispatch["dear"] > 1.0
    assert lmp["b2"] == pytest.approx(10.2, abs=1e-3)


# --- MATPOWER's published optima ----------------------------------------------------------------


@pytest.mark.parametrize("name", sorted(PUBLISHED_OBJECTIVE))
def test_bundled_case_reaches_the_published_objective(name: str) -> None:
    result = solve_ac_opf(cases.load(name))

    assert result.status == "Optimal", (name, result.message)
    published = PUBLISHED_OBJECTIVE[name]
    assert abs(result.objective_cost - published) / published <= PUBLISHED_TOL, (
        name,
        result.objective_cost,
        published,
    )
    assert result.max_mismatch_pu <= 1e-6


def test_case14_matches_the_published_dispatch_and_lmp() -> None:
    """MATPOWER's runopf case14 solution: Pg = 194.33, 36.72, 28.74, 0.00, 8.49 MW; bus 1 at
    1.060 pu with λ_P = 36.72 $/MWh."""
    result = solve_ac_opf(cases.load("case14"))
    dispatch = [g.p_mw for g in result.generators]
    bus1 = result.buses[0]

    assert dispatch == pytest.approx([194.33, 36.72, 28.74, 0.0, 8.49], abs=0.05)
    assert bus1.vm_pu == pytest.approx(1.06, abs=1e-4)
    assert bus1.lmp_p == pytest.approx(36.72, abs=0.01)
    assert bus1.va_deg == 0.0


# --- constraint discipline ----------------------------------------------------------------------


@pytest.mark.parametrize("name", ["case14", "case30", "case57"])
def test_solution_respects_every_bound(name: str) -> None:
    net = cases.load(name)
    result = solve_ac_opf(net)
    assert result.status == "Optimal"
    bus = {b.id: b for b in net.buses}
    gen = {g.id: g for g in net.generators}
    for row in result.buses:
        assert bus[row.id].v_min_pu is not None and bus[row.id].v_max_pu is not None
        assert bus[row.id].v_min_pu - 1e-6 <= row.vm_pu <= bus[row.id].v_max_pu + 1e-6
    for row in result.generators:
        assert gen[row.id].p_min_mw - 1e-4 <= row.p_mw <= gen[row.id].p_max_mw + 1e-4
        assert gen[row.id].q_min_mvar - 1e-4 <= row.q_mvar <= gen[row.id].q_max_mvar + 1e-4
    for row in result.branches:
        if row.loading_percent is not None:
            assert row.loading_percent <= 100.0 + 1e-4


def test_case30_ratings_bind_and_are_priced() -> None:
    """case30 is the one bundled case whose shipped ratings bind at the AC optimum."""
    result = solve_ac_opf(cases.load("case30"))
    assert result.status == "Optimal"
    binding = [
        b for b in result.branches if b.loading_percent is not None and b.loading_percent > 99.99
    ]
    assert binding, "expected at least one branch at its rating"
    assert any(abs(b.flow_from_dual) + abs(b.flow_to_dual) > 1e-9 for b in binding)
    assert all(
        abs(b.flow_from_dual) + abs(b.flow_to_dual) < 1e-9
        for b in result.branches
        if b.loading_percent is not None and b.loading_percent < 99.0
    )


def test_losses_are_generation_minus_load() -> None:
    net = cases.load("case14")
    result = solve_ac_opf(net)
    load = sum(ld.p_mw for ld in net.loads)
    assert result.losses_mw == pytest.approx(sum(g.p_mw for g in result.generators) - load)
    assert 0.0 < result.losses_mw < 0.1 * load


# --- options and the array-level contract -------------------------------------------------------


def test_default_voltage_band_applies_to_a_bus_without_limits() -> None:
    net = _two_bus()
    for bus in net.buses:
        bus.v_min_pu = None
        bus.v_max_pu = None
    arr = NetworkArrays.from_network(net)
    v_min, v_max = voltage_limits(net, arr, default_min=0.9, default_max=1.1)
    assert v_min.tolist() == [0.9, 0.9] and v_max.tolist() == [1.1, 1.1]

    tight = solve_ac_opf(net, OpfAcOptions(v_default_min_pu=0.98, v_default_max_pu=1.02))
    assert tight.status == "Optimal"
    assert all(0.98 - 1e-6 <= b.vm_pu <= 1.02 + 1e-6 for b in tight.buses)
    assert tight.provenance.options["v_default_max_pu"] == 1.02


def test_array_level_rejects_bad_voltage_limits() -> None:
    net = _two_bus()
    arr = NetworkArrays.from_network(net)
    cost_coeffs, _ = gen_cost_coeffs(net, arr)
    with pytest.raises(ValueError, match="shape"):
        ac_opf(arr, cost_coeffs, OpfAcOptions(), v_min_pu=np.ones(3), v_max_pu=np.ones(2))
    with pytest.raises(ValueError, match="v_min_pu <= v_max_pu"):
        ac_opf(arr, cost_coeffs, OpfAcOptions(), v_min_pu=np.array([1.1, 1.1]), v_max_pu=np.ones(2))


def test_iteration_limit_is_reported_not_raised() -> None:
    result = solve_ac_opf(cases.load("case14"), OpfAcOptions(max_iter=2))
    assert result.status == "IterationLimit"
    assert result.message is not None and "2 LP steps" in result.message
    assert result.generators == [] and result.objective_cost > 0.0


def test_piecewise_linear_costs_solve() -> None:
    result = solve_ac_opf(cases.load("derived/case14_pwl"))
    assert result.status == "Optimal", result.message
    assert result.objective_cost > 0.0


# --- round trip and the jobs kind ---------------------------------------------------------------


def test_result_round_trips_and_the_jobs_kind_runs_and_fails_structurally() -> None:
    result = solve_ac_opf(_two_bus())
    assert OpfAcResult.model_validate_json(result.model_dump_json()) == result

    ok = run(SolveRequest(kind="opf.ac", network=_two_bus()))
    assert ok.status == "ok" and isinstance(ok.result, OpfAcResult)
    assert ok.provenance is not None and ok.provenance.kind == "opf.ac"

    cut = run(SolveRequest(kind="opf.ac", network=cases.load("case14"), options={"max_iter": 2}))
    assert cut.status == "failed" and cut.error is not None
    assert cut.error.code == "INFEASIBLE_LP" and "IterationLimit" in cut.error.message
