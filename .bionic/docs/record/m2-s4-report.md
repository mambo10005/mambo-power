# M2 / S4 "ac-newton" — report

Wave M2 power-flow, slice S4: sparse polar Newton-Raphson AC power flow with pandapower-semantics
Q-limits and effective roles (W1, AC-1, AC-2, AC-7), `solve_ac`, `solve_dc` switched to effective
roles (A6). Worktree `C:\Claude Projects\mambo-power-m2`, branch `wave/02-power-flow`, base
`cf3f9fb` (S6 committed while this slice ran; nothing of S6's was excluded from any gate).
Written 2026-08-21 (UTC). Every number below was produced by a command in this session.

**Headline.** All six parity rows match pandapower `runpp` at machine precision (max 3e-14 pu,
4e-12 deg, 1e-10 MVA), pinned sets identical on every fixture where limits bind, case300 cold
solve 0.031 s. Two things the lead must know before reading further:

1. **The brief's "file precision" column bands (5e-4 pu / 5e-3 deg) fail on data grounds on all
   four CDF fixtures** — case14 bus 4 sits 1.33e-3 pu from its stored VM with any solver
   (pandapower agrees with us to 1e-15). Research §1.4 said exactly this ("tightening below
   ~1.5e-3 / 0.45° would fail case14 / case_ieee30 on data, not solver, grounds"); AC-1's
   wording contradicts it. I ran the file-precision bands first (RED below), then set the test
   to W1's ratified 2e-3 pu / 0.5 deg and additionally pinned the per-fixture measured residual
   (`MEASURED_RESIDUAL`) so the test cannot drift looser than the data. **Decision needed:**
   ratify the 2e-3/0.5 bands in AC-1 (my recommendation — the alternative is deleting the
   column tier, since no band ≤ 1.3e-3 passes case14) or tell me to leave the tier failing.
2. **pandapower's `from_ppc` puts every transformer tap on the winding it calls `hv`, chosen by
   base voltage.** For the 16 case300 transformers whose T_BUS is the higher-voltage end this
   moves MATPOWER's from-side tap to the other winding — inert in DC (only `1/(x·tap)` enters,
   which is why S3's parity passed) but a different network in AC: 164 MVA on branch 396. The
   oracle copy now reverses those rows with MATPOWER's exact swap identity (`hv_side_first`).
   Consequences for the record: research §1.2/§4.3's "case300 stored columns 0.107 pu away at
   bus 17" and "pandapower cannot converge case300 with Q-limits" were **both artefacts of that
   defect**, not properties of the data. Against this solver the case300 stored columns are
   8.5e-3 pu away at worst (11/300 buses outside 2e-3, iterations 5), and on the aligned oracle
   pandapower converges case300 with `enforce_q_lims=True` in 2 iterations with the same 10
   pins we find. I added that as a sixth parity row (beyond the contracted scope — say so if
   unwanted). S1's PROVENANCE wording for case300 and the spec's assumption (a) inherit the
   research's numbers; I touched neither.

## Files (commit `e4ed0f6846b50baae77012c04b27f85c6108c4a3`; `git show --stat` at the end)

- `src/mambo_power/pf/ac_newton.py` (new, 323 lines): `AcOptions` (pydantic, frozen,
  `extra="forbid"`: `tol=1e-8`, `max_iter=20`, `q_limits=True`, `max_q_rounds=10`,
  `init="auto"|"flat"`), `AcSolution` (frozen dataclass: `v`, `converged`, `iterations` total
  across rounds, `max_mismatch_pu`, `q_limit_rounds`, `q_limited` per bus ∈ {0, ±1}, `bus_type`
  after pinning, `s_bus_pu = V·conj(YV)`, `gen_p_pu`, `gen_q_pu`, `message`), `flat_start`,
  `specified_injection`, `newton_raphson` (one MATPOWER `newtonpf` solve: sparse `dSbus_dV`,
  `sparse.bmat` Jacobian, `splu`), `allocate_generation` (MATPOWER `pfsoln` rules),
  `newton(arr, roles, opts, v0=None)` (the Q-limit loop). Module docstring carries the NR
  equations, the Q-limit rules with pandapower `run_newton_raphson_pf.py:182-249` /
  MATPOWER `runpf.m:366-440` line cites, and the Q-allocation rule (`pfsoln.py:109-141`).
- `src/mambo_power/pf/__init__.py`: `solve_ac(net, *, options=None) -> AcPowerFlowResult`,
  `initial_voltage(net, arr, roles, options)` (the `"auto"` rule needs `Bus.vm_pu/va_deg`,
  which `NetworkArrays` does not carry, so the start is built here and handed to `newton` as
  `v0`), `solve_dc` now derives `effective_roles` and reports them (A6); exports `AcOptions`,
  `AcSolution`, `ac_newton`.
- `src/mambo_power/results/from_arrays.py`: `ac_result_from_arrays(...)` (positions→ids,
  pu→MW, `loading_pct = |S_from|/rating`, per-gen `q_limited` inherited from the bus pin);
  `dc_result_from_arrays(..., bus_type=None)` optional effective roles. `results/__init__.py`
  exports it. `results/power_flow.py`: one field description (`iterations` = summed over
  rounds — S3 had written "of the final round"; the brief says total).
- Tests: `tests/unit/test_pf_ac_newton.py` (21), `tests/parity/test_ac_vs_pandapower.py` (37:
  6 rows × 6 tests + 1), `tests/parity/test_ac_vs_matpower_stored.py` (10),
  `tests/parity/test_ac_timing.py` (1). S1's `pandapower_from_raw` helper is untouched (an
  earlier passthrough-kwarg attempt was reverted with `git checkout`).

## RED

Before `pf/__init__.py` exported anything (the four files were written first; `ac_newton.py`
existed on disk but nothing imported it yet):

```
$ uv run pytest -q -p no:cacheprovider tests/unit/test_pf_ac_newton.py
tests\unit\test_pf_ac_newton.py:26: in <module>
    from mambo_power.pf import AcOptions, AcSolution, solve_ac
E   ImportError: cannot import name 'AcOptions' from 'mambo_power.pf' (...\src\mambo_power\pf\__init__.py)
ERROR tests/unit/test_pf_ac_newton.py
1 error in 1.39s

$ uv run pytest -q -p no:cacheprovider tests/parity/test_ac_vs_pandapower.py tests/parity/test_ac_vs_matpower_stored.py tests/parity/test_ac_timing.py
E   ImportError: cannot import name 'AcOptions' from 'mambo_power.pf' (...)   [x2]
ERROR tests/parity/test_ac_vs_pandapower.py
ERROR tests/parity/test_ac_vs_matpower_stored.py
Interrupted: 2 errors during collection
```
(`test_ac_timing.py` collects without importing the package — its subprocess would have died on
the same ImportError.)

First GREEN attempt after wiring `solve_ac`: `5 failed, 25 passed` in the unit file — pinned
generators reported `imag(S)+Q_load` (off the limit by the 1e-8 tolerance: 0.37732414 vs
0.37732380 MVAr) instead of the limit itself, and `BusResult.p_mw` still contained the shunt
(Σ injections 5.43 MW vs branch losses 0.45 MW). Both fixed at the source (pinned buses report
the limit, as pandapower's `fixedQg` restore does; the reported injection is
`V·conj(YV) − |V|²·conj(g + jb)`, i.e. gen − load − shunt, matching the DC result and
`−res_bus`). Then `6 failed, 79 passed`: the five case300 rows vs pandapower (0.107 pu at bus
17, 2.26° at bus 528, 164 MVA at branch 396 / bus 7062, 13.4 MW slack) — the tap-side defect
above — and `test_excluded_buses_are_really_defective[case57]` (my premise that each excluded
bus breaches the band individually was wrong: bus 14 is at 0.09 of the band, the defect shows
at bus 46 — test reworded, see judgment 6).

File-precision bands, run once before settling on 2e-3 / 0.5:
```
$ uv run python -c "... m.VM_BAND, m.VA_BAND = 5e-4, 5e-3 ..."
case14       FAIL ('case14', 'bus-4', 0.0013291463082354404)
case_ieee30  FAIL ('case_ieee30', 'bus-16', 0.0006098011437822848)
case57       FAIL ('case57', 'bus-32', 0.0008747178231146568)
case118      FAIL ('case118', 'bus-105', 0.000990191391393891)
```

## GREEN

```
$ uv run ruff check .                      -> All checks passed!                exit 0
$ uv run ruff format --check .             -> 84 files already formatted        exit 0
$ uv run mypy                              -> Success: no issues found in 27 source files   exit 0
$ uv run pytest -q -p no:cacheprovider     -> 451 passed, 10 warnings in 34.11s (36 s wall incl. uv)   exit 0
                                              (380 at S2 + S6's + 69 new: 21 unit, 37 + 10 + 1 parity)
```
Whole tree, nothing excluded (S6 had committed `cf3f9fb` by then; `tests/unit/test_docstrings.py`
passes on every new public symbol). The 10 warnings are the pre-existing pandapower `from_ppc`
RuntimeWarnings (case14/case57 `BASE_KV = 0`) and pandas FutureWarnings. Intermediate full run
before the last test edits: `445 passed, 10 warnings in 36.45s`.

## Parity vs pandapower `runpp` (AC-1, AC-2)

`init="flat"`, `tolerance_mva=1e-8`, `trafo_model="pi"`, `max_iteration=50`, `numba=False`,
`enforce_q_lims` matched; tolerances 1e-6 pu / 1e-4 deg / 1e-4 MVA.

| fixture | q_limits | NR iters (total) | q rounds | pinned (side) | max dvm pu | max dva deg | max dflow MVA | max dinj MVA | pp iters | solve_ac elapsed_s |
|---|---|---|---|---|---|---|---|---|---|---|
| case14 | on | 4 | 0 | — | 8.9e-16 | 2.8e-14 | 4.1e-13 | 9.0e-13 | 4 | 0.0085 |
| case_ieee30 | on | 6 | 1 | 2 (max) | 1.1e-15 | 6.4e-14 | 7.1e-13 | 4.3e-08 | 2 | 0.0229 |
| case57 | on | 4 | 0 | — | 5.6e-15 | 1.7e-13 | 2.1e-12 | 1.5e-10 | 4 | 0.0195 |
| case118 | on | 7 | 1 | 19 (min), 32 (min), 34 (min), 92 (min), 103 (max), 105 (min) | 8.9e-16 | 2.0e-13 | 6.3e-12 | 8.6e-12 | 3 | 0.0290 |
| case300 | off | 5 | 0 | — | 3.2e-14 | 4.3e-12 | 1.3e-10 | 2.3e-10 | 5 | 0.0247 |
| case300 (extra) | on | 7 | 1 | 10, 20, 156, 170, 171, 236, 7003, 7055, 7062, 9002 (all max) | 4.0e-14 | 4.3e-12 | 9.2e-11 | 6.5e-11 | 2 | 0.0682 |

"NR iters" is our total across rounds (case118: 3 + 4 after pinning); pandapower reports only
its last round. "pinned" sets and sides equal pandapower's on every row
(`test_pinned_buses_match_runpp`, oracle read from `_ppc["internal"]["pq"]` via
`_pd2ppc_lookups["bus"]` — `_ppc["bus"][:, BUS_TYPE]` is unusable because
`_run_ac_pf_with_qlims_enforced` resets only the last round's buses to PV for reporting,
`run_newton_raphson_pf.py:244`; the probe confirmed it shows no PQ conversions at all).
case_ieee30's `dinj` of 4e-8 is pandapower's own `res_bus` rounding at the pinned bus (its
`res_gen.q` is the restored limit while `res_bus` carries the solved value — 1e-8 pu × 100).

## Stored MATPOWER columns (AC-1 secondary, AC-2 negative pair)

Q-limits on, flat start, slack-aligned angles, bands 2e-3 pu / 0.5 deg after exclusions:

| fixture | excluded (defect MVA, research §1.3) | max dvm pu (bus) | max dva deg (bus) | file-precision 5e-4 / 5e-3 |
|---|---|---|---|---|
| case14 | — | 1.33e-3 (4) | 1.7e-2 (4) | FAIL on VM and VA |
| case_ieee30 | 3 (8.2) | 6.1e-4 (16) | 0.336 (4) | FAIL |
| case57 | 14 (21.2), 46 (45.8), 47 (24.7) | 8.7e-4 (32) | 0.052 (32) | FAIL |
| case118 | 17 (45.3), 30 (129.7), 38 (31.3), 68 (10.5) | 9.9e-4 (105) | 0.312 (1) | FAIL |

Excluded-bus breach ratios (1.0 = band; `test_exclusions_sit_where_the_data_are_worst`):
case_ieee30 {3: 0.86} vs worst kept bus 4 at 0.67; case57 {14: 0.09, 46: 4.90, 47: 0.13} vs
worst kept bus 32 at 0.44; case118 {17: 0.53, 30: 8.76, 38: 0.39, 68: 0.12} vs worst kept bus 1
at 0.63. AC-2 negative pair: case118 bus 103 stored 1.001; q_limits off → 1.01000 (|Δ| 9.0e-3,
breaches 2e-3); on → 1.00071 (|Δ| 2.9e-4). case30 (stored state flat, asserted) and case300
(q_limits off): solve, warm-start from the result under `init="auto"` → 0 iterations, identical
state to 1e-9 pu / 1e-7 deg / 1e-6 MW. `init="auto"` from the shipped columns on the upstream
fixtures: case14 2 iterations, case_ieee30 4 (+1 round), case57 3, case118 6 (+1 round),
case300 5 — all converge to the flat-start fixed point.

## AC-7 timing (case300, q_limits off, flat start, fresh interpreter)

```
$ uv run pytest -q -s tests/parity/test_ac_timing.py
case300 AC cold 0.0312 s, warm 0.0194 s, 5 iterations        (assert < 1.0 s; Windows 11, Python 3.12)
```
The cold figure is the first `solve_ac` call in a subprocess (arrays, Ybus, 5 sparse LU
factorisations, result construction). CI ubuntu is the contracted surface; the threshold was
not touched.

## Judgment calls

1. **Convergence test `‖F‖∞ ≤ tol`, tested before each step.** MATPOWER/pandapower use `<`;
   the brief says `≤`. Immaterial at 1e-8, documented. A start already inside tolerance reports
   **0** iterations (MATPOWER semantics); the brief's "warm start converges in 1 iteration" is
   asserted as `≤ 1` and the observed value is 0.
2. **A non-converged Newton solve ends the Q-limit loop without pinning.** pandapower keeps
   pinning on an unconverged state and raises afterwards; pinning from garbage has no oracle, so
   we stop and report `converged=False` with the Newton message. `max_q_rounds` exhausted →
   `converged=False`, message lists the still-violating buses (pandapower raises).
3. **Per-bus aggregate limits** (`q_min_pu/q_max_pu` sums), as the brief says; pandapower tests
   per generator. With MATPOWER's range-proportional Q split the two agree whenever a bus's gens
   have non-zero ranges (every fixture has one generator per bus, so they coincide exactly).
   Pinned buses report the limit itself, not `imag(S)+Q_load` (1e-8-pu apart).
4. **Reported bus injection excludes the shunt** (`gen − load − shunt(|V|²)`), as the
   `BusResult` docstring, the DC result and pandapower's `−res_bus` all define it; `AcSolution.
   s_bus_pu` keeps the raw `V·conj(YV)` the Q-limit test needs.
5. **`init="auto"` keeps the stored slack angle** (case118: 30°), so `va_deg` is slack-relative
   only for flat starts; both oracles behave this way. Parity runs `init="flat"`.
6. **Exclusion test semantics.** The exclusion list comes from research §1.3's MVA gate, not
   from the voltage band; case57 buses 14/47 and case118 17/38/68 stay inside the band
   individually (the defect surfaces at 46 and 30). The test therefore asserts the excluded set
   contains the fixture's worst-deviating bus (true on all three) and prints every ratio.
7. **Transformer alignment on the oracle copy, not in `pandapower_from_raw`.** The exact swap
   identity (`τ' = 1/τ, r' = rτ², x' = xτ², b' = b/τ², shift' = −shift`, derived from the four
   `Yff/Yft/Ytf/Ytt` entries) is applied to the raw rows where `tap ∉ {0,1}` and
   `BASE_KV[T] > BASE_KV[F]`; pandapower then sees an hv-first transformer and runs its standard
   path. An attempt to pass `from_ppc(tap_side=<array>)` instead left the 164 MVA unchanged
   (pandapower's lv-side tap re-refers `vk` by `(1+ratio)²` but does not reproduce MATPOWER's
   branch) and was reverted.
8. **case300 with Q-limits added as a sixth parity row** — the only scope addition; it is the
   evidence behind headline 2. Remove the tuple from `CASES` if the lead wants the contracted
   five only.
9. **`AcPowerFlowResult.iterations` description changed** to "summed over all Q-limit rounds"
   (S3's field said "of the final round"; the brief and `AcSolution` say total).

## Notes for other slices

- **S5/jobs:** `AcOptions().model_dump()` is what `provenance.options` carries; `AcOptions` is a
  pydantic model (`extra="forbid"`, frozen) ready to be `KindSpec.options_model`. Non-convergence
  is a result (`converged=False`), not an exception — only `NoSlackGeneratorError` /
  `ValueError` (singular Ybus, r=x=0) escape `solve_ac`.
- **Research / S1 record:** §1.2's case300 row and §4.3's "cannot converge with Q-limits" need
  a correction note; `fixtures/matpower/PROVENANCE.md` may repeat the 0.107 figure.
- **S6 docs:** `pf.ac_newton` module docstring is the power-flow manual's source for the NR and
  Q-limit equations.

## Commit

```
$ git add <9 paths>; git commit -q -F -      exit 0   (no hook blocked)
$ git show --stat HEAD
commit e4ed0f6846b50baae77012c04b27f85c6108c4a3
Author: Manho Joung <manhojoung@gmail.com>
Date:   Thu Aug 20 21:06:02 2026 -0700

    feat(m2/S4): AC Newton-Raphson power flow — sparse polar NR, pandapower-semantics Q-limits, effective roles; parity vs runpp and MATPOWER stored solutions; case300 timing

    Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>
    Claude-Session: https://claude.ai/code/session_01NA3xnvrFVGDqG3azRk8CBs

 src/mambo_power/pf/__init__.py             | 121 ++++++-
 src/mambo_power/pf/ac_newton.py            | 323 +++++++++++++++++
 src/mambo_power/results/__init__.py        |   3 +-
 src/mambo_power/results/from_arrays.py     | 107 +++++-
 src/mambo_power/results/power_flow.py      |   2 +-
 tests/parity/test_ac_timing.py             |  49 +++
 tests/parity/test_ac_vs_matpower_stored.py | 175 ++++++++++
 tests/parity/test_ac_vs_pandapower.py      | 316 +++++++++++++++++
 tests/unit/test_pf_ac_newton.py            | 535 +++++++++++++++++++++++++++++
 9 files changed, 1614 insertions(+), 17 deletions(-)
$ git status --short      (clean afterwards)
```
Not pushed.
