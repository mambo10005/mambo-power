# M2 / S5 "jobs" — report

Wave M2 power-flow, slice S5: the stateless, JSON-serialisable job surface (W6, AC-6, design
item 6, ADR-004). Worktree `C:\Claude Projects\mambo-power-m2`, branch `wave/02-power-flow`,
base `e4ed0f6` (S4). Written 2026-08-21 (UTC). Every number below was produced by a command in
this session. Not pushed.

**Headline.** `mambo_power.jobs` ships `SolveRequest` / `SolveResult` / `StructuredError`, the
`KINDS` registry (`pf.ac`, `pf.dc`; `register`, `kinds`), `run` and `run_json`. 24 new unit
tests; whole tree `475 passed`; mkdocs `--strict` 0 warnings; ruff / mypy clean. Commit
`0ba1c8d5a1cf61ac468e674d26d458d59dfcdd88`. Two things the lead should know:

1. **The manual page's failure codes were replaced by the brief's.** `docs/manual/jobs.md`
   (S6's design contract) named `INVALID_OPTIONS` / `INVALID_NETWORK` / `SOLVER_ERROR`; the brief
   names `BAD_OPTIONS` / `VALIDATION` / `NO_SLACK_GENERATOR` / `INTERNAL` and distinguishes the
   slack case. I implemented the brief's set and rewrote the page to match (option "update the
   page"). One code was added beyond both: `BAD_REQUEST`, emitted only by `run_json` when the
   text is not valid JSON or not a `SolveRequest` shape — neither list covered that path, and
   "never raises across the boundary" needs it.
2. **`docs/index.md` still says the `jobs` surface "lands" later** (lines 19-20, "in progress"
   table row). Not mine to edit under the brief's file list and S6 (`m2-s6-docs`) owns that page;
   flagging so the wave close picks it up.

## Files (commit `0ba1c8d`; `git show --stat` at the end)

- `src/mambo_power/jobs/models.py` (new, 140 lines): `StructuredError(code, message,
  issues: list[ValidationIssue] | None, details: list[dict] | None)`, `SolveRequest(kind,
  network, options={}, job_id=None)` (`extra="forbid"`), `SolveResult(kind, job_id, status,
  result, error, provenance, warnings: list[str])` (`extra="forbid"`, frozen), the `ResultModel`
  union alias and the `FailureCode` literal. Module docstring documents the discrimination
  choice (below).
- `src/mambo_power/jobs/registry.py` (new, 70 lines): frozen dataclass `KindSpec(kind,
  options_model, result_model, runner)`, `KINDS`, `register` (duplicate → `ValueError`),
  `kinds()` (sorted), private adapters `_run_ac` / `_run_dc` giving `solve_ac` / `solve_dc` the
  uniform `(network, options) -> result` shape.
- `src/mambo_power/jobs/run.py` (new, 243 lines): `run`, `run_json`, helpers for the minimal
  provenance and pydantic error records. Module docstring carries the five-step pipeline and
  the thread caveat of `warnings.catch_warnings`.
- `src/mambo_power/jobs/__init__.py`: exports.
- `tests/unit/test_jobs.py` (new, 24 tests).
- `docs/manual/jobs.md` rewritten (real API, six executed code blocks with their output);
  `docs/api/jobs.md` new (`::: mambo_power.jobs` + models / registry / run sections);
  `mkdocs.yml` nav entry; `docs/changelog.md` Unreleased entry (and `jobs` removed from the
  "landing in the same wave" line).

## RED

Test file written first, package absent:

```
$ uv run pytest -q -p no:cacheprovider tests/unit/test_jobs.py
tests\unit\test_jobs.py:26: in <module>
    from mambo_power import jobs
E   ImportError: cannot import name 'jobs' from 'mambo_power' (C:\Claude Projects\mambo-power-m2\src\mambo_power\__init__.py)
ERROR tests/unit/test_jobs.py
!!!!!!!!!!!!!!!!!!! Interrupted: 1 error during collection !!!!!!!!!!!!!!!!!!!!
1 error in 0.51s
```

First run after the package existed: `1 failed, 25 passed` (with `test_docstrings.py`) —
`test_mutated_invalid_network_through_run_is_a_failed_result` mutated the `Network` *before*
building the `SolveRequest`, and pydantic re-ran `Network`'s after-validator on the way into
the request field, so the `NetworkValidationError` fired at construction, not in `run`. The
test now mutates `req.network` after construction, which is the case the re-validation step in
`run` exists for; the production code was unchanged by this. mypy's first pass had two errors
(a `str` where `ResultProvenance.engine` wants the literal; `result=raw` typed `BaseModel`) —
fixed by inlining the literal and narrowing with `isinstance(raw, ResultModel)`, which also
became the guard for a runner whose result class is outside the union (→ `INTERNAL`).

## GREEN

```
$ uv run mkdocs build --strict          -> exit 0, 0 WARNING lines (grep -c)
$ uv run ruff check .                   -> All checks passed!                          exit 0
$ uv run ruff format --check .          -> 90 files already formatted                  exit 0
$ uv run mypy                           -> Success: no issues found in 31 source files exit 0
$ uv run pytest -q -p no:cacheprovider  -> 475 passed, 10 warnings in 47.45s           exit 0
```
Counts: `--collect-only` gives 451 without `tests/unit/test_jobs.py` (S4's figure) + 24 new =
475. The 10 warnings are the pre-existing pandapower/pandas ones. `tests/unit/test_docstrings.py`
passes on every new public symbol (the walk now reaches `mambo_power.jobs` and its three
submodules).

Executed docs check: the six ```` ```python ```` blocks of `docs/manual/jobs.md` were
concatenated, run with `uv run python`, and their stdout compared with the six ```` ```text ````
blocks — `PAGE OUTPUTS MATCH ( 6 python blocks )`. The site built to `site/api/jobs/` and
`site/manual/jobs/`; `site/` was removed afterwards (gitignored anyway).

## Decisions

### Result discrimination: by `kind`, in validators, over a closed union annotation

`SolveResult.result: AcPowerFlowResult | DcPowerFlowResult | None`. A
`model_validator(mode="before")` looks the payload's `kind` up in `KINDS` and, when `result` is
a dict, validates it with exactly that kind's `result_model`; a `model_validator(mode="after")`
asserts `type(result) is KINDS[kind].result_model`, refuses a result on an unknown kind, and
checks `status` against which of `result` / `error` is present. Why not a pydantic
discriminated union: the discriminator (`kind`) lives on the parent, and the two power-flow
results carry no tag field (the DC result is a strict subset of the AC one — smart-mode union
resolution would work today only because `extra="forbid"` makes the shapes disjoint, and that
is an accident, not a contract). Consequence for later waves: registering a kind means widening
the union annotation; the after-validator catches a result class that is not the kind's model,
the field validation catches one outside the union, and `run` turns the latter into an
`INTERNAL` failure rather than an exception. Tested: `test_result_type_must_match_the_kind`
(both the Python and the JSON path), round-trip gives back the kind's concrete type.

### Non-convergence is `status="ok"`, `result.converged == False`

`solve_ac` returns `converged=False` rather than raising (S4 report, "Notes for S5"), and `run`
passes the result through unchanged — the partial state (iterations, final mismatch, the
voltages it stopped at) is a result, not a failure, and a service decides what to do with it.
Tested with `max_iter=1, init="flat"` on case14: `ok`, `converged False`, `iterations 1`,
`error None`. The manual says so in bold; the `NOT_CONVERGED` "reserved" row from the contract
page was dropped because there is no such code.

### Failure codes and what carries them

| code | source | payload |
|---|---|---|
| `UNKNOWN_KIND` | `kind ∉ KINDS` | message lists registered kinds |
| `BAD_OPTIONS` | options model `ValidationError`; or any key for a kind with `options_model=None` | `details` = pydantic records (`loc` as list, `msg`, `type`; no `input`/`ctx`/`url` so the dict is always JSON) |
| `VALIDATION` | `validate_network` before the runner (mutated network); `NetworkValidationError` from the runner; `NetworkValidationError` while parsing the request JSON in `run_json` | `issues` = the full `ValidationIssue` list |
| `NO_SLACK_GENERATOR` | `NoSlackGeneratorError` | message names the bus |
| `BAD_REQUEST` | `run_json` only: pydantic `ValidationError` on the request text (incl. invalid JSON) | `details` |
| `INTERNAL` | any other exception from the runner; runner returned the wrong class; result class outside the union | `"ExceptionType: message"` |

### Provenance on failure

Minimal `ResultProvenance(kind, version=mambo_power.__version__, solver="none", started_at,
elapsed_s, options=<validated options as dict, {} before validation>)` whenever the kind is a
non-empty string; `None` only when `run_json` could not read a kind from the text at all (the
`ResultProvenance.kind` field has `min_length=1`, so an empty kind cannot be stamped — rather
than invent a placeholder, no stamp). `run_json` echoes `kind` / `job_id` best-effort via
`json.loads` when the request failed to validate (`kind=""` otherwise).

## Judgment calls

1. **`run` re-validates the network** (`validate_network`, the all-issues pass) before calling
   the runner. `Network` validates on construction but not on mutation, and pure-function
   semantics mean `run` must not trust its input; cost is one linear pass per call. Tested
   by mutating `req.network` after construction → `VALIDATION` / `DANGLING_REF`.
2. **Warnings: all categories captured, `simplefilter("always")` inside the context**, so the
   `SetpointConflictWarning` is recorded on every call (the default once-per-location registry
   would otherwise swallow the second run's warning and break purity). Strings are
   `"Category: message"`. The test runs `run` under `simplefilter("error")` to prove nothing
   leaks, and checks `solve_ac` on the same network still warns. The process-global filter
   swap is documented as the one thread caveat (manual note + module docstring); Python 3.14's
   context-aware warnings remove it.
3. **`StructuredError.details`** is an addition to the brief's `(code, message, issues)`:
   `issues` is typed to the model's `ValidationIssue` (closed code set), so pydantic option
   errors cannot ride in it, and a service wants them structured, not only in the message.
4. **`register` refuses duplicates** (`ValueError`) rather than overwriting — a later wave
   silently replacing `pf.ac` would be a bug, not a feature. Tests that register a fake kind
   clean up with `KINDS.pop`.
5. **`kinds()` is sorted** (stable for a capability list); `KINDS` keeps insertion order.
6. **Runner adapters are private module functions** (`_run_ac`, `_run_dc`) so `KindSpec.runner`
   has one signature `(network, options) -> result`; `solve_ac` takes `options` keyword-only and
   `solve_dc` takes none. `_run_ac` asserts the options are `AcOptions` (guaranteed by `run`).
7. **Type check on the runner's return is `type(raw) is spec.result_model`** (exact, not
   `isinstance`) — a subclass would serialise differently and the after-validator uses the same
   test; a mismatch is `INTERNAL` with both class names.
8. **The manual's executed blocks are inline** (python + text fences), matching the convention
   the other manual pages use until S7's `examples/` scripts replace them; the page's example
   table row for `jobs_api.py` in `docs/examples/index.md` is untouched.
9. **`SolveRequest` is not frozen** (`Network` inside it is mutable anyway); `SolveResult` and
   `StructuredError` are frozen like the result models.

## Notes for other slices / wave close

- **S6 / docs:** `docs/index.md` lines 19-20 and the roadmap row still describe `jobs` as
  landing; `docs/design/decisions.md` may want the code table. `docs/examples/index.md` promises
  `jobs_api.py` (S7).
- **S7 / examples:** the six blocks in `docs/manual/jobs.md` are a ready `jobs_api.py`; they run
  from the repository root against `fixtures/`.
- **Spec AC-6:** satisfied on every clause — JSON round-trip of `AcPowerFlowResult` /
  `DcPowerFlowResult` inside `SolveResult`, `version == mambo_power.__version__`, equal results
  modulo timing on a double run, invalid network → `status="failed"` with structured error and
  no exception (through `run_json`, as the brief asked, and through a mutated network via
  `run`), `KINDS == {pf.ac, pf.dc}` with models and runner checked.

## Commit

```
$ git add <9 paths>; git commit -q -F -      exit 0   (no hook blocked)
$ git show --stat HEAD
commit 0ba1c8d5a1cf61ac468e674d26d458d59dfcdd88
Author: Manho Joung <manhojoung@gmail.com>
Date:   Thu Aug 20 21:18:36 2026 -0700

    feat(m2/S5): stateless jobs API — SolveRequest/SolveResult, KINDS registry (pf.ac, pf.dc), run/run_json with structured failures; jobs manual + API page

    Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>
    Claude-Session: https://claude.ai/code/session_01NA3xnvrFVGDqG3azRk8CBs

 docs/api/jobs.md                 |  20 +++
 docs/changelog.md                |  11 +-
 docs/manual/jobs.md              | 245 +++++++++++++++++++++------
 mkdocs.yml                       |   1 +
 src/mambo_power/jobs/__init__.py |  34 ++++
 src/mambo_power/jobs/models.py   | 140 +++++++++++++++
 src/mambo_power/jobs/registry.py |  70 ++++++++
 src/mambo_power/jobs/run.py      | 243 ++++++++++++++++++++++++++
 tests/unit/test_jobs.py          | 356 +++++++++++++++++++++++++++++++++++++++
 9 files changed, 1065 insertions(+), 55 deletions(-)
$ git status --short      (clean afterwards)
```
Not pushed. Dependencies unchanged.
