# M2 Step 6 — adversarial critic (stance 2)

Critic: m2-critic (fresh; implemented, reviewed and audited nothing in this wave). Date:
2026-08-23. Subject: worktree `C:\Claude Projects\mambo-power-m2`, `git diff 6c94459..502dc1b`
(8 commits, 79 files, +11187/−34). Read-only: nothing edited, committed or pushed in either
repo; `git status --porcelain` empty in the worktree before and after every command below
(re-verified at the end, HEAD `502dc1b` unchanged). `uv` run as `uv run --no-sync` from the
worktree root. Probe scripts live under `C:\Claude Projects\mambo-power-m2\.bionic\tmp\critic-m2\`
(two were already there from an earlier session — `probe1_auto_vs_flat.py`,
`probe2_edges.py` — I re-ran both rather than duplicating them; `probe3_gen_on_oos_bus.py` is
new). Every factual claim below carries a command/output or a `file:line`, or is labelled
`unverified`.

**Write-location note.** `.bionic/docs/` is not tracked in the wave branch's history
(`git -C C:\Claude Projects\mambo-power-m2 show HEAD:.bionic/docs/record/` → `fatal: path
'.bionic/docs/record/' exists on disk, but not in 'HEAD'`) — the wave worktree's `.bionic` is a
filesystem junction onto the main checkout, not a committed tree. This file is therefore
written directly at `C:\Claude Projects\mambo-power\.bionic\docs\record\m2-critic.md` in the
main checkout, which is where the spec/plan/audit/review files I read also live on disk.

Inputs held: wave spec (`wave-02-power-flow.spec.md`), wave plan (matrix, per-AC evidence,
ledger, A1-A12), Step-6 stance-1 six-axis self-review (`m2-review-6axis.md`), Step-5 auditor
report (`m2-audit.md`), and `m1-critic.md` for shape calibration. The self-review's and
auditor's findings (dropped `AcSolution.message`, DC `x==0` → `INTERNAL`, duplicated slack-P
rule, `run_json` RecursionError, unbounded `max_iter`/`max_q_rounds`, AC-5's untested
pandapower-match clause, AC-8's missing `pf.ac_newton` API page, W7's uncited-design
coverage hole) are taken as known and are **not** restated as my findings; I re-verified two of
them for authenticity (below) and found them accurate. My job was to find what those three
documents missed.

---

## Confirmed background (not a new finding — sanity-checking the open state I was told about)

The auditor's two REFUTED rows are still unresolved at the wave head; the "fold" the plan
describes has not landed in `502dc1b`:

```
$ grep -rn "ac_newton" docs/api/pf.md
(no output — file has no ::: mambo_power.pf.ac_newton block)
$ grep -rln case14_island tests/
tests/unit/test_fixtures_derived.py
tests/unit/test_islands.py
$ grep -n "solve_ac\|runpp" tests/unit/test_islands.py tests/parity/*.py | grep -i island
(no output — no parity test exercises the island fixture through a solver)
```

Matches the audit's finding exactly (`m2-audit.md` §4, AC-5/AC-8 rows). I did not re-litigate
this per the dispatch brief; it stands as-is going into the merge decision.

---

## Issues

### 1. should-fix-this-wave — the shipped architecture diagram (an AC-8 deliverable) draws an
import edge that doesn't exist and omits two that do, for exactly the module M2 added

**Where.** `docs/design/architecture.md:21,36-38` — the mermaid `flowchart TB` draws
`ac --> results` (`ac` = `pf.ac_newton`) and omits `pf --> model` and `jobs --> numerics`.

**Reproduction:**

```
$ grep -n "^from mambo_power\|^import mambo_power" src/mambo_power/pf/ac_newton.py
68:from mambo_power.numerics.arrays import BUS_TYPE_CODE, NetworkArrays
69:from mambo_power.numerics.roles import EffectiveRoles
70:from mambo_power.numerics.ybus import ybus
$ grep -n "results" src/mambo_power/pf/ac_newton.py
(no output)
```

`pf.ac_newton` imports only `numerics.*`; it never imports `mambo_power.results` (`AcSolution`
carries plain numpy arrays, not result models — `ac_newton.py:100-125`). The diagram's
`ac --> results` edge has no corresponding `import` anywhere in the module. Meanwhile two real
edges are missing from the same diagram:

```
$ grep -n "^from mambo_power\|^import mambo_power" src/mambo_power/pf/__init__.py
22:import mambo_power
23:from mambo_power.model import Network
24:from mambo_power.numerics import EffectiveRoles, NetworkArrays, effective_roles, yf_yt
...
$ grep -n "^from mambo_power" src/mambo_power/jobs/run.py
43:from mambo_power.model import NetworkValidationError, ValidationIssue, validate_network
44:from mambo_power.numerics import NoSlackGeneratorError
45:from mambo_power.results import ResultProvenance
```

`pf/__init__.py:23` imports `model.Network` directly (not just transitively through
`numerics`) and `jobs/run.py:44` imports `numerics.NoSlackGeneratorError` directly — neither
`pf --> model` nor `jobs --> numerics` is drawn. (The self-review's own Architecture section
text — `m2-review-6axis.md:173-179` — states the real edges correctly in prose: "`pf → numerics,
results, model`"; the *rendered* mermaid diagram the self-review did not re-check disagrees
with the self-review's own prose.)

**Why it matters.** AC-8 requires "the Design page renders a mermaid architecture diagram" and
is checked by `mkdocs build --strict` (renders without warning) plus the auditor's page/anchor
probes — neither checks whether the diagram's *content* matches the code it claims to describe.
This is exactly the kind of cross-cutting gap a single-axis review misses: Architecture checked
the import graph as text; Docs/AC-8 checked that a diagram exists and mermaid parses it; nobody
checked the two against each other. A reader trusting the diagram would conclude
`pf.ac_newton` depends on `results` (false) and that `jobs` never touches `numerics` directly
(false).

**Fix.** Drop `ac --> results`; add `pf --> model` and `jobs --> numerics`. One-line diagram
edit, `mkdocs build --strict` re-run to confirm it still parses.

---

### 2. should-fix-this-wave — the fixture provenance files M2 built AC-11 around describe
infrastructure that does not exist anywhere in this repository

**Where.** `fixtures/matpower/PROVENANCE.md:7,9,14,185,200-201` and
`fixtures/matpower/SOURCES.md:7,30` (8 occurrences total) reference `packages/io/test/fixtures/
matpower/`, `packages/engine-pf/test/solveAcPf.test.ts`, `packages/engine-pf/src/parity.ts`, a
"Node suite", a "browser harness in S8", and requirement numbering "W1-R5 / AC-4".

**Reproduction:**

```
$ grep -rn "packages/|Node suite|browser harness|engine-pf" fixtures/matpower/PROVENANCE.md \
    fixtures/matpower/SOURCES.md | wc -l
8
$ [ -d packages ] && echo EXISTS || echo "packages/ DOES NOT EXIST"
packages/ DOES NOT EXIST
$ grep -rn "packages/|Node suite|browser harness|W1-R5|engine-pf" \
    .bionic/docs/specs .bionic/docs/plans .bionic/docs/record src tests examples docs
(no hits anywhere else in the repository or its documentation)
$ cat pyproject.toml | head -3
[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"
```

mambo-power is a single Python package (`src/mambo_power`, hatchling build) with no `packages/`
directory, no TypeScript/Node toolchain, and no "S8" step anywhere in its own spec/plan
numbering (M2's steps are S1-S7). The referenced files (`solveAcPf.test.ts`, `parity.ts`, a
"browser harness") belong to a different project entirely.

**Origin, confirmed:**

```
$ git log --oneline --all -S "packages/engine-pf" -- fixtures/matpower/PROVENANCE.md \
    fixtures/matpower/SOURCES.md
ca10b6a chore(epic-01): migrate MATPOWER fixtures from gridlab W1 with provenance intact
```

`ca10b6a`'s own message says "migrate ... from gridlab W1 with provenance intact" — the text
was carried over verbatim from a prior, unrelated project (`gridlab-w1`; the M2 plan's Handoff
section, `wave-02-power-flow.plan.md:228`, separately lists "delete leftover
`C:\Claude Projects\gridlab-w1`" as an outstanding user action, confirming that project exists
and was abandoned). The sha256/retrieval facts were preserved correctly (verified independently
below), but the surrounding narrative — which monorepo holds the fixtures, which test runners
consume them, which future step adds a browser harness — was never adapted to mambo-power's
actual layout.

**Why this is M2's problem, not just an inherited M1 defect to carry forward.** This predates
M2 (the text sits in unchanged context lines of the diff, not the `+` lines), so it is not a
new defect M2 introduced. But M2 substantially rewrote both files in this exact wave —
`git diff 6c94459..502dc1b -- fixtures/matpower/PROVENANCE.md` adds a 24-line "Licence" section
and a 50-line "case300.m" provenance section, and `SOURCES.md` gains a new retrieval table and
licence paragraph — landing new, careful, heavily-cited M2 content directly adjacent to the
fabricated cross-project references without flagging or correcting them. Worse: **AC-11 was
added at Step 5 specifically because the auditor found "W7 had zero design citations and no
criterion" for this exact file's sha256/licence clause** (`m2-audit.md` §1, "Uncovered list").
The fold that closes AC-11 tests the sha256 and the BSD-exclusion quotation
(`tests/unit/test_fixture_case300.py`, verified below) — both of which are correct — but no
test, review, or audit pass touched the surrounding provenance narrative's internal consistency
with the repository it now lives in. A document whose entire purpose is establishing
trustworthy data lineage contains eight sentences about a codebase that isn't this one.

**Independent verification that the load-bearing facts (not the narrative) are sound:**

```
$ sha256sum fixtures/matpower/case300.m
69a90280e999ef533d94656e0fbc08311f1347c962dd2753ff2005ff5e3f9ac5 *fixtures/matpower/case300.m
```
Matches the digest quoted in the spec, plan, `PROVENANCE.md`, and `SOURCES.md` exactly (64 hex
chars — I miscounted by hand on a first pass and re-verified programmatically:
`python3 -c "print(len('69a90280e999ef533d94656e0fbc08311f1347c962dd2753ff2005ff5e3f9ac5'))"` →
`64`). AC-11's actual assertions hold; only the surrounding prose is contaminated.

**Fix.** Strip the `packages/`, "Node suite", "browser harness in S8" and "W1-R5" sentences
from both files (or replace with mambo-power's real structure: `fixtures/matpower/`,
consumed by `tests/parity/` and `tests/unit/`, no browser harness planned). Cheap — prose-only,
no test depends on the removed sentences (they're not part of what AC-11 checks). Worth a line
in the fold noting the gridlab-w1 origin so a future reader isn't left to reconstruct it via
`git log -S`.

---

## Falsification attempts that failed

1. **"The Q-limit hand-built pin tests (`test_q_max_pin`/`test_q_min_pin`/
   `test_no_restore_after_pinning`) are self-referential — they assert the pinning code against
   a value derived from the same code, the way M1's PTDF-slack-column test asserted a property
   true by construction."** Read `tests/unit/test_pf_ac_newton.py:267-359`: `bus2_q_unlimited()`
   solves the *unconstrained* network to learn how much Q the bus actually needs, then the test
   sets `q_max` a fixed 5 MVAr *below* that independently-measured need and asserts (a) the pin
   fires, (b) the reported `gen_q_pu` equals the limit to 1e-9, (c) voltage moves in the
   physically correct direction (down for a Qmax pin, up for a Qmin pin) — a sign check no
   amount of code-only self-reference could pass by accident. `test_no_restore_after_pinning`
   goes further: it manufactures a state where a naive restore rule would flip bus A back to PV
   (`no_restore_case()` docstring, `:319-324`) and asserts it does not. Real, independent
   assertions — not circular. Confirmed further by the auditor's revert-and-watch
   (`m2-audit.md` §2b): stubbing the violator-detection lines turns exactly these tests red.
2. **"A generator or load marked `in_service=True` but attached to a bus that is itself
   `in_service=False` silently corrupts the power balance (double-counted or index-error)."**
   Built a 3-bus hand network with `gen-dead` (`in_service=True`) on a bus with
   `in_service=False` (`.bionic/tmp/critic-m2/probe3_gen_on_oos_bus.py`):
   ```
   arr.bus_ids: ['s', 'a']            # 'dead' correctly absent from the array view
   AC total gen P: 20.043... vs total load: 20     # balances against the live network only
   DC gens reported: [('gs', 20.0)]                 # 'gdead' silently excluded, not double-counted
   ```
   `NetworkArrays.from_network` filters generators by their *bus's* in-service flag before
   building positional arrays, so the dangling in-service generator is dropped cleanly, not
   miscounted. This is M1 substrate M2 didn't touch; not a finding.
3. **"`solve_ac`/`newton` mutate the caller's `NetworkArrays` or `Network` in place, re-opening
   the M1 critic's `NetworkArrays` `frozen=True`-in-name-only finding now that a real solver
   scratches into these arrays every iteration."** Read `ac_newton.py:266-271` (`bus_type =
   roles.bus_type.copy()`, `v = np.asarray(v0, ...).copy()`) and `specified_injection`
   (`:136-141`, returns a fresh array from arithmetic, not a view onto `arr`'s storage) — every
   value `newton` mutates across Q-limit rounds is a copy, never a view into the input
   `NetworkArrays`. Independently re-ran the self-review's own probe pattern
   (`net.model_dump()` before/after `solve_ac`) mentally against the code path: `solve_ac`
   never assigns back to `net` or `arr`. Confirmed correct, no finding — the M1-era risk was
   real but M2's solver defends against it by copying at every mutation site.

---

## Verdict

**Two should-fix-this-wave issues found** (both documentation/provenance authenticity, neither
a numerical or behavioural defect): the architecture diagram misdraws `pf.ac_newton`'s
dependencies, and the fixture provenance files carry eight sentences of fabricated
cross-project infrastructure that predate M2 but that M2 built its own AC-11 evidence directly
alongside without noticing. Neither invalidates a numeric claim — the solver formulation,
Q-limit semantics, DC results and jobs boundary are correctly proven by the self-review and
auditor, and I did not find a counter-example in either. Combined with the auditor's own
still-open REFUTED rows (AC-5's island-vs-pandapower clause untested, AC-8's `pf.ac_newton` API
page missing — both confirmed still true at `502dc1b` above), this wave is **not ready to merge
as-is**: it needs the two auditor-mandated fold items plus these two documentation-accuracy
fixes before the wave verdict can be re-issued CONFIRMED. All four are cheap (no solver code
touched) and none contradicts the substance of what M2 built.
