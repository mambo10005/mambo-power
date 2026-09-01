"""A2 probe: is a nonzero cost_coeffs row alongside a pwl_costs entry for the SAME generator
caught, or silently double-counted?

The load side raises on that overlap (_extract_and_validate, "must be either polynomial or
piecewise-linear, not both"). The generator side has no such check; gen_cost_coeffs maintains
the invariant by construction (`continue` after recording the PWL entry). The question is what
happens when a caller that is NOT gen_cost_coeffs builds the pair.
"""

import numpy as np

from mambo_power.io import matpower
from mambo_power.numerics.arrays import NetworkArrays
from mambo_power.opf import gen_cost_coeffs
from mambo_power.opf.dc_opf import OpfDcOptions, dc_opf

net = matpower.load("fixtures/matpower/case14.m")
arr = NetworkArrays.from_network(net)
coeffs, pwl = gen_cost_coeffs(net, arr)
print(f"case14: {len(arr.gen_ids)} gens, pwl entries from the model: {sorted(pwl)}")
print(f"gen 0 true coeffs [c2,c1,c0] = {coeffs[0]}")

opts = OpfDcOptions()

# Baseline: the model's own (polynomial) offer.
base = dc_opf(arr, coeffs, opts)
print(f"\nbaseline           status={base.status}  objective={base.objective_cost:.6f}")

# A PWL offer for generator 0 that is a faithful 2-segment sample of its own quadratic cost,
# so the "correct form" objective should land close to the baseline.
c2, c1, c0 = coeffs[0]
pmin = float(arr.gen_p_min_pu[0]) * arr.base_mva
pmax = float(arr.gen_p_max_pu[0]) * arr.base_mva
pts = [(p, c2 * p * p + c1 * p + c0) for p in np.linspace(pmin, pmax, 5)]

# (1) CORRECT form: zero the polynomial row, hand the curve through pwl_costs.
correct = coeffs.copy()
correct[0] = 0.0
r_correct = dc_opf(arr, correct, opts, pwl_costs={0: pts})
print(f"correct form       status={r_correct.status}  objective={r_correct.objective_cost:.6f}")

# (2) BROKEN form: leave the polynomial row in place AND hand the same curve as PWL.
broken = coeffs.copy()
try:
    r_broken = dc_opf(arr, broken, opts, pwl_costs={0: pts})
except Exception as exc:  # noqa: BLE001 - the point is to see whether anything is raised
    print(f"broken form        RAISED {type(exc).__name__}: {exc}")
else:
    print(f"broken form        status={r_broken.status}  objective={r_broken.objective_cost:.6f}")
    delta = r_broken.objective_cost - r_correct.objective_cost
    print(f"\n>>> NOT CAUGHT. objective differs from the correct form by {delta:.6f}")
    print(">>> gen 0 dispatch: correct=%.6f broken=%.6f" % (
        r_correct.dispatch_mw[0], r_broken.dispatch_mw[0]))

# For contrast: the load side's overlap IS caught.
try:
    dc_opf(
        arr,
        coeffs,
        opts,
        demand_bid_coeffs={0: (0.0, 50.0, 0.0)},
        demand_pwl_bids={0: [(0.0, 0.0), (10.0, 500.0)]},
    )
except Exception as exc:  # noqa: BLE001
    print(f"\nload-side overlap  RAISED {type(exc).__name__}: {str(exc)[:110]}")
