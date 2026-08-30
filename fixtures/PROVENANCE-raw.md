# PSS/E RAW v33 fixtures — provenance and hand derivations (M8 W4, AC-4)

Two hand-authored files, both NOT upstream bytes and both consumed only by
`tests/unit/test_io_psse_raw.py` through `mambo_power.io.psse_raw`. Neither
carries a reference power-flow solution. The record layouts follow the v33
field order recorded in `.bionic/docs/record/m8-research.md` §3 (from
grg-pssedata `struct.py`, BSD-3, and MATPOWER `psse_convert.m` /
`psse_convert_xfmr.m`, BSD-3); no upstream RAW file was copied (the only
public IEEE-14 RAW found carries no detectable licence — spec "Rejected
alternatives").

Layout common to both: line 1 `IC, SBASE, REV, XFRRAT, NXFRAT, BASFRQ`
(`IC=0`, `REV=33`), two title lines, then the sections in v33 order — bus,
load, fixed shunt, generator, non-transformer branch, transformer, area,
two-terminal DC, VSC DC, impedance correction, multi-terminal DC,
multi-section line, zone, inter-area transfer, owner, FACTS, switched shunt,
GNE, induction machine — each closed by a line whose first field is `0`, and
`Q` at the end. Text after `/` outside quotes is a comment.

## case14_v33.raw — transcription of `matpower/case14.m`

Authored 2026-08-29 field by field from `fixtures/matpower/case14.m` (the
verbatim MATPOWER file; its own provenance is in `fixtures/matpower/PROVENANCE.md`).
`io.psse_raw.load(case14_v33.raw)` must equal `io.matpower.load(case14.m)` on
every bus, branch (including `kind`), generator-limit and load field to 1e-9
(AC-4). Every field of every record is one of: a `case14.m` cell (mapping
below), a v33 default that the importer ignores, or a derived id.

### Bus records (14) — `mpc.bus` row → bus record

| RAW field | source | unit |
| --- | --- | --- |
| `I` | `BUS_I` | — |
| `NAME` | `mpc.bus_name` row (informational; the model has no bus name) | — |
| `BASKV` | `BASE_KV` = **0** in `case14.m` (CDF "unknown"); kept as 0 so that both importers apply the same `BASE_KV_REPLACED` repair to 1.0 — writing 138 kV would make `base_kv` differ from the `.m` import | kV |
| `IDE` | `BUS_TYPE` (3 slack, 2 PV, 1 PQ) — same code table | — |
| `AREA`, `ZONE` | `AREA`, `ZONE` (all 1) | — |
| `OWNER` | 1 (default; ignored) | — |
| `VM`, `VA` | `VM`, `VA` | pu, deg |
| `NVHI`, `NVLO` | `VMAX`, `VMIN` (1.06 / 0.94) | pu |
| `EVHI`, `EVLO` | copies of `VMAX`, `VMIN` (ignored by the importer) | pu |

### Load records (11) — `PD`/`QD` of each bus row with a non-zero pair

`I` = `BUS_I`, `ID` = `'1 '`, `STATUS` = 1, `AREA`/`ZONE` = the bus's,
`PL` = `PD` (MW), `QL` = `QD` (MVAr), `IP IQ YP YQ` = 0 (no current- or
admittance-type load in MATPOWER), `OWNER` 1, `SCALE` 1, `INTRPT` 0. Buses
1, 7 and 8 have `PD = QD = 0` and get no record, exactly as `io.matpower`
emits no `Load` for them. Importer id `load-<I>-<ID>` (`load-2-1`, …) versus
matpower's `load-<I>`; the AC-4 test matches loads by bus.

### Fixed shunt (1) — `GS`/`BS` of bus 9

`9,'1 ',1, GL=0.000 (GS, MW), BL=19.000 (BS, MVAr)`; same sign convention as
MATPOWER (positive `BL` injects). Only bus 9 has a non-zero `GS`/`BS` pair.

### Generator records (5) — `mpc.gen` row → generator record

| RAW field | source |
| --- | --- |
| `I`, `ID` | `GEN_BUS`, `'1 '` |
| `PG`, `QG` | `PG`, `QG` (MW, MVAr) |
| `QT`, `QB` | `QMAX`, `QMIN` |
| `VS` | `VG` |
| `IREG` | 0 (default; ignored) |
| `MBASE` | `MBASE` = 100 (ignored by the model) |
| `ZR ZX RT XT GTAP` | 0, 1, 0, 0, 1 (v33 defaults; ignored) |
| `STAT` | `GEN_STATUS` |
| `RMPCT` | 100 (default; ignored) |
| `PT`, `PB` | `PMAX`, `PMIN` |
| `O1..F4`, `WMOD`, `WPF` | 1,1.0,0,1.0,0,1.0,0,1.0,0,1.0 (defaults; ignored) |

Costs: `mpc.gencost` has **no RAW representation** — no v33 section carries
economic data (research §3) — so every imported generator has `cost=None` and
the importer reports `RAW_NO_COSTS` once. `PC1..APF` of `mpc.gen` are not
read by `io.matpower` either.

### Non-transformer branch records (17) — `mpc.branch` rows with `TAP = 0`

`I`=`F_BUS`, `J`=`T_BUS`, `CKT`=`'1 '`, `R`=`BR_R`, `X`=`BR_X`, `B`=`BR_B`
(pu on SBASE = baseMVA = 100), `RATEA RATEB RATEC` = `RATE_A RATE_B RATE_C`
= 0 (unrated → `rating_mva=None` in both importers), `GI BI GJ BJ` = 0,
`ST` = `BR_STATUS`, `MET` 1, `LEN` 0, owners default. Importer id
`branch-<I>-<J>-<CKT>`; matched by `(from, to)` in the test.

### Two-winding transformer records (3) — `mpc.branch` rows 8, 9, 10 (`TAP ≠ 0`)

case14's branches 4-7 (tap 0.978), 4-9 (0.969) and 5-6 (0.932) are written as
four-line transformer records with **CW=1, CZ=1, CM=1** so the round-trip is
exact by construction:

- line 1: `I, J, K=0 (two-winding), CKT='1 ', CW=1, CZ=1, CM=1, MAG1=0, MAG2=0,
  NMETR=2, NAME='', STAT=BR_STATUS, owners default, VECGRP=''`
- line 2: `R1-2 = BR_R, X1-2 = BR_X` — with CZ=1 these are pu on system
  SBASE, i.e. the `.m` values verbatim; `SBASE1-2 = 100` (unused for CZ=1)
- line 3: `WINDV1 = TAP` — with CW=1 a pu turns ratio on the bus base, so
  `tap = WINDV1 / WINDV2 = TAP / 1.0`; `NOMV1 = 0` (= bus base), `ANG1 = SHIFT
  = 0`, `RATA1 = RATE_A = 0` (→ `None`), `RATB1 RATC1` 0, `COD1 = 0` (no
  control), `CONT1 0`, `RMA1 RMI1 VMA1 VMI1` 1.1/0.9 (control limits; ignored),
  `NTP1 33`, `TAB1 0`, `CR1 CX1 CNXA1` 0
- line 4: `WINDV2 = 1.0, NOMV2 = 0`

`BR_B` is 0 on all three rows, matching the transformer model (`b = 0`).
`Branch.kind` is `"transformer"` for these records (set from the record type,
not inferred from the tap) and `"line"` for the 17 branch records — equal to
what `io.matpower` derives from the `TAP` column on this file.

### Area, zone

`1, ISW=1, PDES=0, PTOL=999.99, ARNAME='IEEE14'` (the importer keeps only the
bus `AREA` label); zone `1,'1'` → `Zone(id="1", name="1")` (matpower yields
`name=None`; zones are outside the AC-4 field comparison).

## synthetic_quirks_v33.raw — hand-derived expected network

Authored 2026-08-29; 4 buses, SBASE 100 MVA, 50 Hz header. Purpose: every
conversion branch of the importer that `case14_v33.raw` does not reach.
Quirks present: CZ=2 and CZ=3, CW=2 and CW=3, CM=2, a neutral-tap (1.0 / 0 deg)
transformer, the four-line transformer
record continuation, two circuits between one bus pair (`CKT '1'` / `'2'`),
a ZIP load, two loads (plus one out-of-service) on one bus, a fixed shunt,
branch end shunts (`BI`, `GJ`), a 9-field bus record (no `NVHI..EVLO`), a
short generator record (no owner fields), a quoted name containing a comma,
trailing `/` comments on data lines, an out-of-service generator, and ignored
records: one owner, one switched shunt.

### Buses

| id | base_kv | type | vm | va | v_min | v_max | area | zone |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `bus-1` | 138 | slack | 1.00 | 0.0 | 0.9 | 1.1 | `"1"` | `"1"` |
| `bus-2` | 138 | pq | 0.95 | -2.5 | 0.9 | 1.1 | `"1"` | `"1"` |
| `bus-3` | 13.8 | pv | 1.02 | -1.0 | 0.95 | 1.05 | `"2"` | `"1"` |
| `bus-4` | 13.8 | pq | 1.00 | -3.0 | `None` | `None` | `"2"` | `"2"` |

Zones: `Zone("1", name="ZONE-A")`, `Zone("2", name="ZONE-B")`.

### Loads (MATPOWER rule: `P = PL + IP·VM + YP·VM²`, same for Q, at the bus's VM)

- `load-2-1` at `bus-2`, VM = 0.95: `p = 40 + 10·0.95 + 20·0.95² = 40 + 9.5 +
  18.05 = 67.55` MW; `q = 10 + 2·0.95 + 4·0.9025 = 10 + 1.9 + 3.61 = 15.51`
  MVAr; reported `RAW_LOAD_ZIP_FOLDED`.
- `load-4-1`: 20 / 5; `load-4-2`: 5 / 1; `load-4-3`: 99 / 99 with
  `in_service=False` (STATUS 0).

### Shunts

- `shunt-2-1` (fixed shunt): `g_mw = 1.0`, `b_mvar = 15.0`.
- `shunt-branch-1-2-2-i` at `bus-1` from branch `1-2 '2'` end shunt `BI = 0.01`
  pu: `b_mvar = 0.01 · 100 = 1.0`, `g_mw = 0`; `shunt-branch-1-2-2-j` at
  `bus-2` from `GJ = 0.002` pu: `g_mw = 0.2`, `b_mvar = 0`. Reported
  `RAW_BRANCH_END_SHUNT_FOLDED` (one entry per end).
- `shunt-xfmr-2-3-1` at `bus-2` from T1's magnetising branch (CM=2, below):
  `g_mw = 0.02`, `b_mvar = -0.9997999799959989`. Reported
  `RAW_XFMR_MAGNETISING_FOLDED`.

### Generators

- `gen-1-1` at `bus-1`: p 50, q 0, q_max 100, q_min -100, v_set 1.0, p_max 200,
  p_min 0, in service.
- `gen-3-1` at `bus-3`: p 30, q 5, q_max 50, q_min -20, v_set 1.02, p_max 80,
  p_min 10, in service.
- `gen-3-2` at `bus-3` (18-field record): p 0, q 0, q_max 10, q_min -10, v_set
  1.02, p_max 20, p_min 0, `in_service=False` (STAT 0).
- All `cost=None`; `RAW_NO_COSTS` reported once.

### Lines (non-transformer branch records)

- `branch-1-2-1`: r 0.01, x 0.1, b 0.02, rating 150, kind `line`, no tap/shift.
- `branch-1-2-2`: r 0.02, x 0.2, b 0.04, rating 100, kind `line`.

### T1 — `branch-2-3-1`, CW=2, CZ=2, CM=2 (kind `transformer`)

Record: `R1-2 = 0.005, X1-2 = 0.08, SBASE1-2 = 50`; `WINDV1 = 144.9` kV,
`NOMV1 = 0` (→ bus 2 base 138 kV), `ANG1 = 0`, `RATA1 = 60`; `WINDV2 = 13.8`
kV, `NOMV2 = 0`; `MAG1 = 20000` W, `MAG2 = 0.02`.

- CZ=2: `R, X` are pu on `SBASE1-2` and `NOMV1`. Impedance base conversion
  (`psse_convert_xfmr.m`): `factor = Zb_winding / Zb_system =
  (NOMV1² / SBASE1-2) / (BASKV_I² / SBASE) = (138/138)² · 100/50 = 2`.
  `r = 0.005 · 2 = 0.01`, `x = 0.08 · 2 = 0.16`.
- CW=2: winding voltages in kV, each divided by its bus base:
  `t1 = 144.9 / 138 = 1.05`, `t2 = 13.8 / 13.8 = 1.0`; `tap_ratio = t1 / t2
  = 1.05`; `shift_deg = None` (ANG1 = 0).
- CM=2: `MAG1` no-load loss in W, `MAG2` exciting current pu on `SBASE1-2`
  and `NOMV1`. `G_w = 20000 / (1e6 · 50) = 0.0004`; `B_w = -sqrt(MAG2² −
  G_w²) = -sqrt(0.0004 − 0.00000016) = -sqrt(0.00039984) =
  -0.01999599959991998` (inductive, negative). To system base admittance
  scales by `SBASE1-2 / SBASE = 0.5`, then to physical: `g_mw = 0.0004 · 0.5 ·
  100 = 0.02` MW, `b_mvar = -0.01999599959991998 · 0.5 · 100 =
  -0.9997999799959989` MVAr, placed at the from bus `bus-2` as
  `shunt-xfmr-2-3-1`.
- `rating_mva = 60`, `b = 0`, in service.

### T2 — `branch-3-4-1`, CW=3, CZ=3, CM=1 (kind `transformer`)

Record: `R1-2 = 10000` (W, load loss), `X1-2 = 0.12` (|Z| pu on `SBASE1-2`),
`SBASE1-2 = 25`; `WINDV1 = 0.98` (pu of `NOMV1`), `NOMV1 = 14.49` kV,
`ANG1 = 5.0`, `RATA1 = 30`; `WINDV2 = 1.0`, `NOMV2 = 0`; `MAG1 = MAG2 = 0`.

- CZ=3: `R_w = 10000 / (1e6 · 25) = 0.0004` pu on the winding base;
  `X_w = sqrt(0.12² − 0.0004²) = sqrt(0.0144 − 0.00000016) =
  sqrt(0.01439984) = 0.11999933333148147`.
  `factor = (NOMV1 / BASKV_3)² · SBASE / SBASE1-2 = (14.49/13.8)² · 100/25 =
  1.05² · 4 = 1.1025 · 4 = 4.41`.
  `r = 0.0004 · 4.41 = 0.001764`, `x = 0.11999933333148147 · 4.41 =
  0.5291970599918333`.
- CW=3: winding voltages in pu of nominal, converted to pu of bus base by
  `NOMV / BASKV` (`NOMV = 0` → 1): `t1 = 0.98 · 14.49 / 13.8 = 0.98 · 1.05 =
  1.029`, `t2 = 1.0`; `tap_ratio = 1.029`; `shift_deg = 5.0`.
- CM=1 with `MAG1 = MAG2 = 0`: no magnetising shunt, no report entry.
- `rating_mva = 30`, `b = 0`, in service.

### T3 — `branch-2-4-1`, CW=1, CZ=1, CM=1, neutral tap (kind `transformer`; spec A7 / AC-6)

Record: `R1-2 = 0.002, X1-2 = 0.05, SBASE1-2 = 100`; `WINDV1 = 1.0`, `NOMV1 = 0`,
`ANG1 = 0`, `RATA1 = 40`; `WINDV2 = 1.0`, `NOMV2 = 0`; `MAG1 = MAG2 = 0`.

- CZ=1: `r = 0.002`, `x = 0.05` verbatim (pu on SBASE).
- CW=1: `t1 = 1.0`, `t2 = 1.0`; `tap_ratio = 1.0 / 1.0 = 1.0` — nominal; `shift_deg =
  None` (ANG1 = 0). Nothing about the parameters distinguishes this branch from a
  line: `kind = "transformer"` comes only from the record type, which is what the
  fixture exists to prove (`Branch._default_kind` would infer `"line"` here).
- `rating_mva = 40`, `b = 0`, in service; no magnetising shunt, no report entry.
- Adds the loop 2-3-4-2; the network stays one island.

### Ignored records (one report entry each)

- owner `1,'OWNER ONE'` → `RAW_SECTION_IGNORED` naming section `owner`,
  record `1`.
- switched shunt at bus 4 (`BINIT = 5.0`) → `RAW_SWITCHED_SHUNT_IGNORED`
  naming bus 4 (`BINIT` is **not** folded into a shunt; the entry says so).

Areas (`AREA HV`, `AREA MV`) contribute nothing beyond the bus labels and are
not reported (they are read, not ignored).

### Not in this file

A three-winding transformer (five-line record, `K ≠ 0`) is exercised by an
inline text in `tests/unit/test_io_psse_raw.py` (each such record →
`RAW_THREE_WINDING_IGNORED`, one entry), so this fixture stays a network the
model accepts unchanged.
