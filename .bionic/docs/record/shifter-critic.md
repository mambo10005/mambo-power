# Critic — task-shifter-flow-fix, at `9e00ab5`

Step-6 adversarial review, `task/shifter-flow-fix` HEAD `9e00ab5`, diff range `1a2b31c..9e00ab5`.
Run against an isolated `git archive` copy (`scratchpad/shifter-critic-9e00ab5/`), `mambo_power.__file__`
verified to resolve there. Read the task plan's Scope/Design/Walk/Audit sections; did not read
`record/shifter-fix-report.md`.

## Findings

### 1. BLOCKING — `opf.multiperiod`/`opf.redispatch` carry their own unfixed copy of the identical bug; live via `market.solve_multiperiod` and `market.solve_zonal`

The plan's Scope section names exactly three sites with "the same flow, missing `- p_shift`." A
fourth grep (`pf_shift`/`ptdf_matrix @` outside the three named files — the plan's own Design
section flagged this as worth checking, "do they have their OWN copy... that this fix did NOT
touch") turns up **two more, neither touched by any of the six commits**:

- `src/mambo_power/opf/multiperiod.py:485` — the flow-limit row constant:
  `const.append(pf_shift_mw - ptdf_matrix @ (p_load_mw + g_shunt_mw))` — no `p_shift_mw` term.
  `p_shift` is never imported in this module (only `pf_shift`, line 110).
- `src/mambo_power/opf/redispatch.py:423-424` — the identical construction:
  `const = pf_shift_mw - ptdf_matrix @ (p_load_mw + g_shunt_mw)` — same omission, same
  import gap (`pf_shift` only, line 101).
- `src/mambo_power/opf/redispatch.py:550` — the module's own **derived, reported** branch flow:
  `branch_flow_mw = ptdf_matrix @ injection_mw + pf_shift_mw` — doesn't even attempt the
  correction, and doesn't call `flow_from_ptdf` at all.

`redispatch.py`'s `branch_flow_mw` reaches a public result field directly:
`market/zonal.py:689` — `p_from_mw=float(final.branch_flow_mw[k])` — so `market.solve_zonal`'s
reported branch flows are wrong on any network with a shifter, exactly like the diagnosed defect,
completely unaffected by this fix. `market.solve_multiperiod` has no branch-flow field
(`MultiperiodSolution` carries no `branch_flow_mw`/`p_from_mw`), so the LP's wrong constant shows
up as wrong dispatch/duals/false-Infeasible rather than a wrong reported number, but it is the
same defect mechanism the walk documented for the three named sites.

**Reproduction** (`tests/_shifter.shifter_loop_network`, `shift_deg=-7`, run in the isolated
archive against `pf.solve_dc` as oracle):

```
=== redispatch_dc_opf branch_flow_mw vs pf.solve_dc ground truth, shift_deg=-7 (t12 unrated) ===
redispatch status: Optimal
redispatch dispatch_mw: [100.   0.]
redispatch branch_flow_mw: [188.83971431 -33.33333333  33.33333333]
pf.solve_dc p_from (MW) at redispatch's own dispatch: [107.39101588   7.39101588  -7.39101588]
max abs diff redispatch.branch_flow_mw vs pf.solve_dc: 81.44869842640203

=== flow_from_ptdf (the fixed helper), same dispatch, for comparison ===
flow_from_ptdf (correct): [107.39101588   7.39101588  -7.39101588]
max abs diff flow_from_ptdf vs pf.solve_dc: 1.7763568394002505e-15
```

`redispatch_dc_opf` is off by 81.4 MW on `t12` (and wrong-signed on `l23`/`l13`) at the exact
dispatch where `flow_from_ptdf` — the identical identity, correctly applied — matches the oracle
to machine precision. The 81.4 MW is exactly `ptdf_matrix @ (p_shift(arr) * arr.base_mva)` on
this fixture — the omitted term, confirmed by direct computation.

**False Infeasible, the same failure mode the task diagnosed, now shown in `multiperiod_dc_opf`**
(rating chosen so the *true* physical flow, swept over dispatch, never exceeds it, but the buggy
constant's implied flow always does):

```
dc_opf (FIXED, t12 rated 120 MVA)     : status = Optimal    dispatch = [100.   0.]
multiperiod_dc_opf (UNFIXED, same net): status = Infeasible  dispatch = [0. 0.]
```

True `t12` flow at `dc_opf`'s dispatch is 107.39 MW, comfortably inside the 120 MVA rating —
`dc_opf`'s `Optimal` is physically correct. `multiperiod_dc_opf`'s own row believes every
achievable dispatch puts `t12` at 155–189 MW (the 81.4 MW offset added on top of the true
74–107 MW range), so it reports a false `Infeasible` on a network with no real congestion —
the exact defect class F1/A19 diagnosed, on a sibling code path this task never touched.

Scripts: `scratchpad/shifter-critic-9e00ab5/repro_missed_sites.py`,
`.../diverge.py`, `.../offset.py`, `.../sweep.py`.

**Proposed fix:** `redispatch.py:550` should call `flow_from_ptdf(ptdf_matrix, injection_mw, arr)`
exactly as `opf/__init__.py` and `market/_clearing.py` now do; `multiperiod.py:485` and
`redispatch.py:423-424`'s `const` should each subtract `ptdf_matrix @ (p_shift(arr) *
arr.base_mva)`, mirroring `dc_opf.py`'s own by-hand derivation (both build an LP-row constant,
not a full-injection-vector product, so neither can call `flow_from_ptdf` directly, same as T1).
Add regression tests for `multiperiod_dc_opf`, `redispatch_dc_opf`, `market.solve_multiperiod`
and `market.solve_zonal` on `tests/_shifter.shifter_loop_network`, mirroring
`test_shifter_flow_fix.py`'s existing coverage of the three sites this task did fix — their
absence is exactly why this gap wasn't caught by the task's own regression suite, the walk, or
the audit.

### 2. BLOCKING — T5's `formats.md` caveat removal is now a false claim of safety

`docs/manual/formats.md` (four sections: pandapower JSON, PyPSA, MATPOWER, native/CSV) each
carried a caveat reading, generically: *"A network with a non-zero `shift_deg` gets wrong or
infeasible `opf` / `market` results until the phase-shifter fix lands... `pf.solve_dc` is
right."* T5 (`6a7617f`) deletes all four in full, on the stated basis that the defect is fixed.
Finding 1 shows it is **not** fixed for `opf.multiperiod_dc_opf`, `opf.redispatch_dc_opf`,
`market.solve_multiperiod` or `market.solve_zonal` — the deleted text's claim ("`opf` / `market`
results" are wrong with a shifter) is still literally true for those four call paths. Deleting
the caveat rather than narrowing it now actively tells a reader that phase shifters are safe
across mambo's `opf`/`market` surface, which is false. `docs/changelog.md`'s new "Fixed" entry is
narrower and does not make this over-broad claim (it names the three sites explicitly) — only
the `formats.md` deletions overreach.

**Proposed fix:** restore a caveat in the four sections, narrowed to name
`opf.multiperiod_dc_opf`, `opf.redispatch_dc_opf`, `market.solve_multiperiod` and
`market.solve_zonal` specifically (the three T2/T3/T1 sites are genuinely fixed and should stay
uncaveated); remove it for real once finding 1 is closed.

### 3. Should-fix, non-blocking — carried forward from the audit, independently confirmed

`test_dc_opf_flow_limit_row_reports_infeasible_below_the_achievable_floor`
(`tests/unit/test_shifter_flow_fix.py:114`) asserts only `status == "Infeasible"`, not *why* — a
T1 regression producing `Infeasible` for an unrelated reason would still pass this test alone
(its sibling `test_dc_opf_flow_limit_row_forces_a_true_physical_redispatch` is what actually
discharges AC-1, per the audit). No new instance of this pattern found elsewhere in the two new
test files.

### 4. Informational — the critic brief's performance premise doesn't hold; no timing needed

The dispatch brief assumed `flow_from_ptdf` is called per-round inside `market.solve_agents`'s
loop via `market/_clearing.py`. Traced the actual control flow (`market/agents.py:551-620`):
`ptdf_matrix = compute_ptdf(arr)` is built once before `while True:` (as its own comment says,
"critic finding 3, M7 S11"); the loop itself calls only `dc_opf(..., ptdf=ptdf_matrix)` and
`lmp_decomposition` every round. `clearing_rows` — the only caller of `flow_from_ptdf` in this
path — is called exactly **once**, after the loop breaks, on the final round only
(`market/agents.py:620`, matching `_clearing.py`'s own module docstring: "`solve_nodal` clears
once; `solve_agents` clears once per round and reports its **last** one"). The fix's new
`p_shift(arr)` computation (one `incidence(arr)` build plus one sparse matvec) therefore runs
once per `solve_agents` call, not once per round — negligible next to a 200-round LP loop. No
regression to measure.

### 5. Investigated, not a bug — transformer + phase shifter interaction

Built a branch with both `tap_ratio=1.05` and `shift_deg=-7.0` (`kind="transformer"`). First
attempt showed a 26.9 MW mismatch between `flow_from_ptdf` and `pf.solve_dc` — traced to my own
test script, not the code: I fed `flow_from_ptdf` an injection vector with a nonzero value at a
non-slack generator bus while that generator's `Generator.p_mw` (which `pf.solve_dc` reads via
`NetworkArrays.p_gen_pu`) was still its unset default of `0.0` — an apples-to-oranges comparison.
Rebuilt with the network's own declared generator dispatch matching the injection vector
(`scratchpad/.../transformer_shift2.py`): `flow_from_ptdf` and `pf.solve_dc` agree to `7.1e-15`.
`Branch.kind`/tap machinery (M8) and the shifter fix are confirmed orthogonal — `branch_susceptance`
(`1/(x·tap)`) is the one place tap enters, and both `pf.solve_dc` and `flow_from_ptdf` build on
identical `bbus`/`bf`/`p_shift`/`pf_shift` primitives, so the algebraic identity holds regardless
of tap.

### 6. Investigated, confirmed correct — superposition, slack-adjacency, extreme angles

At the three sites the fix touched (proven via `flow_from_ptdf` directly, since it is the shared
primitive all three now call):

- **Two shifters** on one network (−7° and +12°, non-symmetric): max abs diff vs `pf.solve_dc`
  `2.8e-14` — `p_shift`'s `Cftᵀ · pf_shift` construction sums correctly over both shifted
  branches (no per-branch special-casing needed; it was already a sum).
- **Shifter touching the slack bus directly** (`b1`→`b2`, `b1` is slack, `θ[slack]=0` enforced):
  `2.1e-14`.
- **Extreme `shift_deg`** — `180.0`, `720.0`, `-540.0`: `5.7e-13`, `9.1e-13`, `1.4e-12` (these
  grow with angle magnitude from `sin`/`cos`-free linear-DC roundoff, not a formula defect —
  still 9-10 orders of magnitude below any physically meaningful tolerance).

Scripts: `scratchpad/shifter-critic-9e00ab5/edge_cases.py`.

### 7. T1's hand-derived LP constant — re-derived independently, confirmed identical

Re-derived `dc_opf.py`'s `const = pf_shift_mw - ptdf_matrix @ (fixed_bus_mw + p_shift_mw)` from
the actual row construction (`_flow_limit_rows`, `_balance_row`, the full elastic-demand column
layout in `dc_opf`'s body — not from the module docstring's own restatement of it): writing the
full-injection identity as (decision-variable PTDF terms) + (constant), the constant term is
exactly `pf_shift_k - ptdf[k,:]·(fixed_bus_mw + p_shift_mw)`, matching the code. Also confirmed
by hand that the balance row needs no correction: `Σ_bus p_shift(arr) == 0` identically (every
row of `Cft` sums to zero, so `Cftᵀ·pf_shift` sums to zero regardless of shift values) — the
module comment's claim is correct.

## Verdict

**Not merge-ready.** Findings 1 and 2 are blocking. The task's own Scope section, written before
Step 0, named exactly three call sites sharing "the same flow, missing `- p_shift`" — but the
codebase has at least two more (`opf.multiperiod_dc_opf`, `opf.redispatch_dc_opf`) that
independently reconstruct the identical formula and were never touched by any of the six
commits; they remain exactly as broken as the diagnosed defect, reachable end-to-end through
`market.solve_multiperiod`'s dispatch/duals and `market.solve_zonal`'s public `branches[].p_from_mw`
(proven numerically: 81.4 MW off at an `Optimal` dispatch, and a reproduced false-`Infeasible`
identical in kind to the one the walk used to characterize the original bug). The audit's
"PASS, 8/8, 0 blocking" verdict did not catch this — Priority 2 of this critic's own dispatch
("multiperiod/zonal/redispatch OPF variants... do they have their OWN copy... this fix did NOT
touch") anticipated exactly this gap, and it is real. Compounding it, T5's documentation change
deletes (rather than narrows) a caveat that is still true for those two unfixed modules, so the
shipped docs now assert phase shifters are safe everywhere in `opf`/`market`, which is false.
Everything else holds up under independent reconstruction: the three sites the fix does touch are
correct (T1's hand-derived constant re-derived from the row-construction code, not from any
existing writeup; both the balance-row and flow-limit-row derivations check out algebraically),
robust to two shifters, a slack-adjacent shifter, extreme shift angles, and transformer+shift
combinations (my own first attempt at that last case produced a false alarm, traced to a bug in
my test script, not the code — logged as finding 5 so it isn't silently discarded), the
performance premise in the dispatch brief doesn't hold (no per-round `p_shift` recomputation
exists to regress), and test quality has only the one already-known, already-carried-forward
should-fix. Recommend: extend the fix to `opf/multiperiod.py` and `opf/redispatch.py` (mirroring
`dc_opf.py`'s by-hand LP-constant derivation, and a direct `flow_from_ptdf` call for
`redispatch.py`'s reported `branch_flow_mw`), add regression tests for the two now-covered
solvers plus `market.solve_multiperiod`/`market.solve_zonal` on `tests/_shifter.py`'s fixture,
restore narrowed `formats.md` caveats naming the still-affected paths, then re-run Steps 4-6.
