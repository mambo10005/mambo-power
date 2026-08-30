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
    "CSV_MANIFEST_INVALID",
    "CSV_SCHEMA_VERSION",
    "CSV_MISSING_TABLE",
    "CSV_UNKNOWN_COLUMN",
    "CSV_MISSING_COLUMN",
    "CSV_DUPLICATE_ID",
    "CSV_BAD_VALUE",
    "CSV_ORPHAN_ROW",
]
"""The closed set of importer/repair warning codes.

``ISLAND_DEACTIVATED`` — :func:`mambo_power.model.repair_islands` switched an island off.
``BASE_KV_REPLACED`` — MATPOWER ``BASE_KV <= 0`` replaced by the importer default.
``GENCOST_REACTIVE_IGNORED`` — a ``2 * ngen``-row ``gencost`` had its reactive half dropped.

The ``CSV_*`` codes are :mod:`mambo_power.io.csv_bundle` import errors (never warnings):
``CSV_MANIFEST_INVALID`` — ``manifest.json`` missing, unparsable, or disagreeing with the tables;
``CSV_SCHEMA_VERSION`` — the manifest names a schema version this build does not read;
``CSV_MISSING_TABLE`` — a table file the bundle must carry is absent;
``CSV_UNKNOWN_COLUMN`` / ``CSV_MISSING_COLUMN`` — a table header is not the model's field list;
``CSV_DUPLICATE_ID`` — an id appears twice in one table;
``CSV_BAD_VALUE`` — a cell does not parse as its column's type (``nan`` included), or an
entity fails its own field validation;
``CSV_ORPHAN_ROW`` — a cost/bid side-table row whose owner is absent or carries no ``kind``.
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
