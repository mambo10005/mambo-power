"""``market.zonal`` clearing: zonal market, min-cost redispatch, nodal reference — and what the
distance between them costs (wave M6 W4/W5, spec AC-4/AC-5).

:func:`solve_zonal` is the third ``Scenario``-facing market entry point, at exactly the altitude
:func:`~mambo_power.market.nodal.solve_nodal` and
:func:`~mambo_power.market.multiperiod.solve_multiperiod` sit at: model-side extraction and
settlement over array-level builders that do the numerics. Nothing here builds a row or a column.
What is new is that it drives **three** solves instead of one, and that its result is their
relationship rather than any one of them.

**The chain, in order, and why each stage is there.**

1. **Zones off the model.** ``Bus.zone`` and ``net.zones`` have been schema-present since M1 and
   are populated by every MATPOWER import; this is where they finally become solver input. The
   partition is read, never derived: a bus with no zone is an error, because there is no
   defensible default for whose balance row its load belongs in.
2. **Zonal clearing** — :func:`~mambo_power.opf.zonal.zonal_dc_opf` on that partition and the
   caller's corridor capacities. One price per zone, the intra-zone grid ignored, inter-zonal
   exchange bounded by one corridor variable per tied zone pair (design decision D2, b2). This is
   the market the participants actually clear in, and its schedule is generally **not** something
   the real network can carry.
3. **Min-cost redispatch** — :func:`~mambo_power.opf.redispatch.redispatch_dc_opf` from that
   schedule, with the **true** cost and bid curves in the objective (design decision D1) and the
   real PTDF flow rows reinstated. This is the operator's action after the market closes.
4. **The nodal reference** — :func:`~mambo_power.market.nodal.solve_nodal` on the *same*
   scenario. It is the yardstick, and it is a genuinely separate solve rather than a quantity
   inferred from stage 3, precisely because stage 3's agreement with it is the thing AC-4 asserts.
   Inferring the reference from the thing being tested would make that assertion vacuous.
5. **Composition** into :class:`~mambo_power.results.MarketZonalResult`.

**Why stage 4 is not redundant, even though D1 makes it predictable.** Under D1 the redispatch
objective is the true welfare function over nodal's exact feasible set, so the redispatched point
*is* the nodal optimum — :attr:`~mambo_power.results.MarketZonalResult.welfare_gap` is ``0`` by
theorem. That makes stage 4 a **check** on the chain rather than a source of new information, and
a check is worth its solve: it is the one thing that would notice if the redispatch LP's feasible
set quietly stopped being nodal's. It also supplies the reference welfare and generation cost
that the other two figures are measured against.

**Where each of the three figures comes from, computed one way.** Welfare figures are needed at
three different points — the zonal schedule, the final schedule and the nodal optimum — and only
some of them are reported by the solve that produced them (:class:`~mambo_power.opf.zonal.
ZonalSolution` has a generation cost but no demand value; :class:`~mambo_power.results.
MarketNodalResult` has neither). Rather than mix reported figures with derived ones, this module
evaluates the **true** cost and bid curves itself at all three points, through the one pair of
helpers :func:`_generation_cost` / :func:`_demand_value`, so that every difference taken below is
like-for-like. Those helpers are an independent evaluation path from the LPs' own epigraph/
hypograph encoding, and ``tests/unit/test_market_zonal.py`` asserts they agree with
:attr:`~mambo_power.opf.redispatch.RedispatchSolution.objective_cost` /
:attr:`~mambo_power.opf.redispatch.RedispatchSolution.demand_value` — an agreement between two
constructions, not a tautology.

* ``redispatch_payment = [cost(final) - cost(zonal)] + [value(d_zonal) - value(d_final)]`` — the
  settlement figure spec ``## Design`` A5 names: extra generation cost plus curtailment
  compensation at bid value. Algebraically identical to ``welfare(zonal) - welfare(final)``, which
  is why it is non-negative wherever the zonal LP is a relaxation of the nodal one: it is exactly
  the welfare the zonal clearing promised and the network could not deliver.
* ``welfare_gap = welfare(nodal) - welfare(final)`` — the exactness row; ``0`` by D1.
* ``generation_cost_gap = cost(zonal) - cost(nodal)`` — the unsigned diagnostic.

**The three are two quantities and a combination, and the combination is worth naming.** Under D1
``cost(final) == cost(nodal)``, so with ``A = cost(final) - cost(zonal)`` and
``B = value(d_zonal) - value(d_final)`` the three fields are ``A + B``, ``0`` and ``-A``. Hence

    ``redispatch_payment + generation_cost_gap == value(d_zonal) - value(d_final)``

exactly: adding the diagnostic to the settlement cancels the generation-cost term and leaves the
**curtailment compensation** on its own. That is the whole of what the third field adds — on a
network where no load carries a bid curve it is identically zero and ``generation_cost_gap`` is
precisely ``-redispatch_payment``, while on rated case30 with bids it is 0.94 of a 14.51 $/h
payment. Read the pair that way and the fields stop looking redundant; read them as three
independent numbers and a sign flip will pass for information.

**A note on the third figure's definition.** The wave's research (§6) defined
``generation_cost_gap`` as ``cost(final) - cost(nodal)``, which was the informative quantity under
the *anchored-rate* redispatch objective it assumed (§3a) — that objective lands somewhere other
than nodal, and §4(b) worked an example where it lands at strictly lower generation cost while
destroying welfare. Design decision D1 rejected the anchored rate (spec ``## Rejected
alternatives``; plan A17), and under true curves ``cost(final) - cost(nodal)`` is identically
zero: the same theorem that makes ``welfare_gap`` zero makes it zero, so it would be a second copy
of the exactness row rather than the diagnostic the spec asks for. The quantity that survives D1
is the **zonal** point's cost against nodal's, and it survives with §4(b)'s reasoning intact and
assumption-free: welfare is what the relaxation argument orders, generation cost is not, so a
zonal clearing can be welfare-better and generation-cost-cheaper or dearer than nodal. That is the
figure this module reports, and the reason its description insists it is not sign-constrained.

**Never raises for a solve that does not converge.** A non-``Optimal`` stage — zonal, redispatch
or nodal — comes back as ``status`` plus a ``message`` naming that stage, this package's standing
convention. Malformed *input* still raises up front, and **which** exception it raises decides how
a caller of :func:`mambo_power.jobs.run` is told whose mistake it was. A corridor list that is
ambiguous on its own — a self-pair, the same unordered pair twice — is rejected by
:class:`MarketZonalOptions`'s validator before any solve, so it arrives as ``BAD_OPTIONS``. A
corridor naming a zone the network does not have is only detectable once both are in hand, so
:func:`_reject_corridors_naming_absent_zones` raises
:class:`~mambo_power.model.NetworkValidationError` with a ``DANGLING_REF`` issue and it arrives as
``VALIDATION``. A bus with no zone, a non-convex generator cost and a non-concave load bid still
raise their own ``ValueError``/typed errors.
"""

from __future__ import annotations

import time
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime

import numpy as np
from pydantic import BaseModel, ConfigDict, Field, model_validator

import mambo_power
from mambo_power.model import Network, NetworkValidationError, Scenario, ValidationIssue
from mambo_power.numerics.arrays import NetworkArrays
from mambo_power.opf import gen_cost_coeffs
from mambo_power.opf.dc_opf import (
    FloatArray,
    NonConcaveBidError,
    NonConvexCostError,
    lmp_decomposition,
)
from mambo_power.opf.redispatch import RedispatchSolution, redispatch_dc_opf
from mambo_power.opf.zonal import ZonalSolution, ZoneKey, zonal_dc_opf
from mambo_power.results import (
    BusLmpResult,
    GenDispatchResult,
    GenRedispatchResult,
    LoadDispatchResult,
    LoadRedispatchResult,
    MarketZonalResult,
    OpfBranchFlowResult,
    ResultProvenance,
    ZonePriceResult,
)

from mambo_power.market.nodal import load_bid_coeffs, solve_nodal  # isort: skip

MAX_CORRIDORS = 500
"""Upper bound on :attr:`MarketZonalOptions.corridors`' length: a request/response-size guard, not
a solver limit — the same guard :data:`~mambo_power.model.scenario.MAX_PERIODS` puts on
``Scenario.periods``, applied to the other user-supplied list this package takes.

The *honest* bound is the network's own: a partition into ``n`` zones admits at most ``n(n-1)/2``
distinct pairs, and a corridor list longer than that necessarily repeats one (now rejected on its
own). But ``n`` is a property of the network and this is an options model, which has none — so the
bound here is a fixed number chosen to sit above every network anyone clears zonally and below the
sizes that make the *response* a problem. ``corridors`` is echoed verbatim into every result's
``provenance.options``, so the list's length is paid twice, once inbound and once out.

500 covers a 32-zone network exhaustively (496 pairs, measured 22,025 bytes of options JSON), and
32 zones is already above Europe's day-ahead market, the largest zonal design in operation at
around 25 bidding zones. Above it, growth is quadratic and unbounded in an options field: 200
zones is 19,900 corridors and 913,425 bytes echoed back per solve. Review F2 measured 20,000
entries accepted before this bound existed."""

__all__ = [
    "CorridorLimit",
    "MarketZonalOptions",
    "NonConcaveBidError",
    "NonConvexCostError",
    "solve_zonal",
]


class CorridorLimit(BaseModel):
    """One inter-zonal corridor's transfer capacity — an entry of
    :attr:`MarketZonalOptions.corridors`.

    **Why this is an option and not a model field.** A corridor capacity is a transfer limit
    between two *zones*, and the domain model has no transfer-capacity entity: design decision D3
    rejected inventing one, because a real NTC is administratively negotiated data that no
    committed fixture carries and no branch rating uniquely determines. So capacities are supplied
    per solve, by the caller who knows them. ``tests/_zones.py``'s ``corridors()`` derives a
    defensible test-time set (the sum of ``rating_mva`` over the pair's cut-set) and is the
    fixture half of the wave's acceptance criteria.

    **Why a row model rather than a ``{(z1, z2): cap}`` mapping.** The mapping is the shape the
    array-level builder takes and the shape :meth:`MarketZonalOptions.corridor_map` hands it. It
    is not a shape a pydantic options model can carry, because a ``dict`` keyed by a tuple does
    not survive a JSON round trip: pydantic serialises the key ``("1", "2")`` to the string
    ``"1,2"`` and then refuses to validate that string back into a tuple. An options model that
    cannot round-trip through JSON is a ``jobs`` request form that cannot round-trip either (the
    epic's ``jobs`` criterion is exact JSON round-trip on every kind), so the serialisable shape
    is the one stored and the mapping is derived on the way to the builder.
    """

    model_config = ConfigDict(
        extra="forbid", frozen=True, allow_inf_nan=True, ser_json_inf_nan="constants"
    )
    """The one model in this package that does **not** set ``allow_inf_nan=False``, and the reason
    is :attr:`cap_mw`'s alone.

    Everywhere else a non-finite float is meaningless — an infinite ``base_kv`` or ``p_max_mw``
    describes nothing — so the package refuses them at the wire. An infinite *transfer capacity*
    does describe something, and something the array level already accepts and the manual already
    teaches: the **copper plate**, a corridor left in place with its bound lifted, which is not the
    same market as deleting the corridor (that islands the zones). Before this, the two layers
    disagreed — :func:`~mambo_power.opf.zonal.zonal_dc_opf`'s own guard says "give a number, 0, or
    inf" and maps ``inf`` to ``kHighsInf``, while this model rejected it with ``finite_number`` and
    left ``solve_zonal`` unable to express the copper plate at all (walk defect D3, review C12).
    This model is now the one that yields.

    ``allow_inf_nan`` is a model-wide switch, but the *scoping* is done by ``cap_mw``'s own
    ``ge=0.0``, which rejects ``-inf`` and ``NaN`` (a ``NaN`` comparison is false), so ``+inf`` is
    the only non-finite value that gets through — and ``zone1``/``zone2`` are strings.

    ``ser_json_inf_nan="constants"`` writes it as the bare token ``Infinity``, which is what
    :func:`json.dumps` emits and :func:`json.loads` accepts, so ``run_json``'s output stays
    readable by the standard library and by pydantic. It is a JSON *extension*, not RFC 8259 — a
    browser's ``JSON.parse`` will reject it — so a caller who needs strict JSON should send a large
    finite cap instead. The default (``"null"``) was not an option: it serialises the cap to
    ``null`` and then refuses to read it back, which is a one-way round trip that looks fine until
    something reads it.
    """

    zone1: str = Field(
        description="One end of the corridor: a zone id present in the network. A zone id no bus "
        "carries is rejected at solve time, when the network is in hand (jobs: VALIDATION)."
    )
    zone2: str = Field(
        description="The other end; must differ from ``zone1``, and the resulting unordered pair "
        "must not appear elsewhere in the list. Both are enforced on MarketZonalOptions itself, "
        "before any solve (jobs: BAD_OPTIONS)."
    )
    cap_mw: float = Field(
        ge=0.0,
        description="Transfer capacity, MW, as a magnitude: the corridor is bounded at "
        "[-cap_mw, +cap_mw], so it constrains both directions equally. ``0`` is allowed and means "
        "a tie that exists but can carry nothing; ``inf`` is allowed and means the copper plate -- "
        "the corridor stays in the LP, with no bound, which is a different market from deleting "
        "the entry (that islands the two zones). ``NaN`` and ``-inf`` are rejected by this field's "
        "own ``ge=0.0``. On the wire an infinite cap is the bare token ``Infinity``, a JSON "
        "extension that json.loads reads and a browser's JSON.parse does not.",
    )


class MarketZonalOptions(BaseModel):
    """Options of a ``market.zonal`` clearing.

    Unlike :class:`~mambo_power.market.nodal.MarketNodalOptions` and
    :class:`~mambo_power.market.multiperiod.MarketMultiperiodOptions`, this one has a field from
    the start, and it is not solver tuning: :attr:`corridors` is *market design data* the model
    deliberately does not carry (see :class:`CorridorLimit`). An empty list is a meaningful
    default and not a missing argument -- it means no zone pair may exchange anything, so each
    zone must supply itself.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    corridors: list[CorridorLimit] = Field(
        default_factory=list,
        max_length=MAX_CORRIDORS,
        description="Transfer capacity per tied zone pair. A pair absent from this list has no "
        "corridor at all and so cannot exchange power -- which is a stronger statement than a "
        "corridor of capacity 0 only in that no capacity shadow price is reported for it. At most "
        "MAX_CORRIDORS (500) entries -- a request/response-size guard, since this list is echoed "
        "verbatim into every result's provenance.options; 500 exhausts a 32-zone network, which is "
        "above every zonal market in operation.",
    )

    @model_validator(mode="after")
    def _each_pair_is_two_distinct_zones_named_once(self) -> MarketZonalOptions:
        """Reject a corridor list whose meaning is not determined by the list itself.

        Two shapes are ambiguous and both used to get through. A **self-pair** contradicts
        :attr:`CorridorLimit.zone2`'s own description ("must differ from ``zone1``") and would only
        surface from the array-level builder at solve time. A **repeated unordered pair** is worse
        in one direction: :meth:`corridor_map` is a dict comprehension, so the same pair given
        twice in the *same* order silently kept the last entry and cleared the market on a capacity
        the caller never asked for, while the reversed order raised — from deep enough that
        ``jobs.run`` classified a caller's typo as an engine bug (review F1, walk D1).

        Checking it here rather than in the builder is what makes it a *request* error: an options
        model validates before any solve, so :func:`mambo_power.jobs.run` reports ``BAD_OPTIONS``
        with pydantic's own details. The third corridor mistake — a zone id the network does not
        have — cannot be checked here, because an options model has no network; it is caught at
        resolution time by :func:`_reject_corridors_naming_absent_zones`.
        """
        seen: dict[ZoneKey, int] = {}
        for index, entry in enumerate(self.corridors):
            if entry.zone1 == entry.zone2:
                raise ValueError(
                    f"corridors[{index}] names the same zone twice ({entry.zone1!r}) -- a corridor "
                    "joins two *distinct* zones; a zone is a copper plate, so an intra-zone tie is "
                    "not a thing this model has"
                )
            key: ZoneKey = (
                (entry.zone1, entry.zone2)
                if entry.zone1 < entry.zone2
                else (entry.zone2, entry.zone1)
            )
            if key in seen:
                raise ValueError(
                    f"zone pair {key!r} appears more than once in corridors (at index {seen[key]} "
                    f"and index {index}) -- a corridor is keyed by an *unordered* pair, so give it "
                    "exactly once, in either order"
                )
            seen[key] = index
        return self

    def corridor_map(self) -> dict[ZoneKey, float]:
        """:attr:`corridors` as the ``{(zone1, zone2): cap_mw}`` mapping
        :func:`~mambo_power.opf.zonal.zonal_dc_opf` takes. Keys are left in the order given; the
        builder normalises each to sorted order. This is a dict comprehension and so cannot report
        a repeated key -- which is exactly why the repeat is rejected on the model above, before
        any mapping is built."""
        return {(entry.zone1, entry.zone2): entry.cap_mw for entry in self.corridors}


def _reject_corridors_naming_absent_zones(
    opts: MarketZonalOptions, partition: Mapping[str, str]
) -> None:
    """Raise :class:`~mambo_power.model.NetworkValidationError` if any corridor names a zone no bus
    is assigned to.

    This is the one corridor mistake :class:`MarketZonalOptions`'s own validator cannot make: it
    is a statement about the *pair* (options, network), and an options model sees only the first
    half. The array-level builder catches it too — :func:`~mambo_power.opf.zonal.zonal_dc_opf`'s
    guard is what a caller driving the arrays directly relies on — but it raises ``ValueError``,
    which :func:`mambo_power.jobs.run`'s boundary can only classify as ``INTERNAL``, i.e. "the
    library has a bug". A caller who fat-fingers a zone name would page the service's on-call
    (walk defect D1). Raised as a network-validation issue instead, it reaches them as
    ``VALIDATION`` with a ``DANGLING_REF`` issue whose ``path`` points at the option that is
    wrong, which is what a dangling reference is.

    Every offending end of every corridor is reported in one pass, following
    :class:`~mambo_power.model.NetworkValidationError`'s own convention of never stopping at the
    first.
    """
    known = set(partition.values())
    issues = [
        ValidationIssue(
            code="DANGLING_REF",
            path=f"options.corridors[{index}].{field}",
            message=f"corridor names zone {zone!r}, which no bus is assigned to (zones present: "
            f"{sorted(known)})",
        )
        for index, entry in enumerate(opts.corridors)
        for field, zone in (("zone1", entry.zone1), ("zone2", entry.zone2))
        if zone not in known
    ]
    if issues:
        raise NetworkValidationError(issues)


def zone_partition(net: Network, arr: NetworkArrays) -> dict[str, str]:
    """``{bus id: zone id}`` for every bus :class:`~mambo_power.numerics.NetworkArrays` keeps,
    read straight off ``Bus.zone``.

    Public for the same reason :func:`~mambo_power.opf.gen_cost_coeffs` and
    :func:`~mambo_power.market.nodal.load_bid_coeffs` are: it is the model-to-solver extraction
    step for one more kind of network data, and a caller driving
    :func:`~mambo_power.opf.zonal.zonal_dc_opf` directly needs exactly this mapping.

    Raises :class:`ValueError` naming the first offending bus if any kept bus has ``zone is
    None``. A partition with a hole has no defensible repair -- that bus's load and generation
    must enter *some* zone's balance row, and choosing one for the caller would clear a market for
    a network they did not describe. (Buses ``NetworkArrays`` drops -- out of service, or on an
    islanded component -- are not consulted: they have no columns and no load in the LP.)
    """
    zone_of = {bus.id: bus.zone for bus in net.buses}
    missing = [bus_id for bus_id in arr.bus_ids if zone_of.get(bus_id) is None]
    if missing:
        raise ValueError(
            f"{len(missing)} of {len(arr.bus_ids)} in-service buses carry no zone (first: "
            f'"{missing[0]}") -- a zonal clearing needs every bus assigned to exactly one zone. '
            "Set Bus.zone (every MATPOWER import populates it from the ZONE column)."
        )
    return {bus_id: str(zone_of[bus_id]) for bus_id in arr.bus_ids}


def _pwl_curve_value(
    points: Sequence[tuple[float, float]], quantity: float, *, convex: bool
) -> float:
    """A piecewise-linear curve's value at ``quantity``, evaluated the way the LP's own rows
    evaluate it.

    :func:`~mambo_power.opf.dc_opf._epigraph_rows` encodes a convex PWL cost as ``cost_g >=
    slope_i * p + intercept_i`` for every segment ``i``, and the free ``cost_g`` column is pushed
    down onto the curve by its ``+1`` objective coefficient -- so at the optimum ``cost_g`` is the
    **maximum** over the segments' affine extensions. :func:`~mambo_power.opf.dc_opf.
    _hypograph_rows` mirrors it for a concave bid, where ``val_d`` is pushed up and lands on the
    **minimum**. Inside the breakpoint range both are ordinary interpolation; outside it they are
    the extension of the nearest segment, which is what the LP does too. Reproducing the encoding
    rather than interpolating keeps this evaluation exact where the LP's is, instead of agreeing
    only on the interior.
    """
    if len(points) < 2:
        raise ValueError(
            f"a piecewise curve needs at least two breakpoints to have a segment, got {points!r}"
        )
    values = []
    for (q_a, y_a), (q_b, y_b) in zip(points, points[1:], strict=False):
        if q_b == q_a:
            continue
        slope = (y_b - y_a) / (q_b - q_a)
        values.append(slope * (quantity - q_a) + y_a)
    return max(values) if convex else min(values)


def _generation_cost(
    cost_coeffs: FloatArray,
    pwl_costs: Mapping[int, Sequence[tuple[float, float]]],
    p_mw: FloatArray,
) -> float:
    """Total true generation cost at the dispatch ``p_mw``, $/h, constants included.

    The same figure :attr:`~mambo_power.opf.dc_opf.OpfSolution.objective_cost` reports, computed
    from the dispatch rather than read off any solver: ``sum(c2*p**2 + c1*p + c0)`` over the
    quadratic generators plus each piecewise-linear generator's own curve value. A PWL
    generator's ``cost_coeffs`` row is all-zero by the builders' shared contract, so it
    contributes to the second sum only.
    """
    p = np.asarray(p_mw, dtype=np.float64)
    coeffs = np.asarray(cost_coeffs, dtype=np.float64)
    total = float(np.sum(coeffs[:, 0] * p**2 + coeffs[:, 1] * p + coeffs[:, 2]))
    for gen_idx, points in pwl_costs.items():
        total += _pwl_curve_value(points, float(p[gen_idx]), convex=True)
    return total


def _demand_value(
    demand_bid_coeffs: Mapping[int, tuple[float, float, float]],
    demand_pwl_bids: Mapping[int, Sequence[tuple[float, float]]],
    d_mw: FloatArray,
    elastic_idxs: Sequence[int],
) -> float:
    """Total true bid value of the served demand ``d_mw``, $/h, constants included -- the
    demand-side mirror of :func:`_generation_cost`, and the same figure
    :attr:`~mambo_power.opf.redispatch.RedispatchSolution.demand_value` reports.

    ``d_mw`` is in ascending bid-index order (``elastic_idxs``), the order every builder in this
    package returns elastic quantities in. A load with no bid contributes nothing: it is not a
    decision variable, and its fixed demand is served identically at every point being compared,
    so including it would add the same constant to both sides of every difference taken from
    these figures.
    """
    slot = {load_idx: j for j, load_idx in enumerate(elastic_idxs)}
    d = np.asarray(d_mw, dtype=np.float64)
    total = 0.0
    for load_idx, (v2, v1, v0) in demand_bid_coeffs.items():
        q = float(d[slot[load_idx]])
        total += v2 * q**2 + v1 * q + v0
    for load_idx, points in demand_pwl_bids.items():
        total += _pwl_curve_value(points, float(d[slot[load_idx]]), convex=False)
    return total


def _dispatch_rows(
    arr: NetworkArrays, p_mw: FloatArray, bound_dual: FloatArray
) -> list[GenDispatchResult]:
    """One :class:`~mambo_power.results.GenDispatchResult` per generator, in
    ``NetworkArrays`` generator order -- :func:`~mambo_power.market.nodal.solve_nodal`'s own row
    construction, shared here because both dispatch layers of this result need it."""
    return [
        GenDispatchResult(
            id=gen_id,
            bus=arr.bus_ids[int(arr.gen_bus[i])],
            p_mw=float(p_mw[i]),
            bound_dual=float(bound_dual[i]),
        )
        for i, gen_id in enumerate(arr.gen_ids)
    ]


def _load_rows(
    net: Network,
    arr: NetworkArrays,
    d_mw: FloatArray,
    bound_dual: FloatArray,
    elastic_idxs: Sequence[int],
) -> list[LoadDispatchResult]:
    """One :class:`~mambo_power.results.LoadDispatchResult` per load, bid or not, in
    ``NetworkArrays`` load order.

    A bid load's served demand comes from the solve's elastic vector; a load with no bid stays at
    its own fixed ``Load.p_mw`` with ``bound_dual`` 0, because it never became an LP column. This
    is :func:`~mambo_power.market.nodal.solve_nodal`'s rule verbatim, and it matters for the same
    reason: the settlement identity sums ``LMP * p_d`` over *every* load.
    """
    slot = {load_idx: j for j, load_idx in enumerate(elastic_idxs)}
    loads_by_id = {ld.id: ld for ld in net.loads}
    rows = []
    for i, load_id in enumerate(arr.load_ids):
        j = slot.get(i)
        p_mw = float(d_mw[j]) if j is not None else float(loads_by_id[load_id].p_mw)
        dual = float(bound_dual[j]) if j is not None else 0.0
        rows.append(
            LoadDispatchResult(
                id=load_id,
                bus=arr.bus_ids[int(arr.load_bus[i])],
                p_mw=p_mw,
                bound_dual=dual,
            )
        )
    return rows


def _redispatch_load_rows(
    net: Network,
    arr: NetworkArrays,
    solution: RedispatchSolution,
    elastic_idxs: Sequence[int],
) -> list[LoadRedispatchResult]:
    """One :class:`~mambo_power.results.LoadRedispatchResult` per load, bid or not. A load with no
    bid is not a decision variable in either stage, so both of its deltas are exactly 0."""
    slot = {load_idx: j for j, load_idx in enumerate(elastic_idxs)}
    rows = []
    for i, load_id in enumerate(arr.load_ids):
        j = slot.get(i)
        restore = float(solution.demand_delta_up_mw[j]) if j is not None else 0.0
        curtail = float(solution.demand_delta_down_mw[j]) if j is not None else 0.0
        rows.append(
            LoadRedispatchResult(
                id=load_id,
                bus=arr.bus_ids[int(arr.load_bus[i])],
                delta_restore_mw=restore,
                delta_curtail_mw=curtail,
            )
        )
    return rows


def _nodal_quantities(
    net: Network,
    arr: NetworkArrays,
    generators: Sequence[GenDispatchResult],
    loads: Sequence[LoadDispatchResult],
    elastic_idxs: Sequence[int],
) -> tuple[FloatArray, FloatArray]:
    """The nodal reference's ``(p_mw, d_mw)`` as arrays in the builders' own orders.

    :class:`~mambo_power.results.MarketNodalResult` reports id-keyed rows, and the figures below
    are computed against ``NetworkArrays``-ordered arrays, so the rows are gathered **by id**
    rather than by position -- the two orders happen to coincide today, and a comparison this
    result's whole content rests on should not be silently load-bearing on that.
    """
    p_by_id = {row.id: row.p_mw for row in generators}
    d_by_id = {row.id: row.p_mw for row in loads}
    p_mw = np.array([p_by_id[gen_id] for gen_id in arr.gen_ids], dtype=np.float64)
    d_mw = np.array([d_by_id[arr.load_ids[i]] for i in elastic_idxs], dtype=np.float64)
    return p_mw, d_mw


def solve_zonal(scenario: Scenario, options: MarketZonalOptions | None = None) -> MarketZonalResult:
    """Clear ``scenario.network`` zonally, redispatch it onto the real network, and compare the
    result against the nodal optimum (module docstring).

    ``options.corridors`` supplies each tied zone pair's transfer capacity; the zone partition is
    read from ``Bus.zone``. With no corridors at all, every zone must supply itself -- a
    legitimate (and often infeasible) market design, not an error.

    Never raises for an infeasible or unbounded stage -- reported through
    ``MarketZonalResult.status``/``message``, naming the stage. Raises :class:`ValueError` for a
    bus with no zone or a malformed corridor list, :class:`~mambo_power.opf.dc_opf.
    NonConvexCostError` / :class:`~mambo_power.opf.dc_opf.NonConcaveBidError` for a cost or bid
    curve the shared extractor rejects -- all before any solve is attempted. The network is not
    modified.
    """
    opts = options if options is not None else MarketZonalOptions()
    started_at = datetime.now(UTC)
    clock = time.perf_counter()
    net = scenario.network
    arr = NetworkArrays.from_network(net)
    cost_coeffs, pwl_costs = gen_cost_coeffs(net, arr)
    demand_bid_coeffs, demand_pwl_bids = load_bid_coeffs(net, arr)
    elastic_idxs = sorted(set(demand_bid_coeffs) | set(demand_pwl_bids))
    partition = zone_partition(net, arr)
    _reject_corridors_naming_absent_zones(opts, partition)
    corridor_caps = opts.corridor_map()

    def _provenance() -> ResultProvenance:
        return ResultProvenance(
            engine="mambo-power",
            version=mambo_power.__version__,
            kind="market.zonal",
            solver="highspy.Highs",
            started_at=started_at,
            elapsed_s=time.perf_counter() - clock,
            options=opts.model_dump(),
        )

    # --- stage 2: the zonal clearing.
    zonal: ZonalSolution = zonal_dc_opf(
        arr,
        cost_coeffs,
        partition,
        corridor_caps,
        pwl_costs=pwl_costs or None,
        demand_bid_coeffs=demand_bid_coeffs or None,
        demand_pwl_bids=demand_pwl_bids or None,
    )
    if zonal.status != "Optimal" or zonal.duals is None:
        return MarketZonalResult(
            provenance=_provenance(),
            status=zonal.status,
            message=f"zonal clearing stage: {zonal.message}",
        )

    # --- stage 3: min-cost redispatch from the zonal point onto the real network.
    final: RedispatchSolution = redispatch_dc_opf(
        arr,
        cost_coeffs,
        zonal.dispatch_mw,
        zonal.demand_dispatch_mw,
        pwl_costs=pwl_costs or None,
        demand_bid_coeffs=demand_bid_coeffs or None,
        demand_pwl_bids=demand_pwl_bids or None,
    )
    if final.status != "Optimal" or final.duals is None:
        return MarketZonalResult(
            provenance=_provenance(),
            status=final.status,
            message=f"redispatch stage: {final.message}",
        )

    # --- stage 4: the nodal reference, a separate solve on the same scenario (module docstring).
    nodal = solve_nodal(scenario)
    if nodal.status != "Optimal":
        return MarketZonalResult(
            provenance=_provenance(),
            status=nodal.status,
            message=f"nodal reference stage: {nodal.message}",
        )

    # --- stage 5: compose. Every welfare figure below is evaluated on the true curves by the one
    # pair of helpers, at all three points, so the differences are like-for-like.
    p_nodal, d_nodal = _nodal_quantities(net, arr, nodal.generators, nodal.loads, elastic_idxs)
    cost_zonal = _generation_cost(cost_coeffs, pwl_costs, zonal.dispatch_mw)
    value_zonal = _demand_value(
        demand_bid_coeffs, demand_pwl_bids, zonal.demand_dispatch_mw, elastic_idxs
    )
    cost_final = _generation_cost(cost_coeffs, pwl_costs, final.dispatch_mw)
    value_final = _demand_value(
        demand_bid_coeffs, demand_pwl_bids, final.demand_dispatch_mw, elastic_idxs
    )
    cost_nodal = _generation_cost(cost_coeffs, pwl_costs, p_nodal)
    value_nodal = _demand_value(demand_bid_coeffs, demand_pwl_bids, d_nodal, elastic_idxs)

    redispatch_payment = (cost_final - cost_zonal) + (value_zonal - value_final)
    welfare_gap = (value_nodal - cost_nodal) - (value_final - cost_final)
    generation_cost_gap = cost_zonal - cost_nodal

    lmp = lmp_decomposition(final.duals, final.ptdf)
    return MarketZonalResult(
        provenance=_provenance(),
        status="Optimal",
        message=None,
        zones=[
            ZonePriceResult(id=zone_id, price=float(zonal.duals.zone_price[z]))
            for z, zone_id in enumerate(zonal.zone_ids)
        ],
        generators=_dispatch_rows(arr, zonal.dispatch_mw, zonal.duals.gen_bound),
        loads=_load_rows(net, arr, zonal.demand_dispatch_mw, zonal.demand_bound, elastic_idxs),
        redispatch_generators=[
            GenRedispatchResult(
                id=gen_id,
                bus=arr.bus_ids[int(arr.gen_bus[i])],
                delta_up_mw=float(final.delta_up_mw[i]),
                delta_down_mw=float(final.delta_down_mw[i]),
            )
            for i, gen_id in enumerate(arr.gen_ids)
        ],
        redispatch_loads=_redispatch_load_rows(net, arr, final, elastic_idxs),
        generators_final=_dispatch_rows(arr, final.dispatch_mw, final.duals.gen_bound),
        loads_final=_load_rows(
            net, arr, final.demand_dispatch_mw, final.demand_bound, elastic_idxs
        ),
        branches=[
            OpfBranchFlowResult(
                id=branch_id,
                from_bus=arr.bus_ids[int(arr.f[k])],
                to_bus=arr.bus_ids[int(arr.t[k])],
                p_from_mw=float(final.branch_flow_mw[k]),
                flow_limit_dual=float(final.duals.flow_limit[k]),
            )
            for k, branch_id in enumerate(arr.branch_ids)
        ],
        buses=[
            BusLmpResult(
                id=bus_id,
                lmp=float(lmp.lmp[i]),
                energy=float(lmp.energy[i]),
                congestion=float(lmp.congestion[i]),
            )
            for i, bus_id in enumerate(arr.bus_ids)
        ],
        redispatch_payment=redispatch_payment,
        welfare_gap=welfare_gap,
        generation_cost_gap=generation_cost_gap,
    )
