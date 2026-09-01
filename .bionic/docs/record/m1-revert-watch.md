# M1 revert-and-watch — record (relaunched run)

> **Relaunched run.** The previous test-runner died mid-task on a server error. This run was
> performed by a fresh runner (m1-revert-watch, 2026-08-20) that inherited an already-existing
> detached worktree at `C:\Claude Projects\mambo-power-audit` with the §2 stub already applied.
> The worktree was NOT re-created. Whether the previous runner had run `uv sync` or captured a
> baseline is unknown, so both were redone here from scratch (stub stashed for the baseline).
>
> Protocol: `.bionic/tmp/audit-revert-request.md` (auditor m1-auditor). Every claim below carries
> its command and trimmed output. `uv` = `C:\Users\mambo\AppData\Roaming\Python\Python314\Scripts\uv.exe`.
> Git's `LF will be replaced by CRLF` warning on `ybus.py` appeared on every git command touching
> that file; it is elided below and is not part of the diff.

## 1. Inherited state and HEAD sha

```
$ cd "C:\Claude Projects\mambo-power-audit"
$ git rev-parse HEAD
36bd20aefae9bd5da20ed63fac49ff53815bf0ae

$ git diff --stat
 src/mambo_power/numerics/ybus.py | 2 +-
 1 file changed, 1 insertion(+), 1 deletion(-)

$ git status --porcelain
 M src/mambo_power/numerics/ybus.py

$ git -C "C:\Claude Projects\mambo-power" worktree list
C:/Claude Projects/mambo-power        ca10b6a [main]
C:/Claude Projects/mambo-power-audit  36bd20a (detached HEAD)
C:/Claude Projects/mambo-power-m1     36bd20a [wave/01-substrate]
```

HEAD matches the required sha. The inherited diff (full text in §3 below) was exactly the §2
hunk and nothing else.

## 2. Baseline (stub stashed)

```
$ git stash
Saved working directory and index state WIP on (no branch): 36bd20a feat(m1/S6): install smoke — ...
$ git diff --stat
(empty)

$ uv sync --locked --all-groups
Resolved 81 packages in 17ms
Checked 77 packages in 118ms

$ uv run pytest -q -p no:cacheprovider
175 passed, 9 warnings in 88.98s (0:01:28)
```

Baseline summary line: **`175 passed, 9 warnings in 88.98s`** — matches the auditor's expected 175.

## 3. The stub (`git diff` after `git stash pop`)

```
$ git stash pop
Dropped refs/stash@{0} (347fd24dec6f0ac6733f8487a283f1b1a3c32270)

$ git diff
diff --git a/src/mambo_power/numerics/ybus.py b/src/mambo_power/numerics/ybus.py
index 5facb40..8d4d450 100644
--- a/src/mambo_power/numerics/ybus.py
+++ b/src/mambo_power/numerics/ybus.py
@@ -29,7 +29,7 @@ def branch_admittances(
     """Per-branch ``(Yff, Yft, Ytf, Ytt)`` vectors."""
     ys = np.asarray(1.0 / (arr.r + 1j * arr.x), dtype=np.complex128)
     bc = np.asarray(1j * arr.b / 2.0, dtype=np.complex128)
-    a = np.asarray(arr.tap * np.exp(1j * arr.shift_rad), dtype=np.complex128)
+    a = np.asarray(np.exp(1j * arr.shift_rad), dtype=np.complex128)
     yff: ComplexArray = (ys + bc) / (a * np.conj(a))
     yft: ComplexArray = -ys / np.conj(a)
     ytf: ComplexArray = -ys / a

$ git diff --stat
 1 file changed, 1 insertion(+), 1 deletion(-)
```

Exactly the one-line §2 change; nothing else.

## 4. Full run with the stub applied

```
$ uv run pytest -q -p no:cacheprovider
(exit 1)
FAILED tests/parity/test_ybus_vs_pandapower.py::test_ybus_yf_yt_match_pandapower[case14]
FAILED tests/parity/test_ybus_vs_pandapower.py::test_ybus_yf_yt_match_pandapower[case_ieee30]
FAILED tests/parity/test_ybus_vs_pandapower.py::test_ybus_yf_yt_match_pandapower[case57]
FAILED tests/parity/test_ybus_vs_pandapower.py::test_ybus_yf_yt_match_pandapower[case118]
FAILED tests/unit/test_numerics_dense.py::test_ybus_matches_dense_double_loop
FAILED tests/unit/test_numerics_dense.py::test_yf_yt_match_dense_and_assemble_ybus
6 failed, 169 passed, 9 warnings in 22.19s
```

Full-run summary line: **`6 failed, 169 passed, 9 warnings in 22.19s`**. The six FAILED lines
above are the complete `short test summary info`.

## 5. Targeted run with the stub applied

```
$ uv run pytest -q -p no:cacheprovider tests/unit/test_numerics_dense.py tests/parity/test_ybus_vs_pandapower.py tests/property/test_numerics_properties.py
(exit 1)
FAILED tests/unit/test_numerics_dense.py::test_ybus_matches_dense_double_loop
FAILED tests/unit/test_numerics_dense.py::test_yf_yt_match_dense_and_assemble_ybus
FAILED tests/parity/test_ybus_vs_pandapower.py::test_ybus_yf_yt_match_pandapower[case14]
FAILED tests/parity/test_ybus_vs_pandapower.py::test_ybus_yf_yt_match_pandapower[case_ieee30]
FAILED tests/parity/test_ybus_vs_pandapower.py::test_ybus_yf_yt_match_pandapower[case57]
FAILED tests/parity/test_ybus_vs_pandapower.py::test_ybus_yf_yt_match_pandapower[case118]
6 failed, 28 passed in 66.27s (0:01:06)
```

Targeted-run summary line: **`6 failed, 28 passed in 66.27s`**.

To make the predicted-green items explicit, the same three files were also run with `-v`
(extra to the protocol; same stub state). Per-test status, `[NN%]` columns stripped:

```
$ uv run pytest -p no:cacheprovider -v tests/unit/test_numerics_dense.py tests/parity/test_ybus_vs_pandapower.py tests/property/test_numerics_properties.py
tests/unit/test_numerics_dense.py::test_ybus_matches_dense_double_loop FAILED
tests/unit/test_numerics_dense.py::test_yf_yt_match_dense_and_assemble_ybus FAILED
tests/unit/test_numerics_dense.py::test_ybus_is_not_symmetric_with_phase_shift PASSED
tests/unit/test_numerics_dense.py::test_bbus_matches_dense_double_loop PASSED
tests/unit/test_numerics_dense.py::test_bbus_is_symmetric_with_zero_row_sums PASSED
tests/unit/test_numerics_dense.py::test_ptdf_slack_column_is_zero PASSED
tests/unit/test_numerics_dense.py::test_ptdf_columns_equal_direct_dc_solve PASSED
tests/unit/test_numerics_dense.py::test_ptdf_with_explicit_slack PASSED
tests/unit/test_numerics_dense.py::test_ptdf_flows_conserve_at_every_bus PASSED
tests/unit/test_numerics_dense.py::test_bridges_is_exactly_the_radial_branch PASSED
tests/unit/test_numerics_dense.py::test_lodf_bridge_column_is_nan_and_diagonal_minus_one PASSED
tests/unit/test_numerics_dense.py::test_lodf_matches_brute_force_outage PASSED
tests/unit/test_numerics_dense.py::test_lodf_accepts_precomputed_ptdf PASSED
tests/unit/test_numerics_dense.py::test_dense_oracle_case_has_parallel_branches PASSED
tests/parity/test_ybus_vs_pandapower.py::test_ybus_yf_yt_match_pandapower[case14] FAILED
tests/parity/test_ybus_vs_pandapower.py::test_bbus_bf_pshift_match_pandapower[case14] PASSED
tests/parity/test_ybus_vs_pandapower.py::test_bridges_are_consistent_with_a_removal_bfs[case14] PASSED
tests/parity/test_ybus_vs_pandapower.py::test_ybus_yf_yt_match_pandapower[case30] PASSED
tests/parity/test_ybus_vs_pandapower.py::test_bbus_bf_pshift_match_pandapower[case30] PASSED
tests/parity/test_ybus_vs_pandapower.py::test_bridges_are_consistent_with_a_removal_bfs[case30] PASSED
tests/parity/test_ybus_vs_pandapower.py::test_ybus_yf_yt_match_pandapower[case_ieee30] FAILED
tests/parity/test_ybus_vs_pandapower.py::test_bbus_bf_pshift_match_pandapower[case_ieee30] PASSED
tests/parity/test_ybus_vs_pandapower.py::test_bridges_are_consistent_with_a_removal_bfs[case_ieee30] PASSED
tests/parity/test_ybus_vs_pandapower.py::test_ybus_yf_yt_match_pandapower[case57] FAILED
tests/parity/test_ybus_vs_pandapower.py::test_bbus_bf_pshift_match_pandapower[case57] PASSED
tests/parity/test_ybus_vs_pandapower.py::test_bridges_are_consistent_with_a_removal_bfs[case57] PASSED
tests/parity/test_ybus_vs_pandapower.py::test_ybus_yf_yt_match_pandapower[case118] FAILED
tests/parity/test_ybus_vs_pandapower.py::test_bbus_bf_pshift_match_pandapower[case118] PASSED
tests/parity/test_ybus_vs_pandapower.py::test_bridges_are_consistent_with_a_removal_bfs[case118] PASSED
tests/property/test_numerics_properties.py::test_ybus_symmetric_without_phase_shift PASSED
tests/property/test_numerics_properties.py::test_bbus_row_sums_are_zero PASSED
tests/property/test_numerics_properties.py::test_reduced_bbus_is_nonsingular PASSED
tests/property/test_numerics_properties.py::test_ptdf_slack_column_is_zero PASSED
tests/property/test_numerics_properties.py::test_bridges_and_nan_lodf_columns_agree_with_removal PASSED
```

## 6. Comparison against the auditor's prediction (§4 of the request)

Predicted FAIL (6) — observed:

| Predicted to FAIL | Observed |
|---|---|
| `tests/unit/test_numerics_dense.py::test_ybus_matches_dense_double_loop` | FAILED — **matched** |
| `tests/unit/test_numerics_dense.py::test_yf_yt_match_dense_and_assemble_ybus` | FAILED — **matched** |
| `tests/parity/test_ybus_vs_pandapower.py::test_ybus_yf_yt_match_pandapower[case14]` | FAILED — **matched** |
| `tests/parity/test_ybus_vs_pandapower.py::test_ybus_yf_yt_match_pandapower[case_ieee30]` | FAILED — **matched** |
| `tests/parity/test_ybus_vs_pandapower.py::test_ybus_yf_yt_match_pandapower[case57]` | FAILED — **matched** |
| `tests/parity/test_ybus_vs_pandapower.py::test_ybus_yf_yt_match_pandapower[case118]` | FAILED — **matched** |

Predicted GREEN — observed:

| Predicted to stay GREEN | Observed |
|---|---|
| `test_ybus_yf_yt_match_pandapower[case30]` | PASSED — **matched** |
| `test_bbus_bf_pshift_match_pandapower[*]` (case14, case30, case_ieee30, case57, case118) | all 5 PASSED — **matched** |
| `tests/unit/test_numerics_dense.py::test_ybus_is_not_symmetric_with_phase_shift` | PASSED — **matched** |
| `tests/property/test_numerics_properties.py::test_ybus_symmetric_without_phase_shift` | PASSED — **matched** |
| all PTDF / LODF / bridges tests | all PASSED (4 ptdf + 3 lodf + 1 bridges in dense; 5 bridges parity; 2 property) — **matched** |

Counts: predicted "exactly 6 fail, 169 pass" — observed `6 failed, 169 passed`. **Matched.**
No test outside the predicted six failed; no predicted-green test failed. **No divergence.**

Failure signatures — predicted vs observed:

- Parity: predicted `AssertionError: case14: max |Ybus diff| = <order 1e-2..1e0>`. Observed
  `6.001e-01` (case14), `5.908e-01` (case_ieee30), `3.191e+00` (case57), `3.888e+00` (case118).
  Form **matched**. Magnitude: case14 and case_ieee30 sit inside the predicted 1e-2..1e0 band;
  case57 (3.19) and case118 (3.89) sit slightly above the top of that band. Recorded as-is; the
  auditor's band was phrased as an order-of-magnitude expectation, not a bound.
- Dense: predicted `numpy.testing` "Mismatched elements" with atol=1e-12. Observed exactly
  that (`Not equal to tolerance rtol=0, atol=1e-12` / `Mismatched elements: 3 / 36` and `2 / 54`).
  **Matched.**

## 7. Assertion excerpts (from the full run in §4)

Parity failure, `test_ybus_yf_yt_match_pandapower[case14]`:

```
E       AssertionError: case14: max |Ybus diff| = 6.001e-01
E       assert 0.6001353415925337 <= 1e-09
```

(Other parity cases, same form: `case_ieee30: max |Ybus diff| = 5.908e-01`;
`case57: max |Ybus diff| = 3.191e+00`; `case118: max |Ybus diff| = 3.888e+00`.)

Dense failure, `test_ybus_matches_dense_double_loop`:

```
E       AssertionError:
E       Not equal to tolerance rtol=0, atol=1e-12
E
E       Mismatched elements: 3 / 36 (8.33%)
E       Mismatch at indices:
E        [2, 2]: (4.802792427315753-21.521744421906696j) (ACTUAL), (4.846111186684077-22.041569534326573j) (DESIRED)
E        [2, 3]: (-1.4083197317680303+8.184262506450544j) (ACTUAL), (-1.4518760121319898+8.437384027268601j) (DESIRED)
E        [3, 2]: (0.03425807922769118+8.304477324033522j) (ACTUAL), (0.03531760745122814+8.561316828900537j) (DESIRED)
E       Max absolute difference among violations: 0.52162694
E       Max relative difference among violations: 0.03
```

(The mismatched entries are exactly the [2,2], [2,3], [3,2] cells touched by the tap-0.97
branch xf-34 on the 6-bus dense case, consistent with the auditor's note. The second dense
failure, `test_yf_yt_match_dense_and_assemble_ybus`, reported `Mismatched elements: 2 / 54 (3.7%)`,
same max absolute difference 0.52162694.)

## 8. Restore and green confirmation

```
$ git checkout -- src/mambo_power/numerics/ybus.py
$ git status --porcelain
(empty)

$ uv run pytest -q -p no:cacheprovider tests/unit/test_numerics_dense.py tests/parity/test_ybus_vs_pandapower.py
29 passed in 36.19s
```

## 9. Worktree removal

```
$ git -C "C:\Claude Projects\mambo-power" worktree remove "C:\Claude Projects\mambo-power-audit" --force
(no output, exit 0)

$ git -C "C:\Claude Projects\mambo-power" worktree list
C:/Claude Projects/mambo-power     ca10b6a [main]
C:/Claude Projects/mambo-power-m1  36bd20a [wave/01-substrate]

$ test -d "C:\Claude Projects\mambo-power-audit"   -> gone
$ git -C "C:\Claude Projects\mambo-power" status --porcelain
(empty)
```

`mambo-power-m1` was never entered or modified. No commits, no pushes.

## Unverified

Nothing in the protocol was left unrun. The only item not independently verifiable is the
pre-relaunch state (whether the dead runner had synced or run a baseline); it was made moot
by redoing both steps here.
