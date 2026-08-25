"""W6/W7 / AC-6/AC-8: the stateless ``jobs`` surface — ``SolveRequest`` → ``run`` → ``SolveResult``.

Wave M4 W5/AC-7 extends this file (rather than duplicating it) for ``market.nodal``: a fifth
kind, whose runner takes the same ``(Network, options)`` shape as every other kind but wraps the
``Network`` into a ``Scenario`` itself (``Scenario`` is genuinely just ``network: Network`` this
wave, per ``model/scenario.py`` — no widening of ``SolveRequest``/``ResultModel``'s *request*
side is needed, only ``SolveResult.result``'s union, same mechanical step every prior kind took);
and a shared non-Optimal-status-translation helper both ``opf.dc`` and ``market.nodal``'s runners
call (wave spec Design item 6), proved genuinely shared, not duplicated.

Contract under test (wave M2 design item 6, wave M3 design item 7, wave M4 design item 6; ADR-004):

* ``KINDS`` lists exactly ``pf.ac``, ``pf.dc``, ``opf.dc``, ``n1``, ``market.nodal``; every
  spec's models are importable pydantic models and its runner is callable;
* ``run`` is pure: two calls on the same request give equal results modulo provenance timing;
* requests and results round-trip through JSON (``run_json`` is JSON in, JSON out);
* every failure — unknown kind, bad options, invalid network, slack without a generator, a
  runner bug — is a ``status="failed"`` result with a stable code; nothing raises across the
  boundary;
* non-convergence is *not* a failure: ``status="ok"`` with ``result.converged == False`` — but
  an infeasible/unbounded ``opf.dc`` LP/QP *is* a failure (``INFEASIBLE_LP``/``UNBOUNDED_LP``,
  not ``INTERNAL``), a deliberate M3 distinction (wave spec W7): an infeasible LP has no
  dispatch at all, unlike a non-converged AC iterate;
* warnings emitted inside the solve (``SetpointConflictWarning``) are attached as strings.
"""

from __future__ import annotations

import json
import warnings
from typing import Any, NoReturn

import pytest
from pydantic import BaseModel, ValidationError

import mambo_power
from mambo_power import jobs
from mambo_power.contingency import N1Options
from mambo_power.io import matpower
from mambo_power.jobs import (
    KINDS,
    KindSpec,
    SolveRequest,
    SolveResult,
    StructuredError,
    kinds,
    register,
    run,
    run_json,
)
from mambo_power.jobs import registry as jobs_registry
from mambo_power.market import MarketNodalOptions
from mambo_power.model import Network
from mambo_power.numerics import SetpointConflictWarning
from mambo_power.opf import OpfDcOptions
from mambo_power.pf import AcOptions, solve_ac, solve_dc
from mambo_power.results import (
    AcPowerFlowResult,
    DcPowerFlowResult,
    MarketNodalResult,
    N1Result,
    OpfDcResult,
    ResultProvenance,
)
from tests._fixtures import FIXTURES_DIR

DERIVED_DIR = FIXTURES_DIR / "derived"
TIMING = {"provenance": {"started_at", "elapsed_s"}}
KNOWN_KINDS = {"pf.ac", "pf.dc", "opf.dc", "n1", "market.nodal"}


def _network(name: str = "case14") -> Network:
    path = (DERIVED_DIR if name.startswith("case14_") else FIXTURES_DIR) / f"{name}.m"
    return matpower.load(path)


@pytest.fixture(scope="module")
def case14() -> Network:
    return _network("case14")


def _infeasible_net(case14: Network) -> Network:
    """``case14`` with every generator's capacity collapsed far below its own load — no
    dispatch can possibly satisfy the balance constraint (AC-8's/AC-7's ``INFEASIBLE_LP`` case;
    ``case14``'s loads carry no bid, so this is infeasible for ``market.nodal`` the identical
    way it is for ``opf.dc`` — the welfare LP reduces to the same fixed-load balance row)."""
    generators = [
        g.model_copy(update={"p_max_mw": 0.01, "p_min_mw": 0.0}) for g in case14.generators
    ]
    return case14.model_copy(update={"generators": generators})


# --- KINDS contract -------------------------------------------------------------------------------
def test_kinds_lists_exactly_the_m3_kinds() -> None:
    assert set(KINDS) == KNOWN_KINDS
    assert kinds() == sorted(KNOWN_KINDS)
    assert jobs.KINDS is KINDS


def test_every_kind_has_models_and_a_callable_runner() -> None:
    for name, spec in KINDS.items():
        assert isinstance(spec, KindSpec)
        assert spec.kind == name
        assert spec.options_model is None or issubclass(spec.options_model, BaseModel)
        assert issubclass(spec.result_model, BaseModel)
        assert callable(spec.runner)
    assert KINDS["pf.ac"].options_model is AcOptions
    assert KINDS["pf.ac"].result_model is AcPowerFlowResult
    assert KINDS["pf.dc"].options_model is None
    assert KINDS["pf.dc"].result_model is DcPowerFlowResult
    assert KINDS["opf.dc"].options_model is OpfDcOptions
    assert KINDS["opf.dc"].result_model is OpfDcResult
    assert KINDS["n1"].options_model is N1Options
    assert KINDS["n1"].result_model is N1Result
    assert KINDS["market.nodal"].options_model is MarketNodalOptions
    assert KINDS["market.nodal"].result_model is MarketNodalResult


def test_register_adds_a_kind_and_refuses_duplicates() -> None:
    spec = KindSpec(
        kind="test.echo", options_model=None, result_model=DcPowerFlowResult, runner=solve_dc
    )
    try:
        register(spec)
        assert "test.echo" in kinds()
        with pytest.raises(ValueError, match="already registered"):
            register(spec)
    finally:
        KINDS.pop("test.echo", None)
    assert set(KINDS) == KNOWN_KINDS


# --- happy path -----------------------------------------------------------------------------------
def test_run_pf_ac_on_case14_is_ok_with_typed_result_and_provenance(case14: Network) -> None:
    out = run(SolveRequest(kind="pf.ac", network=case14, job_id="j-1"))
    assert isinstance(out, SolveResult)
    assert out.status == "ok"
    assert out.kind == "pf.ac"
    assert out.job_id == "j-1"
    assert out.error is None
    assert isinstance(out.result, AcPowerFlowResult)
    assert out.result.converged is True
    assert out.result.iterations > 0
    assert isinstance(out.provenance, ResultProvenance)
    assert out.provenance.kind == "pf.ac"
    assert out.provenance.version == mambo_power.__version__
    assert out.provenance.elapsed_s > 0
    assert out.provenance == out.result.provenance
    assert out.warnings == []


def test_run_pf_dc_on_case14_is_ok_with_typed_result_and_provenance(case14: Network) -> None:
    out = run(SolveRequest(kind="pf.dc", network=case14))
    assert out.status == "ok"
    assert out.job_id is None
    assert isinstance(out.result, DcPowerFlowResult)
    assert out.provenance is not None
    assert out.provenance.kind == "pf.dc"
    assert out.provenance == out.result.provenance
    assert out.provenance.options == {}


def test_run_opf_dc_on_case14_is_ok_with_typed_result_and_provenance(case14: Network) -> None:
    out = run(SolveRequest(kind="opf.dc", network=case14))
    assert out.status == "ok"
    assert out.error is None
    assert isinstance(out.result, OpfDcResult)
    assert out.result.status == "Optimal"
    assert out.result.generators
    assert out.provenance is not None
    assert out.provenance.kind == "opf.dc"
    assert out.provenance == out.result.provenance


def test_run_n1_on_case14_is_ok_with_typed_result_and_provenance(case14: Network) -> None:
    out = run(SolveRequest(kind="n1", network=case14))
    assert out.status == "ok"
    assert out.error is None
    assert isinstance(out.result, N1Result)
    assert out.provenance is not None
    assert out.provenance.kind == "n1"
    assert out.provenance == out.result.provenance


def test_run_market_nodal_on_case14_is_ok_with_typed_result_and_provenance(case14: Network) -> None:
    """``case14``'s loads carry no bid, so ``market.nodal`` reduces to plain fixed-load
    clearing (AC-5's price-taker reduction) — this is a jobs-boundary smoke test, not a
    re-proof of AC-4/AC-5's settlement math (that's ``test_market_nodal.py``'s job)."""
    out = run(SolveRequest(kind="market.nodal", network=case14))
    assert out.status == "ok"
    assert out.error is None
    assert isinstance(out.result, MarketNodalResult)
    assert out.result.status == "Optimal"
    assert out.result.generators
    assert out.result.loads
    assert out.provenance is not None
    assert out.provenance.kind == "market.nodal"
    assert out.provenance == out.result.provenance


def test_options_are_validated_and_passed_to_the_runner(case14: Network) -> None:
    out = run(
        SolveRequest(kind="pf.ac", network=case14, options={"q_limits": False, "init": "flat"})
    )
    assert out.status == "ok"
    assert out.provenance is not None
    assert out.provenance.options == AcOptions(q_limits=False, init="flat").model_dump()


def test_run_matches_the_module_level_entry_points(case14: Network) -> None:
    ac = run(SolveRequest(kind="pf.ac", network=case14)).result
    dc = run(SolveRequest(kind="pf.dc", network=case14)).result
    assert ac is not None and dc is not None
    assert ac.model_dump(exclude=TIMING) == solve_ac(case14).model_dump(exclude=TIMING)
    assert dc.model_dump(exclude=TIMING) == solve_dc(case14).model_dump(exclude=TIMING)


@pytest.mark.parametrize("kind", ["pf.ac", "pf.dc", "opf.dc", "n1", "market.nodal"])
def test_run_is_pure_equal_results_modulo_timing(kind: str, case14: Network) -> None:
    req = SolveRequest(kind=kind, network=case14)
    first, second = run(req), run(req)
    assert first.result is not None and second.result is not None
    assert first.result.model_dump(exclude=TIMING) == second.result.model_dump(exclude=TIMING)
    assert first.model_dump(exclude={"result", "provenance"}) == second.model_dump(
        exclude={"result", "provenance"}
    )
    assert first.provenance is not None and second.provenance is not None
    assert first.provenance.started_at <= second.provenance.started_at


# --- JSON round-trip ------------------------------------------------------------------------------
def test_request_round_trips_through_json(case14: Network) -> None:
    req = SolveRequest(kind="pf.ac", network=case14, options={"max_iter": 5}, job_id="rt")
    again = SolveRequest.model_validate_json(req.model_dump_json())
    assert again == req
    assert again.network == case14


def test_result_round_trips_through_json_with_the_kinds_result_type(case14: Network) -> None:
    for kind, result_type in (
        ("pf.ac", AcPowerFlowResult),
        ("pf.dc", DcPowerFlowResult),
        ("opf.dc", OpfDcResult),
        ("n1", N1Result),
        ("market.nodal", MarketNodalResult),
    ):
        out = run(SolveRequest(kind=kind, network=case14))
        again = SolveResult.model_validate_json(out.model_dump_json())
        assert again == out
        assert type(again.result) is result_type


def test_result_type_must_match_the_kind(case14: Network) -> None:
    dc = run(SolveRequest(kind="pf.dc", network=case14))
    with pytest.raises(ValidationError, match="pf.ac"):
        SolveResult(kind="pf.ac", status="ok", result=dc.result, provenance=dc.provenance)
    payload = json.loads(dc.model_dump_json())
    payload["kind"] = "pf.ac"
    with pytest.raises(ValidationError):
        SolveResult.model_validate(payload)


def test_run_json_is_json_in_json_out(case14: Network) -> None:
    text = SolveRequest(kind="pf.dc", network=case14, job_id="json-1").model_dump_json()
    out_text = run_json(text)
    assert isinstance(out_text, str)
    payload = json.loads(out_text)
    assert payload["status"] == "ok"
    assert payload["kind"] == "pf.dc"
    assert payload["job_id"] == "json-1"
    assert payload["error"] is None
    assert payload["provenance"]["kind"] == "pf.dc"
    out = SolveResult.model_validate_json(out_text)
    assert isinstance(out.result, DcPowerFlowResult)
    assert out.result.model_dump(exclude=TIMING) == solve_dc(case14).model_dump(exclude=TIMING)


def test_models_forbid_extra_fields(case14: Network) -> None:
    with pytest.raises(ValidationError):
        SolveRequest(kind="pf.dc", network=case14, extra=1)  # type: ignore[call-arg]
    with pytest.raises(ValidationError):
        StructuredError(code="X", message="m", extra=1)  # type: ignore[call-arg]


# --- structured failures --------------------------------------------------------------------------
def _assert_failed(out: SolveResult, code: str) -> StructuredError:
    assert out.status == "failed"
    assert out.result is None
    assert out.error is not None
    assert out.error.code == code
    assert out.error.message
    # a minimal provenance is stamped whenever the kind could be read from the request
    if out.kind:
        assert out.provenance is not None
        assert out.provenance.kind == out.kind
        assert out.provenance.solver == "none"
        assert out.provenance.version == mambo_power.__version__
        assert out.provenance.elapsed_s >= 0.0
    else:
        assert out.provenance is None
    return out.error


def test_unknown_kind_is_a_failed_result(case14: Network) -> None:
    # "market.zonal" (spec Not Doing: zonal clearing is M6, not this wave) — genuinely unknown,
    # unlike "market.nodal" which this wave (S6) registers; a still-unregistered example was
    # needed after S6 landed.
    out = run(SolveRequest(kind="market.zonal", network=case14, job_id="u"))
    error = _assert_failed(out, "UNKNOWN_KIND")
    assert out.kind == "market.zonal"
    assert out.job_id == "u"
    assert "market.zonal" in error.message
    assert "pf.ac" in error.message and "pf.dc" in error.message


def test_bad_options_is_a_failed_result_with_pydantic_details(case14: Network) -> None:
    error = _assert_failed(
        run(SolveRequest(kind="pf.ac", network=case14, options={"tol": "x"})), "BAD_OPTIONS"
    )
    assert "tol" in error.message
    assert error.issues is None
    assert error.details is not None
    assert error.details[0]["loc"] == ["tol"]
    # unknown keys are a failure too, never silently ignored
    unknown = _assert_failed(
        run(SolveRequest(kind="pf.ac", network=case14, options={"nope": 1})), "BAD_OPTIONS"
    )
    assert "nope" in unknown.message
    # pf.dc takes no options: any key is rejected
    dc = _assert_failed(
        run(SolveRequest(kind="pf.dc", network=case14, options={"tol": 1e-8})), "BAD_OPTIONS"
    )
    assert "pf.dc" in dc.message


def test_invalid_network_through_run_json_is_a_failed_result_with_issues(case14: Network) -> None:
    payload: dict[str, Any] = json.loads(
        SolveRequest(kind="pf.dc", network=case14, job_id="bad").model_dump_json()
    )
    payload["network"]["branches"][0]["to_bus"] = "bus-999"  # dangling reference
    text = json.dumps(payload)
    with pytest.raises(Exception, match="DANGLING_REF"):
        SolveRequest.model_validate_json(text)  # the raw model raises ...
    out = SolveResult.model_validate_json(run_json(text))  # ... the job boundary does not
    error = _assert_failed(out, "VALIDATION")
    assert out.kind == "pf.dc"
    assert out.job_id == "bad"
    assert error.issues is not None
    assert [i.code for i in error.issues] == ["DANGLING_REF"]
    assert error.issues[0].path == "branches[0].to_bus"


def test_mutated_invalid_network_through_run_is_a_failed_result() -> None:
    req = SolveRequest(kind="pf.ac", network=_network("case14"))
    req.network.branches[0].to_bus = "bus-999"  # Network does not re-validate on mutation; run must
    out = run(req)
    error = _assert_failed(out, "VALIDATION")
    assert error.issues is not None
    assert error.issues[0].code == "DANGLING_REF"


def test_malformed_request_json_is_a_failed_result() -> None:
    out = SolveResult.model_validate_json(run_json('{"kind": "pf.dc", "job_id": "m"}'))
    error = _assert_failed(out, "BAD_REQUEST")
    assert out.kind == "pf.dc"
    assert out.job_id == "m"
    assert "network" in error.message
    not_json = SolveResult.model_validate_json(run_json("{not json"))
    _assert_failed(not_json, "BAD_REQUEST")
    assert not_json.kind == ""


def test_deeply_nested_malformed_json_is_a_failed_result_not_a_crash() -> None:
    """S4.1: pydantic's own parser bails on depth with a caught ``ValidationError``, but the
    ``_peek`` helper's own ``json.loads`` on the same text raised an uncaught ``RecursionError``
    — nothing crossing the boundary is the whole contract of ``run_json`` (module docstring)."""
    text = "[" * 5000 + "]" * 5000
    out = SolveResult.model_validate_json(run_json(text))
    _assert_failed(out, "BAD_REQUEST")
    assert out.kind == ""
    assert out.job_id is None


def test_dc_of_a_zero_reactance_branch_is_unsolvable_network_not_internal(case14: Network) -> None:
    """C2: a branch with ``x == 0`` is a legal ``Network`` (BAD_RANGE only fires on a branch
    with r == x == 0, model M1 fold item B) but DC susceptance is undefined for it — a
    user-data problem, not a solver bug, so it must not be filed as INTERNAL (review
    m2-review-6axis.md, Correctness finding 2)."""
    branches = list(case14.branches)
    branches[0] = branches[0].model_copy(update={"x": 0.0})
    assert branches[0].r != 0.0  # legal per validate_network; only DC cannot solve it
    net = case14.model_copy(update={"branches": branches})
    out = run(SolveRequest(kind="pf.dc", network=net))
    error = _assert_failed(out, "UNSOLVABLE_NETWORK")
    assert "x == 0" in error.message
    assert branches[0].id in error.message


def test_slack_without_generator_is_a_failed_result() -> None:
    for kind in ("pf.ac", "pf.dc"):
        out = run(SolveRequest(kind=kind, network=_network("case14_noslackgen")))
        error = _assert_failed(out, "NO_SLACK_GENERATOR")
        assert "bus-1" in error.message
        assert error.issues is None


def test_infeasible_opf_dc_is_infeasible_lp_not_internal(case14: Network) -> None:
    """AC-8: a hand-built infeasible LP (contradictory generator bounds, load unreachable)
    fails as ``INFEASIBLE_LP`` — a structured job failure, not ``INTERNAL`` and not a
    "successful" ``status="ok"`` result carrying a non-Optimal status (unlike ``pf.ac``'s
    non-convergence, see ``test_non_convergence_is_ok_with_converged_false``)."""
    out = run(SolveRequest(kind="opf.dc", network=_infeasible_net(case14)))
    error = _assert_failed(out, "INFEASIBLE_LP")
    assert "Infeasible" in error.message


def test_infeasible_market_nodal_is_infeasible_lp_not_internal(case14: Network) -> None:
    """AC-7: the same hand-built infeasible LP (contradictory generator bounds), routed through
    ``market.nodal`` instead of ``opf.dc`` — ``case14``'s loads carry no bid, so the welfare LP
    reduces to the identical fixed-load infeasibility, and it must land as ``INFEASIBLE_LP``,
    not ``INTERNAL``, via the shared status-translation helper (wave spec Design item 6)."""
    out = run(SolveRequest(kind="market.nodal", network=_infeasible_net(case14)))
    error = _assert_failed(out, "INFEASIBLE_LP")
    assert "Infeasible" in error.message


def test_opf_dc_and_market_nodal_share_the_same_status_translation_function(
    case14: Network, monkeypatch: pytest.MonkeyPatch
) -> None:
    """AC-7/wave spec Design item 6: the non-Optimal-status-to-structured-failure translation is
    genuinely shared, not duplicated a second time — proved by spying on the one function object
    both ``_run_opf_dc`` and ``_run_market_nodal`` call, confirming both runners' infeasible-LP
    paths exercise it (not two copies of the same ~15 lines)."""
    original = jobs_registry._translate_non_optimal_status
    calls: list[str] = []

    def spy(kind: str, status: str, message: str | None) -> NoReturn:
        calls.append(kind)
        original(kind, status, message)

    monkeypatch.setattr(jobs_registry, "_translate_non_optimal_status", spy)
    net = _infeasible_net(case14)
    assert run(SolveRequest(kind="opf.dc", network=net)).error is not None
    assert run(SolveRequest(kind="market.nodal", network=net)).error is not None
    assert calls == ["opf.dc", "market.nodal"]


def test_runner_exception_is_a_failed_internal_result(
    case14: Network, monkeypatch: pytest.MonkeyPatch
) -> None:
    def boom(net: Network, options: BaseModel | None) -> BaseModel:
        raise RuntimeError("kaboom")

    monkeypatch.setitem(
        KINDS,
        "pf.dc",
        KindSpec(kind="pf.dc", options_model=None, result_model=DcPowerFlowResult, runner=boom),
    )
    out = run(SolveRequest(kind="pf.dc", network=case14))
    error = _assert_failed(out, "INTERNAL")
    assert error.message == "RuntimeError: kaboom"


def test_runner_returning_the_wrong_type_is_internal(
    case14: Network, monkeypatch: pytest.MonkeyPatch
) -> None:
    def wrong(net: Network, options: BaseModel | None) -> BaseModel:
        return solve_dc(net)

    monkeypatch.setitem(
        KINDS,
        "pf.ac",
        KindSpec(
            kind="pf.ac", options_model=AcOptions, result_model=AcPowerFlowResult, runner=wrong
        ),
    )
    error = _assert_failed(run(SolveRequest(kind="pf.ac", network=case14)), "INTERNAL")
    assert "DcPowerFlowResult" in error.message


# --- warnings and non-convergence -----------------------------------------------------------------
def test_setpoint_conflict_warning_is_attached_not_raised() -> None:
    net = _network("case14_roles")
    with warnings.catch_warnings():
        warnings.simplefilter("error")  # a leaked warning would raise here
        out = run(SolveRequest(kind="pf.ac", network=net))
    assert out.status == "ok"
    assert len(out.warnings) == 1
    assert out.warnings[0].startswith("SetpointConflictWarning: ")
    assert "bus-2" in out.warnings[0]
    with pytest.warns(SetpointConflictWarning):
        solve_ac(net)  # the module-level entry point still warns


def test_warnings_round_trip_and_are_empty_on_clean_networks(case14: Network) -> None:
    net = _network("case14_roles")
    out = run(SolveRequest(kind="pf.dc", network=net))
    again = SolveResult.model_validate_json(out.model_dump_json())
    assert again.warnings == out.warnings and len(again.warnings) == 1
    assert run(SolveRequest(kind="pf.dc", network=case14)).warnings == []


def test_non_convergence_is_ok_with_converged_false(case14: Network) -> None:
    out = run(SolveRequest(kind="pf.ac", network=case14, options={"max_iter": 1, "init": "flat"}))
    assert out.status == "ok"
    assert out.error is None
    assert isinstance(out.result, AcPowerFlowResult)
    assert out.result.converged is False
    assert out.result.iterations == 1
    assert out.result.message is not None and "did not converge" in out.result.message
    assert out.provenance is not None
    assert out.provenance.options["max_iter"] == 1
