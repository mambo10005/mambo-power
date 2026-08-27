"""griffe extension: publish pydantic ``Field(description=...)`` text as attribute documentation.

The package documents two kinds of result object in two different ways. The dataclasses under
``mambo_power.opf`` carry a PEP-257 attribute docstring under each field, which griffe reads
directly, so ``api/opf`` renders one entry per attribute. The pydantic models under
``mambo_power.results`` (and ``mambo_power.model``) instead put their prose in
``Field(description=...)``, which is an argument to a function call -- not a docstring. griffe
sees an undocumented attribute, ``show_if_no_docstring: false`` drops it, and the description
reaches the site only as syntax-highlighted Python inside the source view.

This extension closes that gap without touching the source: after a package is loaded it imports
each module that declares pydantic models, reads ``model_fields[name].description`` from the real
class, and attaches it to the corresponding griffe ``Attribute`` as its docstring. Fields that
already carry an attribute docstring are left alone -- an explicit docstring always wins.

Registered from ``mkdocs.yml`` under the mkdocstrings python handler's ``options.extensions``.
"""

from __future__ import annotations

import importlib
from typing import Any

import griffe

_logger = griffe.get_logger(__name__)


def _model_fields(cls: griffe.Class) -> dict[str, Any] | None:
    """Return the real class's ``model_fields`` if it is a pydantic model, else ``None``."""
    module_path = cls.module.path
    try:
        module = importlib.import_module(module_path)
        obj = getattr(module, cls.name, None)
    except Exception as exc:  # pragma: no cover - a broken import must not fail the build
        _logger.debug(f"pydantic_fields: could not import {module_path}: {exc}")
        return None
    fields = getattr(obj, "model_fields", None)
    # ``model_fields`` on a non-model is anything at all; require the pydantic shape.
    if not isinstance(fields, dict) or not isinstance(obj, type):
        return None
    if not any(base.__name__ == "BaseModel" for base in obj.__mro__):
        return None
    return fields


def _default_repr(field: Any) -> str | None:
    """The field's real default as source text, or ``None`` when it has no plain default.

    A pydantic field's griffe ``value`` is the whole ``Field(...)`` call, which renders in the
    attribute signature as a wall of constraint keywords and a duplicate of the description.
    Replacing it with the actual default is both the useful thing to show and the thing that
    keeps the signature ASCII: mkdocstrings formats every signature by piping it to an external
    formatter's stdin, which on Windows encodes cp1252, so a non-Latin-1 character anywhere in a
    rendered value crashes the build (``pf.AcPowerFlowOptions.tol``'s description carries U+221E).
    """
    default = getattr(field, "default", None)
    if default is None or type(default).__name__ == "PydanticUndefinedType":
        return None
    try:
        return repr(default)
    except Exception:  # pragma: no cover - a pathological __repr__ must not fail the build
        return None


def _document(cls: griffe.Class) -> int:
    """Document ``cls``'s own pydantic fields. Returns how many descriptions were attached."""
    fields = _model_fields(cls)
    if not fields:
        return 0
    attached = 0
    for name, member in cls.members.items():
        if not isinstance(member, griffe.Attribute) or name not in fields:
            continue
        field = fields[name]
        # The ``Field(...)`` call is never worth rendering as a value; the default is.
        if member.value is not None and str(member.value).startswith("Field("):
            member.value = _default_repr(field)
        if member.docstring is not None:
            continue  # an explicit attribute docstring always wins
        description = getattr(field, "description", None)
        if not description:
            continue
        member.docstring = griffe.Docstring(description, parent=member)
        attached += 1
    return attached


class PydanticFieldDescriptions(griffe.Extension):
    """Turn every pydantic field's ``description=`` into the attribute's griffe docstring."""

    def on_package(self, *, pkg: griffe.Module, **kwargs: Any) -> None:
        """Walk the loaded package once and document every pydantic model in it."""
        attached = 0
        stack: list[griffe.Module | griffe.Class] = [pkg]
        while stack:
            current = stack.pop()
            for member in current.members.values():
                if isinstance(member, griffe.Module):
                    stack.append(member)
                elif isinstance(member, griffe.Class):
                    stack.append(member)
                    attached += _document(member)
        _logger.info(f"pydantic_fields: documented {attached} field(s) in {pkg.path}")
