"""``ResultProvenance``: who produced a result, with what, when, and how long it took.

Every result model carries one of these: engine version, solver, timings and diagnostics, typed
per kind. ``version`` is stamped from ``mambo_power.__version__`` by the solver entry points,
never typed by hand, so that a stored result can always be traced to the code that produced it.
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

    model_config = ConfigDict(
        extra="forbid", frozen=True, allow_inf_nan=False, ser_json_inf_nan="constants"
    )
    """``allow_inf_nan=False`` still governs this model's own float, :attr:`elapsed_s`.
    ``ser_json_inf_nan`` reaches only inside :attr:`options`, whose values pydantic does not
    validate — see that field's description."""

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
        description="The options the solver ran with, echoed verbatim. JSON-native values, with "
        "one documented exception: market.zonal's CorridorLimit.cap_mw may be ``inf`` (the copper "
        "plate), which serialises as the bare token ``Infinity`` -- json.loads reads it, a "
        "browser's JSON.parse does not. No other option field in the package accepts a non-finite "
        "value, and every model reachable from a request's network or scenario forbids one.",
    )

    @field_validator("started_at")
    @classmethod
    def _must_be_aware_utc(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("started_at must be timezone-aware (UTC)")
        return value.astimezone(UTC)
