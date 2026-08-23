"""AC-8: the API reference covers every public symbol (audit m2-audit.md §3: ``pf.ac_newton``
was missing entirely — ``newton``, ``newton_raphson``, ``flat_start``, ``specified_injection``,
``allocate_generation`` had no ``:::`` block anywhere and no anchor in the built site).

Walks every ``docs/api/*.md`` page for its ``::: mambo_power....`` directives, then walks each
top-level package's submodules with :mod:`pkgutil` (mirroring how ``tests/unit/test_docstrings.py``
walks the whole package). A submodule needs no directive of its own if every public class/function
*defined in it* is re-exported into a module that already has one — mkdocstrings documents a
re-exported member wherever it is rendered, even under ``show_submodules: false`` (verified: the
built site already carries ``model.islands``' and ``numerics.roles``' symbols this way — the gap
was specific to ``pf.ac_newton``, which is not re-exported anywhere).
"""

from __future__ import annotations

import importlib
import inspect
import pkgutil
import re
from pathlib import Path

DOCS_API = Path(__file__).parents[2] / "docs" / "api"
PACKAGES = ("model", "io", "numerics", "pf", "results", "jobs")
DIRECTIVE_RE = re.compile(r"^:::\s+(mambo_power(?:\.\w+)*)\s*$")


def _directive_targets() -> set[str]:
    """Every dotted name named by a ``:::`` directive across all API pages."""
    targets: set[str] = set()
    for page in DOCS_API.glob("*.md"):
        for line in page.read_text(encoding="utf-8").splitlines():
            match = DIRECTIVE_RE.match(line.strip())
            if match:
                targets.add(match.group(1))
    return targets


def _public_names_defined_in(module: object) -> list[str]:
    """Public classes/functions whose ``__module__`` is this module itself (not imported)."""
    names = []
    for name, obj in vars(module).items():
        if name.startswith("_"):
            continue
        if (inspect.isclass(obj) or inspect.isfunction(obj)) and getattr(
            obj, "__module__", None
        ) == module.__name__:
            names.append(name)
    return names


def _find_gaps() -> list[str]:
    targets = _directive_targets()
    documented = [importlib.import_module(name) for name in sorted(targets)]
    gaps: list[str] = []
    for pkg_name in PACKAGES:
        pkg = importlib.import_module(f"mambo_power.{pkg_name}")
        for info in pkgutil.iter_modules(pkg.__path__, prefix=f"mambo_power.{pkg_name}."):
            if info.name.rsplit(".", 1)[-1].startswith("_"):
                continue  # private implementation module (e.g. pf._common) — not public API
            if info.name in targets:
                continue  # named directly
            sub = importlib.import_module(info.name)
            uncovered = [
                name
                for name in _public_names_defined_in(sub)
                if not any(getattr(mod, name, None) is getattr(sub, name) for mod in documented)
            ]
            if uncovered:
                gaps.append(f"{info.name}: {', '.join(sorted(uncovered))}")
    return gaps


def test_every_public_symbol_is_reachable_from_an_api_page() -> None:
    gaps = _find_gaps()
    assert not gaps, "submodule symbols missing from docs/api pages:\n" + "\n".join(gaps)


def test_walk_covers_every_shipped_package() -> None:
    """The walk must see the packages the API reference is supposed to cover, or the check
    above is vacuous."""
    for pkg_name in PACKAGES:
        pkg = importlib.import_module(f"mambo_power.{pkg_name}")
        assert list(pkgutil.iter_modules(pkg.__path__)), f"{pkg_name} has no submodules to walk"
