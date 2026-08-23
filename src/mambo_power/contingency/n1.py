"""N-1 branch-contingency screening: LODF fast screen -> confirming DC re-solve (wave M3 W5).

Two stages, mirroring ``pf.ac_newton``/``pf.dc``'s array-level split. :func:`screen_n1` is the
*estimate*: for every non-bridge branch outage ``k`` (:func:`mambo_power.numerics.bridges`
skips the rest — a bridge outage disconnects the network, LODF is undefined for it, the same
skip rule ``_brute_force_lodf.py`` uses), it estimates every other branch ``l``'s post-outage
flow from the base-case DC dispatch and :func:`mambo_power.numerics.lodf`::

    estimated[l] = |base_flow[l] + lodf[l, k] * base_flow[k]|

— the exact form S1's fixture-wide rating-margin sanity sweep used (record/m3-s1-report.md) —
and flags ``k`` if any ``l``'s estimate exceeds ``l``'s ``rating_mva``. :func:`confirm_n1` is
the *ground truth*: for each flagged outage, it rebuilds the network with that branch out of
service (the same deep-copy-once/flip/rebuild pattern ``_brute_force_lodf.py`` uses) and runs a
real :func:`mambo_power.pf.dc.solve` — a single right-hand-side DC re-solve, cheap even at
case300 scale (record/m3-research.md §4) — confirming whether each flagged branch's flow
genuinely exceeds its rating. An outage the screen does not flag is never re-solved; AC-6's
brute-force agreement test (``tests/unit/test_contingency_n1_brute_force.py``) proves that is
safe: the confirmed-violation set this pipeline produces equals a full brute-force sweep's.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import numpy.typing as npt
from pydantic import BaseModel, ConfigDict

from mambo_power.model import Network, validate_network
from mambo_power.numerics import NetworkArrays, bridges, lodf, ptdf
from mambo_power.pf import dc as pfdc
from mambo_power.results import N1BranchFlag, N1OutageResult

FloatArray = npt.NDArray[np.float64]

VIOLATION_TOL_MVA = 1e-9
"""Absolute slack against float noise when comparing an estimated or confirmed flow to a
rating — matches ``tests._rated``'s own base-case-never-violates check."""


class N1Options(BaseModel):
    """Options for :func:`mambo_power.contingency.n1`. Empty today; reserved for future knobs
    (e.g. a screening tolerance) so the public signature does not need to change to add one."""

    model_config = ConfigDict(extra="forbid", frozen=True)


@dataclass(frozen=True)
class N1Screen:
    """Array-level LODF fast-screen verdict (:func:`screen_n1`).

    ``flagged_positions[k]`` lists the positions of branches whose LODF-estimated post-outage
    flow exceeds their rating when branch ``k`` is taken out; only outages with at least one
    flagged branch appear as a key. ``estimated_flow_mw[k]`` is the full ``n_branch``-length
    estimated-flow array for that outage (every branch, not only the flagged ones), kept so
    :func:`confirm_n1` can report the estimate alongside the confirmed value.
    ``bridge_positions`` lists the branches skipped because their outage would disconnect the
    network (:func:`mambo_power.numerics.bridges`) — LODF is undefined for them.
    """

    flagged_positions: dict[int, list[int]]
    estimated_flow_mw: dict[int, FloatArray]
    bridge_positions: list[int]


def screen_n1(arr: NetworkArrays, options: N1Options) -> N1Screen:
    """LODF fast screen: which branch outages would push another branch over its rating.

    Solves the base case once (:func:`mambo_power.pf.dc.solve`), then for every non-bridge
    branch ``k``, estimates every other branch's post-outage flow and flags ``k`` if any
    estimate exceeds that branch's ``rating_mva`` (``inf`` on an unrated branch, so it is never
    flagged). ``options`` is accepted for symmetry with :func:`confirm_n1` and future
    extensibility; nothing in it is read yet.
    """
    del options
    base_sol = pfdc.solve(arr)
    # The LODF formula (post[l] = pre[l] + LODF[l, k] * pre[k]) needs the *signed* pre-outage
    # flow — the same signed quantity `_brute_force_lodf.py`'s own oracle assembles via
    # `ptdf(arr) @ p`. Only the final estimate is taken in magnitude, for comparison against a
    # rating; abs-ing the inputs first would silently flip the formula's sign on any branch
    # whose declared from/to direction opposes its actual flow direction.
    base_flow_signed_mw = base_sol.p_from_pu * arr.base_mva
    rating_mva = arr.rating_pu * arr.base_mva

    lodf_matrix = lodf(arr, ptdf(arr))
    bridge_positions = bridges(arr)
    bridge_set = set(bridge_positions)

    flagged_positions: dict[int, list[int]] = {}
    estimated_flow_mw: dict[int, FloatArray] = {}
    for k in range(arr.n_branch):
        if k in bridge_set:
            continue
        estimated: FloatArray = np.abs(
            base_flow_signed_mw + lodf_matrix[:, k] * base_flow_signed_mw[k]
        )
        violating = [
            branch
            for branch in range(arr.n_branch)
            if branch != k and estimated[branch] > rating_mva[branch] + VIOLATION_TOL_MVA
        ]
        if violating:
            flagged_positions[k] = violating
            estimated_flow_mw[k] = estimated
    return N1Screen(
        flagged_positions=flagged_positions,
        estimated_flow_mw=estimated_flow_mw,
        bridge_positions=bridge_positions,
    )


def confirm_n1(net: Network, arr: NetworkArrays, screen: N1Screen) -> list[N1OutageResult]:
    """Confirming DC re-solve for every outage *screen* flagged; ground truth, not estimate.

    Rebuilds the network with each flagged branch out of service and runs a real
    :func:`mambo_power.pf.dc.solve`, recording both the LODF-estimated and the confirmed flow
    for every branch the screen flagged for that outage. *net* is not modified.

    Mirrors ``_brute_force_lodf.py``'s deep-copy-once/flip/rebuild/restore pattern: *net* is
    deep-copied exactly once up front, not once per outage — flipping ``in_service`` on that one
    copy and restoring it after each re-solve is what keeps this cheap at case300 scale (record/
    m3-research.md §4); a fresh ``model_copy(deep=True)`` per outage was measured ~20x slower.
    """
    outaged = net.model_copy(deep=True)
    by_id = {br.id: br for br in outaged.branches}
    outages: list[N1OutageResult] = []
    for k in sorted(screen.flagged_positions):
        outage_id = arr.branch_ids[k]
        by_id[outage_id].in_service = False
        assert validate_network(outaged) == []
        arr_k = NetworkArrays.from_network(outaged)
        sol_k = pfdc.solve(arr_k)
        by_id[outage_id].in_service = True
        confirmed_flow_mw = np.abs(sol_k.p_from_pu) * arr_k.base_mva
        confirmed_rating_mva = arr_k.rating_pu * arr_k.base_mva

        flags: list[N1BranchFlag] = []
        for branch in screen.flagged_positions[k]:
            monitored_id = arr.branch_ids[branch]
            pos = arr_k.branch_index[monitored_id]
            confirmed = float(confirmed_flow_mw[pos])
            limit = float(confirmed_rating_mva[pos])
            flags.append(
                N1BranchFlag(
                    branch_id=monitored_id,
                    rating_mva=limit,
                    estimated_flow_mw=float(screen.estimated_flow_mw[k][branch]),
                    confirmed_flow_mw=confirmed,
                    confirmed_violating=confirmed > limit + VIOLATION_TOL_MVA,
                )
            )
        outages.append(
            N1OutageResult(
                outage_branch_id=outage_id,
                flagged_branches=flags,
                confirmed_violating=any(f.confirmed_violating for f in flags),
            )
        )
    return outages
