"""DC susceptance matrices and phase-shift injections (MATPOWER ``makeBdc`` conventions).

Per branch ``b = 1 / (x · tap)`` (tap magnitude only; ``r`` and line charging ignored). With
``Cft`` the ``n_branch × n_bus`` from-minus-to incidence matrix::

    Bf   = diag(b) · Cft                 Pf   = Bf · θ + pf_shift
    Bbus = Cftᵀ · Bf                     P    = Bbus · θ + p_shift

where ``pf_shift = -b · shift_rad`` and ``p_shift = Cftᵀ · pf_shift``. A DC solve therefore
reads ``Bbus · θ = P - p_shift``.
"""

from __future__ import annotations

from typing import Any

import numpy as np
import numpy.typing as npt
from scipy import sparse

from mambo_power.numerics.arrays import NetworkArrays
from mambo_power.numerics.errors import UnsolvableNetworkError

FloatArray = npt.NDArray[np.float64]


def branch_susceptance(arr: NetworkArrays) -> FloatArray:
    """Per-branch DC susceptance ``1 / (x · tap)``."""
    if np.any(arr.x == 0.0):
        zero = [arr.branch_ids[k] for k in np.flatnonzero(arr.x == 0.0)]
        raise UnsolvableNetworkError(
            f"DC susceptance undefined: x == 0 on in-service branch(es) {zero}"
        )
    result: FloatArray = 1.0 / (arr.x * arr.tap)
    return result


def incidence(arr: NetworkArrays) -> Any:
    """``Cft``: ``n_branch × n_bus`` sparse matrix with +1 at the from bus and -1 at the to bus."""
    rows = np.concatenate([np.arange(arr.n_branch), np.arange(arr.n_branch)])
    cols = np.concatenate([arr.f, arr.t])
    data = np.concatenate([np.ones(arr.n_branch), -np.ones(arr.n_branch)])
    return sparse.csc_matrix((data, (rows, cols)), shape=(arr.n_branch, arr.n_bus))


def bf(arr: NetworkArrays) -> Any:
    """``Bf``: ``n_branch × n_bus`` CSC matrix; ``Bf @ θ`` is the from-side DC flow (pu)."""
    b = branch_susceptance(arr)
    rows = np.concatenate([np.arange(arr.n_branch), np.arange(arr.n_branch)])
    cols = np.concatenate([arr.f, arr.t])
    data = np.concatenate([b, -b])
    return sparse.csc_matrix((data, (rows, cols)), shape=(arr.n_branch, arr.n_bus))


def bbus(arr: NetworkArrays) -> Any:
    """``Bbus``: ``n_bus × n_bus`` real CSC DC susceptance matrix (``Cftᵀ · Bf``)."""
    matrix = (incidence(arr).T @ bf(arr)).tocsc()
    matrix.sum_duplicates()
    return matrix


def pf_shift(arr: NetworkArrays) -> FloatArray:
    """Per-branch phase-shifter flow injection ``-b · shift_rad`` (pu), at the from bus."""
    result: FloatArray = branch_susceptance(arr) * (-arr.shift_rad)
    return result


def p_shift(arr: NetworkArrays) -> FloatArray:
    """Per-bus phase-shifter injection ``Cftᵀ · pf_shift`` (pu); ``P = Bbus·θ + p_shift``."""
    result: FloatArray = np.asarray(incidence(arr).T @ pf_shift(arr), dtype=np.float64).ravel()
    return result


def flow_from_ptdf(ptdf: FloatArray, injection_mw: FloatArray, arr: NetworkArrays) -> FloatArray:
    """Branch flow, MW, from a PTDF matrix and a full bus net-injection vector, MW.

    ``flow = ptdf @ (injection_mw − p_shift·base_mva) + pf_shift·base_mva`` — the phase-shifter
    injection is subtracted out of the bus injection *before* the PTDF product, then each
    branch's own from-side shift flow is added back on. This is exactly :func:`mambo_power.pf.dc.
    solve`'s construction (its module docstring: ``rhs = P − p_shift`` feeds the angle solve, and
    ``p_from = Bf·θ + pf_shift``; combined with ``θ = B'⁻¹(P − p_shift)`` and ``PTDF = Bf·B'⁻¹``
    on the reduced system, ``p_from = PTDF·(P − p_shift) + pf_shift``) — the model every DC
    PTDF-based flow in this package must match. Omitting the ``− p_shift`` term (all of
    ``opf.dc_opf``, ``opf.solve_dc_opf`` and ``market._clearing`` did until M8 finding F1 / A19)
    reproduces ``pf.solve_dc``'s flow only when no branch has a shift, since
    ``p_shift(arr) == 0`` identically in that case.

    ``injection_mw`` must be the *full* net injection per bus (generation minus load minus
    shunt, MW) — callers that instead fold some of that into a decision-variable-relative LP
    constant (``opf.dc_opf``'s own flow-limit rows) derive the identical correction by hand
    rather than calling this helper, since their ``injection`` is not one vector (see that
    module's own derivation).
    """
    result: FloatArray = (
        ptdf @ (injection_mw - p_shift(arr) * arr.base_mva) + pf_shift(arr) * arr.base_mva
    )
    return result
