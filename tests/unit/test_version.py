import mambo_power


def test_version_is_nonempty_string() -> None:
    assert isinstance(mambo_power.__version__, str)
    assert mambo_power.__version__
