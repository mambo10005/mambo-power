# M4 Step 6 — adversarial critic (stance 2)

Critic: m4-critic (fresh; implemented, reviewed, and audited nothing in this wave — not the
six-axis self-reviewer, a separate agent). Date: 2026-08-24. Subject: worktree
`C:\Claude Projects\mambo-power-m4`, `git diff 5fa3285..f5e20d9` (8 commits, 32 files,
+2536/−113). Read-only throughout: nothing edited, committed, or pushed by this agent;
`git status --porcelain` empty before and after every command below; `HEAD f5e20d9` unchanged
throughout (verified again at the end of this session). `uv` =
`C:\Users\mambo\AppData\Roaming\Python\Python314\Scripts\uv.exe`. Scratch probe scripts run
from the worktree root with `PYTHONPATH=.` (`probe_ac6*.py`, not committed anywhere — deleted
before finishing, confirmed by `git status --porcelain` staying empty).

Inputs held: wave spec (W1-W7, AC-1..8, Design items 1-8, Assumptions A1-A6), wave plan (matrix,
per-AC evidence, dispatch ledger), the full diff, `m4-audit.md` (Step-5 exit gate — CONFIRMED,
with two disclosed non-blocking findings), `m4-r1-fold-report.md` (the fold that closed those two
findings), and `m3-critic.md` for shape/severity calibration. The audit's coverage/power/
authenticity work is taken as done and correct where I re-verified it — my job is what a
single-axis pass over known findings would miss, not re-deriving what the audit already nailed
down.

---

## Issues

### 1. carry-to-next-wave — AC-6's "the dispatch-quantity sub-checks are decorative" framing is
accepted by the audit as structurally unfixable; it is not. A cheap, one-load fix gives them real
power, on the same fixture, without abandoning the VOLL-anchor-rule strategy

**Where.** `tests/_bids.py:20-42` (the anchor rule: every derived bid's marginal-value floor is
`fleet_max_marginal_cost`, an upper bound on the achievable clearing price on that fixture) and
`m4-audit.md`'s §2/§3 AC-6 analysis, which concludes the three dispatch-quantity sub-tests in
`tests/parity/test_market_nodal_vs_pandapower.py` "cannot distinguish correct dispatch from S3's
double-counting bug on case14" and treats this as a property of the fixture the wave cannot
cheaply change without "abandoning the VOLL-anchor-rule fixture strategy" (dispatch brief's own
framing, echoed uncritically by both the audit and the R1 fold's wording-only fix, item E).

**Reproduction.** case14 (this repo's fixture, confirmed by direct read) has **zero rated
branches** (all 20 `Branch.rating_mva` are `None` — no congestion is structurally possible on
it), and its fixed-load baseline market-clearing price is a uniform **39.02 $/MWh** at every bus
(`opf.solve_dc_opf` on the plain fixture). `tests/_bids.py`'s anchor rule floors every derived
bid's marginal value at `fleet_max_marginal_cost` = **90 $/MWh** — comfortably *above* that
39.02 clearing price at every load's own `p_mw`, which is exactly why every one of the 11
fixture-derived bids ends up fully price-taking (the property the audit's revert-and-watch
confirmed removes power from 3 of 4 sub-tests).

Ran a scratch experiment (`PYTHONPATH=. uv run --no-sync python probe_ac6c.py` /
`probe_ac6d.py`, real case14 data, `market.nodal.solve_nodal`) giving **one** load (`load-9`,
29.5 MW) a bid anchored **below** the 39.02 clearing price instead of the fleet ceiling (VOLL=200,
floor=25 — still a genuinely concave curve, well within spec Assumption (a)'s requirements),
leaving the other 10 loads' bids exactly as `tests/_bids.py` derives them today:

```
CORRECT: load-9 = 27.166158797900817 MW   LMP(bus-9) = 38.84481797380301 $/MWh
   (cap was 29.5 MW -- load-9 lands INTERIOR to its own bound, bound_dual == 0.0,
    the price-and-quantity-elastic case AC-6's fixture structurally cannot produce today)
```

Then simulated the double-counting bug's effect on this one load **without touching `src/`**
(no revert-and-watch stub needed — a phantom, non-bid `Load` of the same 29.5 MW added at the
same bus reproduces the identical RHS inflation the real bug would cause, since the real bug's
mechanism is exactly "the fixed aggregate still contains this load's own contribution *and* its
elastic LP column is added on top"):

```
DOUBLE-COUNTED (simulated): load-9 = 26.957460032723773 MW   LMP(bus-9) = 40.08286151690959 $/MWh

dispatch delta: 0.2087 MW   (AC-6's DISPATCH_ABS_TOL_MW = 1e-6 -- a ~200,000x blowout)
LMP delta:      1.238  $/MWh (AC-6's LMP_ABS_TOL = 1e-3 -- a ~1,200x blowout)
```

Reproducible on request (scripts were scratch-only, deleted after use; the three-line change is
trivial to reconstruct: anchor `load-9`'s bid floor below the fixture's own fixed-load clearing
price instead of `fleet_max_marginal_cost`).

**Why this matters.** The dispatch brief explicitly asked whether AC-6's power gap is "genuinely
structurally unfixable without abandoning the VOLL-anchor-rule fixture strategy," and both the
audit and the R1 fold accepted "not blocking, disclosed" as the final word without checking for a
cheap fix. There is one: keep `tests/_bids.py`'s existing anchor rule as the default for every
load (it is the right choice for AC-6's other three loads — genuinely testing the QP hypograph
path is valuable and the audit is right that this doesn't need to change), and add a second,
narrowly-scoped bid-derivation path — anchored to a value *below* the fixture's own fixed-load
baseline clearing price rather than the fleet ceiling — for **one** load in the case14 fixture.
This costs roughly the same as `bid_for_load`'s existing ~15 lines, computes the anchor from data
the fixture already has (`opf.solve_dc_opf`'s own baseline LMP, which the parity test module
could compute once, same pattern `fleet_max_marginal_cost` already establishes), and gives all
three currently-decorative dispatch-quantity sub-checks genuine power against the double-counting
bug **on the real pandapower-cross-validated fixture**, not only on AC-4's hand-built network
(which proves the interior case exists, but only against `dc_opf`'s own internal PTDF/dual
arithmetic, never against an independent oracle engine). This is exactly the AC-6/AC-4 coverage
distinction `m4-audit.md`'s own §4 "S5's fixture-strategy finding" scrutiny item already
identifies — the audit named the gap precisely and correctly, then stopped one step short of
checking whether it was cheap to close.

**Severity.** Not a defect — AC-6 discharges today exactly as the audit found, and AC-4
independently covers the interior-dispatch case against `dc_opf`'s own arithmetic. This is a
genuine strengthening opportunity the wave's own record talks itself out of pursuing on the
mistaken belief that the fixture strategy would need to change to get it. Cheap (a few lines,
one load, no change to the`sgen` oracle framing or the tolerance discipline) — worth doing in a
follow-up slice, not blocking this merge.

---

### 2. note — the R1 fold's disclosed scope expansion (item C) is sound; independently re-verified,
not merely trusted

The fold report discloses widening item C from the audit's 3 named files to 7, reasoning that
"M4's own new code only" applies to the defect class, not just the files the walk happened to
click through. Independently re-grepped the current tree (not the fold's own quoted grep output):

```
$ grep -rn "record/m4-research" src/ examples/ docs/   -> (no hits)
$ grep -rn "wave M4 W" src/ examples/ docs/             -> (no hits)
$ grep -rn "wave M[0-9] W" src/                         -> only jobs/models.py, results/n1.py,
                                                            results/opf.py, results/__init__.py
                                                            (all M1/M2/M3-era, A6's convention,
                                                            none using the record/-path or
                                                            wave-M4-specific forms)
```

Confirmed: the widened scope reached exactly the 7 files it claims, touched none of A6's 22
pre-existing M1/M2/M3 files, and left no remaining M4-authored leak. The disclosed reasoning
("the audit's instruction is to not extend A6 to *this wave's own new leaks*, not just the 3
files the walk sampled") is sound and the execution matches the claim. No finding here — a
falsification attempt that failed, recorded because the dispatch brief specifically asked for it.

---

### 3. note — the S5 delayed-message case is a genuine "committed correctly, message just late"
instance, not an unverified "got lucky"

Commit `5442465` (`feat(m4/S5): fixtures-oracle`) is timestamped `2026-08-24 17:40:51 -0700`,
stages exactly the 3 files its own report claims (`tests/_bids.py`,
`tests/parity/test_market_nodal_vs_pandapower.py`, `tests/unit/test_bids.py` — confirmed via
`git show --stat`, matching `m4-s5-report.md`'s own file list), and its progress file
(`.bionic/tmp/m4-s5-progress.md`) independently records "Status: DONE" with the same test counts,
commit hash, and tolerance figures the report and plan cite — a self-consistent, immutable
git-level record that predates any message. This is a different failure mode from S1/S2 (which
genuinely went idle before committing, requiring the orchestrator to verify and land the work
itself) — S5's own commit and progress file already carry everything the orchestrator's readback
cites; nothing was reconstructed or taken on faith after the fact. No finding — a falsification
attempt that failed.

---

### 4. note — elastic demand's real cost showed up as encoding density in one file, not as
scope creep or a hidden requirement

The user chose "elastic demand too" over a narrower scope at the Step 1 interview. Read
`opf/dc_opf.py`'s diff in full (335 lines) looking for evidence the choice was more expensive
than represented: the LP/QP encoding genuinely triples in complexity (dispatch-block Hessian
combining generator and demand curvature in one call rather than two, `objective_cost`'s
semantics needing an explicit recomputation to stay "generation cost only" once demand columns
inject into HiGHS's own combined objective, hypograph rows as the exact structural mirror of the
existing epigraph rows) — this is real, concentrated cost, but it landed entirely inside one
already-complex, senior-implementor-owned file (`dc_opf.py`), was anticipated by the design
interview's own Option A/B tradeoff discussion, and shipped GREEN on the first attempt per S3's
own report (10/10, no adjustment against the hand-KKT numbers). No other file shows comparable
density. Worth naming for M5-M7 scoping: the cost of "elastic demand" was concentrated
complexity in the solver core, not a wider blast radius across the codebase — a future wave
extending `dc_opf` again (e.g., storage or multi-period) inherits an LP-building function that is
now handling four column types (generator poly, generator PWL, demand poly, demand PWL) and four
row families in one function body, which is a maintainability cost worth watching, not yet a
problem. No finding — an observation for whoever scopes the next extension of this same function.

---

### 5. note — `Load.bid` on the entity holds up in practice; no workaround found in `market/nodal.py`

Read `market/nodal.py`'s `_gen_cost_coeffs`/`_load_bid_coeffs`/`solve_nodal` in full for any sign
of friction pulling bid data through `scenario.network.loads[i].bid` that a Scenario-level
collection would have avoided. Both extraction functions build an `{id: entity}` dict from
`net.loads`/`net.generators` once per call and look up by id in `NetworkArrays` order — the exact
same pattern `opf/__init__.py`'s pre-existing `_cost_coeffs` already uses for generators, so
`market.nodal` adds no new access pattern, no `scenario`-specific plumbing, and no filtering logic
a Scenario-level `bids: dict[str, LoadBid]` collection would have made simpler. `Scenario` itself
carries no field besides `network` this wave, so there was nothing for the design to make more or
less convenient — the wrapping is trivial in both directions. No finding — the design choice is
confirmed sound by its one real consumer, not merely asserted sound by the spec's own reasoning.

---

## Falsification attempts that failed

1. **"The `objective_cost` recomputation (S3, `dc_opf.py`) silently diverges from HiGHS's own
   objective whenever a PWL generator's `cost_coeffs` row isn't exactly zero."** Traced the new
   formula (`poly_gen_cost = Σ(c2·p²+c1·p+c0)` over *all* generators, `+ pwl_gen_cost` from the
   epigraph `cost_g` values) against the invariant it depends on: `_gen_cost_coeffs` (both in
   `opf/__init__.py` pre-M4 and `market/nodal.py`'s own mirror) sets a PWL generator's
   `cost_coeffs` row to all-zero by construction (never populated in the branch that handles
   `cost.kind == "piecewise"`), so the two formulas are provably identical whenever that
   invariant holds — which it always does, since nothing in this diff gives a caller a way to
   pass a nonzero row for a PWL generator through either public entry point. Confirmed by the
   existing 68/68 opf/PWL/parity tests staying green unchanged (S3's own report) — this was
   already exercised, not merely reasoned about.
2. **"`Scenario`'s dangling-reference test is vacuous — it might just be re-testing `Network`'s
   own validator with extra wrapping, not actually proving `Scenario` construction triggers it."**
   Read `tests/unit/test_load_bid_scenario.py` directly (the dangling-ref tests the audit already
   cited at lines 159-182) and `model/scenario.py`'s own construction path: `Scenario.network:
   Network` is a genuine nested pydantic field with no `validate_default`/`skip_validation`
   override, so `Network`'s `model_validator(mode="after")` unavoidably runs during `Scenario(...)`
   construction — traced this is not a documentation claim but an artifact of ordinary pydantic
   nested-model validation, no special-casing needed or present. No gap found.
3. **"case14's zero rated branches (found while investigating Issue 1) is itself an undisclosed
   gap — AC-4's own settlement identity only covers congestion via a hand-built network, so
   nothing in this wave proves the settlement identity against a *real*, oracle-verified fixture
   under simultaneous congestion and elastic demand."** True as stated, but not undisclosed: S5's
   own report says this explicitly ("this particular anchor rule cannot itself produce a
   congestion-and-price-elastic-demand interaction on an unrated fixture ... AC-4's own
   settlement-identity test already covers that interaction on a hand-built network") and
   `m3-research.md §6` is cited as the reason none of this wave's fixtures rate any branch at all
   — a carry-over constraint from M3's fixture set, not something M4 introduced or hid. Genuinely
   disclosed, not a fresh finding.

---

## Verdict

**One carry-to-next-wave issue (a real, cheap, previously-unexplored strengthening for AC-6's
evidence), four notes — none a behaviour defect, none blocking.** The wave's core technical
claims hold up under independent re-derivation and a fresh reproducible experiment: the
elastic-demand LP extension, the settlement identity, the price-taker reduction, and the R1
fold's disclosed scope widening are all exactly as claimed. The one substantive finding (Issue 1)
does not change the correctness verdict — AC-6 discharges today, and AC-4 independently covers
the case AC-6's fixture cannot reach — but it does correct the record's own framing: the
dispatch-quantity sub-checks' weakness on case14 is not structural to the VOLL-anchor-rule
strategy, as both the audit and the R1 fold's wording assumed; it is a one-load fixture choice,
cheap to fix, and worth doing before a future wave (M5+) inherits the same fixture and reproduces
the same "not blocking, disclosed" conclusion without checking either.

Combined with `m4-audit.md`'s CONFIRMED wave verdict (not re-litigated here — its coverage,
power, and authenticity work all check out on my own independent reading and re-execution) and
the R1 fold's clean closure of both of the audit's disclosed findings, this wave is **ready to
merge**, with Issue 1 worth carrying into M5's own scoping as a cheap, optional strengthening of
AC-6's evidence rather than a blocking gap in this wave's own record.
