# `mambo_power.io.limitations`

The `LIMITATIONS` registry: format module name → every report code it can emit. Lives above
the format modules in the import graph (it imports them for their `CODES`; they import only
[`io.report`](io-report.md)), and a test pins that every registered code is documented in
[File formats](../manual/formats.md).

::: mambo_power.io.limitations
