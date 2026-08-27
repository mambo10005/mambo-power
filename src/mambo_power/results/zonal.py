""":func:`~mambo_power.market.zonal.solve_zonal`'s result: a zonal clearing, the redispatch that
makes it network-feasible, and what the pair costs against the nodal optimum (wave M6 W4, D4).

The third market result type, and shaped like the other two: id-keyed rows plus
:class:`~mambo_power.results.provenance.ResultProvenance`, never attached to a
:class:`~mambo_power.model.Network`, every row model ``extra="forbid"``/``frozen=True``/
``allow_inf_nan=False``. :class:`~mambo_power.results.opf.GenDispatchResult`,
:class:`~mambo_power.results.market.LoadDispatchResult`,
:class:`~mambo_power.results.opf.BusLmpResult` and
:class:`~mambo_power.results.opf.OpfBranchFlowResult` are reused **verbatim** (ADR-006's reuse
discipline); only the zone-price row, the two delta rows and the three gap figures are new.

**Two layers, both reported.** ``market.zonal`` runs three solves — a zonal clearing, a min-cost
redispatch from that clearing's point, and ``market.nodal`` as the reference — and its content is
their *relationship*, so a result that reported only the final point would have thrown away the
comparison it exists to make. Hence the two dispatch layers: :attr:`~MarketZonalResult.generators`
/ :attr:`~MarketZonalResult.loads` carry the **zonal** clearing's own schedule (what the market
sold), :attr:`~MarketZonalResult.generators_final` / :attr:`~MarketZonalResult.loads_final` carry
the **redispatched** one (what the network actually delivers), and
:attr:`~MarketZonalResult.redispatch_generators` /
:attr:`~MarketZonalResult.redispatch_loads` carry the move between them, per participant and per
direction.

**The first market result carrying branch rows.** ``MarketNodalResult`` and
``MarketPeriodResult`` carry prices and quantities but no per-branch surface, so the settlement
identity's flow-dual side (``-sum_k mu_k * f_k``) could not be recomputed from either object —
wave M5's carry-over A23. :attr:`MarketZonalResult.branches` closes that: with
``p_from_mw`` and ``flow_limit_dual`` per branch alongside the per-bus LMPs and the final
dispatch, **both** sides of the identity are computable from this object alone, with no second
solve. ``tests/unit/test_market_zonal.py`` proves exactly that, in a test that imports nothing
from :mod:`mambo_power.numerics` or :mod:`mambo_power.opf`.

**Three separated figures, and why separating them is the point.** The wave's own research (§4b)
established that welfare and generation cost order *differently* between a zonal clearing and the
nodal optimum, and that a result type conflating them would let a reader draw the wrong
conclusion from either. So there are three fields, not one:

* :attr:`~MarketZonalResult.redispatch_payment` — a **settlement** figure: what the operator pays
  out to move from the sold schedule to the deliverable one.
* :attr:`~MarketZonalResult.welfare_gap` — the **exactness** row: ``0`` by design decision D1's
  theorem, and therefore a check on the chain rather than a measurement of it.
* :attr:`~MarketZonalResult.generation_cost_gap` — a **diagnostic**, explicitly not
  sign-constrained.

Each field's own description says which of the three it is.

**How the three relate, stated so a reader does not have to derive it.** They are two independent
quantities and a combination, not three independent ones. Writing ``A = cost_final − cost_zonal``
and ``B = value_zonal − value_final``, the fields are ``A + B``, ``0`` and ``−A``, so

    ``redispatch_payment + generation_cost_gap == value_zonal − value_final``

exactly — the **curtailment compensation**, the bid value elastic demand was scheduled and did not
receive. On a network with no bid curves it is identically zero and ``generation_cost_gap`` is
exactly ``−redispatch_payment``; on one with elastic demand it is the whole of what the third field
adds (measured: 0.94 of a 14.51 $/h payment on rated case30). The identity is asserted in
``tests/unit/test_market_zonal.py`` on both a bid fixture and its fixed-load pair.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from mambo_power.results.market import LoadDispatchResult
from mambo_power.results.opf import BusLmpResult, GenDispatchResult, OpfBranchFlowResult
from mambo_power.results.provenance import ResultProvenance


class _Row(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, allow_inf_nan=False)


class ZonePriceResult(_Row):
    """One zone's clearing price in the zonal stage.

    The price is that zone's own balance-row dual in the zonal LP
    (:attr:`~mambo_power.opf.zonal.ZonalDuals.zone_price`), which the wave's ownership table names
    as the single source of truth for the "zone price" concept. It is emphatically **not** an
    average or a rollup of the bus LMPs in :attr:`MarketZonalResult.buses`: those are the *final*,
    post-redispatch nodal prices, and the whole content of a nodal-versus-zonal comparison is that
    the two disagree. Two zones joined by a corridor that does not bind necessarily price
    identically; prices separate exactly where a corridor binds, and by that corridor's own
    capacity shadow price.
    """

    id: str = Field(description="Zone id from the network (``Zone.id`` / ``Bus.zone``).")
    price: float = Field(
        description="Zonal clearing price, $/MWh: this zone's own balance-row dual in the zonal "
        "clearing LP. One price for the whole zone, by construction -- that is what makes it a "
        "zonal market."
    )


class GenRedispatchResult(_Row):
    """One generator's move from the zonal schedule to the redispatched one.

    Two nonnegative fields rather than one signed one, for the reason the wave's research gives
    (§6) and :class:`~mambo_power.results.multiperiod.StorageDispatchResult` already follows for
    charge/discharge: a signed net number erases which direction was actually instructed, and
    "instructed up" and "instructed down" are different products a real redispatch mechanism
    settles differently. Here at most one of the two is nonzero for any generator, because
    :class:`~mambo_power.opf.redispatch.RedispatchSolution` reports the netted canonical
    representative rather than whichever split the solver happened to return.
    """

    id: str = Field(description="Generator id from the network.")
    bus: str = Field(description="Bus id the generator is connected to.")
    delta_up_mw: float = Field(
        description="Instructed increase above the zonal schedule, MW; >= 0. "
        "``p_final = p_zonal + delta_up_mw - delta_down_mw`` exactly."
    )
    delta_down_mw: float = Field(
        description="Instructed decrease below the zonal schedule, MW; >= 0."
    )


class LoadRedispatchResult(_Row):
    """One load's move from the zonal schedule to the redispatched one — the demand-side mirror of
    :class:`GenRedispatchResult`, and a row type ``results/`` did not have before this wave
    (:class:`~mambo_power.results.market.LoadDispatchResult` carries a served quantity, not a
    delta).

    Every load gets a row, bid or not, exactly as
    :class:`~mambo_power.results.market.LoadDispatchResult` gives every load a row. A load with no
    bid is not a decision variable in either stage, so it cannot be curtailed or restored and both
    fields are ``0.0`` -- which is a fact worth reporting rather than a row worth omitting: it is
    how a reader tells "this load was not moved" from "this load could not be moved".
    """

    id: str = Field(description="Load id from the network.")
    bus: str = Field(description="Bus id the load is connected to.")
    delta_restore_mw: float = Field(
        description="Served demand restored above the zonal schedule, MW; >= 0. "
        "``d_final = d_zonal + delta_restore_mw - delta_curtail_mw`` exactly."
    )
    delta_curtail_mw: float = Field(
        description="Served demand curtailed below the zonal schedule, MW; >= 0. 0.0 for a load "
        "with no bid, which is not a decision variable in either stage."
    )


class MarketZonalResult(BaseModel):
    """Result of :func:`mambo_power.market.zonal.solve_zonal` (module docstring).

    When ``status != "Optimal"`` every row list is empty and every figure is ``0.0``; ``message``
    carries the diagnostic, naming which of the three stages did not solve. The chain never
    raises for an infeasible or unbounded stage -- this package's standing convention, shared with
    :class:`~mambo_power.results.MarketNodalResult` and
    :class:`~mambo_power.results.MarketMultiperiodResult`.
    """

    model_config = ConfigDict(extra="forbid", frozen=True, allow_inf_nan=False)

    provenance: ResultProvenance
    status: str = Field(
        description='HiGHS model status: "Optimal", "Infeasible", "Unbounded", or another HiGHS '
        "status string passed through verbatim from whichever stage did not reach Optimal."
    )
    message: str | None = Field(
        default=None,
        description="Diagnostic when status != Optimal, naming the stage (zonal clearing, "
        "redispatch, or the nodal reference) that produced it.",
    )

    zones: list[ZonePriceResult] = Field(
        default_factory=list, description="One clearing price per zone, from the zonal stage."
    )
    generators: list[GenDispatchResult] = Field(
        default_factory=list,
        description="The **zonal** clearing's generator schedule -- what the market sold, before "
        "the network was consulted.",
    )
    loads: list[LoadDispatchResult] = Field(
        default_factory=list,
        description="The **zonal** clearing's served demand, every load in the network.",
    )
    redispatch_generators: list[GenRedispatchResult] = Field(
        default_factory=list,
        description="Per-generator move from the zonal schedule to the final one.",
    )
    redispatch_loads: list[LoadRedispatchResult] = Field(
        default_factory=list,
        description="Per-load curtailment/restoration between the zonal schedule and the final "
        "one.",
    )
    generators_final: list[GenDispatchResult] = Field(
        default_factory=list,
        description="The **redispatched** generator dispatch -- what the network actually "
        "delivers, and (design decision D1's theorem) the nodal optimum's own dispatch. "
        "``bound_dual`` is that generator's [p_min, p_max] reduced cost at the final point.",
    )
    loads_final: list[LoadDispatchResult] = Field(
        default_factory=list,
        description="The **redispatched** served demand, every load in the network.",
    )
    branches: list[OpfBranchFlowResult] = Field(
        default_factory=list,
        description="Per-branch flow and flow-limit shadow price at the **final** point -- the "
        "first market result type to carry them (M5 carry-over A23). Makes the settlement "
        "identity's flow-dual side, -sum_k(mu_k * f_k), computable from this object alone.",
    )
    buses: list[BusLmpResult] = Field(
        default_factory=list,
        description="Per-bus LMP at the **final** point, decomposed into energy and congestion. "
        "These are nodal prices; the zonal prices the market actually cleared at are in "
        "``zones``, and the two differing is the whole subject of this result.",
    )

    redispatch_payment: float = Field(
        default=0.0,
        description="**Settlement figure**, $/h: what the operator pays to move from the zonal "
        "schedule to the final one -- the extra generation cost, cost(final) - cost(zonal), plus "
        "compensation to curtailed load at its own bid value, value(d_zonal) - value(d_final) "
        "(a load *restored* above its zonal schedule contributes negatively, paying back at the "
        "same bid value). Equivalently and exactly, welfare(zonal) - welfare(final): the welfare "
        "the zonal clearing promised and the network could not deliver, which is why this figure "
        "is >= 0 whenever the zonal LP is a relaxation of the nodal one. Adding "
        "generation_cost_gap to this cancels the cost term and leaves the compensation alone: "
        "redispatch_payment + generation_cost_gap == value(d_zonal) - value(d_final). "
        "0.0 when not Optimal.",
    )
    welfare_gap: float = Field(
        default=0.0,
        description="**Exactness row**, $/h: welfare(nodal) - welfare(final), both evaluated on "
        "the true cost and bid curves at their own dispatch. Design decision D1 puts the true "
        "curves in the redispatch objective, which makes the redispatched point the nodal optimum "
        "itself -- so this is 0 to solver tolerance, and a nonzero value means the chain is "
        "wrong, not that zonal clearing is expensive (that figure is redispatch_payment). "
        "0.0 when not Optimal.",
    )
    generation_cost_gap: float = Field(
        default=0.0,
        description="**Diagnostic**, $/h: cost(zonal) - cost(nodal), true generation cost at each "
        "point, never a payment. **Not sign-constrained** -- the relaxation argument orders "
        "*welfare*, not generation cost, and a zonal clearing that serves less (or less valuable) "
        "demand can have strictly lower generation cost than the nodal optimum while being "
        "welfare-worse (research §4b). Do not read it as 'how far zonal lands from nodal'; only "
        "welfare answers that. Because design decision D1 makes cost(final) == cost(nodal), this "
        "is exactly -(cost(final) - cost(zonal)) -- minus redispatch_payment's leading term -- so "
        "the two fields sum to the curtailment compensation value(d_zonal) - value(d_final) and "
        "are equal and opposite whenever no load carries a bid curve. 0.0 when not Optimal.",
    )
