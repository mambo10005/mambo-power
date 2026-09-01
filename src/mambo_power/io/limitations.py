"""The registry of report codes each format module can emit (its documented limitations).

Lives in its own module, *above* the format modules in the import graph: each format module
imports :mod:`mambo_power.io.report` for the report classes, and this module imports the format
modules for their ``CODES`` — so ``report`` stays a leaf and no module is ever imported
half-initialised (M8 critic finding 9; the registry used to sit at the bottom of ``report.py``,
which only worked because the classes above it happened to exist by the time the format modules
looked). ``CODES`` are plain tuples, and pandapower / PyPSA are imported lazily inside the format
modules' functions, so importing this costs no optional dependency.

``tests/unit/test_io_limitations.py`` checks that ``docs/manual/formats.md`` names every code.
"""

from __future__ import annotations

from mambo_power.io import csv_bundle, pandapower_json, psse_raw, pypsa

__all__ = ["LIMITATIONS"]

LIMITATIONS: dict[str, tuple[str, ...]] = {
    "io.matpower": ("BASE_KV_REPLACED", "GENCOST_REACTIVE_IGNORED", "ISLAND_DEACTIVATED"),
    "io.pandapower_json": pandapower_json.CODES,
    "io.pypsa": pypsa.CODES,
    "io.psse_raw": psse_raw.CODES,
    "io.csv_bundle": csv_bundle.CODES,
}
"""Format module name → every report code it can emit."""
