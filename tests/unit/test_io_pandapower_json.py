"""W1/W2, AC-1/AC-7 (unit half): ``io.pandapower_json`` import and export against pandapower's
own ``case14``/``case30`` and hand-built networks.

AC-1: pandapower's ``case14``/``case30`` (``pp.networks`` -> ``to_json`` -> ``loads``) agree
with ``io.matpower.load(fixtures/case14.m|case30.m)`` on every bus base kV, branch ``r/x/b``,
``tap_ratio``, ``shift_deg``, ``kind``, generator limits and cost coefficients to 1e-9 — except
the deviations pandapower's own case files carry, listed in :data:`KNOWN_DEVIATIONS` and
asserted *present* (so a silently vanishing deviation is noticed too).
"""

from __future__ import annotations

import math
import subprocess
import sys
import warnings
from collections import defaultdict
from typing import Any

import pytest

from mambo_power.io import matpower
from mambo_power.io import pandapower_json as pj
from mambo_power.io.report import ExportReport, ImportReport
from mambo_power.model import (
    Branch,
    Bus,
    Generator,
    ImportIssueCode,
    Load,
    Network,
    PiecewiseBid,
    PiecewiseCost,
    PolynomialCost,
    Shunt,
    Storage,
    Zone,
)
from tests._fixtures import FIXTURES_DIR

pp = pytest.importorskip("pandapower")
pn = pytest.importorskip("pandapower.networks")

TOL = 1e-9

KNOWN_DEVIATIONS: dict[str, dict[str, Any]] = {
    # pandapower's own case files deviate from our .m fixtures in these fields (measured on
    # 3.3.0); each entry is asserted *present*, so a vanishing deviation is noticed too.
    "case14": {
        # real voltage levels where case14.m has BASE_KV = 0 (io.matpower repairs to 1.0)
        "base_kv": {"bus-1": 135.0, "bus-2": 135.0, "bus-3": 135.0, "bus-4": 135.0,
                    "bus-5": 135.0, "bus-6": 0.208, "bus-7": 14.0, "bus-8": 12.0,
                    "bus-9": 0.208, "bus-10": 0.208, "bus-11": 0.208, "bus-12": 0.208,
                    "bus-13": 0.208, "bus-14": 0.208},
        # .m rows 14 (7-8) and 15 (7-9) are plain lines; pandapower made them nominal-tap
        # trafos because their ends differ in kV (14 vs 12, 14 vs 0.208) — the A7 case
        "kind": {"branch-14": "transformer", "branch-15": "transformer"},
        # the ext_grid cost coefficient is rounded (0.0430293 vs the .m's 0.0430292599)
        "cost": {"gen-1": [0.0430293, 20.0, 0.0]},
        # MATPOWER's 9900 MVA "unrated" sentinel on every branch; the fixture carries RATE_A 0
        "rating_mva": 9900.0,
    },
    # pandapower's case30 carries MATPOWER's loss zones 1/2/3; the fixture has ZONE 1 throughout
    "case30": {
        "zone": {"bus-10": "3", "bus-12": "2", "bus-13": "2", "bus-14": "2", "bus-15": "2",
                 "bus-16": "2", "bus-17": "2", "bus-18": "2", "bus-19": "2", "bus-20": "2",
                 "bus-21": "3", "bus-22": "3", "bus-23": "2", "bus-24": "3", "bus-25": "3",
                 "bus-26": "3", "bus-27": "3", "bus-29": "3", "bus-30": "3"},
    },
}  # fmt: skip


def _pp_json(name: str) -> str:
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        return pp.to_json(getattr(pn, name)())


@pytest.fixture(scope="module", params=["case14", "case30"])
def pair(request: pytest.FixtureRequest) -> tuple[str, Network, ImportReport, Network]:
    name = request.param
    net, report = pj.loads_with_report(_pp_json(name))
    return name, net, report, matpower.load(FIXTURES_DIR / f"{name}.m")


def _bus_key(bus_id: str) -> str:
    """pandapower's ``bus.name`` is the MATPOWER bus number: ``"7"`` <-> ``"bus-7"``."""
    return bus_id.removeprefix("bus-")


def _match_branches(ours: Network, ref: Network) -> list[tuple[Branch, Branch]]:
    by_pair: dict[tuple[str, str], list[Branch]] = defaultdict(list)
    for br in ours.branches:
        by_pair[(br.from_bus, br.to_bus)].append(br)
    pairs: list[tuple[Branch, Branch]] = []
    for rb in ref.branches:
        key = (_bus_key(rb.from_bus), _bus_key(rb.to_bus))
        candidates = by_pair.get(key) or by_pair.get(key[::-1]) or []
        assert len(candidates) == 1, (rb.id, key, candidates)
        pairs.append((candidates[0], rb))
    return pairs


# --- AC-1: pandapower's own cases vs the .m fixtures --------------------------------------------


def test_import_report_is_empty_on_pandapowers_own_cases(pair: Any) -> None:
    name, _, report, _ = pair
    assert report.warnings == [] and report.errors == [], (name, report.as_strings())


def test_buses_match_matpower_except_listed_base_kv(pair: Any) -> None:
    name, net, _, ref = pair
    deviations = KNOWN_DEVIATIONS[name].get("base_kv", {})
    assert [b.id for b in net.buses] == [_bus_key(b.id) for b in ref.buses]
    for ours, theirs in zip(net.buses, ref.buses, strict=True):
        assert ours.type == theirs.type, theirs.id
        assert ours.in_service == theirs.in_service
        if theirs.id in deviations:
            assert ours.base_kv == deviations[theirs.id], theirs.id
            assert theirs.base_kv == matpower.DEFAULT_BASE_KV  # the BASE_KV=0 repair
        else:
            assert abs(ours.base_kv - theirs.base_kv) <= TOL, theirs.id
        assert ours.v_min_pu == theirs.v_min_pu and ours.v_max_pu == theirs.v_max_pu
        zones = KNOWN_DEVIATIONS[name].get("zone", {})
        assert ours.zone == zones.get(theirs.id, theirs.zone), theirs.id
        if theirs.id in zones:
            assert theirs.zone != zones[theirs.id]


def test_branches_match_matpower_to_1e9(pair: Any) -> None:
    name, net, _, ref = pair
    kinds = KNOWN_DEVIATIONS[name].get("kind", {})
    pairs = _match_branches(net, ref)
    assert len(pairs) == len(net.branches) == len(ref.branches)
    for ours, theirs in pairs:
        flipped = ours.from_bus != _bus_key(theirs.from_bus)
        assert not flipped or theirs.tap_ratio is None, theirs.id  # taps keep orientation
        for field in ("r", "x", "b"):
            assert abs(getattr(ours, field) - getattr(theirs, field)) <= TOL, (theirs.id, field)
        assert abs((ours.tap_ratio or 1.0) - (theirs.tap_ratio or 1.0)) <= TOL, theirs.id
        assert abs((ours.shift_deg or 0.0) - (theirs.shift_deg or 0.0)) <= TOL, theirs.id
        rating = KNOWN_DEVIATIONS[name].get("rating_mva", theirs.rating_mva)
        assert ours.rating_mva == pytest.approx(rating, abs=1e-6), theirs.id
        if "rating_mva" in KNOWN_DEVIATIONS[name]:
            assert theirs.rating_mva is None
        assert ours.kind == kinds.get(theirs.id, theirs.kind), theirs.id
        if theirs.id in kinds:
            assert theirs.kind != kinds[theirs.id]  # the deviation is real


def test_generators_match_matpower_to_1e9(pair: Any) -> None:
    name, net, _, ref = pair
    costs = KNOWN_DEVIATIONS[name].get("cost", {})
    assert len(net.generators) == len(ref.generators)
    for ours, theirs in zip(net.generators, ref.generators, strict=True):
        assert ours.bus == _bus_key(theirs.bus), theirs.id
        for field in ("p_min_mw", "p_max_mw", "q_min_mvar", "q_max_mvar", "v_set_pu"):
            assert abs(getattr(ours, field) - getattr(theirs, field)) <= TOL, (theirs.id, field)
        assert isinstance(ours.cost, PolynomialCost) and isinstance(theirs.cost, PolynomialCost)
        expected = costs.get(theirs.id, theirs.cost.coefficients)
        assert len(ours.cost.coefficients) == len(expected) == 3
        for a, b in zip(ours.cost.coefficients, expected, strict=True):
            assert abs(a - b) <= TOL, (theirs.id, ours.cost.coefficients, expected)
        if theirs.id in costs:
            assert (
                max(abs(a - b) for a, b in zip(expected, theirs.cost.coefficients, strict=True))
                > TOL
            )


def test_loads_and_shunts_match_matpower(pair: Any) -> None:
    _, net, _, ref = pair
    ours_loads = {(ld.bus, ld.p_mw, ld.q_mvar) for ld in net.loads}
    assert ours_loads == {(_bus_key(ld.bus), ld.p_mw, ld.q_mvar) for ld in ref.loads}
    ours_shunts = {(s.bus, round(s.g_mw, 9), round(s.b_mvar, 9)) for s in net.shunts}
    assert ours_shunts == {(_bus_key(s.bus), s.g_mw, s.b_mvar) for s in ref.shunts}
    assert net.shunts, "case14/case30 both carry a shunt: the sign convention is exercised"


# --- AC-1: the ext_grid rule, drops and defaults -------------------------------------------------


def _pp_two_bus() -> Any:
    net = pp.create_empty_network(sn_mva=100.0, f_hz=50.0)
    b0 = pp.create_bus(net, 110.0, name="a")
    b1 = pp.create_bus(net, 110.0, name="b")
    pp.create_ext_grid(net, b0, vm_pu=1.02, max_p_mw=100.0, min_p_mw=0.0,
                       max_q_mvar=50.0, min_q_mvar=-50.0)  # fmt: skip
    pp.create_line_from_parameters(net, b0, b1, 1.0, 1.21, 12.1, 100.0, max_i_ka=1.0, name="l")
    pp.create_load(net, b1, 20.0, 5.0, name="d")
    return net


def test_second_ext_grid_becomes_pv_generator_with_one_repair_warning() -> None:
    net = _pp_two_bus()
    pp.create_ext_grid(net, 1, vm_pu=1.0, name="second", max_p_mw=10.0, min_p_mw=0.0,
                       max_q_mvar=5.0, min_q_mvar=-5.0)  # fmt: skip
    ours, report = pj.loads_with_report(pp.to_json(net))
    assert [b.type for b in ours.buses] == ["slack", "pv"]
    assert [w.code for w in report.warnings] == ["EXTRA_EXT_GRID_DEMOTED"]
    assert report.warnings[0].element_ids == ["second"] and report.warnings[0].bus_ids == ["b"]


def test_dropped_columns_are_reported_with_element_and_field() -> None:
    net = _pp_two_bus()
    net.line.at[0, "g_us_per_km"] = 3.0
    net.load.at[0, "const_z_p_percent"] = 50.0
    pp.create_switch(net, 0, 0, et="l", closed=True)
    ours, report = pj.loads_with_report(pp.to_json(net))
    assert report.codes == {"COLUMN_DROPPED", "ELEMENT_DROPPED"}
    texts = report.as_strings()
    assert any("l" in w.element_ids and "g_us_per_km" in w.message for w in report.warnings), texts
    assert any(
        "d" in w.element_ids and "const_z_p_percent" in w.message for w in report.warnings
    ), texts
    assert any(w.code == "ELEMENT_DROPPED" and "switch[0]" in w.message for w in report.warnings)
    assert len(ours.branches) == 1 and ours.branches[0].kind == "line"


def test_missing_limits_are_pinned_at_the_setpoint_and_reported() -> None:
    net = _pp_two_bus()
    pp.create_sgen(net, 1, p_mw=7.0, q_mvar=1.0, name="s")
    ours, report = pj.loads_with_report(pp.to_json(net))
    s = next(g for g in ours.generators if g.id == "s")
    assert (s.p_min_mw, s.p_max_mw, s.q_min_mvar, s.q_max_mvar) == (7.0, 7.0, 1.0, 1.0)
    assert ours.buses[1].type == "pq"  # an sgen does not make a bus PV
    fields = {w.message.split()[1] for w in report.warnings if w.code == "FIELD_DEFAULTED"}
    assert fields == {"min_p_mw", "max_p_mw", "min_q_mvar", "max_q_mvar"}
    assert all(w.element_ids == ["s"] for w in report.warnings)


def test_shunt_sign_and_tap_conversion() -> None:
    net = _pp_two_bus()
    pp.create_shunt(net, 1, q_mvar=-19.0, p_mw=0.5, vn_kv=110.0, name="c")
    b2 = pp.create_bus(net, 20.0, name="c2")
    pp.create_transformer_from_parameters(
        net, 1, b2, sn_mva=50.0, vn_hv_kv=110.0, vn_lv_kv=20.0, vkr_percent=1.0, vk_percent=10.0,
        pfe_kw=0.0, i0_percent=0.0, shift_degree=30.0, tap_side="hv", tap_neutral=0, tap_pos=2,
        tap_step_percent=1.25, tap_changer_type="Ratio", name="t",
    )  # fmt: skip
    pp.create_load(net, b2, 1.0, 0.0)
    ours, report = pj.loads_with_report(pp.to_json(net))
    assert report.warnings == []
    shunt = ours.shunts[0]
    assert (shunt.b_mvar, shunt.g_mw) == (19.0, 0.5)  # consumption -> injection
    t = next(b for b in ours.branches if b.id == "t")
    assert t.kind == "transformer" and (t.from_bus, t.to_bus) == ("b", "c2")
    assert t.tap_ratio == pytest.approx(1.025) and t.shift_deg == 30.0
    z = 0.10 * 100.0 / 50.0
    assert t.r == pytest.approx(0.01 * 100.0 / 50.0) and t.x == pytest.approx(
        math.sqrt(z * z - t.r * t.r)
    )
    assert t.rating_mva == 50.0


def test_pwl_cost_imports_as_piecewise_breakpoints() -> None:
    net = _pp_two_bus()
    pp.create_gen(net, 1, p_mw=5.0, vm_pu=1.0, max_p_mw=100.0, min_p_mw=0.0,
                  max_q_mvar=1.0, min_q_mvar=-1.0, name="g")  # fmt: skip
    pp.create_pwl_cost(net, 0, "gen", points=[[0, 50, 10], [50, 100, 20]])
    ours, _ = pj.loads_with_report(pp.to_json(net))
    g = next(g for g in ours.generators if g.id == "g")
    assert isinstance(g.cost, PiecewiseCost)
    assert g.cost.points == [(0.0, 0.0), (50.0, 500.0), (100.0, 1500.0)]


def test_core_package_imports_without_pandapower() -> None:
    code = "import sys, mambo_power.io.pandapower_json; print('pandapower' in sys.modules)"
    out = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, check=True)
    assert out.stdout.strip() == "False"


# --- W2 / AC-7: export drops and round trip ------------------------------------------------------


def _net_with_everything() -> Network:
    return Network(
        base_mva=100.0,
        buses=[
            Bus(id="s", base_kv=110.0, type="slack", area="A", zone="z1", vm_pu=1.02, va_deg=0.0),
            Bus(id="v", base_kv=110.0, type="pv", area="A", zone="z1"),
            Bus(id="q", base_kv=20.0, type="pq"),
        ],
        branches=[
            Branch(id="l", from_bus="s", to_bus="v", r=0.01, x=0.1, b=0.02, rating_mva=100.0),
            Branch(
                id="t",
                from_bus="v",
                to_bus="q",
                r=0.005,
                x=0.05,
                b=0.01,
                tap_ratio=1.05,
                shift_deg=10.0,
                rating_mva=40.0,
            ),  # fmt: skip
        ],
        generators=[
            Generator(
                id="g0",
                bus="s",
                p_mw=10.0,
                q_mvar=1.0,
                p_min_mw=0.0,
                p_max_mw=100.0,
                q_min_mvar=-50.0,
                q_max_mvar=50.0,
                v_set_pu=1.02,
                cost=PolynomialCost(coefficients=[1.0, 0.1, 2.0, 5.0], startup=3.0),
            ),
            Generator(
                id="g1",
                bus="v",
                p_mw=5.0,
                q_mvar=0.0,
                p_min_mw=0.0,
                p_max_mw=50.0,
                q_min_mvar=-10.0,
                q_max_mvar=10.0,
                v_set_pu=1.0,
                ramp_up_mw=5.0,
                cost=PiecewiseCost(points=[(0.0, 7.0), (25.0, 107.0), (50.0, 307.0)]),
            ),
            Generator(
                id="g2",
                bus="q",
                p_mw=1.0,
                q_mvar=0.5,
                p_min_mw=0.0,
                p_max_mw=2.0,
                q_min_mvar=-1.0,
                q_max_mvar=1.0,
                v_set_pu=1.0,
                cost=PolynomialCost(coefficients=[0.5, 20.0, 1.0]),
            ),
        ],  # fmt: skip
        loads=[
            Load(id="d", bus="q", p_mw=3.0, q_mvar=1.0),
            Load(
                id="e",
                bus="v",
                p_mw=2.0,
                q_mvar=0.0,
                bid=PiecewiseBid(points=[(0.0, 0.0), (2.0, 100.0)]),
            ),  # fmt: skip
        ],
        shunts=[Shunt(id="c", bus="q", g_mw=0.0, b_mvar=1.0)],
        storage=[
            Storage(
                id="st",
                bus="q",
                p_max_mw=1.0,
                energy_mwh=4.0,
                soc_initial=0.5,
                efficiency_charge=0.9,
                efficiency_discharge=0.9,
            )
        ],  # fmt: skip
        zones=[Zone(id="z1", name="north")],
    )


def test_export_reports_every_drop_by_element_and_field() -> None:
    text, report = pj.dumps_with_report(_net_with_everything())
    assert isinstance(report, ExportReport) and not report.has_errors
    by_element: dict[str, set[str]] = defaultdict(set)
    for w in report.warnings:
        assert len(w.element_ids) == 1, w
        by_element[w.element_ids[0]].add(w.code)
    assert by_element == {
        "z1": {"FIELD_DROPPED"},  # zone.name
        "g0": {"FIELD_DROPPED", "COST_DROPPED"},  # p_mw/q_mvar setpoints, startup, degree 3
        "g1": {"FIELD_DROPPED"},  # ramp_up_mw, pwl offset 7.0
        "e": {"BID_DROPPED"},
        "st": {"ELEMENT_DROPPED"},
        "t": {"FIELD_DROPPED"},  # b on a trafo
    }, dict(by_element)  # g2 (PQ bus -> sgen) loses nothing: p, q and limits all have columns
    messages = "\n".join(report.as_strings())
    for needle in ("g0: p_mw=10.0", "g0: q_mvar=1.0", "cost.startup=3.0", "degree 3",
                   "g1: ramp_up_mw=5.0", "cost.points[0][1]=7.0", "t: b=0.01",
                   "e: bid (piecewise)", "st: storage", "z1: zone.name='north'"):  # fmt: skip
        assert needle in messages, needle
    reloaded = pp.from_json_string(text)
    assert len(reloaded.ext_grid) == 1 and len(reloaded.gen) == 1 and len(reloaded.sgen) == 1
    assert list(reloaded.poly_cost.et) == ["sgen"]  # g0's degree-3 cost was never approximated
    assert list(reloaded.pwl_cost.et) == ["gen"]
    assert reloaded.pwl_cost.points.iloc[0] == [[0.0, 25.0, 4.0], [25.0, 50.0, 8.0]]
    assert list(reloaded.bus.area) == ["A", "A", None]


def test_lossless_network_exports_with_an_empty_report_and_round_trips() -> None:
    net = _net_with_everything()
    net.zones[0].name = None
    net.storage = []
    net.loads[1].bid = None
    net.branches[1].b = 0.0
    g0, g1 = net.generators[0], net.generators[1]
    g0.p_mw = g0.q_mvar = 0.0
    g0.cost = PolynomialCost(coefficients=[0.1, 2.0, 5.0])
    g1.ramp_up_mw = None
    g1.cost = PiecewiseCost(points=[(0.0, 0.0), (25.0, 100.0), (50.0, 300.0)])
    text, report = pj.dumps_with_report(net)
    assert report.warnings == [], report.as_strings()
    back, in_report = pj.loads_with_report(text)
    assert in_report.warnings == [], in_report.as_strings()
    assert back.base_mva == net.base_mva
    assert [(b.id, b.base_kv, b.type, b.area, b.zone, b.vm_pu, b.va_deg) for b in back.buses] == [
        (b.id, b.base_kv, b.type, b.area, b.zone, b.vm_pu, b.va_deg) for b in net.buses
    ]
    for ours, theirs in zip(back.branches, net.branches, strict=True):
        assert ours.id == theirs.id and ours.kind == theirs.kind
        assert (ours.from_bus, ours.to_bus) == (theirs.from_bus, theirs.to_bus)
        for field in ("r", "x", "b", "rating_mva", "tap_ratio", "shift_deg"):
            a, b = getattr(ours, field), getattr(theirs, field)
            assert a == b or (a is not None and b is not None and abs(a - b) <= 1e-12), (
                theirs.id, field, a, b,
            )  # fmt: skip
    for ours, theirs in zip(back.generators, net.generators, strict=True):
        assert ours.model_dump(exclude={"cost"}) == theirs.model_dump(exclude={"cost"})
        assert ours.cost == theirs.cost
    assert back.loads == net.loads and back.shunts == net.shunts and back.zones == net.zones


def test_unrated_transformer_export_reports_the_invented_sn_mva() -> None:
    net = _net_with_everything()
    net.branches[1].rating_mva = None
    _, report = pj.dumps_with_report(net)
    hits = [w for w in report.warnings if w.code == "FIELD_DEFAULTED"]
    assert [w.element_ids for w in hits] == [["t"]] and "sn_mva" in hits[0].message


def test_codes_are_a_subset_of_the_closed_issue_code_set() -> None:
    from typing import get_args

    assert set(pj.CODES) <= set(get_args(ImportIssueCode))
    assert "ISLAND_DEACTIVATED" in pj.CODES
