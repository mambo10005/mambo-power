"""Named errors and warnings raised by the numerics layer.

Both types are plain :class:`Exception` / :class:`UserWarning` subclasses so that callers can
catch them by name without also catching the generic ``ValueError`` that array construction
raises for malformed input.
"""

from __future__ import annotations


class NoSlackGeneratorError(Exception):
    """The slack bus has no in-service generator, so nothing can close the power balance.

    Raised by :func:`mambo_power.numerics.effective_roles`. MATPOWER's ``bustypes`` would
    silently hand the reference role to the first PV bus; the M2 spec rejects that
    re-slacking (Not Doing: "MATPOWER slack-limiting re-slack") and names the condition
    instead. ``bus_id`` is the slack bus id, ``position`` its index in the arrays.
    """

    bus_id: str
    position: int

    def __init__(self, bus_id: str, position: int) -> None:
        self.bus_id = bus_id
        self.position = position
        super().__init__(
            f'slack bus "{bus_id}" (position {position}) has no in-service generator; '
            "a power flow cannot close the balance"
        )


class UnsolvableNetworkError(Exception):
    """A ``Network`` that passes :func:`~mambo_power.model.validate_network` but cannot be
    solved by the numerics it was handed to — e.g. DC susceptance is undefined when a branch
    carries ``x == 0`` with ``r != 0`` (legal under the model, since ``BAD_RANGE`` only rejects
    ``r == x == 0``). This is user data, not a solver bug: :func:`mambo_power.jobs.run` maps it
    to the structured ``UNSOLVABLE_NETWORK`` failure code rather than ``INTERNAL``.
    """


class SetpointConflictWarning(UserWarning):
    """Several in-service generators at one bus carry different voltage setpoints.

    Emitted by :func:`mambo_power.numerics.effective_roles` (via :func:`warnings.warn`). The
    last generator's setpoint is used, following MATPOWER; pandapower raises a
    ``UserWarning`` and aborts in the same situation, which is why this is surfaced rather
    than resolved silently.
    """
