# Fixture provenance — reference solutions and their sources (AC-7)

One consolidated record per fixture file: where it came from, what lineage its
data carries, what serves as the parity reference solution, and what is known
about that reference's quality. Every claim below is transcribed from an
existing in-repo record — the retrieval table in
`packages/io/test/fixtures/matpower/SOURCES.md`, this directory's `SOURCES.md`,
each fixture file's own header comments, and the AC parity suite header
(`packages/engine-pf/test/solveAcPf.test.ts`) — or from the parity suite's
printed gate output. Nothing here is asserted beyond those sources; each
section cites where its facts live.

All five files are byte-identical copies of the verbatim MATPOWER distribution
files in `packages/io/test/fixtures/matpower/` (this directory's `SOURCES.md`),
retrieved 2026-08-19 from the MATPOWER `master` branch `data/` directory via
raw.githubusercontent.com (retrieval table in the io `SOURCES.md`). Do not
edit them.

## Per-fixture record

### case14.m
- **Source:** https://raw.githubusercontent.com/MATPOWER/matpower/master/data/case14.m — retrieved 2026-08-19 (io `SOURCES.md` table).
- **Upstream lineage:** converted from IEEE Common Data Format (`ieee14cdf.txt`)
  by cdf2matp rev. 2393; UW archive, https://labs.ece.uw.edu/pstca/ —
  "08/19/93 UW ARCHIVE 100.0 1962 W IEEE 14 Bus Test Case" (file header).
- **Reference solution:** the stored VM (pu) / VA (deg) columns of `mpc.bus`,
  the solved operating point shipped by MATPOWER with the distribution
  (this directory's `SOURCES.md`; AC test header).
- **Known reference-quality findings:** no gate exclusions (measured gate
  output — see "Reference-quality findings" below).

### case30.m
- **Source:** https://raw.githubusercontent.com/MATPOWER/matpower/master/data/case30.m — retrieved 2026-08-19 (io `SOURCES.md` table).
- **Upstream lineage:** NOT CDF — based on Alsac, O. & Stott, B., "Optimal Load
  Flow with Steady State Security", IEEE Trans. PAS, Vol. PAS-93, No. 3, 1974,
  pp. 745-751, with synthetic edits recorded in the file header: branch
  parameters rounded to nearest 0.01, shunt values divided by 100, shunt on
  bus 10 moved to bus 5, load at bus 5 zeroed out; generator locations, costs,
  limits and bus areas from Ferrero, Shahidehpour & Ramesh 1997; generator Q
  limits derived from Alsac & Stott (file header).
- **Reference solution:** NONE STORED. The VM/VA columns are flat
  (VM = 1, VA = 0 on every bus row) — a flat start, not a solution — so
  case30 is BY DESIGN (orchestrator ruling 2026-08-19) excluded from column
  parity and held to convergence + the independent self-consistency check
  instead; its 30-bus parity seat is taken by case_ieee30 (AC test header).
  Every parity reference is guarded against flat stored columns before being
  trusted (AC test header; the suite's `flatReference` assertion).

### case_ieee30.m
- **Source:** https://raw.githubusercontent.com/MATPOWER/matpower/master/data/case_ieee30.m — retrieved 2026-08-19 (io `SOURCES.md` table).
- **Upstream lineage:** converted from IEEE Common Data Format
  (`ieee30cdf.txt`) by cdf2matp rev. 2393; UW archive,
  https://labs.ece.uw.edu/pstca/ — "08/20/93 UW ARCHIVE 100.0 1961 W IEEE 30
  Bus Test Case". Modification v2 (2025-06-14, WGV): tap parameter of
  branches 13, 14, 16 set to 1.0 (file header).
- **Reference solution:** stored VM/VA columns of `mpc.bus` (this directory's
  `SOURCES.md`; AC test header). Holds the 30-bus parity seat in place of the
  flat case30 (AC test header).
- **Known reference-quality findings:** bus 3 stored columns self-mismatch
  8.2 MVA > 5 MVA gate — reference defect, excluded from column comparison
  (AC test header; measured gate output).

### case57.m
- **Source:** https://raw.githubusercontent.com/MATPOWER/matpower/master/data/case57.m — retrieved 2026-08-19 (io `SOURCES.md` table).
- **Upstream lineage:** converted from IEEE Common Data Format
  (`ieee57cdf.txt`) by cdf2matp rev. 2393; UW archive,
  https://labs.ece.uw.edu/pstca/ — "08/25/93 UW ARCHIVE 100.0 1961 W IEEE 57
  Bus Test Case". Manual modification: Qmax, Qmin on generator 1 set to 200,
  -140 (file header).
- **Reference solution:** stored VM/VA columns of `mpc.bus` (this directory's
  `SOURCES.md`; AC test header).
- **Known reference-quality findings:** buses 14, 46, 47 stored columns
  self-mismatch 21.2 / 45.8 / 24.7 MVA > 5 MVA gate — the published solution
  auto-adjusted tap 14-46, which the shipped fixed-tap data does not carry
  (AC test header: "bus 46 and neighbors"; measured gate output for the full
  bus list and magnitudes).

### case118.m
- **Source:** https://raw.githubusercontent.com/MATPOWER/matpower/master/data/case118.m — retrieved 2026-08-19 (io `SOURCES.md` table).
- **Upstream lineage:** converted from IEEE Common Data Format
  (`ieee118cdf.txt`) by cdf2matp rev. 2393; UW archive,
  https://labs.ece.uw.edu/pstca/ — "08/25/93 UW ARCHIVE 100.0 1961 W IEEE 118
  Bus Test Case". baseKV data taken from the PSAP format file from the same
  site (added 10-Mar-2006); branches 86-87 and 68-116 changed from
  transmission lines to transformers (tap ratio 1) on 2019-02-15
  (file header).
- **Reference solution:** stored VM/VA columns of `mpc.bus` (this directory's
  `SOURCES.md`; AC test header). Slack bus 69 is stored at VA = 30 deg, so
  angle parity is compared slack-relative (AC test header).
- **Known reference-quality findings:** buses 17, 30, 38, 68 stored columns
  self-mismatch 45.3 / 129.7 / 31.3 / 10.5 MVA > 5 MVA gate — bus 30 shows a
  phantom 129.7 MVAr at a zero-injection bus; the CDF original carries the
  same fixed taps, so the 1961-era stored point simply does not solve the
  shipped data there (AC test header: "bus 30 and neighbors"; measured gate
  output for the full bus list and magnitudes).

## Reference-quality findings (shared context)

- **Q-limit-enforced lineage:** the stored solutions are compared under the
  AMENDED AC-4 (W1-R5, user-ratified 2026-08-19, option C): Q-limit
  enforcement ON, data-precision bands max |VM| error 2e-3 pu and max |VA|
  error 0.5 deg, slack-relative angles. The bands are set by the reference
  data itself, not the solver: the stored columns keep 3 decimals of VM and
  2 of VA and came out of CDF-era solution processes whose own convergence
  slop is measurable (AC test header).
- **Reference-quality gate:** before comparison, each stored reference bus is
  checked against the case's own power-flow equations — dense arithmetic on
  the file + its stored columns only, no engine output involved. A bus whose
  stored columns violate the shipped data by more than 5 MVA (P at non-slack
  buses, Q additionally at PQ buses) is a defective reference point, excluded
  from column comparison and printed with its magnitude; the gate is capped
  at ceil(5%) of buses per case (AC test header; `GATE_MVA` in
  `packages/engine-pf/src/parity.ts`). Measured exclusions (parity suite gate
  output, 2026-08-19 run): case_ieee30 bus 3 (8.2 MVA); case57 buses 14
  (21.2), 46 (45.8), 47 (24.7); case118 buses 17 (45.3), 30 (129.7),
  38 (31.3), 68 (10.5); case14 none.

## W9 regeneration contract

Tighter parity bands arrive with the W9 cross-engine regenerated references
contracted in the spec (ADR-002); the AC parity suite's band provenance is
that contract (AC test header). Until then the stored MATPOWER columns above,
gated as described, remain the published reference.

## Consumers

This directory is the one copy both parity runners consume — the Node suite
in `packages/engine-pf/test/` and the S8 browser harness — per W1 design
decision 3 (this directory's `SOURCES.md`).
