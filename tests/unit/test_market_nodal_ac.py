"""``market.nodal_ac`` (ADR-031): the nodal market cleared at AC physics and settled at AC LMPs.

The clearing itself is the elastic AC-OPF (ADR-030), whose oracles live in
``test_opf_ac_elastic_demand.py`` and the pandapower parity tier; what is checked here is the
market layer on top of it:

* **The rows are the AC-OPF's** — same dispatch, same served demand, same prices — so the market
  adds settlement and nothing else.
* **Settlement arithmetic**, recomputed here from the rows: payment, receipts and their
  difference; the reactive sums likewise.
* **The surplus is the loss and congestion rent**: zero on a lossless, uncongested network
  (uniform LMPs), positive on the lossy two-bus case even with nothing congested, and — on a
  lossless network with one binding rating — equal to the DC market's congestion rent on the
  same problem, because with no losses and no reactive flow the AC and DC clearings coincide.
* **The option plumbing**: the AC-OPF options pass through with ``elastic_demand`` forced on;
  the ``market.nodal_ac`` job runs, carries its options in the provenance, and a non-converged
  solve is a structured failure like ``opf.ac``'s.
"""

from __future__ import annotations

import pytest

from mambo_power import cases
from mambo_power.jobs import SolveRequest, run
from mambo_power.market import MarketNodalAcOptions, solve_nodal, solve_nodal_ac
from mambo_power.model import Network, PolynomialBid, Scenario
from mambo_power.opf import OpfAcOptions, solve_ac_opf
from mambo_power.opf.dc_opf import NonConcaveBidError
from mambo_power.results import MarketNodalAcResult
from tests.unit.test_opf_ac import LOAD_P, _two_bus


def _case14_with_bids(value: float = 38.0, count: int = 3) -> Network:
    net = cases.load("case14")
    for load in net.loads[:count]:
        load.bid = PolynomialBid(coefficients=[value, 0.0])
    return net


def _lossless_two_bus(**kwargs: float) -> Network:
    net = _two_bus(**kwargs)
    net.branches[0].r = 0.0
    net.branches[0].b = 0.0
    return net


def test_the_rows_are_the_elastic_ac_opf_s() -> None:
    net = _case14_with_bids()
    market = solve_nodal_ac(Scenario(network=net))
    opf = solve_ac_opf(net, OpfAcOptions(elastic_demand=True))

    assert market.status == "Optimal", market.message
    assert market.generators == opf.generators
    assert market.loads == opf.loads
    assert market.branches == opf.branches
    assert [(b.id, b.lmp, b.lmp_q) for b in market.buses] == [
        (b.id, b.lmp_p, b.lmp_q) for b in opf.buses
    ]
    assert market.objective_cost == opf.objective_cost
    assert market.demand_value == opf.demand_value
    assert market.losses_mw == opf.losses_mw
    assert market.iterations == opf.iterations
    assert market.provenance.kind == "market.nodal_ac"
    assert any(ld.elastic for ld in market.loads)


def test_settlement_is_recomputed_from_the_rows() -> None:
    market = solve_nodal_ac(Scenario(network=_case14_with_bids()))
    lmp = {b.id: b.lmp for b in market.buses}
    lmp_q = {b.id: b.lmp_q for b in market.buses}
    payment = sum(lmp[ld.bus] * ld.p_mw for ld in market.loads)
    receipts = sum(lmp[g.bus] * g.p_mw for g in market.generators)
    assert market.total_load_payment == pytest.approx(payment)
    assert market.total_generator_receipts == pytest.approx(receipts)
    assert market.merchandising_surplus == pytest.approx(payment - receipts)
    assert market.total_reactive_payment == pytest.approx(
        sum(lmp_q[ld.bus] * ld.q_mvar for ld in market.loads)
    )
    assert market.total_reactive_receipts == pytest.approx(
        sum(lmp_q[g.bus] * g.q_mvar for g in market.generators)
    )
    assert market.merchandising_surplus > 0.0  # losses are priced at the margin: a rent


def test_a_lossless_uncongested_network_has_one_price_and_no_surplus() -> None:
    market = solve_nodal_ac(Scenario(network=_lossless_two_bus()))
    assert market.status == "Optimal", market.message
    prices = [b.lmp for b in market.buses]
    assert prices == pytest.approx([10.0, 10.0], abs=1e-6)
    assert market.merchandising_surplus == pytest.approx(0.0, abs=1e-6)
    assert market.losses_mw == pytest.approx(0.0, abs=1e-9)
    (load,) = market.loads
    assert not load.elastic and load.p_mw == LOAD_P


def test_lossy_but_uncongested_the_surplus_is_the_loss_rent() -> None:
    market = solve_nodal_ac(Scenario(network=_two_bus()))
    assert market.status == "Optimal", market.message
    assert all(b.flow_from_dual == 0.0 and b.flow_to_dual == 0.0 for b in market.branches)
    lmp = {b.id: b.lmp for b in market.buses}
    assert lmp["b2"] > lmp["b1"]  # the delivered MW costs its losses
    # the surplus is the load's price premium over what its generation earned
    assert market.merchandising_surplus == pytest.approx(
        lmp["b2"] * LOAD_P - lmp["b1"] * market.generators[0].p_mw
    )
    assert market.merchandising_surplus > 0.0
    # marginal-loss pricing over-recovers: the surplus exceeds the cost of the losses themselves
    assert market.merchandising_surplus > 10.0 * market.losses_mw


def test_lossless_and_congested_the_surplus_is_the_dc_congestion_rent() -> None:
    net = _lossless_two_bus(dear_cost=30.0)
    net.branches[0].rating_mva = 60.0  # the cheap unit can only send 60 of the 100 MW
    scenario = Scenario(network=net)
    ac = solve_nodal_ac(scenario)
    dc = solve_nodal(scenario)
    assert ac.status == "Optimal" and dc.status == "Optimal"
    (branch,) = ac.branches
    assert branch.s_from_mva == pytest.approx(60.0, abs=1e-4) or branch.s_to_mva == pytest.approx(
        60.0, abs=1e-4
    )
    assert ac.merchandising_surplus == pytest.approx(dc.congestion_rent, rel=1e-3)
    assert ac.merchandising_surplus == pytest.approx(20.0 * 60.0, rel=1e-3)  # (30 − 10) × 60
    assert [b.lmp for b in ac.buses] == pytest.approx([10.0, 30.0], abs=1e-3)


def test_options_pass_through_with_elastic_demand_forced_on() -> None:
    options = MarketNodalAcOptions(opf=OpfAcOptions(elastic_demand=False, max_iter=300))
    market = solve_nodal_ac(Scenario(network=_case14_with_bids()), options)
    assert market.status == "Optimal"
    assert any(ld.elastic for ld in market.loads)  # the flag was overridden
    assert market.provenance.options == {"opf": options.opf.model_dump()}
    assert market.provenance.options["opf"]["max_iter"] == 300

    with pytest.raises(NonConcaveBidError):
        net = _two_bus()
        net.loads[0].bid = PolynomialBid(coefficients=[0.1, 20.0, 0.0])
        solve_nodal_ac(Scenario(network=net))


def test_result_round_trips_and_the_job_runs_and_fails_structurally() -> None:
    net = _case14_with_bids(count=2)
    market = solve_nodal_ac(Scenario(network=net))
    assert MarketNodalAcResult.model_validate_json(market.model_dump_json()) == market

    ok = run(SolveRequest(kind="market.nodal_ac", scenario=Scenario(network=net)))
    assert ok.status == "ok" and isinstance(ok.result, MarketNodalAcResult)
    assert ok.result.total_load_payment == pytest.approx(market.total_load_payment)

    cut = run(
        SolveRequest(
            kind="market.nodal_ac",
            network=net,
            options={"opf": {"max_iter": 2}},
        )
    )
    assert cut.status == "failed" and cut.error is not None
    assert cut.error.code == "INFEASIBLE_LP" and "IterationLimit" in cut.error.message

    bad = run(SolveRequest(kind="market.nodal_ac", network=net, options={"tol": 1e-6}))
    assert bad.status == "failed" and bad.error is not None and bad.error.code == "BAD_OPTIONS"
