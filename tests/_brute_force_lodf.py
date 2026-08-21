"""Brute-force LODF oracle: actually take each branch out of service and re-solve.

Shared by the unit tier (hand-built 6-bus case) and the parity tier (the five MATPOWER
fixtures; AC-7 "LODF equals the brute-force single-outage PTDF difference"). Nothing here is
shared with :mod:`mambo_power.numerics` beyond calling its public ``ptdf`` on the *outaged*
network — the independence comes from physically removing the branch, not from a formula.
"""

from __future__ import annotations

import numpy as np

from mambo_power.model import Network, validate_network
from mambo_power.numerics import NetworkArrays, bridges, ptdf


def brute_force_lodf(net: Network, arr: NetworkArrays, p: np.ndarray) -> np.ndarray:
    """``n_branch × n_branch`` LODF from one outage rebuild per branch; bridge columns NaN.

    ``p`` is a balanced injection vector that loads every non-bridge branch (asserted).
    """
    pre = ptdf(arr) @ p
    bridge = set(bridges(arr))
    expected = np.full((arr.n_branch, arr.n_branch), np.nan)
    outaged = net.model_copy(deep=True)
    by_id = {br.id: br for br in outaged.branches}
    for k in range(arr.n_branch):
        if k in bridge:
            continue
        assert abs(pre[k]) > 1e-6, "test injection must load every branch"
        # Take branch k out on the copy, re-check the invariants (models do not re-validate on
        # mutation), rebuild the arrays, and restore it for the next outage.
        by_id[arr.branch_ids[k]].in_service = False
        assert validate_network(outaged) == []
        arr_k = NetworkArrays.from_network(outaged)
        by_id[arr.branch_ids[k]].in_service = True
        assert arr_k.bus_ids == arr.bus_ids
        post = ptdf(arr_k) @ p
        for l_idx, branch_id in enumerate(arr.branch_ids):
            if l_idx == k:
                expected[l_idx, k] = -1.0
            else:
                expected[l_idx, k] = (post[arr_k.branch_index[branch_id]] - pre[l_idx]) / pre[k]
    return expected
