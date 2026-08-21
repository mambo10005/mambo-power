"""``ResultProvenance``: who produced a result, with what, when, and how long it took.

Every result model carries one of these (epic Design §1: "typed per kind with provenance —
engine version, solver, timings, diagnostics"). ``version`` is stamped from
``mambo_power.__version__`` by the solver entry points, never typed by hand, so that a stored
result can always be traced to the code that produced it (AC-6 agreement test).
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class ResultProvenance(BaseModel):
    """Provenance stamp attached to every solver result.

    ``started_at`` must be timezone-aware; it is normalised to UTC on validation so the JSON
    form is always a ``Z``-suffixed instant.
    """

    model_config = ConfigDict(extra="forbid", frozen=True, allow_inf_nan=False)

    engine: Literal["mambo-power"] = Field(description="Producing engine; always this package.")
    version: str = Field(min_length=1, description="``mambo_power.__version__`` at solve time.")
    kind: str = Field(min_length=1, description="Analysis kind, e.g. ``pf.dc`` or ``pf.ac``.")
    solver: str = Field(
        min_length=1, description="Linear-algebra backend, e.g. ``scipy.sparse.linalg.splu``."
    )
    started_at: datetime = Field(description="Wall-clock start of the solve, UTC.")
    elapsed_s: float = Field(ge=0.0, description="Wall-clock duration of the solve, seconds.")
    options: dict[str, Any] = Field(
        default_factory=dict,
        description="The options the solver ran with, JSON-native values only.",
    )

    @field_validator("started_at")
    @classmethod
    def _must_be_aware_utc(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("started_at must be timezone-aware (UTC)")
        return value.astimezone(UTC)
