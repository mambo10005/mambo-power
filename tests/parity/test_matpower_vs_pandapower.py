"""AC-6: the MATPOWER importer agrees with pandapower on the five IEEE fixtures.

Oracle path. pandapower 3.3.0's ``converter.from_mpc`` parses ``.m`` files through the
optional package ``matpowercaseframes``, which is not in this environment (dev deps are
locked). ``from_mpc`` is ``_m2ppc`` (read the matrices) followed by pandapower's own
``_adjust_ppc_indices``, ``_change_ppc_TAP_value`` and ``converter.pypower.from_ppc``. This
module replaces only the first step with an independent read of the same bytes —
``numpy.loadtxt`` over regex-extracted ``mpc.<name> = [ ... ];`` blocks — and runs the rest of
the pandapower pipeline unchanged. The comparison then has two layers:

* layer A — raw MATPOWER columns (bus, gen, branch, gencost) from the numpy read versus the
  values our :class:`Network` carries, within ``TOL``; this is the exhaustive per-column check;
* layer B — the pandapower element tables produced by ``from_ppc`` (bus, load, sgen, shunt,
  ext_grid, gen, line, trafo, impedance, poly_cost) versus our network after unit alignment,
  reconciled row-by-row through ``net._from_ppc_lookups``; values pandapower does not keep
  (BR_STATUS of transformers, PG/QG of the slack generator, base_kv = 0 lines) are counted
  as skipped and reported, never silently passed.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any

import numpy as np
import pytest

from mambo_power.io import matpower
from mambo_power.model import Network, PolynomialCost
from tests._fixtures import FIXTURES, FIXTURES_DIR
from tests.parity._mpc_reader import read_mpc_numpy

TOL = 1e-9
F_HZ = 60.0
PP_MAX_VAL = 99999.0  # pandapower from_ppc sentinel for "no rating"
BUS_TYPE = {3: "slack", 2: "pv", 1: "pq", 4: "pq"}


# --- the pandapower half of from_mpc (the .m read is tests/parity/_mpc_reader.py) -----------------


def pandapower_from_raw(raw: dict[str, Any]) -> Any:
    """Run the pandapower half of ``from_mpc`` on a copy of the raw matrices."""
    from pandapower.converter.matpower.from_mpc import (
        _adjust_ppc_indices,
        _change_ppc_TAP_value,
    )
    from pandapower.converter.pypower.from_ppc import _branch_to_which, from_ppc

    ppc = {k: (v.copy() if isinstance(v, np.ndarray) else v) for k, v in raw.items()}
    _adjust_ppc_indices(ppc)
    _change_ppc_TAP_value(ppc)
    # pandapower 3.3.0 defect (from_ppc.py:303): for branches it classifies as "impedance"
    # (TAP in {0, 1} between different base_kv) with RATE_A == 0 it writes the MAX_VAL
    # sentinel into the *trafo* array and raises IndexError. Apply its evident intent —
    # RATE_A 0 -> 99999 on exactly those rows — to the oracle's copy only.
    _, _, is_impedance, _ = _branch_to_which(ppc)
    rate_a = ppc["branch"][:, 5]
    ppc["branch"][is_impedance & (rate_a == 0), 5] = PP_MAX_VAL
    return from_ppc(ppc, f_hz=F_HZ)


@dataclass
class Case:
    name: str
    raw: dict[str, Any]
    pp: Any
    net: Network
    warnings: list[str]


@dataclass
class Report:
    """Max abs diff per column group plus what could not be compared (and why)."""

    diffs: dict[str, float] = field(default_factory=dict)
    skipped: dict[str, int] = field(default_factory=dict)

    def add(self, group: str, ours: float, theirs: float) -> None:
        self.diffs[group] = max(self.diffs.get(group, 0.0), abs(ours - theirs))

    def skip(self, reason: str) -> None:
        self.skipped[reason] = self.skipped.get(reason, 0) + 1

    @property
    def worst(self) -> float:
        return max(self.diffs.values(), default=0.0)


@pytest.fixture(scope="module", params=FIXTURES)
def case(request: pytest.FixtureRequest) -> Case:
    path = FIXTURES_DIR / f"{request.param}.m"
    raw = read_mpc_numpy(path)
    net, warnings = matpower.load_with_warnings(path)
    return Case(request.param, raw, pandapower_from_raw(raw), net, warnings)


def _label(value: float) -> str:
    return str(int(value))


# --- layer A: raw MATPOWER columns --------------------------------------------------------------


def compare_raw(case: Case) -> Report:
    rep = Report()
    raw, net = case.raw, case.net
    assert net.base_mva == raw["baseMVA"]

    bus_rows = raw["bus"]
    assert len(net.buses) == bus_rows.shape[0]
    loads = {ld.bus: ld for ld in net.loads}
    shunts = {s.bus: s for s in net.shunts}
    seen_loads = seen_shunts = 0
    for bus, row in zip(net.buses, bus_rows, strict=True):
        assert bus.id == f"bus-{_label(row[0])}"
        assert bus.type == BUS_TYPE[int(row[1])]
        assert bus.in_service is (int(row[1]) != 4)
        if row[2] != 0 or row[3] != 0:
            seen_loads += 1
            rep.add("bus.PD", loads[bus.id].p_mw, row[2])
            rep.add("bus.QD", loads[bus.id].q_mvar, row[3])
        else:
            assert bus.id not in loads
        if row[4] != 0 or row[5] != 0:
            seen_shunts += 1
            rep.add("bus.GS", shunts[bus.id].g_mw, row[4])
            rep.add("bus.BS", shunts[bus.id].b_mvar, row[5])
        else:
            assert bus.id not in shunts
        assert bus.area == _label(row[6])
        assert bus.vm_pu is not None and bus.va_deg is not None
        rep.add("bus.VM", bus.vm_pu, row[7])
        rep.add("bus.VA", bus.va_deg, row[8])
        if row[9] > 0:
            rep.add("bus.BASE_KV", bus.base_kv, row[9])
        else:
            assert bus.base_kv == 1.0
            assert any(bus.id in w for w in case.warnings)
            rep.skip("bus.BASE_KV<=0 replaced by 1.0 (warned)")
        assert bus.zone == _label(row[10])
        assert bus.v_max_pu is not None and bus.v_min_pu is not None
        rep.add("bus.VMAX", bus.v_max_pu, row[11])
        rep.add("bus.VMIN", bus.v_min_pu, row[12])
    assert seen_loads == len(net.loads)
    assert seen_shunts == len(net.shunts)
    assert [z.id for z in net.zones] == list(dict.fromkeys(_label(v) for v in bus_rows[:, 10]))

    gen_rows = raw["gen"]
    assert len(net.generators) == gen_rows.shape[0]
    for k, (gen, row) in enumerate(zip(net.generators, gen_rows, strict=True), start=1):
        assert gen.id == f"gen-{k}"
        assert gen.bus == f"bus-{_label(row[0])}"
        rep.add("gen.PG", gen.p_mw, row[1])
        rep.add("gen.QG", gen.q_mvar, row[2])
        rep.add("gen.QMAX", gen.q_max_mvar, row[3])
        rep.add("gen.QMIN", gen.q_min_mvar, row[4])
        rep.add("gen.VG", gen.v_set_pu, row[5])
        assert gen.in_service is bool(row[7] > 0)
        rep.add("gen.PMAX", gen.p_max_mw, row[8])
        rep.add("gen.PMIN", gen.p_min_mw, row[9])

    br_rows = raw["branch"]
    assert len(net.branches) == br_rows.shape[0]
    for k, (br, row) in enumerate(zip(net.branches, br_rows, strict=True), start=1):
        assert br.id == f"branch-{k}"
        assert br.from_bus == f"bus-{_label(row[0])}"
        assert br.to_bus == f"bus-{_label(row[1])}"
        rep.add("branch.BR_R", br.r, row[2])
        rep.add("branch.BR_X", br.x, row[3])
        rep.add("branch.BR_B", br.b, row[4])
        if row[5] > 0:
            assert br.rating_mva is not None
            rep.add("branch.RATE_A", br.rating_mva, row[5])
        else:
            assert br.rating_mva is None
        if row[8] != 0:
            assert br.tap_ratio is not None
            rep.add("branch.TAP", br.tap_ratio, row[8])
        else:
            assert br.tap_ratio is None
        if row[9] != 0:
            assert br.shift_deg is not None
            rep.add("branch.SHIFT", br.shift_deg, row[9])
        else:
            assert br.shift_deg is None
        assert br.in_service is bool(row[10] > 0)

    if "gencost" not in raw:
        assert all(g.cost is None for g in net.generators)
        return rep
    gc_rows = raw["gencost"]
    assert gc_rows.shape[0] in (gen_rows.shape[0], 2 * gen_rows.shape[0])
    for gen, row in zip(net.generators, gc_rows, strict=False):
        assert gen.cost is not None
        rep.add("gencost.STARTUP", gen.cost.startup, row[1])
        rep.add("gencost.SHUTDOWN", gen.cost.shutdown, row[2])
        ncost = int(row[3])
        if int(row[0]) == 2:
            assert isinstance(gen.cost, PolynomialCost)
            assert len(gen.cost.coefficients) == ncost
            for ours, theirs in zip(gen.cost.coefficients, row[4 : 4 + ncost], strict=True):
                rep.add("gencost.COST(poly)", ours, theirs)
        else:
            assert gen.cost.kind == "piecewise"
            assert len(gen.cost.points) == ncost
            flat = [v for point in gen.cost.points for v in point]
            for ours, theirs in zip(flat, row[4 : 4 + 2 * ncost], strict=True):
                rep.add("gencost.COST(pwl)", ours, theirs)
    return rep


# --- layer B: pandapower tables after unit alignment -------------------------------------------


def _pp_bus(case: Case, bus_id: str) -> int:
    """pandapower bus index for one of our bus ids (``_adjust_ppc_indices`` → BUS_I - 1)."""
    return int(bus_id.removeprefix("bus-")) - 1


def gen_split(case: Case) -> dict[str, int]:
    lookup = case.pp._from_ppc_lookups["gen"]
    return {et: int((lookup.element_type == et).sum()) for et in ("ext_grid", "gen", "sgen")}


def branch_split(case: Case) -> dict[str, int]:
    lookup = case.pp._from_ppc_lookups["branch"]
    return {et: int((lookup.element_type == et).sum()) for et in ("line", "trafo", "impedance")}


def compare_pandapower(case: Case) -> Report:
    rep = Report()
    pp, net, base = case.pp, case.net, case.net.base_mva
    omega = math.pi * F_HZ

    # buses
    assert len(pp.bus) == len(net.buses)
    for bus in net.buses:
        row = pp.bus.loc[_pp_bus(case, bus.id)]
        assert bool(row.in_service) is bus.in_service
        assert _label(float(row.zone)) == bus.zone
        assert bus.v_max_pu is not None and bus.v_min_pu is not None
        rep.add("pp.bus.max_vm_pu", bus.v_max_pu, row.max_vm_pu)
        rep.add("pp.bus.min_vm_pu", bus.v_min_pu, row.min_vm_pu)
        if row.vn_kv > 0:
            rep.add("pp.bus.vn_kv", bus.base_kv, row.vn_kv)
        else:
            rep.skip("pp.bus.vn_kv==0 (we substitute 1.0)")

    # loads: pandapower makes a load for PD>0 or (PD==0, QD!=0) and an sgen for PD<0
    gen_lookup = case.pp._from_ppc_lookups["gen"]
    gen_sgens = set(gen_lookup.element[gen_lookup.element_type == "sgen"].astype(int))
    bus_sgens = pp.sgen.drop(index=list(gen_sgens))
    assert len(net.loads) == len(pp.load) + len(bus_sgens)
    ours = {ld.bus: ld for ld in net.loads}
    for row in pp.load.itertuples():
        ld = ours[f"bus-{int(row.bus) + 1}"]
        rep.add("pp.load.p_mw", ld.p_mw, row.p_mw)
        rep.add("pp.load.q_mvar", ld.q_mvar, row.q_mvar)
    for row in bus_sgens.itertuples():
        ld = ours[f"bus-{int(row.bus) + 1}"]
        rep.add("pp.load.p_mw", ld.p_mw, -row.p_mw)
        rep.add("pp.load.q_mvar", ld.q_mvar, -row.q_mvar)

    # shunts: pandapower q_mvar = -BS (consumption-positive), p_mw = GS
    assert len(pp.shunt) == len(net.shunts)
    shunts = {s.bus: s for s in net.shunts}
    for row in pp.shunt.itertuples():
        s = shunts[f"bus-{int(row.bus) + 1}"]
        rep.add("pp.shunt.p_mw", s.g_mw, row.p_mw)
        rep.add("pp.shunt.q_mvar", s.b_mvar, -row.q_mvar)

    # generators: row k of mpc.gen -> ext_grid (first gen at a type-3 bus), gen (first gen at a
    # type-2 bus) or sgen (every other gen); pandapower gives every gen at a bus the VG of the
    # FIRST gen at that bus, so v_set_pu is compared only for first-at-bus rows.
    assert len(gen_lookup) == len(net.generators)
    first_at_bus: set[str] = set()
    for k, gen in enumerate(net.generators):
        et, el = gen_lookup.element_type.iloc[k], int(gen_lookup.element.iloc[k])
        is_first = gen.bus not in first_at_bus
        first_at_bus.add(gen.bus)
        table = getattr(pp, et)
        row = table.loc[el]
        assert int(row.bus) == _pp_bus(case, gen.bus)
        assert bool(row.in_service) is gen.in_service
        rep.add("pp.gen.max_p_mw", gen.p_max_mw, row.max_p_mw)
        rep.add("pp.gen.min_p_mw", gen.p_min_mw, row.min_p_mw)
        rep.add("pp.gen.max_q_mvar", gen.q_max_mvar, row.max_q_mvar)
        rep.add("pp.gen.min_q_mvar", gen.q_min_mvar, row.min_q_mvar)
        if et == "ext_grid":
            bus = next(b for b in net.buses if b.id == gen.bus)
            assert bus.va_deg is not None
            rep.add("pp.ext_grid.va_degree", bus.va_deg, row.va_degree)
            rep.skip("pp.ext_grid drops PG/QG")
        else:
            rep.add("pp.gen.p_mw", gen.p_mw, row.p_mw)
        if et == "sgen":
            rep.add("pp.sgen.q_mvar", gen.q_mvar, row.q_mvar)
        elif is_first:
            rep.add("pp.gen.vm_pu", gen.v_set_pu, row.vm_pu)
        else:
            rep.skip("pp.gen.vm_pu taken from first gen at bus")

    # branches
    br_lookup = case.pp._from_ppc_lookups["branch"]
    assert len(br_lookup) == len(net.branches)
    assert len(pp.line) + len(pp.trafo) + len(pp.impedance) == len(net.branches)
    for k, br in enumerate(net.branches):
        et, el = br_lookup.element_type.iloc[k], int(br_lookup.element.iloc[k])
        f, t = _pp_bus(case, br.from_bus), _pp_bus(case, br.to_bus)
        tap = br.tap_ratio if br.tap_ratio is not None else 1.0
        shift = br.shift_deg if br.shift_deg is not None else 0.0
        if et == "line":
            row = pp.line.loc[el]
            assert (int(row.from_bus), int(row.to_bus)) == (f, t)
            assert bool(row.in_service) is br.in_service
            assert tap == 1.0 and shift == 0.0
            vn = float(pp.bus.loc[t].vn_kv)
            zni = vn**2 / base
            if zni > 0:
                rep.add("pp.line.r", br.r, row.r_ohm_per_km / zni)
                rep.add("pp.line.x", br.x, row.x_ohm_per_km / zni)
                rep.add("pp.line.b", br.b, row.c_nf_per_km * 2 * omega * zni / 1e9)
                if br.rating_mva is None:
                    assert row.max_i_ka == PP_MAX_VAL
                else:
                    rep.add("pp.line.rating", br.rating_mva, row.max_i_ka * vn * math.sqrt(3))
            else:
                rep.skip("pp.line at vn_kv==0 bus (ohm values degenerate)")
        elif et == "trafo":
            row = pp.trafo.loc[el]
            assert {int(row.hv_bus), int(row.lv_bus)} == {f, t}
            sn = float(row.sn_mva)
            if br.rating_mva is None:
                assert sn == PP_MAX_VAL
            else:
                rep.add("pp.trafo.rating", br.rating_mva, sn)
            rk = row.vkr_percent * base / (100 * sn)
            zk = abs(row.vk_percent) * base / (100 * sn)
            xk = math.copysign(math.sqrt(max(zk**2 - rk**2, 0.0)), row.vk_percent)
            rep.add("pp.trafo.r", br.r, rk)
            rep.add("pp.trafo.x", br.x, xk)
            rep.add("pp.trafo.|b|", abs(br.b), row.i0_percent * sn / (100 * base))
            rep.add("pp.trafo.tap", tap, 1.0 + row.tap_pos * row.tap_step_percent / 100)
            rep.add("pp.trafo.shift", shift, row.shift_degree)
            rep.skip("pp.trafo drops BR_STATUS")
        else:
            row = pp.impedance.loc[el]
            assert (int(row.from_bus), int(row.to_bus)) == (f, t)
            sn = float(row.sn_mva)
            if br.rating_mva is None:
                assert sn == PP_MAX_VAL
                rep.skip("pp.impedance RATE_A==0 -> sentinel (oracle defect workaround)")
            else:
                rep.add("pp.impedance.rating", br.rating_mva, sn)
            rep.add("pp.impedance.r", br.r, row.rft_pu * base / sn)
            rep.add("pp.impedance.x", br.x, row.xft_pu * base / sn)
            rep.add("pp.impedance.b", br.b, row.bf_pu * 2 * sn / base)
            rep.skip("pp.impedance drops BR_STATUS")

    # gencost: pandapower poly_cost keeps c0..c2 per (et, element)
    poly = {(r.et, int(r.element)): r for r in pp.poly_cost.itertuples()}
    ours_poly = [
        (k, g.cost) for k, g in enumerate(net.generators) if isinstance(g.cost, PolynomialCost)
    ]
    assert len(poly) == len(ours_poly)
    assert len(pp.pwl_cost) == sum(
        1 for g in net.generators if g.cost is not None and g.cost.kind == "piecewise"
    )
    for k, cost in ours_poly:
        et, el = gen_lookup.element_type.iloc[k], int(gen_lookup.element.iloc[k])
        row = poly[(et, el)]
        padded = [0.0] * (3 - len(cost.coefficients)) + cost.coefficients  # [c2, c1, c0]
        rep.add("pp.poly_cost.cp2", padded[0], row.cp2_eur_per_mw2)
        rep.add("pp.poly_cost.cp1", padded[1], row.cp1_eur_per_mw)
        rep.add("pp.poly_cost.cp0", padded[2], row.cp0_eur)
    return rep


# --- tests ------------------------------------------------------------------------------------


def test_counts_match_pandapower(case: Case) -> None:
    pp, net = case.pp, case.net
    assert len(net.buses) == len(pp.bus)
    assert len(net.branches) == len(pp.line) + len(pp.trafo) + len(pp.impedance)
    assert len(net.generators) == sum(gen_split(case).values())
    assert len(net.shunts) == len(pp.shunt)
    assert len(net.loads) == len(pp.load) + len(pp.sgen) - gen_split(case)["sgen"]


def test_bus_types_and_service(case: Case) -> None:
    types = case.raw["bus"][:, 1].astype(int)
    assert [b.type for b in case.net.buses] == [BUS_TYPE[t] for t in types]
    assert [b.in_service for b in case.net.buses] == [t != 4 for t in types]
    assert sum(b.type == "slack" for b in case.net.buses) == 1
    assert gen_split(case)["ext_grid"] == 1


def test_raw_columns_within_tolerance(case: Case) -> None:
    rep = compare_raw(case)
    assert rep.worst <= TOL, rep.diffs
    assert {"bus.VM", "bus.VA", "gen.PG", "branch.BR_X", "gencost.COST(poly)"} <= rep.diffs.keys()


def test_pandapower_aligned_values_within_tolerance(case: Case) -> None:
    rep = compare_pandapower(case)
    assert rep.worst <= TOL, rep.diffs
    assert {"pp.load.p_mw", "pp.gen.max_p_mw", "pp.poly_cost.cp1"} <= rep.diffs.keys()


def test_generator_reconciliation_is_explicit(case: Case) -> None:
    """Every mpc.gen row lands in exactly one pandapower table and the slack gen is ext_grid."""
    lookup = case.pp._from_ppc_lookups["gen"]
    assert set(lookup.element_type) <= {"ext_grid", "gen", "sgen"}
    slack = next(b.id for b in case.net.buses if b.type == "slack")
    first_slack_gen = next(k for k, g in enumerate(case.net.generators) if g.bus == slack)
    assert lookup.element_type.iloc[first_slack_gen] == "ext_grid"


def test_importer_warnings_only_for_known_causes(case: Case) -> None:
    zero_kv = int((case.raw["bus"][:, 9] <= 0).sum())
    assert len(case.warnings) == zero_kv
    assert all("base_kv" in w or "BASE_KV" in w for w in case.warnings)
