"""AC power flow by polar Newton-Raphson over :class:`~mambo_power.numerics.NetworkArrays` (W1).

Formulation (MATPOWER ``newtonpf``). With the bus admittance matrix ``Y``
(:func:`mambo_power.numerics.ybus`), the complex voltages ``V = Vm·e^{jVa}`` and the specified
net injections ``S_spec = (P_gen − P_load) + j(Q_gen − Q_load)`` in per unit (shunts live in
``Y``), the mismatch is::

    ΔS = V · conj(Y V) − S_spec
    F  = [ real(ΔS)[pv ∪ pq] ; imag(ΔS)[pq] ]

The state is ``x = [Va[pv ∪ pq]; Vm[pq]]`` and each iteration solves ``J·Δx = −F`` with the
Jacobian assembled from the sparse partial derivatives (MATPOWER ``dSbus_dV``, polar)::

    ∂S/∂Vm = diag(V) · conj(Y · diag(V/|V|)) + conj(diag(Y V)) · diag(V/|V|)
    ∂S/∂Va = j · diag(V) · conj(diag(Y V) − Y · diag(V))

    J = [ real(∂S/∂Va)[pvpq, pvpq]   real(∂S/∂Vm)[pvpq, pq] ]
        [ imag(∂S/∂Va)[pq,   pvpq]   imag(∂S/∂Vm)[pq,   pq] ]

factorised with ``scipy.sparse.linalg.splu``. The mismatch is tested **before** each step, so a
start that already satisfies ``‖F‖∞ ≤ tol`` reports zero iterations; the loop stops with
``converged = False`` after ``max_iter`` updates, on a singular Jacobian, or when an update
produces a non-finite voltage (the last finite iterate is returned).

Start. Flat: ``Vm = 1, Va = 0`` at PQ buses, ``Vm = v_set`` (the effective setpoint from
:func:`mambo_power.numerics.effective_roles`) and ``Va = 0`` at PV and slack buses. Warm: a
caller-supplied ``v0`` (``solve_ac`` builds one from the buses' stored ``vm_pu``/``va_deg`` under
``init="auto"``); PV and slack magnitudes are always overridden by the setpoint. The slack angle
is whatever the start carries (0 for flat).

Q-limit enforcement (pandapower semantics, spec design item 3; pandapower 3.3.0
``pf/run_newton_raphson_pf.py:182-249`` ``_run_ac_pf_with_qlims_enforced``, itself MATPOWER
``runpf.m:366-440`` with ``pf.enforce_q_lims = 1``). After every converged Newton solve the
reactive generation per bus is ``Qg = imag(V·conj(Y V)) + Q_load``; every bus still PV whose
``Qg > ΣQmax`` or ``Qg < ΣQmin`` (aggregate over its in-service generators, **strict**
comparison — pandapower ``:199-200``; MATPOWER adds a 5e-6 ``opf.violation`` slack, pandapower
does not) is converted to PQ with ``Q_spec = Q_limit − Q_load`` (``:224-242``: the generator's
``QG`` is pinned at the limit and folded into the bus load). All violators of a round are
converted together (``enforce_q_lims=1``, simultaneous), the next solve warm-starts from the
current voltages, and pins **accumulate — a pinned bus is never restored to PV**
(``limited = r_[limited, mx]``, ``:235``; the spec rejects the restore). The slack bus is never
converted (``setdiff1d(changed_gens, ref)``, ``:227``). The loop ends when a converged solve shows
no new violation; if violations persist after ``max_q_rounds`` re-solves the result carries
``converged = False`` and a diagnostic (pandapower would raise ``LoadflowNotConverged``). A
Newton solve that fails to converge ends the loop immediately without pinning.

Generator allocation (MATPOWER ``pfsoln``; pandapower ``pypower/pfsoln.py:109-141`` is a
verbatim copy). Active power: every generator keeps its dispatch except the **first in-service
generator at the slack bus**, which absorbs the slack-bus balance (the rule ``pf.dc`` already
applies). Reactive power: the bus total ``Qg_bus = imag(S) + Q_load`` is split among the bus's
in-service generators — equally when every generator's range is zero, otherwise
``Qg_i = Qmin_i + (Qg_bus − ΣQmin) / (ΣQmax − ΣQmin) · (Qmax_i − Qmin_i)`` (proportional to
each generator's reactive range). A pinned bus's generators therefore sit exactly at their
individual limits.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

import numpy as np
import numpy.typing as npt
from pydantic import BaseModel, ConfigDict, Field
from scipy import sparse
from scipy.sparse.linalg import splu

from mambo_power.numerics.arrays import BUS_TYPE_CODE, NetworkArrays
from mambo_power.numerics.roles import EffectiveRoles
from mambo_power.numerics.ybus import ybus
from mambo_power.pf._common import absorb_slack_p

FloatArray = npt.NDArray[np.float64]
IntArray = npt.NDArray[np.int64]
ComplexArray = npt.NDArray[np.complex128]

SOLVER = "scipy.sparse.linalg.splu"
"""Linear-algebra backend name stamped into the result provenance."""

_DIVERGENCE_FACTOR = 1e6
"""Stop a Newton solve once ‖F‖∞ exceeds this multiple of its starting value.

Caller-controlled ``max_iter`` is now bounded (:class:`AcOptions`), but a genuinely diverging
start can still burn the whole bound doing no useful work — this catches that case without
touching the well-behaved (converging or merely slow) ones, which never grow past their own
starting mismatch by anywhere near this factor."""

_PQ, _PV, _SLACK = BUS_TYPE_CODE["pq"], BUS_TYPE_CODE["pv"], BUS_TYPE_CODE["slack"]


class AcOptions(BaseModel):
    """Options of the AC Newton-Raphson solve (spec design item 1).

    ``tol`` is compared against the infinity norm of the per-unit power mismatch (MATPOWER
    ``pf.tol`` semantics; pandapower's ``tolerance_mva`` is the same pu quantity despite its
    name). ``init="auto"`` warm-starts from the buses' stored ``vm_pu``/``va_deg`` when every
    in-service bus carries both, else flat; PV and slack magnitudes are always the setpoint.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    tol: float = Field(default=1e-8, gt=0.0, description="Mismatch ∞-norm tolerance, pu.")
    max_iter: int = Field(default=20, ge=1, le=1000, description="Newton iterations per solve.")
    q_limits: bool = Field(default=True, description="Enforce generator reactive limits.")
    max_q_rounds: int = Field(default=10, ge=0, le=100, description="Maximum Q-limit re-solves.")
    init: Literal["auto", "flat"] = Field(default="auto", description="Starting point rule.")


@dataclass(frozen=True)
class AcSolution:
    """Positional AC solution in per unit, in :class:`NetworkArrays` order."""

    v: ComplexArray
    """Complex bus voltages (pu, radians inside)."""
    converged: bool
    """Final Newton solve met ``tol`` and no Q-limit violation remained."""
    iterations: int
    """Newton iterations summed over every Q-limit round."""
    max_mismatch_pu: float
    """Infinity norm of the final mismatch vector, pu."""
    q_limit_rounds: int
    """Number of re-solves triggered by pinning (0 when nothing was pinned)."""
    q_limited: IntArray
    """Per bus: 0 free, +1 pinned at ΣQmax, -1 pinned at ΣQmin."""
    bus_type: IntArray
    """Effective bus types after pinning (1 = pq, 2 = pv, 3 = slack)."""
    s_bus_pu: ComplexArray
    """Realised net complex injection per bus ``V·conj(Y V)``."""
    gen_p_pu: FloatArray
    """Per-generator active output; the first slack-bus generator absorbs the balance."""
    gen_q_pu: FloatArray
    """Per-generator reactive output, split by the MATPOWER ``pfsoln`` rule."""
    message: str | None = None
    """Diagnostic when ``converged`` is False; ``None`` otherwise."""


def flat_start(arr: NetworkArrays, roles: EffectiveRoles) -> ComplexArray:
    """``1∠0`` at PQ buses, ``v_set∠0`` at PV and slack buses (effective roles)."""
    vm = np.ones(arr.n_bus)
    held = roles.bus_type != _PQ
    vm[held] = roles.v_set[held]
    return np.asarray(vm, dtype=np.complex128)


def specified_injection(arr: NetworkArrays) -> ComplexArray:
    """``(P_gen − P_load) + j(Q_gen − Q_load)`` per bus, pu; shunts are in ``Y``, not here."""
    return np.asarray(
        (arr.p_gen_pu - arr.p_load_pu) + 1j * (arr.q_gen_pu - arr.q_load_pu),
        dtype=np.complex128,
    )


def _dsbus_dv(y: Any, v: ComplexArray) -> tuple[Any, Any]:
    """MATPOWER ``dSbus_dV`` (polar): ``(dS/dVm, dS/dVa)`` as sparse matrices."""
    ibus = y @ v
    diag_v = sparse.diags(v)
    diag_i = sparse.diags(ibus)
    diag_vnorm = sparse.diags(v / np.abs(v))
    ds_dvm = diag_v @ (y @ diag_vnorm).conj() + diag_i.conj() @ diag_vnorm
    ds_dva = 1j * diag_v @ (diag_i - y @ diag_v).conj()
    return ds_dvm, ds_dva


def newton_raphson(
    y: Any,
    s_spec: ComplexArray,
    v0: ComplexArray,
    pv: IntArray,
    pq: IntArray,
    *,
    tol: float,
    max_iter: int,
) -> tuple[ComplexArray, bool, int, float, str | None]:
    """One Newton solve (MATPOWER ``newtonpf``): ``(V, converged, iterations, ‖F‖∞, message)``."""
    v = v0.astype(np.complex128, copy=True)
    va = np.angle(v)
    vm = np.abs(v)
    pvpq = np.concatenate([pv, pq])
    n_a = pvpq.size
    n_m = pq.size

    def mismatch(v: ComplexArray) -> FloatArray:
        ds = v * np.conj(y @ v) - s_spec
        return np.asarray(np.concatenate([ds.real[pvpq], ds.imag[pq]]), dtype=np.float64)

    f = mismatch(v)
    norm = float(np.max(np.abs(f))) if f.size else 0.0
    norm0 = norm
    converged = bool(np.isfinite(norm) and norm <= tol)
    iterations = 0
    message: str | None = None
    while not converged and iterations < max_iter:
        iterations += 1
        ds_dvm, ds_dva = _dsbus_dv(y, v)
        j11 = ds_dva[pvpq, :][:, pvpq].real
        j12 = ds_dvm[pvpq, :][:, pq].real
        j21 = ds_dva[pq, :][:, pvpq].imag
        j22 = ds_dvm[pq, :][:, pq].imag
        jac = sparse.bmat([[j11, j12], [j21, j22]], format="csc")
        try:
            dx = -splu(jac).solve(f)
        except RuntimeError as exc:  # SuperLU: "Factor is exactly singular"
            message = f"singular Jacobian at iteration {iterations} ({exc})"
            break
        va_new = va.copy()
        vm_new = vm.copy()
        va_new[pvpq] += dx[:n_a]
        vm_new[pq] += dx[n_a : n_a + n_m]
        v_new = np.asarray(vm_new * np.exp(1j * va_new), dtype=np.complex128)
        if not np.all(np.isfinite(v_new)):
            message = f"non-finite voltage at iteration {iterations}"
            break
        v = v_new
        vm = np.abs(v)  # MATPOWER: re-normalise so a negative Vm step flips the angle
        va = np.angle(v)
        f = mismatch(v)
        norm = float(np.max(np.abs(f))) if f.size else 0.0
        if not np.isfinite(norm):
            message = f"non-finite mismatch at iteration {iterations}"
            break
        if norm0 > 0.0 and norm > _DIVERGENCE_FACTOR * norm0:
            message = (
                f"diverging: ‖F‖∞ = {norm:.3e} pu exceeds "
                f"{_DIVERGENCE_FACTOR:.0e}× the starting mismatch ({norm0:.3e} pu) "
                f"at iteration {iterations}"
            )
            break
        converged = norm <= tol
    if not converged and message is None:
        message = f"did not converge in {max_iter} iterations (‖F‖∞ = {norm:.3e} pu)"
    return v, converged, iterations, norm, message


def allocate_generation(
    arr: NetworkArrays, s_bus: ComplexArray, q_limited: IntArray
) -> tuple[FloatArray, FloatArray]:
    """Per-generator ``(P, Q)`` from the bus totals: MATPOWER ``pfsoln`` rules (module docstring).

    A pinned bus (``q_limited`` ±1) reports exactly its aggregate limit rather than the solved
    ``imag(S) + Q_load``, which differs from it by the convergence tolerance (pandapower restores
    ``fixedQg`` the same way, ``run_newton_raphson_pf.py:246``).
    """
    n_gen = len(arr.gen_ids)
    gen_q = np.zeros(n_gen)
    if n_gen == 0:
        return arr.gen_p_pu.copy(), gen_q
    p_bus = float(s_bus[arr.slack].real + arr.p_load_pu[arr.slack])
    gen_p = absorb_slack_p(arr, p_bus)
    q_bus = s_bus.imag + arr.q_load_pu
    q_bus[q_limited == 1] = arr.q_max_pu[q_limited == 1]
    q_bus[q_limited == -1] = arr.q_min_pu[q_limited == -1]
    counts = np.bincount(arr.gen_bus, minlength=arr.n_bus)
    for position in np.flatnonzero(counts):
        rows = np.flatnonzero(arr.gen_bus == position)
        q_min = arr.gen_q_min_pu[rows]
        q_max = arr.gen_q_max_pu[rows]
        total_range = float(np.sum(q_max - q_min))
        if total_range > 0.0:
            share = (q_bus[position] - float(np.sum(q_min))) / total_range
            gen_q[rows] = q_min + share * (q_max - q_min)
        else:
            gen_q[rows] = q_bus[position] / rows.size
    return gen_p, gen_q


def newton(
    arr: NetworkArrays,
    roles: EffectiveRoles,
    opts: AcOptions,
    v0: ComplexArray | None = None,
) -> AcSolution:
    """Solve the AC power flow of ``arr`` with the effective ``roles`` (module docstring).

    ``v0`` is the starting voltage (flat start when ``None``); PV and slack magnitudes in it are
    replaced by the effective setpoints. Never raises for a non-converged solve — the result
    carries ``converged = False`` and a ``message``.
    """
    y = ybus(arr)
    s_spec = specified_injection(arr)
    bus_type = roles.bus_type.copy()
    q_limited = np.zeros(arr.n_bus, dtype=np.int64)
    if v0 is None:
        v = flat_start(arr, roles)
    else:
        v = np.asarray(v0, dtype=np.complex128).copy()
        held = bus_type != _PQ
        v[held] = roles.v_set[held] * np.exp(1j * np.angle(v[held]))

    total_iterations = 0
    rounds = 0
    message: str | None = None
    while True:
        pv = np.flatnonzero(bus_type == _PV).astype(np.int64)
        pq = np.flatnonzero(bus_type == _PQ).astype(np.int64)
        v, converged, iterations, norm, message = newton_raphson(
            y, s_spec, v, pv, pq, tol=opts.tol, max_iter=opts.max_iter
        )
        total_iterations += iterations
        if not converged or not opts.q_limits:
            break
        s_calc = v * np.conj(y @ v)
        q_gen = s_calc.imag + arr.q_load_pu
        over = pv[q_gen[pv] > arr.q_max_pu[pv]]
        under = pv[q_gen[pv] < arr.q_min_pu[pv]]
        if over.size == 0 and under.size == 0:
            break
        if rounds >= opts.max_q_rounds:
            converged = False
            violators = [arr.bus_ids[i] for i in np.concatenate([over, under])]
            message = (
                f"Q-limit enforcement did not settle within max_q_rounds={opts.max_q_rounds}; "
                f"still violating: {violators}"
            )
            break
        rounds += 1
        bus_type[over] = _PQ
        bus_type[under] = _PQ
        q_limited[over] = 1
        q_limited[under] = -1
        s_spec[over] = s_spec[over].real + 1j * (arr.q_max_pu[over] - arr.q_load_pu[over])
        s_spec[under] = s_spec[under].real + 1j * (arr.q_min_pu[under] - arr.q_load_pu[under])

    s_bus = np.asarray(v * np.conj(y @ v), dtype=np.complex128)
    gen_p, gen_q = allocate_generation(arr, s_bus, q_limited)
    return AcSolution(
        v=v,
        converged=converged,
        iterations=total_iterations,
        max_mismatch_pu=norm,
        q_limit_rounds=rounds,
        q_limited=q_limited,
        bus_type=bus_type,
        s_bus_pu=s_bus,
        gen_p_pu=gen_p,
        gen_q_pu=gen_q,
        message=None if converged else message,
    )
