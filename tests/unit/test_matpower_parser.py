"""MATPOWER .m importer: tiny inline cases, every error code, format tolerance."""

import textwrap
from pathlib import Path

import pytest

from mambo_power.io import matpower
from mambo_power.io.matpower import MatpowerImportError
from mambo_power.model import NetworkValidationError, PiecewiseCost, PolynomialCost

TINY = textwrap.dedent(
    """\
    function mpc = tiny
    % two buses, one generator, one line, one polynomial cost
    mpc.version = '2';
    mpc.baseMVA = 100;
    mpc.bus = [
    \t1\t3\t0\t0\t0\t0\t1\t1.0\t0\t110\t1\t1.1\t0.9;
    \t2\t1\t50\t10\t0\t5\t2\t0.98\t-3.5\t110\t2\t1.1\t0.9;
    ];
    mpc.gen = [
    \t1\t60\t5\t100\t-100\t1.02\t100\t1\t200\t0;
    ];
    mpc.branch = [
    \t1\t2\t0.01\t0.1\t0.02\t150\t0\t0\t0\t0\t1;
    ];
    mpc.gencost = [
    \t2\t100\t50\t3\t0.01\t20\t5;
    ];
    """
)

BUS_2 = "mpc.bus = [\n1 3 0 0 0 0 1 1 0 110 1 1.1 0.9;\n2 1 50 10 0 0 1 1 0 110 1 1.1 0.9;\n];"
GEN_1 = "mpc.gen = [\n1 60 5 100 -100 1.02 100 1 200 0;\n];"
BRANCH_1 = "mpc.branch = [\n1 2 0.01 0.1 0.02 150 0 0 0 0 1;\n];"


def _case(
    *,
    bus: str = BUS_2,
    gen: str = GEN_1,
    branch: str = BRANCH_1,
    gencost: str | None = None,
    base_mva: str | None = "mpc.baseMVA = 100;",
) -> str:
    """Assemble a case text from overridable sections.

    Line numbers with the defaults: 1 function, 2 version, 3 baseMVA, 4 ``mpc.bus = [``,
    5-6 bus rows, 7 ``];``, 8 ``mpc.gen = [``, 9 gen row, 10 ``];``, 11 ``mpc.branch = [``,
    12 branch row, 13 ``];``, 14 ``mpc.gencost = [``, 15 first gencost row.
    """
    parts = ["function mpc = t", "mpc.version = '2';"]
    if base_mva:
        parts.append(base_mva)
    parts += [bus, gen, branch]
    if gencost:
        parts.append(gencost)
    return "\n".join(parts) + "\n"


# --- happy path --------------------------------------------------------------------------


def test_minimal_case_parses() -> None:
    net = matpower.loads(TINY)
    assert net.base_mva == 100.0
    assert [b.id for b in net.buses] == ["bus-1", "bus-2"]
    assert [b.type for b in net.buses] == ["slack", "pq"]
    assert all(b.in_service for b in net.buses)
    b2 = net.buses[1]
    assert (b2.vm_pu, b2.va_deg, b2.base_kv) == (0.98, -3.5, 110.0)
    assert (b2.v_max_pu, b2.v_min_pu, b2.area, b2.zone) == (1.1, 0.9, "2", "2")
    assert [z.id for z in net.zones] == ["1", "2"]
    assert [(ld.id, ld.bus, ld.p_mw, ld.q_mvar) for ld in net.loads] == [
        ("load-2", "bus-2", 50.0, 10.0)
    ]
    assert [(s.id, s.bus, s.g_mw, s.b_mvar) for s in net.shunts] == [("shunt-2", "bus-2", 0.0, 5.0)]
    (g,) = net.generators
    assert (g.id, g.bus, g.p_mw, g.q_mvar) == ("gen-1", "bus-1", 60.0, 5.0)
    assert (g.q_max_mvar, g.q_min_mvar, g.v_set_pu) == (100.0, -100.0, 1.02)
    assert (g.p_max_mw, g.p_min_mw, g.in_service) == (200.0, 0.0, True)
    (br,) = net.branches
    assert (br.id, br.from_bus, br.to_bus) == ("branch-1", "bus-1", "bus-2")
    assert (br.r, br.x, br.b, br.rating_mva) == (0.01, 0.1, 0.02, 150.0)
    assert (br.tap_ratio, br.shift_deg, br.in_service) == (None, None, True)
    assert net.storage == []


def test_load_from_path_and_loads_agree(tmp_path: Path) -> None:
    path = tmp_path / "tiny.m"
    path.write_text(TINY, encoding="utf-8")
    assert matpower.load(path) == matpower.loads(TINY)
    assert matpower.load(str(path)) == matpower.loads(TINY)


def test_load_with_warnings_returns_network_and_list(tmp_path: Path) -> None:
    path = tmp_path / "tiny.m"
    path.write_text(TINY, encoding="utf-8")
    net, warnings = matpower.load_with_warnings(path)
    assert net == matpower.loads(TINY)
    assert warnings == []
    assert matpower.loads_with_warnings(TINY) == (net, [])


# --- gencost -------------------------------------------------------------------------------


def test_gencost_polynomial() -> None:
    (g,) = matpower.loads(TINY).generators
    assert g.cost == PolynomialCost(coefficients=[0.01, 20.0, 5.0], startup=100.0, shutdown=50.0)


def test_gencost_piecewise() -> None:
    text = _case(gencost="mpc.gencost = [\n1 10 0 3 0 0 50 1000 100 2500;\n];")
    (g,) = matpower.loads(text).generators
    assert g.cost == PiecewiseCost(
        points=[(0.0, 0.0), (50.0, 1000.0), (100.0, 2500.0)], startup=10.0, shutdown=0.0
    )


def test_gencost_absent_gives_none() -> None:
    (g,) = matpower.loads(_case()).generators
    assert g.cost is None


def test_gencost_reactive_rows_use_first_half_and_warn() -> None:
    text = _case(gencost="mpc.gencost = [\n2 0 0 2 20 5;\n2 0 0 2 1 0;\n];")
    net, warnings = matpower.loads_with_warnings(text)
    (g,) = net.generators
    assert g.cost == PolynomialCost(coefficients=[20.0, 5.0])
    assert len(warnings) == 1 and "gencost" in warnings[0]


def test_gencost_ncost_governs_not_row_width() -> None:
    # rows padded with zeros to a common width: NCOST governs, not the row width
    text = _case(
        gen="mpc.gen = [\n1 60 5 100 -100 1.02 100 1 200 0;\n1 0 0 10 -10 1.02 100 1 50 0;\n];",
        gencost="mpc.gencost = [\n2 0 0 3 0.01 20 5;\n2 0 0 2 30 1 0;\n];",
    )
    g1, g2 = matpower.loads(text).generators
    assert g1.cost == PolynomialCost(coefficients=[0.01, 20.0, 5.0])
    assert g2.cost == PolynomialCost(coefficients=[30.0, 1.0])


def test_gencost_row_count_mismatch_is_bad_row() -> None:
    text = _case(gencost="mpc.gencost = [\n2 0 0 2 20 5;\n2 0 0 2 1 0;\n2 0 0 2 1 0;\n];")
    with pytest.raises(MatpowerImportError) as info:
        matpower.loads(text)
    assert info.value.code == "BAD_ROW"


def test_gencost_row_shorter_than_ncost_is_bad_row() -> None:
    text = _case(gencost="mpc.gencost = [\n2 0 0 3 20 5;\n];")
    with pytest.raises(MatpowerImportError) as info:
        matpower.loads(text)
    assert info.value.code == "BAD_ROW"
    assert info.value.line == 15


def test_gencost_bad_model_is_bad_number() -> None:
    text = _case(gencost="mpc.gencost = [\n3 0 0 2 20 5;\n];")
    with pytest.raises(MatpowerImportError) as info:
        matpower.loads(text)
    assert info.value.code == "BAD_NUMBER"
    assert info.value.line == 15


# --- column semantics ---------------------------------------------------------------------


def test_bus_type_4_is_out_of_service_pq() -> None:
    text = _case(
        bus=(
            "mpc.bus = [\n1 3 0 0 0 0 1 1 0 110 1 1.1 0.9;\n"
            "2 1 50 10 0 0 1 1 0 110 1 1.1 0.9;\n3 4 0 0 0 0 1 1 0 110 1 1.1 0.9;\n];"
        )
    )
    net = matpower.loads(text)
    assert net.buses[2].type == "pq"
    assert net.buses[2].in_service is False
    assert net.buses[2].id == "bus-3"


def test_bus_type_other_is_bad_number() -> None:
    text = _case(
        bus="mpc.bus = [\n1 5 0 0 0 0 1 1 0 110 1 1.1 0.9;\n2 1 0 0 0 0 1 1 0 110 1 1.1 0.9;\n];"
    )
    with pytest.raises(MatpowerImportError) as info:
        matpower.loads(text)
    assert info.value.code == "BAD_NUMBER"
    assert info.value.line == 5


def test_base_kv_nonpositive_becomes_one_with_warning() -> None:
    text = _case(
        bus="mpc.bus = [\n1 3 0 0 0 0 1 1 0 0 1 1.1 0.9;\n2 1 0 0 0 0 1 1 0 110 1 1.1 0.9;\n];"
    )
    net, warnings = matpower.loads_with_warnings(text)
    assert net.buses[0].base_kv == 1.0
    assert net.buses[1].base_kv == 110.0
    assert len(warnings) == 1 and "bus-1" in warnings[0]


def test_zero_load_and_shunt_rows_are_not_emitted() -> None:
    net = matpower.loads(_case())
    assert [ld.id for ld in net.loads] == ["load-2"]
    assert net.shunts == []


def test_load_emitted_when_only_q_nonzero() -> None:
    text = _case(
        bus="mpc.bus = [\n1 3 0 0 0 0 1 1 0 110 1 1.1 0.9;\n2 1 0 -4 0 0 1 1 0 110 1 1.1 0.9;\n];"
    )
    net = matpower.loads(text)
    assert [(ld.p_mw, ld.q_mvar) for ld in net.loads] == [(0.0, -4.0)]


def test_shunt_emitted_when_only_g_nonzero() -> None:
    text = _case(
        bus="mpc.bus = [\n1 3 0 0 0 0 1 1 0 110 1 1.1 0.9;\n2 1 0 0 2 0 1 1 0 110 1 1.1 0.9;\n];"
    )
    net = matpower.loads(text)
    assert [(s.g_mw, s.b_mvar) for s in net.shunts] == [(2.0, 0.0)]


def test_rate_a_zero_is_none_and_positive_kept() -> None:
    text = _case(
        branch=(
            "mpc.branch = [\n1 2 0.01 0.1 0.02 0 0 0 0 0 1;\n1 2 0.01 0.1 0.02 90 0 0 0 0 1;\n];"
        )
    )
    b1, b2 = matpower.loads(text).branches
    assert b1.rating_mva is None
    assert b2.rating_mva == 90.0


def test_tap_and_shift_zero_are_none_nonzero_kept() -> None:
    text = _case(
        branch=(
            "mpc.branch = [\n1 2 0.01 0.1 0.02 0 0 0 0 0 1;\n"
            "1 2 0.01 0.1 0.02 0 0 0 1.025 -2.5 1;\n];"
        )
    )
    b1, b2 = matpower.loads(text).branches
    assert (b1.tap_ratio, b1.shift_deg) == (None, None)
    assert (b2.tap_ratio, b2.shift_deg) == (1.025, -2.5)


def test_statuses_map_to_in_service() -> None:
    text = _case(
        gen="mpc.gen = [\n1 60 5 100 -100 1.02 100 1 200 0;\n1 0 0 10 -10 1.0 100 0 50 0;\n];",
        branch=(
            "mpc.branch = [\n1 2 0.01 0.1 0.02 0 0 0 0 0 1;\n1 2 0.01 0.1 0.02 0 0 0 0 0 0;\n];"
        ),
    )
    net = matpower.loads(text)
    assert [g.in_service for g in net.generators] == [True, False]
    assert [b.in_service for b in net.branches] == [True, False]


def test_extra_trailing_columns_are_ignored() -> None:
    text = _case(
        gen="mpc.gen = [\n1 60 5 100 -100 1.02 100 1 200 0 0 0 0 0 0 0 0 0 0 0 0;\n];",
        branch="mpc.branch = [\n1 2 0.01 0.1 0.02 0 0 0 0 0 1 -360 360;\n];",
    )
    net = matpower.loads(text)
    assert len(net.generators) == 1 and len(net.branches) == 1


def test_slack_out_of_service_raises_network_validation() -> None:
    text = _case(
        bus="mpc.bus = [\n1 4 0 0 0 0 1 1 0 110 1 1.1 0.9;\n2 1 0 0 0 0 1 1 0 110 1 1.1 0.9;\n];"
    )
    with pytest.raises(NetworkValidationError) as info:
        matpower.loads(text)
    assert "NO_SLACK" in info.value.codes


def test_unknown_fields_and_bus_name_are_ignored() -> None:
    extra = (
        "mpc.bus_name = {\n\t'Bus 1 % not a comment';\n\t'Bus 2';\n};\n"
        "mpc.areas = [\n1 1;\n];\nmpc.foo = 42;\n"
    )
    assert matpower.loads(TINY + extra) == matpower.loads(TINY)


# --- format tolerance ----------------------------------------------------------------------


def test_crlf_comments_tabs_blank_lines_and_scientific_notation() -> None:
    text = (
        "function mpc = t\r\n\r\nmpc.version = '2';\r\nmpc.baseMVA = 1e2; % base\r\n"
        "mpc.bus = [ % header comment\r\n\t1\t3\t0\t0\t0\t0\t1\t1\t0\t1.1e2\t1\t1.1\t0.9;\r\n"
        "\r\n  2 1 5.0E1 1e1 0 0 1 1 0 110 1 1.1 0.9 ; % trailing\r\n];\r\n"
        "mpc.gen = [\r\n1 60 5 100 -100 1.02 100 1 200 0;\r\n];\r\n"
        "mpc.branch = [\r\n1 2 1e-2 0.1 0.02 0 0 0 0 0 1;\r\n];\r\n"
    )
    net = matpower.loads(text)
    assert net.base_mva == 100.0
    assert net.buses[0].base_kv == 110.0
    assert net.loads[0].p_mw == 50.0 and net.loads[0].q_mvar == 10.0
    assert net.branches[0].r == 0.01


def test_utf8_bom_does_not_hide_the_first_assignment(tmp_path: Path) -> None:
    # A BOM-prefixed file whose first line is an mpc.* assignment must still parse: U+FEFF is
    # not whitespace, so the anchored `^\\s*mpc\\.` regex would otherwise skip that line.
    text = "mpc.baseMVA = 100;\n" + BUS_2 + "\n" + GEN_1 + "\n" + BRANCH_1 + "\n"
    path = tmp_path / "bom.m"
    path.write_bytes(b"\xef\xbb\xbf" + text.encode("utf-8"))
    assert matpower.load(path) == matpower.loads(text)
    assert matpower.loads("\ufeff" + text) == matpower.loads(text)


def test_rows_without_semicolons_and_multiple_rows_per_line() -> None:
    text = _case(
        bus="mpc.bus = [\n1 3 0 0 0 0 1 1 0 110 1 1.1 0.9\n2 1 50 10 0 0 1 1 0 110 1 1.1 0.9\n];",
        branch="mpc.branch = [1 2 0.01 0.1 0.02 0 0 0 0 0 1; 2 1 0.02 0.2 0 0 0 0 0 0 1];",
    )
    net = matpower.loads(text)
    assert len(net.buses) == 2
    assert [b.id for b in net.branches] == ["branch-1", "branch-2"]


def test_base_mva_without_semicolon_and_matrix_closer_on_row_line() -> None:
    text = _case(
        base_mva="mpc.baseMVA = 50",
        gen="mpc.gen = [\n1 60 5 100 -100 1.02 100 1 200 0];",
    )
    net = matpower.loads(text)
    assert net.base_mva == 50.0
    assert len(net.generators) == 1


# --- error codes -----------------------------------------------------------------------------


def test_missing_base_mva() -> None:
    with pytest.raises(MatpowerImportError) as info:
        matpower.loads(_case(base_mva=None))
    assert info.value.code == "MISSING_BASE_MVA"


@pytest.mark.parametrize("section", ["bus", "gen", "branch"])
def test_missing_section(section: str) -> None:
    text = _case(**{section: ""})  # type: ignore[arg-type]
    with pytest.raises(MatpowerImportError) as info:
        matpower.loads(text)
    assert info.value.code == "MISSING_SECTION"
    assert section in str(info.value)


def test_unterminated_matrix_reports_opener_line() -> None:
    text = "mpc.baseMVA = 100;\nmpc.bus = [\n1 3 0 0 0 0 1 1 0 110 1 1.1 0.9;\n"
    with pytest.raises(MatpowerImportError) as info:
        matpower.loads(text)
    assert info.value.code == "UNTERMINATED_MATRIX"
    assert info.value.line == 2


def test_bad_number_reports_line() -> None:
    text = _case(
        bus="mpc.bus = [\n1 3 0 0 0 0 1 1 0 110 1 1.1 0.9;\n2 1 abc 10 0 0 1 1 0 110 1 1.1 0.9;\n];"
    )
    with pytest.raises(MatpowerImportError) as info:
        matpower.loads(text)
    assert info.value.code == "BAD_NUMBER"
    assert info.value.line == 6
    assert "abc" in str(info.value)


def test_bad_number_in_base_mva() -> None:
    with pytest.raises(MatpowerImportError) as info:
        matpower.loads(_case(base_mva="mpc.baseMVA = hundred;"))
    assert info.value.code == "BAD_NUMBER"
    assert info.value.line == 3


def test_non_finite_is_bad_number() -> None:
    with pytest.raises(MatpowerImportError) as info:
        matpower.loads(_case(base_mva="mpc.baseMVA = Inf;"))
    assert info.value.code == "BAD_NUMBER"


def test_bad_row_too_few_columns() -> None:
    text = _case(branch="mpc.branch = [\n1 2 0.01 0.1 0.02;\n];")
    with pytest.raises(MatpowerImportError) as info:
        matpower.loads(text)
    assert info.value.code == "BAD_ROW"
    assert info.value.line == 12


def test_bad_row_ragged_matrix() -> None:
    text = _case(
        branch=(
            "mpc.branch = [\n1 2 0.01 0.1 0.02 0 0 0 0 0 1 -360 360;\n"
            "1 2 0.01 0.1 0.02 0 0 0 0 0 1;\n];"
        )
    )
    with pytest.raises(MatpowerImportError) as info:
        matpower.loads(text)
    assert info.value.code == "BAD_ROW"
    assert info.value.line == 13


def test_non_integer_bus_number_is_bad_number() -> None:
    text = _case(
        bus="mpc.bus = [\n1.5 3 0 0 0 0 1 1 0 110 1 1.1 0.9;\n2 1 0 0 0 0 1 1 0 110 1 1.1 0.9;\n];"
    )
    with pytest.raises(MatpowerImportError) as info:
        matpower.loads(text)
    assert info.value.code == "BAD_NUMBER"


def test_error_str_carries_code_and_line() -> None:
    err = MatpowerImportError("BAD_ROW", "mpc.gen row has 3 columns, expected >= 10", line=7)
    assert err.code == "BAD_ROW"
    assert err.line == 7
    assert str(err) == "BAD_ROW: mpc.gen row has 3 columns, expected >= 10 (line 7)"
