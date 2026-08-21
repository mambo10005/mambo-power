"""Effective power-flow bus roles derived from the declared roles and generator status (W3).

:class:`~mambo_power.numerics.NetworkArrays` carries the roles *declared* on the buses. The
solvers need the *effective* roles, which depend on which generators are in service. This
module is the single derivation site (wave M2 design item 2); ``pf.ac``, ``pf.dc`` and
``results`` consume its output and never re-derive it.

Rules, each with its oracle:

1. **PV bus without an in-service generator → PQ.** MATPOWER ``bustypes.m``:
   ``pv = find(BUS_TYPE == PV & bus_gen_status)``, ``pq = find(BUS_TYPE == PQ |
   ~bus_gen_status)``. pandapower: only in-service generators write ``BUS_TYPE = PV``
   (``build_gen.py``), so such a bus keeps the default PQ type.
2. **Slack bus without an in-service generator → :class:`NoSlackGeneratorError`.** MATPOWER
   would move the reference to the first PV bus; the spec rejects that re-slacking, so the
   condition is named and raised.
3. **Several in-service generators at one bus → the LAST one's ``v_set_pu`` in generator
   order.** MATPOWER ``runpf.m`` sets ``V0(gbus) = VG`` with a repeated-index assignment,
   and MATLAB applies such assignments sequentially, so the last row wins. pandapower refuses
   differing setpoints with a ``UserWarning``; here the disagreement is reported as a
   :class:`SetpointConflictWarning` and the MATPOWER value is used. (pandapower's
   ``from_ppc`` converter, by contrast, keeps the *first* row's VG — record/m2-research.md §2.)

Buses with no generator keep ``v_set = 1.0``; PQ buses with a generator carry its setpoint
too (MATPOWER sets ``V0`` at every generator bus), solvers pick by role. The input arrays
are never modified.
"""

from __future__ import annotations

import math
import warnings
from dataclasses import dataclass

import numpy as np
import numpy.typing as npt

from mambo_power.numerics.arrays import BUS_TYPE_CODE, NetworkArrays
from mambo_power.numerics.errors import NoSlackGeneratorError, SetpointConflictWarning

FloatArray = npt.NDArray[np.float64]
IntArray = npt.NDArray[np.int64]

SETPOINT_TOL = 1e-9
"""Setpoints at one bus that differ by more than this (pu) are a conflict."""


@dataclass(frozen=True)
class EffectiveRoles:
    """The roles and setpoints a solver must use, positional over the arrays' bus order."""

    bus_type: IntArray
    """Effective role per bus: 1 = pq, 2 = pv, 3 = slack (same codes as the arrays)."""
    v_set: FloatArray
    """Effective voltage setpoint per bus (pu): last in-service generator's; 1.0 if none."""
    demoted_pv: IntArray
    """Positions of buses declared PV but solved as PQ (no in-service generator), ascending."""
    setpoint_conflicts: list[tuple[str, list[str], list[float]]]
    """``(bus_id, gen_ids, setpoints)`` for every bus whose in-service generators disagree."""


def effective_roles(arr: NetworkArrays) -> EffectiveRoles:
    """Derive the effective roles and setpoints from ``arr`` (see the module docstring).

    Raises :class:`NoSlackGeneratorError` when the slack bus has no in-service generator.
    Emits one :class:`SetpointConflictWarning` per bus whose generators disagree.
    """
    pq, pv, slack = BUS_TYPE_CODE["pq"], BUS_TYPE_CODE["pv"], BUS_TYPE_CODE["slack"]
    n_gen = len(arr.gen_ids)
    gens_at: dict[int, list[int]] = {}
    for g in range(n_gen):
        gens_at.setdefault(int(arr.gen_bus[g]), []).append(g)

    bus_type = arr.bus_type.copy()
    has_gen = np.zeros(arr.n_bus, dtype=bool)
    has_gen[list(gens_at)] = True

    if bus_type[arr.slack] == slack and not has_gen[arr.slack]:
        raise NoSlackGeneratorError(arr.bus_ids[arr.slack], int(arr.slack))

    demoted = np.flatnonzero((bus_type == pv) & ~has_gen).astype(np.int64)
    bus_type[demoted] = pq

    v_set = np.ones(arr.n_bus)
    conflicts: list[tuple[str, list[str], list[float]]] = []
    for position in sorted(gens_at):
        rows = gens_at[position]
        setpoints = [float(arr.gen_v_set[g]) for g in rows]
        v_set[position] = setpoints[-1]
        if len(rows) > 1 and any(
            not math.isclose(s, setpoints[-1], rel_tol=0.0, abs_tol=SETPOINT_TOL) for s in setpoints
        ):
            bus_id = arr.bus_ids[position]
            gen_ids = [arr.gen_ids[g] for g in rows]
            conflicts.append((bus_id, gen_ids, setpoints))
            pairs = ", ".join(f"{gid}={s:g}" for gid, s in zip(gen_ids, setpoints, strict=True))
            warnings.warn(
                SetpointConflictWarning(
                    f'bus "{bus_id}": in-service generators disagree on the voltage setpoint '
                    f"({pairs}); using the last one, {setpoints[-1]:g} pu (MATPOWER rule)"
                ),
                stacklevel=2,
            )

    return EffectiveRoles(
        bus_type=bus_type, v_set=v_set, demoted_pv=demoted, setpoint_conflicts=conflicts
    )
