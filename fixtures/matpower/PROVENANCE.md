# Fixture provenance — reference solutions and their sources (AC-7)

One consolidated record per fixture file: where it came from, what lineage its
data carries, what serves as the parity reference solution, and what is known
about that reference's quality. Every claim below is transcribed from an
existing in-repo record — this directory's own `SOURCES.md`, each fixture
file's own header comments, and the AC parity test headers under
`tests/parity/` — or from those tests' own printed gate output. Nothing here
is asserted beyond those sources; each section cites where its facts live.

The five M1 files are byte-identical copies of the verbatim MATPOWER distribution
files (this directory's `SOURCES.md`), retrieved 2026-08-19 from the MATPOWER
`master` branch `data/` directory via raw.githubusercontent.com (retrieval
table below). The sixth file, `case300.m`, was retrieved the same way on
2026-08-20 and is pinned by git blob SHA-1 and sha256 (its section below;
`tests/unit/test_fixture_case300.py` re-checks the digest). Do not edit them.

Synthetic variants for AC-4 / AC-5 live in `derived/` with their own
`derived/PROVENANCE.md`; they are not upstream bytes and are not in the parity
fixture list.

## Licence (applies to every file in this directory)

The case files are carried as public IEEE test data as distributed by MATPOWER.
No BSD claim is made for them: MATPOWER's `LICENSE` (master, sha256
`5d14c09b3e4f2adf62c0373e6320163697aa4603186f8925c07c6b84201e1750`, fetched
2026-08-20) opens with

> The code in MATPOWER is distributed under the 3-clause BSD license below. The
> MATPOWER case files distributed with MATPOWER are not covered by the BSD
> license. In most cases, the data has either been included with permission or
> has been converted from data available from a public source.

and none of the case files carries a licence line of its own (only the
"MATPOWER" mark and the CDF provenance in its header). The underlying data are
the IEEE test cases published by the University of Washington Power Systems
Test Case Archive (https://labs.ece.uw.edu/pstca/), converted by MATPOWER's
`cdf2matp`, plus MATPOWER's documented edits (each file's header).

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

### case300.m
- **Source:** https://raw.githubusercontent.com/MATPOWER/matpower/master/data/case300.m — retrieved 2026-08-20 (M2 S1, `curl -sSL`). Pinned: git blob SHA-1 `004203b8adae83b3f21ce9ceb4a13db9b18f0132` (`git hash-object`), sha256 `69a90280e999ef533d94656e0fbc08311f1347c962dd2753ff2005ff5e3f9ac5`, 66034 bytes, LF line endings (`.gitattributes` keeps `*.m` unnormalised). The same three values were recorded independently in `record/m2-research.md` §4.1 on 2026-08-20 against the GitHub contents API.
- **Upstream lineage:** converted from IEEE Common Data Format
  (`ieee300cdf.txt`) on 18-Nov-2014 by cdf2matp rev. 2393; UW archive,
  https://labs.ece.uw.edu/pstca/ — "13/05/91 CYME INTERNATIONAL 100.0 1991 S
  IEEE 300-BUS TEST SYSTEM" (file header). Modification v2 (2025-06-14, WGV):
  "Set tap parameter of branches # 71, 90, 188, 189, 190, 191, 192, 193, 208,
  232, 233, 267, 279, 299, 310, 313, 315, 316, 318, 320, 324, and 325 to 1.0
  to model transformers with nominal turns ratio" — 22 branches (file header;
  all 22 rows carry TAP = 1.0 in the file). MATPOWER Case Format version 2,
  baseMVA 100; 300 bus rows, 69 gen rows, 411 branch rows, 69 gencost rows;
  no type-4 buses; no BASE_KV <= 0; slack = bus 7049 (stored VM 1.0507,
  VA 0, 13.8 kV); one negative-reactance branch (row 179, 1201-120,
  x = -0.3697); no phase shifters (`record/m2-research.md` §4.1; counts
  re-checked by `tests/unit/test_fixture_case300.py`).
- **Licence:** see "Licence" above — public IEEE data as distributed by
  MATPOWER, not covered by MATPOWER's BSD licence (`record/m2-research.md`
  §4.2).
- **Reference solution:** the stored VM/VA columns (4 / 2 decimals) are a
  CDF-era (1991) solved point, NOT a converged solution of the shipped v2
  data — and the v2 tap edits are not the cause (the pre-v2 pandapower-bundled
  copy and the verbatim file converge to the same point). Measured against
  our AC Newton-Raphson solution (Q-limits on, flat start, 5 iterations), the
  stored VM columns are at worst 8.5e-3 pu away, with 11 of 300 buses beyond
  the 2e-3 pu band (M2 S4, `tests/parity/test_ac_vs_matpower_stored.py`).
  case300 is a convergence + self-consistency + DC fixture and a
  pandapower-oracle column-parity fixture with Q-limits both OFF and ON
  (spec AC-1, AC-3, AC-7): on a tap-side-correct oracle copy pandapower
  converges case300 with `enforce_q_lims=True` in 2 iterations and pins the
  same 10 generator buses we pin. Erratum: the earlier record of "0.107 pu
  away at bus 17" and "pandapower cannot converge with Q-limits"
  (`record/m2-research.md` §1.2, §4.3; M2 plan A11) came from a pandapower
  `from_ppc` oracle that placed the tap of 16 transformers on the wrong
  winding, i.e. a different network; those two figures are withdrawn and the
  column-parity statement above replaces them.
- **Known reference-quality findings (research transcription, not
  re-measured by S4 — the column-parity figure above is the current
  statement of how far the stored columns sit from a solution):** the W1
  reference-quality gate (5 MVA; cap ceil(5%) = 15 buses) excluded 9 buses: 137 (7.7), 181 (7.3),
  196 (926.1), 231 (11.2), 235 (7.2), 237 (9.9), 238 (8.5), 2040 (926.9),
  9001 (5.0) MVA. The 927 MVA pair sits across branch row 390, 196-2040
  (r = 0.0001, x = 0.02, b = 0, tap = 1): the stored angles differ by 10.4
  deg across it (196 at -25.32, 2040 at -14.94), implying ~9 pu of flow, so
  the CDF-era solution cannot have been computed with this branch as shipped.
  No later wave may treat the stored columns as a converged solution of this
  file (`record/m2-research.md` §1.3, §4.3 — transcribed, not re-measured
  here).

## Reference-quality findings (shared context)

- **Q-limit-enforced lineage:** the stored solutions are compared under the
  AMENDED AC-4 (user-ratified 2026-08-19, option C): Q-limit
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
  at ceil(5%) of buses per case (AC test header; the `EXCLUDED` table in
  `tests/parity/test_ac_vs_matpower_stored.py`). Measured exclusions (parity
  test gate output, 2026-08-19 run): case_ieee30 bus 3 (8.2 MVA); case57 buses 14
  (21.2), 46 (45.8), 47 (24.7); case118 buses 17 (45.3), 30 (129.7),
  38 (31.3), 68 (10.5); case14 none. case300 (M2 research, 2026-08-20 run,
  same gate recomputed densely): 9 buses, listed in its section above.

## W9 regeneration contract

Tighter parity bands arrive with the W9 cross-engine regenerated references
contracted in the spec (ADR-002); the AC parity suite's band provenance is
that contract (AC test header). Until then the stored MATPOWER columns above,
gated as described, remain the published reference.

## Consumers

This directory is the one copy mambo-power's tests consume — `tests/parity/`
(AC/DC solve, Ybus/Bbus/PTDF/LODF, and stored-column comparisons against
pandapower and MATPOWER's own reference solutions) and `tests/unit/`
(importer round-trip, fixture byte/hash checks and this provenance record's
own wording, e.g. `tests/unit/test_fixture_case300.py`). No browser test
harness is planned for this repo.

(Note: earlier drafts of this file carried references to a `packages/`
monorepo, a Node/TypeScript test suite and a browser harness, inherited
verbatim from an abandoned prior project, `gridlab-w1`, when the fixtures
were migrated in — commit `ca10b6a`. Those sentences never described
mambo-power and have been removed; see `record/m2-critic.md` issue 2.)
