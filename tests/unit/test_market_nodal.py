"""AC-4, AC-5, AC-8: ``market.nodal`` clearing -- settlement identity, price-taker reduction, and
per-branch flow rows (spec W4, design item 5).

Reuses the exact two-bus network ``m4-research.md`` §4.1 / S3's own AC-1 test in
``test_opf_dc_demand.py`` hand-derive (slack ``b1``/``g1`` linear cost 10, ``b2``/``g2`` linear
cost 50, one 20 MW-rated branch, load ``d1`` at ``b2``) -- but built through ``Generator.cost``/
``Load.bid``/``Scenario`` so ``solve_nodal`` (not ``dc_opf`` directly) is what's under test.
"""

from __future__ import annotations

import numpy as np
import pytest

from mambo_power.io import matpower
from mambo_power.market.nodal import MarketNodalOptions, solve_nodal
from mambo_power.model import (
    Branch,
    Bus,
    Generator,
    Load,
    LoadBid,
    Network,
    PiecewiseBid,
    PolynomialBid,
    PolynomialCost,
    Scenario,
)
from mambo_power.numerics.arrays import NetworkArrays
from mambo_power.opf import solve_dc_opf
from mambo_power.opf.dc_opf import OpfDcOptions, dc_opf
from mambo_power.pf import dc as pfdc
from mambo_power.results import MarketNodalResult, MarketZonalResult, OpfBranchFlowResult
from tests._bids import with_bids
from tests._fixtures import FIXTURES_DIR
from tests._rated import rated_network


def _two_bus_network(*, bid: LoadBid | None) -> Network:
    return Network(
        base_mva=100.0,
        buses=[
            Bus(id="b1", base_kv=138.0, type="slack"),
            Bus(id="b2", base_kv=138.0, type="pq"),
        ],
        branches=[
            Branch(id="br12", from_bus="b1", to_bus="b2", r=0.0, x=0.1, b=0.0, rating_mva=20.0),
        ],
        generators=[
            Generator(
                id="g1",
                bus="b1",
                p_mw=0,
                q_mvar=0,
                p_min_mw=0,
                p_max_mw=100,
                q_min_mvar=0,
                q_max_mvar=0,
                v_set_pu=1.0,
                cost=PolynomialCost(coefficients=[10.0, 0.0]),
            ),
            Generator(
                id="g2",
                bus="b2",
                p_mw=0,
                q_mvar=0,
                p_min_mw=0,
                p_max_mw=100,
                q_min_mvar=0,
                q_max_mvar=0,
                v_set_pu=1.0,
                cost=PolynomialCost(coefficients=[50.0, 0.0]),
            ),
        ],
        loads=[Load(id="d1", bus="b2", p_mw=100.0, q_mvar=0.0, bid=bid)],
    )


# 2-segment concave bid: marginal value 45 on [0,50], 20 on [50,100] (m4-research.md §4.1, the
# same points test_opf_dc_demand.py's AC-1 test uses).
D1_BID_POINTS = [(0.0, 0.0), (50.0, 2250.0), (100.0, 3250.0)]


# --- AC-4: settlement identity, proved not asserted by construction -----------------------------


def test_ac4_settlement_identity_holds_on_a_binding_flow_limit_network() -> None:
    net = _two_bus_network(bid=PiecewiseBid(points=D1_BID_POINTS))
    scenario = Scenario(network=net)

    result = solve_nodal(scenario, MarketNodalOptions())

    assert isinstance(result, MarketNodalResult)
    assert result.status == "Optimal"
    by_gen = {g.id: g.p_mw for g in result.generators}
    by_load = {ld.id: ld.p_mw for ld in result.loads}
    assert by_gen["g1"] == pytest.approx(20.0, abs=1e-6)
    assert by_gen["g2"] == pytest.approx(0.0, abs=1e-6)
    assert by_load["d1"] == pytest.approx(20.0, abs=1e-6)

    lmp_by_bus = {b.id: b.lmp for b in result.buses}
    assert lmp_by_bus["b1"] == pytest.approx(10.0, abs=1e-6)
    assert lmp_by_bus["b2"] == pytest.approx(45.0, abs=1e-6)

    # left side of the identity: solve_nodal's own payment/receipt/rent fields, computed
    # directly from dispatch and LMPs (results/market.py docstring) -- matches m4-research.md
    # §4.1's hand-KKT numbers exactly.
    assert result.total_load_payment == pytest.approx(900.0, abs=1e-4)
    assert result.total_generator_receipts == pytest.approx(200.0, abs=1e-4)
    assert result.congestion_rent == pytest.approx(700.0, abs=1e-4)

    # right side of the identity (-sum_k mu_k * flow_k), computed here independently via a
    # direct array-level dc_opf() call and its own PTDF/duals -- a different code path from
    # solve_nodal's payment/receipt subtraction above, so this is a real proof of the identity,
    # not a restatement of solve_nodal's own arithmetic.
    arr = NetworkArrays.from_network(net)
    d1 = arr.load_ids.index("d1")
    coeffs = np.array([[0.0, 10.0, 0.0], [0.0, 50.0, 0.0]])
    solution = dc_opf(arr, coeffs, OpfDcOptions(), demand_pwl_bids={d1: D1_BID_POINTS})
    assert solution.status == "Optimal"
    assert solution.duals is not None
    gen_by_bus = np.bincount(arr.gen_bus, weights=solution.dispatch_mw, minlength=arr.n_bus)
    load_by_bus = np.zeros(arr.n_bus)
    load_by_bus[arr.load_bus[d1]] = solution.demand_dispatch_mw[0]
    injection_mw = gen_by_bus - load_by_bus
    flows_mw = solution.ptdf @ injection_mw
    congestion_rent_rhs = float(-solution.duals.flow_limit @ flows_mw)
    assert congestion_rent_rhs == pytest.approx(700.0, abs=1e-4)
    assert congestion_rent_rhs == pytest.approx(result.congestion_rent, abs=1e-4)


def test_ac4_dispatch_and_lmp_rows_are_id_keyed_and_cover_every_generator_and_load() -> None:
    net = _two_bus_network(bid=PiecewiseBid(points=D1_BID_POINTS))
    result = solve_nodal(Scenario(network=net))
    assert {g.id for g in result.generators} == {"g1", "g2"}
    assert {ld.id for ld in result.loads} == {"d1"}
    assert {b.id for b in result.buses} == {"b1", "b2"}
    d1 = next(ld for ld in result.loads if ld.id == "d1")
    # d1 sits at 20 MW (branch-limited), an interior point of its own [0, 100] bid bound -- not
    # pinned at either end of it, so its bound reduced cost is 0 (the binding constraint here is
    # the branch's flow limit, whose dual shows up in bus b2's LMP congestion component instead).
    assert d1.bound_dual == 0.0


# --- AC-5: price-taker reduction, the wave's main correctness test ------------------------------


def test_ac5_price_taker_reduction_matches_plain_opf_dc_opf() -> None:
    """d1's bid marginal value (1000, constant/linear) exceeds every achievable price (the
    highest generator's marginal cost, 50) at every quantity up to d1's own fixed historical
    demand (100 MW) -- the precise condition m4-research.md §4.2 states. Per that condition,
    d1 is pinned exactly at 100 MW and solve_nodal's dispatch/duals/LMPs must be identical to
    opf.solve_dc_opf called on the same network with d1 fixed (no bid) -- reducing to M3's own
    already-oracle-proved opf.dc_opf parity.
    """
    elastic_net = _two_bus_network(bid=PolynomialBid(coefficients=[1000.0, 0.0]))
    fixed_net = _two_bus_network(bid=None)

    market_result = solve_nodal(Scenario(network=elastic_net), MarketNodalOptions())
    opf_result = solve_dc_opf(fixed_net, OpfDcOptions())

    assert market_result.status == "Optimal"
    assert opf_result.status == "Optimal"

    d1 = next(ld for ld in market_result.loads if ld.id == "d1")
    assert d1.p_mw == pytest.approx(100.0, abs=1e-6)  # pinned at its own fixed historical demand
    assert d1.bound_dual != 0.0

    by_gen_market = {g.id: g.p_mw for g in market_result.generators}
    by_gen_opf = {g.id: g.p_mw for g in opf_result.generators}
    assert by_gen_market == pytest.approx(by_gen_opf, abs=1e-6)

    bound_dual_market = {g.id: g.bound_dual for g in market_result.generators}
    bound_dual_opf = {g.id: g.bound_dual for g in opf_result.generators}
    assert bound_dual_market == pytest.approx(bound_dual_opf, abs=1e-6)

    lmp_market = {b.id: b.lmp for b in market_result.buses}
    lmp_opf = {b.id: b.lmp for b in opf_result.buses}
    assert lmp_market == pytest.approx(lmp_opf, abs=1e-6)

    congestion_market = {b.id: b.congestion for b in market_result.buses}
    congestion_opf = {b.id: b.congestion for b in opf_result.buses}
    assert congestion_market == pytest.approx(congestion_opf, abs=1e-6)


# --- AC-8: MarketNodalResult carries OpfBranchFlowResult rows, symmetrically with MarketZonalResult


PF_DC_FLOW_TOL_MW = 1e-9
"""Absolute tolerance, MW, for ``MarketNodalResult.branches[*].p_from_mw`` against an independent
``pf.dc`` readback of the same dispatch. Reuses ``tests/unit/test_opf_redispatch.py``'s own pin
for the identical claim (``RedispatchSolution.branch_flow_mw`` vs. ``pf.dc``) rather than
inventing a second number for one comparison -- both constructions are the same PTDF-times-
injection formula (module docstring, ``opf/dc_opf.py``'s flow-limit-row derivation) evaluated
through two independent code paths (the LP's own PTDF multiply here, ``scipy.sparse.linalg.splu``
over ``B'`` in ``pf.dc``), so both residuals are pure floating-point noise, not modelling slack.
Measured here: 0.0 MW on the two-bus fixture, 7.99e-14 MW (sup-norm) on rated case14 with bids --
four orders below this pin."""


def test_ac8_branch_flows_match_an_independent_pf_dc_readback_on_the_two_bus_fixture() -> None:
    """``MarketNodalResult.branches[*].p_from_mw`` is the flow ``pf.dc`` computes at the same
    dispatch (generators *and* the elastic load's solved quantity) -- proved through a code path
    that shares nothing with ``solve_nodal``'s own PTDF-injection construction except the network
    and the dispatch it produced."""
    net = _two_bus_network(bid=PiecewiseBid(points=D1_BID_POINTS))
    result = solve_nodal(Scenario(network=net), MarketNodalOptions())
    assert result.status == "Optimal"

    out = net.model_copy(deep=True)
    dispatch_by_id = {g.id: g.p_mw for g in result.generators}
    demand_by_id = {ld.id: ld.p_mw for ld in result.loads}
    for gen in out.generators:
        gen.p_mw = dispatch_by_id[gen.id]
    for load in out.loads:
        load.p_mw = demand_by_id[load.id]
    arr = NetworkArrays.from_network(out)
    expected = pfdc.solve(arr).p_from_pu * arr.base_mva

    branch_flow = {b.id: b.p_from_mw for b in result.branches}
    assert branch_flow.keys() == {"br12"}
    assert [branch_flow["br12"]] == pytest.approx(expected, abs=PF_DC_FLOW_TOL_MW)


def test_ac8_branch_flows_match_an_independent_pf_dc_readback_on_a_rated_multi_branch_network() -> (
    None
):
    """The same claim as above, on rated case14 with a mix of price-taking and interior bid loads
    (``tests/_rated.py`` / ``tests/_bids.py``, this repo's own fixture-derivation tradition) --
    multiple branches, several of them rating-bound, rather than the one-branch hand fixture."""
    base = rated_network(matpower.load(FIXTURES_DIR / "case14.m"))
    load_ids = [ld.id for ld in base.loads if ld.p_mw > 0][:3]
    net = with_bids(base, load_ids, interior_load_ids=load_ids[:1])
    result = solve_nodal(Scenario(network=net), MarketNodalOptions())
    assert result.status == "Optimal"
    assert result.branches, "case14 has branches; an empty list would make this test vacuous"

    out = net.model_copy(deep=True)
    dispatch_by_id = {g.id: g.p_mw for g in result.generators}
    demand_by_id = {ld.id: ld.p_mw for ld in result.loads}
    for gen in out.generators:
        gen.p_mw = dispatch_by_id[gen.id]
    for load in out.loads:
        load.p_mw = demand_by_id[load.id]
    arr = NetworkArrays.from_network(out)
    expected_by_id = {
        branch_id: float(pfdc.solve(arr).p_from_pu[k] * arr.base_mva)
        for k, branch_id in enumerate(arr.branch_ids)
    }

    branch_flow = {b.id: b.p_from_mw for b in result.branches}
    assert branch_flow.keys() == expected_by_id.keys()
    for branch_id, expected_mw in expected_by_id.items():
        assert branch_flow[branch_id] == pytest.approx(expected_mw, abs=PF_DC_FLOW_TOL_MW)


def test_ac8_nodal_and_zonal_expose_branches_under_the_same_field_name_and_row_type() -> None:
    """W4/AC-8: ``MarketNodalResult`` gains ``OpfBranchFlowResult`` rows under the **same** field
    name ``MarketZonalResult`` already carries them under -- asserted structurally against both
    models' own field metadata, not just observed by reading two docstrings side by side."""
    assert "branches" in MarketNodalResult.model_fields
    assert "branches" in MarketZonalResult.model_fields
    nodal_branches_type = MarketNodalResult.model_fields["branches"].annotation
    zonal_branches_type = MarketZonalResult.model_fields["branches"].annotation
    assert nodal_branches_type == zonal_branches_type == list[OpfBranchFlowResult]


def test_ac8_branch_rows_are_id_keyed_and_carry_the_flow_limit_dual() -> None:
    """Every branch gets a row, keyed by its own id, carrying both the flow and the flow-limit
    row's shadow price -- the two figures the settlement identity's flow-dual side needs
    (``-sum_k mu_k * f_k``), both readable from this object alone."""
    net = _two_bus_network(bid=PiecewiseBid(points=D1_BID_POINTS))
    result = solve_nodal(Scenario(network=net))
    assert {b.id for b in result.branches} == {"br12"}
    br12 = next(b for b in result.branches if b.id == "br12")
    assert br12.from_bus == "b1"
    assert br12.to_bus == "b2"
    assert br12.p_from_mw == pytest.approx(20.0, abs=1e-6)  # the branch is rating-bound (AC-4)
    # -sum_k(mu_k * flow_k) reproduces congestion_rent (already proved as an identity above);
    # here it is just the sign/magnitude of this one row's own dual, read directly.
    assert br12.flow_limit_dual == pytest.approx(-35.0, abs=1e-6)


# --- The rows and settlement are one construction, shared with market.agents (M7 S11) ------------


@pytest.mark.parametrize(
    "net",
    [
        matpower.load(FIXTURES_DIR / "case14.m"),
        _two_bus_network(bid=PiecewiseBid(points=D1_BID_POINTS)),
        with_bids(rated_network(matpower.load(FIXTURES_DIR / "case14.m"))),
    ],
    ids=["case14", "two-bus-pwl-bid", "rated-case14-with-bids"],
)
def test_nodal_and_agent_less_agents_rows_and_settlement_are_identical(net: Network) -> None:
    """``solve_nodal`` and ``solve_agents`` with nobody bidding strategically build their
    generator, load and branch rows and their two settlement totals through one shared
    helper (``market/_clearing.py``, critic finding 4). Equal by ``==`` on the row models and
    the floats -- not ``approx`` -- because the two solvers clear the same LP with the same
    coefficients and then apply the same construction; anything short of identity would mean
    a second copy had crept back in."""
    from mambo_power.market.agents import MarketAgentsOptions, solve_agents

    nodal = solve_nodal(Scenario(network=net), MarketNodalOptions())
    agents = solve_agents(Scenario(network=net), MarketAgentsOptions(max_iterations=5))
    assert nodal.status == agents.status == "Optimal"
    assert nodal.generators == agents.generators
    assert nodal.loads == agents.loads
    assert nodal.branches == agents.branches
    assert nodal.buses == agents.buses
    assert nodal.total_load_payment == agents.total_load_payment
    assert nodal.total_generator_receipts == agents.total_generator_receipts
    assert nodal.congestion_rent == agents.congestion_rent
