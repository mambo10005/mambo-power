# M8 interop — Step 1 scope (idea-refine)

Wave M8 `interop`, triple build · audited · wave, integration branch `epic/01-foundation` (base
`cdb4fef`, 1175 passed / 4 skipped, CI green on Linux/macOS/Windows). Step 0 confirmed by the user
2026-08-30 ("confirm"), walk required, design interview on.

## The refined idea

Four interchange formats around one pivot: **`Network` is the schema of record; every format is
import → `Network` → export**. Nothing is converted format-to-format, and no format is allowed to
change what the solvers compute — an imported pandapower case that flows in pandapower must flow the
same in `pf.dc`/`pf.ac`, because the parity oracles are the same libraries the importers read.

| format | direction | oracle | fidelity class |
|---|---|---|---|
| pandapower JSON | import + export | pandapower itself (`from_json` → `runpp`/`rundcpp`) | lossless target for the entities the model carries; transformers decide whether the model widens |
| PyPSA | export | PyPSA `optimize` on the exported network vs `opf.solve_dc_opf` (extends M3's parity) | **lossy by nature**: no piecewise cost, no demand bid, no zone |
| PSS/E RAW v33 | import | none bundled — hand-authored fixtures with declared field provenance; MATPOWER's `psse2mpc` field map as the reference | **lossy by nature**: no cost data at all — an imported RAW network flows but does not dispatch |
| CSV bundle | import + export | itself — bit-exact `Network` round-trip; native JSON stays the schema of record | lossless by construction (one CSV per entity table + manifest) |

## Rulings from the Step-1 interview (user, 2026-08-30)

- **D1 — lossy policy: best effort + report.** Every conversion runs; every dropped or approximated
  field is named in a report the caller can read — `ImportReport` already exists (`io/report.py`,
  used by `io.matpower`); exports get its mirror. Nothing silent. *Rejected:* refuse-unless-opted-in
  (noisier for the common case, and the report gives the same information without the exception);
  silent best effort (the M6 and M7 walks both found the silent-drop class expensive).
- **D2 — scope: all four formats.** They parallelise as four slices; RAW is the only one without a
  library oracle, which makes its fixtures the design question rather than a reason to defer.
- **D3 — CSV bundle audience: machine round-trip.** Column names are the model's field names
  verbatim; the criterion is a lossless `Network` round-trip. A human-editable dialect is *not
  doing* until a human consumer exists.
- **D4 — model widening: only for losslessness.** A `Network` field is added only when an import
  would otherwise lose it **and** a solver can carry it; each addition is a design decision in the
  spec with the schema snapshot updated. Candidates (researcher confirms): transformer tap ratio /
  phase shift on `Branch`, bus area, per-element status where the model has none.

## Not doing

- Format-to-format conversion without passing through `Network`.
- A human-editable CSV dialect (D3); a PSS/E RAW **export**; PyPSA **import** (PyPSA networks
  carry time series and components the model has no place for — a later wave if ever).
- MATPOWER export (the `.m` importer exists; export was never asked for).
- Reading pandapower's or PyPSA's *results* tables — only network topology and parameters cross.
- Any change to what the solvers compute. Widening the model is allowed (D4); changing a
  formulation to consume a new field is a separate wave.
- Pinning to formats' *current* upstream versions beyond what the CI matrix installs today;
  version drift is recorded as an assumption, not a compatibility layer.

## Prior art (the alternatives lens)

- `io.matpower` (M1): the importer shape M8 copies — `load`/`loads`/`load_with_report`, derived
  ids, column maps documented per section in `docs/manual/formats.md`, repairs as warnings, islands
  reported not fixed. Its `ImportReport` is D1's vehicle.
- `tests/parity/test_opf_vs_pypsa.py` (M3) and `tests/parity/test_ac_vs_pandapower.py` (M2):
  already build PyPSA and pandapower networks *from* `Network` for parity — the exporters are those
  mappings promoted to a public surface, plus what they skip.
- pandapower's own `to_json`/`from_json` and PyPSA's `export_to_csv_folder`/`import_from_csv_folder`
  are the format conventions the CSV bundle and JSON I/O imitate rather than invent.
- MATPOWER `psse2mpc` for the RAW v33 field map (the PSS/E manual is proprietary).
- Carry-overs from M7 (`continuation-m7.md`) that touch M8: none of the seven is an interop item;
  carry 4 (demand-Hessian test blindness in `dc_opf`'s own tests) is a candidate for a small
  test-only slice if M8 has slack, and is otherwise M9's.

## Open for Step 2 (the design interview)

1. Transformer representation: widen `Branch` with `tap`/`shift` (D4 says yes if the solvers carry
   it — `numerics` already builds `pf_shift`; does `Branch` carry tap?) — researcher confirms.
2. `ext_grid` ↔ slack generator mapping and what happens to a pandapower case with several.
3. Whether importers reach `jobs` (a `SolveRequest` that accepts a pandapower JSON string) or stay
   in-process only; the M4 decision that requests carry a `Network` argues for in-process.
4. RAW fixture provenance: hand-authored from case14/case30 with every field's origin declared, or
   a public-domain RAW file if one exists with a licence the repo can carry.

## Design ledger (Step 2 interview, 2026-08-30)

Frame ratified by the user ("Frame holds — walk S1"): pivot through `Network`, one shared report
type, one model widening, three strategic decisions walked one per turn, six tactical defaults
surfaced at ratification.

- **S1 — `Branch.kind`: explicit, defaulted.** `Branch` gains `kind: Literal["line", "transformer"]`
  with the default derived at construction from `tap != 1 or shift != 0`; importers set it from the
  source table (pandapower `trafo`, RAW transformer records). Schema snapshot moves once; no fixture,
  test or example changes. *Rejected:* inference only (a neutral-tap transformer — pandapower's
  case14 has one at tap 1.0 — imports as a line, and the round-trip is lossy exactly where the
  format is most particular); required field (every `Branch(...)` in the tree changes for the same
  information).
- **S2 — inexpressible costs on export: drop + report.** A piecewise, degree > 2 or elastic-bid cost
  that the target cannot hold is omitted (PyPSA `marginal_cost` 0, no pandapower `poly_cost` row)
  and named in the `ExportReport`. No approximation anywhere: the parity rows are scoped to
  networks whose costs the target can express, so the oracle never compares two different
  problems. *Rejected:* approximate + report (first-segment slope or quadratic fit — runnable, but
  the exported optimum moves by an unbounded amount, silently for anyone not reading the report);
  refuse (contradicts D1 for the common case).
- **S3 — RAW v33 fixture: hand-authored from `case14.m`** with a PROVENANCE note tracing every
  field; the criterion is round-trip agreement with `io.matpower`'s `Network`. A second small
  synthetic file exercises the format's quirks deliberately (CZ/CW codes, four-line transformer
  records, continuation, CKT ids). *Rejected:* the IEEE-14 RAW found in the wild (licence
  undetected, cannot be committed); deferring RAW (contradicts D2).

Tactical defaults, surfaced at ratification: **T1** `ExportReport` mirrors `ImportReport` (same
issue shape, codes, `warnings`), rather than one generic class — the two are read in different
places and a reader should not have to ask which direction it holds; **T2** formats are in-process
only, not `jobs` kinds (M4's decision that requests carry a `Network`); **T3** RAW branch ids encode
`from-to-ckt`, RAW bus ids are the bus numbers as text; **T4** areas map to nothing and are reported
(no solver reads them), zones map by name; **T5** pandapower `ext_grid` → the slack generator; more
than one `ext_grid` → the first becomes slack and the rest PV generators, with a repair warning;
**T6** the CSV bundle is `manifest.json` (schema version, `base_mva`, table list) plus one CSV per
entity table, costs and bids as long-format side tables keyed by owner id; empty cell = `None`,
ids as text, floats via `repr`.
