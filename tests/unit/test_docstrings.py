"""Every public symbol in ``mambo_power`` carries a docstring (wave M2 W10 / AC-10).

Walks the package with :mod:`pkgutil`, imports every module, and checks the module itself and
every public class, function, method and property *defined in* ``mambo_power`` (re-exports of
third-party objects are skipped). The failure message lists every offender at once.
"""

from __future__ import annotations

import importlib
import inspect
import pkgutil
from types import ModuleType
from typing import Any

import mambo_power

PACKAGE = mambo_power.__name__


def _public(name: str) -> bool:
    return not name.startswith("_")


def _ours(obj: Any) -> bool:
    module = getattr(obj, "__module__", None)
    return isinstance(module, str) and (module == PACKAGE or module.startswith(PACKAGE + "."))


def _has_doc(obj: Any) -> bool:
    doc = inspect.getdoc(obj)
    return bool(doc and doc.strip())


def _iter_modules() -> list[ModuleType]:
    modules = [mambo_power]
    for info in pkgutil.walk_packages(mambo_power.__path__, prefix=PACKAGE + "."):
        modules.append(importlib.import_module(info.name))
    return modules


def _class_members(cls: type) -> list[tuple[str, Any]]:
    """Public methods and properties defined in the class body itself (not inherited)."""
    members: list[tuple[str, Any]] = []
    for name, raw in vars(cls).items():
        if not _public(name):
            continue
        if isinstance(raw, property):
            members.append((name, raw))
        elif isinstance(raw, (staticmethod, classmethod)):
            members.append((name, raw.__func__))
        elif inspect.isfunction(raw):
            members.append((name, raw))
    return members


def find_missing_docstrings() -> list[str]:
    """Dotted names of every public module/class/function/method without a docstring."""
    missing: list[str] = []
    for module in _iter_modules():
        if not _has_doc(module):
            missing.append(module.__name__)
        for name, obj in vars(module).items():
            if not _public(name) or not _ours(obj):
                continue
            if inspect.isclass(obj):
                # Only report a class once, in the module that defines it.
                if obj.__module__ != module.__name__:
                    continue
                qualified = f"{module.__name__}.{name}"
                if not _has_doc(obj):
                    missing.append(qualified)
                for member_name, member in _class_members(obj):
                    if not _has_doc(member):
                        missing.append(f"{qualified}.{member_name}")
            elif inspect.isfunction(obj):
                if obj.__module__ != module.__name__:
                    continue
                if not _has_doc(obj):
                    missing.append(f"{module.__name__}.{name}")
    return sorted(set(missing))


def test_every_public_symbol_has_a_docstring() -> None:
    missing = find_missing_docstrings()
    if missing:
        listing = "\n".join(f"  - {name}" for name in missing)
        print(f"\n{len(missing)} public symbol(s) without a docstring:\n{listing}")
    assert not missing, f"{len(missing)} public symbol(s) without a docstring:\n" + "\n".join(
        f"  - {name}" for name in missing
    )


def test_walk_covers_every_shipped_module() -> None:
    """The walk must see the packages the wave ships, or the check above is vacuous."""
    names = {module.__name__ for module in _iter_modules()}
    for expected in (
        "mambo_power.model",
        "mambo_power.io.matpower",
        "mambo_power.io.native",
        "mambo_power.numerics",
        "mambo_power.pf",
        "mambo_power.results",
    ):
        assert expected in names, f"{expected} not reached by the package walk"
