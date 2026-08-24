"""``run`` and ``run_json``: the one pure entry point every analysis kind is reachable through.

Pipeline of :func:`run` (design item 6):

1. look the kind up in :data:`~mambo_power.jobs.KINDS` — miss → ``UNKNOWN_KIND``;
2. validate ``request.options`` into the kind's options model — ``BAD_OPTIONS`` (pydantic
   errors in ``error.details``); a kind without an options model rejects any key;
3. re-check the network's invariants with :func:`mambo_power.model.validate_network` —
   ``VALIDATION`` with every issue (a ``Network`` validates on construction but not on
   mutation, so ``run`` does not trust its input);
4. call the runner under ``warnings.catch_warnings(record=True)`` and wrap what it raises:
   :class:`~mambo_power.model.NetworkValidationError` → ``VALIDATION`` with ``.issues``;
   :class:`~mambo_power.numerics.NoSlackGeneratorError` → ``NO_SLACK_GENERATOR``;
   :class:`~mambo_power.numerics.UnsolvableNetworkError` → ``UNSOLVABLE_NETWORK`` (a valid
   network the numerics it was handed to cannot solve, e.g. DC on an ``x == 0`` branch —
   user data, not a solver bug);
   :class:`~mambo_power.jobs.registry.InfeasibleLpError`/:class:`~mambo_power.jobs.registry.
   UnboundedLpError` → ``INFEASIBLE_LP``/``UNBOUNDED_LP`` (the ``opf.dc`` runner's own
   translation of a non-Optimal :class:`~mambo_power.results.OpfDcResult.status`; unlike
   ``pf.ac``'s non-convergence, an infeasible/unbounded LP has no dispatch at all, so it is a
   structured failure rather than an ``"ok"`` result); anything else → ``INTERNAL`` with
   ``"ExceptionType: message"``;
5. check the runner returned the kind's ``result_model`` (else ``INTERNAL``), copy its
   provenance and the captured warnings onto the :class:`~mambo_power.jobs.SolveResult`.

No exception crosses ``run``: a runner whose result class is outside the ``result`` union
is an ``INTERNAL`` failure too. A solve
that does not converge is not a failure — ``solve_ac`` returns ``converged = False`` rather
than raising, and that result is passed through with ``status = "ok"``.

Warnings are captured with ``warnings.catch_warnings``, which swaps the *process-global*
filter list for the duration of the runner; two ``run`` calls on different threads can
therefore see each other's warnings (Python ≥ 3.14 makes the context thread-local). Pure
means "a function of its input", which holds; warning attribution across threads is the one
caveat, and a worker process per job (the SaaS's deployment shape) does not hit it.
"""

from __future__ import annotations

import json
import time
import warnings
from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel, ValidationError

import mambo_power
from mambo_power.jobs.models import ResultModel, SolveRequest, SolveResult, StructuredError
from mambo_power.jobs.registry import KINDS, InfeasibleLpError, UnboundedLpError
from mambo_power.model import NetworkValidationError, ValidationIssue, validate_network
from mambo_power.numerics import NoSlackGeneratorError, UnsolvableNetworkError
from mambo_power.results import ResultProvenance

NO_SOLVER = "none"
"""``provenance.solver`` on a failed result: no linear-algebra backend ran to completion."""


def _minimal_provenance(
    kind: str, started_at: datetime, clock: float, options: dict[str, Any]
) -> ResultProvenance | None:
    if not kind:
        return None
    return ResultProvenance(
        engine="mambo-power",
        version=mambo_power.__version__,
        kind=kind,
        solver=NO_SOLVER,
        started_at=started_at,
        elapsed_s=time.perf_counter() - clock,
        options=options,
    )


def _pydantic_details(exc: ValidationError) -> list[dict[str, Any]]:
    records = exc.errors(include_url=False, include_context=False, include_input=False)
    return [{**r, "loc": list(r["loc"])} for r in records]


def _failed(
    *,
    kind: str,
    job_id: str | None,
    code: str,
    message: str,
    started_at: datetime,
    clock: float,
    issues: list[ValidationIssue] | None = None,
    details: list[dict[str, Any]] | None = None,
    options: dict[str, Any] | None = None,
    captured: list[str] | None = None,
) -> SolveResult:
    return SolveResult(
        kind=kind,
        job_id=job_id,
        status="failed",
        error=StructuredError(code=code, message=message, issues=issues, details=details),
        provenance=_minimal_provenance(kind, started_at, clock, options or {}),
        warnings=captured or [],
    )


def _messages(caught: list[warnings.WarningMessage]) -> list[str]:
    return [f"{w.category.__name__}: {w.message}" for w in caught]


def run(request: SolveRequest) -> SolveResult:
    """Run ``request`` and return a :class:`~mambo_power.jobs.SolveResult`; never raises.

    See the module docstring for the pipeline and the failure codes. On success
    ``result`` is the kind's result model, ``provenance`` is the stamp the solver put on it,
    and ``warnings`` lists every warning the solve emitted (they are captured, not shown).
    """
    started_at = datetime.now(UTC)
    clock = time.perf_counter()
    kind, job_id = request.kind, request.job_id

    def fail(code: str, message: str, **extra: Any) -> SolveResult:
        return _failed(
            kind=kind,
            job_id=job_id,
            code=code,
            message=message,
            started_at=started_at,
            clock=clock,
            **extra,
        )

    spec = KINDS.get(kind)
    if spec is None:
        known = ", ".join(sorted(KINDS))
        return fail("UNKNOWN_KIND", f'unknown kind "{kind}"; registered kinds: {known}')

    options: BaseModel | None = None
    if spec.options_model is not None:
        try:
            options = spec.options_model.model_validate(request.options)
        except ValidationError as exc:
            return fail(
                "BAD_OPTIONS",
                f'options for kind "{kind}" are invalid: {exc}',
                details=_pydantic_details(exc),
            )
    elif request.options:
        keys = ", ".join(sorted(request.options))
        return fail("BAD_OPTIONS", f'kind "{kind}" takes no options; got: {keys}')
    run_options = options.model_dump() if options is not None else {}

    issues = validate_network(request.network)
    if issues:
        error = NetworkValidationError(issues)
        return fail("VALIDATION", str(error), issues=issues, options=run_options)

    raw: BaseModel | None = None
    failure: tuple[str, str, list[ValidationIssue] | None] | None = None
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        try:
            raw = spec.runner(request.network, options)
        except NetworkValidationError as exc:
            failure = ("VALIDATION", str(exc), exc.issues)
        except NoSlackGeneratorError as exc:
            failure = ("NO_SLACK_GENERATOR", str(exc), None)
        except UnsolvableNetworkError as exc:
            failure = ("UNSOLVABLE_NETWORK", str(exc), None)
        except InfeasibleLpError as exc:
            failure = ("INFEASIBLE_LP", str(exc), None)
        except UnboundedLpError as exc:
            failure = ("UNBOUNDED_LP", str(exc), None)
        except Exception as exc:  # noqa: BLE001 — the boundary's whole point
            failure = ("INTERNAL", f"{type(exc).__name__}: {exc}", None)
    captured = _messages(caught)

    if failure is not None:
        code, message, failure_issues = failure
        return fail(code, message, issues=failure_issues, options=run_options, captured=captured)
    if type(raw) is not spec.result_model:
        return fail(
            "INTERNAL",
            f'runner for kind "{kind}" returned {type(raw).__name__}, '
            f"expected {spec.result_model.__name__}",
            options=run_options,
            captured=captured,
        )
    if not isinstance(raw, ResultModel):
        return fail(
            "INTERNAL",
            f'result model {type(raw).__name__} of kind "{kind}" is not in SolveResult.result',
            options=run_options,
            captured=captured,
        )
    provenance = getattr(raw, "provenance", None)
    if not isinstance(provenance, ResultProvenance):
        provenance = _minimal_provenance(kind, started_at, clock, run_options)
    return SolveResult(
        kind=kind, job_id=job_id, status="ok", result=raw, provenance=provenance, warnings=captured
    )


def _peek(text: str) -> tuple[str, str | None]:
    """Best-effort ``(kind, job_id)`` from request text that failed to validate."""
    try:
        payload = json.loads(text)
    except (ValueError, RecursionError):
        # best-effort by definition — a deeply nested payload can blow the recursion limit
        # inside json.loads itself (not just pydantic's own depth check), and _peek must
        # never be the thing that lets an exception cross run_json's boundary.
        return "", None
    if not isinstance(payload, dict):
        return "", None
    kind, job_id = payload.get("kind"), payload.get("job_id")
    return (kind if isinstance(kind, str) else ""), (job_id if isinstance(job_id, str) else None)


def run_json(text: str) -> str:
    """JSON in, JSON out: parse ``text`` as a :class:`~mambo_power.jobs.SolveRequest`, ``run`` it.

    Returns ``SolveResult.model_dump_json()``. A request that does not parse is a failed result
    too: an invalid network → ``VALIDATION`` with every issue; malformed JSON or a request of
    the wrong shape → ``BAD_REQUEST`` with the pydantic errors in ``error.details``. The kind
    and ``job_id`` are echoed when they can be read from the text (``kind = ""`` and no
    provenance otherwise).
    """
    started_at = datetime.now(UTC)
    clock = time.perf_counter()
    try:
        request = SolveRequest.model_validate_json(text)
    except NetworkValidationError as exc:
        kind, job_id = _peek(text)
        return _failed(
            kind=kind,
            job_id=job_id,
            code="VALIDATION",
            message=str(exc),
            issues=exc.issues,
            started_at=started_at,
            clock=clock,
        ).model_dump_json()
    except ValidationError as exc:
        kind, job_id = _peek(text)
        return _failed(
            kind=kind,
            job_id=job_id,
            code="BAD_REQUEST",
            message=f"request is not a valid SolveRequest: {exc}",
            details=_pydantic_details(exc),
            started_at=started_at,
            clock=clock,
        ).model_dump_json()
    except Exception as exc:  # noqa: BLE001 — nothing crosses the boundary
        kind, job_id = _peek(text)
        return _failed(
            kind=kind,
            job_id=job_id,
            code="INTERNAL",
            message=f"{type(exc).__name__}: {exc}",
            started_at=started_at,
            clock=clock,
        ).model_dump_json()
    return run(request).model_dump_json()
