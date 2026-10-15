"""MATPOWER ``.m`` export (:mod:`mambo_power.io.matpower_export`, ADR-032).

* **Lossless where it says so.** Every bundled ``.m`` case reads, writes and reads back as the
  identical ``Network`` — ids, costs, ratings, the derived cases' piecewise costs and emergency
  ratings included — with an empty report; the one exception (``case14_island``, an
  out-of-service ``pv`` bus the format spells ``BUS_TYPE 4``) reports the loss it suffers.
* **Another parser reads what we write**: the parity tier's independent regex + ``numpy``
  reader (``tests/parity/_mpc_reader.py``) gets the same matrices from the written file as from
  the original, column for column.
* **Everything the format cannot carry is reported, and the rest comes back**: a hand-built
  network with every droppable feature, checked drop by drop.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from mambo_power import cases
from mambo_power.io import limitations, matpower
from mambo_power.model import (
    Branch,
    Bus,
    Generator,
    ImportIssueCode,
    Load,
    Network,
    PolynomialBid,
    PolynomialCost,
    Shunt,
    Storage,
    Zone,
)
from tests.parity._mpc_reader import read_mpc_numpy

BUNDLED = [name for name in cases.available() if name.endswith(".m")]
LOSSY = {"derived/case14_island.m": "FIELD_DROPPED"}


@pytest.mark.parametrize("name", BUNDLED)
def test_bundled_cases_round_trip_losslessly(name: str) -> None:
    net = cases.load(name)
    text, report = matpower.dumps_with_report(net)
    back = matpower.loads(text)
    if name in LOSSY:
        assert report.codes == {LOSSY[name]}
        assert back != net
        return
    assert report.warnings == [] and report.errors == []
    assert back == net


@pytest.mark.parametrize("name", ["case14.m", "case300.m", "derived/case14_pwl.m"])
def test_an_independent_reader_gets_the_same_matrices(name: str, tmp_path: Path) -> None:
    original = read_mpc_numpy(cases.path(name))
    out = tmp_path / "written.m"
    matpower.dump(cases.load(name), out)
    written = read_mpc_numpy(out)
    assert written["baseMVA"] == original["baseMVA"]

    def same(table: str, columns: list[int]) -> None:
        np.testing.assert_allclose(
            written[table][:, columns], original[table][:, columns], rtol=0, atol=0
        )

    # every column the importer reads verbatim; the two it repairs are compared where it does
    # not (BASE_KV <= 0 becomes 1.0; RATE_C is read only where it exceeds a positive RATE_A)
    same("bus", [0, 1, 2, 3, 4, 5, 6, 7, 8, 10, 11, 12])
    base_kv = original["bus"][:, 9]
    np.testing.assert_allclose(written["bus"][base_kv > 0, 9], base_kv[base_kv > 0])
    assert np.all(written["bus"][base_kv <= 0, 9] == 1.0)
    same("gen", list(range(10)))
    same("branch", [0, 1, 2, 3, 4, 5, 8, 9, 10, 11, 12])
    rate_a, rate_c = original["branch"][:, 5], original["branch"][:, 7]
    kept = (rate_a > 0) & (rate_c > rate_a)
    np.testing.assert_allclose(written["branch"][kept, 7], rate_c[kept])
    assert np.all(written["branch"][~kept, 7] == 0.0)
    if original["gencost"] is not None:
        np.testing.assert_allclose(written["gencost"], original["gencost"], rtol=0, atol=0)


def _gen(gen_id: str, bus: str, **extra: object) -> Generator:
    return Generator(
        id=gen_id,
        bus=bus,
        p_mw=50.0,
        q_mvar=0.0,
        p_min_mw=0.0,
        p_max_mw=100.0,
        q_min_mvar=-50.0,
        q_max_mvar=50.0,
        v_set_pu=1.0,
        cost=PolynomialCost(coefficients=[0.01, 20.0, 5.0], startup=100.0, shutdown=10.0),
        **extra,  # type: ignore[arg-type]
    )


def _everything() -> Network:
    """One of each thing the format cannot hold, on a three-bus network."""
    return Network(
        base_mva=100.0,
        buses=[
            Bus(id="bus-1", base_kv=110.0, type="slack", vm_pu=1.02, va_deg=0.0, zone="north"),
            Bus(id="bus-2", base_kv=110.0, type="pv", area="east", zone="north"),  # no state
            Bus(id="bus-3", base_kv=110.0, type="pq", v_min_pu=0.95, v_max_pu=1.05, zone="south"),
            Bus(id="bus-4", base_kv=110.0, type="pv", in_service=False, zone="south"),
        ],
        branches=[
            Branch(id="branch-1", from_bus="bus-1", to_bus="bus-2", r=0.01, x=0.1, b=0.02),
            Branch(
                id="tie",  # renamed on the way back
                from_bus="bus-2",
                to_bus="bus-3",
                r=0.01,
                x=0.1,
                b=0.0,
                rating_mva=80.0,
                rating_emergency_mva=80.0,  # equal: reads back as none
                angle_min_deg=-360.0,  # MATPOWER's "no limit": reads back as None
                angle_max_deg=30.0,
            ),
            Branch(
                id="branch-3",
                from_bus="bus-1",
                to_bus="bus-3",
                r=0.0,
                x=0.2,
                b=0.0,
                kind="transformer",
            ),
            Branch(
                id="branch-4",
                from_bus="bus-3",
                to_bus="bus-4",
                r=0.01,
                x=0.1,
                b=0.0,
                in_service=False,
            ),
        ],
        generators=[
            _gen("gen-1", "bus-1", ramp_up_mw=10.0, min_up_periods=2),
            Generator(
                id="g2",  # renamed, and no cost: defaulted
                bus="bus-2",
                p_mw=20.0,
                q_mvar=0.0,
                p_min_mw=0.0,
                p_max_mw=50.0,
                q_min_mvar=-10.0,
                q_max_mvar=10.0,
                v_set_pu=1.0,
            ),
        ],
        loads=[
            Load(
                id="load-3",
                bus="bus-3",
                p_mw=40.0,
                q_mvar=10.0,
                bid=PolynomialBid(coefficients=[50.0, 0.0]),
            ),
            Load(id="industrial", bus="bus-3", p_mw=20.0, q_mvar=5.0),  # merged into bus-3's row
            Load(id="load-2", bus="bus-2", p_mw=10.0, q_mvar=0.0, in_service=False),
            Load(id="load-1", bus="bus-1", p_mw=0.0, q_mvar=0.0),  # zero: not an element
        ],
        shunts=[Shunt(id="cap", bus="bus-2", g_mw=0.0, b_mvar=5.0)],
        storage=[
            Storage(
                id="battery",
                bus="bus-3",
                p_max_mw=10.0,
                energy_mwh=20.0,
                soc_initial=0.5,
                efficiency_charge=0.9,
                efficiency_discharge=0.9,
            )
        ],
        zones=[Zone(id="north", name="North"), Zone(id="south"), Zone(id="west")],
    )


def test_everything_the_format_cannot_carry_is_reported_and_the_rest_comes_back() -> None:
    net = _everything()
    text, report = matpower.dumps_with_report(net)
    by_code: dict[str, list[str]] = {}
    for w in report.warnings:
        by_code.setdefault(w.code, []).append(w.message)
    assert set(by_code) == {
        "MATPOWER_ID_RENUMBERED",
        "ELEMENT_MERGED",
        "ELEMENT_DROPPED",
        "FIELD_DROPPED",
        "FIELD_DEFAULTED",
        "COST_DEFAULTED",
        "BID_DROPPED",
    }

    def named(code: str) -> set[str]:
        return {i for w in report.warnings if w.code == code for i in w.element_ids + w.bus_ids}

    assert {"tie", "g2"} <= named("MATPOWER_ID_RENUMBERED")
    assert any("zone labels" in m for m in by_code["MATPOWER_ID_RENUMBERED"])
    assert any("area labels" in m for m in by_code["MATPOWER_ID_RENUMBERED"])
    assert named("ELEMENT_MERGED") == {"industrial", "load-3", "cap"}
    assert named("ELEMENT_DROPPED") == {"load-2", "load-1", "battery", "west"}
    assert named("COST_DEFAULTED") == {"g2"}
    assert named("BID_DROPPED") == {"load-3"}
    assert named("FIELD_DEFAULTED") == {"bus-2", "bus-3", "bus-4", "bus-1"} - {"bus-1"} | {"bus-1"}
    assert named("FIELD_DROPPED") >= {"gen-1", "tie", "north", "bus-4", "branch-3"}

    back = matpower.loads(text)
    by_id = {b.id: b for b in back.buses}
    # buses: numbers kept, state and limits defaulted, the dead pv bus back as pq
    assert [b.id for b in back.buses] == ["bus-1", "bus-2", "bus-3", "bus-4"]
    assert (by_id["bus-2"].vm_pu, by_id["bus-2"].va_deg) == (1.0, 0.0)
    assert (by_id["bus-2"].v_min_pu, by_id["bus-2"].v_max_pu) == (0.9, 1.1)
    assert (by_id["bus-3"].v_min_pu, by_id["bus-3"].v_max_pu) == (0.95, 1.05)
    assert by_id["bus-4"].type == "pq" and not by_id["bus-4"].in_service
    # labels numbered by first appearance
    assert [b.zone for b in back.buses] == ["1", "1", "2", "2"]
    assert by_id["bus-2"].area == "1"
    # loads merged per bus, the dead and the zero one gone, the bid gone
    assert {ld.id: (ld.p_mw, ld.q_mvar) for ld in back.loads} == {"load-3": (60.0, 15.0)}
    assert back.loads[0].bid is None
    assert [(sh.id, sh.b_mvar) for sh in back.shunts] == [("shunt-2", 5.0)]
    # generators by position; the costless one with a zero polynomial; dropped fields gone
    g1, g2 = back.generators
    assert (g1.id, g2.id) == ("gen-1", "gen-2")
    assert g1.cost == net.generators[0].cost
    assert g1.ramp_up_mw is None and g1.min_up_periods is None
    assert g2.cost == PolynomialCost(coefficients=[0.0, 0.0], startup=0.0, shutdown=0.0)
    # branches by position; the equal emergency rating and the ±360 limit gone, the rest kept
    b1, b2, b3, b4 = back.branches
    assert (b1.id, b2.id, b3.id, b4.id) == ("branch-1", "branch-2", "branch-3", "branch-4")
    assert (b2.rating_mva, b2.rating_emergency_mva) == (80.0, None)
    assert (b2.angle_min_deg, b2.angle_max_deg) == (None, 30.0)
    assert not b3.is_transformer and b3.tap_ratio is None  # kind alone does not survive
    assert not b4.in_service
    assert back.storage == []
    assert back.base_mva == 100.0


def test_no_costs_at_all_omits_gencost_and_reads_back_none() -> None:
    net = _everything()
    for gen in net.generators:
        gen.cost = None
    text, report = matpower.dumps_with_report(net)
    assert "gencost" not in text
    assert "COST_DEFAULTED" not in report.codes
    assert all(g.cost is None for g in matpower.loads(text).generators)


def test_numbers_are_written_to_round_trip_exactly() -> None:
    net = cases.load("case14")
    net.branches[0].x = 0.1 + 1e-15
    net.generators[0].p_max_mw = 332.4000000000001
    back = matpower.loads(matpower.dumps(net))
    assert back.branches[0].x == net.branches[0].x
    assert back.generators[0].p_max_mw == net.generators[0].p_max_mw


def test_dump_writes_a_file_the_loader_reads(tmp_path: Path) -> None:
    out = tmp_path / "case.m"
    report = matpower.dump_with_report(cases.load("case30"), out)
    assert report.warnings == []
    assert matpower.load(out) == cases.load("case30")
    assert out.read_text(encoding="utf-8").startswith("function mpc = ")


def test_export_codes_are_registered() -> None:
    from typing import get_args

    for code in matpower.EXPORT_CODES:
        assert code in get_args(ImportIssueCode)
        assert code in limitations.LIMITATIONS["io.matpower"]
