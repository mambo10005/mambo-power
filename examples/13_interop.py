"""Interchange: one ``Network`` in and out of pandapower, PyPSA, PSS/E RAW and a CSV bundle,
with every conversion reporting what it could not carry.

What this shows:

* ``io.pandapower_json.dumps(net)`` -> ``pp.from_json_string`` -> ``pp.rundcpp``: pandapower's
  own DC solver on the exported document agrees with ``pf.solve_dc`` on the original, angle by
  angle, and the export report names each field pandapower has no column for.
* ``io.pandapower_json.loads_with_report`` on ``pp.networks.case14()``: pandapower's case14 comes
  in with an **empty** report -- the conversion was lossless -- and its neutral-tap transformers
  keep ``kind="transformer"`` because the source table says so.
* ``io.pypsa.to_network_with_report`` then PyPSA ``optimize()``: the DC-OPF objective agrees
  with ``opf.solve_dc_opf`` (the constant cost term travels beside PyPSA's objective in the
  ``marginal_cost_constant`` column, since ``n.objective`` excludes constants).
* ``io.psse_raw.load_with_report`` on ``fixtures/case14_v33.raw``: the same IEEE case14 spelled
  as a RAW file; RAW carries no costs, and the report says so with ``RAW_NO_COSTS`` rather than
  the importer inventing any.
* ``io.csv_bundle.dump`` / ``load`` through a temporary directory: ``load(dump(net)) == net``,
  bit-exact, with no tolerance.
* One deliberately lossy conversion -- a piecewise-cost generator into PyPSA, which has no
  piecewise cost -- and the ``ExportReport`` that names the generator, the field and what was
  written instead.

Every conversion is *best effort + report*: an empty report means lossless; anything dropped,
approximated or repaired is an issue naming the element id and the field. Nothing is logged or
printed by the converters themselves.

pandapower and PyPSA are development extras (``uv sync`` installs them); the core package never
imports either.

Run from the repository root: ``uv run python examples/13_interop.py``.
"""

from __future__ import annotations

import logging
import tempfile
import warnings
from pathlib import Path

import numpy as np
import pandapower as pp
import pandapower.networks as pn

from mambo_power import opf, pf
from mambo_power.io import csv_bundle, matpower, pandapower_json, psse_raw, pypsa
from mambo_power.model import PiecewiseCost

# The third-party libraries log freely (numba advice, PyPSA consistency notes, solver banners);
# the converters themselves never do. Keep the output to what this script prints.
for name in ("pandapower", "pypsa", "linopy"):
    logging.getLogger(name).setLevel(logging.ERROR)

net = matpower.load("fixtures/matpower/case14.m")
print(f"case14: {len(net.buses)} buses, {len(net.branches)} branches, {len(net.generators)} gens")

# --- 1. pandapower JSON export, solved by pandapower itself ----------------------------------
text, export_report = pandapower_json.dumps_with_report(net)
print(f"\npandapower export: {len(text)} chars, report codes {sorted(export_report.codes)}")
for issue in export_report.warnings[:3]:
    print("  ", issue)
print(f"   ... {len(export_report.warnings)} issues in all; none touches a carried value")

pp_net = pp.from_json_string(text)
with warnings.catch_warnings():  # pandapower warns about the missing optional numba
    warnings.simplefilter("ignore")
    pp.rundcpp(pp_net, numba=False, trafo_model="pi")
ours = pf.solve_dc(net)
theirs = {
    str(name): float(va) for name, va in zip(pp_net.bus.name, pp_net.res_bus.va_degree, strict=True)
}
worst = max(abs(b.va_deg - theirs[b.id]) for b in ours.buses)
print(f"pp.rundcpp vs pf.solve_dc: worst angle difference {worst:.1e} deg, {len(ours.buses)} buses")

# --- 2. pandapower import: pp.networks.case14() ---------------------------------------------
pp14, import_report = pandapower_json.loads_with_report(pp.to_json(pn.case14()))
trafos = [br.id for br in pp14.branches if br.kind == "transformer"]
print(f"\npandapower import of pp.networks.case14(): report {import_report.as_strings()}")
print("   (an empty report means the conversion was lossless)")
print(f"   {len(pp14.buses)} buses, {len(pp14.branches)} branches, transformers {trafos}")
neutral = [
    br.id for br in pp14.branches if br.kind == "transformer" and br.tap_ratio in (None, 1.0)
]
print(f"   neutral-tap transformers kept as transformers by the source table: {neutral}")

# --- 3. PyPSA export, optimised by PyPSA ------------------------------------------------------
n, pypsa_report = pypsa.to_network_with_report(net)
print(f"\nPyPSA export: {len(n.buses)} buses, {len(n.lines)} lines, {len(n.transformers)} trafos")
print(f"   report codes {sorted(pypsa_report.codes)} ({len(pypsa_report.warnings)} issues)")
with warnings.catch_warnings():
    warnings.simplefilter("ignore")
    status = n.optimize(solver_name="highs", solver_options={"output_flag": False})
c0 = float(n.generators[pypsa.COST_CONSTANT_COLUMN].sum())
pypsa_objective = float(n.objective) + c0
dc_opf = opf.solve_dc_opf(net)
rel = abs(dc_opf.objective_cost - pypsa_objective) / pypsa_objective
print(f"   PyPSA optimize {status}: objective {pypsa_objective:.4f} $/h (incl. constant {c0:.1f})")
print(f"   opf.solve_dc_opf {dc_opf.status}: objective {dc_opf.objective_cost:.4f} $/h")
print(f"   relative difference {rel:.1e}")

# --- 4. PSS/E RAW v33 import ------------------------------------------------------------------
raw_net, raw_report = psse_raw.load_with_report("fixtures/case14_v33.raw")
print(f"\nRAW import: {len(raw_net.buses)} buses, {len(raw_net.branches)} branches")
print(f"   report codes {sorted(raw_report.codes)} ({len(raw_report.warnings)} issues)")
print("  ", next(str(w) for w in raw_report.warnings if w.code == "RAW_NO_COSTS"))
raw_dc = pf.solve_dc(raw_net)
raw_angles = np.array([b.va_deg for b in raw_dc.buses])
m_angles = np.array([b.va_deg for b in ours.buses])
raw_worst = float(np.abs(raw_angles - m_angles).max())
print(
    f"   pf.solve_dc on the RAW network vs the MATPOWER one: worst angle diff {raw_worst:.1e} deg"
)

# --- 5. CSV bundle round trip -----------------------------------------------------------------
with tempfile.TemporaryDirectory() as directory:
    csv_bundle.dump(net, directory)
    files = sorted(p.name for p in Path(directory).iterdir())
    back = csv_bundle.load(directory)
print(f"\nCSV bundle: {files}")
print(f"   load(dump(net)) == net: {back == net}")

# --- 6. A deliberately lossy conversion --------------------------------------------------------
lossy = net.model_copy(deep=True)
lossy.generators[1].cost = PiecewiseCost(points=[(0.0, 0.0), (50.0, 1500.0), (140.0, 5000.0)])
_, lossy_report = pypsa.to_network_with_report(lossy)
print("\nPiecewise cost into PyPSA (which has none):")
for issue in lossy_report.warnings:
    if issue.code == "PYPSA_PWL_COST_DROPPED":
        print(f"   {issue.code}: element_ids={issue.element_ids}")
        print(f"   {issue.message}")
