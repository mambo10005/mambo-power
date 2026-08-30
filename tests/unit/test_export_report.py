"""AC-7 (report half): ``ExportReport`` mirrors ``ImportReport`` — issue shape, ``warnings``,
``errors``, ``codes``, ``as_strings``, ``raise_on_error``; empty means lossless (D1)."""

import pytest

from mambo_power.io.report import ConversionIssue, ExportReport, ImportReport, ReportError
from mambo_power.model import ImportIssue


def _issue(code: str = "BASE_KV_REPLACED", msg: str = "x") -> ImportIssue:
    return ImportIssue(code=code, message=msg, element_ids=["e1"])  # type: ignore[arg-type]


def test_conversion_issue_is_the_import_issue_shape() -> None:
    assert ConversionIssue is ImportIssue


@pytest.mark.parametrize("cls", [ExportReport, ImportReport])
def test_empty_report_is_lossless(cls: type[ExportReport] | type[ImportReport]) -> None:
    r = cls()
    assert r.warnings == [] and r.errors == [] and r.codes == set() and r.as_strings() == []
    assert not r.has_errors
    r.raise_on_error()  # no-op


@pytest.mark.parametrize("cls", [ExportReport, ImportReport])
def test_codes_and_strings_cover_warnings_and_errors(
    cls: type[ExportReport] | type[ImportReport],
) -> None:
    r = cls(
        warnings=[_issue("BASE_KV_REPLACED", "w")], errors=[_issue("GENCOST_REACTIVE_IGNORED", "e")]
    )
    assert r.codes == {"BASE_KV_REPLACED", "GENCOST_REACTIVE_IGNORED"}
    assert r.as_strings() == ["BASE_KV_REPLACED: w", "GENCOST_REACTIVE_IGNORED: e"]
    assert r.has_errors


@pytest.mark.parametrize("cls", [ExportReport, ImportReport])
def test_raise_on_error_raises_only_for_errors(
    cls: type[ExportReport] | type[ImportReport],
) -> None:
    cls(warnings=[_issue()]).raise_on_error()
    r = cls(errors=[_issue("GENCOST_REACTIVE_IGNORED", "dropped")])
    with pytest.raises(ReportError, match="GENCOST_REACTIVE_IGNORED: dropped") as info:
        r.raise_on_error()
    assert info.value.report is r


def test_import_report_legacy_shape_unchanged() -> None:
    r = ImportReport(warnings=[_issue()])
    assert r.as_strings() == ["BASE_KV_REPLACED: x"] and r.codes == {"BASE_KV_REPLACED"}
