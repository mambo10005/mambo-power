"""Multiperiod DC-OPF LP/QP builder over HiGHS (wave M5 W2; AC-2, AC-3).

Array-level entry point: :func:`multiperiod_dc_opf` solves ``T`` **coupled** periods in one LP/QP.
It is the direct sibling of :func:`mambo_power.opf.dc_opf.dc_opf`, at the same altitude (pure
numerics over :class:`~mambo_power.numerics.NetworkArrays`, no ``Network``/``Scenario``
dependency, ADR-006's array-level seam); the ``Scenario``-facing wrapper is
``mambo_power.market.multiperiod.solve_multiperiod``.

**One builder, not two.** ADR-007 binds multiperiod to the *same* row-family core, and M5's W1
extraction is what makes that literally true: the per-period nodal-balance row, PTDF flow-limit
rows and PWL epigraph/hypograph rows here are built by ``dc_opf``'s own
:func:`~mambo_power.opf.dc_opf._balance_row` / :func:`~mambo_power.opf.dc_opf._flow_limit_rows` /
:func:`~mambo_power.opf.dc_opf._epigraph_rows` / :func:`~mambo_power.opf.dc_opf._hypograph_rows`,
called once per period against that period's own column indices. Nothing in those four families
is reimplemented here. What *is* new is the three coupling families below, which are exactly the
families a single-period solve cannot have.

**Column layout — two tiers, not one block per period.** ``record/m5-research.md`` §2.2 describes
the variable vector as ``T`` per-period blocks concatenated, each block ending in that period's
PWL free variables. That does not survive contact with ``dc_opf``'s documented Hessian-ordering
constraint: the quadratic cost Hessian is passed once, over a *prefix* of the columns, before any
free ``cost_g``/``val_d`` column exists. So the free variables are hoisted into a second tier:

* **tier 1** (``T * (n_gen + n_demand + 3*n_storage)`` columns), period-major, each period's block
  being ``[gen | demand | charge | discharge | soc]``. The Hessian covers exactly this tier.
* **tier 2** (``T * (n_pwl + n_demand_pwl)`` columns), period-major, each period's block being
  ``[cost_g | val_d]``.

At ``T == 1`` with no storage this is column-for-column, row-for-row and call-for-call the model
``dc_opf`` itself builds, which is what makes the degenerate case *exact* rather than merely close
(wave AC-4).

**Storage columns (tactical default T2).** Two nonnegative columns per unit per period —
``charge`` and ``discharge``, each bounded ``[0, p_max_mw]`` — plus an explicit ``soc`` column
bounded ``[0, energy_mwh]``, rather than one signed power column: the charge and discharge
efficiencies enter the SoC row with *different* coefficients (``+eta_c`` against ``-1/eta_d``), an
asymmetry a single signed column cannot express in one linear row (research §3.1). Simultaneous
charge and discharge is therefore representable, and deliberately so: research §3.2 constructs a
network where forbidding it makes the LP **infeasible**, so this formulation *bounds* the overlap
with a shared ``charge + discharge <= p_max_mw`` row rather than banning it with a binary. The
"does it actually happen on our own data" question is settled by a committed invariant test, not
by assumption (AC-3), and that test is paired with the constructed network where it *must* happen,
so the near-zero reading is a real measurement rather than an absence.

**Row families and their order.** Row indices are read back for duals, so the order is a contract,
stated here and depended on nowhere else:

===== ======================================== ==================================================
tier  family                                    row index
===== ======================================== ==================================================
1     nodal balance, one per period             ``t``
2     PTDF flow limit, per branch per period    ``T + t*n_branch + k``
3     SoC balance, per unit per period          ``T*(1 + n_branch) + t*n_storage + s``
4     ``charge + discharge <= p_max``           after tier 3, ``t*n_storage + s``
5     cyclic ``soc[T-1] == soc_initial``        after tier 4, ``s``
6     ramp coupling, per ramped gen per pair    after tier 5, ``(t-1)*n_ramped + j``
7     PWL epigraph rows, per period             after tier 6 — internal encoding detail
8     PWL hypograph rows, per period            last — internal encoding detail
===== ======================================== ==================================================

This is **this module's own** contract, not one inherited from ``dc_opf``: ``dc_opf`` gets balance
at row 0 and flows at ``1..n_branch`` because it adds them first, and the same reasoning is
re-derived here for ``T`` periods rather than assumed to carry over. Tiers 7-8 stay last for the
same reason they do in ``dc_opf`` — they are an encoding detail of the PWL cost curves and are
never part of :class:`MultiperiodDuals`' shape.

**Coupling row families.**

* **Ramp coupling** — one *two-sided* row per ramp-limited generator per adjacent period pair
  ``t = 1..T-1``: ``-ramp_down_mw[g] <= p_g[t] - p_g[t-1] <= ramp_up_mw[g]``. A generator with
  neither limit set gets **no row at all** (not a row with a large finite bound), and one with
  only one of the two set gets a genuinely unbounded side (``±highspy.kHighsInf``). A ramp limit
  of exactly ``0`` is rejected: it would mean "frozen for the whole horizon", which is MATPOWER's
  unpopulated-ramp-column trap rather than anything a caller means (research §4.2).
* **SoC balance** — one equality row per unit per period.  At ``t = 0`` it anchors to the unit's
  own initial energy, ``soc[0] - eta_c*charge[0] + discharge[0]/eta_d == soc_initial*energy_mwh``;
  for ``t >= 1`` it couples adjacent periods,
  ``soc[t] - soc[t-1] - eta_c*charge[t] + discharge[t]/eta_d == 0``.
* **Cyclic end of horizon** — ``soc[T-1] == soc_initial*energy_mwh``, one equality row per unit.
  Not configurable: M5's scope answer 2 is "cyclic", and a free or fixed-target end state would be
  a third code path this wave deliberately does not ship.

**Period-varying data.** Only the *load* varies by period (``period_load_mw``), matching
:class:`~mambo_power.model.Period`, which carries a per-load override and nothing else. That one
array moves two things, because ``Load.p_mw`` means two things: a fixed load's whole demand, and
an elastic load's *maximum served quantity* (M4's elastic-demand contract). So a period's value
sets both the fixed-load total in that period's balance/flow rows **and** the upper bound of that
load's elastic column, if it has one. Moving only the first would be a silent no-op on every load
that bids: the two cancel exactly. Costs, **bids**, generator bounds, ratings and the PTDF matrix
are horizon-invariant — a bid load's willingness-to-pay curve is fixed by hour even though the
quantity it is bid against is not — and the PTDF is computed **once**
and reused across every period, which assumes a static topology over the horizon (no intra-horizon
switching or outage), consistent with the wave's Not-Doing list (research §2.2).

**Duals.** Read back from ``Highs.getSolution().row_dual``/``col_dual`` exactly as ``dc_opf``
does, under HiGHS's own convention ``reduced_cost_j = c_j - sum_r y_r * a_rj``. Per-period LMPs
come from feeding :class:`MultiperiodDuals`' period ``t`` slice to
:func:`~mambo_power.opf.dc_opf.lmp_decomposition`, unchanged from M3.

**Unit commitment (ADR-017).** With a :class:`Commitment` block the same model becomes a MIP:
three binary columns per generator per period — ``on`` (``u``), ``startup`` (``v``) and
``shutdown`` (``w``) — in a third column tier after the PWL free variables, and three row
families after tier 8:

===== ======================================== ==================================================
tier  family                                    rows
===== ======================================== ==================================================
9     capacity, ``p_g[t] − p_max·u_g[t] <= 0``  ``T*n_gen``
10    minimum, ``p_g[t] − p_min·u_g[t] >= 0``   ``T*n_gen``
11    logic, ``u[t] − u[t−1] − v[t] + w[t] == 0`` ``T*n_gen`` (``t = 0`` against ``initial_on``)
12    ``v[t] + w[t] <= 1``                      ``T*n_gen`` (no start and stop in one period)
13    minimum up, ``Σ v[s] − u[t] <= 0``        ``T`` per committable unit with ``min_up > 1``
14    minimum down, ``Σ w[s] + u[t] <= 1``      ``T`` per committable unit with ``min_down > 1``
===== ======================================== ==================================================

Tiers 13-14 (ADR-019) sum the events of the last ``min_up`` (``min_down``) periods ending at
``t``, ``s = max(0, t − min + 1) .. t``: a unit started inside that window is still on, one
stopped inside it is still off. A minimum of 1 is what the logic row already says and builds no
row. An obligation from before the horizon (``Commitment.initial_state_periods``) is a fixed
``on`` column over the periods it covers, not a row.

**Spinning reserve (ADR-023).** With ``reserve_mw`` (``(T,)``, the MW the fleet must hold in
each period) one reserve column ``r_g[t]`` per generator per period is appended after every
other column, bounded ``[0, reserve_max_mw[g]]`` (``inf`` where unlimited), costless, and two
row families follow tier 14 (or tier 8 without commitment):

===== ======================================== ==================================================
tier  family                                    rows
===== ======================================== ==================================================
15    requirement, ``Σ_g r_g[t] >= reserve[t]`` ``T``
16    headroom, ``p_g[t] + r_g[t] − p_max·u_g[t] <= 0`` ``T*n_gen`` (``u = 1`` without commitment)
===== ======================================== ==================================================

Reserve is held in a unit's unused capacity, so an uncommitted unit holds none, and a unit
cannot be dispatched to its ceiling while holding any. The requirement row's dual
(:attr:`MultiperiodDuals.reserve`) is the reserve price, nonnegative, nonzero when the fleet's
headroom is short: the energy that has to move from a cheaper unit to a dearer one to free it.
Storage holds no reserve here.

A unit with ``p_min <= 0``, no no-load cost and no start-up or shut-down cost has nothing
to commit — on at 0 MW and off are the same thing — so its binaries are fixed on and its
events off, and it stays the continuous column it is in the LP; only the other units are
*committable*. The generator columns' own lower bound drops to ``min(0, p_min)`` — the minimum
is a row that applies only while committed — and the objective gains ``no_load_cost·u``,
``startup_cost·v`` and ``shutdown_cost·w``. Tier 6 ramp rows split into one-sided pairs with a
``−p_max·v[t]`` / ``+p_max·w[t]`` relaxation so a unit may start at any output up to its capacity
and stop from any output; minimum up and down times are tiers 13-14. HiGHS solves MILPs, not
MIQPs, so a nonzero ``c2`` (or ``v2``) with a commitment block is a ``ValueError``: the caller
linearises a quadratic cost into ``pwl_costs`` first, as
:func:`mambo_power.market.multiperiod.solve_multiperiod` does. Tier 7 epigraph rows carry the
unit's ``on`` column, ``cost_g >= slope_i·p_g + intercept_i·u_g``, so a committed unit's cost is
its curve and an off unit's is exactly zero; the polynomial ``c0`` stays the unconditional
per-period constant it is in the LP (a caller who means "no-load" moves it into
``Commitment.no_load_cost``, as the market wrapper does). After the MIP solves, the binaries are
fixed at their solution and the model is re-run as an LP, which is where every dual above comes
from — the restricted-LP prices a unit-commitment market settles on (ADR-017).
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field

import highspy
import numpy as np
import numpy.typing as npt

from mambo_power.numerics.arrays import NetworkArrays
from mambo_power.numerics.bbus import p_shift, pf_shift
from mambo_power.numerics.ptdf import ptdf as compute_ptdf
from mambo_power.opf.dc_opf import (
    ColArray,
    FloatArray,
    _add_rows,
    _balance_row,
    _epigraph_rows,
    _extract_and_validate,
    _flow_limit_rows,
    _hypograph_rows,
    _pass_diagonal_hessian,
    _RowBlock,
)

_OPTIMAL = "Optimal"

__all__ = ["Commitment", "MultiperiodDuals", "MultiperiodSolution", "multiperiod_dc_opf"]

BoolArray = npt.NDArray[np.bool_]
IntArray = npt.NDArray[np.int64]


@dataclass(frozen=True)
class Commitment:
    """Unit-commitment data for :func:`multiperiod_dc_opf` (module docstring, "Unit commitment").

    All three arrays are ``(n_gen,)`` in ``NetworkArrays`` generator order. ``initial_on`` is each
    unit's status in the period before the horizon: a unit that is off there pays ``startup_cost``
    to run in period 0, one that is on pays ``shutdown_cost`` to stop.
    """

    startup_cost: FloatArray
    """Cost of a start-up, $ per event; ``>= 0``."""
    shutdown_cost: FloatArray
    """Cost of a shut-down, $ per event; ``>= 0``."""
    initial_on: BoolArray
    """Whether the unit is committed in the period before the horizon."""
    no_load_cost: FloatArray
    """Cost of being on for one period at any output, $; ``>= 0``."""
    min_up_periods: IntArray | None = None
    """``(n_gen,)`` minimum consecutive periods on once started (ADR-019); ``>= 1``, where 1
    (or ``None`` for the whole array) means no minimum: the logic rows already force a started
    unit on in the period it starts."""
    min_down_periods: IntArray | None = None
    """``(n_gen,)`` minimum consecutive periods off once stopped; ``>= 1``, 1 meaning none."""
    initial_state_periods: IntArray | None = None
    """``(n_gen,)`` how many periods each unit has already spent in its ``initial_on`` state
    before the horizon, ``>= 1`` (the period just before the horizon counts). ``None`` means
    long enough that no obligation carries in. A unit on for fewer periods than its minimum up
    time is held on for the remainder (clipped to the horizon), and likewise off against its
    minimum down time."""


@dataclass(frozen=True)
class MultiperiodDuals:
    """Shadow prices from one :func:`multiperiod_dc_opf` solve.

    Every array is period-major: row ``t`` is period ``t``'s own slice, in ``NetworkArrays``
    order along the second axis. :attr:`balance` and :attr:`flow_limit` row ``t`` are exactly the
    pair :func:`~mambo_power.opf.dc_opf.lmp_decomposition` takes for period ``t``.
    """

    balance: FloatArray
    """``(T,)`` — shadow price of each period's own nodal-balance row, $/MWh: that period's
    energy component. May be **negative** in a ramp-constrained period, and legitimately so: an
    extra MW of load in a period that a ramp row binds out of can let a cheap unit start earlier
    and displace an expensive one later (this module's own AC-2 test derives such a case by
    hand)."""
    flow_limit: FloatArray
    """``(T, n_branch)`` — per-period, per-branch shadow price of the ``[-rating, rating]`` flow
    row; 0 off the binding set, including every unrated branch."""
    gen_bound: FloatArray
    """``(T, n_gen)`` — per-period reduced cost of each generator's ``[p_min, p_max]`` bound."""
    demand_bound: FloatArray
    """``(T, n_demand)`` — per-period reduced cost of each elastic load's own bound, in the
    caller's ascending bid-index order (as :attr:`MultiperiodSolution.demand_dispatch_mw`)."""
    ramp: FloatArray
    """``(T-1, n_gen)`` — dual of the two-sided ramp row coupling period ``t-1`` to ``t`` (row
    ``t-1`` of this array), dense over **all** generators: exactly ``0`` for a generator that has
    no ramp row at all, which is also what a slack ramp row returns. Negative when the ramp-*up*
    side binds, positive when the ramp-*down* side does — HiGHS's own row-dual sign, the same
    convention :attr:`flow_limit` carries. Shape ``(0, n_gen)`` when ``T == 1``."""
    soc_balance: FloatArray
    """``(T, n_storage)`` — dual of each unit's per-period SoC equality row, $/MWh, carrying
    HiGHS's own row-dual sign (the convention :attr:`flow_limit` and :attr:`ramp` carry too). It
    is the **negative** of the marginal value of stored energy, so it comes out *negative*
    wherever an extra MWh in the unit is worth having: ``-lambda_t / eta_c`` where the unit
    charges on an interior column and ``-eta_d * lambda_t`` where it discharges on one — e.g.
    exactly ``-45.0`` against a 50 $/MWh price at ``eta_d = 0.9``, hand-derived from the KKT
    conditions in ``tests/unit/test_opf_multiperiod.py``. Read the worth of an MWh as
    ``-soc_balance``."""
    storage_power_limit: FloatArray
    """``(T, n_storage)`` — dual of the shared ``charge + discharge <= p_max_mw`` row; 0 unless
    the unit's combined throughput is at its converter rating."""
    storage_soc_bound: FloatArray
    """``(T, n_storage)`` — reduced cost of the ``soc`` column's ``[0, energy_mwh]`` bound,
    non-zero at **either** end of it: a unit sitting empty binds that bound exactly as much as a
    unit sitting full, and an empty unit is the commoner reading of the two (research §7.3's
    ``mu_soc`` is the full-end case). 0 only where the state of charge is strictly interior."""
    cyclic: FloatArray
    """``(n_storage,)`` — dual of the end-of-horizon ``soc[T-1] == soc_initial`` equality row: the
    cost the cyclic condition itself imposes, separable from the SoC dynamics above it."""
    reserve: FloatArray = field(default_factory=lambda: np.zeros(0))
    """``(T,)`` — dual of each period's reserve-requirement row (ADR-023), $/MW: the reserve
    price, ``>= 0``. Length 0 without a ``reserve_mw`` argument."""


@dataclass(frozen=True)
class MultiperiodSolution:
    """Result of one :func:`multiperiod_dc_opf` solve.

    Every quantity array is period-major — row ``t`` is period ``t`` — so a caller slices a period
    out rather than reshaping. All are zero-filled at the declared shape when ``status`` is not
    ``"Optimal"``, mirroring :class:`~mambo_power.opf.dc_opf.OpfSolution`.
    """

    status: str
    """HiGHS's own model-status string, passed through verbatim (as ``OpfSolution.status``)."""
    n_periods: int
    """``T`` — the number of coupled periods solved, echoed back so a caller reading only this
    object still knows the leading axis of every array below."""
    dispatch_mw: FloatArray
    """``(T, n_gen)`` per-generator dispatch, MW, ``NetworkArrays`` generator order."""
    demand_dispatch_mw: FloatArray
    """``(T, n_demand)`` per-elastic-load dispatch, MW. Column order is the caller's own bid-index
    set, ``sorted(set(demand_bid_coeffs or {}) | set(demand_pwl_bids or {}))`` — identical to
    :attr:`~mambo_power.opf.dc_opf.OpfSolution.demand_dispatch_mw`'s. Width 0 when no bid was
    supplied."""
    storage_charge_mw: FloatArray
    """``(T, n_storage)`` charging power, MW, ``NetworkArrays`` storage order; nonnegative."""
    storage_discharge_mw: FloatArray
    """``(T, n_storage)`` discharging power, MW; nonnegative. ``min(charge, discharge)`` is
    expected to be ~0 (AC-3's committed invariant) but is *not* structurally forced — see the
    module docstring on why banning overlap can make the LP infeasible."""
    storage_soc_mwh: FloatArray
    """``(T, n_storage)`` state of charge at the **end** of each period, MWh. ``storage_soc_mwh[-1]
    == soc_initial * energy_mwh`` exactly, by the cyclic row."""
    ptdf: FloatArray
    """The single PTDF matrix used for every period's flow rows, returned for reuse (LMP
    decomposition) exactly as :attr:`~mambo_power.opf.dc_opf.OpfSolution.ptdf` is."""
    objective_cost: float
    """Total generation cost over the whole horizon, $ — ``sum_t sum_g cost(p_g[t])``, including
    every generator's constant term in every period. 0.0 when ``status != "Optimal"``. Storage
    itself is costless here: :class:`~mambo_power.model.Storage` carries no cost field, so a unit's
    only economic footprint is the round-trip loss it imposes on generation."""
    duals: MultiperiodDuals | None
    """``None`` exactly when ``status != "Optimal"``."""
    message: str | None = None
    """Diagnostic when ``status != "Optimal"``; ``None`` otherwise."""
    committed: BoolArray = field(default_factory=lambda: np.zeros((0, 0), dtype=np.bool_))
    """``(T, n_gen)`` commitment status per period (ADR-017); shape ``(0, 0)`` without a
    :class:`Commitment` block."""
    started: BoolArray = field(default_factory=lambda: np.zeros((0, 0), dtype=np.bool_))
    """``(T, n_gen)`` start-up events; ``started[0]`` is relative to ``Commitment.initial_on``."""
    stopped: BoolArray = field(default_factory=lambda: np.zeros((0, 0), dtype=np.bool_))
    """``(T, n_gen)`` shut-down events."""
    commitment_cost: float = 0.0
    """Start-up plus shut-down cost over the horizon, $, included in :attr:`objective_cost`."""
    no_load_cost: float = 0.0
    """``sum_t sum_g Commitment.no_load_cost_g · u_g[t]``, $, included in :attr:`objective_cost`;
    0.0 without a :class:`Commitment` block."""
    reserve_mw: FloatArray = field(default_factory=lambda: np.zeros((0, 0)))
    """``(T, n_gen)`` spinning reserve each unit holds per period (ADR-023); shape ``(0, 0)``
    without a ``reserve_mw`` requirement."""


def _sparse_rows(
    rows: Sequence[Sequence[tuple[int, float]]],
    lower: Sequence[float] | FloatArray,
    upper: Sequence[float] | FloatArray,
) -> _RowBlock:
    """A :class:`~mambo_power.opf.dc_opf._RowBlock` from explicit ``(column, coefficient)`` pairs.

    The coupling families this module adds are *sparse* — a ramp row touches two columns, an SoC
    row four — so they are built from pairs rather than from
    :func:`~mambo_power.opf.dc_opf._dense_csr`, which exists to preserve ``dc_opf``'s dense
    structural-zero pattern for the balance/flow families and would be wrong here.
    """
    indices: list[int] = []
    values: list[float] = []
    starts = [0]
    for row in rows:
        for col, coefficient in row:
            indices.append(col)
            values.append(coefficient)
        starts.append(len(indices))
    return _RowBlock(
        lower=np.asarray(lower, dtype=np.float64),
        upper=np.asarray(upper, dtype=np.float64),
        starts=np.asarray(starts, dtype=np.int32),
        indices=np.asarray(indices, dtype=np.int32),
        values=np.asarray(values, dtype=np.float64),
    )


def _checked_ramp(
    name: str, values: FloatArray | None, n_gen: int, *, allow_zero: bool = False
) -> FloatArray:
    """Validate one ramp array and normalise "unconstrained" to ``+inf``.

    ``None`` (no array at all), ``inf`` and ``nan`` all mean *unconstrained* — no row is built for
    that generator. Anything else must be **strictly** positive: ``0`` would freeze the generator
    at its first-period dispatch for the whole horizon, which is MATPOWER's unpopulated-column
    default rather than a limit anybody declares (research §4.2, design table T1). With
    ``allow_zero`` (a reserve cap, ADR-023) ``0`` is a legitimate value: the unit holds none.
    """
    if values is None:
        return np.full(n_gen, np.inf)
    array = np.asarray(values, dtype=np.float64)
    if array.shape != (n_gen,):
        raise ValueError(f"{name} must have shape ({n_gen},), got {array.shape}")
    array = np.where(np.isnan(array), np.inf, array)
    finite = np.isfinite(array)
    if allow_zero:
        if finite.any() and (array[finite] < 0).any():
            raise ValueError(f"{name} must be >= 0 (None/inf/nan for an uncapped generator)")
        return array
    if finite.any() and (array[finite] <= 0).any():
        bad = int(np.flatnonzero(finite & (array <= 0))[0])
        raise ValueError(
            f"{name}[{bad}] = {array[bad]!r} — a ramp limit must be strictly positive "
            "(use None/inf/nan for an unconstrained generator; 0 would mean 'frozen', the "
            "MATPOWER unpopulated-ramp-column trap)"
        )
    return array


def _checked_periods(name: str, values: IntArray | None, n_gen: int, least: int) -> IntArray:
    """``commitment.<name>`` as an ``(n_gen,)`` integer array ``>= least``; ``None`` is all
    ``least``."""
    if values is None:
        return np.full(n_gen, least, dtype=np.int64)
    out = np.asarray(values)
    if out.shape != (n_gen,):
        raise ValueError(
            f"commitment.{name} must have shape ({n_gen},) (NetworkArrays generator order), "
            f"got {out.shape}"
        )
    if not np.issubdtype(out.dtype, np.integer) or np.any(out < least):
        raise ValueError(f"commitment.{name} must be integers >= {least}")
    return out.astype(np.int64)


def multiperiod_dc_opf(
    arr: NetworkArrays,
    cost_coeffs: FloatArray,
    n_periods: int,
    *,
    period_load_mw: FloatArray | None = None,
    ramp_up_mw: FloatArray | None = None,
    ramp_down_mw: FloatArray | None = None,
    pwl_costs: Mapping[int, Sequence[tuple[float, float]]] | None = None,
    demand_bid_coeffs: Mapping[int, tuple[float, float, float]] | None = None,
    demand_pwl_bids: Mapping[int, Sequence[tuple[float, float]]] | None = None,
    commitment: Commitment | None = None,
    reserve_mw: FloatArray | None = None,
    reserve_max_mw: FloatArray | None = None,
) -> MultiperiodSolution:
    """Solve ``n_periods`` coupled DC-OPF periods as one LP/QP (module docstring).

    ``cost_coeffs``, ``pwl_costs``, ``demand_bid_coeffs`` and ``demand_pwl_bids`` are exactly
    :func:`~mambo_power.opf.dc_opf.dc_opf`'s, and are **horizon-invariant**: M5 varies the fixed
    load across periods and nothing else (per-period offers/bids are the wave's own Not-Doing
    list). ``period_load_mw`` is ``(n_periods, n_load)`` in MW, indexed by
    ``NetworkArrays.load_ids``; ``None`` means every period carries the network's own load, which
    reduces the whole solve to ``n_periods`` identical copies of ``dc_opf``'s LP coupled only by
    whatever ramp/SoC rows the other arguments ask for. ``ramp_up_mw``/``ramp_down_mw`` are
    ``(n_gen,)`` in MW; ``None``, ``inf`` and ``nan`` all mark an unconstrained generator, for
    which no ramp row is built at all.

    Storage is read straight off ``arr``'s per-storage identity arrays (M5 W4) — a network with no
    :class:`~mambo_power.model.Storage` builds no storage column and no SoC row, so the storage
    formulation costs a storage-free caller nothing.

    Raises :class:`~mambo_power.opf.dc_opf.NonConvexCostError` /
    :class:`~mambo_power.opf.dc_opf.NonConcaveBidError` up front for a non-convex cost or
    non-concave bid, and :class:`ValueError` for a mis-shaped argument — all before any HiGHS
    object exists. Never raises for an infeasible or unbounded model: that is reported through
    ``status``/``message``, as in ``dc_opf``.

    ``commitment`` (module docstring, "Unit commitment") turns the solve into a MIP over per-unit
    on/start-up/shut-down binaries, with the duals read from the LP left once those binaries are
    fixed at the optimum; ``None`` — every other caller — leaves the LP exactly as before.

    ``reserve_mw`` (module docstring, "Spinning reserve") is the ``(T,)`` reserve requirement,
    met from committed units' headroom and priced by its own row; ``reserve_max_mw`` caps each
    unit's contribution (``(n_gen,)``; ``None``, ``nan`` and ``inf`` mean uncapped, 0 excludes
    the unit). ``None`` builds no reserve column or row.
    """
    n_gen = len(arr.gen_ids)
    n_load = len(arr.load_ids)
    n_storage = len(arr.storage_ids)
    n_branch = arr.n_branch

    if n_periods < 1:
        raise ValueError(f"n_periods must be >= 1, got {n_periods}")

    # --- cost/bid extraction and validation: dc_opf's own helper, not a copy of it (ADR-008).
    # It runs before period_load_mw/ramp validation because every guard it carries is promised
    # "up front" by this function's own docstring and by the two error classes' docstrings.
    problem = _extract_and_validate(
        cost_coeffs, pwl_costs, demand_bid_coeffs, demand_pwl_bids, n_gen, n_load
    )
    c2, c1, c0 = problem.c2, problem.c1, problem.c0
    v1, v2 = problem.v1, problem.v2
    pwl_gen_idxs, segments_by_gen = problem.pwl_gen_idxs, problem.segments_by_gen
    demand_pwl_idxs, demand_segments_by_load = (
        problem.demand_pwl_idxs,
        problem.demand_segments_by_load,
    )
    elastic_load_idxs = problem.elastic_load_idxs
    n_pwl, n_demand, n_demand_pwl = problem.n_pwl, problem.n_demand, problem.n_demand_pwl

    if period_load_mw is not None:
        period_load_mw = np.asarray(period_load_mw, dtype=np.float64)
        if period_load_mw.shape != (n_periods, n_load):
            raise ValueError(
                f"period_load_mw must have shape ({n_periods}, {n_load}) "
                f"(MW per load, NetworkArrays.load_ids order), got {period_load_mw.shape}"
            )
    ramp_up = _checked_ramp("ramp_up_mw", ramp_up_mw, n_gen)
    ramp_down = _checked_ramp("ramp_down_mw", ramp_down_mw, n_gen)
    if commitment is not None:
        for name, values in (
            ("startup_cost", commitment.startup_cost),
            ("shutdown_cost", commitment.shutdown_cost),
            ("initial_on", commitment.initial_on),
            ("no_load_cost", commitment.no_load_cost),
        ):
            if np.asarray(values).shape != (n_gen,):
                raise ValueError(
                    f"commitment.{name} must have shape ({n_gen},) (NetworkArrays generator "
                    f"order), got {np.asarray(values).shape}"
                )
        if (
            np.any(commitment.startup_cost < 0)
            or np.any(commitment.shutdown_cost < 0)
            or np.any(commitment.no_load_cost < 0)
        ):
            raise ValueError("commitment start-up, shut-down and no-load costs must be >= 0")
        if np.any(c2 != 0.0) or np.any(v2 != 0.0):
            raise ValueError(
                "unit commitment needs linear or piecewise-linear costs and bids: HiGHS solves "
                "MILPs, not MIQPs; linearise a quadratic cost into pwl_costs first (the market "
                "wrapper does this with MarketMultiperiodOptions.quadratic_segments)"
            )
        min_up = _checked_periods("min_up_periods", commitment.min_up_periods, n_gen, 1)
        min_down = _checked_periods("min_down_periods", commitment.min_down_periods, n_gen, 1)
        initial_periods = (
            None
            if commitment.initial_state_periods is None
            else _checked_periods(
                "initial_state_periods", commitment.initial_state_periods, n_gen, 1
            )
        )

    reserve: FloatArray | None = None
    if reserve_mw is not None:
        reserve = np.asarray(reserve_mw, dtype=np.float64)
        if reserve.shape != (n_periods,):
            raise ValueError(
                f"reserve_mw must have shape ({n_periods},) (MW per period), got {reserve.shape}"
            )
        if np.any(reserve < 0) or not np.all(np.isfinite(reserve)):
            raise ValueError("reserve_mw must be finite and >= 0")
    reserve_cap = _checked_ramp("reserve_max_mw", reserve_max_mw, n_gen, allow_zero=True)

    # --- column layout (module docstring, "Column layout") -------------------------------------
    per_period_dispatch = n_gen + n_demand + 3 * n_storage
    per_period_free = n_pwl + n_demand_pwl
    n_dispatch_total = n_periods * per_period_dispatch

    def _cols(base: int, offset: int, count: int) -> ColArray:
        return np.arange(base + offset, base + offset + count, dtype=np.int32)

    gen_cols: list[ColArray] = []
    demand_cols: list[ColArray] = []
    charge_cols: list[ColArray] = []
    discharge_cols: list[ColArray] = []
    soc_cols: list[ColArray] = []
    for t in range(n_periods):
        base = t * per_period_dispatch
        gen_cols.append(_cols(base, 0, n_gen))
        demand_cols.append(_cols(base, n_gen, n_demand))
        charge_cols.append(_cols(base, n_gen + n_demand, n_storage))
        discharge_cols.append(_cols(base, n_gen + n_demand + n_storage, n_storage))
        soc_cols.append(_cols(base, n_gen + n_demand + 2 * n_storage, n_storage))

    cost_col_of: list[dict[int, int]] = []
    demand_val_col_of: list[dict[int, int]] = []
    for t in range(n_periods):
        base = n_dispatch_total + t * per_period_free
        cost_col_of.append(dict(zip(pwl_gen_idxs, range(base, base + n_pwl), strict=True)))
        demand_val_col_of.append(
            dict(
                zip(
                    demand_pwl_idxs,
                    range(base + n_pwl, base + n_pwl + n_demand_pwl),
                    strict=True,
                )
            )
        )
    # dc_opf keys its epigraph rows by generator index into a *dense* gen-column array; the
    # per-period equivalent is that period's own gen_cols slice.
    demand_col_of: list[dict[int, int]] = [
        dict(zip(elastic_load_idxs, cols.tolist(), strict=True)) for cols in demand_cols
    ]

    h = highspy.Highs()  # type: ignore[no-untyped-call]  # highspy ships no type stubs
    h.setOptionValue("output_flag", False)

    # --- tier 1 columns, period by period (the same addVars/changeColsCost sequence dc_opf
    # issues, repeated once per period, so a one-period solve is the identical call sequence).
    p_min = arr.gen_p_min_pu * arr.base_mva
    p_max = arr.gen_p_max_pu * arr.base_mva
    # With commitment the minimum output is a row that applies only while the unit is on (tier
    # 10); the column itself must admit 0 so the unit can be off.
    p_col_min = np.minimum(p_min, 0.0) if commitment is not None else p_min
    elastic_idx_arr = np.asarray(elastic_load_idxs, dtype=np.int64)
    demand_p_min = arr.load_p_min_pu[elastic_idx_arr] * arr.base_mva
    # ``(n_periods, n_demand)``: a bid load's upper bound is **that period's** own demand, not the
    # network's base one. ``Load.p_mw`` is the largest quantity an elastic load's bid can clear
    # (M4's elastic-demand contract) and ``Period.load_p_mw`` overrides ``p_mw``, so the override
    # has to move this bound with it. A bound frozen at ``arr.load_p_max_pu`` would cancel the
    # override exactly: the period's own value is already removed from the fixed-load total below
    # (the double-counting contract), so the column would re-serve the *base* quantity and a
    # profile would have no effect at all on any load that bids. The bid itself stays
    # horizon-invariant -- what moves is the quantity anchor, not the willingness-to-pay curve.
    # ``load_p_min_pu`` is not derived from ``p_mw``, so it does not move.
    if period_load_mw is None:
        demand_p_max = np.tile(arr.load_p_max_pu[elastic_idx_arr] * arr.base_mva, (n_periods, 1))
    else:
        demand_p_max = period_load_mw[:, elastic_idx_arr]
    storage_p_max = arr.storage_p_max_pu * arr.base_mva
    storage_energy = arr.storage_energy_pu * arr.base_mva
    soc_initial_mwh = arr.storage_soc_initial * storage_energy
    eta_charge = arr.storage_efficiency_charge
    eta_discharge = arr.storage_efficiency_discharge

    for t in range(n_periods):
        if n_gen:
            h.addVars(n_gen, p_col_min, p_max)
            h.changeColsCost(n_gen, gen_cols[t], c1)
        if n_demand:
            h.addVars(n_demand, demand_p_min, demand_p_max[t])
            # minimising sum(cost_g) - sum(value_d): the demand column's linear coefficient is -v1
            h.changeColsCost(n_demand, demand_cols[t], -v1)
        if n_storage:
            h.addVars(n_storage, np.zeros(n_storage), storage_p_max)
            h.addVars(n_storage, np.zeros(n_storage), storage_p_max)
            h.addVars(n_storage, np.zeros(n_storage), storage_energy)

    # --- Hessian over tier 1 only, passed before any tier-2 column exists (module docstring).
    # dc_opf's own helper, not a copy of it (ADR-008 one level down): one block per period,
    # per_period_dispatch wide, whose 3*n_storage storage columns carry no quadratic term.
    _pass_diagonal_hessian(
        h,
        c2,
        v2,
        n_gen,
        n_demand,
        n_blocks=n_periods,
        block_stride=per_period_dispatch,
    )

    # --- tier 2 columns: the free PWL cost_g / val_d variables, period by period.
    for t in range(n_periods):
        if n_pwl:
            cols = np.asarray(sorted(cost_col_of[t].values()), dtype=np.int32)
            h.addVars(n_pwl, np.full(n_pwl, -highspy.kHighsInf), np.full(n_pwl, highspy.kHighsInf))
            h.changeColsCost(n_pwl, cols, np.ones(n_pwl))
        if n_demand_pwl:
            cols = np.asarray(sorted(demand_val_col_of[t].values()), dtype=np.int32)
            h.addVars(
                n_demand_pwl,
                np.full(n_demand_pwl, -highspy.kHighsInf),
                np.full(n_demand_pwl, highspy.kHighsInf),
            )
            h.changeColsCost(n_demand_pwl, cols, -np.ones(n_demand_pwl))

    # --- tier 3 columns (module docstring, "Unit commitment"): per period [on | startup |
    # shutdown], binary, costed c0 / startup / shutdown. Appended after every continuous column
    # so the Hessian prefix and the tier-2 layout above are untouched.
    on_cols: list[ColArray] = []
    start_cols: list[ColArray] = []
    stop_cols: list[ColArray] = []
    committable = np.zeros(n_gen, dtype=np.bool_)
    if commitment is not None and n_gen:
        committable = (
            (p_min > 0.0)
            | (commitment.no_load_cost > 0.0)
            | (commitment.startup_cost > 0.0)
            | (commitment.shutdown_cost > 0.0)
        )
        on_lower = np.where(committable, 0.0, 1.0)
        event_upper = np.where(committable, 1.0, 0.0)
        tier3_base = n_dispatch_total + n_periods * per_period_free
        for t in range(n_periods):
            base = tier3_base + t * 3 * n_gen
            on_cols.append(_cols(base, 0, n_gen))
            start_cols.append(_cols(base, n_gen, n_gen))
            stop_cols.append(_cols(base, 2 * n_gen, n_gen))
            for cols, cost, lower, upper in (
                (on_cols[t], commitment.no_load_cost, on_lower, np.ones(n_gen)),
                (start_cols[t], commitment.startup_cost, np.zeros(n_gen), event_upper),
                (stop_cols[t], commitment.shutdown_cost, np.zeros(n_gen), event_upper),
            ):
                h.addVars(n_gen, lower, upper)
                h.changeColsCost(n_gen, cols, np.asarray(cost, dtype=np.float64))
                h.changeColsIntegrality(n_gen, cols, [highspy.HighsVarType.kInteger] * n_gen)

    # --- per-period fixed load, and the flow-row constant it drives -----------------------------
    # dc_opf's own arithmetic, evaluated once per period: the bus-aggregate fixed load minus each
    # elastic load's own contribution at its own bus (the double-counting contract). With
    # period_load_mw=None the expressions below are literally dc_opf's, which is what makes the
    # T=1 reduction exact rather than merely close. p_shift_mw (numerics.bbus.p_shift) is the
    # phase-shifter bus injection dc_opf's own const_k folds in by hand (dc_opf.py's flow-limit
    # row comment; M8 finding F1 / A19, task-shifter-flow-fix.plan.md T6) -- it is
    # period-invariant (a function of topology, not dispatch), so it is computed once here rather
    # than inside the per-period loop below.
    ptdf_matrix = compute_ptdf(arr)
    pf_shift_mw = pf_shift(arr) * arr.base_mva
    p_shift_mw = p_shift(arr) * arr.base_mva
    g_shunt_mw = arr.g_shunt_pu * arr.base_mva
    rating_mw = arr.rating_pu * arr.base_mva
    elastic_bus = arr.load_bus[elastic_idx_arr]

    total_fixed: list[float] = []
    const: list[FloatArray] = []
    for t in range(n_periods):
        if period_load_mw is None:
            p_load_mw = arr.p_load_pu * arr.base_mva
            elastic_own_mw = arr.load_p_max_pu[elastic_idx_arr] * arr.base_mva
        else:
            p_load_mw = np.asarray(
                np.bincount(arr.load_bus, weights=period_load_mw[t], minlength=arr.n_bus),
                dtype=np.float64,
            )
            elastic_own_mw = period_load_mw[t][elastic_idx_arr]
        if n_demand:
            p_load_mw = p_load_mw - np.bincount(
                elastic_bus, weights=elastic_own_mw, minlength=arr.n_bus
            )
        total_fixed.append(float(np.sum(p_load_mw) + np.sum(g_shunt_mw)))
        const.append(pf_shift_mw - ptdf_matrix @ (p_load_mw + g_shunt_mw + p_shift_mw))

    # --- rows, in the order the module docstring's table declares -------------------------------
    # tier 1: nodal balance, one row per period. Storage discharges into the balance and charges
    # out of it, so it joins the generator/elastic-load sides of the *same* helper.
    for t in range(n_periods):
        _add_rows(
            h,
            _balance_row(
                np.concatenate([gen_cols[t], discharge_cols[t]]),
                np.concatenate([demand_cols[t], charge_cols[t]]),
                total_fixed[t],
            ),
        )

    # tier 2: PTDF flow-limit rows, per branch per period. Storage sits at a bus like anything
    # else, so its two columns carry that bus's PTDF column with the injection/withdrawal sign.
    injection_bus = np.concatenate([arr.gen_bus, arr.storage_bus])
    withdrawal_bus = np.concatenate([elastic_bus, arr.storage_bus])
    for t in range(n_periods):
        _add_rows(
            h,
            _flow_limit_rows(
                ptdf_matrix,
                np.concatenate([gen_cols[t], discharge_cols[t]]),
                injection_bus,
                np.concatenate([demand_cols[t], charge_cols[t]]),
                withdrawal_bus,
                rating_mw,
                const[t],
            ),
        )

    # tier 3: SoC balance, one equality row per unit per period.
    if n_storage:
        soc_rows: list[list[tuple[int, float]]] = []
        soc_rhs: list[float] = []
        for t in range(n_periods):
            for s in range(n_storage):
                row = [
                    (int(soc_cols[t][s]), 1.0),
                    (int(charge_cols[t][s]), -float(eta_charge[s])),
                    (int(discharge_cols[t][s]), 1.0 / float(eta_discharge[s])),
                ]
                if t == 0:
                    soc_rhs.append(float(soc_initial_mwh[s]))
                else:
                    row.append((int(soc_cols[t - 1][s]), -1.0))
                    soc_rhs.append(0.0)
                soc_rows.append(row)
        _add_rows(h, _sparse_rows(soc_rows, soc_rhs, soc_rhs))

        # tier 4: the shared power-limit row (research §3.3 option 1) — bounds how much overlap
        # the formulation can ever reach for, without banning the case where it is required.
        limit_rows = [
            [(int(charge_cols[t][s]), 1.0), (int(discharge_cols[t][s]), 1.0)]
            for t in range(n_periods)
            for s in range(n_storage)
        ]
        limit_upper = np.tile(storage_p_max, n_periods)
        _add_rows(
            h,
            _sparse_rows(limit_rows, np.full(limit_upper.size, -highspy.kHighsInf), limit_upper),
        )

        # tier 5: cyclic end-of-horizon SoC (scope answer 2 — not configurable).
        last = n_periods - 1
        cyclic_rows = [[(int(soc_cols[last][s]), 1.0)] for s in range(n_storage)]
        _add_rows(h, _sparse_rows(cyclic_rows, soc_initial_mwh, soc_initial_mwh))

    # tier 6: ramp coupling. A generator with neither limit gets no row; a one-sided limit gets a
    # genuinely infinite bound on the other side.
    ramped = np.flatnonzero(np.isfinite(ramp_up) | np.isfinite(ramp_down))
    n_ramped = int(ramped.size)
    if n_ramped and n_periods > 1:
        down = np.where(np.isfinite(ramp_down[ramped]), -ramp_down[ramped], -highspy.kHighsInf)
        up = np.where(np.isfinite(ramp_up[ramped]), ramp_up[ramped], highspy.kHighsInf)
        if commitment is None:
            ramp_rows = [
                [(int(gen_cols[t][g]), 1.0), (int(gen_cols[t - 1][g]), -1.0)]
                for t in range(1, n_periods)
                for g in ramped
            ]
            _add_rows(
                h,
                _sparse_rows(ramp_rows, np.tile(down, n_periods - 1), np.tile(up, n_periods - 1)),
            )
        else:
            # Two one-sided families, each relaxed by the unit's capacity on the period it
            # starts (up side) or stops (down side), so a start-up to any output and a
            # shut-down from any output are both admissible — the ramp applies between two
            # committed periods only.
            up_rows = [
                [
                    (int(gen_cols[t][g]), 1.0),
                    (int(gen_cols[t - 1][g]), -1.0),
                    (int(start_cols[t][g]), -float(p_max[g])),
                ]
                for t in range(1, n_periods)
                for g in ramped
            ]
            down_rows = [
                [
                    (int(gen_cols[t][g]), 1.0),
                    (int(gen_cols[t - 1][g]), -1.0),
                    (int(stop_cols[t][g]), float(p_max[g])),
                ]
                for t in range(1, n_periods)
                for g in ramped
            ]
            n_pairs = (n_periods - 1) * n_ramped
            _add_rows(
                h,
                _sparse_rows(
                    up_rows, np.full(n_pairs, -highspy.kHighsInf), np.tile(up, n_periods - 1)
                ),
            )
            _add_rows(
                h,
                _sparse_rows(
                    down_rows, np.tile(down, n_periods - 1), np.full(n_pairs, highspy.kHighsInf)
                ),
            )

    # tiers 7-8: PWL epigraph / hypograph rows, appended after tier 6 so no dual index above
    # shifts. With commitment the epigraph carries the unit's ``on`` column (module docstring,
    # "Unit commitment") so an off unit's cost_g is pulled to exactly zero.
    for t in range(n_periods):
        if commitment is None:
            _add_rows(h, _epigraph_rows(segments_by_gen, gen_cols[t], cost_col_of[t]))
        else:
            rows = [
                [
                    (cost_col_of[t][g], 1.0),
                    (int(gen_cols[t][g]), -slope),
                    (int(on_cols[t][g]), -intercept),
                ]
                for g in sorted(segments_by_gen)
                for slope, intercept in segments_by_gen[g]
            ]
            _add_rows(
                h,
                _sparse_rows(rows, np.zeros(len(rows)), np.full(len(rows), highspy.kHighsInf)),
            )
    for t in range(n_periods):
        _add_rows(
            h, _hypograph_rows(demand_segments_by_load, demand_col_of[t], demand_val_col_of[t])
        )

    # tiers 9-12 (module docstring, "Unit commitment"): capacity, minimum, logic and
    # one-event-per-period rows.
    n_commit_rows = 0
    if commitment is not None and n_gen:
        cap_rows = [
            [(int(gen_cols[t][g]), 1.0), (int(on_cols[t][g]), -float(p_max[g]))]
            for t in range(n_periods)
            for g in range(n_gen)
        ]
        min_rows = [
            [(int(gen_cols[t][g]), 1.0), (int(on_cols[t][g]), -float(p_min[g]))]
            for t in range(n_periods)
            for g in range(n_gen)
        ]
        logic_rows: list[list[tuple[int, float]]] = []
        logic_rhs: list[float] = []
        for t in range(n_periods):
            for g in range(n_gen):
                row = [
                    (int(on_cols[t][g]), 1.0),
                    (int(start_cols[t][g]), -1.0),
                    (int(stop_cols[t][g]), 1.0),
                ]
                if t == 0:
                    # a non-committable unit is always on, whatever its declared initial state
                    on_initially = commitment.initial_on[g] or not committable[g]
                    logic_rhs.append(1.0 if on_initially else 0.0)
                else:
                    row.append((int(on_cols[t - 1][g]), -1.0))
                    logic_rhs.append(0.0)
                logic_rows.append(row)
        # Without this row a unit whose start and stop are both free could register one of each
        # in the same period at no cost, which the logic row alone admits.
        event_rows = [
            [(int(start_cols[t][g]), 1.0), (int(stop_cols[t][g]), 1.0)]
            for t in range(n_periods)
            for g in range(n_gen)
        ]
        n_commit_rows = 4 * n_periods * n_gen
        count = n_periods * n_gen
        _add_rows(h, _sparse_rows(cap_rows, np.full(count, -highspy.kHighsInf), np.zeros(count)))
        _add_rows(h, _sparse_rows(min_rows, np.zeros(count), np.full(count, highspy.kHighsInf)))
        _add_rows(h, _sparse_rows(logic_rows, logic_rhs, logic_rhs))
        _add_rows(h, _sparse_rows(event_rows, np.full(count, -highspy.kHighsInf), np.ones(count)))
        # tiers 13-14 (ADR-019): a start within the last min_up periods keeps the unit on, a
        # stop within the last min_down periods keeps it off. A minimum of 1 adds nothing the
        # logic row does not already say, so it builds no row; nor does a non-committable unit.
        up_units = [g for g in range(n_gen) if committable[g] and min_up[g] > 1]
        down_units = [g for g in range(n_gen) if committable[g] and min_down[g] > 1]
        up_rows = [
            [(int(start_cols[s][g]), 1.0) for s in range(max(0, t - int(min_up[g]) + 1), t + 1)]
            + [(int(on_cols[t][g]), -1.0)]
            for t in range(n_periods)
            for g in up_units
        ]
        down_rows = [
            [(int(stop_cols[s][g]), 1.0) for s in range(max(0, t - int(min_down[g]) + 1), t + 1)]
            + [(int(on_cols[t][g]), 1.0)]
            for t in range(n_periods)
            for g in down_units
        ]
        n_commit_rows += len(up_rows) + len(down_rows)
        if up_rows:
            n_up = len(up_rows)
            _add_rows(h, _sparse_rows(up_rows, np.full(n_up, -highspy.kHighsInf), np.zeros(n_up)))
        if down_rows:
            n_down = len(down_rows)
            _add_rows(
                h, _sparse_rows(down_rows, np.full(n_down, -highspy.kHighsInf), np.ones(n_down))
            )
        # An obligation carried in from before the horizon is a fixed ``on`` column, not a row:
        # a unit on for k < min_up periods stays on for min_up - k more, and likewise off.
        if initial_periods is not None:
            for g in range(n_gen):
                if not committable[g]:
                    continue
                on_initially = bool(commitment.initial_on[g])
                minimum = int(min_up[g]) if on_initially else int(min_down[g])
                held = min(n_periods, max(0, minimum - int(initial_periods[g])))
                for t in range(held):
                    value = 1.0 if on_initially else 0.0
                    h.changeColBounds(int(on_cols[t][g]), value, value)
        # The default 1e-4 relative gap can leave a cheaper schedule unexplored; the problems
        # built here are small, so ask for the optimum.
        h.setOptionValue("mip_rel_gap", 1e-9)

    # tiers 15-16 (module docstring, "Spinning reserve"): reserve columns after every other
    # column, the requirement row per period and the headroom row per generator per period.
    reserve_cols: list[ColArray] = []
    n_reserve_rows = 0
    if reserve is not None and n_gen:
        base = h.getNumCol()
        upper = np.where(np.isfinite(reserve_cap), reserve_cap, highspy.kHighsInf)
        for t in range(n_periods):
            reserve_cols.append(_cols(base, t * n_gen, n_gen))
            h.addVars(n_gen, np.zeros(n_gen), upper)
        requirement_rows = [[(int(c), 1.0) for c in reserve_cols[t]] for t in range(n_periods)]
        headroom_rows = [
            [(int(gen_cols[t][g]), 1.0), (int(reserve_cols[t][g]), 1.0)]
            + ([(int(on_cols[t][g]), -float(p_max[g]))] if commitment is not None else [])
            for t in range(n_periods)
            for g in range(n_gen)
        ]
        headroom_upper = (
            np.zeros(n_periods * n_gen)
            if commitment is not None
            else np.tile(np.asarray(p_max, dtype=np.float64), n_periods)
        )
        _add_rows(h, _sparse_rows(requirement_rows, reserve, np.full(n_periods, highspy.kHighsInf)))
        _add_rows(
            h,
            _sparse_rows(
                headroom_rows, np.full(n_periods * n_gen, -highspy.kHighsInf), headroom_upper
            ),
        )
        n_reserve_rows = n_periods * (1 + n_gen)

    h.run()
    status = h.modelStatusToString(h.getModelStatus())

    committed = np.zeros((0, 0), dtype=np.bool_)
    started = np.zeros((0, 0), dtype=np.bool_)
    stopped = np.zeros((0, 0), dtype=np.bool_)
    if commitment is not None and n_gen and status == _OPTIMAL:
        # Fix the binaries at the MIP optimum and re-run as an LP: the duals every caller reads
        # below are this restricted LP's (module docstring, "Unit commitment").
        mip_value = np.asarray(h.getSolution().col_value, dtype=np.float64)

        def _bits(cols: list[ColArray]) -> BoolArray:
            return np.array([mip_value[c] > 0.5 for c in cols], dtype=np.bool_)

        committed, started, stopped = _bits(on_cols), _bits(start_cols), _bits(stop_cols)
        for t in range(n_periods):
            for cols, bits in (
                (on_cols[t], committed[t]),
                (start_cols[t], started[t]),
                (stop_cols[t], stopped[t]),
            ):
                fixed = bits.astype(np.float64)
                h.changeColsIntegrality(n_gen, cols, [highspy.HighsVarType.kContinuous] * n_gen)
                h.changeColsBounds(n_gen, cols, fixed, fixed)
        h.run()
        status = h.modelStatusToString(h.getModelStatus())

    if status != _OPTIMAL:
        return MultiperiodSolution(
            status=status,
            n_periods=n_periods,
            dispatch_mw=np.zeros((n_periods, n_gen)),
            demand_dispatch_mw=np.zeros((n_periods, n_demand)),
            storage_charge_mw=np.zeros((n_periods, n_storage)),
            storage_discharge_mw=np.zeros((n_periods, n_storage)),
            storage_soc_mwh=np.zeros((n_periods, n_storage)),
            ptdf=ptdf_matrix,
            objective_cost=0.0,
            duals=None,
            message=f"multiperiod_dc_opf: HiGHS reported model status {status!r}",
        )

    sol = h.getSolution()
    col_value = np.asarray(sol.col_value, dtype=np.float64)
    col_dual = np.asarray(sol.col_dual, dtype=np.float64)
    row_dual = np.asarray(sol.row_dual, dtype=np.float64)

    def _read(cols: list[ColArray], source: FloatArray) -> FloatArray:
        """``(T, width)`` view of one per-period column family, period-major."""
        out = np.zeros((n_periods, cols[0].size))
        for t, period_cols in enumerate(cols):
            out[t] = source[period_cols]
        return out

    dispatch_mw = _read(gen_cols, col_value)
    demand_dispatch_mw = _read(demand_cols, col_value)
    storage_charge_mw = _read(charge_cols, col_value)
    storage_discharge_mw = _read(discharge_cols, col_value)
    storage_soc_mwh = _read(soc_cols, col_value)

    # The row-order contract is declared in the module docstring's table, implemented once ~150
    # lines above, and re-derived just below as a hand-maintained running sum. Nothing else ties
    # those three together: a row family appended after tier 6 and not accounted for here shifts
    # every dual index below it, silently and by exactly its own height. The ``.reshape`` calls
    # below catch some of that, but only when a storage unit happens to exist. This does not
    # depend on anything happening to exist.
    n_epigraph = sum(len(segments_by_gen[i]) for i in pwl_gen_idxs)
    n_hypograph = sum(len(demand_segments_by_load[i]) for i in demand_pwl_idxs)
    n_ramp_rows = (n_periods - 1) * n_ramped * (2 if commitment is not None else 1)
    expected_rows = (
        n_periods * (1 + n_branch + 2 * n_storage)  # tiers 1-4
        + n_storage  # tier 5 (cyclic), one per unit for the whole horizon
        + n_ramp_rows  # tier 6, empty at T == 1 or with nothing ramped; two families committed
        + n_periods * (n_epigraph + n_hypograph)  # tiers 7-8, one row per segment per period
        + n_commit_rows  # tiers 9-14 (ADR-017, ADR-019)
        + n_reserve_rows  # tiers 15-16 (ADR-023)
    )
    assert h.getNumRow() == expected_rows, (
        f"multiperiod_dc_opf built {h.getNumRow()} rows, but the row-order contract in this "
        f"module's docstring accounts for {expected_rows} — every dual index below is read off "
        "that contract, so they must agree"
    )

    # row offsets, exactly the module docstring's table
    flow_base = n_periods
    soc_base = flow_base + n_periods * n_branch
    limit_base = soc_base + n_periods * n_storage
    cyclic_base = limit_base + n_periods * n_storage
    ramp_base = cyclic_base + n_storage

    ramp_duals = np.zeros((max(n_periods - 1, 0), n_gen))
    if n_ramped and n_periods > 1:
        block = row_dual[ramp_base : ramp_base + (n_periods - 1) * n_ramped]
        ramp_duals[:, ramped] = block.reshape(n_periods - 1, n_ramped)
        if commitment is not None:
            # the two one-sided families price the same coupling; only one can bind per pair
            down_block = row_dual[
                ramp_base + (n_periods - 1) * n_ramped : ramp_base + 2 * (n_periods - 1) * n_ramped
            ]
            ramp_duals[:, ramped] += down_block.reshape(n_periods - 1, n_ramped)

    duals = MultiperiodDuals(
        balance=row_dual[:n_periods].copy(),
        flow_limit=row_dual[flow_base:soc_base].reshape(n_periods, n_branch),
        gen_bound=_read(gen_cols, col_dual),
        demand_bound=_read(demand_cols, col_dual),
        ramp=ramp_duals,
        soc_balance=row_dual[soc_base:limit_base].reshape(n_periods, n_storage),
        storage_power_limit=row_dual[limit_base:cyclic_base].reshape(n_periods, n_storage),
        storage_soc_bound=_read(soc_cols, col_dual),
        cyclic=row_dual[cyclic_base:ramp_base].copy(),
        reserve=(
            # a >= row's dual is nonnegative at a minimum; clip HiGHS's -0.0 / -1e-13 to 0
            np.maximum(
                row_dual[
                    expected_rows - n_reserve_rows : expected_rows - n_reserve_rows + n_periods
                ],
                0.0,
            )
            if n_reserve_rows
            else np.zeros(0)
        ),
    )
    reserve_held = _read(reserve_cols, col_value) if reserve_cols else np.zeros((0, 0))

    pwl_gen_cost = float(
        sum(col_value[cost_col_of[t][i]] for t in range(n_periods) for i in pwl_gen_idxs)
    )
    poly_gen_cost = float(np.sum(c2 * dispatch_mw**2 + c1 * dispatch_mw + c0))
    commitment_cost = 0.0
    no_load_cost = 0.0
    if commitment is not None:
        no_load_cost = float(np.sum(commitment.no_load_cost * committed))
        commitment_cost = float(
            np.sum(commitment.startup_cost * started) + np.sum(commitment.shutdown_cost * stopped)
        )
    return MultiperiodSolution(
        status=status,
        n_periods=n_periods,
        dispatch_mw=dispatch_mw,
        demand_dispatch_mw=demand_dispatch_mw,
        storage_charge_mw=storage_charge_mw,
        storage_discharge_mw=storage_discharge_mw,
        storage_soc_mwh=storage_soc_mwh,
        ptdf=ptdf_matrix,
        objective_cost=poly_gen_cost + pwl_gen_cost + no_load_cost + commitment_cost,
        duals=duals,
        message=None,
        committed=committed,
        started=started,
        stopped=stopped,
        commitment_cost=commitment_cost,
        no_load_cost=no_load_cost,
        reserve_mw=reserve_held,
    )
