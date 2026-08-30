# m8-s3 progress (PyPSA export) — 2026-08-29

- worktree C:\Claude Projects\mambo-power-m8-s3, branch wave/08-interop-s3, base a51250f
- red: test_codes_are_registered_issue_codes failed (PYPSA_* not in ImportIssueCode) before warnings.py edit
- green: tests/unit/test_io_pypsa.py 18 → 19 passed; tests/parity/test_pypsa_export_vs_pypsa.py 14 passed
- sabotage 1 (p_set on generators): unit p_set tests + case14 parity red ('warning','infeasible'); restored
- sabotage 2 (transformer x not on s_nom): unit red; case14 parity did NOT redden (no fixture rates a branch → dispatch is impedance-independent); added test_rated_tap_transformer_loop_dispatch_matches, which reddens (1520 vs 1000 $/h); restored
- sabotage 3 (PWL drop unreported): unit + parity PWL tests red; restored
- gates: ruff check/format clean, mypy clean (55 files); tests/unit + parity file: 984 passed
- commits: 9714c1f (exporter, codes, tests), 0a88cbd (docs/api/io-pypsa.md + mkdocs nav — needed by test_api_docs_coverage)
- finding sent to team-lead: opf/dc_opf.py shifter flow rows omit −PTDF@p_shift (out of S3 scope)
