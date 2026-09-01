# M8 S1 report — Branch.kind (W6, AC-6) and ExportReport (W7, AC-7)

Worktree `C:\Claude Projects\mambo-power-m8`, branch `wave/08-interop`, base `15e71fa`. Three commits, never amended.

## Commits

```
a51250f docs(m8/s1): API page for io.report (ExportReport, ReportError, LIMITATIONS)
25e9bed feat(m8/s1): ExportReport mirroring ImportReport, LIMITATIONS registry, docs-coverage test (W7, AC-7)
79a71ea feat(m8/s1): Branch.kind — line|transformer, defaulted from tap and shift (W6, AC-6)
```

## Files touched

- `src/mambo_power/model/entities.py` — `BranchKind`, `_is_nominal`, `Branch.kind` field, `_default_kind` before-validator
- `src/mambo_power/model/__init__.py` — export `BranchKind`
- `tests/unit/snapshots/network.schema.json` — one property added (below)
- `tests/unit/test_branch_kind.py` — new, 15 tests
- `src/mambo_power/io/report.py` — `_Report` base, `ImportReport`, `ExportReport`, `ReportError`, `ConversionIssue`, `LIMITATIONS`
- `tests/unit/test_export_report.py` — new, 8 tests
- `tests/unit/test_io_limitations.py` — new, 8 tests
- `docs/api/io-report.md` — new; `mkdocs.yml` — nav entry

## Snapshot property added (verbatim from `git show 79a71ea`)

```
+        },
+        "kind": {
+          "default": "line",
+          "description": "'line' or 'transformer'. Defaults to 'transformer' when tap_ratio is not None/1.0 or shift_deg is not None/0.0, else 'line'; an explicit 'transformer' at nominal tap is kept; an explicit 'line' with a tap or shift is rejected.",
+          "enum": [
+            "line",
+            "transformer"
+          ],
+          "title": "Kind",
+          "type": "string"
```

## Feature 1 — Branch.kind: red / green / sabotage

- Red: `uv run pytest -q tests/unit/test_branch_kind.py -p no:cacheprovider` → `14 failed, 1 passed in 16.18s`
- Green (with snapshot): `uv run pytest -q tests/unit/test_branch_kind.py tests/unit/test_json_schema_snapshot.py` → `17 passed` after `MAMBO_UPDATE_SNAPSHOTS=1`
- Pre-M8 count: `uv run pytest --collect-only -q tests/unit --ignore=tests/unit/test_branch_kind.py` → `920 tests collected`; unit suite after commit 1: `935 passed in 208.59s`
- Sabotage (default forced to `"line"`):
  ```
  FAILED tests/unit/test_branch_kind.py::test_default_is_transformer_off_nominal[fields0]
  FAILED tests/unit/test_branch_kind.py::test_default_is_transformer_off_nominal[fields1]
  FAILED tests/unit/test_branch_kind.py::test_default_is_transformer_off_nominal[fields2]
  FAILED tests/unit/test_branch_kind.py::test_default_is_transformer_off_nominal[fields3]
  4 failed, 11 passed in 2.40s
  ```
  Restored (note: my restore was a `git checkout` that also wiped the feature; I re-applied it in full and re-ran green before committing).

## Feature 2 — ExportReport: red / green / sabotage

- Red: `uv run pytest -q tests/unit/test_io_limitations.py tests/unit/test_export_report.py` → `2 errors in 2.99s` (collection: `LIMITATIONS`, `ExportReport` missing)
- Green: `16 passed in 2.04s`
- Sabotage (`GENCOST_REACTIVE_IGNORED` renamed in `docs/manual/formats.md`):
  ```
  FAILED tests/unit/test_io_limitations.py::test_every_registered_code_is_documented[io.matpower-GENCOST_REACTIVE_IGNORED]
  1 failed, 7 passed in 2.57s
  ```
  `git checkout -- docs/manual/formats.md` → `8 passed in 2.33s`

## Deviation: ImportReport had no `errors`/`raise_on_error`

The brief said to mirror ImportReport's `errors` and `raise_on_error`; neither existed. Added both to a shared `_Report` base so both reports are identical in shape; ImportReport stays backward compatible (`errors` defaults empty). `ConversionIssue` is an alias of `model.ImportIssue`; S2–S5 extend the closed `ImportIssueCode` Literal for new codes.

## Mistake and fix (commit 3)

The unit run behind commit 2 was `1 failed, 950 passed` (`test_api_docs_coverage`: `ExportReport`, `ReportError` had no `:::` page) but the `| tail` masked the exit code and the commit message claims 951 passed. Commit `a51250f` adds `docs/api/io-report.md` and states the correction. `uv run --group docs mkdocs build --strict` exit 0.

## Final gates

```
uv run pytest -q tests/unit -p no:cacheprovider   → 951 passed in 173.05s (0:02:53), exit 0
uv run ruff check .                                → All checks passed!
uv run ruff format --check .                       → 183 files already formatted
uv run mypy                                        → Success: no issues found in 54 source files
```

Full suite not run (orchestrator's). Worktree clean.

## Not done

- No changelog entry; no prose in `docs/manual/formats.md`/`model.md` for `kind` or `ExportReport` (read as W8/S6).
- `io/__init__` does not re-export `ExportReport` (nor `ImportReport` today).
