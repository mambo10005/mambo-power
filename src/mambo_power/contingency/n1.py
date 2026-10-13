"""N-1 contingency screening: linear fast screen -> confirming DC re-solve.

Two stages, mirroring ``pf.ac_newton``/``pf.dc``'s array-level split. :func:`screen_n1` is the
*estimate*. For every non-bridge branch outage ``k`` (:func:`mambo_power.numerics.bridges`
skips the rest — a bridge outage disconnects the network, LODF is undefined for it, the same
skip rule ``_brute_force_lodf.py`` uses), it estimates every other branch ``l``'s post-outage
flow from the base-case DC dispatch and :func:`mambo_power.numerics.lodf`::

    estimated[l] = |base_flow[l] + lodf[l, k] * base_flow[k]|

— the exact form S1's fixture-wide rating-margin sanity sweep used (record/m3-s1-report.md) —
and flags ``k`` if any ``l``'s estimate exceeds ``l``'s ``rating_mva``. For every generator
``g`` that is not at the slack bus (ADR-015), it estimates the flow after ``g``'s base-case
dispatch ``P_g`` is lost and picked up by the slack from :func:`mambo_power.numerics.ptdf`::

    estimated[l] = |base_flow[l] - ptdf[l, bus(g)] * P_g|

(the PTDF's slack column is zero, so the slack's pickup contributes nothing) and flags ``g`` on
the same rule. :func:`confirm_n1` and :func:`confirm_n1_generators` are the *ground truth*: for
each flagged outage, they rebuild the network with that element out of service (the same
deep-copy-once/flip/rebuild pattern ``_brute_force_lodf.py`` uses) and run a real
:func:`mambo_power.pf.dc.solve` — a single right-hand-side DC re-solve, cheap even at case300
scale (record/m3-research.md §4) — confirming whether each flagged branch's flow genuinely
exceeds its rating. An outage the screen does not flag is never re-solved; the brute-force
agreement tests (``tests/unit/test_contingency_n1_brute_force.py``,
``tests/unit/test_contingency_n1_generators.py``) prove that is safe: the confirmed-violation
set this pipeline produces equals a full brute-force sweep's, for branches and for generators.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import numpy.typing as npt
from pydantic import BaseModel, ConfigDict, Field

from mambo_power.model import Network, validate_network
from mambo_power.numerics import NetworkArrays, bridges, lodf, ptdf
from mambo_power.numerics.bbus import flow_from_ptdf
from mambo_power.pf import dc as pfdc
from mambo_power.results import N1BranchFlag, N1GeneratorOutageResult, N1OutageResult

FloatArray = npt.NDArray[np.float64]

VIOLATION_TOL_MVA = 1e-9
"""Absolute slack against float noise when comparing an estimated or confirmed flow to a
rating — matches ``tests._rated``'s own base-case-never-violates check."""


class N1Options(BaseModel):
    """Options for :func:`mambo_power.contingency.n1`."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    generator_outages: bool = Field(
        default=True,
        description=(
            "Also screen and confirm the outage of every in-service generator that is not at "
            "the slack bus; off leaves N1Result.generator_outages empty."
        ),
    )


@dataclass(frozen=True)
class N1Screen:
    """Array-level linear fast-screen verdict (:func:`screen_n1`).

    ``flagged_positions[k]`` lists the positions of branches whose LODF-estimated post-outage
    flow exceeds their rating when branch ``k`` is taken out; only outages with at least one
    flagged branch appear as a key. ``estimated_flow_mw[k]`` is the full ``n_branch``-length
    estimated-flow array for that outage (every branch, not only the flagged ones), kept so
    :func:`confirm_n1` can report the estimate alongside the confirmed value.
    ``bridge_positions`` lists the branches skipped because their outage would disconnect the
    network (:func:`mambo_power.numerics.bridges`) — LODF is undefined for them.

    The three ``gen_*`` fields are the generator counterparts, keyed by position in
    ``arr.gen_ids``: ``gen_flagged_positions[g]`` and ``gen_estimated_flow_mw[g]`` for every
    flagged generator outage, and ``gen_slack_positions`` for the generators at the slack bus,
    which are skipped (ADR-015). ``gen_lost_p_mw[g]`` is the base-case DC dispatch the outage
    removes, recorded for every screened generator, flagged or not.
    """

    flagged_positions: dict[int, list[int]]
    estimated_flow_mw: dict[int, FloatArray]
    bridge_positions: list[int]
    gen_flagged_positions: dict[int, list[int]] = field(default_factory=dict)
    gen_estimated_flow_mw: dict[int, FloatArray] = field(default_factory=dict)
    gen_slack_positions: list[int] = field(default_factory=list)
    gen_lost_p_mw: dict[int, float] = field(default_factory=dict)


def _violating(estimated: FloatArray, rating_mva: FloatArray, skip: int | None) -> list[int]:
    """Positions whose estimate exceeds their rating, excluding *skip* (the outaged branch)."""
    return [
        branch
        for branch in range(estimated.shape[0])
        if branch != skip and estimated[branch] > rating_mva[branch] + VIOLATION_TOL_MVA
    ]


def screen_n1(arr: NetworkArrays, options: N1Options) -> N1Screen:
    """Linear fast screen: which branch or generator outages would push a branch over its rating.

    Solves the base case once (:func:`mambo_power.pf.dc.solve`), then for every non-bridge
    branch ``k``, estimates every other branch's post-outage flow from the LODF and flags ``k``
    if any estimate exceeds that branch's ``rating_mva`` (``inf`` on an unrated branch, so it is
    never flagged). When ``options.generator_outages`` is on, it also estimates, for every
    in-service generator not at the slack bus, the flow after its base-case dispatch is lost to
    the slack, from the PTDF column of its bus, and flags the generator on the same rule. The
    screen itself is :func:`screen_flows`; this function supplies it the base case.
    """
    base_sol = pfdc.solve(arr)
    # The LODF formula (post[l] = pre[l] + LODF[l, k] * pre[k]) needs the *signed* pre-outage
    # flow — the same signed quantity `_brute_force_lodf.py`'s own oracle assembles via
    # `ptdf(arr) @ p`. Only the final estimate is taken in magnitude, for comparison against a
    # rating; abs-ing the inputs first would silently flip the formula's sign on any branch
    # whose declared from/to direction opposes its actual flow direction.
    return screen_flows(
        arr,
        base_sol.p_from_pu * arr.base_mva,
        base_sol.gen_p_pu * arr.base_mva,
        options,
    )


def screen_n1_dispatch(
    arr: NetworkArrays,
    gen_p_mw: FloatArray,
    options: N1Options,
    *,
    ptdf_matrix: FloatArray | None = None,
) -> N1Screen:
    """:func:`screen_n1` for a caller-supplied dispatch instead of the network's declared one.

    ``gen_p_mw`` is per generator in ``arr.gen_ids`` order and must balance the fixed load and
    shunts (as an OPF dispatch does); the base-case flows are
    :func:`mambo_power.numerics.bbus.flow_from_ptdf` of the resulting injection, the same
    identity :func:`mambo_power.pf.dc.solve` solves for. This is the screen
    :func:`mambo_power.opf.scopf.scopf_dc` runs on each candidate dispatch (ADR-016); a
    precomputed ``ptdf_matrix`` is reused when given, since that loop screens the same network
    many times.
    """
    ptdf_matrix = ptdf(arr) if ptdf_matrix is None else ptdf_matrix
    gen_by_bus = np.bincount(arr.gen_bus, weights=gen_p_mw, minlength=arr.n_bus)
    injection_mw = gen_by_bus - (arr.p_load_pu + arr.g_shunt_pu) * arr.base_mva
    base_flow_signed_mw = flow_from_ptdf(ptdf_matrix, injection_mw, arr)
    return screen_flows(arr, base_flow_signed_mw, gen_p_mw, options, ptdf_matrix=ptdf_matrix)


def screen_flows(
    arr: NetworkArrays,
    base_flow_signed_mw: FloatArray,
    gen_p_mw: FloatArray,
    options: N1Options,
    *,
    ptdf_matrix: FloatArray | None = None,
) -> N1Screen:
    """The screen proper, over a given base case: signed branch flows and per-generator dispatch
    in ``arr`` order, both MW. :func:`screen_n1` and :func:`screen_n1_dispatch` differ only in
    where the base case comes from. The LODF, bridges and (when ``ptdf_matrix`` is not given)
    the PTDF are computed here.
    """
    rating_mva = arr.rating_pu * arr.base_mva
    ptdf_matrix = ptdf(arr) if ptdf_matrix is None else ptdf_matrix
    lodf_matrix = lodf(arr, ptdf_matrix)
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
        violating = _violating(estimated, rating_mva, k)
        if violating:
            flagged_positions[k] = violating
            estimated_flow_mw[k] = estimated

    gen_flagged_positions: dict[int, list[int]] = {}
    gen_estimated_flow_mw: dict[int, FloatArray] = {}
    gen_slack_positions: list[int] = []
    gen_lost_p_mw: dict[int, float] = {}
    if options.generator_outages:
        # The base-case *solved* dispatch, not the declared one: the two agree for every
        # generator off the slack bus, and the slack bus's own generators are skipped, so this
        # is the MW a re-solve with the generator out of service actually removes.
        for g in range(len(arr.gen_ids)):
            bus = int(arr.gen_bus[g])
            if bus == arr.slack:
                gen_slack_positions.append(g)
                continue
            lost_p_mw = float(gen_p_mw[g])
            gen_lost_p_mw[g] = lost_p_mw
            estimated = np.abs(base_flow_signed_mw - ptdf_matrix[:, bus] * lost_p_mw)
            violating = _violating(estimated, rating_mva, None)
            if violating:
                gen_flagged_positions[g] = violating
                gen_estimated_flow_mw[g] = estimated
    return N1Screen(
        flagged_positions=flagged_positions,
        estimated_flow_mw=estimated_flow_mw,
        bridge_positions=bridge_positions,
        gen_flagged_positions=gen_flagged_positions,
        gen_estimated_flow_mw=gen_estimated_flow_mw,
        gen_slack_positions=gen_slack_positions,
        gen_lost_p_mw=gen_lost_p_mw,
    )


def _flags_for(
    arr: NetworkArrays,
    arr_k: NetworkArrays,
    sol_k: pfdc.DcSolution,
    monitored: list[int],
    estimated: FloatArray,
) -> list[N1BranchFlag]:
    """The :class:`N1BranchFlag` rows for one confirming re-solve.

    *monitored* and *estimated* are in the base-case ``arr`` positions; each monitored branch is
    looked up by id in the outaged ``arr_k`` because the two array views differ by the outaged
    element.
    """
    confirmed_flow_mw = np.abs(sol_k.p_from_pu) * arr_k.base_mva
    confirmed_rating_mva = arr_k.rating_pu * arr_k.base_mva
    flags: list[N1BranchFlag] = []
    for branch in monitored:
        monitored_id = arr.branch_ids[branch]
        pos = arr_k.branch_index[monitored_id]
        confirmed = float(confirmed_flow_mw[pos])
        limit = float(confirmed_rating_mva[pos])
        flags.append(
            N1BranchFlag(
                branch_id=monitored_id,
                rating_mva=limit,
                estimated_flow_mw=float(estimated[branch]),
                confirmed_flow_mw=confirmed,
                confirmed_violating=confirmed > limit + VIOLATION_TOL_MVA,
            )
        )
    return flags


def confirm_n1(net: Network, arr: NetworkArrays, screen: N1Screen) -> list[N1OutageResult]:
    """Confirming DC re-solve for every branch outage *screen* flagged; ground truth, not estimate.

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
        flags = _flags_for(
            arr, arr_k, sol_k, screen.flagged_positions[k], screen.estimated_flow_mw[k]
        )
        outages.append(
            N1OutageResult(
                outage_branch_id=outage_id,
                flagged_branches=flags,
                confirmed_violating=any(f.confirmed_violating for f in flags),
            )
        )
    return outages


def confirm_n1_generators(
    net: Network, arr: NetworkArrays, screen: N1Screen
) -> list[N1GeneratorOutageResult]:
    """Confirming DC re-solve for every generator outage *screen* flagged; ground truth.

    The generator counterpart of :func:`confirm_n1`: takes each flagged generator out of
    service on one deep copy of *net*, re-solves (the slack-bus generator absorbs the lost
    dispatch, :func:`mambo_power.pf.dc.solve`'s own rule) and records the PTDF-estimated and
    the confirmed flow for every branch the screen flagged for that outage. *net* is not
    modified.
    """
    outaged = net.model_copy(deep=True)
    by_id = {gen.id: gen for gen in outaged.generators}
    outages: list[N1GeneratorOutageResult] = []
    for g in sorted(screen.gen_flagged_positions):
        outage_id = arr.gen_ids[g]
        by_id[outage_id].in_service = False
        assert validate_network(outaged) == []
        arr_g = NetworkArrays.from_network(outaged)
        sol_g = pfdc.solve(arr_g)
        by_id[outage_id].in_service = True
        flags = _flags_for(
            arr, arr_g, sol_g, screen.gen_flagged_positions[g], screen.gen_estimated_flow_mw[g]
        )
        outages.append(
            N1GeneratorOutageResult(
                outage_generator_id=outage_id,
                lost_p_mw=screen.gen_lost_p_mw[g],
                flagged_branches=flags,
                confirmed_violating=any(f.confirmed_violating for f in flags),
            )
        )
    return outages
