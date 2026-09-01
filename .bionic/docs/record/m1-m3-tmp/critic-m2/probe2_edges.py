"""P2: edge probes - divergence overflow, no-PQ network, warm-from-q-off, jobs boundary, islands."""
import json
import warnings

from mambo_power import jobs
from mambo_power.io import matpower
from mambo_power.model import (
    Branch, Bus, Generator, Load, Network, Shunt, Storage, Zone, repair_islands_entities,
)
from mambo_power.pf import AcOptions, solve_ac, solve_dc

warnings.simplefilter("ignore")


def gen(id, bus, p, vset=1.0, qmin=-100, qmax=100, in_service=True):
    return Generator(id=id, bus=bus, p_mw=p, q_mvar=0, p_min_mw=0, p_max_mw=1e6,
                     q_min_mvar=qmin, q_max_mvar=qmax, v_set_pu=vset, in_service=in_service)


print("=== B. divergence to overflow: does solve_ac raise?")
for load_mw in (1e6, 1e9, 1e12, 1e15, 1e18):
    net = Network(base_mva=100,
                  buses=[Bus(id="b1", base_kv=230, type="slack"), Bus(id="b2", base_kv=230, type="pq")],
                  branches=[Branch(id="l", from_bus="b1", to_bus="b2", r=0.01, x=0.1, b=0.0)],
                  generators=[gen("g", "b1", 0)],
                  loads=[Load(id="ld", bus="b2", p_mw=load_mw, q_mvar=0)])
    try:
        r = solve_ac(net, options=AcOptions(init="flat"))
        print(f"  load={load_mw:.0e}: converged={r.converged} it={r.iterations} "
              f"mismatch={r.max_mismatch_mva:.3e} vm2={r.buses[1].vm_pu:.3e}")
    except Exception as e:
        print(f"  load={load_mw:.0e}: RAISED {type(e).__name__}: {str(e)[:200]}")
    out = jobs.run(jobs.SolveRequest(kind="pf.ac", network=net, options={"init": "flat"}))
    print(f"     jobs.run -> status={out.status} code={out.error.code if out.error else None}")

print("=== E. slack + PV only (no PQ bus)")
net = Network(base_mva=100,
              buses=[Bus(id="b1", base_kv=230, type="slack"), Bus(id="b2", base_kv=230, type="pv")],
              branches=[Branch(id="l", from_bus="b1", to_bus="b2", r=0.01, x=0.1, b=0.0)],
              generators=[gen("g1", "b1", 0), gen("g2", "b2", 50, vset=1.02)])
try:
    r = solve_ac(net, options=AcOptions(init="flat"))
    print(f"  converged={r.converged} it={r.iterations} rounds={r.q_limit_rounds} "
          f"vm={[b.vm_pu for b in r.buses]} q={[g.q_mvar for g in r.generators]}")
except Exception as e:
    print("  RAISED", type(e).__name__, str(e)[:300])

print("=== E2. slack only (single bus)")
net1 = Network(base_mva=100, buses=[Bus(id="b1", base_kv=230, type="slack")],
               generators=[gen("g1", "b1", 0)], loads=[Load(id="ld", bus="b1", p_mw=10, q_mvar=5)])
try:
    r = solve_ac(net1)
    print("  ac ok", r.converged, r.iterations, r.generators[0].p_mw, r.generators[0].q_mvar)
except Exception as e:
    print("  ac RAISED", type(e).__name__, str(e)[:300])
try:
    r = solve_dc(net1)
    print("  dc ok", r.generators[0].p_mw)
except Exception as e:
    print("  dc RAISED", type(e).__name__, str(e)[:300])

print("=== P5. case118: warm from q-off solution, then q on (docs: one re-pin round)")
net = matpower.load("fixtures/matpower/case118.m")
off = solve_ac(net, options=AcOptions(init="flat", q_limits=False))
flat_on = solve_ac(net, options=AcOptions(init="flat", q_limits=True))
state = {b.id: (b.vm_pu, b.va_deg) for b in off.buses}
for b in net.buses:
    b.vm_pu, b.va_deg = state[b.id]
warm_on = solve_ac(net, options=AcOptions(init="auto", q_limits=True))
pf = sorted((g.bus, g.q_limited) for g in flat_on.generators if g.q_limited != "none")
pw = sorted((g.bus, g.q_limited) for g in warm_on.generators if g.q_limited != "none")
d = max(abs(a.vm_pu - b.vm_pu) for a, b in zip(flat_on.buses, warm_on.buses))
print(f"  warm from q-off: it={warm_on.iterations} rounds={warm_on.q_limit_rounds} pins_equal={pf == pw} dvm={d:.1e}")
state = {b.id: (b.vm_pu, b.va_deg) for b in flat_on.buses}
for b in net.buses:
    b.vm_pu, b.va_deg = state[b.id]
warm_on2 = solve_ac(net, options=AcOptions(init="auto", q_limits=True))
pw2 = sorted((g.bus, g.q_limited) for g in warm_on2.generators if g.q_limited != "none")
d2 = max(abs(a.vm_pu - b.vm_pu) for a, b in zip(flat_on.buses, warm_on2.buses))
print(f"  warm from q-on state: it={warm_on2.iterations} rounds={warm_on2.q_limit_rounds} pins_equal={pf == pw2} dvm={d2:.1e}")

print("=== P3. jobs boundary")
net14 = matpower.load("fixtures/matpower/case14.m")
base = json.loads(jobs.SolveRequest(kind="pf.ac", network=net14).model_dump_json())


def try_json(label, doc_or_text):
    text = doc_or_text if isinstance(doc_or_text, str) else json.dumps(doc_or_text)
    try:
        out = json.loads(jobs.run_json(text))
        code = out["error"]["code"] if out["error"] else None
        print(f"  {label}: status={out['status']} code={code} kind={out['kind']!r}")
    except Exception as e:
        print(f"  {label}: RAISED {type(e).__name__}: {str(e)[:120]}")


base_text = json.dumps(base)
try_json("huge int max_iter", {**base, "options": {"max_iter": 10**40}})
try_json("20000-digit int in tol", base_text[:-1] + ', "options": {"tol": ' + "9" * 20000 + "}}")
try_json("1e400 tol", base_text[:-1] + ', "options": {"tol": 1e400}}')
try_json("kind with path sep", {**base, "kind": "../pf.ac"})
try_json("job_id non-string", {**base, "job_id": 12})
try_json("options nested dict", {**base, "options": {"tol": {"a": 1}}})
try_json("options list", {**base, "options": [1, 2]})
try_json("network null", {**base, "network": None})
try_json("deep options (3000)", base_text[:-1] + ', "options": {"x": ' + "[" * 3000 + "]" * 3000 + "}}")
try_json("top-level deep array", "[" * 3000 + "]" * 3000)
try_json("duplicate kind keys", '{"kind":"pf.dc","kind":"pf.ac","network":' + json.dumps(base["network"]) + "}")
try_json("NaN token in network", base_text.replace('"base_mva": 100.0', '"base_mva": NaN'))
try_json("base_mva zero", {**base, "network": {**base["network"], "base_mva": 0}})
try_json("pf.dc with options", {**base, "kind": "pf.dc", "options": {"tol": 1}})
try_json("max_iter 0", {**base, "options": {"max_iter": 0}})
try_json("max_iter bool", {**base, "options": {"max_iter": True}})
try_json("tol as string '1e-8'", {**base, "options": {"tol": "1e-8"}})

print("=== P4. islands")
buses = [Bus(id="s", base_kv=230, type="slack"), Bus(id="a", base_kv=230, type="pq"),
         Bus(id="i1", base_kv=230, type="pv"), Bus(id="i2", base_kv=230, type="pq"),
         Bus(id="dead", base_kv=230, type="pq", in_service=False, zone="Z")]
branches = [Branch(id="s-a", from_bus="s", to_bus="a", r=0.01, x=0.1, b=0),
            Branch(id="a-i1", from_bus="a", to_bus="i1", r=0.01, x=0.1, b=0, in_service=False),
            Branch(id="i1-i2", from_bus="i1", to_bus="i2", r=0.01, x=0.1, b=0),
            Branch(id="i2-dead", from_bus="i2", to_bus="dead", r=0.01, x=0.1, b=0),
            Branch(id="a-dead", from_bus="a", to_bus="dead", r=0.01, x=0.1, b=0, in_service=False)]
gens = [gen("gs", "s", 0), gen("gi", "i1", 10, vset=1.01), gen("gdead", "dead", 5)]
loads = [Load(id="la", bus="a", p_mw=20, q_mvar=5), Load(id="li2", bus="i2", p_mw=3, q_mvar=1),
         Load(id="loff", bus="i2", p_mw=3, q_mvar=1, in_service=False)]
shunts = [Shunt(id="sh", bus="i2", g_mw=0, b_mvar=5)]
storage = [Storage(id="st", bus="i1", p_max_mw=5, energy_mwh=10, soc_initial=0.5,
                   efficiency_charge=0.9, efficiency_discharge=0.9)]
b2, br2, g2, l2, sh2, st2, issues = repair_islands_entities(buses, branches, gens, loads, shunts, storage)
for i in issues:
    print("  ", i.code, i.bus_ids, i.element_ids)
print("   live buses:", [b.id for b in b2 if b.in_service],
      "live branches:", [b.id for b in br2 if b.in_service])
print("   live gens:", [g.id for g in g2 if g.in_service], "live loads:", [x.id for x in l2 if x.in_service],
      "live shunts:", [s.id for s in sh2 if s.in_service], "live storage:", [s.id for s in st2 if s.in_service])
try:
    net = Network(base_mva=100, buses=b2, branches=br2, generators=g2, loads=l2, shunts=sh2,
                  storage=st2, zones=[Zone(id="Z")])
    r = solve_ac(net)
    print("   network valid; solve converged", r.converged, [b.id for b in r.buses])
except Exception as e:
    print("   Network RAISED", type(e).__name__, str(e)[:300])
