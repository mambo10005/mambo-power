# `mambo_power.io.csv_bundle`

The CSV bundle: `manifest.json` plus one CSV per entity table, a bit-exact re-spelling of the
native schema for spreadsheet tooling. `load(dump(net)) == net` on every fixture; a bundle that
is not exact is refused with a named `ImportReport` error. See
[File formats › CSV bundle](../manual/formats.md).

::: mambo_power.io.csv_bundle
