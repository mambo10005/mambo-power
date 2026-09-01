"""AC-5 (hand-written network): native JSON round-trip is identity and omits null fields."""

import json
from pathlib import Path
from typing import Any

from mambo_power.io import native
from mambo_power.model import (
    Branch,
    Bus,
    Generator,
    Geo,
    Load,
    Network,
    PiecewiseCost,
    PolynomialCost,
    Shunt,
    Storage,
    Zone,
)


def full_network() -> Network:
    return Network(
        base_mva=100.0,
        buses=[
            Bus(
                id="b1",
                base_kv=110.0,
                type="slack",
                vm_pu=1.02,
                va_deg=0.0,
                v_min_pu=0.9,
                v_max_pu=1.1,
                area="north",
                zone="z1",
                geo=Geo(lat=37.5, lon=127.0),
            ),
            Bus(id="b2", base_kv=110.0, type="pv", zone="z1"),
            Bus(id="b3", base_kv=20.0, type="pq"),
            Bus(id="b4", base_kv=20.0, type="pq", in_service=False),
        ],
        branches=[
            Branch(id="l12", from_bus="b1", to_bus="b2", r=0.01, x=0.1, b=0.02, rating_mva=250.0),
            Branch(
                id="t23",
                from_bus="b2",
                to_bus="b3",
                r=0.0,
                x=0.05,
                b=0.0,
                tap_ratio=1.025,
                shift_deg=-2.5,
            ),
            Branch(id="l34", from_bus="b3", to_bus="b4", r=0.02, x=0.2, b=0.0, in_service=False),
        ],
        generators=[
            Generator(
                id="g1",
                bus="b1",
                p_mw=50.0,
                q_mvar=5.0,
                p_min_mw=0.0,
                p_max_mw=200.0,
                q_min_mvar=-100.0,
                q_max_mvar=100.0,
                v_set_pu=1.02,
                cost=PolynomialCost(coefficients=[0.01, 20.0, 100.0], startup=500.0),
            ),
            Generator(
                id="g2",
                bus="b2",
                p_mw=30.0,
                q_mvar=0.0,
                p_min_mw=0.0,
                p_max_mw=80.0,
                q_min_mvar=-40.0,
                q_max_mvar=40.0,
                v_set_pu=1.0,
                cost=PiecewiseCost(
                    points=[(0.0, 0.0), (40.0, 1000.0), (80.0, 2500.0)], shutdown=50.0
                ),
            ),
            Generator(
                id="g3",
                bus="b2",
                p_mw=0.0,
                q_mvar=0.0,
                p_min_mw=0.0,
                p_max_mw=10.0,
                q_min_mvar=0.0,
                q_max_mvar=0.0,
                v_set_pu=1.0,
                in_service=False,
            ),
        ],
        loads=[Load(id="d3", bus="b3", p_mw=70.0, q_mvar=20.0)],
        shunts=[Shunt(id="s3", bus="b3", g_mw=0.0, b_mvar=15.0)],
        storage=[
            Storage(
                id="e2",
                bus="b2",
                p_max_mw=10.0,
                energy_mwh=40.0,
                soc_initial=0.5,
                efficiency_charge=0.95,
                efficiency_discharge=0.9,
            )
        ],
        zones=[Zone(id="z1", name="Zone 1"), Zone(id="z2")],
    )


def _walk_for_none(value: Any, path: str, found: list[str]) -> None:
    if value is None:
        found.append(path)
    elif isinstance(value, dict):
        for key, item in value.items():
            _walk_for_none(item, f"{path}.{key}", found)
    elif isinstance(value, list):
        for index, item in enumerate(value):
            _walk_for_none(item, f"{path}[{index}]", found)


def test_dumps_loads_is_identity() -> None:
    net = full_network()
    assert native.loads(native.dumps(net)) == net


def test_model_validate_json_of_model_dump_json_is_identity() -> None:
    # AC-5 wording, verbatim.
    net = full_network()
    assert Network.model_validate_json(net.model_dump_json()) == net


def test_dumps_has_no_null_fields() -> None:
    text = native.dumps(full_network())
    found: list[str] = []
    _walk_for_none(json.loads(text), "$", found)
    assert found == []


def test_dumps_is_indented_json() -> None:
    text = native.dumps(full_network())
    assert text.startswith("{\n  ")


def test_save_load_is_identity(tmp_path: Path) -> None:
    net = full_network()
    target = tmp_path / "net.json"
    native.save(net, target)
    assert native.load(target) == net
    assert native.load(str(target)) == net
