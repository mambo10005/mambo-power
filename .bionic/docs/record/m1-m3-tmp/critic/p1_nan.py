"""P1: does the model accept non-finite floats, and does the native round-trip survive them?"""
import numpy as np
from mambo_power.model import Bus, Branch, Generator, Network, NetworkValidationError
from mambo_power.io import native
from mambo_power.numerics import NetworkArrays, ybus, bbus


def gen(bus="a"):
    return Generator(id="g", bus=bus, p_mw=0, q_mvar=0, p_min_mw=0, p_max_mw=1,
                     q_min_mvar=0, q_max_mvar=1, v_set_pu=1)


# 1. NaN on an optional bus field
net = Network(base_mva=100, buses=[Bus(id="a", base_kv=110, type="slack", vm_pu=float("nan"))],
              generators=[gen()])
print("1) constructed with vm_pu=nan:", net.buses[0].vm_pu)
s = native.dumps(net)
print("   dumps ->", s.replace("\n", " "))
try:
    back = native.loads(s)
    print("   loads(dumps(net)) == net ?", back == net, "| back.vm_pu =", back.buses[0].vm_pu)
except Exception as e:
    print("   loads(dumps(net)) raised", type(e).__name__, str(e).splitlines()[0])

# 2. NaN on a required field (branch x) -> AC-5 expression verbatim
net2 = Network(
    base_mva=100,
    buses=[Bus(id="a", base_kv=110, type="slack"), Bus(id="b", base_kv=110, type="pq")],
    branches=[Branch(id="l", from_bus="a", to_bus="b", r=0.01, x=float("nan"), b=0.0)],
    generators=[gen()],
)
print("2) constructed with x=nan:", net2.branches[0].x)
print("   model_dump_json ->", net2.model_dump_json())
try:
    ok = Network.model_validate_json(net2.model_dump_json()) == net2
    print("   AC-5 expression ->", ok)
except Exception as e:
    print("   AC-5 expression raised", type(e).__name__, "->", str(e).splitlines()[0:3])
arr = NetworkArrays.from_network(net2)
print("   ybus finite?", bool(np.isfinite(ybus(arr).toarray()).all()))
try:
    m = bbus(arr)
    print("   bbus x==0 guard tripped? no -> bbus finite?", bool(np.isfinite(m.toarray()).all()))
except ValueError as e:
    print("   bbus guard:", e)

# 3. JSON text carrying NaN / Infinity tokens (what a SaaS client might send)
txt = ('{"base_mva": Infinity, "buses": [{"id": "a", "base_kv": 110, "type": "slack"}], '
       '"generators": [{"id":"g","bus":"a","p_mw":NaN,"q_mvar":0,"p_min_mw":0,"p_max_mw":1,'
       '"q_min_mvar":0,"q_max_mvar":1,"v_set_pu":1}]}')
try:
    n3 = native.loads(txt)
    print("3) JSON with Infinity/NaN tokens accepted: base_mva =", n3.base_mva,
          "gen p_mw =", n3.generators[0].p_mw)
    a3 = NetworkArrays.from_network(n3)
    print("   p_gen_pu =", a3.p_gen_pu, "gen_p_pu =", a3.gen_p_pu)
except NetworkValidationError as e:
    print("3) named error:", e.codes)
except Exception as e:
    print("3) rejected with", type(e).__name__, str(e).splitlines()[0])
