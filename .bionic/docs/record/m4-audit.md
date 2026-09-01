# M4 audit — nodal-market Step-5 exit gate

Independent auditor, read-only, worktree `C:\Claude Projects\mambo-power-m4` @ `aa53140`
(branch `wave/04-nodal-market`). No implementation, review, or prior audit role in this wave.
`git status --porcelain` empty before and after every step in this audit; no edits, commits,
or pushes made by this agent at any point (verified directly, see §6).

**auditor-wave: CONFIRMED, with two named non-blocking caveats** — W1-W6's requirements are
faithfully implemented and proven at the tier claimed; W7 (documentation) satisfies AC-8's
literal criterion but has real, verified substance gaps (home-page staleness, an internal
file-path citation leaking into public docstrings) that should be fixed in this wave's R1
fold, not carried forward silently. One narrow, disclosed AC-6 power gap (dispatch-quantity
parity is a weak witness to the double-counting bug on this specific fixture; LMP parity is
the check that actually carries power) does not change the verdict, since the LMP sub-check
is present, cited, and its power was independently confirmed by re-execution and by the
revert-and-watch demonstration below.

## 1. Coverage — requirement → design decision → criterion → evidence

Inverting the spec's own `provenance:` citations against the Design section's seven numbered
items:

| Req | Design decision | AC(s) | Verdict |
|---|---|---|---|
| W1 (elastic-demand DC-OPF) | Design item 1 | AC-1, AC-2 | covered |
| W2 (`Load.bid`, `Scenario`) | Design items 2, 3 | AC-3 | covered |
| W3 (`NetworkArrays` per-load) | Design item 4 | AC-3 | covered |
| W4 (`market.nodal`) | Design item 5 | AC-4, AC-5 | covered |
| W5 (Jobs API) | Design item 6 | AC-7 | covered |
| W6 (oracle & fixtures) | Design item 7 | AC-6 | covered |
| W7 (documentation) | **none** | AC-8 | **hole — no numbered design decision** |

**Wave-level coverage finding (not blocking, but a genuine hole, not a nitpick):** the spec's
Design section (lines 151-224) numbers exactly seven decisions, one each for W1-W6; W7 gets no
corresponding design item. W7 is answered by a criterion (AC-8) and by real, substantial
implementation (S7's slice, `docs/manual/market.md`, `docs/api/market.md`, the architecture
diagram, the new example) — but never by a named *design decision* the way W1-W6 each are. Per
the audit mandate, criteria-with-no-design-decision is a hole in the chain, not a covered
requirement, regardless of how much work actually shipped against it. Practically low-stakes
(documentation work doesn't carry the same kind of architectural risk a numbered LP-encoding
or ownership decision does), but it is a real, mechanically-detectable gap the spec/plan should
close by either adding an eighth design item for W7 or explicitly noting documentation is
criterion-only by convention — not silently left implicit, which is what happened here and in
M2/M3 before it (not re-audited, but the same shape recurs).

Every other requirement (W1-W6) has both an inbound design-item citation and an inbound
AC citation — no other holes found.

## 2. Power — per-AC, plus the revert-and-watch demonstration

For each AC: what would the cited observation have shown had the wave's change been absent?

- **AC-1** (T1, hand-KKT 2-bus): powerful. A wrong LP encoding (e.g. sign error, missing
  hypograph row) would produce different dispatch/dual numbers, not the same ones — confirmed
  directly by the revert-and-watch demonstration (§3): stubbing the double-counting
  subtraction, a real change inside the exact code path this AC exercises, turned this test
  RED with a different, wrong dispatch (`[20, 80]` instead of `[20, 0]`).
- **AC-2** (T1, error-raising): powerful in the trivial sense (absence of the guard ⇒ no error
  raised, tests would fail on the `pytest.raises` context manager itself) — confirmed
  unaffected by the revert-and-watch stub, exactly as predicted (the guards run before the
  stubbed code).
- **AC-3** (T1, round-trip + dangling-ref): powerful. Read `test_scenario_with_dangling_ref_network_is_rejected_at_construction`/`..._via_json_is_rejected` directly
  (`tests/unit/test_load_bid_scenario.py:159-182`) — both genuinely construct a `Scenario`
  wrapping a `Network` with an out-of-range bus reference and assert a `DANGLING_REF`-coded
  failure, not a vacuous "doesn't crash" check.
- **AC-4** (T1, settlement identity): powerful, and non-circular by construction — the test's
  own right-hand side is computed via a **separate** `dc_opf()` call and independent PTDF/duals
  arithmetic, not `solve_nodal`'s own numbers restated. Confirmed to have real teeth by the
  revert-and-watch demonstration: went RED under the double-counting stub with clearly wrong
  numbers (`by_gen["g2"]` observed `80.0` against an expected `0.0`).
- **AC-5** (T1, price-taker reduction): powerful — confirmed empirically, not just by
  inspection, via the revert-and-watch demonstration. This was worth independently checking:
  the request flagged AC-5 as a case where the bug *might* be masked (a load pinned at its own
  fixed `p_mw` could, in principle, land there whether or not the RHS was double-counted). On
  this wave's actual two-bus network it did **not** mask — the stub turned AC-5 RED too (`d1`
  dispatched to `20.0` MW instead of the correct `100.0`), because the branch's flow limit
  (not the bid) is what's actually binding here, so the corrupted balance RHS changes the
  answer materially. AC-5 genuinely discharges.
- **AC-6** (T2, pandapower `sgen` parity): **has power, but narrowly** — this is the one place
  the revert-and-watch demonstration surfaced something the static review would not have
  caught. Predicted all 4 parity tests RED under the stub; actual was only 1 of 4 (the LMP
  comparison). The other three (`converges_optimal`, `dispatch_matches_the_sgen_oracle`,
  `every_bid_load_is_fully_price_taking`) stayed GREEN, because S5's own documented
  "every derived bid on case14 ends up fully price-taking" property (its own report, §"A
  proven, documented mathematical consequence of the anchor rule") means every one of case14's
  11 loads lands at exactly its own fixed `p_mw` in *both* the correct and the double-counted
  formulation — so raw dispatch quantities can't distinguish the two. LMPs can, and do: the
  double-counted RHS inflates required flow, and the LMP-parity test's worst-case residual
  jumped from a measured `1.94e-5 $/MWh` (the real evidence's own pinned tolerance headroom) to
  an actual `2.485 $/MWh` against a `1e-3` tolerance under the stub — a >2400x blowout,
  unambiguous. **Conclusion: AC-6 discharges, but its power rests entirely on the LMP
  sub-check; the dispatch-quantity sub-checks are decorative on this fixture, not because
  they're badly written, but because case14's own bid anchor rule (verified in §1's audit of
  S5) makes every load's raw dispatch quantity insensitive to this class of bug.** This is a
  disclosed, narrow finding, not a discharge failure — the LMP sub-check is present, cited in
  the plan's own tier-run block ("LMP 1.94e-5 $/MWh"), and independently re-executed by this
  audit (§4) with the same result before the stub was ever applied.
- **AC-7** (T1, jobs boundary): powerful — `test_opf_dc_and_market_nodal_share_the_same_status_translation_function`
  (read directly, `tests/unit/test_jobs.py:427-445`) is a genuine non-circular proof (a
  monkeypatch spy on the actual shared function object, not an assertion that two code blocks
  look similar); `test_infeasible_market_nodal_is_infeasible_lp_not_internal` constructs a real
  contradictory-bounds network and checks the specific failure code, not just "an error
  happened."
- **AC-8** (T2, docs build): the criterion itself (`mkdocs --strict` exit 0, coverage test,
  example exit 0) is powerful in the narrow sense that a real build break, a missing API entry,
  or an example regression would fail it — and it did catch one real regression this wave
  (S6's `examples/04_jobs_api.py` collision, per its own report). It is not powerful with
  respect to documentation *substance* — see §5.

### 3. Revert-and-watch demonstration

Change reverted/stubbed: `src/mambo_power/opf/dc_opf.py`'s double-counting subtraction inside
`dc_opf()` (S3's own central design decision — the `if n_demand: ... p_load_mw = p_load_mw -
np.bincount(...)` block). Performed by a dedicated test-runner agent in a throwaway, detached
worktree (`C:\Claude Projects\mambo-power-audit4`, created from and later confirmed
byte-identical to `aa53140`), per the request file `.bionic/tmp/m4-audit-revert-request.md`;
full output in `.bionic/tmp/m4-audit-revert-result.md`. This auditor did not revert, stub, or
run anything itself — validated the executor's capture only.

**Predicted RED, confirmed RED**: `test_mixed_elastic_and_inelastic_load_no_double_counting`
(the primary target — actual dispatch `130.0 MW` against expected `80.0 MW`, exactly the
predicted double-counting blowout), both AC-1 tests, the PWL-demand-breakpoint test, both AC-4
tests. **Predicted GREEN, confirmed GREEN**: all four AC-2 guard tests, the backward-
compatibility test, and the full sampled pre-M4-adjacent suite (46 tests across
`test_opf_dc.py`/`test_opf_dc_pwl.py`/`test_jobs.py`). **Flagged as genuinely ambiguous,
resolved empirically**: AC-5 (resolved RED, confirmed the check has power — see §2). **One
real prediction miss, disclosed rather than buried**: 3 of 4 AC-6 parity tests were predicted
RED and stayed GREEN, for the documented fixture-degeneracy reason in §2. The stub was cleanly
reverted (`git status --porcelain` and `git diff aa53140 --stat` both empty afterward) and the
throwaway worktree removed; `mambo-power-m4` was confirmed never touched throughout (its
`git worktree list` entry stayed at `aa53140` unmoved).

This is exactly the kind of finding the demonstration exists to surface: a prediction miss that
reveals a real, narrow, previously-undocumented characteristic of AC-6's evidence (its power
comes from LMPs, not dispatch quantities, on this fixture) rather than a defect that changes
the wave's overall correctness — the LMP channel was already present and already cited.

## 4. Authenticity — re-execution (T1 and T2, 3 of 3 budget used)

| Command (tier) | Reported | Re-executed | Match |
|---|---|---|---|
| `pytest -q tests/unit/test_opf_dc_demand.py` (T1, AC-1/AC-2) | 10 passed | **10 passed** | Yes |
| `pytest -q tests/unit/test_market_nodal.py` (T1, AC-4/AC-5) | 3 passed | **3 passed** | Yes |
| `pytest -q tests/parity/test_market_nodal_vs_pandapower.py` (T2, AC-6) | 4 passed | **4 passed** | Yes |

All three re-executions matched the reported pass counts exactly, on the real repo state
(`aa53140`), before any revert-and-watch stubbing — a genuine cold re-run, not a rerun against
a warm/cached result (the worktree's `.venv`, not a fresh one, but no source files were
modified between the slice's own run and this audit's re-execution — `git status --porcelain`
confirmed clean throughout, see §6).

AC-6 (T2) carries the required fixture-fidelity declaration (`tests/parity/
test_market_nodal_vs_pandapower.py`'s own docstring plus `tests/_bids.py`'s module docstring)
and the fixture is structurally able to reach the failure the AC guards — confirmed
independently by the revert-and-watch demonstration reaching a real (if narrower than
predicted) failure through it, not merely asserted by the fixture author.

### Specific scrutiny items

- **S3's double-counting contract**: read `dc_opf.py:115-127` (module docstring) and the actual
  implementation (`dc_opf.py:490-499`) directly — the subtraction reads `arr.load_p_max_pu[idx]`
  (not a caller-supplied value) and removes it from `arr.p_load_pu`'s aggregate at the load's
  own bus, exactly as both the module docstring and S3's report describe. `test_mixed_elastic_and_inelastic_load_no_double_counting`
  (read at `test_opf_dc_demand.py:210-227`) is real, not decorative, and the revert-and-watch
  demonstration proves it has power (§3). **Confirmed**, not merely plausible.
- **AC-1's exactness claim**: re-executed (§4 above) — the current test still passes with the
  exact hand-KKT numbers the report claims (`10 passed`, and `test_ac1_two_bus_hand_kkt_welfare_optimum`
  reads the literal `10.0`/`45.0`/`-35.0` assertions directly, `test_opf_dc_demand.py:75-97`).
  This audit cannot independently verify the *historical* claim ("first implementation attempt,
  no adjustment needed") — that is a claim about process, not a re-checkable fact — but the
  claim about the numbers being exactly research-predicted is re-confirmed on the current code.
- **AC-5's price-taker bid construction**: read `test_market_nodal.py:143-178` directly. The
  bid is `PolynomialBid(coefficients=[1000.0, 0.0])`, which `_load_bid_coeffs`
  (`market/nodal.py:107-109`) maps to `v2=0, v1=1000.0` — a **constant** marginal value of
  $1000/MWh at every quantity. The research's precise condition (§4.2: marginal value exceeds
  every achievable price at every quantity up to the load's fixed historical demand) requires
  exceeding the highest generator's marginal cost at its own `p_max` (here, `g2`'s constant
  $50/MWh) for every `p` in `[0, 100]`. A flat $1000 constant satisfies this everywhere,
  trivially and correctly — not a weaker, coincidentally-passing approximation, but a genuine
  (if extreme, unconditionally-satisfying) instance of the stated class. **Confirmed**.
- **S5's fixture-strategy finding and the AC-6 power question**: worked this out independently
  rather than accepting either framing in the dispatch brief at face value. Read `tests/_bids.py`
  directly (`bid_for_load`, `fleet_max_marginal_cost`) — the anchor rule genuinely guarantees
  every derived bid's low end is an upper bound on the achievable market price, so every
  fixture-derived bid load is provably always price-taking; this is confirmed both
  algebraically (source read) and empirically (revert-and-watch, §2/§3 — dispatch quantities
  really are insensitive to the double-counting bug on this fixture). Then checked whether
  AC-4's separate hand-built network actually covers the case AC-6 structurally cannot: yes —
  `test_ac4_dispatch_and_lmp_rows_are_id_keyed_and_cover_every_generator_and_load`
  (`test_market_nodal.py:137`) asserts `d1.bound_dual == 0.0`, i.e. `d1` sits at an *interior*
  point of its own bid bound (20 of 100 MW), genuinely price- **and** flow-constrained jointly —
  the case AC-6's fixture cannot produce. **This is a real power gap in AC-6 specifically
  (confirmed, not merely a paper distinction — see §2/§3), fully compensated by AC-4's
  independent hand-built network, and not a gap in the wave's overall correctness proof.**
- **S6's `Scenario`-wrapping decision**: read `model/scenario.py` directly — `Scenario` is
  genuinely `network: Network` and nothing else this wave (no hidden fields to lose). Read
  `jobs/registry.py:126-136`'s `_run_market_nodal` — it wraps `Scenario(network=net)` with no
  other transformation. Nothing is silently lost or misrouted; **confirmed**, not taken on
  S1's word alone.
- **The non-response procedure trail (S1, S2)**: `git show --stat 6578709` lists exactly the
  6 files `m4-s1-report.md` claims (`model/__init__.py`, `model/entities.py`, `model/network.py`,
  `model/scenario.py`, the schema snapshot, the new test file); `git show --stat f1dfa9b` lists
  exactly the 2 files `m4-s2-report.md` claims (`numerics/arrays.py`, the new test file). Both
  **confirmed** — no discrepancy between the landed commit and its report.

## 5. Documentation substance (W7) — factored into the wave-level verdict, not AC-8's cell

AC-8's literal criterion is met (re-confirmed by reading the reports and by the grep evidence
below, not re-run — within this audit's tier budget). But the walk's three real findings
(`m4-walk-docs-site.md`) were independently re-verified, not waved through:

- **Home page staleness, confirmed by direct read**: `docs/index.md:20-21` still reads "Wave
  **M3** ... is in progress"; `docs/index.md:105-106`'s roadmap table still lists M3 as "in
  progress" and "M4-M7 ... Markets: nodal LMP..." as **"planned"** — while the site being built
  from this exact commit has a full, live nodal-market manual page, API reference, and example.
  This is the same recurring gap M3's own walk found and M3's R1 fold fixed (per the plan's own
  handoff notes) — now stale again for M4. Confirmed exactly as the walk described.
- **Internal file-path citation leak, confirmed by direct grep — and this one deserves more
  weight than M3's precedent, per the audit's own brief**: `record/m4-research.md §4.1` appears
  **verbatim** in `src/mambo_power/market/nodal.py`'s module docstring (line 8) and in an
  inline comment (line 199), and in `examples/09_nodal_market.py`'s module docstring (lines 6
  and 77) — the latter is directly embedded in the public Examples page (confirmed by S7's own
  report and the walk). `"wave M4 W4"` also appears three times across
  `market/__init__.py`/`market/nodal.py`'s public docstrings. A published-package reader has no
  filesystem access to `record/m4-research.md` at all — this is categorically different from
  M3's single "wave M3 W5" instance, which M2/M3's own audit (Assumption A6) correctly ruled a
  harmless, established house shorthand convention (a bare identifier, resolvable in context as
  jargon even if unfamiliar). A literal path into a document that does not exist in the
  installed package is not the same class of finding, and this audit does **not** extend A6's
  precedent to it.
- **`MarketNodalResult` absent from the Results manual page, confirmed by direct grep**:
  `docs/manual/results.md` mentions `market` exactly once, in a generic enum-value list
  (`"market.*"`), never `MarketNodalResult` by name. A reader who goes to "Manual → Results"
  specifically to see what result shapes the package returns would not learn this one exists.

**Judgment**: W7's documentation requirement is met in letter (AC-8's criterion, machine-
checked, passes) but not fully in substance — a real reader following the site's own internal
consistency (home page → roadmap → nav) would be actively misled about what's shipped, and a
reader of the published API docs is handed a citation they cannot resolve. None of this
invalidates the technical correctness proven by AC-1 through AC-7; it is a documentation-
process finding that belongs in this wave's R1 fold, the same place M3's equivalent staleness
finding was fixed last time.

## 6. Read-only compliance

`git status --porcelain` on `mambo-power-m4` returned empty before this audit began, after the
three re-executions in §4 (no source files touched by a `pytest` run), and after the
revert-and-watch demonstration (performed entirely in a separate, throwaway worktree never
`cd`'d into from this audit — confirmed in the executor's own report, §5 of
`m4-audit-revert-result.md`). No file in `mambo-power-m4` was edited, committed, or pushed by
this audit at any point.

## Row verdicts

| AC | tier | auditor verdict | basis |
|---|---|---|---|
| AC-1 | T1 | **CONFIRMED** | re-executed (10/10); revert-and-watch turned it RED with wrong numbers; hand-KKT numbers re-verified in source |
| AC-2 | T1 | **CONFIRMED** | re-executed; guards fire pre-solve, confirmed unaffected by the stub (predicted GREEN, actual GREEN) |
| AC-3 | T1 | **CONFIRMED** | dangling-ref tests read directly, genuinely check `DANGLING_REF`; S1/S2 commits match reports exactly |
| AC-4 | T1 | **CONFIRMED** | re-executed (3/3); non-circular (independent RHS computation); revert-and-watch turned it RED with wrong numbers |
| AC-5 | T1 | **CONFIRMED** | bid construction matches the research's precise condition exactly; revert-and-watch confirmed real power (resolved RED, not masked) |
| AC-6 | T2 | **CONFIRMED, power narrowly located** | re-executed (4/4); fixture-fidelity declaration present and structurally sound; revert-and-watch confirms power resides in the LMP sub-check specifically (§2/§3), not the dispatch-quantity sub-checks — disclosed, not a discharge failure |
| AC-7 | T1 | **CONFIRMED** | shared-helper spy test and infeasible-LP test read directly, both genuine (non-circular) proofs |
| AC-8 | T2 | **CONFIRMED (criterion); substance gaps documented separately (§5)** | criterion machine-checked and met; documentation substance findings factored into the wave-level verdict, not this cell |

**Wave-level coverage verdict: HOLE (non-blocking)** — W7 has no numbered design decision in
the spec's Design section, unlike every other requirement (§1).

**auditor-wave: CONFIRMED.** The wave's core technical claims (elastic-demand LP extension,
settlement identity, price-taker reduction, oracle parity, jobs integration) are faithfully
implemented and genuinely proven, including under an independent revert-and-watch
demonstration that surfaced one real, narrow, disclosed refinement to how AC-6's evidence
actually carries power (§2) rather than any defect in the wave's correctness. Two non-blocking
findings should be closed in this wave's R1 fold rather than carried forward silently: W7's
missing design-decision citation (§1) and W7's documentation-substance gaps (§5, especially the
internal file-path leak, which is a more serious class of finding than M3's precedent and
should not be waved through on that precedent alone).
