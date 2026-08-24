"""AC-5 fixture: ``case14_pwl`` — case14 with two generators' costs converted to convex PWL (W4).

No MATPOWER-shipped fixture carries any MODEL-1 (piecewise) generator cost data
(record/m3-research.md §2.2: every ``gencost`` row in all five OPF fixtures is MODEL 2). This
derived fixture exists solely to exercise the OPF PWL-cost LP path (S3) against something
real; it is NOT attempted against OPF here — only the fixture's own well-formedness and
importability, per the wave plan's Slice S1 scope. Mirrors
``tests/unit/test_fixtures_derived.py``'s pattern for ``case14_roles``/``case14_island``: an
independent-reader raw-matrix diff proves the file is exactly ``case14.m`` plus the documented
``gencost`` edit.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np

from mambo_power.io import matpower
from mambo_power.model import PiecewiseCost, PolynomialCost
from tests._fixtures import FIXTURES_DIR
from tests.parity._mpc_reader import read_mpc_numpy

DERIVED_DIR = FIXTURES_DIR / "derived"
BASE = FIXTURES_DIR / "case14.m"

# gen-2 (bus 2, p_max_mw=140) and gen-3 (bus 3, p_max_mw=100) breakpoints, both convex
# (non-decreasing marginal cost between consecutive segments): gen-2 slopes 20, 25, 30 MW->$/h;
# gen-3 slopes 20, 30, 40 MW->$/h. See case14_pwl.m's header and PROVENANCE.md for the full
# cell-by-cell rationale.
GEN2_POINTS = [(0.0, 0.0), (40.0, 800.0), (90.0, 2050.0), (140.0, 3550.0)]
GEN3_POINTS = [(0.0, 0.0), (30.0, 600.0), (70.0, 1800.0), (100.0, 3000.0)]


def _raw(path: Path) -> dict[str, np.ndarray]:
    return {k: v for k, v in read_mpc_numpy(path).items() if isinstance(v, np.ndarray)}


def _pwl_row(points: list[tuple[float, float]]) -> list[float]:
    return [1.0, 0.0, 0.0, float(len(points)), *(v for pt in points for v in pt)]


def test_pwl_is_case14_plus_documented_gencost_edit() -> None:
    base = _raw(BASE)
    # mpc.gencost rows are rectangular (the importer requires uniform column width): every row
    # widens to 12 columns (MODEL, startup, shutdown, n, then 4 (x, y) pairs) with the original
    # MODEL-2 rows' trailing columns zero-padded — harmless, since MODEL 2 import only reads
    # `values[:n_cost]` and ignores anything after.
    widened = np.zeros((base["gencost"].shape[0], 12))
    widened[:, : base["gencost"].shape[1]] = base["gencost"]
    widened[1] = _pwl_row(GEN2_POINTS)  # row 2 (gen-2, bus 2): MODEL 2 -> MODEL 1
    widened[2] = _pwl_row(GEN3_POINTS)  # row 3 (gen-3, bus 3): MODEL 2 -> MODEL 1
    expected = {**base, "gencost": widened}
    _assert_same_matrices(_raw(DERIVED_DIR / "case14_pwl.m"), expected)


def _assert_same_matrices(ours: dict[str, np.ndarray], expected: dict[str, np.ndarray]) -> None:
    assert ours.keys() == expected.keys()
    for name in expected:
        np.testing.assert_array_equal(ours[name], expected[name], err_msg=name)


def test_header_names_base_and_purpose() -> None:
    head = (DERIVED_DIR / "case14_pwl.m").read_text(encoding="utf-8").split("mpc.version")[0]
    assert "function mpc = case14_pwl" in head
    assert "case14.m" in head and "SYNTHETIC" in head
    assert "AC-5" in head


def test_pwl_costs_survive_import() -> None:
    net = matpower.load(DERIVED_DIR / "case14_pwl.m")
    by_id = {g.id: g for g in net.generators}

    gen2_cost = by_id["gen-2"].cost
    assert isinstance(gen2_cost, PiecewiseCost)
    assert gen2_cost.points == GEN2_POINTS
    assert gen2_cost.startup == 0.0 and gen2_cost.shutdown == 0.0

    gen3_cost = by_id["gen-3"].cost
    assert isinstance(gen3_cost, PiecewiseCost)
    assert gen3_cost.points == GEN3_POINTS

    # the untouched generators keep their original polynomial costs
    for gen_id in ("gen-1", "gen-4", "gen-5"):
        assert isinstance(by_id[gen_id].cost, PolynomialCost)


def test_pwl_breakpoints_are_convex_non_decreasing_slope() -> None:
    for points in (GEN2_POINTS, GEN3_POINTS):
        slopes = [
            (points[i + 1][1] - points[i][1]) / (points[i + 1][0] - points[i][0])
            for i in range(len(points) - 1)
        ]
        assert slopes == sorted(slopes), f"non-convex slope sequence: {slopes}"
        assert len(set(slopes)) == len(slopes), "expected strictly increasing slopes"
