"""N-2 branch-pair screening by the generalised LODF, confirmed by DC re-solves (ADR-024).

The N-1 screen (:mod:`mambo_power.contingency.n1`) estimates every single branch outage from the
LODF; this module does the same for every **pair** of branch outages. Taking branches ``i`` and
``j`` out together is not two N-1 outages added up — each outage's flow redistributes over the
other, now-missing branch — but the DC model is linear, so the joint effect is still a closed
form (the "generalised LODF"): with ``L`` the LODF and ``f`` the base-case signed flows, the
pre-outage flows the two branches have to shed are the solution of ::

    [ 1        -L[i, j] ] [x_i]   [f_i]
    [ -L[j, i]  1       ] [x_j] = [f_j]

and every other branch ``l`` then carries ``f_l + L[l, i]·x_i + L[l, j]·x_j``. The determinant
``1 − L[i, j]·L[j, i]`` is zero exactly when removing both branches disconnects the network —
the pair is a cut set — so a pair with a determinant inside :data:`ISLAND_DET_TOL` is reported
as an **islanding pair**, never estimated; a pair containing an N-1 bridge is skipped for the
same reason before any arithmetic. The screen is vectorised over ``j`` for each ``i``, so it is
``O(n_branch³)``: a few tens of millions of flops on case300, well under a second.

**Confirmation** is a real :func:`mambo_power.pf.dc.solve` with both branches out, exactly as
:func:`~mambo_power.contingency.n1.confirm_n1` does for one — the screen is an estimate, the
re-solve is the fact, and ``tests/unit/test_contingency_n2.py`` checks the two agree against a
brute force over every pair. Post-contingency flows are held to the emergency rating where a
branch has one (ADR-020). Generator outages and mixed generator–branch pairs are not screened
(ADR-024 lists them).
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import numpy.typing as npt
from pydantic import BaseModel, ConfigDict, Field

from mambo_power.contingency.n1 import VIOLATION_TOL_MVA
from mambo_power.model import Network, validate_network
from mambo_power.numerics import NetworkArrays, bridges, lodf, ptdf
from mambo_power.pf import dc as pfdc
from mambo_power.results import N1BranchFlag, N2OutageResult

__all__ = ["ISLAND_DET_TOL", "N2Options", "N2Screen", "confirm_n2", "pair_flows_mw", "screen_n2"]

FloatArray = npt.NDArray[np.float64]

ISLAND_DET_TOL = 1e-9
"""A pair whose generalised-LODF determinant ``1 − L[i, j]·L[j, i]`` is below this in magnitude
is a cut set — removing both branches disconnects the network — and is reported, not estimated."""


class N2Options(BaseModel):
    """Options for :func:`mambo_power.contingency.n2`."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    max_confirmed_pairs: int = Field(
        default=1000,
        ge=1,
        description="Cap on the flagged pairs that are DC re-solved, in pair order; a screen "
        "that flags more reports the rest unconfirmed (N2Result.truncated).",
    )


@dataclass(frozen=True)
class N2Screen:
    """Array-level generalised-LODF screen verdict (:func:`screen_n2`).

    ``flagged[(i, j)]`` (``i < j``, branch positions) lists the positions of the branches whose
    estimated flow with both ``i`` and ``j`` out exceeds their post-contingency rating;
    ``estimated_flow_mw[(i, j)]`` is the full ``n_branch`` estimate for that pair. Pairs appear
    in lexicographic order. ``islanding`` lists the pairs whose removal disconnects the network
    (determinant inside :data:`ISLAND_DET_TOL`), which the screen does not estimate;
    ``bridge_positions`` the single branches skipped as N-1 bridges, so no pair contains one.
    """

    flagged: dict[tuple[int, int], list[int]]
    estimated_flow_mw: dict[tuple[int, int], FloatArray]
    islanding: list[tuple[int, int]]
    bridge_positions: list[int]
    n_pairs_screened: int = 0
    base_flow_signed_mw: FloatArray = field(default_factory=lambda: np.zeros(0))


def screen_n2(arr: NetworkArrays) -> N2Screen:
    """Generalised-LODF screen of every branch pair of the in-service network (module docstring).

    Solves the base case once, then for every ``i`` estimates all pairs ``(i, j > i)`` at once:
    the pair's two shed flows from the 2×2 system, every other branch's flow from them, and a
    flag wherever an estimate exceeds the branch's emergency (else normal) rating by more than
    :data:`~mambo_power.contingency.n1.VIOLATION_TOL_MVA`. The two outaged branches themselves
    are never flagged.
    """
    n = arr.n_branch
    base_sol = pfdc.solve(arr)
    base_flow = np.asarray(base_sol.p_from_pu, dtype=np.float64) * arr.base_mva
    ptdf_matrix = ptdf(arr)
    lodf_matrix = lodf(arr, ptdf_matrix)
    bridge_positions = bridges(arr)
    bridge_set = set(bridge_positions)
    rating_mw = arr.rating_emergency_pu * arr.base_mva
    limit = rating_mw + VIOLATION_TOL_MVA
    candidates = np.array([k for k in range(n) if k not in bridge_set], dtype=np.int64)

    flagged: dict[tuple[int, int], list[int]] = {}
    estimated: dict[tuple[int, int], FloatArray] = {}
    islanding: list[tuple[int, int]] = []
    n_pairs = 0
    for a, i in enumerate(candidates):
        js = candidates[a + 1 :]
        if js.size == 0:
            continue
        n_pairs += int(js.size)
        det = 1.0 - lodf_matrix[i, js] * lodf_matrix[js, i]
        island = np.abs(det) <= ISLAND_DET_TOL
        for j in js[island]:
            islanding.append((int(i), int(j)))
        live = js[~island]
        if live.size == 0:
            continue
        det_live = det[~island]
        x_i = (base_flow[i] + lodf_matrix[i, live] * base_flow[live]) / det_live
        x_j = (base_flow[live] + lodf_matrix[live, i] * base_flow[i]) / det_live
        # (n_branch, n_live): every branch's estimate under every live pair with i
        post = base_flow[:, None] + np.outer(lodf_matrix[:, i], x_i) + lodf_matrix[:, live] * x_j
        over = np.abs(post) > limit[:, None]
        over[i, :] = False
        over[live, np.arange(live.size)] = False
        hits = np.flatnonzero(over.any(axis=0))
        for col in hits:
            j = int(live[col])
            key = (int(i), j)
            flagged[key] = [int(m) for m in np.flatnonzero(over[:, col])]
            estimated[key] = np.abs(post[:, col])
    return N2Screen(
        flagged=flagged,
        estimated_flow_mw=estimated,
        islanding=islanding,
        bridge_positions=bridge_positions,
        n_pairs_screened=n_pairs,
        base_flow_signed_mw=base_flow,
    )


def confirm_n2(
    net: Network, arr: NetworkArrays, screen: N2Screen, *, max_pairs: int | None = None
) -> tuple[list[N2OutageResult], bool]:
    """Confirming DC re-solve of every flagged pair (the first *max_pairs* of them); returns the
    results and whether any flagged pair was left unconfirmed. *net* is not modified — one deep
    copy, both branches flipped out and back per pair, as
    :func:`~mambo_power.contingency.n1.confirm_n1` does.
    """
    outaged = net.model_copy(deep=True)
    by_id = {br.id: br for br in outaged.branches}
    results: list[N2OutageResult] = []
    pairs = sorted(screen.flagged)
    truncated = max_pairs is not None and len(pairs) > max_pairs
    for i, j in pairs[:max_pairs]:
        ids = (arr.branch_ids[i], arr.branch_ids[j])
        for branch_id in ids:
            by_id[branch_id].in_service = False
        assert validate_network(outaged) == []
        arr_ij = NetworkArrays.from_network(outaged)
        sol_ij = pfdc.solve(arr_ij)
        for branch_id in ids:
            by_id[branch_id].in_service = True
        confirmed_flow = np.abs(sol_ij.p_from_pu) * arr_ij.base_mva
        confirmed_rating = arr_ij.rating_emergency_pu * arr_ij.base_mva
        flags: list[N1BranchFlag] = []
        for monitored in screen.flagged[(i, j)]:
            monitored_id = arr.branch_ids[monitored]
            pos = arr_ij.branch_index[monitored_id]
            confirmed = float(confirmed_flow[pos])
            rating = float(confirmed_rating[pos])
            flags.append(
                N1BranchFlag(
                    branch_id=monitored_id,
                    rating_mva=rating,
                    estimated_flow_mw=float(screen.estimated_flow_mw[(i, j)][monitored]),
                    confirmed_flow_mw=confirmed,
                    confirmed_violating=confirmed > rating + VIOLATION_TOL_MVA,
                )
            )
        results.append(
            N2OutageResult(
                outage_branch_ids=list(ids),
                flagged_branches=flags,
                confirmed_violating=any(f.confirmed_violating for f in flags),
            )
        )
    return results, truncated


def pair_flows_mw(arr: NetworkArrays, i: int, j: int) -> FloatArray:
    """Signed flow of every branch with ``i`` and ``j`` out, by the generalised LODF (module
    docstring) — the closed form the screen uses, for one pair; ``nan`` everywhere when the pair
    is a cut set."""
    base_flow = np.asarray(pfdc.solve(arr).p_from_pu, dtype=np.float64) * arr.base_mva
    lodf_matrix = lodf(arr, ptdf(arr))
    det = 1.0 - lodf_matrix[i, j] * lodf_matrix[j, i]
    if abs(det) <= ISLAND_DET_TOL:
        return np.full(arr.n_branch, np.nan)
    x_i = (base_flow[i] + lodf_matrix[i, j] * base_flow[j]) / det
    x_j = (base_flow[j] + lodf_matrix[j, i] * base_flow[i]) / det
    post = base_flow + lodf_matrix[:, i] * x_i + lodf_matrix[:, j] * x_j
    post[[i, j]] = 0.0
    return np.asarray(post, dtype=np.float64)
