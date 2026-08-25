"""Typed, id-keyed solver results with provenance (epic Design §1-2; wave M2 W5).

Results are values produced by ``pf`` (and later ``opf``, ``contingency``, ``market``) and
consumed by ``jobs`` and user code. They are pydantic v2 models — exact JSON round-trip,
unknown fields and non-finite numbers rejected — keyed by the network's stable ids, with a
positional ``to_arrays()`` view. They are never attached to a ``Network``.
"""

from mambo_power.results.feasibility import (
    FeasibilityReport,
    ThermalViolation,
    VoltageViolation,
    feasibility_report,
)
from mambo_power.results.from_arrays import ac_result_from_arrays, dc_result_from_arrays
from mambo_power.results.market import LoadDispatchResult, MarketNodalResult
from mambo_power.results.n1 import N1BranchFlag, N1OutageResult, N1Result
from mambo_power.results.opf import (
    BusLmpResult,
    GenDispatchResult,
    OpfBranchFlowResult,
    OpfDcResult,
)
from mambo_power.results.power_flow import (
    AcPowerFlowResult,
    DcPowerFlowResult,
    PowerFlowArrays,
    PowerFlowResultBase,
)
from mambo_power.results.provenance import ResultProvenance
from mambo_power.results.tables import (
    BranchResult,
    BusResult,
    BusRole,
    GenResult,
    QLimitSide,
)

__all__ = [
    "AcPowerFlowResult",
    "BranchResult",
    "BusLmpResult",
    "BusResult",
    "BusRole",
    "DcPowerFlowResult",
    "FeasibilityReport",
    "GenDispatchResult",
    "GenResult",
    "LoadDispatchResult",
    "MarketNodalResult",
    "N1BranchFlag",
    "N1OutageResult",
    "N1Result",
    "OpfBranchFlowResult",
    "OpfDcResult",
    "PowerFlowArrays",
    "PowerFlowResultBase",
    "QLimitSide",
    "ResultProvenance",
    "ThermalViolation",
    "VoltageViolation",
    "ac_result_from_arrays",
    "dc_result_from_arrays",
    "feasibility_report",
]
