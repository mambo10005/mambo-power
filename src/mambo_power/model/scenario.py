"""The :class:`Scenario` model — a self-contained market scenario, and its :class:`Period`s."""

from typing import Self

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from mambo_power.model.network import Network


class Period(BaseModel):
    """One period's load overrides within a multi-period :class:`Scenario`.

    ``load_p_mw`` is an id-keyed **override** of each ``Load``'s ``p_mw`` for this period, not
    a scale factor: a load id absent from the dict falls back unchanged to that ``Load``'s own
    ``p_mw`` (solver-side behaviour; nothing reads this field yet, wave M5 Design item 1). Every
    key must resolve to a real ``Load`` id in the scenario's network — checked by
    :class:`Scenario`, not here, since a bare ``Period`` has no network to check against — and
    every value must be ``>= 0``.
    """

    model_config = ConfigDict(extra="forbid", frozen=False, allow_inf_nan=False)

    load_p_mw: dict[str, float] = Field(
        description="Per-load active-power override for this period, MW, keyed by Load id."
    )

    @field_validator("load_p_mw")
    @classmethod
    def _values_non_negative(cls, value: dict[str, float]) -> dict[str, float]:
        negative = {load_id: p for load_id, p in value.items() if p < 0}
        if negative:
            raise ValueError(f"load_p_mw values must be >= 0, got {negative}")
        return value


class Scenario(BaseModel):
    """A market scenario to clear: the network to clear it against, and its periods, if any.

    Embeds ``network: Network`` directly, mirroring ``jobs.models.SolveRequest``'s
    self-contained pattern rather than an id/path cross-reference — no such resolution
    mechanism exists anywhere else in this codebase.
    ``Network``'s own ``model_validator(mode="after")`` runs while ``Scenario`` is being
    constructed (it is a nested pydantic model field), so every invariant ``Network`` already
    checks — including dangling references — is checked here too, with no separate pass needed.

    ``periods: list[Period] | None = None`` — ``None`` means single-period: ``market.nodal``'s
    existing behaviour is unaffected (AC-4, wave M5). No agent-strategy fields this wave: their
    eventual shape is genuinely undesigned by M7, unlike ``Storage``'s successful M1 stub, which
    had a full spec before it shipped (design interview 2026-08-24, ratified; wave spec Design
    item 3).
    """

    model_config = ConfigDict(extra="forbid", frozen=False, allow_inf_nan=False)

    network: Network = Field(description="The network to clear; the scenario is self-contained.")
    periods: list[Period] | None = Field(
        default=None,
        min_length=1,
        description="Per-period load overrides; None = single-period, market.nodal semantics "
        "unchanged. If given, must be non-empty.",
    )

    @model_validator(mode="after")
    def _check_period_load_refs(self) -> Self:
        # Period has no network to check its own load ids against; this is the one place that
        # holds both the periods and the network at once, mirroring how Network's own
        # validate_network() catches a dangling reference, but at the Scenario level since
        # Period is scenario data, not a Network entity.
        if self.periods is None:
            return self
        load_ids = {load.id for load in self.network.loads}
        dangling = sorted(
            {
                load_id
                for period in self.periods
                for load_id in period.load_p_mw
                if load_id not in load_ids
            }
        )
        if dangling:
            raise ValueError(
                f"periods reference load id(s) not present in network.loads: {dangling}"
            )
        return self
