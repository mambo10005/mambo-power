"""The jobs API: one stateless, JSON-serialisable call for every analysis kind.

What this shows:

* ``jobs.SolveRequest(kind, network, options, job_id)`` → ``jobs.run`` → ``jobs.SolveResult``
  for ``pf.ac`` and ``pf.dc``; the validated options come back in the provenance.
* ``jobs.run_json`` — text in, text out, exactly what an HTTP handler or a queue worker does —
  and the round trip back to typed results.
* Failures are **data**: an unknown kind, bad options and an invalid network each give
  ``status="failed"`` with a ``StructuredError`` (stable ``code``, message, and the full issue
  list for validation), never an exception across the boundary.
* Warnings raised during the solve (here a ``SetpointConflictWarning`` on the case14 variant
  with two generators at different setpoints) are captured on the result, not printed.

Run from the repository root: ``uv run python examples/04_jobs_api.py``.
"""

from __future__ import annotations

import json

from mambo_power import jobs
from mambo_power.io import matpower

net = matpower.load("fixtures/matpower/case14.m")

# --- 1. Run pf.ac and pf.dc through the same entry point ----------------------------------
print("registered kinds:", jobs.kinds())
ac = jobs.run(jobs.SolveRequest(kind="pf.ac", network=net, options={"init": "flat"}, job_id="a1"))
dc = jobs.run(jobs.SolveRequest(kind="pf.dc", network=net, job_id="d1"))
for outcome in (ac, dc):
    assert outcome.result is not None and outcome.provenance is not None
    print(
        f"{outcome.kind:5s} job_id={outcome.job_id} status={outcome.status} "
        f"result={type(outcome.result).__name__} converged={outcome.result.converged} "
        f"slack P={outcome.result.generators[0].p_mw:.3f} MW"
    )
print("pf.ac options as run:", ac.provenance.options)

# --- 2. JSON in, JSON out --------------------------------------------------------------------
request_text = jobs.SolveRequest(kind="pf.dc", network=net, job_id="json-1").model_dump_json()
reply_text = jobs.run_json(request_text)
payload = json.loads(reply_text)
print("reply keys:", sorted(payload), "| status:", payload["status"])
typed = jobs.SolveResult.model_validate_json(reply_text)  # back to typed models
assert typed.result is not None and dc.result is not None
print("round trip gives", type(typed.result).__name__, end="; ")
print("equal to the direct run:", typed.result.buses == dc.result.buses)

# --- 3. Failures are structured results ----------------------------------------------------
unknown = jobs.run(jobs.SolveRequest(kind="opf.dc", network=net))
assert unknown.error is not None
print("\nunknown kind ->", unknown.status, unknown.error.code, "|", unknown.error.message)

bad_options = jobs.run(jobs.SolveRequest(kind="pf.ac", network=net, options={"tol": -1}))
assert bad_options.error is not None and bad_options.error.details is not None
print("bad options ->", bad_options.status, bad_options.error.code, "|", end=" ")
print([(d["loc"], d["type"]) for d in bad_options.error.details])

request = jobs.SolveRequest(kind="pf.ac", network=net)
request.network.branches[0].to_bus = "nowhere"  # mutate after construction: no re-validation
invalid = jobs.run(request)
assert invalid.error is not None and invalid.error.issues is not None
print("invalid network ->", invalid.status, invalid.error.code, "|", end=" ")
print([(i.code, i.path) for i in invalid.error.issues])

# --- 4. Warnings travel with the result ----------------------------------------------------
roles = matpower.load("fixtures/matpower/derived/case14_roles.m")
outcome = jobs.run(jobs.SolveRequest(kind="pf.ac", network=roles, options={"init": "flat"}))
assert outcome.result is not None
print("\ncase14_roles ->", outcome.status, "converged", outcome.result.converged)
for line in outcome.warnings:
    print("  warning:", line)
