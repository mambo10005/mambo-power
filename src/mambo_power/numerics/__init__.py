"""Network matrices over scipy.sparse: the positional pu view, Ybus, Bbus, PTDF and LODF.

The only package module that holds positional indices. :class:`NetworkArrays` is the single
per-unit conversion site; every builder here takes that view, never a ``Network`` directly.
:func:`effective_roles` derives the roles a solver must use from the declared ones (W3).
"""

from mambo_power.numerics.arrays import NetworkArrays
from mambo_power.numerics.bbus import bbus, bf, flow_from_ptdf, p_shift
from mambo_power.numerics.errors import (
    NoSlackGeneratorError,
    SetpointConflictWarning,
    UnsolvableNetworkError,
)
from mambo_power.numerics.lodf import bridges, lodf
from mambo_power.numerics.ptdf import ptdf
from mambo_power.numerics.roles import EffectiveRoles, effective_roles
from mambo_power.numerics.ybus import ybus, yf_yt

__all__ = [
    "EffectiveRoles",
    "NetworkArrays",
    "NoSlackGeneratorError",
    "SetpointConflictWarning",
    "UnsolvableNetworkError",
    "bbus",
    "bf",
    "bridges",
    "effective_roles",
    "flow_from_ptdf",
    "lodf",
    "p_shift",
    "ptdf",
    "ybus",
    "yf_yt",
]
