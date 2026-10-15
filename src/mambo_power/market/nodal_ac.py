"""``market.nodal_ac`` clearing (ADR-031): the nodal market at AC physics.

:func:`solve_nodal_ac` is to :func:`mambo_power.opf.solve_ac_opf` what
:func:`~mambo_power.market.nodal.solve_nodal` is to :func:`mambo_power.opf.solve_dc_opf`: it
clears ``scenario.network``'s generator costs against its load bids — the AC-OPF with
``elastic_demand`` on (ADR-030) — and settles the result at the AC LMPs. Where the DC market's
price is energy plus congestion, the AC price carries losses and voltage support as well, so a
load's payment and a generator's receipt differ even on an uncongested network and the
difference is a rent the market design must account for.

**Settlement.** With \\(\\lambda_i\\) the active LMP at bus \\(i\\) (the P-balance dual):

* ``total_load_payment`` — \\(\\sum_d \\lambda(bus_d) \\cdot p_d\\) over every load, served
  demand (a bid load's dispatch, a fixed load's ``p_mw``);
* ``total_generator_receipts`` — \\(\\sum_g \\lambda(bus_g) \\cdot p_g\\);
* ``merchandising_surplus`` — the difference, what the market operator collects. In the DC
  market this is the congestion rent alone; here it is the **loss rent plus the congestion
  rent**: marginal-cost pricing of losses over-recovers them (the marginal loss factor is about
  twice the average), and a binding apparent-power limit adds its rent as before. On a lossless
  uncongested network it is zero, which ``tests/unit/test_market_nodal_ac.py`` checks.

Reactive power is settled too, at \\(\\lambda^q_i\\) (the Q-balance dual, 0 wherever reactive
support is free): ``total_reactive_payment`` and ``total_reactive_receipts``, the same sums
over ``q_mvar``. They are reported, not folded into the active surplus.

No decomposition of the AC LMP into energy, loss and congestion components is reported: unlike
the DC price's PTDF decomposition it is not unique (it depends on the reference bus chosen for
the loss factors), and the settlement above does not need it.
"""

from __future__ import annotations

import time
from datetime import UTC, datetime

import numpy as np
from pydantic import BaseModel, ConfigDict, Field

import mambo_power
from mambo_power.model import Scenario
from mambo_power.opf import OpfAcOptions, solve_ac_opf
from mambo_power.opf.dc_opf import NonConcaveBidError, NonConvexCostError
from mambo_power.results import BusLmpAcResult, MarketNodalAcResult, ResultProvenance

__all__ = [
    "MarketNodalAcOptions",
    "NonConcaveBidError",
    "NonConvexCostError",
    "solve_nodal_ac",
]


class MarketNodalAcOptions(BaseModel):
    """Options of a ``market.nodal_ac`` clearing: the AC-OPF's own, with elastic demand on."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    opf: OpfAcOptions = Field(
        default_factory=OpfAcOptions,
        description="Solver options of the underlying AC-OPF (tolerances, step budget, "
        "default voltage band). Its elastic_demand flag is ignored: a market clearing always "
        "honours the bids.",
    )


def solve_nodal_ac(
    scenario: Scenario, options: MarketNodalAcOptions | None = None
) -> MarketNodalAcResult:
    """Welfare-maximising AC-OPF of ``scenario.network`` (module docstring): dispatch with
    reactive power, every load's served demand, AC LMPs and the settlement at them.

    Never raises for a run that does not converge — reported through
    ``MarketNodalAcResult.status``/``message`` like :func:`mambo_power.opf.solve_ac_opf`. Raises
    :class:`~mambo_power.opf.dc_opf.NonConvexCostError` and
    :class:`~mambo_power.opf.dc_opf.NonConcaveBidError` up front. The network is not modified.
    """
    opts = options if options is not None else MarketNodalAcOptions()
    started_at = datetime.now(UTC)
    clock = time.perf_counter()
    opf_options = opts.opf.model_copy(update={"elastic_demand": True})
    ac = solve_ac_opf(scenario.network, opf_options)
    provenance = ResultProvenance(
        engine="mambo-power",
        version=mambo_power.__version__,
        kind="market.nodal_ac",
        solver=ac.provenance.solver,
        started_at=started_at,
        elapsed_s=time.perf_counter() - clock,
        options=opts.model_dump(),
    )
    if ac.status != "Optimal":
        return MarketNodalAcResult(
            provenance=provenance, status=ac.status, message=ac.message, iterations=ac.iterations
        )

    lmp = {b.id: b.lmp_p for b in ac.buses}
    lmp_q = {b.id: b.lmp_q for b in ac.buses}
    payment = float(np.sum([lmp[ld.bus] * ld.p_mw for ld in ac.loads]))
    receipts = float(np.sum([lmp[g.bus] * g.p_mw for g in ac.generators]))
    reactive_payment = float(np.sum([lmp_q[ld.bus] * ld.q_mvar for ld in ac.loads]))
    reactive_receipts = float(np.sum([lmp_q[g.bus] * g.q_mvar for g in ac.generators]))
    buses = [
        BusLmpAcResult(id=b.id, lmp=b.lmp_p, lmp_q=b.lmp_q, vm_pu=b.vm_pu, va_deg=b.va_deg)
        for b in ac.buses
    ]
    return MarketNodalAcResult(
        provenance=provenance,
        status=ac.status,
        message=None,
        iterations=ac.iterations,
        objective_cost=ac.objective_cost,
        demand_value=ac.demand_value,
        losses_mw=ac.losses_mw,
        generators=ac.generators,
        loads=ac.loads,
        buses=buses,
        branches=ac.branches,
        total_load_payment=payment,
        total_generator_receipts=receipts,
        merchandising_surplus=payment - receipts,
        total_reactive_payment=reactive_payment,
        total_reactive_receipts=reactive_receipts,
    )
