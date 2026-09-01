"""N-1 branch-contingency screen-then-confirm result.

``N1Result`` is shared here rather than siloed in ``contingency`` because it is the type
``contingency.n1`` produces *and* the type ``jobs``' ``n1`` kind consumes, mirroring why
:class:`~mambo_power.results.FeasibilityReport` is shared too: code composing N-1 state elsewhere
wants the identical shape without importing ``contingency`` for it.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from mambo_power.results.provenance import ResultProvenance


class N1BranchFlag(BaseModel):
    """One (outage, monitored branch) pair the LODF screen flagged, with the confirming re-solve.

    ``estimated_flow_mw`` is the LODF-screen's estimate (``|base_flow + lodf[:, k] *
    base_flow[k]|``); ``confirmed_flow_mw`` is the actual flow from the real DC re-solve with
    the outage branch taken out of service — the ground truth the screen is checked against.
    """

    model_config = ConfigDict(extra="forbid", frozen=True, allow_inf_nan=False)

    branch_id: str = Field(description="The monitored branch id whose flow was flagged.")
    rating_mva: float = Field(gt=0.0, description="The monitored branch's thermal rating, MVA.")
    estimated_flow_mw: float = Field(
        ge=0.0, description="LODF-screen estimated |flow| on this branch after the outage, MW."
    )
    confirmed_flow_mw: float = Field(
        ge=0.0, description="Actual |flow| on this branch from the confirming DC re-solve, MW."
    )
    confirmed_violating: bool = Field(
        description="Whether the re-solve confirms confirmed_flow_mw exceeds rating_mva."
    )


class N1OutageResult(BaseModel):
    """The LODF screen's verdict on one branch outage, plus its confirming re-solve.

    Only outages the screen flagged (at least one monitored branch estimated over its rating)
    are re-solved and appear here at all — an unflagged outage is asserted, not re-solved, to
    be non-violating, which a brute-force agreement test in ``tests/`` proves is safe.
    """

    model_config = ConfigDict(extra="forbid", frozen=True, allow_inf_nan=False)

    outage_branch_id: str = Field(description="The branch id taken out of service.")
    flagged_branches: list[N1BranchFlag] = Field(
        description="Other branches the LODF screen flagged for this outage, at least one."
    )
    confirmed_violating: bool = Field(
        description="Whether the DC re-solve confirms at least one flagged branch violates."
    )


class N1Result(BaseModel):
    """N-1 branch-contingency screen-then-confirm result (``contingency.n1``).

    ``bridge_branch_ids`` names branches whose outage would disconnect the network
    (``numerics.bridges``) — LODF is undefined for them, so they are skipped by the screen
    entirely and never appear as an ``outages`` entry. Branch outages only this wave;
    generator-outage contingencies are an explicit carry-over (wave spec Not Doing).
    """

    model_config = ConfigDict(extra="forbid", frozen=True, allow_inf_nan=False)

    provenance: ResultProvenance
    outages: list[N1OutageResult] = Field(
        description="One entry per outage the LODF screen flagged, in branch order."
    )
    bridge_branch_ids: list[str] = Field(
        description="Branch ids skipped because their outage disconnects the network."
    )
