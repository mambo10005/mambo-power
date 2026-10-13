"""Security-constrained DC-OPF: preventive redispatch against the N-1 screen (ADR-016).

:func:`scopf_dc` finds the cheapest dispatch that survives every single branch or generator
outage without a post-contingency overload, under the same DC model as
:func:`mambo_power.contingency.n1` — the same LODF/PTDF estimates, the same slack-absorbs-the-
loss rule for a lost unit, the same ratings. It is **preventive**: one dispatch has to hold for
every contingency, with no post-contingency corrective action.

**Formulation.** The base-case LP is :func:`mambo_power.opf.dc_opf.dc_opf` unchanged. For a
monitored branch ``l`` under a branch outage ``k`` the post-contingency flow is
``flow_l + LODF[l, k]·flow_k``, and under a generator outage ``g`` it is
``flow_l − PTDF[l, bus(g)]·p_g``; both are linear in the dispatch, so each (outage, branch)
pair is one extra row of the same shape as a base-case flow-limit row
(:class:`~mambo_power.opf.dc_opf.SecurityRows`). Every pair at once would be ``n_outages ×
n_branch`` dense rows — case300 alone has ~170 000 — almost all of them slack at the optimum.

**Constraint generation.** So the rows are generated lazily, with the N-1 screen as the
oracle: solve, screen the dispatch (:func:`mambo_power.contingency.n1.screen_n1_dispatch`),
add a row for every (outage, branch) pair the screen flags that is not already constrained,
re-solve, and stop when the screen flags nothing new. Because the DC model is linear, a row
added for a pair makes that pair's post-contingency flow feasible exactly in the next solve,
so each iteration either terminates or adds at least one new row from a finite set — the loop
converges, in practice in a handful of iterations. The final dispatch is then confirmed the
honest way: :func:`mambo_power.opf.solve_scopf` writes it into a copy of the network and runs
the real :func:`mambo_power.contingency.n1`, re-solving every flagged outage.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import Literal

import numpy as np
import numpy.typing as npt
from pydantic import BaseModel, ConfigDict, Field

from mambo_power.contingency.n1 import (
    VIOLATION_TOL_MVA,
    N1Options,
    N1Screen,
    dispatch_flows_mw,
    screen_n1_dispatch,
)
from mambo_power.numerics import NetworkArrays, lodf
from mambo_power.numerics import ptdf as compute_ptdf
from mambo_power.numerics.bbus import p_shift, pf_shift
from mambo_power.opf.dc_opf import (
    CorrectiveRows,
    OpfDcOptions,
    OpfSolution,
    SecurityRows,
    dc_opf,
)

FloatArray = npt.NDArray[np.float64]
OutageKind = Literal["branch", "generator"]

_OPTIMAL = "Optimal"
ITERATION_LIMIT = "IterationLimit"
"""``ScopfSolution.status`` when ``options.max_iterations`` solves did not reach a dispatch the
screen passes; the last solution is still returned so the caller can see how far it got."""


class ScopfOptions(BaseModel):
    """Options for :func:`mambo_power.opf.solve_scopf` and :func:`scopf_dc`."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    generator_outages: bool = Field(
        default=True,
        description="Secure against the loss of every non-slack generator as well as every "
        "non-bridge branch (contingency.n1's own option).",
    )
    max_iterations: int = Field(
        default=25,
        ge=1,
        description="Cap on solve/screen rounds of the constraint-generation loop.",
    )
    ac_check: bool = Field(
        default=False,
        description="Re-run pf.solve_ac on the secure dispatch and attach a "
        "results.FeasibilityReport, as opf.dc's ac_check does.",
    )
    corrective: bool = Field(
        default=False,
        description="Allow post-contingency redispatch (ADR-021): the immediate post-outage "
        "flow is held to the emergency rating and a corrected dispatch, each unit moved by at "
        "most its ramp_up_mw / ramp_down_mw, to the normal rating.",
    )


@dataclass(frozen=True)
class Contingency:
    """One (outage, monitored branch) pair that has a row in the security block."""

    kind: OutageKind
    """``"branch"`` or ``"generator"``."""
    outage: int
    """Position of the outaged element in ``arr.branch_ids`` or ``arr.gen_ids``."""
    monitored: int
    """Position of the monitored branch in ``arr.branch_ids``."""


@dataclass(frozen=True)
class ScopfSolution:
    """Result of one :func:`scopf_dc` run."""

    status: str
    """``"Optimal"`` when the loop ended with a dispatch the screen passes; :data:`ITERATION_LIMIT`
    when it ran out of rounds; otherwise the LP's own non-Optimal status."""
    solution: OpfSolution
    """The last :func:`~mambo_power.opf.dc_opf.dc_opf` solution — the secure dispatch when
    ``status == "Optimal"``."""
    contingencies: list[Contingency]
    """The pairs constrained in the final solve, in the order their rows were added, aligned
    with ``security`` and with ``solution.duals.security``."""
    security: SecurityRows
    """The row block of the final solve (empty when the plain OPF was already secure)."""
    iterations: int
    """Number of LP solves performed, at least 1."""
    base_objective_cost: float
    """Cost of the first, unsecured, solve, $/h — ``solution.objective_cost − base_objective_cost``
    is what security cost."""
    screen: N1Screen | None = None
    """The screen of the final dispatch; ``None`` when the final LP was not Optimal."""
    message: str | None = None
    """Diagnostic when ``status != "Optimal"``."""
    post_contingency_flow_mw: FloatArray = field(default_factory=lambda: np.zeros(0))
    """Signed post-contingency flow of each constrained pair at the final dispatch, MW, aligned
    with ``contingencies``."""
    corrected_outages: list[tuple[OutageKind, int]] = field(default_factory=list)
    """The contingencies that have a corrected dispatch (ADR-021), one per
    :class:`~mambo_power.opf.dc_opf.CorrectiveRows` block, in block order; empty without
    ``options.corrective``."""
    corrected_contingencies: list[Contingency] = field(default_factory=list)
    """The pairs whose *corrected* flow is constrained, aligned with ``corrective`` and
    ``solution.duals.corrective_flow``."""
    corrective: CorrectiveRows | None = None
    """The corrective block of the final solve; ``None`` without ``options.corrective``."""
    corrected_flow_mw: FloatArray = field(default_factory=lambda: np.zeros(0))
    """Signed corrected flow of each pair in ``corrected_contingencies`` at the final corrected
    dispatches, MW."""


def corrective_rows(
    arr: NetworkArrays,
    ptdf_matrix: FloatArray,
    lodf_matrix: FloatArray,
    outages: Sequence[tuple[OutageKind, int]],
    contingencies: Sequence[Contingency],
    ramp_up_mw: FloatArray,
    ramp_down_mw: FloatArray,
) -> CorrectiveRows:
    """Build the :class:`~mambo_power.opf.dc_opf.CorrectiveRows` block (ADR-021): one block per
    entry of *outages*, one corrected flow row per entry of *contingencies* (each of which names
    an outage in *outages*), held to the **normal** rating. The sensitivities and constants are
    :func:`security_rows`'s; the lost unit's column is zeroed by ``dc_opf`` itself.
    """
    block_index = {outage: b for b, outage in enumerate(outages)}
    rows = security_rows(arr, ptdf_matrix, lodf_matrix, contingencies)
    return CorrectiveRows(
        lost_gen=np.array(
            [outage if kind == "generator" else -1 for kind, outage in outages], dtype=np.int64
        ),
        ramp_up_mw=ramp_up_mw,
        ramp_down_mw=ramp_down_mw,
        block_of_row=np.array(
            [block_index[(c.kind, c.outage)] for c in contingencies], dtype=np.int64
        ),
        bus_sensitivity=rows.bus_sensitivity,
        const_mw=rows.const_mw,
        rating_mw=(arr.rating_pu * arr.base_mva)[[c.monitored for c in contingencies]],
    )


def _corrected_flows_mw(
    arr: NetworkArrays,
    ptdf_matrix: FloatArray,
    lodf_matrix: FloatArray,
    outage: tuple[OutageKind, int],
    dispatch_mw: FloatArray,
) -> FloatArray:
    """Signed flow of every branch under *outage* at a corrected *dispatch_mw*, which balances
    the load with the lost unit at zero: no slack pickup, so a generator outage's flows are the
    plain flows of that dispatch."""
    flows = dispatch_flows_mw(arr, dispatch_mw, ptdf_matrix)
    kind, k = outage
    if kind == "branch":
        flows = flows + lodf_matrix[:, k] * flows[k]
    return flows


def security_rows(
    arr: NetworkArrays,
    ptdf_matrix: FloatArray,
    lodf_matrix: FloatArray,
    contingencies: Sequence[Contingency],
) -> SecurityRows:
    """Build the :class:`~mambo_power.opf.dc_opf.SecurityRows` block for *contingencies*.

    Row ``r`` is ``contingencies[r]``. For a branch outage ``k`` monitoring ``l`` the bus
    sensitivity is ``PTDF[l] + LODF[l, k]·PTDF[k]`` and the constant ``const_l + LODF[l, k]·
    const_k``, where ``const`` is the fixed (load, shunt, phase-shift) part of each base-case
    flow exactly as :func:`~mambo_power.opf.dc_opf.dc_opf` computes it; for a generator outage
    the sensitivity and constant are the base case's and the outaged unit's own column is
    zeroed. A branch outage must not be a bridge and a generator outage must not sit at the
    slack bus — :func:`scopf_dc` only ever asks for pairs the screen produced, which skips both.
    """
    n_rows = len(contingencies)
    n_gen = len(arr.gen_ids)
    bus_sensitivity = np.zeros((n_rows, arr.n_bus))
    gen_coeffs = np.zeros((n_rows, n_gen))
    const_mw = np.zeros(n_rows)
    rating_mw = np.zeros(n_rows)
    fixed_bus_mw = (arr.p_load_pu + arr.g_shunt_pu + p_shift(arr)) * arr.base_mva
    base_const = pf_shift(arr) * arr.base_mva - ptdf_matrix @ fixed_bus_mw
    # a post-contingency row is held to the emergency rating where one is set (ADR-020)
    base_rating = arr.rating_emergency_pu * arr.base_mva
    for r, c in enumerate(contingencies):
        if c.kind == "branch":
            factor = float(lodf_matrix[c.monitored, c.outage])
            sensitivity = ptdf_matrix[c.monitored] + factor * ptdf_matrix[c.outage]
            const_mw[r] = base_const[c.monitored] + factor * base_const[c.outage]
            gen_coeffs[r] = sensitivity[arr.gen_bus]
        else:
            sensitivity = ptdf_matrix[c.monitored]
            const_mw[r] = base_const[c.monitored]
            gen_coeffs[r] = sensitivity[arr.gen_bus]
            gen_coeffs[r, c.outage] = 0.0
        bus_sensitivity[r] = sensitivity
        rating_mw[r] = base_rating[c.monitored]
    return SecurityRows(
        gen_coeffs=gen_coeffs,
        bus_sensitivity=bus_sensitivity,
        const_mw=const_mw,
        rating_mw=rating_mw,
    )


def _flagged_pairs(screen: N1Screen) -> list[Contingency]:
    """Every (outage, monitored) pair the screen flagged, branches first, in position order."""
    pairs = [
        Contingency("branch", k, monitored)
        for k in sorted(screen.flagged_positions)
        for monitored in screen.flagged_positions[k]
    ]
    pairs.extend(
        Contingency("generator", g, monitored)
        for g in sorted(screen.gen_flagged_positions)
        for monitored in screen.gen_flagged_positions[g]
    )
    return pairs


def scopf_dc(
    arr: NetworkArrays,
    cost_coeffs: FloatArray,
    options: ScopfOptions,
    pwl_costs: Mapping[int, Sequence[tuple[float, float]]] | None = None,
    *,
    ramp_up_mw: FloatArray | None = None,
    ramp_down_mw: FloatArray | None = None,
) -> ScopfSolution:
    """Security-constrained DC-OPF by constraint generation (module docstring).

    Arguments are :func:`~mambo_power.opf.dc_opf.dc_opf`'s. Solves the plain OPF, screens its
    dispatch with :func:`mambo_power.contingency.n1.screen_n1_dispatch`, adds a security row for
    every newly flagged (outage, branch) pair and re-solves, until the screen flags nothing that
    is not already constrained or ``options.max_iterations`` solves have run. Never raises for a
    non-Optimal LP — reported through ``status``/``message`` like ``dc_opf``.

    With ``options.corrective`` (ADR-021) a second screen holds every outage's flows to the
    *normal* rating, against the corrected dispatch of that outage where one exists and the
    base dispatch where not; each newly flagged pair becomes a corrected flow row (and a
    corrective block for an outage that had none). ``ramp_up_mw``/``ramp_down_mw`` are the
    ``(n_gen,)`` corrective ramps, ``None``/``nan``/``inf`` marking an unlimited unit.
    """
    opf_options = OpfDcOptions()
    n1_options = N1Options(generator_outages=options.generator_outages)
    ptdf_matrix = compute_ptdf(arr)
    lodf_matrix = lodf(arr, ptdf_matrix)
    n_gen = len(arr.gen_ids)
    normal_rating_mw = arr.rating_pu * arr.base_mva
    ramp_up = _corrective_ramp("ramp_up_mw", ramp_up_mw, n_gen)
    ramp_down = _corrective_ramp("ramp_down_mw", ramp_down_mw, n_gen)

    constrained: list[Contingency] = []
    seen: set[Contingency] = set()
    security = security_rows(arr, ptdf_matrix, lodf_matrix, constrained)
    outages: list[tuple[OutageKind, int]] = []
    corrected: list[Contingency] = []
    corrected_seen: set[Contingency] = set()
    corrective: CorrectiveRows | None = None
    base_cost: float | None = None
    iterations = 0

    def finish(
        status: str, solution: OpfSolution, screen: N1Screen, message: str | None
    ) -> ScopfSolution:
        corrected_flows = np.array(
            [
                _corrected_flows_mw(
                    arr,
                    ptdf_matrix,
                    lodf_matrix,
                    (c.kind, c.outage),
                    solution.corrective_dispatch_mw[outages.index((c.kind, c.outage))],
                )[c.monitored]
                for c in corrected
            ]
        )
        return ScopfSolution(
            status=status,
            solution=solution,
            contingencies=constrained,
            security=security,
            iterations=iterations,
            base_objective_cost=base_cost if base_cost is not None else 0.0,
            screen=screen,
            message=message,
            post_contingency_flow_mw=_post_contingency_flows(arr, security, solution.dispatch_mw),
            corrected_outages=list(outages),
            corrected_contingencies=list(corrected),
            corrective=corrective,
            corrected_flow_mw=corrected_flows,
        )

    while True:
        iterations += 1
        solution = dc_opf(
            arr,
            cost_coeffs,
            opf_options,
            pwl_costs=pwl_costs,
            ptdf=ptdf_matrix,
            security=security,
            corrective=corrective,
        )
        if base_cost is None:
            base_cost = solution.objective_cost
        if solution.status != _OPTIMAL:
            return ScopfSolution(
                status=solution.status,
                solution=solution,
                contingencies=constrained,
                security=security,
                iterations=iterations,
                base_objective_cost=base_cost,
                message=f"scopf_dc: iteration {iterations}: {solution.message}",
                corrected_outages=list(outages),
                corrected_contingencies=list(corrected),
                corrective=corrective,
            )
        # the immediate post-contingency flows, against the emergency rating
        screen = screen_n1_dispatch(arr, solution.dispatch_mw, n1_options, ptdf_matrix=ptdf_matrix)
        new = [c for c in _flagged_pairs(screen) if c not in seen]
        # the corrected flows, against the normal rating: a corrected dispatch where the outage
        # has one, the base dispatch where it does not yet
        new_corrected: list[Contingency] = []
        if options.corrective:
            normal_screen = screen_n1_dispatch(
                arr,
                solution.dispatch_mw,
                n1_options,
                ptdf_matrix=ptdf_matrix,
                rating_mw=normal_rating_mw,
            )
            for c in _flagged_pairs(normal_screen):
                if (c.kind, c.outage) not in outages and c not in corrected_seen:
                    new_corrected.append(c)
            for b, outage in enumerate(outages):
                flows = np.abs(
                    _corrected_flows_mw(
                        arr, ptdf_matrix, lodf_matrix, outage, solution.corrective_dispatch_mw[b]
                    )
                )
                skip = outage[1] if outage[0] == "branch" else -1
                for monitored in range(arr.n_branch):
                    if monitored == skip:
                        continue
                    if flows[monitored] > normal_rating_mw[monitored] + VIOLATION_TOL_MVA:
                        c = Contingency(outage[0], outage[1], monitored)
                        if c not in corrected_seen:
                            new_corrected.append(c)
        if not new and not new_corrected:
            return finish(_OPTIMAL, solution, screen, None)
        if iterations >= options.max_iterations:
            return finish(
                ITERATION_LIMIT,
                solution,
                screen,
                f"scopf_dc: {iterations} solves reached options.max_iterations with "
                f"{len(new) + len(new_corrected)} newly flagged (outage, branch) pairs still "
                "unconstrained",
            )
        constrained.extend(new)
        seen.update(new)
        security = security_rows(arr, ptdf_matrix, lodf_matrix, constrained)
        if new_corrected:
            for c in new_corrected:
                if (c.kind, c.outage) not in outages:
                    outages.append((c.kind, c.outage))
            corrected.extend(new_corrected)
            corrected_seen.update(new_corrected)
            corrective = corrective_rows(
                arr, ptdf_matrix, lodf_matrix, outages, corrected, ramp_up, ramp_down
            )


def _corrective_ramp(name: str, values: FloatArray | None, n_gen: int) -> FloatArray:
    """``(n_gen,)`` corrective ramp with ``inf`` where unlimited; ``None``, ``nan`` and ``inf``
    all mean unlimited, a negative value is a ``ValueError``."""
    if values is None:
        return np.full(n_gen, np.inf)
    out = np.asarray(values, dtype=np.float64).copy()
    if out.shape != (n_gen,):
        raise ValueError(f"{name} must have shape ({n_gen},), got {out.shape}")
    out[np.isnan(out)] = np.inf
    if np.any(out < 0):
        raise ValueError(f"{name} must be >= 0 (inf or nan for an unlimited unit)")
    return out


def _post_contingency_flows(
    arr: NetworkArrays, security: SecurityRows, dispatch_mw: FloatArray
) -> FloatArray:
    """Signed post-contingency flow of each security row at *dispatch_mw* (no elastic demand)."""
    del arr
    if not security.n_rows:
        return np.zeros(0)
    return np.asarray(security.gen_coeffs @ dispatch_mw + security.const_mw, dtype=np.float64)
