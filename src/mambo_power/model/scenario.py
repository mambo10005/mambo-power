"""The :class:`Scenario` model — a self-contained market scenario."""

from pydantic import BaseModel, ConfigDict, Field

from mambo_power.model.network import Network


class Scenario(BaseModel):
    """A market scenario to clear: the network to clear it against, and nothing else yet.

    Embeds ``network: Network`` directly, mirroring ``jobs.models.SolveRequest``'s
    self-contained pattern rather than an id/path cross-reference — no such resolution
    mechanism exists anywhere else in this codebase.
    ``Network``'s own ``model_validator(mode="after")`` runs while ``Scenario`` is being
    constructed (it is a nested pydantic model field), so every invariant ``Network`` already
    checks — including dangling references — is checked here too, with no separate pass needed.

    No ``periods`` or agent-strategy fields this wave: their eventual shape is genuinely
    undesigned by M5/M7, unlike ``Storage``'s successful M1 stub, which had a full spec before
    it shipped (design interview 2026-08-24, ratified; wave spec Design item 3).
    """

    model_config = ConfigDict(extra="forbid", frozen=False, allow_inf_nan=False)

    network: Network = Field(description="The network to clear; the scenario is self-contained.")
