"""The analysis-kinds registry: what the installed version can run (ADR-004, design item 6).

``KINDS`` maps a kind name (``"pf.ac"``, ``"pf.dc"``, ``"opf.dc"``, ``"n1"``, ``"market.nodal"``,
``"market.multiperiod"``, ``"market.zonal"``, ``"market.agents"``) to a :class:`KindSpec` — the
options model the request's ``options`` dict is validated against, the result model the runner
returns, and the runner itself. The registry is the capability list a service publishes, and the
contract test (AC-6/AC-8, wave M4 AC-7, wave M5 AC-7, wave M6 AC-7, wave M7 AC-6) asserts every
entry's models are importable and its runner callable. Later waves add kinds with :func:`register`;
nothing else in the package changes.

``market.nodal`` was the first kind whose subject is not a bare ``Network``:
:func:`mambo_power.market.nodal.solve_nodal` takes a ``Scenario``. Wave M4 kept ``SolveRequest``
``network``-shaped and had ``_run_market_nodal`` wrap the incoming ``Network`` into a
``Scenario`` itself, since ``Scenario`` was then genuinely just ``network: Network``. Wave M5
(design item D3) widened ``SolveRequest`` to accept either ``network`` or ``scenario`` — now
that ``Scenario`` also carries ``periods``, a bare ``Network`` genuinely cannot supply everything
a caller may need — so that wrap moved outward, onto ``SolveRequest.resolved_scenario``
(``jobs/models.py``): every ``Runner`` now has the one ``(Scenario, options) -> result`` shape,
and reads ``.network`` off the scenario when that is all it needs (``pf.ac``, ``pf.dc``,
``opf.dc``, ``n1``); ``_run_market_nodal`` no longer wraps anything itself.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import NoReturn

from pydantic import BaseModel

from mambo_power.contingency import N1Options, n1
from mambo_power.market.agents import AgentSetError, MarketAgentsOptions, solve_agents
from mambo_power.market.multiperiod import MarketMultiperiodOptions, solve_multiperiod
from mambo_power.market.nodal import MarketNodalOptions, solve_nodal
from mambo_power.market.zonal import MarketZonalOptions, UnzonedBusError, solve_zonal
from mambo_power.model import NetworkValidationError, Scenario, ValidationIssue
from mambo_power.opf import OpfDcOptions, solve_dc_opf
from mambo_power.pf import AcOptions, solve_ac, solve_dc
from mambo_power.results import (
    AcPowerFlowResult,
    DcPowerFlowResult,
    MarketAgentsResult,
    MarketMultiperiodResult,
    MarketNodalResult,
    MarketZonalResult,
    N1Result,
    OpfDcResult,
)

Runner = Callable[[Scenario, BaseModel | None], BaseModel]
"""Signature every kind's runner has: ``(scenario, validated_options_or_None) -> result``."""


class InfeasibleLpError(Exception):
    """``opf.dc``'s, ``market.nodal``'s, ``market.multiperiod``'s, ``market.zonal``'s or
    ``market.agents``'s runner found a non-Optimal, non-Unbounded status (e.g.
    ``OpfDcResult.status == "Infeasible"``) — see :func:`_translate_non_optimal_status`.

    None of :func:`mambo_power.opf.solve_dc_opf`, :func:`mambo_power.market.nodal.solve_nodal`,
    :func:`mambo_power.market.multiperiod.solve_multiperiod`,
    :func:`mambo_power.market.zonal.solve_zonal` or
    :func:`mambo_power.market.agents.solve_agents` ever raises on a non-Optimal LP/QP status
    (their own docstrings, mirroring :func:`mambo_power.pf.solve_ac`'s
    never-raise-on-non-convergence convention) — each reports the status as data. But an
    infeasible LP has *no* dispatch at all, unlike a non-converged AC iterate which still
    carries a meaningful partial state; wave M3's design (item 7) draws that line deliberately,
    so every such job kind reports it as a structured job failure (``INFEASIBLE_LP``) rather
    than a "successful" result carrying a non-Optimal status. Raised only here, by the job
    runners — not by
    ``solve_dc_opf``/``solve_nodal``/``solve_multiperiod``/``solve_zonal``/``solve_agents``
    themselves.
    """


class UnboundedLpError(Exception):
    """``opf.dc``'s, ``market.nodal``'s, ``market.multiperiod``'s, ``market.zonal``'s or
    ``market.agents``'s runner found status ``"Unbounded"``; see :class:`InfeasibleLpError` for
    why this is a job failure rather than an ``"ok"`` result."""


def _translate_non_optimal_status(kind: str, status: str, message: str | None) -> NoReturn:
    """Translate a non-``"Optimal"`` LP/QP status into :class:`InfeasibleLpError`/
    :class:`UnboundedLpError`, for :mod:`mambo_power.jobs.run` to map to a structured failure —
    see :class:`InfeasibleLpError`. Shared by ``opf.dc``'s, ``market.nodal``'s,
    ``market.multiperiod``'s, ``market.zonal``'s and ``market.agents``'s runners (wave M3 spec
    Design item 6, reused rather than reimplemented by wave M5's S7, wave M6's S7b and wave M7's
    S7): all five wrap a welfare/cost LP with the identical two failure shapes (infeasible: no
    feasible dispatch; unbounded: every bound is finite by construction, but a malformed input
    could still trigger it), so the translation is one function, not five copies.

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
    """``(scenario, options) -> result``; ``options`` is ``None`` when ``options_model`` is."""


def _run_ac(scenario: Scenario, options: BaseModel | None) -> BaseModel:
    """Runner for ``pf.ac``: :func:`mambo_power.pf.solve_ac` with the validated options."""
    assert isinstance(options, AcOptions)  # guaranteed by run(): validated into options_model
    return solve_ac(scenario.network, options=options)


def _run_dc(scenario: Scenario, options: BaseModel | None) -> BaseModel:
    """Runner for ``pf.dc``: :func:`mambo_power.pf.solve_dc`; the kind takes no options."""
    return solve_dc(scenario.network)


def _run_opf_dc(scenario: Scenario, options: BaseModel | None) -> BaseModel:
    """Runner for ``opf.dc``: :func:`mambo_power.opf.solve_dc_opf`, then translate a non-Optimal
    ``status`` via the shared :func:`_translate_non_optimal_status` — see
    :class:`InfeasibleLpError` for why a non-Optimal status is a job failure, not an ``"ok"``
    result carrying it.
    """
    assert isinstance(options, OpfDcOptions)  # guaranteed by run(): validated into options_model
    result = solve_dc_opf(scenario.network, options=options)
    if result.status != "Optimal":
        _translate_non_optimal_status("opf.dc", result.status, result.message)
    return result


def _run_n1(scenario: Scenario, options: BaseModel | None) -> BaseModel:
    """Runner for ``n1``: :func:`mambo_power.contingency.n1`."""
    assert isinstance(options, N1Options)  # guaranteed by run(): validated into options_model
    return n1(scenario.network, options=options)


def _run_market_nodal(scenario: Scenario, options: BaseModel | None) -> BaseModel:
    """Runner for ``market.nodal``: :func:`mambo_power.market.nodal.solve_nodal` on ``scenario``
    directly — the ``Network``-to-``Scenario`` wrap now happens upstream, at
    ``SolveRequest.resolved_scenario`` (module docstring) — then translates a non-Optimal status
    via the same :func:`_translate_non_optimal_status` :func:`_run_opf_dc` calls — see
    :class:`InfeasibleLpError`.
    """
    assert isinstance(options, MarketNodalOptions)  # guaranteed by run(): options_model-validated
    result = solve_nodal(scenario, options=options)
    if result.status != "Optimal":
        _translate_non_optimal_status("market.nodal", result.status, result.message)
    return result


def _run_market_multiperiod(scenario: Scenario, options: BaseModel | None) -> BaseModel:
    """Runner for ``market.multiperiod``: :func:`mambo_power.market.multiperiod.solve_multiperiod`
    on ``scenario`` directly (``scenario.periods is None`` clears a single period — wave M5
    AC-4), then translates a non-Optimal status via the same shared
    :func:`_translate_non_optimal_status` — see :class:`InfeasibleLpError`.
    """
    assert isinstance(options, MarketMultiperiodOptions)  # run(): options_model-validated
    result = solve_multiperiod(scenario, options=options)
    if result.status != "Optimal":
        _translate_non_optimal_status("market.multiperiod", result.status, result.message)
    return result


def _run_market_zonal(scenario: Scenario, options: BaseModel | None) -> BaseModel:
    """Runner for ``market.zonal``: :func:`mambo_power.market.zonal.solve_zonal` on ``scenario``
    directly, then translates a non-Optimal status (from whichever of the chain's three stages —
    zonal clearing, redispatch, nodal reference — did not reach Optimal) via the same shared
    :func:`_translate_non_optimal_status` the other market runners use — see
    :class:`InfeasibleLpError`. ``options.corridors`` is market design data
    (:class:`~mambo_power.market.zonal.MarketZonalOptions`'s own docstring), not solved for.

    The one other thing this runner does is translate
    :class:`~mambo_power.market.zonal.UnzonedBusError` into a
    :class:`~mambo_power.model.NetworkValidationError`, which :func:`mambo_power.jobs.run` already
    maps to ``VALIDATION``. A bus carrying no zone is the caller's network data: ``Bus.zone`` is
    optional in the model and every other kind solves such a network happily, so
    :func:`~mambo_power.model.validate_network` cannot and should not reject it -- but this kind
    cannot run on it, and reporting that as ``INTERNAL`` would tell a service its engine has a bug
    when a customer mistyped a network. One issue per offending bus, at the same ``buses[i].zone``
    path and under the same ``DANGLING_REF`` code ``validate_network`` uses for a bus whose zone
    references a zone that does not exist -- the neighbouring failure, reported the same way.
    """
    assert isinstance(options, MarketZonalOptions)  # run(): options_model-validated
    try:
        result = solve_zonal(scenario, options=options)
    except UnzonedBusError as exc:
        index_of = {bus.id: index for index, bus in enumerate(scenario.network.buses)}
        raise NetworkValidationError(
            ValidationIssue(
                code="DANGLING_REF",
                path=f"buses[{index_of[bus_id]}].zone",
                message=f'bus "{bus_id}": carries no zone, and a zonal clearing needs every bus '
                "assigned to exactly one zone (set Bus.zone; every MATPOWER import populates it "
                "from the ZONE column)",
            )
            for bus_id in exc.bus_ids
        ) from exc
    if result.status != "Optimal":
        _translate_non_optimal_status("market.zonal", result.status, result.message)
    return result


def _run_market_agents(scenario: Scenario, options: BaseModel | None) -> BaseModel:
    """Runner for ``market.agents``: :func:`mambo_power.market.agents.solve_agents` on
    ``scenario`` directly, then translates a non-Optimal status via the same shared
    :func:`_translate_non_optimal_status` the other market runners use — see
    :class:`InfeasibleLpError`. ``options.strategies`` is which bidding rule each generator plays
    (market design data, like ``market.zonal``'s ``options.corridors``), not solved for; only the
    in-process ``strategies`` argument to :func:`~mambo_power.market.agents.solve_agents` is a
    seam this runner never uses, since only the config union crosses ``jobs`` (spec W2, W6).

    The one other thing this runner does is translate
    :class:`~mambo_power.market.agents.AgentSetError` -- the ``ValueError`` subclass
    :func:`~mambo_power.market.agents.solve_agents` raises up front for a caller mistake in the
    agent set (its own docstring: a strategy naming a generator the network does not have, one
    naming a generator present in the network but absent from its arrays -- out of service, or on
    a bus that is -- one naming a generator with no ``Generator.cost`` to depart from, an injected
    :class:`~mambo_power.market.strategy.MarkupStrategy` whose step is too coarse for
    ``offer_tol``, or a strategy that cannot bid on its generator's true cost at all -- a markup
    agent on one of the bundled MATPOWER cases, every generator of which is quadratic) into a
    :class:`~mambo_power.model.NetworkValidationError`, which
    :func:`mambo_power.jobs.run` already maps to ``VALIDATION`` -- the same translation
    :func:`_run_market_zonal` applies to :class:`~mambo_power.market.zonal.UnzonedBusError`, for
    the same reason: without it this is a caller mistake about how ``options.strategies`` relates
    to the network, not an engine bug, and reporting it as ``INTERNAL`` is exactly the mapping
    M6's own walk found four instances of on ``market.zonal`` (AC-6, spec provenance). An unknown
    ``StrategyConfig.kind`` and a non-positive ``max_iterations``/``offer_tol`` never reach this
    runner at all -- both fail ``MarketAgentsOptions`` validation itself (a discriminated union
    with no matching member, and ``Field(gt=0)``, respectively) and are already ``BAD_OPTIONS``
    before ``jobs.run`` ever calls a runner.

    Only that one type is caught, never bare ``ValueError``: the clearing's own
    :class:`~mambo_power.opf.dc_opf.NonConvexCostError` / ``NonConcaveBidError`` (a cost or bid
    the clearing cannot accept, raised by ``dc_opf`` under every kind that clears) are
    ``ValueError`` subclasses too, and a bare ``except ValueError`` relabelled them as
    ``VALIDATION`` at ``options.strategies`` while ``market.nodal`` reported the same network as
    ``INTERNAL`` (audit finding 2, M7 S10). Those now fall through to :func:`mambo_power.jobs.run`
    and get whatever verdict every other kind gives them. A strategy's ``NotImplementedError``
    for a cost shape it does not support is raised on its round-0 offer, which ``solve_agents``
    asks for up front and re-raises as an ``AgentSetError`` (M7 S9) -- so for every shipped
    strategy it arrives here as that type. One raised from a *later* round (a strategy whose
    support depends on its own history; nothing shipped does this) is not caught anywhere and
    reaches :func:`mambo_power.jobs.run`'s catch-all as ``INTERNAL`` -- the honest verdict for
    a strategy that changed its mind mid-run.
    """
    assert isinstance(options, MarketAgentsOptions)  # run(): options_model-validated
    try:
        result = solve_agents(scenario, options=options)
    except AgentSetError as exc:
        raise NetworkValidationError(
            [ValidationIssue(code="DANGLING_REF", path="options.strategies", message=str(exc))]
        ) from exc
    if result.status != "Optimal":
        _translate_non_optimal_status("market.agents", result.status, result.message)
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
register(
    KindSpec(
        kind="market.multiperiod",
        options_model=MarketMultiperiodOptions,
        result_model=MarketMultiperiodResult,
        runner=_run_market_multiperiod,
    )
)
register(
    KindSpec(
        kind="market.zonal",
        options_model=MarketZonalOptions,
        result_model=MarketZonalResult,
        runner=_run_market_zonal,
    )
)
register(
    KindSpec(
        kind="market.agents",
        options_model=MarketAgentsOptions,
        result_model=MarketAgentsResult,
        runner=_run_market_agents,
    )
)
