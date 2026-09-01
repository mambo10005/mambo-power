"""``io.pypsa`` unit tests (wave M8, W3 / AC-3 report half): the field map on a hand-built
network, the drop-and-report rule (D1 — nothing PyPSA cannot express is approximated), and the
one invariant the whole parity file depends on: no generator ever carries ``p_set``."""

from __future__ import annotations

import ast
import math
from pathlib import Path
from typing import Any, get_args

import pytest

from mambo_power.io import matpower
from mambo_power.io import pypsa as io_pypsa
from mambo_power.model import (
    Branch,
    Bus,
    Generator,
    ImportIssueCode,
    Load,
    Network,
    PiecewiseBid,
    PiecewiseCost,
    PolynomialBid,
    PolynomialCost,
    Shunt,
    Storage,
    Zone,
)
from tests._fixtures import FIXTURES_DIR

pytest.importorskip("pypsa")


def _gen(gid: str, bus: str, cost: PolynomialCost | PiecewiseCost | None, **kw: Any) -> Generator:
    base: dict[str, Any] = {
        "p_mw": 0.0,
        "q_mvar": 0.0,
        "p_min_mw": 10.0,
        "p_max_mw": 100.0,
        "q_min_mvar": -40.0,
        "q_max_mvar": 40.0,
        "v_set_pu": 1.02,
    }
    base.update(kw)
    return Generator(id=gid, bus=bus, cost=cost, **base)


def _hand_network() -> Network:
    """Three buses, a line, a tap+shift transformer, an off line, two generators, a load, a
    shunt, a storage unit and a zone — one of everything the exporter routes on."""
    return Network(
        base_mva=100.0,
        buses=[
            Bus(id="b1", base_kv=138.0, type="slack", v_min_pu=0.94, v_max_pu=1.06, area="A"),
            Bus(id="b2", base_kv=138.0, type="pv", v_min_pu=0.95, v_max_pu=1.05, zone="z1"),
            Bus(id="b3", base_kv=69.0, type="pq", in_service=False),
        ],
        branches=[
            Branch(id="l12", from_bus="b1", to_bus="b2", r=0.01, x=0.1, b=0.02, rating_mva=50.0),
            Branch(
                id="t23",
                from_bus="b2",
                to_bus="b3",
                r=0.0,
                x=0.2,
                b=0.0,
                tap_ratio=0.98,
                shift_deg=3.0,
                rating_mva=80.0,
            ),
            Branch(id="l13", from_bus="b1", to_bus="b3", r=0.0, x=0.3, b=0.0, in_service=False),
        ],
        generators=[
            _gen("g1", "b1", PolynomialCost(coefficients=[0.1, 20.0, 5.0])),
            _gen("g2", "b2", PolynomialCost(coefficients=[15.0, 0.0]), ramp_up_mw=30.0),
        ],
        loads=[Load(id="d1", bus="b2", p_mw=60.0, q_mvar=10.0)],
        shunts=[Shunt(id="s1", bus="b2", g_mw=2.0, b_mvar=19.0)],
        storage=[
            Storage(
                id="st1",
                bus="b1",
                p_max_mw=10.0,
                energy_mwh=40.0,
                soc_initial=0.5,
                efficiency_charge=0.9,
                efficiency_discharge=0.8,
            )
        ],
        zones=[Zone(id="z1", name="north")],
    )


def test_codes_are_registered_issue_codes() -> None:
    assert io_pypsa.CODES
    for code in io_pypsa.CODES:
        assert code in get_args(ImportIssueCode), code


def test_buses_map_name_v_nom_limits_control_active() -> None:
    n = io_pypsa.to_network(_hand_network())
    b = n.buses
    assert list(b.index) == ["b1", "b2", "b3"]
    assert b.loc["b1", "v_nom"] == 138.0
    assert b.loc["b3", "v_nom"] == 69.0
    assert b.loc["b1", "v_mag_pu_min"] == 0.94
    assert b.loc["b1", "v_mag_pu_max"] == 1.06
    assert list(b["control"]) == ["Slack", "PV", "PQ"]
    assert list(b["in_service"]) == [True, True, False]
    assert "active" not in b.columns  # PyPSA buses have no active flag; elements at b3 do
    assert b.loc["b1", "area"] == "A"
    assert b.loc["b2", "zone"] == "z1"
    # a PV bus takes its generator's voltage setpoint
    assert b.loc["b2", "v_mag_pu_set"] == 1.02


def test_line_in_ohm_and_siemens() -> None:
    n = io_pypsa.to_network(_hand_network())
    zb = 138.0**2 / 100.0
    line = n.lines.loc["l12"]
    assert (line["bus0"], line["bus1"]) == ("b1", "b2")
    assert line["r"] == pytest.approx(0.01 * zb)
    assert line["x"] == pytest.approx(0.1 * zb)
    assert line["b"] == pytest.approx(0.02 / zb)
    assert line["s_nom"] == 50.0
    assert bool(line["active"]) is True
    assert bool(n.lines.loc["l13", "active"]) is False
    # t23 is in service but reaches out-of-service b3: exported inactive, as NetworkArrays drops it
    assert bool(n.transformers.loc["t23", "active"]) is False
    assert n.lines.loc["l13", "s_nom"] == io_pypsa.UNRATED_S_NOM_MVA
    assert "t23" not in n.lines.index


def test_transformer_pi_model_x_on_s_nom_tap_and_shift() -> None:
    n = io_pypsa.to_network(_hand_network())
    t = n.transformers.loc["t23"]
    assert (t["bus0"], t["bus1"]) == ("b2", "b3")
    assert t["model"] == "pi"
    assert t["s_nom"] == 80.0
    assert t["x"] == pytest.approx(0.2 * 80.0 / 100.0)
    assert t["tap_ratio"] == 0.98
    assert t["tap_side"] == 0
    assert t["phase_shift"] == 3.0
    assert "t23" not in n.lines.index


def test_neutral_tap_transformer_routes_on_kind() -> None:
    net = _hand_network()
    net.branches.append(
        Branch(id="t0", from_bus="b1", to_bus="b2", r=0.0, x=0.1, b=0.0, kind="transformer")
    )
    n = io_pypsa.to_network(net)
    assert "t0" in n.transformers.index
    assert "t0" not in n.lines.index
    assert n.transformers.loc["t0", "tap_ratio"] == 1.0
    assert n.transformers.loc["t0", "phase_shift"] == 0.0


def test_generators_p_nom_p_min_pu_costs_and_never_p_set() -> None:
    n = io_pypsa.to_network(_hand_network())
    g = n.generators
    assert g.loc["g1", "p_nom"] == 100.0
    assert g.loc["g1", "p_min_pu"] == pytest.approx(0.1)
    assert g.loc["g1", "p_max_pu"] == 1.0
    assert g.loc["g1", "marginal_cost"] == 20.0
    assert g.loc["g1", "marginal_cost_quadratic"] == 0.1
    assert g.loc["g1", io_pypsa.COST_CONSTANT_COLUMN] == 5.0
    assert g.loc["g2", "marginal_cost"] == 15.0
    assert g.loc["g2", "marginal_cost_quadratic"] == 0.0
    assert g.loc["g2", "ramp_limit_up"] == pytest.approx(0.3)
    assert math.isnan(g.loc["g1", "ramp_limit_up"])
    assert list(g["control"]) == ["Slack", "PV"]
    # the pin: a non-NaN p_set fixes dispatch in optimize() (test_opf_vs_pypsa.py's root cause)
    assert g["p_set"].isna().all()


def test_case14_generators_carry_no_p_set() -> None:
    n = io_pypsa.to_network(matpower.load(FIXTURES_DIR / "case14.m"))
    assert n.generators["p_set"].isna().all()
    assert n.generators_t.p_set.empty


def test_elements_at_an_out_of_service_bus_are_inactive() -> None:
    net = _hand_network()
    net.loads.append(Load(id="d3", bus="b3", p_mw=1.0, q_mvar=0.0))
    net.generators.append(_gen("g3", "b3", None))
    n = io_pypsa.to_network(net)
    assert bool(n.loads.loc["d3", "active"]) is False
    assert bool(n.generators.loc["g3", "active"]) is False
    assert bool(n.loads.loc["d1", "active"]) is True


def test_loads_shunts_storage() -> None:
    n = io_pypsa.to_network(_hand_network())
    assert n.loads.loc["d1", "p_set"] == 60.0
    assert n.loads.loc["d1", "q_set"] == 10.0
    sh = n.shunt_impedances.loc["s1"]
    assert sh["g"] == pytest.approx(2.0 / 138.0**2)
    assert sh["b"] == pytest.approx(19.0 / 138.0**2)
    st = n.storage_units.loc["st1"]
    assert st["p_nom"] == 10.0
    assert st["max_hours"] == 4.0
    assert st["state_of_charge_initial"] == 20.0
    assert st["efficiency_store"] == 0.9
    assert st["efficiency_dispatch"] == 0.8
    assert n.meta["base_mva"] == 100.0


def test_report_names_q_limits_and_zone_only_on_the_hand_network() -> None:
    _, report = io_pypsa.to_network_with_report(_hand_network())
    assert not report.has_errors
    assert report.codes == {
        "PYPSA_GEN_Q_LIMITS_DROPPED",
        "PYPSA_ZONE_DROPPED",
        "PYPSA_UNRATED_S_NOM_DEFAULTED",
    }
    q_issues = [w for w in report.warnings if w.code == "PYPSA_GEN_Q_LIMITS_DROPPED"]
    assert sorted(i for w in q_issues for i in w.element_ids) == ["g1", "g2"]
    assert all("q_min_mvar" in w.message and "q_max_mvar" in w.message for w in q_issues)
    (z,) = [w for w in report.warnings if w.code == "PYPSA_ZONE_DROPPED"]
    assert z.element_ids == ["z1"]
    assert "zones" in z.message


def test_unrated_branches_are_reported_one_entry_each_naming_the_sentinel() -> None:
    """M8 walk, surprise 4: ``s_nom = UNRATED_S_NOM_MVA`` is an approximation, and the page's one
    rule is that an approximation is a report entry naming the element and the field (D1). One
    ``PYPSA_UNRATED_S_NOM_DEFAULTED`` per unrated branch -- line or transformer -- with the
    sentinel in the message; a rated branch gets none."""
    net = _hand_network()
    trafos = [br for br in net.branches if br.kind == "transformer"]
    trafos[0] = trafos[0].model_copy(update={"rating_mva": None})
    net = net.model_copy(
        update={"branches": [br for br in net.branches if br.kind == "line"] + trafos}
    )
    n, report = io_pypsa.to_network_with_report(net)
    issues = [w for w in report.warnings if w.code == "PYPSA_UNRATED_S_NOM_DEFAULTED"]
    assert sorted(i for w in issues for i in w.element_ids) == ["l13", "t23"]
    assert all(len(w.element_ids) == 1 for w in issues)
    for w in issues:
        assert "rating_mva" in w.message and "s_nom" in w.message
        assert str(io_pypsa.UNRATED_S_NOM_MVA) in w.message
        assert "UNRATED_S_NOM_MVA" in w.message
    assert n.lines.loc["l13", "s_nom"] == io_pypsa.UNRATED_S_NOM_MVA
    assert n.transformers.loc["t23", "s_nom"] == io_pypsa.UNRATED_S_NOM_MVA
    assert n.lines.loc["l12", "s_nom"] == 50.0
    assert not report.has_errors


def test_empty_report_when_nothing_is_lost() -> None:
    net = Network(
        base_mva=100.0,
        buses=[Bus(id="b1", base_kv=1.0, type="slack"), Bus(id="b2", base_kv=1.0, type="pq")],
        # rated: an unrated branch is an approximation the report names (M8 walk, surprise 4)
        branches=[Branch(id="l", from_bus="b1", to_bus="b2", r=0.0, x=0.1, b=0.0, rating_mva=10.0)],
        generators=[
            _gen(
                "g", "b1", PolynomialCost(coefficients=[10.0, 0.0]), q_min_mvar=0.0, q_max_mvar=0.0
            )
        ],
        loads=[Load(id="d", bus="b2", p_mw=5.0, q_mvar=0.0)],
    )
    _, report = io_pypsa.to_network_with_report(net)
    assert report.warnings == []
    assert report.errors == []


def test_piecewise_cost_dropped_marginal_cost_zero_and_named() -> None:
    net = _hand_network()
    net.generators[1].cost = PiecewiseCost(points=[(0.0, 0.0), (50.0, 1000.0), (100.0, 2500.0)])
    n, report = io_pypsa.to_network_with_report(net)
    assert n.generators.loc["g2", "marginal_cost"] == 0.0
    assert n.generators.loc["g2", "marginal_cost_quadratic"] == 0.0
    (w,) = [w for w in report.warnings if w.code == "PYPSA_PWL_COST_DROPPED"]
    assert w.element_ids == ["g2"]
    assert "cost" in w.message


def test_degree_three_cost_dropped_but_padded_degree_two_kept() -> None:
    net = _hand_network()
    net.generators[0].cost = PolynomialCost(coefficients=[0.001, 0.1, 20.0, 0.0])
    net.generators[1].cost = PolynomialCost(coefficients=[0.0, 0.0, 15.0, 0.0])  # padded deg 1
    n, report = io_pypsa.to_network_with_report(net)
    assert n.generators.loc["g1", "marginal_cost"] == 0.0
    assert n.generators.loc["g1", "marginal_cost_quadratic"] == 0.0
    assert n.generators.loc["g2", "marginal_cost"] == 15.0
    (w,) = [w for w in report.warnings if w.code == "PYPSA_COST_DEGREE_DROPPED"]
    assert w.element_ids == ["g1"]
    assert "degree 3" in w.message


@pytest.mark.parametrize(
    "bid",
    [
        PolynomialBid(coefficients=[-0.1, 50.0, 0.0]),
        PiecewiseBid(points=[(0.0, 0.0), (60.0, 3000.0)]),
    ],
)
def test_load_bid_dropped_and_named(bid: PolynomialBid | PiecewiseBid) -> None:
    net = _hand_network()
    net.loads[0].bid = bid
    n, report = io_pypsa.to_network_with_report(net)
    assert n.loads.loc["d1", "p_set"] == 60.0
    (w,) = [w for w in report.warnings if w.code == "PYPSA_LOAD_BID_DROPPED"]
    assert w.element_ids == ["d1"]
    assert "bid" in w.message


def test_conflicting_v_set_at_one_bus_reported() -> None:
    net = _hand_network()
    net.generators.append(_gen("g3", "b2", None, v_set_pu=1.05))
    n, report = io_pypsa.to_network_with_report(net)
    assert n.buses.loc["b2", "v_mag_pu_set"] == 1.02
    (w,) = [w for w in report.warnings if w.code == "PYPSA_GEN_VSET_CONFLICT"]
    assert w.bus_ids == ["b2"]
    assert sorted(w.element_ids) == ["g2", "g3"]


def test_zero_capacity_generator_has_no_ramp_and_is_reported() -> None:
    net = _hand_network()
    net.generators[1].p_min_mw = 0.0
    net.generators[1].p_max_mw = 0.0
    n, report = io_pypsa.to_network_with_report(net)
    assert n.generators.loc["g2", "p_nom"] == 0.0
    assert n.generators.loc["g2", "p_min_pu"] == 0.0
    assert math.isnan(n.generators.loc["g2", "ramp_limit_up"])
    (w,) = [w for w in report.warnings if w.code == "PYPSA_GEN_RAMP_DROPPED"]
    assert w.element_ids == ["g2"]
    assert "ramp_up_mw" in w.message


def test_negative_only_generator_keeps_both_limits() -> None:
    net = _hand_network()
    net.generators[1].p_min_mw = -50.0
    net.generators[1].p_max_mw = -10.0
    n = io_pypsa.to_network(net)
    g = n.generators.loc["g2"]
    assert g["p_nom"] == 50.0
    assert g["p_min_pu"] == pytest.approx(-1.0)
    assert g["p_max_pu"] == pytest.approx(-0.2)


def test_pypsa_is_imported_lazily() -> None:
    tree = ast.parse(Path(io_pypsa.__file__).read_text(encoding="utf-8"))
    names = [
        alias.name for node in tree.body if isinstance(node, ast.Import) for alias in node.names
    ] + [node.module or "" for node in tree.body if isinstance(node, ast.ImportFrom)]
    assert not any(name == "pypsa" or name.startswith("pypsa.") for name in names)


def test_tap_assigned_to_a_line_after_construction_exports_as_a_transformer() -> None:
    """M8 critic finding 3: exporters route on ``Branch.is_transformer`` (kind *or* the fields),
    so a tap assigned after construction becomes a ``Transformer`` row, not a tapless ``Line``."""
    net = _hand_network()
    line = next(b for b in net.branches if b.kind == "line")
    line.tap_ratio = 1.05
    assert line.kind == "line"
    n = io_pypsa.to_network(net)
    assert line.id in n.transformers.index and line.id not in n.lines.index
    assert n.transformers.loc[line.id, "tap_ratio"] == 1.05


def test_v_mag_pu_set_comes_from_in_service_generators_only() -> None:
    """M8 critic finding 15: an out-of-service unit's setpoint is not what the bus holds."""
    net = _hand_network()
    bus = net.generators[0].bus
    off = net.generators[0].model_copy(update={"id": "off", "v_set_pu": 1.05, "in_service": False})
    net.generators.insert(0, off)  # first at the bus, but out of service
    live = next(g for g in net.generators if g.bus == bus and g.in_service).v_set_pu
    assert live != 1.05
    n, report = io_pypsa.to_network_with_report(net)
    assert n.buses.loc[bus, "v_mag_pu_set"] == live
    assert "PYPSA_GEN_VSET_CONFLICT" not in report.codes


def test_concave_quadratic_cost_is_exported_unchanged_and_reported() -> None:
    net = _hand_network()
    g = net.generators[0]
    g.cost = PolynomialCost(coefficients=[-0.01, 10.0, 0.0])
    n, report = io_pypsa.to_network_with_report(net)
    assert n.generators.loc[g.id, "marginal_cost_quadratic"] == -0.01  # never approximated
    issues = [w for w in report.warnings if w.code == "PYPSA_COST_NONCONVEX"]
    assert len(issues) == 1 and issues[0].element_ids == [g.id]
    assert "concave" in issues[0].message
