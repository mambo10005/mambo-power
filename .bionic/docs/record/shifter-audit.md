# Audit — the DC-OPF phase-shifter flow defect fix (task-shifter-flow-fix)

Rigor: audited. Auditor scope: falsify the claim that `6a7617f` (`task/shifter-flow-fix`,
worktree `C:\Claude Projects\mambo-power-shifter`) faithfully fixes M7 finding F1 / M8 finding
A19 and proves it.

**Isolation.** Two independent copies via `git archive 6a7617f | tar -x`, never the shared
worktree: `scratchpad/shifter-audit-6a7617f` (read-only checks, `uv run` confirmed
`mambo_power.__file__` under that path) and `scratchpad/shifter-sabotage-6a7617f` (all mutation).
Every fixture, script and sabotage below is the auditor's own — none of it is
`tests/_shifter.py`.

## Identity, derived by hand from the code (not the plan)

Read `pf/dc.py`, `numerics/ptdf.py`, `numerics/bbus.py` directly.

- `pf.dc.solve`: reduced system `B'[keep,keep]·θ[keep] = (P − p_shift)[keep]`, then
  `p_from = Bf·θ + pf_shift`.
- `numerics.ptdf.ptdf`: solves `B'ᵀ·X = Bfᵀ` on the reduced system → `X = (Bf·B'⁻¹)ᵀ`, i.e.
  `PTDF = Bf·B'⁻¹` (reduced).
- Substituting: `θ[keep] = B'[keep,keep]⁻¹(P−p_shift)[keep]`, so
  `p_from = Bf·B'⁻¹(P−p_shift) + pf_shift = PTDF@(P−p_shift) + pf_shift`.

This is exactly `numerics.bbus.flow_from_ptdf`'s formula and exactly what `opf/dc_opf.py`'s
`const_k` derivation reduces to when its `Σ_g PTDF·p_g − Σ_d PTDF·p_d` decision-variable term is
added back (`const_k = pf_shift_mw − PTDF@(fixed_bus_mw + p_shift_mw)`, and
`flow = row_expr + const_k`). Confirmed independently, not taken on faith.

## AC-1 — `dc_opf`'s own flow-limit row constant

Own fixture (`_audit_fixture.py`): 3-bus loop `b1(slack)–l12–b2–s23(shifter)–b3–l13–b1`, gens at
`b1`/`b2`, load at `b3` — topology, ids, costs and load all distinct from `tests/_shifter.py`.
Shift angles `-6°`/`15°` (asymmetric, own choice).

- **Positive proof**: at `-6°` the cheap-only dispatch sits at the achievable-flow *floor* — a
  rating below it correctly reports `Infeasible`. At `15°` cheap-only sits at the *ceiling* — a
  midpoint rating forces a real redispatch (`g1:60→30, g2:0→30`), and the TRUE physical flow (an
  independent `pf.solve_dc` readback of the resulting dispatch) respects the rating
  (`42.2284 ≤ 42.2284+1e-5`). Both scenarios PASS.
- **Sabotage** (site only): reverted `const = pf_shift_mw − ptdf_matrix @ fixed_bus_mw` (dropped
  `+ p_shift_mw`) in `dc_opf.py`, nothing else touched. Implementor's own suite:
  `test_dc_opf_flow_limit_row_forces_a_true_physical_redispatch` reddens; the other 11 tests
  (including the OTHER T1 test, `..._reports_infeasible_below_the_achievable_floor`) stay green.
  My own AC-1 `15°` check reddens identically (`Infeasible` where `Optimal` was expected).
  Restored; `diff` against the pre-sabotage backup is empty; implementor's suite back to 12/12.

**Verdict: PASS.** One note (see Should-fix) — the floor-side test doesn't independently confirm
*why* it reports Infeasible.

## AC-2 — `solve_dc_opf`'s derived flows

Same own fixture, both shift angles. `solve_dc_opf(net).branches[].p_from_mw` vs an independent
`pf.solve_dc` readback of the solved dispatch: all 3 branches × 2 angles match to `<1e-7` MW
(values e.g. `55.634216` both sides at `-6°`); KCL at the load bus (`b3`) holds to `1e-6` MW both
angles.

**Sabotage** (site only): reverted `flows_mw = flow_from_ptdf(...)` to the old
`ptdf_matrix @ injection_mw + pf_shift(arr)*base_mva` in `opf/__init__.py` only. Implementor's
suite: exactly `test_solve_dc_opf_branch_flows_match_pf_solve_dc` (both angles) and
`test_kcl_holds_at_the_shifted_bus[dc_opf-...]` (both angles) redden — 4 of 12; the two `nodal`
KCL variants and `test_solve_nodal_branch_flows_match_pf_solve_dc` (T3, untouched) stay green.
My own 8 AC-2 checks all reddened with the expected wrong numbers (e.g. `got=112.98` vs
`want=55.63`); AC-1, T3 and regression checks (16 more) stayed green. Restored; diff empty;
suite back to 12/12.

**Verdict: PASS.**

## T3 corroboration — `market._clearing` / `solve_nodal` (not a named AC, verified anyway)

Same fixture: `solve_nodal(Scenario(network=net)).branches[].p_from_mw` vs the `pf.solve_dc`
oracle, both angles, all branches — match to `<1e-7` MW.

## AC-3 — PyPSA `lpf()` as a second, external oracle

Own fixture exported via `io.pypsa.to_network`, dispatched at the FIXED `solve_dc_opf`'s own
solved point, `n.lpf()` run directly (not `optimize()`, which PyPSA 1.2.4 ignores `phase_shift`
in — correctly documented, see AC-4). Both angles:

- PyPSA vs `pf.solve_dc`: bus angles and branch flows agree to `<1e-7` (this proves PyPSA
  itself — an independently-implemented DC engine — gets the shifted case right, not just that
  mambo agrees with itself).
- PyPSA vs the fixed `solve_dc_opf` output (the actual site under audit): agrees to `<1e-7`.

18/18 checks pass.

**Verdict: PASS.**

## AC-4 — manual docs: no stale caveat, no overclaim

- `git show 6a7617f -- docs/manual/formats.md`: confirmed the *exact* "wrong or infeasible …
  until the phase-shifter fix lands (F1 / A19)" bullet removed from all four, and only four,
  importer Limitations sections (pandapower JSON L373-377, PyPSA L458-462, PSS/E RAW L600-604,
  CSV bundle L708-710) — grepped the repo for `"wrong or infeasible"` and `F1\|A19`
  post-fix: zero hits outside an unrelated Mermaid node label in `power-flow.md`.
- `opf.md`'s own row-formula prose ("`const_k` folds in the branch's fixed (load/shunt/
  phase-shift) contribution") now matches the fixed code exactly — before the fix this text was
  aspirational, not descriptive; now it is accurate.
- MATPOWER's own Limitations section never carried the caveat (git diff confirms it wasn't
  touched) — consistent with the commit's own "four" count.
- The other phase-shift mentions found repo-wide (`market.md` L143, `multiperiod.md`
  L274/282/348/350, `results.md` L133, `zonal.md` L250-261/493) are all a *different*,
  legitimate, out-of-scope topic: the settlement/LMP-decomposition identity's phase-shift
  *correction term* and the zonal balance row's deliberate omission of phase-shift injections.
  Both are structural facts of the market math (`lmp_decomposition` consumes duals, not the
  derived flow — explicitly "Not doing" in the plan) and are unaffected by this fix; none reads
  as a residual bug caveat.
- `docs/changelog.md`: new `### Fixed` entry at the top of `[Unreleased]`, correctly describing
  all three sites and the identity; M8's own historical "Known limitation" bullet is left intact
  with a one-line `**Fixed** — see "Fixed", above.` pointer rather than being rewritten (accurate
  as a historical record).
- Re-ran independently: `uv run --group docs mkdocs build --strict` → exit 0.
  `tests/unit/test_io_limitations.py` + `test_docs_registry_listing.py` → **92 passed** (matches
  the commit message's own count).

**Verdict: PASS.**

## Revert-and-watch — the shared helper `flow_from_ptdf` alone

Reverted only `numerics/bbus.py`'s `flow_from_ptdf` body (dropped the `− p_shift` term inside the
helper), leaving both call sites (`opf/__init__.py`, `market/_clearing.py`) untouched.

- Implementor's suite: **8 of 12 redden** — `test_solve_dc_opf_branch_flows_match_pf_solve_dc`
  (T2, both angles), `test_solve_nodal_branch_flows_match_pf_solve_dc` (T3, both angles),
  `test_kcl_holds_at_the_shifted_bus[dc_opf-...]` and `[nodal-...]` (both angles) — i.e. every
  test that runs through either caller. The two `dc_opf`-row tests (T1, which derives its own
  formula by hand rather than calling the helper) and the two PyPSA parity tests (which never
  touch `flow_from_ptdf`) stay green.
- My own script: 14 of 24 checks redden — every AC-2 (T2) and T3 check, with identical wrong
  numbers on both; AC-1 (T1) and the regression check all stay green.

Restored; diff against backup empty; both the implementor's suite (12/12) and my own script
(24/24) pass again post-restore.

**Verdict: exactly the claimed pattern — PASS.**

## Regression spot-check

`numerics.bbus.p_shift(NetworkArrays.from_network(io.matpower.load("fixtures/matpower/
case14.m")))` is the exact zero vector (`max abs = 0.0`); confirmed independently that no branch
in `case14.m` carries `shift_deg != 0`. The fix is a provable no-op on the bundled fixture
checked; consistent with the plan's "every pre-existing fixture has `shift_deg == 0`" claim
(not exhaustively re-checked across every bundled fixture — this was a spot-check as instructed,
on the fixture the plan itself names).

## Test hygiene, four→three new/changed test files

The dispatch named "four new/changed test files"; the actual diff (`b01062f~1..6a7617f`) touches
**three**: `tests/_shifter.py` (fixture, not collected — underscore-prefixed), `tests/unit/
test_shifter_flow_fix.py`, `tests/parity/test_shifter_pf_vs_pypsa.py`. Not a fix defect — an
inaccuracy in the audit dispatch's count, noted for the record, not blocking.

Reviewed all three:
- No `skip`/`xfail` anywhere except a legitimate `pytest.importorskip("pypsa")` guard (pypsa is
  installed here, so it never actually skips).
- Independent-oracle discipline throughout: every assertion compares against a *separately*
  computed `pf.solve_dc` (or PyPSA `lpf()`) readback, never a hand-restated constant.
- Deliberately asymmetric shift angles (`-7°`/`+12°`) so a sign error can't cancel at a symmetric
  pair — good practice, and I independently adopted the same discipline (`-6°`/`15°`) rather than
  reusing theirs.
- Tight, appropriate tolerances (`abs=1e-9` for direct comparisons).
- `tests/_shifter.py`'s docstring and helpers are accurate to what I independently re-derived.

## Findings

No blocking findings. One should-fix (test-strength, not correctness):

- **Should-fix**: `test_dc_opf_flow_limit_row_reports_infeasible_below_the_achievable_floor`
  (and its equivalent in my own AC-1 floor-side check) verifies only `status == "Infeasible"`,
  not that the row's own `const_k` is why. Confirmed by sabotage: reverting the T1 site's
  `p_shift` term did **not** redden this test — it happened to still report `Infeasible` for the
  wrong numeric reason. The sibling test
  (`..._forces_a_true_physical_redispatch`) does catch the T1-site bug, so AC-1 is discharged
  overall, but this one test alone would not catch a T1 regression. Low severity: it doesn't
  block this task, but a future editor relying on it alone for T1 coverage would have a gap.

## Overall

| Criterion | Result |
|---|---|
| Identity derivation (own, from code) | confirmed |
| AC-1 (`dc_opf` row) | PASS |
| AC-2 (`solve_dc_opf` derived flows) | PASS |
| T3 corroboration (`market`/`solve_nodal`) | PASS |
| AC-3 (PyPSA second oracle) | PASS |
| AC-4 (docs) | PASS |
| Revert-and-watch (shared helper) | PASS — exact claimed pattern |
| Regression spot-check | PASS |
| Test hygiene | PASS (1 should-fix, non-blocking) |

**Counts: 8/8 criteria PASS, 0 blocking, 1 should-fix.**

**Task verdict: PASS.** The fix is faithfully implemented at all three sites and is proven by
independent, own-built evidence: hand-derivation from the actual solver code (not the plan),
two independently-built fixtures (own AC-1/2/3 fixture, distinct from the implementor's),
a second external oracle (PyPSA `lpf()`) that itself was checked against `pf.solve_dc` first,
three isolated single-site sabotages plus one shared-helper revert-and-watch — every one
reddening exactly the tests the claim predicts and nothing else, with full restoration verified
by empty diffs and passing suites — and a full read of every phase-shifter doc mention across
the manual confirming no stale caveat and no scope overclaim.

## Re-audit at bd952cc

Rigor: audited. Scope: falsify the claim that T6–T8 (`8a6fb11`, `eb771b1`, `272d84c`, `9e0cbb4`,
`bd952cc`) close the critic's two blocking findings — `opf/multiperiod.py`'s and
`opf/redispatch.py`'s own independent copies of the identical missing-`p_shift` bug — without
reopening anything the first audit (above) already passed.

**Isolation.** Three independent copies via `git archive | tar -x`, never the shared worktree,
`mambo_power.__file__` confirmed under each own path before any check: `scratchpad/
shifter-reaudit-bd952cc` (read-only), `scratchpad/shifter-resab-bd952cc` (all sabotage), and
`scratchpad/shifter-pre-t6t7-9e00ab5` (the critic's own head, pre-T6/T7, used only to *prove the
bug was live* — never to judge the fix). Own fixture throughout (`_reaudit_fixture.py`, copied
verbatim into all three): a 5-bus network `n1(slack)`–`n2`–`n3`–`n4`–`n5`–`n1` (a ring) plus a
chord `n2`–`n5` carrying the phase shifter — a genuine two-loop mesh, topologically distinct from
every prior fixture in this task (the implementor's 3-bus loop, the first audit's own 3-bus loop,
the walk's 4-bus ring / 5-bus chain) — at its own asymmetric angles (`-11°`, later `+11°` for the
ceiling-type check below), never `tests/_shifter.py`.

### Item 1 — T6/T7 discharged on own inputs

**T6** (`multiperiod_dc_opf`'s per-period row constant): a 3-period horizon (loads 40/70/100 MW)
at a rating (190 MVA on the shifter chord) strictly between the true achievable flow (~135–139
MW) and what the pre-fix formula would have estimated at that same dispatch (~242–246 MW,
measured directly — see Item 2). Solves `Optimal` at every period; each period's dispatch,
reconstructed into a flow via the already-audited `flow_from_ptdf` and independently via
`pf.solve_dc` on a copy of the network carrying that period's dispatch, agree to `<1e-6` MW, and
the true flow respects the rating at every period. A second, ceiling-type own fixture (shift
`+11°`, where cheap-only dispatch sits at the flow *ceiling* rather than the floor) forces a real
redispatch (`g1: 100→50, g3: 0→50`) and the resulting *true* physical flow (`pf.solve_dc`
readback) lands exactly at the rating (`123.1820 ≤ 123.1820+1e-6`) — the row's own constant, not
just the post-hoc reconstruction, is what is being exercised here.

**T7** (`redispatch_dc_opf`'s constant and its `branch_flow_mw` output): own `p0_mw = [100, 0]`
starting point (cheap-only), same two fixtures. Floor-type (`-11°`, rating 190): solves `Optimal`,
`branch_flow_mw[e25]` matches the `pf.solve_dc` oracle to `<1e-6` MW. Ceiling-type (`+11°`, rating
123.182): genuinely redispatches away from `p0` (`g1: 100→50, g3: 0→50`), `branch_flow_mw`
matches the oracle at the redispatched point exactly, and the true flow lands at the rating.

**Sabotage, each site alone**, on the implementor's own suite (`tests/unit/
test_shifter_flow_fix_multiperiod_redispatch.py` + `test_shifter_flow_fix.py`, 24 tests): T6
alone (dropped `+ p_shift_mw` from `multiperiod.py`'s `const.append(...)`) reddened exactly 2 —
`test_multiperiod_dc_opf_flow_limit_row_forces_true_physical_redispatch_every_period` and
`test_solve_multiperiod_no_longer_reproduces_the_critics_false_infeasible` — with T7's and T1–T5's
tests, including `test_multiperiod_dc_opf_derived_flows_match_pf_solve_dc_at_every_period`,
staying green (see Should-fix below on why that last one doesn't redden). T7 alone (dropped
`+ p_shift_mw` from `redispatch.py`'s `const`, and reverted `branch_flow_mw = flow_from_ptdf(...)`
to the old `ptdf_matrix @ injection_mw + pf_shift_mw`) reddened exactly 8 — every
`test_redispatch_dc_opf_branch_flow_matches_pf_solve_dc` parametrization (4), the forced-
redispatch test, both `test_solve_zonal_branch_flows_match_pf_solve_dc` parametrizations (2, since
`solve_zonal` calls `redispatch_dc_opf`), and the critic's own 81.4 MW named reproduction — with
every T6-only and T1–T5 test staying green. Both restored; `diff` against backup empty both times;
full 24/24 passes again after each restore.

### Item 2 — `market.solve_zonal` / `market.solve_multiperiod` end-to-end, own scenario

Reproduced **both** of the critic's failure modes on the auditor's own fixture, then confirmed
both are gone at `bd952cc` after first confirming both are *live* at the pre-T6/T7 head
(`9e00ab5`, same fixture, same script, `git archive`d separately) — proving the reproduction is
real and not an artefact of the auditor's own script:

- **Silent wrong-number pattern** (the critic's 81.4 MW gap): generous ratings so `solve_zonal`
  reports `Optimal` at both heads. At `bd952cc`, `branches[].p_from_mw` matches an independent
  `pf.solve_dc` readback of the *final* (`generators_final`) dispatch to machine precision on
  every one of the 6 branches (`gap = 0.0000` MW everywhere). At `9e00ab5`, the same scenario
  reports `Optimal` with the *same* dispatch but branch-flow gaps up to **107.2263 MW** on the
  shifter chord (61–71 MW on the other five branches) — the same order of magnitude and the same
  "Optimal but wrong" character as the critic's own 81.4 MW finding, reproduced independently.
- **False-`Infeasible` pattern**: a rating (190 MVA) strictly above the true achievable flow
  (~139 MW) but below what the pre-fix formula would estimate (~246 MW). `market.solve_multiperiod`
  and the array-level `multiperiod_dc_opf` both report `Optimal` at `bd952cc` and **`Infeasible`**
  at `9e00ab5` on the identical scenario — `market.solve_zonal`'s redispatch stage does too, at the
  same rating.

One correction made mid-audit, recorded rather than silently fixed: the first pass of this check
read `MarketZonalResult.generators` (the *zonal-stage* dispatch) instead of `.generators_final`
(the dispatch `branches[].p_from_mw` is actually sourced from) — it happened to pass because that
particular corridor/rating combination left the two stages coincidentally equal, which would have
made the check vacuous. Re-run with a corridor/rating combination that provably forces
`generators` ≠ `generators_final` (`g1: 100→50, g3: 0→50`, confirmed unequal) closes that gap; the
match against `pf.solve_dc` at the true final dispatch still holds to `<1e-6` MW (see Item 1's T7
ceiling case, same numbers).

### Item 3 — exhaustive site search, own differently-shaped greps

Four independent search shapes, none reusing the critic's/orchestrator's literal
`"ptdf_matrix @|ptdf @"` pattern: every call site of the `ptdf()` builder (`grep -rn
"compute_ptdf(|import ptdf"`), every module using `pf_shift` (9 hits), every module using
`p_shift` (6 hits), and a broadened matrix-vector-product regex (`@ \(?(injection|fixed_bus|
p_load|...)`) that would catch a differently-named local variable a literal `ptdf_matrix @` search
misses. Two candidates surfaced that the critic's narrower grep would not have caught as literal
matches (neither line contains a bare `ptdf_matrix @` or `ptdf @` token):

- `market/agents.py:551` (`ptdf_matrix = compute_ptdf(arr)`) — read in full: the matrix is built
  once and handed into `opf.dc_opf.dc_opf(..., ptdf=ptdf_matrix)` (a caching optimisation,
  critic's own M7 finding 3), and the module's own branch rows come from `market/_clearing.py`'s
  `clearing_rows` — T3's already-fixed site. Not an independent computation, not a fourth site.
- `contingency/n1.py` (imports `bridges, lodf, ptdf`) — `base_flow_signed_mw` comes from
  `pfdc.solve(arr)` (the correct oracle itself, not a PTDF product), and `lodf()` (read in full,
  `numerics/lodf.py`) is a pure ratio `h_k[l] / (1 − h_k[k])` built from PTDF *differences* with no
  additive `pf_shift`/`p_shift` term anywhere in its formula — structurally immune to this
  specific bug class, not merely untested for it.

`opf/zonal.py` re-confirmed (own read, not taken from the plan/critic): its own module docstring
states `_flow_limit_rows` is never called and no PTDF matrix is ever built there (ADR-009,
copper-plate per zone) — grepped for `ptdf|pf_shift|p_shift|flow` and found only prose, no code.
No fourth site found by any of the four shapes.

### Item 4 — revert-and-watch, T6 and T7 individually

Folded into Item 1's sabotage runs above (same commands, reported once): T6 alone reddens exactly
2 tests, T7 alone reddens exactly 8, with zero overlap between the two sets and zero effect on
T1–T5's own file (`test_shifter_flow_fix.py`, all 12 stay green both times) — the claimed
independence, confirmed both directions.

### Item 5 — docs

- `docs/changelog.md`'s `### Fixed` entry (own read at `bd952cc`) names all five sites by name —
  `opf.dc_opf`'s row constant, `opf.solve_dc_opf`'s derived flow, `market._clearing`/
  `solve_nodal`/`solve_agents`'s derived flow, `opf.multiperiod_dc_opf`'s per-period row constant,
  and `opf.redispatch_dc_opf`'s row constant *and* its `branch_flow_mw` — and states which three
  now call `flow_from_ptdf` directly versus which three fold the term by hand into a decision-
  variable-relative constant, matching the actual diff.
- `grep -rn "wrong or infeasible|F1 / A19|F1\/A19" docs/`: one hit, the pre-existing M8 "Known
  limitation" changelog bullet the first audit already confirmed is a deliberate, accurate
  historical record (with a "Fixed — see above" pointer) — no live/stale caveat anywhere.
- `docs/manual/numerics.md`'s clarification from `9e00ab5` (the walk's fix: `numerics.bbus` is
  itself the `bbus(arr)` function, shadowing the submodule, so `numerics.bbus.pf_shift` raises
  `AttributeError`) re-verified by hand at `bd952cc`: `numerics.__init__.py` still re-exports
  `bbus` as the function (`from mambo_power.numerics.bbus import bbus, ...`), and running it
  confirms `numerics.bbus.pf_shift` still raises exactly that `AttributeError`. Still accurate.

### Item 6 — test hygiene, T6–T8's new/changed files

`tests/unit/test_shifter_flow_fix_multiperiod_redispatch.py` (new, 315 lines) and `tests/
_shifter.py` (extended): no `skip`/`xfail` anywhere; independent-oracle discipline held throughout
(every assertion via a fresh `pf.solve_dc` readback through the file's own `_oracle_flow` helper,
never a hand-restated constant); tight tolerances (`abs=1e-6`); the two named critic-reproduction
tests (`..._no_longer_reproduces_the_critics_81_4_mw_gap`, `..._no_longer_reproduces_the_critics_
false_infeasible`) make the regression against the critic's own numbers explicit rather than
merely subsumed. `ruff check`, `ruff format --check` and `mypy` on the two changed source files
and the new/changed test files: all clean, independently re-run. `git status --porcelain` at
`bd952cc`: clean (confirms the orchestrator's F1 cleanup commit).

One should-fix, same lineage as the first audit's AC-1 finding:
`test_multiperiod_dc_opf_derived_flows_match_pf_solve_dc_at_every_period` reconstructs its
expected flow via `flow_from_ptdf` (the already-audited, correct helper) applied to the *solved
dispatch*, on an unrated network where "neither rating binds" (the test's own docstring) — so it
never actually reads anything the LP's own (possibly wrong) row constant produced; it only proves
that a correct flow-reconstruction helper, fed a correctly-computed cheap-only dispatch, agrees
with itself. Confirmed by sabotage: T6-alone did **not** redden this test. T6 is still discharged
overall — its sibling `..._forces_true_physical_redispatch_every_period` and `market.
solve_multiperiod`'s false-Infeasible test both do exercise the row constant and both reddened —
but this specific test's name could mislead a future reader into believing it independently proves
the row math. Low severity, non-blocking, carried forward exactly as the first audit's AC-1
should-fix was.

### Overall at bd952cc

| Item | Result |
|---|---|
| 1. T6/T7 discharged on own inputs (floor- and ceiling-type) | PASS |
| 1. Sabotage independence (T6 alone: 2 red; T7 alone: 8 red; no overlap) | PASS — exact claimed pattern |
| 2. `solve_zonal` silent-gap reproduction (0.0000 MW at `bd952cc` vs up to 107.2 MW at `9e00ab5`) | PASS |
| 2. `solve_multiperiod`/`multiperiod_dc_opf` false-Infeasible reproduction (Optimal at `bd952cc` vs Infeasible at `9e00ab5`, same scenario) | PASS |
| 3. Exhaustive site search, 4 independently-shaped greps + full read of 2 non-obvious candidates | PASS — no fourth site |
| 4. Revert-and-watch, T6 and T7 individually | PASS |
| 5. Docs (changelog names all 5 sites, no stale caveat, `numerics.md` still accurate) | PASS |
| 6. Test hygiene (T6–T8 files) | PASS (1 should-fix, non-blocking) |

**Counts: 8/8 items PASS, 0 blocking, 1 should-fix (carried forward from the first audit's own
AC-1 finding, same pattern, new site).**

**Task verdict at `bd952cc`: PASS.** Both of the critic's blocking findings are closed and proven
closed by independent, own-built evidence — a topologically distinct own fixture throughout, both
of the critic's own failure modes (the 81.4-MW-scale silent wrong number and the false
`Infeasible`) reproduced first on the pre-fix head to confirm they were live, then shown gone at
`bd952cc`; T6 and T7 sabotaged individually with zero cross-contamination into each other or into
T1–T5's own suite; four differently-shaped exhaustive searches (not a re-run of the critic's own
grep) finding no fourth site, with the two non-obvious candidates each read in full and cleared by
reasoning about their actual code, not by pattern-match absence alone; docs re-confirmed accurate
at the new head. One non-blocking should-fix, in the same family as the first audit's own AC-1
finding, carried forward for a future editor.
