"""The ``mambo-power`` command line (:mod:`mambo_power.cli`, ADR-027).

Every subcommand is driven through :func:`mambo_power.cli.main` with an argv list, the way the
console script and ``python -m mambo_power`` call it, and checked on its exit status and on what
it printed: JSON that parses back into the result model, lines that name what they should, and
errors on stderr with status 1 rather than a traceback.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from mambo_power import cases, jobs
from mambo_power.cli import main
from mambo_power.io import matpower, native, psse_raw
from mambo_power.results import DcPowerFlowResult, ScopfDcResult


def test_kinds_lists_every_registered_kind(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["kinds"]) == 0
    lines = capsys.readouterr().out.strip().splitlines()
    assert [line.split()[0] for line in lines] == sorted(jobs.KINDS)
    assert any("pf.dc" in line and "DcPowerFlowResult" in line for line in lines)

    assert main(["kinds", "--json"]) == 0
    rows = json.loads(capsys.readouterr().out)
    assert rows["opf.scopf"] == {"options": "ScopfOptions", "result": "ScopfDcResult"}
    assert rows["pf.dc"]["options"] is None


def test_cases_lists_the_bundled_cases(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["cases"]) == 0
    assert capsys.readouterr().out.split() == cases.available()


def test_solve_runs_a_kind_on_a_bundled_case(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["solve", "pf.dc", "case14"]) == 0
    reply = jobs.SolveResult.model_validate_json(capsys.readouterr().out)
    assert reply.status == "ok" and isinstance(reply.result, DcPowerFlowResult)
    assert reply.result.provenance.kind == "pf.dc"


def test_solve_takes_options_a_job_id_and_an_output_file(tmp_path: Path) -> None:
    out = tmp_path / "scopf.json"
    status = main(
        [
            "solve",
            "opf.scopf",
            "derived/case14_rated",
            "--options",
            '{"corrective": true, "generator_outages": false}',
            "--job-id",
            "night-shift",
            "-o",
            str(out),
            "--indent",
            "2",
        ]
    )
    assert status == 0
    text = out.read_text(encoding="utf-8")
    assert text.startswith("{\n  ")  # pretty-printed
    reply = jobs.SolveResult.model_validate_json(text)
    assert reply.job_id == "night-shift"
    assert isinstance(reply.result, ScopfDcResult)
    assert reply.result.provenance.options["corrective"] is True
    assert reply.result.n1 is not None and reply.result.n1.generator_outages == []


def test_a_failed_job_is_a_result_with_exit_status_1(capsys: pytest.CaptureFixture[str]) -> None:
    # the RAW case has no costs: opf.dc fails validation, as a well-formed SolveResult
    assert main(["solve", "opf.dc", "case14_v33.raw"]) == 1
    reply = jobs.SolveResult.model_validate_json(capsys.readouterr().out)
    assert reply.status == "failed" and reply.error is not None
    assert reply.error.code == "VALIDATION"

    assert main(["solve", "opf.dc", "case14", "--options", '{"bogus": 1}']) == 1
    reply = jobs.SolveResult.model_validate_json(capsys.readouterr().out)
    assert reply.error is not None and reply.error.code == "BAD_OPTIONS"


def test_usage_errors_go_to_stderr_with_exit_status_1(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["solve", "pf.dc", "no-such-file.m"]) == 1
    assert "cannot read no-such-file.m" in capsys.readouterr().err
    assert main(["solve", "pf.dc", "case14", "--options", "not json"]) == 1
    assert "--options is not valid JSON" in capsys.readouterr().err
    assert main(["solve", "pf.dc", "case14", "--options", "[1]"]) == 1
    assert "must be a JSON object" in capsys.readouterr().err
    assert main(["convert", "case14", "out.xyz"]) == 1
    assert "cannot infer the format" in capsys.readouterr().err
    with pytest.raises(SystemExit) as exc:
        main(["solve", "pf.dc", "case14", "--from", "excel"])
    assert exc.value.code == 2


def test_run_takes_a_request_file_or_stdin(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    request = jobs.SolveRequest(kind="pf.dc", network=cases.load("case14"), job_id="r1")
    path = tmp_path / "request.json"
    path.write_text(request.model_dump_json(), encoding="utf-8")
    assert main(["run", str(path)]) == 0
    reply = jobs.SolveResult.model_validate_json(capsys.readouterr().out)
    assert reply.status == "ok" and reply.job_id == "r1"

    import io

    monkeypatch.setattr("sys.stdin", io.StringIO(request.model_dump_json()))
    assert main(["run", "-"]) == 0
    assert jobs.SolveResult.model_validate_json(capsys.readouterr().out).status == "ok"

    path.write_text('{"kind": "pf.telepathy", "network": {}}', encoding="utf-8")
    assert main(["run", str(path)]) == 1
    reply = jobs.SolveResult.model_validate_json(capsys.readouterr().out)
    assert reply.status == "failed"


def test_convert_round_trips_through_raw_json_and_csv(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    raw = tmp_path / "c14.raw"
    assert main(["convert", "case14", str(raw)]) == 0
    err = capsys.readouterr().err
    assert "COST_DROPPED" in err and "RAW_ID_RENUMBERED" in err  # lossy, and said so
    assert main(["convert", "case14", str(raw), "--strict"]) == 1  # the same issues, strict

    as_json = tmp_path / "c14.json"
    assert main(["convert", str(raw), str(as_json)]) == 0
    assert "RAW_NO_COSTS" in capsys.readouterr().err
    net = native.load(as_json)
    assert net == psse_raw.load(raw)

    bundle = tmp_path / "c14_csv"
    assert main(["convert", str(as_json), str(bundle)]) == 0
    assert capsys.readouterr().err == ""  # native JSON and the CSV bundle are lossless
    assert (bundle / "buses.csv").exists()
    assert main(["convert", str(bundle), str(tmp_path / "back.json"), "--strict"]) == 0
    assert native.load(tmp_path / "back.json") == net

    # a bundled RAW case, by name, with --to overriding the extension
    assert main(["convert", "case14_v33.raw", str(tmp_path / "x.txt"), "--to", "json"]) == 0
    assert native.load(tmp_path / "x.txt").buses[0].id == "bus-1"

    # MATPOWER is written too (ADR-032), losslessly for a case the importer produced
    m = tmp_path / "c14.m"
    assert main(["convert", "case14", str(m)]) == 0
    err = capsys.readouterr().err
    assert "BASE_KV_REPLACED" in err and "DROPPED" not in err  # the import's repair, no loss
    assert matpower.load(m) == cases.load("case14")
    assert main(["convert", str(m), str(tmp_path / "again.m"), "--strict"]) == 0  # lossless


def test_python_dash_m_runs_the_same_program() -> None:
    import subprocess
    import sys

    done = subprocess.run(
        [sys.executable, "-m", "mambo_power", "cases"], capture_output=True, text=True, check=False
    )
    assert done.returncode == 0
    assert done.stdout.split() == cases.available()
