"""N-2 branch-pair contingency result (ADR-024, ``contingency.n2``).

The pair counterpart of :mod:`mambo_power.results.n1`: one entry per flagged pair with the same
:class:`~mambo_power.results.n1.N1BranchFlag` rows (screen estimate against confirming re-solve),
plus the pairs that cannot be screened because their removal disconnects the network.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from mambo_power.results.n1 import N1BranchFlag
from mambo_power.results.provenance import ResultProvenance


class N2OutageResult(BaseModel):
    """The generalised-LODF screen's verdict on one branch pair, plus its confirming re-solve."""

    model_config = ConfigDict(extra="forbid", frozen=True, allow_inf_nan=False)

    outage_branch_ids: list[str] = Field(
        min_length=2, max_length=2, description="The two branch ids taken out together."
    )
    flagged_branches: list[N1BranchFlag] = Field(
        description="Branches the screen flagged for this pair, at least one; rating_mva is "
        "the post-contingency limit applied (the emergency rating where set)."
    )
    confirmed_violating: bool = Field(
        description="Whether the DC re-solve with both branches out confirms a violation."
    )


class N2Result(BaseModel):
    """N-2 branch-pair screen-then-confirm result (``contingency.n2``).

    ``islanding_pairs`` are the pairs whose joint removal disconnects the network — a cut set,
    detected by a zero generalised-LODF determinant — which the DC model cannot estimate and the
    screen therefore reports instead; ``bridge_branch_ids`` are the single branches that are
    cut sets on their own, so no pair containing one is screened. ``truncated`` says the screen
    flagged more pairs than ``N2Options.max_confirmed_pairs`` and only the first that many, in
    pair order, were re-solved.
    """

    model_config = ConfigDict(extra="forbid", frozen=True, allow_inf_nan=False)

    provenance: ResultProvenance
    outages: list[N2OutageResult] = Field(
        description="One entry per flagged and confirmed pair, in lexicographic branch order."
    )
    islanding_pairs: list[list[str]] = Field(
        default_factory=list, description="Pairs whose removal disconnects the network."
    )
    bridge_branch_ids: list[str] = Field(
        default_factory=list,
        description="Branches skipped because their own outage disconnects the network.",
    )
    n_pairs_screened: int = Field(
        default=0, ge=0, description="Pairs the screen estimated (islanding pairs included)."
    )
    truncated: bool = Field(
        default=False, description="Whether flagged pairs beyond the cap were left unconfirmed."
    )
