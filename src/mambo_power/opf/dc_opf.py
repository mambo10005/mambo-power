"""DC-OPF LP/QP builder over HiGHS (spec design item 1; W1, W2).

Array-level entry point: :func:`dc_opf` is pure numerics over
:class:`~mambo_power.numerics.NetworkArrays` plus a caller-supplied cost-coefficient array — no
``Network``/``Scenario`` dependency, mirroring :func:`mambo_power.pf.ac_newton.newton` /
:func:`mambo_power.pf.dc.solve`. The Network-facing wrapper is
:func:`mambo_power.opf.solve_dc_opf`.

**Formulation.** One decision variable per generator (``NetworkArrays`` generator order),
bounded by its declared ``[p_min_mw, p_max_mw]``. Two row families, both built directly on
:class:`highspy.Highs` with the exact ``addVars``/``changeColsCost``/``addRows`` CSR API proven
in ``record/m3-research.md`` §1:

* **One system-wide nodal-balance equality row**: ``Σ p_g == Σ p_load + Σ g_shunt`` (a DC/
  lossless network has no other sink; phase-shifter injections net to zero system-wide by
  construction, so they never enter this row — see the module's own derivation in the
  implementation comments below). Its dual is the *energy* component of every bus's LMP
  (:func:`lmp_decomposition`).
* **One PTDF-based flow-limit row per branch**: ``-rating <= Σ_g PTDF[k, gen_bus[g]]·p_g +
  const_k <= rating``, where ``const_k`` folds in the branch's fixed (load/shunt/phase-shift)
  contribution to its flow — see the derivation in :func:`dc_opf`. Unrated branches (``rating ==
  inf``) get an unconstrained row (never binds; its dual is always 0). Its dual is the
  *congestion* component.

**Cost.** ``cost_coeffs`` is a caller-supplied ``(n_gen, 3)`` array, columns ``[c2, c1, c0]``
(:class:`~mambo_power.model.PolynomialCost` order, "highest order first", zero-padded — see
:func:`mambo_power.opf.solve_dc_opf`'s cost extraction). The wave's five OPF-parity fixtures
carry genuine nonzero quadratic (``c2``) coefficients (confirmed by direct probe against every
fixture's raw ``gencost`` block — no fixture's generator cost is purely linear), and pandapower's
own ``rundcopp`` honours them (``_from_ppc_gencost`` maps MATPOWER's ``c2``/``c1``/``c0``
straight into ``cp2_eur_per_mw2``/``cp1_eur_per_mw``/``cp0_eur``, the same unscaled
``cost(p) = c2·p² + c1·p + c0`` convention MATPOWER's gencost itself uses) — so matching
pandapower's dispatch on real fixture data requires honouring the quadratic term, not just the
linear one. ``dc_opf`` therefore stays a pure LP (no Hessian call at all) whenever every
generator's ``c2`` is exactly 0 — the common case, and the literal "single LP" the wave spec
describes — and transparently extends to a convex QP via ``Highs.passHessian`` only when a
nonzero ``c2`` is present. Both paths were probed directly against an independent hand-KKT
solve before being relied on here (``.bionic/tmp/m3-s2-progress.md``): HiGHS's diagonal-Hessian
convention is ``0.5·xᵀQx``, so the Hessian value for generator ``g`` is ``2·c2[g]``; the
resulting dispatch and ``row_dual``/``col_dual`` values matched the hand solve exactly, so no
QP-specific dual-reading logic is needed — :func:`dc_opf` reads duals identically in both cases.

Startup/shutdown costs (:class:`~mambo_power.model.PolynomialCost`'s ``startup``/``shutdown``
fields) are not modelled: this is a single-period economic dispatch over already-committed
generators (no unit-commitment decision), matching pandapower's own ``rundcopp``, which does not
model them either.

**Duals.** After ``Highs.run()``, ``Highs.getSolution().row_dual``/``col_dual`` are read
directly — proven generically in ``record/m3-research.md`` §1, and re-verified here for both the
pure-LP and the QP path. No PTDF-reconstruction fallback is needed.

**PWL costs.** Out of scope for this slice (wave M3 slice S3); ``cost_coeffs`` with more than 3
columns, or a caller wanting a piecewise-linear formulation, is not this module's job —
:func:`mambo_power.opf.solve_dc_opf` raises ``NotImplementedError`` up front for a
:class:`~mambo_power.model.PiecewiseCost` generator rather than silently misreading it as
polynomial. There is no PWL-specific branch inside :func:`dc_opf` to leave a seam for; the clean
extension point is ``cost_coeffs``'s own shape and the row-building block below, both untouched
by this slice.
"""

from __future__ import annotations

from dataclasses import dataclass

import highspy
import numpy as np
import numpy.typing as npt
from pydantic import BaseModel, ConfigDict

from mambo_power.numerics.arrays import NetworkArrays
from mambo_power.numerics.bbus import pf_shift
from mambo_power.numerics.ptdf import ptdf as compute_ptdf

FloatArray = npt.NDArray[np.float64]

SOLVER = "highspy.Highs"
"""Solver backend name stamped into the result provenance."""

_OPTIMAL = "Optimal"


class OpfDcOptions(BaseModel):
    """Options of the DC-OPF LP/QP solve.

    Empty today: HiGHS needs no tuning for the problems this wave builds (small dense LPs/QPs,
    always solved to default tolerances). A field is added here, not invented speculatively,
    the first time a caller actually needs to tune something (mirrors the guidance behind
    :class:`~mambo_power.pf.ac_newton.AcOptions`'s much larger option set: every field there
    controls real solver behaviour).
    """

    model_config = ConfigDict(extra="forbid", frozen=True)


@dataclass(frozen=True)
class OpfDuals:
    """Shadow prices from one :func:`dc_opf` solve, in ``NetworkArrays`` order."""

    balance: float
    """Shadow price of the single system-wide nodal-balance row, $/MWh — the energy component
    of every bus's LMP (:func:`lmp_decomposition`); also exactly equal to an *unconstrained*
    slack-bus generator's own linear cost coefficient, since the slack bus's PTDF column is
    always zero (no congestion term enters its stationarity condition)."""
    flow_limit: FloatArray
    """Per-branch shadow price of the ``[-rating, rating]`` flow row, branch order; 0 off the
    binding set (including every unrated branch, whose row never binds)."""
    gen_bound: FloatArray
    """Per-generator reduced cost of its ``[p_min, p_max]`` bound, generator order; 0 unless the
    generator is pinned at a bound."""


@dataclass(frozen=True)
class OpfSolution:
    """Result of one :func:`dc_opf` solve."""

    status: str
    """HiGHS's own model-status string. This wave's callers branch on ``"Optimal"``,
    ``"Infeasible"`` and ``"Unbounded"``; any other status HiGHS can report (e.g. a time or
    iteration limit) is passed through verbatim rather than mapped, since none of this wave's
    options can trigger one."""
    dispatch_mw: FloatArray
    """Per-generator dispatch, MW, generator order; all-zero when ``status != "Optimal"``."""
    objective_cost: float
    """Total generation cost, $/h — ``Σ (c2·p² + c1·p + c0)`` at the found dispatch, including
    every generator's constant term (HiGHS's own objective value omits it, since a constant
    does not affect the optimum; added back here for a cost figure comparable to an external
    oracle's). 0.0 when ``status != "Optimal"``."""
    duals: OpfDuals | None
    """``None`` exactly when ``status != "Optimal"``."""
    message: str | None = None
    """Diagnostic when ``status != "Optimal"``; ``None`` otherwise."""


@dataclass(frozen=True)
class LmpBreakdown:
    """Per-bus locational marginal price, decomposed into its energy and congestion terms."""

    lmp: FloatArray
    """``energy + congestion``, bus order."""
    energy: FloatArray
    """The balance dual, broadcast to every bus (uniform system-wide energy price)."""
    congestion: FloatArray
    """``flow_limit_duals @ ptdf``: each bus's exposure to every binding flow-limit row."""


def lmp_decomposition(duals: OpfDuals, ptdf: FloatArray) -> LmpBreakdown:
    """Per-bus LMP = balance dual (energy) + Σ(flow-limit-row duals × that bus's PTDF column).

    Standalone and independent of :func:`dc_opf`/:func:`mambo_power.opf.solve_dc_opf` — callable
    with any hand-built ``OpfDuals``/PTDF pair (spec design item 2); a later wave's
    ``market.nodal`` calls this identically with its own duals.
    """
    n_bus = ptdf.shape[1]
    energy = np.full(n_bus, duals.balance, dtype=np.float64)
    congestion = np.asarray(duals.flow_limit @ ptdf, dtype=np.float64)
    return LmpBreakdown(lmp=energy + congestion, energy=energy, congestion=congestion)


def dc_opf(arr: NetworkArrays, cost_coeffs: FloatArray, options: OpfDcOptions) -> OpfSolution:
    """Solve the DC-OPF LP/QP of ``arr`` (module docstring): minimise Σ cost(p_g) subject to one
    system-wide nodal-balance row and one PTDF-based flow-limit row per branch, over generator
    bounds. ``cost_coeffs`` is ``(n_gen, 3)``, columns ``[c2, c1, c0]``, generator order. Never
    raises for an infeasible or unbounded model — reported through ``status``/``message``.
    """
    del options  # no tunable fields yet (OpfDcOptions docstring)
    n_gen = len(arr.gen_ids)
    coeffs = np.asarray(cost_coeffs, dtype=np.float64)
    if coeffs.shape != (n_gen, 3):
        raise ValueError(
            f"cost_coeffs must have shape ({n_gen}, 3) ([c2, c1, c0] per generator), "
            f"got {coeffs.shape}"
        )
    c2, c1, c0 = coeffs[:, 0], coeffs[:, 1], coeffs[:, 2]

    h = highspy.Highs()  # type: ignore[no-untyped-call]  # highspy ships no type stubs
    h.setOptionValue("output_flag", False)

    p_min = arr.gen_p_min_pu * arr.base_mva
    p_max = arr.gen_p_max_pu * arr.base_mva
    if n_gen:
        h.addVars(n_gen, p_min, p_max)
        h.changeColsCost(n_gen, np.arange(n_gen, dtype=np.int32), c1)
        nz = np.flatnonzero(c2)
        if nz.size:
            hess = highspy.HighsHessian()
            hess.dim_ = n_gen
            hess.format_ = highspy.HessianFormat.kTriangular
            starts = np.zeros(n_gen + 1, dtype=np.int32)
            starts[nz + 1] = 1
            starts = np.cumsum(starts).astype(np.int32)
            hess.start_ = starts.tolist()
            hess.index_ = nz.tolist()
            hess.value_ = (2.0 * c2[nz]).tolist()
            h.passHessian(hess)

    # --- nodal balance: Σ p_g == Σ p_load + Σ g_shunt (module docstring; phase shifts cancel
    # system-wide because Σ_bus p_shift == Σ_branch (pf_shift_k − pf_shift_k) == 0 identically).
    p_load_mw = arr.p_load_pu * arr.base_mva
    g_shunt_mw = arr.g_shunt_pu * arr.base_mva
    total_fixed = float(np.sum(p_load_mw) + np.sum(g_shunt_mw))

    # --- flow-limit rows: flow_k = Σ_g PTDF[k, gen_bus[g]]·p_g + const_k, where
    # const_k = pf_shift_mw_k − Σ_bus PTDF[k, bus]·(p_load_mw[bus] + g_shunt_mw[bus]) folds in
    # every *fixed* contribution to branch k's flow (derivation: module docstring above).
    # Row bounds: −rating_k − const_k <= row_expr_k <= rating_k − const_k.
    ptdf_matrix = compute_ptdf(arr)
    pf_shift_mw = pf_shift(arr) * arr.base_mva
    fixed_bus_mw = p_load_mw + g_shunt_mw
    const = pf_shift_mw - ptdf_matrix @ fixed_bus_mw
    rating_mw = arr.rating_pu * arr.base_mva  # inf where unrated -> row never binds

    n_rows = 1 + arr.n_branch
    lower = np.empty(n_rows)
    upper = np.empty(n_rows)
    lower[0] = total_fixed
    upper[0] = total_fixed
    lower[1:] = -rating_mw - const
    upper[1:] = rating_mw - const

    if n_gen:
        balance_row = np.ones((1, n_gen))
        flow_rows = ptdf_matrix[:, arr.gen_bus] if arr.n_branch else np.zeros((0, n_gen))
        dense = np.vstack([balance_row, flow_rows])
        row_starts = np.arange(0, n_gen * n_rows + 1, n_gen, dtype=np.int32)
        col_indices = np.tile(np.arange(n_gen, dtype=np.int32), n_rows)
        values = dense.ravel()
        h.addRows(n_rows, lower, upper, col_indices.size, row_starts, col_indices, values)
    else:
        row_starts = np.zeros(n_rows + 1, dtype=np.int32)
        h.addRows(n_rows, lower, upper, 0, row_starts, np.zeros(0, dtype=np.int32), np.zeros(0))

    h.run()
    status = h.modelStatusToString(h.getModelStatus())
    if status != _OPTIMAL:
        return OpfSolution(
            status=status,
            dispatch_mw=np.zeros(n_gen),
            objective_cost=0.0,
            duals=None,
            message=f"dc_opf: HiGHS reported model status {status!r}",
        )

    sol = h.getSolution()
    dispatch_mw = np.asarray(sol.col_value, dtype=np.float64)
    duals = OpfDuals(
        balance=float(sol.row_dual[0]) if n_rows else 0.0,
        flow_limit=np.asarray(sol.row_dual[1:], dtype=np.float64),
        gen_bound=np.asarray(sol.col_dual, dtype=np.float64),
    )
    objective_cost = float(h.getInfo().objective_function_value + np.sum(c0))
    return OpfSolution(
        status=status,
        dispatch_mw=dispatch_mw,
        objective_cost=objective_cost,
        duals=duals,
        message=None,
    )
