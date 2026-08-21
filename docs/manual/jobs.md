# Jobs API

!!! warning "API lands in wave M2"
    `mambo_power.jobs` is being implemented in the same wave as this page. This page is the
    **design contract** — the names, shapes and guarantees the implementation is tested
    against (epic requirement R10, ADR-004). Until the module exists, the module-level
    functions such as `pf.solve_dc` are the way to run an analysis; `jobs` calls exactly
    those.

## Why a job surface

The commercial layer will call this package server-side: behind an HTTP handler, from a
worker queue, possibly across processes. A notebook-style API — mutable network objects with
results stored on them, global solver state — does not survive that boundary. So every
analysis is reachable through one **stateless, fully JSON-serialisable** function:

```text
jobs.run(SolveRequest) -> SolveResult
```

It is safe to call from a notebook, a CLI, a worker or a FastAPI handler. The same call works
everywhere; a service adds transport and persistence, never semantics.

## Guarantees

| Guarantee | Meaning |
| --- | --- |
| Pure | `run` is a function of its input. Calling it twice on the same request yields equal results modulo provenance timing (`started_at`, `elapsed_s`). No module-level state. |
| JSON-native | `SolveRequest` and `SolveResult` are pydantic models; `model_dump_json()` / `model_validate_json()` round-trip them exactly. |
| Never raises across the boundary | Every failure — an invalid network, a singular matrix, an unknown kind, a solver bug — is returned as `SolveResult(status="failed", error=StructuredError(...))`. Exceptions do not cross `run`. |
| Stamped | Every successful result carries a `ResultProvenance` (engine, version, kind, solver, started_at, elapsed_s, options) plus the kind's own diagnostics. |
| Discoverable | `jobs.KINDS` lists every analysis the installed version can run, with its option and result models — the capability list a service publishes. |

## `SolveRequest`

| Field | Type | Meaning |
| --- | --- | --- |
| `kind` | `str` | One of the keys of `KINDS`: `"pf.dc"`, `"pf.ac"` in M2; `"opf.dc"`, `"n1"`, `"market.nodal"`, `"market.zonal"`, `"market.multiperiod"`, `"market.agents"` in later waves. |
| `network` | `Network` | The network to solve (inline; the request is self-contained). |
| `options` | `dict[str, Any]` | Kind-specific options, validated against the kind's options model (`AcOptions` for `pf.ac`; empty for `pf.dc`). Unknown keys are a failure, not silently ignored. |

## `SolveResult`

| Field | Type | Meaning |
| --- | --- | --- |
| `status` | `"ok" \| "failed"` | Outcome. |
| `kind` | `str` | Echo of the request kind. |
| `result` | kind's result model or `None` | `DcPowerFlowResult` / `AcPowerFlowResult` for the power-flow kinds. Present when `status == "ok"`. |
| `error` | `StructuredError \| None` | Present when `status == "failed"`. |

`StructuredError` carries a stable `code`, a `message`, and an optional `issues` list — for an
invalid network that is the full `ValidationIssue` list from the model's all-issues pass, so a
service can return every problem in one response.

| Error code | When |
| --- | --- |
| `UNKNOWN_KIND` | `kind` is not in `KINDS`. |
| `INVALID_OPTIONS` | The options did not validate against the kind's options model. |
| `INVALID_NETWORK` | The network failed validation; `issues` holds the codes and paths. |
| `SOLVER_ERROR` | The runner raised (singular matrix, no slack generator, ...); `message` carries the exception text. |
| `NOT_CONVERGED` | Reserved: AC power flow that did not converge returns `status="ok"` with `result.converged == False`, not a failure — the partial result is useful. |

## `KINDS`

```text
KINDS: dict[str, KindSpec]
KindSpec(options_model: type[BaseModel], result_model: type[BaseModel], runner: Callable)
```

The registry is the contract: a test asserts every entry has an options model, a result model
and a runner, and that `KINDS` lists exactly the kinds the wave ships (`pf.ac`, `pf.dc` for
M2). Later waves register their kinds; nothing else in the package needs to change.

## `run`

```text
run(request: SolveRequest) -> SolveResult
```

1. Look up `request.kind` in `KINDS` (`UNKNOWN_KIND` on miss).
2. Validate `request.options` against the kind's options model (`INVALID_OPTIONS`).
3. Start the clock, call the runner with the network and the validated options.
4. On success wrap the typed result; on any exception wrap it as a `StructuredError` with the
   matching code.

The runner for `pf.dc` is `pf.solve_dc`; for `pf.ac` it is `pf.solve_ac`. The provenance on
the result is the one those entry points stamp.

## Intended use

From a script or notebook, once the module lands:

```text
from mambo_power import jobs
from mambo_power.io import matpower

request = jobs.SolveRequest(kind="pf.dc", network=matpower.load("fixtures/matpower/case14.m"))
outcome = jobs.run(request)
assert outcome.status == "ok"
print(outcome.result.generators[0].p_mw)
```

Behind an HTTP handler the body of the request *is* the `SolveRequest` JSON and the body of
the response *is* the `SolveResult` JSON — no translation layer:

```text
@app.post("/solve")
def solve(body: jobs.SolveRequest) -> jobs.SolveResult:
    return jobs.run(body)
```

Long-running kinds (multi-period markets, agent-based bidding) will take a
`cancel` / `progress` hook in the request rather than holding state; their waves define it.

## Relationship to the module-level functions

`pf.solve_dc`, `pf.solve_ac` (and later `opf.solve_dc`, `market.clear_nodal`, ...) remain
the notebook-friendly entry points. They take and return the same pydantic models, raise
Python exceptions on failure, and are what `jobs.run` calls. Use them directly when you are
writing Python; use `jobs` when the caller is a service, a queue, or anything that needs a
failure to be data rather than an exception.
