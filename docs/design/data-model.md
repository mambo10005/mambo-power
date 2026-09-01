# Data model

The native file format **is** the pydantic model: `Network.model_dump_json()` writes it,
`Network.model_validate_json()` reads it, and `Network.json_schema()` emits the JSON schema
that is snapshot-tested in CI. The diagram shows the entities, their key fields and
multiplicities; the [Network model manual page](../manual/model.md) has the full field tables.

## Class diagram

```mermaid
classDiagram
    class Network {
        +int schema_version = 1
        +float base_mva
        +list~Bus~ buses
        +list~Branch~ branches
        +list~Generator~ generators
        +list~Load~ loads
        +list~Shunt~ shunts
        +list~Storage~ storage
        +list~Zone~ zones
        +json_schema() dict
    }
    class Bus {
        +str id
        +float base_kv
        +BusType type
        +bool in_service
        +float vm_pu
        +float va_deg
        +float v_min_pu
        +float v_max_pu
        +str area
        +str zone
        +Geo geo
    }
    class Geo {
        +float lat
        +float lon
    }
    class Branch {
        +str id
        +str from_bus
        +str to_bus
        +float r
        +float x
        +float b
        +float rating_mva
        +float tap_ratio
        +float shift_deg
        +bool in_service
    }
    class Generator {
        +str id
        +str bus
        +float p_mw
        +float q_mvar
        +float p_min_mw
        +float p_max_mw
        +float q_min_mvar
        +float q_max_mvar
        +float v_set_pu
        +bool in_service
        +GeneratorCost cost
    }
    class PolynomialCost {
        +kind = polynomial
        +list~float~ coefficients
        +float startup
        +float shutdown
    }
    class PiecewiseCost {
        +kind = piecewise
        +list~tuple~ points
        +float startup
        +float shutdown
    }
    class Load {
        +str id
        +str bus
        +float p_mw
        +float q_mvar
        +bool in_service
    }
    class Shunt {
        +str id
        +str bus
        +float g_mw
        +float b_mvar
        +bool in_service
    }
    class Storage {
        +str id
        +str bus
        +float p_max_mw
        +float energy_mwh
        +float soc_initial
        +float efficiency_charge
        +float efficiency_discharge
        +bool in_service
    }
    class Zone {
        +str id
        +str name
    }

    Network "1" *-- "1..*" Bus
    Network "1" *-- "*" Branch
    Network "1" *-- "*" Generator
    Network "1" *-- "*" Load
    Network "1" *-- "*" Shunt
    Network "1" *-- "*" Storage
    Network "1" *-- "*" Zone
    Bus "1" o-- "0..1" Geo
    Branch "*" --> "1" Bus : from_bus
    Branch "*" --> "1" Bus : to_bus
    Generator "*" --> "1" Bus : bus
    Load "*" --> "1" Bus : bus
    Shunt "*" --> "1" Bus : bus
    Storage "*" --> "1" Bus : bus
    Bus "*" --> "0..1" Zone : zone
    Generator "1" o-- "0..1" PolynomialCost : cost
    Generator "1" o-- "0..1" PiecewiseCost : cost
```

Optional fields (`vm_pu`, `va_deg`, `v_min_pu`, `v_max_pu`, `area`, `zone`, `geo`,
`rating_mva`, `tap_ratio`, `shift_deg`, `cost`, `name`) default to `None` and are omitted
from native JSON on write. `in_service` defaults to `true` everywhere.

References between entities are **string ids**, never object references or positional
integers. `Network` validation checks that every reference resolves (`DANGLING_REF`) and that
ids are unique within each collection (`DUPLICATE_ID`). Positional integers exist only inside
`numerics.NetworkArrays`.

## Units convention

The model stores **physical units**, exactly as MATPOWER and pandapower files do, so files stay
human-readable and interop stays lossless. Per-unit conversion happens in exactly one place,
`NetworkArrays.from_network`, and never in the model.

| Quantity | Unit in the model | Field suffix | Converted in `NetworkArrays` as |
| --- | --- | --- | --- |
| Active power | MW | `_mw` | `/ base_mva` → pu |
| Reactive power | MVAr | `_mvar` | `/ base_mva` → pu |
| Apparent power (ratings) | MVA | `_mva` | `/ base_mva` → pu (`inf` when absent) |
| Energy | MWh | `_mwh` | not consumed by a solver yet |
| Voltage magnitude | per unit of `base_kv` | `_pu` | unchanged |
| Voltage angle, phase shift | degrees | `_deg` | `radians()` |
| Bus nominal voltage | kV | `base_kv` | unchanged (not needed by the pu formulation) |
| Branch `r`, `x`, `b` | per unit on `base_mva` | none | unchanged |
| Tap ratio | dimensionless, from-side | `tap_ratio` | `1.0` when `None` |
| Shunt | MW consumed / MVAr injected at 1.0 pu | `g_mw`, `b_mvar` | `/ base_mva` → pu admittance |

Field names are snake_case with the unit suffix; booleans are booleans (`in_service: bool`
rather than a `0 | 1` status integer); the bus role is a closed literal
`"slack" | "pv" | "pq"` and MATPOWER's type 4 (isolated) maps to `in_service = False`.

## Result tables

Results mirror the model's id convention: every row names the element by id, units are
physical, and `None` (never `NaN`) marks a quantity that does not exist.

```mermaid
classDiagram
    class ResultProvenance {
        +engine = mambo-power
        +str version
        +str kind
        +str solver
        +datetime started_at
        +float elapsed_s
        +dict options
    }
    class PowerFlowResultBase {
        +ResultProvenance provenance
        +bool converged
        +list~BusResult~ buses
        +list~BranchResult~ branches
        +list~GenResult~ generators
        +to_arrays() PowerFlowArrays
    }
    class DcPowerFlowResult
    class AcPowerFlowResult {
        +int iterations
        +float max_mismatch_mva
        +int q_limit_rounds
    }
    class BusResult {
        +str id
        +float vm_pu
        +float va_deg
        +float p_mw
        +float q_mvar
        +BusRole role_effective
        +bool in_service
    }
    class BranchResult {
        +str id
        +str from_bus
        +str to_bus
        +float p_from_mw
        +float q_from_mvar
        +float p_to_mw
        +float q_to_mvar
        +float loading_pct
    }
    class GenResult {
        +str id
        +str bus
        +float p_mw
        +float q_mvar
        +QLimitSide q_limited
    }
    PowerFlowResultBase <|-- DcPowerFlowResult
    PowerFlowResultBase <|-- AcPowerFlowResult
    PowerFlowResultBase *-- ResultProvenance
    PowerFlowResultBase *-- "*" BusResult
    PowerFlowResultBase *-- "*" BranchResult
    PowerFlowResultBase *-- "*" GenResult
```

See [Manual › Results](../manual/results.md) for the field semantics and the JSON round-trip.
