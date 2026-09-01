"""Market clearing (epic Design §2 ``market/``): welfare-maximizing DC-OPF over generator costs
and load bids, decomposed into LMPs and settlement. Built directly on
:mod:`mambo_power.opf.dc_opf`/``lmp_decomposition`` per ADR-006's reuse seam.

Four entry points. Two share a shape at two horizons:
:func:`~mambo_power.market.nodal.solve_nodal` clears one period, and
:func:`~mambo_power.market.multiperiod.solve_multiperiod` clears a ``Scenario``'s whole horizon as
one coupled LP/QP with ramp coupling and storage; a one-period multiperiod clearing reproduces the
nodal one exactly (wave M5 AC-4). The third, :func:`~mambo_power.market.zonal.solve_zonal`, clears
one period at *zonal* granularity and then redispatches onto the real network, reporting what that
market design costs against the nodal optimum -- so it drives three solves rather than one, and
``solve_nodal`` is one of them. The fourth, :func:`~mambo_power.market.agents.solve_agents`, is the
first whose supply curve is *decided* rather than read from the network: generators bid through a
:class:`~mambo_power.market.strategy.Strategy`, round after round, and the market clears their
offers until the offer vector settles (wave M7).
"""

from mambo_power.market.agents import AgentSetError, MarketAgentsOptions, solve_agents
from mambo_power.market.multiperiod import MarketMultiperiodOptions, solve_multiperiod
from mambo_power.market.nodal import MarketNodalOptions, load_bid_coeffs, solve_nodal
from mambo_power.market.zonal import CorridorLimit, MarketZonalOptions, solve_zonal, zone_partition
from mambo_power.opf.dc_opf import MissingCostError, NonConcaveBidError, NonConvexCostError

__all__ = [
    "AgentSetError",
    "CorridorLimit",
    "MarketAgentsOptions",
    "MarketMultiperiodOptions",
    "MarketNodalOptions",
    "MarketZonalOptions",
    "MissingCostError",
    "NonConcaveBidError",
    "NonConvexCostError",
    "load_bid_coeffs",
    "solve_agents",
    "solve_multiperiod",
    "solve_nodal",
    "solve_zonal",
    "zone_partition",
]
