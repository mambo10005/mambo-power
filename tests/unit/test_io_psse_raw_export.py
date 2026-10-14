"""PSS/E RAW v33 export (:mod:`mambo_power.io.psse_raw_export`, ADR-022).

The bundled ``case14_v33.raw`` is the fixed point: read, written and read again it is the same
``Network``, with an empty export report. Every bundled MATPOWER case goes through the writer and
comes back with the same physics — the branches re-ordered (RAW keeps transformers in their own
section) but equal pair by pair, and the AC power flow identical — while the report names the
costs the format cannot carry and the ids it had to number.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from mambo_power import cases, pf
from mambo_power.io import psse_raw
from mambo_power.model import (
    Branch,
    Bus,
    Generator,
    Load,
    Network,
    PolynomialBid,
    PolynomialCost,
    Shunt,
    Storage,
    Zone,
)

MATPOWER_CASES = ["case14", "case30", "case_ieee30", "case57", "case118", "case300"]


def test_the_bundled_raw_case_is_a_fixed_point() -> None:
    net = psse_raw.load(cases.path("case14_v33.raw"))
    text, report = psse_raw.dumps_with_report(net)

    assert report.warnings == [] and report.errors == []
    assert psse_raw.loads(text) == net
    assert text.splitlines()[0].startswith("0, 100.00, 33,")
    assert text.rstrip().endswith("Q")


@pytest.mark.parametrize("name", MATPOWER_CASES)
def test_bundled_matpower_cases_round_trip_with_the_same_physics(name: str) -> None:
    net = cases.load(name)
    text, report = psse_raw.dumps_with_report(net)
    back = psse_raw.loads(text)

    assert "COST_DROPPED" in report.codes
    assert [(b.id, b.base_kv, b.type, b.in_service) for b in back.buses] == [
        (b.id, b.base_kv, b.type, b.in_service) for b in net.buses
    ]
    # a transformer's line charging has no RAW field: dropped, and said so (case300 has some)
    charged = [br.id for br in net.branches if br.is_transformer and br.b != 0.0]
    if charged:
        (dropped,) = [w for w in report.warnings if w.code == "FIELD_DROPPED"]
        assert dropped.element_ids == charged
    by_pair = {(br.from_bus, br.to_bus, br.r, br.x): br for br in net.branches}
    assert len(back.branches) == len(net.branches)
    for br in back.branches:
        original = by_pair[(br.from_bus, br.to_bus, br.r, br.x)]
        assert br.b == (0.0 if original.id in charged else original.b)
        assert br.rating_mva == original.rating_mva
        assert (br.tap_ratio or 1.0) == (original.tap_ratio or 1.0)
        assert (br.shift_deg or 0.0) == (original.shift_deg or 0.0)
        assert br.in_service == original.in_service and br.kind == original.kind
    assert [
        (g.bus, g.p_mw, g.q_mvar, g.p_max_mw, g.q_min_mvar, g.v_set_pu) for g in back.generators
    ] == [(g.bus, g.p_mw, g.q_mvar, g.p_max_mw, g.q_min_mvar, g.v_set_pu) for g in net.generators]
    assert sum(ld.p_mw for ld in back.loads) == sum(ld.p_mw for ld in net.loads)
    assert [(s.bus, s.g_mw, s.b_mvar) for s in back.shunts] == [
        (s.bus, s.g_mw, s.b_mvar) for s in net.shunts
    ]
    if charged:
        return  # the dropped charging moves the AC solution: nothing to compare exactly
    original = pf.solve_ac(net)
    again = pf.solve_ac(back)
    assert again.converged and original.converged
    vm = np.array([b.vm_pu for b in original.buses]) - np.array([b.vm_pu for b in again.buses])
    assert np.max(np.abs(vm)) < 1e-12


def _small() -> Network:
    return Network(
        base_mva=100.0,
        buses=[
            Bus(id="north", base_kv=138.0, type="slack", area="N", zone="z1"),
            Bus(id="south", base_kv=138.0, type="pq", area="S", zone="z1", v_min_pu=0.95),
        ],
        zones=[Zone(id="z1", name="Zone one")],
        branches=[
            Branch(
                id="tie",
                from_bus="north",
                to_bus="south",
                r=0.01,
                x=0.1,
                b=0.02,
                rating_mva=80.0,
                rating_emergency_mva=100.0,
            ),
            Branch(
                id="xf",
                from_bus="north",
                to_bus="south",
                r=0.0,
                x=0.2,
                b=0.01,
                tap_ratio=0.98,
                shift_deg=3.0,
                rating_mva=50.0,
                rating_emergency_mva=60.0,
            ),
        ],
        generators=[
            Generator(
                id="g",
                bus="north",
                p_mw=50.0,
                q_mvar=0.0,
                p_min_mw=0.0,
                p_max_mw=100.0,
                q_min_mvar=-50.0,
                q_max_mvar=50.0,
                v_set_pu=1.02,
                ramp_up_mw=10.0,
                min_up_periods=2,
                cost=PolynomialCost(coefficients=[20.0, 0.0]),
            )
        ],
        loads=[
            Load(
                id="ld",
                bus="south",
                p_mw=50.0,
                q_mvar=10.0,
                bid=PolynomialBid(coefficients=[80.0, 0.0]),
            ),
            Load(id="ld2", bus="south", p_mw=5.0, q_mvar=1.0),
        ],
        shunts=[Shunt(id="sh", bus="south", g_mw=0.0, b_mvar=5.0)],
        storage=[
            Storage(
                id="st",
                bus="south",
                p_max_mw=10.0,
                energy_mwh=20.0,
                soc_initial=0.5,
                efficiency_charge=0.9,
                efficiency_discharge=0.9,
            )
        ],
    )


def test_everything_the_format_cannot_carry_is_reported_and_the_rest_comes_back() -> None:
    net = _small()
    text, report = psse_raw.dumps_with_report(net)
    back = psse_raw.loads(text)

    assert report.errors == []
    assert sorted(report.codes) == sorted(
        {
            "RAW_ID_RENUMBERED",
            "COST_DROPPED",
            "BID_DROPPED",
            "ELEMENT_DROPPED",
            "FIELD_DROPPED",
            "FIELD_DEFAULTED",
        }
    )
    by_code = {w.code: w for w in report.warnings}
    assert by_code["COST_DROPPED"].element_ids == ["g"]
    assert by_code["BID_DROPPED"].element_ids == ["ld"]
    assert by_code["ELEMENT_DROPPED"].element_ids == ["st"]
    dropped = [w for w in report.warnings if w.code == "FIELD_DROPPED"]
    assert any("ramp_up_mw, min_up_periods" in w.message for w in dropped)
    assert any(w.element_ids == ["xf"] for w in dropped)  # line charging on a transformer
    renumbered = [w for w in report.warnings if w.code == "RAW_ID_RENUMBERED"]
    assert {tuple(w.bus_ids) or tuple(w.element_ids) for w in renumbered} == {
        ("north", "south"),
        ("ld", "ld2"),
        ("sh",),
        ("g",),
        ("tie", "xf"),
    }

    assert [b.id for b in back.buses] == ["bus-1", "bus-2"]
    assert [b.area for b in back.buses] == ["1", "2"]
    assert back.buses[1].v_min_pu == 0.95 and back.buses[0].v_min_pu == 0.9
    assert back.zones == [Zone(id="1", name="Zone one")]
    assert [ld.id for ld in back.loads] == ["load-2-1", "load-2-2"]
    assert [ld.p_mw for ld in back.loads] == [50.0, 5.0]
    assert back.shunts[0].b_mvar == 5.0 and back.generators[0].cost is None
    line, xfmr = back.branches
    assert (line.id, line.kind, line.b, line.rating_mva, line.rating_emergency_mva) == (
        "branch-1-2-1",
        "line",
        0.02,
        80.0,
        100.0,
    )
    assert (xfmr.id, xfmr.kind, xfmr.b, xfmr.tap_ratio, xfmr.shift_deg) == (
        "branch-1-2-2",
        "transformer",
        0.0,
        0.98,
        3.0,
    )
    assert xfmr.rating_mva == 50.0  # RATC1 is written but the importer reads only branch RATEC
    assert back.storage == [] and all(ld.bid is None for ld in back.loads)


def test_dump_writes_a_file_the_loader_reads(tmp_path: Path) -> None:
    net = psse_raw.load(cases.path("case14_v33.raw"))
    target = tmp_path / "out.raw"
    report = psse_raw.dump_with_report(net, target)
    assert report.warnings == []
    assert psse_raw.load(target) == net
    psse_raw.dump(net, str(target))
    assert psse_raw.load(str(target)) == net


def test_export_codes_are_registered() -> None:
    from mambo_power.io.limitations import LIMITATIONS

    assert set(psse_raw.EXPORT_CODES) <= set(LIMITATIONS["io.psse_raw"])
