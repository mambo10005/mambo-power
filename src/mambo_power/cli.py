"""The ``mambo-power`` command line (ADR-027): the ``jobs`` surface and the formats from a shell.

Five subcommands, each a thin wrapper over a function this package already exposes, so the
command line adds no behaviour of its own:

* ``kinds`` — every registered analysis (:data:`mambo_power.jobs.KINDS`) with its option and
  result models; ``--json`` for a machine-readable list.
* ``cases`` — the bundled cases (:func:`mambo_power.cases.available`); ``solve`` and
  ``convert`` take any of them by name, with or without the ``.m`` suffix.
* ``run REQUEST`` — a :class:`~mambo_power.jobs.SolveRequest` JSON file (``-`` for stdin) through
  :func:`mambo_power.jobs.run_json`; the :class:`~mambo_power.jobs.SolveResult` JSON goes to
  ``--output`` or stdout. Exit status 0 when the result's ``status`` is ``"ok"``, 1 otherwise —
  a failed solve is still a well-formed result, never a traceback.
* ``solve KIND SOURCE`` — the same without writing the request by hand: ``SOURCE`` is a bundled
  case name or a network file in any readable format, ``--options`` a JSON object for the
  kind's options model.
* ``convert SOURCE TARGET`` — read a network in one format, write it in another. Formats are
  inferred from the path (``.m`` MATPOWER, ``.raw`` PSS/E, ``.json`` native, a directory the
  CSV bundle) or named with ``--from`` / ``--to`` (``pandapower`` for pandapower JSON, which
  shares the extension). Every import or export report issue is printed to stderr, one per
  line, so a lossy conversion is never silent; ``--strict`` makes any issue a failure.

Everything prints JSON or plain lines, nothing is interactive, and the only exit statuses are
0 (done), 1 (the job failed or the conversion had issues under ``--strict``) and 2 (bad usage,
argparse's own). ``python -m mambo_power`` is the same program.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Callable, Sequence
from pathlib import Path
from typing import Literal, cast

from pydantic import ValidationError

import mambo_power
from mambo_power import cases, jobs
from mambo_power.io import csv_bundle, matpower, native, psse_raw
from mambo_power.io.report import ExportReport, ImportReport
from mambo_power.model import Network, NetworkValidationError

__all__ = ["FORMATS", "main"]

_Handler = Callable[[argparse.Namespace], int]

Format = Literal["matpower", "raw", "json", "pandapower", "csv"]
FORMATS: tuple[str, ...] = ("matpower", "raw", "json", "pandapower", "csv")
"""The formats ``convert`` reads and writes (MATPOWER is read-only)."""

_EXTENSIONS: dict[str, Format] = {".m": "matpower", ".raw": "raw", ".json": "json"}


def main(argv: Sequence[str] | None = None) -> int:
    """Run the command line with *argv* (``sys.argv[1:]`` when ``None``); the exit status."""
    parser = _parser()
    args = parser.parse_args(argv)
    handler = cast("_Handler", args.handler)
    try:
        return handler(args)
    except _CliError as exc:
        print(f"mambo-power: {exc}", file=sys.stderr)
        return 1


class _CliError(Exception):
    """A failure to report on stderr with exit status 1, never a traceback."""


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="mambo-power",
        description="Power system analysis and electricity market modelling from the shell.",
    )
    parser.add_argument("--version", action="version", version=mambo_power.__version__)
    sub = parser.add_subparsers(dest="command", required=True)

    kinds = sub.add_parser("kinds", help="list the registered analyses")
    kinds.add_argument("--json", action="store_true", help="one JSON object instead of lines")
    kinds.set_defaults(handler=_kinds)

    bundled = sub.add_parser("cases", help="list the bundled cases")
    bundled.set_defaults(handler=_cases)

    run = sub.add_parser("run", help="run a SolveRequest JSON file")
    run.add_argument("request", help="path of the request JSON, or - for stdin")
    _output_arguments(run)
    run.set_defaults(handler=_run)

    solve = sub.add_parser("solve", help="run one analysis on a case or network file")
    solve.add_argument("kind", help="a registered kind, e.g. opf.dc (see: kinds)")
    solve.add_argument("source", help="a bundled case name or a network file")
    solve.add_argument("--from", dest="source_format", choices=FORMATS, help="source format")
    solve.add_argument("--options", default=None, help="JSON object for the kind's options")
    solve.add_argument("--job-id", default=None, help="echoed in the result")
    _output_arguments(solve)
    solve.set_defaults(handler=_solve)

    convert = sub.add_parser("convert", help="read a network in one format, write another")
    convert.add_argument("source", help="a bundled case name or a network file / CSV directory")
    convert.add_argument("target", help="output file / CSV directory")
    convert.add_argument("--from", dest="source_format", choices=FORMATS, help="source format")
    convert.add_argument("--to", dest="target_format", choices=FORMATS, help="target format")
    convert.add_argument(
        "--strict", action="store_true", help="fail (exit 1) when the conversion reports any issue"
    )
    convert.set_defaults(handler=_convert)
    return parser


def _output_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("-o", "--output", default=None, help="write the result JSON here")
    parser.add_argument("--indent", type=int, default=None, help="pretty-print with this indent")


# -- commands ----------------------------------------------------------------------------------


def _kinds(args: argparse.Namespace) -> int:
    rows = {
        name: {
            "options": spec.options_model.__name__ if spec.options_model else None,
            "result": spec.result_model.__name__,
        }
        for name, spec in sorted(jobs.KINDS.items())
    }
    if args.json:
        print(json.dumps(rows, indent=2))
    else:
        width = max(len(name) for name in rows)
        for name, row in rows.items():
            print(f"{name:{width}s}  {row['options'] or '-':26s} {row['result']}")
    return 0


def _cases(args: argparse.Namespace) -> int:
    del args
    for name in cases.available():
        print(name)
    return 0


def _run(args: argparse.Namespace) -> int:
    text = sys.stdin.read() if args.request == "-" else _read_text(args.request)
    return _emit(jobs.run_json(text), args)


def _solve(args: argparse.Namespace) -> int:
    net = _read_network(args.source, args.source_format)
    options: dict[str, object] | None = None
    if args.options is not None:
        try:
            parsed = json.loads(args.options)
        except json.JSONDecodeError as exc:
            raise _CliError(f"--options is not valid JSON: {exc}") from None
        if not isinstance(parsed, dict):
            raise _CliError("--options must be a JSON object")
        options = parsed
    try:
        request = (
            jobs.SolveRequest(kind=args.kind, network=net, job_id=args.job_id)
            if options is None
            else jobs.SolveRequest(kind=args.kind, network=net, options=options, job_id=args.job_id)
        )
    except ValidationError as exc:
        raise _CliError(f"bad request: {exc}") from None
    return _emit(jobs.run(request).model_dump_json(), args)


def _convert(args: argparse.Namespace) -> int:
    target_format = args.target_format or _infer_format(args.target, "--to")
    if target_format == "matpower":
        raise _CliError("MATPOWER .m is read-only here: no writer exists")
    net, import_report = _read_network_with_report(args.source, args.source_format)
    issues = list(import_report.warnings) + list(import_report.errors)
    export_report = _write_network(net, args.target, target_format)
    if export_report is not None:
        issues.extend(export_report.warnings)
        issues.extend(export_report.errors)
    for issue in issues:
        print(str(issue), file=sys.stderr)
    return 1 if (issues and args.strict) else 0


# -- helpers -----------------------------------------------------------------------------------


def _emit(result_json: str, args: argparse.Namespace) -> int:
    text = result_json
    if args.indent is not None:
        text = json.dumps(json.loads(result_json), indent=args.indent)
    if args.output:
        Path(args.output).write_text(text + "\n", encoding="utf-8")
    else:
        print(text)
    return 0 if json.loads(result_json).get("status") == "ok" else 1


def _read_text(path: str) -> str:
    try:
        return Path(path).read_text(encoding="utf-8")
    except OSError as exc:
        raise _CliError(f"cannot read {path}: {exc.strerror}") from None


def _infer_format(path: str, flag: str) -> Format:
    p = Path(path)
    if p.is_dir() or (p.suffix == "" and not p.exists()):
        return "csv"
    fmt = _EXTENSIONS.get(p.suffix.lower())
    if fmt is None:
        raise _CliError(f"cannot infer the format of {path}; name it with {flag}")
    return fmt


def _read_network(source: str, source_format: str | None) -> Network:
    return _read_network_with_report(source, source_format)[0]


def _bundled(source: str) -> str | None:
    """The bundled case name *source* names (``case14``, ``case14.m``, ``derived/case14_rated``,
    ``case14_v33.raw``), or ``None`` when it names none."""
    names = cases.available()
    if source in names:
        return source
    return f"{source}.m" if f"{source}.m" in names else None


def _read_network_with_report(
    source: str, source_format: str | None
) -> tuple[Network, ImportReport]:
    bundled = _bundled(source) if source_format is None else None
    if bundled is not None:
        if bundled.endswith(".raw"):
            return psse_raw.load_with_report(cases.path(bundled))
        return matpower.load_with_report(cases.path(bundled))
    fmt = cast("Format", source_format) if source_format else _infer_format(source, "--from")
    try:
        if fmt == "matpower":
            return matpower.load_with_report(source)
        if fmt == "raw":
            return psse_raw.load_with_report(source)
        if fmt == "json":
            return native.load(source), ImportReport()
        if fmt == "pandapower":
            from mambo_power.io import pandapower_json

            return pandapower_json.load_with_report(source)
        return csv_bundle.load_with_report(source)
    except FileNotFoundError as exc:
        raise _CliError(f"cannot read {source}: {exc.strerror}") from None
    except NetworkValidationError as exc:
        raise _CliError(f"{source} is not a valid network: {exc}") from None
    except ImportError as exc:
        raise _CliError(f"the {fmt} format needs an optional dependency: {exc}") from None
    except (ValueError, OSError) as exc:
        raise _CliError(f"cannot read {source} as {fmt}: {exc}") from None


def _write_network(net: Network, target: str, fmt: Format) -> ExportReport | None:
    try:
        if fmt == "raw":
            return psse_raw.dump_with_report(net, target)
        if fmt == "json":
            native.save(net, target)
            return None
        if fmt == "pandapower":
            from mambo_power.io import pandapower_json

            text, report = pandapower_json.dumps_with_report(net)
            Path(target).write_text(text, encoding="utf-8")
            return report
        if fmt == "csv":
            csv_bundle.dump(net, target)
            return None
    except ImportError as exc:
        raise _CliError(f"the {fmt} format needs an optional dependency: {exc}") from None
    except (ValueError, OSError) as exc:
        raise _CliError(f"cannot write {target} as {fmt}: {exc}") from None
    raise _CliError(f"no writer for {fmt}")


if __name__ == "__main__":  # pragma: no cover - ``python -m mambo_power.cli``
    sys.exit(main())
