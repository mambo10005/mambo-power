"""P6a: island contrast on case30 (every bus 135 kV, so pandapower's from_ppc yields finite ohms).
P6b: re-execute one S4-report mutation claim (branch-8 x += 2e-9 -> layer A worst 2e-9 > TOL)."""
import importlib.util
import io
import re
import sys
import warnings
from pathlib import Path

import numpy as np

from mambo_power.io import matpower
from mambo_power.model import NetworkValidationError
from mambo_power.numerics import NetworkArrays, bridges

FIX = Path(sys.argv[1])
TESTS = Path(sys.argv[2])

# ---- P6a -----------------------------------------------------------------------------------
path = FIX / "case30.m"
net0 = matpower.load(path)
arr0 = NetworkArrays.from_network(net0)
k = bridges(arr0)[0]
f_id, t_id = net0.branches[k].from_bus, net0.branches[k].to_bus
f_n, t_n = int(f_id.removeprefix("bus-")), int(t_id.removeprefix("bus-"))
print(f"case30 bridge chosen: {arr0.branch_ids[k]} {f_id}-{t_id}")
lines = path.read_text(encoding="utf-8").splitlines()
hit = 0
for i, ln in enumerate(lines):
    if re.match(rf"^\s*{f_n}\s+{t_n}\s+", ln):
        cols = ln.split()
        assert cols[10].rstrip(";") == "1", cols
        cols[10] = "0"
        lines[i] = "\t" + "\t".join(cols)
        hit = i + 1
assert hit
mod = "\n".join(lines) + "\n"
try:
    matpower.loads(mod)
    print("ours: loaded")
except NetworkValidationError as e:
    print("ours: matpower.loads raised", [str(i) for i in e.issues])

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
isolated = [int(b) + 1 for b in n.res_bus.index[n.res_bus.vm_pu.isna()]]
print("pandapower: from_ppc + runpp converged =", n.converged, "| buses with NaN result (isolated, tolerated):", isolated)

# ---- P6b -----------------------------------------------------------------------------------
spec = importlib.util.spec_from_file_location("_s4", TESTS / "parity" / "test_matpower_vs_pandapower.py")
s4 = importlib.util.module_from_spec(spec)
sys.modules["_s4"] = s4
spec.loader.exec_module(s4)
p14 = FIX / "case14.m"
raw = s4.read_mpc_numpy(p14)
net, warns = matpower.load_with_warnings(p14)
with warnings.catch_warnings():
    warnings.simplefilter("ignore")
    ppn = s4.pandapower_from_raw(raw)
case = s4.Case("case14", raw, ppn, net, warns)
print("baseline layer A worst =", s4.compare_raw(case).worst, "| layer B worst =", s4.compare_pandapower(case).worst)
net.branches[7].x += 2e-9
ra = s4.compare_raw(case)
rb = s4.compare_pandapower(case)
print(f"after branch-8 x += 2e-9: layer A worst = {ra.worst:.2e} (> 1e-9: {ra.worst > 1e-9}) | layer B worst = {rb.worst:.2e} (> 1e-9: {rb.worst > 1e-9})")
