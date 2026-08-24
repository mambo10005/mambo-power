"""N-1 branch-contingency screening (epic Design §2 ``contingency/``).

The public entry point (:func:`n1`) takes a :class:`~mambo_power.model.Network` and returns a
typed :class:`~mambo_power.results.N1Result`; the array-level split
(:func:`mambo_power.contingency.n1.screen_n1`, :func:`mambo_power.contingency.n1.confirm_n1`)
mirrors :func:`mambo_power.pf.dc.solve` vs :func:`mambo_power.pf.solve_dc`. Branch outages only
this wave — generator-outage contingencies are an explicit carry-over (wave spec Not Doing).

Note: this module deliberately binds the name ``n1`` twice — the submodule
``mambo_power.contingency.n1`` (imported below for its array-level functions) and the network-
level function defined at the end of this file, which rebinds the package attribute ``n1`` to
itself. After import, ``mambo_power.contingency.n1`` is the function; code that wants the
submodule imports it directly (``from mambo_power.contingency.n1 import screen_n1``), as this
module itself does.
"""

from __future__ import annotations

import time
from datetime import UTC, datetime

import mambo_power
from mambo_power.contingency.n1 import N1Options, confirm_n1, screen_n1
from mambo_power.model import Network
from mambo_power.numerics import NetworkArrays
from mambo_power.pf import dc as pfdc
from mambo_power.results import N1Result, ResultProvenance

__all__ = ["N1Options", "n1"]


def n1(net: Network, options: N1Options | None = None) -> N1Result:
    """LODF-screen every outageable branch of *net*, then DC re-solve to confirm each flagged one.

    Builds the in-service :class:`~mambo_power.numerics.NetworkArrays`, runs
    :func:`mambo_power.contingency.n1.screen_n1` (the LODF fast screen against the network's own
    ``rating_mva``) then :func:`mambo_power.contingency.n1.confirm_n1` (the confirming DC
    re-solve, one right-hand side per flagged outage), and returns a provenance-stamped
    :class:`~mambo_power.results.N1Result`. *net* is not modified.
    """
    opts = options if options is not None else N1Options()
    started_at = datetime.now(UTC)
    clock = time.perf_counter()

    arr = NetworkArrays.from_network(net)
    screen = screen_n1(arr, opts)
    outages = confirm_n1(net, arr, screen)

    elapsed_s = time.perf_counter() - clock
    provenance = ResultProvenance(
        engine="mambo-power",
        version=mambo_power.__version__,
        kind="n1",
        solver=pfdc.SOLVER,
        started_at=started_at,
        elapsed_s=elapsed_s,
        options=opts.model_dump(),
    )
    bridge_branch_ids = [arr.branch_ids[p] for p in screen.bridge_positions]
    return N1Result(provenance=provenance, outages=outages, bridge_branch_ids=bridge_branch_ids)
