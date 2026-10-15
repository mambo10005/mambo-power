"""AC optimal power flow by trust-region sequential quadratic programming on HiGHS (ADR-018).

Array-level entry point: :func:`ac_opf` is pure numerics over
:class:`~mambo_power.numerics.NetworkArrays` plus caller-supplied cost coefficients and voltage
limits, mirroring :func:`mambo_power.opf.dc_opf.dc_opf`; the ``Network``-facing wrapper is
:func:`mambo_power.opf.solve_ac_opf`.

**Formulation** (MATPOWER's ``opf`` in polar form, ``opf.flow_lim = 'S'``). The state is
``x = [Va, Vm, Pg, Qg]`` — every bus's angle (the slack's pinned at 0) and magnitude, every
generator's active and reactive output. Minimise ``Σ cost_g(Pg)`` subject to

* the full AC nodal balance at every bus, ``Re/Im( V · conj(Y V) ) + S_load − C_g·S_g = 0``,
  the same mismatch :mod:`mambo_power.pf.ac_newton` drives to zero, now with ``Pg``/``Qg`` free;
* ``v_min <= Vm <= v_max`` at every bus, ``[p_min, p_max]`` and ``[q_min, q_max]`` on every
  generator;
* ``|S_from|² <= rating²`` and ``|S_to|² <= rating²`` on every rated branch (apparent power at
  both ends, MATPOWER's default; an unrated branch has no row).

Losses, reactive power and voltage are therefore real, which is exactly what the DC-OPF cannot
say: its dispatch is routinely AC-infeasible (``ac_check``), and its LMPs carry no loss term.

**Why sequential LPs on HiGHS, not an interior-point NLP.** The package owns its solvers on
numpy, scipy and HiGHS (ADR-002), and HiGHS's simplex is the one solver here whose every answer
and every dual can be trusted to machine precision. So the nonlinear problem is solved as a
sequence of LPs: at the current point every constraint is replaced by its first-order Taylor
expansion — the nodal balance by the Newton Jacobian (:func:`_dsbus_dv`, the same ``dSbus_dV``
the power flow factorises), the flow limits by ``2·P·dP + 2·Q·dQ`` of ``dSbr_dV`` — and the
step is confined to a trust region on ``Va``, ``Vm`` and ``Pg``. A quadratic cost is carried
**exactly where it matters**: as convex chords of the true curve through the current dispatch,
eight across the ``Pg`` trust region plus the two reaching the bounds, in the same epigraph
encoding ``dc_opf`` uses for piecewise-linear costs. The chords are a tangent-tight model of the
curve inside the region the step may reach, and because the current dispatch is itself a
breakpoint, the LP returns a zero ``Pg`` step exactly when the marginal price lies between the
two chord slopes meeting there — a subgradient test whose width shrinks with the radius.

The LP's linearised balance rows carry penalised elastic slacks so it is always feasible. A
step is followed by a **restoration**: with the LP's generator injections held, a few Newton
iterations on every angle and magnitude drive the nodal balance back to zero (a power flow in
which every bus is PQ and the slack unit absorbs the active residual, within its bounds), which
removes the second-order mismatch a first-order step leaves behind. The restored point is
accepted when an ``ℓ₁`` merit function (cost plus a penalty on the nonlinear residual) actually
decreases as the model predicted, and the radius grows or shrinks with the agreement ratio —
the standard trust-region SLP shape. Once a feasible point gives a zero step, the radii
are cut and the loop continues until the ``Pg`` radius is below ``options.step_tol_mw``; at that
point the step is zero to within a chord of that width, the point is a KKT point to the same
accuracy, and the LP's row duals are the nonlinear problem's Lagrange multipliers: the
P-balance duals are the LMPs, with losses and voltage support priced in.

**What this is and is not.** It is a local method: it converges to a KKT point of a non-convex
problem, the same guarantee MATPOWER's MIPS, PYPOWER's PIPS and every production AC-OPF
offers. It starts from the AC power flow of the declared dispatch (flat if that fails), which
on the bundled cases leads to the optimum MATPOWER publishes for each of them. It is not an
interior-point method: a first-order model converges linearly, so expect some tens of LPs, each
a sparse problem HiGHS solves in milliseconds at case300 size.
"""

from __future__ import annotations

import dataclasses
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any

import highspy
import numpy as np
import numpy.typing as npt
from pydantic import BaseModel, ConfigDict, Field
from scipy import sparse

from mambo_power.numerics.arrays import NetworkArrays
from mambo_power.numerics.roles import effective_roles
from mambo_power.numerics.ybus import ybus, yf_yt
from mambo_power.opf.dc_opf import (
    ColArray,
    FloatArray,
    _add_rows,
    _extract_and_validate,
    _RowBlock,
)
from mambo_power.pf.ac_newton import _PQ, _PV, _SLACK, AcOptions, _dsbus_dv, newton

ComplexArray = npt.NDArray[np.complex128]

_OPTIMAL = "Optimal"
SOLVER = "highspy.Highs (trust-region SLP)"
"""Solver name stamped into the result provenance."""


class OpfAcOptions(BaseModel):
    """Options of :func:`ac_opf` / :func:`mambo_power.opf.solve_ac_opf`."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    tol: float = Field(
        default=1e-6,
        gt=0.0,
        description="Convergence tolerance, pu: the nodal mismatch and flow violation must be "
        "below it and the QP step's largest element too.",
    )
    max_iter: int = Field(default=200, ge=1, le=10000, description="Maximum LP steps.")
    step_tol_mw: float = Field(
        default=1e-3,
        gt=0.0,
        description="The Pg trust-region radius, MW, below which a zero step is accepted as "
        "converged; it bounds the dispatch error of the chord model of a quadratic cost.",
    )
    cost_tol: float = Field(
        default=1e-7,
        gt=0.0,
        description="Relative cost tolerance: a feasible point the LP model cannot improve by "
        "more than cost_tol × (1 + cost), or at which ten consecutive accepted steps each gained "
        "less than that, is converged.",
    )
    chords: int = Field(
        default=8, ge=2, description="Chords of a quadratic cost across the Pg trust region."
    )
    v_default_min_pu: float = Field(
        default=0.9, gt=0.0, description="Voltage floor for a bus with no v_min_pu."
    )
    v_default_max_pu: float = Field(
        default=1.1, gt=0.0, description="Voltage ceiling for a bus with no v_max_pu."
    )
    penalty: float = Field(
        default=1.0e3,
        gt=0.0,
        description="Merit-function and elastic-slack penalty, $/MW of nonlinear residual; "
        "above any plausible marginal price so the merit is an exact penalty function.",
    )
    restoration_iter: int = Field(
        default=5, ge=0, le=50, description="Newton iterations of the restoration after a step."
    )
    elastic_demand: bool = Field(
        default=False,
        description="solve_ac_opf only (ADR-030): honour Load.bid — a load with a bid is served "
        "where its marginal value meets the AC LMP, within [0, p_mw], at its own power factor. "
        "False keeps every load fixed, like solve_dc_opf.",
    )


@dataclass(frozen=True)
class AcOpfDuals:
    """Lagrange multipliers at the solution, bus/generator/branch order, $/MWh or $/MVArh."""

    lmp_p: FloatArray
    """Per-bus marginal cost of active demand, $/MWh — the AC LMP, losses included."""
    lmp_q: FloatArray
    """Per-bus marginal cost of reactive demand, $/MVArh."""
    gen_p_bound: FloatArray
    """Per-generator reduced cost of its active bound; 0 unless pinned."""
    gen_q_bound: FloatArray
    """Per-generator reduced cost of its reactive bound; 0 unless pinned."""
    v_bound: FloatArray
    """Per-bus reduced cost of its voltage bound, $/pu; 0 unless pinned."""
    flow_from: FloatArray
    """Per-branch dual of the from-side apparent-power limit, $/MVA²h; 0 unless binding."""
    flow_to: FloatArray
    """Per-branch dual of the to-side apparent-power limit; 0 unless binding."""
    angle: FloatArray = field(default_factory=lambda: np.zeros(0))
    """Per-branch dual of the angle-difference limit (ADR-029), $/rad·h: negative when the
    upper limit binds, positive when the lower one does, 0 otherwise or on an unlimited
    branch."""
    demand_bound: FloatArray = field(default_factory=lambda: np.zeros(0))
    """Per-elastic-load reduced cost of its ``[0, p_mw]`` bound (ADR-030), $/MWh, in
    :attr:`AcOpfSolution.demand_dispatch_mw` order; 0 unless pinned."""


@dataclass(frozen=True)
class AcOpfSolution:
    """Result of one :func:`ac_opf` run."""

    status: str
    """``"Optimal"`` for a converged KKT point; ``"IterationLimit"`` when ``max_iter`` LP steps
    did not converge; ``"Infeasible"`` when the trust region collapsed with the nonlinear
    residual still above tolerance (no AC-feasible point was found); or a HiGHS status the QP
    itself reported."""
    v: ComplexArray
    """Bus voltages, pu, at the final point."""
    gen_p_mw: FloatArray
    """Per-generator active dispatch, MW."""
    gen_q_mvar: FloatArray
    """Per-generator reactive dispatch, MVAr."""
    objective_cost: float
    """``Σ cost_g(Pg)`` at the final point, $/h (constant terms included)."""
    iterations: int
    """LP steps taken."""
    max_mismatch_pu: float
    """Largest nodal mismatch at the final point, pu."""
    max_flow_violation_pu: float
    """Largest apparent-power overload at the final point, pu² (``|S|² − rating²``)."""
    duals: AcOpfDuals | None
    """``None`` exactly when ``status != "Optimal"``."""
    message: str | None = None
    """Diagnostic when ``status != "Optimal"``."""
    s_from_pu: ComplexArray = field(default_factory=lambda: np.zeros(0, dtype=np.complex128))
    """Per-branch from-side complex flow, pu."""
    s_to_pu: ComplexArray = field(default_factory=lambda: np.zeros(0, dtype=np.complex128))
    """Per-branch to-side complex flow, pu."""
    demand_dispatch_mw: FloatArray = field(default_factory=lambda: np.zeros(0))
    """Per-elastic-load served demand, MW (ADR-030), in ``sorted(set(demand_bid_coeffs) |
    set(demand_pwl_bids))`` order like
    :attr:`~mambo_power.opf.dc_opf.OpfSolution.demand_dispatch_mw`; length 0 without bids."""
    demand_value: float = 0.0
    """``Σ value_d(P_d)`` of the elastic loads at the final point, $/h; the solver minimises
    ``objective_cost − demand_value``."""


def _dsbr_dv(
    yf: Any, yt: Any, v: ComplexArray, f: Any, t: Any
) -> tuple[Any, Any, Any, Any, ComplexArray, ComplexArray]:
    """MATPOWER ``dSbr_dV`` (polar): ``(dSf/dVa, dSf/dVm, dSt/dVa, dSt/dVm, Sf, St)``."""
    n_branch = yf.shape[0]
    i_f = yf @ v
    i_t = yt @ v
    vnorm = v / np.abs(v)
    rows = np.arange(n_branch)
    shape = (n_branch, v.size)
    c_f = sparse.csc_matrix((np.ones(n_branch), (rows, f)), shape=shape)
    c_t = sparse.csc_matrix((np.ones(n_branch), (rows, t)), shape=shape)
    diag_v = sparse.diags(v)
    diag_vnorm = sparse.diags(vnorm)
    diag_vf = sparse.diags(v[f])
    diag_vt = sparse.diags(v[t])
    diag_if = sparse.diags(i_f)
    diag_it = sparse.diags(i_t)
    dsf_dva = 1j * (diag_if.conj() @ c_f @ diag_v - diag_vf @ (yf @ diag_v).conj())
    dsf_dvm = diag_vf @ (yf @ diag_vnorm).conj() + diag_if.conj() @ c_f @ diag_vnorm
    dst_dva = 1j * (diag_it.conj() @ c_t @ diag_v - diag_vt @ (yt @ diag_v).conj())
    dst_dvm = diag_vt @ (yt @ diag_vnorm).conj() + diag_it.conj() @ c_t @ diag_vnorm
    s_f = np.asarray(v[f] * np.conj(i_f), dtype=np.complex128)
    s_t = np.asarray(v[t] * np.conj(i_t), dtype=np.complex128)
    return dsf_dva, dsf_dvm, dst_dva, dst_dvm, s_f, s_t


def _csr_block(matrix: Any, cols: ColArray) -> tuple[list[int], list[int], list[float]]:
    """Dense-free CSR pieces of a sparse row block whose columns map through ``cols``."""
    m = sparse.csr_matrix(matrix)
    m.eliminate_zeros()
    starts = [int(x) for x in m.indptr]
    indices = [int(cols[j]) for j in m.indices]
    values = [float(x) for x in m.data]
    return starts, indices, values


def _rows_from_blocks(
    blocks: Sequence[tuple[Any, ColArray]], lower: FloatArray, upper: FloatArray
) -> _RowBlock:
    """One :class:`_RowBlock` whose rows are the horizontal concatenation of sparse *blocks*,
    each paired with the LP columns its own columns map to."""
    n_rows = int(lower.size)
    parts = [_csr_block(matrix, cols) for matrix, cols in blocks]
    starts = [0]
    indices: list[int] = []
    values: list[float] = []
    for r in range(n_rows):
        for part_starts, part_indices, part_values in parts:
            lo, hi = part_starts[r], part_starts[r + 1]
            indices.extend(part_indices[lo:hi])
            values.extend(part_values[lo:hi])
        starts.append(len(indices))
    return _RowBlock(
        lower=np.asarray(lower, dtype=np.float64),
        upper=np.asarray(upper, dtype=np.float64),
        starts=np.asarray(starts, dtype=np.int32),
        indices=np.asarray(indices, dtype=np.int32),
        values=np.asarray(values, dtype=np.float64),
    )


def ac_opf(
    arr: NetworkArrays,
    cost_coeffs: FloatArray,
    options: OpfAcOptions,
    *,
    v_min_pu: FloatArray,
    v_max_pu: FloatArray,
    pwl_costs: Mapping[int, Sequence[tuple[float, float]]] | None = None,
    demand_bid_coeffs: Mapping[int, tuple[float, float, float]] | None = None,
    demand_pwl_bids: Mapping[int, Sequence[tuple[float, float]]] | None = None,
) -> AcOpfSolution:
    """Solve the AC-OPF of ``arr`` (module docstring).

    ``cost_coeffs`` and ``pwl_costs`` are :func:`~mambo_power.opf.dc_opf.dc_opf`'s (``(n_gen,
    3)`` ``[c2, c1, c0]`` rows; a piecewise-linear generator has an all-zero row and its points
    in ``pwl_costs``). ``v_min_pu``/``v_max_pu`` are per-bus voltage limits in ``arr`` bus
    order. Raises :class:`~mambo_power.opf.dc_opf.NonConvexCostError` up front for a non-convex
    cost and ``ValueError`` for mis-shaped limits; never raises for a run that does not
    converge — reported through ``status``/``message``.

    ``demand_bid_coeffs`` / ``demand_pwl_bids`` are :func:`~mambo_power.opf.dc_opf.dc_opf`'s
    (ADR-030): a load index in either becomes an elastic load served at ``P_d`` in
    ``[load_p_min, load_p_max]`` at its own power factor (``Q_d = P_d · q_mvar / p_mw``), its
    bid's value joining the objective as ``−value_d(P_d)``; a non-concave bid raises
    :class:`~mambo_power.opf.dc_opf.NonConcaveBidError` up front. Every other load stays fixed.
    """
    n_bus, n_gen, n_branch = arr.n_bus, len(arr.gen_ids), arr.n_branch
    base = arr.base_mva
    v_min_pu = np.asarray(v_min_pu, dtype=np.float64)
    v_max_pu = np.asarray(v_max_pu, dtype=np.float64)
    if v_min_pu.shape != (n_bus,) or v_max_pu.shape != (n_bus,):
        raise ValueError(f"v_min_pu and v_max_pu must have shape ({n_bus},), bus order")
    if np.any(v_min_pu > v_max_pu) or np.any(v_min_pu <= 0.0):
        raise ValueError("voltage limits must satisfy 0 < v_min_pu <= v_max_pu at every bus")
    problem = _extract_and_validate(
        cost_coeffs, pwl_costs, demand_bid_coeffs, demand_pwl_bids, n_gen, len(arr.load_ids)
    )
    c2, c1, c0 = problem.c2, problem.c1, problem.c0
    pwl_gen_idxs, segments_by_gen = problem.pwl_gen_idxs, problem.segments_by_gen
    # elastic loads (ADR-030): −value_d is convex, so it is carried exactly like a cost, as
    # chords of a2·p² + a1·p with a2 = −v2 >= 0, a1 = −v1 (a piecewise bid's segments negated)
    elastic = np.asarray(problem.elastic_load_idxs, dtype=np.int64)
    n_dem = elastic.size
    a2, a1, a0 = -problem.v2, -problem.v1, -problem.v0
    pwl_dem = [
        j for j, idx in enumerate(problem.elastic_load_idxs) if idx in problem.demand_pwl_idxs
    ]
    pwl_dem_set = set(pwl_dem)
    neg_segments_by_dem = {
        j: [(-slope, -intercept) for slope, intercept in problem.demand_segments_by_load[idx]]
        for j, idx in enumerate(problem.elastic_load_idxs)
        if idx in problem.demand_pwl_idxs
    }

    y = ybus(arr)
    yf, yt = yf_yt(arr)
    f_idx, t_idx = arr.f, arr.t
    rated = np.flatnonzero(np.isfinite(arr.rating_pu))
    # branches with an angle-difference limit (ADR-029): va[f] − va[t] within [min, max]
    angled = np.flatnonzero(np.isfinite(arr.angle_min_rad) | np.isfinite(arr.angle_max_rad))
    angle_lo = arr.angle_min_rad[angled]
    angle_hi = arr.angle_max_rad[angled]
    rating_sq = arr.rating_pu[rated] ** 2
    dem_bus = arr.load_bus[elastic]
    d_min, d_max = arr.load_p_min_pu[elastic] * base, arr.load_p_max_pu[elastic] * base
    with np.errstate(divide="ignore", invalid="ignore"):
        pf_ratio = np.where(d_max > 0.0, arr.load_q_pu[elastic] * base / d_max, 0.0)
    c_d = sparse.csc_matrix((np.ones(n_dem), (dem_bus, np.arange(n_dem))), shape=(n_bus, n_dem))
    # the bus aggregate holds every load at p_mw: take the elastic ones out, they come back
    # through P_d (dc_opf's double-counting contract)
    p_load_fixed = arr.p_load_pu - np.asarray(c_d @ (d_max / base)).ravel()
    q_load_fixed = arr.q_load_pu - np.asarray(c_d @ (pf_ratio * d_max / base)).ravel()

    def loads_at(pd_mw: FloatArray) -> tuple[FloatArray, FloatArray]:
        p_load = p_load_fixed + np.asarray(c_d @ (pd_mw / base)).ravel()
        q_load = q_load_fixed + np.asarray(c_d @ (pf_ratio * pd_mw / base)).ravel()
        return p_load, q_load

    gen_bus = arr.gen_bus
    c_g = sparse.csc_matrix((np.ones(n_gen), (gen_bus, np.arange(n_gen))), shape=(n_bus, n_gen))
    p_min, p_max = arr.gen_p_min_pu * base, arr.gen_p_max_pu * base
    q_min, q_max = arr.gen_q_min_pu * base, arr.gen_q_max_pu * base

    # --- starting point: the AC power flow of the declared dispatch, else flat ---------------
    roles = effective_roles(arr)
    # Q-limited, so the reactive dispatch starts inside its bounds and the start is feasible
    # up to the slack unit's own active bound; a Q-unlimited start would be pushed out of
    # balance by the clip below
    start = newton(arr, roles, AcOptions(q_limits=True, init="flat"))
    if not start.converged:
        start = newton(arr, roles, AcOptions(q_limits=False, init="flat"))
    if start.converged:
        v = start.v.copy()
        pg = np.clip(start.gen_p_pu * base, p_min, p_max)
        qg = np.clip(start.gen_q_pu * base, q_min, q_max)
    else:
        v = np.ones(n_bus, dtype=np.complex128)
        pg = np.clip(arr.gen_p_pu * base, p_min, p_max)
        qg = np.clip(arr.gen_q_pu * base, q_min, q_max)
    vm = np.clip(np.abs(v), v_min_pu, v_max_pu)
    va = np.angle(v)
    va -= va[arr.slack]
    v = vm * np.exp(1j * va)
    pd = d_max.copy()  # the declared demand, the power flow's own starting load

    def cost_of(pg_mw: FloatArray, pwl_value: float) -> float:
        return float(np.sum(c2 * pg_mw**2 + c1 * pg_mw + c0)) + pwl_value

    def pwl_cost_of(pg_mw: FloatArray) -> float:
        total = 0.0
        for g in pwl_gen_idxs:
            total += max(s * pg_mw[g] + b for s, b in segments_by_gen[g])
        return total

    def value_of(pd_mw: FloatArray) -> float:
        """``Σ value_d(P_d)``, $/h: the bids' worth of the demand served."""
        total = float(np.sum(-(a2 * pd_mw**2 + a1 * pd_mw + a0)))
        for j in pwl_dem:
            total -= max(s * pd_mw[j] + b for s, b in neg_segments_by_dem[j])
        return total

    def net_cost(pg_mw: FloatArray, pd_mw: FloatArray) -> float:
        return cost_of(pg_mw, pwl_cost_of(pg_mw)) - value_of(pd_mw)

    def residuals(
        v: ComplexArray, pg_mw: FloatArray, qg_mvar: FloatArray, pd_mw: FloatArray
    ) -> tuple[FloatArray, FloatArray, FloatArray, ComplexArray, ComplexArray]:
        s_bus = v * np.conj(y @ v)
        p_load, q_load = loads_at(pd_mw)
        g_p = s_bus.real + p_load - np.asarray(c_g @ (pg_mw / base)).ravel()
        g_q = s_bus.imag + q_load - np.asarray(c_g @ (qg_mvar / base)).ravel()
        s_f = v[f_idx] * np.conj(yf @ v)
        s_t = v[t_idx] * np.conj(yt @ v)
        vm = np.abs(v)
        va = np.angle(v)
        theta = va[f_idx[angled]] - va[t_idx[angled]]
        viol = np.concatenate(
            [
                np.abs(s_f[rated]) ** 2 - rating_sq,
                np.abs(s_t[rated]) ** 2 - rating_sq,
                v_min_pu - vm,  # a voltage outside its band is a violation like an overload
                vm - v_max_pu,
                np.where(np.isfinite(angle_lo), angle_lo - theta, 0.0),
                np.where(np.isfinite(angle_hi), theta - angle_hi, 0.0),
            ]
        )
        return g_p, g_q, np.maximum(viol, 0.0), s_f, s_t

    gen_buses = np.unique(gen_bus)
    has_gen = np.zeros(n_bus, dtype=np.bool_)
    has_gen[gen_buses] = True
    pf_bus_type = np.where(has_gen, _PV, _PQ).astype(np.int64)
    pf_bus_type[arr.slack] = _SLACK

    def restore(
        v: ComplexArray, pg_mw: FloatArray, qg_mvar: FloatArray, pd_mw: FloatArray
    ) -> tuple[ComplexArray, FloatArray, FloatArray]:
        """An AC power flow at the LP's point, by :func:`mambo_power.pf.ac_newton.newton`
        with its Q-limit rounds: generator buses hold the LP's magnitude (PV) and the slack its
        angle, every other voltage floats (PQ), and the balance is closed by the slack unit's
        ``Pg`` and the generator buses' ``Qg`` within their limits — a bus whose units hit a
        limit is converted to PQ and re-solved, exactly as the power flow does. What a
        first-order step leaves of the nodal residual is second order and this removes it."""
        vm = np.abs(v)
        gen_v_set = vm[gen_bus]
        p_load, q_load = loads_at(pd_mw)
        point = dataclasses.replace(
            arr,
            p_load_pu=p_load,
            q_load_pu=q_load,
            bus_type=pf_bus_type,
            v_set=np.where(has_gen, vm, 1.0),
            p_gen_pu=np.asarray(np.bincount(gen_bus, weights=pg_mw, minlength=n_bus) / base),
            q_gen_pu=np.asarray(np.bincount(gen_bus, weights=qg_mvar, minlength=n_bus) / base),
            gen_p_pu=pg_mw / base,
            gen_q_pu=qg_mvar / base,
            gen_v_set=gen_v_set,
        )
        solved = newton(
            point,
            effective_roles(point),
            AcOptions(
                tol=options.tol * 1e-3,
                max_iter=options.restoration_iter,
                q_limits=True,
                init="flat",
            ),
            v0=v,
        )
        if not np.all(np.isfinite(solved.v)):
            return v, pg_mw, qg_mvar
        pg_new = np.clip(solved.gen_p_pu * base, p_min, p_max)
        qg_new = np.clip(solved.gen_q_pu * base, q_min, q_max)
        return solved.v, pg_new, qg_new

    def merit(v: ComplexArray, pg_mw: FloatArray, qg_mvar: FloatArray, pd_mw: FloatArray) -> float:
        g_p, g_q, viol, _, _ = residuals(v, pg_mw, qg_mvar, pd_mw)
        residual = float(np.sum(np.abs(g_p)) + np.sum(np.abs(g_q)) + np.sum(viol))
        return net_cost(pg_mw, pd_mw) + options.penalty * base * residual

    # --- column layout of every LP: [dva | dvm | dpg | dqg | dpd | sp+ | sp- | sq+ | sq- |
    # flow and angle slacks | cost_g and −value_d epigraph columns]
    col_va = np.arange(0, n_bus, dtype=np.int32)
    col_vm = np.arange(n_bus, 2 * n_bus, dtype=np.int32)
    col_pg = np.arange(2 * n_bus, 2 * n_bus + n_gen, dtype=np.int32)
    col_qg = np.arange(2 * n_bus + n_gen, 2 * n_bus + 2 * n_gen, dtype=np.int32)
    col_pd = np.arange(2 * n_bus + 2 * n_gen, 2 * n_bus + 2 * n_gen + n_dem, dtype=np.int32)
    slack_base = 2 * n_bus + 2 * n_gen + n_dem
    col_sp_plus = np.arange(slack_base, slack_base + n_bus, dtype=np.int32)
    col_sp_minus = col_sp_plus + n_bus
    col_sq_plus = col_sp_plus + 2 * n_bus
    col_sq_minus = col_sp_plus + 3 * n_bus
    n_flow = 2 * rated.size + 2 * angled.size  # flow slacks, then angle slacks
    col_flow_slack = np.arange(
        slack_base + 4 * n_bus, slack_base + 4 * n_bus + 2 * rated.size, dtype=np.int32
    )
    col_angle_slack = np.arange(
        slack_base + 4 * n_bus + 2 * rated.size, slack_base + 4 * n_bus + n_flow, dtype=np.int32
    )
    cost_base = slack_base + 4 * n_bus + n_flow
    curved = sorted(set(pwl_gen_idxs) | set(np.flatnonzero(c2 != 0.0).tolist()))
    cost_col_of = {g: cost_base + j for j, g in enumerate(curved)}
    curved_dem = sorted(pwl_dem_set | set(np.flatnonzero(a2 != 0.0).tolist()))
    value_col_of = {j: cost_base + len(curved) + k for k, j in enumerate(curved_dem)}
    n_cols = cost_base + len(curved) + len(curved_dem)
    inf = highspy.kHighsInf

    def chords(
        q2: float, q1: float, at: float, lo_bound: float, hi_bound: float, radius: float
    ) -> list[tuple[float, float]]:
        """``(slope, intercept)`` chords of the convex quadratic ``q2·p² + q1·p``:
        ``options.chords`` across ``[at − radius, at + radius]`` (clipped to the bounds, the
        current *at* always a breakpoint) plus one chord out to each bound."""
        lo, hi = max(lo_bound, at - radius), min(hi_bound, at + radius)
        half = options.chords // 2
        points = sorted(
            {float(np.clip(at + radius * k / half, lo, hi)) for k in range(-half, half + 1)}
            | {float(lo_bound), float(hi_bound)}
        )
        segments = []
        for a, b in zip(points[:-1], points[1:], strict=True):
            if b - a <= 1e-12:
                continue
            ca = q2 * a * a + q1 * a
            cb = q2 * b * b + q1 * b
            slope = (cb - ca) / (b - a)
            segments.append((slope, ca - slope * a))
        if not segments:  # pinned by lo_bound == hi_bound
            segments.append((q1 + 2.0 * q2 * at, -q2 * at * at))
        return segments

    def chord_segments(g: int, radius: float) -> list[tuple[float, float]]:
        """Generator *g*'s quadratic cost as :func:`chords` through the current ``pg``."""
        return chords(float(c2[g]), float(c1[g]), float(pg[g]), p_min[g], p_max[g], radius)

    def demand_chord_segments(j: int, radius: float) -> list[tuple[float, float]]:
        """Elastic load *j*'s ``−value`` as :func:`chords` through the current ``pd``."""
        return chords(float(a2[j]), float(a1[j]), float(pd[j]), d_min[j], d_max[j], radius)

    stalled = 0
    radius_va, radius_vm = 0.2, 0.05
    pg_range = max(
        float(np.max(p_max - p_min)) if n_gen else 1.0,
        float(np.max(d_max - d_min)) if n_dem else 0.0,
    )
    radius_pg = max(pg_range / 10.0, 1.0)
    radius_min = 1e-9
    iterations = 0
    status = "IterationLimit"
    message: str | None = None
    duals: AcOpfDuals | None = None
    g_p, g_q, viol, s_f, s_t = residuals(v, pg, qg, pd)

    while iterations < options.max_iter:
        iterations += 1
        vm, va = np.abs(v), np.angle(v)
        ds_dvm, ds_dva = _dsbus_dv(y, v)
        dsf_dva, dsf_dvm, dst_dva, dst_dvm, s_f, s_t = _dsbr_dv(yf, yt, v, f_idx, t_idx)
        g_p, g_q, viol, _, _ = residuals(v, pg, qg, pd)

        h = highspy.Highs()  # type: ignore[no-untyped-call]  # highspy ships no type stubs
        h.setOptionValue("output_flag", False)
        lower = np.empty(n_cols)
        upper = np.empty(n_cols)
        lower[col_va], upper[col_va] = -radius_va, radius_va
        lower[arr.slack], upper[arr.slack] = 0.0, 0.0
        # a bus the restoration left outside its band is sent back to the band edge even if
        # that exceeds the radius: the bound, not the trust region, is the hard constraint
        lower[col_vm] = np.maximum(v_min_pu - vm, -radius_vm)
        upper[col_vm] = np.maximum(lower[col_vm], np.minimum(v_max_pu - vm, radius_vm))
        lower[col_vm] = np.minimum(lower[col_vm], upper[col_vm])
        lower[col_pg] = np.maximum(p_min - pg, -radius_pg)
        upper[col_pg] = np.maximum(lower[col_pg], np.minimum(p_max - pg, radius_pg))
        lower[col_qg], upper[col_qg] = q_min - qg, q_max - qg
        lower[col_pd] = np.maximum(d_min - pd, -radius_pg)
        upper[col_pd] = np.maximum(lower[col_pd], np.minimum(d_max - pd, radius_pg))
        lower[slack_base:cost_base], upper[slack_base:cost_base] = 0.0, inf
        lower[cost_base:], upper[cost_base:] = -inf, inf
        # a bound within rounding of zero is zero: HiGHS treats 1e-16 as a tiny open interval
        lower[np.abs(lower) < 1e-12] = 0.0
        upper[np.abs(upper) < 1e-12] = 0.0
        h.addVars(n_cols, lower, upper)
        cost = np.zeros(n_cols)
        cost[col_pg] = np.where(c2 != 0.0, 0.0, c1)  # a curved unit's cost is its cost_g column
        cost[col_pg[pwl_gen_idxs]] = 0.0
        cost[col_pd] = np.where(a2 != 0.0, 0.0, a1)  # −v1: served demand is worth its bid
        cost[col_pd[pwl_dem]] = 0.0
        cost[slack_base:cost_base] = options.penalty * base  # slacks are pu, the penalty $/MW
        cost[cost_base:] = 1.0
        h.changeColsCost(n_cols, np.arange(n_cols, dtype=np.int32), cost)

        # nodal balance, linearised (pu): J·[dva, dvm] − C_g·dp/base + s⁺ − s⁻ = −g
        eye = sparse.identity(n_bus, format="csc")
        _add_rows(
            h,
            _rows_from_blocks(
                [
                    (ds_dva.real, col_va),
                    (ds_dvm.real, col_vm),
                    (-c_g / base, col_pg),
                    (c_d / base, col_pd),
                    (eye, col_sp_plus),
                    (-eye, col_sp_minus),
                ],
                -g_p,
                -g_p,
            ),
        )
        _add_rows(
            h,
            _rows_from_blocks(
                [
                    (ds_dva.imag, col_va),
                    (ds_dvm.imag, col_vm),
                    (-c_g / base, col_qg),
                    (c_d @ sparse.diags(pf_ratio) / base, col_pd),
                    (eye, col_sq_plus),
                    (-eye, col_sq_minus),
                ],
                -g_q,
                -g_q,
            ),
        )
        # apparent-power limits, linearised: 2P·dP + 2Q·dQ <= rating² − |S|²
        if rated.size:
            for side, (ds_dva_side, ds_dvm_side, s_side) in enumerate(
                ((dsf_dva, dsf_dvm, s_f), (dst_dva, dst_dvm, s_t))
            ):
                p_side, q_side = s_side.real[rated], s_side.imag[rated]
                scale_p = sparse.diags(2.0 * p_side)
                scale_q = sparse.diags(2.0 * q_side)
                d_va = scale_p @ ds_dva_side[rated].real + scale_q @ ds_dva_side[rated].imag
                d_vm = scale_p @ ds_dvm_side[rated].real + scale_q @ ds_dvm_side[rated].imag
                slack_cols = col_flow_slack[side * rated.size : (side + 1) * rated.size]
                _add_rows(
                    h,
                    _rows_from_blocks(
                        [
                            (d_va, col_va),
                            (d_vm, col_vm),
                            (-sparse.identity(rated.size, format="csc"), slack_cols),
                        ],
                        np.full(rated.size, -inf),
                        rating_sq - np.abs(s_side[rated]) ** 2,
                    ),
                )
        # angle-difference limits (ADR-029), exact in the step: dva[f] − dva[t] − s⁺ <= max − θ,
        # dva[f] − dva[t] + s⁻ >= min − θ, one elastic slack per side like a flow row
        if angled.size:
            theta_now = va[f_idx[angled]] - va[t_idx[angled]]
            incidence = sparse.csc_matrix(
                (
                    np.concatenate([np.ones(angled.size), -np.ones(angled.size)]),
                    (
                        np.concatenate([np.arange(angled.size), np.arange(angled.size)]),
                        np.concatenate([f_idx[angled], t_idx[angled]]),
                    ),
                ),
                shape=(angled.size, n_bus),
            )
            eye_a = sparse.identity(angled.size, format="csc")
            _add_rows(
                h,
                _rows_from_blocks(
                    [(incidence, col_va), (-eye_a, col_angle_slack[: angled.size])],
                    np.full(angled.size, -inf),
                    np.where(np.isfinite(angle_hi), angle_hi - theta_now, inf),
                ),
            )
            _add_rows(
                h,
                _rows_from_blocks(
                    [(incidence, col_va), (eye_a, col_angle_slack[angled.size :])],
                    np.where(np.isfinite(angle_lo), angle_lo - theta_now, -inf),
                    np.full(angled.size, inf),
                ),
            )
        # epigraph rows, cost_g − slope·dpg >= slope·pg + intercept: a piecewise-linear cost's
        # own segments, a quadratic cost's chords through the current dispatch; the same for
        # an elastic load's −value over its dpd column
        if curved or curved_dem:
            rows = []
            rhs = []
            for g in curved:
                segments = (
                    segments_by_gen[g] if g in segments_by_gen else chord_segments(g, radius_pg)
                )
                for slope, intercept in segments:
                    rows.append([(cost_col_of[g], 1.0), (int(col_pg[g]), -slope)])
                    rhs.append(slope * pg[g] + intercept)
            for j in curved_dem:
                segments = (
                    neg_segments_by_dem[j]
                    if j in pwl_dem_set
                    else demand_chord_segments(j, radius_pg)
                )
                for slope, intercept in segments:
                    rows.append([(value_col_of[j], 1.0), (int(col_pd[j]), -slope)])
                    rhs.append(slope * pd[j] + intercept)
            block = _RowBlock(
                lower=np.asarray(rhs),
                upper=np.full(len(rhs), inf),
                starts=np.arange(0, 2 * len(rows) + 1, 2, dtype=np.int32),
                indices=np.asarray([c for row in rows for c, _ in row], dtype=np.int32),
                values=np.asarray([x for row in rows for _, x in row], dtype=np.float64),
            )
            _add_rows(h, block)

        h.run()
        qp_status = h.modelStatusToString(h.getModelStatus())
        if qp_status != _OPTIMAL:
            status = qp_status
            message = f"ac_opf: HiGHS reported model status {qp_status!r} at iteration {iterations}"
            break
        sol = h.getSolution()
        step = np.asarray(sol.col_value, dtype=np.float64)
        d_va, d_vm = step[col_va], step[col_vm]
        d_pg, d_qg, d_pd = step[col_pg], step[col_qg], step[col_pd]
        slack_total = float(np.sum(step[slack_base:cost_base]))

        # convergence: a feasible point from which the LP moves nowhere — or gains nothing
        feasible = max(np.max(np.abs(g_p)), np.max(np.abs(g_q))) <= options.tol and (
            viol.size == 0 or np.max(viol) <= options.tol
        )
        step_norm = max(
            np.max(np.abs(d_va)),
            np.max(np.abs(d_vm)),
            np.max(np.abs(d_pg)) / base if n_gen else 0.0,
            np.max(np.abs(d_qg)) / base if n_gen else 0.0,
            np.max(np.abs(d_pd)) / base if n_dem else 0.0,
        )
        linear = np.flatnonzero((c2 == 0.0) & ~np.isin(np.arange(n_gen), pwl_gen_idxs))
        linear_dem = np.flatnonzero((a2 == 0.0) & ~np.isin(np.arange(n_dem), pwl_dem))
        merit_now = merit(v, pg, qg, pd)
        # the model's prediction: linearised residual is zero except the elastic slacks, and the
        # linearised flow rows hold, so the predicted merit is the LP objective (in $/h)
        model_cost = float(
            np.sum(c1[linear] * (pg[linear] + d_pg[linear]))
            + np.sum(c0)
            + sum(step[cost_col_of[g]] for g in curved)
            + np.sum(a1[linear_dem] * (pd[linear_dem] + d_pd[linear_dem]))
            + np.sum(a0)
            + sum(step[value_col_of[j]] for j in curved_dem)
            + options.penalty * base * slack_total
        )
        predicted = merit_now - model_cost
        economic_tol = options.cost_tol * (1.0 + abs(merit_now))
        stationary = step_norm <= options.tol or predicted <= economic_tol or stalled >= 10
        if feasible and stationary and slack_total <= options.tol:
            if radius_pg > options.step_tol_mw:
                # a zero step at this chord width: refine the model and look again
                radius_pg = max(radius_pg / 4.0, options.step_tol_mw)
                radius_va, radius_vm = max(radius_va / 4.0, 1e-6), max(radius_vm / 4.0, 1e-6)
                continue
            row_dual = np.asarray(sol.row_dual, dtype=np.float64)
            col_dual = np.asarray(sol.col_dual, dtype=np.float64)
            flow_from = np.zeros(n_branch)
            flow_to = np.zeros(n_branch)
            if rated.size:
                flow_from[rated] = row_dual[2 * n_bus : 2 * n_bus + rated.size]
                flow_to[rated] = row_dual[2 * n_bus + rated.size : 2 * n_bus + 2 * rated.size]
            angle_dual = np.zeros(n_branch)
            if angled.size:
                angle_base = 2 * n_bus + 2 * rated.size
                angle_dual[angled] = (
                    row_dual[angle_base : angle_base + angled.size]
                    + row_dual[angle_base + angled.size : angle_base + 2 * angled.size]
                )
            # the balance row carries −C_g·dp/base: a $/pu·h dual on it is −base × the price
            # a column's reduced cost belongs to its physical bound only when the column sits
            # on that bound; on a trust-region bound it is an artefact of the last radius
            at_p = (np.abs(pg - p_min) <= 1e-6) | (np.abs(pg - p_max) <= 1e-6)
            at_q = (np.abs(qg - q_min) <= 1e-6) | (np.abs(qg - q_max) <= 1e-6)
            at_v = (np.abs(vm - v_min_pu) <= 1e-6) | (np.abs(vm - v_max_pu) <= 1e-6)
            at_d = (np.abs(pd - d_min) <= 1e-6) | (np.abs(pd - d_max) <= 1e-6)
            duals = AcOpfDuals(
                lmp_p=-row_dual[:n_bus] / base,
                lmp_q=-row_dual[n_bus : 2 * n_bus] / base,
                gen_p_bound=np.where(at_p, col_dual[col_pg], 0.0),
                gen_q_bound=np.where(at_q, col_dual[col_qg], 0.0),
                v_bound=np.where(at_v, col_dual[col_vm], 0.0),
                flow_from=flow_from,
                flow_to=flow_to,
                angle=angle_dual,
                demand_bound=np.where(at_d, col_dual[col_pd], 0.0),
            )
            status = _OPTIMAL
            message = None
            break

        # trust-region step acceptance on the ℓ₁ merit function
        pg_new = np.clip(pg + d_pg, p_min, p_max)
        qg_new = np.clip(qg + d_qg, q_min, q_max)
        pd_new = np.clip(pd + d_pd, d_min, d_max)
        vm_new = np.clip(vm + d_vm, v_min_pu, v_max_pu)
        va_new = va + d_va
        v_new = np.asarray(vm_new * np.exp(1j * va_new), dtype=np.complex128)
        v_new, pg_new, qg_new = restore(v_new, pg_new, qg_new, pd_new)
        merit_new = merit(v_new, pg_new, qg_new, pd_new)
        actual = merit_now - merit_new
        ratio = actual / predicted if predicted > 1e-12 else (1.0 if actual >= 0.0 else -1.0)
        at_boundary = (
            np.max(np.abs(d_va)) >= 0.99 * radius_va
            or np.max(np.abs(d_vm)) >= 0.99 * radius_vm
            or (n_gen and np.max(np.abs(d_pg)) >= 0.99 * radius_pg)
            or (n_dem and np.max(np.abs(d_pd)) >= 0.99 * radius_pg)
        )
        if ratio >= 0.1:
            stalled = stalled + 1 if actual <= economic_tol else 0
            v, pg, qg, pd = v_new, pg_new, qg_new, pd_new
            if ratio >= 0.25 and at_boundary:
                radius_va = min(2.0 * radius_va, 1.0)
                radius_vm = min(2.0 * radius_vm, 0.2)
                radius_pg = min(2.0 * radius_pg, pg_range)
        else:
            radius_va *= 0.5
            radius_vm *= 0.5
            radius_pg = max(radius_pg * 0.5, options.step_tol_mw)
            if radius_vm < radius_min:
                g_p, g_q, viol, _, _ = residuals(v, pg, qg, pd)
                status = "Infeasible" if not feasible else "IterationLimit"
                message = (
                    f"ac_opf: trust region collapsed at iteration {iterations} with max mismatch "
                    f"{max(np.max(np.abs(g_p)), np.max(np.abs(g_q))):.3e} pu"
                )
                break
    else:
        message = f"ac_opf: did not converge in {options.max_iter} LP steps"

    g_p, g_q, viol, s_f, s_t = residuals(v, pg, qg, pd)
    return AcOpfSolution(
        status=status,
        v=v,
        gen_p_mw=pg,
        gen_q_mvar=qg,
        objective_cost=cost_of(pg, pwl_cost_of(pg)),
        iterations=iterations,
        max_mismatch_pu=float(max(np.max(np.abs(g_p)), np.max(np.abs(g_q)))) if n_bus else 0.0,
        max_flow_violation_pu=float(np.max(viol)) if viol.size else 0.0,
        duals=duals if status == _OPTIMAL else None,
        message=message,
        s_from_pu=s_f,
        s_to_pu=s_t,
        demand_dispatch_mw=pd,
        demand_value=value_of(pd),
    )
