"""Typed, id-keyed solver results with provenance.

Results are values produced by ``pf`` (and later ``opf``, ``contingency``, ``market``) and
consumed by ``jobs`` and user code. They are pydantic v2 models — exact JSON round-trip,
unknown fields and non-finite numbers rejected — keyed by the network's stable ids, with a
positional ``to_arrays()`` view. They are never attached to a ``Network``.
"""

from mambo_power.results.ac_opf import (
    AcBranchFlowResult,
    AcBusResult,
    AcGenDispatchResult,
    AcLoadDispatchResult,
    OpfAcResult,
)
from mambo_power.results.agents import (
    AgentOfferResult,
    MarketAgentsResult,
    TerminationReason,
)
from mambo_power.results.feasibility import (
    FeasibilityReport,
    ThermalViolation,
    VoltageViolation,
    feasibility_report,
)
from mambo_power.results.from_arrays import ac_result_from_arrays, dc_result_from_arrays
from mambo_power.results.market import (
    BusLmpAcResult,
    LoadDispatchResult,
    MarketNodalAcResult,
    MarketNodalResult,
)
from mambo_power.results.multiperiod import (
    GenCommitmentResult,
    GenPeriodDispatchResult,
    MarketMultiperiodResult,
    MarketPeriodResult,
    StorageDispatchResult,
)
from mambo_power.results.n1 import (
    N1BranchFlag,
    N1GeneratorOutageResult,
    N1OutageResult,
    N1Result,
)
from mambo_power.results.n2 import N2OutageResult, N2Result
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
from mambo_power.results.scopf import (
    CorrectiveActionResult,
    GenCorrectionResult,
    LoadShedResult,
    ScopfDcResult,
    SecurityConstraintResult,
)
from mambo_power.results.tables import (
    BranchResult,
    BusResult,
    BusRole,
    GenResult,
    QLimitSide,
)
from mambo_power.results.zonal import (
    GenRedispatchResult,
    LoadRedispatchResult,
    MarketZonalResult,
    ZonePriceResult,
)

__all__ = [
    "AcBranchFlowResult",
    "AcBusResult",
    "AcGenDispatchResult",
    "AcLoadDispatchResult",
    "AcPowerFlowResult",
    "AgentOfferResult",
    "BranchResult",
    "BusLmpAcResult",
    "BusLmpResult",
    "CorrectiveActionResult",
    "BusResult",
    "BusRole",
    "DcPowerFlowResult",
    "FeasibilityReport",
    "GenCommitmentResult",
    "GenCorrectionResult",
    "LoadShedResult",
    "GenDispatchResult",
    "GenPeriodDispatchResult",
    "GenRedispatchResult",
    "GenResult",
    "LoadDispatchResult",
    "LoadRedispatchResult",
    "MarketAgentsResult",
    "MarketMultiperiodResult",
    "MarketNodalAcResult",
    "MarketNodalResult",
    "MarketPeriodResult",
    "MarketZonalResult",
    "N1BranchFlag",
    "N1GeneratorOutageResult",
    "N1OutageResult",
    "N1Result",
    "N2OutageResult",
    "N2Result",
    "OpfAcResult",
    "OpfBranchFlowResult",
    "OpfDcResult",
    "PowerFlowArrays",
    "PowerFlowResultBase",
    "QLimitSide",
    "ResultProvenance",
    "ScopfDcResult",
    "SecurityConstraintResult",
    "StorageDispatchResult",
    "TerminationReason",
    "ThermalViolation",
    "VoltageViolation",
    "ZonePriceResult",
    "ac_result_from_arrays",
    "dc_result_from_arrays",
    "feasibility_report",
]
