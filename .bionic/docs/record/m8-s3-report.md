# m8-s3 report — PyPSA export (W3, AC-3)

Date 2026-08-29. Worktree `C:\Claude Projects\mambo-power-m8-s3`, branch `wave/08-interop-s3`, base `a51250f`.

## Commits

| hash | subject | --stat |
|---|---|---|
| 9714c1f | feat(m8/s3): io.pypsa — Network → pypsa.Network export with ExportReport | io/pypsa.py +342, model/warnings.py +11, tests/parity/test_pypsa_export_vs_pypsa.py +246, tests/unit/test_io_pypsa.py +320 |
| 0a88cbd | docs(m8/s3): API page for io.pypsa | docs/api/io-pypsa.md +9, mkdocs.yml +1 (required by tests/unit/test_api_docs_coverage.py; not in the ownership list) |

## Deliverable

`io.pypsa.to_network(net)` / `to_network_with_report(net)`; PyPSA imported lazily (AST test). Field map in the module docstring. `CODES` = PYPSA_PWL_COST_DROPPED, PYPSA_COST_DEGREE_DROPPED, PYPSA_LOAD_BID_DROPPED, PYPSA_ZONE_DROPPED, PYPSA_GEN_Q_LIMITS_DROPPED, PYPSA_GEN_RAMP_DROPPED, PYPSA_GEN_VSET_CONFLICT (appended to `ImportIssueCode`; not registered in `LIMITATIONS` — that would require `formats.md`, S6's).

Conventions S6 must document: `UNRATED_S_NOM_MVA = 1e5`; `COST_CONSTANT_COLUMN = "marginal_cost_constant"`; bus `in_service` custom column, elements at a dead bus `active=False`; `area`/`zone` custom bus columns; `n.meta["base_mva"]`; PyPSA 1.2.4 `optimize()` ignores `phase_shift` (carried, not reported).

## Evidence

- red: `uv run pytest tests/unit/test_io_pypsa.py -x` → `AssertionError: PYPSA_PWL_COST_DROPPED ... not in ('ISLAND_DEACTIVATED', 'BASE_KV_REPLACED', 'GENCOST_REACTIVE_IGNORED')`, 1 failed (before warnings.py edit).
- green: unit + parity file → 33 passed.
- sabotage 1 (generator `p_set`): unit `assert np.False_ ... p_set gen-1 232.4 ... isna`; parity `case14: ('warning','infeasible') == ('ok','optimal')`. Restored.
- sabotage 2 (transformer x unscaled): unit `0.2 == 0.16 ± 1.6e-07`; case14 parity did **not** redden (no fixture rates a branch → merit-order dispatch is impedance-independent). Added `test_rated_tap_transformer_loop_dispatch_matches`; under the sabotage: `assert (519.99 / 1000.0) <= 1e-08`. Restored.
- sabotage 3 (PWL `warn()` removed): `ValueError: not enough values to unpack (expected 1, got 0)`, `assert [] == ['gen-2','gen-3']`. Restored.
- gates: `ruff check .` All checks passed; `ruff format --check .` 186 files already formatted; `mypy` Success, 55 files; `pytest tests/unit tests/parity/test_pypsa_export_vs_pypsa.py` 984 passed in 270.98s.

## AC-3 deviation

Objective 1e-8 rel: all three (worst 1.3e-12). Dispatch 1e-4 MW: case14, case30. case118: 1.87e-3 MW on gen-5 (M3's test measured the same on its ppc oracle). Cause is the oracle's HiGHS QP: both dispatches balance 4242.0 MW, costs strictly convex, exact polynomial puts ours 1.6e-7 $/h below PyPSA; HiGHS logs P-D objective error 1.1e-6; tolerances 1e-8/1e-9 and solver=ipm/simplex leave 1.87e-3 unchanged, 1e-10 → internal_solver_error. Pinned `CASE118_DISPATCH_ABS_TOL_MW = 2e-3`. Lead decides: amend AC-3 wording, or drop case118 from the dispatch assertion.

## Limitations (for S6 → formats.md)

- PyPSA cannot carry: piecewise costs, polynomial costs of degree > 2, load bids, zones, generator reactive limits (each dropped and reported under the codes above; never approximated).
- PyPSA 1.2.4 `optimize()` ignores `phase_shift` (only `lpf()`/`pf()` read it): the exporter carries the shift, but DC-OPF parity is for shift-free networks.
- **Until M8 F1 lands** (the `opf/dc_opf.py` shifter fix, a standalone task after M8 merges), mambo `opf` flows and flow-limit rows on an exported (or any) phase-shifter network are wrong on the mambo side; `pf.solve_dc` is correct and agrees with PyPSA `lpf()`.
- `rating_mva = None` becomes `s_nom = 1e5` (`UNRATED_S_NOM_MVA`); the constant cost term lives in the custom `marginal_cost_constant` column; bus `in_service`, `area`, `zone` are custom bus columns.

## Finding outside S3 (confirmed by lead as M8 F1)

`opf/dc_opf.py:906` flow-limit const omits `−PTDF @ p_shift_bus`: on a 3-bus loop with a 5° shifter and identical dispatch, `pf.solve_dc` gives t12 = 95.755 MW (−5°) / 37.578 (+5°), matching PyPSA `lpf()` to 1e-9, while `solve_dc_opf` reports 153.933 / −20.600 and its other flows do not move with the shift (KCL violated at b2). Repro: scratchpad `dbg7.py`. Reported to team-lead.
