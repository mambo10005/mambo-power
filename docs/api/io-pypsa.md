# `mambo_power.io.pypsa`

PyPSA export: `to_network(net)` returns a `pypsa.Network` built from a `Network`;
`to_network_with_report` also returns the `ExportReport` naming every field PyPSA cannot carry
(piecewise and degree > 2 costs, load bids, zones, generator reactive limits). PyPSA is
imported lazily. No generator ever carries `p_set` — PyPSA's optimiser reads it as a fixed
dispatch. `CODES` lists the report codes this module can emit.

::: mambo_power.io.pypsa
