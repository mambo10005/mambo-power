"""ADR-030 parity: ``opf.solve_ac_opf(elastic_demand=True)`` agrees with pandapower ``runopp``
on case14 with three bid loads, framed as the sign-flipped ``sgen`` oracle of
``test_market_nodal_vs_pandapower.py`` (``cost_sgen(p) = −value(−p)``, so ``cp1 = v1`` and
``cp2 = −v2``), solved by PYPOWER's PIPS interior-point AC-OPF.

Two fixture conventions carried over from the AC-OPF parity test: the slack bus voltage is
pinned to the slack unit's setpoint on our side (pandapower's ``ext_grid`` holds it there), and
no rating binds on case14. One of this test's own: the bid loads are made purely active
(``q_mvar = 0``, on both sides) because a controllable ``sgen``'s reactive output is a free
variable of pandapower's OPF inside ``[min_q, max_q]`` while our elastic load keeps its power
factor — at ``q = 0`` the two are the same constraint. The bids are quadratic (the chord path of
``ac_opf``), with marginal values crossing the ~38–41 $/MWh AC LMPs so that at least one load
clears in the interior and at least one at its full ``p_mw``.
"""

from __future__ import annotations

import warnings
from dataclasses import dataclass
from typing import Any

import numpy as np
import pytest

from mambo_power.io import matpower
from mambo_power.model import Network, PolynomialBid
from mambo_power.opf import OpfAcOptions, solve_ac_opf
from mambo_power.results import OpfAcResult
from tests._fixtures import FIXTURES_DIR
from tests.parity._mpc_reader import read_mpc_numpy
from tests.parity.test_ac_opf_vs_pandapower import _with_slack_voltage_pinned
from tests.parity.test_matpower_vs_pandapower import pandapower_from_raw

pytest.importorskip("pandapower")

CASE = "case14"
BIDS = {  # load id -> (v2, v1): marginal value v1 + 2·v2·p, $/MWh
    "load-2": (-0.05, 44.0),  # 44 → 41.8 over its 21.7 MW: above the price, served in full
    "load-3": (-0.05, 45.0),  # 45 → 35.6 over 94.2 MW: crosses the price, clears inside
    "load-4": (-0.10, 42.0),  # 42 → 32.4 over 47.8 MW: crosses the price, clears inside
}
COST_REL_TOL = 5e-5
DISPATCH_ABS_TOL_MW = 0.5
LMP_ABS_TOL = 0.05


@dataclass
class Case:
    ours: OpfAcResult
    pp: Any
    sgen_bus: dict[str, int]
    sgen_idx: dict[str, int]


def _with_bids(net: Network) -> Network:
    bid_net = net.model_copy(deep=True)
    for load in bid_net.loads:
        if load.id in BIDS:
            v2, v1 = BIDS[load.id]
            load.bid = PolynomialBid(coefficients=[v2, v1, 0.0])
            load.q_mvar = 0.0  # module docstring: purely active, on both sides
    return bid_net


def _build_sgen_oracle(raw: dict[str, Any], bid_net: Network) -> tuple[Any, dict, dict]:
    import pandapower as pp

    patched = {k: (v.copy() if isinstance(v, np.ndarray) else v) for k, v in raw.items()}
    patched["bus"][patched["bus"][:, 9] <= 0, 9] = 1.0
    net_pp = pandapower_from_raw(patched)

    sgen_bus: dict[str, int] = {}
    sgen_idx: dict[str, int] = {}
    for ld in bid_net.loads:
        if ld.bid is None:
            continue
        bus_i = int(ld.id.split("-")[1])
        bus_pp = int(np.where(raw["bus"][:, 0] == bus_i)[0][0])
        sgen_bus[ld.id] = bus_pp
        # the bus's own fixed load row goes (one representation of that demand), the sgen comes
        rows = net_pp.load.index[net_pp.load.bus == bus_pp]
        net_pp.load = net_pp.load.drop(index=list(rows))
        v2, v1, _ = ld.bid.coefficients  # type: ignore[union-attr]
        idx = pp.create_sgen(
            net_pp,
            bus_pp,
            p_mw=-ld.p_mw / 2,
            q_mvar=0.0,
            min_p_mw=-ld.p_mw,
            max_p_mw=0.0,
            min_q_mvar=0.0,
            max_q_mvar=0.0,
            controllable=True,
        )
        pp.create_poly_cost(net_pp, idx, "sgen", cp1_eur_per_mw=v1, cp2_eur_per_mw2=-v2)
        sgen_idx[ld.id] = idx

    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        pp.runopp(net_pp, trafo_model="pi", init="pf")
    return net_pp, sgen_bus, sgen_idx


@pytest.fixture(scope="module")
def case() -> Case:
    path = FIXTURES_DIR / f"{CASE}.m"
    raw = read_mpc_numpy(path)
    bid_net = _with_slack_voltage_pinned(_with_bids(matpower.load(path)))
    ours = solve_ac_opf(bid_net, OpfAcOptions(elastic_demand=True))
    pp_net, sgen_bus, sgen_idx = _build_sgen_oracle(raw, bid_net)
    return Case(ours=ours, pp=pp_net, sgen_bus=sgen_bus, sgen_idx=sgen_idx)


def test_solve_ac_opf_converges_optimal(case: Case) -> None:
    assert case.ours.status == "Optimal", case.ours.message


def test_the_fixture_has_an_interior_and_a_pinned_load(case: Case) -> None:
    elastic = {ld.id: ld for ld in case.ours.loads if ld.elastic}
    assert set(elastic) == set(BIDS)
    full = {ld.id: -float(case.pp.sgen.at[idx, "min_p_mw"]) for ld, idx in case.sgen_idx.items()}
    assert any(elastic[i].p_mw < full[i] - 1e-3 for i in BIDS)
    assert any(abs(elastic[i].p_mw - full[i]) < 1e-6 for i in BIDS)


def test_welfare_objective_matches_runopp(case: Case) -> None:
    pp_cost = float(case.pp.res_cost)  # generation cost minus the sgens' value
    ours = case.ours.objective_cost - case.ours.demand_value
    rel = abs(ours - pp_cost) / abs(pp_cost)
    assert rel <= COST_REL_TOL, (ours, pp_cost, rel)


def test_served_demand_matches_the_sgen_oracle(case: Case) -> None:
    ours = {ld.id: ld.p_mw for ld in case.ours.loads}
    for load_id, idx in case.sgen_idx.items():
        theirs = -float(case.pp.res_sgen.at[idx, "p_mw"])
        assert abs(ours[load_id] - theirs) <= DISPATCH_ABS_TOL_MW, (load_id, ours[load_id], theirs)


def test_lmp_matches_at_every_bid_bus(case: Case) -> None:
    lmp = {b.id: b.lmp_p for b in case.ours.buses}
    bus_of = {ld.id: ld.bus for ld in case.ours.loads}
    for load_id, bus_pp in case.sgen_bus.items():
        theirs = float(case.pp.res_bus.at[bus_pp, "lam_p"])
        ours = lmp[bus_of[load_id]]
        assert abs(ours - theirs) <= LMP_ABS_TOL, (load_id, ours, theirs)
