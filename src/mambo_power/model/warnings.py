"""Typed, non-fatal findings reported by importers and repairs.

A :class:`ValidationIssue` (``model.errors``) is something the model rejects; an
:class:`ImportWarning` is something an importer *repaired* and wants the caller to know
about. Codes are a closed set so callers can dispatch on them; ``str(warning)`` is the
``CODE: message`` line the legacy ``list[str]`` APIs carry.

Note: this class deliberately shares its name with :class:`builtins.ImportWarning` because
the wave spec names it so. It is a pydantic record, not a :class:`Warning` subclass, and is
never passed to :func:`warnings.warn`; import it as ``mambo_power.model.ImportWarning`` to
keep the distinction visible.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

ImportWarningCode = Literal[
    "ISLAND_DEACTIVATED",
    "BASE_KV_REPLACED",
    "GENCOST_REACTIVE_IGNORED",
]
"""The closed set of importer/repair warning codes.

``ISLAND_DEACTIVATED`` — :func:`mambo_power.model.repair_islands` switched an island off.
``BASE_KV_REPLACED`` — MATPOWER ``BASE_KV <= 0`` replaced by the importer default.
``GENCOST_REACTIVE_IGNORED`` — a ``2 * ngen``-row ``gencost`` had its reactive half dropped.
"""


class ImportWarning(BaseModel):
    """One repair an importer performed: stable ``code``, message, and the ids it touched."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    code: ImportWarningCode
    message: str
    bus_ids: list[str] = Field(default_factory=list, description="Buses involved, if any.")
    element_ids: list[str] = Field(
        default_factory=list,
        description="Non-bus elements involved (branches, generators, loads, shunts, storage).",
    )

    def __str__(self) -> str:
        return f"{self.code}: {self.message}"
