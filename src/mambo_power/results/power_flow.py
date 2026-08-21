"""Power-flow result models and their positional view.

:class:`DcPowerFlowResult` and :class:`AcPowerFlowResult` share the three id-keyed tables
(:class:`~mambo_power.results.tables.BusResult`, ``BranchResult``, ``GenResult``) and a
:class:`~mambo_power.results.provenance.ResultProvenance`; the AC model adds the Newton
diagnostics. Both expose :meth:`PowerFlowResultBase.to_arrays`, a frozen bundle of numpy
arrays in the order the rows were emitted — the :class:`~mambo_power.numerics.NetworkArrays`
order when the result came from a solver — for numeric consumers that want positions rather
than ids. A result is a value: it is never stored on the :class:`~mambo_power.model.Network`.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import numpy.typing as npt
from pydantic import BaseModel, ConfigDict, Field

from mambo_power.results.provenance import ResultProvenance
from mambo_power.results.tables import BranchResult, BusResult, GenResult

FloatArray = npt.NDArray[np.float64]


@dataclass(frozen=True)
class PowerFlowArrays:
    """Positional view of a power-flow result; one array per column, rows in table order.

    ``loading_pct`` holds ``nan`` where the branch is unrated (``None`` in the table).
    """

    bus_ids: tuple[str, ...]
    vm_pu: FloatArray
    va_deg: FloatArray
    p_bus_mw: FloatArray
    q_bus_mvar: FloatArray
    branch_ids: tuple[str, ...]
    p_from_mw: FloatArray
    q_from_mvar: FloatArray
    p_to_mw: FloatArray
    q_to_mvar: FloatArray
    loading_pct: FloatArray
    gen_ids: tuple[str, ...]
    p_gen_mw: FloatArray
    q_gen_mvar: FloatArray


class PowerFlowResultBase(BaseModel):
    """Fields common to DC and AC power-flow results."""

    model_config = ConfigDict(extra="forbid", frozen=True, allow_inf_nan=False)

    provenance: ResultProvenance
    converged: bool = Field(description="Whether the solve met its tolerance (always True for DC).")
    buses: list[BusResult] = Field(description="One row per solved bus, solver order.")
    branches: list[BranchResult] = Field(description="One row per solved branch, solver order.")
    generators: list[GenResult] = Field(description="One row per solved generator, solver order.")

    def to_arrays(self) -> PowerFlowArrays:
        """The positional view: one numpy array per column, rows in table order."""

        def column(values: list[float]) -> FloatArray:
            return np.asarray(values, dtype=np.float64)

        return PowerFlowArrays(
            bus_ids=tuple(b.id for b in self.buses),
            vm_pu=column([b.vm_pu for b in self.buses]),
            va_deg=column([b.va_deg for b in self.buses]),
            p_bus_mw=column([b.p_mw for b in self.buses]),
            q_bus_mvar=column([b.q_mvar for b in self.buses]),
            branch_ids=tuple(b.id for b in self.branches),
            p_from_mw=column([b.p_from_mw for b in self.branches]),
            q_from_mvar=column([b.q_from_mvar for b in self.branches]),
            p_to_mw=column([b.p_to_mw for b in self.branches]),
            q_to_mvar=column([b.q_to_mvar for b in self.branches]),
            loading_pct=column(
                [np.nan if b.loading_pct is None else b.loading_pct for b in self.branches]
            ),
            gen_ids=tuple(g.id for g in self.generators),
            p_gen_mw=column([g.p_mw for g in self.generators]),
            q_gen_mvar=column([g.q_mvar for g in self.generators]),
        )


class DcPowerFlowResult(PowerFlowResultBase):
    """Result of :func:`mambo_power.pf.solve_dc`: lossless, reactive columns are 0, ``vm_pu`` 1."""


class AcPowerFlowResult(PowerFlowResultBase):
    """Result of the AC Newton-Raphson solve (W1), with the iteration diagnostics."""

    iterations: int = Field(ge=0, description="Newton iterations of the final Q-limit round.")
    max_mismatch_mva: float = Field(ge=0.0, description="Final power-mismatch infinity norm, MVA.")
    q_limit_rounds: int = Field(ge=0, description="Outer Q-limit enforcement rounds run.")
