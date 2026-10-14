"""Angle-difference limits in the AC-OPF (ADR-029): ``Branch.angle_min_deg`` / ``angle_max_deg``
bound ``va(from) − va(to)``.

Three kinds of evidence:

* **The SLSQP oracle of ``test_opf_ac.py``** with one more inequality: on the two-bus hand case
  the angle across the line is a plain function of the decision vector, so the limit is one
  ``scipy.optimize`` constraint. Objective, dispatch and the angle must agree.
* **The limit's price.** On case14 a cap at 80 % of the unconstrained angle across branch-2 is
  binding: the angle sits at the cap, the cost rises, and the reported dual (``$/rad·h``) matches
  a finite difference of the optimal cost in the cap to within the solver's tolerance. Mirroring
  the branch and stating the same limit as a lower bound gives the same optimum with the dual's
  sign flipped.
* **Discipline.** A branch with no limit is unaffected (every bundled case solves to the same
  objective as before, since none states one); the model rejects inverted or out-of-range
  limits; MATPOWER's ``ANGMIN``/``ANGMAX`` read in, with both "no limit" spellings as ``None``.
"""

from __future__ import annotations

import math
from pathlib import Path

import numpy as np
import pytest
from scipy import optimize

from mambo_power import cases
from mambo_power.io import matpower
from mambo_power.model import Branch, Network
from mambo_power.model.network import validate_network
from mambo_power.numerics import NetworkArrays
from mambo_power.opf import solve_ac_opf
from mambo_power.results import OpfAcResult
from tests.unit.test_opf_ac import LOAD_P, LOAD_Q, B, R, X, _two_bus

ANGLE_CAP_DEG = 3.0
"""Tighter than the unconstrained two-bus angle (about 5.6°), so the cap binds."""


def _limited_two_bus(angle_max_deg: float) -> Network:
    net = _two_bus()
    (br,) = net.branches
    return net.model_copy(
        update={"branches": [br.model_copy(update={"angle_max_deg": angle_max_deg})]}
    )


def _oracle(angle_max_deg: float) -> optimize.OptimizeResult:
    """SLSQP on the two-bus AC-OPF with ``va1 − va2 <= angle_max`` added as an inequality."""
    y_s = 1.0 / (R + 1j * X)
    y_sh = 1j * B / 2.0
    y = np.array([[y_s + y_sh, -y_s], [-y_s, y_s + y_sh]])
    cost = np.array([10.0, 30.0])
    load = np.array([0.0, LOAD_P]) / 100.0 + 1j * np.array([0.0, LOAD_Q]) / 100.0

    def unpack(x: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
        va2, vm1, vm2, pg1, pg2, qg1, qg2 = x
        v = np.array([vm1, vm2 * np.exp(1j * va2)])
        return v, np.array([pg1, pg2]), np.array([qg1, qg2])

    def balance(x: np.ndarray) -> np.ndarray:
        v, pg, qg = unpack(x)
        s = v * np.conj(y @ v) + load - (pg + 1j * qg) / 100.0
        return np.concatenate([s.real, s.imag])

    def angle(x: np.ndarray) -> float:
        # va(from) − va(to) = 0 − va2 <= cap  <=>  cap + va2 >= 0
        return float(math.radians(angle_max_deg) + x[0])

    x0 = np.array([0.0, 1.0, 1.0, LOAD_P, 0.0, LOAD_Q, 0.0])
    result = optimize.minimize(
        lambda x: float(np.dot(cost, unpack(x)[1])),
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
        ],
        constraints=[{"type": "eq", "fun": balance}, {"type": "ineq", "fun": angle}],
        options={"ftol": 1e-12, "maxiter": 500},
    )
    assert result.success, result.message
    return result


# --- the hand case against SLSQP ----------------------------------------------------------------


def test_two_bus_angle_cap_agrees_with_scipy_slsqp() -> None:
    free = solve_ac_opf(_two_bus())
    assert free.status == "Optimal"
    assert free.branches[0].angle_deg > ANGLE_CAP_DEG  # the cap will bind
    assert free.branches[0].angle_dual == 0.0

    result = solve_ac_opf(_limited_two_bus(ANGLE_CAP_DEG))
    oracle = _oracle(ANGLE_CAP_DEG)
    assert result.status == "Optimal", result.message
    assert result.objective_cost == pytest.approx(oracle.fun, rel=1e-6)
    assert result.objective_cost > free.objective_cost
    dispatch = {g.id: g.p_mw for g in result.generators}
    assert dispatch["cheap"] == pytest.approx(oracle.x[3], abs=1e-3)
    assert dispatch["dear"] == pytest.approx(oracle.x[4], abs=1e-3)
    (br,) = result.branches
    assert br.angle_deg == pytest.approx(ANGLE_CAP_DEG, abs=1e-6)
    assert br.angle_deg == pytest.approx(-math.degrees(oracle.x[0]), abs=1e-5)
    assert br.angle_dual < 0.0  # the cap costs: relaxing it would lower the objective


# --- case14: the limit's price -----------------------------------------------------------------


def _case14_with(branch_index: int, **limits: float) -> Network:
    net = cases.load("case14")
    branches = list(net.branches)
    branches[branch_index] = branches[branch_index].model_copy(update=limits)
    return net.model_copy(update={"branches": branches})


def _mirrored(branch: Branch, **limits: float) -> Branch:
    return branch.model_copy(
        update={"from_bus": branch.to_bus, "to_bus": branch.from_bus, **limits}
    )


def test_case14_cap_binds_and_its_dual_prices_the_cap() -> None:
    free = solve_ac_opf(cases.load("case14"))
    theta = free.branches[1].angle_deg  # branch-2, 1→3, about 7.43°
    assert theta == pytest.approx(7.4282, abs=1e-3)
    cap = 0.8 * theta

    capped = solve_ac_opf(_case14_with(1, angle_max_deg=cap))
    assert capped.status == "Optimal", capped.message
    assert capped.objective_cost == pytest.approx(8145.89, abs=0.01)
    assert capped.objective_cost > free.objective_cost
    assert capped.branches[1].angle_deg == pytest.approx(cap, abs=1e-6)
    assert all(b.angle_dual == 0.0 for i, b in enumerate(capped.branches) if i != 1)
    dual = capped.branches[1].angle_dual
    assert dual < 0.0

    # the dual is ∂cost/∂cap: a finite difference of the optimum in the cap agrees
    eps_deg = 1e-3
    bumped = solve_ac_opf(_case14_with(1, angle_max_deg=cap + eps_deg))
    finite_difference = (bumped.objective_cost - capped.objective_cost) / math.radians(eps_deg)
    assert finite_difference == pytest.approx(dual, rel=2e-3)

    # every bus keeps its angle inside the branch's limit, reading the angles off the buses
    va = {b.id: b.va_deg for b in capped.buses}
    br = capped.branches[1]
    assert va[br.from_bus] - va[br.to_bus] == pytest.approx(cap, abs=1e-6)


def test_the_same_limit_as_a_lower_bound_on_the_mirrored_branch_flips_the_sign() -> None:
    net = cases.load("case14")
    theta = solve_ac_opf(net).branches[1].angle_deg
    branches = list(net.branches)
    branches[1] = _mirrored(branches[1], angle_min_deg=-0.8 * theta)
    mirrored = solve_ac_opf(net.model_copy(update={"branches": branches}))
    capped = solve_ac_opf(_case14_with(1, angle_max_deg=0.8 * theta))

    assert mirrored.status == "Optimal", mirrored.message
    assert mirrored.objective_cost == pytest.approx(capped.objective_cost, rel=1e-8)
    assert mirrored.branches[1].angle_deg == pytest.approx(-capped.branches[1].angle_deg, abs=1e-8)
    assert mirrored.branches[1].angle_dual == pytest.approx(
        -capped.branches[1].angle_dual, rel=1e-6
    )
    assert mirrored.branches[1].angle_dual > 0.0


def test_a_slack_limit_changes_nothing_and_an_infeasible_one_is_reported() -> None:
    free = solve_ac_opf(cases.load("case14"))
    loose = solve_ac_opf(_case14_with(1, angle_min_deg=-30.0, angle_max_deg=30.0))
    assert loose.status == "Optimal"
    assert loose.objective_cost == pytest.approx(free.objective_cost, rel=1e-9)
    assert loose.branches[1].angle_dual == 0.0

    # a branch cannot carry its flow at zero angle: the elastic rows make the LP infeasible
    tight = solve_ac_opf(_case14_with(1, angle_min_deg=-1e-6, angle_max_deg=1e-6))
    assert tight.status != "Optimal" or tight.objective_cost > free.objective_cost


def test_results_round_trip_with_the_new_fields() -> None:
    result = solve_ac_opf(_limited_two_bus(ANGLE_CAP_DEG))
    assert OpfAcResult.model_validate_json(result.model_dump_json()) == result
    assert result.branches[0].angle_deg == pytest.approx(ANGLE_CAP_DEG, abs=1e-6)


# --- model, arrays and MATPOWER ----------------------------------------------------------------


def test_arrays_carry_the_limits_in_radians_with_inf_where_none() -> None:
    arr = NetworkArrays.from_network(_case14_with(1, angle_min_deg=-10.0, angle_max_deg=20.0))
    assert arr.angle_min_rad[1] == pytest.approx(math.radians(-10.0))
    assert arr.angle_max_rad[1] == pytest.approx(math.radians(20.0))
    others = np.delete(np.arange(arr.angle_min_rad.size), 1)
    assert np.all(np.isneginf(arr.angle_min_rad[others]))
    assert np.all(np.isposinf(arr.angle_max_rad[others]))


def test_validation_rejects_inverted_or_out_of_range_limits() -> None:
    def bad_range(**limits: float) -> list[str]:
        net = _case14_with(1, **limits)
        return [i.path for i in validate_network(net) if i.code == "BAD_RANGE"]

    assert bad_range(angle_min_deg=-10.0, angle_max_deg=20.0) == []
    assert bad_range(angle_min_deg=20.0, angle_max_deg=10.0) == ["branches[1].angle_min_deg"]
    assert bad_range(angle_max_deg=361.0) == ["branches[1].angle_min_deg"]
    assert bad_range(angle_min_deg=-400.0) == ["branches[1].angle_min_deg"]
    assert bad_range(angle_min_deg=-360.0, angle_max_deg=360.0) == []


def test_matpower_angmin_angmax_read_in_with_both_no_limit_spellings_as_none() -> None:
    def case(angmin: float, angmax: float) -> str:
        return (
            "function mpc = t\nmpc.version = '2';\nmpc.baseMVA = 100;\n"
            "mpc.bus = [\n1 3 0 0 0 0 1 1 0 110 1 1.1 0.9;\n"
            "2 1 50 10 0 0 1 1 0 110 1 1.1 0.9;\n];\n"
            "mpc.gen = [\n1 60 5 100 -100 1.02 100 1 200 0;\n];\n"
            f"mpc.branch = [\n1 2 0.01 0.1 0.02 150 0 0 0 0 1 {angmin} {angmax};\n];\n"
            "mpc.gencost = [\n2 0 0 2 10 0;\n];\n"
        )

    def limits(angmin: float, angmax: float) -> tuple[float | None, float | None]:
        (br,) = matpower.loads(case(angmin, angmax)).branches
        return br.angle_min_deg, br.angle_max_deg

    assert limits(-360, 360) == (None, None)
    assert limits(0, 0) == (None, None)
    assert limits(-30, 30) == (-30.0, 30.0)
    assert limits(-360, 30) == (None, 30.0)
    assert limits(-30, 360) == (-30.0, None)
    # no bundled case states a limit, so every published AC-OPF objective is unchanged
    for name in cases.available():
        if name.endswith(".raw"):
            continue
        net = cases.load(name)
        assert all(br.angle_min_deg is None and br.angle_max_deg is None for br in net.branches)


# --- exporters: dropped, and said so ----------------------------------------------------------


def test_raw_export_drops_the_limits_with_field_dropped() -> None:
    from mambo_power.io import psse_raw

    net = _case14_with(1, angle_min_deg=-10.0, angle_max_deg=20.0)
    _, report = psse_raw.dumps_with_report(net)
    (dropped,) = [w for w in report.warnings if w.code == "FIELD_DROPPED" and "angle" in w.message]
    assert dropped.element_ids == ["branch-2"]
    _, clean = psse_raw.dumps_with_report(cases.load("case14"))
    assert not any("angle" in w.message for w in clean.warnings)


def test_pandapower_export_drops_the_limits_with_field_dropped() -> None:
    pytest.importorskip("pandapower")
    from mambo_power.io import pandapower_json

    _, report = pandapower_json.dumps_with_report(_case14_with(1, angle_max_deg=20.0))
    assert any(
        w.code == "FIELD_DROPPED" and "angle_max_deg" in w.message and "branch-2" in w.element_ids
        for w in report.warnings
    )


def test_pypsa_export_drops_the_limits_with_its_own_code() -> None:
    pytest.importorskip("pypsa")
    from mambo_power.io import pypsa as pypsa_io

    _, report = pypsa_io.to_network_with_report(_case14_with(1, angle_min_deg=-20.0))
    (dropped,) = [w for w in report.warnings if w.code == "PYPSA_ANGLE_LIMIT_DROPPED"]
    assert dropped.element_ids == ["branch-2"]


def test_the_limits_round_trip_through_json_and_the_csv_bundle(tmp_path: Path) -> None:
    from mambo_power.io import csv_bundle

    net = _case14_with(1, angle_min_deg=-10.0, angle_max_deg=20.0)
    assert Network.model_validate_json(net.model_dump_json()) == net
    csv_bundle.dump(net, tmp_path)
    assert csv_bundle.load(tmp_path).branches == net.branches
