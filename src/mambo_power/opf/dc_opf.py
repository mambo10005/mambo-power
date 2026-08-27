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

**Row-family core (M5 W1).** Every row family described here is built by its own internal helper —
:func:`_balance_row`, :func:`_flow_limit_rows`, :func:`_epigraph_rows`, :func:`_hypograph_rows` —
each *returning* a :class:`_RowBlock` (the CSR triple :meth:`highspy.Highs.addRows` takes) rather
than touching a :class:`highspy.Highs` object; :func:`dc_opf` assembles its model by handing those
blocks to :func:`_add_rows`, and is the only thing here that owns a solver object. Two properties
of the helpers are deliberate rather than incidental: each takes the **LP column indices** its
coefficients attach to as parameters instead of assuming :func:`dc_opf`'s own
``[gen | demand | cost_g | val_d]`` layout, and none of them holds or mutates state across calls,
so a family can be built any number of times against any column layout. That is what makes
ADR-007's "one place the balance row is assembled" literally true for a multi-period builder,
which constructs the *same* balance/flow/epigraph/hypograph rows once per period instead of
reproducing the idioms. The extraction is a pure refactor: :func:`dc_opf`'s signature, the LP it
hands HiGHS (structural zeros included) and its results are unchanged (wave M5 AC-1).

**PWL costs (W4, spec design item 4).** A generator with a convex piecewise-linear cost is
passed via ``dc_opf``'s optional ``pwl_costs`` argument — a ``{generator_index:
[(p_mw, cost), ...]}`` mapping (``PiecewiseCost.points``, verbatim) — instead of through
``cost_coeffs`` (that generator's ``cost_coeffs`` row is all-zero: its cost is captured entirely
by the rows built here, reusing the existing "no cost -> all-zero row -> free" convention rather
than adding a second one). The standard convex **segment/epigraph LP encoding** (research §2.1):
for each PWL generator ``g`` with breakpoints ``(p_0,c_0)...(p_n,c_n)``, one new free decision
variable ``cost_g`` is added with objective coefficient ``1`` (so minimising the LP pulls it down
to the tightest bound), plus one inequality row per segment ``i``:
``cost_g >= slope_i * p_g + intercept_i`` where ``slope_i = (c_{i+1}-c_i)/(p_{i+1}-p_i)`` and
``intercept_i = c_i - slope_i * p_i``. Because the segment slopes are non-decreasing (convex —
enforced below), the upper envelope of these lines equals the true piecewise cost exactly on
``[p_0, p_n]``, so at the LP optimum ``cost_g`` is pinned to ``cost(p_g)`` exactly — the standard
epigraph trick; it composes with the QP path above unchanged (a network may mix quadratic and
PWL generators in the same solve — exercised by this wave's own ``case14_pwl.m`` fixture).
**Only valid when the breakpoints span the generator's own ``[p_min, p_max]``** (true of every
PWL generator this wave's own fixture uses); outside that range the epigraph rows extrapolate
along the boundary segments' slopes, which is not necessarily the caller's intent — not checked
here, since no caller in this codebase currently violates it.

A non-convex breakpoint sequence (a decreasing segment slope) is rejected by
:class:`NonConvexCostError`, raised by :func:`dc_opf` itself before any HiGHS object is created
(fail fast, not a wrong-but-optimal-looking LP answer — research §2.1: an LP built from a
non-convex PWL curve silently produces the wrong dispatch, since the encoding above is only valid
for convex costs). This is deliberately an ``opf``-local check, not a retroactive change to
:class:`~mambo_power.model.PiecewiseCost`'s own validation (which checks only strictly-increasing
``p_mw`` — record/m3-research.md §2.3; a carry-over for a later wave, not silently dropped).
:func:`dc_opf` also rejects a quadratic generator cost with ``c2 < 0`` (non-convex) the same way,
closing a gap that predates this wave (M4 research §1.2) — both checks raise
:class:`NonConvexCostError`, the same error family, since they are the same underlying failure
mode (a non-convex cost fed to a convex-cost-only LP/QP encoding).

**Elastic demand (M4 W1, design item 1).** :func:`dc_opf` gains two optional parameters,
``demand_bid_coeffs`` and ``demand_pwl_bids``, both defaulting to ``None`` — every M2/M3 caller is
completely unaffected (the code paths below are additive; with no elastic loads, every new array
has length 0 and the LP is byte-for-byte the pre-M4 one). Both are keyed by **load index** in
``NetworkArrays.load_ids`` order (mirroring how ``pwl_costs`` is keyed by generator index) — a
load index appearing in either mapping becomes an elastic-demand LP column; a load index appearing
in neither stays represented only through the fixed balance/flow-row RHS, exactly as today.
``demand_bid_coeffs`` maps a load index to ``(v2, v1, v0)`` (mirrors ``cost_coeffs``' ``[c2, c1,
c0]`` row, highest order first) for a polynomial (linear/quadratic) marginal-value curve;
``demand_pwl_bids`` maps a load index to ``[(p_mw, value), ...]`` breakpoints (mirrors
``pwl_costs``) for a piecewise-linear one. A load index must not appear in both.

Each elastic load gets one new decision variable, bounded ``[load_p_min_mw, load_p_max_mw]`` (from
``NetworkArrays.load_p_min_pu``/``load_p_max_pu``, W3) — **no sign flip**: unlike the rejected
pseudo-generator trick (research §2.2, Option A), a bid-load's own dispatch is a non-negative
quantity in its own right. The nodal-balance row gains a ``−1``-signed term per elastic-load
column (``Σp_g − Σp_d == fixed_load + shunt``) and each flow-limit row gains a
``−PTDF[k, load_bus[d]]``-signed term, the exact mirror of the ``+PTDF[k, gen_bus[g]]`` generator
term (so ``flow_k = Σ_g PTDF[k,gen_bus]·p_g − Σ_d PTDF[k,load_bus]·p_d + const_k`` — the same
convention M4 research §4.1 hand-derives and this module's own AC-1 test reproduces exactly).

A polynomial bid's marginal value is ``v1 + 2·v2·p``; concavity (non-increasing marginal value)
requires ``v2 <= 0`` — the literal sign mirror of the generator-side ``c2 >= 0`` requirement above.
A piecewise-linear bid's breakpoints must have **non-increasing** segment slopes — the mirror of
the convex epigraph's non-decreasing requirement. Either violation raises
:class:`NonConcaveBidError` before any HiGHS object is created, the demand-side twin of
:class:`NonConvexCostError`. The PWL encoding itself is a **hypograph** (concave "min of
supporting lines"), the sign-mirror of the epigraph above: one free ``val_d`` variable per PWL
bid-load with objective coefficient ``−1`` (so minimising ``Σcost_g − Σval_d`` pulls ``val_d`` up
to its tightest bound), plus one row per segment, ``val_d <= slope_i·p_d + intercept_i``.

**Double-counting contract.** ``NetworkArrays.p_load_pu`` is the *aggregate* fixed load at each
bus, built from every in-service load's own ``p_mw`` regardless of whether it later turns out to
be elastic (W3's own docstring is explicit that this is unconditional). Rather than requiring the
caller to pre-subtract each bid-load's contribution from ``p_load_pu`` before calling ``dc_opf``
(a fragile, easy-to-get-wrong contract, since the caller would need to reconstruct exactly which
per-bus amount to remove), :func:`dc_opf` does this subtraction itself: for every load index
appearing in ``demand_bid_coeffs``/``demand_pwl_bids``, it reads that load's own contribution
directly off ``arr.load_p_max_pu[idx]`` (which W3 built from the identical ``ld.p_mw`` source the
``p_load_pu`` aggregate itself sums — the two are provably in sync, not merely assumed to be) and
removes exactly that amount, at that load's own bus, from the fixed RHS before adding the load's
new LP column. A caller therefore passes ``arr`` **unmodified** — the same ``NetworkArrays`` it
would pass for a plain fixed-load solve — and supplies bid data only for whichever loads are
actually meant to be elastic; :func:`dc_opf` guarantees no double-counting on its own.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from itertools import pairwise

import highspy
import numpy as np
import numpy.typing as npt
from pydantic import BaseModel, ConfigDict, Field

from mambo_power.numerics.arrays import IntArray, NetworkArrays
from mambo_power.numerics.bbus import pf_shift
from mambo_power.numerics.ptdf import ptdf as compute_ptdf

FloatArray = npt.NDArray[np.float64]
ColArray = npt.NDArray[np.int32]
"""LP column index / CSR index array — int32, the width HiGHS's own API takes (:class:`_RowBlock`).
Distinct from :data:`~mambo_power.numerics.arrays.IntArray`, which is the int64 width every
``NetworkArrays`` *bus* index array uses."""

SOLVER = "highspy.Highs"
"""Solver backend name stamped into the result provenance."""

_OPTIMAL = "Optimal"


class OpfDcOptions(BaseModel):
    """Options of the DC-OPF LP/QP solve, plus the Network-level AC-feasibility check (W6).

    No solver-tuning field yet: HiGHS needs none for the problems this wave builds (small dense
    LPs/QPs, always solved to default tolerances) — one is added here, not invented
    speculatively, the first time a caller actually needs to tune something (mirrors the
    guidance behind :class:`~mambo_power.pf.ac_newton.AcOptions`'s much larger option set: every
    field there controls real solver behaviour). ``ac_check`` is read only by
    :func:`mambo_power.opf.solve_dc_opf`; :func:`dc_opf` itself ignores it (see the ``del
    options`` below) since the array-level LP has no notion of a Network to AC-solve.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    ac_check: bool = Field(
        default=False,
        description="Re-run pf.solve_ac on the dispatched network and attach a "
        "results.FeasibilityReport as OpfDcResult.ac_check.",
    )


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
    ptdf: FloatArray
    """The PTDF matrix ``dc_opf`` already built to construct its flow-limit rows (module
    docstring), returned so callers (:func:`mambo_power.opf.solve_dc_opf`) can reuse it instead
    of recomputing — :func:`~mambo_power.numerics.ptdf.ptdf` is ~31% of a warm ``solve_dc_opf``
    call on case300, so computing it twice was ~62% of that call's runtime (review Performance
    FLAG). Present regardless of ``status``: it is built before ``Highs.run()`` and does not
    depend on the solve's outcome."""
    objective_cost: float
    """Total generation cost, $/h — ``Σ (c2·p² + c1·p + c0)`` at the found dispatch, including
    every generator's constant term (HiGHS's own objective value omits it, since a constant
    does not affect the optimum; added back here for a cost figure comparable to an external
    oracle's). 0.0 when ``status != "Optimal"``."""
    duals: OpfDuals | None
    """``None`` exactly when ``status != "Optimal"``."""
    message: str | None = None
    """Diagnostic when ``status != "Optimal"``; ``None`` otherwise."""
    demand_dispatch_mw: FloatArray = field(default_factory=lambda: np.zeros(0))
    """Per-elastic-load dispatch, MW (M4 W1) — never overloads ``dispatch_mw``, which stays
    generator-only. Order: ``sorted(set(demand_bid_coeffs or {}) | set(demand_pwl_bids or {}))``,
    i.e. the caller's own bid-index set (into ``NetworkArrays.load_ids``), ascending — the caller
    already has this set (it built the bid mappings), so no extra id list is threaded through
    here, mirroring how ``dispatch_mw`` itself relies on the caller already knowing
    ``arr.gen_ids``. Length 0 (not all-zero at generator length) when no bid was supplied for any
    load — including when ``status != "Optimal"``."""
    demand_bound: FloatArray = field(default_factory=lambda: np.zeros(0))
    """Per-elastic-load reduced cost of its ``[load_p_min_mw, load_p_max_mw]`` bound, same order
    as :attr:`demand_dispatch_mw`; 0 unless that load is pinned at a bound."""


@dataclass(frozen=True)
class LmpBreakdown:
    """Per-bus locational marginal price, decomposed into its energy and congestion terms."""

    lmp: FloatArray
    """``energy + congestion``, bus order."""
    energy: FloatArray
    """The balance dual, broadcast to every bus (uniform system-wide energy price)."""
    congestion: FloatArray
    """``flow_limit_duals @ ptdf``: each bus's exposure to every binding flow-limit row."""


class NonConvexCostError(ValueError):
    """A generator cost is non-convex: either a :class:`~mambo_power.model.PiecewiseCost`'s
    breakpoint slopes are not non-decreasing, or a quadratic cost has ``c2 < 0``.

    Raised by :func:`dc_opf` before any HiGHS object is created (module docstring, "PWL costs" /
    "Elastic demand"): the convex segment/epigraph LP encoding, and the QP Hessian's positive
    semi-definiteness, are only valid for a convex cost, and silently solving a non-convex one
    would give a wrong-but-optimal-looking dispatch rather than fail loudly (research §2.1, §1.2).
    ``opf``-local — :class:`~mambo_power.model.PiecewiseCost` itself validates only
    strictly-increasing ``p_mw``, not convexity (record/m3-research.md §2.3).
    """


class NonConcaveBidError(ValueError):
    """A demand bid is non-concave: either a piecewise-linear bid's breakpoint slopes are not
    non-increasing, or a quadratic (polynomial) bid has ``v2 > 0``.

    The demand-side mirror of :class:`NonConvexCostError` (module docstring, "Elastic demand"),
    raised by :func:`dc_opf` before any HiGHS object is created: the concave segment/hypograph LP
    encoding, and the QP Hessian's positive semi-definiteness (built from ``−v2``), are only valid
    for a concave value curve — silently solving a non-concave one would give a
    wrong-but-optimal-looking dispatch rather than fail loudly (research §1.1, §1.2).
    """


def _convex_pwl_segments(points: Sequence[tuple[float, float]]) -> list[tuple[float, float]]:
    """``(slope, intercept)`` per segment of a convex PWL cost's breakpoints, for the epigraph
    encoding (module docstring): ``cost >= slope * p + intercept`` on each segment.

    Raises :class:`NonConvexCostError` if any segment's slope is less than the previous segment's
    (a decreasing marginal cost) — the one check this encoding depends on, done once, up front.
    """
    segments: list[tuple[float, float]] = []
    prev_slope: float | None = None
    for (p0, c0), (p1, c1) in pairwise(points):
        slope = (c1 - c0) / (p1 - p0)
        if prev_slope is not None and slope < prev_slope:
            raise NonConvexCostError(
                f"non-convex piecewise-linear cost: segment slope {slope!r} following breakpoint "
                f"({p0!r}, {c0!r}) is less than the previous segment's slope {prev_slope!r} — "
                "breakpoints must have non-decreasing marginal cost for the convex "
                "segment/epigraph LP encoding to be valid (module docstring)"
            )
        segments.append((slope, c0 - slope * p0))
        prev_slope = slope
    return segments


def _concave_pwl_segments(points: Sequence[tuple[float, float]]) -> list[tuple[float, float]]:
    """``(slope, intercept)`` per segment of a concave PWL demand bid's breakpoints, for the
    hypograph encoding (module docstring, "Elastic demand"): ``val <= slope * p + intercept`` on
    each segment — the mirror image of :func:`_convex_pwl_segments`.

    Raises :class:`NonConcaveBidError` if any segment's slope is greater than the previous
    segment's (an increasing marginal value).
    """
    segments: list[tuple[float, float]] = []
    prev_slope: float | None = None
    for (p0, v0), (p1, v1) in pairwise(points):
        slope = (v1 - v0) / (p1 - p0)
        if prev_slope is not None and slope > prev_slope:
            raise NonConcaveBidError(
                f"non-concave piecewise-linear demand bid: segment slope {slope!r} following "
                f"breakpoint ({p0!r}, {v0!r}) is greater than the previous segment's slope "
                f"{prev_slope!r} — breakpoints must have non-increasing marginal value for the "
                "concave segment/hypograph LP encoding to be valid (module docstring)"
            )
        segments.append((slope, v0 - slope * p0))
        prev_slope = slope
    return segments


@dataclass(frozen=True)
class _RowBlock:
    """One family of LP rows, in exactly the CSR form :meth:`highspy.Highs.addRows` takes.

    ``starts`` has ``n_rows + 1`` entries (the trailing one being the total nonzero count), so a
    block is self-describing: families are built independently and added in whatever order the
    caller wants its rows numbered in.
    """

    lower: FloatArray
    """Row lower bounds, one per row."""
    upper: FloatArray
    """Row upper bounds, one per row (equal to :attr:`lower` for an equality row)."""
    starts: ColArray
    """CSR row starts, ``n_rows + 1`` entries."""
    indices: ColArray
    """Column index of each nonzero, row-major."""
    values: FloatArray
    """Coefficient of each nonzero, row-major, aligned with :attr:`indices`."""

    @property
    def n_rows(self) -> int:
        """Number of rows in this block."""
        return int(self.lower.size)


def _add_rows(h: highspy.Highs, block: _RowBlock) -> None:
    """Append ``block``'s rows to ``h`` — the only place a row family meets the solver object.

    A block with no rows is a no-op: a family can legitimately be empty (a network with no
    branches, a solve with no piecewise-linear generator), and HiGHS is never asked to add zero
    rows, exactly as before the families were extracted.
    """
    if not block.n_rows:
        return
    h.addRows(
        block.n_rows,
        block.lower,
        block.upper,
        block.indices.size,
        block.starts,
        block.indices,
        block.values,
    )


def _dense_csr(dense: FloatArray, cols: ColArray) -> tuple[ColArray, ColArray, FloatArray]:
    """CSR triple for a *dense* row block: every row carries an entry in every column of ``cols``,
    structural zeros included — the exact coefficient pattern this module has always handed HiGHS,
    preserved so that no degenerate-vertex choice (and hence no dual) can shift underneath the
    extraction.
    """
    n_rows, n_cols = dense.shape
    if not n_cols:
        return (
            np.zeros(n_rows + 1, dtype=np.int32),
            np.zeros(0, dtype=np.int32),
            np.zeros(0),
        )
    starts = np.arange(0, n_cols * n_rows + 1, n_cols, dtype=np.int32)
    return starts, np.tile(cols, n_rows), np.asarray(dense.ravel(), dtype=np.float64)


def _balance_row(
    injection_cols: ColArray,
    withdrawal_cols: ColArray,
    fixed_mw: float,
) -> _RowBlock:
    """The system-wide nodal-balance equality row (module docstring): ``Σ x_inject − Σ x_withdraw
    == fixed_mw``, coefficient ``+1`` on every injection column and ``−1`` on every withdrawal one.

    Both arguments are **LP column indices**, not generator/load indices: the row is pure algebra
    and does not care what a column represents, only which side of the balance it sits on.
    :func:`dc_opf` passes its generator columns as injections and its elastic-load columns as
    withdrawals. ``fixed_mw`` is the caller's — it is what varies when the fixed load does — and is
    the right-hand side of both bounds, the row being an equality.
    """
    dense = np.hstack([np.ones((1, injection_cols.size)), -np.ones((1, withdrawal_cols.size))])
    starts, indices, values = _dense_csr(dense, np.concatenate([injection_cols, withdrawal_cols]))
    return _RowBlock(
        lower=np.full(1, fixed_mw),
        upper=np.full(1, fixed_mw),
        starts=starts,
        indices=indices,
        values=values,
    )


def _flow_limit_rows(
    ptdf: FloatArray,
    injection_cols: ColArray,
    injection_bus: IntArray,
    withdrawal_cols: ColArray,
    withdrawal_bus: IntArray,
    rating_mw: FloatArray,
    const_mw: FloatArray,
) -> _RowBlock:
    """One PTDF-based flow-limit row per branch (module docstring): ``−rating_k − const_k <=
    Σ_i PTDF[k, injection_bus[i]]·x_i − Σ_j PTDF[k, withdrawal_bus[j]]·x_j <= rating_k − const_k``.

    ``injection_bus``/``withdrawal_bus`` give the bus each of those columns injects at or withdraws
    from, aligned with ``injection_cols``/``withdrawal_cols``. ``const_mw`` folds in every *fixed*
    contribution to each branch's flow and is the caller's to compute (it is what varies when the
    fixed load does); the ``±rating − const`` bound convention is this row family's own and lives
    here. An unrated branch (``rating == inf``) gets an unconstrained row, which never binds.
    """
    n_branch = ptdf.shape[0]
    injections = ptdf[:, injection_bus] if injection_cols.size else np.zeros((n_branch, 0))
    withdrawals = -ptdf[:, withdrawal_bus] if withdrawal_cols.size else np.zeros((n_branch, 0))
    starts, indices, values = _dense_csr(
        np.hstack([injections, withdrawals]),
        np.concatenate([injection_cols, withdrawal_cols]),
    )
    return _RowBlock(
        lower=-rating_mw - const_mw,
        upper=rating_mw - const_mw,
        starts=starts,
        indices=indices,
        values=values,
    )


def _epigraph_rows(
    segments_by_gen: Mapping[int, Sequence[tuple[float, float]]],
    gen_cols: ColArray,
    cost_col_of: Mapping[int, int],
) -> _RowBlock:
    """Convex-PWL generator cost rows (module docstring, "PWL costs"): one row per segment,
    ``cost_g − slope_i·p_g >= intercept_i``.

    ``segments_by_gen`` maps a generator index to that generator's ``(slope, intercept)`` segments
    (:func:`_convex_pwl_segments`, which has already rejected a non-convex curve); ``gen_cols[g]``
    is generator ``g``'s dispatch column and ``cost_col_of[g]`` its free ``cost_g`` column. Rows
    come out in ascending generator index.
    """
    lower: list[float] = []
    indices: list[int] = []
    values: list[float] = []
    starts = [0]
    for gen_idx in sorted(segments_by_gen):
        p_col, cost_col = int(gen_cols[gen_idx]), cost_col_of[gen_idx]
        for slope, intercept in segments_by_gen[gen_idx]:
            lower.append(intercept)
            indices.extend([p_col, cost_col])
            values.extend([-slope, 1.0])
            starts.append(len(indices))
    return _RowBlock(
        lower=np.asarray(lower, dtype=np.float64),
        upper=np.full(len(lower), highspy.kHighsInf),
        starts=np.asarray(starts, dtype=np.int32),
        indices=np.asarray(indices, dtype=np.int32),
        values=np.asarray(values, dtype=np.float64),
    )


def _hypograph_rows(
    segments_by_load: Mapping[int, Sequence[tuple[float, float]]],
    demand_col_of: Mapping[int, int],
    val_col_of: Mapping[int, int],
) -> _RowBlock:
    """Concave-PWL demand-bid rows (module docstring, "Elastic demand"): one row per segment,
    ``val_d − slope_i·p_d <= intercept_i`` — the sign mirror of :func:`_epigraph_rows`, kept a
    separate function for the same reason :func:`_concave_pwl_segments` is separate from
    :func:`_convex_pwl_segments`: each side reads as its own derivation rather than as a flag.

    ``segments_by_load`` maps a load index to that bid's ``(slope, intercept)`` segments
    (:func:`_concave_pwl_segments`); ``demand_col_of[d]`` is load ``d``'s dispatch column and
    ``val_col_of[d]`` its free ``val_d`` column. Rows come out in ascending load index.
    """
    upper: list[float] = []
    indices: list[int] = []
    values: list[float] = []
    starts = [0]
    for load_idx in sorted(segments_by_load):
        p_col, val_col = demand_col_of[load_idx], val_col_of[load_idx]
        for slope, intercept in segments_by_load[load_idx]:
            upper.append(intercept)
            indices.extend([p_col, val_col])
            values.extend([-slope, 1.0])
            starts.append(len(indices))
    return _RowBlock(
        lower=np.full(len(upper), -highspy.kHighsInf),
        upper=np.asarray(upper, dtype=np.float64),
        starts=np.asarray(starts, dtype=np.int32),
        indices=np.asarray(indices, dtype=np.int32),
        values=np.asarray(values, dtype=np.float64),
    )


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


def dc_opf(
    arr: NetworkArrays,
    cost_coeffs: FloatArray,
    options: OpfDcOptions,
    pwl_costs: Mapping[int, Sequence[tuple[float, float]]] | None = None,
    demand_bid_coeffs: Mapping[int, tuple[float, float, float]] | None = None,
    demand_pwl_bids: Mapping[int, Sequence[tuple[float, float]]] | None = None,
) -> OpfSolution:
    """Solve the DC-OPF/welfare LP/QP of ``arr`` (module docstring): minimise Σ cost(p_g) −
    Σ value(p_d) subject to one system-wide nodal-balance row and one PTDF-based flow-limit row
    per branch, over generator and elastic-load bounds. ``cost_coeffs`` is ``(n_gen, 3)``, columns
    ``[c2, c1, c0]``, generator order. ``pwl_costs`` (module docstring, "PWL costs") is an
    optional ``{generator_index: points}`` map for any generator whose cost is convex
    piecewise-linear instead of polynomial — that generator's own ``cost_coeffs`` row should be
    all-zero. ``demand_bid_coeffs``/``demand_pwl_bids`` (module docstring, "Elastic demand") are
    optional ``{load_index: ...}`` maps, both defaulting to ``None`` (no elastic demand — every
    M2/M3 caller's exact behavior); a load index must not appear in both. Raises
    :class:`NonConvexCostError` up front (before any HiGHS object exists) for a non-convex
    generator cost (piecewise-linear or ``c2 < 0`` quadratic), and :class:`NonConcaveBidError` for
    a non-concave demand bid (piecewise-linear or ``v2 > 0`` quadratic). Never raises for an
    infeasible or unbounded model — reported through ``status``/``message``.
    """
    del options  # no tunable fields yet (OpfDcOptions docstring)
    n_gen = len(arr.gen_ids)
    n_load = len(arr.load_ids)
    coeffs = np.asarray(cost_coeffs, dtype=np.float64)
    if coeffs.shape != (n_gen, 3):
        raise ValueError(
            f"cost_coeffs must have shape ({n_gen}, 3) ([c2, c1, c0] per generator), "
            f"got {coeffs.shape}"
        )
    c2, c1, c0 = coeffs[:, 0], coeffs[:, 1], coeffs[:, 2]

    # PWL segments are validated (convexity/concavity) before anything else is built — fail
    # fast, per NonConvexCostError's/NonConcaveBidError's own docstrings.
    pwl_costs_ = pwl_costs or {}
    pwl_gen_idxs = sorted(pwl_costs_)
    segments_by_gen = {i: _convex_pwl_segments(pwl_costs_[i]) for i in pwl_gen_idxs}
    n_pwl = len(pwl_gen_idxs)

    demand_bid_coeffs_ = demand_bid_coeffs or {}
    demand_pwl_bids_ = demand_pwl_bids or {}
    overlap = set(demand_bid_coeffs_) & set(demand_pwl_bids_)
    if overlap:
        raise ValueError(
            f"load index(es) {sorted(overlap)} appear in both demand_bid_coeffs and "
            "demand_pwl_bids — a load's bid must be either polynomial or piecewise-linear, "
            "not both"
        )
    elastic_load_idxs = sorted(set(demand_bid_coeffs_) | set(demand_pwl_bids_))
    for idx in elastic_load_idxs:
        if not (0 <= idx < n_load):
            raise ValueError(
                f"demand bid load index {idx} out of range for {n_load} loads "
                "(NetworkArrays.load_ids)"
            )
    n_demand = len(elastic_load_idxs)
    demand_col_of = {idx: n_gen + j for j, idx in enumerate(elastic_load_idxs)}
    demand_pwl_idxs = sorted(demand_pwl_bids_)
    demand_segments_by_load = {
        i: _concave_pwl_segments(demand_pwl_bids_[i]) for i in demand_pwl_idxs
    }
    n_demand_pwl = len(demand_pwl_idxs)

    # polynomial demand-bid coefficients, dense over elastic_load_idxs order (PWL bid-loads get an
    # all-zero row here — their value is captured entirely by the hypograph rows below, mirroring
    # how a PWL generator's cost_coeffs row is all-zero).
    v2 = np.zeros(n_demand)
    v1 = np.zeros(n_demand)
    v0 = np.zeros(n_demand)
    for j, idx in enumerate(elastic_load_idxs):
        if idx in demand_bid_coeffs_:
            v2[j], v1[j], v0[j] = demand_bid_coeffs_[idx]

    # convexity/concavity guards on the polynomial coefficients (module docstring): generator
    # c2 >= 0, demand v2 <= 0 — the sign mirror.
    neg_c2 = np.flatnonzero(c2 < 0)
    if neg_c2.size:
        bad = int(neg_c2[0])
        raise NonConvexCostError(
            f"non-convex quadratic generator cost: generator index {bad} has c2={c2[bad]!r} < 0 "
            "— a quadratic cost must have c2 >= 0 for the QP's Hessian to be convex "
            "(module docstring, generator-side convexity guard)"
        )
    pos_v2 = np.flatnonzero(v2 > 0)
    if pos_v2.size:
        bad = int(pos_v2[0])
        bad_idx = elastic_load_idxs[bad]
        raise NonConcaveBidError(
            f"non-concave quadratic demand bid: load index {bad_idx} has v2={v2[bad]!r} > 0 — "
            "a quadratic value curve must have v2 <= 0 for the welfare QP's Hessian to stay "
            "convex (module docstring, mirror of the generator-side c2 >= 0 guard)"
        )

    h = highspy.Highs()  # type: ignore[no-untyped-call]  # highspy ships no type stubs
    h.setOptionValue("output_flag", False)

    p_min = arr.gen_p_min_pu * arr.base_mva
    p_max = arr.gen_p_max_pu * arr.base_mva
    if n_gen:
        h.addVars(n_gen, p_min, p_max)
        h.changeColsCost(n_gen, np.arange(n_gen, dtype=np.int32), c1)

    elastic_idx_arr = np.asarray(elastic_load_idxs, dtype=np.int64)
    if n_demand:
        demand_p_min = arr.load_p_min_pu[elastic_idx_arr] * arr.base_mva
        demand_p_max = arr.load_p_max_pu[elastic_idx_arr] * arr.base_mva
        h.addVars(n_demand, demand_p_min, demand_p_max)
        # minimising Σcost_g − Σvalue_d means the demand column's linear objective coefficient is
        # −v1 (module docstring, "Elastic demand").
        h.changeColsCost(n_demand, np.arange(n_gen, n_gen + n_demand, dtype=np.int32), -v1)

    # combined Hessian over both dispatch blocks (generator [0, n_gen), demand [n_gen,
    # n_dispatch)), built and passed once, before any free-var (PWL cost_g/val_d) column is
    # appended — the same ordering already proven safe against later addVars calls by the
    # existing case14_pwl fixture test (quadratic + PWL generators mixed in one solve).
    n_dispatch = n_gen + n_demand
    if n_dispatch:
        hess_diag = np.zeros(n_dispatch)
        hess_diag[:n_gen] = 2.0 * c2
        hess_diag[n_gen:] = -2.0 * v2
        nz = np.flatnonzero(hess_diag)
        if nz.size:
            hess = highspy.HighsHessian()
            hess.dim_ = n_dispatch
            hess.format_ = highspy.HessianFormat.kTriangular
            starts = np.zeros(n_dispatch + 1, dtype=np.int32)
            starts[nz + 1] = 1
            starts = np.cumsum(starts).astype(np.int32)
            hess.start_ = starts.tolist()
            hess.index_ = nz.tolist()
            hess.value_ = hess_diag[nz].tolist()
            h.passHessian(hess)

    # PWL cost columns: one free "cost_g" variable per PWL generator, appended after the
    # n_dispatch generator+demand columns (module docstring, "PWL costs"). Objective coefficient
    # 1 — minimising the LP pulls each cost_g down to the tightest epigraph bound, i.e. exactly
    # cost(p_g).
    cost_col_of: dict[int, int] = {}
    if n_pwl:
        cost_cols = np.arange(n_dispatch, n_dispatch + n_pwl, dtype=np.int32)
        h.addVars(n_pwl, np.full(n_pwl, -highspy.kHighsInf), np.full(n_pwl, highspy.kHighsInf))
        h.changeColsCost(n_pwl, cost_cols, np.ones(n_pwl))
        cost_col_of = dict(zip(pwl_gen_idxs, cost_cols.tolist(), strict=True))

    # PWL demand columns: one free "val_d" variable per PWL bid-load, appended after the PWL cost
    # columns (module docstring, "Elastic demand"). Objective coefficient −1 — minimising
    # −Σval_d pulls each val_d up to the tightest hypograph bound, i.e. exactly value(p_d).
    demand_val_col_of: dict[int, int] = {}
    if n_demand_pwl:
        val_cols = np.arange(n_dispatch + n_pwl, n_dispatch + n_pwl + n_demand_pwl, dtype=np.int32)
        h.addVars(
            n_demand_pwl,
            np.full(n_demand_pwl, -highspy.kHighsInf),
            np.full(n_demand_pwl, highspy.kHighsInf),
        )
        h.changeColsCost(n_demand_pwl, val_cols, -np.ones(n_demand_pwl))
        demand_val_col_of = dict(zip(demand_pwl_idxs, val_cols.tolist(), strict=True))

    # --- nodal balance: Σ p_g − Σ p_d == Σ p_load_fixed + Σ g_shunt (module docstring; phase
    # shifts cancel system-wide because Σ_bus p_shift == Σ_branch (pf_shift_k − pf_shift_k) == 0
    # identically). p_load_fixed excludes every elastic load's own contribution (double-counting
    # contract, module docstring, "Elastic demand") — each elastic load's own historical p_mw
    # (== arr.load_p_max_pu at its index, by construction, W3) is removed from the bus it sits on
    # before the fixed aggregate is used anywhere below.
    p_load_mw = arr.p_load_pu * arr.base_mva
    if n_demand:
        elastic_bus = arr.load_bus[elastic_idx_arr]
        elastic_own_mw = arr.load_p_max_pu[elastic_idx_arr] * arr.base_mva
        p_load_mw = p_load_mw - np.bincount(
            elastic_bus, weights=elastic_own_mw, minlength=arr.n_bus
        )
    g_shunt_mw = arr.g_shunt_pu * arr.base_mva
    total_fixed = float(np.sum(p_load_mw) + np.sum(g_shunt_mw))

    # --- flow-limit rows: flow_k = Σ_g PTDF[k, gen_bus[g]]·p_g − Σ_d PTDF[k, load_bus[d]]·p_d +
    # const_k, where const_k = pf_shift_mw_k − Σ_bus PTDF[k, bus]·(p_load_fixed_mw[bus] +
    # g_shunt_mw[bus]) folds in every *fixed* contribution to branch k's flow (derivation: module
    # docstring above). Row bounds: −rating_k − const_k <= row_expr_k <= rating_k − const_k.
    ptdf_matrix = compute_ptdf(arr)
    pf_shift_mw = pf_shift(arr) * arr.base_mva
    fixed_bus_mw = p_load_mw + g_shunt_mw
    const = pf_shift_mw - ptdf_matrix @ fixed_bus_mw
    rating_mw = arr.rating_pu * arr.base_mva  # inf where unrated -> row never binds

    # Each row family is built by its own helper (module docstring, "Row-family core") against
    # explicit column indices, and appended in the order their row indices are read back below:
    # the balance row is row 0, the flow-limit rows are 1..n_branch.
    n_rows = 1 + arr.n_branch
    gen_cols = np.arange(n_gen, dtype=np.int32)
    demand_cols = np.arange(n_gen, n_dispatch, dtype=np.int32)

    _add_rows(h, _balance_row(gen_cols, demand_cols, total_fixed))
    _add_rows(
        h,
        _flow_limit_rows(
            ptdf_matrix,
            gen_cols,
            arr.gen_bus,
            demand_cols,
            arr.load_bus[elastic_idx_arr],
            rating_mw,
            const,
        ),
    )

    # PWL epigraph / hypograph rows, appended after the balance and flow-limit rows so those
    # rows' indices (0 and 1..n_branch, read below) are unaffected.
    _add_rows(h, _epigraph_rows(segments_by_gen, gen_cols, cost_col_of))
    _add_rows(h, _hypograph_rows(demand_segments_by_load, demand_col_of, demand_val_col_of))

    h.run()
    status = h.modelStatusToString(h.getModelStatus())
    if status != _OPTIMAL:
        return OpfSolution(
            status=status,
            dispatch_mw=np.zeros(n_gen),
            ptdf=ptdf_matrix,
            objective_cost=0.0,
            duals=None,
            message=f"dc_opf: HiGHS reported model status {status!r}",
            demand_dispatch_mw=np.zeros(n_demand),
            demand_bound=np.zeros(n_demand),
        )

    sol = h.getSolution()
    # only the first n_dispatch columns/rows are the generator+demand dispatch / balance+flow-
    # limit rows this wave's callers know about — PWL cost_g/val_d columns and epigraph/hypograph
    # rows (if any) are appended after them and are an internal encoding detail, not part of
    # OpfSolution/OpfDuals's shape.
    dispatch_mw = np.asarray(sol.col_value[:n_gen], dtype=np.float64)
    demand_dispatch_mw = np.asarray(sol.col_value[n_gen:n_dispatch], dtype=np.float64)
    duals = OpfDuals(
        balance=float(sol.row_dual[0]) if n_rows else 0.0,
        flow_limit=np.asarray(sol.row_dual[1:n_rows], dtype=np.float64),
        gen_bound=np.asarray(sol.col_dual[:n_gen], dtype=np.float64),
    )
    demand_bound = np.asarray(sol.col_dual[n_gen:n_dispatch], dtype=np.float64)

    # objective_cost stays "total generation cost only" (unchanged M2/M3 semantics, docstring on
    # OpfSolution.objective_cost) even with elastic demand in the same solve — computed directly
    # from generator dispatch + PWL cost_g values rather than HiGHS's own combined objective
    # (which, with demand columns present, also nets in the negated demand value). Algebraically
    # identical to the pre-M4 formula (`objective_function_value + Σc0`) whenever n_demand == 0.
    poly_gen_cost = float(np.sum(c2 * dispatch_mw**2 + c1 * dispatch_mw + c0))
    pwl_gen_cost = float(sum(sol.col_value[cost_col_of[i]] for i in pwl_gen_idxs))
    objective_cost = poly_gen_cost + pwl_gen_cost
    return OpfSolution(
        status=status,
        dispatch_mw=dispatch_mw,
        ptdf=ptdf_matrix,
        objective_cost=objective_cost,
        duals=duals,
        message=None,
        demand_dispatch_mw=demand_dispatch_mw,
        demand_bound=demand_bound,
    )
