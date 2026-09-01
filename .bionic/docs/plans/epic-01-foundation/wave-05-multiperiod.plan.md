---
governing-skill: superpowers:writing-plans
sdlc-step: 3
intent: build
rigor: audited
scale: wave
canonical_sdlc_version: 13
surface_type: library
language: python
has_ui: false
multi_agent: true
deploy_target: pypi
cleanup_on_finish: true
use_worktree: true
rigor-floor: audited
walk: required
design-interview: true
model_plan:
  orchestrator: opus-5
  implementor: sonnet
  senior-implementor: opus
  researcher: sonnet
  test-runner: sonnet
  auditor: opus
  critic: opus
---

# Wave M5 plan — multiperiod

Spec: `.bionic/docs/specs/epic-01-foundation/wave-05-multiperiod.spec.md` (design pointer →
epic spec §Design, plus the M5-local `## Design` section written after the 2026-08-25 interview).
Branch: `wave/05-multiperiod` off `epic/01-foundation` (`e88752c`). Worktree:
`C:\Claude Projects\mambo-power-m5` with `.bionic` junctioned to the main checkout (remove the
junction with git-bash `rm`, NOT PowerShell/cmd `rmdir` — assumption A7 — **before**
`git worktree remove`).

## SDLC State

integration-branch: epic/01-foundation
intent: build
rigor: audited
scale: wave
current: 4

- Step 0: prereqs: ok; configured 2026-08-25 via "confirm"; model_plan=opus-5 orchestrator /
  sonnet-opus tiers; integration-branch=epic/01-foundation; walk=required (docs site is
  drivable, standing R14)
- Step 1: scope closed 2026-08-25 via 3 scoping answers (load profile only; cyclic end-of-horizon
  SoC; the solve entry point *is* the runner) — recorded in record/m5-scope-closure.md, and
  carried into the spec's Requirements + Not Doing + Prior art sections; research
  record/m5-research.md (8 sections). Research corrected a stale carry-over: assumption A4
  (PyPSA infeasible) had been closed inside M3 and was propagated forward in error by both
  m4-research.md §3.2 and continuation-m4.md; both corrected 2026-08-25, AC-6 keeps its oracle
  tier as a result.
- Step 2: design interview 2026-08-25 — frame ratified ("Frame holds — walk D1 first"), then
  D1 (T-loop location: "Extract shared core; both call it"), D2 (Period shape: "Per-load
  override, no bid fields"), D3 (jobs surface: "Widen Runner to Scenario, uniformly") each
  ratified individually; three tactical defaults T1-T3 surfaced at ratification; composed design
  ratified ("Ratified — write the spec"); spec §Design written after that ratification
- Step 3: wave-05-multiperiod.plan.md approved by user 2026-08-25 ("APPROVED"); design + plan +
  matrix locked together at that one checkpoint; governing design named in the approval display
  (spec §Design + epic spec pointer)
- Step 4: slices S1-S3 landed as commits fbab76d (S1), 7afa9c5 (S2), d0031cb (S3) — reports
  record/m5-s{1,2,3}-report.md. Full-suite reconciliation on the clean combined tree:
  **692 passed** = 654 baseline + 22 (S2) + 16 (S3) + 0 (S1, pure refactor); mypy clean (43
  source files); repo-wide ruff clean. S4-S8 pending. Real findings: S1 proved AC-1's
  "extraction is real" half by sabotage rather than by reading, 6/6 helpers going red when
  broken; S3 found no `model.Storage` field gap, so the M1 stub was sufficient after all; S2's
  dangling-ref check proved firing on both construction and JSON paths with a paired positive
  case. Two orchestrator errors, both disclosed and corrected in place: a `git stash` of the
  shared worktree while S1/S2 were live (no data loss — S2 re-read all seven files and confirmed
  them intact), and overwriting S2's own report after misreading an idle notification as death
  (restored, agent content primary). Worktree: C:\Claude Projects\mambo-power-m5; base-sha:
  e88752c; branch: wave/05-multiperiod

## Slices

| Slice | Delivers | ACs | complexity | role |
|---|---|---|---|---|
| S1 core-extraction | W1: extract `dc_opf`'s balance row / PTDF flow rows / epigraph+hypograph cost blocks into internal helpers; `dc_opf()` keeps its exact public signature as the T=1 caller | AC-1 | complex | senior-implementor |
| S2 domain-model | W3: `Period`, `Scenario.periods`, `Generator.ramp_up_mw`/`ramp_down_mw` | AC-2 (model half) | standard | implementor |
| S3 arrays | W4: `NetworkArrays` per-storage identity, mirroring M4's per-load identity | AC-3 (arrays half) | standard | implementor |
| S4 multiperiod-builder | W2: `opf/multiperiod.py` — T-loop over S1's core, ramp rows, SoC rows, cyclic row | AC-2, AC-3 | complex | senior-implementor |
| S5 market-multiperiod | W5: `market/multiperiod.py:solve_multiperiod`, `MarketMultiperiodResult`, per-period settlement | AC-4, AC-5 | complex | senior-implementor |
| S6 fixtures-oracle | W7: `tests/_periods.py`, `tests/_storage.py`, rated branch via `tests/_rated.py`; PyPSA multi-period parity test | AC-6 | standard | implementor |
| S7 jobs | W6: `SolveRequest` widening, uniform `Runner`, `market.multiperiod` kind | AC-7 | standard | implementor |
| S8 docs | W8: manual page, API page, architecture diagram, example + CI + snippet embed | AC-8 | complex | senior-implementor |

**Order: S1, S2 and S3 run in parallel** (disjoint files: `opf/dc_opf.py` vs
`model/entities.py`+`model/scenario.py` vs `numerics/arrays.py` — flag to all three that they may
each need to touch an `__init__.py` export, the collision M3's S2/S4 and M4's S1/S2 both hit;
stage explicit paths and coordinate directly if two land near the same time).

**S1 is the gating slice and must be proven before S4 starts.** AC-1 requires the extraction to
be behaviour-preserving with **zero test edits** — 654/654 green and oracle parity (MATPOWER,
pandapower, PyPSA) unchanged. This is assumption A6's own consequence, named in the design
interview: if the extraction and the first multiperiod row family land together, a parity
regression cannot be attributed to either. S4 starts once S1 **and** S3 have landed.

S5 starts once both S2 (Period/Scenario) and S4 (builder) have landed. S6 and S7 both start once
S5 lands and may run in parallel (disjoint: `tests/_periods.py`+`tests/_storage.py`+a new parity
test vs `jobs/*.py`). S8 last. Every slice RED → GREEN.

## Verification Matrix

stack-health: before (M4 close, merge commit e88752c): 654 tests, ruff/format/mypy clean, mkdocs
--strict 0 warnings, 9/9 examples, build+smoke clean; after: PENDING — taken at Step 5

walk-artifact: PENDING — Step 5 opens with it (`walk: required`; the mkdocs site is the drivable
surface, walked by an agent that has not read the ACs, same as M2/M3/M4)

auditor-wave: PENDING — Step 5 exit gate

| AC | tier | status | evidence | auditor |
|---|---|---|---|---|
| AC-1 | T1 | pending | see AC-1 | |
| AC-2 | T1 | pending | see AC-2 | |
| AC-3 | T1 | pending | see AC-3 | |
| AC-4 | T1 | pending | see AC-4 | |
| AC-5 | T1 | pending | see AC-5 | |
| AC-6 | T2 | pending | see AC-6 | |
| AC-7 | T1 | pending | see AC-7 | |
| AC-8 | T2 | pending | see AC-8 | |

AC-1:
  criterion: S1's extraction of the shared row-family core is behaviour-preserving — the full
    suite passes with zero test edits, and `dc_opf`'s existing oracle parity (MATPOWER,
    pandapower, PyPSA) is unchanged
  provenance: wave spec W1; design interview D1 2026-08-25
  tier-rationale: T1 — pure substrate, no runtime surface. The proof is the existing suite going
    green unmodified, which is a stronger claim than any new test could make.
  tier-run: (filled at Step 4/5)
  readback: (filled at Step 4/5)

AC-2:
  criterion: the multiperiod builder reproduces a hand-derived optimum exactly on a small case
    where a generator ramp limit binds, with the binding period identified and its dual recovered
  provenance: wave spec W2; epic spec R7; record/m5-research.md §2.2
  tier-rationale: T1 — pure substrate; the hand-derived optimum is the oracle, same shape as M3's
    hand-KKT case and M4's AC-1.
  tier-run: (filled at Step 4/5)
  readback: (filled at Step 4/5)

AC-3:
  criterion: SoC balance holds every period with charge/discharge efficiency applied; the cyclic
    condition SoC_T == soc_initial is met exactly; a committed invariant test shows
    min(charge, discharge) ~= 0 on every fixture M5 ships
  provenance: wave spec W2/W3; user 2026-08-25 scope answer 2 "Cyclic"; record/m5-research.md §3.3
  tier-rationale: T1 — pure substrate. Note the absence-readback rule applies to the
    min(charge, discharge) ~= 0 check: a near-zero reading proves nothing on its own, so this row
    must carry a paired positive case — research §3.2's constructed overlap-required network,
    where the same readback is non-zero — or it is presumed powerless.
  tier-run: (filled at Step 4/5)
  readback: (filled at Step 4/5)

AC-4:
  criterion: a T=1 multiperiod solve reproduces market.nodal's dispatch, duals and LMPs exactly
    (not approximately) on a real fixture; and Scenario.periods=None leaves market.nodal
    byte-identical to its M4 behaviour
  provenance: wave spec W5; epic spec module table "1 period ≡ nodal"; record/m5-research.md §6.2
  tier-rationale: T1 — pure substrate, and the wave's own agreement test for the shared-core
    ownership row: it is what fails if S1's extraction and S4's T-loop ever disagree.
  tier-run: (filled at Step 4/5)
  readback: (filled at Step 4/5)

AC-5:
  criterion: the analytic 2-bus/2-period storage-arbitrage optimum is reproduced to the pinned
    tolerance, matching record/m5-research.md §7.2's closed-form derivation
  provenance: wave spec W5; epic spec module table "analytic 2-bus/2-period arbitrage";
    record/m5-research.md §7.2-7.3
  tier-rationale: T1 — pure substrate; the closed form is the oracle, already independently
    cross-checked against a scipy LP at research stage to 6 decimals.
  tier-run: (filled at Step 4/5)
  readback: (filled at Step 4/5)

AC-6:
  criterion: market.multiperiod matches a PyPSA multi-period oracle (ramp limits and lossy
    storage both active) within a tolerance measured and pinned at implementation, on at least
    one real fixture with a rated branch so congestion binds in some periods and not others
  provenance: wave spec W7; epic spec R9; record/m5-research.md §1.3, §8.2
  tier-rationale: T2 — engine-divergent, real oracle engine over a declared-fidelity fixture.
  fixture-fidelity: (declared at Step 4/5) — derived 24-period profile and storage sizing on
    already-verbatim MATPOWER fixtures via tests/_periods.py + tests/_storage.py, rated branch
    via tests/_rated.py, all test-time derivation committing no new fixture data. **The rated
    branch is load-bearing, not decoration**: M4's own critic proved that a fixture whose answer
    is pinned by a bound cannot test the term that moves the answer, so this fixture must
    demonstrably produce a period where congestion binds and a period where it does not.
  tier-run: (filled at Step 4/5)
  readback: (filled at Step 4/5)

AC-7:
  criterion: jobs.run/run_json for market.multiperiod is pure, JSON round-trips and never raises;
    every pre-existing SolveRequest(kind=..., network=...) still works unchanged across all five
    prior kinds; jobs.KINDS lists exactly 6 kinds
  provenance: wave spec W6; design interview D3 2026-08-25; epic ADR-004
  tier-rationale: T1 — pure substrate. The backward-compatibility half is the risky half: D3
    widens a public, JSON-serializable request surface, so the existing-kinds check is not a
    formality.
  tier-run: (filled at Step 4/5)
  readback: (filled at Step 4/5)

AC-8:
  criterion: mkdocs build --strict exits 0 with the new manual + API pages; the symbol-coverage
    test passes without modification; the new example exits 0 in CI and is snippet-embedded
  provenance: wave spec W8; epic spec R14 standing requirement 2026-08-20
  tier-rationale: T2 — the built site is the artifact, same as M2/M3/M4's docs AC.
  fixture-fidelity: the built site itself, same as prior waves' docs ACs
  tier-run: (filled at Step 4/5)
  readback: (filled at Step 4/5)

## Tasks

The wave's dispatched-unit ledger — using the canonical `## Tasks` heading from the start, per
assumption A8 (M1-M3 titled this "Dispatch ledger" and predate the evidence gate's check). One
row per dispatched unit, written at dispatch and completed at execution-confirmation.

| id | role | unit | deliverable | status |
|---|---|---|---|---|
| m5-s1-core-extraction | senior-implementor | S1 core-extraction: extract dc_opf's balance row / PTDF flow rows / epigraph+hypograph cost blocks into internal helpers, dc_opf() unchanged as the T=1 caller — progress .bionic/tmp/m5-s1-progress.md, cadence 10m, ~75-100 min | record/m5-s1-report.md + commit on wave/05-multiperiod | done (commit fbab76d, one file, +231/-80; AC-1 BOTH halves proven. Half 1: 654->654 zero test edits, proved by hashing every tracked file against its e88752c blob — only dc_opf.py differs; parity 196 passed, the MATPOWER/pandapower/PyPSA files 91 passed. Half 2: sabotage proof, 6/6 helpers go red when broken, file restored byte-identical. Agent could not reconcile in the shared worktree so it built an isolated `git archive e88752c` tree with a PYTHONPATH prefix over the shared venv — verified via mambo_power.__file__. Orchestrator independently re-ran the _balance_row sabotage: RED in 1.73s, restored clean) |
| m5-s2-domain-model | implementor | S2 domain-model: Period, Scenario.periods, Generator.ramp_up_mw/ramp_down_mw — progress .bionic/tmp/m5-s2-progress.md, cadence 10m, ~45-60 min | record/m5-s2-report.md + commit on wave/05-multiperiod | done (commit 7afa9c5; +22 tests by --collect-only count, 654+22=676 this slice's own contribution; dangling-ref catch proved on both construction and JSON paths with a paired positive case; ramp >0 rejection independently re-proved by the orchestrator at the validate_network level). **Orchestrator error, corrected**: an idle notification was misread as the A9 non-response pattern and the agent's own report was overwritten before its late-arriving completion message showed it had finished normally; report restored with the agent's content primary and the orchestrator's independent re-verification kept alongside. Agent's committed work never touched. Agent self-flagged its own deviation — it committed before sending the completion message, which is what made the misread possible |
| m5-s3-arrays | implementor | S3 arrays: NetworkArrays per-storage identity, mirroring M4's per-load identity — progress .bionic/tmp/m5-s3-progress.md, cadence 10m, ~45-60 min | record/m5-s3-report.md + commit on wave/05-multiperiod | done (commit d0031cb, report verified on disk 8.7KB; 32 passed scoped, RED proved via AttributeError on storage_ids; existing aggregate arrays proved byte-identical on all 6 fixtures; no model.Storage field gap found — nothing to route to S2. Agent disclosed rather than hid that its 670 full-suite figure was contaminated by S1/S2 in-flight edits) |
| m5-s4-multiperiod-builder | senior-implementor | S4 multiperiod-builder: opf/multiperiod.py — T-loop over S1's extracted helpers, ramp coupling rows, storage SoC rows, cyclic end-of-horizon row — progress .bionic/tmp/m5-s4-progress.md, cadence 10m, ~100-140 min | record/m5-s4-report.md + commit on wave/05-multiperiod | done (commit d93c448; 3 files, +1446/-1; AC-2 and AC-3 both hold. 725 passed = 692 + 33, `git diff -- tests/` empty. AC-2: hand-derived ramp optimum written down before solving, binding period t=1, ramp dual -40.0, balance duals [-30.0, 50.0] — the negative t=0 price falls out of KKT. AC-3: paired positive case genuinely non-zero — min(charge,discharge)=[26.667,26.667] MW on research §3.2's overlap-required network vs <1e-7 on four canonical fixtures, plus an Infeasible negative control proving the shared power-limit row is load-bearing. **Caught two powerless tests of its own** by sabotage sweep (see A10). S1's helpers called unmodified, no signature changed; dc_opf.py absent from the commit entirely. Orchestrator re-verified: scope, 725 full suite, 33/33 own tests, and the four power-proving tests by name) |
| m5-s5-market-multiperiod | senior-implementor | S5 market-multiperiod: market/multiperiod.py solve_multiperiod + MarketMultiperiodResult + per-period settlement — progress .bionic/tmp/m5-s5-progress.md, cadence 10m, ~100-140 min | record/m5-s5-report.md + commit on wave/05-multiperiod | done (commit faba273; 7 files, +1318/-8; AC-4 and AC-5 both hold. 747 = 725 + 22, verified by the orchestrator's own independent full-suite run. AC-4 bit-exact via assert_array_equal (not allclose) on dispatch/duals/LMPs vs solve_nodal on case14+case30; period-less scenarios route through the structurally exact `None` path, the materialised path's agreement documented as measured. AC-5 matches research §7.2/§7.3's closed form incl. mu_soc=-11.111111 from its independent scipy probe. **Settlement identity closes per period with storage as the third participant**, right side built via a separate array-level call and a PTDF recomputed from numerics.ptdf.ptdf; paired negative readings prove storage's and the shunt's terms are both load-bearing. Caught 3 powerless tests of its own (ramp transposition no-op, shunt term decorative, flat-profile risk). Promoted `_load_bid_coeffs` -> public `load_bid_coeffs` for sharing, M4/R2's own precedent — M4's nodal test files byte-identical across the whole wave, so nodal behaviour provably unchanged. Surfaced A16 (M4's identity statement omits shunt/pf_shift terms)) |
| m5-s6-fixtures-oracle | implementor | S6 fixtures-oracle: tests/_periods.py + tests/_storage.py derivations, rated branch via tests/_rated.py, PyPSA multi-period parity test — progress .bionic/tmp/m5-s6-progress.md, cadence 10m, ~75-100 min | record/m5-s6-report.md + commit on wave/05-multiperiod | done (commit ad0ad7e; 5 files, +777, all under tests/, no src/ touched; 27/27 own tests verified by the orchestrator. AC-6 holds: case14 x 24 periods with rated branches, ramp AND lossy storage both active. Residuals measured then margined — obj 4.35e-13 rel (tol 1e-9), gen dispatch 3.01e-4 MW (tol 1e-2), storage net 1.10e-4 MW (tol 1e-2), SoC 1.25e-4 MWh (tol 1e-2), LMP 4.24e-5 $/MWh (tol 1e-3). **Binding/non-binding precondition committed as its own test**: 10 of 24 hours have a branch exactly at rating, 14 hours have every branch <95% — the power M4's AC-6 fixture lacked. Sabotage vs the true oracle held fixed: ramp removed 9.2 MW (~900x tol), efficiency magnitude wrong 2.16 MW (~200x), two rating loosenings 6.84/2.10 MW — all RED. Two findings disclosed, see A18/A19) |
| m5-s7-jobs | implementor | S7 jobs: SolveRequest network-or-scenario widening, uniform (Scenario, options) Runner, market.multiperiod kind — progress .bionic/tmp/m5-s7-progress.md, cadence 10m, ~60-80 min | record/m5-s7-report.md + commit on wave/05-multiperiod | done (commit 1fd4c74, **landed by the orchestrator under the non-response procedure** — agent completed and verified the work, reported green, then went idle across two nudge rounds without committing; its four files committed byte-for-byte unchanged, and it wrote its own 22KB report afterwards. AC-7 holds: KINDS exactly 6; network=/scenario= both ok, neither/both both ValidationError; market.multiperiod over a real 3-period Scenario returns a typed MarketMultiperiodResult and JSON round-trips with type preserved — **every one of these re-verified directly by the orchestrator before landing**, not taken on report. 795 = 774 + 21, confirmed by an independent full-suite run and again by the agent standalone (515.85s, no contention). 39 pre-existing test cases unmodified. Sabotages redone fresh against the landed commit: neutered exactly-one-of validator -> 2 red; dropped periods -> 4 red; restored and sha256-verified against the committed blob. Stub edit adjudicated in A21. Real finding in A22) |
| m5-s8-docs | senior-implementor | S8 docs: multiperiod manual page, API pages, architecture diagram edges, runnable example + snippet embed, jobs.md staleness check — progress .bionic/tmp/m5-s8-progress.md, cadence 10m, ~75-100 min | record/m5-s8-report.md + commit on wave/05-multiperiod | active (dispatched 2026-08-25) |
| m5-research | researcher | Step 1/2: PyPSA oracle viability, LP formulation + sizing, storage modelling, ramp fields, Scenario.periods options, degeneracy conditions, analytic arbitrage derivation, fixture strategy | record/m5-research.md | done (8 sections, every claim command-backed; §1 verdict YES on the PyPSA oracle — and found A4 had already been fixed in M3, correcting two stale records; §2.4 surfaced the T-loop-location fork that became design decision D1; §6/§7 derivations ready to become AC-4/AC-5 tests directly) |

## Assumptions

- A1 (spec A1): PyPSA is a working multi-period oracle — **verified, not assumed** (20 parity
  tests on 5 fixtures plus an end-to-end multi-period probe with ramp and lossy storage,
  2026-08-25). Supersedes the stale A4 carried in M4's plan and continuation, both corrected.
- A2 (spec A2): simultaneous charge/discharge does not bind on M5's own fixtures — to be **proven
  by a committed invariant test** (AC-3), never assumed. Research §3.2 constructed a case where
  forbidding overlap makes the LP infeasible, so the formulation bounds it rather than banning it.
- A3 (spec A3): no MATPOWER fixture populates ramp data (all-zero columns on every generator of
  all five fixtures), so `None` is the honest default; `0` would mean "cannot move at all".
- A4 (spec A4): no fixture carries storage; derived at test time (S6).
- A5 (spec A5): cyclic end-of-horizon SoC, not configurable this wave (user scope answer 2).
- A6 (spec A6): S1's extraction must be proven behaviour-preserving **before** S4 starts —
  entangling the two makes a parity regression unattributable. This is a slice-ordering
  constraint, not a preference.
- A7 (carry-over, M4, **extended 2026-08-25**): the worktree `.bionic` junction needs
  *different* shells at each end on this machine. **Create with PowerShell**
  (`New-Item -ItemType Junction -Path <worktree>\.bionic -Target <main>\.bionic`) — git-bash
  `ln -s` fails "Operation not permitted" even with MSYS=winsymlinks:nativestrict, and `cmd
  //c mklink /J` through git-bash gets its arguments mangled by path translation. **Remove with
  git-bash `rm`** before `git worktree remove` — PowerShell/cmd `rmdir` is sandbox-blocked on
  that path (the original M4 finding). Verified both ends 2026-08-25: git-bash reads the result
  as a symlink, plan and spec are visible through it, `git status` stays clean.
- A8 (carry-over, M4): the evidence gate requires a `## Tasks` heading on an audited multi-agent
  wave plan; M1-M3's plans still use the old "Dispatch ledger" title and would block if anything
  ever commits against them again.
- A14 (finding, S4 2026-08-25): **research §2.2's column layout did not survive contact with the
  real builder.** Its "T per-period blocks concatenated, each ending in that period's PWL free
  variables" conflicts with `dc_opf`'s documented Hessian-ordering constraint — the Hessian is
  passed once over a column *prefix*, before any free `cost_g`/`val_d` column exists. S4 hoisted
  the free variables into a second tier: tier-1 `[gen|demand|charge|discharge|soc]` per period,
  then tier-2 `[cost_g|val_d]` per period. Same LP, documented in the module docstring. Payoff:
  at T=1 the builder is column-for-column, row-for-row and call-for-call what `dc_opf` itself
  builds, so the AC-4 degeneracy is **bit-exact** — two committed tests assert
  `np.testing.assert_array_equal`, not `allclose`.
- A22 (finding, S7 2026-08-25 — **the one place D3's widening had real teeth**): `Scenario(network=net)`
  genuinely re-runs `Network`'s own validator on wrap (Scenario's own docstring says so; S7 had
  assumed no-revalidation-on-wrap). So resolving a request whose network had been mutated
  in-place into an invalid state could raise `NetworkValidationError` **at the resolution step,
  before `run()`'s own `validate_network()` ever executed** — which would have broken AC-7's
  "never raises" contract and the pre-existing
  `test_mutated_invalid_network_through_run_is_a_failed_result`. Caught and handled in `run()` at
  resolution; that test is green and unedited (verified by the orchestrator: the only occurrence
  of its name in the whole diff is an *added* line inside a new test's docstring referencing it,
  not an edit to the function). Worth recording because it shows D3's widening was not the purely
  mechanical signature change it looked like — it moved *when* validation happens, and only the
  pre-existing test caught that.
- A21 (adjudication, orchestrator 2026-08-25 — **for the auditor**): S7's brief said that editing
  a pre-existing test to make things pass *is* the backward-compatibility break announcing
  itself. S7 edited one and flagged it inline rather than absorbing it. **Adjudicated as the
  legitimate exception, on content not testimony.** `git diff -U0 tests/unit/test_jobs.py`
  restricted to deletions yields exactly five lines: two `import` statements, the `KNOWN_KINDS`
  constant (which AC-7's own criterion *requires* to change from 5 to 6 kinds), and the two-line
  body of a local stub `wrong()` that implements the `Runner` protocol. **No pre-existing test
  case was modified, and nothing exercising the public `SolveRequest(network=...)` surface was
  touched** — all 39 pre-existing cases stand. The distinction that matters: D3 ratified widening
  the `Runner` protocol to `(Scenario, options)`, so every implementor changes by construction,
  and a test-internal stub is an implementor. That is categorically different from a public
  request-surface usage breaking, which is the compatibility AC-7 actually guards and which is
  intact. Recorded because the orchestrator set the tripwire and should be seen to have ruled on
  it explicitly rather than waved it through.
- A18 (**correction to the orchestrator's own D2 rationale**, measured by S6 2026-08-25): during
  the Step-2 design interview I argued against scalar load scaling on the grounds that "every
  load moves in lockstep, so the spatial pattern is identical in every period — congestion binds
  in all 24 or none." **That specific claim is empirically false and S6 measured it.** A single
  uniform system-wide curve (peak 1.2x / trough 0.7x) on case14 produces genuine differentiation:
  10 of 24 hours have a branch exactly at its rating, 14 have every branch under 95%. Temporal
  variation alone differentiates, because flow *magnitudes* scale with demand even when the
  spatial *pattern* does not. D2's decision still stands on its other leg — per-load overrides
  are strictly more general and M7's confirmed dependency needs them — but the argument I used to
  sell it did not survive contact with a real fixture, and a later reader should not inherit it as
  established. S6 in fact had to *abandon* per-load diversity for this fixture: any divergence
  from case14's own base-case load ratios, even a 2-hour phase shift at unchanged amplitude, makes
  the 24-period LP infeasible, because several of `tests/_rated.py`'s derived ratings sit at
  exactly their 1.2x margin with no redispatch slack.
- A19 (finding, S6 2026-08-25, **undiagnosed — carry-forward candidate**): rating both PyPSA
  `Line` and `Transformer` components simultaneously makes PyPSA's constrained QP genuinely
  infeasible on case14 (which has 3 tap-ratio transformers). Reproduced from the bare
  single-period base case — the exact dispatch the ratings were derived from — up through 3x
  uniform slack on every rating, so it is not a numerical near-miss. Root cause `unverified`
  beyond "reproducibly fails". Routed around by rating only the 17 lines in the oracle, which is
  safe *and asserted in the committed test*: every branch that actually binds in our own engine's
  dispatch across the horizon is one of those 17. Same shape as M4's `sgen` workaround for
  pandapower's quadratic-load-cost non-convergence — a real third-party limitation, named
  precisely so a future reader or a PyPSA upgrade does not have to rediscover it.
- A20 (weakness, S6 2026-08-25, **disclosed — expect the auditor and critic to probe it**):
  storage's usage on the AC-6 fixture is small (~0.5-1 MW) and nearly symmetric between charge
  and discharge, so **transposing the two true efficiency values is a near no-op** (3.14e-4 MW
  residual vs 3.01e-4 baseline noise). A magnitude sabotage on the same field *is* caught
  clearly (2.16 MW, ~200x tolerance), so storage is not decorative in AC-6 — but the fixture
  cannot distinguish which efficiency is which. This is a narrower version of the gap M4's critic
  found in its own AC-6, and it is disclosed rather than discovered. Note S4's AC-3 covers
  efficiency orientation directly on a hand-built asymmetric fixture
  (`test_charge_and_discharge_efficiencies_enter_the_soc_row_the_right_way_round`), so the wave
  does prove it — just not at AC-6's oracle tier.
- A17 (fold candidates, collected during Step 4 — close at the wave's R-fold, not mid-slice):
  (a) `opf/__init__.py`'s `gen_cost_coeffs` docstring says the demand-side mirror "has no
  prior-wave analog to share". That is now dated: S5 promoted `_load_bid_coeffs` to public
  `load_bid_coeffs` for exactly that sharing, so the sentence describes a state that no longer
  holds. S5 made only the one-line cross-reference fix the rename strictly required and flagged
  the content rather than expanding an out-of-scope edit — correct call, close it at the fold.
  (b) A16's `market.nodal` identity docstring, same fold or M6.
  (c) S5 notes `test_api_docs_coverage.py` is green without a docs edit because the new symbols
  are reachable through the existing `::: mambo_power.market` / `::: mambo_power.results`
  directives; S8 may still want dedicated `::: mambo_power.market.multiperiod` and
  `::: mambo_power.results.multiperiod` blocks for page structure. S8's call, not a defect.
- A16 (finding about M4, surfaced by S5 2026-08-25 — **candidate for M6/M9, not fixed in M5**):
  M4's statement of the settlement identity omits the shunt and phase-shift terms, and was
  correct only because none of M4's own fixtures carried either. The general per-period form S5
  derived and proved is `load_payment + storage_charge_payment - generator_receipts -
  storage_discharge_revenue == -sum_k mu_k*f_k + sum_k mu_k*pf_shift_k - sum_n LMP_n*g_shunt_n`.
  `case300` does carry non-zero `g_shunt` (max 0.0014 pu, measured), so a `market.nodal` user on
  that fixture would find `MarketNodalResult.congestion_rent`'s docstring claim
  ("equals -sum_k(mu_k * flow_k) at the optimum") not holding exactly. The computed *value* is
  right — it is the operator's merchandising surplus by construction — but the documented
  identity is stated too strongly. S5 corrected the wording on its own new type; M4's nodal type
  still carries the imprecise claim. Not fixed here: M5's shape locked at Step 3 and `market/
  nodal.py`'s documented behaviour is out of this wave's scope. Worth one docstring correction in
  M6 or M9.
- A15 (decision, orchestrator 2026-08-25): `multiperiod_dc_opf` takes **no `options` parameter**.
  S4 offered one for symmetry with `dc_opf` and flagged it as a two-line change; declined —
  `dc_opf`'s own options parameter does nothing but `del options`, so an empty model at the
  array level would be exactly the speculative-field trap design decision D2 rejected. Options
  belong at the market layer, where S5 owns `MarketMultiperiodOptions` mirroring
  `MarketNodalOptions`.
- A13 (process rule, from the M5 orchestrator's own error 2026-08-25): **verification gestures
  against a worktree that any slice is live in must be READ-ONLY.** `git stash push
  --include-untracked` silently pulls the floor out from under every agent holding uncommitted
  work in that tree. The orchestrator did this while S1 and S2 were live; it happened to be
  harmless (both re-read their files and confirmed them intact — S1 proved it with a three-way
  sha256 over the committed blob, its proof-tree copy and the working tree) but would not have
  been thirty minutes earlier. Use instead: `git show <sha>:<path>` to read a committed version,
  `git worktree add --detach` for a throwaway checkout, or a `git archive <sha>` extraction run
  against the shared venv via a PYTHONPATH prefix — S1's own isolation technique, which had the
  side benefit of making its whole AC-1 proof immune to this. Never `stash`, never `checkout`,
  never `reset` a shared worktree while a slice is active.
- A12 (process, hit 2026-08-25): `dispatch-preflight.sh` fails to match a deliverable label
  wrapped in markdown bold (`**Expected artifact:** <path>`), blocking the dispatch with "names
  no deliverable" even though the path is present — despite that exact form having passed for
  four earlier dispatches this session. Workaround: write the label plain and unstyled at the
  very start of the brief (`Expected artifact: <path>`). Fragile matching rather than a missing
  field; recorded so a later wave does not re-diagnose it.
- A11 (process, hit 2026-08-25): `stop-guard.sh`'s Windows-path bug (the third of the three,
  known-open since M2/M3) **blocks agent stand-down in this wave**. It declares a locally-launched
  agent FOREIGN while printing two identical session ids, and its prescribed observation command
  `stop-check.sh` then loops — reporting "ambiguous — 2 agents" while listing only one, the
  phantom-duplicate signature of the same drive-letter parse. Not worked around: forging a human
  stop order via `stop-orders.sh order` would fabricate user intent, and editing the hook is the
  user's call. Consequence: finished agents stay idle rather than stopped. Harmless but untidy;
  surfaced to the user 2026-08-25.
- A9 (carry-over, M4, **sharpened 2026-08-25**): agent non-response has recurred across M3 and
  M4, once leaving three completed items uncommitted across a session boundary. **The converse
  error is now also on record**: in M5's S2 the orchestrator read an idle notification as death,
  applied the non-response procedure to a live agent that was merely slow, and overwrote the
  report it had just written. Idle is not a completion signal *and not a failure signal*; the
  only safe reads are the completion message and the artifact on disk. Before taking over a
  writing agent's bookkeeping, check whether the artifact already exists — if it does, the agent
  is further along than the silence suggests. Every dispatch in this wave carries a
  progress-artifact path and cadence, and the non-response procedure applies — a writing agent is
  never resumed; examine its output, verify independently, take over.
- A10 (process, M4 lesson, **applied and extended 2026-08-25**): a fixture whose answer is pinned
  by a bound cannot test the term that moves the answer. AC-6's rated branch and AC-3's paired
  positive case both exist because of it. S4 then applied the lesson *proactively* and found two
  powerless tests of its own, by running an S1-style sabotage sweep over all seven of its row
  families: (a) swapping `eta_charge`/`eta_discharge` in the SoC row changed nothing, because
  every fixture had `eta_c == eta_d` — nothing in the module could tell the two apart; (b)
  deleting the cyclic row entirely changed nothing, because every fixture's unconstrained optimum
  already ended at `soc_initial`, making the cyclic assertion a tautology. Both were fixed with
  hand-derived fixtures (asymmetric efficiencies; a half-charged unit where the cyclic row
  genuinely moves the answer, cyclic dual +45.0 derived two independent ways before running).
  7/7 sabotages then go red. **The generalisation: a sabotage sweep over every row family is now
  the cheapest known way to find a test that cannot fail**, and it should be standard for any
  slice that adds constraint families. S5 then ran a 14-way sweep (13 red, the one survivor a
  documented measured-equivalence finding rather than a hole) and separately caught that its
  real-fixture identity test was powerless on case14 — every rent read 0.0 because no branch
  there ever binds — moving it to case30 with storage at the max-congestion bus. Four
  consecutive slices have now found powerless tests in their own work before reporting; this is
  the wave's most valuable emergent practice and belongs in M6's briefs from the start.

## Handoff

Resume point: Step 3, awaiting user approval of this plan. Branch `wave/05-multiperiod` not yet
created; worktree `C:\Claude Projects\mambo-power-m5` not yet created. Base
`e88752c` (epic/01-foundation, M4's merge, pushed).

Decisions ratified this session: Step 0 configuration ("confirm"); three Step-1 scoping answers;
Step-2 frame, D1, D2, D3 and the composed design.

Discovered surprises (persist): assumption A4 was stale — PyPSA has worked since M3, and the
error had propagated into two records before being caught by M5's own Step-1 research.

Open blockers: none. Uncommitted work: none in git (`.bionic` is untracked by design).

Resume instruction: on approval, `git worktree add "C:\Claude Projects\mambo-power-m5"
-b wave/05-multiperiod e88752c`, junction `.bionic` to the main checkout, verify the junction
with git-bash `ls -la`, bump `current:` to 4, then dispatch S1, S2 and S3 in parallel.
