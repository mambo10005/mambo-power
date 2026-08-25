"""The analysis-kinds registry: what the installed version can run (ADR-004, design item 6).

``KINDS`` maps a kind name (``"pf.ac"``, ``"pf.dc"``, ``"opf.dc"``, ``"n1"``, ``"market.nodal"``)
to a :class:`KindSpec` — the options model the request's ``options`` dict is validated against,
the result model the runner returns, and the runner itself. The registry is the capability list
a service publishes, and the contract test (AC-6/AC-8, AC-7) asserts every entry's models are
importable and its runner callable. Later waves add kinds with :func:`register`; nothing else in
the package changes.

``market.nodal`` is the first kind whose subject is not a bare ``Network``:
:func:`mambo_power.market.nodal.solve_nodal` takes a ``Scenario``. ``SolveRequest`` stays
``network``-shaped rather than growing a parallel ``scenario`` field — ``Scenario`` is, this
wave, genuinely just ``network: Network`` and nothing else (``model/scenario.py``), so
``_run_market_nodal`` wraps the incoming ``Network`` into a ``Scenario`` itself; every ``Runner``
still has the one ``(Network, options) -> result`` shape. Revisit only if a future wave gives
``Scenario`` fields a bare ``Network`` cannot supply.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import NoReturn

from pydantic import BaseModel

from mambo_power.contingency import N1Options, n1
from mambo_power.market.nodal import MarketNodalOptions, solve_nodal
from mambo_power.model import Network, Scenario
from mambo_power.opf import OpfDcOptions, solve_dc_opf
from mambo_power.pf import AcOptions, solve_ac, solve_dc
from mambo_power.results import (
    AcPowerFlowResult,
    DcPowerFlowResult,
    MarketNodalResult,
    N1Result,
    OpfDcResult,
)

Runner = Callable[[Network, BaseModel | None], BaseModel]
"""Signature every kind's runner has: ``(network, validated_options_or_None) -> result``."""


class InfeasibleLpError(Exception):
    """``opf.dc``'s or ``market.nodal``'s runner found a non-Optimal, non-Unbounded status
    (e.g. ``OpfDcResult.status == "Infeasible"``) — see :func:`_translate_non_optimal_status`.

    Neither :func:`mambo_power.opf.solve_dc_opf` nor :func:`mambo_power.market.nodal.solve_nodal`
    ever raises on a non-Optimal LP/QP status (their own docstrings, mirroring
    :func:`mambo_power.pf.solve_ac`'s never-raise-on-non-convergence convention) — each reports
    the status as data. But an infeasible LP has *no* dispatch at all, unlike a non-converged AC
    iterate which still carries a meaningful partial state; wave M3's design (item 7) draws that
    line deliberately, so both job kinds report it as a structured job failure
    (``INFEASIBLE_LP``) rather than a "successful" result carrying a non-Optimal status. Raised
    only here, by the job runners — not by ``solve_dc_opf``/``solve_nodal`` themselves.
    """


class UnboundedLpError(Exception):
    """``opf.dc``'s or ``market.nodal``'s runner found status ``"Unbounded"``; see
    :class:`InfeasibleLpError` for why this is a job failure rather than an ``"ok"`` result."""


def _translate_non_optimal_status(kind: str, status: str, message: str | None) -> NoReturn:
    """Translate a non-``"Optimal"`` LP/QP status into :class:`InfeasibleLpError`/
    :class:`UnboundedLpError`, for :mod:`mambo_power.jobs.run` to map to a structured failure —
    see :class:`InfeasibleLpError`. Shared by ``opf.dc``'s and ``market.nodal``'s runners (wave
    spec Design item 6): both wrap a welfare/cost LP with the identical two failure shapes
    (infeasible: no feasible dispatch; unbounded: every bound is finite by construction, but a
    malformed input could still trigger it), so the translation is one function, not two copies.

    ``"Unbounded"`` maps to :class:`UnboundedLpError`; every other non-``"Optimal"`` status
    (``"Infeasible"`` and, in principle, any other HiGHS status this wave's options cannot
    actually trigger) maps to :class:`InfeasibleLpError`, since "no feasible dispatch" is the
    closer reading of an unexpected status than "unbounded objective".
    """
    if status == "Unbounded":
        raise UnboundedLpError(f"{kind} LP/QP is unbounded: {message}")
    raise InfeasibleLpError(f"{kind} LP/QP is infeasible (status={status}): {message}")


@dataclass(frozen=True)
class KindSpec:
    """One entry of :data:`KINDS`: the models and runner of an analysis kind."""

    kind: str
    """Registry key, e.g. ``"pf.ac"``."""
    options_model: type[BaseModel] | None
    """Model ``SolveRequest.options`` is validated into; ``None`` means the kind takes none."""
    result_model: type[BaseModel]
    """Type the runner returns and ``SolveResult.result`` carries for this kind."""
    runner: Runner
    """``(network, options) -> result``; ``options`` is ``None`` when ``options_model`` is."""


def _run_ac(net: Network, options: BaseModel | None) -> BaseModel:
    """Runner for ``pf.ac``: :func:`mambo_power.pf.solve_ac` with the validated options."""
    assert isinstance(options, AcOptions)  # guaranteed by run(): validated into options_model
    return solve_ac(net, options=options)


def _run_dc(net: Network, options: BaseModel | None) -> BaseModel:
    """Runner for ``pf.dc``: :func:`mambo_power.pf.solve_dc`; the kind takes no options."""
    return solve_dc(net)


def _run_opf_dc(net: Network, options: BaseModel | None) -> BaseModel:
    """Runner for ``opf.dc``: :func:`mambo_power.opf.solve_dc_opf`, then translate a non-Optimal
    ``status`` via the shared :func:`_translate_non_optimal_status` — see
    :class:`InfeasibleLpError` for why a non-Optimal status is a job failure, not an ``"ok"``
    result carrying it.
    """
    assert isinstance(options, OpfDcOptions)  # guaranteed by run(): validated into options_model
    result = solve_dc_opf(net, options=options)
    if result.status != "Optimal":
        _translate_non_optimal_status("opf.dc", result.status, result.message)
    return result


def _run_n1(net: Network, options: BaseModel | None) -> BaseModel:
    """Runner for ``n1``: :func:`mambo_power.contingency.n1`."""
    assert isinstance(options, N1Options)  # guaranteed by run(): validated into options_model
    return n1(net, options=options)


def _run_market_nodal(net: Network, options: BaseModel | None) -> BaseModel:
    """Runner for ``market.nodal``: wraps ``net`` into a ``Scenario`` (module docstring, "not a
    bare ``Network``") and calls :func:`mambo_power.market.nodal.solve_nodal`, then translates a
    non-Optimal status via the same :func:`_translate_non_optimal_status` :func:`_run_opf_dc`
    calls — see :class:`InfeasibleLpError`.
    """
    assert isinstance(options, MarketNodalOptions)  # guaranteed by run(): options_model-validated
    result = solve_nodal(Scenario(network=net), options=options)
    if result.status != "Optimal":
        _translate_non_optimal_status("market.nodal", result.status, result.message)
    return result


KINDS: dict[str, KindSpec] = {}
"""Every analysis kind the installed version can run, keyed by name (insertion order)."""


def register(spec: KindSpec) -> None:
    """Add ``spec`` to :data:`KINDS`; a kind already registered raises ``ValueError``."""
    if spec.kind in KINDS:
        raise ValueError(f'kind "{spec.kind}" is already registered')
    KINDS[spec.kind] = spec


def kinds() -> list[str]:
    """The registered kind names, sorted."""
    return sorted(KINDS)


register(
    KindSpec(kind="pf.ac", options_model=AcOptions, result_model=AcPowerFlowResult, runner=_run_ac)
)
register(KindSpec(kind="pf.dc", options_model=None, result_model=DcPowerFlowResult, runner=_run_dc))
register(
    KindSpec(
        kind="opf.dc", options_model=OpfDcOptions, result_model=OpfDcResult, runner=_run_opf_dc
    )
)
register(KindSpec(kind="n1", options_model=N1Options, result_model=N1Result, runner=_run_n1))
register(
    KindSpec(
        kind="market.nodal",
        options_model=MarketNodalOptions,
        result_model=MarketNodalResult,
        runner=_run_market_nodal,
    )
)
