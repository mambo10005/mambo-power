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
  orchestrator: sonnet
  implementor: sonnet
  senior-implementor: opus
  researcher: sonnet
  test-runner: sonnet
  auditor: opus
  critic: opus
---

# Wave M4 plan — nodal-market

Spec: .bionic/docs/specs/epic-01-foundation/wave-04-nodal-market.spec.md (design pointer →
epic spec §Design, plus M4-local design). Branch: wave/04-nodal-market off epic/01-foundation
(5fa3285). Worktree: C:\Claude Projects\mambo-power-m4 with `.bionic` junctioned to the main
checkout (remove the junction with git-bash `rm`, NOT PowerShell/cmd `rmdir` — see
continuation-m3.md's hook-bug note — before `git worktree remove`).

## SDLC State

integration-branch: epic/01-foundation
intent: build
rigor: audited
scale: wave
current: 9

- Step 0: prereqs: ok; configured 2026-08-24 via "confirm"; model_plan=sonnet/opus tiers;
  integration-branch=epic/01-foundation; walk=required (docs site is drivable)
- Step 1: scope closed 2026-08-24 via 2 scoping answers (elastic demand in-wave; full
  model.Scenario now) in wave-04-nodal-market.spec.md sections Requirements + Not Doing +
  Prior art; research record/m4-research.md
- Step 2: design interview 2026-08-24 — frame ratified, Decision 1 (opf.dc_opf extension:
  Option B, "the latter with cleaner lp code"), Decision 2 (Scenario periods/strategy
  fields: omit, "agree"), composed design ratified ("ok"); spec Design section written after
  ratification
- Step 3: wave-04-nodal-market.plan.md approved by user 2026-08-24 ("approved"); design +
  plan + matrix locked; worktree C:\Claude Projects\mambo-power-m4 created (base 5fa3285,
  branch wave/04-nodal-market), .bionic junctioned and verified (git-bash `ls -la` shows
  symlink, spec files visible through it)
- Step 4: slices S1-S7 landed RED→GREEN as commits 6578709, f1dfa9b, 972d7f9, ec4ba22,
  5442465, df565c6, aa53140 — reports record/m4-s{1..7}-report.md; four slices (S1, S2, S4
  briefly, and S5's completion message) hit the same non-response/lag pattern M3 saw
  repeatedly — the orchestrator verified and landed S1/S2 independently per the non-response
  procedure; S3-S7 all self-reported cleanly. Real findings along the way: S3's
  double-counting contract (dc_opf itself subtracts an elastic load's contribution using
  load_p_max_pu, not caller-trusted) plus the AC-1 hand-KKT case matching exactly on the
  first attempt; S4's decision to report every load (bid or fixed) in MarketNodalResult,
  required by the settlement identity; S5's VOLL=10,000 anchor rule proving every derived
  bid ends up fully price-taking (a mathematical consequence, not a gap — AC-4's hand-built
  network already covers the congestion+elastic interaction); S6's Scenario-wrapping
  decision for SolveRequest plus catching a stale "market.nodal as unknown-kind" example in
  examples/04_jobs_api.py the full suite surfaced; S7's jobs.md stale-snippet fix and the
  architecture diagram's real market import edges. Worktree: C:\Claude Projects\
  mambo-power-m4; base-sha: 5fa3285; branch: wave/04-nodal-market
- Step 5: walk-artifact: record/m4-walk-docs-site.md (real findings — stale home page,
  file-path/wave-shorthand leaks in public docstrings, Results manual silent on
  MarketNodalResult; math rendering clean, confirming M3's fix generalized); cmd: `uv run
  pytest -q -p no:cacheprovider` on wave head aa53140 (plus ruff, format, mypy, mkdocs
  --strict, 9 examples, build+smoke); pass: 646; total: 646; output: record/
  m4-step5-tests-floor.md; auditor: m4-auditor (record/m4-audit.md) CONFIRMED all 8 rows,
  2 non-blocking caveats closed by R1 fold (commit f5e20d9, record/m4-r1-fold-report.md)
- Step 6: stance 1 six-axis review: record/m4-review-6axis.md (Correctness/Readability/
  Architecture/Security/Performance PASS; Duplication FLAG — market/nodal.py's _gen_cost_coeffs
  a byte-for-byte duplicate of opf's _cost_coeffs; 2 correctness flags closed in-review by a
  direct 3-segment probe). stance 2 independent critic: record/m4-critic.md (ready-to-merge;
  one substantive finding — AC-6's "dispatch sub-checks are structurally decorative" framing,
  which the audit and R1 fold both accepted, is false: a one-load anchor change gives them real
  power, PROVED by a reproducible experiment; 4 notes, all confirmations; 3 falsification
  attempts, all failed). Both folded by R2 (record/m4-r2-fold-report.md) — the fold's own
  revert-and-watch measures the dispatch sub-check going from 7.14e-10 MW (undetecting) to
  1.569 MW, ~1,570x over tolerance, with dc_opf's double-counting subtraction stubbed out; src
  restored and re-confirmed byte-identical. 654/654 full suite, ruff/format/mypy clean, mkdocs
  --strict exit 0, 9/9 examples, build+smoke clean. Non-response procedure applied: the
  m4-r2-fold agent landed items A/B/C uncommitted then went idle across a session boundary —
  orchestrator verified its work independently, took over item D, stood it down.
- Step 7: adr: adrs/epic-01-foundation/adr-007-welfare-lp-extends-the-one-dc-opf-builder.md —
  Decision 1 of Step 2's design interview (extend dc_opf's own LP builder with demand-side
  columns rather than translating bids into pseudo-generators) carries the same cross-wave,
  expensive-to-reverse weight ADR-006 had: M5's ramp/SoC coupling, M6's zonal + redispatch LPs
  and M7's repeated clearing all extend this same builder, so the seam M4 fixes is the one three
  later waves inherit. Records what it cost too — M3's oracle-verified builder was modified
  rather than left alone — and the R2 fold's generalizable lesson (a fixture whose answer is
  pinned by a bound cannot test the term that moves the answer). Lesser decisions (Scenario
  shape, sgen oracle convention, SolveRequest shape, the all-or-nothing Load.bid contract) stay
  in the spec's Design section, this plan's Assumptions, and their owning docstrings.
- Step 8: merge: e88752c (wave/04-nodal-market 66ff908 -> epic/01-foundation, --no-ff, local;
  merge tree verified byte-identical to the CI-proven wave head via `git diff 66ff908 HEAD
  --stat` = empty, so the 654/654 + CI 32889587198 evidence carries over without re-running the
  suite; pushing the epic branch is the user's call, same convention as M1-M3);
  worktree-removed: C:\Claude Projects\mambo-power-m4 (junction removed FIRST via git-bash
  `rm`, per A5, then `git worktree remove --force`; main checkout's .bionic confirmed intact
  afterwards — 69 records, 7 ADRs); cleanup: done; tmp-wiped: .bionic/tmp emptied 2026-08-25;
  the same two junk files M3 had to clear (.playwright-cli/, bash.exe.stackdump) had
  reaccumulated in the main checkout and were removed before merging; tasks-completed: all 15
  ledger rows done, none active (m4-r2-fold's row corrected to record its split authorship)
- Step 9: deploy: none this wave — PyPI publish is M9 (deploy_target: pypi applies at M9, same
  as M1-M3); verified-at: CI run 32889587198 on 66ff908 (success, the exact tree merged,
  confirmed byte-identical) + Step-5 auditor record/m4-audit.md (CONFIRMED, wave + all 8 rows)
  + Step-6 record/m4-review-6axis.md and record/m4-critic.md, both folded in
  record/m4-r2-fold-report.md; monitor: GitHub Actions on every push to epic/01-foundation and
  wave/* (ci.yml); continuation: record/continuation-m4.md

## Slices

| Slice | Delivers | ACs | complexity | role |
|---|---|---|---|---|
| S1 domain-model | `Load.bid: LoadBid \| None` (`PolynomialBid`/`PiecewiseBid`, mirroring `GeneratorCost`); `Scenario` (`network: Network` embedded, no periods/strategy fields) | AC-3 (model half) | standard | implementor |
| S2 arrays | `NetworkArrays` per-load identity: `load_ids`/`load_bus`/`load_p_min_pu`/`load_p_max_pu`, mirroring the `gen_*` arrays | AC-3 (arrays half) | standard | implementor |
| S3 opf-extension | `opf/dc_opf.py`: optional demand-side LP columns + hypograph rows + balance/flow row extension; `OpfSolution.demand_dispatch_mw`/`demand_bound`; `NonConcaveBidError`; generator-side `c2 ≥ 0` convexity guard | AC-1, AC-2 | complex | senior-implementor |
| S4 market-nodal | `market/nodal.py:solve_nodal(scenario, options) -> MarketNodalResult`; settlement (payments, receipts, congestion rent); reuses `lmp_decomposition` verbatim | AC-4, AC-5 | complex | senior-implementor |
| S5 fixtures-oracle | `tests/_bids.py` (test-time-derived bid curves, mirrors `tests/_rated.py`); pandapower `sgen`-framed oracle parity test | AC-6 | standard | implementor |
| S6 jobs | `market.nodal` `KindSpec`; shared non-Optimal-status-to-structured-failure helper (factored out of `opf.dc`'s runner) | AC-7 | standard | implementor |
| S7 docs | Manual page (nodal-market), `docs/api/market.md`, one new example script + CI + snippet embed | AC-8 | complex | senior-implementor |

Order: S1 and S2 run in parallel (disjoint files: `model/entities.py`+new `model/scenario.py`
vs `numerics/arrays.py` — flag to both agents that they may both need to touch
`model/__init__.py`'s or `numerics/__init__.py`'s exports, mirroring the collision M3's S2/S4
hit on `results/__init__.py`; stage explicit paths, coordinate directly if both land near the
same time). S3 starts once S2 lands (needs the per-load array shape to build demand columns
against for real, though its own hand-built AC-1 test could in principle use an ad hoc array
— building against S2's real shape from the start avoids a rework). S4 starts once BOTH S1
(Scenario/Load.bid) and S3 (extended dc_opf) land. S5 and S6 both start once S4 lands
(disjoint: `tests/_bids.py` + a new parity test file vs `jobs/*.py`) and may run in parallel.
S7 last. Every slice RED → GREEN.

## Verification Matrix

stack-health: before (M3 close/epic merge, 5fa3285's own merge commit message): 596 tests;
after (Step 5, record/m4-step5-tests-floor.md): 646 (+50 — market module, Scenario/LoadBid
domain types, elastic-demand LP extension, market.nodal jobs kind, bid-derivation + oracle
tests), zero package-version drift from M3, ruff/format/mypy clean, mkdocs --strict 0
warnings, 9/9 examples, build+wheel/sdist smoke clean

walk-artifact: record/m4-walk-docs-site.md (docs-site walk in a real browser by an agent that
had not read the ACs) — real findings: home page stale in two directions (undersells M3 as
"in progress" when merged, silent on M4 existing at all — the same recurring gap M3's own
walk found and the R1 fold fixed, now stale again for this wave); internal wave-shorthand AND
a literal `record/m4-research.md §4.1` file-path citation leak into public docstrings and the
new example's own module docstring (worse than M3's single "wave M3 W5" instance — a path
into a document a published-package reader cannot open at all, not just cryptic jargon); the
Results manual page never mentions the new `MarketNodalResult` type. Positive: math rendering
is clean on the new manual page, confirming M3's R1 MathJax fix generalized. Unexplained but
almost certainly benign: a DOM query on the architecture page's mermaid diagrams reports them
empty while every screenshot shows them rendered correctly — flagged as a likely
browser-automation/CDP artifact, not a claimed site defect.

auditor-wave: CONFIRMED (record/m4-audit.md) — W1-W6 faithfully implemented and proven,
  including under an independent revert-and-watch demonstration; W7 meets AC-8's criterion but
  carries a non-blocking coverage hole (no numbered design decision) and documentation-substance
  gaps (home-page staleness, an internal file-path citation leaking into public docstrings) to
  close in this wave's R1 fold, not carried forward silently.

| AC | tier | status | evidence | auditor |
|---|---|---|---|---|
| AC-1 | T1 | done | see AC-1 | CONFIRMED (record/m4-audit.md) |
| AC-2 | T1 | done | see AC-2 | CONFIRMED (record/m4-audit.md) |
| AC-3 | T1 | done | see AC-3 | CONFIRMED (record/m4-audit.md) |
| AC-4 | T1 | done | see AC-4 | CONFIRMED (record/m4-audit.md) |
| AC-5 | T1 | done | see AC-5 | CONFIRMED (record/m4-audit.md) |
| AC-6 | T2 | done | see AC-6 | CONFIRMED, power narrowly located in the LMP sub-check (record/m4-audit.md) |
| AC-7 | T1 | done | see AC-7 | CONFIRMED (record/m4-audit.md) |
| AC-8 | T2 | done | see AC-8 | CONFIRMED (criterion); doc-substance gaps documented separately (record/m4-audit.md) |

AC-1:
  criterion: the extended dc_opf reproduces the hand-KKT-verified 2-bus welfare optimum
    (p1=20, p2=0, d=20, λ=10, μ_flow=-35, LMP(bus1)=10, LMP(bus2)=45) exactly
  provenance: wave spec W1; record/m4-research.md §4.1
  tier-run: `uv run --no-sync pytest -q tests/unit/test_opf_dc_demand.py` — 10 passed.
    test_ac1_two_bus_hand_kkt_welfare_optimum reproduces the network exactly (2-segment
    concave PWL demand bid, marginal value 45 on [0,50] / 20 on [50,100], 20 MW rated
    branch): dispatch_mw=[20,0] (g1,g2), demand_dispatch_mw=[20], balance dual=10.0,
    flow_limit dual=-35.0 (confirmed by direct interactive run, matches research exactly, no
    sign-convention fudging needed), LMP(b1)=10.0, LMP(b2)=45.0 via lmp_decomposition (M3's,
    reused verbatim). test_ac1_settlement_identity_holds_on_the_two_bus_case independently
    cross-checks via payments=900, receipts=200, rent=700 — matches research §4.1 exactly.
  readback: done 2026-08-24 (m4-s3-report.md, commit — see below). All values exact to
    1e-6, first implementation attempt, no adjustment needed against the research doc's
    hand-KKT numbers.
AC-2:
  criterion: NonConcaveBidError pre-solve on a non-concave bid; a c2<0 generator cost
    rejected by the new generator-side convexity guard
  provenance: wave spec W1; record/m4-research.md §1.2
  tier-run: same file — test_nonconcavebiderror_on_increasing_pwl_segment_slope (PWL bid,
    slopes 20 then 25, increasing -> NonConcaveBidError),
    test_nonconcavebiderror_on_positive_v2_polynomial_bid (quadratic bid, v2=0.5>0 ->
    NonConcaveBidError), test_nonconvexcosterror_on_negative_c2_generator_cost (c2=-0.1 ->
    NonConvexCostError, the generator-side guard closing the research-flagged asymmetry,
    same commit per spec Design item 1), test_positive_c2_generator_cost_is_unaffected_by_the_new_guard
    (c2=0.1 valid, solves fine — guard doesn't misfire on legitimate convex costs). All
    raised before any HiGHS object exists, per both errors' own docstrings.
  readback: done 2026-08-24, same commit as AC-1.
AC-3:
  criterion: Load.bid/Scenario/NetworkArrays per-load identity round-trip through JSON and
    construction; a dangling reference inside a Scenario is caught the same way Network's own
    validation catches one
  provenance: wave spec W2, W3
  tier-run: S2 (arrays half only — model half is S1's, still in progress): `uv run --no-sync
    pytest -q tests/unit/test_numerics_arrays.py` — 16 passed. load_ids/load_bus correctly
    identify each load/bus position; load_p_min_pu=0, load_p_max_pu=p_mw/base_mva per load
    (every load bounded [0, its own historical demand]); p_load_pu/q_load_pu aggregate
    proven byte-identical before/after on every fixture.
  readback: S2 done 2026-08-24 (m4-s2-report.md, commit f1dfa9b — completed by the
    orchestrator: agent finished the work but went idle before committing/reporting;
    verified independently before landing, no changes made to its work). S1 also done
    2026-08-24 (m4-s1-report.md, commit 6578709, same non-response pattern — orchestrator
    verified and landed): LoadBid/Load.bid/Scenario round-trip; a dangling ref inside a
    Scenario is caught via Network's own nested validator, proven not assumed. AC-3 fully
    discharged (both halves). 617/617 full suite green.
  readback: (filled at Step 4)
AC-4:
  criterion: on real multi-bus fixtures with derived bids, the settlement identity
    Σ_d LMP(bus_d)·p_d - Σ_g LMP(bus_g)·p_g = -Σ_k μ_k·flow_k holds exactly
  provenance: wave spec W4; record/m4-research.md §4.1
  tier-run: `uv run --no-sync pytest -q tests/unit/test_market_nodal.py` — 3 passed.
    test_ac4_settlement_identity_holds_on_a_binding_flow_limit_network reuses the exact
    two-bus network m4-research.md §4.1/S3's AC-1 test hand-derive (now built through
    Generator.cost/Load.bid/Scenario, exercising solve_nodal's own extraction, not dc_opf
    directly): dispatch g1=20/g2=0/d1=20, LMP(b1)=10/LMP(b2)=45, solve_nodal's own
    total_load_payment=900/total_generator_receipts=200/congestion_rent=700 (the identity's
    left side, computed from dispatch+LMPs) match a fully independent right-side computation
    in the test itself (-Σμ_k·flow_k, built via a direct dc_opf() call and its own PTDF/duals,
    a different code path from solve_nodal's arithmetic) to 700.0 exactly — the identity is
    proved, not asserted by construction. test_ac4_dispatch_and_lmp_rows_are_id_keyed... confirms
    every generator/load/bus gets exactly one row, id-keyed.
  readback: done 2026-08-24 (m4-s4-report.md, commit ec4ba22). GREEN first attempt (one incorrect
    test assertion in a same-slice non-AC test fixed before commit — see report). 630/630 full
    suite green (627 + 3 new, reconciles exactly), ruff/ruff format/mypy clean.
AC-5:
  criterion: with every load's bid above every achievable price up to its fixed historical
    demand, market.nodal's dispatch/duals/LMPs equal plain opf.dc_opf's fixed-load result
  provenance: wave spec W4; record/m4-research.md §4.2
  tier-run: same file — test_ac5_price_taker_reduction_matches_plain_opf_dc_opf: d1's bid
    (constant marginal value 1000, exceeding both generators' marginal costs 10/50 at every
    quantity up to d1's own 100 MW fixed historical demand — the precise m4-research.md §4.2
    condition) pins d1 at exactly 100 MW; solve_nodal's generator dispatch, generator bound
    duals, bus LMPs and bus congestion components all match opf.solve_dc_opf called on the
    identical network with d1 fixed (bid=None) to 1e-6 — reduces exactly to M3's own
    already-oracle-proved opf.dc_opf parity, per the spec's own framing of this as the wave's
    main correctness test.
  readback: done 2026-08-24, same commit as AC-4.
AC-6:
  criterion: market.nodal matches pandapower's sgen-framed elastic-demand rundcopp within a
    tolerance measured and pinned at implementation, on at least one real fixture
  provenance: wave spec W6; record/m4-research.md §3.1
  fixture-fidelity: derived bid curves (tests/_bids.py) on already-verbatim MATPOWER fixtures;
    oracle uses the sgen framing this wave adopts as its permanent convention
  tier-run: `uv run --no-sync pytest -q tests/parity/test_market_nodal_vs_pandapower.py` — 5
    passed post-R2 (4 at Step 5). case14, all 11 loads bid via tests/_bids.py — ten by the
    default fleet-ceiling derivation described here, and (post-R2) load-9 by the
    baseline-bracketing interior rule; see the Precision note below. Fleet-ceiling rule (VOLL=10,000
    $/MWh, marginal value descending linearly to the fixture's own generation-fleet max marginal
    cost, 90 $/MWh at gen2's own p_max). Oracle: every load row dropped and replaced by a
    sign-flipped sgen (min_p_mw=-p_mw, max_p_mw=0, controllable=True) with
    cp1_eur_per_mw=v1/cp2_eur_per_mw2=-v2 (cost_sgen(p)=-value(-p)), rundcopp(trafo_model="pi").
    Measured worst-case residuals across all 11 loads: at Step 5, dispatch 7.14e-10 MW / LMP
    1.94e-5 $/MWh (DISPATCH_ABS_TOL_MW=1e-6, LMP_ABS_TOL=1e-3); post-R2, dispatch 1.006e-5 MW /
    LMP 1.797e-5 $/MWh with DISPATCH_ABS_TOL_MW re-pinned to 1e-3 — the dispatch figure is now
    set by the interior load's genuinely solved quantity rather than by a bound-pinned one, so
    the re-pin is a re-calibration to a harder measurement, not a loosening (~100x margin, the
    same discipline LMP_ABS_TOL already used). Every fleet-anchored bid load ends up fully
    price-taking (pinned at its own p_mw) — a proven mathematical consequence of the anchor rule (fleet_max_mc upper-
    bounds the achievable market price on any fixture), confirmed against pandapower's own
    engine, not just opf.dc_opf's own price-taker reduction (AC-5). tests/unit/test_bids.py (7
    passed at Step 5; 13 post-R2) proves tests/_bids.py's own guarantees directly: anchored to each load's own
    p_mw, genuinely concave (v2<0), non-trivial (>1000 $/MWh marginal-value swing), no mutation.
    Precision note (m4-audit.md §2/§3, revert-and-watch) — SUPERSEDED BY THE R2 FOLD, kept
    because the correction is the point. The audit found this AC's evidence non-uniform across
    its 4 sub-tests: because every derived bid on this fixture was fully price-taking (the anchor
    rule above), the three dispatch-quantity sub-checks could not distinguish correct dispatch
    from S3's double-counting bug — reverting that subtraction left all three GREEN, and AC-6's
    power rested entirely on the fourth, the LMP-parity sub-check (same revert: 1.94e-5 -> 2.485
    $/MWh, a >2400x blowout). The audit, the dispatch brief and the R1 fold all treated this as
    structural to the VOLL-anchor-rule fixture strategy. The Step-6 critic proved it was not
    (record/m4-critic.md Issue 1), and the R2 fold closed it (record/m4-r2-fold-report.md item
    D): one load (load-9) now carries tests/_bids.interior_bid_for_load's baseline-bracketing
    derivation instead of the fleet-ceiling one, so it clears strictly inside its own bound
    (20.0176 MW of 29.5, bound_dual 0) while the other ten stay fleet-anchored and price-taking.
    Re-measured revert-and-watch on the folded tree: with dc_opf's double-counting subtraction
    stubbed out, the worst dispatch residual goes from 1.006e-5 MW to 1.569 MW — ~1,570x over
    the pinned tolerance, where before it did not move at all. All four sub-checks now carry
    genuine power against that bug on the real oracle-cross-validated fixture.
  readback: done 2026-08-24 (m4-s5-report.md, commit 5442465, pushed). GREEN first attempt (no
    RED-phase surprises — the sgen sign-flip transformation was probed and pinned numerically in
    scratchpad before any test was written, per the wave's own research-then-implement
    discipline). 645/645 full suite green (630 S4 baseline + S6's df565c6 jobs tests + 11 new),
    ruff/ruff format clean, bare `uv run mypy` clean (src-only per pyproject, tests/ untouched by
    strict mode as established).
AC-7:
  criterion: jobs.run/run_json for market.nodal pure, JSON round-trip, never raises;
    infeasible welfare LP yields INFEASIBLE_LP not INTERNAL; jobs.KINDS lists exactly 5 kinds
  provenance: wave spec W5
  tier-run: `uv run --no-sync pytest -q tests/unit/test_jobs.py` — 36 passed. KINDS contract:
    `set(KINDS) == {pf.ac, pf.dc, opf.dc, n1, market.nodal}`, every spec's options/result models
    importable pydantic models, runner callable; `KINDS["market.nodal"].options_model is
    MarketNodalOptions` / `.result_model is MarketNodalResult`. Happy path: `run(SolveRequest(
    kind="market.nodal", network=case14))` — `status="ok"`, typed `MarketNodalResult`,
    `provenance == result.provenance` (case14's loads carry no bid, so this is AC-5's
    price-taker reduction exercised at the jobs boundary). Purity: parametrized across all 5
    kinds including `market.nodal`, two runs equal modulo timing. JSON round-trip: `market.nodal`
    added to the kind/result-type table, `SolveResult.model_validate_json(out.model_dump_json())
    == out` with `type(result) is MarketNodalResult`. Infeasible LP: the same hand-built
    contradictory-generator-bounds network (`_infeasible_net`, generator caps collapsed below
    load) routed through `market.nodal` gives `status="failed"`, `error.code == "INFEASIBLE_LP"`
    (not `INTERNAL`) — case14's loads carry no bid, so the welfare LP reduces to the identical
    fixed-load infeasibility `opf.dc` already proves. Shared-helper proof: a monkeypatch spy on
    `jobs.registry._translate_non_optimal_status` records `["opf.dc", "market.nodal"]` across
    both kinds' infeasible-LP runs — one function object, not two copies of the ~15-line
    translation.
  readback: done 2026-08-24 (m4-s6-report.md, commit df565c6, pushed). Request-shape decision:
    `SolveRequest` stays `network`-shaped (no `scenario` field added) — `Scenario` (S1) is
    genuinely just `network: Network` this wave, so `_run_market_nodal` wraps the incoming
    `Network` into `Scenario(network=net)` itself, trivially; every `Runner` keeps its one
    `(Network, options) -> result` shape. `_translate_non_optimal_status(kind, status, message)
    -> NoReturn` factored out of `_run_opf_dc` into `jobs/registry.py`, called by both `_run_opf_dc`
    and the new `_run_market_nodal` — genuinely shared, proved by the spy test above, not
    duplicated. Found and fixed one real regression this slice's own change caused:
    `examples/04_jobs_api.py` used `kind="market.nodal"` as its own "unknown kind" demo (the
    identical collision `test_unknown_kind_is_a_failed_result` had); both swapped to
    `"market.zonal"` (Not Doing per spec, genuinely still unregistered). 645/645 full suite
    green (569 before S3/S4 + S3's 10 + S4's 3 + S5's fixture/parity tests landed concurrently
    in the shared worktree + S6's own — reconciles with S5's concurrent commit, not audited here
    since S5 owns that count), ruff check/format clean, bare `uv run mypy` clean (43 source
    files). One known follow-up flagged for S7: `docs/manual/jobs.md`'s hand-written
    "market.nodal ... UNKNOWN_KIND" snippet and its literal output text are now stale (not
    exercised by any test, so this did not block GREEN) — S7's territory, not touched here.
AC-8:
  criterion: mkdocs build --strict exits 0 with the new manual + API pages; symbol-coverage
    test passes for market without modification; new example exits 0 in CI, snippet-embedded
  provenance: wave spec W7
  fixture-fidelity: the built site is the artifact, same as M2/M3's docs ACs
  tier-run: `uv run --no-sync mkdocs build --strict` — exit 0, "Documentation built in 28.11
    seconds" (only warning is Material's own MkDocs-2.0 deprecation notice, unrelated to this
    wave). `uv run --no-sync pytest -q tests/unit/test_api_docs_coverage.py` — 2 passed:
    test_every_public_symbol_is_reachable_from_an_api_page (docs/api/market.md's `:::
    mambo_power.market.nodal` directive covers solve_nodal/MarketNodalOptions) and
    test_walk_covers_every_shipped_package, which fails vacuously unless PACKAGES actually
    walks a package with submodules -- confirmed non-vacuous: "market" added to PACKAGES,
    pkgutil.iter_modules over mambo_power.market lists nodal.py, so the walk genuinely visits
    it, not merely asserts by omission. `uv run --no-sync pytest -q tests/unit/
    test_examples_run.py` — 11 passed, including test_example_runs_to_completion[09_nodal_market]
    and test_every_example_is_embedded_in_the_docs (examples/09_nodal_market.py embedded in
    docs/examples/index.md via `--8<--`).
  readback: `uv run python examples/09_nodal_market.py` printed directly (not just asserted
    exit 0): dispatch g1=30.000 MW, g2=0.000 MW (bound dual 5.000, uneconomic), load d0=10.000
    MW (fixed, no bid), load d1=20.000 MW (elastic, capped by the 20 MVA branch rating); LMP
    b1=10.000 (pure energy), LMP b2=45.000 (10.000 energy + 35.000 congestion); settlement
    payment 1000.00, receipts 300.00, congestion rent 700.00, identity holds True. Full repo
    suite: `uv run --no-sync pytest -q` — 646 passed (645 S6 baseline + 1 new parametrized
    example-run case), 10 warnings (pre-existing pandapower FutureWarning/RuntimeWarning
    noise, unrelated to this slice). `ruff check .` — all checks passed. `ruff format --check
    .` — 140 files formatted clean (ruff format also rewrote the plain ```python fence inside
    docs/manual/market.md's "Using it" section, matching opf.md's own precedent — not the
    `--8<--` snippet-embed form, so this is expected, not a regression). Bare `uv run mypy` —
    "Success: no issues found in 43 source files" (unchanged source-file count: this slice
    touched no `src/` files).
  R1-fold closure (record/m4-r1-fold-report.md): the two non-blocking W7 findings
    m4-audit.md §1/§5 raised are closed. Coverage hole — wave spec's Design section gained item
    8, naming the docs/manual/market.md + docs/api/market.md + architecture-diagram +
    examples/09_nodal_market.py deliverable, closing the "criterion with no design decision"
    gap the same way W1-W6 each already had one. Doc-substance — docs/index.md's status
    callout/where-to-go-next/roadmap now reflect M3 merged and M4 in progress with the market
    manual linked; the internal `record/m4-research.md` path citation and bare "wave M4 W#"
    shorthand are removed from every M4-authored public docstring the leak reached
    (market/nodal.py, market/__init__.py, results/market.py, model/scenario.py,
    numerics/arrays.py, jobs/registry.py, examples/09_nodal_market.py — the audit named the
    first three explicitly; the rest carried the identical defect and were in scope as M4's own
    new code, not the pre-existing M1-M3 files A6 covers); docs/manual/results.md now covers
    `MarketNodalResult`. Not a re-audit — the auditor-wave verdict and each row's `auditor`
    column above are unchanged, per the fold's own scope.

## Tasks

The wave's dispatched-unit ledger (M1-M3 titled this same section "Dispatch ledger"; renamed
here to the canonical `## Tasks` heading the evidence gate requires of an audited multi-agent
wave plan — same table, same rows, no content change). One row per dispatched unit, written at
dispatch and completed at execution-confirmation.

| id | role | unit | deliverable | status |
|---|---|---|---|---|
| m4-s1-domain-model | implementor | S1 domain-model: LoadBid + Load.bid + Scenario — progress .bionic/tmp/m4-s1-progress.md, cadence 10m, ~40-50 min | record/m4-s1-report.md + commit on wave/04-nodal-market | done (commit 6578709, pushed; 17/17 own tests, 617/617 full suite, ruff/mypy clean — non-response procedure: agent finished the work but went idle before committing/reporting; orchestrator verified and landed it as-is) |
| m4-s2-arrays | implementor | S2 arrays: NetworkArrays per-load identity — progress .bionic/tmp/m4-s2-progress.md, cadence 10m, ~40-50 min | record/m4-s2-report.md + commit on wave/04-nodal-market | done (commit f1dfa9b, pushed; 16/16 own tests, ruff/mypy clean — non-response procedure: agent finished the work but went idle before committing/reporting; orchestrator verified and landed it as-is) |
| m4-s3-opf-extension | senior-implementor | S3 opf-extension: elastic-demand LP columns/rows in dc_opf, NonConcaveBidError, generator c2>=0 guard — progress .bionic/tmp/m4-s3-progress.md, cadence 10m, ~90-120 min | record/m4-s3-report.md + commit on wave/04-nodal-market | done (commit 972d7f9, pushed; 10/10 own tests, 627/627 full suite, 68/68 existing opf/PWL/parity tests unaffected, ruff/mypy clean) |
| m4-s4-market-nodal | senior-implementor | S4 market-nodal: solve_nodal + MarketNodalResult + settlement — progress .bionic/tmp/m4-s4-progress.md, cadence 10m, ~75-100 min | record/m4-s4-report.md + commit on wave/04-nodal-market | done (commit ec4ba22, pushed; 3/3 own tests, 630/630 full suite, ruff/ruff format/mypy clean — AC-4's settlement identity and AC-5's price-taker reduction both proved GREEN first attempt) |
| m4-s5-fixtures-oracle | implementor | S5 fixtures-oracle: tests/_bids.py derivation + pandapower sgen oracle parity — progress .bionic/tmp/m4-s5-progress.md, cadence 10m, ~45-60 min | record/m4-s5-report.md + commit on wave/04-nodal-market | done (commit 5442465, pushed; 11/11 own tests (7 tests/_bids.py + 4 parity), 645/645 full suite green (reconciles with S6's df565c6 landing concurrently), ruff/ruff format clean, bare `uv run mypy` clean — VOLL=10,000 $/MWh, measured tolerances DISPATCH_ABS_TOL_MW=1e-6/LMP_ABS_TOL=1e-3) |
| m4-s6-jobs | implementor | S6 jobs: market.nodal KindSpec, shared status-translation helper — progress .bionic/tmp/m4-s6-progress.md, cadence 10m, ~45-60 min | record/m4-s6-report.md + commit on wave/04-nodal-market | done (commit df565c6, pushed; 36/36 own tests, 645/645 full suite green, ruff/mypy clean — request-shape decision: SolveRequest stays network-shaped, _run_market_nodal wraps Network into Scenario itself) |
| m4-s7-docs | senior-implementor | S7 docs: manual (market), API page, architecture diagram, example, jobs.md stale-snippet fix — progress .bionic/tmp/m4-s7-progress.md, cadence 10m, ~60-75 min | record/m4-s7-report.md + commit on wave/04-nodal-market | done (commit pending; docs/manual/market.md, docs/api/market.md, mkdocs.yml nav, docs/design/architecture.md diagram+ownership, examples/09_nodal_market.py + docs/examples/index.md registration, docs/manual/jobs.md stale-snippet fix, tests/unit/test_api_docs_coverage.py PACKAGES entry; 646/646 full suite, mkdocs build --strict exit 0, api-docs-coverage 2/2 non-vacuous, examples-run 11/11, ruff/ruff-format/mypy clean — last slice of the wave) |
| m4-review-6axis | code-reviewer | Step 6 stance 1: six-axis review of 5fa3285..f5e20d9 (correctness, readability, architecture + closure, security, performance, duplication vs ownership table) | record/m4-review-6axis.md | done (Correctness/Readability/Architecture/Security/Performance PASS — Security confirmed PiecewiseBid.points already carries M3's max_length=200; Performance confirmed market.solve_nodal doesn't repeat M3's double-PTDF bug; Duplication FLAG — market/nodal.py's _gen_cost_coeffs is a byte-for-byte duplicate of opf's _cost_coeffs, disclosed but not architecturally justified; 2 correctness flags closed in-review via direct probe) |
| m4-critic | critic | Step 6 stance 2: adversarial critic over spec + plan + diff + audit; ~45-60 min | record/m4-critic.md | done (ready-to-merge verdict; found and PROVED a cheap fix exists for AC-6's power gap the audit+fold both accepted as unfixable without checking — case14's VOLL anchor floors every bid above the baseline clearing price, anchoring one load below it instead gives a real interior dispatch with a reproducible double-counting-detectable delta; re-verified R1's scope widening, S5's delayed-message case, elastic-demand cost, and Load.bid placement, all sound) |
| m4-r2-fold | senior-implementor | R2 fold: shared cost-coeffs helper, 3+-segment bid test, partial-bid docs, AC-6 real power on all 4 sub-checks — progress .bionic/tmp/m4-r2-progress.md, cadence 10m, ~60-75 min | record/m4-r2-fold-report.md + commit on wave/04-nodal-market | done, split authorship (record/m4-r2-fold-report.md) — agent landed items A/B/C **uncommitted** then went idle across the 2026-08-24/25 session boundary; non-response procedure applied 2026-08-25 (writing agent, never resumed): orchestrator examined .bionic/tmp/m4-r2-progress.md + git diff, independently re-verified A/B/C on the full suite (647/647) before building on them, took over item D itself, stood the agent down. Item D's own revert-and-watch: dispatch residual 7.14e-10 MW -> 1.569 MW with dc_opf's subtraction stubbed (~1,570x over tolerance), src restored byte-identical. 654/654 full suite, ruff/format/mypy clean, mkdocs --strict exit 0, 9/9 examples, build+smoke clean |
| m4-auditor | auditor | Step 5 exit gate: coverage / power / authenticity over spec + design + matrix + record; ≤3 re-executions; revert-and-watch via a fresh test-runner in a throwaway worktree | record/m4-audit.md | done (auditor-wave: CONFIRMED, all 8 AC rows CONFIRMED; 2 non-blocking caveats — W7 coverage hole, doc-substance leaks not extended M3's A6 precedent; revert-and-watch found AC-6's double-counting detection power is real but narrower than implied — only the LMP sub-check catches it on case14's fully price-taking bids, not raw dispatch) |
| m4-r1-fold | senior-implementor | R1 fold: W7 design decision, home page + docstring-leak fixes (M4-local only, not the 22-file convention), Results manual mention, AC-6 wording precision — progress .bionic/tmp/m4-r1-progress.md, cadence 10m, ~45-60 min | record/m4-r1-fold-report.md + commit on wave/04-nodal-market | done (commit f5e20d9, pushed, CI 32800006341 success; all 5 items closed; scope of item C disclosed-expanded from 3 to 7 files — same M4-new-code-only principle, just more instances found; 646/646 unchanged (doc-only fold), mkdocs --strict clean, orchestrator independently re-verified the leak grep and mkdocs build) |
| m4-floor | test-runner | Step 5 tests floor on aa53140: discovered suites (ruff, format, mypy, pytest tiers + full, mkdocs --strict, examples x9, build + wheel/sdist smoke, market timing), stack-health | record/m4-step5-tests-floor.md | done (all green: 646/646 tests, 0 stack drift from M3, mkdocs strict 0 warnings, 9/9 examples, build+smoke clean; case14 solve_nodal cold 0.0208s informational) |
| m4-walk | researcher | Step 5 walk: build + serve the docs site, drive it in a real browser (browser-verify), narrate what is seen — agent has NOT read the ACs | record/m4-walk-docs-site.md | done (real findings — home page stale in 2 directions (undersells M3, silent on M4); internal wave-shorthand AND a literal `record/m4-research.md` file-path citation leak into public docstrings/example, worse than M3's single "wave M3 W5" instance; Results manual page never mentions MarketNodalResult; math rendering clean this time, confirming M3's R1 MathJax fix held; unexplained but likely-benign mermaid DOM-vs-screenshot discrepancy, flagged not claimed as a bug; 25 screenshots in record/walk-m4/) |
| m4-research | researcher | Step 1/2: welfare-LP formulation, dc_opf extension shape, oracle strategy, settlement identities, fixture strategy, Scenario shape, jobs mechanics | record/m4-research.md | done (verified on disk; central finding: dc_opf could be reused unmodified via a pseudo-generator trick, but the design interview chose the cleaner Option B extension instead; settlement identity + price-taker reduction fully proved at research stage) |

## Assumptions

- A1 (spec assumption a): the VOLL figure and bid-curve anchor rule are pinned during
  implementation (S5), not fixed here — must produce a genuinely concave, non-trivial curve,
  not a degenerate linear step.
- A2 (spec assumption b, carry-over): pandapower's `load`-row quadratic-cost non-convergence
  is a real, reproduced bug (record/m4-research.md §3.1) — this wave routes around it via
  `sgen`, but the implementing slice should document it precisely in its own test file so a
  future reader (or a pandapower upgrade) doesn't have to rediscover it via `git log -S`.
- A3 (spec assumption c): the generator-side `c2 ≥ 0` convexity guard is a pre-existing gap
  this wave closes as a byproduct of building the bid-side mirror, not a new requirement of
  its own — log it as such, not as evidence M3 shipped incomplete.
- A4 (carry-over, inherited from M3): ~~PyPSA's infeasibility on plain generator-only OPF
  (record/m3-research.md §3.1) remains open~~ — **STALE, corrected 2026-08-25 by M5 Step 1
  research (record/m5-research.md §1).** A4 was already closed inside M3 itself: the root cause
  is `import_from_pypower_ppc` pinning `n.generators.p_set` to MATPOWER's unbalanced base-case
  Pg, and the fix ships in `tests/parity/test_opf_vs_pypsa.py` (commit 4bd67d9). This assumption
  read the frozen m3-research.md instead of the shipped code, and M4's own continuation then
  copied the error forward. Re-verified 2026-08-25: 20 passed on all five fixtures. M4's own
  statement that PyPSA is not an oracle for `market.nodal` stands on its own merits (no
  elastic-demand oracle need arose), but the *reason* given here was wrong.
- A5 (process note, from continuation-m3.md): worktree junction removal on this machine needs
  git-bash `rm`, not PowerShell/cmd `rmdir` (sandbox blocks the latter two on this path).
- A7 (M5 candidate, from record/m4-critic.md §3 — logged at Step 6, does not reshape this
  wave): case14 rates no branch (all 20 `Branch.rating_mva` are None, a carry-over of M3's
  fixture set per record/m3-research.md §6), so no fixture in this wave proves the settlement
  identity under *simultaneous* congestion and elastic demand against an independent oracle
  engine. AC-4 covers that interaction on a hand-built network against dc_opf's own PTDF/dual
  arithmetic, which is why this is disclosed rather than blocking. M5 inherits the same fixture
  set — worth rating one branch (the tests/_rated.py pattern already exists) before it
  reproduces the same conclusion without checking.
- A6 (process note, from continuation-m3.md): two Windows-path bugs in this session's global
  `~/.claude/hooks/*.sh` were found and fixed in M2/M3 (`dispatch-preflight.sh`,
  `canonical-sdlc-governing-skill.sh`) and held cleanly through M3's whole dispatch load; a
  third (`stop-guard.sh`, TaskStop-only, non-blocking) is known and left open.

## Handoff

Resume point (2026-08-24): Step 3 plan written, awaiting user approval.
Decisions ratified this session: triple, scope (2 answers), design interview (frame + 2
decisions + composition), spec + plan written.
Open blockers: none.
Resume instruction: on approval, `git worktree add C:\Claude Projects\mambo-power-m4 -b
wave/04-nodal-market epic/01-foundation`, junction `.bionic`, dispatch S1 and S2 in parallel
(flag the likely `__init__.py`-export collision to both upfront, per M3's own repeated
lesson).
