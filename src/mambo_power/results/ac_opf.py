"""AC-OPF result (ADR-018): dispatch with reactive power and voltages, AC LMPs, apparent flows.

Mirrors :mod:`mambo_power.results.opf` for the DC-OPF: id-keyed rows plus provenance, never
attached to a :class:`~mambo_power.model.Network`. The rows carry what the DC result cannot —
``q_mvar``, ``vm_pu``, a reactive price, apparent power at both ends of a branch — so a reader
comparing the two sees exactly where the AC model adds information.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from mambo_power.results.provenance import ResultProvenance


class _Row(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, allow_inf_nan=False)


class AcGenDispatchResult(_Row):
    """One generator's AC-OPF dispatch and its bounds' shadow prices."""

    id: str = Field(description="Generator id from the network.")
    bus: str = Field(description="Bus id the generator is connected to.")
    p_mw: float = Field(description="Optimal active dispatch, MW.")
    q_mvar: float = Field(description="Optimal reactive dispatch, MVAr.")
    p_bound_dual: float = Field(
        description="Reduced cost of the [p_min, p_max] bound, $/MWh; 0 unless pinned."
    )
    q_bound_dual: float = Field(
        description="Reduced cost of the [q_min, q_max] bound, $/MVArh; 0 unless pinned."
    )


class AcBusResult(_Row):
    """One bus's AC-OPF voltage and marginal prices."""

    id: str = Field(description="Bus id from the network.")
    vm_pu: float = Field(description="Voltage magnitude, per unit.")
    va_deg: float = Field(description="Voltage angle, degrees; 0 at the slack.")
    lmp_p: float = Field(
        description="Marginal cost of active demand, $/MWh: the AC LMP, with losses and "
        "voltage support priced in."
    )
    lmp_q: float = Field(description="Marginal cost of reactive demand, $/MVArh.")
    v_bound_dual: float = Field(
        description="Reduced cost of the voltage band, $/pu·h; 0 unless the bus sits on it."
    )


class AcBranchFlowResult(_Row):
    """One branch's AC-OPF flows at both ends and its apparent-power limits' shadow prices."""

    id: str = Field(description="Branch id from the network.")
    from_bus: str = Field(description="Bus id of the from (tap) side.")
    to_bus: str = Field(description="Bus id of the to side.")
    p_from_mw: float = Field(description="Active flow into the branch at the from side, MW.")
    q_from_mvar: float = Field(description="Reactive flow at the from side, MVAr.")
    p_to_mw: float = Field(description="Active flow into the branch at the to side, MW.")
    q_to_mvar: float = Field(description="Reactive flow at the to side, MVAr.")
    s_from_mva: float = Field(ge=0.0, description="Apparent power at the from side, MVA.")
    s_to_mva: float = Field(ge=0.0, description="Apparent power at the to side, MVA.")
    loading_percent: float | None = Field(
        default=None,
        description="max(s_from, s_to) / rating × 100; None on an unrated branch.",
    )
    flow_from_dual: float = Field(
        default=0.0, description="Dual of the from-side |S|² <= rating² row; 0 unless binding."
    )
    flow_to_dual: float = Field(
        default=0.0, description="Dual of the to-side |S|² <= rating² row; 0 unless binding."
    )


class OpfAcResult(BaseModel):
    """Result of :func:`mambo_power.opf.solve_ac_opf`.

    ``status`` is ``"Optimal"`` for a converged KKT point, ``"IterationLimit"`` when the step
    budget ran out, ``"Infeasible"`` when no AC-feasible point was found, or an LP status passed
    through. When ``status != "Optimal"`` the rows are empty and ``message`` carries the
    diagnostic; ``objective_cost`` still reports the cost at the final point.
    """

    model_config = ConfigDict(extra="forbid", frozen=True, allow_inf_nan=False)

    provenance: ResultProvenance
    status: str = Field(description='"Optimal", "IterationLimit", "Infeasible", or an LP status.')
    message: str | None = Field(default=None, description="Diagnostic when status != Optimal.")
    iterations: int = Field(ge=0, description="LP steps the trust-region loop took.")
    objective_cost: float = Field(default=0.0, description="Total generation cost, $/h.")
    losses_mw: float = Field(
        default=0.0, description="Total active losses, MW: generation minus load at the optimum."
    )
    max_mismatch_pu: float = Field(
        default=0.0, description="Largest nodal power mismatch at the final point, pu."
    )
    generators: list[AcGenDispatchResult] = Field(default_factory=list)
    buses: list[AcBusResult] = Field(default_factory=list)
    branches: list[AcBranchFlowResult] = Field(default_factory=list)
