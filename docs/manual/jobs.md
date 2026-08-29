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
| `kind` | `str` | One of the keys of `KINDS`: `"pf.ac"`, `"pf.dc"` in M2; `"opf.dc"`, `"n1"` in M3; `"market.nodal"` in M4; `"market.multiperiod"` in M5; `"market.zonal"` in M6; `"market.agents"` in M7. |
| `network` | `Network \| None` | The network to solve (inline; the request is self-contained). Mutually exclusive with `scenario`. |
| `scenario` | `Scenario \| None` | The scenario to solve — a network plus its `periods`. Mutually exclusive with `network`. |
| `options` | `dict[str, Any]` | Kind-specific options, validated against the kind's options model (`AcOptions` for `pf.ac`; none for `pf.dc`). Unknown keys are a failure, not silently ignored. Default `{}`. |
| `job_id` | `str \| None` | An opaque correlation id; echoed on the result. |

**Exactly one of `network` and `scenario`** (wave M5): neither or both is a `ValueError` at
construction, which `run_json` turns into a `BAD_REQUEST` failure. `network` is the original
shape and every pre-existing `SolveRequest(kind=..., network=...)` — in Python or as stored
JSON — keeps working unchanged; `scenario` is what a genuine multi-period kind needs, since
a bare `Network` cannot supply `Scenario.periods`. What a runner actually receives is
`request.resolved_scenario`: the `scenario` as given, or the `network` wrapped as
`Scenario(network=network)` — single-period, `periods=None`, exactly every one-period kind's
existing semantics. It is recomputed on each access rather than cached, so a `network`
mutated in place after construction is still reflected.

### Request-size bounds

A `SolveRequest` is a wire format, so the lists inside it that multiply the size of the solve
carry an explicit maximum. Both are enforced by the model, not by a future HTTP layer — added
after the models were treated as stable, either bound would be a breaking change — and both come
back as `BAD_OPTIONS` (or `BAD_REQUEST`, for a bound on the scenario itself) rather than as a
solve that runs for a very long time.

| Bound | Value | On |
| --- | --- | --- |
| `MAX_PERIODS` (`model.scenario`) | 200 | `Scenario.periods`. More than eight days at hourly resolution, and well past what these builders are sized for. |
| `MAX_CORRIDORS` (`market.zonal`) | 500 | `MarketZonalOptions.corridors`. A complete graph on 32 zones; the list is also echoed back in `provenance.options`, so it bounds the response too. |

Neither is a statement about what the solvers can handle — they are amplification guards. A small
request expands into a large matrix (a 34 kB horizon expands to ~20 million matrix nonzeros), and
an unbounded list in a network-facing model is an unbounded solve.

## `SolveResult`

| Field | Type | Meaning |
| --- | --- | --- |
| `kind` | `str` | Echo of the request kind (`""` when the request text could not be read at all). |
| `job_id` | `str \| None` | Echo of the request `job_id`. |
| `status` | `"ok" \| "failed"` | Outcome. |
| `result` | kind's result model or `None` | The registered kind's own model — `AcPowerFlowResult` / `DcPowerFlowResult` for the power-flow kinds, `OpfDcResult`, `N1Result`, `MarketNodalResult`, `MarketMultiperiodResult`, `MarketZonalResult`, `MarketAgentsResult` for the rest. Present exactly when `status == "ok"`. |
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
| `INFEASIBLE_LP` | An `opf.dc`, `market.nodal`, `market.multiperiod`, `market.zonal` or `market.agents` LP/QP came back with a non-`"Optimal"`, non-`"Unbounded"` status: there is no feasible dispatch at all, so there is nothing to return. For `market.agents` this is the round the loop stopped in, whichever round that was. |
| `UNBOUNDED_LP` | The same five kinds, status `"Unbounded"`. |
| `BAD_REQUEST` | `run_json` only: the text is not valid JSON, not a `SolveRequest`, or carries neither/both of `network` and `scenario`. |
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
         runner: Callable[[Scenario, BaseModel | None], BaseModel])
register(spec: KindSpec) -> None      # refuses a kind already registered
kinds() -> list[str]                  # sorted names
```

The registry is the contract: the contract test asserts `KINDS` lists exactly the kinds the
wave ships — eight as of M7 — and that every entry's models are importable and its runner
callable. Later waves `register` their kinds; nothing else in the package changes.

Every runner has the one `(Scenario, options) -> result` shape (wave M5). A kind that only
needs a network reads `.network` off the scenario; the `Network`-to-`Scenario` wrap that
`market.nodal`'s runner used to do for itself moved outward, to
`SolveRequest.resolved_scenario`, so no runner does it any more.

## `run`

```text
run(request: SolveRequest) -> SolveResult
run_json(text: str) -> str
```

1. Look `request.kind` up in `KINDS` (`UNKNOWN_KIND` on miss).
2. Validate `request.options` into the kind's options model (`BAD_OPTIONS`).
3. Resolve the request to a `Scenario` via `request.resolved_scenario` and re-check its
   network's invariants with `validate_network` (`VALIDATION`) — a `Network` validates on
   construction but not on mutation, so `run` does not trust its input. The wrap itself
   re-runs `Network`'s own validator, so it can raise where reading `request.network` never
   did; `run` catches that at the same point, and it stays a graceful `VALIDATION` failure.
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
['market.agents', 'market.multiperiod', 'market.nodal', 'market.zonal', 'n1', 'opf.dc', 'pf.ac', 'pf.dc']
pf.ac AcOptions AcPowerFlowResult
pf.dc None DcPowerFlowResult
opf.dc OpfDcOptions OpfDcResult
n1 N1Options N1Result
market.nodal MarketNodalOptions MarketNodalResult
market.multiperiod MarketMultiperiodOptions MarketMultiperiodResult
market.zonal MarketZonalOptions MarketZonalResult
market.agents MarketAgentsOptions MarketAgentsResult
```

JSON in, JSON out — what a handler or a queue worker does. The byte count below moves by a
digit or two between runs: `provenance.elapsed_s` is part of the payload.

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
ok pf.dc 6092
```

Behind an HTTP handler there is no translation layer:

```text
@app.post("/solve")
def solve(body: jobs.SolveRequest) -> jobs.SolveResult:
    return jobs.run(body)
```

### Failures are data

The demo below uses `"pf.telepathy"`, which is **deliberately fictional**. An unknown-kind
example has to name a kind that can never become real: `"market.zonal"` stood here until wave M6
registered it, at which point this page, `examples/04_jobs_api.py` and
`tests/unit/test_jobs.py`'s `test_unknown_kind_is_a_failed_result` all stopped demonstrating what
they claimed — three sites breaking on the same day. Naming the *next* planned kind only re-arms
that. A kind nobody will ever implement never does.

```python
bad_kind = jobs.run(jobs.SolveRequest(kind="pf.telepathy", network=net))  # never registered
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
failed UNKNOWN_KIND | unknown kind "pf.telepathy"; registered kinds: market.agents, market.multiperiod, market.nodal, market.zonal, n1, opf.dc, pf.ac, pf.dc
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

`market.multiperiod` clears a whole horizon in one call and takes no `cancel` / `progress`
hook: a 24-period case14 horizon solves in well under a second, so there is nothing to
report progress on yet. A kind whose runtime makes that untrue would take such a hook in
the request rather than holding state; its wave defines it.

`market.zonal`'s `MarketZonalOptions.corridors` is market design data the network does not
carry (a transfer capacity is administratively negotiated, not a network invariant), so unlike
every other kind's options it is not solver tuning — see
`mambo_power.market.zonal.CorridorLimit`. `corridors` defaults to `[]`, which is not shorthand
for "no limit": with no corridors at all, every zone must supply itself, a legitimate (and
often infeasible) market design in its own right.

Every way of getting the corridor list wrong is a **caller** error and is classified as one —
none of them reaches you as `INTERNAL`, and all of them are caught before any solve is
attempted:

| The mistake | Code |
| --- | --- |
| A corridor naming the same zone twice | `BAD_OPTIONS` |
| The same zone pair given twice, **in either order** | `BAD_OPTIONS` |
| A negative `cap_mw`, or more than `MAX_CORRIDORS` entries | `BAD_OPTIONS` |
| A corridor naming a zone no bus is assigned to | `VALIDATION`, with a `DANGLING_REF` issue whose `path` is the offending `options.corridors[i].zone1` or `.zone2` |

The first three are decided by `MarketZonalOptions` itself, so they come back with pydantic's own
`details`. The fourth cannot be — an options model has no network to check against — so it is
raised at resolution time as a network-validation issue, which is what a dangling reference is,
and every offending end of every corridor is reported in one pass rather than stopping at the
first.

Its three-stage chain (zonal clearing, redispatch, nodal reference) reports whichever stage first
failed to reach `Optimal` through the same `INFEASIBLE_LP` / `UNBOUNDED_LP` translation the other
market kinds use.

`market.agents`' `MarketAgentsOptions.strategies` is market design data in the same sense — which
bidding rule each generator plays is a statement about the game being simulated, not a knob on the
solver. It maps a generator id to a `StrategyConfig`, a discriminated union on `kind`
(`price_taker` | `markup`), and it crosses JSON **as data**: `{"strategies": {"g1": {"kind":
"markup", "step": 0.5}}}`. A callable never crosses this boundary. `solve_agents` also takes an
in-process `strategies=` argument accepting any object conforming to the `Strategy` Protocol —
that seam exists for a rule the config union cannot express, and `jobs` deliberately cannot reach
it, so nothing a service can send changes which code runs.

An empty `strategies` mapping is meaningful rather than missing: it is a market in which nobody
bids strategically, and it clears exactly as `market.nodal` would.

Every way of getting the agent set wrong is a **caller** error, and none of them arrives as
`INTERNAL` — measured through `jobs.run`, not inferred:

| The mistake | Code |
| --- | --- |
| An unknown `StrategyConfig` kind | `BAD_OPTIONS` |
| A non-positive `max_iterations`, or a non-positive `offer_tol` | `BAD_OPTIONS` |
| An `offer_tol` below `2 * step` for a markup agent | `BAD_OPTIONS` |
| A strategy naming a generator the network does not have — or one it has but its arrays do not (out of service, or on a bus that is), or one with no `Generator.cost` to depart from | `VALIDATION`, with a `DANGLING_REF` issue whose `path` is `options.strategies` |

The first three are decided by `MarketAgentsOptions` itself, so they come back with pydantic's own
`details`. The fourth cannot be — an options model has no network to check against — so it is
raised at resolution time, before any solve, as a network-validation issue.

!!! warning "`status` is the LP's; `converged` is the loop's"
    A `market.agents` job that comes back `status="ok"` has an `Optimal` **clearing**. Whether the
    best-response iteration settled is a separate field on the result — `converged`, with
    `termination_reason` naming which of `converged` / `iteration_cap` / `cycle` ended it. A run
    can clear optimally in every round and still not converge. `jobs` does not fold one into the
    other, and neither should a caller: a non-converged run is a successful job with an honest
    result, not a failure.

## Relationship to the module-level functions

`pf.solve_dc`, `pf.solve_ac`, `opf.solve_dc_opf`, `contingency.n1`, `market.solve_nodal`,
`market.solve_multiperiod`, `market.solve_zonal` and `market.solve_agents` remain the
notebook-friendly entry points.
They take and return the same pydantic models, raise
Python exceptions on failure, let warnings propagate, and are what `jobs.run` calls. Use them
directly when you are writing Python; use `jobs` when the caller is a service, a queue, or
anything that needs a failure to be data rather than an exception.

See the [API reference](../api/jobs.md) for every field and signature.
