# Idea: file the pandapower `from_ppc` impedance-rating bug upstream

Found 2026-08-20 during mambo-power M1/S4 (record/m1-s4-report.md §5.4).

`pandapower/converter/pypower/from_ppc.py:303` (pandapower 3.3.0) does
`sn[sn_is_zero] = MAX_VAL` inside the impedance block, where `sn` is the transformer
RATE_A array and the intended target is `sn_mva` (the impedance array). Any case with an
impedance-classified branch (TAP in {0,1} between buses of different base_kv) whose
RATE_A is 0 raises `IndexError` whenever trafo and impedance counts differ. Upstream
MATPOWER `case_ieee30` (4 trafos, 3 impedances) and `case118` (9 / 2) both reproduce.

Minimal repro: load either case through `from_mpc` with `matpowercaseframes` installed,
or build the ppc by hand and call `from_ppc(ppc, f_hz=60)`.

Filing is external-facing — user's call. Not needed by any mambo-power wave; our oracle
copy works around it.
