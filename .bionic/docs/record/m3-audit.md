# M3 audit — Step 5 exit gate (coverage · power · authenticity)

Auditor: m3-auditor (fresh, read-only; implemented, reviewed, and audited nothing in M3).
Written 2026-08-23 in worktree `C:\Claude Projects\mambo-power-m3` (wave head `f37815a`,
`wave/03-opf-n1`). `git status --porcelain` empty before and after every command below; no
edits, commits, or pushes made by this agent at any point. `uv` =
`C:\Users\mambo\AppData\Roaming\Python\Python314\Scripts\uv.exe`.

Inputs held: wave spec (W1-W9, AC-1..9, Design 1-9), epic spec §Design, plan (matrix, per-AC
evidence, dispatch ledger, Assumptions A1-A5), record/m3-research.md,
.bionic/tmp/m3-pypsa-diag-result.md, m3-s1..s7-report.md, m3-step5-tests-floor.md,
m3-walk-docs-site.md + walk-m3/ screenshots. Every factual claim here carries its command +
output, a direct code citation, or is labelled `unverified`.

## Headline

**Wave verdict: REFUTED as "implemented and proven," on one row, with substance intact
everywhere else and no behaviour defect found.** Every solver claim I re-executed reproduces
exactly (AC-1 pandapower parity 20/20, the AC-2/AC-3/AC-4/AC-6 unit bundle 19/19 with AC-6's
five confirmed-outage counts matching digit-for-digit, `mkdocs build --strict` exit 0). The
revert-and-watch demonstration (AC-4/AC-6's LODF sign-fix stubbed back to the unsigned bug it
replaced → all 5 of AC-6's parametrized fixtures plus 3 more n1 tests turn red, everything else
stays green) is **VALIDATED**, and validates more strongly than predicted (the request only
staked case14 as certain to fail; all five fixtures failed).

The one refutation is a proof gap, not a behaviour defect: **AC-1**'s literal criterion commits
to PyPSA `optimize` matching within a band on all 5 fixtures; PyPSA was never run inside the
wave's own Step 4 evidence chain — only in a separate Step 1/2 research diagnostic
(`.bionic/tmp/m3-pypsa-diag-result.md`) that is not cited as AC-1 evidence and was never turned
into a committed, repeatable test. The gap is honestly and clearly logged as an open carry-over
at every layer (S2's report, the plan's AC-1 readback) — this is materially different from, and
less severe than, M2's analogous AC-5 refutation, which rested on a *false* claim of coverage.
Here nothing is misrepresented; the matrix's flat "discharged" status in the summary table is
simply not qualified by the honest prose sitting two lines below it.

No wave-level coverage hole was found (§1) — every W1-W9 has both a design-item citation and an
AC-provenance citation, unlike M2's W7. One browser-verified correction to the walk artifact's
own framing: the MathJax rendering break the walk found on both new manual pages is **real but
pre-existing and site-wide**, not a defect this wave's docs work introduced — I reproduced the
identical partial-render failure on `docs/manual/numerics.md` (an M1/M2-era page untouched by
this wave), reproducibly across two page reloads (§3, browser re-execution). The walk's other
finding — the stale home-page status/roadmap — **is** genuinely this wave's own accountability
gap and should fold.

---

## 1. Coverage — requirement → design decision → criterion → evidence

### Mechanical seed (inverted citation maps)

```
$ grep -n "provenance: W|\(W[0-9]" wave-03-opf-n1.spec.md
```
(spec lines 125-221, read in full above). Every `W1`-`W9` appears at least once in an AC's
`provenance:` line and at least once as a Design item's parenthetical:

| Req | Design item(s) citing it | AC(s) citing it | Inbound = 0? |
|---|---|---|---|
| W1 | 1 (LP builder split) | AC-1, AC-2 | no |
| W2 | 1, 2 (LMP decomposition) | AC-3 | no |
| W3 | 3 (rating derivation) | AC-4 | no |
| W4 | 4 (PWL costs) | AC-5 | no |
| W5 | 5 (N-1) | AC-6 (**and see below**) | no |
| W6 | 6 (AC-feasibility) | AC-7 | no |
| W7 | 7 (jobs) | AC-8 | no |
| W8 | 8 (verification policy) | AC-1 (co-cited with W1) | no |
| W9 | 9 (docs) | AC-9 | no |

**No wave-level coverage hole** — unlike M2's W7 (zero inbound citations from either side), every
requirement here has both a design decision and a criterion pointing at it.

### Chain walk with judgment (the harder half: cited but weakly expressed)

One citation-precision nit, not a hole: **AC-4**'s criterion text ("at least one branch outage in
at least one fixture causes a violation under the derived ratings") is behaviourally a `W5`
(N-1 screen/confirm) claim as much as a `W3` (rating derivation) one, but AC-4's `provenance:`
line cites only `W3`. The plan's own AC-4 evidence block correctly splits this in half ("S1
delivered the fixture half... S4 still owes: the actual LODF-screen-then-reslve confirm") and
S4's behavioral-half addendum fills it in — so the chain is *substantively* whole (evidence
exists, cross-referenced correctly in the record), just not *formally* cited at the spec's
provenance-line level. Letter gap, substance present; a one-line fold fix (`provenance: W3, W5`)
would close it.

**AC-1's two named caveats, checked directly, not taken on faith:**

- **PTDF-vs-theta formulation caveat.** Read `src/mambo_power/opf/dc_opf.py` and
  `tests/parity/test_opf_vs_pandapower.py` directly. The matrix's claim — pandapower's `rundcopp`
  marks the slack generator `controllable=False` (a dependent balance-residual variable) while
  `dc_opf`'s PTDF formulation makes every generator, including the slack one, a normal bounded
  LP/QP variable, so the two are only guaranteed to agree when (a) no branch is rated and (b) the
  slack generator's own bounds never bind — holds up: `test_every_branch_is_unconstrained_so_
  no_flow_limit_dual_binds` exists and is one of the 20 tests I re-executed (below); the wording
  in both the wave spec's AC-1 and the plan's AC-1 tier-run is scoped correctly ("true on all 5
  fixtures today... not proven true in general," never overclaiming general equivalence). No
  overclaim found.
- **PyPSA gap.** Confirmed genuinely logged, not quietly absent: S2's report names it explicitly
  under "Carry-overs" and again under a dedicated "PyPSA (secondary oracle) was not attempted
  this slice" heading; the plan's AC-1 readback repeats this in full, including *why* (time went
  to the load-bearing QP-vs-LP finding) and cites the dispatch brief's own framing ("bonus, not a
  blocker"). This is genuinely disclosed. See §3 for why disclosure alone does not discharge the
  AC's literal criterion.

**AC-4/AC-6's rating-derivation dependency**, checked against `tests/_rated.py` directly (full
file read): the module docstring states plainly this is "a documented, test-time transformation"
of an already-owned fixture, explicitly *not* real MATPOWER data — no overclaim. S1's own
sanity-check that violations are actually producible at the chosen margin (`RATING_MARGIN = 1.2`)
is real, not assumed: the margin-sweep table in `m3-s1-report.md` shows real violation counts at
five candidate margins, and I independently re-ran the actual behavioral test (not the sweep
script) and got the exact same confirmed-outage counts the record claims (§3).

**AC-5's LP degeneracy**, checked against `tests/unit/test_opf_dc_case14_pwl.py` directly (full
file read): the test module docstring names the tie explicitly (gen-2's third segment slope
equals gen-3's second segment slope, both at the equilibrium price), and the test file asserts
gen-1/gen-4/gen-5 and the total cost (`6239.0`) at tight tolerance while the tied
gen-2/gen-3 residual (`RESIDUAL_MW = 22.8`) is asserted only as an approximate sum via floor +
residual, not a specific split. This is the correct way to test a degenerate LP — it does not
weaken the proof for the 3/5 non-degenerate generators or the total cost, which remain pinned
exactly.

---

## 2. Power — what would the observation have shown had the change been absent?

| AC | Observation | Counterfactual (change absent) | Paired positive/negative case? | Power |
|---|---|---|---|---|
| AC-1 | 20/20 parity, cost rel. diff ≤ 1.6e-11, dispatch abs. diff ≤ 1.42e-2 MW; every flow-limit dual exactly 0 on all 5 fixtures (re-run below) | Pure-linear cost LP (no QP) → wrong dispatch entirely on all 5 fixtures (the QP-vs-LP finding S2 names as "load-bearing for AC-1 to pass at all"). | Yes — nonzero, fixture-specific residuals pinned, not a zero readback. | Strong for pandapower half. **Zero for the PyPSA half** — no observation of any kind exists in the committed suite (§3). |
| AC-2 | Hand-built triangle: balance dual == 10.0 exactly; flow-limit dual nonzero only on the one rated, binding branch; bound reduced cost nonzero only on the one pinned generator | Wrong dual wiring → the two unrated branches or the two interior generators would show a nonzero value where the test asserts zero, or the binding branch would show zero. | Yes — three separate positive/negative pairs in one test (binding vs. two non-binding branches; pinned vs. two interior generators). | Strong |
| AC-3 | Two different `cost_coeffs` arrays over the identical `NetworkArrays` give two different, each-internally-optimal dispatches (`g2=85` vs `g2=30` MW) | A cost path secretly coupled to `Network` → both dispatches would come out identical regardless of the array passed in. | Yes — the two dispatches differing *is* the positive case; a bug would collapse them to one value. | Strong |
| AC-4 | Base-case dispatch never violates its own derived rating (case14/case118, unit test) + at least one real DC-re-solve-confirmed violation exists (case14: 18 outages / 86 pairs, re-run below) | Margin too loose → zero violations anywhere (a real risk S1's own sweep table rules out even at the loosest margin tried, 1.5). Margin too tight / formula wrong → base case itself would violate its own rating (asserted false by the same test). | Yes — "never violates the base case" and "at least one outage does violate" are the explicit positive/negative pair. | Strong |
| AC-5 | Case14_pwl dispatch matches an independent lambda-iteration oracle exactly on 3/5 generators and total cost; non-convex hand case raises `NonConvexCostError` pre-solve | Non-convex guard absent → the non-convex hand case would silently solve to a wrong-but-plausible-looking LP answer instead of raising (§2.1 of research: "there is no LP encoding of a non-convex PWL cost"). Wrong epigraph encoding → total cost (`6239.0`) or the 3 pinned generators would miss. | Yes — a raising case and a solving case, both asserted. | Strong |
| AC-6 | Screen-then-confirm confirmed-violating set equals a full brute-force sweep exactly, on all 5 fixtures (293/293 on case300) | LODF screen misses a real violation, or over-flags one that doesn't confirm → the two sets diverge. **This is exactly what the revert-and-watch demonstration produces** (§2a) — not a hypothetical counterfactual, an executed one. | Yes, and independently demonstrated live. | **Strongest row in the wave** |
| AC-7 | Hand thermal-overload case caught; hand voltage-bound case caught; clean case empty on both; `converged` passed through, not recomputed | Check absent → the overload/voltage hand cases would show empty violation lists instead of the expected entry. | Yes — one clean (negative) case paired with two violating (positive) cases, per the test names read directly (`test_feasibility_report_catches_a_thermal_violation`, `..._catches_a_voltage_violation`, `..._clean_case_has_no_violations`). | Strong (not independently re-executed by me — code/test-name read, within the 3-re-execution cap; see §3) |
| AC-8 | Infeasible hand case (`p_max_mw` collapsed) → `status="failed"`, `error.code=="INFEASIBLE_LP"`; RED confirmed by `git stash`-ing only the 4 implementation files (9 failed), popped (32 passed) | `pf.ac`'s own non-convergence stays `status="ok"` on the *same style* of hand case (`test_non_convergence_is_ok_with_converged_false`, unmodified) — the deliberate AC-8 distinction is the paired negative case. | Yes. | Strong |
| AC-9 | `--strict` exit 0, 0 real warnings; coverage test 2/2 — **but S7's own report records the check's power directly**: running the coverage test *unmodified* against the new packages first gave a vacuous 2/2 pass (packages never walked), then widening `PACKAGES` and removing the two submodule `:::` blocks reproduced a real failure, restoring them cleared it. | A missing manual/API page → an anchor/nav warning under `--strict` (non-zero exit). | Yes — S7 demonstrated the coverage test's power directly, the same discipline the mandate asks of a zero-readback claim, and I independently confirmed `PACKAGES` is in fact widened (`"opf", "contingency"` present) and the two `:::` blocks exist (§3). | Strong |

### 2a. Revert-and-watch (durable, whole-change demonstration)

Request written at `.bionic/tmp/m3-audit-revert-request.md`. Target: **the LODF sign-convention
fix in `contingency/n1.py::screen_n1`** (the AC-4/AC-6 scrutiny item named in my dispatch) — one
line, `base_flow_signed_mw = base_sol.p_from_pu * arr.base_mva` stubbed back to
`np.abs(base_sol.p_from_pu) * arr.base_mva`, reintroducing exactly the bug S4's report documents
finding and fixing. Predicted RED: 4 named unit tests in `test_contingency_n1.py` (the triangle
network's two physically-symmetric outages stop being flagged symmetrically) plus
`test_contingency_n1_brute_force.py`, "staked" only on case14 (S4's report quantifies the
discrepancy only there: 17/81 unsigned vs. 18/86 signed) with the other 4 fixtures marked
explicitly not-staked. Predicted GREEN: everything outside the two `contingency` test files, plus
one explicitly not-staked case inside them (`test_ac4_behavioral_case14_has_a_confirmed_n1_
violation`, which only asserts "at least one" violation exists, not an exact count).

Dispatched a fresh general-purpose agent as test-runner, throwaway detached worktree
`C:\Claude Projects\mambo-power-audit3` at `f37815a` (never `mambo-power-m3` itself — confirmed
below). Capture: `.bionic/tmp/m3-audit-revert-capture.md`.

### 2b. Revert-and-watch validation — **VALIDATED**

1. **Change really absent, then really restored.** Reported diff is byte-for-byte the requested
   one-line stub (`base_flow_signed_mw = base_sol.p_from_pu * arr.base_mva` →
   `np.abs(base_sol.p_from_pu) * arr.base_mva`), applied to a fresh checkout of `f37815a`. After
   capture, `git checkout --` restored it; `git status --porcelain` and `git diff HEAD` both
   empty; targeted tests re-ran green (14 passed) confirming the restore actually took. My own
   worktree was never entered: `git worktree list` (run by me, after) shows only `mambo-power`
   and `mambo-power-m3` — `mambo-power-audit3` is gone — and `git status --porcelain` in
   `mambo-power-m3` was empty both before I dispatched the demonstration and after it returned.
2. **Checks the matrix leans on.** The BEFORE baseline (14 passed: 9 + 5) is exactly `AC-2`
   through `AC-6`'s contingency tier-run count; the AFTER red set is 9 tests, all inside
   `test_contingency_n1.py`/`test_contingency_n1_brute_force.py` — precisely the files AC-4's
   behavioral half and AC-6 lean on. The full-repo-suite AFTER run (`9 failed, 564 passed`)
   confirms nothing outside those two files was touched by the stub — no test elsewhere silently
   depends on the LODF sign convention.
3. **The red is the failure I predicted, and slightly more.** All 4 named unit tests
   (`test_screen_n1_flags_the_direct_branch_when_either_indirect_leg_is_outaged`,
   `test_confirm_n1_confirms_the_screened_violation_with_the_exact_resolved_flow`,
   `test_n1_public_entry_point_returns_an_n1_result`, `test_n1_accepts_explicit_options`) failed
   exactly as predicted. The brute-force agreement test failed on **all five** parametrized
   fixtures (case14, case_ieee30, case57, case118, case300) — the request only staked case14 as
   certain, explicitly leaving the other four "not staked, record whichever actually fail." All
   five failing is consistent with the bug's mechanism (a sign flip on any branch whose from/to
   convention opposes its flow direction exists on every fixture, not uniquely on case14) and is
   not a surprise that undermines the demonstration — it is a stronger confirmation of the
   fix's real, wave-wide load-bearing role than the conservative prediction assumed.
4. **Direction-not-predicted item resolved.** `test_ac4_behavioral_case14_has_a_confirmed_n1_
   violation` — explicitly marked "not staked, genuinely uncertain" in the request — passed. This
   is consistent with the prediction's own reasoning (18 real violations at this margin leaves
   enough slack that even a buggy screen likely still finds at least one that confirms); recorded
   here as the request asked, not silently treated as a miss.

Verdict on the demonstration: **VALIDATED** — durable, auditable after integration, covers the
N-1 sign-convention fix end-to-end (hand-built unit cases and all 5 real-fixture brute-force
agreement cases at once), and demonstrates AC-6's evidence has real teeth, not vacuous agreement.

---

## 3. Authenticity — evidence produced at its declared tier; ≤ 3 re-executions

Tiers used by the matrix: T2 (AC-1, AC-5, AC-9), T1 (AC-2, AC-3, AC-4, AC-6, AC-7, AC-8). No T3
row (no live/real-external-surface claim is declared at T3 anywhere in this wave), so the T3
checklist does not apply — same as M2's audit. Every T2 row carries a `fixture-fidelity:` line;
the fixtures are structurally able to reach the guarded failure (AC-1: verbatim MATPOWER bytes
already M1-committed, oracle genuinely converges/diverges depending on the cost formulation, as
the QP-vs-LP finding proves; AC-5: a fresh derived fixture whose PWL edit is the exact thing
being tested; AC-9: the built site is the artifact itself).

### Re-execution 1 (T2 · AC-1)

```
$ uv run --no-sync pytest -q -m parity tests/parity/test_opf_vs_pandapower.py
20 passed in 19.13s
```
Record: "20 passed (5 fixtures x 4 tests)" (plan AC-1 tier-run). **Match.**

### Re-execution 2 (T1 · AC-2/AC-3/AC-4/AC-6)

```
$ uv run --no-sync pytest -q tests/unit/test_opf_dc.py tests/unit/test_contingency_n1.py \
    tests/unit/test_contingency_n1_brute_force.py -s
case14: screen+confirm=0.232s brute_force=0.196s confirmed=18 outages
case_ieee30: screen+confirm=0.444s brute_force=0.514s confirmed=34 outages
case57: screen+confirm=1.530s brute_force=1.530s confirmed=75 outages
case118: screen+confirm=1.553s brute_force=1.751s confirmed=166 outages
case300: screen+confirm=4.747s brute_force=5.713s confirmed=293 outages
19 passed in 20.81s
```
Record: AC-2 5 passed + AC-4 behavioral 1 passed + AC-6 5 passed + the rest of
`test_contingency_n1.py`'s 9 = 5 + 9 + 5 = 19 (plan AC-2/AC-4/AC-6 tier-runs). **Match** — and
the confirmed-outage counts (18, 34, 75, 166, 293) match the plan's AC-6 table digit-for-digit
on every one of the five fixtures.

### Re-execution 3 (T2 · AC-9, plus a browser re-execution beyond the cap for the walk artifact)

```
$ uv run --no-sync mkdocs build --strict -d <scratchpad>/audit-site
INFO    -  Documentation built in 17.91 seconds
exit=0
```
Record: exit 0, 0 real warnings (plan AC-9 tier-run, S7 report). **Match.**

`PACKAGES` widening and submodule `:::` blocks, read directly (not re-executed, within cap):
```
$ grep -n PACKAGES tests/unit/test_api_docs_coverage.py
PACKAGES = ("model", "io", "numerics", "pf", "opf", "contingency", "results", "jobs")
$ cat docs/api/opf.md docs/api/contingency.md
  ::: mambo_power.opf  (show_submodules: false)  + ## LP/QP builder over arrays / ::: mambo_power.opf.dc_opf
  ::: mambo_power.contingency (show_submodules: false) + ## LODF screen.../ ::: mambo_power.contingency.n1
```
Matches S7's report exactly.

**Browser check of the walk's MathJax finding** (not one of the 3 pytest re-executions — a
different-tool authenticity check on the walk artifact itself, which the mandate treats as
Step-5 evidence I must confirm was produced at its declared tier, i.e. genuinely in a real
browser against the real built site). I served the same built site
(`mkdocs build --strict -d <scratchpad>/audit-site`, the build above) over a local HTTP server
and drove it with `chrome-devtools` directly:
```
Navigate → http://localhost:8791/manual/numerics/  (an M1/M2-era page this wave never touched)
$ divCount=6 spanCount=17 → spanProcessed=5 spanRaw=12, divProcessed=3 divRaw=3
```
Reproduced identically on a full page reload with a 6-second wait (not a timing artifact):
`divProcessed=3 divRaw=3, spanProcessed=5 spanRaw=12`, byte-for-byte the same split. Both
`docs/manual/opf.md` and `docs/manual/numerics.md` emit structurally identical markup
(`<span class="arithmatex">`/`<div class="arithmatex">`, same `javascripts/mathjax.js` config,
same CDN `unpkg.com/mathjax@3` load) — confirmed by diffing the built HTML directly. **The
MathJax partial-render failure the walk found is real, reproducible, and site-wide — present
identically on a page this wave never touched.** This refines, not overturns, the walk's finding:
it is a genuine defect worth folding, but it is not something S7's docs work introduced, and the
walk artifact's own phrasing ("silently broken on both new manual pages") reads as page-specific
when the underlying cause is not.

### Per-row authenticity

| AC | Tier | Declared evidence found at that tier? | Note |
|---|---|---|---|
| AC-1 | T2 | Pandapower half: yes, re-executed. **PyPSA half: no** — the criterion's own literal text names it; the only evidence anywhere in the record is a Step 1/2 research diagnostic never cited as AC-1 tier-run evidence and never committed as a test. | not fully at tier |
| AC-2 | T1 | yes | re-executed |
| AC-3 | T1 | yes | re-executed |
| AC-4 | T1 | yes | re-executed |
| AC-5 | T2 | yes — fixture-fidelity declared, degeneracy handling read directly | read, not re-executed (cap) |
| AC-6 | T1 | yes | re-executed + revert-and-watch |
| AC-7 | T1 | yes — test names and hand-case shape read directly, commit diff matches report | read, not re-executed (cap) |
| AC-8 | T1 | yes — `InfeasibleLpError`/`UnboundedLpError` wiring and `run.py` except-chain read directly | read, not re-executed (cap) |
| AC-9 | T2 | yes — build/coverage/`PACKAGES` re-executed and read; walk artifact's MathJax claim re-verified in a real browser (found real but mischaracterized in scope) | re-executed + browser check |

---

## 4. The non-response procedure trail and S6's regression catch (specifically scrutinized)

**Non-response procedure (S3, S5)**: spot-checked, not taken on the reports' word.
`git show --stat 8d2c4e6` (S3) lists exactly the six files S3's report claims:
`src/mambo_power/opf/{__init__.py,dc_opf.py}` modified, `tests/unit/test_opf_{dc_case14_pwl,
dc_pwl,pwl_guard}.py` new, `test_opf_solve_dc_opf.py` extended. `git show --stat 9d317ee` (S5)
lists exactly its six: `opf/{__init__.py,dc_opf.py}`, `results/{__init__.py,feasibility.py}`
modified, `test_feasibility.py` new, `test_opf_solve_dc_opf.py` extended. Both commits' authored
timestamps (S4 16:38, S5 17:17, S3 17:34) are internally consistent with the reports' own
narrative that S3 built on top of S5's already-landed commit. `tests/unit/test_opf_pwl_guard.py`
and `tests/unit/test_feasibility.py`'s actual test names, read directly, match each report's
described test shape exactly (raise/accept/unaffected for the convexity guard; thermal/voltage/
clean/converged-pass-through for `FeasibilityReport`). **The landed code matches what both
reports claim**, not merely that the reports exist.

**S6's regression catch**: confirmed real and complete, not moved elsewhere.
`grep -rn "market.nodal"` shows `examples/04_jobs_api.py:51`, `docs/manual/jobs.md:202`, and
`tests/unit/test_jobs.py:273` all now use `kind="market.nodal"` for the "unknown kind" demo.
`grep -n "register(" src/mambo_power/jobs/registry.py` confirms exactly four kinds registered
(`pf.ac`, `pf.dc`, `opf.dc`, `n1`) and **`market.nodal` is genuinely absent** — the fix did not
just relocate the staleness to a kind that turns out to be registered too.

---

## 5. Verdict table

| Row | Verdict | Reason (one line) |
|---|---|---|
| AC-1 | **REFUTED (as proven)** | Pandapower-primary-oracle half strongly CONFIRMED (re-executed 20/20, ≤1.6e-11 relative). PyPSA-secondary-oracle half of the literal criterion has zero committed evidence — only a separate, uncited research diagnostic exists (informal, not a proof gate for this wave's own Step 4/5). Genuinely and honestly logged as a carry-over at every layer (not a reporting-contract violation, unlike M2's analogous AC-5 gap) — a proof gap, not a behaviour defect, and cheap to fold (promote the diagnostic to a committed spot-check, or soften the spec text). |
| AC-2 | CONFIRMED | Hand-built triangle duals; three positive/negative pairs in one test; re-executed. |
| AC-3 | CONFIRMED | Two cost arrays give two dispatches; standalone `lmp_decomposition`; re-executed. |
| AC-4 | CONFIRMED | Base case never violates + real DC-re-solve-confirmed violation exists (18/86 on case14, re-executed exactly); minor provenance-citation nit (cites W3 only, not W5) noted, substance whole. |
| AC-5 | CONFIRMED | Independent lambda-iteration oracle match on 3/5 generators + total cost exact; degenerate residual honestly asserted as an interval, not a false-precise split; convexity guard raises pre-solve. |
| AC-6 | CONFIRMED | Brute-force agreement exact on all 5 fixtures, re-executed with matching counts; revert-and-watch VALIDATED (§2b) — the strongest-power row in the wave. |
| AC-7 | CONFIRMED | Thermal/voltage/clean/converged-pass-through hand cases; test names and commit diff verified directly. |
| AC-8 | CONFIRMED | `INFEASIBLE_LP`/`UNBOUNDED_LP` wiring read directly in `registry.py`/`run.py`; RED→GREEN via `git stash` documented; `pf.ac` non-convergence-stays-"ok" is the deliberate paired negative case. |
| AC-9 | CONFIRMED | `--strict` exit 0 re-executed; coverage test's own power demonstrated by S7 and independently confirmed (`PACKAGES` widened, submodule blocks present); walk's MathJax finding re-verified in a real browser and found real but **pre-existing/site-wide, not introduced by this wave** (§3) — a correction to the walk's scope claim, not a refutation of AC-9 itself. |
| **Wave — coverage** | **CONFIRMED** | No requirement has zero inbound citations (unlike M2's W7); one letter-only citation gap on AC-4/W5, substance present. |
| **Wave — overall** | **REFUTED** (as "implemented and proven") | One row (AC-1) refuted purely on an undischarged secondary-oracle proof, honestly disclosed throughout the record, not a behaviour defect and not a reporting-contract violation. Every other row CONFIRMED, several with unusually strong power (AC-6's revert-and-watch). W9's documentation is substantively strong on the new content itself (walk's own assessment) with one real, wave-attributable gap (stale home-page status/roadmap, correctly identified by the walk as non-AC-9-gating) and one real-but-not-new gap (site-wide MathJax) that this audit newly attributes correctly. Fixable in the fold without touching solver code, mirroring M2's own "REFUTED, substance intact" shape. |

---

## 6. Reporting-contract check on the record itself

No factual claim found in the plan or the seven slice reports that lacks either a proving
command/output or an explicit `unverified`/carry-over label, with one qualification: the
Verification Matrix's top summary table marks **AC-1 status as a bare "discharged"** with no
inline qualifier, while the AC-1 readback two lines below it is fully honest about the PyPSA gap.
This is not a false claim (the readback is right there and is accurate), but a reader who reads
only the summary table would come away with a stronger impression of completeness than the
record actually supports — worth tightening in the fold (e.g. "discharged (pandapower); PyPSA
carry-over" in the status cell) rather than relying on a reader to open the detail block.

The walk artifact (`m3-walk-docs-site.md`) itself is accurate in every specific claim I checked
(the MathJax break is real, the stale home page is real, the two anchor-clipping/mermaid-lazy
observations are correctly labelled as likely-cosmetic) — its one imprecision is scope framing
("both new manual pages," which reads as page-specific), addressed in §3/§5 above, not a
reporting-contract violation by the walker (who explicitly was not shown the ACs and had no way
to know the same rendering pattern predates this wave without checking a page outside their walk
route).

## 7. Cleanup confirmation

`git status --porcelain` in `C:\Claude Projects\mambo-power-m3` — empty, both before this audit
began and after every step, including after the revert-and-watch demonstration returned.
Throwaway worktree `C:\Claude Projects\mambo-power-audit3` created and removed by the dispatched
test-runner agent, confirmed gone via `git worktree list` (run by me). Local static file server
used for the MathJax browser re-execution served only the already-built, throwaway
`<scratchpad>/audit-site` directory — no worktree files were served or modified.
