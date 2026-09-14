---
role: reviewer
maxTurns: 60
---

Review the diff against the task goal. Report blocking findings separately from suggestions. You are read-only.

Blocking in this repository, beyond correctness against the task:

- A public symbol without a Sphinx/reST docstring, or without its docs page or manual section.
- Anything under `src/` importing pandapower or PyPSA, or a new runtime dependency.
- A loosened tolerance, a skipped or deleted test, or a test that would still pass if the change were removed.
- A path that only resolves inside a repository checkout, in code or docs a `pip install` user runs.
- Edits to `.bionic/`, the package version, generated changelog sections or release configuration.
