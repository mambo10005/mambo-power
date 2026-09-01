# M1 Step 6 — adversarial critic (stance 2)

Critic: m1-critic (fresh; implemented, reviewed and audited nothing in this wave). Date: 2026-08-20.
Subject: worktree `C:\Claude Projects\mambo-power-m1`, `git diff ca10b6a..36bd20a` (2922d8e, 8c82e9d, c9b5a90,
fc68535, 36bd20a). Read-only: nothing edited, committed or pushed in any repo; `git status --porcelain` empty
after every command below (printed as `(status end)` with no preceding line). `uv` =
`C:\Users\mambo\AppData\Roaming\Python\Python314\Scripts\uv.exe`, run from the worktree root with `--no-sync`.
Probe scripts live only under `C:\Claude Projects\mambo-power\.bionic\tmp\critic\` (p1-p6); each is named
where its output is quoted. Every factual claim carries a command/output or a file:line, or is labelled `unverified`.

Inputs held: wave spec, epic spec §Design, plan (matrix, ledger, A1-A14), `m1-review-6axis.md`, `m1-audit.md`,
`m1-s4-report.md`, `m1-s5-report.md`, `m1-s6-report.md`, `m1-s2-ci-proof.md`, `m1-step5-tests-floor.md`, and every
file in the diff. The six-axis review's findings (self-loop, `tap_ratio<=0`, `r=x=0`, `Network.bus_index()`,
F1, F2, import hack, fixture-list triplication) are taken as known and are not restated; I verified two of its
load-bearing claims (`Network.bus_index()` has one test caller and no `src` caller — `grep -rn "bus_index()" src tests`
→ `tests/unit/test_model_examples.py:58` only; the self-loop fillers exist at `tests/unit/test_model_invariants.py:134,221`)
and found them correct.

Severity scale (per brief): **blocker** · **should-fix-this-wave** · **carry-to-next-wave** · **note**.

---

## Issues

### 1. should-fix-this-wave — the model admits non-finite floats; W3 "round-trip is identity" and BAD_BASE both break on them

**Where.** `src/mambo_power/model/entities.py:22` (`_Entity.model_config`), `network.py:28` (`Network.model_config`)
— neither sets `allow_inf_nan=False`; `network.py:89` checks only `base_mva > 0`, which `inf` satisfies.
The importer guards the *file* path (`matpower.py:214` → BAD_NUMBER "is not finite"), but the model itself —
the native format per epic R1 "the native file format IS the model" — does not.

**Reproduction** (`p1_nan.py`, `uv run --no-sync python .../p1_nan.py`):

```
1) constructed with vm_pu=nan: nan
   dumps -> { ... "vm_pu": null ... }
   loads(dumps(net)) == net ? False | back.vm_pu = None
2) constructed with x=nan: nan
   model_dump_json -> {... "x":null ...}
   AC-5 expression raised ValidationError -> ['1 validation error for Network', 'branches.0.x',
     '  Input should be a valid number [type=float_type, input_value=None, input_type=NoneType]']
   ybus finite? False
   bbus x==0 guard tripped? no -> bbus finite? False
3) JSON with Infinity/NaN tokens accepted: base_mva = inf gen p_mw = nan
   p_gen_pu = [nan] gen_p_pu = [nan]
```

So: (a) `native.py:3` ("`loads(dumps(net)) == net` for every valid network") is false for a network the model
accepts; (b) pydantic's default `ser_json_inf_nan='null'` turns a required NaN field into `null`, so a saved file
cannot be re-read — and the failure is a pydantic `ValidationError`, not a named error; (c) `native.loads` accepts
the non-standard JSON tokens `NaN`/`Infinity`, so a SaaS client can post `base_mva: Infinity` past BAD_BASE and
get NaN arrays back silently; (d) the `bbus` `x == 0` guard does not fire for `x = NaN`, so the DC path returns
non-finite matrices without the error `bbus.py:28-30` promises.

AC-5 itself is not falsified (fixtures carry no NaN), but the W3 requirement and R1's format contract are
broader than the fixtures, and this is exactly the class of input a SaaS boundary sees.

**Fix.** One line each: `ConfigDict(extra="forbid", frozen=False, allow_inf_nan=False)` on `_Entity` and on
`Network` — pydantic then rejects NaN/±inf for Python *and* JSON input (including the `NaN`/`Infinity` tokens) at
parse, which is the same tier as a string in a float field. Add two tests: `pytest.raises(ValidationError)` for
`Branch(x=nan)` and for `native.loads('{"base_mva": Infinity, ...}')`. Snapshot: `allow_inf_nan` does not change
the JSON schema, so no regeneration (verify by running the snapshot test). If a named error is preferred instead,
add a finite check to `validate_network` under BAD_RANGE — but then (c) still needs the config line, because
`Infinity` must be refused at the JSON layer, not after construction.

### 2. carry-to-next-wave (M2) — `NetworkArrays.bus_type` / `v_set` are *declared* roles, not the *effective* ones MATPOWER and pandapower solve with; no fixture can tell the difference

**Where.** `src/mambo_power/numerics/arrays.py:104-106` (`bus_type` from `bus.type`), `:162-168` (`v_set` = first
in-service generator), `:99-103` (slack = declared slack, no generator required).

**Reproduction** (`p5_misc.py`):

```
a) v_set at pv bus, gens (OOS 1.05 | 1.02 | 1.07): 1.02 -- MATPOWER runpf: last in-service wins (1.07); pandapower from_ppc: first row (1.05)
b) pv bus with every gen out: bus_type = 2 v_set = 1.0 -- MATPOWER bustypes() demotes to PQ
c) slack bus with no generator accepted: gen_bus = [1] slack = 0
```

MATPOWER's `bustypes()` demotes a PV bus with no in-service generator to PQ and re-selects the reference when
the declared one has none; `runpf` seeds `V0(gbus(k)) = gen(on(k), VG)` with repeated indices, so the *last*
in-service generator's VG wins at a multi-generator bus. pandapower's `from_ppc` takes the *first* row
(acknowledged at `tests/parity/test_matpower_vs_pandapower.py:297-299`). Ours takes the first *in-service* one
— a third convention. Fixture survey (`p3_dropped_columns.py`): `multi-gen buses={}` and `gens off=0` on all five,
so AC-6/AC-7 have **zero power** over any of these three choices; the only guard is the hand-built 4-bus
unit case, which asserts our convention against itself.

**Why it matters now.** `arrays.py:47` says "as declared on the bus" — honest, but M2's Newton-Raphson will
either index PV/PQ sets from `bus_type` (wrong on real files with off generators) or re-derive them (then
`bus_type` is a trap). The epic's AC parity oracle (MATPOWER solutions + `runpp`) will disagree on exactly such
cases.

**Fix.** Decide before M2 opens: either compute effective types in `from_network` (PV→PQ when no in-service
gen; refuse/relabel a slack with no in-service gen) and document the `v_set` tie rule as MATPOWER's (last
in-service) so AC parity holds, or keep "declared" and add `effective_bus_type()` in `numerics` for M2. Either way,
add one fixture-free unit case per rule and log the chosen convention as an assumption (the spec is silent).

### 3. carry-to-next-wave (design decision for the user) — an in-service island makes an otherwise valid MATPOWER file unloadable, which contradicts Design 4's stated rationale

**Where.** `src/mambo_power/io/matpower.py:344` constructs `Network`, whose `_check_connectivity`
(`network.py:191-226`) raises DISCONNECTED_BUS for any in-service bus not reachable from the slack.

**Reproduction** (`p4_island.py` on case14, `p6_island_case30_and_s4_mutation.py` on case30 — one branch status
flipped to 0 in the file text, everything else verbatim):

```
modified line 67: 7	8	0	0.17615	0	0	0	0	0	0	0	-360	360;
matpower.loads raised NetworkValidationError:
    DISCONNECTED_BUS at buses[7]: bus "bus-8" is not connected to bus "bus-1" over in-service branches

case30 bridge chosen: branch-13 bus-9-bus-11
ours: matpower.loads raised ['DISCONNECTED_BUS at buses[10]: bus "bus-11" is not connected ...']
pandapower: from_ppc + runpp converged = True | buses with NaN result (isolated, tolerated): [11]
```

MATPOWER keeps islanded in-service buses through `ext2int` (only type 4 is removed); pandapower's `runpp`
default `check_connectivity=True` sets unsupplied buses out of service and solves. The wave spec Design 4 justifies
type-4 tolerance with "keeps real-world RAW/MATPOWER files loadable" — but the far more common real-world
shape (a `BR_STATUS = 0` that strands a bus; PEGASE/RTE/ACTIVSg cases carry many) is rejected at import. Not
an M1 defect — AC-4 specifies DISCONNECTED_BUS and the fixtures are all connected (audit survey `status0 0`) —
but it is a silent narrowing of R11 "MATPOWER import" that the `## Assumptions` ledger does not record.

**Fix (pick one, log as A15).** (a) Importer repair in the existing "repair + warn" pattern (`matpower.py:15-18`):
after building, demote every bus unreachable from the slack over in-service branches to `in_service=False`
and append a warning per bus — the model invariant stays as specified, real files load, the user sees what
happened. (b) Keep the hard error and say so in the spec's Not Doing. (a) is ~20 lines and matches pandapower's
behaviour; (b) is free. Either is defensible; leaving it unlogged is not.

### 4. carry-to-next-wave — the importer silently drops MATPOWER columns that R3/R4/R7 will need, and emits no warning, and the fixtures cannot detect it

**Where.** `matpower.py:297-342` reads bus 0-12, gen 0-9, branch 0-10, gencost 0-3+; `matpower.py:6-7` says
"ignores every field it does not know". Dropped: gen `MBASE` (6), `PC1/PC2/QC1MIN..QC2MAX` (10-15, capability
curve), `RAMP_AGC/RAMP_10/RAMP_30/RAMP_Q` (16-19), `APF` (20); branch `RATE_B/RATE_C` (6-7), `ANGMIN/ANGMAX`
(11-12); `mpc.bus_name` (A9, declared). `Generator` has no ramp or emergency-rating fields (`entities.py:88-101`,
`:48-60`).

**Evidence** (`p3_dropped_columns.py`):

```
case14       gen cols=21 br cols=13 | MBASE!=100:0 RATE_B!=RATE_A:0 RATE_C!=RATE_A:0 ANGMIN!=+-360:0 ANGMAX!=+-360:0 | ... extra sections=['bus_name']
case30       ... identical zeros ...
case_ieee30  ... identical zeros ...
case57       ... identical zeros ...
case118      ... identical zeros ...
```

Every dropped column is at its default in all five fixtures, so AC-6's "per-element values" clause is
satisfied *and* says nothing about these columns. R7 ("ramp limits") and R4 (N-1; MATPOWER's `RATE_B/C` are the
post-contingency limits) will need them; R3's parity oracle `rundcopf` enforces `ANGMIN/ANGMAX` when they are
not ±360. The wave spec does not list them, so this is not scope shortfall — but unlike the gencost 2·ngen case
(`matpower.py:361`, warned) the drop is **silent**, which is a different contract from the one the module
docstring's "repaired … reported" paragraph advertises.

**Fix.** Now (cheap, same pattern): one warning per non-default dropped column group (`RATE_B/C ≠ RATE_A`,
any `RAMP_* ≠ 0`, `|ANGMIN/ANGMAX| ≠ 360`, `MBASE ≠ baseMVA`, `PC1/PC2 ≠ 0`), so a user importing a real case
learns what was lost. Later (M3/M4/M7, additive schema change, snapshot regen): `Branch.rating_b_mva`,
`rating_c_mva`, `angle_min_deg/max_deg`; `Generator.ramp_*`. Record the deferral as an assumption.

### 5. note — PTDF/LODF have no independent oracle in the suite, though one sits in the locked env; I ran it and it passes

**Where.** PTDF evidence = dense `Bθ=P` on the 6-bus case (`tests/unit/test_numerics_dense.py:235-262`) and
properties that are true by construction (`test_ptdf_slack_column_is_zero`, `tests/property/...:126-131` —
`ptdf.py:27,35` never writes the slack column, so this assertion has zero power). LODF evidence = brute-force
rebuild on the 6-bus case only (F1). `pandapower.pypower.makePTDF` / `makeLODF` are importable in the locked
pandapower 3.3.0 and were not used.

**Falsification attempt** (`p2_ptdf_lodf_oracle.py`; ppc from an independent regex+`numpy.loadtxt` read of the
`.m` bytes, never from our importer, so the chain file → importer → arrays → `ptdf`/`lodf` is compared end to end):

```
case14       PTDF max|diff|=5.55e-16  LODF non-bridge cols max|diff|=1.39e-15  bridges=[13]
case30       PTDF max|diff|=1.17e-15  LODF non-bridge cols max|diff|=4.10e-15  bridges=[12, 15, 33]
case_ieee30  PTDF max|diff|=4.00e-15  LODF non-bridge cols max|diff|=6.00e-15  bridges=[12, 15, 33]
case57       PTDF max|diff|=1.50e-15  LODF non-bridge cols max|diff|=1.09e-14  bridges=[44]
case118      PTDF max|diff|=4.77e-15  LODF non-bridge cols max|diff|=5.33e-15  bridges=[6, 8, 112, 132, 133, 175, 176, 182, 183]
WORST PTDF 4.77e-15 WORST LODF 1.09e-14 PASS
```

(pypower's `makeLODF` returns non-finite bridge columns — `oracle bridge cols finite? False` on every fixture —
which independently confirms the bridge sets.) **The code is right.** The finding is about the record: the
matrix's AC-7 row claims fixture-level proof for PTDF/LODF that the suite does not contain (F1), and a stronger,
cheaper closure than parametrising the brute-force test exists: ~20 lines in
`tests/parity/test_ybus_vs_pandapower.py` reusing the existing `case` fixture. Recommend folding it with F1.

### 6. note — semantic mismatch between importer and native format on `rating_mva = 0`, plus three unguarded cost/limit shapes

(`p5_misc.py`) `rating_mva=0.0 accepted -> rating_pu = [0.]` — the importer maps `RATE_A 0` → `None`
(unlimited, `matpower.py:336`) but a native file's `0.0` means zero capacity; in M2/M3 every flow on such a
branch is a violation. `PolynomialCost(coefficients=[])` and `PiecewiseCost(points=[])` construct; PWL with
equal consecutive `p` (`[(0,0),(10,5),(10,9)]`, a vertical segment) passes the non-decreasing check
(`network.py:154` uses `<`, MATPOWER requires strictly increasing x). All are M3-facing; all fit the review's
proposed BAD_RANGE batch (Correctness 3) at one line each: `rating_mva > 0` when present, `len(coefficients) >= 1`,
`len(points) >= 2` with strictly increasing `p`.

### 7. note — `NetworkArrays` is `frozen=True` in name only

(`p5_misc.py` h) `arr.x[0] = 0.0` succeeds on a "frozen" instance and `bbus` then raises on the mutated value.
The dataclass freeze protects attribute rebinding, not array contents. Either `arr.setflags(write=False)` on each
array in `from_network` (then the docstring's "Frozen positional arrays" is true) or soften the docstring.
M2 solvers that scratch into these arrays would otherwise corrupt a view other code holds.

### 8. note — record / process observations not already in the audit

- **8a. Integration branch is local-only.** `git branch -a`: `epic/01-foundation` (ca10b6a) exists locally; origin
  has `main` and `wave/01-substrate` only (`gh api repos/mambo10005/mambo-power/branches` → `main`,
  `wave/01-substrate`). CI is `on: push`/`pull_request`. The Handoff authorises pushing the *wave* branch; after
  the Step-7 merge into `epic/01-foundation` nothing runs CI on the integrated state unless that branch is also
  pushed — a decision the orchestrator needs from the user before claiming post-merge green.
- **8b. Two deviations live outside `## Assumptions`.** F2 (`load(path)`/`loads(text)` vs spec `load(path_or_text)`)
  and F5 (AC-6 oracle is `from_ppc` fed by an independent reader, not `from_mpc`) are each declared in a slice
  report and the matrix line but not in the ledger the brief names as the place for them. Log as A15/A16 (F5
  should also amend AC-6's wording).
- **8c. S4 mutation table re-executed — holds.** The audit labelled s4 §2's mutation rows `unverified` (scratch
  scripts gone). I re-ran one (`p6_...py`, mutating *our* `Network`, not the file): baseline layer A/B worst `0.0`;
  after `branches[7].x += 2e-9`: `layer A worst = 2.00e-09 (> 1e-9: True) | layer B worst = 2.00e-09 (> 1e-9: True)`
  — matches the report's row verbatim. The S4 claim is authentic.
- **8d. A8 is a rationalised deviation, honestly labelled.** AC-2 says "reverted and CI is green again"; what ran
  was green-before on the wave branch, red on a throwaway branch, branch deleted. The substance (same workflow
  file, both polarities) is proven and the audit's F4 already accepts it; I agree, and note only that the
  literal sequence was never observed.
- **8e. `mypy` covers `src` only** (`pyproject.toml:56`). The tests are annotated but unchecked; W1 says
  "ruff + mypy strict" without scoping it. Not a deviation, but worth one word in the spec so M2 does not
  discover it as a surprise.

---

## Falsification attempts that failed (beyond the issues above)

1. **"AC-6/AC-7 parity is really self-consistency."** Read `test_ybus_vs_pandapower.py:52-90` and
   `test_matpower_vs_pandapower.py:46-84`: the oracle ppc is built from `read_mpc_numpy` (regex + `numpy.loadtxt`)
   and re-indexed by `BUS_I`, never from our importer or arrays; alignment is by id, not row order. The chain is
   genuinely file → two independent readers → two independent builders. Confirmed further by P2 (PTDF/LODF)
   and P6b (a 2e-9 perturbation on our side alone is caught). Not self-consistency.
2. **"The JSON schema snapshot would let an additive change pass."** `test_json_schema_snapshot.py:26-33`
   asserts dict equality against the committed file (regeneration only under `MAMBO_UPDATE_SNAPSHOTS=1`, which
   `ci.yml` never sets); the snapshot carries `additionalProperties: false` ×11 (`extra="forbid"`) and
   `schema_version: const 1`. An added optional field changes the dict → red. Holds.
3. **"CI evidence is not what the record says / R12 is breached."** `gh run view 32428177629 --json conclusion,headSha,jobs`
   → `success`, `headSha 36bd20a…`, 6/6 jobs success, no non-success step; `gh run list` shows the two red plants
   (c594112, faef8a3) on `m1/s2-planted-failure` and green on every wave commit; repo `visibility: public`
   (Actions minutes free, macOS included); `ci.yml:7-8` `permissions: contents: read`; runtime deps numpy/scipy/
   highspy/pydantic, dev oracles BSD/MIT; no paid service anywhere in the diff. Holds (actions are tag-pinned,
   already noted by the review).

---

## Merge verdict

**READY AFTER FIXES** — (1) `allow_inf_nan=False` on `_Entity` and `Network` with two negative tests, folded
into the review's fix commit alongside its Architecture 1 / Correctness 2-3 items; plus log A15 (island policy,
issue 3) and A16/A17 (F2, F5) in `## Assumptions` before Step 7. Issues 2, 4, 5, 6, 7 carry to the M2/M3 plans
(issue 5's 20-line parity test is cheap enough to fold now if the review-fold commit touches
`test_ybus_vs_pandapower.py` for F1). Issue 8a needs a user decision on pushing `epic/01-foundation`.
