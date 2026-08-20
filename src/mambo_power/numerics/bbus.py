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

FloatArray = npt.NDArray[np.float64]


def branch_susceptance(arr: NetworkArrays) -> FloatArray:
    """Per-branch DC susceptance ``1 / (x · tap)``."""
    if np.any(arr.x == 0.0):
        zero = [arr.branch_ids[k] for k in np.flatnonzero(arr.x == 0.0)]
        raise ValueError(f"DC susceptance undefined: x == 0 on in-service branch(es) {zero}")
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
