"""DC-OPF result: dispatch, LMP breakdown, branch flows, shadow prices.

Mirrors the ``pf`` result pattern (:mod:`mambo_power.results.power_flow`):
id-keyed rows plus :class:`~mambo_power.results.provenance.ResultProvenance`, never attached to
a :class:`~mambo_power.model.Network`.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from mambo_power.results.feasibility import FeasibilityReport
from mambo_power.results.provenance import ResultProvenance


class _Row(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, allow_inf_nan=False)


class GenDispatchResult(_Row):
    """One generator's DC-OPF dispatch and its bound's shadow price."""

    id: str = Field(description="Generator id from the network.")
    bus: str = Field(description="Bus id the generator is connected to.")
    p_mw: float = Field(description="Optimal dispatch, MW.")
    bound_dual: float = Field(
        description="Reduced cost of the generator's [p_min, p_max] bound; 0 unless pinned."
    )


class BusLmpResult(_Row):
    """One bus's locational marginal price, decomposed (``opf.dc_opf.lmp_decomposition``)."""

    id: str = Field(description="Bus id from the network.")
    lmp: float = Field(description="Locational marginal price, $/MWh: energy + congestion.")
    energy: float = Field(description="Energy component: the system-wide balance dual.")
    congestion: float = Field(description="Congestion component: Σ(flow-limit duals × PTDF).")


class OpfBranchFlowResult(_Row):
    """One branch's DC-OPF flow and its flow-limit row's shadow price."""

    id: str = Field(description="Branch id from the network.")
    from_bus: str = Field(description="Bus id of the from (tap) side.")
    to_bus: str = Field(description="Bus id of the to side.")
    p_from_mw: float = Field(description="From-side active flow at the optimal dispatch, MW.")
    flow_limit_dual: float = Field(
        description="Shadow price of the branch's [-rating, rating] row; 0 unless binding."
    )


class OpfDcResult(BaseModel):
    """Result of :func:`mambo_power.opf.solve_dc_opf`.

    When ``status != "Optimal"`` the dispatch/LMP/flow rows and ``objective_cost``/
    ``balance_dual`` are meaningless and left at their empty/zero defaults; ``message`` carries
    the diagnostic (mirrors :class:`~mambo_power.results.AcPowerFlowResult`'s ``message``
    pattern for a non-converged solve).
    """

    model_config = ConfigDict(extra="forbid", frozen=True, allow_inf_nan=False)

    provenance: ResultProvenance
    status: str = Field(
        description='HiGHS model status: "Optimal", "Infeasible", "Unbounded", or another '
        "HiGHS status string passed through verbatim."
    )
    message: str | None = Field(default=None, description="Diagnostic when status != Optimal.")
    objective_cost: float = Field(
        default=0.0, description="Total generation cost, $/h; 0.0 when not Optimal."
    )
    balance_dual: float = Field(
        default=0.0, description="System-wide energy price, $/MWh; 0.0 when not Optimal."
    )
    generators: list[GenDispatchResult] = Field(default_factory=list)
    buses: list[BusLmpResult] = Field(default_factory=list)
    branches: list[OpfBranchFlowResult] = Field(default_factory=list)
    ac_check: FeasibilityReport | None = Field(
        default=None,
        description="AC-feasibility check of the dispatch; None unless options.ac_check is true "
        "and the LP/QP solved to Optimal.",
    )
