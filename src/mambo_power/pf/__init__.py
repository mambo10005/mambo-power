"""Power-flow solvers (epic Design §2 ``pf/``): DC now, AC Newton-Raphson in W1.

Public entry points take and return pydantic models (a :class:`~mambo_power.model.Network` in,
a typed result out) and stamp provenance; the array-level solvers
(:func:`mambo_power.pf.dc.solve`) work on :class:`~mambo_power.numerics.NetworkArrays` only.
"""

from __future__ import annotations

import time
from datetime import UTC, datetime

import mambo_power
from mambo_power.model import Network
from mambo_power.numerics import NetworkArrays
from mambo_power.pf import dc
from mambo_power.pf.dc import DcSolution
from mambo_power.results import DcPowerFlowResult, ResultProvenance, dc_result_from_arrays

__all__ = ["DcSolution", "dc", "solve_dc"]


def solve_dc(net: Network) -> DcPowerFlowResult:
    """DC power flow of ``net``: lossless ``B'θ = P`` with phase shifts, flows via ``Bf``.

    Builds the in-service :class:`NetworkArrays`, runs :func:`mambo_power.pf.dc.solve`, and
    returns a :class:`~mambo_power.results.DcPowerFlowResult` in MW keyed by ids, with
    provenance (``version = mambo_power.__version__``, ``solver = scipy.sparse.linalg.splu``,
    UTC start time, wall-clock duration). The network is not modified.
    """
    started_at = datetime.now(UTC)
    clock = time.perf_counter()
    arr = NetworkArrays.from_network(net)
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
    )
