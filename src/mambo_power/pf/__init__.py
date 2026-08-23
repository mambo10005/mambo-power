"""Power-flow solvers (epic Design §2 ``pf/``): AC Newton-Raphson (W1) and DC (W2).

Public entry points take and return pydantic models (a :class:`~mambo_power.model.Network` in,
a typed result out) and stamp provenance; the array-level solvers
(:func:`mambo_power.pf.ac_newton.newton`, :func:`mambo_power.pf.dc.solve`) work on
:class:`~mambo_power.numerics.NetworkArrays` only. Both entry points derive the bus roles
through :func:`mambo_power.numerics.effective_roles` (W3) — a PV bus without an in-service
generator solves as PQ, a slack without one raises
:class:`~mambo_power.numerics.NoSlackGeneratorError`, and a
:class:`~mambo_power.numerics.SetpointConflictWarning` propagates to the caller.
"""

from __future__ import annotations

import math
import time
from datetime import UTC, datetime

import numpy as np
import numpy.typing as npt

import mambo_power
from mambo_power.model import Network
from mambo_power.numerics import EffectiveRoles, NetworkArrays, effective_roles, yf_yt
from mambo_power.numerics.arrays import BUS_TYPE_CODE
from mambo_power.pf import ac_newton, dc
from mambo_power.pf.ac_newton import AcOptions, AcSolution
from mambo_power.pf.dc import DcSolution
from mambo_power.results import (
    AcPowerFlowResult,
    DcPowerFlowResult,
    ResultProvenance,
    ac_result_from_arrays,
    dc_result_from_arrays,
)

__all__ = [
    "AcOptions",
    "AcSolution",
    "DcSolution",
    "ac_newton",
    "dc",
    "initial_voltage",
    "solve_ac",
    "solve_dc",
]

ComplexArray = npt.NDArray[np.complex128]


def initial_voltage(
    net: Network, arr: NetworkArrays, roles: EffectiveRoles, options: AcOptions
) -> ComplexArray:
    """Starting voltages for :func:`solve_ac` under ``options.init``.

    ``"flat"``: :func:`mambo_power.pf.ac_newton.flat_start`. ``"auto"``: when every in-service
    bus carries both ``vm_pu`` and ``va_deg`` the stored state is the start (angles in radians,
    the slack keeping its stored angle), with PV and slack magnitudes replaced by the effective
    setpoint; otherwise flat.
    """
    if options.init == "auto":
        stored = {b.id: b for b in net.buses if b.in_service}
        if all(b.vm_pu is not None and b.va_deg is not None for b in stored.values()):
            vm = np.array([float(stored[i].vm_pu or 0.0) for i in arr.bus_ids])
            va = np.array([math.radians(float(stored[i].va_deg or 0.0)) for i in arr.bus_ids])
            held = roles.bus_type != BUS_TYPE_CODE["pq"]
            vm[held] = roles.v_set[held]
            return np.asarray(vm * np.exp(1j * va), dtype=np.complex128)
    return ac_newton.flat_start(arr, roles)


def solve_ac(net: Network, *, options: AcOptions | None = None) -> AcPowerFlowResult:
    """AC power flow of ``net`` by Newton-Raphson (:mod:`mambo_power.pf.ac_newton`).

    Builds the in-service :class:`NetworkArrays` and the effective roles, solves with Q-limit
    enforcement per ``options``, computes branch flows ``S_from = V_f · conj(Yf V)`` and
    ``S_to = V_t · conj(Yt V)``, and returns an :class:`~mambo_power.results.AcPowerFlowResult`
    in MW/MVAr keyed by ids with provenance (``kind = "pf.ac"``, ``solver =
    scipy.sparse.linalg.splu``, the options as run). A solve that does not converge is
    reported through ``converged = False`` — never raised. The network is not modified.
    """
    opts = options if options is not None else AcOptions()
    started_at = datetime.now(UTC)
    clock = time.perf_counter()
    arr = NetworkArrays.from_network(net)
    roles = effective_roles(arr)
    v0 = initial_voltage(net, arr, roles, opts)
    sol = ac_newton.newton(arr, roles, opts, v0=v0)
    yf, yt = yf_yt(arr)
    s_from = np.asarray(sol.v[arr.f] * np.conj(yf @ sol.v), dtype=np.complex128)
    s_to = np.asarray(sol.v[arr.t] * np.conj(yt @ sol.v), dtype=np.complex128)
    # reported bus injection = generation − load − shunt: take the shunt's |V|²·conj(g + jb)
    # out of V·conj(Y V) (Y carries the shunts), matching the DC result and pandapower's res_bus
    vm2 = np.abs(sol.v) ** 2
    s_inj = np.asarray(
        sol.s_bus_pu - vm2 * (arr.g_shunt_pu - 1j * arr.b_shunt_pu), dtype=np.complex128
    )
    elapsed_s = time.perf_counter() - clock
    provenance = ResultProvenance(
        engine="mambo-power",
        version=mambo_power.__version__,
        kind="pf.ac",
        solver=ac_newton.SOLVER,
        started_at=started_at,
        elapsed_s=elapsed_s,
        options=opts.model_dump(),
    )
    return ac_result_from_arrays(
        arr,
        v=sol.v,
        s_bus_pu=s_inj,
        s_from_pu=s_from,
        s_to_pu=s_to,
        gen_p_pu=sol.gen_p_pu,
        gen_q_pu=sol.gen_q_pu,
        bus_type=sol.bus_type,
        q_limited=sol.q_limited,
        converged=sol.converged,
        iterations=sol.iterations,
        max_mismatch_pu=sol.max_mismatch_pu,
        q_limit_rounds=sol.q_limit_rounds,
        provenance=provenance,
        message=sol.message,
    )


def solve_dc(net: Network) -> DcPowerFlowResult:
    """DC power flow of ``net``: lossless ``B'θ = P`` with phase shifts, flows via ``Bf``.

    Builds the in-service :class:`NetworkArrays`, runs :func:`mambo_power.pf.dc.solve`, and
    returns a :class:`~mambo_power.results.DcPowerFlowResult` in MW keyed by ids, with
    provenance (``version = mambo_power.__version__``, ``solver = scipy.sparse.linalg.splu``,
    UTC start time, wall-clock duration). ``role_effective`` reports the effective roles (W3):
    the solve itself needs no setpoints, but a slack without an in-service generator is still
    an error and a gen-less PV bus is reported as PQ. The network is not modified.
    """
    started_at = datetime.now(UTC)
    clock = time.perf_counter()
    arr = NetworkArrays.from_network(net)
    roles = effective_roles(arr)
    sol = dc.solve(arr)
    elapsed_s = time.perf_counter() - clock
    provenance = ResultProvenance(
        engine="mambo-power",
        version=mambo_power.__version__,
        kind="pf.dc",
        solver=dc.SOLVER,
        started_at=started_at,
        elapsed_s=elapsed_s,
        options={},
    )
    return dc_result_from_arrays(
        arr,
        theta_rad=sol.theta_rad,
        p_from_pu=sol.p_from_pu,
        p_inj_pu=sol.p_inj_pu,
        gen_p_pu=sol.gen_p_pu,
        provenance=provenance,
        bus_type=roles.bus_type,
    )
