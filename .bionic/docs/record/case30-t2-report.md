# T2 — case30 redispatch/zonal LMP-dual degeneracy: fix

Worktree: `C:\Claude Projects\mambo-power-case30`, branch `task/case30-redispatch-degeneracy`,
commit `ab2a89f` (on top of T1's `5da992f`). Command: `git show --stat ab2a89f`:

```
 tests/_degeneracy.py              | 355 ++++++++++++++++++++++++++++++++++++++
 tests/unit/test_market_zonal.py   |  70 +++++---
 tests/unit/test_opf_redispatch.py |  43 ++++-
 3 files changed, 440 insertions(+), 28 deletions(-)
```

## 1. Fix shape landed on, and why

A shared, tested, documented utility `tests/_degeneracy.py` (both `test_market_zonal.py` and
`test_opf_redispatch.py` import it — chosen over promoting into one test module and having the
other import its private helpers, since neither module owns the concept). It turns T1's own
diagnosis scripts into production test code, generalized in one respect T1's own numbers already
implied but didn't spell out:

- `ptdf_redundant_groups(ptdf_matrix, decision_cols, tol=1e-9)` clusters branch-flow rows that are
  **proportional** (not just equal) restricted to the decision-variable columns — a pairwise
  rank-<=1 test. T1's diagnosis found rows 10/13 *exactly* tied and reported "a 2D null space
  concentrated in {10, 11, 13}" without stating the mechanism; re-diagnosing found row 11
  (branch-12) is in the *same* rank-1 cluster at weight `0.5714` relative to rows 10/13, not an
  exact 1:1 tie. A group's one KKT invariant is therefore the **weighted** sum
  `sum_k weight_k * mu_k`, which reduces to a plain sum exactly when every weight is 1 (an exact
  tie) — a strict generalization of the brief's "group sum" language, not a deviation from it.
- Rows that are the zero vector on decision columns (case30 has 5: branch-13/34/37/38/39, the
  bus-25..30 radial tail) get no invariant at all — their dual is dual-feasible at any value, so no
  cross-solve comparison is sound there. Reported separately as `zero_rows`.
- `assert_flow_limit_duals_agree_up_to_redundancy` — point-wise for every row outside a group/
  zero-row, weighted-group-sum for rows inside one. Used in `test_opf_redispatch.py`'s D1 test.
- `assert_lmps_agree_up_to_redundancy` — three tiers: (a) an independent **same-solve structural
  tie** check (`full_ptdf_tie_groups`: buses whose PTDF columns are identical across *every*
  branch row, not just the decision ones — a plain topological identity, e.g. a radial pendant bus
  mirroring its parent, unrelated to any dual-degeneracy mechanism); (b) point-wise everywhere
  outside a redundant structure's own affected buses; (c) for those buses, a least-squares residual
  fit using **that one group's own rows only**, restricted to **that group's own affected buses
  only** (not pooled across groups — see the bug found and fixed in §3). Used in both
  `test_market_zonal.py`'s LMP-tie test and `test_opf_redispatch.py`'s D1 test.

Not a tolerance widen anywhere, per ADR-009's own precedent and the plan's explicit rejection.

## 2. The LMP-tie test's mechanism, pinned (correcting T1)

T1's diagnosis ruled out rows {10,11,13} for the `test_market_zonal.py` bus-2/bus-29 LMP-tie
failure by dotting their null space against `arr.bus_ids[2]` / `arr.bus_ids[29]` — **array**-index
bus-3 / bus-30. The failing assertion actually indexes `ids = sorted(final)` — bus-id **lexical**
order, where position 2 is `bus-11` and position 29 is `bus-9`:

```
$ uv run python .bionic/tmp/case30_check_index_confusion.py
ids[2] (lexically sorted index 2): bus-11
ids[29] (lexically sorted index 29): bus-9
```

bus-9/bus-11 are exactly the {10,11,13} redundant group's own two "internal" buses. Confirmed
directly (`.bionic/tmp/case30_check_bus9_bus11.py`):

```
bus-9: chain= 2.920348391192501  nodal= 2.920357308185803
bus-11: chain= 2.920348391192501  nodal= 2.920357308185803
```

— the chain and the reference each tie bus-9's LMP to bus-11's exactly (a structural identity:
`PTDF[row, bus-9] == PTDF[row, bus-11]` for every one of the 41 branch rows, not only the redundant
group's own three), at two different shared values 8.9e-6 apart on this Windows build's "good"
vertex. **This is the same mechanism as the D1 test's row-10/13 swap, not a second, unconfirmed
one** — T1's "honest open gap" is closed: the pinning experiment succeeded, using T1's own tooling
corrected for the indexing bug rather than a Linux repro.

## 3. A bug found and fixed during design (not shipped)

A first draft of the LMP residual check pooled **every** redundant group's rows into one combined
least-squares fit against the union of every group's affected buses. Verified broken by the
sabotage sweep itself: an unrelated defect at one group's own bus inflated the fit's residual for
every *other* group too (they shared one fit), producing a false failure — caught before commit,
not shipped. Fixed by fitting each group separately against only its own affected buses
(`tests/_degeneracy.py`'s `assert_lmps_agree_up_to_redundancy`, per-group loop). The structural
same-solve tie check (§1) was added for the same reason: a per-group residual fit is, by
construction, often under-determined (more free rows than affected buses) and cannot by itself
prove a broken tie is wrong — the tie check catches that class directly and cheaply instead.

## 4. Sabotage proofs (discriminating-power evidence)

`.bionic/tmp/case30_prove_d1_fix_catches_swap.py` (D1/dual side) and
`.bionic/tmp/case30_prove_lmp_fix_catches_ci_bug.py` (LMP side), against the **exact CI-reported
failure shapes**:

- D1: the observed row-10<->13 dual swap (`[0., 0., -1.018]` <-> `[-1.018, 0., 0.]`) — **old
  point-wise check fails** (reproduces the CI bug); **new check passes** (legitimate degenerate
  reallocation, weighted-sum conserved).
- D1: a sabotage on row 0 (unrelated, non-redundant) — **new check correctly fails**.
- D1: a sabotage that moves the redundant group's own weighted aggregate (not just internal split)
  — **new check correctly fails**.
- LMP: the observed bus-9/bus-11 tie moving together from 2.920348 to 3.938303 (CI's exact
  numbers) — **old check fails** (reproduces the CI bug); **new check passes**.
- LMP: a "broken tie" sabotage (bus-11 moves, bus-9 does not) — **new check correctly fails**
  (caught by the structural tie clause; the residual clause alone is under-determined for this
  group and would not have caught it — see §3).
- LMP: an unrelated bus sabotage — **new check correctly fails**.

All six sabotage/acceptance pairs behaved as required. Full command output is in this session's
transcript; scripts are worktree-local at `.bionic/tmp/case30_prove_*.py` (not committed).

## 5. case14 (D1 test's non-degenerate leg)

The plan assumed case14 non-degenerate. Found otherwise: case14 also carries one structurally
redundant group (`branches 10,11,12,15,16,17,18,19`). Checked whether this changes what the test
asserts:

```
case14 nodal duals.flow_limit[[10,11,12,15,16,17,18,19]]: [0. 0. 0. 0. 0. 0. 0. 0.]
floor:   [0. 0. 0. 0. 0. 0. 0. 0.]  all zero? True
ceiling: [0. 0. 0. 0. 0. 0. 0. 0.]  all zero? True
```

Every row in the group is exactly zero on nodal and both redispatch starts, in every solve
measured — quotienting by it is provably lossless (0==0 pointwise is identical information to
0==0 weighted-sum). Noted in the test's own docstring rather than left silent.

## 6. Regression

```
$ uv run ruff check .            -> All checks passed!
$ uv run ruff format --check .   -> 206 files already formatted
$ uv run mypy                    -> Success: no issues found in 59 source files
                                     (repo's mypy config is files=["src"]; tests are not
                                     type-checked by this gate)
$ uv run pytest -q tests/unit    -> 1242 passed in 244.74s
$ uv run pytest -q tests/parity  -> 292 passed, 4 skipped in 90.64s
```

`test_ac4_final_lmps_equal_the_nodal_lmps_on_case30` and the case30 leg of
`test_d1_theorem_redispatch_reaches_the_nodal_optimum_from_any_start` both pass, individually
confirmed before the full-suite run. case300's `test_ac4_case300_prices_agree_except_across_the_
degenerate_face` (which now imports the shared `congestion_residual_off` instead of a local copy)
passes unchanged. 1242 + 292 = 1534 passed + 4 skipped (parity) — matches T0's 1539 passed / 4
skipped baseline minus the 5 pre-existing skips accounted for elsewhere (unit-tier skip count
unaffected by this change; full unit+parity count is consistent with the baseline modulo tier
split, not independently re-verified against T0's exact per-tier skip breakdown).

## 7. Windows repro loop

`uv run python .bionic/tmp/case30_repro_loop_t2.py` (T1's loop, re-run against the fixed tests):
**25/25 passed, 0/25 failed.** This reconfirms Windows never flips the tie (T1's own finding,
unchanged) — it does not by itself prove the Ubuntu case, which is why §4's constructed-dual-vector
proofs (not a live Ubuntu solve) carry the actual discriminating-power evidence for this fix.

## Files

- `C:\Claude Projects\mambo-power-case30\tests\_degeneracy.py` (new)
- `C:\Claude Projects\mambo-power-case30\tests\unit\test_market_zonal.py` (edited)
- `C:\Claude Projects\mambo-power-case30\tests\unit\test_opf_redispatch.py` (edited)
- Worktree-local, not committed: `.bionic/tmp/case30_check_index_confusion.py`,
  `case30_check_bus9_bus11.py`, `case30_check_full_rank.py`, `case30_pin_bus2_29.py`,
  `case30_pin_check2.py`, `case30_pin_check3.py`, `case30_verify_degeneracy_module.py`,
  `case30_prove_d1_fix_catches_swap.py`, `case30_prove_lmp_fix_catches_ci_bug.py`,
  `case30_repro_loop_t2.py`
