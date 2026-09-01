# M1 S3 report — Network model (pydantic v2 entities, named errors, JSON schema snapshot, native round-trip)

Agent: m1-s3-model · 2026-08-20 · worktree `C:\Claude Projects\mambo-power-m1`, branch `wave/01-substrate`
Base: 2922d8e (S1 scaffold) → **commit 8c82e9dc2d01c490e565e3abe8f7d3ebe1f28dfb** (not pushed).
Every claim below carries its command and trimmed output, or is labelled `unverified`.

## 1. Delivered

| Path (under `src/mambo_power/`) | Contents |
|---|---|
| `model/entities.py` | `Geo`, `Bus`, `Branch`, `PolynomialCost`, `PiecewiseCost`, `GeneratorCost` (discriminated on `kind`), `Generator`, `Load`, `Shunt`, `Storage`, `Zone`; all `ConfigDict(extra="forbid", frozen=False)`; every unit-bearing field carries a `Field(description=...)` that lands in the JSON schema |
| `model/errors.py` | `ValidationCode` (7-literal), `ValidationIssue(code, path, message)` (frozen pydantic model), `NetworkValidationError` with `.issues`, `.codes`, readable `__str__` |
| `model/network.py` | `Network(schema_version=1, base_mva, buses, branches, generators, loads, shunts, storage, zones)`; `model_validator(mode="after")` collects ALL issues; `Network.json_schema()` classmethod; `bus_index()`; public `validate_network(net) -> list[ValidationIssue]` |
| `model/__init__.py` | re-exports all public names |
| `io/__init__.py`, `io/native.py` | `dumps` (indent 2, exclude_none), `loads`, `save`, `load` |

Tests: `tests/unit/test_model_invariants.py` (28 cases), `test_model_roundtrip.py` (5), `test_json_schema_snapshot.py` (3), `test_model_examples.py` (4), snapshot `tests/unit/snapshots/network.schema.json` (654 lines, 16 400 bytes).

## 2. RED — tests written first, run before any source existed

Command: `uv run pytest tests/unit/test_model_invariants.py tests/unit/test_model_roundtrip.py tests/unit/test_json_schema_snapshot.py tests/unit/test_model_examples.py -q` → **exit 2**

```
ERROR collecting tests/unit/test_model_invariants.py
tests\unit\test_model_invariants.py:11: in <module>
    from mambo_power.model import (
E   ModuleNotFoundError: No module named 'mambo_power.model'
ERROR collecting tests/unit/test_model_roundtrip.py
tests\unit\test_model_roundtrip.py:7: in <module>
    from mambo_power.io import native
E   ModuleNotFoundError: No module named 'mambo_power.io'
ERROR collecting tests/unit/test_json_schema_snapshot.py
tests\unit\test_json_schema_snapshot.py:15: in <module>
    from mambo_power.model import Network
E   ModuleNotFoundError: No module named 'mambo_power.model'
ERROR collecting tests/unit/test_model_examples.py
tests\unit\test_model_examples.py:6: in <module>
    from mambo_power.model import Branch, Bus, Generator, Load, Network
E   ModuleNotFoundError: No module named 'mambo_power.model'
4 errors in 0.55s
```

Second RED, after the source landed but before the snapshot existed — `uv run pytest tests/unit -q` → **exit 1**:

```
F........................................                                [100%]
______________________ test_json_schema_matches_snapshot ______________________
>       assert SNAPSHOT.exists(), REGENERATE_HINT
E       AssertionError: JSON schema of mambo_power.model.Network differs from the committed snapshot
        C:\Claude Projects\mambo-power-m1\tests\unit\snapshots\network.schema.json. If the model change is
        intentional, regenerate with `MAMBO_UPDATE_SNAPSHOTS=1 uv run pytest tests/unit/test_json_schema_snapshot.py`,
        review the snapshot diff, and commit it together with the model change.
1 failed, 40 passed in 0.82s
```

Snapshot generated: `MAMBO_UPDATE_SNAPSHOTS=1 uv run pytest tests/unit/test_json_schema_snapshot.py -q` → `3 passed`, exit 0.

**Drift detection proven (the instrument catches):** `sed -i 's/"base_kv": {/"base_kv_RENAMED": {/' tests/unit/snapshots/network.schema.json` then the same pytest command →

```
E       AssertionError: JSON schema of mambo_power.model.Network differs from the committed snapshot ... regenerate with ...
1 failed, 2 passed in 0.49s     exit=1
```

Regenerated with the env var → `3 passed`; `grep -c base_kv_RENAMED` → `0`. Comparison is on parsed JSON (`json.loads`), not bytes.

## 3. GREEN gate (after one `ruff format` fix, see §5 item 12)

| Command | Exit | Trimmed output |
|---|---|---|
| `uv run ruff check .` | 0 | `All checks passed!` |
| `uv run ruff format --check .` | 0 | `17 files already formatted` |
| `uv run mypy` | 0 | `Success: no issues found in 7 source files` |
| `uv run pytest` | 0 | see below |

```
tests\parity\test_oracles_import.py ..                                   [  4%]
tests\unit\test_json_schema_snapshot.py ...                              [ 11%]
tests\unit\test_model_examples.py ....                                   [ 20%]
tests\unit\test_model_invariants.py ............................         [ 86%]
tests\unit\test_model_roundtrip.py .....                                 [ 97%]
tests\unit\test_version.py .                                             [100%]
============================= 43 passed in 4.20s ==============================
```

`uv` invoked as `C:\Users\mambo\AppData\Roaming\Python\Python314\Scripts\uv.exe`; `uv sync --locked --all-groups` → `Resolved 81 packages ... Checked 77 packages`, exit 0. Locked pydantic 2.13.4 / pydantic-core 2.46.4.

## 4. Commit

`git rev-parse HEAD` → `8c82e9dc2d01c490e565e3abe8f7d3ebe1f28dfb`. `git show --stat HEAD`:

```
commit 8c82e9dc2d01c490e565e3abe8f7d3ebe1f28dfb
Author: Manho Joung <manhojoung@gmail.com>
Date:   Thu Aug 20 15:29:34 2026 -0700

    feat(m1/S3): Network model — pydantic v2 entities, named validation errors, JSON schema snapshot, native round-trip

    Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>
    Claude-Session: https://claude.ai/code/session_01NA3xnvrFVGDqG3azRk8CBs

 src/mambo_power/io/__init__.py           |   5 +
 src/mambo_power/io/native.py             |  32 ++
 src/mambo_power/model/__init__.py        |  38 ++
 src/mambo_power/model/entities.py        | 143 +++++++
 src/mambo_power/model/errors.py          |  66 ++++
 src/mambo_power/model/network.py         | 226 +++++++++++
 tests/unit/snapshots/network.schema.json | 654 +++++++++++++++++++++++++++++++
 tests/unit/test_json_schema_snapshot.py  |  54 +++
 tests/unit/test_model_examples.py        |  70 ++++
 tests/unit/test_model_invariants.py      | 232 +++++++++++
 tests/unit/test_model_roundtrip.py       | 153 ++++++++
 11 files changed, 1673 insertions(+)
```

No hook blocked the commit. `git status --short` after commit: clean. Nothing pushed; `uv.lock`, `pyproject.toml`, CI untouched (`git show --stat` above is the complete file list).

## 5. Design deviations and judgment calls

1. **`NetworkValidationError` subclasses `Exception`, not `ValueError` (deviation from the brief).** Probed before writing a line of `errors.py`: a `ValueError` subclass raised from `model_validator(mode="after")` or `model_post_init` is converted by pydantic-core into `pydantic_core.ValidationError` on every entry point (`Network(...)`, `model_validate`, `model_validate_json`), and `.issues` is lost (`getattr(e, "issues", None)` → `None`). A plain `Exception` subclass propagates unchanged with `.issues` intact on all three. Probe output:
   ```
   E1(ValueError) init     -> pydantic_core._pydantic_core.ValidationError None
   E1(ValueError) validate -> pydantic_core._pydantic_core.ValidationError None
   E1(ValueError) json     -> pydantic_core._pydantic_core.ValidationError None
   E2(Exception)  init     -> __main__.E2 ['i']
   E2(Exception)  validate -> __main__.E2 ['i']
   E2(Exception)  json     -> __main__.E2 ['i']
   ```
   The brief's operative requirement — "raises `NetworkValidationError` carrying ALL issues" — is only satisfiable this way. Consequence: `except ValueError` does not catch it; `except NetworkValidationError` / `except Exception` do. The class docstring records the reason. `test_model_validate_json_raises_the_same_error` pins the JSON path.
2. **BAD_BASE and BAD_RANGE are checked in the `Network` after-validator, not as pydantic `Field(gt=0, ...)` constraints.** Field constraints would raise pydantic's own `ValidationError` before the after-validator runs, so a file with a bad base *and* a dangling reference would report only the first — contradicting "ALL issues in one error". Consequences: (a) a standalone `Bus(base_kv=-1.0)` or `Storage(soc_initial=2.0)` constructs without error; only putting it in a `Network` fails; (b) the JSON schema carries the limits as `description` text, not as `exclusiveMinimum`/`minimum`/`maximum` keywords. If the lead wants machine-readable bounds in the schema, the cheap follow-up is `json_schema_extra` on those four fields (no behaviour change, snapshot regen).
3. **Connectivity start bus** = first in-service slack; if there is none (NO_SLACK already reported), the first in-service bus — W1's `checkConnectivity` behaviour (extract §1.4). So a slack-less network may also report DISCONNECTED_BUS; the minimal NO_SLACK counter-example (one pq bus) does not. Traversal ignores out-of-service branches and branches touching an out-of-service bus; out-of-service buses are never reported (wave design item 4), tested by `test_out_of_service_bus_is_not_disconnected` and `test_disconnected_bus_over_branch_to_out_of_service_bus`.
4. **DUPLICATE_ID** path points at the *repeated* occurrence (`buses[1].id`), one issue per repeat, per collection — W1 semantics; cross-collection id reuse is allowed and tested (`test_duplicate_id_is_per_collection_not_global`).
5. **MULTIPLE_SLACK / NO_SLACK** count in-service slack buses only (brief), which is stricter than W1 (counted all). Path is `buses`; message lists the slack ids.
6. **BAD_RANGE paths** name the lower-bound field (`generators[0].p_min_mw`, `buses[0].v_min_pu`) or the offending field (`storage[0].soc_initial`, `storage[0].efficiency_charge`, `generators[0].cost.points`). `v_min_pu > v_max_pu` is only checked when both are present. `PiecewiseCost` enforces non-decreasing `p_mw` only — no minimum point count, no monotone cost — per brief.
7. **Public `validate_network(net) -> list[ValidationIssue]`** and `NetworkValidationError.codes` are additions beyond the brief. Reason: `frozen=False` without `validate_assignment` means mutating a constructed network never re-validates; callers need a re-check entry that returns issues rather than raising. The validator itself is that function, so no duplicated logic.
8. **W1 fields renamed / not ported, all per the wave spec or brief:** `status: 0|1` → `in_service: bool`; `BAD_PER_UNIT` → `BAD_BASE`; W1's `ValidationResult {ok, errors}` shape → exception; `Storage.energyCapacityMWh/powerCapacityMW/chargeEfficiency/dischargeEfficiency/socInitial` → `energy_mwh/p_max_mw/efficiency_charge/efficiency_discharge/soc_initial`; `Branch.from/to/ratingMVA/tapRatio/phaseShiftDeg` → `from_bus/to_bus/rating_mva/tap_ratio/shift_deg`; `Shunt.gsMW/bsMVAr` → `g_mw/b_mvar`; `Zone.name` required in W1 → optional here (brief). Added vs W1: `Bus.vm_pu/va_deg/v_min_pu/v_max_pu/area/in_service`, `Load.in_service`, `Shunt.in_service`, `Storage.in_service`, `Generator.cost`, all BAD_RANGE checks (closes extract "Surprises" item 7, `socInitial` unvalidated). Not ported on purpose: W1's "`baseKV ≤ 0` silently → 1" — that is importer behaviour and belongs to S4; the model reports BAD_BASE.
9. **Snapshot regeneration** is built into the test (`MAMBO_UPDATE_SNAPSHOTS=1`), writes LF with `indent=2` and a trailing newline, and the failure message states the procedure. Comparison is parsed JSON; `test_json_schema_is_the_pydantic_schema` pins `json_schema()` ≡ `model_json_schema()`.
10. **`native.save`** writes `dumps(net) + "\n"` (trailing newline, LF, UTF-8); `native.loads` also accepts `bytes`. `dumps` is exactly `model_dump_json(indent=2, exclude_none=True)` per brief; `test_dumps_has_no_null_fields` walks the parsed document rather than grepping for the string `null`.
11. **Tests beyond the brief's minimum** (all in the four named files): out-of-service slack counts as NO_SLACK; disconnection via an out-of-service branch and via an out-of-service intermediate bus; out-of-service isolated bus tolerated; per-collection uniqueness; seven DANGLING_REF sites parametrised (incl. `bus.zone`); eight BAD_RANGE sites parametrised; `model_validate_json` raises the same error; `extra="forbid"` rejects unknown fields; `save`/`load` with both `Path` and `str`; the AC-5 expression `Network.model_validate_json(net.model_dump_json()) == net` verbatim on the hand-written network.
12. **Gate fix:** first `ruff check` run flagged one E501 (104 > 100) on `Storage.soc_initial`'s description; `uv run ruff format src/mambo_power/model/entities.py` wrapped it. The schema snapshot is unaffected (string content unchanged; re-ran the snapshot test → 3 passed).
13. **Line endings:** git printed `LF will be replaced by CRLF` warnings at `git add` (core.autocrlf on this machine); the index holds LF. No action taken — same situation as S1's files. `unverified`: whether S1 chose to address this in `.gitattributes` beyond `*.m -text`.
14. Nothing in `tests/parity` or `tests/property` was touched; the MATPOWER fixture round-trip (AC-5 over fixtures) is S4's, as briefed. No importer written.

## 6. Progress artifact

`C:\Claude Projects\mambo-power\.bionic\tmp\s3-progress.md` — appended at T+0/2/3/12/18/22.
