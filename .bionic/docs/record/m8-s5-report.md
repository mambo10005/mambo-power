# M8 S5 — CSV bundle (`io.csv_bundle`) — slice report

Branch `wave/08-interop-s5`, worktree `C:\Claude Projects\mambo-power-m8-s5`, base `a51250f`.

## Commit

`f9bf026` feat(m8/s5): io.csv_bundle — manifest + per-table CSV, long-format cost/bid side tables, bit-exact round-trip (W5, AC-5)

```
 docs/api/io-csv-bundle.md         |   8 +
 mkdocs.yml                        |   1 +
 src/mambo_power/io/csv_bundle.py  | 639 +++
 src/mambo_power/model/warnings.py |  18 +
 tests/unit/test_io_csv_bundle.py  | 394 +++
```

`docs/api/io-csv-bundle.md` + one `mkdocs.yml` nav line are outside the nominal ownership; required by
`tests/unit/test_api_docs_coverage.py` (any public `io` submodule needs a `:::` page). `formats.md` and
`LIMITATIONS` untouched (S6).

## Layout

- `manifest.json`: `format`, `schema_version` (= `Network.schema_version`, no separate bundle version), `base_mva`, `tables` {file: rows}.
- `buses.csv` (geo → `geo_lat, geo_lon`), `branches.csv`, `generators.csv` (cost → `cost_kind, cost_startup, cost_shutdown`) + `generator_costs.csv` (`generator_id, index, p_mw, value`), `loads.csv` (bid → `bid_kind`) + `load_bids.csv`, `shunts.csv`, `storage.csv`, `zones.csv`. Headers = model field names in field order (derived from `model_fields`).
- Empty cell ⇔ None; ids text; floats `repr`; bools `true/false` (`1/0` accepted); header-only empty tables; order preserved. `dump` raises `ValueError` on an optional string field holding `""`.

## CODES (all errors)

`CSV_MANIFEST_INVALID, CSV_SCHEMA_VERSION, CSV_MISSING_TABLE, CSV_UNKNOWN_COLUMN, CSV_MISSING_COLUMN, CSV_DUPLICATE_ID, CSV_BAD_VALUE, CSV_ORPHAN_ROW` — S6 registers them in `LIMITATIONS["io.csv_bundle"]` and documents in `formats.md`.

## Evidence

- RED: `uv run pytest tests/unit/test_io_csv_bundle.py` → `ImportError while importing test module ... 1 error during collection`.
- GREEN: `56 passed in 33.81s`.
- Sabotage 1 (`f"{x:.12g}"` for `repr`): `4 failed, 52 passed` (case14_bids identity, numeric-ids identity + array_equal, repr-cells test). Restored.
- Sabotage 2 (`id` column `int()`-coerced when `isdigit`): `20 failed, 36 passed` (all six MATPOWER fixtures via `Zone.id == "1"`, storage/zones/bids/numeric-ids). Restored; `git status --short` clean.
- Gates on f9bf026: ruff `All checks passed!`; format `186 files already formatted`; mypy `Success: no issues found in 55 source files`; `pytest tests/unit` → `1007 passed in 227.32s`.
