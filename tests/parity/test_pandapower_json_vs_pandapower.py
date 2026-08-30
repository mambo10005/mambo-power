"""AC-2: pandapower's own solvers agree with mambo's on the network ``io.pandapower_json``
exports, and the export re-imports (A6/A16 measurement).

Oracle path: ``io.matpower.load(fixtures/<case>.m)`` -> ``io.pandapower_json.dumps`` ->
``pp.from_json_string`` -> ``pp.rundcpp`` / ``pp.runpp(init="flat", trafo_model="pi")``. Ours is
``pf.solve_dc`` / ``pf.solve_ac(AcOptions(init="flat", q_limits=False))`` on the *original*
``Network`` (the M8 invariant: the oracle runs the converted network, mambo the original).

Alignment rules (convention differences, not tolerances): angles are compared after
subtracting the oracle's slack angle; the exporter writes lines in mambo branch order into
``line`` and transformers into ``trafo`` (``from_bus`` = ``hv_bus``) with the branch id as
``name``, so flows are read back by table and name. Q-limits are off on both sides (``runpp``'s
default).

Tolerances (AC-2): 1e-6 deg / MW on the DC angles and flows, 1e-6 pu on the AC voltages.

A16 (the ``nets_equal`` half of AC-2, assumption A6) is *measured* here, not tolerated:
``test_nets_equal_round_trip_measured`` pins the exact set of carried tables on which
``pp.toolbox.nets_equal(from_json(dumps(loads(to_json(pn)))), pn)`` holds on 3.3.0, and
``test_carried_values_survive_the_round_trip`` shows that every value column the model carries
does come back. The strict failures are: ids written into ``name`` (pandapower's own cases carry
``None``); ``bus.name``/``bus.zone`` dtype (int/float in pandapower, ``str`` ids in the model);
GeoJSON whitespace; the default-column set ``create_*`` adds versus what ``from_ppc`` added
(``line.type``, ``load.type``, ``max_loading_percent``, ``controllable``, ...); and
1e-13-level float noise in ``vk_percent``/``tap_step_percent``.
"""

from __future__ import annotations

import warnings
from dataclasses import dataclass
from typing import Any

import numpy as np
import pytest

from mambo_power.io import matpower
from mambo_power.io import pandapower_json as pj
from mambo_power.pf import AcOptions, solve_ac, solve_dc
from mambo_power.results import AcPowerFlowResult, DcPowerFlowResult
from tests._fixtures import FIXTURES, FIXTURES_DIR

pp = pytest.importorskip("pandapower")

TOL_DC = 1e-6
TOL_VM = 1e-6
CASES = ["case14", "case30", "case57"]


@dataclass
class Case:
    name: str
    pp_dc: Any
    pp_ac: Any
    dc: DcPowerFlowResult
    ac: AcPowerFlowResult
    slack_id: str


def _from_export(net: Any) -> Any:
    return pp.from_json_string(pj.dumps(net))


@pytest.fixture(scope="module", params=CASES)
def case(request: pytest.FixtureRequest) -> Case:
    net = matpower.load(FIXTURES_DIR / f"{request.param}.m")
    slack_id = next(b.id for b in net.buses if b.type == "slack")
    pp_dc, pp_ac = _from_export(net), _from_export(net)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        pp.rundcpp(pp_dc, numba=False, trafo_model="pi")
        pp.runpp(
            pp_ac,
            init="flat",
            tolerance_mva=1e-8,
            enforce_q_lims=False,
            trafo_model="pi",
            max_iteration=50,
            calculate_voltage_angles=True,
            numba=False,
        )
    assert pp_ac.converged
    ac = solve_ac(net, options=AcOptions(init="flat", q_limits=False))
    assert ac.converged
    return Case(request.param, pp_dc, pp_ac, solve_dc(net), ac, slack_id)


def _bus_row(pn: Any, bus_id: str) -> int:
    rows = pn.bus.index[pn.bus.name == bus_id]
    assert len(rows) == 1, bus_id
    return int(rows[0])


def _oracle_from_flows(pn: Any, branches: list[Any]) -> dict[str, float]:
    line_of = {str(name): int(i) for i, name in pn.line.name.items()}
    trafo_of = {str(name): int(i) for i, name in pn.trafo.name.items()}
    flows: dict[str, float] = {}
    for br in branches:
        if br.id in line_of:
            row = pn.line.loc[line_of[br.id]]
            assert (pn.bus.name[row.from_bus], pn.bus.name[row.to_bus]) == (br.from_bus, br.to_bus)
            flows[br.id] = float(pn.res_line.at[line_of[br.id], "p_from_mw"])
        else:
            row = pn.trafo.loc[trafo_of[br.id]]
            assert (pn.bus.name[row.hv_bus], pn.bus.name[row.lv_bus]) == (br.from_bus, br.to_bus)
            flows[br.id] = float(pn.res_trafo.at[trafo_of[br.id], "p_hv_mw"])
    return flows


# --- DC ---------------------------------------------------------------------------------------


def test_dc_angles_match_rundcpp(case: Case) -> None:
    va = case.pp_dc.res_bus.va_degree
    offset = float(va.loc[_bus_row(case.pp_dc, case.slack_id)])
    diffs = {
        b.id: abs(b.va_deg - (float(va.loc[_bus_row(case.pp_dc, b.id)]) - offset))
        for b in case.dc.buses
    }
    worst = max(diffs, key=diffs.__getitem__)
    assert diffs[worst] <= TOL_DC, (case.name, worst, diffs[worst])
    assert max(abs(b.va_deg) for b in case.dc.buses) > 0.1


def test_dc_branch_flows_match_rundcpp(case: Case) -> None:
    theirs = _oracle_from_flows(case.pp_dc, case.dc.branches)
    assert len(theirs) == len(case.dc.branches) == len(case.pp_dc.line) + len(case.pp_dc.trafo)
    diffs = {b.id: abs(b.p_from_mw - theirs[b.id]) for b in case.dc.branches}
    worst = max(diffs, key=diffs.__getitem__)
    assert diffs[worst] <= TOL_DC, (case.name, worst, diffs[worst])


# --- AC ---------------------------------------------------------------------------------------


def test_ac_voltages_match_runpp(case: Case) -> None:
    vm, va = case.pp_ac.res_bus.vm_pu, case.pp_ac.res_bus.va_degree
    offset = float(va.loc[_bus_row(case.pp_ac, case.slack_id)])
    for b in case.ac.buses:
        row = _bus_row(case.pp_ac, b.id)
        assert abs(b.vm_pu - float(vm.loc[row])) <= TOL_VM, (case.name, b.id)
        assert abs(b.va_deg - (float(va.loc[row]) - offset)) <= 1e-4, (case.name, b.id)


def test_ac_branch_flows_match_runpp(case: Case) -> None:
    theirs = _oracle_from_flows(case.pp_ac, case.ac.branches)
    diffs = {b.id: abs(b.p_from_mw - theirs[b.id]) for b in case.ac.branches}
    worst = max(diffs, key=diffs.__getitem__)
    assert diffs[worst] <= 1e-4, (case.name, worst, diffs[worst])


# --- every bundled fixture loads in pandapower ---------------------------------------------------


@pytest.mark.parametrize("name", FIXTURES)
def test_every_fixture_export_loads_in_pandapower(name: str) -> None:
    path = FIXTURES_DIR / f"{name}.m"
    if not path.exists():
        pytest.skip(f"{name}.m not present")
    net = matpower.load(path)
    text, report = pj.dumps_with_report(net)
    pn = pp.from_json_string(text)
    assert len(pn.bus) == len(net.buses)
    assert len(pn.line) + len(pn.trafo) == len(net.branches)
    assert len(pn.ext_grid) + len(pn.gen) + len(pn.sgen) == len(net.generators)
    assert not report.has_errors


# --- A16: nets_equal on pandapower's own cases, measured ------------------------------------------

CARRIED_TABLES = [
    "bus", "ext_grid", "gen", "sgen", "load", "shunt", "line", "trafo", "poly_cost", "pwl_cost",
]  # fmt: skip
NETS_EQUAL_HOLDS_ON = {"poly_cost", "pwl_cost"}
"""Measured on pandapower 3.3.0 (the module docstring says why the others fail strictly)."""

VALUE_COLUMNS: dict[str, list[str]] = {
    "bus": ["vn_kv", "in_service", "max_vm_pu", "min_vm_pu"],
    "ext_grid": ["bus", "vm_pu", "va_degree", "in_service", "max_p_mw", "min_p_mw",
                 "max_q_mvar", "min_q_mvar"],
    "gen": ["bus", "p_mw", "vm_pu", "min_q_mvar", "max_q_mvar", "in_service", "max_p_mw",
            "min_p_mw"],
    "sgen": ["bus", "p_mw", "q_mvar", "in_service"],
    "load": ["bus", "p_mw", "q_mvar", "in_service"],
    "shunt": ["bus", "q_mvar", "p_mw", "vn_kv", "step", "in_service"],
    "line": ["from_bus", "to_bus", "length_km", "r_ohm_per_km", "x_ohm_per_km", "c_nf_per_km",
             "max_i_ka", "parallel", "in_service"],
    "trafo": ["hv_bus", "lv_bus", "sn_mva", "vn_hv_kv", "vn_lv_kv", "vk_percent", "vkr_percent",
              "pfe_kw", "i0_percent", "shift_degree", "tap_side", "tap_neutral",
              "tap_step_percent", "tap_pos", "in_service"],
    "poly_cost": ["element", "et", "cp0_eur", "cp1_eur_per_mw", "cp2_eur_per_mw2"],
    "pwl_cost": ["element", "et", "points"],
}  # fmt: skip


@pytest.fixture(scope="module", params=["case14", "case30"])
def own_case(request: pytest.FixtureRequest) -> tuple[Any, Any]:
    import pandapower.networks as pn_networks

    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        original = getattr(pn_networks, request.param)()
        text = pj.dumps(pj.loads(pp.to_json(original)), f_hz=float(original.f_hz))
        return original, pp.from_json_string(text)


def test_pandapowers_own_json_round_trip_holds(own_case: tuple[Any, Any]) -> None:
    """The first half of A16: pandapower's own to_json/from_json is lossless on 3.3.0."""
    original, _ = own_case
    assert pp.toolbox.nets_equal(pp.from_json_string(pp.to_json(original)), original)


def test_nets_equal_round_trip_measured(own_case: tuple[Any, Any]) -> None:
    original, back = own_case
    holds = {t for t in CARRIED_TABLES if pp.toolbox.nets_equal(back, original, name_selection=[t])}
    assert holds == NETS_EQUAL_HOLDS_ON, holds


def test_carried_values_survive_the_round_trip(own_case: tuple[Any, Any]) -> None:
    original, back = own_case
    for table, columns in VALUE_COLUMNS.items():
        a, b = original[table], back[table]
        assert len(a) == len(b), table
        for col in columns:
            if col not in a.columns:
                continue
            x, y = list(a[col]), list(b[col])
            if table == "pwl_cost":
                assert x == y
            elif a[col].dtype.kind in "fi":
                np.testing.assert_allclose(
                    np.asarray(x, dtype=float),
                    np.asarray(y, dtype=float),
                    rtol=1e-12,
                    atol=1e-12,
                    equal_nan=True,
                    err_msg=f"{table}.{col}",
                )
            else:
                assert x == y, (table, col)
