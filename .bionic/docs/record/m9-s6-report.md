# M9 S6 report — `.github/workflows/publish.yml` (W7/AC-5)

Worktree: `C:\Claude Projects\mambo-power-m9-s6`, branch `wave/09-release-0.1-s6`, base
`d18aaea`. Commit: `a922ce6` — `git show --stat a922ce6`:

```
feat(m9): W7/AC-5 — publish.yml, PyPI trusted publishing on v* tag push
 .github/workflows/publish.yml | 89 +++++++++++++++++++++++++++++++++++++++++++
 1 file changed, 89 insertions(+)
```

Only file touched: `.github/workflows/publish.yml` (new). Nothing else in the worktree was
staged or modified.

## Trigger / permissions logic

```yaml
on:
  push:
    tags:
      - "v*"

permissions:
  contents: read

jobs:
  build:      # checkout, uv setup, version-consistency check, uv build, upload-artifact
  publish:    # needs: build, environment: pypi, permissions: id-token: write, download-artifact,
              # pypa/gh-action-pypi-publish@v1.14.2, no password/api-token input
```

- **Trigger**: `on: push: tags: ['v*']` only. No `on: push: branches:`, no `pull_request:`, no
  `workflow_dispatch:`. I deliberately skipped the optional manual-trigger escape hatch: AC-5's
  own wording ("a workflow-dispatch or push-to-branch event does NOT trigger the publish job")
  reads as a hard requirement, not just an example, so adding `workflow_dispatch` would have put
  the workflow at odds with its own acceptance criterion. Judgment call, stated here per the
  house rule that a call reverting cleanly doesn't need to come to you first — happy to add it
  back if you want the escape hatch and are fine relaxing that reading.
- **Permissions**: top-level `permissions: contents: read` only (least privilege). `id-token:
  write` is scoped to the `publish` job alone — the `build` job never gets it, since only the
  OIDC exchange in the publish step needs it. This is the exact mechanism: GitHub mints a
  short-lived OIDC identity token for the job, `pypa/gh-action-pypi-publish` exchanges it for a
  scoped PyPI upload credential, and **no `password`/`api-token` input is set on the action
  call** — that absence is what puts it in trusted-publishing mode instead of legacy
  token auth.
- **Publish job runs in `environment: pypi`** (`url: https://pypi.org/p/mambo-power`, the
  documented PyPI trusted-publishing project-page shorthand) — this is what makes a
  required-reviewer rule on that environment (T1) act as a manual-approval gate. The environment
  doesn't need to exist in repo settings yet for the YAML itself to be valid.
- **Version-consistency check** (build job, before `uv build`): strips the `v` prefix off
  `$GITHUB_REF_NAME`, reads `pyproject.toml`'s `[project].version` via stdlib `tomllib`, fails
  the job on any mismatch or on a non-`v*` ref (defensive; unreachable given the trigger, kept
  as belt-and-suspenders). Standalone — doesn't depend on S5's semantic-release landing; it'll
  hold once S5 does.

## Structural proofs (not just "I wrote it right")

1. **YAML parses**: `python -c "import yaml; yaml.safe_load(open(...))"` — exit 0.
2. **Trigger cannot be satisfied by branch push or PR** — proved programmatically, not by
   inspection alone:
   ```python
   d = yaml.safe_load(open(".github/workflows/publish.yml"))
   on_block = d[True]  # PyYAML parses bare `on:` as boolean key — expected YAML 1.1 quirk
   assert on_block == {'push': {'tags': ['v*']}}
   ```
   Passed — output: `STRUCTURAL PROOF PASSED: on block is exactly {push: {tags: [v*]}} — no
   branches, no pull_request, no workflow_dispatch`.
3. **No token/secret/password/PYPI_ string outside an explanatory comment**:
   `grep -inE 'token|secret|password|PYPI_' publish.yml` → 5 matches, all either prose comments
   explaining the deliberate absence of a credential, or the literal `id-token: write`
   permissions key itself. That key is GitHub Actions' own OIDC permission name (required
   syntax, mandated by the task's own T1), not a credential value — flagging this distinction
   explicitly since it does match the grep pattern.
4. **Version-check logic verified by simulation** (not just read): ran the exact shell logic
   locally against `GITHUB_REF_NAME=v0.0.1.dev0` (matches the repo's current `pyproject.toml`
   version — passes), `v0.1.0` (mismatch — fails with a clear message, exit 1), and `notatag`
   (fails the `v*` shape check, exit 1). All three behaved as intended.
5. **`pypa/gh-action-pypi-publish@v1.14.2` pin verified real**: `git ls-remote --tags
   https://github.com/pypa/gh-action-pypi-publish` confirms `v1.14.2` resolves to commit
   `a892a5a61159132606e93a2fa6f4358831b04d26`. (Caught myself first pinning a fabricated SHA I
   had not verified — corrected before committing; noted here for the record, not hidden.)

`actionlint` was not available (not on PATH, and not resolvable via `uv run --with` since it's a
Go binary rather than a PyPI package) — skipped per the task's own fallback instruction, YAML
validity and the structural proofs above stand in its place.

## Step-9 checklist item for the user

Before the `v0.1.0` tag is ever pushed, someone with repo-admin access needs to, in GitHub repo
settings (outside this SDLC's reach):

1. Create the `pypi` environment (Settings → Environments → New environment → name it exactly
   `pypi`).
2. Add a required-reviewer rule to it (the manual-approval gate T1 commits to).
3. Confirm pypi.org's pending-trusted-publisher form for the `mambo-power` project has these
   values, exactly matching what's in this workflow: owner `mambo10005`, repository
   `mambo-power`, workflow filename `publish.yml`, environment name `pypi`.

I have no PyPI credentials and made no live-publish attempt — this workflow has not been run,
only statically verified per the "verify the FORM, not by actually running it" instruction.

Duration: ~25 minutes.
