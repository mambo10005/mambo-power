"""``market.multiperiod`` clearing result: per-period dispatch, LMPs and settlement, per-storage
charge/discharge/SoC, and horizon totals.

The multiperiod sibling of :mod:`mambo_power.results.market`, and shaped the same way: id-keyed
rows plus :class:`~mambo_power.results.provenance.ResultProvenance`, never attached to a
:class:`~mambo_power.model.Network`. :class:`~mambo_power.results.market.LoadDispatchResult` and
:class:`~mambo_power.results.opf.BusLmpResult` are reused **verbatim** (ADR-006's reuse
discipline); only the per-period container, the storage row and the generator row's one extra
field are new.

**The settlement identity this result reports, and where storage sits in it.** ``market.nodal``
proved, per solve, that total load payment minus total generator receipts equals the congestion
rent ``-sum_k(mu_k * flow_k)``. A storage unit injects *and* withdraws at a bus, so it is a
third settlement participant: it pays ``LMP * charge_mw`` and is paid ``LMP * discharge_mw``, and
the identity does **not** close if a dispatched unit is left unsettled -- it is then wrong by
exactly the unit's net revenue, which is the whole of its arbitrage profit. So the identity this
module claims, and which ``tests/unit/test_market_multiperiod.py`` proves per period with the
right-hand side computed by a separate code path, is::

    load_payment + storage_charge_payment - generator_receipts - storage_discharge_revenue
        == -sum_k(mu_k * f_k) + sum_k(mu_k * pf_shift_k) - sum_n(LMP_n * g_shunt_n)

The two trailing terms are the general form's corrections for phase-shifting transformers and
for bus shunt conductance -- both fixed, unsettled withdrawals from the network itself rather
than from a market participant. They are exactly zero on every MATPOWER fixture this repository
ships except ``case300``, whose ``g_shunt`` is non-zero; ``market.nodal``'s M4-era statement of
the identity omitted them and was correct only because its own fixtures had none.

Every quantity is per period: nothing here is a horizon average. ``$/h`` figures are that
period's rate, and the horizon totals on :class:`MarketMultiperiodResult` are their plain sum,
which is an energy-weighted total only because every period is one hour long (the wave carries
no period-duration field).
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from mambo_power.results.market import LoadDispatchResult
from mambo_power.results.opf import BusLmpResult, GenDispatchResult
from mambo_power.results.provenance import ResultProvenance


class GenPeriodDispatchResult(GenDispatchResult):
    """One generator's dispatch in one period, plus the ramp row that reaches into that period.

    Extends :class:`~mambo_power.results.opf.GenDispatchResult` rather than replacing it: ``id``,
    ``bus``, ``p_mw`` and ``bound_dual`` mean exactly what they mean in a single-period DC-OPF
    result, so a reader who knows one knows the other.
    """

    ramp_dual: float = Field(
        default=0.0,
        description="Dual of the two-sided ramp row coupling the *previous* period to this one, "
        "$/MWh: negative when the ramp-up side binds, positive when the ramp-down side does. "
        "0.0 in period 0 (no row reaches into it) and for any generator whose ramp_up_mw and "
        "ramp_down_mw are both None (no row is built at all).",
    )


class StorageDispatchResult(BaseModel):
    """One storage unit's charge, discharge and state of charge in one period.

    ``charge_mw`` and ``discharge_mw`` are both nonnegative and are separate columns of the LP,
    not two signs of one column: the charge and discharge efficiencies enter the SoC balance row
    with different coefficients, an asymmetry a single signed column cannot express (see
    :mod:`mambo_power.opf.multiperiod`). Simultaneous charge *and* discharge is therefore
    representable and is bounded rather than banned, so both fields can be non-zero at once --
    rare, but real on a network where forbidding it would make the problem infeasible.
    """

    model_config = ConfigDict(extra="forbid", frozen=True, allow_inf_nan=False)

    id: str = Field(description="Storage id from the network.")
    bus: str = Field(description="Bus id the unit is connected to.")
    charge_mw: float = Field(description="Charging power in this period, MW; >= 0.")
    discharge_mw: float = Field(description="Discharging power in this period, MW; >= 0.")
    soc_mwh: float = Field(description="State of charge at the *end* of this period, MWh.")
    soc_dual: float = Field(
        description="Dual of the unit's SoC balance row for this period, $/MWh, in the solver's "
        "own row-dual sign: the *negative* of the marginal value of stored energy, so it is "
        "negative wherever one more MWh in this unit is worth having (-LMP/efficiency_charge "
        "while the unit charges on an interior column, -efficiency_discharge*LMP while it "
        "discharges on one). The worth of an MWh is -soc_dual."
    )
    energy_bound_dual: float = Field(
        description="Reduced cost of the unit's [0, energy_mwh] state-of-charge bound, non-zero "
        "at either end of it: a unit sitting empty binds that bound as much as a unit sitting "
        "full. 0 only when the state of charge is strictly between the two."
    )
    power_limit_dual: float = Field(
        description="Dual of the shared charge + discharge <= p_max_mw row; 0 unless the unit's "
        "combined throughput is at its converter rating."
    )


class MarketPeriodResult(BaseModel):
    """One period of a :func:`mambo_power.market.multiperiod.solve_multiperiod` horizon.

    Carries the same four things ``market.nodal`` reports for a single solve -- generator
    dispatch, every load's served demand, per-bus LMPs, settlement -- plus the storage rows a
    single-period clearing has no place for. The settlement identity (module docstring) holds on
    **this** object, period by period; the horizon totals above it are a convenience sum, not the
    level at which the identity is claimed.
    """

    model_config = ConfigDict(extra="forbid", frozen=True, allow_inf_nan=False)

    period: int = Field(description="Zero-based index of this period within the horizon.")
    generators: list[GenPeriodDispatchResult] = Field(default_factory=list)
    loads: list[LoadDispatchResult] = Field(default_factory=list)
    buses: list[BusLmpResult] = Field(default_factory=list)
    storage: list[StorageDispatchResult] = Field(default_factory=list)
    total_load_payment: float = Field(
        default=0.0,
        description="Sum over every load of LMP(bus_d)*p_d in this period, $/h.",
    )
    total_generator_receipts: float = Field(
        default=0.0,
        description="Sum over every generator of LMP(bus_g)*p_g in this period, $/h.",
    )
    total_storage_charge_payment: float = Field(
        default=0.0,
        description="Sum over every storage unit of LMP(bus_s)*charge_mw, $/h -- what storage "
        "pays the market for the energy it stores. 0.0 with no storage.",
    )
    total_storage_discharge_revenue: float = Field(
        default=0.0,
        description="Sum over every storage unit of LMP(bus_s)*discharge_mw, $/h -- what the "
        "market pays storage for the energy it returns. 0.0 with no storage.",
    )
    congestion_rent: float = Field(
        default=0.0,
        description="(load payment + storage charge payment) - (generator receipts + storage "
        "discharge revenue), $/h: the market operator's merchandising surplus for this period, "
        "computed directly from prices and quantities and never asserted equal to the "
        "identity's flow-dual side by construction. It is congestion rent *proper* -- exactly "
        "-sum_k(mu_k * f_k) -- on a network with no bus shunt conductance and no phase-shifting "
        "transformer; where either exists the surplus also carries that unsettled withdrawal, "
        "and the module docstring gives the full identity.",
    )


class MarketMultiperiodResult(BaseModel):
    """Result of :func:`mambo_power.market.multiperiod.solve_multiperiod`.

    When ``status != "Optimal"`` ``periods`` is empty and every total is left at zero;
    ``message`` carries the diagnostic, mirroring
    :class:`~mambo_power.results.MarketNodalResult`'s own convention for a non-converged solve.
    """

    model_config = ConfigDict(extra="forbid", frozen=True, allow_inf_nan=False)

    provenance: ResultProvenance
    status: str = Field(
        description='HiGHS model status: "Optimal", "Infeasible", "Unbounded", or another '
        "HiGHS status string passed through verbatim."
    )
    message: str | None = Field(default=None, description="Diagnostic when status != Optimal.")
    n_periods: int = Field(
        description="Number of periods cleared: len(Scenario.periods), or 1 for a period-less "
        "scenario."
    )
    periods: list[MarketPeriodResult] = Field(
        default_factory=list,
        description="One entry per period, in scenario order; empty when not Optimal.",
    )
    objective_cost: float = Field(
        default=0.0,
        description="Total generation cost over the whole horizon, $. Storage is costless in "
        "the objective -- model.Storage carries no cost field, so a unit's only economic "
        "footprint is the round-trip loss it imposes on generation. 0.0 when not Optimal.",
    )
    total_load_payment: float = Field(
        default=0.0, description="Horizon sum of the per-period load payments, $."
    )
    total_generator_receipts: float = Field(
        default=0.0, description="Horizon sum of the per-period generator receipts, $."
    )
    total_storage_charge_payment: float = Field(
        default=0.0, description="Horizon sum of the per-period storage charge payments, $."
    )
    total_storage_discharge_revenue: float = Field(
        default=0.0, description="Horizon sum of the per-period storage discharge revenues, $."
    )
    congestion_rent: float = Field(
        default=0.0, description="Horizon sum of the per-period congestion rents, $."
    )
