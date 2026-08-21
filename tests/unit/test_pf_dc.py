"""W2: DC power flow on a hand-built 3-bus case with a phase-shifting transformer.

The oracle here is a dense re-derivation written out in this file: the DC susceptance matrix
is assembled with an explicit loop over branches, the reduced system is solved with
``numpy.linalg.solve``, and flows are recomputed per branch as ``b·(θ_f − θ_t) − b·shift``.
Nothing is shared with :mod:`mambo_power.pf` or :mod:`mambo_power.numerics`.

Case: bus 1 slack (two generators — the MATPOWER slack rule gives the whole balance to the
first), bus 2 PV with a 40 MW generator, bus 3 PQ with a 70 MW load and a 5 MW conductive
shunt. Branches: 1-2 line (x 0.10, 60 MVA rating), 2-3 transformer (x 0.20, tap 0.98, shift
+3°), 1-3 line (x 0.25, no rating), plus an out-of-service 1-3 line that must not appear.
"""

from __future__ import annotations

import math

import numpy as np
import pytest

from mambo_power.model import Branch, Bus, Generator, Load, Network, Shunt
from mambo_power.numerics import NetworkArrays
from mambo_power.pf import DcSolution, solve_dc
from mambo_power.pf import dc as pf_dc
from mambo_power.results import DcPowerFlowResult

BASE = 100.0
TOL = 1e-12


def three_bus() -> Network:
    def generator(id: str, bus: str, p_mw: float) -> Generator:
        return Generator(
            id=id,
            bus=bus,
            p_mw=p_mw,
            q_mvar=0.0,
            p_min_mw=0.0,
            p_max_mw=300.0,
            q_min_mvar=-100.0,
            q_max_mvar=100.0,
            v_set_pu=1.02,
        )

    return Network(
        base_mva=BASE,
        buses=[
            Bus(id="bus-1", base_kv=230.0, type="slack"),
            Bus(id="bus-2", base_kv=230.0, type="pv"),
            Bus(id="bus-3", base_kv=115.0, type="pq"),
        ],
        branches=[
            Branch(id="br-12", from_bus="bus-1", to_bus="bus-2", r=0.01, x=0.10, b=0.02),
            Branch(
                id="xf-23",
                from_bus="bus-2",
                to_bus="bus-3",
                r=0.005,
                x=0.20,
                b=0.0,
                tap_ratio=0.98,
                shift_deg=3.0,
                rating_mva=60.0,
            ),
            Branch(id="br-13", from_bus="bus-1", to_bus="bus-3", r=0.02, x=0.25, b=0.04),
            Branch(
                id="br-13-out",
                from_bus="bus-1",
                to_bus="bus-3",
                r=0.02,
                x=0.25,
                b=0.04,
                in_service=False,
            ),
        ],
        generators=[
            generator("gen-1a", "bus-1", 10.0),
            generator("gen-1b", "bus-1", 12.0),
            generator("gen-2", "bus-2", 40.0),
        ],
        loads=[Load(id="load-3", bus="bus-3", p_mw=70.0, q_mvar=20.0)],
        shunts=[Shunt(id="shunt-3", bus="bus-3", g_mw=5.0, b_mvar=0.0)],
    )


# --- dense oracle -------------------------------------------------------------------------------

LIVE = [  # (from, to, x, tap, shift_deg) in network order, out-of-service branch removed
    (0, 1, 0.10, 1.0, 0.0),
    (1, 2, 0.20, 0.98, 3.0),
    (0, 2, 0.25, 1.0, 0.0),
]
P_INJ_MW = np.array([10.0 + 12.0, 40.0, -70.0 - 5.0])  # declared: gens − loads − shunt GS


def dense_dc() -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Return (theta_rad, p_from_pu, p_inj_pu) from an explicit dense derivation."""
    n = 3
    b_mat = np.zeros((n, n))
    p_shift = np.zeros(n)
    sus = []
    for f, t, x, tap, shift in LIVE:
        b = 1.0 / (x * tap)
        sus.append(b)
        b_mat[f, f] += b
        b_mat[t, t] += b
        b_mat[f, t] -= b
        b_mat[t, f] -= b
        # phase shift: flow term −b·shift on the from side, +b·shift on the to side
        p_shift[f] += -b * math.radians(shift)
        p_shift[t] -= -b * math.radians(shift)
    p = P_INJ_MW / BASE
    theta = np.zeros(n)
    keep = [1, 2]
    theta[keep] = np.linalg.solve(b_mat[np.ix_(keep, keep)], (p - p_shift)[keep])
    p_from = np.array(
        [
            sus[k] * (theta[f] - theta[t]) - sus[k] * math.radians(shift)
            for k, (f, t, _, _, shift) in enumerate(LIVE)
        ]
    )
    p_inj = b_mat @ theta + p_shift
    return theta, p_from, p_inj


@pytest.fixture(scope="module")
def net() -> Network:
    return three_bus()


@pytest.fixture(scope="module")
def arr(net: Network) -> NetworkArrays:
    return NetworkArrays.from_network(net)


@pytest.fixture(scope="module")
def sol(arr: NetworkArrays) -> DcSolution:
    return pf_dc.solve(arr)


@pytest.fixture(scope="module")
def result(net: Network) -> DcPowerFlowResult:
    return solve_dc(net)


# --- arrays level --------------------------------------------------------------------------------


def test_angles_match_dense_solve_and_slack_is_zero(sol: DcSolution) -> None:
    theta, _, _ = dense_dc()
    assert sol.theta_rad[0] == 0.0
    np.testing.assert_allclose(sol.theta_rad, theta, rtol=0, atol=TOL)
    assert abs(theta[2]) > 1e-3  # the case is not trivially flat


def test_flows_match_dense_solve_including_phase_shift(sol: DcSolution) -> None:
    _, p_from, _ = dense_dc()
    np.testing.assert_allclose(sol.p_from_pu, p_from, rtol=0, atol=TOL)
    assert sol.p_from_pu.shape == (3,)  # the out-of-service branch is not present


def test_bus_injections_balance_flows(sol: DcSolution, arr: NetworkArrays) -> None:
    _, _, p_inj = dense_dc()
    np.testing.assert_allclose(sol.p_inj_pu, p_inj, rtol=0, atol=TOL)
    # non-slack buses carry exactly their declared injection
    np.testing.assert_allclose(sol.p_inj_pu[1:], P_INJ_MW[1:] / BASE, rtol=0, atol=TOL)
    # KCL per bus: Σ from-flows − Σ to-flows == injection (lossless, so the slack closes it)
    kcl = np.zeros(arr.n_bus)
    np.add.at(kcl, arr.f, sol.p_from_pu)
    np.add.at(kcl, arr.t, -sol.p_from_pu)
    np.testing.assert_allclose(kcl, sol.p_inj_pu, rtol=0, atol=TOL)
    assert abs(sol.p_inj_pu.sum()) < TOL


def test_first_slack_generator_absorbs_the_balance(sol: DcSolution, arr: NetworkArrays) -> None:
    # MATPOWER rundcpf rule: the whole slack-bus mismatch is added to the first in-service
    # generator at the slack bus; every other generator keeps its dispatch.
    slack_total = (70.0 + 5.0 - 40.0) / BASE  # load + shunt − other gens (lossless)
    assert arr.gen_ids == ["gen-1a", "gen-1b", "gen-2"]
    assert sol.gen_p_pu[0] == pytest.approx(slack_total - 12.0 / BASE, abs=TOL)
    assert sol.gen_p_pu[1] == pytest.approx(12.0 / BASE, abs=TOL)
    assert sol.gen_p_pu[2] == pytest.approx(40.0 / BASE, abs=TOL)
    assert sol.gen_p_pu.sum() == pytest.approx(slack_total + 40.0 / BASE, abs=TOL)


# --- typed result -----------------------------------------------------------------------------


def test_result_tables_are_keyed_by_id_in_mw(result: DcPowerFlowResult) -> None:
    theta, p_from, p_inj = dense_dc()
    buses = {b.id: b for b in result.buses}
    branches = {b.id: b for b in result.branches}
    gens = {g.id: g for g in result.generators}
    assert list(buses) == ["bus-1", "bus-2", "bus-3"]
    assert list(branches) == ["br-12", "xf-23", "br-13"]
    assert list(gens) == ["gen-1a", "gen-1b", "gen-2"]
    assert buses["bus-1"].va_deg == 0.0
    assert buses["bus-3"].va_deg == pytest.approx(math.degrees(theta[2]), abs=1e-10)
    assert buses["bus-3"].p_mw == pytest.approx(p_inj[2] * BASE, abs=1e-9)
    assert branches["xf-23"].p_from_mw == pytest.approx(p_from[1] * BASE, abs=1e-9)
    assert gens["gen-2"].p_mw == pytest.approx(40.0, abs=1e-9)


def test_dc_specific_fields(result: DcPowerFlowResult) -> None:
    assert result.converged is True
    assert all(b.vm_pu == 1.0 for b in result.buses)
    assert all(b.q_mvar == 0.0 for b in result.buses)
    assert all(b.in_service for b in result.buses)
    assert [b.role_effective for b in result.buses] == ["slack", "pv", "pq"]
    assert all(br.q_from_mvar == 0.0 and br.q_to_mvar == 0.0 for br in result.branches)
    assert all(br.p_to_mw == -br.p_from_mw for br in result.branches)
    assert all(g.q_mvar == 0.0 and g.q_limited == "none" for g in result.generators)


def test_loading_pct_only_where_a_rating_exists(result: DcPowerFlowResult) -> None:
    branches = {b.id: b for b in result.branches}
    rated = branches["xf-23"]
    assert rated.loading_pct == pytest.approx(abs(rated.p_from_mw) / 60.0 * 100.0, abs=1e-9)
    assert branches["br-12"].loading_pct is None
    assert branches["br-13"].loading_pct is None


def test_branch_endpoints_are_ids(result: DcPowerFlowResult) -> None:
    xf = next(b for b in result.branches if b.id == "xf-23")
    assert (xf.from_bus, xf.to_bus) == ("bus-2", "bus-3")


def test_zero_reactance_branch_is_a_named_error() -> None:
    net = three_bus()
    net.branches[0].x = 0.0
    with pytest.raises(ValueError, match="x == 0"):
        solve_dc(net)
