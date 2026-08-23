"""AC-4 / AC-5 fixtures under ``fixtures/matpower/derived/``: synthetic case14 variants.

Each derived file is case14 with a documented cell-level edit (``derived/PROVENANCE.md`` and
each file's header). Two things are checked here:

* the edit is exactly the documented one — the raw matrices of the derived file equal the raw
  matrices of case14 after applying the edit in numpy (``tests.parity._mpc_reader``, the
  independent reader), so nothing else drifted;
* the importer's behaviour on each file TODAY, which S2 (effective roles, island repair)
  built on. ``case14_island`` is the one whose expected behaviour S2 flipped — see that test.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from mambo_power.io import matpower, native
from mambo_power.model import Network, NetworkValidationError
from tests._fixtures import FIXTURES_DIR
from tests.parity._mpc_reader import read_mpc_numpy

DERIVED_DIR = FIXTURES_DIR / "derived"
BASE = FIXTURES_DIR / "case14.m"
DERIVED = ["case14_roles", "case14_island", "case14_noslackgen"]

# mpc column positions (0-based) used by the edits
GEN_PG, GEN_QG, GEN_VG, GEN_STATUS = 1, 2, 5, 7
BR_STATUS = 10


def _raw(path: Path) -> dict[str, np.ndarray]:
    return {k: v for k, v in read_mpc_numpy(path).items() if isinstance(v, np.ndarray)}


def _assert_same_matrices(ours: dict[str, np.ndarray], expected: dict[str, np.ndarray]) -> None:
    assert ours.keys() == expected.keys()
    for name in expected:
        np.testing.assert_array_equal(ours[name], expected[name], err_msg=name)


# --- derivation: verbatim except the documented cells -------------------------------------------


def test_roles_is_case14_plus_documented_edits() -> None:
    base = _raw(BASE)
    base["gen"][3, GEN_STATUS] = 0  # row 4, bus 6: its only generator out of service
    base["gen"][1, GEN_PG] = 20.0  # row 2, bus 2: PG 40 -> 20, QG 42.4 -> 21.2 ...
    base["gen"][1, GEN_QG] = 21.2
    second = base["gen"][1].copy()  # ... and a second bus-2 generator appended (row 6)
    second[GEN_VG] = 1.055  # VG 1.045 + 0.01
    base["gen"] = np.vstack([base["gen"], second])
    base["gencost"] = np.vstack([base["gencost"], base["gencost"][1]])
    _assert_same_matrices(_raw(DERIVED_DIR / "case14_roles.m"), base)


def test_island_is_case14_plus_documented_edits() -> None:
    base = _raw(BASE)
    base["branch"][13, BR_STATUS] = 0  # row 14, branch 7-8: the only bridge in case14
    _assert_same_matrices(_raw(DERIVED_DIR / "case14_island.m"), base)


def test_noslackgen_is_case14_plus_documented_edits() -> None:
    base = _raw(BASE)
    base["gen"][0, GEN_STATUS] = 0  # row 1, bus 1 (slack): its only generator out of service
    _assert_same_matrices(_raw(DERIVED_DIR / "case14_noslackgen.m"), base)


@pytest.mark.parametrize("name", DERIVED)
def test_header_names_base_and_purpose(name: str) -> None:
    head = (DERIVED_DIR / f"{name}.m").read_text(encoding="utf-8").split("mpc.version")[0]
    assert f"function mpc = {name}" in head
    assert "case14.m" in head and "SYNTHETIC" in head
    assert ("AC-4" in head) or ("AC-5" in head)


# --- importer behaviour today -------------------------------------------------------------------


def test_roles_loads_with_one_unit_less_pv_bus_and_one_two_gen_bus() -> None:
    net = matpower.load(DERIVED_DIR / "case14_roles.m")
    live = [g for g in net.generators if g.in_service]
    by_bus: dict[str, list[float]] = {}
    for g in live:
        by_bus.setdefault(g.bus, []).append(g.v_set_pu)
    pv_without_gen = [b.id for b in net.buses if b.type == "pv" and b.id not in by_bus]
    assert pv_without_gen == ["bus-6"]
    multi = {bus: vs for bus, vs in by_bus.items() if len(vs) > 1}
    assert multi == {"bus-2": [1.045, 1.055]}  # file order; differing setpoints
    slack = next(b for b in net.buses if b.type == "slack")
    assert slack.id == "bus-1" and slack.in_service and by_bus["bus-1"] == [1.06]
    assert len(net.generators) == 6 and len(live) == 5
    assert native.loads(native.dumps(net)) == net


def test_island_is_repaired_by_the_importer_and_rejected_by_the_model() -> None:
    # S2 (W4, design item 4): `load` / `load_with_warnings` repair the island (deactivate
    # bus-8 and gen-5, warn ISLAND_DEACTIVATED); only a direct `Network(...)` keeps raising
    # DISCONNECTED_BUS. The full behaviour is covered in tests/unit/test_islands.py.
    net, warnings = matpower.load_with_warnings(DERIVED_DIR / "case14_island.m")
    assert [b.in_service for b in net.buses if b.id == "bus-8"] == [False]
    assert [g.in_service for g in net.generators if g.id == "gen-5"] == [False]
    island = [w for w in warnings if w.startswith("ISLAND_DEACTIVATED:")]  # + 14 BASE_KV ones
    assert len(island) == 1 and "bus-8" in island[0] and "gen-5" in island[0]
    assert native.loads(native.dumps(net)) == net
    raw = net.model_dump()
    for bus in raw["buses"]:
        bus["in_service"] = True
    with pytest.raises(NetworkValidationError) as excinfo:
        Network.model_validate(raw)
    assert excinfo.value.codes == {"DISCONNECTED_BUS"}
    assert any("bus-8" in str(issue) for issue in excinfo.value.issues)


def test_noslackgen_loads_with_no_in_service_generator_on_the_slack() -> None:
    net = matpower.load(DERIVED_DIR / "case14_noslackgen.m")
    slack = [b for b in net.buses if b.type == "slack"]
    assert [b.id for b in slack] == ["bus-1"] and slack[0].in_service
    on_slack = [g for g in net.generators if g.bus == "bus-1"]
    assert len(on_slack) == 1 and not on_slack[0].in_service
    assert [g.id for g in net.generators if g.in_service and g.bus == "bus-1"] == []
    assert native.loads(native.dumps(net)) == net
