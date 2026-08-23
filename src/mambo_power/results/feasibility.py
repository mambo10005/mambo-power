"""``FeasibilityReport``: AC-feasibility check of a dispatch (spec design item 6).

Shared under ``results`` rather than siloed in ``opf`` since a later wave's AC-checked N-1 state
wants the identical shape (design item 6). **Not populated by this wave's slice**: wave M3
slice S5 wires the actual check (``pf.solve_ac`` on the dispatched network, thermal violations
from ``BranchResult.loading_pct``, voltage violations from the ``Network``'s own ``v_min_pu``/
``v_max_pu`` against the solved ``vm_pu``) — this module exists now only so
``OpfDcResult.ac_check`` has a real type to declare; ``opf.solve_dc_opf`` always sets it to
``None`` in this slice.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class _Row(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, allow_inf_nan=False)


class ThermalViolation(_Row):
    """A branch loaded beyond its thermal rating."""

    branch_id: str = Field(description="Branch id from the network.")
    loading_pct: float = Field(description="Measured apparent-flow loading, percent of rating.")
    limit_pct: float = Field(description="The loading limit exceeded, percent.")


class VoltageViolation(_Row):
    """A bus outside its declared voltage-magnitude limits."""

    bus_id: str = Field(description="Bus id from the network.")
    vm_pu: float = Field(description="Measured voltage magnitude, per unit.")
    limit_pu: float = Field(description="The voltage limit exceeded (v_min_pu or v_max_pu), pu.")


class FeasibilityReport(BaseModel):
    """AC-feasibility check result: convergence plus thermal/voltage violations of a dispatch."""

    model_config = ConfigDict(extra="forbid", frozen=True, allow_inf_nan=False)

    converged: bool = Field(
        description="Whether the AC re-solve converged (mirrors AcPowerFlowResult.converged)."
    )
    message: str | None = Field(default=None, description="Diagnostic when converged is False.")
    thermal_violations: list[ThermalViolation] = Field(default_factory=list)
    voltage_violations: list[VoltageViolation] = Field(default_factory=list)
