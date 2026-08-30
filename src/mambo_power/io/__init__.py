"""Importers and exporters. Every format speaks only :mod:`mambo_power.model`.

Six formats: the native JSON (:mod:`~mambo_power.io.native`), MATPOWER ``.m``
(:mod:`~mambo_power.io.matpower`), pandapower JSON both ways
(:mod:`~mambo_power.io.pandapower_json`), PyPSA export (:mod:`~mambo_power.io.pypsa`), PSS/E RAW
v33 import (:mod:`~mambo_power.io.psse_raw`) and the CSV bundle (:mod:`~mambo_power.io.csv_bundle`).
pandapower and PyPSA are imported lazily inside the functions that need them, so importing this
package never requires either. :data:`~mambo_power.io.report.LIMITATIONS` lists every report code
each module can emit.
"""

# `report` must be imported first: it registers the format modules' CODES at its bottom, and the
# format modules import its classes, so the chain has to start there (see report.py).
from mambo_power.io import report  # noqa: I001
from mambo_power.io import csv_bundle, matpower, native, pandapower_json, psse_raw, pypsa

__all__ = ["csv_bundle", "matpower", "native", "pandapower_json", "psse_raw", "pypsa", "report"]
