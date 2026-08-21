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
from mambo_power.results.power_flow import DcPowerFlowResult
from mambo_power.results.provenance import ResultProvenance
from mambo_power.results.tables import BranchResult, BusResult, BusRole, GenResult

FloatArray = npt.NDArray[np.float64]

_ROLE_BY_CODE: dict[int, BusRole] = {
    BUS_TYPE_CODE["pq"]: "pq",
    BUS_TYPE_CODE["pv"]: "pv",
    BUS_TYPE_CODE["slack"]: "slack",
}


def _loading_pct(p_from_pu: float, rating_pu: float) -> float | None:
    """``|p_from| / rating`` in percent, or ``None`` when the branch carries no rating."""
    if not math.isfinite(rating_pu):
        return None
    return abs(p_from_pu) / rating_pu * 100.0


def dc_result_from_arrays(
    arr: NetworkArrays,
    *,
    theta_rad: FloatArray,
    p_from_pu: FloatArray,
    p_inj_pu: FloatArray,
    gen_p_pu: FloatArray,
    provenance: ResultProvenance,
) -> DcPowerFlowResult:
    """Map a DC solution in ``arr`` order to a :class:`DcPowerFlowResult` in MW.

    ``theta_rad``/``p_inj_pu`` are per bus, ``p_from_pu`` per branch, ``gen_p_pu`` per generator
    (already carrying the slack balance). Reactive columns are 0, ``vm_pu`` is 1.0 (MATPOWER
    ``rundcpf`` sets ``VM = 1`` everywhere), and ``role_effective`` is the declared role from
    ``arr.bus_type`` until W3's ``effective_roles`` is routed through here.
    """
    if theta_rad.shape != (arr.n_bus,) or p_inj_pu.shape != (arr.n_bus,):
        raise ValueError("bus arrays must have shape (n_bus,)")
    if p_from_pu.shape != (arr.n_branch,):
        raise ValueError("p_from_pu must have shape (n_branch,)")
    if gen_p_pu.shape != (len(arr.gen_ids),):
        raise ValueError("gen_p_pu must have shape (n_gen,)")
    base = arr.base_mva

    buses = [
        BusResult(
            id=arr.bus_ids[i],
            vm_pu=1.0,
            va_deg=math.degrees(float(theta_rad[i])),
            p_mw=float(p_inj_pu[i]) * base,
            q_mvar=0.0,
            role_effective=_ROLE_BY_CODE[int(arr.bus_type[i])],
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
