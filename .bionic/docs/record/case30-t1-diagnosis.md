# T1 — case30 redispatch/zonal LMP-dual degeneracy: diagnosis

Worktree: `C:\Claude Projects\mambo-power-case30`, branch `task/case30-redispatch-degeneracy`,
HEAD `5da992f`. Diagnosis only — no test or source file touched. All scratch scripts referenced
below live at `.bionic/tmp/case30_diag*.py` and `.bionic/tmp/case30_repro_loop.py` in that
worktree (not committed).

## 1. Windows reproduction loop

`uv run python .bionic/tmp/case30_repro_loop.py` ran
`test_market_zonal.py::test_ac4_final_lmps_equal_the_nodal_lmps_on_case30` and
`test_opf_redispatch.py::test_d1_theorem_redispatch_reaches_the_nodal_optimum_from_any_start`
as 25 independent fresh `pytest` subprocesses.

**Result: 25/25 passed, 0 failed.** Windows never flips the tie across 25 fresh-process solves —
consistent with the tie-break being deterministic per platform/build, not genuinely random.

## 2. Primal degeneracy — confirmed and exactly located

`fixtures/matpower/case30.m`'s `mpc.gencost` carries genuine nonzero quadratic coefficients for
all 6 generators (0.02, 0.0175, 0.0625, 0.00834, 0.025, 0.025), so `dc_opf`/`redispatch_dc_opf`
build a strictly-convex QP (real diagonal Hessian), not a pure LP — confirmed by reading
`_pass_diagonal_hessian` in `src/mambo_power/opf/dc_opf.py`.

At the case30 redispatch/nodal optimum (`_elastic_network("case30")`, floor-start
`redispatch_dc_opf`), branches `branch-11` (PTDF/flow-limit row 10), `branch-12` (row 11) and
`branch-14` (row 13) sit **simultaneously and exactly at their own rating**:

```
row 10: branch-11  f=bus-6  t=bus-9   flow=5.759241286665455  rating=5.759241286665459  overload=3.6e-15
row 11: branch-12  f=bus-6  t=bus-10  flow=3.290995...        rating=3.290995...        overload=1.8e-15
row 13: branch-14  f=bus-9  t=bus-10  flow=5.759241286665455  rating=5.7592412866654525 overload=2.7e-15
```

(overload measured via the independent `pf.dc` readback, `RedispatchSolution.branch_flow_mw`,
not the LP's own rows.)

This is not coincidence. Bus-9 (`arr.bus_ids[8]`) carries **zero net injection**: no generator,
no load, no shunt (`gens at bus-9: []`, `loads at bus-9: []`, `p_load_pu[8]=0.0`,
`g_shunt_pu[8]=0.0`), and sits between branch-11 (bus-6→bus-9) and branch-14 (bus-9→bus-10).
Restricted to the PTDF columns any decision variable (a generator's bus or an elastic load's bus)
actually touches, row 10 and row 13 are **identical to 1.2e-17**:

```
buses touched by decision variables: [0, 1, 2, 3, 6, 7, 12, 21, 22, 26]   (bus-9 = idx 8 not among them)
max|row10 - row13| restricted to those columns: 1.214306433183765e-17
full max|row10-row13| (all 30 bus columns): 0.9999999999999999   -- only column 8 (bus-9 itself) differs, by exactly 1.0
```

i.e. the only column the two rows disagree on is the one column no generator or elastic load ever
multiplies (the standard PTDF self-column identity: `PTDF[k, from(k)] - PTDF[k, to(k)] = 1`).

Restricting the 6-row active set `{0, 10, 11, 13, 19, 25}` (all branches within 1e-2 MW of rating
at this optimum) to the same decision-variable columns gives a matrix of **rank 4, not 6**:

```
singular values: [2.057, 0.620, 0.233, 0.091, 3.6e-17, 1.6e-17]
```

— a genuine 2-dimensional null space, concentrated in `{10, 11, 13}` (rows 0/19/25 carry ~0
weight in both near-zero singular vectors). This is the algebraic signature of dual
non-uniqueness: HiGHS has real, KKT-legitimate freedom in how the ≈1.018 $/MWh combined shadow
price on this bottleneck is distributed among rows 10, 11 and 13.

A full pairwise scan of all 41 branches found **19 branch pairs** in this fixture with
exactly-redundant PTDF rows on the decision-variable columns (script:
`.bionic/tmp/case30_diag8.py`), including a second, separate radial family at the network's
bus-25→26→27→29→30 tail (rows 33/34/36/37/38 — branch-34/37/38/39 — all pairwise identical to
≤1.4e-15). case30's rated topology is broadly riddled with this kind of redundancy, not a single
isolated coincidence.

## 3. Both dual vectors are legitimate optima

Four independent solves — `dc_opf` nodal, and `redispatch_dc_opf` from three unrelated starting
points (bound floor, bound ceiling, the AC-3 zonal-relaxed start) — **all four**, on this Windows
build, place the dual mass on row 13 and leave rows 10/11 at exactly zero:

```
nodal:        duals[10,11,13] = [ 0.,  0., -1.01794604]
floor:        duals[10,11,13] = [ 0.,  0., -1.01794604]
ceiling:      duals[10,11,13] = [ 0.,  0., -1.01795527]
zonal-ish:    duals[10,11,13] = [ 0.,  0., -1.01795275]
```

agreeing among themselves to ~1e-5 $/MWh (ordinary solver noise, not a real reallocation) — never
the CI-reported full 0.0-vs-(-1.018) swap.

24 microscopic cost perturbations (±1e-9 and ±1e-7 relative on generator linear cost coefficient
`c1`, one generator at a time, all 6 generators) were resolved independently
(`.bionic/tmp/case30_diag6.py`). All 24 kept the *same* row-13-only assignment (dual10=dual11=0.0
to displayed precision in every case). Primal dispatch moved at most 9.4e-6 MW and objective at
most ~2e-5 $/h across all 24 — the primal is essentially rigid, matching ADR-009's own case300
signature ("primal agrees to a tight tolerance... only the dual moves").

**Not run:** the requested simplex-vs-IPM cross-check. Neither `dc_opf.py` nor `redispatch.py`
sets any solver-algorithm option (`grep` confirms the only option set anywhere is
`h.setOptionValue("output_flag", False)`; `h.getOptionValue("solver")` reports `"choose"`, HiGHS's
auto default). Because this is a QP (real Hessian), HiGHS routes to its QP solver rather than the
LP simplex/IPM path, so the LP-only `kSimplex`/`kIpm` switch does not directly apply. A quick scan
of `highspy.Highs().getOptions()` found `qp_regularization_value=1e-7` and `kkt_tolerance=1e-7`
but no obvious QP algorithm-choice knob — left as an unexplored angle rather than assumed absent.

**Caveat:** everything above proves the degenerate face exists and is real (rank-deficiency is
exact algebra, not measurement). It does not prove Windows and Ubuntu sit on *different* vertices
of it — every experiment run here landed on the same vertex (row 13 carries the dual). Confirming
the actual Ubuntu vertex needs either that CI run's own dual vector or a Linux highspy 1.15.1
build to solve on; neither is available in this Windows worktree.

## 4. Old fixture, new finding

`git log -S"CASE30_LMP_ATOL" -- tests/unit/test_market_zonal.py` shows the constant and the test
were both introduced together in `f1782e8` (M6/S5), with the docstring at introduction reading:

> `CASE30_LMP_ATOL = 1e-3` — "AC-4's LMP agreement on rated case30, $/MWh. Measured: 8.92e-6 on
> prices of order 6.8 $/MWh. Deliberately *not* applied to case300 (A20): there the same
> measurement is 0.32 $/MWh, and it is degeneracy rather than disagreement — see the structural
> test that replaces it."

This shows the test's author explicitly believed case30 (unlike case300) was **not**
degenerate at authoring time, and sized the 1e-3 tolerance (100x headroom over one measured
8.92e-6 run) for ordinary floating-point noise, not for a vertex swap. This diagnosis shows that
belief was incorrect: case30 carries the same class of degeneracy as case300 (§2 above), just not
exercised on whichever machine authored/first-CI'd that commit. **Verdict: blind luck, not
deliberate headroom** — the gap was never sized against a real dual-vertex swap (~1.02 $/MWh,
three orders above the pinned tolerance) because the tie never broke the other way until Ubuntu's
highspy build did.

## 5. Plain verdict

**Genuine LP/QP dual degeneracy, not a correctness bug**, for the `test_opf_redispatch.py` D1
theorem failure — proven by exact algebra (rank deficiency of the restricted active-constraint
matrix, §2), not merely by measurement. Precisely located: branch-11/branch-12/branch-14 around
bus-9, a zero-injection node that makes two of the three branches' flow-limit rows literally
redundant constraints, combined with `tests/_rated.py`'s rating derivation apparently pinning all
three branches' ratings from the same base-case flow (their measured ratings coincide to ~1e-15
relative).

For `test_market_zonal.py`'s bus-2/bus-29 LMP tie specifically: the same `{10,11,13}` redundancy
is **provably not** the cause — both of its null-space directions dot to exactly 0 (~1e-17)
against bus-2's and bus-29's own PTDF columns, so reallocating dual mass among those three rows
cannot move either bus's LMP at all (`.bionic/tmp/case30_diag5.py`,`case30_diag4.py`). My Windows
repro of that exact test also lands on the "good" vertex (chain vs. nodal LMP agree to 4.4e-6,
comfortably inside tolerance), so I never observed whichever alternate active set Ubuntu hits. A
second, separate redundant family sits in bus-29's own neighborhood (rows 36/37/38 =
branch-37/38/39, the bus-25→…→30 radial tail; branch-39 terminates at bus-30, adjacent to
bus-29) but none of those branches are at rating on this Windows solve, so I cannot confirm it is
the active one either.

**Honest open gap:** I am confident the LMP-tie failure is the same *class* of defect (case30's
topology holds 19 structurally-redundant branch pairs, any one of which is a legitimate
mechanism for a platform-dependent LMP tie) but could not pin down which specific redundancy
Ubuntu's solve activates without either that CI run's own numbers or a Linux repro. That is the
one experiment the plan asked for that I could not complete, and I am naming it rather than
guessing.

## Scripts (worktree-local, not committed)

- `.bionic/tmp/case30_repro_loop.py` — 25x fresh-process reproduction loop (§1)
- `.bionic/tmp/case30_diag.py` — floor/ceiling redispatch vs nodal flow-limit dual comparison
- `.bionic/tmp/case30_diag2.py` / `case30_diag3.py` — at-rating branch/bus topology inspection
- `.bionic/tmp/case30_diag4.py` — exact PTDF row-redundancy proof and null-space/rank analysis (§2)
- `.bionic/tmp/case30_diag5.py` — market_zonal chain LMP tie vs rows-10/13 redundancy cross-check
- `.bionic/tmp/case30_diag6.py` — 24-perturbation cost-coefficient sensitivity sweep (§3)
- `.bionic/tmp/case30_diag7.py` — three-starting-point dual comparison + HiGHS QP option scan (§3)
- `.bionic/tmp/case30_diag8.py` — full 41-branch pairwise PTDF-redundancy scan (§2, §5)
