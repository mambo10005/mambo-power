"""The typed reports returned by importers (``load_with_report``) and exporters (wave M8).

Importers keep two parallel entry points: ``load_with_warnings`` returns the legacy
``list[str]`` (one ``CODE: message`` line per warning, unchanged for M1 callers) and
``load_with_report`` returns an :class:`ImportReport`, whose
:class:`~mambo_power.model.ImportIssue` entries carry the code and the ids involved so a
caller can act on them without parsing text. Both come from the same warning objects:
``report.as_strings()`` is exactly the legacy list.

Exporters return an :class:`ExportReport` of the same shape. The rule both share (M8 design
item D1): **an empty report means the conversion was lossless.** Anything dropped, approximated
or repaired is an issue naming the element id (``bus_ids`` / ``element_ids``) and, in the
message, the field concerned. Importers and exporters neither log nor print; the report is
the only channel.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from mambo_power.model import ImportIssue

ConversionIssue = ImportIssue
"""One issue in either report. The record is :class:`~mambo_power.model.ImportIssue` — its
name predates exporters; the shape (``code``, ``message``, ``bus_ids``, ``element_ids``) and the
closed :data:`~mambo_power.model.ImportIssueCode` set are shared by both directions."""


class ReportError(ValueError):
    """Raised by :meth:`_Report.raise_on_error` when a report carries errors."""

    def __init__(self, report: _Report) -> None:
        self.report = report
        super().__init__("; ".join(str(e) for e in report.errors))


@dataclass(frozen=True)
class _Report:
    warnings: list[ConversionIssue] = field(default_factory=list)
    """Repairs and drops the conversion carried out anyway, in the order they happened."""
    errors: list[ConversionIssue] = field(default_factory=list)
    """Issues the caller must not ignore; :meth:`raise_on_error` turns them into an exception."""

    @property
    def codes(self) -> set[str]:
        """The distinct codes present (warnings and errors), for quick membership checks."""
        return {w.code for w in self.warnings} | {e.code for e in self.errors}

    @property
    def has_errors(self) -> bool:
        return bool(self.errors)

    def as_strings(self) -> list[str]:
        """The legacy ``list[str]`` form: ``str(issue)`` for each warning, then each error."""
        return [str(w) for w in self.warnings] + [str(e) for e in self.errors]

    def raise_on_error(self) -> None:
        """Raise :class:`ReportError` if any errors were recorded; a no-op otherwise."""
        if self.errors:
            raise ReportError(self)


@dataclass(frozen=True)
class ImportReport(_Report):
    """Every repair an importer performed, in the order it happened (empty = lossless)."""


@dataclass(frozen=True)
class ExportReport(_Report):
    """Every field an exporter dropped, approximated or repaired (empty = lossless, D1).

    Mirrors :class:`ImportReport` exactly: same issue record, ``warnings``/``errors``, ``codes``,
    ``as_strings`` and ``raise_on_error``. An issue always names the element id and the field.
    """


# The registry sits at the bottom because the format modules import the report classes above:
# importing them here (after the classes exist) is safe, and `io/__init__` imports this module
# first so the chain is always report -> formats, never the reverse. `CODES` are plain tuples
# and every third-party library (pandapower, PyPSA) is imported lazily inside the format
# modules' functions, so this costs no optional dependency.
from mambo_power.io import csv_bundle, pandapower_json, psse_raw, pypsa  # noqa: E402

LIMITATIONS: dict[str, tuple[str, ...]] = {
    "io.matpower": ("BASE_KV_REPLACED", "GENCOST_REACTIVE_IGNORED", "ISLAND_DEACTIVATED"),
    "io.pandapower_json": pandapower_json.CODES,
    "io.pypsa": pypsa.CODES,
    "io.psse_raw": psse_raw.CODES,
    "io.csv_bundle": csv_bundle.CODES,
}
"""Registry: format module name → every report code it can emit (its documented limitations).
`tests/unit/test_io_limitations.py` checks that `docs/manual/formats.md` names each code."""
