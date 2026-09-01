"""AC-5: the repaired ``case14_island`` network's AC solve matches pandapower on the main
island.

Reproduces the Step-5 auditor's hand probe (``m2-audit.md`` §3, "Auditor probe for AC-5's
unproven clause") as a durable test. ``load_with_warnings`` repairs the island itself (bus-8 /
gen-5 deactivated, ``ISLAND_DEACTIVATED``); pandapower's own ``runpp`` reaches the same main
island independently, through its own connectivity check (``check_connectivity=True``, the
default) rather than through our repair — bus 8 stays in ``net.bus`` but its result row is
``NaN``. The two paths therefore land on the same 13-bus main island from opposite directions,
and comparing them is not circular. Same oracle convention as
:mod:`tests.parity.test_ac_vs_pandapower` (BASE_KV substitution, ``trafo_model="pi"``,
``enforce_q_lims=True``).
"""

from __future__ import annotations

import warnings
from typing import Any

import numpy as np

from mambo_power.io import matpower
from mambo_power.pf import AcOptions, solve_ac
from tests._fixtures import FIXTURES_DIR
from tests.parity._mpc_reader import read_mpc_numpy
from tests.parity.test_ac_vs_pandapower import SUBSTITUTE_KV, _pp_bus, _worst
from tests.parity.test_matpower_vs_pandapower import pandapower_from_raw

ISLAND = FIXTURES_DIR / "derived" / "case14_island.m"
# Auditor's probe measured 8.9e-16 pu / 4.4e-14 deg on this fixture; these keep that order of
# magnitude of headroom rather than tightening past what is actually reproducible.
TOL_VM = 1e-14
TOL_VA_DEG = 1e-13


def _run_pandapower_island(raw: dict[str, Any]) -> Any:
    import pandapower as pp

    patched = {k: (v.copy() if isinstance(v, np.ndarray) else v) for k, v in raw.items()}
    patched["bus"][patched["bus"][:, 9] <= 0, 9] = SUBSTITUTE_KV
    net = pandapower_from_raw(patched)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        pp.runpp(
            net,
            init="flat",
            tolerance_mva=1e-8,
            enforce_q_lims=True,
            trafo_model="pi",
            max_iteration=50,
            calculate_voltage_angles=True,
            numba=False,
        )
    assert net.converged
    return net


def test_repaired_island_solve_matches_runpp_on_the_main_island() -> None:
    net, _report_warnings = matpower.load_with_warnings(ISLAND)
    ours = solve_ac(net, options=AcOptions(init="flat", q_limits=True))
    assert ours.converged
    # bus-8 was deactivated by the repair, so it never reaches AcPowerFlowResult.buses.
    assert len(ours.buses) == 13
    assert all(b.id != "bus-8" for b in ours.buses)

    raw = read_mpc_numpy(ISLAND)
    pp = _run_pandapower_island(raw)
    # pandapower's own connectivity check drops bus 8 independently of our repair: it stays in
    # net.bus but its solved row is NaN.
    assert bool(np.isnan(pp.res_bus.loc[_pp_bus("bus-8")].vm_pu))

    slack_id = next(b.id for b in net.buses if b.type == "slack" and b.in_service)
    vm, va = pp.res_bus.vm_pu, pp.res_bus.va_degree
    offset = float(va.loc[_pp_bus(slack_id)])
    vm_diffs = {b.id: abs(b.vm_pu - float(vm.loc[_pp_bus(b.id)])) for b in ours.buses}
    va_diffs = {b.id: abs(b.va_deg - (float(va.loc[_pp_bus(b.id)]) - offset)) for b in ours.buses}
    worst_vm, value_vm = _worst(vm_diffs)
    worst_va, value_va = _worst(va_diffs)
    assert value_vm <= TOL_VM, (worst_vm, value_vm)
    assert value_va <= TOL_VA_DEG, (worst_va, value_va)
