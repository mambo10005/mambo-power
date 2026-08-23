"""Stateless, JSON-serialisable job surface: ``run(SolveRequest) -> SolveResult`` (ADR-004, W6).

The one function every analysis kind is reachable through, safe to call from a notebook, a
CLI, a worker or an HTTP handler — a service adds transport and persistence, never semantics.
``run`` is a pure function of its input; every failure is a ``status = "failed"`` result with a
:class:`StructuredError`, never an exception; :data:`KINDS` is the capability list of the
installed version. The module-level entry points (``pf.solve_ac``, ``pf.solve_dc``) remain the
notebook-friendly API and are what the registered runners call.
"""

from mambo_power.jobs.models import (
    FailureCode,
    ResultModel,
    SolveRequest,
    SolveResult,
    StructuredError,
)
from mambo_power.jobs.registry import KINDS, KindSpec, Runner, kinds, register
from mambo_power.jobs.run import run, run_json

__all__ = [
    "KINDS",
    "FailureCode",
    "KindSpec",
    "ResultModel",
    "Runner",
    "SolveRequest",
    "SolveResult",
    "StructuredError",
    "kinds",
    "register",
    "run",
    "run_json",
]
