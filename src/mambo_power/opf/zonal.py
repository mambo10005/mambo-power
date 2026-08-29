"""Zonal clearing LP/QP builder over HiGHS.

Array-level entry point: :func:`zonal_dc_opf` clears a market at **zonal** granularity — one
price per zone, the intra-zone grid ignored entirely. It is the third caller of ``dc_opf``'s
row-family core (ADR-007) and the second of :func:`~mambo_power.opf.dc_opf._extract_and_validate`
(ADR-008), at the same altitude as :func:`~mambo_power.opf.dc_opf.dc_opf` and
:func:`~mambo_power.opf.multiperiod.multiperiod_dc_opf`: pure numerics over
:class:`~mambo_power.numerics.NetworkArrays` plus a caller-supplied zone partition and corridor
map, with no ``Network``/``Scenario`` dependency. The ``Scenario``-facing entry point is
:func:`~mambo_power.market.zonal.solve_zonal`.

**What a zonal clearing is, as an LP.** The nodal LP (:func:`~mambo_power.opf.dc_opf.dc_opf`)
carries one system-wide balance row and one PTDF flow-limit row per branch. The zonal LP replaces
*both*: one balance row **per zone**, and — instead of any branch-level flow row — one bounded
**exchange variable per tied zone-pair**, whose bound is that corridor's transfer capacity. That
is the design this builder implements: each zone is a copper plate internally, and the only thing
limiting where power comes from is how much a corridor can carry. There are deliberately **no**
intra-zone flow rows, and no flow rows at all —
:func:`~mambo_power.opf.dc_opf._flow_limit_rows` is never called here, and no PTDF matrix is ever
built. The whole point of the zonal design is that the intra-zone grid does not constrain
the clearing; a solve that consulted the PTDF would be modelling something else.

**Column layout — two tiers, mirroring** :func:`~mambo_power.opf.multiperiod.multiperiod_dc_opf`:

* **tier 1**: ``[gen (n_gen) | demand (n_demand) | corridor (n_corridor)]``.
* **tier 2**: ``[cost_g (n_pwl) | val_d (n_demand_pwl)]`` — the free PWL epigraph/hypograph
  columns, exactly as ``dc_opf`` appends them.

The quadratic Hessian covers the **dispatch** columns only (``[gen | demand]``), and is passed
*before* the corridor columns are appended — so this is ``dc_opf``'s own already-proven ordering
("Hessian over a column prefix, then append more columns") unchanged, not a new one. A corridor
column is a transfer, never a cost or a value: it carries no objective coefficient and no
quadratic term, so it has nothing to contribute to a Hessian in the first place.

**Corridor sign convention.** ``corridors`` is keyed by an unordered zone pair, given as a tuple
``(z1, z2)``; :func:`zonal_dc_opf` normalises each key to sorted order (``z1 < z2``) and uses
**positive == power flowing z1 -> z2**. Concretely, corridor ``(z1, z2)``'s column enters zone
``z1``'s balance row as a *withdrawal* (coefficient ``-1``) and zone ``z2``'s as an *injection*
(``+1``), and its variable bounds are the plain, symmetric ``[-cap_mw, +cap_mw]`` — the corridor's
capacity is a **variable bound**, not a row. So a negative
:attr:`ZonalSolution.corridor_flow_mw` entry means that corridor is carrying power the other way,
``z2 -> z1``, and is at ``-cap`` when it binds in that direction. Written out for a two-zone
network with one corridor, the pair of balance rows is ``p_A - f_AB == L_A`` and
``p_B + f_AB == L_B``.

**Row layout.** One balance row per zone, in :attr:`ZonalSolution.zone_ids` order (sorted), at row
indices ``0 .. n_zone-1``; then the PWL epigraph rows, then the PWL hypograph rows, both of which
are an internal encoding detail whose row indices nothing reads back. Zone ``z``'s row is::

    Σ p_g[z] − Σ p_d[z] + Σ f[·, z] − Σ f[z, ·]  ==  fixed_load_mw[z] + shunt_mw[z]

built by ``dc_opf``'s own :func:`~mambo_power.opf.dc_opf._balance_row` — the identical helper, the
identical ``+1``/``-1`` sign convention, just handed each zone's own column sets and each zone's
own fixed right-hand side. Nothing about the balance row's algebra is reimplemented here.

**Zone price.** Zone ``z``'s clearing price is its own balance row's dual, read straight off
HiGHS (:attr:`ZonalDuals.zone_price`) — the per-zone counterpart of
:attr:`~mambo_power.opf.dc_opf.OpfDuals.balance`, and the sole owner of the "zone price" concept
in this package. Two zones joined by a **slack** corridor necessarily price identically: summing
their balance rows cancels the exchange column entirely, collapsing them into the single
system-wide row ``dc_opf`` already builds. Prices separate exactly when a corridor binds, and by
exactly that corridor's own capacity shadow price.

**Corridor capacity shadow price.** :attr:`ZonalDuals.corridor_cap` is the shadow price of the
corridor's *capacity*: the rate at which the objective would improve per extra MW of cap, in
whichever direction the corridor is actually binding. It is therefore **non-negative by
construction** and ``0`` on a slack corridor, regardless of which way the flow runs. HiGHS reports
a bounded column's reduced cost with a sign that depends on which bound is active (negative at the
upper bound of a minimisation, positive at the lower); since relaxing the *capacity* moves the
active bound outward either way, the capacity price is that reduced cost's magnitude — see
:func:`_corridor_cap_price`, which derives the equality rather than asserting it.

**Degenerate case: one zone, no corridors.** Explicitly allowed, and equal to ``dc_opf`` on an
**unrated** network (every ``rating_mva`` absent). With a single zone the per-zone balance rows
collapse to the one system-wide row, and with no corridors there is no exchange column — so the
only structural difference from ``dc_opf`` is the ``n_branch`` unconstrained flow-limit rows
``dc_opf`` still builds and this builder never does. Those rows cannot bind, so the two LPs have
the same feasible set and the same optimum; they are nonetheless *different LPs* handed to HiGHS,
so the agreement is asserted to a measured **tolerance**, never bitwise — floating-point
reductions in a different order do not have to agree in the last bit, and on some platforms they
do not. The measured agreement on case30 is far tighter than the pinned tolerance — see
``tests/unit/test_opf_zonal.py``.

**Phase shifters do not enter the zonal balance rows.** ``dc_opf`` omits phase-shift injections
from its single balance row because they cancel *system-wide* by construction; per **zone** they
do not, since a phase shifter on a tie line injects in one zone and withdraws in the other. They
are omitted here regardless, and deliberately: a phase shifter is a device for steering flow on a
branch model this LP does not have. Whatever inter-zone transfer it would produce is already, and
entirely, what the corridor variable represents — bounded by the corridor's own capacity rather
than by a device setting. Folding ``pf_shift`` into a zone's fixed right-hand side would instead
*force* a transfer the zonal abstraction has no basis for, on top of the free one. At one zone
this omission is not merely defensible but exactly ``dc_opf``'s own (the system-wide cancellation),
which is what keeps the degenerate case above exact.

**Everything else is** ``dc_opf``'s. Cost/bid extraction, both convexity guards, the bid-index
range check and the polynomial/piecewise exclusivity rule come from the single shared
:func:`~mambo_power.opf.dc_opf._extract_and_validate` (ADR-008's whole point: this builder cannot
get them subtly different, because it does not implement them). The PWL epigraph/hypograph rows
come from :func:`~mambo_power.opf.dc_opf._epigraph_rows` /
:func:`~mambo_power.opf.dc_opf._hypograph_rows` verbatim. The elastic-demand double-counting
contract is honoured exactly as ``dc_opf`` honours it — each bid load's own historical ``p_mw`` is
removed from its own bus before that bus's fixed load is aggregated into its zone's row — so a
caller passes ``arr`` unmodified here too.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass

import highspy
import numpy as np

from mambo_power.numerics.arrays import NetworkArrays
from mambo_power.opf.dc_opf import (
    FloatArray,
    _add_rows,
    _balance_row,
    _epigraph_rows,
    _extract_and_validate,
    _hypograph_rows,
    _pass_diagonal_hessian,
)

_OPTIMAL = "Optimal"

ZoneKey = tuple[str, str]
"""An unordered zone pair, carried as a sorted tuple (``z1 < z2``) — a corridor's identity."""


@dataclass(frozen=True)
class ZonalDuals:
    """Shadow prices from one :func:`zonal_dc_opf` solve."""

    zone_price: FloatArray
    """``(n_zone,)`` — each zone's clearing price, $/MWh, in :attr:`ZonalSolution.zone_ids` order:
    the dual of that zone's own balance row (module docstring, "Zone price"). The per-zone
    counterpart of :attr:`~mambo_power.opf.dc_opf.OpfDuals.balance`, and equal to it in every zone
    when no corridor binds."""
    corridor_cap: FloatArray
    """``(n_corridor,)`` — each corridor's capacity shadow price, $/MWh, in
    :attr:`ZonalSolution.corridor_ids` order: how much the objective improves per extra MW of that
    corridor's cap, in whichever direction it is binding. **Non-negative**, and exactly ``0`` on a
    corridor that is not at either of its bounds (module docstring, "Corridor capacity shadow
    price"; :func:`_corridor_cap_price`). Where corridor ``(z1, z2)`` binds and the zones on
    either side both price at an interior marginal unit, this equals ``|price[z2] − price[z1]|``
    — an identity the tests assert, not one this field is computed from."""
    gen_bound: FloatArray
    """``(n_gen,)`` — reduced cost of each generator's ``[p_min, p_max]`` bound, generator order;
    0 unless that generator is pinned at a bound. Exactly
    :attr:`~mambo_power.opf.dc_opf.OpfDuals.gen_bound`."""


@dataclass(frozen=True)
class ZonalSolution:
    """Result of one :func:`zonal_dc_opf` solve.

    Modelled field-for-field on :class:`~mambo_power.opf.dc_opf.OpfSolution`, minus the two things
    a zonal clearing has no notion of (a PTDF matrix and per-branch flow duals) and plus the three
    a nodal one has no notion of (zone ids, corridor ids and corridor flows). Every quantity array
    is zero-filled at its declared shape when ``status`` is not ``"Optimal"``, exactly as
    ``OpfSolution``'s are.
    """

    status: str
    """HiGHS's own model-status string, passed through verbatim (as ``OpfSolution.status``)."""
    zone_ids: list[str]
    """The solve's zones, **sorted**, one per balance row. Echoed back because — unlike
    ``arr.gen_ids``, which the caller already holds — this ordering is derived here (from the
    ``zone_of_bus`` argument's own value set) and is the axis every zonal array below is in.
    Present regardless of ``status``."""
    corridor_ids: list[ZoneKey]
    """The solve's corridors, sorted, each a ``(z1, z2)`` tuple with ``z1 < z2`` — the axis of
    :attr:`corridor_flow_mw` and :attr:`ZonalDuals.corridor_cap`, and the key whose order fixes
    the flow sign convention (module docstring). Echoed back for the same reason
    :attr:`zone_ids` is; the caller's own ``corridors`` keys may have been given unsorted."""
    dispatch_mw: FloatArray
    """``(n_gen,)`` per-generator dispatch, MW, ``NetworkArrays`` generator order."""
    demand_dispatch_mw: FloatArray
    """``(n_demand,)`` per-elastic-load dispatch, MW. Column order is the caller's own bid-index
    set, ``sorted(set(demand_bid_coeffs or {}) | set(demand_pwl_bids or {}))`` — identical to
    :attr:`~mambo_power.opf.dc_opf.OpfSolution.demand_dispatch_mw`'s. Length 0 when no bid was
    supplied for any load."""
    demand_bound: FloatArray
    """``(n_demand,)`` reduced cost of each elastic load's ``[load_p_min_mw, load_p_max_mw]``
    bound, same order as :attr:`demand_dispatch_mw`; 0 unless that load is pinned at a bound.
    Sits on the solution rather than on :class:`ZonalDuals` because that is where
    :attr:`~mambo_power.opf.dc_opf.OpfSolution.demand_bound` sits. Required here, rather than
    defaulted as ``OpfSolution``'s is: that default exists only because the field was added to
    an already-shipped dataclass, which is not this one's history."""
    corridor_flow_mw: FloatArray
    """``(n_corridor,)`` net inter-zonal transfer on each corridor, MW, in :attr:`corridor_ids`
    order. **Positive means ``z1 -> z2``** for that corridor's own sorted key (module docstring);
    ``|flow| == cap`` exactly where the corridor binds."""
    objective_cost: float
    """Total **generation** cost, $/h — ``Σ (c2·p² + c1·p + c0)`` at the found dispatch plus every
    PWL generator's own ``cost_g``, including constant terms. Deliberately identical in meaning to
    :attr:`~mambo_power.opf.dc_opf.OpfSolution.objective_cost`, which likewise stays
    generation-cost-only even with elastic demand in the same solve: it is **not** HiGHS's own
    objective value, which with bid loads present also nets in the negated demand value. 0.0 when
    ``status != "Optimal"``."""
    duals: ZonalDuals | None
    """``None`` exactly when ``status != "Optimal"``."""
    message: str | None = None
    """Diagnostic when ``status != "Optimal"``; ``None`` otherwise."""


def _zone_labels(
    zone_of_bus: Mapping[str, str] | Sequence[str], bus_ids: Sequence[str]
) -> list[str]:
    """Each bus's zone label, in ``NetworkArrays`` bus order, from either accepted argument form.

    ``zone_of_bus`` may be a ``{bus id: zone id}`` mapping (what ``tests/_zones.py``'s
    ``zone_of_bus`` returns, and what a ``Network``-level caller naturally builds) or a positional
    sequence/array of labels already in bus order (what an array-level caller that never had bus
    ids naturally holds). Both are validated to the same standard: **every** bus must carry a zone.
    A partition with a hole is rejected rather than defaulted, because there is no defensible
    default — a bus omitted from the mapping has load and generation that must land in *some*
    zone's balance row, and silently dropping it would clear a market for a network the caller did
    not describe.
    """
    if isinstance(zone_of_bus, Mapping):
        missing = [bus_id for bus_id in bus_ids if bus_id not in zone_of_bus]
        if missing:
            raise ValueError(
                f"zone_of_bus is missing {len(missing)} of {len(bus_ids)} buses "
                f"(first: {missing[0]!r}) -- every bus must be assigned to a zone"
            )
        return [str(zone_of_bus[bus_id]) for bus_id in bus_ids]
    labels = [str(label) for label in zone_of_bus]
    if len(labels) != len(bus_ids):
        raise ValueError(
            f"zone_of_bus has {len(labels)} entries but the network has {len(bus_ids)} buses -- "
            "a positional zone_of_bus must be in NetworkArrays bus order, one label per bus"
        )
    return labels


def _normalise_corridors(
    corridors: Mapping[ZoneKey, float], zone_ids: Sequence[str]
) -> dict[ZoneKey, float]:
    """``corridors`` with every key sorted (``z1 < z2``), validated against the zone partition.

    Rejects, in each case naming the offending key: a key that is not a pair of two distinct zone
    ids; a zone id no bus is assigned to (a corridor to nowhere, whose column would enter only one
    balance row and so act as an unbounded free source of power in it); the same unordered pair
    given twice under both orderings (ambiguous -- one corridor or two?); and a cap that is
    negative or not a number. A cap of exactly ``0`` is *allowed*: it is the honest encoding of a
    tie that exists but can carry nothing, and it keeps that corridor's own capacity price readable
    instead of requiring the caller to delete the entry.

    The duplicate guard can only ever see the *reversed* ordering, because ``corridors`` is a
    ``Mapping``: a pair repeated in the same order is one key here, whatever the caller wrote. That
    is not a hole in this function -- it is the shape of its input -- but it is a hole one layer up,
    where the caller writes a *list*, so
    :class:`~mambo_power.market.zonal.MarketZonalOptions` rejects the repeat on the list before it
    is ever collapsed into a mapping.
    """
    known = set(zone_ids)
    out: dict[ZoneKey, float] = {}
    for key, cap in corridors.items():
        if not isinstance(key, tuple) or len(key) != 2:
            raise ValueError(
                f"corridor key {key!r} is not a (zone1, zone2) pair -- corridors is keyed by "
                "unordered zone pairs"
            )
        z1, z2 = str(key[0]), str(key[1])
        if z1 == z2:
            raise ValueError(
                f"corridor key {key!r} names the same zone twice -- a corridor joins two "
                "*distinct* zones (an intra-zone tie is not modelled: a zone is a copper plate)"
            )
        for zone in (z1, z2):
            if zone not in known:
                raise ValueError(
                    f"corridor key {key!r} names zone {zone!r}, which no bus is assigned to "
                    f"(zones present: {sorted(known)})"
                )
        cap_mw = float(cap)
        if np.isnan(cap_mw):
            raise ValueError(f"corridor {key!r} has a NaN cap -- give a number, 0, or inf")
        if cap_mw < 0.0:
            raise ValueError(
                f"corridor {key!r} has a negative cap {cap_mw!r} -- a transfer capacity is a "
                "magnitude; the corridor's own bounds are the symmetric [-cap, +cap]"
            )
        ordered: ZoneKey = (z1, z2) if z1 < z2 else (z2, z1)
        if ordered in out:
            raise ValueError(
                f"zone pair {ordered!r} appears twice in corridors (once as {key!r}) -- a corridor "
                "is keyed by an *unordered* pair, so give it exactly once"
            )
        out[ordered] = cap_mw
    return dict(sorted(out.items()))


def _corridor_cap_price(reduced_cost: FloatArray) -> FloatArray:
    """The capacity shadow price of each corridor, from that column's own reduced cost.

    A corridor column ``f`` is bounded ``[-cap, +cap]`` and carries no objective coefficient, so
    HiGHS's reduced cost for it is ``d = -lambda^T A_f`` -- the negated price difference across the
    corridor. For a minimisation, ``d <= 0`` at the upper bound, ``d >= 0`` at the lower, and
    ``d == 0`` strictly inside. Raising the **capacity** by ``delta`` moves whichever bound is
    active outward: at the upper bound ``f`` rises by ``delta`` and the objective changes by
    ``d*delta <= 0``; at the lower bound ``f`` falls by ``delta`` and the objective changes by
    ``-d*delta <= 0``. Either way the objective improves by ``|d|*delta``, so the capacity price is
    ``|d|`` -- non-negative in both directions and ``0`` on a slack corridor, with no need to
    branch on which bound is active. Returning the raw signed reduced cost instead would make the
    field's meaning depend on the corridor key's alphabetical ordering, which is an artifact of
    zone naming rather than of the market.
    """
    return np.abs(np.asarray(reduced_cost, dtype=np.float64))


def zonal_dc_opf(
    arr: NetworkArrays,
    cost_coeffs: FloatArray,
    zone_of_bus: Mapping[str, str] | Sequence[str],
    corridors: Mapping[ZoneKey, float],
    *,
    pwl_costs: Mapping[int, Sequence[tuple[float, float]]] | None = None,
    demand_bid_coeffs: Mapping[int, tuple[float, float, float]] | None = None,
    demand_pwl_bids: Mapping[int, Sequence[tuple[float, float]]] | None = None,
) -> ZonalSolution:
    """Clear ``arr`` at zonal granularity (module docstring): minimise ``sum cost(p_g) - sum
    value(p_d)`` subject to one balance row **per zone**, coupled only by one bounded exchange
    column per tied zone-pair -- no branch flow rows anywhere.

    ``cost_coeffs`` is ``(n_gen, 3)``, columns ``[c2, c1, c0]``, generator order, and it,
    ``pwl_costs``, ``demand_bid_coeffs`` and ``demand_pwl_bids`` are exactly
    :func:`~mambo_power.opf.dc_opf.dc_opf`'s, validated by the very same
    :func:`~mambo_power.opf.dc_opf._extract_and_validate` -- so
    :class:`~mambo_power.opf.dc_opf.NonConvexCostError` and
    :class:`~mambo_power.opf.dc_opf.NonConcaveBidError` are raised here on the same inputs, and
    before any HiGHS object exists. ``zone_of_bus`` is either a ``{bus id: zone id}`` mapping or a
    positional sequence of labels in ``NetworkArrays`` bus order; every bus must carry a zone.
    ``corridors`` maps an unordered zone pair to that corridor's transfer capacity in MW; keys are
    normalised to sorted order and caps must be non-negative (``0`` and ``inf`` both allowed).

    A single zone with no corridors is a legitimate solve, not a degenerate case to guard against:
    it is the same LP :func:`~mambo_power.opf.dc_opf.dc_opf` builds for an unrated network (module
    docstring, "Degenerate case").

    Raises :class:`ValueError` for a malformed partition or corridor map (:func:`_zone_labels`,
    :func:`_normalise_corridors`). Never raises for an infeasible or unbounded model -- reported
    through ``status``/``message``, mirroring ``dc_opf``.
    """
    n_gen = len(arr.gen_ids)
    n_load = len(arr.load_ids)
    problem = _extract_and_validate(
        cost_coeffs, pwl_costs, demand_bid_coeffs, demand_pwl_bids, n_gen, n_load
    )
    c2, c1, c0 = problem.c2, problem.c1, problem.c0
    v1, v2 = problem.v1, problem.v2
    elastic_load_idxs = problem.elastic_load_idxs
    n_pwl, n_demand, n_demand_pwl = problem.n_pwl, problem.n_demand, problem.n_demand_pwl

    bus_zone = _zone_labels(zone_of_bus, arr.bus_ids)
    zone_ids = sorted(set(bus_zone))
    corridor_caps = _normalise_corridors(corridors, zone_ids)
    corridor_ids = list(corridor_caps)
    n_zone, n_corridor = len(zone_ids), len(corridor_ids)
    zone_pos = {zone: i for i, zone in enumerate(zone_ids)}
    bus_zone_idx = np.asarray([zone_pos[z] for z in bus_zone], dtype=np.int64)

    n_dispatch = n_gen + n_demand
    demand_col_of = {idx: n_gen + j for j, idx in enumerate(elastic_load_idxs)}

    h = highspy.Highs()  # type: ignore[no-untyped-call]  # highspy ships no type stubs
    h.setOptionValue("output_flag", False)

    # --- tier 1a: generator and elastic-demand dispatch columns, exactly dc_opf's own block.
    if n_gen:
        h.addVars(n_gen, arr.gen_p_min_pu * arr.base_mva, arr.gen_p_max_pu * arr.base_mva)
        h.changeColsCost(n_gen, np.arange(n_gen, dtype=np.int32), c1)
    elastic_idx_arr = np.asarray(elastic_load_idxs, dtype=np.int64)
    if n_demand:
        h.addVars(
            n_demand,
            arr.load_p_min_pu[elastic_idx_arr] * arr.base_mva,
            arr.load_p_max_pu[elastic_idx_arr] * arr.base_mva,
        )
        # minimising sum cost_g - sum value_d puts -v1 on the demand column (dc_opf, "Elastic
        # demand").
        h.changeColsCost(n_demand, np.arange(n_gen, n_dispatch, dtype=np.int32), -v1)

    # Hessian over the dispatch prefix, passed *before* any further column is appended -- the
    # ordering dc_opf already proves safe against later addVars calls (module docstring). The
    # assembly itself is dc_opf's helper, not a copy of it (ADR-008 one level down).
    _pass_diagonal_hessian(h, c2, v2, n_gen, n_demand)

    # --- tier 1b: one exchange column per corridor, bounded [-cap, +cap] (module docstring,
    # "Corridor sign convention"). No objective coefficient: a transfer is neither a cost nor a
    # value, and every economic consequence of moving power between zones is already carried by
    # the two balance rows the column appears in.
    corridor_cols = np.arange(n_dispatch, n_dispatch + n_corridor, dtype=np.int32)
    if n_corridor:
        caps = np.asarray(list(corridor_caps.values()), dtype=np.float64)
        caps = np.where(np.isinf(caps), highspy.kHighsInf, caps)
        h.addVars(n_corridor, -caps, caps)
    n_tier1 = n_dispatch + n_corridor

    # --- tier 2: the free PWL cost_g / val_d columns, appended after every tier-1 column exactly
    # as dc_opf appends them after its own dispatch block.
    cost_col_of: dict[int, int] = {}
    if n_pwl:
        cost_cols = np.arange(n_tier1, n_tier1 + n_pwl, dtype=np.int32)
        h.addVars(n_pwl, np.full(n_pwl, -highspy.kHighsInf), np.full(n_pwl, highspy.kHighsInf))
        h.changeColsCost(n_pwl, cost_cols, np.ones(n_pwl))
        cost_col_of = dict(zip(problem.pwl_gen_idxs, cost_cols.tolist(), strict=True))
    demand_val_col_of: dict[int, int] = {}
    if n_demand_pwl:
        val_cols = np.arange(n_tier1 + n_pwl, n_tier1 + n_pwl + n_demand_pwl, dtype=np.int32)
        h.addVars(
            n_demand_pwl,
            np.full(n_demand_pwl, -highspy.kHighsInf),
            np.full(n_demand_pwl, highspy.kHighsInf),
        )
        h.changeColsCost(n_demand_pwl, val_cols, -np.ones(n_demand_pwl))
        demand_val_col_of = dict(zip(problem.demand_pwl_idxs, val_cols.tolist(), strict=True))

    # --- per-zone fixed right-hand sides. The same double-counting contract dc_opf carries: each
    # elastic load's own historical p_mw (== arr.load_p_max_pu at its index) comes off its own
    # bus before that bus is aggregated into its zone, so the caller passes arr unmodified here too.
    p_load_mw = arr.p_load_pu * arr.base_mva
    if n_demand:
        p_load_mw = p_load_mw - np.bincount(
            arr.load_bus[elastic_idx_arr],
            weights=arr.load_p_max_pu[elastic_idx_arr] * arr.base_mva,
            minlength=arr.n_bus,
        )
    fixed_bus_mw = p_load_mw + arr.g_shunt_pu * arr.base_mva
    fixed_zone_mw = np.bincount(bus_zone_idx, weights=fixed_bus_mw, minlength=n_zone)

    # --- one balance row per zone, row index == that zone's position in zone_ids. Built by
    # dc_opf's own _balance_row against this zone's own column sets: its generators and inbound
    # corridors inject, its bid loads and outbound corridors withdraw.
    gen_zone = bus_zone_idx[arr.gen_bus] if n_gen else np.zeros(0, dtype=np.int64)
    demand_zone = (
        bus_zone_idx[arr.load_bus[elastic_idx_arr]] if n_demand else np.zeros(0, dtype=np.int64)
    )
    inbound: list[list[int]] = [[] for _ in zone_ids]
    outbound: list[list[int]] = [[] for _ in zone_ids]
    for c, (z1, z2) in enumerate(corridor_ids):
        outbound[zone_pos[z1]].append(int(corridor_cols[c]))  # positive f leaves z1 ...
        inbound[zone_pos[z2]].append(int(corridor_cols[c]))  # ... and arrives in z2
    for z in range(n_zone):
        gen_cols_z = np.flatnonzero(gen_zone == z).astype(np.int32)
        demand_cols_z = (np.flatnonzero(demand_zone == z) + n_gen).astype(np.int32)
        _add_rows(
            h,
            _balance_row(
                np.concatenate([gen_cols_z, np.asarray(inbound[z], dtype=np.int32)]),
                np.concatenate([demand_cols_z, np.asarray(outbound[z], dtype=np.int32)]),
                float(fixed_zone_mw[z]),
            ),
        )

    # PWL epigraph / hypograph rows, appended after every balance row so the zone rows keep row
    # indices 0..n_zone-1 (module docstring, "Row layout").
    gen_cols = np.arange(n_gen, dtype=np.int32)
    _add_rows(h, _epigraph_rows(problem.segments_by_gen, gen_cols, cost_col_of))
    _add_rows(h, _hypograph_rows(problem.demand_segments_by_load, demand_col_of, demand_val_col_of))

    # The row-order contract is declared in the module docstring's "Row layout", implemented just
    # above, and re-derived here as a hand-maintained sum. Nothing else ties those three together:
    # ``zone_price`` below is ``row_dual[:n_zone]``, so a row family appended *before* the epigraph
    # block -- or a balance row not built for some zone -- silently reassigns every zone's price.
    # The PWL blocks are conditionally present, which is exactly when a slice-by-contract goes
    # wrong for one caller and not another. M5's own equivalent assert (opf/multiperiod.py) was
    # measured to be the only guard on its layout; this is the same guard for this one.
    n_epigraph = sum(len(segs) for segs in problem.segments_by_gen.values())
    n_hypograph = sum(len(segs) for segs in problem.demand_segments_by_load.values())
    expected_rows = n_zone + n_epigraph + n_hypograph
    assert h.getNumRow() == expected_rows, (
        f"zonal_dc_opf built {h.getNumRow()} rows, but the row-order contract in this module's "
        f"docstring accounts for {expected_rows} — the zone prices are read off that contract as "
        "row_dual[:n_zone], so they must agree"
    )

    h.run()
    status = h.modelStatusToString(h.getModelStatus())
    if status != _OPTIMAL:
        return ZonalSolution(
            status=status,
            zone_ids=zone_ids,
            corridor_ids=corridor_ids,
            dispatch_mw=np.zeros(n_gen),
            demand_dispatch_mw=np.zeros(n_demand),
            demand_bound=np.zeros(n_demand),
            corridor_flow_mw=np.zeros(n_corridor),
            objective_cost=0.0,
            duals=None,
            message=f"zonal_dc_opf: HiGHS reported model status {status!r}",
        )

    sol = h.getSolution()
    dispatch_mw = np.asarray(sol.col_value[:n_gen], dtype=np.float64)
    duals = ZonalDuals(
        zone_price=np.asarray(sol.row_dual[:n_zone], dtype=np.float64),
        corridor_cap=_corridor_cap_price(
            np.asarray(sol.col_dual[n_dispatch:n_tier1], dtype=np.float64)
        ),
        gen_bound=np.asarray(sol.col_dual[:n_gen], dtype=np.float64),
    )

    # generation cost only, computed from the dispatch rather than read off HiGHS's own objective
    # -- the identical construction, and the identical reason, as OpfSolution.objective_cost.
    poly_gen_cost = float(np.sum(c2 * dispatch_mw**2 + c1 * dispatch_mw + c0))
    pwl_gen_cost = float(sum(sol.col_value[cost_col_of[i]] for i in problem.pwl_gen_idxs))
    return ZonalSolution(
        status=status,
        zone_ids=zone_ids,
        corridor_ids=corridor_ids,
        dispatch_mw=dispatch_mw,
        demand_dispatch_mw=np.asarray(sol.col_value[n_gen:n_dispatch], dtype=np.float64),
        demand_bound=np.asarray(sol.col_dual[n_gen:n_dispatch], dtype=np.float64),
        corridor_flow_mw=np.asarray(sol.col_value[n_dispatch:n_tier1], dtype=np.float64),
        objective_cost=poly_gen_cost + pwl_gen_cost,
        duals=duals,
        message=None,
    )
