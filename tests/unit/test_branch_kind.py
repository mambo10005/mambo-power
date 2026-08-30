"""AC-6: ``Branch.kind`` — defaulted from the tap, explicit ``transformer`` preserved, an explicit
``line`` with a tap promoted; a tap assigned after construction survives the native round trip
and is what exporters route on (M8 critic finding 3)."""

import json

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
def test_explicit_line_with_tap_is_promoted_to_transformer(fields: dict[str, object]) -> None:
    br = _branch(kind="line", **fields)
    assert br.kind == "transformer"
    assert br.is_transformer


def test_is_transformer_reads_the_fields_not_only_kind() -> None:
    br = _branch()
    assert br.kind == "line" and not br.is_transformer
    br.tap_ratio = 1.05
    assert br.kind == "line"  # assignment does not re-validate ...
    assert br.is_transformer  # ... but exporters see the tap
    assert _branch(kind="transformer").is_transformer  # neutral-tap transformer stays one


def _two_bus(branch: Branch) -> Network:
    return Network(
        base_mva=100.0,
        buses=[Bus(id="a", base_kv=10.0, type="slack"), Bus(id="b", base_kv=10.0, type="pq")],
        branches=[branch],
    )


@pytest.mark.parametrize("mutation", [{"tap_ratio": 1.05}, {"shift_deg": -3.0}])
def test_tap_assigned_after_construction_round_trips_through_native(
    mutation: dict[str, float],
) -> None:
    """Pre-M8 scripts set a tap on a line and save; the dump then says ``"kind": "line"`` beside
    the tap, and loading it must promote, not raise, and equal the network built fresh."""
    net = _two_bus(_branch())
    for field, value in mutation.items():
        setattr(net.branches[0], field, value)
    assert net.branches[0].kind == "line"
    text = native.dumps(net)
    # the file carries one truth (M8 critic nit 24): the dump writes the promoted kind
    assert json.loads(text)["branches"][0]["kind"] == "transformer"
    assert net.branches[0].kind == "line"  # serialising does not mutate the object
    back = native.loads(text)
    fresh = _two_bus(_branch(**mutation))
    assert fresh.branches[0].kind == "transformer"
    assert back == fresh


def test_unknown_kind_is_rejected() -> None:
    with pytest.raises(ValueError, match=r"kind\s+Input should be 'line' or 'transformer'"):
        _branch(kind="cable")
