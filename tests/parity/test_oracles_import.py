"""AC-3: the dev-only oracles import inside the test session on every CI OS."""


def test_pandapower_imports() -> None:
    import pandapower

    assert isinstance(pandapower.__version__, str)
    assert pandapower.__version__


def test_pypsa_imports() -> None:
    import pypsa

    assert isinstance(pypsa.__version__, str)
    assert pypsa.__version__
