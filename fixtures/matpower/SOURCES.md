# Parity fixture provenance (AC-7)

> Consolidated per-fixture provenance record (sources, lineage, reference
> solutions, known reference defects): see `PROVENANCE.md` in this directory.

Byte-identical copies of the verbatim MATPOWER distribution files in
`packages/io/test/fixtures/matpower/` (see that directory's SOURCES.md for the
retrieval table: MATPOWER `master` `data/` directory via raw.githubusercontent.com,
retrieved 2026-08-19; upstream IEEE provenance in each file's header, converted
from IEEE Common Data Format, https://labs.ece.uw.edu/pstca/).

The five M1 files are case14, case30, case57, case118, case_ieee30. M2 adds
case300, retrieved the same way on 2026-08-20 and pinned:

| File | URL | git blob SHA-1 | sha256 | bytes | retrieved |
| --- | --- | --- | --- | --- | --- |
| case300.m | https://raw.githubusercontent.com/MATPOWER/matpower/master/data/case300.m | `004203b8adae83b3f21ce9ceb4a13db9b18f0132` | `69a90280e999ef533d94656e0fbc08311f1347c962dd2753ff2005ff5e3f9ac5` | 66034 | 2026-08-20 |

Licence: the files are public IEEE test data carried as distributed by
MATPOWER; MATPOWER's LICENSE states "The MATPOWER case files distributed with
MATPOWER are not covered by the BSD license", so no BSD claim is made for them
(full quotation and context in `PROVENANCE.md`, "Licence").

Reference solutions: the VM (voltage magnitude, pu) and VA (voltage angle, deg)
columns of each file's `mpc.bus` matrix are the solved operating points shipped
by MATPOWER with the distribution — the published reference the parity suite
(W1-R5 / AC-4) compares against — except case300, whose stored columns are
not a solution of the shipped data (see its `PROVENANCE.md` section; pandapower
with Q-limits off is the oracle there). This directory is the one copy both runners
consume (Node suite here; browser harness in S8) per W1 design decision 3.

Do not edit these files.

Synthetic case14 variants for AC-4 / AC-5 (roles, island, no slack generator)
live in `derived/` with their own `derived/PROVENANCE.md`; they are not upstream
bytes and stay out of the parity fixture list.
