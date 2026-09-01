# M6 audit — Step 5 exit gate

Wave M6 (`zonal-redispatch`), branch `wave/06-zonal-redispatch`, head `d0ce957`, worktree
`C:\Claude Projects\mambo-power-m6`. Independent auditor. Read-only on the live worktree
(`git status --short` empty before and after; verified).

**Mandate:** falsify the claim that M6's requirements were faithfully implemented *and proven*.
Three levels — coverage, power, authenticity.

**Budget used:** 3 of 3 evidence re-executions (AC-4 T1, AC-6 T2, AC-3 T1). One revert-and-watch
demonstration in a detached scratch worktree, restored and removed. Two read-only measurements
(`jobs.KINDS`; the AC-5(b) figures).

**Reporting contract:** every factual claim below either carries its command and output, or is
explicitly labelled *(from the record)* / *(source-read)* / *(unverified)*.

---

## Verdicts

| AC | verdict | one-line reason |
|---|---|---|
| AC-1 | **CONFIRMED** | Overlay-tree + tripwire + three helper sabotages red on both surfaces; one disclosed guard-ordering divergence remains untested *(from the record)* |
| AC-2 | **CONFIRMED** | Oracle is genuinely external — hand KKT plus `scipy.optimize.linprog` with the dual sign convention verified by perturbation, derived before `opf.zonal` existed *(source-read)* |
| AC-3 | **CONFIRMED** | Re-executed, 4 passed; **and I proved its power myself** — stubbing the redispatch stage drives the chain readback red at 21.6 MW of overload |
| AC-4 | **CONFIRMED** (primal) · **UNVERIFIABLE** (case300 LMP clause) | Re-executed, 11 passed; the D1 theorem's primal half is strongly proven, but A20's substituted case300 clause is complementary slackness on one LP's own rows — any optimal solve passes it |
| AC-5 | **CONFIRMED** (a)(c) · **letter-only** (b) | (a) and (c) are strong; (b)'s "three distinct fields" are measurably **two** — on fixed-load case30 `generation_cost_gap` is exactly `−redispatch_payment` (sum = −2.6e-11) |
| AC-6 | **CONFIRMED** | Re-executed, 43 passed / 4 skipped incl. skip reasons; oracle verified held fixed **at source**, negative control genuinely hands one swapped fixture to both sides |
| AC-7 | **CONFIRMED** | `len(jobs.KINDS) == 7` verified live, `market.zonal` present; registry pin RED-before / GREEN-after is a real paired readback *(from the record)* |
| AC-8 | **CONFIRMED** against its criterion | Criterion is knowingly weak (build ≠ render); the independent walk is the compensating control and it worked *(build not re-executed — budget)* |

### Wave verdict: **CONFIRMED WITH FINDINGS**

The wave's central claim — D1's theorem, that the redispatched point *is* the nodal optimum — is
genuinely proven on its primal side, and I demonstrated its power myself rather than agreeing with
the report. The verification is well above the repo's usual standard: external oracles derived
before the code existed, sabotage sweeps naming the residual that moves, a committed negative
control for what parity cannot catch, and an independent walk run before any row was marked.

Three findings stop this being a clean confirmation. One is a hole in the requirement→design chain
(**F1**, wave-level). Two are rows discharged in letter while the substance went unproven (**F2**
on AC-4's case300 prices, **F3** on AC-5(b)). None is a correctness defect in the shipped code;
all three are defects in the *proof*.

---

## Level 1 — Coverage: requirement → design decision → criterion → evidence

Seeded mechanically by inverting the `## Design` section's `Serves W…` markers, the ownership
table, and the `provenance:` citations. (Note the `provenance:` lines cite *sources* — ADR-008,
the design interview, research sections — not W-numbers, so the design section's own markers carry
the inversion.)

| requirement | design decision(s) | criterion | chain |
|---|---|---|---|
| W1 preamble unification | `dc_opf._extract_and_validate` (*Serves W1*); ownership row 1 | AC-1 | whole |
| W2 zonal LP | `opf.zonal.zonal_dc_opf` (*Serves W2*); ownership row 2 (zone price) | AC-2, AC-6 | whole |
| W3 redispatch LP | `opf.redispatch.redispatch_dc_opf` (*Serves W3*) | AC-3, AC-4 | whole |
| W4 `market.solve_zonal` | `market.zonal.solve_zonal` + `results.zonal` (*Serves W4/W5*) | AC-5, AC-4 | whole |
| W5 invariants | same, plus ownership row 3 (final dispatch == nodal, D1 theorem) | AC-3(a), AC-4(b), AC-5(c) | whole |
| W6 jobs | `jobs` KINDS entry (*Serves W6*); ownership row 5 | AC-7 | whole |
| W7 fixtures + oracle | Domain-model paragraph (`tests/_zones.py`), **unmarked**; ownership row 4 | AC-6 | weak link |
| W8 docs | **none** | AC-8 | **hole** |

### F1 — W8 has zero inbound design decisions, and the hole is demonstrated, not theoretical (wave-level, HIGH)

`## Design` covers component boundaries, an ownership table, rejected alternatives and five
assumptions. Nothing in any of them concerns documentation. W8 is answered by a criterion (AC-8)
and by no design decision at all.

That would be forgivable — docs are a standing epic requirement (R14), not usually a design
question — except that this wave produced the exact defect a W8 design decision would have owned.
Walk defect D2 / A29 W2: `MarketZonalResult`'s field names are **published nowhere**. `api/results`
renders zero field entries for every pydantic result model site-wide; `delta_restore_mw` and
`delta_curtail_mw` occur zero times in the built site; the walker followed the manual's netting
section and hit an `AttributeError`. M6 is the first wave whose result type a reader must construct
*from*, so the gap became load-bearing here.

AC-8's four clauses are `mkdocs build --strict` exit 0, the coverage test unmodified, the example
exit 0 and snippet-embedded, and a changelog entry. **Not one of them can detect an unrendered
field list.** The criterion certifies the build; the question "where do result-model field names
reach the reader?" is a design question that was never asked, so no criterion was written to answer
it. The matrix's own AC-8 tier-rationale names the limit ("build ≠ render") and correctly routes
around it with the independent walk — which is why the defect was caught at all. But that is a
compensating control substituting for a missing link in the chain, not the chain being whole.

*Disposition:* the fold already carries it (A29 fold item (d)). The finding is that the chain, not
the fold, is what needs the repair — M7's spec should carry a design decision for the docs surface
so its AC-8 equivalent can be written against something.

### W7 is a weak link, not a hole

W7's fixture half is served by the Domain-model paragraph (`promote_areas_to_zones`, `corridors`)
and ownership row 4, neither of which carries a `Serves W7` marker but both of which are real
design decisions. W7's *oracle* half — "PyPSA multi-zone parity with the partition and caps handed
to the oracle independently" — rests on spec **A1**, which is an assumption the spec itself flags
as unproven and at-risk, not a design decision. A1 was settled during the wave by S6 with a
mechanism (A23(i): only a `Link` is column-for-column the corridor variable; a `Line` would close a
KVL loop). That is the right resolution and it is recorded. Noting it because "settled by the
implementing slice" is a weaker position than "decided at design time", and if the `Link` form had
failed, AC-6 would have had to be downgraded mid-wave under the Waiver Protocol.

### Covered in letter, checked in substance — the harder half

I walked each W's sub-clauses against the criteria that claim them. Three are worth recording:

- **W2's "no intra-zone flow rows"** is asserted by no criterion directly. AC-2's copper-plate
  control cannot catch it: derivation §5 records that zone A's only internal branch (`br12`) is
  unrated on that fixture, so an intra-zone flow row could exist and never bind. Likewise
  `test_one_zone_no_corridors_equals_dc_opf_on_unrated_case30` compares against an **unrated**
  case30. The clause is in fact covered — by **AC-6**, whose PyPSA oracle is one bus per zone with
  no intra-zone network at all, on *rated* case30, where an intra-zone row would bind and break
  parity. Worth stating because it makes AC-6 load-bearing for W2 in a way the matrix does not say,
  and AC-6 is the wave's only T2 engine-divergent row.
- **W3's "bounds shifted by the zonal point"** is covered by
  `test_generator_bounds_are_never_left_by_the_delta_caps` and the two `p0`/`d0`-out-of-bounds
  tests. Adequate.
- **W4's "per-branch flows and duals"** is covered by AC-5(c), and well: the plan's readback zeroed
  `flow_limit_dual` while *keeping* the rows and got exactly the two identity tests red, which is
  the right shape of proof that they read μ off the result rather than recomputing it.

### One walk defect was dropped in reconciliation (LOW)

`record/m6-walk.md` lists **nine** defects (D1–D9). A29's fold table lists **eight** (W1–W8),
mapping D1→W1, D2→W2, D3→W3, D4→W4, D5→W5, D6→W6, D7→W7, D9→W8. **D8 has no row.**

D8 is real and durable: `docs/contributing.md`'s quality-gate checklist runs
`uv run mkdocs build --strict` with no preceding `uv sync --all-groups`, while `pyproject.toml`
declares no `default-groups` — so on a fresh clone that line fails with "Failed to spawn: mkdocs".
The same file's "Building the docs locally" section further down *does* include the sync, so it is
a one-line inconsistency inside a single file.

The reason to raise it: **D8 is the documented root cause of A27**, the wave's own docs-gate
incident, where the orchestrator hit exactly that "Failed to spawn" and diagnosed it as a worktree
venv problem. A27 records the fix as a worktree-setup instruction for M7; D8 records that the
checklist a contributor actually follows still has the bug. Fixing only the M7 runbook leaves the
trap armed for the next person. **It does not change any matrix verdict** — it is a process-doc
defect, not a criterion failure. It belongs on the fold list as item (j).

---

## Level 2 — Power: what the observation would have shown had the change been absent

### The revert-and-watch demonstration

**Change reverted.** `market/zonal.py` stage 3 stubbed to a no-op — the chain publishes the *zonal*
point as its final point (deltas zeroed), i.e. the min-cost redispatch is absent. Applied only in a
detached scratch worktree:

```
$ git worktree add --detach .../scratchpad/m6-revert HEAD
Preparing worktree (detached HEAD d0ce957)
$ git diff --stat            # in the scratch tree
 src/mambo_power/market/zonal.py | 14 ++++++++++++++
 1 file changed, 14 insertions(+)
```

**Capture validated — the change really absent and really loaded:**

```
$ PYTHONPATH=.../m6-revert/src uv run --no-sync python -c "..."
LOADED: C:\Users\mambo\...\scratchpad\m6-revert\src\mambo_power\market\zonal.py
STUB PRESENT: True
```

**The red:**

```
$ PYTHONPATH=.../m6-revert/src uv run --no-sync pytest -q tests/unit/test_market_zonal.py \
      -k "pf_dc_feasible or ac4 or ac5"
>       assert overload <= FLOW_TOL_MW
E       assert 21.598814780084247 <= 1e-06
tests\unit\test_market_zonal.py:697: AssertionError

FAILED ...::test_ac4_the_redispatched_point_is_the_nodal_optimum[case30-0.001]
FAILED ...::test_ac4_the_redispatched_point_is_the_nodal_optimum[case300-0.05]
FAILED ...::test_ac4_welfare_gap_is_zero[case30]
FAILED ...::test_ac4_welfare_gap_is_zero[case300]
FAILED ...::test_ac5a_the_zonal_clearing_is_a_relaxation_so_its_welfare_is_never_lower[case30]
FAILED ...::test_ac5a_redispatch_payment_is_the_welfare_the_zonal_clearing_could_not_deliver
FAILED ...::test_ac5b_the_three_figures_differ_on_case30
FAILED ...::test_ac5c_the_settlement_identity_closes_from_the_result_object_alone_on_case30
FAILED ...::test_the_final_point_is_pf_dc_feasible_and_closes_the_energy_balance[case30]
FAILED ...::test_the_final_point_is_pf_dc_feasible_and_closes_the_energy_balance[case300]
10 failed, 3 passed, 17 deselected in 1.28s
```

Restored and removed:

```
$ git checkout -- src/mambo_power/market/zonal.py && git status --short   # (empty)
$ git worktree remove --force .../m6-revert                               # gone from `git worktree list`
```

**Validation of the capture, as mandated.** The change was really absent (module `__file__` printed
from the scratch path, stub text confirmed in the loaded source, `git diff --stat` showing the
14-line insertion and nothing else). The checks are ones the matrix leans on
(`test_the_final_point_is_pf_dc_feasible_and_closes_the_energy_balance` is the chain-level
realisation of AC-3/W5(a); the AC-4 and AC-5 rows are named in the matrix by these exact test
names). The red is the failure I predicted before running: a rating overload at the zonal point.

**The three survivors are correctly explained by the stub's deliberate scope.** I replaced only the
two dispatch arrays and the four delta arrays, not `duals`, `branch_flow_mw` or `ptdf` — so
`test_ac4_final_lmps_equal_the_nodal_lmps_on_case30` and
`test_ac4_case300_flow_duals_are_degenerate_at_the_nodal_optimum` read unstubbed inputs and cannot
be read as evidence either way. `test_ac5a[case300]` survives for a substantive reason:
`welfare(zonal) ≥ welfare(final)` is trivially true at equality when `final := zonal`. Its case30
sibling *did* go red, because that one asserts `margin > 1.0` strictly. That is the strict clause
doing exactly the job AC-5(a) assigns it.

### F2 — AC-4's case300 LMP clause is a description, not a property (HIGH)

A20 narrowed AC-4's price clause on case300 to a "committed structural property". Read at source,
`test_ac4_case300_flow_duals_are_degenerate_at_the_nodal_optimum`
(`tests/unit/test_market_zonal.py:480`) computes both of its sets from **one** LP solution's own
rows:

```
at_rating = {row.id for row in result.branches if |‖row.p_from_mw‖ − rating| ≤ atol}
priced    = {row.id for row in result.branches if row.flow_limit_dual != 0.0}
assert priced <= at_rating
assert len(at_rating) > len(priced)
```

and `result.branches` is populated at `src/mambo_power/market/zonal.py:506-514` from
`final.branch_flow_mw` and `final.duals.flow_limit` — the redispatch LP's own primal and dual
vectors. `priced ⊆ at_rating` is therefore **complementary slackness**: every optimal LP solution
satisfies it, including one that landed on a completely wrong point. The `_nodal` fixture element is
bound but never used in the test body.

This is not my inference — the wave observed it and recorded it as a success. The AC-4 readback
says the anchored-rate sabotage produced "**10 failed, 1 passed** on the AC-4 selection; the
survivor is the case300 structural-property test, which is correct — the degeneracy property does
not depend on the objective." Correct, and that is precisely the problem: a check that does not
depend on the objective cannot stand in for a check that the *prices* agree.

So the substitution swapped a falsifiable claim (chain LMPs ≈ nodal LMPs on case300) for one that
nothing can falsify. **On case300, nothing in this wave compares the chain's LMPs to any
reference.** The matrix's framing — "a criterion clarification recorded before discharge, not a
waiver" — does not survive the reading: it is a waiver, because what replaced the clause carries no
information.

The underlying degeneracy (A20) is real and the wave's refusal of a blanket 1 $/MWh tolerance was
the right call — that would have admitted real regressions to hide a known one. But the honest
options were a *discriminating* degeneracy check or an explicit waiver, and a discriminating one is
available: assert that the two solves' priced sets are each ⊆ at-rating **and compare the LMPs on
the branches where both agree**, or assert the two LMP vectors differ only on the degenerate face
(equal energy component, congestion differing only across the at-rating-but-unpriced set). The
redispatch-level sibling (`tests/unit/test_opf_redispatch.py:375`) already gets halfway there — it
does compare two independent solves' priced sets — and is the better template.

*Recommendation:* fold item — replace or supplement the case300 clause with a two-solve comparison.
Until then AC-4's case300 price clause stands **unproven**, and the matrix should say so.

### F3 — no external oracle reaches `redispatch_dc_opf` on a real fixture (MED)

Dig (c) asked what would still go red if a shared-core bug made both `solve_nodal` and the chain
wrong the same way. Both routes go through `_extract_and_validate` and the same
`_balance_row` / `_flow_limit_rows` / `_epigraph_rows` helpers, so D1's agreement test is blind to
any fault living in those.

**The answer, named:** `test_a_corridor_at_the_true_rating_sells_a_schedule_the_network_can_carry`
and `test_an_overstated_corridor_sells_a_schedule_the_network_cannot_carry`
(`tests/unit/test_market_zonal.py:249, 286`). Their expected final dispatch `(70, 10)` and LMPs
`(10, 10, 50)` come from `record/m6-ac2-derivation.md`. §5 obtains those numbers by running
`market.solve_nodal` — engine-produced, so not an oracle on its own — **but** §5 also records that
they equal §2's numbers exactly, and §2 is a hand KKT solve independently cross-checked with
`scipy.optimize.linprog(method="highs")` on hand-built matrices, with scipy's dual sign convention
verified numerically by perturbing `L_A` by +1 MW and confirming `Δobjective = 10.0 =
eqlin.marginals[0]`. The anchor is therefore genuine, and transitively external *(source-read:
`.bionic/docs/record/m6-ac2-derivation.md` §2 "Independent scipy cross-check", §5)*. Backing it, the
pre-existing `tests/parity/test_opf_vs_pypsa.py` pins `dc_opf` — and hence those shared row helpers
— against PyPSA on real fixtures.

**The hole that remains:** the anchor is a 3-bus radial network with no elastic demand in the
binding case, and it would only catch a shared-core fault that manifests at that scale. On real
fixtures, `redispatch_dc_opf`'s *distinctive* machinery — the Δ⁺/Δ⁻ column pairs, the bounds shifted
by `(p0, d0)`, the zonal point folded into the fixed RHS — is checked only against `dc_opf`, which
shares its helpers. AC-6's PyPSA parity covers the **zonal stage only**
(`run_engine` calls `zonal_dc_opf`); there is no PyPSA counterpart for the redispatch stage in this
wave. A shift-neutral fault in a shared helper would move both solves identically and D1's
agreement would still hold.

Mitigating: `test_d1_theorem_redispatch_reaches_the_nodal_optimum_from_any_start` computes its
welfare side *outside* the solver from raw coefficient arrays (`_welfare_of`), and drives from two
extreme starts (box floor and box ceiling), so path-independence is genuinely tested. That is good
work and it narrows the hole without closing it.

*Recommendation:* M7 candidate — a PyPSA (or scipy) oracle for the redispatch stage on a real
fixture. Not a blocker for M6.

### AC-3's power — resolved in the wave's favour, with a note

Dig (e) asked whether AC-3's paired negative uses a start built the way the real zonal LP builds
one. It does not: `test_ac3_redispatch_restores_pf_dc_feasibility_from_an_infeasible_zonal_point`
constructs its start with `_relax_intra_zone` + `dc_opf` — a *nodal* solve with intra-zone ratings
stripped — not with `zonal_dc_opf`. That is a genuine deviation from the criterion's wording ("the
**zonal** dispatch itself violates ≥1 rating").

It turns out not to matter, and my revert-and-watch is why. Stubbing the redispatch stage made the
chain publish the true zonal point, and the chain-level readback failed at
**21.598814780084247 MW** of overload on case300 — against the matrix's quoted **21.6 MW** for the
proxy start. The two coincide because no corridor binds on case300 (A23's "first bound dropped →
green on case300"), so the zonal LP and the intra-zone-relaxed nodal LP both reduce to the same
unconstrained economic dispatch there. The proxy *is* the zonal point on that fixture. On case30,
where corridors do bind, the two differ — and the chain-level test went red there too.

**Note (MED):** `test_the_final_point_is_pf_dc_feasible_and_closes_the_energy_balance` carries no
committed paired negative of its own. Its non-vacuity is real — I measured it — but it is
undocumented and unpinned. If a future fixture or cap change made the zonal point already
network-feasible, that test would silently become an absence readback with nothing to catch it. One
assertion on the *zonal* point's overload, in the same test, would fix it permanently. Fold
candidate.

Separately, A21 deserves credit rather than scrutiny: the finding that `pf.dc` absorbs injection
mismatch at the slack, so a flow-only readback passes an unbalanced dispatch, is a genuine
verification-method defect that the wave's own sabotage sweep found and closed in `55f716d`. Both
`_balance_residual_mw` and `_readback` now assert both halves. That is the sweep working as
intended.

### F4 — AC-5(b)'s "three distinct fields" are measurably two (MED)

Dig (b). From source, `src/mambo_power/market/zonal.py:477-479`:

```python
redispatch_payment  = (cost_final - cost_zonal) + (value_zonal - value_final)
welfare_gap         = (value_nodal - cost_nodal) - (value_final - cost_final)
generation_cost_gap = cost_zonal - cost_nodal
```

Under D1, `cost_final == cost_nodal` and `value_final == value_nodal`. Substituting:
`welfare_gap ≡ 0` (that is its job — the exactness row), and
`generation_cost_gap = cost_zonal − cost_final = −(cost_final − cost_zonal)`, i.e. **exactly the
negation of `redispatch_payment`'s first term**. The two genuinely independent quantities are
`A = cost_final − cost_zonal` and `B = value_zonal − value_final`; the wave publishes `A + B`, `−A`
and `0`.

Measured directly (read-only, live worktree, `uv run --no-sync`):

```
case30 fixed-load    payment=+14.636683  welfare_gap=-2.649e-11  gen_cost_gap=-14.636683
                     payment + gen_cost_gap = -2.648903e-11
case30 elastic       payment=+14.513372  welfare_gap=-4.133e-09  gen_cost_gap=-13.572257
                     payment + gen_cost_gap = +9.411150e-01
```

On fixed load the sum is −2.6e-11: `generation_cost_gap` **is** `−redispatch_payment`, to solver
precision. With elastic demand the sum is +0.9412 $/h — that is `B`, and it is the entire
independent content of the third field, 6.5% of the payment.

Now the test. `test_ac5b_the_three_figures_differ_on_case30` asserts `payment > 1.0`,
`generation_cost_gap < −1.0`, `|welfare_gap|` negligible, and
`payment != approx(generation_cost_gap, abs=1.0)`. **Every one of those is satisfied by the sign
flip alone.** They would all still pass if `B` were exactly zero — as the fixed-load drive shows,
where the fields are ±14.6367. Nothing anywhere asserts on `B`. The hand-fixture sibling
(`test_the_three_figures_are_three_different_numbers_on_the_hand_fixture`, values `+400 / 0 / −400`)
is the degenerate case by construction: no bid loads, so `B = 0` and the "three distinct numbers"
are `A`, `0`, `−A`.

**On A24(ii), which I was asked to attack as a claim.** Its diagnosis is right: research §6's
`cost(final) − cost(nodal)` is identically zero under D1, so shipping it would have made AC-5(b)'s
three fields two. Its remedy is only half a fix. It moved the field from "identically zero" to
"identically minus another field's leading term" — better, because the sign inversion it exposes on
case30 (`−13.57` against a `+14.51` payment) is a genuinely useful diagnostic and research §4(b)'s
warning does apply to the zonal point directly. But the claim that AC-5(b)'s three fields are
thereby three *quantities* does not hold, and the criterion's wording ("three distinct fields") is
weak enough that it was discharged without anyone having to notice.

*Recommendation:* fold item — assert the distinguishing term. One line in
`test_ac5b_the_three_figures_differ_on_case30`:
`assert result.redispatch_payment + result.generation_cost_gap == approx(value_zonal − value_final)`
and `> 0.5` on the elastic fixture, would make the third field's independence a proven claim instead
of a definitional one. Cheap, and it converts the row from letter to substance.

### Power, row by row

| AC | absent the change, the observation would have shown | verdict on power |
|---|---|---|
| AC-1 | Suite green is an absence readback — but the three helper sabotages (guard flip 7 dc / 11 mp; `c1`×1.05 9 / 21) and the `getNumRow` tripwire (`expected_rows += 1` → 56 red) are the paired positives *(from the record)* | adequate |
| AC-2 | Copper-plate control is `cap = inf`, not corridor deletion — A22(i) is right that deletion islands the zones and would also pass a sign-flipped column. Paired negative committed as an equality: `λ_B(binding) − λ_B(copper) == 40 == corridor dual` | strong |
| AC-3 | 21.6 MW overload — **measured by me**, above | strong |
| AC-4 | Anchored-rate sabotage → 10 of 11 red; my stub → 4 AC-4 tests red. **Except** the case300 price clause, which shows the same thing either way (F2) | strong / **null on case300 prices** |
| AC-5 | (a) strict-case red under my stub; (c) the zeroed-`flow_limit_dual` sabotage red on exactly the two identity tests *(from the record)*. (b) would show the same thing if the third field carried no independent content (F4) | strong (a)(c) / **weak (b)** |
| AC-6 | Three engine-side sabotages red against a fixed oracle; the zone-relabel one moves case300 dispatch by 7.5e-4 MW, so the tight pins are load-bearing — the repo's usual 1e-2 MW band would have missed it *(from the record)* | strong |
| AC-7 | Registry pin RED before `jobs.md` was updated, GREEN after; registration neutered → 18 red *(from the record)* | strong |
| AC-8 | `--strict` exit 0 certifies the build, not the render — which is why the walk exists and why it found nine defects the gate could not | weak by design, correctly compensated |

---

## Level 3 — Authenticity: was each row's evidence produced at its declared tier?

**Tiers used:** T1 (AC-1, 2, 3, 4, 5, 7) and T2 (AC-6, AC-8). Both T2 rows carry a
`fixture-fidelity:` declaration, as the tier requires. Re-executed one command per tier plus one
extra, all three matching the matrix exactly:

```
$ uv run --no-sync python -c "…print(importlib.import_module('mambo_power.market.zonal').__file__)"
C:\Claude Projects\mambo-power-m6\src\mambo_power\market\zonal.py

$ uv run --no-sync pytest -q tests/unit/test_market_zonal.py tests/unit/test_opf_redispatch.py \
      -k "ac4 or theorem or equals_nodal or welfare_gap or degenerate"     # AC-4, T1
11 passed, 37 deselected in 2.00s                                          # matrix claims 11 passed ✓

$ uv run --no-sync pytest -q tests/parity/test_market_zonal_vs_pypsa.py    # AC-6, T2
SKIPPED [2] …:451: fixed-load parameter: no elastic demand column on either side
SKIPPED [2] …:530: fixed-load parameter: nothing to clear
43 passed, 4 skipped in 16.21s                                             # matrix claims 43 passed, 4 skipped ✓

$ uv run --no-sync pytest -q tests/unit/test_opf_redispatch.py -k "ac3 or feasib or balance"  # AC-3, T1
4 passed, 14 deselected in 0.96s                                           # matrix claims 4 passed ✓
```

The AC-6 skip reasons match the matrix's characterisation exactly ("elastic-only parity tests on
fixed-load parameters"), and the count 4 is right. Also verified live:

```
$ uv run --no-sync python -c "from mambo_power import jobs; print(len(jobs.KINDS)); print(sorted(jobs.KINDS))"
7
['market.multiperiod', 'market.nodal', 'market.zonal', 'n1', 'opf.dc', 'pf.ac', 'pf.dc']
```

and the walk's independence machine-check:

```
$ grep -c "AC-[0-9]" .bionic/docs/record/m6-walk.md
0
```

### AC-6's fixture fidelity, and whether it can reach the failure the AC guards

The T2 declaration is: case30 verbatim MATPOWER, with the AREA→Zone promotion and corridor caps
derived at test time by `tests/_zones.py` from `tests/_rated.py`; no new fixture data. Read at
source, that is accurate. A18 sharpens it usefully and honestly — `tests/_rated.py` *overwrites*
every rating with `max(RATING_MARGIN × base-case DC flow, RATING_FLOOR_MVA)`, so the tie-line caps
are entirely synthetic (1.52–8.97 MVA), not case30's shipped `RATE_A`. As A18 says, that is the
cleaner fidelity story: one derivation rule, no mixed provenance. A19 then measures that every zone
is self-sufficient on promoted rated case30 and the tight caps bind whenever exchange is economic —
which is what makes the fixture structurally able to reach the failure AC-6 guards. Verified at
source: `test_case30_corridor_structure_binds_two_of_three` is committed and asserts exactly that.

### F5 — dig (d): the oracle is genuinely held fixed. Clean. (verified at source, not from the report)

I read `tests/parity/test_market_zonal_vs_pypsa.py` rather than S6's report.

- `run_pypsa_zonal_oracle(fix)` reads only `fix` (`net`, `zone_of`, `caps`, `elastic_ids`) plus the
  raw MATPOWER matrices via `read_mpc_numpy`. It never imports or touches
  `mambo_power.opf.zonal`, and nothing in it reads a `ZonalSolution`. So **any** sabotage applied to
  `src/mambo_power/opf/zonal.py` leaves the oracle bit-identical. The engine-side sabotages are
  therefore genuine sabotages, and the row's claim holds structurally, not just empirically.
- `zone_of_bus` and `corridors` live in `tests/_zones.py` — shared fixture data handed to both
  sides. This is exactly what the negative control exists to demonstrate.
- `test_transposing_the_shared_caps_is_not_a_sabotage` is correctly built. It constructs **one**
  `ZonalFixture` with the `('1','3')`/`('2','3')` caps swapped and passes that same object to both
  `run_engine` and `run_pypsa_zonal_oracle`. It first proves the transposition moved the market
  (objective > 1e-2, dispatch > 100× tolerance, flow > 100×, price > 100×) — without which the
  control would prove nothing — and then calls the five parity assertions directly and shows them
  green. The claim "a fault in shared fixture data cannot be caught by a parity test" is
  demonstrated, not asserted.

Both halves of dig (d) check out. This is the strongest single piece of verification in the wave.

*One scope gap (LOW).* `run_engine` calls `zonal_dc_opf(arr, …, fix.zone_of, fix.caps)` directly.
AC-6's criterion says "**`market.zonal`'s** zonal stage". The chain's own partition function,
`market.zonal.zone_partition` (`src/mambo_power/market/zonal.py:184`), is never exercised against
the oracle — and the only test that touches it,
`test_every_row_family_covers_its_whole_entity_set`, uses `zone_partition` on both sides of its
assertion, so it cannot detect a divergence between `zone_partition` and `tests/_zones.py`'s
`zone_of_bus`. A one-line equality test between the two on case30 and case300 would close it. Small,
but it is the seam between the unit under parity and the unit the criterion names.

### AC-1's disclosed divergence (LOW)

S1's report discloses one deliberate behaviour change: `multiperiod`'s convexity guards now fire
before period/ramp validation, matching `dc_opf`'s order — "observable only with two simultaneously
invalid arguments, and no test supplies two". Correctly disclosed rather than buried, and the
overlay-tree proof stands. But it means "behaviour-preserving" is proven over the behaviours the
suite exercises, with one known divergence that no test pins in either direction. A single test
supplying two simultaneously invalid arguments would convert a disclosure into a decision. Fold
candidate, not a blocker.

### Process observations (not verdicts)

- **A27 mutated the live worktree's venv during Step 5.** Fixing the missing docs group required
  `uv sync --all-groups` in `C:\Claude Projects\mambo-power-m6`. That is outside "read-only on the
  live worktree" for the verification phase, and it means the environment AC-8's gate ran against is
  not the environment S1–S8 ran against. Nothing here suggests it changed an outcome — S8's own
  build via `python -m mkdocs` and the gate's `uv run --no-sync mkdocs` both exit 0 *(from the
  record; not re-executed — budget)*. Recording it because the sequence "unexplained `mkdocs exit=2`
  beside a green suite" is the kind of signal that invites a state-changing fix before the cause is
  known, and here the state change happened to be right. D8 is its root cause and is still open.
- **A stale sabotage worktree is still on disk and still dirty.** `git worktree list` shows
  `…/scratchpad/m6sab` at `d0ce957` detached, with `M src/mambo_power/opf/zonal.py`. It cannot
  affect `wave/06-zonal-redispatch`'s content, but anyone running pytest from it gets sabotaged
  results, and it should be removed before the wave closes:
  `git worktree remove --force <path>`.

---

## Not covered by any criterion

Things I looked for that no AC claims, listed so the gap is a decision rather than an oversight.

1. **W8's docs surface has no design decision** (F1) — the wave-level finding above.
2. **`MarketZonalResult` carries no corridor rows.** A26(v) records it: corridor flow and capacity
   price are readable only at the array level. AC-5 requires the *settlement* identity be computable
   from the result alone and that is met, but the corridor — the object the whole zonal design turns
   on — is not on the published result. No criterion asks for it. M7 candidate, in the A23 mould.
3. **`jobs.run` error taxonomy for `market.zonal`.** Walk D1 / A29 W1: four caller mistakes return
   `INTERNAL` (which `jobs.md` defines as "a bug"), and a duplicate corridor pair returns
   `status=ok` with an undocumented winner. AC-7 requires "never raises" and gets it; nothing
   requires that a caller error be *distinguishable* from a library bug. AC-7 is discharged
   correctly and the defect is real — the criterion simply does not reach it. Already fold item (c),
   correctly triaged as HIGH.
4. **No criterion covers `Zone` becoming solver-read.** The design says "`Zone` (M1,
   schema-present) becomes solver-read", which is a real change in the model's contract — a field
   that was decorative is now load-bearing, and a bus with `zone=None` now changes behaviour. It is
   tested (`test_a_bus_with_no_zone_is_rejected_rather_than_defaulted`) but claimed by no AC.
   Cosmetic; noting for completeness.
5. **Walk defect D8 has no fold row** — see Level 1.

---

## Findings summary

| # | sev | finding | disposition |
|---|---|---|---|
| F1 | HIGH | W8 (docs) has zero inbound design decisions; the missing link produced walk D2 (result fields render nowhere), which AC-8's four clauses structurally cannot detect | wave-level. Fold (d) repairs the symptom; M7's spec should carry a docs design decision |
| F2 | HIGH | AC-4's case300 LMP clause (A20) is complementary slackness on one LP's own rows — any optimal solve passes. Nothing on case300 compares chain LMPs to a reference. The plan's own readback names it "the survivor" | AC-4's case300 price clause is **unproven**. Fold: two-solve comparison, template at `test_opf_redispatch.py:375` |
| F3 | MED | No external oracle reaches `redispatch_dc_opf` on a real fixture; AC-6 parity covers the zonal stage only. Anchor is the 3-bus scipy-checked hand fixture | M7 candidate, not an M6 blocker |
| F4 | MED | AC-5(b)'s three fields are two: `generation_cost_gap == −redispatch_payment` to 2.6e-11 on fixed-load case30. The distinguishing term (0.94 $/h) is asserted nowhere; A24(ii)'s rescue is half a fix | Fold: one assertion on `payment + generation_cost_gap` |
| F5 | — | AC-6's oracle is genuinely held fixed; negative control correctly built. **Clean** | none |
| — | MED | Chain-level feasibility test has no committed paired negative. Non-vacuity measured by me (21.6 MW), but unpinned against future fixture drift | Fold: assert the zonal point's overload in the same test |
| — | LOW | Walk defect D8 (`contributing.md` checklist omits `uv sync --all-groups`) dropped from A29's fold list; it is A27's documented root cause | Fold item (j) |
| — | LOW | AC-6 parity drives `zonal_dc_opf`, never `market.zonal.zone_partition`, which the criterion names | Fold: one equality test |
| — | LOW | AC-1's disclosed guard-ordering divergence is pinned by no test | Fold candidate |
| — | LOW | Stale dirty sabotage worktree `…/scratchpad/m6sab` on disk | `git worktree remove --force` before close |

**Do any of these change a matrix verdict?** The mandate asked specifically about the walk's
defects: **no** — all nine are correctly triaged as fold items and none touches a criterion's
discharge. The verdict changes come from F2 (AC-4's case300 price clause moves from *discharged* to
*unproven*) and F4 (AC-5(b) moves from *discharged* to *discharged in letter*). Both are recorded
above with the evidence.

---

*Auditor's note.* The bar this wave set for itself is high enough that the findings above are about
the last 5%. Three things are worth naming as good practice rather than as findings: the AC-2 oracle
derived and cross-checked in a second solver *before* the code existed; A21's discovery that `pf.dc`
absorbs slack mismatch, found by the wave's own sweep and closed rather than disclosed; and the AC-6
negative control, which commits the proof of what parity *cannot* catch instead of leaving it in
prose. The two substantive failures — F2 and F4 — share one shape: a criterion whose wording was
loose enough that a narrowed or redefined quantity could satisfy it without carrying the meaning the
requirement intended. That is worth carrying into M7's Step 2 as a spec-writing note.
