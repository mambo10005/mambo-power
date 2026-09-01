# Getting started

This page takes you from a clean machine to a solved DC power flow on the IEEE 14-bus case in
about five minutes. Every code block on this page has been executed against the wave head; the
numbers shown are the real ones.

## Install

mambo-power is on PyPI as of `v0.1.0`:

```bash
pip install mambo-power
# or: uv add mambo-power
```

!!! note "What gets installed"
    The wheel ships only the package and its `py.typed` marker. The MATPOWER fixtures under
    `fixtures/` and the test suite are in the sdist and the repository, not in the wheel, so
    the examples below — and the [tutorials](tutorials/index.md) — assume you are in a clone of
    the repository, not just a `pip install`.

To work from a clone (required for the examples on this page, and for the tutorials):

```bash
git clone https://github.com/mambo10005/mambo-power.git
cd mambo-power
uv sync                 # runtime deps only: numpy, scipy, highspy, pydantic
uv run python -c "import mambo_power; print(mambo_power.__version__)"
```

Add `--all-groups` to `uv sync` if you also want the development tools (pytest, hypothesis,
ruff, mypy, the pandapower/PyPSA oracles) and the documentation toolchain.

Without uv, any Python ≥ 3.11 environment works:

```bash
pip install -e .        # or: pip install .
```

## Load a MATPOWER case

```python
from mambo_power.io import matpower

net = matpower.load("fixtures/matpower/case14.m")
print(len(net.buses), len(net.branches), len(net.generators), len(net.loads), len(net.shunts))
```

```text
14 20 5 11 1
```

`net` is a [`Network`](manual/model.md): a pydantic model in physical units (MW, MVAr, kV,
degrees) with stable string ids. Every entity is a plain attribute:

```python
print(net.buses[0])
print(net.branches[0])
```

```text
id='bus-1' base_kv=1.0 type='slack' in_service=True vm_pu=1.06 va_deg=0.0 v_min_pu=0.94 v_max_pu=1.06 area='1' zone='1' geo=None
id='branch-1' from_bus='bus-1' to_bus='bus-2' r=0.01938 x=0.05917 b=0.0528 rating_mva=None tap_ratio=None shift_deg=None in_service=True
```

Some files need small repairs on the way in (case14 stores `baseKV = 0`, which becomes
`1.0`). `load` applies them silently; `load_with_warnings` tells you what it did:

```python
net, warnings = matpower.load_with_warnings("fixtures/matpower/case14.m")
print(len(warnings))
print(warnings[0])
```

```text
14
BASE_KV_REPLACED: bus-1: BASE_KV is 0; base_kv set to 1.0 (line 25)
```

See [File formats](manual/formats.md) for the full column map and every warning.

## Validate

Construction already validated the network: `matpower.load` cannot return an invalid
`Network`. Validation checks **every** invariant in one pass and reports all failures at once,
so you fix a bad file in one round trip rather than one error at a time:

```python
from mambo_power.model import Branch, Bus, Network, NetworkValidationError

try:
    Network(
        base_mva=100,
        buses=[Bus(id="a", base_kv=110, type="pq"), Bus(id="b", base_kv=0, type="pq")],
        branches=[Branch(id="l", from_bus="a", to_bus="c", r=0.01, x=0.1, b=0.0)],
    )
except NetworkValidationError as err:
    print(err)
    print(sorted(err.codes))
```

```text
Network validation failed with 4 issues:
  - BAD_BASE at buses[1].base_kv: bus "b": base_kv must be > 0, got 0.0
  - DANGLING_REF at branches[0].to_bus: branch "l": to_bus references missing bus "c"
  - NO_SLACK at buses: no in-service slack bus defined
  - DISCONNECTED_BUS at buses[1]: bus "b" is not connected to bus "a" over in-service branches
['BAD_BASE', 'DANGLING_REF', 'DISCONNECTED_BUS', 'NO_SLACK']
```

Models are mutable and mutation does **not** re-validate. After editing a network, re-check it
with `validate_network`, which returns the issue list instead of raising:

```python
from mambo_power.model import validate_network

net.buses[1].base_kv = -1
print(validate_network(net))
net.buses[1].base_kv = 1.0
```

```text
[ValidationIssue(code='BAD_BASE', path='buses[1].base_kv', message='bus "bus-2": base_kv must be > 0, got -1')]
```

## Run a DC power flow

```python
from mambo_power import pf

result = pf.solve_dc(net)
print(result.converged, result.provenance.kind, result.provenance.solver)
```

```text
True pf.dc scipy.sparse.linalg.splu
```

`solve_dc` builds the per-unit arrays, solves \(B'\theta = P - P_\text{shift}\) with the slack
angle fixed at zero, computes branch flows, and returns a typed result in MW keyed by the
network's ids. The network is not modified.

## Read the results

```python
for bus in result.buses[:3]:
    print(f"{bus.id:7s} va={bus.va_deg:8.3f} deg  p={bus.p_mw:8.2f} MW  role={bus.role_effective}")
for branch in result.branches[:3]:
    print(f"{branch.id:9s} {branch.from_bus}->{branch.to_bus}  p_from={branch.p_from_mw:8.2f} MW")
for gen in result.generators:
    print(f"{gen.id:6s} at {gen.bus}  p={gen.p_mw:7.2f} MW")
```

```text
bus-1   va=   0.000 deg  p=  219.00 MW  role=slack
bus-2   va=  -5.012 deg  p=   18.30 MW  role=pv
bus-3   va= -12.954 deg  p=  -94.20 MW  role=pv
branch-1  bus-1->bus-2  p_from=  147.84 MW
branch-2  bus-1->bus-5  p_from=   71.16 MW
branch-3  bus-2->bus-3  p_from=   70.01 MW
gen-1  at bus-1  p= 219.00 MW
gen-2  at bus-2  p=  40.00 MW
gen-3  at bus-3  p=   0.00 MW
gen-4  at bus-6  p=   0.00 MW
gen-5  at bus-8  p=   0.00 MW
```

The slack generator (`gen-1`) absorbed the balance: total load is 259 MW, `gen-2` dispatches
its declared 40 MW, and the lossless DC model has no losses, so `gen-1` ends at 219 MW. Bus
`p_mw` is the *net injection into the network*, so it sums to zero across the network.

Results are values. They serialise to JSON and back exactly, and expose a positional numpy
view for numeric work:

```python
text = result.model_dump_json()
again = type(result).model_validate_json(text)
print(again == result)

arrays = result.to_arrays()
print(arrays.p_from_mw[:3])
```

```text
True
[147.83859556  71.16140444  70.01463596]
```

See [Results](manual/results.md) for every field and the provenance stamp.

## Run an AC power flow

The AC Newton-Raphson solver has the same shape: a network in, an `AcPowerFlowResult` out,
with the Newton diagnostics on top. `AcOptions` controls the tolerance, the iteration budget,
Q-limit enforcement and the starting point (`init="flat"` here; the default `"auto"` warm-starts
from stored bus voltages when every bus has them).

```python
ac = pf.solve_ac(net, options=pf.AcOptions(init="flat"))
print(ac.converged, ac.iterations, ac.q_limit_rounds, f"{ac.max_mismatch_mva:.1e} MVA")
for bus in ac.buses[:3]:
    print(f"{bus.id:7s} vm={bus.vm_pu:.4f} pu  va={bus.va_deg:8.3f} deg  q={bus.q_mvar:7.2f} MVAr")
print(f"losses {sum(b.p_from_mw + b.p_to_mw for b in ac.branches):.3f} MW")
```

```text
True 4 0 8.8e-13 MVA
bus-1   vm=1.0600 pu  va=   0.000 deg  q= -16.55 MVAr
bus-2   vm=1.0450 pu  va=  -4.983 deg  q=  30.86 MVAr
bus-3   vm=1.0100 pu  va= -12.725 deg  q=   6.08 MVAr
losses 13.393 MW
```

Generators pinned at a reactive limit show up as `q_limited="min"` / `"max"` on their
`GenResult` rows (none on case14; six on case118). See [Power flow](manual/power-flow.md) for
the formulation, the Q-limit semantics and the parity figures.

## Build a network by hand

You do not need a file. A two-bus network is a few lines:

```python
from mambo_power.model import Branch, Bus, Generator, Load, Network
from mambo_power.io import native

mini = Network(
    base_mva=100,
    buses=[Bus(id="b1", base_kv=110, type="slack"), Bus(id="b2", base_kv=110, type="pq")],
    branches=[Branch(id="l12", from_bus="b1", to_bus="b2", r=0.01, x=0.1, b=0.02)],
    generators=[
        Generator(
            id="g1",
            bus="b1",
            p_mw=0,
            q_mvar=0,
            p_min_mw=0,
            p_max_mw=200,
            q_min_mvar=-100,
            q_max_mvar=100,
            v_set_pu=1.0,
        )
    ],
    loads=[Load(id="d2", bus="b2", p_mw=50, q_mvar=10)],
)
res = pf.solve_dc(mini)
print(res.branches[0].p_from_mw, res.generators[0].p_mw, round(res.buses[1].va_deg, 4))
native.save(mini, "mini.json")  # the native format is the model's JSON
```

```text
50.0 50.0 -2.8648
```

## Next steps

- [Network model](manual/model.md) — every entity, field, unit and validation code.
- [Numerics](manual/numerics.md) — Ybus, Bbus, PTDF and LODF from the same network.
- [Power flow](manual/power-flow.md) — the DC and AC formulations, Q-limit semantics,
  effective roles, parity and timing figures.
- [Jobs API](manual/jobs.md) — the stateless `run(SolveRequest)` surface for services.
- [Examples](examples/index.md) — seven runnable scripts executed in CI, embedded in the
  manual.
