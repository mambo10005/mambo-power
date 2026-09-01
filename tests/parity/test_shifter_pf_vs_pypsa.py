"""M7 F1 / M8 A19 (task-shifter-flow-fix.plan.md T4): PyPSA's linear power flow (``n.lpf()``) as
a second, external oracle on ``tests._shifter.shifter_loop_network``, agreeing with
``pf.solve_dc`` -- the in-repo oracle ``tests/unit/test_shifter_flow_fix.py`` checks the three
fixed sites against -- at the same two asymmetric shift angles, ``-7`` and ``+12`` degrees.

This mirrors ``test_pypsa_export_vs_pypsa.py::test_phase_shift_sign_matches_pypsa_lpf_on_a_loop``
(that file's own ``_shifter_mesh`` fixture, a 70 MVA-rated loop) on the shifter-flow-fix task's
own, generously-rated fixture: not a duplicate, since the two fixtures differ (rating, load,
generator costs), and this file exists to re-prove ``io.pypsa.to_network``'s shift handling is
still correct against the exact fixture the fix's own tests use, independent of whichever
generator happens to be dispatched by an OPF/market solve.
"""

from __future__ import annotations

import warnings

import numpy as np
import pytest

from mambo_power import pf
from mambo_power.io import pypsa as io_pypsa
from tests._shifter import dispatched_network, shifter_loop_network

pytest.importorskip("pypsa")

SHIFT_ANGLES_DEG = [-7.0, 12.0]


@pytest.mark.parametrize("shift_deg", SHIFT_ANGLES_DEG)
def test_pf_solve_dc_matches_pypsa_lpf_on_the_shifter_fixture(shift_deg: float) -> None:
    net = shifter_loop_network(shift_deg)
    dispatch = {"g1": 100.0, "g3": 0.0}  # g1 alone serves the load; the DC PF needs one
    dispatched = dispatched_network(net, dispatch)

    n = io_pypsa.to_network(dispatched)
    # lpf (not optimize) reads p_set, and this is the test's own pin, not the exporter's
    assert n.generators["p_set"].isna().all()
    for gid, p in dispatch.items():
        n.generators.loc[gid, "p_set"] = p
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        n.lpf()

    ours = pf.solve_dc(dispatched)
    assert ours.converged

    angles = n.buses_t.v_ang.iloc[0] * 180.0 / np.pi
    for bus in ours.buses:
        assert bus.va_deg == pytest.approx(float(angles[bus.id]), abs=1e-9), bus.id

    flows = {**n.lines_t.p0.iloc[0].to_dict(), **n.transformers_t.p0.iloc[0].to_dict()}
    for branch in ours.branches:
        assert branch.p_from_mw == pytest.approx(float(flows[branch.id]), abs=1e-9), branch.id
