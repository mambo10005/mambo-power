"""P4: a MATPOWER file with an in-service bus islanded by an out-of-service branch: loadable?"""
import io
import re
import sys
import warnings
from pathlib import Path

import numpy as np

from mambo_power.io import matpower
from mambo_power.model import NetworkValidationError

FIX = Path(sys.argv[1])
text = (FIX / "case14.m").read_text(encoding="utf-8")
# branch 7-8 is the only branch reaching bus 8 (a PV bus carrying a synchronous condenser).
lines = text.splitlines()
hit = None
for i, ln in enumerate(lines):
    if re.match(r"^\s*7\s+8\s+", ln):
        cols = ln.split()
        assert cols[10].rstrip(";") == "1", cols
        cols[10] = "0"
        lines[i] = "\t" + "\t".join(cols)
        hit = i + 1
assert hit, "branch 7-8 not found"
mod = "\n".join(lines) + "\n"
print(f"modified line {hit}: {lines[hit - 1].strip()}")
try:
    net = matpower.loads(mod)
    print("loaded; bus-8 in_service =", next(b for b in net.buses if b.id == "bus-8").in_service)
except NetworkValidationError as e:
    print("matpower.loads raised NetworkValidationError:")
    for issue in e.issues:
        print("   ", issue)

# what pandapower does with the same ppc
import pandapower as pp
from pandapower.converter.matpower.from_mpc import _adjust_ppc_indices, _change_ppc_TAP_value
from pandapower.converter.pypower.from_ppc import from_ppc

t = re.sub(r"%[^\n]*", "", mod)


def block(name):
    m = re.search(rf"mpc\.{name}\s*=\s*\[(.*?)\];", t, re.S)
    return np.loadtxt(io.StringIO(m.group(1).replace(";", "\n")), ndmin=2)


ppc = {"version": "2", "baseMVA": 100.0, "bus": block("bus"), "gen": block("gen"),
       "branch": block("branch"), "gencost": block("gencost")}
_adjust_ppc_indices(ppc)
_change_ppc_TAP_value(ppc)
with warnings.catch_warnings():
    warnings.simplefilter("ignore")
    n = from_ppc(ppc, f_hz=60)
    pp.runpp(n)
print("pandapower runpp converged:", n.converged, "| bus 8 vm_pu =", n.res_bus.vm_pu.iloc[7],
      "(NaN = isolated, tolerated) | bus 8 in_service after runpp:", bool(n.bus.in_service.iloc[7]))
