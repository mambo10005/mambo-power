"""``FeasibilityReport``: AC-feasibility check of a dispatch.

Shared under ``results`` rather than siloed in ``opf`` because an AC-checked N-1 state wants the
identical shape. :func:`feasibility_report` builds one from a solved
:class:`~mambo_power.results.AcPowerFlowResult` (the dispatched state) plus the
:class:`~mambo_power.model.Network` it was solved on (the declared bounds) — neither alone
carries both; :func:`mambo_power.opf.solve_dc_opf` calls it when ``options.ac_check`` is true.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from mambo_power.model import Network
from mambo_power.results.power_flow import AcPowerFlowResult

THERMAL_LIMIT_PCT = 100.0
"""``loading_pct`` above this is a thermal violation — the 100%-of-rating boundary
``results.from_arrays._loading_pct`` already normalises every branch's apparent flow against."""


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


def feasibility_report(ac: AcPowerFlowResult, net: Network) -> FeasibilityReport:
    """Build a :class:`FeasibilityReport` from a solved AC state and the network it bounds.

    ``ac`` carries the dispatched, solved state (``BranchResult.loading_pct``, ``BusResult.
    vm_pu``); ``net`` carries the declared bounds (``Branch.rating_mva`` indirectly via ``ac``'s
    already-computed ``loading_pct``, ``Bus.v_min_pu``/``v_max_pu`` directly) — matched by id.
    ``converged``/``message`` are passed through from ``ac`` unchanged, never recomputed.

    A branch with no rating (``loading_pct is None``) never contributes a thermal violation —
    "unmeasurable" is not "violating". A bus with neither bound set never contributes a voltage
    violation. When both bounds are set and a bus is on the wrong side of both (a misconfigured
    network with ``v_min_pu > v_max_pu``), the low-side check wins; that misconfiguration is not
    this function's job to guard against.
    """
    thermal = [
        ThermalViolation(branch_id=b.id, loading_pct=b.loading_pct, limit_pct=THERMAL_LIMIT_PCT)
        for b in ac.branches
        if b.loading_pct is not None and b.loading_pct > THERMAL_LIMIT_PCT
    ]
    bounds_by_id = {bus.id: bus for bus in net.buses}
    voltage: list[VoltageViolation] = []
    for bus in ac.buses:
        bound = bounds_by_id.get(bus.id)
        if bound is None:
            continue
        if bound.v_min_pu is not None and bus.vm_pu < bound.v_min_pu:
            voltage.append(
                VoltageViolation(bus_id=bus.id, vm_pu=bus.vm_pu, limit_pu=bound.v_min_pu)
            )
        elif bound.v_max_pu is not None and bus.vm_pu > bound.v_max_pu:
            voltage.append(
                VoltageViolation(bus_id=bus.id, vm_pu=bus.vm_pu, limit_pu=bound.v_max_pu)
            )
    return FeasibilityReport(
        converged=ac.converged,
        message=ac.message,
        thermal_violations=thermal,
        voltage_violations=voltage,
    )
