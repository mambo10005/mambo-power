# M2 revert-and-watch — record

Performed 2026-08-20 by the test-runner, following `.bionic/tmp/m2-audit-revert-request.md`
literally. Nothing was fixed, committed, or pushed. All work happened in a throwaway detached
worktree; `C:\Claude Projects\mambo-power-m2` was never entered (read-only `git -C` status
checks only).

## 1. Worktree and starting state

```
$ git -C "C:\Claude Projects\mambo-power" worktree add --detach "C:\Claude Projects\mambo-power-audit2" 502dc1b
Preparing worktree (detached HEAD 502dc1b)
HEAD is now at 502dc1b docs(m2/S7): home page status names the shipped jobs surface (pf.ac / pf.dc via jobs.run) and links the manual

$ git rev-parse HEAD            (in mambo-power-audit2)
502dc1b6c97beb42da12582e9fd23298fb85551d

$ git status --porcelain        (in mambo-power-audit2)
<empty>

$ sed -n '289,290p' src/mambo_power/pf/ac_newton.py
        over = pv[q_gen[pv] > arr.q_max_pu[pv]]
        under = pv[q_gen[pv] < arr.q_min_pu[pv]]
```

`uv sync --locked --all-groups` completed in the throwaway worktree
(`C:\Users\mambo\AppData\Roaming\Python\Python314\Scripts\uv.exe`).

## 2. BEFORE (unmodified 502dc1b) — summary lines

| # | command | summary | exit |
|---|---------|---------|------|
| 1 | `uv run pytest -q -p no:cacheprovider tests/unit/test_pf_ac_newton.py` | `21 passed in 49.70s` | 0 |
| 2 | `uv run pytest -q -p no:cacheprovider tests/parity/test_ac_vs_pandapower.py` | `37 passed in 189.93s (0:03:09)` | 0 |
| 3 | `uv run pytest -q -p no:cacheprovider tests/parity/test_ac_vs_matpower_stored.py` | `10 passed in 7.83s` | 0 |
| 4 | `uv run pytest -q -p no:cacheprovider tests/parity/test_ac_timing.py tests/unit/test_jobs.py tests/unit/test_examples_run.py tests/parity/test_dc_vs_pandapower.py` | `59 passed, 1 warning in 115.19s (0:01:55)` | 0 |

**BEFORE total: 127 passed, 0 failed.**

**Divergence from the request's expected baseline (reported, not rationalised):** the request
expected command 4 to yield 55 (1 + 24 + 9 + 21) and a grand total of 123. Observed is 59 / 127.
`pytest --collect-only -q` per file on the unmodified tree: `test_ac_timing.py` 1,
`test_jobs.py` 24, `test_examples_run.py` 9, `test_dc_vs_pandapower.py` **25** (the request
assumed 21). The other three commands matched the expected 21 / 37 / 10 exactly. The single
warning in command 4 is a pandas `FutureWarning` raised inside
`pandapower/converter/pypower/from_ppc.py:330`, present identically before and after the stub.

## 3. The applied stub

```
$ git diff --stat
 src/mambo_power/pf/ac_newton.py | 4 ++--
 1 file changed, 2 insertions(+), 2 deletions(-)
```

```diff
diff --git a/src/mambo_power/pf/ac_newton.py b/src/mambo_power/pf/ac_newton.py
index 353c9e2..b39f362 100644
--- a/src/mambo_power/pf/ac_newton.py
+++ b/src/mambo_power/pf/ac_newton.py
@@ -286,8 +286,8 @@ def newton(
             break
         s_calc = v * np.conj(y @ v)
         q_gen = s_calc.imag + arr.q_load_pu
-        over = pv[q_gen[pv] > arr.q_max_pu[pv]]
-        under = pv[q_gen[pv] < arr.q_min_pu[pv]]
+        over = pv[:0]  # AUDIT STUB: never detect a violator
+        under = pv[:0]  # AUDIT STUB: never detect a violator
         if over.size == 0 and under.size == 0:
             break
         if rounds >= opts.max_q_rounds:
```

(git also printed `warning: in the working copy of 'src/mambo_power/pf/ac_newton.py', LF will
be replaced by CRLF the next time Git touches it` — autocrlf noise, not part of the change.)

## 4. AFTER (stubbed) — summary lines and every FAILED line verbatim

| # | summary | exit |
|---|---------|------|
| 1 | `5 failed, 16 passed in 9.28s` | 1 |
| 2 | `19 failed, 18 passed in 44.28s` | 1 |
| 3 | `4 failed, 6 passed in 6.92s` | 1 |
| 4 | `59 passed, 1 warning in 61.98s (0:01:01)` | 0 |

**AFTER total: 99 passed, 28 failed.**

### Command 1 — `tests/unit/test_pf_ac_newton.py`

```
=========================== short test summary info ===========================
FAILED tests/unit/test_pf_ac_newton.py::test_q_max_pin - assert 0 == 1
FAILED tests/unit/test_pf_ac_newton.py::test_q_min_pin - assert 0 == 1
FAILED tests/unit/test_pf_ac_newton.py::test_no_restore_after_pinning - asser...
FAILED tests/unit/test_pf_ac_newton.py::test_max_q_rounds_exhausted_reports_not_converged
FAILED tests/unit/test_pf_ac_newton.py::test_solve_ac_q_limited_generators_are_reported
5 failed, 16 passed in 9.28s
```

### Command 2 — `tests/parity/test_ac_vs_pandapower.py`

```
=========================== short test summary info ===========================
FAILED tests/parity/test_ac_vs_pandapower.py::test_voltage_magnitudes_match_runpp[case_ieee30-qlim-on]
FAILED tests/parity/test_ac_vs_pandapower.py::test_voltage_angles_match_runpp[case_ieee30-qlim-on]
FAILED tests/parity/test_ac_vs_pandapower.py::test_branch_flows_match_runpp[case_ieee30-qlim-on]
FAILED tests/parity/test_ac_vs_pandapower.py::test_bus_injections_match_runpp[case_ieee30-qlim-on]
FAILED tests/parity/test_ac_vs_pandapower.py::test_slack_generation_matches_ext_grid_at_bus_level[case_ieee30-qlim-on]
FAILED tests/parity/test_ac_vs_pandapower.py::test_pinned_buses_match_runpp[case_ieee30-qlim-on]
FAILED tests/parity/test_ac_vs_pandapower.py::test_voltage_magnitudes_match_runpp[case118-qlim-on]
FAILED tests/parity/test_ac_vs_pandapower.py::test_voltage_angles_match_runpp[case118-qlim-on]
FAILED tests/parity/test_ac_vs_pandapower.py::test_branch_flows_match_runpp[case118-qlim-on]
FAILED tests/parity/test_ac_vs_pandapower.py::test_bus_injections_match_runpp[case118-qlim-on]
FAILED tests/parity/test_ac_vs_pandapower.py::test_slack_generation_matches_ext_grid_at_bus_level[case118-qlim-on]
FAILED tests/parity/test_ac_vs_pandapower.py::test_pinned_buses_match_runpp[case118-qlim-on]
FAILED tests/parity/test_ac_vs_pandapower.py::test_voltage_magnitudes_match_runpp[case300-qlim-on]
FAILED tests/parity/test_ac_vs_pandapower.py::test_voltage_angles_match_runpp[case300-qlim-on]
FAILED tests/parity/test_ac_vs_pandapower.py::test_branch_flows_match_runpp[case300-qlim-on]
FAILED tests/parity/test_ac_vs_pandapower.py::test_bus_injections_match_runpp[case300-qlim-on]
FAILED tests/parity/test_ac_vs_pandapower.py::test_slack_generation_matches_ext_grid_at_bus_level[case300-qlim-on]
FAILED tests/parity/test_ac_vs_pandapower.py::test_pinned_buses_match_runpp[case300-qlim-on]
FAILED tests/parity/test_ac_vs_pandapower.py::test_at_least_one_fixture_pins
19 failed, 18 passed in 44.28s
```

### Command 3 — `tests/parity/test_ac_vs_matpower_stored.py`

```
=========================== short test summary info ===========================
FAILED tests/parity/test_ac_vs_matpower_stored.py::test_matches_stored_columns_outside_the_exclusions[case_ieee30]
FAILED tests/parity/test_ac_vs_matpower_stored.py::test_matches_stored_columns_outside_the_exclusions[case118]
FAILED tests/parity/test_ac_vs_matpower_stored.py::test_exclusions_sit_where_the_data_are_worst[case_ieee30]
FAILED tests/parity/test_ac_vs_matpower_stored.py::test_case118_without_q_limits_breaches_at_bus_103
4 failed, 6 passed in 6.92s
```

### Command 4 — timing / jobs / examples / dc-parity

No FAILED lines. `59 passed, 1 warning in 61.98s (0:01:01)`.

### Assertion messages (trimmed)

Unit pin test — `test_q_max_pin`:

```
        assert sol.converged
>       assert sol.q_limit_rounds == 1
E       assert 0 == 1
E        +  where 0 = AcSolution(v=array([1.02      +0.j        , 1.0099612 +0.00885295j,
            0.99195695-0.10469929j]), converged=True, ... gen_q_pu=array([0.07942103, 0.07942103, 0.05377324]),
            message=None).q_limit_rounds
```

Parity qlim-on test — `test_pinned_buses_match_runpp[case118-qlim-on]`:

```
>       assert ours == theirs, (case.name, ours, theirs)
E       AssertionError: ('case118', {}, {'bus-19': 'min', 'bus-32': 'min', 'bus-34': 'min', 'bus-92': 'min', ...})
E       assert {} == {'bus-19': 'm...': 'min', ...}
E         Right contains 6 more items:
E         {'bus-103': 'max',
E          'bus-105': 'min',
E          'bus-19': 'min',
E          'bus-32': 'min',
E          'bus-34': 'min',
E          'bus-92': 'min'}
```

Additional matpower-stored assertions (for the "direction not predicted" rows):

```
test_matches_stored_columns_outside_the_exclusions[case_ieee30]
E       AssertionError: ('case_ieee30', 'bus-2', 0.0020000000000000018)
E       assert 0.0020000000000000018 <= 0.002

test_matches_stored_columns_outside_the_exclusions[case118]
E       AssertionError: ('case118', 'bus-103', 0.008999999999999675)
E       assert 0.008999999999999675 <= 0.002

test_exclusions_sit_where_the_data_are_worst[case_ieee30]
E       AssertionError: ('case_ieee30', {'bus-3': 0.8626808312931527})
E       assert 0.8626808312931527 >= 1.0000000000000009

test_case118_without_q_limits_breaches_at_bus_103
E       AssertionError: 1.0099999999999996
E       assert 0.008999999999999675 <= 0.002
E        +  where 0.008999999999999675 = abs((1.0099999999999996 - 1.001))
```

## 5. Prediction comparison

### Predicted RED

| test | predicted | observed | match |
|------|-----------|----------|-------|
| unit `test_q_max_pin` | RED | RED (`assert 0 == 1`) | matched |
| unit `test_q_min_pin` | RED | RED (`assert 0 == 1`) | matched |
| unit `test_no_restore_after_pinning` | RED | RED | matched |
| unit `test_max_q_rounds_exhausted_reports_not_converged` | RED | RED | matched |
| unit `test_solve_ac_q_limited_generators_are_reported` | RED | RED | matched |
| pp `test_voltage_magnitudes_match_runpp[case_ieee30/case118/case300-qlim-on]` | RED x3 | RED x3 | matched |
| pp `test_voltage_angles_match_runpp[...]` x3 | RED x3 | RED x3 | matched |
| pp `test_branch_flows_match_runpp[...]` x3 | RED x3 | RED x3 | matched |
| pp `test_bus_injections_match_runpp[...]` x3 | RED x3 | RED x3 | matched |
| pp `test_pinned_buses_match_runpp[...]` x3 | RED x3 (ours = {}) | RED x3 (case118: ours `{}` vs 6 pins, shown above) | matched |
| pp `test_at_least_one_fixture_pins` | RED | RED | matched |
| pp `test_slack_generation_matches_ext_grid_at_bus_level[...]` x3 | "likely red, not staked" | RED x3 | consistent with the lean |
| mp `test_case118_without_q_limits_breaches_at_bus_103` | RED at 9.0e-3 | RED, `abs(1.0099999999999996 - 1.001) = 0.008999999999999675 > 0.002` | matched, including the predicted 9.0e-3 magnitude |
| mp `test_matches_stored_columns_outside_the_exclusions[case118]` | RED at bus 103, 9.0e-3 | RED, `('case118', 'bus-103', 0.008999999999999675)` | matched, including bus and magnitude |

### Direction not predicted — actual outcomes

| test | observed |
|------|----------|
| mp `test_matches_stored_columns_outside_the_exclusions[case_ieee30]` | RED — `('case_ieee30', 'bus-2', 0.0020000000000000018)`, i.e. bus 2 sits 2e-18 above the 2e-3 band (a floating-point-edge breach, not a gross one) |
| mp `test_exclusions_sit_where_the_data_are_worst[case_ieee30]` | RED — `{'bus-3': 0.8626808312931527}`, max excluded ratio 0.86 < required 1.0 (with no pin, the worst residual moved off the excluded bus) |
| mp `test_exclusions_sit_where_the_data_are_worst[case118]` | GREEN |

### Predicted GREEN

| group | predicted | observed | match |
|-------|-----------|----------|-------|
| unit: the other 16 tests (incl. `test_q_limits_off_leaves_pv_at_setpoint`, `test_strict_comparison_does_not_pin_at_the_limit`, `test_matches_dense_newton_to_1e_10`, `test_warm_start_from_its_own_solution_is_immediate`, `test_solve_ac_result_and_provenance`, `test_effective_roles_are_honoured_on_case14_roles`, `test_solve_dc_reports_effective_roles`) | GREEN | 16 passed; none of these appear in the FAILED list | matched |
| pp: all six tests on `case14-qlim-on`, `case57-qlim-on`, `case300-qlim-off` (18) | GREEN | 18 passed; no FAILED line carries those parametrizations | matched |
| mp: `[case14]`, `[case57]` rows, `test_case30_self_consistency`, `test_case300_converges_without_q_limits_and_is_self_consistent` | GREEN | 6 passed = `matches[case14]`, `matches[case57]`, `exclusions[case57]`, `exclusions[case118]`, `case30_self_consistency`, `case300_...` | matched |
| `test_ac_timing.py` (1), `test_jobs.py` (24), `test_examples_run.py` (9), `test_dc_vs_pandapower.py` (25) | GREEN | 59 passed, 0 failed | matched |

### Unpredicted failures

None. Every one of the 28 FAILED lines is either in the predicted-RED list, in the
"likely red" slack group, or in the explicitly "direction not predicted" set. No predicted-GREEN
test went red.

### Divergences from the request (summary)

1. Baseline count: command 4 = 59, not 55; total 127, not 123. Cause: `test_dc_vs_pandapower.py`
   collects 25 tests, not 21. Not a failure; the extra tests were green before and after.
2. Nothing else diverged.

## 6. Restore, green, worktree removal, m2 untouched

```
$ git checkout -- src/mambo_power/pf/ac_newton.py
$ git status --porcelain
<empty>
$ git diff --stat
<empty>
$ git rev-parse HEAD
502dc1b6c97beb42da12582e9fd23298fb85551d
$ uv run pytest -q -p no:cacheprovider tests/unit/test_pf_ac_newton.py
21 passed in 5.12s

$ git -C "C:\Claude Projects\mambo-power" worktree remove --force "C:\Claude Projects\mambo-power-audit2"
(exit 0, no output)
$ git -C "C:\Claude Projects\mambo-power" worktree list
C:/Claude Projects/mambo-power     6c94459 [epic/01-foundation]
C:/Claude Projects/mambo-power-m2  502dc1b [wave/02-power-flow]
$ ls -d "C:/Claude Projects/mambo-power-audit2"
ls: cannot access 'C:/Claude Projects/mambo-power-audit2': No such file or directory

$ git -C "C:\Claude Projects\mambo-power-m2" rev-parse HEAD        (checked before and after; read-only)
502dc1b6c97beb42da12582e9fd23298fb85551d
$ git -C "C:\Claude Projects\mambo-power-m2" status --porcelain
<empty>
```

## Not run / unverified

- The full `bash tests/run.sh` and the remaining suites were not part of the protocol and were
  not run: `unverified` for this record.
- The unit file was re-run after restore (green); commands 2-4 were not re-run after restore
  (the tree was byte-identical to 502dc1b per `git status`/`git diff`, and their BEFORE runs
  stand as the clean baseline).
