"""The typed import report returned by every importer's ``load_with_report``.

Importers keep two parallel entry points: ``load_with_warnings`` returns the legacy
``list[str]`` (one ``CODE: message`` line per warning, unchanged for M1 callers) and
``load_with_report`` returns this :class:`ImportReport`, whose
:class:`~mambo_power.model.ImportWarning` entries carry the code and the ids involved so a
caller can act on them without parsing text. Both come from the same warning objects:
``report.as_strings()`` is exactly the legacy list.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from mambo_power.model import ImportWarning


@dataclass(frozen=True)
class ImportReport:
    """Every repair an importer performed, in the order it happened."""

    warnings: list[ImportWarning] = field(default_factory=list)

    @property
    def codes(self) -> set[str]:
        """The distinct warning codes present, for quick membership checks."""
        return {w.code for w in self.warnings}

    def as_strings(self) -> list[str]:
        """The legacy ``list[str]`` form: ``str(warning)`` for each warning."""
        return [str(w) for w in self.warnings]
