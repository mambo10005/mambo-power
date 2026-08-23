# Jobs API

`mambo_power.jobs` is the one **stateless, fully JSON-serialisable** function every analysis
is reachable through (epic requirement R10, [ADR-004](../design/decisions.md)):

```text
jobs.run(SolveRequest) -> SolveResult
```

It is safe to call from a notebook, a CLI, a worker or a FastAPI handler. A service adds
transport and persistence, never semantics: the body of an HTTP request *is* the
`SolveRequest` JSON and the body of the response *is* the `SolveResult` JSON.

## Why a job surface

The commercial layer will call this package server-side: behind an HTTP handler, from a
worker queue, possibly across processes. A notebook-style API — mutable network objects with
results stored on them, global solver state, exceptions as the failure channel — does not
survive that boundary. `jobs` turns every outcome into data.

## Guarantees

| Guarantee | Meaning |
| --- | --- |
| Pure | `run` is a function of its input. Calling it twice on the same request yields equal results modulo provenance timing (`started_at`, `elapsed_s`). No module-level state. |
| JSON-native | `SolveRequest` and `SolveResult` are pydantic models with `extra="forbid"`; `model_dump_json()` / `model_validate_json()` round-trip them exactly. `run_json(text) -> text` does JSON in, JSON out. |
| Never raises across the boundary | Every failure — an unknown kind, bad options, an invalid network, a slack without a generator, a solver bug — is returned as `SolveResult(status="failed", error=StructuredError(...))`. |
| Stamped | Every result carries a `ResultProvenance`: the solver's own on success (engine, version, kind, solver, `started_at`, `elapsed_s`, options), a minimal one on failure (kind, version, elapsed time, `solver = "none"`). |
| Warnings as data | Warnings the solve emits (`SetpointConflictWarning` for conflicting generator setpoints) are captured and attached as `SolveResult.warnings`, never shown. |
| Discoverable | `jobs.KINDS` lists every analysis the installed version can run, with its option and result models — the capability list a service publishes. |

## `SolveRequest`

| Field | Type | Meaning |
| --- | --- | --- |
| `kind` | `str` | One of the keys of `KINDS`: `"pf.ac"`, `"pf.dc"` in M2; `"opf.dc"`, `"n1"`, `"market.nodal"`, `"market.zonal"`, `"market.multiperiod"`, `"market.agents"` in later waves. |
| `network` | `Network` | The network to solve (inline; the request is self-contained). |
| `options` | `dict[str, Any]` | Kind-specific options, validated against the kind's options model (`AcOptions` for `pf.ac`; none for `pf.dc`). Unknown keys are a failure, not silently ignored. Default `{}`. |
| `job_id` | `str \| None` | An opaque correlation id; echoed on the result. |

## `SolveResult`

| Field | Type | Meaning |
| --- | --- | --- |
| `kind` | `str` | Echo of the request kind (`""` when the request text could not be read at all). |
| `job_id` | `str \| None` | Echo of the request `job_id`. |
| `status` | `"ok" \| "failed"` | Outcome. |
| `result` | kind's result model or `None` | `AcPowerFlowResult` / `DcPowerFlowResult` for the power-flow kinds. Present exactly when `status == "ok"`. |
| `error` | `StructuredError \| None` | Present exactly when `status == "failed"`. |
| `provenance` | `ResultProvenance \| None` | The solver's stamp on success; a minimal stamp on failure; `None` only when not even the kind was readable. |
| `warnings` | `list[str]` | Every warning emitted during the solve, as `"Category: message"` strings. |

`result` is typed by the request **kind**, not by shape: when a `SolveResult` is parsed from
JSON, a `model_validator(mode="before")` looks the kind up in `KINDS` and validates the
`result` document with exactly that kind's `result_model`; an `after` validator then asserts
the instance type matches the kind and that `status` agrees with which of `result` / `error`
is present. The annotation is the closed union of the registered kinds' result models (a wave
that registers a new kind widens it). A pydantic discriminated union was not used because the
discriminator lives on the parent, not inside the result.

### `StructuredError`

| Field | Type | Meaning |
| --- | --- | --- |
| `code` | `str` | Stable code from the table below. |
| `message` | `str` | Human-readable; the exception text when there was one. |
| `issues` | `list[ValidationIssue] \| None` | For `VALIDATION`: the **full** issue list from the model's all-issues pass, so a service can return every problem in one response. |
| `details` | `list[dict] \| None` | For `BAD_OPTIONS` / `BAD_REQUEST`: pydantic error records (`loc`, `msg`, `type`). |

| Error code | When |
| --- | --- |
| `UNKNOWN_KIND` | `kind` is not in `KINDS`; the message lists the registered kinds. |
| `BAD_OPTIONS` | `options` did not validate against the kind's options model (wrong type, unknown key, any key for a kind without options). |
| `VALIDATION` | The network failed validation — on mutation after construction, or in the request JSON (`run_json`); `issues` holds every code and path. |
| `NO_SLACK_GENERATOR` | The slack bus has no in-service generator (`NoSlackGeneratorError` from `effective_roles`). |
| `UNSOLVABLE_NETWORK` | A valid network the numerics it was handed to cannot solve, e.g. DC on a branch with `x == 0` (`UnsolvableNetworkError`) — user data, not a solver bug. |
| `BAD_REQUEST` | `run_json` only: the text is not valid JSON or not a `SolveRequest`. |
| `INTERNAL` | Anything else the runner raised (singular matrix, a bug): `"ExceptionType: message"`. |

**Non-convergence is not a failure.** An AC power flow that does not converge returns
`status="ok"` with `result.converged == False` — `pf.solve_ac` reports non-convergence in the
result rather than raising, and `run` passes that through. The partial state (iterations,
final mismatch, the voltages it stopped at) is useful to a caller; a service decides what to
do with it.

## `KINDS`

```text
KINDS: dict[str, KindSpec]
KindSpec(kind: str, options_model: type[BaseModel] | None, result_model: type[BaseModel],
         runner: Callable[[Network, BaseModel | None], BaseModel])
register(spec: KindSpec) -> None      # refuses a kind already registered
kinds() -> list[str]                  # sorted names
```

The registry is the contract: the contract test asserts `KINDS` lists exactly the kinds the
wave ships (`pf.ac`, `pf.dc` for M2) and that every entry's models are importable and its
runner callable. Later waves `register` their kinds; nothing else in the package changes.

## `run`

```text
run(request: SolveRequest) -> SolveResult
run_json(text: str) -> str
```

1. Look `request.kind` up in `KINDS` (`UNKNOWN_KIND` on miss).
2. Validate `request.options` into the kind's options model (`BAD_OPTIONS`).
3. Re-check the network's invariants with `validate_network` (`VALIDATION`) — a `Network`
   validates on construction but not on mutation, so `run` does not trust its input.
4. Call the runner under `warnings.catch_warnings(record=True)`; wrap what it raises
   (`VALIDATION`, `NO_SLACK_GENERATOR`, `UNSOLVABLE_NETWORK`, `INTERNAL`).
5. Check the runner returned the kind's `result_model`, copy its provenance and the captured
   warnings onto the `SolveResult`.

The runner for `pf.dc` is `pf.solve_dc`; for `pf.ac` it is `pf.solve_ac` with the validated
`AcOptions`. The provenance on a successful result is the one those entry points stamp.

## Using it

A request on case14, the result, its provenance:

```python
from mambo_power import jobs
from mambo_power.io import matpower

net = matpower.load("fixtures/matpower/case14.m")
request = jobs.SolveRequest(kind="pf.dc", network=net, job_id="demo-1")
outcome = jobs.run(request)
print(outcome.status, outcome.kind, outcome.job_id, type(outcome.result).__name__)
print(outcome.result.generators[0])
print(outcome.provenance.kind, outcome.provenance.solver, outcome.provenance.version)
```

```text
ok pf.dc demo-1 DcPowerFlowResult
id='gen-1' bus='bus-1' p_mw=218.99999999999983 q_mvar=0.0 q_limited='none'
pf.dc scipy.sparse.linalg.splu 0.0.1.dev0
```

Options are a plain dict and come back, validated and completed with defaults, in the
provenance:

```python
outcome = jobs.run(
    jobs.SolveRequest(kind="pf.ac", network=net, options={"q_limits": False, "init": "flat"})
)
print(outcome.status, outcome.result.converged, outcome.result.iterations)
print(outcome.provenance.options)
```

```text
ok True 4
{'tol': 1e-08, 'max_iter': 20, 'q_limits': False, 'max_q_rounds': 10, 'init': 'flat'}
```

The capability list:

```python
print(jobs.kinds())
for name, spec in jobs.KINDS.items():
    options = spec.options_model.__name__ if spec.options_model else None
    print(name, options, spec.result_model.__name__)
```

```text
['pf.ac', 'pf.dc']
pf.ac AcOptions AcPowerFlowResult
pf.dc None DcPowerFlowResult
```

JSON in, JSON out — what a handler or a queue worker does:

```python
import json

text = request.model_dump_json()  # the HTTP request body
reply = jobs.run_json(text)  # the HTTP response body
payload = json.loads(reply)
print(sorted(payload))
print(payload["status"], payload["provenance"]["kind"], len(reply))
```

```text
['error', 'job_id', 'kind', 'provenance', 'result', 'status', 'warnings']
ok pf.dc 6098
```

Behind an HTTP handler there is no translation layer:

```text
@app.post("/solve")
def solve(body: jobs.SolveRequest) -> jobs.SolveResult:
    return jobs.run(body)
```

### Failures are data

```python
bad_kind = jobs.run(jobs.SolveRequest(kind="opf.dc", network=net))
print(bad_kind.status, bad_kind.error.code, "|", bad_kind.error.message)

bad_opts = jobs.run(jobs.SolveRequest(kind="pf.ac", network=net, options={"tol": "x"}))
print(bad_opts.status, bad_opts.error.code, "|", bad_opts.error.details)

doc = json.loads(text)
doc["network"]["branches"][0]["to_bus"] = "bus-999"  # a dangling reference in the request JSON
broken = jobs.SolveResult.model_validate_json(jobs.run_json(json.dumps(doc)))
print(broken.status, broken.error.code, "|", [str(i) for i in broken.error.issues])

noslack_net = matpower.load("fixtures/matpower/derived/case14_noslackgen.m")
noslack = jobs.run(jobs.SolveRequest(kind="pf.ac", network=noslack_net))
print(noslack.status, noslack.error.code, "|", noslack.error.message)
```

```text
failed UNKNOWN_KIND | unknown kind "opf.dc"; registered kinds: pf.ac, pf.dc
failed BAD_OPTIONS | [{'type': 'float_parsing', 'loc': ['tol'], 'msg': 'Input should be a valid number, unable to parse string as a number'}]
failed VALIDATION | ['DANGLING_REF at branches[0].to_bus: branch "branch-1": to_bus references missing bus "bus-999"']
failed NO_SLACK_GENERATOR | slack bus "bus-1" (position 0) has no in-service generator; a power flow cannot close the balance
```

### Warnings and non-convergence

On the derived fixture where two in-service generators at bus 2 disagree on their setpoint,
`pf.solve_ac` warns; `jobs.run` attaches the warning instead:

```python
roles_net = matpower.load("fixtures/matpower/derived/case14_roles.m")
roles = jobs.run(jobs.SolveRequest(kind="pf.ac", network=roles_net))
print(roles.status, roles.result.converged, roles.warnings)

stuck = jobs.run(
    jobs.SolveRequest(kind="pf.ac", network=net, options={"max_iter": 1, "init": "flat"})
)
print(stuck.status, stuck.error, stuck.result.converged, stuck.result.iterations)
```

```text
ok True ['SetpointConflictWarning: bus "bus-2": in-service generators disagree on the voltage setpoint (gen-2=1.045, gen-6=1.055); using the last one, 1.055 pu (MATPOWER rule)']
ok None False 1
```

!!! note "Threads"
    Warnings are captured with `warnings.catch_warnings`, which swaps the process-global
    filter list for the duration of the runner; two `run` calls on different threads of one
    interpreter can see each other's warnings (Python 3.14 makes the context thread-local).
    A worker process per job — the deployment shape the SaaS uses — does not hit this.

Long-running kinds (multi-period markets, agent-based bidding) will take a
`cancel` / `progress` hook in the request rather than holding state; their waves define it.

## Relationship to the module-level functions

`pf.solve_dc`, `pf.solve_ac` (and later `opf.solve_dc`, `market.clear_nodal`, ...) remain
the notebook-friendly entry points. They take and return the same pydantic models, raise
Python exceptions on failure, let warnings propagate, and are what `jobs.run` calls. Use them
directly when you are writing Python; use `jobs` when the caller is a service, a queue, or
anything that needs a failure to be data rather than an exception.

See the [API reference](../api/jobs.md) for every field and signature.
