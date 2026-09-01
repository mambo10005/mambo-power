"""Results: JSON round trip, the positional ``to_arrays()`` view, and a CSV export.

What this shows:

* A result is a pydantic model: ``model_dump_json`` / ``model_validate_json`` round-trip it
  exactly (provenance included), so a result can be stored, queued or returned from a
  service as-is.
* ``to_arrays()`` gives one numpy array per column in table order, for numeric consumers
  that want positions rather than ids — e.g. finding the most loaded branch or the voltage
  envelope in one line.
* Exporting the bus and branch tables to CSV needs nothing beyond the standard library:
  every row is a pydantic model, so ``model_dump()`` feeds ``csv.DictWriter`` directly.

Run from the repository root: ``uv run python examples/07_results_and_export.py``.
"""

from __future__ import annotations

import csv
import json
import tempfile
from pathlib import Path

import numpy as np

from mambo_power import pf
from mambo_power.io import matpower
from mambo_power.results import AcPowerFlowResult

net = matpower.load("fixtures/matpower/case14.m")
result = pf.solve_ac(net, options=pf.AcOptions(init="flat"))

# --- 1. JSON round trip --------------------------------------------------------------------
text = result.model_dump_json()
back = AcPowerFlowResult.model_validate_json(text)
print(f"JSON: {len(text)} bytes; round trip equal: {back == result}")
document = json.loads(text)
print("top-level keys:", sorted(document))
print("provenance keys:", sorted(document["provenance"]))
print("a bus row:", document["buses"][0])

# --- 2. The positional view ------------------------------------------------------------------
arrays = result.to_arrays()
print(f"\nto_arrays: {len(arrays.bus_ids)} buses, {len(arrays.branch_ids)} branches,", end=" ")
print(f"{len(arrays.gen_ids)} generators")
lo, hi = int(np.argmin(arrays.vm_pu)), int(np.argmax(arrays.vm_pu))
print(f"voltage envelope: {arrays.bus_ids[lo]} {arrays.vm_pu[lo]:.4f} pu", end=" ... ")
print(f"{arrays.bus_ids[hi]} {arrays.vm_pu[hi]:.4f} pu")
apparent = np.hypot(arrays.p_from_mw, arrays.q_from_mvar)
k = int(np.argmax(apparent))
print(f"largest from-side flow: {arrays.branch_ids[k]} {apparent[k]:.2f} MVA")
print(f"total losses from arrays: {(arrays.p_from_mw + arrays.p_to_mw).sum():.3f} MW")
print("loading_pct is NaN where the branch is unrated:", int(np.isnan(arrays.loading_pct).sum()))

# --- 3. CSV export with the standard library ------------------------------------------------
with tempfile.TemporaryDirectory() as tmp:
    out = Path(tmp)
    for name, rows in (("buses", result.buses), ("branches", result.branches)):
        records = [row.model_dump() for row in rows]
        with (out / f"{name}.csv").open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=list(records[0]))
            writer.writeheader()
            writer.writerows(records)
    for path in sorted(out.iterdir()):
        lines = path.read_text(encoding="utf-8").splitlines()
        print(f"\n{path.name}: {len(lines) - 1} rows")
        print("  " + lines[0])
        print("  " + lines[1])
