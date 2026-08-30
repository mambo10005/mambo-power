"""PSS/E RAW v33 importer (M8 W4, AC-4): case14 parity with the .m import, hand-derived quirks,
ignored records, and file defects."""

from pathlib import Path

import pytest

from mambo_power.io import matpower, psse_raw
from mambo_power.io.psse_raw import RawImportError

FIXTURES = Path(__file__).resolve().parents[2] / "fixtures"
CASE14_RAW = FIXTURES / "case14_v33.raw"
CASE14_M = FIXTURES / "matpower" / "case14.m"
QUIRKS_RAW = FIXTURES / "synthetic_quirks_v33.raw"

TOL = 1e-9

BUS_FIELDS = (
    "base_kv",
    "type",
    "in_service",
    "vm_pu",
    "va_deg",
    "v_min_pu",
    "v_max_pu",
    "area",
    "zone",
)
BRANCH_FIELDS = ("r", "x", "b", "rating_mva", "tap_ratio", "shift_deg", "in_service", "kind")
GEN_FIELDS = (
    "p_mw",
    "q_mvar",
    "p_min_mw",
    "p_max_mw",
    "q_min_mvar",
    "q_max_mvar",
    "v_set_pu",
    "in_service",
    "cost",
)
LOAD_FIELDS = ("p_mw", "q_mvar", "in_service")
SHUNT_FIELDS = ("g_mw", "b_mvar", "in_service")


def _same(a: object, b: object) -> bool:
    if isinstance(a, float) and isinstance(b, float):
        return abs(a - b) <= TOL
    return a == b


def _assert_fields(got: object, want: object, fields: tuple[str, ...], label: str) -> None:
    for name in fields:
        g, w = getattr(got, name), getattr(want, name)
        assert _same(g, w), f"{label}.{name}: raw={g!r} matpower={w!r}"


# --- AC-4 (a): case14_v33.raw == case14.m -----------------------------------------------------


@pytest.fixture(scope="module")
def case14_pair():
    raw_net, report = psse_raw.load_with_report(CASE14_RAW)
    m_net = matpower.load(CASE14_M)
    return raw_net, m_net, report


def test_case14_base_and_counts(case14_pair):
    raw_net, m_net, _ = case14_pair
    assert raw_net.base_mva == m_net.base_mva == 100.0
    assert len(raw_net.buses) == len(m_net.buses) == 14
    assert len(raw_net.branches) == len(m_net.branches) == 20
    assert len(raw_net.generators) == len(m_net.generators) == 5
    assert len(raw_net.loads) == len(m_net.loads) == 11
    assert len(raw_net.shunts) == len(m_net.shunts) == 1


def test_case14_buses_equal(case14_pair):
    raw_net, m_net, _ = case14_pair
    raw_by_id = {b.id: b for b in raw_net.buses}
    for want in m_net.buses:
        assert want.id in raw_by_id, want.id
        _assert_fields(raw_by_id[want.id], want, BUS_FIELDS, want.id)


def test_case14_branches_equal_including_kind(case14_pair):
    raw_net, m_net, _ = case14_pair
    raw_by_ends = {(b.from_bus, b.to_bus): b for b in raw_net.branches}
    assert len(raw_by_ends) == 20
    for want in m_net.branches:
        got = raw_by_ends[(want.from_bus, want.to_bus)]
        _assert_fields(got, want, BRANCH_FIELDS, f"{want.from_bus}-{want.to_bus}")
    kinds = {b.kind for b in raw_net.branches}
    assert kinds == {"line", "transformer"}
    assert sum(b.kind == "transformer" for b in raw_net.branches) == 3


def test_case14_generators_equal_and_costless(case14_pair):
    raw_net, m_net, report = case14_pair
    raw_by_bus = {g.bus: g for g in raw_net.generators}
    for want in m_net.generators:
        got = raw_by_bus[want.bus]
        _assert_fields(got, want, tuple(f for f in GEN_FIELDS if f != "cost"), want.id)
        assert want.cost is not None  # the .m carries costs ...
        assert got.cost is None  # ... RAW cannot
    assert [w.code for w in report.warnings].count("RAW_NO_COSTS") == 1


def test_case14_loads_and_shunts_equal(case14_pair):
    raw_net, m_net, _ = case14_pair
    raw_loads = {ld.bus: ld for ld in raw_net.loads}
    for want in m_net.loads:
        _assert_fields(raw_loads[want.bus], want, LOAD_FIELDS, want.id)
    raw_shunts = {s.bus: s for s in raw_net.shunts}
    for want in m_net.shunts:
        _assert_fields(raw_shunts[want.bus], want, SHUNT_FIELDS, want.id)


def test_case14_report_is_only_base_kv_and_costs(case14_pair):
    _, _, report = case14_pair
    assert not report.errors
    codes = [w.code for w in report.warnings]
    assert codes.count("BASE_KV_REPLACED") == 14  # BASKV 0 kept from case14.m
    assert set(codes) == {"BASE_KV_REPLACED", "RAW_NO_COSTS"}


def test_case14_ids_follow_the_id_scheme(case14_pair):
    raw_net, _, _ = case14_pair
    assert raw_net.buses[0].id == "bus-1"
    assert {b.id for b in raw_net.branches if b.kind == "transformer"} == {
        "branch-4-7-1",
        "branch-4-9-1",
        "branch-5-6-1",
    }
    assert raw_net.generators[0].id == "gen-1-1"
    assert raw_net.loads[0].id == "load-2-1"
    assert raw_net.shunts[0].id == "shunt-9-1"
    assert [z.id for z in raw_net.zones] == ["1"]


def test_load_and_loads_agree_with_report_variants():
    text = CASE14_RAW.read_text(encoding="utf-8")
    assert psse_raw.load(CASE14_RAW) == psse_raw.loads(text)
    assert psse_raw.loads_with_report(text)[0] == psse_raw.load_with_report(CASE14_RAW)[0]


# --- AC-4 (b): the quirks fixture matches the hand derivation -----------------------------------


@pytest.fixture(scope="module")
def quirks():
    return psse_raw.load_with_report(QUIRKS_RAW)


def test_quirks_buses(quirks):
    net, _ = quirks
    by_id = {b.id: b for b in net.buses}
    assert list(by_id) == ["bus-1", "bus-2", "bus-3", "bus-4"]
    b1, b2, b3, b4 = (by_id[f"bus-{k}"] for k in (1, 2, 3, 4))
    assert (b1.type, b2.type, b3.type, b4.type) == ("slack", "pq", "pv", "pq")
    assert (b1.base_kv, b3.base_kv) == (138.0, 13.8)
    assert (b2.vm_pu, b2.va_deg) == (0.95, -2.5)
    assert (b3.v_min_pu, b3.v_max_pu) == (0.95, 1.05)
    assert (b4.v_min_pu, b4.v_max_pu) == (None, None)  # 9-field record
    assert (b3.area, b4.area, b4.zone) == ("2", "2", "2")
    assert {(z.id, z.name) for z in net.zones} == {("1", "ZONE-A"), ("2", "ZONE-B")}


def test_quirks_zip_load_folded_at_bus_vm(quirks):
    net, report = quirks
    loads = {ld.id: ld for ld in net.loads}
    assert set(loads) == {"load-2-1", "load-4-1", "load-4-2", "load-4-3"}
    assert abs(loads["load-2-1"].p_mw - 67.55) <= TOL
    assert abs(loads["load-2-1"].q_mvar - 15.51) <= TOL
    assert (loads["load-4-1"].p_mw, loads["load-4-1"].q_mvar) == (20.0, 5.0)
    assert (loads["load-4-2"].p_mw, loads["load-4-2"].q_mvar) == (5.0, 1.0)
    assert loads["load-4-3"].in_service is False
    zip_entries = [w for w in report.warnings if w.code == "RAW_LOAD_ZIP_FOLDED"]
    assert [w.element_ids for w in zip_entries] == [["load-2-1"]]


def test_quirks_shunts(quirks):
    net, report = quirks
    shunts = {s.id: s for s in net.shunts}
    assert set(shunts) == {
        "shunt-2-1",
        "shunt-branch-1-2-2-i",
        "shunt-branch-1-2-2-j",
        "shunt-xfmr-2-3-1",
    }
    assert (shunts["shunt-2-1"].bus, shunts["shunt-2-1"].g_mw, shunts["shunt-2-1"].b_mvar) == (
        "bus-2",
        1.0,
        15.0,
    )
    i, j = shunts["shunt-branch-1-2-2-i"], shunts["shunt-branch-1-2-2-j"]
    assert (i.bus, i.g_mw, i.b_mvar) == ("bus-1", 0.0, 1.0)
    assert (j.bus, j.g_mw, j.b_mvar) == ("bus-2", 0.2, 0.0)
    mag = shunts["shunt-xfmr-2-3-1"]
    assert mag.bus == "bus-2"
    assert abs(mag.g_mw - 0.02) <= TOL
    assert abs(mag.b_mvar - (-0.9997999799959989)) <= TOL
    assert [w.code for w in report.warnings].count("RAW_BRANCH_END_SHUNT_FOLDED") == 2
    assert [w.code for w in report.warnings].count("RAW_XFMR_MAGNETISING_FOLDED") == 1


def test_quirks_generators(quirks):
    net, report = quirks
    gens = {g.id: g for g in net.generators}
    assert set(gens) == {"gen-1-1", "gen-3-1", "gen-3-2"}
    g = gens["gen-3-1"]
    assert (g.bus, g.p_mw, g.q_mvar, g.q_max_mvar, g.q_min_mvar) == (
        "bus-3",
        30.0,
        5.0,
        50.0,
        -20.0,
    )
    assert (g.v_set_pu, g.p_max_mw, g.p_min_mw, g.in_service) == (1.02, 80.0, 10.0, True)
    short = gens["gen-3-2"]  # 18-field record, STAT 0
    assert (short.q_max_mvar, short.q_min_mvar, short.p_max_mw, short.in_service) == (
        10.0,
        -10.0,
        20.0,
        False,
    )
    assert all(g.cost is None for g in net.generators)
    assert [w.code for w in report.warnings].count("RAW_NO_COSTS") == 1


def test_quirks_parallel_circuits(quirks):
    net, _ = quirks
    lines = {b.id: b for b in net.branches if b.kind == "line"}
    assert set(lines) == {"branch-1-2-1", "branch-1-2-2"}
    a, b = lines["branch-1-2-1"], lines["branch-1-2-2"]
    assert (a.r, a.x, a.b, a.rating_mva, a.tap_ratio, a.shift_deg) == (
        0.01,
        0.1,
        0.02,
        150.0,
        None,
        None,
    )
    assert (b.r, b.x, b.b, b.rating_mva) == (0.02, 0.2, 0.04, 100.0)


def test_quirks_transformer_cw2_cz2_cm2(quirks):
    net, _ = quirks
    t1 = next(b for b in net.branches if b.id == "branch-2-3-1")
    assert t1.kind == "transformer"
    assert (t1.from_bus, t1.to_bus) == ("bus-2", "bus-3")
    assert abs(t1.r - 0.01) <= TOL
    assert abs(t1.x - 0.16) <= TOL
    assert abs(t1.tap_ratio - 1.05) <= TOL
    assert t1.shift_deg is None
    assert (t1.b, t1.rating_mva, t1.in_service) == (0.0, 60.0, True)


def test_quirks_transformer_cw3_cz3(quirks):
    net, _ = quirks
    t2 = next(b for b in net.branches if b.id == "branch-3-4-1")
    assert t2.kind == "transformer"
    assert abs(t2.r - 0.001764) <= TOL
    assert abs(t2.x - 0.5291970599918333) <= TOL
    assert abs(t2.tap_ratio - 1.029) <= TOL
    assert t2.shift_deg == 5.0
    assert (t2.b, t2.rating_mva) == (0.0, 30.0)


def test_quirks_ignored_records_one_entry_each(quirks):
    _, report = quirks
    assert not report.errors
    owner = [w for w in report.warnings if w.code == "RAW_SECTION_IGNORED"]
    assert len(owner) == 1
    assert "owner" in owner[0].message and "1" in owner[0].message
    sw = [w for w in report.warnings if w.code == "RAW_SWITCHED_SHUNT_IGNORED"]
    assert len(sw) == 1
    assert sw[0].bus_ids == ["bus-4"]
    assert "BINIT" in sw[0].message


# --- AC-4 (c): three-winding transformers are ignored, one entry per record ---------------------

THREE_WINDING = """\
0, 100.00, 33, 0, 0, 60.00
three-winding test
-
1,'A', 138.0, 3, 1, 1, 1, 1.0, 0.0
2,'B', 138.0, 1, 1, 1, 1, 1.0, 0.0
3,'C', 13.8, 1, 1, 1, 1, 1.0, 0.0
4,'D', 13.8, 1, 1, 1, 1, 1.0, 0.0
0 / END OF BUS DATA
2,'1 ', 1, 1, 1, 10.0, 2.0, 0, 0, 0, 0, 1, 1, 0
0 / END OF LOAD DATA
0 / END OF FIXED SHUNT DATA
1,'1 ', 10.0, 0.0, 50.0, -50.0, 1.0, 0, 100.0, 0, 1, 0, 0, 1, 1, 100.0, 100.0, 0.0
0 / END OF GENERATOR DATA
1, 2, '1 ', 0.01, 0.1, 0.0, 0, 0, 0, 0, 0, 0, 0, 1, 1, 0
2, 3, '1 ', 0.01, 0.1, 0.0, 0, 0, 0, 0, 0, 0, 0, 1, 1, 0
3, 4, '1 ', 0.01, 0.1, 0.0, 0, 0, 0, 0, 0, 0, 0, 1, 1, 0
0 / END OF BRANCH DATA
2, 3, 4, '1 ', 1, 1, 1, 0.0, 0.0, 2, 'TW-A', 1, 1, 1.0, '    '
0.01, 0.1, 100.0, 0.01, 0.1, 100.0, 0.01, 0.1, 100.0, 1.0, 0.0
1.0, 0.0, 0.0, 0, 0, 0, 0, 0, 1.1, 0.9, 1.1, 0.9, 33, 0, 0, 0, 0
1.0, 0.0, 0.0, 0, 0, 0, 0, 0, 1.1, 0.9, 1.1, 0.9, 33, 0, 0, 0, 0
1.0, 0.0, 0.0, 0, 0, 0, 0, 0, 1.1, 0.9, 1.1, 0.9, 33, 0, 0, 0, 0
1, 2, 0, '2 ', 1, 1, 1, 0.0, 0.0, 2, 'TWO-W', 1, 1, 1.0, '    '
0.0, 0.2, 100.0
1.0, 0.0, 0.0, 0, 0, 0, 0, 0, 1.1, 0.9, 1.1, 0.9, 33, 0, 0, 0, 0
1.0, 0.0
2, 3, 4, '2 ', 1, 1, 1, 0.0, 0.0, 2, 'TW-B', 1, 1, 1.0, '    '
0.01, 0.1, 100.0, 0.01, 0.1, 100.0, 0.01, 0.1, 100.0, 1.0, 0.0
1.0, 0.0, 0.0, 0, 0, 0, 0, 0, 1.1, 0.9, 1.1, 0.9, 33, 0, 0, 0, 0
1.0, 0.0, 0.0, 0, 0, 0, 0, 0, 1.1, 0.9, 1.1, 0.9, 33, 0, 0, 0, 0
1.0, 0.0, 0.0, 0, 0, 0, 0, 0, 1.1, 0.9, 1.1, 0.9, 33, 0, 0, 0, 0
0 / END OF TRANSFORMER DATA
0 / END OF AREA DATA
0 / END OF TWO-TERMINAL DC DATA
0 / END OF VSC DC LINE DATA
0 / END OF IMPEDANCE CORRECTION DATA
0 / END OF MULTI-TERMINAL DC DATA
0 / END OF MULTI-SECTION LINE DATA
0 / END OF ZONE DATA
0 / END OF INTER-AREA TRANSFER DATA
0 / END OF OWNER DATA
0 / END OF FACTS DEVICE DATA
0 / END OF SWITCHED SHUNT DATA
0 / END OF GNE DATA
0 / END OF INDUCTION MACHINE DATA
Q
"""


def test_three_winding_records_are_ignored_one_entry_each():
    net, report = psse_raw.loads_with_report(THREE_WINDING)
    entries = [w for w in report.warnings if w.code == "RAW_THREE_WINDING_IGNORED"]
    assert len(entries) == 2
    assert entries[0].bus_ids == ["bus-2", "bus-3", "bus-4"]
    assert "TW-A" in entries[0].message or "2-3-4-1" in entries[0].message
    assert "2-3-4-2" in entries[1].message
    ids = {b.id for b in net.branches}
    assert ids == {"branch-1-2-1", "branch-2-3-1", "branch-3-4-1", "branch-1-2-2"}
    assert next(b for b in net.branches if b.id == "branch-1-2-2").kind == "transformer"
    assert next(b for b in net.branches if b.id == "branch-1-2-2").tap_ratio == 1.0


def test_codes_are_exposed_and_closed():
    assert set(psse_raw.CODES) == {
        "BASE_KV_REPLACED",
        "ISLAND_DEACTIVATED",
        "RAW_NO_COSTS",
        "RAW_LOAD_ZIP_FOLDED",
        "RAW_BRANCH_END_SHUNT_FOLDED",
        "RAW_XFMR_MAGNETISING_FOLDED",
        "RAW_THREE_WINDING_IGNORED",
        "RAW_SWITCHED_SHUNT_IGNORED",
        "RAW_SECTION_IGNORED",
    }


# --- islands follow io.matpower's convention ----------------------------------------------------


def test_island_is_deactivated_like_matpower():
    text = THREE_WINDING.replace(
        "3, 4, '1 ', 0.01, 0.1, 0.0, 0, 0, 0, 0, 0, 0, 0, 1, 1, 0",
        "3, 4, '1 ', 0.01, 0.1, 0.0, 0, 0, 0, 0, 0, 0, 0, 0, 1, 0",
    )
    net, report = psse_raw.loads_with_report(text)
    assert "ISLAND_DEACTIVATED" in report.codes
    assert next(b for b in net.buses if b.id == "bus-4").in_service is False


# --- file defects raise RawImportError ---------------------------------------------------------


def _replace_line(text: str, old: str, new: str) -> str:
    assert old in text
    return text.replace(old, new)


@pytest.mark.parametrize(
    ("mutate", "code"),
    [
        (lambda t: t.replace("0, 100.00, 33,", "0, 100.00, 32,", 1), "UNSUPPORTED_VERSION"),
        (lambda t: t.replace("0, 100.00, 33,", "0, abc, 33,", 1), "BAD_NUMBER"),
        (
            lambda t: t.replace("\n2,'1 ', 1, 1, 1, 10.0, 2.0", "\n2,'1 ', 1, 1, 1, x, 2.0"),
            "BAD_NUMBER",
        ),
        (
            lambda t: t.replace("\n1,'A', 138.0, 3, 1, 1, 1, 1.0, 0.0", "\n1,'A', 138.0, 3"),
            "BAD_RECORD",
        ),
        (lambda t: t.split("0 / END OF LOAD DATA")[0], "UNTERMINATED_SECTION"),
    ],
)
def test_defects_raise(mutate, code):
    with pytest.raises(RawImportError) as info:
        psse_raw.loads(mutate(THREE_WINDING))
    assert info.value.code == code
    assert code in str(info.value)


def test_missing_bus_reference_raises():
    text = THREE_WINDING.replace("2,'1 ', 1, 1, 1, 10.0, 2.0", "9,'1 ', 1, 1, 1, 10.0, 2.0")
    with pytest.raises(RawImportError) as info:
        psse_raw.loads(text)
    assert info.value.code == "UNKNOWN_BUS"
