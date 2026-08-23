"""W1: AC Newton-Raphson on hand-built 3-bus cases, checked against a dense NR written here.

The oracle is an independent dense polar Newton-Raphson: the bus admittance matrix is
assembled with an explicit loop over branches, the Jacobian is built element by element from
the textbook ``H/N/J/L`` formulas (``P_i = V_i Σ V_j (G_ij cos θ_ij + B_ij sin θ_ij)`` …), and
the linear step uses ``numpy.linalg.solve``. Nothing is shared with :mod:`mambo_power.pf` or
:mod:`mambo_power.numerics`.

Base case: bus 1 slack (two generators, the MATPOWER slack rule gives the whole balance to
the first), bus 2 PV (40 MW generator at 1.01 pu), bus 3 PQ (70 MW + 30 MVAr load, a 5 MW
conductive shunt and a 10 MVAr capacitor). Branches: 1-2 line, 2-3 transformer (tap 0.98,
shift +3°, 60 MVA rating), 1-3 line, plus an out-of-service 1-3 line that must not appear.
"""

from __future__ import annotations

import math
import warnings
from typing import Any

import numpy as np
import pytest
from pydantic import ValidationError

from mambo_power.model import Branch, Bus, Generator, Load, Network, Shunt
from mambo_power.numerics import NetworkArrays, SetpointConflictWarning, effective_roles
from mambo_power.pf import AcOptions, AcSolution, solve_ac
from mambo_power.pf import ac_newton as nr
from mambo_power.results import AcPowerFlowResult
from tests._fixtures import FIXTURES_DIR

BASE = 100.0
PQ, PV, SLACK = 1, 2, 3


def generator(
    id: str,
    bus: str,
    p_mw: float,
    *,
    v_set: float = 1.02,
    q_min: float = -100.0,
    q_max: float = 100.0,
    in_service: bool = True,
) -> Generator:
    return Generator(
        id=id,
        bus=bus,
        p_mw=p_mw,
        q_mvar=0.0,
        p_min_mw=0.0,
        p_max_mw=300.0,
        q_min_mvar=q_min,
        q_max_mvar=q_max,
        v_set_pu=v_set,
        in_service=in_service,
    )


def three_bus(
    *,
    q_min_2: float = -100.0,
    q_max_2: float = 100.0,
    v_set_2: float = 1.01,
    load_p_mw: float = 70.0,
    load_q_mvar: float = 30.0,
) -> Network:
    return Network(
        base_mva=BASE,
        buses=[
            Bus(id="bus-1", base_kv=230.0, type="slack"),
            Bus(id="bus-2", base_kv=230.0, type="pv"),
            Bus(id="bus-3", base_kv=115.0, type="pq"),
        ],
        branches=[
            Branch(id="br-12", from_bus="bus-1", to_bus="bus-2", r=0.01, x=0.10, b=0.02),
            Branch(
                id="xf-23",
                from_bus="bus-2",
                to_bus="bus-3",
                r=0.005,
                x=0.20,
                b=0.0,
                tap_ratio=0.98,
                shift_deg=3.0,
                rating_mva=60.0,
            ),
            Branch(id="br-13", from_bus="bus-1", to_bus="bus-3", r=0.02, x=0.25, b=0.04),
            Branch(
                id="br-13-out",
                from_bus="bus-1",
                to_bus="bus-3",
                r=0.02,
                x=0.25,
                b=0.04,
                in_service=False,
            ),
        ],
        generators=[
            generator("gen-1a", "bus-1", 10.0),
            generator("gen-1b", "bus-1", 12.0),
            generator("gen-2", "bus-2", 40.0, v_set=v_set_2, q_min=q_min_2, q_max=q_max_2),
        ],
        loads=[Load(id="load-3", bus="bus-3", p_mw=load_p_mw, q_mvar=load_q_mvar)],
        shunts=[Shunt(id="shunt-3", bus="bus-3", g_mw=5.0, b_mvar=10.0)],
    )


# --- the dense oracle ----------------------------------------------------------------------------


def dense_ybus(net: Network) -> tuple[np.ndarray, dict[str, int]]:
    index = {b.id: i for i, b in enumerate(net.buses)}
    n = len(index)
    y = np.zeros((n, n), dtype=complex)
    for br in net.branches:
        if not br.in_service:
            continue
        f, t = index[br.from_bus], index[br.to_bus]
        ys = 1.0 / complex(br.r, br.x)
        tap = 1.0 if br.tap_ratio is None else br.tap_ratio
        shift = 0.0 if br.shift_deg is None else math.radians(br.shift_deg)
        a = tap * complex(math.cos(shift), math.sin(shift))
        y[f, f] += (ys + 1j * br.b / 2) / (tap * tap)
        y[t, t] += ys + 1j * br.b / 2
        y[f, t] += -ys / a.conjugate()
        y[t, f] += -ys / a
    for sh in net.shunts:
        if sh.in_service:
            y[index[sh.bus], index[sh.bus]] += complex(sh.g_mw, sh.b_mvar) / net.base_mva
    return y, index


def dense_newton(
    net: Network, *, tol: float = 1e-12, max_iter: int = 50
) -> tuple[np.ndarray, np.ndarray, int]:
    """Textbook polar NR with an element-wise Jacobian; returns (Vm, Va_rad, iterations)."""
    y, index = dense_ybus(net)
    n = len(index)
    g, b = y.real, y.imag
    p_spec = np.zeros(n)
    q_spec = np.zeros(n)
    vset = np.ones(n)
    for gen in net.generators:
        if gen.in_service:
            p_spec[index[gen.bus]] += gen.p_mw / net.base_mva
            q_spec[index[gen.bus]] += gen.q_mvar / net.base_mva
            vset[index[gen.bus]] = gen.v_set_pu  # last in-service generator wins
    for ld in net.loads:
        if ld.in_service:
            p_spec[index[ld.bus]] -= ld.p_mw / net.base_mva
            q_spec[index[ld.bus]] -= ld.q_mvar / net.base_mva
    types = {index[bus.id]: bus.type for bus in net.buses}
    slack = next(i for i, t in types.items() if t == "slack")
    pv = [i for i, t in types.items() if t == "pv"]
    pq = [i for i, t in types.items() if t == "pq"]
    vm = np.ones(n)
    va = np.zeros(n)
    for i in pv + [slack]:
        vm[i] = vset[i]

    def powers() -> tuple[np.ndarray, np.ndarray]:
        p = np.zeros(n)
        q = np.zeros(n)
        for i in range(n):
            for j in range(n):
                th = va[i] - va[j]
                p[i] += vm[i] * vm[j] * (g[i, j] * math.cos(th) + b[i, j] * math.sin(th))
                q[i] += vm[i] * vm[j] * (g[i, j] * math.sin(th) - b[i, j] * math.cos(th))
        return p, q

    ang = pv + pq
    mag = pq
    for it in range(max_iter + 1):
        p, q = powers()
        f = np.concatenate([(p - p_spec)[ang], (q - q_spec)[mag]])
        if np.max(np.abs(f)) < tol:
            return vm, va, it
        na, nm = len(ang), len(mag)
        jac = np.zeros((na + nm, na + nm))
        for r, i in enumerate(ang):
            for c, j in enumerate(ang):  # dP/dθ
                if i == j:
                    jac[r, c] = -q[i] - b[i, i] * vm[i] ** 2
                else:
                    th = va[i] - va[j]
                    jac[r, c] = vm[i] * vm[j] * (g[i, j] * math.sin(th) - b[i, j] * math.cos(th))
            for c, j in enumerate(mag):  # dP/dV
                if i == j:
                    jac[r, na + c] = p[i] / vm[i] + g[i, i] * vm[i]
                else:
                    th = va[i] - va[j]
                    jac[r, na + c] = vm[i] * (g[i, j] * math.cos(th) + b[i, j] * math.sin(th))
        for r, i in enumerate(mag):
            for c, j in enumerate(ang):  # dQ/dθ
                if i == j:
                    jac[na + r, c] = p[i] - g[i, i] * vm[i] ** 2
                else:
                    th = va[i] - va[j]
                    jac[na + r, c] = (
                        -vm[i] * vm[j] * (g[i, j] * math.cos(th) + b[i, j] * math.sin(th))
                    )
            for c, j in enumerate(mag):  # dQ/dV
                if i == j:
                    jac[na + r, na + c] = q[i] / vm[i] - b[i, i] * vm[i]
                else:
                    th = va[i] - va[j]
                    jac[na + r, na + c] = vm[i] * (g[i, j] * math.sin(th) - b[i, j] * math.cos(th))
        dx = np.linalg.solve(jac, -f)
        for r, i in enumerate(ang):
            va[i] += dx[r]
        for c, j in enumerate(mag):
            vm[j] += dx[na + c]
    raise AssertionError("dense oracle did not converge")


def solve_arrays(net: Network, opts: AcOptions | None = None) -> tuple[NetworkArrays, AcSolution]:
    arr = NetworkArrays.from_network(net)
    roles = effective_roles(arr)
    return arr, nr.newton(arr, roles, opts or AcOptions())


# --- agreement with the dense oracle -------------------------------------------------------------


def test_matches_dense_newton_to_1e_10() -> None:
    net = three_bus()
    vm, va, _ = dense_newton(net)
    arr, sol = solve_arrays(net, AcOptions(q_limits=False))
    assert sol.converged
    np.testing.assert_allclose(np.abs(sol.v), vm, rtol=0, atol=1e-10)
    np.testing.assert_allclose(np.angle(sol.v), va, rtol=0, atol=1e-10)
    assert sol.max_mismatch_pu <= 1e-8
    assert abs(sol.v[arr.slack]) == pytest.approx(1.02) and np.angle(sol.v[arr.slack]) == 0.0


def test_converges_from_flat_in_at_most_six_iterations() -> None:
    _, sol = solve_arrays(three_bus())
    assert sol.converged
    assert 0 < sol.iterations <= 6
    assert sol.q_limit_rounds == 0


def test_warm_start_from_its_own_solution_is_immediate() -> None:
    net = three_bus()
    arr, sol = solve_arrays(net)
    roles = effective_roles(arr)
    warm = nr.newton(arr, roles, AcOptions(), v0=sol.v)
    assert warm.converged
    assert warm.iterations <= 1  # mismatch is tested before the first step: 0 when already solved
    np.testing.assert_allclose(warm.v, sol.v, rtol=0, atol=1e-12)


def test_max_iter_one_returns_not_converged() -> None:
    _, sol = solve_arrays(three_bus(), AcOptions(max_iter=1))
    assert not sol.converged
    assert sol.iterations == 1
    assert sol.max_mismatch_pu > 1e-8
    assert np.all(np.isfinite(sol.v))


def test_max_iter_and_max_q_rounds_are_bounded() -> None:
    """S4.2: unbounded work from caller-controlled options — ``run_json`` hands both straight
    through to an untrusted caller (review m2-review-6axis.md, Security finding 2)."""
    AcOptions(max_iter=1000)  # the ceiling itself is fine
    AcOptions(max_q_rounds=100)
    with pytest.raises(ValidationError):
        AcOptions(max_iter=1001)
    with pytest.raises(ValidationError):
        AcOptions(max_q_rounds=101)


def test_diverging_start_stops_early_with_a_diverging_message() -> None:
    """S4.2: a genuinely diverging start (an extreme overload, far past any Q-limit/physical
    range) is stopped by the divergence guard well short of the (now bounded) ``max_iter``
    cap, rather than burning the whole cap doing no useful work."""
    net = three_bus(load_p_mw=1e11, load_q_mvar=4e10, q_min_2=-1e12, q_max_2=1e12)
    _, sol = solve_arrays(net, AcOptions(max_iter=1000, q_limits=False))
    assert not sol.converged
    assert sol.iterations < 10  # would run to 1000 without the guard
    assert sol.message is not None and "diverging" in sol.message
    assert np.all(np.isfinite(sol.v))


def test_flat_start_holds_setpoints_and_zero_angles() -> None:
    arr = NetworkArrays.from_network(three_bus())
    roles = effective_roles(arr)
    v0 = nr.flat_start(arr, roles)
    assert np.allclose(np.angle(v0), 0.0)
    assert abs(v0[arr.bus_index["bus-1"]]) == 1.02
    assert abs(v0[arr.bus_index["bus-2"]]) == 1.01
    assert abs(v0[arr.bus_index["bus-3"]]) == 1.0


# --- Q-limit enforcement -------------------------------------------------------------------------


def bus2_q_unlimited() -> float:
    """Reactive output the PV bus needs (MVAr) to hold its setpoint when nothing limits it."""
    arr, sol = solve_arrays(three_bus(), AcOptions(q_limits=False))
    i = arr.bus_index["bus-2"]
    return float((sol.s_bus_pu[i].imag + arr.q_load_pu[i]) * BASE)


def test_q_max_pin() -> None:
    needed = bus2_q_unlimited()
    q_max = needed - 5.0  # the setpoint needs more than the generator can give
    arr, sol = solve_arrays(three_bus(q_max_2=q_max))
    i = arr.bus_index["bus-2"]
    assert sol.converged
    assert sol.q_limit_rounds == 1
    assert sol.q_limited[i] == 1 and sol.bus_type[i] == PQ
    assert abs(sol.v[i]) < 1.01  # no longer at the setpoint: less Q than needed -> lower voltage
    assert sol.gen_q_pu[arr.gen_ids.index("gen-2")] * BASE == pytest.approx(q_max, abs=1e-9)
    assert (sol.s_bus_pu[i].imag + arr.q_load_pu[i]) * BASE == pytest.approx(q_max, abs=1e-5)
    assert sol.bus_type[arr.slack] == SLACK and sol.q_limited[arr.slack] == 0


def test_q_min_pin() -> None:
    needed = bus2_q_unlimited()
    q_min = needed + 5.0  # the generator must produce more than the setpoint wants
    arr, sol = solve_arrays(three_bus(q_min_2=q_min, q_max_2=q_min + 50.0))
    i = arr.bus_index["bus-2"]
    assert sol.converged
    assert sol.q_limit_rounds == 1
    assert sol.q_limited[i] == -1 and sol.bus_type[i] == PQ
    assert abs(sol.v[i]) > 1.01  # forced to inject more -> higher voltage
    assert sol.gen_q_pu[arr.gen_ids.index("gen-2")] * BASE == pytest.approx(q_min, abs=1e-9)


def test_q_limits_off_leaves_pv_at_setpoint() -> None:
    needed = bus2_q_unlimited()
    arr, sol = solve_arrays(three_bus(q_max_2=needed - 5.0), AcOptions(q_limits=False))
    i = arr.bus_index["bus-2"]
    assert sol.converged
    assert sol.q_limit_rounds == 0
    assert sol.bus_type[i] == PV and sol.q_limited[i] == 0
    assert abs(sol.v[i]) == pytest.approx(1.01, abs=1e-12)


def test_strict_comparison_does_not_pin_at_the_limit() -> None:
    arr, sol = solve_arrays(three_bus())
    i = arr.bus_index["bus-2"]
    exact = float((sol.s_bus_pu[i].imag + arr.q_load_pu[i]) * BASE)
    # a limit equal to the demand (to floating-point) is not a violation: Qg > Qmax is strict
    _, pinned = solve_arrays(three_bus(q_max_2=exact + 1e-9))
    assert pinned.q_limit_rounds == 0 and pinned.bus_type[i] == PV


def no_restore_case() -> Network:
    """Two PV buses: A runs out of Q (pinned at max); B must inject at least its Qmin.

    After both pins the forced injection at B lifts A's voltage *above* A's setpoint — the
    state in which a restore rule would hand A back to PV. pandapower/MATPOWER do not restore,
    and neither do we: A stays PQ at Qmax with ``vm > v_set``.
    """
    return Network(
        base_mva=BASE,
        buses=[
            Bus(id="bus-1", base_kv=230.0, type="slack"),
            Bus(id="bus-A", base_kv=230.0, type="pv"),
            Bus(id="bus-B", base_kv=230.0, type="pv"),
        ],
        branches=[
            Branch(id="br-1A", from_bus="bus-1", to_bus="bus-A", r=0.02, x=0.20, b=0.0),
            Branch(id="br-AB", from_bus="bus-A", to_bus="bus-B", r=0.01, x=0.10, b=0.0),
        ],
        generators=[
            generator("gen-1", "bus-1", 0.0, v_set=1.0),
            generator("gen-A", "bus-A", 20.0, v_set=1.0, q_min=-100.0, q_max=0.0),
            generator("gen-B", "bus-B", 0.0, v_set=1.0, q_min=40.0, q_max=100.0),
        ],
        loads=[Load(id="load-A", bus="bus-A", p_mw=50.0, q_mvar=20.0)],
    )


def test_no_restore_after_pinning() -> None:
    net = no_restore_case()
    arr, free = solve_arrays(net, AcOptions(q_limits=False))
    a, b = arr.bus_index["bus-A"], arr.bus_index["bus-B"]
    qa = (free.s_bus_pu[a].imag + arr.q_load_pu[a]) * BASE
    qb = (free.s_bus_pu[b].imag + arr.q_load_pu[b]) * BASE
    assert qa > 0.0 and qb < 40.0  # premises: A above Qmax = 0, B below Qmin = 40

    _, sol = solve_arrays(net)
    assert sol.converged
    assert sol.q_limited[a] == 1 and sol.q_limited[b] == -1
    assert sol.bus_type[a] == PQ and sol.bus_type[b] == PQ
    assert abs(sol.v[a]) > 1.0 + 1e-6  # A's voltage is above its setpoint ...
    assert sol.gen_q_pu[arr.gen_ids.index("gen-A")] == pytest.approx(
        0.0, abs=1e-9
    )  # ... yet pinned
    assert sol.gen_q_pu[arr.gen_ids.index("gen-B")] * BASE == pytest.approx(40.0, abs=1e-9)
    assert sol.q_limit_rounds >= 1


def test_max_q_rounds_exhausted_reports_not_converged() -> None:
    needed = bus2_q_unlimited()
    _, sol = solve_arrays(three_bus(q_max_2=needed - 5.0), AcOptions(max_q_rounds=0))
    assert not sol.converged
    assert sol.q_limit_rounds == 0
    assert sol.message is not None and "max_q_rounds" in sol.message


# --- generator allocation ------------------------------------------------------------------------


def test_slack_balance_goes_to_the_first_slack_generator() -> None:
    arr, sol = solve_arrays(three_bus())
    ia, ib = arr.gen_ids.index("gen-1a"), arr.gen_ids.index("gen-1b")
    assert sol.gen_p_pu[ib] * BASE == pytest.approx(12.0)
    p_bus = (sol.s_bus_pu[arr.slack].real + arr.p_load_pu[arr.slack]) * BASE
    assert sol.gen_p_pu[ia] * BASE == pytest.approx(p_bus - 12.0)
    assert sol.gen_p_pu[arr.gen_ids.index("gen-2")] * BASE == pytest.approx(40.0)


def test_slack_q_split_proportional_to_range() -> None:
    net = three_bus()
    net = net.model_copy(
        update={
            "generators": [
                generator("gen-1a", "bus-1", 10.0, q_min=-10.0, q_max=30.0),  # range 40
                generator("gen-1b", "bus-1", 12.0, q_min=-50.0, q_max=70.0),  # range 120
                generator("gen-2", "bus-2", 40.0),
            ]
        }
    )
    arr, sol = solve_arrays(net)
    q_bus = (sol.s_bus_pu[arr.slack].imag + arr.q_load_pu[arr.slack]) * BASE
    ia, ib = arr.gen_ids.index("gen-1a"), arr.gen_ids.index("gen-1b")
    share = (q_bus - (-60.0)) / (100.0 - (-60.0))
    assert sol.gen_q_pu[ia] * BASE == pytest.approx(-10.0 + share * 40.0)
    assert sol.gen_q_pu[ib] * BASE == pytest.approx(-50.0 + share * 120.0)
    assert (sol.gen_q_pu[ia] + sol.gen_q_pu[ib]) * BASE == pytest.approx(q_bus)


def test_zero_range_generators_split_equally() -> None:
    net = three_bus()
    net = net.model_copy(
        update={
            "generators": [
                generator("gen-1a", "bus-1", 10.0, q_min=0.0, q_max=0.0),
                generator("gen-1b", "bus-1", 12.0, q_min=0.0, q_max=0.0),
                generator("gen-2", "bus-2", 40.0),
            ]
        }
    )
    arr, sol = solve_arrays(net)
    ia, ib = arr.gen_ids.index("gen-1a"), arr.gen_ids.index("gen-1b")
    assert sol.gen_q_pu[ia] == pytest.approx(sol.gen_q_pu[ib])
    assert (sol.gen_q_pu[ia] + sol.gen_q_pu[ib]) == pytest.approx(
        sol.s_bus_pu[arr.slack].imag + arr.q_load_pu[arr.slack]
    )


# --- effective roles ------------------------------------------------------------------------------


def test_effective_roles_are_honoured_on_case14_roles() -> None:
    from mambo_power.io import matpower

    net = matpower.load(FIXTURES_DIR / "derived" / "case14_roles.m")
    with pytest.warns(SetpointConflictWarning, match="bus-2"):
        result = solve_ac(net, options=AcOptions(init="flat"))
    assert result.converged
    rows = {b.id: b for b in result.buses}
    assert rows["bus-6"].role_effective == "pq"  # declared PV, its only generator is out
    assert abs(rows["bus-6"].vm_pu - 1.07) > 1e-3
    assert rows["bus-2"].role_effective == "pv"
    assert rows["bus-2"].vm_pu == pytest.approx(1.055, abs=1e-9)  # last generator's setpoint
    assert rows["bus-1"].role_effective == "slack" and rows["bus-1"].va_deg == 0.0


# --- solve_ac: the typed result ------------------------------------------------------------------


def test_solve_ac_result_and_provenance() -> None:
    net = three_bus()
    result = solve_ac(net)
    assert isinstance(result, AcPowerFlowResult)
    assert result.converged and result.iterations > 0 and result.q_limit_rounds == 0
    assert result.max_mismatch_mva <= 1e-8 * BASE
    assert result.provenance.kind == "pf.ac"
    assert result.provenance.solver == "scipy.sparse.linalg.splu"
    assert result.provenance.options == AcOptions().model_dump()
    assert result.provenance.elapsed_s > 0.0
    assert [b.id for b in result.buses] == ["bus-1", "bus-2", "bus-3"]
    assert [b.id for b in result.branches] == ["br-12", "xf-23", "br-13"]
    assert [g.id for g in result.generators] == ["gen-1a", "gen-1b", "gen-2"]
    assert [b.role_effective for b in result.buses] == ["slack", "pv", "pq"]
    assert all(g.q_limited == "none" for g in result.generators)
    # round trip
    again = AcPowerFlowResult.model_validate_json(result.model_dump_json())
    assert again == result


def test_solve_ac_flows_balance_against_injections() -> None:
    result = solve_ac(three_bus())
    arrays = result.to_arrays()
    losses_p = float(np.sum(arrays.p_from_mw + arrays.p_to_mw))
    assert losses_p > 0.0
    # Σ injections = Σ (from + to) flows: what enters the branches is what the buses inject
    assert float(np.sum(arrays.p_bus_mw)) == pytest.approx(losses_p, abs=1e-7)
    assert float(np.sum(arrays.q_bus_mvar)) == pytest.approx(
        float(np.sum(arrays.q_from_mvar + arrays.q_to_mvar)), abs=1e-7
    )
    by_id = {b.id: b for b in result.branches}
    assert by_id["br-12"].loading_pct is None
    xf = by_id["xf-23"]
    assert xf.loading_pct == pytest.approx(math.hypot(xf.p_from_mw, xf.q_from_mvar) / 60.0 * 100.0)
    bus3 = next(b for b in result.buses if b.id == "bus-3")
    # net injection at the PQ bus: -load - shunt(vm²) (conductance consumes, capacitor injects)
    vm3 = bus3.vm_pu
    assert bus3.p_mw == pytest.approx(-70.0 - 5.0 * vm3**2, abs=1e-7)
    assert bus3.q_mvar == pytest.approx(-30.0 + 10.0 * vm3**2, abs=1e-7)


def test_solve_ac_q_limited_generators_are_reported() -> None:
    needed = bus2_q_unlimited()
    result = solve_ac(three_bus(q_max_2=needed - 5.0))
    gen2 = next(g for g in result.generators if g.id == "gen-2")
    assert gen2.q_limited == "max" and gen2.q_mvar == pytest.approx(needed - 5.0, abs=1e-9)
    assert next(b for b in result.buses if b.id == "bus-2").role_effective == "pq"
    assert result.q_limit_rounds == 1


def test_solve_ac_auto_init_warm_starts_from_stored_state() -> None:
    net = three_bus()
    cold = solve_ac(net, options=AcOptions(init="flat"))
    state = {b.id: b for b in cold.buses}
    warm_net = net.model_copy(
        update={
            "buses": [
                b.model_copy(update={"vm_pu": state[b.id].vm_pu, "va_deg": state[b.id].va_deg})
                for b in net.buses
            ]
        }
    )
    warm = solve_ac(warm_net)  # init="auto": every bus carries vm_pu and va_deg
    assert warm.converged and warm.iterations <= 1
    # with one bus lacking a stored state "auto" falls back to flat
    partial = warm_net.model_copy(
        update={
            "buses": [warm_net.buses[0].model_copy(update={"va_deg": None})] + warm_net.buses[1:]
        }
    )
    assert solve_ac(partial).iterations == cold.iterations


def test_solve_ac_not_converged_is_reported_not_raised() -> None:
    result = solve_ac(three_bus(), options=AcOptions(max_iter=1))
    assert not result.converged and result.iterations == 1
    assert result.max_mismatch_mva > 0.0
    assert result.message is not None and "did not converge" in result.message


def test_solve_dc_reports_effective_roles() -> None:
    from mambo_power.io import matpower
    from mambo_power.pf import solve_dc

    net = matpower.load(FIXTURES_DIR / "derived" / "case14_roles.m")
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", SetpointConflictWarning)
        result = solve_dc(net)
    rows: dict[str, Any] = {b.id: b for b in result.buses}
    assert rows["bus-6"].role_effective == "pq"
    assert rows["bus-1"].role_effective == "slack"
