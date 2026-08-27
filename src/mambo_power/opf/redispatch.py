"""Min-cost redispatch LP/QP from a zonal operating point (wave M6 W3, spec AC-3/AC-4).

Array-level entry point: :func:`redispatch_dc_opf` is pure numerics over
:class:`~mambo_power.numerics.NetworkArrays` plus the caller's cost/bid data and a starting
operating point ``(p0, d0)`` — no ``Network``/``Scenario`` dependency, exactly as
:func:`~mambo_power.opf.dc_opf.dc_opf` and
:func:`~mambo_power.opf.multiperiod.multiperiod_dc_opf` are. It is the third caller of
``dc_opf``'s row-family core (ADR-007/ADR-008): ``_extract_and_validate``, ``_balance_row``,
``_flow_limit_rows``, ``_epigraph_rows``, ``_hypograph_rows`` and ``_add_rows`` are imported and
used unmodified, and **no new row-family helper is introduced** — the one genuinely new row this
module needs (the PWL linking equality below) is an instance of ``_balance_row``, whose own
docstring records that it is pure algebra over LP column indices and "does not care what a column
represents".

**What the LP is.** Given a zonal-cleared operating point — a per-generator dispatch ``p0`` and a
per-bid-load served demand ``d0``, typically produced by ``opf.zonal``'s network-blind clearing
and therefore *not* deliverable on the real network — find the cheapest way to move to a point the
real network can carry. The move is expressed as four nonnegative column families:

* ``Δp+_g in [0, p_max_g − p0_g]`` and ``Δp-_g in [0, p0_g − p_min_g]`` per generator;
* ``Δd+_d in [0, d_max_d − d0_d]`` and ``Δd-_d in [0, d0_d − d_min_d]`` per bid load.

The final point is ``p_g = p0_g + Δp+_g − Δp-_g`` and ``d_d = d0_d + Δd+_d − Δd-_d``. Because the
bounds are exactly the *shifted* generator/load bounds, the final point ranges over precisely
``[p_min, p_max]`` and ``[d_min, d_max]`` — the same box nodal has, no larger and no smaller.
(``NetworkArrays.load_p_min_pu`` is all-zero on every network W3 builds, so ``[0, d0_d − d_min_d]``
is today the ``[0, d0_d]`` the wave brief names; it is written against ``d_min`` anyway, because it
is ``d_min`` and not ``0`` that the theorem below actually needs.)

**Design decision D1: true cost/value curves in the objective.** The objective is the *true*
welfare function evaluated at the *final* quantity — ``Σ_g cost_g(p0_g + Δp+_g − Δp-_g) −
Σ_d value_d(d0_d + Δd+_d − Δd-_d)`` — not a linear rate anchored at ``(p0, d0)``. Research §3(a)
proposed the anchored rate and §4(b) then proved it carries a systematic over-curtailment bias
(its worked example curtails a load to zero and reports generation cost 0 against nodal's 1800
while destroying welfare); the design interview rejected it at D1 and the spec's ``## Rejected
alternatives`` records the rejection. So the objective here is the exact one, mechanically:

* **quadratic participants** — ``cost_g(p0+u) = c2·(p0+u)² + c1·(p0+u) + c0`` expands to a
  constant, a *linear* term ``(c1 + 2·c2·p0)·u`` and a *quadratic* term ``c2·u²`` where
  ``u = Δp+ − Δp-``. The linear part is a column cost (``+mc`` on ``Δp+``, ``−mc`` on ``Δp-``);
  the quadratic part is a **2x2 Hessian block coupling the pair**, ``2·c2·[[1, −1], [−1, 1]]``, not
  the diagonal block ``dc_opf`` passes over its single dispatch column. The demand side mirrors it
  with ``−v2``/``−mv`` (the same sign mirror ``dc_opf`` already draws). The constant terms
  (``c2·p0² + c1·p0 + c0``, ``v2·d0² + v1·d0 + v0``) are dropped from the LP, as constants always
  are, and added back into :attr:`RedispatchSolution.objective_cost` /
  :attr:`~RedispatchSolution.demand_value`, which are recomputed from the final quantities
  directly.
* **piecewise-linear participants** — the epigraph/hypograph encoding needs the cost row to see
  *one* column carrying the final quantity, and here the final quantity spans two. So a PWL
  participant gets one extra column ``q`` (bounded by its own ``[p_min, p_max]`` /
  ``[d_min, d_max]``) tied to its delta pair by the linking equality ``q + Δ- − Δ+ == p0`` — an
  ordinary ``_balance_row`` with ``q``/``Δ-`` on the injection side and ``Δ+`` on the withdrawal
  side. ``_epigraph_rows``/``_hypograph_rows`` are then called verbatim, with ``q`` where
  ``dc_opf`` passes its dispatch column. Only PWL participants pay for this column; a quadratic
  one has no ``q`` at all.

**The double-counting contract, applied to the zonal point.** ``dc_opf`` owns the rule that the
caller passes ``arr`` unmodified and the builder removes each bid load's historical ``p_mw`` from
the fixed RHS itself (its module docstring, "Elastic demand"). This module keeps that rule and
extends it by one step: since the delta columns measure movement *away from* ``(p0, d0)``, the
zonal point itself is fixed data and belongs on the right-hand side too.

* balance: ``Σ Δp+ − Σ Δp- + Σ Δd- − Σ Δd+ == total_fixed − Σ_g p0_g + Σ_d d0_d``, i.e.
  ``dc_opf``'s own ``total_fixed`` with the zonal point moved across the equals sign.
* flow limits: ``const_k`` gains ``+ Σ_g PTDF[k, gen_bus[g]]·p0_g − Σ_d PTDF[k, load_bus[d]]·d0_d``
  — the same fold-every-fixed-contribution-into-``const_k`` convention ``dc_opf`` uses for fixed
  load and shunts, applied to the zonal quantities. ``_flow_limit_rows`` itself is unchanged: the
  ``Δp+``/``Δd-`` columns go in as injections at the generator/load bus and ``Δp-``/``Δd+`` as
  withdrawals at the same buses, which is exactly the sign each already carries in ``dc_opf``.

**D1's theorem, and why it is a feature rather than a redundancy.** Because the objective is the
true welfare function and the constraints reconstruct nodal's exact feasible set, this LP's
solution *is* the nodal optimum: ``redispatch_dc_opf(arr, ..., p0, d0)`` returns the same final
point as ``dc_opf(arr, ...)`` for **any** feasible ``(p0, d0)``, to solver tolerance (never
bitwise — M5's macOS CI finding, spec assumption A3). Redispatch is therefore not an approximation
of nodal that might land somewhere worse; the thing it measures is the *distance travelled* from
the zonal point to nodal — redispatch volume and the payment that settles it — which is precisely
the cost of the zonal market design (spec `## Design` A5). ``tests/unit/test_opf_redispatch.py``
asserts the theorem from two unrelated starting points on two fixtures, and the paired negative
(an anchored-rate objective substituted in a scratch tree) is AC-4's own.

**Reported deltas are netted.** Under D1 the objective depends on the pair only through
``u = Δ+ − Δ-``, so any ``(Δ+ + α, Δ- + α)`` is exactly as optimal and the split is a solver
choice, not a modelling one. :class:`RedispatchSolution` therefore reports the canonical
representative — ``delta_up = max(u, 0)``, ``delta_down = max(−u, 0)``, computed from the solved
columns — so that ``final == p0 + delta_up − delta_down`` and ``delta_up · delta_down == 0`` hold
exactly, on every platform, whatever vertex HiGHS returns. The raw columns are never surfaced.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass

import highspy
import numpy as np

from mambo_power.numerics.arrays import NetworkArrays
from mambo_power.numerics.bbus import pf_shift
from mambo_power.numerics.ptdf import ptdf as compute_ptdf
from mambo_power.opf.dc_opf import (
    ColArray,
    FloatArray,
    OpfDuals,
    _add_rows,
    _balance_row,
    _epigraph_rows,
    _extract_and_validate,
    _flow_limit_rows,
    _hypograph_rows,
)

_OPTIMAL = "Optimal"

BOUND_TOL_MW = 1e-6
"""Slack allowed when checking ``p0``/``d0`` against their own declared bounds, MW.

A zonal operating point arrives from another solve, so a generator cleared *at* its ``p_max``
routinely lands a few ulp outside it. Rejecting that would make the redispatch stage fail on
exactly the points it exists to fix, so the check tolerates ``BOUND_TOL_MW`` and the derived delta
caps are floored at 0 (``max(p_max − p0, 0)``) rather than allowed to go negative. A point outside
by *more* than this is a real caller error and raises.
"""


@dataclass(frozen=True)
class RedispatchSolution:
    """Result of one :func:`redispatch_dc_opf` solve.

    Modelled on :class:`~mambo_power.opf.dc_opf.OpfSolution` /
    :class:`~mambo_power.opf.multiperiod.MultiperiodSolution`: every array is zero-filled at its
    declared shape when ``status`` is not ``"Optimal"``, and :attr:`duals` is ``None`` exactly
    then.
    """

    status: str
    """HiGHS's own model-status string, passed through verbatim (as ``OpfSolution.status``)."""
    dispatch_mw: FloatArray
    """``(n_gen,)`` **final** per-generator dispatch, MW, ``NetworkArrays`` generator order —
    ``p0 + delta_up_mw − delta_down_mw``, exactly."""
    demand_dispatch_mw: FloatArray
    """``(n_demand,)`` **final** per-elastic-load served demand, MW. Column order is the caller's
    own bid-index set, ``sorted(set(demand_bid_coeffs or {}) | set(demand_pwl_bids or {}))`` —
    identical to :attr:`~mambo_power.opf.dc_opf.OpfSolution.demand_dispatch_mw`'s. Width 0 when no
    bid was supplied."""
    delta_up_mw: FloatArray
    """``(n_gen,)`` upward redispatch, MW, nonnegative. Netted against
    :attr:`delta_down_mw` (module docstring, "Reported deltas are netted"), so at most one of the
    pair is nonzero for any generator."""
    delta_down_mw: FloatArray
    """``(n_gen,)`` downward redispatch, MW, nonnegative."""
    demand_delta_up_mw: FloatArray
    """``(n_demand,)`` demand *restored*, MW, nonnegative — served demand above ``d0``."""
    demand_delta_down_mw: FloatArray
    """``(n_demand,)`` demand *curtailed*, MW, nonnegative — served demand below ``d0``."""
    branch_flow_mw: FloatArray
    """``(n_branch,)`` branch flow at the final point, MW, ``NetworkArrays`` branch order:
    ``PTDF @ (net injection) + phase-shift injection``, the same construction
    :func:`mambo_power.opf.solve_dc_opf` uses for
    :class:`~mambo_power.results.OpfBranchFlowResult`. Present so AC-3's feasibility readback and
    AC-5's settlement identity are both computable from this object alone (M5 carry-over A23);
    all-zero when ``status != "Optimal"``."""
    ptdf: FloatArray
    """The PTDF matrix this solve built for its flow-limit rows, returned for reuse (LMP
    decomposition) exactly as :attr:`~mambo_power.opf.dc_opf.OpfSolution.ptdf` is. Present
    regardless of ``status``."""
    objective_cost: float
    """Total **generation cost** at the final dispatch, $/h — ``Σ (c2·p² + c1·p + c0)`` over
    quadratic generators plus each PWL generator's own epigraph value, including every constant
    term. Identical semantics to :attr:`~mambo_power.opf.dc_opf.OpfSolution.objective_cost`, so
    the two are directly comparable (the wave's ``generation_cost_gap``). 0.0 when ``status !=
    "Optimal"``."""
    demand_value: float
    """Total **bid value** of the final served demand, $/h — ``Σ (v2·d² + v1·d + v0)`` over
    quadratic bids plus each PWL bid's own hypograph value, including every constant term (the
    generator-side mirror of :attr:`objective_cost`, which also carries its ``c0``). 0.0 when
    ``status != "Optimal"`` and 0.0 when there is no elastic demand at all."""
    duals: OpfDuals | None
    """``None`` exactly when ``status != "Optimal"``. See :attr:`OpfDuals.gen_bound` and this
    class's own note: because the redispatch LP's rows are nodal's rows, ``duals.balance`` and
    ``duals.flow_limit`` are the nodal energy price and the nodal congestion duals — the exact
    pair :func:`~mambo_power.opf.dc_opf.lmp_decomposition` takes. ``duals.gen_bound`` is the
    reduced cost of each generator's ``Δp+`` column, which by the chain rule
    ``∂L/∂Δp+ = ∂L/∂p`` is that generator's own ``[p_min, p_max]`` reduced cost at the final
    point."""
    demand_bound: FloatArray
    """``(n_demand,)`` reduced cost of each elastic load's ``Δd+`` column — its own
    ``[d_min, d_max]`` reduced cost at the final point, by the same chain rule as
    ``duals.gen_bound``. Mirrors
    :attr:`~mambo_power.opf.dc_opf.OpfSolution.demand_bound`, which is likewise a field of the
    solution rather than of :class:`~mambo_power.opf.dc_opf.OpfDuals`."""
    message: str | None = None
    """Diagnostic when ``status != "Optimal"``; ``None`` otherwise."""

    @property
    def welfare(self) -> float:
        """``demand_value − objective_cost``, $/h — the quantity D1's objective maximises and the
        one the wave's ``welfare_gap`` compares against nodal's."""
        return self.demand_value - self.objective_cost


def _check_point(
    point: FloatArray,
    lower: FloatArray,
    upper: FloatArray,
    ids: Sequence[str],
    what: str,
    argument: str,
) -> None:
    """Raise :class:`ValueError` naming the first entity whose starting quantity sits outside its
    own declared bounds by more than :data:`BOUND_TOL_MW`."""
    bad = np.flatnonzero((point < lower - BOUND_TOL_MW) | (point > upper + BOUND_TOL_MW))
    if bad.size:
        i = int(bad[0])
        raise ValueError(
            f'{what} "{ids[i]}" has a starting {argument} of {float(point[i])!r} MW, outside its '
            f"own bounds [{float(lower[i])!r}, {float(upper[i])!r}] MW (tolerance "
            f"{BOUND_TOL_MW!r} MW) — a redispatch starting point must be within the box the "
            "final point is allowed to range over"
        )


def _hessian_pairs(
    quadratic: FloatArray,
    up_cols: ColArray,
    down_cols: ColArray,
) -> dict[int, list[tuple[int, float]]]:
    """Lower-triangular Hessian entries for ``Σ_i quadratic_i · (x_up_i − x_down_i)²``, keyed by
    column.

    The objective is ``0.5·xᵀQx``, so a term ``a·u²`` with ``u = x_up − x_down`` contributes
    ``Q_uu = Q_dd = 2a`` and ``Q_ud = Q_du = −2a``; only the lower triangle is stored
    (``HessianFormat.kTriangular``), the off-diagonal entry standing for both. This is the one
    structural difference from :func:`~mambo_power.opf.dc_opf.dc_opf`'s Hessian, whose single
    dispatch column per participant makes it purely diagonal.
    """
    entries: dict[int, list[tuple[int, float]]] = {}
    for i, coefficient in enumerate(quadratic):
        if coefficient == 0.0:
            continue
        up, down = int(up_cols[i]), int(down_cols[i])
        entries.setdefault(up, []).append((up, 2.0 * coefficient))
        entries.setdefault(up, []).append((down, -2.0 * coefficient))
        entries.setdefault(down, []).append((down, 2.0 * coefficient))
    return entries


def redispatch_dc_opf(
    arr: NetworkArrays,
    cost_coeffs: FloatArray,
    p0_mw: FloatArray,
    d0_mw: FloatArray | None = None,
    *,
    pwl_costs: Mapping[int, Sequence[tuple[float, float]]] | None = None,
    demand_bid_coeffs: Mapping[int, tuple[float, float, float]] | None = None,
    demand_pwl_bids: Mapping[int, Sequence[tuple[float, float]]] | None = None,
) -> RedispatchSolution:
    """Minimum-cost redispatch of ``arr`` from the operating point ``(p0_mw, d0_mw)`` onto the
    real network (module docstring).

    ``cost_coeffs``/``pwl_costs``/``demand_bid_coeffs``/``demand_pwl_bids`` are exactly
    :func:`~mambo_power.opf.dc_opf.dc_opf`'s, validated by the one shared
    ``_extract_and_validate`` (ADR-008), and carry the same contracts: a PWL generator's
    ``cost_coeffs`` row is all-zero, a load index may not appear in both bid maps, and ``arr`` is
    passed **unmodified** (the builder removes each bid load's own historical ``p_mw`` from the
    fixed RHS itself).

    ``p0_mw`` is ``(n_gen,)`` in ``NetworkArrays`` generator order. ``d0_mw`` is ``(n_demand,)`` in
    the caller's ascending bid-index order — the order
    :attr:`~mambo_power.opf.dc_opf.OpfSolution.demand_dispatch_mw` comes back in, so a zonal
    solve's own demand output is passed straight through. It may be ``None`` exactly when there is
    no elastic demand.

    Raises :class:`ValueError` for a mis-shaped argument or for a starting quantity outside its own
    generator/load bounds (naming that generator or load, :data:`BOUND_TOL_MW` slack);
    :class:`~mambo_power.opf.dc_opf.NonConvexCostError` /
    :class:`~mambo_power.opf.dc_opf.NonConcaveBidError` up front for a non-convex cost or
    non-concave bid, before any HiGHS object exists. Never raises for an infeasible or unbounded
    model — reported through ``status``/``message``, this package's standing convention.
    """
    n_gen = len(arr.gen_ids)
    n_load = len(arr.load_ids)
    problem = _extract_and_validate(
        cost_coeffs, pwl_costs, demand_bid_coeffs, demand_pwl_bids, n_gen, n_load
    )
    c2, c1, c0 = problem.c2, problem.c1, problem.c0
    v2, v1, v0 = problem.v2, problem.v1, problem.v0
    elastic_load_idxs = problem.elastic_load_idxs
    n_pwl, n_demand, n_demand_pwl = problem.n_pwl, problem.n_demand, problem.n_demand_pwl
    elastic_idx_arr = np.asarray(elastic_load_idxs, dtype=np.int64)
    slot_of_load = {idx: j for j, idx in enumerate(elastic_load_idxs)}

    # --- the starting point, validated against the very bounds the delta caps are derived from.
    p0 = np.asarray(p0_mw, dtype=np.float64)
    if p0.shape != (n_gen,):
        raise ValueError(f"p0_mw must have shape ({n_gen},) (one per generator), got {p0.shape}")
    d0 = np.zeros(n_demand) if d0_mw is None else np.asarray(d0_mw, dtype=np.float64)
    if d0.shape != (n_demand,):
        raise ValueError(
            f"d0_mw must have shape ({n_demand},) (one per elastic load, in ascending bid-index "
            f"order), got {d0.shape}"
        )
    p_min = arr.gen_p_min_pu * arr.base_mva
    p_max = arr.gen_p_max_pu * arr.base_mva
    d_min = arr.load_p_min_pu[elastic_idx_arr] * arr.base_mva
    d_max = arr.load_p_max_pu[elastic_idx_arr] * arr.base_mva
    _check_point(p0, p_min, p_max, arr.gen_ids, "generator", "dispatch p0_mw")
    _check_point(
        d0,
        d_min,
        d_max,
        [arr.load_ids[i] for i in elastic_load_idxs],
        "load",
        "served demand d0_mw",
    )

    # --- tier-1 columns: the four delta families, in this order (the Hessian covers exactly this
    # prefix, and is passed before any tier-2 free column exists — dc_opf's own documented
    # ordering constraint, which multiperiod.py also obeys).
    gen_up_cols = np.arange(0, n_gen, dtype=np.int32)
    gen_down_cols = np.arange(n_gen, 2 * n_gen, dtype=np.int32)
    dem_up_cols = np.arange(2 * n_gen, 2 * n_gen + n_demand, dtype=np.int32)
    dem_down_cols = np.arange(2 * n_gen + n_demand, 2 * n_gen + 2 * n_demand, dtype=np.int32)
    n_delta = 2 * (n_gen + n_demand)

    h = highspy.Highs()  # type: ignore[no-untyped-call]  # highspy ships no type stubs
    h.setOptionValue("output_flag", False)

    # Delta bounds are the generator/load bounds shifted by the starting point, floored at 0
    # against BOUND_TOL_MW-scale noise in (p0, d0). The final quantity therefore ranges over
    # exactly [p_min, p_max] / [d_min, d_max] — the property D1's theorem rests on.
    if n_gen:
        h.addVars(n_gen, np.zeros(n_gen), np.maximum(p_max - p0, 0.0))
        h.addVars(n_gen, np.zeros(n_gen), np.maximum(p0 - p_min, 0.0))
        # linear part of cost_g(p0 + u) = ... + (c1 + 2·c2·p0)·u + c2·u², u = Δ+ − Δ−.
        gen_rate = c1 + 2.0 * c2 * p0
        h.changeColsCost(n_gen, gen_up_cols, gen_rate)
        h.changeColsCost(n_gen, gen_down_cols, -gen_rate)
    if n_demand:
        h.addVars(n_demand, np.zeros(n_demand), np.maximum(d_max - d0, 0.0))
        h.addVars(n_demand, np.zeros(n_demand), np.maximum(d0 - d_min, 0.0))
        # minimising Σcost − Σvalue: the *restore* column carries −mv and the *curtail* column
        # +mv, the delta form of dc_opf's own −v1 demand convention.
        demand_rate = v1 + 2.0 * v2 * d0
        h.changeColsCost(n_demand, dem_up_cols, -demand_rate)
        h.changeColsCost(n_demand, dem_down_cols, demand_rate)

    # --- Hessian over tier 1 only: one 2x2 block per quadratic participant (module docstring).
    if n_delta:
        entries = _hessian_pairs(c2, gen_up_cols, gen_down_cols)
        entries.update(_hessian_pairs(-v2, dem_up_cols, dem_down_cols))
        if entries:
            starts: list[int] = [0]
            indices: list[int] = []
            values: list[float] = []
            for col in range(n_delta):
                for row, value in entries.get(col, []):
                    indices.append(row)
                    values.append(value)
                starts.append(len(indices))
            hess = highspy.HighsHessian()
            hess.dim_ = n_delta
            hess.format_ = highspy.HessianFormat.kTriangular
            hess.start_ = starts
            hess.index_ = indices
            hess.value_ = values
            h.passHessian(hess)

    # --- tier-2 columns: one bounded "final quantity" column q plus one free cost_g/val_d column
    # per *piecewise-linear* participant (module docstring). A quadratic participant has neither.
    next_col = n_delta
    gen_q_col_of: dict[int, int] = {}
    gen_cost_col_of: dict[int, int] = {}
    if n_pwl:
        pwl_idx = np.asarray(problem.pwl_gen_idxs, dtype=np.int64)
        q_cols = np.arange(next_col, next_col + n_pwl, dtype=np.int32)
        h.addVars(n_pwl, p_min[pwl_idx], p_max[pwl_idx])
        gen_q_col_of = dict(zip(problem.pwl_gen_idxs, q_cols.tolist(), strict=True))
        next_col += n_pwl
        cost_cols = np.arange(next_col, next_col + n_pwl, dtype=np.int32)
        h.addVars(n_pwl, np.full(n_pwl, -highspy.kHighsInf), np.full(n_pwl, highspy.kHighsInf))
        h.changeColsCost(n_pwl, cost_cols, np.ones(n_pwl))
        gen_cost_col_of = dict(zip(problem.pwl_gen_idxs, cost_cols.tolist(), strict=True))
        next_col += n_pwl

    dem_q_col_of: dict[int, int] = {}
    dem_val_col_of: dict[int, int] = {}
    if n_demand_pwl:
        # position of each PWL bid load within the ascending elastic-load order (its delta columns)
        pwl_slots = np.asarray([slot_of_load[i] for i in problem.demand_pwl_idxs], dtype=np.int64)
        q_cols = np.arange(next_col, next_col + n_demand_pwl, dtype=np.int32)
        h.addVars(n_demand_pwl, d_min[pwl_slots], d_max[pwl_slots])
        dem_q_col_of = dict(zip(problem.demand_pwl_idxs, q_cols.tolist(), strict=True))
        next_col += n_demand_pwl
        val_cols = np.arange(next_col, next_col + n_demand_pwl, dtype=np.int32)
        h.addVars(
            n_demand_pwl,
            np.full(n_demand_pwl, -highspy.kHighsInf),
            np.full(n_demand_pwl, highspy.kHighsInf),
        )
        h.changeColsCost(n_demand_pwl, val_cols, -np.ones(n_demand_pwl))
        dem_val_col_of = dict(zip(problem.demand_pwl_idxs, val_cols.tolist(), strict=True))
        next_col += n_demand_pwl

    # --- the fixed right-hand side: dc_opf's own total_fixed (every bid load's historical p_mw
    # removed from its bus, the double-counting contract) with the zonal point moved across.
    p_load_mw = arr.p_load_pu * arr.base_mva
    elastic_bus = arr.load_bus[elastic_idx_arr]
    if n_demand:
        elastic_own_mw = arr.load_p_max_pu[elastic_idx_arr] * arr.base_mva
        p_load_mw = p_load_mw - np.bincount(
            elastic_bus, weights=elastic_own_mw, minlength=arr.n_bus
        )
    g_shunt_mw = arr.g_shunt_pu * arr.base_mva
    total_fixed = float(np.sum(p_load_mw) + np.sum(g_shunt_mw))
    balance_rhs = total_fixed - float(np.sum(p0)) + float(np.sum(d0))

    ptdf_matrix = compute_ptdf(arr)
    pf_shift_mw = pf_shift(arr) * arr.base_mva
    const = pf_shift_mw - ptdf_matrix @ (p_load_mw + g_shunt_mw)
    # ...plus the zonal point's own (fixed) contribution to every branch's flow.
    p0_by_bus = np.bincount(arr.gen_bus, weights=p0, minlength=arr.n_bus)
    d0_by_bus = np.bincount(elastic_bus, weights=d0, minlength=arr.n_bus)
    const = const + ptdf_matrix @ (p0_by_bus - d0_by_bus)
    rating_mw = arr.rating_pu * arr.base_mva  # inf where unrated -> row never binds

    # --- rows, in the order their indices are read back below: balance is row 0, the flow-limit
    # rows are 1..n_branch, and everything after them is an internal encoding detail.
    n_rows = 1 + arr.n_branch
    injection_cols = np.concatenate([gen_up_cols, dem_down_cols])
    withdrawal_cols = np.concatenate([gen_down_cols, dem_up_cols])
    injection_bus = np.concatenate([arr.gen_bus, elastic_bus])
    withdrawal_bus = injection_bus

    _add_rows(h, _balance_row(injection_cols, withdrawal_cols, balance_rhs))
    _add_rows(
        h,
        _flow_limit_rows(
            ptdf_matrix,
            injection_cols,
            injection_bus,
            withdrawal_cols,
            withdrawal_bus,
            rating_mw,
            const,
        ),
    )

    # PWL linking equalities: q + Δ− − Δ+ == starting quantity, one per PWL participant, built
    # from _balance_row (module docstring — it is pure algebra over column indices).
    for gen_idx, q_col in gen_q_col_of.items():
        _add_rows(
            h,
            _balance_row(
                np.asarray([q_col, gen_down_cols[gen_idx]], dtype=np.int32),
                np.asarray([gen_up_cols[gen_idx]], dtype=np.int32),
                float(p0[gen_idx]),
            ),
        )
    for load_idx, q_col in dem_q_col_of.items():
        slot = slot_of_load[load_idx]
        _add_rows(
            h,
            _balance_row(
                np.asarray([q_col, dem_down_cols[slot]], dtype=np.int32),
                np.asarray([dem_up_cols[slot]], dtype=np.int32),
                float(d0[slot]),
            ),
        )

    # Epigraph/hypograph rows over the *final* quantity column, verbatim.
    q_col_by_gen = np.zeros(n_gen, dtype=np.int32)
    for gen_idx, q_col in gen_q_col_of.items():
        q_col_by_gen[gen_idx] = q_col
    _add_rows(h, _epigraph_rows(problem.segments_by_gen, q_col_by_gen, gen_cost_col_of))
    _add_rows(h, _hypograph_rows(problem.demand_segments_by_load, dem_q_col_of, dem_val_col_of))

    # The row-order contract is declared in the module docstring, implemented just above, and
    # re-derived here as a hand-maintained sum. Nothing else ties those three together: the duals
    # below are ``row_dual[0]`` and ``row_dual[1:n_rows]``, and three row families of
    # conditionally-present height (the PWL linking equalities, the epigraph and hypograph blocks)
    # are appended *after* the flow rows. A family inserted before them instead shifts every
    # flow-limit dual by exactly its own height, silently. M5's own equivalent assert
    # (opf/multiperiod.py) was measured to be the only guard on its layout; this is the same guard.
    n_linking = len(gen_q_col_of) + len(dem_q_col_of)
    n_epigraph = sum(len(segs) for segs in problem.segments_by_gen.values())
    n_hypograph = sum(len(segs) for segs in problem.demand_segments_by_load.values())
    expected_rows = n_rows + n_linking + n_epigraph + n_hypograph
    assert h.getNumRow() == expected_rows, (
        f"redispatch_dc_opf built {h.getNumRow()} rows, but the row-order contract in this "
        f"module's docstring accounts for {expected_rows} — the balance and flow-limit duals are "
        "read off that contract as row_dual[0] and row_dual[1:n_rows], so they must agree"
    )

    h.run()
    status = h.modelStatusToString(h.getModelStatus())
    if status != _OPTIMAL:
        return RedispatchSolution(
            status=status,
            dispatch_mw=np.zeros(n_gen),
            demand_dispatch_mw=np.zeros(n_demand),
            delta_up_mw=np.zeros(n_gen),
            delta_down_mw=np.zeros(n_gen),
            demand_delta_up_mw=np.zeros(n_demand),
            demand_delta_down_mw=np.zeros(n_demand),
            branch_flow_mw=np.zeros(arr.n_branch),
            ptdf=ptdf_matrix,
            objective_cost=0.0,
            demand_value=0.0,
            duals=None,
            demand_bound=np.zeros(n_demand),
            message=f"redispatch_dc_opf: HiGHS reported model status {status!r}",
        )

    sol = h.getSolution()
    col_value = np.asarray(sol.col_value, dtype=np.float64)
    # Netted deltas (module docstring): the objective sees only Δ+ − Δ−, so the canonical
    # representative is reported rather than whichever split this platform's HiGHS returned.
    gen_net = col_value[gen_up_cols] - col_value[gen_down_cols]
    dem_net = col_value[dem_up_cols] - col_value[dem_down_cols]
    delta_up_mw = np.maximum(gen_net, 0.0)
    delta_down_mw = np.maximum(-gen_net, 0.0)
    demand_delta_up_mw = np.maximum(dem_net, 0.0)
    demand_delta_down_mw = np.maximum(-dem_net, 0.0)
    dispatch_mw = p0 + gen_net
    demand_dispatch_mw = d0 + dem_net

    duals = OpfDuals(
        balance=float(sol.row_dual[0]) if n_rows else 0.0,
        flow_limit=np.asarray(sol.row_dual[1:n_rows], dtype=np.float64),
        gen_bound=np.asarray(sol.col_dual, dtype=np.float64)[gen_up_cols],
    )
    demand_bound = np.asarray(sol.col_dual, dtype=np.float64)[dem_up_cols]

    # True curves at the final point, constants included — the figures OpfSolution reports, so
    # that the wave's cost/welfare gaps compare like with like.
    poly_gen_cost = float(np.sum(c2 * dispatch_mw**2 + c1 * dispatch_mw + c0))
    pwl_gen_cost = float(sum(col_value[gen_cost_col_of[i]] for i in problem.pwl_gen_idxs))
    poly_demand_value = float(np.sum(v2 * demand_dispatch_mw**2 + v1 * demand_dispatch_mw + v0))
    pwl_demand_value = float(sum(col_value[dem_val_col_of[i]] for i in problem.demand_pwl_idxs))

    # Branch flows at the final point — the same construction solve_dc_opf uses (module docstring).
    gen_by_bus = np.bincount(arr.gen_bus, weights=dispatch_mw, minlength=arr.n_bus)
    demand_by_bus = np.bincount(elastic_bus, weights=demand_dispatch_mw, minlength=arr.n_bus)
    injection_mw = gen_by_bus - demand_by_bus - p_load_mw - g_shunt_mw
    branch_flow_mw = ptdf_matrix @ injection_mw + pf_shift_mw

    return RedispatchSolution(
        status=status,
        dispatch_mw=dispatch_mw,
        demand_dispatch_mw=demand_dispatch_mw,
        delta_up_mw=delta_up_mw,
        delta_down_mw=delta_down_mw,
        demand_delta_up_mw=demand_delta_up_mw,
        demand_delta_down_mw=demand_delta_down_mw,
        branch_flow_mw=np.asarray(branch_flow_mw, dtype=np.float64),
        ptdf=ptdf_matrix,
        objective_cost=poly_gen_cost + pwl_gen_cost,
        demand_value=poly_demand_value + pwl_demand_value,
        duals=duals,
        demand_bound=demand_bound,
        message=None,
    )
