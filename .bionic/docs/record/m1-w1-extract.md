# M1 W1 extract — Case schema v1, MATPOWER importer, parity conventions, NR conventions

Source of truth: git repo `C:\Claude Projects\gridlab`, tag `archive/ts-w1`. Every section cites
the path under that tag; read with `git -C "C:/Claude Projects/gridlab" show archive/ts-w1:<path>`.
Extracted 2026-08-20 for canonical-sdlc wave M1 (mambo-power substrate). Read-only extraction; no
interpretation beyond what the cited file states, except where marked **note**.

---

## 1. Case schema v1

Source: `packages/schema/src/types.ts` (types), `packages/schema/src/validate.ts` (validation),
`packages/schema/src/index.ts` (re-exports both).

### 1.1 Design statements carried in the file header (`types.ts`)

| Statement | Consequence for the port |
| --- | --- |
| `SCHEMA_VERSION = 1` (const literal) | `Case.schemaVersion` is the literal `1`. |
| Market inputs (bids/offers, periods, strategies) excluded — they live on `Scenario` (W5). | No cost/market fields on any entity. |
| Generator cost fields "reserved for W2 and intentionally NOT defined". | No gencost anywhere in v1. |
| Storage and zones are "schema-present but engine-ignored until W6/W7"; validation covers them, no W1 solver reads them. | Storage/Zone must validate (ids, refs) but solvers ignore them. |
| Power quantities are stored in **MW / MVAr**, impedances in **per-unit on system base**. Engines divide by `baseMVA`. | Schema is not per-unit for powers; conversion happens at solve time. |

### 1.2 Type aliases

| Name | Definition | Notes |
| --- | --- | --- |
| `BusType` | `"slack" \| "pv" \| "pq"` | String enum; no "isolated" type. |
| `Status` | `0 \| 1` | MATPOWER convention: 1 in service, 0 out. |

### 1.3 Entities and fields

Optionality: `req` = required, `opt` = optional (`?` in TS). "Default" is the semantic default stated in
the doc comment when the field is absent (the schema itself has no defaulting code).

#### `Case` (root) — 9 fields

| Field | Type | Units | Opt | Default / constraint |
| --- | --- | --- | --- | --- |
| `schemaVersion` | `1` (literal `typeof SCHEMA_VERSION`) | — | req | must be `1` |
| `baseMVA` | `number` | MVA | req | must be `> 0` (validated: `BAD_PER_UNIT`) |
| `buses` | `Bus[]` | — | req | — |
| `branches` | `Branch[]` | — | req | — |
| `generators` | `Generator[]` | — | req | — |
| `loads` | `Load[]` | — | req | — |
| `shunts` | `Shunt[]` | — | req | — |
| `storage` | `Storage[]` | — | req | array, may be empty (importer always emits `[]`) |
| `zones` | `Zone[]` | — | req | — |

#### `Geo` — 2 fields (embedded in `Bus`, not a top-level collection)

| Field | Type | Units | Opt |
| --- | --- | --- | --- |
| `lat` | `number` | degrees | req |
| `lon` | `number` | degrees | req |

#### `Bus` — 5 fields

| Field | Type | Units | Opt | Default / constraint |
| --- | --- | --- | --- | --- |
| `id` | `string` | — | req | unique within `buses` |
| `baseKV` | `number` | kV | req | must be `> 0` (validated: `BAD_PER_UNIT`) |
| `type` | `BusType` | — | req | exactly one bus with `"slack"` across the case |
| `geo` | `Geo` | — | opt | — |
| `zone` | `string` | — | opt | must reference a `Zone.id` when present (`DANGLING_REF`) |

**Note:** Bus carries no voltage magnitude, no angle, no Vmin/Vmax, no area. Engines therefore fix
the slack angle at 0 themselves (see section 4).

#### `Branch` — 11 fields

| Field | Type | Units | Opt | Default / constraint |
| --- | --- | --- | --- | --- |
| `id` | `string` | — | req | unique within `branches` |
| `from` | `string` | — | req | bus id; must resolve (`DANGLING_REF`) |
| `to` | `string` | — | req | bus id; must resolve (`DANGLING_REF`) |
| `r` | `number` | pu on system base | req | — |
| `x` | `number` | pu on system base | req | DC solver throws if `x === 0` on an in-service branch (engine-level, not schema) |
| `b` | `number` | pu, **total** line charging | req | engines use `b/2` per end |
| `ratingMVA` | `number` | MVA | opt | absent = no rating |
| `tapRatio` | `number` | — | opt | absent means `1` (nominal); tap is on the **from** side |
| `phaseShiftDeg` | `number` | degrees | opt | absent means `0` |
| `status` | `Status` | — | req | — |

#### `Generator` — 10 fields

| Field | Type | Units | Opt | Constraint |
| --- | --- | --- | --- | --- |
| `id` | `string` | — | req | unique within `generators` |
| `bus` | `string` | — | req | must resolve (`DANGLING_REF`) |
| `pMW` | `number` | MW | req | — |
| `qMVAr` | `number` | MVAr | req | — |
| `pMinMW` | `number` | MW | req | not range-validated |
| `pMaxMW` | `number` | MW | req | not range-validated |
| `qMinMVAr` | `number` | MVAr | req | not range-validated |
| `qMaxMVAr` | `number` | MVAr | req | not range-validated |
| `vSetpointPu` | `number` | pu | req | — |
| `status` | `Status` | — | req | — |

No cost fields (comment in file: "Cost fields reserved for W2 — deliberately not defined in v1").

#### `Shunt` — 4 fields

| Field | Type | Units | Opt | Semantics |
| --- | --- | --- | --- | --- |
| `id` | `string` | — | req | unique within `shunts` |
| `bus` | `string` | — | req | must resolve (`DANGLING_REF`) |
| `gsMW` | `number` | MW at V = 1.0 pu | req | **positive = consumes** active power |
| `bsMVAr` | `number` | MVAr at V = 1.0 pu | req | **positive = injects** reactive power |

(Matches MATPOWER GS/BS sign convention; engine adds `(gsMW + j·bsMVAr)/baseMVA` to the Y-bus diagonal.)

#### `Load` — 4 fields

| Field | Type | Units | Opt |
| --- | --- | --- | --- |
| `id` | `string` | — | req (unique within `loads`) |
| `bus` | `string` | — | req (must resolve) |
| `pMW` | `number` | MW | req |
| `qMVAr` | `number` | MVAr | req |

#### `Storage` — 7 fields (schema-present, engine-ignored in W1)

| Field | Type | Units | Opt | Constraint |
| --- | --- | --- | --- | --- |
| `id` | `string` | — | req | unique within `storage` |
| `bus` | `string` | — | req | must resolve (`DANGLING_REF`) |
| `energyCapacityMWh` | `number` | MWh | req | not range-validated |
| `powerCapacityMW` | `number` | MW | req | not range-validated |
| `chargeEfficiency` | `number` | fraction | req | not range-validated |
| `dischargeEfficiency` | `number` | fraction | req | not range-validated |
| `socInitial` | `number` | fraction of `energyCapacityMWh`, doc says `[0, 1]` | req | **not validated** despite doc |

#### `Zone` — 2 fields

| Field | Type | Opt |
| --- | --- | --- |
| `id` | `string` | req (unique within `zones`) |
| `name` | `string` | req |

**Totals:** 9 interfaces (8 entities + `Geo` embedded), 54 fields.

### 1.4 Validation (`packages/schema/src/validate.ts`)

API: `validate(caseData: Case): ValidationResult` where
`ValidationResult = { ok: true } | { ok: false; errors: NamedError[] }` and
`NamedError = { code: ErrorCode; message: string }`. Collects **every** violation (does not stop at the
first). The file header states it is "the single source of truth for case validity — there is no
separate JSON-Schema document". It validates semantics only; it does not check types/shape.

Check order (as executed): unique ids → per-unit bases → references → slack → connectivity.

| `ErrorCode` | Checked by | Rule | Message format |
| --- | --- | --- | --- |
| `DUPLICATE_ID` | `checkUniqueIds` | Within each of the 7 collections (`buses, branches, generators, loads, shunts, storage, zones`), `id` must be unique. Uniqueness is **per collection**, not global. One error per repeated occurrence. | `duplicate id "<id>" in <collection>` |
| `BAD_PER_UNIT` | `checkPerUnitBases` | `baseMVA > 0`; every `bus.baseKV > 0`. (Uses `!(x > 0)`, so NaN/undefined also fail.) | `baseMVA must be > 0, got <v>` / `bus "<id>": baseKV must be > 0, got <v>` |
| `DANGLING_REF` | `checkReferences` | `bus.zone` (when present) ∈ zone ids; `branch.from`, `branch.to`, `generator.bus`, `load.bus`, `shunt.bus`, `storage.bus` ∈ bus ids. | `<kind> "<id>": <field> references missing "<ref>"` |
| `NO_SLACK` | `checkSlack` | zero buses with `type === "slack"` | `no slack bus defined` |
| `MULTIPLE_SLACK` | `checkSlack` | more than one slack | `expected exactly one slack bus, found <n>: "<id>", ...` |
| `DISCONNECTED_BUS` | `checkConnectivity` | Graph over **in-service** branches (`status === 1`) whose both endpoints resolve; DFS from the slack bus (or `buses[0]` if no slack); every bus must be reached. Skipped when `buses` is empty. Branches with dangling endpoints are silently ignored here (already reported as `DANGLING_REF`). One error per unreached bus. | `bus "<id>" is not connected to bus "<start>" over in-service branches` |

**Named validation errors: 6.** Fixtures exercising them: `packages/schema/test/fixtures/{bad-per-unit,dangling-ref,disconnected-bus,duplicate-id,multiple-slack,no-slack,valid-small}.json`.

What is **not** validated (useful for deciding what the Python port should add, if anything): generator
P/Q limit ordering, `vSetpointPu > 0`, `x !== 0`, `storage.socInitial ∈ [0,1]`, efficiency ranges,
`status ∈ {0,1}`, PV bus having a generator, `schemaVersion === 1`.

---

## 2. MATPOWER importer

Source: `packages/io/src/importMatpower.ts`; public surface re-exported from `packages/io/src/index.ts`
(`DEFAULT_BASE_KV`, `ImportError`, `importMatpower`, `ImportErrorCode`).

API: `importMatpower(source: string): Case` — takes the `.m` file text, returns a `Case` (v1,
`schemaVersion: 1`). It does **not** call `validate()`; callers validate separately. Both in-service
and out-of-service elements are imported with their status.

### 2.1 Parsing rules

| Step | Rule |
| --- | --- |
| Comments | `%` to end of line stripped globally before any parsing. |
| `baseMVA` | regex `mpc\.baseMVA\s*=\s*([^;\n]+);` — **semicolon required**; value parsed as number. |
| Matrices | `mpc\.<name>\s*=\s*\[` then body up to the **first** `]`; rows split on `;`; tokens split on whitespace; blank rows skipped. Only `bus`, `gen`, `branch` are read. |
| Minimum columns | `bus` ≥ 13, `gen` ≥ 10 (through PMIN), `branch` ≥ 11 (through BR_STATUS). Extra trailing columns are tolerated and ignored. |
| Numbers | `Number(token)`; must be finite. |
| Format version | Not checked (`mpc.version` ignored; assumes caseformat v2 column layout). |
| `mpc.gencost` | **Not read at all.** (`git grep -i gencost archive/ts-w1 -- packages/ ':!**/*.m'` returns nothing.) Cost data is dropped. |
| `mpc.bus_name`, `mpc.areas`, any other section | Not read. |

### 2.2 Importer errors (`ImportError`, class with `.code` and `.name === "ImportError"`)

| `ImportErrorCode` | When |
| --- | --- |
| `MISSING_BASE_MVA` | `mpc.baseMVA = ...;` not found |
| `MISSING_SECTION` | `mpc.bus`, `mpc.gen`, or `mpc.branch` matrix opener not found |
| `UNTERMINATED_MATRIX` | no `]` after the opener (truncated file) |
| `BAD_NUMBER` | a token (baseMVA or any matrix cell) is not a finite number |
| `BAD_ROW` | a row has fewer than the minimum columns for that matrix |
| `BAD_BUS_TYPE` | bus type code not in {1, 2, 3} — **includes MATPOWER type 4 (isolated)** |

**Named importer errors: 6.** Malformed fixtures: `packages/io/test/fixtures/malformed/{bad-number,missing-bus,truncated}.m`.

### 2.3 Column map — `mpc.bus` (0-based index in code; 1-based MATPOWER name in parentheses)

| Idx | MATPOWER col | Schema target | Conversion |
| --- | --- | --- | --- |
| 0 | `BUS_I` (1) | `Bus.id` | `String(value)` (integer → string id) |
| 1 | `BUS_TYPE` (2) | `Bus.type` | `3 → "slack"`, `2 → "pv"`, `1 → "pq"`, anything else → `ImportError BAD_BUS_TYPE` |
| 2 | `PD` (3) | `Load.pMW` | MW kept as MW; a `Load` row is emitted **only if** `PD ≠ 0 or QD ≠ 0`; id `load-<busId>`; at most one load per bus |
| 3 | `QD` (4) | `Load.qMVAr` | as above |
| 4 | `GS` (5) | `Shunt.gsMW` | MW kept as MW; a `Shunt` row is emitted **only if** `GS ≠ 0 or BS ≠ 0`; id `shunt-<busId>` |
| 5 | `BS` (6) | `Shunt.bsMVAr` | as above |
| 6 | `AREA` (7) | — | **dropped** |
| 7 | `VM` (8) | — | **dropped** by importer (read separately by `parity.ts` as the reference solution) |
| 8 | `VA` (9) | — | **dropped** by importer (same) |
| 9 | `BASE_KV` (10) | `Bus.baseKV` | if `> 0` kept; else `DEFAULT_BASE_KV = 1` (CDF-derived case14/case57 carry 0 meaning "unknown"; recorded in the W1 Assumptions ledger per the source comment) |
| 10 | `ZONE` (11) | `Bus.zone` and `Zone.id` | `String(value)`; a `Zone { id, name: "Zone <id>" }` is synthesised per distinct value, in first-appearance order. **Uses MATPOWER's loss-zone column, not `AREA`.** |
| 11 | `VMAX` (12) | — | dropped |
| 12 | `VMIN` (13) | — | dropped |

### 2.4 Column map — `mpc.gen`

| Idx | MATPOWER col | Schema target | Conversion |
| --- | --- | --- | --- |
| 0 | `GEN_BUS` (1) | `Generator.bus` | `String(value)` |
| 1 | `PG` (2) | `Generator.pMW` | MW as-is |
| 2 | `QG` (3) | `Generator.qMVAr` | MVAr as-is |
| 3 | `QMAX` (4) | `Generator.qMaxMVAr` | as-is |
| 4 | `QMIN` (5) | `Generator.qMinMVAr` | as-is |
| 5 | `VG` (6) | `Generator.vSetpointPu` | as-is |
| 6 | `MBASE` (7) | — | **dropped** (no machine-base rescaling) |
| 7 | `GEN_STATUS` (8) | `Generator.status` | `> 0 → 1`, else `0` |
| 8 | `PMAX` (9) | `Generator.pMaxMW` | as-is |
| 9 | `PMIN` (10) | `Generator.pMinMW` | as-is |
| 10+ | `PC1 … APF` | — | dropped / optional |
| — | — | `Generator.id` | `gen-<1-based row index>` |

### 2.5 Column map — `mpc.branch`

| Idx | MATPOWER col | Schema target | Conversion |
| --- | --- | --- | --- |
| 0 | `F_BUS` (1) | `Branch.from` | `String(value)` |
| 1 | `T_BUS` (2) | `Branch.to` | `String(value)` |
| 2 | `BR_R` (3) | `Branch.r` | pu as-is |
| 3 | `BR_X` (4) | `Branch.x` | pu as-is |
| 4 | `BR_B` (5) | `Branch.b` | pu as-is (total charging) |
| 5 | `RATE_A` (6) | `Branch.ratingMVA` | set **only if** `> 0`; else field absent |
| 6 | `RATE_B` (7) | — | dropped |
| 7 | `RATE_C` (8) | — | dropped |
| 8 | `TAP` (9) | `Branch.tapRatio` | set **only if** `≠ 0`; `0` (MATPOWER "no transformer") → field absent (= 1) |
| 9 | `SHIFT` (10) | `Branch.phaseShiftDeg` | set **only if** `≠ 0`; degrees as-is |
| 10 | `BR_STATUS` (11) | `Branch.status` | `> 0 → 1`, else `0` |
| 11–12 | `ANGMIN`, `ANGMAX` | — | dropped / optional |
| — | — | `Branch.id` | `branch-<1-based row index>` |

### 2.6 Other importer behaviours

| Topic | Behaviour |
| --- | --- |
| Slack choice | Not chosen by the importer — whatever bus has `BUS_TYPE = 3` becomes `"slack"`. Zero or multiple type-3 buses import fine and fail later in `validate()` (`NO_SLACK` / `MULTIPLE_SLACK`). |
| Unit conversion | **None at import.** MW/MVAr stay MW/MVAr; r/x/b stay pu; degrees stay degrees. Division by `baseMVA` happens inside the engines. |
| `gencost` | Ignored entirely (see 2.1). |
| `storage` | Always `[]` ("storage does not exist in the format"). |
| `geo` | Never set. |
| Output field order | `{ schemaVersion, baseMVA, buses, branches, generators, loads, shunts, storage, zones }` |

**Importer column-map count:** 26 columns mapped to schema fields (bus 8, gen 9, branch 9); 0 from
gencost; 11 columns explicitly dropped within the required widths (bus AREA/VM/VA/VMAX/VMIN, gen MBASE,
branch RATE_B/RATE_C, plus the optional ANGMIN/ANGMAX and gen OPF columns).

---

## 3. Parity conventions

Sources: `packages/engine-pf/src/parity.ts`, `packages/engine-pf/fixtures/matpower/PROVENANCE.md`,
`packages/engine-pf/fixtures/matpower/SOURCES.md`, `packages/io/test/fixtures/matpower/SOURCES.md`,
header of `packages/engine-pf/test/solveAcPf.test.ts`.

### 3.1 Fixtures and where the reference came from

All five `.m` files under `packages/engine-pf/fixtures/matpower/` are byte-identical copies of
`packages/io/test/fixtures/matpower/`, which are verbatim MATPOWER `master` `data/` files retrieved
2026-08-19 from `https://raw.githubusercontent.com/MATPOWER/matpower/master/data/<file>`. "Do not edit."

| Fixture | Buses | Upstream lineage | Reference solution | Role in parity | Known reference defects (gate exclusions, measured 2026-08-19) |
| --- | --- | --- | --- | --- | --- |
| `case14.m` | 14 | IEEE CDF `ieee14cdf.txt` via cdf2matp rev. 2393; UW archive (1962 W IEEE 14 Bus) | stored `VM`/`VA` columns of `mpc.bus` | AC column parity | none |
| `case30.m` | 30 | **Not CDF** — Alsac & Stott 1974 with synthetic edits (branch params rounded to 0.01, shunts ÷100, bus-10 shunt moved to bus 5, bus-5 load zeroed); gens/costs/limits from Ferrero, Shahidehpour & Ramesh 1997 | **none** — stored columns are flat (VM = 1, VA = 0 everywhere) | excluded from column parity by design (orchestrator ruling 2026-08-19); held to convergence + self-consistency only | n/a |
| `case_ieee30.m` | 30 | IEEE CDF `ieee30cdf.txt` via cdf2matp rev. 2393; UW archive (1961 W IEEE 30 Bus); v2 mod 2025-06-14: taps of branches 13, 14, 16 set to 1.0 | stored `VM`/`VA` columns | AC column parity (takes the 30-bus seat) | bus 3 (8.2 MVA) |
| `case57.m` | 57 | IEEE CDF `ieee57cdf.txt` via cdf2matp rev. 2393; UW archive; manual mod: gen 1 Qmax/Qmin = 200/−140 | stored `VM`/`VA` columns | AC column parity | buses 14 (21.2), 46 (45.8), 47 (24.7) MVA — published solution auto-adjusted tap 14-46, fixed-tap data does not carry it |
| `case118.m` | 118 | IEEE CDF `ieee118cdf.txt` via cdf2matp rev. 2393; UW archive; baseKV from PSAP file (2006); branches 86-87 and 68-116 made transformers tap 1 (2019-02-15) | stored `VM`/`VA` columns; slack bus 69 stored at VA = 30° | AC column parity (slack-relative angles) | buses 17 (45.3), 30 (129.7 — phantom MVAr at a zero-injection bus), 38 (31.3), 68 (10.5) MVA |

Reference values per fixture are therefore: per bus, `VM` (pu, 3 decimals) and `VA` (deg, 2 decimals),
read straight from `mpc.bus` columns 8 and 9 (1-based) by `parity.storedSolution(source)`. No branch-flow
or slack-injection reference values exist. DC has no stored reference; it is checked against an
in-suite dense solve.

### 3.2 Tolerances and gates (constants exported from `parity.ts`)

| Constant | Value | Meaning |
| --- | --- | --- |
| `VM_TOL_PU` | `2e-3` | max abs \|VM\| error, pu, over non-excluded buses (W1-R5 band, set by reference-data precision) |
| `VA_TOL_DEG` | `0.5` | max abs \|VA\| error, degrees, **slack-relative**: compares `(va_got − va_got_slack)` to `(va_ref − va_ref_slack)` |
| `GATE_MVA` | `5` | reference-quality gate: a bus whose **stored** columns violate the case's own equations by `> 5 MVA` is excluded from column comparison |
| gate cap | `ceil(0.05 · nBuses)` | more exclusions than this → `gateOverflow` → case fails |
| `SELF_CONSISTENCY_TOL_PU` | `1e-6` | dense recomputation of engine output must balance specified injections within this (P at all non-slack buses; Q at PQ buses only — effective PV buses and Q-limit-pinned buses keep Q free) |
| `DC_DENSE_TOL` | `1e-10` | engine DC vs dense Gaussian-elimination DC: angles (deg) **and** flows (MW), strict `<` |

Gate rule detail (`referenceQualityGate`): for each non-slack bus, `dp = |P_calc − P_spec|`; `dq` is
computed only for `type === "pq"` buses (PV-lineage buses have Q free); `worstMVA = max(dp, dq) · baseMVA`;
excluded if `worstMVA > GATE_MVA`. Inputs are the Case plus stored columns only — engine-independent.

### 3.3 Verdict runners (what a parity test asserts)

| Runner | Inputs | `pass` condition |
| --- | --- | --- |
| `checkAcParity(name, source, case)` | solves with `enforceQLimits: true` | `!flatReference && converged && !gateOverflow && maxVmErrPu ≤ 2e-3 && maxVaErrDeg ≤ 0.5` |
| `checkAcSelfConsistency(name, case, enforceQLimits, tol=1e-6)` | engine solve, dense recheck | `converged && violations.length === 0` |
| `checkDcDense(name, case)` | engine DC vs dense DC | `maxAngleErrDeg < 1e-10 && maxFlowErrMW < 1e-10` |

AC parity case list in the test: `["case14", "case_ieee30", "case57", "case118"]`; `case30` goes to
self-consistency only. `flatReference` is true when every stored bus has `vm === 1 && va === 0`.

Dense reference model (`branchBlocks`): `ys = 1/(r + jx)`, `ych = j·b/2`, `a = t·e^{jθ}`;
`yff = (ys + ych)/t²`, `yft = −ys/conj(a)`, `ytf = −ys/a`, `ytt = ys + ych`; shunts add
`(gsMW + j·bsMVAr)/baseMVA` on the diagonal — identical to the engine's model (section 4).

### 3.4 Provenance statements worth carrying forward

- Bands are "set by the reference data itself, not the solver" (3 decimals VM, 2 decimals VA, CDF-era
  convergence slop). Tighter bands are deferred to a "W9 cross-engine regenerated references" contract
  (ADR-002 in the gridlab spec). Until then the gated stored columns are the published reference.
- The single `fixtures/matpower/` directory under `engine-pf` is the one copy consumed by both the
  Node suite and the browser (S8) harness ("W1 design decision 3").

---

## 4. NR / Q-limit / DC conventions (for M2)

Sources: `packages/engine-pf/src/solveAcPf.ts`, `packages/engine-pf/src/solveDcPf.ts`,
`packages/solver-port/src/types.ts` (param/result shapes).

### 4.1 AC Newton-Raphson (`solveAcPf(case, params?)`)

| Convention | Value / rule |
| --- | --- |
| Formulation | Full NR, polar form; full Jacobian rebuilt and sparse-LU-factorised every iteration (`@gridlab/numerics` CSR + LU). State = `[θ at non-slack buses; |V| at non-voltage-holding buses]`. |
| `DEFAULT_TOLERANCE` | `1e-8` pu, on the **infinity norm** of the power mismatch vector (P rows for non-slack, Q rows for PQ/pinned). Converged when `worst < tolerance` (strict). |
| `DEFAULT_MAX_ITERATIONS` | `20` |
| `DEFAULT_MAX_QLIMIT_ROUNDS` | `10` outer rounds |
| Params (`PfAcParams`) | `tolerance?`, `maxIterations?`, `enforceQLimits?` (default **false**) |
| Iteration count semantics | mismatch checked before each step; `iterations` = number of NR updates applied (0 if flat start already satisfies tolerance). Loop `for iter = 0..maxIterations` inclusive, so at most `maxIterations` updates. |
| Y-bus | In-service branches only; MATPOWER branch model with tap on from side, `a = tap·e^{j·shift}`; `yff = (ys + j·b/2)/tap²`, `ytt = ys + j·b/2`, `yft = −ys/conj(a)`, `ytf = −ys/a`; shunts `(gsMW + j·bsMVAr)/baseMVA` on diagonal. |
| Specified injections | pu on `baseMVA`: sum of **in-service** generators' `pMW/qMVAr` minus all loads' `pMW/qMVAr`. Out-of-service generators contribute nothing (also not to Q limits or setpoint). |
| Slack | The single `type === "slack"` bus; angle fixed at **0 rad** (Case carries no angles); `|V|` = first in-service generator's `vSetpointPu` at that bus, or `1.0` if none. Never converted to PQ. |
| PV bus | `|V|` held at the **first in-service generator's** `vSetpointPu` at that bus; a PV bus with no in-service generator **degrades to PQ**. |
| Flat start | Round 1: PQ buses `|V| = 1.0`, `θ = 0`; PV/slack at setpoint, `θ = 0`. Later Q-limit rounds **warm-start** from the previous solve. |
| Q-limit rule (when `enforceQLimits`) | After each converged solve, for every effective PV bus (not slack): `qGen = qCalc − qLoad`; if `qGen > ΣqMax + ε` pin as PQ at `ΣqMax + qLoad` (side `"max"`); if `qGen < ΣqMin − ε` pin at `ΣqMin + qLoad` (side `"min"`). Limits are **aggregate** over the bus's in-service generators. `ε = 1e-9` pu. |
| PQ→PV restore | A pinned bus returns to PV (and `|V|` reset to setpoint) when `side === "max"` and `vm > setpoint + ε`, or `side === "min"` and `vm < setpoint − ε`. |
| Round cap | If changes are still occurring after `DEFAULT_MAX_QLIMIT_ROUNDS` (10) re-solves → `settled = false`, `converged = false`, message `Q-limit enforcement did not settle within 10 rounds`. `iterations` in the result is the **total** across rounds. |
| Failure modes → `converged: false` (never throws) | iteration cap; `SingularMatrixError` from LU; non-finite mismatch (NaN/Inf). Last usable iterate is returned. |
| Failure modes → throws `Error` | no slack bus; any reference to an unknown bus ("validate the case first"). |
| Result (`AcPfResult = PfAcResult & { qLimits?: AcQLimitInfo }`) | `converged`, `iterations`, `busVoltages[{bus, vmPu, vaDeg}]`, `branchFlows[{branch, pFromMW, qFromMVAr, pToMW, qToMVAr}]` (out-of-service → all zeros), `slack {bus, pMW, qMVAr}` (= `pCalc/qCalc` at slack × base). `qLimits` present iff `enforceQLimits`: `{ settled, rounds, limitedBuses (bus order), message? }`. |
| Branch flow | `If = yff·Vf + yft·Vt`, `Sf = Vf·conj(If)`; likewise `It = ytf·Vf + ytt·Vt`, `St = Vt·conj(It)`; scaled by `baseMVA`. |

### 4.2 DC power flow (`solveDcPf(case)`) — no parameters (`PfDcParams = Record<string, never>`)

| Convention | Value / rule |
| --- | --- |
| B' | in-service branches; per-branch `b = 1/(x · tapRatio)`; `r` and line-charging `b` ignored. |
| Phase shifters | equivalent injections: `+b·s` at from bus, `−b·s` at to bus (`s` in radians). |
| Injections | `Σ in-service gen pMW − Σ load pMW − Σ shunt gsMW`, all `/baseMVA` (matches MATPOWER `dcpf`, `Pbus` includes `−GS/baseMVA`). `bsMVAr` unused. |
| Slack | angle 0; slack row/column removed; solved via sparse LU. |
| Flow | `pMW = b·(θf − θt − s)·baseMVA`, signed from→to; out-of-service branches report exactly `0`. |
| Throws | no slack; unknown bus; in-service branch with `x === 0`; `SingularMatrixError` propagates (islanded in-service network is structural, not swallowed — "WA-15"). |
| Result (`PfDcResult`) | `busAngles[{bus, vaDeg}]`, `branchFlows[{branch, pMW}]`. |

### 4.3 Solver-port envelope (context only; `packages/solver-port/src/types.ts`)

`ANALYSIS_KINDS = ["pf.ac","pf.dc","opf.dc","n1","market.nodal","market.zonal","market.multiperiod","market.agents"]`;
only `pf.ac`/`pf.dc` have concrete payloads in W1. Everything crossing the port must be plain JSON
(`JSON.parse(JSON.stringify(x))` deep-equals `x`). `SolveRequest { kind, caseData, params, jobId }`,
`SolveResult { engine {id, version}, status: "ok"|"error"|"cancelled", data?, diagnostics { elapsedMs?, iterations?, messages[] } }`.

---

## Surprises / things the port must decide on

1. `mpc.gencost` is never parsed — cost import does not exist in W1 (W2 reserved it).
2. `Bus.zone` is populated from MATPOWER's **`ZONE`** (loss zone, col 11), not `AREA` (col 7).
3. MATPOWER bus type 4 (isolated) is a hard `ImportError`, not an out-of-service bus.
4. `baseKV ≤ 0` is silently replaced with `1` (case14, case57 carry zeros).
5. Loads and shunts are emitted only for non-zero rows; ids are derived (`load-<bus>`, `shunt-<bus>`,
   `gen-<n>`, `branch-<n>`), so round-tripping original MATPOWER row identity relies on ordering.
6. Q-limits are enforced per **bus aggregate** (sum of qMin / sum of qMax over in-service generators),
   not per generator; `PfAcParams.enforceQLimits` defaults to **false** but the parity suite runs with
   it **true**.
7. `Storage.socInitial` documents a `[0,1]` range that nothing validates.
8. The AC `iterations` result aggregates across Q-limit rounds, and convergence is reported `false`
   when the PV/PQ partition fails to settle even though the last inner NR converged.
