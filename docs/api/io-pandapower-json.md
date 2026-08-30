# `mambo_power.io.pandapower_json`

pandapower JSON (`pp.to_json` / `pp.from_json`) importer and exporter: `load` / `loads` /
`load_with_report` read a `pandapowerNet` document into a `Network`; `dumps` / `dump` /
`dumps_with_report` write one that loads in `pp.from_json` and on which pandapower's own
`rundcpp` / `runpp` agree with `pf.solve_dc` / `pf.solve_ac`. pandapower is imported lazily.
See [File formats › pandapower JSON](../manual/formats.md#pandapower-json) for the table map,
unit conversions, the `ext_grid` rule, report codes and limitations.

::: mambo_power.io.pandapower_json
