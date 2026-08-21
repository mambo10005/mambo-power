"""Builders that turn positional solver arrays back into id-keyed result tables.

This is the one place that walks from :class:`~mambo_power.numerics.NetworkArrays` positions
back to ids and multiplies per-unit quantities by ``base_mva`` on the way out. Solvers hand in
plain arrays; nothing here re-derives physics.
"""

from __future__ import annotations

import math

import numpy as np
import numpy.typing as npt

from mambo_power.numerics.arrays import BUS_TYPE_CODE, NetworkArrays
from mambo_power.results.power_flow import AcPowerFlowResult, DcPowerFlowResult
from mambo_power.results.provenance import ResultProvenance
from mambo_power.results.tables import BranchResult, BusResult, BusRole, GenResult, QLimitSide

FloatArray = npt.NDArray[np.float64]
IntArray = npt.NDArray[np.int64]
ComplexArray = npt.NDArray[np.complex128]

_ROLE_BY_CODE: dict[int, BusRole] = {
    BUS_TYPE_CODE["pq"]: "pq",
    BUS_TYPE_CODE["pv"]: "pv",
    BUS_TYPE_CODE["slack"]: "slack",
}


_Q_LIMIT_SIDE: dict[int, QLimitSide] = {0: "none", 1: "max", -1: "min"}


def _loading_pct(s_from_pu: float, rating_pu: float) -> float | None:
    """``|S_from| / rating`` in percent, or ``None`` when the branch carries no rating."""
    if not math.isfinite(rating_pu):
        return None
    return abs(s_from_pu) / rating_pu * 100.0


def dc_result_from_arrays(
    arr: NetworkArrays,
    *,
    theta_rad: FloatArray,
    p_from_pu: FloatArray,
    p_inj_pu: FloatArray,
    gen_p_pu: FloatArray,
    provenance: ResultProvenance,
    bus_type: IntArray | None = None,
) -> DcPowerFlowResult:
    """Map a DC solution in ``arr`` order to a :class:`DcPowerFlowResult` in MW.

    ``theta_rad``/``p_inj_pu`` are per bus, ``p_from_pu`` per branch, ``gen_p_pu`` per generator
    (already carrying the slack balance). Reactive columns are 0, ``vm_pu`` is 1.0 (MATPOWER
    ``rundcpf`` sets ``VM = 1`` everywhere). ``role_effective`` comes from ``bus_type`` — the
    effective roles (W3) when the caller passes them, the declared ``arr.bus_type`` otherwise.
    """
    if theta_rad.shape != (arr.n_bus,) or p_inj_pu.shape != (arr.n_bus,):
        raise ValueError("bus arrays must have shape (n_bus,)")
    if p_from_pu.shape != (arr.n_branch,):
        raise ValueError("p_from_pu must have shape (n_branch,)")
    if gen_p_pu.shape != (len(arr.gen_ids),):
        raise ValueError("gen_p_pu must have shape (n_gen,)")
    base = arr.base_mva
    roles = arr.bus_type if bus_type is None else bus_type

    buses = [
        BusResult(
            id=arr.bus_ids[i],
            vm_pu=1.0,
            va_deg=math.degrees(float(theta_rad[i])),
            p_mw=float(p_inj_pu[i]) * base,
            q_mvar=0.0,
            role_effective=_ROLE_BY_CODE[int(roles[i])],
            in_service=True,
        )
        for i in range(arr.n_bus)
    ]
    branches = [
        BranchResult(
            id=arr.branch_ids[k],
            from_bus=arr.bus_ids[int(arr.f[k])],
            to_bus=arr.bus_ids[int(arr.t[k])],
            p_from_mw=float(p_from_pu[k]) * base,
            q_from_mvar=0.0,
            p_to_mw=-float(p_from_pu[k]) * base,
            q_to_mvar=0.0,
            loading_pct=_loading_pct(float(p_from_pu[k]), float(arr.rating_pu[k])),
        )
        for k in range(arr.n_branch)
    ]
    generators = [
        GenResult(
            id=arr.gen_ids[g],
            bus=arr.bus_ids[int(arr.gen_bus[g])],
            p_mw=float(gen_p_pu[g]) * base,
            q_mvar=0.0,
            q_limited="none",
        )
        for g in range(len(arr.gen_ids))
    ]
    return DcPowerFlowResult(
        provenance=provenance,
        converged=True,
        buses=buses,
        branches=branches,
        generators=generators,
    )


def ac_result_from_arrays(
    arr: NetworkArrays,
    *,
    v: ComplexArray,
    s_bus_pu: ComplexArray,
    s_from_pu: ComplexArray,
    s_to_pu: ComplexArray,
    gen_p_pu: FloatArray,
    gen_q_pu: FloatArray,
    bus_type: IntArray,
    q_limited: IntArray,
    converged: bool,
    iterations: int,
    max_mismatch_pu: float,
    q_limit_rounds: int,
    provenance: ResultProvenance,
) -> AcPowerFlowResult:
    """Map an AC solution in ``arr`` order to an :class:`AcPowerFlowResult` in MW/MVAr/degrees.

    ``v`` and ``s_bus_pu`` are per bus (complex voltage; realised net injection
    ``V·conj(Y V)``), ``s_from_pu``/``s_to_pu`` per branch (complex power entering the branch at
    each end), ``gen_p_pu``/``gen_q_pu`` per generator. ``bus_type`` is the effective role after
    Q-limit pinning and ``q_limited`` the per-bus pin side (0 / +1 max / -1 min), which every
    generator at the bus inherits (limits are enforced on the bus aggregate). Non-finite
    voltages are rejected by the result model, so callers pass the last finite iterate.
    """
    if v.shape != (arr.n_bus,) or s_bus_pu.shape != (arr.n_bus,):
        raise ValueError("bus arrays must have shape (n_bus,)")
    if bus_type.shape != (arr.n_bus,) or q_limited.shape != (arr.n_bus,):
        raise ValueError("bus_type and q_limited must have shape (n_bus,)")
    if s_from_pu.shape != (arr.n_branch,) or s_to_pu.shape != (arr.n_branch,):
        raise ValueError("branch arrays must have shape (n_branch,)")
    n_gen = len(arr.gen_ids)
    if gen_p_pu.shape != (n_gen,) or gen_q_pu.shape != (n_gen,):
        raise ValueError("generator arrays must have shape (n_gen,)")
    base = arr.base_mva

    buses = [
        BusResult(
            id=arr.bus_ids[i],
            vm_pu=float(np.abs(v[i])),
            va_deg=math.degrees(float(np.angle(v[i]))),
            p_mw=float(s_bus_pu[i].real) * base,
            q_mvar=float(s_bus_pu[i].imag) * base,
            role_effective=_ROLE_BY_CODE[int(bus_type[i])],
            in_service=True,
        )
        for i in range(arr.n_bus)
    ]
    branches = [
        BranchResult(
            id=arr.branch_ids[k],
            from_bus=arr.bus_ids[int(arr.f[k])],
            to_bus=arr.bus_ids[int(arr.t[k])],
            p_from_mw=float(s_from_pu[k].real) * base,
            q_from_mvar=float(s_from_pu[k].imag) * base,
            p_to_mw=float(s_to_pu[k].real) * base,
            q_to_mvar=float(s_to_pu[k].imag) * base,
            loading_pct=_loading_pct(float(np.abs(s_from_pu[k])), float(arr.rating_pu[k])),
        )
        for k in range(arr.n_branch)
    ]
    generators = [
        GenResult(
            id=arr.gen_ids[g],
            bus=arr.bus_ids[int(arr.gen_bus[g])],
            p_mw=float(gen_p_pu[g]) * base,
            q_mvar=float(gen_q_pu[g]) * base,
            q_limited=_Q_LIMIT_SIDE[int(q_limited[int(arr.gen_bus[g])])],
        )
        for g in range(n_gen)
    ]
    return AcPowerFlowResult(
        provenance=provenance,
        converged=converged,
        buses=buses,
        branches=branches,
        generators=generators,
        iterations=iterations,
        max_mismatch_mva=max_mismatch_pu * base,
        q_limit_rounds=q_limit_rounds,
    )
