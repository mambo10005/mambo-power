"""Request, result and error models of the job surface (ADR-004; wave M2 W6).

All three are pydantic v2 models with ``extra="forbid"`` and exact JSON round-trip, so the
body of an HTTP request *is* a :class:`SolveRequest` and the body of the response *is* a
:class:`SolveResult` — no translation layer.

**How ``SolveResult.result`` is typed.** Its annotation is the closed union of the registered
kinds' result models (``AcPowerFlowResult | DcPowerFlowResult`` in M2, widened to add
``OpfDcResult | N1Result`` in M3, ``MarketNodalResult`` in M4, ``MarketMultiperiodResult`` in
M5, ``MarketZonalResult`` in M6). The type is *not* inferred from the payload's shape: a
``model_validator(mode="before")`` looks the request ``kind`` up in :data:`~mambo_power.jobs.KINDS`
and validates a dict ``result``
with exactly that kind's ``result_model``; a second validator (``mode="after"``) then checks
that the instance type equals the kind's model, and that ``status`` agrees with which of
``result`` / ``error`` is present. A pydantic discriminated union was not used because the
discriminator (``kind``) lives on the parent, not inside the result, and because the power-flow
results do not carry a tag field of their own. A wave that registers a new kind widens the union
annotation — the ``after`` validator will refuse a result whose class is not the kind's
``result_model``, and the field validation refuses a class outside the union, so the two cannot
silently drift apart.
"""

from __future__ import annotations

from typing import Any, Literal, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from mambo_power.jobs.registry import KINDS
from mambo_power.model import Network, Scenario, ValidationIssue
from mambo_power.results import (
    AcPowerFlowResult,
    DcPowerFlowResult,
    MarketMultiperiodResult,
    MarketNodalResult,
    MarketZonalResult,
    N1Result,
    OpfDcResult,
    ResultProvenance,
)

ResultModel = (
    AcPowerFlowResult
    | DcPowerFlowResult
    | OpfDcResult
    | N1Result
    | MarketNodalResult
    | MarketMultiperiodResult
    | MarketZonalResult
)
"""The closed union of result types a ``SolveResult`` can carry (one per registered kind)."""

FailureCode = Literal[
    "UNKNOWN_KIND",
    "BAD_REQUEST",
    "BAD_OPTIONS",
    "VALIDATION",
    "NO_SLACK_GENERATOR",
    "UNSOLVABLE_NETWORK",
    "INFEASIBLE_LP",
    "UNBOUNDED_LP",
    "INTERNAL",
]
"""The codes :func:`mambo_power.jobs.run` / :func:`mambo_power.jobs.run_json` emit (M2, M3)."""


class StructuredError(BaseModel):
    """A failure as data: stable ``code``, readable ``message``, optional structured detail.

    ``issues`` is the network's full :class:`~mambo_power.model.ValidationIssue` list for
    ``VALIDATION`` failures (every problem in one response); ``details`` is the pydantic error
    list (``loc``, ``msg``, ``type``) for ``BAD_OPTIONS`` and ``BAD_REQUEST``. ``code`` is a plain
    string so later kinds can add codes without a schema change; M2's are
    :data:`FailureCode`.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    code: str = Field(min_length=1, description="Stable failure code, e.g. ``VALIDATION``.")
    message: str = Field(description="Human-readable description; the exception text when any.")
    issues: list[ValidationIssue] | None = Field(
        default=None, description="Every network validation issue, for ``VALIDATION``."
    )
    details: list[dict[str, Any]] | None = Field(
        default=None,
        description="pydantic error records (``loc``, ``msg``, ``type``) for bad options/requests.",
    )


class SolveRequest(BaseModel):
    """One analysis to run: the kind, the subject (inline) and the kind's options.

    ``network``/``scenario`` — wave M5 design item D3 (2026-08-25) — exactly one must be given:
    ``network`` is the original, still-supported shape (a bare
    :class:`~mambo_power.model.Network`), and every pre-existing
    ``SolveRequest(kind=..., network=...)`` construction and serialized JSON keeps working
    unchanged. ``scenario`` is the new form, for a genuine multi-period
    :class:`~mambo_power.model.Scenario` (``market.multiperiod``) or simply an explicit
    single-period one. Neither or both given is a ``ValueError`` (a pydantic error at
    construction time; :func:`mambo_power.jobs.run_json` turns it into ``BAD_REQUEST``).
    :attr:`resolved_scenario` is what every :class:`~mambo_power.jobs.registry.Runner` actually
    receives — ``scenario`` itself, or ``network`` wrapped as ``Scenario(network=network)``
    (single-period, ``periods=None``, exactly ``market.nodal``'s and every T=1 kind's existing
    semantics) — never the raw fields, so widening this model changes no runner's contract.

    ``options`` is validated by :func:`mambo_power.jobs.run` against the kind's options model
    (``AcOptions`` for ``pf.ac``; ``pf.dc`` takes none) — unknown keys are a ``BAD_OPTIONS``
    failure, never silently ignored. ``job_id`` is an opaque caller tag echoed on the result.
    """

    model_config = ConfigDict(extra="forbid")

    kind: str = Field(min_length=1, description="A key of ``jobs.KINDS``, e.g. ``pf.ac``.")
    network: Network | None = Field(
        default=None, description="The network to solve; mutually exclusive with ``scenario``."
    )
    scenario: Scenario | None = Field(
        default=None, description="The scenario to solve; mutually exclusive with ``network``."
    )
    options: dict[str, Any] = Field(
        default_factory=dict, description="Kind-specific options, validated by ``run``."
    )
    job_id: str | None = Field(default=None, description="Caller's correlation id, echoed back.")

    @model_validator(mode="after")
    def _exactly_one_of_network_or_scenario(self) -> Self:
        if (self.network is None) == (self.scenario is None):
            raise ValueError(
                "SolveRequest requires exactly one of `network` or `scenario`, got "
                f"network={'given' if self.network is not None else None}, "
                f"scenario={'given' if self.scenario is not None else None}"
            )
        return self

    @property
    def resolved_scenario(self) -> Scenario:
        """This request as a :class:`~mambo_power.model.Scenario`: ``scenario`` itself when
        given, or ``network`` wrapped as ``Scenario(network=network)`` — single-period,
        ``periods=None``. Recomputed on every access, not cached, so a ``network`` mutated in
        place after construction (``request.network.branches[0].to_bus = ...`` — ``Network``
        does not re-validate on mutation on its own) is reflected here too, exactly as it was
        when ``jobs.registry._run_market_nodal`` did this same wrap internally pre-M5.

        Constructing the wrapping ``Scenario`` *does* re-run ``Network``'s own after-validator —
        nested-model construction re-checks every invariant (``model/scenario.py``'s own
        docstring) — so this can raise :class:`~mambo_power.model.NetworkValidationError` for a
        ``network`` mutated into an invalid state; :func:`mambo_power.jobs.run` catches that
        itself, immediately, precisely so it stays a graceful ``VALIDATION`` failure rather than
        an exception crossing its boundary. A directly-supplied ``scenario`` is returned as-is,
        with no such re-check — mirroring ``network``'s own no-revalidation-on-mutation rule.
        """
        if self.scenario is not None:
            return self.scenario
        assert self.network is not None  # guaranteed by _exactly_one_of_network_or_scenario
        return Scenario(network=self.network)


class SolveResult(BaseModel):
    """Outcome of :func:`mambo_power.jobs.run`: a typed result or a structured error, never both.

    ``status == "ok"`` carries ``result`` (the kind's result model) and its ``provenance``;
    ``status == "failed"`` carries ``error`` and, when the kind was readable, a minimal
    provenance (kind, version, elapsed time, ``solver = "none"``). ``warnings`` holds every
    warning emitted during the solve as ``"Category: message"`` strings — for a network with
    conflicting generator setpoints that is the ``SetpointConflictWarning``. A power flow that
    did not converge is ``status == "ok"`` with ``result.converged == False``: the partial
    state is a result, not a failure.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    kind: str = Field(description='Echo of the request kind (``""`` when unreadable).')
    job_id: str | None = Field(default=None, description="Echo of the request ``job_id``.")
    status: Literal["ok", "failed"] = Field(description="Outcome.")
    result: ResultModel | None = Field(
        default=None, description='The kind\'s result model; present when ``status == "ok"``.'
    )
    error: StructuredError | None = Field(
        default=None, description='Present when ``status == "failed"``.'
    )
    provenance: ResultProvenance | None = Field(
        default=None, description="The result's stamp, or a minimal one on failure."
    )
    warnings: list[str] = Field(
        default_factory=list, description="Warnings emitted during the solve, as strings."
    )

    @model_validator(mode="before")
    @classmethod
    def _dispatch_result_by_kind(cls, data: Any) -> Any:
        # A dict ``result`` is validated with the *kind's* result model, never by shape.
        if isinstance(data, dict):
            kind, result = data.get("kind"), data.get("result")
            if isinstance(result, dict) and isinstance(kind, str) and kind in KINDS:
                data = {**data, "result": KINDS[kind].result_model.model_validate(result)}
        return data

    @model_validator(mode="after")
    def _consistent(self) -> Self:
        if self.result is not None:
            spec = KINDS.get(self.kind)
            if spec is None:
                raise ValueError(f'a result cannot be carried for unknown kind "{self.kind}"')
            if type(self.result) is not spec.result_model:
                raise ValueError(
                    f'result for kind "{self.kind}" must be {spec.result_model.__name__}, '
                    f"got {type(self.result).__name__}"
                )
        if self.status == "ok" and (self.result is None or self.error is not None):
            raise ValueError('status "ok" requires a result and no error')
        if self.status == "failed" and (self.error is None or self.result is not None):
            raise ValueError('status "failed" requires an error and no result')
        return self
