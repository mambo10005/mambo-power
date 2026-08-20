"""Bus admittance matrix and branch admittance matrices (MATPOWER ``makeYbus`` conventions).

Per branch with series admittance ``y = 1 / (r + jx)``, total charging ``b`` and from-side
complex tap ``a = tap · e^{j·shift}``::

    Yff = (y + j·b/2) / |a|²      Yft = -y / conj(a)
    Ytf = -y / a                  Ytt =  y + j·b/2

``Ybus = Cfᵀ·Yf + Ctᵀ·Yt + diag(g_shunt + j·b_shunt)`` with the shunt admittance already in pu
(:class:`~mambo_power.numerics.arrays.NetworkArrays` divided by ``base_mva``).
"""

from __future__ import annotations

from typing import Any

import numpy as np
import numpy.typing as npt
from scipy import sparse

from mambo_power.numerics.arrays import NetworkArrays

ComplexArray = npt.NDArray[np.complex128]


def branch_admittances(
    arr: NetworkArrays,
) -> tuple[ComplexArray, ComplexArray, ComplexArray, ComplexArray]:
    """Per-branch ``(Yff, Yft, Ytf, Ytt)`` vectors."""
    ys = np.asarray(1.0 / (arr.r + 1j * arr.x), dtype=np.complex128)
    bc = np.asarray(1j * arr.b / 2.0, dtype=np.complex128)
    a = np.asarray(arr.tap * np.exp(1j * arr.shift_rad), dtype=np.complex128)
    yff: ComplexArray = (ys + bc) / (a * np.conj(a))
    yft: ComplexArray = -ys / np.conj(a)
    ytf: ComplexArray = -ys / a
    ytt: ComplexArray = ys + bc
    return yff, yft, ytf, ytt


def yf_yt(arr: NetworkArrays) -> tuple[Any, Any]:
    """``(Yf, Yt)``: ``n_branch × n_bus`` complex CSC matrices giving from/to branch currents.

    ``Yf @ V`` is the current injected into each branch at its from bus, ``Yt @ V`` at its to
    bus — the inputs M2 needs for branch flows.
    """
    yff, yft, ytf, ytt = branch_admittances(arr)
    rows = np.concatenate([np.arange(arr.n_branch), np.arange(arr.n_branch)])
    cols = np.concatenate([arr.f, arr.t])
    shape = (arr.n_branch, arr.n_bus)
    yf = sparse.csc_matrix((np.concatenate([yff, yft]), (rows, cols)), shape=shape)
    yt = sparse.csc_matrix((np.concatenate([ytf, ytt]), (rows, cols)), shape=shape)
    return yf, yt


def ybus(arr: NetworkArrays) -> Any:
    """The ``n_bus × n_bus`` complex CSC bus admittance matrix over the in-service subset."""
    yff, yft, ytf, ytt = branch_admittances(arr)
    rows = np.concatenate([arr.f, arr.f, arr.t, arr.t, np.arange(arr.n_bus)])
    cols = np.concatenate([arr.f, arr.t, arr.f, arr.t, np.arange(arr.n_bus)])
    data = np.concatenate([yff, yft, ytf, ytt, arr.g_shunt_pu + 1j * arr.b_shunt_pu])
    matrix = sparse.csc_matrix((data, (rows, cols)), shape=(arr.n_bus, arr.n_bus))
    matrix.sum_duplicates()
    return matrix
