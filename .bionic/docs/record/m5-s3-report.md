# M5 S3 — arrays (per-storage identity)

Slice S3 of wave M5 (`multiperiod`). Scope: `src/mambo_power/numerics/*` plus its tests only.

## What it built

`NetworkArrays` (`src/mambo_power/numerics/arrays.py`) gains per-storage identity, mirroring
M4's own S2 per-load identity addition (`load_ids`/`load_bus`/`load_p_min_pu`/`load_p_max_pu`)
field-for-field in shape:

- `storage_ids: list[str]`, `storage_bus: IntArray` — identity and bus position, built from
  the same in-service-filtered `storage_units` list `from_network` builds once.
- `storage_p_max_pu`, `storage_energy_pu` — `Storage.p_max_mw`/`energy_mwh` divided by
  `base_mva`, the same pu-conversion convention every other physical field in this class
  already uses (ADR-005: physical units in the model, pu in numerics; module docstring, "the
  *single* site where physical units … are divided by `base_mva`"). `energy_mwh` becomes
  pu-hours under this convention — no different in kind from how `rating_pu`/`p_max_pu` are
  already built.
- `storage_soc_initial`, `storage_efficiency_charge`, `storage_efficiency_discharge` — carried
  through **unconverted**: `soc_initial` is already a fraction of `energy_mwh` in `[0, 1]` on
  the entity, and both efficiencies are already dimensionless ratios in `(0, 1]`. Neither has a
  physical unit to divide out, so applying `/ base` to them would be wrong, not merely
  unnecessary.

Only in-service storage participates, matching how `from_network` already treats buses,
branches, generators, loads and shunts. Every field defaults to an empty list/zero-length array
(matching `gen_ids`/`load_ids`'s own `field(default_factory=...)` pattern), so a network with no
`Storage` entities at all — every one of the 6 committed MATPOWER fixtures — builds without
special-casing.

Nothing solves with these arrays this slice. No solver reads them; that is S4's job, correctly
out of scope here.

## Storage field gap: none found

`model.Storage` (`p_max_mw`, `energy_mwh`, `soc_initial`, `efficiency_charge`,
`efficiency_discharge`, `bus`, `in_service`) already carries every field the array-level
identity needs. No gap to route to S2.

## TDD: RED before GREEN

Wrote 16 new tests in `tests/unit/test_numerics_arrays.py` first (a new `multi_storage_network`
hand-built fixture mirroring `multi_load_network`'s shape, plus fixture-parametrized checks over
every committed MATPOWER case), ran them against the unmodified `arrays.py`:

```
$ uv run --no-sync pytest -q tests/unit/test_numerics_arrays.py
...
FAILED tests/unit/test_numerics_arrays.py::test_no_storage_gives_empty_arrays_not_a_crash
FAILED tests/unit/test_numerics_arrays.py::test_per_storage_identity - Attrib...
FAILED tests/unit/test_numerics_arrays.py::test_per_storage_values - Attribut...
FAILED tests/unit/test_numerics_arrays.py::test_storage_pu_conversion_scales_with_base
FAILED tests/unit/test_numerics_arrays.py::test_every_matpower_fixture_has_no_storage[case14]
FAILED tests/unit/test_numerics_arrays.py::test_every_matpower_fixture_has_no_storage[case30]
FAILED tests/unit/test_numerics_arrays.py::test_every_matpower_fixture_has_no_storage[case_ieee30]
FAILED tests/unit/test_numerics_arrays.py::test_every_matpower_fixture_has_no_storage[case57]
FAILED tests/unit/test_numerics_arrays.py::test_every_matpower_fixture_has_no_storage[case118]
FAILED tests/unit/test_numerics_arrays.py::test_every_matpower_fixture_has_no_storage[case300]
10 failed, 22 passed in 19.16s
```

Every failure was `AttributeError: 'NetworkArrays' object has no attribute 'storage_ids'` —
confirmed RED for the right reason, not an import error or a typo. The 22 passes were the
pre-existing suite in this file, unmodified. Then implemented the fields and construction logic,
re-ran:

```
$ uv run --no-sync pytest -q tests/unit/test_numerics_arrays.py
................................                                         [100%]
32 passed in 7.42s
```

## Must-prove checklist (from the dispatch)

- **Every in-service storage unit gets exactly one entry, correctly ordered, bus index
  correct.** `test_per_storage_identity` — a 4-storage/2-bus network, one unit out of service:
  `sarr.storage_ids == ["storage-2a", "storage-2b", "storage-3"]`,
  `sarr.storage_bus == [1, 1, 2]`.
- **Out-of-service storage excluded.** Same test/fixture — `"storage-2-off"` (bus-2,
  `in_service=False`) is absent from `storage_ids`.
- **A network with no storage at all still works — empty arrays, not a crash.**
  `test_no_storage_gives_empty_arrays_not_a_crash` (the existing 4-bus fixture, which carries no
  `Storage` at all) asserts every per-storage field comes back shape-`(0,)` with the right
  dtype, no exception. `test_every_matpower_fixture_has_no_storage`, parametrized over all 6
  committed MATPOWER fixtures (`case14, case30, case_ieee30, case57, case118, case300`, via
  `tests._fixtures.FIXTURES`), confirms `storage_ids == []` on every one — matching
  `m5-research.md` §8.1's finding directly (the message said "five"; the repo's own
  `tests/_fixtures.FIXTURES` list has six MATPOWER cases including `case30`, checked all six for
  completeness — all zero storage).
- **Nothing existing changed.** `test_existing_aggregate_arrays_unchanged_on_every_fixture`,
  parametrized over the same 6 fixtures, asserts `p_load_pu`, `q_load_pu` and `p_max_pu` are
  **byte-identical** (`np.testing.assert_array_equal`, not `allclose`) to an independently
  recomputed reference built directly from `net.loads`/`net.generators` via `np.bincount` — the
  same construction `arrays.py` itself uses, computed separately in the test so it doesn't share
  a code path with the field under test. This mirrors M4's own
  `test_aggregate_load_arrays_unchanged_by_per_load_identity` pattern exactly (that test is
  still present, unmodified, and still passing).

## Verification

```
$ uv run --no-sync pytest -q tests/unit/test_numerics_arrays.py
32 passed in 7.42s

$ uv run --no-sync pytest -q          # full suite, run once before commit
670 passed, 10 warnings in 230.07s (0:03:50)

$ uv run --no-sync ruff check src/mambo_power/numerics/arrays.py tests/unit/test_numerics_arrays.py
All checks passed!

$ uv run --no-sync ruff format --check src/mambo_power/numerics/arrays.py tests/unit/test_numerics_arrays.py
2 files already formatted        # after one `ruff format` pass on arrays.py, run once

$ uv run --no-sync mypy src/mambo_power/numerics/arrays.py
Success: no issues found in 1 source file
```

670 − 654 (confirmed baseline, `uv run --no-sync pytest -q` → `654 passed` before this slice's
work started) = 16, exactly the new test count in `test_numerics_arrays.py`. No pre-existing
test was edited — confirmed by `git diff --stat` scoped to the two touched files
(`+214/-1` across exactly `arrays.py` and `test_numerics_arrays.py`, nothing else).

**Caveat on the 670 number**: the full-suite run above executed in the shared worktree
(`C:\Claude Projects\mambo-power-m5`) while S1 (`opf/dc_opf.py`) and S2
(`model/entities.py`, `model/network.py`, `model/scenario.py`, `model/__init__.py`,
`tests/unit/test_period_scenario.py`, `tests/unit/test_model_invariants.py`,
`tests/unit/snapshots/network.schema.json`) had concurrent, uncommitted changes present in the
same working tree — confirmed via `git status --short` immediately after. That run therefore
exercised a mixture of my committed diff and their in-flight work, not my diff in isolation. The
scoped run (`tests/unit/test_numerics_arrays.py` → `32 passed`, `ruff`/`mypy` scoped to my two
files) is the one that is purely attributable to this slice; the 670 full-suite number is
directional evidence, not a clean before/after for S3 alone. A full-repo `ruff check`/`mypy` at
the same moment showed unrelated findings in S1's/S2's own touched files
(`tests/unit/test_period_scenario.py`: import-sort + one E501; `src/mambo_power/opf/dc_opf.py`:
two mypy arg-type errors) — not investigated further, not this slice's files, not this slice's
responsibility.

## Commit

`d0031cb` on `wave/05-multiperiod` (base `e88752c`), worktree
`C:\Claude Projects\mambo-power-m5`. Staged only the two files listed above, by exact path —
confirmed via `git status --short` before and after `git add` that no S1/S2 in-progress file was
swept in. Not pushed, per the dispatch.

## Not done by this slice (by design)

- No solver reads `storage_p_max_pu`/`storage_energy_pu`/etc. yet — S4 (`opf/multiperiod.py`)
  is the consumer.
- `model/`, `opf/`, `market/`, `jobs/` untouched, as scoped.
- `numerics/__init__.py` untouched — no new export needed; `NetworkArrays` itself was already
  exported and this slice only adds fields to it, not a new symbol.
