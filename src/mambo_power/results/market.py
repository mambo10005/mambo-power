"""``market.nodal`` clearing result: dispatch (generators and loads), per-bus LMP, per-branch flow,
settlement — and, since ADR-031, the ``market.nodal_ac`` result at the bottom of the module.
Mirrors the ``results/opf.py`` pattern: id-keyed rows plus
:class:`~mambo_power.results.provenance.ResultProvenance`, never attached to a
:class:`~mambo_power.model.Network`. Reuses :class:`~mambo_power.results.opf.GenDispatchResult`/
:class:`~mambo_power.results.opf.BusLmpResult`/:class:`~mambo_power.results.opf.
OpfBranchFlowResult` verbatim for the generator-dispatch, LMP and branch-flow rows (ADR-006's
reuse discipline) -- only the load-dispatch row and settlement fields are new.

**Branch rows, closing M5's A23 symmetrically (M7 W4, AC-8).** M6 gave
:class:`~mambo_power.results.MarketZonalResult` per-branch flow/dual rows under
:attr:`~mambo_power.results.MarketZonalResult.branches`, on the strength of a settlement identity
that needed them; this result carried no such rows, which is exactly the asymmetry M6's own AC-4
re-audit found itself structurally blind to (continuation-m6 carry-over 12). ``branches`` here is
the **same field name and the same row type** as ``MarketZonalResult``'s, populated by
:func:`mambo_power.market.nodal.solve_nodal` from the one clearing it already has -- no second
solve, no new model field.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from mambo_power.results.ac_opf import (
    AcBranchFlowResult,
    AcGenDispatchResult,
    AcLoadDispatchResult,
)
from mambo_power.results.opf import BusLmpResult, GenDispatchResult, OpfBranchFlowResult
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
    branches: list[OpfBranchFlowResult] = Field(
        default_factory=list,
        description="Per-branch flow and flow-limit shadow price at the solved dispatch -- the "
        "same field name and row type as MarketZonalResult.branches (module docstring, AC-8). "
        "Makes the settlement identity's flow-dual side, -sum_k(mu_k * f_k), computable from "
        "this object alone.",
    )
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


class BusLmpAcResult(BaseModel):
    """One bus's AC locational marginal prices (ADR-031) and the voltage they were set at."""

    model_config = ConfigDict(extra="forbid", frozen=True, allow_inf_nan=False)

    id: str = Field(description="Bus id from the network.")
    lmp: float = Field(
        description="Active LMP, $/MWh: the P-balance dual, losses and voltage support included."
    )
    lmp_q: float = Field(description="Reactive LMP, $/MVArh: the Q-balance dual.")
    vm_pu: float = Field(description="Voltage magnitude at the clearing, pu.")
    va_deg: float = Field(description="Voltage angle at the clearing, degrees; 0 at the slack.")


class MarketNodalAcResult(BaseModel):
    """Result of :func:`mambo_power.market.nodal_ac.solve_nodal_ac` (ADR-031).

    When ``status != "Optimal"`` the rows and settlement are left at their empty/zero defaults
    and ``message`` carries the diagnostic, like :class:`~mambo_power.results.OpfAcResult`.
    """

    model_config = ConfigDict(extra="forbid", frozen=True, allow_inf_nan=False)

    provenance: ResultProvenance
    status: str = Field(description='"Optimal", "IterationLimit", "Infeasible", or an LP status.')
    message: str | None = Field(default=None, description="Diagnostic when status != Optimal.")
    iterations: int = Field(default=0, ge=0, description="LP steps the AC-OPF took.")
    objective_cost: float = Field(default=0.0, description="Total generation cost, $/h.")
    demand_value: float = Field(
        default=0.0, description="Bid value of the demand served by the bid loads, $/h."
    )
    losses_mw: float = Field(default=0.0, description="Generation minus served demand, MW.")
    generators: list[AcGenDispatchResult] = Field(default_factory=list)
    loads: list[AcLoadDispatchResult] = Field(default_factory=list)
    buses: list[BusLmpAcResult] = Field(default_factory=list)
    branches: list[AcBranchFlowResult] = Field(default_factory=list)
    total_load_payment: float = Field(
        default=0.0, description="Σ_d LMP(bus_d) · p_d over every load's served demand, $/h."
    )
    total_generator_receipts: float = Field(
        default=0.0, description="Σ_g LMP(bus_g) · p_g over every generator, $/h."
    )
    merchandising_surplus: float = Field(
        default=0.0,
        description="total_load_payment − total_generator_receipts, $/h: the loss rent plus "
        "the congestion rent (module docstring); 0 on a lossless uncongested network.",
    )
    total_reactive_payment: float = Field(
        default=0.0, description="Σ_d LMP_q(bus_d) · q_d over every load, $/h."
    )
    total_reactive_receipts: float = Field(
        default=0.0, description="Σ_g LMP_q(bus_g) · q_g over every generator, $/h."
    )
