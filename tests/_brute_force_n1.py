"""Brute-force N-1 oracle: DC re-solve every branch outage directly, no LODF pre-filter.

Generalizes ``_brute_force_lodf.py``'s deep-copy-once/flip/rebuild shape from "outage -> PTDF
diff" to "outage -> DC re-solve -> limit check" (wave spec Design item 5), to prove S4's
LODF-screen-then-DC-reslve pipeline (:mod:`mambo_power.contingency`) misses no confirmed
violation and confirms nothing the brute force would not (AC-6).
"""

from __future__ import annotations

import numpy as np

from mambo_power.contingency.n1 import VIOLATION_TOL_MVA
from mambo_power.model import Network, validate_network
from mambo_power.numerics import NetworkArrays, bridges
from mambo_power.pf import dc as pfdc


def brute_force_n1(net: Network, arr: NetworkArrays) -> set[str]:
    """Branch ids whose outage a real DC re-solve confirms violates another branch's rating.

    Re-solves *every* non-bridge branch outage (skipping bridges the same way
    ``_brute_force_lodf.py`` and the LODF screen both do — their outage disconnects the
    network) with no LODF pre-filter at all: this is the ground-truth confirmed-violation set
    the screen-then-confirm pipeline is checked against.
    """
    bridge = set(bridges(arr))
    confirmed: set[str] = set()
    outaged = net.model_copy(deep=True)
    by_id = {br.id: br for br in outaged.branches}
    for k in range(arr.n_branch):
        if k in bridge:
            continue
        outage_id = arr.branch_ids[k]
        by_id[outage_id].in_service = False
        assert validate_network(outaged) == []
        arr_k = NetworkArrays.from_network(outaged)
        sol = pfdc.solve(arr_k)
        by_id[outage_id].in_service = True
        flow_mw = np.abs(sol.p_from_pu) * arr_k.base_mva
        rating_mva = arr_k.rating_pu * arr_k.base_mva
        if np.any(flow_mw > rating_mva + VIOLATION_TOL_MVA):
            confirmed.add(outage_id)
    return confirmed
