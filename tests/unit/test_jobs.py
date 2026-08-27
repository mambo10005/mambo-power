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
import math
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
from mambo_power.market import CorridorLimit, MarketMultiperiodOptions, MarketNodalOptions
from mambo_power.market.zonal import MarketZonalOptions
from mambo_power.model import Network, Period, Scenario
from mambo_power.numerics import SetpointConflictWarning
from mambo_power.opf import OpfDcOptions
from mambo_power.pf import AcOptions, solve_ac, solve_dc
from mambo_power.results import (
    AcPowerFlowResult,
    DcPowerFlowResult,
    MarketMultiperiodResult,
    MarketNodalResult,
    MarketZonalResult,
    N1Result,
    OpfDcResult,
    ResultProvenance,
)
from tests._fixtures import FIXTURES_DIR
from tests._rated import rated_network
from tests._zones import corridors, promote_areas_to_zones

DERIVED_DIR = FIXTURES_DIR / "derived"
TIMING = {"provenance": {"started_at", "elapsed_s"}}
# NOTE (S7/AC-7, and again M6/S7b/AC-7): widened from the M4 set of 5 to include
# "market.multiperiod" (M5), then to include "market.zonal" (M6) -- the one deliberate edit to a
# pre-existing line in this file, unavoidable because this constant is compared against
# jobs.KINDS by test_kinds_lists_exactly_the_m3_kinds/
# test_register_adds_a_kind_and_refuses_duplicates, both of which assert the *current* set of
# registered kinds. Wave M6's AC-7 requires "jobs.KINDS lists exactly 7 kinds", so leaving this
# at 6 would make those two pre-existing tests assert something now false, not preserve a
# compatibility guarantee -- the same treatment wave M4 gave this identical line when it added
# "market.nodal" as the 5th kind, and wave M5 gave it again for the 6th. No other pre-existing
# line in this file is touched; the request/response *compatibility* tests below are added new,
# alongside the untouched originals.
KNOWN_KINDS = {
    "pf.ac",
    "pf.dc",
    "opf.dc",
    "n1",
    "market.nodal",
    "market.multiperiod",
    "market.zonal",
}


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
    # "pf.telepathy" is deliberately *fictional*, and that is the whole point of the choice.
    # This test has already been moved twice -- off "market.nodal" and then off "market.zonal" --
    # each time because the string it used as its example of an unknown kind got registered, which
    # made the assertion silently stop testing what it names. A plausible-sounding placeholder is
    # a time bomb on a fixed date nobody knows; a kind that can never become real is not.
    # docs/manual/jobs.md and examples/04_jobs_api.py use the same string for the same reason.
    out = run(SolveRequest(kind="pf.telepathy", network=case14, job_id="u"))
    error = _assert_failed(out, "UNKNOWN_KIND")
    assert out.kind == "pf.telepathy"
    assert out.job_id == "u"
    assert "pf.telepathy" in error.message
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
    # S7/AC-7 NOTE: the one deliberate edit to a pre-existing test *body* in this file. This
    # local stub's signature/body is adapted from (net: Network, ...) -> solve_dc(net) to
    # (scenario: Scenario, ...) -> solve_dc(scenario.network), because "every Runner becomes
    # (Scenario, options) -> result" (wave M5 design item 2) is the plan's own mandated change
    # to jobs.registry.Runner -- an internal registry extension-point contract, not part of the
    # SolveRequest/JSON compatibility surface AC-7's "risky half" protects (that surface is
    # proven intact by every test above this banner, none of which needed this treatment). The
    # test's actual claim -- a runner returning the wrong result type is an INTERNAL failure --
    # is otherwise unchanged.
    def wrong(scenario: Scenario, options: BaseModel | None) -> BaseModel:
        return solve_dc(scenario.network)

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


# =================================================================================================
# wave M5 S7 / AC-7 -- SolveRequest widening (network-or-scenario), the uniform (Scenario, options)
# Runner, and the new market.multiperiod kind. Every test below is *added*; nothing above this
# banner (besides the single KNOWN_KINDS line, explained where it is defined, and the one Runner-
# signature adaptation inside test_runner_returning_the_wrong_type_is_internal, explained there)
# was edited, and that is the point: the M2/M3/M4 tests above are the primary evidence that D3's
# widening of a public, JSON-serializable request surface did not change any pre-existing
# SolveRequest(kind=..., network=...) construction or any pre-existing serialized JSON.
# =================================================================================================

# NOTE (M6/S7b/AC-7): renamed from ALL_SIX_KINDS and widened with "market.zonal" -- the same kind
# of unavoidable, count-bearing rename KNOWN_KINDS documents above (its own name would otherwise
# assert a false "six" once a 7th kind exists). Its one usage (the purity parametrize below) and
# the comment naming it were updated together; nothing else in this M5 section changed.
ALL_SEVEN_KINDS = (
    "pf.ac",
    "pf.dc",
    "opf.dc",
    "n1",
    "market.nodal",
    "market.multiperiod",
    "market.zonal",
)


def _two_period_scenario(case14: Network) -> Scenario:
    """A genuine multi-period Scenario built from case14's own first load (id "load-2",
    p_mw=21.7): two periods with different overrides, so the horizon is not degenerate."""
    return Scenario(
        network=case14,
        periods=[Period(load_p_mw={"load-2": 18.0}), Period(load_p_mw={"load-2": 30.0})],
    )


# --- KINDS contract: the 6th kind -------------------------------------------------------------
def test_kinds_registers_market_multiperiod_as_the_sixth_kind() -> None:
    # NOTE (M6/S7b/AC-7): bumped 6 -> 7, the same necessary-count-edit treatment KNOWN_KINDS
    # documents above -- a 7th kind (market.zonal) is now registered too, and this pre-existing
    # exact-count assertion would otherwise assert something now false.
    assert len(KINDS) == 7
    assert "market.multiperiod" in KINDS
    spec = KINDS["market.multiperiod"]
    assert spec.options_model is MarketMultiperiodOptions
    assert spec.result_model is MarketMultiperiodResult
    assert callable(spec.runner)


# --- SolveRequest widening: exactly one of network/scenario --------------------------------------
def test_solve_request_rejects_neither_network_nor_scenario() -> None:
    with pytest.raises(ValidationError, match="network.*scenario|scenario.*network"):
        SolveRequest(kind="pf.dc")  # type: ignore[call-arg]


def test_solve_request_rejects_both_network_and_scenario(case14: Network) -> None:
    with pytest.raises(ValidationError, match="network.*scenario|scenario.*network"):
        SolveRequest(kind="pf.dc", network=case14, scenario=Scenario(network=case14))


def test_solve_request_network_normalizes_to_a_single_period_scenario(case14: Network) -> None:
    """The powerless-test guard from the dispatch: this does not just check construction does
    not raise -- it inspects the *normalized* Scenario's contents and identity."""
    req = SolveRequest(kind="pf.dc", network=case14)
    resolved = req.resolved_scenario
    assert isinstance(resolved, Scenario)
    assert resolved.network == case14
    assert resolved.network is case14  # wrapped, not copied -- no revalidation-triggered clone
    assert resolved.periods is None


def test_solve_request_scenario_field_is_used_directly(case14: Network) -> None:
    scenario = _two_period_scenario(case14)
    req = SolveRequest(kind="market.multiperiod", scenario=scenario)
    assert req.network is None
    assert req.resolved_scenario is scenario
    assert req.resolved_scenario.periods is not None
    assert len(req.resolved_scenario.periods) == 2


def test_solve_request_network_mutation_is_still_picked_up_via_resolved_scenario(
    case14: Network,
) -> None:
    """The pre-widening behaviour this must not regress: run() re-checks the network's
    invariants itself because Network does not re-validate on mutation on its own
    (test_mutated_invalid_network_through_run_is_a_failed_result, untouched, proves the same
    thing through run()). This proves resolved_scenario itself observes the mutation: wrapping
    a mutated-invalid network into a fresh Scenario *does* re-run Network's own after-validator
    (nested-model construction, model/scenario.py's own documented behaviour), so the mutation
    surfaces here as a raised NetworkValidationError where it did not before mutation -- run()
    catches exactly this exception (see jobs/run.py) so it never crosses run()'s own boundary."""
    req = SolveRequest(kind="pf.ac", network=_network("case14"))
    before = req.resolved_scenario  # valid before mutation: does not raise
    assert before.network.branches[0].to_bus != "bus-999"
    req.network.branches[0].to_bus = "bus-999"
    with pytest.raises(Exception, match="DANGLING_REF"):
        _ = req.resolved_scenario


def test_runner_receives_the_resolved_scenario_not_a_bare_network(
    case14: Network, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Powerless-test guard: proves the runner is actually called with a Scenario wrapping this
    request's network, not merely that SolveRequest construction succeeds."""
    received: list[object] = []

    def spy(scenario: Scenario, options: BaseModel | None) -> BaseModel:
        received.append(scenario)
        return solve_dc(scenario.network)

    monkeypatch.setitem(
        KINDS,
        "pf.dc",
        KindSpec(kind="pf.dc", options_model=None, result_model=DcPowerFlowResult, runner=spy),
    )
    out = run(SolveRequest(kind="pf.dc", network=case14))
    assert out.status == "ok"
    assert len(received) == 1
    assert isinstance(received[0], Scenario)
    assert received[0].network is case14


# --- market.multiperiod happy path ----------------------------------------------------------------
def test_run_market_multiperiod_on_case14_is_ok_with_typed_result_and_provenance(
    case14: Network,
) -> None:
    """A period-less (network=) request: T=1, mirroring the market.nodal jobs smoke test."""
    out = run(SolveRequest(kind="market.multiperiod", network=case14))
    assert out.status == "ok"
    assert out.error is None
    assert isinstance(out.result, MarketMultiperiodResult)
    assert out.result.status == "Optimal"
    assert out.result.n_periods == 1
    assert out.result.periods
    assert out.provenance is not None
    assert out.provenance.kind == "market.multiperiod"
    assert out.provenance == out.result.provenance


def test_run_market_multiperiod_with_real_periods_via_scenario(case14: Network) -> None:
    scenario = _two_period_scenario(case14)
    out = run(SolveRequest(kind="market.multiperiod", scenario=scenario))
    assert out.status == "ok"
    assert isinstance(out.result, MarketMultiperiodResult)
    assert out.result.status == "Optimal"
    assert out.result.n_periods == 2
    assert len(out.result.periods) == 2


# --- purity, across all seven kinds -----------------------------------------------------------
@pytest.mark.parametrize("kind", ALL_SEVEN_KINDS)
def test_run_is_pure_across_all_seven_kinds(kind: str, case14: Network) -> None:
    req = SolveRequest(kind=kind, network=case14)
    first, second = run(req), run(req)
    assert first.result is not None and second.result is not None
    assert first.result.model_dump(exclude=TIMING) == second.result.model_dump(exclude=TIMING)
    assert first.model_dump(exclude={"result", "provenance"}) == second.model_dump(
        exclude={"result", "provenance"}
    )
    assert first.provenance is not None and second.provenance is not None
    assert first.provenance.started_at <= second.provenance.started_at


def test_run_is_pure_for_market_multiperiod_with_real_periods(case14: Network) -> None:
    """The purity check above uses network= (T=1); this repeats it with a genuine multi-period
    Scenario, so purity is proven on a non-trivial (non-constant-looking) result too."""
    scenario = _two_period_scenario(case14)
    req = SolveRequest(kind="market.multiperiod", scenario=scenario)
    first, second = run(req), run(req)
    assert first.result is not None and second.result is not None
    assert isinstance(first.result, MarketMultiperiodResult)
    assert first.result.n_periods == 2
    assert first.result.model_dump(exclude=TIMING) == second.result.model_dump(exclude=TIMING)


# --- JSON round trip --------------------------------------------------------------------------
def test_request_with_scenario_round_trips_through_json(case14: Network) -> None:
    scenario = _two_period_scenario(case14)
    req = SolveRequest(kind="market.multiperiod", scenario=scenario, job_id="rt-s")
    again = SolveRequest.model_validate_json(req.model_dump_json())
    assert again == req
    assert again.network is None
    assert again.resolved_scenario == req.resolved_scenario


def test_result_round_trips_through_json_for_market_multiperiod(case14: Network) -> None:
    out = run(SolveRequest(kind="market.multiperiod", network=case14))
    again = SolveResult.model_validate_json(out.model_dump_json())
    assert again == out
    assert type(again.result) is MarketMultiperiodResult


def test_market_multiperiod_with_real_periods_round_trips_through_run_json(
    case14: Network,
) -> None:
    """Explicit requirement: a market.multiperiod request carrying a genuine multi-period
    Scenario round-trips through run_json (JSON text in, JSON text out) and returns a typed
    MarketMultiperiodResult, not just a dict-shaped payload."""
    scenario = _two_period_scenario(case14)
    req = SolveRequest(kind="market.multiperiod", scenario=scenario, job_id="mp-1")
    out_text = run_json(req.model_dump_json())
    payload = json.loads(out_text)
    assert payload["status"] == "ok"
    assert payload["kind"] == "market.multiperiod"
    assert payload["job_id"] == "mp-1"
    out = SolveResult.model_validate_json(out_text)
    assert isinstance(out.result, MarketMultiperiodResult)
    assert out.result.n_periods == 2
    assert len(out.result.periods) == 2


# --- never raises: structured failures for market.multiperiod --------------------------------
def test_infeasible_market_multiperiod_is_infeasible_lp_not_internal(case14: Network) -> None:
    """AC-7: the same hand-built infeasible network as market.nodal's/opf.dc's equivalent
    tests, routed through market.multiperiod -- an infeasible multiperiod horizon must land as
    INFEASIBLE_LP, not INTERNAL, and not a "successful" status="ok" result."""
    out = run(SolveRequest(kind="market.multiperiod", network=_infeasible_net(case14)))
    error = _assert_failed(out, "INFEASIBLE_LP")
    assert "Infeasible" in error.message


def test_market_multiperiod_shares_the_status_translation_function(
    case14: Network, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Design item 6 (reused, not re-implemented a third time): spies on the same
    _translate_non_optimal_status object opf.dc and market.nodal already share (proved by the
    untouched test_opf_dc_and_market_nodal_share_the_same_status_translation_function above),
    and confirms market.multiperiod's runner exercises that identical function object too."""
    original = jobs_registry._translate_non_optimal_status
    calls: list[str] = []

    def spy(kind: str, status: str, message: str | None) -> NoReturn:
        calls.append(kind)
        original(kind, status, message)

    monkeypatch.setattr(jobs_registry, "_translate_non_optimal_status", spy)
    net = _infeasible_net(case14)
    assert run(SolveRequest(kind="market.multiperiod", network=net)).error is not None
    assert calls == ["market.multiperiod"]


# =================================================================================================
# wave M6 S7b / AC-7 -- the market.zonal kind, jobs.KINDS widened from 6 to exactly 7. Every test
# below is *added*; the only pre-existing lines touched are the two AC-7 itself forces (KNOWN_KINDS,
# and ALL_SIX_KINDS -> ALL_SEVEN_KINDS with its one usage and comment), each explained at its own
# site above -- the same treatment wave M5 gave this file when it added market.multiperiod.
# =================================================================================================


@pytest.fixture(scope="module")
def case30_zoned() -> Network:
    """A rated, zone-promoted case30 -- three real zones (11/10/9 buses, all three carrying
    generation, measured directly), corridors derivable from tests/_zones.py's own cut-set
    ratings. Mirrors tests/unit/test_market_zonal.py's _elastic_zoned_network, minus the elastic
    bids AC-7's jobs-surface contract does not need."""
    return rated_network(promote_areas_to_zones(_network("case30")))


def _case30_zonal_options(net: Network) -> MarketZonalOptions:
    """``MarketZonalOptions`` carrying every corridor ``tests/_zones.py`` derives from ``net``'s
    own cut-set ratings -- the fixture half of AC-7's "corridors from tests/_zones.py" clause."""
    caps = corridors(net)
    return MarketZonalOptions(
        corridors=[CorridorLimit(zone1=z1, zone2=z2, cap_mw=cap) for (z1, z2), cap in caps.items()]
    )


# --- KINDS contract: the 7th kind ---------------------------------------------------------------
def test_kinds_registers_market_zonal_as_the_seventh_kind() -> None:
    assert len(KINDS) == 7
    assert "market.zonal" in KINDS
    spec = KINDS["market.zonal"]
    assert spec.options_model is MarketZonalOptions
    assert spec.result_model is MarketZonalResult
    assert callable(spec.runner)


def test_kinds_is_sorted_with_market_zonal_in_place() -> None:
    assert kinds() == sorted(KNOWN_KINDS)
    assert "market.zonal" in kinds()


# --- market.zonal happy path, promoted rated case30 with real corridors -------------------------
def test_run_market_zonal_on_case30_is_ok_with_typed_result_and_provenance(
    case30_zoned: Network,
) -> None:
    options = _case30_zonal_options(case30_zoned)
    scenario = Scenario(network=case30_zoned)
    out = run(SolveRequest(kind="market.zonal", scenario=scenario, options=options.model_dump()))
    assert out.status == "ok"
    assert out.error is None
    assert isinstance(out.result, MarketZonalResult)
    assert out.result.status == "Optimal"
    assert len(out.result.zones) == 3  # one row per zone, promoted case30
    assert out.result.branches  # M5 A23 carry-over: per-branch flow/dual rows present
    assert out.provenance is not None
    assert out.provenance.kind == "market.zonal"
    assert out.provenance == out.result.provenance
    assert len(out.provenance.options["corridors"]) == 3  # AC-7: options land in provenance too


def test_run_market_zonal_with_no_options_is_ok_single_zone_case14(case14: Network) -> None:
    """market.zonal takes the same network= single-period request every prior kind's jobs smoke
    test uses (case14, one zone, no corridors needed) -- the T=1/no-corridor degenerate case, and
    proof this kind needs no options to run at all (``MarketZonalOptions.corridors`` defaults to
    ``[]``)."""
    out = run(SolveRequest(kind="market.zonal", network=case14))
    assert out.status == "ok"
    assert isinstance(out.result, MarketZonalResult)
    assert out.result.status == "Optimal"
    assert len(out.result.zones) == 1


# --- purity, JSON round trip, options preserved --------------------------------------------------
def test_run_is_pure_for_market_zonal_with_real_corridors(case30_zoned: Network) -> None:
    options = _case30_zonal_options(case30_zoned)
    scenario = Scenario(network=case30_zoned)
    req = SolveRequest(kind="market.zonal", scenario=scenario, options=options.model_dump())
    first, second = run(req), run(req)
    assert first.result is not None and second.result is not None
    assert isinstance(first.result, MarketZonalResult)
    assert first.result.model_dump(exclude=TIMING) == second.result.model_dump(exclude=TIMING)


def test_request_with_market_zonal_options_round_trips_through_json(case30_zoned: Network) -> None:
    """AC-7's explicit "including the options" clause: a ``SolveRequest`` carrying
    ``MarketZonalOptions.corridors`` populated survives ``model_dump_json`` / ``model_validate_
    json`` exactly, corridors and all."""
    options = _case30_zonal_options(case30_zoned)
    scenario = Scenario(network=case30_zoned)
    req = SolveRequest(
        kind="market.zonal", scenario=scenario, options=options.model_dump(), job_id="zt-1"
    )
    again = SolveRequest.model_validate_json(req.model_dump_json())
    assert again == req
    assert again.options["corridors"] == req.options["corridors"]
    assert len(again.options["corridors"]) == 3


def test_result_round_trips_through_json_for_market_zonal(case30_zoned: Network) -> None:
    options = _case30_zonal_options(case30_zoned)
    scenario = Scenario(network=case30_zoned)
    out = run(SolveRequest(kind="market.zonal", scenario=scenario, options=options.model_dump()))
    again = SolveResult.model_validate_json(out.model_dump_json())
    assert again == out
    assert type(again.result) is MarketZonalResult


def test_market_zonal_with_corridors_round_trips_through_run_json(case30_zoned: Network) -> None:
    """AC-7: ``run_json`` (JSON text in, JSON text out) for ``market.zonal`` with its options'
    corridors populated -- the options-preservation clause, exercised through the JSON-in/
    JSON-out entry point rather than ``run`` directly."""
    options = _case30_zonal_options(case30_zoned)
    scenario = Scenario(network=case30_zoned)
    req = SolveRequest(
        kind="market.zonal", scenario=scenario, options=options.model_dump(), job_id="mz-1"
    )
    out_text = run_json(req.model_dump_json())
    payload = json.loads(out_text)
    assert payload["status"] == "ok"
    assert payload["kind"] == "market.zonal"
    assert payload["job_id"] == "mz-1"
    assert len(payload["provenance"]["options"]["corridors"]) == 3
    out = SolveResult.model_validate_json(out_text)
    assert isinstance(out.result, MarketZonalResult)
    assert len(out.result.zones) == 3


# --- never raises: adversarial inputs for market.zonal -------------------------------------------
def test_market_zonal_with_empty_corridors_islands_the_zones_and_is_not_an_error(
    case30_zoned: Network,
) -> None:
    """S3's A22(i) finding, exercised through ``jobs``: an empty corridor list is not the copper
    plate -- it islands the zones, each self-supplying -- and every zone on promoted case30
    carries generation (measured directly, ``_case30_zonal_options``'s own docstring), so this is
    a legitimate Optimal clearing, not a failure. ``solve_zonal``'s own docstring: "With no
    corridors at all, every zone must supply itself -- a legitimate (and often infeasible) market
    design, not an error." """
    scenario = Scenario(network=case30_zoned)
    out = run(SolveRequest(kind="market.zonal", scenario=scenario))  # options={} -> corridors=[]
    assert out.status == "ok"
    assert isinstance(out.result, MarketZonalResult)
    assert out.result.status == "Optimal"
    prices = {z.id: z.price for z in out.result.zones}
    assert len(prices) == 3
    assert len(set(prices.values())) == 3  # islanded: every zone prices independently


def test_market_zonal_copper_plate_survives_the_json_round_trip_and_prices_as_one_zone(
    case30_zoned: Network,
) -> None:
    """Walk defect D3: the manual teaches the copper plate as "lifting the cap -- leaving the
    column in place, unbounded", ``opf.zonal``'s own guard says "give a number, 0, or inf", and
    ``CorridorLimit`` used to reject ``inf`` with ``finite_number``, so through ``solve_zonal`` the
    copper plate could only be approximated by a large finite number.

    Proven here on the surface that made it hard -- ``run_json``, JSON text in and out -- and
    proven as a *market* claim rather than a serialisation one: with every corridor unbounded the
    three zones must clear at a single price, which is what a copper plate is. The paired negative
    is committed next door, where an empty corridor list islands the same network and its three
    zones price independently.
    """
    zone_ids = sorted({str(bus.zone) for bus in case30_zoned.buses if bus.zone is not None})
    corridors = [
        {"zone1": a, "zone2": b, "cap_mw": math.inf}
        for i, a in enumerate(zone_ids)
        for b in zone_ids[i + 1 :]
    ]
    req = SolveRequest(
        kind="market.zonal",
        scenario=Scenario(network=case30_zoned),
        options={"corridors": corridors},
        job_id="copper-plate",
    )
    out_text = run_json(req.model_dump_json())
    assert "Infinity" in out_text  # the wire form; json.loads reads it, JSON.parse does not
    payload = json.loads(out_text)
    assert payload["status"] == "ok", payload.get("error")
    echoed = payload["provenance"]["options"]["corridors"]
    assert [entry["cap_mw"] for entry in echoed] == [math.inf] * len(corridors)

    out = SolveResult.model_validate_json(out_text)
    assert isinstance(out.result, MarketZonalResult)
    prices = [zone.price for zone in out.result.zones]
    assert len(prices) == 3
    assert prices == pytest.approx([prices[0]] * 3, abs=1e-4), (
        f"an unbounded corridor between every pair is the copper plate: one price, got {prices}"
    )


def test_market_zonal_corridor_naming_an_unknown_zone_is_a_validation_failure(
    case30_zoned: Network,
) -> None:
    """A corridor naming a zone no bus is assigned to is a *caller* mistake about the network, so
    it lands as ``VALIDATION`` with a ``DANGLING_REF`` issue naming the offending option path --
    not ``INTERNAL``, which the jobs manual defines as "anything else the runner raised (singular
    matrix, a bug)". Walk defect D1: a service author maps ``INTERNAL`` to a 5xx and a pager, so
    every customer who fat-fingers a zone name would page them.

    It cannot be caught at the options model, which has no access to the network -- hence the
    network-level code rather than ``BAD_OPTIONS``.
    """
    scenario = Scenario(network=case30_zoned)
    bad_options = {"corridors": [{"zone1": "1", "zone2": "no-such-zone", "cap_mw": 10.0}]}
    out = run(SolveRequest(kind="market.zonal", scenario=scenario, options=bad_options))
    error = _assert_failed(out, "VALIDATION")
    assert "no-such-zone" in error.message
    assert error.issues
    assert [issue.code for issue in error.issues] == ["DANGLING_REF"]
    assert "corridors[0].zone2" in error.issues[0].path


@pytest.mark.parametrize(
    ("corridors", "fragment"),
    [
        pytest.param(
            [{"zone1": "1", "zone2": "1", "cap_mw": 10.0}], "same zone twice", id="self-pair"
        ),
        pytest.param(
            [
                {"zone1": "1", "zone2": "2", "cap_mw": 10.0},
                {"zone1": "1", "zone2": "2", "cap_mw": 999.0},
            ],
            "more than once",
            id="duplicate-same-order",
        ),
        pytest.param(
            [
                {"zone1": "1", "zone2": "2", "cap_mw": 10.0},
                {"zone1": "2", "zone2": "1", "cap_mw": 999.0},
            ],
            "more than once",
            id="duplicate-reversed",
        ),
    ],
)
def test_market_zonal_malformed_corridor_list_is_bad_options(
    case30_zoned: Network, corridors: list[dict[str, object]], fragment: str
) -> None:
    """A corridor list the options model can judge without the network -- a self-pair, or the same
    unordered pair given twice in either order -- is rejected at step 2 of ``run``'s pipeline, so
    the caller gets ``BAD_OPTIONS`` and pydantic's own ``details``.

    The same-order duplicate is the one review F1 found: ``corridor_map()`` is a dict
    comprehension, so before this validator the second entry silently overwrote the first and the
    market cleared at 999 MW with nothing said. The reversed one already raised, deeper down, as
    ``INTERNAL``.
    """
    scenario = Scenario(network=case30_zoned)
    out = run(
        SolveRequest(kind="market.zonal", scenario=scenario, options={"corridors": corridors})
    )
    error = _assert_failed(out, "BAD_OPTIONS")
    assert fragment in error.message or any(
        fragment in str(detail) for detail in (error.details or [])
    )


def test_market_zonal_through_resolved_scenario_invalid_network_is_a_failed_validation_result(
    case30_zoned: Network,
) -> None:
    """The same mutated-invalid-network path ``test_mutated_invalid_network_through_run_is_a_
    failed_result`` proves for ``pf.ac``, routed through ``market.zonal``:
    ``SolveRequest.resolved_scenario``'s wrap re-runs ``Network``'s own validator (M5 A22), so
    ``run`` still catches it as ``VALIDATION`` rather than letting the exception cross its
    boundary."""
    req = SolveRequest(kind="market.zonal", network=case30_zoned)
    before = req.resolved_scenario  # valid before mutation: does not raise
    assert before.network is case30_zoned
    req.network.branches[0].to_bus = "bus-999999"
    out = run(req)
    error = _assert_failed(out, "VALIDATION")
    assert error.issues


def test_infeasible_market_zonal_is_infeasible_lp_not_internal(case14: Network) -> None:
    """AC-7: the same hand-built infeasible network as ``opf.dc``'s / ``market.nodal``'s /
    ``market.multiperiod``'s equivalent tests, routed through ``market.zonal`` -- an infeasible
    zonal clearing must land as ``INFEASIBLE_LP``, not ``INTERNAL``, and not a "successful"
    ``status="ok"`` result."""
    out = run(SolveRequest(kind="market.zonal", network=_infeasible_net(case14)))
    error = _assert_failed(out, "INFEASIBLE_LP")
    assert "Infeasible" in error.message
    assert "zonal clearing stage" in error.message


def test_market_zonal_shares_the_status_translation_function(
    case14: Network, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Design item 6 (reused, not re-implemented a fourth time): spies on the same
    ``_translate_non_optimal_status`` object ``opf.dc``, ``market.nodal`` and ``market.
    multiperiod`` already share, and confirms ``market.zonal``'s runner exercises that identical
    function object too."""
    original = jobs_registry._translate_non_optimal_status
    calls: list[str] = []

    def spy(kind: str, status: str, message: str | None) -> NoReturn:
        calls.append(kind)
        original(kind, status, message)

    monkeypatch.setattr(jobs_registry, "_translate_non_optimal_status", spy)
    net = _infeasible_net(case14)
    assert run(SolveRequest(kind="market.zonal", network=net)).error is not None
    assert calls == ["market.zonal"]


# --- backward compatibility: all six prior kinds unchanged ---------------------------------------
PRIOR_SIX_KINDS = ("pf.ac", "pf.dc", "opf.dc", "n1", "market.nodal", "market.multiperiod")


@pytest.mark.parametrize("kind", PRIOR_SIX_KINDS)
def test_prior_six_kinds_still_accept_their_existing_network_form_unchanged(
    kind: str, case14: Network
) -> None:
    """AC-7's explicit clause: registering ``market.zonal`` as the 7th kind changes nothing about
    the six that came before it -- every pre-existing ``SolveRequest(kind=..., network=...)``
    construction still resolves and runs exactly as it did before this slice."""
    out = run(SolveRequest(kind=kind, network=case14))
    assert out.status == "ok"
    assert out.error is None
    assert out.result is not None


@pytest.mark.parametrize("kind", ("pf.ac", "market.multiperiod"))
def test_prior_kinds_still_accept_their_existing_scenario_form_unchanged(
    kind: str, case14: Network
) -> None:
    """The ``scenario=`` form (wave M5 D3), also unchanged by this slice's widening."""
    out = run(SolveRequest(kind=kind, scenario=Scenario(network=case14)))
    assert out.status == "ok"
    assert out.error is None
    assert out.result is not None
