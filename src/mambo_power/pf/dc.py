"""DC power flow over :class:`~mambo_power.numerics.NetworkArrays` (MATPOWER ``rundcpf``).

Formulation. With the DC susceptance matrix ``B'`` (:func:`mambo_power.numerics.bbus`), the
from-side flow matrix ``Bf`` (:func:`mambo_power.numerics.bf`), the phase-shifter injections
``p_shift = Cftᵀ · pf_shift`` and ``pf_shift = -b · shift`` (:mod:`mambo_power.numerics.bbus`),
and the declared net injection per bus in per unit::

    P_bus = P_gen − P_load − G_shunt          (G_shunt: conductance consumption at 1.0 pu)

the angles solve the linear system with the slack row and column removed and θ_slack = 0::

    B'[keep, keep] · θ[keep] = (P_bus − p_shift)[keep]          θ[slack] = 0

and the flows and realised injections follow::

    p_from = Bf · θ + pf_shift          p_to = −p_from          p_inj = B' · θ + p_shift

``p_inj`` equals ``P_bus`` on every non-slack bus; at the slack it is whatever closes the
balance (lossless, so Σ p_inj = 0). Those are exactly MATPOWER's ``rundcpf`` steps —
``Pbus = real(makeSbus) − Pbusinj − GS/baseMVA``, ``Va = dcpf(B, Pbus, Va0, ref, pv, pq)``,
``PF = (Bf·Va + Pfinj)·baseMVA``, ``PT = −PF`` — which pandapower's ``rundcpp`` copies
verbatim (record/m2-research.md §2).

Slack generation. The slack-bus balance goes **entirely to the first in-service generator at
the slack bus**, every other generator keeping its dispatch (MATPOWER ``rundcpf``:
``gen(on(refgen(1)), PG) += (B(ref,:)·Va − Pbus(ref))·baseMVA``; pandapower reports the same
number on ``res_ext_grid``). Bus-level generation is therefore engine-independent; the
per-generator split is a documented convention. If the slack bus carries no in-service
generator the balance is still visible on the bus injection; naming that situation is W3's
``effective_roles``.

The reduced system is factorised with ``scipy.sparse.linalg.splu`` (the same backend as the
PTDF builder and the AC Newton solve). Bus roles are the *declared* roles from the arrays —
DC needs no generator setpoints, so effective-role derivation (W3) does not enter here.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import numpy.typing as npt
from scipy.sparse.linalg import splu

from mambo_power.numerics.arrays import NetworkArrays
from mambo_power.numerics.bbus import bbus, bf, p_shift, pf_shift
from mambo_power.pf._common import absorb_slack_p

FloatArray = npt.NDArray[np.float64]

SOLVER = "scipy.sparse.linalg.splu"
"""Linear-algebra backend name stamped into the result provenance."""


@dataclass(frozen=True)
class DcSolution:
    """Positional DC solution in per unit, in :class:`NetworkArrays` order."""

    theta_rad: FloatArray
    """Bus angles, radians; ``theta_rad[arr.slack] == 0``."""
    p_from_pu: FloatArray
    """From-side branch flow ``Bf·θ + pf_shift``; the to-side flow is its negative."""
    p_inj_pu: FloatArray
    """Realised net injection per bus ``B'·θ + p_shift`` (slack closes the balance)."""
    gen_p_pu: FloatArray
    """Per-generator output; the first in-service slack-bus generator absorbs the balance."""


def declared_injection(arr: NetworkArrays) -> FloatArray:
    """``P_gen − P_load − G_shunt`` per bus in pu — the right-hand side before phase shifts."""
    result: FloatArray = arr.p_gen_pu - arr.p_load_pu - arr.g_shunt_pu
    return result


def solve(arr: NetworkArrays) -> DcSolution:
    """Solve ``B'θ = P − p_shift`` with the slack at 0 and return angles, flows and injections.

    Raises :class:`~mambo_power.numerics.UnsolvableNetworkError` when a branch has ``x == 0``
    (susceptance undefined; user data DC cannot solve, distinct from a malformed-input
    ``ValueError``) or ``ValueError`` when the reduced ``B'`` is singular / yields non-finite
    angles (an islanded bus set).
    """
    b_matrix = bbus(arr)
    p_declared = declared_injection(arr)
    rhs = p_declared - p_shift(arr)

    theta = np.zeros(arr.n_bus)
    keep = np.array([i for i in range(arr.n_bus) if i != arr.slack], dtype=np.int64)
    if keep.size:
        reduced = b_matrix[keep][:, keep].tocsc()
        try:
            theta[keep] = splu(reduced).solve(rhs[keep])
        except RuntimeError as exc:  # SuperLU: "Factor is exactly singular"
            raise ValueError(f"DC power flow: reduced B' is singular ({exc})") from exc
    if not np.all(np.isfinite(theta)):
        raise ValueError("DC power flow: non-finite angles (reduced B' is singular)")

    p_from: FloatArray = np.asarray(bf(arr) @ theta, dtype=np.float64).ravel() + pf_shift(arr)
    p_inj: FloatArray = np.asarray(b_matrix @ theta, dtype=np.float64).ravel() + p_shift(arr)

    # realised gross generation the slack bus supplies = realised net injection plus what
    # declared_injection subtracted to declare it (load, shunt); absorb_slack_p undoes that
    # subtraction on the other side (arr.p_gen_pu[arr.slack]) — see its docstring.
    p_bus = float(p_inj[arr.slack] + arr.p_load_pu[arr.slack] + arr.g_shunt_pu[arr.slack])
    gen_p = absorb_slack_p(arr, p_bus)

    return DcSolution(theta_rad=theta, p_from_pu=p_from, p_inj_pu=p_inj, gen_p_pu=gen_p)
