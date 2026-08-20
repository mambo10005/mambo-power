# mambo-power

A fundamental Python package for power system analysis and electricity market modelling.

- Network and scenario model with a JSON-native schema (pydantic v2)
- AC Newton-Raphson and DC power flow, DC optimal power flow, N-1 contingency analysis
- Market clearing: nodal LMP, zonal with redispatch, multi-period with storage and ramping,
  agent-based bidding
- Own formulations on numpy / scipy / HiGHS; pandapower and PyPSA serve only as test oracles
- Stateless, serializable job API (`mambo_power.jobs`) designed to sit behind a service

Free in both senses: open-source stack end to end, no paid solvers or licences.
Governing spec, plan and ADRs live in the project SDLC record (untracked `.bionic/docs/`).
