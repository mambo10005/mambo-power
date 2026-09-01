"""P3: which MATPOWER columns does the importer drop, and do the fixtures carry non-default data there?"""
import io
import re
import sys
from collections import Counter
from pathlib import Path

import numpy as np

FIX = Path(sys.argv[1])


def read(path):
    text = re.sub(r"%[^\n]*", "", path.read_text(encoding="utf-8"))

    def block(name):
        m = re.search(rf"mpc\.{name}\s*=\s*\[(.*?)\];", text, re.S)
        return None if m is None else np.loadtxt(io.StringIO(m.group(1).replace(";", "\n")), ndmin=2)

    return block("bus"), block("gen"), block("branch"), block("gencost"), text


GEN = {6: "MBASE", 10: "PC1", 11: "PC2", 12: "QC1MIN", 13: "QC1MAX", 14: "QC2MIN", 15: "QC2MAX",
       16: "RAMP_AGC", 17: "RAMP_10", 18: "RAMP_30", 19: "RAMP_Q", 20: "APF"}
BR = {6: "RATE_B", 7: "RATE_C", 11: "ANGMIN", 12: "ANGMAX"}
for name in ["case14", "case30", "case_ieee30", "case57", "case118"]:
    bus, gen, br, gc, text = read(FIX / f"{name}.m")
    out = []
    for c, lab in GEN.items():
        if gen.shape[1] > c:
            v = gen[:, c]
            if lab == "MBASE":
                out.append(f"MBASE!=100:{int((v != 100).sum())}")
            elif int((v != 0).sum()):
                out.append(f"{lab}!=0:{int((v != 0).sum())}")
    for c, lab in BR.items():
        if br.shape[1] > c:
            v = br[:, c]
            if lab.startswith("RATE"):
                out.append(f"{lab}!=RATE_A:{int((v != br[:, 5]).sum())}")
            else:
                out.append(f"{lab}!=+-360:{int((np.abs(v) != 360).sum())}")
    multi = Counter(gen[:, 0].astype(int))
    multi = {b: n for b, n in multi.items() if n > 1}
    others = sorted(set(re.findall(r"^\s*mpc\.(\w+)\s*=", text, re.M))
                    - {"baseMVA", "bus", "gen", "branch", "gencost", "version"})
    neg_load = int((bus[:, 2] < 0).sum())
    gen_off = int((gen[:, 7] <= 0).sum())
    print(f"{name:12s} gen cols={gen.shape[1]} br cols={br.shape[1]} | {' '.join(out)} | "
          f"multi-gen buses={multi} neg PD={neg_load} gens off={gen_off} | extra sections={others}")
