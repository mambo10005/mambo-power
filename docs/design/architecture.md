# Architecture

mambo-power is one Python package, `mambo_power`, split into modules with a strict import
direction. Only two kinds of objects cross module boundaries: **model** types (`Network` and
its entities) and **results** types. Numerics are derived views; no module holds global
state; every public function takes and returns pydantic models.

## Component diagram

Solid arrows are the allowed import directions today; the lower groups are modules that
this and later waves add (their dependencies are already fixed by the epic design).

```mermaid
flowchart TB
    subgraph present["Shipped (M1 + M2 so far)"]
        model["model<br/>Network, entities, validation errors"]
        io["io<br/>matpower, native"]
        numerics["numerics<br/>NetworkArrays, ybus, bbus, ptdf, lodf"]
        pf["pf<br/>solve_dc, dc.solve"]
        results["results<br/>BusResult, BranchResult, GenResult,<br/>ResultProvenance, from_arrays"]
    end
    subgraph wave["Landing in M2"]
        ac["pf.ac_newton"]
        jobs["jobs<br/>SolveRequest, SolveResult, KINDS, run"]
    end
    subgraph later["Later waves"]
        opf["opf (M3)"]
        n1["contingency (M3)"]
        market["market (M4-M7)"]
        formats["io: pandapower_json, pypsa,<br/>psse_raw, csv_bundle (M8)"]
    end

    io --> model
    numerics --> model
    pf --> numerics
    pf --> results
    results --> numerics
    ac --> numerics
    ac --> results
    jobs --> pf
    jobs --> results
    jobs --> model
    opf -.-> numerics
    n1 -.-> pf
    n1 -.-> numerics
    market -.-> opf
    formats -.-> model
```

Rules the diagram encodes:

- `io` speaks only `model`. An importer produces a `Network`; it never touches arrays or
  solvers.
- `numerics` is the **only** module that holds positional indices and the **single** site
  where physical units are divided by `base_mva`.
- Solvers (`pf`, later `opf`, `contingency`, `market`) consume `NetworkArrays`, never a
  `Network` directly, and hand plain arrays to `results.from_arrays`, which walks back to ids
  and multiplies by `base_mva` on the way out.
- `market` composes `opf`; it never reimplements it.
- `jobs` is the outermost layer: it validates a request, calls a solver entry point, times
  it and wraps any exception into a structured failure.
- pandapower and PyPSA appear nowhere in this graph. They are development dependencies used
  by the parity test tier only.

## Ownership table

Each concept has exactly one owner (single source of truth). The agreement test is what keeps
consumers honest when the owner changes.

| Concept | Owner (SSoT) | Consumers | Agreement test |
| --- | --- | --- | --- |
| Network schema | `model` | io, numerics, jobs, future SaaS | round-trip of every importer against schema fixtures; JSON-schema snapshot test |
| Per-unit conversion and positional indices | `numerics.NetworkArrays` | every solver, `results.from_arrays` | Ybus parity against pandapower `makeYbus` on the IEEE fixtures (fails if the conversion drifts) |
| Power-flow solutions | `pf` | contingency, market (AC feasibility check), results | parity against MATPOWER published solutions and pandapower `runpp` / `rundcpp` |
| Effective bus roles | `numerics.effective_roles` (M2) | pf.ac, pf.dc, results | modified-case14 fixture vs pandapower |
| Island repair | `model.repair_islands` (M2) | every importer | islanded case14 variant: warning emitted, main island matches pandapower |
| Result provenance | `results.ResultProvenance` | jobs, docs | `provenance.version == mambo_power.__version__` |
| DC-OPF formulation | `opf` (M3) | market.* | MATPOWER `rundcopf`, PyPSA `optimize` |
| LMP / congestion rent | `market.nodal` (M4) | zonal comparison, multiperiod, agents | settlement identities; LMP(slack) = λ |
| Analysis kinds registry | `jobs` | future SaaS capability list | contract test: every kind has request model, result model, runner |

## Data flow of one solve

```mermaid
sequenceDiagram
    participant U as caller
    participant IO as io.matpower
    participant M as model.Network
    participant N as numerics.NetworkArrays
    participant S as pf.dc.solve
    participant R as results.from_arrays
    U->>IO: load("case14.m")
    IO->>M: Network(buses=..., branches=...)
    M-->>M: validate every invariant in one pass
    M-->>U: Network (physical units, string ids)
    U->>N: NetworkArrays.from_network(net)
    N-->>N: drop out-of-service elements, divide by base_mva, assign positions
    U->>S: solve(arr)
    S-->>S: B'θ = P − p_shift, flows = Bf·θ + pf_shift
    S->>R: dc_result_from_arrays(arr, θ, flows, injections, gen_p, provenance)
    R-->>U: DcPowerFlowResult (MW, keyed by ids)
```

The public entry point `pf.solve_dc(net)` performs the three middle steps for you and stamps
the provenance. The network is never modified; the result is a separate value.

## Module map on disk

```text
src/mambo_power/
  __init__.py       __version__ from package metadata
  model/            entities.py (Bus, Branch, Generator, ...), network.py (Network, validate_network), errors.py
  io/               matpower.py (load, loads, *_with_warnings), native.py (load, loads, save, dumps)
  numerics/         arrays.py (NetworkArrays), ybus.py, bbus.py, ptdf.py, lodf.py
  pf/               __init__.py (solve_dc), dc.py (solve, DcSolution)
  results/          tables.py, provenance.py, power_flow.py, from_arrays.py
```

The test suite mirrors the boundaries: `tests/unit` exercises each module hermetically,
`tests/parity` compares against the oracles, `tests/property` runs hypothesis over random
radial and meshed networks. See [Contributing](../contributing.md).
