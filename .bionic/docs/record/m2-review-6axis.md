# M2 / Step 6 — six-axis review (stance 1)

Wave M2 power-flow, worktree `C:\Claude Projects\mambo-power-m2`, diff `6c94459..502dc1b`
(8 commits, 79 files, +11187 / −34). Reviewed 2026-08-21 against the wave spec (requirements,
AC-1..10, Design 1-8), epic §Design (boundaries, ownership table §3) and plan assumptions
A1-A12 (not re-raised). Every claim below carries its proving command/output or a `file:line`;
anything else is marked `unverified`.

Evidence run in the worktree (read-only; `git status --porcelain` empty before and after):

```
uv run pytest -q -p no:cacheprovider --durations=15   -> 484 passed, 10 warnings in 226.44s  exit 0
uv run pytest tests/parity/test_ac_timing.py -q -s    -> case300 AC cold 0.5746 s, warm 0.4045 s, 5 iterations; 1 passed
uv run mkdocs build --strict -q                        -> exit 0, real 0m32.5s
```

(The 226 s and 0.57 s were measured while two other agents ran suites in the same worktree;
the floor's figure is authoritative for wall time. S4 recorded 0.031 s cold idle.)

Closing table and fold order are at the end.

---

## 1. Correctness — **PASS** (with flags)

The formulation, the Q-limit semantics and the role/island rules are right and are proven
against three independent oracles (dense textbook NR at 1e-10, pandapower `runpp` at
≤ 3e-14 pu on six rows, MATPOWER stored columns at the ratified band). The flags are edges
and a dropped diagnostic, not wrong numbers.

Verified correct (with the evidence):

- NR formulation — `_dsbus_dv` is MATPOWER `dSbus_dV` polar verbatim
  (`src/mambo_power/pf/ac_newton.py:143-150`); Jacobian blocks J11/J12/J21/J22 sliced from
  `[pvpq, pvpq] / [pvpq, pq] / [pq, pvpq] / [pq, pq]` (`:185-189`), state
  `[Va[pvpq]; Vm[pq]]` (`:197-199`), mismatch tested before each step (`:176-178`),
  ∞-norm ≤ tol. Proof: `test_matches_dense_newton_to_1e_10` (dense element-wise H/N/J/L
  oracle, nothing shared) and `test_ac_vs_pandapower.py` six rows at 1e-6/1e-4 bands with
  measured residuals ≤ 3e-14 pu (S4 report table).
- Flat/warm start — `flat_start` holds PV/slack at the *effective* setpoint (`:123-128`);
  warm path overrides held magnitudes and keeps angles (`:268-271`); `initial_voltage`
  falls back to flat when any in-service bus lacks vm/va (`pf/__init__.py:61-68`), proven by
  `test_solve_ac_auto_init_warm_starts_from_stored_state` (both branches).
- Q-limit loop vs pandapower — strict `>`/`<` (`ac_newton.py:289-290`,
  `test_strict_comparison_does_not_pin_at_the_limit`), slack exempt because only `pv`
  positions are tested (`:283,289`), pins accumulate (pinned buses leave `pv`, never re-enter;
  `test_no_restore_after_pinning`), round bound with message (`:294-301`,
  `test_max_q_rounds_exhausted_reports_not_converged`), inner NR failure breaks the loop
  before any pin (`:285-286`), Q_spec pinned to `Q_limit − Q_load` (`:307-308`, MATPOWER
  `QD -= QG` equivalent). Pinned sets equal pandapower's on every binding fixture
  (`test_pinned_buses_match_runpp`, oracle read from `_ppc["internal"]["pq"]`).
- Q allocation — `allocate_generation` is `pfsoln` (`:217-252`): first slack gen absorbs P,
  proportional-to-range Q split, equal split at zero range, pinned buses report the limit
  itself; `test_slack_q_split_proportional_to_range`, `test_zero_range_generators_split_equally`,
  `test_slack_generation_matches_ext_grid_at_bus_level`.
- Branch flows — `S_f = V_f·conj(Yf V)`, `S_t = V_t·conj(Yt V)` (`pf/__init__.py:90-91`);
  reported bus injection removes the shunt term so it equals gen − load − shunt
  (`:95-97`; `test_solve_ac_flows_balance_against_injections` checks
  `p = −70 − 5·vm²`, `q = −30 + 10·vm²` at the shunt bus); flows ≤ 1e-10 MVA vs pandapower.
- Effective roles — demotion, last-VG, conflict warning, `NoSlackGeneratorError`
  (`numerics/roles.py:67-104`); arrays untouched (`test_arrays_are_not_modified`); pandapower
  demotes the same bus (`test_pandapower_solves_the_gen_less_pv_bus_as_pq`); the
  converter's first-wins vs our last-wins is pinned explicitly
  (`test_converter_first_wins_vs_our_last_wins_is_explicit`).
- Island repair — BFS from every in-service slack over in-service branches whose two ends
  are in service (`model/islands.py:64-73`), attached elements deactivated via `model_copy`
  (no mutation, `test_repair_islands_does_not_mutate_its_input`), one warning per component
  in bus order, already-out elements not listed
  (`test_entities_repair_deactivates_each_island_with_its_elements_and_live_branches`).
- DC — `P = Pg − Pl − Gs`, rhs `P − p_shift`, `p_from = Bf θ + pf_shift`,
  `p_inj = B'θ + p_shift` (`pf/dc.py:79-98`); 1e-9 vs `rundcpp` on all six fixtures
  including case300; phase-shift hand case vs dense solve (`test_pf_dc.py`).
- Results id/position mapping — shape guards then `arr.bus_ids[i]`, `arr.branch_ids[k]`,
  `arr.gen_ids[g]` (`results/from_arrays.py:44-62,128-145`);
  `test_to_arrays_follows_network_arrays_order`; `solve_ac` leaves the network untouched
  (probe: `net.model_dump() == before` → `True`).
- Examples' claims vs code — ran `examples/02` and `03`: case118 q-on pins exactly six
  generators (gen-9/15/16/43/48 min, gen-46 max), bus 103 `1.00071 / 1.01000`, warm start
  0 iterations; `03` largest DC/AC gap 408.23 MW on branch-403 vs AC losses 408.32 MW — the
  "feeds the slack bus" sentence is consistent with the numbers.

Findings:

1. **Medium — non-convergence diagnostic is dropped at the public boundary.**
   `AcSolution.message` (`ac_newton.py:322`; "singular Jacobian at iteration n",
   "Q-limit enforcement did not settle … still violating: [...]") is never read by
   `solve_ac` (`pf/__init__.py:88-120` passes no message) and `AcPowerFlowResult`
   (`results/power_flow.py:90-95`) has no field for it. A `jobs.run` / `solve_ac` caller
   sees `converged=False` and nothing else. The manual says otherwise at the public level:
   `docs/manual/power-flow.md:255` ("return converged = False — message lists the violating
   buses") sits in the `solve_ac` flow diagram. Epic §1 (`epic.spec.md:125`) lists
   "diagnostics" in the result provenance. Fix: add `message: str | None = None` to
   `AcPowerFlowResult`, thread it through `ac_result_from_arrays`, assert it in
   `test_solve_ac_not_converged_is_reported_not_raised` and `test_non_convergence_is_ok_with_converged_false`.
2. **Medium — a valid network that DC cannot solve is reported as a solver bug.**
   `x == 0` with `r > 0` passes `validate_network` (BAD_RANGE needs both zero) and is
   legitimate for AC, but `pf.dc.solve` raises `ValueError` (`pf/dc.py:91,93`, and
   `numerics.bbus` for `x == 0`), which `jobs.run` maps to `INTERNAL`
   (`jobs/run.py:156`). Probe: `run_json` with `branches[0].x = 0.0`, kind `pf.dc` →
   `status=failed code=INTERNAL msg="ValueError: DC susceptance undefined: x == 0 …"`.
   `INTERNAL` is documented as "a solver bug" (`docs/manual/jobs.md`), so a user-data
   problem is misfiled. Fix: a named numerics error (e.g. `UnsolvableNetworkError` /
   reuse of a `numerics.errors` class) raised by `bbus`/`dc.solve` and mapped by `run` to a
   structured code (`UNSOLVABLE` or `BAD_NETWORK`), added to `FailureCode`.
3. **Low — `loading_pct` uses the from-side flow only** (`results/from_arrays.py:34-38`,
   `:116,:180`; documented at `docs/manual/results.md:67`). MATPOWER reports both ends and
   pandapower's `loading_percent` is `max(i_from, i_to)/i_max`; on a lossy line the to-side
   apparent flow can exceed the from-side. It is a documented convention today, but M3's N-1
   loading screen will inherit it. Fix: `max(|S_f|, |S_t|)/rating` (AC) and say so in the
   table row; DC is unaffected (`|p_to| == |p_from|`).
4. **Low — per-generator vs per-bus limit check differs in one edge.** pandapower/MATPOWER
   test `gen[:, QG] > QMAX` per generator after the `pfsoln` split and turn the violating
   *generator* off; ours tests the bus aggregate (`ac_newton.py:289-290`). The two coincide
   whenever every generator at the bus has a positive range or equal zero-range limits
   (the proportional split puts all of them over together) — true on every fixture (pinned
   sets identical) — but a bus mixing zero-range generators with *unequal* limits pins
   earlier in pandapower. `unverified` on pandapower (no such fixture); worth one sentence
   in the Q-limit section rather than code.
5. **Low — proportional Q split loses precision with very wide limits.** Probe: case14
   gen-2 with `q_min/q_max = ∓1e308` solves `converged=True` and reports `q_mvar = 0.0`
   (cancellation in `q_min + share·range`, `ac_newton.py:243-246`) where the bus actually
   needs a non-zero Q. MATPOWER fixtures use 9999 so this is invisible there. Fix: when a
   bus has exactly one in-service generator assign `q_bus` directly; keep the proportional
   rule for ≥ 2.
6. **Low — `initial_voltage` treats a stored `vm_pu = 0.0` as a start.** `pf/__init__.py:64`
   (`vm_pu or 0.0` is a typing crutch); a zero magnitude on a PQ bus makes `v/|v|` NaN in
   the first Jacobian and the solve returns `converged=False` at iteration 1 (probe: all
   buses stored `vm_pu = 0` → `converged=False`, 1 iteration). Not a crash, but "auto" would
   do better falling back to flat when any stored `vm_pu <= 0`. Fix: add `and vm_pu > 0` to
   the `all(...)` guard.

## 2. Readability — **PASS** (with flags)

Module sizes are fine (`ac_newton.py` 323, `matpower.py` 465, `network.py` 264,
`jobs/run.py` 243 lines); docstrings are reST, substantive and cite the oracle line numbers
they follow; tests read as specifications. Flags are small shape issues.

1. **Low — `AcSolution` is incomplete where `DcSolution` is complete.** `DcSolution` carries
   `p_from_pu`/`p_inj_pu`; `AcSolution` stops at `s_bus_pu` and the branch flows plus the
   shunt-corrected injection are computed in the package `__init__`
   (`pf/__init__.py:89-97`). The array-level API the spec names
   (`pf.ac_newton.newton(arr, roles, opts)`) therefore does not give its caller flows, and
   `pf/__init__.py` carries physics instead of glue. Fix: compute `s_from_pu`/`s_to_pu` and
   the shunt-free injection inside `ac_newton.newton` (it already has `y`; `yf_yt` is one
   call) and make `solve_ac` pure mapping.
2. **Low — `RepairedEntities` is a positional 7-tuple** (`model/islands.py:37-46`) returned
   from two identical early-return blocks (`:66-74`, `:85-93`) and unpacked positionally in
   `io/matpower.py` and the tests. A small frozen dataclass (`buses, branches, …, issues`)
   reads better and removes the duplicated returns.
3. **Low — the local name `warnings` holds `list[ImportIssue]`** in `model/islands.py:110`
   and `io/matpower.py:_build`, next to a module `model/warnings.py` and the stdlib
   `warnings` the package imports elsewhere. `issues` would match the type's name
   (`ImportIssue`, A7) and the field name `ImportReport.warnings` could follow in a later
   wave.
4. **Low — dead branch in a parity test.** `tests/parity/test_dc_vs_pandapower.py:56-62`
   guards `if "case300" not in FIXTURES:`; S1 added case300 to `FIXTURES`
   (`tests/_fixtures.py:12`), so the skip-param path is unreachable. Delete it.
5. **Low — `test_effective_roles.py:106` parametrises a hand list**
   (`case14, case_ieee30, case118, case300`) with no note on why case30/case57 are omitted;
   use `FIXTURES`.
6. **Low — an overstated docstring claim.** `jobs/run.py:25` and `docs/manual/jobs.md:246`
   say "Python ≥ 3.14 makes the [warnings] context thread-local". In 3.14 that is the
   `context_aware_warnings` flag, default on only for the free-threaded build and opt-in
   (`-X context_aware_warnings=1`) otherwise. Reword to "opt-in from 3.14".
7. **Low — the documented AC-7 figure needs its condition stated.**
   `docs/manual/power-flow.md:333` gives 0.029 s cold; this review measured 0.575 s on the
   same machine under two concurrent test runs (command above). Both are < 1.0 s, but the
   page should say "idle machine" next to the number, since the contracted surface is CI and
   the margin under load is < 2×.

## 3. Architecture — **PASS** (with flags)

Import graph (grep of every `from mambo_power…` in `src/`): `model` imports nothing;
`io → model`; `numerics → model`; `results → numerics.arrays`; `pf → numerics, results,
model`; `jobs → pf, results, model, numerics`. `results` does **not** import `pf`; `pf`
imports `results` — the direction the epic allows (results is the lower layer). `jobs` knows
no solver internals: it imports `AcOptions`/`solve_ac`/`solve_dc` from `pf`'s public surface
and `NoSlackGeneratorError` from `numerics` for the code mapping
(`jobs/registry.py:19-21`, `jobs/run.py:44-46`).

Closure check — every new public primitive has a call path from a public entry point and
was exercised by Step-5 evidence (tests + examples + CI):

| Primitive | Production callsite | Test | Example / CI |
| --- | --- | --- | --- |
| `pf.solve_ac` | `jobs.registry._run_ac` | `test_pf_ac_newton`, 3 parity files, `test_jobs` | `02, 03, 05, 07`; timing step |
| `pf.solve_dc` | `jobs.registry._run_dc` | `test_pf_dc`, `test_dc_vs_pandapower`, `test_jobs` | `03` |
| `pf.ac_newton.newton` | `pf.solve_ac` | `test_pf_ac_newton` (direct, 15 tests) | via `02` |
| `pf.dc.solve` | `pf.solve_dc` | `test_pf_dc` (direct) | via `03` |
| `numerics.effective_roles` | `pf.solve_ac`, `pf.solve_dc` | `test_effective_roles`, `test_roles_vs_pandapower` | `05` |
| `model.repair_islands_entities` | `io.matpower._build` | `test_islands` | `05` (through the importer) |
| `model.repair_islands` | none in `src/` (tests + docs only) | `test_islands` (4 tests) | — |
| `io.load_with_report` | `load_with_warnings` delegates to it | `test_islands` | `01, 05` |
| `results.ac/dc_result_from_arrays` | `pf.solve_*` | `test_results_models` | via every example |
| `results.*.to_arrays` | — (consumer API) | `test_results_models`, stored parity | `03, 07` |
| `jobs.run` / `run_json` / `KINDS` | `run_json → run`; `SolveResult` validators read `KINDS` | `test_jobs` (26 tests) | `04`; examples CI job |

1. **Low — `model.repair_islands(net)` has no production caller.** The spec names it as the
   owner (design item 4) and the importer calls the entity-level variant, which is the
   right call for "before validation". It is tested and documented, so not dead substrate,
   but the spec sentence "`io.matpower.load_with_warnings` calls it" is literally false.
   Fix: one line in the spec/architecture page naming `repair_islands_entities` as the
   importer hook and `repair_islands` as the user-facing form.
2. **Low — the pu boundary statement is now contradicted by the code it governs.**
   `numerics/arrays.py:3-6` ("nothing else in the package divides by base_mva") and epic
   `epic.spec.md:124,140` ("positional ints exist only here"; "ONLY model and results types
   cross") vs `results/from_arrays.py:3-5`, which multiplies by `base_mva` and walks
   positions back to ids, and `pf/__init__.py:90-91` indexing `sol.v[arr.f]`. The wave spec
   (design item 5) ratified `results.from_arrays`, so this is a docs-consistency gap, not a
   code move: amend the arrays docstring to "the single site that divides by base_mva; the
   inverse lives in `results.from_arrays`" and add a parenthesis to epic §2.
3. **Low — `FailureCode` is exported but nothing uses it.** `jobs/models.py:33-40` defines
   the Literal; `StructuredError.code` is typed `str` by design (`:56`) and no test asserts
   the emitted codes are a subset of it. Either type `code: FailureCode` (later kinds widen
   the Literal, which is a one-line schema change) or add a test that every code `run`
   emits is in `typing.get_args(FailureCode)`.
4. **Low — API reference misses `pf.ac_newton`.** `docs/api/pf.md:6-12` renders
   `mambo_power.pf` (`show_submodules: false`) and `mambo_power.pf.dc` but not
   `mambo_power.pf.ac_newton`; in the built site `newton_raphson` and `allocate_generation`
   have 0 occurrences (`grep -o … site/api/pf/index.html | wc -l`), while `AcOptions`,
   `AcSolution`, `flat_start` appear only through the re-export. AC-8 promises every public
   symbol of `pf`. Fix: add `## AC solver over arrays` + `::: mambo_power.pf.ac_newton`.
   Every other new public symbol checked is present (`effective_roles` 19,
   `repair_islands` 23, `ImportReport` 27, `run_json` 27, `to_arrays` 13, `FailureCode` 20).

## 4. Security — **FLAG**

Examples use repo-relative `fixtures/...` paths only and `07` writes inside
`tempfile.TemporaryDirectory`; `ci.yml` has top-level `permissions: contents: read`
(`.github/workflows/ci.yml:7-8`); no secrets in workflows, examples, docs or `mkdocs.yml`
(grep for secret/token/password/api_key: only `id-token`). Actions are tag-pinned
(`checkout@v4`, `setup-uv@v5`, `upload-artifact@v4`, `configure-pages@v5`,
`upload-pages-artifact@v3`, `deploy-pages@v4`). Two things fall short of the stated
contract.

1. **High-priority (medium severity) — `run_json` raises on deeply nested JSON.**
   Contract: "nothing crosses the boundary" (`jobs/run.py:21`, test
   `test_malformed_request_json_is_a_failed_result`). Probe:
   `run_json("[" * 5000 + "]" * 5000)` → `RecursionError: maximum recursion depth exceeded
   while decoding a JSON array` escapes; same for 5000-deep objects inside `options`. Cause:
   pydantic's parser refuses the depth with a `ValidationError` (caught at `:219`), the
   handler then calls `_peek` (`:186-195`), whose `json.loads` raises `RecursionError`, and
   `_peek` catches only `ValueError` (`:190`). Depth 200 is handled correctly
   (`BAD_REQUEST`, "recursion limit"). Fix: `except (ValueError, RecursionError)` in `_peek`
   — or simply `except Exception` there, since `_peek` is best-effort by definition — and a
   regression test with depth 5000.
2. **Medium — unbounded work from caller-controlled options.** `AcOptions.max_iter` has
   `ge=1` and no upper bound (`ac_newton.py:94`; `max_q_rounds` likewise `:96`), and
   `run_json` hands both to an untrusted caller. A non-converging case whose iterates stay
   finite never trips the non-finite guard: probe, case14 with a 1e6 MW load →
   `max_iter=20` 0.30 s, `200` 2.9 s, `2000` 28.4 s (≈ 14 ms/iteration, mismatch
   oscillating 1e6–2e9 MVA, never NaN); a 10-minute probe with `max_iter=10**6` was killed
   by the harness timeout. Fix: `le=1000` on `max_iter` and `le=100` on `max_q_rounds` (the
   defaults are 20 / 10; MATPOWER's ceiling is 10–30), plus a divergence guard in
   `newton_raphson` (stop when the norm exceeds, say, 1e6 × the starting norm). Payload
   size (a 10 MB `job_id` is accepted and echoed) is the transport layer's job and is fine
   to leave undocumented-but-known.
3. **Low — `pages.yml` grants `pages: write` and `id-token: write` to both jobs.**
   `.github/workflows/pages.yml:10-13` is workflow-level; only `deploy` (`:40-49`) needs
   them. Fix: keep `contents: read` at the top and move `pages: write`/`id-token: write`
   under `deploy:`.
4. **Low — the docs site loads MathJax from an unpinned major on a third-party CDN**
   (`mkdocs.yml:94`, `https://unpkg.com/mathjax@3/es5/tex-mml-chtml.js`). This is
   mkdocs-material's own recommended snippet, so it is conventional; pinning the exact
   version (`mathjax@3.2.2`) is a one-token hardening.

Not findings: pydantic rejects `NaN`/`Infinity` tokens in the network (`allow_inf_nan=False`
on every model: probe → `BAD_REQUEST`) and in options (`tol: NaN` → `BAD_OPTIONS`); extra
fields are refused at every level (`BAD_REQUEST`); `"abc"`, `[1,2,3]`, `""`, control bytes
→ `BAD_REQUEST` with `kind = ""` and no provenance.

## 5. Performance — **PASS**

Measured on case300 (probe script, in-process, under load): `solve_ac` q-off 0.28 s first
call / 0.20 s q-on second call; `ac_newton.newton` alone 0.107 s for 5 iterations;
`solve_dc` 34 ms; `matpower.load` 57 ms; `NetworkArrays.from_network` 3.3 ms.

- No dense n×n intermediates: `_dsbus_dv` returns CSR matrices with nnz 1118 of 90 000
  (`probe: dS/dVm type csr_matrix nnz 1118`); the Jacobian has nnz 3736; `sparse.bmat(…,
  format="csc")` feeds `splu` directly (`ac_newton.py:185-191`).
- `splu` per iteration is necessary (the Jacobian changes every step) and is not the
  bottleneck: per iteration `_dsbus_dv` 7.5 ms, fancy-index slicing + `bmat` 7.2 ms,
  `splu` 4.0 ms. The two assembly steps are ~80 % of an iteration; a later wave could build
  J from branch triplets (MATPOWER-style) or precompute selection matrices for a ~2×
  headroom. Not needed for AC-7.
- Q-limit loop cost is one warm NR per round and rounds are bounded by the number of PV
  buses (pins accumulate); case300 q-on: 7 iterations, 1 round.
- Results construction: `ac_result_from_arrays` 28 ms for case300 (780 pydantic rows),
  `model_dump_json` 3 ms, `to_arrays` 1.1 ms. ~10-25 % of a solve; acceptable, and the
  per-row validation is what rejects `inf`/`nan`, so leave it.
- Test suite: 484 tests, 226 s wall here under contention (S4 recorded 34 s idle for 451;
  floor to confirm). Slowest: `test_lodf_matches_brute_force_outage[case300]` 36 s — an M1
  test now parametrised over case300 because S1 appended it to `FIXTURES`; consider a
  `slow` mark or a smaller fixture set for the brute-force tier. Parity fixtures are
  module-scoped and parametrised, so pandapower conversion happens once per (fixture, mode)
  — no repeated conversions per test. The seven examples run in the matrix
  (`test_examples_run.py`, ~6 s each here, subprocess) *and* in the dedicated CI job; the
  duplication is deliberate and commented (`ci.yml:49-52`).
- Docs build: `mkdocs build --strict` 32.5 s. Fine.

## 6. Duplication — **PASS** (with flags)

Shared-truth pairs, anchored on the ownership tables (epic §3, wave "Ownership additions"):

| Concept | Single site | Second site? | Agreement test |
| --- | --- | --- | --- |
| Effective roles / slack selection | `numerics.roles.effective_roles` | none in `src` (pf.ac, pf.dc, results consume) | `test_effective_roles_are_honoured_on_case14_roles`, `test_solve_dc_reports_effective_roles`, `test_roles_vs_pandapower` (AC-4) |
| Island repair | `model.islands` | none (`io.matpower` calls it) | `test_load_with_report_carries_typed_island_warning`, `test_repaired_network_round_trips_through_repair_unchanged` (AC-5) |
| Provenance | `results.ResultProvenance` | constructed at 3 sites (`pf/__init__.py:99,142`, `jobs/run.py:51`) — same type, no second *definition* | `test_run_pf_ac_on_case14_…` (`out.provenance == out.result.provenance`, version equality, AC-6) |
| Legacy warning strings vs `ImportReport` | `ImportIssue.__str__` | none (`as_strings` uses it) | `test_islands.py:74` `report.as_strings() == load_with_warnings()[1]` |
| pu conversion | `numerics.arrays` (÷) | `results.from_arrays` (×) — ratified by design item 5 | `test_to_arrays_follows_network_arrays_order` + every MW-level parity test |
| Branch flows | `pf/__init__.py:90-91` (AC), `pf/dc.py:96` (DC) | none in `results` | parity flows vs pandapower (AC 1e-4 MVA, DC 1e-9 MW) |
| MATPOWER column semantics | `io.matpower` | `tests/parity/_mpc_reader` — **intended** oracle duplication | column parity tier (M1) |
| Dense NR / dense Ybus | `pf.ac_newton`, `numerics.ybus` | `tests/unit/test_pf_ac_newton.py` dense oracle — **intended** | `test_matches_dense_newton_to_1e_10` |
| Bus-type codes | `numerics.arrays.BUS_TYPE_CODE` | tests hardcode `1, 2, 3` (acceptable) | — |

Findings:

1. **Medium — the slack-P balance rule is implemented twice with no agreement test between
   the two.** `pf/dc.py:99-101` and `pf/ac_newton.py:231-234` both encode "first in-service
   slack-bus generator absorbs the balance"; each is tested against its own oracle
   (`test_first_slack_generator_absorbs_the_balance`, `test_slack_balance_goes_to_the_first_slack_generator`)
   but nothing ties them to each other, so M3 could change one and not the other. Fix: one
   helper (`pf._common.absorb_slack_p(arr, p_bus_pu) -> gen_p_pu` or a `numerics` function)
   called by both, and the existing two tests become its agreement tests.
2. **Low — two voltage-setpoint derivations coexist.** `NetworkArrays.v_set` is "first
   in-service generator's v_set_pu" (`numerics/arrays.py:77-78`) and `EffectiveRoles.v_set`
   is last-wins (`numerics/roles.py:89`). After M2 no `src` module reads `arr.v_set`
   (grep: only `tests/unit/test_effective_roles.py:63,127,131` and
   `test_numerics_arrays.py:186`), so the first-wins array is a stale second truth whose only
   remaining role is to be asserted different from the real one. Fix: drop `v_set` from
   `NetworkArrays` (keep `gen_v_set`) or rename it `declared_v_set_first` with a docstring
   that says solvers must not use it.
3. **Low — provenance stamping is written out three times** (`pf/__init__.py:99-107`,
   `:142-150`, `jobs/run.py:51-65`), each repeating `engine="mambo-power"`,
   `version=mambo_power.__version__`, `elapsed_s=time.perf_counter() - clock`. A
   `ResultProvenance.stamp(kind, solver, started_at, clock, options)` classmethod would make
   the "version is never typed by hand" promise (`results/provenance.py:4-6`) structural.
4. **Low — `SUBSTITUTE_KV = 1.0  # mirrors DEFAULT_BASE_KV` appears in three test files**
   (`test_ac_vs_pandapower.py:53`, `test_dc_vs_pandapower.py:52`,
   `test_roles_vs_pandapower.py:43`). This is not oracle code — it is the importer's own
   constant — so importing `mambo_power.io.matpower.DEFAULT_BASE_KV` removes a silent
   divergence if the default ever changes (DC proves invariance to it; AC does not).
5. **Low — examples `01` and `06` build the same 3-bus `mini` network** verbatim. Examples
   are meant to be self-contained, so this is acceptable; noting it so nobody "fixes" it by
   adding a shared helper that the snippet embedding could not show.

---

## Verdicts

| Axis | Verdict |
| --- | --- |
| 1. Correctness | PASS (6 flags, 2 medium) |
| 2. Readability | PASS (7 flags, all low) |
| 3. Architecture | PASS (4 flags, all low) |
| 4. Security | **FLAG** (1 contract breach + 1 unbounded-work, both medium; 2 low) |
| 5. Performance | PASS |
| 6. Duplication | PASS (5 flags, 1 medium) |

No axis FAILs: no wrong number reaches a user, no boundary is crossed in the wrong
direction, every primitive has a caller and a test. The security FLAG is the one
contract the wave states and does not keep ("nothing crosses `run_json`").

## Recommended fold order

1. **S4.1 `_peek` RecursionError** (two lines + one test) — restores the stated contract.
2. **S4.2 bounds on `max_iter` / `max_q_rounds`** (+ divergence guard) — closes the
   unbounded-work path on the same boundary.
3. **C1 `message` on `AcPowerFlowResult`** — makes the manual's diagram true for the public
   result and satisfies epic §1 "diagnostics".
4. **C2 named error for DC-unsolvable networks** (`x == 0`, singular B′) with a structured
   job code — stops filing user data as `INTERNAL`.
5. **D1 one slack-P helper** for AC and DC with its agreement test.
6. **A4 `::: mambo_power.pf.ac_newton` in `docs/api/pf.md`** — AC-8 completeness (one
   block; strict build re-run).
7. Docs/text batch (no behaviour): A1 spec sentence on `repair_islands_entities`, A2 pu
   boundary wording (arrays docstring + epic §2), R6 "3.14 opt-in", R7 timing condition,
   C3 loading note, C4 per-gen edge sentence, S4.3 pages permissions, S4.4 MathJax pin.
8. Code tidy batch: R1 flows into `AcSolution`, R2 dataclass for `RepairedEntities`, R4
   dead `case300` branch, R5 `FIXTURES`, D2 drop/rename `arr.v_set`, D3 provenance
   stamp helper, D4 import `DEFAULT_BASE_KV`, A3 `FailureCode` test, C5 single-gen Q
   assignment, C6 `vm_pu > 0` guard.

Items 1-6 change behaviour or public surface and each needs its test; 7-8 are safe to
fold together. Nothing here blocks the wave's numerical claims — the parity evidence stands.
