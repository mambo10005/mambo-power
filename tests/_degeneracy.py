"""PTDF-row redundancy detection for LP/QP dual degeneracy (ADR-009's case300 finding, extended to
case30 -- ``.bionic/docs/record/case30-t1-diagnosis.md`` and its T2 follow-up). Turns T1's own
diagnostic scripts (``.bionic/tmp/case30_diag*.py``, worktree-local, not committed) into a tested,
documented utility both ``test_market_zonal.py`` and ``test_opf_redispatch.py`` import, rather than
each carrying its own copy or one importing the other's private helpers.

**Why this exists.** A DC-OPF flow-limit row's coefficient on any decision variable (a generator or
an elastic load) comes only from the PTDF columns those variables' buses sit in --
``decision_cols`` below. When two or more branch-flow rows are linearly dependent restricted to
those columns, the LP/QP has real, KKT-legitimate freedom in how it splits their combined shadow
price among the rows: any redistribution that keeps the *dependent combination* fixed leaves every
decision variable's stationarity condition, and therefore the primal optimum, exactly where it was.
HiGHS's own tie-breaking (basis choice) then becomes solver/platform/build-dependent, which is what
surfaces as a flaky dual (and LMP) mismatch between two independently-solved LPs on the same
network -- proven, not assumed, for case30's rows 10/11/13 (below) and case300 (A20).

**Two structurally different degenerate shapes, both handled here.**

* A cluster of two or more rows whose restriction to ``decision_cols`` spans a common 1-D
  direction -- *proportional*, not merely equal. T1's diagnosis found branch-11/branch-14 (rows
  10/13) exactly tied (weight 1:1); re-diagnosing for this task found branch-12 (row 11) is *also*
  in the same rank-1 cluster at weight ``0.5714``, not tied 1:1 -- T1's own rank-4-of-6 / 2D
  null-space finding already implied this (a 3-row, rank-1 set has a 2D null space), it just wasn't
  spelled out as a weighted relationship. The one real KKT invariant for such a cluster is the
  *weighted* sum ``sum_k weight_k * mu_k``, not a plain sum -- a plain sum is only correct when
  every member's weight happens to be 1, which is what an *exact* tie looks like from here.
* A row that is the zero vector on ``decision_cols`` -- no decision variable's injection reaches it
  at all, so its dual contributes nothing to any stationarity condition and is dual-feasible at
  *any* nonnegative value. No cross-solve invariant is derivable from KKT for a lone such row; where
  it has nonzero PTDF entries on buses outside ``decision_cols`` (case30's branch-13/34/37/38/39,
  the bus-25..30 radial tail), those buses' LMP is likewise unconstrained by the theorem and is
  excluded from the point-wise comparison rather than asserted equal by luck.

**The re-diagnosis this module's design rests on.** T1's own diagnosis of the
``test_market_zonal.py`` LMP-tie failure ruled out rows 10/11/13 by dotting their null space against
``arr.bus_ids[2]`` and ``arr.bus_ids[29]`` -- *array*-index bus-3 and bus-30. But the failing
assertion there indexes ``sorted(final)`` (bus-*id-string* lexical order), where position 2 is
``bus-11`` and position 29 is ``bus-9`` -- exactly the two buses rows 10/11/13's redundancy pins
together (PTDF[row, bus-9] == PTDF[row, bus-11] for every row, to 1e-15, independent of the
redundancy: bus-11 is a radial continuation of bus-9). Confirmed by direct measurement on this
worktree (``.bionic/tmp/case30_check_bus9_bus11.py``): the chain and nodal solves each tie
``bus-9``'s LMP to ``bus-11``'s exactly, at two different values 8.9e-6 apart on this Windows
build's "good" vertex -- the same magnitude and mechanism as ``test_opf_redispatch.py``'s D1
failure, not a second, unpinned one. T1's own honest-gap framing (same *class*, mechanism
unconfirmed) undersold it: it is the *same* cluster.

**Deliberately not attempted:** a cluster whose joint rank exceeds 1 without any two members being
pairwise proportional (a genuine multi-dimensional dependency not reducible to one shared
direction). Every redundant cluster found in case30's or case300's fixtures at the time of writing
is rank 0 or rank 1 (``.bionic/tmp/case30_diag8.py`` and this module's own re-scan); a future
fixture that needed more would want T1's full SVD-null-space treatment, generalized here only as
far as the cases actually observed.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field

import numpy as np
import numpy.typing as npt
import pytest

FloatArray = npt.NDArray[np.float64]

DECISION_COLUMN_TOL = 1e-9
"""Tie/rank tolerance for PTDF-row redundancy on the decision-variable columns, in PTDF units
(dimensionless flow-per-injection sensitivity). T1's diagnosis measured exact ties at ~1e-17 and
the nearest non-tied pair 7-8 orders above that (rank gap: singular values 3.6e-17 vs 0.091 on the
6-row active set) -- this sits deep inside that gap, nowhere near ordinary solver noise (~1e-9 on
the dispatch, which is what could plausibly blur a *true* tie into a near-tie)."""


@dataclass(frozen=True)
class RedundantGroup:
    """A cluster of branch-flow rows tied to one shared direction on the decision-variable columns.

    ``rows[0]`` is the arbitrary reference row; ``weights[k]`` is ``rows[k]``'s own scale relative
    to it (``restricted[rows[k]] == weights[k] * restricted[rows[0]]`` to
    :data:`DECISION_COLUMN_TOL` on the decision-variable columns the group was built from).
    ``weights[0] == 1.0`` always. The group's one KKT-conserved invariant is
    ``sum_k weights[k] * mu[rows[k]]``.
    """

    rows: list[int]
    weights: list[float] = field(default_factory=list)


def decision_variable_bus_columns(
    gen_bus: Sequence[int], elastic_load_bus: Sequence[int]
) -> list[int]:
    """Bus column indices any decision variable (a generator or an elastic load) actually
    multiplies in the PTDF -- the columns a flow-limit row's coefficient on a decision variable can
    ever come from, so the columns two rows must agree on to be redundant for *any* LP/QP this
    package builds."""
    return sorted({int(b) for b in gen_bus} | {int(b) for b in elastic_load_bus})


def ptdf_redundant_groups(
    ptdf_matrix: FloatArray, decision_cols: Sequence[int], *, tol: float = DECISION_COLUMN_TOL
) -> tuple[list[RedundantGroup], list[int]]:
    """``(groups, zero_rows)`` -- the structural redundancy of ``ptdf_matrix``'s branch-flow rows,
    restricted to ``decision_cols``. Purely a property of the network's PTDF and which buses carry
    decision variables; independent of any solve's dual output, so it can be computed once from
    either side of a comparison (they share the same PTDF when built from the same network arrays).

    Rows are clustered greedily: row ``j`` joins row ``i``'s cluster when the 2-row stack
    ``[restricted[i], restricted[j]]`` has rank <= 1 (a pairwise proportionality test that catches
    both exact ties and T1's weighted case in one test, since a rank-1 cluster's members are
    pairwise proportional to *any* one of them, including the first). A row whose own restricted
    norm is <= ``tol`` -- the zero vector, no decision variable reaches it -- is reported separately
    in ``zero_rows`` rather than folded into a group: it carries no invariant to assert (see module
    docstring), and a zero row is trivially "proportional" to everything, which would otherwise
    swallow unrelated clusters into one meaningless group.
    """
    restricted = np.asarray(ptdf_matrix, dtype=np.float64)[:, list(decision_cols)]
    n = restricted.shape[0]
    norms = np.linalg.norm(restricted, axis=1)
    zero_rows = [i for i in range(n) if norms[i] <= tol]
    assigned = [False] * n
    for i in zero_rows:
        assigned[i] = True
    groups: list[RedundantGroup] = []
    for i in range(n):
        if assigned[i]:
            continue
        members = [i]
        for j in range(i + 1, n):
            if assigned[j]:
                continue
            pair = restricted[[i, j], :]
            if np.linalg.matrix_rank(pair, tol=tol) <= 1:
                members.append(j)
        if len(members) > 1:
            for m in members:
                assigned[m] = True
            ref = restricted[members[0]]
            weights = [float(np.dot(restricted[m], ref) / np.dot(ref, ref)) for m in members]
            groups.append(RedundantGroup(rows=members, weights=weights))
        else:
            assigned[i] = True
    return groups, zero_rows


def assert_flow_limit_duals_agree_up_to_redundancy(
    actual: FloatArray,
    expected: FloatArray,
    groups: Sequence[RedundantGroup],
    zero_rows: Sequence[int],
    *,
    atol: float,
    label: str = "",
) -> None:
    """D1's dual-side theorem (and case300's A20 analogue), quotiented by known PTDF-row
    redundancy. Point-wise for every row outside a redundant group or the zero-row set; for a
    redundant group, the KKT-invariant quantity is the group's own *weighted* aggregate dual mass
    (:class:`RedundantGroup`), not each row's individual share of it -- HiGHS has real, legitimate
    freedom in how that shared shadow price is attributed among the group's rows. A zero row's dual
    is dual-feasible at any value (module docstring); no assertion is made about it at all.

    Sabotage-resistant by construction: a real defect moving dual mass *out of* a redundant group,
    or getting the group's own weighted sum wrong, still fails; a defect anywhere outside a known
    group or the zero-row set still fails the point-wise clause exactly as before.
    """
    actual = np.asarray(actual, dtype=np.float64)
    expected = np.asarray(expected, dtype=np.float64)
    excluded = set(zero_rows) | {row for group in groups for row in group.rows}
    for i in range(actual.shape[0]):
        if i in excluded:
            continue
        assert actual[i] == pytest.approx(expected[i], abs=atol), (
            f"{label}row {i}: {actual[i]!r} != {expected[i]!r} "
            "(not part of any known-redundant group)"
        )
    for group in groups:
        weights = np.asarray(group.weights, dtype=np.float64)
        actual_sum = float(np.dot(weights, actual[group.rows]))
        expected_sum = float(np.dot(weights, expected[group.rows]))
        assert actual_sum == pytest.approx(expected_sum, abs=atol), (
            f"{label}redundant group rows={group.rows} weights={group.weights}: weighted dual "
            f"mass {actual_sum!r} != {expected_sum!r}"
        )


def _group_internal_buses(
    ptdf_matrix: FloatArray, group: RedundantGroup, *, tol: float = DECISION_COLUMN_TOL
) -> set[int]:
    """Bus columns where one redundant group's own weighted-proportionality breaks -- necessarily
    outside ``decision_cols`` by construction of :func:`ptdf_redundant_groups`. Only at these buses
    can redistributing dual mass *within this group* move the LMP; every other bus's contribution
    from this group is pinned by the group's own conserved invariant times a fixed structural
    coefficient."""
    matrix = np.asarray(ptdf_matrix, dtype=np.float64)
    ref_row = matrix[group.rows[0]]
    internal: set[int] = set()
    for member, weight in zip(group.rows, group.weights, strict=True):
        residual = matrix[member] - weight * ref_row
        internal |= set(np.flatnonzero(np.abs(residual) > tol).tolist())
    return internal


def redundant_group_internal_buses(
    ptdf_matrix: FloatArray,
    groups: Sequence[RedundantGroup],
    zero_rows: Sequence[int],
    *,
    tol: float = DECISION_COLUMN_TOL,
) -> set[int]:
    """Union, over every group and zero row, of the buses only *that* structure can move -- the
    buses point-wise LMP equality must not be asserted at. See :func:`_group_internal_buses` for a
    single group's own set and why the *union* is not what the residual check below fits against
    (pooling every group's rows into one fit would let one group's rows spuriously "explain" a
    disagreement that lives at another group's bus -- caught by this module's own sabotage sweep;
    :func:`assert_lmps_agree_up_to_redundancy` fits each group separately instead).
    """
    matrix = np.asarray(ptdf_matrix, dtype=np.float64)
    internal: set[int] = set()
    for group in groups:
        internal |= _group_internal_buses(matrix, group, tol=tol)
    for row in zero_rows:
        internal |= set(np.flatnonzero(np.abs(matrix[row]) > tol).tolist())
    return internal


def full_ptdf_tie_groups(
    ptdf_matrix: FloatArray, *, tol: float = DECISION_COLUMN_TOL
) -> list[list[int]]:
    """Buses (PTDF columns) that are *structurally* identical across every branch row -- not just
    the decision-variable ones. This is a stronger, simpler, degeneracy-independent fact than a
    :class:`RedundantGroup`: a bus with exactly one connecting branch and no decision variable of
    its own (a radial pendant, e.g. case30's bus-11 hanging off bus-9) mirrors its neighbour's LMP
    in *every* optimal solution, not only up to some known freedom. Two solves must agree with each
    other on this identity even where they disagree with one another on the shared value -- which
    is exactly what :func:`assert_lmps_agree_up_to_redundancy` checks it for, tightly, before ever
    reaching for the looser redundant-group reasoning.
    """
    matrix = np.asarray(ptdf_matrix, dtype=np.float64)
    n_bus = matrix.shape[1]
    assigned = [False] * n_bus
    groups: list[list[int]] = []
    for i in range(n_bus):
        if assigned[i]:
            continue
        members = [i]
        for j in range(i + 1, n_bus):
            if assigned[j]:
                continue
            if np.max(np.abs(matrix[:, i] - matrix[:, j])) <= tol:
                members.append(j)
        if len(members) > 1:
            for m in members:
                assigned[m] = True
            groups.append(members)
        else:
            assigned[i] = True
    return groups


def congestion_residual_off(
    difference: FloatArray, ptdf_matrix: FloatArray, branch_rows: Sequence[int]
) -> float:
    """Sup-norm of what is left of a per-bus ``difference`` vector after the best least-squares fit
    by flow duals confined to ``branch_rows``. Shared with ``test_market_zonal.py``'s case300
    clause (A20/ADR-009) -- both fixtures' degeneracy checks use the same helper rather than two
    independently-maintained copies of the same fit.

    A congestion component is by construction ``PTDFᵀ mu`` for a dual vector ``mu`` supported on the
    binding branches, so two solves' congestion components differ by ``PTDFᵀ(mu_a − mu_b)``. Asking
    which branch rows can reproduce that difference asks *where the two solvers disagreed*, and a
    least-squares fit answers it without either solver having to hand over its dual vector.
    """
    if not branch_rows:
        return float(np.max(np.abs(difference)))
    columns = np.asarray(ptdf_matrix, dtype=np.float64)[list(branch_rows), :].T
    coefficients, *_ = np.linalg.lstsq(columns, difference, rcond=None)
    return float(np.max(np.abs(columns @ coefficients - difference)))


def assert_lmps_agree_up_to_redundancy(
    actual: FloatArray,
    expected: FloatArray,
    ptdf_matrix: FloatArray,
    groups: Sequence[RedundantGroup],
    zero_rows: Sequence[int],
    *,
    atol: float,
    label: str = "",
) -> None:
    """AC-4's price-side theorem, quotiented the same way as the dual-side one above, in two tiers.

    1. **Structural ties** (:func:`full_ptdf_tie_groups`) are checked *within* each solve, tightly:
       buses that are always identical mirror each other in both ``actual`` and ``expected``
       regardless of which degenerate vertex either solve landed on. This is what catches a defect
       that breaks the tie itself -- a bug this design's first draft missed, since the loose
       cross-solve fit below is, by construction, unable to (a single redundant group's own
       observable freedom is generally under-determined by the bus differences it can explain, so
       fitting it proves only that *a* reallocation exists, never that the tie survived).
    2. Point-wise, everywhere except a redundant group's or zero-row's own internal buses
       (:func:`_group_internal_buses`); there, the disagreement must be reproducible as flow duals
       confined to *that one group's* own rows alone -- explained entirely by reallocation inside a
       cluster already proven degenerate, not by anything else, and not by a different cluster's
       rows either (each group is fit separately; see :func:`redundant_group_internal_buses`).

    Sabotage-resistant three ways: a real defect moving LMP mass to any bus outside the
    known-degenerate set fails the point-wise clause; a defect that gets a degenerate bus's LMP
    wrong by more than that bus's *own* group can explain fails the residual clause; a defect that
    breaks a structural tie outright fails the tie clause even though the other two, alone, cannot
    see it.
    """
    actual = np.asarray(actual, dtype=np.float64)
    expected = np.asarray(expected, dtype=np.float64)

    for tie in full_ptdf_tie_groups(ptdf_matrix):
        assert actual[tie] == pytest.approx(actual[tie][0], abs=atol), (
            f"{label}structurally tied buses {tie} disagree with each other in the actual result"
        )
        assert expected[tie] == pytest.approx(expected[tie][0], abs=atol), (
            f"{label}structurally tied buses {tie} disagree with each other in the reference"
        )

    internal = redundant_group_internal_buses(ptdf_matrix, groups, zero_rows)
    external = [i for i in range(actual.shape[0]) if i not in internal]
    if external:
        assert actual[external] == pytest.approx(expected[external], abs=atol), (
            f"{label}LMP disagreement at a bus no known-redundant row can explain"
        )

    difference = actual - expected
    matrix = np.asarray(ptdf_matrix, dtype=np.float64)
    for group in groups:
        group_internal = sorted(_group_internal_buses(matrix, group))
        if not group_internal:
            continue
        # Restricted to this group's *own* buses and *own* rows only -- fitting against the full
        # bus vector would let an unrelated sabotage elsewhere inflate every other group's residual
        # too (every group's least-squares problem shares the same difference vector otherwise),
        # which is exactly the false failure this module's own sabotage sweep caught in review.
        sub_difference = difference[group_internal]
        sub_ptdf = matrix[:, group_internal]
        residual = congestion_residual_off(sub_difference, sub_ptdf, group.rows)
        assert residual <= atol, (
            f"{label}LMP disagreement at group {group.rows}'s own buses {group_internal} is not "
            f"explained by reallocation within that group's rows alone -- residual {residual!r}"
        )
    for row in zero_rows:
        row_internal = sorted(np.flatnonzero(np.abs(matrix[row]) > atol).tolist())
        if not row_internal:
            continue
        sub_difference = difference[row_internal]
        sub_ptdf = matrix[:, row_internal]
        residual = congestion_residual_off(sub_difference, sub_ptdf, [row])
        assert residual <= atol, (
            f"{label}LMP disagreement at zero-row {row}'s own buses {row_internal} is not "
            f"explained by that row's own dual freedom alone -- residual {residual!r}"
        )
