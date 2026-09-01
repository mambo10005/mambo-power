# M3 Step 6 — adversarial critic (stance 2)

Critic: m3-critic (fresh; implemented, reviewed and audited nothing in this wave — not the
six-axis self-reviewer, a separate agent). Date: 2026-08-23. Subject: worktree
`C:\Claude Projects\mambo-power-m3`, `git diff dcdc1c9..8fc8581` (8 commits, 42 files,
+3555/−59). Read-only: nothing edited, committed or pushed; `git status --porcelain` empty
before and after every command below, HEAD `8fc8581` unchanged throughout. `uv` =
`C:\Users\mambo\AppData\Roaming\Python\Python314\Scripts\uv.exe`. Probe scripts run from the
session scratchpad (`.../scratchpad/case300_probe*.py`, `PYTHONPATH=.` against the worktree),
not committed anywhere.

Inputs held: wave spec (W1-W9, AC-1..9, Design 1-9, Assumptions a-c), wave plan (matrix, per-AC
evidence, dispatch ledger, A1-A6), the full diff, `m3-audit.md` (Step-5 exit gate, REFUTED on
AC-1's PyPSA half), `m3-r2-reaudit.md` (scoped re-audit, CONFIRMED after the R1 fold), and
`m2-critic.md` for shape calibration. Both audits' findings are taken as known and are **not**
restated as my findings — I re-verified several for authenticity and found them accurate. My job
was what those two thorough audit passes missed.

---

## Issues

### 1. should-fix-this-wave — the case300 PyPSA residual's stated root-cause theory is wrong;
the real cause is a genuine, quantifiable formulation gap in the oracle, not "index alignment"

**Where.** `tests/parity/test_opf_vs_pypsa.py:43-45` (module docstring): *"not chased further
here either (plausibly related to case300's non-contiguous bus numbering causing a minor
index-alignment difference somewhere in one of the two independent importers)"*. The identical
guess is repeated verbatim in two more places that should have been independent checks on it,
not copies of it: `.bionic/docs/plans/epic-01-foundation/wave-03-opf-n1.plan.md:193-194` ("root
cause not investigated — plausibly case300's non-contiguous bus numbering causing a minor
index-alignment difference in one of the two independent importers") and
`.bionic/docs/record/m3-r2-reaudit.md:70-71` ("root cause named but not chased — plausibly a
bus-numbering index-alignment artifact between the two independent importers").

**Reproduction.** Ran `opf.solve_dc_opf` and the test module's own `run_pypsa_dcopf` on
case300 directly, then compared *both* dispatch totals against the fixture's true declared load
(not just against each other, which is all the committed test does):

```
$ PYTHONPATH=. uv run --no-sync python case300_probe.py
n_gens: 69
sum(diffs) [ours - pypsa, should be ~0 if just redistribution]: 1.2999999999923209
num gens with |diff| > 0.001 MW: 68 / 69
mambo_power total dispatch: 23527.149999999998
pypsa total dispatch: 23525.850000000006

$ PYTHONPATH=. uv run --no-sync python case300_probe2.py   # true balance-row RHS from our own loader
true total load+shunt (our balance-row RHS): 23527.149999999998

$ PYTHONPATH=. uv run --no-sync python case300_probe3.py   # PyPSA's own load total
pypsa n.loads['p_set'] sum: 23525.85
raw bus PD column sum: 23525.85

$ PYTHONPATH=. uv run --no-sync python case300_probe4.py   # bus shunt conductance (MATPOWER GS,
                                                            # bus col 5) across all 5 OPF fixtures
case14 sum(GS) MW: 0.0        n_nonzero: 0
case_ieee30 sum(GS) MW: 0.0   n_nonzero: 0
case57 sum(GS) MW: 0.0        n_nonzero: 0
case118 sum(GS) MW: 0.0       n_nonzero: 0
case300 sum(GS) MW: 1.3000000000000003   n_nonzero: 17
```

Reproducible run-to-run (re-ran the first probe fresh; gap is exactly `1.3` both times, to the
same 68/69-generator pattern).

**Diagnosis, fully closed, not "not chased."** `dc_opf`'s own documented balance row is
`Σ p_g == Σ p_load + Σ g_shunt` (`src/mambo_power/opf/dc_opf.py:14-18,288-290` — `g_shunt_mw =
arr.g_shunt_pu * arr.base_mva`, included in `total_fixed`). case300 is the **only** one of the
five OPF fixtures with nonzero MATPOWER bus `GS` (shunt conductance, "MW demanded at V=1.0 pu"):
17 buses, summing to exactly 1.3 MW. `opf.solve_dc_opf`'s total dispatch on case300
(23527.15 MW) matches the fixture's true declared load-plus-shunt exactly — its balance
constraint is a hard equality, so it cannot do otherwise. PyPSA's total dispatch (23525.85 MW)
matches only the raw `PD` (load) column, with **zero contribution from `GS`** — confirmed
directly (`n.loads["p_set"].sum() == raw bus PD sum`, no shunt term anywhere in that sum).
`import_from_pypower_ppc`/PyPSA's DC-LOPF is silently dropping case300's 17 shunt-conductance
buses from its own power balance, under-serving load by exactly 1.3 MW system-wide — the same
1.3 MW that shows up, redistributed across 68 of 69 generators via the QP's marginal-cost
weighting, as the "residual" the wave's record names.

This is not a coincidence needing more digits to confirm: `raw GS sum (1.3 MW) == mambo_power
total − pypsa total (1.3 MW)` to 13 significant figures, and no other of the five fixtures has
any nonzero `GS` at all — exactly the fixtures the record itself already reports as landing in
the *tight* tolerance band. A bus-numbering/index-alignment bug would produce a handful of large,
lumpy discrepancies (swapped identities), not a small, uniformly-distributed spread across
essentially every generator plus an exact, non-zero *total* imbalance — DC-OPF is lossless, so
two importers reading the *same* network should always produce dispatch totals that agree with
each other and with the true load; an index swap changes *who* is credited with what, never the
sum. The observed signature (near-total-load-matching in ours, systematic 1.3 MW shortfall in
PyPSA, spread thinly across 68/69 generators by the QP's cost-minimizing redistribution) is the
textbook signature of a dropped fixed real-power term, not a mislabelled index.

**Why this matters, concretely.** Three separate documents (a committed test's own module
docstring, the wave plan's pinned AC-1 evidence, and an independent re-audit) all repeat the same
untested guess rather than checking it — this is exactly the "cross-cutting concern a
single-axis review would miss" the mandate names: `m3-audit.md` never re-derived case300's
number at all (declared out of the 3-re-execution cap, read only); `m3-r2-reaudit.md`
independently *re-measured the residual to the same precision* (its own strongest piece of
evidence) but never asked *why* the two totals differ, so it re-published the same speculative
sentence as if independent verification had touched it. None had — until now. Substantively,
this is good news for the wave, not bad: it demonstrates `opf.dc_opf`'s balance formula is *more*
correct than the very oracle it is measured against (it honours a real MATPOWER field, `GS`,
that PyPSA's importer silently discards), so nothing in `dc_opf` needs to change. But the
committed record's causal story is factually wrong, and it is exactly the kind of gap M4 will
walk straight into: M4 builds `market.nodal` directly on `lmp_decomposition`/`dc_opf`, and any
future PyPSA-oracle parity test on a network with nonzero bus shunts (real markets commonly model
fixed reactor/capacitor banks this way) will reproduce this identical, currently-misdiagnosed
gap.

**Fix.** Replace the "bus-numbering index-alignment" guess in all three locations with the real,
now-closed diagnosis (bus `GS` shunt conductance omitted from PyPSA's `import_from_pypower_ppc`
DC-LOPF balance; case300 is the only OPF fixture with nonzero `GS`). Prose-only, no code or
tolerance change needed — `WIDE_COST_REL_TOL`/`WIDE_DISPATCH_ABS_TOL_MW` already correctly cover
this, and now for a known, not speculative, reason. Worth a one-line forward note for M4: any new
PyPSA-oracle fixture with nonzero bus shunts will need the same accounting, not a wider
tolerance band.

---

### 2. carry-to-next-wave — the R1 fold's docstring cleanup (A6) created a fresh inconsistency
one file away from the one it fixed, inside the same two-file package

**Where.** `src/mambo_power/contingency/__init__.py:1` (post-fold) vs.
`src/mambo_power/contingency/n1.py:1` (unchanged).

**Reproduction.**

```
$ git show 8fc8581 -- src/mambo_power/contingency/__init__.py
-"""N-1 branch-contingency screening (epic Design §2 ``contingency/``; wave M3 W5).
+"""N-1 branch-contingency screening (epic Design §2 ``contingency/``).

$ sed -n '1p' src/mambo_power/contingency/n1.py
"""N-1 branch-contingency screening: LODF fast screen -> confirming DC re-solve (wave M3 W5).
```

**Why it matters.** Plan Assumption A6 defends leaving `contingency/n1.py` (and 2 more files)
unfixed on the grounds that the "wave M3 W5"-style citation is a pervasive, deliberate 22-file
house convention, and that fixing 3 more files in isolation "would make the codebase *less*
consistent, not more" — reasoning independently spot-checked and confirmed accurate at the
repo-wide scale by `m3-r2-reaudit.md`. That's a sound argument for the wave-wide question ("should
I chase all 22?"). It does not address the narrower, more locally visible side effect the fold's
*kept* fix (`__init__.py`) actually produced: `contingency/`'s own `__init__.py` module docstring
(the file's own opening sentence describes it as importing `contingency.n1` directly two lines
below) and `contingency/n1.py`'s module docstring — the two files of the same package, one
importing the other by name — now cite the same design item in two different styles side by
side, where before the fold they matched. A6's own file-by-file spot-check
(`m3-r2-reaudit.md:143-158`) verified the pattern's *pervasiveness* across M1/M2/M3 but never
checked internal consistency *within* the one package the fold actually touched — a package-level
comparison, not a repo-wide count, which is the kind of check a repo-wide "is this pervasive"
audit naturally skips.

**Severity.** Purely prose, zero behavioural or AC impact, and genuinely minor — but it is a real
regression in the *specific* dimension (this package's own internal consistency) the fold's
underlying finding cared about, produced by the fix that was kept rather than the one that was
reverted. Cheap to close either direction next time this convention is touched: either restore
`__init__.py`'s citation to match its sibling, or fold `n1.py` in too (A6's own carry-over already
names this as future work).

---

### 3. note — a `Field` description describing pre-S5 placeholder behaviour was never updated
after S5 landed, but does not reach the docs site

**Where.** `src/mambo_power/results/opf.py:77-80`:
```python
ac_check: FeasibilityReport | None = Field(
    default=None,
    description="AC-feasibility check of the dispatch; always None until wave M3 slice S5.",
)
```

**Reproduction.** This field was added by S2 (`d6d3ef5`) before `ac_check` existed as a real
option, with that description honestly true *at the time*. S5 (`9d317ee`) wired
`OpfDcOptions.ac_check` all the way through `solve_dc_opf` and populates this field whenever the
option is set and the solve is Optimal — but never touched `results/opf.py`:

```
$ git show 9d317ee -- src/mambo_power/results/opf.py
(no output — file untouched by S5)
```

The description is now factually stale: `ac_check` is *not* "always None" post-wave, only
`None` when `options.ac_check` is unset or the solve failed. Checked whether this reaches a
reader of the live docs site (mkdocstrings, `show_source: true`, same config that renders
`opf.dc_opf`'s own source verbatim on `api/opf/index.html`): built the site fresh
(`mkdocs build --strict`, exit 0) and grepped the output —

```
$ grep -rn "always None until wave M3 slice S5" <built-site>/   # no hits anywhere
$ sed -n '3012,3040p' <built-site>/api/results/index.html       # OpfDcResult's rendered section
      Result of mambo_power.opf.solve_dc_opf.
      When status != "Optimal" the dispatch/LMP/flow rows [...] are meaningless [...]
      (no field-level Field(description=...) text, no source block, for this class)
```

`docs/api/results.md`'s `::: mambo_power.results` block (`show_submodules: false`) renders only
`OpfDcResult`'s class docstring on the built site, not its individual `Field(description=...)`
strings or its source — unlike `opf.dc_opf`'s page, which does show source. So this stale text is
invisible to anyone reading the API reference; it is a source-only accuracy nit.

**Fix.** One-line description update (e.g. "AC-feasibility check of the dispatch;
`None` unless `options.ac_check` is true and the solve reached `Optimal`"). Trivial, no
user-facing effect.

---

## Falsification attempts that failed

1. **"`test_opf_pwl_guard.py`/`test_feasibility.py`'s assertions could pass with a subtly wrong
   implementation."** Read both files and the implementations they exercise
   (`opf/dc_opf.py:_convex_pwl_segments`, `results/feasibility.py:feasibility_report`) line by
   line. The non-convex guard test's slope arithmetic checks out by hand (points
   `(0,0),(30,600),(60,900)` → slopes 20 then 10, correctly flagged decreasing; the convex
   companion test's slopes 20/30/37.5 correctly pass). `feasibility_report`'s thermal/voltage
   branches are each exercised by an independently-constructed hand network (a reactive-heavy
   overload for thermal, a high-reactance sag for voltage, deliberately isolated from each other
   — the voltage case leaves its branch unrated so the thermal path can't accidentally fire) with
   both a positive and the paired negative (`_clean_case_has_no_violations`) case. No
   self-reference, no vacuous assertion found in either file.
2. **"`opf.dc_opf` over-built speculative generality for M4's market-clearing reuse beyond what
   M3 itself needed (the opposite failure mode from under-building)."** Read
   `opf/dc_opf.py`/`opf/__init__.py`/`contingency/n1.py` in full for unused knobs, dead
   parameters, or premature abstraction. `OpfDcOptions` carries exactly one field (`ac_check`),
   with its own docstring explicitly declining to add solver-tuning fields "speculatively."
   `N1Options` is empty (matches `OpfDcOptions`'s pre-S5 shape, an established M2-era pattern, not
   new speculation). `lmp_decomposition`'s standalone-function shape is the literal thing AC-3
   requires, not an add-on. No unused surface, no dead M4-only branch found — the "built with M4
   in mind" framing shows up only as accurate docstring cross-references (`market.nodal` named in
   three docstrings as a *future* caller, never as code that exists or executes today), not as
   over-engineering.
3. **"The non-response-procedure takeovers (S3, S5) conceal quality problems the reports paper
   over — the orchestrator, not a fresh implementor, is grading its own work."** Read both
   commits' full diffs directly (not just `--stat`, which the audit already checked) and both
   slices' progress files. `m3-s5-progress.md` stops abruptly at "designing test networks...
   about to write RED tests" — far short of the 13-test, fully-wired deliverable the commit
   actually contains — confirming the progress trail genuinely lags real completion rather than
   documenting a shortcut; the landed code (`opf/__init__.py`'s `ac_check` wiring,
   `results/feasibility.py`) reads as correct and complete on independent inspection (Issue 3's
   nit aside, which is orthogonal — a stale field description S5 never touched, not a defect in
   what S5 built). `m3-s3-progress.md` documents finding pandapower's real quadratic+PWL
   mixing restriction firsthand and building an independent lambda-iteration oracle in response,
   consistent with the shipped `test_opf_dc_case14_pwl.py`. No discrepancy between either
   report's narrative and the code that actually landed.

---

## Verdict

**One should-fix-this-wave issue, one carry-to-next-wave issue, one note — none a behaviour
defect, none blocking.** The wave's actual numerics hold up under direct, independent
re-derivation: `opf.dc_opf`'s balance formula is not merely PyPSA-matched, it is *provably more
complete* than PyPSA's own import path on the one fixture (case300) where the two diverge, and
that divergence is now fully root-caused for the first time in this wave's record rather than
left as an open guess three documents deep. The two smaller findings are both prose/documentation
accuracy nits with zero behavioural surface and cheap, mechanical fixes.

Combined with `m3-r2-reaudit.md`'s CONFIRMED wave verdict (which I did not re-litigate — its
re-execution of AC-1's PyPSA half, the full suite, and the other fold items all check out on my
own independent reading), this wave is **ready to merge**, with the case300 root-cause correction
(Issue 1) worth folding first since it is committed, published documentation asserting an
un-investigated and, on inspection, incorrect causal claim — cheap, and better fixed before M4
inherits the same fixture and re-derives the same wrong guess a second time.
