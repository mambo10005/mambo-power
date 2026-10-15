# Command line

`pip install mambo-power` installs a `mambo-power` command ([ADR-027](../design/decisions.md));
`python -m mambo_power` is the same program. It is the [jobs API](jobs.md) and the
[file formats](formats.md) from a shell — every subcommand is a thin wrapper over a function
the package already exposes, so nothing is reachable from the command line that is not
reachable from Python, and nothing behaves differently there. Output is JSON or plain lines,
nothing is interactive, and the exit status is 0 (done), 1 (the job failed, or a conversion
reported issues under `--strict`, or a usage error reported on stderr) or 2 (bad arguments).

| Command | Does |
| --- | --- |
| `mambo-power kinds [--json]` | List the registered analyses with their option and result models. |
| `mambo-power cases` | List the bundled cases. |
| `mambo-power run REQUEST [-o OUT] [--indent N]` | Run a `SolveRequest` JSON file (`-` for stdin) and print the `SolveResult` JSON. |
| `mambo-power solve KIND SOURCE [--options JSON] [--job-id ID] [-o OUT] [--indent N]` | The same without writing the request: `SOURCE` is a bundled case name or a network file. |
| `mambo-power convert SOURCE TARGET [--from F] [--to F] [--strict]` | Read a network in one format, write it in another; every report issue goes to stderr. |

## Formats

`solve` and `convert` read a bundled case by name (`case14`, `derived/case14_rated`,
`case14_v33.raw`) or a path, and infer the format from the path: `.m` MATPOWER, `.raw` PSS/E,
`.json` the native JSON, a directory the CSV bundle. pandapower JSON shares the `.json`
extension, so it is named: `--from pandapower` / `--to pandapower` (and needs pandapower
installed). A conversion prints every import and
export report issue — a dropped cost, a renumbered id, a defaulted field — one per line on
stderr, so a lossy conversion is never silent; `--strict` turns any issue into exit status 1.

## Examples

```console
$ mambo-power solve opf.dc case14 --indent 2 -o case14-opf.json
$ mambo-power solve opf.scopf derived/case14_rated --options '{"corrective": true}' \
    | python -c "import json,sys; r=json.load(sys.stdin)['result']; print(r['objective_cost'])"
8447.25…
$ mambo-power convert case14 case14.raw
COST_DROPPED: 5 generator cost(s) dropped: RAW carries no economic data
RAW_ID_RENUMBERED: 11 load id(s) do not carry a RAW ID (load-<I>-<ID> at their own bus); …
$ mambo-power convert case14.raw case14-bundle --strict; echo $?
RAW_NO_COSTS: RAW carries no cost data; all 5 generators imported with cost=None
1
$ cat request.json | mambo-power run - | jq .status
"ok"
```

A failed job is still a well-formed `SolveResult` on stdout — `status: "failed"` with the
structured error the [jobs API](jobs.md#structurederror) documents — and exit status 1; the
command line never shows a traceback for anything the package itself reports.
