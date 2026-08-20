"""Named validation errors for :class:`mambo_power.model.Network`.

Every invariant violation is reported as a :class:`ValidationIssue` with a stable ``code``,
a ``path`` into the network document (``buses[3].base_kv``) and a human-readable message.
:class:`NetworkValidationError` carries *all* issues found in one pass, never just the first.
"""

from collections.abc import Iterable, Sequence
from typing import Literal

from pydantic import BaseModel, ConfigDict

ValidationCode = Literal[
    "NO_SLACK",
    "MULTIPLE_SLACK",
    "DISCONNECTED_BUS",
    "DUPLICATE_ID",
    "DANGLING_REF",
    "BAD_BASE",
    "BAD_RANGE",
]
"""The closed set of network-level validation codes (wave M1 design item 5)."""


class ValidationIssue(BaseModel):
    """One invariant violation: stable code, document path, readable message."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    code: ValidationCode
    path: str
    message: str

    def __str__(self) -> str:
        return f"{self.code} at {self.path}: {self.message}"


class NetworkValidationError(Exception):
    """Raised by ``Network`` when one or more invariants fail.

    Subclasses :class:`Exception` rather than :class:`ValueError` on purpose: pydantic-core
    converts any ``ValueError`` raised inside a validator into its own ``ValidationError``,
    which would hide ``.issues`` behind a generic message. A plain ``Exception`` propagates
    unchanged through ``Network(...)``, ``model_validate`` and ``model_validate_json``.
    """

    issues: list[ValidationIssue]

    def __init__(self, issues: Iterable[ValidationIssue]) -> None:
        self.issues = list(issues)
        super().__init__(self._format(self.issues))

    @property
    def codes(self) -> set[str]:
        """The distinct codes present, for quick membership checks."""
        return {issue.code for issue in self.issues}

    @staticmethod
    def _format(issues: Sequence[ValidationIssue]) -> str:
        noun = "issue" if len(issues) == 1 else "issues"
        lines = [f"Network validation failed with {len(issues)} {noun}:"]
        lines.extend(f"  - {issue}" for issue in issues)
        return "\n".join(lines)

    def __str__(self) -> str:
        return self._format(self.issues)
