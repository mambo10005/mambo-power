"""AC-5 on the five MATPOWER fixtures: native JSON round-trip is identity."""

from pathlib import Path

import pytest

from mambo_power.io import matpower, native
from mambo_power.model import Network

FIXTURES_DIR = Path(__file__).resolve().parents[2] / "fixtures" / "matpower"
FIXTURES = ["case14", "case30", "case_ieee30", "case57", "case118"]


@pytest.mark.parametrize("name", FIXTURES)
def test_loads_dumps_is_identity(name: str) -> None:
    net = matpower.load(FIXTURES_DIR / f"{name}.m")
    assert native.loads(native.dumps(net)) == net


@pytest.mark.parametrize("name", FIXTURES)
def test_model_validate_json_of_model_dump_json_is_identity(name: str) -> None:
    # AC-5 wording, verbatim.
    net = matpower.load(FIXTURES_DIR / f"{name}.m")
    assert Network.model_validate_json(net.model_dump_json()) == net


@pytest.mark.parametrize("name", FIXTURES)
def test_save_load_is_identity(name: str, tmp_path: Path) -> None:
    net = matpower.load(FIXTURES_DIR / f"{name}.m")
    target = tmp_path / f"{name}.json"
    native.save(net, target)
    assert native.load(target) == net


def test_case14_stored_solution_is_preserved_on_buses() -> None:
    """VM/VA columns of mpc.bus are the M2 reference solution (W1 extract §3.1)."""
    net = matpower.load(FIXTURES_DIR / "case14.m")
    by_id = {bus.id: bus for bus in net.buses}
    # spot-checked against the raw file, rows 1, 2, 9, 14
    assert (by_id["bus-1"].vm_pu, by_id["bus-1"].va_deg) == (1.06, 0.0)
    assert (by_id["bus-2"].vm_pu, by_id["bus-2"].va_deg) == (1.045, -4.98)
    assert (by_id["bus-9"].vm_pu, by_id["bus-9"].va_deg) == (1.056, -14.94)
    assert (by_id["bus-14"].vm_pu, by_id["bus-14"].va_deg) == (1.036, -16.04)
    assert all(bus.vm_pu is not None and bus.va_deg is not None for bus in net.buses)
