"""W5 / AC-6 (results part): typed result tables with provenance.

Construction, exact JSON round-trip, the positional ``to_arrays`` view in ``NetworkArrays``
order, rejection of ``inf``/``nan`` and unknown fields, and provenance stamping (version equals
``mambo_power.__version__``). The models are exercised directly and through ``solve_dc`` on a
small network so the builder (``results.from_arrays``) is covered end to end.
"""

from __future__ import annotations

import math
from datetime import UTC, datetime, timedelta, timezone

import numpy as np
import pytest
from pydantic import ValidationError

import mambo_power
from mambo_power.model import Branch, Bus, Generator, Load, Network
from mambo_power.numerics import NetworkArrays
from mambo_power.pf import solve_dc
from mambo_power.results import (
    AcPowerFlowResult,
    BranchResult,
    BusResult,
    DcPowerFlowResult,
    GenResult,
    PowerFlowArrays,
    ResultProvenance,
)


def provenance(**overrides: object) -> ResultProvenance:
    fields: dict[str, object] = {
        "engine": "mambo-power",
        "version": mambo_power.__version__,
        "kind": "pf.dc",
        "solver": "scipy.sparse.linalg.splu",
        "started_at": datetime(2026, 8, 20, 12, 30, 15, 123456, tzinfo=UTC),
        "elapsed_s": 0.00123,
        "options": {},
    }
    fields.update(overrides)
    return ResultProvenance.model_validate(fields)


def bus(id: str, **overrides: object) -> BusResult:
    fields: dict[str, object] = {
        "id": id,
        "vm_pu": 1.0,
        "va_deg": -1.5,
        "p_mw": 10.0,
        "q_mvar": 0.0,
        "role_effective": "pq",
        "in_service": True,
    }
    fields.update(overrides)
    return BusResult.model_validate(fields)


def branch(id: str, **overrides: object) -> BranchResult:
    fields: dict[str, object] = {
        "id": id,
        "from_bus": "bus-1",
        "to_bus": "bus-2",
        "p_from_mw": 12.5,
        "q_from_mvar": 0.0,
        "p_to_mw": -12.5,
        "q_to_mvar": 0.0,
        "loading_pct": None,
    }
    fields.update(overrides)
    return BranchResult.model_validate(fields)


def gen(id: str, **overrides: object) -> GenResult:
    fields: dict[str, object] = {
        "id": id,
        "bus": "bus-1",
        "p_mw": 5.0,
        "q_mvar": 0.0,
        "q_limited": "none",
    }
    fields.update(overrides)
    return GenResult.model_validate(fields)


def dc_result() -> DcPowerFlowResult:
    return DcPowerFlowResult(
        provenance=provenance(),
        converged=True,
        buses=[bus("bus-1", role_effective="slack", va_deg=0.0), bus("bus-2")],
        branches=[branch("br-12", loading_pct=12.5)],
        generators=[gen("gen-1")],
    )


def small_network() -> Network:
    return Network(
        base_mva=100.0,
        buses=[
            Bus(id="b1", base_kv=110.0, type="slack"),
            Bus(id="b2", base_kv=110.0, type="pv"),
            Bus(id="b3", base_kv=110.0, type="pq"),
            Bus(id="b4", base_kv=110.0, type="pq", in_service=False),
        ],
        branches=[
            Branch(id="l12", from_bus="b1", to_bus="b2", r=0.01, x=0.1, b=0.0, rating_mva=80.0),
            Branch(id="l23", from_bus="b2", to_bus="b3", r=0.01, x=0.1, b=0.0),
            Branch(id="l13", from_bus="b1", to_bus="b3", r=0.01, x=0.1, b=0.0),
            Branch(id="l34", from_bus="b3", to_bus="b4", r=0.01, x=0.1, b=0.0),
        ],
        generators=[
            Generator(
                id="g1",
                bus="b1",
                p_mw=0.0,
                q_mvar=0.0,
                p_min_mw=0.0,
                p_max_mw=200.0,
                q_min_mvar=-50.0,
                q_max_mvar=50.0,
                v_set_pu=1.0,
            ),
            Generator(
                id="g2",
                bus="b2",
                p_mw=30.0,
                q_mvar=0.0,
                p_min_mw=0.0,
                p_max_mw=100.0,
                q_min_mvar=-50.0,
                q_max_mvar=50.0,
                v_set_pu=1.0,
            ),
        ],
        loads=[Load(id="d3", bus="b3", p_mw=60.0, q_mvar=10.0)],
    )


# --- construction -----------------------------------------------------------------------------


def test_models_construct_with_every_field() -> None:
    result = dc_result()
    assert result.provenance.engine == "mambo-power"
    assert result.provenance.kind == "pf.dc"
    assert result.buses[0].role_effective == "slack"
    assert result.branches[0].loading_pct == 12.5
    assert result.generators[0].q_limited == "none"
    ac = AcPowerFlowResult(
        provenance=provenance(kind="pf.ac"),
        converged=True,
        buses=result.buses,
        branches=result.branches,
        generators=result.generators,
        iterations=4,
        max_mismatch_mva=1e-9,
        q_limit_rounds=0,
    )
    assert ac.iterations == 4


def test_unknown_fields_are_rejected() -> None:
    with pytest.raises(ValidationError):
        BusResult.model_validate({**bus("bus-1").model_dump(), "colour": "red"})
    with pytest.raises(ValidationError):
        ResultProvenance.model_validate({**provenance().model_dump(), "host": "x"})
    with pytest.raises(ValidationError):
        DcPowerFlowResult.model_validate({**dc_result().model_dump(), "iterations": 3})


@pytest.mark.parametrize("value", [math.inf, -math.inf, math.nan])
def test_inf_and_nan_are_rejected(value: float) -> None:
    with pytest.raises(ValidationError):
        bus("bus-1", vm_pu=value)
    with pytest.raises(ValidationError):
        branch("br", loading_pct=value)
    with pytest.raises(ValidationError):
        gen("g", p_mw=value)
    with pytest.raises(ValidationError):
        provenance(elapsed_s=value)


def test_provenance_rejects_foreign_engine_naive_timestamps_negative_elapsed() -> None:
    with pytest.raises(ValidationError):
        provenance(engine="pandapower")
    with pytest.raises(ValidationError):
        provenance(started_at=datetime(2026, 8, 20, 12, 30, 15))
    with pytest.raises(ValidationError):
        provenance(elapsed_s=-1.0)


def test_provenance_normalises_aware_timestamps_to_utc() -> None:
    plus_two = timezone(timedelta(hours=2))
    stamped = provenance(started_at=datetime(2026, 8, 20, 14, 30, 15, tzinfo=plus_two))
    assert stamped.started_at.utcoffset() == timedelta(0)
    assert stamped.started_at == datetime(2026, 8, 20, 12, 30, 15, tzinfo=UTC)


# --- JSON round-trip ---------------------------------------------------------------------------


def test_json_round_trip_is_exact() -> None:
    result = dc_result()
    text = result.model_dump_json()
    back = DcPowerFlowResult.model_validate_json(text)
    assert back == result
    assert back.model_dump_json() == text
    assert back.provenance.started_at == result.provenance.started_at
    assert back.provenance.started_at.tzinfo is not None


def test_json_round_trip_of_solved_network_is_exact() -> None:
    result = solve_dc(small_network())
    back = DcPowerFlowResult.model_validate_json(result.model_dump_json())
    assert back == result
    assert back.model_dump() == result.model_dump()


# --- to_arrays ----------------------------------------------------------------------------------


def test_to_arrays_follows_network_arrays_order() -> None:
    net = small_network()
    arr = NetworkArrays.from_network(net)
    result = solve_dc(net)
    view = result.to_arrays()
    assert isinstance(view, PowerFlowArrays)
    assert list(view.bus_ids) == arr.bus_ids == ["b1", "b2", "b3"]
    assert list(view.branch_ids) == arr.branch_ids == ["l12", "l23", "l13"]
    assert list(view.gen_ids) == arr.gen_ids == ["g1", "g2"]
    assert view.va_deg.shape == (3,)
    assert view.p_from_mw.shape == (3,)
    assert view.p_gen_mw.shape == (2,)
    np.testing.assert_array_equal(view.va_deg, [b.va_deg for b in result.buses])
    np.testing.assert_array_equal(view.p_from_mw, [b.p_from_mw for b in result.branches])
    np.testing.assert_array_equal(view.p_gen_mw, [g.p_mw for g in result.generators])
    # loading_pct: NaN stands in for None in the positional view
    assert not math.isnan(view.loading_pct[0])
    assert math.isnan(view.loading_pct[1]) and math.isnan(view.loading_pct[2])
    with pytest.raises(AttributeError):
        view.va_deg = view.va_deg  # type: ignore[misc]


def test_to_arrays_on_hand_built_ac_result() -> None:
    ac = AcPowerFlowResult(
        provenance=provenance(kind="pf.ac"),
        converged=True,
        buses=[bus("x", q_mvar=2.0), bus("y", q_mvar=-3.0)],
        branches=[branch("xy", q_from_mvar=1.0, q_to_mvar=-0.5)],
        generators=[gen("g", q_mvar=7.0)],
        iterations=3,
        max_mismatch_mva=1e-10,
        q_limit_rounds=1,
    )
    view = ac.to_arrays()
    np.testing.assert_array_equal(view.q_bus_mvar, [2.0, -3.0])
    np.testing.assert_array_equal(view.q_from_mvar, [1.0])
    np.testing.assert_array_equal(view.q_to_mvar, [-0.5])
    np.testing.assert_array_equal(view.q_gen_mvar, [7.0])


# --- provenance from the solver -------------------------------------------------------------------


def test_solver_stamps_provenance() -> None:
    before = datetime.now(UTC)
    result = solve_dc(small_network())
    after = datetime.now(UTC)
    prov = result.provenance
    assert prov.engine == "mambo-power"
    assert prov.version == mambo_power.__version__
    assert prov.kind == "pf.dc"
    assert prov.solver == "scipy.sparse.linalg.splu"
    assert before <= prov.started_at <= after
    assert prov.started_at.tzinfo is not None
    assert prov.elapsed_s > 0
    assert prov.options == {}
    assert result.converged is True


def test_results_are_not_attached_to_the_network() -> None:
    net = small_network()
    snapshot = net.model_dump()
    solve_dc(net)
    assert net.model_dump() == snapshot
    assert not hasattr(net, "results")
