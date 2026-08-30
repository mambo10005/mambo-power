# M8 S6 report — docs + registrations (W8, AC-8; A18 second half; W6 docs)

Worktree `C:\Claude Projects\mambo-power-m8`, branch `wave/08-interop`, base `4ebb2bc`, head
`b01e432`. Every claim carries its command/output or the label `unverified`.

## Commits (`git log --stat 4ebb2bc..HEAD`)

| hash | subject | files |
|---|---|---|
| `4f536cb` | feat: register the four format modules in `io.report.LIMITATIONS`, re-export from `io`, API page for `io.pandapower_json` | `io/__init__.py` +15/-3, `io/report.py` +18/-8, `docs/api/io-pandapower-json.md` +10, `mkdocs.yml` +1 |
| `45828c3` | docs: `formats.md` — pandapower JSON, PyPSA export, PSS/E RAW v33, CSV bundle sections | `docs/manual/formats.md` +458/-3 |
| `7baacf3` | docs: `model.md` — `Branch.kind` | `docs/manual/model.md` +24 |
| `953ad21` | docs: `examples/13_interop.py` + gallery section 13 | `examples/13_interop.py` +130, `docs/examples/index.md` +20/-1 |
| `b01e432` | docs: changelog M8 entry, architecture box/edges/module map, index status + roadmap | `docs/changelog.md` +55, `docs/design/architecture.md` +24/-6, `docs/index.md` +40/-13 |

`git status --short` after the last commit: clean.

## Registrations (A18 second half)

`LIMITATIONS` references each module's `CODES` tuple (no retyping). The four modules import
`io.report`'s classes, so a top-of-file import in `report.py` is a cycle; the registry sits at the
bottom of `report.py` (`# noqa: E402`) and `io/__init__` imports `report` first (`# noqa: I001`).

- Every entry order verified: `uv run python -c "import <m>; from mambo_power.io import report; print(sorted(report.LIMITATIONS))"` for `mambo_power.io.report`, `.pypsa`, `.csv_bundle`, `mambo_power.io`, `mambo_power` → all print `['io.csv_bundle', 'io.matpower', 'io.pandapower_json', 'io.psse_raw', 'io.pypsa']`.
- Lazy-import safety: a `sys.meta_path` hook raising `ImportError` for `pandapower`/`pypsa`/`linopy`, then `import mambo_power.io` → `without pandapower/pypsa: [...all five...] ('PYPSA_PWL_COST_DROPPED',)`.
- Final mapping (printed from the package): matpower 3 codes; pandapower_json 8; pypsa 7; psse_raw 9; csv_bundle 8 — exactly the modules' `CODES`.

## Docs

- `formats.md`: intro rewritten (six formats, the empty-report rule, `LIMITATIONS`); one section per format in the matpower shape. The `shift_deg` opf/market caveat (F1/A19) is under all four limitations lists; the measured `nets_equal` set (F2) under pandapower; the case118 residual (F3) as a parity note under PyPSA. Example blocks' outputs were produced by running the snippets (probe run recorded in the session).
  - Correction made during the write: pandapower import `FIELD_DEFAULTED` is for missing limit columns (`min/max_p_mw`, `min/max_q_mvar`) defaulted to the setpoint — not `vm_pu`; verified at `pandapower_json.py:308-318`.
- `model.md`: `kind` table row + `### Branch.kind` subsection (default rule, neutral-tap case, line-with-tap rejection), text checked against `entities.py:73-93`.
- `examples/13_interop.py`: exit 0; stdout identical across two runs (`diff run1.txt run2.txt` empty), stderr empty. Key figures: rundcpp vs solve_dc 8.9e-15 deg; pandapower case14 import report `[]`, neutral-tap `trafo-3`, `trafo-4` kept as transformers; PyPSA objective 7642.5918 vs solve_dc_opf 7642.5918 (rel 7.5e-14); RAW `RAW_NO_COSTS`, angles 0.0 vs MATPOWER; CSV `load(dump(net)) == net: True`; `PYPSA_PWL_COST_DROPPED` for `gen-2`.
- `index.md`: also corrected principle 1 ("never imported by package code" → lazily imported by `io.pandapower_json`/`io.pypsa` only), added the new inputs/outputs to the system-context diagram and the where-to-go row. Flagged to the lead as a small widening inside an owned file.
- Not touched (outside ownership): `architecture.md` still lists `market.agents` under "Later waves".

## Gates

- `uv run --group docs mkdocs build --strict` → exit 0; tail `INFO - pydantic_fields: documented 249 field(s) in mambo_power` / `INFO - Documentation built in 30.95 seconds`; grep `WARNING|unlinked|anchor|not found|ERROR` → nothing.
- `uv run pytest -q tests/unit/test_io_limitations.py tests/unit/test_api_docs_coverage.py tests/unit/test_docstrings.py tests/unit/test_examples_run.py tests/unit/test_docs_registry_listing.py` → `95 passed in 122.63s`. (`test_io_limitations` alone: 72 passed — was 29 failed / 45 passed after commit 1 and before `formats.md`; `test_examples_run` alone: 15 passed.)
- `uv run ruff check .` All checks passed! · `uv run ruff format --check .` 199 files already formatted · `uv run mypy` Success: no issues found in 58 source files.
- Whole suite: not run (per the slice brief).
