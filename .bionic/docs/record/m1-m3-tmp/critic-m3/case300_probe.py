"""Independent check: are 'ours' and PyPSA solving genuinely the same case300 network, or does
the residual hide an index-alignment mismatch big enough to matter (not just tie-breaking noise)?
"""
import numpy as np
from mambo_power.io import matpower
from mambo_power.opf import solve_dc_opf
from tests._fixtures import FIXTURES_DIR
from tests.parity._mpc_reader import read_mpc_numpy
from tests.parity.test_opf_vs_pypsa import run_pypsa_dcopf

path = FIXTURES_DIR / "case300.m"
raw = read_mpc_numpy(path)
n, status, cond, c0_sum = run_pypsa_dcopf(raw)
net = matpower.load(path)
ours = solve_dc_opf(net)

by_id = {g.id: g.p_mw for g in ours.generators}
pypsa_dispatch = n.generators_t.p.iloc[0].to_numpy()
diffs = []
for k in range(len(pypsa_dispatch)):
    ours_p = by_id[f"gen-{k+1}"]
    diffs.append(ours_p - pypsa_dispatch[k])
diffs = np.array(diffs)
print("n_gens:", len(diffs))
print("worst 10 abs diffs (idx, ours, pypsa, diff):")
idx_sorted = np.argsort(-np.abs(diffs))[:10]
for i in idx_sorted:
    print(i, by_id[f"gen-{i+1}"], pypsa_dispatch[i], diffs[i])
print("sum(diffs) [should be ~0 if just redistribution]:", diffs.sum())
print("num gens with |diff| > 0.001 MW:", int((np.abs(diffs) > 0.001).sum()), "/", len(diffs))
print("mambo_power total dispatch:", sum(by_id.values()))
print("pypsa total dispatch:", pypsa_dispatch.sum())
