"""Per-element result rows keyed by the network's stable ids.

Units are physical, matching :mod:`mambo_power.model`: MW, MVAr, per unit, degrees. Rows cover
the **in-service subset** the solver saw (the same elements
:class:`~mambo_power.numerics.NetworkArrays` holds, in the same order), so ``in_service`` is
``True`` on every row a solver emits today; the field exists so a later wave can report
deactivated elements without a schema change. ``inf`` and ``nan`` are rejected — a quantity
that does not exist is ``None`` (``loading_pct`` on an unrated branch), never a sentinel number.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

BusRole = Literal["slack", "pv", "pq"]
"""The role a bus was solved with — the *effective* role, which may differ from the declared."""

QLimitSide = Literal["none", "min", "max"]
"""Which reactive limit a generator was pinned at by AC Q-limit enforcement; ``none`` for DC."""


class _Row(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, allow_inf_nan=False)


class BusResult(_Row):
    """Solved state of one bus.

    ``p_mw``/``q_mvar`` are the **net injection into the network**: generation minus load minus
    shunt consumption (MATPOWER bus-equation sign; pandapower's ``res_bus`` is the negative).
    """

    id: str = Field(description="Bus id from the network.")
    vm_pu: float = Field(description="Voltage magnitude, per unit (1.0 on every bus for DC).")
    va_deg: float = Field(description="Voltage angle, degrees; the slack is 0.")
    p_mw: float = Field(description="Net active injection into the network, MW.")
    q_mvar: float = Field(description="Net reactive injection into the network, MVAr (0 for DC).")
    role_effective: BusRole = Field(description="Role the bus was solved with.")
    in_service: bool = Field(description="Whether the bus was part of the solve.")


class BranchResult(_Row):
    """Flows on one branch, measured into the branch at each end.

    ``p_from_mw`` is positive when power leaves ``from_bus`` into the branch; a lossless (DC)
    solve has ``p_to_mw == -p_from_mw``.
    """

    id: str = Field(description="Branch id from the network.")
    from_bus: str = Field(description="Bus id of the from (tap) side.")
    to_bus: str = Field(description="Bus id of the to side.")
    p_from_mw: float = Field(description="Active power entering the branch at the from bus, MW.")
    q_from_mvar: float = Field(description="Reactive power entering at the from bus, MVAr.")
    p_to_mw: float = Field(description="Active power entering the branch at the to bus, MW.")
    q_to_mvar: float = Field(description="Reactive power entering at the to bus, MVAr.")
    loading_pct: float | None = Field(
        description="Apparent from-side flow over ``rating_mva`` in percent; None when unrated."
    )


class GenResult(_Row):
    """Dispatch of one generator after the solve."""

    id: str = Field(description="Generator id from the network.")
    bus: str = Field(description="Bus id the generator is connected to.")
    p_mw: float = Field(description="Active output, MW (slack-bus generators absorb the balance).")
    q_mvar: float = Field(description="Reactive output, MVAr (0 for DC).")
    q_limited: QLimitSide = Field(description="Reactive limit the generator was pinned at.")
