"""The analysis-kinds registry: what the installed version can run (ADR-004, design item 6).

``KINDS`` maps a kind name (``"pf.ac"``, ``"pf.dc"``; later ``"opf.dc"``, ``"n1"``,
``"market.*"``) to a :class:`KindSpec` — the options model the request's ``options`` dict is
validated against, the result model the runner returns, and the runner itself. The registry
is the capability list a service publishes, and the contract test (AC-6) asserts every entry's
models are importable and its runner callable. Later waves add kinds with :func:`register`;
nothing else in the package changes.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from pydantic import BaseModel

from mambo_power.model import Network
from mambo_power.pf import AcOptions, solve_ac, solve_dc
from mambo_power.results import AcPowerFlowResult, DcPowerFlowResult

Runner = Callable[[Network, BaseModel | None], BaseModel]
"""Signature every kind's runner has: ``(network, validated_options_or_None) -> result``."""


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
