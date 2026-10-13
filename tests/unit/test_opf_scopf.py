"""Security-constrained DC-OPF (:mod:`mambo_power.opf.scopf`, ADR-016).

``_triangle`` is the 3-bus equal-reactance mesh of the N-1 tests with costs: a cheap slack unit
``g1`` at ``b1`` ($10/MWh), a dear unit ``g3`` at ``b3`` ($20/MWh), a 90 MW load at ``b2``. The
plain OPF puts all 90 MW on ``g1``: ``br12 = 60``, ``br13 = 30``, ``br23 = −30``. With ``g3``
dispatched at ``x`` the flows superpose (``x`` flows ``b3 -> b1``, two thirds direct): ``br12 =
60 − x/3``, ``br13 = 30 − 2x/3``, ``br23 = −30 − x/3``. Post-contingency, by hand:

* ``br12`` out: ``b2`` is fed only through ``b3``, so ``br13 = 90 − x`` (everything ``g1`` makes
  goes ``b1 -> b3 -> b2``) and ``br23 = −90``.
* ``br23`` out: ``g3``'s ``x`` can only leave through ``br13``, so ``br13 = −x``; ``br12 = 90``.
* ``br13`` out: ``br12 = 90 − x``, ``br23 = −x``.
* ``g3`` lost: the slack makes up the 90 MW, the plain single-source flows again.

Rate ``br13`` at 60 MVA and leave the two branches into the load bus unconstrained (100 MVA —
any outage of one of them puts the whole 90 MW load on the other, which no dispatch can change).
The base case is fine at ``x = 0`` (``br13 = 30``), but the ``br12`` outage needs ``90 − x <=
60``, i.e. ``x >= 30``, and the ``br23`` outage ``x <= 60``. The cheapest secure dispatch is
therefore ``g3 = 30``, ``g1 = 60``, cost ``10·60 + 20·30 = 1200`` against the plain OPF's 900, with
exactly one binding row — (``br12`` out, ``br13`` monitored) at ``60 == rating`` — found in two
solves: the first dispatch is screened, the one violated pair is added, the second passes.
Rating ``br13`` at 40 instead makes the two requirements ``x >= 50`` and ``x <= 40``: no
preventive dispatch exists, and the LP must say so — on the third solve, since each requirement
only surfaces once the previous dispatch violates it.
"""

from __future__ import annotations

import numpy as np
import pytest

from mambo_power import cases
from mambo_power.contingency.n1 import N1Options, confirm_n1, confirm_n1_generators, screen_n1
from mambo_power.jobs import SolveRequest, run
from mambo_power.model import Branch, Bus, Generator, Load, Network, PolynomialCost
from mambo_power.numerics import NetworkArrays, lodf, ptdf
from mambo_power.opf import ScopfOptions, gen_cost_coeffs, solve_dc_opf, solve_scopf
from mambo_power.opf.dc_opf import OpfDcOptions, dc_opf, lmp_decomposition
from mambo_power.opf.scopf import ITERATION_LIMIT, Contingency, scopf_dc, security_rows
from mambo_power.results import ScopfDcResult


def _gen(gen_id: str, bus: str, marginal_cost: float) -> Generator:
    return Generator(
        id=gen_id,
        bus=bus,
        p_mw=0.0,
        q_mvar=0.0,
        p_min_mw=0.0,
        p_max_mw=200.0,
        q_min_mvar=0.0,
        q_max_mvar=0.0,
        v_set_pu=1.0,
        cost=PolynomialCost(coefficients=[marginal_cost, 0.0]),
    )


def _triangle(*, br13_rating: float | None = 60.0) -> Network:
    return Network(
        base_mva=100.0,
        buses=[
            Bus(id="b1", base_kv=138.0, type="slack"),
            Bus(id="b2", base_kv=138.0, type="pq"),
            Bus(id="b3", base_kv=138.0, type="pv"),
        ],
        branches=[
            Branch(id="br12", from_bus="b1", to_bus="b2", r=0.0, x=0.1, b=0.0, rating_mva=100.0),
            Branch(
                id="br13", from_bus="b1", to_bus="b3", r=0.0, x=0.1, b=0.0, rating_mva=br13_rating
            ),
            Branch(id="br23", from_bus="b2", to_bus="b3", r=0.0, x=0.1, b=0.0, rating_mva=100.0),
        ],
        generators=[_gen("g1", "b1", 10.0), _gen("g3", "b3", 20.0)],
        loads=[Load(id="ld2", bus="b2", p_mw=90.0, q_mvar=0.0)],
    )


# --- the hand case ---------------------------------------------------------------------------


def test_triangle_secure_dispatch_matches_the_hand_derivation() -> None:
    result = solve_scopf(_triangle())

    assert result.status == "Optimal"
    assert result.secure is True
    assert result.iterations == 2
    assert {g.id: g.p_mw for g in result.generators} == {
        "g1": pytest.approx(60.0),
        "g3": pytest.approx(30.0),
    }
    assert result.base_objective_cost == pytest.approx(900.0)
    assert result.objective_cost == pytest.approx(1200.0)
    assert result.security_cost == pytest.approx(300.0)
    assert result.provenance.kind == "opf.scopf"

    binding = [c for c in result.constraints if abs(c.dual) > 1e-9]
    assert [(c.outage_kind, c.outage_id, c.branch_id) for c in binding] == [
        ("branch", "br12", "br13")
    ]
    assert binding[0].post_contingency_flow_mw == pytest.approx(60.0)
    assert binding[0].rating_mva == pytest.approx(60.0)
    for c in result.constraints:
        assert abs(c.post_contingency_flow_mw) <= c.rating_mva + 1e-6

    # the confirmation travels with the result: a real contingency.n1 of the secure dispatch
    assert result.n1 is not None
    assert not any(o.confirmed_violating for o in result.n1.outages)
    assert not any(o.confirmed_violating for o in result.n1.generator_outages)
    assert result.n1.slack_generator_ids == ["g1"]


def test_triangle_with_nothing_to_secure_is_the_plain_opf_in_one_solve() -> None:
    net = _triangle(br13_rating=None)

    result = solve_scopf(net)
    plain = solve_dc_opf(net)

    assert result.status == "Optimal" and result.secure is True
    assert result.iterations == 1
    assert result.constraints == []
    assert result.objective_cost == pytest.approx(plain.objective_cost)
    assert result.security_cost == pytest.approx(0.0)
    assert [g.p_mw for g in result.generators] == pytest.approx([g.p_mw for g in plain.generators])
    assert [b.lmp for b in result.buses] == pytest.approx([b.lmp for b in plain.buses])


def test_triangle_rated_too_tight_has_no_preventive_dispatch() -> None:
    result = solve_scopf(_triangle(br13_rating=40.0))

    assert result.status == "Infeasible"
    assert result.secure is False
    # solve 1 (x = 0) flags the br12 outage, solve 2 (x = 50) flags the br23 outage, solve 3
    # has both rows and no feasible x
    assert result.iterations == 3
    assert result.message is not None and "iteration 3" in result.message
    assert result.generators == [] and result.constraints == [] and result.n1 is None
    assert result.base_objective_cost == pytest.approx(900.0)
    assert result.objective_cost == 0.0


def test_triangle_binding_row_prices_the_lmps() -> None:
    """A binding post-contingency row is congestion like any other: the LMP at the bus whose
    injection relieves it (``b3``) differs from the slack's, and the energy term is uniform."""
    result = solve_scopf(_triangle())
    lmp = {b.id: b for b in result.buses}

    assert lmp["b1"].energy == lmp["b2"].energy == lmp["b3"].energy
    assert lmp["b1"].congestion == pytest.approx(0.0)
    assert lmp["b3"].congestion != pytest.approx(0.0, abs=1e-6)
    # the dear unit is marginal at b3, so its LMP is its own marginal cost
    assert lmp["b3"].lmp == pytest.approx(20.0)


# --- the array-level pieces -------------------------------------------------------------------


def test_security_rows_reproduce_the_screen_and_the_re_solve_on_case14_rated() -> None:
    """A security row's ``gen_coeffs @ dispatch + const`` is the post-contingency flow the N-1
    screen estimates and the DC re-solve confirms — for branch and for generator outages."""
    net = cases.load("derived/case14_rated")
    arr = NetworkArrays.from_network(net)
    ptdf_matrix = ptdf(arr)
    lodf_matrix = lodf(arr, ptdf_matrix)
    screen = screen_n1(arr, N1Options())
    pairs = [
        Contingency("branch", k, m)
        for k in screen.flagged_positions
        for m in screen.flagged_positions[k]
    ] + [
        Contingency("generator", g, m)
        for g in screen.gen_flagged_positions
        for m in screen.gen_flagged_positions[g]
    ]
    assert any(c.kind == "generator" for c in pairs)

    rows = security_rows(arr, ptdf_matrix, lodf_matrix, pairs)
    declared_mw = arr.gen_p_pu * arr.base_mva
    # the declared dispatch balances the load on case14 (the slack absorbs nothing), so the
    # declared per-generator output is the base case the screen used
    post = rows.gen_coeffs @ declared_mw + rows.const_mw

    confirmed = {
        ("branch", o.outage_branch_id, f.branch_id): f.confirmed_flow_mw
        for o in confirm_n1(net, arr, screen)
        for f in o.flagged_branches
    }
    confirmed.update(
        {
            ("generator", o.outage_generator_id, f.branch_id): f.confirmed_flow_mw
            for o in confirm_n1_generators(net, arr, screen)
            for f in o.flagged_branches
        }
    )
    for r, c in enumerate(pairs):
        outage_id = (arr.branch_ids if c.kind == "branch" else arr.gen_ids)[c.outage]
        assert abs(post[r]) == pytest.approx(
            confirmed[(c.kind, outage_id, arr.branch_ids[c.monitored])]
        )
        assert rows.rating_mw[r] == pytest.approx(arr.rating_pu[c.monitored] * arr.base_mva)


def test_dc_opf_without_security_rows_is_unchanged_and_prices_nothing_extra() -> None:
    net = cases.load("derived/case14_rated")
    arr = NetworkArrays.from_network(net)
    cost_coeffs, _ = gen_cost_coeffs(net, arr)

    sol = dc_opf(arr, cost_coeffs, OpfDcOptions())

    assert sol.duals is not None and sol.duals.security.size == 0
    with_none = lmp_decomposition(sol.duals, sol.ptdf, None)
    plain = lmp_decomposition(sol.duals, sol.ptdf)
    np.testing.assert_array_equal(with_none.lmp, plain.lmp)


def test_scopf_dc_iteration_limit_reports_the_last_dispatch_and_does_not_claim_security() -> None:
    net = cases.load("derived/case14_rated")
    arr = NetworkArrays.from_network(net)
    cost_coeffs, _ = gen_cost_coeffs(net, arr)

    stopped = scopf_dc(arr, cost_coeffs, ScopfOptions(max_iterations=1))

    assert stopped.status == ITERATION_LIMIT
    assert stopped.iterations == 1
    assert stopped.solution.status == "Optimal"  # the LP itself was fine; the loop was cut short
    assert stopped.message is not None and "max_iterations" in stopped.message
    assert stopped.screen is not None and stopped.screen.flagged_positions

    result = solve_scopf(net, ScopfOptions(max_iterations=1))
    assert result.status == ITERATION_LIMIT and result.secure is False and result.n1 is None


# --- a real network ---------------------------------------------------------------------------


def test_case14_rated_is_secured_at_a_cost_and_the_confirmation_agrees() -> None:
    net = cases.load("derived/case14_rated")

    result = solve_scopf(net)
    plain = solve_dc_opf(net)

    assert result.status == "Optimal" and result.secure is True
    assert 1 < result.iterations <= 10
    assert result.base_objective_cost == pytest.approx(plain.objective_cost)
    assert result.objective_cost > plain.objective_cost
    assert result.security_cost == pytest.approx(result.objective_cost - result.base_objective_cost)
    kinds = {c.outage_kind for c in result.constraints}
    assert kinds == {"branch", "generator"}
    assert {c.outage_kind for c in result.constraints if abs(c.dual) > 1e-9} == {
        "branch",
        "generator",
    }
    for c in result.constraints:
        assert abs(c.post_contingency_flow_mw) <= c.rating_mva + 1e-6
    assert result.n1 is not None
    assert result.n1.outages == [] and result.n1.generator_outages == []
    # the secure dispatch still balances the load exactly
    load_mw = sum(ld.p_mw for ld in net.loads)
    assert sum(g.p_mw for g in result.generators) == pytest.approx(load_mw)

    again = ScopfDcResult.model_validate_json(result.model_dump_json())
    assert again == result


def test_generator_outages_off_secures_branches_only() -> None:
    result = solve_scopf(cases.load("derived/case14_rated"), ScopfOptions(generator_outages=False))

    assert result.status == "Optimal" and result.secure is True
    assert {c.outage_kind for c in result.constraints} == {"branch"}
    assert result.n1 is not None and result.n1.generator_outages == []
    assert result.n1.slack_generator_ids == []
    assert result.provenance.options == {
        "generator_outages": False,
        "max_iterations": 25,
        "ac_check": False,
    }


def test_ac_check_attaches_a_feasibility_report_of_the_secure_dispatch() -> None:
    result = solve_scopf(cases.load("derived/case14_rated"), ScopfOptions(ac_check=True))

    assert result.status == "Optimal"
    assert result.ac_check is not None
    assert result.ac_check.converged is True


# --- the jobs kind ------------------------------------------------------------------------------


def test_jobs_opf_scopf_kind_runs_and_fails_structurally_when_infeasible() -> None:
    ok = run(SolveRequest(kind="opf.scopf", network=_triangle()))
    assert ok.status == "ok" and isinstance(ok.result, ScopfDcResult)
    assert ok.result.secure is True
    assert ok.provenance is not None and ok.provenance.kind == "opf.scopf"

    bad = run(SolveRequest(kind="opf.scopf", network=_triangle(br13_rating=40.0)))
    assert bad.status == "failed" and bad.result is None
    assert bad.error is not None and bad.error.code == "INFEASIBLE_LP"

    cut = run(
        SolveRequest(
            kind="opf.scopf",
            network=cases.load("derived/case14_rated"),
            options={"max_iterations": 1},
        )
    )
    assert cut.status == "failed" and cut.error is not None
    assert cut.error.code == "INFEASIBLE_LP" and ITERATION_LIMIT in cut.error.message
