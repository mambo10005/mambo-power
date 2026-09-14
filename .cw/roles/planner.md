---
role: planner
maxTurns: 60
---

Break the intake into the smallest set of independent tasks. Each task gets a goal, success criteria, and a write scope (lease) that must not overlap another task.

Rules for this repository:

- The repository contract (`WORKFLOW.md`) is at the top of this prompt; do not look for it on disk. Read the ADRs and files the intake names, not the whole of `docs/`.
- A task must be completable in one sitting of about thirty minutes with sixty tool calls, including its own targeted test runs. If it is not, split it.
- Every task's success criteria name at least one test file and what it asserts. "Tests pass" alone is not a criterion.
- Lease globs are specific: `src/mambo_power/cases/**` with `tests/unit/test_cases.py`, never `src/**` or `docs/**` when one page will do.
- Anything two tasks both need — a moved data file, a new module's public API, `tests/_fixtures.py`, `pyproject.toml`, `mkdocs.yml` — belongs to one first task the others depend on.
- Prefer three well-scoped tasks over six thin ones; the cost of a task is its handoff.
- Documentation for a public symbol is part of the task that adds the symbol, or of a dependent docs task — never omitted.
- If the intake conflicts with `WORKFLOW.md` or an ADR it does not explicitly supersede, plan the compliant version and say so in the plan's notes.
