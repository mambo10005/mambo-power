"""AC-1 (secondary) / AC-2 (negative pair): ``solve_ac`` against the MATPOWER stored VM/VA columns.

The stored columns are CDF-era solutions carried with 3 decimals (VM) / 2 decimals (VA) and
are **not** 1e-8 solutions of the shipped data (record/m2-research.md §1): every fixture's
stored state differs from any converged solve by more than its rounding floor, and a few buses
carry real data defects. So this tier is *secondary*: pandapower is the primary oracle
(:mod:`tests.parity.test_ac_vs_pandapower`), and the bands here are the ones W1 ratified and
M2's research re-measured as the tightest the data support — **2e-3 pu / 0.5 deg** (research
§1.4: "tightening below ~1.5e-3 / 0.45° would fail case14 / case_ieee30 on data, not solver,
grounds"). The brief's "file precision" bands (5e-4 pu / 5e-3 deg) were run first and fail on
data grounds (case14 bus 4 sits 1.3e-3 pu from the stored VM with every solver); the measured
residual per fixture is recorded in the S4 report, and ``MEASURED_RESIDUAL`` below pins it.

Exclusions (each with the stored-state mismatch measured in MVA by research §1.3, an
engine-independent dense gate — the stored voltages cannot satisfy the shipped data there):
case_ieee30 bus 3; case57 buses 14, 46, 47; case118 buses 17, 30, 38, 68.

Angles are compared after subtracting the stored slack angle (case118 stores 30° at bus 69).
Q-limits are **on** (the stored points were produced with limits enforced: with limits off
case118 breaches the VM band at bus 103 — that is AC-2's negative pair, asserted below).
case30's stored state is flat (VM = 1, VA = 0 on every row): self-consistency only.
case300: no promised column parity — convergence with Q-limits off plus self-consistency.
(Research §4.3 measured the stored columns "0.107 pu away" through pandapower's ``from_ppc``,
whose hv-side tap placement mis-models 16 case300 transformers; against this solver the
stored columns are 8.5e-3 pu away at worst, 11/300 buses outside 2e-3 — S4 report.)
"""

from __future__ import annotations

import warnings
from typing import Any

import numpy as np
import pytest

from mambo_power.io import matpower
from mambo_power.pf import AcOptions, solve_ac
from tests._fixtures import FIXTURES_DIR
from tests.parity._mpc_reader import read_mpc_numpy

VM_BAND = 2e-3  # pu — W1's ratified band; 3-decimal VM columns round to ±5e-4 at best
VA_BAND = 0.5  # deg — 2-decimal VA columns round to ±5e-3 at best
VM_COL, VA_COL = 7, 8

EXCLUDED: dict[str, dict[int, float]] = {
    # bus -> stored-state mismatch in MVA (record/m2-research.md §1.3, dense gate)
    "case14": {},
    "case_ieee30": {3: 8.2},
    "case57": {14: 21.2, 46: 45.8, 47: 24.7},
    "case118": {17: 45.3, 30: 129.7, 38: 31.3, 68: 10.5},
}

MEASURED_RESIDUAL: dict[str, tuple[float, float]] = {
    # (max |ΔVM| pu, max |ΔVA| deg) after exclusions, research §1.2 (pandapower == ours);
    # the test asserts we are not worse than these by more than the 1e-6 / 1e-4 primary band
    "case14": (1.3e-3, 0.017),
    "case_ieee30": (0.6e-3, 0.428),
    "case57": (0.9e-3, 0.052),
    "case118": (1.0e-3, 0.312),
}


def stored_state(name: str) -> tuple[dict[str, float], dict[str, float]]:
    raw = read_mpc_numpy(FIXTURES_DIR / f"{name}.m")
    bus = raw["bus"]
    vm = {f"bus-{int(row[0])}": float(row[VM_COL]) for row in bus}
    va = {f"bus-{int(row[0])}": float(row[VA_COL]) for row in bus}
    return vm, va


def solve(name: str, **options: Any) -> Any:
    net = matpower.load(FIXTURES_DIR / f"{name}.m")
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        return solve_ac(net, options=AcOptions(init="flat", **options))


@pytest.mark.parametrize("name", list(EXCLUDED))
def test_matches_stored_columns_outside_the_exclusions(name: str) -> None:
    vm_ref, va_ref = stored_state(name)
    result = solve(name, q_limits=True)
    assert result.converged
    slack = next(b for b in result.buses if b.role_effective == "slack")
    offset = va_ref[slack.id]
    excluded = {f"bus-{b}" for b in EXCLUDED[name]}
    vm_diff = {b.id: abs(b.vm_pu - vm_ref[b.id]) for b in result.buses if b.id not in excluded}
    va_diff = {
        b.id: abs(b.va_deg - (va_ref[b.id] - offset)) for b in result.buses if b.id not in excluded
    }
    assert len(vm_diff) == len(result.buses) - len(excluded)
    worst_vm = max(vm_diff, key=vm_diff.__getitem__)
    worst_va = max(va_diff, key=va_diff.__getitem__)
    assert vm_diff[worst_vm] <= VM_BAND, (name, worst_vm, vm_diff[worst_vm])
    assert va_diff[worst_va] <= VA_BAND, (name, worst_va, va_diff[worst_va])
    # and no better-than-data claim: the residual is the data's, not ours
    vm_meas, va_meas = MEASURED_RESIDUAL[name]
    assert vm_diff[worst_vm] <= vm_meas + 1e-4, (name, worst_vm, vm_diff[worst_vm])
    assert va_diff[worst_va] <= va_meas + 1e-2, (name, worst_va, va_diff[worst_va])


@pytest.mark.parametrize("name", [n for n in EXCLUDED if EXCLUDED[n]])
def test_exclusions_sit_where_the_data_are_worst(name: str) -> None:
    """The exclusion list is not tolerance padding: it holds the fixture's worst-deviating bus.

    Each excluded bus carries a stored-state defect of 5+ MVA (research §1.3). The defect shows
    as a band breach at the bus (case57 bus 46: 4.9× the band; case118 bus 30: 8.8×) or, where
    the surrounding solution absorbs it, as the fixture's largest deviation (case_ieee30 bus 3:
    0.86 of the band, its neighbours 4/16 at 0.68). Per-bus ratios are printed for the record.
    """
    vm_ref, va_ref = stored_state(name)
    result = solve(name, q_limits=True)
    slack = next(b for b in result.buses if b.role_effective == "slack")
    offset = va_ref[slack.id]

    def ratio(b: Any) -> float:
        return max(
            abs(b.vm_pu - vm_ref[b.id]) / VM_BAND,
            abs(b.va_deg - (va_ref[b.id] - offset)) / VA_BAND,
        )

    excluded = {f"bus-{n}" for n in EXCLUDED[name]}
    assert all(EXCLUDED[name][n] >= 5.0 for n in EXCLUDED[name])
    ratios_excluded = {b.id: ratio(b) for b in result.buses if b.id in excluded}
    ratios_kept = {b.id: ratio(b) for b in result.buses if b.id not in excluded}
    worst_kept = max(ratios_kept, key=ratios_kept.__getitem__)
    print(
        f"{name} excluded-bus breach ratios (1.0 = band): {ratios_excluded}; "
        f"worst kept bus {worst_kept}: {ratios_kept[worst_kept]:.3f}"
    )
    assert max(ratios_excluded.values()) >= ratios_kept[worst_kept], (name, ratios_excluded)


def test_case118_without_q_limits_breaches_at_bus_103() -> None:
    """AC-2 negative pair: the stored point was produced with limits on (research §1.4)."""
    vm_ref, _ = stored_state("case118")
    off = solve("case118", q_limits=False)
    on = solve("case118", q_limits=True)
    assert off.converged and on.converged
    vm_off = next(b.vm_pu for b in off.buses if b.id == "bus-103")
    vm_on = next(b.vm_pu for b in on.buses if b.id == "bus-103")
    assert abs(vm_off - vm_ref["bus-103"]) > VM_BAND, vm_off
    assert abs(vm_on - vm_ref["bus-103"]) <= VM_BAND, vm_on
    assert off.q_limit_rounds == 0 and on.q_limit_rounds >= 1


def _self_consistent(name: str, **options: Any) -> None:
    net = matpower.load(FIXTURES_DIR / f"{name}.m")
    first = solve_ac(net, options=AcOptions(init="flat", **options))
    assert first.converged and first.iterations > 0
    state = {b.id: b for b in first.buses}
    warm_net = net.model_copy(
        update={
            "buses": [
                b.model_copy(update={"vm_pu": state[b.id].vm_pu, "va_deg": state[b.id].va_deg})
                for b in net.buses
            ]
        }
    )
    second = solve_ac(warm_net, options=AcOptions(init="auto", **options))
    assert second.converged and second.iterations <= 1
    ours = first.to_arrays()
    again = second.to_arrays()
    np.testing.assert_allclose(again.vm_pu, ours.vm_pu, rtol=0, atol=1e-9)
    np.testing.assert_allclose(again.va_deg, ours.va_deg, rtol=0, atol=1e-7)
    np.testing.assert_allclose(again.p_from_mw, ours.p_from_mw, rtol=0, atol=1e-6)


def test_case30_self_consistency() -> None:
    vm_ref, va_ref = stored_state("case30")
    assert set(vm_ref.values()) == {1.0} and set(va_ref.values()) == {0.0}  # stored state is flat
    _self_consistent("case30", q_limits=True)


def test_case300_converges_without_q_limits_and_is_self_consistent() -> None:
    _self_consistent("case300", q_limits=False)
