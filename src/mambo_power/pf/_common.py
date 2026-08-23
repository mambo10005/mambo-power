"""Private helpers shared between :mod:`mambo_power.pf.dc` and :mod:`mambo_power.pf.ac_newton`.

Not part of the public ``pf`` surface — the leading underscore is the same "internal, not
walked for the API reference" convention as ``tests/parity/_mpc_reader.py``.
"""

from __future__ import annotations

import numpy as np
import numpy.typing as npt

from mambo_power.numerics.arrays import NetworkArrays

FloatArray = npt.NDArray[np.float64]


def absorb_slack_p(arr: NetworkArrays, p_bus_pu: float) -> FloatArray:
    """Per-generator active dispatch with the slack-bus balance absorbed by the first
    in-service generator there (D1: the MATPOWER rule ``pf.dc`` and ``pf.ac_newton`` both
    apply, now in one place instead of two independently-tested copies).

    Every generator keeps its declared dispatch (``arr.gen_p_pu``) except the first
    in-service generator at the slack bus, which absorbs ``p_bus_pu -
    arr.p_gen_pu[arr.slack]`` — the gap between the realised and the declared generation at
    that bus. ``p_bus_pu`` is the realised *gross* generation the slack bus supplies: the
    realised net injection plus whatever was subtracted to declare it (load, and for DC the
    shunt conductance; AC folds shunts into ``Y`` so no separate term is needed there). A
    slack bus with no in-service generator leaves ``gen_p_pu`` untouched — naming that
    situation is :func:`mambo_power.numerics.effective_roles`'s job, not this function's.

    Both callers' own hand-case tests
    (``tests/unit/test_pf_dc.py::test_slack_balance_goes_to_the_first_slack_generator``,
    ``tests/unit/test_pf_ac_newton.py::test_first_slack_generator_absorbs_the_balance``) are
    this function's agreement tests: they now exercise the same code path, so a change to one
    solver's slack rule cannot silently diverge from the other's.
    """
    gen_p = arr.gen_p_pu.copy()
    slack_gens = np.flatnonzero(arr.gen_bus == arr.slack)
    if slack_gens.size:
        gen_p[slack_gens[0]] += p_bus_pu - arr.p_gen_pu[arr.slack]
    return gen_p
