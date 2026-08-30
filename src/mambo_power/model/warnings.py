"""Typed, non-fatal findings reported by importers and repairs.

A :class:`ValidationIssue` (``model.errors``) is something the model rejects; an
:class:`ImportIssue` is something an importer *repaired* and wants the caller to know
about. Codes are a closed set so callers can dispatch on them; ``str(warning)`` is the
``CODE: message`` line the legacy ``list[str]`` APIs carry.

Note: the class was first shipped as ``ImportWarning`` (the wave spec's name) and renamed
``ImportIssue`` because that name shadowed :class:`builtins.ImportWarning`. It is a pydantic
record, not a :class:`Warning` subclass, and is never passed to :func:`warnings.warn`.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

ImportIssueCode = Literal[
    "ISLAND_DEACTIVATED",
    "BASE_KV_REPLACED",
    "GENCOST_REACTIVE_IGNORED",
    # io.pypsa (wave M8, W3) — see ``mambo_power.io.pypsa.CODES``
    "PYPSA_PWL_COST_DROPPED",
    "PYPSA_COST_DEGREE_DROPPED",
    "PYPSA_LOAD_BID_DROPPED",
    "PYPSA_ZONE_DROPPED",
    "PYPSA_GEN_Q_LIMITS_DROPPED",
    "PYPSA_GEN_RAMP_DROPPED",
    "PYPSA_GEN_VSET_CONFLICT",
]
"""The closed set of importer/repair warning codes.

``ISLAND_DEACTIVATED`` — :func:`mambo_power.model.repair_islands` switched an island off.
``BASE_KV_REPLACED`` — MATPOWER ``BASE_KV <= 0`` replaced by the importer default.
``GENCOST_REACTIVE_IGNORED`` — a ``2 * ngen``-row ``gencost`` had its reactive half dropped.
``PYPSA_*`` — fields :mod:`mambo_power.io.pypsa` dropped because PyPSA cannot carry them
(piecewise or degree > 2 costs, load bids, zones, generator Q limits, a ramp on a zero-capacity
generator) or collapsed (disagreeing voltage setpoints at one bus).
"""


class ImportIssue(BaseModel):
    """One repair an importer performed: stable ``code``, message, and the ids it touched."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    code: ImportIssueCode
    message: str
    bus_ids: list[str] = Field(default_factory=list, description="Buses involved, if any.")
    element_ids: list[str] = Field(
        default_factory=list,
        description="Non-bus elements involved (branches, generators, loads, shunts, storage).",
    )

    def __str__(self) -> str:
        return f"{self.code}: {self.message}"
