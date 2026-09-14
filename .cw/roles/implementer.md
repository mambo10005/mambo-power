---
role: implementer
maxTurns: 60
---

Implement the task. Stay inside the write scope. Never write outside the worktree, your own memory directory included: a lesson for later belongs in the final message. Run the tests you can run. Stop when the success criteria are met.

Rules for this repository:

- The repository contract (`WORKFLOW.md`) is at the top of this prompt; do not look for it on disk. Read only the files and ADRs the task names.
- Write the test first, watch it fail, then implement. The final message says which test would fail if the change were removed.
- Run the test files you touched, `uv run ruff check .`, `uv run ruff format --check .` and `uv run mypy`. Do not run the full `uv run pytest` more than once; it takes 15–20 minutes and the gates run it after you.
- Move files with `git mv` so history follows them; a moved data file keeps its bytes exactly.
- Do not touch files outside your lease even to fix something obviously wrong there. Report it instead.
- A public symbol you add gets its docstring in the same edit.
