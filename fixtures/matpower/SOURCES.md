# Parity fixture provenance (AC-7)

> Consolidated per-fixture provenance record (sources, lineage, reference
> solutions, known reference defects): see `PROVENANCE.md` in this directory.

Byte-identical copies of the verbatim MATPOWER distribution files in
`packages/io/test/fixtures/matpower/` (see that directory's SOURCES.md for the
retrieval table: MATPOWER `master` `data/` directory via raw.githubusercontent.com,
retrieved 2026-08-19; upstream IEEE provenance in each file's header, converted
from IEEE Common Data Format, https://labs.ece.uw.edu/pstca/).

The five files are case14, case30, case57, case118, case_ieee30.

Reference solutions: the VM (voltage magnitude, pu) and VA (voltage angle, deg)
columns of each file's `mpc.bus` matrix are the solved operating points shipped
by MATPOWER with the distribution — the published reference the parity suite
(W1-R5 / AC-4) compares against. This directory is the one copy both runners
consume (Node suite here; browser harness in S8) per W1 design decision 3.

Do not edit these files.
