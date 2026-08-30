# M8 S4 report — PSS/E RAW v33 import (W4, AC-4)

Worktree `C:\Claude Projects\mambo-power-m8-s4`, branch `wave/08-interop-s4`, base `a51250f`.

## Commits (verified with `git diff --cached --stat` before each)

- `8327358` fixtures(m8/s4): `fixtures/PROVENANCE-raw.md` (+228), `fixtures/case14_v33.raw` (+85), `fixtures/synthetic_quirks_v33.raw` (+51).
- `f30a8a7` feat(m8/s4): `src/mambo_power/io/psse_raw.py` (+717), `src/mambo_power/model/warnings.py` (+22), `tests/unit/test_io_psse_raw.py` (+408), `docs/api/io-psse-raw.md` (+6), `mkdocs.yml` (+1).

## Decisions

- case14 transformers written as 4-line records with CW=1/CZ=1/CM=1 (exact round-trip); BASKV kept at 0 so both importers apply `BASE_KV_REPLACED` and `base_kv` compares equal.
- "Record continuation" = the multi-line transformer record; v33 has no other continuation syntax. Extra quirks covered: 9-field bus record, 18-field generator record, quoted name containing a comma, `/` comments on data lines.
- Ids: `bus-<I>`, `load|shunt|gen-<I>-<ID>`, `branch-<I>-<J>-<CKT>`, `shunt-branch-<I>-<J>-<CKT>-i|j`, `shunt-xfmr-<I>-<J>-<CKT>`.
- `LIMITATIONS["io.psse_raw"]` NOT registered (S6 owns `formats.md`; `test_io_limitations` would fail without the docs). `CODES` exposed at module level.
- `docs/api/io-psse-raw.md` + mkdocs nav line added because `tests/unit/test_api_docs_coverage.py` fails otherwise (same as S1 did for `io.report`). `io/__init__.py` untouched.

## CODES

BASE_KV_REPLACED, ISLAND_DEACTIVATED, RAW_NO_COSTS, RAW_LOAD_ZIP_FOLDED, RAW_BRANCH_END_SHUNT_FOLDED, RAW_XFMR_MAGNETISING_FOLDED, RAW_THREE_WINDING_IGNORED, RAW_SWITCHED_SHUNT_IGNORED, RAW_SECTION_IGNORED. Errors: BAD_HEADER, UNSUPPORTED_VERSION, BAD_NUMBER, BAD_RECORD, UNTERMINATED_SECTION, UNKNOWN_BUS.

## Evidence

- Red: `uv run pytest tests/unit/test_io_psse_raw.py -q` → `ImportError: cannot import name 'psse_raw'`, 1 error during collection.
- Green: 25 passed in 1.04s; `uv run pytest tests/unit -q` → 976 passed in 208.60s.
- Sabotage 1 (CZ=2 conversion skipped): `FAILED test_quirks_transformer_cw2_cz2_cm2 — assert 0.005 <= 1e-09 (r=0.005)`; 1 failed, 24 passed.
- Sabotage 2 (`kind="transformer"` dropped): `FAILED test_three_winding_records_are_ignored_one_entry_each — assert 'line' == 'transformer'`; 1 failed, 24 passed. The case14 kind test stays green because `Branch._default_kind` infers transformer from the off-nominal taps; only the nominal-tap transformer catches the drop.
- Restored via `git checkout -- src/`; status clean; 25 passed.
- Gates: ruff check "All checks passed!"; ruff format --check "187 files already formatted"; mypy "Success: no issues found in 55 source files".
- Process note: an early `git checkout -- src/` during sabotage reverted the then-uncommitted `warnings.py` edit and left the untracked parser sabotaged; caught by the gates, re-applied, committed, and the sabotages were re-run against the commit (outputs above are from the re-run).
