"""Defensive ``ValueError`` guards in ``numerics`` (review Correctness 3-4).

Every guard is reachable only by mutating an already-validated :class:`Network` (models are
mutable and do not re-validate, plan A7) or by passing a bad argument, so each test does
exactly that on a 2-bus, 2-branch case.
"""

from __future__ import annotations

import numpy as np
import pytest

from mambo_power.model import Branch, Bus, Generator, Network
from mambo_power.numerics import NetworkArrays, bbus, lodf, ptdf, ybus


def two_bus() -> Network:
    return Network(
        base_mva=100.0,
        buses=[Bus(id="b1", base_kv=110.0, type="slack"), Bus(id="b2", base_kv=110.0, type="pq")],
        branches=[
            Branch(id="l1", from_bus="b1", to_bus="b2", r=0.01, x=0.1, b=0.0),
            Branch(id="l2", from_bus="b1", to_bus="b2", r=0.02, x=0.2, b=0.0),
        ],
        generators=[
            Generator(
                id="g1",
                bus="b1",
                p_mw=0.0,
                q_mvar=0.0,
                p_min_mw=0.0,
                p_max_mw=100.0,
                q_min_mvar=-50.0,
                q_max_mvar=50.0,
                v_set_pu=1.0,
            )
        ],
    )


def test_from_network_requires_exactly_one_in_service_slack() -> None:
    net = two_bus()
    net.buses[0].type = "pq"  # mutation after validation: no slack left
    with pytest.raises(ValueError, match="expected exactly one in-service slack"):
        NetworkArrays.from_network(net)


def test_ybus_rejects_zero_series_impedance() -> None:
    net = two_bus()
    net.branches[1].r = 0.0
    net.branches[1].x = 0.0
    arr = NetworkArrays.from_network(net)
    with pytest.raises(ValueError, match=r"l2"):
        ybus(arr)


def test_bbus_rejects_zero_reactance() -> None:
    net = two_bus()
    net.branches[0].x = 0.0
    arr = NetworkArrays.from_network(net)
    with pytest.raises(ValueError, match=r"DC susceptance undefined.*l1"):
        bbus(arr)


def test_ptdf_rejects_slack_out_of_range() -> None:
    arr = NetworkArrays.from_network(two_bus())
    with pytest.raises(ValueError, match="out of range for"):
        ptdf(arr, slack=arr.n_bus)
    with pytest.raises(ValueError, match="out of range for"):
        ptdf(arr, slack=-1)


def test_lodf_rejects_mis_shaped_ptdf() -> None:
    arr = NetworkArrays.from_network(two_bus())
    with pytest.raises(ValueError, match="ptdf_matrix has shape"):
        lodf(arr, ptdf_matrix=np.zeros((arr.n_branch + 1, arr.n_bus)))
