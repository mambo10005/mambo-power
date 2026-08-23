# Derived fixtures — synthetic case14 variants (AC-4, AC-5)

These files are NOT upstream data and carry no reference solution. Each is
`../case14.m` (the verbatim MATPOWER file; provenance and sha256 in
`../PROVENANCE.md`) with a small, documented set of cell edits that put the
network into a state the M2 semantics must handle: a PV bus without a live
generator, a bus with two live generators at differing setpoints, a slack bus
without a live generator, and an island. They are excluded from the parity
fixture list (`tests/_fixtures.py::FIXTURES`) because they are not upstream
bytes; they are exercised by `tests/unit/test_fixtures_derived.py` and by the
S2 role/island tests.

## Derivation rule

1. Start from the bytes of `../case14.m`; change the `function mpc = case14`
   line to the new file name and insert a header comment block naming the base
   file, the purpose (AC-4 / AC-5) and every edited cell by matrix, 1-based row
   and MATPOWER column name.
2. Edit only the listed cells (plus, for `case14_roles`, one appended `mpc.gen`
   row and its `mpc.gencost` row). Every other byte of the mpc matrices — and
   the original case14 header, kept below the new block — is unchanged; the
   stored VM/VA columns are therefore case14's, not a solution of the edited
   network, and must not be used as one.
3. `tests/unit/test_fixtures_derived.py` enforces the rule: it reads both files
   with the independent numpy reader (`tests/parity/_mpc_reader.py`), applies
   the documented edit to case14's matrices in numpy, and asserts exact equality
   with the derived file's matrices.
4. Regenerate rather than hand-edit: the generator script lives in the S1
   report (`.bionic/docs/record/m2-s1-report.md`); the test is the contract.

## Files

### case14_roles.m — AC-4 (W3, effective bus roles)
- `mpc.gen` row 4 (bus 6, the bus's only generator): `GEN_STATUS` 1 -> 0.
  Bus 6 is still declared type 2 (PV) in `mpc.bus`; the effective role is PQ.
  Bus 6 was chosen over bus 8 (the other single-generator PV bus) because it
  carries load (11.2 MW / 7.5 MVAr) and is meshed, so solving it as PQ is a
  meaningful check; bus 8 is radial and unloaded.
- `mpc.gen` row 2 (bus 2): `PG` 40 -> 20, `QG` 42.4 -> 21.2.
- `mpc.gen` row 6 (appended, bus 2): copy of the edited row 2 with `VG`
  1.045 -> 1.055, so bus 2 has two in-service generators whose setpoints
  differ by 0.01 pu; per-bus PG/QG totals at bus 2 are unchanged. Appending
  (rather than inserting after row 2) keeps `gen-1..gen-5` identical to
  case14's ids; the new unit is `gen-6` and is the *last* in-service generator
  at bus 2, so the MATPOWER last-wins rule selects 1.055 and the pandapower
  first-row rule selects 1.045 — the disagreement W3's warning is about.
  `QMAX/QMIN/PMAX/PMIN` are duplicated verbatim on both rows (not halved), so
  the bus's aggregate limits are doubled; no M2 test depends on bus-2 limits.
- `mpc.gencost` row 6 (appended): copy of gencost row 2.
- Slack bus 1 / gen row 1 untouched.

### case14_island.m — AC-5 (W4, island policy)
- `mpc.branch` row 14 (7-8): `BR_STATUS` 1 -> 0.
  Branch 7-8 is the only bridge in case14 (bus 8 has no other branch; M1's
  bridge detection on case14 finds exactly this one). With it out, bus 8 —
  declared PV, in service, carrying in-service gen row 5 — is an island without
  the slack.
- Behaviour today (M1 model, pre-S2): `io.matpower.load` raises
  `NetworkValidationError` with code `DISCONNECTED_BUS` naming `bus-8`. From S2
  on: `load` / `load_with_warnings` deactivate bus 8 and gen 5 and return an
  `ISLAND_DEACTIVATED` warning; `Network(...)` built directly still raises.

### case14_noslackgen.m — AC-4 (W3, `NoSlackGeneratorError`)
- `mpc.gen` row 1 (bus 1, the slack bus's only generator): `GEN_STATUS` 1 -> 0.
  The slack bus still exists and is in service, so the model accepts the file;
  `numerics.effective_roles` must raise `NoSlackGeneratorError` on it.
