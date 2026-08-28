# Results

`mambo_power.results` defines the typed, id-keyed values every solver returns. Results are
pydantic v2 models — exact JSON round-trip, unknown fields and non-finite numbers rejected —
in physical units, keyed by the network's stable ids, with a positional numpy view. A result
is a **value**: it is never stored on the `Network`.

## Shape of a power-flow result

```text
DcPowerFlowResult / AcPowerFlowResult
├── provenance: ResultProvenance
├── converged: bool
├── buses:      list[BusResult]      one row per solved bus, solver order
├── branches:   list[BranchResult]   one row per solved branch, solver order
├── generators: list[GenResult]      one row per solved generator, solver order
└── (AC only) iterations, max_mismatch_mva, q_limit_rounds
```

Rows cover the **in-service subset** the solver saw — the same elements
[`NetworkArrays`](numerics.md) holds, in the same order — so every row's `in_service` is
`True` today; the field exists so a later wave can report deactivated elements without a
schema change.

## `ResultProvenance`

Who produced the result, with what, when, and how long it took. Every result carries one.

| Field | Type | Meaning |
| --- | --- | --- |
| `engine` | `"mambo-power"` | Always this package. |
| `version` | `str` | `mambo_power.__version__` at solve time — stamped by the entry point, never typed by hand, so a stored result traces to the code that produced it. |
| `kind` | `str` | Analysis kind: `"pf.dc"`, `"pf.ac"`, later `"opf.dc"`, `"n1"`, `"market.*"`. |
| `solver` | `str` | Linear-algebra backend, e.g. `"scipy.sparse.linalg.splu"`. |
| `started_at` | `datetime` | Wall-clock start, **timezone-aware**; normalised to UTC so the JSON form is a `Z`-suffixed instant. A naive datetime is rejected. |
| `elapsed_s` | `float ≥ 0` | Wall-clock duration of the solve. |
| `options` | `dict[str, Any]` | The options the solver ran with, JSON-native values only (`{}` for DC). |

## `BusResult`

| Field | Type | Unit | Meaning |
| --- | --- | --- | --- |
| `id` | `str` | — | Bus id from the network. |
| `vm_pu` | `float` | pu | Voltage magnitude; 1.0 on every bus for DC. |
| `va_deg` | `float` | degrees | Voltage angle; the slack is 0. |
| `p_mw` | `float` | MW | **Net injection into the network**: generation − load − shunt consumption. |
| `q_mvar` | `float` | MVAr | Net reactive injection; 0 for DC. |
| `role_effective` | `"slack" \| "pv" \| "pq"` | — | The role the bus was solved with (may differ from the declared `Bus.type`). |
| `in_service` | `bool` | — | Whether the bus was part of the solve. |

The injection sign follows MATPOWER's bus equation; pandapower's `res_bus.p_mw` is the
negative (it reports consumption).

## `BranchResult`

Flows are measured **into the branch at each end**, so `p_from_mw` is positive when power
leaves `from_bus` into the branch.

| Field | Type | Unit | Meaning |
| --- | --- | --- | --- |
| `id` | `str` | — | Branch id. |
| `from_bus`, `to_bus` | `str` | — | Bus ids of the from (tap) and to sides. |
| `p_from_mw` | `float` | MW | Active power entering at the from bus. |
| `q_from_mvar` | `float` | MVAr | Reactive power entering at the from bus (0 for DC). |
| `p_to_mw` | `float` | MW | Active power entering at the to bus; `-p_from_mw` for a lossless (DC) solve, and `p_from_mw + p_to_mw` is the loss for AC. |
| `q_to_mvar` | `float` | MVAr | Reactive power entering at the to bus. |
| `loading_pct` | `float \| None` | % | From-side flow over `rating_mva` in percent; **`None`** when the branch is unrated (never `NaN`). |

## `GenResult`

| Field | Type | Unit | Meaning |
| --- | --- | --- | --- |
| `id` | `str` | — | Generator id. |
| `bus` | `str` | — | Bus id. |
| `p_mw` | `float` | MW | Active output; slack-bus generators absorb the balance (first in-service one for DC). |
| `q_mvar` | `float` | MVAr | Reactive output; 0 for DC. |
| `q_limited` | `"none" \| "min" \| "max"` | — | Which reactive limit AC Q-limit enforcement pinned the generator at; `"none"` for DC. |

## `DcPowerFlowResult` and `AcPowerFlowResult`

Both extend `PowerFlowResultBase` (provenance, `converged`, the three tables, `to_arrays()`).

- **DC**: `converged` is always `True`; reactive columns are 0; `vm_pu` is 1.0.
- **AC** adds `iterations` (Newton iterations of the final Q-limit round),
  `max_mismatch_mva` (final power-mismatch ∞-norm in MVA) and `q_limit_rounds` (outer rounds
  run). When `converged` is `False` the tables hold the last iterate.

## `MarketNodalResult`

`market.nodal` clearing (see [Manual › Nodal market](market.md)) returns its own result shape,
`MarketNodalResult`, rather than reusing `DcPowerFlowResult`/`AcPowerFlowResult` — it adds
per-load dispatch (`LoadDispatchResult`, alongside the reused `GenDispatchResult`), per-bus LMPs
(`BusLmpResult`, reused verbatim from `opf.solve_dc_opf`) and settlement fields
(`total_load_payment`, `total_generator_receipts`, `congestion_rent`). It carries the same
`ResultProvenance` every result does and is a frozen value, never stored on the `Network`, same
as every other result on this page. See the nodal-market manual page for the full field
reference and the settlement identity these fields satisfy.

## `MarketMultiperiodResult`

`market.solve_multiperiod` (see [Manual › Multiperiod market](multiperiod.md)) clears a whole
horizon in one LP, so its result is horizon-shaped: a list of per-period results plus the totals
over them. It carries the same `ResultProvenance` every result does, is frozen, and follows the
same non-converged convention as `MarketNodalResult` — when `status != "Optimal"`, `periods` is
empty, every total is `0.0` and `message` carries the diagnostic.

| Field | Type | Unit | Meaning |
| --- | --- | --- | --- |
| `status` | `str` | — | HiGHS model status, passed through verbatim. |
| `message` | `str \| None` | — | Diagnostic when `status != "Optimal"`. |
| `n_periods` | `int` | — | Periods cleared: `len(Scenario.periods)`, or 1 for a period-less scenario. |
| `periods` | `list[MarketPeriodResult]` | — | One entry per period, in scenario order. |
| `objective_cost` | `float` | \$ | Total generation cost over the horizon. Storage is costless in the objective — `model.Storage` has no cost field, so a unit's only economic footprint is the round-trip loss it imposes on generation. |
| `total_load_payment` | `float` | \$ | Horizon sum of the per-period load payments. |
| `total_generator_receipts` | `float` | \$ | Horizon sum of the per-period generator receipts. |
| `total_storage_charge_payment` | `float` | \$ | Horizon sum of the per-period storage charge payments. |
| `total_storage_discharge_revenue` | `float` | \$ | Horizon sum of the per-period storage discharge revenues. |
| `congestion_rent` | `float` | \$ | Horizon sum of the per-period congestion rents. |

Each `MarketPeriodResult` carries `period` (its zero-based index), the four row lists and its own
copy of the five settlement totals:

| Field | Type | Meaning |
| --- | --- | --- |
| `generators` | `list[GenPeriodDispatchResult]` | `GenDispatchResult` plus `ramp_dual`, this period's ramp-constraint shadow price. |
| `loads` | `list[LoadDispatchResult]` | Reused verbatim from the nodal result. |
| `buses` | `list[BusLmpResult]` | This period's LMPs, energy and congestion components. |
| `storage` | `list[StorageDispatchResult]` | `charge_mw`, `discharge_mw`, `soc_mwh` (end of period), and three duals: `soc_dual`, `energy_bound_dual`, `power_limit_dual`. |

Charge and discharge are **two non-negative columns, not one signed one**, which is why both can
be nonzero in the same period — see [Multiperiod market › Two columns, not one signed
column](multiperiod.md#two-columns-not-one-signed-column). The settlement identity these fields
satisfy, in the general form that includes the phase-shift and shunt correction terms, is on
[Multiperiod market › Settlement](multiperiod.md#the-identity-in-its-general-form).

## `MarketZonalResult`

`market.solve_zonal` (see [Manual › Zonal market](zonal.md)) chains three solves — a zonal
clearing, a min-cost redispatch onto the real network, and `market.solve_nodal` as the reference —
and its content is their *relationship*, so it carries **two dispatch layers** rather than one.
Same provenance, frozen, and the same non-converged convention: on `status != "Optimal"` every row
list is empty, every figure is `0.0`, and `message` names which of the three stages failed.

!!! warning "`generators` here is what the market *sold*, not what the network delivers"
    `MarketZonalResult.generators` / `.loads` are the **zonal** clearing's schedule;
    `.generators_final` / `.loads_final` are the **redispatched** one the network actually
    carries. On `MarketNodalResult` and on every power-flow result, `generators` *is* the
    delivered dispatch — the same attribute name means two different things across these result
    types, so code that switches on result type has to know which layer it wants. Settlement,
    reporting and plotting want the `_final` pair.

| Field | Type | Meaning |
| --- | --- | --- |
| `zones` | `list[ZonePriceResult]` | One clearing price per zone (`id`, `price`), from the zonal stage. Not a rollup of the bus LMPs. |
| `generators`, `loads` | `list[GenDispatchResult]`, `list[LoadDispatchResult]` | The **sold** schedule — the zonal clearing, before the network was consulted. |
| `generators_final`, `loads_final` | same types | The **delivered** dispatch after redispatch, which is also the nodal optimum's own dispatch. |
| `redispatch_generators` | `list[GenRedispatchResult]` | Per-generator move: `delta_up_mw`, `delta_down_mw`. |
| `redispatch_loads` | `list[LoadRedispatchResult]` | Per-load move: `delta_restore_mw`, `delta_curtail_mw` — **not** `delta_up_mw`/`delta_down_mw`. |
| `branches` | `list[OpfBranchFlowResult]` | Per-branch flow and flow-limit shadow price at the final point. |
| `buses` | `list[BusLmpResult]` | Per-bus LMP at the **final** point. These are nodal prices; the zonal prices the market cleared at are in `zones`, and the two disagreeing is the subject of the result. |
| `redispatch_payment` | `float` (\$/h) | Settlement figure: what the operator pays to move from the sold schedule to the delivered one. |
| `welfare_gap` | `float` (\$/h) | Exactness row: `0` by the theorem. A nonzero value means the chain is wrong. |
| `generation_cost_gap` | `float` (\$/h) | Diagnostic: `cost(zonal) − cost(nodal)`. **Not** sign-constrained. |

Both delta pairs are netted to the canonical representative, so exactly one of each pair is
nonzero and `final == start + up − down` holds exactly whatever vertex the solver picked.

Three things about this object that catch readers, each covered on the zonal manual page:

- `redispatch_payment` is **not** always non-negative — see [When `redispatch_payment` goes
  negative](zonal.md#when-redispatch_payment-goes-negative).
- The three figures are **two** independent quantities plus a check:
  `redispatch_payment + generation_cost_gap` is exactly the curtailment-compensation term, and
  `0` on a fixed-load network. See [The three figures are two independent quantities plus a
  check](zonal.md#the-three-figures-are-two-independent-quantities-plus-a-check).
- There are **no corridor rows**. A corridor's own flow and capacity price are array-level
  quantities (`opf.zonal.zonal_dc_opf`); at the market level the same information shows up as the
  price separation between the zones a corridor joins.

This is the first market result type carrying per-branch rows, which makes **both** sides of the
settlement identity computable from the object alone, with no second solve — worked in full at
[Zonal market › Settlement, from the result object
alone](zonal.md#settlement-from-the-result-object-alone).

## JSON round-trip

Results serialise with the standard pydantic surface and come back equal:

```python
from mambo_power import pf
from mambo_power.io import matpower
from mambo_power.results import DcPowerFlowResult

net = matpower.load("fixtures/matpower/case14.m")
result = pf.solve_dc(net)

text = result.model_dump_json()  # one JSON document, ~6 kB for case14
again = DcPowerFlowResult.model_validate_json(text)
print(again == result)
print(text[:120])
```

```text
True
{"provenance":{"engine":"mambo-power","version":"0.0.1.dev0","kind":"pf.dc","solver":"scipy.sparse.linalg.splu","started
```

Result models are frozen (`model_config.frozen = True`) — build a modified copy with
`model_copy(update=...)` if you need one. Because `NaN`/`inf` are rejected, a result that
serialised will always parse back.

## `to_arrays()` — the positional view

For numeric consumers that want columns rather than rows, `to_arrays()` returns a frozen
`PowerFlowArrays` with one numpy array per column, rows in table order (the `NetworkArrays`
order when the result came from a solver):

| Attribute | Shape | From |
| --- | --- | --- |
| `bus_ids` | `tuple[str, ...]` | `buses[i].id` |
| `vm_pu`, `va_deg`, `p_bus_mw`, `q_bus_mvar` | `(n_bus,)` | bus columns |
| `branch_ids` | `tuple[str, ...]` | `branches[k].id` |
| `p_from_mw`, `q_from_mvar`, `p_to_mw`, `q_to_mvar` | `(n_branch,)` | branch columns |
| `loading_pct` | `(n_branch,)` | `nan` where the table has `None` |
| `gen_ids` | `tuple[str, ...]` | `generators[g].id` |
| `p_gen_mw`, `q_gen_mvar` | `(n_gen,)` | generator columns |

```python
import numpy as np

arrays = result.to_arrays()
print(arrays.p_from_mw[:3])
print(np.isnan(arrays.loading_pct).all())  # case14 has no ratings
heaviest = arrays.branch_ids[int(np.argmax(np.abs(arrays.p_from_mw)))]
print(heaviest)
```

```text
[147.83859556  71.16140444  70.01463596]
True
branch-1
```

## Building results from arrays

Solvers do not construct rows by hand. `results.dc_result_from_arrays(arr, theta_rad=...,
p_from_pu=..., p_inj_pu=..., gen_p_pu=..., provenance=...)` is the one place that walks from
`NetworkArrays` positions back to ids and multiplies per-unit quantities by `base_mva` on the
way out; it validates array shapes and raises `ValueError` on a mismatch.
`results.ac_result_from_arrays(arr, v=..., s_bus_pu=..., s_from_pu=..., s_to_pu=...,
gen_p_pu=..., gen_q_pu=..., bus_type=..., q_limited=..., converged=..., iterations=...,
max_mismatch_pu=..., q_limit_rounds=..., provenance=...)` is the AC counterpart: complex
voltages become `vm_pu` / `va_deg`, complex flows become the four branch columns,
`loading_pct` is the from-side apparent flow over the rating, and each generator's
`q_limited` is inherited from its bus's pin. [`07_results_and_export.py`](../examples/index.md#7-results-and-export)
round-trips an AC result and exports its tables to CSV.
