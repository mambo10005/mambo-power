"""P2: independent oracle for PTDF/LODF: pandapower.pypower.makePTDF / makeLODF on the 5 fixtures.

The ppc is built from an independent regex + numpy.loadtxt read of the .m bytes (same idea as the
S4/S5 parity modules), never from our importer, so the chain file -> importer -> arrays -> ptdf/lodf
is compared end to end against file -> pypower builders.
"""
import io
import re
import sys
import warnings
from pathlib import Path

import numpy as np
from pandapower.pypower.idx_brch import branch_cols
from pandapower.pypower.idx_bus import bus_cols
from pandapower.pypower.makeLODF import makeLODF
from pandapower.pypower.makePTDF import makePTDF

from mambo_power.io import matpower
from mambo_power.numerics import NetworkArrays, bridges, lodf, ptdf

FIX = Path(sys.argv[1])


def read(path):
    text = re.sub(r"%[^\n]*", "", path.read_text(encoding="utf-8"))
    base = float(re.search(r"mpc\.baseMVA\s*=\s*([^;\s]+)", text).group(1))

    def block(name):
        m = re.search(rf"mpc\.{name}\s*=\s*\[(.*?)\];", text, re.S)
        return np.loadtxt(io.StringIO(m.group(1).replace(";", "\n")), ndmin=2)

    return base, block("bus"), block("branch")


worst_p = worst_l = 0.0
for name in ["case14", "case30", "case_ieee30", "case57", "case118"]:
    path = FIX / f"{name}.m"
    base, bus_raw, br_raw = read(path)
    bus = np.zeros((bus_raw.shape[0], bus_cols))
    bus[:, : bus_raw.shape[1]] = bus_raw
    pos = {int(n): k for k, n in enumerate(bus_raw[:, 0])}
    bus[:, 0] = np.arange(bus.shape[0])
    br = np.zeros((br_raw.shape[0], branch_cols))
    br[:, : br_raw.shape[1]] = br_raw
    br[:, 0] = [pos[int(n)] for n in br_raw[:, 0]]
    br[:, 1] = [pos[int(n)] for n in br_raw[:, 1]]

    net = matpower.load(path)
    arr = NetworkArrays.from_network(net)
    perm = np.array([pos[int(b.removeprefix("bus-"))] for b in arr.bus_ids])

    h_pp_raw = np.asarray(makePTDF(base, bus, br))  # nl x nb, oracle slack = the REF bus
    h_pp = h_pp_raw[:, perm]
    h = ptdf(arr)
    dp = float(np.abs(h - h_pp).max())

    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        l_pp = np.asarray(makeLODF(br, h_pp_raw))
    lm = lodf(arr)
    brid = bridges(arr)
    keep = [k for k in range(arr.n_branch) if k not in brid]
    dl = float(np.abs(lm[np.ix_(keep, keep)] - l_pp[np.ix_(keep, keep)]).max())
    # also the bridge *rows* for non-bridge outages (full non-bridge columns)
    dl_cols = float(np.abs(lm[:, keep] - l_pp[:, keep]).max())
    oracle_bridge_finite = bool(np.isfinite(l_pp[:, brid]).all()) if brid else None
    print(
        f"{name:12s} PTDF max|diff|={dp:.2e}  LODF non-bridge cols max|diff|={dl_cols:.2e} "
        f"(square {dl:.2e})  bridges={brid}  oracle bridge cols finite? {oracle_bridge_finite}"
    )
    worst_p, worst_l = max(worst_p, dp), max(worst_l, dl_cols)
verdict = "PASS" if worst_p <= 1e-9 and worst_l <= 1e-9 else "FAIL"
print("WORST PTDF", f"{worst_p:.2e}", "WORST LODF", f"{worst_l:.2e}", verdict)
