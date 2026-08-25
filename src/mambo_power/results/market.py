"""``market.nodal`` clearing result: dispatch (generators and loads), per-bus LMP, settlement.
Mirrors the ``results/opf.py`` pattern: id-keyed rows plus
:class:`~mambo_power.results.provenance.ResultProvenance`, never attached to a
:class:`~mambo_power.model.Network`. Reuses :class:`~mambo_power.results.opf.GenDispatchResult`/
:class:`~mambo_power.results.opf.BusLmpResult` verbatim for the generator-dispatch and LMP rows
(ADR-006's reuse discipline) -- only the load-dispatch row and settlement fields are new.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from mambo_power.results.opf import BusLmpResult, GenDispatchResult
from mambo_power.results.provenance import ResultProvenance


class LoadDispatchResult(BaseModel):
    """One load's ``market.nodal`` dispatch and its bound's shadow price.

    ``p_mw`` is the load's actual served demand: for a bid load, its solved elastic dispatch
    (:attr:`~mambo_power.opf.dc_opf.OpfSolution.demand_dispatch_mw`); for a load with no bid,
    its own fixed historical ``Load.p_mw`` (it never became an LP column, so it has no reduced
    cost -- ``bound_dual`` is ``0.0``). Every load in the network gets a row, bid or not, since
    the settlement identity sums ``LMP·p_d`` over *every* load, not just the elastic ones -- the
    identity's own derivation never assumes ``p_d`` is a decision variable.
    """

    model_config = ConfigDict(extra="forbid", frozen=True, allow_inf_nan=False)

    id: str = Field(description="Load id from the network.")
    bus: str = Field(description="Bus id the load is connected to.")
    p_mw: float = Field(description="Served demand, MW.")
    bound_dual: float = Field(
        description="Reduced cost of the load's [0, p_mw] bid bound; 0.0 for a non-bid load, "
        "since it is not a decision variable."
    )


class MarketNodalResult(BaseModel):
    """Result of :func:`mambo_power.market.nodal.solve_nodal`.

    When ``status != "Optimal"`` the dispatch/LMP/settlement fields are left at their empty/zero
    defaults; ``message`` carries the diagnostic (mirrors
    :class:`~mambo_power.results.OpfDcResult`'s own convention for a non-converged/infeasible
    solve).
    """

    model_config = ConfigDict(extra="forbid", frozen=True, allow_inf_nan=False)

    provenance: ResultProvenance
    status: str = Field(
        description='HiGHS model status: "Optimal", "Infeasible", "Unbounded", or another '
        "HiGHS status string passed through verbatim."
    )
    message: str | None = Field(default=None, description="Diagnostic when status != Optimal.")
    generators: list[GenDispatchResult] = Field(default_factory=list)
    loads: list[LoadDispatchResult] = Field(default_factory=list)
    buses: list[BusLmpResult] = Field(default_factory=list)
    total_load_payment: float = Field(
        default=0.0,
        description="Sum over every load of LMP(bus_d)*p_d, $/h -- computed directly from "
        "dispatch and LMPs, not asserted equal to the settlement identity's other side by "
        "construction (proved, not assumed, in tests/unit/test_market_nodal.py). 0.0 when not "
        "Optimal.",
    )
    total_generator_receipts: float = Field(
        default=0.0,
        description="Sum over every generator of LMP(bus_g)*p_g, $/h; 0.0 when not Optimal.",
    )
    congestion_rent: float = Field(
        default=0.0,
        description="total_load_payment - total_generator_receipts, $/h -- equals "
        "-sum_k(mu_k * flow_k) at the optimum (the settlement identity); 0.0 when not Optimal.",
    )
