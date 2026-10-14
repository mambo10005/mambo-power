"""N-1 contingency screening (epic Design §2 ``contingency/``).

The public entry point (:func:`n1`) takes a :class:`~mambo_power.model.Network` and returns a
typed :class:`~mambo_power.results.N1Result`; the array-level split
(:func:`mambo_power.contingency.n1.screen_n1`, :func:`mambo_power.contingency.n1.confirm_n1`,
:func:`mambo_power.contingency.n1.confirm_n1_generators`) mirrors
:func:`mambo_power.pf.dc.solve` vs :func:`mambo_power.pf.solve_dc`. Branch outages are screened
by LODF, generator outages by the PTDF column of the generator's bus (ADR-015); both are
confirmed by a real DC re-solve.

:func:`n2` is the branch-pair counterpart (ADR-024): the generalised-LODF screen of every pair
of branch outages, confirmed the same way.

Note: this module deliberately binds the names ``n1`` and ``n2`` twice — the submodule
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
from mambo_power.contingency.n1 import N1Options, confirm_n1, confirm_n1_generators, screen_n1
from mambo_power.contingency.n2 import N2Options, confirm_n2, screen_n2
from mambo_power.model import Network
from mambo_power.numerics import NetworkArrays
from mambo_power.pf import dc as pfdc
from mambo_power.results import N1Result, N2Result, ResultProvenance

__all__ = ["N1Options", "N2Options", "n1", "n2"]


def n1(net: Network, options: N1Options | None = None) -> N1Result:
    """Screen every outageable branch and generator of *net*, then DC re-solve each flagged one.

    Builds the in-service :class:`~mambo_power.numerics.NetworkArrays`, runs
    :func:`mambo_power.contingency.n1.screen_n1` (the LODF fast screen for branch outages and,
    unless ``options.generator_outages`` is off, the PTDF fast screen for generator outages,
    both against the network's own ``rating_mva``) then
    :func:`mambo_power.contingency.n1.confirm_n1` and
    :func:`mambo_power.contingency.n1.confirm_n1_generators` (the confirming DC re-solves, one
    right-hand side per flagged outage), and returns a provenance-stamped
    :class:`~mambo_power.results.N1Result`. *net* is not modified.
    """
    opts = options if options is not None else N1Options()
    started_at = datetime.now(UTC)
    clock = time.perf_counter()

    arr = NetworkArrays.from_network(net)
    screen = screen_n1(arr, opts)
    outages = confirm_n1(net, arr, screen)
    generator_outages = confirm_n1_generators(net, arr, screen)

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
    slack_generator_ids = [arr.gen_ids[p] for p in screen.gen_slack_positions]
    return N1Result(
        provenance=provenance,
        outages=outages,
        bridge_branch_ids=bridge_branch_ids,
        generator_outages=generator_outages,
        slack_generator_ids=slack_generator_ids,
    )


def n2(net: Network, options: N2Options | None = None) -> N2Result:
    """Screen every pair of branch outages of *net* by the generalised LODF, then DC re-solve each
    flagged pair (ADR-024; :mod:`mambo_power.contingency.n2`).

    Pairs whose joint removal disconnects the network are reported as ``islanding_pairs`` rather
    than estimated; the confirming re-solves stop at ``options.max_confirmed_pairs`` and the
    result says so (``truncated``). *net* is not modified.
    """
    opts = options if options is not None else N2Options()
    started_at = datetime.now(UTC)
    clock = time.perf_counter()

    arr = NetworkArrays.from_network(net)
    screen = screen_n2(arr)
    outages, truncated = confirm_n2(net, arr, screen, max_pairs=opts.max_confirmed_pairs)

    provenance = ResultProvenance(
        engine="mambo-power",
        version=mambo_power.__version__,
        kind="n2",
        solver=pfdc.SOLVER,
        started_at=started_at,
        elapsed_s=time.perf_counter() - clock,
        options=opts.model_dump(),
    )
    return N2Result(
        provenance=provenance,
        outages=outages,
        islanding_pairs=[[arr.branch_ids[i], arr.branch_ids[j]] for i, j in screen.islanding],
        bridge_branch_ids=[arr.branch_ids[p] for p in screen.bridge_positions],
        n_pairs_screened=screen.n_pairs_screened,
        truncated=truncated,
    )
