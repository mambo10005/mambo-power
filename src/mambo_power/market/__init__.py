"""Market clearing (epic Design §2 ``market/``): welfare-maximizing DC-OPF over generator costs
and load bids, decomposed into LMPs and settlement. Built directly on
:mod:`mambo_power.opf.dc_opf`/``lmp_decomposition`` per ADR-006's reuse seam.

Two entry points, the same shape at two horizons: :func:`~mambo_power.market.nodal.solve_nodal`
clears one period, and :func:`~mambo_power.market.multiperiod.solve_multiperiod` clears a
``Scenario``'s whole horizon as one coupled LP/QP with ramp coupling and storage. A one-period
multiperiod clearing reproduces the nodal one exactly (wave M5 AC-4).
"""

from mambo_power.market.multiperiod import MarketMultiperiodOptions, solve_multiperiod
from mambo_power.market.nodal import MarketNodalOptions, load_bid_coeffs, solve_nodal
from mambo_power.opf.dc_opf import NonConcaveBidError, NonConvexCostError

__all__ = [
    "MarketMultiperiodOptions",
    "MarketNodalOptions",
    "NonConcaveBidError",
    "NonConvexCostError",
    "load_bid_coeffs",
    "solve_multiperiod",
    "solve_nodal",
]
