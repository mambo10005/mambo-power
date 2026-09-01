"""AC-3 (model half): ``Load.bid``/``LoadBid``/``Scenario`` construction and JSON round-trip.

``LoadBid`` mirrors ``GeneratorCost`` field-for-field (``PolynomialBid``/``PiecewiseBid``, same
``coefficients``/``points`` shape as ``PolynomialCost``/``PiecewiseCost``); the
convexity-*direction* check (non-increasing marginal value) is ``opf.dc_opf``'s job at solve
time (wave spec Design item 1), not model-construction's — this file only checks the same
structural validation costs already get (at least two points, strictly increasing ``p_mw``).

``Scenario`` embeds ``network: Network`` directly (mirrors ``SolveRequest``, research §6.2): no
id/path reference, no ``periods``/agent-strategy fields (design interview 2026-08-24, ratified).
"""

import pytest
from pydantic import ValidationError

from mambo_power.io import native
from mambo_power.model import (
    Bus,
    Load,
    Network,
    NetworkValidationError,
    PiecewiseBid,
    PolynomialBid,
    Scenario,
)


def _slack() -> Bus:
    return Bus(id="b1", base_kv=110.0, type="slack")


def _network_with_load(load: Load) -> Network:
    return Network(base_mva=100.0, buses=[_slack()], loads=[load])


# --- LoadBid: construction, JSON round-trip -------------------------------------------------


def test_polynomial_bid_construction() -> None:
    bid = PolynomialBid(coefficients=[-0.01, 40.0])
    assert bid.kind == "polynomial"
    assert bid.coefficients == [-0.01, 40.0]


def test_piecewise_bid_construction() -> None:
    bid = PiecewiseBid(points=[(0.0, 0.0), (50.0, 2250.0), (100.0, 3250.0)])
    assert bid.kind == "piecewise"
    assert len(bid.points) == 3


def test_polynomial_bid_json_roundtrip() -> None:
    bid = PolynomialBid(coefficients=[-0.02, 45.0, 0.0])
    assert PolynomialBid.model_validate_json(bid.model_dump_json()) == bid


def test_piecewise_bid_json_roundtrip() -> None:
    bid = PiecewiseBid(points=[(0.0, 0.0), (50.0, 2250.0), (100.0, 3250.0)])
    assert PiecewiseBid.model_validate_json(bid.model_dump_json()) == bid


def test_piecewise_bid_needs_at_least_two_points() -> None:
    # Structural checks on PiecewiseBid.points live in Network's validation pass, mirroring
    # exactly where the same checks live for PiecewiseCost.points (network.py, not entities.py).
    load = Load(id="d1", bus="b1", p_mw=10.0, q_mvar=0.0, bid=PiecewiseBid(points=[(0.0, 0.0)]))
    with pytest.raises(NetworkValidationError) as excinfo:
        _network_with_load(load)
    assert any(
        issue.code == "BAD_RANGE" and issue.path == "loads[0].bid.points"
        for issue in excinfo.value.issues
    )


def test_piecewise_bid_p_mw_must_be_strictly_increasing() -> None:
    # Structural check only (mirrors PiecewiseCost) — this is not the concavity/convexity
    # direction check, which is opf.dc_opf's job (NonConcaveBidError, S3).
    load = Load(
        id="d1",
        bus="b1",
        p_mw=10.0,
        q_mvar=0.0,
        bid=PiecewiseBid(points=[(0.0, 0.0), (10.0, 100.0), (10.0, 150.0)]),
    )
    with pytest.raises(NetworkValidationError) as excinfo:
        _network_with_load(load)
    assert any(
        issue.code == "BAD_RANGE" and issue.path == "loads[0].bid.points"
        for issue in excinfo.value.issues
    )


def test_load_bid_does_not_reject_a_non_concave_shape() -> None:
    # model-level validation deliberately does not check convexity direction (spec Design
    # item 1); a bid whose marginal value increases (non-concave) is still structurally valid
    # here and only rejected later, at solve time, by NonConcaveBidError (S3, out of scope).
    bid = PiecewiseBid(points=[(0.0, 0.0), (50.0, 100.0), (100.0, 500.0)])
    assert len(bid.points) == 3


# --- Load.bid: field, JSON round-trip, backward compatibility ------------------------------


def test_load_bid_defaults_to_none() -> None:
    load = Load(id="d1", bus="b1", p_mw=10.0, q_mvar=0.0)
    assert load.bid is None


def test_load_with_polynomial_bid_roundtrip() -> None:
    load = Load(
        id="d1", bus="b1", p_mw=10.0, q_mvar=0.0, bid=PolynomialBid(coefficients=[-0.01, 40.0])
    )
    assert Load.model_validate_json(load.model_dump_json()) == load
    assert load.bid is not None
    assert load.bid.kind == "polynomial"


def test_load_with_piecewise_bid_roundtrip() -> None:
    load = Load(
        id="d1",
        bus="b1",
        p_mw=10.0,
        q_mvar=0.0,
        bid=PiecewiseBid(points=[(0.0, 0.0), (10.0, 400.0)]),
    )
    assert Load.model_validate_json(load.model_dump_json()) == load


def test_load_without_bid_roundtrip_via_native_omits_the_field() -> None:
    # Backward compatible: every M1-M3 fixture/test with a Load and no .bid set is unaffected.
    # native.dumps (the native file format) uses exclude_none, same as every other optional
    # field (e.g. Generator.cost) — checked here the same way test_model_roundtrip.py checks it.
    net = _network_with_load(Load(id="d1", bus="b1", p_mw=10.0, q_mvar=0.0))
    text = native.dumps(net)
    assert '"bid"' not in text
    assert native.loads(text) == net


# --- Scenario: construction, JSON round-trip, embedded Network validation ------------------


def test_scenario_construction_with_valid_network() -> None:
    net = _network_with_load(Load(id="d1", bus="b1", p_mw=10.0, q_mvar=0.0))
    scenario = Scenario(network=net)
    assert scenario.network == net


def test_scenario_json_roundtrip() -> None:
    bid = PolynomialBid(coefficients=[-0.01, 40.0])
    net = _network_with_load(Load(id="d1", bus="b1", p_mw=10.0, q_mvar=0.0, bid=bid))
    scenario = Scenario(network=net)
    assert Scenario.model_validate_json(scenario.model_dump_json()) == scenario


def test_scenario_forbids_extra_fields() -> None:
    net = _network_with_load(Load(id="d1", bus="b1", p_mw=10.0, q_mvar=0.0))
    with pytest.raises(ValidationError):
        Scenario(network=net, periods=[])  # type: ignore[call-arg]


def test_scenario_with_dangling_ref_network_is_rejected_at_construction() -> None:
    # Network's own model_validator(mode="after") runs during Scenario construction, since
    # Network is a nested pydantic model field — no explicit Scenario-level check is needed.
    bad_load = Load(id="d1", bus="ghost", p_mw=10.0, q_mvar=0.0)
    with pytest.raises((NetworkValidationError, ValidationError)) as excinfo:
        Scenario(network=Network(base_mva=100.0, buses=[_slack()], loads=[bad_load]))
    # NetworkValidationError raised inside a nested-model validator surfaces as a
    # pydantic ValidationError wrapping it when constructed via Scenario(network=...); confirm
    # the DANGLING_REF code is reachable either way, rather than assuming the wrapping shape.
    err = excinfo.value
    if isinstance(err, NetworkValidationError):
        assert any(issue.code == "DANGLING_REF" for issue in err.issues)
    else:
        assert "DANGLING_REF" in str(err) or "loads" in str(err)


def test_scenario_with_dangling_ref_via_json_is_rejected() -> None:
    bad_json = (
        '{"network": {"base_mva": 100.0, "buses": [{"id": "b1", "base_kv": 110.0, '
        '"type": "slack"}], "loads": [{"id": "d1", "bus": "ghost", "p_mw": 10.0, '
        '"q_mvar": 0.0}]}}'
    )
    with pytest.raises((NetworkValidationError, ValidationError)):
        Scenario.model_validate_json(bad_json)


# --- Existing Load construction sites are unaffected by the new field ----------------------


def test_existing_load_construction_without_bid_still_works_in_a_network() -> None:
    net = _network_with_load(Load(id="d1", bus="b1", p_mw=70.0, q_mvar=20.0))
    assert net.loads[0].bid is None
