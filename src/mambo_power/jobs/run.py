"""``run`` and ``run_json``: the one pure entry point every analysis kind is reachable through.

Pipeline of :func:`run` (design item 6):

1. look the kind up in :data:`~mambo_power.jobs.KINDS` — miss → ``UNKNOWN_KIND``;
2. validate ``request.options`` into the kind's options model — ``BAD_OPTIONS`` (pydantic
   errors in ``error.details``); a kind without an options model rejects any key;
3. resolve ``request`` to a :class:`~mambo_power.model.Scenario` via
   ``request.resolved_scenario`` (wave M5 D3: ``scenario`` as given, or ``network`` wrapped) and
   re-check its network's invariants with :func:`mambo_power.model.validate_network` —
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

    try:
        scenario = request.resolved_scenario
    except NetworkValidationError as exc:
        # request.network was mutated in place into an invalid network after construction
        # (Network does not re-validate on mutation) and resolved_scenario's wrap of it into a
        # fresh Scenario *does* re-run Network's own after-validator (Scenario's own docstring:
        # nested-model construction re-checks every invariant, dangling refs included) -- so the
        # wrap itself can raise where a bare `request.network` never did. Caught here, in the
        # same shape as the explicit validate_network() check just below, so this remains a
        # graceful VALIDATION failure rather than an exception crossing run()'s boundary.
        return fail("VALIDATION", str(exc), issues=exc.issues, options=run_options)
    issues = validate_network(scenario.network)
    if issues:
        error = NetworkValidationError(issues)
        return fail("VALIDATION", str(error), issues=issues, options=run_options)

    raw: BaseModel | None = None
    failure: tuple[str, str, list[ValidationIssue] | None] | None = None
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        try:
            raw = spec.runner(scenario, options)
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


class DuplicateKeyError(ValueError):
    """A JSON object in a ``run_json`` request repeats a key.

    ``json.loads`` keeps the last value silently, so a request that names one generator twice
    under ``options.strategies`` -- or repeats ``kind``, or a field inside ``network`` -- would
    run as if only the last spelling had been written. Every kind shares this boundary, so the
    check is here, before pydantic, and the failure is ``BAD_REQUEST`` naming the key and its
    path.
    """


def _reject_duplicate_keys(text: str) -> None:
    """Raise :class:`DuplicateKeyError` if any object in ``text`` repeats a key, at any depth."""

    def hook(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        out: dict[str, Any] = {}
        for key, value in pairs:
            if key in out:
                raise DuplicateKeyError(key)
            out[key] = value
        return out

    # The path is found on a second pass only when there is something to report.
    try:
        json.loads(text, object_pairs_hook=hook)
    except DuplicateKeyError as exc:
        key = exc.args[0]
        path = _path_to_duplicate(text, key)
        raise DuplicateKeyError(f'duplicate key "{key}" at {path}') from None
    except Exception:  # noqa: BLE001 — malformed or too-deep JSON: pydantic reports it, as before
        return


def _path_to_duplicate(text: str, key: str) -> str:
    """Dotted path of the first object that repeats ``key`` (``options.strategies``, ``request``
    for the top level)."""
    found: list[str] = []

    class _Node(dict[str, Any]):
        path: str = ""

    def hook(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        node = _Node()
        for k, v in pairs:
            if k in node and not found:
                found.append(k)
                node["__dup__"] = True
            node[k] = v
        return node

    try:
        root = json.loads(text, object_pairs_hook=hook)
    except Exception:  # noqa: BLE001
        return "request"

    def walk(node: Any, path: str) -> str | None:
        if isinstance(node, dict):
            if node.get("__dup__") and key in node:
                return path or "request"
            for k, v in node.items():
                hit = walk(v, f"{path}.{k}" if path else k)
                if hit:
                    return hit
        elif isinstance(node, list):
            for i, v in enumerate(node):
                hit = walk(v, f"{path}[{i}]")
                if hit:
                    return hit
        return None

    return walk(root, "") or "request"


def run_json(text: str) -> str:
    """JSON in, JSON out: parse ``text`` as a :class:`~mambo_power.jobs.SolveRequest`, ``run`` it.

    Returns ``SolveResult.model_dump_json()``. A request that does not parse is a failed result
    too: an invalid network → ``VALIDATION`` with every issue; malformed JSON or a request of
    the wrong shape → ``BAD_REQUEST`` with the pydantic errors in ``error.details``; a JSON
    object repeating a key at any depth → ``BAD_REQUEST`` naming the key and its path, for every
    kind, because ``json`` would otherwise keep the last value silently. The kind
    and ``job_id`` are echoed when they can be read from the text (``kind = ""`` and no
    provenance otherwise).
    """
    started_at = datetime.now(UTC)
    clock = time.perf_counter()
    try:
        _reject_duplicate_keys(text)
        request = SolveRequest.model_validate_json(text)
    except DuplicateKeyError as exc:
        kind, job_id = _peek(text)
        return _failed(
            kind=kind,
            job_id=job_id,
            code="BAD_REQUEST",
            message=f"request is not a valid SolveRequest: {exc}",
            started_at=started_at,
            clock=clock,
        ).model_dump_json()
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
