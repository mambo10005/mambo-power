"""AC-4 oracle: pandapower solves the gen-less PV bus of case14_roles as PQ, as we do.

The case14_roles matrices go through the same pipeline as the column-parity tier
(``tests.parity._mpc_reader`` → pandapower's own ``from_ppc`` half of ``from_mpc``) and then
``pp.runpp(init="flat")``. Two facts are checked against the oracle:

* bus 6 (declared PV, its only generator out of service) is NOT pinned to its setpoint —
  pandapower's ``res_bus.vm_pu`` differs from VG = 1.07 — i.e. it solves as PQ, the same
  demotion ``effective_roles`` performs;
* bus 2 (two in-service generators, VG 1.045 then 1.055): pandapower's *converter* gives the
  second generator the first one's setpoint (``from_ppc`` ``drop_duplicates(keep="first")``,
  record/m2-research.md §2), so its solve pins bus 2 at 1.045. We follow MATPOWER's last-wins
  rule (1.055) and warn. That difference is documented, not hidden: this test pins both
  numbers so a change on either side is visible.
"""

from __future__ import annotations

import warnings
from typing import Any

import numpy as np
import pytest

from mambo_power.io import matpower
from mambo_power.numerics import NetworkArrays, SetpointConflictWarning, effective_roles
from tests._fixtures import FIXTURES_DIR
from tests.parity._mpc_reader import read_mpc_numpy
from tests.parity.test_matpower_vs_pandapower import pandapower_from_raw

ROLES = FIXTURES_DIR / "derived" / "case14_roles.m"
PQ = 1


@pytest.fixture(scope="module")
def solved_pp() -> Any:
    import pandapower as pp

    raw = read_mpc_numpy(ROLES)
    # case14 carries BASE_KV = 0 on every bus; pandapower's trafo model divides by it. Apply
    # the importer's own substitution (DEFAULT_BASE_KV = 1.0) to the oracle's copy, as the
    # research probes did (record/m2-research.md §1.2); pu data are unchanged by this.
    raw["bus"][raw["bus"][:, 9] <= 0, 9] = 1.0
    net = pandapower_from_raw(raw)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")  # pandapower's from_ppc / pandas chatter
        pp.runpp(net, init="flat", tolerance_mva=1e-8, calculate_voltage_angles=True)
    assert net.converged
    return net


def test_pandapower_solves_the_gen_less_pv_bus_as_pq(solved_pp: Any) -> None:
    net = solved_pp
    pp_bus6 = 5  # _adjust_ppc_indices: BUS_I - 1
    gens_at_6 = net.gen[net.gen.bus == pp_bus6]
    assert len(gens_at_6) == 1 and not bool(gens_at_6.in_service.iloc[0])
    vm6 = float(net.res_bus.vm_pu.loc[pp_bus6])
    assert abs(vm6 - 1.07) > 1e-3, vm6  # not pinned: PQ behaviour
    assert float(net._ppc["bus"][pp_bus6, 1]) == PQ
    # and our derivation says the same
    arr = NetworkArrays.from_network(matpower.load(ROLES))
    with pytest.warns(SetpointConflictWarning):
        roles = effective_roles(arr)
    assert roles.bus_type[arr.bus_index["bus-6"]] == PQ


def test_pandapower_keeps_every_other_pv_bus_pinned(solved_pp: Any) -> None:
    res = solved_pp.res_bus.vm_pu
    for pp_bus, vg in ((2, 1.01), (7, 1.09)):  # buses 3 and 8, single in-service gens
        assert abs(float(res.loc[pp_bus]) - vg) < 1e-9


def test_converter_first_wins_vs_our_last_wins_is_explicit(solved_pp: Any) -> None:
    vm2 = float(solved_pp.res_bus.vm_pu.loc[1])
    assert abs(vm2 - 1.045) < 1e-9  # pandapower converter: first gen row's VG
    arr = NetworkArrays.from_network(matpower.load(ROLES))
    with pytest.warns(SetpointConflictWarning, match="bus-2"):
        roles = effective_roles(arr)
    assert roles.v_set[arr.bus_index["bus-2"]] == 1.055  # MATPOWER: last gen row's VG
    assert not np.isclose(vm2, roles.v_set[arr.bus_index["bus-2"]])
