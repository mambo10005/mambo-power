"""AC-6: ``Branch.kind`` — defaulted from the tap, explicit values preserved, lines cannot tap."""

import pytest

from mambo_power.io import native
from mambo_power.model import Branch, Bus, Network


def _branch(**kw: object) -> Branch:
    base: dict[str, object] = {
        "id": "br",
        "from_bus": "a",
        "to_bus": "b",
        "r": 0.0,
        "x": 0.1,
        "b": 0.0,
    }
    return Branch(**{**base, **kw})  # type: ignore[arg-type]


@pytest.mark.parametrize(
    "fields",
    [
        {},
        {"tap_ratio": None},
        {"tap_ratio": 1.0},
        {"shift_deg": 0.0},
        {"tap_ratio": 1.0, "shift_deg": 0.0},
    ],
)
def test_default_is_line_at_nominal_tap(fields: dict[str, object]) -> None:
    assert _branch(**fields).kind == "line"


@pytest.mark.parametrize(
    "fields",
    [
        {"tap_ratio": 1.025},
        {"tap_ratio": 0.98},
        {"shift_deg": -2.5},
        {"tap_ratio": 1.0, "shift_deg": 3.0},
    ],
)
def test_default_is_transformer_off_nominal(fields: dict[str, object]) -> None:
    assert _branch(**fields).kind == "transformer"


def test_explicit_transformer_at_nominal_tap_is_preserved() -> None:
    assert _branch(kind="transformer").kind == "transformer"
    assert _branch(kind="transformer", tap_ratio=1.0).kind == "transformer"


def test_explicit_transformer_at_nominal_tap_round_trips_through_native() -> None:
    net = Network(
        base_mva=100.0,
        buses=[Bus(id="a", base_kv=10.0, type="slack"), Bus(id="b", base_kv=10.0, type="pq")],
        branches=[_branch(kind="transformer")],
    )
    text = native.dumps(net)
    assert '"kind": "transformer"' in text
    back = native.loads(text)
    assert back == net
    assert back.branches[0].kind == "transformer"


def test_kind_is_in_model_dump() -> None:
    assert _branch().model_dump()["kind"] == "line"


@pytest.mark.parametrize("fields", [{"tap_ratio": 1.025}, {"shift_deg": 1.0}])
def test_explicit_line_with_tap_is_rejected(fields: dict[str, object]) -> None:
    with pytest.raises(ValueError, match="br"):
        _branch(kind="line", **fields)


def test_unknown_kind_is_rejected() -> None:
    with pytest.raises(ValueError):
        _branch(kind="cable")
