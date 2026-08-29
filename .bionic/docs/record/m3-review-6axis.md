# M3 / Step 6 — six-axis review (stance 1)

Wave M3 opf-n1, worktree `C:\Claude Projects\mambo-power-m3`, diff `dcdc1c9..8fc8581`
(the whole wave, base to final fold commit; 42 files, +3555/−59). Reviewed 2026-08-24 against
the wave spec (Requirements W1-W9, AC-1..9, Design 1-9), epic §Design (module table, ownership)
and the plan's Verification Matrix/Assumptions (A1-A6, not re-raised). Every claim below carries
its proving command/output or a `file:line`; anything else is marked `unverified`. This review
does not re-run the coverage/power/authenticity analysis `m3-audit.md`/`m3-r2-reaudit.md`
already did — it is scoped to the six axes below, several of which surface findings neither
audit went looking for (both audits' `ptdf`/PTDF hits are the pre-existing QP-vs-theta
formulation caveat, not the double-computation finding in §5 below).

Evidence run in the worktree (read-only; `git status --porcelain` empty before, during and
after):

```
git rev-parse --short HEAD          -> 8fc8581 (wave/03-opf-n1)
git status --porcelain              -> (empty)
```

Timing/architecture probes below were run directly against the installed package
(`uv run --no-sync python -c "..."`), not edits to the tree — confirmed with `git status
--porcelain` staying empty after each.

---

## 1. Correctness — **PASS** (with flags)

The LP/QP formulation, the PWL epigraph layering, the LODF sign fix, and
`FeasibilityReport`'s violation logic are all right where checked; the flags are untested edges
in `FeasibilityReport`, not wrong numbers.

**LP/QP + PWL index layering (`opf/dc_opf.py:223-376`), verified correct.** Columns are
`[dispatch_0..dispatch_{n_gen-1}, pwl_cost_0..pwl_cost_{n_pwl-1}]` (PWL columns appended after
dispatch, `:281`); rows are `[balance, flow_0..flow_{n_branch-1}, epigraph_0..]` (epigraph rows
appended after balance/flow via a second `addRows` call, `:338-346`, so `n_rows = 1 +
arr.n_branch` at `:302` is still the correct balance+flow row count when epigraph rows exist).
Three things keep the two extensions (S2's QP, S3's PWL) from corrupting each other under
layering, all confirmed by reading, not assumed:

- A PWL generator's `cost_coeffs` row is forced all-zero by `_cost_coeffs`
  (`opf/__init__.py:60-65`, `continue` before any coefficient is written), so
  `np.flatnonzero(c2)` (`dc_opf.py:263`) never includes a PWL generator's dispatch column in the
  Hessian, and `changeColsCost` (`:262`) sets its linear cost to 0 — its entire cost enters only
  through the epigraph rows, never double-counted against the QP/LP objective.
- `balance_row`/`flow_rows` (`:311-312`) are built over `n_gen` columns only — the PWL `cost_g`
  columns are absent from their CSR construction (not zeroed, structurally excluded), so a PWL
  generator's auxiliary cost variable cannot leak into the physical balance or flow constraints.
- Result extraction slices `sol.col_value[:n_gen]` / `sol.col_dual[:n_gen]` and
  `sol.row_dual[1:n_rows]` (`:363-367`) — exactly the pre-epigraph column/row ranges, because
  epigraph rows/PWL columns are appended *after* balance/flow/dispatch are already built, so
  their indices never shift. Probed on the shipped `case14_pwl.m` fixture (mixed quadratic +
  PWL, as the fixture is documented to be, `case14_pwl.m` PROVENANCE.md) via
  `tests/unit/test_opf_dc_case14_pwl.py` (26 tests total across the three PWL test files, plan.md
  AC-5 evidence) — dispatch and duals both match the independent lambda-iteration oracle.

**LODF sign fix (`contingency/n1.py:76-97`), verified right, not just re-tested.**
`numerics/lodf.py:1-11`'s own docstring defines `LODF[l,k] = h_k[l]/(1-h_k[k])` as "the fraction
of branch k's pre-outage flow that appears on l after k is removed" — i.e. `post[l] = pre[l] +
LODF[l,k]*pre[k]` needs the *signed* `pre[k]`, not `|pre[k]|`. `screen_n1` now feeds
`base_flow_signed_mw = base_sol.p_from_pu * arr.base_mva` (`pf.dc.solve`'s own signed
`p_from_pu`, `pf/dc.py:60-62`, `Bf·θ + pf_shift`) straight into the formula and takes `np.abs`
only of the final `estimated` (`n1.py:95-97`) — matching the LODF module's own algebraic
derivation exactly, not just matching AC-6's brute-force count. This is not "trading one edge
case for another": the old (buggy) unsigned version was wrong for *any* branch whose declared
from/to direction opposes its actual flow direction, which is common, not an edge case — S4's
own case14 count (17→18 outages, 81→86 pairs, m3-s4-report.md) shows the bug was live-firing on
real fixture data. AC-6's brute-force agreement (exact match on all 5 fixtures, no LODF
involved on the oracle side at all) is independent, sign-convention-free proof the corrected
formula is right, not merely self-consistent.

**`FeasibilityReport` (`results/feasibility.py:55-93`) — logic correct, two named edges
untested.**

- `loading_pct > THERMAL_LIMIT_PCT` (`:72`, strict) — a branch loaded to *exactly* 100.0% is
  correctly not a violation (the boundary belongs to "at rating", not "over rating"). Verified
  by reading; **no test exercises `loading_pct == 100.0` exactly** — both
  `test_feasibility_report_catches_a_thermal_violation` (`tests/unit/test_feasibility.py:51-66`,
  asserts `loading_pct > 100.0`, `:66`) and the clean-case test use a margin, not the exact
  boundary. `grep -n "loading_pct == 100\|== 100.0" tests/unit/test_feasibility.py` → no
  match. Low-severity (the code is unambiguous), but this is exactly the edge the task brief
  asked about and it is a real, unverified-by-test corner.
- The `if`/`elif` bound check (`:80-86`) correctly handles a bus with only one of
  `v_min_pu`/`v_max_pu` set (`bound.v_min_pu is not None and ...` / `elif bound.v_max_pu is not
  None and ...`, each guarded independently) — a bus with only `v_max_pu` set never enters the
  first branch (short-circuits on `None`) and correctly falls to the `elif`. Verified by
  reading. `grep -n "v_min_pu=None\|v_max_pu=None"` across `tests/`/`src/` → **no hit**: every
  test network in `tests/unit/test_feasibility.py:21-28` sets both bounds or neither
  (`_net(..., v_min_pu=..., v_max_pu=...)`, always both non-`None` or both defaulted). The
  single-bound path is untested end-to-end, though the two-line guard logic is unambiguous by
  inspection and `model/entities.py:41-42` confirms both fields are independently optional
  (`float | None = Field(default=None)`).

Not a finding, confirmed correct: `elif` (not two independent `if`s) at `:80-84` means a bus
cannot register two violations from one solve — physically correct, since a single `vm_pu`
cannot be simultaneously below `v_min_pu` and above `v_max_pu`.

## 2. Readability — **PASS**

Module sizes are reasonable: `opf/dc_opf.py` 376 lines (the LP builder, including a genuinely
long formulation docstring — appropriate for the module doing the most numerically subtle
work in the wave), `opf/__init__.py` 167, `contingency/n1.py` 160, `contingency/__init__.py` 60,
`results/feasibility.py` 93, `results/n1.py` 76, `results/opf.py` 80 (`wc -l` above). No module
crosses the 400-line line M1/M2's own review implicitly treated as the concerning threshold.

Docstrings are substantive and, notably, *derive* their own numbers rather than assert them:
`opf/dc_opf.py:1-79`'s module docstring walks the full balance-row/flow-row/PWL-epigraph
derivation with the algebra spelled out (`const_k = pf_shift_mw_k - Σ...`, `:292-294`); the
AC-2 hand-built test (`tests/unit/test_opf_dc.py:1-22`) derives its own expected numbers by
hand and cross-checks them against `numerics.ptdf`'s already-trusted output before ever calling
`dc_opf` — a reader can verify the test's own oracle, not just trust it. This is the same
discipline M2's review praised in `ac_newton.py`.

**`OpfDcOptions`/`OpfSolution`/`OpfDcResult`'s relationship is clear from one file's worth of
reading, mirroring the already-established `AcOptions`/`AcSolution`/`AcPowerFlowResult` split
from M2** — a reader who has seen the M2 pattern needs zero extra context; a reader who has not
gets it from `opf/__init__.py:1-11`'s module docstring, which states the three-file split
explicitly ("mirrors `solve_dc`/`dc.solve`") rather than leaving it implicit. `OpfDcOptions`
lives in `dc_opf.py` (array-level module, since `ac_check` is read only by the wrapper but the
type itself has no `Network` dependency — `dc_opf.py:104-114`'s own docstring explains this
placement choice, including *why* `dc_opf` ignores `ac_check` via `del options`); `OpfSolution`
is the array-level LP/QP answer (`dc_opf.py:142-161`); `OpfDcResult` is the Network-facing,
id-keyed pydantic result (`results/opf.py:51-80`). One low nit: `OpfDcOptions` living in
`opf/dc_opf.py` while its only reader (`ac_check`) is consumed by `opf/__init__.py` means a
reader chasing "what does `ac_check` do" starts in one file and finishes in another — the
module docstring pre-empts the confusion, but it is still a real hop.

Minor: `contingency/__init__.py:9-14`'s docstring explaining the deliberate `n1`/`n1`
submodule-vs-function name collision is a genuinely good practice — flagging a construct a
future reader would otherwise find surprising, in the exact place they would be surprised by
it, rather than after the fact in a design doc.

No flags rise above low: nothing here obscures behavior or misleads a reader.

## 3. Architecture — **PASS**

**Import graph matches the (now-fixed, per S7) diagram exactly.**
`grep -n "^from mambo_power\|^import mambo_power" src/mambo_power/opf/*.py` →
`opf → model, numerics.arrays, numerics.bbus, numerics.ptdf, pf (solve_ac), results`;
`grep ... src/mambo_power/contingency/*.py` → `contingency → model, numerics, pf (dc), results`.
`docs/design/architecture.md` (diff `dcdc1c9..8fc8581`) states exactly these four edges for each
of `opf`/`contingency` (`opf --> model/numerics/pf/results`, `contingency --> model/numerics/pf/
results`, lines added in the diff) — verified against the real imports, not assumed from the
diagram. `jobs --> opf`, `jobs --> contingency` (new edges) match `jobs/registry.py:18,20`'s
imports. No edge in either direction that the diagram does not also claim (no `opf →
contingency`, no `contingency → opf`, no reverse `results → opf` — confirmed by the same grep
turning up nothing in `results/`).

**Closure check — every new public primitive has a real caller and Step-5 evidence reached it:**

| Primitive | Production callsite | Test | Example |
| --- | --- | --- | --- |
| `opf.solve_dc_opf` | `jobs.registry._run_opf_dc` (`registry.py:72-90`) | `test_opf_solve_dc_opf.py`, `test_opf_vs_pandapower.py`, `test_opf_vs_pypsa.py`, `test_jobs.py` | `examples/08_opf_and_n1.py:28,54` |
| `opf.dc_opf.dc_opf` | `opf.solve_dc_opf` (`opf/__init__.py:96`) | `test_opf_dc.py` (direct, AC-2/AC-3), `test_opf_dc_pwl.py`, `test_opf_dc_case14_pwl.py` (direct) | via `08` |
| `opf.dc_opf.lmp_decomposition` | `opf.solve_dc_opf` (`opf/__init__.py:111`) | `test_opf_dc.py::test_lmp_decomposition_is_standalone...` (direct, zero calls to `dc_opf`, AC-3) | via `08`'s LMP printout |
| `contingency.n1` | `jobs.registry._run_n1` (`registry.py:93-96`) | `test_contingency_n1.py` (AC-4 behavioral), `test_contingency_n1_brute_force.py` (AC-6), `test_jobs.py` | `examples/08_opf_and_n1.py:76` |
| `contingency.n1.screen_n1`/`confirm_n1` | `contingency.n1` (`contingency/__init__.py:46-47`) | `test_contingency_n1.py` (direct import, `:29`) | via `08` (through the package function) |

`grep -rn "from mambo_power.opf.dc_opf import\|from mambo_power.contingency.n1 import"
tests/ examples/ src/` (run above) confirms every array-level primitive is imported directly by
at least one test module, not only reached transitively — the discipline the audit's own
closure check used, re-run independently here and agreeing with it (`m3-audit.md` found no
dead substrate; this pass reaches the identical conclusion by tracing the same edges from
scratch).

No architecture flags.

## 4. Security — **FLAG** (one real gap, low-to-moderate; not a contract breach)

`OpfDcOptions` (`opf/dc_opf.py:104-122`) has exactly one field (`ac_check: bool`) — no
numeric knob at all, so it cannot reproduce M2's `max_iter`/`max_q_rounds` class of finding
directly. `N1Options` (`contingency/n1.py:42-46`) is empty. HiGHS's own solve has no
caller-exposed iteration/time-limit knob in this wave's surface, so the LP/QP solve itself is
not a caller-tunable unbounded-work vector the way `AcOptions.max_iter` was.

**But the unbounded-work vector M2's fold looked for in *options* exists here in *network
data*.** `PiecewiseCost.points` (`model/entities.py:78-80`) has no `max_length` — only
`validate_network` (`model/network.py:182-197`) checking "at least two, strictly increasing
`p_mw`", no upper bound. Every breakpoint contributes one epigraph row
(`opf/dc_opf.py:322-346`) to the LP `dc_opf` builds. Since `jobs.run`'s `opf.dc` kind takes the
full network inline (`SolveRequest.network`, `jobs/models.py:88`) and only re-validates it with
`validate_network` (which does not bound point count) before calling the runner, a caller can
submit an arbitrarily large `points` list through `run_json` and force a correspondingly large
LP. Probed directly (read-only, no edits — `git status --porcelain` empty before/after):
a single generator's `PiecewiseCost` with 100 / 2,000 / 20,000 points →
`solve_dc_opf` 0.038s / 0.034s / 0.169s (roughly linear, not runaway — HiGHS's own LP solve
does not exhibit pathological blowup here), but nothing stops a caller from going further; this
is the same *class* of gap the M2 R1 fold closed for `max_iter`/`max_q_rounds` (unbounded
caller-controlled work reaching a solve), just moved from options to network data, and this
wave's own R1 fold did not look for it (its scope was the AC-1 PyPSA gap plus docs/MathJax
items, per `m3-r1-fold-report.md`). Severity: low-to-moderate — growth is linear, not
exponential, and a genuinely adversarial payload (millions of points) would still cost seconds,
not hours, but it is a real, unbounded, caller-reachable resource-consumption path that the
wave's own security-conscious precedent (M2's fold) would have flagged had it existed then.
Fix shape: a `max_length` on `PiecewiseCost.points` (e.g. a few hundred, generous for any real
convex marginal-cost curve) enforced either as a pydantic field constraint or a
`validate_network` check — the latter is more consistent with the wave's existing
"at least two" check living there already.

**`INFEASIBLE_LP`/`UNBOUNDED_LP` messages leak nothing sensitive.** Traced the full string
path: `OpfSolution.message` is always exactly
`f"dc_opf: HiGHS reported model status {status!r}"` (`opf/dc_opf.py:356`, only HiGHS's own
model-status string, one of a small fixed vocabulary — `"Infeasible"`, `"Unbounded"`, etc. —
never network data); `registry.py:87-90` wraps it as `f"opf.dc LP/QP is {infeasible/unbounded}
(status=...): {result.message}"` with no additional interpolation of caller data;
`jobs/run.py:166-169` passes that string through to `StructuredError.message` verbatim. No
dispatch value, no bus/branch id, no cost coefficient ever appears in either failure message —
confirmed by reading every hop, not just the terminal string. `duals`/`dispatch_mw` are `None`/
all-zero on any non-Optimal status (`OpfSolution` docstring, `:158-159`), so there is nothing
sensitive to leak even structurally.

Not findings, checked directly: `OpfDcResult`/`N1Result`/`FeasibilityReport` all keep
`extra="forbid"`/`allow_inf_nan=False` (`results/opf.py:60`, `results/n1.py:25,48,68`,
`results/feasibility.py:23,45`), consistent with every other M1/M2 result type; no new file I/O,
subprocess, or eval-like surface introduced anywhere in the diff (`git diff --stat` above shows
only `.py`/`.md`/`.m` files, no config/workflow changes this wave touches beyond `mkdocs.yml`'s
nav, already covered by S7's own docs work).

## 5. Performance — **FLAG** (one real, quantified, moderate finding)

**`solve_dc_opf` computes the PTDF matrix twice per call for no reason.**
`opf/dc_opf.py:296` (`ptdf_matrix = compute_ptdf(arr)`, inside `dc_opf`, to build the flow-limit
rows) and `opf/__init__.py:110` (`ptdf_matrix = compute_ptdf(arr)`, inside `solve_dc_opf`, to
feed `lmp_decomposition` and reconstruct branch flows) are two independent calls to
`numerics.ptdf.ptdf(arr)` on the *same* `arr` within one `solve_dc_opf` invocation — the second
call's result is never derived from or cached against the first. Measured directly (read-only
probe, worktree unmodified — `git status --porcelain` empty before/after):

```
solve_dc_opf warm avg (case300, 5 reps) = 0.1163 s
ptdf(arr) warm avg (case300, 5 reps)    = 0.0362 s
```

`ptdf` alone is ~31% of `solve_dc_opf`'s total warm cost, and it runs *twice* inside that one
call — roughly **62% of `solve_dc_opf`'s warm runtime is spent computing the same PTDF matrix
a second time.** This is exactly the "recomputing something that could be computed once"
pattern the task brief asked about — just in `opf`, not `contingency`. Fix shape: have
`dc_opf` optionally accept a precomputed `ptdf_matrix` (or return the one it builds internally
alongside `OpfSolution`) so `solve_dc_opf` reuses it instead of recomputing.
`contingency.screen_n1`, by contrast, computes `ptdf(arr)` exactly once (`n1.py:86`, passed
directly into `lodf(arr, ptdf(arr))`) — no analogous bug there.

**The `m3-step5-tests-floor.md` `contingency.n1` 0.7559s vs `opf.solve_dc_opf` 0.3943s
comparison is measuring something other than what it looks like it's measuring, and the real
cause is in `screen_n1`'s Python-level loop, not the DC-re-solve confirm stage.** The floor's
own script ran on the *unrated* case300 fixture (default `N1Options`, no derived ratings), and
its own output line says so directly: `n1_contingencies=0` (`m3-step5-tests-floor.md:217`) — the
LODF screen flagged nothing, so `confirm_n1`'s re-solve loop never ran at all for that
measurement. Traced and timed the actual cost breakdown (read-only probe on case300,
`n_bus=300, n_branch=411`):

```
pf.dc.solve(arr)      0.0204 s
ptdf(arr)              0.0798 s
lodf(arr, h)            0.0238 s
bridges(arr)             0.0041 s
screen_n1's own outage loop (411 outages, pure Python)   0.2070 s   <- dominant cost
```

The screen loop itself — not the base solve, not PTDF, not LODF — is the single largest
contributor, and it is a Python-level inefficiency, not an inherent algorithmic cost: for each
of the 411 outages, `screen_n1` builds `violating = [branch for branch in
range(arr.n_branch) if branch != k and estimated[branch] > rating_mva[branch] + TOL]`
(`contingency/n1.py:98-102`) — a pure-Python list comprehension doing scalar `numpy` indexing
(`estimated[branch]`, `rating_mva[branch]`) ~411 times per outage, ~169,000 scalar-indexed
comparisons total, each carrying `numpy` per-element overhead far above a vectorized boolean
mask. A vectorized rewrite (`mask = (estimated > rating_mva + TOL); mask[k] = False; violating
= np.flatnonzero(mask)`) would do the identical O(n_branch²) work at array-operation speed
instead of Python-loop speed — this is squarely the same class of finding as the double-PTDF
call above, just in the other new package. Neither finding threatens any AC or timing gate (AC-6's
own case300 numbers, 5.6s isolated total for screen+confirm+brute-force combined, stay
comfortably under the ~10s unit-tier threshold even with this inefficiency included) but both
are real, easily fixed, and worth folding before M4 starts composing `opf.dc_opf` and
`contingency.n1` as building blocks — a 62%-of-runtime redundant computation and an avoidable
O(n²) Python-loop cost are exactly the kind of thing that compounds once a later wave calls
these functions in a hotter loop (e.g. `market.nodal` calling `lmp_decomposition`/`dc_opf`
repeatedly, per the epic's own stated composition plan).

No other wasteful pattern found: `confirm_n1`'s per-outage `NetworkArrays.from_network(outaged)`
rebuild (`n1.py:132`) does re-derive the full array set from the pydantic `Network` on every
flagged outage rather than patching one field of a cached `NetworkArrays`, but this was already
measured and is small in absolute terms (`m3-s4-report.md`'s own isolated case300 number,
`confirm_n1` 3.96s for 293 re-solves ≈ 13.5ms/outage total including the rebuild, the DC solve,
and the flag construction) — not flagged as a separate finding, since the report already
quantified it and it is dwarfed by the two findings above in relative terms.

## 6. Duplication — **PASS** (with the two performance-axis items also read as duplication)

Ownership table, built exactly per the spec's Design section and checked against the actual
code, not assumed from the spec text:

| Concept | Single site | Consumer(s) | Agreement test |
| --- | --- | --- | --- |
| DC-OPF dispatch/duals | `opf.dc_opf.dc_opf` (`opf/dc_opf.py:223`) | `opf.solve_dc_opf` (`opf/__init__.py:96`), `jobs` kind `opf.dc` (`registry.py:83`) | `test_opf_vs_pandapower.py`, `test_opf_vs_pypsa.py` (AC-1) |
| LMP decomposition | `opf.dc_opf.lmp_decomposition` (`opf/dc_opf.py:210`) | `OpfDcResult.lmp` via `solve_dc_opf` (`opf/__init__.py:111`) | `test_opf_dc.py::test_lmp_decomposition_is_standalone...` (AC-2/AC-3); M4's settlement-identity test is the named future consumer, not yet written |
| N-1 screen-vs-confirm | `contingency.n1` (`contingency/__init__.py:32`, wrapping `contingency.n1.screen_n1`/`confirm_n1`) | `results.N1Result`, `jobs` kind `n1` (`registry.py:96`) | `test_contingency_n1_brute_force.py` (AC-6) |
| AC feasibility | `results.FeasibilityReport`/`feasibility_report` (`results/feasibility.py:42,55`) | `OpfDcResult.ac_check` via `opf.solve_dc_opf` (`opf/__init__.py:156`) | `test_feasibility.py` (AC-7) |

Each concept has exactly one implementation site; grepped for a second definition of each
(`grep -rn "def dc_opf\b\|def lmp_decomposition\b\|def screen_n1\b\|def confirm_n1\b\|def
feasibility_report\b" src/`) — one hit each, all in the files above.

**`absorb_slack_p` (M2's R1-fold slack-balance helper) — checked for an analog, found one, and
confirmed it is genuinely reused, not reimplemented.** `contingency.n1.confirm_n1` calls
`pf.dc.solve` (`n1.py:133`), which itself calls `absorb_slack_p` internally (`pf/dc.py:39,
98`) — so N-1's confirming re-solve inherits the shared slack-absorption logic automatically,
with no second implementation anywhere in `contingency`. `opf.dc_opf`, by contrast,
**legitimately does not** need or duplicate `absorb_slack_p`: it is solving a different problem
(every generator, including the one at the slack bus, is a *free LP decision variable* bounded
by `[p_min, p_max]` — `dc_opf.py:258-261` — not a fixed dispatch whose balance residual gets
assigned to one generator after the fact). `dc_opf.py:126-133`'s own `OpfDuals.balance`
docstring names this precisely: the balance dual *is* the slack-bus generator's marginal cost
when unconstrained, a genuinely different mechanism from `absorb_slack_p`'s "first in-service
slack generator absorbs the residual" rule. Confirmed no `dc_opf`/`opf` code path re-derives or
re-implements slack-residual assignment — `grep -n "slack" src/mambo_power/opf/*.py` finds only
the `OpfDuals.balance` docstring's explanatory prose, no assignment logic. The spec's own AC-1
evidence block (plan.md, "A real formulation difference was found and checked") independently
names this same distinction from the parity-testing side — this review reaches the identical
conclusion from the code side.

**The two performance findings above are also duplication in the literal sense** (the same
computation — PTDF — performed twice for one logical answer) and are cross-referenced here
rather than re-argued: `opf/dc_opf.py:296` and `opf/__init__.py:110` are two call sites
computing the identical `ptdf(arr)` for one `solve_dc_opf` invocation, with no shared cache
between them — the fix (thread the PTDF matrix through once) closes both the performance cost
and the duplication.

No other duplication found: `VIOLATION_TOL_MVA` (`contingency/n1.py:37`) is a single named
constant, not restated; `THERMAL_LIMIT_PCT` (`results/feasibility.py:17`) likewise. PWL-cost
extraction logic lives once in `opf/dc_opf.py:187-207`/`_cost_coeffs`
(`opf/__init__.py:43-73`), not duplicated between the array- and Network-level layers — the
array level takes raw `pwl_costs`/`cost_coeffs`, the Network level only derives them from
`Generator.cost`, no overlapping logic.

---

## Verdicts

| Axis | Verdict |
| --- | --- |
| 1. Correctness | PASS (2 low flags: untested `loading_pct == 100%` and single-bound-set edges in `FeasibilityReport`; both verified correct by reading, neither tested directly) |
| 2. Readability | PASS (1 low flag: `OpfDcOptions`/`ac_check` split across two files, pre-empted by docstring) |
| 3. Architecture | PASS (no flags — import graph and closure check both confirmed exactly as diagrammed) |
| 4. Security | **FLAG** (1 low-to-moderate: `PiecewiseCost.points` has no upper bound, an unbounded-work vector via network data reaching `jobs.run`'s `opf.dc` kind — same class as M2's `max_iter` finding, moved from options to data) |
| 5. Performance | **FLAG** (2 moderate, both quantified: `solve_dc_opf` computes PTDF twice, ~62% of its warm runtime; `screen_n1`'s per-outage Python list comprehension dominates `contingency.n1`'s cost, explaining the floor report's "n1 costs ~2x dc_opf" number, which turns out to reflect 0 confirmed outages, not the re-solve loop) |
| 6. Duplication | PASS (0 real duplication beyond the two performance findings, which are cross-referenced, not double-counted; `absorb_slack_p` correctly reused by `contingency` and correctly *not* reused by `opf`, for a real, checked reason) |

No axis FAILs. Both FLAGs are real, quantified, and non-gating: neither threatens any AC, neither
is a contract breach analogous to M2's `_peek` RecursionError, and both are cheap to fold
(estimated: PTDF threading is a same-shape change to two functions' signatures; the screen-loop
vectorization is a four-line rewrite of one list comprehension; the `PiecewiseCost.points` bound
is one field constraint). All three are worth folding before M4 starts composing `opf.dc_opf`
and `contingency.n1` directly, per the epic's own stated plan.

## Recommended fold order

1. **P1 — thread the PTDF matrix through `dc_opf`→`solve_dc_opf` once** (`opf/dc_opf.py:296`,
   `opf/__init__.py:110`) instead of computing it twice. Highest-leverage single fix in this
   review: ~62% of `solve_dc_opf`'s own warm runtime on case300, and every future caller
   (`market.nodal` per the epic's composition plan) inherits the fix for free.
2. **P2 — vectorize `screen_n1`'s per-outage violation check** (`contingency/n1.py:98-102`),
   replacing the Python list comprehension with a boolean-mask/`np.flatnonzero` construction.
   Explains and closes the dominant cost behind the floor report's `contingency.n1` timing
   number.
3. **S1 — bound `PiecewiseCost.points`** (`model/entities.py:78-80` or the check in
   `model/network.py:182-197`) with a `max_length` (or an explicit `validate_network` check)
   generous enough for any real convex marginal-cost curve. Closes the one caller-reachable
   unbounded-work path this wave introduces.
4. **T1 — add the two named-but-untested `FeasibilityReport` edges** as explicit unit tests:
   `loading_pct == 100.0` exactly (not a violation) and a bus with only one of
   `v_min_pu`/`v_max_pu` set (the other correctly never contributing a violation). Both are
   already correct by reading; this closes the gap between "correct" and "proven" for the
   exact edges the wave's own design called out.

Items 1-3 are small, scoped, behavior-preserving-or-hardening changes with an obvious test
each; item 4 is test-only, no production code change. Nothing here blocks the wave's own
acceptance criteria or its CONFIRMED audit verdict — this review found no wrong number, no
contract breach, and no dead substrate; it found two real efficiency gaps and one real
unbounded-input gap that the wave's existing evidence did not surface because none of its
tests were built to look for them.
