# M5 / Step 1 — scope closure

Wave M5 (`multiperiod`), triple **build · audited · wave**, integration branch
`epic/01-foundation` (base `e88752c`, M4's merge). Recorded 2026-08-25.

This file exists because the scope answers below are settled *now* but cannot land in their
permanent home yet: the governing-skill hook blocks a wave spec that carries no `## Design`, so
`wave-05-multiperiod.spec.md` is written once, after the Step 2 design interview, with
Requirements + Not Doing + Prior art + Design together. Until then this is the durable record.
When the spec is written, these sections move into it and this file becomes inert history.

## Problem statement

**How might we clear a 24-period day-ahead market where dispatch decisions in one hour constrain
the next — through generator ramp limits and storage that must husband a finite energy budget
across the whole horizon?**

What makes M5 different from every wave before it: M1-M4 solved a *single* instant. Each solve
was independent, and correctness was checkable one snapshot at a time. M5 introduces **temporal
coupling** — a ramp row ties period t to t-1, and an SoC row ties the whole horizon into one
budget. That is the wave's real content, and it is why the degenerate-to-nodal test (AC-4
candidate) matters so much: it is the proof that adding a time dimension did not change the
answer where time is not supposed to matter.

## Scope answers (user, 2026-08-25, three questions)

1. **Per-period variation: load profile only.** Demand scales per period; the profile is derived
   at test time from already-committed fixture data (the `tests/_bids.py` / `tests/_rated.py`
   precedent — no new fixture data committed). Generator offers and demand bids stay constant
   across the horizon. Rationale accepted: a varying load is already sufficient to force both
   ramping and storage arbitrage, so the ramp and SoC machinery is fully exercised without a
   time dimension on the bid surface. Time-varying bids are M7's (agents) genuine need, and M7
   extends `Scenario` when it gets there.

2. **End-of-horizon SoC: cyclic — `SoC_T == soc_initial`.** The standard day-ahead convention.
   Two consequences, both wanted: the horizon cannot silently finance itself by draining the
   battery, and the analytic arbitrage optimum (AC-5 candidate) is well-posed with a unique
   expected answer rather than a boundary artifact. Not configurable this wave — an options
   field with three code paths was offered and declined, since no acceptance criterion asks for
   free or fixed-target end conditions.

3. **"Scenario runner" = the multiperiod solve entry point itself.** The epic carve's phrase
   means `market.solve_multiperiod(scenario, options)`, mirroring how `market.nodal` is its own
   entry point. No separate batch-over-N-scenarios facility, no separate result type. M7 builds
   whatever loop it actually needs.

## Not Doing (explicit)

- **Per-period offers/bids** — scope answer 1. `Scenario` may be *shaped* at Step 2 so M7 can add
  them without a re-cut, but M5 implements load-profile variation only.
- **Configurable end-of-horizon SoC** (free / fixed-target) — scope answer 2. Cyclic only.
- **A batch scenario runner** — scope answer 3.
- **Unit commitment.** No binary on/off, no startup/shutdown costs, no minimum up/down times.
  M5 stays a continuous LP/QP on the one array-level builder ADR-007 fixed. Ramp limits without
  commitment is the standard economic-dispatch relaxation and is what R7 asks for.
- **AC multiperiod.** DC only, as with every market wave. `pf.ac_newton` is not in this path.
- **Reserve/ancillary co-optimization.** Not in R7, not in the epic module table.
- **Storage degradation, cycle limits, or state-dependent efficiency.** `model.Storage` carries
  constant `efficiency_charge`/`efficiency_discharge` and M5 uses exactly those.
- **A second solver.** ADR-007 is binding: multiperiod extends the one array-level `dc_opf`
  builder with further column/row families. Composing a separate multiperiod solver is refused
  by that ADR, not merely disfavoured.
- **Fixing PyPSA's generator-only-OPF infeasibility (A4)** as a goal in itself. Research §1 is
  asked to root-cause it because AC-6's oracle depends on the answer, but repairing PyPSA
  integration is not an M5 deliverable — if PyPSA cannot serve, AC-6 becomes an analytic T1 row
  and the tier downgrade goes to the user under the Waiver Protocol.

## Prior art / alternatives lens

Grounded in this repo's own record plus the external oracles, pending
`record/m5-research.md`'s evidence:

- **Within this repo.** M4 is the direct predecessor: it added demand-side columns and hypograph
  rows to `dc_opf` and proved the result three ways (hand-KKT, settlement identity, oracle
  parity). M5 adds two further row families to the same builder. M3 supplied
  `lmp_decomposition`, reused verbatim by M4 and expected to be reused per period here. M1 put
  `Storage` in the schema and left it solver-ignored; M5 is the wave that makes it real.
- **The formulation is textbook, and that is a feature.** Multi-period economic dispatch with
  ramp limits and storage SoC balance is standard (Wood, Wollenberg & Sheblé; the MATPOWER
  Optimal Scheduling Tool / MOST for the multi-period extension of exactly our DC-OPF). The
  wave's risk is not "is the formulation right" but "did we wire it into an existing builder
  without breaking the single-period answer" — hence AC-4's degeneracy test carrying real
  weight.
- **Oracle alternatives, in preference order.** (i) PyPSA multi-period `optimize` with
  `StorageUnit`/`Store` and `ramp_limit_up`/`ramp_limit_down` — the natural fit, blocked on
  A4's open infeasibility finding, which research §1 must reproduce and root-cause. (ii)
  MATPOWER MOST — a published multi-period reference, but it is Matlab/Octave and this repo has
  no Matlab in CI, so it could serve only as hand-transcribed published numbers, not a live
  oracle. (iii) pandapower — ruled out, it has no multi-period OPF at all, so M4's
  `rundcopp`/`sgen` route does not extend. (iv) Hand-derived analytic optima — always available,
  already the shape of AC-5, and the honest fallback if (i) fails.
- **The simultaneous charge/discharge relaxation** is the known hazard in every LP storage
  formulation. It is well-documented rather than novel; research §3 must state precisely when it
  is provably non-binding and what our formulation does when it is not.

## Open questions carried into Step 2

- **AC-6's oracle** — the wave's one at-risk matrix row. Resolved by research §1, not by
  assumption.
- **`Scenario.periods` shape** — deliberately left to the Step 2 design interview (research §5
  is instructed to present options and not to pick).
- **Whether M5 needs a rated branch** (continuation A7) for its own ACs to be meaningful, and
  whether the 24-period load profile is derived or committed — research §8.
