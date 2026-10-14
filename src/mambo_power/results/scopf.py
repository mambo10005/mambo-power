"""Security-constrained DC-OPF result (ADR-016): the secure dispatch and what securing it cost.

Reuses the DC-OPF row types (:mod:`mambo_power.results.opf`) for the dispatch, LMPs and base-case
flows, adds one row per binding-candidate post-contingency constraint, and carries the
:class:`~mambo_power.results.N1Result` that confirms the dispatch, so the proof of security
travels with the result rather than being something the reader has to re-run.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from mambo_power.results.feasibility import FeasibilityReport
from mambo_power.results.n1 import N1Result
from mambo_power.results.n2 import N2Result
from mambo_power.results.opf import BusLmpResult, GenDispatchResult, OpfBranchFlowResult
from mambo_power.results.provenance import ResultProvenance


class SecurityConstraintResult(BaseModel):
    """One (outage, monitored branch) pair the constraint-generation loop had to constrain.

    ``post_contingency_flow_mw`` is the monitored branch's signed from-side flow once the outage
    has happened, at the secure dispatch — within ``±rating_mva`` by construction. ``dual`` is
    the row's shadow price: nonzero exactly for the pairs that actually bind the secure dispatch,
    the contingencies the system is paying to be ready for.
    """

    model_config = ConfigDict(extra="forbid", frozen=True, allow_inf_nan=False)

    outage_kind: Literal["branch", "generator", "pair"] = Field(
        description='What is lost: one branch, one generator, or a "pair" of branches (ADR-025).'
    )
    outage_id: str = Field(
        description="Id of the outaged branch or generator; for a pair, the first branch."
    )
    outage_ids: list[str] = Field(
        default_factory=list,
        description="For a pair, both outaged branch ids, in id order; empty otherwise.",
    )
    branch_id: str = Field(description="The monitored branch id.")
    rating_mva: float = Field(
        gt=0.0,
        description="The post-contingency limit applied to the monitored branch, MVA: its "
        "emergency rating where one is set, else its normal rating (ADR-020).",
    )
    post_contingency_flow_mw: float = Field(
        description="Signed from-side flow on the monitored branch after the outage, MW."
    )
    dual: float = Field(description="Shadow price of the post-contingency row; 0 unless binding.")


class GenCorrectionResult(BaseModel):
    """One generator's corrected output in one contingency (ADR-021)."""

    model_config = ConfigDict(extra="forbid", frozen=True, allow_inf_nan=False)

    id: str = Field(description="Generator id from the network.")
    p_mw: float = Field(description="Corrected output once the contingency has happened, MW.")
    delta_mw: float = Field(description="p_mw minus the base-case dispatch, MW.")


class CorrectiveActionResult(BaseModel):
    """The post-contingency redispatch for one outage (ADR-021, corrective SCOPF).

    The redispatch is the corrected dispatch the LP found for this outage: every unit within its
    corrective ramp of the base case, the lost unit at zero, the load served without the slack
    making anything up. ``constraints`` are the pairs whose *corrected* flow is held to the
    normal rating; ``confirmed_max_loading`` is the real DC re-solve of the network with the
    outage applied and this redispatch, as a fraction of the normal rating over every branch
    — ``<= 1`` is what ``ScopfDcResult.corrected_secure`` means.
    """

    model_config = ConfigDict(extra="forbid", frozen=True, allow_inf_nan=False)

    outage_kind: Literal["branch", "generator"] = Field(description="What is lost.")
    outage_id: str = Field(description="Id of the outaged branch or generator.")
    redispatch: list[GenCorrectionResult] = Field(
        description="Every generator's corrected output, generator order."
    )
    constraints: list[SecurityConstraintResult] = Field(
        default_factory=list,
        description="The corrected-flow rows for this outage: rating_mva is the normal rating, "
        "post_contingency_flow_mw the corrected flow.",
    )
    confirmed_max_loading: float = Field(
        ge=0.0,
        description="Largest |flow| / normal rating over every rated branch in the confirming DC "
        "re-solve with the outage applied and the redispatch in place.",
    )


class ScopfDcResult(BaseModel):
    """Result of :func:`mambo_power.opf.solve_scopf`.

    ``status`` is ``"Optimal"`` for a secure dispatch, ``"IterationLimit"`` when the loop ran out
    of rounds (the last dispatch is reported but is not secure), or the LP's own status — an
    ``"Infeasible"`` here means *no* preventive dispatch survives every contingency at these
    ratings, which is a finding about the network, not a solver failure. When ``status !=
    "Optimal"`` the dispatch/LMP/flow rows are empty and ``message`` carries the diagnostic.
    ``n1`` is the real :func:`mambo_power.contingency.n1` of the secure dispatch and ``secure``
    is its verdict; ``security_cost`` is what the security rows added to the plain OPF's cost.
    With ``ScopfOptions.corrective`` (ADR-021), ``n1`` confirms the *immediate* post-contingency
    flows against the emergency ratings and ``corrections`` / ``corrected_secure`` the corrected
    ones against the normal ratings.
    """

    model_config = ConfigDict(extra="forbid", frozen=True, allow_inf_nan=False)

    provenance: ResultProvenance
    status: str = Field(
        description='"Optimal", "IterationLimit", or the LP status ("Infeasible", "Unbounded", '
        "or another HiGHS status string passed through verbatim)."
    )
    message: str | None = Field(default=None, description="Diagnostic when status != Optimal.")
    iterations: int = Field(ge=1, description="LP solves the constraint-generation loop ran.")
    secure: bool = Field(
        default=False,
        description="Whether the confirming contingency.n1 (and, with branch_pairs, "
        "contingency.n2) of the dispatch found no violation.",
    )
    base_objective_cost: float = Field(
        default=0.0, description="Cost of the plain (unsecured) DC-OPF, $/h."
    )
    objective_cost: float = Field(
        default=0.0, description="Cost of the secure dispatch, $/h; 0.0 when not Optimal."
    )
    security_cost: float = Field(
        default=0.0, description="objective_cost − base_objective_cost, $/h; 0.0 when not Optimal."
    )
    balance_dual: float = Field(
        default=0.0, description="System-wide energy price, $/MWh; 0.0 when not Optimal."
    )
    generators: list[GenDispatchResult] = Field(default_factory=list)
    buses: list[BusLmpResult] = Field(
        default_factory=list,
        description="LMPs whose congestion term includes the binding post-contingency rows.",
    )
    branches: list[OpfBranchFlowResult] = Field(
        default_factory=list, description="Base-case flows at the secure dispatch."
    )
    constraints: list[SecurityConstraintResult] = Field(
        default_factory=list,
        description="Every (outage, branch) pair constrained in the final solve, in the order "
        "the loop added them; empty when the plain OPF was already secure or when not Optimal.",
    )
    n1: N1Result | None = Field(
        default=None,
        description="contingency.n1 of the secure dispatch (the confirmation); None when not "
        "Optimal.",
    )
    n2: N2Result | None = Field(
        default=None,
        description="With ScopfOptions.branch_pairs (ADR-025): contingency.n2 of the secure "
        "dispatch, the pair confirmation that `secure` also requires; None otherwise.",
    )
    corrections: list[CorrectiveActionResult] = Field(
        default_factory=list,
        description="With ScopfOptions.corrective (ADR-021): the post-contingency redispatch for "
        "every outage that needed one, in the order the loop added them.",
    )
    corrected_secure: bool = Field(
        default=True,
        description="Whether every correction's confirming re-solve keeps every branch at or "
        "under its normal rating; True when there are no corrections.",
    )
    ac_check: FeasibilityReport | None = Field(
        default=None,
        description="AC-feasibility check of the secure dispatch; None unless options.ac_check "
        "is true and the solve is Optimal.",
    )
