# M2 / S3 "dc-results" — report

Wave M2 power-flow, slice S3: `results/` package (W5) + `pf/` DC solver (W2), parity vs
pandapower `rundcpp` on every fixture incl. case300 (AC-3), results JSON/provenance half of
AC-6. Worktree `C:\Claude Projects\mambo-power-m2`, branch `wave/02-power-flow`.

**Commit:** `41e531b` — `feat(m2/S3): DC power flow + typed results with provenance — parity vs
pandapower rundcpp on all fixtures` (on top of S1's `011698c`; no rebase needed, disjoint files).
**Tests:** full suite 355 passed (47 new: 14 results-model, 12 pf-dc, 21 parity). Gates all exit 0.

```
$ git show --stat HEAD
 src/mambo_power/pf/__init__.py         |  52 ++++++
 src/mambo_power/pf/dc.py               | 103 ++++++++++++
 src/mambo_power/results/__init__.py    |  37 +++++
 src/mambo_power/results/from_arrays.py | 101 ++++++++++++
 src/mambo_power/results/power_flow.py  |  95 +++++++++++
 src/mambo_power/results/provenance.py  |  44 +++++
 src/mambo_power/results/tables.py      |  70 ++++++++
 tests/parity/test_dc_vs_pandapower.py  | 214 ++++++++++++++++++++++++
 tests/unit/test_pf_dc.py               | 232 ++++++++++++++++++++++++++
 tests/unit/test_results_models.py      | 288 +++++++++++++++++++++++++++++++++
 10 files changed, 1236 insertions(+)
```

## RED (tests written before the packages existed)

```
$ uv run pytest -q -p no:cacheprovider tests/unit/test_results_models.py tests/unit/test_pf_dc.py tests/parity/test_dc_vs_pandapower.py
ImportError while importing test module '...\tests\parity\test_dc_vs_pandapower.py'.
tests\parity\test_dc_vs_pandapower.py:39: in <module>
    from mambo_power.pf import solve_dc
E   ModuleNotFoundError: No module named 'mambo_power.pf'
ERROR tests/unit/test_results_models.py
ERROR tests/unit/test_pf_dc.py
ERROR tests/parity/test_dc_vs_pandapower.py
3 errors in 1.40s
```

First run after implementation: `44 passed, 3 failed` — all three on case300 (see "oracle
alignment" below: pandapower's default T transformer model), then `47 passed`.

## GREEN

```
$ uv run ruff check .                      -> All checks passed!            (exit 0)
$ uv run ruff format --check .             -> 49 files already formatted    (exit 0)
$ uv run mypy                              -> Success: no issues found in 21 source files (exit 0)
$ uv run pytest -q -p no:cacheprovider     -> 355 passed, 10 warnings in 39.38s (exit 0)
```

(The 10 warnings are pre-existing pandapower `FutureWarning`s from `from_ppc`.)

## Parity vs pandapower `rundcpp` — per-fixture max diffs

Tolerances in the test: 1e-9 deg on angles, 1e-9 MW on from-flows and bus injections.

| fixture | buses | branches | max dva (deg) | max dp_from (MW) | max dp_bus (MW) | slack gen ours / ext_grid (MW) | oracle slack VA offset | elapsed_s |
|---|---|---|---|---|---|---|---|---|
| case14 | 14 | 20 | 7.11e-15 | 9.24e-14 | 1.42e-13 | 219.000000 / 219.000000 | 0 | 0.0011 |
| case30 | 30 | 41 | 1.78e-15 | 8.88e-14 | 5.60e-14 | 23.530000 / 23.530000 | 0 | 0.0008 |
| case_ieee30 | 30 | 41 | 1.07e-14 | 8.88e-14 | 2.61e-13 | 243.400000 / 243.400000 | 0 | 0.0016 |
| case57 | 57 | 80 | 1.53e-13 | 4.48e-13 | 3.98e-13 | 450.800000 / 450.800000 | 0 | 0.0018 |
| case118 | 118 | 186 | 2.34e-13 | 2.52e-12 | 5.17e-12 | 381.000000 / 381.000000 | 30 | 0.0023 |
| case300 | 300 | 411 | 3.33e-12 | 3.47e-12 | 4.26e-12 | 47.720000 / 47.720000 | 0 | 0.0053 |

Every fixture is three orders of magnitude inside the 1e-9 bound. case300 came from S1's
commit `011698c`, which also appended it to `tests/_fixtures.py::FIXTURES`; the parity module
takes it from there (the `skipif`-on-path fallback only fires if it is ever removed from the list).

## Oracle alignment rules (documented in the parity module docstring)

1. **Base voltage.** case14 and case57 carry `BASE_KV = 0` on every bus. pandapower's
   transformer conversion divides by `vn_kv` → NaN, and `rundcpp` raises
   `FloatingPointError` in `_wye_delta`. The oracle's raw copy gets the same substitution our
   importer applies (`BASE_KV <= 0 → 1.0 kV`, M1's documented warning). DC results do not
   depend on base voltage; `test_oracle_is_invariant_to_the_base_kv_substitution` proves it on
   case14 (1.0 kV vs 100 kV agree at 1e-9).
2. **Transformer model — `trafo_model="pi"`.** MATPOWER's branch is a π equivalent.
   pandapower's default `trafo_model="t"` turns any transformer with magnetizing admittance
   (`BR_B != 0`; four case300 transformers: branches 373, 374, 382, 385) into a T and converts
   the series impedance T→π (`build_branch._wye_delta`), changing `x` by up to 6.1e-4 relative
   (e.g. 0.0384 → 0.038421). Effect on case300: 2.6e-3 deg on angles, 1.3e-2 MW on flows. With
   `trafo_model="pi"` pandapower's internal `_ppc` branch `X·TAP` products match the raw
   MATPOWER matrices on all 411 branches. **Relevant to S4 (AC parity):** `runpp` has the same
   default and the same T-model; use `trafo_model="pi"` there too or case300 will miss.
3. **Slack angle.** pandapower seeds the DC solve with the ext_grid's `va_degree` (the stored
   slack VA: 30° in case118) and every angle carries that offset; ours fixes the slack at 0.
   Oracle angles are compared after subtracting the oracle's slack angle.
4. **Branch orientation.** Lines and impedances keep MATPOWER's from/to. pandapower puts a
   transformer's `hv_bus` at the higher-voltage end, which is MATPOWER's `T_BUS` for 16 case300
   branches; when `hv_bus == our to_bus` the oracle's from-side flow is `p_lv_mw` (DC is
   lossless so `p_lv = -p_hv`). The test asserts one of the two orientations holds for every row.
5. **Sign.** Our `p_from_mw` is power entering the branch at the from bus — same as pandapower's
   `p_from_mw`/`p_hv_mw` — so no sign flip beyond the orientation rule. Our `BusResult.p_mw` is
   the **net injection into the network** (gens − loads − shunt GS); pandapower's `res_bus.p_mw`
   is the negative (consumption-positive) and, for shunts, is `vm²`-scaled, so the oracle
   injection is rebuilt from `res_ext_grid + res_gen + res_sgen − res_load − shunt.p_mw(input)`.

## Slack-generator split rule

MATPOWER `rundcpf`: `gen(on(refgen(1)), PG) += (B(ref,:)·Va − Pbus(ref))·baseMVA` — the whole
slack-bus balance is added to the **first in-service generator at the slack bus**; every other
generator (including other slack-bus generators) keeps its dispatch. Implemented verbatim in
`pf/dc.py::solve` (`gen_p[slack_gens[0]] += p_inj[slack] − p_declared[slack]`), unit-tested
with two slack-bus generators (`test_first_slack_generator_absorbs_the_balance`), and
documented in the module docstring. pandapower reports the same number on `res_ext_grid`. The
parity compares **bus-level** generation (sum over ext_grid/gen/sgen at the slack bus vs our sum
over slack-bus GenResults) so it does not depend on the per-generator split; on the fixtures
every slack bus has exactly one generator, so the rules coincide anyway. If the slack bus has
no in-service generator the balance stays visible on `BusResult.p_mw` and no GenResult is
adjusted — naming that situation is W3's `effective_roles` (S2), per the brief.

## What was delivered

- `src/mambo_power/results/provenance.py` — `ResultProvenance(engine: Literal["mambo-power"],
  version, kind, solver, started_at, elapsed_s, options)`; frozen, `extra="forbid"`,
  `allow_inf_nan=False`; `started_at` must be tz-aware and is normalised to UTC; `elapsed_s >= 0`.
- `src/mambo_power/results/tables.py` — `BusResult`, `BranchResult` (`loading_pct: float | None`),
  `GenResult` (`q_limited: Literal["none","min","max"]`), plus the `BusRole`/`QLimitSide` aliases.
- `src/mambo_power/results/power_flow.py` — `PowerFlowResultBase` (provenance, converged, three
  tables, `to_arrays()`), `DcPowerFlowResult`, `AcPowerFlowResult(+ iterations,
  max_mismatch_mva, q_limit_rounds)` for S4 to fill; `PowerFlowArrays` frozen dataclass of
  numpy arrays in table (= `NetworkArrays`) order, NaN standing in for `None` loading.
- `src/mambo_power/results/from_arrays.py` — `dc_result_from_arrays(arr, *, theta_rad,
  p_from_pu, p_inj_pu, gen_p_pu, provenance)`; the one positions→ids and pu→MW site.
- `src/mambo_power/pf/dc.py` — `DcSolution` (theta_rad, p_from_pu, p_inj_pu, gen_p_pu),
  `declared_injection(arr)`, `solve(arr)`; module docstring carries the equations.
- `src/mambo_power/pf/__init__.py` — `solve_dc(net) -> DcPowerFlowResult`; provenance
  `kind="pf.dc"`, `solver="scipy.sparse.linalg.splu"`, `version=mambo_power.__version__`,
  `started_at=datetime.now(UTC)`, `elapsed_s` from `time.perf_counter`, `options={}`.
- Docstrings on every public module, class, function and field (R14 / W10).

## Judgment calls

1. **Solver backend: `splu`, not `spsolve`.** Same backend as the PTDF builder and the planned
   AC Newton; one name in provenance across the package. A singular reduced B' (SuperLU
   `RuntimeError`) or non-finite angles become a `ValueError` naming the cause; `x == 0` keeps
   numerics' existing named error.
2. **DC `vm_pu = 1.0` on every bus** (MATPOWER `rundcpf` sets `VM = 1`); pandapower instead
   echoes the initial magnitudes. Not compared in parity; documented on `DcPowerFlowResult`.
3. **Shunt conductance is in the DC injection** (`P = Pg − Pd − GS/base`), exactly as MATPOWER
   and pandapower do; `BusResult.p_mw` therefore reports gens − loads − GS.
4. **Results cover the in-service subset only**, in `NetworkArrays` order, so `to_arrays()` is
   positional without filtering and `allow_inf_nan=False` holds (no NaN rows for dead buses).
   `in_service` is therefore `True` on every emitted row today; the field stays so a later wave
   can add deactivated rows without a schema change. Flagging this as the one place the brief's
   field list and the "NetworkArrays order" requirement pull in different directions.
5. **`role_effective` carries the declared role** from `arr.bus_type` for DC, per the brief
   (S2 owns `effective_roles`); the docstring says so and names the W3 hand-off.
6. **`converged` is always `True` for DC** (linear solve; failure raises). Kept as a field so the
   two result models share a base and `jobs` can treat them alike.
7. **Oracle helper reuse.** The parity module imports `pandapower_from_raw` from S1's
   `tests/parity/test_matpower_vs_pandapower.py` rather than duplicating the pandapower half of
   `from_mpc`; if S1 renames it the import breaks loudly, which is preferable to a silently
   diverging copy.
8. **`tests/_fixtures.py` untouched** (S1's file). The parity module adds case300 with a
   path-`skipif` only when it is absent from `FIXTURES`; S1 has since added it, so today the
   list is taken verbatim.

## Notes for other slices

- **S4 (AC-NR parity):** use `trafo_model="pi"` on `runpp`, patch `BASE_KV <= 0 → 1.0` on the
  oracle copy (both case14 and case57 need it), and expect the ext_grid `va_degree` offset on
  case118. `AcPowerFlowResult` is defined; fill `iterations`, `max_mismatch_mva`,
  `q_limit_rounds`, and set `q_limited` / `role_effective` from the Q-limit rounds.
- **W6 (jobs):** `ResultProvenance.kind` is already `"pf.dc"`; `options` is `{}` for DC.
