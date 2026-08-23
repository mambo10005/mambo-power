"""mkdocs hook: render the reST cross-reference roles used in docstrings as autoref links.

The package's docstrings are written in Sphinx/reST style, so they cite other symbols as
``:class:`mambo_power.model.Network``` or ``:func:`~mambo_power.pf.solve_dc```. Python-Markdown
turns the backticked part into ``<code>`` and leaves the ``:class:`` prefix as literal text.
This hook runs after Markdown conversion and rewrites every ``:role:<code>target</code>`` into
an ``<autoref>`` element that mkdocs-autorefs resolves to the symbol's API page when it exists
(``optional`` keeps unresolved targets from failing ``--strict``). A leading ``~`` shortens the
visible text to the last path component, as Sphinx does.
"""

from __future__ import annotations

import re

_ROLE = re.compile(r":(?:class|func|mod|meth|attr|exc|data|obj):<code>(~?)([A-Za-z_][\w.]*)</code>")


def _replace(match: re.Match[str]) -> str:
    tilde, target = match.groups()
    label = target.rsplit(".", 1)[-1] if tilde else target
    return f'<autoref identifier="{target}" optional><code>{label}</code></autoref>'


def on_page_content(html: str, **kwargs: object) -> str:
    """Rewrite reST roles in the rendered HTML of every page."""
    return _ROLE.sub(_replace, html)
