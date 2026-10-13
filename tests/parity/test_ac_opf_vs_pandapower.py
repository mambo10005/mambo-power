"""ADR-018 parity: ``opf.solve_ac_opf`` agrees with pandapower ``runopp`` on every OPF fixture.

The oracle path is ``test_opf_vs_pandapower.py``'s with ``pp.runopp`` (PYPOWER's PIPS
interior-point AC-OPF) in place of ``rundcopp``: the independent ``.m`` read, the ``BASE_KV <= 0``
patch, ``pandapower_from_raw`` with ``trafo_model="pi"``. The two solvers share nothing but
the problem — a primal-dual interior-point method against a trust-region sequential-LP method —
so agreement is evidence about the formulation, not the code.

**One formulation difference, measured and reproduced rather than tolerated.** pandapower's OPF
holds the ``ext_grid`` voltage at its ``vm_pu`` setpoint; MATPOWER's ``opf`` (and ours) lets the
slack bus voltage float inside its band like any other. Run blind, the two agree on case14 and
case_ieee30 — whose slack setpoint is already 1.06, the band's top — and disagree on case30,
case57 and case118 by 2.5e-3, 7.7e-4 and 2.5e-4 of the cost, pandapower's always the higher
(the more constrained problem), with the worst voltage difference sitting on the slack bus at
exactly the setpoint (case118: 1.060 against 1.035). The fixture therefore pins the slack bus's
band to the slack unit's setpoint in *our* network before solving, which is the oracle's problem
stated in our model; the unit tier keeps the unpinned comparison against MATPOWER's published
optima. Likewise pandapower's default branch limit is a current magnitude (PYPOWER
``OPF_FLOW_LIM=2``) where MATPOWER's and ours is apparent power; the oracle is run with
``OPF_FLOW_LIM=0`` so case30's binding ratings mean the same thing on both sides.
pandapower's ``ext_grid`` active power is likewise not a bounded decision variable, which
matters only where the slack unit's bound would bind — it does not on these fixtures.

The tolerances carry a margin over the unit tier's measured agreement with MATPOWER (2e-6
relative on five cases, 1.5e-5 on case30) for PIPS's own termination tolerance; the 0.5 MW
dispatch margin covers the flat trade-off between near-equal marginal units the hand case in
``tests/unit/test_opf_ac.py`` documents. case300 is skipped when PIPS itself does not converge
on it (``OPFNotConverged``): no oracle, no comparison.
"""

from __future__ import annotations

import warnings
from dataclasses import dataclass
from typing import Any

import numpy as np
import pytest

from mambo_power.io import matpower
from mambo_power.model import Network
from mambo_power.opf import solve_ac_opf
from mambo_power.results import OpfAcResult
from tests._fixtures import FIXTURES_DIR
from tests.parity._mpc_reader import read_mpc_numpy
from tests.parity.test_matpower_vs_pandapower import pandapower_from_raw

COST_REL_TOL = 5e-5
DISPATCH_ABS_TOL_MW = 0.5
VOLTAGE_ABS_TOL_PU = 2e-3

CASES = ["case14", "case30", "case_ieee30", "case57", "case118", "case300"]


@dataclass
class Case:
    name: str
    pp: Any
    ours: OpfAcResult


def run_pandapower_opp(raw: dict[str, Any]) -> Any:
    """pandapower net from the raw matrices (BASE_KV <= 0 patched), solved with ``runopp``."""
    import pandapower as pp
    from pandapower.auxiliary import OPFNotConverged

    patched = {k: (v.copy() if isinstance(v, np.ndarray) else v) for k, v in raw.items()}
    patched["bus"][patched["bus"][:, 9] <= 0, 9] = 1.0
    net = pandapower_from_raw(patched)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        try:
            # OPF_FLOW_LIM=0: apparent-power branch limits, MATPOWER's default and ours;
            # pandapower's own default (2) is a current-magnitude limit, a different constraint
            # on the one fixture whose ratings bind (case30)
            pp.runopp(net, trafo_model="pi", init="pf", OPF_FLOW_LIM=0)
        except OPFNotConverged:
            pytest.skip("pandapower's PIPS did not converge on this case: no oracle to compare")
    return net


@pytest.fixture(scope="module", params=CASES)
def case(request: pytest.FixtureRequest) -> Case:
    path = FIXTURES_DIR / f"{request.param}.m"
    raw = read_mpc_numpy(path)
    pp_net = run_pandapower_opp(raw)
    net = _with_slack_voltage_pinned(matpower.load(path))
    ours = solve_ac_opf(net)
    return Case(request.param, pp_net, ours)


def _with_slack_voltage_pinned(net: Network) -> Network:
    """A copy of *net* whose slack bus band is the slack generator's setpoint (module docstring):
    pandapower's OPF holds the ``ext_grid`` voltage there."""
    pinned = net.model_copy(deep=True)
    slack = next(b for b in pinned.buses if b.type == "slack" and b.in_service)
    setpoint = next(g.v_set_pu for g in pinned.generators if g.bus == slack.id and g.in_service)
    slack.v_min_pu = setpoint
    slack.v_max_pu = setpoint
    return pinned


def _pp_dispatch_by_gen_lookup_order(pp_net: Any) -> np.ndarray:
    lookup = pp_net._from_ppc_lookups["gen"]
    dispatch = np.zeros(len(lookup))
    for i, row in lookup.iterrows():
        table = pp_net.res_gen if row.element_type == "gen" else pp_net.res_ext_grid
        dispatch[i] = table.at[row.element, "p_mw"]
    return dispatch


def test_solve_ac_opf_converges_optimal(case: Case) -> None:
    assert case.ours.status == "Optimal", (case.name, case.ours.message)


def test_objective_cost_matches_runopp(case: Case) -> None:
    pp_cost = float(case.pp.res_cost)
    ours_cost = case.ours.objective_cost
    rel = abs(ours_cost - pp_cost) / abs(pp_cost)
    assert rel <= COST_REL_TOL, (case.name, ours_cost, pp_cost, rel)


def test_dispatch_matches_runopp(case: Case) -> None:
    theirs = _pp_dispatch_by_gen_lookup_order(case.pp)
    by_id = {g.id: g.p_mw for g in case.ours.generators}
    ours = np.array([by_id[f"gen-{k + 1}"] for k in range(len(theirs))])
    diffs = np.abs(ours - theirs)
    worst = int(np.argmax(diffs))
    assert diffs[worst] <= DISPATCH_ABS_TOL_MW, (
        case.name,
        worst,
        diffs[worst],
        ours[worst],
        theirs[worst],
    )


def test_voltages_match_runopp(case: Case) -> None:
    """Bus order: pandapower's ``bus`` table keeps the MATPOWER row order, as our ids do."""
    theirs = np.asarray(case.pp.res_bus.vm_pu.to_numpy(), dtype=np.float64)
    ours = np.array([b.vm_pu for b in case.ours.buses])
    assert ours.shape == theirs.shape, case.name
    diffs = np.abs(ours - theirs)
    worst = int(np.argmax(diffs))
    assert diffs[worst] <= VOLTAGE_ABS_TOL_PU, (case.name, worst, diffs[worst])
