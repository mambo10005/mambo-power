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
