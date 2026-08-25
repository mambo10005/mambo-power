"""W3 (model half): ``Period``/``Scenario.periods`` and ``Generator.ramp_up_mw``/``ramp_down_mw``.

Mirrors ``test_load_bid_scenario.py``'s discipline: construction, JSON round-trip, and the
dangling-reference / range invariants, each proved to actually fire rather than assumed.

``Period.load_p_mw`` is an id-keyed *override*, not a scale factor: a load id absent from the
dict falls back to that ``Load``'s own ``p_mw`` (solver-side behaviour, out of scope for this
slice -- nothing reads these fields yet, spec Design item 1 / Not Doing). ``Scenario.periods:
list[Period] | None = None`` -- ``None`` means single-period, and must leave ``market.nodal``'s
existing behaviour untouched (AC-4, discharged by a later slice); this file only proves the
domain model itself is sound.
"""

import pytest
from pydantic import ValidationError

from mambo_power.model import (
    Bus,
    Generator,
    Load,
    Network,
    NetworkValidationError,
    Period,
    Scenario,
)


def _slack() -> Bus:
    return Bus(id="b1", base_kv=110.0, type="slack")


def _network_with_load(*loads: Load) -> Network:
    return Network(base_mva=100.0, buses=[_slack()], loads=list(loads))


# --- Period: construction, JSON round-trip, value invariant --------------------------------


def test_period_construction() -> None:
    period = Period(load_p_mw={"d1": 12.5, "d2": 0.0})
    assert period.load_p_mw == {"d1": 12.5, "d2": 0.0}


def test_period_allows_empty_overrides() -> None:
    # An empty dict is a legitimate period: every load falls back to the network's own p_mw.
    period = Period(load_p_mw={})
    assert period.load_p_mw == {}


def test_period_json_roundtrip() -> None:
    period = Period(load_p_mw={"d1": 42.0})
    assert Period.model_validate_json(period.model_dump_json()) == period


def test_period_forbids_extra_fields() -> None:
    with pytest.raises(ValidationError):
        Period(load_p_mw={}, load_scale=1.5)  # type: ignore[call-arg]


def test_period_rejects_negative_load_p_mw() -> None:
    with pytest.raises(ValidationError):
        Period(load_p_mw={"d1": -1.0})


def test_period_accepts_zero_load_p_mw() -> None:
    # Zero is a legitimate override (the load is fully curtailed that period); only negative
    # values are rejected.
    period = Period(load_p_mw={"d1": 0.0})
    assert period.load_p_mw["d1"] == 0.0


# --- Scenario.periods: default, non-empty-if-present, JSON round-trip ----------------------


def test_scenario_periods_defaults_to_none() -> None:
    net = _network_with_load(Load(id="d1", bus="b1", p_mw=10.0, q_mvar=0.0))
    scenario = Scenario(network=net)
    assert scenario.periods is None


def test_scenario_with_periods_construction() -> None:
    net = _network_with_load(
        Load(id="d1", bus="b1", p_mw=10.0, q_mvar=0.0),
        Load(id="d2", bus="b1", p_mw=5.0, q_mvar=0.0),
    )
    periods = [Period(load_p_mw={"d1": 12.0}), Period(load_p_mw={"d1": 8.0, "d2": 3.0})]
    scenario = Scenario(network=net, periods=periods)
    assert scenario.periods == periods


def test_scenario_with_periods_json_roundtrip() -> None:
    net = _network_with_load(Load(id="d1", bus="b1", p_mw=10.0, q_mvar=0.0))
    scenario = Scenario(network=net, periods=[Period(load_p_mw={"d1": 11.0})])
    assert Scenario.model_validate_json(scenario.model_dump_json()) == scenario


def test_scenario_periods_empty_list_is_rejected() -> None:
    # "if present, the list must be non-empty" (wave spec Design item 1).
    net = _network_with_load(Load(id="d1", bus="b1", p_mw=10.0, q_mvar=0.0))
    with pytest.raises(ValidationError):
        Scenario(network=net, periods=[])


# --- Scenario.periods: dangling load-reference cross-check, proved to fire -----------------


def test_scenario_periods_dangling_load_ref_is_rejected() -> None:
    # Period alone cannot check this (it has no network); Scenario must, since it is the only
    # place that holds both the periods and the network at once.
    net = _network_with_load(Load(id="d1", bus="b1", p_mw=10.0, q_mvar=0.0))
    with pytest.raises(ValidationError) as excinfo:
        Scenario(network=net, periods=[Period(load_p_mw={"ghost": 5.0})])
    assert "ghost" in str(excinfo.value)


def test_scenario_periods_dangling_load_ref_via_json_is_rejected() -> None:
    bad_json = (
        '{"network": {"base_mva": 100.0, "buses": [{"id": "b1", "base_kv": 110.0, '
        '"type": "slack"}], "loads": [{"id": "d1", "bus": "b1", "p_mw": 10.0, "q_mvar": 0.0}]}, '
        '"periods": [{"load_p_mw": {"ghost": 5.0}}]}'
    )
    with pytest.raises(ValidationError):
        Scenario.model_validate_json(bad_json)


def test_scenario_periods_referencing_a_real_load_id_is_accepted() -> None:
    # Positive case, paired with the dangling-ref rejection above: the same load id, present
    # this time, must not be rejected.
    net = _network_with_load(Load(id="d1", bus="b1", p_mw=10.0, q_mvar=0.0))
    scenario = Scenario(network=net, periods=[Period(load_p_mw={"d1": 5.0})])
    assert scenario.periods is not None
    assert scenario.periods[0].load_p_mw == {"d1": 5.0}


def test_scenario_periods_partial_override_omits_some_loads() -> None:
    # A Period need not mention every load; the ones it omits fall back to the network's own
    # p_mw (solver-side behaviour, not checked here -- this only proves the shape is valid).
    net = _network_with_load(
        Load(id="d1", bus="b1", p_mw=10.0, q_mvar=0.0),
        Load(id="d2", bus="b1", p_mw=5.0, q_mvar=0.0),
    )
    scenario = Scenario(network=net, periods=[Period(load_p_mw={"d1": 12.0})])
    assert scenario.periods is not None
    assert "d2" not in scenario.periods[0].load_p_mw


def test_scenario_with_dangling_ref_network_still_rejected_with_periods_present() -> None:
    # Network's own nested validator still runs (and still raises its own error shape) even
    # when periods are also present -- the two checks are independent.
    bad_load = Load(id="d1", bus="ghost", p_mw=10.0, q_mvar=0.0)
    with pytest.raises((NetworkValidationError, ValidationError)):
        Scenario(
            network=Network(base_mva=100.0, buses=[_slack()], loads=[bad_load]),
            periods=[Period(load_p_mw={"d1": 1.0})],
        )


# --- Generator.ramp_up_mw / ramp_down_mw: default, JSON round-trip, range invariant --------


def _gen(**overrides: object) -> Generator:
    data: dict[str, object] = {
        "id": "g1",
        "bus": "b1",
        "p_mw": 10.0,
        "q_mvar": 0.0,
        "p_min_mw": 0.0,
        "p_max_mw": 100.0,
        "q_min_mvar": -50.0,
        "q_max_mvar": 50.0,
        "v_set_pu": 1.0,
    }
    data.update(overrides)
    return Generator(**data)  # type: ignore[arg-type]


def test_generator_ramp_defaults_to_none() -> None:
    gen = _gen()
    assert gen.ramp_up_mw is None
    assert gen.ramp_down_mw is None


def test_generator_ramp_positive_values_accepted() -> None:
    gen = _gen(ramp_up_mw=15.0, ramp_down_mw=20.0)
    assert gen.ramp_up_mw == 15.0
    assert gen.ramp_down_mw == 20.0


def test_generator_ramp_json_roundtrip() -> None:
    gen = _gen(ramp_up_mw=15.0, ramp_down_mw=20.0)
    assert Generator.model_validate_json(gen.model_dump_json()) == gen


def test_generator_without_ramp_roundtrip_via_native_omits_the_field() -> None:
    # Backward compatible: every M1-M4 fixture/test with a Generator and no ramp set is
    # unaffected. native.dumps uses exclude_none, same as every other optional field.
    from mambo_power.io import native

    net = Network(base_mva=100.0, buses=[_slack()], generators=[_gen()])
    text = native.dumps(net)
    assert '"ramp_up_mw"' not in text
    assert '"ramp_down_mw"' not in text
    assert native.loads(text) == net


# ramp_up_mw/ramp_down_mw = 0 / negative rejection (BAD_RANGE) is catalogued alongside every
# other range invariant in test_model_invariants.py's test_bad_range, not duplicated here.
