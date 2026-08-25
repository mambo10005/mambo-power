"""Nodal-market clearing (epic Design §2 ``market/``): welfare-maximizing DC-OPF over generator
costs and load bids, decomposed into LMPs and settlement (wave M4 W4). Built directly on
:mod:`mambo_power.opf.dc_opf`/``lmp_decomposition`` per ADR-006's reuse seam.
"""

from mambo_power.market.nodal import MarketNodalOptions, solve_nodal
from mambo_power.opf.dc_opf import NonConcaveBidError, NonConvexCostError

__all__ = ["MarketNodalOptions", "NonConcaveBidError", "NonConvexCostError", "solve_nodal"]
