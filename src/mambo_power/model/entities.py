"""Network entities — the native file format IS these models.

Units are physical (wave M1 design item 1): MW, MVAr, kV, MWh, degrees; branch ``r``/``x``/``b``
are per-unit on the network's ``base_mva``. Per-unit conversion lives in ``numerics``, never
here. Field names are snake_case with a unit suffix (design item 2). Every model rejects
unknown fields so a typo in a file is an error, not silently dropped data.

Cross-entity invariants (slack count, connectivity, references, ranges) are checked by
:class:`mambo_power.model.Network`, not by the entities themselves, so that one validation
pass can report every problem at once.
"""

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field

BusType = Literal["slack", "pv", "pq"]
"""Bus role in power flow. MATPOWER type 4 (isolated) maps to ``in_service=False`` instead."""


class _Entity(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=False, allow_inf_nan=False)


class Geo(_Entity):
    """Geographic position of a bus in decimal degrees (WGS 84)."""

    lat: float = Field(description="Latitude, decimal degrees.")
    lon: float = Field(description="Longitude, decimal degrees.")


class Bus(_Entity):
    """Electrical node. ``vm_pu``/``va_deg`` hold an initial or last-solved state, if any."""

    id: str = Field(description="Unique within buses.")
    base_kv: float = Field(description="Nominal voltage, kV. Must be > 0.")
    type: BusType = Field(description="Power-flow role: exactly one in-service slack per network.")
    in_service: bool = True
    vm_pu: float | None = Field(default=None, description="Voltage magnitude, per unit.")
    va_deg: float | None = Field(default=None, description="Voltage angle, degrees.")
    v_min_pu: float | None = Field(default=None, description="Lower voltage limit, per unit.")
    v_max_pu: float | None = Field(default=None, description="Upper voltage limit, per unit.")
    area: str | None = Field(default=None, description="Free-form area label (MATPOWER AREA).")
    zone: str | None = Field(default=None, description="Zone id; must resolve to zones[].id.")
    geo: Geo | None = None


class Branch(_Entity):
    """Line or transformer between two buses. Tap is on the ``from`` side (MATPOWER model)."""

    id: str = Field(description="Unique within branches.")
    from_bus: str = Field(description="Bus id of the from (tap) side.")
    to_bus: str = Field(description="Bus id of the to side.")
    r: float = Field(description="Series resistance, per unit on base_mva.")
    x: float = Field(description="Series reactance, per unit on base_mva.")
    b: float = Field(description="Total line charging susceptance, per unit on base_mva.")
    rating_mva: float | None = Field(default=None, description="Thermal rating, MVA; None = none.")
    tap_ratio: float | None = Field(default=None, description="Off-nominal tap; None = 1.0.")
    shift_deg: float | None = Field(default=None, description="Phase shift, degrees; None = 0.")
    in_service: bool = True


class PolynomialCost(_Entity):
    """MATPOWER gencost MODEL 2: cost(p_mw) = sum(c_k * p_mw**k), highest order first."""

    kind: Literal["polynomial"] = "polynomial"
    coefficients: list[float] = Field(
        description="Polynomial coefficients (at least one), highest order first, cost per hour."
    )
    startup: float = Field(default=0.0, description="Startup cost.")
    shutdown: float = Field(default=0.0, description="Shutdown cost.")


class PiecewiseCost(_Entity):
    """MATPOWER gencost MODEL 1: piecewise-linear (p_mw, cost) breakpoints, increasing in p."""

    kind: Literal["piecewise"] = "piecewise"
    points: list[tuple[float, float]] = Field(
        max_length=200,
        description="(p_mw, cost) breakpoints, at least two and at most 200 (each adds one "
        "epigraph row to opf.dc_opf's LP); p_mw must be strictly increasing.",
    )
    startup: float = Field(default=0.0, description="Startup cost.")
    shutdown: float = Field(default=0.0, description="Shutdown cost.")


GeneratorCost = Annotated[PolynomialCost | PiecewiseCost, Field(discriminator="kind")]


class PolynomialBid(_Entity):
    """Demand-side mirror of :class:`PolynomialCost`: value(p_mw) = sum(c_k * p_mw**k).

    Marginal value must be non-increasing (concave value) for a valid market clearing; that
    convexity-*direction* check is ``opf.dc_opf``'s job at solve time
    (:class:`~mambo_power.opf.NonConcaveBidError`), not construction-time here — mirrors how
    :class:`PolynomialCost` also has no construction-time convexity check.
    """

    kind: Literal["polynomial"] = "polynomial"
    coefficients: list[float] = Field(
        description="Polynomial coefficients (at least one), highest order first, value per hour."
    )


class PiecewiseBid(_Entity):
    """Demand-side mirror of :class:`PiecewiseCost`: piecewise-linear (p_mw, value) breakpoints.

    Only the same structural checks :class:`PiecewiseCost` gets (at least two points,
    strictly increasing ``p_mw``) apply here; the concavity *direction* of the value curve is
    checked at solve time, not here (see :class:`PolynomialBid`).
    """

    kind: Literal["piecewise"] = "piecewise"
    points: list[tuple[float, float]] = Field(
        max_length=200,
        description="(p_mw, value) breakpoints, at least two and at most 200 (each adds one "
        "hypograph row to opf.dc_opf's LP); p_mw must be strictly increasing.",
    )


LoadBid = Annotated[PolynomialBid | PiecewiseBid, Field(discriminator="kind")]


class Generator(_Entity):
    """Dispatchable injection. ``cost`` is model-present and solver-ignored until M3."""

    id: str = Field(description="Unique within generators.")
    bus: str = Field(description="Bus id.")
    p_mw: float = Field(description="Active power setpoint or dispatch, MW.")
    q_mvar: float = Field(description="Reactive power setpoint or dispatch, MVAr.")
    p_min_mw: float = Field(description="Lower active limit, MW; must be <= p_max_mw.")
    p_max_mw: float = Field(description="Upper active limit, MW.")
    q_min_mvar: float = Field(description="Lower reactive limit, MVAr; must be <= q_max_mvar.")
    q_max_mvar: float = Field(description="Upper reactive limit, MVAr.")
    v_set_pu: float = Field(description="Voltage setpoint, per unit.")
    in_service: bool = True
    cost: GeneratorCost | None = None
    ramp_up_mw: float | None = Field(
        default=None, description="Max increase from the previous period, MW; None = none."
    )
    ramp_down_mw: float | None = Field(
        default=None, description="Max decrease from the previous period, MW; None = none."
    )


class Load(_Entity):
    """Demand at a bus, fixed or elastic. ``bid`` is read by ``market.nodal`` and
    ``market.multiperiod``; ``opf.solve_dc_opf`` ignores it and serves ``p_mw`` in full."""

    id: str = Field(description="Unique within loads.")
    bus: str = Field(description="Bus id.")
    p_mw: float = Field(
        description="Active demand, MW. With a bid, this is the *maximum* quantity that can be "
        "served, and the bid decides where in [0, p_mw] the load actually clears; a Period "
        "override of it therefore moves that maximum too."
    )
    q_mvar: float = Field(description="Reactive demand, MVAr.")
    in_service: bool = True
    bid: LoadBid | None = Field(
        default=None,
        description="Elastic-demand bid covering this Load's entire p_mw; market.nodal and "
        "market.multiperiod read it, opf.solve_dc_opf does not. There is no per-Load "
        "partial-capacity split -- bidding "
        "only part of a load's capacity, with the rest must-serve, means splitting it into two "
        "Load entities at the same bus (one bid=None fixed, one bid-carrying).",
    )


class Shunt(_Entity):
    """Fixed shunt at 1.0 pu voltage, MATPOWER GS/BS sign convention."""

    id: str = Field(description="Unique within shunts.")
    bus: str = Field(description="Bus id.")
    g_mw: float = Field(description="Conductance as MW consumed at 1.0 pu; positive consumes.")
    b_mvar: float = Field(description="Susceptance as MVAr injected at 1.0 pu; positive injects.")
    in_service: bool = True


class Storage(_Entity):
    """Energy storage. Read by ``market.multiperiod``, which gives each unit a charge, a
    discharge and a state-of-charge column per period; every other solver ignores it."""

    id: str = Field(description="Unique within storage.")
    bus: str = Field(description="Bus id.")
    p_max_mw: float = Field(description="Charge/discharge power limit, MW.")
    energy_mwh: float = Field(description="Energy capacity, MWh.")
    soc_initial: float = Field(
        description="Initial state of charge, fraction of energy_mwh in [0, 1]."
    )
    efficiency_charge: float = Field(description="Charging efficiency in (0, 1].")
    efficiency_discharge: float = Field(description="Discharging efficiency in (0, 1].")
    in_service: bool = True


class Zone(_Entity):
    """Named grouping of buses (MATPOWER loss zone, market zone, ...)."""

    id: str = Field(description="Unique within zones.")
    name: str | None = None
