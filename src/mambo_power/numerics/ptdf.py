"""Power transfer distribution factors from the DC model.

``PTDF = Bf · Bbus⁻¹`` with the slack row and column removed before the inverse and the slack
column of the result set to zero: ``flows = PTDF @ P`` for any injection vector ``P`` (the
slack absorbs the imbalance). The reduced ``Bbus`` is factorised once with a sparse LU and
solved against the dense transposed ``Bf``; the full matrix is never inverted densely.
"""

from __future__ import annotations

import numpy as np
import numpy.typing as npt
from scipy.sparse.linalg import splu

from mambo_power.numerics.arrays import NetworkArrays
from mambo_power.numerics.bbus import bbus, bf

FloatArray = npt.NDArray[np.float64]


def ptdf(arr: NetworkArrays, slack: int | None = None) -> FloatArray:
    """Dense ``n_branch × n_bus`` PTDF with a zero column at ``slack`` (default: the network's)."""
    ref = arr.slack if slack is None else slack
    if not 0 <= ref < arr.n_bus:
        raise ValueError(f"slack position {ref} out of range for {arr.n_bus} buses")
    keep = np.array([i for i in range(arr.n_bus) if i != ref], dtype=np.int64)
    result = np.zeros((arr.n_branch, arr.n_bus))
    if arr.n_branch == 0 or keep.size == 0:
        return result
    b_reduced = bbus(arr)[keep][:, keep].tocsc()
    bf_reduced = bf(arr)[:, keep].toarray()
    # Bbus is symmetric, so solving Bᵀ·X = Bfᵀ gives X = (Bf·B⁻¹)ᵀ.
    lu = splu(b_reduced)
    solved = lu.solve(np.ascontiguousarray(bf_reduced.T))
    result[:, keep] = solved.T
    return result
