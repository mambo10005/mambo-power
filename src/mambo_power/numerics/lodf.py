"""Line outage distribution factors and graph-theoretic bridge detection.

``LODF[l, k]`` is the fraction of branch ``k``'s pre-outage flow that appears on branch ``l``
after ``k`` is removed. With ``h_k = PTDF·(e_f(k) − e_t(k))`` the flows caused by a unit
transfer across ``k``::

    LODF[l, k] = h_k[l] / (1 − h_k[k])     (l ≠ k)         LODF[k, k] = −1

A branch whose removal disconnects the network (a bridge) has ``h_k[k] = 1`` and no finite
LODF; its whole column is ``NaN``. The numeric test (``|1 − h_kk| < 1e-10``) and the
graph-theoretic :func:`bridges` are independent and must agree — the test suite checks that.
"""

from __future__ import annotations

import numpy as np
import numpy.typing as npt

from mambo_power.numerics.arrays import NetworkArrays
from mambo_power.numerics.ptdf import ptdf

FloatArray = npt.NDArray[np.float64]

BRIDGE_TOL = 1e-10
"""``|1 − PTDF_kk| < BRIDGE_TOL`` marks branch ``k`` as a bridge in :func:`lodf`."""


def lodf(arr: NetworkArrays, ptdf_matrix: FloatArray | None = None) -> FloatArray:
    """Dense ``n_branch × n_branch`` LODF; bridge columns are ``NaN``, diagonal is ``−1``."""
    h = ptdf(arr) if ptdf_matrix is None else ptdf_matrix
    if h.shape != (arr.n_branch, arr.n_bus):
        raise ValueError(f"ptdf_matrix has shape {h.shape}, expected {(arr.n_branch, arr.n_bus)}")
    # Column k: flows on every branch for a unit transfer from f[k] to t[k].
    transfer = h[:, arr.f] - h[:, arr.t]
    denominator = 1.0 - np.diag(transfer)
    is_bridge = np.abs(denominator) < BRIDGE_TOL
    safe = np.where(is_bridge, 1.0, denominator)
    result = transfer / safe[np.newaxis, :]
    np.fill_diagonal(result, -1.0)
    result[:, is_bridge] = np.nan
    return result


def bridges(arr: NetworkArrays) -> list[int]:
    """Positions of branches whose removal disconnects the in-service graph (sorted).

    Iterative Tarjan lowpoint search over the multigraph; parallel branches between the same
    pair of buses are never bridges because the search skips only the *edge* it arrived by.
    """
    n_bus, n_branch = arr.n_bus, arr.n_branch
    adjacency: list[list[tuple[int, int]]] = [[] for _ in range(n_bus)]
    for k in range(n_branch):
        u, v = int(arr.f[k]), int(arr.t[k])
        adjacency[u].append((v, k))
        adjacency[v].append((u, k))

    disc = [-1] * n_bus
    low = [0] * n_bus
    found: list[int] = []
    clock = 0
    for root in range(n_bus):
        if disc[root] != -1:
            continue
        disc[root] = low[root] = clock
        clock += 1
        # stack entries: (node, edge used to enter it, next adjacency cursor)
        stack: list[tuple[int, int, int]] = [(root, -1, 0)]
        while stack:
            node, via, cursor = stack[-1]
            if cursor < len(adjacency[node]):
                stack[-1] = (node, via, cursor + 1)
                nxt, edge = adjacency[node][cursor]
                if edge == via:
                    continue
                if disc[nxt] == -1:
                    disc[nxt] = low[nxt] = clock
                    clock += 1
                    stack.append((nxt, edge, 0))
                else:
                    low[node] = min(low[node], disc[nxt])
            else:
                stack.pop()
                if stack:
                    parent = stack[-1][0]
                    low[parent] = min(low[parent], low[node])
                    if low[node] > disc[parent]:
                        found.append(via)
    found.sort()
    return found
